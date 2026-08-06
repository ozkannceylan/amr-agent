# EVIDENCE — protective-field evaluation, phase 1 (m5-12b)

**This file was created with its headings before the first run of this
brief and appended to as each result landed.**

**Authority.** `agv/forklift/FIELD-EVALUATION.md` (m5-12) specifies what
was built. `plc/forklift-safety/SPEC.md` §7 and
`bridge/STANDIN-WRITER-DESIGN.md` §3 specify the consumer this feeds.
Neither was edited by this brief.

**This is not a safety claim, in whole or in part** (ADR 0011 D5). What
ran is a **model of what a safety-rated scanner does inside its own
housing**, in Python, on two rendered depth images that crossed a bridge
and a ROS graph, feeding a **stand-in for wiring**. No Category, no
Performance Level, no SIL, no PFH, no channel count and no diagnostic
coverage is claimed, achieved or implied by anything below. Every PL and
Category in the documents behind it is a **PLr target** out of
`docs/safety/`, never an achievement. No depth, response time or stopping
distance recorded here is a figure any machine is characterised by.

---

## 0. Environment, and that the simulator was free

| Item | Value |
|---|---|
| Date, run window (UTC) | 2026-08-05, `22:12` to `22:37` |
| Host | **WSL2 on the owner's Windows machine** — the target platform, not a container (LESSONS 2026-07-27). Ubuntu, kernel `5.15.167.4-microsoft-standard-WSL2`, glibc 2.39, **20 cores** |
| ROS 2 | Jazzy, `/opt/ros/jazzy` |
| Gazebo | **8.11.0**, `ros-jazzy-gz-sim-vendor`, `gz sim -r -s`, headless |
| Isolation | `GZ_PARTITION=m512b` **and** `ROS_DOMAIN_ID=77`. Both, because gz transport is not DDS (LESSONS 2026-07-27) |
| **Simulator free before starting** | Checked, and this is the record of the check: `pgrep -af "gz sim\|gzserver"` and `pgrep -af "ros2\|rclpy\|nav2"` both returned **nothing** at 2026-08-05 21:59 UTC; `uptime` load average 0.57. `/tmp` held earlier agents' scripts (`m5-38-*`, `m5-40-*`) but **no live process**. Serialised, per LESSONS 2026-07-30 |
| World | `sim/worlds/forklift_arena.sdf`, md5 `c7733d22ee66ad734c7e3ee828d4a464`, unedited |
| Model | `agv/forklift/model.sdf`, md5 `de5edf370986bd77312204e297f4a5c6`, unedited by this brief |
| **Plant** | **The new plant.** `steer_joint` `<p_gain>` reads **60000.0**, not the 6000 of the M4 build (model.sdf line 1046). The vehicle was **not driven** in any run of this brief — it stood at its spawn pose throughout — so no figure here depends on the steering loop; the value is recorded because the brief required the plant in force to be named |
| Vehicle pose | spawned at world **(7.000, 0.000)**, yaw 0, carriage travel 0.000 m. Chosen because from there every arena feature except the east wall is beyond the 5.50 m scanner range, and the R2 lift window (travel 0.05–0.10 m) is not entered |
| Consumer | the stand-in writer, `-Instance safecell3`, PLCSIM Advanced API 7.0, `OperatingState = Run`. **`bridge/` was not edited**; the writer was run as built and its session log read |
| Writer session | `bridge/standin_writer/logs/standin-writer-20260805T221508Z-pid15932.log` (gitignored per `bridge/.gitignore`; the lines that matter are quoted below) |

**Two clocks, and every cross-host figure is qualified by it.** This
node's log is stamped from WSL's UTC clock; the writer's from Windows'.
No offset between them was measured, so **no "WSL→Windows transit"
figure below is a transit measurement**; each is a difference of two
clocks that additionally contains up to one 50 ms writer cycle.

---

## 1. What was built, and what phase 1 deliberately does not build

| Built | File |
|---|---|
| The evaluation node | `agv/forklift/scripts/field_evaluation.py` |
| Every constant it uses | `agv/forklift/config.yaml`, `field:` block |
| The rear measurement channel bridged under its reserved name | `agv/forklift/launch/vehicle.launch.py`, and the `topics:` entry |
| The reverse speed cap the static field is sized for | `agv/forklift/nav2.yaml`, `min_velocity` −0.60 → **−0.55** |

**Not built, by instruction** (FIELD-EVALUATION.md §12): the warning
field (phase 2), case selection A/B/C (phase 3), any speed enforcement,
any ROS topic for the verdict, any change to `plc/` or `bridge/`, any new
dependency. `obstacle_zone.py` is untouched and still reads the front
measurement channel as the M4 comfort stop.

**The verdict has no ROS topic, and the brief's phrase was read as the
design reads it.** The brief asked for "the OSSD-equivalent channel pair
flipping in a recorded topic echo". `config.yaml`'s `topics:` block
carries an owner ruling (m5-06, 2026-07-30) that *"the safe channel has
no topic on either transport, ever"*, `scripts/check_sensor_frames.py` §4
checks that rule by machine, and FIELD-EVALUATION.md §2 resolves the
phrase to "on the link". **The recorded evidence is therefore the
transition log and the writer's session log, correlated** — which is what
SPEC §7.6 actually requires of criterion (a), and is strictly stronger
than a topic echo because it names the *source* of each write. The
conflict is restated in the m5-12b report, not resolved silently.

---

## 2. The contour in force, read back from the running node

Read back from the node's own `START` and `DEVICE` lines rather than
recomputed:

```
contour: corridors x -3.225..2.210 m, y -0.550..+0.550 m in the vehicle frame
         - the plan outline (-1.875..0.860 m) grown by the protective depth
         1.35 m fore and aft, half width 0.55 m
self-return clip: rear  device, sensor frame -133.0..-71.8 deg, boundary 0.040 m
self-return clip: front device, sensor frame +136.4..+137.6 deg, boundary 1.034 m

front contour built: 275 rays, 275 of them with a live field,
                     boundary 0.100..3.925 m over the live rays,
                     mount (x=0.700 y=0.450 yaw=0.7854 rad)
rear  contour built: 275 rays, 214 of them with a live field,
                     boundary 0.100..2.913 m over the live rays,
                     mount (x=-0.700 y=-0.450 yaw=-2.3562 rad)
```

The mounts are **read out of `model.sdf` at start-up**, not mirrored: the
node parses the two `<sensor>` elements the way `sensor_tf.py` does, so
no pose is copied into `config.yaml`. The plan outline
`x ∈ [−1.8750, 0.8600]`, `y ∈ [−0.5490, 0.5490]` was likewise extracted
from `model.sdf`, and the corridor half-width 0.55 m lands **1 mm outside
the vehicle's own widest plan point** — the two scanner housings at 45°,
which sit 20 mm below the scan plane and therefore return nothing.

**The design's §6 clip band, applied verbatim, leaves the vehicle inside
its own field.** FIELD-EVALUATION.md §6 quotes the rear band as
−131.5°…−72.3°. Those are `EVIDENCE_SENSOR_COVERAGE.md` §13.2's measured
−131.48°…−72.26° rounded **outward at one end and inward at the other**,
and the inward rounding drops the band's edge rays:

