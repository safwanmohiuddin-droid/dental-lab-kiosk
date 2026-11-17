#!/bin/sh
set -eu

# shortcut: migrations run on every start; fine with one web container, use a separate
# one-off migrate step if the app is ever scaled to several containers.
python manage.py migrate --noinput

# Access logs come from Caddy (JSON); the app logs JSON to stdout.
exec gunicorn config.wsgi \
    --bind 0.0.0.0:8000 \
    --workers "${WEB_CONCURRENCY:-3}" \
    --timeout 60
