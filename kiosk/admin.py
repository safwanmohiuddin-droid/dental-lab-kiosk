from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["name", "active", "registered_at", "last_seen_at", "registered_by"]
    list_filter = ["active"]
    fields = ["name", "active", "registered_at", "last_seen_at", "registered_by"]
    readonly_fields = ["registered_at", "last_seen_at", "registered_by"]
    actions = ["new_registration_link"]

    def _show_link(self, request, device, token):
        url = request.build_absolute_uri(reverse("kiosk:register", args=[token]))
        messages.warning(
            request,
            format_html(
                "Open this link once on the tablet <b>{}</b> within 24 hours. "
                "It is shown only now: <a href='{}'>{}</a>",
                device.name,
                url,
                url,
            ),
        )

    def save_model(self, request, obj, form, change):
        token = None if change else obj.new_link_token(request.user)
        super().save_model(request, obj, form, change)
        if token:
            self._show_link(request, obj, token)

    @admin.action(description="Create a new registration link (signs the tablet out)")
    def new_registration_link(self, request, queryset):
        for device in queryset:
            token = device.new_link_token(request.user)
            device.save()
            self._show_link(request, device, token)
