# EVIDENCE — Nav2 for the tricycle forklift, measured

**Brief m5-10.** The forklift plans and follows paths in the committed
warehouse grid with a configuration written for a vehicle that **steers and
cannot rotate in place**. Every figure below is a **measurement**: the
parameter traps were probed on running nodes, the Twist → tricycle
conversion was checked against a **commanded motion in the simulator**, and
the four navigation cases were driven.

| Item | Value |
|---|---|
| Date | **2026-08-04** |
| Under test | `agv/forklift/nav2.yaml`, `launch/navigation.launch.py`, `behavior_trees/navigate_to_pose_tricycle.xml`, `scripts/cmd_vel_to_tricycle.py` |
| nav2 | **1.3.12** (`nav2_planner`, `nav2_controller`, `nav2_bt_navigator`, `nav2_behaviors`, `nav2_velocity_smoother`, `nav2_smac_planner`, `nav2_regulated_pure_pursuit_controller`, `nav2_costmap_2d` — all 1.3.12), ROS 2 Jazzy |
| Simulator | `gz sim` 8.11.0, headless, software rasterised |
| Map | `sim/maps/warehouse/warehouse.pgm` md5 `a663163036c5890937f9045bcf559e72`, **frozen and read only** |
| Registration | `sim/maps/warehouse/warehouse_registration.yaml`, θ = −0.453511°, t = (+6.029223, +5.541460) m |
| **FLOOR** | **registration residual rms 0.0404 m, MAX 0.1411 m** |
| Reference | `/forklift/odom` — the simulator's own pose of the model, **exact**, consumed by the measurement harness only |
| Harness | `agv/forklift/scripts/nav2_run.py`, `agv/forklift/scripts/footprint_from_model.py` |
| Host | project session container, Ubuntu 24.04, kernel 6.18.5, 4 cores, headless |

**The environment qualifies every figure.** These runs are container runs.
`EVIDENCE_LOCALIZATION.md`'s figures, which this file is dimensioned
against, were taken in the same container. Nothing here has been reproduced
on the owner's WSL machine, and the M5 showcase runs there
(`docs/LESSONS.md` 2026-07-27).

**ADR 0014 D1 holds by construction.** Nothing started by
`navigation.launch.py` is an OPC UA client, nothing reads or writes a PLC
node, and no motion value leaves the vehicle's own ROS graph. The envelope
gate is m5-11's and is absent here; its insertion point is the `cmd_topic`
launch argument and nothing else in this stack anticipates it.

---

## 0. What was inherited, and what was re-decided

The configuration under test was **authored but never run** (commit
`307dd10`, honestly labelled `wip`), and a harness plus one recording landed
at `73e1e62`. This brief owns the result, not the draft's choices.

**What survived review unchanged, because it was checked and found right:**
the planner and controller choices (§1, §5), the footprint polygon — which
was re-derived from `model.sdf` and came out **identical**, vertex for
vertex (§2) — and the conversion algebra (§3).

**What was corrected:**

| Was | Is | Why |
|---|---|---|
| §1's planner probe quoted a configure line that no captured log contained, re-wrapped over three lines | every quotation below is a verbatim line from a committed probe capture in `evidence/m5-10-probe-*.txt` | `docs/LESSONS.md` 2026-07-27: quote a tool as it prints, never as it was remembered |
| §1(b) claimed `grep -Ei 'reject\|warn\|error\|rotate\|revers'` returned **no lines** | that pattern returns **121** lines on a bare probe, all of them `tf error` from having no transform tree; the claim under test needs the narrower pattern, which returns none | a grep whose pattern matches unrelated noise cannot prove an absence |
| the conversion check drove eight segments that walked the vehicle 7 m across the apron | every segment is now **retraced** by the one after it | the inherited recording's two tightest arcs measured 0.09 and 0.00 m/s against a commanded 0.30: the vehicle had driven into a rack face and the contact was reported as an arc (§3.3) |
| `nav2_run analyse` reported "2 cusps, 0.7 % reverse" for a plan down a straight aisle | a direction change counts only after it persists 0.25 m | those cusps were single path points where a 3 mm step disagreed with a smoothed heading. A tricycle's cusp is a real event; the metric now counts real ones |
| the harness had no way to ask the planner alone | `nav2_run.py plan` drives `ComputePathToPose` against a bare planner and map server | a plan costs 0.02 s to measure this way and 90 s with a simulator, which is the difference between stating what a parameter changed and guessing |

**Nothing was migrated.** The retired RB-KAIROS platform (ADR 0010 D1) was
omnidirectional and its configuration was deleted with the vehicle.

---

## 1. The five Jazzy traps, each probed on a running node

Probed **with no simulator running at all**, on `ROS_DOMAIN_ID=71` with no
`GZ_PARTITION`, so that none of these results depends on the stack under
test. Captures: `evidence/m5-10-probe-a-planner.txt`,
`evidence/m5-10-probe-b-controller.txt`,
`evidence/m5-10-probe-c-smoother.txt`,
`evidence/m5-10-probe-d-versions-bt.txt`.

### (a) `allow_reverse_expansion` is not a `SmacPlannerHybrid` parameter

A probe params file set it **deliberately** to `true` under a
`nav2_smac_planner::SmacPlannerHybrid` plugin, alongside
`allow_unknown: false`. The planner configured successfully and:

```
### ros2 param get /planner_server GridBased.allow_reverse_expansion
Parameter not set

### ros2 param get /planner_server GridBased.motion_model_for_search
String value is: REEDS_SHEPP
```

