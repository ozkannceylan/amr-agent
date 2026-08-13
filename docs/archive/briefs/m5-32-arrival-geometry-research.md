# m5-32 — arrival geometry: derive it, do not tune it

    gate:                M5 (criterion (d))
    agent:               agv-ros2   (research and plan; no implementation)
    goal:                A deterministic, kinematically derived solution to the arrival problem — the vehicle arrives at a goal already pointing the right way, by construction rather than by manoeuvring — grounded in how real steered vehicles actually do this.
    invariants_touched:  none expected
    inputs:
      - docs/reports/m5-31-nav2-route-diagnosis.md — the diagnosis you are solving
      - agv/forklift/EVIDENCE_NAV2.md §8 (the new dated section) and §5
      - agv/forklift/nav2.yaml, behavior_trees/navigate_to_pose_tricycle.xml
      - agv/forklift/scripts/cmd_vel_to_tricycle.py — the conversion and its derivation
      - agv/forklift/model.sdf and config.yaml — wheelbase, steer limit, the vehicle's real geometry
      - agv/forklift/EVIDENCE_MODEL.md — the measured turning geometry
      - docs/TODO.md §"Measured numbers a later session should not re-derive"
      - docs/interfaces/vda5050-subset.md — see §4, the contract already has a word for this
      - docs/LESSONS.md
    deliverable:         agv/forklift/ARRIVAL-GEOMETRY.md and docs/reports/m5-32-arrival-geometry-research.md
    done_when:           The tolerance pair is derived from the vehicle's measured geometry rather than chosen; the chosen approach is justified against surveyed alternatives with sources and dates; and the plan's first phase is small enough to land inside M5.
    forbidden:
      - proposing "widen the yaw tolerance" as the solution — the owner ruled against it, and the diagnosis says it hides the geometry rather than removing it
      - writing code, launch files or configuration — this brief produces documents
      - adopting an external approach without checking its premises against this repository and this vehicle (LESSONS 2026-07-28)
      - citing a source without a version and a verification date (LESSONS 2026-07-26)
      - re-deriving the measured numbers in docs/TODO.md; quote them
      - any solution that requires the vehicle to know where it is better than the localizer can tell it

---

## 1. The problem, stated as geometry

The goal checker requires position **and** heading inside their tolerances **at
the same instant**. This vehicle steers; it cannot rotate in place. So heading is
bought with travel, at a measured **2.1–2.6 m per radian** in the endgame. A
0.15 rad heading correction therefore costs 0.32–0.39 m against a 0.25 m box:
**the test is unsatisfiable by construction**, and m5-31 proved it — 55.9 s inside
the position circle, 47.1 s inside the heading window, zero samples inside both.

The owner's ruling: fix it **upstream**, so the vehicle arrives already aligned.
And fix it **deterministically** — this is computable physics, not a tuning
exercise.

## 2. Derive the constraint

Before surveying anything, write down the relation. Roughly: for a vehicle of
minimum turning radius **R**, a conjunctive arrival test is satisfiable only if
`xy_tol > R × yaw_tol` — with **R taken from this vehicle's measured geometry**,
not from a datasheet number nobody checked. The smallest measured arc radius is
**1.29 m** (TODO); the wheelbase and steer limit are in `model.sdf`, which is the
named authority.

State the relation properly, say what it assumes, and say where it stops holding
(it is a small-angle, single-arc argument — say so). Then evaluate the current
pair against it and give the margin as a number.

**This relation is the spine of the document.** Everything after it is about how
to satisfy it honestly.

## 3. Survey — we are not the first to solve this

Find out how steered vehicles actually arrive on a pose. Cover at least:

- **Nav2's own machinery**: the goal checker plugins that exist, what
  `SmacPlannerHybrid` already guarantees about terminal heading through its
  Reeds–Shepp expansion, and whether `opennav_docking` (or its equivalent in
  Jazzy) is the intended answer to exactly this question.
- **The staged-pose / approach-corridor pattern**: plan to a pre-goal pose offset
  along the goal heading, then drive a constrained final segment. This is what
  the owner asked for by name — find out how it is really done, what the
  offset distance is chosen from, and what happens when the corridor is blocked.
- **Industrial AGV and forklift docking**: how real pallet approaches work.
  Line following, natural-feature docking, laser-guided final approach. This
  matters because the project's claim is realism, and M6 puts four of these
  against ten stations.
- **Ackermann versus tricycle**: the owner's instinct is that a real forklift is
  Ackermann. Say what actually differs for THIS problem, and whether a solution
  derived for the tricycle transfers.

Cite sources with versions and verification dates. Grade them: documentation and
source code outrank a blog post.

## 4. A contract detail worth finding

`docs/interfaces/vda5050-subset.md` — the fleet interface this project is
committed to — already carries a notion of permitted arrival deviation, including
in theta. Find it, quote it, and say whether the solution you propose is
expressible in it. If the fleet standard already has the vocabulary for arrival
tolerance, the design should speak it rather than invent a parallel one, and M6
gets it for free.

## 5. The plan

Phased, in the house style of `docs/reports/m5-22-...` §4: one observable
done-condition per phase, files touched, explicit does-NOT list, and a marker on
any phase that needs an owner decision.

**Phase 1 must be small enough to land inside M5**, and the owner has said time
is tight. So: what is the least work that makes the arrival deterministic and
correct? If the honest answer is that a principled minimum still costs half a
day, say that — but do not pad it, and do not propose the full industrial
solution as phase 1.

Say clearly what each phase does to the **failure distribution** m5-31 measured
(1 clean, 2 recovered, 2 timed out of 5). The success criterion is not "it worked
once"; it is that the distribution moves and the mechanism explains why.

## 6. Two constraints from measurement, not opinion

- **The recovery shuffle degrades localization to 0.661 m worst case**, 2.5× the
  0.263 m that `footprint_padding: 0.27` derives from. A solution that arrives
  cleanly removes the shuffle and therefore this exposure — say so if true, and
  say what remains if it is not.
- **Routes through the 2.35 m column pinches leave 0.356 m of total budget.** An
  approach corridor that needs clearance must fit that, or say where it cannot
  and hand it to fleet routing at M6.

## 7. Working discipline

- Read `docs/LESSONS.md` first. Two are directly yours: a bound derived from one
  instance is a sample; and a motion check that does not retrace its segments
  cannot tell a followed arc from a blocked one.
- **Write the document as it settles**, not in one pass.
- Nothing heavy — this is research. If you need a measurement the repository does
  not have, name it as a measurement to take rather than estimating it.
- **Do not commit.** The orchestrator commits by pathspec.
