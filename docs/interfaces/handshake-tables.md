# Handshake tables — station sequences and data ownership

Gate M1. Composes docs/interfaces/vda5050-subset.md (m1-01) and
docs/interfaces/opcua-nodes.md (m1-02) into step-by-step station sequences.
All node and field names below are taken verbatim from those two documents.

## 1. Rules that apply to every table

| Rule | Statement |
|---|---|
| Mediation | The AGV talks VDA 5050 (MQTT) to the fleet manager. The fleet manager talks OPC UA to the PLC. The PLC and the AGV never talk directly (invariant 11). Every sequence below interleaves the two interfaces through the fleet manager. |
| Request only | The fleet manager writes request bits, tokens, its heartbeat and its Seq counter — never actuator commands. The PLC forms outputs from its interlocks (invariants 5, 6). |
| Levels, not edges | All handshake bits are levels (CLAUDE.md section 9). `*Done` and `*Fault` are held by the PLC until the client withdraws the request. A restart re-reads levels; no step depends on having observed an edge. |
| Token protocol | Before setting a request bit the fleet manager writes a fresh unique token (`TransferToken` / `PassageToken` / `ChargeToken`). It trusts `*Ready`/`*Busy`/`*Done` only while the PLC echo (`*TokenAck`) equals its token. Mismatch = stale or crossed handshake: withdraw the request, resynchronize, start over with a new token. |
| Seq counters | `*SeqFleet` is incremented by the fleet manager each time it changes a request-side value; `*SeqPlc` by the PLC on each of its handshake transitions. After a reconnect, a counter that moved unexpectedly means the peer acted while the link was down: re-read all nodes and resynchronize before issuing anything. |
| Timeouts | The fleet manager supervises every step with the timeouts below (proposed defaults; the concrete constants are fleet-layer configuration). The PLC additionally runs its own internal sequence timeouts, surfaced only as `*Fault`. |
| No auto-resume | A fault never clears itself and nothing restarts automatically (section 9). Recovery is always: cause cleared → request withdrawn → PLC back to idle → **new** handshake with a **new** token, initiated by the fleet manager after operator confirmation where noted. If any Safety/ mirror shows a tripped function, a local monitored reset must happen first (`SafetyResetRequired` back to false); nothing over OPC UA or MQTT performs that reset. |
| Link loss | Loss of MQTT or OPC UA is degraded mode, not a safety event (invariant 2). Vehicle: controlled stop via its supervision watchdog (m1-01 §7). PLC: on `CellHeartbeatFleet` loss it brings any in-flight handshake to a defined idle or fault state by its own logic. Fleet manager: stops issuing, re-reads and resynchronizes on reconnect. |

Interface column shorthand: `VDA order` / `VDA state` / `VDA instantActions` =
MQTT topics of m1-01; `OPC …` = OPC UA node of m1-02.

## 2. Conveyor transfer (load and unload)

One table for both directions. `TransferDirection` = 0: station → vehicle
(AGV loads); = 1: vehicle → station (AGV unloads). The AGV is passive during
the transfer (m1-01 supports no pick/drop actions); it only holds position.
The hold is guaranteed by end-of-base mechanics: the order base ends at the
station node and the fleet manager does not extend it while the handshake runs.

Preconditions: handshake idle (`TransferRequest`=0, `TransferBusy`=0,
`TransferDone`=0, `TransferFault`=0), `ConveyorFault`=0; direction 0 also
`ConveyorPalletPresent`=1, direction 1 also `ConveyorPalletPresent`=0.

