# Bridge design — Gazebo plant ↔ S7-1500

**Two signal groups, one bridge process, one OPC UA session.**

| Signal group | Gate | Node contract | ROS 2 contract |
|---|---|---|---|
| **Demonstration cell** — conveyor, photo-eye, panel | M3, ADR 0004 | `opcua-nodes.md` §9 | `sim/README.md` § "Demonstration cell (M3)" |
| **Forklift commissioning cell** — traction, steer, fork, lidar | M4, ADR 0008 | `opcua-nodes.md` §10 | `agv/forklift/README.md` (§10.10) |

Both halves of this document were written **before the bridge code they specify**: the M3
half is the specification `bridge/` (m3-04) was implemented against, and the M4 half was
added by m4f-05 before any bridge work on that gate, on the same design-before-code
precedent.

Authority. `docs/interfaces/opcua-nodes.md` is the node contract — **§9** for the cell
group, **§10** for the forklift group. This document derives its signal map from §9.9 and
§10.10 and adds only *operational* detail: conversion, cadence, startup, liveness,
reconnect and measurement. **If this document ever disagrees with the node model, the node
model wins and this document is corrected** (§9.9 and §10.10 state the same rule from the
other side).

The forklift group loosens nothing the cell group established. Where a statement was true
of the cell alone it has been **scoped to its group rather than deleted**, and every count
below says which set it counts (§2.1).

---

## 1. What the bridge is, and is not

| | Statement |
|---|---|
| It is | One OS process that is **an OPC UA client** (invariant 4) **and a ROS 2 node**, and nothing else. |
| Its whole job | Carry each signal in the §9.9 and §10.10 maps — for the groups the run configures (§2.1) — from one side to the other, unchanged, plus write its own heartbeat. |
| It is not | A controller, a sequencer, an interlock, a filter, a safety device, a fleet component, an HMI, or an OPC UA **server**. |
| It is not | Part of the fleet manager. ADR 0004 rejected folding the bridge into it. The two are separate processes that share no state and call no code of each other's, and m3-04 places the bridge in its own top-level layer `bridge/` (ADR 0005; see §12, open item 1). |
| It is not | **The commissioning HMI.** Since ADR 0008 a *second* client writes to this server: the local HMI in `hmi/`. It is a separate process on its own session, with its own heartbeat and its own link verdict; the two clients share no state and their writable sets are disjoint by BrowseName prefix (`opcua-nodes.md` §10.1). The bridge never reads and never writes the `Forklift/Hmi/` group or `Forklift/Link/HmiHeartbeat` — §4.10, and the allowlist consequence in §3. |
| It never | Listens on a socket, accepts a connection, or exposes a server endpoint of any kind. Client only, in every configuration, including the test-double configuration (§10). |
| Layer position | Plant (ROS 2 / Gazebo: the demonstration cell **and** the forklift) ↔ bridge ↔ PLC (OPC UA server). It touches no other layer: no MQTT, no VDA 5050, no Nav2, no fleet vehicle, no HMI (invariant 11). The forklift is *plant*, not a fleet vehicle (ADR 0008 D5), so carrying it adds no fleet path and no vehicle path. |
| Timing class | **Best effort. Not a real-time component** (invariant 9). Its cadence is a target, not a deadline. No correctness in this cell depends on the bridge meeting a deadline; every timing decision that matters is a PLC timer in the PLC's own time base. |

### 1.1 The NO-LOGIC RULE

> The bridge applies **no process decision** to any signal. It moves values. The only
> numeric operation permitted anywhere in the bridge is **unit-preserving type
> conversion** (ROS `float64` → S7 `Real`, i.e. IEEE-754 double → single narrowing).
> No scaling, no offset, no clamping, no rounding to a "nicer" value, no unit change.

Everything below is a violation **in both cells**, with the owner of the decision. The
first block is the demonstration cell, the second the forklift; the rule is one rule and
the second block exists only because each new signal brings its own tempting shortcut:

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

Forklift group (`opcua-nodes.md` §10). Same rule, new temptations:

| Would-be bridge behaviour | Why it is a violation | Correct owner |
|---|---|---|
| Scaling `HmiTractionRequest` (a fraction) into a speed, or `HmiForkRequest` into m/s | The scale is `TRACTION_SPEED_MAX` / `FORK_SPEED_MAX`, PLC constants and process decisions. A bridge that owned the scale would be a second owner of the machine's top speed (invariant 10) — and it would have to read a node it may not read at all (§4.10) | PLC, `Forklift/Output/*` (§10.6) |
| Zeroing `ForkliftTractionSpeedRef` on the way out because `ForkliftObstacleInStopZone` reads `TRUE` | That *is* the obstacle stop. The latch, the monitored reset and the mandatory-`ELSE` gating are all PLC content (§10.7); a bridge doing it would become the stop device, and it would stop the machine on a signal the PLC had not yet acted on | PLC |
| Inverting `ForkliftObstacleInStopZone` so that `TRUE` means "clear" | The vehicle layer owns the topic's polarity and it is deliberately non-permissive-`TRUE`, including on an invalid or stale scan. Inverting in transport would put the polarity in two places, and changing one end alone silently inverts a stop (§10.5) | Nobody — it is already correct on both sides |
| Deriving "obstacle present" from `ForkliftObstacleMinDistance` | A second owner of a verdict the field bit already carries (invariant 10). The field is a sector over 181 samples and no scalar reconstructs it; the distance is a diagnostic and a transducer-health value, not a route to the same answer (§10.5) | Nobody |
| Clamping `ForkliftSteerAngleRef` to the mechanical range, or centring it when the machine stops | Both are process decisions the PLC makes and states: the clamp is the PLC's, and so is the centring — **all three setpoints, the steer angle included, are driven to `0.0` in the mandatory `ELSE` when the interlocks fail** (§10.6), which is precisely why the transport must not do it (§10.7) | PLC |
| Reading a `Forklift/Hmi/` request for any purpose, including logging | Operator intent is the HMI's to write and the PLC's to interpret. A bridge that read it would be a second interpreter of the operator, and the group is outside both the read set and the write allowlist by construction (§3, §4.10) | PLC |
| Republishing `0.0` on the three `/forklift/cmd/*` topics when the HMI link drops | The HMI watchdog is a PLC timer with a mandatory `ELSE` (§10.8 P5). The bridge cannot see `HmiLinkOk` as anything but a logged diagnostic, and acting on it would make the transport a watchdog | PLC |

Permitted, and exhaustive: field selection/addressing (§4.5), `bool` ↔ `Boolean` and
`float64` → `Float` marshalling, incrementing the bridge's **own** heartbeat counter (its
own value, not a plant signal), and **reading that same counter back once per cycle** to
detect a server restart — a value applied to nothing, transported nowhere and compared
only with what this session itself wrote (§8.1).

---

## 2. Process shape

```
   ROS 2 (Gazebo: cell and forklift)             OPC UA (S7-1500 server, PLCSIM)
                 |                                                  ^
   the CONFIGURED input topics                                      | ONE client session
   (§2.1: 7 /cell/*, 4 /forklift/*)                                 | for every group
                 v                                                  |
   +---------------------------------------------------------------------------+
   |  bridge process                                                            |
   |                                                                            |
   |  subscriber callbacks  -->  latest-value slots  -->  50 ms cycle task      |
   |  (one slot per input signal, overwritten, never queued)                    |
   |                                                                            |
   |  cycle: 0. read own heartbeat back  (restart check, §8.1 — transports      |
   |            nothing, decides nothing about a signal)                        |
   |         1. read Outputs  ->  2. publish each to its ROS topic              |
   |         3. write Inputs  ->  4. write Heartbeat, last                      |
   +---------------------------------------------------------------------------+
```

Step 0 is the one addition the implemented cycle made to the four steps this document
first specified. It exists because a server that reinitialises its data blocks **without
dropping the session** produces no failed read, no failed write and no keep-alive failure,
so nothing else in the cycle would notice (§8.1, restart-detection row). It reads a single
node the bridge itself owns and compares it with what this session last wrote.

| Element | Decision | Why |
|---|---|---|
| Processes | One | It is one translator. Splitting it would create an internal interface with no owner |
| Concurrency | rclpy executor in one thread, OPC UA client on an asyncio loop; they meet only at the latest-value slots, guarded by a lock | Keeps ROS callback latency independent of OPC UA round-trip time, so a slow server cannot distort the measured receive timestamps |
| Buffering | **Slots, not queues.** Each input signal has exactly one slot: `(value, monotonic_receive_time, sim_time)`, overwritten by every callback | A queue would accumulate samples the bridge is then tempted to summarise. A slot makes latest-sample decimation the only possible behaviour (§4.3) |
| Cycle overrun | Logged and counted, never compensated | No catch-up bursts, no skipped-cycle logic. Compensation would be a timer that changes behaviour (invariant 9, §1.1) |
| Config | One file: endpoint URL, **both namespace URIs** (§3.1), the **signal groups this run carries** (§2.1) with their node BrowseNames and topic names, joint name, cycle period, security settings, evidence path, plus session and reconnect housekeeping (§8.1) — including the *requested* session timeout, which is a request the server may revise and never a value the bridge may rely on (§3.2) — and the diagnostics poll rate. **No thresholds, no limits, no tolerances, no timers** — a config key for any of those would be logic wearing a disguise. The keep-alive period is **derived** from the granted session timeout (§3.2), never configured | |
| Secrets | Endpoint credentials and certificates live outside the repository and are referenced by path (invariant 13) | |

### 2.1 The configured signal set — normative

The bridge carries **signal groups**. A group is a named set of slots that travel
together because they belong to one plant and one node-model section: today the
**cell** group (`opcua-nodes.md` §9) and the **forklift** group (§10). The config
declares which groups a run carries; the union of their slots is the run's **configured
signal set**, and it is the only set any rule in this document counts.

