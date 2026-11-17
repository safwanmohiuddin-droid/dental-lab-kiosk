#!/usr/bin/env bash
# Nightly encrypted database backup (ADR 0034). Run from the folder that holds compose.prod.yaml:
#   15 2 * * * cd /opt/kiosk && ./scripts/backup.sh >> backups/backup.log 2>&1
#
# Needs `age` on the server. The server only holds the PUBLIC key (BACKUP_AGE_RECIPIENT), so it can
# write backups but never read them; the private key stays offline with the lab owner.
# Optional off-site copy with rclone (BACKUP_RCLONE_REMOTE, for example b2:my-bucket/kiosk).
set -euo pipefail

# Settings come from the environment, else from .env (read, never sourced: values aren't shell).
setting() { local v="${!1:-}"; [ -n "$v" ] || v="$(sed -n "s/^$1=//p" .env 2>/dev/null | tail -n 1)"; echo "$v"; }

dir="$(setting BACKUP_DIR)"; dir="${dir:-./backups}"
keep="$(setting BACKUP_KEEP)"; keep="${keep:-14}"
recipient="$(setting BACKUP_AGE_RECIPIENT)"
remote="$(setting BACKUP_RCLONE_REMOTE)"

# .env holds the secret key and the database password: only its owner should read it.
if [ -f .env ] && [ "$(stat -c %a .env)" != "600" ] && [ "$(stat -c %a .env)" != "400" ]; then
    echo "WARNING: .env is readable by other users (mode $(stat -c %a .env)). Run: chmod 600 .env" >&2
fi

if [ -z "$recipient" ]; then
    echo "backup refused: set BACKUP_AGE_RECIPIENT in .env (see docs/operations.md, Backups)" >&2
    exit 1
fi
command -v age >/dev/null || { echo "backup refused: install age (apt install age)" >&2; exit 1; }

mkdir -p "$dir"
file="$dir/kiosk-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
trap 'rm -f "$file.part"' EXIT  # a failed run leaves nothing half-written behind
# Temp name first, so a failed or partial dump is never mistaken for a good backup.
docker compose -f compose.prod.yaml exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    | age --encrypt --recipient "$recipient" > "$file.part"
[ -s "$file.part" ] || { echo "backup failed: empty file" >&2; rm -f "$file.part"; exit 1; }
mv "$file.part" "$file"
echo "backup written: $file"

# Keep the newest $keep local backups.
ls -1t "$dir"/kiosk-*.dump.age | tail -n +"$((keep + 1))" | while read -r old; do rm -f -- "$old"; done

if [ -n "$remote" ]; then
    rclone copy "$file" "$remote"
    echo "copied off-site: $remote"
else
    echo "WARNING: no off-site copy (set BACKUP_RCLONE_REMOTE). A dead disk takes the backups too." >&2
fi
