# EVIDENCE — the forklift repoint and the envelope group, across the real bridge

**What this file is.** The dated capture of the first run in which the
committed bridge configuration addressed the **forklift** signal group on the
commissioned CPU, and of the first run in which a **PLC-formed autonomy
envelope** crossed the bridge to the vehicle's own envelope gate. Until now the
gate had only ever met a topic double (`agv/forklift/EVIDENCE_ENVELOPE.md`,
m5-11) and `bridge/config/bridge.yaml` was deliberately cell-only.

Written **as the observations landed**, section by section, not assembled
afterwards.

---

## 0. Environment, and what qualifies every figure

| Item | Value |
|---|---|
| Date | **2026-08-06** |
| Controller | PLCSIM Advanced instance `safecell3` at `192.168.53.1`, project `safe_amr`, CPU 1513F-1 PN, fw V3.1 — the build of `plc/forklift/TIA-BUILD-PROCEDURE.md` chunks 0–O, downloaded 2026-08-05. **Nothing in TIA was opened, changed, compiled or downloaded for this work** |
| Bridge host | **WSL2 on the owner's Windows machine**, Ubuntu 24.04, 20 cores, ROS 2 Jazzy, `rmw_fastrtps_cpp`; the bridge runs on `~/amr-bridge-venv` (`asyncua==2.0.1`) |
| Simulator | `gz sim` 8.11.0, headless, software rasterised, `sim/launch/warehouse_bringup.launch.py` at `x=-4.5 y=7.0 yaw=0.0` |
| Isolation | `ROS_DOMAIN_ID=57` **and** `GZ_PARTITION=m544`, both, always (LESSONS 2026-07-27) |
| Machine load before the timed runs | idle: `uptime` load average `0.08 0.42 1.11`, no `gz`, no ROS 2 and no bridge process running (`pgrep` empty). One simulator at a time throughout (LESSONS 2026-07-30) |
| Independent witness | `bridge/tools/probe_server_paths.py`, an `asyncua` client on the **Windows** host — a different machine-side process, a different interpreter and a different session from the bridge, so nothing it reports is the bridge echoing itself |

**What no figure here is.** Not a safety figure. The envelope, the mode, the
process stop and the vehicle's report are **process data** (`opcua-nodes.md`
§12.1, ADR 0011 D5); loss of any of these links is a **degraded mode, not a
safety event** (invariant 2). No PL, SIL, Category or PFH is claimed for
anything in this file.

---

## 1. What the server actually publishes — established before anything was pointed at it

`bridge/tools/probe_server_paths.py`, run **2026-08-06 05:38 UTC** against
`opc.tcp://192.168.53.1:4840`. Two questions kept apart, because they are
different claims (LESSONS 2026-08-05): **advertised** (the name appears in a
browse of its parent) and **addressable** (the path the bridge will use returns
a value rather than an error).

Namespace array as read, 5 entries; both URIs resolved **by URI**, never by
index (`bridge-design.md` §3.1 N2):

```
[3] http://www.siemens.com/simatic-s7-opcua   -> ServerInterfaces
[4] http://DemoCell                           -> the interface node, ns=4;i=1
```

Advertised, one level at a time:

```
DemoCell/            : ['Forklift', 'Link']
DemoCell/Link/       : ['BridgeHeartbeat']
DemoCell/Forklift/   : ['Envelope', 'Hmi', 'Input', 'Link', 'Mode', 'Output',
                        'ProcessStop', 'Safety', 'Status', 'Vehicle']   (ten)
Forklift/Envelope/   : ForkliftEquipmentPermit, ForkliftMotionEnable, ForkliftSpeedCeiling
Forklift/Mode/       : ForkliftDriveModeActive, HmiDriveModeRequest
Forklift/Vehicle/    : ForkliftVehicleHeartbeat, ForkliftVehicleModeApplied
Forklift/ProcessStop/: ForkliftProcessStopActive, HmiProcessStopRequest
```

**Not one browse name carries a `_1` suffix** — swept by reading every child of
every folder, not by trusting the build log (LESSONS 2026-07-30).

### 1.1 The finding that changed the shape of the repoint

**The cell group cannot be carried against this CPU at all.** The `DemoCell`
interface on project `safe_amr` publishes `Forklift/` and
`Link/BridgeHeartbeat` **and nothing else**. Addressed directly — the strong
form of the claim, not a failed browse (LESSONS 2026-08-05) — every M3 cell
node answers with an error:

| Path | Result |
|---|---|
| `Input/ConveyorBeltPosition` | `BadNoMatch` |
| `Output/ConveyorSpeedCommand` | `BadNoMatch` |
| `Status/CellCycleRunning` | `BadNoMatch` |
| `Link/BridgeLinkOk` | `BadNoMatch` |

So the deferred TODO item — "point `bridge/config/bridge.yaml` at the Forklift
groups" — is **not an addition to the cell group but a replacement of it**. A
config carrying `cell` here fails at node resolution, which is the intended
failure mode (§3.1 N4) and not a configuration worth keeping. `groups:` in the
committed file now reads `["forklift"]` (and, from §4 below, the envelope group
beside it), and the cell group's node and topic tables left the file with the
group rather than staying as a commented-out block nothing checks.

**`Link/BridgeLinkOk` is absent, and that is the one consequence to carry
forward.** The bridge's own liveness *verdict* — the PLC's answer to "is the
bridge alive" — is a §9 node this project's forklift function block computes
internally (`#bridgeLinkOk`, `FB_ForkliftTeleop.scl`) but does **not** publish
on this interface. The bridge does not need it (it is a logged diagnostic of
the *cell* group, `bridge-design.md` §4.4), and its absence changes no rule
here; it does mean an observer of this CPU cannot read the PLC's link verdict
from a node, and must infer it from the behaviour it gates. Requested, not
invented — see the report's REQUESTS.

### 1.2 Every path the bridge would address, read back

All twelve §10 paths and all seven §12 paths resolved and read, with the
DataType the node model documents. Values at the moment of the probe were the
cold ones the build recorded (`ForkliftResetRequired` `TRUE`,
`ForkliftProcessStopActive` `TRUE`, mode `0`, enable `FALSE`, ceiling `0.0`,
permit `FALSE`) — the §14.9 cold-start signature, unchanged since 2026-08-05
and **not disturbed by this probe, which writes nothing**.

