# EVIDENCE_MAP_V3.md — the map of warehouse_ver3, built and scored

F3 Task 1. A frozen, committed, registered, absolutely-scored occupancy
map of the floor this track drives on, built by `slam_toolbox` **offline
and sync** from a recording of the REAL sensor chain — the TiM571-profile
nav lidar and F2's EKF odometry, with the ground truth deliberately left
out of the bag.

Everything below was measured on **this rig** (WSL Ubuntu 24.04, ROS 2
Jazzy, gz-sim 8.11.0, RTX 4050) on **2026-08-26**, on the **nominal**
plant and the **default** estimator arm (`wheel+imu`), headless. Every
figure names the instrument that produced it and the artifact it came
from.

---

## 0. The answer, before the working

| | |
|---|---|
| **instrument floor** (registration residual) | **rms 0.0291 m, MAX 0.1179 m**, internal shear 0.2650° over 2084 wall points |
| **absolute score** — hall width E↔W | 48.000 m true, **48.0194 m measured, +0.0194 m** (+0.39 cells, +0.040 %) |
| **absolute score** — N wall ↔ annex front (HELD OUT of the fit) | 28.000 m true, **28.0361 m measured, +0.0361 m** (+0.72 cells, +0.129 %) |
| **coverage** | **98.21 %** of the 1394.0 m² open floor marked FREE |
| **geometry outside the building** | **0 occupied cells, 0 free cells** |
| **repeatability** | three independent builds, **byte-identical pose graphs** |
| comparison row, DIFFERENT FLOOR | m5_ver1 warehouse: rms 0.0404 m, MAX 0.1411 m, shear 0.3250° |

**No localisation figure at or below 0.1179 m is a measurement of the
localiser.** That is §6.4 and it is the number F3's next task has to be
read against.

### What was built

| artifact | what it is |
|---|---|
| `config.yaml` `drive_route.profiles.mapping` | the commissioning drive: 227.0 m over the whole road graph, nine 90° corners, 774.7 s, one speed |
| `logs/evidence/drive-mapping-20260826-174815/` | the recording — ten CSVs **and** a rosbag2 (untracked; md5s in §5.2) |
| `slam.yaml` | what the mapper does. Eleven values differ from the shipped defaults: two are the topic and frame contract, two are mechanism, and the seven that are tuning are each argued from a measured property |
| `tools/build_map.sh` | the offline run: a bag, a mapper and two transforms, on a ROS domain of its own |
| `maps/warehouse_v3/warehouse_v3.{pgm,yaml}` | the frozen occupancy grid |
| `maps/warehouse_v3/warehouse_v3.{posegraph,data}` | the frozen pose graph |
| `maps/warehouse_v3/registration.yaml` + `build.txt` | the committed world→map transform, the score, and what it was built from |
| `tools/map_core.py` + `tests/test_map_core.py` | the arithmetic, and 82 tests that reach it with no simulator |
| `tools/map_register.py` | `derive` \| `show` \| `clearance`. Needs no ROS |

---

## 1. The drive, and why it is shaped the way it is

### 1.1 The route is the fleet's own road graph

`m6/ipc/route.py`'s `build_graph()` — read READ-ONLY, the way this track
reads the floor — is the aisle centrelines of `warehouse_ver3` and
nothing else. Twelve edges, **180.00 m**:

| road | where | clear width | class |
|---|---|---|---|
| RING | `x = ±20.00`, `y = ±10.00`, closed, 120.00 m round | 8.00 m | cruise |
| SPINE | `x = 0.00`, `y = −10.00 … +10.00` | 8.00 m | cruise |
| PICK AISLE | `y = 0.00`, `x = −20.00 … +20.00` | **5.00 m** | creep |

Four of the graph's junctions have **odd degree** — `(0, ±10)` and
`(±20, 0)` each carry three edges — so no walk traverses every edge
exactly once. The profile drives the ring's four legs a second time and
covers everything in **227.0 m of straight and nine corners**:

| leg | from | to | m | road | corner at the far end |
|---|---|---|---|---|---|
| L1 | (−17, +10) | (0, +10) | 17.0 | ring N | C1 **RIGHT** E→S |
| L2 | (0, +10) | (0, −10) | 20.0 | **SPINE** | C2 RIGHT S→W |
| L3 | (0, −10) | (−20, −10) | 20.0 | ring S | C3 RIGHT W→N |
| L4 | (−20, −10) | (−20, 0) | 10.0 | ring W | C4 RIGHT N→E |
| L5 | (−20, 0) | (+20, 0) | 40.0 | **PICK AISLE** | C5 **LEFT** E→N |
| L6 | (+20, 0) | (+20, +10) | 10.0 | ring E | C6 LEFT N→W |
| L7 | (+20, +10) | (−20, +10) | 40.0 | ring N | C7 LEFT W→S |
| L8 | (−20, +10) | (−20, −10) | 20.0 | ring W | C8 LEFT S→E |
| L9 | (−20, −10) | (+20, −10) | 40.0 | ring S | C9 LEFT E→N |
| L10 | (+20, −10) | (+20, 0) | 10.0 | ring E | — (it stops) |

L2 drives straight **through** the crossing at (0, 0) and L5 drives
through it the other way, which is why neither costs a corner.

**The pick aisle is driven fifth, and that ordering is the safety
argument.** It is the only 5.00 m corridor on this floor; the rack faces
stand at `y = ±2.50` and the truck is 1.20 m wide, so the rear axle has
±1.90 m of room against ±3.40 m in every 8.00 m corridor. This is an
**open-loop** profile — nothing reads a pose and nothing corrects — so
the error budget is spent as the run goes on, and the tightest corridor
is driven with four corners and 67 m behind it rather than nine and
200 m.

**And it crosses its own track on purpose.** L7 re-drives the leg the run
started on, 180 m later; L8 re-drives L4's floor and L9 re-drives L3's.
Those revisits are what loop closure has to work with, and a mapping
drive that never crosses itself hands the optimiser nothing to close.

### 1.2 The four plant constants the table is built from

Measured on this rig 2026-08-26 on the F1.5 tuned plant, ground truth
only. **Instrument:** a throwaway probe of `tools/drive_route.py`'s own
two classes (`SimClock` + `Terminals`) with `gz topic -e` on
`topics.odom_ground_truth` beside it — the same shape of probe the
`square:` table was first sized by, and every figure it produced is
reproducible from any recording of the `mapping` profile because
`sensor_evidence.py` records the same stream.