`ros2 param list /planner_server` declares **34** `GridBased.*` parameters
(the full list is in the capture) and `allow_reverse_expansion` is **not one
of them**. The value in the params file was accepted by the YAML parser and
then ignored by the plugin. `allow_reverse_expansion` is declared by
`SmacPlannerLattice` only.

**Reverse comes from the motion model**, and the planner says so at
configure — one line, verbatim:

```
[INFO] [1785832526.945157287] [planner_server]: Configured plugin GridBased of type SmacPlannerHybrid with maximum iterations 1000000, max on approach iterations 1000, and not allowing unknown traversal. Tolerance 0.25.Using motion model: Reeds-Shepp.
```

That line also confirms the **`SmacPlannerHybrid` default `tolerance` is
0.25 m** — the number `nav2.yaml` tightens to 0.10 and states as the
default.

**Plugin naming, from the shipped descriptor** — the colon form is the only
one that exists:

```
/opt/ros/jazzy/share/nav2_smac_planner/smac_plugin_hybrid.xml:2:	<class type="nav2_smac_planner::SmacPlannerHybrid" base_class_type="nav2_core::GlobalPlanner">
```

**Why not `SmacPlannerLattice`**, checked rather than argued: this
installation ships exactly two control sets,
`sample_primitives/5cm_resolution/{0.5m,1m}_turning_radius`. Neither is
generated for this vehicle's 1.05 m planned radius or its footprint, and
generating one is a tool and a dependency this brief may not add.

### (b) RPP's rejected parameter pair is accepted silently at configure

`use_rotate_to_heading: true` **together with** `allow_reversing: true` is
documented as a rejected combination. A probe set both:

```
### ros2 lifecycle set /controller_server configure
Transitioning successful

### ros2 param get /controller_server FollowPath.use_rotate_to_heading
Boolean value is: True
### ros2 param get /controller_server FollowPath.allow_reversing
Boolean value is: True
```

and over the whole 154-line controller log:

```
$ grep -Ein 'reject|rotate|revers' b_node.log
(no output, exit 1)
```

The guard exists only in the dynamic-parameter callback; a params file
setting both is loaded, and the controller then commands in-place rotations
this vehicle cannot perform.

> `use_rotate_to_heading: false` in `nav2.yaml` is therefore **not a
> preference and not a defensive setting — it is the only thing standing
> between this vehicle and a command it cannot execute, and nothing in the
> stack will tell you if it is wrong.**

### (c) The default behaviour tree's recoveries assume a differential base

`/opt/ros/jazzy/share/nav2_bt_navigator/behavior_trees/navigate_to_pose_w_replanning_and_recovery.xml`:

```
42:            <Spin spin_dist="1.57" error_code_id="{spin_error_code}"/>
43:            <Wait wait_duration="5.0"/>
44:            <BackUp backup_dist="0.30" backup_speed="0.15" error_code_id="{backup_code_id}"/>
```

and the stock behaviour-server plugin list
(`nav2_bringup/params/nav2_params.yaml:305`) is
`["spin", "backup", "drive_on_heading", "assisted_teleop", "wait"]`.
`Spin` commands `angular.z` with `linear.x = 0`, which has **no**
`(δ, v_D)` solution on this vehicle. `behavior_trees/navigate_to_pose_tricycle.xml`
carries the two costmap clears and `Wait`, and nothing that moves; §5 shows
what that costs and what it buys.

### (d) `enable_stamped_cmd_vel` defaults **false** on Jazzy

Read off live nodes with nothing set:

```
### ros2 param get /controller_server enable_stamped_cmd_vel
Boolean value is: False

### ros2 topic list -t | grep -E 'cmd_vel|odom'
/cmd_vel [geometry_msgs/msg/Twist]
/cmd_vel_smoothed [geometry_msgs/msg/Twist]
/odom [nav_msgs/msg/Odometry]
```

So the chain carries `geometry_msgs/Twist`, not `TwistStamped`. `nav2.yaml`
pins it on all three publishers rather than inheriting it, because a
subscriber of the wrong type receives nothing and logs nothing about it.

### (e) The velocity smoother's defaults are open-loop and unscaled

Read off a `velocity_smoother` started with **no parameters at all**:

| parameter | measured default | set here | why |
|---|---|---|---|
| `feedback` | **`OPEN_LOOP`** | `CLOSED_LOOP` | ADR 0014 seam (b). Open loop ramps against the smoother's own last command, so a vehicle that is not following gets a step when it re-engages. |
| `scale_velocities` | **`false`** | `true` | False limits vx and wz independently, which corrupts the ratio wz/vx — and that ratio **is** the commanded steer angle (§3). |
| `enable_stamped_cmd_vel` | **`false`** | `false`, pinned | (d). |
| `odom_topic` | **`odom`** | `/forklift/odom_filtered` | The default would silently subscribe to a topic that does not exist on this vehicle; `/forklift/odom` is ground truth despite its name. |
| `max_velocity` | **`[0.5, 0.0, 2.5]`** | `[0.60, 0.0, 0.5714]` | wz is derived: v_max / R_min = 0.60 / 1.05. The default 2.5 rad/s would let the smoother emit a twist whose implied steer angle is far beyond the mechanical stop. |
| `max_accel` | **`[2.5, 0.0, 3.2]`** | `[0.50, 0.0, 0.4762]` | 2.5 m/s² on a 900 kg counterbalance truck is not a ramp, it is a step. 0.50 m/s² gives a 0.36 m stop distance from 0.60 m/s, inside RPP's 0.60 m collision look-ahead. |

