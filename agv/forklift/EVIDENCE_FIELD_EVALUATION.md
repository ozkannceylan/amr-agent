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

---
---

# EVIDENCE — the WARN sender: the warning verdict reaches the stand-in writer (m5-61, 2026-08-06)

**No integrity claim of any kind is made or implied here.** No Category,
Performance Level, SIL, PFH, MTTFd, DCavg or CCF appears below, for this
node, for the link, for the stand-in writer or for anything downstream of
them. The evaluation is a **model** of what a safety-rated scanner does
inside its own housing, running as standard software on a rendered depth
image; the writer is an **engineering stand-in for wiring**, labelled as
such throughout. Every PL and Category named anywhere in this file is a
**PLr target** out of `docs/safety/`, never an achievement.

## 18. What this session was for, in one sentence

`docs/VALIDATION-M5.md` finding **F3**: *nothing sent the `WARN` line*, so
`SafetyInputStandIn.WarningFieldClear` had been **FALSE in every session
that has ever run**, the F-side limit selector
`InstF_Forklift_Safety.WarningFieldClearValid` was permanently FALSE with
it, and the reduced limit was permanently in force. The warning field
itself was built and proven in m5-47; the protective field's sender
already worked over the same 45015 link in the same protocol. This session
built **the missing half of a mechanism that otherwise existed**, and it
is the first time in this project that `WarningFieldClear` has read
**True**.

### 18.1 What was built — three edits, all additive

| File | Change |
|---|---|
| `scripts/field_evaluation.py` | `WriterLink` gained `warn_line()`, `publish_warn()` and `sent_warn`; `service()`, `_poll_connect()` and `_connected()` carry the warning level; `_connected()` sends one `WARN` line after its `ZONE` line; `close()` clears `sent_warn`; `cb_evaluate()` inverts the node's OCCUPIED into the wire's CLEAR once, at the boundary, and publishes on transition **after** the zone line |
| `config.yaml` | `field.link.warn_clear_digit: 1`, `warn_occupied_digit: 0`, with the derivation and the polarity argument beside them |
| this file | sections 18–25 |

**The protocol was not invented.** `bridge/STANDIN-WRITER-DESIGN.md` §3
already defines `WARN 1` / `WARN 0` on 45015 and the writer already parses
it; this node was made to match a receiving end that was built and
running-tested (m5-57). Nothing in `plc/`, `bridge/`, `hmi/` or `docs/`
was written by this brief.

### 18.2 The two disciplines the design had to keep, and where each is proven

| Discipline | Where it lives | Proven in |
|---|---|---|
| **Silence must never be readable as "clear"; a clear verdict is a fresh claim, never an inherited one** | The writer already converts silence into `WarningFieldClear := FALSE` — before the first `WARN` line of a session, and again on every field-link loss. This node adds the other half: after a reconnect the permissive level exists nowhere, so it is **claimed afresh** rather than assumed | §21, the link-loss and reconnect run: `WarningFieldClear` fell **with no `WARN 0` ever sent**, and came back only 2.06 s after the new connection, once the SF-04 clear-hold had run again on the new node |
| **Do not disturb the protective-field path** | The `WARN` line is sent strictly **after** the `ZONE` line, in the same tick, on the same socket; no protective code path was edited | §22: four warning-only intrusions produced **zero** `ZONE` lines, and a protective intrusion run with the sender live reproduced the committed shape exactly |

---

## 19. Environment, and that the machine was free

| Item | Value |
|---|---|
| Date, run window (UTC) | 2026-08-06, `19:48` to `20:05` |
| Vehicle host | **WSL2 on the owner's Windows machine** — the target platform. Kernel `5.15.167.4-microsoft-standard-WSL2`, 20 cores, 15 GiB, Python 3.12.3, ROS 2 Jazzy |
| Gazebo | **Sim 8.11.0**, `gz sim -r -s`, headless, llvmpipe (`libEGL … falling back to kms_swrast`, as always on this host) |
| Isolation | `GZ_PARTITION=m561a` **and** `ROS_DOMAIN_ID=61`. Both, because gz transport is not DDS |
| **Consumer host** | Windows, beside PLCSIM Advanced. **This is the difference from m5-47**, which ran against a throwaway TCP sink with no PLC at all |
| CPU | PLCSIM Advanced instance **`safecell3`**, read back from `RegisteredInstanceInfo` and never assumed; `OperatingState = Run`; **269 tags** |
| Stand-in writer | `bridge/standin_writer/standin_writer.ps1`, API 7.0, session log `standin-writer-20260806T194823Z-pid27436.log`; its `MEMBERS` probe reported **all eleven members of safety SPEC §11.3 present**, warning group included |
| **Machine free before starting** | Checked at `19:48`: nothing listening on 45015 or 45016; the `Global\amr-standin-writer` mutex acquired free and released to prove no writer was running; no `gz sim` process. Two orphaned `nav2` nodes from an earlier session were alive on a **different** ROS domain and were left alone |
| World | `sim/worlds/forklift_arena.sdf`, md5 `c7733d22ee66ad734c7e3ee828d4a464`, **unedited** |
| Model | `agv/forklift/model.sdf`, md5 `42b6e7f8649c2570870cf7894c7baa6b`, **unedited by this brief**. It is not m5-47's md5: the STO work changed the file in between |
| Vehicle pose | spawned at world **(7.000, 4.000)**, yaw 0, **never driven** — it stood there for the whole session, as in m5-47, so that both fields start clear |
| Node session logs | `evidence/field_evaluation/field-evaluation-20260806T195030Z-pid261081.log` (before the deliberate kill) and `…-20260806T195723Z-pid262144.log` (after it) |

