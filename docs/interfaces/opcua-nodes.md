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

## 2. Namespace, browse path and folder layout

Server interface exported from TIA Portal. Namespace URI: `http://DemoCell`
(namespace index is assigned at session establishment; the client browses by URI, never hardcodes the index).

The URI is **not chosen here**: TIA Portal derives a server interface's namespace URI as
`http://<interface name>` and the field is not editable, so naming the interface `DemoCell` is what
produces `http://DemoCell`. There is **one namespace per server interface** — a second interface
carries its own derived URI and none is shared (ADR 0006).

### 2.1 Browse path — a server interface is not a child of Objects

Owner-verified in the tool at commissioning phase 0, 2026-07-27 (full environment record in §9.10).
The interface node does **not** hang directly under `Objects`. The S7-1500 places every server
interface inside a folder that belongs to a *Siemens* namespace, not to the interface's own:

```
Objects                        standard OPC UA namespace
  ServerInterfaces             namespace http://www.siemens.com/simatic-s7-opcua
    DemoCell                   namespace http://DemoCell
      Input/ Output/ Status/ Link/      the M3 demonstration-cell nodes (§9.2)
      Forklift/                         the M4 forklift commissioning nodes (§10.3)
```

| Rule | Statement |
|---|---|
| Resolve **both** namespaces by URI | A client resolves two indices at connect time: `http://www.siemens.com/simatic-s7-opcua` for the `ServerInterfaces` folder and `http://DemoCell` for the interface node and everything below it. Both are resolved by URI at session establishment; neither index is ever hardcoded (ADR 0006 D4). |
| The parent folder does not share the interface namespace | Reusing the interface's index for `ServerInterfaces` fails to browse. The two indices are unrelated and must be kept distinct. |
| Paths in this document are relative to the interface node | A path written `DemoCell/Input/ConveyorBeltPosition` is `Objects/ServerInterfaces/DemoCell/Input/ConveyorBeltPosition` in full. The folder trees below (§2.2, §9.2) start at the interface node, never at `Objects`. |
| A second interface is a sibling, not a child | The future fleet-facing interface (§9, ADR 0006 D3) appears in the same `ServerInterfaces` folder under its own name, carrying its own derived URI. Resolving one interface's namespace never yields the other's. |

A wrong or absent interface still presents as "namespace not found" at every connect, which remains
the intended failure mode. What changes is that there are now two lookups that can fail that way.

### 2.2 Folder layout

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
- **Update**: `on-change` = subscribed monitored item, report on value change; `cyclic` = subscribed with fixed sampling (heartbeats, analog values). Requested sampling interval 100 ms, requested publish interval 250 ms.
- **A requested session parameter is a request, not a setting.** `CreateSession` returns a *revised* session timeout, `CreateSubscription` a revised publishing interval and `CreateMonitoredItems` a revised sampling interval, and the server is free to grant less than was asked for. Every interval in this document is therefore what a client **asks** for. The client reads the granted value out of the response and derives its own timing — keep-alive, staleness limits, supervision windows — from **that** value, never from the value it requested. The bridge's connect sequence and the keep-alive it derives from the granted session timeout are specified in `docs/interfaces/bridge-design.md` (m3-19), which is where the observed granted values are recorded.

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

Each row below means "no such node **on this server interface**". The S7-1500 also auto-publishes its
global data blocks under a separate `DataBlocksGlobal` folder in its own namespace, which is outside
this contract and does not contradict these rows — see §9.8, where the same scoping is stated for the
commissioned demonstration interface.

| Not on this interface | Why |
|---|---|
| Order IDs, order state, transport assignments | Fleet manager data; VDA 5050 over MQTT carries it (invariants 3, 5) |
| Zone reservation / traffic nodes | Fleet manager logic; the PLC only reports what its own sensors measure (ZoneAOccupied) |
| Actuator command nodes (motor on, door open, contactor close) | The client may only request; outputs are formed in the PLC from interlocks (invariant 6) |
| Safety commands (e-stop trigger, reset, override) | Safety never traverses the network (invariant 1); reset is a local monitored reset |
| Vehicle state (position, battery, mode) | Vehicle data flows AGV → MQTT → fleet manager; the PLC is not on that path (invariant 11) |

## 9. Demonstration cell I/O (M3)

Added by ADR 0004, which proves the Gazebo-to-PLC signal loop before any mobile robot work.
The demonstration cell is **fixed equipment only**: one conveyor, one product sensor, one operator
panel (Start, Stop, Reset, process stop). The client here is the **bridge** — a ROS 2 node and
OPC UA client that translates between Gazebo and the PLC, and nothing else.

The authoritative signal list is the **signal table in `sim/README.md` § "Demonstration cell (M3)"**
(m3-01). Sections 9.3 and 9.4 below are in exact one-to-one correspondence with its PLC rows;
§9.9 records that reconciliation and §9.8 records what the cell publishes but the PLC does not receive.

Sections 3–7 above describe the target cell served to the **fleet manager**. This section describes
the M3 demonstration cell served to the **bridge**. The nodes below live on the `DemoCell` server
interface, namespace URI `http://DemoCell`, reached at `Objects/ServerInterfaces/DemoCell`
(§2.1 — the interface is not a child of `Objects`). A fleet-facing interface is a **separate server
interface** and carries its own URI, derived the same way from its own name: each server interface
has exactly one namespace and the two sets cannot share one (ADR 0006). No node is shared between the
two sets and they are never merged.

This section defines **nodes only**. Conveyor control, reset behaviour, fault detection and the
reaction to a stale bridge heartbeat are PLC standard-program content (`plc/demo-cell/SPEC.md`).
No logic, sequencing, latching or timer is defined here, and none belongs in the bridge (ADR 0004).

### 9.1 Direction rule for the bridge

