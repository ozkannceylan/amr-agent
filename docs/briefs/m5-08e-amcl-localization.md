# Brief m5-08e — AMCL against the frozen map, measured absolutely

```
gate:                M5
agent:               agv-ros2
goal:                the vehicle localizes against the committed warehouse map
                     with AMCL, and the localization error is measured
                     absolutely — through the committed registration, against
                     the named ground-truth reference, with the instrument's
                     floor stated beside every figure.
invariants_touched:  none. Invariant 10: the map and its registration have one
                     owner (sim/maps/warehouse/) and this brief consumes them
                     read-only.
inputs:              [sim/maps/warehouse/warehouse.{pgm,yaml} and
                      warehouse_registration.yaml (read only — T(world→map),
                      residual rms 0.040 m, MAX 0.141 m: the FLOOR),
                      sim/scenarios/tools/mapping_evidence.py --score absolute,
                      sim/launch/warehouse_slam.launch.py (the working
                      estimator bringup to mirror, read only),
                      agv/forklift/ as landed through m5-07e,
                      docs/reports/m5-08c-slam-judge.md findings 2 and 3,
                      docs/reports/m5-08d-remap-and-registration.md,
                      docs/reports/m5-07e-gate-leak.md (the dwell cost bound:
                      at most 0.33° for a dwell beginning at the stop, 0.000°
                      for one beginning >16 s after it),
                      sim/worlds/WAREHOUSE_LANDMARKS.md (the degenerate
                      stretches by name)]
deliverable:         agv/ — the localization launch, the AMCL configuration,
                     and the measured evidence
done_when:           AMCL consumes the navigation lidar and the EKF odometry
                     against the frozen committed map, with ground truth
                     reaching neither AMCL nor the EKF; the launch lives in
                     agv/forklift/launch/ as the vehicle's localization stack,
                     referencing sim/'s map artifacts read-only; the tricycle
                     motion model choice is stated and justified (the retired
                     platform's omni model is gone for a reason); and the
                     evidence reports, each figure beside the 0.141 m floor
                     and scored ABSOLUTELY through the committed registration
                     with no per-run anchoring:
                     (a) steady-state error over the full mapping route,
                     (b) convergence from a deliberately wrong initial pose,
                         with the offset stated,
                     (c) the named DWELL test — the vehicle driven into a
                         named degenerate stretch (East A), stopped for at
                         least 120 s, the error before, during and after
                         stated, and the estimator's own dwell cost bound
                         quoted beside the result,
                     (d) the named REVERSE test — the same stretch traversed
                         fork-first, since the route has never driven it
                         backwards and the scanners' geometry is asymmetric;
                     any figure at or below the floor is reported as "at the
                     instrument's resolution", never as a smaller number.
forbidden:           [feeding ground truth into AMCL, the EKF or any
                      estimator; regenerating or editing the map or the
                      registration (a mismatch is a stop-and-report, not a
                      rebuild); per-run anchoring anywhere; editing sim/
                      (request launch additions in the report if needed);
                      tuning AMCL until a test passes without recording every
                      non-default and why; feeding either safety scanner into
                      AMCL; committing (the orchestrator commits)]
```

## Why the criterion is shaped like this

The judge's findings built this brief. Finding 2: an anchored score is
circular for localization — a consistently wrong AMCL scores near zero — so
every figure goes through the committed T(world→map) and the 0.141 m residual
MAX is the floor below which this instrument cannot see. Finding 3: the
mapping run never let the degeneracy bite — it crossed the stretches at
0.8 m/s with a good heading and never stopped — so the dwell and the reverse
traversal are named measurements here, not incidental coverage.

The dwell result must be read against the estimator's own contribution: the
gate leak fix bounds the estimator's dwell cost at 0.33° when the dwell
begins at the stop and 0.000° after 16 s of settling. Quote that bound beside
the dwell figure so a reader can apportion what AMCL did and what it was
handed.

## Notes

`nav2_amcl` on Jazzy; the motion model for a tricycle is the differential
model (`nav2_amcl::DifferentialMotionModel`) — a tricycle steers, it does not
translate sideways, and the omni model would let particles do what the
vehicle cannot. Set `use_sim_time` everywhere. Non-defaults recorded with one
sentence each.

The reference stream is `/forklift/gz/tf_ground_truth`'s topic pair as m5-07b
named it — the reference, consumed by the scorer only, never by an estimator.
State in the evidence that the reference is exact (simulation truth), so the
error figures are attributable entirely to the localization chain.

Isolate with BOTH `GZ_PARTITION` and `ROS_DOMAIN_ID`; headless; bounded
polling; clean up every process. Write intermediate results into the evidence
as you go — this queue has lost work to interruptions three times.

Do not commit. Leave files modified/untracked and write your report to
docs/reports/m5-08e-amcl-localization.md.
