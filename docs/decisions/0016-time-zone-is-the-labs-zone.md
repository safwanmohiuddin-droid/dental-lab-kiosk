# 0016. Django's TIME_ZONE is the lab's time zone

- Status: Accepted (owner, 2026-11-17)
- Date: 2026-11-17
- Supersedes: the time-zone part of [0012](0012-time-and-numbers.md)

## Context
ADR 0012 kept `TIME_ZONE = "UTC"` and planned a separate `LAB_TIMEZONE` setting for reports. The
first browser test showed an import created at 10:54 local time as "6:54 a.m.". The assumption
behind 0012 was wrong: with `USE_TZ = True`, Django always stores UTC in Postgres
(`timestamptz`), whatever `TIME_ZONE` says. `TIME_ZONE` only decides how times are shown and
where "today" and "this month" start.

## Decision
`TIME_ZONE` is set per install from the environment (`TIME_ZONE=Asia/Dubai`, default `UTC`).
No separate `LAB_TIMEZONE`. Storage stays UTC. Reports use Django's own time-zone-aware date
functions (`TruncMonth`, `timezone.localdate()`), which follow `TIME_ZONE`.

## Alternatives considered
- Keep UTC and convert in every report and template: more code, and the admin would still show
  UTC to users.
- Per-user time zones: one lab sits in one place; not needed.

## Consequences
One less setting. The month-boundary test in Phase 7 must run with a non-UTC `TIME_ZONE`.

## Interview angle
"I had the model of `TIME_ZONE` wrong; a real screen caught it. Storage is UTC either way; the
setting is about presentation and calendar boundaries."
