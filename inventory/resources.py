"""Excel / CSV / pasted-rows import and export of master data (django-import-export).

Stock quantities are NOT imported here: deliveries go through the stock import (ADR 0006),
so every change to stock stays in the ledger.
"""

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from .excel_import import _barcode
from .models import Department, Employee, Material


class DepartmentByName(ForeignKeyWidget):
    """Departments are matched by name and created when missing, so one sheet sets up everything."""

    def __init__(self):
        super().__init__(Department, field="name")

    def clean(self, value, row=None, **kwargs):
        name = (value or "").strip()
        if not name:
            raise ValueError("Department is empty.")
        return Department.objects.get_or_create(name=name)[0]


class DepartmentResource(resources.ModelResource):
    class Meta:
        model = Department
        fields = ("name", "active")
        import_id_fields = ("name",)
        skip_unchanged = True


class EmployeeResource(resources.ModelResource):
    department = fields.Field(
        attribute="department", column_name="department", widget=DepartmentByName()
    )

    class Meta:
        model = Employee
        fields = ("name", "department", "active")
        import_id_fields = ("name",)
        skip_unchanged = True


class MaterialResource(resources.ModelResource):
    qty_on_hand = fields.Field(attribute="qty_on_hand", column_name="qty_on_hand", readonly=True)
    avg_cost = fields.Field(attribute="avg_cost", column_name="avg_cost", readonly=True)

    class Meta:
        model = Material
        fields = ("barcode", "name", "unit", "category", "active", "qty_on_hand", "avg_cost")
        import_id_fields = ("barcode",)
        skip_unchanged = True

    def before_import_row(self, row, **kwargs):
        # Same barcode rules as the stock import: text, no spaces, and catch Excel's dropped zeros.
        text, numeric, error = _barcode(row.get("barcode"))
        if error:
            raise ValueError(error)
        if numeric:
            zero_lost = Material.objects.filter(barcode__endswith=text, barcode__startswith="0")
            match = next((m.barcode for m in zero_lost if m.barcode.lstrip("0") == text), None)
            if match:
                raise ValueError(
                    f"Excel turned barcode {match} into the number {text}. "
                    "Format the barcode column as Text."
                )
        row["barcode"] = text
