# m5-34 — force the arrival heading inside the window

    gate:                M5 (criterion (d))
    agent:               agv-ros2   (design; the build follows)
    goal:                Close the two done-conditions m5-33 missed, by making the vehicle enter the position circle inside 8.594° rather than merely closer to it.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-33-staged-approach-build.md — **the result you are extending**, especially its three named mechanisms
      - agv/forklift/EVIDENCE_NAV2.md §9 (m5-33's runs) and §8 (m5-31's discriminator)
      - agv/forklift/ARRIVAL-GEOMETRY.md — the design m5-33 built; you are writing its next section
      - agv/forklift/nav2.yaml, behavior_trees/navigate_to_pose_tricycle.xml, scripts/nav2_run.py
      - agv/forklift/scripts/cmd_vel_to_tricycle.py
      - docs/LESSONS.md
    deliverable:         a new section in agv/forklift/ARRIVAL-GEOMETRY.md and docs/reports/m5-34-arrival-heading-forcing.md
    done_when:           Each of m5-33's three mechanisms is either given a fix with a stated expected effect on the distribution, or explicitly ruled out with a reason. The plan is small enough to build and measure in one run of five.
    forbidden:
      - widening `xy_goal_tolerance` or `yaw_goal_tolerance` — the owner ruled against it twice
      - activating `opennav_docking` — still an owner decision at M6
      - adding a dependency
      - resurrecting the lateral-offset explanation without new evidence — m5-33 tested it and it is **not supported at n = 5**: the run that started 0.231 m off, essentially the worst run's offset, was clean
      - writing code — this brief produces a design
      - proposing anything whose success can only be shown by one good run

---

## 1. Where this stands

m5-33 staged the approach and the distribution moved: clean 1→3 of 5, shuffling
4→1 of 5, and the 0.661 m localization excursion gone (worst now 0.1186 m). Two
done-conditions still fail: **≥4/5 clean** and **no run shuffling**.

The cause is not in doubt. m5-31's discriminator reproduced **5 of 5 with no
exception**: every run entering the position circle within **8.594°** was clean;
both runs outside it were not. Staging narrowed the arrival spread from
−16…+37° to −1.8…+16.9°. **Narrowing is not forcing.**

## 2. The three mechanisms m5-33 named and did not fix

Take each one. Fix it, or rule it out and say why.

1. **The terminal stall.** In r1 the command held **0.015 m/s at near-full lock**
   with ground truth frozen for 20 s. This is not the shuffle — the
   pre-registered shuffle test correctly scored it NO — but the run was not
   clean either. **Ask whether the vehicle can physically execute that
   command.** A steered vehicle at full lock and near-zero speed is exactly
   where a plant stops responding, and `cmd_vel_to_tricycle.py` is where a
   command that cannot be executed would be produced. If there is a minimum
   executable speed, it is a number this project should know and does not.
2. **The go-around returns to staging with unconstrained heading** — **−28.56°**
   measured. So the retry begins worse than the first attempt did. A go-around
   that does not restore the precondition it exists to restore is not a retry.
3. **The staging error is lateral by construction.** Say what follows from that
   — and note that m5-33 already refused the obvious inference, so do not
   re-derive it. If you believe lateral offset matters, the burden is a
   measurement, not an argument.

## 3. The obvious lever, and why it is not obviously right

The vehicle arrives at staging with whatever heading it happens to have. The
final leg then has 3.0 m to converge. Two directions exist:

- **constrain the heading at staging** — arrive there aligned, so the final leg
  starts straight rather than correcting;
- **give the final leg more room** — a longer d converges more heading, at the
  cost of a longer corridor that must still fit the 2.35 m column pinches with
  their measured 0.356 m of total budget.

Both are derivable, not guessable. Do the arithmetic for each against the same
relation `ARRIVAL-GEOMETRY.md` already establishes, and say which one the
geometry actually favours. If it is both, say which is cheaper to build.

## 4. What the plan must promise

For each change: **the expected effect on the distribution**, stated before the
run. Not "should improve" — which runs, and why. That way the measurement can
falsify the design instead of merely reporting it.

Keep it to one build and one five-repeat run. Time is tight and a plan that
needs three rounds is not a plan for this week.

## 5. Working discipline

- Read `docs/LESSONS.md` first. The one that matters most here: a bound from a
  single instance is a sample, not a bound.
- **Write the design as it settles**, not in one pass at the end.
- Nothing heavy — this is design. The build measures.
- **Do not commit.** The orchestrator commits by pathspec.
- **The owner is working in `plc/` right now in another session.** Do not touch
  `plc/`.
