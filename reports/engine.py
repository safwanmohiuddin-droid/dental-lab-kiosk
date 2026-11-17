"""Report engine: any measure, split by any dimension, over any time grain (ADR 0037).

    run(Spec(...)) -> Report(rows, columns, chart, totals, notes)

Everything is aggregated in SQL by reusing the consumption figures in queries.py.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from . import queries

MEASURES = {  # key: (label, field produced by queries.CONSUMPTION)
    "units": ("Units used", "net_qty"),
    "cost": ("Cost", "net_cost"),
    "takes": ("Times taken", "issues"),
}
DIMENSIONS = {  # key: (label, field, label for empty values)
    "department": ("Department", "department__name", "No department"),
    "material": ("Material", "material__name", "Unknown material"),
    "person": ("Person", "employee__name", "Not recorded"),
    "category": ("Category", "material__category", "No category"),
    "case": ("Case number", "case_ref", "No case number"),
}
GRAINS = {"day": ("Day", TruncDay), "week": ("Week", TruncWeek), "month": ("Month", TruncMonth)}
SERIES = 6  # lines on a time chart; the rest are summed as "Everything else"
BARS = 15  # bars on a breakdown chart; the table still lists every row


@dataclass
class Spec:
    start: date
    end: date
    measure: str = "units"
    by: str = ""  # a DIMENSIONS key, or "" for no breakdown
    every: str = ""  # a GRAINS key, or "" for no time axis
    department: object = None
    category: str = ""
    material: object = None
    person: object = None


@dataclass
class Report:
    spec: Spec
    measure_label: str
    columns: list = field(default_factory=list)  # header labels for the table
    rows: list = field(default_factory=list)  # [{"label": str, "values": [...], "total": x}]
    chart: dict = field(default_factory=dict)  # {"type", "labels", "series": [{"name", "data"}]}
    total: object = None
    takes: int = 0
    coverage: int | None = None
    notes: list = field(default_factory=list)


def _moves(spec):
    moves = queries.consumption(spec.start, spec.end, spec.department)
    if spec.category:
        moves = moves.filter(material__category=spec.category)
    if spec.material:
        moves = moves.filter(material=spec.material)
    if spec.person:
        moves = moves.filter(employee=spec.person)
    return moves


def _periods(spec):
    """Every period start between start and end, so quiet days show as 0 instead of vanishing."""
    current = spec.start
    if spec.every == "week":
        current -= timedelta(days=current.weekday())
    elif spec.every == "month":
        current = current.replace(day=1)
    periods = []
    while current <= spec.end:
        periods.append(current)
        if spec.every == "day":
            current += timedelta(days=1)
        elif spec.every == "week":
            current += timedelta(days=7)
        else:
            current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    return periods


def _period_label(day, every):
    return {
        "day": day.strftime("%d %b"),
        "week": "w/c " + day.strftime("%d %b"),
        "month": day.strftime("%b %Y"),
    }[every]


def run(spec):
    label, value_field = MEASURES[spec.measure]
    report = Report(spec=spec, measure_label=label)
    moves = _moves(spec)

    overall = moves.aggregate(**queries.CONSUMPTION)
    report.total, report.takes = overall[value_field], overall["issues"]
    report.coverage = queries.coverage(overall)
    if spec.measure == "units":
        units = sorted(set(moves.values_list("material__unit", flat=True).distinct()))
        if len(units) > 1:
            each = (
                " Each material row is one unit; the total mixes them."
                if spec.by == "material"
                else ""
            )
            report.notes.append(
                f"This adds up different units ({', '.join(units)}).{each} "
                "Filter to one material or category for a true count."
            )
    if spec.measure == "cost" and report.coverage is not None and report.coverage < 100:
        report.notes.append(f"Only {report.coverage}% of takes have a price; cost is incomplete.")

    group = [DIMENSIONS[spec.by][1]] if spec.by else []
    if spec.every:
        trunc = GRAINS[spec.every][1]("created_at", tzinfo=timezone.get_current_timezone())
        moves = moves.annotate(period=trunc)
        group.append("period")
    if not group:
        report.columns = [label]
        report.rows = [{"label": "Total", "values": [report.total], "total": report.total}]
        return report
    data = list(moves.values(*group).annotate(**queries.CONSUMPTION))

    empty = DIMENSIONS[spec.by][2] if spec.by else ""

    def name(row):
        return (row[DIMENSIONS[spec.by][1]] or empty) if spec.by else label

    if not spec.every:  # breakdown only: a bar per group
        data.sort(key=lambda r: (r[value_field] is None, -(r[value_field] or 0)))
        report.columns = [DIMENSIONS[spec.by][0], label]
        report.rows = [
            {"label": name(r), "values": [r[value_field]], "total": r[value_field]} for r in data
        ]
        top = report.rows[:BARS]
        report.chart = {
            "type": "bar",
            "labels": [r["label"] for r in top],
            "series": [{"name": label, "data": [_num(r["total"]) for r in top]}],
        }
        return report

    periods = _periods(spec)
    index = {p: i for i, p in enumerate(periods)}
    grid = {}
    for row in data:
        day = (
            timezone.localtime(row["period"]).date()
            if hasattr(row["period"], "tzinfo")
            else row["period"]
        )
        values = grid.setdefault(name(row), [None] * len(periods))
        if day in index and row[value_field] is not None:
            values[index[day]] = (values[index[day]] or 0) + row[value_field]
    totals = {k: sum(v for v in vals if v is not None) for k, vals in grid.items()}
    ordered = sorted(grid, key=lambda k: -totals[k])
    report.columns = [
        DIMENSIONS[spec.by][0] if spec.by else "",
        *(_period_label(p, spec.every) for p in periods),
        "Total",
    ]
    report.rows = [{"label": k, "values": grid[k], "total": totals[k]} for k in ordered]

    shown = ordered[:SERIES]
    series = [{"name": k, "data": [_num(v) for v in grid[k]]} for k in shown]
    rest = ordered[SERIES:]
    if rest:
        series.append(
            {
                "name": "Everything else",
                "data": [_num(sum((grid[k][i] or 0) for k in rest)) for i in range(len(periods))],
            }
        )
    report.chart = {
        "type": "line",
        "labels": [_period_label(p, spec.every) for p in periods],
        "series": series,
    }
    return report


def _num(value):
    return float(value) if value is not None else 0  # chart only; tables keep Decimal
