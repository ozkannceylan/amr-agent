brief:               docs/briefs/m3r-01-adr-0004-reordering.md
status:              done
files_changed:
  - docs/adr/0004-gate-reordering-plc-loop-first.md (new)
  - docs/reports/m3r-01-adr-0004-reordering.md (this report)
invariants_touched:  none — ADR 0004 restates invariants 1, 4, 5, 6 and 10 as
                     binding constraints on the new gate order; it changes
                     only sequencing, not the invariant set in ADR 0001.
open_questions:
  - The ADR notes that the OPC UA node model will gain fixed-equipment I/O
    nodes for the demonstration cell. That extension is not written; it needs
    an interface-agent brief before M3 bridge work starts.
  - The bridge design document is named as a precondition for bridge code but
    has no owner or path assigned yet.
  - sim/scenarios/DEFERRED.md is named as a consequence but is outside this
    agent's write access; it needs a sim-agent brief.
  - Existing briefs and reports use the old gate numbers (m3-01-world-bringup
    was written under the old M3 "Simulated vehicle"). The ADR records that
    filenames are kept as-is; confirm the orchestrator agrees before the
    roadmap renumbering brief lands.
next_suggested:      Issue the roadmap/PLAN renumbering brief so
                     docs/roadmap.md, docs/PLAN.md and docs/TODO.md match
                     ADR 0004's M0..M11 order.
