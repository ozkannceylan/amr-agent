# Report m5-04 — safety scanner pair and navigation lidar, with measured coverage

```
brief:               docs/briefs/m5-04-sensor-layout.md
status:              done
files_changed:       agv/forklift/model.sdf
                     agv/forklift/config.yaml
                     agv/forklift/README.md
                     agv/forklift/launch/vehicle.launch.py
                     agv/forklift/EVIDENCE_MODEL.md   (status note only)
                     agv/forklift/EVIDENCE_SENSOR_COVERAGE.md   (new)
                     agv/forklift/scripts/sensor_coverage.py    (new)
                     docs/reports/m5-04-sensor-layout.md
invariants_touched:  none
open_questions:      seven, below; two of them need an owner ruling before the
                     next M5 brief and two are requests to other layers
next_suggested:      rule on open question 1 (what feeds the process comfort
                     zone now), then run the live confirmation brief
```

## What was built

Three `gpu_lidar` sensors, each on its own link with `<gz_frame_id>` naming
that link, replacing the single 180° scanner at `(0.72, 0, 0.25)`.

| Sensor | Pose (x, y, z, yaw) | Aperture, samples | Range | Why that pose |
|---|---|---|---|---|
| `safety_scanner_front` | 0.700, 0.450, 0.150, **+45°** | 275°, 275 @ 10 Hz | 0.10–5.50 m | The corner of the chassis footprint itself (1.40 × 0.90 → half extents 0.70, 0.45). Yaw +45° puts the 85° blind sector on the corner diagonal at bearing 225°, into the vehicle |
| `safety_scanner_rear` | −0.700, −0.450, 0.150, **−135°** | 275°, 275 @ 10 Hz | 0.10–5.50 m | The diagonally opposite chassis corner, blind sector at bearing 45°. Which diagonal is geometrically free and is stated as free: every shape crossing this plane is mirror-symmetric about y = 0 |
| `nav_lidar` | 0.550, −0.400, **1.800**, 0° | 360°, 360 @ 10 Hz | 0.10–8.00 m | The only band where a 360° aperture is worth its cost: above the guard roof (1.71) and below the mast crossmember (1.95). x = 0.55 stands over the front-right guard post; y = −0.40 is the largest offset keeping the post on the roof plate and puts the astern ray 0.04 m clear of the mast |

Two numbers came out of the model's geometry rather than the brief's envelope,
and both agree with it for reasons worth stating:

* **Scan plane 0.150 m** is not "about 150 mm", it is the midpoint of the only
  free window there is: the lowered tine top is at z = 0.100 (fork links at
  0.075, 0.05 m section) and the chassis underside is at z = 0.200 (box centred
  0.45, 0.50 m high). 50 mm of clearance either way.
* **Which diagonal** could not be derived, because the model is mirror-
  symmetric about y = 0 at that plane. That is written into the evidence and
  into `model.sdf` as a free choice rather than dressed up as a derivation.
  Mirroring both poses mirrors every residual and changes no measured figure.

Two design details that are correctness, not style: the aperture rotation lives
in the **link** pose with the sensor pose identity, so the frame
`<gz_frame_id>` names is also the frame the scan's angles are measured in; and
every housing finishes 10–20 mm **below** its own scan plane, so no sensor
renders its own mounting (checked by the script, section 1).

## The coverage evidence

`agv/forklift/EVIDENCE_SENSOR_COVERAGE.md`, computed by
`agv/forklift/scripts/sensor_coverage.py`, which reads `model.sdf` itself so
the figures follow the model instead of ageing beside it. **Every figure is
computed from geometry. Gazebo and ROS 2 are both absent from this container
and neither ran**; the evidence says so at the top and section 12 lists what a
live run owes. No new dependency: Python standard library only.

The measurement is made twice, and the difference is a finding. A `gpu_lidar`
renders `<visual>` geometry, so a `<collision>`-only shape is invisible to it —
and this model has one, the mast's 0.10 × 0.72 × 2.00 collision box whose
visual counterpart is two 0.09 rails. **Every claim is made on the physical
set (visual + collision), because it is the smaller one.**

