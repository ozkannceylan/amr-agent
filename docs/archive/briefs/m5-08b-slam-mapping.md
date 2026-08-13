# Brief m5-08b — the warehouse map, built by SLAM against real odometry

```
gate:                M5
agent:               sim
goal:                slam_toolbox builds a map of the warehouse from the
                     vehicle's own sensors and its own drifting odometry, and
                     the map becomes a versioned artifact.
invariants_touched:  none. Invariant 10: the map has one owner and one
                     authoritative file.
inputs:              [sim/worlds/warehouse.sdf and WAREHOUSE_LANDMARKS.md
                      (the landmark prediction this run is read against),
                      sim/launch/forklift_bringup.launch.py,
                      agv/forklift/ as landed by m5-07c — the IMU, the wheel
                      odometry, the EKF, and EVIDENCE_ODOMETRY.md's measured
                      drift (read only; agv/ is not yours),
                      docs/reports/m5-07c-realistic-odometry.md,
                      sim/setup/CONTAINER_TOOLCHAIN.md]
deliverable:         a warehouse bringup that carries the estimator stack, a
                     slam_toolbox mapping run, and the map committed as both
                     artifacts with its evidence
done_when:           a launch brings up the warehouse world with the forklift,
                     the IMU bridged, the wheel odometry and EKF running, and
                     `odom -> base_link` published by the EKF alone — shown by
                     a captured publisher count, not asserted; the ground-truth
                     bridge is OFF in this launch; slam_toolbox `online_async`
                     runs against `/forklift/scan` while the vehicle is driven
                     over a stated route; BOTH artifacts are saved — the
                     `.pgm`/`.yaml` pair for AMCL and the serialised pose graph
                     for resuming — and committed with the route, the
                     parameters and the tool versions recorded; and the result
                     is READ AGAINST the landmark prediction: where
                     WAREHOUSE_LANDMARKS.md predicted weak constraint, say
                     what actually happened there.
forbidden:           [editing agv/ (the estimator is m5-07c's and is settled),
                      feeding either safety scanner into SLAM, feeding
                      ground-truth odometry into slam_toolbox or into any
                      estimator, tuning parameters until the map looks good
                      without recording what was changed and why, claiming a
                      map is correct because it looks correct, committing
                      (the orchestrator commits)]
```

## What makes this run worth doing

Until m5-07c the vehicle's pose was Gazebo's ground truth and SLAM would have
succeeded everywhere regardless of whether scan matching worked. That is no
longer true, and the numbers are specific: over a 106 m route with 1450° of
turning the EKF accumulated **5.21 m and −17.18° of heading error**, and the
heading term is the one that bites — 17° at the mouth of a 3.80 m aisle points
the scan at the wrong wall. m5-08 predicted three degenerate stretches in the
fully-loaded east half where the only along-aisle information is a handful of
grazing returns.

So this run is a test with a prediction attached. Report what happened at
East A, East B and the east dock aisle specifically. If loop closure rescues
them, say so and say where the closure came from. If it does not, that is a
finding worth more than a clean map — it is the condition real installations
answer with reflectors, and naming it is what an honest gate does.

## Method notes

Drive the vehicle over a route you state in advance and record; do not steer
toward whatever makes the map improve. Whether the route is driven through the
teleop path or by a scripted stimulus is yours to choose — say which, because
a map built by a route no one can reproduce is not an artifact.

`slam_toolbox online_async` is the mode: `online_sync` blocks its scan
callback and will stall under software rendering. Warehouse-relevant
parameters are worth stating explicitly in the committed configuration —
resolution, minimum travel distance and heading, scan buffer size and its
maximum range, and the loop-closure group — with a sentence per non-default
saying why it is not the default.

Save both artifacts. The `.pgm`/`.yaml` pair is what AMCL will consume; the
serialised pose graph is what lets mapping resume rather than restart. Note
that `.gitattributes` already marks generated binaries explicitly — check that
the map files are covered before committing, because a misdetected binary is
corrupted silently.

`sim/scenarios/maps/` currently holds a stale map from the retired platform's
era. Rule on it: replace, relocate or delete, and say which — do not leave two
maps in a repository where one of them is nobody's.

Every consumer of this transform tree needs `use_sim_time:=true`, or it asks
for a stamp far in the future and reports a *missing transform* rather than a
misconfigured node. That failure looks like a TF bug and is not one.

ROS 2 Jazzy, Gazebo 8.11.0, `slam_toolbox 2.8.5`. Isolate with BOTH
`GZ_PARTITION` and `ROS_DOMAIN_ID`; keep it headless. Drive runs to completion
with bounded foreground polling; clean up every process.

Do not commit. Leave files modified/untracked and write your report to
docs/reports/m5-08b-slam-mapping.md.
