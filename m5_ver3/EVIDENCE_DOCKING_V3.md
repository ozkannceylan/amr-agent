# EVIDENCE_DOCKING_V3.md — precision approach and the pallet (F5)

F4 handed this phase a verbatim contract (CONTEXT.md / EVIDENCE_NAV_V3
§20.5): approach accuracy n=1 (0.545 m truth, −0.877 rad at the 0.60 m
box); a TWO-STAGE approach as a requirement; the START_OCCUPIED bay
constraint; jump allowance 1.20 m amcl / 0.89 m slam with no established
maximum; the collision monitor as backstop-not-guard; and the global
costmap obstacle-layer gap, taint proven nil.

This file is what pays those debts. **§1 is the obstacle-layer
re-drive. §2 is station furniture, the colour bridge, Nav2 to
staging, and AprilTag pose vs the marker at staging range.** **§3 is
the dock** (plugin ×5, class verdict, fail-fast, undock). **§4 is the
pallet** (spawn, attach predicate, lift, carry, detach). **§5 is the
track close.**

Everything below was taken on **this rig** (WSL Ubuntu 24.04, ROS 2
Jazzy, gz-sim 8.11.0, RTX 4050) **headless**, `traction=nominal`,
`arm=wheel+imu`, `loc=amcl@735cdbc6`. The dry bar is the acceptance bar
(F4 constraint 19, owner ruling 2026-08-26).

---

## 0. The answer, before the working

| | |
|---|---|
| **global costmap plugins** | `static_layer → obstacle_layer → inflation_layer` (`nav=on@3ed626ce`, parameters hash `9063bec9`) |
| **combination_method 1, empty floor** | LOWERED **0** cells. The layer can only add. |
| **what it added** | 12 427 cells raised, of which **190 NEW LETHAL**, all of them existing 99-cost wall cells going 100. No vehicle trail. |
| **headline `spine_north` on the new label** | **6 arrivals in 6 fresh bringups** that finished. Truth **0.4607 – 0.5226 m**, belief **0.4662 – 0.4889 m**, 56.8 – 57.5 s, RTF 0.9989 – 0.9998. F4's committed set was truth 0.4474 – 0.5859 m on `nav=on@3148d052`. The box still holds. |
| **two `no_progress` on the same file** | named below. Not a painted wall. The truck left the line and the watchdog fired at 7.8 – 10.3 m. Same class as F4's `ring_corner` residual. |
| **S5 staging, Nav2, `nav=on@3ed626ce`** | **4 arrivals** that finished. Truth **0.5131 – 0.5691 m**, belief **0.5229 – 0.5773 m**. Heading at rest **0.666 – 1.370 rad**. START_OCCUPIED never fired (error_code never 205). One named `no_progress` (same miss class as §1.4). |
| **furniture** | `tag36h11_0` spawned at world (7.000, 2.600, 0.800), yaw +π/2, via `/world/warehouse/create`. `warehouse_ver3.sdf` not edited. |
| **AprilTag at staging range** | **n=211, rms 0.0706 m** in `map` vs the marker through the committed registration (`tag-s5-20260828-155745`). Z is 0.798 vs 0.800. The number sits **inside** the registration residual MAX **0.1179 m**, so it is not a measurement of PnP beyond the map's own floor. Nav2's latched heading does **not** put the tag in the camera. |
| **S5 dock, `docking=on@3526e090`** | **Plugin 5/5** from heading-aligned staging (the same seed T1 used for the tag). Truth **0.2465 – 0.2553 m**. Strict 0.25 m class **2/5**. Heading **0.032 – 0.596 rad** (`isDocked` is XY). One spawn→dock also in class (`190838`, 0.2425 m). Fail-fast **901**. Undock **905**. |
| **S5 pallet, `run-20260828-230721`** | Spawned at world **(7.000, 3.030, 0.072)**. `attach_ok` **True** at the seated docked pose (yaw_err **0**, height_err **0.014 m**). Lift: pallet z **0.072 → 0.152**. Carry: truck and pallet both **+0.433 m** in y. Detach left the pallet at **(7.000, 3.478, 0.072)**. Nav2 cycle ×3 **not run**. Laden footprint **not switched**. |

