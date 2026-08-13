# Brief m5-10 — Nav2 for the tricycle forklift, written from scratch

```
gate:                M5
agent:               agv-ros2
goal:                the forklift plans and follows paths autonomously in the
                     warehouse, with a configuration written for its actual
                     kinematics rather than inherited from anything.
invariants_touched:  none. ADR 0014 D1 is the constraint that shapes this:
                     the loop closes onboard and no motion value crosses the
                     OPC UA seam.
inputs:              [agv/forklift/model.sdf and config.yaml (the real
                      kinematics — wheelbase, steer limit, wheel radius,
                      footprint),
                      agv/forklift/amcl.yaml and launch/localization.launch.py
                      (the localization stack this builds on),
                      agv/forklift/EVIDENCE_LOCALIZATION.md (what
                      localization actually delivers, floor included),
                      sim/maps/warehouse/ (read only),
                      sim/worlds/WAREHOUSE_LANDMARKS.md,
                      docs/adr/0014-motion-control-locus.md,
                      docs/reports/mc-01-motion-control-locus-research.md
                      section I (the specified interface and its Jazzy traps)]
deliverable:         agv/ — the Nav2 configuration, its launch, the
                     Twist-to-tricycle conversion, and measured evidence
done_when:           the forklift navigates to commanded goals in the
                     warehouse world, with the planner and controller chosen
                     for a vehicle that steers and cannot rotate in place, and
                     every non-default parameter carrying one sentence of
                     justification; the Twist → (steer angle, drive speed)
                     conversion is derived from the vehicle's own geometry,
                     stated as a formula, and checked against a commanded
                     motion rather than asserted; the footprint is the real
                     polygon, not a radius, because the forks extend well
                     beyond the chassis; and the evidence reports MEASURED
                     results for at least: a straight aisle traverse, a goal
                     requiring a cusp or reverse segment, a goal in a named
                     degenerate stretch, and a goal the planner should refuse
                     — with what it did when it refused.
forbidden:           [migrating any parameter from the retired platform's
                      configuration (it was deleted with its vehicle and this
                      starts from empty); routing any velocity through the PLC
                      or the OPC UA seam (ADR 0014 D1 — the envelope gate is
                      m5-11's and comes after this); feeding either safety
                      scanner into a costmap or the planner; regenerating the
                      map or its registration; tuning until a goal succeeds
                      without recording what was changed and why; committing
                      (the orchestrator commits)]
```

## The kinematics, and why the defaults are wrong

A forklift steers on one driven wheel, has a minimum turning radius, cannot
rotate in place, and drives both drive-end-first and fork-first. Nav2's
defaults assume a differential base and will produce behaviour the vehicle
physically cannot execute.

From mc-01 §I and the Jazzy research, the traps that will otherwise cost a
day, each to be verified rather than trusted:

- The planner must emit reversible paths. `SmacPlannerHybrid` with
  `REEDS_SHEPP` does; Dubins is forward-only. `allow_reverse_expansion` is a
  **Lattice** parameter, not Hybrid-A*'s — reverse comes from the motion model.
- `RegulatedPurePursuit` rejects `use_rotate_to_heading: true` together with
  `allow_reversing: true`. For this vehicle rotate-to-heading must be false;
  it is not a preference.
- The default behaviour tree's `Spin` and `BackUp` recoveries assume a
  differential base. Both are kinematically illegal here.
- On Jazzy, `enable_stamped_cmd_vel` defaults false, so the topic carries
  `Twist`, not `TwistStamped`. Pin it explicitly rather than discovering it.
- The velocity smoother's default `feedback: "OPEN_LOOP"` limits acceleration
  against its own last command. Closed-loop against odometry is the correct
  setting here and matters more once m5-11's gate can attenuate commands.

## What the localization result means for this brief

`EVIDENCE_LOCALIZATION.md` measured steady-state rms 0.124 m with a max of
0.263 m, against an instrument floor of 0.141 m. So the vehicle's belief about
where it is carries roughly a quarter-metre of worst-case error that is real
and measured. Inflation, goal tolerances and any docking claim must be
dimensioned against that number, not against an assumption of perfect
localization — and the evidence should say which parameter was set from it.

## Notes

The goal-refusal case matters as much as the successes: a planner that
silently fails, or one that returns a path through a rack, is worse than one
that refuses. Record what refusal looks like from the outside.

Isolate with BOTH `GZ_PARTITION` and `ROS_DOMAIN_ID`; headless;
`use_sim_time` everywhere; bounded polling; clean up every process. Write
intermediate results into the evidence as you go — this queue has lost work
to interruptions three times.

Two known `sim/` defects you will meet and must not fix yourself (they are
requested in a parallel brief): `warehouse_slam.launch.py` carries a
lifecycle emit-before-register race, and the bringup has no `seed` argument.

Do not commit. Leave files modified/untracked and write your report to
docs/reports/m5-10-nav2-tricycle.md.
