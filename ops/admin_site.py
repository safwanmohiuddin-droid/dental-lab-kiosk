from django.conf import settings
from django.contrib.admin import AdminSite
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

    def has_permission(self, request):
        if settings.ADMIN_REQUIRE_2FA:
            return super().has_permission(request)
        return AdminSite.has_permission(self, request)
