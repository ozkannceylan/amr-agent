# Brief m4f-04g — the SPEC's §6.5 caveat becomes agreement

```
gate:                M4
agent:               plc
goal:                SPEC section 6.5 no longer quotes a replaced wording as a
                     live caveat.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md section 10.7 as amended by
                      1618dff, plc/forklift/SPEC.md section 6.5,
                      docs/reports/m4f-01f-speedlimit-flag-reading.md]
deliverable:         plc/forklift/SPEC.md — the one section 6.5 sentence that
                     quotes the old section 10.7 wording and calls it "could be
                     read as the narrower verdict"
done_when:           the sentence records agreement instead: section 10.7 now
                     states the wide in-force reading this specification
                     implements (1618dff), the caveat withdrawn; SCL,
                     constants, tags, step tables and every other sentence
                     byte-identical (statement-line count as before); a
                     subject sweep over the flag's name in the SPEC finds no
                     other sentence still describing the interface doc as
                     ambiguous.
forbidden:           [any other SPEC change, editing plc/forklift/double/ or
                      docs/interfaces/, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly SPEC.md plus
your report docs/reports/m4f-04g-spec-caveat-agreement.md; message style
`docs(plc): withdraw the caveat the interface ruling resolved`.
