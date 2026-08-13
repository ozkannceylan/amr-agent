gate:                M0
agent:               infra
goal:                docs/roadmap.md tracks the M0 to M8 gates and marks the current gate.
invariants_touched:  none
inputs:              [CLAUDE.md section 6]
deliverable:         docs/roadmap.md
done_when:           The file contains the full M0 to M8 gate table from CLAUDE.md section 6 (gate, deliverable, closes-when), plus a current-gate line marking M0 as in progress; exactly one gate is marked current; no gate is marked closed.
forbidden:           [marking M0 closed in advance, inventing new gates or criteria, writing application code, editing files other than the deliverable and the report, committing to git]
