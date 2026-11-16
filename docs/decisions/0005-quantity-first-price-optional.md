# 0005. Quantity is primary, price optional

- Status: Accepted (owner, 2026-11-16)
- Date: 2026-11-16

## Context
Goal: cost per department, which department takes the most, who took it, how much. Many labs don't
have reliable unit prices.

## Decision
Every report works on quantity. Money appears when a cost is known: unit cost comes from the
stock-in import (optional column), moving average per material. An issue stores `unit_cost` as a
snapshot (nullable). Reports show a **cost coverage %** ("82% of issues this month have a cost") so
nobody mistakes a partial total for a full one.

## Alternatives considered
- Require prices: blocks adoption.
- Hide money entirely: loses the main goal for labs that do have prices.

## Consequences
`unit_cost` and `value` are nullable; every money aggregate must handle NULL explicitly.

## Interview angle
"Designing for missing data instead of pretending it's complete, and surfacing the gap in the UI."