**The startup order, and why it is the order.** m5-57 recorded that *with
the writer running and no field source, no monitored reset can be accepted
while the vehicle is above the reduced limit*, which has cost two earlier
agents a run. It was planned into the sequence rather than into a
recovery: **writer first** (it owns both listeners and refuses a second
instance by mutex), **then** Gazebo and the field evaluation, so that a
live `WARN 1` existed before anything else was attempted. No reset was
needed and none was attempted; the vehicle never moved, so the reduced
limit was never a constraint on this run.

---

## 20. THE INTRUSION — a real object in Gazebo, and the control case

A **0.30 x 0.30 x 0.60 m box** was created in the running world and then
**moved** with `gz service /world/forklift_arena/set_pose`. No value was
typed anywhere in the chain, and **every reposition was read back before
the run was allowed to continue** — `set_pose` returns `data: true` for a
well-formed *call*, not for a moved *entity* (LESSONS 2026-08-06), so the
driver re-read the pose through `gz model -m intruder -p` after every move
and would have **discarded** the run, not repaired it, on a mismatch. The
entity id (**130**) was resolved from that same read-back. **All eleven
read-backs matched to within 0.02 m; none was rejected.**

Geometry, with the vehicle at (7.0, 4.0):

| Boundary | World x | Corridor |
|---|---|---|
| protective | **3.775** (rear) … **9.210** (front) | y 3.45 … 4.55 |
| warning | **1.775** (rear) … **11.210** (front) | y 3.45 … 4.55 |

### 20.1 The sequence, as it ran — n = 4 warning intrusions, n = 5 controls

Drivers `evidence/m5-61-stimulus-driver-{A,B,C}.py`, as-run logs
`evidence/m5-61-stimulus-{A,B,C}-*.log`.

| # | Stimulus | Node verdict | `WARN` on the wire | Writer applied it |
|---|---|---|---|---|
| **C1** | box at **(10.0, 6.0)** — 2.77 m from the front device, plainly visible, **1.45 m outside the corridor** | **no verdict of any kind**, 10 s | none | — |
| **W1** | to **(10.0, 4.0)** — near face 9.85, **outside** protective 9.21, **inside** warning 11.21 | `19:52:14.335` front warning OCCUPIED on one scan, **9 rays** inside, nearest 2.173 m (seq=1008) | `19:52:14.361  SEND WARN 0` | `19:52:14.381  WarningFieldClear := False` |
| **R1** | back to **(10.0, 6.0)** | released after the 3-scan debounce **and** the SF-04 hold, measured **2.021 s** | `19:52:26.965  WARN 1` | `19:52:26.990  := True` |
| **C2** | to **(11.6, 4.0)** — **in** the corridor, in the driving direction, plainly visible, **0.24 m outside** the warning boundary | **no verdict of any kind**, 12 s | none | — |
| **W2** | to **(10.0, 4.0)** | `19:52:48.633`, 9 rays, nearest 2.173 m (seq=1345) | `19:52:48.660  WARN 0` | `19:52:48.685  := False` |
| **C3** | to **(11.6, 4.0)** | released at `19:53:01.255` after **2.022 s** of hold, then nothing for 11 s | `19:53:01.264  WARN 1` | `19:53:01.292  := True` |
| **W3** | to **(2.70, 4.0)** — far face 2.85, outside protective 3.775, inside warning 1.775 — the **rear** device | `19:53:11.550`, **5 rays**, nearest 3.464 m (seq=1570) | `19:53:11.562  WARN 0` | `19:53:11.581  := False` |
| **C4** | to **(10.0, 6.0)** | released at `19:53:24.155` after **2.005 s** | `19:53:24.166  WARN 1` | `19:53:24.186  := True` |
| **W4** | to **(10.0, 4.0)**, second sequence | occupied | `WARN 0` | `19:56:11.330  := False` |
| **C5** | to **(11.6, 4.0)** | **no verdict**, 12 s. The release at `19:56:23.9` is the SF-04 hold expiring after the box left, not the control producing anything | `WARN 1` | `19:56:23.947  := True` |

