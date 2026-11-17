# 0008. Offline mode: PWA outbox, server decides

- Status: Superseded by [0033](0033-online-only.md) (owner, 2026-11-17)
- Date: 2026-11-16

## Context
Store rooms are often basements with no signal. Owner wants offline issuing.

## Decision
The kiosk is a PWA. A service worker caches the kiosk shell and a material list (barcode → name,
unit). Offline issues go into an IndexedDB **outbox** with their idempotency key and client
timestamp. On `online` event or app open (iOS has no Background Sync), the outbox POSTs in order.
The server is authoritative: it records both `client_at` and `server_at`; if an offline issue
would make stock negative it is **accepted and flagged** (the material physically left the
shelf), never rejected. Only issues/returns work offline, not imports or reports.
Offline needs a prior online login on that device (cached employee list with PIN hashes is NOT
shipped to the browser; offline PIN check uses a per-device short-lived token instead, details in
a follow-up ADR when built).

## Alternatives considered
- No offline: simplest; owner chose offline.
- Full offline sync of all data (CRDTs): far beyond need.

## Consequences
The hardest feature in the project. Built LAST in the kiosk phase, behind a setting.
Negative-stock flags need an admin screen.

## Interview angle
"Offline-first with a server-authoritative outbox: why I accept the conflicting write and flag it
instead of rejecting a fact that already happened in the real world."