| # | Actor | Action / signal | Interface | Success condition | Timeout | Fault branch |
|---|---|---|---|---|---|---|
| 1 | Fleet manager | Send order whose base ends at the station node (tight `allowedDeviationXY`/`Theta`) | VDA order | `state` echoes `orderId`/`orderUpdateId`, no order-related error | next `state` ≤ 30 s | Order rejected: log, fix order, no PLC interaction has started |
| 2 | AGV | Drive to station node, stop at end of base | VDA state | `lastNodeId` = station node, `driving` = false | fleet ETA supervision (config) | Vehicle error (`errors[]` FATAL) or overdue: `cancelOrder`, report, re-plan |
| 3 | Fleet manager | Write fresh `TransferToken`, `TransferDirection`, then `TransferRequest` = 1 | OPC `Conveyor/Handshake/` | Writes acknowledged | 2 s | OPC write failure: degraded mode, vehicle stays parked, retry after resync |
| 4 | PLC | Echo token | OPC `TransferTokenAck` | `TransferTokenAck` = token | 2 s | Withdraw request, one retry with new token, then report station unresponsive |
| 5 | PLC | Interlocks satisfied, accept transfer | OPC `TransferReady` | `TransferReady` = 1 | 10 s | `TransferFault` = 1 or timeout → §5 fault procedure |
| 6 | PLC | Execute transfer | OPC `TransferBusy`, `ConveyorRunning` | `TransferBusy` = 1 observed; fleet manager does **not** extend the base while set | 5 s Ready→Busy | Timeout / `TransferFault` → §5 fault procedure |
| 7 | PLC | Complete transfer | OPC `TransferDone`, `ConveyorPalletPresent` | `TransferBusy` = 0, `TransferDone` = 1; `ConveyorPalletPresent` = 0 (dir 0) / 1 (dir 1) | 60 s Busy→Done | `TransferFault` → §5; `Done` with wrong `ConveyorPalletPresent` → treat as fault, do not release vehicle |
| 8 | Fleet manager | Withdraw: `TransferRequest` = 0, clear `TransferToken`; update its load bookkeeping | OPC `Conveyor/Handshake/` | PLC clears `TransferDone` and `TransferTokenAck` (back to idle) | 5 s | PLC stuck non-idle: report, station out of service until resync |
| 9 | Fleet manager | Extend order base past the station (`orderUpdateId` + 1) | VDA order | `state` shows new base nodes; vehicle departs | next `state` ≤ 30 s | Rejected update: re-issue or new order |

## 3. Door passage

The client requests passage, never "motor on" (m1-02 §6). The vehicle is held
before the door by end-of-base; the base is extended through the doorway only
after `PassageReady`.

Preconditions: handshake idle, `DoorFault` = 0.

| # | Actor | Action / signal | Interface | Success condition | Timeout | Fault branch |
|---|---|---|---|---|---|---|
| 1 | Fleet manager | Send order whose base ends at the hold node before the door; horizon continues beyond | VDA order | `state` echoes order, no error | next `state` ≤ 30 s | Order rejected: log, fix, nothing requested from PLC yet |
| 2 | AGV | Drive to hold node, stop | VDA state | `lastNodeId` = hold node, `driving` = false | fleet ETA supervision | `cancelOrder`, report, re-plan |
| 3 | Fleet manager | Write fresh `PassageToken`, then `PassageRequest` = 1 | OPC `Door/Handshake/` | Writes acknowledged | 2 s | OPC failure: vehicle stays at hold node, resync |
| 4 | PLC | Echo token | OPC `PassageTokenAck` | `PassageTokenAck` = token | 2 s | Withdraw, one retry with new token, then report |
| 5 | PLC | Open and hold door | OPC `PassageBusy` (moving), then `PassageReady`, `DoorOpen` | `PassageReady` = 1 and `DoorOpen` = 1 | 15 s | `PassageFault`/`DoorFault` or timeout → §5; vehicle was never released, stays at hold node |
| 6 | Fleet manager | Extend base through doorway to exit node; keep `PassageRequest` = 1 for the whole transit | VDA order | `state` shows extended base; vehicle moving | next `state` ≤ 30 s | Rejected update: withdraw passage request after vehicle confirmed still at hold node |
| 7 | AGV | Traverse doorway | VDA state | `lastNodeId` = exit node | 120 s transit | Vehicle stalled in doorway: do **not** withdraw request (door stays held); report, operator intervention |
| 8 | PLC | Detect doorway clear (PLC-side clearance detection — see §7 item 1), close door | OPC `PassageBusy` (closing), then `PassageDone`, `DoorClosed` | `PassageDone` = 1 and `DoorClosed` = 1 | 30 s after clear | `PassageFault`/`DoorFault`: door state unknown → block further passages, report; vehicle already through, may continue |
| 9 | Fleet manager | Verify **both** `lastNodeId` = exit node and `PassageDone` = 1, then withdraw: `PassageRequest` = 0, clear token | OPC `Door/Handshake/` | PLC clears `PassageDone` and `PassageTokenAck` | 5 s | PLC stuck non-idle: report, door out of service until resync |

