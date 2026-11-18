import csv
import io
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import override_settings
from openpyxl import load_workbook

from inventory import services
from inventory.models import Department, Employee, Material, StockMove
from reports import engine

DASHBOARD = "/r/"
EVER = (date(2000, 1, 1), date(2100, 1, 1))


def run(**kw):
    start, end = kw.pop("start", EVER[0]), kw.pop("end", EVER[1])
    return engine.run(engine.Spec(start=start, end=end, **kw))


def by_label(report):
    return {r["label"]: r for r in report.rows}


# engine: the numbers


@override_settings(TIME_ZONE="Asia/Dubai")
def test_month_boundary_uses_the_lab_time_zone(material, employee):
    services.receive(material, 5)
    move = services.issue(material, 1, employee)
    # 21:00 UTC on 31 Oct is 01:00 on 1 Nov in Dubai (UTC+4).
    StockMove.objects.filter(pk=move.pk).update(created_at=datetime(2026, 10, 31, 21, tzinfo=UTC))
    november = run(start=date(2026, 11, 1), end=date(2026, 11, 30), by="department")
    assert by_label(november)["CAD/CAM"]["total"] == 1
    assert run(start=date(2026, 10, 1), end=date(2026, 10, 31)).takes == 0
    monthly = run(start=date(2026, 10, 1), end=date(2026, 11, 30), every="month")
    assert monthly.rows[0]["values"] == [None, 1]  # October empty, November 1


def test_returns_reduce_consumption_at_the_issue_cost(material, employee):
    services.receive(material, 10, D("80"))
    taken = services.issue(material, 4, employee)
    services.receive(material, 10, D("200"))  # average cost moves, the return must not
    services.return_(taken, 1)
    assert (run().total, run(measure="cost").total, run(measure="takes").total) == (3, D("240"), 1)


def test_missing_prices_are_skipped_and_flagged(material, employee):
    priced = Material.objects.create(name="Bur", barcode="BUR-1")
    services.receive(material, 10)  # no price
    services.receive(priced, 10, D("10"))
    services.issue(material, 2, employee)
    services.issue(priced, 1, employee)
    report = run(measure="cost")
    assert (report.total, report.coverage) == (D("10"), 50)
    assert any("50% of takes have a price" in n for n in report.notes)


def test_no_prices_at_all_means_unknown_cost_not_zero(material, employee):
    services.receive(material, 3)
    services.issue(material, 1, employee)
    report = run(measure="cost")
    assert report.total is None and report.coverage == 0


def test_filters(material, employee):
    ceramics = Department.objects.create(name="Ceramics")
    other = Employee.objects.create(name="Carlos", department=ceramics)
    bur = Material.objects.create(name="Bur", barcode="BUR-1", category="Burs")
    for m in (material, bur):
        services.receive(m, 10)
    services.issue(material, 2, employee)
    services.issue(bur, 3, other)
    assert list(by_label(run(by="department", department=ceramics))) == ["Ceramics"]
    assert run(category="Burs").total == 3
    assert run(person=employee).total == 2
    assert run(material=material).total == 2


def test_people_rows_follow_the_department_on_the_move(material, employee):
    services.receive(material, 10)
    services.issue(material, 2, employee)
    employee.department = Department.objects.create(name="Ceramics")
    employee.save()
    services.issue(material, 1, employee)
    assert by_label(run(by="department")).keys() == {"CAD/CAM", "Ceramics"}
    assert by_label(run(by="person"))[employee.name]["total"] == 3


def test_breakdown_is_sorted_and_charted_as_bars(material, employee):
    bur = Material.objects.create(name="Bur", barcode="BUR-1")
    for m in (material, bur):
        services.receive(m, 10)
    services.issue(material, 1, employee)
    services.issue(bur, 4, employee)
    report = run(by="material")
    assert [r["label"] for r in report.rows] == ["Bur", material.name]
    assert report.chart == {
        "type": "bar",
        "labels": ["Bur", material.name],
        "series": [{"name": "Units used", "data": [4.0, 1.0]}],
    }