**The control case is what makes the intrusion mean anything.** C2, C3 and
C5 are the sharp form: the box is **inside the corridor**, in the driving
direction, 3.75 m from the front device and plainly visible to it — the
same object, the same sensor, the same rays — and the **boundary
discriminates it by 24 cm**. It produced no verdict, no line and no member
change on any of the three occasions. C1 and C4 are the loose form, 1.45 m
outside the corridor. **n = 5 controls, 0 verdicts; n = 4 warning
intrusions, 4 verdicts, 4 member changes.**

### 20.2 The member change, in the consumer's view

`evidence/m5-61-consumer-witness-warning.log` — a **read-only** witness on
the PLCSIM Advanced API, UTC-stamped in the writer's own log format so the
two interleave without a parser. The verdict column is
`InstF_Forklift_Safety.*`: **what the safety program actually computed**,
never the writer's own read-back (LESSONS 2026-08-04).

```
19:56:04.358 | STATE  | baseline  WarningFieldClear=True WarningFieldClear=True
                        WarningFieldClearValid=True ... StandInValid=True
19:56:11.365 | CHANGE | WarningFieldClear: True -> False          <- W4, the writer's member
19:56:11.382 | CHANGE | WarningFieldClear: True -> False;
                        WarningFieldClearValid: True -> False     <- the F-program, 17 ms later
19:56:23.984 | CHANGE | WarningFieldClear: False -> True
19:56:24.062 | CHANGE | WarningFieldClear: False -> True;
                        WarningFieldClearValid: False -> True
```

The first name in each line is `SafetyInputStandIn.WarningFieldClear`, the
member the writer writes; the second and third are
`InstF_Forklift_Safety.WarningFieldClear` and `…ClearValid`, the F-block's
own instance data. **SL9 is `WarningFieldClear AND StandInValid`** (safety
SPEC §11.5 SL9) and it now moves, in both directions, driven by an object
in the simulator. It had been FALSE in every session that ever ran.

The whole of sequence A was captured independently with the project's own
instrument, `bridge/standin_writer/testing/observe_consumer.ps1`, in
`evidence/m5-61-observe-consumer-sequenceA.log`: **six changes of columns
[23] and [25], one for each of the six `FIELD | WARN` lines in the writer's
log**, and nothing else moved.

### 20.3 Timing observed — each figure is one draw, not a bound

| Interval | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| `set_pose` issued → node's own `WARNING` line | 388 ms | 378 ms | 371 ms | — |
| node `SEND` → writer's `FIELD` line (WSL → Windows TCP) | 20 ms | 25 ms | 19 ms | ~25 ms |
| writer's `FIELD` line → the F-block's own static | — | — | — | **17 ms** |

The first row contains the `gz service` call's own round trip, because the
stamp is taken **before** the call is issued; it is an honest
command-to-verdict figure and **not** a t2 measurement. The second row is
FIELD-EVALUATION §11 measurement 2 (`ZONE`/`WARN` send → writer receipt),
across four draws — **19–25 ms against a 10 ms budget** for t3. Stated as
four samples on one machine, not a bound; per LESSONS 2026-08-05 a re-run
will not reproduce them, and §11's budget is not revised on four draws.

---

## 21. Silence, and the fresh claim — the discipline tested rather than asserted

The field evaluation was **`SIGTERM`ed** at `19:56:44.4` with the writer
running, and restarted 39 s later.

| Event | Observed |
|---|---|
| node killed | `19:56:44.439` EXIT lines written, socket closed deliberately |
| writer notices | `19:56:44.453  LINK down (the field evaluation closed the connection); ZoneDeviceCircuitClosed driven FALSE (open) AND WarningFieldClear driven FALSE` — **14 ms**, by end-of-stream detection rather than by the 1 s staleness reaper |
| the F-program follows | `19:56:44.568` `WarningFieldClear` and `WarningFieldClearValid` both FALSE in the consumer's view |
| node restarted | `19:57:23.887` writer accepts the new client |
| first two lines on the new connection | `19:57:23.981 ZONE 0`, `19:57:23.984 WARN 0` — **both in the demanding direction**, 3 ms apart, ZONE first |
| protective verdict re-earned | `19:57:24.044 ZONE 1`, 60 ms later — three fully-valid clear scans |
| warning verdict re-earned | `19:57:26.045 WARN 1` — **2.06 s after the connection**, because SF-04's 2 s clear-hold had to run again on the new node |

**This is the whole of discipline 1, in one run.** The warning channel went
FALSE with **no `WARN 0` ever sent for it** — the writer converted silence
into the demanding value on its own, which is exactly why this node
deliberately adds nothing to its own death behaviour. And the permissive
level did not come back with the connection: it came back 2.06 s later,
when a live source had **re-earned** it. A clear verdict on this link is
always a fresh claim.

---

## 22. The protective path, undisturbed — shown rather than asserted

Three independent readings, all from the same session with the `WARN`
sender live:

1. **Four warning-only intrusions produced zero `ZONE` lines.** W1–W4 and
   their releases account for **ten** `WARN` lines in session 1's
   transition log and **two** `ZONE` lines, both of which belong to the
   connect sequence at `19:50:30` / `19:50:33`. The two roads stay
   separate.
