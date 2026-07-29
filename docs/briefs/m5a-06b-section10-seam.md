# Brief m5a-06b — the §10.11 seam and the §11 cross-references

```
gate:                M5 (early)
agent:               interface
goal:                The node model no longer contradicts itself at §10.11, and
                     §11's requested cross-references exist.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md sections 10.11 and 11
                      (§11.8 lists the exact requests), docs/adr/0009-*.md]
deliverable:         docs/interfaces/opcua-nodes.md — the §10.11 row and the
                     cross-references §11.8 requests
done_when:           §10.11's row keeps its invariant-1 half (no SAFETY PATH
                     under DemoCell/Forklift/ — the mirrors are read-only
                     diagnostics, never a reaction channel) while its expired
                     premise ("this plant has no F-CPU") is replaced per
                     ADR 0009, pointing at §11; the cross-references §11.8
                     names are added exactly; a subject sweep over "safety"
                     within section 10 finds no other statement resting on the
                     expired premise; nothing else changes.
forbidden:           [changing any §11 ruling or node row, editing plc/ or
                      hmi/, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the doc plus
your report docs/reports/m5a-06b-section10-seam.md; message style
`docs(interfaces): reconcile the forklift row with the mirror section`.
