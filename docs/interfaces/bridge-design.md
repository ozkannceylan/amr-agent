# Bridge design — Gazebo cell ↔ S7-1500 (M3)

Gate M3, ADR 0004. This document was written **before any bridge code** and is the
specification `bridge/` (m3-04) was implemented against.

Authority. `docs/interfaces/opcua-nodes.md` §9 is the node contract and
`sim/README.md` § "Demonstration cell (M3)" is the ROS 2 signal contract. This document
derives its signal map from §9.9 and adds only *operational* detail: conversion, cadence,
startup, liveness, reconnect and measurement. **If this document ever disagrees with §9,
§9 wins and this document is corrected** (§9.9 states the same rule).

---

## 1. What the bridge is, and is not

| | Statement |
|---|---|
| It is | One OS process that is **an OPC UA client** (invariant 4) **and a ROS 2 node**, and nothing else. |
| Its whole job | Carry each signal in the §9.9 map from one side to the other, unchanged, plus write its own heartbeat. |
| It is not | A controller, a sequencer, an interlock, a filter, a safety device, a fleet component, an HMI, or an OPC UA **server**. |
| It is not | Part of the fleet manager. ADR 0004 rejected folding the bridge into it. The two are separate processes that share no state and call no code of each other's, and m3-04 places the bridge in its own top-level layer `bridge/` (ADR 0005; see §12, open item 1). |
| It never | Listens on a socket, accepts a connection, or exposes a server endpoint of any kind. Client only, in every configuration, including the test-double configuration (§10). |
| Layer position | Cell (ROS 2 / Gazebo) ↔ bridge ↔ PLC (OPC UA server). It touches no other layer: no MQTT, no VDA 5050, no Nav2, no vehicle (invariant 11). |
| Timing class | **Best effort. Not a real-time component** (invariant 9). Its cadence is a target, not a deadline. No correctness in this cell depends on the bridge meeting a deadline; every timing decision that matters is a PLC timer in the PLC's own time base. |

### 1.1 The NO-LOGIC RULE

> The bridge applies **no process decision** to any signal. It moves values. The only
> numeric operation permitted anywhere in the bridge is **unit-preserving type
> conversion** (ROS `float64` → S7 `Real`, i.e. IEEE-754 double → single narrowing).
> No scaling, no offset, no clamping, no rounding to a "nicer" value, no unit change.

Everything below is a violation **in this cell**, with the owner of the decision:

| Would-be bridge behaviour | Why it is a violation | Correct owner |
|---|---|---|
| Thresholding `ProductSensorRange` into a present/absent bit | The switching distance depends on product geometry, beam alignment and desired hysteresis — a process decision, and it would create a second owner of "product present" (invariant 10) | PLC, `DemoCell/Status/ProductPresentAtSensor`, §9.3/§9.5 |
| Deriving `ConveyorDriveFault` by comparing command with measured speed | Same: tolerance and delay are process parameters | PLC, §9.5 |
| Latching a stop — holding `PanelStopCircuitClosed` false after the contact recloses | Latching *is* the stop function. The bridge would become the stop device | PLC standard program |
| Debouncing a contact in a way that changes meaning: suppressing a short press, stretching a pulse, requiring N stable samples | Changes which events the PLC can see. A 40 ms press either reaches the PLC or does not; that must be the transport's honest answer, not the bridge's opinion | PLC (filter time, if any) |
| Sequencing: publishing a belt speed because Start was pressed | This is the entire M3 demonstration, moved into the wrong layer | PLC |
| Any timer that gates a signal: "write only if stable for X ms", "hold the last good value for X ms after a dropout", re-write throttling that suppresses a change | A timer that decides whether a value is transported is control | PLC |
| Counting edges or integrating travel from the ~500 Hz encoder samples that decimation discards | Discarded samples must contribute **nothing**. Anything derived from them is information the PLC cannot see or audit | Nobody. The samples are discarded, full stop |
| Averaging, interpolating, min/max-holding or low-passing belt position, speed or range | A filter changes meaning (§9.2) | Nobody |
| Clamping, ramping, rate-limiting or zeroing `ConveyorSpeedCommand` | The bridge may never shape an actuator output (invariant 6, §9.4). The cell applies the command as given — including while a stop contact reads pressed. That is the point of the gate | PLC |
| Publishing `0.0` on `/cell/conveyor/cmd_speed` at startup, at shutdown, or on OPC UA disconnect | "Stop the belt" is a control decision, however sensible it looks. A bridge that stops equipment is a controller (§7, §8) | PLC |
| Inverting the NC contacts so the tag reads "pressed" | The cell already publishes circuit state and §9.3 names the nodes for circuit state. Inverting would put the wire-NC/program-NO convention in two places | Nobody — it is already correct on both sides |
| Substituting a default (0.0, last known, `range_max`) for a missing or `NaN` sample | Inventing a value the cell never produced (§6) | Nobody |
| Refusing to write one input because another input says something | An interlock | PLC |
| Re-writing a command it saw before an outage, after reconnect | Auto-resume of equipment (CLAUDE.md §9, §8 below) | PLC |
| Clamping range to `range_min` / `range_max` | A filter, and it would hide a sensor fault | Nobody |

Permitted, and exhaustive: field selection/addressing (§4.5), `bool` ↔ `Boolean` and
`float64` → `Float` marshalling, and incrementing the bridge's **own** heartbeat counter
(its own value, not a cell signal).

