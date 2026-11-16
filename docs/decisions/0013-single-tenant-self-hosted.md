# 0013. Single tenant, self-hosted, docker compose

- Status: Accepted (owner, 2026-11-16)
- Date: 2026-11-16

## Context
Open source for any lab. No budget for hosting others' data; a lab does hundreds of moves a day.

## Decision
One lab per install. `docker compose up` runs `web` (gunicorn), `postgres`, `caddy` (HTTPS).
Works LAN-only. Nightly `pg_dump` with a documented, tested restore.
No worker container in v1: imports and reports run in the request (they take seconds).

## Alternatives considered
- Multi-tenant SaaS: tenant isolation, billing, compliance; revisit only with demand.
- Celery/Redis: no job long enough to need it yet.

## Consequences
Upgrades are `docker compose pull && docker compose up -d` (migrations run on start).

## Interview angle
"I sized the architecture to the load, hundreds of writes a day, and wrote down when I'd change it."
