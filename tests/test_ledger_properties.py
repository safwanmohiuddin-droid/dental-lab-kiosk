"""Random sequences of stock operations must never break the ledger's invariants."""

import uuid
from decimal import Decimal as D

from django.db.models import Sum
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from inventory import services
from inventory.models import Material, StockMove
from inventory.services import StockError

qty = st.decimals(min_value=D("0.001"), max_value=D("500"), places=3)
cost = st.none() | st.decimals(min_value=D("0"), max_value=D("5000"), places=4)

operation = st.one_of(
    st.tuples(st.just("receive"), qty, cost),
    st.tuples(st.just("issue"), qty, st.booleans()),  # bool: offline sync allowed negative
    st.tuples(st.just("return"), st.integers(min_value=0), qty),  # int: which earlier issue
    st.tuples(st.just("adjust"), qty, st.booleans()),  # bool: found (+) or missing (-)
)


@settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(ops=st.lists(operation, max_size=25))
def test_ledger_invariants_hold_for_any_sequence(employee, ops):
    material = Material.objects.create(name="Disc", barcode=uuid.uuid4().hex)
    issues = []

    for op, a, b in ops:
        try:
            if op == "receive":
                services.receive(material, a, b)
            elif op == "issue":
                issues.append(services.issue(material, a, employee, allow_negative=b))
            elif op == "return" and issues:
                services.return_(issues[a % len(issues)], b)
            elif op == "adjust":
                services.adjust(material, a if b else -a, note="count")
        except StockError:
            pass  # refusals are fine; corrupting state is not

    material.refresh_from_db()
    moves = StockMove.objects.filter(material=material)

    # 1. The cache always equals the ledger.
    assert material.qty_on_hand == (moves.aggregate(s=Sum("qty"))["s"] or 0)
    # 2. Cost is unknown or non-negative, never garbage.
    assert material.avg_cost is None or material.avg_cost >= 0
    # 3. Stock only goes negative through a flagged offline issue.
    if material.qty_on_hand < 0:
        assert moves.filter(flagged=True).exists()
    # 4. No issue is ever returned more than was taken.
    for issued in issues:
        returned = issued.returns.aggregate(s=Sum("qty"))["s"] or 0
        assert returned <= -issued.qty