---

## 1. The obstacle layer, and the label it bought back

F4 §19.9 / §20.6 handed the layer on with three reasons: it moves
`nav2.yaml`'s VALUE hash; it changes what every arm plans through; a
planar scan into a non-rolling map leaves marks nothing clears.
`nav2.yaml` pays all three in the file: `combination_method: 1` (MAX),
marking 8.00 m / clearing 12.0 m, `footprint_clearing_enabled: true`.
This section is the measurement that file predicted.

### 1.1 Two captures, empty floor, truck at rest at spawn

`tools/costmap_probe.py record` then `compare`. No goal, no twist.

| capture | session | `nav=` |
|---|---|---|
| before | `costmap-static_only-20260827-223500` | `on@e0bbf698` (static + inflation only) |
| after | `costmap-obstacle_layer-20260827-223802` | `on@3ed626ce` (static + obstacle + inflation) |

Both `loc=amcl@735cdbc6`. `compare` refuses a pair whose `loc=` differs.

```
                   before        after
lethal              15757        15947
unknown           1430272      1430184
free               110328       108568
other              491195       492853

RAISED    12427 cells  (of which NEW LETHAL 190)
LOWERED   0 cells  (of which LETHAL LOST 0)
```

**LOWERED 0 is the prediction.** `updateWithMax` never writes below what
is already there. On a floor whose obstacles are all in the frozen grid,
the layer can only add.

**THE 190 NEW LETHALS ARE NOT A TRAIL.** The first ten raised cells are
all `99 → 100` at world y ≈ +14.1, x ∈ [−21.0, −17.3] — the north-wall
band the frozen map already carries at high cost. A heading smear of a
few centimetres at 8 m range is enough to push an inflated-inscribed
cell over the lethal threshold. It is the scan agreeing with the map,
not a new object.

### 1.2 After a failed drive, the master grid is allowed to move

`costmap-with_layer-20260828-095032` vs `costmap-after_fail-20260828-095406`
are the same bringup (`run-20260828-094727`), same `nav=on@3ed626ce`,
taken before and after `goal-spine_north-20260828-095142` (`no_progress`).

```
RAISED    11822 cells  (of which NEW LETHAL 889)
LOWERED   16049 cells  (of which LETHAL LOST 819)
```

`compare` prints the sentence the header predicted: a LOWERED cell is
the one result `combination_method: 1` cannot produce **inside the
obstacle layer**. The master OccupancyGrid is the three layers
combined. Inflation is recomputed from the current lethals; footprint
clearing paints the truck free; raytrace clearing can drop the obstacle
layer's own marks before MAX is applied. So the published grid MAY
lower between two captures of a moving truck, and that is not the
prediction failing.

The lowered cells in the first ten are again `100 → 99` on the same
north wall, not a 17 m stripe along the spine. **The failed run did not
paint the vehicle into the global plan.**

### 1.3 `spine_north` ×3, twice, on `nav=on@3ed626ce`

F4's headline on the previous file (`nav=on@3148d052`, parameters
`f5255467` era then `3148d052`): three arrivals, truth 0.4646 – 0.5396 m,
~57 s, ~16.4 m driven. The new file has to carry the same claim or the
label chain is a comment.

**Six fresh-bringup arrivals, all `outcome=ran`, action status 4,
error_code 0.** Two extra `no_progress` on the same parameters are in
§1.4 and are not in this table.

