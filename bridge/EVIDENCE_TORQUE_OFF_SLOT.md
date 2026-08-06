# EVIDENCE — the torque-off demand slot, and what it does at the plant

**What this file is.** The dated capture of the first runs of the bridge slot
that carries the F-program's SS1 second-stage demand to the vehicle —
`DemoCell/Forklift/Safety/TorqueOffDemand` → `/forklift/safety/torque_off_demand`
(`opcua-nodes.md` §11, rules **SD1–SD10** in §11.2b) — and of the consumer that
had carried that subscription since m5-50 with **no publisher at all**:
`publisher count 0`, measured on the vehicle side in `docs/VALIDATION-M5.md`
while the vehicle drove 19 s at 1.000 m/s with the demand standing.

Written **as each observation landed**, run by run.

---

## 0. Environment, and what qualifies every figure

| Item | Value |
|---|---|
| Date | **2026-08-06**, 20:07–20:16 UTC |
| Server | **The test double**, `bridge/test_double/plc_test_double.py`, extended in this same round to serve the six `Forklift/Safety/` mirrors. **Not a PLC and not a model of one** |
| Controller | **The CPU was read but never written, and no figure below was produced by it.** The leaf does not exist on it yet — see §1 |
| Bridge | The real one, `bridge/run_bridge.py --config bridge/config/bridge-double-m5.yaml`, started as a child process by the harness. Nothing in `amr_bridge/` stubbed or special-cased |
| Consumer | The real `agv/forklift/scripts/sto_contactor.py`, started from the committed `agv/forklift/config.yaml`. Unmodified by this brief — nothing in `agv/` was written |
| Host | WSL2 on the owner's Windows machine, Ubuntu 24.04, ROS 2 Jazzy, `rmw_fastrtps_cpp`; `~/amr-bridge-venv` (`asyncua==2.0.1`) |
| Isolation | `ROS_DOMAIN_ID=93` throughout. A second session held domain 61 with `GZ_PARTITION=m561a` and was running Gazebo the whole time; the two never met, and **this session started no simulator** (LESSONS 2026-07-30) |
| Machine state | `load average 2.51 1.84 1.18` at the start, recorded rather than assumed — the other session's simulator is in that number |
| Harness | `bridge/tools/check_torque_off_slot.py`, new in this round. It owns the double's and the bridge's lifecycles, publishes the input sources and the actuator command, and records the three observables |

**What no figure here is.** Not a safety figure. The consumer is process-side
Python **simulating the effect on the plant** of a hardwired onboard inhibit this
plant does not have (§11.2b **SD9**, ADR 0011 D5, invariant 1). **No PL,
Category, SIL or PFH is claimed, achieved or implied anywhere in this file, and
no stopping time or distance is measured, derived or quoted.** "Torque removed"
means exactly: *the simulated plant received no actuator command and a standing
zero at the traction terminal*.

**And no simulator ran.** What is measured is **delivery to the plant's terminal
topics** — the inputs of `model.sdf`'s joint controllers — not wheel rotation.
No sentence in this file says the vehicle moved or did not move.

---

## 1. The controller half is NOT built yet, and this is what was measured

`bridge/tools/probe_server_paths.py`, read-only, against the commissioned
PLCSIM Advanced instance `opc.tcp://192.168.53.1:4840`, **2026-08-06T21:58Z**:

```
DemoCell/Forklift/: ['Envelope', 'Hmi', 'Input', 'Link', 'Mode', 'Output',
                     'ProcessStop', 'Safety', 'Status', 'Vehicle', 'Warning']
  Forklift/Safety/: ['EStopDemand', 'SafetyResetFault',
                     'SafetyResetRequired', 'ZoneStopDemand']
```

**Four mirrors, not six.** `TorqueOffDemand` and `SpeedMonitorDemand` are created
by `plc/forklift/TIA-FIX-PROCEDURE.md` chunks AD–AF, which the owner had not yet
applied — the session is tomorrow morning. So:

> **Every run in this file was taken against the test double. Not one of them was
> taken against the CPU, and no claim below may be read as a live-controller
> claim.** What §11.6 calls the design value stays a design value until the leaf
> is read back out of the tool.

