import uuid
from datetime import timedelta
from decimal import Decimal as D

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from inventory import services
from inventory.models import Material, StockMove
from kiosk.models import Device

PIN = "4826"


@pytest.fixture
def stocked(material):
    services.receive(material, 10, D("80"))
    material.refresh_from_db()
    return material


@pytest.fixture
def tablet(client, employee):
    """A registered shared tablet with the employee signed in by PIN."""
    owner = get_user_model().objects.create_user("owner", password="x", is_staff=True)
    device = Device(name="Store room")
    token = device.new_link_token(owner)
    device.save()
    assert client.post(f"/k/register/{token}/").status_code == 302
    employee.set_pin(PIN)
    employee.save()
    assert client.post(f"/k/pin/{employee.pk}/", {"pin": PIN}).url == "/k/home/"
    return client


@pytest.fixture
def phone(client, employee):
    """A personal phone: the employee signed in with their own user account."""
    user = get_user_model().objects.create_user("aisha", password="pw-123456")
    employee.user = user
    employee.save()
    client.force_login(user)
    return client


def take(client, material, qty, key=None, case_ref="", follow=False):
    data = {"material": material.pk, "qty": qty, "case_ref": case_ref, "key": key or uuid.uuid4()}
    return client.post("/k/issue/", data, follow=follow)


def final_url(response):
    return response.redirect_chain[-1][0] if response.redirect_chain else None


# looking up a barcode


def test_barcode_lookup_shows_material_and_stock(phone, stocked):
    page = phone.get("/k/home/", {"barcode": stocked.barcode}).content.decode()
    assert stocked.name in page and "10 disc" in page and 'name="qty"' in page


def test_unknown_barcode_is_explained(phone, db):
    page = phone.get("/k/home/", {"barcode": "NOPE"}).content.decode()
    assert "No material with barcode NOPE." in page


def test_archived_material_is_refused_at_lookup(phone, stocked):
    stocked.active = False
    stocked.save()
    assert "is archived" in phone.get("/k/home/", {"barcode": stocked.barcode}).content.decode()


def test_barcode_form_cannot_take_stock(phone, stocked):
    # The barcode field is its own GET form, so a scanner's Enter only looks up.
    page = phone.get("/k/home/").content.decode()
    form_start = page.index('<form method="get" action="/k/home/">')
    assert page.index("</form>", form_start) > page.index('id="barcode"')
    assert not StockMove.objects.filter(kind="issue").exists()


# confirm and issue


def test_confirm_shows_summary_and_changes_nothing(phone, stocked):
    page = phone.get("/k/confirm/", {"material": stocked.pk, "qty": "3", "case_ref": "C-9"})
    html = page.content.decode()
    assert "Take 3 disc" in html and "C-9" in html and "data-client-key" in html
    stocked.refresh_from_db()
    assert stocked.qty_on_hand == 10


def test_confirm_refuses_more_than_in_stock(phone, stocked):
    html = phone.get("/k/confirm/", {"material": stocked.pk, "qty": "11"}).content.decode()
    assert "Only 10 disc in stock." in html


@pytest.mark.parametrize("qty", ["0", "-1", "abc", "1.2345"])
def test_confirm_rejects_bad_quantities(phone, stocked, qty):
    html = phone.get("/k/confirm/", {"material": stocked.pk, "qty": qty}).content.decode()
    assert "Confirm" not in html.split("<main>")[1].split("</h1>")[0]


def test_personal_issue_flow(phone, stocked, employee):
    response = take(phone, stocked, "4", case_ref="C-1001", follow=True)
    assert response.redirect_chain == [("/k/done/", 302)]
    done = response.content.decode()
    assert "Taken" in done and "4 disc" in done and "Take something else" in done
    move = StockMove.objects.get(kind="issue")
    assert (move.qty, move.employee, move.department, move.case_ref) == (
        -4,
        employee,
        employee.department,
        "C-1001",
    )
    assert move.created_by == employee.user
    # still signed in on a personal phone
    assert phone.get("/k/home/").status_code == 200


def test_double_submit_records_one_issue(phone, stocked):
    key = uuid.uuid4()
    take(phone, stocked, "2", key=key)
    take(phone, stocked, "2", key=key)  # double tap or browser resend
    stocked.refresh_from_db()
    assert StockMove.objects.filter(kind="issue").count() == 1 and stocked.qty_on_hand == 8


def test_insufficient_stock_at_issue_time(phone, stocked):
    html = take(phone, stocked, "11").content.decode()
    assert "Only 10 disc" in html
    assert not StockMove.objects.filter(kind="issue").exists()


def test_material_archived_between_confirm_and_issue(phone, stocked):
    stocked.active = False
    stocked.save()
    html = take(phone, stocked, "1").content.decode()
    assert "archived" in html and not StockMove.objects.filter(kind="issue").exists()