---

## 2. Stage 1 — the committed config carries the forklift group against the CPU

**Run `s1`**, 2026-08-06 07:50:30 local. Stack: warehouse bringup →
`agv/forklift/launch/envelope.launch.py io:=true` →
`agv/forklift/scripts/obstacle_zone.py` → the bridge on
`bridge/config/bridge.yaml`. Evidence CSV
`bridge/evidence/latency-2026-08-06-m544-s1-20260806T055030Z-pid151891.csv.gz`
(one file per session, unique name per start — LESSONS 2026-07-28; gzipped
after the session had ended and the process was gone, never under a live
writer — LESSONS 2026-07-29).

Quoted as the bridge printed them:

```
configured signal set: forklift — forklift 4in/3out/5diag (opcua-nodes.md §10);
  4 input slots, 3 output slots, 5 diagnostics, 13 nodes touched,
  write allowlist 5 keys
session timeout: requested 10000 ms, granted 10000 ms — granted as requested
keep-alive interval 3.333 s = granted 10000 ms / 3 (§3.2 S3)
namespace http://www.siemens.com/simatic-s7-opcua (server_interfaces) resolved to index 3
namespace http://DemoCell (interface) resolved to index 4
browse path: Objects/3:ServerInterfaces/4:DemoCell
all 13 node DataTypes match the node model (opcua-nodes.md §10)
session established, 13 nodes resolved for group(s) forklift
input image rewritten after cache invalidation: 0 of 4 configured input nodes ();
  no real sample yet for ForkliftForkHeight, ForkliftLinearSpeed,
  ForkliftObstacleInStopZone, ForkliftObstacleMinDistance (R1)
heartbeat withheld: 4 of 4 configured input(s) carry no real sample yet (startup rule R3)
heartbeat withheld: 2 of 4 configured input(s) carry no real sample yet —
  ForkliftObstacleInStopZone, ForkliftObstacleMinDistance (startup rule R3)
startup rule R3 satisfied: all 4 input nodes of the configured set (forklift)
  carry a real plant sample; heartbeat begins advancing at 1
```

**R3 was observed doing its job rather than asserted**: the heartbeat was
withheld for 2.9 s — first over all four inputs, then over the two whose
publisher (`obstacle_zone.py`) is slower to produce a first sample — and only
then began advancing. R1 was observed in the same window: the restart-repair
rewrite wrote **0 of 4** because no slot yet held a real sample, and named the
four rather than inventing values for them.

**Confirmed from outside the bridge.** A second probe run at 07:51, from the
Windows host on its own session:

| Node | Read back | What it is |
|---|---|---|
| `Link/BridgeHeartbeat` | `457` | advancing; the probe cannot write it, so this is the bridge's counter |
| `Forklift/Input/ForkliftObstacleMinDistance` | `5.145787715911865` | a live lidar-derived value from the warehouse world |
| `Forklift/Input/ForkliftForkHeight` | `-5.0139e-14` | the carriage at rest, carried **unrounded** — the narrowing is the only numeric operation permitted (§1.1) |
| `Forklift/Input/ForkliftObstacleInStopZone` | `False` | carried uninverted (§4.7 row 12) |
| `Forklift/Status/ForkliftResetRequired` | `True` | the PLC's own verdict, read as a diagnostic and applied to nothing |

Stage 1 stands: **the committed configuration, not a hand-edited copy, carries
the forklift group to the commissioned CPU.**

### 2.1 One untracked artefact found on the way, recorded rather than adopted

`~/amr-live-forklift.yaml` on the WSL host is a `sed`-rewritten copy of
`bridge/config/rehearsal-forklift.yaml` with the endpoint swapped to the live
CPU, generated by `~/amr-demo-start.sh` at every demo start. It works, but it
carries the rehearsal file's own comments verbatim — including "It is the
**rehearsal** configuration … points at the PLC **logic double**" and
"`bridge/config/bridge.yaml` stays cell-only" — over a file that points at
PLCSIM Advanced. Both sentences are now false of that file and of this
repository. It is outside `bridge/` and outside the repository; the report asks
for the launcher to be pointed at the committed config instead.

---

## 3. Stage 2 — the §12 envelope group crosses the bridge

**Run `s2`**, 2026-08-06 07:56:35 → 08:12:22 local, 947.0 s, one session, no
reconnect. Same stack, `bridge/config/bridge.yaml` now declaring
`groups: ["forklift", "envelope"]`. Evidence CSV
`bridge/evidence/latency-2026-08-06-m544-s2-20260806T055635Z-pid151999.csv.gz`
(archived **after** the writer had exited — LESSONS 2026-07-28/29).

As the bridge printed it:

```
configured signal set: forklift+envelope — forklift 4in/3out/5diag (opcua-nodes.md §10),
  envelope 2in/4out/1diag (opcua-nodes.md §12); 6 input slots, 7 output slots,
  6 diagnostics, 20 nodes touched, write allowlist 7 keys
all 20 node DataTypes match the node model (opcua-nodes.md §10, opcua-nodes.md §12)
session established, 20 nodes resolved for group(s) forklift+envelope
startup rule R3 satisfied: all 6 input nodes of the configured set (forklift+envelope)
  carry a real plant sample; heartbeat begins advancing at 1
```

**R3 counted six**, not four and not a literal — the rule took its "every" from
the configured set, as §6.1 requires, and the two `Forklift/Vehicle/` slots held
the heartbeat back until the gate had published each of them once.

**The write allowlist grew to seven keys and to nothing else**: the four
`Forklift/Input/` nodes, the two `Forklift/Vehicle/` nodes, and the heartbeat.
Neither `Forklift/Envelope/*` nor `Forklift/Mode/*` is in it, in any
configuration, and the CPU independently refuses an envelope write
(`BadNotWritable`, read back 2026-08-05) — the two independent enforcements
§12.2 describes, neither depending on the other.