What the probe *does* establish about the live controller, and it is the reason
the committed `bridge/config/bridge.yaml` carries the group today: the folder is
there, the four existing mirrors read back with their documented types and no
`_1` suffix, and the missing leaf answers `BadNoMatch` — the status §6 below
exercises.

---

## 2. What was built

| Piece | What it is |
|---|---|
| `amr_bridge/config.py` `SAFETY_GROUP` | one **output** slot — the bridge READS `Forklift/Safety/TorqueOffDemand` and republishes it. **No inputs**, so the derived write allowlist gains zero keys: §11.4 **MR1** by construction |
| `SignalGroup.optional_nodes` | §11.6's rule that *no client's connect may fail over this group*. Addressing only; it never produces a value |
| `opcua_side._resolve_nodes` | an absent optional node is logged once by name and left unresolved; only `BadNoMatch` / `BadNodeIdUnknown` / `BadNotFound` count as absence, and only for a key its group declared optional |
| `config/bridge.yaml`, `config/bridge-double-m5.yaml` | the group, its one node and its one topic |
| `test_double/plc_test_double.py` | the six §11 mirrors with §11.6's start values, **read-only to every client**, served in three real shapes: `six`, `four` (the controller as measured above) and `none` |
| `tools/check_torque_off_slot.py` | the harness this file records |
| `tools/check_write_allowlist.py` | four `Forklift/Safety/` rows added to the server-side refusal list |

**No `StaleAssert`, no freshness window, no synthesised value.** That is
§11.2b **SD5**, and it is the deliberate opposite of the warning slot one section
over in the same file. The reason is written at `SAFETY_GROUP`; the other
behaviour is in no line of the package.

---

## 3. Run r1 — the whole chain, one run, 25 checks

`check_torque_off_slot.py --tag m562-r1`, 2026-08-06T20:07:43Z.
Command value **5.5 rad/s** in every phase — one value for the run, so the
positive control and the refusal differ in the demand and in nothing else. The
brake is `0.0` (`agv/forklift/config.yaml` `sto.brake_traction_radps`), so a
terminal message carrying 5.5 can only be a forwarded command.

| Phase | What was done | What was measured |
|---|---|---|
| 0 | chain up, double in the `six` shape | **publisher count on `/forklift/safety/torque_off_demand` = 1.** The condition VALIDATION-M5 measured as 0 is closed |
| 1 | nothing — the node's **start value** is `TRUE` (§11.6) | demand `TRUE` reached the vehicle; contactor latched OPEN; **n=20 commands, 0 reached the traction terminal**; 50 terminal messages in the window, **all 0.0** — the terminal is *driven* to the brake, not merely quiet |
| 2 | **POSITIVE CONTROL** — hand writes `TorqueOffDemand=false` server-side | demand `FALSE` observed; **n=20 commands, 20 reached the terminal** |
| 3 | hand writes `true` | **n=20 commands, 0 reached the terminal**, against the 20/20 control above |
| 4 | hand writes `false`, then waits 1.5 s sending nothing | **0 forwarded** in the quiet window; a fresh command then moves 20/20. Clearing a latch energizes nothing (**SD4**) |
| 5 | **the bridge is killed mid-run**, demand absent | publisher count **0**; **20/20 commands still reached the terminal**; the latch stayed CLOSED (**SD5**) |
| 6 | double restarted in the **`four`** shape, bridge restarted | session established; absence logged by name; **0 messages** on the demand topic in 3 s; **20/20** commands reached the terminal |
| 7 | inspection of the run | no `WriteNotPermitted`; allowlist 8 keys = 7 inputs + 1 heartbeat; `SpeedMonitorDemand` in no node table and no topic table |

**25 checks, 25 passed.** Run r2 (`--tag m562-r2`, 20:15:15Z) repeated the whole
sequence: **25/25**. **n = 2 runs**, and every count above reproduced exactly.

### 3.1 The positive control, stated as the rule requires

*The vehicle did not move* is not evidence of anything once a component can make
the plant deaf: a correct refusal, a latched contactor and a contactor that was
never started produce the identical observation (LESSONS 2026-08-06, §11.2b's
own closing paragraph). So:

