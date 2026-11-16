# Bug log

Every real bug, newest first. Write the failing test before the fix.

### 2026-11-16: CI broke after bumping actions: "unable to find version `v10`"
- **Symptom:** CI failed in 2 s at "Set up job" right after moving off the Node.js 20 warning.
- **Root cause:** I assumed every action publishes a moving major tag (`@v10`). `setup-uv` only
  publishes exact versions, so `@v10` doesn't exist.
- **Fix:** pin both actions to the full commit SHA of a release, with the version in a comment;
  Dependabot opens PRs to update the pins.
- **Test:** the CI run itself.
- **Lesson:** "Tags can move or not exist; a commit SHA can't. Pinning by SHA is also a supply-chain
  defence, and Dependabot keeps the pins from going stale."

### 2026-11-16: Tests error: "PostgreSQL 14 or later is required (found 12.4)"
- **Symptom:** smoke test errored at DB setup; lint and `manage.py check` were green.
- **Root cause:** the machine's existing Postgres is 12.4; Django 5.2 dropped support below 14.
  `manage.py check` doesn't connect to the DB, so it can't catch this.
- **Fix:** portable PostgreSQL 16.14 on port 5433 (ADR 0015); same major version as CI.
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
