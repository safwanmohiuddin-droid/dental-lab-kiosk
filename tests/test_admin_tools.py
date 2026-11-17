"""Owner tools: count correction, undo, delete-or-archive, import/export, setup checklist,
and the lab's sign-in setting."""

import uuid
from decimal import Decimal as D

import pytest
import tablib
from django.contrib.auth import get_user_model

from inventory import services
from inventory.models import Department, Employee, Material, StockMove
from inventory.resources import EmployeeResource, MaterialResource
from inventory.services import InsufficientStock, StockError
from kiosk.models import Device, LabSettings


def fresh(obj):
    obj.refresh_from_db()
    return obj


# count correction


def test_count_sets_stock_to_what_is_on_the_shelf(material):
    services.receive(material, 10, D("5"))
    move = services.count(material, 12, note="stock take")
    assert (move.kind, move.qty, move.note) == ("adjust", 2, "stock take")
    assert fresh(material).qty_on_hand == 12


def test_count_that_matches_changes_nothing(material):
    services.receive(material, 10)
    assert services.count(material, 10, note="stock take") is None
    assert material.moves.count() == 1


def test_count_below_zero_is_refused(material):
    with pytest.raises(StockError):
        services.count(material, -1, note="x")


# undo


def test_undo_issue_puts_stock_back_for_the_same_department(material, employee):
    services.receive(material, 10, D("8"))
    taken = services.issue(material, 4, employee)
    back = services.undo(taken)
    assert (back.kind, back.qty, back.department, back.unit_cost) == (
        "return",
        4,
        taken.department,
        8,
    )
    assert fresh(material).qty_on_hand == 10


def test_undo_twice_is_one_undo(material, employee):
    services.receive(material, 10)
    taken = services.issue(material, 4, employee)
    assert services.undo(taken).pk == services.undo(taken).pk
    assert fresh(material).qty_on_hand == 10


def test_undo_after_partial_return_returns_the_rest(material, employee):
    services.receive(material, 10)
    taken = services.issue(material, 4, employee)
    services.return_(taken, 1)
    assert services.undo(taken).qty == 3


def test_undo_receipt_removes_it_unless_already_used(material, employee):
    receipt = services.receive(material, 5)
    services.issue(material, 4, employee)
    with pytest.raises(InsufficientStock):
        services.undo(receipt)  # 4 of the 5 already left the shelf


def test_returns_cannot_be_undone(material, employee):
    services.receive(material, 5)
    back = services.return_(services.issue(material, 2, employee), 1)
    with pytest.raises(StockError):
        services.undo(back)


# admin: delete or archive


def test_delete_button_only_without_history(admin_client, material, employee):
    unused = Material.objects.create(name="Unused", barcode="U-1")
    services.receive(material, 3)
    assert admin_client.get(f"/admin/inventory/material/{unused.pk}/delete/").status_code == 200
    assert admin_client.get(f"/admin/inventory/material/{material.pk}/delete/").status_code == 403


def test_delete_selected_deletes_unused_and_archives_the_rest(admin_client, material, employee):
    unused = Material.objects.create(name="Unused", barcode="U-1")
    services.receive(material, 3)
    admin_client.post(
        "/admin/inventory/material/",
        {"action": "delete_or_archive", "_selected_action": [unused.pk, material.pk]},
    )
    assert not Material.objects.filter(pk=unused.pk).exists()
    assert fresh(material).active is False and material.moves.exists()


def test_department_still_in_use_is_archived_not_broken(admin_client, employee):
    admin_client.post(
        "/admin/inventory/department/",
        {"action": "delete_or_archive", "_selected_action": [employee.department_id]},
    )
    assert Department.objects.get(pk=employee.department_id).active is False


def test_restore_unarchives(admin_client, material):
    Material.objects.filter(pk=material.pk).update(active=False)
    admin_client.post(
        "/admin/inventory/material/", {"action": "restore", "_selected_action": [material.pk]}
    )
    assert fresh(material).active is True


# admin: count screen and undo action


def test_count_screen_corrects_stock(admin_client, material):
    services.receive(material, 10)
    url = f"/admin/inventory/material/{material.pk}/count/"
    assert b"The system says" in admin_client.get(url).content
    admin_client.post(url, {"counted": "7", "note": "monthly count"})
    assert fresh(material).qty_on_hand == 7


