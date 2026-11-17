# 0012. UTC storage, lab-timezone reports, Decimal only

- Status: Accepted (owner, 2026-11-16), time-zone part superseded by [0016](0016-time-zone-is-the-labs-zone.md)
- Date: 2026-11-16

## Context
"This month's cost per department" depends on where midnight is. Floats can't represent money
or 0.1 g exactly.

## Decision
- `USE_TZ = True`; store UTC; one `LAB_TIMEZONE` setting; all period filters convert lab-local
  boundaries to UTC before querying.
- Quantities `Decimal(12,3)` (grams, ml, fractions of a disc). Money `Decimal(14,4)` stored,
  rounded to 2 only for display. Never `float`, enforced by a test that scans model fields.

## Alternatives considered
- Store local time: breaks on any server move or DST region.

## Consequences
Every report takes a lab-local date range. Excel import converts numbers via `Decimal(str(x))`.

## Interview angle
"The month-boundary bug: an issue at 01:00 local showed up in the previous month."
