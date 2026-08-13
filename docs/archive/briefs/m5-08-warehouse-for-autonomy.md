# Brief m5-08 — the warehouse world as the M5 autonomy environment

```
gate:                M5
agent:               sim
goal:                sim/worlds/warehouse.sdf carries the forklift and enough
                     real structure at the navigation plane for SLAM to be
                     honest, with landmark availability MEASURED rather than
                     assumed.
invariants_touched:  none
inputs:              [sim/worlds/warehouse.sdf, sim/worlds/BRINGUP_EVIDENCE.md,
                      sim/launch/warehouse_bringup.launch.py,
                      sim/worlds/forklift_arena.sdf (the safety zone marking
                      and the GUI block are the patterns to follow),
                      agv/forklift/model.sdf and its EVIDENCE_SENSOR_* files
                      (read only), docs/roadmap.md row M5]
deliverable:         sim/worlds/warehouse.sdf, its launch, and a measured
                     landmark-availability evidence file
done_when:           the warehouse world spawns the forklift and bridges its
                     topics, proved by captured `ros2 topic hz` output on the
                     navigation lidar and odometry; the world carries the
                     safety zone marking pattern the arena established, so
                     M5's safety and autonomy demonstrations can be recorded
                     in ONE world; the retired platform's spawn path is gone
                     from the launch and BRINGUP_EVIDENCE.md is either
                     re-captured for the forklift or clearly marked as the
                     retired vehicle's historical record; the `VisualizeLidar`
                     GUI block is present as in the arena; and a
                     LANDMARK evidence file reports, from the navigation
                     lidar's own 1.80 m plane, how much structure is visible
                     from a set of sampled poses along the aisles and at the
                     intersections — with the degenerate stretches NAMED, not
                     removed.
forbidden:           [editing agv/, plc/, hmi/, bridge/ or docs/interfaces/;
                      adding structure whose only purpose is to make scan
                      matching easy — see the honesty rule below; changing the
                      forklift model or its sensors; running any timing or RTF
                      measurement while another agent is running the simulator
                      (LESSONS 2026-07-30); committing (the orchestrator
                      commits)]
```

## The honesty rule this brief turns on

A long, featureless aisle is a **degenerate direction** for scan matching. No
slam_toolbox parameter fixes it; real installations solve it with reflectors
precisely because geometry alone does not. So there are two ways to make SLAM
work here and only one of them is legitimate:

- **Legitimate**: model a warehouse the way a real warehouse is built — rack
  uprights and rack ends that break the wall line, cross-aisles, door frames,
  columns, a charging bay. Structure that exists because a warehouse has it.
- **Not legitimate**: scattering objects into the aisle because SLAM struggles
  without them. That produces a demonstration that proves nothing and would
  not survive a reviewer asking why the boxes are there.

Where the honest world still leaves a degenerate stretch, that is a **finding
to measure and report**, and the localization brief that follows will quantify
its cost. Name it; do not landscape it away.

## The measurement

From the navigation lidar's plane (1.80 m, 360°, 8.0 m range — read the model
for the current values rather than trusting these), sample poses along each
aisle and at each intersection and report per pose: how many returns are
finite, the angular spread of the structure seen, and whether the visible
structure constrains position in both axes or only one. A short analysis
script committed beside the evidence is welcome. The point is a map of where
localization will be strong and where it will be weak, produced BEFORE any
SLAM run, so the SLAM result can be read against a prediction instead of
being the only thing anyone looks at.

## Notes

The owner ruled 2026-07-30 that M5 autonomy runs in the warehouse world rather
than the commissioning arena: autonomy needs aisles and racks to be
meaningful, and M6 enlarges this same world to five loading and five unloading
stations, so the map artifact and the Nav2 tuning carry forward instead of
being discarded. The commissioning arena keeps its M4 role.

Two carried items are yours if they fall inside this work:
`sim/launch/warehouse_bringup.launch.py` still spawns the retired vehicle
through its vendor launch, and `sim/worlds/BRINGUP_EVIDENCE.md` is that
vehicle's bringup evidence — both were left by m5-09 because another agent
held the directory.

ROS 2 Jazzy and Gazebo 8.11.0 work in this container. Isolate with BOTH
`GZ_PARTITION` and `ROS_DOMAIN_ID`; another agent may be running the simulator
headless. Do not run a GUI and do not take RTF measurements in this brief —
they would be contended and worthless.

Do not commit. Leave files modified/untracked and write your report to
docs/reports/m5-08-warehouse-for-autonomy.md.
