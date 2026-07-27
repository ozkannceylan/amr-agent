# OPC UA node model — S7-1500 server, fleet manager client

Gate M1. Defines every node the PLC serves and the fleet manager consumes for one warehouse cell:
one conveyor transfer station, one automatic door, one charging station, plus cell-level status.
Handshake **sequencing** (who sets which bit when) is specified in m1-03; this document defines the nodes only.

## 1. Direction rule

| Rule | Statement |
|---|---|
| Server/client | The PLC is the OPC UA server. The fleet manager is the client. Never inverted (invariant 4). |
| No actuator writes | The fleet manager never writes actuator commands. It writes only handshake/request bits and its own heartbeat. Actuator outputs are formed inside the PLC from the cycle-running flag and interlocks (invariant 6). |
| No fleet data on the PLC | No order IDs, traffic state or zone reservations live on the PLC (invariant 5). The only fleet-originated identifier is the opaque handshake token per station. |
| Not a safety path | Every node here is process data. Safety functions run onboard the vehicle and in the F-CPU over PROFIsafe (invariant 1). Loss of this OPC UA link is a degraded mode, not a safety event (invariant 2). |

## 2. Namespace and folder layout

Server interface exported from TIA Portal. Namespace URI: `urn:amr-agent:cell:plc`
(namespace index is assigned at session establishment; the client browses by URI, never hardcodes the index).

```
Cell/                cell-level status and supervision heartbeats
Safety/              read-only informational mirrors of F-CPU status
Conveyor/            conveyor transfer station status
Conveyor/Handshake/  request/acknowledge nodes for the transfer station
Door/                automatic door status
Door/Handshake/      request/acknowledge nodes for door passage
Charger/             charging station status
Charger/Handshake/   request/acknowledge nodes for charging
```

Conventions for all tables below:

- **BrowseName** is PascalCase, physical thing + meaning, and mirrors the PLC tag name exactly (CLAUDE.md section 9) so this document and the TIA export can be diffed.
- **Access** is from the client's (fleet manager's) view: `R` or `R/W`.
- **Owner** is the single source of truth (invariant 10). Only the owner writes the value; the other side never recomputes it locally.
- **Update**: `on-change` = subscribed monitored item, report on value change; `cyclic` = subscribed with fixed sampling (heartbeats, analog values). Suggested sampling interval 100 ms, publish interval 250 ms.

## 3. Cell/

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| CellOperatingMode | Int | Int16 | R | on-change | PLC | 0 = off, 1 = manual, 2 = automatic |
| CellAlarmActive | Bool | Boolean | R | on-change | PLC | Any standard-program alarm pending |
| CellHeartbeatPlc | UInt | UInt16 | R | cyclic | PLC | PLC-incremented counter; client supervises server liveness |
| CellHeartbeatFleet | UInt | UInt16 | R/W | cyclic | Fleet | Client-incremented counter; PLC supervises client liveness. Loss triggers degraded mode only, never a safety reaction |
| ZoneAOccupied | Bool | Boolean | R | on-change | PLC | Zone A occupancy measured by PLC-wired sensors. PLC-owned because the sensors are the PLC's. Not a reservation: zone reservation logic lives in the fleet manager and is not exposed here |

## 4. Safety/ — informational mirrors only

These nodes are **read-only process information mirrored from the F-CPU status**. They exist for
dashboards, logging and fleet-side diagnostics. They are **not a safety path**: the F-CPU executes
all safety reactions independently over PROFIsafe and hardwired channels, regardless of whether any
client reads these nodes (invariants 1, 7). No client decision may substitute for a safety function.

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| EStopActive | Bool | Boolean | R | on-change | PLC (mirror of F-CPU) | E-stop chain tripped |
| ProtectiveStopActive | Bool | Boolean | R | on-change | PLC (mirror of F-CPU) | Protective stop in effect |
| SafetyDoorClosed | Bool | Boolean | R | on-change | PLC (mirror of F-CPU) | Safety door position (wire NC, program NO: signal high = closed and healthy) |
| SafetyResetRequired | Bool | Boolean | R | on-change | PLC (mirror of F-CPU) | A monitored manual reset is pending; no restart happens over OPC UA |

## 5. Conveyor/

### Status

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| ConveyorRunning | Bool | Boolean | R | on-change | PLC | Conveyor motor running |
| ConveyorFault | Bool | Boolean | R | on-change | PLC | Drive or sequence fault |
| ConveyorPalletPresent | Bool | Boolean | R | on-change | PLC | Load present at transfer position (PLC sensor) |

