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
