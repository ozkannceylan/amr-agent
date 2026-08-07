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

---
---

# 8. THE SHOWCASE MACHINE — 2026-08-05 (m5-31)

**Sections 0-7 above are untouched.** They are container runs and they stay
exactly as they were committed. This section is the first diagnosis of the
same route on the **WSL machine the M5 showcase runs on**, and it is written
as each measurement landed rather than assembled afterwards.

| Item | Value |
|---|---|
| Date | **2026-08-05** |
| Host | WSL2 Ubuntu 24.04 on the owner's Windows 11 machine, **20 cores**, headless, llvmpipe |
| Package stack | current with the archive as of m5-26 (`sim/setup/WSL_ENVIRONMENT.md` Part III); nav2 **1.3.12**, the same version §0 records |
| Under test | unchanged. No file in `agv/` was edited to obtain any figure in this section |
| Isolation | `GZ_PARTITION=m531<tag>` **and** `ROS_DOMAIN_ID=81`, both set on every run |
| Machine checked alone | before the first run: `load average 0.03`, no `gz sim`, no ROS 2 process, `/dev/shm` 2 entries, 2026-08-05T12:26:54Z |
| Chain | `warehouse_bringup` -> `localization.launch.py` -> `navigation.launch.py gate:=false cmd_topic:=/cmd_vel_smoothed` — the **m5-10 chain**, one variable against §5 |
| Route | §5.1's case A, world (−4.5, +7.0) -> (+1.0, +7.0) |

**This is not a regression and this section never calls it one.** §0's own
environment block says nothing above was ever reproduced here, so every figure
below is a **first measurement on this platform**, not a second one
(`docs/LESSONS.md` 2026-08-05).

## 8.1 Two hypotheses the 4-core / 20-core clue pointed at, and how each was killed

Both were killed by measurement before anything was changed.

### (a) Real-time factor and the wall-clock loop rates — FALSIFIED

The reasoning was: nav2's controller loop is a steady-clock loop, so if the
simulator's real-time factor differs, the controller's period in **simulated**
time differs with it, and a machine that runs the world slower gives its
controller more iterations per simulated metre.

Measured on WSL, `gz topic -e -t /world/warehouse/stats`:

```
bare world, no vehicle, no ROS       real_time_factor: 0.99619999511862
full stack up, vehicle at rest       real_time_factor: 0.9999855002102469
immediately after a route run        real_time_factor: 1.0010951981467726
```

The container side is settled from the **committed** artefacts rather than
guessed. `evidence/m5-10-a_straight-stack.txt` carries the wall clock of every
`Passing new path to controller`, which the behaviour tree provokes once per
replan:

```
1785837125.586  1785837126.637  1785837127.678  1785837128.716  1785837129.756
1785837130.786  1785837131.807  1785837132.827
             consecutive differences 0.997 0.989 0.977 0.967 0.997 0.967 0.987 s
```

Thirteen replans spanning **12.6 s of wall clock** inside a run whose recording
spans **13.39 s of simulation time**. **The container was also at RTF ~ 1.0.**
There is no real-time-factor difference between the two platforms, so nothing
downstream of one can explain the difference in outcome.

### (b) Belief degrading while the stack stood still before the goal — FALSIFIED

`sim/README.md` records that the EKF integrates ~0.0023 rad/s of heading on a
stationary vehicle, and AMCL does not correct it because `update_min_d 0.25` /
`update_min_a 0.2` mean a stationary robot produces no update. The container
issued its goals at **t_sim 45-48**; this session's runs issue them at
**t_sim 150-183**, because bringing three launch files up here takes longer.
That is a two-to-three-minute difference in standing time.

Measured, believed pose against ground truth **at the first recorded sample of
each run**, which is the instant the goal was accepted:

| run | t_sim at goal ACCEPTED | position error | heading error |
|---|---|---|---|
| container 5.1 case A | 47.69 | 0.000 m | -0.07 deg |
| container 5.1 attempt 4 | 45.22 | 0.000 m | +0.00 deg |
| container 5.3 case C | 47.84 | 0.000 m | -0.01 deg |
| **WSL r1** | **150.32** | **0.000 m** | **+0.00 deg** |
| **WSL r2** | **178.82** | **0.000 m** | **+0.00 deg** |

**No drift reaches the belief, on either platform**, and r2 is the positive
control: it stood the longest (178.82 s) and produced the **best** run in this
whole session. Dwell is not the variable.

## 8.2 The route on this platform, five runs, nothing changed

`gate:=false cmd_topic:=/cmd_vel_smoothed`, the section 5 chain, committed
`nav2.yaml`, committed behaviour tree, same goal, `--timeout 120`. Machine
checked idle before the first and torn down to zero stray processes after each.

| run | result | elapsed (sim) | ground-truth path | goal error, absolute | believed | tracking rms / max | fwd / rev / rest | steer max |
|---|---|---|---|---|---|---|---|---|
| **r1** | SUCCEEDED | 82.21 s | 12.090 m | 0.061 m | 0.167 m | 0.4097 / 1.0838 m | 461 / 264 / 98 | **75.06 deg (stop)** |
| **r2** | **SUCCEEDED** | **13.21 s** | **5.556 m** | **0.156 m** | 0.199 m | **0.0510 / 0.1030 m** | 112 / 16 / 5 | 45.47 deg |
| **r3** | SUCCEEDED | 106.30 s | 14.248 m | 0.187 m | 0.059 m | 0.4578 / 1.1350 m | 545 / 352 / 164 | **75.06 deg (stop)** |
| **r4** | **TIMEOUT** | 120.00 s | 12.110 m | 0.432 m | 0.387 m | 0.3425 / 0.7923 m | 609 / 352 / 235 | **75.06 deg (stop)** |
| **r5** | **TIMEOUT** | 120.00 s | 13.624 m | 0.272 m | 0.444 m | 0.4259 / 1.0517 m | 535 / 319 / 343 | **75.06 deg (stop)** |

Artefacts: `evidence/m5-31-a_straight-r<N>-{run.csv,goal.txt,analyse.txt,plan.json}`.

**The committed 13.40 s / 0.183 m result reproduces here — r2 gives 13.21 s and
0.156 m, and tracks three times tighter than the committed run did.** So there
is no platform regression and no packaging regression to find. What there is,
is a route whose outcome is a **draw**: one clean traverse in five, two that
arrived and then spent 70-95 s recovering, and two that never finished.

The container's own history says the same thing and always did: section 5.1
records four attempts on this route, of which one succeeded in 13.40 s and one
ran 240 s without ever satisfying the goal, **at the same parameters**. The
committed figure is one draw quoted as a result.

**The plan is identical in every run and is not the variable.** 71 points,
5.693 m, 1 cusp, 1.6 % reverse — the committed plan, in all five. Section 5.5's
whole bench re-runs here unchanged; see 8.6.

## 8.3 THE CAUSE — the goal checker's two conditions are not jointly reachable by this vehicle

The goal checker is `SimpleGoalChecker` with `xy_goal_tolerance: 0.25` and
`yaw_goal_tolerance: 0.15` rad (8.594 deg). Both must hold **at the same
controller tick**.

Counted over every recorded sample of each run — believed pose against the
commanded goal, which is the pair the checker itself evaluates:

| run | samples inside 0.25 m | samples inside 8.594 deg | **samples inside BOTH** | outcome |
|---|---|---|---|---|
| container 5.1 case A | 1 | 134 | **1**, at t = 13.4 s | SUCCEEDED at t = 13.4 s |
| container 5.1 attempt 4 | 80 | 2186 | **0** | TIMEOUT at 240 s |
| WSL r2 | 2 | 133 | **2**, first at t = 13.1 s | SUCCEEDED at t = 13.2 s |
| WSL r3 | 446 | 262 | 6, first at t = 105.8 s | SUCCEEDED at t = 106.3 s |
| WSL r1 | 177 | 461 | 15, first at t = 14.9 s | SUCCEEDED at t = 82.2 s |
| **WSL r4** | **559** | **471** | **0** | **TIMEOUT at 120 s** |
| **WSL r5** | **117** | **641** | **0** | **TIMEOUT at 120 s** |

**Every completion happens at a sample where both hold, and every failure is a
run in which the two never hold together.** r4 is the clearest: it spent
**55.9 s inside the position circle** and **47.1 s inside the heading window**,
and never one second inside both. The container's 240 s attempt is the same
shape, and it is the same shape at four cores.

### The position term is not what blocks it

`stateful: true` is set precisely so that position latches once satisfied. It
is reset by `ControllerServer::setPlannerPath`, which runs on every path the
behaviour tree hands down — **116 times in r4's 120 s**, once per second, from
the tree's `<RateController hz="1.0">`. The obvious next hypothesis is that the
latch never survives long enough to be useful.

**Tested, with the replan rate lowered tenfold and nothing else changed** —
`bt_xml:=` a copy of the committed tree with `hz="0.1"`
(`evidence/m5-31-experiment-bt-slowreplan.xml`), run e1:

```
resets (Passing new path to controller)   11 over 120 s, against 116 in r4
RESULT           CANCELLED/TIMEOUT
elapsed          120.00 s
final BELIEVED   0.0265 m from the goal, heading -47.208 deg
samples inside 0.25 m   851 of 1196     samples inside 8.594 deg   238
samples inside BOTH     0
```

**The vehicle parked 2.7 cm from the goal and stayed there, pointing 47 deg
away, for the rest of the run.** So the latch is not the mechanism and the
position tolerance is not the binding term: **the heading is.**

### Why heading cannot be fixed once position is right

The endgame is a manoeuvre with a measured cost. Over every sample after the
vehicle first came within 0.6 m of the goal, from ground truth:

| run | endgame duration | ground-truth path | total heading turned | **metres travelled per radian** | median instantaneous radius |
|---|---|---|---|---|---|
| container 5.1 case A | 1.1 s | 0.38 m | 1.5 deg | 14.95 | 14.56 m |
| WSL r2 | 0.8 s | 0.37 m | 1.6 deg | 12.90 | 12.99 m |
| WSL r1 | 69.4 s | 6.88 m | 160.3 deg | **2.46** | 2.17 m |
| WSL r3 | 93.5 s | 8.95 m | 245.3 deg | **2.09** | 2.21 m |
| WSL r4 | 105.2 s | 6.72 m | 158.6 deg | **2.43** | 2.05 m |
| WSL r5 | 107.0 s | 8.35 m | 213.5 deg | **2.24** | 1.87 m |
| container 5.1 attempt 4 | 218.8 s | 2.54 m | 57.1 deg | **2.55** | 1.46 m |
| WSL e1 (slow replan) | 109.2 s | 4.99 m | 120.9 deg | **2.37** | 1.05 m |

**The two clean runs turn 1.5 deg in the endgame and the rest turn 120-245 deg.**
And when this vehicle turns, it pays **2.1-2.6 m of travel per radian** — the
non-holonomic coupling, measured, not assumed. Correcting a heading error of
one yaw tolerance (0.15 rad) therefore costs about **0.32-0.39 m of travel**,
against a position tolerance of **0.25 m**. The correction is bigger than the
box it has to stay inside.

> **The cause, stated once.** `xy_goal_tolerance: 0.25 m` and
> `yaw_goal_tolerance: 0.15 rad` are each individually reasonable and are
> **jointly unreachable** on a vehicle that cannot rotate in place and pays
> ~2.4 m of travel per radian of heading. Any approach that delivers the goal
> position with more than roughly 8.6 deg of heading error has **no manoeuvre**
> that fixes the heading without leaving the position circle, and no manoeuvre
> that re-enters the position circle without changing the heading again. The
> run then either completes on the approach itself or does not complete at all.

### The discriminator, and it is the approach, not the endgame

Believed heading error at the **first** sample inside the position circle:

| run | heading at first entry | outcome |
|---|---|---|
| container 5.1 case A | **-3.86 deg** | SUCCEEDED, 13.4 s |
| WSL r2 | **+2.17 deg** | SUCCEEDED, 13.2 s |
| WSL r1 | -7.72 deg | SUCCEEDED at 82.2 s, after 69 s of recovery |
| WSL r5 | -13.11 deg | TIMEOUT |
| container 5.1 attempt 4 | -16.34 deg | TIMEOUT |
| WSL r4 | +19.73 deg | TIMEOUT |
| WSL r3 | +37.26 deg | SUCCEEDED at 106.3 s, after 94 s of recovery |

**Every run that arrives inside 8.6 deg finishes at once; no run that arrives
outside it finishes quickly, and two never finish.** The arrival heading is not
controlled by anything: RPP delivers whatever the last metre of path gives, and
the vehicle is still correcting cross-track error as it reaches the goal. In r1
the vehicle tracked 0.41 m north of the aisle centre and was turning right when
it arrived; in r2 it tracked 0.09 m north and arrived straight.

## 8.4 Two one-variable confirmations — RUN AS EXPERIMENTS, NOT APPLIED

**Nothing in `agv/` was edited for these.** Each used a copy of `nav2.yaml` in
`/tmp` differing from the committed file by **exactly one line**, verified by
`diff` after the run, and passed in with `params_file:=`.

| experiment | the one line | result | endgame |
|---|---|---|---|
| **e2** | `yaw_goal_tolerance: 0.15` -> **0.60** | **SUCCEEDED in 15.01 s**, path 5.752 m, 0 refusals | none — finished on the approach, believed heading **-8.642 deg** |
| **e3** | the same | **SUCCEEDED in 13.71 s**, path 5.559 m, 0 refusals | none — believed heading -0.819 deg |
| **e4** | `xy_goal_tolerance: 0.25` -> **0.45** | SUCCEEDED in 31.06 s, path 7.171 m, 1 refusal | one correction manoeuvre, steer to 74.40 deg, then in |

**e2 is the sharpest number in this section.** It completed with a believed
heading error of **8.642 deg**, which is **0.048 deg outside the committed
0.15 rad tolerance**. Under the committed configuration that identical approach
would have been rejected and would have entered the shuffle. The margin the
committed configuration leaves is not small; it is negative by a rounding
error.

e4 says the same thing from the other side: 0.20 m of extra position slack is
enough to absorb **one** heading correction, so the route completes — but in
31 s and with the steer at 74.40 deg, not on the approach.

**Neither value is proposed here and neither was written to `nav2.yaml`.** They
are the measurement that identifies which term binds. What to do about it is
8.7.

## 8.5 What the recovery shuffle costs the localizer — a second-order finding

Section 4 dimensions `footprint_padding: 0.27` from a measured localization
worst case of **0.263 m**. Believed pose against ground truth, over every
sample of this session's runs:

| run | position rms | position max | heading rms | heading max |
|---|---|---|---|---|
| r2 (clean traverse) | 0.0421 m | 0.0955 m | 0.78 deg | 1.90 deg |
| r1 | 0.1021 m | 0.2402 m | 1.63 deg | 3.53 deg |
| r5 | 0.1146 m | 0.1741 m | 1.66 deg | 3.91 deg |
| e1 | 0.1865 m | 0.2335 m | 5.69 deg | 11.32 deg |
| r3 | 0.2468 m | 0.4154 m | 3.57 deg | 8.18 deg |
| **r4** | **0.3990 m** | **0.6610 m** | 5.78 deg | **10.48 deg** |
| **all pooled, n = 5606** | **0.2394 m** | **0.6610 m** | 4.18 deg | 11.32 deg |

**A clean traverse localizes better than the committed figure; a shuffling one
localizes far worse.** r4's 0.661 m worst case is **2.5 x the 0.263 m the
costmap padding is dimensioned from**, so during the recovery the padded
footprint no longer covers where the vehicle actually is. The mechanism is not
mysterious — hundreds of direction reversals with the steer at the stop are the
regime AMCL's motion model is least able to follow — but it means the endgame
does not merely waste time: **it degrades the one measurement the collision
geometry is built on.**

## 8.6 Ruling on every committed figure

Each row is **still stands** (re-measured here, with the number), **superseded**
(both numbers given), or **unverified on this platform** — never "plausible".

### The Nav2 figures (sections 1, 3, 5)

| committed figure | ruling on WSL |
|---|---|
| 5.1 case A **SUCCEEDED 13.40 s, 0.183 m, rms 0.119 m** | **SUPERSEDED as a result, reproduced as a draw.** r2 gives 13.21 s / 0.156 m / rms 0.051 m — but that is 1 run in 5. The honest figure for this route on this platform is the 8.2 table: 5 runs -> 1 clean, 2 completed after 69-94 s of recovery, 2 timed out at 120 s |
| 5.1 attempt 4, **TIMEOUT at 240 s, 0.335 m** | **STILL STANDS, and is the majority case here.** WSL r4 and r5 are the same event at 120 s |
| 5.1 the plan, **5.693 m, 71 points, 1 cusp, 1.6 % reverse** | **STILL STANDS.** Identical in all nine runs of this session |
| 5.1 the **0.092 m leading reverse primitive** | **STILL STANDS.** Present in every plan measured here |
| 5.1 `lookahead_dist` 1.20 -> 1.60 | **UNVERIFIED on this platform.** No 1.20 m run was taken here; the comparison it rests on is container-only |
| 5.5 the planner bench: A 5.693 m 1 cusp; B 2 m 2.000 m 0 cusps 100 % reverse; B 6 m 6.106 m; C 6.003 m; the 10 m route 10.254 m; D refused | **STILL STANDS, every row, exactly.** Re-run here against a bare `map_server` + `planner_server`, no simulator: 5.693 / 2.000 / 6.106 / 6.003 / 10.254 m with the same cusp counts and the same reverse percentages, and D `ABORTED 207 TIMEOUT` — one of the two codes 5.4 records for it. **The planner is deterministic and is not the variable** |
| 5.5 planning times 0.012-0.166 s | **UNVERIFIED.** The bench ran, but no timing figure was taken and none is quoted |
| 5.0 the 10 m route's **0.410 m excursion** and the column pinch | **UNVERIFIED as a drive.** The plan re-measures here (10.254 m); no vehicle was driven down it in this session |
| 5.2 case B, 2 m astern, 0.312 m, rms 0.0009 m | **UNVERIFIED on this platform.** Not driven here |
| 5.2 case B', reverse diverges beyond **~2.4 m** | **UNVERIFIED on this platform.** Not driven here, and it was already n = 1 |
| 5.3 case C, degenerate stretch, 11.09 s, 0.150 m | **UNVERIFIED on this platform.** Not driven here |
| 5.4 case D, refusal `208` after 90.77 s, vehicle moves 0.000 m | **PARTLY.** The planner's refusal re-measures on the bench (`207`); the 90.77 s, the seven attempts and the 0.000 m of motion were not re-driven here |
| 3.3 the conversion check, understeer to 23 %, refusal of rotation in place | **UNVERIFIED as a run.** But the refusal path is exercised in every run above (r1 7, r4 8, r5 11 refusals counted), and the endgame's measured 1.05-2.21 m median radius is consistent with the 1.29 m the committed check reports |
| 1 (a)-(e), the five Jazzy parameter traps | **UNVERIFIED on this platform.** nav2 is 1.3.12 on both sides, but a version match is not a measurement and this section does not treat it as one |
| 2, the footprint hull and `--aisle`'s 0.356 m | **UNVERIFIED here.** Both are computed from committed files by a script that takes no measurement from the machine |

### The localization figures (section 4, from `EVIDENCE_LOCALIZATION.md`)

| committed figure | ruling on WSL |
|---|---|
| the **0.141 m instrument floor** (registration residual max) | **STILL STANDS.** `load_registration` verifies the grid's md5 and re-derives the floor at the start of every harness run; all nine runs of this session printed `FLOOR rms 0.0404 MAX 0.1411 m` and would have refused to run against a rebuilt map |
| steady-state **rms 0.124 m** | **STILL STANDS while the vehicle drives, SUPERSEDED while it shuffles.** Clean traverse r2: **0.042 m**. Recovery runs: r3 **0.247 m**, r4 **0.399 m**. Pooled over all 5606 samples: **0.239 m** |
| worst case **max 0.263 m** | **SUPERSEDED: 0.661 m** (r4). Three runs stay under it (r2 0.096, r5 0.174, r1 0.240); the two worst shuffles exceed it by 1.6x and 2.5x |
| heading **rms 1.44 deg, max 4.52 deg** | **SUPERSEDED: rms 4.18 deg, max 11.32 deg** pooled. r2 alone gives **0.78 / 1.90 deg**, better than committed |
| section 4's derived `footprint_padding: 0.27` | **NO LONGER COVERS THE MEASUREMENT it is derived from**, during recovery only (0.661 m against 0.263 m). It is untouched here; 8.7 asks for it |

**One qualification these rows carry.** The localization figures above were
taken on the aisle-A route this brief drove, not on the route
`EVIDENCE_LOCALIZATION.md` measured. They are the same building, the same
localizer and the same instrument floor, and the comparison is stated as
route-to-route rather than as a repeat of that run.

## 8.7 What this asks for, and what was deliberately not done

**Nothing was tuned.** `nav2.yaml`, the behaviour tree, `config.yaml`,
`cmd_vel_to_tricycle.py` and both launch files are exactly as they were
committed. The two parameter values in 8.4 exist only in `/tmp` copies and are
named as the instrument that identified the binding term.

1. **The goal criterion has to be re-derived against the vehicle's turning
   geometry, not only against the localizer.** Section 6 item 1 already asked
   for this and dimensioned it wrongly: it says the vehicle "has no small move
   that closes a 0.3 m gap", and the measurement here says the position gap is
   closed routinely — r4 reached 0.047 m and e1 reached 0.027 m — while the
   **heading** is what cannot be brought in. The tolerance pair has to satisfy
   `xy_tol > R_endgame x yaw_tol`, and with R measured at 2.1-2.6 m/rad,
   0.25 m against 0.15 rad fails that by about 1.5x. Either term can pay for it
   (e2, e4), and which one should is a decision about what a "reached" goal
   means for a fork truck approaching a station — not a number to nudge.
