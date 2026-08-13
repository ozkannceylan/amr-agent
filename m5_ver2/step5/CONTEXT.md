# Step 6 context

The file the next step reads first. `m5_ver2/CLAUDE.md` holds the PLC tag
table, the safety-program behaviour and the working agreements — it is the
ground truth for anything with a tag name in it. This page holds what Steps 1
to 5 added on top and what a Step 6 implementer must not break.

## What each step added

| Step | Added | Proved, against the live `PLC_2` |
|---|---|---|
| 1 | E-Stop chain, HMI joystick, command gate | `step1/PROOF.md`, 8 of 8 |
| 2 | Three microScan3 scanners, field evaluation, the monitoring case | `step2/PROOF.md`, 5 of 5 |
| 3 | Two encoder reading channels, fault injection | `step3/PROOF.md`, 6 of 6 |
| 4 | (copy; the safety chain unchanged) | `step4/PROOF.md` |
| 5 | **`cmd_mux` seam, the autopilot (graph router, pure pursuit, lidar guard), the warehouse sketch in the HMI, and a simulated deploy** | `step5/PROOF.md`, 6 of 8 ticked, 1 PARTIAL, 1 descoped |

Each step is a **copy** of the one before. That is the owner's ruling so every
step runs on its own; the cost is that a fix must be made in the copy being
worked on, and earlier copies are left frozen.

**After `cp -r stepN stepN+1`, run `diff -r stepN stepN+1` and read every line
the rename touched.** The whole-branch review found the code never diverged
between copies — every constant identical, `git log` on the earlier copies
empty — but the *prose* did, because a `sed` turned four statements from stale
into confidently wrong. One of them was executable: a README telling the
operator the wrong `ROS_DOMAIN_ID`. Step 5 carried three more of these into its
own final task; expect the same and sweep case-insensitively for `step4`,
`step 4`, `STEP 4` and the older step numbers.

## The command chain

```
  HMI joystick ──▶ /hmi/cmd_vel ─┐
                                 ├─▶ cmd_mux ──▶ /vehicle/cmd_vel ──▶ cmd_gate ──▶ sto_contactor ──▶ plant
  nav_node ──────▶ /auto/cmd_vel ┘   (mode)                            (Motor,
        ▲                                                               staleness,
        │ /hmi/mode (TRANSIENT_LOCAL, depth 1)                          V_Limit)
        └────────── HMI ──────────────────────────────┐
                                                      │ /plc/status
                                              plc_link ┘  ◀── UDP 5100 ◀── windows/step5.py
```

Three rules that Step 6 must not soften:

- **`/vehicle/cmd_vel` is the one seam.** Everything the plant ever sees passed
  through the mux and then the gate. A new command source is a new mux input,
  never a new publisher onto the gate's topic or the actuators.
- **The autopilot is a requester, not an authority.** `nav_core`'s states —
  `IDLE`, `EN-ROUTE`, `HOLD`, `SAFETY-STOP`, `ARRIVED` — exist for the
  operator's screen. The safety chain neither reads nor needs them.
- **`/hmi/mode` must stay TRANSIENT_LOCAL, depth 1.** `cmd_mux` and `nav_node`
  both subscribe latched; a VOLATILE publisher is incompatible with those
  subscriptions and delivers **nothing** — measured in Step 5's Task 6, where
  the Auto radio silently did nothing at all. The same applies from the command
  line: a `ros2 topic pub --once` latched publisher's retained sample dies with
  the process, so a late subscriber reads nothing (use `-t 3 -w 2`). And a node
  restarted mid-demo reads whatever latched sample survives — which is the
  HMI's, i.e. `teleop`, the safe direction.

## Six live rounds, and what each one leaves behind

Step 5 found six defects on the floor, one per round, against `PLC_2` on
2026-08-13. `step5/PROOF.md` carries the transcripts; these are the invariants
they bought, and every one of them is a way to break the truck again.

**1. Self-mask bearings are BODY-FIXED, and the mask is in travel-offset
degrees.** The nav lidar renders the vehicle's own two mast uprights inside the
travel sector — measured at travel-offset -3..-6° @ 1.287-1.292 m and
-26..-29° @ 1.447-1.483 m — and both clusters sit under the 1.5 m HOLD band, so
before `SELF_MASK` the autopilot held on every tick and never moved. The
windows are **absolute body bearings (offsets from π)**, checked in both travel
directions, and they simply never land in the reverse sector. Moving the lidar,
the mast, or the sector centre invalidates them; re-probe with a live scan
before trusting the constant. Each window also carries a **ceiling** — without
one the mask would hide the world behind it.