| session | sim s | driven | TRUTH | BELIEF | heading | RTF |
|---|---|---|---|---|---|---|
| `goal-spine_north-20260827-223911` | 56.96 | 16.566 m | **0.4768 m** | 0.4679 m | +0.0034 rad | 0.9998 |
| `goal-spine_north-20260827-224218` | 56.87 | 16.517 m | **0.4922 m** | 0.4716 m | −0.0428 rad | 0.9997 |
| `goal-spine_north-20260827-224444` | 56.86 | 16.487 m | **0.5217 m** | 0.4733 m | +0.0102 rad | 0.9998 |
| `goal-spine_north-20260828-095934` | 57.51 | 16.494 m | **0.5179 m** | 0.4811 m | +0.0183 rad | 0.9995 |
| `goal-spine_north-20260828-100218` | 56.76 | 16.502 m | **0.5226 m** | 0.4889 m | −0.0144 rad | 0.9991 |
| `goal-spine_north-20260828-100918` | 56.86 | 16.582 m | **0.4607 m** | 0.4662 m | +0.1346 rad | 0.9989 |

Every arrival is inside the 0.60 m box at rest, on both instruments.
Closest believed approach 0.5798 – 0.6082 m — the box latches, then the
truck stops, same as F4 §16.5. Path deviation mean 0.037 – 0.064 m.
Controller 20.018 – 20.021 Hz. Worst steer step 0.100000 rad/tick on
the runs that asked for a full step. Cusps 0. Plans ~56.

**THE LABEL IS BOUGHT BACK.** Parameters hash `9063bec9` (comments-only
difference from file hash `3ed626ce`) is now a measured spine_north set,
not an unmeasured edit.

Two sessions on the 2026-08-27 22:36 bringup (`…224020`, `…224033`)
returned in 50 ms with status 4 because the truck was still at the goal
from `…223911`. They are recordings of a second `navigate_to_pose` to a
pose the checker already held. They are not in the table.

### 1.4 Two `no_progress`, named

| session | closest truth | end truth | notes |
|---|---|---|---|
| `goal-spine_north-20260828-095142` | 7.8291 m at t+41.3 s | 9.6234 m at (−9.48, +8.37) | same bringup as the empty-floor capture; first plan 17.003 m reverse, last plan 10.528 m still reverse; 14.865 m driven against a 7.690 m line |
| `goal-spine_north-20260828-100453` | 10.3833 m | 10.3771 m at (−10.27, +8.53) | fresh bringup; first plan 16.994 m reverse; last plan 11.585 m with 2 forward segments |

The watchdog abandoned both at ~30 s without closing 0.5 m on their
best mark. The truck had left the north-leg line and was heading south
of west, ~8 m west of the goal. **That is not START_OCCUPIED (error_code
was never 205; the planner kept publishing reverse plans) and it is not
a self-painted wall (§1.2).** It is the long-straight residual F4 parked
on `ring_corner`: the controller leaves the line, curvature following
does not pull it back, the fail-fast names it in 60–67 s instead of
130 m.

F4's own committed set on the previous file was `spine_north` 3/3 and
`ring_corner` 1 `no_progress`. This file's headline is still 3/3 (twice)
with the same named miss class on the same route family. The layer did
not create it.

### 1.5 What §1 does not claim

- No furniture in the world yet. The 190 new lethals are the map's own
  walls seen by the nav lidar, not an AprilTag board.
- No wet set. Constraint 19.
- No `--rf2o` / `--fuse` driven goal. F4's debt, still.
- The 8.00 m marking / 12.0 m clearing inequality is argued in
  `nav2.yaml` and pinned by `tests/test_nav2_params.py`. It is not
  re-derived here. A later section that spawns a body the map does not
  know is where that inequality becomes a measurement.

---

## 2. Station furniture, colour, staging

