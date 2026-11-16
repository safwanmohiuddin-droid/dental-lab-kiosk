# 0006. Stock in via staged Excel import

- Status: Accepted (owner, 2026-11-16)
- Date: 2026-11-16

## Context
Labs already keep supplier deliveries in spreadsheets. Typing receipts one by one won't happen.

## Decision
Upload `.xlsx` (openpyxl) → **validate every row** → show a preview with errors per row →
owner clicks Commit → all rows posted in ONE transaction, or none. A downloadable template defines
columns: `barcode` (text), `name`, `qty`, `unit`, `unit_cost` (optional), `reference` (optional).
Unknown barcodes can create materials in the same import (checkbox). The SHA-256 of the file is
stored; uploading the same file twice is refused.

## Alternatives considered
- Post rows as they're read: a bad row 200 leaves 199 half-imported.
- CSV only: users have Excel; CSV loses leading zeros and encodings vary.

## Consequences
An `import_batch` table (status: validated / committed / failed) with row-level errors stored as
JSON for the preview.

## Interview angle
"Validate-then-commit, all-or-nothing, idempotent by file hash, and the leading-zero barcode bug
Excel gave me."
