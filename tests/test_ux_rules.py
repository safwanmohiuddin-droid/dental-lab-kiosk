"""Checks for docs/ux-rules.md: the behaviour each rule promises, not the styling."""

import uuid

from django.contrib.auth import get_user_model

from inventory import services
from inventory.models import Department, Employee, Material, StockMove
from kiosk.models import Device

PIN = "2468"


def tablet_with(client, *people):
    owner = get_user_model().objects.create_user("owner-x", password="x", is_staff=True)
    device = Device(name="Store room")
    token = device.new_link_token(owner)
    device.save()
    client.post(f"/k/register/{token}/")
    for person in people:
        person.set_pin(PIN)
        person.save()
    return client


# R8: finding your name


def test_start_screen_has_search_and_recent_people_first(client, employee, department):
    other = Employee.objects.create(name="Zed Last", department=department)
    tablet_with(client, employee, other)
    material = Material.objects.create(name="Disc", barcode="D-1")
    services.receive(material, 5)
    services.issue(material, 1, other)  # Zed took something most recently
    html = client.get("/k/").content.decode()
    assert "data-filter" in html and "Find your name" in html
    recent = html.index("Recent")
    assert html.index("Zed Last", recent) < html.index("Everyone")


# R11, Jakob's law: PIN pad like a phone lock screen


def test_pin_screen_has_an_on_screen_pad(client, employee):
    tablet_with(client, employee)
    html = client.get(f"/k/pin/{employee.pk}/").content.decode()
    assert html.count("data-digit=") == 10 and 'inputmode="none"' in html


# R6, R7: usual items one tap away


def test_home_lists_your_usual_items(client, employee):
    user = get_user_model().objects.create_user("aisha", password="pw-123456")
    employee.user = user
    employee.save()
    client.force_login(user)
    material = Material.objects.create(name="Disc", barcode="D-1", unit="disc")
    services.receive(material, 5)
    services.issue(material, 2, employee)
    html = client.get("/k/home/").content.decode()
    assert "Your usual" in html and "?barcode=D-1&amp;qty=2" in html


# R2, R12: reports in plain words, with a headline; R8: controls are a sentence, not buttons


def test_reports_use_plain_words_and_a_headline(admin_client, employee):
    material = Material.objects.create(name="Disc", barcode="D-1")
    services.receive(material, 5)
    services.issue(material, 2, employee)
    html = admin_client.get(
        "/r/", {"by": "department", "every": "", "period": "this_month"}
    ).content.decode()
    assert f"<strong>{employee.department.name}</strong> leads." in html
    for word in ("Units used", "Times taken", "Have a price", "Show", "by", "per", "for"):
        assert word in html
    for jargon in ("Net qty", "Priced<", ">Issues<"):
        assert jargon not in html


# R2, R8: admin home puts developer sections last, in plain words


def test_admin_home_puts_advanced_sections_last(admin_client):
    html = admin_client.get("/admin/").content.decode()
    assert "Advanced: logins and groups" in html and "Advanced: two-factor apps" in html
    assert html.index("Stock and people") < html.index("Advanced: logins and groups")
    assert "OTP_TOTP" not in html and "Authentication and Authorization" not in html


# R6, R11: actions are visible buttons, and work the way the browser sends them


def test_admin_actions_are_buttons(admin_client, department):  # actions show only with rows
    html = admin_client.get("/admin/inventory/department/").content.decode()
    assert 'name="action" value="delete_or_archive"' in html
    assert 'select name="action"' not in html


def test_admin_action_button_post_works(admin_client, db):
    unused = Department.objects.create(name="Unused")
    admin_client.post(
        "/admin/inventory/department/",
        {"action": "delete_or_archive", "index": "0", "_selected_action": [unused.pk]},
    )
    assert not Department.objects.filter(pk=unused.pk).exists()


# R1: idempotent take survives a "Saving..." double press even on the unusual path


def test_unusual_confirm_reuses_the_first_key(client, employee):
    user = get_user_model().objects.create_user("aisha", password="pw-123456")
    employee.user = user
    employee.save()
    client.force_login(user)
    material = Material.objects.create(name="Disc", barcode="D-1", unit="disc")
    services.receive(material, 100)
    for _ in range(3):
        services.issue(material, 1, employee)
    key = str(uuid.uuid4())
    html = client.post(
        "/k/issue/", {"material": material.pk, "qty": "20", "case_ref": "", "key": key}
    ).content.decode()
    assert f'name="key" value="{key}"' in html
    assert StockMove.objects.filter(kind="issue", qty=-20).count() == 0
