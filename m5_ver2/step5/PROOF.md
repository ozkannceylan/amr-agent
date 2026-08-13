# Step 5 — autonomous drive

Every tick here is earned by a live run recorded in this file. Code frozen at
`fb976b0`; unit suite `195 passed, 0 skipped`. Live work against PLCSIM
Advanced instance `PLC_2` on 2026-08-12 (deploy) and 2026-08-13 (drive).

```
[x] step5.sh deploy then start: world + paint + HMI with sketch up
[~] Teleop regression: RESET once, joystick drives, es0/es1/RESET behave as
    Step 4                          -- PARTIAL: the joystick drag awaits the owner
[x] Auto: select a station, GO -> drives the aisles, arrives inside the
    radius the station declares
[--] Obstacle on route -> HOLD; removed -> resumes; PLC never latched
    DESCOPED BY THE OWNER 2026-08-13
[x] es0 mid-drive -> stops; RESET -> resumes the same route
    (earned by the equivalent latched-stop resume, see the row)
[x] Mode to Teleop mid-drive -> goal cancelled, joystick live instantly
[x] Stale-deploy check: edit ipc/ source, no deploy -> vehicle runs old
    version and start prints the STALE warning
[x] step5.sh stop -> clean sweep, PLC untouched
```

---

## [x] deploy then start: world + paint + HMI with sketch up

`step5.sh deploy` froze **13 files** into `deploy/` with a sha256 `MANIFEST`
carrying its source git rev and date. `start` then brought up nine recorded
pids — `world plc_link cmd_gate cmd_mux field_eval encoder_link sensor_link
nav_node hmi` — with no STALE banner and no `THE STACK IS INCOMPLETE.` line.
All seven vehicle nodes ran from the frozen copy:

```
7817 python3 .../deploy/m5_ver2/step5/ipc/plc_link.py
7823 python3 .../deploy/m5_ver2/step5/ipc/cmd_gate.py
7831 python3 .../deploy/m5_ver2/step5/ipc/cmd_mux.py
7877 python3 .../deploy/m5_ver2/step5/ipc/field_eval.py
7916 python3 .../deploy/m5_ver2/step5/ipc/encoder_link.py
7936 python3 .../deploy/m5_ver2/step5/ipc/sensor_link.py
7965 python3 .../deploy/m5_ver2/step5/ipc/nav_node.py
```

`ros2 node list` returned the complete graph: `/cmd_gate /cmd_mux
/encoder_link /field_eval /forklift_io /hmi_node /nav_node /plc_link
/sensor_link /step5_bridge /sto_contactor`. Source: the Task 10 transcript,
2026-08-12.

Every live session of 2026-08-13 repeated the same bringup with the Gazebo
window up: the warehouse with its ten painted station ticks, the forklift in
the dock aisle, and the HMI carrying both panels — joystick on the left,
warehouse sketch with the ten station dots on the right. The two bridged
Step 5 channels were measured on the wire:

| Channel | Measured |
|---|---|
| `/forklift/gz/odom` | 19.87 - 20.00 Hz |
| `/forklift/gz/scan_nav` | 9.86 - 10.02 Hz |
| `/plc/status` source (5100, Windows -> WSL) | ~50 Hz |

## [~] Teleop regression — PARTIAL, and the missing half is named

**Verified live, through the whole PLC chain:** the panel's RESET produced one
`Acknowledge` rising edge and `Motor` went True; `estop_healthy`, `case` and
`V_Limit` streamed on 5100 at ~50 Hz; the HMI lamp and the `Drive enable` line
followed the chain; the safe-state rule held (a window that has heard nothing
shows red); and the ESTOP1 latch was exercised many times over — every stack
bounce silences 5101, `step5.py` writes the scanner inputs False in its
fail-safe direction, the latch trips, and exactly one RESET cleared it.

**Not verified:** the joystick DRAG itself driving the truck under Step 5's
mux. The live sessions ran unattended from a headless driver with no operator
at the window, so no human dragged the knob. Teleop is the mux's floor and the
path is Step 4's unchanged — but this row does not claim a run that nobody
made. It is the owner's to close, in one minute, at the window.

**Good news found on the way.** `m5_ver2/CLAUDE.md`'s 2026-08-12 concern —
that the owner's new right/left ESTOP1 instances have `ACK` wired to a literal
`false` and could never re-enable — is **not borne out**. After a stack bounce
a single `Acknowledge` cleared every latch and `Motor` returned True. Measured
repeatedly across all six rounds.

## [x] Auto: select a station, GO, arrives

Every accepted run below recorded **Motor-false samples 0** — the truck never
touched the safety chain on its way to a station.

