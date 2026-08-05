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
controller**; the scanner's simulated signal reaches the F-program through the
**automated API-driven standard-DB stand-in** — m5-03 settled ADR 0011 D2 in
the tool 2026-08-04 and the F-I/O path answered no, so ADR 0015 amended
roadmap criterion (a) to the stand-in path, proven in the consumer's view and
against an independent OPC UA witness (m5-03b), labelled a stand-in
everywhere, S015-checked, and buying no safety integrity; autonomous mode is
governed by a **PLC-issued motion
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
   (f5ff3a7). 3. **m5-03 F-I/O feasibility — RUN 2026-08-04, verdict is
   `ADR 0011 D2 fallback`** (plc/forklift-safety/FIO-FEASIBILITY.md §7,
   docs/reports/m5-03-fio-probe-run.md). The ET 200SP F-DI configured,
   compiled, downloaded and ran with safety mode activated, but the module
   stayed passivated with no acknowledgement reachable, and the API's
   by-name write — which does return success and does read back — never
   appeared in the watch table. The standard-DB stand-in of
   plc/forklift-safety/SPEC.md §7 stays the input path. **Owner ruling
   2026-08-04 on the consequence: BOTH remedies** — the stand-in is upgraded to
   an automated API-driven standard-DB stimulus (a proof run first, verified in
   the consumer's view, since the probe only ever wrote an F-channel) **and**
   roadmap criterion (a) is amended by ADR. Part one PROVEN 2026-08-04
   (docs/reports/m5-03b-standin-stimulus-proof.md, on the probe copy — repeats
   on `safe_amr` before the gate cites it); part two DONE by **ADR 0015** and
   the amended M5 row (m5-20). m5-15 is written against the proven path.
   Definition of done: docs/TODO.md.

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

11. m5-10 Nav2 for the tricycle. CLOSED (a5b330d): SmacPlannerHybrid with
    REEDS_SHEPP and RegulatedPurePursuit, the Twist->tricycle conversion
    derived and checked in the simulator, and four measured cases including
    a goal the planner correctly refuses without the vehicle moving.
12. **m5-11 agv — CLOSED 2026-08-04** (f02ece7,
    docs/reports/m5-11-envelope-gate-node.md). All six acceptance observations
    measured on the owner's WSL machine. The §3.2 centrepiece came out a real
    number, not an assertion: gate release open-loop steps 0.5000 m/s and
    3.5249 m/s², closed-loop 0.0250 m/s and 0.4096 m/s² — 20x and 8.6x, the
    open-loop peak seven times what the chain is dimensioned for. A creep defect
    found by measurement (0.0852 m) is fixed and re-measured at zero.
    The envelope gate node: subscribes to the PLC
    envelope, gates motion, and sits BELOW the velocity smoother so it still
    acts with the link dead; the smoother moves to CLOSED_LOOP against
    odometry, because Nav2's open-loop default limits acceleration against
    its own last command and would lurch on gate release — the envelope gate node: consumes the PLC envelope, gates
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

### Wave E — PLC specifications and the build. BUILT 2026-08-05

The M5 PLC half was built in one owner-driven TIA session on `safe_amr` and
merged as `c9a4c77` (local only, unpushed). The §12 node set, the §14 standard
delta and the §4.5 F-delta are all on the CPU; HMI v2a connected to the live
controller for the first time. **The one part left unproven is the writer run**
— until it happens, `StandInValid` going TRUE, every T6 step and the reset path
on this build may not be claimed by any gate criterion. The authoritative
account is `plc/forklift/TIA-BUILD-PROCEDURE.md`'s progress block; the queue is
docs/TODO.md.

### Wave E — the specifications behind it

16. m5-15 plc — F-program spec. **UNBLOCKED 2026-08-04**: written against the
    automated stand-in stimulus of ADR 0015 (never watch-table *Modify*),
    carrying FIO-FEASIBILITY §6's three consequences and rewriting
    plc/forklift-safety/SPEC.md §7 and its §2 checkpoint F3 accordingly.
17. m5-16 plc — standard program delta: mode arbitration and envelope
    formation. CLOSED (57f0f57).
18. m5-17 interface — envelope, mode and process-stop nodes. CLOSED
    (682831d).
19. m5-18 safety-spec — PLr targets and the D5 claim boundary. CLOSED
    (bea766b).
20. m5-19 verifier — gate verification, last.

## Session handover, 2026-08-04

The vehicle side of M5 is built and evidenced through Nav2. The owner is
pausing agent work here to settle the PLC questions first, so a later session
should expect the next instruction to concern the PLC half, not the vehicle.

**The one hard external dependency — SETTLED 2026-08-04, this paragraph is kept
as history.** `plc/forklift-safety/FIO-FEASIBILITY.md` was written with its
verdict section blank, awaiting five owner-executed steps in TIA Portal and
PLCSIM Advanced. Those steps ran: the verdict is **`ADR 0011 D2 fallback`**
(§7), the configured F-I/O path answered no, and criterion (a) was amended by
**ADR 0015** rather than left reopened. m5-15 is unblocked and is written
against the automated stand-in stimulus. Wave 0 above carries the current
statement; nothing in this handover section is still pending.

**Agent discipline for the next session**, learned the hard way here: run ONE
agent at a time. Parallel fleets both hit usage limits sooner and multiply the
loss when a limit or a container suspension lands — four agents died to one
suspension in this session and three runs were lost to limits. Every brief
should require intermediate results to be written into the evidence as they
land rather than held for the end; that change reduced a lost run from hours
of work to minutes.

**What a resumed session should read first**, in order: docs/LESSONS.md (the
standing rule), this file, docs/TODO.md's "M5 - where the work stands"
section for the measured numbers that should not be re-derived, then the
report for whichever brief it is resuming.

Sequencing rule for this gate, from the owner: each module is verified before
the next builds on it. A wave does not open on an unverified predecessor.

## Restructure round m5r (ADR 0010) — CLOSED 2026-07-30

Eight briefs closed; m5r-09 ruled pass-with-findings after the SF-08
correction and the tracking reconciliation. Residue in docs/TODO.md.
Beside it: m4f-10, the one-command stack launcher (real bringup untested
off-container).

M0 closed 2026-07-26, M1 2026-07-26, M2 2026-07-26, M3 2026-07-28.
Filename convention stands: a file's number names its round.
