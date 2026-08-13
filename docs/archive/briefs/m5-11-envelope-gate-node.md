# m5-11 — envelope gate node

    gate:                M5
    agent:               agv-ros2
    goal:                A ROS 2 node on the vehicle consumes the PLC motion envelope and gates commanded motion below the velocity smoother, so that a dead or stale link stops the vehicle and a live envelope clamps it, measured in the warehouse simulation.
    invariants_touched:  none
    inputs:
      - docs/adr/0011-sensored-autonomy-architecture.md
      - docs/adr/0012-envelope-composition.md
      - docs/adr/0014-motion-control-locus.md
      - docs/interfaces/opcua-nodes.md (§12 — envelope, mode, process stop)
      - agv/forklift/nav2.yaml
      - agv/forklift/launch/navigation.launch.py
      - agv/forklift/scripts/cmd_vel_to_tricycle.py
      - agv/forklift/EVIDENCE_NAV2.md
      - docs/LESSONS.md
    deliverable:         agv/forklift/scripts/envelope_gate.py plus its configuration, its launch wiring and agv/forklift/EVIDENCE_ENVELOPE.md
    done_when:           EVIDENCE_ENVELOPE.md carries measured runs for all six acceptance observations in §4 below, each with the command it was produced by, and the open-loop / closed-loop comparison of §3.2 shows a numeric difference rather than an assertion.
    forbidden:
      - writing outside agv/ (request any file in plc/, sim/, bridge/, hmi/, docs/interfaces/ or docs/adr/ in the report instead of creating or editing it)
      - connecting to OPC UA, to PLCSIM Advanced or to the bridge; this node is tested against a ROS 2 topic double
      - putting any velocity, speed ceiling or motion command onto the OPC UA seam, or designing any part of the ~20 Hz loop off the vehicle (ADR 0014)
      - adding a Python dependency without proposing it in the report first
      - editing agv/forklift/EVIDENCE_*.md files other than the new EVIDENCE_ENVELOPE.md
      - re-deriving the measured numbers listed in docs/TODO.md §"Measured numbers a later session should not re-derive"; quote them

---

## 1. What the node is

A small node in the vehicle's own control chain. It subscribes to the PLC-issued
motion envelope — **motion enable, speed ceiling, fixed-equipment / station
permit** — as it arrives on the vehicle side, and it gates the commanded motion:

- **enable false, or the envelope stale** → controlled stop.
- **enable true** → pass the command through, **clamped to the speed ceiling**.

Read `docs/interfaces/opcua-nodes.md` §12 for the three elements' names, types
and semantics, and ADR 0012 for why the third element is a fixed-equipment /
station permit and not a zone permit. **Implement what those documents say.
Invent no node, no name and no third behaviour.** If §12 does not settle
something the node needs — the staleness period, the permit's effect on motion,
the units of the ceiling — say so in the report as an open question and
implement the most conservative reading, naming that reading in the code.

## 2. Where it sits, and why — this is the design decision, not an implementation detail

The chain is `Nav2 controller → velocity smoother → **envelope gate** →
cmd_vel_to_tricycle → vehicle`.

**2.1 The gate sits BELOW the velocity smoother.** Above it, a dead link would
leave the smoother free to keep ramping whatever command it last held, so the
one failure the gate exists to catch is the one it would miss. Verify the actual
topic chain in `nav2.yaml` and `navigation.launch.py` before wiring, and record
the before/after topic names in the evidence — do not assume the chain from this
brief.

**2.2 The velocity smoother must run CLOSED_LOOP against odometry.** Nav2's
default is open-loop: it limits acceleration against **its own last command**,
not the vehicle's actual velocity. With the gate below it, an open-loop smoother
keeps ramping its internal command while the vehicle is held at zero, so gate
release applies a step and the vehicle lurches. Set the smoother's feedback to
closed loop and give it the odometry topic the EKF actually publishes.

**2.3 ADR 0014 binds.** The loop closes onboard. No velocity value crosses the
OPC UA seam in either direction.

## 3. What must be measured, not asserted

Run in the warehouse simulation, the same stack the Nav2 work used
(`EVIDENCE_NAV2.md` records how it was brought up). Drive the envelope from a
**ROS 2 topic double** you write — the PLC is not running and must not be
connected.

**3.1** Every observation in §4 carries the command that produced it and the raw
figures, not a summary of them.

**3.2 The open-loop / closed-loop comparison is the centrepiece.** Run gate
release under `OPEN_LOOP` and under `CLOSED_LOOP` with everything else equal, and
report the commanded-velocity step at release in m/s and the resulting
acceleration, for both. If the difference is not visible in the numbers, say so —
a null result honestly reported is a result. Do not describe the lurch you
expected; report the one you measured.

## 4. Acceptance observations

1. **Enable drops while moving** → the vehicle reaches a controlled stop.
   Report the stop distance and the time from the enable edge, and say
   explicitly whether the deceleration was the smoother's limit or an abrupt
   zero.
2. **Envelope goes stale** (the double stops publishing, link dead rather than
   commanded stop) → the same controlled stop. Report the measured latency from
   last message to first zero command, against the staleness period the design
   uses.
3. **Ceiling clamp** — a command above the ceiling is passed through at the
   ceiling, not blocked and not passed unchanged. Report commanded vs emitted
   for at least three ceiling values including one below the vehicle's normal
   cruise.
4. **Gate release** — §3.2's comparison.
5. **Pass-through fidelity** — with enable true and the command under the
   ceiling, the gate changes nothing measurable. Report the residual.
6. **Fixed-equipment / station permit** — whatever §12 says it does, shown
   happening. If §12 leaves its motion effect unspecified, report that as the
   open question and demonstrate the conservative reading you implemented.

## 5. Working discipline — read this before starting

- **Write each result into `EVIDENCE_ENVELOPE.md` as it lands**, not at the end.
  A run lost mid-flight must cost minutes, not hours. Create the file with its
  section headings first and fill them in as you go.
- **Do not commit.** The orchestrator commits by pathspec. Leave the tree with
  your files written and say in the report exactly which paths are yours.
- **Read `docs/LESSONS.md` first.** Several entries bear directly on this work:
  the closed-loop/adopt-window lesson (2026-07-31), the motion-check lesson that
  a kinematic check must retrace its segments and carry a speed-achievement
  column (2026-08-04), the fail-safe-validity lesson that a rangefinder's
  beyond-range return is a measurement (2026-07-29), and the rule that a bound
  derived from one instance of an event is a sample with n=1, never a bound
  (2026-08-04). Apply the last one to every figure you report.
- If a `robotics-lessons` corpus is reachable, search it before web search when
  something behaves unexpectedly, and cite the lesson id.
- If the work turns out to require touching an invariant or a locked document,
  **stop and write the report** saying so. Do not implement around it.
