# Architecture Decision Records

One file per decision. Never edit an accepted ADR's decision, write a new ADR that supersedes it
and link both ways. That history is the point: it shows *why* the system looks the way it does.

Status: `Proposed` (my default, waiting on owner) · `Accepted` · `Superseded by NNNN` · `Rejected`

| # | Decision | Status |
|---|---|---|
| [0001](0001-record-decisions.md) | Record decisions as ADRs | Accepted |
| [0002](0002-django-htmx-monolith.md) | Django + HTMX monolith | Accepted |
| [0003](0003-postgres-everywhere.md) | PostgreSQL in dev, test and prod | Accepted, amended by 0015 |
| [0004](0004-append-only-ledger.md) | Append-only stock ledger with cached balance | Accepted |
| [0005](0005-quantity-first-price-optional.md) | Quantity is primary, price optional | Accepted |
| [0006](0006-stock-in-via-excel.md) | Stock in via staged Excel import | Accepted |
| [0007](0007-client-idempotency-keys.md) | Client-generated idempotency keys | Accepted |
| [0008](0008-offline-outbox.md) | Offline mode: PWA outbox, server decides | Superseded by 0033 |
| [0009](0009-two-identity-paths.md) | Shared device + PIN, and personal login | Accepted |
| [0010](0010-camera-scanning.md) | Camera scanning: native API + WASM fallback | Accepted |
| [0011](0011-returns.md) | Returns credit the department at issue cost | Accepted |
| [0012](0012-time-and-numbers.md) | UTC storage, lab-timezone reports, Decimal only | Accepted, time zone part superseded by 0016 |
| [0013](0013-single-tenant-self-hosted.md) | Single tenant, self-hosted, docker compose | Accepted |
| [0014](0014-license.md) | License: AGPL-3.0 | Accepted |
| [0015](0015-native-postgres-for-local-dev.md) | Portable native PostgreSQL 16 for local dev | Accepted |
| [0016](0016-time-zone-is-the-labs-zone.md) | Django TIME_ZONE is the lab's time zone | Accepted |
| [0026](0026-admin-2fa.md) | Admin two-factor login with a runtime switch | Accepted |
| [0027](0027-production-defaults.md) | Production defaults follow DEBUG; Caddy, WhiteNoise | Accepted |
| [0030](0030-plain-css-and-boosted-htmx.md) | Plain CSS and a boosted htmx kiosk | Accepted |
| [0033](0033-online-only.md) | Online only: no offline mode | Accepted |

Numbers 0017-0025, 0028-0029, 0031-0032 and 0034-0035 were reserved for parallel phases and not used.

Template: [0000-template.md](0000-template.md)
