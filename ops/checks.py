from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def admin_2fa_enabled(app_configs, **kwargs):
    if settings.DEBUG or settings.ADMIN_REQUIRE_2FA:
        return []
    return [
        Warning(
            "ADMIN_REQUIRE_2FA is off: the admin can be reached with a password alone.",
            hint="Remove ADMIN_REQUIRE_2FA=False from the production environment (ADR 0026).",
            id="ops.W001",
        )
    ]