| Ray | Sensor bearing | Measured self-return | Contour boundary there | Verdict under §6's band |
|---|---|---|---|---|
| index 5 | −132.482° | **0.780 m** (mast rail corner, §13.3) | 1.001 m | **inside the field — permanent intrusion** |
| index 65 | −72.263° | **0.164 m** (carriage, §13.3) | 2.183 m | **inside the field — permanent intrusion** |

Either one alone holds the aggregate at INTRUSION for ever. §13.2's own
body-return index set is **5..65**, not 6..65, and §13.3 lists index 5
explicitly. The band in force is therefore taken from the measured index
set and placed **between rays** (index 4 is at −133.485°, index 66 at
−71.259°), giving −133.0…−71.8 and excluding exactly indices 5..65 —
**61 rays**, which is why 214 of 275 rear rays carry a live field. A
correction to §6's table is requested in the m5-12b report rather than
edited into another brief's deliverable.

**This is field geometry, not a filter.** No sample is discarded anywhere
in the node; what the clip changes is how far the monitored region
reaches at those bearings, which is what a real device's configured
contour does. `EVIDENCE_SENSOR_COVERAGE.md` §13.8 point 1 states the
distinction and this build keeps it.

---

## 3. The link: address read-back, connection, and the ZONE encoding

```
link: 172.19.176.1:45015 - the address was read back from this host
      (WSL default route (ip route show default)), never taken from a
      document (ADR 0006). ZONE 1 = field clear, ZONE 0 = intrusion or
      this evaluation's own fault: the digit is the CIRCUIT LEVEL
```

The encoding is `bridge/STANDIN-WRITER-DESIGN.md` §3's, **matched rather
than invented** — the listener is built and running-tested, and its own
document says the m5-12 build must adopt it. No change to the wire format
was needed and none is requested.

The writer accepted the connection and applied the first line
immediately, so the design's argument that *a fresh connection is a
transition from unknown* is confirmed against the implementation rather
than asserted:

```
22:18:51.440Z | LINK  | up: field-evaluation client 172.19.180.72:43808 connected;
                        the zone channel now belongs to the field and is held FALSE
                        until its first ZONE line
22:18:51.443Z | FIELD | ZONE 0 -> ZoneDeviceCircuitClosed := False
22:18:51.581Z | FIELD | ZONE 1 -> ZoneDeviceCircuitClosed := True
```

**Nothing blocked at the firewall.** The connect succeeded on the first
attempt in every session. Before a writer was listening, attempts failed
with *timed out* rather than *connection refused* — Windows drops rather
than refuses on a closed port — which is worth recording because it looks
like a firewall and is not one.

---

## 4. THE INTRUSION — an object entering the protective field in Gazebo

Session `agv/forklift/evidence/field_evaluation/field-evaluation-20260805T221851Z-pid137538.log`,
writer session `standin-writer-20260805T221508Z-pid15932.log`.

### 4.1 The stimulus, and that it originated in the simulator

A 0.30 × 0.30 × 0.60 m box was **spawned into the running Gazebo world**
and then **moved** with `gz service /world/forklift_arena/set_pose`. No
value was typed anywhere in the chain: the object moved in the simulator,
the simulator's two `gpu_lidar` sensors saw it, this node formed the
verdict, and the writer put it on the stand-in channel.

| # | Stimulus issued (WSL) | Returned | Node verdict (WSL) | Detail from the node's own log |
|---|---|---|---|---|
| 1 | 22:19:25.068 **spawn OUTSIDE the field at (10.5, 0)** | .683 | **no transition** | the object is 2.85 m from the front sensor and visible to it, and the field boundary discriminated it |
| 2 | 22:19:33.703 **move to (8.5, 0)** — drive corridor | .995 | 22:19:34.011 **INTRUSION** | `front INTRUSION on one scan: 24 ray(s) inside the contour, nearest 0.721 m (seq=425 stamp=216.300000)` |
| 3 | 22:19:41.998 move back to (10.5, 0) | 42.285 | 22:19:42.509 **CLEAR** | `front CLEAR after 3 consecutive fully-valid fully-clear scans (seq=509)` |
| 4 | 22:19:50.287 **move to (4.5, 0)** — fork corridor | 50.586 | 22:19:50.621 **INTRUSION** | `rear INTRUSION on one scan: 11 ray(s) inside the contour, nearest 1.683 m (seq=589 stamp=232.700000)` |
| 5 | 22:19:58.606 move back to (10.5, 0) | 58.902 | 22:19:59.138 **CLEAR** | `rear CLEAR after 3 consecutive fully-valid fully-clear scans (seq=673)` |

Step 1 is the control and is the reason the other four mean anything: an
object the scanner can see but the **field** excludes produces no
verdict. Steps 2 and 4 exercise **both devices** — the drive corridor is
the front device's to watch, the fork corridor the rear device's.

### 4.2 The OSSD-equivalent pair at the transition

Each per-device evaluation forms `(a_clear, b_intrusion)` from **two
separate accumulators in one pass**, carried with the sequence number and
the triggering scan's stamp in one record. A record where `a == b` is a
discrepancy, is a device-evaluation fault on the spot, and reads
intrusion. **Zero discrepancies were recorded in any run of this brief**
— across 673, 603 and 244 scans per device in the three longest sessions,
no `OSSD-equivalent DISCREPANCY` line appears in any log.

Stated flatly, as the design requires: **that buys shape, not
integrity.** Both channels are computed by one process from one scan and
share every failure of the rays and of the process. No Category follows
from it.

### 4.3 The consumer's view — the writer's session log

Every one of the four transitions appears in the writer's log with
source **`FIELD`**, which is exactly what SPEC §7.6 says distinguishes
criterion-(a) evidence from the operator form:

```
22:19:34.089Z | FIELD | ZONE 0 -> ZoneDeviceCircuitClosed := False (intrusion or evaluation fault, circuit open)
22:19:42.591Z | FIELD | ZONE 1 -> ZoneDeviceCircuitClosed := True  (field clear, circuit closed)
22:19:50.690Z | FIELD | ZONE 0 -> ZoneDeviceCircuitClosed := False (intrusion or evaluation fault, circuit open)
22:19:59.180Z | FIELD | ZONE 1 -> ZoneDeviceCircuitClosed := True  (field clear, circuit closed)
```

**No `OPERATOR` line appears anywhere in the writer's session.** The zone
channel was owned by the field link from the first connection to the last.

**What this does NOT show, and it is the largest gap in this file.** The
chain is demonstrated as far as `ZoneDeviceCircuitClosed` at the writer.
It is **not** carried through to `ZoneStopDemand` in
`InstF_Forklift_Safety`, because that observation is made in the
consumer's view at a watch table under activated safety mode, and no
watch table was opened by this brief. **Criterion (a) is therefore not
closed by this file**; what is closed is the half of the chain that did
not exist yesterday.

### 4.4 Clear again, and the asymmetric debounce

Intrusion asserts on **one** scan; clear requires **three consecutive
fully-valid, fully-clear scans**. Measured against the moment the
`set_pose` call returned:

| Transition | set_pose returned → node verdict |
|---|---|
| into the drive corridor | **16 ms** |
| out of the drive corridor | **224 ms** |
| into the fork corridor | **35 ms** |
| out of the fork corridor | **236 ms** |

The two "out" figures contain the deliberate 0.30 s clear debounce and
the two "in" figures do not, which is the asymmetry working. Each is
**one draw**, not a bound (LESSONS 2026-08-05).

---

## 5. Failure behaviour, exercised

