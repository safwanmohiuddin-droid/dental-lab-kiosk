import threading
import time
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from inventory.models import Employee
from kiosk import auth
from kiosk.models import Device

PIN = "4826"


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user("owner", password="x", is_staff=True)


@pytest.fixture
def with_pin(employee):
    employee.set_pin(PIN)
    employee.save()
    return employee


def make_device(staff, **fields):
    device = Device(name="Store room tablet", **fields)
    token = device.new_link_token(staff)
    device.save()
    return device, token


@pytest.fixture
def tablet(client, staff):
    """A test client that is a registered shared tablet."""
    device, token = make_device(staff)
    assert client.post(f"/k/register/{token}/").status_code == 302
    client.device = device
    return client


# PIN rules


@pytest.mark.parametrize("pin", ["123", "1234567", "12a4", "", "١٢٣٤"])
def test_pin_must_be_4_to_6_ascii_digits(employee, pin):
    with pytest.raises(ValueError):
        employee.set_pin(pin)


def test_pin_is_hashed_with_argon2(with_pin):
    assert with_pin.pin_hash.startswith("argon2") and PIN not in with_pin.pin_hash


# device registration


def test_opening_the_link_does_not_use_it_up(client, staff):
    # Chat apps fetch links to build previews; a GET must not register anything.
    device, token = make_device(staff)
    assert client.get(f"/k/register/{token}/").status_code == 200
    device.refresh_from_db()
    assert device.registered_at is None


def test_link_works_once(client, staff):
    _, token = make_device(staff)
    assert client.post(f"/k/register/{token}/").status_code == 302
    assert "kiosk_device" in client.cookies
    assert client.post(f"/k/register/{token}/").status_code == 404


@pytest.mark.parametrize(
    "fields",
    [{"active": False}],
    ids=["inactive-device"],
)
def test_link_refused_for_inactive_device(client, staff, fields):
    _, token = make_device(staff, **fields)
    assert client.post(f"/k/register/{token}/").status_code == 404


def test_expired_link_is_refused(client, staff):
    device, token = make_device(staff)
    Device.objects.filter(pk=device.pk).update(link_expires_at=timezone.now() - timedelta(1))
    assert client.post(f"/k/register/{token}/").status_code == 404


def test_new_link_signs_the_old_tablet_out(tablet, staff, with_pin):
    tablet.device.new_link_token(staff)
    tablet.device.save()
    assert tablet.get(f"/k/pin/{with_pin.pk}/").status_code == 403


def test_forged_device_cookie_is_ignored(client, with_pin):
    client.cookies["kiosk_device"] = "made-up"
    assert client.get(f"/k/pin/{with_pin.pk}/").status_code == 403


# PIN sign-in on a shared tablet


def test_pin_page_refuses_unregistered_devices(client, with_pin):
    assert client.get(f"/k/pin/{with_pin.pk}/").status_code == 403
    response = client.post(f"/k/pin/{with_pin.pk}/", {"pin": PIN})
    assert response.status_code == 403 and "kiosk_employee_id" not in client.session


def test_tablet_lists_employees_with_a_pin(tablet, with_pin, department):
    Employee.objects.create(name="No Pin Yet", department=department)
    page = tablet.get("/k/").content.decode()
    assert with_pin.name in page and "No Pin Yet" not in page


def test_correct_pin_signs_in_with_a_new_session_id(tablet, with_pin):
    tablet.get("/k/")
    before = tablet.session.session_key
    response = tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": PIN})
    assert response.url == "/k/home/"
    assert tablet.session.session_key != before  # no session fixation
    assert with_pin.name in tablet.get("/k/home/").content.decode()


def test_five_wrong_pins_lock_the_employee(tablet, with_pin):
    for _ in range(4):
        assert tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": "0000"}).status_code == 200
    assert tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": "0000"}).status_code == 403
    # Even the right PIN is refused while locked.
    assert tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": PIN}).status_code == 403
    with_pin.refresh_from_db()
    assert with_pin.pin_locked_until > timezone.now()


def test_lock_expires(tablet, with_pin):
    Employee.objects.filter(pk=with_pin.pk).update(
        pin_locked_until=timezone.now() - timedelta(seconds=1)
    )
    assert tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": PIN}).url == "/k/home/"


def test_right_pin_resets_the_counter(tablet, with_pin):
    tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": "0000"})
    tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": PIN})
    with_pin.refresh_from_db()
    assert with_pin.failed_pin_attempts == 0