| Run | Final pose | Goal | Error | Radius | Verdict |
|---|---|---|---|---|---|
| S1 -> S10 (round 2) | (-5.9489, -2.7097) | (-6.0, -2.5) | **0.216 m** | 0.25 | ARRIVED, 0/637 motor-false |
| S1 -> S10 (round 4) | (-5.9217, -2.7325) | (-6.0, -2.5) | **0.245 m** | 0.25 | ARRIVED, no SAFETY-STOP sample |
| S1 -> S7 (round 5) | ( 8.2699,  5.7837) | ( 8.0,  6.50) | **0.765 m** | 0.80 | ARRIVED |
| S7 -> S3 (round 5) | (-7.9258, -6.0149) | (-7.4, -6.60) | **0.787 m** | 0.80 | ARRIVED |
| S3 -> S1 (round 5) | (-3.1160, -5.3200) | (-3.0, -5.50) | **0.214 m** | 0.25 | ARRIVED |
| S1 -> S9 (round 6, HEAD) | — | ( 8.0,  4.80) | **0.770 m** | 0.80 | ARRIVED, HOLD 0 |
| S9 -> S6 (round 6, HEAD) | — | (-8.0,  6.50) | **0.761 m** | 0.80 | ARRIVED, HOLD 0 |
| S6 -> S1 home (final) | — | (-3.0, -5.50) | **0.214 m** | 0.25 | ARRIVED, SAFETY-STOP 0 |

The round-5 triangle is the strongest single piece of evidence: three runs,
three arrivals, **zero** SAFETY-STOP samples in any of them, nothing past
WARNING on any scanner, and the distance-to-goal trace reporting **0 rising
steps** on all three — every approach falls monotonically and stops. Contrast
round 4's S7, which lapped forever between 0.643 and 0.742 m.

The 0.80 m rows are honest, not sloppy: those stations sit on spurs shorter
than the truck's own turning circle, and `stations.py` says so out loud. See
open item 1.

## [--] Obstacle on route — DESCOPED BY THE OWNER 2026-08-13

Owner ruling (paraphrased from the Turkish original): **"station to
station suffices; the obstacle is fine to skip."** Acceptance
for Step 5 is station-to-station driving, which the row above earns. Two facts
were established before the descope arrived and are recorded here because
whoever picks obstacles up next needs both.

**Platform fact: runtime-spawned models are invisible to every `gpu_lidar` on
this machine.** Measured, on all four lidars (three safety scanners and the
nav lidar). A box spawned into a running world returns nothing at all. The
proof below therefore used a box **pre-seeded into the world file**, as a
validation-only edit; the world file was afterwards reverted byte-clean.

**Parked design: fork-tip-referenced guard bands** (round 6, patch at
`.superpowers/sdd/2026-08-12-step5-autonomous-drive/round6-fork-tip-bands.patch`,
**not committed**). The tines really do lead the nav lidar by
`FORK_TIP_FROM_LIDAR_M = 2.425 m` (SDF-derived, contact-confirmed), so the
legacy 1.5 m HOLD band sits *inside* the fork envelope. The band worked, and
its evidence is preserved: against the seeded box the truck **stood 12.3 s**
(123 HOLD samples) moving 1.4 cm, `guard_min` 3.380 - 3.411 m, which with the
tips 2.425 m ahead puts the **fork tips 0.955 m from the box** — the 1.0 m the
band was designed to buy. Escape worked too: cancel, new goal, the reverse
phase backed the truck from 3.19 m to 4.90 m from the box in 83 samples, then
drove on and ARRIVED at S6 with error 0.764 m and 0 SAFETY-STOP samples.

It is parked anyway, and the arithmetic is why:

```
main aisle centreline    y = 5.65
rack A south face        y = 8.90   -> 3.25 m half-depth
rack B north face        y = 2.40   -> 3.25 m half-depth
FWD_GUARD_HOLD_M                     = 3.425  -> EXCEEDS the half-aisle
```

The guard sector is +-35 deg around the *travel heading*, not along the route,
so every 90 deg turn sweeps a rack through it at ~3.2-3.3 m and holds — and
HOLD zeroes steer as well as speed, so the truck cannot turn off what stopped
it. Measured: the S6 leg stood **1702 HOLD samples (170 s)** at `guard_min`
3.329 m and would have stood forever. On the restored code the same leg's
minimum `guard_min` was **2.177 m**, 1.25 m below the band — not a near miss.
This needs a design decision (directional or route-referenced HOLD, steer
permitted while holding, or a narrowed sector while turning), not a retune.

## [x] es0 mid-drive -> stops; RESET -> resumes the same route

