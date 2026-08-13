# m5-73 — the lidar visual never tracked the vehicle; it coincided with it, and now it tracks

    brief:               docs/briefs/m5-73-lidar-visual-regression.md
    status:              done
    invariants_touched:  none. model.sdf was not modified - no sensor pose,
                         angle, range or ray count changed, and git diff on the
                         file is empty. Nothing in plc/ or TIA was touched, no
                         safety timeout moved, and no PL, Category, SIL or PFH
                         is claimed or implied by anything added here.

## The one-line answer

**There is no regression commit, because the visual never tracked the vehicle
on this Gazebo build — the m5-05 captures looked right only because that
vehicle spawned at the world origin, where an origin-anchored fan and the
vehicle coincide. The mechanism is now isolated by probe, and a repair ships
that anchors the drawn fan to the sensor's live pose without touching the
model, the mounts or a single measured ray.**

## 1. The mechanism, proven with a purpose-built probe

On gz-sim 8.11.0 / gz-sensors 8.2.2, `gz.msgs.LaserScan.world_pose` is **the
sensor's static SDF `<pose>` relative to its parent link** — copied at load,
never composed with the model's pose, never updated. The probe
(`agv/forklift/evidence/m5-73/world_pose-probe.sdf`): one model spawned at
`(4, -2, yaw 0.7)` carrying two lidars, one with its mount declared in the
sensor element, one with the mount in the link and sensor pose identity (this
model's pattern). The first published its raw SDF pose uncomposed; the second
published identity; both stayed byte-identical after a read-back-verified
teleport. `model.sdf` writes every scanner mount into the **link** — its own
comment explains why: so the measurement frame and `<gz_frame_id>` agree — so
all three streams publish identity, and the GUI's `VisualizeLidar` plugin,
whose drawing anchor is that field, puts every fan at the world origin.

## 2. When it "worked", and what the owner remembers

The sensor SDF nesting is **unchanged since the first scanner commit**
(`4b623c1`) — every edit in `PLANT-CHANGE-INVENTORY.md` left it alone. What
changed is the spawn. The m5-05 arena captures (2026-07-30,
`assets/m5-forklift/beams-*.png`) were taken through `vehicle.launch.py` at
the config.yaml default spawn, `(0, 0, 0.05, yaw 0)` — **the origin** — and
m5-05's own open question 4 records that nothing was measured with the
vehicle moving. Inspecting those captures now, the fan converges at the
origin beside the parked vehicle, not at the sensor. The warehouse
composition (`3fb88a0`, spawn moved to mapped free space by `20efbb1`,
composed by `demo.sh`) starts the vehicle at `(-3.00, -5.50)`, and the
origin-anchored fan stayed behind — 3.00 m ahead, 5.50 m left, exactly where
the owner sees it. **The owner's memory is honest: the beams really did sit
on the vehicle. The coincidence moved, not the sensor.**

## 3. The fix

`agv/forklift/scripts/scan_viz_repeater.cc` — C++ because gz-transport has no
Python bindings on this stack (`gz.msgs10` ships, `gz.transport13` does not);
built on first use by `scan_viz_repeater.sh` into an uncommitted `build/`.
It subscribes `/world/<world>/pose/info`, composes the model's world pose
with the scanner link's model-relative pose, and republishes each of the
three scans on `/forklift/gz/viz/*` with **only `world_pose` replaced**. The
viewer points `VisualizeLidar`'s combo box at the viz topic. Started by
`vehicle.launch.py lidar_viz:=`, **default = the value of `gui`**, so
`demo.sh --gui` gets it with no demo.sh edit and a headless run pays nothing.
With no pose stream it publishes nothing and says so — absence, not a wrong
anchor. Visualization only: no vehicle node reads the viz topics, they are
never bridged onto ROS.

## 4. Done-when, demonstrated

Headless warehouse stack at the demo spawn, isolated
(`GZ_PARTITION`/`ROS_DOMAIN_ID`), evidence in `agv/forklift/evidence/m5-73/`
and `EVIDENCE_SENSOR_COVERAGE.md` §16:

| Where | Anchor vs mount-composed ground truth |
|---|---|
| pose A `(-3.000, -5.500, 0°)`, at rest | `(-2.3000, -5.0500, yaw 45.000°)`, error **0.0000 m / 0.00000 rad** |
| **driving**, 11.2 m at 0.5 m/s, 14 samples | anchor advances with the vehicle sample for sample (`drive-track.csv`); residual x offset equals drive speed x sequential-CLI sampling skew, y exact |
| after the drive, at rest, model `(8.2260, -5.5048)` | `(8.9262, -5.0551)` — exact to sub-millimetre |
| pose C = m5-72's second pose `(+1.500, -5.500, 45°)`, teleport verified by read-back | `(1.6768, -4.6868, yaw 90.000°)`, error **0.0000 m** |

The one pixel step not shown here: `VisualizeLidar` draws whatever a human
selects, so the on-screen confirmation is selecting the viz topic. The
plugin's anchor IS `world_pose` — that is what m5-72 measured when the fan
stood at the origin — so the corrected field is the corrected drawing.

## 5. The measurement did not move

* **m5-72's certified agreement reproduces with the repeater running** —
  same method, same two poses: median **0.072 m** (n = 155, committed 0.072
  at n = 156) and **0.016 m** (n = 114, committed 0.017 at n = 114); q90 and
  max match to the millimetre.
* **25 of 25** simultaneous scans, paired by header stamp between the front
  measurement channel and its viz twin: ranges, intensities and frame
  identical.
* The three measurement streams still publish `world_pose` identity —
  untouched, byte for byte what every prior consumer saw.
* `model.sdf` unmodified; the checker suite passes: `check_sensor_frames.py`
  prints `RESULT: PASS (23 check(s), 0 failing)`.

## 6. A checker defect found and fixed on the way

`check_sensor_frames.py`'s rule "every config gz_ topic exists in model.sdf"
was **already failing at HEAD** — the three m5-50 command topics
(`/forklift/gz/{steer,traction,fork}_cmd`) became software-side names when
the model's controllers moved to the actuator terminals, and the rule never
learned it (verified by running the checker against the HEAD config before my
edit: `FAIL ... extra: [fork_cmd, steer_cmd, traction_cmd]`). The check now
carries a named, justified software-owned exception set (m5-50's three, plus
m5-73's three viz topics), still fails on any new unexplained topic, and
gains a second check refusing two owners of one name if the model ever
publishes a software-owned topic itself.

## files_changed

| File | Change |
|---|---|
| `agv/forklift/scripts/scan_viz_repeater.cc` | new — the repeater |
| `agv/forklift/scripts/scan_viz_repeater.sh` | new — build-if-stale wrapper |
| `agv/forklift/launch/vehicle.launch.py` | `lidar_viz` argument (default = `gui`) and the repeater process |
| `agv/forklift/config.yaml` | the three `/forklift/gz/viz/*` topic names, with the ownership comment |
| `agv/forklift/scripts/check_sensor_frames.py` | section-4 rule corrected as in §6 |
| `agv/forklift/README.md` | scripts-table entry, VisualizeLidar passage, `lidar_viz` in the arguments list |
| `agv/forklift/EVIDENCE_SENSOR_COVERAGE.md` | new §16, dated: mechanism probe, the no-regression finding, the repair, both proofs |
| `agv/forklift/evidence/m5-73/` | probe world, both pose capture sets, drive track CSV, paired-stamp captures, analysis tools |
| `docs/reports/m5-73-lidar-visual-regression.md` | this report |

Untracked build output `agv/forklift/scripts/build/scan_viz_repeater` is left
in the tree and must not be committed. Two `agv/forklift/evidence/*/*.log`
files show modified in git status: they are being appended by the **owner's
live demo stack** (its PIDs are in their filenames), which was up throughout
this work and was not touched — all runs here were isolated under their own
`GZ_PARTITION` and `ROS_DOMAIN_ID`, and every process this brief started was
verified stopped by PID before finishing.

## invariants_touched

none (see header).

## Requests — work outside agv/

| # | Request | Owner | Blocking? |
|---|---|---|---|
| 1 | Add `agv/forklift/scripts/build/` to the root `.gitignore` (compiled repeater binary; agv cannot edit the root file) | infra | No, but soon — it will show untracked forever |
| 2 | `sim/worlds/warehouse.sdf` and `forklift_arena.sdf` carry `VisualizeLidar` comments describing topic selection; they should say the topic to select is `/forklift/gz/viz/*`, and why (one sentence, pointer to `EVIDENCE_SENSOR_COVERAGE.md` §16) | sim | No |
| 3 | `RUNBOOK.md` GUI notes likewise: the fan topic to select is the viz one; a measurement channel draws at the world origin by mechanism | infra | No — but it is the difference between the fix being used and being missed on stage |
| 4 | `assets/m5-forklift/README.md` describes the m5-05 beam captures as showing the scanners' apertures on the vehicle; §16.2's finding (origin-anchored fan on an origin-parked vehicle) qualifies two captions. A one-line provenance note would keep the gallery honest | infra (assets/ has no roster owner) | No |

## open_questions

1. **The pixel-level confirmation is one human topic selection away.** All
   anchor evidence is message-level; the inference to the drawn fan rests on
   the plugin's anchor being `world_pose`, which the fault itself
   demonstrated. The owner's next `demo.sh up --gui` session settles it by
   selecting `/forklift/gz/viz/safety_scanner_front` in the combo box.
2. **The viz topics are three more fixed names at n = 1** — same
   single-instance contract as the fixed gz topic names already recorded in
   `PLANT-CHANGE-INVENTORY.md`; stated in the config comment and the tool's
   header. They join that item's n = 2 re-scoping, they do not add a new one.
3. **VisualizeLidar's combo-box default is unchanged** (sorted entry zero is
   still the front measurement channel, `viz/` sorts after `safety…`), so
   m5-05's caption hazard — first beams shown are a safety scanner's
   measurement channel — now has a second face: the default selection also
   draws at the origin. Request 3 covers it.

## next_suggested

Have the owner run `demo.sh up --gui`, select the front viz topic, and watch
the fan ride the vehicle through one teleop pass — the fifteen-second visual
close of what this brief proved in messages.
