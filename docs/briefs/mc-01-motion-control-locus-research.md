# Brief mc-01 — where motion control belongs: research against industrial practice

```
gate:                M5 (architecture question, blocking waves C and E)
agent:               research (fable)
goal:                establish which of two candidate architectures is closer
                     to how real industrial AGV/AMR systems are actually
                     built, and recommend one with its command interface
                     specified concretely.
invariants_touched:  none may be changed. Invariants 1, 5, 6, 9, 10 and 11 all
                     bear on this and the recommendation must be checked
                     against each.
inputs:              [CLAUDE.md sections 2, 3, 9;
                      docs/adr/0011-sensored-autonomy-architecture.md D3;
                      docs/adr/0012-envelope-composition.md;
                      docs/interfaces/opcua-nodes.md sections 10 and 12;
                      plc/forklift/SPEC.md sections 7 and 13;
                      docs/roadmap.md rows M4, M5, M6;
                      docs/reports/mv-01-beckhoff-portability-research.md
                      (for how a second vendor would inherit whatever is
                      chosen)]
deliverable:         docs/reports/mc-01-motion-control-locus-research.md
done_when:           both candidate architectures are described in the terms
                     a controls engineer would use; real industrial practice
                     is established from named products and standards, not
                     from reasoning about what ought to be true; the
                     recommendation is made and defended, including against
                     its strongest objection; the command interface of the
                     recommended architecture is specified concretely enough
                     that an interface brief could be written from it; the
                     latency and rate budget is worked out with numbers; and
                     every invariant is checked.
forbidden:           [deciding gate scope or schedule; writing any node
                      names, PLC code or ROS configuration; recommending an
                      architecture on elegance rather than industrial
                      evidence; treating this project's existing ADRs as
                      constraints on the ANSWER — they are the current state,
                      and the owner has explicitly opened them to revision;
                      claiming a product behaves a certain way without a
                      source; editing any file but your own report]
```

## Why this brief exists

The owner is not building a hobby project. The stated priority is **the system
and process closest to real industrial practice**. Two readings of the vehicle
architecture are now on the table, they are materially different, and the
owner wants the more industrially faithful one chosen on evidence.

## Architecture A — as currently recorded (ADR 0011 D3, ADR 0012)

The PLC publishes a low-rate **motion envelope**: a motion enable, a speed
ceiling, and an equipment/station permit. The vehicle's own computer runs
perception, SLAM, localization and Nav2, closes the ~20 Hz control loop
onboard, and **drives the actuators itself**, bounded by the envelope. The
PLC's authority is permissive: whether the vehicle may move, how fast at most,
and whether the fixed equipment is ready. Rationale recorded at the time:
routing a 20 Hz control loop through ROS → OPC UA → PLC scan → back introduces
tens to a hundred-plus milliseconds of non-deterministic latency, which would
place a timing-critical loop in Python (invariant 9) and, when commands are
gated to zero, abort the goal through Nav2's progress checker.

## Architecture B — as the owner describes it

The safety laser scanners are wired to the F-PLC; the F-program's most
important job, in either drive mode, is **SLS and STO**. Steer-by-wire and
motor control **flow through the PLC**. The vehicle computer reads the lidar,
builds the map, plans the motion, and **gives the PLC work** — "this much to
the right, this much forward". The vehicle never writes an actuator; the PLC
forms every motion setpoint, exactly as it does for the teleoperated joystick
at M4, with the mode selector merely changing which source writes the request.

Note what recommends B inside this project: it preserves M4's central claim
into autonomous mode, it reuses the M4 PLC logic unchanged, and it sits
consistently with ADR 0011 D1's reading that the S7-1500 represents the
forklift's **onboard** controller — in which case there is no network in the
motion loop architecturally, only in the simulation's realisation of it.

## What the research must establish

1. **How real AGV and AMR systems actually divide this.** Name products and
   architectures rather than reasoning from first principles. Consider at
   least: navigation/AGV controller products (for example Kollmorgen NDC,
   BlueBotics ANT, SEW-EURODRIVE's AGV solutions, Beckhoff's and Siemens'
   own AGV offerings), and what each puts on the "navigation computer" versus
   the "vehicle controller". Where does the trajectory-following loop close on
   a real machine? Who writes the drive's setpoint? At what rate, over what
   link, and with what determinism guarantees?

2. **The drive interface.** Real vehicles command drives over CANopen CiA 402,
   EtherCAT/CoE, PROFIdrive or equivalent, in velocity or position mode. What
   does that imply for who does what? A drive in velocity mode already closes
   the fast loop itself — which changes the meaning of "motor control in the
   PLC". Establish what a PLC genuinely does in such a stack: ramps, limits,
   interlocks, mode words, safe-state handling, coordination — and what it
   does not.

3. **Rates and latency, with numbers.** What loop rates do real AGVs run for
   path following, and what latency budget does a path-following controller
   tolerate at warehouse speeds (0.3–1.5 m/s)? Work out the position error a
   given latency produces at a given speed and turning radius, so the
   discussion is quantitative. Then assess: is a 50–150 ms round trip in the
   command path an engineering problem, a tuning problem, or a non-problem at
   these speeds?

4. **The safety layer's placement**, which the owner treats as the foundation.
   In real AGVs, where do safety scanner OSSDs terminate, where do SLS and STO
   execute, and how does the safety layer inhibit motion — by removing drive
   enable, by commanding the drive's own safety function, or by cutting
   power? Confirm or correct this project's current reading. Also: does the
   safety layer's placement CONSTRAIN where motion control belongs? If SLS
   monitors speed, something must measure speed safely and something must act
   on the drive — establish whether that forces motion control to sit near the
   safety controller.

5. **What the vehicle computer sends.** Continuous velocity commands, motion
   segments, a path to follow, or a pose target? For each, name real systems
   that do it, and give the consequences: what breaks when the link is slow,
   what happens when the link drops, who holds the state, and how the vehicle
   corrects for error. This is the question the owner could not resolve and it
   is the heart of the brief.

6. **The M6 consequence.** Four vehicles, VDA 5050, a fleet manager. Under
   each architecture, what does the fleet layer talk to, and does the choice
   still hold at four vehicles? An architecture that is elegant at one vehicle
   and impossible at four is the wrong answer.

7. **The simulation consequence.** In this project the PLC runs on PLCSIM
   Advanced on Windows and the vehicle computer runs in WSL2, linked by OPC UA
   through a bridge — so the simulation adds latency that a real onboard link
   would not have. State what must be measured and disclosed under each
   architecture, and whether the recommended one remains demonstrable in this
   setup or needs the disclosure written differently.

## Output shape

Recommend ONE architecture. Defend it against its strongest objection rather
than against a weak one. Then specify its command interface concretely: what
the vehicle sends, at what rate, with what semantics on loss, who holds which
state, and what the PLC does with it — enough that an interface brief and a
PLC specification brief could both be written from your section without
inventing anything.

Include a short section the orchestrator can read to the owner **step by step
as a flow**, in plain language, from lidar return to wheel motion, naming
which component does each step and why that component and not another. The
owner has asked explicitly to confirm that both of us read the flow the same
way, so that section is a deliverable, not a courtesy.

Where the recommendation contradicts ADR 0011 D3 or ADR 0012, say so plainly
and list which decisions would need superseding — those ADRs record the
current state, not a constraint on your answer.

Cite sources with URLs and verification dates; today is 2026-07-31. Mark
anything unverified as unverified with what would settle it.
