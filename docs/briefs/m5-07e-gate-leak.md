# Brief m5-07e — the IMU gate leaks in post-drive idle

```
gate:                M5
agent:               agv-ros2
goal:                the standstill gate holds heading in the idle regime an
                     AMCL dwell test will actually sit in — idle AFTER a
                     drive — or the leak is explained and bounded.
invariants_touched:  none
inputs:              [agv/forklift/scripts/imu_gate.py, wheel_odometry.py,
                      agv/forklift/ekf.yaml,
                      docs/reports/m5-07d-stationary-handling.md (the
                      original fix and its idle evidence),
                      docs/reports/m5-08d-remap-and-registration.md §9 (the
                      measurement: +0.01° over 26.8 s pre-drive, +2.02° over
                      200.4 s post-drive, 0.61 °/min, 0.24 °/min excluding
                      settling; 92-97 % suppressed, not 100 %)]
deliverable:         agv/ — the leak diagnosed with its mechanism measured,
                     and either fixed or bounded with the bound stated
done_when:           the mechanism is established by measurement, not by
                     plausibility — candidate hypotheses at least: the gate's
                     0.50 s arming window admitting gyro samples around the
                     stop transition; encoder counts still settling after a
                     drive so the standstill verdict arrives late or flickers;
                     EKF velocity decay integrating a stale twist; the gate's
                     freshness window lapsing — each ruled in or out by a
                     captured measurement; the fix (or the explicit decision
                     not to fix) keeps m5-07d's honesty rules — no bias
                     estimation carried into motion, no ground truth in the
                     estimator, moving drift unchanged and re-shown on the
                     same profile; and the post-drive idle hold is re-measured
                     over at least 200 s with the number stated, whatever it
                     is.
forbidden:           [feeding ground truth into the estimator; touching the
                      datasheet noise numbers; changing SLAM parameters or
                      sim/ (read the evidence, do not re-run mapping);
                      declaring the leak fixed without the 200 s re-measurement;
                      committing (the orchestrator commits)]
```

## Why now

The AMCL brief is next, and the judge's finding 3 requires a DWELL measurement
inside a degenerate aisle — the vehicle stopped, for a while, exactly where
localization has the least to work with. That test sits in the one regime this
leak occupies: idle after a drive. At 0.61 °/min a two-minute dwell hands AMCL
a heading error of over a degree from the estimator alone, and the dwell test
would then measure the leak, not the localizer.

m5-07d's own idle evidence was honest but incomplete: both its idles were from
bringup, before any drive. The 26.8 s pre-drive figure (+0.01°) reproduces it;
the 200.4 s post-drive figure (+2.02°) is the new regime. Something about
having driven changes the gate's behaviour, and "something" is not a
mechanism.

Do not commit. Leave files modified and write your report to
docs/reports/m5-07e-gate-leak.md.