**(1) Straight ground speed at a commanded 0.300 m/s: `0.2990 m/s`.**
60 s of held command; four disjoint windows after the first 10 s
(+5…+10, +10…+20, +20…+40, +40…+60 s) all read `0.2990`. 0.33 % of slip,
the same order as the 0.95 % `EVIDENCE_FUSION.md` §8.1 measures at cruise.
Lateral drift over the 17.24 m: **−0.0138 m**; heading moved
**−0.00007 rad**. A straight leg on this plant is straight. What it is
not is the length the command asks for.

**(2) Start-up deficit `0.704 m`, stop coast `0.5548 m`.** From rest the
first 5 s of a 0.300 command covers 0.7907 m against the 1.4950 m steady
travel would give; after the command returns to zero the truck runs on
for 0.5548 m before it stops. **The two do not cancel and neither is
ignored**: L1 is lengthened by the first and L10 shortened by the second,
each once.

> A standing zero on this model is therefore **not a brake**, and
> `drive_route.py`'s header should be read with that beside it. It is a
> standing order to stop DRIVING — which is what stops a truck running
> away on a dead publisher — and it is not 0.55 m of stopping distance a
> profile may spend elsewhere.

**(3) The π/4 corner, both hands, and they are the same corner.** Two
full circles at a held steer of ∓0.785398 rad, 0.300 m/s, 31 s each —
one revolution and a bit, so the rate is averaged over every heading
rather than one. A circle was fitted to the steady portion (Kåsa,
algebraic):

| hand | steady yaw rate | base_link radius | circle-fit rms |
|---|---|---|---|
| LEFT (−0.785398) | **+0.203658 rad/s** | 1.1190 m | 0.00041 m |
| RIGHT (+0.785398) | **−0.203887 rad/s** | 1.1171 m | 0.00059 m |

**0.11 % apart.** That symmetry is why this route may turn both ways:
`square:` and `corner_creep:` only ever turn left, so nothing on this
track had measured a right-hand corner before, and a route round a ring
cannot avoid one hand or the other.

> The radius is **base_link's** and it is 1.119 m rather than the 1.05 m
> the wheelbase promises, because this vehicle's **steered wheel
> trails**: `model.sdf` puts `steer_link` at x = +0.55 and the two load
> wheels at x = −0.50, and the travel direction is model −x, so the wheel
> that steers is at the counterweight end and base_link swings 0.13 m the
> WRONG way at the start of every corner before it comes round. Measured
> (the y of the left circle dips to 9.8669 before it rises to 12.1034),
> and it is why the corner's geometry is taken from the recording rather
> than from R.

**(4) The corner block, measured whole rather than derived.** The steer
axis has to slew in and slew out and neither is a steady state:

| | LEFT | RIGHT |
|---|---|---|
| yaw taken in the first 5 s, against the steady rate | **−0.27706 rad** | −0.27426 rad |
| yaw taken after the steer returned to zero (3.0 s) | **+0.27781 rad** | +0.28037 rad |
| net over a whole 31 s circle | **+0.00075 rad** | — |

**The two cancel.** So a corner is (a hold at the steer) + (a straight
segment long enough for the axis to come out), and the pair turns the
vehicle by the steady rate times the hold. The slew-out is complete
inside 3.0 s at 0.300 m/s — the segment after it reads 0.0008 rad of
further yaw — and every corner in the profile is followed by a straight
of at least that.

**A 90° corner is a 7.748 s hold.** Measured directly rather than
divided: a 7.7086 s hold plus its 3.0 s slew-out turned the truck
1.55919 rad (LEFT) and 1.56649 rad (RIGHT) against the 1.5707963 asked,
so both hands want 0.021–0.057 s more and the table carries the mean. The
residual spread is **0.42° between the hands** and it is not tuned out:
it is the plant, and what it costs is 0.42° of heading per corner, which
over the longest leg that follows one (40.00 m) is 0.29 m of lateral.

**And the lane it consumes is measured the same way.** Over the whole
block (hold + slew-out) the truck's displacement in the frame it entered
on is **1.95 m forward along the entry lane and 0.93 m sideways along the
exit lane** — which is not (R, R) and could not be, for the
trailing-steer reason above. So a corner at junction J is commanded
1.95 m before J, and when the block ends the truck is already 0.93 m past
J on the new lane. That is the whole of the arithmetic in the table.

### 1.3 One speed from end to end

0.300 m/s everywhere: no cruise leg, no ramp, no speed change at a
corner. Three reasons and they point the same way. The pick aisle is a
CREEP corridor in the floor's own spec, so part of the route is at this
speed whatever happens. Every constant in §1.2 was measured AT this
speed, and a profile that changed speed would need the corner block
measured again at the other one. And a slower drive is a denser
recording — 15 Hz over 774.7 s is **11,901 scans over 225.0 m, one scan
per 19 mm of travel**. A commissioning map is not a lap time.

---

## 2. What the drive actually did

**Session:** `logs/evidence/drive-mapping-20260826-174815`, nominal
traction, `wheel+imu` arm, headless, `drive_exit=0`.
**Instruments:** `sensor_evidence.py analyse` and
`map_register.py clearance`.

### 2.1 It fitted the floor — measured, not assumed

`config.yaml`'s corridor arithmetic is a PREDICTION. This is the
measurement: the truck's outline (1.875 m ahead of base_link at the fork
tips, 0.90 m astern, 0.60 m each side — a **bound**, not the model's
silhouette) swept along the **recorded ground truth**, against all 25
obstacle rectangles `map_core.sdf_obstacles()` reads out of
`m6/gazebo/warehouse_ver3.sdf`.

```
WORST CLEARANCE 1.0732 m
  against RackSE3 at sample 7247, base_link (+16.9395, -0.8507)
```

The ten nearest approaches, all of them on the pick aisle except the last
three:

| obstacle | worst gap | where |
|---|---|---|
| RackSE3 | **1.0732 m** | (+16.939, −0.851) |
| RackSE2 | 1.2178 m | (+11.439, −0.706) |
| RackSE1 | 1.3786 m | (+5.445, −0.546) |
| RackSW3 | 1.6158 m | (−3.044, −0.311) |
| RackSW2 | 1.7797 m | (−8.529, −0.149) |
| RackNW1 | 1.8045 m | (−16.659, +0.117) |
| RackSW1 | 1.9744 m | (−14.507, +0.043) |
| RackNW2 | 1.9863 m | (−11.160, −0.067) |
| RackNW3 | 2.1673 m | (−5.122, −0.250) |
| AnnexE | 2.2031 m | (+19.382, −10.739) |

### 2.2 The open loop held every lane