def test_time_axis_includes_quiet_periods(material, employee):
    services.receive(material, 10)
    move = services.issue(material, 2, employee)
    StockMove.objects.filter(pk=move.pk).update(created_at=datetime(2026, 11, 4, 10, tzinfo=UTC))
    report = run(start=date(2026, 11, 2), end=date(2026, 11, 22), every="week")
    assert len(report.chart["labels"]) == 3  # three weeks even though only one had a take
    assert report.chart["series"][0]["data"] == [2.0, 0, 0]


def test_many_groups_collapse_into_everything_else(employee):
    for i in range(8):
        m = Material.objects.create(name=f"M{i}", barcode=f"M-{i}")
        services.receive(m, 20)
        services.issue(m, i + 1, employee)
    report = run(by="material", every="month", start=date.today().replace(day=1), end=date.today())
    names = [s["name"] for s in report.chart["series"]]
    assert len(names) == engine.SERIES + 1 and names[-1] == "Everything else"
    assert report.chart["series"][-1]["data"][-1] == 1 + 2  # the two smallest: M0 and M1
    assert len(report.rows) == 8  # the table still lists every material


def test_mixed_units_are_called_out(material, employee):
    gram = Material.objects.create(name="Glaze", barcode="G-1", unit="g")
    for m in (material, gram):
        services.receive(m, 10)
        services.issue(m, 1, employee)
    assert any("different units" in n for n in run().notes)
    assert not run(material=material).notes


# builder page


def test_anonymous_is_sent_to_login(client):
    response = client.get(DASHBOARD)
    assert response.status_code == 302 and "/admin/login/" in response.url


def owner(django_user_model, **fields):
    user = django_user_model.objects.create_user("owner", password="unused-123", **fields)
    user.user_permissions.add(Permission.objects.get(codename="view_stockmove"))
    return user


def test_staff_without_permission_gets_403(client, django_user_model):
    user = django_user_model.objects.create_user("clerk", password="unused-123", is_staff=True)
    client.force_login(user)
    assert client.get(DASHBOARD).status_code == 403


def test_staff_with_view_permission_is_enough(client, django_user_model):
    client.force_login(owner(django_user_model, is_staff=True))
    assert client.get(DASHBOARD).status_code == 200


def test_kiosk_login_alone_does_not_open_reports(client, django_user_model):
    client.force_login(owner(django_user_model))
    assert "/admin/login/" in client.get(DASHBOARD).url


def test_reports_need_2fa_when_the_admin_does(client, django_user_model, settings):
    settings.ADMIN_REQUIRE_2FA = True
    client.force_login(owner(django_user_model, is_staff=True))
    assert "/admin/login/" in client.get(DASHBOARD).url


def test_builder_updates_live_without_a_show_button(admin_client, material, employee):
    services.receive(material, 10)
    services.issue(material, 2, employee)
    html = admin_client.get(DASHBOARD).content.decode()
    assert 'hx-trigger="change, submit"' in html and 'hx-push-url="true"' in html
    # Two quick changes must not let an older answer overwrite a newer one.
    assert 'hx-sync="this:replace"' in html
    assert 'id="report-chart-data"' in html
    form = html.split('class="sentence"')[1].split("</form>")[0]
    visible = form.split("<noscript>")[0] + form.split("</noscript>")[1]
    assert "<button" not in visible  # the form's only button is the no-JavaScript fallback


def test_every_choice_changes_the_report(admin_client, material, employee):
    services.receive(material, 10)
    services.issue(material, 2, employee)
    html = admin_client.get(
        DASHBOARD, {"measure": "takes", "by": "person", "every": "", "period": "this_month"}
    ).content.decode()
    assert f"<strong>{employee.name}</strong> leads." in html and '"type": "bar"' in html


def test_bad_custom_dates_explain_and_fall_back(admin_client, db):
    html = admin_client.get(
        DASHBOARD, {"period": "custom", "start": "2026-02-10", "end": "2026-01-01"}
    ).content.decode()
    assert "start date is after the end date" in html and "Showing the default report" in html


@pytest.mark.parametrize("old, by", [("/r/materials/", "material"), ("/r/people/", "person")])
def test_old_report_links_open_the_builder(admin_client, old, by):
    response = admin_client.get(old)
    assert response.status_code == 302 and f"by={by}" in response.url


