# Changelog

## 0.2.0 (2026-11-17)

- **Backups are now encrypted** with a public key (age) and can be copied off-site (rclone).
  Upgrading: set `BACKUP_AGE_RECIPIENT` in `.env` and install `age`, or backups stop with a clear
  message. See docs/operations.md, Backups.
- `SECRET_KEY_FALLBACKS` for rotating the secret key without unregistering tablets.
- Nightly warning when `.env` is readable by other users.
- The site root `/` opens the kiosk instead of a 404.
- `seed_demo` creates demo logins (development only).

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
