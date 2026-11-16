# 0002. Django + HTMX monolith

- Status: Accepted (owner, 2026-11-16)
- Date: 2026-11-16

## Context
One developer. Needs a back office (materials, employees, imports), a mobile kiosk, reports and an
API. Must be easy for strangers to self-host and contribute to.

## Decision
One Django 5.2 LTS project, server-rendered templates, HTMX for partial updates, Tailwind via the
standalone CLI (no Node at runtime). A small amount of plain JS only where the browser must act
alone: camera scanning (ADR 0010) and the offline outbox (ADR 0008).

## Alternatives considered
- Next.js + FastAPI: two languages, two deploys, admin built by hand.
- React SPA + Django REST: state lives in two places; overkill for ~8 screens.

## Consequences
Fast to build, one container, Django admin for free. Offline mode is harder than in an SPA because
HTML comes from the server, accepted, the offline path is narrow (issue only).

## Interview angle
"Choosing boring tech for a solo build, and where I deliberately broke out of it (offline)."
