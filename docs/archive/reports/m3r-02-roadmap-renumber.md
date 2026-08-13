brief:               docs/briefs/m3r-02-roadmap-renumber.md
status:              done
files_changed:
  - docs/roadmap.md (renumbered to ADR 0004 order M0..M11)
  - docs/PLAN.md (rewritten for the new M3)
  - docs/reports/m3r-02-roadmap-renumber.md (this report)
invariants_touched:  none
open_questions:
  - docs/TODO.md is outside this agent's write access and still carries the
    old M3 (Simulated vehicle) work queue. It now disagrees with roadmap.md
    and PLAN.md; it needs a brief before the next delegation.
  - The six M3 briefs listed in PLAN.md are named but not yet written. Two of
    them carry preconditions: m3-03 (bridge design) must be reviewed before
    m3-04 (bridge implementation) starts, and m3-02 (OPC UA node extension)
    should land before either, since the bridge codes against those nodes.
  - sim/scenarios/DEFERRED.md, required by ADR 0004's consequences, is still
    unwritten and belongs to the sim agent.
next_suggested:      Issue the TODO.md re-queue brief, then m3-02 (interface)
                     and m3-01 (sim), which have no dependency on each other.