---

## 2. The footprint is a polygon, and it is derived

`agv/forklift/scripts/footprint_from_model.py` reads `model.sdf`, places
every `<collision>` and `<visual>` primitive by its link pose composed with
its own pose, projects it onto the floor and takes the convex hull. Full
output: `evidence/m5-10-footprint-derivation.txt`.

```
THE HULL, 8 vertices, counter-clockwise, base_link frame
  [ -1.875,  -0.340]   fork_right / collision
  [ -0.700,  -0.549]   safety_scanner_rear_link / housing
  [ +0.700,  -0.450]   base_link / chassis_collision
  [ +0.860,  -0.400]   base_link / counterweight_collision
  [ +0.860,  +0.400]   base_link / counterweight_collision
  [ +0.700,  +0.549]   safety_scanner_front_link / housing
  [ -0.700,  +0.450]   base_link / chassis_collision
  [ -1.875,  +0.340]   fork_left / collision

CHECK against nav2.yaml: IDENTICAL
```

| quantity | value | what it means |
|---|---|---|
| length | **2.735 m** | 0.860 counterweight to −1.875 fork tips |
| width | **1.098 m** | the two safety-scanner housings, on opposite corners |
| circumscribed radius | **1.906 m** | **a `robot_radius` model would refuse every aisle in this building** — half a 3.80 m aisle is 1.90 m |
| padded (0.27 m) | 3.275 × 1.638 m | nav2 pads per coordinate outward, not by offsetting the polygon |
| swept circle on the tightest planned arc | **4.739 m across, padded** | the vehicle **cannot turn round in an aisle**, which is correct for a forklift and is what makes §5's reverse case a real manoeuvre rather than a contrived one |

**One correction was needed to get there, and it is worth recording**: a
first version of the derivation projected each cylinder as a square of side
`max(length, 2r)`, which ignores that every wheel in this model is rolled
90°. That put the rear wheel's *diameter* across the vehicle instead of its
0.10 m width and invented a ninth hull vertex at `[-0.620, +0.480]`. With
roll and pitch read properly the hull matches `nav2.yaml` exactly. **A
conservative approximation is not free: it changes the answer.**

### 2.1 What the padded polygon leaves in this building — the lateral budget

`footprint_from_model.py --aisle` scans the committed grid along a line and
reports the free interval and what is left over after the padded polygon:

```
WORST on this line: x = -6.25, free +6.55 .. +8.90 (2.35 m), leaving +0.356 m each side of the padded polygon.
```

Aisle A is nominally 3.80 m, leaving 1.081 m each side — comfortable. But
the building's columns stand proud of the rack faces, and at **x ≈ −6.25**
and **x ≈ +3.90** the free width falls to **2.35 m**, leaving **0.356 m**.
That 0.356 m is the **entire** budget shared by the plan's own detours and
the controller's tracking error, and the measured 0.263 m localization worst
case is already spent inside the padding.

**This number decided the routes measured in §5**, and it is the reason the
first straight-traverse attempt failed (§5.0). It is a property of the
building, not of the configuration.

---

## 3. The Twist → tricycle conversion

### 3.1 The formula, from the vehicle's own geometry

From `model.sdf`: one steered driven wheel **leading** at x = +0.55, two
passive wheels **trailing** on an axle at x = −0.50, drive wheel radius
0.12 m, steer stop ±1.31 rad.

```
    L = wheelbase = 0.55 − (−0.50) = 1.05 m
    d = base_link ahead of the rear axle = 0.50 m
```

The rear axle midpoint R is the only point of a tricycle whose velocity is
purely longitudinal. base_link B stands d forward of it along +x, so for a
rigid body `v_B = v_R + ω × (B − R) = (v_R, 0) + (0, dω)`: **the x
components are identical** and only a lateral term appears. Therefore
`linear.x` at base_link *is* the rear axle's longitudinal speed, and the
0.50 m offset **drops out of the conversion entirely**. (It does not drop
out of odometry, which is why `wheel_odometry.py` places base_link on the
rear axle pose.)

The bicycle relation, with the instantaneous centre on the rear axle line:

```
    (1)   w   = v · tan(δ) / L
    (2)   v_D = v / cos(δ)                    v_D is DRIVE-WHEEL TREAD speed

  solved for the two actuators:

    (3)   δ   = atan2( L·w·sign(v), |v| )     never divides by v; correct in
                                              reverse without a second case
    (4)   v_D = v / cos(δ)
```

`/forklift/cmd/traction_speed` carries **v_D and not v**, and that is a
contract this node did not invent: `forklift_io.py` publishes
`speed / wheel_radius` onto the gz joint command, so the number it is given
*is* the wheel's tread speed. Feeding it `v` would under-drive every turn by
cos δ — 3.6 % at 15°, 29 % at the tightest arc the planner may emit.

### 3.2 Checked by round trip against an independently written forward model

`cmd_vel_to_tricycle.py --self-check` runs (3)–(4) forward and
`v = v_D cos δ`, `w = v_D sin δ / L` back:

```
case                                           v[m/s]  w[rad/s] | delta[deg]  vD[m/s] |   v'[m/s] w'[rad/s] | limit
-------------------------------------------------------------------------------------------------------------------
straight ahead                                  0.600    0.0000 |     0.000    0.600 |    0.6000    0.0000 | none
straight astern                                -0.600    0.0000 |    -0.000   -0.600 |   -0.6000    0.0000 | none
R = 1.05 m left, the planner's tightest arc     0.600    0.5714 |    45.000    0.849 |    0.6000    0.5714 | none
R = 1.05 m left, IN REVERSE                    -0.600   -0.5714 |    45.000   -0.849 |   -0.6000   -0.5714 | none
R = 2.10 m left                                 0.600    0.2857 |    26.565    0.671 |    0.6000    0.2857 | none
BEYOND the steer stop, R = 0.20 m               0.600    3.0000 |    75.057    1.500 |    0.3868    1.3803 | STEER CLAMPED, drive clamped
creep, R = 1.05 m                               0.050    0.0476 |    45.000    0.071 |    0.0500    0.0476 | none
fast + tight: drive speed above the traction limit    1.400    1.3333 |    45.000    1.500 |    1.0607    1.0102 | drive clamped

largest round-trip residual over the UNLIMITED cases: 1.110e-16
VERDICT: round trip exact to 1.1e-16
```

**That proves the algebra is self-consistent and nothing else.** If the
wheelbase were wrong, or the traction topic carried body speed instead of
tread speed, or a sign were inverted, the round trip would still close
exactly. Which is why §3.3 exists.

### 3.3 Checked against a COMMANDED MOTION in the simulator

`nav2_run.py convcheck` publishes a timed sequence of known twists onto the
converter's own input topic — with the bringup and the converter running and
**no planner, controller or localizer** — and measures what the vehicle then
did, from the simulator's own pose of the model. Wheelbase, wheel radius,
the tread-speed convention and both signs are all inside that measurement.
Verbatim: `evidence/m5-10-convcheck.txt`; recording:
`evidence/m5-10-convcheck.csv` (3411 samples at 50 Hz of simulation time,
64 s of simulation).

```
segment                                                      v_cmd    w_cmd |   v_meas    w_meas | delta_pub delta_meas |    R_cmd   R_meas speed
-------------------------------------------------------------------------------------------------------------------------------------------------
straight ahead                                               0.300   0.0000 |   0.3000   -0.0001 |     0.000    -0.027 |      inf -2269.265   100%
straight astern - retraces the row above                    -0.300   0.0000 |  -0.3000   -0.0014 |     0.000    +0.277 |      inf +217.438   100%
left,  R = 2.10 m  (delta +26.57 deg)                        0.300   0.1429 |   0.3107    0.1297 |    26.565   +23.674 |   +2.100   +2.395   104%
astern on the same lock, R = 2.10 m - retrace               -0.300  -0.1429 |  -0.3021   -0.1549 |    26.565   +28.296 |   +2.100   +1.950   101%
left,  R = 1.05 m  (delta +45.0 deg, the tightest planned arc)   0.300   0.2857 |   0.3425    0.2652 |    45.000   +39.112 |   +1.050   +1.291   114%
astern on the same lock, R = 1.05 m - retrace               -0.300  -0.2857 |  -0.3228   -0.2922 |    45.000   +43.548 |   +1.050   +1.105   108%
right, R = 1.05 m  (delta -45.0 deg)                         0.300  -0.2857 |   0.3309   -0.2848 |   -45.000   -42.105 |   -1.050   -1.162   110%
astern on the same lock, R = 1.05 m - retrace               -0.300   0.2857 |  -0.3204    0.2951 |   -45.000   -44.049 |   -1.050   -1.085   107%
ROTATION IN PLACE - must be REFUSED                          0.000   0.5000 |   0.0000    0.0000 |   -45.000        -- |       --       --     --

THE REFUSAL SEGMENT, read on its own terms:
  commanded            v = +0.000 m/s, w = +0.5000 rad/s
  refusals counted     7435 over 5.50 s
  traction published   +0.0000 m/s
  the vehicle moved    0.0000 m and turned +0.0000 deg
WORST RELATIVE RADIUS ERROR over the arcs: 23.00% (left,  R = 1.05 m  (delta +45.0 deg, the tightest planned arc))
```

**What this establishes.**

1. **Straight, both ways, is exact.** 0.3000 m/s commanded, 0.3000 m/s
   achieved, yaw rate −0.0001 and −0.0013 rad/s over 5.5 s. The sign
   convention, the wheel radius and the tread-speed contract are all right,
   in both directions.
2. **Every arc is driven the right way round and reversed on the same
   lock.** `delta_pub` matches (3) exactly (±26.565°, ±45.000°), and the
   retrace rows show the converter turning a negated twist into the *same*
   steer angle with a negated wheel speed — which is what a Reeds-Shepp
   reverse segment needs.
3. **The vehicle UNDERSTEERS, by up to 23 % of radius at the tightest
   planned arc.** Commanded R = 1.050 m, achieved R = 1.291 m; commanded
   45.0° of steer, the arc actually driven corresponds to 39.1°. The gentler
   arc is closer: R 2.100 → 2.395 m, 14 %. **That figure contains tyre slip
   as well as the conversion and is an upper bound on the conversion's own
   error**, never quoted as the conversion's error. The consequence for
   `nav2.yaml` is stated rather than absorbed: the planner's tightest arc
   costs the controller more steer than the kinematic 45°, so the reserve to
   the 75.06° stop is nearer 24° than the 30° the file's derivation claims.
