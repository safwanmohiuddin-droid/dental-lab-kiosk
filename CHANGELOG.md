# Changelog

## Unreleased

- **Report builder**: any measure (units used, cost, times taken) by any breakdown (department,
  material, person, category, case) per day, week or month, with filters; live chart and table,
  no Show button; the page address is the report; Excel and CSV export what's on screen.
- **Motion**: content eases in, buttons respond, the quantity bumps, the done tick draws itself,
  charts animate. Off under "reduce motion".
- **Redesign by published UX rules** (docs/ux-rules.md): one look across kiosk, reports and
  admin; name search and recent people on the tablet; an on-screen PIN pad; take in one step
  with a big stepper, with a second look only for unusually large amounts; "Saving..." feedback;
  reports in plain words with quick periods and a headline; admin actions as visible buttons.
- **Lab settings**: choose how people sign in: shared tablet only, personal phones only, or both.
- **Spreadsheets**: import and export departments, employees and materials (Excel, CSV, or paste
  cells straight from Excel or Google Sheets), always with a preview first.
- **Delete selected** deletes what has no history and archives the rest; **Restore** brings
  archived items back.
- **Undo** for a mistaken stock movement (adds a correcting movement) and a **Correct count**
  screen for stock takes.
- Setup checklist on the admin home page; plain-language labels.
- Fix: the 14-day return limit is now enforced on the return itself, not only on the list.

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