**The first topic-carried `UInt16` in this project's history.** The bridge has
generated a `UInt16` since m3-04 — its own heartbeat — and had never carried one
from or to a topic. Three now travel: `/forklift/mode/in_force` out,
`/forklift/mode/applied` and `/forklift/vehicle/heartbeat` in. No dependency was
added (§11, §2.1 G4).

**Witnessed from the Windows host**, on its own session, while the bridge ran:

```
t=0  VehicleHeartbeat= 10093  ModeApplied=0  BridgeHeartbeat=572
t=1  VehicleHeartbeat= 10113  ModeApplied=0  BridgeHeartbeat=592
t=2  VehicleHeartbeat= 10133  ModeApplied=0  BridgeHeartbeat=612
t=3  VehicleHeartbeat= 10153  ModeApplied=0  BridgeHeartbeat=632
```

Twenty increments per second on both counters, on nodes the witness cannot
write. This is what `#vehicleAlive` in `FB_ForkliftTeleop.scl` has been waiting
for since the build: **the third watched party is answering for the first
time.**

## 4. The envelope, formed by the PLC, acting on the vehicle

Three observations, in the order they were taken. The vehicle-side capture is
`bridge/tools/observe_envelope_chain.py`, a subscriber-only witness; times are
`CLOCK_MONOTONIC` on the bridge host, differenced only against themselves
(§9.1 C1/C2).

**How the cell was brought to a permissive state**, listed so the run is
reproducible and so nothing in it is mistaken for something the bridge did: the
stand-in writer (`bridge/standin_writer/`, Windows, PLCSIM API, **not** OPC UA)
closed the two simulated circuits and pulsed the monitored reset, clearing
`EStopDemand` and `ZoneStopDemand`; the commissioning HMI (`hmi/`, its own OPC
UA session) released the process stop, tapped the monitored reset, and selected
`Autonomous`. **Every one of those is a client action on a PLC input. The
envelope itself is formed only in the standard program.**

### 4.1 Observation 1 — the envelope goes permissive and the vehicle drives

`bridge/evidence/envelope-chain-2026-08-06-r1.csv.gz`, transitions as recorded:

```
t=  1.4948  equipment_permit   -> 1
t= 12.5919  mode_in_force      0 -> 2
t= 12.5925  motion_enable      0 -> 1
t= 12.5937  speed_ceiling      0.0 -> 0.6000000238418579
t= 12.6382  mode_applied       0 -> 2
```

Three elements and the mode arrived on the vehicle **within 1.8 ms of each
other** — one bridge cycle, one poll phase, as §4.8 and §12.4's cadence note
require. The gate adopted the law **44.5 ms** later and the bridge carried that
readback back to the CPU, where `ForkliftVehicleModeApplied` read `2`. That is
the whole ADR 0014 D5.3 round trip, closed for the first time.

The ceiling reads `0.6000000238418579` on the vehicle side: the PLC's `Real`
`0.6`, widened to `float64`. **The bridge did not round it to a nicer value**
(§1.1), and the reader can see the narrowing that produced it.

The vehicle then drove — command source `ros2 topic pub` on `/cmd_vel`, through
the deployed `velocity_smoother → envelope gate → cmd_vel_to_tricycle →
forklift_io` chain. Peak `/cmd_vel_gated` 0.1018 m/s, ground truth
`/forklift/odom` 0.0978 m/s.

> **This run does not exercise the ceiling clamp.** The closed-loop smoother
> never produced more than 0.1018 m/s from rest against a 0.60 m/s ceiling, so
> the ceiling was never the binding constraint. The clamp is measured in
> `agv/forklift/EVIDENCE_ENVELOPE.md` §5 against a topic double and is **not**
> re-established here. Said plainly, rather than implied by a permissive-looking
> run.

### 4.2 Observation 2 — the PLC withdraws the envelope and the vehicle stops

**The withdrawal was not the one that was about to be triggered, and it is the
better observation for it.** While the vehicle drove, its own lidar protective
field saw the warehouse structure. Everything that followed was decided in the
standard program, and it is timed across the real seam:

| Event | Where it is recorded | Time |
|---|---|---|
| Bridge writes `ForkliftObstacleInStopZone` `TRUE`, server acknowledges | `L2` row, bridge CSV | monotonic `256713728908028` |
| Bridge reads `ForkliftMotionEnable` `FALSE` | `read_rt` row, bridge CSV | monotonic `256713770491175` |
| **PLC round trip: field bit acknowledged → envelope withdrawn and read back** | | **41.6 ms** |
| `motion_enable` `1 → 0` seen on the vehicle | witness r1 | `t = 125.1405` |
| `speed_ceiling` `0.600 → 0.0` seen on the vehicle | witness r1 | `t = 125.1411` |
| `/cmd_vel_gated` reaches exactly `0.0` | witness r1 | **+162.5 ms** |
| `/forklift/odom` \|vx\| < 0.005 m/s | witness r1 | **+221.3 ms** |

`/cmd_vel_gated` immediately before the withdrawal was 0.1018 m/s; the gate's
own ramp at 0.50 m/s² accounts for 0.204 s to zero from that speed, and the
measured 162.5 ms to the first exact zero sits inside it. **The gate published
its terminal value and only then held zero** — it did not fall silent early,
which is the 2026-08-04 lesson honoured in the deployed node.

The PLC's own verdict crossed in the same run: `ForkliftObstacleStopActive` read
`True` in the bridge's 1 Hz diagnostics at 08:02:36.875, **with
`ForkliftProcessStopActive` still `False` in the same line** — which is what
attributes this stop to the obstacle latch and not to the operator action that
came ten seconds later.