| # | Rule |
|---|---|
| G1 | A group absent from the config **contributes nothing**: no subscription, no slot, no node resolution, no write, no poll, no diagnostics read, and no entry in the write allowlist. It is not a disabled feature that idles; it does not exist in that run |
| G2 | Every per-signal rule — the startup rule (§6), the write-on-change and refresh rules (§5), the reconnect refresh and the rewrite after a detected server restart (§8.1) — applies to **every slot in the configured set and to no other**. No rule names a fixed count |
| G3 | Groups are **not** a runtime mode. Nothing switches a group on or off while the process runs, nothing degrades from two groups to one, and no signal decides a group's membership. The set is fixed at startup by the config and is logged there |
| G4 | Adding a group adds **slots, not kinds**. It brings no new value type (Real/Bool/UInt16 only, `opcua-nodes.md` §10.3), no new dependency (§11), and no exception to §1.1 |
| G5 | The bridge writes **one** heartbeat for the whole process, not one per group (`opcua-nodes.md` §10.1, §10.11). One session, one counter, one link verdict `BridgeLinkOk`, consumed by both PLC function blocks |

The three configurations this design admits, with the counts every other section refers
back to:

| Configuration | Input slots (bridge writes) | Output slots (bridge reads and republishes) | Diagnostics (read, logged only) | Nodes touched |
|---|---|---|---|---|
| Cell only | 7 | 1 | 6 | 15 |
| Forklift only | 4 | 3 | 5 | **13** |
| Both | **11** | **4** | **11** | **27** |

"Nodes touched" counts the input slots, the output slots, the diagnostics and — for any
configuration that runs at all — the single `DemoCell/Link/BridgeHeartbeat`. That heartbeat
is a **§9 node used by every configuration**, which is why a forklift-only run touches 13
nodes and not 12: twelve of §10's eighteen, plus the one shared counter. With both groups
configured the interface carries 33 nodes (15 in §9, 18 in §10) and the bridge touches 27
of them: the six it never touches are the five `Forklift/Hmi/` requests and
`Forklift/Link/HmiHeartbeat`, which belong to the other client (§4.10).

**The honest consequence of one heartbeat over several groups.** Because G5 keeps a single
counter and §6 R3 holds it until every configured input has carried a real sample, a group
that is configured but whose publisher is not running **stalls the heartbeat for the whole
process**, including the other group's PLC block. That is deliberate: the alternative is a
per-group heartbeat, which means a second liveness story for one process (rejected in
`opcua-nodes.md` §10.1 and §10.11), or a bridge that decides a group is "not really
expected", which is a process decision (§1.1). The remedy is configuration, not logic —
**a run configures the groups it actually has**, and G1 makes that free.

### 2.2 What the forklift group does not change

