# EVIDENCE — the warehouse map, built by SLAM against real odometry (m5-08b)

> ## SUPERSEDED, 2026-08-04, by m5-08d — read §12 before quoting anything here
>
> **The artifacts this file describes no longer exist in the working tree.**
> `sim/maps/warehouse/warehouse.{pgm,yaml,posegraph,data}` were rebuilt by
> brief `m5-08d` on 2026-08-04. The grid this file measures is
> `warehouse.pgm` md5 `8c48cc4e9d1771558eb3c648d9c15df8`; the committed
> grid is now `a663163036c5890937f9045bcf559e72`. **§12 records the
> replacement**, with the full md5 table and what changed.
>
> Three specific things in this file are now wrong or must be re-read, and
> they are corrected in place below as well as here:
>
> 1. **The −2.82° in §5 and §9 is not the map's rotation from the
>    building.** It is a single-sample frame relation at the first sample
>    of the drive. The m5-08b artifact's actual rotation, measured by
>    fitting its walls, is **+1.83°**, and the new artifact's is
>    **−0.45°**. Nothing may use a number from §5 as a world→map
>    transform: that transform now has one owner and one file,
>    `sim/maps/warehouse/warehouse_registration.yaml`, derived by
>    `sim/maps/warehouse/register_map.py`.
> 2. **Every error figure in this file — 0.185 m rms, 0.358 m max, 0.014 m
>    final — is ANCHORED DRIFT, not localisation error.** They remain
>    correct as drift figures and this file always said so. They are
>    invalid as a localisation score, because the anchor makes the first
>    sample zero by construction (`docs/reports/m5-08c-slam-judge.md`
>    finding 2). The instrument that produced them now demands
>    `--score anchored-drift` by name, and `--score absolute` is the mode
>    an AMCL number comes from.
> 3. **The 2.82° cosine correction in §9's span check used the wrong
>    angle** (the artifact's rotation is 1.83°). The effect is 0.01–0.02 m
>    and changes no conclusion; the span check was independently
>    reproduced by m5-08c at 30.046 m against a true 30.00 m.
>
> The run recorded in §§1–11 happened and its account of it is accurate.
> It is kept, not deleted, because the two maps are a measured before and
> after of the idle-drift fix.


**The first M5 run in which SLAM could fail.** Until brief m5-07c the
vehicle's pose came from Gazebo's ground truth, so scan matching was
scored against its own input and could not be wrong. m5-07c retired that:
the vehicle now estimates its own pose from a modelled encoder set and a
modelled IMU, and `agv/forklift/EVIDENCE_ODOMETRY.md` measures what that
costs — **5.21 m and −17.18° over a 106 m route**.

This file records what slam_toolbox built on top of that estimate, and
reads the result against the prediction `worlds/WAREHOUSE_LANDMARKS.md`
made **before** any SLAM run: three named degenerate stretches in the
fully-loaded east half where the only along-aisle information is ten
grazing rays.

**The short answer, and it is not the flattering one for the prediction as
a forecast of failure:** the map came out good — 0.185 m rms trajectory
error against ground truth, 0.014 m at the end of a 107.5 m closed circuit
— and **all three degenerate stretches were crossed with under 0.10 m of
along-aisle error growth**. The prediction was not wrong about the
geometry; §5 of this file shows exactly the mechanism it named, and shows
that odometry carried the vehicle through, which is the outcome
`WAREHOUSE_LANDMARKS.md` §9.4 asked to be reported as an odometry result
rather than a SLAM one.

---

## 1. Fixed inputs of the recorded run

| Item | Value |
|---|---|
| Date | **2026-07-31** |
| Environment | **project container** — Ubuntu 24.04.4 LTS (noble), kernel 6.18.5, `nproc` 4, 15 GiB. **This is not evidence about the owner's WSL2 host**, which has never run Nav2 or slam_toolbox (`setup/CONTAINER_TOOLCHAIN.md` §1, `setup/WSL_ENVIRONMENT.md`) |
| ROS 2 | Jazzy, `rmw_fastrtps_cpp` |
| Gazebo | `gz sim --versions` → `8.11.0` |
| `ros-jazzy-slam-toolbox` | `2.8.5-1noble.20260615.161600` |
| `ros-jazzy-robot-localization` | `3.8.3-1noble.20260615.152020` |
| `ros-jazzy-nav2-map-server` | `1.3.12-1noble.20260615.153120` (the map saver `/slam_toolbox/save_map` spawns) |
| Rendering | `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)` — **software rasterisation**, read from `/root/.gz/rendering/ogre2.log`, which was deleted before the run |
| Isolation | `GZ_PARTITION=m508b_map2`, `ROS_DOMAIN_ID=94`. **Both transports**, because gz transport is not DDS |
| Display | headless throughout, `QT_QPA_PLATFORM=offscreen`, no `gui:=true` |

Input files, `md5sum`, verified identical at the start and the end of the run:

```
c3bd8f810a72a3d4846d8a202f077e3e  sim/worlds/warehouse.sdf
b04706c41a379abf5b54f409843f8f98  agv/forklift/model.sdf
cdb8040252c0d71b43685687d8fb54ec  agv/forklift/config.yaml
da93e469fb357fab5bfa7f7ea5cd107f  agv/forklift/ekf.yaml
cc1cbc5a722ec81aa1d39bdc2354ca05  sim/config/slam_toolbox_warehouse.yaml
18e3446d4f091ad1e6e38ab5baad0029  sim/scenarios/warehouse_mapping_route.py
```

Run window, UTC:

```
bringup           2026-07-31T11:05:23Z
slam_toolbox      2026-07-31T11:05:43Z   (active 4 s later)
route start       2026-07-31T11:05:46Z
route end         2026-07-31T11:08:52Z
artifacts saved   2026-07-31T11:09:15Z
```

## 2. Real time factor, which this world was owed

`worlds/WAREHOUSE_EVIDENCE.md` §6 owed a real-time-factor figure for this
world taken on an uncontended machine. **This brief had the machine to
itself** — every run in it was serialised, and no other agent's simulator
ran beside it (LESSONS 2026-07-30).

| Configuration | Figure | Source |
|---|---|---|
| bringup alone, vehicle stationary | `real_time_factor: 0.99934892417589938` | `gz topic -e -t /stats` |
| bringup + slam_toolbox, over the 179 s drive | **0.9831 simulation seconds per wall second** | least squares over the route driver's 35 timed progress lines, `mapping_evidence.py closures`, max residual 0.198 s |

Real time at the world's 2 ms fixed step with three `gpu_lidar` sensors
rendering on four cores and software rasterisation, **and with a scan
matcher and a Ceres solver running beside it**. The ~0.1 figure quoted for
the pre-m5-08 world belonged to the retired platform and to a world that
carried an RGBD camera; it does not apply here and is superseded.

## 3. `odom → base_link` has exactly one publisher, captured

Two captures, from one dedicated run (`GZ_PARTITION=m508b_pubs`,
`ROS_DOMAIN_ID=95`) whose only purpose was this check, because it is a
property of the launch files and not of the mapping run.

**A. The warehouse bringup alone.** `ros2 topic info /tf --verbose`:

```
Type: tf2_msgs/msg/TFMessage

Publisher count: 1

Node name: forklift_ekf
Node namespace: /
```

and, over a 10 s subscription, every edge that appeared on `/tf`:

```
/tf
  Publisher count: 1
    Node name: forklift_ekf   Node namespace: /   Topic type: tf2_msgs/msg/TFMessage
  Edges observed over 10 s, parent -> child : messages
    forklift/odom -> forklift/base_link : 499
/tf_static
  Publisher count: 1
    Node name: sensor_tf
```

**One publisher, one edge.** With one publisher on the topic, that node is
the sole publisher of every edge on it — no attribution argument is
needed.

**B. The same bringup with `warehouse_slam.launch.py` beside it:**

```
/tf
  Publisher count: 3
    Node name: forklift_ekf   Node namespace: /   Topic type: tf2_msgs/msg/TFMessage
    Node name: slam_toolbox   Node namespace: /   Topic type: tf2_msgs/msg/TFMessage
    Node name: slam_toolbox   Node namespace: /   Topic type: tf2_msgs/msg/TFMessage
  Edges observed over 10 s, parent -> child : messages
    forklift/odom -> forklift/base_link : 393
    map -> forklift/odom : 352
```

Three publishers, and **`slam_toolbox` registers two of them itself** —
that is worth knowing before someone reads a count of 3 as three sources.
The edge set grew by exactly one, `map -> forklift/odom`, which is
disjoint from the EKF's. Read together with capture A, where the EKF was
alone on the topic, the ownership is pinned: the EKF owns
`forklift/odom -> forklift/base_link` and slam_toolbox owns
`map -> forklift/odom`, and neither touches the other's.

**This is structural, not a default.** `sim/launch/warehouse_bringup.launch.py`
carries no ground-truth TF bridge and no argument that adds one;
`sim/launch/forklift_bringup.launch.py`, which it includes, bridges no
transform at all. `agv/forklift/launch/vehicle.launch.py` does carry a
switchable ground-truth bridge, retired and off by default, and refuses to
start with both — but a launch file that cannot express the wrong
configuration is stronger than one that refuses it.

`/tf_static` has one publisher, `sensor_tf`, carrying `base_link` to the
four sensor frames. Two topics, two halves of one tree.

## 4. The route

Driven by `sim/scenarios/warehouse_mapping_route.py`, **a scripted
stimulus, not the teleop path**. The route is a constant in that file and
is printed by `--print-route`:

```
Stated mapping route - rear axle midpoint, world frame, metres
  the lidar rides 1.05 m ahead of this point and 0.40 m right of it

  (  -6.50,  -5.50)      0.00 m   W1  start, dock aisle west half, facing +x
  ( +11.90,  -5.50)     18.40 m   W2  dock aisle W->E   [crosses EAST DOCK, x +1.5..+7.0]
  ( +11.90,  +0.65)     24.55 m   W3  east end aisle S->N
  ( -11.90,  +0.65)     48.35 m   W4  aisle B E->W      [crosses EAST B, x +3.0..+7.0]
  ( -11.90,  +7.00)     54.70 m   W5  west end aisle S->N
  ( +11.90,  +7.00)     78.50 m   W6  aisle A W->E      [crosses EAST A, x +2.0..+7.0]
  ( +11.90,  +0.65)     84.85 m   W7  east end aisle N->S  (revisit)
  (  +0.00,  +0.65)     96.75 m   W8  aisle B E->W        (EAST B, second pass)
  (  +0.00,  -5.50)    102.90 m   W9  central cross aisle N->S
  (  -6.50,  -5.50)    109.40 m   W10 dock aisle E->W, back to W1  (circuit closed)

  total 109.40 m, 9 legs, 8 x 90 deg turns = 720 deg of turning
```

As driven: **107.54 m of ground-truth path, 914.9° of turning, 178.7 s of
simulation time.** (The path is 1.9 m under the stated 109.40 m because
pure pursuit cuts and overshoots corners rather than tracing them; the
turning exceeds 720° for the same reason.)

Four choices in that file that a reader should not have to infer:

- **The controller closes its loop on ground truth**, and that is stated at
  the top of the file. It stands in for the human at the tiller, and a
  human sees the aisle rather than the odometry. It makes the physical
  route reproducible; closing on the estimate would have put the vehicle
  4 m from the stated route by the end.
  **No ground truth reaches any estimator or the map.** The script
  publishes exactly two topics, both raw joint commands. The driver has
  truth; the estimator does not.
- **It bypasses the PLC**, publishing `/forklift/gz/traction_cmd` and
  `/forklift/gz/steer_cmd` directly, with the two unit conversions taken
  from `agv/forklift/config.yaml`. **So this run is not evidence about the
  M4 command path** and must never be offered as such. It is evidence about
  what a lidar carried around this world builds.
- **Speeds**: 0.80 m/s on the straights, 0.35 m/s whenever the steer angle
  exceeds 0.25 rad. Chosen once, before the run.
- **The end-aisle legs run at x = ±11.90, not the ±13.00 the landmark
  tables sample.** Those tables are sensor sample poses, not a claim that a
  vehicle fits there — see §7.

## 5. Read against the prediction

Both estimates are **anchored to the world at the first sample of the
drive**. Neither `forklift/odom` nor `map` is the world frame and neither
claims to be: `odom` is anchored at the spawn pose and `map` at whatever
pose the EKF was reporting when slam_toolbox processed its first scan.
Differencing either against a world-frame truth without anchoring measures
an arbitrary offset and calls it drift. Every number below is therefore
**drift since the start of the drive**, which is the quantity that means
something.

For this run both frames came out at `(-6.009, -5.500)`, rotated
**−2.82°** from the world. That rotation is the EKF's heading error at the
instant SLAM initialised — see §6.

> **Corrected 2026-08-04 (m5-08d).** That −2.82° is a **single-sample**
> frame relation at the first sample of the drive, and it is **not** this
> map's rotation from the building — the grid is drawn from all 327 graph
> nodes and does not inherit that instant. Fitting the artifact's own
> walls puts it at **+1.83°**. Nothing may use −2.82° as a world→map
> transform. That transform is derived, per map, by
> `sim/maps/warehouse/register_map.py`.

### Whole run

| estimate | final &#124;dx,dy&#124; | final heading | max &#124;dx,dy&#124; | rms &#124;dx,dy&#124; |
|---|---|---|---|---|
| EKF (dead reckoning) | 4.295 m | +23.64° | 4.295 m | 2.152 m |
| **SLAM (`map -> base_link`)** | **0.014 m** | **−0.41°** | **0.358 m** | **0.185 m** |

The scan matcher removed a 4.3 m / 23.6° dead-reckoning error down to
14 mm and 0.4°. **The map's geometric error is the trajectory error**,
because a scan is drawn into the grid at the pose the graph gives it, so
the 0.185 m rms figure is the honest statement about the map and "it looks
correct" is not needed anywhere in this file.

### The three named stretches, by name

Extents read out of `WAREHOUSE_LANDMARKS.md` §5 at run time rather than
copied. Membership is decided by the **sensor's** ground-truth position,
because those extents are sensor lines; the errors reported are the pose
estimate's, which is `base_link`'s. `along-x` is the error component
**along** the aisle — the direction those stretches carry no information
in.

| stretch | pass | samples | entry along-x | exit along-x | growth | max across-y | heading at exit |
|---|---|---|---|---|---|---|---|
| **East A** | 1 | 62 | +0.137 m | +0.155 m | **+0.018 m** | 0.056 m | −1.04° |
| **East B** | 1 | 51 | +0.025 m | +0.029 m | **+0.003 m** | 0.134 m | −1.34° |
| **East B** | 2 | 50 | +0.030 m | −0.009 m | **−0.039 m** | 0.107 m | −1.01° |
| **East dock** | 1 | 69 | +0.015 m | −0.076 m | **−0.091 m** | 0.131 m | −0.90° |

And the same stretches for the EKF alone — what the scan matcher had to
work against inside them:

| stretch | pass | entry along-x | exit along-x | growth |
|---|---|---|---|---|
| **East A** | 1 | −1.799 m | −1.929 m | −0.130 m |
| **East B** | 1 | −0.427 m | −0.413 m | +0.014 m |
| **East B** | 2 | −0.107 m | +0.110 m | +0.217 m |
| **East dock** | 1 | +0.034 m | +0.042 m | +0.008 m |

### What that means, stretch by stretch

**East dock (x ∈ [+1.5, +7.0], y = −5.50, worst `aniso` 0.041).** Crossed
first, 22 m into the run, with the estimate still nearly perfect. Along-x
error moved from +0.015 m to −0.076 m, a growth of 0.091 m over 5.5 m —
the largest of the three, and still under 0.1 m. **No loop closure was
involved**: the first closure of the run did not occur until t = 126 s and
this crossing ended at about t = 27 s. Along-x here was carried by dead
reckoning, whose own along-x error grew 0.008 m over the same stretch.

**East B (x ∈ [+3.0, +7.0], y = +0.65, worst `aniso` 0.031).** Crossed
twice. First pass at t ≈ 48 s: growth +0.003 m. Second pass at t ≈ 145 s,
after 100 m of driving: growth −0.039 m, entering at +0.030 m — that is,
**the second pass entered East B with the same 30 mm of error the first
pass entered with**, 97 m of driving later. That is what a working graph
does. One loop closure fired inside East B on the second pass, at
(+4.85, +0.69) — §6.

**East A (x ∈ [+2.0, +7.0], y = +7.00, worst `aniso` 0.034, the worst pose
in the world at 0.034 with `top10` 99%).** Crossed at t ≈ 106–112 s, with
the EKF's along-x error already at −1.8 m. Along-x growth **+0.018 m over
5 m** — the smallest of the three, in the pose the prediction called worst.
The lateral error stayed under 0.056 m, the smallest across-aisle figure
of the four crossings, which is exactly what the prediction says should
happen: two flat parallel walls pin the sensor **across** the aisle
perfectly. The degeneracy is along-aisle and only along-aisle, and the
measurement shows both halves of that.

### So was the prediction wrong?

**No. It was right about the geometry and right about the mechanism, and
the outcome it produced is the one it listed as needing to be reported as
an odometry result.** `WAREHOUSE_LANDMARKS.md` §9.4 says: *"If a SLAM run
comes out better than section 5 predicts in the east half, find out why
before believing it. The two candidates are that the run never held still
long enough for drift to show, and that odometry carried it."*

Both candidates apply, and they are measurable:

1. **Odometry carried it, and the arithmetic is small.** The prediction is
   about what the scan cannot correct, not about how much error there is
   to correct. A degenerate stretch is 4.0 to 5.5 m long and this vehicle
   crossed each in 5 to 7 s at 0.80 m/s. The EKF's own along-x error grew
   by 0.008 to 0.217 m over those spans (table above). **The scan matcher
   only had to not make it worse**, and it did not: 0.003 to 0.091 m. The
   17° of heading the brief warned about is an error accumulated over
   106 m, not over 5 m, and SLAM had already removed it at the mouth of
   every aisle where structure was available.
2. **The run never held still in a degenerate stretch.** It drove through
   at cruise. A vehicle that stops, manoeuvres or reverses inside East A —
   which is what a picking or a docking manoeuvre does — spends far longer
   with nothing correcting along-x, and this run says nothing about that
   case.

The finding is therefore **not** "the degeneracy does not matter". It is:

> **Along-aisle information in the east half is carried by odometry over
> the length of one degenerate stretch, and that is sufficient at
> 0.80 m/s in a single traverse. It is a statement about a 5 m dead
> reckoning budget, not about scan matching.** The condition that would
> break it is dwell — stopping, reversing or repeatedly manoeuvring inside
> the stretch — and no measurement here bounds that.

Two further pieces of support that this is a real crossing and not a
lucky one:

- the vehicle's own mast contributes 9 of 360 rays and carries no
  information about where it is (`WAREHOUSE_LANDMARKS.md` §6); nothing in
  this run changes that;
- the maximum SLAM error anywhere in the run, 0.358 m, occurred nowhere
  near a degenerate stretch — the per-stretch maxima are 0.056 to 0.134 m
  across-aisle and under 0.16 m along it.

## 6. Loop closure: ten of them, and where they came from

One Ceres solve is one graph optimisation, and slam_toolbox calls the
solver only from `MapperGraph::CorrectPoses()`, which runs only after
`TryCloseLoop()` succeeded. The count is therefore a count of printed
lines, not an inference:

```
| #  | route time | at ground truth  | on                        |
| 1  | 126.4 s    | (+12.15, +4.86)  | east end aisle            |
| 2  | 127.9 s    | (+11.93, +3.74)  | east end aisle            |
| 3  | 128.3 s    | (+11.87, +3.38)  | east end aisle            |
| 4  | 128.7 s    | (+11.84, +3.10)  | east end aisle            |
| 5  | 129.2 s    | (+11.82, +2.74)  | east end aisle            |
| 6  | 145.9 s    | ( +4.85, +0.69)  | East B                    |
| 7  | 161.7 s    | ( -0.02, -2.78)  | central cross aisle       |
| 8  | 162.6 s    | ( +0.06, -3.49)  | central cross aisle       |
| 9  | 163.0 s    | ( +0.08, -3.81)  | dock aisle cross aisle mouth |
| 10 | 163.3 s    | ( +0.09, -4.13)  | dock aisle cross aisle mouth |

total loop closures during the route: 10
Ceres solves outside the route window, not counted: 1
```

Three bursts, and each one is a revisit the route was built to create:

- **1–5, east end aisle, t ≈ 126–129 s.** Leg 7 drives the east end aisle
  southward, over ground first covered by leg 2 at t ≈ 26–33 s. The
  closure is against that chain, 95 s and 90 m of driving earlier.
- **6, inside East B, t = 145.9 s.** The second pass closing against the
  first (t ≈ 48 s). **A degenerate stretch produced a loop closure** — its
  across-aisle constraint is perfect, and its ten grazing rays were enough
  once the chain either side of it was already pinned.
- **7–10, cross aisle into the dock aisle, t ≈ 162–163 s.** The circuit
  closing back onto leg 1.

**But loop closure did not rescue the degenerate stretches, because they
did not need rescuing.** East dock was crossed at t ≈ 22–27 s, a hundred
seconds before the first closure, and came out with 0.091 m of along-x
growth. East A was crossed at t ≈ 106–112 s, also before the first
closure, with 0.018 m. Only East B's second pass had a closure inside it,
and it entered that pass already at 0.030 m. **The good result in the east
half is scan matching plus dead reckoning over 5 m, not a graph
optimisation cleaning up afterwards.** That distinction matters, because it
is the one that decides whether a vehicle that dwells in an aisle is safe:
it would be relying on the same 5 m budget with no closure available.

The `loop_search_maximum_distance` was raised from the shipped 3.0 m to
6.0 m, argued from the 5.21 m of accumulated error `EVIDENCE_ODOMETRY.md`
measures. **In this run it was not needed** — SLAM's own error never
exceeded 0.358 m, so every closure was found well inside 3.0 m. The
parameter cost nothing and it bought nothing here; it is kept because the
argument for it is about the error the closure exists to remove, and this
run's error was small only because the closures kept firing. **No false
closure appeared**: a false one 2.30 m along (the rack bay pitch) would
show as a step of that order in `map -> forklift/odom`, and the largest
step observed anywhere in the run was 0.166 m.

## 7. Two things that had to be driven to be found

**The end aisles are not drivable at x = ±13.00.** `warehouse.sdf` stands
four building columns at x = ±13.400, y = +3.850 and −2.550, 0.25 m
square. A 1.04 m wide vehicle centred on x = 13.00 spans [12.48, 13.52]
and fouls the column at [13.275, 13.525]. The first rehearsal of this
route **stalled at (13.245, −3.558) heading 94.1°** — the front left corner
in that column — and spent 400 s driving a stationary vehicle with nothing
complaining. `WAREHOUSE_LANDMARKS.md` samples that line because it samples
**sensor** poses; that is not a claim that a vehicle fits there, and this
file states it so the next brief does not rediscover it.

The route driver now carries a stall detector: less than 0.30 m of motion
in 8 s of simulation time while a non-zero speed is commanded aborts the
run and prints the pose.

A second rehearsal at x = ±12.20 completed the circuit with a **minimum
footprint-corner clearance of 0.196 m**, to the same column, at the W2
corner where pure pursuit overshoots ~0.30 m to the outside of a turn.
0.196 m is not a margin a repeatable procedure should stand on, so the
four end-aisle waypoints were moved 0.30 m inboard to x = ±11.90 **before**
the recorded run.

**`async_slam_toolbox_node` is a lifecycle node and does nothing at all
until it is transitioned.** Started as a plain `Node` it comes up
UNCONFIGURED and stays there: it logs `Node using stack size 40000000`,
warns nothing, errors nothing, subscribes to no scan, advertises no `/map`
and publishes no transform. The only visible difference from a working
node is that `ros2 topic list` shows `/slam_toolbox/transition_event` and
nothing else of it. `setup/CONTAINER_TOOLCHAIN.md` §4.7 had recorded
exactly that state in 2026-07-30 without naming the cause.
`sim/launch/warehouse_slam.launch.py` therefore emits the configure and
activate transitions, and the check that it worked is `/map` on the topic
list, never a clean-looking log.

## 8. The estimator drifts while parked, and the map frame inherits it

Measured twice in the recorded run, on the two stationary segments either
side of the drive:

```
parked before the drive     5.1 s, EKF heading moved   +0.68 deg  (+0.00230 rad/s at rest)
parked  after the drive    24.2 s, EKF heading moved   +3.28 deg  (+0.00237 rad/s at rest)
```

Two independent measurements agreeing to 3%: **the EKF integrates about
0.0023 rad/s of heading on a completely stationary vehicle**, which is
0.13°/s, or 8°/minute. The modelled gyro bias is 0.002618 rad/s
(`agv/forklift/model.sdf`, from the BMI088 datasheet) and `ekf.yaml` fuses
the IMU's yaw rate against a wheel odometry whose yaw rate is exactly
zero and whose variance is comparable, so the filter tracks most of the
bias. This is `docs/reports/m5-07c-realistic-odometry.md` open question 5
appearing as a number rather than as a prediction, and it is what a
zero-velocity update exists to remove.

**The consequence for the artifact is concrete: the map frame's
orientation is the EKF's heading error at the moment slam_toolbox
processed its first scan.** In the recorded run that was −2.82°, because
SLAM was activated 20 s after the bringup and the route began 3 s after
that. **An earlier attempt at this run left the stack idling for four
minutes first, and produced a map rotated about 20° from the building** —
visibly skewed, 677 × 596 cells for a 30 × 20 m hall instead of 614 × 421.
Nothing was wrong with that map internally; a SLAM map's frame is its own.
But a warehouse map that is not square to the warehouse is a poor artifact
for everything downstream, so the recorded procedure starts the drive as
soon as SLAM is active, and this file says why.

**Nothing about the drift is tuned away and the direction is not
reproducible.** `EVIDENCE_ODOMETRY.md` finding 2 records that gz draws the
gyro bias sign at random per run — three runs gave −17.18°, −16.41° and
+19.85°. So the map frame's rotation is a different small angle, of either
sign, on every run. Anyone re-running this must expect that and must not
read it as a defect.

## 9. The artifacts

Both are saved, and neither substitutes for the other.

| File | Bytes | What it is for |
|---|---|---|
| `sim/maps/warehouse/warehouse.pgm` | 258 509 | the occupancy grid AMCL will consume. 614 × 421 cells at 0.05 m = 30.70 × 21.05 m |
| `sim/maps/warehouse/warehouse.yaml` | 131 | its metadata |
| `sim/maps/warehouse/warehouse.posegraph` | 12 148 423 | the serialised pose graph — what lets mapping RESUME rather than restart |
| `sim/maps/warehouse/warehouse.data` | 4 227 463 | the serialised dataset that goes with it. The two are one artifact in two files |

```
8c48cc4e9d1771558eb3c648d9c15df8  sim/maps/warehouse/warehouse.pgm
306392c787c18f95d010d2927ee0ad2f  sim/maps/warehouse/warehouse.yaml
a7c8ade4b898fbd9d91cb9270c77ea79  sim/maps/warehouse/warehouse.posegraph
59ae8f84aef684f8575771ebcf296863  sim/maps/warehouse/warehouse.data
```

`warehouse.yaml` as written by the map saver:

```
image: warehouse.pgm
mode: trinary
resolution: 0.050
origin: [-9.596, -4.803, 0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
```

### The grid measured against the world file

The raster's 30.70 × 21.05 m bounding box is not a measurement of the hall
— it bounds the occupied cells of a grid whose frame is rotated, and the
vehicle never saw the outside of the building. So the hall was measured
**inside** the grid instead, by scanning for the first and last occupied
cell along lines that cross it cleanly:

| Measured in the grid | Value | `warehouse.sdf` says | Difference |
|---|---|---|---|
| west wall to east wall, four rows across aisle B | **30.050 m** (identical on all four) | 30.00 m between inner faces at x = ±15.00 | +0.05 m = **1 cell** |
| north wall to south wall, five columns through the central cross aisle | **20.05–20.10 m** | 20.00 m between inner faces at y = ±10.00 | +0.05 to +0.10 m = **1–2 cells** |

Those scans run along the image axes, which sit 2.82° off the wall
normals, so each reading is long by a factor `1/cos 2.82° = 1.0012` — 0.04
m on the 30 m span and 0.02 m on the 20 m one. Corrected, the map puts the
hall at **30.01 × 20.03–20.08 m against a true 30.00 × 20.00 m**, which is
inside the 0.05 m cell size in both directions.

> **Corrected 2026-08-04 (m5-08d).** The angle used here is wrong: the
> image axes sit **1.83°** off the wall normals, not 2.82° (see the
> correction in §5). `1/cos 1.83° = 1.0005`, so the correction is 0.015 m
> on the 30 m span rather than 0.04 m. **The conclusion is unchanged** —
> the map is still inside one cell in both directions — and m5-08c
> reproduced the east-west span independently, perpendicular to fitted
> walls, at **30.046 m against a true 30.00 m**.

That is the check that says the map is right. "It looks correct" appears
nowhere in this file.

A cruder check on the same grid is reported because it FAILED and the
reason matters: fitting a line to the topmost occupied cell of each column
gives the north edge at +1.57° with a 0.45 m rms residual, and the same
fit on the west edge gives +25.9° with 4.8 m — both useless, because rack
row A stands against the north wall and the west edge of the raster is
mostly rack ends and the partially-observed wedges described next. An
edge-of-raster fit measures whatever the raster's edge happens to be; the
inner-span scans above measure the building.

### The fan-shaped grey wedges are correct, and they are worth knowing

The grid carries several wedges of *unknown* cells fanning out from
narrow apertures, mainly along the west half and through the south wall.
They are not artifacts of a bad pose. They are the geometry the world was
built with:

- the **west runs are depleted on alternate bays at the reserve level**
  (`warehouse.sdf`, "reserve level occupancy"), so at the navigation
  plane's 1.80 m the lidar looks straight through an empty bay into the
  back-to-back flue and out the far side. Cells behind that aperture are
  seen from a narrow range of bearings and only from the few poses that
  line up, which is exactly what produces a fan;
- the **dock door gap** is a 4 m opening in the south wall, and rays
  through it leave the building into space the vehicle never visited.

The east half has no such wedges, because every east bay is loaded. The
map therefore shows the same east/west asymmetry `WAREHOUSE_LANDMARKS.md`
§3 declared before any of this was run — from the other side: the west
half is well conditioned *because* it is full of holes, and the holes are
visible in the grid.

**The pose graph was checked to load, not merely to write.** Calling
`/slam_toolbox/deserialize_map` on the running node against the saved
files logged `Load From File`, re-registered the sensor
(`Registering sensor: [Custom Described Lidar]`) and ran one solver pass.
That solver pass is the "1 Ceres solve outside the route window" in §6 and
is not a loop closure.

The graph itself: **327 markers on `/slam_toolbox/graph_visualization`**,
one per pose-graph vertex, for 107.54 m of driving.

**A note for whoever commits these.** `.gitattributes` marks `*.pgm -text`
explicitly and that covers the grid. It does **not** cover `.posegraph` or
`.data`: `git check-attr text` reports `auto` for both, so they rely on
git's heuristic. The heuristic is correct today — both carry NULs in their
first 8000 bytes (1495 and 1518 of them) — but LESSONS 2026-07-27 is that
a generated binary is marked rather than detected, because the cost of the
rule is one line and the cost of a misdetection is silent corruption. Two
lines are requested in `docs/reports/m5-08b-slam-mapping.md`; that file is
not `sim/`'s to edit.

## 10. Reproducing this

```
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=<unique> ROS_DOMAIN_ID=<n> QT_QPA_PLATFORM=offscreen

# terminal 1 - plant, vehicle and the vehicle's own pose estimate
ros2 launch sim/launch/warehouse_bringup.launch.py

# terminal 2 - the mapper. Start it and DRIVE PROMPTLY (section 8)
ros2 launch sim/launch/warehouse_slam.launch.py

# terminal 3 - the evidence recorder, started before the drive
/usr/bin/python3 sim/scenarios/tools/mapping_evidence.py record \
    --csv /tmp/run.csv --seconds 600

# terminal 4 - the route
/usr/bin/python3 sim/scenarios/warehouse_mapping_route.py \
    --leg-log /tmp/legs.csv

# then, in any terminal, both artifacts
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
    "{name: {data: '<repo>/sim/maps/warehouse/warehouse'}}"
ros2 service call /slam_toolbox/serialize_map \
    slam_toolbox/srv/SerializePoseGraph \
    "{filename: '<repo>/sim/maps/warehouse/warehouse'}"

# the registration for the map just saved. PER MAP - re-derive every time
python3 sim/maps/warehouse/register_map.py derive --write

# and the reading. --score is MANDATORY (superseded 2026-08-04: this line
# read `analyse --csv /tmp/run.csv` and silently produced the anchored
# quantity). Use anchored-drift for a mapping run, absolute for a
# localisation score.
/usr/bin/python3 sim/scenarios/tools/mapping_evidence.py analyse \
    --csv /tmp/run.csv --score anchored-drift
/usr/bin/python3 sim/scenarios/tools/mapping_evidence.py closures \
    --slam-log <slam stdout> --route-log <route stdout> --csv /tmp/run.csv
```

Four traps, all hit during this work:

- **`save_map` races the map publisher.** The nav2 map saver that
  `/slam_toolbox/save_map` spawns waits 2 s for a message on `/map`, and
  `map_update_interval` is the shipped 5.0 s, so the call fails perhaps
  half the time with `Failed to spin map subscription` and
  `result=255`. **Check the result and retry**; the run recorded here
  succeeded on the second attempt. The parameter was deliberately NOT
  lowered to work around a client-side timeout — that would be changing
  mapping behaviour to fix a save.
- **Every consumer needs `use_sim_time:=true`.** A node on the system
  clock differences two clocks, asks tf2 for a transform ~1.8e9 s in the
  future and is told the transform does not exist. That reads as a missing
  publisher or a broken tree and is neither. Both launch files set it; so
  do the route driver and the recorder.
- **`ros2 topic info /tf` answers `Unknown topic '/tf'` for about 25 s
  after a bringup**, then answers correctly. A negative taken immediately
  is a discovery artifact, exactly as `CONTAINER_TOOLCHAIN.md` §8 records
  for `ros2 topic hz`.
- **Signalling `ros2 launch` does not bring its group down.** Check
  `ps -eo pid,args` for `gz sim`, `parameter_bridge`, `ekf_node`,
  `wheel_odometry`, `sensor_tf` and `async_slam_toolbox_node`, and finish
  each survivor by exact pid. Match on observed output, not on `pgrep -f`,
  which matches its own invoking shell.

To look at the grid:

```
/usr/bin/python3 -c "from PIL import Image; Image.open('sim/maps/warehouse/warehouse.pgm').show()"
```

## 11. What this run does not establish

- **Nothing about the owner's WSL2 host.** Container evidence only. That
  host has never had `slam_toolbox`, `navigation2` or
  `robot_localization` installed or checked (`setup/WSL_ENVIRONMENT.md`).
- **Nothing about localisation.** A map is not AMCL. Whether this grid is
  enough to localise in — particularly in the east half, where the same
  degeneracy applies to AMCL with no graph to fall back on — is the
  localisation brief's question, and `WAREHOUSE_LANDMARKS.md` §9.2's
  reflector question is still open.
- **Nothing about dwell.** Every crossing of a degenerate stretch was a
  single traverse at 0.80 m/s. Stopping, reversing or manoeuvring inside
  one is untested and is the case §5 names as the real risk.
- **Nothing about a loaded vehicle, another speed or another floor.**
  `EVIDENCE_ODOMETRY.md` open question 8 applies unchanged: one floor, one
  speed, empty forks.
- **Nothing about the M4 command path.** The route bypasses the PLC (§4).
- **One run.** The gyro bias sign is drawn per run (§8), so a second run
  will produce different numbers. Nothing here is a repeatability claim.

---

## 12. The rebuild — m5-08d, 2026-08-04

This section records the artifacts that **replaced** the ones §§1–11
measure, and it is the section to read first. Everything above it is the
superseded run, kept as the before half of a measured comparison.

### 12.1 Why the map was rebuilt

`docs/reports/m5-08c-slam-judge.md` finding 1: the m5-08b grid is rotated
**2.0°** from the building, because the estimator integrated gyro bias
through the ~20 s of idle between bringup and the drive. That cause was
fixed in `agv/` by brief m5-07d — an encoder-gated zero angular rate
update — and this run is the first map built by a stack carrying it.

### 12.2 Environment

| Item | Value |
|---|---|
| Where | project session container. **Not the owner's WSL2 host**, which has never run this stack (`sim/setup/WSL_ENVIRONMENT.md`) |
| ROS 2 | Jazzy |
| Gazebo | Harmonic, `gz sim --versions` → `8.11.0` |
| slam_toolbox | `2.8.5-1noble.20260615.161600` |
| robot_localization | `3.8.3-1noble.20260615.152020` |
| Isolation | `GZ_PARTITION=m508d_map`, `ROS_DOMAIN_ID=71`. **Both transports**, because gz transport is not DDS |
| Display | headless, `QT_QPA_PLATFORM=offscreen`, `DISPLAY` unset |
| Seed | **none**, the same discipline as m5-08b, so the gyro bias sign is drawn fresh |

### 12.3 The estimator stack, captured

The bringup starts four `agv/`-owned processes where m5-08b started three:
`sensor_tf.py`, `wheel_odometry.py`, **`imu_gate.py`** and the
`robot_localization` EKF. `sim/launch/warehouse_bringup.launch.py` ties
all four to one `estimator` argument, because `ekf.yaml` fuses
`/forklift/imu_gated`, which only `imu_gate.py` publishes — started
without it the EKF silently runs on wheel odometry alone.

`mapping_evidence.py publishers --seconds 12`, bringup only:

```
/tf
  Publisher count: 1
    Node name: forklift_ekf   Node namespace: /   Topic type: tf2_msgs/msg/TFMessage
  Edges observed over 12 s, parent -> child : messages
    forklift/odom -> forklift/base_link : 470
/tf_static
  Publisher count: 1
    Node name: sensor_tf
VERDICT: 1 publisher(s) on /tf: forklift_ekf
```

The ground-truth TF bridge is not started and has no argument. With SLAM
up the count goes to 3 (both extras named `slam_toolbox`) and the edge set
gains exactly the disjoint `map -> forklift/odom`.

**The gate is live, not merely started.** Parked, `/forklift/imu` runs at
100.038 Hz and `/forklift/imu_gated` publishes nothing at all;
`/forklift/wheel_standstill` is `true` at 50.012 Hz. Across a 60 s idle the
fused orientation is bit-identical (`z: 0.0005849960834777662`,
`w: 0.9999998288897766` at both ends). That residual is a yaw of 0.067°,
which is the 0.50 s of ungated gyro the gate costs at every stop by design.

### 12.4 The run

Route unchanged — `sim/scenarios/warehouse_mapping_route.py` was not
edited. **178.9 s of simulation time, 9 legs, 107.68 m of ground-truth
path, 916.4° of turning** against m5-08b's 179 s / 107.5 m: the same drive.

### 12.5 The artifacts

| file | superseded md5 (m5-08b) | **committed md5 (m5-08d)** |
|---|---|---|
| `warehouse.pgm` | `8c48cc4e9d1771558eb3c648d9c15df8` | **`a663163036c5890937f9045bcf559e72`** |
| `warehouse.yaml` | `306392c787c18f95d010d2927ee0ad2f` | **`62bfa651dbb7f93d6a873a4edcf433cf`** |
| `warehouse.posegraph` | `a7c8ade4b898fbd9d91cb9270c77ea79` | **`158bc494430a7da4f6ff4b4c7335c477`** |
| `warehouse.data` | `59ae8f84aef684f8575771ebcf296863` | **`01177d41fb0b29d0c39a521f76db420e`** |

New grid 606 × 410 cells at 0.050 m, origin `[-9.145, -4.778, 0]`,
`mode: trinary`, `negate: 0`, thresholds 0.65 / 0.196 — the nav2 defaults,
unchanged. `save_map` returned `result=0` on the first attempt and
`serialize_map` on the first.

`.gitattributes` coverage **verified, not assumed**: `git check-attr text`
returns `unset` for `warehouse.pgm`, `warehouse.posegraph` and
`warehouse.data` (rules `*.pgm -text`, `*.posegraph -text`,
`sim/maps/**/*.data -text`), and `auto` for the two yaml files, which is
correct for text.

### 12.6 Squareness — the headline, and it is not zero

Measured from the committed grid alone by fitting its four perimeter walls
(`sim/maps/warehouse/register_map.py`); no run figure enters it.

| | m5-08b grid | **rebuilt grid** |
|---|---|---|
| rotation from the building | +1.8343° | **−0.4535°** |
| internal shear | 0.4244° | **0.3250°** |
| west / south / north / east | +1.81 / +2.11 / +1.69 / +1.81° | **−0.58 / −0.26 / −0.55 / −0.46°** |

**4.0× squarer, and not square.** The 0.45° that remains is not the idle:
§12.3 measured the idle contribution at 0.067° and showed it frozen, so at
most 15 % of it can be pre-drive. The rest is in-motion heading error that
the pose graph did not fully absorb. The shear barely moved and is
therefore not an idle-drift effect at all — it is a property of the
mapping, and it is what the registration residual mostly is. **No
slam_toolbox parameter was changed to chase either number.**

### 12.7 The registration

`sim/maps/warehouse/warehouse_registration.yaml`, derived from this grid:

```
p_map = R(theta) * p_world + t
theta = -0.007915259 rad = -0.453510947 deg
t     = (+6.029222691, +5.541459743) m
residual rms 0.040363 m, MAX 0.141100 m, over 1444 wall points
```

**0.141 m is the floor under every localisation number measured through
it.** It must be re-derived for every regenerated map, and that is
enforced: the file records the grid's md5 and `load_registration()`
refuses a mismatch.

### 12.8 This run's own error, both ways, on one CSV

The same 4150-sample recording, read by both scoring modes:

| | `--score anchored-drift` | `--score absolute` |
|---|---|---|
| what it measures | drift since the start of the drive | world-frame error through the committed transform |
| `map -> base_link` rms | 0.138 m | **0.077 m** |
| max | 0.290 m | **0.146 m** |
| final | 0.031 m | 0.082 m |
| parked samples | dropped | **kept** |

The absolute figure is **smaller** than the anchored one, which is worth
saying plainly because the reverse was expected. The anchored mode pins the
curve onto one sample at the start of the drive, and yaw noise in that
single sample rotates everything after it; the absolute mode has no such
sample. **The absolute max, 0.146 m, is at the registration floor of
0.141 m** — so this run establishes that SLAM's own `map -> base_link`
tracked truth to within the instrument's resolution, and nothing finer.
That is what a floor is for.

### 12.9 What this rebuild does not establish

Everything in §11 still applies unchanged — no WSL evidence, no
localisation claim, no dwell, one speed, one floor, empty forks, no M4
command path, and one run with a freshly drawn bias sign.

One thing to add. **The gate leaks during a long idle AFTER a drive**,
which is a case m5-07d did not test — its 60 s and 240 s idles were both
from bringup, with the vehicle never having moved. Measured here with
ground-truth position frozen to 0.0000 m for 180 s:

| idle | span | EKF heading moved | rate |
|---|---|---|---|
| **before** the drive | 26.8 s | **+0.01°** | ~0.00 °/min |
| **after** the drive, whole tail | 200.4 s | **+2.02°** | 0.61 °/min |
| **after** the drive, excluding the first settling window | 180.7 s | **+0.72°** | 0.24 °/min |

Against the ungated 7.71 °/min m5-07d measured, the gate is removing
92–97 % of it and not 100 %. The likely mechanism is drive-encoder dither
under a settled suspension re-opening the 0.50 s standstill window, but
nothing here confirms it. **It did not affect this map** — the mapping was
done and the artifacts saved before that idle — but it is exactly the
regime an AMCL dwell test will sit in, and it is raised as an open
question to `agv/` in `docs/reports/m5-08d-remap-and-registration.md`.
