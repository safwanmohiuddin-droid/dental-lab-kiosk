# 0034. Encrypted, off-site backups and secret key rotation

- Status: Accepted (owner, 2026-11-17)
- Date: 2026-11-17

## Context
A security review after v0.1.0 found that `scripts/backup.sh` wrote plain `pg_dump` files to the
same server as the database: a dead disk loses both, and a stolen server or leaked copy exposes
all stock, staff and cost data. The secret key and database password live in `.env` with no
guidance on its permissions, and rotating `SECRET_KEY` would unregister every tablet (their
cookies are signed with it).

## Decision
- Backups are encrypted with [age](https://age-encryption.org) to a **public key**
  (`BACKUP_AGE_RECIPIENT`). The private key is created and kept off the server by the lab owner.
  The server can write backups but never read them.
- The script **refuses** to run without a recipient: no silent plain backups. It writes to a temp
  file and removes it on any failure (`set -o pipefail` plus an exit trap).
- Optional off-site copy with rclone (`BACKUP_RCLONE_REMOTE`); without it every run warns.
  Remote retention is the bucket's lifecycle rule.
- The script warns nightly when `.env` is readable by other users; install docs `chmod 600 .env`.
- `SECRET_KEY_FALLBACKS` from the environment, so the key can be rotated with a grace period.
- CI proves it: refuses without a key, the file on disk contains no readable data, decrypts with
  the private key, restores into a fresh database.

## Alternatives considered
- Symmetric encryption (gpg passphrase in `.env`): the passphrase sits next to the backups, so a
  stolen server can still read them.
- A secrets manager (Vault, cloud KMS): right for a fleet, too heavy for one self-hosted lab
  server; file permissions plus rotation fit the threat.
- Mandatory off-site copy: needs an account the lab owns; a loud warning is the honest default.

## Consequences
Two host tools (`age`, `rclone`). Losing the private key means losing every backup, so the docs
insist on two offline copies. Restores need the key holder.

## Interview angle
"Public-key encryption for backups: the machine that makes them can't read them, so compromising
it doesn't expose history. And a CI gotcha: `! grep` never fails under `bash -e`."
