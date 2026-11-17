# 0009. Shared device + PIN, and personal login

- Status: Accepted (owner, 2026-11-16), amended by [0035](0035-sign-in-mode-and-owner-tools.md) (labs choose which paths are on)
- Date: 2026-11-16

## Context
Some labs put one tablet in the store room; others want staff to use their own phones.

## Decision
One `Employee` record (name, department, PIN hash, optional link to a Django `User`).
- **Shared device:** an admin registers the device (long-lived signed cookie). On it, employee
  picks their name and enters a 4-6 digit PIN. Session ends after each issue.
- **Personal phone:** employee logs in with username + password once; stays signed in
  (remember-me, 30 days). No PIN needed.
PIN rules: argon2 hash, 5 wrong tries → 15-minute lock per employee, attempts logged.

## Alternatives considered
- Personal login only: forces every technician to manage a password on a shared tablet.
- PIN everywhere: a 4-digit PIN on the open internet is guessable.

## Consequences
PIN login is only allowed from registered devices. Two auth paths to test.

## Interview angle
"Matching authentication strength to the threat: a PIN is fine on a trusted device, not on the
internet."
