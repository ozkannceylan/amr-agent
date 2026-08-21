# m1/ — Milestone 1: the interface contracts

**Closed 2026-07-26, verified PASS (after one remediation round) in
[`docs/archive/reports/m1-04-verify.md`](../docs/archive/reports/m1-04-verify.md).**

M1 wrote no code. It wrote the contracts every later milestone codes
against — and they are **live documents**: the current system
(`m5_ver2/step5`, `m6/`) still implements them, and the M8 vendor-portability
gate's drift check reads them as its reference.

| Contract | Where | What it pins |
|---|---|---|
| VDA 5050 subset | [`docs/interfaces/vda5050-subset.md`](../docs/interfaces/vda5050-subset.md) | The order/state message subset, pinned to VDA 5050 tag **2.1.0**; every omitted field named; connection loss mapped to degraded mode, never to a safety path |
| OPC UA node model | [`docs/interfaces/opcua-nodes.md`](../docs/interfaces/opcua-nodes.md) | **49 nodes**, each with exactly one owner; exactly **11 fleet-writable** request/handshake bits and **zero** actuator commands crossing the seam; the PLC serves, the fleet is a client |
| Handshake tables | [`docs/interfaces/handshake-tables.md`](../docs/interfaces/handshake-tables.md) | **35 step rows** of station/docking handshakes; monitored restart, no auto-resume, levels not edges; no PLC↔AGV direct path |
| Bridge design | [`docs/interfaces/bridge-design.md`](../docs/interfaces/bridge-design.md) | The ROS 2 ↔ OPC UA translator's contract (commissioning-era; amended through M3–M5) |

## What the gate measured

The verifier's round 1 found the contracts individually sound but
**cross-document inconsistent** — the m1-02 node revision
(`DoorwayClear`, `ChargerVehicleDocked`) had not propagated into the
handshake tables, and two state fields lacked owner rows. Remediation
(commits `a2d571d`, `72640db`) closed it; round 2 passed with all 49
nodes covered in the ownership map, zero unresolved identifiers, zero
double ownership.

The invariants these contracts encode (safety never on the network, one
writer per datum, the PLC as the only OPC UA server) are ADR 0001's —
see [`docs/adr/`](../docs/adr/).

## Media

None — a paper milestone by design. The first thing this project
*recorded* is [M3's cell](../m3/).
