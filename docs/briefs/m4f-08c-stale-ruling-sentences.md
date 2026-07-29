# Brief m4f-08c — two stale ruling sentences in the scenario doc

```
gate:                M4
agent:               sim
goal:                The scenario document nowhere describes as pending a
                     ruling its own findings table records as taken.
invariants_touched:  none
inputs:              [sim/scenarios/forklift_commissioning.md sections 3, 5
                      and 11, commit bc6a570]
deliverable:         sim/scenarios/forklift_commissioning.md — the section 5
                     FINDING block's closing sentence and the section 3
                     start-order note's request sentence, nothing else
done_when:           the section 5 FINDING block ends by recording that
                     bc6a570 ruled the scale form (pass line ≈+0.060 m/s)
                     rather than "it is not one this file may take"; the
                     section 3 note states the section 11 revision landed in
                     the same commit rather than being requested; no figure,
                     step, observable or findings-table row changes
                     (git diff --numstat small and named in your report); a
                     subject sweep over "ruling", "requested" and "intended"
                     in the file finds no further sentence describing the
                     settled question as open.
forbidden:           [any other change to the file, editing plc/ hmi/ bridge/
                      files, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the scenario
doc plus your report docs/reports/m4f-08c-stale-ruling-sentences.md; message
style `docs(sim): record the taken ruling where the procedure still asked for
it`.