2. **The arrival heading is uncontrolled, and that is the upstream fix.** A
   goal checker with slack hides the problem; the vehicle still arrives turning
   because RPP is correcting cross-track error into the last metre. An approach
   corridor — the final segment driven straight along the goal heading, which
   the Reeds-Shepp planner can express and the behaviour tree could enforce —
   fixes the cause instead of widening the acceptance. This is the same request
   section 6 item 2 makes about the leading reverse primitive, at the other end
   of the path, and both belong in a plan post-processor or the tree.
3. **`footprint_padding` is dimensioned from a number the recovery
   invalidates** (8.5). Either the padding grows to cover the recovery regime,
   or — better — the recovery stops happening, which is items 1 and 2.
4. **Not measured here, and it should be, before the showcase:** whether the
   other section 5 cases (B, B', C, and D as a drive) behave on this platform.
   This brief re-measured case A and the planner bench only. 8.6 marks each of
   the others unverified rather than assuming the aisle-A result carries.
5. **A repeat count belongs in the harness.** Every figure in section 5 is
   n = 1, and this section only exists because five repeats were taken.
   `nav2_run.py goal` should take a repeat argument and stamp its own output
   path, which also closes section 6 item 9's truncation problem.

## 8.8 How this section was run

```bash
# machine verified alone first: load average 0.03, no gz, no ROS process,
# /dev/shm 2 entries, 2026-08-05T12:26:54Z
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=m531<tag> ROS_DOMAIN_ID=81     # BOTH, every run
unset DISPLAY WAYLAND_DISPLAY                      # headless, llvmpipe

ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
ros2 launch agv/forklift/launch/localization.launch.py \
    initial_pose_x:=1.584770 initial_pose_y:=12.576859 initial_pose_yaw:=-0.007915
ros2 launch agv/forklift/launch/navigation.launch.py \
    gate:=false cmd_topic:=/cmd_vel_smoothed
python3 agv/forklift/scripts/nav2_run.py goal --x 1.0 --y 7.0 --yaw 0.0 \
    --settle 20 --timeout 120 --csv <tag>.csv --plan <tag>.json
python3 agv/forklift/scripts/nav2_run.py analyse --csv <tag>.csv --plan <tag>.json

# THE PLANNER BENCH NEEDS A TF TREE AS WELL AS A MAP, which section 7's recipe
# omits: planner_server ACTIVATE FAILS without one, and every route then
# returns 205 START_OCCUPIED, which reads like a map fault and is not one.
ros2 run tf2_ros static_transform_publisher --x 1.58477 --y 12.576859 \
    --yaw -0.007915 --frame-id map --child-frame-id forklift/odom
ros2 run tf2_ros static_transform_publisher \
    --frame-id forklift/odom --child-frame-id forklift/base_link
ros2 run nav2_map_server map_server --ros-args \
    -p yaml_filename:=sim/maps/warehouse/warehouse.yaml
ros2 run nav2_planner planner_server --ros-args --params-file agv/forklift/nav2.yaml
python3 agv/forklift/scripts/nav2_run.py plan --start-x -4.5 --start-y 7.0 --x 1.0 --y 7.0
```

Every run was torn down by pattern against observed `ps -eo args` output,
`ros2 daemon stop` included, and verified to **zero** remaining processes
before the next one started. Runs were serialised; no two simulators ever ran
at once, and the machine was re-checked idle between them.

---

# 9. THE STAGED APPROACH — 2026-08-05 (m5-33)

**Sections 0-8 above are untouched.** Section 8 is the diagnosis this section
answers; its figures are the baseline every figure below is read against.

This section is written **as each run lands**, not assembled afterwards. A
session limit already killed one attempt at this brief with nothing measured
surviving it (`docs/LESSONS.md` 2026-08-05, and the 2026-08-04 entry on
dispatch losses), so each run's row is appended the moment the run exists.

| Item | Value |
|---|---|
| Date | **2026-08-05** |
| Host | WSL2 Ubuntu 24.04 on the owner's Windows 11 machine, 20 cores, headless, llvmpipe — the §8 machine |
| Package stack | unchanged since §8. nav2 **1.3.12** |
| Under test | the staged approach: `nav2.yaml` `staging_goal_checker`, the tree's `GoalCheckerSelector`, `nav2_run.py stage` |
| **Tolerances** | **`xy_goal_tolerance: 0.25` and `yaw_goal_tolerance: 0.15` are UNCHANGED.** Neither was widened; the whole design exists so the vehicle *satisfies* them |
| Isolation | `GZ_PARTITION=m533r<N>` **and** `ROS_DOMAIN_ID=81`, both set on every run |
| Chain | `warehouse_bringup` -> `localization.launch.py` -> `navigation.launch.py gate:=false cmd_topic:=/cmd_vel_smoothed` — the §8.8 chain, one variable against §8.2 |
| Route | §5.1's case A, world (−4.5, +7.0) -> station (+1.0, +7.0) yaw 0 — **the same route §8.2 measured** |
| Staging pose | world (−2.0, +7.0) yaw 0, i.e. `d = 3.0` m back along the goal heading (derived, `ARRIVAL-GEOMETRY.md` §4.2) |
| Go-around bound | `--max-go-arounds 2`: **three approaches maximum**, then the run reports failure rather than continuing to manoeuvre |
| Approach timeout | 45 s of simulation time per approach (a clean 3 m leg costs ~10 s; §8.2's shuffles ran 69-120 s) |

## 9.0 What was verified before the first run

```
# the machine, alone
load average 0.00, 0.00, 0.00   no gz sim, no ROS 2 process, /dev/shm 2 entries
2026-08-05T15:23:27Z

# the two mechanisms, in the INSTALLED binaries, not in documentation
$ grep -o 'nav2_controller::[A-Za-z]*GoalChecker' \
      /opt/ros/jazzy/share/nav2_controller/plugins.xml | sort -u
nav2_controller::PositionGoalChecker
nav2_controller::SimpleGoalChecker
nav2_controller::StoppedGoalChecker

$ strings /opt/ros/jazzy/lib/libbt_navigator_core.so | grep -o nav2_goal_checker_selector_bt_node
nav2_goal_checker_selector_bt_node        # in bt_navigator's COMPILED-IN default
                                          # plugin list, and nav2.yaml sets no
                                          # plugin_lib_names override
```

Both are present, so nothing here needs a dependency added.

## 9.1 What the resumed session found in the committed draft

Commit `6798d8d` is marked INCOMPLETE AND UNVERIFIED and it is. Read against
`ARRIVAL-GEOMETRY.md` §7 the three files were judged as follows, before
anything was run:

| File | Verdict |
|---|---|
| `nav2.yaml` | **correct.** Adds `staging_goal_checker` (`PositionGoalChecker`, 0.25 m, `stateful: true`) and lists it beside `general_goal_checker`. `general_goal_checker` is byte-identical — 0.25 m / 0.15 rad untouched, confirmed by `git show 6798d8d -- agv/forklift/nav2.yaml` |
| `behavior_trees/navigate_to_pose_tricycle.xml` | **correct.** One `GoalCheckerSelector` line and one `goal_checker_id` port, placed like the two selectors already there; `default_goal_checker="general_goal_checker"` makes an unselected goal behave exactly as before |
| `scripts/nav2_run.py` | **broken as committed.** `cmd_stage` is fully written but **unreachable**: `main()` registers `goal`, `plan`, `convcheck`, `analyse` and no `stage` subparser, so the command could not be invoked at all. Added here, with the bound, the timeouts and `d` as explicit arguments |

## 9.2 The five repeats

Same route, same chain, same way §8.2 did them. Rows are appended as each run
lands.

**"Clean" means: REACHED, with zero go-arounds used and no leg in the shuffle
regime.** The shuffle test is pre-registered in `nav2_run.py`
(`_SHUFFLE_REVERSALS = 3`): a leg is shuffling when, after its first sample
inside the goal's position circle, the commanded direction reverses three or
more times. §8.2's two clean traverses reversed 0 and 1 times after entry;
every non-completing run reversed dozens.

| run | outcome | go-arounds | approaches | shuffle regime | elapsed (sim, all legs) | final approach: believed err | truth err | entry heading | localization max |
|---|---|---|---|---|---|---|---|---|---|
| **r1** | FAILED_RETURNING_TO_STAGING | 1 of 2 | 1 | **NO** | 146.15 s | 0.3546 m / +7.16 deg | 0.3360 m / +9.65 deg | **+10.87 deg** | **0.1059 m** |
| **r2** | **REACHED (clean)** | 0 of 2 | 1 | **NO** | **16.42 s** | 0.1818 m / −0.75 deg | 0.2591 m / −1.25 deg | **−1.46 deg** | **0.1186 m** |
| **r3** | **REACHED (clean)** | 0 of 2 | 1 | **NO** | **12.57 s** | 0.2532 m / −1.16 deg | 0.2470 m / −0.66 deg | **−1.78 deg** | **0.0952 m** |
| **r4** | REACHED, **but through a shuffle** | 0 of 2 | 1 | **YES: approach0, 20 reversals** | 46.28 s | 0.1882 m / +8.89 deg | 0.1586 m / +13.03 deg | **+16.94 deg** | **0.1037 m** |
| **r5** | **REACHED (clean)** | 0 of 2 | 1 | **NO** | **12.68 s** | 0.1197 m / +6.52 deg | 0.1820 m / +6.05 deg | **+5.44 deg** | **0.1068 m** |

## 9.3 How this section was run

Each repeat is one invocation of the driver below. It **refuses to start** if
anything matching `gz sim|nav2|amcl|controller_server|bt_navigator|parameter_bridge`
is already running, prints the machine's load and `/dev/shm` count before the
run, and tears down to a verified process count after it — so "measured alone"
is enforced by the script rather than remembered by the operator.

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=m533r<N> ROS_DOMAIN_ID=81     # BOTH, every run
unset DISPLAY WAYLAND_DISPLAY                      # headless, llvmpipe

ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
ros2 launch agv/forklift/launch/localization.launch.py \
    initial_pose_x:=1.584770 initial_pose_y:=12.576859 initial_pose_yaw:=-0.007915
ros2 launch agv/forklift/launch/navigation.launch.py \
    gate:=false cmd_topic:=/cmd_vel_smoothed

# THE ONE COMMAND THAT DIFFERS FROM 8.8. Same route, same goal; the sequencing
# is the deliverable.
python3 agv/forklift/scripts/nav2_run.py stage \
    --x 1.0 --y 7.0 --yaw 0.0 --d 3.0 --max-go-arounds 2 \
    --settle 30 --staging-timeout 90 --approach-timeout 45 \
    --csv  evidence/m5-33-a_straight-r<N>-run.csv \
    --plan evidence/m5-33-a_straight-r<N>-plan.json

python3 agv/forklift/scripts/nav2_run.py analyse \
    --csv  evidence/m5-33-a_straight-r<N>-run-approach.csv \
    --plan evidence/m5-33-a_straight-r<N>-plan.json
```

Each stage leg is gated on a topic appearing rather than on a fixed sleep
(`/forklift/odom`, then `/particle_cloud`, then `/plan`), so a slow bring-up
delays the run instead of corrupting it. Artefacts per run:
`evidence/m5-33-a_straight-r<N>-{run.csv,run-approach.csv,plan.json,stage.txt,analyse.txt}`.

### r1 — what happened, recorded before the next run was started

Run window 2026-08-05T15:27:41Z to 15:31:07Z, machine verified alone before
(`load 0.03`, `/dev/shm` 2, zero stray processes) and torn down to **zero**
remaining processes after.

The staged sequence itself worked mechanically — the checker selection reached
the tree, the staging leg was accepted position-only, the go-around fired and
was bounded. **The arrival did not.** Two mechanisms, both new, both named from
the recording rather than inferred:

**(A) The staging pose is reached with its whole tolerance spent LATERALLY.**
The staging leg stopped at ground truth **(−2.020, +7.253)** against a staging
pose of (−2.000, +7.000): 0.020 m longitudinal and **0.253 m lateral**. This is
the worst distribution of e₀ the design can be handed, and it is not bad luck —
`PositionGoalChecker` stops the vehicle the moment the *radius* is satisfied,
and the vehicle enters the circle from behind and to one side, so the residual
is lateral by construction. The final leg then has to remove 0.25 m of
cross-track inside 3 m. It did not settle: the plan was clean (2.950 m, 42
points, **0 cusps, 0.0 % reverse**), but the drive swung from y = +7.253 to
y = +6.673 — 0.58 m across the line — and entered the position circle at
**+10.87 deg**, outside the 8.594 deg discriminator §8.3 established.

**(B) The endgame is now a STALL, not a shuffle.** From t + 28 s the recording
freezes: ground truth held at (+0.700, +7.151) to three decimals for **20 s**,
with `cmd_v` held at **+0.015 m/s** and the steer at **+1.072 rad**, until the
45 s timeout cancelled the leg. 259 of the leg's 494 samples are at rest. The
converter is not refusing (the refusal count is frozen at 5) — it is converting
a command the plant does not answer: 0.015 m/s at near-full lock is below what
this vehicle breaks away at, so the last 0.34 m is never closed. `analyse`
reports 138 forward / 97 reverse / **244 at rest**.

Mechanism (B) also consumed the go-around: `goaround0` spent **752 of 945
samples at rest** and never re-entered the staging circle, so the run ended
`FAILED_RETURNING_TO_STAGING` with one of two go-arounds spent.

**What did move.** No leg entered the shuffle regime (0, 1 and 0 reversals
after entry, against the pre-registered threshold of 3), and localization
stayed at **rms 0.065 m / max 0.106 m** — against the 0.661 m §8.5 measured
during the shuffle, and comfortably inside the 0.263 m `footprint_padding` is
dimensioned from. The shuffle and its localization excursion are gone; what
replaced them is a stall.

**Nothing was changed after this run.** r2-r5 were run at identical settings,
because one draw is not a distribution (`docs/LESSONS.md` 2026-08-05) and
re-tuning after run 1 would destroy the very measurement this brief exists to
take.

### r2, r3, r5 — the clean shape

Three runs of the five are clean in the strict sense: REACHED, zero go-arounds,
no leg in the shuffle regime, **12.57-16.42 s over both legs**. Their final legs
are 6.31 s each and the mechanism column is unambiguous — entry headings
**−1.46, −1.78 and +5.44 deg**, all inside the 8.594 deg discriminator. The
final-leg plan in every one is 0 cusps and 0.0 % reverse: a straight run-in,
tracked once, with no correction attempted.

### r4 — REACHED, but through the shuffle the design exists to remove

r4 entered the position circle at **+16.94 deg** and then reversed direction
**20 times**, well past the pre-registered threshold of 3. It *succeeded*
anyway, at 40.06 s for the final leg. This is the one run that contradicts the
design's prediction, and it is not explained away here: an approach that enters
badly aligned still shuffles, exactly as §8.3 measured, because nothing in this
phase removes the endgame — the phase removes the *need* for it, and when the
approach misses, the need returns.

## 9.4 The go-around bound, fired deliberately

The five repeats above never exhausted the bound (r1 spent one go-around of two
and then failed on the return leg). A bound that is never seen to fire is not
evidence, so it was fired on purpose: the **same route and the same build**,
with `--max-go-arounds 1 --approach-timeout 4`, four seconds being less than
the 6.31 s a clean final leg takes, so every approach must miss.

```
  stage        SUCCEEDED   6.31 s   truth 0.100 m / -2.11 deg
  approach0: TIMEOUT after 4.0 s of simulation time; cancelling
  approach0    CANCELED    4.02 s
  goaround0    SUCCEEDED   5.70 s   truth 0.176 m / -28.56 deg
  approach1: TIMEOUT after 4.0 s of simulation time; cancelling
  approach1    CANCELED    4.02 s
  GO-AROUND BOUND REACHED: 2 approach(es) attempted, 1 go-around(s) allowed
  and spent. Reporting failure rather than continuing to manoeuvre.

RESULT           FAILED_GO_AROUND_BOUND
go-arounds       1 used of 1 allowed   BOUND FIRED
elapsed          20.05 s of simulation time over all legs
```

Artefacts: `evidence/m5-33-a_straight-bound-*`. **The bound is real**: two
approaches were attempted, one go-around was spent, and the run reported
failure at 20.05 s instead of continuing to manoeuvre. It also shows the
go-around itself works — `goaround0` returned to the staging circle in 5.70 s,
which is what r1's stall prevented.

**And it exposes a weakness in the go-around as built.** The return leg is
checked position-only, so the vehicle arrived back at staging pointing
**−28.56 deg** away from the approach axis. A re-approach that begins 28 deg
off the corridor is a worse approach than the first one, which is the opposite
of what a go-around is for. Named here rather than fixed: the fix is a design
decision (a heading-checked return, or a return pose further back), and this
brief may not substitute a design for `ARRIVAL-GEOMETRY.md` §7.

## 9.5 THE DISTRIBUTION — the deliverable, against the done-condition

| | m5-31 baseline (§8.2) | m5-33 staged |
|---|---|---|
| clean traverses | **1 of 5** (13.21 s) | **3 of 5** (12.57, 12.68, 16.42 s) |
| reached at all | 3 of 5 | **4 of 5** |
| did not reach | 2 of 5 (timeouts at 120 s) | 1 of 5 (r1) |
| runs in the shuffle regime | 4 of 5 | **1 of 5** (r4) |
| localization **max** over the set | **0.661 m** | **0.1186 m** |
| localization heading max | 11.32 deg | 5.29 deg |
| slowest completing run | 106.30 s | 46.28 s |

Against the brief's three done-conditions, stated as met or not met and not
softened:

| criterion | result | verdict |
|---|---|---|
| ≥ 4 of 5 **clean** traverses | **3 of 5** | **NOT MET** |
| no run enters the shuffle regime | **r4 did**, 20 reversals | **NOT MET** |
| localization max ≤ 0.263 m across the set | **0.1186 m**, the worst of five | **MET**, with 2.2× margin |

**The distribution moved, and it did not move far enough.** Clean traverses
went 1/5 → 3/5 and shuffling runs 4/5 → 1/5; the 0.661 m localization excursion
§8.5 recorded is gone, replaced by a worst-of-five 0.1186 m that sits well
inside the figure `footprint_padding: 0.27` is dimensioned from, which closes
m5-31 open question 4 for the arrival case. But two of five runs still failed
to arrive cleanly, so **the staged approach as built is not yet the
deterministic arrival `ARRIVAL-GEOMETRY.md` §7 phase 1 promises**, and this
section does not claim it is.

### Why, in one measurement

The m5-31 §8.3 discriminator reproduces **5 out of 5**, without a single
exception:

| run | final-leg entry heading | inside 8.594 deg? | outcome |
|---|---|---|---|
| r2 | −1.46 deg | yes | clean, 6.31 s final leg |
| r3 | −1.78 deg | yes | clean, 6.31 s final leg |
| r5 | +5.44 deg | yes | clean, 6.31 s final leg |
| **r1** | **+10.87 deg** | **no** | stalled, go-around, failed |
| **r4** | **+16.94 deg** | **no** | 20-reversal shuffle |

So the mechanism is exactly the one §8.3 named, and the staged approach acts on
it in the right direction but not decisively: it narrowed the arrival-heading
spread from m5-31's **−16 to +37 deg** down to **−1.8 to +16.9 deg**, and put
three of five inside ±2 deg — but it did not force every approach inside the
window.

**What the staging scatter does and does not explain.** The staging stop is
almost entirely *lateral*, as §9.1 (A) found, and the five stops measure:

| run | staging stop error, longitudinal | **lateral** | outcome |
|---|---|---|---|
| r1 | −0.020 m | **+0.253 m** | failed |
| r2 | −0.011 m | **+0.231 m** | **clean** |
| r3 | +0.067 m | −0.096 m | clean |
| r4 | +0.048 m | **−0.145 m** | shuffled |
| r5 | +0.067 m | −0.095 m | clean |

The tempting story — a large lateral offset causes the miss — **is not
supported at n = 5**: r2 started 0.231 m off, all but r1's offset, and was
clean. Stated as the sample it is rather than as a bound (`docs/LESSONS.md`
2026-08-04): the lateral scatter is real, it spans 0.40 m peak to peak, and on
this evidence it does not by itself determine the outcome. What determines the
outcome is the heading the final leg delivers, and the residual variance in
that is not accounted for by these five runs.

## 9.6 What this section asks the next brief to decide

Three findings that are new here, none of them actionable inside this brief's
`forbidden` list, and none of them a tolerance change:

1. **The terminal stall (§9.1 B) is a mechanism this project had not seen.**
   `cmd_v` holds at **0.015 m/s** at near-full steer lock and the vehicle does
   not move at all — 20 s of frozen ground truth in r1, and 752 of 945 samples
   at rest in its go-around leg. `min_approach_linear_velocity` is at nav2's
   default 0.05 and the recorded topic is the smoother's output, so where the
   0.015 m/s is formed, and whether it is below this vehicle's breakaway at
   lock, is a measurement nobody has taken.
2. **The go-around returns to staging with an unconstrained heading**
   (−28.56 deg measured, §9.4), so a re-approach can start worse aligned than
   the approach it replaces.
3. **`d = 3.0 m` was derived for a lateral e₀ of 0.35 m, and the measured e₀ is
   lateral by construction.** Either the staging checker's radius or `d` is the
   term to move, and `ARRIVAL-GEOMETRY.md` §4.2 already states the relation
   that ties them — but which one moves is a design decision, and this brief
   was told to build §7 as written rather than substitute for it.

**No tolerance was widened anywhere in this section.** `general_goal_checker`
is byte-identical to its committed form: `xy_goal_tolerance: 0.25`,
`yaw_goal_tolerance: 0.15`.

# 10. FORCING THE ARRIVAL — 2026-08-05 (m5-35)

**Sections 0-9 above are untouched.** Section 9 is the distribution this
section tries to close; section 8 is the diagnosis both answer.

This section is written **as each run lands**, exactly as section 9 was, and
for the same reason: a session limit already destroyed one attempt's
unwritten work today (`docs/LESSONS.md` 2026-08-05, and the 2026-08-04 entry
on dispatch losses). The headings below were written **before the first run
was started**, and each row is appended the moment the run it describes
exists.

| Item | Value |
|---|---|
| Date | **2026-08-05** |
| Host | WSL2 Ubuntu 24.04 on the owner's Windows 11 machine, 20 cores, headless, llvmpipe — the §8/§9 machine |
| Package stack | unchanged since §8. nav2 **1.3.12** |
| Under test | `ARRIVAL-GEOMETRY.md` §9 as written: the creep-deadband fix (§9.1), the 4.5 m final leg (§9.4) and the miss detector (§9.5), with the staging-stop heading instrumented (§9.3) |
| **Tolerances** | **`xy_goal_tolerance: 0.25` and `yaw_goal_tolerance: 0.15` are UNCHANGED**, as they were in §9. Neither was widened. The miss detector *reads* the yaw tolerance; it does not move it |
| Isolation | `GZ_PARTITION=m535r<N>` **and** `ROS_DOMAIN_ID` per run, both set on every run |
| Chain | `warehouse_bringup` -> `localization.launch.py` -> `navigation.launch.py gate:=false cmd_topic:=/cmd_vel_smoothed` — the §8.8/§9.3 chain |
| Route | §5.1's case A, world (−4.5, +7.0) -> station (+1.0, +7.0) yaw 0 — **the same route §8.2 and §9.2 measured** |
| Staging pose | world (**−3.5**, +7.0) yaw 0, i.e. **`d = 4.5`** m back along the goal heading (§9.4; §9's d was 3.0, staging at −2.0) |
| Go-around bound | `--max-go-arounds 2`, unchanged |
| Approach timeout | 45 s of simulation time, unchanged — now the **backstop behind** the miss detector rather than the thing that detects a miss |

## 10.0 What was verified before the first run

### (a) The three changes, and that they are the ones §9 specifies

| file | change | authority |
|---|---|---|
| `config.yaml` | `navigation.creep_speed_mps: 0.02` -> **0.005**, with the admissible-window derivation written into the comment as a FORMULA rather than a number | §9.1 |
| `scripts/nav2_run.py` | the miss detector on approach legs (entry-heading and 2-reversal aborts), the staging-stop heading instrumented, both surfaced in the log and in the JSON | §9.5, §9.3 |
| invocation | `--d 4.5` (the argument already existed; the default stays 3.0) | §9.4 |

Nothing else changed. `nav2.yaml` and the behaviour tree are byte-identical
to their §9 form; no dependency was added; `opennav_docking` was not
activated.

### (b) THE DEADBAND SWEEP — every floor in the chain, not only the one that bit

The §9.1 deadlock is a relation between **two floors**, so fixing it means
checking that no *other* pair stands in that relation afterwards. The chain
from the controller to the plant was read stage by stage:

| stage | floor it imposes | after this build |
|---|---|---|
| RPP `min_approach_linear_velocity: 0.05` | a floor on the **requested** speed, above the smoother | never reaches the plant; the smoother's from-rest ramp forms the command |
| `velocity_smoother`, `CLOSED_LOOP` + `scale_velocities` | from rest emits at most `max_accel*dt` on the tightest axis: `v_pinned(κ) = min(0.025, 0.02381/κ)`, whose minimum over the reachable range is **0.00667 m/s** at the mechanical steer stop (κ_max = tan(1.31)/1.05 = 3.569 1/m) | unchanged — this is the layer that *produces* the smallest command |
| `envelope_gate.py` | `zero_speed_mps` (0.002), but **only inside `ramp_towards_zero`**, i.e. on the stop ramp; the permissive path has no deadband | not in this chain at all (`gate:=false`), and would not deadlock if it were |
| `cmd_vel_to_tricycle.py` creep deadband | **zeroes traction** below it — the deadlocking floor | **0.005 m/s**, which is below 0.00667, so no command the smoother can form from rest is zeroed |
| `cmd_vel_to_tricycle.py` `zero_speed_mps` (0.002) | classifies a **refusal**; it gates nothing, because the creep branch has already decided the traction | unchanged; semantics untouched |
| `forklift_io.py` | a symmetric clamp at ±1.50 m/s and nothing else — **no deadband** | unchanged |
| gz `JointController` on `drive_wheel_joint` | raw velocity command, no ramp, no deadzone | unchanged |

**Stated explicitly, because it is the thing that could have been moved
rather than removed: after this build no pair of floors in the chain stands
in the deadlock relation.** The only deadband that zeroes traction (0.005)
sits below the smallest command the layer above it can produce from rest
(0.00667), with the refusal threshold (0.002) below that again. The one
floor left unmeasured is the **plant's own breakaway**, which is not a
parameter of ours: if the vehicle physically cannot move at the tread speed
0.00667 m/s implies, the symptom returns with **nonzero traction commanded**,
and that is what falsifier 2 below is read against.

### (c) THE CONVERTER BENCH, run before any simulator (§9.6)

The smoother's from-rest output at r1's recorded steer of 1.072 rad, fed to
the real converter node under both deadbands. Artefact:
`evidence/m5-35-creep-bench.txt`.

```
kappa = tan(1.072)/1.05 = 1.7483 1/m
the smoother's from-rest output at that curvature: a_w*dt/kappa = 0.02381/1.7483 = 0.01362 m/s
the config file in the tree says creep_speed_mps = 0.005

COMMITTED deadband (m5-33)     creep 0.0200 m/s  in v +0.01362 m/s w +0.02381 rad/s
                               ->  steer +1.0720 rad  traction +0.00000 m/s   refusals 0
CHANGED deadband (this build)  creep 0.0050 m/s  in v +0.01362 m/s w +0.02381 rad/s
                               ->  steer +1.0720 rad  traction +0.02847 m/s   refusals 0

VERDICT: the committed deadband zeroes traction and the changed one does not
```

Three things are established by it, none of them needing a simulator:

1. **The §9.1 derivation is arithmetic, not a story.** The predicted
   0.0136 m/s comes out as **0.01362 m/s**, against r1's recorded held
   command of 0.015 m/s — one sample quantum apart.
2. **The committed build zeroes traction on that exact command** while
   holding the steer axis at +1.0720 rad, which is every recorded symptom of
   §9.3 r1 reproduced on a bench in seconds.
3. **The changed build passes it**: +0.02847 m/s of drive-wheel tread, which
   is `v/cos(1.072)`, the conversion's own formula. The refusal counter
   stays at 0 in both, confirming this was never the refusal branch.

### (d) The machine, alone

Recorded per run in §10.3 below, by the driver rather than by the operator:
the driver refuses to start if anything matching the simulator/Nav2 process
patterns is running, prints load, `/dev/shm` count and a UTC timestamp before
the run, and verifies the remaining process count after it.

## 10.1 The five repeats

Same route, same chain, same way §8.2 and §9.2 did them. Rows are appended as
each run lands.

**"Clean" means what it meant in §9.2**: REACHED, with zero go-arounds used
and no leg in the shuffle regime. **An aborted approach is NOT clean.** The
shuffle test is unchanged and still pre-registered (`_SHUFFLE_REVERSALS = 3`,
`_MOVING_MPS = 0.02`); it was deliberately *not* re-tied to the new creep
deadband, because a pre-registered test whose definition moves between the
runs it compares is not a test.

| run | outcome | go-arounds | approaches | miss aborts | shuffle regime | staging-stop heading (believed / truth) | final approach: entry heading | localization max |
|---|---|---|---|---|---|---|---|---|
| **r1** | FAILED_RETURNING_TO_STAGING | 1 of 2 | 1 | **YES: approach0** (entry) | **NO** | **-6.471 / -7.406 deg** | **+27.46 deg** | **0.4565 m** |
| **r2** | **REACHED (clean)** | 0 of 2 | 1 | none | **NO** | **-2.739 / -3.024 deg** | **+2.93 deg** | **0.1414 m** |
| **r3** | **REACHED (clean)** | 0 of 2 | 1 | none | **NO** | **-9.758 / -9.554 deg** | **+6.57 deg** | **0.1141 m** |
| **r4** | FAILED_RETURNING_TO_STAGING | 1 of 2 | 1 | **YES: approach0** (entry) | **NO** | **-10.440 / -9.040 deg** | **+33.37 deg** | **0.4045 m** |
| **r5** | FAILED_GO_AROUND_BOUND | **2 of 2, BOUND FIRED** | 3 | **YES: approach0, approach1** (entry) | **NO** | **+0.265 / +0.561 deg** | **+17.12 deg** (approach0); approach1 **+34.14 deg**; approach2 never entered | **0.3698 m** |

## 10.2 What each run did, recorded before the next was started

### r1 — the miss detector fired; the go-around then failed on its own leg

Run window 2026-08-05T16:33Z to 16:40Z, machine verified alone before
(`load 0.00`, `/dev/shm` 165 from the previous session's orphaned Fast-DDS
segments, **zero** matching processes) and torn down to **zero** processes
after.

**The stall is gone, and the recording proves it rather than asserting it.**
The falsifier-2 test, run over the whole CSV of both r1s:

```
m5-35 r1   frozen truth >= 5 s with nonzero cmd_v      : none
           frozen truth >= 5 s with nonzero TRACTION   : none
           samples commanded in 0.005-0.02 m/s: 30 (29 with nonzero traction)

m5-33 r1   frozen truth >= 5 s with nonzero cmd_v      : 75.8-95.6 s, 131.2-146.2 s,
                                                         146.4-161.4 s, 161.6-176.6 s,
                                                         181.6-190.0 s
           frozen truth >= 5 s with nonzero TRACTION   : none
           samples commanded in 0.005-0.02 m/s: 857 (0 with nonzero traction)
```

That is the deadlock and its removal in one table. Under the committed
deadband, **857 samples** were commanded into the 0.005-0.02 m/s band and
**not one of them reached the plant**; the truth froze for 19.8 s and then
for three further windows. Under the changed deadband, 29 of 30 such samples
produce traction and no freeze of 5 s or longer occurs anywhere in the run.
**Note the second row of each block**: neither run has a freeze with nonzero
*traction*, so falsifier 2 as literally worded (`nonzero cmd_v`) fires on the
m5-33 recording it was written from. The form that discriminates is the one
with the converter's output in it, and both are reported here for that
reason.

**What failed instead, and it is not the stall.** The final leg tracked out
of the corridor rather than converging into it. The vehicle left staging at
truth yaw **-7.41 deg**, ran the 4.7 m plan at 0.6 m/s, and arrived beside
the station rather than at it: at t = 51.8 s ground truth was
(+1.230, +7.383), i.e. **0.38 m to the left of the goal line with the
position circle never entered**. It then overshot to x = +1.89, reversed
through a large arc that swung the heading to +1.29 rad, and only on the way
back did it first enter the 0.25 m circle — at **+27.46 deg**, at which point
the detector abandoned the approach, as designed. The go-around leg was then
**ABORTED by Nav2** at 69.71 s having reached (0.525 m, +44.66 deg) from
staging, so the run ended `FAILED_RETURNING_TO_STAGING` with one go-around
spent.

**Localization**: rms 0.1725 m, **max 0.4565 m**, which is **above** the
0.263 m criterion — the first run of the set already breaches it, and the
excursion belongs to the large reverse manoeuvre, exactly the coupling §8.5
measured.

**Nothing was changed after this run.** r2-r5 were run at identical
settings. One draw is not a distribution (`docs/LESSONS.md` 2026-08-05), and
re-tuning after run 1 would destroy the measurement.

### r2 — the clean shape at d = 4.5, and the leg cost the design predicted

Machine verified alone (`load 0.45`, zero matching processes), torn down to
zero. **REACHED, clean**: no go-around, no abort, no leg in the shuffle
regime, 16.61 s over both legs. The final leg took **9.16 s** for 4.5 m,
against the ~9.5 s 9.6 predicted from the clean 3 m leg's 6.31 s, and it
entered the circle at **+2.93 deg** - inside the window, from a staging stop
whose heading was **-3.02 deg** (truth). Localization max **0.1414 m**,
inside the criterion.

### r3 — clean from the worst staging heading of the set so far

Machine verified alone (`load 0.79`, zero matching processes), torn down to
zero. **REACHED, clean**, 18.16 s over both legs, final leg 8.61 s. It is
the informative row of the three so far: the vehicle arrived at staging
**-9.55 deg** off the approach axis (truth) with a **-0.2412 m lateral**
residual, i.e. outside the 8.594 deg window at staging and with essentially
the whole staging tolerance spent laterally - and the 4.5 m leg still
delivered a **+6.57 deg** entry, inside the window, and a clean arrival.
That is the tail doing the work the settling model says it does.

### r4 — the same failure shape as r1, and the go-around leg is where it ends

Machine verified alone (zero matching processes), torn down to zero. The
load average at start was **1.85**, the highest of the set, the previous
run's teardown still draining; recorded because it is the one between-run
difference this session did not control.

r4 repeats r1 shape for shape: the staging stop was **-9.04 deg** (truth)
with a **-0.2747 m longitudinal** residual, the final leg missed the
corridor rather than converging into it, the first entry into the position
circle came at **+33.37 deg** on the way back from an overshoot, the
detector abandoned the approach, and the go-around leg was then **ABORTED
by Nav2** at 48.72 s, ending 0.659 m and -67.34 deg from staging.
Localization max **0.4045 m**, again above the 0.263 m criterion and again
belonging to the large manoeuvre rather than to the approach.

Two of the four runs so far therefore fail in the same way, and it is
**not** the failure §9 was built against: no stall, no shuffle, no in-circle
correction. It is the final leg leaving the corridor.

### r5 — the run that decides the attribution: a perfect staging heading, and the leg still missed

Machine verified alone (`load 2.08`, zero matching processes), torn down to
zero. r5 arrived at staging **+0.56 deg** off the approach axis (truth) with
a 0.059 m lateral residual — the best-aligned staging stop of the five — and
the 4.5 m leg **still** put the vehicle 0.41 m below the goal line and
entered the circle at **+17.12 deg**. The detector abandoned it; the
go-around returned to staging (69.45 s); the second approach entered at
**+34.14 deg**, *worse than the first*; the second go-around returned; and
the third approach was **ABORTED by Nav2 at 4.74 m from the goal**. The
bound then fired, correctly: three approaches attempted, two go-arounds
spent, failure reported at 141.74 s rather than continued manoeuvring.

**This is the run that settles §9.3's question.** The staging-stop heading
column exists to say whether the entry-heading variance is *inherited* from
staging or *generated on the leg*. r5 inherits nothing — it starts on the
axis — and generates 17 deg. The answer is: **generated on the leg.**

## 10.3 How this section was run

Identical in discipline to §9.3, one driver invocation per repeat. The
driver refuses to start if anything matching
`gz sim|nav2|amcl|controller_server|bt_navigator|parameter_bridge|planner_server|velocity_smoother|robot_state_publisher|ekf_node|cmd_vel_to_tricycle|forklift_io|wheel_odometry|imu_gate`
is running, prints the load, the `/dev/shm` count and a UTC timestamp
before the run, gates each bring-up stage on a topic appearing rather than
on a fixed sleep (`/forklift/odom`, then `/particle_cloud`, then `/plan`),
and verifies the remaining process count after teardown. **All five runs
started with zero matching processes and ended with zero.**

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=m535r<N> ROS_DOMAIN_ID=9<N>     # BOTH, every run
unset DISPLAY WAYLAND_DISPLAY                        # headless, llvmpipe

ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
ros2 launch agv/forklift/launch/localization.launch.py \
    initial_pose_x:=1.584770 initial_pose_y:=12.576859 initial_pose_yaw:=-0.007915
ros2 launch agv/forklift/launch/navigation.launch.py \
    gate:=false cmd_topic:=/cmd_vel_smoothed

# THE ONE ARGUMENT THAT DIFFERS FROM 9.3: --d 3.0 -> --d 4.5.
python3 agv/forklift/scripts/nav2_run.py stage \
    --x 1.0 --y 7.0 --yaw 0.0 --d 4.5 --max-go-arounds 2 \
    --settle 30 --staging-timeout 90 --approach-timeout 45 \
    --csv  evidence/m5-35-a_straight-r<N>-run.csv \
    --plan evidence/m5-35-a_straight-r<N>-plan.json

python3 agv/forklift/scripts/nav2_run.py analyse \
    --csv  evidence/m5-35-a_straight-r<N>-run-approach.csv \
    --plan evidence/m5-35-a_straight-r<N>-plan.json
```

Per-run load average at start, recorded because it is the one between-run
difference this session did not control: r1 0.00, r2 0.45, r3 0.79,
r4 1.85, r5 2.08 (each run's teardown still draining into the next). It
does **not** order the outcomes: r1 failed from the quietest machine of the
five and r3 was clean from a busier one. Artefacts per run:
`evidence/m5-35-a_straight-r<N>-{run.csv,run-approach.csv,plan.json,stage.txt,analyse.txt}`,
plus `evidence/m5-35-creep-bench.txt`.

## 10.4 THE DISTRIBUTION — against the done-condition, not softened

| criterion | result | verdict |
|---|---|---|
| >= 4 of 5 **clean** traverses | **2 of 5** (r2, r3) | **NOT MET** |
| no run enters the shuffle regime | **none did**, 0 of 5 | **MET** — and partly *by construction*, as §9.5 declared in advance: three runs were abandoned by the miss detector before any in-circle correction could begin |
| localization max <= 0.263 m across the set | **0.4565 m** (r1); r4 0.4045 m and r5 0.3698 m also breach it | **NOT MET** |

| | m5-31 (§8.2) | m5-33, d = 3.0 (§9.2) | **m5-35, d = 4.5** |
|---|---|---|---|
| clean traverses | 1 of 5 | **3 of 5** | **2 of 5** |
| reached at all | 3 of 5 | 4 of 5 | **2 of 5** |
| runs in the shuffle regime | 4 of 5 | 1 of 5 | **0 of 5** |
| localization max over the set | 0.661 m | **0.1186 m** | **0.4565 m** |
| terminal stalls | — | 1 of 5 (r1) | **0 of 5** |

**Stated plainly: the distribution did not close, and on two of the three
criteria this build is worse than the one it replaces.** The shuffle is gone
and the stall is gone; what remains is a third failure mode that neither
§8's diagnosis nor §9's design addresses, and the localization excursions
come back with it because a failed approach manoeuvres.

### THE MECHANISM, measured rather than inferred

The failing runs do not stall, do not shuffle and are not badly aligned at
staging. **They drive out of the corridor.** Ground-truth cross-track from
the y = 7.0 approach line, measured over the OUTBOUND part of the first
approach only — every sample up to the first commanded reversal, so no
recovery manoeuvre is counted:

| set | run | cross-track at the end of the outbound run | outcome |
|---|---|---|---|
| m5-33 (d = 3.0) | r1 | **-0.340 m** | failed |
| m5-33 | r2 | +0.220 m | clean |
| m5-33 | r3 | -0.148 m | clean |
| m5-33 | r4 | **-0.416 m** | shuffled (not clean) |
| m5-33 | r5 | +0.167 m | clean |
| **m5-35 (d = 4.5)** | r1 | **+0.550 m** | failed |
| **m5-35** | r2 | +0.150 m | **clean** |
| **m5-35** | r3 | +0.202 m | **clean** |
| **m5-35** | r4 | **-0.583 m** | failed |
| **m5-35** | r5 | **-0.409 m** | failed |

**A cross-track above the 0.25 m position tolerance at the end of the
outbound run separates clean from not-clean 10 times out of 10, across both
sets.** It is a sharper discriminator than the entry heading, and it is
upstream of it: a vehicle that passes the station further than `xy_tol` to
one side never enters the position circle on its outbound run at all, so
everything that follows — the overshoot, the reverse arc, the late entry at
17-33 deg — is *recovery*, and the entry heading measures the recovery
rather than the approach.

**And this is why lengthening the leg was the wrong lever.** The cross-track
is not a decaying transient; it is a rate. In r5 the vehicle held a
sustained heading of about -6.6 deg for the whole leg while its belief error
stayed under 0.126 m, so the offset accumulated at roughly 0.10 m per metre
travelled. The §9.4 settling model assumed the *heading* error decays with
tail length, which it may; what integrates along the tail is the *lateral*
error, and 4.5 m of it buys 50 % more cross-track than 3.0 m did. The
measured means bear it out: mean terminal |cross-track| went from 0.258 m at
d = 3.0 to 0.379 m at d = 4.5.

The plans are not the cause and were checked before the controller was
blamed: every approach plan is straight to within 0.014-0.096 m of its own
chord and every one ends at y = +7.000 exactly. Localization is not the
cause either: belief-versus-truth error during the approach legs peaked at
0.114-0.199 m, well under the 0.4-0.66 m excursions.

### A SECOND NEW MECHANISM: the go-around cannot always be planned

Two of the four go-arounds attempted (r1, r4) and r5's third approach ended
`ABORTED` by Nav2, and the planner log says why:

```
[planner_server] GridBased plugin failed to plan from (2.04, 11.67) to (2.58, 12.57): "Start occupied"
[bt_navigator] Goal failed
```

A miss that ends beside the station leaves the vehicle in a pose the global
costmap scores as **occupied**, and no path can be planned *from* it. §9.2
provisioned the go-around for a bad return **heading**; the precondition it
actually lacks is a **plannable start pose**. The same log carries a
standing configuration warning, pre-existing and not introduced here:
`inflation radius (0.550000) is smaller than the circumscribed radius
(2.230050)`, which both slows SE2 collision checking and makes a
0.4 m-off-line pose next to a rack likely to read as occupied.

## 10.5 THE REGISTERED PREDICTIONS, scored — including the ones that failed

§9.7 registered a per-run prediction and four falsifiers **before** this run
existed. Scored honestly, because a design that predicted wrongly and says
so is worth more than one that reports outcomes only.

| §9.7 prediction | outcome | verdict |
|---|---|---|
| **5 of 5** first-approach clean (point prediction) | 2 of 5 | **WRONG** |
| r2/r3/r5-analogues clean, entries within ±6 deg | two clean at +2.93 and +6.57 deg; the third run of that group failed | **PARTLY** |
| r4-analogue clean at ≈ +7 deg — *the settling model's own test row* | no run converted a large entry into a small one; three entered at +17.12, +27.46 and +33.37 deg | **WRONG** |
| r1-analogue: **no stall anywhere** | no freeze of >= 5 s with nonzero traction in any of the five runs; and none with nonzero `cmd_v` either | **RIGHT** |
| a residual miss aborts immediately and completes via one provisioned go-around | the abort half held exactly — every abort fired at the first in-circle sample; the completion half did not — **no** go-around ever produced a clean arrival, and two could not even be planned | **HALF RIGHT** |
| localization ≈ 0.12 m, criterion 0.263 m | 0.114-0.457 m; three runs breach the criterion | **WRONG** |

| §9.7 falsifier | fired? | what it kills |
|---|---|---|
| 1. any final-leg entry outside 8.594 deg | **FIRED**, 3 of 5 (+17.12, +27.46, +33.37 deg) | **the §9.4 settling model is falsified.** The staging-heading column then decides the follow-up, and it does: see below |
| 2. ground truth frozen >= 5 s with nonzero `cmd_v` | **did not fire** in any of the five | **§9.1's derivation stands**, and is independently confirmed by the bench of §10.0 (c) and by the 857-vs-30 band comparison of §10.2 |
| 3. a re-approach entering worse than its first attempt | **FIRED** — r5's approach1 entered at +34.14 deg against approach0's +17.12 deg | **the §9.2 capacity argument is falsified.** Extra leg length does not make a re-approach better than the approach it replaces |
| 4. a clean-shaped run killed by an abort | **did not fire** — every abort was an entry at 17-33 deg, nowhere near the 8.594 deg window, and no aborted leg had reached even one reversal | **the §9.5 thresholds are sound as derived**; the aborts cost no clean run |

**Falsifier 1 fired, and §9.3's instrumentation answers the question it
raises.** The staging-stop heading, per run against the entry it produced:

| run | staging-stop heading (truth) | first-approach entry heading | outcome |
|---|---|---|---|
| r1 | -7.41 deg | +27.46 deg | failed |
| r2 | -3.02 deg | +2.93 deg | **clean** |
| r3 | **-9.55 deg** | +6.57 deg | **clean** |
| r4 | -9.04 deg | +33.37 deg | failed |
| r5 | **+0.56 deg** | +17.12 deg | failed |

There is no relation. The **worst** staging heading of the set (r3, -9.55
deg, outside the arrival window and with its whole tolerance spent
laterally) produced a clean arrival; the **best** (r5, +0.56 deg, on the
axis) produced a 17 deg miss. So the entry-heading variance is **generated
on the final leg, not inherited from staging** — which is exactly the
disjunction §9's open question 2 posed, now decided by measurement. The
lever is therefore neither the staging pose nor the leg length: it is
tracking on the leg.

## 10.6 What this section asks the next brief to decide

The done-condition is **not met** and this section does not tune to reach
it. `xy_goal_tolerance: 0.25` and `yaw_goal_tolerance: 0.15` are
byte-identical to their committed form, as they have been through §8, §9 and
§10, and no threshold in the miss detector touches either.

What remains, named:

1. **The cross-track rate on a straight leg is the unsolved quantity.** A
   sustained heading offset of a few degrees, held for the length of the
   leg, is what puts the vehicle beside the station. It must be *measured*
   before anything is changed: the understeer-at-small-angles measurement
   §6 already asks for is the first candidate, the converter's steer-angle
   fidelity at small commands the second, and RPP's lack of any cross-track
   term the third. This is a controller question, and it is the first one
   in this whole line of work that is.
2. **`d` is not the lever, and 4.5 m is worse than 3.0 m.** On the evidence
   here the shorter leg should be restored unless a cross-track fix lands
   first, because the error integrates along the leg.
3. **The go-around needs a plannable start, not just a heading.** Three legs
   died on `"Start occupied"`. A retry that cannot be planned is not a
   retry, and this is the second time the go-around's *precondition* has
   turned out to be something other than what was provisioned for.
4. The inflation-radius warning (`0.55` against a circumscribed `2.23`) is
   pre-existing, is logged on every run, and has never been ruled on.

**What this section does establish, and it is not nothing.** The terminal
stall is gone by derivation and by measurement: 0 of 5 runs stalled, against
1 of 5 before, and the bench shows the mechanism switching off at the
converter. The shuffle regime is gone: 0 of 5, against 1 of 5 and 4 of 5
before it. The miss detector works exactly as designed and cost no clean
run. And the staging-stop instrumentation answered the attribution question
that two previous sections could only argue about.

---

# 11. THE CROSS-TRACK RATE — 2026-08-05 (m5-38)

**Sections 0-10 above are untouched and byte-identical.** Section 10 asks
for exactly one thing (§10.6 item 1): *measure* the cross-track rate on a
straight leg before changing anything. This section is that measurement.

This section is written **as each result lands**, not assembled afterwards
(`docs/LESSONS.md` 2026-08-04, 2026-08-05: a session limit destroyed one
agent's unwritten work).

| Item | Value |
|---|---|
| Date | **2026-08-05** |
| Host | WSL2 Ubuntu 24.04 on the owner's Windows 11 machine, 20 cores, headless, llvmpipe — the §8/§9/§10 machine |
| Package stack | unchanged since §8. nav2 **1.3.12** |
| **Tolerances** | **`xy_goal_tolerance: 0.25` and `yaw_goal_tolerance: 0.15` are UNCHANGED**, as through §8, §9 and §10 |
| Isolation | `GZ_PARTITION` **and** `ROS_DOMAIN_ID`, both set on every run |

## 11.1 The sign, established first — it is not a bias

The brief asks for the sign first, because a consistent sign is a bias and a
random sign is not. **The sign is not consistent.** Signed ground-truth
cross-track rate over the outbound part of the first approach leg — the same
window §10.4 measured, every sample up to the first commanded reversal, so
no recovery manoeuvre is counted. Artefact:
`evidence/m5-38-offline-cross-track.txt`.

| set | run | y−7 at leg start | y−7 at leg end | **signed rate [m/m]** | mean yaw [deg] | outcome |
|---|---|---|---|---|---|---|
| m5-33 (d = 3.0) | r1 | +0.253 | −0.340 | **−0.1966** | −6.65 | failed |
| m5-33 | r2 | +0.231 | +0.220 | −0.0037 | +1.02 | clean |
| m5-33 | r3 | −0.096 | −0.148 | −0.0164 | −1.32 | clean |
| m5-33 | r4 | −0.145 | −0.416 | **−0.0922** | −4.63 | shuffled |
| m5-33 | r5 | −0.095 | +0.167 | **+0.0868** | +2.85 | clean |
| m5-35 (d = 4.5) | r1 | +0.025 | +0.550 | **+0.0927** | +3.06 | failed |
| m5-35 | r2 | +0.009 | +0.150 | +0.0288 | +0.58 | clean |
| m5-35 | r3 | −0.241 | +0.202 | **+0.0970** | +1.79 | clean |
| m5-35 | r4 | +0.084 | −0.533 | **−0.1271** | −6.27 | failed |
| m5-35 | r5 | +0.059 | −0.409 | **−0.1007** | −4.00 | failed |

```
n = 10   negative 6   positive 4
mean  -0.0231 m/m      mean of |rate|  0.0842 m/m      sd  0.1026 m/m
the mean is 0.71 standard errors from zero
```

**Six one way, four the other, and a mean indistinguishable from zero
against a magnitude of 0.084 m/m.** This halves the search exactly as the
brief said it would, and it eliminates the whole bias family in one
measurement: **no steady steer trim, no estimator heading bias, no
converter sign asymmetry and no left/right asymmetry in the model can
produce a quantity whose magnitude is reproducible and whose sign is a coin
flip.** Whatever this is, it *amplifies a disturbance the vehicle already
has* rather than injecting one of its own.

That reframes the question. It is not "what is pushing the vehicle off the
line", it is **"why does the controller's correction not bring it back"**.

## 11.2 THE STATIC CURVE, from the ten committed recordings

The correction is not brought back because **the vehicle does not execute
it.** Commanded steer is the `steer` column — what `cmd_vel_to_tricycle.py`
published. Achieved steer is inferred from ground truth alone,
`δ_ach = atan(L·ω/v)`, which is the same bicycle relation the converter
inverts, read the other way. Pooled over every sample of all ten runs with
|v| > 0.20 m/s. One sample of actuator lag is removed; the lag was
identified by sweep rather than assumed (rms of `δ_ach − δ_cmd`: 2.518 deg
at lag 0, **2.456 at lag 1**, 2.816 at lag 2, rising monotonically after —
so the transport lag is one sample, ~0.1 s, and it is not the mechanism).

| commanded [deg] | n | mean cmd | mean achieved | **achieved / commanded** |
|---|---|---|---|---|
| −90 .. −40 | 96 | −48.888 | −48.911 | **1.000** |
| −40 .. −25 | 105 | −32.303 | −33.392 | 1.034 |
| −25 .. −15 | 77 | −20.238 | −20.536 | 1.015 |
| −15 .. −8 | 103 | −10.961 | −9.918 | 0.905 |
| −8 .. −4 | 113 | −5.511 | −4.478 | 0.813 |
| −4 .. −2.5 | 67 | −3.199 | −1.770 | 0.553 |
| −2.5 .. −1.5 | 117 | −1.866 | −0.693 | **0.372** |
| −1.5 .. −0.75 | 136 | −1.122 | −0.076 | **0.068** |
| −0.75 .. −0.25 | 68 | −0.504 | −0.309 | 0.614 |
| −0.25 .. +0.25 | 56 | −0.021 | +0.154 | — |
| +0.25 .. +0.75 | 71 | +0.519 | −0.152 | **−0.292** |
| +0.75 .. +1.5 | 155 | +1.186 | +0.034 | **0.029** |
| +1.5 .. +2.5 | 203 | +1.973 | +0.607 | **0.308** |
| +2.5 .. +4 | 134 | +3.078 | +2.512 | 0.816 |
| +4 .. +8 | 108 | +6.048 | +5.585 | 0.923 |
| +8 .. +15 | 131 | +11.433 | +10.808 | 0.945 |
| +15 .. +25 | 143 | +20.198 | +20.126 | 0.996 |
| +25 .. +40 | 177 | +32.021 | +32.432 | 1.013 |
| +40 .. +90 | 146 | +50.021 | +48.552 | 0.971 |

**Above ~15 deg the vehicle executes what it is told, to within 3 %. Below
~2 deg it executes essentially nothing, on both sides of zero.** That is a
symmetric **deadband of roughly ±2 deg of steer**, and it is exactly the
shape the §11.1 sign result predicts: a deadband has no sign of its own, it
simply refuses to remove whatever error is already there.

**This is the answer to the brief's "a bias a straight line exposes and an
arc hides".** It is not a bias, but the exposure argument is right and it is
geometric: the planner's tightest arc is 45 deg of steer and a mid-aisle
correction is 5-20 deg — all far outside the band. A **straight** line is the
one regime in which every command RPP forms lives inside ±2.5 deg, and it is
therefore the one regime in which the vehicle is effectively open-loop in
yaw.

It is also, quantitatively, the whole of §10.4's finding. Held heading error
θ integrates to cross-track at `sin θ` per metre; the observed 0.084-0.127
m/m is θ = 4.8-7.3 deg, and the §10 runs sat at −6.65, −6.27, −4.63 and
−4.00 deg mean yaw with the steer commanded at +1.5 to +2.2 deg and the yaw
*frozen*. m5-35 r4 is the cleanest single window: over 3.5 s of leg the
command was held at +1.19 to +2.23 deg and ground-truth yaw read −10.85,
−10.97, −11.06, −11.08, −11.06 deg. **Three seconds of sustained command,
zero response.** That is not noise and it is not lag.

And it explains §10's reversal directly. The deadband makes the leg an
integrator with no feedback, so cross-track grows linearly with leg length:
4.5 m buys 50 % more than 3.0 m, which is what the two sets measured
(mean |terminal cross-track| 0.258 m → 0.379 m).

**What this section does NOT yet establish** is *where* the deadband lives.
`δ_ach` is inferred from body yaw, so it conflates two candidates: the steer
joint failing to reach the commanded angle (actuator), and the joint
reaching it while the body fails to yaw (tyre slip at the rear axle, whose
`mu2` is 0.4). §11.3 separates them, because the fix is different for each
and a fix aimed at the wrong one is a green run with an unknown cause.

## 11.3 The decisive experiment: is the deadband in the actuator or in the tyre?

`scripts/steer_bench.py` publishes **straight onto the model's own command
inputs** — `/forklift/gz/steer_cmd` and `/forklift/gz/traction_cmd` — so
Nav2, the smoother, `envelope_gate.py`, `cmd_vel_to_tricycle.py` and
`forklift_io.py` are **all out of the loop**. Anything it measures is the
plant. It reads the steer joint's own angle out of `/forklift/joint_states`
and the body pose out of the ground-truth odometry, so the two candidates
are separated by measurement rather than by argument. Each step carries its
**achieved speed**, so a step the vehicle was blocked for is visibly held
rather than silently scored as an arc (`docs/LESSONS.md` 2026-08-04).

### (a) The joint is not the deadband, and the body is not slipping

Run **c**, warehouse world, one command held long enough to separate a slow
arrival from a refusal to arrive. Artefact:
`evidence/m5-38-steer-bench-c.{csv,txt}`.

```
phase        cmd[deg]  JOINT[deg]   BODY[deg] joint/cmd  body/cmd   v[m/s]
standstill      2.000       1.338         nan     0.669         -    0.000
rolling         2.000       1.621       1.605     0.810     0.803    0.599
```

**The body does exactly what the joint does** — 1.605 deg of implied steer
against 1.621 deg of joint angle, 1 % apart, at a verified 0.599 m/s. So
**tyre slip is not the mechanism**, and §11.2's inference from body yaw was
reading the joint faithfully all along.

**What the joint does is the finding.** A 2 deg step, held, rolling:

```
t+ 0.0 s  +0.70    t+ 3.5 s  +0.98    t+ 7.5 s  +1.56    t+11.0 s  +1.61
t+ 1.0 s  +0.53    t+ 4.5 s  +1.05    t+ 8.5 s  +1.54    t+12.5 s  +1.82
t+ 2.0 s  +0.49    t+ 5.5 s  +1.40    t+ 9.5 s  +1.53    t+13.5 s  +1.62
t+ 3.0 s  +0.93    t+ 6.5 s  +1.25    t+10.5 s  +1.77    final     +1.66
```

**Fourteen seconds of held command and the axis has still not arrived at
two degrees.** The settling time of the steer axis for a small command is of
the order of **ten seconds**. A Nav2 approach leg lasts 8-9 s and RPP
re-forms its command every 50 ms.

### (b) The resisting moment is the tyre's, proven by a one-variable A/B

The two worlds differ in exactly one thing that matters here: in
`sim/worlds/forklift_arena.sdf` the drive wheel **has no grip** — the bench
found it spinning at a commanded 5.000 rad/s with the body at 0.005 m/s,
i.e. 0.6 m/s of tread producing no travel — while in the warehouse the same
command drives the vehicle at 0.600 m/s. Same model, same PID gains, same
joint, same 1.4 s hold, same command sequence. Runs **d** (arena) and **b**
(warehouse). Artefacts: `evidence/m5-38-steer-bench-{b,d}.{csv,txt}`.

| commanded [deg] | **arena** joint/cmd (no grip) | **warehouse** joint/cmd (grip) |
|---|---|---|
| −20.0 | **1.052** | 0.787 |
| −10.0 | **1.026** | 0.548 |
| −5.0 | **1.013** | 0.000 |
| −3.0 | **1.007** | −0.088 |
| −2.0 | **1.006** | 0.039 |
| −1.5 | **1.013** | 0.040 |
| −1.0 | **1.042** | −0.030 |
| −0.5 | **1.191** | −0.099 |
| +0.5 | **0.735** | 0.220 |
| +1.0 | **0.937** | 0.065 |
| +1.5 | **0.980** | 0.095 |
| +2.0 | **0.994** | 0.052 |
| +3.0 | **1.001** | 0.114 |
| +5.0 | **1.008** | 0.393 |
| +10.0 | **1.017** | 0.603 |
| +20.0 | **1.033** | 0.779 |

**Without grip the axis reaches every commanded angle, half a degree
included, inside 1.4 s. With grip it reaches none of the small ones.** The
resisting moment is therefore **contact-borne** — it comes from the tyre,
not from the joint's own damping or friction, and not from the controller.

This also falsifies `model.sdf`'s own documented assumption. The comment
above the steer PID says the scrub "disappears" once the vehicle rolls. It
does not: run **b**'s rolling rows are the same as its standstill rows at
every small angle, at a verified 0.600 m/s.

## 11.4 THE CAUSE, stated once

> **The steer axis has no proportional authority over the tyre's reaction
> moment at small angles, so small steer commands are executed only by
> integral windup, on a ten-second timescale. Nav2's corrections on a
> straight leg are 1 to 2.5 degrees and the leg lasts 8 to 9 seconds, so
> the vehicle executes essentially none of them. Whatever heading error it
> enters the leg with is therefore HELD for the whole leg, and a held
> heading error integrates into cross-track at sin θ per metre — 0.10 m per
> metre at the 5.7 deg the failing runs hold.**

The arithmetic is `model.sdf`'s own. The steer PID's proportional term is
`p_gain · e = 6000 · e` N·m. The comment above that plugin records the
tyre's scrub reaction as **"roughly 400 N m for this vehicle"**, measured.
Proportional torque only exceeds it above

```
e > 400 / 6000 = 0.0667 rad = 3.8 deg
```

and below that the joint waits on the integral, `i_gain 1500`, which needs
`∫e dt = 400/1500 = 0.267 rad·s` — **7.6 s at a 2 deg error**. The
predicted knee at 3.8 deg and the ten-second windup are what §11.2 measured
independently from ten Nav2 runs (`ach/cmd` 0.03 at 1.2 deg, 0.31 at
2.0 deg, 0.82 at 3.1 deg, 0.92 at 6.0 deg, 1.00 above 15 deg) and what
§11.3 (a) measured directly on the joint. **Three independent measurements,
one number.**

**Why the envelope gate's zero residual was never in tension with this.**
The gate passes a Twist through unchanged and that is exactly what it was
measured to do; the loss is two stages below it, between a steer angle
command and a steer joint. Nothing above the converter can see it, which is
why nine sections of diagnosis upstream of the plant found real defects and
never found this one.

**Why a straight line exposes it and an arc hides it, quantitatively.** The
planner's tightest arc is 45 deg of steer and a mid-aisle correction is
5-20 deg — all above the knee, all executed at unity gain. A straight leg is
the only regime in which every command RPP forms lives inside the dead
region, and it is therefore the only regime in which the vehicle is
**open-loop in yaw**.

**Why every previous lever failed, in one line each.** Staging the approach
(§9) fixed the *entry* heading, which the deadband then holds instead of
correcting. Lengthening the leg (§10) added metres to an open-loop
integrator. Widening a tolerance (§8.4, refused twice by the owner) would
have accepted the error rather than removing it. **None of them could have
worked**, and the §10.5 result that the worst staging heading arrived clean
while the best missed by 17 deg is exactly what an open-loop leg predicts:
the outcome is set by the disturbance the vehicle happens to pick up in the
first metre, not by where it started.

## 11.5 The fix, and whether applying it is inside this task

**The lever is the quantity that sets the threshold, and it is one number.**
`e* = M_scrub / p_gain`. Raising the steer PID's proportional gain from
**6000 to 60000** moves the threshold from 3.8 deg to **0.38 deg**, i.e.
below every command RPP forms on a straight leg. That value is not
arbitrary — it is the gain `model.sdf` already gives the mast joint, so the
model gains stay in one family.

Measured, run **e**, the same bench and the same 1.4 s hold as run **b**,
warehouse world, differing from **b** by **exactly one line**
(`diff` verified: `1002c1002`, `<p_gain>6000.0</p_gain>` →
`<p_gain>60000.0</p_gain>`, 1 line changed, nothing else). Artefact:
`evidence/m5-38-steer-bench-e.{csv,txt}`.

| commanded [deg], rolling | joint/cmd **committed** (run b) | joint/cmd **experiment** (run e) | body/cmd (run e) |
|---|---|---|---|
| ±0.5 | 0.220 / −0.099 | 0.094 / **0.232** | 0.095 / 0.234 |
| ±1.0 | 0.065 / −0.030 | **0.525 / 0.595** | 0.523 / 0.596 |
| ±1.5 | 0.095 / 0.040 | **0.677 / 0.728** | 0.676 / 0.726 |
| ±2.0 | 0.052 / 0.039 | **0.761 / 0.789** | 0.759 / 0.789 |
| ±3.0 | 0.114 / −0.088 | **0.838 / 0.860** | 0.835 / 0.859 |
| ±5.0 | 0.393 / 0.000 | **0.899 / 0.914** | 0.894 / 0.912 |
| ±10.0 | 0.603 / 0.548 | **0.948 / 0.956** | 0.934 / 0.950 |
| ±20.0 | 0.779 / 0.787 | **0.974 / 0.981** | 0.943 / 0.951 |

**A 2 deg command goes from 5 % executed to 76 % executed inside 1.4 s**,
and the body follows the joint to within 1 % at every row, so the yaw the
controller asked for is the yaw it gets. The residual shortfall in run **e**
is *settling inside a 1.4 s window*, not a dead region: it falls smoothly
with command size and the only row still collapsed is ±0.5 deg, which is
0.009 m of cross-track per metre — a twelfth of the failing rate and below
the 0.084 m/m this whole investigation is about. **The predicted knee at
0.38 deg is where the measured curve breaks.** No hunting appeared at the
large angles (±20 deg reaches ±19.5 cleanly), which is the failure mode
`model.sdf`'s comment warns about at the other end.

> **So the answer to the brief's question is yes: the drift can be removed,
> and the lever is the steer axis's proportional authority over the tyre's
> reaction moment.**

### Whether applying it is inside this task — it is NOT, and here is why

**The change is not written into `agv/forklift/model.sdf`.** It exists only
as a `/tmp` copy differing by one verified line and passed in with
`model:=`, which is the same discipline §8.4 used for the two tolerance
experiments. Three reasons, and the third is the binding one:

1. **`model.sdf` is the vehicle plant, and every committed motion figure in
   the repository is qualified by it** — `EVIDENCE_ODOMETRY.md`,
   `EVIDENCE_LOCALIZATION.md`, this file's §1-§10, `sim/`'s arena and
   warehouse evidence, and the recorded M4 commissioning showcase. Changing
   the plant inside a diagnosis brief would silently re-qualify all of them.
2. **The gains it changes are recorded in `model.sdf` as measured**, with a
   documented instability at the opposite end (`d_gain 1200` stopped the
   joint responding; joint damping 400 stopped it moving). A ten-fold gain
   change deserves its own bracketing, not a line edit inside another
   brief's scope.
3. **A plant change is a cross-layer consequence and this agent owns one
   layer.** `sim/` re-measures against this model and does not know it moved.

**What is offered instead is the strongest evidence obtainable without
applying it**: the five repeats of §11.6, run on the experimental model by
argument, so the orchestrator can rule on a one-line change that already has
its distribution measured.

## 11.6 The five repeats, on the experimental model, NOT applied

**One variable against §10.** The route, the chain, the goal, the staging
distance `--d 4.5`, the go-around bound, every timeout and the whole
committed configuration are §10.3's exactly; `nav2.yaml`, the behaviour
tree, `config.yaml` and every script in the command chain are byte-identical
to their committed form. **The single difference is the steer `p_gain` in
the model passed with `model:=`.** §10 is therefore the baseline, and it is
deliberately the *harder* geometry: §10.6 item 2 records that d = 4.5 is
worse than d = 3.0, so this set is run on the leg length that amplifies the
defect most.

**Done-condition, from the brief, not softened**: at least 4 of 5 clean, no
run in the shuffle regime, localization max at or below 0.263 m.

| baseline | m5-33 §9 (d = 3.0) | **m5-35 §10 (d = 4.5)** | **m5-38 §11 (d = 4.5, p_gain 60000)** |
|---|---|---|---|
| clean traverses | 3 of 5 | **2 of 5** | *see below* |
| localization max | 0.1186 m | **0.4565 m** | *see below* |

Rows are appended **as each run lands**, before the next is launched.

| run | outcome | go-arounds | approaches | shuffle regime | entry heading | terminal outbound cross-track | localization max |
|---|---|---|---|---|---|---|---|
| **r1** | **REACHED (clean)** | 0 of 2 | 1 | **NO** | **−3.34 deg** | **+0.048 m** (from +0.174, it CONVERGED) | **0.1523 m** |
| **r2** | **REACHED (clean)** | 0 of 2 | 1 | **NO** | **+2.23 deg** | **+0.056 m** (rate +0.0048 m/m) | **0.1082 m** |
| **r3** | **REACHED (clean)** | 0 of 2 | 1 | **NO** | **−2.19 deg** | **+0.035 m** (rate +0.0056 m/m) | **0.1315 m** |
| **r4** | **REACHED (clean)** | 0 of 2 | 1 | **NO** | **−0.57 deg** | **+0.028 m** (rate +0.0126 m/m) | **0.0718 m** |
| **r5** | **REACHED (clean)** | 0 of 2 | 1 | **NO** | **+1.86 deg** | **+0.056 m** (rate +0.0173 m/m) | **0.1068 m** |

### THE DISTRIBUTION, against the done-condition

| criterion | result | verdict |
|---|---|---|
| ≥ 4 of 5 **clean** traverses | **5 of 5** | **MET** |
| no run enters the shuffle regime | **0 of 5**, and this time **not by construction** — the miss detector never fired, so no approach was abandoned before it could shuffle | **MET** |
| localization max ≤ 0.263 m | **0.1523 m** worst of the set (0.0718, 0.1068, 0.1082, 0.1315, 0.1523) | **MET** |

**All three met, on the leg length §10 proved is the worse one.** Against
the two baselines, one variable at a time:

| | m5-31 §8.2 (no staging) | m5-33 §9 (d = 3.0) | m5-35 §10 (d = 4.5) | **m5-38 §11 (d = 4.5, p_gain 60000)** |
|---|---|---|---|---|
| clean traverses | 1 of 5 | 3 of 5 | 2 of 5 | **5 of 5** |
| reached at all | 3 of 5 | 4 of 5 | 2 of 5 | **5 of 5** |
| runs in the shuffle regime | 4 of 5 | 1 of 5 | 0 of 5 | **0 of 5** |
| go-arounds spent | — | 1 | 4 | **0** |
| miss aborts | — | 0 | 3 | **0** |
| localization max | 0.661 m | 0.1186 m | 0.4565 m | **0.1523 m** |
| entry heading, worst | +37.26 deg | +16.94 deg | +33.37 deg | **+2.23 deg** |

### The cross-track rate itself — the quantity the brief asked for

This is the measurement that closes §10.6 item 1, and it is the one that
matters, because the outcome column above could in principle be luck and
this cannot.

| set | terminal outbound cross-track, per run | mean \|rate\| |
|---|---|---|
| m5-33 (d = 3.0) | −0.340, +0.220, −0.148, −0.416, +0.167 m | **0.0791 m/m** |
| m5-35 (d = 4.5) | +0.550, +0.150, +0.202, −0.583, −0.409 m | **0.0893 m/m** |
| **m5-38 (d = 4.5, experiment)** | **+0.048, +0.056, +0.035, +0.028, +0.056 m** | **0.0134 m/m** |

**The rate falls by a factor of 6.7, and the spread collapses from ±0.58 m
to a 0.028-0.056 m band.** Every one of the ten baseline runs ended the
outbound leg somewhere in a 1.13 m-wide scatter; all five of these end
inside 28 mm of each other, and every one is an order of magnitude inside
the 0.25 m tolerance that §10.4 showed separates clean from not-clean ten
times out of ten.

**And r1 is the row that proves the loop is closed rather than merely
quiet.** It began its leg at **+0.174 m** of cross-track — a larger initial
offset than eight of the ten baseline runs — and *converged* to +0.048 m
over the 4.74 m leg, a rate of **−0.0267 m/m** pointing back at the line.
Under the committed plant no run ever converged; the error only ever grew,
because the vehicle could not execute the correction. **This is the
difference between an open-loop leg and a closed one, in one run.**

Mean yaw over the leg fell from −6.65 to +3.06 deg across the baselines to
**−1.40 to +0.83 deg** here, which is the same result read at the cause
rather than at the effect.

## 11.7 How this section was run

### What was changed in the repository, and what was not

**`agv/forklift/model.sdf` is byte-identical to its committed form**; line
1002 still reads `<p_gain>6000.0</p_gain>`, verified after the last run.
`nav2.yaml`, `config.yaml`, the behaviour tree, both launch files,
`cmd_vel_to_tricycle.py`, `envelope_gate.py` and `forklift_io.py` are all
byte-identical. **No tolerance was widened** — `xy_goal_tolerance: 0.25` and
`yaw_goal_tolerance: 0.15` are untouched, as they have been through §8, §9,
§10 and here. No dependency was added, `opennav_docking` was not activated,
and `plc/` and `bridge/` were not touched.

**One file was added**: `scripts/steer_bench.py`, the plant harness §11.3
runs. It is a measurement harness — it closes no loop, holds no goal, and no
launch file that navigates starts it.

The experimental plant is `/tmp/m5-38-exp-model.sdf`, one verified line from
the committed model (`evidence/m5-38-exp-model.diff`), reached with
`model:=`. `warehouse_bringup.launch.py` does not declare a `model`
argument, but a launch configuration set on the command line is visible to
the include (`docs/LESSONS.md` 2026-08-05), so `forklift_bringup`'s own
`model` argument takes it and the committed file is never read for the
spawn. This is the §8.4 pattern: a one-line experiment, diffed after the
run, never written to the tree.

### Isolation and measuring alone

**Enforced by the driver, not remembered by the operator.** Every run
refuses to start unless `pgrep -c -f` over the
`gz sim|nav2|amcl|controller_server|bt_navigator|parameter_bridge|planner_server|velocity_smoother|robot_state_publisher|ekf_node|cmd_vel_to_tricycle|forklift_io|wheel_odometry|imu_gate`
pattern returns **0**, prints load, `/dev/shm` count and a UTC timestamp
before, gates each bring-up stage on a topic appearing rather than on a
sleep (`/forklift/odom`, `/particle_cloud`, `/plan`), and verifies the
remaining count after teardown. **All five route runs and all five bench
runs started with zero matching processes and ended with zero.**

`GZ_PARTITION` **and** `ROS_DOMAIN_ID` were both set on every run —
`GZ_PARTITION=m538r<N>`, `ROS_DOMAIN_ID=9<N>` for the route runs and
`m538<tag>` / `88` for the bench runs — because `gz transport` does not use
DDS and the ROS variable does not isolate the simulator (`docs/LESSONS.md`
2026-07-27).

Per-run starting load, recorded because it is the one between-run difference
not controlled: r1 (machine idle, 0.00 at session start), r2 0.31,
r3 **3.28**, r4 2.10, r5 2.27 — the previous run's teardown still draining.
**It does not order the outcomes**: all five are clean, and r3, from the
busiest machine of the set, is neither the best nor the worst row.
`/dev/shm` grew from 214 to 459 orphaned Fast-DDS segments across the
session, left in place; no figure depends on them.

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=m538r<N> ROS_DOMAIN_ID=9<N>     # BOTH, every run
unset DISPLAY WAYLAND_DISPLAY                        # headless, llvmpipe

# THE ONE ARGUMENT THAT DIFFERS FROM 10.3, and it is the whole experiment.
ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0 \
    model:=/tmp/m5-38-exp-model.sdf
ros2 launch agv/forklift/launch/localization.launch.py \
    initial_pose_x:=1.584770 initial_pose_y:=12.576859 initial_pose_yaw:=-0.007915
ros2 launch agv/forklift/launch/navigation.launch.py \
    gate:=false cmd_topic:=/cmd_vel_smoothed

python3 agv/forklift/scripts/nav2_run.py stage \
    --x 1.0 --y 7.0 --yaw 0.0 --d 4.5 --max-go-arounds 2 \
    --settle 30 --staging-timeout 90 --approach-timeout 45 \
    --csv  evidence/m5-38-a_straight-r<N>-run.csv \
    --plan evidence/m5-38-a_straight-r<N>-plan.json
python3 agv/forklift/scripts/nav2_run.py analyse \
    --csv  evidence/m5-38-a_straight-r<N>-run-approach.csv \
    --plan evidence/m5-38-a_straight-r<N>-plan.json

# THE PLANT BENCH, no Nav2 anywhere in it
ros2 launch sim/launch/warehouse_bringup.launch.py x:=-8.0 y:=7.0 yaw:=0.0 \
    [model:=/tmp/m5-38-exp-model.sdf for run e]
python3 agv/forklift/scripts/steer_bench.py --csv <tag>.csv --speed 0.6 --hold 1.4
python3 agv/forklift/scripts/steer_bench.py --csv <tag>.csv --profile hold \
    --angles 2 --long-hold 14 --speed 0.6          # run c
```

Bench runs: **a** arena / committed model / hold 2.0, **b** warehouse /
committed / hold 1.4, **c** warehouse / committed / 2 deg held 14 s,
**d** arena / committed / hold 1.4 (the exact A/B partner of **b**),
**e** warehouse / experimental / hold 1.4 (the other exact A/B partner of
**b**). Artefacts: `evidence/m5-38-steer-bench-{a,b,c,d,e}.{csv,txt}`,
`evidence/m5-38-offline-cross-track.txt`,
`evidence/m5-38-exp-model.diff`, and per route run
`evidence/m5-38-a_straight-r<N>-{run.csv,run-approach.csv,plan.json,stage.txt,analyse.txt}`.

## 11.8 What this section asks the next brief to decide

1. **Whether to apply the one-line plant change.** It has its distribution
   measured (5 of 5, §11.6) and its mechanism named (§11.4). It is not
   applied here for the three reasons in §11.5, and the first of them needs
   a ruling: **every committed motion figure in `agv/` and `sim/` is
   qualified by the current plant**, and applying this re-qualifies them.
   The honest options are (i) apply and re-measure the affected evidence,
   (ii) apply and mark the affected figures as taken on the prior plant, or
   (iii) leave it and accept the arrival distribution.
2. **`d` should still be restored to 3.0** if the change is applied. §10.6
   item 2 stands on its own evidence; this set used 4.5 only to keep the
   comparison one variable against §10, and a shorter leg is strictly better
   once the leg is closed-loop.
3. **Two `sim/`-owned findings this brief cannot write** (they are in the
   report as requests): the arena floor gives the drive wheel **no
   traction** — 5.000 rad/s of commanded wheel speed against 0.005 m/s of
   travel, §11.3 (b) — which every arena figure involving traction,
   steering effort or tyre behaviour is qualified by; and `model.sdf`'s
   documented claim that the scrub "disappears" once the vehicle rolls is
   **falsified** (§11.3 (b)).
4. **The go-around's `"Start occupied"` precondition (§10.6 item 3) and the
   inflation-radius warning (§10.6 item 4) are untouched here** and remain
   open. Neither fired in any of these five runs, because no run needed a
   go-around — which is not the same as either being fixed.

---
---

# 12. THE PLANT CHANGE, APPLIED AND RE-MEASURED - 2026-08-05 (m5-40)

**Sections 0-11 above are untouched and byte-identical.** Section 11 (m5-38)
diagnosed the cause and proved the fix on a `/tmp` copy passed with
`model:=`; the owner then ruled option (i) of section 11.8 item 1 - apply the
change and re-measure what it invalidates.
`agv/forklift/PLANT-CHANGE-INVENTORY.md` (m5-39) is the authority for what
that means and in what order; this section executes that order and nothing
else.

**Every heading below was written before the run that fills it.** Rows are
appended the moment a run lands, before the next is launched
(`docs/LESSONS.md` 2026-08-05, entry 117).

## 12.0 The change, as applied

| | committed before | committed after |
|---|---|---|
| `model.sdf` steer `p_gain` | 6000.0 | **60000.0** |
| smallest promptly executable steer error `e* = 400 / p_gain` | 3.8 deg | **0.38 deg** |
| the plugin's comment block | argued for 6000, sized `i_max` against it, and claimed the scrub "disappears once the vehicle rolls" | rewritten: states `e*`, why 60000, the two honest limits on it, the falsified claim named as falsified, and what `i_max` now carries |

Nothing else in the file moved: `i_gain`, `d_gain`, `i_max`, `i_min`,
`cmd_max`, `cmd_min`, the joint damping, the geometry, the masses, the
sensors and every topic name are unchanged. The mast joint already ran
`p_gain` 60000, so the model's gains stay in one family.

## 12.1 Run 0 - the committed-tree stamp

Section 11.6's five repeats were taken with `model:=` pointing at a `/tmp`
copy. The inventory (section 4, run 0) records the one formality that owes:
**one run of the committed tree**, no `model:=` anywhere, so the figures
rest on the file the repository carries rather than on a copy that matched
it. Same route, same goal, same `--d 4.5`, same protocol as 11.6 - the only
difference from r1-r5 is that the model argument is gone.

### The pre-run check, and the result

Machine alone, enforced by the driver: matching processes **0** before the
run and **0** after teardown, load 0.08, `/dev/shm` 517,
`2026-08-05T21:09:13Z`. The driver also prints the committed model's
`p_gain` lines before bring-up, so the artefact records which plant it ran:
`<p_gain>60000.0</p_gain>` at line 1046 (steer) and 1091 (mast).

| | m5-38 r1-r5 (`model:=` copy) | **m5-40 r0 (committed tree)** |
|---|---|---|
| outcome | REACHED (clean) x5 | **REACHED (clean)** |
| go-arounds | 0 of 2, every run | **0 of 2** |
| approaches | 1, every run | **1** |
| miss aborts | none | **none** |
| shuffle regime | NO, 0 of 5 | **NO** |
| entry heading | -3.34 .. +2.23 deg | **-1.94 deg** |
| localization max | 0.0718 .. 0.1523 m | **0.1083 m** |
| terminal outbound cross-track | +0.028 .. +0.056 m | **+0.030 m** |
| cross-track rate over the leg | +0.0048 .. +0.0173, r1 -0.0267 m/m | **+0.0007 m/m** |
| absolute goal error (truth) | - | **0.0912 m**, below the 0.1411 m floor |

```
RESULT           REACHED          elapsed 18.95 s of simulation time, 2 legs
final approach   SUCCEEDED        believed 0.1585 m / -2.401 deg
LOCALIZATION     n = 278          position rms 0.0663 m  MAX 0.1083 m
                                  heading  rms 0.84 deg  MAX 1.75 deg
THE PLAN         4.696 m, 0 cusps, 0.0 % reverse
THE DRIVE        truth path 4.682 m, steer commanded max 6.72 deg, 0 refusals
TRACKING         rms 0.0352 m  max 0.0722 m  p95 0.0637 m (upper bound, contains localization)
```

Cross-track was computed from `m5-40-r0-run-approach.csv` by the same
definition section 11.6 used (`gt_y - 7.0` at the first and last sample of
the approach leg, over the leg's ground-truth length). The definition was
checked by re-deriving m5-38 r1 from its committed CSV first:
**+0.174 -> +0.048 m, rate -0.0267 m/m, mean yaw -1.41 deg**, which
reproduces section 11.6's published row.

### What the stamp settles

Section 11.6's figures no longer rest on a `model:=` override. One run of
the committed tree lands **inside the band of the five**, on every column:
clean, no go-around, no shuffle, localization max between r4's 0.0718 and
r1's 0.1523, terminal cross-track inside the 0.028-0.056 m band.

Two things it deliberately does **not** claim. It is **one draw**, so it
stamps the tree rather than re-measuring the distribution
(`docs/LESSONS.md` 2026-08-05, entry 103); the distribution is section
11.6's five, and this run is the evidence that the five describe the
committed file. And its cross-track rate of +0.0007 m/m is the lowest of
the six, which is a draw and not an improvement.

## 12.2 Case B-prime, 6 m astern - RUN FIRST, and why

Section 5.2's second half is the one committed figure whose **conclusion**
the plant change could flip: "reverse is followed to about 2.4 m; beyond
that the heading diverges", n = 1, on the old plant, in the container,
already marked platform-unverified by section 8.6. Reverse pure pursuit
with the steered axle trailing is exactly a small-correction regime, and on
the old plant small corrections did not execute. If the divergence was
partly a deadband artefact, that is a finding worth more than the
re-measurement, which is why the inventory puts it first.

Route: spawn world (+1.0, +7.0), goal world (-5.0, +7.0).

### A defect found on the way in, in the committed harness

The first attempt did not run: `nav2_run.py goal` raised
`NameError: name 'NavigateToPose' is not defined` at line 311, before a
goal was ever sent. The import was lost when the recorder was factored out
into `_build_recorder` (`6798d8d`, m5-33); `cmd_stage` kept its own copy at
its own call site and `cmd_goal` did not. **Every `goal` invocation has
raised at the first goal since that commit**, which is why sections 8, 9,
10 and 11 - all of them `stage` runs - never saw it. The section 5 cases
were last driven before the refactor. One line restored, at the site that
uses the name, with the history in a comment beside it.

A second, softer trap in the same path: the first repaired run was
`ABORTED` in 0.20 s with 0 plans and
`bt_navigator: Initial robot pose is not available` -
`Requested time 12.838 but the earliest data is at time 13.400`. The goal
was formed before AMCL's `map -> odom` had any history older than the goal
stamp. `cmd_goal`'s `--settle` loop exits the instant the transform is
first available, which is exactly one sample too early; the driver now
waits 25 s after `/plan` appears. `stage` does not show this because its
goal-checker selection and staging leg spend that time anyway. **Recorded
here, not fixed in the harness**: the fix belongs with a decision about
whether `cmd_goal` should require a minimum TF age, which is a design
question and not this brief's.

### Result - and the conclusion does move, though not in the predicted direction

**Two runs, one variable.** The same route, the same platform, the same
committed tree, the same driver, the same domain-isolated protocol; the
only difference is which `model.sdf` the vehicle is spawned from - the
committed tree (steer `p_gain` 60000) or `git show HEAD:` of the same file
(steer `p_gain` 6000, byte-verified identical to HEAD), passed with
`model:=`. This is a one-variable A/B, unlike the comparison against
section 5.2 itself, which also crosses a platform and every nav2.yaml
round from section 5.1 onwards.

| | section 5.2, old plant, container | **old plant, WSL, this tree** | **new plant, WSL, this tree** |
|---|---|---|---|
| outcome | **ABORTED `104`** | **ABORTED `104`** | **SUCCEEDED, 57.59 s** |
| plan | 6.106 m, 0 cusps, 100 % reverse | 6.106 m, 0 cusps, 100 % reverse | 6.106 m, 0 cusps, 100 % reverse |
| ground-truth path | - | 3.927 m | **12.470 m** |
| heading divergence begins | ~2.39 m of travel | **2.745 m of travel** | 5.7 m of travel |
| worst heading | +0.87 rad (50 deg) | **+44.42 deg** at 3.26 m | **-51.54 deg** at 6.26 m |
| distance from goal at the end | 3.68 m | **2.78 m** | **0.345 m** (2.45 x floor) |
| rotation-in-place refusals | - | 1 | 2 |
| plans published | - | 19 | 52 |

**The old plant reproduces its own committed result on this platform.**
Abort code, onset distance and divergence magnitude all land where section
5.2 put them, which retires that figure's platform caveat (section 8.6) at
the same time as it answers the deadband question.

**So B-prime's divergence is NOT a deadband artefact.** It is real, it is
the geometry section 5.2 named - pure pursuit referenced at the trailing
end of the wheelbase - and it survives a plant ten times stiffer at small
angles. On the new plant the heading still runs out, and further (-51.5 deg
against +44.4), simply because the vehicle keeps going instead of being
abandoned at 3.9 m.

**What the plant change does move is the outcome.** The new plant recovers:
52 plans against 19, 12.470 m of travel for a 6.106 m plan, forward
segments inside a 100 %-reverse plan, and an arrival 0.345 m from the goal
instead of an abort 2.78 m short. That is a reverse manoeuvre completed by
replanning, not a reverse manoeuvre followed.

### Ruling on section 5.2's reverse bound

Section 5.2 reads: *"Measured limit on this vehicle at 0.60 m/s: reverse is
followed to about 2.4 m; beyond that the heading diverges."* That sentence
**stands, on both plants**, and it now has n = 2 platforms behind it rather
than n = 1 run: the onset measured here is 2.745 m on the old plant and the
divergence is not removed on the new one.

What must **not** be carried forward is the sentence beside it, that a
6 m reverse goal is unreachable. On the new plant it is reached. TODO's
measured-numbers block quotes the bound; it should keep the bound and gain
the outcome, phrased as: *reverse is followed to about 2.4 m and the
heading then diverges on both plants; under `p_gain` 60000 the vehicle
recovers by replanning and still arrives, at 3.2 x the plan length in
travel.* The cost is the number that matters for M6 traffic, and it is
measured: **a 6 m reverse costs 12.5 m of travel and 57.6 s.**

## 12.3 Case B, 2 m astern

Route: spawn world (+1.0, +7.0), goal world (-1.0, +7.0). The old-plant
figure is `SUCCEEDED in 4.37 s`, tracking rms 0.0009 m, absolute error
0.3117 m.

### Result - and the surprise of this section

Same one-variable A/B as 12.2: two runs, the plant is the only difference.

| | section 5.2, old plant, container | **old plant, WSL, this tree** | **new plant, WSL, this tree** |
|---|---|---|---|
| outcome | SUCCEEDED 4.37 s | SUCCEEDED 4.50 s | SUCCEEDED 4.65 s |
| plan | 2.000 m, 0 cusps, 100 % reverse | 2.000 m, 0 cusps, 100 % reverse | 2.000 m, 0 cusps, 100 % reverse |
| ground-truth path | - | 1.708 m | 1.755 m |
| steer commanded, max | 2.82 deg | **3.35 deg** | **13.21 deg** |
| TRACKING rms | **0.0009 m** | **0.0010 m** | **0.0206 m** |
| TRACKING max | 0.0027 m | 0.0031 m | **0.0480 m** |
| absolute goal error (truth) | 0.3117 m | 0.2924 m | **0.2512 m** |

**The tracking figure gets 20 times worse on the new plant, and that is not
a defect - it is the same mechanism as 12.2 read at a route where it costs
something.** Case B is a 2 m straight reverse from an already-aligned pose.
The correct trajectory is to do nothing but drive backwards, and on the old
plant that is exactly what a frozen steer axis produces: a 3.35 deg command
that does not execute *is* the perfect plan here, so the deadband was
**flattering** this case. Section 5.2's 0.0009 m is therefore the tightest
tracking in the file for a reason that has nothing to do with control
quality, and the WSL old-plant run reproduces it to 0.0001 m.

Give the axis authority and RPP's reverse corrections start acting - and
reverse corrections are exactly the ones section 5.2 identified as an
unstable loop, because the steered wheel trails. The commanded steer goes
to 13.21 deg and the vehicle wobbles at the 2 cm scale. It still arrives,
and it arrives **closer** than either old-plant run (0.2512 m against
0.2924 / 0.3117), because the endgame correction now executes.

**The finding, stated once.** The plant change did not create the reverse
instability and did not remove it; it **un-masked** it. Under `p_gain`
6000 the reverse loop could not act, so short reverse legs looked perfect
and long ones aborted. Under 60000 the loop acts: short legs cost 2 cm of
wobble and long legs cost travel instead of an abort. Section 5.2's
recommendation - that RPP needs a reverse-specific reference point and
lookahead on this vehicle - is not weakened by the plant change. It is the
open item the plant change makes visible, and it is now the binding one for
any M6 route that reverses.

## 12.4 Case C, the named degenerate stretch

Route: spawn world (+1.0, +7.0), goal world (+7.0, +7.0). Old plant:
`SUCCEEDED in 11.09 s`, tracking rms 0.0730 m, absolute error 0.1503 m.

### Result

| | section 5.3, old plant, container | **new plant, WSL, this tree** |
|---|---|---|
| outcome | SUCCEEDED 11.09 s | **SUCCEEDED 11.41 s** |
| plan | 6.003 m, 0 cusps, 0.0 % reverse | 6.003 m, 0 cusps, 0.0 % reverse |
| ground-truth path | 5.866 m | 5.791 m |
| steer commanded, max | 11.63 deg | 7.86 deg |
| TRACKING rms / max | 0.0730 / 0.1223 m | **0.0423 / 0.0885 m** |
| absolute goal error (truth) | 0.1503 m (1.07 x floor) | **0.2009 m (1.42 x floor)** |
| rotation-in-place refused | 0 | 0 |

**Tracking improves by 42 % and the arrival error grows, and the two are
not in tension.** This is a forward drive, the regime in which the plant
change simply lets small corrections act: the vehicle now holds the plan to
0.0885 m worst against 0.1223 m, and asks for a smaller maximum steer angle
to do it (7.86 against 11.63 deg), which is what a loop that corrects early
looks like. The arrival error is a different instrument: at 0.2009 m
against a 0.1411 m registration floor it is 1.42 x the floor, where section
5.3's draw was 1.07 x, and both sit inside the regime section 5.3 itself
describes as "at the instrument's resolution". East A is the aisle where
99 % of the along-aisle information is carried by ten rays; what this pair
of draws bounds is the localizer, not the controller.

**Case C's conclusion is unchanged**: the named degenerate stretch costs the
traverse nothing measurable, and the drive is clean, 0 cusps, 0 % reverse,
0 refusals. No re-derivation follows from it.

## 12.5 Case D, the goal the planner must refuse

Route: spawn world (+1.0, +7.0), goal world (+5.0, +9.0), inside RackRowA.
The refusal half (error code 208, seven planning attempts) was already
re-measured on the bench in section 8.6 and is plant-independent. What is a
drive observation, and therefore re-measured here, is the other half: **the
vehicle never moves**, ground-truth path 0.000 m.

### Result

| | section 5.4, old plant, container | **new plant, WSL, this tree** |
|---|---|---|
| goal accepted at the door | yes | **yes** (`t_sim 30.22`) |
| planning attempts, each failing out loud | 7 | **14** |
| the planner's stated reason | `"no valid path found"` | **`"exceeded maximum iterations"`** |
| costmap clears / `Wait 5.0` recoveries | 6 retries | 10 global-costmap clears, 3 waits |
| result | **ABORTED `208` NO_VALID_PATH**, 90.77 s | **ABORTED `207`**, 59.84 s |
| **ground-truth path** | **0.000 m** | **0.000 m** |
| samples, all at rest | 905 over 90.74 s | **597 over 59.81 s**, 0 forward / 0 reverse / 597 at rest |
| rotation-in-place refusals | 0 | 0 |
| final truth pose | the spawn pose to six decimals | **the spawn pose to six decimals** |

**The half this brief owed is confirmed and unchanged: the vehicle never
moves.** 597 consecutive at-rest samples over a minute of refusal, and the
final truth pose is the spawn pose. That is the property removing `Spin`
and `BackUp` from the behaviour tree exists to produce, and it does not
depend on the plant - which is what the inventory predicted, and it is now
measured rather than predicted.

**The error code changed, and section 5.4 predicted that too.** It reads:
*"the planner does not distinguish 'goal occupied' from 'no path' ... the
bench shows the same goal returning `207 TIMEOUT` on other runs, from the
same cause. A caller cannot tell from the error code why it was refused."*
This run is that second draw arriving in a full-stack run rather than on
the bench, with the planner's own reason changing from
`"no valid path found"` to `"exceeded maximum iterations"` for the same
goal on the same grid. **It strengthens section 6's M6 request rather than
disturbing it**: a fleet manager reading `207` versus `208` learns nothing
about the world, and this is now demonstrated twice at two levels.

## 12.6 The `footprint_padding` re-derivation

The standing TODO item is "padding re-derived or the shuffle prevented".
The shuffle is what the plant change prevents (0 of 5 in section 11.6), so
the re-derivation belongs here, on new-plant localization maxima.

### The new-plant localization maxima this derivation may use

Believed pose against ground truth, every sample of every **new-plant**
drive on the record, re-read through the committed registration by the same
`map_to_world` the harness uses. The reader was validated first by
reproducing two figures the harness printed itself: m5-40 r0's
`rms 0.0663 / MAX 0.1083` and m5-38 r1's `MAX 0.1523`, both exact.

| run | regime | n | position rms | **position max** | heading max |
|---|---|---|---|---|---|
| m5-38 r1 | staged route, d = 4.5 | 295 | 0.0884 m | 0.1523 m | 1.34 deg |
| m5-38 r2, r3, r4, r5 | staged route, d = 4.5 | - | - | 0.1082 / 0.1315 / 0.0718 / 0.1068 m | - |
| **m5-40 r0** | staged route, committed tree | 278 | 0.0663 m | 0.1083 m | 1.75 deg |
| **m5-40 case B** | 2 m reverse | 47 | 0.0166 m | **0.0364 m** | 0.68 deg |
| **m5-40 case C** | degenerate stretch, forward | 114 | 0.0408 m | 0.0885 m | 3.34 deg |
| **m5-40 case B-prime** | 6 m reverse, 52 replans | 574 | 0.1236 m | **0.2056 m** | 4.12 deg |
| m5-40 case D | refusal, stationary throughout | 597 | 0.0000 m | 0.0000 m | 0.05 deg |
| **pooled, all nine driving runs** | | **2413** | **0.0849 m** | **0.2056 m** | **4.12 deg** |

Two things this table says that a single number would hide. **The worst
new-plant localization is not on the criterion route** - it is case
B-prime, the long reverse, whose 52 replans and reversals are the regime
section 8.5 identified as the one AMCL's motion model follows worst. And
**the shuffle regime does not appear at all**: section 8.5's 0.661 m came
from r4's hundreds of reversals at the steer stop, and no new-plant run has
entered that regime (0 of 6 staged routes).

### The derivation

Section 4's rule is explicit: `footprint_padding` is the measured
localization max, rounded up to the centimetre, because a costmap places
the footprint at the pose the vehicle *believes* and the vehicle is really
somewhere within that radius of it. Applying the same rule to the same
quantity on the new plant:

```
measured max, pooled over every new-plant drive   0.2056 m
rounded up to the centimetre                      0.21 m
committed value                                   0.27 m
```

**The derivation says the committed 0.27 stands, and it is not changed.**
That is the ruling, and the reasons are worth more than the number:

1. **0.27 now covers the measurement again, with 0.06 m to spare.** The
   standing TODO item is "padding re-derived **or** the shuffle prevented";
   section 8.6 opened it because r4's 0.661 m left the padding not covering
   its own derivation. Both halves are now satisfied - the shuffle does not
   occur on this plant, and the re-derivation lands under the committed
   value.
2. **Shrinking it to 0.21 would be a real loss for no gain.** Section 2.1
   spends the padding out of a 1.081 m half-aisle and a 0.356 m half-pinch;
   0.06 m back buys aisle margin nobody has asked for, at the cost of
   making the collision polygon a tighter fit to a distribution measured
   over nine runs.
3. **The 0.263 m it was derived from is a different route's measurement.**
   Section 4 takes it from `EVIDENCE_LOCALIZATION.md`'s route case (a),
   which has **not** been re-driven on the new plant (inventory item 6, and
   still open). Replacing a figure from that route with a figure from these
   routes would be a substitution, not a re-derivation, and section 8.6
   already carries the route-to-route caveat.

**The goal tolerances beside it, checked by their own rules rather than
re-derived.** `xy_goal_tolerance: 0.25` is section 4's "twice the measured
rms and just inside the measured max": 2 x 0.0849 = 0.17 m and the max is
0.2056 m, so 0.25 sits outside both and stays. `yaw_goal_tolerance: 0.15`
rad is "1.9 x the heading max": 1.9 x 4.12 deg = 7.8 deg = 0.137 rad,
inside the committed 0.15. **Neither is changed, and neither is widened.**
Both are covered by their own derivations on the new plant, which is the
first time that has been true since section 8.6.

## 12.7 Section 3.3 convcheck, on the new plant

`nav2.yaml`'s steer-reserve derivation cites section 3.3's **23 % understeer
at the tightest arc**. The arcs it drives (26.57 deg, 45 deg) sit above even
the old 3.8 deg knee, but the transient onto each lock and the achieved-radius
means pass through the steer PID.

### The first attempt was HELD, and the harness said so

Run at world (-8.0, +7.0), inside aisle A, three of the eight arc segments
came back at **79 %, 46 % and 82 %** of commanded speed with the harness's
own warning: *"A vehicle that will not accelerate to a speed it is given is
being HELD by something."* It was: an `R = 1.05 m` arc swings up to 2.1 m
laterally and the aisle is 3.80 m wide. That run
(`evidence/m5-40-conv-convcheck.{csv,txt}`) is kept as what it is - **not a
conversion measurement** - because it is the check of `docs/LESSONS.md`
2026-08-04 (a motion check that does not retrace its segments cannot tell a
followed arc from a blocked one) doing its job on a live run for the first
time. Its 147.94 % worst radius error is the arithmetic of a blocked
vehicle and means nothing about the conversion.

Section 3.3's own spawn pose is not recorded (it was a container run,
`/home/user/amr-agent/...`), so the re-run derives one instead of guessing
again: the most open cell in the committed grid, by clear half-width, is
**world (-1.396, -6.756) with 2.90 m of clearance** - the dock apron. The
re-run spawns at (-1.4, -6.75) and **no segment is HELD**: every row lands
at 100-111 % of commanded speed.

### Result

`evidence/m5-40-conv2-convcheck.{csv,txt}`, 3500 samples.

| segment | old plant (section 3.3, container) | **new plant (m5-40, apron)** |
|---|---|---|
| straight ahead / astern | 0.3000 / -0.3000 m/s, 100 % | 0.3000 / -0.3000 m/s, 100 % |
| `R = 2.10 m` left, achieved R | +2.395 m (14 % wide) | **+2.271 m (8.1 % wide)** |
| `R = 2.10 m` astern retrace | +1.950 m | +2.180 m |
| `R = 1.05 m` left, achieved R | +1.291 m | **+1.202 m** |
| `R = 1.05 m` left, `delta_meas` | +39.112 deg for 45 commanded | **+41.150 deg** |
| `R = 1.05 m` right, achieved R | -1.162 m | -1.177 m |
| **worst relative radius error** | **23.00 %** | **14.43 %** |
| speed achievement, every segment | 100-114 % | 100-111 % |
| rotation in place | REFUSED, vehicle moved 0.0000 m | **REFUSED, vehicle moved 0.0000 m, turned +0.0000 deg** |

**The understeer is not removed; it is reduced from 23 % to 14 %, and both
figures are upper bounds that contain tyre slip.** That is the honest
reading: the steer axis now reaches its commanded lock sooner, so less of
each arc is spent in the transient onto it, but a tricycle on a scrubbing
tyre still drives wider than its kinematic radius, and nothing in this
change touches the tyre.

**What it does to `nav2.yaml`'s steer reserve.** Section 3.3 item 3 rules
that the planner's tightest arc costs more steer than the kinematic 45 deg,
and puts the reserve to the 75.06 deg stop "nearer 24 deg than the 30 deg
the file's derivation claims". Re-derived from the new measurement by the
same route - to drive `delta_meas` 45 deg you must publish
`45 x 45 / 41.150 = 49.2 deg` - the reserve becomes **75.06 - 49.2 =
25.8 deg**. So the correction section 3.3 makes to `nav2.yaml` **stands and
shrinks**: the file's 30 deg is still optimistic, by about 4 deg rather
than 6. No parameter is changed here; the derivation is what was asked for.

**Two rows to read with care.** The `R = 2.10 m` astern retrace moves from
+1.950 m to +2.180 m, i.e. from 7 % tight to 4 % wide - the old row was the
only arc in the set that came out *tighter* than commanded, which is what a
half-executed lock produces, and it is now on the same side as every other
row. And the refusal count fell from 7435 to 1363; both are counts of
messages at whatever rate the harness spun, and section 3.3 already quotes
that number only as "nonzero".

## 12.8 How this section was run

### The machine, alone, per run

**Enforced by the driver, not remembered by the operator**, the section
11.7 protocol unchanged: every run refuses to start unless `pgrep -c -f`
over the
`gz sim|nav2|amcl|controller_server|bt_navigator|parameter_bridge|planner_server|velocity_smoother|robot_state_publisher|ekf_node|cmd_vel_to_tricycle|forklift_io|wheel_odometry|imu_gate`
pattern returns **0**, prints load, `/dev/shm` count and a UTC timestamp,
gates each bring-up stage on a topic appearing (`/forklift/odom`,
`/particle_cloud`, `/plan`) rather than on a sleep, and verifies the count
after teardown. The driver additionally prints the committed `model.sdf`'s
`<p_gain>` lines before bring-up, so every artefact records which plant
produced it.

| run | partition / domain | start (UTC) | end (UTC) | load at start | `/dev/shm` | before / after |
|---|---|---|---|---|---|---|
| r0, committed-tree stamp | `m540r0` / 90 | 21:09:13 | 21:10:02 | 0.08 | 517 | 0 / 0 |
| B-prime, new plant | `m540bprime` / 91 | 21:13:0x | 21:15:31 | 0.58 | 578 | 0 / 0 |
| B-prime, **old plant** | `m540bprime-oldplant` / 92 | 21:17:5x | 21:19:20 | - | - | 0 / 0 |
| B, new plant | `m540b` / 93 | 21:19:4x | 21:21:08 | - | - | 0 / 0 |
| B, **old plant** | `m540b-oldplant` / 94 | 21:22:1x | 21:23:33 | 1.48 | - | 0 / 0 |
| C | `m540c` / 95 | 21:23:5x | 21:25:09 | 1.25 | - | 0 / 0 |
| D | `m540d` / 96 | 21:25:2x | 21:27:12 | 2.82 | - | 0 / 0 |
| convcheck, HELD, discarded | `m540conv` / 97 | 21:28:5x | 21:30:38 | 0.54 | 646 | 0 / 0 |
| convcheck, apron | `m540conv2` / 98 | 21:31:2x | 21:33:14 | 1.86 | 668 | 0 / 0 |

**One incident, recorded rather than tidied away.** The first `b-oldplant`
launch was issued twice, two minutes apart, because the launching shell
reported a path error that made the first launch look like it had not
started. It had. **The guard did its job**: the second invocation counted
15 matching processes and refused to start. But the second invocation's
output redirection truncated the first's log while the first was still
writing to it - the same open-file hazard as `docs/LESSONS.md` 2026-07-28
(entry 69), arriving through a redirect rather than a `gzip`. **That run
was discarded, not repaired**, and `b-oldplant` was re-run alone from a
verified-empty machine; the figures in 12.3 are the re-run's. The
discarded run left no evidence file that any figure here quotes.

**A second self-inflicted trap worth one line**: `pkill -f "gz sim"` issued
from an interactive shell kills the shell, because the shell's own command
line contains the pattern (`docs/LESSONS.md` 2026-07-27). Written
`pkill -f "gz[ ]sim"` in the driver's teardown.

### Isolation

`GZ_PARTITION` **and** `ROS_DOMAIN_ID` were both set on every run, distinct
per run, because `gz transport` does not use DDS and the ROS variable does
not isolate the simulator (`docs/LESSONS.md` 2026-07-27). Every run
headless, `DISPLAY` and `WAYLAND_DISPLAY` unset. **No RTF figure was taken
and none is quoted** (`docs/LESSONS.md` 2026-07-30).

### What was and was not changed in the repository

**Changed**: `model.sdf`'s steer `p_gain` and the comment block that argues
for it (12.0), and one restored import in `nav2_run.py` (12.2).

**Byte-identical**: `nav2.yaml`, `amcl.yaml`, `ekf.yaml`, `config.yaml`,
the behaviour tree, both launch files, `cmd_vel_to_tricycle.py`,
`envelope_gate.py`, `forklift_io.py`, `wheel_odometry.py`. **No tolerance
was widened** - `xy_goal_tolerance: 0.25` and `yaw_goal_tolerance: 0.15`
are untouched, and 12.6 checks both against their own derivations rather
than adjusting either. **No dependency was added.** `plc/`, `bridge/` and
`sim/` were not touched.

### Commands

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=m540<tag> ROS_DOMAIN_ID=<n>      # BOTH, every run
unset DISPLAY WAYLAND_DISPLAY                        # headless, llvmpipe

# the staged route, run 0 - section 11.7's commands with model:= REMOVED
ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
ros2 launch agv/forklift/launch/localization.launch.py \
    initial_pose_x:=1.584770 initial_pose_y:=12.576859 initial_pose_yaw:=-0.007915
ros2 launch agv/forklift/launch/navigation.launch.py \
    gate:=false cmd_topic:=/cmd_vel_smoothed
python3 agv/forklift/scripts/nav2_run.py stage \
    --x 1.0 --y 7.0 --yaw 0.0 --d 4.5 --max-go-arounds 2 \
    --settle 30 --staging-timeout 90 --approach-timeout 45 \
    --csv evidence/m5-40-r0-run.csv --plan evidence/m5-40-r0-plan.json

# the section 5 cases - spawn at world (+1.0, +7.0), map (7.084598, 12.533325)
ros2 launch sim/launch/warehouse_bringup.launch.py x:=1.0 y:=7.0 yaw:=0.0
#   ... localization at the map pose above, navigation as above, THEN:
python3 agv/forklift/scripts/nav2_run.py goal --x <GX> --y 7.0 --yaw 0.0 \
    --settle 30 --csv evidence/m5-40-<tag>-run.csv \
    --plan evidence/m5-40-<tag>-plan.json
#   B' GX = -5.0    B GX = -1.0    C GX = +7.0    D --x 5.0 --y 9.0 --timeout 240
# NOTE: 25 s of wait after /plan appears, before the goal - see 12.2.

# the conversion check - bringup + converter + io ONLY, no planner or localizer
ros2 launch sim/launch/warehouse_bringup.launch.py x:=-1.4 y:=-6.75 yaw:=0.0
python3 agv/forklift/scripts/cmd_vel_to_tricycle.py --ros-args -p use_sim_time:=true
python3 agv/forklift/scripts/forklift_io.py --ros-args -p use_sim_time:=true
python3 agv/forklift/scripts/nav2_run.py convcheck \
    --csv evidence/m5-40-conv2-convcheck.csv

# THE ONE ARGUMENT THAT MAKES AN OLD-PLANT A/B, and it is the whole comparison
git show HEAD:agv/forklift/model.sdf > /tmp/m5-40-oldplant.sdf   # verified identical
ros2 launch sim/launch/warehouse_bringup.launch.py ... model:=/tmp/m5-40-oldplant.sdf
```

Artefacts, all under `agv/forklift/evidence/`:
`m5-40-r0-{run.csv,run-approach.csv,plan.json,run.txt,analyse.txt}`,
`m5-40-{b,bprime,c,d}-{run.csv,plan.json,run.txt,analyse.txt}`,
`m5-40-{b,bprime}-oldplant-{run.csv,plan.json,run.txt,analyse.txt}`,
`m5-40-conv-convcheck.{csv,txt}` (the HELD run, kept as what it is),
`m5-40-conv2-convcheck.{csv,txt}`.

## 12.9 What section 12 asks the next brief to decide

1. **RPP has no reverse-specific reference point on this vehicle, and the
   plant change made that the binding item** (12.2, 12.3). It was section
   5.2's diagnosis, masked for two gates by an actuator that could not
   execute the corrections. Any M6 route that reverses more than ~2.4 m
   pays 3.2 x the plan length in travel today.
2. **`cmd_goal`'s settle loop exits one sample too early** (12.2). Recorded,
   not fixed: whether it should require a minimum TF age is a design
   decision, and the `goal` path had been dead since m5-33 so no committed
   figure depends on the current behaviour.
3. **`footprint_padding` stays 0.27 and the standing TODO item closes**
   (12.6), on both of its alternatives at once.
4. **`nav2.yaml`'s steer-reserve comment still overstates the reserve**
   (12.7): 30 deg claimed, ~25.8 deg measured. Section 3.3 already rules
   this; the number moves, the ruling does not.
5. **Section 3.3's spawn pose is not recorded anywhere** and had to be
   re-derived (12.7). Any harness whose result depends on where the vehicle
   stands should print that pose into its own artefact.
6. **`sim/` items are untouched, as the inventory left them**:
   `FORKLIFT_ARENA_EVIDENCE.md` section 5's traction figure still
   contradicts m5-38 section 11.3 (b), and its section 6 steer step still
   describes the old plant. Both are requests to `sim/`, not findings this
   section may act on.

---

# 13. THE MISSION THAT WOULD NOT PLAN — 2026-08-07 (m5-69)

**m5-68 issued the first autonomous mission of the project and got 0 plans in
100 s.** The diagnosis it handed on was "the spawn pose sits at the corner of
the committed grid". This section settles that as a geometry question, fixes
it as one, and then does the thing this file exists to insist on: it drives the
mission **repeatedly** and reports the rate.

| Item | Value |
|---|---|
| Date | **2026-08-07** |
| Brief | `docs/briefs/m5-69-autonomous-mission-unblock.md` |
| Host | **the owner's WSL2 showcase machine** — Ubuntu 24.04.4 on kernel 5.15.167.4-microsoft-standard-WSL2, **20 cores visible, 15.4 GiB of RAM allocated to the guest** out of 31.6 GiB on the host (13th Gen Intel Core i9-13900H). Headless, `DISPLAY` and `WAYLAND_DISPLAY` unset, software rasterised |
| nav2 | **1.3.12** — `nav2_planner`, `nav2_smac_planner`, `nav2_controller`, `nav2_bt_navigator`, `nav2_costmap_2d`, `nav2_regulated_pure_pursuit_controller`, `nav2_velocity_smoother`, `nav2_amcl`, all 1.3.12 |
| Simulator | `gz sim` 8.11.0 |
| Map | `sim/maps/warehouse/warehouse.pgm` md5 `a663163036c5890937f9045bcf559e72`, **unchanged**, verified by `load_registration()` at the start of every run below |
| Under test | `sim/launch/warehouse_bringup.launch.py`'s spawn pose — **the only committed file whose behaviour changed** |
| New tools | `agv/forklift/scripts/start_pose_check.py`, `agv/forklift/scripts/mission_repeat.py` |

**The environment qualifies every figure, in the direction that matters this
time.** Sections 1–5 are container runs; sections 8–12 and this one are WSL
runs. **This section is the first in the file whose figures were taken on the
platform the showcase runs on AND with nothing else on the machine** — no
PLCSIM, no TIA, no bridge, no HMI. Section 13.5 measures what that is worth,
because m5-68's second failure was a stack that died under exactly that load.

**`allow_unknown` STAYS `false`.** No planner, controller, costmap or tolerance
parameter was touched. `nav2.yaml`, `amcl.yaml`, `ekf.yaml`, `config.yaml`,
the behaviour tree, `model.sdf` and both `agv/forklift/launch/` files are
byte-identical to the tree this section started from. The single behavioural
edit is a spawn coordinate and the comment block that argues for it.

## 13.1 THE GEOMETRY, established before anything was changed

The claim to test is that the vehicle starts outside the region the planner
will plan from. That is a statement about two objects — the grid, and a pose —
so both were measured against each other first.

**The tool checks the planner's own rule, not a plausible-looking proxy.**
`nav2_costmap_2d::FootprintCollisionChecker` traces the **outline** of the
**padded** footprint with a Bresenham raytrace and takes the worst cell on it;
it does not fill the polygon. `start_pose_check.py` traces the same outline,
pads with `costmap_2d::padFootprint`'s own rule, and parses the polygon and
the padding **out of `nav2.yaml`** rather than restating them, so the tool
cannot disagree with the planner about the shape it is checking.

### What the committed grid actually covers

```
grid       606 x 410 cells at 0.050 m = 30.30 x 20.50 m
cells      free 188430 (75.8 %)  unknown 53603 (21.6 %)  lethal 6427 (2.6 %)
footprint  padded 8 vertices, padding 0.270 m, inscribed radius 0.769 m
passable components at clearance >= 0.769 m: 2 total
   #1        230.4 m^2
```

**21.6 % of the committed grid is unmapped**, and that is the number the
diagnosis turns on. The map is a SLAM product, not a floor plan: it covers
what the mapping route drove past. The world file is open where the vehicle
stood; the grid had simply never seen it.

### The committed spawn, measured

```
world      (-6.000, -5.500) yaw +0.0000 rad
map        (-0.014, +0.089) yaw -0.0079 rad   cell (182, 312)
cell class free
padded-footprint OUTLINE, 191 cells: free 155  UNKNOWN 36  LETHAL 0  off-grid 0
inscribed clearance 0.430 m against inscribed radius 0.769 m -> DOES NOT FIT AT ANY YAW
passable component 0 (none - below inscribed radius)
VERDICT: INVALID for allow_unknown false
yaw sweep, 72 headings: 55 of 72 INVALID
```

**36 of the 191 outline cells are unmapped**, and **0** are lethal. That
distinction is the whole finding: the pose is not blocked by an obstacle, it
is blocked by ignorance. The inscribed clearance of **0.430 m** against a
**0.769 m** inscribed radius says the vehicle does not fit in the *mapped free
space* there at **any** heading, which is why 55 of 72 headings fail and why
turning the vehicle on the spot could never have helped.

**"At the corner of the grid" was the right instinct and the wrong object.**
Cell (182, 312) is nowhere near the corner of the 606 x 410 image. It is
about 1 m from the edge of the **mapped region**, and the two are 9 m apart.

### Where the mapped aisle actually begins

Scanning the dock aisle along y = -5.50, at yaw 0, one pose every 0.5 m:

| world x | free | unknown | lethal | clearance | component | verdict |
|---|---|---|---|---|---|---|
| -9.00 | 26 | **166** | 0 | 0.000 | 0 | invalid |
| -8.00 | 85 | **106** | 0 | 0.050 | 0 | invalid |
| -7.00 | 128 | **64** | 0 | 0.250 | 0 | invalid |
| **-6.00** | 155 | **36** | 0 | **0.430** | 0 | **invalid — the committed spawn** |
| -5.50 | 175 | 16 | 0 | 0.430 | 0 | invalid |
| **-5.00** | **191** | **0** | 0 | 0.828 | 1 | **VALID — the first one** |
| -4.00 | 191 | 0 | 0 | 1.518 | 1 | VALID |
| **-3.00** | **191** | **0** | 0 | **1.972** | 1 | **VALID — the local maximum** |
| -1.00 | 192 | 0 | 0 | 1.838 | 1 | VALID |
| 0.00 | 191 | 0 | 0 | 1.619 | 1 | VALID |
| 1.00 | 191 | 0 | 0 | 0.650 | 0 | VALID (outline clears; inscribed circle does not) |
| 1.50 | 191 | 0 | 0 | 0.269 | 0 | invalid |

The mapped free space in this aisle **begins at x = -5.00**. The committed
spawn stands **1.00 m west of it**, and the unknown count falls monotonically
from 166 to 0 across that metre — this is a boundary, not a speckle.

### A second defect the diagnosis did not have

m5-68's goal was world (-1.00, -3.00). Measured the same way it is **free at
the centre cell with 0.765 m of clearance against a 0.769 m inscribed
radius** — under it by 4 mm. So the goal was unusable too, independently of
the start, and 13.2 shows the planner agreeing. **Both ends of that mission
were invalid.** Had only the spawn been moved, the mission would have failed
again for a reason nobody was looking for.

## 13.2 THE PLANNER'S OWN VERDICT — the bench, no simulator

The geometry above is a model of what the planner does. The planner is the
authority, so it was asked directly: `map_server` + `planner_server` + a static
TF tree, `nav2_run.py plan`, nothing else running. **Section 8.6 established
that the planner is deterministic and is not the variable**, which is what
makes n = 1 adequate here and nowhere else in this section.

| # | start (world) | goal (world) | result | planning time |
|---|---|---|---|---|
| A | **(-6.00, -5.50)** committed spawn | (-1.00, -3.00) m5-68's goal | **ABORTED, 205 START_OCCUPIED** | 0.014 s wall |
| B | **(-6.00, -5.50)** committed spawn | (+1.00, -5.50) | **ABORTED, 205 START_OCCUPIED** | 0.025 s wall |
| C | (-3.00, -5.50) | (+1.00, -5.50) | **SUCCEEDED**, 4.000 m, 51 points, **0 cusps, 0.0 % reverse**, excursion 0.013 m | 0.010 s |
| D | (-3.00, -5.50) | **(-1.00, -3.00)** m5-68's goal | **ABORTED, 207 TIMEOUT** | 2.030 s wall |
| E | (-4.50, +7.00) → (+1.00, +7.00), the committed aisle-A route | **SUCCEEDED**, 5.693 m, 71 points, 1 cusp, 1.6 % reverse | 0.022 s |
| F | (-3.00, -5.50) | (+10.00, -5.50) | **SUCCEEDED**, 13.442 m, 157 points, **0 cusps, 0.0 % reverse**, excursion 0.793 m | 0.042 s |

**A and B settle the diagnosis.** The refusal is `START_OCCUPIED` and it costs
14 ms — the planner never searches at all. **D settles the second defect**: from
a valid start, m5-68's goal is not refused but searched for until the planner's
own timeout, 145 times longer than a route that works.

**E is a control and it re-measures exactly.** 5.693 m, 71 points, 1 cusp,
1.6 % reverse — identical to section 5.1's committed plan and to 8.6's re-run.
Nothing about the planner has changed; only the pose it was asked to start
from.

**One honest limit on the tool.** 13.1's outline model calls (-4.50, +7.00)
invalid on **one** unknown cell, and the planner plans from it (row E). The
tool is conservative by up to about a cell, because it bins the polygon's
vertices to integers before tracing. It is a screen, not a verdict: **the
planner bench is the verdict**, and `mission_repeat.py` uses the tool only to
refuse a pose before spending a bring-up on it.

## 13.3 THE FIX

`sim/launch/warehouse_bringup.launch.py`, one pose:

```
_SPAWN_X = '-6.00'   ->   _SPAWN_X = '-3.00'
_SPAWN_Y = '-5.50'   ->   _SPAWN_Y = '-5.50'   (unchanged)
```

Same aisle, same heading, same stated intent — the vehicle still stands in the
dock aisle south of rack row C facing +x with the central cross aisle ahead.
It stands 3.00 m further into the building.

**x = -3.00 is chosen for margin, not for the shortest move that works.** It is
**2.00 m east of the first valid pose** in the aisle, it carries **1.972 m of
inscribed clearance** — the local maximum along y = -5.50 — and it lies in the
grid's one large passable component. Section 8.6 measured localisation
excursions to **0.661 m** during recovery; 2.00 m of margin means no such
excursion can push the start pose back out of the mapped region.

**What was NOT done, and why.** `allow_unknown: false` is untouched. A planner
permitted to route through unmapped space on a vehicle that carries safety
claims is a decision for the owner, not a step for this brief, and the
argument for taking it would have to survive the fact that **21.6 % of this
grid is unmapped** — the vehicle would have been free to plan through a fifth
of the building it has never seen. The defect was a vehicle standing outside
its map. The fix is to stand it inside.

**The comment that justified -6.00 was not deleted, it was answered.** Its
reasoning — the plan envelope is clear of rack row C, of the column at
(-4.60, -7.00) and of both charge bays — is still **true of the world**. It was
the wrong object: Nav2 plans against the grid, not against `warehouse.sdf`.
That is written into the file so the next reader cannot make the same
substitution.

## 13.4 THE MISSION, DRIVEN — and the rate, not the best draw

Three routes were driven, **five repeats each, on the fixed spawn**, by
`mission_repeat.py`. Every repeat gets its own `GZ_PARTITION` and
`ROS_DOMAIN_ID`, refuses to start unless `pgrep` over the whole autonomy
pattern returns 0, gates each bring-up stage on a topic **carrying a
message** (or, for AMCL, on the `map -> forklift/odom` transform, because
AMCL is distance-triggered and a standing vehicle publishes no pose), and
tears down to a verified zero. Nothing was changed between repeats.

**The verdict of each repeat is `nav2_run.py`'s own.** This section counts
them; it does not decide what counts as arrival.

### 13.4a The reproduction — the old spawn, full stack, n = 1

Before the fix was trusted, the defect was reproduced end to end from the
**committed** spawn, `--skip-pose-check`, everything else identical:

```
RESULT           ABORTED
error_code       205
elapsed          0.04 s of simulation time
plans published  0
final TRUTH      world (-6.0000, -5.5000) yaw -0.0000
```
```
[planner_server] GridBased plugin failed to plan from (-0.01, 0.09) to (6.99, 0.03): "Start occupied"
[bt_navigator] [navigate_to_pose] [ActionServer] Aborting handle.
```

**The vehicle moved 0.000 m and the whole mission lasted 0.04 s.**

**One difference from m5-68 that is worth stating rather than smoothing
over.** m5-68 recorded `plans_published: 0` and then **100 s of silence**,
its harness timing out with no result. Here the same invalid start produces
an **immediate abort with a code**. The geometry defect is identical and
proven; the *reporting* is not the same, and the difference is on the side
m5-68 also reported as broken — a `bt_navigator` that never delivered its
result. So m5-68's mission attempt shows **both** of its defects at once,
and this section reproduces only the first of them. 13.5 is about the
second.

### 13.4b Route A — the 4.00 m dock leg. **5 of 5.**

`(-3.00, -5.50) -> (+1.00, -5.50)`, plan 4.000 m, 51 points, **0 cusps,
0.0 % reverse**.

| repeat | result | code | elapsed (sim) | plans | travelled | final truth | truth goal error | heading error |
|---|---|---|---|---|---|---|---|---|
| r1 | **SUCCEEDED** | none | 8.53 s | 8 | 3.682 m | (+0.680, -5.550) | 0.3071 m | -0.328 deg |
| r2 | **SUCCEEDED** | none | 8.46 s | 9 | 3.735 m | (+0.734, -5.536) | 0.2682 m | -0.252 deg |
| r3 | **SUCCEEDED** | none | 8.66 s | 9 | 3.780 m | (+0.778, -5.542) | 0.2255 m | -1.192 deg |
| r4 | **SUCCEEDED** | none | 8.49 s | 8 | 3.786 m | (+0.784, -5.519) | 0.2097 m | +1.308 deg |
| r5 | **SUCCEEDED** | none | 8.71 s | 9 | 3.771 m | (+0.769, -5.531) | 0.2178 m | -0.219 deg |

**Rate: 5 of 5.** Elapsed **8.46–8.71 s**, a spread of 0.25 s — this is not a
distribution straddling a criterion, it is five draws of the same event. **No
recovery behaviour ran in any repeat**, and no repeat produced a single
rotation-in-place refusal.

**Two qualifications this table carries, both of which the numbers state
themselves.**

1. **Nav2's arrival is scored against the BELIEVED pose; the last column is
   scored against the truth.** All five satisfied `xy_goal_tolerance: 0.25`
   as the goal checker sees it. Against ground truth the error is
   **0.210–0.307 m**, mean 0.246 m — r1 is outside 0.25 m in truth and inside
   it in belief. The difference is the localiser, and it is bounded below by
   the registration's own **0.141 m** instrument floor: the errors here are
   **1.49–2.18 x that floor**, so between a third and a half of the miss is
   the map, not the vehicle. The section 8.3 arrival geometry is not exercised
   at all on this route, because the approach is straight and the arrival
   heading is within **1.31 deg** of the goal heading in every repeat.
2. **The route ends 0.23 m short by design of the checker, not by accident.**
   The vehicle travels 3.68–3.79 m of a 4.00 m plan and stops inside the
   tolerance box.

### 13.4c Route B — the 13.44 m dock leg. **0 of 5**, and the reason is not length

`(-3.00, -5.50) -> (+10.00, -5.50)`, plan 13.442 m, 157 points, 0 cusps,
0.0 % reverse, excursion 0.793 m. It benched clean (13.2 row F). It fails
every time.

| repeat | result | code | meaning | elapsed (sim) | travelled | stopped at (truth) |
|---|---|---|---|---|---|---|
| r1 | ABORTED | **205** | START_OCCUPIED on a mid-route replan | 10.57 s | 5.564 m | (+2.375, -6.782) |
| r2 | ABORTED | **104** | FollowPath PATIENCE_EXCEEDED | 27.84 s | 3.730 m | (+0.657, -4.798) |
| r3 | ABORTED | **205** | START_OCCUPIED on a mid-route replan | 16.22 s | 4.324 m | (+1.223, -4.962) |
| r4 | ABORTED | **104** | FollowPath PATIENCE_EXCEEDED | 34.39 s | 4.653 m | (+0.799, -4.962) |
| r5 | ABORTED | **104** | FollowPath PATIENCE_EXCEEDED | 27.84 s | 3.890 m | (+0.719, -4.752) |

**Rate: 0 of 5.** All five stop in the same place — between x = +0.66 and
x = +2.38 — after 3.7 to 5.6 m of a 13.0 m journey. **This is one failure
seen five times, not five failures.**

**THE MECHANISM, measured rather than inferred.** The dock aisle pinches at
x in [1.25, 4.00]:

| world x at y = -5.50 | inscribed clearance |
|---|---|
| +1.00 | 0.650 m |
| +1.50 | **0.269 m** |
| +2.00 | 0.472 m |
| +3.00 | 0.453 m |
| +4.00 | 0.450 m |

against a **0.769 m** inscribed radius. The vehicle does not fit through that
stretch of the aisle at any heading — and **the planner routes through it
anyway**, because `FootprintCollisionChecker` traces the footprint's outline
and never looks inside the polygon. This vehicle's padded footprint is
**3.275 m long**: a rack leg can sit entirely inside it and the check still
passes.

Scoring the emitted plan pose by pose with `start_pose_check.py path`:

| route | length | poses whose OUTLINE is invalid | poses whose INSCRIBED CIRCLE does not fit | min clearance | measured rate |
|---|---|---|---|---|---|
| **A** | 4.000 m | 0 of 51 | **2 of 51**, both at the terminus | 0.650 m | **5 of 5** |
| **B** | 13.442 m | **38 of 157** | **13 of 157**, mid-route | 0.500 m | **0 of 5** |
| E (aisle A, committed) | 5.693 m | 5 of 71 (the tool's ~1-cell conservatism at the start) | 0 of 71 | 1.662 m | not driven here |

**r1 is the clearest single data point in the section.** It replanned from
map (8.33, -1.22) = world (2.354, -6.743) and the planner refused its own
vehicle's current pose:

```
world      (+2.354, -6.743)
padded-footprint OUTLINE, 190 cells: free 186  UNKNOWN 4  LETHAL 0
inscribed clearance 0.752 m against inscribed radius 0.769 m -> DOES NOT FIT AT ANY YAW
VERDICT: INVALID for allow_unknown false
```

**The vehicle drove itself, along a plan the planner produced, into a pose the
planner will not plan from.** That is not a spawn problem and it is not a
tuning problem: it is the outline-only collision model meeting a 3.275 m
vehicle in a 2.5 m gap.

### 13.4d Route G — the 12.24 m lane leg. **5 of 5**, and the prediction was registered first

The corridor-width finding above makes a prediction, so it was **written down
before the run**:

> `G (-3.00, -5.50) -> (+9.00, -7.00)` scores **0 of 143 poses outline-invalid,
> 0 of 143 below the inscribed radius, minimum clearance 0.950 m**.
> PREDICTION: G completes at a rate closer to A's than to B's — **at least 3 of
> 5** — despite being **3.06 x** A's length, because length is not what killed
> B, corridor width is.
> FALSIFIED IF: G scores 0 or 1 of 5, which would mean route LENGTH is the
> binding term and the check predicts nothing.

**Result: 5 of 5.** Plan 12.237 m, 143 points, **0 cusps, 0.0 % reverse**.

| repeat | result | code | elapsed (sim) | plans | travelled | final truth | truth goal error | heading error |
|---|---|---|---|---|---|---|---|---|
| r1 | **SUCCEEDED** | none | 21.77 s | 22 | 12.031 m | (+8.780, -7.043) | 0.2240 m | +5.102 deg |
| r2 | **SUCCEEDED** | none | 21.77 s | 22 | 12.015 m | (+8.780, -7.053) | 0.2130 m | +7.116 deg |
| r3 | **SUCCEEDED** | none | 21.71 s | 22 | 12.023 m | (+8.796, -7.004) | 0.1911 m | +3.839 deg |
| r4 | **SUCCEEDED** | none | 21.96 s | 22 | 12.037 m | (+8.804, -7.007) | 0.1963 m | +7.547 deg |
| r5 | **SUCCEEDED** | none | 21.46 s | 21 | 11.923 m | (+8.714, -7.048) | 0.2567 m | +4.638 deg |

**Rate: 5 of 5**, elapsed **21.46–21.96 s**, a spread of 0.50 s over a route
three times as long as A. Mean speed **0.55 m/s**. Truth goal error
**0.191–0.257 m**, mean 0.216 m — no worse than the 4 m route despite triple
the distance, which is what a localiser rather than an accumulating dead
reckoner looks like.

**The prediction holds and the check is now worth something**: three routes,
three corridor-width scores, three rates, monotone in the same order. But
**n = 3 routes is what that claim rests on**, and the check is a screen rather
than a proof.

**One thing route G costs, stated because it is the term nearest its limit.**
The arrival heading error is **+3.84 to +7.55 deg** against the committed
`yaw_goal_tolerance: 0.15 rad = 8.594 deg` — the worst repeat used **88 % of
the heading budget**, where route A used at most 15 %. The difference is the
lane change: G leaves the dock aisle for the y = -7.00 lane and RPP is still
settling that manoeuvre when it arrives. **Section 8.7 item 2's request — an
approach corridor driven straight along the goal heading — is what this route
would consume if it were lengthened or if the goal were moved, and no repeat
here had margin to spare on it.**

### 13.4e The three rates in one place

| route | plan | corridor min clearance | poses below inscribed | **rate** | elapsed |
|---|---|---|---|---|---|
| the **committed spawn**, any goal | refused | — | — | **0 of 1**, `205 START_OCCUPIED` in 0.04 s | 0.04 s |
| **A**, 4.00 m dock leg | 4.000 m, 0 cusps | 0.650 m (at the terminus) | 2 of 51 | **5 of 5** | 8.46–8.71 s |
| **B**, 13.44 m dock leg | 13.442 m, 0 cusps | 0.500 m (mid-route) | 13 of 157 | **0 of 5** | aborts at 10.6–34.4 s |
| **G**, 12.24 m lane leg | 12.237 m, 0 cusps | 0.950 m | 0 of 143 | **5 of 5** | 21.46–21.96 s |

**16 missions were driven for this section.** The brief's `done_when` — "a
mission is issued, planned, and driven to completion on the showcase platform,
repeated enough times to state a success rate rather than a single draw" — is
met by **A at 5 of 5 and G at 5 of 5**, and the honest headline is not either
of those numbers on its own. It is that **the rate is a property of the route,
not of the day**: this file's own history (8.6, 9.5, 10.4) is a distribution
straddling the criterion, and here the two routes that pass pass every time
and the route that fails fails every time, each with a spread far tighter than
its own margin.

**What has NOT been shown by these 16 runs.** Route A and route G are both
straight-ish legs whose goal heading is the travel heading. Nothing here
re-opens section 8.3's arrival geometry, section 10's staged approach or
section 12's reverse bound, and none of those figures is superseded: they were
measured on routes with a cusp, a reverse segment or an uncontrolled arrival
heading, and no such route was driven in this section.

## 13.5 THE ACTION SERVER THAT DIED — three hypotheses, all three killed

m5-68's second failure was that `/navigate_to_pose` had gone: "`planner_server`,
`bt_navigator` and the three vehicle-side processes had died between the mode
entry and the send, and two relaunch attempts did not bring the action server
back inside the session." A recording cannot survive that, so it was tested.

**The experiment.** The same route A, three repeats, with **K synthetic CPU
burners** running beside it. K is the only variable; the burners match no part
of the autonomy pattern, so the guard, the sampler and the teardown all still
see the stack and only the stack. 20 cores are visible to the guest.

| K | peak load1 | repeats | **rate** | sim elapsed | launches alive after the mission | `/navigate_to_pose` after |
|---|---|---|---|---|---|---|
| **0** | 3.72–7.85 | 10 (routes A and G) | **10 of 10** | 8.46–21.96 s | 3 of 3, every repeat | present, every repeat |
| **20** | **24.96–28.95** | 3 | **3 of 3** | 8.44–8.54 s | 3 of 3, every repeat | present, every repeat |
| **60** | **65.11–70.21** | 3 | **3 of 3** | 8.14–8.54 s | 3 of 3, every repeat | present, every repeat |

**At 3.5 x CPU oversubscription the stack does not die, and the mission still
completes.** That is 16 missions across three load levels with no process loss
of any kind.

### The three hypotheses, and what killed each

**(a) The guest ran out of memory and the OOM killer took the servers —
FALSIFIED, and this is the strongest single reading in the section.**

```
/proc/vmstat:  oom_kill 0
uptime -s:     2026-08-03 08:44:19        (up 4 days, 3:01)
```

`oom_kill` is a **monotonic counter since boot**, and this guest has been up
since **2026-08-03**, which spans m5-68's session on 2026-08-07. **The Linux
OOM killer has never fired in this guest at all.** Whatever ended those
processes, the kernel did not.

**(b) The stack was starved of memory short of an OOM kill — FALSIFIED with
the margin.** Across all 19 runs of this section the autonomy stack's total
resident set is **1660–1683 MB** and available memory never fell below
**13 000 MB** of the guest's 15 808 MB. The stack uses **11 %** of the memory
the guest has, and the spread across every load level is 23 MB. There is no
memory story here.

**(c) CPU contention killed it — FALSIFIED as a KILL, and this is where the
real finding is.** What contention does on this machine is not kill the stack.
It stretches the time the stack takes to become usable:

| K | peak load1 | simulator → `/forklift/odom` | localizer → `map -> forklift/odom` | navigation → `/plan` |
|---|---|---|---|---|
| 0 | 3.7–7.9 | 3–8 s | 8–12 s | **15–18 s** |
| 20 | 25.0–29.0 | 10–11 s | 15–16 s | **36–50 s** |
| 60 | 65.1–70.2 | 15 s | 24–26 s | **74–97 s** |

**The navigation stage takes up to 6.1 x longer to advertise `/plan`** — 15 s
becomes 97 s — and the other two stages stretch by 4 x and 2.6 x. Every stage
still completes. **A procedure that waits a fixed interval and then sends a
goal finds no action server**, and reports exactly what m5-68 reported: the
action server had gone. It had not gone. It had not arrived.

### The log signature is not evidence of a death, and that matters

Every navigation log in this section, **including the ten runs whose stack the
driver verified alive and serving immediately beforehand**, ends like this:

```
[WARNING] [launch]: user interrupted with ctrl-c (SIGINT)
[ERROR] [velocity_smoother-4]: process has died [pid ...], exit code -2 ...
[ERROR] [behavior_server-3]:   process has died [pid ...], exit code -2 ...
[ERROR] [cmd_vel_to_tricycle-6]: process has died [pid ...], exit code -2 ...
```

against, in the same run's own record:

```
launch processes alive after the mission: {'sim': True, 'loc': True, 'nav': True}
/navigate_to_pose present after the mission: 1
VERDICT SUCCEEDED
```

**`exit code -2` is SIGINT, and a deliberate teardown is indistinguishable in
the log from a crash.** `ros2 launch` is a process group attached to its
controlling terminal; anything that signals that terminal shuts every node
down and writes this. So m5-68's reading of its logs is not wrong, but the
evidence it rested on **cannot separate "the stack died" from "the stack was
shut down"** — which is the same shape as `docs/LESSONS.md` 2026-08-06's
stopped contactor, where stillness proved nothing because two causes produce
one observation.

**What this section can and cannot conclude.** It did not have m5-68's logs and
it does not claim to know what ended those processes. It establishes, with
numbers, that **the three mechanisms a loaded machine is usually blamed for
did not do it here**, that the stack survives 3.5 x oversubscription intact,
and that the one effect load reliably produces is a **6 x longer bring-up** —
which a fixed wait turns into "no action server" without a single process
dying. `mission_repeat.py` gates on a topic carrying a message instead of on a
sleep for exactly this reason, and it brought the stack up successfully at
every load level tested.

**The honest residual risk for a recording** is therefore not that the stack
dies. It is that under the load of PLCSIM, TIA, the bridge and the HMI the
stack may take **a minute and a half** to be ready, and an operator following a
timed script will conclude it is broken. **Bring the autonomy stack up first,
wait for `/plan`, and only then start the mission** — and note that the whole
of this section ran with **no PLC-side process on the machine at all**, so the
load levels above are synthetic CPU pressure and not a measurement of that
stack.

## 13.6 WHAT SECTION 13 ASKS THE NEXT BRIEF TO DECIDE

1. **`allow_unknown` was NOT changed and the case for changing it is weaker
   than it looks.** 21.6 % of the committed grid is unmapped. Permitting the
   planner into it would licence routes through a fifth of a building the
   vehicle has never observed. **The real remedy is a better grid**: a mapping
   route that covers the south-west corner and the dock aisle's western end
   would make the original spawn valid without touching a planner parameter.
   That is a `sim/` question, not an `agv/` one.
2. **THE OUTLINE-ONLY COLLISION MODEL IS THE MOST IMPORTANT FINDING HERE AND
   IT IS UNRESOLVED.** nav2 checks the footprint's outline, never its
   interior. This vehicle's padded footprint is 3.275 m long, so **an
   obstacle can sit entirely inside it and be invisible to the planner and to
   the controller alike**. Route B is that defect arriving in a drive: a plan
   the planner emitted, 13 of whose 157 poses have less clearance than the
   vehicle's inscribed circle, driven until the vehicle wedged. It bounds
   every "cannot collide" statement the project makes about the process
   layer, and it does not touch the safety layer, which is onboard and
   hardwired and reads no costmap. **A decision is needed on whether routes
   are pre-screened for corridor width** (`start_pose_check.py path` is a
   screen, not a fix) **or whether the costmap gains an inflation radius that
   covers the circumscribed radius** — nav2 warns about exactly this at every
   plan: `inflation radius (0.550000) is smaller than the circumscribed radius
   (2.230050)`. The second is a `nav2.yaml` change with a planning-time cost
   and is not this brief's to make.
3. **Route selection is now a gate criterion in disguise.** A showcase mission
   must be screened before it is recorded: three routes, three corridor-width
   scores, three rates, in the same order. Which route the M5 showcase drives
   is an owner decision and route **G** is the recommendation — 12.24 m,
   21.7 s of driving, 5 of 5 — with route A (4.00 m, 8.5 s, 5 of 5) as the
   short alternative.
4. **Route G spends 88 % of the heading tolerance** on its worst repeat
   (+7.55 deg of 8.594 deg). Section 8.7 item 2's approach corridor is what
   buys that margin back, and any goal moved further along that lane will
   need it.
5. **`/dev/shm` accumulates segments across runs** — 948 entries at the end of
   this session, 32 MB of 7.8 GB used. Nothing here failed because of it and
   no figure rests on it, but the count only ever grows, and the teardown that
   removes processes does not remove their segments.
6. **`sim/scenarios/warehouse_mapping_route.py` line 99** cites the spawn as
   "(-6.00, -5.50)" inside a parenthetical about `WAREHOUSE_LANDMARKS.md`
   section 6's sensor validation. Its live claim — that the mapping route's
   0.40 m lidar offset matches the spawn's — is still true, because y = -5.50
   did not move. The parenthetical is now stale as a spawn reference. **A
   request to `sim/`, not a change made here.**

## 13.7 HOW SECTION 13 WAS RUN

### The machine, and what else was on it

**Nothing.** No PLCSIM, no TIA, no bridge, no HMI, no `field_evaluation.py`.
Every run refused to start unless `pgrep -af` over

```
gz[ ]sim|nav2|amcl|controller_server|bt_navigator|parameter_bridge|planner_server|
velocity_smoother|robot_state_publisher|ekf_node|cmd_vel_to_tricycle|forklift_io|
wheel_odometry|imu_gate|map_server|smoother_server|behavior_server|
waypoint_follower|sensor_tf|sto_contactor|collision_monitor|ros_gz_bridge|ros_gz_sim
```

returned zero, **with the sweep excluded from itself** (`docs/LESSONS.md`
2026-08-06), and each run printed its own load, `/dev/shm` count and UTC stamp
into its own log. Every run verified **zero** matching processes after
teardown; all 19 did.

### Isolation

`GZ_PARTITION` **and** `ROS_DOMAIN_ID`, both set, **distinct per repeat** —
`gz transport` does not use DDS and the ROS variable does not isolate the
simulator (`docs/LESSONS.md` 2026-07-27). Domains 51, 61–65, 81–85, 91–95,
101–103, 111–113; partitions `m569old…`, `m569dockA…`, `m569dockB…`,
`m569laneG…`, `m569load20…`, `m569load60…`. Headless throughout. Runs were
**serialised**; no two simulators ever ran at once (`docs/LESSONS.md`
2026-07-30). **No real-time factor was taken and none is quoted.**

### Commands

```bash
source /opt/ros/jazzy/setup.bash
unset DISPLAY WAYLAND_DISPLAY

# 13.1 — the geometry, no ROS, no simulator
python3 agv/forklift/scripts/start_pose_check.py coverage --sketch
python3 agv/forklift/scripts/start_pose_check.py pose --x -6.0 --y -5.5 --yaw-sweep 72
python3 agv/forklift/scripts/start_pose_check.py scan \
    --x0 -9 --x1 2 --y0 -5.5 --y1 -5.5 --step 0.5

# 13.2 — THE PLANNER BENCH. It needs a TF TREE as well as a map (8.8), and
# ros2 lifecycle set must be RETRIED: the first call after a fresh CLI daemon
# answers "Node not found" for a node that is running (docs/LESSONS.md
# 2026-08-05). Cross-read with `ros2 node list` after `ros2 daemon stop`.
export ROS_DOMAIN_ID=77
ros2 run tf2_ros static_transform_publisher --x 1.58477 --y 12.576859 \
    --yaw -0.007915 --frame-id map --child-frame-id forklift/odom &
ros2 run tf2_ros static_transform_publisher \
    --frame-id forklift/odom --child-frame-id forklift/base_link &
ros2 run nav2_map_server map_server --ros-args \
    -p yaml_filename:=sim/maps/warehouse/warehouse.yaml -p use_sim_time:=false &
ros2 run nav2_planner planner_server --ros-args \
    --params-file agv/forklift/nav2.yaml -p use_sim_time:=false &
for n in /map_server /planner_server; do
  ros2 lifecycle set $n configure; ros2 lifecycle set $n activate; done
python3 agv/forklift/scripts/nav2_run.py plan \
    --start-x -6.0 --start-y -5.5 --x 1.0 --y -5.5 --plan /tmp/B.json
python3 agv/forklift/scripts/start_pose_check.py path --plan /tmp/B.json

# 13.4 — the driven missions. ONE COMMAND PER ROUTE; the driver owns the
# guard, the isolation, the staged bring-up, the sampler and the teardown.
python3 agv/forklift/scripts/mission_repeat.py --spawn-x -6.0 --spawn-y -5.5 \
    --x 1.0 --y -5.5 --repeats 1 --tag m5-69-oldspawn --domain 50 \
    --partition m569old --skip-pose-check --timeout 100
python3 agv/forklift/scripts/mission_repeat.py --spawn-x -3.0 --spawn-y -5.5 \
    --x 1.0 --y -5.5 --repeats 5 --tag m5-69-dockA --domain 60 \
    --partition m569dockA --timeout 120
python3 agv/forklift/scripts/mission_repeat.py --spawn-x -3.0 --spawn-y -5.5 \
    --x 10.0 --y -5.5 --repeats 5 --tag m5-69-dockB --domain 80 \
    --partition m569dockB --timeout 180
python3 agv/forklift/scripts/mission_repeat.py --spawn-x -3.0 --spawn-y -5.5 \
    --x 9.0 --y -7.0 --repeats 5 --tag m5-69-laneG --domain 90 \
    --partition m569laneG --timeout 180

# 13.5 — THE ONE ARGUMENT THAT DIFFERS, and it is the whole experiment: K
# busy loops running beside an otherwise identical route-A sweep.
for i in $(seq 1 $K); do ( exec -a m569burner bash -c 'while :; do :; done' ) & done
python3 agv/forklift/scripts/mission_repeat.py --spawn-x -3.0 --spawn-y -5.5 \
    --x 1.0 --y -5.5 --repeats 3 --tag m5-69-load$K --domain 1$K \
    --partition m569load$K --timeout 120 --stage-timeout 300
pkill -f m569burner
```

### What was and was not changed in the repository

**Changed**: `sim/launch/warehouse_bringup.launch.py`'s `_SPAWN_X` and the
comment block that argues for it. **Added**:
`agv/forklift/scripts/start_pose_check.py`,
`agv/forklift/scripts/mission_repeat.py`, this section and its artefacts.

**Byte-identical**: `nav2.yaml`, `amcl.yaml`, `ekf.yaml`, `config.yaml`, the
behaviour tree, `model.sdf`, `cmd_vel_to_tricycle.py`, `nav2_run.py`, and both
`agv/forklift/launch/` files. **`allow_unknown: false`,
`xy_goal_tolerance: 0.25`, `yaw_goal_tolerance: 0.15`, `footprint_padding: 0.27`
and `inflation_radius: 0.55` are all untouched.** No dependency was added —
13.1's distance transform is written out in `start_pose_check.py` rather than
imported, because `scipy` on this machine is built against numpy 1.x and the
interpreter carries 2.4.2. `plc/`, `bridge/` and `hmi/` were not read from and
not written to.

### Artefacts

All under `agv/forklift/evidence/`, one set per repeat, each carrying the run
that produced it in its name:

`m5-69-{oldspawn,dockA,dockB,laneG,load20,load60}-r<N>-{run.txt,run.csv,plan.json,machine.csv,sim.log,localization.log,navigation.log}`
and `m5-69-<tag>-summary.json` per sweep, rewritten after **every** repeat so a
session that dies mid-sweep still leaves its finished repeats behind.
