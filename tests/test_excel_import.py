import io
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook, load_workbook

from inventory import excel_import
from inventory.models import ImportBatch, Material, StockMove
from inventory.services import StockError

HEADER = ["barcode", "name", "qty", "unit", "unit_cost", "category", "reference"]


def xlsx(*rows, header=HEADER, name="delivery.xlsx"):
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for row in rows:
        ws.append(list(row))
    out = io.BytesIO()
    wb.save(out)
    return SimpleUploadedFile(name, out.getvalue())


def upload(admin_user, *rows, create_missing=False, **kw):
    return excel_import.create_batch(xlsx(*rows, **kw), create_missing, admin_user)


def messages(batch):
    return [e["message"] for e in batch.errors]


# happy path


def test_valid_file_previews_then_commits(admin_user, material):
    batch = upload(admin_user, [material.barcode, "", 10, "", 80, "", "INV-7"])
    assert batch.status == ImportBatch.Status.VALID and not StockMove.objects.exists()

    excel_import.commit(batch.pk, admin_user)

    material.refresh_from_db()
    assert (material.qty_on_hand, material.avg_cost) == (10, 80)
    move = StockMove.objects.get()
    assert (move.import_batch_id, move.note) == (batch.pk, "INV-7")


def test_commit_twice_imports_once(admin_user, material):
    batch = upload(admin_user, [material.barcode, "", 5])
    excel_import.commit(batch.pk, admin_user)
    excel_import.commit(batch.pk, admin_user)  # double click
    material.refresh_from_db()
    assert material.qty_on_hand == 5 and StockMove.objects.count() == 1


def test_new_materials_are_created_when_allowed(admin_user):
    batch = upload(admin_user, ["NEW-1", "Glaze paste", 3, "g", 2.5], create_missing=True)
    excel_import.commit(batch.pk, admin_user)
    new = Material.objects.get(barcode="NEW-1")
    assert (new.name, new.unit, new.qty_on_hand, new.avg_cost) == ("Glaze paste", "g", 3, D("2.5"))


def test_price_column_is_optional(admin_user, material):
    batch = upload(admin_user, [material.barcode, None, 4], header=["barcode", "name", "qty"])
    excel_import.commit(batch.pk, admin_user)
    material.refresh_from_db()
    assert (material.qty_on_hand, material.avg_cost) == (4, None)


def test_blank_rows_are_skipped(admin_user, material):
    batch = upload(admin_user, [material.barcode, "", 1], [None] * 7, [material.barcode, "", 2])
    assert [r["row"] for r in batch.rows] == [2, 4]


# the Excel traps


def test_barcode_that_lost_its_leading_zero_is_explained(admin_user):
    Material.objects.create(name="Alumina", barcode="012345678905")
    batch = upload(admin_user, [12345678905, "", 1])  # what Excel stores if typed in a number cell
    assert batch.status == ImportBatch.Status.INVALID
    assert "Excel turned barcode 012345678905 into the number 12345678905" in messages(batch)[0]


def test_numeric_barcode_without_zero_still_matches(admin_user):
    Material.objects.create(name="Disc", barcode="200000000011")
    batch = upload(admin_user, [200000000011, "", 1])
    assert batch.status == ImportBatch.Status.VALID


def test_float_noise_in_quantity_is_rounded(admin_user, material):
    batch = upload(admin_user, [material.barcode, "", 4.999999999])
    assert batch.rows[0]["qty"] == "5.000"


def test_too_many_decimals_is_an_error_not_a_rounding(admin_user, material):
    batch = upload(admin_user, [material.barcode, "", 1.2345])
    assert messages(batch) == ["Quantity has more than 3 decimal places."]


def test_formula_without_saved_value_is_reported(admin_user, material):
    batch = upload(admin_user, [material.barcode, "", "=2+3"])  # openpyxl saves no cached result
    assert "formulas must be saved" in messages(batch)[0]


# all-or-nothing


def test_one_bad_row_blocks_the_whole_file(admin_user, material):
    batch = upload(admin_user, [material.barcode, "", 5], ["UNKNOWN", "", 1])
    assert batch.status == ImportBatch.Status.INVALID
    with pytest.raises(StockError):
        excel_import.commit(batch.pk, admin_user)
    material.refresh_from_db()
    assert material.qty_on_hand == 0


def test_material_archived_after_preview_rolls_back_everything(admin_user, material):
    other = Material.objects.create(name="Bur", barcode="BUR-1")
    batch = upload(admin_user, [material.barcode, "", 5], [other.barcode, "", 2])
    other.active = False
    other.save()
    with pytest.raises(StockError):
        excel_import.commit(batch.pk, admin_user)
    material.refresh_from_db()
    assert material.qty_on_hand == 0 and not StockMove.objects.exists()


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (["", "", 1], "Barcode is empty."),
        (["200000000011", "", 0], "Quantity must be more than zero."),
        (["200000000011", "", "ten"], "Quantity must be a number, not 'ten'."),
        (["200000000011", "", 1, "", -5], "Unit cost can't be negative."),
        (["NEW-2", "", 1], "Unknown barcode NEW-2. Tick 'create unknown materials'."),
        (["AB 12", "", 1], "Barcode 'AB 12' contains a space."),
    ],
)
def test_row_errors(admin_user, material, row, expected):
    assert expected in messages(upload(admin_user, row))


def test_new_material_needs_a_name(admin_user):
    batch = upload(admin_user, ["NEW-3", "", 1], create_missing=True)
    assert messages(batch) == ["New barcode NEW-3 needs a name."]


# file-level checks


def test_same_file_twice_is_refused(admin_user, material):
    first = upload(admin_user, [material.barcode, "", 1])
    with pytest.raises(excel_import.DuplicateFile) as dup:
        upload(admin_user, [material.barcode, "", 1])
    assert dup.value.batch == first


def test_missing_required_column(admin_user):
    batch = upload(admin_user, ["x", 1], header=["barcode", "amount"])
    assert messages(batch) == ["Missing column(s): qty."]


def test_not_an_excel_file(admin_user):
    junk = SimpleUploadedFile("stock.xlsx", b"this is not a spreadsheet")
    batch = excel_import.create_batch(junk, False, admin_user)
    assert messages(batch) == ["This is not a valid .xlsx file."]


def test_empty_file(admin_user):
    assert messages(upload(admin_user)) == ["The file has no data rows."]


def test_template_has_columns_and_text_barcodes():
    ws = load_workbook(io.BytesIO(excel_import.build_template())).active
    assert [c.value for c in ws[1]] == HEADER
    assert ws["A2"].number_format == "@"


# admin screens


def test_admin_upload_preview_and_commit(admin_client, material):
    page = admin_client.post(
        "/admin/inventory/importbatch/add/", {"file": xlsx([material.barcode, "", 7])}
    )
    batch = ImportBatch.objects.get()
    assert page.status_code == 302
    preview = admin_client.get(page.url)
    assert b"Commit 1 row to stock" in preview.content

    admin_client.post(f"/admin/inventory/importbatch/{batch.pk}/commit/")

    material.refresh_from_db()
    assert material.qty_on_hand == 7


def test_admin_commit_needs_post(admin_client, admin_user, material):
    batch = upload(admin_user, [material.barcode, "", 1])
    assert admin_client.get(f"/admin/inventory/importbatch/{batch.pk}/commit/").status_code == 405


def test_admin_template_download(admin_client):
    response = admin_client.get("/admin/inventory/importbatch/template/")
    assert response.status_code == 200 and response.content[:2] == b"PK"  # xlsx is a zip
