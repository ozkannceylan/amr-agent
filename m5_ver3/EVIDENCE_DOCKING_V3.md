# EVIDENCE_DOCKING_V3.md — precision approach and the pallet (F5)

F4 handed this phase a verbatim contract (CONTEXT.md / EVIDENCE_NAV_V3
§20.5): approach accuracy n=1 (0.545 m truth, −0.877 rad at the 0.60 m
box); a TWO-STAGE approach as a requirement; the START_OCCUPIED bay
constraint; jump allowance 1.20 m amcl / 0.89 m slam with no established
maximum; the collision monitor as backstop-not-guard; and the global
costmap obstacle-layer gap, taint proven nil.

This file is what pays those debts. **§1 is Task 1's first half: the
layer, the costmap, the headline re-drive.** Station furniture, tag
detection and staging arrivals follow in later sections as they are
measured.

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
