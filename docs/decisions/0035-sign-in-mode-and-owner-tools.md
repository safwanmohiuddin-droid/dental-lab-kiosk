# 0035. Sign-in mode per lab, and owner tools in the admin

- Status: Accepted (owner, 2026-11-17)
- Date: 2026-11-17
- Amends: [0009](0009-two-identity-paths.md) (both identity paths were always on)

## Context
Owner feedback after v0.2.0: adding people and materials one by one is slow, things are hard to
delete, the admin is confusing on first use, and a lab should choose between a shared store-room
tablet and personal phone logins. A review also found that the 14-day return limit was only
applied to the on-screen list, and that there was no way to correct a wrong stock count.

## Decision
- **Lab settings** (one row, edited in the admin): sign in by *shared tablet only*, *personal
  phones only*, or *both* (default). The switched-off path answers 403 with a plain explanation.
- **Spreadsheets**: django-import-export for departments, employees and materials (Excel, CSV,
  and pasted cells from Excel or Google Sheets, which arrive as tab-separated text). Every import
  previews first. Employee rows create missing departments. Stock quantities are never imported
  here: deliveries still go through the stock import, so every change stays in the ledger.
- **Removing things**: "Delete selected" deletes what has no stock history and archives the rest.
  Stock movements are never deleted; a mistake gets **Undo**, which adds a correcting movement.
- **Stock count**: enter what is on the shelf; the difference is computed under the row lock.
- **Setup checklist** on the admin home page, adapted to the sign-in mode; plain labels.
- Returns use the same query for the list and the action, so the 14-day and ownership rules
  can't drift apart again.

## Alternatives considered
- A custom owner website instead of the Django admin: better UX, far more to build and maintain.
- Hard delete with cascades: silently rewrites past reports.
- Google Sheets API integration: needs OAuth and a Google project per lab; pasting covers it.

## Consequences
New dependency (django-import-export). Kiosk pages read one settings row per request.

## Interview angle
"Deletion in a ledger system: delete what has no history, archive what does, and undo mistakes
with a correcting entry, so last month's report never silently changes."
