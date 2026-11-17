from django.contrib import admin

from .models import Department, Employee, Material, StockMove


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "active"]
    list_filter = ["active"]
    search_fields = ["name"]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["name", "department", "user", "active"]
    list_filter = ["department", "active"]
    search_fields = ["name"]
    autocomplete_fields = ["user"]


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