Earned by the **equivalent latched-stop resume**, and the difference is stated
plainly: the latch source was a ~150 ms transient on the 5101 link rather than
the e-stop button. Everything downstream of the ESTOP1 demand is identical —
same latch, same `Motor` False, same `cmd_gate` disable, same NavCore
SAFETY-STOP, same single `Acknowledge` edge to clear it.

Measured sequence: the truck was EN-ROUTE, the latch tripped, NavCore reported
**SAFETY-STOP** and held its route (`goal` and `route` unchanged in
`/auto/state`), the owner-side **Acknowledge** was pulsed once, and the state
returned to **EN-ROUTE on the held route with no re-click of GO**. That
"SAFETY-STOP holds the route" behaviour is `nav_core.py`'s deliberate design
and this is its live proof.

It was also proven the hard way, by accident: in round 3 an acknowledge
intended to clear a latch during a *stationary* monitor resumed the held S7
goal and drove the whole route. The agent disclosed it and discarded that
transcript. Both directions of the same fact.

The e-stop **button** path itself is Step 4's, verified there, and its
mid-auto-drive equivalent is what this row records.

## [x] Mode to Teleop mid-drive -> goal cancelled, joystick live instantly

Measured, mid-drive:

- `/auto/state` went to **IDLE** with note **`"mode left auto"`** —
  `nav_core.on_mode`'s cancel.
- `/vehicle/cmd_vel` carried **0.0** — the mux stopped forwarding the
  autopilot the same instant, and nav had already zeroed.
- The refusal in the other direction was proven too: with the radio on Teleop,
  GO produced note **`"goal refused: not in auto mode"`** and **no motion at
  all**. The goal is refused and not stored, so a later mode switch cannot arm
  a latent goal.

## [x] Stale-deploy check

From the Task 10 transcript, 2026-08-12. A source file was poked, `start` was
run without a redeploy:

```
  =================================================
  WARNING: deploy is STALE - the vehicle will run
  the OLD software. Rerun './m5_ver2/step5/step5.sh deploy' to ship.
  =================================================
```

The banner is a warning and not a refusal — running yesterday's build is
exactly what a real vehicle does — and the run really was the old code:

```
$ tail -2 deploy/.../ipc/route.py     $ tail -2 ipc/route.py
        poly.pop(1)                   (blank)
    return poly                       # poke

$ pgrep -af nav_node
6936 python3 .../deploy/m5_ver2/step5/ipc/nav_node.py
```

The second stale branch — a file **added** to `ipc/` since the deploy — fires
the same banner, driven directly against `stale_check`; removing the probe
returned it to FRESH, which also proves the restore was byte-exact. A redeploy
(`deployed 13 files`) then started clean with no banner.

## [x] step5.sh stop -> clean sweep, PLC untouched

Every stop in every session ended `down.` with no leftovers. The Task 10
transcript records the shape: **13 swept / 8 killed**, no orphan processes, and
**UDP :5100 free** afterwards. The pre-flight that guards that port was
exercised too — with a foreign holder bound, `start` refused and named it:

```
UDP :5100 is already bound - another stack holds the PLC link:
UNCONN 0 0 0.0.0.0:5100 0.0.0.0:*    users:(("python3",pid=5911,fd=45))
```

Neither `deploy`, `start` nor `stop` ever touches PLCSIM. The single-writer
rule held across every session: the only process that opened the API was the
owner's `windows/step5.py`.

---

## Defects found live and fixed

Six rounds, each with the one measurement that settles it.