### Conveyor/Handshake/

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| TransferRequest | Bool | Boolean | R/W | on-change | Fleet | Client requests a transfer at this station. Request bit only — the PLC decides whether and when to act, from its interlocks |
| TransferDirection | Int | Int16 | R/W | on-change | Fleet | 0 = station to vehicle, 1 = vehicle to station. Valid only while TransferRequest is set |
| TransferToken | String[16] | String | R/W | on-change | Fleet | Opaque correlation token written by the client with the request. The PLC never parses it; it is not an order ID to the PLC |
| TransferTokenAck | String[16] | String | R | on-change | PLC | PLC echo of the token it is currently serving, for client-side correlation |
| TransferReady | Bool | Boolean | R | on-change | PLC | Station ready to execute the requested transfer (interlocks satisfied) |
| TransferBusy | Bool | Boolean | R | on-change | PLC | Transfer in progress |
| TransferDone | Bool | Boolean | R | on-change | PLC | Transfer completed; held until the client withdraws the request (level, not edge — survives a restart) |
| TransferFault | Bool | Boolean | R | on-change | PLC | Transfer aborted or failed |
| TransferSeqPlc | UInt | UInt16 | R | cyclic | PLC | PLC handshake sequence counter |
| TransferSeqFleet | UInt | UInt16 | R/W | cyclic | Fleet | Client handshake sequence counter |

## 6. Door/

### Status

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| DoorOpen | Bool | Boolean | R | on-change | PLC | Door at open end position (PLC sensor) |
| DoorClosed | Bool | Boolean | R | on-change | PLC | Door at closed end position (PLC sensor) |
| DoorFault | Bool | Boolean | R | on-change | PLC | Door drive or sequence fault |
| DoorwayClear | Bool | Boolean | R | on-change | PLC | Doorway clearance measured by a PLC-side sensor. Informational input to handshake sequencing (m1-03); not a safety path — safety clearance monitoring belongs to the F-CPU (invariant 1) |

### Door/Handshake/

The client requests **passage**, never "motor on". Opening, holding and closing are PLC sequence
logic formed from interlocks (including the F-CPU-mirrored safety state).

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| PassageRequest | Bool | Boolean | R/W | on-change | Fleet | Client requests door passage for a vehicle |
| PassageToken | String[16] | String | R/W | on-change | Fleet | Opaque correlation token, as for the conveyor |
| PassageTokenAck | String[16] | String | R | on-change | PLC | PLC echo of the token being served |
| PassageReady | Bool | Boolean | R | on-change | PLC | Door open and held; vehicle may pass |
| PassageBusy | Bool | Boolean | R | on-change | PLC | Door moving or passage in progress |
| PassageDone | Bool | Boolean | R | on-change | PLC | Passage complete, door closed again; held until request withdrawn |
| PassageFault | Bool | Boolean | R | on-change | PLC | Passage aborted or failed |
| PassageSeqPlc | UInt | UInt16 | R | cyclic | PLC | PLC handshake sequence counter |
| PassageSeqFleet | UInt | UInt16 | R/W | cyclic | Fleet | Client handshake sequence counter |

## 7. Charger/

### Status

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| ChargerAvailable | Bool | Boolean | R | on-change | PLC | Bay free and charger healthy |
| ChargerContactorClosed | Bool | Boolean | R | on-change | PLC | Charge contactor closed (informational; the closing decision is PLC interlock logic) |
| ChargerOutputCurrent | Real | Float | R | cyclic | PLC | Measured charge current, A |
| ChargerFault | Bool | Boolean | R | on-change | PLC | Charger fault |
| ChargerVehicleDocked | Bool | Boolean | R | on-change | PLC | Diagnostic: vehicle detected in the docked position by the PLC's own sensor |

### Charger/Handshake/

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| ChargeRequest | Bool | Boolean | R/W | on-change | Fleet | Client requests charging for the docked vehicle. The PLC closes the contactor only when its own interlocks confirm docking |
| ChargeToken | String[16] | String | R/W | on-change | Fleet | Opaque correlation token |
| ChargeTokenAck | String[16] | String | R | on-change | PLC | PLC echo of the token being served |
| ChargeReady | Bool | Boolean | R | on-change | PLC | Bay interlocks satisfied, charging can start |
| ChargeBusy | Bool | Boolean | R | on-change | PLC | Charging in progress |
| ChargeDone | Bool | Boolean | R | on-change | PLC | Charging ended normally; held until request withdrawn |
| ChargeFault | Bool | Boolean | R | on-change | PLC | Charging aborted or failed |
| ChargeSeqPlc | UInt | UInt16 | R | cyclic | PLC | PLC handshake sequence counter |
| ChargeSeqFleet | UInt | UInt16 | R/W | cyclic | Fleet | Client handshake sequence counter |

## 8. Deliberately absent