Session `field-evaluation-20260805T223157Z-pid140266.log`.

### 5.1 One scanner killed — the union demands a stop

The stack's single `ros_gz_bridge` carries both scanners, so a throwaway
relay was interposed on the rear channel and the field evaluation started
with its rear subscription remapped onto it. **Killing the relay is then
a genuine per-device death**: one scanner's channel stops, the other
keeps publishing.

| Event | Issued | Observed | Delay |
|---|---|---|---|
| `SIGKILL` the rear channel | 22:32:08.969 | `INTRUSION - rear: scan stamp age 0.308 s outside [0, 0.30] s` at 22:32:09.190 | **221 ms** |
| `ZONE 0` sent | | 22:32:09.197 | |
| writer applied it | | 22:32:09.233 | |
| rear channel restored | 22:32:14.972 | `CLEAR - both devices clear` at 22:32:15.440 | **468 ms** |

**The healthy device's verdict is still computed and logged**, so the
evidence names *which* device failed — the reason string is
`rear: …` alone, never a blanket failure. That is §8 rule 4 exactly: the
union is the coverage, and one scanner is never enough to keep driving.

An earlier session tested the same rule from the other end: the node
started with the rear subscription pointed at a topic nothing publishes
at all. The front device built its contour, went CLEAR and stayed
healthy; the aggregate never left INTRUSION, with the reason
`rear: no scan yet received`.

### 5.2 The empty horizon — the 2026-07-29 lesson, tested rather than asserted

**A 24 × 16 m walled arena cannot produce an all-`inf` scan**, so the
case the 2026-07-29 defect is about was exercised **by construction**,
driving `DeviceEvaluation` directly with crafted scans. Twenty cases,
verbatim output:

```
empty-horizon and validity check, 275 rays, window 0.10..5.50 m
----------------------------------------------------------------------------------------------------
every ray +inf (the empty horizon)                         front  CLEAR     -> clear
every ray +inf (the empty horizon)                         rear   CLEAR     -> clear
every ray NaN                                              front  INTRUSION -> fault
every ray -inf                                             front  INTRUSION -> fault
every ray 0.05 m (finite, below range_min)                 front  INTRUSION -> fault
every ray 6.00 m (finite, above range_max)                 front  INTRUSION -> fault
every ray 5.50 m (finite, exactly range_max)               front  CLEAR     -> clear
  [front] deepest live ray is index 271, bearing +134.49 deg, boundary 3.925 m
inf everywhere except ONE ray at 1.96 m (INSIDE the boundary) front  INTRUSION -> not-clear
inf everywhere except ONE ray at 5.50 m (OUTSIDE the boundary) front CLEAR    -> clear
inf everywhere except ONE NaN on that same live ray (0.4%)  front  INTRUSION -> not-clear
  [rear] deepest live ray is index 274, bearing +137.50 deg, boundary 2.913 m
inf everywhere except ONE ray at 1.46 m (INSIDE the boundary) rear  INTRUSION -> not-clear
inf everywhere except ONE ray at 4.37 m (OUTSIDE the boundary) rear CLEAR     -> clear
inf everywhere except ONE NaN on that same live ray (0.4%)  rear   INTRUSION -> not-clear
inf everywhere except ONE ray at 0.50 m INSIDE the rear clip band rear CLEAR  -> clear
inf everywhere except ONE NaN INSIDE the rear clip band (0.4%) rear CLEAR     -> clear
inf everywhere except 10 NaN inside the rear clip band (3.6%) rear CLEAR      -> clear
inf everywhere except 20 NaN inside the rear clip band (7.3%) rear INTRUSION  -> fault
inf everywhere, stamps FROZEN                              front  INTRUSION -> frozen-stamps
inf everywhere but only TWO scans (debounce needs three)   front  INTRUSION -> not-clear
----------------------------------------------------------------------------------------------------
```

Reading the four lines that matter most:

- **An empty horizon reads CLEAR** on both devices. A `+inf` return is a
  measurement — clear to `range_max` — and the field verdict needs no
  finite return anywhere.
- **Every other way a ray can fail reads INTRUSION**: NaN, `-inf`, finite
  below `range_min`, finite above `range_max`. A single NaN on a live
  ray, 0.4 % of the scan, is already an intrusion of that field; the 5 %
  threshold is a separate thing and raises a *device fault*, at 7.3 % and
  not at 3.6 %.
- **A ray inside a clipped sector raises nothing**, distance or NaN
  alike, because there is no field there to be uncertain about. That is
  the clip behaving as geometry.
- Frozen stamps and an incomplete debounce both read INTRUSION.

The one label to read carefully: the "OUTSIDE the boundary" front case
was clamped to `range_max` 5.50 m, not the 5.89 m the label computes.

**Live corroboration.** At the clear baseline the majority of every scan
is already `inf` and the aggregate is CLEAR: front **191 inf / 84 finite
/ 0 NaN**, rear **212 inf / 63 finite / 0 NaN**, measured by an
independent probe over 200 messages per device.

### 5.3 The evaluation itself killed — the consumer converts the silence

| Event | Issued | Observed in the **writer's** log | Delay |
|---|---|---|---|
| `SIGKILL` the field evaluation | 22:32:31.002 | `LINK down (stale: no well-formed line for 1000 ms); ZoneDeviceCircuitClosed driven FALSE (open)` at 22:32:31.941 | **939 ms** |

Repeated at the end of the session: stack stopped 22:37:02.231, writer
drove the channel open at 22:37:02.894 (**663 ms**). This node adds
nothing to its own death behaviour, deliberately — the consumer's
contract already converts silence into the demanding value, and §5.4
below is why that turned out to be load-bearing rather than tidy.

### 5.4 THE DEFECT THIS RUN FOUND: the watchdog's tick ran on the clock of the thing it watched

**Symptom.** With the bridge stopped — `SIGKILL` or `SIGTERM`, it made no
difference — the node produced **nothing at all**: no verdict, no log
line, not even a keepalive. Its own freshness rule never fired. Measured
three times:

| Run | Bridge stopped | Node's last output | Writer's stale rule opened the channel |
|---|---|---|---|
| earlier | 22:23:20.485 `SIGKILL` | 22:23:15.344 (nothing after) | 22:23:21.092, **607 ms** |
| run3 | 22:26:15.476 `SIGKILL` | 22:25:38.249 (nothing for the 10 s probed) | 22:26:16.330, **854 ms** |
| run4 | 22:29:08.344 `SIGTERM` | 22:29:01.197 (nothing after) | 22:29:09.329, **985 ms** |

**Characterised, not guessed.** The process was alive throughout: 34
threads, all sleeping, the main thread in `futex_wait_queue_me`, and its
CPU time frozen to the jiffy (`utime/stime` 875/27 unchanged across 3 s).

**Attributed, not assumed.** The first hypothesis was an rmw or Fast-DDS
deadlock on abrupt participant loss. It was wrong, and one observation
killed it: `obstacle_zone.py` — an rclpy node in the same process tree
subscribing to the **same topic from the same bridge** — kept reporting
`stop zone occupied: min_distance=0.000 reason=scan stale` every 5 s
throughout both events. The stack was fine. The bug was mine.

**Cause.** The evaluation tick was a plain `create_timer`, which on a
node with `use_sim_time:=true` runs on the **simulation clock** — and
`/clock` is carried by **the same `ros_gz_bridge` process that carries
both scanner channels**. So the failure that stops the scans is exactly
the failure that stops the timer meant to detect it, and the node waits
for ever on a tick that can never become ready.

