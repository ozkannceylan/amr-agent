# Brief m4r-02 — roadmap and plan onto the ADR 0007 order

gate:                reordering (no gate advances; M3 stays current)
agent:               arch-docs
goal:                docs/roadmap.md carries the ADR 0007 gate table and docs/PLAN.md reflects the same order, so the tracking files agree with the accepted ADR
invariants_touched:  none
inputs:              [docs/adr/0007-safety-first-gate-order.md, docs/roadmap.md, docs/PLAN.md]
deliverable:         docs/roadmap.md and docs/PLAN.md updated to the ADR 0007 order (one logical change)
done_when:           the roadmap table matches ADR 0007 row for row including the embedded M4/M8 showcases and M11's entry condition (the m4-00 decision list); closed gates and M3 are unchanged; PLAN.md's gate context lines match the new numbers; and no statement in either file still reflects the ADR 0004 order
forbidden:           [editing ADR files, editing TODO.md (the orchestrator owns the queue), editing docs/safety/, plc/ or sim/ (their stale references are separate briefs), changing M3 scope or status, editing any file outside docs/roadmap.md and docs/PLAN.md]

## Context

ADR 0007 (accepted 2026-07-28) supersedes ADR 0004's order: M4 safety
layer on the fixed cell, M5-M8 unchanged in number and content, M9
demonstration, M10 arm, M11 Hermes (parked, m4-00 decisions as entry
condition). Renumbering is minimal by construction — only four rows move.
Carry over ADR 0007's per-function SRS split into the M4/M5/M6/M8/M10
rows only to the extent the roadmap table format bears it (a criterion
line, not the full table — the ADR holds the detail). The roadmap's
"gate order follows ADR 0004" line must now cite 0007.
