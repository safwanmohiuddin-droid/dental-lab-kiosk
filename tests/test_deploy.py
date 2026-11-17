import json
import logging
import os
import secrets
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command
from django.db import DatabaseError
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from ops.logging import JsonFormatter

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "test-only-password-91"


# health check


def test_healthz_ok(client, db):
    response = client.get("/healthz")
    assert response.status_code == 200 and response.json() == {"status": "ok", "database": "ok"}


def test_healthz_reports_database_down(client, monkeypatch):
    class DeadConnection:
        def cursor(self):
            raise DatabaseError("connection refused")

    monkeypatch.setattr("ops.views.connection", DeadConnection())
    response = client.get("/healthz")
    assert response.status_code == 503 and response.json()["database"] == "unavailable"


def test_https_redirect_spares_only_healthz(client, db, settings):
    settings.SECURE_SSL_REDIRECT = True
    assert client.get("/healthz").status_code == 200
    assert client.get("/admin/login/").status_code == 301


# production settings


def _check_deploy(**extra):
    env = {
        **os.environ,
        "DEBUG": "False",
        "SECRET_KEY": secrets.token_urlsafe(50),
        "ALLOWED_HOSTS": "kiosk.example.com",
        "CSRF_TRUSTED_ORIGINS": "https://kiosk.example.com",
        **extra,
    }
    return subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_check_deploy_is_clean_with_production_env():
    result = _check_deploy()
    assert result.returncode == 0, result.stdout + result.stderr


def test_check_deploy_flags_admin_without_2fa():
    result = _check_deploy(ADMIN_REQUIRE_2FA="False")
    assert result.returncode != 0 and "ops.W001" in result.stdout + result.stderr


def test_logs_are_one_json_object_per_line():
    try:
        raise ValueError("boom")
    except ValueError:
        info = sys.exc_info()
    record = logging.LogRecord("kiosk", logging.ERROR, __file__, 1, "x=%s", (5,), info)
    line = json.loads(JsonFormatter().format(record))
    assert (line["level"], line["message"], line["logger"]) == ("ERROR", "x=5", "kiosk")
    assert "ValueError: boom" in line["exception"]


# admin 2FA (ADR 0026)


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user(
        "boss", password=PASSWORD, is_staff=True, is_superuser=True
    )


@pytest.fixture
def two_factor(settings):
    settings.ADMIN_REQUIRE_2FA = True


def _code(device):
    return TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift).token()


def test_password_alone_does_not_open_admin(client, staff, two_factor):
    client.force_login(staff)
    assert client.get("/admin/").status_code == 302


def test_login_with_authenticator_code_opens_admin(client, staff, two_factor):
    device = TOTPDevice.objects.create(user=staff, name="phone", confirmed=True)
    page = client.get("/admin/login/")
    assert b'name="otp_token"' in page.content
    client.post(
        "/admin/login/?next=/admin/",
        {"username": "boss", "password": PASSWORD, "otp_token": f"{_code(device):06d}"},
    )
    assert client.get("/admin/").status_code == 200


def test_two_devices_still_require_choosing_one(client, staff, two_factor):
    device = TOTPDevice.objects.create(user=staff, name="phone", confirmed=True)
    TOTPDevice.objects.create(user=staff, name="tablet", confirmed=True)
    page = client.post(
        "/admin/login/", {"username": "boss", "password": PASSWORD, "otp_token": _code(device)}
    )
    assert b"Please select a device" in page.content
    assert client.get("/admin/").status_code == 302


def test_wrong_code_is_refused(client, staff, two_factor):
    TOTPDevice.objects.create(user=staff, name="phone", confirmed=True)
    client.post("/admin/login/", {"username": "boss", "password": PASSWORD, "otp_token": "000000"})
    assert client.get("/admin/").status_code == 302


def test_without_2fa_the_normal_login_is_used(client, db):
    assert b'name="otp_token"' not in client.get("/admin/login/").content


def test_totp_setup_command(staff):
    out = StringIO()
    call_command("totp_setup", "boss", stdout=out)
    assert TOTPDevice.objects.filter(user=staff, confirmed=True).count() == 1
    assert "Or add this key by hand" in out.getvalue()
    with pytest.raises(CommandError):
        call_command("totp_setup", "boss", stdout=StringIO())
    call_command("totp_setup", "boss", "--replace", stdout=StringIO())
    assert TOTPDevice.objects.filter(user=staff).count() == 1