2. **A protective intrusion still behaves exactly as committed.** Stimulus
   **P1**, box to **(8.5, 4.0)**, near face 8.35, inside the protective
   boundary 9.21:

   ```
   19:58:52.879 | SEND  | ZONE 0 -> aggregate transition
   19:58:52.879 | SEND  | WARN 0 -> warning transition
   19:58:52.883 | FIELD | ZONE 0 -> ZoneDeviceCircuitClosed := False
   19:58:52.886 | FIELD | WARN 0 -> WarningFieldClear := False
   19:59:04.475 | SEND  | ZONE 1        19:59:06.480 | SEND | WARN 1
   ```

   **The zone line goes first, by 3 ms on the wire**, and the two verdicts
   are nested exactly as §6.1 derives them (W > D at every bearing, so
   every protective intrusion is also a warning occupation). The retreat
   shows the asymmetry the whole design exists for: the **stop** releases
   at `19:59:04.5` and the **speed reduction** holds a further 2.005 s.
3. **The send order is structural, not incidental.** `cb_evaluate` calls
   `link.publish()` before `link.publish_warn()`, and `_connected()` sends
   `ZONE` before `WARN`; no protective code path was edited.

**What P1 does not show.** `ZoneStopDemand` and `SafetyResetRequired` read
`True` in the witness **before, during and after** P1
(`evidence/m5-61-consumer-witness-protective.log`): the latch was already
standing when this session started, from the e-stop circuit that has been
open since before it. P1 therefore demonstrates the **channel** reaching
the F-program, not a fresh latch forming. The fresh-latch form is m5-12b
§4.3's and is not re-run here.

---

## 23. The link's traffic budget — the hazard measured rather than argued

`FIELD_LINK_STALE_MAX` is **1 s** against this node's keepalive, and m5-57
measured the link reaped as stale **10 ms before the fourth keepalive** at
1 Hz. The brief asked whether adding a second line type to the same link
makes that worse. **It does not, and here is the measurement.**

Both node sessions report their own totals at `EXIT`; both are quoted as
the tool printed them.

| Reading | Node session 1 | Node session 2 |
|---|---|---|
| Link-up | `19:50:30.6` → `19:56:44.4` = **373.8 s** | `19:57:23.9` → `20:07:48.7` = **624.8 s** |
| Lines sent (`EXIT`) | **719** | **1 191** |
| of which keepalives | **707** | **1 182** |
| of which verdict lines | **12** — 2 `ZONE`, **10 `WARN`** | **9** |
| Traffic the `WARN` sender added | **10 lines in 6 min 14 s = +1.4 %** | comparable |

| Whole writer session | Value |
|---|---|
| **Stale reaps** | **0.** Every inter-line gap across **998.6 s** of link was therefore under the 1000 ms window |
| Writer cycles / overruns / write failures / refusals | **23 291 / 0 / 0 / 1** — the one refusal is §25.5, an operator command file written with a BOM |

**And the direction is favourable by construction, not by luck.** The
writer refreshes its link clock on *every* well-formed line, `WARN`
included — `standin_writer.ps1` sets `$st.linkLastMs` in the `WARN` arm
exactly as it does in the `ZONE` and `PING` arms — so an added line type
can only ever **shorten** the maximum gap between lines. The sender cannot
make the margin worse.

**What is still not satisfied, stated plainly and not fixed here.** m5-59
states the rule as *window >= 3 x ping period + one writer cycle*. This
node's `ping_period_s` is **0.50 s** (2 Hz), which gives **1.55 s against a
1 s window** — the rule is **not** satisfied, and m5-59 asks `agv/` to
raise the keepalive to 5 Hz. **That change was not made by this brief**,
for two reasons worth recording: it re-times the **protective** path's
link, whose behaviour is measured and committed and which this brief is
forbidden to disturb; and `FIELD_LINK_STALE_MAX` itself is `plc/`'s
constant, which may not be retuned silently from here. The observation
above is what the decision should rest on: **0 reaps in 998.6 s of link at
2 Hz, and the run this session needed did not trip once.** That is one
session on one machine, not a bound.

---

## 23.1 Teardown, and one more rule-1 confirmation that came free

The chain was taken down in the order that leaves the machine as m5-57
documented it, and one step of the teardown is itself an observation:

| Time | Event |
|---|---|
| `20:06:35` | `gz sim` and the launch group stopped — **the scan source dies** |
| `20:06:41.184/.186` | the node's own freshness rule fires and it sends **`ZONE 0` then `WARN 0`**, in that order. A dead sensor proves nothing about either field, and the warning channel goes to the demanding value on §8 rule 1 exactly as the protective one does |
| `20:07:48.768` | writer `TERMINAL`: three circuits FALSE, **`WarningFieldClear` FALSE**, `MotionPresent` TRUE with `MotionObservationValid` FALSE, both speed sequences left unwritten and frozen |
| `20:07:48.775` | writer `EXIT`, **23 291 cycles, 0 overruns, 0 write failures** |
| `20:08:43.9` | field evaluation stopped; 28 connect attempts logged while the writer was gone, each one a refusal it correctly did not paper over |

