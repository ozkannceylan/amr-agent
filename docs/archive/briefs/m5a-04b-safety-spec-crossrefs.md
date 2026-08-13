# Brief m5a-04b — the safety SPEC learns the mirror ruling

```
gate:                M5 (early)
agent:               plc
goal:                plc/forklift-safety/SPEC.md's open notes are closed against
                     the interface ruling they waited for.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md section 11 (the ruling:
                      DemoCell/Forklift/Safety/, DB ForkliftSafetyMirror, the
                      four node names and start values),
                      plc/forklift-safety/SPEC.md sections 6.4 and 10]
deliverable:         plc/forklift-safety/SPEC.md — section 6.4 notes 1-3 and
                     section 10 item 4
done_when:           the notes cite section 11's ruling instead of describing
                     it as pending (path, DB name, per-tag access, start
                     values); every other section byte-identical (verify as the
                     spec's own discipline requires); a sweep over "mirror" in
                     the file finds no sentence still calling the ruling open.
forbidden:           [changing any network description, tag, constant or T6
                      step, editing docs/interfaces/, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly SPEC.md plus
your report docs/reports/m5a-04b-safety-spec-crossrefs.md; message style
`docs(plc): close the mirror notes against the interface ruling`.