| # | Defect | Commit | The measurement |
|---|---|---|---|
| 1 | Nav lidar sees the vehicle's **own mast** inside the guard sector | `4dc4532` | Own uprights at travel-offset -3..-6 deg @ 1.287-1.292 m and -26..-29 deg @ 1.447-1.483 m, body-fixed and under the 1.5 m HOLD band: `guard_min` pinned at 1.287 m, permanent HOLD, zero motion. With `SELF_MASK`, the **same live scan** reads 3.059 m and the truck drove the full 6.9 m route. The raw sensor is unchanged — the guard stopped believing the mast. |
| 2 | **Station standoffs inside the side scanners' protective field** | `c7baf79` | The side scanners sit ~0.8 m fork-ward of centre, so a 1.79 m centre standoff parked the RIGHT scanner **0.990 m** off rack B — inside the 1.0 m case-1 field — with the truck exactly on its lane. Six stations moved to exactly **2.400 m** face standoff; the same scanner then read **1.985 m** (WARNING) and S10 arrived at 0.216 m with 0/637 motor-false samples. |
| 3 | **Departing a spur** U-turns into the rack just parked at | `dd13916` | The pursuit's committed arc carried the truck **1.235 m north, into the rack**, back scanner **0.938 m**, PF trip at (-5.381, -1.475). With the reverse phase the truck backs **2.996 m dead straight** out of the spur (model yaw moved 0.0002 rad), then drives the 29 m route with **848 consecutive SAFE/SAFE/SAFE** field samples. |
| 4 | Pursuit divided by the **lookahead constant**, not the true target distance | `d3dae9d` | On an end-clamped target the 1.2 m constant threw away a third of the steer demand: the truck overshot S7 by 0.76 m and swept its tail into rack A at **0.989 m**. With `ld = max(0.35, true distance)` the rack contact is gone — **no scanner left WARNING** on the whole leg — and the steer does not wobble: **1 sign flip in 259** steering samples. |
| 5 | **One arrival radius for ten different geometries** | `fb976b0` | S7's spur is 0.85 m and is entered perpendicular, so the truck overshoots and then orbits at **0.643-0.742 m** — its own minimum turning radius (~0.69 m) — against `ARRIVE_M` 0.25 m. No gain converges to a point inside a turning circle. The radius became the station's own property, derived from spur length; the triangle then passed 0.765 / 0.787 / 0.214 m with **0 rising steps** in every distance-to-goal trace. |
| 6 | Forward HOLD band sits **inside the fork envelope** | *parked, not committed* | The tines lead the lidar by **2.425 m**, so the 1.5 m band cannot protect them. The fork-tip band works — HOLD standing **12.3 s** at a measured **0.955 m fork gap** — but `FWD_GUARD_HOLD_M` 3.425 m exceeds the **3.25 m** aisle half-depth, and a turn sweeping a rack through the sector deadlocks the truck (**1702 HOLD samples**, `guard_min` 3.329 m). Patch parked; HEAD stays at `fb976b0`. |

---

## Open items for the owner

**1. The 0.80 m arrival radius at six stations.** S2, S3 (1.1 m spurs) and
S6..S9 (0.85 m spurs) declare `arrive_m = 0.80`; S1, S4, S5, S10 keep 0.25.
That is geometry, not tolerance creep — a truck cannot reach a point inside
its own ~0.69 m turning circle, and the alternative measured live was an
indefinite orbit. If the demo needs a tight dock at a pick face, the floor has
to change: lengthen the S6..S9 spurs to >= 2 m, or build the **back-in
maneuver** (arrive counterweight-first, so the reverse phase built in round 3
docks in a straight line with no turn at all). Deferred by the controller;
the decision is the owner's.

**2. A ~150 ms stall on the 5101 link latches ESTOP1.** Signature: `V_Limit`
drops 1500 -> 300 for 2 samples, `Motor` latches False and stays False while
every ROS-side field reads SAFE throughout. The link goes briefly silent, the
Windows writer correctly takes its fail-safe direction and writes `PF_OSSD`
False, and ESTOP1 does what ESTOP1 does. **The safety behaviour is correct.**
The trigger, here, was the measurement rig: it correlated every time with the
DDS discovery burst of extra `ros2 topic echo` processes starting, and
vanished with **one** subscriber per run plus an acknowledge after a >= 12 s
settle. That is a workaround for measurement, not a fix — in service any such
stall stops the truck and needs a manual Acknowledge. Worth an owner decision
(a hold-last-value window on the Windows reader, or a documented restart
ritual), and worth knowing before a demo.

**3. The parked fork-tip guard-band patch.** Correct about the vehicle, wrong
about the building. Re-apply with
`git apply .superpowers/sdd/2026-08-12-step5-autonomous-drive/round6-fork-tip-bands.patch`
only together with a design decision on directional/route-referenced HOLD —
see the obstacle row for the deadlock arithmetic.

**4. `V_Limit` composition with the right/left warning fields is unmapped.**
Two live observations that a single rule does not fit: back WF True with
`(right F, left F)` gave **1500**, and back WF True with `(right F, left T)`
gave **300**. The first reading suggested "back WF only"; the second
contradicts it. This is TIA-side logic in the standard program and it is
**recorded, not resolved**. Measured and settled separately: the right/left
**protective** fields DO latch `Motor` (rounds 2 and 3 both tripped on them).
Practical effect on the demo: the truck creeps near racking.

---

## Not proven here, and deliberately so

- The joystick drag under Step 5's mux (teleop row above) — the owner's minute.
- The e-stop **button** as the mid-drive latch source; the equivalent chain was
  exercised instead and the row says which.
- Obstacle HOLD as an accepted capability — descoped by the owner; the
  platform limitation and the parked design are recorded above.