def test_shared_tablet_signs_out_after_issue(tablet, stocked):
    done = take(tablet, stocked, "1", follow=True)
    assert final_url(done) == "/k/done/"
    assert "Signed out" in done.content.decode() and "Next person" in done.content.decode()
    # The next person must sign in, and the tablet itself stays registered.
    after = tablet.get("/k/home/", follow=True)
    assert final_url(after) == "/k/" and "Who are you?" in after.content.decode()


def test_shared_double_submit_after_sign_out_records_nothing_more(tablet, stocked):
    key = uuid.uuid4()
    take(tablet, stocked, "1", key=key)
    second = take(tablet, stocked, "1", key=key, follow=True)
    assert final_url(second) == "/k/" and "Who are you?" in second.content.decode()
    assert StockMove.objects.filter(kind="issue").count() == 1


def test_done_page_shows_once(phone, stocked):
    take(phone, stocked, "1", follow=True)
    again = phone.get("/k/done/", follow=True)  # personal user: /k/ forwards to home
    assert [url for url, _ in again.redirect_chain] == ["/k/", "/k/home/"]
    assert "Take material" in again.content.decode()


# repeat last issue


def test_recent_materials_prefill_the_last_quantity(phone, stocked, employee):
    other = Material.objects.create(name="Bur", barcode="BUR-1", unit="pcs")
    services.receive(other, 20)
    for material, qty in [(stocked, 2), (other, 5), (stocked, 3)]:
        services.issue(material, qty, employee)
    html = phone.get("/k/home/").content.decode()
    assert html.count('class="chip"') == 2
    assert f"?barcode={stocked.barcode}&amp;qty=3" in html
    prefilled = phone.get("/k/home/", {"barcode": stocked.barcode, "qty": "3"}).content.decode()
    assert 'value="3"' in prefilled


# returns


def test_return_flow(phone, stocked, employee):
    taken = services.issue(stocked, 4, employee)
    html = phone.get("/k/returns/").content.decode()
    assert stocked.name in html and "Can return" in html
    response = phone.post(f"/k/returns/{taken.pk}/", {"qty": "1", "key": uuid.uuid4()}, follow=True)
    assert final_url(response) == "/k/done/" and "Returned" in response.content.decode()
    back = StockMove.objects.get(kind="return")
    assert (back.qty, back.unit_cost, back.returns_move) == (1, 80, taken)


def test_over_return_is_refused(phone, stocked, employee):
    taken = services.issue(stocked, 2, employee)
    html = phone.post(f"/k/returns/{taken.pk}/", {"qty": "3", "key": uuid.uuid4()})
    assert "left to return" in html.content.decode()
    assert not StockMove.objects.filter(kind="return").exists()


def test_fully_returned_and_old_issues_are_not_listed(phone, stocked, employee):
    done = services.issue(stocked, 1, employee)
    services.return_(done, 1)
    old = services.issue(stocked, 1, employee)
    StockMove.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=15))
    assert "Nothing to return" in phone.get("/k/returns/").content.decode()


def test_cannot_return_someone_elses_issue(phone, stocked, employee, department):
    from inventory.models import Employee

    other = Employee.objects.create(name="Tom", department=department)
    theirs = services.issue(stocked, 2, other)
    response = phone.post(f"/k/returns/{theirs.pk}/", {"qty": "1", "key": uuid.uuid4()})
    assert response.status_code == 404


# access


@pytest.mark.parametrize("url", ["/k/home/", "/k/confirm/", "/k/returns/"])
def test_unidentified_visitors_end_on_the_sign_in_page(client, db, url):
    response = client.get(url, follow=True)
    assert [u for u, _ in response.redirect_chain] == ["/k/", "/accounts/login/"]
    assert response.status_code == 200


@pytest.mark.parametrize("url", ["/k/home/", "/k/confirm/", "/k/returns/"])
def test_signed_in_non_employee_gets_a_clear_403_not_a_loop(admin_client, url):
    response = admin_client.get(url, follow=True)
    assert response.status_code == 403 and response.redirect_chain == []


def test_issue_needs_post(phone):
    assert phone.get("/k/issue/").status_code == 405


def test_scan_button_points_at_scanner_module_and_starts_hidden(phone):
    html = phone.get("/k/home/").content.decode()
    assert 'data-scanner-url="/static/scanner/scanner.js"' in html and "hidden" in html


def test_kiosk_assets_are_served(client):
    for path in ["kiosk/kiosk.js", "kiosk/kiosk.css", "kiosk/vendor/htmx-2.0.11.min.js"]:
        from django.contrib.staticfiles import finders

        assert finders.find(path), path


def test_no_template_comment_leaks_into_the_page(client):
    # A two-line {# #} comment once printed raw at the top of every kiosk page.
    html = client.get("/accounts/login/").content.decode()
    assert "{#" not in html and "#}" not in html and "{%" not in html


def test_htmx_times_out_so_bad_wifi_shows_a_message(client):
    html = client.get("/accounts/login/").content.decode()
    assert '"timeout":15000' in html
