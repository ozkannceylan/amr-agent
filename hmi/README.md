# hmi

## This layer must not access

Per ADR 0008 D2 and its consequences. Every item is a hard boundary, not a
preference.

- **ROS 2, in any form.** No `rclpy`, no DDS, no topic, service, action,
  message type or launch file. The HMI has no path to the vehicle software and
  no path to the plant except through the PLC (invariant 11).
- **Gazebo and `gz` transport.** No `gz-sim`, no partition, no world, model,
  link or joint name. What the plant looks like is not this layer's concern
  (invariant 11).
- **`bridge/` internals.** Nothing under `bridge/` is imported here and no
  state is shared with it. The bridge and the HMI are two independent OPC UA
  clients of the same server that call no code of each other's (ADR 0005,
  ADR 0008 D1).
- **Fleet manager internals.** Nothing under `fleet/` is imported, and no
  VDA 5050, MQTT, order, traffic or zone-reservation concept appears here
  (invariants 3, 5, 6). Homing the HMI inside `fleet/` was rejected in
  ADR 0008 precisely because it would have needed an exception carved into that
  layer's boundary statement.
- **Any PLC node outside the HMI-writable group.** The HMI writes the
  HMI-writable nodes and reads status nodes. `DemoCell/Input/*`,
  `DemoCell/Link/BridgeHeartbeat` and everything under the auto-published
  `DataBlocksGlobal` folder belong to other owners and are never written from
  here (invariant 10). The group's names, folder and access rights are an
  interface question that ADR 0008 leaves open; until `docs/interfaces/`
  settles them, the rule is still that nothing outside the group is touched.
- **Forming or writing any actuator output.** What this layer streams are
  *requests*. The PLC standard program forms every actuator setpoint from them
  and owns the outcome (invariants 5, 6; ADR 0008 D2.2).
- **Any interlock, latch, timer or sequencing logic.** Teleop routing, the
  fork-height speed cap, the fork soft travel limits and the lidar obstacle
  stop are process interlocks in the standard program (ADR 0008 D3). No verdict
  the PLC also computes is recomputed here (invariant 10).
- **Any safety function or safety path.** Nothing here is a safety device and
  nothing here carries safety integrity. The teleop interlocks implement no SRS
  function — not SF-02, SF-03, SF-04, SF-07, SF-09 (ADR 0008 D3) — and loss of
  this process is a degraded mode, never a safety event (invariants 1, 2).
- **The OPC UA server role.** The PLC is the server, this process is the
  client, and that direction is never inverted. The HMI holds no server and
  exposes no endpoint, in any configuration (invariant 4, ADR 0008 D2.1).
- **Remote transport of any kind.** ADR 0008 rules the *local* case only: same
  machine, same cell network. Tailscale is engineering access and never a data
  path (invariant 8), and the remote or assistant-originated operator path
  stays parked and unruled (ADR 0008 D2.7). Nothing here is precedent for it.
- **Hard real-time responsibilities.** Deterministic timing lives in PLC logic
  or vehicle firmware, never in this process (invariant 9).
- **Secrets.** Endpoint credentials, certificates and keys live outside this
  repository and are referenced by absolute path (invariant 13).

Owns: the operator-side setpoint stream for the forklift commissioning cell —
the OPC UA client session that writes the HMI-writable nodes, the heartbeat
that session carries, and the operator interface that produces both.

---

## What it is

A **local commissioning HMI**: one process that is an **OPC UA client** of the
S7-1500 and nothing else, driven by an operator standing at the same machine.
It streams into the HMI-writable node group:

- drive, steer and fork jog **setpoints**;
- an **enable**;
- a **reset request**, carried as a level and edge-evaluated in the standard
  program rather than here — the M3 rule that the edge and the hold belong to
  the program, never to the client;
- a `UInt16` **heartbeat**.

```
   operator                                   S7-1500 / PLCSIM (OPC UA server)
       |                                                   ^
       |  setpoints, enable, reset request, heartbeat      | client session
       v                                                   |
   +-----------------------------------------------------------------+
   |  hmi process                                                    |
   |  UI -> request values -> writes into the HMI-writable group     |
   |  reads status nodes; forms no actuator output, holds no verdict |
   +-----------------------------------------------------------------+
```

Every command reaches the plant as **HMI to PLC to bridge to Gazebo**, and
every state report returns **Gazebo to bridge to PLC** (ADR 0008 D1). No
command reaches the simulation without passing through PLC logic, and this
layer has no second path to it.

**The PLC owns the outcome.** The standard program applies the interlocks of
ADR 0008 D3 and watchdogs the heartbeat; loss of that heartbeat drives every
motion setpoint to zero in a mandatory `ELSE` branch, the gating discipline of
`plc/demo-cell/SPEC.md` §6.4 rather than a conditional write. That is
invariant 2's controlled stop applied at the operator boundary — losing the
link is a degraded mode, never a safety event. **This HMI is not a safety
device.**

**The heartbeat obligation is one-sided.** The HMI's job is to make the counter
change every cycle. The verdict is the PLC's, under the `BridgeHeartbeat` rules
of `plc/demo-cell/SPEC.md` §6.1: compared for inequality only, never
subtracted, never assumed monotonic, wrap-safe — and FALSE until the counter
has been seen to change at least once, because "not yet proven stale" is not
"alive" (`docs/LESSONS.md`, 2026-07-28).

**A setpoint stream, not a command handshake.** What is ruled here is a
continuous stream of process setpoints under a watchdog. It is not the discrete
request/`Ready`/`Busy`/`Done`/`Fault` handshake sketched for a remote
originator in `docs/reports/m4-00-hermes-survey.md` §5. The two are different
contracts and neither substitutes for the other (ADR 0008 D2.4).

The layer exists as a boundary statement first; its implementation lands with
the forklift commissioning gate of ADR 0008 D1, whose live number is carried by
`docs/roadmap.md`.

## Known limitation, recorded rather than discovered later

Per-tag writability **is** enforced by the CPU (`plc/demo-cell/SPEC.md` §4.2),
so a tag this layer must not write is refused by the server. Per-*client*
scoping is **not**: the commissioned CPU runs with access control disabled and
security `None` as a deliberate demonstration setting
(`docs/interfaces/opcua-nodes.md` §9.10). "Only the HMI writes the HMI group"
is therefore policy honoured by the client, exactly as the bridge's allowlist
is, and two writing clients instead of one make that gap materially wider. It
is not closed by ADR 0008 (D2.5).

## What this layer does not decide

- The HMI-writable node names, their folder and their access rights — an
  interface question, owned by `docs/interfaces/`.
- The implementation technology, beyond the constraints above. ADR 0008
  rejected a WinCC screen in TIA Portal on the ground that it produces no
  repository artifact a reader can inspect, diff or run.
- Anything about the remote operator path, which stays parked behind its own
  ADR.