**Then the operator's process stop, on the same run.** A `POST /control
{"process_stop": true}` to the HMI at 08:02:46 latched
`ForkliftProcessStopActive`, and the vehicle saw `equipment_permit 1 → 0` at
`t = 134.5948` — a **second, independently formed** envelope element withdrawn
for a **different cause**, carried by the same six slots. The enable and the
ceiling were already withdrawn, so the machine did not move; the permit's fall
is the visible half of `EQ2` (`NOT ProcessStopLatch`) in
`FB_ForkliftTeleop.scl`.

**And nothing resumed by itself.** With the field clear again
(`ForkliftObstacleMinDistance` 1.2156 m, `ForkliftObstacleInStopZone` `False`)
`ForkliftObstacleStopActive` stayed `True`: a latch is not cleared by its cause
going away. Recovery took the sequence CLAUDE.md §9 and §12.3 specify — release
the process stop, tap the monitored reset, **leave the mode and select it
again** — and only then did `motion_enable` return. A reset alone did not
re-enter `Autonomous`; the mode had to be re-selected, which is the affirmative
operator action §12.3 makes the entry edge.

### 4.3 Observation 3 — the link drops and the vehicle stops on its own watchdog

`bridge/evidence/envelope-chain-2026-08-06-r4-linkloss.csv.gz`. `SIGTERM` to the
bridge at wall `1785996742.6355`; the bridge closed its session cleanly and
**wrote no farewell value and zeroed nothing**, as §8.3 N5 requires:

```
bridge signal 15: stopping; no farewell value, nothing zeroed
session closed (clean shutdown); no farewell value written, nothing zeroed
```

The gate reached its own verdict without being told:

```
[envelope_gate] GATE CLOSED after 3 stop(s): envelope stale (or never received).
  Ramping to zero at 0.50 m/s^2. This is a degraded mode, not a safety function (invariant 2).