**2. The 2.4 m station standoff is a scanner dimension.** The side safety
scanners sit ~0.8 m fork-ward of the truck centre, so a fork-first approach
puts them 0.8 m closer to the face than the pose suggests. At a 1.79 m centre
standoff the RIGHT scanner read **0.990 m** against rack B — inside the 1.0 m
case-1 protective field — and latched `Motor` with the truck exactly on its
lane and zero tracking error. `2.4 = 0.8 scanner offset + 1.0 protective field
+ 0.2 field hysteresis + 0.4 pursuit residual`. `test_route.py` pins it. Any
new station that faces a rack or the conveyor takes the same 2.4 m, and any
change to the scanner mounting changes the number.

**3. The reverse phase is load-bearing, and not only where you last saw it
fire.** A tricycle cannot rotate in place, so leaving a station forks-first
commits the pursuit to a minimum-radius arc whose **first half drives the truck
at the rack it just parked in front of**: measured leaving S10, 1.235 m of
northing and the back scanner 0.938 m off rack B. Backing straight out spends
no floor at all and is the direction this vehicle guards best. With the wider
short-spur arrival radii the truck no longer commits into S6..S9, so the phase
rarely engages there — **it remains load-bearing at S4, S10 and anywhere the
truck actually drives into a spur.** Do not delete it because a run did not use
it. The 45° dead band (`ENTER` 120°, `EXIT` 75°) is what stops it chattering at
a corner; narrowing it reinstates the chatter.

**4. `arrive_m` is derived from spur length, and the rule is the thing under
test.** `0.80 if 0.0 < spur < 2.0 else 0.25`, computed from `STATIONS` and
`route.MAIN_Y`/`DOCK_Y` by
`test_route.py::test_arrival_radius_follows_the_spur_length`. The physics:
a perpendicular spur shorter than the truck's ~0.69 m minimum turning radius
cannot be hit tightly by **any** gain — measured, S7 settled into a stable
limit cycle at 0.643-0.742 m and lapped indefinitely. Move a station and its
radius re-derives; move a station and hand-write its radius and the test
fails, which is the point. Tightening the six 0.80 m stations needs longer
spurs or a **back-in maneuver** (arrive counterweight-first, so the reverse
phase docks in a straight line) — not a tuning pass.

**5. A guard band must never exceed the aisle half-depth.** Round 6 built
fork-tip-referenced forward bands, correctly: the tines lead the lidar by
2.425 m, so the legacy 1.5 m HOLD band sits *inside* the fork envelope, and the
new band demonstrably worked (HOLD standing 12.3 s at a measured 0.955 m fork
gap). It was still **not committed**, because:

```
main aisle centreline   y = 5.65
rack faces              y = 8.90 and y = 2.40   -> 3.25 m half-depth
FWD_GUARD_HOLD_M                                 = 3.425  -> EXCEEDS it
```

The guard sector is ±35° around the **travel heading**, not along the route, so
every 90° turn sweeps a rack through it — and HOLD zeroes steer as well as
speed, so the truck cannot turn off what stopped it. Measured: 1702 HOLD
samples (170 s) standing still, and it would have stood forever. A corridor
check that looks only at route *legs* will clear this and be wrong; the failure
is in the headings **between** legs. The patch is parked at
`.superpowers/sdd/2026-08-12-step5-autonomous-drive/round6-fork-tip-bands.patch`
and needs a **design** decision — directional or route-referenced HOLD, steer
permitted while holding, or a narrowed sector while turning.

