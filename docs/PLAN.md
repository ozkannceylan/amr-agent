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

### Wave 0 — foundations. CLOSED

1. m5-01 ADR 0011 (166ffb3). 2. m5-02 topology monitoring-plane edge
   (f5ff3a7). 3. **m5-03 F-I/O feasibility — WRITTEN, AWAITING THE OWNER'S
   TIA SESSION** (plc/forklift-safety/FIO-FEASIBILITY.md, verdict section
   blank). This is the gate's one hard external dependency: it opens the
   PLC half and blocks m5-15 alone. A judge review found that a NO verdict
   also puts roadmap criterion (a) in question — see docs/TODO.md, the
   blocker deferred by owner ruling until the verdict is in.

Beside the wave: ADR 0012 envelope composition, ADR 0013 vendor gate (M8),
ADR 0014 motion control locus, and the m5-judge architecture review that
forced the last two.

### Wave A — model and sensors. CLOSED

4. m5-04 two 275° diagonal safety scanners + 360° navigation lidar with
   measured coverage (4b623c1); m5-04b the rear self-occlusion band
   measured and accepted as residual R8 (ab9b5f9).
5. m5-05 beam visualisation, m5-05b bringup realignment, both verified
   live (c938307).
6. m5-06 measurement/safe channel split and sensor TF (6068b31).

### Wave B — estimation, mapping, localization. CLOSED

7. m5-07 toolchain installed and pinned (5bdf09a).
8. m5-07b interim odom transform (682831d); **m5-07c realistic odometry** —
   IMU, tricycle wheel odometry, EKF, all noise from a datasheet (72987b0);
   m5-07d encoder-gated standstill (1cafefb); m5-07e the post-drive gate
   leak diagnosed to the steer axis and closed (9cc9c0d).
9. m5-08 warehouse world with measured landmark cover (3fb88a0);
   m5-08b the first SLAM map (5c34865); **m5-08c judge review** — three
   blockers (4415c08); m5-08d rebuilt map, world→map registration, absolute
   scoring (75e244b).
10. **m5-08e AMCL, measured absolutely** (783185b): steady state rms
    0.124 m / max 0.263 m, convergence from 1.166 m and 10° wrong, a 128.7 s
    dwell in the worst degenerate stretch, and a fork-first reverse pass —
    every figure beside the instrument's 0.141 m floor.

### Wave C — autonomy and the envelope. IN FLIGHT

11. **m5-10 Nav2 for the tricycle — in flight.** Configuration and launch
    landed unverified (307dd10, 73e1e62) when a usage limit cut the first
    agent; the resumed agent verifies them rather than inheriting them.
12. m5-11 agv — the envelope gate node: consumes the PLC envelope, gates
    motion below the smoother so it acts with the link dead, velocity
    smoother closed-loop against odometry.
13. m5-12 agv/sim — protective and warning field evaluation from the two
    safety scanners, output shaped as OSSD-equivalent channel pairs;
    inherits R3 and R8 as field-geometry constraints.

### Wave D — operator

14. m5-13 — the read-only monitoring service (directory recommended `agv/`,
    ruled at this brief per ADR 0011 D4; the judge's finding on
    construction-versus-runtime enforcement is in TODO).
15. m5-14 hmi — HMI v2a (visually reduced, mode selection, emergency button
    per ADR 0010 D6b, safety lamps) then v2b (live map, after m5-13).
    Note m5-16's hard dependency: HmiProcessStopRequest starts TRUE, so the
    §14 program is inert under HMI v1.

### Wave E — PLC specifications, owner-executed

16. m5-15 plc — F-program spec. **BLOCKED on m5-03's verdict.**
17. m5-16 plc — standard program delta: mode arbitration and envelope
    formation. CLOSED (57f0f57).
18. m5-17 interface — envelope, mode and process-stop nodes. CLOSED
    (682831d).
19. m5-18 safety-spec — PLr targets and the D5 claim boundary. CLOSED
    (bea766b).
20. m5-19 verifier — gate verification, last.

Sequencing rule for this gate, from the owner: each module is verified before
the next builds on it. A wave does not open on an unverified predecessor.

## Restructure round m5r (ADR 0010) — CLOSED 2026-07-30

Eight briefs closed; m5r-09 ruled pass-with-findings after the SF-08
correction and the tracking reconciliation. Residue in docs/TODO.md.
Beside it: m4f-10, the one-command stack launcher (real bringup untested
off-container).

M0 closed 2026-07-26, M1 2026-07-26, M2 2026-07-26, M3 2026-07-28.
Filename convention stands: a file's number names its round.