The bridge is unchanged *in kind*: more slots, same contract (ADR 0008, "what becomes
easier"). Stated explicitly, because the cheapest way to break a working design is to
re-open a settled property while adding to it:

| Property | Standing |
|---|---|
| The NO-LOGIC RULE (§1.1) | Unchanged, and extended by example rather than by exception. The forklift brings new temptations, not new permissions |
| 20 Hz / 50 ms cycle | Unchanged, and shared by every group. Rows 14–16 are read in row 8's phase; no group gets its own cadence (§5, §5.1) |
| One process, one session, one heartbeat, one link verdict | Unchanged (§2.1 G5, `opcua-nodes.md` §10.1) |
| Poll rather than subscribe on the output path | Unchanged, for the same measurement reason (§5.1) |
| Slots, not queues | Unchanged. Four more slots, same latest-value overwrite (§2) |
| Startup rule R1/R2/R5, and R3's *meaning* | Unchanged. R3's **count** is now the configured set instead of a literal seven (§6.1) |
| Reconnect semantics, and the rewrite after a detected server restart | Unchanged in rule, now covering **every configured slot** rather than seven (§8.1) |
| No auto-resume on any output path | Unchanged, per slot (§8.3) |
| Per-session evidence files | Unchanged: one CSV per bridge session, unique name per start, never a shared path across restarts (§9.4) |
| Client only, never a server; invariant 4 | Unchanged, against PLCSIM and against the double (§1, §10) |
| Dependencies | Unchanged. No new library, no new value type (§11, §2.1 G4) |
| Two namespaces, browse by URI | Unchanged: the forklift adds a level, not a namespace (§3.1 N7) |

## 3. Session and address-space rules

| Rule | Statement |
|---|---|
| Direction | The bridge connects **out** to the PLC's endpoint. Never inverted (invariant 4) |
| Namespaces | The bridge's browse path crosses **two** namespaces. Both indices are resolved by URI at every session establishment and **neither is ever hardcoded** (§2 of the node model; §3.1 below). The browse-by-URI rule is unchanged; what changed at commissioning is that there are two URIs and that the interface's URI is TIA-derived from the server interface name, a field that is not editable (ADR 0006) |
| Node resolution | Resolve NodeIds by browse path from `Objects`, through the commissioned `ServerInterfaces` → `DemoCell` parents (§3.1), once per session; cache for the session; re-resolve on reconnect |
| Path shorthand | `DemoCell/Input/…`, `DemoCell/Forklift/Input/…` and every other `DemoCell/…` name in this document is a path **relative to the interface node**, never relative to `Objects` (§3.1 N1). `opcua-nodes.md` §10 writes the same forklift paths without the leading `DemoCell/`, because there the interface node is implied; `DemoCell/Forklift/Hmi/X` here and `Forklift/Hmi/X` there are the same node |
| Session parameters | Every session parameter the bridge sends is a **request**. The values in force are the ones the server returns. The bridge reads them back and uses those (§3.2) |
| Writable set | The bridge writes **only** the `Input/` nodes of the configured groups plus the single `DemoCell/Link/BridgeHeartbeat` (`opcua-nodes.md` §9.1, §10.1): 7 + 1 with the cell group alone, 4 + 1 with the forklift group alone, **11 + 1 with both**. Any other write is a defect. m3-04 enforces this with a single write helper that rejects a NodeId outside the allowlist, and the allowlist is **derived from the configured groups** (§2.1 G1), never hand-maintained beside them |
| Read set | The `Output/` nodes of the configured groups, applied to their ROS topics unchanged — `DemoCell/Output/ConveyorSpeedCommand` and the three `DemoCell/Forklift/Output/*Ref` — plus, for **logging only and never applied to anything**, `DemoCell/Status/*`, `DemoCell/Link/BridgeLinkOk`, `DemoCell/Forklift/Status/*` and `DemoCell/Forklift/Link/HmiLinkOk` |
| Never touched | `DemoCell/Forklift/Hmi/*` and `DemoCell/Forklift/Link/HmiHeartbeat` are **neither read nor written, in any configuration** (§4.10). They are the other client's nodes. This is a design rule, not an access consequence: the server would accept those writes today (§10.3 marks the group writable and the CPU runs with access control disabled), so the refusal has to come from the bridge |
| Startup check | On every connect, verify that each resolved node's DataType matches the expected type below. A mismatch is a fatal configuration error, not something to coerce around |

### 3.1 Namespaces and the commissioned browse path — normative

Owner-verified in TIA Portal and independently with an `asyncua` client from Windows,
commissioning phase 0, 2026-07-27 — **for the four M3 folders**. The `Forklift/` line is a
design value until it is read back out of the tool (`opcua-nodes.md` §10.2 step 6, §10.12
item 1), and it is marked as such rather than presented beside verified rows as if it
shared their standing:

```
Objects
  +- ServerInterfaces      ns http://www.siemens.com/simatic-s7-opcua   (Siemens, vendor-fixed)
       +- DemoCell         ns http://DemoCell                          (= interface name, ADR 0006)
            +- Input/  Output/  Status/  Link/   and their variables   (same ns as DemoCell)
            +- Forklift/   Hmi/ Input/ Output/ Status/ Link/           (same ns; DESIGN VALUE,
                                                                        §10.3, not yet read back)
```

| # | Rule |
|---|---|
| N1 | `DemoCell` does **not** hang directly under `Objects`. It is a child of the `ServerInterfaces` folder the S7-1500 publishes. A browse path that starts at `Objects` and looks for `DemoCell` finds nothing, on every connect, forever |
| N2 | The bridge resolves **both** namespace indices by URI at every session establishment: `http://www.siemens.com/simatic-s7-opcua` for `ServerInterfaces`, `http://DemoCell` for the interface node and everything beneath it. Neither index is hardcoded, and neither is derived from the other |
| N3 | The bridge **never assumes the parent folder shares the interface namespace**. Each element of the browse path is qualified with the index of the namespace *that element* belongs to. Phase 0 observed `ServerInterfaces` at index 3 and `DemoCell` at a different index; those numbers are evidence that the indices differ, not values to configure |
| N4 | Either URI missing presents as **namespace not found** at connect — the intended failure mode (ADR 0006 D4). It is a connect failure, retried per §8.1. The bridge never browses around it, never scans the namespace array for a likely-looking entry, and never falls back to an index |
| N5 | Both URIs are config values (§2): one is vendor-fixed, the other follows the interface name, and that name is contract. Renaming the server interface changes its namespace URI and breaks every browse until the config follows (ADR 0006) |
| N6 | Nothing above is a signal decision. Namespace resolution happens once per session, before any value moves, and its outcome is connect or fail — never a substituted, defaulted or held value (§1.1, §6 R1) |
| N7 | The forklift group adds a **level, not a namespace**. `opcua-nodes.md` §10.2 extends the commissioned `DemoCell` interface instead of creating a second one, so the interface name and its derived URI `http://DemoCell` do not move: N1–N6 hold word for word, the browse path still crosses exactly **two** namespaces, and `DemoCell/Forklift/…` resolves under the same interface node as `DemoCell/Input/…`. A *second* interface would break this — a third URI, a second root, and N1–N6 restated for a path no evidence exercises — which is why §10.2 rules that if a later gate creates one, its name is a contract decision taken in a document and never in the tool |

Conformance of the running client and the test double to N1–N6 was delivered by
m3-21 and is recorded in `bridge/EVIDENCE_CONNECT.md` §1–§2 (§12 item 9). N7 is a scope
statement about those same rules and needs no separate mechanism; what it does need is the
owner's read-back of the `Forklift/` subtree (§12 item 10).

### 3.2 Session timeout and keep-alive — normative

The S7-1500 **revises the session timeout**. Phase 0, same date: a requested 3600000 ms was
granted as 30000 ms — a clamp downwards there, but the rules below hold in whichever
direction the grant lands, because the request the bridge now sends is smaller than that
observed grant.

| # | Rule |
|---|---|
| S1 | The session timeout in the config (§2) is a **requested** value. It is what the bridge asks for and nothing more |
| S2 | On connect the bridge **reads the granted (revised) session timeout from the CreateSession response** and logs the requested and granted values together. From that point the granted value is the only session timeout any bridge behaviour may use. The bridge never assumes its request was honored |
| S3 | The keep-alive interval is **derived from the granted value**, never configured and never derived from the request. The derivation: a fixed fraction of the granted timeout small enough that at least three keep-alive exchanges fall inside the granted window (i.e. period ≤ granted / 3), so two consecutive lost exchanges cannot by themselves expire the session. At the commissioned grant of 30000 ms that is ≤ 10000 ms |
| S4 | Both values are re-read and the keep-alive re-derived on **every** new session, including every reconnect (§8.1). A grant is a property of one session, not of the server |
| S5 | The granted value also bounds the PLC-side observation in §7.3 case A: it is how long the server may hold a session whose client vanished without a FIN/RST |
| S6 | The same discipline applies to **every** negotiated parameter, not only this one — the secure channel lifetime is revised by the same mechanism, and were a subscription ever added (§5.1 rejects one) its publishing interval and keep-alive count would be too. Requested is not granted, anywhere |

Why the derivation matters even though the bridge is never idle: the 50 ms cycle touches the
server ~20 times a second, so in a healthy run the keep-alive is not what holds the session
open. It matters when the cycle is stalled — and it matters that it is derived, because a
keep-alive computed from an un-granted 3600000 ms would never fire inside a 30 s window, so
the session would expire while the bridge believed it had an hour.

This is **connection housekeeping, not a signal gate** — the same standing as §8.1's retry
timing. It never delays or suppresses a value that could be sent, and it applies no process
decision to any signal (§1.1).

Library note, `asyncua==2.0.1` (the pin in §11), verified 2026-07-27: the client already
overwrites its own `session_timeout` with `RevisedSessionTimeout` from the CreateSession
response, logs a warning when the two differ, and derives its health-probe timeout from the
resulting value. That warning is not a substitute for S2's log line — m3-21 found it prints
the library's *secure channel* default as the requested value, not the session timeout the
bridge asked for (`bridge/EVIDENCE_CONNECT.md` §3). S2 and S3 therefore mostly forbid
*undoing* the library's behaviour — re-reading the config value afterwards, or computing
anything from the requested number — and require that both numbers reach the bridge's own
log and the evidence file.

Conformance of the running client and the test double to S1–S6 was delivered by m3-21 and is
recorded in `bridge/EVIDENCE_CONNECT.md` §1–§3 and §5, with the grant landing below the
request in one run and above it in the other (§12 item 9).

---

## 4. Signal map

Two groups (§2.1), derived directly from `opcua-nodes.md` §9.9 and §10.10. With both
configured: **eleven** nodes the bridge writes, **four** it reads and applies, one
heartbeat it writes and reads back, **eleven** read-only diagnostics — and **six** nodes on
the same interface it never touches (§4.10).

| Rows | Group | Direction | Where |
|---|---|---|---|
| 1–7 | cell | cell → PLC | §4.1 |
| 8 | cell | PLC → cell | §4.2 |
| 9 | both | the bridge's own node | §4.3 |
| 10–13 | forklift | plant → PLC | §4.7 |
| 14–16 | forklift | PLC → plant | §4.8 |

The forklift rows **continue** the numbering rather than restarting it, so an existing
reference to "signal map row 5" keeps meaning what it meant. Addressing (§4.5) and QoS
(§4.6) stay single tables covering both groups; the group-specific detail sits with each
group's rows.

### 4.1 Demonstration cell → PLC (bridge writes into the PLC input image)

| # | ROS 2 topic | Msg type | Field | → OPC UA node (`DemoCell/…`) | S7 / OPC UA type | Conversion | Cadence |
|---|---|---|---|---|---|---|---|
| 1 | `/cell/conveyor/joint_state` | `sensor_msgs/JointState` | `position[i]`, `i` = index of `belt_joint` | `Input/ConveyorBeltPosition` | Real / `Float` | `float64 → Float` narrowing, metres unchanged | cyclic 20 Hz, latest sample |
| 2 | `/cell/conveyor/joint_state` | `sensor_msgs/JointState` | `velocity[i]`, same `i` | `Input/ConveyorBeltSpeed` | Real / `Float` | `float64 → Float`, m/s unchanged | cyclic 20 Hz, latest sample |
| 3 | `/cell/product_sensor/scan` | `sensor_msgs/LaserScan` | `ranges[0]` | `Input/ProductSensorRange` | Real / `Float` | `float32 → Float` (already single on the wire), metres unchanged, **no threshold** | cyclic 20 Hz, latest sample |
| 4 | `/cell/panel/start` | `std_msgs/Bool` | `data` | `Input/PanelStartPressed` | Bool / `Boolean` | none (NO contact, `true` = pressed) | on-change + refresh on connect |
| 5 | `/cell/panel/reset` | `std_msgs/Bool` | `data` | `Input/PanelResetPressed` | Bool / `Boolean` | none (NO contact, `true` = held, fail state `FALSE`). The rising edge the PLC acts on and which latches clear are PLC program content; there is no hold time and no timer | on-change + refresh on connect |
| 6 | `/cell/panel/stop` | `std_msgs/Bool` | `data` | `Input/PanelStopCircuitClosed` | Bool / `Boolean` | none (NC circuit state, `true` = closed) | on-change + refresh on connect |
| 7 | `/cell/panel/process_stop` | `std_msgs/Bool` | `data` | `Input/PanelProcessStopCircuitClosed` | Bool / `Boolean` | none (NC circuit state, `true` = closed) | on-change + refresh on connect |

Row order follows `opcua-nodes.md` §9.3, which groups the panel inputs by failure direction
(NO, NO, NC, NC) rather than by panel layout.

### 4.2 PLC → demonstration cell (bridge reads and republishes)

| # | OPC UA node | S7 / OPC UA type | → ROS 2 topic | Msg type | Field | Conversion | Cadence |
|---|---|---|---|---|---|---|---|
| 8 | `DemoCell/Output/ConveyorSpeedCommand` | Real / `Float` | `/cell/conveyor/cmd_speed` | `std_msgs/Float64` | `data` | `Float → float64` widening, m/s unchanged. **No ramp, clamp, interlock or zeroing** | polled 20 Hz; published every cycle in which a value was read |

### 4.3 Bridge's own node

One node, both directions, and the only node the bridge may read for a purpose other than
transport — because it is the only node the bridge owns.

| # | Node | S7 / OPC UA type | Direction | Cadence |
|---|---|---|---|---|
| 9 | `DemoCell/Link/BridgeHeartbeat` | UInt / `UInt16` | bridge writes | 20 Hz, **after** the cycle's input writes are acknowledged (§7) |
| 9r | `DemoCell/Link/BridgeHeartbeat` | UInt / `UInt16` | bridge **reads back** | 20 Hz, **first** operation of each cycle. Session bookkeeping: compared only with what this session last wrote, applied to nothing, published nowhere (§8.1) |

Row 9r is shared by every configured group, like row 9 (§2.1 G5). It is not a per-group
node and there is no second heartbeat (`opcua-nodes.md` §10.11).

### 4.4 Demonstration cell read-only, applied to nothing

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
| Forklift scalars (rows 10–16) | Every forklift topic carries `std_msgs/Float64` or `std_msgs/Bool`, whose payload is the single field `data`. **There is no index to resolve and no array to select from.** The vehicle layer derives `fork_height` from the joint array and both obstacle values from the 181-sample scan, and publishes scalars (`opcua-nodes.md` §10.10); that derivation is the vehicle layer's, and a bridge doing it would be filtering (§1.1) |
| `inf` / `NaN` on any forklift Real | Same rule as the range above: written through **unchanged**, logged at WARN, counted. The PLC tests each Real affirmatively against its plausibility window and takes the fault in the `ELSE` (`opcua-nodes.md` §10.4, §10.5), so a non-finite value reads there as a sensor fault. Note the deliberate consequence for `ForkliftObstacleMinDistance`: `0.0` is the vehicle layer's no-data sentinel and sits *outside* its window, so it must reach the PLC as `0.0` and not be repaired here |

### 4.6 ROS 2 QoS

Both groups, one table. Every row is a *subscription* profile except where marked.

| Topic class | Subscription QoS | Why |
|---|---|---|
| `/cell/conveyor/joint_state`, `/cell/product_sensor/scan` | `KEEP_LAST` depth **1**, reliability matched to the publisher (verified with `ros2 topic info -v` at m3-04) | Depth 1 *is* latest-sample decimation, performed by the middleware queue rather than by bridge code. Nothing accumulates, so nothing can be derived |
| `/cell/panel/*` | `KEEP_LAST` depth 1, `RELIABLE`, `VOLATILE` | A contact change must not be dropped by best-effort delivery |
| `/cell/conveyor/cmd_speed` (publisher) | `KEEP_LAST` depth 1, `RELIABLE`, `VOLATILE` | Matches how the cell is driven today (`ros2 topic pub`) |
| `/forklift/fork_height`, `/forklift/linear_speed`, `/forklift/obstacle/min_distance` | `KEEP_LAST` depth **1**, reliability matched to the publisher | Same rule as the cell analogs. Here the **source is slower than the cycle** (10 Hz published against a 20 Hz cycle, `opcua-nodes.md` §10.5), so no decimation occurs and depth 1 simply guarantees the slot holds the newest sample. Depth 1 is kept anyway: the queue must not become a place where samples could accumulate if the source rate ever rises |
| `/forklift/obstacle/in_stop_zone` | `KEEP_LAST` depth 1, `RELIABLE`, `VOLATILE` | A field-violation change must not be dropped by best-effort delivery — the panel-contact argument, applied to the one forklift Bool |
| `/forklift/cmd/traction_speed`, `/forklift/cmd/steer_angle`, `/forklift/cmd/fork_speed` (publishers) | `KEEP_LAST` depth 1, `RELIABLE`, `VOLATILE` | Matches the cell's command publisher. The vehicle layer's nodes use a default reliable, volatile profile with a deeper queue, which is compatible; compatibility is **checked at startup, not assumed** |
| Durability | `VOLATILE` throughout, both groups. `TRANSIENT_LOCAL` would give retained-like behaviour but requires the *publisher* to opt in, which is a plant-layer decision (m3-01 for the cell, `agv/forklift/` for the forklift) and would not remove the need for the startup rule in §6 | |

Mismatched QoS is silent in ROS 2 — the subscription simply receives nothing. m3-04 checks
endpoint compatibility at startup and logs the result; the forklift topics are checked the
same way, per configured group.

### 4.7 Forklift plant → PLC (bridge writes into the PLC input image)

| # | ROS 2 topic | Msg type | Field | → OPC UA node (`DemoCell/Forklift/…`) | S7 / OPC UA type | Conversion | Cadence |
|---|---|---|---|---|---|---|---|
| 10 | `/forklift/fork_height` | `std_msgs/Float64` | `data` | `Input/ForkliftForkHeight` | Real / `Float` | `float64 → Float` narrowing, metres unchanged | cyclic 20 Hz, latest sample (source 10 Hz) |
| 11 | `/forklift/linear_speed` | `std_msgs/Float64` | `data` | `Input/ForkliftLinearSpeed` | Real / `Float` | `float64 → Float`, m/s unchanged, sign preserved | cyclic 20 Hz, latest sample (source 10 Hz) |
| 12 | `/forklift/obstacle/in_stop_zone` | `std_msgs/Bool` | `data` | `Input/ForkliftObstacleInStopZone` | Bool / `Boolean` | none — **no inversion** (`TRUE` = object in the field, or a missing, stale or structurally unusable scan, or a sector with no sample in either valid class; a beyond-range return is `CLEAR` evidence at `range_max` and never sets `TRUE` on its own — `74c7d5f`) | on-change + refresh on every (re)connect **and after a detected server restart** (§8.1) |
| 13 | `/forklift/obstacle/min_distance` | `std_msgs/Float64` | `data` | `Input/ForkliftObstacleMinDistance` | Real / `Float` | `float64 → Float`, metres unchanged, **no threshold**; the `0.0` no-data sentinel is passed through as `0.0` | cyclic 20 Hz, latest sample (source 10 Hz) |

Row order follows `opcua-nodes.md` §10.5. Two properties of this group differ from the
cell's and are stated rather than left to be inferred:

- **The source is slower than the cycle.** All four publish at 10 Hz against a 20 Hz
  cycle, so no decimation happens and the cyclic write simply repeats the latest slot.
  A repeated identical write is **not** a freshness statement — freshness is the
  heartbeat's job (§7), and a plant that has stopped publishing under a live bridge is
  case D of §7.3, unchanged here.
- **Row 12 is the one input whose `TRUE` is the non-permissive state**, inverting the
  contact convention of rows 4–7. The bridge carries it exactly as published; inverting is
  a §1.1 violation, and fail-safety is carried instead by the vehicle layer's fail-to-`TRUE`,
  the `TRUE` DB start value and the `BridgeLinkOk` qualification (`opcua-nodes.md` §10.5,
  §10.9). Anyone renaming that node moves the ROS topic's polarity in the same change.

### 4.8 PLC → forklift plant (bridge reads and republishes)

| # | OPC UA node (`DemoCell/Forklift/…`) | S7 / OPC UA type | → ROS 2 topic | Msg type | Field | Conversion | Cadence |
|---|---|---|---|---|---|---|---|
| 14 | `Output/ForkliftTractionSpeedRef` | Real / `Float` | `/forklift/cmd/traction_speed` | `std_msgs/Float64` | `data` | `Float → float64` widening, m/s unchanged. **No ramp, clamp, interlock or zeroing** | polled 20 Hz; published every cycle in which a value was read |
| 15 | `Output/ForkliftSteerAngleRef` | Real / `Float` | `/forklift/cmd/steer_angle` | `std_msgs/Float64` | `data` | widening, rad unchanged. **No clamp and no centring** — both are the PLC's: it clamps to the mechanical range and drives the angle to `0.0` in the interlock-failed `ELSE`, like the other two setpoints (§10.6) | as above |
| 16 | `Output/ForkliftForkSpeedRef` | Real / `Float` | `/forklift/cmd/fork_speed` | `std_msgs/Float64` | `data` | widening, m/s unchanged. `0.0` means *hold*, and the bridge translates it into nothing — it publishes `0.0` | as above |

All four output rows (8 and 14–16) are read and published in the **same cycle phase**, so
the process keeps one cadence and one ordering guarantee to hand the PLC (§5, §7.1). Rows
14–16 obey §8.3 word for word: nothing is published while disconnected, nothing read before
an outage is replayed, and after reconnect the first published value is whatever the PLC is
commanding now.

### 4.9 Forklift read-only, applied to nothing

| Node (`DemoCell/Forklift/…`) | Use |
|---|---|
| `Status/ForkliftTeleopActive`, `ForkliftObstacleStopActive`, `ForkliftSpeedLimitActive`, `ForkliftResetRequired` | Polled at 1 Hz, written to the bridge log and the evidence file only. **Never applied to a ROS topic and never used in a bridge decision** — these are exactly the verdicts a helpful transport would be tempted to act on (§1.1) |
| `Link/HmiLinkOk` | Same. The PLC's verdict on the *other* client's liveness, logged so a recording shows both link verdicts side by side. It never gates a publish, a write or a heartbeat |

### 4.10 Never read, never written: the HMI group — a design rule

> **The bridge does not touch `DemoCell/Forklift/Hmi/*` or
> `DemoCell/Forklift/Link/HmiHeartbeat`, in any configuration, in either direction.**

| Node | Standing for the bridge |
|---|---|
| `Hmi/HmiTractionRequest`, `HmiSteerRequest`, `HmiForkRequest`, `HmiTeleopRequest`, `HmiResetRequest` | Not in the write allowlist, not in the read set, not in the diagnostics poll. Written by the HMI, read by the PLC (`opcua-nodes.md` §10.3) |
| `Link/HmiHeartbeat` | The same. Its only contract reader is the PLC; a bridge that logged it would be a second observer of the operator's liveness, with a second opinion available to drift from `HmiLinkOk` |

Why it is a rule here and not merely an absence:

| Reason | Detail |
|---|---|
| Single writer | Every node has exactly one writer (invariant 10). Two clients on one server make that a live risk instead of a formality, and the two writable sets are disjoint **by BrowseName prefix** so the rule is checkable from a node name alone (`opcua-nodes.md` §10.1, §10.3) |
| The server would allow it | `Forklift/Hmi/*` is marked *Writable from HMI/OPC UA* (§10.3) and the commissioned CPU runs with access control disabled and security `None` (§9.10). Per-*client* scoping is policy, not enforcement (ADR 0008 D2.5). So a bridge write to an HMI node would **succeed**, silently, and the operator's request would be overwritten by a transport |
| Reading is not harmless either | A read is how logic starts. A request value in the bridge's hands is an invitation to scale it, to gate on it, or to "helpfully" republish it — every one of which is a §1.1 violation and a second interpreter of the operator |

**The write-allowlist consequence**, which is what makes the rule enforceable rather than
aspirational:

1. The allowlist is **derived from the configured groups** (§2.1 G1): the `Input/` nodes of
   each configured group, plus the one heartbeat key. It is never a second hand-maintained
   list that could drift from the config.
2. With both groups configured it holds exactly **12** keys — 7 `DemoCell/Input/`, 4
   `DemoCell/Forklift/Input/`, and `DemoCell/Link/BridgeHeartbeat`. Nothing under any
   `Hmi/`, `Output/`, `Status/` or other `Link/` name is in it, in any configuration.
3. The single write helper rejects a NodeId outside the allowlist (§3). The rejection is a
   **defect signal** — a raised error naming the rule — not a skipped write to be retried.
4. The config loader rejects a configuration that places an `Hmi…` node in a writable
   position, so the defect is caught at startup rather than at the first write attempt.
   Belt and braces with the per-tag *Writable* flag on the server: two independent
   enforcements, the arrangement §10.3 describes.
5. The negative test is only meaningful against a server that **would** accept the write,
   which is why the test double serves the `Hmi/` group writable (§10). A refusal proven
   against a server that refuses everything proves nothing about the bridge.

---

## 5. Update model: poll or subscribe, and why

| Path | Mechanism | Rate | Rationale |
|---|---|---|---|
| Cell → PLC, analogs (1, 2, 3) | Cyclic **write** of the slot's latest value | 20 Hz / 50 ms | §9.2 expectation. ~2× the intended PLC scan, far below the ~500 Hz source, so measured latency is dominated by the OPC UA path and not by decimation |
| Cell → PLC, contacts (4, 5, 6, 7) | **Write on change** of the subscribed value, plus a full refresh of **every configured input** on every (re)connect and after a detected server restart (§8.1) | event | §9.2. Contacts are level signals with no fixed publish rate; writing an unchanged bool cyclically would duplicate the heartbeat's job (proving liveness) on a node whose meaning is a circuit state |
| PLC → cell (8) | **Cyclic read (poll)**, not an OPC UA subscription | 20 Hz / 50 ms, phase-locked to the write cycle | See below |
| Plant → PLC, forklift analogs (10, 11, 13) | Cyclic **write** of the slot's latest value | 20 Hz / 50 ms | `opcua-nodes.md` §10.5. The source publishes at 10 Hz, so the cycle rewrites the latest slot and nothing is decimated; the cadence is the *bridge's*, not a claim about the plant |
| Plant → PLC, forklift field bit (12) | **Write on change**, plus the same full refresh as rows 4–7 | event | §10.5. The one forklift level signal, treated exactly as a contact |
| PLC → plant, forklift (14, 15, 16) | **Cyclic read (poll)**, same phase as row 8 | 20 Hz / 50 ms | One cadence for the whole process (§5.1, "one cadence") |
| Heartbeat (9) | Cyclic write, last operation of each cycle | 20 Hz / 50 ms | §7 |
| Heartbeat read-back (9r) | Cyclic read, **first** operation of each cycle | 20 Hz / 50 ms | §8.1's restart detection. It is in this table for honesty about what the cycle costs, not because it moves a signal — it moves none |
| `Status/*`, `BridgeLinkOk`, `Forklift/Status/*`, `Forklift/Link/HmiLinkOk` | Cyclic read | 1 Hz | Diagnostics only; a low rate keeps them visibly out of the measured loop. Eleven nodes with both groups configured, all logged and applied to nothing |

### 5.1 Why poll rather than subscribe on the output path

The M3 gate exists to **measure** the loop honestly (exit item 3). That requirement drives
the choice more than efficiency does.

| Argument | Detail |
|---|---|
| Measurement attribution | With a poll, the bridge knows exactly when it asked and when the answer arrived; the interval it reports is a service round trip it originated. With a monitored item, the notification time is the sum of the server's sampling phase, its publishing interval, the queue occupancy and the network — none of which the client can separate. A "latency" measured that way is mostly a measurement of the server's own configuration |
| One cadence | Read, publish, write, heartbeat in a single 50 ms cycle gives one number to report and one ordering guarantee to hand the PLC (§7). Two independent cadences would make the ordering guarantee unprovable — and adding a signal group must not add a cadence, which is why rows 14–16 share row 8's phase rather than acquiring their own |
| Server independence | The address space the bridge touches is small in every configuration — 15 nodes for the cell group (`opcua-nodes.md` §9), 12 of the 18 in §10 for the forklift group plus the shared heartbeat, 27 for both (§2.1) — and needs no server-side sampling. Polling avoids depending on the S7-1500's monitored-item limits, sampling granularity and publish-interval negotiation, which differ between PLCSIM Advanced and hardware, and it keeps that independence as the node count grows |
| Failure visibility | A failed read is visible every cycle. A silent subscription (no notifications because nothing changed) is indistinguishable from a dead one without a keep-alive whose semantics are again server-configured — and, as §3.2 S6 records, whose requested parameters the server is free to revise |
| Honest cost, stated | Polling adds up to one cycle (0–50 ms, ~uniform) of phase latency on the output path and aliases changes faster than 50 ms. This is **reported, not hidden**: §9 requires the poll-phase component to be shown separately, and m3-04 may run a subscription-based comparison as supplementary evidence. The primary path stays poll |

Note that the input direction has no such choice: the bridge *writes* the PLC's input image;
there is no subscribe/poll question, only a cadence question.

---

## 6. Startup — resolving "there is no initial value"

Closes m3-01 open question 2, and refines the wording in `sim/README.md` § "There is no
initial value".

ROS topics are not retained. Before the first publish, the bridge has **no value** for the
four panel contacts or the forklift field bit, and no value for the belt, the range, the
fork height, the chassis speed or the obstacle distance until each source's first sample.
The tempting fix — write a "safe" default such as *contacts read as pressed, command 0.0* —
means the bridge invents a value the plant never produced. That value is then
indistinguishable, in the PLC's input image, from a real measurement. The bridge would be
asserting a process state, which is exactly §1.1's violation.

### 6.1 The rule

| Rule | Statement |
|---|---|
| R1 | The bridge **writes no input node until it has received a real sample** for that node's source signal — in either group. There is no default, no placeholder and no "safe value" written by the bridge, ever |
| R2 | Each input node is written as soon as its own source has produced a sample (they arrive at different times, and the two groups start at different times) |
| R3 | The bridge **writes no heartbeat** until **every input in the configured signal set** (§2.1) has been written at least once from a real sample and the writes were acknowledged. Only then does the heartbeat begin advancing. **The set is what the config declares, not what the interface offers**: a cell-only run counts 7, a forklift-only run counts 4, both groups count 11. A group that is not configured contributes no slot and cannot hold the heartbeat back (§2.1 G1) |
| R4 | The same rule applies after every reconnect **and after a detected server restart** (§8.1): the bridge first refreshes every configured input from its current slots and only then resumes the heartbeat. If any slot is still empty — that signal has never published — the heartbeat stays stopped. On a detected restart both steps fall in the **same cycle**: the rewrite is step 3 and the heartbeat is step 4, so the heartbeat resumes in that cycle unless the rewrite left a configured input unwritten |
| R5 | The bridge publishes nothing on an output topic until it has read a value from the server for that node (§8.3). This is per output slot, so a cell-only run withholds `/cell/conveyor/cmd_speed` and a run with both groups withholds all four |

**Why R3 counts the configured set and not a fixed number.** The rule as first written said
"all seven", which was the whole input set while the cell group was the only group. Left
that way, a **forklift-only run would stall the heartbeat forever**, waiting for conveyor
topics the run does not have and was never configured to have — the bridge withholding
liveness over signals that are absent by design rather than missing by fault. A cell-only
run is unaffected either way, and that is the point: the literal was correct for exactly
one configuration and silently wrong for every other, which is what a count written into a
rule always becomes. Scoping it to the configured set preserves the rule's meaning exactly
— *the heartbeat advances only when every signal this run carries has been carried at least
once* — and the tightening R3 exists for, a heartbeat that implies a truthful input image,
is unchanged. Only the definition of "every" now comes from the config instead of from a
literal.

### 6.2 What the PLC program can rely on

> **While `BridgeHeartbeat` is not advancing, the input values of every configured group
> are not attributable to their plant.** They are the PLC's own DB start values, or values
> left over from a previous bridge session.
>
> **Once `BridgeHeartbeat` has advanced at least once, every input node in the configured
> signal set has carried at least one real sample from a running plant**, and continues to
> be refreshed per §5.

This is a single, checkable predicate — the PLC needs no per-signal validity bits, and no
node in `opcua-nodes.md` §9 or §10 is added or changed to support it. One heartbeat covers
both groups (§2.1 G5), which is why the predicate stays one sentence as the signal set
grows, and why a group configured without its publisher holds the whole predicate down
(§2.1, "the honest consequence").

The forklift group consumes this predicate through the PLC's own verdict rather than
directly: `opcua-nodes.md` §10.9 states that while `BridgeLinkOk` is `FALSE` the four
`Forklift/Input/` values are not attributable to the plant. `BridgeLinkOk` is the PLC's
verdict on this same heartbeat (§7.2), so the two statements are one statement seen from
two sides — there is no second liveness path and no second verdict (§10.1, §10.11).

### 6.3 Where the fail-safe values live instead

The fail-safe pre-connection state is real and necessary; it simply belongs to the PLC, as
the start values of the input-image data block. Interface expectation for
`plc/demo-cell/SPEC.md` (start values, **not** logic, and not owned by this document) —
**cell group**; the forklift group's start values are `opcua-nodes.md` §10.9's and are
deliberately not repeated here, because a start value with two homes has two owners
(invariant 10):

| Node | Start value | Reading |
|---|---|---|
| `PanelStopCircuitClosed` | `FALSE` | circuit open = actuated or broken wire = not permitted to run (wire NC, program NO) |
| `PanelProcessStopCircuitClosed` | `FALSE` | same |
| `PanelStartPressed` | `FALSE` | NO contact open = not pressed. Never start on a start value |
| `PanelResetPressed` | `FALSE` | NO contact open = not pressed (`opcua-nodes.md` §9.3: this node's fail state is 0, the opposite of the two stop nodes). `TRUE` would assert a reset no operator pressed and clear a latch at startup — the automatic resume CLAUDE.md §9 forbids. R1 gives the same answer before the first publish: the bridge writes nothing, so the node holds this start value |
| `ConveyorBeltSpeed` | `0.0` | belt not known to be moving |
| `ConveyorBeltPosition` | `0.0` | a position with no meaning until the heartbeat runs; the program must not treat it as homed |
| `ProductSensorRange` | `0.0` | below any plausible threshold, i.e. reads as "beam blocked", the non-permissive interpretation |

The PLC program must qualify these inputs with the heartbeat predicate (§6.2) rather than
with the start values alone, because a restart can land either way and **neither way is
attributable to the plant**: a CPU restart may reinitialise the non-retentive input DB to
these start values — observed on **2026-07-28**, where a *warm* restart reverted every
input under a surviving bridge session, which is why §8.1 carries a restart-detection row —
or it may leave a previous session's values in place. Only the predicate separates either
case from a live input image. The reaction is PLC content (§7.4).

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
| A | Bridge crash (SIGKILL, unhandled exception, host loss) | stops advancing at an arbitrary value | frozen at their last written values | depends on how the process died: a `SIGKILL` on a live host closes the TCP socket at OS level, so the server sees the drop at once (`EVIDENCE_SIGNAL_LOSS.md` §A.4, where the double saw `sessions 1 → 0` within 2 s); only a host or network loss, where no FIN/RST arrives, leaves the server holding the session until the **granted** session timeout expires — the value the server returned, not the one the bridge requested (§3.2 S5); the commissioned S7-1500 granted 30 s | **Heartbeat stale.** Session-state may lag by up to the granted session timeout, so it is never the faster indicator |
| B | Bridge clean shutdown (SIGINT/SIGTERM) | stops advancing; **the bridge writes no farewell value and does not zero anything** | frozen at their last written values | session closed immediately and cleanly | **Heartbeat stale**, plus an immediate, clean session close. This is the only PLC-visible difference from A, and it is a difference in *how fast the session disappears*, not in the input image. **A program that behaves differently for A and B is wrong** |
| C | OPC UA connection loss (network, server restart, PLCSIM stopped) while the bridge lives | stops advancing (the bridge cannot write) | frozen at their last written values, or lost entirely if the server restarted with DB start values | session broken; bridge enters reconnect (§8) | **Heartbeat stale.** From the PLC side, indistinguishable from A. From the bridge side it is fully distinguishable and is logged |
| D | **Sim stopped, bridge alive** | **keeps advancing** — the bridge is still writing | **frozen at the last real sample**, because the slots are never cleared and the cyclic write repeats the last value | healthy | **No difference at all: the input image looks live.** A frozen belt position with a non-zero speed command is the only clue, and detecting that is `ConveyorDriveFault` — PLC content (§9.5) |
| E | **Server restart that does *not* drop the session** — a CPU warm restart, or a download that reinitialises the input DBs while the session survives | keeps advancing until the cycle's read-back fires; then the write cache is invalidated and R4 applies, so it pauses only if the rewrite leaves a configured input unwritten | **reverted to the CPU's DB start values**, and a write-on-change client would never repair the ones whose slot values had not changed | **healthy** — no failed read, no failed write, no keep-alive failure, so nothing in the cycle would otherwise notice | **The dangerous one: nothing looks wrong.** A live heartbeat over an input image of start values — open stop circuits, `ForkliftObstacleInStopZone` `TRUE`. It is caught by the **bridge**, not by the PLC, because only the bridge knows what it last wrote: §8.1's restart-detection row. Observed live on 2026-07-28, where the PLC read open stop circuits for minutes. **Caught, but not always at the first revert**: one landing inside the cycle's own read-then-write window is erased by that cycle's heartbeat write and waits for the next one — measured at roughly one in ten, with a 4.0 s exposure in the run that caught it (§8.1 *Restart residual*) |

Case D is the honest limitation of a heartbeat that proves the *bridge* is alive: it says
nothing about the *plant*. Three options were considered and rejected here:

| Rejected option | Why |
|---|---|
| Stop the heartbeat when a topic goes quiet | A timer in the bridge that gates a signal (§1.1). It would also make "topic quiet" mean "bridge dead", conflating two different faults |
| Add a per-signal freshness node | New nodes are §9's to define, and it would move staleness policy into the interface. `ConveyorDriveFault` already gives the PLC a derivable verdict from signals it owns |
| Have the bridge zero the inputs when the cell stops | Inventing values (§6) |

The recommendation to `plc/demo-cell/SPEC.md` is therefore: treat a *live heartbeat with a
motionless belt under a non-zero speed command* as the drive-fault condition it already
owns. Recorded here as an observation, not as a requirement this document can impose.

**Case D on the forklift plant, and what is missing there.** The mechanism is identical —
slots are never cleared, so a stopped plant under a live bridge presents a frozen but
plausible input image — but the forklift group has **no drive-fault verdict**: the node set
of `opcua-nodes.md` §10 carries no `ForkliftDriveFault`, and §10.11 records its absence
deliberately rather than inventing one. So on the forklift the PLC has the same exposure
with no node to express the conclusion in. Nothing here is the bridge's to fix: detecting a
frozen plant is exactly the timer-and-threshold work §1.1 assigns to the PLC. Carried as
§12 open item 12, mirroring `opcua-nodes.md` §10.12 item 3.

Case E, by contrast, *is* the bridge's, and is handled — see §8.1. The division is: what
the plant does is the PLC's to judge; what **this session** wrote is the bridge's to know.

### 7.4 What the equipment must therefore do — stated as an expectation only

For `plc/demo-cell/SPEC.md`, so the PLC program can be written against this document:

1. Qualify **every configured group's input values** with "heartbeat advancing" (§6.2). Do
   not act on the input image while the heartbeat is stale. For the forklift group this is
   already written as the `BridgeLinkOk` qualification rule of `opcua-nodes.md` §10.9.
2. On heartbeat stale, drop the cycle-running flag and command `0.0` — and, for the
   forklift, drive every motion setpoint to `0.0` in the mandatory `ELSE` of §10.6 — noting
   that these commands **cannot reach the plant while the bridge is down** (§8.4). They
   take effect on the first read after the bridge returns, which is what makes recovery a
   PLC decision rather than a bridge decision.
3. Require a monitored, edge-triggered local reset before the cycle may run again
   (CLAUDE.md §9). A returning heartbeat must never, by itself, restart the conveyor or
   re-enable teleop. For the forklift the reset input is `HmiResetRequest` and its edge is
   armed **per link session** (§10.8 P6) — a guard the bridge neither implements nor sees.

---

## 8. Reconnect and restart — no auto-resume

### 8.1 OPC UA reconnect, and server restart under a surviving session

| Step | Behaviour |
|---|---|
| Detection | A failed read or write, or a session/keep-alive failure, marks the session broken. **Any** exception raised by a request in flight counts, not only the anticipated session-error types — an unanticipated one is still routed here and counted separately, because the evidence should say *how* the session was lost, not only that it was. The keep-alive period is the one derived from the **granted** session timeout of the session that is failing (§3.2 S3) |
| Retry | Reconnect attempts at a fixed interval with a bounded backoff, forever. Retry timing is bridge housekeeping, not a signal gate — it never delays or suppresses a value that could be sent |
| On reconnect | Re-resolve **both namespace indices** by URI (§3.1 N2) and all NodeIds through the `ServerInterfaces` → `DemoCell` path, for every configured group — never reuse a cached index or NodeId across sessions — then re-read the granted session timeout and re-derive the keep-alive from it (§3.2 S4), re-verify data types, then **refresh every configured input from the current slots** (§9.2, §2.1 G2), then resume the heartbeat per R4 |
| **Restart detection** (server restarted, session survived) | A CPU restart or a download can reinitialise the input data blocks **without** breaking the session, so none of the signals in the *Detection* row fires — §7.3 case E, observed live on 2026-07-28. The bridge therefore **reads its own `BridgeHeartbeat` back once per cycle**, as step 0 of the cycle (§2, §4.3 row 9r), and compares it with the value *this session* last wrote. Any difference means the server's copy of the input image is not the one this session established. The test is an **exact inequality** against that last written value: not "lower than", because the counter wraps at 65535 → 0 and a wrap is not a restart; and not a tolerance or a timer, because there is none to choose. It is session bookkeeping — the value read is applied to nothing, published nowhere, and compared with nothing but the bridge's own record (§1.1) |
| **Restart repair** | On a difference, the **per-session write cache is invalidated**, and every configured input slot that carries a real sample is rewritten in that same cycle's step 3 — **every group, level signals included**, because write-on-change is precisely what a reverted server defeats: the slot value has not changed, so nothing would otherwise be rewritten. R1 is untouched: a slot that has never carried a real sample is still not written and no value is invented. R4 then governs the heartbeat in step 4 of the same cycle. Nothing is latched, timed or thresholded; a cache is emptied |
| **Restart residual** | **Two cases, and the second is the large one.** *(a)* A revert that lands on exactly the value this session last wrote is invisible to the test — one heartbeat value in 65536. *(b)* **A revert that lands inside the cycle's own read-then-write window is erased before it can be seen**: the step-0 read-back happens, the revert lands, and that same cycle's step-4 heartbeat write restores the witness to the value the bridge expects, so the next read-back compares **equal** and the restart goes undetected. Measured against the double, 2026-07-29 (`bridge/EVIDENCE_CONNECT.md` § m4f-06.4), quoted as the run printed it: the window is `median 5.255 ms p95 7.886 ms max 10.143 ms` of a `median 50.015 ms` cycle, `as a fraction of the median cycle: 10.5 %` — so roughly **one revert in ten**, not one in 65536. Not a theoretical figure: in that run one masked revert left the server holding an **open stop circuit and `ForkliftObstacleInStopZone` `TRUE` for 4.0 s — 81 heartbeat increments — under a heartbeat that never faltered**, which is §7.3 case E surviving its own detector, and on the commissioned cell the PLC would have qualified those inputs as attributable because the predicate it is given is the heartbeat. **Pre-existing and not forklift-specific**: the cell-only `check_session_lifecycle.py` reproduced it the same morning on the unmodified cell config, and it is in the m3-35 code as shipped. A restart that *does* break the session is caught by the *Detection* row instead, which invalidates the same cache. **Both restart harnesses now trigger reverts until one is caught, up to a bound, and report how many were masked**, so the property is measured on every run rather than flaked over. Still stated rather than patched: closing it needs a second witness, and **a second witness needs an owner — an open owner decision, unchanged by this measurement, which sizes the gap without deciding it** |
| Heartbeat continuity | The counter **is not reset** across a reconnect, **is not reset** by a detected server restart, and **is not reset** across a process restart if it can be avoided; either way the PLC must treat any *change* as liveness (§7.1), so a discontinuity is harmless and no rule depends on continuity |
| Empty slots | If a signal has produced no sample since bridge start, its node is not written and the heartbeat stays stopped (R3/R4). Neither a reconnect nor a restart repair lowers that bar |

**Why the heartbeat is the witness, and why it stays a valid one with two clients.**
`BridgeHeartbeat` is the only node the bridge writes for itself, and it is in the bridge's
writable set and in no other client's: the HMI's counter is `Forklift/Link/HmiHeartbeat`,
which the bridge never touches, and the two writable sets are disjoint by construction
(`opcua-nodes.md` §10.1, §4.10 here). So a value at `BridgeHeartbeat` that this session did
not write can only have come from the server itself. A witness that two clients could write
would prove nothing, and a witness taken from the *plant's* signals would make a process
value into a session verdict — which is why the bridge's own node is the one used.

### 8.2 ROS side restart (a plant restarted under a live bridge)

| Step | Behaviour |
|---|---|
| Subscriptions | rclpy re-matches publishers automatically; no bridge action. This holds per group: restarting the forklift's vehicle-layer nodes while the cell keeps publishing changes nothing in the bridge, and vice versa |
| Slots | Retain their last value. They are **not** cleared — clearing them would require the bridge to decide the old value is invalid, which is a staleness judgement (§1.1). The consequence is case D of §7.3 and is documented, not patched |
| Heartbeat | Continues advancing throughout, because the bridge is alive and writing. This is intentional and is what §7.3 D describes |

### 8.3 The command path never resumes itself

| Rule | Statement |
|---|---|
| N1 | The bridge publishes on an output topic **only** values it has just read from that topic's `Output/` node in the current cycle. Per slot, for all four: `/cell/conveyor/cmd_speed` from `ConveyorSpeedCommand`, and the three `/forklift/cmd/*` from their `Forklift/Output/*Ref` |
| N2 | It **never re-publishes a value it read before an outage**. A value read before a disconnect is discarded at the disconnect and is never replayed |
| N3 | It publishes **nothing** while disconnected — not the last value, not zero, not anything, on any output topic |
| N4 | After reconnect the first published value is whatever the PLC is commanding **now**. If the PLC has dropped its cycle-running flag or its teleop-active verdict (as §7.4 expects), those values are `0.0` and the machine stops. If the PLC is still commanding motion, the machine moves — because the PLC decided so, which is correct. Note that `ForkliftSteerAngleRef` **is** driven to `0.0` on a stop like the other two (`opcua-nodes.md` §10.6), so a reconnect into a stopped machine carries a centred steer: the bridge publishes whatever angle it reads, and that too is the PLC's decision |
| N5 | The bridge has no notion of "resume", no saved command state, and no shutdown hook that writes a value |

This is CLAUDE.md §9 ("after a stop the machine never resumes automatically") honoured by
construction: the bridge holds no state that *could* resume anything.

### 8.4 Residual: the belt during an outage — stated honestly

While the bridge is down, **no command can reach the plant**, and the cell's gz
`JointController` holds the last velocity it was given — so the belt keeps running at its
last commanded speed until the bridge returns and delivers the PLC's current command. The
forklift inherits the same residual on its three commanded joints, for the same reason and
with the same bound: whatever the vehicle layer last received is what the plant keeps
doing until the first read after reconnect.

| Point | Detail |
|---|---|
| Whose property is this | The **plant's**. m3-01 deliberately put no interlock, timeout or zeroing in the cell world, and the forklift plant follows that precedent; making the world stop on silence would place process logic in the simulation layer |
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
| **RB** | Restart-check read-back | start of the read | read response received | monotonic | The round trip of cycle step 0 (§8.1), recorded as a `read_rt` row so what the restart check *adds* to the 50 ms cycle is measured rather than asserted. It transports nothing, so it appears in the cost figures and in no signal figure |
| **R1** | Cycle rate | consecutive cycle starts | | monotonic | Achieved cadence; target 50 ms |
| **R2** | Per-node write rate | consecutive writes of each node | | monotonic | Achieved update rate per node |
| **R3** | Decimation ratio | samples received vs samples written, per signal | | count | Explicit evidence that discarded samples were discarded and contributed to nothing (§1.1) |

### 9.3 How it is instrumented

| Item | Decision |
|---|---|
| Where | Inside the bridge. Each slot carries its receive timestamp; the cycle records start, per-node write-response and publish timestamps |
| Overhead | Timestamps are two integer reads per sample; the instrumentation is always on. There is no "measurement mode" that behaves differently from the production path — a measurement of a different code path measures nothing |
| Recording | Per-event rows appended to CSV in memory and flushed periodically. **No aggregation inside the loop** |
| Reported statistics | For each of L1, L2, L3, L5, L6, L7, RB, R1, R2: **sample count, run duration, min, median, p95, max**. Never a mean alone. Plus: cycle overruns (> 50 ms), write errors, read errors, reconnects, session outages, `inf`/`NaN` samples, and R3 per signal. Since §8.1 gained its restart rows, also: **heartbeat read-backs, server restarts detected, inputs rewritten after a restart**, and the count of cycles in which the heartbeat was withheld by R3 — the last one is how a stalled startup is told apart from a stalled bridge |
| Per group | Every per-node figure (L1, L2, L3, L5, R2, R3) is reported **per slot**, so a run with both groups configured reports them for all of them and a cell-only run reports the seven it has. No figure is averaged across groups: a forklift slot and a conveyor slot share a cycle, not a meaning |
| Run length | Long enough for a stable p95 and to include at least one full product traverse (~9 s of belt travel at 0.15 m/s per m3-01) and at least one process-stop press. m3-04 states the achieved duration and sample counts |
| Reproducibility | The run is scripted, states the configuration (cycle period, endpoint, server kind), and reports RTF |

### 9.4 Evidence location

| File | Content |
|---|---|
| `bridge/EVIDENCE_LATENCY.md` | Dated, human-readable capture: configuration, run duration, the statistics table, the caveats of §9.5, and the raw-file reference. Follows the `sim/worlds/CELL_EVIDENCE.md` precedent |
| `bridge/evidence/latency-<stem>-<UTC second>-<pid>.csv[.gz]` | Raw per-event rows behind the table. **One file per bridge session**: the configured path is a *stem*, the recorder appends a per-session suffix and creates the file exclusively, so no start can truncate an earlier session's capture (LESSONS 2026-07-28). A capture is archived only after its writer has stopped, or the archive is labelled a snapshot of an open file |
| `bridge/EVIDENCE_SIGNAL_LOSS.md` | Dated capture of failure modes **A–D** of §7.3, delivered by m3-04 alongside the latency file. The delivered capture is test-double, in-container; its repetition against PLCSIM is item 6 of the latency file's owner-run section. Case E post-dates it and is covered by the lifecycle file below |
| `bridge/EVIDENCE_LIFECYCLE.md` | Dated capture of **session lifecycle**: an in-flight failure routed into the reconnect path, a server restart **with** and **without** a session loss (§7.3 case E, §8.1's restart rows), and the per-session evidence-file mechanics. Test-double, in-container; the harness kills and restarts its own server, which is why it may never be pointed at the commissioned endpoint (§10) |
| `bridge/EVIDENCE_CONNECT.md` | Dated capture of **session establishment**: the two-namespace browse path of §3.1 (N1–N6) and the granted-timeout / derived-keep-alive rules of §3.2 (S1–S6), each check named against the rule it tests, plus a re-run of the full loop and of a reconnect against the commissioned address space. Delivered by m3-21; test-double, in-container, and its repetition against PLCSIM is item 9 of the latency file's owner-run section |
| `bridge/evidence/connect-conformance-<YYYY-MM-DD>.csv` | Raw per-event rows behind that capture, including the keep-alive exchanges whose spacing is what proves the derivation |

The latency evidence file has **two clearly separated sections**: *test double, in-container,
agent-run* and *PLCSIM Advanced, owner-run*. The gate closes on the second. m3-04 produces
the first; the second is owner-executed (PLAN.md).

### 9.5 What cannot be measured without the real PLC — stated up front

| Not measurable in-container | Why |
|---|---|
| PLC scan-cycle contribution to L7 | The test double has no scan cycle. Its L7 is a transport floor, not the loop time |
| S7-1500 OPC UA server behaviour | Its sampling of the process image, its write handling relative to the scan, its session and monitored-item limits — a Python server reproduces none of them. **One exception, deliberate:** the double revises the session timeout away from the request as the S7-1500 does (§10), so that the client's derivation of §3.2 is testable. The revision's *shape* is imitated; its value is still not the PLC's |
| PLCSIM Advanced vs hardware timing fidelity | PLCSIM's own timing is not the hardware's; the owner's run records which was used |
| L4 (output poll phase) in absolute terms | Requires observing the PLC's internal output change, which no client can see |
| Network path | The in-container run is loopback: no switch, no VPN, no PROFINET load. Numbers are a lower bound |
| The PLC's reaction time to a stale heartbeat | A property of the PLC program, measured against `plc/demo-cell/SPEC.md`, not of the bridge |

| Establishable with the test double alone | |
|---|---|
| That every §9.9 **and** §10.10 signal traverses in both directions, with correct types, names and polarity — including that row 12 is carried **without inversion** | |
| That the decimation rule is obeyed and discarded samples are counted (R3) | |
| L1, L2, L3, L5, RB, R1, R2 as **bridge-side** figures — genuinely the bridge's own cost | |
| L6, which involves no PLC at all | |
| The startup rule (§6) **with its count taken from the configured set** — a cell-only run, a forklift-only run and a both-groups run each reaching the heartbeat on their own set, and each stalling when one of their own topics is silent | |
| That the write allowlist refuses an `Hmi` node **against a server that would have accepted the write** (§4.10, §10) | |
| The liveness behaviour (§7.3 A–D), case E and the restart repair (§8.1), and the no-auto-resume rule (§8.3) on every output slot, all as reproducible tests | |
| The connect requirements: both namespaces resolved by URI under `ServerInterfaces` (§3.1) and the keep-alive derived from a granted timeout the double revises away from the request, in either direction (§3.2). **Established** — `bridge/EVIDENCE_CONNECT.md` | |

---

## 10. Test double

| Item | Statement |
|---|---|
| What it is | A minimal OPC UA **server** that stands in for the S7-1500 on PLCSIM Advanced, exposing the `DemoCell/` address space of `opcua-nodes.md` §9 **and the `Forklift/` subtree of §10** — same BrowseNames, same folder paths, same data types, same access levels. All 33 nodes, **including the six the bridge never touches** (§4.10): a node absent from the double cannot be proven untouched |
| The HMI group: served, writable, and never written by the bridge | The five `Forklift/Hmi/` requests and `Forklift/Link/HmiHeartbeat` are served with the *Writable* standing §10.3 gives them, so a bridge write to one **would succeed**. That is the point: the conformance check proves the bridge's own allowlist refuses them, not that the server refused. Conversely `Forklift/Output/*` is served **not writable**, so the server-side half of the two-independent-enforcements arrangement is exercised too. A double that refused everything would make both checks vacuous |
| Restart fidelity | The double can be **restarted, and can revert its input values to their start values without dropping the session** — the shape of §7.3 case E. This is what makes §8.1's restart detection and repair testable at all: no other failure produces a healthy session over a reverted input image. Like the timeout revision below, the *shape* is imitated; the CPU's actual restart behaviour is still not reproduced |
| Shape it must reproduce | The **commissioned two-namespace path of §3.1**: a `ServerInterfaces` folder in namespace `http://www.siemens.com/simatic-s7-opcua` under `Objects`, with the `DemoCell` interface node and everything beneath it in `http://DemoCell` (the URI TIA derives from the interface name, ADR 0006). The double matches both URIs so the bridge's browse-by-URI resolves identically against it and against PLCSIM. It deliberately registers the two namespaces so their **indices differ from PLCSIM's**: a bridge that hardcoded either index must fail against the double |
| Negotiation fidelity | The double **grants a session timeout other than the requested one**, as the S7-1500 does (§3.2): below the request in its default configuration, and above it when configured to, because S2 and S3 must hold in both directions and the commissioned CPU's grant may land either side of the bridge's request. This is the one server behaviour it copies deliberately rather than by accident, because it is the only way to test that the keep-alive is derived from the granted value. It is scaffolding and is labelled as such |
| Why it exists | So the bridge and the loop mechanics can be verified automatically on any machine that can run the cell, and so m3-04's tests do not need the owner's TIA/PLCSIM environment |
| Invariant 4 | **Preserved.** The server role belongs to the PLC; the double merely plays that role. The bridge is a client against the double and against PLCSIM, with no code path difference and no server mode (§1) |
| What it proves | The bridge: signal traversal both ways **for every configured group**, types, polarity (including row 12 uninverted), decimation, the startup rule counted from the configured set, liveness behaviour, reconnect, the restart detection and repair of §8.1, the write allowlist's refusal of an `Hmi` node, no-auto-resume on all four output slots, the connect requirements of §3.1 and §3.2 (both namespaces resolved by URI under `ServerInterfaces`, keep-alive derived from a revised grant — recorded in `bridge/EVIDENCE_CONNECT.md`), and the bridge-side latency figures of §9.5 |
| What it does **not** prove | **The PLC program.** It runs no standard program, has no scan cycle, no process image, no interlocks, no cycle-running flag and no reset — and now also: no teleop routing, no fork-height speed cap, no soft travel limits, no obstacle latch, no monitored reset and no HMI watchdog. Nothing observed against the double is evidence for `plc/demo-cell/SPEC.md` or for the forklift function block's specification |
| It is **not** the HMI either | Serving the `Hmi/` group is not playing the HMI. The double stores those values; it runs no operator interface, forms no request and holds no session of the kind `hmi/` will. A run against the double proves nothing about ADR 0008's operator path, and any value the harness places in that group is scaffolding under the row below |
| Scaffolding is labelled | Anything the double does beyond storing values — echoing a nominated input for L7, driving `ConveyorSpeedCommand` or the three `Forklift/Output/*Ref` from a script to exercise the output paths, seeding the `Hmi/` group, or reverting its input values to simulate a restart — is **test scaffolding**, marked as such in code and in the evidence file, and is not a model of PLC or HMI behaviour |
| ADR 0004 | The ADR rejected proving the loop against a mock *only*. The double is for automated regression; each gate's exit items close against PLCSIM, owner-run |
| Operational rule | The double is never started as part of a demonstration run, and never on the same endpoint as PLCSIM. The lifecycle harness kills and restarts its own server, so it is doubly forbidden to point it at the commissioned instance — and an owner session may be live on that endpoint at any time. The evidence file always states which server produced each number |
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

**The forklift group adds no dependency and requests none.** It brings four subscriptions,
three publications and eleven more nodes, all on message types the bridge already carries
(`std_msgs/Float64`, `std_msgs/Bool`) and value types it already marshals (Real, Bool,
UInt16 — `opcua-nodes.md` §10.3). That is the point of §2.1 G4: a group is slots, not a new
kind of thing. If a future group appears to need a library, that is the signal to check
whether it is really asking for logic (§1.1).

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
| 8 | m3-01 open question 6 (stale "Navigation scenario (M3)" heading in `sim/README.md`) | **Corrected, re-opened, and closed.** `sim/` first made the heading "Navigation scenario (M5, deferred)"; **ADR 0008 D1** then shifted every gate above M3 by one, which made that M5 name the wrong gate. **ADR 0010 supersedes that shift** (accepted 2026-07-30): vehicle and navigation work is **M5**, on the in-house forklift, and RB-KAIROS is retired as the platform (D1, D2, D7) — so the number was right and the platform was not. `sim/` corrected the heading under m5r-07; see item 15 for the text now in force. **Closed** |
| 9 | Conformance of the running bridge and test double to §3.1 and §3.2 | **Closed by m3-21**, recorded in `bridge/EVIDENCE_CONNECT.md`. The client carries both URIs in config, resolves both indices by URI at every session establishment with each path element qualified by its own namespace, and reads the granted session timeout back to derive the keep-alive from it (N1–N6, S1–S6). The double serves the `ServerInterfaces` → `DemoCell` shape on indices deliberately unlike PLCSIM's and revises the request in both directions, so the rules are falsifiable rather than merely satisfied. The pre-commissioning shape — one namespace, `DemoCell` resolved directly under `Objects`, the configured session timeout used as if granted — is gone from the tree and is rejected by the config loader if a stale checkout reintroduces it. What remains is the owner's repetition of the same checks against PLCSIM: item 9 of `EVIDENCE_LATENCY.md` Section B, with the checklist at the end of `bridge/EVIDENCE_CONNECT.md` |
| 10 | The `Forklift/` browse path, its folder tree, its per-tag access rights and its node count | **Design values until read back out of TIA Portal** (`opcua-nodes.md` §10.2 step 6, §10.12 item 1). §3.1's tree marks the line as such. No gate criterion may rest on them before the owner's read-back with a client that is not the bridge, recorded with its date — the ADR 0006 discipline, and the LESSONS 2026-07-27 rule that a spec value authored without the tool that realises it is a design value, not a fact. **Open, owner, at commissioning** |
| 11 | Implementing the configured-signal-set model in `bridge/` | **Closed by m4f-06, 2026-07-29, commit `71d3b76`.** All four now hold in the shipped code: the write allowlist is **derived** from the configured groups (§4.10) and a config naming an `Hmi` node in any position is rejected outright; R3's count comes from the configured set rather than the seven cell inputs (§6.1); the reconnect refresh and the restart repair take the same count (§8.1); and the log lines are worded per configured set instead of naming `DemoCell/Input` (§9.3). Recorded in `bridge/EVIDENCE_CONNECT.md` § m4f-06 against the double, with the figures as printed: `check_forklift_slots.py` **46 checks, 46 passed**; `check_write_allowlist.py` **39 checks, 39 passed**; the restart rewrite read `11 of 11` out of the bridge's log and `11/11` out of its evidence file; a forklift-only run reaches its heartbeat on **four** inputs and touches **13** nodes. The design was the contract and the code followed it. **The commissioned `bridge.yaml` stays cell-only by choice**, because a PLCSIM run would otherwise browse for a subtree that is a design value until item 10's read-back; adding the group there is a one-file edit afterwards |
| 12 | §7.3 case D on the forklift plant — plant stopped, bridge alive, input image looks live, and **no `ForkliftDriveFault` node exists** to carry the verdict | **Open, owner decision then the PLC forklift FB specification.** Mirrors `opcua-nodes.md` §10.12 item 3 exactly and is not restated as a second request. Nothing here is the bridge's to fix: detecting a frozen plant needs a timer and a threshold, which §1.1 places in the PLC. The M3 cell closed the same item with `ConveyorDriveFault` (item 4); the forklift has no equivalent node yet |
| 13 | `bridge/EVIDENCE_LATENCY.md`'s standing request: "§8.1's *Detection* row … the design document does not carry it. It needs a row, and the bridge's own log cites §8.1 for a rule that is not yet there" | **Resolved here**: §8.1 gains *Restart detection*, *Restart repair* and *Restart residual*, §7.3 gains case E, §2's cycle description gains step 0, §4.3 gains row 9r, and §9.2 gains RB. The log line's citation now resolves to a rule that exists. The requesting file is in `bridge/` and cannot be edited from here — and **`bridge/` marked its own request `SATISFIED, 2026-07-29`** in `EVIDENCE_LATENCY.md` Section B item 1 (m4f-06, `71d3b76`), confirming that the bridge's "§8.1" log citation now resolves and that the exact-inequality test the design words is what the code does. **Both halves closed.** The same note requested **one correction back** — that §8.1's *Restart residual* row understated the residual — which is made in §8.1 above and is the reason this item closes with a corrected row rather than the row it was resolved with |
| 14 | Statements elsewhere that were true of a one-group interface and are now scope-stale | **Bridge half confirmed, 2026-07-29** (`bridge/EVIDENCE_LIFECYCLE.md` §1.2, m4f-06): with the forklift group configured, the bridge's write set is the `Input/` nodes of the configured groups **plus its own heartbeat**, so `BridgeHeartbeat` remains the only node outside an `Input/` folder that the bridge writes — the sentence stands rather than merely staying defensible. It also remains a valid *witness*, because the second client's counter is `Forklift/Link/HmiHeartbeat`, a node the bridge never touches, and the two writable sets are disjoint by BrowseName prefix (`opcua-nodes.md` §10.1). What that confirmation did **not** establish is how wide the witness's blind spot is — measured since, and now carried by §8.1's *Restart residual* row. **The `plc/` half stays open**: `plc/demo-cell/SPEC.md` §4.3's "Nothing else goes into the interface" was true of the M3 cell and is no longer true of the interface. `plc/`'s to correct; requested, not edited here |
| 15 | `sim/README.md`'s navigation-scenario heading | **Closed by m5r-07, 2026-07-30.** The heading now reads `## Navigation scenario (RB-KAIROS, parked — resumes at M5 on the forklift)`. This item was raised against the ADR 0008 D1 shift, which made "M5, deferred" name the wrong gate; **ADR 0010 supersedes that shift** and puts vehicle and navigation work back at **M5**, on the forklift, with RB-KAIROS retired — so what was stale was the platform, not the number. Raised from item 8, which this document owns the history of but not the file |
