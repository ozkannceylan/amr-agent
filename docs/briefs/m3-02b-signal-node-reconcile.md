gate:                M3
agent:               interface
goal:                The OPC UA demonstration cell section and the sim signal table describe the same signal set, one node per signal, no orphans.
invariants_touched:  none
inputs:              [sim/README.md "Demonstration cell (M3)" signal table, docs/interfaces/opcua-nodes.md section 9, docs/reports/m3-01-fixed-equipment-world.md open questions]
deliverable:         docs/interfaces/opcua-nodes.md section 9, reconciled
done_when:           Every sim signal that is a PLC signal has exactly one node and every node has exactly one sim signal; the photo-eye's raw distance is converted to a bit at a stated threshold owned by a stated layer; belt encoder decimation is stated as an interface expectation; ground-truth-only topics are explicitly excluded from the node set; the process-stop naming matches ADR 0004; any signal the sim publishes but the PLC does not need is listed as deliberately absent.
forbidden:           [adding logic, sequencing or interlocks to the node model, promoting ground truth to a node, renaming ADR-mandated process-stop terminology, editing directories other than docs/interfaces/ and the report]
