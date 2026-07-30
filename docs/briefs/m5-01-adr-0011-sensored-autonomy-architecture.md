# Brief m5-01 — ADR 0011: M5 architecture, sensored autonomous forklift

```
gate:                M5 (opening)
agent:               arch-docs
goal:                ADR 0011 records, as accepted, the five owner rulings of
                     2026-07-30 that set the architecture of the sensored
                     autonomous forklift gate.
invariants_touched:  none changed. Invariants 1-13 stand. Two consequences are
                     explicit and must be stated as such: (i) the CLAUDE.md §3
                     topology gains a monitoring-plane edge, which invariant 11
                     reads against, so the diagram is amended by a separate
                     owner-approved infra brief and this ADR is its authority;
                     (ii) decision 3 amends a GATE-CRITERION phrasing from M4
                     ("the PLC forms all motion setpoints"), not an invariant.
inputs:              [docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md,
                      docs/adr/0010-milestone-restructure-forklift-first.md,
                      docs/adr/0005-bridge-layer-and-opcua-client.md,
                      docs/roadmap.md row M5,
                      plc/forklift-safety/SPEC.md sections 1.3 and 10,
                      docs/safety/SRS.md, docs/safety/PL-SCENARIOS.md,
                      the rulings and facts blocks below]
deliverable:         docs/adr/0011-sensored-autonomy-architecture.md
done_when:           the ADR states the five decisions with context,
                     consequences and rejected alternatives; every external
                     fact carries its source and the verification date
                     2026-07-30; decision 2's feasibility condition and its
                     named fallback are explicit, in the ADR 0009 pattern;
                     decision 5's non-claim list is reproduced in full; the
                     relationship to ADRs 0002, 0005, 0008, 0009 and 0010 is
                     each stated; status reads accepted with the
                     owner-approval date 2026-07-30.
forbidden:           [editing any other ADR, editing CLAUDE.md (separate infra
                      brief), editing roadmap.md/PLAN.md/TODO.md, writing code
                      or specifications, deciding the monitoring service's
                      directory (recorded as recommended-not-ruled),
                      inventing external facts beyond the facts block,
                      claiming any achieved PL, SIL or PFH anywhere in the
                      document, mentioning any deadline]
```

## Decisions to record (owner-approved 2026-07-30)

1. **The forklift's F-runtime group is the vehicle's onboard safety
   controller.** `F_Forklift_Safety` is declared, architecturally, the safety
   controller carried BY the forklift — not the fixed cell's F-CPU acting on a
   remote vehicle. The scanner → F-program → STO chain is therefore internal to
   the vehicle and, in a real build, hardwired. Context: research of 2026-07-30
   establishes that on real AGVs the safety laser scanner's OSSDs go to the
   vehicle's own safety controller (Flexi Soft or an onboard safety PLC), and
   that PROFIsafe from a moving vehicle to a stationary F-CPU over a wireless
   link is not accepted practice — it would break invariant 1. Consequence: the
   reading scales to M6, where each of four forklifts carries its own safety
   instance; the simulation's single 1513F-1 hosting that instance is a
   simulation artifact to be disclosed, not an architectural claim. This
   extends ADR 0009 (which opened cell-scope safety on the twin) by naming what
   the twin's F-layer represents.

2. **The scanner reaches the F-program through configured F-I/O, stimulated by
   the PLCSIM Advanced API — the simulation's equivalent of wiring.** An
   ET 200SP F-DI is configured in HW config as the scanner's OSSD pair
   (1oo2 equivalent, discrepancy time, input delay parameterised as if real);
   the Gazebo scanner model drives those channel values through the S7-PLCSIM
   Advanced API by tag name. Rationale: in a real vehicle the OSSD signal
   arrives on copper, never on a network, so the honest simulation analogue is
   a path that does not traverse OPC UA either. Safety signals therefore never
   enter the process network, and invariant 1 holds in letter as well as
   spirit. OPC UA continues to carry process data and the read-only `Safety/`
   mirrors only.
   **Feasibility condition, in the ADR 0009 pattern:** the first M5 brief
   settles in the tool whether this project's PLCSIM Advanced version and its
   safety system version support F-I/O simulation, and whether the API writes
   the configured F-DI's channel values by tag name. If it does not, the named
   fallback is the present standard-DB stand-in, which is then labelled a
   stand-in wherever it appears and carries the Siemens S015 validity check
   visibly in the F-code. The fallback does not reopen decision 1.

