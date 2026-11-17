# Dental Lab Material Kiosk: Build Plan (v0.3, 2026-11-16)

> Simple product, rigorous process. Every phase ships something usable, teaches one system-design
> idea, and leaves an interview story behind.

## 1. What we are building

**Question the app answers:** *Which department consumes the most material, what does it cost,
and who took it?*

A technician opens the kiosk (shared tablet or own phone), scans a material, types a quantity,
confirms. Ten seconds. The owner sees cost and quantity per department, per item, per person.

### v1 scope (owner-confirmed 2026-11-16)
- Stock in: **Excel import** ([ADR 0006](docs/decisions/0006-stock-in-via-excel.md))
- Issue from kiosk, **phone camera scanning**, USB scanner also works
- **Repeat last issue** (one tap)
- **Returns** to stock
- Optional **case number** on an issue
- ~~Offline mode~~ dropped 2026-11-17: online only with a clear no-connection message (ADR 0033)
- Identity: **shared device + PIN** and **personal login**
- Price optional; quantity always ([ADR 0005](docs/decisions/0005-quantity-first-price-optional.md))
- Reports: by department, by material, by employee, by period; Excel export
- Mobile-first everywhere

### Not in v1 (on purpose)
REST API, webhooks, accounting connectors, multi-tenant, lots/expiry, budgets, alerts.
See §8 backlog.

## 2. Decisions

All in [docs/decisions/](docs/decisions/README.md). Rule: no code that depends on a `Proposed`
ADR until the owner accepts it. Open right now: 0003, 0004, 0007, 0008, 0010-0014.

## 3. The model (target, v1)

```
Department    name, code, active
Employee      name, department→, pin_hash, user→ (nullable, personal login),
              failed_pin_attempts, pin_locked_until, active
Device        name, token_hash, registered_by→, last_seen_at, active
Material      name, barcode (text, unique), unit (pcs/g/ml/disc…), category (text),
              qty_on_hand Decimal(12,3), avg_cost Decimal(14,4) NULL, active
StockMove     kind (receipt|issue|return|adjust), material→, qty Decimal(12,3) signed,
              unit_cost NULL, employee→ NULL, department→ NULL,
              case_ref NULL, returns_move→ NULL, import_batch→ NULL,
              idempotency_key UUID UNIQUE, client_at NULL, created_at, created_by→,
              device→ NULL, flagged (bool), note
ImportBatch   file_name, file_sha256 UNIQUE, status (validated|committed|failed),
              rows_json, errors_json, created_by→, created_at, committed_at
```

DB constraints (not just form validation): `qty <> 0`; issue ⇒ qty < 0 and department NOT NULL;
receipt ⇒ qty > 0; unique barcode; unique idempotency key; return ⇒ returns_move NOT NULL.
Indexes: `(department, created_at)`, `(material, created_at)`, `(employee, created_at)`.

## 4. Screens (mobile-first, max 8)

| URL | Who | What |
|---|---|---|
| `/k/` | kiosk | pick name → PIN (shared) or straight in (personal) |
| `/k/issue/` | kiosk | scan/type barcode → qty → optional case no. → confirm |
| `/k/repeat/` | kiosk | last 5 issues, tap to repeat |
| `/k/return/` | kiosk | my issues (14 days) → return qty |
| `/r/` | owner | dashboard: this month by department (qty, cost, coverage %) |
| `/r/materials/`, `/r/people/` | owner | drill-downs, date range, Excel export |
| `/import/` | owner | upload → preview with row errors → commit |
| `/admin/` | owner | Django admin: materials, employees, devices, adjustments |

Mobile rules: inputs ≥16px (stops iOS zoom), `inputmode="decimal"` for qty, tap targets ≥44px,
one column, works at 360px wide, thumb-reachable confirm button.

## 5. Phases

