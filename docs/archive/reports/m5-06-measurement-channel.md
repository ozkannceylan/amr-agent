# Report m5-06 — the measurement channel, the process consumer, and sensor TF

```
brief:               docs/briefs/m5-06-measurement-channel.md
status:              done
files_changed:       agv/forklift/model.sdf
                     agv/forklift/config.yaml
                     agv/forklift/README.md
                     agv/forklift/launch/vehicle.launch.py
                     agv/forklift/scripts/obstacle_zone.py
                     agv/forklift/scripts/sensor_tf.py            (new)
                     agv/forklift/scripts/check_sensor_frames.py  (new)
                     agv/forklift/scripts/obstacle_matrix.py      (new)
                     agv/forklift/EVIDENCE_SENSOR_TF.md           (new)
                     agv/forklift/EVIDENCE_SENSOR_COVERAGE.md  (dated notes only)
                     agv/forklift/EVIDENCE_MODEL.md            (dated note only)
                     docs/reports/m5-06-measurement-channel.md
invariants_touched:  none
open_questions:      six, below; two are requests to sim/, one to
                     docs/interfaces/, and four of m5-04's are repeated
                     unchanged at the end
next_suggested:      m5-12 derives the OSSD-equivalent verdict from the same
                     device and takes the safe-channel identifier with it
```

## The channel names, which is what a downstream brief needs from this report

One device, two channels, and the names are built so the pair cannot be
confused when the second one arrives:

| Device | Channel | Transport | Name |
|---|---|---|---|
| `safety_scanner_front` | measurement (**non-safe**) | gz | `/forklift/gz/safety_scanner_front/measurement` |
| `safety_scanner_front` | measurement (**non-safe**) | ROS 2 | `/forklift/safety_scanner_front/measurement` |
| `safety_scanner_rear` | measurement (**non-safe**) | gz | `/forklift/gz/safety_scanner_rear/measurement` |
| `safety_scanner_rear` | measurement (**non-safe**) | ROS 2 | none today; `/forklift/safety_scanner_rear/measurement` when a consumer exists |
| either | **safe** (OSSD-equivalent) | **none, ever** | not a topic on any transport — m5-12 derives it and the PLCSIM Advanced API carries it |
| `nav_lidar` | single channel, non-safe | gz / ROS | `/forklift/gz/scan_nav` → `/forklift/scan`, unchanged |

The rule that makes them un-confusable is one sentence, and it is written
into `model.sdf`, `config.yaml`, `README.md`, the launch file and the
node: **every channel a subscriber can reach is a measurement channel and
says `measurement` in its own name; the safe channel has no topic on
either transport, ever.** `check_sensor_frames.py` §4 checks both halves
mechanically — that every reachable scanner channel ends in
`/measurement`, and that no topic name anywhere matches `ossd`, `safe_`
or `protective`.

Two consequences for whoever cites this:

- **The bridge configuration needs no change from this brief.** It maps
  `/forklift/obstacle/in_stop_zone` and `/forklift/obstacle/min_distance`,
  and both keep their names, types, rates and polarity. What moved is the
  source *behind* them.
- **The safe channel's identifier is not mine to coin.** It is a PLC tag,
  so it belongs in `docs/interfaces/` under invariant 10 and CLAUDE.md §9's
  PascalCase rule. Open question 3 asks for it, with the one constraint
  this brief does impose: it must not reuse the word `measurement`, and
  it must never appear as a topic.

## What changed, in four sentences

1. `obstacle_zone.py` now subscribes to the front safety scanner's
   measurement channel instead of `/forklift/scan`, so the M4 comfort
   stop is back on a low plane (0.15 m, against the 0.25 m it was
   demonstrated on) instead of the navigation lidar's 1.80 m.
2. The front measurement channel is bridged into ROS; the rear one is
   not, because nothing consumes it, and neither device's safe channel is
   a topic at all.
3. `scripts/sensor_tf.py` publishes `/tf_static` for
   `safety_scanner_front_link`, `safety_scanner_rear_link` and
   `nav_lidar_link`, reading every number out of `model.sdf` at start-up.
4. `scripts/check_sensor_frames.py` and `scripts/obstacle_matrix.py` make
   the two claims above checkable rather than asserted, and
   `EVIDENCE_SENSOR_TF.md` is the dated run of both.

## The one change the new aperture forced, stated explicitly

The evaluator gained `obstacle.sector_centre_rad = −0.7853982`. The
sector is centred on the **vehicle's** driving direction, but scan angles
are measured in the **sensor's** frame, and this sensor is mounted on a
chassis corner at +45°. Leaving the centre at zero — correct while the
source was a sensor at yaw 0 — would have watched the diagonal 15…75° off
the bow and reported it as straight ahead. The matrix case `obstacle at
+45 deg (scan zero)` is that failure, and it returns `False / 5.000`.

