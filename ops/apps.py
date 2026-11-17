from django.apps import AppConfig


class OpsConfig(AppConfig):
    name = "ops"
    verbose_name = "Operations"

    def ready(self):
        from django.contrib import admin

        from . import checks  # noqa: F401  (registers the deploy check)
        from .admin_site import KioskAdminSite

        # Swap the default site's class so every existing admin.register() keeps working.
        admin.site.__class__ = KioskAdminSite
