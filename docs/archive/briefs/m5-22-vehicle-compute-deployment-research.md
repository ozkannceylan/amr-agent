# m5-22 — per-vehicle compute and deployment: research, then a plan

    gate:                M5 → M6 bridge (architecture; produces a proposed ADR, not a gate criterion)
    agent:               arch-docs   (research and decision record)
    goal:                Decide and document how the vehicle's autonomy stack is deployed as if each forklift carried its own industrial PC, so that adding a forklift means adding a machine — and produce the implementation plan a coding agent can execute from.
    invariants_touched:  expected none — but this is exactly the brief where that must be checked, not assumed (see §5)
    inputs:
      - CLAUDE.md §2 (invariants), §3 (topology), §4 (layout)
      - docs/adr/0011-sensored-autonomy-architecture.md (D1, D3, D4)
      - docs/adr/0012-envelope-composition.md
      - docs/adr/0014-motion-control-locus.md
      - docs/interfaces/vda5050-subset.md
      - docs/interfaces/opcua-nodes.md §12
      - docs/interfaces/bridge-design.md
      - agv/forklift/README.md, agv/forklift/config.yaml
      - agv/forklift/launch/ (all of it)
      - sim/launch/, sim/worlds/, sim/scenarios/
      - docs/roadmap.md (the M6 row — four forklifts, five loading and five unloading stations)
      - docs/reports/m5-11-envelope-gate-node.md
      - docs/LESSONS.md
    deliverable:         docs/adr/00NN-per-vehicle-compute-and-deployment.md (status `proposed`) and docs/reports/m5-22-vehicle-compute-deployment-research.md carrying the phased implementation plan
    done_when:           The ADR states the chosen isolation mechanism with its alternatives and their rejection reasons; the plan is phased, each phase with an observable done-condition a coding agent can test; and the resource question of §4 is answered with a measurement or an explicit "unmeasured, and here is the risk".
    forbidden:
      - writing code, launch files or configuration — this brief produces documents only
      - writing outside docs/adr/, docs/PLAN.md and your own report
      - proposing MuJoCo (invariant 12), a custom fleet schema in place of VDA 5050 (invariant 3), or any inversion of the OPC UA server/client direction (invariant 4)
      - putting safety on the network, or making network loss a safety event rather than a degraded mode (invariants 1 and 2)
      - citing an external source without a verification date and, where one exists, a pinned ref or version (LESSONS 2026-07-26)
      - adopting an external plan's factual premises without checking them against this repository and the sources it names (LESSONS 2026-07-28)

---

## 1. What the owner asked for, in their words

The autonomy stack should be built and run **as if the vehicle carried an
industrial PC and we were deploying to it**. Every additional forklift should be
**another machine**, not another process sharing one namespace by accident. The
simulation stays the substrate — but the software boundary between "the vehicle's
computer" and "everything else" should be real, not notional.

This is an architecture question with real alternatives, and it is the last
cheap moment to answer it: M6 puts **four forklifts** against five loading and
five unloading stations, and a shortcut taken now is paid for four times there.

## 2. Research — go and find out, do not reason from memory

Cover at least these, with sources, versions and verification dates:

1. **Isolation mechanism.** The candidates are ROS 2 **namespace per vehicle**,
   **`ROS_DOMAIN_ID` per vehicle**, **DDS partitions**, and **container per
   vehicle** — and combinations. For each: what it actually isolates, what leaks,
   and the known failure modes. Pay specific attention to **TF**, which is the
   classic multi-robot trap, and to whether Nav2 on Jazzy supports the option
   cleanly or needs remapping gymnastics.
2. **What the fleet layer needs to still see.** Isolation that also hides the
   vehicle from the fleet manager is not isolation, it is a wall. VDA 5050 runs
   over MQTT (invariant 3) and the monitoring plane is read-only (ADR 0011 D4).
   Both must still work across whatever boundary you choose.
3. **Deployment mechanism**, as it would really be done on an industrial PC:
   systemd units, containers, or a ROS 2-native mechanism. What starts the stack
   at power-on, what restarts it on crash, what pins versions, what carries
   configuration per vehicle (serial number, calibration, map).
4. **The industrial PC itself** — what class of machine actually runs a Nav2
   stack on a forklift, and what its constraints are (fanless thermals, DC
   input, no GPU, real-time or not). This grounds the claim. Keep it short and
   cited; the project is judged on architecture, not on a hardware catalogue.
5. **Time and identity.** Clock discipline across vehicles, and how a vehicle
   knows which vehicle it is. This project has already been bitten once by an
   unsynchronised clock (LESSONS 2026-07-27).

## 3. What the decision must respect

- **Invariant 1 and ADR 0014.** Safety is onboard and the control loop closes
  onboard. A deployment design that moves the loop across a machine boundary is
  wrong on its face.
- **Invariant 2.** Losing the link to the fleet is a **degraded mode**, not a
  safety event. Per-vehicle compute makes this concrete: say exactly what a
  vehicle does when its supervision link dies, and how that is different from
  its own onboard safety acting.
- **Invariant 10.** One owner per datum. Per-vehicle configuration multiplies the
  chances of the same value living in four places.
- **Invariant 11.** If the design implies an edge the CLAUDE.md §3 topology does
  not draw, say so — do not quietly rely on it. Note that docs/TODO.md already
  carries an open topology gap about `bridge/` for exactly this reason.

## 4. The resource question — answer it, do not dodge it

Four forklifts at M6 means four Nav2 stacks, four EKFs, four sets of sensors and
one Gazebo, on **one workstation**. The existing measurements give you a
starting point: `agv/forklift/EVIDENCE_NAV2.md`, `EVIDENCE_ODOMETRY.md` and
docs/TODO.md's render-budget line (three lidars at 910 rays cost nothing
measurable headless, RTF 1.0004; the GUI costs ~8 points).

Either measure what one vehicle's full stack actually costs on this machine, or
state clearly that it is unmeasured and what the risk is. Do **not** produce a
plan whose first phase discovers the machine cannot run it. If the honest answer
is that four full stacks will not fit, the plan says so and proposes what gives
— that is a finding, not a failure.

Note the standing rule that two agents both running the simulator contend even
when their file scopes are disjoint (LESSONS 2026-07-30); if you measure, measure
alone and say when you measured.

## 5. Invariants — check, and stop if you must

If the design you arrive at requires breaking an invariant, **write the ADR as a
proposal, state the conflict, and stop** (CLAUDE.md §2 and §8). Do not implement
around it and do not soften the invariant's wording to fit.

## 6. The plan the coding agent will execute

The second half of your deliverable is a **phased implementation plan** in your
report. Requirements:

- Each phase has **one observable done-condition** — something that can be run
  and seen, not "code written".
- Phase 1 must be executable against **one** vehicle and must leave the current
  m5-10 / m5-11 chain working. The four-vehicle case comes later; a plan that
  only works at four is untestable now.
- Say for each phase which files and directories it touches, so the phases can be
  handed out as briefs with real `forbidden:` fields.
- Name what each phase does **not** do. Scope creep in this area is expensive.
- Flag any phase that needs a decision from the owner rather than a coder.

## 7. Working discipline

- **Write findings into the deliverable as they land**, not at the end.
- **Do not commit.** The orchestrator commits by pathspec.
- Read `docs/LESSONS.md` first. Entry 2026-07-28 on external plans — "an external
  plan is evidence of intent, not of the world" — is the one that most applies to
  a research brief.
- Prefer a short document over a long one, and a diagram over prose (CLAUDE.md
  §10). This project is judged on clarity of architecture, not volume.
