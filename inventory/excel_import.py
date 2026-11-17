"""Stock in from Excel: validate every row, preview, then commit all rows or none (ADR 0006)."""

import hashlib
import io
import uuid
import zipfile
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from . import services
from .models import ImportBatch, Material
from .services import StockError

COLUMNS = ["barcode", "name", "qty", "unit", "unit_cost", "category", "reference"]
HELP = {
    "barcode": "Required. Keep this column formatted as Text so leading zeros survive.",
    "name": "Required only for new materials.",
    "qty": "Required. Amount received, more than zero. Up to 3 decimals.",
    "unit": "Optional, for new materials (pcs, g, ml, disc...). Default pcs.",
    "unit_cost": "Optional. Price per unit, up to 4 decimals.",
    "category": "Optional, for new materials.",
    "reference": "Optional. Supplier invoice or delivery note number.",
}
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
TEMPLATE_ROWS = 1000
KEY_NAMESPACE = uuid.UUID("6f1c2a52-6f0e-4c39-9d0e-6a1f6f3f1b7e")


class DuplicateFile(Exception):
    def __init__(self, batch):
        super().__init__(f"This exact file was already uploaded as import #{batch.pk}.")
        self.batch = batch


def build_template():
    wb = Workbook()
    ws = wb.active
    ws.title = "Deliveries"
    ws.append(COLUMNS)
    for row in range(2, TEMPLATE_ROWS + 2):
        ws.cell(row=row, column=1).number_format = "@"  # Text, so 0123... keeps its zero
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 34
    help_sheet = wb.create_sheet("Instructions")
    help_sheet.append(["Column", "What to enter"])
    for name in COLUMNS:
        help_sheet.append([name, HELP[name]])
    help_sheet.column_dimensions["B"].width = 80
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _sha256(upload):
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()


def _decimal(value, places, label):
    """Excel number or text -> Decimal with at most `places` decimals. Returns (value, error)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    if isinstance(value, bool):
        return None, f"{label} must be a number."
    try:
        # str() first: Decimal(4.999999999) would carry the float's binary noise.
        number = Decimal(value.strip() if isinstance(value, str) else str(value))
    except InvalidOperation:
        return None, f"{label} must be a number, not '{value}'."
    if not number.is_finite():
        return None, f"{label} must be a number."
    rounded = number.quantize(Decimal(1).scaleb(-places))
    if abs(rounded - number) > Decimal("0.000001"):  # float noise is fine, real digits are not
        return None, f"{label} has more than {places} decimal places."
    return rounded, None


def _barcode(value):
    """Returns (text, came_from_a_number_cell, error)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, False, "Barcode is empty."
    if isinstance(value, bool):
        return None, False, "Barcode must be text."
    if isinstance(value, float):
        if not value.is_integer():
            return None, True, "Barcode was read as a decimal number; format the column as Text."
        value = int(value)
    if isinstance(value, int):
        return str(value), True, None
    text = str(value).strip()
    if " " in text:
        return None, False, f"Barcode '{text}' contains a space."
    return text, False, None


def _text(value):
    return "" if value is None else str(value).strip()


