# Bug log

Every real bug, newest first. Write the failing test before the fix.

### 2026-11-17: An older report answer overwrote a newer one
- **Symptom:** in the browser, two quick dropdown changes left "per Whole period" selected but a
  weekly chart on screen.
- **Root cause:** each change sent a request; the first answer arrived last and replaced the
  second. Out-of-order responses.
- **Fix:** `hx-sync="this:replace"`: a newer change cancels the request still in flight (the
  network log shows the older one as aborted).
- **Test:** `test_builder_updates_live_without_a_show_button` checks the attribute; the race was
  reproduced and re-checked in a real browser.
- **Lesson:** "Any live-updating UI needs a rule for which answer wins. The latest request should,
  not the latest response."

### 2026-11-17: A page-transition effect could block a data update
- **Symptom:** after the race fix, the report sometimes didn't update at all; the console said
  "Transition was aborted because of timeout in DOM update".
- **Root cause:** htmx wraps the swap in the browser's View Transitions API; when the transition
  times out, the swap is skipped and old data stays on screen.
- **Fix:** removed View Transitions; motion is CSS on the new content, which can't block the swap.
- **Test:** browser re-check: dropdowns, address, chart type and headline all agree.
- **Lesson:** "Decoration must never be able to block data."

### 2026-11-17: A link that set only some report choices silently showed the default report
- **Symptom:** `/r/?period=last_month` showed this month.
- **Root cause:** missing choices made the whole form invalid, so it fell back to the defaults.
- **Fix:** defaults are merged in per field before validation.
- **Test:** `test_presets_cover_last_month` (failed before the fix).
- **Lesson:** "Partial input should degrade per field, not all at once."

### 2026-11-17: An always-on confirm screen was friction, not safety
- **Symptom:** owner feedback: too many clicks. Every take had a confirm screen, so people learn
  to tap through it, which is exactly when it stops preventing mistakes.
- **Root cause:** safety applied uniformly instead of where errors happen.
- **Fix:** take in one step; ask again only when the amount is over 3x that person's usual
  (median of their last 10). The second look keeps the same request key, so it records once.
- **Test:** `test_unusual_amount_asks_again_then_takes_once`, `test_usual_amount_does_not_ask`.
- **Lesson:** "A confirmation people see every time is noise. Put the check where the risk is."

### 2026-11-17: Admin actions only appear when a list has rows
- **Symptom:** a new test for the action buttons failed on an empty list.
- **Root cause:** Django hides the actions bar when there is nothing to act on; the test had no rows.
- **Fix:** the test creates a department first. The behaviour was right; the test was wrong.
- **Test:** `test_admin_actions_are_buttons`.
- **Lesson:** "When a test fails, check the test's assumptions before changing the code."

### 2026-11-17: The 14-day return limit could be bypassed
- **Symptom:** found when the owner asked "can users return something later?": a hand-made POST could return an issue from months ago.
- **Root cause:** the limit lived in the query for the on-screen list; the return action looked the issue up with a different query that only checked ownership.
- **Fix:** the action uses the same `_returnable()` query as the list.
- **Test:** `test_old_issue_cannot_be_returned_by_posting_directly` (failed before the fix).
- **Lesson:** "When a rule appears in two queries, one day they disagree. Make the action use the list's query."

### 2026-11-17: Owner feedback: the admin was a developer's tool
- **Symptom:** one-by-one data entry, hard deletes blocked by a confusing "no permission to delete stock move" page, no idea where to start.
- **Root cause:** the admin was built to protect the ledger, not to be used by an owner on day one.
- **Fix:** spreadsheet import/export with paste, delete-or-archive, undo, stock count, setup checklist, sign-in mode (ADR 0035).
- **Test:** `tests/test_admin_tools.py`; every screen tried in a browser.
- **Lesson:** "Correct is not the same as usable. Real users find the second kind of bug."

### 2026-11-17: I assumed import previews might write to the database
- **Symptom:** I set `IMPORT_EXPORT_USE_TRANSACTIONS = True` to stop previews creating departments, then a mutation check (setting it to False) still passed.
- **Root cause:** django-import-export always wraps a dry run in a rolled-back transaction (`use_transactions or dry_run`). My setting changed nothing.
- **Fix:** removed the setting; kept a test that previews create nothing, as a guard against a future library change.
- **Test:** `test_import_preview_creates_nothing`.
- **Lesson:** "A mutation check that can't fail tells you the code you added does nothing. Read the library before adding a guard."

