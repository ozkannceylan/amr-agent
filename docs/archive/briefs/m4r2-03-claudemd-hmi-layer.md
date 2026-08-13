# Brief m4r2-03 — CLAUDE.md contract entries and hmi/ bootstrap

```
gate:                M4
agent:               infra (owner-approved for exactly these files, ADR 0005 precedent
                     for layer additions)
goal:                The hmi layer exists in the contract: topology, layout, roster,
                     boundary README and agent definition.
invariants_touched:  none — executes ADR 0008's accepted consequence
inputs:              [docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      CLAUDE.md, bridge/README.md (boundary-statement style),
                      .claude/agents/bridge.md (agent-definition style)]
deliverable:         the hmi layer's contract entry: CLAUDE.md §3/§4/§5 additions,
                     hmi/README.md, .claude/agents/hmi.md
done_when:           §3 topology shows an HMI node with a single edge
                     "OPC UA client to server" into the PLC labelled as process
                     setpoints only; §4 lists hmi/ with a one-line purpose; §5 roster
                     has row "hmi | Commissioning HMI backend and UI | hmi/";
                     hmi/README.md's first section is titled "This layer must not
                     access" and forbids: ROS 2 (rclpy/DDS), Gazebo and gz transport,
                     bridge/ internals, fleet manager internals, and writing any PLC
                     node outside the HMI-writable group; .claude/agents/hmi.md
                     mirrors the structure of an existing roster agent definition;
                     ADR 0008 is cited in the README.
forbidden:           [touching CLAUDE.md §2 invariants or the §6 gate table (roadmap
                      governs gate order, per the ADR 0004/0007 precedent), editing
                      other roster rows or other layers' READMEs, writing any code,
                      mentioning any deadline]
```

Notes:
- §3 addition: node `HMI["Commissioning HMI<br/>teleop setpoints and status<br/>process data only"]` with edge `HMI -->|OPC UA client to server| PLC`. Do not touch the safety edges or the legend beyond, if needed, one clause noting the HMI edge is process data.
- §4 placement: after the bridge/ line, before sim/: `hmi/                  commissioning HMI, OPC UA client of the PLC, process data only`.
- hmi/README.md second section states what the layer is: a local operator HMI streaming drive/steer/fork setpoints, enable, edge-evaluated reset request and a UInt16 heartbeat into HMI-writable PLC nodes; the PLC standard program owns all interlocks and watchdogs the heartbeat; this HMI is not a safety device.
- Git: repo-local owner identity; pathspec-scoped commit of exactly these files plus your report docs/reports/m4r2-03-claudemd-hmi-layer.md; message style `docs(infra): add the hmi layer to the contract`.