**Status 2026-11-17: phases 0 to 10 done, v0.1.0.** Phases 4, 5, 6, 7 and 9 were built in
parallel by separate agents in their own git worktrees, coordinated through a pinned GitHub
issue (#6) with one issue per phase, reserved ADR numbers and test databases. Each PR was
rebased, reviewed, checked in a browser and merged only after CI passed on GitHub.

| Phase | PR | What landed |
|---|---|---|
| 4 Identity | #14, #17 | Registered tablets (one-time link, POST to claim), PIN with Argon2 and row-locked lockout, personal login |
| 5 Kiosk | #19 | Scan/type, quantity, case no., confirm, done; repeat; returns; plain CSS + boosted htmx (ADR 0030) |
| 6 Scanner | #18 | `attachScanner()`, native BarcodeDetector or vendored zxing-wasm, no CDN |
| 7 Reports | #15 | Department, material, person; Excel export; 3 queries per page; `created_at` index (150 to 54 ms) |
| 8 Online only | #21 | Offline mode dropped by the owner (ADR 0033); truthful no-connection message |
| 9 Production | #16 | Docker image, Caddy HTTPS, admin and reports behind TOTP 2FA (ADR 0026), healthz, JSON logs, backups, CI image smoke test |
| 10 Launch | this PR | AGPL-3.0, docs, templates, changelog, release workflow publishing to GHCR |

Phase 11 (pilot) is next and needs a real lab.


Each phase: **Build** → **Learn** → **Bugs you will probably hit** → **Interview story** →
**Done when**. Log every real bug in [docs/BUGS.md](docs/BUGS.md).

### Phase 0: Foundations (1-2 days)
**Build:** `uv` project (Python 3.13), Django 5.2; ruff + pre-commit; pytest-django; docker
compose (postgres); `.env` via `django-environ`; GitHub Actions running ruff + migrations check +
tests against a Postgres service; dev commands in README (no task runner, nothing to wrap yet).
Apps are created in the phase that first needs them (`inventory` in Phase 1).
**Learn:** reproducible environments, 12-factor config, CI as the source of truth.
**Bugs:** psycopg can't find libpq on Windows (use `psycopg[binary]`); CRLF line endings fail
pre-commit; tests pass locally, fail in CI because of a timezone or env var.
**Story:** "First commit was CI, not code."
**Done when:** a PR with a failing test goes red in CI.

### Phase 1: Domain model + admin (2-3 days)
**Build:** models from §3 with DB `CheckConstraint`s; admin with search/filter; seed command
`manage.py seed_demo` (3 departments, 10 employees, 30 materials).
**Learn:** data modelling, constraints in the DB vs validation in forms, migrations.
**Bugs:** adding a NOT NULL column to a table with rows (migration needs a default); a
`CheckConstraint` that passes in tests but fails on existing data; `Decimal` vs `float` in
fixtures.
**Story:** "Why I put business rules in the database, not only in Python."
**Done when:** you can't insert an issue without a department, even from `psql`.
**Built (2026-11-17):** `inventory` app with Department, Employee, Material, StockMove; 9 check
constraints, 3 composite indexes, read-only StockMove admin, `seed_demo` (4 departments).
Deferred to the phase that uses them: PIN fields and Device (Phase 4), ImportBatch (Phase 3).
Dropped `StockMove.value`: it is always `qty * unit_cost`, so reports compute it in SQL.

### Phase 2: The ledger service ★ core (3-4 days)
**Build:** `inventory/services.py`: `receive()`, `issue()`, `return_()`, `adjust()`. Each:
`transaction.atomic()` → `select_for_update()` on the material → validate → insert move →
update cache (qty, moving avg cost) → done. `manage.py check_ledger` verifies the invariant.
**Tests:** unit tests per function; **concurrency test** (two threads issue the last unit,
exactly one wins); **property-based test** with Hypothesis (random sequences of moves ⇒
invariant always holds, avg cost never negative); idempotency replay test.
**Learn:** transactions, isolation, pessimistic locking, invariants, property-based testing.
**Bugs:** lost update without the lock (reproduce it first, on purpose!); division by zero in
avg cost when stock hits 0; rounding drift over 1,000 moves; deadlock if two functions lock
materials in different orders (always lock by ascending id).
**Story:** "I wrote a failing race-condition test, then fixed it with row locks."
**Done when:** concurrency + Hypothesis tests green in CI, `check_ledger` reports 0 drift.

**Built (2026-11-17):** `inventory/services.py` (`receive`, `issue`, `return_`, `adjust`) +
`check_ledger`. Average cost rules: a receipt with no cost keeps the average; a receipt into
empty or negative stock takes its own cost (no blend, no divide by zero). Idempotency keys are
checked after the lock and refuse a key reused for a different move. 49 tests: unit, a
deterministic race test (seen failing without the lock), and a Hypothesis test (seen failing on an
injected bug).

### Phase 3: Excel import (2-3 days)
**Build:** template download; upload → parse (openpyxl, `read_only=True`) → validate each row →
preview with row errors → commit in one transaction through `receive()`; SHA-256 dedup.
**Learn:** validate-then-commit, all-or-nothing, idempotency by content hash, untrusted input.
**Bugs:** Excel turns barcode `0629001` into `629001` (read cells as text, warn on numeric
barcodes); `4.999999999` from float cells (`Decimal(str(v))`); empty trailing rows; merged
cells; a 50 MB file (size limit); formulas showing `None` (`data_only=True`).
**Story:** "Excel silently ate my leading zeros. Here's how the preview step caught it."
**Done when:** importing the same file twice is refused; one bad row blocks the whole file.

**Built (2026-11-17):** `inventory/excel_import.py` + `ImportBatch` model. The UI lives in the
Django admin (Stock imports: Add = upload, view = preview, Commit button, template download)
instead of a separate `/import/` page: admin already gives login, permissions and layout, and
this is an owner-only screen. Row keys are `uuid5(batch, row)`, so commit is idempotent per row;
committing twice is a no-op. Numeric barcodes that lost a leading zero are matched back and
explained. 76 tests. Also found and fixed: `TIME_ZONE` semantics (ADR 0016).

### Phase 4: Identity (2 days)
**Build:** device registration (admin generates a one-time link → signed long-lived cookie);
PIN login only on registered devices; argon2; lockout; personal login with remember-me;
`@kiosk_employee_required` decorator.
**Learn:** authentication vs authorization, threat modelling, rate limiting, session security.
**Bugs:** HTMX POSTs fail with 403 (send CSRF via `hx-headers` on `<body>`); session not
rotated after PIN login (session fixation, `cycle_key()`); lockout counter race (update with
`F()` expressions).
**Story:** "Why a 4-digit PIN is fine on a registered tablet and dangerous on the internet."
**Done when:** 5 wrong PINs lock the employee; PIN page returns 403 on an unregistered device.

### Phase 5: Kiosk UI (3-4 days)
**Build:** issue flow with HTMX partials; scanner text field (USB scanner = keyboard + Enter);
repeat-last; returns; optional case no.; `crypto.randomUUID()` idempotency key per confirm
screen; big success/failure screens.
**Learn:** hypermedia-driven UI, progressive enhancement, UX for 10-second tasks.
**Bugs:** scanner's Enter submits the form early; double tap posts twice (key saves you, prove
it in a test); iOS zooms on focus (font-size); back button resubmits (POST-redirect-GET).
**Story:** "Measured issue time on a real phone: from 25 s to 9 s."
**Done when:** a stranger issues an item on a phone without instructions.