`obstacle_zone.py` survived because the launch does not give it
`use_sim_time`. Its own docstring already states the neighbouring rule —
*"a watchdog that trusts the timestamp of the thing it is watching is not
a watchdog"* — and this defect is that rule one level up: **a watchdog
whose TICK runs on the clock of the thing it is watching is not a
watchdog either.**

**Fix, and the proof it works.** The tick now runs on
`Clock(clock_type=ClockType.STEADY_TIME)`, which nothing in the observed
system can stop. `use_sim_time` stays on, because the design's rule 1
compares the scan's simulated stamp against the ROS clock and that
comparison needs one time base. Re-run:

| Event | Issued | Observed | Delay |
|---|---|---|---|
| `SIGTERM` the bridge — both devices die | 22:32:22.980 | `INTRUSION - front: nothing received for 0.343 s (limit 0.30 s, this node's own monotonic clock); rear: nothing received for 0.333 s` at 22:32:23.240 | **260 ms** |
| `ZONE 0` sent | | 22:32:23.243 | |
| writer applied it | | 22:32:23.292 | |
| one tick later, the frozen clock named in its own right | | `the simulation clock has not advanced for 0.300 s of this node's own steady time` | |

**Which rule actually fired is the point.** It was **not** the design's
§8 rule 1. Rule 1 compares `now_ros - stamp`, and `/clock` froze at the
same instant the scans stopped, so that difference was pinned at its last
value and rule 1 read *fresh* for ever. What fired was the **monotonic
receipt-age test**, which this build added beyond the design's five rules
"in the demanding direction" — and which turns out to be the only rule in
the set that can see this failure at all. A **frozen-simulation-clock
rule** was added in the same pass, also on steady time, so the condition
is named rather than merely survived.

**Two things this leaves on the record.** First, the architecture caught
the defect before the defect could matter: through all three wedged runs
the zone channel was driven open in 0.6–1.0 s by the consumer's stale
rule, which is FIELD-EVALUATION.md §2's row *"this is the evaluation's
own death handled by its consumer, in the demanding direction"* doing
exactly its job. Second, that is **not** a reason to be relaxed about it:
a wedged evaluation reports nothing, and the only reason the vehicle was
covered is that somebody else's contract was written for it.

---

## 6. R3 and R8, respected — what the run shows and what it cannot

**R8 — the rear device's self-return band — is respected as field
geometry, and the run confirms the band is really there.** At the clear
baseline the rear device's **nearest finite return is 0.101 m**: the fork
carriage, 0.09–0.11 m from the housing, precisely where
`EVIDENCE_SENSOR_COVERAGE.md` §13.3 predicts it. The front device's
nearest finite return is **1.084 m** — `rear_wheel_left` at index 274,
the single self-return ray §13.6 measures, to the millimetre. Both sit
inside their device's clipped band and neither produces an intrusion,
while **214 of the rear device's 275 rays keep a live field** and the
front keeps all 275. The band is not filtered out of the samples: it is
still measured, still classified, still logged as the nearest return.

**R3 — load occlusion — is respected by making no claim, and the run
proves the residual rather than asserting it.** A 1.20 × 0.80 × 0.14 m
load was spawned on the tines at world (5.60, 0, 0.15), crossing the
0.150 m scan plane:

| Event | Issued | Observed |
|---|---|---|
| load placed on the tines | 22:36:20.456 (returned .982) | `rear INTRUSION on one scan: 24 ray(s) inside the contour, nearest 0.112 m` at 22:36:21.011; writer applied `ZONE 0` at 22:36:21.091 |
| load moved out of the arena | 22:36:31.002 (returned .287) | `CLEAR` at 22:36:31.521; writer applied `ZONE 1` at 22:36:31.583 |

So **phase 1 with a load in the plane is permanently intruded**: the
vehicle's own load stands inside the vehicle's own protective field, 24
rays of it, and the field cannot be cleared until the load leaves. That
is the demanding direction, and it is also exactly why the design does
not try to watch through a load: FIELD-EVALUATION.md §5 case C excludes
the fork sector 164.5–204.4° outright and mitigates with the SC-13 creep
cap, which is a **speed** answer and not a field answer. **Phase 1 is
unloaded-only by construction**, case C is phase 3, and nothing here
claims personnel detection in the load direction.

**R1 and R2, restated because this run does not clear them either.** R1's
carriage-occluded patch (169.4–174.4°, ≈0.17 m wide) sits inside the
fork-direction field and no mount angle removes it; a single centred limb
in that patch is the accepted residual. R2's lift window — carriage
travel 0.05–0.10 m — was **avoided**, not handled: every run stood at
travel 0.000 m. Parked in that window the tines cross the plane at
bearings the clip does not cover, and the fork corridor would read
permanently intruded. Demanding direction again, and phase 3's to fix.

---

## 7. Timing observed, and what each figure is a sample of

**Every figure below is a draw, not a bound** (LESSONS 2026-08-05). None
is a response time, a stopping distance, or a characteristic of any
machine.

| Quantity | Observed | What it is |
|---|---|---|
| Scan period, both devices | 0.100 s, min = mean = max over 200 messages | the declared 10 Hz, reproduced |
| Scan stamp age at the node | front mean **0.014 s**, max 0.064 s; rear mean **0.024 s**, max 0.032 s | one 20 s window per device, on this host with the stack running |
| `set_pose` returned → intrusion verdict | **16 ms** and **35 ms** | two draws, two devices |
| `set_pose` returned → clear verdict | **224 ms** and **236 ms** | two draws; contains the 0.30 s clear debounce |
| Per-device death → aggregate verdict | **221 ms**, **260 ms** | two draws, against the design's 0.30 s freshness window |
| Node `SEND` → writer `FIELD` | 16, 36, 42, 43, 49, 55, 80 ms | **NOT a transit measurement**: two unsynchronised clocks, plus up to one 50 ms writer cycle. It does not isolate the design's t3 = 10 ms budget and must not be quoted against it |
| Evaluation death → writer opens the channel | **663, 854, 939, 985 ms** | four draws, against the writer's `FIELD_LINK_STALE_MAX` = 1 s |

The design's §11 measurement 1 (scan-stamp → verdict-formed age over
≥10 min) and measurement 2 (a one-clock `ZONE`-to-receipt figure) are
**still owed**; nothing above discharges either.

---

## 8. What this run does NOT establish

1. **Criterion (a) is not closed.** The chain is shown from a Gazebo
   intrusion to `ZoneDeviceCircuitClosed` at the writer. It is not shown
   through to `ZoneStopDemand` latching in `InstF_Forklift_Safety`, nor
   to an observable vehicle stop. No watch table was opened.
2. **Nothing about safety.** No protective field in the normative sense,
   no OSSD, no response time, no PL, no Category, no PFH. A polygon test
   in Python over a bridged rendered scan is not a safety function.
3. **No verified normative coefficient.** The 1.35 m depth inherits
   FIELD-EVALUATION.md §4's **PROVISIONAL** derivation: the ISO 13855
   framing comes from secondary sources, the project has no access to the
   text, the applicability of the Kp intruder-advance term to a
   vehicle-carried field is unresolved, and three of the eight stages of
   T = 0.46 s are budgets rather than measurements. The demanding reading
   is carried.
