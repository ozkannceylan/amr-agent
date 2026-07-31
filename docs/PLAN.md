# PLAN

## M4 — Forklift commissioning cell: CLOSING

Agent-side work complete. Closes on the owner's formal showcase recording
(T5.1-T5.6 per plc/forklift/SPEC.md §11 and the five scenarios per
sim/scenarios/forklift_commissioning.md, T6 beside them under the
TWIN-DEMO-MAP naming discipline) followed by the m4f-09 verifier run.
Owner queue: docs/TODO.md.

## Current gate: M5 — Sensored autonomous forklift (ADR 0010 D2)

Criterion: the M5 row of docs/roadmap.md — safety scanner into the F-blocks,
per-sensor verification, beams visible in Gazebo, SLAM + Nav2 autonomy,
HMI v2 with mode selection, closed by a recorded safety + autonomy showcase.

Architecture settled with the owner 2026-07-30, recorded in ADR 0011:
the forklift's F-runtime group is the vehicle's **onboard safety
controller**; the scanner reaches the F-program through **configured F-DI
stimulated by the PLCSIM Advanced API** — the simulation's wiring, never the
process network, and **design intent that has never been run**: m5-03 settles
it in the tool and its verdict is blank, with the standard-DB stand-in as the
named fallback (ADR 0011 D2); autonomous mode is governed by a **PLC-issued motion
envelope** (enable, speed ceiling, zone permit) with the ~20 Hz loop onboard;
map and obstacles reach the operator over a **read-only monitoring plane**;
and the gate claims **PLr targets only, never an achieved PL, SIL or PFH**.
The single 1513F-1 PN hosting that onboard safety controller is a **simulation
artifact**, never a claim that one F-CPU guards a fleet, and because one
simulated CPU carries what the architecture calls per-vehicle safety the cell
and vehicle chains share an execution substrate in simulation (ADR 0011 D1,
ADR 0012 D2). Refined 2026-07-31 by ADR 0012 D1: the envelope's third element
is a **fixed-equipment / station permit**, not a zone permit, since zone
reservation is the fleet manager's under invariant 5 and one datum has one
owner under invariant 10.

### Wave 0 — foundations (in flight)

1. m5-01 arch-docs — ADR 0011. Issued.
2. m5-02 infra — CLAUDE.md §3 topology gains the monitoring-plane edge,
   owner-approved, authority ADR 0011 D4. After m5-01.
3. m5-03 plc — **F-I/O feasibility in the tool** (ADR 0011 D2 condition):
   PLCSIM Advanced version, safety system version, an ET 200SP F-DI in HW
   config, and whether the API writes its channel values by tag name.
   Owner-executed, agent-specified. Abort-to-fallback trigger of the whole
   scanner design; everything in wave C's PLC half depends on its verdict.

### Wave A — model and sensors, per-module verified

4. m5-04 agv — two 275° safety scanners at diagonal corners (~150 mm plane)
   plus one 360° navigation lidar; poses computed from the model's real
   geometry, `gz_frame_id` set, `<visualize>` set. Deliverable includes a
   **measured coverage artifact**: angular coverage around the vehicle, the
   overlap sectors, and the two named residuals — load occlusion in the fork
   direction, mast shadow wedge — each with its mitigation. No coverage
   claim that is not measured.
5. m5-05 sim — `VisualizeLidar` GUI plugin in the arena world (the
   `<visualize>` flag alone draws nothing in Harmonic); llvmpipe budget
   re-measured at the new sample counts, GUI and headless separately.
6. m5-06 agv — TF tree and the gz→ROS bridge for the new sensors; each
   sensor's data verified correct on its own before anything builds on it.

### Wave B — mapping and localization

7. m5-07 sim — install and record Nav2 and slam_toolbox (both absent on the
   verified host today), pinned versions.
8. m5-08 sim — `slam_toolbox online_async` mapping run; the map committed as
   a versioned artifact with one owner (invariant 10).
9. m5-08b agv — AMCL against the frozen map; localization evidence.
   (Renumbered from m5-09: that id was taken by the retired-platform purge,
   whose brief and report are already committed under it. A filename's
   number names its round, so the file keeps it and the plan moves.)

### Wave C — autonomy and the envelope

10. m5-10 agv — Nav2 written from scratch for the tricycle forklift
    (SmacPlannerHybrid/REEDS_SHEPP, RegulatedPurePursuit with
    `use_rotate_to_heading: false`, polygon footprint, Spin/BackUp removed);
    Twist → steer angle + drive speed. Nothing is migrated: the parked
    scenario's Nav2 parameter file was deleted with the retired platform
    (m5-09, ADR 0010 D1), so this brief starts from an empty config.
11. m5-11 agv — the envelope gate node: consumes the PLC envelope, gates
    motion, velocity smoother closed-loop against odometry.
12. m5-12 agv/sim — protective and warning field evaluation from the two
    safety scanners, output shaped as OSSD-equivalent channel pairs.

### Wave D — operator

13. m5-13 — the read-only monitoring service (directory recommended `agv/`,
    ruled at this brief per ADR 0011 D4).
14. m5-14 hmi — HMI v2: inherits M4, visually reduced, mode selection,
    emergency button (process stop plus F-state display, ADR 0010 D6b),
    safety lamps, live map.

### Wave E — PLC specifications, owner-executed

15. m5-15 plc — F-program spec: F-DI configuration (1oo2 equivalent,
    discrepancy, input delay), monitoring-case selection cross-validated
    against safe speed and direction, SLS monitoring, SS1 → STO.
16. m5-16 plc — standard program spec: envelope formation, teleop/autonomous
    mode arbitration, speed ceiling, fork-height clamp as process logic.
17. m5-17 interface — the OPC UA nodes the envelope, the mode and the
    extended mirrors need.
18. m5-18 safety-spec — PLr derivation for the new functions and the ADR 0011
    D5 non-claim list landed in the safety documents.
19. m5-19 verifier — gate verification, last.

Sequencing rule for this gate, from the owner: each module is verified before
the next builds on it. A wave does not open on an unverified predecessor.

## Restructure round m5r (ADR 0010) — CLOSED 2026-07-30

Eight briefs closed; m5r-09 ruled pass-with-findings after the SF-08
correction and the tracking reconciliation. Residue in docs/TODO.md.
Beside it: m4f-10, the one-command stack launcher (real bringup untested
off-container).

M0 closed 2026-07-26, M1 2026-07-26, M2 2026-07-26, M3 2026-07-28.
Filename convention stands: a file's number names its round.
