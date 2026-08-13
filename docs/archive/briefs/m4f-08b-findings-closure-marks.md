# Brief m4f-08b — scenario-doc findings closed by their commits

```
gate:                M4
agent:               sim
goal:                The scenario document's findings list reflects what has
                     landed since the rehearsal.
invariants_touched:  none
inputs:              [sim/scenarios/forklift_commissioning.md section 11,
                      commit bc6a570 (findings 1 and 2 closed),
                      docs/briefs/m4f-07b-h6-and-holdable-reset.md (finding 3
                      in flight), docs/TODO.md owner queue (finding 4 is the
                      owner's planned bridge.yaml flip)]
deliverable:         sim/scenarios/forklift_commissioning.md — the findings
                     rows only
done_when:           findings 1 and 2 are marked closed naming bc6a570;
                     finding 3 names m4f-07b as its resolution path (update to
                     closed if that commit exists when you write); finding 4
                     points at the owner queue's bridge.yaml flip step; no
                     procedure step, figure or evidence text changes.
forbidden:           [editing any scenario step or rehearsal figure, editing
                      plc/ hmi/ bridge/ files, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the scenario
doc plus your report docs/reports/m4f-08b-findings-closure-marks.md; message
style `docs(sim): mark the rehearsal findings against their closures`.