| | phase 2 (control) | phase 3 (demand) |
|---|---|---|
| command value | 5.5 | 5.5 |
| commands sent | 20 | 20 |
| reached the terminal | **20** | **0** |
| difference between the two phases | — | **the demand, and nothing else** |

Same value, same publisher, same subscriber, same process, **same run**, 2.6 s
apart. Both repeated in r2.

### 3.2 The server's own view, which cannot echo the client

`--observe-csv`, written by the double itself (80 rows, 0.2 s cadence):

| Column | Sequence over r1 |
|---|---|
| `TorqueOffDemand` | `True → False → True → False` — the boot value and the three hand writes |
| `SpeedMonitorDemand` | `False`, **0 transitions** — no slot, no topic, no consumer (**SD1**) |
| `EStopDemand` | `True`, **0 transitions** — served, never touched |
| `ForkliftWarningFieldOccupied` | `True → False` — see §7 |

### 3.3 Demand observed → contactor's applied readback

Both are subscriptions of the harness process, timestamped on one monotonic
clock at callback entry, so the interval is a difference between **two
observations by one observer** — not a plant reaction time, and **not a stopping
figure of any kind**.

| Run | transitions | values |
|---|---|---|
| r1 | 4 | 9.0, 7.7, 8.1, 5.0 ms |
| r2 | 4 | 12.9, 10.4, 9.8, 6.1 ms |

**n = 8 across two runs, on a machine simultaneously running another session's
simulator.** These are draws, not a bound (LESSONS 2026-08-05): nothing in this
project may quote them as a specification, and no gate criterion rests on them.

### 3.4 The consumer said it too, in its own log

```
TORQUE OFF: latch OPEN. Traction terminal driven to 0.000 rad/s and held ...
TORQUE RESTORED: latch CLOSED after 20 refused commands. Nothing moves until
a FRESH command arrives - the value standing at the traction terminal is the brake's.
```

Twice each, in both runs. The refusal count is the consumer's own arithmetic and
it agrees with the harness's independent count of the terminal topic.

---

## 4. SD5, produced deliberately rather than argued

Phase 5 kills the bridge with the demand **absent**. The topic then has **no
publisher at all** — the exact condition VALIDATION-M5 recorded as a defect, here
produced on purpose — and the vehicle **keeps driving**: 20/20 commands reach the
terminal, in both runs.

That is the ruling, and it is the deliberate opposite of the warning slot's
silence-implies-`TRUE`: loss of supervision is a **degraded mode, not a safety
event** (invariant 2); the controlled stop it calls for already exists one layer
up in the envelope gate's freshness rule (§12.4 **E5**); and torque removal is
**asserted, never inferred**. The cost is stated rather than hidden: after this
slot exists, a silent link leaves the vehicle drivable, and the layer that stops
it in that case is the envelope, not this topic.

---

## 5. The boot truth, which will be visible on stage

`TorqueOffDemand`'s start value is `TRUE` (§11.6), because its F-side source is
`TRUE` at every CPU start. Phase 1 is that value arriving at the plant: **the
vehicle boots torque-off and stays deaf until a monitored reset clears the boot
latches inside the F-program**, which no client can reach by any route (**MR3**).
Nothing in this round weakens it, and it is intended (**SD6**) — a demonstration
that begins with a vehicle refusing commands is the no-auto-resume rule arriving
at the plant, not a fault.

---

## 6. The leaf absent from the server (§11.6)

Against the double in the **`four`** shape — the controller as measured in §1:

```
WARNING bridge.opcua TorqueOffDemand is NOT on this server (BadNoMatch) —
declared optional by opcua-nodes.md §11.6, so the connect stands. It will be
read in no cycle and published on no topic: no message, no synthesised value,
and no message is not torque-off (§11.2b SD5).
Path: 5:ServerInterfaces/6:DemoCell/6:Forklift/6:Safety/6:TorqueOffDemand
INFO  bridge.opcua all 21 resolved node DataTypes match the node model ...;
      1 optional node(s) absent from this server: TorqueOffDemand
INFO  bridge.opcua session established, 21 nodes resolved
```