Constraint 21: furniture is spawned, never written into the committed
world file. The marker SDF is generated from libapriltag's own
`tag36h11_create()` (`tools/tag_model.py write`, 48 black cells, 0.50 m
printed tile) and placed by `tools/furniture.py place` on
`/world/warehouse/create` with `sdf_filename` — the same idiom as
`spawn_truck()`. Pose is `tag_core.station_geometry` off
`m6/ipc/stations.py` S5 plus `config.yaml` `dock:`: world
**(7.000, 2.600, 0.800)**, yaw **+π/2** so the printed +X faces the
oncoming forks.

The colour stream is now on the image bridge beside depth
(`topics.cam_image` = `/forklift/gz/cam/image`). F4 left it unbridged
because nothing consumed it. F5's detector does. The point cloud stays
off the wire.

`apriltag_ros` 3.4.0 is vendored under `~/m5v3_apriltag_prefix` (no
sudo). libapriltag lives at `lib/x86_64-linux-gnu/libapriltag.so` on
this archive — measured 2026-08-28, pinned in `apriltag.lib`. Detection
accuracy at staging range is §2.4. `m5v3.sh start --dock` is a flag.

### 2.1 Staging pose, by construction

S5 station point (7.00, 4.25), travel south. Marker 1.65 m ahead.
Docked standoff = fork reach 1.875 + tip 0.10. Staging run-in 2.00 m.
Staging world **(7.000, 6.575)**, travel still south. `tests/test_tag_core.py`
refuses a staging pose inside START_OCCUPIED; the grown-footprint
margin is **+0.946 m**. `nav.goals.station_s5_staging` is a copy of
that derivation (`derived: true`, `route_node: false`, `case_only`);
`tests/test_dock_ground.py` recomputes it and refuses a typed invention.

### 2.2 Nav2 to staging ×3, `nav=on@3ed626ce`

Four fresh bringups with the marker in the world, then a fifth with
`--dock`. One start died in `ekf_health` before any goal
(`run-20260828-144832`) — the known discovery-race refusal, named, not
a staging result. Four of the five finished drives arrived. One
`no_progress` is in §2.3.

| session | sim s | driven | TRUTH | BELIEF | heading | RTF |
|---|---|---|---|---|---|---|
| `case-stage_s5-20260828-144653` | 85.72 | 24.777 m | **0.5397 m** | 0.5448 m | +0.6664 rad | 0.9966 |
| `case-stage_s5-20260828-145110` | 86.56 | 25.204 m | **0.5141 m** | 0.5285 m | +0.6689 rad | 0.9946 |
| `case-stage_s5-20260828-145413` | 85.16 | 24.534 m | **0.5131 m** | 0.5229 m | +0.7394 rad | 0.9975 |
| `goal-station_s5_staging-20260828-155356` | 86.02 | 24.821 m | **0.5691 m** | 0.5773 m | +1.3696 rad | 0.9970 |

Every arrival is inside the 0.60 m box at rest, on both instruments.
Closest believed 0.5890 – 0.6000 m. Cusps driven 0. First plan ~25 m
reverse (forks-first). Error_code **never 205**. The staging pose is
outside the trap zone in the planner's own mouth, not only in the
arithmetic.

**Heading at the box is 38–78 deg.** The first three were 0.666–0.739
rad; the `--dock` bringup latched at **1.370 rad**. That is F4 §16.6 /
§20.5 item 2 on this pose: a 0.60 m position latch with the travel
heading still bent. From that heading the pallet camera does not see
S5 (§2.4). The dock controller is what the two-stage requirement buys.
Nav2 got the truck to staging. It did not dock.

### 2.3 One `no_progress`, named

| session | closest truth | end truth | notes |
|---|---|---|---|
| `case-stage_s5-20260828-144332` | 0.7848 m at t+88.5 s | 2.3351 m at (+9.29, +7.05) | first plan 24.968 m reverse; last plan 3.727 m mixed; watchdog at believed 2.326 m after 30 s without closing 0.50 m on a best of 1.093 m |

