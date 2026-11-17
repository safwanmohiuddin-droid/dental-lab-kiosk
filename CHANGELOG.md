# Changelog

## 0.1.0 (2026-11-17)

First release.

- Stock ledger: receipts, issues, returns and adjustments with row locking, moving average cost
  and an invariant check (`check_ledger`).
- Stock in from Excel: template, row-by-row validation, preview, all-or-nothing commit.
- Kiosk: registered store-room tablets with employee PIN and lockout, or personal login on a
  phone; scan or type a barcode, quantity, optional case number, confirm. Repeat recent issues,
  returns, clear no-connection message.
- Camera barcode scanning on phones (native BarcodeDetector or vendored WASM reader).
- Reports by department, material and person for any date range, with Excel export and cost
  coverage.
- Production: Docker image, Caddy HTTPS, admin and reports behind TOTP two-factor login, health
  check, JSON logs, backup script and restore drill.
