# Bug log

Every real bug, newest first. Write the failing test before the fix.

### 2026-11-16: Tests error: "PostgreSQL 14 or later is required (found 12.4)"
- **Symptom:** smoke test errored at DB setup; lint and `manage.py check` were green.
- **Root cause:** the machine's existing Postgres is 12.4; Django 5.2 dropped support below 14.
  `manage.py check` doesn't connect to the DB, so it can't catch this.
- **Fix:** run Postgres 16 locally (same as CI and prod, ADR 0003).
- **Test:** `tests/test_smoke.py::test_database_is_postgres` hits the DB on every run.
- **Lesson:** "Green static checks don't prove the environment works: one test must touch real
  infrastructure, and dev must match CI's versions."

## Template
### YYYY-MM-DD: short title
- **Symptom:** what you saw
- **Root cause:** why it happened
- **Fix:** commit / PR
- **Test:** the test that now guards it
- **Lesson:** one line you'd say in an interview
