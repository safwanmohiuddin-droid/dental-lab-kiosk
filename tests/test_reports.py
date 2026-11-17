import io
from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import override_settings
from openpyxl import load_workbook

from inventory import services
from inventory.models import Department, Employee, Material, StockMove
from reports import queries

DASHBOARD = "/r/"


def dept_rows(start, end, department=None):
    rows = queries.by_department(queries.consumption(start, end, department))
    return {r["department__name"]: r for r in rows}


@override_settings(TIME_ZONE="Asia/Dubai")
def test_month_boundary_uses_the_lab_time_zone(material, employee):
    services.receive(material, 5)
    move = services.issue(material, 1, employee)
    # 21:00 UTC on 31 Oct is 01:00 on 1 Nov in Dubai (UTC+4).
    StockMove.objects.filter(pk=move.pk).update(created_at=datetime(2026, 10, 31, 21, tzinfo=UTC))

    assert dept_rows(date(2026, 11, 1), date(2026, 11, 30))["CAD/CAM"]["net_qty"] == 1
    assert dept_rows(date(2026, 10, 1), date(2026, 10, 31)) == {}


def test_returns_reduce_consumption_at_the_issue_cost(material, employee):
    services.receive(material, 10, D("80"))
    taken = services.issue(material, 4, employee)
    services.receive(material, 10, D("200"))  # average cost moves, the return must not
    services.return_(taken, 1)

    row = dept_rows(date.min, date.today())["CAD/CAM"]
    assert (row["net_qty"], row["net_cost"], row["issues"]) == (3, D("240"), 1)


def test_missing_prices_are_skipped_and_coverage_shows_the_gap(material, employee):
    priced = Material.objects.create(name="Bur", barcode="BUR-1")
    services.receive(material, 10)  # no price
    services.receive(priced, 10, D("10"))
    services.issue(material, 2, employee)
    services.issue(priced, 1, employee)

    row = dept_rows(date.min, date.today())["CAD/CAM"]
    assert (row["net_qty"], row["net_cost"], queries.coverage(row)) == (3, D("10"), 50)


def test_no_prices_at_all_means_unknown_cost_not_zero(material, employee):
    services.receive(material, 3)
    services.issue(material, 1, employee)
    totals = queries.totals(queries.by_department(queries.consumption(date.min, date.today())))
    assert totals["net_cost"] is None and totals["coverage"] == 0


def test_department_filter(material, employee):
    ceramics = Department.objects.create(name="Ceramics")
    other = Employee.objects.create(name="Carlos", department=ceramics)
    services.receive(material, 10)
    services.issue(material, 2, employee)
    services.issue(material, 3, other)
    assert list(dept_rows(date.min, date.today(), ceramics)) == ["Ceramics"]


def test_people_are_grouped_by_the_department_on_the_move(material, employee):
    services.receive(material, 10)
    services.issue(material, 2, employee)
    employee.department = Department.objects.create(name="Ceramics")
    employee.save()
    services.issue(material, 1, employee)
    rows = queries.by_person(queries.consumption(date.min, date.today()))
    pairs = {(r["department__name"], r["net_qty"]) for r in rows}
    assert pairs == {("CAD/CAM", 2), ("Ceramics", 1)}


# views


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
    # A non-staff user (personal kiosk login) is sent to the admin login, even with permission.
    client.force_login(owner(django_user_model))
    assert "/admin/login/" in client.get(DASHBOARD).url


def test_reports_need_2fa_when_the_admin_does(client, django_user_model, settings):
    settings.ADMIN_REQUIRE_2FA = True
    client.force_login(owner(django_user_model, is_staff=True))  # password only, no TOTP
    assert "/admin/login/" in client.get(DASHBOARD).url


@pytest.mark.parametrize("url", ["/r/", "/r/materials/", "/r/people/"])
def test_pages_render_with_data(admin_client, material, employee, url):
    services.receive(material, 10, D("80"))
    services.issue(material, 4, employee)
    page = admin_client.get(url)
    assert page.status_code == 200
    assert b"Zirconia disc" in page.content or b"CAD/CAM" in page.content
    assert b'style="width: 100%"' in page.content


def test_invalid_dates_fall_back_to_this_month(admin_client):
    page = admin_client.get(DASHBOARD, {"start": "2026-12-01", "end": "2026-11-01"})
    assert page.status_code == 200 and b"start date is after the end date" in page.content


def test_dashboard_query_count_does_not_grow_with_rows(admin_client, django_assert_max_num_queries):
    dept = Department.objects.create(name="Ceramics")
    for n in range(5):
        e = Employee.objects.create(name=f"E{n}", department=dept)
        m = Material.objects.create(name=f"M{n}", barcode=f"M-{n}")
        services.receive(m, 10, D("1"))
        services.issue(m, 1, e)
    with django_assert_max_num_queries(10):  # session, user, form choices, 5 report queries
        admin_client.get(DASHBOARD)


@pytest.mark.parametrize(
    ("url", "sheets"),
    [
        ("/r/", ["Departments", "Top materials by qty", "Top materials by cost", "Top people"]),
        ("/r/materials/", ["Materials"]),
        ("/r/people/", ["People"]),
    ],
)
def test_excel_export(admin_client, material, employee, url, sheets):
    services.receive(material, 10, D("80"))
    services.issue(material, 4, employee)
    response = admin_client.get(url, {"format": "xlsx"})
    wb = load_workbook(io.BytesIO(response.content))
    assert wb.sheetnames == sheets
    assert wb.active.max_row == 2  # header + one row


def test_seed_moves_keeps_the_ledger_consistent(db, settings):
    settings.DEBUG = True  # demo data only (seed_demo refuses otherwise)
    call_command("seed_moves", count=500)
    call_command("check_ledger")
    assert StockMove.objects.filter(kind="issue").count() == 500
    issue_times = {m.pk: m.created_at for m in StockMove.objects.filter(kind="issue")}
    for r in StockMove.objects.filter(kind="return"):
        assert r.created_at > issue_times[r.returns_move_id]


def test_top_by_cost_puts_unknown_cost_last():
    rows = [{"net_cost": None}, {"net_cost": D("5")}, {"net_cost": D("50")}]
    assert [r["net_cost"] for r in queries.top_by_cost(rows, 3)] == [D("50"), D("5"), None]
