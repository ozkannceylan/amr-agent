# Brief m5-07b — the odom → base_link transform

```
gate:                M5
agent:               agv-ros2
goal:                the vehicle publishes odom → base_link, so SLAM and Nav2
                     have the motion estimate they require.
invariants_touched:  none
inputs:              [agv/forklift/model.sdf (the OdometryPublisher system),
                      agv/forklift/scripts/sensor_tf.py and
                      check_sensor_frames.py (the TF work m5-06 landed),
                      agv/forklift/EVIDENCE_SENSOR_TF.md,
                      docs/reports/m5-06-measurement-channel.md (open question:
                      odom → base_link published by nothing)]
deliverable:         agv/ — the transform published and its correctness shown
done_when:           `odom → base_link` is published continuously while the
                     vehicle moves, at a rate stated as measured; the full
                     chain `map` (absent for now) ← `odom` ← `base_link` ←
                     each sensor frame resolves under tf2, shown by a captured
                     lookup rather than asserted; the frame names agree with
                     what a Nav2/slam_toolbox configuration will expect and
                     the choice is stated (gz-sim scopes frame ids, so say
                     what the published names actually are); and the
                     transform is shown to track real motion — drive the
                     vehicle and show the transform moving with it, with the
                     residual against the ground-truth odometry topic
                     reported as a number.
forbidden:           [publishing a static odom → base_link; introducing a
                      second source of the same transform (invariant 10 — if
                      gz-sim's OdometryPublisher can publish it, use that
                      rather than adding a node that recomputes it, and say
                      which you chose and why); editing sim/, plc/, hmi/ or
                      bridge/; changing sensor poses or the vehicle's
                      kinematics; committing (the orchestrator commits)]
```

## Notes

gz-sim's `OdometryPublisher` already publishes the odometry topic at 20 Hz
with frames `forklift/odom` → `forklift/base_link`. Whether it also publishes
the TRANSFORM depends on how it is configured — check before writing anything,
because the cheapest correct answer is a configuration element rather than a
node. If a node is genuinely needed, it consumes the existing odometry rather
than recomputing pose from joint states: one owner per datum.

Note the ground-truth caveat already recorded in the repository — this
odometry is Gazebo's ground truth, not a wheel-odometry estimate with drift.
That is fine for M5 and it is also an opportunity: it gives the localization
brief a reference to measure AMCL against. But say plainly in the evidence
that the transform carries no odometry error, because a reader who assumes
realistic drift would misread every localization figure that follows.

ROS 2 Jazzy and Gazebo 8.11.0 work in this container. Isolate with BOTH
`GZ_PARTITION` and `ROS_DOMAIN_ID`. Keep it headless — no GUI, no RTF
measurement (another agent may be running the simulator).

Do not commit. Leave files modified and write your report to
docs/reports/m5-07b-odom-tf.md.
