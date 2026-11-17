# 0037. A report builder instead of fixed report pages; motion that can't block data

- Status: Accepted (owner, 2026-11-17)
- Date: 2026-11-17

## Context
The owner's goal is monitoring how many units of each item are consumed, by whom, where and over
time. The fixed report pages (overview, materials, people) answered three questions and needed a
button for every view. The owner also found the interface static.

## Decision
- **Engine** (`reports/engine.py`): any measure (units used, cost, times taken) x any breakdown
  (department, material, person, category, case number, or none) x any time grain (day, week,
  month, or whole period) x filters (department, category, material, person) x period presets or
  custom dates. All aggregation in SQL on the existing consumption figures; quiet periods are
  filled with zeros; time charts show the top 6 series plus "Everything else".
- **Honest numbers:** adding different units is flagged; incomplete cost is flagged.
- **Builder page:** one editable sentence ("Show units used by material per week for this
  month") updates the report live with htmx, no Show button. The URL is the report: bookmark or
  share it. Excel and CSV export exactly what's on screen. Old report links redirect into it.
- **Charts:** Chart.js 4.6.1, vendored (MIT, integrity checked against npm), no CDN at runtime.
- **Motion:** content eases in, buttons respond to presses, the quantity bumps, the done tick
  draws itself, charts animate; all disabled under "reduce motion".
- **No View Transitions API:** when a transition times out, htmx skips the swap and the screen
  shows stale data. Motion is done with CSS on the new content instead.
- **`hx-sync="this:replace"`:** a newer change cancels an older request still in flight.

## Alternatives considered
- More fixed pages: every new question needs code.
- A BI tool (Metabase, Superset): powerful, but another server to run and secure per lab.

## Consequences
Reports are one page. Adding a breakdown is one line in `DIMENSIONS`.

## Interview angle
"Two bugs only a browser showed: an out-of-order response overwrote a newer one, and a decorative
transition could silently block a data update. Decoration must never be able to block data."
