# Importing stock from Excel

Deliveries go in through an Excel file, all rows or none.

1. Admin, Inventory, **Stock imports**, **Add**, then **Download the Excel template**.
2. One row per delivered item:

| Column | Required | Notes |
|---|---|---|
| barcode | yes | Keep the column formatted as **Text**, or Excel drops leading zeros |
| name | new materials only | Ignored for barcodes that already exist |
| qty | yes | More than zero, up to 3 decimals (grams, ml and part-discs are fine) |
| unit | no | For new materials: pcs, g, ml, disc... Default pcs |
| unit_cost | no | Price per unit, up to 4 decimals. Leave empty if unknown |
| category | no | For new materials |
| reference | no | Supplier invoice or delivery note number |

3. Upload. Every row is checked and a preview is shown. **Nothing touches stock yet.**
4. If there are errors, fix the file, delete that import, and upload again.
5. If the preview is right, press **Commit**. All rows go in together.

What it catches: barcodes Excel turned into numbers, quantities like `4.999999999` from
formulas, formulas never saved in Excel, unknown barcodes (tick "create unknown materials" to add
them), negative costs, and the same file uploaded twice. Pressing Commit twice imports once.
