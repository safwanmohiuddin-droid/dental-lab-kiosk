# UX rules

Every screen follows these rules. They come from published, widely used sources, not taste:

- **NN/g heuristics:** Jakob Nielsen, [10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) (Nielsen Norman Group). Referenced below as H1 to H10.
- **Laws of UX:** [lawsofux.com](https://lawsofux.com/): Fitts, Hick, Jakob, Miller, Doherty, von Restorff and others.
- **WCAG 2.2:** [Target Size, SC 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html): touch targets at least 24 x 24 px, 44 x 44 px for important controls.

## The rules for this app

| # | Rule | Source |
|---|---|---|
| R1 | Every tap answers within 400 ms: show a busy state at once, then the result. | Doherty threshold, H1 |
| R2 | Use the lab's words: "Use", "Taken", "Has a price", not "Net qty", "Priced", "Issue". | H2 |
| R3 | Every step has a visible way back, and every mistake has an undo. | H3 |
| R4 | One look and feel across kiosk, owner screens and reports. | H4, Jakob's law |
| R5 | Prevent errors before they happen: steppers instead of free typing, warn on unusual amounts. | H5 |
| R6 | Show, don't make people remember: recent items and current stock always visible. | H6, Miller's law |
| R7 | Regulars get shortcuts: one-tap repeat, scanner auto-submit, search. | H7 |
| R8 | One main action per screen. Hide what's rarely needed. | H8, Hick's law |
| R9 | Errors say what happened and what to do next, in one sentence, next to the field. | H9 |
| R10 | The first visit explains itself: setup checklist, empty states that invite action. | H10 |
| R11 | Main buttons at least 48 px tall and at the bottom, where thumbs are. Nothing tappable under 44 px. | Fitts's law, WCAG 2.5.5 |
| R12 | The one thing that matters on a screen looks different from the rest (the quantity, a warning). | von Restorff effect |

## Audit of v0.2 against the rules

| Screen | Problem | Rule | Fix |
|---|---|---|---|
| Kiosk, start | Long list of every employee to scroll through; slow with 30+ people. | R8 (Hick) | Search box plus initials grid; most recent people first. |
| Kiosk, PIN | Phone keyboard pops up over the screen; small keys on a tablet. | R11 (Fitts), R4 (Jakob) | Large on-screen number pad, like a phone lock screen. |
| Kiosk, home | Two-step "Look up" then "Next" with generic labels. | R2, R8 | Scan fills the material straight away; button says "Take 3 discs". |
| Kiosk, home | Quantity is a free text box; typing 30 instead of 3 goes through. | R5 | Big minus / plus stepper; confirm if the amount is far above that person's usual. |
| Kiosk, home | "Repeat last issue" sits below the fold. | R6, R7 | Your usual items at the top, one tap to take. |
| Kiosk, all | No feedback while a request is on its way; people tap twice. | R1 | Button switches to "Saving..." and locks until the answer arrives. |
| Kiosk, done | Auto sign-out after 5 s is announced but there is no visible countdown. | R1 | Shrinking progress bar on the "Next person" button. |
| Owner admin | Home shows developer sections: "Authentication and authorization", "OTP_TOTP". | R2, R8 | Hide them from non-technical owners; group under "Advanced". |
| Owner admin | Actions are hidden in a dropdown plus a "Go" button. | R11, Jakob's law | Visible buttons for the common actions (Import, Delete, Restore). |
| Owner admin | Looks and behaves differently from the kiosk and reports. | R4 | Owner screens rebuilt in the same design as the kiosk; Django admin kept for rare tasks. |
| Reports | Column names "Net qty", "Priced", "Issues". | R2 | "Used", "Has a price", "Times taken". |
| Reports | Date range hidden behind a form and a "Show" button. | R6, R8 | Quick picks: This week, This month, Last month, Custom. |
| Reports | Every number has the same weight; the department that matters doesn't stand out. | R12 | Lead with one sentence: "Ceramics used the most this month: 1.4 k". |

Every fix lands with a test where behaviour changes, and is checked at phone width (375 px) and tablet width.
