import uuid
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from inventory import services
from inventory.models import Department, Employee, Material, StockMove

from . import auth
from .models import Device, LabSettings, hash_token

RETURN_WINDOW = timedelta(days=14)


def start(request):
    """Shared tablet: pick your name. Anyone else: personal sign-in (per Lab settings)."""
    lab = LabSettings.load()
    if auth.current_device(request) is None or not lab.shared_allowed:
        if not lab.personal_allowed:
            return auth.not_available(request, auth.USE_TABLET)
        return redirect("kiosk:home") if request.user.is_authenticated else redirect("login")
    departments = (
        Department.objects.filter(active=True, employees__active=True)
        .distinct()
        .prefetch_related("employees")
    )
    groups = [(d, [e for e in d.employees.all() if e.active and e.pin_hash]) for d in departments]
    return render(request, "kiosk/start.html", {"groups": [g for g in groups if g[1]]})


def pin(request, employee_id):
    if not LabSettings.load().shared_allowed:
        return auth.not_available(request, auth.USE_PHONE)
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


class IssueForm(forms.Form):
    material = forms.ModelChoiceField(
        queryset=Material.objects.filter(active=True),
        widget=forms.HiddenInput,
        error_messages={"invalid_choice": "This material is archived or no longer exists."},
    )
    qty = forms.DecimalField(
        label="Quantity", max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )
    case_ref = forms.CharField(label="Case number (optional)", max_length=50, required=False)


class ConfirmIssueForm(IssueForm):
    key = forms.UUIDField(widget=forms.HiddenInput)


class ReturnForm(forms.Form):
    qty = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    key = forms.UUIDField(widget=forms.HiddenInput)


def _recent_materials(employee):
    """Last 5 distinct active materials this employee took, with the last quantity."""
    # shortcut: scans the last 50 issues in Python; fine at kiosk volumes.
    seen, recent = set(), []
    moves = StockMove.objects.filter(employee=employee, kind=StockMove.Kind.ISSUE)
    for move in moves.select_related("material").order_by("-created_at")[:50]:
        if move.material_id not in seen and move.material.active:
            seen.add(move.material_id)
            recent.append({"material": move.material, "qty": -move.qty})
        if len(recent) == 5:
            break
    return recent


def _returnable(employee):
    """This employee's issues from the last 14 days that still have something to return."""
    returned = Coalesce(Sum("returns__qty"), Value(0), output_field=DecimalField())
    return (
        StockMove.objects.filter(
            employee=employee,
            kind=StockMove.Kind.ISSUE,
            created_at__gte=timezone.now() - RETURN_WINDOW,
        )
        .annotate(left=-F("qty") - returned)
        .filter(left__gt=0)
        .select_related("material")
        .order_by("-created_at")
    )


def _home(request, *, barcode="", material=None, form=None, error=None):
    context = {
        "barcode": barcode,
        "material": material,
        "form": form,
        "error": error,
        "recent": _recent_materials(request.employee),
    }
    return render(request, "kiosk/home.html", context)


def _home_for(request, material_id, form, error=None):
    """Re-show the quantity step for a material after a validation or stock error."""
    material = Material.objects.filter(pk=material_id).first()
    barcode = material.barcode if material else ""
    return _home(request, barcode=barcode, material=material, form=form, error=error)


def _finish(request, kind, move):
    """Remember what was done for the done screen; a shared tablet signs the employee out."""
    summary = {
        "kind": kind,
        "material": move.material.name,
        "qty": services.plain(abs(move.qty)),
        "unit": move.material.unit,
        "department": move.department.name,
        "shared": request.kiosk_mode == "shared",
    }
    if summary["shared"]:
        auth.end_kiosk_session(request)
    request.session["kiosk_done"] = summary
    return redirect("kiosk:done")


@auth.employee_required
def home(request):
    """Scan or type a barcode. Its own GET form, so a scanner's Enter only looks it up."""
    barcode = request.GET.get("barcode", "").strip()
    if not barcode:
        return _home(request)
    material = Material.objects.filter(barcode=barcode).first()
    if material is None:
        return _home(request, barcode=barcode, error=f"No material with barcode {barcode}.")
    if not material.active:
        return _home(request, barcode=barcode, error=f"{material.name} is archived.")
    form = IssueForm(initial={"material": material, "qty": request.GET.get("qty")})
    return _home(request, barcode=barcode, material=material, form=form)


@auth.employee_required
def confirm(request):
    """Check the request before anything changes. GET: it only shows what will happen."""
    form = IssueForm(request.GET)
    if not form.is_valid():
        return _home_for(request, request.GET.get("material"), form)
    material, qty = form.cleaned_data["material"], form.cleaned_data["qty"]
    if qty > material.qty_on_hand:
        on_hand = services.plain(material.qty_on_hand)
        form.add_error("qty", f"Only {on_hand} {material.unit} in stock.")
        return _home(request, barcode=material.barcode, material=material, form=form)
    confirm_form = ConfirmIssueForm(initial={**form.cleaned_data, "key": uuid.uuid4()})
    return render(request, "kiosk/confirm.html", {"form": confirm_form, **form.cleaned_data})


@require_POST
@auth.employee_required
def issue(request):
    form = ConfirmIssueForm(request.POST)
    if not form.is_valid():
        return _home_for(request, request.POST.get("material"), form)
    data = form.cleaned_data
    try:
        move = services.issue(
            data["material"],
            data["qty"],
            request.employee,
            case_ref=data["case_ref"],
            key=data["key"],
            user=request.user if request.user.is_authenticated else None,
        )
    except services.StockError as error:
        return _home_for(request, data["material"].pk, IssueForm(initial=data), str(error))
    return _finish(request, "issue", move)


def _returns_page(request, error=None, error_move=None):
    moves = list(_returnable(request.employee))
    for move in moves:
        move.key = uuid.uuid4()  # one request key per row (ADR 0007)
    context = {"moves": moves, "error": error, "error_move": error_move}
    return render(request, "kiosk/returns.html", context)


@auth.employee_required
def returns(request):
    return _returns_page(request)


@require_POST
@auth.employee_required
def return_move(request, move_id):
    # Same query as the list, so the 14-day and ownership rules can't drift apart.
    move = get_object_or_404(_returnable(request.employee), pk=move_id)
    form = ReturnForm(request.POST)
    if not form.is_valid():
        return _returns_page(request, "Enter a quantity above zero.", move.pk)
    try:
        back = services.return_(
            move,
            form.cleaned_data["qty"],
            key=form.cleaned_data["key"],
            user=request.user if request.user.is_authenticated else None,
        )
    except services.StockError as error:
        return _returns_page(request, str(error), move.pk)
    return _finish(request, "return", back)


def done(request):
    summary = request.session.pop("kiosk_done", None)
    if summary is None:
        return redirect("kiosk:start")
    return render(request, "kiosk/done.html", {"done": summary})


@require_POST
def sign_out(request):
    auth.end_kiosk_session(request)
    return redirect("kiosk:start")


def register(request, token):
    """GET only asks; POST consumes. Chat apps open links to build previews, which must not
    use up the one-time link."""
    if not LabSettings.load().shared_allowed:
        return auth.not_available(request, auth.USE_PHONE)
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

    def dispatch(self, request, *args, **kwargs):
        if not LabSettings.load().personal_allowed:
            return auth.not_available(request, auth.USE_TABLET)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        remember = form.cleaned_data["remember"]
        self.request.session.set_expiry(timedelta(days=30) if remember else 0)
        return response