21 nodes instead of 22, the other three groups unaffected, **0 messages** on the
demand topic, and the vehicle still drives. When the owner applies chunks AD–AF,
the **next session** resolves the leaf and carries it — no edit to any config
file, and nothing to remember under time pressure at the tool.

---

## 7. `ForkliftWarningFieldOccupied` read `True` all session — the answer

m5-61 handed this to `bridge` + `interface` as *"the standard-side node fed by
the ROS-topic carrier that still does not exist"*. **The carrier does exist, and
this round observed it working**: in §3.2 the double's own log shows the node
going `True → False` as the bridge carried the field evaluation's verdict.

What was actually read, live, on the controller at **2026-08-06T20:14:29Z and
again at 20:14:33Z**, four seconds apart:

| Node | Reading | Reading 4 s later |
|---|---|---|
| `Link/BridgeHeartbeat` | 53048 | **53048** |
| `Forklift/Warning/ForkliftWarningFieldOccupied` | `True` | `True` |
| `Forklift/Input/ForkliftObstacleInStopZone` | `True` | `True` |

and `pgrep` for `run_bridge` / `amr_bridge.main` on the machine: **nothing**.

**The heartbeat is frozen and no bridge process exists, so no client has written
any `Input/`-class node on that CPU for the whole session.** Every one of them is
sitting at its DB start value, and the warning node's start value is `TRUE`
exactly as `ForkliftObstacleInStopZone`'s is — both non-permissive, both doing
the job §13 and §10.9 gave them: **"not yet written" is not "clear."**

**So it is not a carrier gap, and it is not `interface`'s to rule.** The three
causes of a `TRUE` on that node are (a) the field really is occupied, (b) the
producer went silent and the bridge asserted `TRUE` (§13.2 W1), (c) **no bridge
ran at all**. This session was (c). The item that remains is therefore neither a
missing node nor a missing rule but two other things, and they are named in the
report rather than fixed here:

1. **run composition** — a session that expects that node to mean anything must
   include the bridge with the `warning` group, which m5-61's stack (field
   evaluation + stand-in writer + Gazebo, all on the 45015 link) did not;
2. **a display rule, `hmi/`'s** — any lamp fed by that node renders the **age**
   of what it has, never the value alone (LESSONS 2026-08-06). The instrument
   that separates cause (c) from (a) and (b) is `Link/BridgeHeartbeat`
   advancing.

One fact for the owner's TIA session, reported and not acted on: **`Link/
BridgeLinkOk` is not addressable on the controller in force** — `BadNoMatch`,
same probe, §1. That is the PLC's own verdict on bridge liveness, and without it
the only bridge-liveness instrument any client has is the raw heartbeat counter.
Whether the forklift build should publish a link verdict of its own is `plc/` and
`interface`'s to rule, not this file's.

---

## 8. Files this round wrote into `bridge/evidence/`

Per run, and every name carries **the run that produced it** so a repeat can
never overwrite the run it is compared against (LESSONS 2026-08-06):

| File | What |
|---|---|
| `m562-witness-<run>.csv.gz` | the harness's own record: every demand, applied and terminal message with its monotonic timestamp |
| `m562-double-observe-<run>-*.csv.gz` | the **server's** view, written by the double |
| `m562-latency-<run>-*.csv.gz`, `m562-latency-four-<run>-*.csv.gz` | the bridge's ordinary evidence CSV for each of the two sessions of the run |
| `m562-bridge-<run>.log`, `m562-bridge-four-<run>.log` | the bridge's console for each session |
| `m562-double-<run>.log`, `m562-double-four-<run>.log` | the double's console, including the shape it served |
| `m562-contactor-<run>.log` | the consumer's own console |
| `m562-demand-<run>.txt` | the hand-written demand file — the whole of the stimulus |
| `m562-allowlist-m562-r1.log` | `check_write_allowlist.py`: **50 checks, 50 passed**, including the four `Forklift/Safety/` rows refused `BadUserAccessDenied` by the server and `WriteNotPermitted` by the bridge, independently |

Every process was stopped before its file was archived, and the archives were
verified with `gzip -t` (LESSONS 2026-07-28: never compress a file under a live
writer).