---

## 2. Process shape

```
        ROS 2 (Gazebo cell)                          OPC UA (S7-1500 server, PLCSIM)
                 |                                                  ^
   7 /cell/* topics                                                 | client session
                 v                                                  |
   +---------------------------------------------------------------------------+
   |  bridge process                                                            |
   |                                                                            |
   |  subscriber callbacks  -->  latest-value slots  -->  50 ms cycle task      |
   |  (one slot per input signal, overwritten, never queued)                    |
   |                                                                            |
   |  cycle: read Output -> publish to cell -> write Inputs -> write Heartbeat  |
   +---------------------------------------------------------------------------+
```

| Element | Decision | Why |
|---|---|---|
| Processes | One | It is one translator. Splitting it would create an internal interface with no owner |
| Concurrency | rclpy executor in one thread, OPC UA client on an asyncio loop; they meet only at the latest-value slots, guarded by a lock | Keeps ROS callback latency independent of OPC UA round-trip time, so a slow server cannot distort the measured receive timestamps |
| Buffering | **Slots, not queues.** Each input signal has exactly one slot: `(value, monotonic_receive_time, sim_time)`, overwritten by every callback | A queue would accumulate samples the bridge is then tempted to summarise. A slot makes latest-sample decimation the only possible behaviour (§4.3) |
| Cycle overrun | Logged and counted, never compensated | No catch-up bursts, no skipped-cycle logic. Compensation would be a timer that changes behaviour (invariant 9, §1.1) |
| Config | One file: endpoint URL, namespace URI, node BrowseNames, topic names, joint name, cycle period, security settings, evidence path, plus session and reconnect housekeeping (§8.1) and the diagnostics poll rate. **No thresholds, no limits, no tolerances, no timers** — a config key for any of those would be logic wearing a disguise | |
| Secrets | Endpoint credentials and certificates live outside the repository and are referenced by path (invariant 13) | |

---

## 3. Session and address-space rules

| Rule | Statement |
|---|---|
| Direction | The bridge connects **out** to the PLC's endpoint. Never inverted (invariant 4) |
| Namespace | Resolve namespace index at session establishment by browsing for URI `urn:amr-agent:cell:plc`. **Never hardcode the index** (§2 of the node model) |
| Node resolution | Resolve NodeIds by BrowseName path (`DemoCell/Input/...`) once per session, cache for the session, re-resolve on reconnect |
| Writable set | The bridge writes **only** the seven `DemoCell/Input/` nodes and `DemoCell/Link/BridgeHeartbeat` (§9.1). Any other write is a defect. m3-04 enforces this with a single write helper that rejects a NodeId outside the allowlist |
| Read set | `DemoCell/Output/ConveyorSpeedCommand` (applied to the cell), and `DemoCell/Status/*` + `DemoCell/Link/BridgeLinkOk` (logging only, never applied to anything) |
| Startup check | On every connect, verify that each resolved node's DataType matches the expected type below. A mismatch is a fatal configuration error, not something to coerce around |

---

## 4. Signal map

Derived directly from `opcua-nodes.md` §9.9. Seven nodes the bridge writes, one it reads and
applies, one heartbeat it writes, plus read-only diagnostics.

### 4.1 Cell → PLC (bridge writes into the PLC input image)

| # | ROS 2 topic | Msg type | Field | → OPC UA node (`DemoCell/…`) | S7 / OPC UA type | Conversion | Cadence |
|---|---|---|---|---|---|---|---|
| 1 | `/cell/conveyor/joint_state` | `sensor_msgs/JointState` | `position[i]`, `i` = index of `belt_joint` | `Input/ConveyorBeltPosition` | Real / `Float` | `float64 → Float` narrowing, metres unchanged | cyclic 20 Hz, latest sample |
| 2 | `/cell/conveyor/joint_state` | `sensor_msgs/JointState` | `velocity[i]`, same `i` | `Input/ConveyorBeltSpeed` | Real / `Float` | `float64 → Float`, m/s unchanged | cyclic 20 Hz, latest sample |
| 3 | `/cell/product_sensor/scan` | `sensor_msgs/LaserScan` | `ranges[0]` | `Input/ProductSensorRange` | Real / `Float` | `float32 → Float` (already single on the wire), metres unchanged, **no threshold** | cyclic 20 Hz, latest sample |
| 4 | `/cell/panel/start` | `std_msgs/Bool` | `data` | `Input/PanelStartPressed` | Bool / `Boolean` | none (NO contact, `true` = pressed) | on-change + refresh on connect |
| 5 | `/cell/panel/reset` | `std_msgs/Bool` | `data` | `Input/PanelResetPressed` | Bool / `Boolean` | none (NO contact, `true` = held). The rising edge, the hold time and which latches clear are PLC program content | on-change + refresh on connect |
| 6 | `/cell/panel/stop` | `std_msgs/Bool` | `data` | `Input/PanelStopCircuitClosed` | Bool / `Boolean` | none (NC circuit state, `true` = closed) | on-change + refresh on connect |
| 7 | `/cell/panel/process_stop` | `std_msgs/Bool` | `data` | `Input/PanelProcessStopCircuitClosed` | Bool / `Boolean` | none (NC circuit state, `true` = closed) | on-change + refresh on connect |

