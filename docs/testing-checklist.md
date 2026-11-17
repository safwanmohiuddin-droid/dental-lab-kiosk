# Hands-on testing checklist

Use the **demo** server (fake data and demo logins) so nothing real changes:

```bash
$env:DATABASE_URL = 'postgres://kiosk:kiosk@localhost:5433/kiosk'; python -m uv run python manage.py runserver 8010
```

Demo logins: owner `owner` / `kiosk-demo`, technician `aisha` / `kiosk-demo`, tablet PIN `1234` for
every demo employee. `python -m uv run python manage.py seed_demo` (with the same `DATABASE_URL`)
resets the logins and prints a new tablet registration link.

Tips:
- Owner in a normal window, technician in a **private window**, so the logins don't collide.
- Press **F12, then Ctrl+Shift+M** in Edge or Chrome and pick a phone to see the phone layout.
- Write down anything confusing, not only what's broken. Each line: what you did, what you
  expected, what happened.

## 1. Owner setup (normal window, http://127.0.0.1:8010/admin/)
- [ ] Home page shows the "Getting started" checklist; done steps have a tick.
- [ ] **Lab settings**: switch to "Shared tablet only", then "Personal phones only", then back to
      "Both". Note what each one does in sections 2 and 3.
- [ ] **Employees, Import**: paste these cells (copy from a spreadsheet, or type with Tab between
      columns), check the preview, confirm:
      `name / department / active` then `Test Person / Implants / 1`.
      The new department "Implants" appears.
- [ ] Same file or paste again: shows "0 new, 0 updated" or skips, never duplicates.
- [ ] **Materials, Export**: downloads a spreadsheet you can open.
- [ ] **Stock imports, Add**: download the template, add 2 rows (one existing barcode, one new
      code with a name), tick "create unknown materials", upload. Preview, then Commit.
- [ ] Upload the same file again: refused with a link to the first import.
- [ ] Put `12345678905` in the barcode column as a number: the preview explains the lost zero.
- [ ] **Materials**: click **Correct count** on one; enter a different number; stock changes and a
      correction appears under Stock movements.
- [ ] **Delete**: tick a material nobody has taken plus one with history; press "Delete selected":
      the first disappears, the second is archived. **Restore selected** brings it back.
- [ ] **Stock movements**: tick a wrong issue, **Undo selected**: stock goes back. Undo again:
      nothing changes twice.

## 2. Shared tablet (private window)
- [ ] Open the registration link printed by `seed_demo`, press Register.
- [ ] "Who are you?": type part of a name; the list filters. People who took something
      recently are at the top.
- [ ] Pick someone; the PIN pad appears. Tap `1 2 3 4`, Sign in.
- [ ] Wrong PIN 5 times on one person: locked for 15 minutes. Owner: Employees, tick them,
      **Unlock PIN sign-in**; they can sign in again.
- [ ] Scan or type `200000000011`, press Enter: material and shelf stock appear.
- [ ] Use **+** and **−**; the button text follows ("Take 3 disc").
- [ ] Add a case number, Take. Done screen shows the amount; the bar drains and the tablet
      returns to "Who are you?" after 5 seconds.
- [ ] Take more than is on the shelf: refused with how many are left.

## 3. Personal phone (private window, http://127.0.0.1:8010/)
- [ ] Sign in as `aisha` / `kiosk-demo`.
- [ ] Take the same material 3 times with small amounts (1 each).
- [ ] Then try 10: "That's more than usual" appears. **Change the amount** goes back;
      **Yes, take** records it once.
- [ ] Double tap Take quickly: only one record (check Stock movements as owner).
- [ ] "Your usual" lists your recent items; tapping one pre-fills the amount.
- [ ] **Return something**: return part of an issue; try to return more than you took: refused.
- [ ] Switch the lab to "Shared tablet only" (as owner): the phone login now says to use the
      tablet. Switch back.

## 4. Reports (owner, http://127.0.0.1:8010/r/)
- [ ] The headline names the department that used the most.
- [ ] Quick periods (This week, This month, Last month, Last 12 months) change the numbers;
      the active one is highlighted.
- [ ] Your takes from sections 2 and 3 appear under the right department and person.
- [ ] "Download as Excel" opens in Excel.
- [ ] Signed in as `aisha` only, open `/r/`: sent to the admin login. Technicians can't see costs.

## 5. Try to break it
- [ ] Stop the server (Ctrl+C) and press a kiosk button: "No connection" message. Start it, press
      again: works, recorded once.
- [ ] Quantities like `0`, `-1`, `abc`, `1.2345`: each refused with a message.
- [ ] Unknown barcode: explained, nothing recorded.
- [ ] Phone size (F12, Ctrl+Shift+M): no page scrolls sideways; every button is easy to tap.

## 6. Automated checks (anyone can run)
```bash
python -m uv run pytest
```
228 tests should pass. CI runs the same tests plus a Docker build, HTTPS, and a backup restore on
every pull request.