Headline measured coverage, safety scanner pair, physical set:

| Measure | Value |
|---|---|
| Aperture union / overlap (direction only) | 360.0° / 189.9°, in two 95° lobes |
| Sight-line coverage at 3.0 m and 4.0 m | **360.0°, no gap** |
| at 2.0 m | 355.0°; one 5.0° gap at bearings 169.4–174.4° |
| at 1.0 m | 317.2° — but that circle passes through the fork envelope; see the perimeter measure |
| Vehicle outline offset 0.50 m and beyond | **100%** |
| offset 0.30 m | 99.0%; the 1.0% is 0.30 m past the left tine tip |
| offset 0.10 m | 93.9%; two of the causes are the 0.10 m `range_min` dead zones |
| All-round detection radius | **4.95 m** (worst bearing), 5.46 m mean, against the sensors' own 5.50 m |
| Planes | **coplanar**, both 0.150 m |
| Navigation lidar mast shadow | **29.0°**, 2.50 m wide at 5 m (physical); 8.9° as the simulated sensor will render it |

Residual sectors, all seven, each with its measured value, its cause and its
mitigation, are section 11 of the evidence. In short: **R1** the carriage
shadow at 169.4–174.4° (5.0° at 2 m, closed at 3 m, closed entirely once the
carriage lifts past 0.11 m, and *structural* — section 9 measures that no mount
angle removes it); **R2** the tines crossing the scan plane in the 50 mm travel
window 0.05–0.10 m, widening the fork-end gap to 20.2°; **R3** load occlusion,
39.9° in the load direction, **stated as a residual and never as solved**, with
the ISO 3691-4 handling (reduced field plus creep, 0.3 m/s cap with muted
personnel detection) named as the mitigation; **R4** the 0.10 m `range_min`
annulus at each corner; **R5** the navigation lidar's 29.0° mast shadow,
narrowed by the lateral offset and widened by a carriage above 1.20 m of
travel; **R6** the 4.95 m all-round reach against a 5.50 m sensor range; **R7**
the simulated-versus-physical occluder divergence itself. Two sectors were
looked for and are absent — the overhead guard reaches neither scan plane, and
the steer wheel at either lock changes no measured arc.

The phrase "no blind spots" appears nowhere, and no sector is claimed covered
by construction.

## Decisions taken inside the brief, with their reasons

**The two safety scanners are declared but not bridged into ROS.** Their gz
topics are in `model.sdf`, `config.yaml` and the README contract table, but
`vehicle.launch.py` does not carry them into the ROS graph. The device they
model emits an OSSD pair on copper and its simulation analogue is the PLCSIM
Advanced API into the F-program (ADR 0011 decision 2). Bridging them would put
a safety device's measurement channel on the process network where any node
could subscribe and quietly become a consumer — which is the failure the
brief's "no navigation consumer" rule exists to prevent, one step earlier.

**`/forklift/scan` is now fed by the navigation lidar.** The topic's only
source was deleted by this layout, and the launch bridge would otherwise
dangle, so the one-line remap was made rather than shipping a broken vehicle.
The launch file was not in the brief's deliverable list; it is inside `agv/`
and inside scope, and the change is declared here rather than left to be found.
The consequence is open question 1.

**The navigation lidar's range was left at 8.00 m** even though the arena is
24 × 16 m, because `obstacle_zone` reports the scan's own `range_max` as its
clear value and `docs/interfaces/opcua-nodes.md` §10.5 plausibility-checks it
against 0.05–8.10 m. Raising it without moving that window first would make a
clear horizon read at the PLC as a transducer fault — the exact mistake
`EVIDENCE_MODEL.md` §6.1 warned about. Open question 4.

## Open questions

