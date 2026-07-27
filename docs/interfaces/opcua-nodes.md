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
      Input/ Output/ Status/ Link/      the M3 nodes (§9.2)
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
| What the bridge writes | **Only** the `DemoCell/Input/` nodes (the PLC's input image) and `DemoCell/Link/BridgeHeartbeat`. Nothing else **on the `DemoCell` interface** is client-writable, and the bridge writes nothing outside that interface — in particular nothing under the auto-published `DataBlocksGlobal` folder, which is not part of this contract and, at the commissioned access settings (§9.10), is not write-protected by the server either. The restriction is the bridge's contract, honoured by the client; it is not enforced by the server today (§9.8 open item). |
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
| BridgeHeartbeat | UInt | UInt16 | R/W | cyclic | Bridge | Counter incremented by the bridge on every write cycle, wrapping at the type limit. Its only meaning is "the bridge wrote recently". It is the sole node outside `DemoCell/Input/` that the bridge may write |
| BridgeLinkOk | Bool | Boolean | R | on-change | PLC | The PLC's own verdict that the heartbeat is advancing. Published for the bridge's logging and the watch table |

**Reaction is PLC program content.** The staleness criterion for `BridgeHeartbeat`, the value of
`BridgeLinkOk`, and what the equipment does when the heartbeat stops are specified in
`plc/demo-cell/SPEC.md` and implemented in the standard program. No timer, threshold or reaction is
defined in this document, and none of it is in the bridge. Loss of the bridge is a degraded mode,
not a safety event (invariant 2), and nothing about it is a safety function.

### 9.8 Deliberately absent from DemoCell/

**Scope of every claim in this subsection: the `DemoCell` server interface, not the server's whole
address space.** The interface carries **exactly 15 nodes** — 7 in `Input/`, 1 in `Output/`, 5 in
`Status/`, 2 in `Link/`. It is *not* true that the server exposes only those 15 nodes: the S7-1500
auto-publishes every global data block under `Objects/DataBlocksGlobal` in its own namespace, so the
DBs backing these nodes are reachable by that second path as well, under their DB and member names
rather than the BrowseNames of §9.3–§9.7 (commissioning phase 0, §9.10).

| Consequence | Statement |
|---|---|
| Node-count checks are interface-scoped | "15 nodes" always means 15 nodes **under `DemoCell`**. A client browsing from `Objects` sees more than 15, and that is not a defect and not a naming error. The independent verification of §9.10, and the bridge's `session established, N nodes resolved` log, both count `DemoCell` nodes only |
| The interface is the contract; the DB path is not | Nothing in this project reads or writes a value through `DataBlocksGlobal`. Clients resolve BrowseName paths under `DemoCell` only (§9.1). A value reached by any other path is outside this contract, whatever it happens to be worth |
| "Deliberately absent" is an interface statement | Each row of the two tables below means "no such node on the `DemoCell` interface". A DB member visible via `DataBlocksGlobal` does not contradict them: it is the same storage under a different, uncontracted path, not a second node in this model |

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

| Not on the DemoCell interface | Why |
|---|---|
| A client-writable conveyor command node, or a run/stop bit alongside `ConveyorSpeedCommand` | The bridge may never write an actuator output (invariant 6). The cell accepts one signed velocity and nothing else; a separate run bit would duplicate information already carried by the sign and magnitude of the command, breaking single ownership (invariant 10) |
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
