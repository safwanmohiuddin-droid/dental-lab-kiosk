import csv
import io
from datetime import timedelta
from functools import wraps

from django import forms
from django.contrib import admin
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from inventory.models import Department, Employee, Material

from . import engine

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


def _presets():
    today = timezone.localdate()  # the lab's date, not UTC (ADR 0016)
    month = today.replace(day=1)
    last_month_end = month - timedelta(days=1)
    return {
        "this_week": ("This week", today - timedelta(days=today.weekday()), today),
        "this_month": ("This month", month, today),
        "last_month": ("Last month", last_month_end.replace(day=1), last_month_end),
        "last_90": ("Last 90 days", today - timedelta(days=89), today),
        "this_year": ("This year", today.replace(month=1, day=1), today),
        "custom": ("Pick dates", None, None),
    }


class ReportForm(forms.Form):
    measure = forms.ChoiceField(
        choices=[(k, v[0]) for k, v in engine.MEASURES.items()], initial="units"
    )
    by = forms.ChoiceField(
        choices=[("", "Nothing")] + [(k, v[0]) for k, v in engine.DIMENSIONS.items()],
        required=False,
        initial="material",
    )
    every = forms.ChoiceField(
        choices=[("", "Whole period")] + [(k, v[0]) for k, v in engine.GRAINS.items()],
        required=False,
        initial="week",
    )
    period = forms.ChoiceField(choices=[], initial="this_month")
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    department = forms.ModelChoiceField(Department.objects.all(), required=False, empty_label="All")
    category = forms.ChoiceField(required=False)
    material = forms.ModelChoiceField(Material.objects.all(), required=False, empty_label="All")
    person = forms.ModelChoiceField(Employee.objects.all(), required=False, empty_label="Everyone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["period"].choices = [(k, v[0]) for k, v in _presets().items()]
        categories = Material.objects.exclude(category="").values_list("category", flat=True)
        self.fields["category"].choices = [("", "All")] + [(c, c) for c in sorted(set(categories))]

    def clean(self):
        data = super().clean()
        label, start, end = _presets()[data.get("period") or "this_month"]
        if data.get("period") == "custom":
            start, end = data.get("start"), data.get("end")
            if not (start and end):
                raise forms.ValidationError("Pick both dates.")
            if start > end:
                raise forms.ValidationError("The start date is after the end date.")
        data["start"], data["end"] = start, end
        return data


DEFAULTS = {"measure": "units", "by": "material", "every": "week", "period": "this_month"}


def _spec(request):
    """The report the URL asks for; bad input shows its error and falls back to the default."""
    # Missing choices fall back one by one, so a link that sets only "period" still works.
    form = ReportForm({**DEFAULTS, **request.GET.dict()})
    if not form.is_valid():
        fallback = ReportForm(DEFAULTS)
        fallback.is_valid()
        data, error = (
            fallback.cleaned_data,
            " ".join(form.non_field_errors()) or "Check the choices.",
        )
    else:
        data, error = form.cleaned_data, None
    spec = engine.Spec(
        start=data["start"],
        end=data["end"],
        measure=data["measure"],
        by=data["by"],
        every=data["every"],
        department=data["department"],
        category=data["category"],
        material=data["material"],
        person=data["person"],
    )
    return form, spec, error


def _export(report, fmt):
    header = [c or "" for c in report.columns]
    body = [
        [r["label"], *r["values"]] + ([r["total"]] if len(r["values"]) > 1 else [])
        for r in report.rows
    ]
    if not report.spec.by and not report.spec.every:
        body = [[report.measure_label, report.total]]
        header = ["", report.measure_label]
    name = f"report-{report.spec.start}-{report.spec.end}"
    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerows([header, *body])
        response = HttpResponse(out.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{name}.csv"'
        return response
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    for row in [header, *body]:
        ws.append(row)
    data = io.BytesIO()
    wb.save(data)
    response = HttpResponse(data.getvalue(), content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{name}.xlsx"'
    return response


@staff_report
def builder(request):
    form, spec, error = _spec(request)
    report = engine.run(spec)
    fmt = request.GET.get("format")
    if fmt in ("csv", "xlsx"):
        return _export(report, fmt)
    leader = report.rows[0] if spec.by and report.rows else None
    query = request.GET.copy()
    query.pop("format", None)
    return render(
        request,
        "reports/builder.html",
        {
            "form": form,
            "report": report,
            "error": error,
            "leader": leader,
            "query": query.urlencode(),
        },
    )


@staff_report
def materials(request):
    return redirect(
        f"{reverse('reports:dashboard')}?by=material&every=&measure=units&period=this_month"
    )


@staff_report
def people(request):
    return redirect(
        f"{reverse('reports:dashboard')}?by=person&every=&measure=units&period=this_month"
    )
