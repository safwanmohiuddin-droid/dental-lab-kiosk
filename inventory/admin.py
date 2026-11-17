from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from . import excel_import
from .models import Department, Employee, ImportBatch, Material, StockMove
from .services import StockError


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "active"]
    list_filter = ["active"]
    search_fields = ["name"]


class EmployeeForm(forms.ModelForm):
    new_pin = forms.CharField(
        label="New PIN",
        required=False,
        widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "new-password"}),
        help_text="4 to 6 digits for shared tablets. Leave empty to keep the current PIN.",
    )

    class Meta:
        model = Employee
        fields = ["name", "department", "user", "active"]

    def clean_new_pin(self):
        pin = self.cleaned_data["new_pin"]
        if pin:
            try:
                self.instance.set_pin(pin)
            except ValueError as error:
                raise forms.ValidationError(str(error)) from error
        return pin


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    form = EmployeeForm
    list_display = ["name", "department", "user", "has_pin", "pin_locked_until", "active"]
    list_filter = ["department", "active"]
    search_fields = ["name"]
    autocomplete_fields = ["user"]
    actions = ["unlock_pin"]

    @admin.display(boolean=True, description="PIN set")
    def has_pin(self, obj):
        return bool(obj.pin_hash)

    @admin.action(description="Unlock PIN sign-in")
    def unlock_pin(self, request, queryset):
        count = queryset.update(failed_pin_attempts=0, pin_locked_until=None)
        messages.success(request, f"Unlocked {count} employee(s).")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ["name", "barcode", "category", "unit", "qty_on_hand", "avg_cost", "active"]
    list_filter = ["category", "active"]
    search_fields = ["name", "barcode"]
    readonly_fields = ["qty_on_hand", "avg_cost"]  # changed only through stock moves


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    """Read-only: moves are written by the stock services (Phase 2), never edited by hand."""

    list_display = ["created_at", "kind", "material", "qty", "unit_cost", "department", "employee"]
    list_filter = ["kind", "department", "flagged"]
    search_fields = ["material__name", "material__barcode", "employee__name", "case_ref"]
    date_hierarchy = "created_at"
    list_select_related = ["material", "department", "employee"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class UploadForm(forms.Form):
    file = forms.FileField(
        label="Excel file (.xlsx)",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )
    create_missing = forms.BooleanField(
        label="Create unknown materials",
        required=False,
        help_text="Barcodes not in the system become new materials (needs a name column).",
    )


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    """Upload -> preview with row errors -> commit all rows or none (ADR 0006)."""

    list_display = ["file_name", "status", "row_count", "created_by", "created_at", "committed_at"]
    list_filter = ["status"]
    fields = ["file_name", "status", "create_missing", "created_by", "created_at", "committed_at"]
    readonly_fields = fields

    @admin.display(description="rows")
    def row_count(self, obj):
        return len(obj.rows)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Uncommitted uploads may be deleted (e.g. to upload a fixed copy of the same file).
        return super().has_delete_permission(request, obj) and (
            obj is None or obj.status != ImportBatch.Status.COMMITTED
        )

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path("template/", view(self.template_view), name="inventory_importbatch_template"),
            path("<int:pk>/commit/", view(self.commit_view), name="inventory_importbatch_commit"),
            *super().get_urls(),
        ]

    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            return HttpResponse(status=403)
        form = UploadForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            try:
                batch = excel_import.create_batch(
                    form.cleaned_data["file"], form.cleaned_data["create_missing"], request.user
                )
            except excel_import.DuplicateFile as dup:
                url = reverse("admin:inventory_importbatch_change", args=[dup.batch.pk])
                form.add_error("file", format_html('{} <a href="{}">Open it</a>.', dup, url))
            else:
                return redirect("admin:inventory_importbatch_change", batch.pk)
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Import deliveries from Excel",
            "form": form,
        }
        return TemplateResponse(request, "admin/inventory/importbatch/upload.html", context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        batch = get_object_or_404(ImportBatch, pk=object_id)
        extra_context = {
            **(extra_context or {}),
            "batch": batch,
            "can_commit": batch.status == ImportBatch.Status.VALID
            and self.has_add_permission(request),
        }
        return super().change_view(request, object_id, form_url, extra_context)

    def template_view(self, request):
        response = HttpResponse(
            excel_import.build_template(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="stock-import-template.xlsx"'
        return response

    def commit_view(self, request, pk):
        if request.method != "POST":
            return HttpResponse(status=405)
        if not self.has_add_permission(request):
            return HttpResponse(status=403)
        try:
            batch = excel_import.commit(pk, request.user)
        except StockError as error:
            messages.error(request, f"Nothing was imported: {error}")
        else:
            messages.success(request, f"Imported {len(batch.rows)} rows into stock.")
        return redirect("admin:inventory_importbatch_change", pk)
