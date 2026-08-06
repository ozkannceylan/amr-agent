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
| No mirror either | Unlike §4, this section carries no safety mirror. `Safety/EStopActive` in §4 remains the only informational mirror of **the fixed cell's** SF-01, and remains read-only and outside every causal chain; the twin's own instantiation of that logic is mirrored separately, on a different machine, at `Forklift/Safety/EStopDemand` (§11). |

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
defined in this document, and **no process timer is in the bridge** — the scope §10.1 rules: a
client's timers may watch its own cycle and its own input channels (the bridge's 20 Hz cadence, a
per-slot topic-freshness window such as §13 W1's), never a plant signal, a debounce, a fault delay
or a verdict the PLC also computes. Loss of the bridge is a degraded mode,
not a safety event (invariant 2), and nothing about it is a safety function.

**Scope: `BridgeLinkOk` is a §9 node and exists only where the §9 program runs.** Both nodes above
belong to the demonstration cell's node set, and only `BridgeHeartbeat` is shared with §10 and §11
(§9.8, §10.11). The forklift build **forms the same verdict and publishes it on no node**:
`#bridgeLinkOk` is a Temp inside its function block (`plc/forklift/SPEC.md` §7), §10.11 refuses a
second bridge-link verdict by name, and §11.7 refuses one for the mirror group — so on the
`safe_amr` CPU `Link/BridgeLinkOk` is not addressable and answers `BadNoMatch`, correctly and by
design rather than by omission. **The consequence for clients — the raw counter is then the only
readable liveness datum, and a counter is not a verdict — is ruled in `bridge-design.md` §7.5
(rules B1–B7), which is where a reader who cannot resolve this node should go.**

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
| What the HMI writes | **Only** the five `Forklift/Hmi/` request nodes and `Forklift/Link/HmiHeartbeat` (§10.4, §10.8) — **plus, from M5, `Forklift/Mode/HmiDriveModeRequest` and `Forklift/ProcessStop/HmiProcessStopRequest` (§12.1), making its every-cycle write set eight**. It writes nothing else on this server, on any interface, and nothing under the auto-published `DataBlocksGlobal` folder. |
| What the bridge writes | Its §9.1 writable set **plus** the four `Forklift/Input/` nodes — **plus, from M5, the two `Forklift/Vehicle/` nodes (§12.1) and `Forklift/Warning/ForkliftWarningFieldOccupied` (§13)** — and nothing more. The bridge never writes an `Hmi…` node and the HMI never writes an `Input/`, `Vehicle/` or `Warning/` node: the two clients' writable sets are disjoint by construction and distinguishable by BrowseName prefix. **This row is about writes.** From M5 the bridge also **reads** one node outside its own groups — `Forklift/Safety/TorqueOffDemand`, republished to the vehicle's torque-off stand-in (§11.2b **SD2**, §11.8 item 4) — and writes nothing in `Forklift/Safety/`, which is read-only to every client (§11.4 **MR1**). |
| No actuator writes, from either client | Neither client writes an actuator output. `Forklift/Output/*` is formed inside the PLC from the teleop-active flag combined with interlocks, and is driven to zero in a mandatory `ELSE` (§10.6). The HMI *requests*; the PLC decides and owns the outcome (invariant 6 discipline, ADR 0008 D2.2). |
| No logic in either client | The bridge remains a signal translator (§9.1). The HMI is a *source of requests and a display*: **no interlock, no latch, no sequencing, no setpoint formation, no reaction to plant state and no verdict the PLC also computes** (invariant 10, ADR 0008 D2.2, D2.6). **The line is not "no timer".** A client needs timers to produce its own cadence and its own liveness, and this model requires three of them by name: the bridge's 20 Hz cycle (`bridge-design.md` §5), the HMI's 10 Hz write cycle and the 5 Hz floor it holds itself to (§10.8 H2), and the HMI's window on its operator's page (§10.8 H6). What no client may do is time a **process value** — a debounce, a fault delay, a dwell, a stale window over a plant signal, "write only if stable for X ms" — because the threshold and the delay are process decisions and they belong to the PLC (§10.5, §10.7, `bridge-design.md` §1.1). **The test is what the timer watches**: its own cycle or its own input channel, never the plant, and never a verdict the PLC also computes. |
| Single owner | Every node below has exactly one writer, listed per tag in §10.3 (invariant 10). No value is recomputed by a consumer. |
| One link verdict per client, no duplicates | The bridge's liveness stays the single heartbeat at the browse path `DemoCell/Link/BridgeHeartbeat` — **no second bridge heartbeat is created for the forklift subtree**. **As built (owner decision 2026-07-30, m4f-04j): the `safe_amr` project has no demonstration-cell FB, so `FB_ForkliftTeleop` forms both link verdicts itself** — the heartbeat tag lives in `ForkliftLink` while its BrowseName and path are unchanged, and the bridge verdict is a Temp published on **no node** (`plc/forklift/SPEC.md` §3.1b). One bridge process, one counter, one verdict, one owner (invariant 10). **The heartbeat's browse path is a read-back, not a design value**: the DB behind it moved and the path must not, so the path is verified by independent browse and recorded with its date — resolved by the committed bridge config against the live CPU 2026-08-06 (m5-44). The HMI's liveness is a *separate and independent* watchdog on a different client (§10.8). |
| Not a safety path | Every node here is process data. The obstacle stop, the fork-height speed cap and the fork soft limits are **standard-program process interlocks** and implement **no** SRS function: not SF-02, not SF-03, not SF-04, not SF-07, not SF-09 (ADR 0008 D3). No SIL or PL is claimed for any of them, and neither "emergency" nor "protective" appears in any tag, node or topic **name** in this section — the same naming discipline §9.6 sets for the demonstration cell's process stop. Loss of either client link is a degraded mode, not a safety event (invariant 2). |
| Timing class | Both clients are best effort (invariant 9). Every timing decision **the cell's behaviour depends on** — the two link stale windows, the fault delays, the reset edge — is a PLC timer in the PLC's own time base. A client's own cadence and its window over its own input channel (§10.8 H2, H6) are best effort by construction, and no plant behaviour rests on either meeting a deadline. |

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
    Safety/   read-only F-safety mirrors (§11, M5 opening wave)
    Mode/ Envelope/ Vehicle/ ProcessStop/   the M5 autonomy delta (§12)
    Warning/  the warning-field verdict (§13)
