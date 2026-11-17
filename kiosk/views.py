from datetime import timedelta

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from inventory.models import Department, Employee

from . import auth
from .models import Device, hash_token


def start(request):
    """Shared tablet: pick your name. Anyone else: personal sign-in."""
    if auth.current_device(request) is None:
        return redirect("kiosk:home") if request.user.is_authenticated else redirect("login")
    departments = (
        Department.objects.filter(active=True, employees__active=True)
        .distinct()
        .prefetch_related("employees")
    )
    groups = [(d, [e for e in d.employees.all() if e.active and e.pin_hash]) for d in departments]
    return render(request, "kiosk/start.html", {"groups": [g for g in groups if g[1]]})


def pin(request, employee_id):
    device = auth.current_device(request)
    if device is None:
        return render(request, "kiosk/device_required.html", status=403)
    employee = get_object_or_404(Employee, pk=employee_id, active=True)
    error = None
    if request.method == "POST":
        result = auth.verify_pin(employee.pk, request.POST.get("pin", ""))
        if result == "ok":
            auth.start_shared_session(request, employee)
            Device.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
            return redirect("kiosk:home")
        employee.refresh_from_db()
        error = result
    until = employee.pin_locked_until
    locked_until = until if until and until > timezone.now() else None
    context = {"employee": employee, "error": error, "locked_until": locked_until}
    return render(request, "kiosk/pin.html", context, status=403 if locked_until else 200)


@auth.employee_required
def home(request):
    # Placeholder until the kiosk screens (Phase 5) replace it.
    return render(request, "kiosk/home.html")


@require_POST
def sign_out(request):
    auth.end_kiosk_session(request)
    return redirect("kiosk:start")


def register(request, token):
    """GET only asks; POST consumes. Chat apps open links to build previews, which must not
    use up the one-time link."""
    device = Device.objects.filter(
        token_hash=hash_token(token),
        active=True,
        registered_at__isnull=True,
        link_expires_at__gt=timezone.now(),
    ).first()
    if device is None:
        return render(request, "kiosk/register.html", {"invalid": True}, status=404)
    if request.method != "POST":
        return render(request, "kiosk/register.html", {"device": device})
    with transaction.atomic():
        claimed = Device.objects.filter(pk=device.pk, registered_at__isnull=True).update(
            registered_at=timezone.now(), link_expires_at=None
        )
    if not claimed:  # two browsers opened the same link at once; only the first wins
        return render(request, "kiosk/register.html", {"invalid": True}, status=404)
    response = redirect("kiosk:start")
    auth.set_device_cookie(response, request, token)
    return response


class PersonalLoginForm(AuthenticationForm):
    remember = forms.BooleanField(label="Keep me signed in for 30 days", required=False)


class PersonalLoginView(LoginView):
    form_class = PersonalLoginForm
    template_name = "kiosk/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        remember = form.cleaned_data["remember"]
        self.request.session.set_expiry(timedelta(days=30) if remember else 0)
        return response
