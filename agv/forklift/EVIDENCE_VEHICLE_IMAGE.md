# EVIDENCE_VEHICLE_IMAGE.md

The dated run behind **Phase 1 of ADR 0016**: the vehicle's autonomy stack
started as one *vehicle image*, from one per-vehicle config, inside its own
DDS domain, against a simulator that is a separate side.

**What this file is for.** A boundary that is claimed is worth nothing. Every
section below is a command and its actual output. Section 3 is the one that
matters: it is the boundary *failing to be crossed*.

---

## 0. Environment, and what qualifies every figure

| | |
|---|---|
| Host | the owner's WSL2 machine (`ozkannotebook`), Ubuntu 24.04, ROS 2 **Jazzy**, 20 logical cores, 15 GiB |
| Autonomy stack | **system packages**, installed 2026-08-05 by m5-21. The `~/ros-overlay/prefix` `.deb` overlay is retired and was not on `AMENT_PREFIX_PATH` for any run here |
| Packages, read rather than assumed | `ros-jazzy-nav2-bringup` **1.3.12**, `ros-jazzy-robot-localization` **3.8.3**, `ros-jazzy-fastrtps` **2.14.6**, `ros-jazzy-rmw-fastrtps-cpp` **8.4.4**, `ros-jazzy-fastcdr` **2.2.7** - the set `sim/setup/WSL_ENVIRONMENT.md` §12.5 left in place |
| Rendering | software rasterisation, headless (`gz sim -r -s`), no GUI in any run below |
| Ran alone | **yes.** `pgrep` before the run showed no `gz sim`, no `ros2`, no ROS node of any kind, and `/dev/shm` was cleared of stranded Fast DDS segments (§12.7's fault) between runs |
| Run started | **2026-08-05T06:50:42Z** (sim side), vehicle image 06:51:05Z. Proofs 1-2 at 06:52:38Z, 06:55:01Z; proof 3 at 06:57:26Z; proof 4 at 07:07:18Z; proof 5 from 07:12Z |
| gz partition | `GZ_PARTITION=m524` for the vehicle-image run, `m524b` for the compatibility recipes. `ROS_DOMAIN_ID` does **not** isolate Gazebo; the two transports are isolated separately (LESSONS 2026-07-27) |

**What every figure here is a figure of.** One vehicle, one run, one host.
Nothing in this file is a bound. The latency in §6 in particular is one draw
of a quantity that has already been measured to move by 60x between runs on
this machine (LESSONS 2026-08-04, `WSL_ENVIRONMENT.md` §12.6).

---

## 1. What was started, and from what

Two sides, started separately, and the separation is the deliverable.

**The sim side — Gazebo and the world, and not one ROS process.**

```
$ export GZ_PARTITION=m524
$ gz sim -r -s -v 2 sim/worlds/warehouse.sdf

---- sim side up, gz topics ----
12
---- ROS processes on the sim side (expect none) ----
0
```

Twelve gz-transport topics, all of them `/world/warehouse/...` and `/clock`;
**zero** ROS processes. The sim side joins no DDS domain at all, because gz
transport is not DDS. It is the warehouse floor and nothing else.

**The vehicle image — one command, one config, one domain.**

```
$ export GZ_PARTITION=m524
$ python3 agv/forklift/scripts/vehicle_image.py --vehicle F001

serial                F001
domain id             51   (from allocation.yaml)
per-vehicle config    .../agv/forklift/vehicles/F001.yaml
spawn   world frame   x -4.5000  y +7.0000  z +0.0500  yaw +0.000000
initial map frame     x +1.584770  y +12.576859  yaw -0.007915
ROS_DOMAIN_ID=51  GZ_PARTITION=m524
ros2 launch .../agv/forklift/launch/vehicle_image.launch.py vehicle:=F001
```

**Seventeen processes**, every one of them something a real forklift's own
computer would run:

```
create-1  parameter_bridge-2  wheel_odometry-3  imu_gate-4  ekf_node-5
sensor_tf-6  forklift_io-7  obstacle_zone-8  map_server-9  amcl-10
planner_server-11  controller_server-12  behavior_server-13
velocity_smoother-14  bt_navigator-15  envelope_gate-16
cmd_vel_to_tricycle-17
```

`create-1` is the spawn and exits cleanly once the model is in the world.
`Nav2 active` was reported **~15 s** after the launcher started;
`process has died` count: **0**.

### 1.1 The defect this composition found on its first run, before any proof

**Two launch files that both declare `params_file` cannot simply be included
one after the other.** `IncludeLaunchDescription` on Jazzy does not scope
launch configurations - its `execute()` returns the `SetLaunchConfiguration`
actions and the included description with no push/pop around them - and
`DeclareLaunchArgument` applies its default only when the configuration is
**not already set**. `localization.launch.py` declares `params_file`
(`amcl.yaml`); `navigation.launch.py` declares `params_file` (`nav2.yaml`).
Included in that order, Nav2 got **`amcl.yaml`**.

Nothing failed. Every node started, every lifecycle transition was emitted,
and the log read normally for sixty seconds. What it actually said, for
anyone reading it:

```
[planner_server]: Created global planner plugin GridBased of type nav2_navfn_planner::NavfnPlanner
[global_costmap]: Timed out waiting for transform from base_link to map ...
                  Invalid frame ID "base_link" ... frame does not exist
[global_costmap]: Failed to activate global_costmap because transform from
                  base_link to map did not become available before timeout
```

`NavfnPlanner` is nav2's **default**, not this vehicle's `SmacPlannerHybrid`;
`base_link` is the **default** `robot_base_frame`, not this vehicle's
`forklift/base_link`. A stack running entirely on defaults looks exactly like
a stack running on its parameter file until you read what it says it loaded.

The fix is one `GroupAction(..., scoped=True)` per include
(`launch/vehicle_image.launch.py`, `_scoped`), which pushes and pops the
configuration stack so each included file resolves its own defaults. After it:

```
[planner_server]: Created global planner plugin GridBased of type nav2_smac_planner::SmacPlannerHybrid
[planner_server]: Configured plugin GridBased ... Using motion model: Reeds-Shepp.
```

Recorded here rather than only fixed, because the failure mode - a silently
defaulted parameter file - is the one this repository has paid for twice
already in other tools.

---

## 2. The identity, resolved with no ROS and no simulator

`scripts/vehicle_identity.py` is the single reader of the serial -> domain
mapping. Its `--self-check` builds temporary tables and asserts that each way
of getting the allocation wrong is a **refusal**:

```
$ python3 agv/forklift/scripts/vehicle_identity.py --self-check

refusals:
  refused as intended: a domain outside the vehicle range
  refused as intended: two vehicles allocated one domain
  refused as intended: a vehicle range outside the safe 0-101 range
  refused as intended: the operator domain inside the vehicle range
  refused as intended: a serial with no allocation
  refused as intended: a per-vehicle file carrying its own domain id
  refused as intended: a per-vehicle file whose serial does not match its name
  refused as intended: a per-vehicle file with no spawn pose

the committed tables:
serial                F001
domain id             51   (from allocation.yaml)
...
the environment check:
  ROS_DOMAIN_ID=  None  accepted=False  ok
  ROS_DOMAIN_ID=    ''  accepted=False  ok
  ROS_DOMAIN_ID=  '52'  accepted=False  ok
  ROS_DOMAIN_ID=  '51'  accepted=True  ok

SELF-CHECK PASS
```

and an unallocated serial is refused rather than guessed:

```
$ python3 agv/forklift/scripts/vehicle_image.py --vehicle F009 --dry-run
REFUSED: .../vehicles/allocation.yaml: no domain is allocated to serial
'F009'. Known: F001. A vehicle with no allocation is not started with a
guessed domain - it is allocated one first.
exit=2
```

**Where the numbers live.** `vehicles/allocation.yaml` holds the mapping and
nothing else does; `vehicles/F001.yaml` holds the serial, the spawn pose and
the initial pose and carries **no** domain ID - a file that carried one would
be refused by the check above (invariant 10).

---

## 3. Proof 1 — from a different domain, the vehicle is not there

**This is the deliverable.** The vehicle image is running, fully active, in
domain 51. Three other domains were asked what they can see: **0** (what a
shell that forgot gets), **10** (the operator / monitoring side of
`allocation.yaml`) and **52** (a reserved vehicle domain with no vehicle in
it). Every command used `--no-daemon --spin-time 5`, so no cached daemon view
could produce a convenient answer.

```
==================== ROS_DOMAIN_ID=0  (NOT the vehicle) ====================
$ ROS_DOMAIN_ID=0 ros2 topic list --no-daemon --spin-time 5
/parameter_events
/rosout
-- topics matching "forklift":
0
$ ROS_DOMAIN_ID=0 ros2 node list --no-daemon --spin-time 5
                                                    <- nothing. Not one node.

==================== ROS_DOMAIN_ID=10  (the operator side) =================
$ ROS_DOMAIN_ID=10 ros2 topic list --no-daemon --spin-time 5
/parameter_events
/rosout
-- topics matching "forklift":
0
$ ROS_DOMAIN_ID=10 ros2 node list --no-daemon --spin-time 5

==================== ROS_DOMAIN_ID=52  (a vehicle domain, empty) ===========
$ ROS_DOMAIN_ID=52 ros2 topic list --no-daemon --spin-time 5
/parameter_events
/rosout
-- topics matching "forklift":
0
$ ROS_DOMAIN_ID=52 ros2 node list --no-daemon --spin-time 5
```

`/parameter_events` and `/rosout` are the querying process's **own** two
topics. There is no third one, in any of the three domains.

The same verdict taken against the contract table rather than by eye, so that
"I see nothing" is a pass with a name on it rather than an empty screen:

```
$ ROS_DOMAIN_ID=52 python3 agv/forklift/scripts/check_contract_topics.py \
      --live --expect-absent
...
contract rows present : 0 of 29
contract rows missing : 29
PASS: the boundary holds  (expected NO contract topic in domain 52)
```

**What this proves and what it does not.** It proves the boundary is the
domain's and not a naming convention's: nothing was renamed, nothing was
namespaced, and a process in another domain cannot see, publish into or
subscribe to this vehicle's graph. It does **not** prove anything about the
gz-transport side - `GZ_PARTITION` is that boundary and it is deliberately
shared, because the world is shared (ADR 0016 D4).

---

## 4. Proof 2 — from inside the vehicle's domain, the whole contract appears

The other half. `check_contract_topics.py` parses the ROS contract table out
of `README.md` ("### ROS 2, after `launch/vehicle.launch.py`") and diffs it
against the live graph, so this is a diff and not an eyeballing.

```
$ ROS_DOMAIN_ID=51 python3 agv/forklift/scripts/check_contract_topics.py --live
ROS_DOMAIN_ID=51   live topics: 93

contract rows present : 29 of 29
  + /forklift/cmd/traction_speed        + /forklift/obstacle/in_stop_zone
  + /cmd_vel                            + /forklift/obstacle/min_distance
  + /cmd_vel_smoothed                   + /forklift/scan
  + /cmd_vel_gated                      + /forklift/odom
  + /forklift/envelope/motion_enable    + /forklift/imu
  + /forklift/envelope/speed_ceiling    + /forklift/imu_gated
  + /forklift/envelope/equipment_permit + /forklift/wheel_standstill
  + /forklift/mode/in_force             + /forklift/odom_wheel
  + /forklift/mode/applied              + /forklift/odom_filtered
  + /forklift/vehicle/heartbeat         + /tf
  + /forklift/envelope/gate_state       + /forklift/joint_states
  + /forklift/nav/tricycle_refusals     + /forklift/gz/*_cmd -> fork_cmd,
  + /forklift/cmd/steer_angle                steer_cmd, traction_cmd
  + /forklift/cmd/fork_speed
  + /forklift/fork_height
  + /forklift/linear_speed
  + /forklift/safety_scanner_front/measurement

contract rows missing : 0

on the wire and not in the table (reported, not failed): 62
  ? /amcl_pose  ? /clock  ? /map  ? /particle_cloud  ? /plan  ? /tf_static
  ? /global_costmap/...  ? /local_costmap/...  ? /navigate_to_pose/_action/...
  ...

PASS: every contract row is on the wire
```

The 62 extra names are Nav2's own action, costmap and lifecycle topics. They
are reported and never failed: the table is the vehicle's **contract**, not an
inventory of its graph.

**Twenty-three nodes**, and the seven managed ones all `active`:

```
$ ROS_DOMAIN_ID=51 ros2 node list --no-daemon --spin-time 8   ->  23 nodes
/amcl /behavior_server /bt_navigator /bt_navigator_navigate_to_pose_rclcpp_node
/cmd_vel_to_tricycle /controller_server /envelope_gate /forklift_bridge
/forklift_ekf /forklift_io /global_costmap/global_costmap /imu_gate
/launch_ros_49152 /local_costmap/local_costmap /map_server /obstacle_zone
/planner_server /sensor_tf /velocity_smoother /wheel_odometry
+ three transform_listener_impl_*

/map_server          active [3]      /behavior_server     active [3]
/amcl                active [3]      /velocity_smoother   active [3]
/planner_server      active [3]      /bt_navigator        active [3]
/controller_server   active [3]
```

`/tf` carries **exactly two publishers, on two disjoint edges**, which is what
a bringup plus a localizer is supposed to show:

```
$ ROS_DOMAIN_ID=51 ros2 topic info /tf --verbose --no-daemon --spin-time 8
Publisher count: 2
Subscription count: 6
  Node name: forklift_ekf      (forklift/odom -> forklift/base_link)
  Node name: amcl              (map           -> forklift/odom)
```

and three contract topics measured rather than assumed:

| Topic | measured rate |
|---|---|
| `/forklift/scan` | **10.050 Hz** |
| `/forklift/odom_filtered` | **49.993 Hz** |
| `/cmd_vel_gated` | **19.994 Hz** |

---

## 5. Proof 3 — a Nav2 goal is ACCEPTED

The route is `EVIDENCE_NAV2.md` §5.1's straight aisle traverse, driven from
inside the vehicle image with the envelope supplied by the ROS 2 double
(`--scenario supervise`, permissive throughout: `--drop-at 999 --duration
140`, i.e. the enable never drops).

```
$ ROS_DOMAIN_ID=51 python3 agv/forklift/scripts/nav2_run.py goal \
      --x 1.0 --y 7.0 --yaw 0.0 --settle 25 --timeout 90 \
      --cmd-topic /cmd_vel_gated --csv proof3-run.csv --plan proof3-plan.json

registration  theta -0.007915259 rad  t (+6.029223, +5.541460) m
goal  world (+1.0000, +7.0000) -> map (+7.0846, +12.5333) yaw -0.0079 rad
goal ACCEPTED at t_sim 408.04
```

**ACCEPTED — which is what this proof is for.** A goal reaching the action
server, being planned and being followed proves the whole vehicle image is
wired: bridge, TF, EKF, map server, AMCL, planner, controller, behaviour
tree, smoother, gate, converter and `forklift_io`, all inside one domain.

**It did not complete, and that is reported rather than tuned away:**

```
RESULT           ABORTED
error_code       104
elapsed          72.42 s of simulation time
plans published  56
refusals         3 rotation-in-place commands refused by the converter
final TRUTH      world (-1.2543, +5.8381) yaw -1.3657
ABSOLUTE goal error 2.5362 m (17.97 x floor), heading -78.250 deg
```

and, scored:

```
THE PLAN (first published)   71 points, 5.693 m, 1 cusp, 1.6 % reverse
THE DRIVE                    ground-truth path 9.158 m
  commanded speed            mean +0.085  max +0.600  min -0.443 m/s
  command sign               300 forward / 182 reverse / 236 at rest
TRACKING (upper bound)       rms 0.9001 m, max 1.5110 m
```

**The plan is the committed one** - 5.693 m with one cusp, the same plan
`EVIDENCE_NAV2.md` §5.1 records - so the planner behaved identically and the
difference is in the following. §7 runs the identical goal on the ungated
m5-10 chain as a one-variable comparison; read the two together before
attributing this to the vehicle image, and neither run is a characterisation
of anything.

**No prior committed run drives this route with the gate permissive
throughout.** `EVIDENCE_NAV2.md` §5.1 ran it with `gate:=false`;
`EVIDENCE_ENVELOPE.md` §10 ran it with the gate and **dropped** the enable at
12 s, so its abort (`error_code 105`) is the gate stopping the vehicle on
purpose. This is the first run of the third combination, and its result is an
open question in the m5-24 report, not a finding this brief may act on -
changing any Nav2, AMCL, EKF or smoother value is outside it.

---

## 6. Proof 4 — the m5-11 §7 pass-through observation, re-run

Run **inside the vehicle image**, in domain 51, against the full stack rather
than against `envelope.launch.py`'s measurement stack. The vehicle was where
proof 3 left it rather than at the §7 spawn pose; the observation is a
relation between two topics and does not depend on where the vehicle stands.

```
$ ROS_DOMAIN_ID=51 python3 agv/forklift/scripts/envelope_run.py run \
      --scenario passthrough --csv proof4-passthrough.csv

recorded 700 state rows, 273 gated messages, 280 envelope publications,
         226 smoothed messages

=== scenario passthrough ===
run 700 state rows over 14.02 s of simulated time
  matched pairs                  : n = 220
  |gated - smoothed|             : max 0.000e+00 m/s, mean 0.000e+00 m/s
  exact matches                  : 220 of 220
  gate latency (smoothed -> gated): max 0.0011 s, mean 0.0005 s
  readback: heartbeat moved 271 times over 676 samples, last 19647;
            mode applied ended 2
```

| | committed (m5-11 §7) | installed A-D (`WSL_ENVIRONMENT.md` §12.6) | **this run, in the vehicle image** |
|---|---|---|---|
| matched pairs | 221 | 221 / 224 / 676 / 440 | **220** |
| `max abs(gated_v - smoothed_v)` | **0.000e+00** | **0.000e+00** in all four | **0.000e+00** |
| exact matches | 221 of 221 | all, in all four | **220 of 220** |
| gate latency, mean | 0.0004 s | 0.0004 - 0.0242 s | **0.0005 s** |
| gate latency, max | 0.0010 s | 0.0014 - 0.0713 s | **0.0011 s** |

**The residual reproduces exactly, which is the half that is a property of
the design.** Every matched pair is exact, as it has been in six recorded runs
across two packagings and now inside a per-vehicle domain.

**The latency is the other half and it is one draw.** 0.0005 s mean and
0.0011 s max here happen to sit beside the committed sample; four runs on this
same machine spanned 0.0004-0.0242 s mean and 0.0014-0.0713 s max. A
difference in these figures is not a regression and this agreement is not a
confirmation (LESSONS 2026-08-04).

---

## 7. Proof 5 — both compatibility recipes still run

Neither recipe is touched by this brief and both were run to show it. Both use
the **old shape** - `sim/launch/warehouse_bringup.launch.py`, one ROS graph,
an ambient domain - which still exists exactly as it did.

### 7.1 The m5-10 chain: `gate:=false cmd_topic:=/cmd_vel_smoothed`

```
$ export ROS_DOMAIN_ID=42 GZ_PARTITION=m524b
$ ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
      process has died: 0
$ ros2 launch agv/forklift/launch/localization.launch.py \
      initial_pose_x:=1.584770 initial_pose_y:=12.576859 initial_pose_yaw:=-0.007915
      amcl active: 1
$ ros2 launch agv/forklift/launch/navigation.launch.py \
      gate:=false cmd_topic:=/cmd_vel_smoothed
      Nav2 active after ~15 s
      envelope_gate started? 0            <- gate:=false honoured
      [planner_server]: Created global planner plugin GridBased of type
                        nav2_smac_planner::SmacPlannerHybrid
```

**Runs.** And because it was up, the identical goal was sent through it - the
one-variable comparison for §5:

```
$ python3 agv/forklift/scripts/nav2_run.py goal --x 1.0 --y 7.0 --yaw 0.0 \
      --settle 25 --timeout 90
goal ACCEPTED at t_sim 64.22
TIMEOUT after 90.0 s of simulation time; cancelling
RESULT           CANCELLED/TIMEOUT      plans published 89
refusals         7 rotation-in-place commands refused by the converter
final TRUTH      world (+0.4160, +7.2319) yaw -0.5891
ABSOLUTE goal error 0.6283 m (4.45 x floor), heading -33.751 deg
```

**The ungated chain did not complete this route either, in this session.**
`EVIDENCE_NAV2.md` §5.1 records it **SUCCEEDED in 13.40 s** with 0.183 m
error; today, with the gate removed and everything else the same, it was
still 0.63 m out and turning after 90 s of simulated time, with seven
rotation-in-place refusals. So whatever is different is **not the vehicle
image and not the envelope gate** - both chains under-perform the committed
figure in the same session, on the m5-21 system-package stack that also moved
the §7 latency by up to 60x.

Read against each other, and neither is a characterisation:

| | committed m5-10 case A | today, ungated (§7.1) | today, in the vehicle image (§5) |
|---|---|---|---|
| goal | ACCEPTED | **ACCEPTED** | **ACCEPTED** |
| plan | 5.693 m | 5.693 m | 5.693 m |
| outcome | SUCCEEDED, 13.40 s | TIMEOUT at 90 s | ABORTED 104 at 72 s |
| absolute error | 0.183 m | 0.628 m | 2.536 m |
| rotation-in-place refusals | - | 7 | 3 |

n = 1 each. The gated run is the worse of the two, and one run does not
establish that the gate is why.

### 7.2 The m5-11 envelope chain

```
$ export ROS_DOMAIN_ID=42 GZ_PARTITION=m524c
$ ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
      process has died: 0
$ ros2 launch agv/forklift/launch/envelope.launch.py feedback:=CLOSED_LOOP
      envelope stack active. ...
      process has died: 0
$ python3 agv/forklift/scripts/envelope_run.py run --scenario passthrough

run 699 state rows over 14.02 s of simulated time
  matched pairs                  : n = 220
  |gated - smoothed|             : max 0.000e+00 m/s, mean 0.000e+00 m/s
  exact matches                  : 220 of 220
  gate latency (smoothed -> gated): max 0.0016 s, mean 0.0004 s
```

**Runs, and gives the same residual.** Two independent re-runs of §7 in one
session - one inside the vehicle image (§6) and one on the untouched m5-11
chain - both `0.000e+00`, both every pair exact, with latency means 0.0005 s
and 0.0004 s and maxima 0.0011 s and 0.0016 s.

---

## 8. What this evidence does not establish

1. **It is one vehicle.** Phase 1 proves the wall around a single machine.
   Nothing here shows two vehicles coexisting, and they cannot yet:
   `model.sdf` states its gz topic names literally, so a second spawn would
   share them. That is Phase 2 and it is deliberately not started here.

2. **It says nothing about the gz-transport side.** `GZ_PARTITION` is shared
   on purpose - one world, one floor (ADR 0016 D4). The isolation demonstrated
   in §3 is DDS isolation only, and the two transports are separate boundaries.

3. **No crossing was exercised.** ADR 0016 D3 names four - VDA 5050, the
   bridge's per-vehicle supervision endpoint, the monitoring plane and
   simulated time. Only (d) exists here, as the vehicle's own `/clock` bridge.
   The envelope came from the **ROS 2 double inside the vehicle's own domain**,
   which is not the crossing the bridge will be.

4. **The Nav2 route does not complete today, on either chain** (§5, §7.1), and
   this file does not explain why. It establishes only that the failure is not
   introduced by the vehicle image, because the untouched chain shows it too.
   Changing any Nav2, AMCL, EKF or smoother value was outside this brief.

5. **No timing figure here is a bound.** The gate latency is one draw; the
   ~15 s to `Nav2 active` is one start on an idle machine; the 17 processes
   were not measured for CPU or memory, so ADR 0016's §3 cost figures are
   unchanged by this run.

6. **The sim side is not yet a committed entry point.** It was started by hand
   as `gz sim -r -s sim/worlds/warehouse.sdf`, because `sim/launch/` is not
   this layer's to edit. The report requests the file that should exist.

---

## 9. How to reproduce

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=m524            # the SIMULATOR's boundary. Shared.

# ---- terminal 1: the sim side. Gazebo and the world, no ROS node ----
gz sim -r -s -v 2 sim/worlds/warehouse.sdf

# ---- terminal 2: the vehicle image. It sets ROS_DOMAIN_ID itself ----
python3 agv/forklift/scripts/vehicle_image.py --vehicle F001

# ---- terminal 3: the proofs ----
# the wall, from outside it
ROS_DOMAIN_ID=52 ros2 topic list --no-daemon --spin-time 5
ROS_DOMAIN_ID=52 python3 agv/forklift/scripts/check_contract_topics.py \
    --live --expect-absent
# the contract, from inside it
ROS_DOMAIN_ID=51 python3 agv/forklift/scripts/check_contract_topics.py --live
ROS_DOMAIN_ID=51 ros2 topic info /tf --verbose --no-daemon --spin-time 8

# a goal, with the envelope from the double (no PLC at M5)
export ROS_DOMAIN_ID=51
python3 agv/forklift/scripts/envelope_run.py run --scenario supervise \
    --ceiling 0.60 --drop-at 999 --duration 140 --csv /tmp/envelope.csv &
python3 agv/forklift/scripts/nav2_run.py goal --x 1.0 --y 7.0 --yaw 0.0 \
    --settle 25 --timeout 90 --cmd-topic /cmd_vel_gated \
    --csv /tmp/run.csv --plan /tmp/plan.json
python3 agv/forklift/scripts/nav2_run.py analyse --csv /tmp/run.csv \
    --plan /tmp/plan.json

# the pass-through observation
python3 agv/forklift/scripts/envelope_run.py run --scenario passthrough \
    --csv /tmp/passthrough.csv

# identity, with no ROS and no simulator
python3 agv/forklift/scripts/vehicle_identity.py --self-check
python3 agv/forklift/scripts/check_contract_topics.py --print
```

**Between runs, verify the machine is clear.** Killing a launch is not killing
its nodes, and a Fast DDS version change strands `/dev/shm`
(`WSL_ENVIRONMENT.md` §12.7). Every run above was preceded by a `pgrep` that
returned nothing and by clearing stranded `fastrtps_*` segments.

**The domain is not a shell memory.** Every hand-run tool has to pick one, and
the number lives in `vehicles/allocation.yaml`. A session that forgets sees
exactly what §3 shows - an empty graph - which is why §3 is a proof and also a
warning.