The door's anti-crush protection is not this handshake: it is the F-CPU /
hardwired safety layer (invariant 1). This sequence only prevents the process
logic from *commanding* a close while a vehicle is expected in the doorway.

## 4. Charger docking

Trigger: `batteryState.batteryCharge` below the fleet threshold (fleet policy).
The vehicle-side charge mode and the charger-side contactor are two separate
handshakes with one mediator: `startCharging`/`stopCharging` over VDA 5050 to
the AGV, `ChargeRequest` over OPC UA to the PLC. The PLC closes the contactor
only from its own docking interlocks (m1-02 §7).

Preconditions: `ChargerAvailable` = 1, `ChargerFault` = 0, handshake idle.

| # | Actor | Action / signal | Interface | Success condition | Timeout | Fault branch |
|---|---|---|---|---|---|---|
| 1 | Fleet manager | Send order whose base ends at the charger bay node (tight deviation, `theta` set) | VDA order | `state` echoes order, no error | next `state` ≤ 30 s | Order rejected: log, fix |
| 2 | AGV | Dock: drive to bay node, stop | VDA state | `lastNodeId` = bay node, `driving` = false | fleet ETA supervision | `cancelOrder`, report, re-plan |
| 3 | Fleet manager | Write fresh `ChargeToken`, then `ChargeRequest` = 1 | OPC `Charger/Handshake/` | Writes acknowledged | 2 s | OPC failure: vehicle stays docked, resync |
| 4 | PLC | Echo token | OPC `ChargeTokenAck` | `ChargeTokenAck` = token | 2 s | Withdraw, one retry with new token, then report |
| 5 | PLC | Docking interlocks confirm, accept | OPC `ChargeReady` | `ChargeReady` = 1 | 10 s | Likely mis-dock: withdraw request, re-position vehicle with a short new order, one retry of steps 2–5, then operator |
| 6 | Fleet manager | Send `startCharging` instant action to the AGV | VDA instantActions | `actionStates[]` for the actionId reaches RUNNING/FINISHED and `batteryState.charging` = true | 10 s | Action FAILED: withdraw `ChargeRequest`, report vehicle-side charge fault |
| 7 | PLC | Close contactor (own interlock decision) | OPC `ChargeBusy`, `ChargerContactorClosed`, `ChargerOutputCurrent` | `ChargeBusy` = 1, `ChargerContactorClosed` = 1, `ChargerOutputCurrent` > 0 | 15 s after steps 5–6 | `ChargeFault` or no current → §5; also send `stopCharging` to the AGV |
| 8 | PLC + AGV | Charging runs; fleet manager monitors `batteryState.batteryCharge` rising | VDA state / OPC `ChargerOutputCurrent` | Charge rising per fleet policy | policy (e.g. min rise per 10 min) | No rise: treat as fault → step F below |
| 9a | PLC | Normal end (charger detects completion): open contactor | OPC `ChargeDone` | `ChargeBusy` = 0, `ChargeDone` = 1 | — | `ChargeFault` → §5 |
| 9b | Fleet manager | Early release (vehicle needed / target charge reached): proceed directly to 10 while `ChargeBusy` = 1 | — | — | — | — |
| 10 | Fleet manager | Send `stopCharging` to the AGV | VDA instantActions | `batteryState.charging` = false | 10 s | Action FAILED: report; still withdraw the request so the contactor opens |
| 11 | Fleet manager | Withdraw: `ChargeRequest` = 0, clear token | OPC `Charger/Handshake/` | PLC opens contactor (if still closed) in orderly sequence, clears `ChargeDone`/`ChargeTokenAck`, `ChargerContactorClosed` = 0 | 5 s | PLC stuck non-idle: report, charger out of service until resync |
| 12 | Fleet manager | Assign next order; vehicle undocks | VDA order | `state` shows new order | next `state` ≤ 30 s | — |
| F | Fleet manager | Any charge fault: `stopCharging` to AGV, then withdraw `ChargeRequest`, mark charger unavailable, report | both | Vehicle safe, charger isolated | — | §5 fault procedure |