4. **Phase 1 only.** No warning field, no case selection, no speed
   enforcement, no loaded case, no lift-dependent contour, no flank
   fields — the contour is two corridors and the lateral 1.02 m flank of
   cases A and C does not exist.
5. **One pose, one world, no motion.** The vehicle never moved. Nothing
   here says what the field does while the vehicle drives, and the 0.05 m
   steering-deviation allowance in the corridor half-width is still the
   unmeasured budget §11 measurement 7 names.
6. **One host, one session.** Twenty cores, WSL2, llvmpipe rendering.
   Every timing is from that machine on that evening.
7. **Nothing about the writer's own correctness.** `bridge/` was read and
   run, never edited or tested; its log is quoted as the consumer's view.

---

## 9. Corrections and surprises found while running

1. **The design's §6 rear clip band, applied verbatim, leaves two
   measured self-return rays inside the field** and holds the verdict at
   INTRUSION for ever (§2 above). Corrected against the measurement the
   design's own rule points at; a correction to §6's table is requested.
2. **The watchdog's tick ran on the clock of the thing it watched**
   (§5.4). Found by killing the bridge, attributed by noticing that
   `obstacle_zone.py` survived the identical event, fixed with a steady
   clock, and re-proven. The rule earned: *a freshness test is only as
   alive as the timer that evaluates it.*
3. **The node's first link code blocked its own executor.** A
   `socket.create_connection(timeout=2.0)` with no writer listening
   stalled the single-threaded executor for the whole timeout; the scan
   and `/clock` queues backed up behind it and the node reported **its
   own** freshness rule violated at 0.838–0.996 s of stamp age, while an
   independent probe on the same two topics in the same run measured
   0.016 s and 0.027 s. **The node was failing itself for a defect
   entirely in its link code.** Fixed with a non-blocking `connect_ex`
   polled by `select()` at zero timeout. LESSONS 2026-07-29 states this
   for a harness; it binds harder on a node whose other job is to notice
   that a scanner has gone silent.
4. **The transition log flooded when a device stayed dead.** The
   "verdict unchanged, reason changed" line compared a *reason string*
   containing a live scan age, so it differed every tick: one killed
   device produced **213 near-identical lines in eleven seconds**,
   burying the four line classes that are criterion-(a) evidence. Fixed
   by comparing a stable verdict **key** and carrying the prose once.
   `PING` lines were likewise removed from the log — 88 of them against 6
   verdict lines in the first session — and are counted at `EXIT`
   instead.
5. **`scripts/sensor_coverage.py` no longer runs against
   `model.sdf`.** `load_model` reads `lidar/scan/horizontal` for every
   `<sensor>` in the file, and the IMU has no `<lidar>`, so it dies with
   `AttributeError: 'NoneType' object has no attribute 'findtext'` before
   printing anything. That is the tool the whole of
   `EVIDENCE_SENSOR_COVERAGE.md` was produced with, and it cannot
   currently reproduce a line of it. **Not fixed by this brief** — it is
   outside the deliverable — and raised in the m5-12b report. The plan
   outline used here was extracted with the tool's own helper functions,
   bypassing `load_model`.
6. **A closed Windows port times out rather than refusing**, so the
   node's "connect attempt failed: timed out" before the writer was
   started reads like a firewall block and is not one (§3).

---

# EVIDENCE — the warning field, phase 2, and the corrected clip band (m5-47, 2026-08-06)

**This section was written as each result landed, not afterwards.** It is
appended; nothing above it was edited, and every figure below comes from
this run.

**This is not a safety claim, in whole or in part** (ADR 0011 D5). What
ran is still a **model of what a safety-rated scanner does inside its own
housing**, in Python, on two rendered depth images that crossed a bridge
and a ROS graph. No Category, no Performance Level, no SIL, no PFH, no
channel count and no diagnostic coverage is claimed, achieved or implied.
Every PL and Category in the documents behind it is a **PLr target**.
**SF-04, the warning function this section builds, carries no PL claim at
all** and is backed unconditionally by SF-03. No depth, response time or
stopping distance recorded here is a figure any machine is characterised
by.

---

## 10. What this session did, and the two things it was for

| # | Deliverable | Where |
|---|---|---|
| 1 | **§6's rear clip band corrected** — the design now reads −133.0°…−71.8°, and carries the rounding rule that produced it | `FIELD-EVALUATION.md` §6 |
| 2 | **The warning field built** — depth **derived** at 3.35 m, verdict on a non-safe ROS topic, SF-04's 2 s clear-hold | `FIELD-EVALUATION.md` §3, §6.1, §8, §12; `config.yaml`; `scripts/field_evaluation.py` |

**The clip-band correction, stated as a correction.** m5-12b built against
the measured index set and **requested** the change rather than editing
another brief's deliverable; the design has now been corrected to what the
node already did, so the two agree for the first time. The withdrawn band
−131.5°…−72.3° rounded a measured −131.48°…−72.26° **outward at one end
and inward at the other**, and the inward end left index 5 (self-return
0.780 m against a 1.001 m boundary) and index 65 (0.164 m against 2.183 m)
inside the field — either one alone a permanent INTRUSION. Two defects,
not one: the rounding **direction**, and the fact that the **angle** was
quoted where the **index set** is the measurement (§13.2's index set is
5..65 while −131.48° is the bearing of index 6). The rule now written into
§6 and into `config.yaml`: **a geometric boundary derived from a
measurement is rounded in the direction that excludes, never for
readability.**

---

## 11. Where 3.35 m comes from — derived, never chosen

The requirement, and it is the whole derivation: **an intruder standing on
the warning boundary must not reach the protective boundary before the
vehicle has finished slowing to the creep ceiling.**

```
W(v) = D + v*T_w + (v^2 - v_c^2)/(2a) + Kp*[T_w + (v - v_c)/a]
```

| Term | Value | Source |
|---|---|---|
| D | 1.35 m | the protective depth **in force** (§4 above, `config.yaml`) |
| T_w | **0.35 s** | `FIELD-EVALUATION.md` §3's warning chain, summed per stage: 100 ms scan + 30 ms evaluate + 50 ms carrier + 20 ms standard-program scan + 50 ms bridge + 100 ms gate. Shorter than the protective T = 0.46 s by exactly the two stages the warning path does not contain — the writer's 50 ms cycle and the F-OB's 100 ms |
| a | 0.50 m/s² | the envelope gate's measured ramp, n = 4 |
| v_c | 0.30 m/s | the creep ceiling (SC-13, SF-10) |
| Kp | 1.6 m/s, **provisional** | inherited from §4 **with its provisionality**; the demanding reading is carried |
| v | 0.60 m/s | `nav2.yaml` `max_velocity` 0.60 forward / `min_velocity` −0.55 reverse — the worst of the two sizes one static contour |

**W(0.60) = 1.35 + 0.210 + 0.270 + 1.520 = 3.350 m**, and that number was
read back out of the running node rather than retyped into it:

```
2026-08-06T08:55:34Z | START | warning contour: corridors x -5.225..4.210 m,
  y -0.550..+0.550 m in the vehicle frame - the SAME outline and the SAME
  half width grown by the warning depth 3.35 m, derived in section 6.1 as
  W = D + v*T_w + (v^2-v_c^2)/2a + Kp*[T_w+(v-v_c)/a]
    = 1.35 + 0.210 + 0.270 + 1.520 at v = 0.60 m/s
```