```

Paths are relative to the interface node, as everywhere in this document:
`Forklift/Hmi/HmiTractionRequest` is
`Objects/ServerInterfaces/DemoCell/Forklift/Hmi/HmiTractionRequest` in full (§2.1).

**Five new global DBs, one per folder. The M3 DBs are not extended.** Adding members to
`DemoCellInput` and its siblings would move the offsets of tags that current evidence, watch tables
and test records depend on, and a download that leaves project and CPU inconsistent shows up as
monitoring errors on exactly the rows whose offsets moved (LESSONS 2026-07-28). Separate DBs leave
the M3 cell byte-identical, so its evidence stays reproducible while this gate is commissioned. A
sixth subfolder, `Safety/`, appears in the tree above: it is a later, separate addition under ADR
0009, with its own DB (`ForkliftSafetyMirror`, §11.3) rather than a sixth member of this delta, and
this paragraph's five is unchanged.

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
§9, and a client browsing from `Objects` sees more than either number. **This count is silent about
the later subfolders**: `Safety/` (ADR 0009, **6** nodes, §11 — 4 mirrors plus the SLS / SS1 pair),
the four M5 autonomy folders (9 nodes, §12) and `Warning/` (1 node, §13). With them the `DemoCell`
interface carries
15 (§9) + 18 (§10) + **6** (§11) + 9 (§12) + 1 (§13) = **49**, still fewer than a client
browsing from `Objects` sees.

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
| `HmiSteerRequest` | Real | Float | rad | −1.31 … +1.31 | ±1.35 | Requested steer angle of the front assembly, signed. The limit is the plant's mechanical steer range, enforced by the PLC's clamp: **§10.6 rules who owns `1.31` and what every other copy of it is**, including the HMI's |
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
stay stale after the DB reverts, because the next cycle rewrites the whole set (eight from M5, §10.8 H1). The failure recorded on
2026-07-28 — a reverted input image that a write-on-change client never repairs — cannot form here.

### 10.5 `Forklift/Input/` — plant state (bridge writes)

Owner is the Gazebo plant; the bridge is the transport, not the source, exactly as in §9.3. These are
the PLC's input image for the forklift and are read as wired field inputs would be.

| BrowseName | S7 type | OPC UA type | Unit | Range / plausibility window | Meaning |
|---|---|---|---|---|---|
| `ForkliftForkHeight` | Real | Float | m | travel 0.00 … 1.60; window **−0.05 … 1.70** | Carriage height above the mast's bottom stop, derived by the vehicle layer from the mast prismatic joint. The window is widened past both mechanical stops so a carriage resting **on** a stop is never called implausible — the `BELT_POSITION_MIN/MAX` reasoning of `plc/demo-cell/SPEC.md` §3.3 |
| `ForkliftLinearSpeed` | Real | Float | m/s | window **−2.00 … +2.00** | Measured chassis speed along its heading, signed, positive forwards, derived from the plant's odometry. The window is a statement about what the transducer can report, **not** a process cap: the cap is `TRACTION_SPEED_MAX` and is a different decision in a different layer |
| `ForkliftObstacleInStopZone` | Bool | Boolean | — | — | The lidar's **field-violation output**: an object inside the configured forward stop field. **`TRUE` is the non-permissive state.** The vehicle layer sorts every sample into three classes: **clear** — `+inf`, or a finite range at or beyond `range_max`, the sensor reporting no echo inside its window and counting as a valid measurement at `range_max`; **distance** — a finite range inside `[range_min, range_max)`; **invalid** — `NaN`, `-inf`, or a range below `range_min`. `TRUE` is published as a fail-safe only when there is no scan, when the newest one is older than 0.50 s, when the scan is structurally unusable, or when the sector holds no sample in **either** valid class — never on a beyond-range, clear scan (`74c7d5f`). See the polarity note below |
| `ForkliftObstacleMinDistance` | Real | Float | m | sensor window 0.10 … 8.00; plausibility **0.05 … 8.10** | Smallest valid range in the same forward sector, published for the operator display and for diagnostics. **`0.0` is the vehicle layer's no-data sentinel and sits deliberately outside the plausibility window**, so the PLC's affirmative window test reads it as a sensor fault at the same moment the field bit reads as an obstacle — two independent signals pointing the same, non-permissive way |

**Polarity, stated because it is the one input here that inverts §9.3's convention.** §9.3 names stop
*contacts* for their circuit state, so the tag reads `TRUE` when the machine may run and `FALSE` in
every failure case. `ForkliftObstacleInStopZone` reads `TRUE` in the failure case. It is named that
way on purpose and the conflation is written out rather than left to be discovered:

- The node mirrors a ROS topic whose polarity the vehicle layer owns, and **the bridge may not invert
  a signal** — inverting is listed as a violation of the no-logic rule (`bridge-design.md` §1.1), so
  a permissive-polarity node would require the inversion to happen in the transport.
- Fail-safety is therefore carried by three independent things instead of by the name: the vehicle
  layer publishes `TRUE` as a fail-safe on a missing, stale or structurally unusable scan, or a
  sector with no sample in either valid class — never on a beyond-range, clear scan (`74c7d5f`); the
  DB start value is `TRUE` (§10.9); and no input-derived verdict is evaluated at all while
  `BridgeLinkOk` is `FALSE` (§10.9).
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
| `ForkliftTractionSpeedRef` | Real | Float | m/s | ±`TRACTION_SPEED_MAX` | Traction speed setpoint, signed, positive forwards. Formed inside the PLC as **one multiplication**: `HmiTractionRequest` times the full-scale speed **in force**, which is `TRACTION_SPEED_MAX` normally and the fork-height speed cap while the carriage is raised. **The cap is a scale, not a ceiling**: what it changes is the multiplier, never a limit applied to the product afterwards. A request of `0.20` under the raised cap — `0.30` m/s in `plc/forklift/SPEC.md` §3.3, a process decision this document does not set — therefore commands `0.060` m/s, never `0.20`, and the operator keeps proportional control inside the reduced range. Then gated to `0.0` by the interlocks of §10.7 |
| `ForkliftSteerAngleRef` | Real | Float | rad | −1.31 … +1.31 | Steer angle setpoint, signed. Formed from `HmiSteerRequest` clamped in the PLC to the plant's mechanical range, and gated to `0.0` by the interlocks of §10.7 **exactly as the other two are** (ruling below). `0.0` is the centred wheel, and it is a commanded centre, not a hold |
| `ForkliftForkSpeedRef` | Real | Float | m/s | −0.15 … +0.15 | Fork jog velocity setpoint, signed, positive raises. Formed from `HmiForkRequest` scaled by `FORK_SPEED_MAX`, aborted **in the offending direction only** at a soft travel limit, and gated to `0.0` by the interlocks of §10.7. `0.0` means hold: the plant holds the carriage against gravity |

**Gating a Real means an unconditional assignment with a mandatory `ELSE`.** Interface expectation
for the PLC specification, restated because it is the analogue-output rule this project has already
been bitten by: each of the three setpoints is assigned in **exactly one statement** in the whole
project, on every call, with the interlock-failed branch driving it to `0.0`. A conditional write
with no `ELSE` leaves the Real holding its last value, so the machine keeps moving after the stop
(LESSONS 2026-07-27, `plc/demo-cell/SPEC.md` §6.4). This is what ADR 0008 D2.3 requires of the HMI
watchdog and what §10.7's obstacle stop requires of the obstacle path; both are the same statement.

**Ruling: all three setpoints, the steer angle included, take `0.0` in the interlock-failed `ELSE`.**
An earlier revision of the row above exempted steering, on the ground that a steer angle is a
position rather than a motion and that centring it would move the wheel of a machine that is supposed
to be stopping. **That exemption is withdrawn**: it contradicted this section's own gating paragraph
and the words ADR 0008 D2.3 uses, and `plc/forklift/SPEC.md` §6.4 implements the zero. Three reasons,
in the order they decide it:

- **A hold needs stored state; the zero needs none.** Holding the last angle means a static carrying
  an operator demand across a stop — the stale sequence state CLAUDE.md §9 tells the machine to
  re-read at restart rather than resume from.
- **One rule across three analogue outputs is the one that survives being read in a hurry.** An
  exemption for one output of three is the shape of the defect this paragraph exists to prevent.
- **What the exemption was protecting against does not occur.** All three assignments execute in the
  same call, so the wheel is re-aimed on a machine whose traction setpoint has already gone to `0.0`:
  the steer joint moves, the machine does not.

**The visible consequence, stated here so it is not discovered on the recording: the steered wheel
returns to centre while the machine is stopping.** It appears in every stop scenario and is not a
defect. If the owner rules the other way it is one branch in the PLC specification and one row here;
no node, count, access right or start value moves either way.

**Who owns ±1.31, and what every other copy of it is.** Two different questions meet on this number and
each has exactly one answer. **The value is the plant's**: it is the `steer_joint` mechanical stop in
the vehicle layer's model, surfaced by that layer as `steer_limit_rad` (`agv/forklift/config.yaml`). It
is a mechanical fact, not a process decision, which is what makes it unlike `TRACTION_SPEED_MAX` — that
one is a process cap the PLC owns (§10.12 item 4). **The authority over what the plant is commanded is
the PLC's clamp, in this section**: `ForkliftSteerAngleRef` is formed from `HmiSteerRequest` clamped to
this range inside the PLC, and nothing reaches the plant except through that assignment
(`plc/forklift/SPEC.md` §3.3 `STEER_ANGLE_MAX`, which cites the vehicle layer's value as its source).
That is the single enforcement point in the command path. The HMI has none, and no client has one.

**Every other copy is derived and names this section as its source.** Nobody re-derives `1.31` from
anything; each copy restates the published value and cites where it comes from, which is what keeps one
owner under invariant 10. The HMI holds it as a named constant beside its citation rather than as a
config key, deliberately, so it cannot be retuned as though it were a deployment setting —
`hmi/config.yaml` states the same rule from the other side, that no threshold, limit, scale or clamp
lives in that file. **That copy is scaling, not authority**: it converts a dimensionless joystick
position into the rad the node declares, so it decides what the operator's stick *means* and never what
the machine does, and **it cannot apply a value the PLC would not**. Set too large it does not widen the
machine's travel — a request between `1.31` and `1.35` is clamped here, and one past `1.35` leaves the
plausibility window of §10.4 and is read as a broken client rather than as a demand. Set too small it
only means the operator cannot reach full lock. The plant's own joint limit clamps as well, and that is
a last-ditch mechanical stop in another layer rather than a second authority — the same reading §10.12
item 4 gives the vehicle layer's traction clamp.

**A test double or a harness may hold its own copy**, and two do. That is not a second owner: an
instrument that imported the value it is checking would check nothing. Those copies are written against
this section and are meant to fail loudly if they ever disagree with it.

The bridge republishes each value to its ROS topic **unchanged** — no ramp, no clamp, no interlock,
no zeroing of its own (invariant 6, `bridge-design.md` §1.1) — and the plant applies it as given,
including while the operator has let go of the controls. Stopping the machine is the PLC's job, and
that is what this gate demonstrates.

### 10.7 `Forklift/Status/` — PLC verdicts, read-only for both clients

PLC-derived values with no corresponding plant signal, in the standing of §9.5: read by the HMI for
its display, by the bridge for logging, applied to no actuator.

| BrowseName | S7 type | OPC UA type | Meaning |
|---|---|---|---|
| `ForkliftTeleopActive` | Bool | Boolean | The PLC's verdict that teleop is enabled: `HmiTeleopRequest` held, both link verdicts `TRUE`, no latch standing. **Entered on a rising edge** of that request and never restored by a returning permissive (§10.8 P5); **a level** once entered, and the separate layer from the setpoints — machine state and actuator command are different things (CLAUDE.md §9), which is why this is not the same node as `ForkliftTractionSpeedRef` being non-zero |
| `ForkliftObstacleStopActive` | Bool | Boolean | A **latched** process stop, raised by `ForkliftObstacleInStopZone` and cleared only by the monitored reset of §10.8. Standard-program process logic; **not** SF-03 and not a protective stop (ADR 0008 D3). The field clearing does not release it: this machine does not resume by itself (CLAUDE.md §9) |
| `ForkliftSpeedLimitActive` | Bool | Boolean | **The fork-height cap is the multiplier in force**: `TRUE` while teleop is active and the carriage is raised (`plc/forklift/SPEC.md` §6.5's `forkRaised`), **regardless of the momentary demand**, so the flag is steady while that condition holds and never follows the operator's control. It therefore reads `TRUE` at zero demand as well, when nothing is being reduced yet; that is the cost of this reading and it is the right one for a display and for a recording. **The discarded reading is "the cap is biting"** — named so it cannot be re-derived: under §10.6's scale semantics the capped setpoint is below the uncapped one at *every* non-zero demand, so that verdict degenerates to "the operator is asking for something" and would drop out each time the control crossed centre. Informational — the reduction itself happens in the setpoint (§10.6). **Not** SF-04 and no PL is claimed |
| `ForkliftResetRequired` | Bool | Boolean | A monitored, edge-triggered reset is pending before teleop may be enabled again. Set by any latch above, by a link loss (§10.8), **and from M5 by the operator's process-stop latch (§12.7 PS5)** — it stays the single answer to "is a monitored reset pending". **No client clears it by writing a node**: the only reset input is `HmiResetRequest`, and the edge and the arming are PLC program content |

Interface expectations for the PLC specification, each a process decision this document does not
make: the fork-height speed cap's height and reduced speed; the fork soft travel limits, which must
be **direction-scoped aborts** and never a blanket permissive, because a carriage sitting on a limit
can only leave it by moving (LESSONS 2026-07-27); and the fault delays. A latch is never a term in
its own clearing condition (LESSONS 2026-07-27), so the reset tests the live world, not the latches.

**One conflation this gate carries, written out where teleop is defined: there is no start request.**
§10.4 defines five requests and none of them is a start, so `HmiTeleopRequest` doubles as the enable
*and* as the post-reset start action. The operator's sequence after any latch is therefore *release
the enable, press reset, assert the enable again*: an enable left asserted through the reset produces
no rising edge and the machine stays stopped, which is the no-automatic-resume behaviour CLAUDE.md §9
requires (`plc/forklift/SPEC.md` §6.7). This follows the rule the M3 cell set for exactly this
situation — when a gate mandates a CLAUDE.md §9 behaviour and the signal table has no device for it,
implement the behaviour on an existing device, state the conflation, and **request the missing device
rather than inventing a tag** (LESSONS 2026-07-27). That request is §10.12 item 7; it is post-gate,
because a sixth request node changes the node count, a DB, a start value and the HMI's write set in a
group that is being commissioned. Until it is taken, the conflation is correct behaviour and not a
defect.

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
| H1 | The HMI writes **all of its nodes** every cycle — **eight from M5**: the five requests, the heartbeat, and the two §12 requests (`HmiDriveModeRequest`, `HmiProcessStopRequest`, §12.1) — never on change. A stream is self-repairing: a CPU restart that reverts the DB is corrected by the next cycle (LESSONS 2026-07-28) |
| H2 | Cycle rate **10 Hz nominal, 5 Hz contractual floor**. Below the floor the HMI is not a supervision source and must stop writing rather than write slowly |
| H3 | The heartbeat is written **last**, after the cycle's five request writes are acknowledged. An advanced heartbeat therefore implies that cycle's requests landed first. This is an **ordering** guarantee, not atomicity: no PLC logic may require two HMI tags to have come from the same cycle |
| H4 | The counter is a counter, never a timestamp: no epoch, no clock synchronisation, no time zone in a liveness signal. It is not reset across a reconnect and starts from an arbitrary value at HMI restart |
| H5 | **Two ways out of a running HMI, and only these two.** A **clean shutdown** — `SIGINT`/`SIGTERM`, the operator stopping the process — writes **no farewell value and zeroes nothing**: the counter stops, the server keeps the last requests it was sent, and noticing that is the PLC's job. A **backend fault or a dropped session is not a shutdown**: the deadman fires first, because a control stream that is no longer being carried is a release, so the controls go to rest; the counter then stops; and **one bounded attempt, never retried**, writes what the controls now hold, which is that rest state. Nothing else is written on the way out on either path, and on reconnect the HMI re-publishes nothing beyond the current state of its controls. Neither path stops the machine or claims to (§10.6), and **no PLC behaviour may distinguish them** (below) |
| H6 | **The operator's presence is watched too, and what is watched is the page.** The browser's unconditional `GET /state` at **5 Hz** doubles as a liveness beacon: any HTTP request from the page refreshes it, and the poll is what guarantees one arrives while no control is being touched. If none arrives for **`UI_POLL_STALE_TIME`** — a named constant, **five poll periods, `1.0 s`** (derived below) — the backend fires **the same deadman as H5's fault path**: all five requests go to rest, the enable included, **while the write cycle and the heartbeat continue**. The process is healthy and keeps saying so; what is gone is the page. Nothing latches and nothing is demanded of the operator: this is invariant 2's degraded-mode pattern one level up, at the operator boundary, and it is **process behaviour, not a safety function** (invariant 1, ADR 0008 D3). The page's controls are carried again as soon as it posts, but **each Bool only once that page has been seen to send it low** — P6's per-session arming, one level up |

**Semantics, interface expectation for the PLC specification.**

| # | Rule |
|---|---|
| P1 | Test `HmiHeartbeat <> LastHmiHeartbeat` — **inequality only**. Never subtract, never test for `+1`, never assume monotonic ordering across the wrap or across an HMI restart |
| P2 | `HmiLinkOk := HmiSeenAlive AND NOT HmiStaleTimer.Q`, where `HmiSeenAlive` is a non-retain latch with start value `FALSE`, set by the first observed change. **The link verdict is `FALSE` from the first scan and stays `FALSE` until the heartbeat has actually moved**: "not yet proven stale" is not "alive", and every guard that rides on link-up inherits this boot polarity (LESSONS 2026-07-28, ADR 0008 D2.3). A verdict formed from the stale timer alone would read `TRUE` for the whole first stale window of every CPU run, before a single operator input had ever arrived |
| P3 | The stale window is a **named constant**, `HMI_STALE_TIME`, **`T#600ms`** — three times the 200 ms period the 5 Hz floor allows. The **rule is three worst-case write periods**, not this number: if the HMI's measured worst-case period at commissioning exceeds 200 ms, the constant is re-derived from the measurement rather than the floor being quietly reinterpreted |
| P4 | `HMI_STALE_TIME` is **its own constant**, never shared with `HEARTBEAT_STALE_TIME`. The two watch different clients at different rates, and retuning one must not silently retune the other (invariant 10, the `BELT_FAULT_DELAY` precedent) |
| P5 | On `HmiLinkOk` `FALSE`: **all three setpoints of §10.6, the steer angle included**, are driven to `0.0` in the mandatory `ELSE` — "every motion setpoint" is not the test, because a steer angle is arguably not a motion and the exemption that reading invited is withdrawn (§10.6) — `ForkliftTeleopActive` drops, and the loss **latches** — `ForkliftResetRequired` is set and a returning heartbeat never by itself restores teleop (ADR 0008 D2.3, CLAUDE.md §9). No request value is evaluated while the verdict is `FALSE`; the requests are then not attributable to an operator |
| P6 | **The reset edge is armed per link session.** A rising edge of `HmiResetRequest` counts only if the PLC has already observed that node `FALSE` **while `HmiLinkOk` was `TRUE` within the current link session** — the arming latch clears whenever `HmiLinkOk` is `FALSE`. Without it, a reset held from before link-up registers as an edge the moment the link forms and clears every latch with no operator acting at the moment of clearing, which is the automatic resume CLAUDE.md §9 forbids. A guard scoped per session is tested by **ending a session**, not by restarting the machine (LESSONS 2026-07-28) |
| P7 | Teleop requires **both** link verdicts: `BridgeLinkOk` (the plant's state is attributable) and `HmiLinkOk` (the operator is present). They are independent watchdogs on independent clients and neither substitutes for the other |

**H5's two paths, and why the fault path writes at all.** The split is the behaviour
`hmi/EVIDENCE_HMI.md` records — §A.9 for both stops, §A.8 for a session lost with a full demand
standing, §B.8 for the PLC catching a clean stop 650 ms later — and it is ruled here because the two
clauses that meet in it were written for different situations. H5's "beyond the current state of its
controls" was written about *reconnect*; the fault path reaches the same wording by a different route,
and the route is now stated rather than re-derived by whoever reads it next.

- **A clean shutdown is a decision; a fault is a loss.** Stopping the process deliberately says nothing
  about where the operator's controls were, so H5 leaves them exactly where they are — and that is the
  better demonstration, because it leaves the server holding a live-looking demand under a stopped
  counter, which is precisely the condition the watchdog exists to catch. Losing the backend or the
  session means the browser's stream of control updates is no longer being carried, which is a
  **release**: the same deadman that runs when the operator lets go of the stick, with the same meaning.
- **What lands is not a farewell value.** A farewell value is one chosen for the way out — a "safe"
  number nobody asked for. What this writes is the controls' actual state after a release, which is
  rest. Inventing a value on the way out is exactly what the bridge is forbidden to do
  (`bridge-design.md` §7.3 B, §8.3 N5), and this rule stays on the same side of that line.
- **The counter stops before the write, not after.** H3 makes an advanced heartbeat mean "that cycle's
  requests landed first". The final write inverts that order deliberately so it can never be read as a
  cycle: the counter has already stopped when it goes out.
- **One attempt, bounded, never retried.** A dying process must not keep writing under a stopped
  counter. The attempt is made once, with a timeout, and its outcome is logged either way — `FAILED`
  with no session (§A.8) and `LANDED` under a live one (§A.9) are the whole range of outcomes.

**No PLC behaviour may distinguish the two paths.** This is `bridge-design.md` §7.3's rule for the
bridge's own cases A and B — "a program that behaves differently for A and B is wrong" — and it holds
here for the same reason: the difference is confined to what a later reader of the server's retained
values sees, never to what the machine does. The PLC's reaction is P5's and is identical either way —
the stale timer expires, all three setpoints take `0.0` in the mandatory `ELSE`, `ForkliftTeleopActive`
drops and the loss latches. `plc/forklift/SPEC.md` satisfies this already and needs no change: it reacts
to `HmiLinkOk` alone and evaluates no request while that verdict is `FALSE` (§10.9). The clause exists
so that nothing later is built on a difference the HMI is not promising to keep.

**`UI_POLL_STALE_TIME` — the derivation, and what the poll does not prove.** The page polls `/state`
every 200 ms, so five periods is `1.0 s` and the window tolerates four consecutive missed polls. **The
rule is the multiple, not the millisecond**: if the page's poll period changes, the constant is
re-derived from the new period, exactly as P3 re-derives `HMI_STALE_TIME` from a measured worst case
rather than quietly reinterpreting the floor. Three stale windows now exist in this cell, and no two of
them share a derivation:

| Constant | Watches | Watcher | Window | Derivation |
|---|---|---|---|---|
| `HEARTBEAT_STALE_TIME` | `BridgeHeartbeat`, 50 ms nominal | PLC | `T#500ms` | ≈ 10 missed beats (`plc/demo-cell/SPEC.md` §3.3) |
| `HMI_STALE_TIME` | `HmiHeartbeat`, 100 ms nominal | PLC | `T#600ms` | 3 × the 200 ms the 5 Hz contractual floor of H2 allows (P3) |
| `UI_POLL_STALE_TIME` | the page's `GET /state`, 200 ms | **the HMI backend** | `1.0 s` | 5 × the poll period — a browser honours no floor, so the multiple absorbs jitter the watched side cannot bound |

- **Why five here and three there.** P3 may use three because H2 gives it a floor the watched party
  contractually honours: below 5 Hz the HMI stops writing rather than write slowly. A page honours no
  floor — `setInterval` is best effort and a beat can be lost to the main thread, to garbage collection
  or to the operating system — so the same rule, a small multiple of the worst-case period, lands on a
  larger multiple from a weaker premise.
- **Its own constant, never shared with `HMI_STALE_TIME`** — P4's principle one level up. The two watch
  different parties across different transports, one from the PLC and one from inside the HMI, and the
  names are deliberately not near-copies of each other so that retuning one cannot read as retuning the
  other.
- **The cost of the window, stated so the choice is visible.** One second is the longest a demand made
  by an absent page can stand; at `TRACTION_SPEED_MAX` = `1.00` m/s (`plc/forklift/SPEC.md` §3.3) that
  is at most a metre of travel before the requests go to rest. **This is not a stopping distance and no
  safety distance is claimed**: the reaction is process behaviour, this plant has no safety-rated stop,
  and stopping the machine remains the PLC's (invariant 1, ADR 0008 D3).
- **What the poll proves, and what it does not.** It proves the *page* is alive. It does not prove a
  person is in front of it: an operator who walks away from a live browser leaves the poll ticking, and
  no timer this layer can run would notice. What H6 closes is the crashed, frozen, closed or
  disconnected browser, demonstrated in `EVIDENCE_HMI.md` **§E** — and the remainder is stated rather
  than covered, in the standing of case D's honest limitation for the bridge heartbeat
  (`bridge-design.md` §7.3).
- **This layer has two 5 Hz polls and H6 is about one of them.** The subject is the browser's
  `GET /state` over loopback HTTP. The backend's own 5 Hz OPC UA read of `Forklift/Input/`,
  `Forklift/Output/`, `Forklift/Status/` and `HmiLinkOk` for the display is a different poll on a
  different transport, and it has no part in this rule.

**Why the heartbeat keeps running under H6, and why nothing latches.** Stopping the counter would say
"the HMI is gone", which is false, and would buy the PLC's heavier reaction: a link loss latches
`ForkliftResetRequired` and demands a monitored reset before teleop may return (P5, P6). A page that had
merely been backgrounded would then cost a reset. The two reactions are proportional on purpose — the
heavier failure, the whole process gone, is caught faster (`HMI_STALE_TIME`, 600 ms) and latches; the
lighter one, the page gone under a healthy process, is caught more slowly and does not. The PLC is told
nothing new in either case: it sees requests at rest under a live heartbeat, a state it already handles,
because §10.6 forms every setpoint from those requests in one assignment.

**Recovery is a release, not a resume.** The three Reals are carried again as soon as the page posts —
they move nothing while `ForkliftTeleopActive` is `FALSE`. The two Bools are different: a page that
thaws with the enable still asserted would otherwise produce a `FALSE → TRUE` on `HmiTeleopRequest` that
no operator made, and the PLC cannot tell that edge from a real one (§10.7). So each is carried again
only once that page has been seen to send it low — P6's per-link-session arming, applied to the HMI's
own input channel. In the ordinary case it costs nothing: the page already returns everything to rest,
the enable included, on blur, on hide and on unload, so a page coming back from the background has sent
both low before it is asked to.

**Where H6 sits against "no logic in either client" (§10.1).** A timer over the client's **own input
channel** stands exactly where H2's timer over its **own cycle** stands: it watches this process's
liveness, never a process value; it forms no interlock, no latch over a plant signal and no verdict the
PLC also computes; and it decides only what this client publishes, never what the machine does. H6 adds
**no node, no start value and no PLC expectation** — the node count of §10.3 and the start values and
qualification rule of §10.9 are untouched — which is what makes it a rule this section can take while
the group is being commissioned.

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
| `Input/ForkliftObstacleInStopZone` | plant → PLC | `/forklift/obstacle/in_stop_zone` | `std_msgs/Bool` | `data` | none — `TRUE` = object in the field, or the fail-safe of §10.5 — never on a beyond-range, clear scan (`74c7d5f`) | on change + refresh on (re)connect and after a detected server restart |
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
| Any safety node other than the read-only mirrors of §11 — a safety command, e-stop input, protective stop, STO or safety reset | Safety never traverses the network (invariant 1): no node in this subtree is a safety path, carries a demand, or can affect one — that is what this row has always meant, and it is unchanged. **What has expired is the premise, not the claim** (analysed in §11.8): this row was written under ADR 0008 for a plant whose CPU had no F-runtime group; ADR 0009 replaced that CPU with a 1513F-1 PN that now instantiates SF-01, SF-08 and the SF-07 pattern, still with no safety-rated device — simulated F-input stand-ins only (ADR 0009 D5). What that CPU exposes on this interface is bounded to the **six** read-only `Forklift/Safety/` mirrors of §11: read-only views, never a reaction channel, and no route by which a client can create, prevent or clear a safety reaction (§11.4). One of the six, `TorqueOffDemand`, is **read** by the bridge and consumed by a labelled process-side stand-in on the vehicle (§11.2b **SD2**, **SD9**); that is a consumer acting on a copy, still no client write and still no path into the F-runtime group. The rest of this row stands word for word (§11.7). The obstacle stop remains process logic, named as such everywhere (ADR 0008 D3) |
| A second bridge heartbeat or a second bridge-link verdict | One bridge process, one counter at `DemoCell/Link/BridgeHeartbeat`, one verdict with one owner (invariant 10, §10.1). As built the forklift FB forms that verdict itself from the shared heartbeat (m4f-04j, §10.1) — still no second heartbeat and no second verdict, and on the `safe_amr` build the verdict is published on no node at all — measured 2026-08-06, where `Link/BridgeLinkOk` answers **`BadNoMatch`** by direct address. What a client must therefore do with the raw heartbeat is `bridge-design.md` §7.5 B1–B7; adding a published verdict here would start by reversing this row, in this document, and is not a build step |
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
| 3 | **Open, and now confirmed from the PLC side.** No `ForkliftDriveFault` node exists, so case D of `bridge-design.md` §7.3 — plant stopped, bridge alive, the input image frozen at plausible values — has no verdict on this plant (§10.11). `plc/forklift/SPEC.md` §8 carries it as **case P** and states the gap rather than papering over it: `ForkliftLinearSpeed` is read and qualified but feeds no verdict, so a frozen image under a live link is indistinguishable from a machine the operator is holding still. One `Forklift/Status/` node would carry the verdict; the detection is PLC content and has not been briefed, and inventing the verdict without a node to publish it on was declined on both sides | **Open request**, recorded not covered: owner decision, then the PLC forklift FB specification (`plc/forklift/SPEC.md` §12 item 3, `bridge-design.md` §12 item 12) |
| 4 | `TRACTION_SPEED_MAX` and `FORK_SPEED_MAX` are PLC constants this document does not set. The interface constraint is that `ForkliftLinearSpeed`'s plausibility window stays **at least twice** `TRACTION_SPEED_MAX`; at the ±2.00 m/s window that bounds the cap at 1.00 m/s, and raising the cap re-derives the window rather than tightening the margin | **Closed by m4f-04, 2026-07-29.** `plc/forklift/SPEC.md` §3.3 sets `TRACTION_SPEED_MAX` = **`1.00` m/s**, which meets the relation at its bound: window ±2.00 ≥ 2 × 1.00. `FORK_SPEED_MAX` = `0.15` m/s, matching `ForkliftForkSpeedRef`'s declared ±0.15 range (§10.6). **The relation stays live in one direction**: a higher cap re-derives the window *here first* (1.50 m/s would require ±3.00 m/s in §10.5) and only then changes the constant — the margin is never tightened to fit a bigger cap. The vehicle layer's own 1.50 m/s clamp is a different layer's last-ditch limit; because 1.00 < 1.50 the PLC never asks for a speed that clamp would touch |
| 5 | The lidar field geometry — sector and stop distance — is configured in the vehicle layer and reaches the PLC as one bit (§10.5). If the owner prefers the PLC to own that threshold, `ForkliftObstacleInStopZone` is deleted and the PLC forms its verdict from `ForkliftObstacleMinDistance` alone: a one-node change here and a polarity change in the vehicle layer, not a redesign | Owner decision |
| 6 | Per-client write scoping remains policy rather than enforcement, and two writing clients widen the gap (ADR 0008 D2.5, §9.8's open item). Closing it is OPC UA access control plus the per-DB visibility work already carried | The gate that configures the server for a real client |
| 7 | **An `HmiStartRequest` node in `Forklift/Hmi/`, requested by `plc/forklift/SPEC.md` §6.7 and its §12 item 4.** This section defines five requests and none is a start, so `HmiTeleopRequest` carries both the enable and the post-reset start action; the conflation and the operator's release-and-reassert sequence are written out in §10.7. A sixth request node would restore the M3 cell's two-device separation — a reset that clears and a separate start that energizes | Owner decision, **post-gate**. It moves the node count, the `ForkliftHmi` DB, a start value (§10.9), the HMI's every-cycle write set (§10.8 H1) and the PLC's enable edge together, which is not a change to make inside a commissioning run. Until then the conflation stands and is stated, not hidden |
| 8 | **H6 was ruled ahead of its implementation; H5 was not.** H6 asked `hmi/` for five things: one timestamp refreshed by **every** request the page makes on the loopback endpoint, `UI_POLL_STALE_TIME` held as a named constant with its derivation beside it, the **existing** deadman fired when the window expires with the write cycle and the heartbeat left running, the two Bools re-armed only after the page has been seen to send each low, and the transition logged and rendered in `/state` so a page that returns learns why its controls were dropped. **H5 needed no code**: the split it rules is the behaviour already implemented and evidenced (`EVIDENCE_HMI.md` §A.8, §A.9, §B.8), and its three added clauses — one bounded attempt never retried, the counter stopping before the final write, nothing else written on the way out — were satisfied as built; H5's fourth clause binds the PLC specification instead, and `plc/forklift/SPEC.md` satisfies it by reacting to `HmiLinkOk` alone | **Closed by `7675960`, 2026-07-29** (`docs/reports/m4f-07b-h6-and-holdable-reset.md`). All five asks are implemented and demonstrated in `hmi/EVIDENCE_HMI.md` **§E** — `check_hmi_h6_and_reset.py`, 34 checks, no failures, against the PLC logic double. **Kernel K1** (§E.2–E.3) is this item's closure: the page's poll is frozen with the backend alive, all five requests read at rest 1063 ms after the last request against the 1000 ms window, the heartbeat increments straight through the drop, `HmiLinkOk` stays `TRUE` and `ForkliftResetRequired` stays `FALSE` — the process behaviour H6 specifies, with nothing latched — and recovery is the release rule, a page that thaws holding both Bools asserted getting neither carried. **Kernel K2** (§E.4) is the same commit's other half, `plc/forklift/SPEC.md` §11 T5.4 driven from the operator's endpoint, closing `m4f-08` finding 3 rather than this item. **One residual is carried, not erased**: `EVIDENCE_HMI.md` §D records that section C's browser pass predates the change and was not re-run, so the page's DOM handlers are unexercised since — E.4 drives the endpoint the page posts to, not the events. That is `hmi/`'s to close and it does not reopen this item |

## 11. Forklift safety mirrors (M5 opening wave)

**Six nodes. Five are display diagnostics; one has a consumer that acts on it, and this section says
which consumer and what it must do.** All six are read-only to every client, **no PLC logic reads any
of them** (§11.3), and **no client write can create, prevent or clear a safety reaction** — neither on
this path nor on any other. What changed when the SLS / SS1 pair arrived (m5-49, m5-59) is that one
mirror, `TorqueOffDemand`, is carried to the vehicle and consumed there. **§11.2b states the required
reaction in full rather than leaving the consumer to choose one**, which is the residue m5-11 left in
§12 and this section does not repeat.

**The safety demand never traverses the network; the mirror of it does.** The demand forms from
simulated F-inputs, latches, and lives inside the F-runtime group of one CPU (ADR 0009 D3.1). What
leaves that CPU is a **process consequence** — the standard program's motion permissive dropping and
its three setpoints going to `0.0` (§10.6) — and a **copy of a flag**. A copy is not a cause, and the
mirror of a demand is not the demand (ADR 0009 D3.3, `plc/forklift-safety/SPEC.md` §6.2 S3).

**Where the copy now reaches a consumer, the claim is stated rather than assumed.** The vehicle's
torque-off stand-in latches on the mirror of `TorqueOffDemand`, so on this plant a **simulation of
the SS1 second stage is stimulated across the network**. It stands in for a hardwired onboard inhibit
that **does not exist on this plant at all** (`plc/forklift-safety/SPEC.md` §1.2 N7); the consumer is
Python on the process side of the vehicle; and the F-input path behind the demand is a labelled
stand-in on a **standard** DB written by an engineering process over a TCP link (ADR 0015,
`plc/forklift-safety/SPEC.md` §7.8). **No PL, no Category, no SIL and no PFH is claimed, achieved or
implied by any part of that path, and no stopping time or distance is claimed for it** (ADR 0011 D5,
`docs/safety/SRS.md` §5.1). In one line: *the demand is real logic in a CPU; everything it reaches on
the vehicle is a model of a reaction, and the network is standing in for a wire the architecture puts
onboard.* **SD9** and §11.8 item 8 carry it, and the showcase narration says it where the reaction is
shown.

Added by **ADR 0009**, which opens the cell-scope core of M5 first, on the M4 forklift twin, under a
fallback rule. **Nothing in this section closes M5, and nothing here is an acceptance test passed**
(ADR 0009 D2.3, D2.4; `plc/forklift-safety/SPEC.md` §1.2 N5) — see §11.8. The F-side names, meanings
and start values below are `plc/forklift-safety/SPEC.md` §6, which is the contract this section
consumes; where the two disagree, that document wins on what the flags mean and this one wins on what
the nodes are called and who may read them.

**Why this reads *opening wave* and not *early*, stated once for the whole section.** **ADR 0010**
(accepted 2026-07-30) restructures the gates above M4 and **extends ADR 0009 rather than superseding
it**: what that ADR opened early on the forklift twin becomes M5's own subject matter (D2), so its
scope table, coupling architecture and wording discipline carry into the new M5 unchanged. The new
M5 is wider than the gate ADR 0009 opened against — safety scanners wired into the F-blocks, a
navigation lidar, SLAM and Nav2 on the forklift, HMI v2, closed by a **recorded safety + autonomy
showcase** — and it lands on **this twin** rather than on the fixed cell (D2, D7). So these four
nodes — four then, six now — are no longer an exception to gate discipline ahead of their gate; they
are the **opening wave** of M5 itself. Nothing else here changes, and the two statements that matter survive the
restructure untouched: nothing in this section closes M5, and a node existing is not an acceptance
test passed. `plc/forklift-safety/SPEC.md` §1.2 N5 makes the same reconciliation from the F-side and
uses the same term.

**The parent folder is the forklift *cell*, not the vehicle.** `Forklift/` is the commissioning
cell's subtree (§10), and the demands mirrored here are **cell-scope** demands formed in the CPU:
the logic of SF-01 and the SF-07 pattern, guarding a machine that happens to be vehicle-shaped. This
plant has **no onboard safety layer at all** — no scanner, no protective field, no STO, no bumper
(`plc/forklift-safety/SPEC.md` §1.2 N7) — and a reader watching a forklift stop must not infer one
from a folder name.

### 11.1 The path ruling — why these mirrors cannot land on the bare `Safety/` path

**Ruling: the twin's mirrors are `DemoCell/Forklift/Safety/`, a sixth subfolder in the `Forklift/`
subtree of the existing `DemoCell` server interface. They are not added to the top-level `Safety/`
group of §4.** This resolves the collision `plc/forklift-safety/SPEC.md` §6.4 note 2 raised and left
open, and it takes the resolution that document suggested.

**It also answers a question an accepted ADR routed here.** ADR 0007 wrote, of the safety gate:
*"Whether the mirrors appear in the M1 `Safety/` group or in the cell interface is an interface
question, requested and not decided here."* The answer is **the cell interface**, in the subtree of
the cell whose F-runtime group they mirror.

The collision is not a leaf-name inconvenience. §4 already defines `Safety/SafetyResetRequired` for
the **fixed cell**, and the twin's F-side flag carries that exact leaf name — so the bare path is not
two nodes with similar names, it is **one full browse path for two different values**:

| Why the bare path is forbidden | Detail |
|---|---|
| **One node cannot hold two values** | `Safety/SafetyResetRequired` is §4's node for the fixed cell's SF-08 mirror. Putting the twin's flag there gives one node two writers and two meanings, which is invariant 10 broken at the node rather than at the tag. A client that resolved it could not tell which machine it had answered about |
| **Neither leaf can move** | §4's leaf is cited by name in `docs/safety/SRS.md` §4, as SF-08's informational mirror. The twin's leaf is fixed by `"InstF_Forklift_Safety".SafetyResetRequired` and by CLAUDE.md §9, which requires a node name to mirror its PLC tag exactly so the two documents can be diffed. **The thing that has to move is the path, because it is the only part of the address neither side owns by name** |
| **The distinct path costs no edit to any existing sentence** | Every statement in this project that says `Safety/…` — SRS §4 and B1, `handshake-tables.md` §1's no-auto-resume rule, its §6 cell-safety-status row enumerating exactly four `Safety/` nodes, and `docs/roadmap.md` row M5 — still refers to precisely the group it was written about, and stays true untouched. A merged group would have made that four-node enumeration incomplete and made *"if any `Safety/` mirror shows a tripped function"* ambiguous across two machines with two F-programs |
| **Different cells, different clients, different gates** | §4's group belongs to the **target cell served to the fleet manager** and is unbuilt. This group belongs to the **commissioning cell served to the HMI** on the `DemoCell` interface. §2.2's folder layout describes the first; §9.2 and §10.3 describe the second. A twin node in §2.2's tree would put the twin inside the fleet manager's cell |
| **It keeps §9.8's refusal row alive** | §9.8 states that no safety node, safety mirror or safety-function reset exists **in the §9 node set**, and ADR 0007 predicted that row would be voided when a safety layer arrived. It is not voided: §11 adds nothing to §9's four folders. The M3 demonstration cell still carries no mirror of anything, its red mushroom is still a process stop (§9.6), and the row stands set-scoped and unedited |

**The folder keeps the name every upstream document already uses.** ADR 0009 D3.3, `TWIN-DEMO-MAP.md`
R3 and `docs/roadmap.md` row M5 all say *"the `Safety/` mirrors"*. What this ruling changes is the
folder's **parent**, not its name, so those sentences read naturally against either group and the
full path is what disambiguates.

**Three "reset required" values now exist in this project, and no two share a path, a folder or an
owner.** The second collision `plc/forklift-safety/SPEC.md` §6.4 note 3 raised is the standard-side
one, and it is resolved by the same ruling:

| Value | Full path | Owner | Means | Cleared by |
|---|---|---|---|---|
| Fixed cell, F-layer | `Safety/SafetyResetRequired` (§4) | the fixed cell's F-CPU, **unbuilt** | a monitored reset is pending on the fixed cell | a local monitored reset on that cell; never over the network |
| Twin, F-layer | `Forklift/Safety/SafetyResetRequired` (§11) | the twin's F-runtime group | at least one F-latch stands on the twin | `"SafetyInputStandIn".ResetButtonPressed`, an F-input stand-in **no client can reach** (`TWIN-DEMO-MAP.md` R1) |
| Twin, **process** | `Forklift/Status/ForkliftResetRequired` (§10.7) | `FB_ForkliftTeleop`, standard program | a process latch or a link loss stands | `Forklift/Hmi/HmiResetRequest`, a client write, on its rising edge |

The two twin rows differ in **both** folder and leaf, which is what `TWIN-DEMO-MAP.md` R4 asks for:
the process flag and the safety flag never share a node, and the two reset *inputs* are on opposite
sides of the client boundary — one is a client write, the other is unreachable from any client.

### 11.2 `Forklift/Safety/` — the six mirror nodes

| BrowseName | S7 type | OPC UA type | Mirrors, exactly | Meaning |
|---|---|---|---|---|
| `EStopDemand` | Bool | Boolean | `"InstF_Forklift_Safety".EStopDemand` | The **logic of SF-01** is latched in the F-runtime group: the simulated cell e-stop circuit was seen open. **Latched** — it stays `TRUE` after the circuit closes again, and only a monitored reset clears it |
| `ZoneStopDemand` | Bool | Boolean | `"InstF_Forklift_Safety".ZoneStopDemand` | The **SF-07 pattern** is latched: the simulated marked-zone device circuit was seen open. **This is not the lidar obstacle stop** — that is `Forklift/Status/ForkliftObstacleStopActive`, standard-program process logic, a different node in a different folder with a different owner (§11.4 MR7) |
| `SafetyResetRequired` | Bool | Boolean | `"InstF_Forklift_Safety".SafetyResetRequired` | The `OR` of the two above: **a monitored reset is required**, including while its cause still stands. It does not answer *"would a reset be accepted now?"* — that is `CauseGone`, an F-internal that is deliberately not a node (§11.7) |
| `SafetyResetFault` | Bool | Boolean | `"InstF_Forklift_Safety".SafetyResetFault` | The reset **device stand-in** is stuck or bridged: held past `RESET_HOLD_MAX`, or pressed and never seen open since the F-runtime group started. A diagnosis of a device, never a demand |
| `SpeedMonitorDemand` | Bool | Boolean | `"InstF_Forklift_Safety".SpeedMonitorDemand` | The **SLS-pattern speed monitor** (the logic of SF-10) has latched: on an armed speed chain, one of its four live causes stood for its own time — a tread reading beyond the limit in force, a reading gone stale, the two channels discrepant, or both readings near zero while the world was observed moving (`plc/forklift-safety/SPEC.md` §11.5 SL8/SL11/SL15/SL18, D1). **Latched** — it stays `TRUE` after every cause clears, and only a monitored reset drops it. **It carries no speed, names no limit and reports no margin** (**SD7**) |
| `TorqueOffDemand` | Bool | Boolean | `"InstF_Forklift_Safety".TorqueOffDemand` | The **SS1 sequencer's second stage** (the logic of SF-11): under a standing `Ss1Demand` — which is `ZoneStopDemand OR SpeedMonitorDemand`, the cell e-stop deliberately excluded — either standstill was confirmed from both channels or `SS1_TIME_MAX` expired, whichever came first. **Not a latch of its own**: it holds for the life of the demanding cause and falls when that cause's latch is cleared by the monitored reset, which is SF-11's *"no latch of its own"* rule (`docs/safety/SRS.md` SF-11 reset row). **This is the one mirror a consumer acts on** — §11.2b |

**All six are Bool. There is no other type in this group and no analogue value of any kind** — no
timer, no elapsed time, no count, no timestamp, and in particular **no speed and no limit** (§11.7).

**`Ss1Demand` is deliberately not a node, and its absence is a ruling rather than an omission.** It
is the live `OR` of two flags that already have nodes, so mirroring it would put a computed aggregate
on the wire (§11.7's refusal, invariant 10) and give the SS1 path a second observable that could
disagree with its own inputs. What a reader needs from the sequencer is **whether stage two is in
force**, which is `TorqueOffDemand`; what a *diagnostician* needs is the watch table, which reads
`Ss1Demand` and its timer directly from F-data (`plc/forklift-safety/SPEC.md` §11.8 Group 5).

**Ruling: the BrowseNames are the F-side tag names exactly, with no prefix.** CLAUDE.md §9 requires
OPC UA node names to mirror PLC tag names exactly so the two documents can be diffed, and
`plc/forklift-safety/SPEC.md` §3.2 states that these mirror names diff against those tags. A
`Safety…` or `Forklift…` prefix would make this the only place in the project where a mirror is
renamed away from its source, and it would break a three-way diff — this table, the TIA export, and
`plc/forklift-safety/SPEC.md` §6.1 — for a word the folder already carries.

That is a deliberate departure from §10.3's `Forklift`-prefix convention, and the departure is
narrow. **That convention answers "which client may write this tag" from the BrowseName alone**;
here the answer is *none*, for every node in the group, which the folder and the access rights both
already say. The diff property is worth more than the repeated word, and the group is small,
uniform and unwritable.

**`EStop` in a node name is correct here, as it is in §4, and in exactly those two places.** §10.1's
naming discipline keeps "emergency" and "protective" out of every **process** node name precisely
because those nodes implement no SRS function. This node mirrors an F-latch that implements the
*logic* of one, so the rule cuts both ways: an `EStop…` name in this project means an F-layer flag
and nothing else (`TWIN-DEMO-MAP.md` §5, which admits "e-stop" **only** for the F-side stand-in
device and its demand). The discipline for §9 and §10 is unchanged and now matters more, because a
correct use exists one folder away from the lidar stop that must never borrow it.

**Ruling: `SafetyResetFault` is a mirror node.** `plc/forklift-safety/SPEC.md` §6.4 note 1 left the
fourth flag to this document. It is admitted, for four reasons in the order that decides it:

- **It is exactly what this group is.** A group of display diagnostics that omitted the one flag
  saying *"the reset device is lying to you"* would be a curated view rather than a mirror.
- **AT-08 (a)'s "reset-fault flagged" half needs an observable** that is not only the watch table, if
  it is ever to be shown to anyone not sitting in TIA.
- **It costs one Bool** in a data block being created anyway: no new folder, no new DB, no new
  client write, no change to any other group.
- **The watch table keeps it regardless.** `plc/forklift-safety/SPEC.md` §8 Group 2 reads all four
  from F-data directly; this node is an addition to that instrument, never a replacement for it.

Whether it also becomes a **lamp** is `hmi/`'s decision, not this document's (§11.8 item 5).

### 11.2b The required consumer reaction — specified here, not chosen by the consumer

**Why this subsection exists.** §12 minted four data and left the vehicle's reaction to them
unspecified; four conservative readings were implemented in the vehicle layer and the residue is
still open in `docs/TODO.md`. The two nodes above are the pair most likely to repeat that, because one
of them is the only mirror in this model with a consumer that **acts**. So the reaction is stated
here, in this document's own voice, in the shape §12's **M**, **E**, **V**, **PS** and §13's **W**
rules take: **interface expectations, binding on `agv/`, on `bridge/` and on `hmi/`**. Each rule says
what a consumer must do, and each says what it must do when the value is stale, absent or never
resolved.

| # | Rule |
|---|---|
| **SD1** | **`SpeedMonitorDemand` has exactly one class of consumer, and it is a display.** No vehicle-side consumer, no ROS topic, no bridge slot, no gate term (§11.8 item 4's second half). **The reaction to the speed monitor's demand is the PLC's**, and the PLC forms it from **F-data read directly** — the motion permissive's third conjunct, `NOT SpeedMonitorDemand` (`plc/forklift-safety/SPEC.md` §11.8) — never from this node, because a consumer never recomputes an owned value (invariant 10, **MR4**). **What reaches the vehicle is the consequence, not the flag**: the permissive drops, `ForkliftTeleopActive` falls, the three §10.6 setpoints take `0.0` in their mandatory `ELSE`, and the envelope goes non-permissive. **Through no stop topic of its own** — §12.7 **PS6**'s rule, applied a second time and for the same reason: a second path to one reaction is a second owner of it |
| **SD2** | **`TorqueOffDemand` is the one mirror a consumer acts on, and this is the act.** On an **observed `TRUE`** the vehicle's torque-off stand-in latches open: it forwards no further actuator command, **drives the traction terminal to a standing `0.0`** — the holding brake — and **holds the steer and fork terminals at their last forwarded values**. The terminals are commanded explicitly rather than left silent, because silence is a standing order wherever a consumer republishes or holds (LESSONS 2026-08-04). The vehicle-side contract this states against is `agv/forklift/PLANT-CHANGE-INVENTORY.md` §10 and `plc/forklift-safety/SPEC.md` §11.7's obligation table; **this row is the interface half of both, and neither may be widened without changing it** |
| **SD3** | **While it stands, the vehicle is deaf, and the envelope has no vote.** `ForkliftMotionEnable` returning `TRUE`, a ceiling rising off `0.0`, a fresh `HmiTeleopRequest`, a mode change, a new goal — **none restores actuator authority**. The permission layer and the torque layer are different layers, and the reaction that removed torque is not one an envelope may undo. This is what makes SS1's two stages distinguishable at the plant rather than nominal |
| **SD4** | **An observed `FALSE` restores authority and commands nothing.** The demand falls only when the demanding latch is cleared by the monitored reset inside the F-program, which no client can reach by any route (**MR3**). Motion then requires a **fresh affirmative command**: the value standing at the terminal is the brake's, and clearing a latch energizes nothing (§12.7 **PS4**, CLAUDE.md §9) |
| **SD5** | **A stale, silent or never-resolved `TorqueOffDemand` is NOT torque-off — and this is the one place in this document where absence is not the non-permissive reading.** The consumer latches on an **observed `TRUE`** and releases on an **observed `FALSE`**; a link that never speaks leaves it closed. Three reasons, and they are not interchangeable: loss of supervision is a **degraded mode, not a safety event** (invariant 2); the controlled stop that a lost supervision link calls for **already exists one layer up**, in the envelope gate's freshness rule (§12.4 **E5**), so inferring a stop here would be a second owner of it; and torque removal is **asserted, never inferred**, because putting a safety reaction on the network's silence would make every run without a bridge a dead vehicle and would put on the network exactly what invariant 1 keeps off it. **The consumer therefore holds no freshness window over this topic at all** — there is nothing for it to decide when the value stops arriving |
| **SD6** | **SD5 does not weaken §11.6, and the two answer different questions.** §11.6 rules the node's **start value** — `TorqueOffDemand` starts **`TRUE`**, because that is its source's start-state truth — which covers the scans before the standard program's first copy. **Consequence, stated so it is not discovered on stage: at every CPU start the vehicle is torque-off until a monitored reset clears the boot latches**, which is the no-auto-resume rule arriving at the plant rather than a fault. *What the server holds before the first write* is this document's; *what a consumer does with a value it never received* is **SD5**'s; the two are different questions and their answers differ deliberately |
| **SD7** | **A demand crosses this seam, never a speed.** Neither new node carries a speed, a limit, a threshold, a margin, a channel reading or the value that was exceeded — one Bool per latch and nothing else (ADR 0014 D4: *no motion value crosses seam (a)*). The SLS limit itself (`SPEED_LIMIT_MAX`) and the readings it compares are **F-program constants and F-statics that reach no node** (`plc/forklift-safety/SPEC.md` §11.3, §11.8). A consumer wanting to know *how fast it was* asks the watch table; a row here that answered it would be the wrong row, and §11.7 refuses it by name |
| **SD8** | **No consumer recomputes, merges or infers a demand.** The vehicle does not derive torque-off from anything it can otherwise see — not from `SpeedMonitorDemand`, not from `SafetyResetRequired`, not from a zeroed setpoint, not from a withdrawn envelope. No display merges the two new nodes with each other, with `Forklift/Status/ForkliftObstacleStopActive` or with `Forklift/ProcessStop/ForkliftProcessStopActive`: four latches, four owners, four causes, and **MR7**'s discipline covers all of them. **A vehicle that stopped is not a vehicle that cannot move**, and the readback that tells them apart is the vehicle layer's own applied-state topic, which commands nothing |
| **SD9** | **Everything SD2–SD4 describes is a labelled stand-in, and every artefact that shows it says so.** The consumer is process-side Python simulating the **effect on the plant** of a hardwired onboard inhibit this plant does not have; the demand behind it rides an F-input path built on a standard DB. **No PL, Category, SIL or PFH is claimed, achieved or implied**, no stopping time or distance is claimed, and "torque removed" means *the simulated plant received no actuator command and a standing zero at the traction terminal* — never that energy was removed from a drive (ADR 0011 D5, `docs/safety/SRS.md` §5, §5.1, `plc/forklift-safety/SPEC.md` §1.2 N1–N4) |
| **SD10** | **The bridge-stopped case, stated rather than left to be inferred.** With the bridge stopped and the OPC UA session down, the F-layer's reactions still execute in the CPU — the latch forms, the permissive drops, the setpoints go to `0.0`, the mirrors update — and `docs/roadmap.md` M5 item (b) is about exactly those, for SF-01, SF-07 and SF-08. **What does not execute is the simulated plant's torque removal**, because on a hardware-free plant the bridge is the only path to it. That is a property of the simulation, not of the architecture, in which the inhibit is hardwired and onboard (invariant 1, CLAUDE.md §3's thick arrow). **No run may claim an SS1 plant reaction with the bridge down, and no narration may imply one** |

**One observation this pair makes untrustworthy, and the rule that repairs it.** Once a consumer can
make the plant deaf, *the vehicle did not move* stops being evidence of anything: a correct refusal, a
latched contactor and a contactor that was never started produce the identical observation (LESSONS
2026-08-06). **Any run that asserts a reaction to either node carries a positive control in the same
run** — the same command moving the vehicle through the same path with the demand absent. This
document states it because it is a property of the interface it just created, not only of the test.

### 11.3 Ownership, the data block and per-tag access rights

**One new global DB, `ForkliftSafetyMirror`, holding all six Bools.** Not new members of
`ForkliftStatus`: adding members moves the offsets of the four M4 status tags that current watch
tables and evidence depend on, and a download that leaves project and CPU inconsistent shows up as
monitoring errors on exactly the rows whose offsets moved (§10.3, LESSONS 2026-07-28). A new DB
leaves the M4 group byte-identical while it is being commissioned.

**The DB name deviates from the `Forklift<Folder>` pattern by one word, deliberately.**
`ForkliftSafety` would sit one underscore from `F_Forklift_Safety [FB2]`, the safety block itself,
and two things that must never be confused would be told apart by punctuation. With `Mirror` in the
name, the word appears in every fully qualified tag, every watch-table row and every screenshot —
the same reasoning `plc/forklift-safety/SPEC.md` §7.1 gives for naming the stand-in DB after what it
stands in for.

| DB | Folder | Contents | *Accessible from HMI/OPC UA* | *Writable from HMI/OPC UA* |
|---|---|---|---|---|
| `ForkliftSafetyMirror` | `Forklift/Safety/` | 6 mirror tags | ✔ | **✘ (all six)** |
| `InstF_Forklift_Safety` (F instance DB) | — | the F-program's whole write set | **✘** | ✘ |
| `SafetyInputStandIn` (F-input stand-in) | — | the three simulated F-input channels | **✘** | ✘ |

The last two rows are `plc/forklift-safety/SPEC.md` D1 and D7, restated here because they are what
makes this group **the only client-visible view of F-state**. No client reads F-data directly and no
client reaches an F-input on any path, including the auto-published `DataBlocksGlobal` folder.

Per-tag ownership. **The value's owner and the node's writer are different roles here, and both are
single** (invariant 10):

| Node (`Forklift/Safety/…`) | Value owner — single source of truth | Node writer | Readers |
|---|---|---|---|
| `EStopDemand` | the F-program, `"InstF_Forklift_Safety".EStopDemand` | PLC **standard** program, copying | HMI (display), owner in the watch table |
| `ZoneStopDemand` | the F-program, `"InstF_Forklift_Safety".ZoneStopDemand` | PLC standard program, copying | HMI (display), owner in the watch table |
| `SafetyResetRequired` | the F-program, `"InstF_Forklift_Safety".SafetyResetRequired` | PLC standard program, copying | HMI (display), owner in the watch table |
| `SafetyResetFault` | the F-program, `"InstF_Forklift_Safety".SafetyResetFault` | PLC standard program, copying | HMI (display), owner in the watch table |
| `SpeedMonitorDemand` | the F-program, `"InstF_Forklift_Safety".SpeedMonitorDemand` | PLC standard program, copying | HMI (display), owner in the watch table. **No bridge slot and no vehicle consumer** (**SD1**) |
| `TorqueOffDemand` | the F-program, `"InstF_Forklift_Safety".TorqueOffDemand` | PLC standard program, copying | HMI (display), owner in the watch table, **and — uniquely in this group — the bridge, which republishes it to the vehicle's torque-off stand-in** (**SD2**; the slot is `bridge-design.md`'s, §11.8 item 4) |

**Why the safety program does not write its own mirrors.** It could — the tool permits an F-block to
write a standard DB, and the build of 2026-07-29 did exactly that. It must not: one tag has one
writer, and a client-visible node written by the safety program would put safety data on the wire
under the safety program's name (ADR 0009 consequences, `plc/forklift-safety/SPEC.md` §3.4). The
F-program's entire write set is its own instance DB; the standard program reads that DB and copies.

**The copy derives nothing.** No threshold, no combination, no inversion, no filter, no timer. Each
node is one unconditional assignment from one F-flag of the same name, so a mismatch is visible on a
single line and a diff of the two documents is a diff of two identical name lists.

**Zero PLC readers: the mirror group is a leaf of the data flow inside the CPU.** The standard program
writes these six and **no program logic reads one**. Both motion-permissive terms that mention a
demand — the two of §6.1 and the third added with the speed monitor — are derived from the **F-data
directly** (`plc/forklift-safety/SPEC.md` §6.1, §11.8), never from a mirror, because a consumer never
recomputes an owned value (invariant 10, §6.2 S3). **If any PLC logic ever reads a mirror, this group
stops being a view and becomes a causal element inside the CPU** — checkable by cross-reference rather
than by assertion, and unchanged by everything below.

**Outside the CPU the claim is narrower now, and the narrowing is written rather than absorbed.**
Until the SLS / SS1 pair landed, no consumer anywhere acted on a mirror. `TorqueOffDemand` is the
exception and the only one: the bridge republishes it and the vehicle's torque-off stand-in latches on
it (**SD2**). So the sentence *"they feed no logic anywhere in this project"*, true of the four, is now
true of **five of the six**, and this document says which one and what it feeds instead of keeping a
sentence that has stopped being true. Three things it does **not** change: no client may write any of
the six (**MR1**), no client write can create, prevent or clear a safety reaction (**MR2**), and no PLC
logic reads a mirror (above). **MR2's second reason survives intact and still stands alone** — the
standard program rewrites all six unconditionally every cycle, so a write that somehow landed would
be a display artefact shorter than one PLC scan.

### 11.4 What no client and no program may do

| # | Rule | Why |
|---|---|---|
| **MR1** | **No client writes any of the six.** *Writable from HMI/OPC UA* is cleared per tag, so a defect in either client is refused **by the CPU** | Read-only is enforcement here, not policy (ADR 0009 consequences, §10.3) |
| **MR2** | **No client write can create, prevent or clear a safety reaction — and this holds independently of MR1.** No PLC logic reads a mirror (§11.3) and the standard program rewrites all six unconditionally every cycle, so a write that somehow landed would be a display artefact shorter than one PLC scan, overwritten before it could be read. **`TorqueOffDemand`'s vehicle consumer does not weaken this**: a client cannot write the node (MR1), the copy is unconditional (**MR5**), and the reaction the consumer performs is a *simulation* of a plant effect which creates, prevents and clears nothing inside the F-runtime group (**SD9**) | Two independent reasons, on purpose. A claim this load-bearing does not rest on one access-right checkbox |
| **MR3** | **No client clears an F-latch by any route.** The only reset input is `"SafetyInputStandIn".ResetButtonPressed`, an F-input stand-in unreachable from any client. `Forklift/Hmi/HmiResetRequest` is the **process** reset and clears standard-program latches only | `TWIN-DEMO-MAP.md` R1, R2; §10.4, §10.7 |
| **MR4** | **No consumer recomputes a demand** — not from a mirror, not from a combination of mirrors, not from plant state | Invariant 10; `plc/forklift-safety/SPEC.md` §6.2 S3 |
| **MR5** | **The copy is unconditional and happens every cycle.** A conditional mirror write leaves a display saying "clear" after a demand has formed | `plc/forklift-safety/SPEC.md` §6.2 S5 |
| **MR6** | **One copy path, one node per flag.** No second mirror of any of the six exists anywhere in this model, on any interface — and no second **topic** carries a demand the vehicle already receives (**SD1**, **SD8**) | A second mirror is a second answer to one question (invariant 10) |
| **MR7** | **The zone demand and the lidar process stop never share a node, a lamp, a caption or a sentence.** `Forklift/Safety/ZoneStopDemand` and `Forklift/Status/ForkliftObstacleStopActive` are two nodes, in two folders, with two owners and two reset paths, and no display may merge or co-locate them | `TWIN-DEMO-MAP.md` R4; `plc/forklift-safety/SPEC.md` §1.3 — the single most likely place for this project's central claim to be misread |

**`on-change` here describes the subscription, not the write.** A client subscribes to these as it
does to any Bool verdict in §9.5 and §10.7. The PLC's own behaviour is MR5's: the DB members are
assigned every cycle whether or not they changed, and the server reports the change when there is
one. The two statements are about different sides and neither weakens the other.

**One caveat, stated rather than discovered.** The per-tag *Writable* attribute is a property of the
**DB member**, so it is expected to govern the auto-published `DataBlocksGlobal` path as well as the
interface path — §9.8 records that at the commissioned access settings the DB path is not otherwise
write-protected, and §9.8's open item to suppress DB-level exposure is unchanged by this section.
**That expectation is a design value until it is read back out of the tool**, which is why §11.5 step
6 asks for a **write attempt and its refusal**, not only a read. MR2's second reason is what keeps
the outcome of that test off the safety path; it is run anyway, because the M5 criterion is a
statement about what a client **cannot** do, and the only evidence for a negative is an attempt.

### 11.5 TIA click path (the §10.2 / `plc/demo-cell/SPEC.md` §4.2–§4.3 pattern)

1. CPU → *OPC UA communication* → *Server interfaces* → open the **existing** `DemoCell` interface.
   Do **not** create a second interface and do **not** rename this one: the interface name **is** the
   namespace URI (ADR 0006, §10.2).
2. **Read the namespace URI back** and confirm it still reads `http://DemoCell`. Nothing is entered;
   the field is derived and not editable. This read-back is repeated after any *Change device*, which
   is known to delete server interfaces silently (LESSONS 2026-07-27).
3. Create **one** new global DB `ForkliftSafetyMirror` with the six Bools of §11.2, *Accessible from
   HMI/OPC UA* ✔ and *Writable from HMI/OPC UA* **✘ on every member**. A new DB, **not** new members
   of `ForkliftStatus` (§11.3). **As built the first four landed first**: the two SLS / SS1 members
   and their leaves are added by `plc/forklift/TIA-FIX-PROCEDURE.md` chunks AD and AE, whose step 7 is
   gated on this section carrying their rows — which it now does.
4. In the interface, add a folder `Safety` beside `Hmi`, `Input`, `Output`, `Status` and `Link` under
   `Forklift`, then drag the six tags into it. **Rename nothing**: each leaf must remain the
   BrowseName of §11.2, so this document, the TIA export and `plc/forklift-safety/SPEC.md` §6.1 can
   be diffed three ways.
5. Download, then confirm the block diff circles are solid green before testing (LESSONS
   2026-07-28). No offset in `ForkliftStatus` moves, because nothing was added to it — **check its
   watch-table rows monitor without the error icon anyway**, since "should not have moved" is not a
   verification.
6. Browse with a client that is **not** the bridge; read all six at their start values (§11.6), then
   **attempt one write and record the refusal with its status code and the date**. A read proves the
   nodes exist; only the refused write proves the read-only claim. Record both in the manner of
   §9.10.

> **Everything in this section is a design value until step 6 is executed.** The folder, the six
> BrowseNames, the per-tag rights, the start values and the refusal are what this document asks the
> tool for; they become facts when they are read back out of it (LESSONS 2026-07-27, ADR 0006). **No
> gate criterion may rest on one before then** — least of all a criterion about a client being unable
> to write.

### 11.6 Start values, and what an absent mirror means

Interface expectation for the PLC specification — start values, **not** logic:

| Node | Start value | Reading |
|---|---|---|
| `EStopDemand` | **`TRUE`** | The F-side value at every CPU start: `"SafetyInputStandIn".EStopCircuitClosed` starts `FALSE`, so the demand is latched from the first F-cycle of every run |
| `ZoneStopDemand` | **`TRUE`** | Same, from the zone circuit |
| `SafetyResetRequired` | **`TRUE`** | The `OR` of the two above. A monitored reset is genuinely required at every CPU start, before the machine can be enabled at all |
| `SafetyResetFault` | `FALSE` | The reset device stand-in starts unpressed and nothing has been diagnosed. `TRUE` would assert a device fault no one has observed |
| `SpeedMonitorDemand` | `FALSE` | **The one start value in this group chosen against the fail direction, and the reason is that the source cannot be `TRUE` yet.** The monitor arms on the first fresh reading of a run (`SpeedChainSeen`), and before that no cause can fire and its latch cannot be set: the F-side truth at every CPU start is `FALSE` (`plc/forklift-safety/SPEC.md` §11.5 SL3, §11.9 Q16's no-source signature). A `TRUE` here would assert a demand the F-program has not made — the same defect as a `FALSE` on a standing latch, in the other direction |
| `TorqueOffDemand` | **`TRUE`** | The F-side value at every CPU start: `ZoneStopDemand` boots latched (row 2), so `Ss1Demand` stands from the first believed F-cycle and `Ss1Timer` expires within a second of every boot. **The consequence is real and is the correct one**: at every CPU start the vehicle is torque-off until a monitored reset clears the boot latches (**SD6**) |

**The rule is: a mirror's start value is its source's start value, not the type's zero.** The mirror's
only job is to be right about the source, and the one moment it can be wrong for free is the scan
before the first copy executes. A display reading "clear" then would be the boot-polarity defect
LESSONS 2026-07-28 records for `BridgeLinkOk`, one layer up: **"not yet written" is not "clear"**,
exactly as "not yet proven stale" was not "alive". Four of these six are therefore not the type's
zero, deliberately, in the standing of §10.9's `ForkliftObstacleInStopZone`. **The rule is "match the
source", not "choose the non-permissive value"**, and `SpeedMonitorDemand` is where the two would part
company: its source really is `FALSE` at every start, and asserting a demand the F-program has not
made would be a different lie in the other direction.

As in §10.9, **start values are the last line, not the first**: the standard program overwrites all
six in its first scan either way, and the F-side truth they are chosen to match is `TRUE`, `TRUE`,
`TRUE`, `FALSE`, `FALSE`, `TRUE` at every CPU start, in this table's order
(`plc/forklift-safety/SPEC.md` §3.1, §11.9 Q16).

**The fallback, and it needs no document edit** (ADR 0009 D4). The DB, the folder and these nodes are
created by the **same delta** that adds the copy statements to the standard program — which held for
the first four and holds again for the SLS / SS1 pair, whose two members, two copy statements and two
leaves are one delta in `plc/forklift/TIA-FIX-PROCEDURE.md` chunks AD–AF. If
the F-layer is not built, that delta is not applied: no DB, no folder, no nodes, and the M4 teleop
demonstration stands alone with its criteria unchanged.

**An absent mirror renders as absent, never as clear** (`plc/forklift-safety/SPEC.md` §6.4 note 4).
A client that cannot resolve these BrowseNames shows the group as *not present* and greys it; it
never substitutes a `FALSE`, and it never treats an unresolved node as a value. **No client's connect
may fail over this group**: five of the six are outside the bridge's configured signal set
(`bridge-design.md` §2.1) and the group is optional for the HMI, so a server without it is a server
with an unbuilt F-layer, not a server in error. **For `TorqueOffDemand` the same rule reads through to
the plant and lands on SD5**: an unresolved leaf means no topic, no message and therefore **no
torque-off** — asserted, never inferred — and a bridge that cannot resolve it logs the absence and
publishes nothing rather than synthesising either polarity.

**The status an S7-1500 actually returns for the unbuilt leaf is `BadNoMatch`** — measured, not
assumed: read directly at 2026-08-06T21:58Z against the commissioned instance, where
`Forklift/Safety/` was advertised and carried the **four** mirrors of the 2026-08-06 build while
`TorqueOffDemand` and `SpeedMonitorDemand` (chunks AD–AF) answered `BadNoMatch` (m5-62,
`bridge/tools/probe_server_paths.py`, read-only; the CPU was not written). A client's tolerance is
scoped to the not-found statuses — `BadNoMatch`, `BadNodeIdUnknown`, `BadNotFound` — and any other
failure remains a connect failure, so this rule cannot become a general amnesty for a broken address
space (`bridge-design.md` §4.12).

### 11.7 Deliberately absent from `Forklift/Safety/`

Each row means "no such node in the §11 node set", in the set-scoped sense §9.8 fixes.

| Not in this group | Why |
|---|---|
| Any writable node, of any kind | Nothing a client writes can reach the F-layer. This is the group's defining property, not a restriction on it (§11.4 MR1, MR2) |
| A safety reset, reset request, acknowledge, inhibit, mute or override node | Safety never traverses the network (invariant 1). §8's "safety commands" row holds here word for word, and `TWIN-DEMO-MAP.md` R1 forbids a client write clearing an F-latch by any route |
| The F-program's internals — `CauseGone`, `ResetSeenOpen`, `ResetPressArmed`, `ResetHoldValid`, `ResetPulse`, either timer's `ET` or `PT` | They answer *"why did the reset not fire?"*, which is an engineering question asked at the machine, and they are already answered by the watch table (`plc/forklift-safety/SPEC.md` §8 Group 3). Exposing logic state invites a client to act on it (§9.8, §10.11) |
| **A speed, a speed limit, a margin, a channel reading or the value that was exceeded** | **SD7**, and it is ADR 0014 in this group's terms: a **demand** crosses the seam, never a motion value. `SPEED_LIMIT_MAX`, `SPEED_STANDSTILL_MAX`, `SpeedReadingA`/`B`, `SpeedDiff` and every speed timer are F-program constants and F-statics that reach no node (`plc/forklift-safety/SPEC.md` §11.3, §11.8). §13.1 runs the same test on the warning node and it is run again here |
| `Ss1Demand`, `VehicleStandstillNow`, `SpeedCauseGone`, `SpeedChainSeen` or any of the four live causes | The first is a computed `OR` of two flags that already have nodes (§11.2's ruling); the rest are the F-program's internals, in the standing of the `CauseGone` row above. All are read from F-data in the watch table's Group 5 |
| A "cell safe", "safety OK" or "all clear" aggregate | Safety states are never merged into a computed flag used for control — each layer acts only on its own inputs (`handshake-tables.md` §6, invariants 1, 7). The `OR` this cell needs is `SafetyResetRequired`, formed in the F-program, with one owner |
| A mirror of the **fixed cell's** SF-01, SF-05, SF-07 or SF-08 | Those are §4's, on the target cell served to the fleet manager, and are unbuilt. This group mirrors the twin's F-runtime group and nothing else (§11.1) |
| A PL, SIL, Category, diagnostic-coverage or channel-count node | No achieved PL, no Category and no safety-rated input is claimed anywhere on this plant (ADR 0009 D5, `plc/forklift-safety/SPEC.md` §1.2 N2–N4) |
| A reaction time, latch age, demand timestamp or any Time value | No timing is claimed here: this program has no output to de-energize and no millisecond figure is measured (`plc/forklift-safety/SPEC.md` §1.2 N1). A timestamp on a mirror would read as a measured reaction time |
| A second bridge or HMI heartbeat, or a link verdict for this group | One heartbeat per client, unchanged (§9.7, §10.1). A mirror group has no liveness of its own; its freshness is the standard program's cycle |

### 11.8 What §11 does not close, the §10 seam, and open items

**The seam with §10.11, stated plainly because this document would otherwise read as contradicting
itself.** §10.11's first row says *"Any safety node, safety mirror, e-stop, protective stop, STO or
safety reset — no such node under `DemoCell/Forklift/`"*, and §11 adds six safety mirrors under
exactly that path. The row is **not an error and was not wrong when written**:

- **Its invariant-1 half is unchanged and is what the row is really about.** No node in §11 is on a
  safety path, carries a demand, or can affect one. The obstacle stop is still process logic and is
  still named as such everywhere (ADR 0008 D3).
- **What expired is its premise.** The row was written under ADR 0008 for a plant whose CPU had no
  F-runtime group — *"this plant has no F-CPU"*. ADR 0009 replaced that CPU with a 1513F-1 PN
  running one, and that is the fact the row rested on.
- **The exception is bounded to these six read-only mirrors.** No safety command, no e-stop input,
  no STO **input** and no safety reset node is added, so the rest of the row stands word for word
  (§11.7). **`TorqueOffDemand` is not an STO node in that row's sense**: nothing writes it, nothing
  commands through it, and it carries the F-program's *statement* that stage two of SS1 is in force —
  which a labelled process-side stand-in then models at the plant (**SD2**, **SD9**). A node a client
  could write to remove torque would be the thing this row refuses, and no such node exists.

**One nearby sentence that survives, and why it is worth saying so.** §9.6 ends with *"`Safety/EStopActive`
in §4 remains the only informational mirror of SF-01"*. That stays true: §4 mirrors **SF-01**, the
fixed cell's e-stop chain, and `Forklift/Safety/EStopDemand` mirrors the twin's instantiation of
**the logic of** SF-01 — a different latch, on a different machine, in a different F-program
(`TWIN-DEMO-MAP.md` §5's say/never-say discipline is exactly this distinction). The sentence is
scope-dependent rather than wrong, which is the category LESSONS 2026-07-27 says to sweep for; it is
listed for a cross-reference in item 1 and needs no correction.

**§10 is not edited by this brief**, so the pointer that would make the seam visible from the §10
side was requested rather than taken, and has since landed (item 1 below, closed 2026-08-06).
Counts stay set-scoped in the sense §9.8 fixes:
**§11 is exactly 6 nodes** — 4 as built 2026-08-06 plus the SLS / SS1 pair this round rules — §10.3's
"18 nodes" remains a true statement about the M4 node set, and the `DemoCell` interface — 37 when this
section was written — now carries
15 (§9) + 18 (§10) + **6** (§11) + 9 (§12) + 1 (§13) = **49**, with a client browsing
from `Objects` seeing more than any of those numbers. **The two new leaves are a design value until
they are read back out of the tool** (§11.5 step 6, open item 2): until then the controller in force
publishes four.

**What §11 does not close.** Nothing here closes M5 or any part of its criterion, and a node existing
is not an acceptance test passed (ADR 0009 D2.3, `plc/forklift-safety/SPEC.md` §1.2 N5). The M5
criterion's own mirror clause — *"the `Safety/` mirrors remain read-only"*, in a criterion item that
also requires the reactions to execute with the bridge stopped and the OPC UA session down
(`docs/roadmap.md` row M5, item (b)) — is a gate-proper statement about the safety layer, which
**ADR 0010 D2 and D7 land on this twin** rather than on the fixed cell, so the group the clause is
about is this one. **Whether it is satisfied as built is still decided at M5 and not here**, because
that item also requires the acceptance tests AT-01, AT-07 and AT-08 and the tool read-back of open
item 2 below, and neither is in this document's gift. The accurate statement remains *"M5's
cell-scope core is being built first"* — the opening wave of the preamble above (ADR 0009 D2.4, ADR
0010 D2). Nothing in §11 may be cited as M4 evidence either (D2.2): the M4 showcase names every
reaction as standard-program process logic, and these four nodes are no part of it.

| # | Open item | Owner |
|---|---|---|
| 1 | ~~**§10 needs three pointers to this section**~~ **CLOSED** — the three pointers landed by m5a-06b (the §10.11 row, §10.3's tree, §10.3's count), and §9.6's optional fourth carries its scope note; closure mark added by m5-54, the §11 edit the m5a-06b brief forbade | Closed 2026-08-06 |
| 2 | **Every value in this section is a design value until read back out of the tool** (§11.5 step 6): the folder, the **six** BrowseNames, the per-tag rights, the **six** start values, and the refused write with its status code. **Partially executed**: the first four and their refusal are the 2026-08-06 build's; the SLS / SS1 pair is `plc/forklift/TIA-FIX-PROCEDURE.md` chunks AD–AF, whose step 49 reads the leaf count back as six and whose step 59 repeats the refused write on a new leaf | Owner, at commissioning, recorded with its date as phase 0 recorded the M3 set (§9.10). **No gate criterion may rest on one before then** |
| 3 | Whether the per-tag *Writable* ✘ also governs the auto-published `DataBlocksGlobal` path is **expected, not verified** (§11.4). §9.8's open item to suppress DB-level exposure is the general form and is unchanged | Owner, at the same read-back; the access-control gate for the general case |
| 4 | ~~**The bridge reads exactly one mirror, and the original refusal stands for the other five.**~~ **CLOSED 2026-08-06 — the read slot is `bridge-design.md` §4.12** (m5-63), carrying **SD5** on its row as this item asked, with `SpeedMonitorDemand` given no slot (**SD1**) and the group declaring no inputs so the write allowlist gains zero keys (**MR1** by construction). The text below is the request as it was made. **The bridge reads exactly one mirror, and the original refusal stands for the other five.** The refusal's reason was the M5 criterion itself — the reactions must execute with the bridge stopped and the OPC UA session down, so evidence of an F-demand must not come from the client that has to be able to be dead — and **it is unchanged as an evidence rule**: the F-side instrument remains the watch table, which reads F-data directly and depends on no copy (**SD10**). What changed is that `TorqueOffDemand` has a **consumer at the plant**, and on a hardware-free plant the bridge is the only path to it. **Requested, not taken here** (`bridge-design.md` is another agent's file): one read slot on `Forklift/Safety/TorqueOffDemand` publishing `/forklift/safety/torque_off_demand` (`std_msgs/Bool`, no inversion), carrying **SD5** explicitly — **no silence rule, no synthesised value, no freshness window**, which is the deliberate opposite of §13.2 **W1**'s warning slot and must be written on the row so the asymmetry is not read as an omission. `SpeedMonitorDemand` gets **no slot at all** (**SD1**) | `bridge-design.md` §2.1 and §4.11, its own brief; the vehicle-side consumer already exists (`agv/`, m5-50) |
| 5 | `SafetyResetFault` has a **node** (§11.2). Whether it gets a **lamp** is `hmi/`'s decision; the HMI brief asks for three lamps and this section does not enlarge that ask | `hmi/`, its own brief |
| 6 | **`plc/forklift-safety/SPEC.md` §6.4 notes 1–3 and its §10 open item 4 are answered by this section** — the group is `Forklift/Safety/`, the leaf names are the F-side names unchanged, and the fourth flag gets a node. That document asks to be told, and it is outside this agent's write scope | Requested: one line in §6.4 and one in its §10 open item 4, pointing at `opcua-nodes.md` §11 |
| 7 | The copy statements themselves — one unconditional assignment per node, every cycle — are `plc/forklift/SPEC.md`'s. **This section is authoritative for the node names, the DB name and the per-tag rights**; `plc/forklift-safety/SPEC.md` §6 is authoritative for what the flags mean | The standard-side delta, its own brief |
| 8 | **ADR 0014 D4 seam (a) is enumerated as the envelope plus the mode down and the vehicle's report up. `TorqueOffDemand` is a third content item on that seam**, and it is admitted here because it is a **demand Bool and not a motion value** — D4's own sentence, *no motion value crosses seam (a)*, is satisfied (**SD7**) — and because `plc/forklift-safety/SPEC.md` §11.7, `docs/safety/SRS.md` SF-11 and ADR 0011 D5 already place the reaction at a labelled stand-in. **What no document yet records in one place is that a modelled safety reaction is stimulated across the process network because the plant has no wire to carry it.** This section states it (**SD9**, **SD10**) and asks the owner whether it should also be an ADR clarification; **it is not an invariant change and is not implemented as one** — invariant 1's chain, the F-runtime group and the client-write refusals are untouched | **Owner / `arch-docs`**, as a clarification round. Nothing waits on it |
| 9 | **`hmi/` inherits two more display candidates and one caption rule.** Whether either new node gets a lamp is `hmi/`'s (item 5's standing), but **SD8** binds any display that does take them: the two new latches are never merged with each other, with `ForkliftObstacleStopActive` or with `ForkliftProcessStopActive`, and a lamp that says *torque removed* is captioned as the stand-in it reads (**SD9**) | `hmi/`, its own brief |

## 12. The autonomy envelope, the drive mode and the operator's process stop (M5)

Added by **ADR 0011 D3** as refined by **ADR 0012 D1**. In autonomous mode the standard program
publishes, at its own cycle, an **autonomy envelope** of three elements — a **motion enable**, a
**speed ceiling** and a **fixed-equipment / station permit** — and the navigation control loop closes
**onboard the vehicle at its own rate**. This section mints the nodes that carry the envelope, the
drive mode that selects which control law is in force, the operator's process-stop request, and the
two values the vehicle's own control layer reports back.

**Nine nodes, in four new subfolders of `Forklift/`.** As in §9, §10 and §11, **this section defines
nodes only**. Every threshold, delay, latch, arbitration rule and formation term named below is
standard-program content owned by `plc/forklift/SPEC.md`, or vehicle-layer content owned by `agv/`;
where a value or a behaviour is named here it is an **interface expectation** for that specification,
marked as such, and never logic defined in this document.

**What is new in kind, and it is new.** Through §11 every value on this server was either formed by
the PLC or measured by the plant. This section adds the first values that are neither: a
**permission the vehicle's own control layer consumes** while forming its own commands, and a
**report that layer makes about its own gating**. That is what ADR 0011 D3 buys, and it is why the
rules below are written before the tables.

**Three statements this section does not weaken.** Nothing here is a safety function, and no PL, SIL,
Category or PFH is claimed for any node in it (ADR 0008 D3, ADR 0011 D5). Nothing here closes M5 or
any part of its criterion; a node existing is not an acceptance test passed (§11's standing, ADR 0009
D2.3). And **nothing here presumes the m5-03 F-I/O verdict**: no node in this section is on the
F-input path whichever way that verdict falls, no node in this section is written by or read by the
F-runtime group, and **the safe scanner channel is not named here** — its name and its path wait on
m5-03 and are not coined in this document (§12.12).

**Where the six required attributes live, so a reader can check the set rather than hunt.** Every
node below carries a **BrowseName**, an **S7 and OPC UA data type**, a **unit and a range or
plausibility statement** where the type admits one, and a **start value with its cold-start reading**
— all four in its own group table, on its own row. **Access right, owner and readers** are in
§12.2's two tables, which cover all nine nodes. The start values are deliberately **not** collected
into a §10.9-style table of their own: a start value that lives in the row it belongs to travels with
that row when a later edit moves it, and a value written in two places goes stale in one of them.

### 12.1 Direction rules — three consumers, one server, and one thing this group is not

| Rule | Statement |
|---|---|
| Server/client | Unchanged. The PLC is the OPC UA server; the bridge and the HMI are its clients (invariant 4, §10.1). **The vehicle's control layer is not a client of this server and never becomes one** — it sees these values as ROS 2 topics the bridge republishes (§12.10), which is what keeps invariant 11's layer adjacency intact |
| What the HMI writes | Its §10.1 set **plus two**: `Forklift/Mode/HmiDriveModeRequest` and `Forklift/ProcessStop/HmiProcessStopRequest`. **Its every-cycle write set becomes eight** — the five requests of §10.4, `Link/HmiHeartbeat`, and these two. §10.8 **H1**'s *rule* governs all eight unchanged — every node this client writes, written every cycle, never on change, so a reverted DB is repaired by the next cycle — and only its **count** went stale, corrected when §12.13 item 2 landed |
| What the bridge writes | Its §10.1 set **plus two**: the two `Forklift/Vehicle/` nodes. It writes no `Mode/`, no `Envelope/` and no `ProcessStop/` node, on any path |
| The two clients' writable sets stay disjoint | Unchanged and still answerable from the BrowseName alone: the two new HMI-written nodes carry the `Hmi` prefix of §10.3, the two new bridge-written nodes do not, and no node in this section is writable by both |
| No actuator writes, from any client | Unchanged. Nothing in this section is an actuator output, and the three `Forklift/Output/` setpoints of §10.6 are untouched — same nodes, same single assignment with its mandatory `ELSE` to `0.0`, same owner |
| **A permission is not a command** | **This is the load-bearing sentence of the section.** Every `Forklift/Envelope/` node is a **bound or a permission** the vehicle's control layer consumes while forming its own commands. **The envelope can prevent motion; it cannot cause it.** No node here instructs the vehicle to move, and a consumer that read `ForkliftMotionEnable` `TRUE` as an instruction to move would be wrong. This is also what keeps invariant 6 out of reach later: when a fleet manager exists it is a **reader** of these nodes at most, and a permission it cannot write is not a channel through which it could command an actuator |
| Single owner | Every node below has exactly one writer, listed per tag in §12.2 (invariant 10). No consumer recomputes a value another layer owns — in particular the PLC never re-derives the mode from the vehicle's report (§12.3 **M4**), and the vehicle never re-derives the mode from the envelope (**M5**) |
| One heartbeat per party, and they are not merged | `DemoCell/Link/BridgeHeartbeat` / `BridgeLinkOk` remains the single answer to *"is the bridge alive?"* (§10.1, §10.11). `Forklift/Vehicle/ForkliftVehicleHeartbeat` is **not** a second bridge heartbeat and **not** a second client: it counts the **vehicle control layer's** own cycles and is carried to the server by the bridge like any other plant input. The two answer different questions and no verdict merges them (§12.6) |
| Not a safety path | Every node here is process data. The envelope, the mode, the operator's process stop and the vehicle's report implement **no** SRS function — not SF-02, not SF-03, not SF-04, not SF-07, not SF-09 — and no SIL or PL is claimed for any of them (ADR 0008 D3, ADR 0011 D5). Neither "emergency" nor "protective" appears in any tag, node or topic **name** in this section, exactly as §9.6 and §10.1 require of process nodes. Loss of any link here is a degraded mode, not a safety event (invariant 2) |
| Timing class | Best effort, and **that is only admissible because nothing here is a per-sample value** (§12.4 **E1**). Every deadline the cell's behaviour depends on is a PLC timer in the PLC's own time base or a vehicle-side timer in the vehicle's; no timing-critical loop is closed across this interface (invariant 9, ADR 0011 D3) |

### 12.2 Folder layout, data blocks and per-tag access rights

```
DemoCell/                          the commissioned server interface, ns http://DemoCell
  Input/ Output/ Status/ Link/     the M3 demonstration cell (§9), unchanged
  Forklift/
    Hmi/ Input/ Output/            the M4 forklift commissioning cell (§10), unchanged
    Status/ Link/
    Safety/                        the F-safety mirrors (§11), unchanged
    Mode/                          which control law is asked for, and which is in force  (this section)
    Envelope/                      the three elements of the autonomy envelope             (this section)
    Vehicle/                       what the vehicle's own control layer reports back       (this section)
    ProcessStop/                   the operator's process-stop request, and its latch      (this section)
```

**Four new global DBs, one per folder, and no existing DB gains a member.** This is §10.3's and
§11.3's rule applied a third time and for the same reason: adding members to `ForkliftHmi`,
`ForkliftStatus` or `ForkliftInput` moves the offsets of tags that the M4 watch tables, evidence and
recording depend on, and a download that leaves project and CPU inconsistent shows up as monitoring
errors on exactly the rows whose offsets moved (LESSONS 2026-07-28). New DBs leave the M3, M4 and §11
groups byte-identical while this gate is built.

**The folder names carry their own disclaimers, deliberately.** `ProcessStop/` puts the word in every
browse path, every watch row and every screenshot, in the standing of §9.6's naming ruling and
§11.3's `Mirror`: the one node in this project most likely to be mistaken for an emergency stop is
the one whose full path says *process stop* three folders deep. `Vehicle/` is named for the **source**
of its two values — the vehicle's own control layer — and it is **not** a vehicle-state group: it
carries exactly two values, both about gating, and §11's warning stands unchanged, that `Forklift/`
is the commissioning cell's subtree and no folder name in it asserts an onboard layer that document
does not describe.

| DB | Folder | Contents | *Accessible from HMI/OPC UA* | *Writable from HMI/OPC UA* |
|---|---|---|---|---|
| `ForkliftMode` | `Forklift/Mode/` | 2 mode tags | ✔ | per tag |
| `ForkliftEnvelope` | `Forklift/Envelope/` | 3 envelope tags | ✔ | **✘ (all three)** |
| `ForkliftVehicle` | `Forklift/Vehicle/` | 2 vehicle-report tags | ✔ | **✔ (both)** |
| `ForkliftProcessStop` | `Forklift/ProcessStop/` | 2 tags | ✔ | per tag |

> The *Writable* column is again where §12.1's direction rules are **enforced by the server rather
> than by convention** (§10.3): with `Forklift/Envelope/*` not writable, a defect in either client
> that tried to write the envelope is refused by the CPU, and the "a permission is not a command"
> rule survives a broken client. **Per-*client* scoping remains policy**, unchanged and no wider than
> §10.3 records: the commissioned CPU runs with access control disabled and security `None` (§9.10),
> so "only the HMI writes the `Hmi…` tags and only the bridge writes the `Vehicle/` tags" is enforced
> by each client's own allowlist and not by the server. Closing that is the access-control work §9.8
> already carries.

Per-tag ownership and readers. **Exactly one writer per node** (invariant 10); "readers" lists every
consumer this contract admits. **Value owner and node writer are different roles for the two
`Vehicle/` rows**, as they are for the §11 mirrors: the vehicle's control layer owns the value, the
bridge writes the node.

| Node (`Forklift/…`) | Writer (single owner) | Value owner, where different | Readers |
|---|---|---|---|
| `Mode/HmiDriveModeRequest` | HMI | — | PLC |
| `Mode/ForkliftDriveModeActive` | PLC | — | HMI (display), **vehicle control layer** (via the bridge), bridge (logging) |
| `Envelope/ForkliftMotionEnable` | PLC | — | **vehicle control layer** (via the bridge), HMI (display), bridge (logging) |
| `Envelope/ForkliftSpeedCeiling` | PLC | — | as above |
| `Envelope/ForkliftEquipmentPermit` | PLC | — | as above |
| `Vehicle/ForkliftVehicleModeApplied` | bridge | the vehicle's control layer (`agv/`, m5-11) | PLC, HMI (display) |
| `Vehicle/ForkliftVehicleHeartbeat` | bridge | the vehicle's control layer | PLC, HMI (display) |
| `ProcessStop/HmiProcessStopRequest` | HMI | — | PLC |
| `ProcessStop/ForkliftProcessStopActive` | PLC | — | HMI (display), bridge (logging) |

**9 nodes** — 2 in `Mode/`, 3 in `Envelope/`, 2 in `Vehicle/`, 2 in `ProcessStop/`. The count is
**set-scoped** in the sense §9.8 fixes: §10.3's "18 nodes" remains a true statement about the M4 node
set and §11's "exactly 6" about the mirror set, and the `DemoCell` interface now carries
15 (§9) + 18 (§10) + **6** (§11) + 9 (§12) + 1 (§13) = **49**, still fewer than a client browsing from
`Objects` sees. §10.3's and §11.8's totals were re-derived to the same arithmetic when the §12.13
pointer rows landed (m5-54) — a total quoted in three places goes stale in two of them, which is why
all three now carry the full sum rather than a partial one.

### 12.3 `Forklift/Mode/` — which control law is asked for, and which is in force

**One encoding, defined once, re-encoded nowhere.** All three mode-valued nodes in this document —
the request here, the verdict here, and the vehicle's report in §12.6 — use it unchanged, so the
three are directly comparable and a disagreement is a comparison rather than a translation.

| Value | Name | Meaning |
|---|---|---|
| `0` | **None** | No mode. The non-permissive value: **neither teleoperated nor autonomous motion is granted while the mode in force is `None`**, and "not yet told" is `None`, never a mode |
| `1` | **Teleop** | The mode M4 demonstrated: the PLC forms every motion setpoint from the operator's requests (§10.6) and the vehicle applies them |
| `2` | **Autonomous** | The mode ADR 0011 D3 rules: the vehicle's own control layer forms the commands and the PLC publishes the envelope that bounds them |

No other value is defined. A value outside `{0, 1, 2}` is a **broken writer, not a mode to clamp**:
interface expectation for both consumers, test affirmatively — `valid := (m = 0) OR (m = 1) OR (m = 2)`
— and take the fault in the `ELSE`, in the form §10.4 fixes for the Reals.

| BrowseName | S7 type | OPC UA type | Unit | Range / plausibility | Start value | Meaning |
|---|---|---|---|---|---|---|
| `HmiDriveModeRequest` | UInt | UInt16 | — (enumeration) | exactly `{0, 1, 2}` above; anything else is a fault | **`0` = None** | The mode the **operator has selected on the HMI**. A **level**, not an edge, and not a command: it expresses "this is what the operator has selected", is written every HMI cycle (§10.8 H1), and survives a PLC scan. The PLC forms any edge it needs. **Cold start `0` is the non-permissive value and is what makes a cold start safe on this row**: a machine that booted into `Autonomous` would be offering a control law nobody selected, and a machine that booted into `Teleop` would be offering an enable path nobody asked for |
| `ForkliftDriveModeActive` | UInt | UInt16 | — (enumeration) | exactly `{0, 1, 2}` above | **`0` = None** | **The authoritative answer to "what mode is the machine in".** The PLC's verdict, formed from `HmiDriveModeRequest`, the link verdicts and the standing latches; the arbitration itself is `plc/forklift/SPEC.md`'s. Read by the HMI for its display **and by the vehicle's control layer** through the bridge — one node, two consumers, one answer. **Cold start `0` is the non-permissive value**: before the standard program has decided anything, the machine is in no mode, and no motion is granted in either path |

**Two beliefs about the mode are made impossible, and here is how.** Interface expectations, binding
on `hmi/`, on `agv/` and on `plc/forklift/SPEC.md` respectively:

| # | Rule |
|---|---|
| **M1** | **There is exactly one authoritative answer**, `ForkliftDriveModeActive`, with the PLC as its single owner (invariant 10). "What mode is the machine in" is answered by reading that node and by nothing else |
| **M2** | **A consumer displays or acts on the node it read, never on what it sent.** The HMI must not render `HmiDriveModeRequest` as the machine's mode: showing your own request back as the machine's state is the defect this rule exists to prevent, and it is invisible precisely when the PLC has refused the request |
| **M3** | **Every consumer's copy is qualified by that consumer's own link verdict.** For the HMI that is `HmiLinkOk`; for the vehicle it is the freshness of the ROS side (**E5**). When the verdict is false the mode reads **unknown**, and unknown renders as unknown — never as the last value silently, and never as `Teleop` on the ground that it is the more restrictive of the two defined modes. This is §11.6's rule one layer up: *not yet written is not clear* |
| **M4** | **The vehicle's report is a different datum, never a second answer** (§12.6). The PLC does not derive its verdict from it, and no consumer chooses between the two: a disagreement is a **fault to display**, not a value to pick |
| **M5** | **No consumer infers the mode from anything else** — not from the envelope, not from `ForkliftTeleopActive`, not from a setpoint being non-zero. An envelope with `ForkliftMotionEnable` `FALSE` is not "teleop"; it is an autonomy envelope that is currently withholding permission, and the two are distinguishable only by reading the mode |
| **M6** | **The two modes are mutually exclusive, and that is checkable.** `ForkliftTeleopActive` (§10.7) may be `TRUE` only while the mode in force is `Teleop`; `ForkliftMotionEnable` may be `TRUE` only while it is `Autonomous`. **The two are never `TRUE` at the same time**, in any state, including during a transition — one falls before the other rises |

**The affirmative action that enters autonomous motion, and the conflation this section carries.**
CLAUDE.md §9 requires that a machine never resume by itself: entering motion takes an operator
action, not a permissive returning. In teleop that action is the rising edge of `HmiTeleopRequest`
(§10.7). **In autonomous mode this section defines no separate enable request**, so the affirmative
action is the operator's **selection of `Autonomous` on `HmiDriveModeRequest`** — a transition into
`2`, which the PLC treats as the edge, exactly as it treats the teleop enable's rising edge. The
operator's sequence after any latch is therefore the same shape as §10.7's: *leave the mode, press
reset, select the mode again.* The conflation is written out rather than left to be discovered, and
the missing device is **requested rather than invented** (LESSONS 2026-07-27): §12.13 item 5 asks for
one enable/start request that serves both modes, and ties it to §10.12 item 7's `HmiStartRequest`,
because **minting two enables for two modes would be the wrong answer to that request**.

### 12.4 `Forklift/Envelope/` — the three elements, and the rules that keep them from becoming a velocity channel

**This folder holds exactly the three elements ADR 0011 D3 composed and ADR 0012 D1 refined, and
nothing else.** A fourth node in this folder would be a change to the envelope's composition, which
is an ADR's to make and not this document's — which is why the drive mode, which a reader might
reasonably have expected here, is in `Mode/` instead: the mode selects **which control law is in
force**, the envelope **bounds motion within one of them**, and keeping them in different folders
makes any later widening of the envelope a visible act.

| # | Rule |
|---|---|
| **E1** | **Low rate, and not a per-sample value.** The envelope is published at the PLC's own cycle and read by the bridge in the same 20 Hz poll as every other output (§10.10) — but **no consumer may depend on a particular read rate**. The test, and it is checkable per node: *a consumer reading this group at 2 Hz and one reading it at 20 Hz must behave identically apart from latency.* **Any node for which that is false does not belong in this group**, and a proposal to add one is a proposal to route the control loop through the PLC, which invariant 9 and ADR 0011 D3 forbid |
| **E2** | **A ceiling is not a setpoint, and its sign convention says so as well as its name.** `ForkliftSpeedCeiling` bounds the **magnitude** of speed in either direction and therefore **carries no sign**; the §10.6 setpoints are **signed**, and a negative one means reverse. A quantity that cannot express a direction cannot be a demand, so the distinction survives a reader who looks only at the value. `0.0` on a setpoint means *stop*; `0.0` here means *no motion is permitted*, and the two arrive at the same standstill by different sentences. The type is `Real` because that is the only floating type this model carries; **negative is not a reverse ceiling, it is a fault** (the row below) |
| **E3** | **The naming reserves `Ref` for setpoints.** No node in this section ends in `Ref` or `Cmd`. Those suffixes belong to §10.6's three, which are the only nodes in this model that command an actuator, and the reservation is what lets a reader tell a bound from a demand in an export, a watch table or a screenshot |
| **E4** | **The loop is not closed across this interface.** The vehicle's controller runs onboard at its own rate against its own odometry (ADR 0011 D3), and its velocity smoother runs closed-loop against **measured** odometry rather than its own last command — a smoother integrating from its own output fights an external gate and ramps from a value the wheels never had (ADR 0011 D3, recorded there as an implementation consequence and repeated here because it is the consumer of these nodes that must obey it) |
| **E5** | **A stale envelope is no envelope.** The vehicle's control layer applies the last envelope it holds only while that envelope is **fresh**; when it is not, the vehicle takes its own controlled stop (invariant 2's degraded mode). The freshness window is a **named constant in the vehicle layer, derived from the rate the bridge republishes at, and it is its own constant — never shared with `HMI_STALE_TIME`, `HEARTBEAT_STALE_TIME` or `UI_POLL_STALE_TIME`** (§10.8 P4's principle, one layer further out). Its value is `agv/`'s and is not set here |
| **E6** | **A permission cannot start motion** (§12.1). Nothing in this folder commands the vehicle; the enable withholds or allows, the ceiling bounds, the permit states a readiness |
| **E7** | **Nothing here carries order, route, traffic or zone data** — no goal, no waypoint, no pose, no reservation, no identifier of any of them (invariants 3, 5; §12.12) |
| **E8** | **No claim of safety.** The ceiling is a **process** bound formed by the standard program. Whether the F-layer independently monitors a safe speed is `plc/forklift-safety/SPEC.md`'s subject, a different datum with a different owner in a different program, and **no node in this folder carries it, mirrors it or may be cited as it** (ADR 0011 D5) |

| BrowseName | S7 type | OPC UA type | Unit | Range / plausibility | Start value | Meaning |
|---|---|---|---|---|---|---|
| `ForkliftMotionEnable` | Bool | Boolean | — | — | **`FALSE`** | The PLC's **permission for autonomous motion**: `TRUE` only while the mode in force is `Autonomous`, no latch stands, both link verdicts are `TRUE` and the standard program's own permissives hold. **It permits; it never commands** (**E6**). `FALSE` whenever the mode in force is not `Autonomous`, so the node is meaningful in every mode rather than undefined in two of them (**M6**). **Cold start `FALSE` is the non-permissive value**: before the standard program has run a scan, nothing is permitted |
| `ForkliftSpeedCeiling` | Real | Float | m/s | `0.00` … `TRACTION_SPEED_MAX` (`1.00` m/s today, `plc/forklift/SPEC.md` §3.3). **Unsigned** (**E2**). A value outside the range is a broken supervisor and is non-permissive to the consumer, never a bound to clamp | **`0.0`** | The **upper bound on the magnitude of the vehicle's ground speed** while it drives itself. **It is not a speed setpoint, not a demand and not a target**: a ceiling of `0.80` does not ask for `0.80` m/s, and a vehicle that drove at its ceiling would be one whose own controller happened to want that speed. The vehicle's controller may command anything at or below it; the PLC never learns what was commanded and does not need to. **The ceiling relation of §10.12 item 4 stays live**: the ceiling can never exceed `TRACTION_SPEED_MAX`, and raising that cap re-derives `ForkliftLinearSpeed`'s plausibility window in §10.5 **first**. **Cold start `0.0` is the non-permissive value**: zero permits no motion at all |
| `ForkliftEquipmentPermit` | Bool | Boolean | — | — | **`FALSE`** | The **fixed-equipment / station permit** of ADR 0012 D1: the PLC's statement that **the equipment it owns is ready for the vehicle to act on it**. It answers *"is the equipment I own ready for you to act on it?"* and **never** *"may you be here?"* — the second question is the fleet manager's zone reservation, a different datum with a different owner, and §12.5 rules the separation. **Cold start `FALSE` is the non-permissive value**: the PLC has stated no readiness, and an unstated readiness is not a granted one |

**Cadence, following §9.2's conventions.** All three are read by the bridge in its 20 Hz output poll
and republished each cycle a value was read, exactly as the three §10.6 setpoints are — the same
transport, deliberately, because a second cadence for a second output group would be a second timing
story for one process. **The 20 Hz is the bridge's, not the envelope's**: **E1** is what makes that
rate an implementation detail rather than a contract, and a run that polled at 2 Hz would be slower,
not wrong.

### 12.5 The station permit is not a zone permit, and at M6 both will exist

ADR 0012 D1 replaced the word deliberately, and the replacement is the reason this subsection exists
rather than a sentence in the table above. **Zone reservation and traffic belong to the fleet manager
under invariant 5**, and one datum has one owner under invariant 10. At M6 a vehicle's motion is
bounded by **both** of these, and they are **different data with different owners**:

| Datum | Owner | Where it lives | The question it answers |
|---|---|---|---|
| **Fixed-equipment / station permit** | **PLC standard program** | `Forklift/Envelope/ForkliftEquipmentPermit` — this node | *Is the equipment I own ready for you to act on it?* — the door is open, the conveyor is ready, the charging bay is clear, the station handshake is satisfied |
| **Zone reservation** | **Fleet manager** | the fleet layer, over VDA 5050 / MQTT. **It reaches no node on this server, at any gate** | *May you be here?* |

| # | Rule |
|---|---|
| **Z1** | **No document, node name, message field, caption, lamp or spoken line may conflate them**, and **neither may be named with the other's word** (ADR 0012 D1). This is §11.4 **MR7**'s discipline applied to the pair most likely to be merged at M6, and for the same reason: the merge would sound plausible |
| **Z2** | **The word "zone" appears in no name in this folder, and that is not a stylistic preference.** This project already spends the word three times, on three different things: `Forklift/Safety/ZoneStopDemand` (the F-side marked-zone demand, §11.2), `Forklift/Input/ForkliftObstacleInStopZone` (the lidar's forward stop field, §10.5), and the fleet manager's zone reservation at M6. **A fourth use would make the word meaningless in exactly the document where a reader goes to find out what a name means** |
| **Z3** | **The permit's granularity is one Bool per vehicle, not one per station**, and it stays that way when the stations arrive. The PLC knows which equipment is engaged with this vehicle from **its own station handshake** (`handshake-tables.md`, invariant 5's second sentence), never from an order, a route or a destination, which are fleet data the PLC does not hold (§8, invariant 5). A per-station node set is the **station handshake's** own group and not an enlargement of the envelope (§12.13 item 6) |
| **Z4** | **At M5 the permit's term set is empty, and that is stated rather than hidden.** The twin's arena carries no door, conveyor or charger in the vehicle's path, so at M5 the permit is the standard program's statement that **no equipment it owns is withholding readiness**. It is still not a literal: interface expectation for `plc/forklift/SPEC.md`, the node is **assigned from the equipment terms in force**, an empty conjunction today, and it gains terms at M6 without a node, a name or a consumer changing. **Its cold start `FALSE` and the qualification rule of §12.8 are what the node is worth at M5** — a permit that has not been stated is not a permit granted |

### 12.6 `Forklift/Vehicle/` — what the vehicle's control layer reports back

The PLC forms the envelope; **it does not enforce it**. Enforcement is the vehicle's envelope gate
node (`agv/`, m5-11), which is where the commands are formed and gated. The honest one-line version
of ADR 0011 D3, stated here because this is the document that says who consumes what: **the PLC owns
the envelope, the vehicle's gate node enforces it in process, and the vehicle's own onboard safety
layer is a separate chain that owes nothing to either.** A supervisor that published a bound and
received nothing back would be making a claim it could not check, so these two nodes are the check.

| BrowseName | S7 type | OPC UA type | Unit | Range / plausibility | Start value | Meaning |
|---|---|---|---|---|---|---|
| `ForkliftVehicleModeApplied` | UInt | UInt16 | — (enumeration) | the §12.3 encoding, exactly `{0, 1, 2}`; anything else is a fault | **`0` = None** | **The mode the vehicle's control layer is applying right now** — a readback of a command, in the standing of a valve's position feedback beside its command. It is **not** a second answer to "what mode is the machine in" (**M1**, **M4**): that answer is `ForkliftDriveModeActive` and this node is what the vehicle says it is doing about it. A disagreement that persists is a **fault**; how long is "persists", and whether the reaction is a display or a latch, is `plc/forklift/SPEC.md`'s decision under its own named constant, not this document's. **Cold start `0` is the non-permissive value**: the vehicle has reported nothing, and "not yet reported" is not "agrees" |
| `ForkliftVehicleHeartbeat` | UInt | UInt16 | — | `0` … `65535`, wraps | **`0`** | Counter incremented by the vehicle's control layer once per its own cycle. Its only meaning is **"the vehicle's control layer completed a cycle recently"**; it carries no process information. It exists because `BridgeLinkOk` proves the **bridge** is alive and proves nothing about the layer behind it — a frozen gate node under a live bridge is case D of `bridge-design.md` §7.3 one level further out, and with the loop onboard that failure now has a motion consequence rather than only a display one. **Cold start `0` is meaningless until it changes**, which is the point: **V2** is what gives it meaning |

**Semantics, interface expectation for the PLC specification.** These are §10.8's P-rules applied to
a third watched party, and they are stated in full rather than by reference because a rule cited
across a document is a rule that gets half-applied:

| # | Rule |
|---|---|
| **V1** | Test `ForkliftVehicleHeartbeat <> LastVehicleHeartbeat` — **inequality only**. Never subtract, never test for `+1`, never assume monotonic ordering across the wrap or across a restart of the vehicle layer |
| **V2** | The verdict is `SeenAlive AND NOT StaleTimer.Q`, with `SeenAlive` a non-retain latch starting `FALSE` and set by the first observed change. **The verdict is `FALSE` from the first scan and stays `FALSE` until the counter has actually moved**: "not yet proven stale" is not "alive", and every guard riding on it inherits that boot polarity (LESSONS 2026-07-28) |
| **V3** | The stale window is **its own named constant**, never shared with `HMI_STALE_TIME` or `HEARTBEAT_STALE_TIME` (§10.8 **P4**). Three parties are now watched across three transports at three rates, and retuning one must not silently retune another. Its value is `plc/forklift/SPEC.md`'s |
| **V4** | **The verdict is not merged with `BridgeLinkOk`.** They answer different questions — *is the transport alive* and *is the layer behind it running* — and a single "vehicle OK" flag would be the computed aggregate this project refuses everywhere else (§11.7, `handshake-tables.md` §6). What the PLC does when the vehicle's verdict is `FALSE` — withdraw the envelope, latch, or both — is `plc/forklift/SPEC.md`'s, and this document requires only that the envelope it publishes while the vehicle is not answering is the non-permissive one |

**What these two nodes do not make true.** They let the PLC **notice** that its envelope is not being
applied; they do not let it **enforce** the envelope, and no node in this model does. The backstops
for a gate node that has stopped gating live in other layers — the vehicle's own onboard safety
chain, and whatever the F-side specifies (`plc/forklift-safety/SPEC.md`, m5-15) — and **this section
neither claims nor describes them**.

Cadence: both are written by the bridge as ordinary plant inputs, the counter cyclically at the
bridge's 20 Hz cycle and the mode on change plus a full refresh on every (re)connect and after any
detected server restart (§10.5's conventions, unchanged).

### 12.7 `Forklift/ProcessStop/` — the operator's process stop, its latch and its monitored reset

| BrowseName | S7 type | OPC UA type | Unit | Range / plausibility | Start value | Meaning |
|---|---|---|---|---|---|---|
| `HmiProcessStopRequest` | Bool | Boolean | — | — | **`TRUE`** | The operator has asked for a **process stop**. A **level** carrying the operator's action, written every HMI cycle (§10.8 H1); **the PLC latches on it**, and no client clears a latch by writing a node. **`TRUE` is the non-permissive state** — the polarity note below. **Cold start `TRUE` is the non-permissive value**: before any client has connected, the server must not be asserting that nobody is asking the machine to stop |
| `ForkliftProcessStopActive` | Bool | Boolean | — | — | **`TRUE`** | A **latched process stop**, raised by `HmiProcessStopRequest` and cleared **only** by the monitored reset below. Its own node with its own cause: the lidar latch remains `ForkliftObstacleStopActive` (§10.7), and **the two are never merged into an aggregate "stopped" flag** — one node answers one question (invariant 10, §11.7's refusal of computed aggregates). **Cold start `TRUE` is the non-permissive value**, in §11.6's rule: *not yet written is not clear*, and the scan before the standard program's first assignment must not read as a machine free to move |

**What this is NOT — one sentence, and it is the point of the folder name.** **The operator's process
stop is not a safety function, not an emergency stop and not a protective stop; it does not reach the
F-layer, it cannot create, prevent or clear an F-latch, and it carries no SIL, PL or Category** —
invariant 1 (safety never traverses the network), ADR 0010 D6(b) (the HMI's emergency button is read
as a process-stop command plus a display of F-layer state, and anything more is an invariant change
needing its own ADR), and §11.4 **MR2**/**MR3**, which hold unchanged for this node as for every other
client write on this server.

**The display half of ADR 0010 D6(b) needs no node from this section.** It is the read-only mirrors of
`Forklift/Safety/` (§11) — four when this section was written, **six** since the SLS / SS1 pair was
ruled — which are read-only to every client and are **not touched, enlarged or renamed by this
section**. The operator's screen therefore shows two different things
side by side and must caption them as two: **what the operator can ask the standard program to do**,
and **what the F-layer has latched**. §11.4 **MR7**'s rule applies to this pairing too — no lamp, no
caption and no sentence may merge them.

**Latch and monitored reset, interface expectations for the PLC specification** (the constants, the
edge and the arming are program content, not defined here):

| # | Rule |
|---|---|
| **PS1** | The latch is **set while the request stands and stays set after it clears**. Releasing the button does not release the machine: this cell does not resume by itself (CLAUDE.md §9), exactly as §10.7's obstacle latch does not release when the field clears |
| **PS2** | The **only** reset input is `Forklift/Hmi/HmiResetRequest` (§10.4). **No second reset node is minted here** — one reset input, one owner (invariant 10) — and the PLC acts on its **rising edge**, under §10.8 **P6**'s per-link-session arming |
| **PS3** | The reset tests the **live world**, never the latches: **a latch is never a term in its own clearing condition** (LESSONS 2026-07-27). For this latch the live-world term is `HmiProcessStopRequest` reading `FALSE` — the operator has released the button — evaluated only while `HmiLinkOk` is `TRUE` |
| **PS4** | **Clearing the latch energizes nothing.** A reset returns the machine to the un-enabled state, and motion resumes only on a fresh affirmative operator action — the teleop enable's rising edge (§10.7) or the mode selection of §12.3, according to the mode |
| **PS5** | The existing `Forklift/Status/ForkliftResetRequired` (§10.7) **gains this cause and stays the single answer** to "is a monitored reset pending". No second reset-required node is created, and the three "reset required" values of §11.1 stay three, not four (§12.13 item 2) |
| **PS6** | While this latch stands, the envelope is the non-permissive one — `ForkliftMotionEnable` `FALSE` and `ForkliftSpeedCeiling` `0.0` — **and the §10.6 setpoints take `0.0` in their mandatory `ELSE`, unchanged**. The stop reaches the vehicle **through the envelope and through the setpoints**, and **through no stop topic of its own**: a second path to stop the vehicle would be a second owner of the reaction (§12.10) |

**Polarity, stated because a client-written stop inverts the convention of §9.3.** §9.3 names stop
*contacts* for their circuit state so that a dead signal reads stopped. There is no circuit here: this
is a button on a screen, written by a client over a network, and naming it `…CircuitClosed` would
assert a wiring property the device does not have. `TRUE` therefore means *stop requested*, the
failure direction, and fail-safety is carried by three independent things rather than by the name —
the start value is `TRUE` (this table); requests are **not attributable to an operator while
`HmiLinkOk` is `FALSE`** and none is evaluated then (§10.9's qualification rule); and a link loss
latches on its own account (§10.8 **P5**), so a stopped HMI produces the stop this button would have
asked for.

**The honest limitation, stated here rather than discovered in the recording.** This path is a
network path: it is subject to the HMI's cycle, the server's scan and the bridge's cadence, it is
**unavailable exactly when the link is down**, and no stopping time or distance is claimed for it.
That is not a defect of the design — it is *why* the safety functions are not on it (invariant 1),
and the F-layer's reactions do not depend on this node, on this client or on this network in any way,
whatever m5-03 settles about how the F-inputs are stimulated.

### 12.8 Start values, the qualification rule, and why every value in this section is the non-permissive one

Fail-safe pre-connection state belongs to the PLC as the DB start values (`bridge-design.md` §6.3,
§10.9, §11.6). **The values themselves are in the group tables above, one per row, each with its
cold-start reading** — the reason is stated in this section's preamble and it is a reason about
edits, not about layout.

**The rule this section applies, and it is checkable in one pass:** *every start value in §12 is the
non-permissive one.* For seven of the nine that happens to be the type's zero; for the two
`ProcessStop/` nodes it is `TRUE`, which is **not** the type's zero and is chosen deliberately, in the
standing of §10.9's `ForkliftObstacleInStopZone` and §11.6's three `TRUE` mirrors. A start value in
this section is never chosen because it is a type's default and never because it is convenient for a
test; where those two coincide it is a coincidence, and the row says why the value is safe rather
than what the type does.

> **The qualification rule, inherited unchanged from §10.9 and `plc/demo-cell/SPEC.md` §6.1.** While
> `BridgeLinkOk` is `FALSE`, the two `Forklift/Vehicle/` values are **not attributable to the vehicle's
> control layer**; while `HmiLinkOk` is `FALSE`, the two HMI-written requests in this section are
> **not attributable to an operator**. No verdict derived from either group is evaluated and no fault
> from either group is latched while its link verdict is `FALSE`. **Start values are the last line,
> not the first**: the boot polarity of §10.8 **P2** and of **V2** is what actually prevents a freshly
> started CPU from acting on them.

### 12.9 The two command paths, and which one is live

Two sources can reach the vehicle's actuators once autonomy exists: the PLC's three §10.6 setpoints,
republished by the bridge to `/forklift/cmd/*`, and the vehicle's own controller. **Exactly one may be
live at any moment, the selector is the mode in force, and the failure direction is standstill.**

| # | Rule |
|---|---|
| **C1** | **The envelope governs the autonomous path only.** The teleop path of §10.6 is unchanged and is not routed through the envelope: in `Teleop` the PLC still forms every motion setpoint, which is the M4 claim standing exactly where it was demonstrated (ADR 0011 D3's mode-scoped reading, ADR 0012 D1) |
| **C2** | **In any mode other than `Teleop`, `ForkliftTeleopActive` is `FALSE` and the three §10.6 setpoints are `0.0`** — produced by the existing mandatory `ELSE`, with no new branch, no second writer and no change to those three assignments (§10.6, §13's discipline in `plc/forklift/SPEC.md`) |
| **C3** | **The arbitration is the vehicle's, and it selects on the mode it read** (`ForkliftDriveModeActive`, **M1**). Which topic reaches the actuators, and how the change is made without a step in the command, is `agv/`'s design (m5-11) and is not specified here |
| **C4** | **A mis-selection fails to standstill.** Because C2 holds, a vehicle that wrongly believed itself in `Teleop` while the PLC was in `Autonomous` would be applying `0.0`; a vehicle that wrongly believed itself in `Autonomous` while the PLC was in `Teleop` would be applying its own controller's output under an envelope whose enable is `FALSE` and whose ceiling is `0.0` (**M6**). **Both errors stop the machine**, and both are visible as a mode disagreement (§12.6) |

### 12.10 ROS 2 topic map

One node per bridged signal, one signal per node, checked in both directions, in §10.10's shape. The
topic names are the vehicle layer's contract (`agv/forklift/README.md`); the BrowseNames here are the
authoritative PLC tag names.

| Node (`Forklift/…`) | Direction (PLC view) | ROS 2 topic | Msg type | Field | Conversion | Cadence |
|---|---|---|---|---|---|---|
| `Mode/ForkliftDriveModeActive` | PLC → vehicle | `/forklift/mode/in_force` | `std_msgs/UInt16` | `data` | none — the §12.3 encoding unchanged | polled 20 Hz, republished each cycle a value was read |
| `Envelope/ForkliftMotionEnable` | PLC → vehicle | `/forklift/envelope/motion_enable` | `std_msgs/Bool` | `data` | none | polled 20 Hz |
| `Envelope/ForkliftSpeedCeiling` | PLC → vehicle | `/forklift/envelope/speed_ceiling` | `std_msgs/Float64` | `data` | `Float → float64` widening, m/s unchanged | polled 20 Hz |
| `Envelope/ForkliftEquipmentPermit` | PLC → vehicle | `/forklift/envelope/equipment_permit` | `std_msgs/Bool` | `data` | none | polled 20 Hz |
| `Vehicle/ForkliftVehicleModeApplied` | vehicle → PLC | `/forklift/mode/applied` | `std_msgs/UInt16` | `data` | none | on change + refresh on (re)connect and after a detected server restart |
| `Vehicle/ForkliftVehicleHeartbeat` | vehicle → PLC | `/forklift/vehicle/heartbeat` | `std_msgs/UInt16` | `data` | none | cyclic 20 Hz, latest value |

**The envelope topics are deliberately not under `/forklift/cmd/`.** That namespace is the vehicle
layer's for **commands applied to joints** (§10.10, `agv/forklift/README.md`), and putting a bound or
a permission beside three setpoints would undo in the topic tree what **E2** and **E3** establish in
the node model. The two `Mode/` topics sit together for the same reason they are comparable: a
reader diffing `/forklift/mode/in_force` against `/forklift/mode/applied` is reading the disagreement
**M4** describes.

Nodes in this section that deliberately reach no topic:

| Node | Why |
|---|---|
| `Mode/HmiDriveModeRequest`, `ProcessStop/HmiProcessStopRequest` | HMI-written request nodes. The bridge **never reads or writes the HMI's nodes, in any configuration** — `bridge-design.md` §4.10's design rule, which this section extends to the two new request nodes without changing it |
| `ProcessStop/ForkliftProcessStopActive` | A PLC verdict. **The stop reaches the vehicle through the envelope, not through a stop topic** (**PS6**): a dedicated stop topic would be a second path to one reaction and a second thing to keep true |

**This section adds the first ROS-carried `UInt16` in the model.** `bridge-design.md` §2.1 **G4**
admits the value type (`Real`/`Bool`/`UInt16`), and `std_msgs/UInt16` needs no new dependency — but
the bridge has until now generated its only `UInt16` internally, as its own heartbeat, and has never
carried one from a topic. That is a change to the bridge's signal map and not to its contract, and it
was requested rather than taken here, and has since landed (§12.13 item 1, `bridge-design.md` §4.11).

### 12.11 TIA click path (the §10.2 / §11.5 pattern)

1. CPU → *OPC UA communication* → *Server interfaces* → open the **existing** `DemoCell` interface.
   Do **not** create a second interface and do **not** rename this one: the interface name **is** the
   namespace URI (ADR 0006, §10.2).
2. **Read the namespace URI back** and confirm it still reads `http://DemoCell`. Nothing is entered;
   the field is derived and not editable. Repeat this read-back after any *Change device*, which is
   known to delete server interfaces silently (LESSONS 2026-07-27).
3. Create the **four** new global DBs of §12.2 with their per-tag *Accessible* and *Writable*
   attributes as tabulated there. **New DBs, not new members of `ForkliftHmi`, `ForkliftStatus`,
   `ForkliftInput` or `ForkliftSafetyMirror`** (§12.2). **The DB names are written correctly the
   first time and are never renamed once the interface binds them** (LESSONS 2026-07-30).
4. In the interface, add the four folders `Mode`, `Envelope`, `Vehicle` and `ProcessStop` beside
   `Hmi`, `Input`, `Output`, `Status`, `Link` and `Safety` under `Forklift`, then drag each tag into
   its folder. **Rename nothing**: each leaf must remain the BrowseName of §12.3–§12.7 so this
   document, the TIA export and `plc/forklift/SPEC.md`'s tag list can be diffed three ways
   (CLAUDE.md §9).
5. Download, then confirm the block diff circles are solid green before testing, and **sweep the new
   browse names and DB statics for TIA's silent `_1` collision suffixes** — it appends them without
   asking, in DB statics and interface rows both, and a `…_1` browse name cuts a client with no error
   dialog (LESSONS 2026-07-30). No offset in any existing DB moves, because nothing was added to one;
   **check the M4 and §11 watch-table rows monitor without the error icon anyway**, since "should not
   have moved" is not a verification.
6. Browse with a client that is **not** the bridge; read all nine at their start values, then
   **attempt one write to a `Forklift/Envelope/` node and record the refusal with its status code and
   the date**. A read proves the nodes exist; only the refused write proves "a permission is not a
   command" is enforced by the server rather than by convention. Record both in the manner of §9.10.

> **Everything in this section is a design value until step 6 is executed.** The four folders, the
> nine BrowseNames, the per-tag rights, the start values and the refusal are what this document asks
> the tool for; they become facts when they are read back out of it (LESSONS 2026-07-27, ADR 0006).
> **No gate criterion may rest on one before then.**

### 12.12 Deliberately absent from this section

Each row means "no such node in the §12 node set", in the set-scoped sense §9.8 fixes.

| Not in this section | Why |
|---|---|
| A velocity, trajectory, curvature or per-sample motion value for autonomous mode | The navigation loop closes onboard at its own rate (ADR 0011 D3). Routing samples through ROS → OPC UA → PLC scan → back puts a timing-critical loop in Python (invariant 9) and makes a gate-zeroed command abort the goal through Nav2's progress checker. **E1** is the standing test for any proposal to add one |
| A goal, waypoint, route, destination or pose target | Order assignment is the fleet manager's (invariant 5), and a pose target on the PLC would make the standard program a navigator. **How an M5 goal is commanded before a fleet manager exists is not answered by a node here and must not become one** (§12.13 item 4) |
| A zone permit, zone reservation, traffic or right-of-way node | ADR 0012 D1 and invariant 5: the datum is the fleet manager's and reaches no node on this server. **Z1**–**Z3** |
| A per-station permit node set, or an array of any kind | **Z3**: the station handshake is its own group (`handshake-tables.md`) and arrays are not expressible in this node model (§10.10) |
| A second stop path — a stop topic, a stop command node, or a vehicle-facing stop bit | **PS6**: the operator's stop reaches the vehicle through the envelope and the setpoints. A second path is a second owner of one reaction |
| A second enable, a mode override, a force or an inhibit node | The mode is one datum with one owner (**M1**), and an override is a second writer wearing a different word |
| Any safety node — an SLS or safe-speed value, an F-reset, a mute, an acknowledge, an inhibit, or **any node for the safety scanner's channel** | Safety never traverses the network (invariant 1). §8's and §11.7's rows hold here word for word. **The safe scanner channel's name and path wait on m5-03 and are deliberately not coined in this document** |
| A safety mirror of any kind | §11 is the whole mirror set and this section adds nothing to it, renames nothing in it and enlarges nothing in it (§11.2, §11.7) |
| A second bridge heartbeat or bridge-link verdict | Unchanged (§10.1, §10.11). `ForkliftVehicleHeartbeat` watches a different party and **V4** forbids merging the verdicts |
| Map, pose, obstacle arrays, costmaps or any monitoring-plane data | Those reach the operator over the **read-only monitoring plane** (ADR 0011 D4), which has no write endpoint, no publisher and **never touches the PLC** (CLAUDE.md §3) |
| Nav2 internals — goal state, planner or controller status, recovery state, progress-checker output | Exposing another layer's logic state invites a consumer to act on it (§9.8, §10.11). The PLC needs the mode applied and a liveness counter, and gets exactly those |
| Timers, thresholds, constants or latch internals exposed for a client | Unchanged from §10.11 and §11.7 |
| A reaction time, latch age, demand timestamp or any Time value | A timestamp on a supervision node reads as a measured reaction time, and none is measured or claimed here (§11.7's row, same reason) |
| A fleet-facing node, or anything on a second server interface | The fleet-facing interface of §2.1 and ADR 0006 D3 belongs to a later gate, and **its name is a contract decision taken in a document, never in the tool** (§10.2) |

### 12.13 What this section changes elsewhere, and open items

**Four statements in §10 and §11 became narrower than the model they now sit beside; the pointer
rows below LANDED 2026-08-06 (m5-54)** and the table is kept as the record of what moved:

| Where | Statement before | What landed |
|---|---|---|
| §10.1, *What the HMI writes* | "**Only** the five `Forklift/Hmi/` request nodes and `Forklift/Link/HmiHeartbeat`" | "…plus `Forklift/Mode/HmiDriveModeRequest` and `Forklift/ProcessStop/HmiProcessStopRequest` (§12.1)" |
| §10.1, *What the bridge writes* | "its §9.1 writable set **plus** the four `Forklift/Input/` nodes, and nothing more" | "…plus the two `Forklift/Vehicle/` nodes (§12.1) and the §13 warning node" |
| §10.3 folder tree, §10.8 **H1** ("all six"), §10.5's "rewrites all six", §10.7 `ForkliftResetRequired` | five subfolders, six HMI writes, latches "above" | eleven subfolders (the four §12 folders and §13's `Warning/`); **eight** HMI writes, swept by subject to both "six" occurrences; and the process-stop latch of §12.7 named as a further cause (**PS5**) |
| §10.3 and §11.8, the interface total | "15 + 18 + 4 = **37**" | "+ 9 (§12) + 1 (§13) = **47**" in both places, and in §12.2 (§13 landed between the request and its execution, so the total moved once more in the same round rather than going stale a third time). **It has since moved again — to 49 — when §11 gained the SLS / SS1 pair (m5-60); the total in force is §11.8's, and this row records what m5-54 landed** |

| # | Open item | Owner |
|---|---|---|
| 1 | ~~**`bridge-design.md` must carry this signal group**~~ **CLOSED 2026-08-06 (m5-54)**: `bridge-design.md` §4.11 carries the group as a **third group** (the m5-44 reading, confirmed as the ruling), with the signal-map rows, QoS, the writable set gaining the two `Forklift/Vehicle/` nodes and the first topic-carried `UInt16`. Nothing in its §1.1 no-logic rule changed | Closed; the bridge's as-built group definition in `config.py` stands as ruled |
| 2 | ~~**The four pointer rows in the table above.**~~ **LANDED 2026-08-06 (m5-54)** — see the table | Closed |
| 3 | **Every value in this section is a design value until read back out of the tool** (§12.11 step 6). **Partially executed**: all nine nodes were read back from outside TIA on 2026-08-06 at their documented types, ten `Forklift/` subfolders, no `_1` suffix (m5-44 report, request 2), and the envelope write refusal was recorded (`BadNotWritable`, 2026-08-05 build session). The start-value read-back with its date remains the owner's | Owner, remaining half, recorded as phase 0 recorded the M3 set (§9.10) |
| 4 | **How an M5 navigation goal is commanded is unanswered and is not answered here.** A goal is not a node in this model and must not become one (invariant 5, §12.12). Whether it comes from a ROS-side tool, from HMI v2 over a path that is not the PLC, or from something else, is `agv/`'s and `hmi/`'s to settle — and any answer that routes a pose through the PLC is an invariant question, not an interface one | Owner decision, at m5-10 / m5-11 / m5-14 |
| 5 | **One enable/start request that serves both modes**, requested rather than invented (§12.3). Today `HmiTeleopRequest` is the teleop enable and the mode selection's transition into `Autonomous` is the autonomous one — two devices for one idea. §10.12 item 7 already asks for an `HmiStartRequest` for the M4 conflation; **one node should answer both asks**, and minting a second, autonomy-only enable would be the wrong answer | Owner decision; it moves a node count, a DB, a start value and the HMI's every-cycle write set together |
| 6 | **At M6 the station permit meets the station handshake.** `handshake-tables.md` owns the handshake sequencing; this node is the vehicle-facing summary of its outcome (**Z3**), and the two documents must be reconciled **before** the stations are built, not after. Nothing is owed until M6 | Interface agent, at M6 briefing |
| 7 | **The mode-disagreement reaction** — how long a disagreement between `ForkliftDriveModeActive` and `ForkliftVehicleModeApplied` must stand before it is a fault, and whether it latches — is `plc/forklift/SPEC.md`'s under its own named constant. This document specifies the datum and requires only that the reaction never be to adopt the vehicle's value (**M4**) | `plc/forklift/SPEC.md`, m5-16 |
| 8 | **The vehicle-side freshness window of E5** is `agv/`'s named constant, its own, never shared with the three of §10.8. It is not set here | `agv/`, m5-11 |

## 13. The warning-field verdict node (M5, m5-49/m5-54)

**Ruling: the node exists, exactly as `plc/forklift/SPEC.md` §14.16 requests it.**

| BrowseName | Full path | S7 type | OPC UA type | Unit | Start value | Meaning |
|---|---|---|---|---|---|---|
| `ForkliftWarningFieldOccupied` | `DemoCell/Forklift/Warning/ForkliftWarningFieldOccupied` | Bool | Boolean | — | **`TRUE`** | The warning-field verdict as the **standard program's process input**: `TRUE` = the warning field is occupied, **or the verdict is stale, silent or has never been heard** — every uncertainty resolves to occupied. `FALSE` only while a live carrier is relaying a live *clear*. **Cold start `TRUE` is the non-permissive value**: before the chain has ever spoken, the ceiling is reduced, never the reverse (§14.16's fail direction) |

| DB | Folder | Contents | *Accessible from HMI/OPC UA* | *Writable from HMI/OPC UA* |
|---|---|---|---|---|
| `ForkliftWarning` | `Forklift/Warning/` | 1 tag | ✔ | **✔** (the bridge writes it) |

| Node | Writer (single owner) | Value owner, where different | Readers |
|---|---|---|---|
| `Warning/ForkliftWarningFieldOccupied` | bridge | the field evaluation (`agv/forklift/scripts/field_evaluation.py`, m5-47) | PLC standard program (§14.16, the ceiling term), HMI (display, optional), bridge (logging) |

**A new subfolder and a new one-member DB, not a member anywhere else.** Not in `ForkliftInput` —
no existing DB gains a member, because offsets move and watch tables lie (§10.3, §11.3, §12.2,
LESSONS 2026-07-28), and §10's "18 nodes" stays set-scoped and true. Not in `Envelope/` — that
folder holds **exactly the three elements ADR 0011 D3 composed** and a fourth node there is a
change to the envelope's composition, which is an ADR's to make (§12.4); this node is an **input
to** the ceiling's formation, not an element of the envelope. `Warning/` follows §12.2's
folder-disclaimer practice: the word is in every browse path, watch row and screenshot, and the
leaf names a **field state**, never a function. Per-*client* scoping stays policy, exactly as for
the two `Vehicle/` tags (§12.2's caveat, unchanged).

### 13.1 Why §12.12's refusals do not catch this node — checked, not assumed

§12.12 refuses, by name, *"an SLS or safe-speed value"* and *"any node for the safety scanner's
channel"*, on §11.7's rule. A warning-field verdict is adjacent to both, so both tests are run:

| Refusal | The test, applied |
|---|---|
| Not an SLS or safe-speed node | The node carries **no speed** — no value, no limit, no setpoint. It is a Bool field state whose consumer forms a ceiling that remains a bound under **E2**/**E3** (single assignment, `MIN` of bounds, mandatory `ELSE`, §14.16). No name in this section contains `Safe`, `SLS`, `Speed`, `Ref` or `Cmd`. The SLS-pattern limit itself (`SPEED_LIMIT_MAX`) lives in the F-program and reaches no node (`plc/forklift-safety/SPEC.md` §11.3) |
| Not the safety scanner's channel | The safe channel rides the **stand-in writer path** — `"SafetyInputStandIn".WarningFieldClear`, fed by the `WARN` line on the field link (`plc/forklift-safety/SPEC.md` §11.2) — which enters below any client interface and **never touches this server**. This node is the **process copy** for the standard program's process ceiling. One producer, two consumers, two transports; neither consumer recomputes the verdict and neither path substitutes for the other (invariant 10) |
| §11 untouched | This node is not under `Forklift/Safety/`, mirrors no F-flag, feeds no F-network and carries no demand. §11.7's rows hold word for word, and **this section enlarges the §11 mirror set by nothing** — that set was 4 when this row was written and is **6** since §11 ruled the SLS / SS1 pair on its own account |
| **E1**, run affirmatively | The verdict is a **level** with the producer's own 2 s clear-hold (`warning_clear_hold_s`); a consumer at 2 Hz and one at 20 Hz behave identically apart from latency. It belongs on this seam |
| Invariant 1 | Process data end to end. Loss of any part of this path makes the cell **more** restrictive (the ceiling falls), never less, and no safety reaction depends on it — the F-side monitor demands the stop on its own measurement whichever way this path fails (§14.16) |

### 13.2 The stale rule across the seam — how a last-value store carries a silence-means-occupied topic

The producer publishes at the 20 Hz evaluation tick, not on transitions, **so that its absence is
visible**; its consumer must treat no-message-inside-the-window as **occupied** (m5-47, LESSONS
2026-08-04). An OPC UA node is the exact hazard that rule names: **the server holds the last
written value, so the seam is by construction a republishing layer.** The model preserves the
guarantee by making every layer that holds the value also **assert** it:

| # | Rule |
|---|---|
| **W1** | **The bridge slot converts silence into an explicit `TRUE`.** No message on `/forklift/warning_field/occupied` inside the bridge's own freshness window → the bridge **writes `TRUE` to the node and logs the transition**. The window is the bridge's own named constant, bounded below by the producer's 50 ms tick, never shared with any other window (§10.8 **P4**'s principle). A `FALSE` on this node is therefore never an implied clear: it is a fresh claim, written by a live bridge that heard a fresh *clear* inside its window |
| **W2** | **Bridge death is the consumer's term, not the slot's.** A dead bridge freezes the node — possibly at `FALSE`. The PLC therefore never reads the node bare: `#warningFieldOccupied := node OR NOT #bridgeLinkOk` (§14.16), and `BridgeLinkOk` boots `FALSE` and falls within `HEARTBEAT_STALE_TIME` of the heartbeat freezing (LESSONS 2026-07-28's boot polarity) |
| **W3** | **The start value covers the scans before the first write**, and a server restart's revert lands at `TRUE` — the fail direction. The bridge's §8.1 full rewrite after a detected restart applies to this slot as to every other |
| **W4** | Write cadence: **on change, plus the explicit `TRUE` of W1 on window expiry, plus a full refresh on (re)connect and after any detected server restart** (§10.5's conventions). No consumer may depend on a faster cadence (**E1**) |
| **W5** | **The honest residual, stated rather than hidden.** Between the bridge's death and `BridgeLinkOk` falling, a frozen `FALSE` can stand for at most the heartbeat stale window, and the ceiling stays up for that bounded time. The process chain accepts that residual; the independent backstop is the F-side monitor, whose own copy of the verdict rides the writer path with its own stale rule and its own onset budget, and which demands the stop if the slow-down fails for **any** reason — this seam included (`plc/forklift-safety/SPEC.md` §11.6, §14.16) |

**What the seam cannot do, said plainly: it cannot itself carry silence.** A held value is what an
OPC UA node *is*. The guarantee survives because silence is converted to an asserted `TRUE` at the
last layer that can observe it (W1), and because the one failure that freezes the node is detected
by a verdict formed outside it (W2). No layer between the producer and the ceiling term republishes
a clear it did not freshly hear.

### 13.3 Topic map, counts, and the tool

| Node (`Forklift/…`) | Direction (PLC view) | ROS 2 topic | Msg type | Field | Conversion | Cadence |
|---|---|---|---|---|---|---|
| `Warning/ForkliftWarningFieldOccupied` | plant → PLC | `/forklift/warning_field/occupied` | `std_msgs/Bool` | `data` | none — `TRUE` = occupied on both sides | per **W4** |

**§13 is exactly 1 node**, in the set-scoped sense §9.8 fixes; the `DemoCell` interface carries
15 (§9) + 18 (§10) + **6** (§11) + 9 (§12) + 1 (§13) = **49**.

The TIA click path is `plc/forklift/TIA-BUILD-PROCEDURE.md` chunk X (steps 338–360), which was
written against the requested shape this section grants unchanged: DB `ForkliftWarning`, folder
`Warning` beside the ten existing `Forklift/` subfolders, leaf = tag name, *Accessible* ✔,
*Writable* ✔. **Everything in this section is a design value until read back out of the tool**
(§12.11 step 6's discipline): the folder, the BrowseName, the rights and the start value become
facts when the owner reads them back, and no gate criterion may rest on one before then.

| # | Open item | Owner |
|---|---|---|
| 1 | ~~**The bridge slot itself** — the W1 window as a named constant, the silence-⇒-`TRUE` write, the transition log line~~ **CLOSED by m5-58, 2026-08-06**: built as ruled, recorded in `bridge/EVIDENCE_WARNING_SLOT.md`, and the observed configuration counts are now `bridge-design.md` §2.1's third row. The design row stays §4.11 row 23 | Closed 2026-08-06 |
| 2 | **Whether the HMI displays the node** — a lamp is `hmi/`'s decision; this section only admits it as a reader | `hmi/`, at its next brief |
| 3 | **Every value here is a design value until the owner's read-back**, recorded with its date | Owner, chunk X steps 349–360 |
