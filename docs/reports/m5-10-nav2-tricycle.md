# Report m5-10 — Nav2 for the tricycle forklift

```
brief:               docs/briefs/m5-10-nav2-tricycle.md
status:              done
files_changed:
  agv/forklift/nav2.yaml                                   (modified)
  agv/forklift/config.yaml                                 (modified)
  agv/forklift/README.md                                   (modified)
  agv/forklift/EVIDENCE_NAV2.md                            (rewritten)
  agv/forklift/scripts/cmd_vel_to_tricycle.py              (modified)
  agv/forklift/scripts/nav2_run.py                         (modified)
  agv/forklift/scripts/footprint_from_model.py             (new)
  agv/forklift/evidence/m5-10-probe-{a,b,c,d}-*.txt        (new, 4 files)
  agv/forklift/evidence/m5-10-footprint-derivation.txt     (new)
  agv/forklift/evidence/m5-10-convcheck.{txt,csv}          (new / rewritten)
  agv/forklift/evidence/m5-10-{a_straight, a_straight_lookahead120,
      a_straight_repeat, b_reverse, b_reverse_short, c_degenerate,
      d_refuse}-{goal,analyse,run,plan,stack}.*            (new, 35 files)
  agv/forklift/launch/navigation.launch.py                 (inherited, reviewed, left as is)
  agv/forklift/behavior_trees/navigate_to_pose_tricycle.xml (inherited, reviewed, left as is)
invariants_touched:  none. ADR 0014 D1 holds by construction: nothing this
                     stack starts is an OPC UA client and no motion value
                     leaves the vehicle's own ROS graph. The m5-11 envelope
                     gate is absent and is not anticipated anywhere except
                     as the `cmd_topic` launch argument. Neither safety
                     scanner reaches a costmap or the planner (invariant 1,
                     ADR 0011). No new dependency was added.
open_questions:
  1. `xy_goal_tolerance` (0.25 m, derived from the localization
     measurement) is BELOW the vehicle's own manoeuvring granularity: its
     smallest measured arc has a 1.29 m radius, so an approach that ends
     0.3 m out has no small move that closes the gap. One attempt in four
     spent 240 s shuffling 0.335 m from its goal with the steer at the
     stop. This needs a decision about what "reached" means for a
     non-holonomic vehicle — a tolerance dimensioned by manoeuvring
     granularity as well as by localization, or a goal checker that
     accepts an approach corridor rather than a circle. It is not a number
     to nudge quietly, and M6's station handshake depends on the answer.
  2. Every plan on the case A route begins with a 0.092 m Reeds-Shepp
     REVERSE primitive — one motion primitive, 1.6 % of the path — because
     start and goal are nearly collinear with a 28 mm lateral offset. RPP
     executes it as a reverse segment and both bad attempts on that route
     began with it. `reverse_penalty` was swept 2.0 / 3.0 / 5.0 / 10.0 on
     the planner bench: it does not remove the artefact, and raising it
     turns a clean 6 m reverse into a 9.5-10.2 m four-cusp manoeuvre. The
     fix is a plan filter that drops a leading direction segment shorter
     than the vehicle can execute, which belongs in the BT or a plan
     post-processor, not in nav2.yaml.
  3. Reverse is followed to about 2.4 m and then the heading diverges
     (measured: 50 deg out after 2.39 m of a 6 m reverse, while a 2 m
     reverse tracked at rms 0.0009 m). Pure pursuit is stable when the
     steered axle LEADS; reversing, this vehicle's steered wheel trails,
     and RPP has no separate reverse reference point or lookahead. That
     figure is n = 1 - one route, one speed, one direction - and is stated
     as an observation, not a bound.
  4. The refusal's error code does not carry its reason: the same goal
     inside a rack returned `208 NO_VALID_PATH` in the driven run and
     `207 TIMEOUT` on the bench. A VDA 5050 client at M6 cannot
     distinguish occupied, unreachable and undecided from the code.
  5. A goal that requires a column pinch consumes the vehicle's whole
     lateral budget (2.35 m free width leaves the padded polygon 0.356 m
     each side). Which routes are drivable is therefore a FLEET ROUTING
     decision, not a Nav2 parameter, and M6 needs it stated somewhere.
  6. Two `sim/` defects were met and left alone as instructed (the
     `warehouse_slam.launch.py` emit-before-register race, the missing
     `seed` argument). The standing `/forklift/odom` ->
     `/forklift/odom_ground_truth` rename is still open.
  7. Container figures only. Nothing here has been reproduced on the
     owner's WSL machine, where the M5 showcase runs.
next_suggested:      m5-11's envelope gate against `cmd_topic`; the goal
                     "reached" decision of open question 1 before any M6
                     work depends on it.
```

## What was done, in one paragraph

The inherited configuration (`307dd10`, honestly labelled `wip`, never run)
was checked against the brief's trap list rather than trusted, and then
measured. Its planner (`SmacPlannerHybrid` + `REEDS_SHEPP`), controller
(`RegulatedPurePursuit`, `use_rotate_to_heading: false`), behaviour tree,
launch and footprint all survived review — the footprint polygon was
re-derived from `model.sdf` by a new committed script and came out
**identical, vertex for vertex**. Five things were corrected and each is
recorded in `EVIDENCE_NAV2.md` §0: a quoted configure line that no captured
log contained, a grep whose pattern could not prove the absence it claimed,
a conversion check that had driven the vehicle into a rack face and reported
the contact as an arc, a cusp metric that counted single path points as
direction reversals, and a 27 MB recording. **One parameter was tuned with
the measurement that decided it**: `lookahead_dist` 1.20 → 1.60 m, because at
1.20 m the same 5.5 m aisle traverse tracked at rms 0.171 / max 0.396 m and
on a repeat diverged 1.18 m into the padded rack face, while at 1.60 m it
tracked at rms 0.119 / max 0.190 m and did not recur — the cause being the
vehicle's measured 23 % understeer at the tightest planned arc. The four
cases are in `EVIDENCE_NAV2.md` §5 with every attempt listed, including the
one that failed and the route that had to be changed, and why.
