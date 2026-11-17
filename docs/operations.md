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
chmod 600 .env                 # holds the secret key and DB password: owner-only
nano .env                      # set DOMAIN, SECRET_KEY, POSTGRES_PASSWORD, TIME_ZONE, BACKUP_*
apt install -y age rclone      # backup encryption and the off-site copy
docker compose -f compose.prod.yaml up -d --build
docker compose -f compose.prod.yaml exec web python manage.py createsuperuser
docker compose -f compose.prod.yaml exec web python manage.py totp_setup <username>
```
`totp_setup` prints a QR code. Scan it with any authenticator app (Google Authenticator,
Microsoft Authenticator, 1Password, Aegis). The admin at `https://<DOMAIN>/admin/` then asks
for the 6-digit code after the password.

Lost phone: `docker compose -f compose.prod.yaml exec web python manage.py totp_setup <username> --replace`.

## First day setup
All in the admin at `https://<DOMAIN>/admin/`.

1. **Departments**: add one per department (for example CAD/CAM, Ceramics, Model Room).
2. **Employees**: add each technician with their department, then set a 4 to 6 digit PIN on
   their page. Staff who will use their own phone also need a user account, linked on the
   employee page (field "User").
3. **Stock**: Inventory, Stock imports, Add. Download the template, fill it in, upload, check
   the preview, press Commit. See [stock-import.md](stock-import.md).
4. **Store-room tablet**: Kiosk, Devices, Add. The admin shows a one-time link (valid 24 hours).
   Open it on the tablet and press "Register this device". From then on the tablet shows
   "Who are you?" at `https://<DOMAIN>/k/`.
5. **Labels**: print a barcode label (Code 128 or EAN-13) for every material without one; the
   number must match the barcode column of the import.

Staff phones: open `https://<DOMAIN>/k/` and sign in with the linked user account.
Reports: `https://<DOMAIN>/r/` (staff with two-factor login).

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
Each release is also published as a ready-made image, `ghcr.io/safwanmohiuddin-droid/dental-lab-kiosk:<version>`; the compose file builds from source by default.

```bash
cd /opt/kiosk
./scripts/backup.sh                                  # always back up first
git pull
docker compose -f compose.prod.yaml up -d --build    # migrations run on start
```

## Backups
Backups are encrypted with a public key (ADR 0034). The server can write them but never read
them, so a stolen server or a leaked bucket gives nothing away.

**Once, on your own computer (not the server):**
```bash
age-keygen -o kiosk-backup-key.txt     # prints "Public key: age1..."
```
Put the `age1...` public key in the server's `.env` as `BACKUP_AGE_RECIPIENT`. Keep
`kiosk-backup-key.txt` **off the server**: in a password manager and on a USB stick in a drawer.
Without it no backup can ever be restored; with it, anyone can read them.

**Off-site copy** (strongly recommended): configure an rclone remote on the server
(`rclone config`, for example Backblaze B2, S3 or Google Drive) and set
`BACKUP_RCLONE_REMOTE=<remote>:<bucket>/kiosk`. Every backup is copied there; set the bucket's own
lifecycle rule to delete files older than, say, 90 days. Without a remote the script warns on every
run: a dead disk takes the database and its backups together.

**Nightly**, from cron:
```
15 2 * * * cd /opt/kiosk && ./scripts/backup.sh >> backups/backup.log 2>&1
```
`backups/kiosk-<UTC time>.dump.age` is written and the newest 14 are kept (`BACKUP_KEEP`). The
script refuses to run without `BACKUP_AGE_RECIPIENT`, leaves nothing behind when a dump fails, and
warns if `.env` is readable by other users. Read `backups/backup.log` now and then.

## Restore drill
Do this once after installing and then every few months, so you know it works before you need
it. CI runs the same steps against every change. You need the private key file.

1. Decrypt the backup on a machine that has the key, then copy `restored.dump` to the server:
   ```bash
   age --decrypt -i kiosk-backup-key.txt kiosk-<time>.dump.age > restored.dump
   ```
2. Restore into a scratch database and check it has data:
   ```bash
   docker compose -f compose.prod.yaml exec -T db sh -c \
     'createdb -U "$POSTGRES_USER" restore_drill && pg_restore -U "$POSTGRES_USER" -d restore_drill --no-owner' \
     < restored.dump
   docker compose -f compose.prod.yaml exec db sh -c \
     'psql -U "$POSTGRES_USER" -d restore_drill -c "select count(*) from inventory_stockmove"'
   docker compose -f compose.prod.yaml exec db sh -c 'dropdb -U "$POSTGRES_USER" restore_drill'
   ```
3. Real restore (replaces the live data):
   ```bash
   docker compose -f compose.prod.yaml stop web
   docker compose -f compose.prod.yaml exec -T db sh -c \
     'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
     < restored.dump
   docker compose -f compose.prod.yaml start web
   docker compose -f compose.prod.yaml exec web python manage.py check_ledger
   ```
4. Delete `restored.dump` afterwards: it is not encrypted.

## Rotating the secret key
Do it if `.env` may have leaked, or yearly.
1. Generate a new key (`python3 -c "import secrets; print(secrets.token_urlsafe(50))"`).
2. In `.env`: move the current `SECRET_KEY` value into `SECRET_KEY_FALLBACKS`, put the new one in
   `SECRET_KEY`, then `docker compose -f compose.prod.yaml up -d`. Tablets and signed-in users
   stay signed in.
3. After a week, empty `SECRET_KEY_FALLBACKS` and restart again. Anything still signed with the
   old key (for example a tablet not used all week) must sign in or be registered again.

If the database password leaked, change it in Postgres and in `.env` together.

## Moving to a new server
Install on the new server (steps above, same `.env`), decrypt the latest backup, do the real
restore, then point DNS at the new server.
