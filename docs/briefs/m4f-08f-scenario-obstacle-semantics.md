# Brief m4f-08f — the sim documents learn the three-class rule

```
gate:                M4
agent:               sim
goal:                sim/ no longer teaches the defect the fix removed, and the
                     crate workaround that existed only to dodge it is retired.
invariants_touched:  none
inputs:              [docs/reports/m4f-02c-inf-means-clear.md (commit 74c7d5f),
                      sim/README.md ("An empty forward sector is a no-data
                      condition, not a clear path"),
                      sim/scenarios/forklift_commissioning.md (the
                      crate-placement workaround)]
deliverable:         sim/README.md and sim/scenarios/forklift_commissioning.md
                     — the stale sentences and the workaround text
done_when:           the README sentence states the corrected rule (an empty
                     forward sector reads clear at range_max since 74c7d5f;
                     the fail-safe remains for missing/stale/unusable scans);
                     the scenario doc's crate-placement workaround is replaced
                     by a note that it predated 74c7d5f and is no longer
                     needed — rehearsal transcripts and figures stay untouched
                     (printed evidence is never edited; a sentence records the
                     build difference, the pattern the file already uses);
                     a sweep over "no-data", "empty forward sector" and the
                     workaround's phrasing finds no further stale statement;
                     no step, figure or observable changes beyond the
                     workaround text itself.
forbidden:           [editing agv/ plc/ docs/interfaces/ files, changing any
                      rehearsal figure or transcript, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the two sim
files plus your report docs/reports/m4f-08f-scenario-obstacle-semantics.md;
message style `docs(sim): retire the pre-fix obstacle workaround`.
