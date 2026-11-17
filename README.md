<div align="center">

# Dental Lab Material Kiosk

**Scan it. Count it. Know where every material goes.**

An open-source, self-hosted kiosk that shows dental labs which department consumes the most
material, what it costs, and who took it.

[![CI](https://github.com/safwanmohiuddin-droid/dental-lab-kiosk/actions/workflows/ci.yml/badge.svg)](https://github.com/safwanmohiuddin-droid/dental-lab-kiosk/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-AGPL--3.0-green)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Django](https://img.shields.io/badge/django-5.2%20LTS-0C4B33)
![PostgreSQL](https://img.shields.io/badge/postgresql-16-336791)

</div>

---

## The problem

In most dental labs, materials leave the store room on paper slips, or with no record at all.
At the end of the month nobody can say which department used the zirconia, why ceramic costs
went up, or who took the last box of burs. Accounting software sees one big "materials" number.

## The idea

A technician walks into the store room, opens the kiosk on a tablet or their own phone, scans a
material, types a quantity and confirms. About ten seconds. The owner gets a live view of:

- **Quantity and cost per department**, per month or any date range
- **Top materials** by quantity and by value
- **Who took what**, and when, with an optional case number
- **Stock on hand**, kept up to date by every issue, return and delivery

Prices are optional. Every report works on quantity, and money appears wherever a cost is known,
with a "cost coverage" figure so a partial total is never mistaken for a full one.

It works next to **any** accounting or lab software. Nothing to integrate on day one.

## How it works

```
 Supplier delivery          Store room                     Owner
 -----------------          ----------                     -----
 Excel sheet  --import-->   Stock on hand  <--issue--   Technician (PIN or own login)
 (qty, optional cost)            |          --return-->  scans with phone camera or USB scanner
                                 v
                         Append-only stock ledger  -->  Reports by department, material, person
```

## Features

| | Feature |
|---|---|
| 📦 | Stock in from an Excel template, checked row by row and previewed before anything is saved |
| 📱 | Mobile-first kiosk for any phone, tablet or desktop browser |
| 📷 | Phone camera barcode scanning (native or WASM fallback); USB and Bluetooth scanners work too |
| 🔁 | Repeat a recent issue in one tap |
| ↩️ | Returns to stock, credited back to the department at the cost it was charged |
| 🦷 | Optional case number on each issue |
| 🔐 | Shared tablet with employee PIN and lockout, or personal login on your own phone |
| 📊 | Reports by department, material and person, exportable to Excel |
| 🛡️ | Admin and reports behind two-factor login; HTTPS, health check, JSON logs, tested backups |

The kiosk needs a network connection. If a phone loses WiFi, it says so plainly, and pressing
again never records an issue twice.

## Install

One lab per install, on a small server or a mini PC in the lab. Needs Docker.

```bash
git clone https://github.com/safwanmohiuddin-droid/dental-lab-kiosk.git
cd dental-lab-kiosk
cp .env.prod.example .env      # set DOMAIN, SECRET_KEY, database password, TIME_ZONE
docker compose -f compose.prod.yaml up -d --build
```

Then create the first admin and its authenticator, register the store-room tablet, and import
your stock. Step by step, including upgrades, backups and a restore drill:
**[docs/operations.md](docs/operations.md)**.

More guides: [importing stock from Excel](docs/stock-import.md) · [hardware](docs/hardware.md) ·
[testing the camera on a phone](docs/phone-testing.md).

## Built on purpose to be boring and reliable

| Layer | Choice |
|---|---|
| Backend | Django 5.2 LTS, Python 3.13 |
| UI | Server-rendered templates, boosted htmx, plain CSS, no build step |
| Database | PostgreSQL 16 |
| Deployment | Docker Compose, Caddy (automatic HTTPS), gunicorn, WhiteNoise |

Some of the engineering inside:

- **Append-only stock ledger** with a cached balance and an invariant check, so stock never drifts
- **Row-level locking** so two people can't take the last unit, or out-guess a PIN lockout, at the
  same moment (both races reproduced in tests first)
- **Idempotency keys** so a double tap or a network retry never records an issue twice
- **Property-based tests** (Hypothesis) throwing random operation sequences at the ledger
- **All-or-nothing imports** that catch Excel's traps, like barcodes that lost their leading zero
- **Decimal everywhere, UTC storage**, and reports in the lab's own time zone

Every significant choice is an [Architecture Decision Record](docs/decisions/README.md), and real
bugs are logged with their root cause in [docs/BUGS.md](docs/BUGS.md).

## Development

Needs [uv](https://docs.astral.sh/uv/) and PostgreSQL 16 (`docker compose up -d` starts one, or
use a native install and set `DATABASE_URL` in `.env`).

```bash
cp .env.example .env        # set SECRET_KEY and DATABASE_URL
uv sync
uv run pre-commit install
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver
```

Same checks as CI:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Contributing

Feedback from people who run or work in a dental lab is the most valuable contribution: how
materials are issued today and what would make this worth installing. See
[CONTRIBUTING.md](CONTRIBUTING.md). Security issues: [SECURITY.md](SECURITY.md).

## License

[AGPL-3.0](LICENSE). Free to use and change. If you run a modified version for other people,
you must share your changes.