### Phase 6: Camera scanning (1-2 days)
**Build:** `BarcodeDetector` with vendored WASM polyfill; Caddy local HTTPS for LAN testing.
**Learn:** browser capability detection, secure contexts, WASM.
**Bugs:** camera blocked on `http://192.168.x.x` (not a secure context); iOS needs `playsinline`
on `<video>`; camera keeps running after scan (stop tracks, battery drain); EAN vs Code 128
format list.
**Story:** "Same feature, three code paths: native, polyfill, hardware scanner."
**Done when:** scans work on an iPhone and an Android phone.

### Phase 7: Reports (2-3 days)
**Build:** dashboard by department (qty, cost, coverage %), top materials, by person, date range
in lab timezone; Excel export of the same queries; simple CSS bar charts (no chart library).
**Learn:** aggregation in SQL (`annotate`/`Sum`/`Coalesce`), query plans (`EXPLAIN ANALYZE`),
indexes, N+1 detection.
**Bugs:** month boundary off by your UTC offset; `SUM` of NULL costs returns NULL; N+1 on employee
names (`select_related`); report slow at 100k moves until the composite index exists.
**Story:** "Seeded 200k moves, report took 2.1 s, an index made it 40 ms. Here's the plan."
**Done when:** dashboard < 200 ms on 200k seeded moves.

