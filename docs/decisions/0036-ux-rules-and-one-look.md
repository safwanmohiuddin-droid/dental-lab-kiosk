# 0036. UX follows published rules; one look everywhere

- Status: Accepted (owner, 2026-11-17)
- Date: 2026-11-17
- Amends: [0030](0030-plain-css-and-boosted-htmx.md) (still plain CSS; now one shared stylesheet)

## Context
The owner found the interface and the experience poor, and asked for the design to follow
published UX rules rather than taste. The kiosk, reports and admin each looked different.

## Decision
- [docs/ux-rules.md](../ux-rules.md) is the rulebook: Nielsen's 10 heuristics, Laws of UX
  (Fitts, Hick, Jakob, Doherty, von Restorff...) and WCAG 2.2 target sizes, turned into 12 rules
  for this app, with an audit of v0.2.
- One stylesheet, `kiosk/static/ui/ui.css`, for kiosk and reports; the admin maps its colour
  variables to the same palette in `templates/admin/base_site.html`. Visual direction:
  "porcelain and ink" (warm white, deep ink, one accent, large serif numbers). Changing the look
  means changing the variables at the top of `ui.css`.
- Kiosk: search plus recent people first; an on-screen PIN pad; take in one step with a big
  stepper; a second look only when the amount is more than 3x that person's usual (median of
  their last 10 takes, needs at least 3); usual items first; "Saving..." busy state; a visible
  countdown on shared tablets.
- Reports: plain words, quick period buttons, a one-sentence headline.
- Admin: actions are visible buttons; developer sections are renamed "Advanced" and listed last.

## Alternatives considered
- Keep an always-on confirm screen: safe but adds a step to every take; the unusual-amount check
  keeps the safety where it matters (error prevention without friction).
- A JavaScript framework for the kiosk: more power than these screens need.

## Consequences
The confirm URL is gone; taking is one POST with the same idempotency key, so a second press
(or the unusual-amount confirmation) still records once.

## Interview angle
"I replaced 'what looks nice to me' with published heuristics, audited the app against them, and
kept the safety net only where the data says it's needed."