| Not on the server | Why |
|---|---|
| Order IDs, order state, transport assignments | Fleet manager data; VDA 5050 over MQTT carries it (invariants 3, 5) |
| Zone reservation / traffic nodes | Fleet manager logic; the PLC only reports what its own sensors measure (ZoneAOccupied) |
| Actuator command nodes (motor on, door open, contactor close) | The client may only request; outputs are formed in the PLC from interlocks (invariant 6) |
| Safety commands (e-stop trigger, reset, override) | Safety never traverses the network (invariant 1); reset is a local monitored reset |
| Vehicle state (position, battery, mode) | Vehicle data flows AGV → MQTT → fleet manager; the PLC is not on that path (invariant 11) |

## 9. Demonstration cell I/O (M3)

Added by ADR 0004, which proves the Gazebo-to-PLC signal loop before any mobile robot work.
The demonstration cell is **fixed equipment only**: one conveyor, one product sensor, one operator
panel equivalent (Start, Stop, process E-stop). The client here is the **bridge** — a ROS 2 node and
OPC UA client that translates between Gazebo and the PLC, and nothing else.

Sections 3–7 above describe the target cell served to the **fleet manager**. This section describes
the M3 demonstration cell served to the **bridge**. Both live on the same server under the same
namespace URI `urn:amr-agent:cell:plc`; no node is shared between the two sets and they are never merged.

This section defines **nodes only**. Conveyor control, reset behaviour, fault detection and the
reaction to a stale bridge heartbeat are PLC standard-program content (`plc/demo-cell/SPEC.md`).
No logic, sequencing, latching or timer is defined here, and none belongs in the bridge (ADR 0004).

### 9.1 Direction rule for the bridge