```

at wall `1785996743.1552` — **519.7 ms after the SIGTERM**, against the gate's
own `stale_window_s` of 0.500 s plus one 50 ms cycle. The last PLC-sourced
envelope sample reached the vehicle at `t = 11.0146` carrying
`enable = 1, ceiling = 0.600, permit = 1, mode = 2` — a **permissive** envelope,
frozen at the instant the link died — and the vehicle stopped anyway. That is
invariant 2 in one line: *loss of supervision is a degraded mode the vehicle
handles onboard, not a safety event, and not a licence to keep going on the last
permission it was granted.* `/cmd_vel_gated` reached exactly `0.0` **+33.9 ms**
after the last envelope sample and stayed there for 2,927 further samples —
holding an explicit zero rather than falling silent, because in an unknown mode
no other owner of the command is known to exist. `mode/applied` fell to `0`.

**Two honest limits of this observation.** The vehicle was already at standstill
when the link dropped — it had run into the same protective-field geometry
during the preceding traverse — so the figures above are the **gate's
reaction**, not a measured deceleration; and the command source for this
observation was a 20 Hz publisher on `/cmd_vel_smoothed`, the gate's input,
rather than the smoother, which is `agv/forklift/EVIDENCE_ENVELOPE.md`'s own
arrangement, because the closed-loop smoother could not accelerate this plant
from rest (it plateaued at 0.034 m/s commanded against 0.001 m/s of ground
truth, the deadlock region LESSONS 2026-08-05 records). Neither is a bridge
property and neither is repaired here.

**One deliberate act on the simulator, recorded so no figure is read as
undisturbed.** Between observations 2 and 3 the model was moved back to its
spawn pose with `gz service -s /world/warehouse/set_pose`, twice, to get the
vehicle out of the protective-field geometry it had stopped in. No figure in §4.1
or §4.2 is from after that move.

## 5. What this evidence does not establish

| Not established | Why |
|---|---|
| Any safety property, PL, SIL, Category or PFH | Nothing in §12 is a safety function (ADR 0011 D5, invariant 1). The stand-in writer carries no integrity claim either |
| The ceiling clamp on the real chain | §4.1: the demand never reached the ceiling. `agv/forklift/EVIDENCE_ENVELOPE.md` §5 measures it against a double |
| A stopping distance or a reaction time the machine is certified to | Every figure here is one observation, **n = 1**, of a process behaviour in a simulator (LESSONS 2026-08-04) |
| That `bridge-design.md` carries the envelope group | **It does not.** `opcua-nodes.md` §12.13 item 1 asks the interface agent for that round and it has not been written. The group definition in `amr_bridge/config.py` is the bridge's proposal made runnable, and it says so in the code |
| AT-02, AT-03 or AT-04 | None was attempted. This run is the prerequisite m5-42 §5 item 3 names, not the tests item 7 names |
| Anything about the cell group on this CPU | It is not on this CPU (§1.1) |
| A repeated figure of any kind | Every timing here is **n = 1**. The obstacle round trip, the ramp, the standstill and the stale reaction were each observed once |

**One observation handed to `agv/` rather than explained here.** In run r4, with
a steady 0.30 m/s on the gate's input and a permissive envelope,
`/cmd_vel_gated` alternated between `0.30` and `0.0` at roughly the gate's own
cycle while the vehicle stood still against the warehouse structure. It does not
appear in r3 under the same command source (200 consecutive samples in a 10 s
window, 0 zeros). It is in `envelope-chain-2026-08-06-r4-linkloss.csv.gz` from
`t ≈ 0.52`, it is upstream of nothing the bridge owns, and it is recorded rather
than diagnosed.

## 6. Files

| File | What it is |
|---|---|
| `bridge/evidence/latency-2026-08-06-m544-s1-…-pid151891.csv.gz` | Stage 1, forklift group alone, 352.2 s |
| `bridge/evidence/latency-2026-08-06-m544-s2-…-pid151999.csv.gz` | Stage 2, forklift + envelope, 947.0 s — carries the `L2`/`read_rt` rows behind §4.2's 41.6 ms |
| `bridge/evidence/envelope-chain-2026-08-06-r1.csv.gz` | Vehicle-side witness, observations 1 and 2 |
| `bridge/evidence/envelope-chain-2026-08-06-r2.csv.gz` | Vehicle-side witness, the recovery sequence |
| `bridge/evidence/envelope-chain-2026-08-06-r3.csv.gz` | Vehicle-side witness, the second traverse |
| `bridge/evidence/envelope-chain-2026-08-06-r4-linkloss.csv.gz` | Vehicle-side witness, observation 3 |
| `bridge/evidence/m544-*.log.gz` | The bridge, HMI, arena and envelope-stack logs of the same runs |
| `bridge/tools/probe_server_paths.py` | The read-only server probe of §1 |
| `bridge/tools/observe_envelope_chain.py` | The subscriber-only vehicle-side witness |

---

# 2026-08-06 (second session) — the same chain, five times

**What this section is.** m5-44, above, ran the chain **once**. Every figure it
records is `n = 1` and its §5 says so. This section repeats the same chain on
the same route with the same protocol **five times**, so that each of those
figures gains a repeat count and a spread, and it closes the one gap m5-44
named: **the ceiling clamp**, which m5-44 could not exercise because the demand
never reached the ceiling.

Nothing above this line was changed. Written **as each run landed**, run by run.

## 7. Environment for this session, and what qualifies every figure in it

| Item | Value |
|---|---|
| Date | **2026-08-06**, 07:40–09:5x UTC (09:40–11:5x local), a separate session from §0–§6 |
| Controller | The **same** PLCSIM Advanced instance `safecell3` at `192.168.53.1`, project `safe_amr`, CPU 1513F-1 PN, downloaded 2026-08-05. **Nothing in TIA was opened, changed, compiled or downloaded for this work** — it was not launched by this session and no client here writes anything but the tags §7.1 lists |
| Bridge host | WSL2 on the owner's Windows machine, Ubuntu 24.04, ROS 2 Jazzy, `rmw_fastrtps_cpp`; `~/amr-bridge-venv` (`asyncua==2.0.1`) |
| Simulator | `gz sim` 8.11.0, headless, software rasterised, `sim/launch/warehouse_bringup.launch.py` at `x=-4.5 y=7.0 yaw=0.0` — **the same spawn as m5-44**, and the pose is commanded back to it between runs so "the same route" is a fact and not a hope |
| Isolation | `ROS_DOMAIN_ID=57` **and** `GZ_PARTITION=m546`, both, always (LESSONS 2026-07-27) |
| Machine state before the timed runs | checked and recorded, not assumed: `2026-08-06T07:40:23Z`, `uptime` load average `0.00 0.00 0.00`, and the stack script's own `pgrep` over `gz sim`, `run_bridge`, `hmi_server`, `envelope_gate`, `forklift_io`, `obstacle_zone`, `velocity_smoother`, `cmd_vel_to_tricycle` returned **nothing running**. One simulator, one session, one agent measuring (LESSONS 2026-07-30, 2026-08-04) |
| Independent witness of the PLC | the **commissioning HMI's own OPC UA session** (`hmi/hmi_server.py --config hmi/config.yaml`), a different process, a different client and a different session from the bridge. Every "the PLC did X" verdict below is cross-read from `GET /state`'s `metrics` block, which the bridge cannot write |

**What no figure here is.** Not a safety figure. The envelope, the mode, the
process stop and the vehicle's report are **process data** (`opcua-nodes.md`
§12.1, ADR 0011 D5); loss of any of these links is a **degraded mode, not a
safety event** (invariant 2). No PL, SIL, Category or PFH is claimed for
anything in this section, and the stand-in writer carries no integrity claim.

### 7.1 The protocol, stated once and run unchanged five times

The stack is m5-44's, from the same launch lines (`~/m544-stack.sh`, copied to
`~/m5-46-stack.sh` with the group tag changed and `obstacle_zone.py` given its
own case). Throwaway harness scripts live **outside the repository** in the
owner's WSL home, as m5-44's did; nothing new was added to `bridge/`.

Brought up once, held for the whole session:

1. `sim/launch/warehouse_bringup.launch.py gui:=false x:=-4.5 y:=7.0 yaw:=0.0`
2. `agv/forklift/launch/envelope.launch.py io:=true`
3. `agv/forklift/scripts/obstacle_zone.py`
4. `hmi/hmi_server.py --config hmi/config.yaml`
5. `bridge/standin_writer/standin_writer.ps1 -Instance safecell3` on **Windows**,
   through the PLCSIM API, **not** OPC UA — then `estop close`, `zone close`,
   `reset pulse 1200`, fed into its own console by process id with
   `standin_writer/testing/console_feed.ps1`. Every one of those is a client
   action on a PLC **input**.

Then, **once per run**, and in this order:

| # | Step | Who decides |
|---|---|---|
| 1 | A **fresh bridge session** on the committed `bridge/config/bridge.yaml`, its own evidence CSV, unique name (LESSONS 2026-07-28) | — |
| 2 | Cell to rest, process stop released, monitored reset tapped, `ForkliftResetRequired` seen `False` | the PLC |
| 3 | The subscriber-only witness `bridge/tools/observe_envelope_chain.py` starts **before** the envelope | — |
| 4 | `drive_mode := 2` (Autonomous) posted to the HMI → the envelope is formed **entirely in the standard program** | the PLC |
| 5 | A **0.90 m/s** demand published at 20 Hz on `/cmd_vel_smoothed`, the gate's input — **above the 0.600 m/s ceiling the PLC carries**. This is the clamp exercise m5-44 could not run, and it is also what drives the vehicle down the route | — |
| 6 | The vehicle traverses; its own protective field trips; the PLC withdraws the envelope | the PLC |
| 7 | The demand is **held live for a further 4 s** after the withdrawal, so the gate is seen holding zero against a standing command rather than against silence | — |
| 8 | Pose commanded back to spawn, latches cleared, mode re-selected → a **permissive** envelope again | the PLC |
| 9 | A 0.30 m/s demand made live so the gate is **PASSING**, then `SIGTERM` to the bridge → the link-loss case | the vehicle, alone |

The command source is a 20 Hz publisher on the gate's input, not the closed-loop
smoother, for the reason m5-44 open question 4 records: the smoother cannot
accelerate this plant from rest. That is `agv/`'s, it is unrepaired, and it is
the same arrangement `agv/forklift/EVIDENCE_ENVELOPE.md` uses.

### 7.2 One protocol correction, made before the five runs and recorded rather than hidden

The first attempt (`r1a`) ran steps 1–8 and then sent `SIGTERM` **with no demand
live**. It measured nothing at step 9: the gate counts and logs its stale close
on the transition *out of* `PASSING`, and `PASSING` is a state it can only hold
while a command is arriving. With no demand the gate sits in `HOLD_ZERO`, a
link loss changes nothing it can report, and the run's log carries no
`GATE CLOSED … envelope stale` line at all. m5-44's r4 had a live 20 Hz
publisher at its `SIGTERM` and that is why it saw one.

Step 9 gained its "make the demand live first" line and the five runs below all
carry it. `r1a`'s files are kept under their own names — its steps 1–8 are a
valid observation and its step 9 is a **null**, not a pass:

* `bridge/evidence/latency-2026-08-06-m546-r1a-protocol-v1-…csv.gz`
* `~/m5-46-runs/envelope-chain-2026-08-06-r1a-protocol-v1.csv`

### 7.3 Two further runs discarded before the five, and why they are named here

Both were failures of the **harness**, not of the chain, and both are kept
because each one is a trap the next person will otherwise walk into.

* **`r1b`** — `gz service … /world/warehouse/set_pose` **returns
  `data: true` and does nothing** when the request carries only
  `name: "Forklift"`. It resolves on the **entity id**. The run therefore began
  where the previous run had ended — jammed against the wall it had stopped at,
  inside the front scanner's blind range, so the scan read *clear* — and drove
  a stalled vehicle for 60 s: `drive_wheel_joint` turned 162.5 rad (19.5 m of
  wheel) while the model moved 0.63 m. The pose reset now reads the id out of
  `dynamic_pose/info`, sends it, and **verifies the move against the pose**;
  a service's own boolean is not evidence that it acted.
* **`r1c`** — the corrected reset worked, and the 60 s window was simply too
  short for the route: the vehicle reached `x = 11.7` with the field still
  clear. Probed afterwards, the field trips at `x ≈ 14.1`. The window became
  150 s, which is a window and not a target.

Both files are kept under their own names and neither contributes a figure.

---

## 8. The five runs

Every run below executed §7.1 steps 1–9 to completion. Each has **three
independent records**: the vehicle-side witness CSV, the bridge's own evidence
CSV (a separate process, a separate clock read, a separate file), and the
envelope gate's own log.

### 8.1 The route, and how repeatable it turned out to be

Spawn `(-4.5, 7.0)` yaw 0, straight down the aisle at `y = 7.0` to the east
wall, pose commanded back and **verified** before every run.

| Run | Traverse to the trip | World pose at the withdrawal |
|---|---|---|
| r1 | 32.2 s | `(13.329, 6.978)` |
| r2 | 144.4 s | `(13.323, 7.000)` |
| r3 | 41.4 s | `(13.334, 6.991)` |
| r4 | 87.3 s | `(13.337, 7.015)` |
| r5 | 147.8 s | `(13.288, 6.990)` |

**The place is repeatable to 49 mm in `x` and 37 mm in `y`; the time is not
repeatable at all.** The same 17.8 m of route took between 32 s and 148 s, a
factor of 4.6, at an unchanging 0.600 m/s ceiling and an unchanging clamped
command — so the variation is in what the **plant** does with a command it is
given, not in what the chain carries. It is `agv/`'s, it is not diagnosed here,
and it is the reason every reaction figure below is timed **from the trip**
rather than from the start of the run.

### 8.2 Envelope arrival and gate adoption, n = 5

`mode_in_force 0→2`, `motion_enable 0→1` and `speed_ceiling 0.0→0.600` are
formed together in the standard program. The spread is how far apart they land
on the vehicle; the adoption is `mode_applied 0→2` measured from
`mode_in_force`.

| Run | Arrival spread (3 elements) | Gate adoption |
|---|---|---|
| r1 | 1.6 ms | **9.7 ms** |
| r2 | 1.2 ms | **44.5 ms** |
| r3 | 2.1 ms | 24.8 ms |
| r4 | 2.2 ms | 32.7 ms |
| r5 | 1.6 ms | 28.8 ms |
| **n = 5** | **1.2 – 2.2 ms**, mean 1.74 | **9.7 – 44.5 ms**, mean 28.1 |

**What the repeat count changes about m5-44's reading.** m5-44 recorded the
three elements arriving "within 1.8 ms of each other" and the gate adopting
"44.5 ms later". The spread reproduces: five runs, all between 1.2 and 2.2 ms,
one bridge cycle and one poll phase, as §4.8 and §12.4's cadence note require.
**The adoption figure does not reproduce as a value.** 44.5 ms is not the
adoption latency of this chain — it is the **top of its range**, and the same
chain adopted in 9.7 ms in r1. The distribution is 4.6x wide, which is what a
readback crossing an asynchronous 20 Hz bridge cycle and a 20 Hz gate cycle
looks like; quoting the single m5-44 observation as *the* latency would have
overstated it by up to a factor of four and understated nothing.

`equipment_permit` is deliberately not in the spread: it goes permissive
earlier, at the release of the process stop, and its own transition is timed in
every run at `t ≈ 4.2 s` against a mode selection at `t ≈ 6.2 s`. It is a
**second, independently formed** element carried on the same six slots, which is
the point m5-44 §4.2 makes about a different cause on the same wires.

### 8.3 The field trip, the PLC's round trip, and the stop, n = 5

Timed across the real seam. The round trip is read from the **bridge's own**
CSV: the `L2` row in which the server acknowledges the bridge's write of
`ForkliftObstacleInStopZone := TRUE`, to the `read_rt` row in which the bridge
reads `ForkliftMotionEnable` back as `FALSE`. Both stamps are
`CLOCK_MONOTONIC` on the bridge host, differenced only against themselves
(§9.1 C1/C2). Everything after it is the vehicle-side witness.

| Run | PLC round trip | `/cmd_vel_gated` before | ceiling→0 after enable→0 | command-to-zero | standstill (settled) |
|---|---|---|---|---|---|
| r1 | 45.1 ms | 0.6000 m/s | 1.1 ms | 1186.6 ms | 1207.6 ms |
| r2 | 44.6 ms | 0.6000 m/s | 0.6 ms | 1208.6 ms | 1208.3 ms |
| r3 | 45.3 ms | 0.6000 m/s | 0.7 ms | 1194.8 ms | 1248.0 ms |
| r4 | **37.2 ms** | 0.6000 m/s | 0.9 ms | 1191.0 ms | **1128.1 ms** |
| r5 | 43.6 ms | 0.6000 m/s | 0.9 ms | 1156.1 ms | 1208.0 ms |
| **n = 5** | **37.2 – 45.3 ms**, mean 43.2 | — | **0.6 – 1.1 ms** | **1156.1 – 1208.6 ms**, mean 1187.4 | **1128.1 – 1248.0 ms**, mean 1200.0 |

**m5-44's 41.6 ms round trip reproduces**: it sits inside a five-run range of
37.2 – 45.3 ms, and four of the five runs are within 1.7 ms of each other with
r4 the low outlier. This is the one m5-44 figure that came back as a figure
rather than as one draw.

**m5-44's 162.5 ms command-to-zero does NOT reproduce, and must not be quoted
as a stopping figure.** It is not a regression and nothing changed: the gate
ramps at a fixed 0.50 m/s², so the time to zero is proportional to the speed it
is ramping *from*. m5-44 withdrew at 0.1018 m/s and took 162.5 ms; these five
withdrew at the full 0.600 m/s ceiling and took 1156 – 1209 ms. Both agree with
`v / 0.50`: 0.204 s and 1.200 s respectively. **The figure that repeats is the
deceleration, not the duration**, and a stopping time quoted without the speed
it started from says nothing.

**r4 behaved differently and is not averaged away.** Its first `|odom vx| <
0.005 m/s` came at **+877.7 ms**, *before* the command reached zero — the plant
decelerated ahead of the commanded ramp. It is not a standstill: the vehicle
moved again afterwards, up to 0.0071 m/s in the following 3 s, and only settled
at **+1128.1 ms**. The other four runs' first crossing and settled standstill
are the same sample. The table quotes the **settled** figure for all five so
the column compares like with like, and r4's transient is stated here rather
than hidden inside it.

**The gate published its terminal value and only then held zero** in all five
runs — 0.0 reached explicitly, never by falling silent (the 2026-08-04 lesson,
honoured in the deployed node), and the demand was still live on the gate's
input for 4 s after every withdrawal, so the zero is held against a standing
command and not against silence.


## 9. THE CEILING CLAMP — the gap m5-44 left, closed

m5-44 §4.1 and §5 say plainly that it could not establish the clamp: "the
demand never reached the ceiling", the peak `/cmd_vel_gated` being 0.1018 m/s
against a 0.600 m/s ceiling, and the clamp was measured only in
`agv/forklift/EVIDENCE_ENVELOPE.md` §5 **against a topic double**.

Here the demand is driven **above** the ceiling, on the real chain, in every
one of the five runs: a 20 Hz publisher holds `/cmd_vel_smoothed` at
**0.900 m/s** against the **0.600 m/s** ceiling the PLC formed and the bridge
carried.

| Run | Demand held | Non-zero gated samples in the window | max `/cmd_vel_gated` | samples exactly at the carried ceiling | samples **above** the ceiling |
|---|---|---|---|---|---|
| r1 | 0.900 m/s | 642 | `0.600000024` | 596 | **0** |
| r2 | 0.900 m/s | 3122 | `0.600000024` | 3075 | **0** |
| r3 | 0.900 m/s | 885 | `0.600000024` | 839 | **0** |
| r4 | 0.900 m/s | 1725 | `0.600000024` | 1679 | **0** |
| r5 | 0.900 m/s | 2978 | `0.600000024` | 2932 | **0** |
| **n = 5** | | **9352** | — | **9121** | **0** |

**Nine thousand three hundred and fifty-two consecutive opportunities to exceed
a PLC-formed bound, and none taken.** The remaining 231 non-zero samples are
the acceleration and the ramp at each end of the window, below the ceiling and
passed through **exactly** — the gate reports itself unclamped for those.

The gate announced it in its own words, unprompted, in every run:

```
[envelope_gate]: clamped to the ceiling: commanded +0.9000 m/s,
  emitting +0.6000 m/s at ceiling 0.6000; the arc is unchanged and the
  vehicle drives it slower
