# Brief m4r-01 — ADR 0007, safety-first reordering and deprioritisation

gate:                reordering (no gate advances; M3 stays current and untouched)
agent:               arch-docs
goal:                ADR 0007 records the owner's 2026-07-28 re-prioritisation, superseding ADR 0004's gate order
invariants_touched:  none (gate order is ADR 0004's, not §2's; this supersedes 0004 by the book)
inputs:              [docs/adr/0004-gate-reordering-plc-loop-first.md, docs/roadmap.md, docs/reports/m4-00-hermes-survey.md, docs/safety/ (SRS function list, for the cell-scope/vehicle-scope split), the owner rulings below]
deliverable:         docs/adr/0007-<slug>.md
done_when:           ADR 0007 is complete in the §8 format (Status accepted, Context, Decision with the full new gate table, Consequences, Alternatives), supersedes 0004 explicitly, and the new order satisfies every owner ruling below
forbidden:           [editing roadmap.md or PLAN.md (that is the next brief), editing ADR 0004 (superseded, never edited), renumbering any closed gate, changing M3's scope or criteria, editing any file outside docs/adr/]

## Owner rulings (2026-07-28, verbatim intent)

1. Priority is: the system working properly, safety standards integrated
   and demonstrated through showcases, F-PLC integration. Robot arm and
   the Hermes assistant come last; Hermes has no priority at all right now
   and is parked.
2. The safety layer (F-CPU) comes directly after the cell and before the
   fleet chain: once M3 closes, the F-CPU is integrated on the fixed cell
   (e-stop chain, cell-scope zone monitoring). SRS functions that need a
   vehicle to exist are completed later, in the phase that has vehicles —
   the ADR must name that split explicitly, function by function, from the
   SRS (which functions are demonstrable on the fixed cell alone, which
   wait).
3. Demonstration is not one final gate only: each major phase's closing
   criterion includes a recorded showcase (cell + safety showcase, fleet
   showcase, final end-to-end demonstration). Keep a final demonstration
   gate; embed the phase showcases in the phase gates' criteria.
4. The resulting order after M3: safety layer on the cell, then the
   vehicle/fleet chain (simulated vehicle, VDA 5050 client, fleet manager,
   PLC/fleet integration), then the final demonstration, then arm
   integration, then the Hermes command path dead last.

## Context the ADR must record

- ADR 0004 put Hermes at M4 on the premise of "a Hermes agent running on
  the same server"; the m4-00 survey showed the deployment contradicts
  that premise (Hermes on a rented remote VPS, the PLC on the owner's machine),
  and the owner has parked the component. The Hermes gate keeps the m4-00
  decision list as its entry condition.
- Closed gates (M0-M2) and the in-progress M3 keep their numbers and
  contents. Only the gates after M3 are renumbered.
- Gate criteria remain observable behaviour, per CLAUDE.md §6.
