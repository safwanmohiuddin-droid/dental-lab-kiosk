"""The only code allowed to change stock (ADR 0004).

Every function: lock the material row, validate, insert one StockMove, update the cached
qty_on_hand / avg_cost, all in one transaction. Quantities passed in are positive amounts.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum

from .models import Material, StockMove

COST_PLACES = Decimal("0.0001")


class StockError(ValueError):
    """A stock operation that must not happen. The message is safe to show to users."""


class InsufficientStock(StockError):
    pass


def _amount(value):
    # ADR 0012: never accept floats; 0.1 + 0.2 must not leak into stock.
    if isinstance(value, float):
        raise TypeError("Use Decimal or int for quantities and costs, not float.")
    return value if value is None else Decimal(value)


def _positive(qty):
    qty = _amount(qty)
    if qty <= 0:
        raise StockError("Quantity must be more than zero.")
    return qty


def _blend(material, qty, unit_cost):
    """New moving average after qty units at unit_cost come into stock."""
    if unit_cost is None:
        return material.avg_cost  # unknown cost: assume it matches what we have
    on_hand = material.qty_on_hand
    if on_hand <= 0 or material.avg_cost is None:
        return unit_cost  # nothing (or nothing priced) to blend with; also avoids / 0
    total = on_hand * material.avg_cost + qty * unit_cost
    return (total / (on_hand + qty)).quantize(COST_PLACES, ROUND_HALF_UP)


def _post(material, key, *, avg_cost, **fields):
    """Insert the move and update the cached balance. The caller already holds the row lock."""
    move = StockMove(material=material, **fields)
    if key is not None:
        move.idempotency_key = key
    material.qty_on_hand += move.qty
    material.avg_cost = avg_cost
    move.save()
    material.save(update_fields=["qty_on_hand", "avg_cost"])
    return move


def _locked(material_id):
    return Material.objects.select_for_update().get(pk=material_id)


def _replay(key, **expected):
    """Return the move already recorded under this key, or None (ADR 0007)."""
    if key is None:
        return None
    move = StockMove.objects.filter(idempotency_key=key).first()
    if move is None:
        return None
    if any(getattr(move, name) != value for name, value in expected.items()):
        raise StockError("This request ID was already used for a different stock move.")
    return move


@transaction.atomic
def receive(material, qty, unit_cost=None, *, key=None, user=None, note="", import_batch=None):
    qty, unit_cost = _positive(qty), _amount(unit_cost)
    if unit_cost is not None and unit_cost < 0:
        raise StockError("Cost can't be negative.")
    material = _locked(material.pk)
    if done := _replay(key, kind="receipt", material_id=material.pk, qty=qty):
        return done
    if not material.active:
        raise StockError(f"{material.name} is archived.")
    return _post(
        material,
        key,
        avg_cost=_blend(material, qty, unit_cost),
        kind="receipt",
        qty=qty,
        unit_cost=unit_cost,
        created_by=user,
        note=note,
        import_batch=import_batch,
    )


@transaction.atomic
def issue(
    material,
    qty,
    employee,
    *,
    case_ref="",
    key=None,
    client_at=None,
    user=None,
    allow_negative=False,
):
    """Take stock out for an employee's department.

    allow_negative is for offline sync (ADR 0008): the material already left the shelf, so the
    move is recorded and flagged instead of refused.
    """
    qty = _positive(qty)
    material = _locked(material.pk)
    if done := _replay(key, kind="issue", material_id=material.pk, qty=-qty):
        return done
    if not material.active:
        raise StockError(f"{material.name} is archived.")
    if not employee.active:
        raise StockError(f"{employee.name} is no longer active.")
    short = qty > material.qty_on_hand
    if short and not allow_negative:
        raise InsufficientStock(
            f"Only {material.qty_on_hand.normalize()} {material.unit} of {material.name} in stock."
        )
    return _post(
        material,
        key,
        avg_cost=material.avg_cost,
        kind="issue",
        qty=-qty,
        unit_cost=material.avg_cost,
        employee=employee,
        department_id=employee.department_id,  # snapshot: survives a department change
        case_ref=case_ref,
        client_at=client_at,
        created_by=user,
        flagged=short,
    )


@transaction.atomic
def return_(issue_move, qty, *, key=None, user=None, note=""):
    """Put part of an issue back on the shelf, credited at the issue's cost (ADR 0011)."""
    qty = _positive(qty)
    material = _locked(issue_move.material_id)  # also serialises concurrent returns
    if done := _replay(key, kind="return", returns_move_id=issue_move.pk, qty=qty):
        return done
    if issue_move.kind != StockMove.Kind.ISSUE:
        raise StockError("Only issues can be returned.")
    returned = issue_move.returns.aggregate(total=Sum("qty"))["total"] or 0
    left = -issue_move.qty - returned
    if qty > left:
        raise StockError(f"Only {left.normalize()} {material.unit} left to return.")
    return _post(
        material,
        key,
        avg_cost=_blend(material, qty, issue_move.unit_cost),
        kind="return",
        qty=qty,
        unit_cost=issue_move.unit_cost,
        employee_id=issue_move.employee_id,
        department_id=issue_move.department_id,
        returns_move=issue_move,
        case_ref=issue_move.case_ref,
        created_by=user,
        note=note,
    )


@transaction.atomic
def adjust(material, qty, *, note, key=None, user=None):
    """Stock count correction. qty is signed: +found, -missing. A reason is required."""
    qty = _amount(qty)
    if qty == 0:
        raise StockError("An adjustment can't be zero.")
    if not note.strip():
        raise StockError("Say why stock is being adjusted.")
    material = _locked(material.pk)
    if done := _replay(key, kind="adjust", material_id=material.pk, qty=qty):
        return done
    if material.qty_on_hand + qty < 0:
        raise InsufficientStock("An adjustment can't take stock below zero.")
    return _post(
        material,
        key,
        avg_cost=material.avg_cost,
        kind="adjust",
        qty=qty,
        unit_cost=material.avg_cost,
        created_by=user,
        note=note,
    )