Everything else in the contract is unchanged and was re-run: stop
distance 1.20 m, timeout 0.50 s, sector ±30°, and the three sample
classes exactly as `m4f-02c`/`m4f-04i` left them, including beyond-range
as a measurement rather than an absence. Two figures move and both belong
to the sensor rather than to the evaluator: the clear-horizon value is
now **5.50 m** (the front scanner's `range_max`, not 8.00 m) and the
sector holds 60 samples at 1.0036°/sample. **5.50 m is inside
`opcua-nodes.md` §10.5's 0.05–8.10 m plausibility window, so this
consumer owes the interface layer nothing.**

## What was exercised live, and what was only checked statically

Gazebo and ROS 2 **are** runnable in this container (the m5-07 toolchain
brief landed while this one ran), so more was exercised than the brief
allowed for. Everything below is container evidence; the owner's WSL host
has never run this configuration.

**Live, in `sim/worlds/forklift_arena.sdf`, headless, `GZ_PARTITION` and
`ROS_DOMAIN_ID` both isolated:**

- The full launch: server, spawn, bridge, `sensor_tf`, `forklift_io`,
  `obstacle_zone`. Front measurement channel at `9.940` Hz, `/forklift/scan`
  at `9.793` Hz.
- `/tf_static` carries all three transforms, each matching `model.sdf` to
  `0.00e+00` in translation and quaternion; `tf2` resolves all three from
  `forklift/base_link`; each scan's `header.frame_id` **is** the frame
  published for it. 28 checks, 0 failing.
- **The ruling's whole point, measured in one run:** the forklift parked
  0.85 m from `AisleCrate` (a 0.90 m cube). The measurement channel
  returns `0.8500197` m and `obstacle_zone` publishes `in_stop_zone=True,
  min_distance=0.850`; the navigation lidar, same sector, same instant,
  reports **60 of 60 samples clear beyond range** and would have
  published `False` at 8.00 m in front of that crate.
- The 20-case evaluator matrix, real node in its own process, PASS.

**Static, no simulator:** the four-way agreement between `model.sdf`,
`config.yaml`, `README.md` and the transform derivation (19 checks, 0
failing), and `sensor_coverage.py` re-run to confirm the topic renames
left it working.

**Not exercised at all:** SLAM, Nav2, `odom → base_link`, the rear
channel on ROS, a moving vehicle, and the render cost of three scanners.

## Two decisions taken inside the brief, with their reasons

**One SDF-reading TF node rather than a URDF or three static publishers.**
A URDF plus `robot_state_publisher` would be a second geometric
description of a vehicle that already has one, kept equal to the first by
hand — the thing invariant 10 exists to prevent. Three
`static_transform_publisher` processes put the poses in a launch file, in
triplicate, with nothing checking them. The node reads `model.sdf`, so
the agreement is structural; and because that alone would make any check
of it tautological, `check_sensor_frames.py` compares the derivation
against the README table a person maintains and the `config.yaml` mirror,
not against itself. A URDF becomes the right answer the day TF is needed
for the **moving** joints; at that point this node is deleted, not kept
beside it.

**The rear measurement channel is not bridged.** A measurement channel
goes onto the process network when something on that network consumes it,
and not before. Bridging an unconsumed one invites the subscriber that
must never appear — a navigation consumer.

## Open questions

1. **Request to `sim/`: `sim/setup/CONTAINER_TOOLCHAIN.md` §6 now names
   two topics that no longer exist.** Its "known gap" section says the
   model publishes `scan_safety_front`, `scan_safety_rear` and `scan_nav`.
   The first two are now
   `/forklift/gz/safety_scanner_front/measurement` and
   `/forklift/gz/safety_scanner_rear/measurement`; `scan_nav` is
   unchanged. Its §4 run recipe quotes the old names too, but that is a
   dated capture and should stay as run. `sim/` is on this brief's
   forbidden list.
2. **Request to `sim/`: m5-04's open question 3 is unaffected but still
   open.** `sim/launch/forklift_bringup.launch.py` still bridges
   `/forklift/gz/scan`; the fix is still `/forklift/gz/scan_nav`, in the
   bridge list, the remap list and the header table. Nothing this brief
   renamed changes that fix. Whether that launch file should also carry
   the front measurement channel is a `sim/` decision — without it,
   `obstacle_zone` under that launch file will publish its fail-safe
   `TRUE` for as long as it runs, which is correct behaviour and a
   confusing demonstration.
3. **Request to `docs/interfaces/`: the safe channel needs an
   identifier.** m5-12 will derive an OSSD-equivalent verdict per device
   and hand it to the F-program by tag name (ADR 0011 D2, fact F7). The
   tag belongs to the interface layer, not to `agv/`. The constraints
   from here: it must not contain `measurement`, it must never become a
   topic, and it should read as the device plus the field, e.g.
   `SafetyScannerFrontProtectiveFieldClear` — proposed, not decided.
4. **`odom → base_link` is published by nothing.** `sensor_tf.py`
   publishes only the static sensor transforms, which is all this brief
   asked for. The gz `OdometryPublisher` declares `forklift/odom` and
   `forklift/base_link` in its messages but no transform is bridged, so
   the tree is currently three leaves and no root motion. SLAM cannot run
   until that exists, and it is a localisation decision for the SLAM
   brief rather than a gap to plug here.
5. **A `TransformListener`'s buffer is not ready when the publisher
   starts.** The live check failed all three `tf2` lookups on one run and
   passed all three on the next, with an identical publisher: the
   listener holds its own subscription and fills its buffer
   independently. The check now waits, bounded. **Every future consumer
   of these frames inherits this** — Nav2 and SLAM must wait for the
   transform rather than assume it at start-up.
6. **The render cost of three scanners is still unmeasured**, and this
   brief added a fourth process to the stack. The two `topic hz` figures
   here are not that measurement.

### Repeated from `docs/reports/m5-04-sensor-layout.md`, so they are not lost

The brief asked for its open questions 2, 3, 4 and 5 to be carried
forward. 3 is subsumed by my item 2 above and is repeated here in its
original form anyway.

- **m5-04 #2 — request to `sim/`: the arena has nothing at the navigation
  plane.** Perimeter walls top out at 0.60 m; the only feature reaching
  1.80 m is `PillarSouth`. SLAM against one pillar is not SLAM. Either
  the arena gains height (walls to ~2.0 m, or tall racking) or M5
  autonomy runs in `warehouse.sdf` (racks 2.0 m, walls 2.5 m). Still
  true; §4 of `EVIDENCE_SENSOR_TF.md` is another instance of it.
- **m5-04 #3 — request to `sim/`:
  `sim/launch/forklift_bringup.launch.py` will break.** It hard-codes
  `/forklift/gz/scan` in its bridge argument list (line ~125), in its
  remap list (line ~139) and in its header topic table (line ~49). That
  gz topic no longer exists, so `/forklift/scan` will never appear and
  `sim/scenarios/run_forklift_rehearsal.py` will block on its 120 s wait
  for it. The fix is `/forklift/gz/scan` → `/forklift/gz/scan_nav` in
  both places, plus the header line.
- **m5-04 #4 — request to the interface agent, if the range is to grow.**
  The navigation lidar's 8.00 m max is bounded by `opcua-nodes.md`
  §10.5's 0.05–8.10 m window. A range that suits a 24 × 16 m arena needs
  that window widened first, in `docs/interfaces/`, and then the model
  follows — not the other way round (invariant 10). **Changed in one
  respect by this brief:** the window no longer constrains this sensor
  through `obstacle_zone`, which now reports 5.50 m from a different
  sensor, so the coupling is weaker than m5-04 recorded. Widening is
  still the interface layer's to decide.
- **m5-04 #5 — the mast has two contradictory representations.**
  Rendered: two 0.09 m rails. Physical: a 0.72 m slab. The simulated
  navigation lidar therefore sees *through* a body the vehicle would
  collide with — 8.9° of shadow against 29.0°. Reconciling them (narrow
  the collision to the rails, or give the slab a visual) changes either
  physics or appearance, so it was measured and reported rather than
  decided unilaterally.

## Notes

- Nothing outside `agv/forklift/` and this report was written. `sim/`,
  `bridge/`, `plc/` and `docs/interfaces/` were read where needed and
  left alone; the two `sim/` items above are requests.
- **No dependency added.** `sensor_tf.py` uses `tf2_ros`, which is
  already pulled in by the distro packages this project installs —
  checked rather than assumed: `apt-cache depends ros-jazzy-ros-base`
  gives `ros-jazzy-geometry2`, which depends on `ros-jazzy-tf2-ros`, and
  `dpkg -l` shows it installed at `0.36.21-1noble.20260615.145818`. The
  checkers use the standard library plus `PyYAML`, which this directory
  already required. Nothing was installed by this brief.
- Nothing committed, no branch created, no staging. The three
  `EVIDENCE_*.md` edits outside this brief's new file are **dated status
  notes only** — no measured figure in either record was altered.
- The scanners' poses, apertures, sample counts and ranges are untouched:
  `git diff` on `model.sdf` is topic names and comments only, and
  `sensor_coverage.py` re-runs unchanged.
