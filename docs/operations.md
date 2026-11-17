# Operations

How to install, upgrade, back up and restore a production kiosk. Everything runs with Docker
Compose: `web` (Django + gunicorn), `db` (PostgreSQL 16) and `caddy` (HTTPS).

## Requirements
- A Linux server (1 vCPU and 1 GB RAM is enough) with Docker and the Compose plugin.
- A domain name, for example `kiosk.yourlab.com`, whose DNS record points at the server.
- Ports 80 and 443 open to the internet (Caddy needs them to get the HTTPS certificate).

## Install
```bash
git clone https://github.com/safwanmohiuddin-droid/dental-lab-kiosk.git /opt/kiosk
cd /opt/kiosk
cp .env.prod.example .env
nano .env                      # set DOMAIN, SECRET_KEY, POSTGRES_PASSWORD, TIME_ZONE
docker compose -f compose.prod.yaml up -d --build
docker compose -f compose.prod.yaml exec web python manage.py createsuperuser
docker compose -f compose.prod.yaml exec web python manage.py totp_setup <username>
```
`totp_setup` prints a QR code. Scan it with any authenticator app (Google Authenticator,
Microsoft Authenticator, 1Password, Aegis). The admin at `https://<DOMAIN>/admin/` then asks
for the 6-digit code after the password.

Lost phone: `docker compose -f compose.prod.yaml exec web python manage.py totp_setup <username> --replace`.

## Check it is healthy
- `https://<DOMAIN>/healthz` returns `{"status": "ok", "database": "ok"}` (503 if the database is
  down). Point an uptime monitor at it.
- `docker compose -f compose.prod.yaml exec web python manage.py check --deploy` should report no
  issues.
- `docker compose -f compose.prod.yaml exec web python manage.py check_ledger` confirms stock
  matches the ledger.

## Logs
```bash
docker compose -f compose.prod.yaml logs -f web     # app, one JSON object per line
docker compose -f compose.prod.yaml logs -f caddy   # HTTP access log, JSON
```

## Upgrade
```bash
cd /opt/kiosk
./scripts/backup.sh                                  # always back up first
git pull
docker compose -f compose.prod.yaml up -d --build    # migrations run on start
```

## Backups
`scripts/backup.sh` writes `backups/kiosk-<UTC time>.dump` (PostgreSQL custom format) and keeps
the newest 14 (`BACKUP_KEEP` to change). Run it nightly from cron:
```
15 2 * * * cd /opt/kiosk && ./scripts/backup.sh >> backups/backup.log 2>&1
```
A backup on the same disk is not a backup. Copy `backups/` somewhere else (another server,
cloud storage, an external drive) at least weekly.

## Restore drill
Do this once after installing and then every few months, so you know it works before you need
it. CI runs the same steps against every change.

1. Restore into a scratch database and check it has data:
   ```bash
   docker compose -f compose.prod.yaml exec -T db sh -c \
     'createdb -U "$POSTGRES_USER" restore_drill && pg_restore -U "$POSTGRES_USER" -d restore_drill --no-owner' \
     < backups/<file>.dump
   docker compose -f compose.prod.yaml exec db sh -c \
     'psql -U "$POSTGRES_USER" -d restore_drill -c "select count(*) from inventory_stockmove"'
   docker compose -f compose.prod.yaml exec db sh -c 'dropdb -U "$POSTGRES_USER" restore_drill'
   ```
2. Real restore (replaces the live data):
   ```bash
   docker compose -f compose.prod.yaml stop web
   docker compose -f compose.prod.yaml exec -T db sh -c \
     'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
     < backups/<file>.dump
   docker compose -f compose.prod.yaml start web
   docker compose -f compose.prod.yaml exec web python manage.py check_ledger
   ```

## Moving to a new server
Install on the new server (steps above, same `.env`), copy the latest dump across, do the real
restore, then point DNS at the new server.