Row order follows `opcua-nodes.md` §9.3, which groups the panel inputs by failure direction
(NO, NO, NC, NC) rather than by panel layout.

### 4.2 PLC → cell (bridge reads and republishes)

| # | OPC UA node | S7 / OPC UA type | → ROS 2 topic | Msg type | Field | Conversion | Cadence |
|---|---|---|---|---|---|---|---|
| 8 | `DemoCell/Output/ConveyorSpeedCommand` | Real / `Float` | `/cell/conveyor/cmd_speed` | `std_msgs/Float64` | `data` | `Float → float64` widening, m/s unchanged. **No ramp, clamp, interlock or zeroing** | polled 20 Hz; published every cycle in which a value was read |

### 4.3 Bridge's own node

| # | Node | S7 / OPC UA type | Direction | Cadence |
|---|---|---|---|---|
| 9 | `DemoCell/Link/BridgeHeartbeat` | UInt / `UInt16` | bridge writes | 20 Hz, **after** the cycle's input writes are acknowledged (§7) |

### 4.4 Read-only, applied to nothing

| Node | Use |
|---|---|
| `DemoCell/Status/CellCycleRunning`, `CellProcessStopActive`, `CellResetRequired`, `ProductPresentAtSensor`, `ConveyorDriveFault` | Polled at 1 Hz, written to the bridge log and the evidence file only. **Never applied to a ROS topic and never used in a bridge decision** — using them would let PLC state steer the transport (§1.1) |
| `DemoCell/Link/BridgeLinkOk` | Same. Logged so the recording shows the PLC's own verdict next to the bridge's cycle counter |

### 4.5 Addressing detail (translation, not logic)

| Item | Rule |
|---|---|
| `belt_joint` index | Resolve `i` by matching `name[i] == "belt_joint"` (configured name), per message. If the name is absent, **no sample is taken** — log an error, leave the slot untouched. Matching by name rather than trusting index 0 is addressing, not logic |
| `ranges[0]` | Single-beam sensor; index 0 is the beam. An empty `ranges` array is a missing sample, handled as above |
| `inf` / `NaN` range | Written through **unchanged** (IEEE-754 single represents both). No substitution, no clamping. Logged at WARN and counted in the evidence file. The m3-01 cell (fixed reflector at 1.440 m, product at 0.540 m, range 0.05–3.0 m) is not expected to produce either. See §12 open item 3 — a `NaN` makes the PLC's `range < 1.00` comparison false, i.e. "no product", which the PLC program must handle explicitly |
| Narrowing loss | `double → single` on a ±2.50 m axis leaves ~0.2 µm of resolution. Any timestamping or differencing done for measurement is done **before** narrowing, on the ROS side (m3-02b open question 3) |

### 4.6 ROS 2 QoS

| Topic class | Subscription QoS | Why |
|---|---|---|
| `/cell/conveyor/joint_state`, `/cell/product_sensor/scan` | `KEEP_LAST` depth **1**, reliability matched to the publisher (verified with `ros2 topic info -v` at m3-04) | Depth 1 *is* latest-sample decimation, performed by the middleware queue rather than by bridge code. Nothing accumulates, so nothing can be derived |
| `/cell/panel/*` | `KEEP_LAST` depth 1, `RELIABLE`, `VOLATILE` | A contact change must not be dropped by best-effort delivery |
| `/cell/conveyor/cmd_speed` (publisher) | `KEEP_LAST` depth 1, `RELIABLE`, `VOLATILE` | Matches how the cell is driven today (`ros2 topic pub`) |
| Durability | `VOLATILE` throughout. `TRANSIENT_LOCAL` would give retained-like behaviour but requires the *publisher* to opt in, which is a cell-layer decision (m3-01) and would not remove the need for the startup rule in §6 | |

Mismatched QoS is silent in ROS 2 — the subscription simply receives nothing. m3-04 checks
endpoint compatibility at startup and logs the result.

---

## 5. Update model: poll or subscribe, and why

| Path | Mechanism | Rate | Rationale |
|---|---|---|---|
| Cell → PLC, analogs (1, 2, 3) | Cyclic **write** of the slot's latest value | 20 Hz / 50 ms | §9.2 expectation. ~2× the intended PLC scan, far below the ~500 Hz source, so measured latency is dominated by the OPC UA path and not by decimation |
| Cell → PLC, contacts (4, 5, 6, 7) | **Write on change** of the subscribed value, plus a full refresh of all seven inputs on every (re)connect | event | §9.2. Contacts are level signals with no fixed publish rate; writing an unchanged bool cyclically would duplicate the heartbeat's job (proving liveness) on a node whose meaning is a circuit state |
| PLC → cell (8) | **Cyclic read (poll)**, not an OPC UA subscription | 20 Hz / 50 ms, phase-locked to the write cycle | See below |
| Heartbeat (9) | Cyclic write, last operation of each cycle | 20 Hz / 50 ms | §7 |
| `Status/*`, `BridgeLinkOk` | Cyclic read | 1 Hz | Diagnostics only; a low rate keeps them visibly out of the measured loop |

### 5.1 Why poll rather than subscribe on the output path

The M3 gate exists to **measure** the loop honestly (exit item 3). That requirement drives
the choice more than efficiency does.

