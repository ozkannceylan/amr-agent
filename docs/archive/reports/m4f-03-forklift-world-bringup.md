# Report m4f-03 — forklift commissioning world and bringup

```
brief:               docs/briefs/m4f-03-forklift-world-bringup.md
status:              done
files_changed:       sim/worlds/forklift_arena.sdf
                     sim/launch/forklift_bringup.launch.py
                     sim/worlds/FORKLIFT_ARENA_EVIDENCE.md
                     docs/reports/m4f-03-forklift-world-bringup.md
invariants_touched:  none
open_questions:      see below
next_suggested:      wire the arena into the ADR 0008 command path, so a
                     setpoint reaches the vehicle through the PLC rather than
                     from a shell
```

## Done_when, against what was measured

Every figure is quoted in `sim/worlds/FORKLIFT_ARENA_EVIDENCE.md` as the tool
printed it. Run: WSL2, ROS 2 Jazzy, `gz sim 8.11.0`, headless server only,
llvmpipe, `GZ_PARTITION=m4f03arena`, `ROS_DOMAIN_ID=42`.

| Criterion | Result |
|---|---|
| Headless run spawns the forklift into the arena via the launch | `Entity creation successful`; `gz model --list` shows 12 arena models plus `Forklift` |
| Bridge covers /clock, scan, odometry, joint states, three gz commands | 7 topics, types explicit, direction confirmed by `ros2 topic info` publisher/subscriber counts |
| Every bridged topic listed with its measured rate | `500.044 / 9.999 / 20.001 / 499.812` for the four gz→ROS topics; `20.001 / 19.999 / 19.999` for the three ROS→gz topics under a 20 Hz stimulus |
| Scripted gz-topic traction pulse visible in the bridged odometry | `odom_x` `-6.000000` → `-3.121976`; `twist_vx 0.480000`; position samples give `0.479998 m/s` against the commanded 4.0 rad/s at a 0.12 m wheel |
| `cell.sdf` and `cell_bringup.launch.py` untouched | `git status --porcelain` on both paths is empty; last commit touching them is `2dbc023`, unrelated to this work |
| Launch log clean | 19 lines, `ERROR=0 WARN=0`, reproduced on a final smoke run of the committed files |

The odometry figure cross-checks the vehicle rather than only the arena:
m4f-02 measured `0.4799968925779739` m/s for the same command on its own
throwaway world, so spawning the model into a 24 x 16 hall changed nothing
about it.

## The three facts the brief required to be honoured

1. **`gz-sim-sensors-system` with `ogre2` is loaded**, and the scanner
   publishes: 181 samples, `9.999` Hz, `6.830417` m dead ahead against the
   `6.83` m the crate geometry predicts and `7.900483` m to each wall against
   the `7.90` m the wall geometry predicts.
2. **`/forklift/joint_states` is bridged as-is** at the physics rate,
   measured `499.812` Hz in this 500 Hz world, and the figure is in the
   evidence file with the other six. The launch file states why it is not
   decimated: choosing a rate for a consumer is logic, and the bridge holds
   none.
3. **Rendering is llvmpipe**, read from the ogre2 log rather than assumed;
   the server ran headless, the scene carries no texture, no shadow and no
   mesh, and `LIBGL_ALWAYS_SOFTWARE` was left unset.

## One finding worth recording

**The gz `gpu_lidar` drops the sample at exactly `+-45 deg`, and it is the
sensor, not the bridge.** It first looked like a clean pattern because the
probe happened to sample both diagonals; dumping all 181 samples showed a
one-ray hole in the middle of an object returned continuously either side of
it (`4.481 / inf / 4.366`). It reproduces against a flat wall, it is not a
fixed bad index — turning the vehicle 180 deg recovers the same ray — and the
raw `gz topic -e -t /forklift/gz/scan` message already contains the `inf`, so
the bridge is translating faithfully.

It does not affect this gate: the stop-zone sector is `+-30 deg`, indices 60
to 120, and the seam sits outside it; and `obstacle_zone.py` judges validity
per sample rather than condemning a scan, so a single dropped ray is absorbed
by design. It is recorded because a consumer written later must not assume
every sample in this scan is finite.

## Open questions

1. **`sim/README.md` has no section for this arena.** It documents the
   warehouse world and the M3 cell, and a reader arriving at `sim/` will not
   find the forklift arena, its layout, its spawn default or how to run it.
   The file is inside this agent's write scope, but the brief names three
   deliverables and fixes the commit pathspec to them, so it was left alone
   rather than bundled. It needs its own brief.
2. **The `+-45 deg` dropout is not in the vehicle's contract table.**
   `agv/forklift/README.md` states the scan as 181 planar ranges without
   saying that a sample may be absent. That file is `agv/`'s and was read
   only. Requested, not written.
3. **`Pallet` and `LoadBox` were spawned but never lifted.** Their masses
   (20 kg and 30 kg) were chosen so that 490 N of added load sits under the
   mast controller's measured `i_min` clamp of 1500 N against an unloaded
   assembly weight of about 882 N. That arithmetic argues the load is
   plausible; it is not a measurement, and m4f-02's open question 3 (fork
   tuning is unloaded-carriage tuning) still stands.
4. **`SIGINT` to the launch pid did not bring the process group down inside
   6 s.** Every run finished the job by exact pid after checking `pgrep -af`.
   A scenario script for this bringup should plan for that rather than assume
   the signal is enough.
5. **The stop-zone geometry is placed but not exercised.** `AisleCrate`
   straddles the aisle centreline so a straight drive meets it head on, and
   the world file carries the arithmetic for where the zone trips (model
   origin at `x = -0.37`, 5.63 m from the spawn). Nothing in this run drove
   that far, and no PLC reaction exists yet.

## Requests outside this directory

- **Nothing was written outside `sim/` and this report.**
  `agv/forklift/README.md`, `model.sdf` and `config.yaml` were read as the
  topic and geometry contract and not edited; `docs/adr/0008` and
  `docs/roadmap.md` were read for the gate numbering.
- **No dependency was added.** The launch uses `ros_gz_sim`, `ros_gz_bridge`
  and `ament_index_python`, all already present and all already used by
  `cell_bringup.launch.py`.

## Notes

- The world is strict-XML parseable (`xml.etree` and `gz sdf -k` both clean).
  The first draft was not: an ASCII layout diagram contained `--`, which the
  XML spec forbids inside a comment. That is the same defect LESSONS records
  for `cell.sdf`, caught here before commit rather than after.
- `git check-attr` confirms `eol: lf` on the launch file under the root
  `.gitattributes` rule `*.py text eol=lf`. `.gitattributes` was not edited.
- Six runs, each with its own `GZ_PARTITION` (`m4f03arena`, `m4f03scan`,
  `m4f03seam`, `m4f03seam2`, `m4f03raw`, `m4f03smoke`) and its own
  `ROS_DOMAIN_ID` (42 to 47, never 61). Both transports were isolated on
  every run because `ROS_DOMAIN_ID` does not isolate Gazebo. Each run
  signalled only pids it had started, matched against observed `pgrep -af`
  output, and the concurrent agent's processes were checked as untouched
  after every one.
