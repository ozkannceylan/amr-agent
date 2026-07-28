# Brief m4f-02 — in-house forklift model and vehicle-side nodes

```
gate:                M4
agent:               agv-ros2
goal:                An original tricycle forklift exists in agv/ as plain SDF with
                     gz built-in systems, plus the two vehicle-side ROS nodes, all
                     verifiable headless.
invariants_touched:  none
inputs:              [docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      sim/worlds/cell.sdf (house SDF style, joint-controller usage),
                      sim/launch/cell_bringup.launch.py (launch style),
                      docs/LESSONS.md (cb_* naming, GZ_PARTITION isolation,
                      affirmative plausibility), the contract below]
deliverable:         agv/forklift/ — model.sdf, config.yaml (named constants),
                     scripts/forklift_io.py, scripts/obstacle_zone.py,
                     launch/vehicle.launch.py, README.md, EVIDENCE_MODEL.md
done_when:           a headless gz-sim run (server only, GZ_PARTITION and
                     ROS_DOMAIN_ID set per LESSONS) shows: the model spawns; steer,
                     traction and fork joints each respond to their explicit gz
                     command topics (gz topic pub/echo transcript); with a throwaway
                     ros_gz_bridge invocation the two nodes publish
                     /forklift/fork_height, /forklift/linear_speed,
                     /forklift/obstacle/in_stop_zone and
                     /forklift/obstacle/min_distance at their declared rates
                     (ros2 topic hz output quoted as printed); the fork holds
                     position under gravity at zero command; the zone evaluator
                     reports in_stop_zone TRUE on invalid, non-finite or stale
                     (>0.5 s) scans; every constant lives in config.yaml, none
                     inline; EVIDENCE_MODEL.md records the run with the environment
                     table pattern used by bridge evidence.
forbidden:           [fetching, cloning or copying anything from
                      cangozpi/ROS2-Forklift-Simulation or the owner's fork (the two
                      reference values needed are already in ADR 0008), external
                      meshes of any origin, ros2_control or gz_ros2_control, xacro,
                      colcon packaging, new pip or apt dependencies, editing sim/ or
                      bridge/ or plc/ or docs/interfaces/, mentioning any deadline]
```

## Model contract

- Tricycle: front assembly = steer joint (revolute about z, ±1.31 rad) carrying the
  driven wheel (spin joint, wheel radius in config, ≈0.12 m); two passive rear
  wheels; chassis ≈1.4 × 0.9 m footprint with counterweight block and overhead
  guard; mast with carriage on one prismatic joint, travel 0…1.6 m; two fork tines
  fixed to the carriage. Primitive geometry only, tidy proportions and distinct
  colors (industrial orange body, dark mast).
- gz systems with EXPLICIT topic parameters (stable names, model-scoped defaults
  forbidden): JointPositionController on steer (topic /forklift/gz/steer_cmd, rad),
  JointController velocity on the drive wheel (topic /forklift/gz/traction_cmd,
  rad/s), JointPositionController on the mast prismatic (topic
  /forklift/gz/fork_cmd, m; gains tuned so motion approximates ≤0.15 m/s with a
  visible ramp — the hydraulic-lag feel), OdometryPublisher, joint-state publisher
  system, and a planar gpu_lidar: 181 samples, 180° forward FOV, 0.1…8 m, 10 Hz
  (llvmpipe budget — do not exceed).
- scripts/forklift_io.py (rclpy, callbacks named cb_*): subscribes
  /forklift/cmd/traction_speed (m/s → rad/s by wheel radius → gz traction topic),
  /forklift/cmd/steer_angle (clamp, pass through), /forklift/cmd/fork_speed
  (integrate to a position target, slew-limited, clamped 0…1.6 — zero command holds);
  derives and publishes /forklift/fork_height from the bridged joint states and
  /forklift/linear_speed from the bridged odometry, both Float64 at 10 Hz.
- scripts/obstacle_zone.py: from /forklift/scan publishes
  /forklift/obstacle/in_stop_zone (Bool) and /forklift/obstacle/min_distance
  (Float64) at a fixed 10 Hz; a sample counts only if finite AND inside
  [range_min, range_max] (affirmative validity); sector ±30° about forward; stop
  threshold 1.2 m (config); invalid/stale scan ⇒ TRUE and 0.0 — absence of data is
  an obstacle, the wire-NC philosophy carried into the vehicle layer.
- README.md first section "This layer must not access": OPC UA/asyncua, bridge/
  internals, fleet/, plc/, hmi/. Then a contract table: every gz topic and ROS topic
  this directory owns, for sim/ and bridge/ to consume.

Git: repo-local owner identity; pathspec-scoped commit of exactly agv/forklift/ plus
your report docs/reports/m4f-02-forklift-model.md; message style
`feat(agv): add the in-house forklift model and vehicle-side nodes`.