### 2026-11-17: The setup checklist squeezed into one letter per line on a phone
- **Symptom:** "How people sign in" rendered as H / o / w down the page at 335 px wide.
- **Root cause:** a three-column table in a narrow viewport.
- **Fix:** a plain list that wraps.
- **Test:** checked at 375 px: no horizontal scroll.
- **Lesson:** "Tables are for comparing rows, not for laying out instructions."

### 2026-11-17: Backups were readable and lived on the same disk
- **Symptom:** found in a security review after v0.1.0, prompted by a post warning that generated apps skip secrets and backup hygiene.
- **Root cause:** `backup.sh` wrote plain `pg_dump` files next to the database. A dead disk loses both; a stolen server exposes every backup.
- **Fix:** encrypt to an age public key (the server can't read its own backups), refuse to run without one, optional rclone off-site copy with a warning when missing (ADR 0034).
- **Test:** CI restore drill: refused without a key, no readable data in the file, decrypt with the private key, restore.
- **Lesson:** "Security reviews belong after a release too; the gaps were exactly the things nobody had asked for."

### 2026-11-17: `! grep` would never have failed the CI step
- **Symptom:** caught while writing the CI check that the backup contains no readable data.
- **Root cause:** bash ignores `set -e` for a command starting with `!`, so `! grep -q secret file` passes even when the secret is there. Proved with `bash -ec '! true; echo reached'`.
- **Fix:** negative checks written as `if grep -q ...; then exit 1; fi`.
- **Test:** the CI step itself.
- **Lesson:** "A test that can't fail is worse than no test, because it looks like coverage."

### 2026-11-17: A failed backup left a half-written file every night
- **Symptom:** a local test with stand-in `docker` and `age` commands: the failing dump stopped the script (good) but left `kiosk-...dump.age.part` behind.
- **Root cause:** `set -e` exits before the cleanup line.
- **Fix:** `trap 'rm -f "$file.part"' EXIT`.
- **Test:** stub run of a failing and a good dump; CI drill.
- **Lesson:** "Cleanup that must always happen goes in a trap, not after the work."

### 2026-11-17: Rotating the secret key would have unregistered every tablet
- **Symptom:** found while documenting key rotation.
- **Root cause:** tablet cookies are signed with `SECRET_KEY`; a new key invalidates them all.
- **Fix:** `SECRET_KEY_FALLBACKS` from the environment for a grace period.
- **Test:** `test_rotating_the_secret_key_keeps_tablets_registered` (works with the fallback, stops after).
- **Lesson:** "Know everything your secret key signs before you change it."

### 2026-11-17: A template comment printed on screen, then the page lost all styling
- **Symptom:** raw comment text at the top of every kiosk page; after one click the page went unstyled.
- **Root cause:** Django's `{# #}` comments are single-line. A two-line one rendered as text inside `<head>`; browsers close `<head>` at the first text, so the CSS and script tags fell into `<body>`, and the next boosted htmx swap replaced the body and removed them.
- **Fix:** `{% comment %}` block.
- **Test:** `test_no_template_comment_leaks_into_the_page` (fails on the old template).
- **Lesson:** "One bug, two symptoms. The screenshot showed the first; inspecting `document.head` explained the second."

### 2026-11-17: Cost reports opened with a kiosk password alone
- **Symptom:** found in review while merging Phase 9: `/r/` only checked login and permission.
- **Root cause:** Phase 7 (reports) and Phase 9 (admin 2FA) were built in parallel; neither owned the gap between them. A user signed in through the kiosk's personal login (password only) could read cost data.
- **Fix:** reports use the admin site's own `has_permission` (staff, and TOTP-verified when 2FA is on). The first attempt passed `admin.site.has_permission` to `user_passes_test`, which hands it a user, not a request: 13 tests failed; replaced with a small wrapper.
- **Test:** `test_kiosk_login_alone_does_not_open_reports`, `test_reports_need_2fa_when_the_admin_does` (both fail on the old gate).
- **Lesson:** "Parallel teams produce gaps between their specs. Review the seams, not just each piece."

### 2026-11-17: Endless redirect between /k/ and /k/home/
- **Symptom:** an admin opening the kiosk bounced between two pages forever.
- **Root cause:** `start` sent a signed-in user without a registered device to `home`; `employee_required` sent anyone who isn't an employee back to `start`. The Phase 4 test asserted the first redirect and never followed it.
- **Fix:** the decorator shows a 403 "not linked to an employee" page in that case.
- **Test:** regression test, plus the old test corrected to the right behaviour.
- **Lesson:** "A redirect test must check where the chain ends, not just the first hop."

### 2026-11-17: Parallel wrong PIN guesses beat the lockout (reproduced on purpose)
- **Symptom:** 8 simultaneous wrong guesses were all checked against a limit of 5.
- **Root cause:** read-then-increment: every request read the counter before the others wrote it. `F()` fixes lost increments but not the check-then-act gap.
- **Fix:** `select_for_update()` on the employee row for the whole attempt.
- **Test:** `test_parallel_wrong_guesses_cannot_exceed_the_limit`.
- **Lesson:** "A lockout counter is a race condition, just like stock."

### 2026-11-17: Registration links would have been used up by chat previews (avoided by design)
- **Symptom:** none in practice; found while designing.
- **Root cause:** WhatsApp and other apps fetch a link to build a preview. If GET registered the device, the preview bot would burn the one-time link.
- **Fix:** GET shows a confirm button; only POST registers.
- **Test:** `test_opening_the_link_does_not_use_it_up`.
- **Lesson:** "Safe methods must be safe: anything can GET your URL."

### 2026-11-17: `str.isdigit()` accepted Arabic-Indic digits as a PIN
- **Symptom:** "١٢٣٤" passed the PIN check.
- **Root cause:** `isdigit()` is true for every Unicode digit.
- **Fix:** PINs must match `[0-9]{4,6}`.
- **Test:** `test_pin_must_be_4_to_6_ascii_digits`.
- **Lesson:** "Validation should name the exact characters it accepts."

### 2026-11-17: "Only 1E+1 disc in stock"
- **Symptom:** stock messages printed 10 as `1E+1`.
- **Root cause:** `Decimal("10.000").normalize()` is `1E+1`; tests only used 3 and 0.001.
- **Fix:** `services.plain()` formats with `:f`.
- **Test:** regression test, seen failing on the old code.
- **Lesson:** "Test round numbers; `normalize()` is not a formatter."

### 2026-11-17: htmx hid error pages and ignored `<meta refresh>`
- **Symptom:** the 403 "PIN locked" page would never appear; the done screen never returned to the start.
- **Root cause:** htmx 2 does not swap 4xx/5xx responses by default, and browsers ignore `<meta refresh>` inside a swapped body.
- **Fix:** `responseHandling` in an `htmx-config` meta tag; the return timer moved to `kiosk.js`.
- **Test:** kiosk screen tests; checked in the browser.
- **Lesson:** "Know what your framework does with error responses."

### 2026-11-17: `Sum(F("qty") * F("unit_cost"))` raised "is an aggregate"
- **Symptom:** every report query failed.
- **Root cause:** annotations named `qty` and `cost` shadowed the model fields, so `F("qty")` resolved to the aggregate.
- **Fix:** annotations renamed `net_qty` and `net_cost`.
- **Test:** all of `tests/test_reports.py`.
- **Lesson:** "Never name an annotation after a model field; F() looks up annotations first."

### 2026-11-17: The dashboard scanned the same 200k rows five times
- **Symptom:** 178 ms for this month, 494 ms for 12 months.
- **Root cause:** five aggregate queries, each a full scan, and no index starting with `created_at`.
- **Fix:** three queries instead of five; `Index(created_at)` added (measured 150 to 54 ms for this month).
- **Test:** `test_dashboard_query_count_does_not_grow_with_rows`; timings and `EXPLAIN ANALYZE` in PR #15.
- **Lesson:** "Measure first. The cheapest fix was asking the database fewer questions."

### 2026-11-17: django-otp 1.7 refused a correct 2FA code
- **Symptom:** admin login with a valid TOTP code stayed on the login page: "Please select a device".
- **Root cause:** django-otp 1.7 requires an explicit device choice.
- **Fix:** the login form picks the device when the user has exactly one.
- **Test:** end-to-end admin login test with a real TOTP code.
- **Lesson:** "Read the changelog of security libraries."

### 2026-11-17: CI never ran on a pull request
- **Symptom:** a PR showed no checks at all.
- **Root cause:** another phase merged first and the PR became conflicting; GitHub does not run `pull_request` workflows when it can't build a merge commit.
- **Fix:** rebase onto `main`, regenerate `uv.lock` with `uv lock` instead of trusting a text merge.
- **Test:** the CI run itself.
- **Lesson:** "No checks is not the same as green checks."

### 2026-11-17: Production defaults would have broken every test in CI
- **Symptom:** caught before pushing: with `DEBUG` off, the test client got HTTPS redirects and 2FA login redirects.
- **Root cause:** CI runs with `DEBUG` off, which turns on `SECURE_SSL_REDIRECT` and admin 2FA.
- **Fix:** an autouse test fixture turns both off; `tests/test_deploy.py` turns them back on and checks them.
- **Test:** `tests/test_deploy.py`; suite run locally with `DEBUG=False`.
- **Lesson:** "Run your tests the way CI runs them."

### 2026-11-17: Our own formatters would have corrupted vendored files
- **Symptom:** pre-commit rewrote the minified polyfill and htmx, and rejected the 946 KB wasm.
- **Root cause:** whitespace and end-of-file hooks treat vendored files like ours.
- **Fix:** pre-commit `exclude: '/vendor/'` and `**/vendor/** -text` in `.gitattributes`; a test checks the wasm hash.
- **Test:** `tests/test_scanner.py`.
- **Lesson:** "Vendored code must stay byte-identical so it can be verified."

### 2026-11-17: Camera left running after Cancel
- **Symptom:** found in code review before any phone test.
- **Root cause:** the stream was dropped without stopping its tracks when Cancel was pressed while `getUserMedia` was pending, or when the reader failed to load.
- **Fix:** keep the stream as soon as it exists and stop its tracks on every exit path.
- **Test:** headless browser test with a fake camera.
- **Lesson:** "Every resource acquired before an `await` needs a release on every path after it."

### 2026-11-17: Shared git refs between worktrees nearly deleted the reports app
- **Symptom:** a squashed commit for Phase 5 removed `reports/`; caught in `git status` before pushing.
- **Root cause:** worktrees share remote-tracking refs. Another worktree fetched mid-squash, so `reset --soft origin/main` landed on a newer `main`.
- **Fix:** redone on an explicit base commit, then rebased.
- **Test:** none possible (workflow).
- **Lesson:** "When others fetch, reset to an explicit SHA, never to a moving ref."

### 2026-11-17: One unexplained test failure under heavy load
- **Symptom:** one full run out of 9 failed one test; never reproduced, including 12 runs of the race tests.
- **Root cause:** unknown. Four agents were loading the same machine (runs took 2.5 to 14 s). Most likely a timing-sensitive concurrency test.
- **Fix:** none yet; every CI run since has been green.
- **Test:** the race and property tests.
- **Lesson:** "Write down what you don't understand, too."

### 2026-11-17: Admin showed 6:54 a.m. for something done at 10:54
- **Symptom:** first browser test of the import screen showed UTC times to a user in UTC+4.
- **Root cause:** my mental model was wrong. I kept `TIME_ZONE = "UTC"` thinking it controlled
  storage. With `USE_TZ = True` storage is always UTC; `TIME_ZONE` only controls display and
  where a day or month starts.
- **Fix:** `TIME_ZONE` comes from `.env` per install (ADR 0016, superseding part of 0012).
- **Test:** checked in the browser; Phase 7 adds a month-boundary test with a non-UTC zone.
- **Lesson:** "Unit tests passed; only a real screen showed the wrong time. Always look at the UI."

### 2026-11-17: A Commit button that would have silently done nothing
- **Symptom:** caught while writing the template: the commit `<form>` was going into a template
  block that renders *inside* the admin's own `<form>`.
- **Root cause:** HTML forbids nested forms; browsers drop the inner `<form>` tag without an
  error, so the button would point at a form that doesn't exist.
- **Fix:** render the commit form after the admin form and link the button with `form="..."`.
  Clicked in a real browser: POST, redirect, 3 rows imported.
- **Test:** `test_admin_upload_preview_and_commit` covers the endpoint; the HTML structure was
  verified in the browser.
- **Lesson:** "Read the framework's template before overriding a block; where it renders matters."

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
