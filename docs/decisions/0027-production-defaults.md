# 0027. Production defaults follow DEBUG; Caddy in front, WhiteNoise for static files

- Status: Accepted (owner, 2026-11-17)
- Date: 2026-11-17

## Context
Self-hosted by labs without an operations team. A missed setting must fail safe, and the dev
setup must not change.

## Decision
- Security settings (`SECURE_SSL_REDIRECT`, secure cookies, HSTS one year with subdomains,
  admin 2FA) default to on whenever `DEBUG` is off; each can be overridden from the environment.
  `/healthz` is exempt from the HTTPS redirect so monitors can use plain HTTP inside the network.
- HSTS preload is not set (`security.W021` silenced): preloading commits the whole parent domain
  and must be the lab's own choice.
- Caddy terminates HTTPS (automatic certificates) and writes JSON access logs; Django trusts
  `X-Forwarded-Proto` from it. The app logs JSON lines to stdout (stdlib formatter, no
  dependency); gunicorn's own access log is off to avoid duplicates.
- WhiteNoise serves static files, compressed but **not** hash-named: hash-named files need
  `collectstatic` before every test run. Browsers re-check static files every 60 s instead.
- The web container runs migrations on start (one web container, so no race).

## Alternatives considered
- nginx: one more config file and container for no gain at this size.
- Separate `settings/production.py`: two files drift; env overrides do the same job.

## Consequences
`check --deploy` is part of CI against the real container, so a regression fails the build.

## Interview angle
"Fail-safe defaults keyed off one switch, verified by `check --deploy` inside the built image."