Not START_OCCUPIED. Not the marker — staging is 4 m north of the board
and the nav lidar at z = 1.80 cannot see a 0.80 m tag. Same miss class
as §1.4 / F4 `ring_corner`: the controller left the line on the way
into the bay mouth and the fail-fast named it.

### 2.4 AprilTag pose vs the marker, staging range

`tag_bench.py` looks up `map` → `tag36h11_0` and scores against the
furniture pose **carried through the committed registration**. A map-frame
CSV scored against the world xy is the hall origin (~31 m on this grid),
not PnP; `tests/test_tag_bench.py` refuses that mix.

Jazzy `apriltag_msgs` 2.0.2 has no pose field. The pose is TF. Two
things had to be true before that TF was a number:

1. **Empty `AprilTagDetectionArray` frames are not a detection.** The
   node publishes one per camera frame. `tag_bench` wait used to latch
   on the first empty array and record zero rows.
2. **PnP is ROS optical (Z forward), Gazebo looks along link +X.**
   Stamping the image as `pallet_cam_link` put range into map-up
   (measured z ≈ 3.74 m on a 0.80 m marker). `--dock` now publishes
   `pallet_cam_link` → `pallet_cam_optical` at REP-103 rpy
   (−π/2, 0, −π/2) and `model.sdf` `gz_frame_id` is the optical frame.

**At the Nav2 latch the camera does not see the tag.**
`goal-station_s5_staging-20260828-155356` arrived inside the 0.60 m box
with heading error **1.370 rad (78.5 deg)** at rest. `tag_bench.py record`
then refused: no id-0 detection in 30 s. That is §2.2's heading residual
in the camera's mouth, not a dead detector.

**At the same xy with the table heading (forks south), after AMCL was
re-seeded at that pose:**

| session | n | mean | rms | min / max |
|---|---|---|---|---|
| `tag-s5-20260828-155745` | 211 | **0.0706 m** | **0.0706 m** | 0.0697 / 0.0721 m |

Expected map (−24.103, 7.176, 0.800). One sample (−24.093, 7.246, 0.798).
Almost all of the 7 cm is +Y. Z is 2 mm.

**THE INSTRUMENT FLOOR TRAVELS WITH IT.** Registration residual rms
0.0291 m, MAX **0.1179 m**. 0.0706 m is inside that MAX, so this is
**not** a measurement of PnP beyond the map's own floor. It is the
statement that the TF chain `map` → `odom` → `base_link` →
`pallet_cam_link` → `pallet_cam_optical` → `tag36h11_0` is consistent
with the furniture at staging range, to the grid's own residual.

The heading-aligned pose is not what Nav2 delivers. That is why Task 2
exists.

### 2.5 What §2 does not claim

- No `opennav_docking` in this section. Heading at the Nav2 box is the
  reason it has to run; the camera does not see S5 from that heading.
  The dock is §3.
- No pallet.
- No wet set. Constraint 19.
- The 0.0706 m figure is heading-aligned at staging xy, not a capture
  from Nav2's latched heading.

---

## 3. The dock

`opennav_docking` 1.3.12, `SimpleNonChargingDock`, `docking=on@3526e090`
on `--headless --localize amcl --nav --dock`. External detection is the
AprilTag TF (`detected_dock.py` → `topics.detected_dock_pose`).
`dock_backwards: true` (forks are model −x). `v_angular_max` 0.08 =
`v_linear_min / 1.25`. Constraint 22: every dock session is
`authority=dock`; the bench cancels NavigateToPose and waits for
`/cmd_vel` quiet before `DockRobot`. On `200222` every live command
was reverse (`vx` ∈ [−0.250, −0.103]) and **0 / 157** broke the 1.25 m
curvature floor.

### 3.1 What had to move before a dock could latch

