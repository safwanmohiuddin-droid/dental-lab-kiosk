# 0004. Append-only stock ledger with cached balance

- Status: Accepted (owner, 2026-11-16)
- Date: 2026-11-16

## Context
The app is the stock master. We must answer "who took what, when, for which department" forever,
and stock must never drift.

## Decision
Table `stock_move` is insert-only (receipt, issue, return, adjust). `material.qty_on_hand` and
`material.avg_cost` are a cache, updated in the same transaction as the move, under
`select_for_update()` on the material row. Mistakes are fixed with a reversing move.
Invariant, checked by tests and a nightly command:
`material.qty_on_hand == SUM(stock_move.qty WHERE material)`.

## Alternatives considered
- Only a quantity column: fast, but no history and no way to audit.
- Compute balance on every read: always correct, slow as history grows.
- Full event sourcing: too much machinery for one aggregate.

## Consequences
Every write goes through one service module (`inventory/services.py`); views never touch the
cache directly. Need a repair command if the invariant ever breaks.

## Interview angle
"Ledger plus cached projection: the same pattern banks use, scaled down. Here's the race I caught
with a two-thread test."