@pytest.mark.django_db(transaction=True)
def test_parallel_wrong_guesses_cannot_exceed_the_limit(with_pin, monkeypatch):
    # Without a row lock, guesses running at the same moment all read the old counter and
    # all get checked, so an attacker gets more than 5 tries.
    def slow_wrong(pin, encoded):
        time.sleep(0.05)
        return False

    monkeypatch.setattr(auth, "check_password", slow_wrong)
    start, results = threading.Barrier(8), []

    def guess():
        try:
            start.wait()
            results.append(auth.verify_pin(with_pin.pk, "0000"))
        finally:
            connection.close()

    threads = [threading.Thread(target=guess) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("wrong") == auth.MAX_PIN_ATTEMPTS
    assert results.count("locked") == 8 - auth.MAX_PIN_ATTEMPTS


def test_sign_out_keeps_the_tablet_registered(tablet, with_pin):
    tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": PIN})
    tablet.post("/k/sign-out/")
    assert tablet.get("/k/home/").url == "/k/"
    assert with_pin.name in tablet.get("/k/").content.decode()


def test_shared_session_is_short(tablet, with_pin):
    tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": PIN})
    assert tablet.session.get_expiry_age() == auth.SHARED_IDLE_SECONDS


def test_deactivated_tablet_ends_open_sessions(tablet, with_pin):
    tablet.post(f"/k/pin/{with_pin.pk}/", {"pin": PIN})
    Device.objects.filter(pk=tablet.device.pk).update(active=False)
    assert tablet.get("/k/home/").url == "/k/"


# personal phone


@pytest.fixture
def phone_user(employee):
    user = get_user_model().objects.create_user("aisha", password="long-enough-pass")
    employee.user = user
    employee.save()
    return user


def test_personal_login_reaches_home(client, phone_user, employee):
    response = client.post(
        "/accounts/login/", {"username": "aisha", "password": "long-enough-pass", "remember": "on"}
    )
    assert response.url == "/k/home/"
    page = client.get("/k/home/")
    assert page.wsgi_request.kiosk_mode == "personal"
    assert page.wsgi_request.employee == employee
    # timedelta expiry is stored as an absolute time, so a second may already have passed
    assert 30 * 24 * 3600 - 60 < client.session.get_expiry_age() <= 30 * 24 * 3600


def test_without_remember_me_session_ends_with_browser(client, phone_user):
    client.post("/accounts/login/", {"username": "aisha", "password": "long-enough-pass"})
    assert client.session.get_expire_at_browser_close()


def test_user_without_employee_cannot_use_kiosk(client, staff):
    client.force_login(staff)
    assert client.get("/k/home/").url == "/k/"


def test_anonymous_phone_is_sent_to_login(client):
    assert client.get("/k/").url == "/accounts/login/"


def test_personal_sign_out_logs_out(client, phone_user):
    client.force_login(phone_user)
    client.post("/k/sign-out/")
    assert "_auth_user_id" not in client.session


# admin


def test_admin_creates_device_and_shows_link_once(admin_client):
    response = admin_client.post(
        "/admin/kiosk/device/add/", {"name": "Tablet 1", "active": "on"}, follow=True
    )
    assert "/k/register/" in response.content.decode()
    device = Device.objects.get()
    assert device.registered_at is None and len(device.token_hash) == 64


def test_admin_sets_pin(admin_client, employee):
    admin_client.post(
        f"/admin/inventory/employee/{employee.pk}/change/",
        {
            "name": employee.name,
            "department": employee.department_id,
            "active": "on",
            "new_pin": "135790",
        },
    )
    employee.refresh_from_db()
    assert employee.pin_hash.startswith("argon2")


def test_admin_rejects_bad_pin(admin_client, employee):
    response = admin_client.post(
        f"/admin/inventory/employee/{employee.pk}/change/",
        {"name": employee.name, "department": employee.department_id, "new_pin": "12"},
    )
    assert response.status_code == 200 and "4 to 6 digits" in response.content.decode()


def test_admin_unlocks(admin_client, with_pin):
    Employee.objects.filter(pk=with_pin.pk).update(
        failed_pin_attempts=3, pin_locked_until=timezone.now() + timedelta(minutes=10)
    )
    admin_client.post(
        "/admin/inventory/employee/",
        {"action": "unlock_pin", "_selected_action": [with_pin.pk]},
    )
    with_pin.refresh_from_db()
    assert with_pin.pin_locked_until is None and with_pin.failed_pin_attempts == 0
