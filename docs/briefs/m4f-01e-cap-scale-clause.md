# Brief m4f-01e — the cap is a scale, ruled at its origin

```
gate:                M4
agent:               interface
goal:                opcua-nodes.md section 10.6 no longer admits the clamp
                     reading the SPEC's pass line inherited.
invariants_touched:  none
inputs:              [docs/reports/m4f-04e-t5-pass-line-corrections.md,
                      plc/forklift/SPEC.md sections 6.5 and 7,
                      docs/interfaces/opcua-nodes.md section 10.6]
deliverable:         docs/interfaces/opcua-nodes.md section 10.6 — one clause
done_when:           the "scaled by TRACTION_SPEED_MAX, reduced by the cap"
                     sentence states scale semantics unambiguously: the
                     request fraction multiplies whichever cap is in force
                     (0.20 under the raised cap 0.30 commands 0.060 m/s,
                     never 0.20); a subject sweep over cap/scale/limit in
                     section 10 finds no other statement admitting the clamp
                     reading; nothing else changes.
forbidden:           [changing constants or node rows, editing plc/ or sim/,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the doc plus
your report docs/reports/m4f-01e-cap-scale-clause.md; message style
`docs(interfaces): state the cap as a scale at its origin`.