| lever | package default | this plant | why |
|---|---|---|---|
| `external_detection_translation_x` | −0.20 | **−1.975** | fork_reach + standoff, **into** the tag. `+1.975` drove through it at `v_max` (`181917`). |
| `dock_backwards` | false | **true** | false is counterweight-first. |
| `staging_x_offset` | −0.7 | **+2.00** | `getStagingPose` along pose_yaw, which points at the aisle. |
| `docking_threshold` | 0.05 | **0.25** | 0.05 sits inside the slowdown bubble. `182748`: 0.184 m at heading 0.001 rad, then `v≈0`, `ω=0.08`, 905. |
| `slowdown_radius` | 0.25 | **0.10** | must be **inside** the threshold. Equal radii made `isDocked` a race against that spin (`184333`: plugin success, truth 0.275 m / 0.633 rad). |
| `use_collision_detection` | true | **false** | `192604`: detection succeeded, then "Collision detected" at odom (−24.72, 3.90) — **staging**. T1 drove this spur ×4. F4: the collision monitor is a backstop, not a guard. |
| `dock_approach_timeout` | 60 | **120** | `184208`: 60 s timed out resetting a missed approach at 0.10 m/s. |
| `undock_*_tolerance` | 0.05 | **0.50 m / 0.30 rad** | 0.05 is a charger breakaway. This undock is "back at staging". |

### 3.2 Fail-fast

`--dock-id nosuch` → **901 `DOCK_NOT_IN_DB`** (`dock-s5-20260828-180958`).
Named, not a hang.

### 3.3 Accuracy, heading-aligned staging, `docking=on@3526e090`

Nav2's goal checker is **position-only** (`xy_goal_tolerance` 0.60 m, no
yaw). T1 latched at 0.67–1.37 rad; the camera does not see S5; DockRobot
from spawn is then **904** (`192920`, `193233`). The ×5 below starts at
the **same heading-aligned staging xy T1 used for the tag capture**
(`dock_bench.py stage`: gz `set_pose` + `/initialpose`). That is stage 2
of the two-stage approach, isolated from Nav2's heading lottery. The
teleport between repeats is **not** a localization jump during approach.

| session | plugin | retries | TRUTH | heading | class 0.25 m |
|---|---|---|---|---|---|
| `dock-s5-20260828-200201` | True / 0 | 0 | 0.2553 m | +0.5318 rad | NO |
| `dock-s5-20260828-200222` | True / 0 | 0 | **0.2479 m** | **−0.0322 rad** | **YES** |
| `dock-s5-20260828-200242` | True / 0 | 0 | 0.2516 m | +0.2325 rad | NO |
| `dock-s5-20260828-200302` | True / 0 | 0 | **0.2465 m** | **+0.0351 rad** | **YES** |
| `dock-s5-20260828-200328` | True / 0 | 0 | 0.2536 m | +0.5960 rad | NO |

**Plugin 5/5. Strict truth class 2/5.** The three NOs are 2–5 mm outside
0.25 m, inside the registration residual MAX 0.1179 m. `isDocked` is XY
against the refined tag pose, not truth against the bay, and not heading.
When XY hits 0.25 m with heading still out, SmoothControlLaw is already
commanding `ω = v_angular_max` (200201, 200328). When heading is already
on the table, the same latch is 0.03 rad (200222, 200302).

One spawn→Nav2-staging→dock also made class, with two internal retries
that returned to staging first:

| session | plugin | retries | TRUTH | heading | class |
|---|---|---|---|---|---|
| `dock-s5-20260828-190838` | True / 0 | 2 | **0.2425 m** | **−0.1119 rad** | **YES** |

That path is not repeatable at ×5: the next four spawn trials were 903
(Nav2 through the bay), 905 (collision-at-staging, before the checker
was switched off), and 904 ×2 (heading 0.74–1.21 rad, camera empty).

### 3.4 Named misses (spawn trials, not in the ×5 table)

