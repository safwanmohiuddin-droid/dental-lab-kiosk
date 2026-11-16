# 0007. Client-generated idempotency keys

- Status: Accepted (owner, 2026-11-16)
- Date: 2026-11-16

## Context
Double taps, flaky Wi-Fi retries and offline sync (ADR 0008) can send the same issue twice.

## Decision
The browser generates a UUIDv4 (`crypto.randomUUID()`) when the confirm screen renders and sends
it with the submit. `stock_move.idempotency_key` has a UNIQUE constraint. On conflict the server
returns the existing move as success. The database, not application code, is the guard.

## Alternatives considered
- Disable the button after click: helps UX, doesn't stop network retries.
- Server-side dedup by (employee, material, qty, minute): blocks legitimate repeat issues.

## Consequences
Every write endpoint accepts a key. Tests must replay the same request and expect one move.

## Interview angle
"Exactly-once is a lie; at-least-once delivery plus an idempotent receiver is what you build."