| Rule | Statement |
|---|---|
| Server/client | The PLC is the OPC UA server. The bridge is a client. Never inverted (invariant 4). |
| What the bridge writes | **Only** the `DemoCell/Input/` nodes (the PLC's input image) and `DemoCell/Link/BridgeHeartbeat`. Nothing else **in the §9 node set** is client-writable, and the bridge writes nothing outside the `DemoCell` interface — in particular nothing under the auto-published `DataBlocksGlobal` folder, which is not part of this contract and, at the commissioned access settings (§9.10), is not write-protected by the server either. The restriction is the bridge's contract, honoured by the client; it is not enforced by the server today (§9.8 open item). |
| No actuator writes | The bridge **never** writes an actuator output node. `ConveyorSpeedCommand` and every other output is formed inside the PLC from its cycle-running flag and interlocks (invariant 6). The bridge reads it and applies it to the simulated actuator unchanged. |
| No logic in the bridge | The bridge is a signal translator: no sequencing, interlocks, timers, latching or debounce that changes meaning (ADR 0004). If logic appears to be needed, it belongs in the PLC (invariants 5, 6). |
| Single owner | Every input value is owned by the Gazebo cell and only ever written by the bridge; every output and status value is owned by the PLC. Neither side recomputes the other's value (invariant 10). |
| Not a safety path | Every node in this section is process data. The panel's red mushroom is a **process stop**, never an emergency stop (§9.6). No safety function traverses OPC UA (invariant 1, SRS B1). |

### 9.2 Folder layout and conventions

```
DemoCell/            demonstration cell (M3), served to the bridge
DemoCell/Input/      cell → PLC: input-image values written by the bridge (bits and analogs)
DemoCell/Output/     PLC → cell: outputs the bridge applies to simulated actuators
DemoCell/Status/     PLC → bridge: read-only status for diagnostics and the watch table
DemoCell/Link/       bridge liveness
```

This tree starts at the **interface node**, whose full browse path is
`Objects/ServerInterfaces/DemoCell` (§2.1). `DemoCell/Input/ConveyorBeltPosition` below is shorthand
for `Objects/ServerInterfaces/DemoCell/Input/ConveyorBeltPosition`, with `ServerInterfaces` in the
Siemens namespace and everything from `DemoCell` down in `http://DemoCell`.

Column conventions are those of section 2, including the rule that a requested session parameter is a
request and the granted value is what a client times against. Three additions for this section:

- **Access** is from the **bridge's** view (the client), not the fleet manager's.
- For client-written nodes, `on-change` means: written when the source ROS 2 signal changes value,
  plus a full refresh of all `DemoCell/Input/` nodes on every (re)connect.
- Numeric conversion is **type narrowing only**: ROS `float64` → S7 `Real`. Units are carried
  unchanged (metres, metres per second). No scaling, offset, filtering, averaging or threshold is
  applied anywhere in the bridge.

Update-rate expectation, per signal class. The cell publishes at its own rates and cannot rate-limit
without putting policy in the simulation layer (m3-01 open question 3), so decimation is an
**interface expectation on the bridge**:

| Signal class | Cell publish rate | Expected OPC UA update | Rule |
|---|---|---|---|
| Belt position and speed (`/cell/conveyor/joint_state`) | ~500 Hz (physics rate) | cyclic, **20 Hz (50 ms)** | **Latest-sample decimation**: write the most recent sample at the write cycle and discard the rest. No averaging, no interpolation, no min/max hold — those would be filters, and a filter changes meaning (ADR 0004). Nothing may be derived from the discarded samples (no edge counting, no travel integration). |
| Photo-eye range (`/cell/product_sensor/scan`) | 30 Hz | cyclic, 20 Hz (50 ms) | Latest sample, same rule. |
| Panel contacts | on publish (no fixed rate) | on-change + refresh on reconnect | Each publish is written through unchanged; never latched, stretched or debounced. |
| `ConveyorSpeedCommand` (PLC → cell) | — | cyclic, 20 Hz (50 ms) | Read at the write cycle and republished to the cell unchanged. |

20 Hz is chosen as roughly twice the intended PLC scan and well inside the ~500 Hz source rate, so
the loop latency measured at M3 is dominated by the OPC UA path rather than by decimation. m3-04
measures what is actually achieved and may revise this number with evidence; it is an expectation,
not logic. ROS topics are not retained, so the values the PLC sees before the first publish are a
bridge startup decision (m3-01 open question 2, resolved in m3-04), not a node property.

### 9.3 DemoCell/Input/ — cell → PLC input image (bridge writes)

Owner is the Gazebo cell; the bridge is the transport, not the source. These nodes are the PLC's
input image: the standard program reads them exactly as it would read wired field inputs.

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| ConveyorBeltPosition | Real | Float | R/W | cyclic | Gazebo cell (via bridge) | Belt travel from home, m, signed. Raw encoder value from `/cell/conveyor/joint_state` `position[0]`. Mechanical stops at ±2.50 m; the limit and any homing decision are PLC program content, not a node (closes m3-01 open question 5 — no separate home or limit signal exists or is invented) |
| ConveyorBeltSpeed | Real | Float | R/W | cyclic | Gazebo cell (via bridge) | Measured belt velocity, m/s, signed, from `/cell/conveyor/joint_state` `velocity[0]`. Drive read-back: the PLC compares it with its own `ConveyorSpeedCommand`, the cell does not |
| ProductSensorRange | Real | Float | R/W | cyclic | Gazebo cell (via bridge) | Photo-eye beam distance, m, from `/cell/product_sensor/scan` `ranges[0]`. **Raw analog value, not a bit** — nominally 1.440 m beam clear, 0.540 m product in the beam; sensor range 0.05 … 3.0 m. The presence decision is made in the PLC (§9.5) |
| PanelStartPressed | Bool | Boolean | R/W | on-change | Gazebo cell (via bridge) | Start pushbutton contact from `/cell/panel/start`. Start devices are wired **NO**: 1 = contact closed = pressed. Momentary level; the PLC forms any edge it needs, the bridge never latches or stretches it |
| PanelResetPressed | Bool | Boolean | R/W | on-change | Gazebo cell (via bridge) | Monitored reset pushbutton contact from `/cell/panel/reset`. **Its fail state is 0, the opposite of the two stop nodes below**: a stop device must fail to *stopped* and so is wired NC, while a reset must fail to *not reset* and so is wired **NO** — a cut wire, a welded-open contact or nothing publishing all read 0, because a reset that asserted itself would clear latches with no operator present, the automatic resume CLAUDE.md §9 forbids. 1 = contact closed = button held. Momentary level: the PLC acts on its **rising edge** — no hold time, no timer — and the bridge never latches, stretches or debounces it. It resets **process** latches in the standard program — not a safety function, no safety integrity (§9.6, invariant 1) |
| PanelStopCircuitClosed | Bool | Boolean | R/W | on-change | Gazebo cell (via bridge) | Stop pushbutton contact from `/cell/panel/stop`. **Wire NC, program NO** (CLAUDE.md §9): 1 = circuit closed, button not actuated; 0 = actuated, or wire broken, or signal absent |
| PanelProcessStopCircuitClosed | Bool | Boolean | R/W | on-change | Gazebo cell (via bridge) | **Process stop** mushroom contact from `/cell/panel/process_stop` (§9.6). Wire NC, program NO: 1 = closed, 0 = actuated. Not an emergency stop, not a safety function, no safety integrity |

Stop devices are named for the **circuit state**, not for the button, so that the tag reads true when
the machine is permitted to run and false in every failure case. A tag named `…Pressed` would invert
the NC convention and make a dead signal look healthy. This matches the cell, which publishes both
stop contacts as NC contact state (`sim/README.md`, *Polarity: wire NC, program NO*). The suffix is
therefore the polarity: a `…CircuitClosed` node is an NC device that fails to 0 = actuated, a
`…Pressed` node is an NO device that fails to 0 = not actuated. One convention does not govern all
four panel inputs, and the four rows above are grouped by polarity rather than by panel layout.

**Where the photo-eye becomes a bit.** The raw range is carried to the PLC and the PLC thresholds it;
the bridge holds no threshold. Choosing the distance below which a product counts as present depends
on product geometry, beam alignment and the hysteresis the process wants — that is a process
decision, not a unit conversion, and ADR 0004 puts every process decision in the PLC. Interface
expectation for the PLC program: a named constant at **1.00 m** (midway between the 1.440 m clear and
0.540 m blocked levels, ≈0.45 m margin either side), product present when `ProductSensorRange` is
below it; any hysteresis or filter time is PLC program content specified in `plc/demo-cell/SPEC.md`.

### 9.4 DemoCell/Output/ — PLC → cell (bridge reads, never writes)

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| ConveyorSpeedCommand | Real | Float | R | cyclic | PLC | Belt surface velocity command, m/s, signed: positive transports the product towards +x, negative reverses, 0.0 stops. Formed inside the PLC from its cycle-running flag combined with interlocks — never driven directly from a sensor (CLAUDE.md §9). The bridge republishes it to `/cell/conveyor/cmd_speed` unchanged: no ramp, no clamp, no interlock, no zeroing of its own (invariant 6, ADR 0004). The cell applies it as given, including while a stop contact reads pressed — stopping the belt is the PLC's job, and that is exactly what M3 demonstrates |

### 9.5 DemoCell/Status/ — PLC state, read-only diagnostics

These are **PLC-derived values with no corresponding cell signal**, deliberately outside the
one-to-one correspondence of §9.3 and §9.4 (full accounting in §9.9). They are read by the bridge for
logging and by the owner in the TIA watch table, and are applied to no simulated actuator. Machine
state and actuator command are separate layers (CLAUDE.md §9), which is why `CellCycleRunning` is a
distinct node from `ConveyorSpeedCommand`.

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| CellCycleRunning | Bool | Boolean | R | on-change | PLC | Standard-program cycle-running flag: the cell is enabled. Level, survives a restart of the bridge |
| CellProcessStopActive | Bool | Boolean | R | on-change | PLC | A **process** stop is latched in the standard program (panel Stop or panel process stop). Not a safety state; no SF of docs/safety/SRS.md is represented here |
| CellResetRequired | Bool | Boolean | R | on-change | PLC | A monitored, edge-triggered local reset is pending before the cycle may run again. No client may clear it by writing a node: the only reset input is `PanelResetPressed` (§9.3), which carries the operator's field contact level, and the rising edge the PLC acts on and which latches clear are PLC program content |
| ProductPresentAtSensor | Bool | Boolean | R | on-change | PLC | The PLC's presence verdict, formed inside the program by thresholding `ProductSensorRange` (§9.3). Published so the watch table and the recording show the conversion result next to its raw input. Derived, never written by the bridge — the bridge has no threshold |
| ConveyorDriveFault | Bool | Boolean | R | on-change | PLC | PLC verdict on disagreement between `ConveyorSpeedCommand` and the measured `ConveyorBeltSpeed` (§9.3). Both inputs exist, so this node is derivable; the tolerance and delay are PLC program content and are not defined here |

### 9.6 The red mushroom is a PROCESS stop

| Statement | Detail |
|---|---|
| What it is | `PanelProcessStopCircuitClosed` is a **process stop input** to the S7-1500 **standard** program. It stops the demonstration conveyor by ordinary program logic. |
| What it is not | It is **not a safety function** and **not an emergency stop**. It appears nowhere in docs/safety/SRS.md §3, carries no SIL/PL claim, and must never be labelled, demonstrated or recorded as an emergency stop (ADR 0004). |
| Naming | The word "emergency" appears in no tag, node, topic or heading for this device. The node name, the PLC tag and the cell's `/cell/panel/process_stop` all carry "process stop" (m3-01 open question 1 — confirmed, the ADR wording governs and no ADR revisit is needed). |
| SF-01 is unaffected | The real cell e-stop chain (SRS SF-01) is executed by the F-CPU on two-channel NC F-I/O over PROFIsafe and hardwired channels. It never travels over OPC UA and is not represented by any node in this section (invariant 1, SRS B1, B3). The demonstration cell has no F-CPU. |
| No mirror either | Unlike §4, this section carries no safety mirror. `Safety/EStopActive` in §4 remains the only informational mirror of SF-01, and remains read-only and outside every causal chain. |

### 9.7 DemoCell/Link/ — bridge liveness

The input-image nodes retain their last written value on the server, so a stopped bridge is not
detectable from the input bits alone. That is the reason this node pair exists.

| BrowseName | S7 type | OPC UA type | Access | Update | Owner | Meaning |
|---|---|---|---|---|---|---|
| BridgeHeartbeat | UInt | UInt16 | R/W | cyclic | Bridge | Counter incremented by the bridge on every write cycle, wrapping at the type limit. Its only meaning is "the bridge wrote recently". It is the sole **non-input** node the bridge may write: its writable set is the input images and this counter, which at M3 meant `DemoCell/Input/` plus this node and from M4 also includes `DemoCell/Forklift/Input/` (§10.1). No second heartbeat is created for the forklift subtree — this node carries the liveness of the one bridge process |
| BridgeLinkOk | Bool | Boolean | R | on-change | PLC | The PLC's own verdict that the heartbeat is advancing. Published for the bridge's logging and the watch table |

**Reaction is PLC program content.** The staleness criterion for `BridgeHeartbeat`, the value of
`BridgeLinkOk`, and what the equipment does when the heartbeat stops are specified in
`plc/demo-cell/SPEC.md` and implemented in the standard program. No timer, threshold or reaction is
defined in this document, and none of it is in the bridge. Loss of the bridge is a degraded mode,
not a safety event (invariant 2), and nothing about it is a safety function.

### 9.8 Deliberately absent from DemoCell/

**Scope of every claim in this subsection: the §9 node set — the M3 demonstration cell's four folders
on the `DemoCell` server interface. Not the server's whole address space, and not the §10 forklift
subtree, which the same interface also carries (ADR 0008).** The §9 node set is **exactly 15 nodes** —
7 in `Input/`, 1 in `Output/`, 5 in `Status/`, 2 in `Link/`. It is *not* true that the server exposes
only those 15 nodes: the S7-1500
auto-publishes every global data block under `Objects/DataBlocksGlobal` in its own namespace, so the
DBs backing these nodes are reachable by that second path as well, under their DB and member names
rather than the BrowseNames of §9.3–§9.7 (commissioning phase 0, §9.10).

| Consequence | Statement |
|---|---|
| Node-count checks are set-scoped | "15 nodes" always means the 15 M3 nodes under `DemoCell/Input|Output|Status|Link`. A client browsing from `Objects` sees more than 15, and that is not a defect and not a naming error; so does a client browsing the same interface once §10's forklift subtree exists beside them. The independent verification of §9.10, and the bridge's `session established, N nodes resolved` log, both count nodes on the `DemoCell` interface, and at M3 that was exactly this set |
| The interface is the contract; the DB path is not | Nothing in this project reads or writes a value through `DataBlocksGlobal`. Clients resolve BrowseName paths under `DemoCell` only (§9.1, §10.1). A value reached by any other path is outside this contract, whatever it happens to be worth |
| "Deliberately absent" is a set statement | Each row of the two tables below means "no such node in the §9 node set". A DB member visible via `DataBlocksGlobal` does not contradict them: it is the same storage under a different, uncontracted path, not a second node in this model. Neither does §10: the forklift subtree is a different set on the same interface, and where a row below is voided for it — the client-writable command group — §10.4 says so by name |

**Open item, later gate — suppress DB-level exposure.** Clear the per-DB *Accessible from HMI/OPC UA*
attribute on the demonstration cell's data blocks so that the `DemoCell` interface becomes the only
path to these values, and the read-only access levels of §9.4, §9.5 and §9.7 can no longer be
circumvented through the DB path. Not done at M3: phase 0 commissioned the endpoint with default DB
visibility and with CPU access control disabled (§9.10), and both are demonstration settings. The
natural place to close it is the gate that creates the fleet-facing interface and configures access
control and user rights for a real client, so visibility and rights are set in one pass rather than
two.

Cell signals that exist but reach no node:

| Cell signal | Why it is not a node |
|---|---|
| `/cell/product_box/pose` (ground-truth product pose, 10 Hz) | **Ground truth, not a transducer.** A real conveyor has no product-position sensor; modelling one would give the PLC information the real cell cannot provide and would let the program cheat the demonstration. It exists so belt transport is observable headless (m3-01 open question 7 — upheld). |
| `/clock` (simulation time) | Simulator infrastructure, not a cell signal. The bridge consumes it as a ROS node; the PLC has its own time base. |

Node kinds that do not exist:

| Not in the §9 node set | Why |
|---|---|
| A client-writable conveyor command node, or a run/stop bit alongside `ConveyorSpeedCommand` | The bridge may never write an actuator output (invariant 6). The cell accepts one signed velocity and nothing else; a separate run bit would duplicate information already carried by the sign and magnitude of the command, breaking single ownership (invariant 10). **This row is about the conveyor command path and still holds there.** It is not a statement about the whole server: §10.4 defines a client-writable *request* group for the forklift cell, admitted by ADR 0008 D2, which commands no actuator either |
| A `ProductPresent` bit in the input image | The presence threshold is a process decision and lives in the PLC (§9.3). The bridge writes the raw range only |
| A belt home or travel-limit signal | The cell has no such transducer; `ConveyorBeltPosition` carries the raw travel and the ±2.50 m limit is a constant in the PLC program (m3-01 open question 5) |
| Any safety node, safety mirror, or reset of a safety function | Safety never traverses the network (invariant 1); the demonstration cell has no F-CPU and no SF. `PanelResetPressed` (§9.3) is not an exception: it is a process device whose contact level resets standard-program latches only |
| Timers, step numbers, latch state exposed for the bridge | Logic and sequencing belong to the PLC; exposing them would invite the bridge to act on them (ADR 0004) |
| Vehicle, order or fleet data | No vehicle exists in M3 (ADR 0004); fleet data never lives on the PLC (invariants 3, 5) |

### 9.9 Reconciliation with the sim signal table

One node per cell signal, one cell signal per node, checked in both directions against
`sim/README.md` § "Demonstration cell (M3)". The proposed names in that table are superseded by the
BrowseNames here, which are the authoritative PLC tag names (m3-01 open question 4).

| Sim signal | ROS 2 topic → field | Direction (PLC view) | Node |
|---|---|---|---|
| `ConveyorSpeedCmd` | `/cell/conveyor/cmd_speed` → `data` | PLC → cell | `DemoCell/Output/ConveyorSpeedCommand` |
| `ConveyorBeltPosition` | `/cell/conveyor/joint_state` → `position[0]` | cell → PLC | `DemoCell/Input/ConveyorBeltPosition` |
| `ConveyorBeltSpeed` | `/cell/conveyor/joint_state` → `velocity[0]` | cell → PLC | `DemoCell/Input/ConveyorBeltSpeed` |
| `ProductSensorRange` | `/cell/product_sensor/scan` → `ranges[0]` | cell → PLC | `DemoCell/Input/ProductSensorRange` |
| `PanelStartContact` | `/cell/panel/start` → `data` | cell → PLC | `DemoCell/Input/PanelStartPressed` |
| `PanelResetContact` | `/cell/panel/reset` → `data` | cell → PLC | `DemoCell/Input/PanelResetPressed` |
| `PanelStopContact` | `/cell/panel/stop` → `data` | cell → PLC | `DemoCell/Input/PanelStopCircuitClosed` |
| `PanelProcessStopContact` | `/cell/panel/process_stop` → `data` | cell → PLC | `DemoCell/Input/PanelProcessStopCircuitClosed` |
| *(diagnostic)* `/cell/product_box/pose` | — | cell → observer | **none, by design** (§9.8) |
| *(infrastructure)* `/clock` | — | cell → observer | **none, by design** (§9.8) |

Nodes with no cell signal, and why each is legitimate rather than an orphan:

| Node | Source |
|---|---|
| `DemoCell/Status/*` (5 nodes) | PLC-derived program state, published for diagnostics and the watch table (§9.5). Read-only for the bridge; none is applied to a simulated actuator |
| `DemoCell/Link/BridgeHeartbeat` | Generated by the bridge itself, not by the cell (§9.7) |
| `DemoCell/Link/BridgeLinkOk` | PLC-derived verdict on the heartbeat (§9.7) |

The operational signal map — including the conversion, decimation and reconnect detail the bridge
implements — is `docs/interfaces/bridge-design.md` (m3-03), derived from this table. If the two ever
disagree, this document is the contract and the bridge design is corrected to match.

### 9.10 Commissioned environment — phase 0, 2026-07-27

Owner-verified **in the tool**, on the machine that will run the demonstration. Every value here was
read back from the tool or off the wire; none was chosen in a document (LESSONS 2026-07-27, on
tool-derived identifiers). This record exists so the addressing rules of §2.1 and the scoping of §9.8
can be traced to the system that produced them.

| Item | Commissioned value |
|---|---|
| Engineering tool | TIA Portal V21 |
| Simulator | S7-PLCSIM Advanced V7.0. V3.0 was removed: broken virtual adapter service, and unsupported with TIA V21 |
| CPU | 1513-1 PN, firmware V3.1 |
| OPC UA runtime license | "large" — the compiler demanded large after the firmware change |
| PLCSIM network mode | TCP/IP Single Adapter, `<Local>` |
| PLCSIM instance address | 192.168.53.1/24 |
| Host virtual adapter | 192.168.53.241/24 |
| Endpoint | `opc.tcp://192.168.53.1:4840` |
| Message security | None |
| Authentication | Anonymous, granted by the CPU-level *Disable access control* setting. V3.x firmware offers no guest-authentication checkbox; disabling access control grants the Anonymous user full rights, OPC UA included |
| Browse path | `Objects` → `ServerInterfaces` (`http://www.siemens.com/simatic-s7-opcua`) → `DemoCell` (`http://DemoCell`), per §2.1 |
| Independent verification | 2026-07-27: an `asyncua` client running on Windows read all 15 `DemoCell` nodes at their start values. **The bridge was not involved** |

**What phase 0 proves, and what it does not.** It proves the endpoint, the security and
authentication configuration, the browse path and the exposure of the 15 nodes with their data types.
It proves **no PLC program behaviour** — no logic was running — and **nothing about the bridge**,
which was not part of the verification. Loop evidence remains the responsibility of
`plc/demo-cell/SPEC.md` §10 and the bridge evidence files.

**These are demonstration settings, not production ones.** Security `None` plus anonymous full rights
plus default DB visibility is the minimum that gets a first session established. Hardening — message
security, user authentication, and the DB-visibility item of §9.8 — is carried to the gate that
configures the server for a real client, and none of it changes a node, a name or a direction in this
document.

## 10. Forklift commissioning nodes (M4)

Added by ADR 0008, which extends the loop M3 proved by one axis: the plant becomes vehicle-shaped —
steered drive, a controlled fork, one planar lidar — and the loop gains an operator. The gate's claim
is that **every command passes HMI → PLC standard program → bridge → simulation, and every state
report returns simulation → bridge → PLC** (ADR 0008 D1). No command reaches the plant without
passing through PLC logic.

Two things are new relative to §9. Everything else — the server, the interface, the bridge, the
namespace rules of §2.1 — is the one M3 commissioned.

1. **A second client.** A local commissioning HMI (`hmi/`, ADR 0008 D2.6) joins the bridge as an OPC
   UA *client* of the same server. It writes requests and reads status; it holds no server and
   exposes no endpoint (invariant 4, ADR 0008 D2.1).
2. **A client-writable request group**, the first in this model (§10.4).

**This section defines nodes only**, as §9 does. Every interlock, speed cap, soft limit, latch, timer
and threshold named below is standard-program content, owned by the PLC layer's forklift function
block and its specification. None of it is in the bridge (ADR 0005 D1, `bridge-design.md` §1.1) and
none of it is in the HMI (ADR 0008 D2.2). Where a value is named here it is an **interface
expectation** for that specification, marked as such, never logic defined in this document.

**The forklift is plant, not a fleet vehicle.** It is supervised by the PLC exactly as the conveyor
is: a Gazebo machine whose I/O the bridge carries, with no VDA 5050 client, no order, no fleet
identity, no navigation stack and no MQTT (ADR 0008 D5). Invariant 11 is therefore untouched, and
§8's "vehicle state does not live on the PLC" row is unaffected — it governs the *fleet* vehicle,
whose state flows AGV → MQTT → fleet manager at its own gate and still reaches no node here.

### 10.1 Direction rules — two clients, one server

| Rule | Statement |
|---|---|
| Server/client | The PLC is the OPC UA server. **Both** the bridge and the HMI are clients. Never inverted, for either (invariant 4, ADR 0008 D2.1). |
| What the HMI writes | **Only** the five `Forklift/Hmi/` request nodes and `Forklift/Link/HmiHeartbeat` (§10.4, §10.8). It writes nothing else on this server, on any interface, and nothing under the auto-published `DataBlocksGlobal` folder. |
| What the bridge writes | Its §9.1 writable set **plus** the four `Forklift/Input/` nodes, and nothing more. The bridge never writes an `Hmi…` node and the HMI never writes an `Input/` node: the two clients' writable sets are disjoint by construction and distinguishable by BrowseName prefix. |
| No actuator writes, from either client | Neither client writes an actuator output. `Forklift/Output/*` is formed inside the PLC from the teleop-active flag combined with interlocks, and is driven to zero in a mandatory `ELSE` (§10.6). The HMI *requests*; the PLC decides and owns the outcome (invariant 6 discipline, ADR 0008 D2.2). |
| No logic in either client | The bridge remains a signal translator (§9.1). The HMI is a *source of requests and a display*: no interlock, no latch, no timer, no sequencing, no verdict the PLC also computes (invariant 10, ADR 0008 D2.2, D2.6). |
| Single owner | Every node below has exactly one writer, listed per tag in §10.3 (invariant 10). No value is recomputed by a consumer. |
| One link verdict per client, no duplicates | The bridge's liveness stays `DemoCell/Link/BridgeHeartbeat` / `BridgeLinkOk` — **no second bridge heartbeat is created for the forklift subtree**. One session serves both function blocks; the verdict is written by the demonstration cell's FB and consumed by the forklift FB as a shared DB bit (invariant 10). The HMI's liveness is a *separate and independent* watchdog on a different client (§10.8). |
| Not a safety path | Every node here is process data. The obstacle stop, the fork-height speed cap and the fork soft limits are **standard-program process interlocks** and implement **no** SRS function: not SF-02, not SF-03, not SF-04, not SF-07, not SF-09 (ADR 0008 D3). No SIL or PL is claimed for any of them, and neither "emergency" nor "protective" appears in any tag, node or topic **name** in this section — the same naming discipline §9.6 sets for the demonstration cell's process stop. Loss of either client link is a degraded mode, not a safety event (invariant 2). |
| Timing class | Both clients are best effort (invariant 9). Every timing decision that matters — the stale windows, the fault delays, the reset edge — is a PLC timer in the PLC's own time base. |

### 10.2 Server interface: `DemoCell` is extended, not replaced

**Ruling: the forklift nodes are added to the existing `DemoCell` server interface, as a `Forklift/`
subtree beside the four M3 folders. No second server interface is created.**

| Why | Detail |
|---|---|
| One interface is one namespace (ADR 0006) | TIA Portal derives a server interface's namespace URI as `http://<interface name>` and the field is not editable, so a second interface would carry a second, differently-named URI. Every client would then resolve a third namespace index and browse two roots to reach one cell. |
| One session, one heartbeat, one link verdict | A second interface does not by itself force a second session, but it invites one — and two sessions mean two liveness stories for one bridge process. Keeping one interface keeps `BridgeLinkOk` the single owner of "the bridge is alive" (invariant 10, §10.1). |
| The cost of a second interface is paid at every connect | §2.1's two-namespace resolution becomes three, and N1–N6 of `bridge-design.md` §3.1 would have to be restated for a path the M3 evidence never exercised. |
| What a second interface would have bought | Nothing this gate needs. Interface-level separation is not access control: per-tag *Writable from HMI/OPC UA* is the enforcement point (§10.3), and it is per tag whichever interface the tag is published on. |

**The `DemoCell` name and its URI `http://DemoCell` are unchanged, and that is safe.** Adding folders
and tags to an interface does not touch its name, so the derived URI does not move and every existing
browse path in §9, in `bridge-design.md` §3.1 and in the commissioned configuration keeps working
untouched. The renaming that ADR 0006 forbids is exactly the operation *not* performed here: an
interface name is a contract identifier of the same standing as a BrowseName, because it **is** the
namespace URI, and renaming it would break every browse-by-URI at connect.

The honest consequence, stated rather than discovered: **`DemoCell` is now an identifier, not a
description.** The interface carries the demonstration cell *and* the forklift commissioning cell.
The name is kept because changing it costs a namespace URI and buys a nicer word.

**If a later gate does create a second interface** — the fleet-facing one of §2.1 and ADR 0006 D3 is
the expected case — its **name is a contract decision taken in a document, never in the tool**,
because the name is the URI. It is chosen at briefing, written down, and only then typed into TIA.

#### TIA click path (the `plc/demo-cell/SPEC.md` §4.2–§4.3 pattern)

1. CPU → *OPC UA communication* → *Server interfaces* → open the **existing** `DemoCell` interface.
   Do **not** create a second interface and do **not** rename this one.
2. **Read the namespace URI back** and confirm it still reads `http://DemoCell`. Nothing is entered:
   the field is derived and not editable (ADR 0006). This read-back is the check that the interface
   opened is the one the bridge browses for, and it is repeated after any *Change device*, which is
   known to delete server interfaces silently (LESSONS 2026-07-27).
3. Create the five new global DBs of §10.3 with their *Accessible from HMI/OPC UA* and *Writable from
   HMI/OPC UA* attributes set per tag as tabulated there. **New DBs, not new members of the M3 DBs**
   — see §10.3.
4. In the interface, add a folder `Forklift` beside `Input`, `Output`, `Status` and `Link`, then the
   five subfolders, then drag each DB tag into its subfolder. **Rename nothing**: each leaf name must
   remain the BrowseName of §10.4–§10.8, so this document and the TIA export can be diffed.
5. Download, then confirm the block diff circles are solid green before testing. A monitoring-error
   icon on a watch-table row, or an in-force timer value that contradicts the call site, is the live
   tell of a stale build (LESSONS 2026-07-28).
6. Browse the server with a client that is **not** the bridge and read every node in §10 at its start
   value, as phase 0 did for the 15 M3 nodes (§9.10). Record the reading with its date.

> **Everything in this section is a design value until step 6 is executed.** The browse path, the
> folder tree, the per-tag rights and the node count are what this document asks the tool for; they
> become facts when they are read back out of it. A spec value authored without the tool that
> realises it is a design value, not a fact (LESSONS 2026-07-27), and no gate criterion may rest on
> one before it has been owner-verified in the tool.

### 10.3 Folder layout, data blocks and per-tag access rights

```
DemoCell/                          the commissioned server interface, ns http://DemoCell
  Input/ Output/ Status/ Link/     the M3 demonstration cell (§9), unchanged
  Forklift/                        the M4 forklift commissioning cell (this section)
    Hmi/      operator → PLC: requests written by the HMI
    Input/    plant → PLC: state written by the bridge
    Output/   PLC → plant: setpoints the bridge reads and republishes
    Status/   PLC → both clients: read-only verdicts
    Link/     HMI liveness
```

Paths are relative to the interface node, as everywhere in this document:
`Forklift/Hmi/HmiTractionRequest` is
`Objects/ServerInterfaces/DemoCell/Forklift/Hmi/HmiTractionRequest` in full (§2.1).

**Five new global DBs, one per folder. The M3 DBs are not extended.** Adding members to
`DemoCellInput` and its siblings would move the offsets of tags that current evidence, watch tables
and test records depend on, and a download that leaves project and CPU inconsistent shows up as
monitoring errors on exactly the rows whose offsets moved (LESSONS 2026-07-28). Separate DBs leave
the M3 cell byte-identical, so its evidence stays reproducible while this gate is commissioned.

| DB | Folder | Contents | *Accessible from HMI/OPC UA* | *Writable from HMI/OPC UA* |
|---|---|---|---|---|
| `ForkliftHmi` | `Forklift/Hmi/` | 5 request tags | ✔ | **✔** (all five) |
| `ForkliftInput` | `Forklift/Input/` | 4 plant-state tags | ✔ | **✔** (all four) |
| `ForkliftOutput` | `Forklift/Output/` | 3 setpoint tags | ✔ | **✘** |
| `ForkliftStatus` | `Forklift/Status/` | 4 verdict tags | ✔ | **✘** |
| `ForkliftLink` | `Forklift/Link/` | `HmiHeartbeat`, `HmiLinkOk` | ✔ | per tag |
| `ForkliftControl_DB` (instance) | — | the forklift FB's internals | **✘** | ✘ |

> The *Writable* column is where the direction rules of §10.1 are **enforced by the server rather
> than by convention**: with `Forklift/Output/*` not writable, a defect in either client that tried
> to write an actuator setpoint is refused by the CPU. This is the same two-independent-enforcements
> arrangement the M3 cell uses (`plc/demo-cell/SPEC.md` §4.2) — each client also enforces its own
> allowlist. **Per-*client* scoping is not enforced**: the commissioned CPU runs with access control
> disabled and security `None` (§9.10), so "only the HMI writes the `Hmi` group" is policy, and with
> two writing clients that gap is materially wider than it was with one (ADR 0008 D2.5). Closing it
> is the same access-control work §9.8 already carries.

Per-tag ownership and readers. **Exactly one writer per node** (invariant 10); "readers" lists every
consumer this contract admits.

| Node (`Forklift/…`) | Writer (single owner) | Readers |
|---|---|---|
| `Hmi/HmiTractionRequest` | HMI | PLC |
| `Hmi/HmiSteerRequest` | HMI | PLC |
| `Hmi/HmiForkRequest` | HMI | PLC |
| `Hmi/HmiTeleopRequest` | HMI | PLC |
| `Hmi/HmiResetRequest` | HMI | PLC |
| `Link/HmiHeartbeat` | HMI | PLC |
| `Link/HmiLinkOk` | PLC | HMI (display), bridge (logging only) |
| `Input/ForkliftForkHeight` | Gazebo plant, via the bridge | PLC, HMI (display) |
| `Input/ForkliftLinearSpeed` | Gazebo plant, via the bridge | PLC, HMI (display) |
| `Input/ForkliftObstacleInStopZone` | Gazebo plant, via the bridge | PLC, HMI (display) |
| `Input/ForkliftObstacleMinDistance` | Gazebo plant, via the bridge | PLC, HMI (display) |
| `Output/ForkliftTractionSpeedRef` | PLC | bridge (applied to the plant), HMI (display) |
| `Output/ForkliftSteerAngleRef` | PLC | bridge (applied to the plant), HMI (display) |
| `Output/ForkliftForkSpeedRef` | PLC | bridge (applied to the plant), HMI (display) |
| `Status/ForkliftTeleopActive` | PLC | HMI, bridge (logging only) |
| `Status/ForkliftObstacleStopActive` | PLC | HMI, bridge (logging only) |
| `Status/ForkliftSpeedLimitActive` | PLC | HMI, bridge (logging only) |
| `Status/ForkliftResetRequired` | PLC | HMI, bridge (logging only) |

**18 nodes** — 5 in `Hmi/`, 4 in `Input/`, 3 in `Output/`, 4 in `Status/`, 2 in `Link/`. The count is
subtree-scoped in the sense §9.8 fixes: the `DemoCell` interface carries these 18 **and** the 15 of
§9, and a client browsing from `Objects` sees more than either number.

An `Hmi` prefix on every HMI-written tag is deliberate redundancy inside a folder already named
`Hmi/`: it survives into the PLC program and into any export, so "which client may write this tag"
is answerable from the BrowseName alone, without consulting a folder or a table. With two writing
clients on one interface, that is worth one repeated word.

### 10.4 `Forklift/Hmi/` — the operator's requests, and the first client-writable group

**This is the first client-writable group in this model, and it is admitted by ADR 0008 D2.** §9.8
records a client-writable command node as deliberately absent; that row is about the M3 cell's
conveyor command path, where it still holds unchanged — the bridge may never write
`ConveyorSpeedCommand` or a run bit beside it. What ADR 0008 admits is different in kind: these are
**requests**, not commands. Every one of them is read by the PLC, combined with interlocks, and
turned into a setpoint the PLC owns (§10.6). No client writes an actuator output anywhere in this
model, at M3 or at M4. The enforcement point for that distinction is the per-tag *Writable from
HMI/OPC UA* column of §10.3: the request group is writable, `Forklift/Output/` is not.

| BrowseName | S7 type | OPC UA type | Unit | Engineering range | Plausibility window | Meaning |
|---|---|---|---|---|---|---|
| `HmiTractionRequest` | Real | Float | — (fraction) | −1.00 … +1.00 | ±1.05 | Operator's traction demand as a fraction of `TRACTION_SPEED_MAX`. Positive drives forwards. The PLC scales, interlocks and gates it; the plant never sees this number |
| `HmiSteerRequest` | Real | Float | rad | −1.31 … +1.31 | ±1.35 | Requested steer angle of the front assembly, signed. The limit is the plant's mechanical steer range |
| `HmiForkRequest` | Real | Float | — (fraction) | −1.00 … +1.00 | ±1.05 | Operator's fork jog demand as a fraction of `FORK_SPEED_MAX`. Positive raises. A jog **speed**, not a height: there is no height request node (§10.11) |
| `HmiTeleopRequest` | Bool | Boolean | — | — | — | Operator asks for teleop. A **level**, not an edge: it expresses "the operator is at the controls", survives a PLC scan and a restart, and is withdrawn by writing `FALSE`. The PLC's verdict is `ForkliftTeleopActive`, which is a different node with a different owner |
| `HmiResetRequest` | Bool | Boolean | — | — | — | Operator asks to clear the latched process stops of §10.7. A level carrying the operator's action; **the PLC acts on its rising edge**, under the arming rule of §10.8. No client clears a latch by writing a node — the write is the request, the edge and the arming are PLC program content |

**Fractions, not velocities, on the two speed requests.** The HMI has no business knowing the plant's
maximum speeds: `TRACTION_SPEED_MAX` and `FORK_SPEED_MAX` are process decisions in the PLC's constant
block, and a fraction means changing one of them changes the machine without changing the operator
interface or requiring the two to agree about a number (invariant 10). The steer request is an angle
because an angle is what the operator is aiming at and what the plant's joint accepts; it is the one
request whose range is a mechanical property rather than a process decision.

**An implausible request is a fault, not a value to clamp.** Interface expectation for the PLC
specification: test each Real affirmatively against its window — `valid := (low < x) AND (x < high)`
— and take the fault in the `ELSE` (LESSONS 2026-07-27). The windows above are wider than the
engineering range by the `float64 → Real` narrowing margin, so a legitimate ±1.0 never reads as a
fault; anything outside them is a broken client, not a demand, and silently clamping it would hide
exactly that. `NaN` and `inf` fall through an affirmative test to the same branch.

**Every HMI node is written every HMI cycle, not on change** (§10.8). That is what makes a CPU
restart under a surviving HMI session harmless on this side: there is no HMI-written level that can
stay stale after the DB reverts, because the next cycle rewrites all six. The failure recorded on
2026-07-28 — a reverted input image that a write-on-change client never repairs — cannot form here.

### 10.5 `Forklift/Input/` — plant state (bridge writes)

Owner is the Gazebo plant; the bridge is the transport, not the source, exactly as in §9.3. These are
the PLC's input image for the forklift and are read as wired field inputs would be.

| BrowseName | S7 type | OPC UA type | Unit | Range / plausibility window | Meaning |
|---|---|---|---|---|---|
| `ForkliftForkHeight` | Real | Float | m | travel 0.00 … 1.60; window **−0.05 … 1.70** | Carriage height above the mast's bottom stop, derived by the vehicle layer from the mast prismatic joint. The window is widened past both mechanical stops so a carriage resting **on** a stop is never called implausible — the `BELT_POSITION_MIN/MAX` reasoning of `plc/demo-cell/SPEC.md` §3.3 |
| `ForkliftLinearSpeed` | Real | Float | m/s | window **−2.00 … +2.00** | Measured chassis speed along its heading, signed, positive forwards, derived from the plant's odometry. The window is a statement about what the transducer can report, **not** a process cap: the cap is `TRACTION_SPEED_MAX` and is a different decision in a different layer |
| `ForkliftObstacleInStopZone` | Bool | Boolean | — | — | The lidar's **field-violation output**: an object inside the configured forward stop field. **`TRUE` is the non-permissive state**, and the vehicle layer publishes `TRUE` whenever the scan is invalid, non-finite or stale — absence of data is an obstacle. See the polarity note below |
| `ForkliftObstacleMinDistance` | Real | Float | m | sensor window 0.10 … 8.00; plausibility **0.05 … 8.10** | Smallest valid range in the same forward sector, published for the operator display and for diagnostics. **`0.0` is the vehicle layer's no-data sentinel and sits deliberately outside the plausibility window**, so the PLC's affirmative window test reads it as a sensor fault at the same moment the field bit reads as an obstacle — two independent signals pointing the same, non-permissive way |

**Polarity, stated because it is the one input here that inverts §9.3's convention.** §9.3 names stop
*contacts* for their circuit state, so the tag reads `TRUE` when the machine may run and `FALSE` in
every failure case. `ForkliftObstacleInStopZone` reads `TRUE` in the failure case. It is named that
way on purpose and the conflation is written out rather than left to be discovered:

- The node mirrors a ROS topic whose polarity the vehicle layer owns, and **the bridge may not invert
  a signal** — inverting is listed as a violation of the no-logic rule (`bridge-design.md` §1.1), so
  a permissive-polarity node would require the inversion to happen in the transport.
- Fail-safety is therefore carried by three independent things instead of by the name: the vehicle
  layer publishes `TRUE` on invalid, non-finite or stale scans; the DB start value is `TRUE`
  (§10.9); and no input-derived verdict is evaluated at all while `BridgeLinkOk` is `FALSE` (§10.9).
- Anyone renaming this node must move the polarity of the ROS topic with it, in the vehicle layer,
  in the same change. Changing one end alone silently inverts a stop.

**Why the field verdict is the device's and not a PLC threshold.** §9.3 sends the photo-eye's raw
range to the PLC precisely so the *threshold* is a process decision in the PLC. The lidar is
different in kind: the field is a geometry — a sector and a distance over 181 samples — that cannot
be reconstructed from any single scalar this node model can carry, and a real scanner reports exactly
this way, with the field configured in the device and a violation bit on its output. So the plant
owns the field verdict and the PLC owns the **reaction**: the stop, the latch, the monitored reset
and the setpoint gating are all PLC content (§10.7). `ForkliftObstacleMinDistance` is *not* a second
route to the same verdict — forming a second "obstacle present" in the PLC would create a second
owner (invariant 10). It is a diagnostic value, and testing it for plausibility is a statement about
the transducer's health, not about the obstacle.

Cadence, following §9.2's conventions: the two Reals and the diagnostic distance are written
cyclically at the bridge's 20 Hz cycle, the Bool on change plus a full refresh on every (re)connect
and after any detected server restart. Note that the **source is slower than the cycle** here — the
vehicle layer publishes all four at 10 Hz — so no decimation occurs and the cycle simply rewrites the
latest slot. A repeated identical write is not a freshness statement: freshness is the heartbeat's
job, and a plant that has stopped publishing under a live bridge is case D of `bridge-design.md`
§7.3, unchanged by this section (§10.12).

### 10.6 `Forklift/Output/` — PLC → plant (bridge reads, never writes)

| BrowseName | S7 type | OPC UA type | Unit | Range | Meaning |
|---|---|---|---|---|---|
| `ForkliftTractionSpeedRef` | Real | Float | m/s | ±`TRACTION_SPEED_MAX` | Traction speed setpoint, signed, positive forwards. Formed inside the PLC from `HmiTractionRequest` scaled by `TRACTION_SPEED_MAX`, reduced by the fork-height speed cap when it applies, and gated to `0.0` by the interlocks of §10.7 |
| `ForkliftSteerAngleRef` | Real | Float | rad | −1.31 … +1.31 | Steer angle setpoint, signed. Clamped in the PLC to the plant's mechanical range. Steering is **not** gated to zero on a stop: a steer setpoint is a position, and forcing it to centre would move the wheel of a machine that is supposed to be stopping |
| `ForkliftForkSpeedRef` | Real | Float | m/s | −0.15 … +0.15 | Fork jog velocity setpoint, signed, positive raises. Formed from `HmiForkRequest` scaled by `FORK_SPEED_MAX`, aborted **in the offending direction only** at a soft travel limit, and gated to `0.0` by the interlocks of §10.7. `0.0` means hold: the plant holds the carriage against gravity |

**Gating a Real means an unconditional assignment with a mandatory `ELSE`.** Interface expectation
for the PLC specification, restated because it is the analogue-output rule this project has already
been bitten by: each of the three setpoints is assigned in **exactly one statement** in the whole
project, on every call, with the interlock-failed branch driving it to `0.0`. A conditional write
with no `ELSE` leaves the Real holding its last value, so the machine keeps moving after the stop
(LESSONS 2026-07-27, `plc/demo-cell/SPEC.md` §6.4). This is what ADR 0008 D2.3 requires of the HMI
watchdog and what §10.7's obstacle stop requires of the obstacle path; both are the same statement.

The bridge republishes each value to its ROS topic **unchanged** — no ramp, no clamp, no interlock,
no zeroing of its own (invariant 6, `bridge-design.md` §1.1) — and the plant applies it as given,
including while the operator has let go of the controls. Stopping the machine is the PLC's job, and
that is what this gate demonstrates.

### 10.7 `Forklift/Status/` — PLC verdicts, read-only for both clients

PLC-derived values with no corresponding plant signal, in the standing of §9.5: read by the HMI for
its display, by the bridge for logging, applied to no actuator.

| BrowseName | S7 type | OPC UA type | Meaning |
|---|---|---|---|
| `ForkliftTeleopActive` | Bool | Boolean | The PLC's verdict that teleop is enabled: `HmiTeleopRequest` held, both link verdicts `TRUE`, no latch standing. **A level**, and the separate layer from the setpoints — machine state and actuator command are different things (CLAUDE.md §9), which is why this is not the same node as `ForkliftTractionSpeedRef` being non-zero |
| `ForkliftObstacleStopActive` | Bool | Boolean | A **latched** process stop, raised by `ForkliftObstacleInStopZone` and cleared only by the monitored reset of §10.8. Standard-program process logic; **not** SF-03 and not a protective stop (ADR 0008 D3). The field clearing does not release it: this machine does not resume by itself (CLAUDE.md §9) |
| `ForkliftSpeedLimitActive` | Bool | Boolean | The fork-height speed cap is in force: the carriage is raised past the cap's height and the traction setpoint is being limited below what the operator asked for. Informational — the reduction itself happens in the setpoint (§10.6). **Not** SF-04 and no PL is claimed |
| `ForkliftResetRequired` | Bool | Boolean | A monitored, edge-triggered reset is pending before teleop may be enabled again. Set by any latch above and by a link loss (§10.8). **No client clears it by writing a node**: the only reset input is `HmiResetRequest`, and the edge and the arming are PLC program content |

Interface expectations for the PLC specification, each a process decision this document does not
make: the fork-height speed cap's height and reduced speed; the fork soft travel limits, which must
be **direction-scoped aborts** and never a blanket permissive, because a carriage sitting on a limit
can only leave it by moving (LESSONS 2026-07-27); and the fault delays. A latch is never a term in
its own clearing condition (LESSONS 2026-07-27), so the reset tests the live world, not the latches.

### 10.8 `Forklift/Link/` — the HMI watchdog

The HMI's request nodes retain their last written value on the server, so a stopped HMI is not
detectable from the requests alone — the same reason `DemoCell/Link/` exists for the bridge. This is
a **second, independent watchdog on a different client**, not a copy of the first.

| BrowseName | S7 type | OPC UA type | Unit | Range | Meaning |
|---|---|---|---|---|---|
| `HmiHeartbeat` | UInt | UInt16 | — | 0 … 65535, wraps | Counter incremented by the HMI once per write cycle. Its only meaning is "the HMI completed a write cycle recently". It carries no process information |
| `HmiLinkOk` | Bool | Boolean | — | — | The PLC's verdict that the HMI heartbeat is advancing. Published so the HMI can show the operator that the PLC believes the link is up |

**Semantics, normative for the HMI layer.**

| # | Rule |
|---|---|
| H1 | The HMI writes **all six** of its nodes every cycle — the five requests and the heartbeat — never on change. A stream is self-repairing: a CPU restart that reverts the DB is corrected by the next cycle (LESSONS 2026-07-28) |
| H2 | Cycle rate **10 Hz nominal, 5 Hz contractual floor**. Below the floor the HMI is not a supervision source and must stop writing rather than write slowly |
| H3 | The heartbeat is written **last**, after the cycle's five request writes are acknowledged. An advanced heartbeat therefore implies that cycle's requests landed first. This is an **ordering** guarantee, not atomicity: no PLC logic may require two HMI tags to have come from the same cycle |
| H4 | The counter is a counter, never a timestamp: no epoch, no clock synchronisation, no time zone in a liveness signal. It is not reset across a reconnect and starts from an arbitrary value at HMI restart |
| H5 | The HMI writes no farewell value, zeroes nothing on shutdown and re-publishes nothing on reconnect beyond the current state of its controls. Stopping the machine is the PLC's decision (§10.6) |

**Semantics, interface expectation for the PLC specification.**

| # | Rule |
|---|---|
| P1 | Test `HmiHeartbeat <> LastHmiHeartbeat` — **inequality only**. Never subtract, never test for `+1`, never assume monotonic ordering across the wrap or across an HMI restart |
| P2 | `HmiLinkOk := HmiSeenAlive AND NOT HmiStaleTimer.Q`, where `HmiSeenAlive` is a non-retain latch with start value `FALSE`, set by the first observed change. **The link verdict is `FALSE` from the first scan and stays `FALSE` until the heartbeat has actually moved**: "not yet proven stale" is not "alive", and every guard that rides on link-up inherits this boot polarity (LESSONS 2026-07-28, ADR 0008 D2.3). A verdict formed from the stale timer alone would read `TRUE` for the whole first stale window of every CPU run, before a single operator input had ever arrived |
| P3 | The stale window is a **named constant**, `HMI_STALE_TIME`, **`T#600ms`** — three times the 200 ms period the 5 Hz floor allows. The **rule is three worst-case write periods**, not this number: if the HMI's measured worst-case period at commissioning exceeds 200 ms, the constant is re-derived from the measurement rather than the floor being quietly reinterpreted |
| P4 | `HMI_STALE_TIME` is **its own constant**, never shared with `HEARTBEAT_STALE_TIME`. The two watch different clients at different rates, and retuning one must not silently retune the other (invariant 10, the `BELT_FAULT_DELAY` precedent) |
| P5 | On `HmiLinkOk` `FALSE`: every motion setpoint is driven to `0.0` in the mandatory `ELSE` of §10.6, `ForkliftTeleopActive` drops, and the loss **latches** — `ForkliftResetRequired` is set and a returning heartbeat never by itself restores teleop (ADR 0008 D2.3, CLAUDE.md §9). No request value is evaluated while the verdict is `FALSE`; the requests are then not attributable to an operator |
| P6 | **The reset edge is armed per link session.** A rising edge of `HmiResetRequest` counts only if the PLC has already observed that node `FALSE` **while `HmiLinkOk` was `TRUE` within the current link session** — the arming latch clears whenever `HmiLinkOk` is `FALSE`. Without it, a reset held from before link-up registers as an edge the moment the link forms and clears every latch with no operator acting at the moment of clearing, which is the automatic resume CLAUDE.md §9 forbids. A guard scoped per session is tested by **ending a session**, not by restarting the machine (LESSONS 2026-07-28) |
| P7 | Teleop requires **both** link verdicts: `BridgeLinkOk` (the plant's state is attributable) and `HmiLinkOk` (the operator is present). They are independent watchdogs on independent clients and neither substitutes for the other |

Loss of either link is a **degraded mode, not a safety event** (invariant 2). The controlled stop it
produces is process logic; the vehicle-side stop that would be safety-rated on real equipment is
onboard and hardwired, and does not exist on this plant (invariant 1, ADR 0008 D3).

### 10.9 Start values and the qualification rule

Fail-safe pre-connection state belongs to the PLC as the DB start values, as it does for the M3 cell
(`bridge-design.md` §6.3). Interface expectation for the PLC specification — start values, **not**
logic:

| Node | Start value | Reading |
|---|---|---|
| `Hmi/HmiTractionRequest`, `HmiSteerRequest`, `HmiForkRequest` | `0.0` | No demand. Never a stored demand from a previous session |
| `Hmi/HmiTeleopRequest` | `FALSE` | No operator at the controls. Never enable on a start value |
| `Hmi/HmiResetRequest` | `FALSE` | Not pressed. A `TRUE` start value would assert a reset no operator made |
| `Link/HmiHeartbeat` | `0` | Meaningless until it changes; `HmiSeenAlive` is what gives it meaning (P2) |
| `Input/ForkliftForkHeight` | `0.0` | A height with no meaning until the link is up; not to be read as "carriage down" |
| `Input/ForkliftLinearSpeed` | `0.0` | Not known to be moving |
| `Input/ForkliftObstacleInStopZone` | **`TRUE`** | The non-permissive value, matching the node's polarity (§10.5). The one start value in this section that is not the type's zero, and deliberately so |
| `Input/ForkliftObstacleMinDistance` | `0.0` | Outside the plausibility window, i.e. reads as a sensor fault rather than as a clear path |

> **The qualification rule, inherited unchanged from `plc/demo-cell/SPEC.md` §6.1.** While
> `BridgeLinkOk` is `FALSE`, the four `Forklift/Input/` values are **not attributable to the plant**;
> while `HmiLinkOk` is `FALSE`, the five `Forklift/Hmi/` values are **not attributable to an
> operator**. No verdict derived from either group is evaluated and no fault from either group is
> latched while its link verdict is `FALSE`. Start values are therefore the last line, not the first:
> the boot polarity of P2 is what actually prevents a freshly started CPU from acting on them.

### 10.10 ROS 2 topic map

One node per bridged plant signal, one plant signal per node, checked in both directions. The topic
names are the vehicle layer's contract (`agv/forklift/README.md`); the BrowseNames here are the
authoritative PLC tag names. Message types are `std_msgs/Float64` and `std_msgs/Bool` throughout, so
the bridge's conversion stays what §9.2 permits: unit-preserving narrowing and widening, nothing else.

| Node (`Forklift/…`) | Direction (PLC view) | ROS 2 topic | Msg type | Field | Conversion | Cadence |
|---|---|---|---|---|---|---|
| `Output/ForkliftTractionSpeedRef` | PLC → plant | `/forklift/cmd/traction_speed` | `std_msgs/Float64` | `data` | `Float → float64` widening, m/s unchanged | polled 20 Hz, republished each cycle a value was read |
| `Output/ForkliftSteerAngleRef` | PLC → plant | `/forklift/cmd/steer_angle` | `std_msgs/Float64` | `data` | as above, rad unchanged | polled 20 Hz |
| `Output/ForkliftForkSpeedRef` | PLC → plant | `/forklift/cmd/fork_speed` | `std_msgs/Float64` | `data` | as above, m/s unchanged | polled 20 Hz |
| `Input/ForkliftForkHeight` | plant → PLC | `/forklift/fork_height` | `std_msgs/Float64` | `data` | `float64 → Float` narrowing, m unchanged | cyclic 20 Hz, latest sample (source 10 Hz) |
| `Input/ForkliftLinearSpeed` | plant → PLC | `/forklift/linear_speed` | `std_msgs/Float64` | `data` | as above, m/s unchanged | cyclic 20 Hz, latest sample (source 10 Hz) |
| `Input/ForkliftObstacleInStopZone` | plant → PLC | `/forklift/obstacle/in_stop_zone` | `std_msgs/Bool` | `data` | none — `TRUE` = object in the field, or the scan is invalid or stale | on change + refresh on (re)connect and after a detected server restart |
| `Input/ForkliftObstacleMinDistance` | plant → PLC | `/forklift/obstacle/min_distance` | `std_msgs/Float64` | `data` | `float64 → Float` narrowing, m unchanged, **no threshold** | cyclic 20 Hz, latest sample (source 10 Hz) |

Plant signals that exist and deliberately reach no node:

| Signal | Why it is not a node |
|---|---|
| `/forklift/scan` (`sensor_msgs/LaserScan`, 181 samples) | An array is not expressible in this node model, and the field verdict the PLC needs is already carried by two scalars (§10.5) |
| The plant's odometry topic (pose and twist) | The PLC needs one scalar speed for its interlocks and gets it. Pose is near-ground-truth in simulation and would give the program information a real vehicle-mounted sensor set does not supply — the `/cell/product_box/pose` reasoning of §9.8 |
| `/forklift/joint_states` | The one joint value the PLC uses is `fork_height`, which the vehicle layer derives and publishes as a single scalar. Selecting a joint out of an array is the bridge's addressing rule, but there is no reason to spend a node on the rest |
| `/forklift/gz/steer_cmd`, `/forklift/gz/traction_cmd`, `/forklift/gz/fork_cmd` | Simulator-internal command topics between the vehicle layer's node and `gz-sim`. The bridge touches neither them nor `gz` transport |
| `/clock` | Simulator infrastructure, not a plant signal, as in §9.8 |

The bridge's operational detail for these rows — slots, QoS, reconnect, the write allowlist and the
measurement method — lives in `docs/interfaces/bridge-design.md`, which **now carries the forklift
signal group** (m4f-05, 2026-07-29): its §4.7–§4.10 hold this table's operational half, §2.1 defines
the configured signal set that scopes every per-signal rule to the groups a run actually carries, and
§4.10 states as a design rule that the bridge never reads or writes the `Forklift/Hmi/` group. This
section remains the contract; where the two disagree, this one wins and the design is corrected.

### 10.11 Deliberately absent from the forklift subtree

Each row means "no such node under `DemoCell/Forklift/`".

| Not in this subtree | Why |
|---|---|
| Any safety node, safety mirror, e-stop, protective stop, STO or safety reset | Safety never traverses the network (invariant 1). This plant has no F-CPU, no safety-rated device and no SRS function; the obstacle stop is process logic and is named as such everywhere (ADR 0008 D3) |
| A second bridge heartbeat or a second bridge-link verdict | One session serves both function blocks; `DemoCell/Link/BridgeLinkOk` remains the single owner of "the bridge is alive" and the forklift FB consumes it as a shared DB bit (invariant 10, §10.1) |
| A fork **height** request, or any position or pose target | The operator jogs a speed. A height target would make the PLC a positioner running a profile, which is a sequencer this gate does not need and did not brief; the fork's soft limits already own the ends of travel |
| An HMI-writable output or status node | The HMI requests and displays. Making a verdict writable would give it two owners (invariant 10) and would let a client clear a latch by writing a node, which §10.7 forbids |
| A client-writable node for anything on the M3 cell | The forklift group is admitted by ADR 0008 D2 for the forklift cell. §9 is untouched: `DemoCell/Input/` still has the bridge as its only writer and `ConveyorSpeedCommand` is still not client-writable |
| Per-signal freshness or validity nodes | Freshness is the two heartbeats' job and validity is the plausibility windows'. A freshness node would move staleness policy into the interface (`bridge-design.md` §7.3) |
| Timers, step numbers, latch state, constants exposed for a client | Logic and sequencing belong to the PLC; exposing them would invite a client to act on them (ADR 0004, ADR 0005) |
| Order, traffic, zone-reservation or VDA 5050 data | Fleet data never lives on the PLC (invariants 3, 5). This plant carries no fleet identity at all (ADR 0008 D5) |
| A drive-fault verdict for the traction path | Not defined here: the starting contract for this gate carries no such node and the detection is PLC content that has not been briefed. Case D of `bridge-design.md` §7.3 — plant stopped, bridge alive, input image looks live — applies to this plant unchanged, so a verdict is worth having; raised as an open item rather than invented (§10.12) |

### 10.12 Open items carried out of this section

| # | Item | Owner |
|---|---|---|
| 1 | Every value in this section is a **design value until read back out of the tool** (§10.2 step 6): the folder tree, the per-tag rights, the node count and the browse path. Phase-0-style verification with a client that is not the bridge, recorded with its date | Owner, at commissioning |
| 2 | `bridge-design.md` had to describe the forklift path before any bridge work on this gate: the writable set of its §3, the signal map of its §4, the startup rule R3 ("all seven inputs") and the QoS table all needed the forklift signal set | **Closed by m4f-05, 2026-07-29.** §3's writable set and read set are now scoped per group with the `Forklift/Hmi/` group named as never touched; §4.7–§4.10 carry the signal map; §4.6 carries the QoS rows; and **R3 now reads "every input in the *configured* signal set"** (§2.1, §6.1), so a cell-only run counts 7, a forklift-only run counts 4, both count 11, and no run stalls the heartbeat waiting for topics it was never configured to carry |
| 3 | No `ForkliftDriveFault` node exists, so case D of `bridge-design.md` §7.3 has no PLC-visible verdict on this plant (§10.11). One status node would carry it; the detection is PLC content | Owner decision, then the PLC forklift FB specification |
| 4 | `TRACTION_SPEED_MAX` and `FORK_SPEED_MAX` are PLC constants this document does not set. The interface constraint is that `ForkliftLinearSpeed`'s plausibility window stays **at least twice** `TRACTION_SPEED_MAX`; at the ±2.00 m/s window that bounds the cap at 1.00 m/s, and raising the cap re-derives the window rather than tightening the margin | PLC forklift FB specification |
| 5 | The lidar field geometry — sector and stop distance — is configured in the vehicle layer and reaches the PLC as one bit (§10.5). If the owner prefers the PLC to own that threshold, `ForkliftObstacleInStopZone` is deleted and the PLC forms its verdict from `ForkliftObstacleMinDistance` alone: a one-node change here and a polarity change in the vehicle layer, not a redesign | Owner decision |
| 6 | Per-client write scoping remains policy rather than enforcement, and two writing clients widen the gap (ADR 0008 D2.5, §9.8's open item). Closing it is OPC UA access control plus the per-DB visibility work already carried | The gate that configures the server for a real client |