| session | error | what it is |
|---|---|---|
| `180958` | **901 DOCK_NOT_IN_DB** | fail-fast |
| `181917` | 905 | translation_x sign was +; drove through the tag |
| `182748` | 905 | threshold 0.05; 0.184 m at heading 0.001 then spin |
| `184333` | 0 | plugin success, truth **0.275 m / 0.633 rad**, class NO (slowdown still 0.25) |
| `185442` | **903 FAILED_TO_STAGE** | START_OCCUPIED from inside the bay |
| `191937` | 903 | Nav2 overshot staging to world y=3.46 |
| `192604` | 905 | collision projection at staging |
| `192920`, `193233` | **904 FAILED_TO_DETECT_DOCK** | Nav2 heading, no tag |

### 3.5 Undock

`UndockRobot` is **not** the reverse-out. With `dock_backwards` the
server takes the **current** pose, flips yaw by π, then
`getStagingPose` with our **+2.00 m** offset — that points at the
marker. Measured: `190838` undock 905, collision at odom (−24.38, 5.57),
truck ended world (6.301, 3.750) yaw −1.439 (south, into the bay). The
spur-exit primitive remains `nav.cases.reverse_out` / `ring_s5_junction`,
and from inside the bay that is 205 START_OCCUPIED.

Between the ×5 repeats the bench did **not** undock; it `set_pose`'d
back to staging.

### 3.6 Class verdict

F4 §16.6 said 0.25 m is not reachable in **one** Nav2 approach. In
**two** stages, with the camera on the tag:

- **XY at the 0.25 m latch is the docking_threshold itself**, scored on
  truth vs the bay. 2/5 inside, 5/5 within 6 mm. The millimetres outside
  are not a second controller problem; they are `isDocked` on belief vs
  a 0.25 m cut on truth, on a grid whose residual MAX is 0.12 m.
- **Heading is not a class this plugin keeps.** The two in-class rows
  are 0.03 rad; the three just-out rows include 0.23–0.60 rad of spin
  after XY arrived.
- Jumps during final approach: not separately instrumented on this
  bench (`dock_bench` records `cmd_vel` + truth, not `map`→`odom`). No
  1.2 m step was observed as a named abort. The `set_pose` between
  repeats is a teleport and is not a jump.

### 3.7 What §3 does not claim

- No wet set. Constraint 19.
- No ×5 from **spawn** through Nav2's position latch. That path made
  class once (`190838`) and 904/903/905 otherwise.
- No working `UndockRobot` on this offset sign. The finding is named.

---

## 4. The pallet

Constraint 21: `pallet_s5` is a create-service spawn
(`pallet_place.py`), never written into `warehouse_ver3.sdf`. Constraint
23: attach is `pallet_core.attach_ok` (both tips in the pocket AABBs,
yaw < 0.087 rad, height < 0.02 m), then `gz.msgs.Empty` on
`topics.pallet_attach`. Contact is not a signal.

Pockets are empty tunnels on the fork spacing **0.56 m** (model.sdf
`fork_left` / `fork_right` y ±0.28). Opening **0.16 m**. EUR planform
1.20 × 0.80 × 0.144 m. Deck bottom sits above the lowered tine top.

### 4.1 Plugin pin, gz-sim 8.11.0

The tutorial names `<child_model_link>`. This binary refuses it:

```
[Err] [DetachableJoint.cc:93] 'child_link' is a required parameter
```

`forklift_ver3/model.sdf` carries `<child_link>pallet_body</child_link>`.
`tests/test_pallet_place.py` pins that spelling.

The plugin **auto-attaches the moment `pallet_s5` exists**, which at
bringup is a 24 m joint from spawn to S5. `m5v3.sh start --dock`
therefore runs `pallet_bench.py detach` immediately after
`pallet_place.py place`. Pickup is the later `attach` gated on the
predicate.

### 4.2 One seated pickup, then a carry, then a drop

