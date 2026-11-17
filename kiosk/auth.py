"""Who is using the kiosk: a PIN on a registered tablet, or a personal login (ADR 0009).

Public contract for the kiosk screens:
- @employee_required sets request.employee and request.kiosk_mode ("shared" or "personal").
- end_kiosk_session(request) signs the employee out.
"""

from datetime import timedelta
from functools import wraps

from django.contrib.auth import logout
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from inventory.models import Employee

from .models import Device, LabSettings, hash_token

DEVICE_COOKIE = "kiosk_device"
DEVICE_COOKIE_SALT = "kiosk.device"
DEVICE_COOKIE_AGE = 400 * 24 * 3600  # browsers cap cookie lifetime at 400 days
SESSION_KEY = "kiosk_employee_id"
SHARED_IDLE_SECONDS = 5 * 60
MAX_PIN_ATTEMPTS = 5
LOCK_TIME = timedelta(minutes=15)


def set_device_cookie(response, request, token):
    response.set_signed_cookie(
        DEVICE_COOKIE,
        token,
        salt=DEVICE_COOKIE_SALT,
        max_age=DEVICE_COOKIE_AGE,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure(),
    )


def current_device(request):
    """The registered, active Device this browser belongs to, or None."""
    token = request.get_signed_cookie(DEVICE_COOKIE, default=None, salt=DEVICE_COOKIE_SALT)
    if not token:
        return None
    return Device.objects.filter(
        token_hash=hash_token(token), active=True, registered_at__isnull=False
    ).first()


def verify_pin(employee_id, pin):
    """Returns "ok", "wrong" or "locked". Attempts for one employee are serialised by a row lock,
    so parallel guesses can't all slip in before the lock is set."""
    with transaction.atomic():
        emp = Employee.objects.select_for_update().get(pk=employee_id, active=True)
        now = timezone.now()
        if emp.pin_locked_until and emp.pin_locked_until > now:
            return "locked"
        if emp.pin_hash and check_password(pin, emp.pin_hash):
            emp.failed_pin_attempts, emp.pin_locked_until = 0, None
            emp.save(update_fields=["failed_pin_attempts", "pin_locked_until"])
            return "ok"
        emp.failed_pin_attempts += 1
        if emp.failed_pin_attempts >= MAX_PIN_ATTEMPTS:
            emp.failed_pin_attempts, emp.pin_locked_until = 0, now + LOCK_TIME
        emp.save(update_fields=["failed_pin_attempts", "pin_locked_until"])
        return "wrong"


def start_shared_session(request, employee):
    request.session.cycle_key()  # new session id after sign-in (session fixation)
    request.session[SESSION_KEY] = employee.pk
    request.session.set_expiry(SHARED_IDLE_SECONDS)


def not_available(request, message):
    """The lab's sign-in setting (Admin, Lab settings) switched this way of signing in off."""
    return render(request, "kiosk/not_available.html", {"message": message}, status=403)


USE_TABLET = "This lab signs in at the store-room tablet. Please use the tablet."
USE_PHONE = "This lab doesn't use a shared tablet. Sign in on your own phone."


def _resolve(request, lab):
    employee_id = request.session.get(SESSION_KEY)
    if lab.shared_allowed and employee_id and current_device(request):
        emp = Employee.objects.filter(pk=employee_id, active=True).first()
        if emp:
            return emp, "shared"
    if lab.personal_allowed and request.user.is_authenticated:
        emp = Employee.objects.filter(user=request.user, active=True).first()
        if emp:
            return emp, "personal"
    return None, None


def employee_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        lab = LabSettings.load()
        request.employee, request.kiosk_mode = _resolve(request, lab)
        if request.employee is None:
            if request.user.is_authenticated and current_device(request) is None:
                if not lab.personal_allowed:
                    return not_available(request, USE_TABLET)
                # Signed in (e.g. as an admin) but not an employee: kiosk:start would send
                # them straight back here, an endless redirect loop.
                return render(request, "kiosk/not_linked.html", status=403)
            return redirect("kiosk:start")
        return view(request, *args, **kwargs)

    return wrapper


def end_kiosk_session(request):
    if request.session.get(SESSION_KEY):
        request.session.flush()  # device cookie is separate, so the tablet stays registered
    else:
        logout(request)