4. **Rotation in place is refused, and the vehicle does not move.** v = 0,
   w = 0.5 rad/s commanded for 5.5 s: traction published +0.0000 m/s, the
   steer axis **held** at the −45.0° it was left on, and the vehicle moved
   **0.0000 m** and turned **+0.0000°**. The refusal count of 7435 is a
   count of *messages*, not of events — the harness republishes as fast as
   it spins — and is quoted only as "nonzero".
5. **Every segment achieved 100–114 % of its commanded speed**, which is the
   check that no row is a contact. The inherited recording failed exactly
   this test at 30 % and 0 % on its two tightest arcs, and that is why the
   sequence now retraces (§0).

---

## 4. The parameter set from the localization measurement

`EVIDENCE_LOCALIZATION.md` measured the vehicle's **absolute** localization
error against the committed registration: steady-state **rms 0.124 m, max
0.263 m**, against an instrument floor of 0.141 m.

**The parameter set from it is `footprint_padding: 0.27`, in both
costmaps.** It is the measured max, 0.263 m, rounded up to the centimetre.

Reason: a costmap places the footprint at the pose the vehicle **believes**;
the vehicle is really somewhere within 0.263 m of it. Growing the collision
polygon by that much is what makes "the planner says this path is clear" a
statement about where the vehicle actually **is**. It is deliberately not
put into `inflation_radius`, because inflation and padding are not
interchangeable here: §2.1 shows the padding costs 0.27 m of a 1.081 m
half-aisle, and 0.27 m of a 0.356 m half-pinch.

Two further parameters are dimensioned from the same measurement, and are
named as consequences rather than as independent choices:

- `xy_goal_tolerance: 0.25` — twice the measured rms and just inside the
  measured max. A tolerance tighter than the localizer's own rms asks the
  vehicle to satisfy a criterion it cannot measure.
- `yaw_goal_tolerance: 0.15` rad (8.6°) — 1.9 × the 4.52° heading max of the
  same run. It has to be reachable **without rotating in place**, because
  this vehicle cannot: the final heading is whatever the Reeds-Shepp path's
  last segment delivers.

**No docking claim is made anywhere.** ADR 0014 G6 quotes an industrial
docking figure of ±1 cm; this vehicle's belief about its own position
carries a measured 0.263 m worst case, 26 times that. Docking needs a local
sensor closing on the station itself, not a map pose. That is M6's problem
and nothing here is progress towards it.

---

## 5. The four cases, measured

Every run: headless, isolated on **both** transports (unique `GZ_PARTITION`
**and** `ROS_DOMAIN_ID`), `use_sim_time` everywhere, **serialised — never two
simulators at once**, driven to completion in the foreground with bounded
polling, every process confirmed gone with `pgrep -af` afterwards. Each run
is bringup → localization (AMCL prior from the spawn pose, exact) →
`navigation.launch.py` → one goal.

Artefacts per case in `evidence/`: `m5-10-<case>-goal.txt` (the harness
verbatim), `-analyse.txt` (the scoring), `-run.csv` (the 10 Hz recording),
`-plan.json` (the plan and the result), `-stack.txt` (the servers' own log,
filtered).

| case | route (world) | result | goal error, absolute | tracking rms / max | plan |
|---|---|---|---|---|---|
| **A** straight aisle traverse | (−4.5, +7.0) → (+1.0, +7.0), 5.5 m forward | **SUCCEEDED** in 13.40 s | **0.183 m** (1.29 × floor), heading −3.0° | 0.119 / 0.190 m | 5.693 m |
| **B** reverse segment | (+1.0, +7.0) → (−1.0, +7.0), 2 m astern | **SUCCEEDED** in 4.37 s | **0.312 m** (2.21 × floor), heading −1.2° | **0.0009 / 0.0027 m** | 2.000 m, **100 % reverse** |
| **B′** the same, 6 m astern | (+1.0, +7.0) → (−5.0, +7.0) | **ABORTED** `error_code 104` after 2.39 m of the 6 m | 3.677 m away, heading out by **50°** | 0.062 / 0.118 m — **position stayed on the path; the heading did not** | 6.106 m, **100 % reverse** |
| **C** named degenerate stretch | (+1.0, +7.0) → (+7.0, +7.0), 6 m into **East A** | **SUCCEEDED** in 11.09 s | **0.150 m** (**1.07 × floor**), heading +5.3° | 0.073 / 0.122 m | 6.003 m |
| **D** a goal the planner must refuse | (−4.5, +7.0) → (+5.0, +9.0), **inside RackRowA** | **ABORTED**, `error_code 208 NO_VALID_PATH`, after 90.77 s | vehicle **did not move**: 0.000 m over 905 samples | — | **no path, ever** |

### 5.0 What the first attempt did, because it is the finding

The first straight-traverse route tried was **(−11.0, +7.0) → (−1.0, +7.0)**,
10 m down aisle A. It **ABORTED** with `error_code 104 PATIENCE_EXCEEDED`
after 3.66 m, and the controller log says why:

```
[controller_server]: RegulatedPurePursuitController detected collision ahead!
[controller_server]: Controller patience exceeded
```

That is not a controller defect. **That route passes a column pinch.** The
`--aisle` scan of §2.1 shows the free width falling from 3.80 m to **2.35 m**
at x ≈ −6.25, which leaves the padded polygon **0.356 m** each side. The
plan legitimately swings north to clear it (measured excursion 0.410 m off
the straight line between its own endpoints — that excursion **is the
avoidance**, not planner noise), the vehicle tracks it with error, and the
sum exceeds the budget.

