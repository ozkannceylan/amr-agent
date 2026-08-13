# Brief m4f-03 — forklift commissioning world and bringup

```
gate:                M4
agent:               sim
goal:                A commissioning arena world and a bringup launch exist so the
                     forklift model runs bridged end to end on the ROS side.
invariants_touched:  none
inputs:              [docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      sim/worlds/cell.sdf and sim/launch/cell_bringup.launch.py
                      (house style), agv/forklift/README.md (topic contract —
                      read it, do not edit it), docs/LESSONS.md (GZ_PARTITION)]
deliverable:         sim/worlds/forklift_arena.sdf,
                     sim/launch/forklift_bringup.launch.py,
                     sim/worlds/FORKLIFT_ARENA_EVIDENCE.md
done_when:           a headless run (GZ_PARTITION + ROS_DOMAIN_ID set) spawns the
                     forklift from agv/forklift/model.sdf into the arena via the
                     launch; the ros_gz_bridge argument list covers /clock,
                     /forklift/scan, the odometry, the joint states and the three
                     gz command topics (ROS→gz) with explicit types in the
                     cell_bringup style; every bridged topic is listed in the
                     evidence file with its measured rate quoted as ros2 topic hz
                     printed it; a scripted gz-topic traction pulse produces a
                     position change visible in the bridged odometry, transcribed
                     into the evidence file; git shows cell.sdf and
                     cell_bringup.launch.py untouched.
forbidden:           [modifying sim/worlds/cell.sdf or sim/launch/cell_bringup.launch.py
                      or anything under agv/ (its README is a read-only input),
                      Nav2, maps, external assets or meshes, GUI-dependent evidence,
                      launching the vehicle-side nodes (agv/forklift/launch owns
                      them), mentioning any deadline]
```

## Arena contract

- ≈24 × 16 m floor: open drive aisle, two or three static obstacle props
  (primitive crates/pillars) placed so one sits near the aisle for the stop-zone
  scenario, a marked pallet zone with one in-house primitive pallet (three boards,
  two blocks — no external mesh) and one load box on it.
- Perimeter low walls optional; keep the scene light for llvmpipe (no textures,
  default lighting).
- The fixed-equipment demo cell is NOT embedded — the coupled cell + vehicle
  scenario belongs to a later gate (roadmap M9); state this in a comment header.
- Launch pattern: gz sim server with the world, optional gui:=true argument,
  ros_gz_sim create for the model file, one ros_gz_bridge process with the explicit
  argument list, use_sim_time true. Follow cell_bringup.launch.py conventions,
  including the header comment stating what runs here and what deliberately does
  not.

Git: repo-local owner identity; pathspec-scoped commit of exactly the three sim/
files plus your report docs/reports/m4f-03-forklift-world-bringup.md; message style
`feat(sim): add the forklift commissioning arena and bringup`.
