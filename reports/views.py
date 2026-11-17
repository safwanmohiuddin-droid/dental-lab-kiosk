import io
from datetime import timedelta
from functools import wraps

from django import forms
from django.contrib import admin
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from inventory.models import Department

from . import queries

TOP = 10
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def staff_report(view):
    """Same gate as the admin (staff, and 2FA-verified when ADMIN_REQUIRE_2FA is on): a password
    from the kiosk's personal login alone must not open cost reports.
    Not allowed in -> admin login; allowed in without permission -> 403."""
    view = permission_required("inventory.view_stockmove", raise_exception=True)(view)

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not admin.site.has_permission(request):  # needs the request, not just the user
            return redirect_to_login(request.get_full_path(), reverse("admin:login"))
        return view(request, *args, **kwargs)

    return wrapper


class PeriodForm(forms.Form):
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    department = forms.ModelChoiceField(
        Department.objects.all(), required=False, empty_label="All departments"
    )

    def clean(self):
        data = super().clean()
        default = _this_month()
        data["start"] = data.get("start") or default["start"]
        data["end"] = data.get("end") or default["end"]
        if data["start"] > data["end"]:
            raise forms.ValidationError("The start date is after the end date.")
        return data


def _this_month():
    today = timezone.localdate()  # the lab's date, not UTC (ADR 0016)
    return {"start": today.replace(day=1), "end": today, "department": None}


def _quick_periods(request, f):
    """One-tap periods instead of date pickers (R6, R8)."""
    today = timezone.localdate()
    first = today.replace(day=1)
    last_month_end = first - timedelta(days=1)
    choices = [
        ("This week", today - timedelta(days=today.weekday()), today),
        ("This month", first, today),
        ("Last month", last_month_end.replace(day=1), last_month_end),
        ("Last 12 months", (first - timedelta(days=335)).replace(day=1), today),
    ]
    keep = request.GET.copy()
    for name in ("start", "end", "format"):
        keep.pop(name, None)
    periods = []
    for label, start, end in choices:
        query = keep.copy()
        query["start"], query["end"] = start.isoformat(), end.isoformat()
        current = (f["start"], f["end"]) == (start, end)
        periods.append({"label": label, "query": query.urlencode(), "current": current})
    return periods


def _page(request, template, form, f, **context):
    periods = _quick_periods(request, f)
    custom = not any(p["current"] for p in periods)
    return render(
        request, template, {"form": form, "f": f, "periods": periods, "custom": custom, **context}
    )


def _period(request):
    """Validated filters; an invalid query string shows its errors and falls back to this month."""
    form = PeriodForm(request.GET)
    return form, (form.cleaned_data if form.is_valid() else _this_month())


# The lab's words, not database words (docs/ux-rules.md, R2).
FIGURES = [
    ("Used (taken minus returned)", "net_qty"),
    ("Cost", "net_cost"),
    ("Times taken", "issues"),
    ("Has a price %", "coverage"),
]
DEPARTMENT = [("Department", "department__name"), *FIGURES]
MATERIAL = [
    ("Material", "material__name"),
    ("Barcode", "material__barcode"),
    ("Unit", "material__unit"),
    *FIGURES,
]
PERSON = [("Employee", "employee__name"), ("Department", "department__name"), *FIGURES]


def _xlsx(filename, sheets):
    """sheets: [(title, columns, rows)] where columns are (header, row key) pairs."""
    wb = Workbook()
    wb.remove(wb.active)
    for title, columns, rows in sheets:
        ws = wb.create_sheet(title)
        ws.append([header for header, _ in columns])
        for row in rows:
            ws.append([row[key] for _, key in columns])
    out = io.BytesIO()
    wb.save(out)
    response = HttpResponse(out.getvalue(), content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _moves(f):
    return queries.consumption(f["start"], f["end"], f["department"])


def _wants_xlsx(request):
    return request.GET.get("format") == "xlsx"


@staff_report
def dashboard(request):
    form, f = _period(request)
    moves = _moves(f)
    # Three scans of the moves: departments, materials (both top lists), people.
    departments = queries.with_bars(queries.by_department(moves))
    materials = list(queries.by_material(moves))
    top_qty = queries.with_bars(dict(r) for r in materials[:TOP])
    top_cost = queries.with_bars(
        (dict(r) for r in queries.top_by_cost(materials, TOP)), key="net_cost"
    )
    people = queries.with_bars(queries.by_person(moves)[:TOP])
    if _wants_xlsx(request):
        return _xlsx(
            f"consumption-{f['start']}-{f['end']}.xlsx",
            [
                ("Departments", DEPARTMENT, departments),
                ("Top materials by qty", MATERIAL, top_qty),
                ("Top materials by cost", MATERIAL, top_cost),
                ("Top people", PERSON, people),
            ],
        )
    return _page(
        request,
        "reports/dashboard.html",
        form,
        f,
        **{
            "top_department": departments[0] if departments else None,
            "totals": queries.totals(departments),
            "departments": departments,
            "top_qty": top_qty,
            "top_cost": top_cost,
            "people": people,
        },
    )


@staff_report
def materials(request):
    form, f = _period(request)
    rows = queries.with_bars(queries.by_material(_moves(f)))
    if _wants_xlsx(request):
        return _xlsx(f"materials-{f['start']}-{f['end']}.xlsx", [("Materials", MATERIAL, rows)])
    return _page(request, "reports/materials.html", form, f, rows=rows)


@staff_report
def people(request):
    form, f = _period(request)
    rows = queries.with_bars(queries.by_person(_moves(f)))
    if _wants_xlsx(request):
        return _xlsx(f"people-{f['start']}-{f['end']}.xlsx", [("People", PERSON, rows)])
    return _page(request, "reports/people.html", form, f, rows=rows)
