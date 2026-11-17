from django.conf import settings
from django.contrib.admin import AdminSite
from django.urls import reverse
from django_otp import devices_for_user
from django_otp.admin import OTPAdminAuthenticationForm, OTPAdminSite


class OneStepOTPForm(OTPAdminAuthenticationForm):
    """django-otp 1.7 makes users pick a device first; with one authenticator, pick it for them."""

    def _chosen_device(self, user):
        device = super()._chosen_device(user)
        if device is None:
            devices = list(devices_for_user(user))  # only this user's confirmed devices
            if len(devices) == 1:
                device = devices[0]
        return device


class KioskAdminSite(OTPAdminSite):
    """Admin that needs a TOTP code when ADMIN_REQUIRE_2FA is on (ADR 0026).

    Read at request time, so tests and dev can turn it off without a second URLconf.
    """

    @property
    def login_form(self):
        return OneStepOTPForm if settings.ADMIN_REQUIRE_2FA else None

    @property
    def login_template(self):
        return OTPAdminSite.login_template if settings.ADMIN_REQUIRE_2FA else None

    site_header = "Material kiosk"
    site_title = "Material kiosk"
    index_title = "Lab setup and stock"
    index_template = "admin/kiosk_index.html"

    def index(self, request, extra_context=None):
        from inventory.models import Department, Employee, ImportBatch
        from kiosk.models import Device, LabSettings

        lab = LabSettings.load()

        def url(name):
            return reverse(f"admin:{name}")

        steps = [
            (
                "How people sign in",
                1,
                url("kiosk_labsettings_changelist"),
                f"Now: {lab.get_sign_in_display()}. Change it in Lab settings.",
            ),
            (
                "Departments",
                Department.objects.filter(active=True).count(),
                url("inventory_department_changelist"),
                "Add each department, one by one or from a spreadsheet (Import).",
            ),
            (
                "Employees",
                Employee.objects.filter(active=True).count(),
                url("inventory_employee_changelist"),
                "Add people one by one, or Import a list from a spreadsheet.",
            ),
            (
                "Materials and stock",
                ImportBatch.objects.filter(status="committed").count(),
                url("inventory_importbatch_add"),
                "Upload your stock as an Excel delivery; new barcodes become materials.",
            ),
        ]
        if lab.shared_allowed:
            steps += [
                (
                    "PINs for the shared tablet",
                    Employee.objects.filter(active=True).exclude(pin_hash="").count(),
                    url("inventory_employee_changelist"),
                    "Open each employee and set a 4 to 6 digit PIN.",
                ),
                (
                    "Store-room tablet",
                    Device.objects.filter(active=True, registered_at__isnull=False).count(),
                    url("kiosk_device_add"),
                    "Add a tablet and open the link it shows on the tablet's browser.",
                ),
            ]
        if lab.personal_allowed:
            steps.append(
                (
                    "Personal phone logins",
                    Employee.objects.filter(active=True, user__isnull=False).count(),
                    url("auth_user_add"),
                    "Create a login for each person, then link it on their employee page.",
                )
            )
        setup = [{"title": t, "done": n > 0, "url": u, "help": h} for t, n, u, h in steps]
        extra_context = {
            **(extra_context or {}),
            "setup": setup,
            "setup_done": all(s["done"] for s in setup),
        }
        return super().index(request, extra_context)

    # Developer sections (logins, two-factor devices) go last under one plain name (R2, R8).
    ADVANCED = {"auth": "Advanced: logins and groups", "otp_totp": "Advanced: two-factor apps"}

    def get_app_list(self, request, app_label=None):
        apps = super().get_app_list(request, app_label)
        for app in apps:
            if app["app_label"] in self.ADVANCED:
                app["name"] = self.ADVANCED[app["app_label"]]
        return sorted(apps, key=lambda app: app["app_label"] in self.ADVANCED)

    def has_permission(self, request):
        if settings.ADMIN_REQUIRE_2FA:
            return super().has_permission(request)
        return AdminSite.has_permission(self, request)
