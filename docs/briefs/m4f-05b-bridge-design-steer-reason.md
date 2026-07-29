# Brief m4f-05b — bridge-design §1.1 steer-gating reason

```
gate:                M4
agent:               interface
goal:                bridge-design.md §1.1 justifies its no-logic verdict with a
                     true statement after the ae93667 steer ruling.
invariants_touched:  none
inputs:              [docs/reports/m4f-01b-steer-gating-correction.md (drop-in
                      text), docs/interfaces/opcua-nodes.md section 10.6]
deliverable:         docs/interfaces/bridge-design.md section 1.1 (one clause)
done_when:           the §1.1 verdict is unchanged and its reason cites the
                     §10.6 ruling (all three setpoints gated to zero) instead of
                     the withdrawn exemption; a whitespace-normalised sweep
                     finds no other statement in the file depending on the old
                     reason.
forbidden:           [any other bridge-design.md change, editing opcua-nodes.md
                      or bridge/ or plc/, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the design doc
plus your report docs/reports/m4f-05b-bridge-design-steer-reason.md; message
style `docs(interfaces): correct the steer-gating reason in the bridge design`.
