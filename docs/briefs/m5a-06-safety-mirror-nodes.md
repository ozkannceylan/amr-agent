# Brief m5a-06 — the Safety/ mirror node group

```
gate:                M5 (early)
agent:               interface
goal:                The node model carries the read-only Safety/ mirror group
                     for the forklift twin.
invariants_touched:  none — mirrors are diagnostics; the safety path never
                     traverses the network (ADR 0009 D3)
inputs:              [docs/adr/0009-*.md, plc/forklift-safety/SPEC.md sections
                      3 and 6 (authoritative for the F-side names — check it
                      exists; if the concurrent plc agent has not landed it,
                      wait for it or state names as proposed and flag),
                      docs/interfaces/opcua-nodes.md]
deliverable:         docs/interfaces/opcua-nodes.md — new section 11,
                     "Forklift safety mirrors (M5 early)"
done_when:           the mirror nodes are defined (SafetyEStopDemand,
                     SafetyZoneStopDemand, SafetyResetRequired — final names
                     per the F-spec's coupling contract), each: Bool,
                     writer = the PLC standard program copying F-data,
                     readers = HMI and diagnostics, Accessible yes / Writable
                     NO for every client; the section states in its first
                     lines that the mirrors are display diagnostics, that no
                     client write can create, prevent or clear a safety
                     reaction, and that the safety demand never traverses the
                     network — the mirror of it does; DemoCell interface
                     extension per the ADR 0006 discipline, nothing renamed;
                     the TIA click-path row follows the section 10 pattern.
forbidden:           [renaming anything, changing section 10, value types
                      beyond Bool, editing plc/ or hmi/, mentioning any
                      deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the doc plus
your report docs/reports/m5a-06-safety-mirror-nodes.md; message style
`docs(interfaces): add the forklift safety mirror group`.
