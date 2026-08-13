# Brief m5-08c — adversarial review of the SLAM mapping run

```
gate:                M5
agent:               judge (fable), read only
goal:                attack the SLAM run's result and its evidence, so that
                     AMCL is not built on a map or a claim that does not hold.
invariants_touched:  none (read only)
inputs:              [docs/reports/m5-08b-slam-mapping.md,
                      sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md,
                      sim/worlds/WAREHOUSE_LANDMARKS.md (the prediction),
                      sim/config/slam_toolbox_warehouse.yaml,
                      sim/scenarios/warehouse_mapping_route.py,
                      sim/scenarios/tools/mapping_evidence.py,
                      sim/maps/warehouse/ (the artifacts),
                      agv/forklift/EVIDENCE_ODOMETRY.md (the drift the map
                      was built against),
                      sim/launch/warehouse_slam.launch.py]
deliverable:         docs/reports/m5-08c-slam-judge.md
done_when:           each line of attack below has been pursued and answered
                     with evidence from the repository, not from reasoning
                     alone; findings are ranked by severity with a concrete
                     failure scenario each; anything that must be fixed BEFORE
                     AMCL is built on this map is marked as blocking and
                     separated from what can follow later; and each claim that
                     survives the attack is stated as surviving, with the
                     attack shown.
forbidden:           [editing any repository file except your own report;
                      re-running the mapping route (that is a fix's job, not a
                      review's) unless a measurement is the only way to settle
                      a finding, in which case say so and isolate with both
                      GZ_PARTITION and ROS_DOMAIN_ID; accepting a number
                      because it appears in two documents — check it against
                      the artifact; committing]
```

## Lines of attack

1. **Is the map good, or does it merely look good?** 0.185 m rms and 0.014 m
   final error are quoted for the whole run. Check how they were computed, by
   what instrument, against what reference, and whether the final-error figure
   is a fair statistic or the accident of where the route ended. A closed
   circuit that returns to its start flatters a final-error number.

2. **Was the prediction actually tested?** `WAREHOUSE_LANDMARKS.md` named three
   degenerate stretches; the run reports small errors across all three and
   concludes the finding is a "5 m dead-reckoning budget" rather than a
   matcher failure. Attack that reading. Was the vehicle ever in a state where
   the degeneracy could bite — speed, dwell, heading error on entry? The report
   itself names dwell as untested. Establish whether the conclusion is
   supported or whether the run simply moved fast enough to outrun the problem.

3. **The route.** It is scripted, closed, and its follower closes its loop on
   ground truth. Does driving a route designed to create revisits, at constant
   speed, with a perfect driver, make the map easier than any real
   commissioning drive? Say what the route cannot show. Note also that the
   route bypasses the PLC, so it is not evidence about the command path — check
   nothing in the evidence claims otherwise.

4. **The artifacts.** The `.pgm`/`.yaml` pair and the serialised pose graph
   are what AMCL and any resumed mapping will consume. Verify the map's
   metadata against the world file independently: resolution, origin,
   dimensions, occupied/free thresholds, and whether the origin convention
   matches what AMCL expects. A map whose origin is subtly wrong localises
   consistently and wrongly.

5. **The parameters.** `slam_toolbox_warehouse.yaml` carries non-default
   values. For each, check the justification actually explains the value and
   is not a restatement of the parameter name. Look in particular for any
   parameter that was changed because the map improved rather than because the
   warehouse warranted it — the brief forbade that and the report should show
   it was honoured.

6. **The transform story.** The report claims `Publisher count: 1` with the
   bringup alone and 3 with SLAM beside it, with one new disjoint edge. Verify
   the claim's shape: who owns `map -> odom`, whether anything can publish a
   competing edge, and what happens to the tree if slam_toolbox is not
   transitioned — the report notes it is a lifecycle node that maps nothing and
   warns nothing until transitioned, which is a trap for whoever runs this next.

7. **The parked-EKF finding.** ~0.0023 rad/s of heading integrated while
   stationary rotates the finished map frame away from the building if the
   stack idles before driving. Establish how large this actually is over a
   plausible idle, whether the committed map is affected, and whether AMCL
   inherits the problem.

8. **What AMCL will need that this run did not produce.** Look ahead one
   brief: is there anything about this map, this frame convention, or this
   evidence that will make the localization measurement ambiguous or
   circular? That measurement is a gate criterion and this is the last cheap
   moment to catch a problem in its foundation.

## Output

Rank by severity. Mark clearly which findings BLOCK the AMCL brief and which
do not. For each: the claim attacked, a concrete failure scenario, the file
and line, and what you would change. A review that concludes the run is sound
is acceptable only if it shows the attacks that failed.