Deviation of the recorded ground truth from each leg's planned
centreline, taking the first 3 s of each leg out (that is the previous
corner's slew-out, which is inside the segment):

| leg | planned lane | samples | mean offset | max abs | budget |
|---|---|---|---|---|---|
| L1 ring N east | y = +10.00 | 994 | +0.0004 m | **0.0008 m** | 2.50 m |
| L2 SPINE south | x = 0.00 | 1145 | −0.1044 m | 0.1607 m | 2.50 m |
| L3 ring S west | y = −10.00 | 1145 | +0.1046 m | 0.1926 m | 2.50 m |
| L4 ring W north | x = −20.00 | 477 | −0.1036 m | 0.1734 m | 2.50 m |
| **L5 PICK AISLE east** | y = 0.00 | 2483 | −0.3682 m | **0.8791 m** | **1.00 m** |
| L6 ring E north | x = +20.00 | 477 | +0.0607 m | 0.1140 m | 2.50 m |
| L7 ring N west | y = +10.00 | 2483 | −0.6992 m | 0.9068 m | 2.50 m |
| L8 ring W south | x = −20.00 | 1145 | +0.0424 m | 0.1180 m | 2.50 m |
| L9 ring S east | y = −10.00 | 2483 | −0.5240 m | 0.6698 m | 2.50 m |
| L10 ring E north | x = +20.00 | 569 | +0.0335 m | 0.1055 m | 2.50 m |

The budget column is the conservative one — the truck's **circumscribed**
1.50 m radius about the rear axle taken at every bearing at once, which
is the bound `square:` and `corner_creep:` already argue their own floor
checks with. On the true outline the pick aisle's budget is ±1.90 m
rather than ±1.00 m, because the 1.375 m of fork overhang is
LONGITUDINAL and a straight leg does not point it at a rack.

**So a full-floor open-loop trace of this graph was geometrically safe on
this plant, and the F1/F2 drift class did not force the drive to be
split.** It was not assumed to be: the profile was written against the
corridors, driven once, and then checked against the world's own
rectangles. The margin that decided it is the 1.0732 m above.

### 2.3 The corners the run itself re-measured

`sensor_evidence.py analyse`'s per-corner table finds the four corners at
its configured target steer (`evidence.corner`), which on this profile
are the four RIGHT-hand ones — C1 to C4:

| # | window [s] | held rad | rear m/s | yaw rate | delivered | in-corner lat |
|---|---|---|---|---|---|---|
| 1 | 91.86–97.93 | +0.788960 | 0.2021 | −0.203693 | **1.0047** | −0.005930 |
| 2 | 159.86–165.92 | +0.788834 | 0.2021 | −0.203669 | 1.0047 | −0.005930 |
| 3 | 227.86–233.94 | +0.788810 | 0.2021 | −0.203662 | 1.0047 | −0.005931 |
| 4 | 262.43–268.55 | +0.788581 | 0.2022 | −0.203607 | 1.0046 | −0.005936 |

**Delivered 1.0046 to 1.0047 over four corners, spread 0.0 % of the
mean**, at four different world headings. The 11.5 % heading dependence
`EVIDENCE_LATERAL_TUNE.md` measures at −1.25 rad does not appear at this
steer angle; it is why π/4 is the angle this profile turns at.

### 2.4 What the sensor delivered, and what the odometry was worth

Delivered rates over the whole 785 s (`analyse`, sim-time stamps):

| stream | samples | Hz (sim) | dt_med | dt_max |
|---|---|---|---|---|
| `scan_nav` | 11,901 | 15.1515 | 0.06600 | **0.06600** |
| `odom_truth` | 15,710 | 20.0000 | 0.05000 | 0.05000 |
| `ekf_odom` | 39,251 | 50.0000 | 0.02000 | 0.02400 |
| `clock` | 392,667 | 499.9338 | 0.00200 | 0.10600 |

`dt_max = dt_med` on the nav lidar: **not one scan was lost over 785 s of
mapping drive.** Mean RTF over the run 0.9985.

And the odometry the mapper is asked to correct — F2's EKF, scored
against the same ground truth by the same function that produces every
row in `EVIDENCE_FUSION.md`:

| figure | raw wheel odom | **EKF (what is in the bag)** | removed |
|---|---|---|---|
| end error | +24.7708 m | **+9.8573 m** | 60.2 % |
| end heading | −1.0708 rad | **−0.4080 rad (−23.4°)** | 61.9 % |
| along-track | −22.4265 m | **−9.8374 m** (ran SHORT) | 56.1 % |
| cross-track | +10.5188 m | **+0.6261 m** | 94.0 % |
| rms over the run | +11.4257 m | **+4.5174 m** | 60.5 % |
| worst | +25.9971 m | **+10.2830 m** | 60.4 % |

**This is the input, not a complaint.** A map built from an estimate that
did not drift would be a map of a plant nobody has. What the SLAM run is
being asked to do is remove 9.86 m of accumulated position error and 23.4°
of heading over 225 m, and the score in §7 is what says whether it did.

---

## 3. The recording

**Mechanism, named:** `tools/sensor_evidence.py record --drive mapping
--bag`. The `--bag` flag is F3 Task 1's addition and it starts
**`ros2 bag record`** as a separate process inside the same session
directory, on `evidence.bag.topics`, with the session's traction and arm
labels and both mixed-set refusals intact.

> **Why a subprocess and not a writer in the recorder.** That process
> already holds ten subscriptions and writes ten CSVs on one thread;
> adding 15 Hz of 811-beam scan and 500 Hz of clock to the same executor
> would put the bag's write latency inside every rate figure in §2.4.
>
> **Why SIGINT and not SIGTERM.** rosbag2 finalises its storage and
> writes `metadata.yaml` in its shutdown handler. A bag killed before
> that runs has no metadata and `ros2 bag play` refuses it by name — so
> the recorder starts it in a session of its own and signals the process
> group.
>
> **Why the ground truth is not in it.** `/forklift/gz/odom` is a
> measurement reference and never an input (F2 global constraint 13). A
> bag that carried it into a SLAM run would be one careless remap away
> from being the thing the map was built on. It is in the session's
> CSVs, where nothing can replay it.

| topic | type | messages |
|---|---|---|
| `/clock` | `rosgraph_msgs/msg/Clock` | 391,963 |
| `/forklift/gz/scan_nav` | `sensor_msgs/msg/LaserScan` | 11,877 |
| `/tf` | `tf2_msgs/msg/TFMessage` | 39,099 |
| `/tf_static` | `tf2_msgs/msg/TFMessage` | 1 |

442,940 messages, **785.158 s**, mcap, 102.4 MB. The 24-scan difference
against the CSV's 11,901 is the 1.6 s between the recorder's own
subscriptions coming alive and the bag process starting; the bag still
spans the whole pre-roll, so the reference pose is inside it.

**The scan is the TiM571 profile and the range that reaches the mapper is
the sensor's own.** Over the 11,901 scans there are **8,944,094 finite
returns**, of which **825,214 — 9.226 % — are beyond 20.0 m**, and the
longest is exactly **25.0000 m**. That figure exists because
`mapper_params_offline.yaml` ships `max_laser_range: 20.0`; see §4.3.

---

## 4. The offline SLAM run: mechanism and configuration

### 4.1 Offline and sync, and what that buys

`docs/reports/m5v3-01` §(a) ranks `slam_toolbox` **offline (sync) from a
recorded bag** first, and the reason it gives is not accuracy: *"Sync +
offline replay is deterministic — repeatable evidence, no dropped
scans."* The async node drops scans when it cannot keep up, so two runs
of one recording process different scans and produce different maps.

`tools/build_map.sh` is that run. It starts no plant and attaches to
none: the world is not running, the truck is not moving, and every input
is a file.

```
bash m5_ver3/tools/build_map.sh m5_ver3/logs/evidence/drive-mapping-20260826-174815
```

| on the wire during the replay | published by |
|---|---|
| `/clock`, `/forklift/gz/scan_nav`, `/tf`, `/tf_static` | the **bag** |
| `base_link → nav_lidar_link` | **`build_map.sh`** — the one seam |
| `map → odom` | `slam_toolbox` |

**The middle row is the only thing on the wire that is not in the
recording**, and it is stated rather than hidden. The default arm does
not publish the nav lidar's mount: `m5v3.sh start --rf2o` spawns a
`lasertf` child for it because `rf2o` needs it, and the default six-child
stack has no consumer for it and therefore no publisher. F3 constraint 17
says baselines are taken on the DEFAULT arm, so the recording was made
there and the transform is published in the OFFLINE graph, from
`config.yaml`'s `vehicle.nav_lidar_mount` — the same three numbers the
`lasertf` child reads, which `nodes/rf2o_twist.py`'s `mount_from_model()`
checks against `model.sdf` and refuses on. **Nothing about the live stack
changed, and F3 constraint 15 holds: this task adds no runtime TF.**

**The replay lives on a ROS domain of its own (98), and that is a safety
property rather than tidiness.** The bag carries `/tf`, which is the
EKF's `odom → base_link`. Replayed onto domain 97 there would be two
publishers of an edge that has exactly one owner, and tf2 does not refuse
that — it carries whichever message arrived last. `build_map.sh` refuses
if `isolation.map_ros_domain_id` is ever made equal to
`isolation.ros_domain_id`, and it unsets `GZ_PARTITION`, because there is
no simulator in an offline run.

**Two refusals before anything starts**, and they are the recorder's two
labels read back:

| check | why it is a refusal and not a warning |
|---|---|
| `traction=nominal` | a map carries whatever it was built on into everything that localises against it |
| `arm=wheel+imu` | the odometry in the bag is what the mapper corrects, so a map built on `--rf2o` or `--fuse` is a map of a stack that does not ship |

And **the output directory must not already exist** — F3 constraint 16.
A rebuild is a new artifact under a new `--name`, never an overwrite, so
a committed `registration.yaml` can never come to belong to a different
grid. Both refusals were exercised: a second run of the same command, and
a session recorded without `--bag`.

### 4.2 The parameters, and what each non-default is argued from

`m5_ver3/slam.yaml` is a ROS **parameter** file and is a second file
beside `config.yaml` for `ekf.yaml`'s reason: `sync_slam_toolbox_node`
reads a `<node>: ros__parameters:` mapping and `config.yaml` is not one
and is not bent into one.

**And the split is held by the same two mechanisms `ekf.yaml` gets, not
by prose.** Every value that is a NAME already written down elsewhere on
this track — `scan_topic`, `base_frame`, `odom_frame`, `map_frame` — is
**absent from `slam.yaml`** and passed by `build_map.sh` as a `-p`
override read from `topics.scan_nav`, `frames.base_link`, `frames.odom`
and `frames.map`. No name is in both files, and an override wins over a
params file, so a copy that reappeared in `slam.yaml` would be inert
rather than authoritative. What `slam.yaml` holds is what the mapper
DOES; what `config.yaml` holds is the addresses.

**And `build_map.sh` greps that `slam.yaml` is addressed to
`map.slam.node_name` before it starts anything**, which is
`m5v3.sh`'s `check_ekf_params()` in this node's currency. A ROS parameter
file keyed to a node that is never started applies nothing and rclcpp
says nothing — and here that is worse than a missing file, because the
four overrides above still land: the mapper would come up on its PACKAGE
defaults (0.5 m travel gate, 10-scan buffer, 3.0 m closure radius),
subscribe the right topic in the right frames, and **build a quietly
worse map of the right floor.** Every check downstream of that line would
pass. The refusal was exercised on a deliberately misspelt
`map.slam.node_name`, with the config restored byte-for-byte afterwards.

**Every default quoted below was read off the running node** on this rig
(`ros2 param get /slam_toolbox <name>` after the configure **and**
activate transitions — a lifecycle node declares nothing before them),
not copied from a README.

| parameter | shipped | set to | the argument |
|---|---|---|---|
| `minimum_travel_distance` | 0.5 | **0.30** | the floor's own scale. Rack segments are 0.50 and 1.00 m long, so at 0.50 m spacing a 0.50 m rack END — the only along-corridor feature a ring leg has — can be crossed between two nodes. 0.30 m puts at least two nodes on the shortest feature the floor has; about 750 nodes over 225 m. |
| `minimum_travel_heading` | 0.5 rad | **0.20 rad** | nine 90° corners. At 0.5 rad a corner is three nodes about 28.6° apart, which is OUTSIDE `coarse_search_angle_offset` (0.349 rad = 20.0°): the coarse match would be starting from further away than its own window. 0.20 rad makes a corner eight nodes. |
| `minimum_time_interval` | 0.5 s | **0.20 s** | two scan periods at 15 Hz. At this profile's 0.2990 m/s the shipped 0.5 s would fix the node spacing at 0.15 m and the two travel gates would never get a vote. It is here to stop a STOPPED truck filling the graph and for nothing else. |
| `scan_buffer_size` | 10 | **30** | at 0.30 m spacing the shipped 10 is 3.0 m of history against a sensor that sees 25.0 m. 30 nodes is 9.0 m — longer than the 8.00 m width of every cruise corridor and longer than the 5.75 m rack pitch, so the running scan always contains at least one rack end. |
| `scan_buffer_maximum_scan_distance` | 10.0 | **25.0** | the shipped value is BELOW this sensor's own range, so it would drop exactly the long-range returns — the far wall of a 48 m hall — that carry the most geometry. Set to the scanner's range and not past it: further would only keep nodes whose scans do not overlap. |
| `loop_search_maximum_distance` | 3.0 | **5.0** | bounded from both sides, below. |
| `loop_search_space_dimension` | 8.0 | **10.0** | it brackets the radius above: ±5.0 m needs 10.0 m of correlation grid, and a radius that admits candidates the correlator cannot then look at is a radius that is not really there. |

**The loop-closure radius has an upper bound and a lower bound and both
are measured.**

- *Upper — the floor's own pitch, 5.75 m.* The rack segments stand at
  `x = ±4.25, ±10.00, ±15.75`, so the rack block repeats every 5.75 m
  along both rows. A search radius past that can find a bay that is not
  the bay it is standing in. 5.0 m is inside it.
- *Lower — the drift closure exists to remove.* The odometry this map is
  built on drifts **9.86 m of position and 23.4° of heading over 225.0 m**
  (§2.4). The CORRECTED trajectory is not that bad, because every node is
  scan-matched onto the running map before it is added — but the shipped
  3.0 m is smaller than the RAW drift over even a quarter of the run
  (1.70 m at 25 %, 6.44 m at 50 %), so it is a radius that could
  plausibly be smaller than the error it exists for.
- *The cost is stated rather than hidden.* Between 3.0 m and 5.0 m
  nothing in this configuration answers the aliasing question. What
  guards it is that **both** loop-closure response thresholds are left at
  their shipped values — 0.35 coarse and 0.45 fine — so a bay that merely
  resembles the right one still has to beat them.

**Two more differ and neither is tuning.** `use_map_saver` is turned OFF
(shipped `true`) because there is exactly one map exporter on this track
and it is nav2's `map_saver_cli` — slam_toolbox's own would be a second
path to the same artifact with its own unstated thresholds, and a grid is
what everything downstream is scored against. And `scan_queue_size` goes
from 1 to 10: that is the tf2 message filter's queue, and live at 15 Hz
against a 50 Hz transform nothing ever waits, so 1 is right. In a REPLAY
the interleaving of two recorded topics is not the interleaving the plant
produced — rosbag2 plays by receive time — so a scan CAN arrive a beat
before the transform that brackets it. A queue of 10 costs ten scans of
memory and removes the one place a replay could silently drop a
measurement the plant delivered, which is the property the whole
offline-sync choice was made for.

**Everything else is shipped and untouched**: the whole correlation
block, the loop-search-space resolutions, every scan-matcher penalty, the
Ceres solver block and both covariance scales. Those are the knobs a map
is most easily flattered with, and this gate's job was to find out what
`warehouse_ver3` does to a scan matcher, not to arrange it.

### 4.3 Two parameters the vendor's own offline file carries and this build ignores

`/opt/ros/jazzy/share/slam_toolbox/config/mapper_params_offline.yaml`
sets `min_laser_range: 0.0` and `max_laser_range: 20.0`. **slam_toolbox
2.8.5 declares neither.** Measured: the node was started bare, driven
through configure and activate, and `ros2 param list /slam_toolbox` then
returns 68 names (the four `qos_overrides` aside) — including
`map_update_interval` and `transform_publish_period`, which are declared
in `on_activate` rather than `on_configure` — and **not** either laser
range. Both keys in the vendor file are read by nothing, so setting them
here would have been a comment wearing the shape of a decision.

What decides the range instead is the **scan message**: `range_min 0.05`
and `range_max 25.0`, the TiM571 profile in
`gazebo/forklift_ver3/model.sdf`. That matters here rather than being a
footnote, because **9.226 % of the 8,944,094 finite returns in this
recording are beyond 20.0 m** (§3) — so a `max_laser_range` of 20.0, had
it been read, would have thrown away a tenth of the measurement and all
of the long sightlines down a 48 m hall.

---

## 5. The SLAM run: what came out, and whether it repeats

### 5.1 The run

```
bash m5_ver3/tools/build_map.sh m5_ver3/logs/evidence/drive-mapping-20260826-174815
```

Three children, one log each, on domain 98: the static `base_link →
nav_lidar_link` transform, `sync_slam_toolbox_node` (2.8.5, driven
through its own `configure` and `activate` transitions), and
`ros2 bag play` at 0.5×. 785 s of recording at half speed is about 26
minutes of wall time, then a 30 s settle, then the pose graph, then the
grid.

**The graph was corrected 35 times during the replay** — one Ceres solve
per accepted loop closure, counted in `logs/map_slam.log`. The travel
gate admits a node every 0.30 m, so the 225.0 m drive is a graph of order
750 nodes. **One scan was dropped**, the first: `Message Filter dropping
message: frame 'nav_lidar_link' at time 30.626 ... the timestamp on the
message is earlier than all the data in the transform cache`. That is
the replay's very first scan arriving a beat before the first `/tf` did;
it is logged rather than silent, and it is one scan of 11,877.

### 5.2 The artifact

| file | bytes | md5 |
|---|---|---|
| `warehouse_v3.pgm` | 2,047,569 | `735cdbc68cfde4971e03f509347839d6` |
| `warehouse_v3.yaml` | 136 | `a3c76218755a9ffe97c0d9f71fb1b19e` |
| `warehouse_v3.posegraph` | 48,681,077 | `4bb88852b2f176ff90f812cbb9f2c176` |
| `warehouse_v3.data` | 13,788,841 | `e2d3c013b4a31d4158f1ed40f4565fd5` |
| `registration.yaml` | 3,343 | `690ee1951b6a26461f582ab9ec4f6d2b` |
| `build.txt` | 761 | `5813b2f964971823943fdf2ced403a07` |

and the inputs those came from:

| input | md5 |
|---|---|
| `m5_ver3/slam.yaml` **as it was at the build** | `076ae1e9d38fbbab7c7d6c03dc296975` |
| `m6/gazebo/warehouse_ver3.sdf` | `9157227ad44f06ac7f487e25ad7c7eda` |
| the recording's `bag_0.mcap` (untracked) | `dc2f21c8c875970d5dfc820fb2896ada` |
| the recording's `scan_nav.csv` (untracked) | `bf3473c8f3b2d9ef4fea3f9a8254ca6f` |
| the recording's `odom_truth.csv` (untracked) | `77a0f780d0a5ce8d14aedbb0ba44c2a0` |

The grid is **1712 × 1196 cells at 0.050 m = 85.60 × 59.80 m**, which is
larger than the 48 × 32 m hall. **That is unknown padding and not
geometry** — §7.3 counts it: 72.5 % of the raster is unknown, and every
occupied and every free cell in it falls inside the building.

> **`slam.yaml`'s md5 has moved since the build and the map has not.**
> `build.txt` records `076ae1e9d38fbbab7c7d6c03dc296975`, which is what
> that file hashed to when this map was made; it now hashes to
> **`32e00dc551e879b0e8f7461e991ccc13`**. `build.txt` is a record of what
> WAS read and is left alone; this is the note that stops the difference
> being a mystery.
>
> **The change cannot have changed the map, and that is checkable rather
> than asserted.** F3's first fix round removed four keys from
> `slam.yaml` — `scan_topic`, `base_frame`, `odom_frame`, `map_frame` —
> because they were a second copy of `topics.scan_nav`,
> `frames.base_link`, `frames.odom` and `frames.map`, and
> `tools/build_map.sh` now passes all four as `-p` overrides from
> `config.yaml` instead. **The four pairs were identical at the moment
> they were separated**, so the mapper is handed the same four strings it
> was handed then:
>
> | key | value at the build (in `slam.yaml`) | value now (from `config.yaml`) |
> |---|---|---|
> | `scan_topic` | `/forklift/gz/scan_nav` | `/forklift/gz/scan_nav` |
> | `base_frame` | `base_link` | `base_link` |
> | `odom_frame` | `odom` | `odom` |
> | `map_frame` | `map` | `map` |
>
> Nothing else in the file moved: the other 54 parameters are unchanged,
> which `git diff` shows and which is why **the map was NOT rebuilt** —
> F3 constraint 16 freezes it, and a rebuild to chase a comment would
> have replaced a scored artifact for no measurable reason. The six
> frozen files are byte-identical to the ones in `c02e3ff`.

### 5.3 It repeats — measured, not asserted

The whole argument for offline sync over online async
(`docs/reports/m5v3-01` §a) is that the same recording gives the same
map. That is checkable, so it was checked.

**The pose graph was built THREE times from the same bag with the same
`slam.yaml` at the same playback rate, in three separate invocations
minutes apart, and all three are byte-identical:**

| run | ended | `.posegraph` md5 | `.data` md5 |
|---|---|---|---|
| 1 | 19:05 | `4bb88852…c176` | `e2d3c013…5fd5` |
| 2 | 19:40 | `4bb88852…c176` | `e2d3c013…5fd5` |
| 3 (the artifact) | 20:20 | `4bb88852…c176` | `e2d3c013…5fd5` |

And the grid is a deterministic **rendering** of that graph, which was
checked separately: run 1's serialized graph was deserialized into a
fresh `slam_toolbox` on a fourth ROS domain and its occupancy grid
saved — `735cdbc68cfde4971e03f509347839d6`, the same md5 as the grid the
artifact carries.

> **What that does and does not say.** It says this recording, these
> parameters and this rate give one answer on this machine. It does not
> say the answer survives a different playback rate, a different machine
> load or a different ROS build, and none of those was tested.

### 5.4 Two failures on the way, both in the exporter and both now checks

Runs 1 and 2 produced a complete pose graph and then **refused at the
last step**, and neither failure was in the SLAM. They are here because
the fixes are now refusals in `build_map.sh` rather than knowledge in
somebody's head.

**(a) `map_saver_cli` has a deadline of its own and it is 2.0 s.** It
exits 1 with `Failed to spin map subscription` two seconds after it
starts, so the shell's own `timeout` never comes into it. Against
`slam_toolbox`'s `/map` at the end of a 750-node run, 2.0 s is not
enough. `map.slam.save_map_timeout_s` is now passed, and the value is
spelled **`120.0`** because the parameter is a `double` and `:=120` is
refused by rclcpp as an integer — which is how run 2 was lost.
`build_map.sh` also now checks that `/map` is on the wire BEFORE the
saver runs, so a future failure says which of the two halves broke.

**(b) `map_saver_cli` advertises `--occ` and `--free` and ignores both.**
Measured on this rig against a grid published by hand: saved with
`--occ 0.77 --free 0.33`, the yaml it writes reads `occupied_thresh:
0.65` and `free_thresh: 0.196` — its own defaults, unchanged, no warning.
So `build_map.sh` **passes neither flag** and instead **reads the written
yaml back and refuses** if either value is not the one `config.yaml`
states. A flag that does nothing is worse than no flag: it makes the
shell look as though it decided something.

> **And which value landed matters.** `slam_toolbox` writes 0, 205 and
> 254 into the grid for occupied, unknown and free. 205 is a shade of
> 50/255 = **0.19608**, a whisker ABOVE the 0.196 that landed — so a
> consumer reading this yaml classifies the unknown cells as UNKNOWN,
> correctly. Had the free threshold been the 0.25 `config.yaml` first
> asked for, **every one of the 1,484,112 unknown cells in this grid
> would have read as open floor.** The right value landed, and it did not
> land because anything in this repository asked for it.

---

## 6. The registration, and the instrument floor

**Instrument:** `python3 m5_ver3/tools/map_register.py derive --write`.
Needs no ROS and no Gazebo; the arithmetic is `tools/map_core.py` and
82 pytest cases in tests/test_map_core.py reach it without a simulator.

### 6.1 Three walls anchor the fit, and the fourth cannot

`nx`/`ny` is the OUTWARD normal and the offset is taken as `min(n·p)`
over the model's own box, so **the true face is read out of the world SDF
and not typed into the config.** `warehouse_ver3`'s floor is centred on
`y = −2.00` and not on the origin, which is why the face is computed from
the box rather than from `abs(centre) − half` — the m5_ver1 tool did the
latter, on a hall that happened to be centred, and it would be wrong here
by 2.00 m on two walls of four.

**`WallSouth` is not an anchor, and that is the building rather than the
drive.** The dock annex (`AnnexW/A/B/C/E`) stands from `y = −18.00` to
`−14.00` and is 4.00 m tall, so over 28.00 m of the wall's length the nav
lidar sees the **annex front at `y = −14.000`** and nothing behind it; in
the four bay openings the **bay backs stand at `y = −17.900`**, one tenth
of a metre in front of the wall, over the other 20.00 m. The outermost
occupied cell in −y is therefore a *different true surface* depending on
where you look, and one line fitted to all of them would be a line
through neither.

Three walls spanning two directions determine a rigid SE(2) completely —
`map_core.solve_translation` **refuses** a set that does not, and
`tests/test_map_core.py` asserts the refusal on an east+west-only set.
What is lost is the north–south redundancy; what replaces it is better
than what was lost: **the annex front becomes a HELD-OUT surface the fit
never sees.**

### 6.2 The trimming rule, stated before any number it produced

Every grid line that has an occupied cell contributes **one** candidate —
the outermost one — and **nothing is filtered at extraction**. The line
is then SEEDED by a repeated median (50 % breakdown point), trimmed at
**3 cells = 0.150 m**, and refitted by total least squares until nothing
more drops.

> A least-squares SEED converges onto whatever stands in front of the
> wall and then reports a TIGHT residual against it — a small residual
> against the wrong surface, which is the failure that looks like
> success. `docs/LESSONS.md` 93 measured it on the m5_ver1 grid: seeded
> by least squares, one wall fitted at −1.61°, −1.80°, −1.43° and −1.32°
> at four trim widths; seeded by the repeated median, +1.69° at all four.
> `tests/test_map_core.py` asserts both halves on synthetic walls: that
> the robust seed recovers a wall with 40 % contamination 0.50 m in front
> of it, and that the least-squares fit of the same points does not.

**And the scan direction is the normal in MAP coordinates, not world
coordinates.** `slam_toolbox`'s map frame is the odom frame, and this
stack's odom frame is the vehicle at spawn, which stands at **yaw π** —
so the world's north wall is the *bottom* of this grid. A scan that went
looking for the outermost cell in +y would have found the world's SOUTH
side and fitted it beautifully. The rotation search is therefore hinted
at `−vehicle.spawn.yaw`, and the hint is **derived, not typed**; it is
only a hint, because the scan still runs ±8° around it and **refuses a
minimum that lands on its own edge** rather than reporting a clipped
angle.

### 6.3 The fit

| wall | outward n (world) | scanned as (map) | true face | extremes | kept | dropped | fit rms | own rotation |
|---|---|---|---|---|---|---|---|---|
| `WallNorth` | (0, +1) | (0.00, −1.00) | 14.000 m | 963 | 960 | 3 | 0.0219 m | +0.0227° |
| `WallEast` | (+1, 0) | (−1.00, −0.00) | 24.000 m | 644 | 563 | 81 | 0.0260 m | −0.1881° |
| `WallWest` | (−1, 0) | (+1.00, 0.00) | 24.000 m | 644 | 561 | 83 | 0.0201 m | +0.0769° |
| *held out* `annex_front` | (0, −1) | — | 14.000 m | 560 | 537 | 23 | 0.0338 m | −0.1199° |

`own rotation` is against the fitted θ and not against the world's axes,
because the map frame is half a turn from the world and "−179.79°" is not
a number anybody can read. What matters is the spread.

```
p_map = R(theta) . p_world + t
theta = -3.138328398 rad = -179.812971942 deg
t     = (-17.111857467, +9.798692466) m
```

**`t` is the spawn pose**, `(−17.00, +10.00)`, to 0.11 m and 0.20 m —
which is what it has to be if the map frame is the odom frame and the
odom frame is the vehicle where it stood at t = 0. Nothing made it come
out that way; it is the first thing that says the fit is not nonsense.

### 6.4 THE INSTRUMENT FLOOR

```
residual rms   0.0291 m   over 2084 wall points
residual MAX   0.1179 m   <- NO LOCALISATION FIGURE AT OR BELOW THIS
                             IS A MEASUREMENT OF THE LOCALISER
internal shear 0.2650 deg
```

**Nothing localised against this map may be reported as better than
0.1179 m without saying so.** The residual is the largest distance
between a kept grid wall point and where the fitted rigid transform says
that wall is; no rigid transform fits this grid to this building better
than that. Most of it is the shear — the amount by which the grid is not
a rigid copy of the building — which a rigid transform cannot absorb by
construction and is not asked to. That is why the transform is rigid:
absorbing the shear into a per-wall or a scale freedom would hide it in
exactly the figure that exists to reveal it.

**How much of that floor is the instrument and how much is the map.** A
0.05 m cell quantises every candidate's normal coordinate to a cell
centre, and the rms of a uniform error one cell wide is
`0.05/√12 = 0.0144 m`. So **no fit to a 0.05 m grid can report below
0.0144 m**, and `tests/test_map_core.py::TestQuantisationFloor` asserts
exactly that on a perfect synthetic wall. The tool was then run end to
end on a **synthetic grid of this floor's true geometry** rasterised at
the same 0.05 m — the three walls, the annex fronts, the bay backs and
all twelve racks, pushed through a known half-turn transform — and it
returned:

| | synthetic (a perfect map) | **warehouse_v3 (this map)** |
|---|---|---|
| θ recovered | to **0.0051°** of the truth | — |
| t recovered | to **2 mm** of the truth | — |
| residual rms | **0.0144 m** (= 0.05/√12) | **0.0291 m** |
| residual max | 0.0274 m | 0.1179 m |
| internal shear | 0.0011° | 0.2650° |

So the instrument's own floor on a 0.05 m grid is 0.0144 m, and **this
map sits at 2.02× it.** The remaining rms and the 0.265° of shear are the
map, not the ruler.

---

## 7. The absolute score

### 7.1 Spans, and why they need no transform

A span is a distance between two surfaces **inside** the map. With
`p_map = R(θ)p_world + t` and two opposed unit normals the translation
cancels exactly — `(n_a + n_b)·t = 0` — so **no choice made while fitting
can flatter a span.** A grid whose metres are one per cent long reports a
48.00 m hall as 48.48 m however it is registered.

> This is the m5_ver1 lineage's own lesson taken at its word.
> `WAREHOUSE_SLAM_EVIDENCE.md` §12.8: an error measured by anchoring the
> estimate onto truth at the first sample is zero at the anchor **by
> construction**, and an estimator that is consistently 0.3 m wrong
> scores near zero. **Nothing here is anchored to anything.**

`config.yaml` states each true span and `map_register.py` **re-derives
both from the world SDF's own faces and refuses if they disagree**, so
the stated number is a copy that says when it has gone stale.

| span | true | measured | error | in cells |
|---|---|---|---|---|
| hall width, east to west (`WallEast`↔`WallWest`) | 48.000 m | **48.0194 m** | **+0.0194 m** | +0.39 |
| north wall to annex front (`WallNorth`↔`annex_front`) | 28.000 m | **28.0361 m** | **+0.0361 m** | +0.72 |

**The second row is the held-out one.** The transform was solved without
a single annex-front point, so nothing about the fit arranged that
28.0361. Both spans are long by under three quarters of one cell, over a
48 m and a 28 m baseline — **0.040 % and 0.129 %.**

### 7.2 Against the only other map this repository has

| map | rms | MAX | shear |
|---|---|---|---|
| **this map — `warehouse_ver3`, 48 × 32 m, TiM571 25 m, 225 m drive** | **0.0291 m** | **0.1179 m** | **0.2650°** |
| m5_ver1 warehouse — 30 × 20 m, ideal 8 m scanner, different route | 0.0404 m | 0.1411 m | 0.3250° |

**THE SECOND ROW IS NOT A TARGET AND NOT A BASELINE.** It is a different
hall, a different scanner, a different vehicle and a different route,
measured by the same method — which is the only sense in which the two
numbers belong on one page. This map is tighter on all three, on a floor
2.6× the area with a scanner three times the range; what that comparison
is worth is "the method behaves", and nothing more.

### 7.3 Does it cover the drivable floor

```
hall       48.00 x 32.00 m, the four walls' INNER faces
building   48.40 x 32.40 m, their OUTER faces
open floor 1394.0 m2   (the hall less 25 obstacle footprints)
mapped FREE inside it  1369.0 m2 = 98.21 %
cells      15757 occupied, 547683 free, 1484112 unknown, 2047552 total
in the wall fabric     933 occupied, 78 free
OUTSIDE THE BUILDING   0 occupied, 0 free
```

**Zero.** Not one occupied cell and not one free cell of this grid falls
outside `warehouse_ver3`'s own outer walls. A diverged run puts geometry
outside the building it was built from, and that count is not a threshold
— it is either zero or it is a finding.

The 933 occupied cells in the **wall fabric** — the 0.20 m band between
the walls' inner and outer faces — are the walls themselves. A wall's own
cells sit ON the inner face, so a return two centimetres proud of it is a
wall and not evidence of anything; counting the band as "outside" would
have turned the building into a defect. The zone is measured separately
for that reason.

**98.21 % of the open floor is marked FREE.** The open floor is derived,
not asserted: the hall's 1536.0 m² less the 142.0 m² of the 25 obstacle
footprints `map_core.sdf_obstacles()` reads out of the world — twelve
rack segments, five annex blocks, four bay backs and the four walls, and
nothing that has only a `<visual>` (the floor paint, the lane marks, the
station discs and the pallet loads are all invisible to a scanner at
z = 1.80 m and are not obstacles either).

And the map's 85.60 × 59.80 m raster is **72.5 % unknown** — padding
`slam_toolbox` reserves around the graph, carrying no claim at all.

---

## 8. What is frozen, and what makes it frozen

`m5_ver3/maps/warehouse_v3/` is committed whole: the grid, the pose
graph, `build.txt` and `registration.yaml`. The md5s are §5.2.

**The freeze is a mechanism and not a promise** (F3 constraint 16):

| mechanism | what it prevents |
|---|---|
| `build_map.sh` **refuses an output directory that already exists** | a rebuild silently replacing a grid a committed registration belongs to |
| `registration.yaml` carries **`map_md5`**, and `map_register.load_registration()` refuses a mismatch | a consumer carrying this θ across a rebuild, which has its own rotation from the building |
| `build.txt` names the **session, the traction, the arm, the params file and its md5** | a map whose provenance has to be reconstructed from memory |
| `build_map.sh` refuses a session that is not `nominal` / `wheel+imu` | a map built on the slippery plant or a non-shipping estimator, unlabelled |

A rebuild is a **new artifact under a new `--name`**, never an overwrite.
Both refusals were exercised: a second run of the same command, and a
session recorded without `--bag`.

> **One cost, stated.** The pose graph is 48.7 MB and its `.data` 13.8 MB
> — 62.5 MB of binary in a repository whose `.git` was 185 MB. Every
> future map costs the same again, and `slam_toolbox` has no knob that
> makes a serialized graph smaller: it stores every scan. It is committed
> because a map without its graph cannot be continued, re-rastered at
> another resolution, or localised against in `map_and_localization`
> mode — but the second map on this track is the point at which somebody
> should decide whether these files belong in git at all.

## 9. What this map is not

Stated rather than left to be discovered.

**It has no south wall, and that is the building rather than the drive.**
The dock annex stands 4.00 m in front of the south wall over 28.00 m of
its length and the four bay backs stand 0.10 m in front of it over the
other 20.00 m, both 4.00 m tall. No ray from the drivable floor ever
returns from `WallSouth`. Anything downstream that expects a rectangular
hall boundary in this grid will not find one on the south side — it will
find the annex fronts at `y = −14.000` and the bay backs at
`y = −17.900`, which is what is there.

**It is a 2D slice at z = 1.80 m and nothing else is in it.** The nav
lidar is on the overhead guard roof (`model.sdf`, `nav_lidar_link`), so
the floor paint at z = 0.005, the pallet loads on top of the racking at
z ≥ 4.00 and the forks of any other vehicle are all invisible to this
map by construction. A costmap that needs them needs another sensor.

**It is one map from one drive on one plant.** Nominal traction,
`wheel+imu` arm, one route, one day. A map built from a `--slippery` run
or from the `--fuse` arm's odometry would be a different map, which is
why `build_map.sh` refuses both by name rather than letting them
through unlabelled.

**Its determinism was checked by rebuilding once, not many times.** §5.3
is a single repeat of a single recording. It says the run is repeatable;
it does not say the run is repeatable under a different machine load, a
different playback rate or a different ROS version.

**The aliasing question is not answered between 3.0 m and 5.0 m.**
`loop_search_maximum_distance` was raised from the shipped 3.0 to 5.0
because the odometry drift closure exists to remove is larger than 3.0 m
over most of this run (§4.2). The rack block repeats every 5.75 m, so
5.0 m is inside the pitch — but nothing in this configuration measured
the residual response of a neighbouring bay, the way
`sim/worlds/WAREHOUSE_LANDMARKS.md` did on the m5_ver1 floor. What guards
it instead is that both loop-closure response thresholds are left at
their shipped values.

**The scanner's shallow-incidence error is in every wall here and is not
modelled.** gz-sim issue #2743 (open): a `gpu_lidar` is measurably less
accurate than a CPU ray sensor at shallow incidence, which is what a wall
seen from 20 m down a corridor is. There is no CPU ray sensor in gz sim
and no fix upstream, so it is written down rather than worked around —
`gazebo/forklift_ver3/model.sdf` says the same thing at the sensor.

**There is no second, independent map to cross-check it against.**
`docs/reports/m5v3-01` §(a) ranks MOLA's `mola_mapper_2d` third and names
its use as exactly that — an independent second map — and it is GPL-3.
Not done here, and it is the honest way to find a systematic error this
method shares with itself.

**And it is a score of the MAP, not of a localiser.** Nothing has yet
been localised against this grid. What §6 measures is the floor under
that future figure; what §7 measures is whether the grid is the right
shape. The localiser is F3's next task, and the number it produces has to
be read against the 0.1179 m in §6.4 or it is not a measurement of the
localiser.
