# 0030. Plain CSS and a boosted htmx kiosk

- Status: Accepted, amended by [0036](0036-ux-rules-and-one-look.md) (one shared stylesheet) (owner, 2026-11-17)
- Date: 2026-11-17
- Amends: [0002](0002-django-htmx-monolith.md) (drops the Tailwind standalone CLI)

## Context
ADR 0002 planned Tailwind via its standalone CLI. The kiosk has six small screens. Tailwind
would add a binary to download, a build step to run before every commit, and a generated file to
keep in sync, for about 150 lines of styling.

## Decision
- One hand-written `kiosk/static/kiosk/kiosk.css` with CSS custom properties (light and dark).
- htmx 2.0.11 vendored, used only as `hx-boost` on `<body>`: every link and form keeps working
  without JavaScript, and with it pages swap without a full reload. No per-element htmx markup.
- htmx is told to swap 4xx/5xx responses too (`htmx-config` meta), so error pages such as the
  403 "PIN locked" screen are shown instead of silently ignored.

## Alternatives considered
- Tailwind CLI: consistent utilities, but a build step and a binary for a tiny stylesheet.
- htmx partial swaps (`hx-get`, `hx-target`) per form: more markup, and every partial needs a
  matching server view; boosting gives most of the speed for none of that.

## Consequences
No build step anywhere in the project. Styling changes are plain CSS edits.

## Interview angle
"I removed a build step because the problem was 150 lines of CSS, and wrote down why."