3. **In autonomous mode the PLC issues a motion envelope, not per-sample
   setpoints.** The standard program publishes, at its own cycle, an autonomy
   envelope — a motion enable, a speed ceiling and a zone permit — and the
   navigation control loop closes onboard the vehicle at its own rate. Context:
   Nav2's controller is a ~20 Hz closed loop; routing each velocity sample
   through ROS → OPC UA → PLC scan → back introduces tens to a hundred-plus
   milliseconds of non-deterministic latency, which would place a timing-
   critical loop in Python (invariant 9) and, when commands are zeroed by the
   gate, abort the goal through Nav2's progress checker. Supervision at order
   and zone level rather than velocity level is also what VDA 5050 and
   industrial practice do, consistent with invariants 5 and 6. Consequence: the
   M4 phrasing "the PLC forms all motion setpoints" continues to hold for
   TELEOPERATED mode, where it was demonstrated, and is amended for AUTONOMOUS
   mode to "the PLC forms and owns the motion envelope; no motion occurs
   outside it". Record that the M4 gate criterion itself is unchanged and
   already closed on teleop. Note as a consequence for implementation, not as a
   decision: an externally gated command stream requires the velocity smoother
   to run closed-loop against measured odometry rather than against its own
   last command.

4. **A read-only monitoring plane joins the topology.** Map, pose and live
   obstacle data reach the operator through a monitoring service that
   subscribes to the vehicle's ROS 2 graph and serves the HMI page read-only.
   It has no write endpoint and no publisher — read-only by construction, not
   by configuration. The process plane (HMI → PLC → bridge → vehicle) remains
   the only command path and is unchanged. Rationale: a SLAM map cannot
   sensibly transit OPC UA process nodes, and adding ROS 2 to `hmi/` would
   weaken that layer's own boundary statement — the reasoning that made
   `bridge/` its own layer in ADR 0005. This is the decision ADR 0010 D6(a)
   left open, and it amends the §3 topology by adding one edge, drawn in a
   third style distinct from both the safety path and the process path.
   The service's directory is **recommended as `agv/` — the vehicle publishing
   its own telemetry — but is NOT ruled here**; record it as an implementation
   question for the first monitoring brief, with the `viz/` top-level
   alternative and the ADR 0005 test named.

5. **Claim boundary for ISO 13849 and ISO 3691-4.** M5 states `PLr` targets
   derived from a documented risk assessment and claims **no achieved PL, SIL
   or PFH whatsoever**. The following are recorded as claims the project must
   never make, in this or any later gate, while it remains hardware-free:
   achieved PL or Category or SIL for its own chain; any PFH, MTTFd, DCavg or
   CCF figure for its own chain; "certified", "compliant with", "TÜV
   assessed", "CE marked"; "validated per ISO 13849-2"; verified response time,
   stopping distance or protective field length; "safety functions tested"
   without "in simulation, against a model"; and any reproduction of a
   component's datasheet safety figure as if it were this system's result.
   The ADR reproduces this list in full. Record also that the TIA Portal
   safety acceptance test and program signature presuppose real F-hardware, so
   no acceptance is claimed.

## Facts block (verified 2026-07-30; the ADR cites these with this date)

- **PLCSIM Advanced F-I/O.** The V5.0 Function Manual (11/2022, A5E37039512-AE)
  §3.7 states that simulating a project with fail-safe input and output modules
  requires safety system version V1.6, V2.0, V2.1, V2.2, V2.3, V2.4 or V2.5,
  and does not work correctly with an older version. The V4.0 manual (05/2021,
  A5E37039512-AD) names only V1.6 and V2.0. TIA V18/V19 projects default to a
  higher safety system version, which is the probable cause of this project's
  earlier finding that no usable F-I/O channel existed. The supported list for
  V6.0 and later was NOT confirmed and is recorded as unverified.
