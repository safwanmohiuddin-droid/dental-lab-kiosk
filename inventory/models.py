import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

QTY = {"max_digits": 12, "decimal_places": 3}  # grams, ml, fractions of a disc (ADR 0012)
MONEY = {"max_digits": 14, "decimal_places": 4}


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    name = models.CharField(max_length=150)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Only for employees who sign in on their own phone.",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Material(models.Model):
    name = models.CharField(max_length=200)
    barcode = models.CharField(max_length=64, unique=True)
    unit = models.CharField(max_length=20, default="pcs")
    category = models.CharField(max_length=100, blank=True)
    # Cache of the ledger (ADR 0004); only the stock services may change these.
    qty_on_hand = models.DecimalField(**QTY, default=0)
    avg_cost = models.DecimalField(**MONEY, null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(barcode="") & ~Q(barcode__contains=" "),
                name="material_barcode_not_blank_no_spaces",
            ),
            models.CheckConstraint(
                condition=Q(avg_cost__isnull=True) | Q(avg_cost__gte=0),
                name="material_avg_cost_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.barcode})"


class ImportBatch(models.Model):
    """One uploaded Excel file of deliveries: validated first, committed all at once (ADR 0006)."""

    class Status(models.TextChoices):
        VALID = "valid", "Ready to commit"
        INVALID = "invalid", "Has errors"
        COMMITTED = "committed", "Committed"

    file_name = models.CharField(max_length=255)
    file_sha256 = models.CharField(max_length=64, unique=True)
    create_missing = models.BooleanField(
        "create unknown materials", default=False, help_text="Add new barcodes as new materials."
    )
    status = models.CharField(max_length=10, choices=Status)
    rows = models.JSONField(default=list)
    errors = models.JSONField(default=list)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "stock imports"
        verbose_name = "stock import"

    def __str__(self):
        return f"{self.file_name} ({self.get_status_display()})"


class StockMove(models.Model):
    """Append-only ledger row. Never updated or deleted; fix mistakes with a reversing move."""

    class Kind(models.TextChoices):
        RECEIPT = "receipt"
        ISSUE = "issue"
        RETURN = "return"
        ADJUST = "adjust"

    kind = models.CharField(max_length=10, choices=Kind)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="moves")
    qty = models.DecimalField(**QTY, help_text="Positive into stock, negative out of stock.")
    unit_cost = models.DecimalField(**MONEY, null=True, blank=True)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True)
    case_ref = models.CharField("case number", max_length=50, blank=True)
    returns_move = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="returns"
    )
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    flagged = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    import_batch = models.ForeignKey(
        ImportBatch, on_delete=models.PROTECT, null=True, blank=True, related_name="moves"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["department", "created_at"]),
            models.Index(fields=["material", "created_at"]),
            models.Index(fields=["employee", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["receipt", "issue", "return", "adjust"]),
                name="move_kind_valid",
            ),
            models.CheckConstraint(condition=~Q(qty=0), name="move_qty_not_zero"),
            models.CheckConstraint(
                condition=Q(unit_cost__isnull=True) | Q(unit_cost__gte=0),
                name="move_unit_cost_not_negative",
            ),
            models.CheckConstraint(
                condition=~Q(kind="receipt") | Q(qty__gt=0), name="move_receipt_adds_stock"
            ),
            models.CheckConstraint(
                condition=~Q(kind="issue")
                | Q(qty__lt=0, employee__isnull=False, department__isnull=False),
                name="move_issue_has_who_and_department",
            ),
            models.CheckConstraint(
                condition=~Q(kind="return")
                | Q(
                    qty__gt=0,
                    returns_move__isnull=False,
                    employee__isnull=False,
                    department__isnull=False,
                ),
                name="move_return_links_issue",
            ),
            models.CheckConstraint(
                condition=Q(kind="return") | Q(returns_move__isnull=True),
                name="move_only_returns_link_issue",
            ),
            models.CheckConstraint(
                condition=Q(kind="receipt") | Q(import_batch__isnull=True),
                name="move_only_receipts_come_from_imports",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.qty} {self.material.unit} of {self.material.name}"
