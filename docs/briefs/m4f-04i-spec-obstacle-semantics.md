# Brief m4f-04i — the SPEC's two obstacle-semantics sentences

```
gate:                M4
agent:               plc
goal:                plc/forklift/SPEC.md no longer describes the vehicle
                     layer's old fail-safe rule.
invariants_touched:  none
inputs:              [docs/reports/m4f-02c-inf-means-clear.md (commit 74c7d5f),
                      plc/forklift/SPEC.md (the report names the two places
                      stating the old semantics)]
deliverable:         plc/forklift/SPEC.md — the two sentences describing the
                     vehicle layer's fail-safe rule
done_when:           both sentences state the three-class rule (beyond-range =
                     clear at 8.00; fail-safe only on missing/stale/unusable
                     scan or an empty-valid sector), each citing 74c7d5f; the
                     PLC-side logic text is untouched — the PLC consumes the
                     booleans and the Real exactly as before; section 7 SCL,
                     constants, tags and step tables byte-identical (verify by
                     the statement-line count as every SPEC pass has); a
                     subject sweep over "non-finite", "no-data" and "invalid"
                     in the SPEC finds no further sentence carrying the old
                     rule.
forbidden:           [any change to SCL, constants, tags, step tables or pass
                      lines, editing agv/ or docs/interfaces/, mentioning any
                      deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly SPEC.md plus
your report docs/reports/m4f-04i-spec-obstacle-semantics.md; message style
`docs(plc): describe the three-class obstacle rule`.
