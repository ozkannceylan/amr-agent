# Brief mc-02 — ADR 0014: the motion control locus, locked

```
gate:                M5
agent:               arch-docs
goal:                ADR 0014 locks where motion control lives, records why
                     the alternative was rejected on industrial evidence, and
                     bounds a reading of ADR 0011 D1 that was drifting.
invariants_touched:  none. Invariants 1, 5, 6, 9, 10 and 11 all bear on this
                     and the ADR should show the check rather than assert it.
inputs:              [docs/reports/mc-01-motion-control-locus-research.md
                      (the evidence base — cite it, do not restate it),
                      docs/adr/0011-sensored-autonomy-architecture.md D1 and D3,
                      docs/adr/0012-envelope-composition.md D1,
                      docs/interfaces/opcua-nodes.md section 12,
                      plc/forklift/SPEC.md sections 7 and 13,
                      the rulings block below]
deliverable:         docs/adr/0014-motion-control-locus.md
done_when:           the five decisions below are recorded with context,
                     consequences and rejected alternatives; the ADR is
                     explicit that it CONFIRMS ADR 0011 D3 and ADR 0012 D1
                     rather than superseding them, and that it BOUNDS the
                     reading of ADR 0011 D1 without editing it; the rejection
                     of the alternative carries its actual reasoning so it is
                     not relitigated from memory; the measured and derived
                     figures are quoted with their source and marked as
                     container measurements where they are; status reads
                     accepted with the owner-approval date 2026-07-31.
forbidden:           [editing any other ADR; editing roadmap.md, PLAN.md,
                      TODO.md or opcua-nodes.md (separate briefs); designing
                      PLC logic, vehicle logic or node names; claiming any
                      achieved PL, SIL or PFH; presenting the simulation's
                      measured latency as a property of a real vehicle;
                      committing (the orchestrator commits)]
```

## Decisions to record (owner-approved 2026-07-31, on mc-01's evidence)

1. **Motion control closes onboard the vehicle; no motion value at any
   granularity crosses OPC UA.** The vehicle's computer runs perception,
   localization, planning and the path-following loop, and writes the
   actuators. This confirms ADR 0011 D3 rather than changing it. The evidence
   is that real systems have exactly two motion seams — continuous velocity
   setpoints between the follower and the drives, always over deterministic
   onboard links, and path or mission download between fleet and vehicle,
   which is the only motion interface that tolerates a network.

2. **The alternative is rejected, and the reason is recorded so it is not
   relitigated.** The owner proposed that the vehicle send incremental motion
   work ("this much to the right, this much forward") for the PLC to execute,
   with steer-by-wire and motor control flowing through the PLC. It was
   examined seriously and rejected on this argument: correcting motion error
   requires pose at loop rate; pose is produced onboard by SLAM; so either
   pose streams to the PLC every sample — which is the same network-in-the-loop
   the architecture forbids, merely reversed — or correction stays onboard, in
   which case the PLC contributes only dead time to a loop the machine is
   already closing. Record that this middle form is not shipped by the vendors
   surveyed, and record why M4's teleoperation is genuinely different: there a
   human closed the loop at human bandwidth, so the PLC forming every setpoint
   cost nothing.

3. **ADR 0011 D1's "onboard" reading is bounded to the F-runtime group.** The
   safety program is read as the vehicle's onboard safety controller. The
   STANDARD program is not: it is the cell's PLC — the owner of the fixed
   equipment, the OPC UA server of invariant 4, and at M6 one box serving four
   vehicles. The ADR states this boundary and says plainly that extending the
   onboard reading to the standard program would have made the M6 arithmetic
   incoherent. ADR 0011 is not edited; this ADR bounds how it is read.

4. **The command interface, three seams.** (a) Supervision, PLC to vehicle
   over OPC UA: the envelope of ADR 0012 D1 as specified in
   `docs/interfaces/opcua-nodes.md` §12, formed at the PLC's scan and
   republished by the bridge, contractually insensitive to its own rate; the
   vehicle returns its applied mode and a heartbeat. On envelope staleness
   beyond the vehicle's freshness window the vehicle takes a controlled stop
   onboard; on heartbeat loss the PLC publishes the non-permissive envelope.
   Both are degraded-mode behaviour and neither is a safety function
   (invariant 2). (b) Motion, onboard only: the controller's velocity command
   through an odometry-closed smoother, then an envelope gate that stops on
   enable-false-or-stale and otherwise clamps to the ceiling — the gate sits
   BELOW the smoother so it still acts with the link dead. (c) Orders, at M6:
   VDA 5050 node and edge graphs, the network-tolerant seam.

5. **The disclosure obligation.** In autonomous mode the PLC's authority is
   permissive and *checked, not compelled*: the enforcing gate runs on the
   vehicle, and the compelling backstop is a safety layer that is modelled
   rather than real while the project is hardware-free. This is a fair
   criticism and the answer is disclosure, not silence — the M5 showcase must
   narrate it explicitly, and the gate's evidence must show the readback that
   demonstrates the vehicle honouring the envelope. Record also where the
   project's PLC-depth claim actually rests: M4's teleoperation, the F-layer,
   and M6's station handshake.

## Figures to record with their provenance

From mc-01, quoted as measured or derived and marked as CONTAINER
measurements where they are: the link's median one-way latency; the position
error a given delay produces at warehouse speed; the loop-bandwidth limit an
in-loop delay imposes; and the docking scatter a given jitter produces against
the industry figure mc-01 cites. Do not restate mc-01's argument — cite it.
Do not present any of these as properties of a real vehicle.

## Alternatives to record as rejected

- The incremental-work interface of decision 2, with its reasoning.
- Streaming pose to the PLC at loop rate so the PLC could correct: the
  forbidden network loop, reversed, and it also puts a timing-critical
  dependency in the bridge's Python path against invariant 9.
- Leaving the ADR 0011 D1 reading unbounded: it was already drifting toward
  the standard program, and at M6 that reading has one PLC being four
  vehicles' onboard controllers at once.

## Git

Report to docs/reports/mc-02-adr-0014-motion-control-locus.md in the standard
report format. Do not commit — the orchestrator commits.