**State the machine was left in**: no writer process, `Global\amr-standin-writer`
free, **nothing listening on 45015 or 45016**, no `gz sim`, no vehicle-side
node, CPU `safecell3` still in `Run`. Two orphaned `nav2` nodes from an
earlier session on a different ROS domain were found before this run and
were left exactly as found.

---

## 24. What this session does NOT establish

1. **No integrity claim.** No Category, PL, SIL, PFH, MTTFd, DCavg or CCF,
   for this node, the link, the writer or anything downstream. The verdict
   arrives at the safety program as **standard data over a stand-in path**.
2. **The reduced limit's *effect* on the vehicle was not observed.**
   `ForkliftStatus.ForkliftSpeedLimitActive` read **False** throughout,
   including while the warning field was occupied. That is
   `docs/VALIDATION-M5.md` finding **F4** — the warning ceiling is
   autonomous-mode only, and the vehicle was not in autonomous mode — and
   it is a `plc/` change in the owner's TIA session, not a defect in
   anything built here. What this session establishes is the half F3 names:
   **the limit selector `WarningFieldClearValid` now moves**, where it was
   permanently FALSE.
3. **No monitored reset was exercised and no latch was cleared.**
   `ZoneStopDemand` and `SafetyResetRequired` stood `True` for the whole
   session, as they did before it. The vehicle never moved.
