# EVIDENCE — Nav2 for the tricycle forklift, measured

**Brief m5-10.** The forklift plans and follows paths in the committed
warehouse grid with a configuration written for a vehicle that **steers and
cannot rotate in place**. Every figure below is a **measurement**: the
parameter traps were probed on running nodes, the Twist → tricycle
conversion was checked against a **commanded motion in the simulator**, and
the four navigation cases were driven to completion.

| Item | Value |
|---|---|
| Date | **2026-08-04** |
| Under test | `agv/forklift/nav2.yaml`, `launch/navigation.launch.py`, `behavior_trees/navigate_to_pose_tricycle.xml`, `scripts/cmd_vel_to_tricycle.py` |
| nav2 | **1.3.12** (`nav2_smac_planner`, `nav2_regulated_pure_pursuit_controller`, `nav2_velocity_smoother`, `nav2_controller`, `nav2_planner`, `nav2_bt_navigator`, `nav2_behaviors` — all 1.3.12), ROS 2 Jazzy |
| Simulator | `gz sim` 8.11.0, headless, software rasterised |
| Map | `sim/maps/warehouse/warehouse.pgm` md5 `a663163036c5890937f9045bcf559e72`, **frozen and read only** |
| Registration | `sim/maps/warehouse/warehouse_registration.yaml`, θ = −0.453511°, t = (+6.029223, +5.541460) m |
| **FLOOR** | **registration residual rms 0.0404 m, MAX 0.1411 m** |
| Reference | `/forklift/odom` — the simulator's own pose of the model, **exact**, consumed by the measurement harness only |
| Harness | `agv/forklift/scripts/nav2_run.py` |
| Host | project session container, Ubuntu 24.04, kernel 6.18.5, 4 cores, headless |

**ADR 0014 D1 holds by construction.** Nothing started by
`navigation.launch.py` is an OPC UA client, nothing reads or writes a PLC
node, and no motion value leaves the vehicle's own ROS graph. The envelope
gate is m5-11's and is absent here; its insertion point is the `cmd_topic`
launch argument and nothing else in this stack anticipates it.

---

## 0. What was inherited, and what was re-decided

The configuration under test was **authored but never run** (commit
`307dd10`, honestly labelled `wip`). This brief owns the result, not the
draft's choices. Every claim the draft made in the future tense — "verified,
not trusted" — is settled below by a measurement, and where the draft's
number was wrong it is corrected in the file and the correction is recorded
here.

**Nothing was migrated.** The retired RB-KAIROS platform (ADR 0010 D1) was
omnidirectional and its configuration was deleted with the vehicle.

---

## 1. The five Jazzy traps, each probed on a running node

Probed **before the simulator was started at all**, on `ROS_DOMAIN_ID=71`
with no `GZ_PARTITION`, so that none of these results depends on the stack
under test.

### (a) `allow_reverse_expansion` is not a `SmacPlannerHybrid` parameter

A probe params file set it **deliberately** to `true` under a
`nav2_smac_planner::SmacPlannerHybrid` plugin. The planner configured
successfully and:

```
$ ros2 param get /planner_server GridBased.allow_reverse_expansion
Parameter not set
[WARN] [rclcpp]: Failed to get parameters: GridBased.allow_reverse_expansion

$ ros2 param get /planner_server GridBased.motion_model_for_search
String value is: REEDS_SHEPP
```

The declared parameter list for `GridBased` contains
`allow_unknown, change_penalty, cost_penalty, minimum_turning_radius,
motion_model_for_search, non_straight_penalty, retrospective_penalty,
reverse_penalty, use_quadratic_cost_penalty` — **and no
`allow_reverse_expansion`**. The value in the params file was accepted by
the YAML parser and then ignored by the plugin, with one WARN that only
appears because the probe asked for it. `allow_reverse_expansion` is
declared by `SmacPlannerLattice` only.

**Reverse comes from the motion model**, and the planner says so at
configure:

```
[INFO] [planner_server]: Configured plugin GridBased of type SmacPlannerHybrid
       with maximum iterations 1000000, max on approach iterations 1000,
       and not allowing unknown traversal. Tolerance 0.25.
       Using motion model: Reeds-Shepp.
```

That line also confirms the **`SmacPlannerHybrid` default `tolerance` is
0.25 m** — the number `nav2.yaml` tightens to 0.10 and states as the
default.

