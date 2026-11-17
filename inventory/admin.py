from django import forms
from django.contrib import admin, messages
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin

from . import excel_import, services
from .models import Department, Employee, ImportBatch, Material, StockMove
from .resources import DepartmentResource, EmployeeResource, MaterialResource
from .services import StockError


class MasterDataAdmin(ImportExportModelAdmin):
    """Import/export (Excel, CSV, pasted rows) and delete-or-archive for master data.

    Anything with stock history can't be deleted without rewriting past reports (ADR 0004), so
    "Delete or archive" deletes what has no history and archives the rest.
    """

    import_template_name = "admin/inventory/import_with_paste.html"
    actions = ["delete_or_archive", "restore"]

    def has_history(self, obj):
        raise NotImplementedError

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        return allowed and (obj is None or not self.has_history(obj))

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)  # replaced by delete_or_archive
        return actions

    @admin.action(description="Delete selected (archive the ones with history)")
    def delete_or_archive(self, request, queryset):
        deleted = archived = 0
        for obj in queryset:
            if not self.has_history(obj):
                try:
                    obj.delete()
                    deleted += 1
                    continue
                except ProtectedError:
                    pass  # still referenced (for example a department with employees)
            if obj.active:
                obj.active = False
                obj.save(update_fields=["active"])
            archived += 1
        messages.success(
            request,
            f"Deleted {deleted}. Archived {archived} that have history or are still in use "
            "(hidden from the kiosk, kept in reports).",
        )

    @admin.action(description="Restore selected (un-archive)")
    def restore(self, request, queryset):
        messages.success(request, f"Restored {queryset.update(active=True)}.")


@admin.register(Department)
class DepartmentAdmin(MasterDataAdmin):
    resource_classes = [DepartmentResource]
    list_display = ["name", "active"]
    list_filter = ["active"]
    search_fields = ["name"]

    def has_history(self, obj):
        return StockMove.objects.filter(department=obj).exists()


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
class EmployeeAdmin(MasterDataAdmin):
    resource_classes = [EmployeeResource]
    form = EmployeeForm
    list_display = ["name", "department", "user", "has_pin", "pin_locked_until", "active"]
    list_filter = ["department", "active"]
    search_fields = ["name"]
    autocomplete_fields = ["user"]
    actions = [*MasterDataAdmin.actions, "unlock_pin"]

    def has_history(self, obj):
        return StockMove.objects.filter(employee=obj).exists()

    @admin.display(boolean=True, description="PIN set")
    def has_pin(self, obj):
        return bool(obj.pin_hash)

    @admin.action(description="Unlock PIN sign-in")
    def unlock_pin(self, request, queryset):
        count = queryset.update(failed_pin_attempts=0, pin_locked_until=None)
        messages.success(request, f"Unlocked {count} employee(s).")


class CountForm(forms.Form):
    counted = forms.DecimalField(
        label="Counted on the shelf", max_digits=12, decimal_places=3, min_value=0
    )
    note = forms.CharField(label="Reason", max_length=200, initial="Stock count")


@admin.register(Material)
class MaterialAdmin(MasterDataAdmin):
    resource_classes = [MaterialResource]
    list_display = ["name", "barcode", "category", "unit", "stock", "avg_cost", "active"]
    list_filter = ["category", "active"]
    search_fields = ["name", "barcode"]
    readonly_fields = ["stock", "avg_cost"]  # changed only through stock moves

    def has_history(self, obj):
        return obj.moves.exists()

    @admin.display(description="In stock", ordering="qty_on_hand")
    def stock(self, obj):
        if obj.pk is None:
            return "0 (add stock with a stock import)"
        url = reverse("admin:inventory_material_count", args=[obj.pk])
        return format_html(
            '{} {} &nbsp;<a href="{}">Correct count</a>',
            services.plain(obj.qty_on_hand),
            obj.unit,
            url,
        )

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path("<int:pk>/count/", view(self.count_view), name="inventory_material_count"),
            *super().get_urls(),
        ]

    def count_view(self, request, pk):
        if not self.has_change_permission(request):
            return HttpResponse(status=403)
        material = get_object_or_404(Material, pk=pk)
        form = CountForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                move = services.count(
                    material,
                    form.cleaned_data["counted"],
                    note=form.cleaned_data["note"],
                    user=request.user,
                )
            except StockError as error:
                form.add_error("counted", str(error))
            else:
                if move is None:
                    messages.info(request, "The count matches the system. Nothing changed.")
                else:
                    messages.success(
                        request, f"Stock corrected by {services.plain(move.qty)} {material.unit}."
                    )
                return redirect("admin:inventory_material_changelist")
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": f"Correct stock count: {material.name}",
            "material": material,
            "on_hand": services.plain(material.qty_on_hand),
            "form": form,
        }
        return TemplateResponse(request, "admin/inventory/material/count.html", context)


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    """Read-only: moves are written by the stock services, never edited. Mistakes get an Undo."""

    list_display = [
        "created_at",
        "kind",
        "material",
        "qty",
        "unit_cost",
        "department",
        "employee",
        "note",
    ]
    list_filter = ["kind", "department", "flagged"]
    search_fields = ["material__name", "material__barcode", "employee__name", "case_ref"]
    date_hierarchy = "created_at"
    list_select_related = ["material", "department", "employee"]
    actions = ["undo"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Undo selected movements (adds a correcting movement)")
    def undo(self, request, queryset):
        for move in queryset:
            try:
                services.undo(move, user=request.user)
            except StockError as error:
                messages.error(request, f"Movement #{move.pk}: {error}")
            else:
                messages.success(request, f"Movement #{move.pk} undone.")


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
