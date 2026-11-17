import uuid

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError, connection, models, transaction

from inventory.models import Department, Employee, Material, StockMove


def test_no_float_fields():
    # ADR 0012: quantities and money are Decimal, never float.
    floats = [
        f"{m.__name__}.{f.name}"
        for m in apps.get_app_config("inventory").get_models()
        for f in m._meta.get_fields()
        if isinstance(f, models.FloatField)
    ]
    assert floats == []


def test_valid_issue_saves(issue):
    assert issue.pk and issue.idempotency_key


def test_valid_return_saves(issue):
    StockMove.objects.create(
        kind="return",
        material=issue.material,
        qty=1,
        employee=issue.employee,
        department=issue.department,
        returns_move=issue,
    )


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"kind": "issue", "qty": 0}, id="zero-qty"),
        pytest.param({"kind": "issue", "qty": 1}, id="issue-adds-stock"),
        pytest.param({"kind": "issue", "qty": -1, "department": None}, id="issue-no-department"),
        pytest.param({"kind": "issue", "qty": -1, "employee": None}, id="issue-no-employee"),
        pytest.param({"kind": "receipt", "qty": -1}, id="receipt-removes-stock"),
        pytest.param({"kind": "return", "qty": 1}, id="return-without-issue"),
        pytest.param({"kind": "adjust", "qty": 1, "unit_cost": -1}, id="negative-cost"),
        pytest.param({"kind": "gift", "qty": 1}, id="unknown-kind"),
    ],
)
def test_database_rejects_invalid_moves(material, employee, department, fields):
    values = {"material": material, "employee": employee, "department": department, **fields}
    with pytest.raises(IntegrityError), transaction.atomic():
        StockMove.objects.create(**values)


def test_only_returns_may_link_an_issue(issue):
    with pytest.raises(IntegrityError), transaction.atomic():
        StockMove.objects.create(kind="receipt", material=issue.material, qty=1, returns_move=issue)


def test_raw_sql_issue_without_department_is_rejected(material, employee):
    # The rule lives in Postgres, so even a hand-written INSERT can't break it.
    sql = """
        INSERT INTO inventory_stockmove
            (kind, material_id, qty, employee_id, department_id, case_ref,
             idempotency_key, created_at, flagged, note)
        VALUES ('issue', %s, -1, %s, NULL, '', %s, now(), false, '')
    """
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cur:
        cur.execute(sql, [material.pk, employee.pk, str(uuid.uuid4())])


def test_same_idempotency_key_twice_is_rejected(issue):
    with pytest.raises(IntegrityError), transaction.atomic():
        StockMove.objects.create(
            kind="issue",
            material=issue.material,
            qty=-1,
            employee=issue.employee,
            department=issue.department,
            idempotency_key=issue.idempotency_key,
        )


@pytest.mark.parametrize("barcode", ["", "2000 0001"])
def test_blank_or_spaced_barcode_is_rejected(db, barcode):
    with pytest.raises(IntegrityError), transaction.atomic():
        Material.objects.create(name="Bad", barcode=barcode)


def test_duplicate_barcode_is_rejected(material):
    with pytest.raises(IntegrityError), transaction.atomic():
        Material.objects.create(name="Copy", barcode=material.barcode)


def test_department_with_moves_cannot_be_deleted(issue):
    with pytest.raises(models.ProtectedError):
        issue.department.delete()


def test_seed_demo_is_repeatable(db):
    call_command("seed_demo")
    call_command("seed_demo")
    assert (Department.objects.count(), Employee.objects.count(), Material.objects.count()) == (
        4,
        10,
        30,
    )


def test_stock_moves_are_read_only_in_admin(admin_client, issue):
    assert admin_client.get("/admin/inventory/stockmove/add/").status_code == 403
    page = admin_client.get(f"/admin/inventory/stockmove/{issue.pk}/change/")
    assert page.status_code == 200 and b'name="_save"' not in page.content