**Plugin naming, from the shipped descriptor** — the colon form is the only
one that exists:

```
/opt/ros/jazzy/share/nav2_smac_planner/smac_plugin_hybrid.xml
  <class type="nav2_smac_planner::SmacPlannerHybrid" .../>
```

**Why not `SmacPlannerLattice`**, checked rather than argued: this
installation ships exactly two control sets,
`share/nav2_smac_planner/sample_primitives/5cm_resolution/{0.5m,1m}_turning_radius`.
Neither is generated for this vehicle's 1.05 m planned radius or its
footprint, and generating one is a tool and a dependency this brief may not
add.

### (b) RPP's rejected parameter pair is accepted silently at configure

`use_rotate_to_heading: true` **together with** `allow_reversing: true` is
documented as a rejected combination. A probe set both:

```
$ ros2 lifecycle set /controller_server configure
Transitioning successful
$ ros2 param get /controller_server FollowPath.use_rotate_to_heading
Boolean value is: True
$ ros2 param get /controller_server FollowPath.allow_reversing
Boolean value is: True
```

**Nothing in the log.** `grep -Ei 'reject|warn|error|rotate|revers'` over
the whole controller log returned **no lines**. The guard exists only in the
dynamic-parameter callback; a params file setting both is loaded, and the
controller then commands in-place rotations this vehicle cannot perform.

> `use_rotate_to_heading: false` in `nav2.yaml` is therefore **not a
> preference and not a defensive setting — it is the only thing standing
> between this vehicle and a command it cannot execute, and nothing in the
> stack will tell you if it is wrong.**

### (c) The default behaviour tree's recoveries assume a differential base

`/opt/ros/jazzy/share/nav2_bt_navigator/behavior_trees/navigate_to_pose_w_replanning_and_recovery.xml`:

```
42:  <Spin spin_dist="1.57" error_code_id="{spin_error_code}"/>
43:  <Wait wait_duration="5.0"/>
44:  <BackUp backup_dist="0.30" backup_speed="0.15" error_code_id="{backup_code_id}"/>
```

and the stock behaviour server plugin list
(`nav2_bringup/params/nav2_params.yaml`) is
`["spin", "backup", "drive_on_heading", "assisted_teleop", "wait"]`.
`Spin` commands `angular.z` with `linear.x = 0`, which has **no**
`(δ, v_D)` solution on this vehicle. `behavior_trees/navigate_to_pose_tricycle.xml`
carries `wait` and the two costmap clears and nothing that moves; §7 measures
what that costs and what it buys.

### (d) `enable_stamped_cmd_vel` defaults **false** on Jazzy

Read off the live nodes with nothing set:

```
$ ros2 param get /controller_server enable_stamped_cmd_vel
Boolean value is: False
$ ros2 topic list -t
/cmd_vel [geometry_msgs/msg/Twist]
/cmd_vel_smoothed [geometry_msgs/msg/Twist]
```

So the chain carries `geometry_msgs/Twist`, not `TwistStamped`. `nav2.yaml`
pins it on all three publishers rather than inheriting it, because a
subscriber of the wrong type receives nothing and logs nothing about it.

### (e) The velocity smoother's defaults are open-loop and unscaled

Read off a `velocity_smoother` started with **no parameters at all**:

| parameter | measured default | set here | why |
|---|---|---|---|
| `feedback` | **`OPEN_LOOP`** | `CLOSED_LOOP` | ADR 0014 seam (b). Open loop ramps against the smoother's own last command, so a vehicle that is not following gets a step when it re-engages. |
| `scale_velocities` | **`false`** | `true` | False limits vx and wz independently, which corrupts the ratio wz/vx — and that ratio **is** the commanded steer angle (§2). |
| `enable_stamped_cmd_vel` | **`false`** | `false`, pinned | (d). |
| `odom_topic` | **`odom`** | `/forklift/odom_filtered` | The default would silently subscribe to a topic that does not exist on this vehicle; `/forklift/odom` is ground truth despite its name. |
| `max_velocity` | `[0.5, 0.0, 2.5]` | `[0.60, 0.0, 0.5714]` | wz is derived: v_max / R_min = 0.60 / 1.05. The default 2.5 rad/s would let the smoother emit a twist whose implied steer angle is far beyond the mechanical stop. |

---