Order of steps 10–11 matters: the vehicle stops drawing before the contactor
side is released, so the contactor is never asked to open under full load by
the process sequence (the PLC interlock protects it regardless).

## 5. Fault and timeout behavior — common procedure

| Aspect | Rule |
|---|---|
| Latching | PLC fault bits (`TransferFault`, `PassageFault`, `ChargeFault`, plus `ConveyorFault`, `DoorFault`, `ChargerFault`) are levels held by the PLC. They clear only when the fault cause is gone **and** the client has withdrawn the request. Fleet-side timeouts latch in the fleet manager's station model until an operator or a successful resync clears them. |
| What resets | Withdrawing the request bit (and clearing the token) returns the handshake to idle — it resets the *sequence*, never the *fault cause*. Equipment causes are cleared at the equipment (PLC alarm handling); safety-tripped causes require the local monitored reset (`SafetyResetRequired` observed back to false). No reset of any kind travels over MQTT or OPC UA. |
| Who reports | The fleet manager is the single reporter to the operator and the log for every sequence in this document. The PLC reports equipment truth via its status/fault nodes; the AGV reports vehicle truth via `errors[]` and `safetyState`. Neither of those two talks to the operator about the *sequence* — only the fleet manager correlates both sides (it is the only party that sees both interfaces). |
| How recovery starts | Never automatically. Fleet manager: withdraw request → verify PLC idle (`*Busy` = 0, `*Done` = 0, `*Fault` = 0, `*TokenAck` cleared) → obtain operator confirmation where the branch says "report" → start a **new** handshake with a **new** token, or re-route the vehicle. A vehicle holding at a station stays held (end of base) until the fleet manager deliberately extends or cancels its order. |
| Timeout ownership | Every timeout in the tables is supervised by the fleet manager. The PLC's internal sequence timeouts are its own and surface only as `*Fault` — the fleet manager never infers PLC state from elapsed time (invariant 10: the status nodes are the truth). |
| Resync after link loss | On OPC UA reconnect: read all handshake nodes, compare `*TokenAck` and `*SeqPlc` with the last known values, and reconcile before writing anything. A `*Done` found latched with the fleet manager's own token is a completed step — consume it, then withdraw. A foreign or empty token with `*Busy` set means state was lost: wait for the PLC to reach `Done`/`Fault`, then withdraw and report. |

## 6. Single-owner data map

Exactly one owner per item (invariant 10). Consumers read; they never
recompute. "Wins" states which value is authoritative where a second party
*could* compute a lookalike.