```

**The value the clamp lands on is the PLC's, carried and not re-created.** The
maximum is `0.600000024` — bit for bit the `float64` widening of the PLC's
`Real` 0.6 that the bridge read off the CPU and republished, the same
`0.6000000238418579` that appears in every run's `speed_ceiling` transition and
in the frozen envelope of §10. **The bridge did not round it to a nicer value**
(§1.1) and the gate did not substitute a configured 0.6 of its own: the clamp
output is the carried number, and that identity is what shows the bound came
from the controller rather than from a constant on the vehicle.

**What this is not.** It is not a safety-rated speed limit and not an SLS. It
is a process bound on a process command, applied by a Python node on a network
(invariant 1, ADR 0011 D5). And it is not a *new* claim about the gate — the
gate's clamp arithmetic was already unit-tested and measured against a double;
what was missing, and is now present, is that the bound the gate applies on the
**real chain** is the one the **PLC formed**, carried unchanged across the OPC
UA seam, with **no velocity value crossing that seam in either direction**
(ADR 0014): what crosses is a ceiling, an enable, a permit and a mode.

## 10. The link-loss case, repeated, n = 5

`SIGTERM` to the bridge with a **permissive** envelope frozen on the wire and a
**live 0.30 m/s demand** on the gate's input, so the gate is in `PASSING` and
its stale close is a real transition (§7.2).

| Run | frozen envelope at the moment of the loss | `SIGTERM` → gate's own stale close | `/cmd_vel_gated` → exactly 0.0 | held-zero samples after | all zero | `mode/applied` after |
|---|---|---|---|---|---|---|
| r1 | enable 1, ceiling 0.600, permit 1, mode 2 | 535.5 ms | 1074.6 ms | 321 | yes | 0 |
| r2 | enable 1, ceiling 0.600, permit 1, mode 2 | 537.5 ms | 1079.0 ms | 321 | yes | 0 |
| r3 | enable 1, ceiling 0.600, permit 1, mode 2 | 508.1 ms | 1065.3 ms | 322 | yes | 0 |
| r4 | enable 1, ceiling 0.600, permit 1, mode 2 | 520.3 ms | 1077.6 ms | 322 | yes | 0 |
| r5 | enable 1, ceiling 0.600, permit 1, mode 2 | 542.9 ms | 1091.8 ms | 320 | yes | 0 |
| **n = 5** | **identical in all five** | **508.1 – 542.9 ms**, mean 528.9 | **1065.3 – 1091.8 ms** | 320 – 322 | **5 of 5** | **0 in 5 of 5** |

Every run, the bridge went out the way §8.3 N5 requires and said so:

```
bridge signal 15: stopping; no farewell value, nothing zeroed
session closed (clean shutdown); no farewell value written, nothing zeroed
```

and every run, the gate reached its own verdict without being told:

```
[envelope_gate]: GATE CLOSED after N stop(s): envelope stale (or never received).
  Ramping to zero at 0.50 m/s^2. This is a degraded mode, not a safety function (invariant 2).
