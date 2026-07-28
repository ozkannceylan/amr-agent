# Brief m4r2-01 — ADR 0008: forklift commissioning gate, operator HMI layer, model sourcing

```
gate:                M4 (opening)
agent:               arch-docs
goal:                ADR 0008 records, as accepted, the owner rulings of 2026-07-28 that
                     insert the forklift commissioning gate and admit a local operator
                     HMI layer to the topology.
invariants_touched:  none changed. The ADR supplies the operator/HMI-layer decision that
                     ADR 0007 requires before any such layer may exist, and re-orders
                     gates on the ADR 0004/0007 precedent. Invariants 1-13 stand.
inputs:              [docs/adr/0002-vehicle-platform.md,
                      docs/adr/0005-bridge-layer-and-opcua-client.md,
                      docs/adr/0006-tia-derived-namespace-uri.md,
                      docs/adr/0007-safety-first-gate-order.md,
                      docs/reports/m4-00-hermes-survey.md (command-node section),
                      docs/safety/SRS.md sections 3-4,
                      plc/demo-cell/SPEC.md sections 4.2-4.3,
                      the facts block below]
deliverable:         docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md
done_when:           the ADR states the five decisions below with context, consequences
                     and rejected alternatives; every external claim carries the pinned
                     ref and its verification date; the amendment of ADR 0007's
                     operator-layer prohibition is explicit and scoped to the LOCAL
                     commissioning HMI; the SRS non-claims name exact SF ids; status
                     reads accepted with the owner-approval date 2026-07-28.
forbidden:           [editing any other ADR, editing docs/roadmap.md or docs/PLAN.md
                      (separate briefs), editing CLAUDE.md (separate infra brief),
                      writing code, inventing external facts beyond the facts block,
                      mentioning any deadline or presentation]
```

## Decisions to record (owner-approved 2026-07-28)

1. **New gate M4 — Forklift commissioning cell.** A tricycle forklift plant model in
   Gazebo, teleoperated from a local commissioning HMI, with every command passing
   HMI → PLC standard program → bridge → simulation and every state report returning
   simulation → bridge → PLC. Current M4–M11 shift to M5–M12 (Hermes stays parked,
   last). Rationale: extends the proven M3 claim — the PLC-supervised plant loop —
   to a vehicle-shaped plant plus an operator path before the safety layer lands on
   the richer cell; consistent with the LESSONS rule that the core architectural
   claim is proven first. Renumber mechanics belong to brief m4r2-02, not this ADR's
   text beyond stating the shift.

2. **Operator/HMI layer, local case.** A commissioning HMI joins the topology as an
   OPC UA client of the PLC — the decision ADR 0007 §5 reserved. It streams process
   setpoints (drive, steer, fork jog), an enable, an edge-triggered reset request and
   a UInt16 heartbeat into HMI-writable nodes. The PLC standard program forms all
   actuator setpoints, applies interlocks, and watchdogs the heartbeat: supervision
   loss zeroes every motion setpoint (the invariant-2 pattern at the HMI boundary).
   Distinguish this continuous setpoint-stream pattern from the Hermes-style discrete
   command handshake (m4-00: request token, PLC-owned Ready/Busy/Done/Fault); the
   remote command path remains parked at M12 and will need its own ADR. Record the
   known limitation the Hermes survey names: per-tag OPC UA writability is CPU-side
   enforcement, per-client scoping stays policy until access control is configured.
   The HMI lives in a new top-level hmi/ directory on the ADR 0005 precedent (a
   component that cannot live inside a layer without weakening that layer's boundary
   is its own layer).

3. **Teleop logic is process logic.** Teleop routing, the fork-height speed cap, fork
   soft travel limits and the lidar obstacle stop are process interlocks in the
   S7-1500 standard program, a second FB beside FB_DemoCellControl. They implement no
   SRS function: not SF-02 (vehicle e-stop/STO), not SF-03 (protective stop, scanner
   and bumper), not SF-04 (warning-field speed reduction), not SF-07 (zone
   monitoring), not SF-09 (supervision watchdog boundary pin). Those land at their own
   gates unchanged. The gate's recording must name each reaction as standard-program
   process logic — the same naming discipline the safety showcase already carries.
   Invariants 1, 2 and 7 are untouched by construction; no F-CPU is involved (none
   exists yet; its PLCSIM feasibility remains an open owner item for the safety gate).

4. **Model sourcing.** The forklift is an original, in-house model authored as plain
   SDF and driven by gz-sim built-in systems (the same plugin family the conveyor
   belt already uses); no ros2_control dependency. The considered source
   cangozpi/ROS2-Forklift-Simulation — and the owner's fork
   ozkannceylan/ROS2-Forklift-Simulation, which carries identical terms — is
   reference-only; no file from either may enter this repository. Facts, verified
   2026-07-28 against pinned commit ba74f767111c6c8a7a907c10d0d962c899a8b1c1:
   license NONE (GitHub API license field null, no LICENSE file in the recursive
   tree, all three package.xml files carry "TODO: License declaration"); drive
   kinematics are differential with a fixed caster, not tricycle; the robot has no
   meshes (primitive geometry only; the single pallet mesh is of unknown origin);
   stack is Gazebo Classic 11 / ROS 2 Humble against this repo's gz-sim Harmonic /
   Jazzy. Reference values that may be cited as prior art: fork prismatic travel
   ≈ −0.046 m to 3.244 m at 0.5 m/s.

5. **Relationship to ADR 0002.** Not superseded. ADR 0002 rejected a custom reach
   truck as the navigation platform on modelling cost; this gate's plant carries no
   navigation claim and needs primitive geometry, three controlled joints and one
   planar lidar. The vehicle gate (M6 after renumbering) keeps RB-KAIROS unless a
   later ADR rules otherwise.

## Alternatives to record as rejected

- Routing teleop through an F-CPU ("F-PLC" in the source plan): no F-program exists,
  its PLCSIM feasibility is unproven, and process logic in the safety program would
  break invariant 7.
- Declaring the networked obstacle stop a safety function: breaks invariant 1; the
  demo behaviour is identical when named as a process interlock.
- Vendoring or submoduling the fork: license NONE; contradicts the repository's own
  ARIAC precedent; would import wrong kinematics and Gazebo Classic plumbing.
- Homing the HMI under fleet/: the boundary-weakening ADR 0005 exists to prevent.
- WinCC HMI in TIA Portal: no repository artifact and it spends owner tool time,
  the scarcest implementation resource.

## Git

Repo-local owner identity before committing (read name/email from an existing owner
commit). Pathspec-scoped commit of exactly the ADR file, conventional message in the
style `docs(adr): add ADR 0008 forklift commissioning gate and HMI layer`. Report to
docs/reports/m4r2-01-adr-0008-forklift-gate.md in the standard report format.
