# 0026. Admin two-factor login with a runtime switch

- Status: Accepted (owner, 2026-11-17)
- Date: 2026-11-17

## Context
The admin holds stock, costs, employees and imports, and is reachable from the internet. A
password alone is not enough. Tests and local development must keep using `admin_client` and a
plain password login.

## Decision
- django-otp with TOTP (any authenticator app). `manage.py totp_setup <user>` prints a QR code in
  the terminal; no extra admin screens.
- The default admin site's class is swapped for `KioskAdminSite` (an `OTPAdminSite`) in
  `ops.apps`, so every existing `admin.register()` keeps working.
- `ADMIN_REQUIRE_2FA` is read **at request time**, defaults to `not DEBUG`, so production is
  protected without configuration and development is unchanged.
- Tests switch it off in an autouse fixture; `tests/test_deploy.py` switches it on and checks the
  full login with a real TOTP code.
- A deploy check (`ops.W001`) fails `check --deploy` if someone turns 2FA off in production.
- django-otp 1.7 makes users choose a device before entering a code. With exactly one
  authenticator we choose it for them (`OneStepOTPForm`); with several, the choice stays.

## Alternatives considered
- A second admin site for production only: two URL configs to keep in sync.
- `django-two-factor-auth`: full setup wizard and backup tokens, but many more templates and
  dependencies than a single-lab install needs.
- Environment-only switch in CI: tests would behave differently on a developer machine.

## Consequences
Losing the phone means an operator runs `totp_setup --replace` on the server. No backup codes in
v1.

## Interview angle
"Secure by default, switchable at runtime, enforced by a deploy check, and a library upgrade that
changed the login UX, caught by a test."