**Four of T_w's six stages are budgets**, exactly as three of T's eight
are, and `FIELD-EVALUATION.md` §11 gained measurements 8–11 naming each.
**Measurement 11 is the one that can falsify this depth** — drive the
vehicle into a warning-field entry and measure whether it is actually at
or below v_c by the protective boundary — and it is **not taken here**:
the vehicle never moved in this run.

**Where the derived boundary does not fit, and it is not smoothed.** §4's
detection-capability floor is 4.01 m for a 70 mm object at 1.00365°/ray:

| Direction | Worst in-corridor point from its device | Verdict |
|---|---|---|
| drive (+x), front device | √((0.16+3.35)² + 1.0²) = **3.65 m** | inside the floor, **fits** |
| fork (−x), rear device | √((1.175+3.35)² + 1.0²) = **4.63 m** | **outside by 0.62 m** |

At 4.63 m the ray spacing has opened to **81 mm**, so a 70 mm object is
not guaranteed to be struck at the far corner of the fork-direction
warning field. That is a **detection-capability** shortfall and not a
range one — 4.63 m is inside the class's 4.95 m reach and inside the
model's 5.50 m `range_max`. It is acceptable for this field and for one
reason only: SF-04 carries **no PL claim** and is backed unconditionally
by SF-03, whose field is inside the floor everywhere. Nothing was resized
to hide it; resizing down to 4.01 m would silently deliver less speed
reduction than the derivation requires.

**One consequence of the depth that only showed up when it ran.** At the
diagonal bearings the derived warning boundary exceeds the sensor's own
window and is clamped to `range_max`: the front device's warning contour
reads `boundary 0.100..5.500 m` where its protective contour reads
`0.100..3.925 m`. So at those bearings the warning field **is** the whole
sensor window, and a finite return at exactly `range_max` reads as
occupation. That is the §6.1 saturation, appearing at the corridor corners
at 0.60 m/s rather than only at the 1.00 m/s ceiling.

---

## 12. Environment, and that the simulator was free

| Item | Value |
|---|---|
| Date, run window (UTC) | 2026-08-06, `08:51` to `09:02` |
| Host | **WSL2 on the owner's Windows machine** — the target platform, not a container. Ubuntu, kernel `5.15.167.4-microsoft-standard-WSL2`, 20 cores, 15 GiB, Python 3.12.3 |
| ROS 2 | Jazzy, `/opt/ros/jazzy` |
| Gazebo | **Sim 8.11.0**, `gz sim -r -s`, headless, llvmpipe (`libEGL … falling back to kms_swrast` in the launch log, as always on this host) |
| Isolation | `GZ_PARTITION=m547a` **and** `ROS_DOMAIN_ID=79`. Both, because gz transport is not DDS |
| **Simulator free before starting** | Checked at **2026-08-06 08:51:24Z**, and this is the record: `pgrep -af "gz sim\|gzserver"` returned **nothing**; the only ROS process on the machine was a leftover `ros2-daemon --ros-domain-id 57`, a different domain from this run's 79. Load average 0.01/0.02/0.26. Serialised: no other agent ran the simulator in this window, and the daemon was stopped at teardown |
| World | `sim/worlds/forklift_arena.sdf`, md5 `c7733d22ee66ad734c7e3ee828d4a464`, **unedited** |
| Model | `agv/forklift/model.sdf`, md5 `de5edf370986bd77312204e297f4a5c6`, **unedited by this brief** |
| Vehicle pose | spawned at world **(7.000, 4.000)**, yaw 0, carriage travel 0.000 m, and **never driven** — it stood there for the whole session. The R2 lift window is not entered |
| Consumer | **none.** No stand-in writer, no PLCSIM instance and no PLC ran in this session; see §16 |
| Node session log | `agv/forklift/evidence/field_evaluation/field-evaluation-20260806T085534Z-pid164982.log` (97 lines, committed) |

**Why the vehicle stands at (7.0, 4.0) and not at m5-12b's (7.0, 0.0) —
and the first corroboration of the depth, which was an accident.** The
first launch of this session used the phase-1 pose, and the warning
verdict would not release. It was not a defect: an independent probe run
against the live scans showed the arena's `AisleCrate` **inside the
warning field and outside the protective one**, 13 rear rays of it —

```
[rear] 13 ray(s) inside the WARNING contour
   idx  80 bearing  -57.21 deg  r 3.937 m  warn bnd 4.630  prot bnd 2.583
           vehicle frame (-4.55, +0.38)  world (+2.45, +0.38)
   ... 12 more, all on the crate's +x face at world x = 2.45
```

The crate's near face sits 4.55 m behind the vehicle, inside the 5.225 m
rear warning boundary and well outside the 3.225 m protective one. That is
the phase-2 discriminator occurring by itself, before a single stimulus
was issued, and it is the reason the vehicle was moved to a pose where
both fields start clear rather than the field being adjusted to the pose.

---

## 13. THE STIMULUS SEQUENCE — real objects, in the simulator, both fields

A 0.30 × 0.30 × 0.60 m box was created in the running world and then
**moved** with `gz service /world/forklift_arena/set_pose`. No value was
typed anywhere in the chain.

**Every reposition was READ BACK before the run was allowed to continue.**
`set_pose` returns `data: true` for a well-formed *call*, not for a moved
*entity* (LESSONS 2026-08-06), so the driver re-read the pose through
`gz model -m intruder -p` after every move and would have aborted — not
repaired — on any mismatch. The entity id (**130**) was resolved from that
same read-back and sent in the request beside the name. **All nine
read-backs matched to within 0.02 m; none was rejected.**

The geometry the sequence is aimed at, with the vehicle at (7.0, 4.0):

| Boundary | World x | Corridor |
|---|---|---|
| protective | **3.775** (rear) … **9.210** (front) | y 3.45 … 4.55 |
| warning | **1.775** (rear) … **11.210** (front) | y 3.45 … 4.55 |