def test_query_count_does_not_grow_with_rows(admin_client, employee, django_assert_max_num_queries):
    for i in range(30):
        m = Material.objects.create(name=f"M{i}", barcode=f"M-{i}")
        services.receive(m, 5)
        services.issue(m, 1, employee)
    params = {"measure": "units", "by": "material", "every": "day", "period": "this_month"}
    with django_assert_max_num_queries(20):
        assert admin_client.get(DASHBOARD, params).status_code == 200


def _sheet(admin_client, params):
    response = admin_client.get(DASHBOARD, {**params, "format": "xlsx"})
    return load_workbook(io.BytesIO(response.content))


def test_export_matches_the_report_on_screen(admin_client, material, employee):
    services.receive(material, 10)
    services.issue(material, 3, employee)
    params = {"measure": "units", "by": "department", "every": "", "period": "this_month"}
    ws = _sheet(admin_client, params)["Report"]
    assert ws["A1"].value == "Units used by department"
    assert "Filters: None" in ws["A3"].value and "admin" in ws["A4"].value
    assert [c.value for c in ws[6]] == ["Department", "Units used"]
    assert [c.value for c in ws[7]] == ["CAD/CAM", 3]
    assert [c.value for c in ws[8]] == ["Total", "=SUM(B7:B7)"]  # a live total, not a typed one
    text = admin_client.get(DASHBOARD, {**params, "format": "csv"}).content.decode()
    assert list(csv.reader(io.StringIO(text)))[1] == ["CAD/CAM", "3.000"]


def test_excel_export_is_ready_to_read_and_print(admin_client, material, employee):
    services.receive(material, 10, unit_cost=D("2.50"))
    services.issue(material, 3, employee)
    params = {"measure": "cost", "by": "material", "every": "week", "period": "this_month"}
    wb = _sheet(admin_client, params)
    ws = wb["Report"]
    width = ws.max_column
    assert ws.cell(6, width).value == "Total"
    assert ws.cell(7, width).value.startswith("=SUM(B7:")  # each row adds up its own periods
    assert ws.cell(7, 2).number_format.startswith("#,##0.00")  # money: 2 decimals, separators
    assert ws.freeze_panes == "B7" and ws.auto_filter.ref.startswith("A6:")
    assert ws.print_title_rows == "$6:$6" and ws.print_title_cols == "$A:$A"
    assert ws.page_setup.fitToWidth == 1  # a few weeks fit one page wide
    assert "Chart" in wb.sheetnames and wb["Chart"]._charts
    text = admin_client.get(DASHBOARD, {**params, "format": "csv"}).content.decode()
    assert list(csv.reader(io.StringIO(text)))[0][-1] == "Total"


def test_excel_export_of_a_plain_total_has_one_row(admin_client, material, employee):
    services.receive(material, 10)
    services.issue(material, 2, employee)
    params = {"measure": "units", "by": "", "every": "", "period": "this_month"}
    ws = _sheet(admin_client, params)["Report"]
    assert [c.value for c in ws[7]] == ["Units used", 2]
    assert ws["A8"].value is None  # no "Total" row repeating the only number


def test_report_page_can_be_printed_with_its_title(admin_client, db):
    html = admin_client.get(DASHBOARD, {"by": "person", "every": ""}).content.decode()
    assert "data-print" in html and "<h2>Units used by person</h2>" in html


def test_seed_moves_keeps_the_ledger_consistent(db, settings):
    settings.DEBUG = True  # demo data only (seed_demo refuses otherwise)
    call_command("seed_moves", count=500)
    call_command("check_ledger")
    assert StockMove.objects.filter(kind="issue").count() == 500
    issue_times = {m.pk: m.created_at for m in StockMove.objects.filter(kind="issue")}
    for r in StockMove.objects.filter(kind="return"):
        assert r.created_at > issue_times[r.returns_move_id]


def test_presets_cover_last_month(admin_client, db):
    first_of_month = date.today().replace(day=1)
    last = (first_of_month - timedelta(days=1)).replace(day=1)
    html = admin_client.get(DASHBOARD, {"period": "last_month"}).content.decode()
    assert f"{last.day} {last:%b %Y} to" in html