**The route was changed and the reason recorded here rather than tuned away.**
A 3.80 m aisle with 2.35 m pinches is what this building is; the vehicle
needs a route that does not spend its whole lateral budget on one obstacle,
and choosing one is a *fleet routing* decision (M6), not a Nav2 parameter.

**This attempt has no committed recording either** — it ran under the same
case name as §5.1's attempts and was truncated by them. Its figures and the
two log lines above are quoted from the run transcript. The remedy is the
same one open question in §6: the harness derives its output path from the
case name, so a case must be renamed before it is re-run.

### 5.1 Case A, straight aisle traverse — and the one parameter that changed

Four attempts on the same route, all recorded:

| attempt | `lookahead_dist` | result | goal error | tracking rms / max | ground truth path | artefacts |
|---|---|---|---|---|---|---|
| 1 | 1.20 m | SUCCEEDED, 26.5 s | 0.250 m | 0.171 / 0.396 m | 6.867 m | **overwritten** — see below |
| 2 | 1.20 m | **ABORTED** `104`, 40.7 s | 1.655 m | 1.060 / 1.228 m | 5.225 m | `m5-10-a_straight_lookahead120-*` |
| 3 | **1.60 m** | **SUCCEEDED, 13.4 s** | **0.183 m** | **0.119 / 0.190 m** | 5.501 m | `m5-10-a_straight-*` |
| 4 | 1.60 m | **TIMEOUT** at 240 s | 0.335 m | 0.228 / 0.760 m | 9.444 m | `m5-10-a_straight_repeat-*` |

**Attempt 1's recording does not exist and its figures are quoted from the
harness transcript only.** The harness writes to a path derived from the
case name, so re-running the same case truncates the previous recording —
the failure `docs/LESSONS.md` 2026-07-28 already records for the bridge's
evidence CSV, met again here. The four rows above are the complete attempt
history for this route; no attempt is omitted.

**What changed and why**: `lookahead_dist` 1.20 → 1.60 m. The mechanism is
in the vehicle, not the parameter — §3.3 measured up to **23 % understeer**
at the tightest planned arc and the steer axis needs up to 0.79 s to slew,
so the curvature RPP demands is realised late and a short carrot
over-corrects. Attempt 2 shows what that costs: the vehicle wandered to
**y = +8.18**, 1.18 m north of the aisle centre and hard against the padded
rack face, where RPP's own collision check stopped it. At 1.60 m the same
route tracked three times tighter and the divergence did not recur. The
ceiling is geometry: pure pursuit needs L ≤ 2R = 2.10 m.

**Attempt 4 is the honest half of the result, and it is the endgame, not the
traverse.** The vehicle reached 0.335 m from the goal and then spent 240 s
shuffling — 200 forward samples, 195 reverse, steer at the **75.06° stop** —
without ever satisfying the goal checker. The cause is geometric and worth
stating plainly:

> **A vehicle whose smallest arc has a 1.29 m measured radius cannot make a
> 0.25 m correction.** Its smallest manoeuvre leaves the tolerance circle
> and comes back. `xy_goal_tolerance: 0.25` is dimensioned from the
> localization measurement (§4) and is *below the vehicle's own manoeuvring
> granularity*, so an approach that ends outside the circle has no small
> move that fixes it.

Nothing was changed to hide that: the tolerance stays derived from the
measurement, and the mismatch is written up as an open question (§6) because
the fix is a decision about what a "reached" goal means for a
non-holonomic vehicle, not a number to nudge.

**One more measured detail from the plan itself.** Every plan on this route
begins with a **0.092 m reverse primitive** — one Reeds-Shepp motion
primitive, 1.6 % of a 5.693 m path — because the start and goal are nearly
collinear with a 28 mm lateral offset and RS resolves that with a reversal
rather than a turn. RPP executes it as a reverse segment, and the two
attempts that went badly both started with it. `reverse_penalty` was swept
on the bench (2.0 → 3.0 → 5.0 → 10.0) and **does not remove it**, while it
does wreck the genuine reverse of case B (a clean 6.0 m reverse becomes a
9.5–10.2 m four-cusp manoeuvre). So it stays at 2.0, and the request that
follows from it is in §6.

### 5.2 Case B, a goal requiring a reverse segment — and where reverse stops working

The vehicle **cannot turn round in an aisle** (§2: the padded swept circle
on the tightest planned arc is 4.739 m across, against a 3.80 m aisle), so a
goal behind it is a genuine reverse manoeuvre and not a contrivance.

**2 m astern, (+1.0, +7.0) → (−1.0, +7.0): SUCCEEDED in 4.37 s.** The plan
is **100 % reverse, 0 cusps**, and the drive is the tightest tracking in
this whole file:

```
  command sign           0 forward / 43 reverse / 1 at rest
  steer angle commanded  max |0.0493| rad (2.82 deg)
  TRACKING  rms 0.0009 m   max 0.0027 m   p95 0.0017 m
  ABSOLUTE position error 0.3117 m (2.21 x floor), heading -1.159 deg
```

The 0.312 m goal error against a 0.0009 m tracking error is **localization,
not control**: the vehicle believed it was 0.230 m from the goal — inside
the 0.25 m tolerance, which is why the checker passed — and it was really
0.312 m away. That gap is the measurement §4 is dimensioned from, visible
end to end in one number.

**6 m astern, (+1.0, +7.0) → (−5.0, +7.0): ABORTED, `error_code 104`, and
the mechanism is geometric.** The plan was again 100 % reverse with 0 cusps.
The vehicle tracked it at **rms 0.0615 m / max 0.118 m for the first
2.39 m**, then diverged: heading ran out to **+0.87 rad (50°)**, and RPP's
patience expired 3.68 m from the goal.

