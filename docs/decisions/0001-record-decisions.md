# 0001. Record decisions as ADRs

- Status: Accepted
- Date: 2026-11-16

## Context
Solo project, built to learn and to explain later. Memory of *why* fades in weeks; code only
shows *what*.

## Decision
Every choice that would be expensive to reverse, or that someone could reasonably question, gets
an ADR in `docs/decisions/` before code depends on it. Bugs worth learning from go in
`docs/BUGS.md`.

## Alternatives considered
- Comments in code: scattered, no history.
- A wiki: drifts away from the code.

## Consequences
Small overhead per decision. The repo becomes its own design portfolio.

## Interview angle
"I write ADRs so reviewers see the trade-off, not just the result. Here's one I later superseded."
