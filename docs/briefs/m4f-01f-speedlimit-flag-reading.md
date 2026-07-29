# Brief m4f-01f — the speed-limit flag's reading, ruled

```
gate:                M4
agent:               interface
goal:                Section 10.7 states which reading ForkliftSpeedLimitActive
                     carries, matching what the corrected SPEC implements.
invariants_touched:  none
inputs:              [plc/forklift/SPEC.md section 6.5 as corrected by bc6a570
                      (the wide "in force" flag), docs/reports/m4f-04e-t5-pass-
                      line-corrections.md request 1, docs/interfaces/opcua-
                      nodes.md section 10.7]
deliverable:         docs/interfaces/opcua-nodes.md section 10.7 — the
                     ForkliftSpeedLimitActive meaning clause
done_when:           the clause states the WIDE reading: TRUE while the raised-
                     carriage cap is the multiplier in force during active
                     teleop, regardless of the momentary demand — not the
                     narrow "biting" verdict, which under scale semantics
                     degenerates to any-nonzero-demand and flickers through
                     centre stick; the discarded narrow reading is named so it
                     cannot be re-derived; a subject sweep over the flag's name
                     across section 10 finds no statement carrying the narrow
                     reading; nothing else changes.
forbidden:           [changing any other clause, editing plc/ files,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the doc plus
your report docs/reports/m4f-01f-speedlimit-flag-reading.md; message style
`docs(interfaces): rule the speed-limit flag's wide reading`.
