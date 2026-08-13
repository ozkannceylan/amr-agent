gate:                M0
agent:               interface (write scope extended to docs/roadmap.md by owner for this brief)
goal:                Add gate M9 to the roadmap for arm integration.
invariants_touched:  none
inputs:              [CLAUDE.md section 6, docs/roadmap.md, docs/adr/0002-vehicle-platform.md]
deliverable:         docs/roadmap.md
content:             M9, arm integration. Closes when arm motion is gated by a base-stationary interlock, arm work is carried as a VDA 5050 action, and the safety zone model distinguishes base and arm.
done_when:           Roadmap table updated, current gate unchanged.
forbidden:           [reordering existing gates, marking any gate complete, writing code]
