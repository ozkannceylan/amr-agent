# Brief m5-02 — CLAUDE.md §3 topology gains the monitoring plane

```
gate:                M5
agent:               infra (owner-approved 2026-07-30)
goal:                the §3 topology diagram shows the read-only monitoring
                     plane ADR 0011 D4 admits, so invariant 11 reads against a
                     diagram that matches the architecture.
invariants_touched:  none changed. Invariant 11 refers to "the topology below";
                     ADR 0011 D4 is the authority for the edge being added, and
                     invariants 1-13 keep their text.
inputs:              [docs/adr/0011-sensored-autonomy-architecture.md (D4),
                      docs/adr/0005-bridge-layer-and-opcua-client.md,
                      CLAUDE.md sections 2 and 3]
deliverable:         CLAUDE.md section 3 only
done_when:           the mermaid diagram carries a monitoring service that
                     subscribes to the vehicle's ROS 2 graph and serves the
                     operator page read-only, drawn in a THIRD arrow style
                     distinct from both the safety path (thick) and the
                     process path (thin); the legend names all three styles
                     and states that the monitoring edge carries no command
                     and has no write endpoint; the existing HMI → PLC process
                     edge and every other edge are unchanged; the legend's
                     ADR 0008 citation is kept and an ADR 0011 citation added;
                     nothing outside section 3 changes.
forbidden:           [editing any other CLAUDE.md section, editing any other
                      file, altering invariant text, drawing the monitoring
                      edge as bidirectional or letting it touch the PLC,
                      deciding the service's directory (ADR 0011 leaves it
                      recommended-not-ruled), committing (the orchestrator
                      commits)]
```

Note: mermaid supports `-.->` (dashed, already used for PROFIsafe) and `==>`
(thick, already the safety path). A third distinct style is needed — consider
a labelled thin edge with a distinguishing marker, or `~~~`/link-style
statements; whichever you choose, the legend must make it unmistakable and the
diagram must still render. Verify the mermaid parses before finishing.

Do not commit. Leave CLAUDE.md modified and write your report to
docs/reports/m5-02-topology-monitoring-plane.md.