> Pure pursuit is stable when the steered axle **leads**. Reversing, this
> vehicle's steered wheel **trails**, and a pursuit law referenced at the
> other end of the wheelbase is an unstable loop — the classic
> reversing-a-trailer geometry. RPP has no separate reverse reference point
> and no separate reverse lookahead. **Measured limit on this vehicle at
> 0.60 m/s: reverse is followed to about 2.4 m; beyond that the heading
> diverges.** That bound is one observation of one route and is quoted with
> its n = 1 (`docs/LESSONS.md` 2026-08-04).

### 5.3 Case C, a goal in the named degenerate stretch

`sim/worlds/WAREHOUSE_LANDMARKS.md` §5 names **East A** — aisle A,
x ∈ [+2.0, +7.0], worst `aniso` 0.034 at x = +7.0, "single axis, x free",
where 99 % of the along-aisle information is carried by ten rays.
`EVIDENCE_LOCALIZATION.md` (c) measured AMCL holding 0.28–0.35 m there
through a 128.7 s dwell.

**Driving 6 m into it, (+1.0, +7.0) → (+7.0, +7.0), ending on the worst
pose: SUCCEEDED in 11.09 s.**

```
  plan                   6.003 m, 0 cusps, 0.0 % reverse
  ground-truth path      5.866 m
  command sign           110 forward / 0 reverse / 1 at rest
  steer angle commanded  max |0.2030| rad (11.63 deg)
  TRACKING  rms 0.0730 m   max 0.1223 m
  ABSOLUTE position error 0.1503 m (1.07 x floor), heading +5.306 deg
```

**0.150 m against a 0.141 m floor is at the instrument's resolution.** The
degenerate stretch cost this traverse nothing measurable — which is the
result the landmark prediction and the AMCL dwell measurement together
predicted, and it is stated as "nothing measurable", not as "nothing":
74 % of that route's samples sit at or below the floor and about them this
instrument says only that they were inside its resolution.

It is also the cleanest drive in the file, and the difference from case A is
visible in one column: **0 cusps and 0 % reverse in the plan**.

### 5.4 Case D, a goal the planner must refuse — and what refusal looks like

Goal: world (+5.0, +9.0), **inside RackRowA**, a lethal cell in the frozen
grid. From outside, in order:

1. **The action server ACCEPTS the goal.** A refusal is a *result*, not a
   rejection at the door: `goal ACCEPTED at t_sim 41.71`.
2. **The planner fails, out loud, every time**, ~5 s apart:
   ```
   [planner_server]: GridBased plugin failed to plan from (1.58, 12.58) to (11.10, 14.50): "no valid path found"
   [planner_server]: [compute_path_to_pose] [ActionServer] Aborting handle.
   ```
3. **The behaviour tree does its two harmless recoveries** — clear the local
   costmap, clear the global costmap, `Wait 5.0` — and replans. Six retries,
   seven planning attempts.
4. **`NavigateToPose` ABORTS with `error_code 208 NO_VALID_PATH`** after
   **90.77 s**.
5. **The vehicle never moves.** 905 samples over 90.74 s of simulation time,
   ground-truth path **0.000 m**, 0 forward / 0 reverse / 905 at rest, zero
   rotation-in-place refusals. The final truth pose is the spawn pose to
   six decimals.

That is the whole point of removing `Spin` and `BackUp` from the tree: a
vehicle that cannot reach a goal **stands still and says so**, instead of
milling about an aisle because a plan failed.

**Two costs of this refusal are measured rather than assumed.** It takes
90.77 s to arrive, because each of the seven attempts spends its full
`max_planning_time` — the planner cannot use its potential-field shortcut
at this inflation radius (§4) and full-footprint checking is the price.
And the planner does **not** distinguish "goal occupied" from "no path": the
same `NO_VALID_PATH` (208) is returned, and the bench (§5.5) shows the same
goal returning `207 TIMEOUT` on other runs, from the same cause. **A caller
cannot tell from the error code why it was refused.** At M6 that matters and
it is in §6.

### 5.5 The planner alone, on the bench

`nav2_run.py plan` drives `ComputePathToPose` with an explicit start pose
against a bare `planner_server` + `map_server` — no simulator, no
controller, no localizer — so a planner claim costs 0.02 s to check instead
of a 3-minute run.

| route | result | planning time | length vs chord | cusps | excursion |
|---|---|---|---|---|---|
| A (−4.5,7) → (+1,7) | SUCCEEDED | 0.015 s | 5.693 / 5.500 m | 1 | 0.125 m |
| B 2 m astern | SUCCEEDED | 0.012 s | 2.000 / 2.000 m | 0 | **0.000 m** |
| B 6 m astern | SUCCEEDED | 0.144 s | 6.106 / 6.000 m | 0 | 0.516 m |
| C East A 6 m | SUCCEEDED | 0.012 s | 6.003 / 6.000 m | 0 | 0.046 m |
| D into the rack | ABORTED `207`/`208` | 3.9–5.2 s | — | — | — |
| the 10 m route of §5.0 | SUCCEEDED | 0.021 s | 10.254 / 10.000 m | 0 | **0.410 m** — the column pinch |

**Planning is not the bottleneck**: 0.012–0.166 s for every route that has a
path, against the 5.0 s `max_planning_time` that a refusal spends.

---

## 6. What this evidence does not establish, and what it asks for

