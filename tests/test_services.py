import uuid
from decimal import Decimal as D

import pytest
from django.core.management import CommandError, call_command

from inventory import services
from inventory.models import Department, StockMove
from inventory.services import InsufficientStock, StockError


def fresh(obj):
    obj.refresh_from_db()
    return obj


# receive


def test_first_receipt_sets_stock_and_cost(material):
    services.receive(material, 10, D("80"))
    m = fresh(material)
    assert (m.qty_on_hand, m.avg_cost) == (10, 80)


def test_second_receipt_blends_average_cost(material):
    services.receive(material, 10, D("80"))
    services.receive(material, 30, D("100"))
    assert fresh(material).avg_cost == D("95")  # (10*80 + 30*100) / 40


def test_receipt_without_cost_keeps_average(material):
    services.receive(material, 10, D("80"))
    services.receive(material, 5)
    m = fresh(material)
    assert (m.qty_on_hand, m.avg_cost) == (15, 80)


def test_price_is_optional_everywhere(material, employee):
    services.receive(material, 10)
    move = services.issue(material, 2, employee)
    assert fresh(material).avg_cost is None and move.unit_cost is None


def test_receipt_into_negative_stock_takes_new_cost(material, employee):
    # Offline issue pushed stock to -2; blending would divide by on_hand + qty = 0 below.
    services.issue(material, 2, employee, allow_negative=True)
    services.receive(material, 2, D("50"))
    m = fresh(material)
    assert (m.qty_on_hand, m.avg_cost) == (0, 50)


def test_average_cost_is_rounded_to_four_places(material):
    services.receive(material, 3, D("10"))
    services.receive(material, 3, D("10.00005"))
    assert fresh(material).avg_cost == D("10.0000")


@pytest.mark.parametrize("qty", [0, -1])
def test_receive_rejects_non_positive_qty(material, qty):
    with pytest.raises(StockError):
        services.receive(material, qty)


def test_floats_are_refused(material):
    with pytest.raises(TypeError):
        services.receive(material, 0.1)


def test_negative_cost_is_refused(material):
    with pytest.raises(StockError):
        services.receive(material, 1, D("-1"))


# issue


def test_issue_takes_stock_and_snapshots_cost_and_department(material, employee):
    services.receive(material, 10, D("80"))
    move = services.issue(material, 4, employee, case_ref="C-1001")
    assert fresh(material).qty_on_hand == 6
    assert (move.qty, move.unit_cost, move.department, move.case_ref) == (
        -4,
        80,
        employee.department,
        "C-1001",
    )


def test_department_on_old_issues_survives_a_transfer(material, employee):
    services.receive(material, 5)
    move = services.issue(material, 1, employee)
    employee.department = Department.objects.create(name="Ceramics")
    employee.save()
    assert fresh(move).department.name == "CAD/CAM"


def test_issue_more_than_on_hand_is_refused(material, employee):
    services.receive(material, 3)
    with pytest.raises(InsufficientStock):
        services.issue(material, 4, employee)
    assert fresh(material).qty_on_hand == 3 and not StockMove.objects.filter(kind="issue")


def test_stock_messages_print_round_numbers_plainly(material, employee):
    # Decimal("10.000").normalize() is 1E+1; users must see "10".
    services.receive(material, 10)
    with pytest.raises(InsufficientStock, match="Only 10 disc of"):
        services.issue(material, 11, employee)
    taken = services.issue(material, 10, employee)
    with pytest.raises(StockError, match="Only 10 disc left to return"):
        services.return_(taken, 20)


def test_offline_issue_beyond_stock_is_recorded_and_flagged(material, employee):
    move = services.issue(material, 2, employee, allow_negative=True)
    assert move.flagged and fresh(material).qty_on_hand == -2


def test_inactive_employee_cannot_take_stock(material, employee):
    services.receive(material, 5)
    employee.active = False
    employee.save()
    with pytest.raises(StockError):
        services.issue(material, 1, employee)


def test_archived_material_cannot_be_issued(material, employee):
    services.receive(material, 5)
    material.active = False
    material.save()
    with pytest.raises(StockError):
        services.issue(material, 1, employee)


# idempotency (ADR 0007)


def test_same_key_twice_records_one_issue(material, employee):
    services.receive(material, 10)
    key = uuid.uuid4()
    first = services.issue(material, 2, employee, key=key)
    again = services.issue(material, 2, employee, key=key)
    assert first.pk == again.pk
    assert fresh(material).qty_on_hand == 8


def test_key_reused_for_a_different_move_is_refused(material, employee):
    services.receive(material, 10)
    key = uuid.uuid4()
    services.issue(material, 2, employee, key=key)
    with pytest.raises(StockError):
        services.issue(material, 3, employee, key=key)


# return (ADR 0011)


def test_return_credits_the_issue_cost_not_todays_average(material, employee):
    services.receive(material, 10, D("80"))
    taken = services.issue(material, 4, employee)
    services.receive(material, 10, D("200"))  # average moves to 155 for the 16 on hand
    back = services.return_(taken, 1)
    assert back.unit_cost == 80 and back.department == taken.department
    assert fresh(material).qty_on_hand == 17


def test_cannot_return_more_than_was_issued(material, employee):
    services.receive(material, 10)
    taken = services.issue(material, 3, employee)
    services.return_(taken, 2)
    with pytest.raises(StockError):
        services.return_(taken, 2)


def test_only_issues_can_be_returned(material):
    receipt = services.receive(material, 5)
    with pytest.raises(StockError):
        services.return_(receipt, 1)


# adjust


def test_adjustment_needs_a_reason(material):
    with pytest.raises(StockError):
        services.adjust(material, 1, note=" ")


def test_adjustment_cannot_go_below_zero(material):
    services.receive(material, 2)
    with pytest.raises(InsufficientStock):
        services.adjust(material, -3, note="count")


def test_adjustment_both_ways(material):
    services.receive(material, 10, D("5"))
    services.adjust(material, -2, note="broken")
    services.adjust(material, 1, note="found one")
    m = fresh(material)
    assert (m.qty_on_hand, m.avg_cost) == (9, 5)


# invariant


def test_check_ledger_passes_then_catches_drift(material, employee):
    services.receive(material, 10)
    services.issue(material, 3, employee)
    call_command("check_ledger")
    material.qty_on_hand = 99  # simulate a write that bypassed the services
    material.save()
    with pytest.raises(CommandError):
        call_command("check_ledger")
