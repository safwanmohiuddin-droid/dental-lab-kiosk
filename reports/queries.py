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


def summarize(moves, *group_by):
    return moves.values(*group_by).annotate(**CONSUMPTION)


def totals(department_rows):
    """Period totals summed from the department rows, saving one more scan of the moves.

    Exact because every issue and return has a department (DB constraint).
    """
    rows = list(department_rows)
    costs = [r["net_cost"] for r in rows if r["net_cost"] is not None]
    row = {
        "net_qty": sum(r["net_qty"] for r in rows),
        "net_cost": sum(costs) if costs else None,
        "issues": sum(r["issues"] for r in rows),
        "priced": sum(r["priced"] for r in rows),
    }
    row["coverage"] = coverage(row)
    return row


def by_department(moves):
    return summarize(moves, "department_id", "department__name").order_by("-net_qty")


def by_material(moves):
    rows = summarize(moves, "material_id", "material__name", "material__unit", "material__barcode")
    return rows.order_by("-net_qty", "material__name")


def by_person(moves):
    rows = summarize(moves, "employee_id", "employee__name", "department__name")
    return rows.order_by("-net_qty", "employee__name")


def top_by_cost(rows, n):
    """Highest known cost first; unknown cost last."""
    return sorted(rows, key=lambda r: (r["net_cost"] is None, -(r["net_cost"] or 0)))[:n]


def coverage(row):
    """Share of issues that carry a cost, as a whole percent; None when there were no issues."""
    return round(100 * row["priced"] / row["issues"]) if row["issues"] else None


def with_bars(rows, key="net_qty"):
    """Add each row's bar width (percent of the largest value) for CSS bar charts."""
    rows = list(rows)
    top = max((r[key] or 0 for r in rows), default=0)
    for r in rows:
        r["bar"] = round(100 * (r[key] or 0) / top) if top > 0 else 0
        r["coverage"] = coverage(r)
    return rows