**6. Runtime-spawned models are invisible to every `gpu_lidar` on this
machine.** Measured on all four (three safety scanners plus the nav lidar): a
box spawned into a running world returns nothing at all. Obstacle work must
**pre-seed geometry into the world file** and restart. Obstacle HOLD as a
capability was descoped by the owner on 2026-08-13 ("station to station
suffices"); if Step 6 picks it up, budget the world-file restart, and revert
the world byte-clean afterwards as Step 5 did.

## The three chains that reach `Motor`

All are ESTOP1 instances in the F-program and `Motor` is their AND. A demand
**latches**: clearing the cause does not re-enable, an `Acknowledge` edge does.

```
E-Stop button      the panel's PUSH / RELEASE EMERGENCY STOP
Protective field   3 scanners -> field_eval -> sensor_link -> PF_OSSD (+ _right, _left)
Speed / encoder    drive shaft -> encoder_link -> sensor_link -> ENC_A/ENC_B
```

Since 2026-08-12 the owner's program carries ESTOP1 instances for the right and
left scanners too, so `windows/step5.py` writes all six field inputs every
cycle.

## PLC facts measured during Step 5

- **The right/left ESTOP1 instances re-arm normally.** `m5_ver2/CLAUDE.md`
  records a concern that their `ACK` inputs are wired to a literal `false` and
  could therefore never re-enable. Not borne out: after every stack bounce a
  **single** `Acknowledge` cleared every latch and `Motor` returned True.
  Observed repeatedly across all six rounds.
- **The right/left PROTECTIVE fields do latch `Motor`.** Rounds 2 and 3 both
  tripped on them (right at 0.990 m, back at 0.938 m and 0.989 m).
- **`V_Limit`'s composition with the right/left WARNING fields is UNMAPPED.**
  Two live observations that no single rule fits: back WF True with
  `(right F, left F)` gave **1500**, and back WF True with `(right F, left T)`
  gave **300**. An early reading suggested "back WF only"; the second
  observation contradicts it. TIA-side logic, **recorded and not resolved**.
  The practical effect is that the truck creeps near racking.
- **Any ~150 ms stall on the 5101 link latches ESTOP1.** `V_Limit` drops
  1500 -> 300 for two samples, `Motor` latches False and stays False while
  every ROS-side field reads SAFE. The Windows writer is taking its fail-safe
  direction and the safety behaviour is correct — but it costs a manual
  Acknowledge every time. In Step 5 the trigger was the measurement rig itself
  (a DDS discovery burst from extra `ros2 topic echo` processes); it vanished
  with **one subscriber per run** plus an acknowledge after a ≥ 12 s settle.
  Open for the owner; see `step5/PROOF.md`.
- **The restart protocol, proven twice.** A stack bounce silences 5101 and
  trips the PF latch, so: restart, let it settle ≥ 12 s, then **one**
  Acknowledge. The Windows writer itself died once mid-round with PLCSIM API
  error `-47` (`NotUpToDate`, stale tag list); restarting it and acknowledging
  once brought `Motor` back.

## What will stop a Step 6 vehicle unexpectedly

**`V_Limit` is live and it is not on any acceptance list.** When `WF_Clear` is
False the standard program computes `V_Limit = 300` mm/s instead of 1500, and
the speed monitor demands a stop above it. Measured in Step 3: driving at
0.5 m/s commanded with racks 1.75 m from the back scanner, `Motor` dropped
0.68 s after enable with the encoder channels agreeing. Step 5's answer is to
obey the limit **at the source** as well as at the gate — `nav_core` caps its
own command, so the truck approaches the ceiling from below instead of through
it — and to put `GUARD_SLOW_M` (3.0 m) **outside** the case-1 warning field
(2.5 m) so the lidar creeps the truck before `WF_Clear` can drop under a
vehicle still doing 0.7 m/s. Keep both properties or reinstate the trap.

## The field logic, unchanged from `m5-plc-debug/microscan3.py`

```python
FIELDS = {1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}   # case: (PF, WF) [m]
N_SCAN = 3          # consecutive scans before a state change
HYSTERESIS_M = 0.20 # extra margin required to RE-CLEAR
```

Three properties are load-bearing:

- **`pf` and `wf` are TRUE when the field is CLEAR**, matching `PF_OSSD` and
  `WF_Clear`. Inverting this inverts the safety function.
- **No measurement means violated.** Silence is not clear.
- **An unreadable monitoring case selects case 3**, the largest field — the
  value the system falls into when the case bits are unreadable, so it is the
  fail-safe path and must work.

## The encoders

`encoder_link` reads two `JointStatePublisher` systems on `drive_wheel_joint`
and converts each independently: `omega × 0.12 m × 1000`.

**A single-channel tested system, never a two-channel one.** One shaft, two
readings, both dying with the shaft they read. No Category, no Performance
Level, no SIL, no PFH is claimed anywhere in this tree.

The F-program faults on `|ENC_A − ENC_B| > 50` mm/s and on a 2800 mm/s ceiling.
The panel injects the faults, because a broken encoder is a field fault and the
PLCSIM API is the wiring — the vehicle sends what the shaft did and never lies.

## The single writer, and how to drive it

**Exactly one process opens the PLCSIM Advanced API: the current step's
`stepN.py` on Windows.** No ROS node, no test, no helper script, and two steps'
writers must never run together. That rule shapes everything below.

**`windows/step5.py` is a tkinter PANEL, not a stdin reader.** Step 4's
`es0` / `es1` / `a` / `q` typed commands became **PUSH EMERGENCY STOP**,
**RELEASE EMERGENCY STOP**, **RESET**, an `ENCODER: OK / FREEZE A / OFFSET A`
row, and closing the window. Typing at the console it was launched from does
nothing. The panel and the PLC cycle are two threads on purpose: Tk stops
pumping events while a window is dragged, and the sole writer must not freeze
with `Motor` energised.

**For unattended runs, drive the same control loop headlessly.** Step 5's live
sessions used a scratchpad `step5_headless.py` that imports `control_loop` and
reads commands from a `plc_cmds.txt` file — same single writer, same trip path,
no window. **That tooling lives in the scratchpad, not in the repo**: it is a
measurement rig, not a deliverable, and committing it would put a second
plausible writer next to the real one. Rebuild it per session from the panel's
own `control_loop` signature.

**A demo that a human attends should use the panel.** An unattended session
cannot close the teleop row — Step 5's PROOF says so explicitly rather than
claiming a drag nobody made.

## Deploy: what ships and what does not

`step5.sh deploy` freezes `ipc/` plus `agv/forklift/config.yaml` (13 files)
into `deploy/` with a sha256 `MANIFEST`, laid out at **source depth** so every
relative path inside still resolves. Every vehicle node runs from that copy;
`start` refuses without one and prints a loud STALE banner when the source has
moved on.

**The HMI is deliberately NOT deployed** — it is the operator's panel on a
commissioning laptop, not software on the industrial PC, and drawing that line
is the deliverable. The honest consequence: an edit to `ipc/status_contract.py`
changes the HMI immediately and the vehicle not at all, because the HMI imports
the source module and every vehicle node imports the deployed one. Step 6 keeps
this boundary or states plainly why it moved it.

## Ports

| Port | Direction | Payload |
|---|---|---|
| 5100 | Windows → WSL | `estop_healthy`, `motor`, `case`, `v_limit`, `ts` |
| 5101 | WSL → Windows | `pf`, `wf`, `pf_right`, `wf_right`, `pf_left`, `wf_left`, `enc_a`, `enc_b`, `ts` |

**Unchanged for Step 6.** The 5101 contract has two implementations that agree
only by inspection: `sensor_link.payload()` writes it, `step5.py
parse_sensor()` validates it. They are a pair. Changing one without the other
is silent.

## Isolation

`GZ_PARTITION=step5`, `ROS_DOMAIN_ID=95`. **Step 6 takes `step6` / `96`**, or
two stacks share one graph and `stop` sweeps the wrong processes. The ports do
**not** change, which means the reverse hazard is real: a concurrently running
Step 5 stack holds UDP :5100 and the new one's `plc_link` binds nothing.
`step5.sh start` pre-flights the port and refuses, fail-closed, naming the
holder — carry that guard forward.

`ROS_DOMAIN_ID` does **not** isolate Gazebo; gz transport is not DDS.
`GZ_PARTITION` is what scopes the sweep, and `stop` reads it back off a
recorded pid rather than trusting the shell it runs in.

## Measurement habits that cost a round each

- `ros2 topic echo /auto/state` must **NAME** the type
  (`std_msgs/msg/String`); type discovery under a short timeout is unstable
  here, and a Step 5 gate wasted a cycle on it.
- Echo with `--truncate-length 3000`. The default 128 characters cuts
  `/auto/state` off before `guard_min` and blinded a whole round.
- A YAML `data: ` with nothing after it parses as the **string `"None"`** — a
  goal cancel must be published as `"data: ''"`.
- **One subscriber per run.** More than one has stalled the 5101 link long
  enough to latch ESTOP1 (see the PLC facts above).

## Known debt carried forward

- **Discharged in Step 5:** the topic-literal debt. `status_contract.py` is now
  the one home for every ROS topic name `config.yaml` has never heard of —
  `/plc/status`, `/hmi/cmd_vel`, `/vehicle/cmd_vel`, `/auto/cmd_vel`,
  `/auto/goal`, `/auto/state`, `/hmi/mode`, the fields/encoders/scan names.
  The gz names stay in `config.yaml` (owner ruling 2026-08-12) and both the
  launch file and `nav_node` read them from there. **Do not add a second home
  for either group.**
- `gated_command`'s third parameter is still named `motor_ok` while every
  caller passes the composite `enabled()`. A future edit "correcting" it would
  reinstate a closed leak.
- `step5.sh`'s startup name list is positional and must be hand-synced with the
  spawn order, and `PATTERNS` must gain an entry for anything added to the
  stack or `stop` orphans it and still prints "down."
- No committed test covers `windows/step5.py`'s fail-direction path (the
  `finally` block that writes `E-Stop` and all six field inputs False).
- Prose in `step5.sh` and `gazebo/step5_world.launch.py` still carries stale
  step-number and count statements ("Port 5101 arrives in a later step", "All
  four recorded command lines" — there are nine pids now). Code-only files, so
  Step 5's docs task could not touch them; sweep them in the copy.
- `update_auto` redraws the sketch canvas at 20 Hz with no dirty guard; the
  dock-door marker in `map_panel.py` is four literals; a selected station dot
  stays orange after STOP. All cosmetic, all deferred by the owner's taste.
- No test ties `config.yaml`'s `gz_odom` / `gz_scan_nav` spellings to
  `model.sdf` (the same gap the drive-speed pair has).
