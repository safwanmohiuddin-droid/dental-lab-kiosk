# 0033. Online only: no offline mode

- Status: Accepted (owner, 2026-11-17)
- Date: 2026-11-17
- Supersedes: [0008](0008-offline-outbox.md)

## Context
ADR 0008 planned a PWA with an offline outbox for store rooms without signal. It was the
hardest feature in the plan (service worker, IndexedDB, sync, conflict flags). The owner decided
the kiosk only needs to work with a connection (WiFi or mobile data), with no network
restriction.

## Decision
No service worker, no outbox. When a kiosk request gets no answer (network error, or 15 s
timeout), the page shows: "No connection. Check the WiFi and press the button again; it will not
be recorded twice."
The message does not claim "nothing was saved": the connection can drop after the server saved
the issue but before the phone heard back. Pressing again is safe because the form keeps the
same request key and the server returns the move it already recorded (ADR 0007).
`issue(..., allow_negative=True)` and `StockMove.flagged` stay: they are tiny, tested, and the
admin can still record a late paper slip that takes stock below zero.

## Alternatives considered
- Offline outbox (ADR 0008): large and hard to get right; not needed for this owner.
- "Nothing was saved" wording: simpler, but can be false.

## Consequences
Phase 8 shrinks to a few lines of JavaScript. A store room with no signal needs WiFi coverage.

## Interview angle
"I dropped the hardest feature once the owner confirmed it wasn't needed, and the error message
stays truthful because of idempotency keys built earlier."
