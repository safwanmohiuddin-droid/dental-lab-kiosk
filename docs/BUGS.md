# Bug log

Every real bug, newest first. Write the failing test before the fix.

### 2026-11-17: Stacked PR closed instead of merged
- **Symptom:** after squash-merging PR #2 with "delete branch", PR #3 (Phase 2, based on #2's
  branch) showed CLOSED, and `main` had Phase 1 but not Phase 2.
- **Root cause:** #3's base branch was deleted by the merge before GitHub retargeted the PR, and a
  PR whose base no longer exists is closed. Squash merging also means #2's original commit is not
  in `main`, so #3's branch still carried it.
- **Fix:** `git rebase --onto origin/main <phase-1 commit> phase-2-ledger` replays only the Phase 2
  commit on top of the squashed `main`; tests re-run (49 pass); reopened as a new PR.
- **Test:** none possible; it's a workflow bug. Rule written instead: with stacked PRs, merge the
  first one *without* deleting its branch, let GitHub retarget the next PR, then delete.
- **Lesson:** "Squash merging and stacked branches don't mix by default; `rebase --onto` is how you
  cut a branch loose from a parent that was rewritten."

### 2026-11-17: Two people took the last unit (lost update), reproduced on purpose
- **Symptom:** with the row lock removed, the race test got `['ok', 'ok']`: both technicians
  were given the last disc, and stock no longer matched the ledger.
- **Root cause:** read-check-write without a lock. Both transactions read `qty_on_hand = 1`, both
  passed the "enough stock?" check, both wrote. Postgres' default READ COMMITTED isolation does
  not prevent this.
- **Fix:** `select_for_update()` on the material row before checking (`inventory/services.py`).
  The second request waits, then sees 0 and is refused.
- **Test:** `tests/test_concurrency.py` (a 50 ms pause inside save makes the overlap certain, so
  the test can't pass by luck). Passed 5 runs out of 5 with the lock.
- **Lesson:** "I wrote the failing race test first and watched it fail, so I know the lock is what
  fixes it, not timing."

### 2026-11-17: Checking that the property-based test can actually fail
- **Symptom:** 150 random operation sequences passed in 2.5 s; fast enough to be suspicious.
- **Check:** injected a bug (removed the over-return guard). Hypothesis failed it and shrank the
  case to the minimum: return 0.002 of an issue of 0.001.
- **Fix:** none needed; guard restored.
- **Test:** `tests/test_ledger_properties.py`.
- **Lesson:** "A test you've never seen fail proves nothing. I mutate the code to prove the test
  bites."

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
