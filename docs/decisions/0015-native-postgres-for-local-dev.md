# 0015. Portable native PostgreSQL 16 for local development

- Status: Accepted (owner, 2026-11-16)
- Date: 2026-11-16
- Amends: [0003](0003-postgres-everywhere.md) (only the "via docker compose locally" part)

## Context
ADR 0003 planned to run PostgreSQL locally with docker compose. On the development PC (Windows 11
Home) Docker Desktop needs WSL2, which needs admin rights and a restart. The PC already runs an
unrelated PostgreSQL 12 on port 5432, too old for Django 5.2 (needs 14+).

## Decision
Local development uses the official PostgreSQL 16 Windows binaries (zip, no installer, no admin),
initialised under the user's profile and listening on `localhost:5433`. CI keeps the `postgres:16`
service container, and `compose.yaml` stays for anyone who has Docker.
What must match across dev, CI and prod is the **major version (16)**, not the packaging.

## Alternatives considered
- Install WSL2 + Docker Desktop: matches CI exactly, but needs admin and a restart now.
- Official installer as a Windows service: needs admin.
- Hosted Postgres (free tier): no install, but tests depend on the internet.

## Consequences
The server is started by hand (`pg_ctl start`) when working. Docker becomes necessary again in
Phase 9 (production compose), which can be built on a Linux server instead.

## Interview angle
"I kept version parity between dev and CI even when I couldn't keep tooling parity, and wrote down
exactly what I gave up."