1. **The endgame is marginal and the tolerance is below the vehicle's
   manoeuvring granularity.** One attempt in four sat 0.335 m from its goal
   for 240 s, shuffling with the steer at the stop. `xy_goal_tolerance` is
   derived from the localization measurement (0.25 m = 2 × rms) but the
   vehicle's smallest measured arc has a 1.29 m radius, so it has no small
   move that closes a 0.3 m gap. **Request:** a brief that decides what
   "reached" means for a non-holonomic vehicle — a tolerance dimensioned by
   manoeuvring granularity as well as by localization, or a goal checker
   that accepts an approach corridor rather than a circle. It is not a
   number to nudge quietly.
2. **A sub-primitive reverse at the head of a plan is executed as a reverse
   segment.** Every plan on the case A route starts with a 0.092 m Reeds-
   Shepp reverse, and both bad attempts on that route began with it.
   `reverse_penalty` does not remove it and raising it wrecks genuine
   reverses (§5.1). **Request:** a plan filter — drop a leading direction
   segment shorter than the vehicle can meaningfully execute — which lives
   in the BT or a plan post-processor, not in this file.
3. **Reverse is followed to about 2.4 m and then diverges** (§5.2), and that
   bound is **n = 1**: one route, one speed, one direction. It is stated as
   an observation, not a bound (`docs/LESSONS.md` 2026-08-04). A seeded,
   repeated sweep of reverse distance against divergence is its own brief.
4. **No obstacle layer exists in either costmap**, by three measured
   arguments in `nav2.yaml`'s local-costmap header — the navigation lidar at
   z = 1.80 m sees the vehicle's own mast rails (9 of 360 rays, astern) and
   cannot see a pallet, a person or a dropped load, and neither safety
   scanner may feed a costmap (ADR 0011). **So this stack's obstacle
   awareness is exactly the awareness of the frozen grid.** Nothing here was
   tested against an obstacle that is not in the map, and nothing here
   should be read as having been.
5. **The refusal's error code does not carry its reason.** The same goal
   inside a rack returned `208 NO_VALID_PATH` in the simulator run and
   `207 TIMEOUT` on the bench. A fleet client at M6 cannot distinguish
   "occupied", "unreachable" and "too slow to decide" from the code, and
   VDA 5050 will want that distinction.
6. **Container, not WSL.** Every figure here was measured in the project
   session container. The M5 showcase runs on the owner's WSL machine, where
   Gazebo renders through llvmpipe at a different real-time factor; timing
   figures in particular (13.4 s, 90.77 s, 240 s) will differ, and the
   evidence must be re-taken there before a gate rests on it
   (`docs/LESSONS.md` 2026-07-27).
7. **The two costmap ERROR lines are expected and are not silenced.** The
   inflation radius is smaller than both the inscribed (0.769 m) and the
   circumscribed (2.230 m) radius of the padded footprint, so the inflation
   layer is a hard 0.55 m band rather than a gradient and the planner cannot
   use its potential-field shortcut. Raising it was measured and rejected
   (§4): it doubled the plan's excursion on the aisle route.
8. **No docking claim, and no obstacle claim.** §4 says why for docking. For
   obstacles, see 4 above.
9. **Two runs have no committed recording.** `nav2_run.py goal` writes to a
   path the caller supplies and the driver derives that path from the case
   name, so re-running a case truncates its predecessor — the same failure
   `docs/LESSONS.md` 2026-07-28 records for the bridge's evidence CSV. The
   10 m route of §5.0 and attempt 1 of §5.1 are quoted from their
   transcripts only. **Rename the case before re-running it**, or have the
   driver stamp the output path.

---

## 7. How to reproduce

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=<unique> ROS_DOMAIN_ID=<unique>     # BOTH, always

# the parameter probes need nothing running
ros2 run nav2_planner planner_server --ros-args --params-file <probe>.yaml
ros2 run nav2_velocity_smoother velocity_smoother     # then ros2 param get

# the footprint, and the aisle it has to fit in
python3 agv/forklift/scripts/footprint_from_model.py --check "<polygon from nav2.yaml>"
python3 agv/forklift/scripts/footprint_from_model.py --aisle --line-y 7.0

# the planner alone: map_server + planner_server, no simulator
python3 agv/forklift/scripts/nav2_run.py plan \
    --start-x -4.5 --start-y 7.0 --x 1.0 --y 7.0

# a full case: three terminals, then the goal
ros2 launch sim/launch/warehouse_bringup.launch.py x:=<X> y:=<Y> yaw:=0.0
python3 agv/forklift/scripts/localization_run.py map-pose --x <X> --y <Y> --yaw 0.0
ros2 launch agv/forklift/launch/localization.launch.py \
    initial_pose_x:=<mx> initial_pose_y:=<my> initial_pose_yaw:=<myaw>
ros2 launch agv/forklift/launch/navigation.launch.py
python3 agv/forklift/scripts/nav2_run.py goal --x <GX> --y <GY> --yaw 0.0 \
    --csv run.csv --plan run.json
python3 agv/forklift/scripts/nav2_run.py analyse --csv run.csv --plan run.json

# the conversion against a commanded motion: bringup + converter + io only
python3 agv/forklift/scripts/cmd_vel_to_tricycle.py --ros-args -p use_sim_time:=true
python3 agv/forklift/scripts/forklift_io.py --ros-args -p use_sim_time:=true
python3 agv/forklift/scripts/nav2_run.py convcheck --csv convcheck.csv
```
