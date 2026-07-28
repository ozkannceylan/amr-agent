# Brief m4f-05 — bridge design addendum: forklift signal groups

```
gate:                M4
agent:               interface
goal:                docs/interfaces/bridge-design.md specifies the forklift signal
                     groups and the generalized output section before any bridge
                     code changes (design-before-code, the m3-03 precedent).
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md section 10 (authoritative
                      node set), docs/interfaces/bridge-design.md,
                      bridge/config/bridge.yaml (current schema),
                      docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md]
deliverable:         docs/interfaces/bridge-design.md (revised)
done_when:           the design states: the outputs section becomes plural (N
                     output slots, each with node path, ROS topic and type); the
                     forklift vehicle-input slots and their ROS topics; the
                     forklift status nodes the bridge reads for diagnostics; the
                     explicit statement that the bridge NEVER reads or writes the
                     HMI-written nodes (single-writer rule, invariant 10 — the hmi
                     layer is their only writer); the write-allowlist consequence;
                     what the test double must serve so conformance covers the new
                     groups; and the unchanged properties (20 Hz cycle, per-session
                     evidence, reconnect and rewrite-on-restart semantics now also
                     covering the new slots). Every section it touches stays
                     consistent with the sections it does not (staleness-sweep
                     discipline from LESSONS).
forbidden:           [writing bridge code or editing bridge/ files, changing the
                      cell slot definitions, adding value types beyond
                      Real/Bool/UInt16, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the design doc
plus your report docs/reports/m4f-05-bridge-design-forklift.md; message style
`docs(interfaces): extend the bridge design with the forklift signal groups`.
