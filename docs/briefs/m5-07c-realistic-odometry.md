# Brief m5-07c — IMU, wheel odometry and the fused pose estimate

```
gate:                M5
agent:               agv-ros2
goal:                the vehicle estimates its own pose the way a real AGV
                     does — wheel odometry from its own joints, an IMU, and a
                     filter fusing them — with Gazebo's ground truth demoted
                     from estimate to reference.
invariants_touched:  none. Invariant 10 is the one to watch: after this brief
                     there are two pose streams in the system and exactly one
                     of them owns `odom -> base_link`.
inputs:              [agv/forklift/model.sdf (tricycle geometry, joints,
                      the OdometryPublisher system),
                      agv/forklift/config.yaml (wheel radius, steer limit,
                      wheelbase),
                      docs/reports/m5-07b-odom-tf.md (the interim transform
                      and the seam it documents — read this first),
                      sim/worlds/WAREHOUSE_LANDMARKS.md (the degenerate
                      stretches this exists to make real),
                      sim/setup/CONTAINER_TOOLCHAIN.md]
deliverable:         agv/ — an IMU on the model, a wheel-odometry source, a
                     fused estimate owning the transform, and the evidence
                     that it drifts the way it should
done_when:           the model carries an IMU with stated noise
                     characteristics and its data is verified on its own
                     before anything consumes it; wheel odometry is computed
                     from the vehicle's OWN joint states through its tricycle
                     kinematics, with the derivation written down and checked
                     against a known motion; a fusion filter owns
                     `odom -> base_link` and the interim source from m5-07b is
                     retired in the same commit, leaving exactly one publisher
                     of that transform; Gazebo's ground truth remains
                     published under its unambiguous reference name and is
                     consumed by no estimator; and the evidence reports
                     MEASURED drift — position and heading error against the
                     reference over a stated distance and a stated
                     manoeuvre set, including at least one sustained turn,
                     because heading is where a tricycle's odometry actually
                     fails.
forbidden:           [feeding ground truth into the filter, or into anything
                      an estimator reads — that would recreate the circularity
                      this brief exists to remove; leaving two publishers of
                      `odom -> base_link`; tuning noise parameters until the
                      drift looks good (see the honesty rule); editing sim/,
                      plc/, hmi/ or bridge/; committing (the orchestrator
                      commits)]
```

## The honesty rule for the noise model

The temptation is to pick noise numbers that make SLAM succeed. Do the
opposite: choose them from what the modelled hardware would plausibly do — a
tricycle drive wheel that slips, a steer encoder with finite resolution, a
MEMS IMU with bias and random walk — state where each number came from, and
then report what the resulting drift IS, whether or not it is convenient.

If the drift turns out too small to exercise the degenerate aisles m5-08
measured, that is a finding to report, not a reason to inflate it. If it turns
out large enough that SLAM struggles, that is also a finding — and an
interesting one, because it is exactly the condition real installations solve
with reflectors. Either way the number is the deliverable and the tuning
argument belongs to the SLAM brief, not this one.

## Why this brief exists

Until now the vehicle's pose came from Gazebo — perfect, drift-free, and
therefore useless as a test of anything. Three things depend on this changing:
`slam_toolbox` uses the odometry as its motion prior, so a perfect prior masks
whether scan matching works; AMCL exists to correct odometry drift, so with no
drift it corrects nothing and proves nothing; and the localization error this
gate will report would be AMCL measured against its own input, which is
circular and would not survive review.

## Dependency

`robot_localization` is the standard ROS 2 answer for the fusion step and is
almost certainly not installed — m5-07 installed Nav2 and `slam_toolbox` only.
Adding it is a new dependency: propose it in your report with the package name
and version as `apt` prints them, install it, and record it in
`sim/setup/CONTAINER_TOOLCHAIN.md`'s pattern — but note that file is `sim/`'s,
so REQUEST the entry in your report rather than writing it. If you judge that
a smaller hand-written filter is the better answer for this vehicle, say why
and what it costs in credibility; the standard package is the default.

## Notes

Read m5-07b's report first — it documents the seam this brief plugs into, and
its interim transform is the thing you retire.

Verify each piece on its own before wiring the next: the IMU's data alone, the
wheel odometry alone against a known motion, then the fusion. That is the
owner's sequencing rule for this gate and this brief is the clearest place it
applies.

ROS 2 Jazzy and Gazebo 8.11.0 work here. Isolate with BOTH `GZ_PARTITION` and
`ROS_DOMAIN_ID`; keep it headless. Drive runs to completion with bounded
polling and clean up every process.

Do not commit. Leave files modified and write your report to
docs/reports/m5-07c-realistic-odometry.md.
