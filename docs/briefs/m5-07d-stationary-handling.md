# Brief m5-07d — the estimator must not turn while the vehicle is still

```
gate:                M5
agent:               agv-ros2
goal:                the pose estimate stops accumulating heading while the
                     vehicle is stationary, so a map's frame no longer depends
                     on how long the stack idled before driving.
invariants_touched:  none
inputs:              [agv/forklift/ekf.yaml, scripts/wheel_odometry.py,
                      agv/forklift/EVIDENCE_ODOMETRY.md,
                      docs/reports/m5-07c-realistic-odometry.md,
                      docs/reports/m5-08c-slam-judge.md finding 4 (the
                      measured consequence)]
deliverable:         agv/ — stationary handling in the estimator and the
                     evidence that it works
done_when:           with the vehicle commanded to rest, the fused heading is
                     shown to hold over an idle of at least the length that
                     produced the committed map's error, measured and stated;
                     the mechanism is a physically justified one — the wheel
                     encoders reporting no motion is evidence the vehicle is
                     not rotating, so the gyro's reading in that condition is
                     bias — and the document says which mechanism was used and
                     why it is legitimate rather than convenient; moving
                     performance is shown NOT to have improved by the change,
                     or if it did, by how much and why; and the drift figures
                     in EVIDENCE_ODOMETRY.md are re-measured over the same
                     route and manoeuvre set so the before and after are
                     comparable.
forbidden:           [feeding ground truth into the estimator or into the
                      stationary test; tuning noise parameters — the datasheet
                      derivations from m5-07c stand and this brief changes the
                      estimator's handling of a state, not its noise model;
                      suppressing drift while moving (that is the drift the
                      gate exists to correct and hiding it would be a cheat);
                      editing sim/, plc/, hmi/ or bridge/; committing (the
                      orchestrator commits)]
```

## The finding this answers

The judge measured the committed warehouse map as rotated **~2.0°** from the
building, consistent with the estimator integrating roughly 0.13°/s of heading
through the idle window before the drive began — and every rebuild draws a new
random bias sign, so the angle is different each time. A map whose orientation
depends on how long someone waited before pressing go is not an artifact.

## Why the fix belongs here and not in a procedure

Telling the operator not to idle would work until the day someone idles. Real
vehicles solve this in the estimator: when the wheels report no motion the
vehicle is not turning, so what the gyro reports is bias, and the estimator
either stops integrating it or uses the interval to observe it. That is
standard practice, not a convenience, and it is the difference between a
result and a workaround.

State plainly in the evidence which mechanism you chose. If the estimator
package offers the behaviour through configuration, prefer that to new code —
one owner per datum, and a configuration element is easier to audit than a
node. If it does not, say so and show what you added.

## What must NOT improve

The drift while moving is the phenomenon this gate exists to correct: 5.21 m
and −17.18° over 106 m of driving with 1450° of turning. That number is
supposed to be large. If your change reduces it, say by how much and explain
the mechanism, because a stationary correction that also flatters the moving
case is doing something other than what it claims. Re-measure over the same
route and manoeuvre set so the comparison is honest.

ROS 2 Jazzy and Gazebo 8.11.0 work here. Isolate with BOTH `GZ_PARTITION` and
`ROS_DOMAIN_ID`; keep it headless. Every consumer needs `use_sim_time:=true`.

Do not commit. Leave files modified and write your report to
docs/reports/m5-07d-stationary-handling.md.
