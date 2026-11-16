<div align="center">

# Dental Lab Material Kiosk

**Scan it. Count it. Know where every material goes.**

An open-source, self-hosted kiosk that shows dental labs which department consumes the most
material, what it costs, and who took it.

[![CI](https://github.com/safwanmohiuddin-droid/dental-lab-kiosk/actions/workflows/ci.yml/badge.svg)](https://github.com/safwanmohiuddin-droid/dental-lab-kiosk/actions/workflows/ci.yml)
![Status](https://img.shields.io/badge/status-early%20development-orange)
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

Prices are optional. Every report works on quantity, and money appears wherever a cost is known.

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

## Planned features (v1)

| | Feature |
|---|---|
| 📦 | Stock in from an Excel file, validated and previewed before anything is saved |
| 📱 | Mobile-first kiosk that works on any phone, tablet or desktop browser |
| 📷 | Phone camera barcode scanning, with USB and Bluetooth scanners also supported |
| 🔁 | Repeat last issue in one tap |
| ↩️ | Returns to stock, credited back to the right department |
| 🦷 | Optional case number on each issue |
| 📶 | Offline mode for store rooms without signal, synced safely when back online |
| 🔐 | Shared tablet with employee PIN, or personal login on your own phone |
| 📊 | Reports by department, material and person, exportable to Excel |

## Built on purpose to be boring and reliable

| Layer | Choice |
|---|---|
| Backend | Django 5.2 LTS, Python 3.13 |
| UI | Server-rendered templates with HTMX, no SPA |
| Database | PostgreSQL 16 |
| Deployment | Docker Compose with Caddy for automatic HTTPS |

Some of the engineering ideas inside:

- **Append-only stock ledger** with a cached balance and an invariant check, so stock never drifts
- **Row-level locking** so two people cannot take the last unit at the same moment
- **Idempotency keys** so a double tap or a network retry never records an issue twice
- **All-or-nothing imports** so one bad row never leaves half a delivery in the system
- **Decimal everywhere, UTC storage**, and reports in the lab's own time zone

Every significant choice is written down as an
[Architecture Decision Record](docs/decisions/README.md), and real bugs are logged with their root
cause in [docs/BUGS.md](docs/BUGS.md).

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Project foundations, CI, decision records | ✅ Done |
| 1 | Data model and admin | ⏳ Next |
| 2 | Stock ledger with locking and property-based tests | |
| 3 | Excel import | |
| 4 | Employee PIN and personal login | |
| 5 | Mobile kiosk | |
| 6 | Camera scanning | |
| 7 | Reports and Excel export | |
| 8 | Offline mode | |
| 9 | Production hardening, backups, one-command deploy | |
| 10 | v0.1.0 release | |

The full plan lives in [PLAN.md](PLAN.md).

## Getting started (development)

Requirements: [uv](https://docs.astral.sh/uv/) and PostgreSQL 16, either with Docker (`docker compose up -d`) or a native install. Set `DATABASE_URL` in `.env` to match.

```bash
git clone https://github.com/safwanmohiuddin-droid/dental-lab-kiosk.git
cd dental-lab-kiosk
cp .env.example .env        # set SECRET_KEY
docker compose up -d        # PostgreSQL 16
uv sync
uv run pre-commit install
uv run python manage.py migrate
uv run python manage.py runserver
```

Run the same checks as CI:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Contributing

The project is early, so the best contribution right now is feedback from people who run or work
in a dental lab: how materials are issued today, what you would want to see, and what would make
this worth installing. Please open an issue.

## License

Not chosen yet. It will be an OSI-approved open-source license before the first release
(see [ADR 0014](docs/decisions/0014-license.md)).