def test_undo_action_on_stock_movements(admin_client, material, employee):
    services.receive(material, 10)
    taken = services.issue(material, 4, employee)
    admin_client.post(
        "/admin/inventory/stockmove/", {"action": "undo", "_selected_action": [taken.pk]}
    )
    assert fresh(material).qty_on_hand == 10


# import / export


def test_employee_import_creates_missing_departments(db):
    rows = tablib.Dataset(["Mei Lin", "CAD/CAM", True], headers=["name", "department", "active"])
    result = EmployeeResource().import_data(rows, dry_run=False)
    assert not result.has_errors()
    assert Employee.objects.get(name="Mei Lin").department.name == "CAD/CAM"


@pytest.mark.django_db
def test_material_import_never_touches_stock():
    rows = tablib.Dataset(
        ["ZIR-001", "Zirconia disc", "disc", "Discs", True, "999"],
        headers=["barcode", "name", "unit", "category", "active", "qty_on_hand"],
    )
    MaterialResource().import_data(rows, dry_run=False)
    assert Material.objects.get(barcode="ZIR-001").qty_on_hand == 0  # stock only via the ledger


@pytest.mark.django_db
def test_material_import_catches_excel_dropping_leading_zeros():
    Material.objects.create(name="Alumina", barcode="012345678905")
    rows = tablib.Dataset([12345678905, "Alumina"], headers=["barcode", "name"])
    result = MaterialResource().import_data(rows, dry_run=True)
    assert result.has_errors() or result.has_validation_errors()


def test_import_pages_offer_paste(admin_client):
    for model in ("department", "employee", "material"):
        page = admin_client.get(f"/admin/inventory/{model}/import/")
        assert page.status_code == 200 and b"paste-rows" in page.content


def test_export_works(admin_client, material):
    page = admin_client.post("/admin/inventory/material/export/", {"format": "1"})
    assert page.status_code == 200


# setup checklist and lab settings


def test_admin_home_shows_the_setup_checklist(admin_client):
    html = admin_client.get("/admin/").content.decode()
    assert "Getting started" in html and "How people sign in" in html


def test_lab_settings_is_a_single_page(admin_client):
    response = admin_client.get("/admin/kiosk/labsettings/")
    assert response.status_code == 302 and response.url.endswith("/1/change/")
    assert admin_client.get("/admin/kiosk/labsettings/add/").status_code == 403


# sign-in modes


@pytest.fixture
def phone_user(client, employee):
    user = get_user_model().objects.create_user("aisha", password="pw-123456")
    employee.user = user
    employee.save()
    return user


@pytest.fixture
def registered_tablet(client, db):
    owner = get_user_model().objects.create_user("owner", password="x", is_staff=True)
    device = Device(name="Store room")
    token = device.new_link_token(owner)
    device.save()
    return client, token


def set_mode(mode):
    lab = LabSettings.load()
    lab.sign_in = mode
    lab.save()


def test_shared_only_turns_phone_logins_off(client, phone_user):
    set_mode("shared")
    assert client.get("/accounts/login/").status_code == 403
    client.force_login(phone_user)  # already signed in before the switch
    page = client.get("/k/home/")
    assert page.status_code == 403 and b"store-room tablet" in page.content


def test_personal_only_turns_the_tablet_off(registered_tablet, employee):
    client, token = registered_tablet
    set_mode("personal")
    assert client.post(f"/k/register/{token}/").status_code == 403
    assert client.get(f"/k/pin/{employee.pk}/").status_code == 403
    assert client.get("/k/").url == "/accounts/login/"


def test_both_modes_by_default(client, phone_user):
    assert LabSettings.load().sign_in == "both"
    assert client.login(username="aisha", password="pw-123456")
    assert client.get("/k/home/").status_code == 200


def test_issue_with_key_still_idempotent_after_changes(material, employee):
    services.receive(material, 5)
    key = uuid.uuid4()
    assert (
        services.issue(material, 1, employee, key=key).pk
        == services.issue(material, 1, employee, key=key).pk
    )
    assert StockMove.objects.filter(kind="issue").count() == 1


def test_import_preview_creates_nothing(db):
    # Employee rows can name new departments; previewing must not create them. django-import-export
    # always rolls a dry run back; this guards against that changing in a future version.
    rows = tablib.Dataset(
        ["Ravi Kumar", "Implants", True], headers=["name", "department", "active"]
    )
    EmployeeResource().import_data(rows, dry_run=True)
    assert not Department.objects.filter(name="Implants").exists()
    assert not Employee.objects.filter(name="Ravi Kumar").exists()