Stack: `run-20260828-230721`, `loc=amcl@735cdbc6`, `nav=on@3ed626ce`,
`docking=on@3526e090`. Truck seated at the T2 docked pose
(7.000, 4.575, yaw +π/2) with `pallet_bench.py seat` (gz `set_pose`,
not `DockRobot`). Pallet already at its spawn pose.

| step | truck (x, y, z) | pallet (x, y, z) |
|---|---|---|
| spawn (bringup) | (−17.00, 10.00, 0) | (7.000, 3.030, 0.072) |
| seated + attach_ok | (7.000, 4.575, 0) | (7.000, 3.030, 0.072) |
| after lift 0.10 m, 3 s | (7.000, 4.575, 0) | (7.000, 3.030, **0.152**) |
| after cmd_vel +0.15, 3 s | (7.000, **5.008**, 0) | (7.000, **3.463**, 0.155) |
| after lower | (7.000, 5.023, 0) | (7.000, 3.478, **0.072**) |
| after detach + leave | (7.000, 5.023, 0) | (7.000, **3.478**, 0.072) |

`attach_ok` **True**, yaw_err **−0.000 rad**, height_err **0.014 m**.
Carry Δy truck **+0.433 m**, pallet **+0.433 m**. The joint held. After
lower+detach the pallet sits on the floor **0.448 m** north of spawn.
The second cmd_vel burst after detach did not move the truck (AMCL /
smoother after `set_pose` is the same class T2 already named); the
pallet **did not follow**, which is the detach check that burst can
still make.

`set_pose` of the truck does **not** carry an attached child. That is
why the carry used `/cmd_vel`, not `dock_bench.py stage`.

### 4.3 What §4 does not claim

- No Nav2 transit → stage → `DockRobot` → attach cycle, and not ×3.
  The pickup was from a seated docked pose. T2 already measured the
  plugin dock.
- No `UndockRobot`. Reverse-out was cmd_vel +x (aisle).
- No laden footprint republish on `~/footprint`. nav2.yaml still ships
  the unladen hull. Cheap to skip, recorded.
- Plant mass does not change under load. The carry is a kinematic
  joint, not a heavier truck.
- `topics.pallet_joint_state` exists and stayed silent to
  `gz topic -e -n 1` (3 s). Attach/detach were scored on pose, not on
  that string.

---

## 5. Track close — AMR-DEC-003

m5-ver3 promised one showcase truck, honest sensors, an estimate
scored against ground truth, then a dock and a pallet. What this
branch measured:

| phase | what was promised | what was measured |
|---|---|---|
| F1–F1.5 | instrumented plant, wheel slip | EVIDENCE_SENSORS / MODEL / LATERAL_TUNE |
| F2 | EKF vs ground truth | EVIDENCE_FUSION |
| F3 | `map` → `odom`, amcl and slam | EVIDENCE_LOCALIZATION_V3 |
| F4 | Nav2 on the tricycle, stations | EVIDENCE_NAV_V3 |
| F5 T1 | obstacle layer + AprilTag at S5 | this file §1–§2 |
| F5 T2 | `opennav_docking` at S5 | this file §3. Plugin 5/5. Class 2/5. Undock 905. |
| F5 T3 | pallet pickup | this file §4. Attach, lift, carry, detach. Not the Nav2 ×3 cycle. |

Still open, and not this track's to pretend otherwise:

- `ring_corner` (F4 residual, two `no_progress` in §1.4)
- wet-floor challenge phase (constraint 19)
- `--fuse` as a prediction, not a shipping arm
- learned pallet detector (markers carry the demo;
  `docs/reports/m5v3-03` §4)
- Nav2 cycle ×3 through the dock plugin
- laden footprint switch
- `UndockRobot` on `dock_backwards: true`

What comes next is the owner's call: M6 fleet integration, the
challenge phase, or finishing the Nav2 pallet cycle on this branch.
Nothing outside `m5_ver3/` was edited. `warehouse_ver3.sdf` was not
edited. PLCSIM was not opened.


