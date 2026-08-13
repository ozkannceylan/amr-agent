gate:                M3 (reordering)
agent:               arch-docs
goal:                docs/roadmap.md and docs/PLAN.md carry the ADR 0004 gate order.
invariants_touched:  none
inputs:              [docs/adr/0004-gate-reordering-plc-loop-first.md, docs/roadmap.md, docs/PLAN.md, CLAUDE.md section 6]
deliverable:         docs/roadmap.md and docs/PLAN.md, updated as the single renumbering change
done_when:           Roadmap lists M0..M11 in the ADR 0004 order with a closes-when per gate (M3 carries the four demonstrated items, M4 the Hermes command path); closed gates M0-M2 keep their dates and report references; current gate is M3; PLAN.md describes M3, its exit criterion and its brief list.
forbidden:           [marking M3 or any later gate closed, dropping the arm gate, altering closed-gate records, writing code, editing directories other than the two files and the report]
