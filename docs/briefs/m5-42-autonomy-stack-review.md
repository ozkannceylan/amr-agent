# m5-42 — the autonomy stack: everything standing between here and criterion (d)

    gate:                M5 (criterion (d))
    agent:               verifier   (read-only; adversarial, and the output is a work list)
    goal:                One ordered, complete list of what must happen before roadmap criterion (d) can close — nothing omitted because it is inconvenient, nothing included because it is easy.
    invariants_touched:  none — this brief reads
    inputs:
      - docs/roadmap.md — **criterion (d) word for word**, and the M5 row's narration clause
      - docs/safety/ — the SRS, and **AT-02, AT-03 and AT-04 in full**. Nobody has established what they require
      - agv/forklift/ — every EVIDENCE_*.md, nav2.yaml, model.sdf, scripts/, launch/, behavior_trees/
      - agv/forklift/ARRIVAL-GEOMETRY.md, PLANT-CHANGE-INVENTORY.md, FIELD-EVALUATION.md
      - docs/reports/m5-31, m5-32, m5-33, m5-34, m5-35, m5-38, m5-39, m5-40, m5-12b
      - docs/reports/m5-23-judge-review.md — its Part B ordering
      - docs/TODO.md and docs/PLAN.md
      - sim/ — its scenarios, launch files and known carried items
      - docs/LESSONS.md
    deliverable:         docs/reports/m5-42-autonomy-stack-review.md
    done_when:           Criterion (d) is decomposed clause by clause with a verdict per clause; every open defect in the autonomy stack is listed with its evidence; and the work list is ORDERED, each item marked agent or owner, each with a one-line observable.
    forbidden:
      - running the simulator — another agent holds it. This is a reading task
      - accepting a report's summary as evidence; open the artifact
      - omitting an item because it looks small, or because fixing it is somebody else's job
      - inventing work; every item traces to a criterion clause, a measured defect or a stated open question
      - softening a finding because a lot of work has gone into this area

---

## 1. Start with the criterion, not with the code

Read criterion (d) **word for word** and decompose it into clauses. For each:
**met**, **not met**, or **not yet attempted** — with the artifact that decides
it. The clauses at least include: SLAM building a map of the warehouse world;
Nav2 driving the forklift autonomously to commanded goals; **AT-02, AT-03 and
AT-04 passing**; and the inhibit **demonstrably acting below the navigation
stack**.

**AT-02, AT-03 and AT-04 are the least-understood part of this gate.** No report
in the repository establishes what they require or whether anything has run
them. Read them in the SRS, say what each demands, say what would satisfy it,
and say whether it is agent work or owner work at a tool. If they need PLCSIM
under activated safety mode, that is owner work and the plan must say so.

Note the M5 row also carries a **narration obligation** for the showcase — the
permissive-and-checked, not-compelled sentence. Say whether the material to
narrate it truthfully now exists.

## 2. Then the defects, and there are known ones

These are already recorded; find the rest yourself, and check each of these is
stated accurately:

- **the reverse defect.** m5-40 established it is real and un-masked, not a
  deadband artefact: RPP has no reverse reference point on a trailing-axle
  vehicle. Note that even the straight route's plans open with a short
  Reeds-Shepp reverse, so this is not confined to reverse cases;
- **the reverse cap moved** −0.60 → −0.55 (m5-12b), invalidating every
  reverse-travel figure in EVIDENCE_NAV2.md;
- **`sensor_coverage.py` no longer runs at all** — so EVIDENCE_SENSOR_COVERAGE.md,
  which it produced entirely, is currently unreproducible;
- **FIELD-EVALUATION §6's rear clip band** rounds a measured boundary the wrong
  way and would hold the verdict at INTRUSION for ever;
- **`nav2_run.py`'s startup race** and `cmd_goal`'s settle loop exiting one
  sample early, both recorded and deliberately not fixed;
- **two inventory items not done** — EVIDENCE_LOCALIZATION cases a/b and
  EVIDENCE_VEHICLE_IMAGE proof 3;
- **sim/ carried items**: the `warehouse_slam.launch.py` lifecycle race, the
  missing `seed` argument, `forklift_bringup.launch.py` not carrying the current
  stack, and the arena traction contradiction m5-39 found;
- **the goal-refusal error code carries no reason.**

For each: is it a criterion-(d) blocker, an evidence-integrity problem, or
housekeeping? Say which, and do not promote housekeeping to make a list look
thorough.

## 3. The question nobody has asked

**Does the vehicle still do what it did?** The plant changed on 2026-08-05 and
the reverse cap changed on 2026-08-06. m5-40 re-measured the inventory's list,
but the inventory was written before the reverse cap moved. Say what is now
unqualified that nobody has noticed — and be specific about which file and which
figure.

## 4. The output is a work list

Ordered. Each item: **what**, **agent or owner**, **what it depends on**, and
**one observable line** that says it is done. Ordered by what unblocks the most,
not by directory and not by ease.

If any clause of criterion (d) **cannot be closed by anything currently planned**,
say so plainly rather than redefining the criterion (CLAUDE.md §10). And if the
honest total is larger than one working session, say that too — the owner has
asked for this to finish, and a list that hides its size does not help them.

## 5. Working discipline

- Read `docs/LESSONS.md` first.
- **Write findings into the report as they land**, not at the end.
- Nothing heavy, and **no simulator** — another agent is running one.
- **Do not commit.** The orchestrator commits.
