# 0003. PostgreSQL in dev, test and prod

- Status: Accepted (owner, 2026-11-16), local-dev part amended by [0015](0015-native-postgres-for-local-dev.md)
- Date: 2026-11-16

## Context
Stock correctness depends on row locks (`SELECT ... FOR UPDATE`). SQLite silently ignores
`select_for_update()`, so tests on SQLite would pass while production races.

## Decision
PostgreSQL 16 everywhere, run via docker compose locally and as a service in CI.

## Alternatives considered
- SQLite for tests: faster, but hides exactly the bug class we care most about.

## Consequences
Docker needed for development. Tests a bit slower.

## Interview angle
"Your test database must have the same concurrency semantics as production, or your race-condition
tests are theatre."
