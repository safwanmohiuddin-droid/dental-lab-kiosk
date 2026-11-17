import io

from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from openpyxl import Workbook

from inventory.models import Department

from . import queries

TOP = 10
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def staff_report(view):
    # Anonymous -> admin login; logged in without permission -> 403.
    return login_required(
        permission_required("inventory.view_stockmove", raise_exception=True)(view),
        login_url="admin:login",
    )


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


def _period(request):
    """Validated filters; an invalid query string shows its errors and falls back to this month."""
    form = PeriodForm(request.GET)
    return form, (form.cleaned_data if form.is_valid() else _this_month())


FIGURES = [
    ("Net qty", "net_qty"),
    ("Cost", "net_cost"),
    ("Issues", "issues"),
    ("Cost coverage %", "coverage"),
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
    return render(
        request,
        "reports/dashboard.html",
        {
            "form": form,
            "f": f,
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
    return render(request, "reports/materials.html", {"form": form, "f": f, "rows": rows})


@staff_report
def people(request):
    form, f = _period(request)
    rows = queries.with_bars(queries.by_person(_moves(f)))
    if _wants_xlsx(request):
        return _xlsx(f"people-{f['start']}-{f['end']}.xlsx", [("People", PERSON, rows)])
    return render(request, "reports/people.html", {"form": form, "f": f, "rows": rows})