4. **`ForkliftWarning.ForkliftWarningFieldOccupied` read `True`
   throughout**, including with both fields demonstrably clear. It is the
   standard-side node fed by the ROS-topic carrier that **does not exist
   yet** (§12 phase 2 hand-on 1, m5-47's own request), so it sits at its
   start value. It is not this node's to write and was not written. Raised
   again in the m5-61 report.
5. **The `WARN` line's own transit was measured on four draws** (§20.3),
   and `T_w`'s remaining stages w3–w6 are still budgets against a path that
   is designed and not built.
6. **Nothing was re-run for the protective path's committed figures.** They
   were not re-measured and are not restated; §22 shows the shape, not new
   numbers.

## 25. Corrections and surprises found while running

1. **The first two launch attempts failed on `set -u` in the launch
   wrapper**, not on anything under test: `/opt/ros/jazzy/setup.bash`
   references `AMENT_TRACE_SETUP_FILES` unset. Each attempt was given its
   own log name (`launch-A` … `launch-D`) rather than reusing one, per
   LESSONS 2026-08-05 on truncated logs.
2. **A `pkill -f "scripts/field_evaluation.py"` matched its own shell** and
   killed it, exit 15 — LESSONS 2026-08-06's "exclude the sweep from
   itself", arriving through `pkill` rather than through a process sweep.
   The node was killed as intended; liveness was afterwards checked with a
   pattern that cannot match the checker.
3. **The rear device's last ingested scan again read 4.00 % invalid
   samples** at `EXIT`, against 0.00 % for the front — the same unexplained
   reading m5-47 §17.4 recorded, reproduced here, still under the 5 %
   device-fault threshold and still not explained.
4. **The writer's `MEMBERS` probe found all eleven members present** at
   connect, so the warning group was live for the whole session. A
   half-built controller would have left it inert and this brief would have
   had nothing to observe — which is why the probe is read rather than
   assumed.
5. **The operator command file was first written with a BOM and the `quit`
   was refused**, `REFUSED | '﻿quit': unrecognised command`.
   `STANDIN-WRITER-DESIGN.md` §4.1 says in as many words to write that file
   as UTF-8 **without** a BOM, and PowerShell 5.1's `-Encoding utf8` adds
   one; the writer offered the BOM to the grammar and refused the line
   loudly, which is the designed behaviour and the only `REFUSED` line in
   23 291 cycles. Re-issued through `UTF8Encoding($false)` and accepted.
   The lesson is the design's own and is recorded here because it cost a
   minute of teardown, not because anything is wrong.

---

# m5-72 — why the zone stop stood with the vehicle parked in open floor

**Dated 2026-08-07.** Everything in sections 26 to 31 was measured on the
owner's own live stack while it was running, from outside it. **No file in
`agv/` was edited by this investigation and no parameter was changed** — in
particular `field.scan_fresh_max_s`, both contour depths and both self-return
clips are exactly as sections 1 to 25 left them. Nothing below claims or
implies a Category, Performance Level, SIL or PFH.

## 26. Environment, and that the stack was the owner's

| Item | Value |
|---|---|
| Date | **2026-08-07**, 10:28–10:48 UTC |
| Stack | the owner's own `./demo.sh up` session, brought up 10:28:34 UTC and **still running throughout**; nothing was restarted, killed or reconfigured |
| Vehicle spawn | `x=-3.00 y=-5.50 z=0.05 yaw=0.0`, world `sim/worlds/warehouse.sdf`, Gazebo **GUI on** (`gui:=true`) |
| Isolation | `GZ_PARTITION=m5demo`, `ROS_DOMAIN_ID=64`, both read out of `/proc/369296/environ` rather than assumed |
| Nodes under observation | `field_evaluation.py` pid 369296, writer `standin_writer.ps1` pid 7004, `hmi_server.py` pid 370558, `run_bridge.py` pid 370460 |
| Instruments | three throwaway read-only probes (a scan/pose comparator, an inter-arrival sampler, a 5 Hz `/state` sampler) plus `gz topic -e`, `gz model -p`, `gz model --list`, and the two committed logs |
| Raw sample | the 5 Hz `/state` trace is kept at `evidence/m5-72/m5-72-state-watch-20260807T104609Z.csv`, 2217 rows. It was copied **after** its writer was verified stopped, never from under a live writer (LESSONS 2026-07-28) |
| Vehicle repositioning | `gz service set_pose` with the **entity id 452**, and the pose **read back** every time (LESSONS 2026-08-06: without the id the call returns `true` and does nothing). The vehicle was left at the spawn pose |
| What was written to the stack | **only** operator actions through the HMI's own `POST /control`, the same endpoint and the same payload shape the operator's page posts. No PLC node was written by any probe |
| TIA / PLCSIM | **not opened, not started, not stopped, not downloaded and not changed.** The CPU stayed signed at 29FD2C52 |

## 27. The first hypothesis, and it is dead: the front scanner is where the model says it is

The brief's leading hypothesis was that the front scanner's pose or frame is
wrong, so that it observes a place the vehicle is not — and that if that place
holds racking, the protective field is permanently occupied and the zone stop
can never clear. **It is refuted, three independent ways.**

**(a) The returns lie on the same walls the navigation lidar sees — at two
different vehicle poses.** Every in-range return projected into `base_link`
through the mount declared in `model.sdf`, then measured against the nearest
navigation-lidar return. **Two poses, because one pose cannot tell a correct
mount from a mount displaced by a constant**: a constant offset would show as
the same non-zero median at both.

| Vehicle ground truth | Device | in-range returns | median | q90 | max |
|---|---|---|---|---|---|
| `x=-3.000 y=-5.500 yaw=0.0000` | front | n = 156 | **0.072 m** | 0.909 m | 1.151 m |
| | rear | n = 151 | **0.028 m** | 0.102 m | 0.530 m |
| `x=+1.500 y=-5.500 yaw=0.7854` | front | n = 114 | **0.017 m** | 0.429 m | 2.379 m |
| | rear | n = 159 | **0.032 m** | 0.090 m | 0.494 m |

The second pose is 4.5 m away and rotated 45°, and the front median **fell**
from 0.072 m to 0.017 m. There is no constant. A scanner observing a place the
vehicle is not cannot agree with a second sensor to a median of 17 mm at one
pose and 72 mm at another. The residual is expected and is not a pose error:
the navigation lidar scans at z = 1.800 m and the safety scanners at
z = 0.150 m, so the two planes cut different parts of the same racking, and
both clouds are quantised at 0.0175 rad.

**So the returns do NOT carry the displacement.** Every field figure in
sections 1 to 25 was taken through a scanner looking where the model says it
looks.

**(b) The nearest front return is the vehicle's own structure, exactly where
the model says it will be.** `r = 1.084 m at sensor bearing +137.5°`, which
falls inside the front self-return clip band the node logs at start,
`+136.4 … +137.6°, boundary capped at 1.034 m`. The rear device's nearest
return, `0.101 m at −93.3°`, likewise falls inside its own declared band
`−133.0 … −71.8°`. Both are geometry the field already knows about.

**(c) The demand's time profile is wrong for a mislocated sensor.** A scanner
parked inside racking is occupied from boot and never clears. This one went
`AGGREGATE | CLEAR` about 3 s after its first scan in every one of the four
sessions logged on 2026-08-07 (10:10:32, 10:13:33, 10:22:31, 10:28:40), and
its one genuine intrusion — 10:17:45.789, `front INTRUSION on one scan: 34
ray(s) inside the contour, nearest 1.507 m` — arrived **52 s after the warning
field went occupied**, which is the signature of a vehicle being driven toward
something, not of a sensor standing in it.

**So the owner's first screenshot was a true reading of a true event.** At
10:17:45 the vehicle really had been driven up to a rack face and was standing
1.507 m from it, inside a protective contour that reaches 2.210 m ahead of
`base_link`. The reset attempted at 10:18:35, with the field still occupied,
was **correctly refused**. That is the safety layer working.

## 28. The lidar visual IS misplaced, and it is a rendering-frame artefact

The owner's second observation is real and is not cosmetic paranoia — but it
is not a pose error either.

Every `gz.msgs.LaserScan` this model publishes carries a `world_pose` field,
and **all three sensors publish it as the identity pose**:

| Topic | `world_pose.position` | `orientation` | true sensor world pose |
|---|---|---|---|
| `…/safety_scanner_front/measurement` | `x 1.11e-16, y 2.78e-17, z 0` | `w 1` | `(-2.30, -5.05, 0.15)`, yaw +45° |
| `…/safety_scanner_rear/measurement` | `y 8.33e-17`, rest 0 | `w 1` | `(-3.70, -5.95, 0.15)`, yaw −135° |
| `…/scan_nav` | all 0 | `w 1` | `(-2.45, -5.90, 1.80)`, yaw 0 |

The `frame` and `frame_id` fields are correct on all three
(`safety_scanner_front_link` and siblings), and the `ranges` are correct —
section 27 measures them. It is only the pose the message advertises for the
fan that is identity.

**That places the drawn fan at the world origin.** At the demonstration spawn
pose the vehicle stands at `(-3.00, -5.50)`, so the world origin is **3.00 m
ahead of it and 5.50 m to its left, in open aisle** — which is where the owner
reports seeing it. The observation, the measurement and the geometry agree.

**And the anchor does not move with the vehicle.** Re-read after teleporting
the vehicle to `x=+1.500 y=-5.500 yaw=0.7854` — 4.5 m away and rotated 45° —
the front sensor's `world_pose` came back **byte-identical**:
`x 1.1102230246251565e-16, y 2.7755575615628914e-17, w 1`. So the fan is
anchored to a fixed point in the world, not rigidly offset from the vehicle.
A viewer who sees the fan "in a different place" after the vehicle moves is
seeing a stationary fan and a moved vehicle, and the apparent offset is
therefore **not** constant. **This is the one thing the owner can settle in a
single look: park the vehicle somewhere else and watch whether the fan stays
where it was.**

**One competing hypothesis was checked and is dead.** `gz model --list`
against the live world returns **exactly one** `Forklift` among 22 models, so
no second vehicle was spawned by a composed launch.

**Nothing in `agv/` produces this and nothing in `agv/` should paper over it.**
The ranges are the product; the advertised pose is not consumed by any node in
this repository — `field_evaluation.py`, `obstacle_zone.py` and the Nav2 stack
all take the ROS `LaserScan` and its `frame_id` through TF. The artefact is
confined to the simulator's own visualisation. **A reader looking at the
Gazebo window is looking at the one channel that is wrong.**

Recorded in passing, because it is on the same path and is also cosmetic:
`gz model -p` prints four warnings of the form *"XML Element[gz_frame_id],
child of element[sensor], not defined in SDF"* for the three lidars and the
IMU. The frame nevertheless arrives correctly in the ROS message, which is
what the consumers read.

## 29. What actually latched the zone stop, and it is not an intrusion

At 10:39:27, with the vehicle standing still at the spawn pose and **the field
measurably clear**, the protective channel opened for 94 ms and the F-side
latched. Both logs, independently:

    field_evaluation, 10:39:27.889Z | WARNING | ... front: nothing received for
        0.310 s (limit 0.30 s, this node's own monotonic clock)
        (front 0 ray(s) inside, rear 0)
    field_evaluation, 10:39:27.899Z | AGGREGATE | INTRUSION - front: nothing
        received for 0.310 s ... (front seq=5674 rear seq=5674)
    field_evaluation, 10:39:27.909Z | SEND | ZONE 0 -> aggregate transition
    writer,           10:39:27.944Z | FIELD | ZONE 0 -> ZoneDeviceCircuitClosed := False
    writer,           10:39:28.038Z | FIELD | ZONE 1 -> ZoneDeviceCircuitClosed := True

`front 0 ray(s) inside, rear 0` is the node saying, in the same line, that
nothing was in either field. The verdict came from the **freshness rule**, not
from a return. The channel was open for **94 ms** at the writer. That was
enough: `ZoneStopDemand` read `False` over OPC UA at 10:38:12 and `True` at
10:43:44, with no other event between them.

**This is the answer to the brief's question.** The demand stood with the
vehicle parked in open floor because a 310 ms gap in a 10 Hz scan stream
latched a protective stop, and a latch does not care that the gap lasted 94 ms.

**The node is right to do this.** A scan that has not arrived is unknown, and
unknown means intrusion (`config.yaml` rule 0, and LESSONS 2026-08-06 on
silence). Nothing here is a defect in the evaluation.

### 29.1 How often, measured

180 s window, vehicle standing, GUI on, inter-arrival on the sampling node's
own `time.monotonic` — the same clock `field_evaluation` uses:

| Stream | n | median | q90 | q99 | max | gaps > 0.30 s |
|---|---|---|---|---|---|---|
| front scan | 1591 | 0.1117 s | 0.1244 s | 0.1495 s | **0.3676 s** | **1 (0.063 %)** |
| rear scan | 1591 | 0.1117 s | 0.1263 s | 0.1494 s | 0.3421 s | 1 (0.063 %) |
| `/clock` | 79 467 | 0.0020 s | 0.0039 s | 0.0067 s | 0.3330 s | 1 (0.001 %) |

Two things follow, and the second is the one that matters.

**The stall is the whole simulator, not the topic.** `/clock` stalled 0.333 s
in the same event. This is Gazebo hitching under llvmpipe software
rasterisation with the GUI attached (`sim/setup/WSL_ENVIRONMENT.md` 4.7), not a
transport problem and not a node problem.

**`scan_fresh_max_s = 0.30` no longer means what its own comment says.** The
comment reads *"THREE SCAN PERIODS"*, derived against the nominal 10 Hz. The
**delivered** period on this machine is 0.1117 s (n = 1591), so the window in
force is **2.69 delivered periods**, not three. Three delivered periods would
be 0.335 s — and the observed maximum was 0.3676 s, so even the parameter's own
stated derivation would not have covered this event.

**This value was NOT changed, and should not be changed to make a demand go
away.** It is a safety-relevant timeout whose direction is the demanding one,
and moving it is an owner's decision with a stated derivation behind it, not an
agent's convenience. What is recorded here is that the derivation and the
machine now disagree, and by how much.

**The mitigation that changes no safety parameter is to stop the simulator
stalling.** `./demo.sh up --headless` removes the GUI render thread that
produces the hitch. **This was not tested here** — testing it means restarting
the owner's live stack, and the owner was mid-demonstration. It is the first
thing to measure next, by re-running the table above headless.

## 30. The path, end to end, watched rather than reasoned about

Sampled at 5 Hz off the HMI's own `/state`, n = 626 rows. Times UTC.

| Time | Observed | By what act |
|---|---|---|
| 10:46:09.970 | `EStopDemand=True ZoneStopDemand=True SafetyResetRequired=True`, mode 0, ceiling 0.000 | the state the owner was stuck in |
| 10:44:53.762 | writer: `estop close -> EStopCircuitClosed := True` | **owner, at the writer console** |
| 10:46:39.297 | writer: `reset pulse 800 -> ResetButtonPressed := True`, released 10:46:40.138 | **owner, at the writer console** |
| 10:46:40.557 | **all three cleared in one sample**: `EStopDemand`, `ZoneStopDemand`, `SafetyResetRequired` all `False`, 0.419 s after the shaped release | the F-side monitored reset |
| 10:46:40 to 10:48:02 | mode stayed at **0** for 82 s with every demand clear and `HmiDriveModeRequest` standing at **1 (Teleop)** | **a selection refused while a demand stood is consumed.** Clearing the demands does not revive it, and a selector left on TELEOP throughout is not a request |
| 10:48:02.571 | `ForkliftDriveModeActive 0 -> 1`, `ForkliftVehicleModeApplied 0 -> 1` | a scripted **None -> Teleop** edge through `POST /control` |
| 10:48:15.412 | `ForkliftTeleopActive True`, `ForkliftTractionSpeedRef 1.000`, speed rising | traction held through `POST /control` |
| 10:48:15 to 10:48:24 | **37 consecutive samples above 0.01 m/s, peak `ForkliftLinearSpeed` 1.000 m/s** | the drive |
| 10:48:23.988 | released: reference to 0.000, `TeleopActive` dropped, speed to 0.000 | the deadman |

**The positive control, on ground truth, because stillness and motion must
both be shown (LESSONS 2026-08-06).** `gz model -m Forklift -p` before the run
read `[-3.000000 -5.500000]`; after it read **`[4.827640 -5.499050]`**, yaw
0.000143 rad. **The vehicle travelled 7.83 m down the aisle.** No intrusion was
logged during the drive — the aisle really was clear for the whole 7.83 m,
which is the control case for section 27.

**So teleoperation is not broken and never was.** Nothing in `agv/` was
changed to produce this run.

## 31. What this section does NOT establish

1. **The headless mitigation is untested.** Section 29.1 recommends it from a
   measurement of the stall, not from a run without the GUI.
2. **The 0.063 % figure is one 180 s window on one machine at idle.** It is an
   observed rate, not a bound, and it will be worse under load — m5-69
   measured 6.1x. What it does establish is that the rate is **not zero**, so a
   demonstration long enough will meet it.
3. **The `world_pose` finding is read off the message, not off the renderer.**
   That the message advertises identity is measured; that the Gazebo GUI plugin
   is what consumes it is the explanation consistent with the owner's
   observation and the spawn geometry, and it was not read out of Gazebo's
   source.
4. **The 800 ms reset hold was accepted.** `RUNBOOK.md` section 3 says 2000 ms.
   Which hold the F-program actually requires was not characterised here; one
   acceptance at 800 ms is a sample, not a limit.
5. **Nothing here is a safety claim.** The evaluation remains a model of what a
   safety-rated device does inside its housing, feeding a stand-in for wiring.