```

**m5-44's 519.7 ms reproduces**, sitting mid-range in 508.1 – 542.9 ms, and all
five fall inside the gate's own `stale_window_s` of 0.500 s plus one 50 ms
cycle — the bound is `[500, 550] ms` by construction and the measurement stays
inside it five times out of five. The 1065 – 1092 ms to an exact zero is the
same 0.50 m/s² ramp from 0.30 m/s (0.600 s) added to the detection.

This is invariant 2 five times over: **the last thing the vehicle was told was
that it may move at 0.600 m/s, and it stopped anyway.** Loss of supervision is
a degraded mode handled onboard, not a safety event, and not a licence to keep
going on the last permission granted. The gate held an **explicit zero** for
~320 samples afterwards rather than falling silent, because in an unknown mode
no other owner of the command is known to exist (the 2026-08-04 lesson).

## 11. What this session establishes, and what it still does not

| Now established, with its n | |
|---|---|
| The chain is **repeatable**: PLC-formed envelope → bridge → gate → vehicle drives → its field trips → PLC withdraws → vehicle stops, five times, one protocol | n = 5 |
| **The ceiling clamp on the real chain**, against a demand 1.5x the ceiling, on the PLC's own carried value | n = 5, 9352 samples, 0 exceedances |
| The **link-loss** degraded mode with a permissive envelope frozen | n = 5 |
| The **PLC round trip** 37.2 – 45.3 ms | n = 5 |
| The **arrival spread** 1.2 – 2.2 ms | n = 5 |

| Still not established | Why |
|---|---|
| Any safety property, PL, SIL, Category or PFH | Nothing in §12 is a safety function (ADR 0011 D5, invariant 1). The stand-in writer carries no integrity claim |
| A stopping distance or a reaction time the machine is certified to | Every figure is a process behaviour in a simulator, on a software-rasterised host under load |
| That `bridge-design.md` carries the envelope group | **It still does not.** `opcua-nodes.md` §12.13 item 1 asks the interface agent for that round. The group definition in `amr_bridge/config.py` remains the bridge's proposal made runnable and still says so in the code; **nothing in this session changed that marking** |
| AT-02, AT-03 or AT-04 | None was attempted |
| The **recovery sequence** as a repeat count | It ran, correctly, before every one of the five runs — the process stop released, the monitored reset tapped, the mode re-selected — but this session did not re-time m5-44 §4.2's latch behaviour and does not claim to |
| Why the same 17.8 m of route takes 32 s in one run and 148 s in another | §8.1. It is the plant, not the chain. Handed to `agv/`, undiagnosed |

**One observation handed to `agv/` rather than explained here.** The traverse
time varied 4.6x across five runs at an unchanging clamped 0.600 m/s command
(§8.1), and in r4 the plant decelerated ahead of the gate's own ramp and then
crept again (§8.3). Both are visible in the committed witness CSVs, both are
downstream of everything the bridge owns, and both are recorded rather than
diagnosed. Together with m5-44's open question 4 — the closed-loop smoother
cannot accelerate this plant from rest — they say the same thing: **the plant's
traction authority is the least settled part of this chain**, and it is the one
part of it no figure in this file is a property of.

## 12. Files, this session

All gzipped **after** their writers had exited and the files had gone quiet —
process gone by `pgrep`, timestamps checked (LESSONS 2026-07-28/29,
2026-07-30). The stand-in writer was quit from its own console first.

| File | What it is |
|---|---|
| `bridge/evidence/latency-2026-08-06-m546-r1…r5-…csv.gz` | The five bridge sessions, one per run, unique name per start — the `L2`/`read_rt` rows behind §8.3's round trip |
| `bridge/evidence/m546-envelope-chain-2026-08-06-r1…r5.csv.gz` | The five vehicle-side witness captures, subscriber-only |
| `bridge/evidence/…-r1a-protocol-v1…`, `…-r1b-jammed…`, `…-r1c-notrip…` | The three discarded runs of §7.2 and §7.3, kept under their own names. **No figure in this section comes from any of them** |

**Why the witness files carry an `m546-` prefix and m5-44's do not.** They were
first written as `envelope-chain-2026-08-06-r1…r5.csv.gz`, which is m5-44's own
naming — **the same date, the same run letters** — and copying them into
`bridge/evidence/` silently overwrote three committed m5-44 captures (`r1`,
`r2`, `r3`). It was caught by `git status` before anything was committed and the
three were restored from the index and verified with `gzip -t`; m5-44's
`r1`, `r2`, `r3` and `r4-linkloss` are the committed files, untouched. The
session prefix is now part of the name, which is the same rule the bridge's own
per-session CSV suffix already follows: **a run identifier that is only unique
within one session is not a file name.**
| `bridge/evidence/m546-bridge-r1…r5.log.gz` | The bridge's own logs, one per session |
| `bridge/evidence/m546-envelope-stack.log.gz` | The gate's own log — every `clamped to the ceiling`, `gate open` and `GATE CLOSED` line quoted above |
| `bridge/evidence/m546-obstacle-zone.log.gz` | The field evaluator's own verdicts |
| `bridge/evidence/m546-arena.log.gz`, `m546-hmi.log.gz` | The simulator and the independent OPC UA witness |
| `bridge/evidence/m546-run-events.txt.gz` | The driver's event stamps for all runs, including the pose resets and their verification |
| `bridge/standin_writer/logs/standin-writer-20260806T074032Z-pid38804.log` | The stand-in writer's session: `estop close`, `zone close`, `reset pulse 1200`, 41 280 cycles, 0 write failures, clean `quit` |