- **F-I/O startup under simulation.** SIMATIC Safety manual (11/2022,
  A5E02714440-AM) §10.7.4: S7-PLCSIM does not fully behave like a real F-CPU,
  and F-I/O startup behaviour cannot be simulated exactly; §12.1: automatic
  reintegration occurs from the second cycle of the F-runtime group. Channel
  values initialise to 0 and value status to 1 on STOP→RUN. Simulated value
  status does not drive QBAD/PASS_OUT as real F-I/O does.
- **Standard-to-safety data rule.** SIMATIC Safety manual §8.2: only fail-safe
  data or fail-safe signals from F-I/O and other safety programs can be
  processed in the safety program, as standard tags are unsafe; warning S015
  requires process-specific validity checks, separately per F-runtime group.
  The reverse direction is unrestricted: the standard program may read all data
  of the safety program (§8.1). TIA's mechanism is disclosure — standard tags
  read by the safety program are listed in the safety summary — not protection.
- **PLCSIM Advanced API.** The manual directs access via tag name rather than
  address areas, warning against writing bytes belonging to other applications
  or containing internal data such as qualifier bits for fail-safe modules.
  Deterministic coupling to the F-runtime group is supported via PIP 1 and
  SYNC_PI/SYNC_PO registered as pre/post processing of the F-runtime group.
- **Scanner class.** SICK microScan3 Pro PROFINET: 275° aperture, ≤8
  simultaneously monitored fields, 128 monitoring cases, Type 3 (IEC 61496),
  Cat 3 / PL d (ISO 13849), PFH 8×10⁻⁸ h⁻¹ — component data, quoted as the
  modelled class, never as this system's achievement. nanoScan3 offers no
  PROFIsafe variant; S300/S3000 are discontinued.
- **Field-set switching safety.** Monitoring-case selection is made safe by a
  safe transmission channel, cross-validation against safely measured speed and
  direction, the scanner's permitted-successor switching-sequence check, and a
  switching-time margin. Warning field → speed reduction is normally a process
  function; protective field → stop is the safety function.
- **SLS/STO.** IEC 61800-5-2 as quoted by Siemens: STO supplies no
  torque-generating energy; SS1 decelerates then applies STO; SLS prevents the
  motor exceeding a defined speed limit. SLS is normally realised in the drive
  and selected by the F-CPU; the SLS stop response is parameterised as
  immediate STO or braking ramp then STO.
- **ISO 3691-4** is a Type C standard for driverless industrial trucks; with
  personnel-detection means muted, maximum speed is 0.3 m/s. ISO 13849-1:2023
  is the fourth edition; EN ISO 13849-1:2015 is withdrawn after 15 May 2027.

## Alternatives to record as rejected

- Presenting the vehicle's scanner as F-I/O of the fixed cell PLC: contradicts
  invariant 1 and is not real-world practice; an industrial reviewer would call
  it out.
- Keeping the standard-DB path as the primary design: Siemens S015 makes such
  data explicitly not fail-safe, so the demonstration would show safety logic
  reading unsafe data while claiming realism.
- Routing every Nav2 velocity sample through the PLC: latency and jitter place
  a timing-critical loop in Python, and gate-zeroing aborts goals through the
  progress checker; no published prior art exists for PLC-in-the-loop Nav2.
- Adding ROS 2 subscribers to the HMI backend: weakens `hmi/`'s boundary
  statement, the failure ADR 0005 exists to prevent.
- foxglove_bridge as the operator map view: read-only would depend on
  configuration rather than construction, and it adds a heavy dependency.
- Claiming a PL for the simulated chain: no hardware, no validation, no
  assessment — the claim would be false regardless of how good the logic is.

## Git

Repo-local owner identity is set. Pathspec-scoped commit of exactly the ADR
file, message `docs(adr): add ADR 0011 sensored autonomy architecture`. Report
to docs/reports/m5-01-adr-0011-sensored-autonomy-architecture.md in the
standard report format.