| Argument | Detail |
|---|---|
| Measurement attribution | With a poll, the bridge knows exactly when it asked and when the answer arrived; the interval it reports is a service round trip it originated. With a monitored item, the notification time is the sum of the server's sampling phase, its publishing interval, the queue occupancy and the network — none of which the client can separate. A "latency" measured that way is mostly a measurement of the server's own configuration |
| One cadence | Read, publish, write, heartbeat in a single 50 ms cycle gives one number to report and one ordering guarantee to hand the PLC (§7). Two independent cadences would make the ordering guarantee unprovable |
| Server independence | The fifteen-node `DemoCell/` address space of `opcua-nodes.md` §9 does not need server-side sampling. Polling avoids depending on the S7-1500's monitored-item limits, sampling granularity and publish-interval negotiation, which differ between PLCSIM Advanced and hardware |
| Failure visibility | A failed read is visible every cycle. A silent subscription (no notifications because nothing changed) is indistinguishable from a dead one without a keep-alive whose semantics are again server-configured |
| Honest cost, stated | Polling adds up to one cycle (0–50 ms, ~uniform) of phase latency on the output path and aliases changes faster than 50 ms. This is **reported, not hidden**: §9 requires the poll-phase component to be shown separately, and m3-04 may run a subscription-based comparison as supplementary evidence. The primary path stays poll |

Note that the input direction has no such choice: the bridge *writes* the PLC's input image;
there is no subscribe/poll question, only a cadence question.

---

## 6. Startup — resolving "there is no initial value"

Closes m3-01 open question 2, and refines the wording in `sim/README.md` § "There is no
initial value".

ROS topics are not retained. Before the first publish, the bridge has **no value** for the
four panel contacts, and no value for the belt or the range until the cell's first sample.
The tempting fix — write a "safe" default such as *contacts read as pressed, command 0.0* —
means the bridge invents a value the cell never produced. That value is then
indistinguishable, in the PLC's input image, from a real measurement. The bridge would be
asserting a process state, which is exactly §1.1's violation.

### 6.1 The rule

| Rule | Statement |
|---|---|
| R1 | The bridge **writes no `DemoCell/Input/` node until it has received a real sample** for that node's source signal. There is no default, no placeholder and no "safe value" written by the bridge, ever |
| R2 | Each input node is written as soon as its own source has produced a sample (they arrive at different times) |
| R3 | The bridge **writes no heartbeat** until **all seven** input nodes have been written at least once from a real sample and the writes were acknowledged. Only then does the heartbeat begin advancing |
| R4 | The same rule applies after every reconnect: on a new session the bridge first refreshes all seven inputs from its current slots and only then resumes the heartbeat. If any slot is still empty (that signal has never published), the heartbeat stays stopped |
| R5 | The bridge publishes nothing on `/cell/conveyor/cmd_speed` until it has read a value from the server (§8.3) |

### 6.2 What the PLC program can rely on

> **While `BridgeHeartbeat` is not advancing, the `DemoCell/Input/` values are not
> attributable to the cell.** They are the PLC's own DB start values, or values left over
> from a previous bridge session.
>
> **Once `BridgeHeartbeat` has advanced at least once, every one of the seven input nodes has
> carried at least one real sample from the running cell**, and continues to be refreshed
> per §5.

This is a single, checkable predicate — the PLC needs no per-signal validity bits, and no
node in §9 is added or changed to support it.

### 6.3 Where the fail-safe values live instead

The fail-safe pre-connection state is real and necessary; it simply belongs to the PLC, as
the start values of the input-image data block. Interface expectation for
`plc/demo-cell/SPEC.md` (start values, **not** logic, and not owned by this document):

