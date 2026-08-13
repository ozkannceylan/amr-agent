> **ARCHIVED 2026-08-13.** Historical record of the claude-supervised
> era (M0-M5 as originally planned). It is not maintained. Current
> status and the roadmap live in the root [README](../../README.md).

# PLAN

## M4 — Forklift commissioning cell: CLOSING

Agent-side work complete. Closes on the owner's formal showcase recording
(T5.1-T5.6 per plc/forklift/SPEC.md §11, the five scenarios per
sim/scenarios/forklift_commissioning.md, T6 beside them under the
TWIN-DEMO-MAP naming discipline) followed by the m4f-09 verifier run.

## Current gate: M5 — Sensored autonomous forklift (ADR 0010 D2)

Criterion: the M5 row of docs/roadmap.md, as amended by ADR 0015.
Architecture: ADR 0011 (+ 0012, 0014). Owner priority ruling 2026-08-06
stands: **the safety PLC is the deliverable** — the safety chain works and is
simulated as realistically as we can make it; autonomy is a working prototype
by owner ruling, its residue a stated backlog that gates nothing.

## STATE OF THE WORLD — 2026-08-10, read this first

**The TIA fix session ran 2026-08-07** (m5-59, TIA-FIX-PROCEDURE 63/63,
nothing open in TIA). New collective F-signature **`29FD2C52`**, offline =
online; six `Forklift/Safety/` leaves read-only, a client write refused
`BadNotWritable`. **Every figure in docs/VALIDATION-M5.md is re-signed to it**
(m5-68 revalidation, same morning):

- **F2, F3, F4 closed outright.** The shaft-doubt band no longer stops a
  healthy vehicle (0 demands in 262 F-samples, positive control alive).
- **The headline result:** full command 1.000 → **0.20 m/s** in the same
  50 ms sample as the warning trip (0.40 s against a 2.30 s budget), then a
  protective stop **1.47 m** short with the command held. E-stop
  operator-to-standstill 241/271 ms. SS1 second stage 0.95/1.016 s vs 1 s.
- **Torque-off reaches the plant live against the CPU** — 6 contactor
  episodes, **95 475** refused commands, same-run positive control. The
  vehicle boots deaf (`TorqueOffDemand` TRUE) by ruling.
- **F1 closed at the plant, one half open:** the standard-side third
  permissive conjunct was never isolated alone — one open-floor run with a
  shaft-doubt demand and nothing else standing closes it.
- The "cannot crash it" sentence carries the qualifier **straight**: a
  full-lock turn escapes the protective contour (rest at 0.29 m, process
  channel). AT-10 is no longer re-measurable — the clamp keeps the vehicle
  inside the limit, which is the fix working.

**Autonomy unblocked 2026-08-07** (m5-69): the cause was never F2 — the
committed spawn pose sat 1.00 m outside mapped free space. Routes A **5/5**,
G **5/5** (12.24 m, 21.7 s), B **0/5** (nav2 checks the footprint outline
only, recorded). docs/VALIDATION-M5.md still reads "NOT ACHIEVED" for the
mission rows and does not cite m5-69 yet.

**Demo infrastructure landed the same day:** `demo.sh up/down/status/home` +
`RUNBOOK.md` (m5-71), the writer bench panel (m5-74), the DDS domain read
from `allocation.yaml` (the HMI map pane worked for the first time), lidar
visualisation moved to RViz, and **the GPU enabled at 17:26** — llvmpipe →
d3d12/RTX 4050, so renderer-sensitive figures measured before it describe
the old environment. **The 4 min 09 s recording** (`assets/demo_m5.mp4`,
YouTube) is one continuous run of **teleop + the live safety chain;
autonomy is not in it.** Its session logs are committed
(agv/forklift/evidence/, the 15:47Z pair).

## What M5 still needs

1. **The recorded safety + autonomy showcase** — the existing recording
   covers (a)/(e) teleop-side; the (d) autonomy leg and the ADR 0014 D5
   permissive-not-compelled narration are not on any recording. No safety
   intrusion during an autonomous run has ever been produced (V4).
2. **The acceptance tests against `29FD2C52`** — AT-01/07/08 including the
   standard-program-in-STOP, bridge-stopped and session-down sub-cases, and
   AT-02/03/04 restated for M5. None has a run record on this build.
3. **F1's isolation run** (above), and the 5 Hz keepalive brief before the
   1.000 m/s clip is ever re-recorded (m5-64 finding 4).
4. **m5-19 gate verification, last.**

Briefed and never executed: m5-67 (functional-safety expert review),
m5-70 (teleop safety hardening — raises the n = 1 narrated figures),
m5-75 (owner study documents). The 08-07 afternoon commits (viz revert,
RViz, DDS domain, GPU, demo.sh home, README) carry no reports.

Wave history and closed-brief commit hashes: the report directory and
git log. Measured numbers a session should not re-derive: docs/TODO.md
"M5 — where the work stands". Standing agent discipline: one agent at a
time; evidence written as it lands (LESSONS 2026-08-04).
