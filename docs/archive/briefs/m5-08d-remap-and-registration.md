# Brief m5-08d — rebuild the map, register it to the world, score absolutely

```
gate:                M5
agent:               sim
goal:                a map whose frame does not depend on how long the stack
                     idled, a committed world-to-map transform derived from
                     the artifact, and an instrument that scores localization
                     absolutely rather than by anchoring on its first sample.
invariants_touched:  none. Invariant 10: the world-to-map transform has one
                     owner and one file, and it is derived, never asserted.
inputs:              [docs/reports/m5-08c-slam-judge.md findings 1, 2 and 3
                      (the three blockers — read these first),
                      docs/reports/m5-07d-stationary-handling.md (the cause
                      that has now been fixed),
                      sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md,
                      sim/scenarios/tools/mapping_evidence.py (the circular
                      instrument), sim/scenarios/warehouse_mapping_route.py,
                      sim/config/slam_toolbox_warehouse.yaml,
                      sim/launch/warehouse_slam.launch.py,
                      sim/maps/warehouse/ (the artifacts being replaced)]
deliverable:         sim/ — the bringup wired for the current estimator, a
                     rebuilt map, a registration tool with its committed
                     transform, and an absolute scoring mode
done_when:           **(a)** the warehouse bringup carries every node the
                     vehicle now needs — the IMU bridge, wheel odometry, the
                     IMU gate and the EKF — with the ground-truth TF bridge
                     off and one publisher of `odom -> base_link`, captured;
                     **(b)** the map is rebuilt over the same stated route
                     with a stack that did not idle-drift, and the artifact's
                     squareness against the building is MEASURED by fitting
                     its walls, reported as an angle and a residual, and
                     compared with the ~2.0° and ~0.4° shear the judge measured
                     in the previous artifact; **(c)** a registration tool is
                     committed that derives `T(world -> map)` from the
                     committed grid by wall fitting, prints the transform and
                     its residual, and is re-runnable — the report states the
                     transform and the residual and says plainly that it must
                     be re-derived for every regenerated map; **(d)**
                     `mapping_evidence.py` gains an ABSOLUTE scoring mode that
                     uses that committed transform and performs NO per-run
                     anchoring, with the existing anchored mode kept, renamed
                     so nobody reaches for it by accident, and documented as
                     valid for mapping drift and invalid for a localization
                     score; and **(e)** the old artifacts and any figure
                     derived from the anchored instrument are superseded in
                     place rather than silently replaced.
forbidden:           [editing agv/ (the estimator is settled — read it);
                      feeding ground truth into slam_toolbox or the EKF;
                      loosening any slam_toolbox acceptance parameter — the
                      judge verified the flattering knobs are at defaults and
                      they stay there; asserting a world-to-map transform
                      instead of deriving it; deleting the previous evidence
                      rather than superseding it; committing (the orchestrator
                      commits)]
```

## The three blockers this closes

**Finding 1.** The committed grid is rotated ~2.0° from the building with
~0.4° of internal shear, and the −2.82° in the previous evidence prose was a
single-sample frame relation at drive start, not the artifact's orientation.
The cause — the estimator integrating heading through the idle before the
drive — is fixed in `agv/` as of m5-07d, measured 0.0000° over both a 60 s and
a 240 s idle. So the rebuild should come out square; **measure it rather than
assume it**, and report the number whatever it is. Residual shear after the
rebuild is a finding about the mapping, not a failure of this brief.

**Finding 2.** `mapping_evidence.py analyse` anchors the estimate onto truth
at the first sample. For mapping drift that is right. For a localization gate
it is circular: an AMCL that is consistently 0.3 m wrong scores near zero.
AMCL must be scored against a transform fixed BEFORE the run and derived from
the artifact, not from the run.

**Finding 3.** Every degenerate-stretch crossing entered with ≤0.14 m and ~1°
of error at 0.80 m/s and never stopped — the run outran the degeneracy rather
than surviving it. That is the AMCL brief's problem to test, but this brief
must leave it testable: whatever route and instrument you produce has to be
able to express a dwell and a reverse inside a named stretch.

## On the registration tool

It is the smallest piece of this brief and the most load-bearing, because
every localization number the gate reports will pass through it. Fit the
walls of the committed grid, derive the rigid transform to the world file's
own geometry, print it with its residual, and state the residual honestly — if
no rigid transform fits better than some bound, that bound is the floor under
every subsequent measurement and must be said out loud rather than buried.

Keep it plain: standard-library Python, no new dependency, re-runnable, and
committed beside the map it registers so the pair travels together.

## Notes

The route may be reused as it stands; it is stated, reproducible and its
follower does not leak ground truth into any estimator. If you change it, say
what changed and why, and re-state the distance and the turning.

`.gitattributes` already covers `*.pgm`, `*.posegraph` and
`sim/maps/**/*.data` — verify rather than assume before the new artifacts land.

ROS 2 Jazzy, Gazebo 8.11.0, `slam_toolbox 2.8.5`. Isolate with BOTH
`GZ_PARTITION` and `ROS_DOMAIN_ID`; keep it headless. `async_slam_toolbox_node`
is a lifecycle node that maps nothing and warns nothing until transitioned —
the previous run recorded that trap and your bringup should not re-set it.
Every consumer needs `use_sim_time:=true`.

Do not commit. Leave files modified/untracked and write your report to
docs/reports/m5-08d-remap-and-registration.md.