| Node | Start value | Reading |
|---|---|---|
| `PanelStopCircuitClosed` | `FALSE` | circuit open = actuated or broken wire = not permitted to run (wire NC, program NO) |
| `PanelProcessStopCircuitClosed` | `FALSE` | same |
| `PanelStartPressed` | `FALSE` | NO contact open = not pressed. Never start on a start value |
| `PanelResetPressed` | `FALSE` | NO contact open = not pressed (`opcua-nodes.md` §9.3: this node's fail state is 0, the opposite of the two stop nodes). `TRUE` would assert a reset no operator pressed and clear a latch at startup — the automatic resume CLAUDE.md §9 forbids. R1 gives the same answer before the first publish: the bridge writes nothing, so the node holds this start value |
| `ConveyorBeltSpeed` | `0.0` | belt not known to be moving |
| `ConveyorBeltPosition` | `0.0` | a position with no meaning until the heartbeat runs; the program must not treat it as homed |
| `ProductSensorRange` | `0.0` | below any plausible threshold, i.e. reads as "beam blocked", the non-permissive interpretation |

Because the DB start values are only applied at a PLC cold restart, the PLC program must
qualify these inputs with the heartbeat predicate (§6.2) rather than with the start values
alone — a warm restart of the PLC with the bridge down leaves the *previous* session's
values in place. The reaction is PLC content (§7.4).

---

## 7. Liveness: `BridgeHeartbeat`

### 7.1 Semantics

| Property | Decision |
|---|---|
| Form | **Monotonic counter**, `UInt16`, incremented by 1 each write cycle, wrapping at 65535 → 0 |
| Rate | 20 Hz (every cycle), i.e. one increment per 50 ms |
| Wrap period | 65536 / 20 Hz ≈ 54.6 minutes |
| Ordering | Written **after** the cycle's input writes have been acknowledged by the server |
| Meaning | Exactly one thing: *the bridge completed a write cycle recently*. It carries no process information and must never be interpreted as one |

**Why a counter and not a timestamp.** A timestamp requires the bridge host and the PLC to
agree on an epoch and stay synchronised; it introduces clock skew, NTP and time-zone as
failure modes of a liveness signal, and the cell has three time bases already (bridge
`CLOCK_MONOTONIC`, Gazebo `/clock`, S7 system time). A counter needs no agreement: the PLC
compares the value with the one it saw last scan, in its own time base, which is the only
comparison it actually needs. Wrapping is harmless because the test is **change detection**,
never arithmetic on the count.

> Interface expectation for the PLC program: test `BridgeHeartbeat <> LastBridgeHeartbeat`
> and run a PLC timer on "unchanged". Do **not** subtract, do not test for `+1`, do not
> assume monotonic ordering across a wrap or across a bridge restart (§7.3).

**What the ordering buys the PLC.** Because the heartbeat is written last, an advanced
heartbeat implies the same cycle's input writes were acknowledged first. The PLC may see
new inputs with an old heartbeat (harmless), but never a new heartbeat with that cycle's
inputs missing. This is an ordering guarantee, not atomicity: the PLC can still latch inputs
and heartbeat in different scans.

### 7.2 Reaction is PLC content

This document specifies **only what the PLC can observe**. The staleness threshold, the
value of `BridgeLinkOk`, and what the conveyor does when the heartbeat stops are specified
in `plc/demo-cell/SPEC.md` and implemented in the standard program (§9.7 of the node model).
No timer, threshold or reaction exists in the bridge. Loss of the bridge is a **degraded
mode, not a safety event** (invariant 2), and no safety function is involved (invariant 1).

### 7.3 What the PLC observes in each failure mode

| # | Failure | Heartbeat | Input nodes | OPC UA session | PLC-observable difference |
|---|---|---|---|---|---|
| A | Bridge crash (SIGKILL, unhandled exception, host loss) | stops advancing at an arbitrary value | frozen at their last written values | depends on how the process died: a `SIGKILL` on a live host closes the TCP socket at OS level, so the server sees the drop at once (`EVIDENCE_SIGNAL_LOSS.md` §A.4, where the double saw `sessions 1 → 0` within 2 s); only a host or network loss, where no FIN/RST arrives, leaves the server holding the session until the session/subscription timeout | **Heartbeat stale.** Session-state may lag by seconds, so it is not a faster indicator |
| B | Bridge clean shutdown (SIGINT/SIGTERM) | stops advancing; **the bridge writes no farewell value and does not zero anything** | frozen at their last written values | session closed immediately and cleanly | **Heartbeat stale**, plus an immediate, clean session close. This is the only PLC-visible difference from A, and it is a difference in *how fast the session disappears*, not in the input image. **A program that behaves differently for A and B is wrong** |
| C | OPC UA connection loss (network, server restart, PLCSIM stopped) while the bridge lives | stops advancing (the bridge cannot write) | frozen at their last written values, or lost entirely if the server restarted with DB start values | session broken; bridge enters reconnect (§8) | **Heartbeat stale.** From the PLC side, indistinguishable from A. From the bridge side it is fully distinguishable and is logged |
| D | **Sim stopped, bridge alive** | **keeps advancing** — the bridge is still writing | **frozen at the last real sample**, because the slots are never cleared and the cyclic write repeats the last value | healthy | **No difference at all: the input image looks live.** A frozen belt position with a non-zero speed command is the only clue, and detecting that is `ConveyorDriveFault` — PLC content (§9.5) |

Case D is the honest limitation of a heartbeat that proves the *bridge* is alive: it says
nothing about the *cell*. Three options were considered and rejected here:

| Rejected option | Why |
|---|---|
| Stop the heartbeat when a topic goes quiet | A timer in the bridge that gates a signal (§1.1). It would also make "topic quiet" mean "bridge dead", conflating two different faults |
| Add a per-signal freshness node | New nodes are §9's to define, and it would move staleness policy into the interface. `ConveyorDriveFault` already gives the PLC a derivable verdict from signals it owns |
| Have the bridge zero the inputs when the cell stops | Inventing values (§6) |

The recommendation to `plc/demo-cell/SPEC.md` is therefore: treat a *live heartbeat with a
motionless belt under a non-zero speed command* as the drive-fault condition it already
owns. Recorded here as an observation, not as a requirement this document can impose.

### 7.4 What the equipment must therefore do — stated as an expectation only

For `plc/demo-cell/SPEC.md`, so the PLC program can be written against this document:

1. Qualify the seven input values with "heartbeat advancing" (§6.2). Do not act on the input
   image while the heartbeat is stale.
2. On heartbeat stale, drop the cycle-running flag and command `0.0` — noting that this
   command **cannot reach the cell while the bridge is down** (§8.4). It takes effect on
   the first read after the bridge returns, which is what makes recovery a PLC decision
   rather than a bridge decision.
3. Require a monitored, edge-triggered local reset before the cycle may run again
   (CLAUDE.md §9). A returning heartbeat must never, by itself, restart the conveyor.

---

## 8. Reconnect and restart — no auto-resume

### 8.1 OPC UA reconnect

| Step | Behaviour |
|---|---|
| Detection | A failed read or write, or a session/keep-alive failure, marks the session broken |
| Retry | Reconnect attempts at a fixed interval with a bounded backoff, forever. Retry timing is bridge housekeeping, not a signal gate — it never delays or suppresses a value that could be sent |
| On reconnect | Re-resolve the namespace index and all NodeIds (never reuse cached NodeIds across sessions), re-verify data types, then **refresh all seven inputs from the current slots** (§9.2), then resume the heartbeat per R4 |
| Heartbeat continuity | The counter **is not reset** across a reconnect and **is not reset** across a process restart if it can be avoided; either way the PLC must treat any *change* as liveness (§7.1), so a discontinuity is harmless and no rule depends on continuity |
| Empty slots | If a signal has produced no sample since bridge start, its node is not written and the heartbeat stays stopped (R3/R4). A reconnect does not lower that bar |

### 8.2 ROS side restart (cell restarted under a live bridge)

| Step | Behaviour |
|---|---|
| Subscriptions | rclpy re-matches publishers automatically; no bridge action |
| Slots | Retain their last value. They are **not** cleared — clearing them would require the bridge to decide the old value is invalid, which is a staleness judgement (§1.1). The consequence is case D of §7.3 and is documented, not patched |
| Heartbeat | Continues advancing throughout, because the bridge is alive and writing. This is intentional and is what §7.3 D describes |

### 8.3 The command path never resumes itself

| Rule | Statement |
|---|---|
| N1 | The bridge publishes on `/cell/conveyor/cmd_speed` **only** values it has just read from `DemoCell/Output/ConveyorSpeedCommand` in the current cycle |
| N2 | It **never re-publishes a value it read before an outage**. A value read before a disconnect is discarded at the disconnect and is never replayed |
| N3 | It publishes **nothing** while disconnected — not the last value, not zero, not anything |
| N4 | After reconnect the first published value is whatever the PLC is commanding **now**. If the PLC has dropped its cycle-running flag (as §7.4 expects), that value is `0.0`, and the belt stops. If the PLC is still commanding motion, the belt runs — because the PLC decided so, which is correct |
| N5 | The bridge has no notion of "resume", no saved command state, and no shutdown hook that writes a value |

This is CLAUDE.md §9 ("after a stop the machine never resumes automatically") honoured by
construction: the bridge holds no state that *could* resume anything.

### 8.4 Residual: the belt during an outage — stated honestly

While the bridge is down, **no command can reach the cell**, and the cell's gz
`JointController` holds the last velocity it was given — so the belt keeps running at its
last commanded speed until the bridge returns and delivers the PLC's current command.

| Point | Detail |
|---|---|
| Whose property is this | The **cell's**. m3-01 deliberately put no interlock, timeout or zeroing in the world; making the world stop on silence would place process logic in the simulation layer |
| Why the bridge must not fix it | Publishing `0.0` on disconnect is a control decision taken by a transport (§1.1). It would also mask exactly the behaviour M3 is meant to expose |
| Bound | On reconnect, the first read (≤ one cycle, 50 ms nominal) delivers the PLC's current command. The uncontrolled interval equals the outage, not more |
| Real-equipment note | On real equipment this residual does not exist in this form: the drive is dropped by a wired enable/contactor, not by an OPC UA value. The demonstration cell has no such wiring, which is a known limit of the simulation and is recorded in the evidence file |
| Not a safety claim | This is a process behaviour of a demonstration cell. No safety function is involved and none is claimed (invariant 1, ADR 0004) |

---

## 9. Measurement method — gate exit item (c)

### 9.1 Clock rules

| Rule | Statement |
|---|---|
| C1 | Every reported interval is the difference of two readings of **the same clock**. No interval is ever computed across clock domains |
| C2 | Bridge-side intervals use `CLOCK_MONOTONIC` (`time.monotonic_ns()`) on the bridge host. Never wall clock (NTP steps), never sim time (pauses and steps) |
| C3 | ROS message `header.stamp` is **sim time** from `/clock` and is recorded for decimation accounting only. It is never differenced against a monotonic reading |
| C4 | Cell-side actuation intervals use **sim time**, and the real-time factor is recorded alongside so the two domains can be compared honestly (m3-01 measured RTF ≈ 1.0 headless for this world, which is what makes the comparison meaningful) |
| C5 | The PLC's clock appears in no computed interval. Nothing in the measurement requires the PLC and the bridge to be synchronised |

### 9.2 What is measured

| ID | Interval | Start | End | Clock | What it contains |
|---|---|---|---|---|---|
| **L1** | Input hold | subscriber callback entry (sample received) | the cycle takes that sample out of its slot | monotonic | Slot hold time: decimation/queue age. Ending at the *slot take* rather than at the cycle start is deliberate — callbacks run on their own thread, so a sample can arrive after the cycle start and still be the one written, which would make a cycle-start-referenced interval negative. Expected ~uniform 0–50 ms. Reported separately so the 20 Hz cadence is not mistaken for latency |
| **L2** | Input write | start of the write | server write-response received | monotonic | Serialisation + OPC UA round trip + server-side write handling |
| **L3** | Bridge input path | callback entry | write response | monotonic | `L1 + L2`. The full cell → PLC-input-image time attributable to the bridge |
| **L4** | Output poll phase | value change occurs in the PLC | read that observes it | — | **Not measurable from the bridge.** Bounded above by the cycle period + server sampling. Reported as a bound, never as a measurement |
| **L5** | Output apply | read response received | `publish()` returns on `/cell/conveyor/cmd_speed` | monotonic | Bridge-attributable PLC → cell time |
| **L6** | Cell actuation | `cmd_speed` publish | `velocity[0]` on `/cell/conveyor/joint_state` first crosses 50 % of the commanded value | sim time | A **simulator** property, not a bridge property. Reported separately and labelled as such |
| **L7** | Closed loop | bridge writes a designated input value | bridge reads the PLC output that responds to it | monotonic | The only end-to-end number measurable from one side. Includes one PLC scan. Requires the PLC program (or the test double's echo, §10) to respond to a nominated input |
| **R1** | Cycle rate | consecutive cycle starts | | monotonic | Achieved cadence; target 50 ms |
| **R2** | Per-node write rate | consecutive writes of each node | | monotonic | Achieved update rate per node |
| **R3** | Decimation ratio | samples received vs samples written, per signal | | count | Explicit evidence that discarded samples were discarded and contributed to nothing (§1.1) |

### 9.3 How it is instrumented

| Item | Decision |
|---|---|
| Where | Inside the bridge. Each slot carries its receive timestamp; the cycle records start, per-node write-response and publish timestamps |
| Overhead | Timestamps are two integer reads per sample; the instrumentation is always on. There is no "measurement mode" that behaves differently from the production path — a measurement of a different code path measures nothing |
| Recording | Per-event rows appended to CSV in memory and flushed periodically. **No aggregation inside the loop** |
| Reported statistics | For each of L1, L2, L3, L5, L6, L7, R1, R2: **sample count, run duration, min, median, p95, max**. Never a mean alone. Plus: cycle overruns (> 50 ms), write errors, read errors, reconnects, `inf`/`NaN` samples, and R3 per signal |
| Run length | Long enough for a stable p95 and to include at least one full product traverse (~9 s of belt travel at 0.15 m/s per m3-01) and at least one process-stop press. m3-04 states the achieved duration and sample counts |
| Reproducibility | The run is scripted, states the configuration (cycle period, endpoint, server kind), and reports RTF |

### 9.4 Evidence location

| File | Content |
|---|---|
| `bridge/EVIDENCE_LATENCY.md` | Dated, human-readable capture: configuration, run duration, the statistics table, the caveats of §9.5, and the raw-file reference. Follows the `sim/worlds/CELL_EVIDENCE.md` precedent |
| `bridge/evidence/latency-<YYYY-MM-DD>.csv.gz` | Raw per-event rows behind the table |
| `bridge/EVIDENCE_SIGNAL_LOSS.md` | Dated capture of the four failure modes of §7.3, delivered by m3-04 alongside the latency file. The delivered capture is test-double, in-container; its repetition against PLCSIM is item 6 of the latency file's owner-run section |

The latency evidence file has **two clearly separated sections**: *test double, in-container,
agent-run* and *PLCSIM Advanced, owner-run*. The gate closes on the second. m3-04 produces
the first; the second is owner-executed (PLAN.md).

### 9.5 What cannot be measured without the real PLC — stated up front

| Not measurable in-container | Why |
|---|---|
| PLC scan-cycle contribution to L7 | The test double has no scan cycle. Its L7 is a transport floor, not the loop time |
| S7-1500 OPC UA server behaviour | Its sampling of the process image, its write handling relative to the scan, its session and monitored-item limits — a Python server reproduces none of them |
| PLCSIM Advanced vs hardware timing fidelity | PLCSIM's own timing is not the hardware's; the owner's run records which was used |
| L4 (output poll phase) in absolute terms | Requires observing the PLC's internal output change, which no client can see |
| Network path | The in-container run is loopback: no switch, no VPN, no PROFINET load. Numbers are a lower bound |
| The PLC's reaction time to a stale heartbeat | A property of the PLC program, measured against `plc/demo-cell/SPEC.md`, not of the bridge |

| Establishable with the test double alone | |
|---|---|
| That every §9.9 signal traverses in both directions, with correct types, names and polarity | |
| That the decimation rule is obeyed and discarded samples are counted (R3) | |
| L1, L2, L3, L5, R1, R2 as **bridge-side** figures — genuinely the bridge's own cost | |
| L6, which involves no PLC at all | |
| The startup rule (§6), the liveness behaviour (§7.3 A–D) and the no-auto-resume rule (§8.3), all as reproducible tests | |

---

## 10. Test double

| Item | Statement |
|---|---|
| What it is | A minimal OPC UA **server** that stands in for the S7-1500 on PLCSIM Advanced, exposing namespace `urn:amr-agent:cell:plc` with the `DemoCell/` address space of §9 — same BrowseNames, same folder paths, same data types, same access levels |
| Why it exists | So the bridge and the loop mechanics can be verified automatically on any machine that can run the cell, and so m3-04's tests do not need the owner's TIA/PLCSIM environment |
| Invariant 4 | **Preserved.** The server role belongs to the PLC; the double merely plays that role. The bridge is a client against the double and against PLCSIM, with no code path difference and no server mode (§1) |
| What it proves | The bridge: signal traversal both ways, types, polarity, decimation, startup rule, liveness behaviour, reconnect, no-auto-resume, and the bridge-side latency figures of §9.5 |
| What it does **not** prove | **The PLC program.** It runs no standard program, has no scan cycle, no process image, no interlocks, no cycle-running flag and no reset. Nothing observed against the double is evidence for `plc/demo-cell/SPEC.md` |
| Scaffolding is labelled | Anything the double does beyond storing values — echoing a nominated input for L7, or driving `ConveyorSpeedCommand` from a script to exercise the output path — is **test scaffolding**, marked as such in code and in the evidence file, and is not a model of PLC behaviour |
| ADR 0004 | The ADR rejected proving the loop against a mock *only*. The double is for automated regression; the gate's four exit items close against PLCSIM, owner-run |
| Operational rule | The double is never started as part of a demonstration run, and never on the same endpoint as PLCSIM. The evidence file always states which server produced each number |
| Location | `bridge/` (m3-04's scope), in a subdirectory whose name says it is a test double |

---

## 11. Dependencies (approved and pinned — `bridge/requirements.txt`)

| Dependency | Status | Purpose | Note |
|---|---|---|---|
| `rclpy`, `std_msgs`, `sensor_msgs`, `rosgraph_msgs` | present (`ros-jazzy-ros-base`) | ROS 2 node side | **Not new** |
| `python3-yaml` | present (ROS 2 dependency) | config file | **Not new** |
| Python stdlib: `asyncio`, `time`, `statistics`, `csv`, `logging`, `dataclasses`, `threading` | present | cycle, timing, percentiles, evidence | **Not new**; `statistics.quantiles` covers p95, so **numpy is deliberately not requested** |
| **`asyncua`** | **approved and installed** — pinned `asyncua==2.0.1` in `bridge/requirements.txt` (ADR 0005 D2) | OPC UA client, and the test double's server | The one new dependency, scoped to the `bridge/` layer. Pure-Python, async, actively maintained, LGPL-3.0, imported unmodified as a library and not vendored; the same package provides both client and server, so the double adds no second dependency. Pull-in: `cryptography` for secure channels, resolved transitively and recorded in the requirements file |

Alternatives considered: `python-opcua` / `opcua` (the deprecated predecessor of `asyncua`,
not recommended for new work) and `open62541` via bindings (a C toolchain dependency for no
benefit at this address-space size).

**Install mechanism, not a machine's path.** The pin is installed into a Python virtual
environment created with `--system-site-packages`, so the one interpreter can import both
`rclpy` from the sourced ROS 2 installation and `asyncua` from the venv. The
`--system-site-packages` flag is the load-bearing part: a plain system-wide `pip install`
fails because pip tries to replace the distribution-packaged `cryptography`, which has no
`RECORD` file and cannot be uninstalled (LESSONS 2026-07-27). The venv is created wherever
the user can write — under `/opt` in the container, under `$HOME` on WSL, where `/opt`
needs root — and its location is an environment fact, not a property of this design.
`bridge/README.md` carries the worked commands. No credentials or certificates are added
to the repository (invariant 13).

---

## 12. Open items carried forward

| # | Item | Status |
|---|---|---|
| 1 | Whether `fleet/README.md`'s "must not access ROS 2 internals" needed an exception for the bridge, which is by definition a ROS 2 node | **Resolved by ADR 0005**: the bridge is its own top-level layer, `bridge/`, not part of `fleet/`. No exception is needed and the earlier request for one is withdrawn; `fleet/README.md` stays absolute |
| 2 | m3-01 open question 2 (no initial value) | **Resolved** here: §6. The `sim/README.md` phrasing "the safe choice is contacts read as pressed and belt command reads as zero" is honoured, but as **PLC DB start values** (§6.3), not as values the bridge writes |
| 3 | `NaN` / `inf` on `ProductSensorRange` | Bridge behaviour fixed (§4.5: pass through, log, count). The PLC-side consequence is **closed** by `plc/demo-cell/SPEC.md` §6.2 (m3-05): the range is tested against its physical window before any process comparison, so `NaN` and `inf` are treated as a sensor fault rather than resolving to "no product" |
| 4 | §7.3 case D — sim stopped, bridge alive, input image looks live | Bridge cannot detect it without adding logic, and does not. **Closed** on the PLC side: `plc/demo-cell/SPEC.md` §6.6 takes the recommendation and latches `ConveyorDriveFault` on a non-zero command with a near-zero measured speed |
| 5 | m3-02b open question 3 (float64 → Real narrowing vs measurement) | **Honoured**: all timestamping and differencing happens on the ROS side before narrowing (§4.5) |
| 6 | m3-02b open question 1 (a Real output means the cycle-running flag gates a setpoint, not a coil) | Unchanged by this design. **Closed** by `plc/demo-cell/SPEC.md` §6.4: the setpoint is gated by driving it to zero in a mandatory, unconditional `ELSE`, never by a conditional write |
| 7 | 20 Hz cycle period | **Closed** by m3-04's measurement, `bridge/EVIDENCE_LATENCY.md` §A.4: the expectation is met — median cycle period 50.003 ms, 0 cycle overruns — so the item closes without a revision and §9.2 stands unchanged |
| 8 | m3-01 open question 6 (stale "Navigation scenario (M3)" heading in `sim/README.md`) | **Corrected in `sim/`**: the heading now reads "Navigation scenario (M5, deferred)" |