def read_rows(upload, create_missing):
    """Parse and validate an uploaded workbook. Returns (rows, errors); errors block the import."""
    if upload.size > MAX_BYTES:
        return [], [{"row": None, "message": "File is larger than 5 MB."}]
    try:
        wb = load_workbook(upload, read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError):
        return [], [{"row": None, "message": "This is not a valid .xlsx file."}]

    lines = wb.worksheets[0].iter_rows(values_only=True)
    header = [_text(h).lower().replace(" ", "_") for h in next(lines, ())]
    missing = [c for c in ("barcode", "qty") if c not in header]
    if missing:
        wb.close()
        return [], [{"row": 1, "message": f"Missing column(s): {', '.join(missing)}."}]
    col = {name: header.index(name) for name in COLUMNS if name in header}

    materials = {m.barcode: m for m in Material.objects.all()}
    # Excel stores 0123 as the number 123; this lets us say what went wrong.
    zero_stripped = {b.lstrip("0"): b for b in materials if b.startswith("0")}

    rows, errors, seen_new, data_rows = [], [], {}, 0
    for number, values in enumerate(lines, start=2):
        cell = {name: values[i] if i < len(values) else None for name, i in col.items()}
        if all(v is None or _text(v) == "" for v in cell.values()):
            continue
        data_rows += 1
        if data_rows > MAX_ROWS:
            errors.append({"row": number, "message": f"More than {MAX_ROWS} rows; split the file."})
            break

        problems = []
        barcode, numeric, err = _barcode(cell.get("barcode"))
        problems += [err] if err else []
        qty, err = _decimal(cell.get("qty"), 3, "Quantity")
        if err:
            problems.append(err)
        elif qty is None:
            problems.append("Quantity is empty (formulas must be saved in Excel first).")
        elif qty <= 0:
            problems.append("Quantity must be more than zero.")
        cost, err = _decimal(cell.get("unit_cost"), 4, "Unit cost")
        problems += [err] if err else []
        if cost is not None and cost < 0:
            problems.append("Unit cost can't be negative.")

        name, new = _text(cell.get("name")), False
        material = materials.get(barcode) if barcode else None
        if barcode and material is None:
            if numeric and barcode in zero_stripped:
                problems.append(
                    f"Excel turned barcode {zero_stripped[barcode]} into the number {barcode}. "
                    "Format the barcode column as Text and type it again."
                )
            elif not create_missing:
                problems.append(f"Unknown barcode {barcode}. Tick 'create unknown materials'.")
            elif not name and barcode not in seen_new:
                problems.append(f"New barcode {barcode} needs a name.")
            else:
                new = True
                seen_new.setdefault(barcode, name)
        elif material and not material.active:
            problems.append(f"{material.name} is archived.")

        if problems:
            errors += [{"row": number, "message": p} for p in problems]
            continue
        rows.append(
            {
                "row": number,
                "barcode": barcode,
                "name": material.name if material else seen_new[barcode],
                "new": new,
                "qty": str(qty),
                "unit": material.unit if material else (_text(cell.get("unit")) or "pcs"),
                "unit_cost": None if cost is None else str(cost),
                "category": _text(cell.get("category")),
                "reference": _text(cell.get("reference")),
            }
        )
    wb.close()
    if not rows and not errors:
        errors.append({"row": None, "message": "The file has no data rows."})
    return rows, errors


def create_batch(upload, create_missing, user):
    digest = _sha256(upload)
    if existing := ImportBatch.objects.filter(file_sha256=digest).first():
        raise DuplicateFile(existing)
    rows, errors = read_rows(upload, create_missing)
    return ImportBatch.objects.create(
        file_name=upload.name[:255],
        file_sha256=digest,
        create_missing=create_missing,
        status=ImportBatch.Status.INVALID if errors else ImportBatch.Status.VALID,
        rows=rows,
        errors=errors,
        created_by=user,
    )


@transaction.atomic
def commit(batch_id, user):
    """Post every row as a receipt, or nothing. Safe to call twice (double click)."""
    batch = ImportBatch.objects.select_for_update().get(pk=batch_id)
    if batch.status == ImportBatch.Status.COMMITTED:
        return batch
    if batch.status != ImportBatch.Status.VALID:
        raise StockError("Fix the errors and upload the file again.")
    for row in batch.rows:
        material, _ = Material.objects.get_or_create(
            barcode=row["barcode"],
            defaults={"name": row["name"], "unit": row["unit"], "category": row["category"]},
        )
        services.receive(
            material,
            Decimal(row["qty"]),
            None if row["unit_cost"] is None else Decimal(row["unit_cost"]),
            key=uuid.uuid5(KEY_NAMESPACE, f"{batch.pk}:{row['row']}"),
            user=user,
            note=row["reference"],
            import_batch=batch,
        )
    batch.status = ImportBatch.Status.COMMITTED
    batch.committed_at = timezone.now()
    batch.save(update_fields=["status", "committed_at"])
    return batch