| Rule | Statement |
|---|---|
| Server/client | The PLC is the OPC UA server. The bridge is a client. Never inverted (invariant 4). |
| What the bridge writes | **Only** the `DemoCell/Input/` nodes (the PLC's input image) and `DemoCell/Link/BridgeHeartbeat`. Nothing else on the server is client-writable. |
| No actuator writes | The bridge **never** writes an actuator output node. `ConveyorRunCommand` and every other output is formed inside the PLC from its cycle-running flag and interlocks (invariant 6). The bridge reads it and applies it to the simulated actuator unchanged. |
| No logic in the bridge | The bridge is a signal translator: no sequencing, interlocks, timers, latching or debounce that changes meaning (ADR 0004). If logic appears to be needed, it belongs in the PLC (invariants 5, 6). |
| Single owner | Every input bit is owned by the Gazebo cell and only ever written by the bridge; every output and status bit is owned by the PLC. Neither side recomputes the other's value (invariant 10). |
| Not a safety path | Every node in this section is process data. The demonstration E-stop is a **process stop** (§9.6). No safety function traverses OPC UA (invariant 1, SRS B1). |

### 9.2 Folder layout and conventions

```
DemoCell/            demonstration cell (M3), served to the bridge
DemoCell/Input/      cell → PLC: input-image bits written by the bridge
DemoCell/Output/     PLC → cell: output bits the bridge applies to simulated actuators
DemoCell/Status/     PLC → bridge: read-only status for diagnostics and the watch table
DemoCell/Link/       bridge liveness
```

Column conventions are those of section 2. Two additions for this section:

- **Access** is from the **bridge's** view (the client), not the fleet manager's.
- For client-written nodes, `on-change` means: written when the source ROS 2 signal changes value,
  plus a full refresh of all `DemoCell/Input/` nodes on every (re)connect.

### 9.3 DemoCell/Input/ — cell → PLC input image (bridge writes)

Owner is the Gazebo cell; the bridge is the transport, not the source. These nodes are the PLC's
input image: the standard program reads them exactly as it would read wired field inputs.

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| ProductPresentAtSensor | Bool | Boolean | R/W | on-change | Gazebo cell (via bridge) | Product detected at the conveyor's product sensor. Presence sensor, NO analogue: 1 = product present |
| ConveyorMotorRunningFeedback | Bool | Boolean | R/W | on-change | Gazebo cell (via bridge) | The simulated drive reports it is actually turning. Feedback, never a command; the PLC compares it with its own output. Present only if the m3-01 world publishes it — if the sim provides no drive feedback, this node is omitted rather than synthesized by the bridge |
| PanelStartPressed | Bool | Boolean | R/W | on-change | Gazebo cell (via bridge) | Start pushbutton actuated. Start devices are wired NO: 1 = pressed. Momentary level; the PLC forms any edge it needs, the bridge never latches or stretches it |
| PanelStopCircuitClosed | Bool | Boolean | R/W | on-change | Gazebo cell (via bridge) | Process stop pushbutton. **Wire NC, program NO** (CLAUDE.md §9): 1 = circuit closed, button not actuated; 0 = actuated, or wire broken, or signal absent |
| PanelEmergencyStopCircuitClosed | Bool | Boolean | R/W | on-change | Gazebo cell (via bridge) | Demonstration panel E-stop mushroom, **process stop only** (§9.6). Wire NC, program NO: 1 = closed, 0 = actuated. Not a safety function and carries no SIL/PL claim |

Stop devices are named for the **circuit state**, not for the button, so that the tag reads true when
the machine is permitted to run and false in every failure case. A tag named `…Pressed` would invert
the NC convention and make a dead signal look healthy.

### 9.4 DemoCell/Output/ — PLC → cell (bridge reads, never writes)

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| ConveyorRunCommand | Bool | Boolean | R | on-change | PLC | Conveyor drive command. Formed inside the PLC from its cycle-running flag combined with interlocks — never driven directly from a sensor (CLAUDE.md §9). The bridge applies it to the simulated conveyor actuator unchanged, with no added condition |

### 9.5 DemoCell/Status/ — PLC state, read-only diagnostics

Read by the bridge for logging and by the owner in the TIA watch table. Not applied to any simulated
actuator. Machine state and actuator command are separate layers (CLAUDE.md §9), which is why
`CellCycleRunning` is a distinct node from `ConveyorRunCommand`.

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| CellCycleRunning | Bool | Boolean | R | on-change | PLC | Standard-program cycle-running flag: the cell is enabled. Level, survives a restart of the bridge |
| CellProcessStopActive | Bool | Boolean | R | on-change | PLC | A **process** stop is latched in the standard program (panel Stop or panel E-stop). Not a safety state; no SF of docs/safety/SRS.md is represented here |
| CellResetRequired | Bool | Boolean | R | on-change | PLC | A monitored, edge-triggered local reset is pending before the cycle may run again. No reset is performed over OPC UA; no node in this section can clear it |
| ConveyorDriveFault | Bool | Boolean | R | on-change | PLC | PLC verdict on command-versus-feedback disagreement. The criterion is PLC logic and is not defined here |

### 9.6 The demonstration E-stop is a PROCESS stop

| Statement | Detail |
|---|---|
| What it is | `PanelEmergencyStopCircuitClosed` is a **process stop input** to the S7-1500 **standard** program. It stops the demonstration conveyor by ordinary program logic. |
| What it is not | It is **not a safety function**. It appears nowhere in docs/safety/SRS.md §3, carries no SIL/PL claim, and must be labelled a process stop in every document, tag name, watch table and recording (ADR 0004). |
| SF-01 is unaffected | The real cell e-stop chain (SRS SF-01) is executed by the F-CPU on two-channel NC F-I/O over PROFIsafe and hardwired channels. It never travels over OPC UA and is not represented by any node in this section (invariant 1, SRS B1, B3). The demonstration cell has no F-CPU. |
| No mirror either | Unlike §4, this section carries no safety mirror. `Safety/EStopActive` in §4 remains the only informational mirror of SF-01, and remains read-only and outside every causal chain. |

### 9.7 DemoCell/Link/ — bridge liveness

The input-image nodes retain their last written value on the server, so a stopped bridge is not
detectable from the input bits alone. That is the reason this node pair exists.

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| BridgeHeartbeat | UInt | UInt16 | R/W | cyclic | Bridge | Counter incremented by the bridge on every write cycle, wrapping at the type limit. Its only meaning is "the bridge wrote recently". It is the sole node outside `DemoCell/Input/` that the bridge may write |
| BridgeLinkOk | Bool | Boolean | R | on-change | PLC | The PLC's own verdict that the heartbeat is advancing. Published for the bridge's logging and the watch table |

**Reaction is PLC program content.** The staleness criterion for `BridgeHeartbeat`, the value of
`BridgeLinkOk`, and what the equipment does when the heartbeat stops are specified in
`plc/demo-cell/SPEC.md` and implemented in the standard program. No timer, threshold or reaction is
defined in this document, and none of it is in the bridge. Loss of the bridge is a degraded mode,
not a safety event (invariant 2), and nothing about it is a safety function.

### 9.8 Deliberately absent from DemoCell/

| Not on the server | Why |
|---|---|
| A client-writable conveyor command node | The bridge may never write an actuator output; the PLC forms outputs from interlocks (invariant 6) |
| Any safety node, mirror or reset | Safety never traverses the network (invariant 1); the demonstration cell has no F-CPU and no SF |
| Timers, step numbers, latch state exposed for the bridge | Logic and sequencing belong to the PLC; exposing them would invite the bridge to act on them (ADR 0004) |
| Vehicle, order or fleet data | No vehicle exists in M3 (ADR 0004); fleet data never lives on the PLC (invariants 3, 5) |