### Phase 8: Offline mode (4-6 days, hardest) [DROPPED: online only, ADR 0033]
**Build:** service worker (cache shell + material list); IndexedDB outbox; sync on `online` /
app open; server flags negative stock; admin "flagged moves" list. Per ADR 0008.
**Learn:** PWAs, eventual consistency, conflict resolution, at-least-once delivery.
**Bugs:** old service worker serves stale HTML after deploy (version the cache, `skipWaiting`);
iOS has no Background Sync; outbox replays twice (idempotency key absorbs it); client clock wrong
(store both `client_at` and `server_at`); CSRF token expired while offline.
**Story:** "Why I accept an offline write that breaks an invariant, and flag it instead."
**Done when:** airplane mode → 3 issues → back online → exactly 3 moves, flagged if negative.

### Phase 9: Production hardening (2-3 days)
**Build:** docker compose prod (gunicorn, caddy); `/healthz`; structured JSON logs; optional
Sentry; 2FA on admin (django-otp); nightly `pg_dump` + **restore drill** documented;
`manage.py check --deploy` clean; Dependabot + `pip-audit`.
**Learn:** operations, backups that are actually tested, security headers, observability.
**Bugs:** static files 404 in prod (`collectstatic`/WhiteNoise); `CSRF_TRUSTED_ORIGINS` missing
behind the proxy; migrations racing on container start.
**Story:** "I restored a backup on a fresh VM in 6 minutes, the runbook is in the repo."
**Done when:** a fresh VM goes from zero to running with one command and a restored backup.

### Phase 10: Open-source launch (2 days)
README (problem, 30-s GIF, 5-minute demo), `docs/` (install, hardware, import template, backup),
LICENSE (ADR 0014), CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, issue templates, v0.1.0 release
with a CHANGELOG and published Docker image.
**Done when:** someone who isn't you installs it from the README.

### Phase 11: Pilot (ongoing)
One real lab, 4 weeks. Track: issues/day, median issue time, % with cost, flagged moves, bugs.
Write the results in `docs/PILOT.md`. That's the strongest interview material you'll have.

## 6. Engineering practices (the "how")
- Branch per change off `main`, small PRs to yourself, CI must pass, squash merge.
- Test pyramid: services (most), views (some), one Playwright smoke test per flow (few).
- Every bug: failing test first, then the fix, then a line in `docs/BUGS.md`.
- Every expensive-to-reverse choice: an ADR first.
- Every feature is the smallest change that fully solves it. No code "for later".
- Measure before optimising: seed data, `EXPLAIN ANALYZE`, then index.

## 7. Interview story bank (fill in as you go)
| Topic | Where it comes from |
|---|---|
| Race condition + row locks | Phase 2 |
| Property-based testing an invariant | Phase 2 |
| Idempotency / exactly-once myth | ADR 0007, Phase 5, 8 |
| Untrusted input, all-or-nothing import | Phase 3 |
| Threat modelling PIN vs password | Phase 4 |
| Index + query plan, with numbers | Phase 7 |
| Offline-first, conflict resolution | Phase 8 |
| Tested backups / incident runbook | Phase 9 |
| A decision you reversed (superseded ADR) | docs/decisions |
| Real users changed the design | Phase 11 |

## 8. Backlog: ideas beyond v1
**Insights (cheap, high value):** days-of-stock-left per material (on hand ÷ avg daily use);
unusual-take flag (issue > 3× that person's median for that item); monthly department budgets;
Monday digest email.
**Dental:** remake/waste reason on issues (material lost to remakes per department, labs rarely
measure this); material cost per unit produced (import crowns/aligners made per department);
lot + expiry traceability.
**Thought-provoking:** shelf QR posters instead of labelling every item; NFC tags on bins;
opt-in anonymous benchmark across labs ("your zirconia cost per crown vs median"); photo on
large or unusual issues; read-only REST API + webhooks; accounting journal export.

## 9. Open questions for the owner
1. Accept or change the `Proposed` ADRs (0003, 0004, 0007, 0008, 0010-0013)?
2. License (ADR 0014).
3. Product name.
4. A pilot lab for Phase 11?
