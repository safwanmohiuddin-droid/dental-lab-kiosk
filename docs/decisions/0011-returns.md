# 0011. Returns credit the department at issue cost

- Status: Accepted (owner, 2026-11-16)
- Date: 2026-11-16

## Context
Owner wants returns to stock. If a return is valued at today's average cost, the department is
credited a different amount than it was charged, department totals drift.

## Decision
A return is a `return` move linked to the original issue (`returns_move_id`), valued at that
issue's `unit_cost`, for the same department. Return quantity can't exceed issued minus already
returned. The kiosk offers "return from my recent issues" (last 14 days). Unlinked returns
(rare) go through an admin adjustment.

## Alternatives considered
- Return at current average cost: simpler, skews department cost.
- Returns as negative issues with no link: can't stop over-returning.

## Consequences
Average cost recomputation must include returns. One extra FK.

## Interview angle
"A tiny valuation choice that decides whether department reports reconcile."