| Data item | Interface / node or field | Owner | Consumers | Double-compute risk — who wins |
|---|---|---|---|---|
| Vehicle pose + localization validity | VDA `state.agvPosition` (x, y, theta, mapId, positionInitialized) | AGV | Fleet manager | Fleet manager could dead-reckon from order progress — **AGV wins**, always |
| Vehicle velocity | VDA `state.velocity` | AGV | Fleet manager (monitoring) | — |
| Battery charge + vehicle charging state | VDA `state.batteryState` (batteryCharge, charging) | AGV | Fleet manager | `ChargerOutputCurrent` > 0 is **not** "vehicle is charging" — **AGV wins** for vehicle charge state |
| Charger output current | OPC `Charger/ChargerOutputCurrent` | PLC | Fleet manager (monitoring) | Distinct item from batteryState; never merged into one value |
| Order content (orderId, orderUpdateId, nodes, edges, actions) | VDA `order` | Fleet manager | AGV | — |
| Order execution progress (lastNodeId, nodeStates, edgeStates, actionStates, driving, paused, newBaseRequest) | VDA `state` | AGV | Fleet manager | Fleet manager must not mark a node reached from pose or timers — **AGV wins** |
| Vehicle connection state | VDA `connection` | AGV (+ broker last will) | Fleet manager | Protocol-level only; vehicle health comes from `state`, not from this |
| Vehicle capabilities and limits | VDA `factsheet` | AGV | Fleet manager | Concrete numerics owned by agv layer (m1-01 §8) |
| Vehicle safety status | VDA `state.safetyState` (eStop, fieldViolation) | AGV (onboard safety) | Fleet manager (report/alert only) | Report-only mirror of what onboard safety already did |
| Cell safety status | OPC `Safety/` (EStopActive, ProtectiveStopActive, SafetyDoorClosed, SafetyResetRequired) | F-CPU (PLC mirrors, read-only) | Fleet manager (report/alert only) | Never merged with vehicle safetyState into a computed "cell safe" flag used for control — each safety layer acts only on its own inputs (invariants 1, 7) |
| Zone A physical occupancy | OPC `Cell/ZoneAOccupied` | PLC (its sensors) | Fleet manager | Fleet manager could derive occupancy from vehicle poses — for the *physical* zone the **PLC wins**; the derived view is only the input to reservations |
| Zone reservations / traffic state | none (fleet-internal) | Fleet manager | — | Never exposed on the PLC (m1-02 §8) and not expressed as VDA zone sets (m1-01 §2) |
| Station equipment state | OPC status nodes (ConveyorRunning, ConveyorFault, ConveyorPalletPresent, DoorOpen, DoorClosed, DoorFault, ChargerAvailable, ChargerContactorClosed, ChargerFault) | PLC | Fleet manager | Fleet manager must not infer door/conveyor position from elapsed time — **PLC wins** |
| Handshake request side (TransferRequest, TransferDirection, PassageRequest, ChargeRequest) | OPC `*/Handshake/` | Fleet manager | PLC | — |
| Handshake tokens (TransferToken, PassageToken, ChargeToken) | OPC `*/Handshake/` | Fleet manager | PLC (opaque echo only, never parsed) | — |
| Token acks (`*TokenAck`) | OPC `*/Handshake/` | PLC | Fleet manager | — |
| Handshake result bits (`*Ready`, `*Busy`, `*Done`, `*Fault`) | OPC `*/Handshake/` | PLC | Fleet manager | — |
| Handshake sequence counters | `*SeqFleet`: Fleet manager; `*SeqPlc`: PLC | each its own | the other side | — |
| Heartbeats | `CellHeartbeatFleet`: Fleet manager; `CellHeartbeatPlc`: PLC | each its own | the other side | Loss = degraded mode only (invariant 2) |
| Cell mode and alarms (CellOperatingMode, CellAlarmActive) | OPC `Cell/` | PLC | Fleet manager | — |
| Load-on-vehicle bookkeeping | none (fleet-internal, derived from completed conveyor handshakes) | Fleet manager | — | No sensor exists (m1-01 omits `loads`; `ConveyorPalletPresent` is station-side only). Single owner is the fleet manager; nobody else may keep a copy |
| Physical docking at charger | PLC-internal interlock (not exposed) | PLC | — | Logical arrival (`lastNodeId` = bay node) is AGV-owned; each side acts only on its own item, neither republishes the other's |

## 7. Additions required (addressed to m1-01 / m1-02 — nothing invented here)

| # | Addressed to | Needed item | Why |
|---|---|---|---|
| 1 | m1-02 opcua-nodes.md | Door passage clearance detection. `PassageDone` semantics ("passage complete, door closed again") require the PLC to know the doorway is clear before closing (door table step 8), but m1-02 defines no such input or status node. Required: the PLC-side clearance sensor as a design assumption of the Door sequence, and recommended: a read-only `DoorwayClear` (Bool, owner PLC) status node so the fleet manager can diagnose a door that never closes. | Without it, step 8 has no defined trigger |
| 2 | m1-02 opcua-nodes.md (optional) | Read-only `ChargerVehicleDocked` (Bool, owner PLC). Lets the fleet manager distinguish "mis-docked" from "charger unhealthy" when `ChargeReady` stays false (charger table step 5). Diagnostic only; the handshake works without it. | Better fault triage |
| 3 | m1-01 vda5050-subset.md | **None.** Arrival and hold at every station use end-of-base mechanics (`released` flags) plus `state` reporting; the vehicle is passive during conveyor transfer, so the omitted pick/drop actions stay omitted. If a future vehicle must actively drive its load deck, pick/drop enter scope — that is an m1-01 change, not a silent extension here. | Recorded so the omission is a decision, not an oversight |
