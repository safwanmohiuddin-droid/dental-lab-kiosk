"""Consumption figures, aggregated in SQL. Consumption = issues minus returns (ADR 0011)."""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from inventory.models import StockMove

QTY_FIELD = DecimalField(max_digits=18, decimal_places=3)
COST_FIELD = DecimalField(max_digits=24, decimal_places=4)

# Issues are stored negative and returns positive, so -SUM(qty) is the net amount consumed.
CONSUMPTION = {
    "net_qty": Coalesce(Sum(-F("qty")), Value(Decimal(0)), output_field=QTY_FIELD),
    # Moves without a unit cost add NULL, which SUM skips: cost is "known cost only" (ADR 0005).
    "net_cost": Sum(-F("qty") * F("unit_cost"), output_field=COST_FIELD),
    "issues": Count("id", filter=Q(kind=StockMove.Kind.ISSUE)),
    "priced": Count("id", filter=Q(kind=StockMove.Kind.ISSUE, unit_cost__isnull=False)),
}


def period_bounds(start, end):
    """Lab-local dates (inclusive) -> aware [from, to) in the lab TIME_ZONE (ADR 0016)."""
    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(start, time.min), tz),
        timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz),
    )


def consumption(start, end, department=None):
    since, until = period_bounds(start, end)
    moves = StockMove.objects.filter(
        kind__in=[StockMove.Kind.ISSUE, StockMove.Kind.RETURN],
        created_at__gte=since,
        created_at__lt=until,
    )
    return moves.filter(department=department) if department else moves


def coverage(row):
    """Share of issues that carry a cost, as a whole percent; None when there were no issues."""
    return round(100 * row["priced"] / row["issues"]) if row["issues"] else None
