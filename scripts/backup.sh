#!/bin/sh
# Nightly database backup. Run from the folder that holds compose.prod.yaml, e.g. from cron:
#   15 2 * * * cd /opt/kiosk && ./scripts/backup.sh >> backups/backup.log 2>&1
set -eu

dir="${BACKUP_DIR:-./backups}"
keep="${BACKUP_KEEP:-14}"
mkdir -p "$dir"

file="$dir/kiosk-$(date -u +%Y%m%dT%H%M%SZ).dump"
# Write to a temp name first so a failed dump is never mistaken for a good backup.
docker compose -f compose.prod.yaml exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$file.part"
[ -s "$file.part" ] || { echo "backup failed: empty dump" >&2; rm -f "$file.part"; exit 1; }
mv "$file.part" "$file"
echo "backup written: $file"

# Keep the newest $keep backups.
ls -1t "$dir"/kiosk-*.dump | tail -n +"$((keep + 1))" | while read -r old; do rm -f -- "$old"; done
