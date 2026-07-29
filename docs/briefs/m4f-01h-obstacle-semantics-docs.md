# Brief m4f-01h — obstacle semantics in the interface documents

```
gate:                M4
agent:               interface
goal:                Both interface documents state the three-class obstacle
                     semantics 74c7d5f implemented.
invariants_touched:  none
inputs:              [docs/reports/m4f-02c-inf-means-clear.md (commit 74c7d5f),
                      agv/forklift/README.md (the corrected contract rows),
                      docs/interfaces/opcua-nodes.md section 10.5,
                      docs/interfaces/bridge-design.md row 12]
deliverable:         docs/interfaces/opcua-nodes.md section 10.5 and
                     docs/interfaces/bridge-design.md row 12 — the fail-safe
                     sentences
done_when:           both state: a beyond-range return (inf or >= range_max)
                     is CLEAR evidence at range_max (8.00 published, inside
                     the plausibility window); the fail-safe (TRUE, 0.0) fires
                     only on a missing, stale (>0.5 s) or structurally
                     unusable scan, or a sector with no sample in either valid
                     class — never on an open horizon; each cites 74c7d5f; a
                     whitespace-normalised sweep over "invalid, non-finite or
                     stale" and "no-data" across both files finds no statement
                     carrying the old rule; nothing else changes.
forbidden:           [changing thresholds or node rows beyond these sentences,
                      editing agv/ plc/ sim/ files, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the two docs
plus your report docs/reports/m4f-01h-obstacle-semantics-docs.md; message style
`docs(interfaces): state the three-class obstacle semantics`.