| # | Stimulus | `set_pose` returned | Node verdict | Delay | What it proves |
|---|---|---|---|---|---|
| **S1** | box at **(10.0, 6.0)** — 2.77 m from the front device, plainly visible, 1.45 m outside the corridor | — | **no verdict of any kind**, 10 s | — | **CONTROL A.** The field, not the sensor, is what discriminates |
| **S2** | move to **(10.0, 4.0)** — near face 9.85, outside protective 9.21, inside warning 11.21 | 08:59:20.971 | 08:59:21.074 `front warning field OCCUPIED on one scan: 9 ray(s) inside the warning contour, nearest 2.173 m (seq=2237)`; aggregate at .096 | **103 ms** | **AT-04's first observation: warning only.** No `AGGREGATE` line — the protective verdict is untouched |
| **S3** | move to **(8.5, 4.0)** — near face 8.35, inside protective | 08:59:31.457 | 08:59:31.497 `AGGREGATE INTRUSION - front: field not clear` | **40 ms** | the protective field still trips, and trips **on top of** an already-occupied warning field: no second warning line, because the verdicts are nested |
| **S4** | move back to **(10.0, 4.0)** | 08:59:41.931 | 08:59:42.207 `AGGREGATE CLEAR`; **no warning release** | **276 ms** | **the asymmetry, and the point of the whole design**: the stop releases and the speed reduction **holds** |
| **S5** | move to **(10.0, 6.0)** — all clear | 08:59:52.398 | hold started .678; `front warning field RELEASED after the SF-04 clear-hold: 2.028 s` at 08:59:54.707 | **2.028 s hold** | SF-04's 2 s clear-hold, measured on the node's own steady clock |
| **S6** | move to **(11.6, 4.0)** — near face 11.45, **0.24 m outside** the warning boundary, 3.75 m from the front device | 09:00:05.845 | **no verdict of any kind**, 12 s | — | **CONTROL B.** A sharp control: the box is in the corridor, in the driving direction, plainly visible, and the boundary discriminates it by 24 cm |
| **S7** | move to **(2.7, 4.0)** — far face 2.85, outside protective 3.775, inside warning 1.775 | 09:00:19.329 | 09:00:19.396 `rear warning field OCCUPIED on one scan: 5 ray(s) inside the warning contour, nearest 3.464 m (seq=2810)` | **67 ms** | the **rear** device's warning field, on its own, with the protective verdict untouched |
| **S8** | move to **(4.5, 4.0)** — inside the rear protective field | 09:00:29.772 | 09:00:29.917 `AGGREGATE INTRUSION - rear: field not clear` | **145 ms** | the rear protective field, re-proven in this session rather than inherited |
| **S9** | move to **(10.0, 6.0)** | 09:00:40.242 | `AGGREGATE CLEAR` at .525 (**283 ms**); `rear warning field RELEASED … 2.029 s` at 09:00:42.524 | | both fields release, in their own orders |

**Both fields therefore have a real Gazebo intrusion and a control case
outside their contour**: protective S3/S8 against controls S1/S6, warning
S2/S7 against controls S1/S6. **S4 is the case neither field has on its
own** — the protective verdict clearing while the warning verdict holds,
which is what makes them two fields rather than one with two names.

Each delay above is **one draw**, not a bound (LESSONS 2026-08-05). The
two "release" figures contain the 0.30 s clear debounce; the two hold
figures contain SF-04's 2 s.

---

## 14. The warning verdict on the wire, and the protective verdict still not on one

`/forklift/warning_field/occupied` [`std_msgs/Bool`], recorded by an
independent subscriber that logs transitions **and rate**:

```
08:55:36.985Z | WATCH | occupied -> the consumer must lower the ceiling   (boot)
08:55:38.943Z | WATCH | clear    -> the ceiling may be released
08:59:21.101Z | WATCH | occupied     (S2, 7 ms after the node's own line)
08:59:54.717Z | WATCH | clear        (S5, after the 2 s hold)
09:00:19.424Z | WATCH | occupied     (S7)
09:00:42.538Z | WATCH | clear        (S9)
...
09:01:16.951Z | WATCH | 20.0 msg/s over the last 5.0 s, level=False
```

**20.0 msg/s in every five-second window of the session.** The level is
published at the evaluation tick and **not** on transitions, on purpose:
a consumer that republishes the last value it saw would turn this node's
death into a standing order to keep driving fast, so the level's
**absence** has to be visible. Any consumer therefore owes a stale rule of
its own — no message inside its window means **occupied**.

**The graph, read from the running node rather than from the code that
was supposed to produce it** (LESSONS 2026-08-06):

```
$ ros2 node info /field_evaluation
  Subscribers:
    /clock, /forklift/safety_scanner_front/measurement,
    /forklift/safety_scanner_rear/measurement
  Publishers:
    /forklift/warning_field/occupied: std_msgs/msg/Bool
    /parameter_events, /rosout
```

**One added publisher, and it is the warning verdict.** The protective
verdict appears nowhere in the graph, on either transport, exactly as the
m5-06 ruling requires; `check_sensor_frames.py` §4's name test is also
satisfied by construction, because the topic contains no `safe`, `ossd` or
`protective` token — which keeps that check honest rather than merely
quiet.

**The protective verdict on its own link.** A **throwaway TCP sink** —
not the stand-in writer, and it writes to no PLC — accepted the link and
timestamped every line:

```
08:56:27.752Z | SINK | connection from ('127.0.0.1', 41062)
08:56:27.809Z | SINK | ZONE 1   (after 0 PING keepalives)
08:59:31.505Z | SINK | ZONE 0   (after 348 PING keepalives)   <- S3
08:59:42.214Z | SINK | ZONE 1   (after 369 PING keepalives)   <- S4
09:00:29.923Z | SINK | ZONE 0   (after 459 PING keepalives)   <- S8
09:00:40.531Z | SINK | ZONE 1   (after 479 PING keepalives)   <- S9
```

Four protective transitions on the wire, each 6–8 ms after the node's own
`AGGREGATE` line, and **no `ZONE` line for any warning transition** — the
two roads stay separate. 728 lines were sent in the session, 721 of them
`PING` keepalives, counted at `EXIT` rather than logged individually.

---

## 15. The failure behaviour, re-exercised with the warning field in it

**Both fields, one rule 0.** The `ros_gz_bridge` carrying both scanners
and `/clock` was `SIGTERM`ed:

| Event | Issued | Observed | Delay |
|---|---|---|---|
| `SIGTERM` the bridge | 09:01:38.652 | `WARNING \| warning field OCCUPIED - front: nothing received for 0.309 s (limit 0.30 s, this node's own monotonic clock)` at 09:01:38.934 | **282 ms** |
| | | `AGGREGATE \| INTRUSION - front: nothing received for 0.309 s …` at 09:01:38.940 | **288 ms** |
| `ZONE 0` at the sink | | 09:01:38.944 | |
| the topic level | | `WATCH \| occupied` at 09:01:38.940, and **the node kept publishing at 20.0 msg/s while blind** | |
| the frozen clock, named in its own right | | `the simulation clock has not advanced for 0.350 s of this node's own steady time` at 09:01:39.043 | |

Three things this run puts on the record:

1. **The steady-clock watchdog still fires**, and it is still the only
   rule that can see this failure: `/clock` froze with the scans, so the
   design's §8 rule 1 (`now_ros − stamp`) reads *fresh* for ever. The
   2026-08-06 defect has not come back with the second field.
2. **A blind node reports the demanding level rather than going silent.**
   The warning topic kept carrying `occupied` at 20 Hz for as long as the
   node lived. Silence is reserved for the node's own death, where the
   consumer's stale rule is what must convert it.
3. **The warning verdict went demanding 6 ms before the protective one**,
   which is an artefact of evaluation order in one tick and not a
   property to rely on. Both are inside one 50 ms tick.

**The empty horizon, and every other way a ray can fail, re-tested with
the warning field added.** A 24 × 16 m walled arena cannot produce an
all-`inf` scan, so the case the 2026-07-29 defect is about was again
exercised **by construction**, driving `DeviceEvaluation` directly with
crafted scans — now reading **both** verdicts. Verbatim:

```
m5-47 validity ladder, 275 rays, window 0.10..5.50 m, protective depth 1.35 m, warning depth 3.35 m
====================================================================================================
every ray +inf (the empty horizon)              front  prot CLEAR     -> clear      warn CLEAR    -> warn-clear
every ray +inf (the empty horizon)              rear   prot CLEAR     -> clear      warn CLEAR    -> warn-clear
every ray NaN                                   front  prot INTRUSION -> fault      warn OCCUPIED -> warn-fault
every ray -inf                                  front  prot INTRUSION -> fault      warn OCCUPIED -> warn-fault
every ray 0.05 m (finite, below range_min)      front  prot INTRUSION -> fault      warn OCCUPIED -> warn-fault
every ray 6.00 m (finite, above range_max)      front  prot INTRUSION -> fault      warn OCCUPIED -> warn-fault
every ray 5.50 m (finite, exactly range_max)    front  prot CLEAR     -> clear      warn OCCUPIED -> warn-occupied
  [front] deepest live ray index 271, bearing +134.49 deg, protective boundary 3.925 m, warning boundary 5.500 m
ONE ray at 3.83 m - inside the PROTECTIVE boundary   front  prot INTRUSION -> not-clear  warn OCCUPIED -> warn-occupied
ONE ray at 4.71 m - BETWEEN the two boundaries       front  prot CLEAR     -> clear      warn OCCUPIED -> warn-occupied
  [front] a ray beyond the warning boundary 5.500 m cannot be expressed: it exceeds range_max 5.50 m
ONE NaN on that same live ray (0.4%)                 front  prot INTRUSION -> not-clear  warn OCCUPIED -> warn-occupied
  [rear] deepest live ray index 274, bearing +137.50 deg, protective boundary 2.913 m, warning boundary 4.915 m
ONE ray at 2.81 m - inside the PROTECTIVE boundary   rear   prot INTRUSION -> not-clear  warn OCCUPIED -> warn-occupied
ONE ray at 3.91 m - BETWEEN the two boundaries       rear   prot CLEAR     -> clear      warn OCCUPIED -> warn-occupied
ONE ray at 5.01 m - beyond the WARNING boundary      rear   prot CLEAR     -> clear      warn CLEAR    -> warn-clear
ONE NaN on that same live ray (0.4%)                 rear   prot INTRUSION -> not-clear  warn OCCUPIED -> warn-occupied
ONE NaN INSIDE the rear clip band (0.4%)             rear   prot CLEAR     -> clear      warn CLEAR    -> warn-clear
20 NaN inside the rear clip band (7.3%)              rear   prot INTRUSION -> fault      warn OCCUPIED -> warn-fault
inf everywhere, stamps FROZEN                        front  prot INTRUSION -> frozen-stamps  warn OCCUPIED -> warn-frozen-stamps
inf everywhere but only TWO scans (debounce needs 3) front  prot INTRUSION -> not-clear  warn OCCUPIED -> warn-occupied
----------------------------------------------------------------------------------------------------
hold test: front ray index 271 at 4.713 m, between the protective 3.925 m and warning 5.500 m boundaries
baseline before occupation: warning occupied = False
warning occupied while a ray sits between the boundaries: True
RELEASED at 2.3 s after the first clear scan (SF-04 hold 2.0 s + 3 debounce scans = 2.3 s expected)
```

The five lines worth reading twice:

- **An empty horizon reads CLEAR on both fields.** A `+inf` return is a
  measurement — clear to `range_max` — and the warning field inherits that
  reading rather than re-opening the 2026-07-29 defect one field over.
- **Every other way a ray can fail reads demanding on both fields**, and
  a single NaN on a live ray is enough on its own.
- **The between-the-boundaries row is phase 2 in one line**: protective
  CLEAR, warning OCCUPIED, from the same scan and the same pass.
- **Nesting held everywhere.** No row reads protective INTRUSION with the
  warning field clear, and the node's own build-time check agrees:
  `front nesting check: 0 ray(s) where the warning boundary is inside the
  protective one (must be 0)`, and the same for the rear.
- **A ray inside a clipped sector still raises nothing**, distance or NaN
  alike, in either field. The clip is geometry, not a filter, for both.

The release is exact: **2.3 s = the 2.0 s SF-04 hold + the three 0.1 s
debounce scans that must precede it.**

---

## 16. What this session does NOT establish

1. **Nothing about safety.** No protective field in the normative sense,
   no warning field in it either, no OSSD, no response time, no PL, no
   Category, no PFH. A polygon test in Python over a bridged rendered scan
   is not a safety function, and SF-04 carries no claim of any kind.
2. **The consumer's view was not observed at all this time.** No
   stand-in writer, no PLCSIM instance and no PLC ran: the protective
   verdict's receipt was recorded by a **throwaway TCP sink on the WSL
   side**, which proves the lines left the node and proves nothing about
   `ZoneDeviceCircuitClosed`. §4.3 above, from 2026-08-05, remains the
   only consumer-view record, and **criterion (a) is still not closed**.
3. **The warning verdict has no consumer at all.** Nothing subscribes to
   `/forklift/warning_field/occupied` except the recorder written for this
   run. The carrier to the PLC (`bridge/`), the node in the model
   (`docs/interfaces/`) and the standard program's lowered ceiling
   (`plc/`) are all requested in the m5-47 report and none of them exists.
   **T_w's stages w3–w6 are therefore budgets against a designed path, not
   a built one**, and the warning field trips **nothing** today.
4. **No verified normative coefficient.** 3.35 m inherits §4's
   **PROVISIONAL** framing whole: the ISO 13855 structure comes from
   secondary sources, the project has no access to the text, the
   applicability of the Kp intruder-advance term to a vehicle-carried
   field is unresolved, and four of T_w's six stages are budgets.
5. **The fork-direction warning boundary is outside the detection
   capability floor** by 0.62 m (§11). Named, not fixed.
6. **One pose, one world, no motion.** The vehicle never moved. Nothing
   here says what either field does while the vehicle drives, and
   measurement 11 — whether 3.35 m actually delivers the reduction it is
   sized for — is untaken.
7. **Phases 1 and 2 only.** No case selection A/B/C, no speed
   enforcement, no loaded case, no lift-dependent contour, no flank
   fields.
8. **One host, one session, single draws.** Every delay in §13 is one
   observation on one evening on one machine.

---

## 17. Corrections and surprises found while running

1. **The design's §6 clip band was corrected rather than worked around**
   (§10). The rule it produced — round a geometric boundary in the
   direction that excludes — is now written in `FIELD-EVALUATION.md` §6
   and in `config.yaml` beside the band itself.
2. **The first launch would not release the warning verdict, and it was
   right not to.** The arena's `AisleCrate` stands 4.55 m behind the
   phase-1 spawn pose: inside the new warning field, outside the
   protective one. Diagnosed with a probe against the live scans before
   anything was changed, and the **vehicle** was moved, not the field
   (§12).
3. **A throwaway sink bound to port 45015 outlived its own stack** and
   the second one failed to bind with `Address already in use`. The node
   handled it exactly as designed — `send failed: Broken pipe`, then
   eleven `Connection refused` reconnect attempts at 1 s, then `up` at
   08:56:27.802 — which incidentally re-exercises the link's own failure
   path, with the first line on the new connection being a `ZONE` line
   (`ZONE 1` at 08:56:27.809, 7 ms after connect).
4. **The rear device's last ingested scan read 4.00 % invalid samples**
   (`EXIT` line), against 0.00 % for the front. It is under the 5 %
   device-fault threshold, so no fault was raised, and it is the scan
   that arrived as the bridge was being killed. Recorded because it is
   the only invalid-sample reading in the session and it is not explained
   here.
5. **`gz service set_pose` was driven with the entity id resolved from a
   read-back**, and every one of the nine moves was confirmed before the
   next step. Nothing had to be discarded, which is the outcome the rule
   exists to make cheap rather than the outcome that proves it unneeded.