1. **What feeds the process comfort zone now? Owner ruling needed.**
   `/forklift/scan` moved from a 0.25 m plane to a 1.80 m plane, so
   `obstacle_zone.py` now evaluates its ±30° sector at chest height. In
   `forklift_arena.sdf`, walls 0.60 m and tallest crate 1.00 m, that sector
   will be empty and the zone will read clear — a functional regression of the
   M4 teleop comfort stop, recorded in the evidence §10a and in `config.yaml`
   beside the constants it governs. Three options, none taken here:
   (a) accept it for M5 and let Nav2's costmap own obstacle avoidance, retiring
   the comfort zone's PLC feed; (b) re-home it onto a safety scanner — which is
   what a real installation does, since a **warning field driving a speed
   reduction is a process function** (m5-01 facts block), but it reuses a
   safety device's channel as a process input and contradicts a reason line
   this brief was asked to record; (c) add a fourth low process scanner, which
   exceeds the three-sensor design and the render budget.
2. **Request to `sim/`: the arena has nothing at the navigation plane.**
   Perimeter walls top out at 0.60 m; the only feature reaching 1.80 m is
   `PillarSouth`. SLAM against one pillar is not SLAM. Either the arena gains
   height (walls to ~2.0 m, or tall racking) or M5 autonomy runs in
   `warehouse.sdf` (racks 2.0 m, walls 2.5 m). Not editable from this brief.
3. **Request to `sim/`: `sim/launch/forklift_bringup.launch.py` will break.**
   It hard-codes `/forklift/gz/scan` in its bridge argument list (line ~125),
   in its remap list (line ~139) and in its header topic table (line ~49).
   That gz topic no longer exists, so `/forklift/scan` will never appear and
   `sim/scenarios/run_forklift_rehearsal.py` will block on its 120 s wait for
   it. The fix is `/forklift/gz/scan` → `/forklift/gz/scan_nav` in both places,
   plus the header line. `sim/` is on this brief's forbidden list and another
   agent is working there, so it is requested and not done.
4. **Request to the interface agent, if the range is to grow.** The navigation
   lidar's 8.00 m max is bounded by `opcua-nodes.md` §10.5's 0.05–8.10 m
   window. A range that suits a 24 × 16 m arena needs that window widened
   first, in `docs/interfaces/`, and then the model follows — not the other way
   round (invariant 10).
5. **The mast has two contradictory representations.** Rendered: two 0.09 m
   rails. Physical: a 0.72 m slab. The simulated navigation lidar will
   therefore see *through* a body the vehicle would collide with — 8.9° of
   shadow against 29.0°. Reconciling them (narrow the collision to the rails,
   or give the slab a visual) changes either physics or appearance, so it was
   measured and reported rather than decided unilaterally.
6. **No TF exists for the three sensor frames.** Each scan names its own link
   and nothing publishes `forklift/base_link` → `safety_scanner_front_link` /
   `_rear_link` / `nav_lidar_link`. SLAM and Nav2 need it; the offsets are
   constants and are in the README table. Next brief's work, flagged so it is
   not discovered at bring-up.
7. **The render cost is not measured.** The ray budget goes from 181 on one
   sensor to 910 across three, on an llvmpipe host, and the 360° sensor is the
   expensive one to render. `model.sdf`'s own rule — nothing goes up without a
   measurement — is restated in the file and in the README, and the real-time
   factor this costs is owed by the live brief. Three sensor links also add
   3.8 kg to a 1105 kg vehicle (0.34%), which is noted rather than ignored
   because the controller tuning in `EVIDENCE_MODEL.md` was measured against
   the old mass.

## Notes

- Nothing outside `agv/forklift/` and this report was touched. `sim/`, `plc/`,
  `hmi/` and `bridge/` were read where needed and left alone.
- `EVIDENCE_MODEL.md` gained a dated status note only. The record itself is
  unaltered: it is a capture of a run, and the scanner it exercised no longer
  exists, so the note says which of its figures will not reproduce and which
  are untouched. Its §7 mechanical check — that `model.sdf` and `config.yaml`
  declare the same set of gz topics — was re-run against the new set and still
  passes.
- Every quoted block in the evidence file was checked line-for-line against the
  script's actual output; the two elisions are marked as elisions in place.
- No dependency added, nothing committed, no branch created.
