# EVIDENCE_G1.md — one truck, the fleet's own order, driven over Nav2

`SPEC_ADAPTER.md`'s mission sentence is one line long:

> retire `m6/ipc/nav_node.py` + `nav_core.py` + `follower.py`
> (+ `avoid.py`) as the motion engine and put a NAV2 ADAPTER in their
> place that presents the byte-identical contract to the untouched
> fleet layer

**This file is the payment of that sentence for one truck.** It is not
a design document — the two specs are, and their AMENDMENTS §3–§10 are
the ruling trail this file measures. What follows is nine field waves,
nineteen runs, sixteen named defect classes, three architecture rulings
with the numbers that bought them, two rulings overturned in the open,
and one session where the fleet closed two orders in a row and every
instrument read zero.

Everything below was taken on **this rig** (WSL Ubuntu 24.04, ROS 2
Jazzy, gz-sim 8.11.0, RTX 4050 through D3D12 / Mesa 25.2.8) **headless**,
partition `m6`, domain 96, one truck `f1`, with the Windows-side writer
in `--virtual` F-PLC (`python m6\windows\m6.py --vehicle f1 --virtual`).

**On provenance.** The session-report instrument (`READING.txt`) arrived
with wave C5. Runs 1–10 therefore have raw capture and no reduction, and
their numbers here come from the wave commit message and from the module
docstring that quotes it. Where a commit message states a figure that
cannot be recomputed from the archive it names, this file uses the
archive's own number and says which is which — §6 lists the three that
came out that way. No number in this file was written from memory.

---

## 0. The answer, before the working

| | |
|---|---|
| **the bar** | `m6_ver2/logs/run19-c9-session`, 2026-09-02 — **two consecutive clean fleet-DONE orders**, S1 pick → S4 drop, the second queued **21.6 s** after the first completed and driven **from S4** rather than from the spawn. Nobody touched the truck. |
| **the fleet** | `done=1` at 14:19:10.762, **270.1 s** after its order was queued; `done=2` at 14:26:47.413, **435.1 s** after its own. `queue 0` throughout (`fleet.log`) |
| **the wire** | 4 × EN-ROUTE, 4 × ARRIVED, **zero BLOCKED**, every `note` empty |
| **the chains** | 4 dispatched, `remain=` **4.00 / 43.89 / 43.91 / 43.89 m**, 141 closing samples, **worst rise 0.000 m on every chain** (one 0.020 m rise on the last station spur's straight ruler) |
| **the corridor** | worst offset from each chain's **own granted polyline** 0.260 / 0.273 / 0.330 / 0.265 m — all inside the **0.366 m** sagitta a right angle rounded at r = 1.25 m cuts. Worst northward of `y = 10.0`: **+0.295 m** (the run-10 comparison every reading prints: **+2.43**) |
| **the cusps** | **0** commanded traction sign flips in **45 471** commands (run-16 comparison: 14 in 30 s) |
| **the PLC** | Motor-False edges **0**; PF demand edges **0**; V_Limit 1500 ↔ 300 by field, `case=1` and `estop_healthy=True` on every edge |
| **the old enemies** | creep plateaus **0** (run-7 comparison: 4, means 0.0816–0.0905) · Smac exhaustion refusals **0** (runs 15/16: **13** and **8**, all over free paint) · `DirectionStablePath` holds **0** (run-10 comparison: 29 lines, eleven of them holds) |
| **the estimate** | whole session `err_m` n=4007 mean **0.0793** p95 **0.1883** max 0.3591; **within 0.60 m of S4: n=784, mean 0.0568, p95 0.0619** — the first S4 sample in the campaign. Every earlier session prints `within 0.60 m of S4: err_m None` |
| **the rig cost** | RTF n=8565 mean **0.8394** p95 1.1756 · CPU (% of one core) adapter mean 50.2 max 60.0, `gz_server` mean 163.7 max 182.6, `planner_server` mean 17.2 max 20.7 |
| **the three rulings** | §4 TRANSIT drives RPP · §5 the derived trees drop `DirectionStablePath` · §9 ring chains drive their own polyline on `/follow_path` |
| **the two overturned** | §6's implied fix, built and flown and **refused** (§7) · §5 × §8, measured **irreconcilable** and dissolved by §9 |
| **the classes** | **sixteen**, D1–D16, every one found on the floor, named, and closed with a red test — §3 |
| **suite** | **571 passed** at `8aa03a4` (wave A opened at 161). `m5_ver3` 1218 and `m6` 589 untouched; `m6/`, `m5_ver3/` and `agv/` tracked bytes never edited |
| **still open, named** | §6 — four trucks unmeasured, one station pair driven, the chain watchdog's true positive never fired, a 1.703 m bay-turn swing, and six more |

---

## 1. The cell

### 1.1 What runs, per truck

`m6v2.sh` is the one operator door. It owns the order, the environment,
the fleet-layer children and the world; `truck.sh` owns one truck's
stack. Wave C1's first live bringup counted **24 children** and every
one of them is named in `START_f1.txt`:

| owner | children |
|---|---|
| `m6v2.sh` | `broker`, `world`, then m6's fleet children per truck — `plc_link`, `cmd_gate`, `cmd_mux`, `field_eval`, `encoder_link`, `sensor_link`, `vda_agent`, `hmi` — and `fleet_manager` |
| `truck.sh` | `imutf`, `lasertf`, `odom` (wheel odometry), `ekf`, `smoother`, `scanmask`, `amcl`, `planner_server`, `controller_server`, `behavior_server`, `bt_navigator`, `nav_lifecycle_manager`, `adapter` |

The collision monitor is configured and dark. `nav_node` is **not**
started: that is the whole point of the branch.

Ownership is `partition AND the M6V2 marker`, so a plain m6 cell can
neither be killed by this script nor joined to it. The exposure runs one
way only and is named rather than hidden: m6's own sweep is
partition-keyed and *will* nominate this cell, which is why `start`
refuses when a plain m6 world is already up.

### 1.2 The namespacing, and why it is the only mechanism

`SPEC_NAMESPACING.md` §1 does not choose namespacing for taste. The
costmaps are **sub-nodes with no command line** — the servers construct
them, their FQNs are `<parent_ns>/local_costmap/local_costmap`, and
`-r __node:=` cannot reach them. Four un-namespaced controller servers
would be four nodes all called `/local_costmap/local_costmap`. So every
per-truck spawn line carries the same three remaps, uniformly:

```
--ros-args -r __ns:=/<vid> -r tf:=/tf -r tf_static:=/tf_static
```

with **prefixed frames** (`fN/odom`, `fN/base_link`), **one shared
`map`**, one `/tf`, one `/clock`, one gz server, one union bridge.
`wheel_odometry` additionally runs through a bootstrap that rebinds its
config module, because no remap can reach a bare `frame_id` written in
code.

The derivation is a **counted rewrite with an inverse**. Wave A's
`instantiate_truck.py` prints its own arithmetic at every boot —

```
instantiate_truck: m6_ver2/vehicles/f1 <- 13 files, 137 literals,
                   spawn -17.00 10.00 yaw 3.14159
```

— and its residue pin requires the inverse replay to equal the donor
**byte for byte**. The spec's blanket `/forklift/` rule was wrong and
the tool says so in its own refusal: the prefix has two populations, gz
topics and `agv/forklift` crib paths, and the second must not move.

### 1.3 The firewall, proven on the wire

`/fN/gz/odom` is ground truth. Nothing in the adapter or the fleet path
may read it. The mechanism is `fleet_odom_firewall.py`, which re-derives
the **m6-side** config the fleet actually opens and re-points one key,
counted and undoable. It is the second line of every `START_f1.txt` in
the campaign:

```
fleet_odom_firewall: m6/vehicles/f1/config.yaml
                     topics.gz_odom /f1/gz/odom -> /f1/est/odom
```

Wave C1 did not take that on faith. It counted subscribers on the live
graph: **truth 0, estimate 2** (commit `77da568`). The world launch
refuses to start an un-firewalled cell.

The consequence is the one that was wanted: `vda_orders.Progress` now
counts on the same estimate the adapter's ARRIVED reads — the "same
measurement made twice" invariant that D6 and D13 both turn on. Its cost
is named in the spec and still true: the key `gz_odom` now lies about
its source, and it gets renamed the day the fleet layer unfreezes.

### 1.4 The health chain — every gate quoted

Nothing in this cell is asserted; each stage prints what it measured and
refuses by name. From `run19-c9-session/START_f1.txt`:

```
  ekf: worst covariance 1.15 against a ceiling of 100
  /f1/amcl active
  /f1/velocity_smoother active
  seed: /f1/initialpose at map (-0.0793, -0.1458) yaw +0.00326
        = world (-17.00, 10.00) yaw 3.14159 through the committed
          registration
        registration residual rms 0.0291 m, MAX 0.1179 m - no figure at
        or below the MAX is a measurement of the localiser
  amcl: worst covariance 0.243 against a ceiling of 1
  amcl: answered 0.033 m from its seed, against a tolerance of 0.50 m
  /f1/navigate_to_pose answering, six lifecycle nodes active
  plan:   the planner PLANS. 2 m ahead of the seed, 29 poses in 0.0080 s
          NOTHING WAS COMMANDED: compute_path_to_pose is the PLANNER's
          action and never reaches the controller. The truck did not move.
```

Every gate held on every run of the campaign. Across the nine sessions
that kept a `START_f1.txt`, EKF worst covariance ran **1.03–1.22**
against a ceiling of 100, AMCL worst covariance **0.229–0.256** against
a ceiling of 1, and AMCL answered **0.033–0.048 m** from its seed
against a tolerance of 0.50 m.

The last gate is wave B5's `nav_plan_health.py`, and it exists because
"the action server answers" is not "the arm can plan". The registration
line is not decoration either: **MAX 0.1179 m** is the margin D6 is
built out of, and it is printed in the adapter's own boot banner:
`arrive_m 0.25 (+0.1179 m registration margin)`.

---

## 2. The contract, and what died

### 2.1 The `/auto` seam is byte-frozen

The fleet layer above the adapter — `vda_agent.py`, `vda_orders.py`,
`vda_messages.py`, `m6/fleet/*`, `cmd_mux.py`, `cmd_gate.py`, `hmi/*` —
was **not modified in G1**. It has no idea any of this changed. So the
adapter presents the same `/[vid]/auto/state` document, in the same
words, with the same rules about which word appears when.

`nav2_state.py` carries that grammar and is **pinned against `nav_core`
itself**: each refusal string is verified by driving a real
`nav_core.NavCore` into the refusal and comparing its `note`; the three
that live in the rclpy shell are pinned against `nav_node.py`'s source.
Run 19's very first state line is one of them, and it is the same line
run 15 and run 18 put on the wire two waves earlier:

```
14:14:22  IDLE  goal=None route_n=0 note='goal refused: unknown station ZZ'
```

The BLOCKED notes are the wire's only WHY, so each names its instrument.
Four of them were exercised in the field, verbatim:

| note | seen in |
|---|---|
| `blocked: no progress - best {m} m, {s} s without closing` | every session that failed — run12 (10.99, 20.67), run13 (3.48), run14 (0.23–0.24 ×12), run15 (4.40–14.34), run16 (4.26–5.54), run17-a (20.30 ×2, 20.32), run18 (15.68, 15.69 ×3) |
| `blocked: nav2 refused (error_code 0)` | run14 only, 5 times — §4.4 |
| `blocked: the granted polyline cannot be driven as a path` | run17-a (4), run17-b (4) — D14 |
| `goal refused: unknown station ZZ` | run15, run18, run19 |

Two deliberate deviations are recorded rather than hidden. `nav_node`
stops publishing `/auto/state` entirely on a stale pose; the adapter
keeps the 10 Hz stream with the note, because silence was the worse
behaviour and nothing downstream depends on it. And `AVOID`/`NUDGE` are
**reserved and never emitted** — nav2's costmap and the BT recoveries
replace m6.7's escalation, and `state_json` refuses to put either on the
wire even if a caller sets it by hand.

### 2.2 What died, and what stands in its place

| what | fate | what replaced it |
|---|---|---|
| `m6/ipc/nav_node.py` | retired as the motion engine | `nav2_adapter/nav2_adapter_node.py` — the one rclpy shell: subscriptions, action client, two timers |
| `m6/ipc/nav_core.py` | retired | `nav2_state.py` (the grammar + state machine, pinned to it), `nav2_legs.py` (the leg runner), `nav2_watch.py` (`ClosingWatch`, a port of `drive_goal`'s) |
| `m6/ipc/follower.py` | retired **as control** | Nav2's `controller_server`. `follower.sector_min` is kept as a **reporting import only**, so `/auto/state.guard_min` stays honest for the HMI |
| `m6/ipc/avoid.py` | retired | nav2 costmap + BT recoveries |
| m5v3 `cmd_vel_tricycle_core.twist_to_tricycle` | ported **as an import, not a copy** | `nav2_cmd.py` — one home for the tan/atan inverse kinematics and the yaw-rate-at-standstill refusal |
| m5v3 `cmd_vel_tricycle.py` (the shell) | **did not port** | it publishes gz actuator topics directly, bypassing mux/gate — the exact thing m6 forbids |
| m6 `cmd_mux`, `cmd_gate`, `forklift_io`, `sto_contactor` | stay, byte-untouched | PLC authority. `cmd_gate` keeps the last word on Motor, staleness and V_Limit |

The cost is stated in the spec and not softened: the dock aisle loses
its 0.7 m/s cruise, because Nav2's envelope is **0.300 m/s** both ways,
at the PLC creep ceiling. What that buys is that the latched-stop class
is structurally absent — and D4 is the wave that found out what happens
when a permission is allowed to *widen* it.

### 2.3 The modules

Eleven files under `m6_ver2/nav2_adapter/`, m5v3's idiom throughout —
pure core, thin shell, `--selftest`, named refusals, **no rclpy in any
core**: `nav2_legs`, `nav2_state`, `nav2_watch`, `nav2_cmd`, `nav2_pose`,
`scan_mask` (wave A's six, selftests 110/110 with mutation checks
proving the pins bite), then `nav2_envelope` (D4, wave C2), `nav2_path`
(§9, wave C8), `nav2_seed`, `_donors`, and the two shells
`nav2_adapter_node.py` and `scan_mask_node.py`. The whole tick is
drivable on a fake graph: preempt generations, cancel, SAFETY-STOP
holding the route, the arrival latch, the sign audit.

---

## 3. The defect ladder — sixteen classes, D1 to D16

Every row was found **on the floor**, on this rig, in the run directory
its last column names, and every row is closed by a test that fails
without its fix. Rows D1–D11 are read from the wave commit messages and
the module docstrings that quote them; D12 onward are read from the
session reports on disk.

| # | symptom, as measured | mechanism | fix | proven in |
|---|---|---|---|---|
| **D1** | `check_isolation` refused a perfectly good derivation with `the derivation says ''` | the `M6V2` marker export was spelled over `M6V2_DIR`; every assignment above it survived, because those resolve before it runs. The only casualty was the one **call-time** expansion — `derived_get()` read `1/vehicles/f1/config.yaml` | the marker is a scalar with its own name; the module path is untouched | `run1-adapter-abort` |
| **D2** | the adapter process aborted inside rosidl (`geometry_msgs__msg__vector3__convert_from_py`, `PyFloat_Check`) on the first sub-creep twist of the first leg — i.e. on every standing start | `nav2_cmd` answers `None` for "hold the steer axis". The donor holds that axis by *not publishing* a Float64 terminal, which a plant with two terminals can do; this wire carries traction and steer in one Twist, and a stopped stream is `cmd_gate`'s staleness demand | the shell **holds the last angle it sent**. Zero would centre the wheel — a motion nobody commanded, and inside a spur a motion into the rack | `run1-adapter-abort` |
| **D3** | the order died 1.49 m from the spur foot, on the first run that got that far | nav2 1.3.12 **refuses a preemption that changes the behaviour tree**, in one long log line; it then aborts the *new* goal with `error_code 0` and keeps the old one running — and the adapter, correctly by its own rules, read that abort as a nav2 failure | the tree decides the door: same tree preempts, different tree cancels and sends on the server's own stale-generation report. Since §4 that is the only boundary nav2 refuses | `run2-preempt-refused` |
| **D4** | the truck entered the S1 spur at 700 mm/s against a 300 mm/s permission; the F-program's speed monitor latched and Motor went False **3.31 s** after the goal was sent | `setSpeedLimit` **replaces** a controller's maximum; it does not intersect with it. V_Limit 1500 went out as `speed_limit 1.5` onto a 0.300 m/s controller, and MPPI scaled `vx_max`, `vx_min` and `wz_max` by five | published limit is `min(permission, nav2's configured envelope)`; the envelope has **one home**, the derived `nav2.yaml`; the shaft is capped at `min(coverage, envelope, permission)`. **28 permission transitions in 23 minutes, wheel already under every one, zero Motor-False** | `run3-speed-limit-latch` |
| **D5** | the truck drove a 180° turn inside a 5.75 m dead-end spur — swung to (-11.32, 7.87) at yaw 2.51, cusped, reversed north-west out to (-13.59, 11.45), watchdog at 30 s; a repeat put it at (-10.42, 12.36) and latched Motor False | the spur exit was classified by **ordinal**. The post-pick route starts with the truck's own 0.245 m parking error, so leg 1 *was* the parking error and the bay-to-mouth leg was a TRANSIT | class is decided by **where a leg starts**, not by its position in the list; a spur exit leaves on the bay's own heading. A leg that *ends* on a station is not leaving one, whatever it started on | `run4-spur-exit-turnaround` |
| **D6** | a 0.2502 m arrival called "arrived short" | the adapter reads the estimate through the registration, nav2 reads AMCL's map pose directly — a 0.25 m boundary both check is a boundary they can **straddle** | the margin is the committed registration's own **MAX residual, 0.1179 m** — a measurement the boot line prints, not a tolerance. A transform that states no residual is worth zero here and says so | `run4-spur-exit-turnaround` |
| **D7** | out of S1 at the mouth (-13.0, 10.0) on -1.75, handed goal yaw 0.0 for the eastbound ring leg. Smac planned the turnaround — (-14.73, 8.65), (-12.13, 11.53), (-12.51, 9.63) — **six BLOCKEDs in one order, not one of them a floor that was not clear** | "along the last segment" is **one** heading for a vehicle that drives both ways. This model's forks are at body -x, so a travel-direction goal yaw means *counterweight first* | TRANSIT goal yaw is the travel direction **or its π-flip, whichever is the smaller rotation** from the truck's current yaw. STATION and SPUR_EXIT keep their bay heading — a station heading is not a preference, it is the pose the bay admits | `run5-aisle-turn-limit-cycle` → AMENDMENTS §3 |
| **D8** | the five yaws the truck actually stood at when a ring leg was dispatched out of the S1 mouth: **-1.550, -1.474, -1.565, -1.581, -1.574** against a bay heading of -1.5708. The one **0.021 rad** on the wrong side of π/2 was handed the travel direction, left the corridor to (-13.05, 11.35) and died on `best 13.06 m, 30 s without closing` | π/2 is not a corner case on a right-angled floor — it is **every junction**, and what decided it was the third decimal place of the localiser | the tie is a **band** (`TIE_BAND_RAD` = `COLLINEAR_RAD` = 15°, the tolerance this file already grants a parking error) and inside it the **flip wins** — not by coin toss: it is the sense the truck already drives, and the sense nav2's own direction-hold node will defend | `run6-d7-tie-band-and-lost-goal` |
| **D9** | `Begin navigating … to (-0.08, -0.15)` / `Received goal preemption request` / `Goal succeeded` **19 ms later, 4 m short**. The truck stood on its spawn node until the watchdog called it — twice, on 4 m of empty aisle | a 0.047 m leg is inside the 0.60 m goal checker **before it is sent**, so the tree returned SUCCESS against the label of the goal that had just displaced it. Two `NavigateToPose` goals at a single-goal server inside 41 ms | a leg born inside `PREEMPT_AT_M` is not a leg: short non-final runs **fold forward** (forward, so the goal stays on the ring leg's heading and not the parking error's), and a non-final SUCCEEDED advances the queue instead of standing on it | `run6-d7-tie-band-and-lost-goal` |
| **D10** | handed a quarter-turn goal at 0.30 m/s at the bay mouth, ground truth ran (-13.35, 9.12) → (-12.60, 10.00) → (-11.83, 10.75) → (-10.50, 11.80) → (-8.58, 12.36): a **2.36 m** arc into the rack line, left PF demanded, Motor latched False. The belief was not the defect — the estimate held median 0.102, p95 0.112, max 0.187 m all session | both doors hand over at P **with the truck moving**. The cancel-door fix failed identically: `Client requested to cancel` at 1788327959.428, `Begin navigating from (-4.13, 1.31)` at .439 — **eleven milliseconds**, and the truck coasted through at 0.273 m/s into the same arc to the metre | SPUR_EXIT **runs to its own goal**, which is the only thing that lets RPP's `approach_velocity_scaling_dist` (1.0 m) bring it down. The next leg then starts from a standstill (0.075 m/s measured), where the direction hold accepts every plan | `run8-d10-undock-preempt-excursion`, `run9-d10-cancel-is-not-a-stop` |
| **D11** | **4/4 across BOTH controllers**: +2.40…2.52 m off the ring band at the mouth turn. Run 10's is the **+2.43 m** that every later session prints as its comparison constant | a quarter-turn goal 13 m east handed at the mouth, **amplified** by `DirectionStablePath` defending the mouth-built plan while the truck drove off it — eleven fresh plans refused, `12.59 m of the accepted plan left … keeping the accepted plan` | §5: strip DSP from the derived rpp/station trees — the seat belt's MPPI was gone and its only measured act on RPP was amplification | `run10-d11-rpp-cannot-hold-the-mouth-turn` → §4.2 |
| **D12** | from a standstill at the mouth, handed a goal 13 m east: out to (-10.63, 10.92), back to (-10.75, 9.76), twelve seconds of dither round (-10.85, 9.5), west to (-11.52, 9.77), away on the same arc — `best 10.99 m, 30 s without closing`. Same shape at a ring corner 110 s later, `best 20.67 m`, truth (-19.09, 11.20). **Not** D11 (worst northward over that stretch +0.927 m) and **not** a creep (0 plateaus, speeds 0.02–0.30 m/s) | with nothing holding the mouth-built plan, Smac **re-decides the sense every replan**: at a quarter turn both senses reach a distant goal and neither has an advantage the other lacks | a short on-ring **alignment leg** first — reachable one way, awkward the other — so the sense is decided by geometry and not by the third decimal place of a replan, and the long goal is then sent to a truck already pointing along it | `run12-c5-session-a` → `run15-c6-session`: `alignment legs driven to completion: 13/13`, thirteen followed by the leg they exist to set up |
| **D13** | the bay-arrival livelock: nav2 finishes at 0.247, vda's `Progress` reads ≥ 0.25, the two-fact rule never closes, the route re-issues — **14 identical dispatches**, the route point frozen bit-for-bit, `truck_yaw` creeping -1.757 → -1.725 while the truck never moves | nav2's station checker (0.25) and the fleet's arrival radius (0.25) are **the same number with zero margin**, sampled by two consumers at two instants. A re-sent goal cannot move a truck already inside the checker; the goal must sit deeper | §6: the STATION goal is the station point advanced `ARRIVE_BIAS_M` = 0.10 m along the bay's own declared approach heading — the same number `leg_yaw` sends as the goal's orientation — **bounded by the paint**. `bay_clearance_m` ray-casts the SDF: S1 **18.250 m**, S4 **18.250 m**, the annex's four **3.000 m**, against `LEAD_OVERHANG_M` **1.400 m**. A bay that cannot pay is refused at leg build, by name, with its arithmetic | `run13-c5-session-b` → `run15-c6-session`: `every bay goal exactly 0.10 m past: True`, `every OTHER leg sent its own end: 42/42`, `ARRIVEDs under 1 s after their own dispatch: 0` (run14: **100**) |
| **D14** | the builder **refused four whole orders by name** in one session and four more in the next: `leg 1/2 ring chain NOT SENT: the corners at (-9.9119, 10.2109) and (-10.0, 10.0) claim 0.832 m of tangent between them at radius 1.250 m and the segment joining them is only 0.229 m long`, and — the second measurement — `a turn of 3.125 rad is a reversal, not a corner: no arc of any radius rounds it` | `route.plan_route` prepends the truck's pose and keeps the entry node, so a truck parked 0.229 m off a ring node is handed a **67° corner with 0.229 m of run-in**, which `_merge_short` then folds *inside* a chunk. Parked 0.247 m *past* its bay point, the same prepend produces a π stub in front of a spur | the refusal was right and the input was wrong: a **head stub too short to carry its own tangent is dropped**, and a reversal at the head is a stub by definition. Only from the head — a mid-polyline stub is still refused, because there the vertex behind it *is* granted and dropping it would move the corridor | `run17-c8-session-a` (7 BLOCKED, 7 cancelOrders), `run17-c8-session-b` (95 route dispatches in an eight-minute requeue loop) |
| **D15** | the truck stopped at the mouth on the bay heading and was handed a path running east: a **circle at the steer stop, 0.79 m north of the ring centreline**, three orders lost on `blocked: no progress - best 20.30 m` (twice) and `20.32 m` | RPP is a pure pursuit. Curvature is `2·sin(α)/L`: at a quarter turn and the configured 0.70–0.95 m lookahead that is **2.1–2.9 1/m**, a radius of 0.35–0.48 m against this truck's measured minimum of **1.25 m**. Not a plan and not a tuning — what a carrot across the body axis costs | the chain **starts in the bay**: the mouth becomes an ordinary rounded corner with 1.25 m of spur behind it and 1.25 m of ring ahead, and the truck leaves dead astern along its own axis with the carrot straight in front of its forks. D10 is satisfied, not overturned — there is no goal at the mouth any more | `run17-c8-session-a` → `run18-c8-session-c` |
| **D16** | the watchdog cancelled **four consecutive orders** — `best 15.69 m, 30 s without closing` three times and `15.68 m` once — on a truck driving perfectly at 0.30 m/s, with the fleet's own node counter advancing **10 → 9 → 8** on the wire underneath, `driving=True`, `errors=[]`, until the cancel wrote `errors=['pathBlocked']` | §9 moved ring legs onto `/follow_path` and left `ClosingWatch` "unchanged" — and unchanged meant still fed the **straight line** from the belief to the leg's end. A chain turns away from its own end by construction: the S1 → S4 grant leaves the bay *northward* up the spur while S4's spur foot is fifteen metres *south*, so the straight line grew **15.69 → 20.93 m** over thirty seconds | the **rule** was right and stays pinned against `drive_goal`'s sample for sample; the **ruler** was wrong for this leg class. Every leg is dispatched with the metric it closes on — `straight_metric(leg.end)` for a manoeuvre, `chain_metric(built.poses)` for a chain. Same thirty seconds, new ruler: **43.90 → 36.63 m, monotone** | `run18-c8-session-c` → `run19-c9-session` |

Three properties of this table are worth stating on their own.

**Nothing is tuned around.** D8's band is `COLLINEAR_RAD`, the tolerance
the file already grants a parking error. D13's bias is bounded by a ray
cast into the SDF, and a station that cannot pay the clearance is
refused rather than shrunk to fit — the tightest bay on this floor
leaves 1.600 m against 0.100 asked. `ALIGN_M` is a printed sum of three
measurements (quarter arc 1.9635 + P 1.50 + straighten 1.05 = **4.5135**,
with `SPLIT_ABOVE_M` **6.0135** following the sum), not a knob.

**Refusals are the instrument, not the failure.** D14's orders died on a
refusal that was *correct*; the wave's work was proving the input wrong.
That is the same shape as `EVIDENCE_FILM.md`'s four takes — every defect
found by a refusal or a sampled measurement, none by watching and hoping.

**The numbering has one seam.** Wave C8's commit message named the
watchdog class **D15b**, as the third class of that wave. The tree
carries it as **D16**, in `nav2_watch.py`, `nav2_path.py`,
`nav2_adapter_node.py` and AMENDMENTS §10; `D15b` appears nowhere in the
repository. The tree's name is the one this file uses.

---

## 4. The three architecture rulings, and the two they overturned

### 4.1 §4 — TRANSIT legs drive RPP (AMR-DEC-005 extended)

D7 made every transit leg forks-first, which is nav2-**reverse** — the
reversal-heavy class `AMR-DEC-005` had already moved off MPPI on the
m5v3 track. Run-7 then measured `EVIDENCE_STALL`'s creep **verbatim** on
those legs:

| | run-7, MPPI transit | after §4 |
|---|---|---|
| creep plateaus | **4**, means **0.0816–0.0905 m/s** — inside `EVIDENCE_STALL`'s own **0.0777–0.0901** band | **0**, in every session from run 12 to run 19 |
| BLOCKEDs | **6 of 10** | 0 in all three C4 runs |
| DSP | holding flip plans; orbit at the leg end | — |

The counter-evidence was weighed in the open rather than dropped: m5v3
measured its clean spawn straight at MPPI 8/8 against RPP 7/8. The
measured incidence *here* was 6/10 against ~1/8, so the row moved — and
RPP's unrecovered lateral-excursion class stays **named**, with the
closing watchdog and the fleet's own requeue as its net. MPPI remains
configured on `FollowPath`; no leg class names it.

Every session from run 12 onward prints the same line under its creep
section: `plateaus: 0 (run-7 comparison: 4, means 0.0816-0.0905)`. Eight
sessions, zero plateaus.

### 4.2 §5 — the derived RPP/station trees drop `DirectionStablePath`

DEC-006 kept DSP as "the seat belt on the MPPI legs". §4 removed the
last MPPI leg, so the guard's **object was gone** — and runs 8/9/10 had
already measured its only remaining effect on an RPP leg: eleven
direction-holds defending a stale mouth-built plan across the D11 arc
while the truck drifted 2.4 m off it.

| | run 10 (before) | run 12 | run 13 | run 19 |
|---|---|---|---|---|
| DSP hold lines | **29, eleven of them holds** | **0** | **0** | **0** |
| worst northward of `y = 10` | **+2.43 m** | +1.441 m session; **+0.927 m** over the D12 mouth-arc stretch | **+0.008 m** | **+0.295 m** |

Two honesty notes on that row. Run 10 kept no reduction, so `+2.43`
survives only as the comparison literal every later `READING.txt`
prints. And run 12's *session* worst is +1.441 m, not the +0.93 the wave
commit headlines — the +0.927 is the worst over the D12 dither stretch,
which is the figure `nav2_legs.py`'s D12 docstring states and the one the
comparison is against. Both are in this table because the strip is what
the smaller number measures and D12 is what the larger one is.

The strip is a **counted, residue-reversible transform** that also
rewrites the header sentence it makes false; the donor trees and the
unnamed MPPI tree keep their decorator.

**The field demand at the top of the arc was arithmetic, not a sensor
fault.** The numbers are all on disk and the subtraction is one line.
The ring centreline is `y = 10.000` and WallNorth's inner face is
`y = 14.000` (`nav2_legs.bay_clearance_m`). `stations.py` budgets
`ABEAM 1.66 m = 1.00 (case-1 protective field) + 0.20 (hysteresis) +
0.46 (lateral scanner mount offset)`. Run 10's +2.43 m excursion puts
the truck at `y ≈ 12.43`, **1.570 m** from that face — 0.090 m inside a
1.66 m budget. The C4 wave's "field demand at y = 12.4" is the same
subtraction: 1.600 m against 1.66 m. Nothing was wrong with the scanner;
the corridor breach had already spent the standoff.

### 4.3 §9 — ring chains drive their own polyline; Smac plans only manoeuvres

Four waves measured one family from one source: **Smac re-deciding
degenerate ring geometry every replan**. The traffic ledger grants a
*polyline*; freespace planning on it was always a translation error.

So the adapter builds the chain's `Path` itself — granted polyline,
corners rounded at `MIN_TURN_RADIUS_M` = 1.25 m, densified at ~0.10 m,
orientations laid by the D7 rule **resolved once per chain at dispatch**
— and sends it on `/fN/follow_path` with all three ids named. The
station spur keeps `NavigateToPose` and keeps Smac, because entering a
4.00 m bay off the ring band is the manoeuvre a freespace planner is
*for*, and it is the only leg with the 0.25 m checker on it.

| | run 15 | run 16 | run 18 (session c) | run 19 |
|---|---|---|---|---|
| Smac refusals, over free paint | **13** | **8** | **0** | **0** |
| `planner_server` CPU mean / p95 / max | 16.5 / 21.7 / **92.3** | 18.0 / **41.8** / **108.2** | 14.2 / 14.8 / **17.0** | 17.2 / 18.7 / 20.7 |
| preemption requests / rejections | — | **9 / 0** | 0 / 0 | 0 / 0 |
| DSP holds · creep plateaus | 0 · 0 | 0 · 0 | 0 · 0 | 0 · 0 |
| worst northward of `y = 10` | +1.446 m | **+1.738 m** | **+0.353 m** | **+0.295 m** |
| worst perpendicular from the route | 2.400 m | 1.738 m | 0.578 m | 1.703 m (§6) |
| RTF mean / p95 | 0.888 / 1.001 | 0.878 / 1.001 | 0.890 / 1.001 | 0.839 / 1.176 |
| estimate `err_m` n / mean / p95 / max | 10258 / 0.113 / 0.197 / 0.436 | 4553 / 0.080 / 0.179 / 0.244 | 3287 / **0.104 / 0.181 / 0.249** | 4007 / 0.079 / 0.188 / 0.359 |

The bound the corridor is checked against is arithmetic, not a
tolerance, and the addendum prints it before it prints an offset: a
corner of turn `t` rounded at radius `r` cuts a sagitta of
`r·(1 − cos(t/2))`, which at a right angle and r = 1.25 m is
**0.366 m**. Every run-19 chain offset is inside it. (The C8 commit
quotes 0.338 m of offset for session c; that figure came from an ad-hoc
instrument that was not kept, and the session's own reduction carries
0.578 m perpendicular / +0.353 m northward. The archive's numbers are
the ones above.)

**What RPP actually reads** was taken out of its own source rather than
assumed (1.3.12, `regulated_pure_pursuit_controller.cpp:225–229`): the
driving sense is `carrot_pose.pose.position.x >= 0.0` in the **robot**
frame, and the path's pose orientations are read in exactly one branch —
`findVelocitySignChange`'s duplicate-position test (`:547–556`). So the
orientations this adapter lays are a **declaration**; what is a
**command** is the absence of a cusp, because one sign change truncates
the lookahead and a 40 m path is then driven at a 0 m carrot. `cusp_at()`
is that test in python and the suite runs it over every route this floor
can plan. Run 19: **0 sign flips in 45 471 commands.**

One caveat is stated rather than assumed: the nearest-point projection
`project_onto` — which now answers all three questions this adapter asks
of a corridor (how far off it, where along it, where to trim it) — needs
a corridor that does not come back near itself, and the suite asserts
that over every ring chain `route.py` plans on this floor rather than
trusting the sentence.

### 4.4 The first overturn — §6's implied fix, built, flown, refused (§7)

§6 assumed nav2's station checker was what stopped the truck at the bay.
It is not: the adapter's own 20 Hz latch fires at `arrive_m` of the
station point, and Decision 3 publishes zeros on `/auto/cmd_vel` outside
EN-ROUTE. Letting the bay's goal outlive the latch was **built and
flown** (`run14-c6-latch-cancel-experiment`) and it did two things.

**It moved the truck nowhere.** The session's rest table has 101 rows
and the first two are the whole argument:

```
09:53:49  at the latch est 0.2488 truth 0.3011 (v 0.1159)
                                -> at rest est 0.2480 truth 0.2988
09:53:52  at the latch est 0.2397 truth 0.2971 (v 0.0000)
                                -> at rest est 0.2397 truth 0.2971
  run-13 comparison (goal AT the point): est 0.2462 truth 0.2719.
```

`v 0.1159 → 0.0000` inside one 0.2 s sample, at estimate 0.2480 m
against run 13's *cancelled* 0.2462 m. The same stop to two millimetres.
The remaining 99 rows are all `v 0.0000`.

**It killed the next order.** Three seconds later the spur exit went out
on the RPP tree with the station tree still on the server, nav2 refused
the preemption, and the leg-2 order died 200 ms after issue. That
refusal has its own note and this is the only session in the campaign
that carries it — **five times**:

```
09:53:52 blocked: nav2 refused (error_code 0)  truth [-13.0601, 4.5420, -1.5588]
09:55:57 blocked: nav2 refused (error_code 0)  truth [-13.0600, 4.5401, -1.5588]
09:57:58 blocked: nav2 refused (error_code 0)  truth [-13.0600, 4.5400, -1.5593]
09:59:58 blocked: nav2 refused (error_code 0)  truth [-13.0600, 4.5400, -1.5593]
10:02:04 blocked: nav2 refused (error_code 0)  truth [-13.0600, 4.5400, -1.5593]
```

with twelve `blocked: no progress - best 0.23–0.24 m, 31–32 s without
closing` between them — a truck standing still, 0.24 m from its goal,
being told it was not closing. The livelock instrument counted the rest:
**113** routes ending at S1, **100** ARRIVEDs landing under one second
after their own dispatch, both-facts-in-one-tick **99/101**.

So the cancel stays; `_on_result` now reads a latched ARRIVED **before**
it reads the status, so no late error code can un-latch an arrival the
fleet has already been told about. And §6's bias is narrowed to what the
contract lets it be — a margin against nav2's own checker (D6's class),
not a change in where the truck comes to rest. Moving the stopping point
is a Decision 3 question and §7 explicitly does **not** rule on it.

Run 15, the next session, is the same instrument with the cancel back:
**11** routes ending at S1, **0** sub-second ARRIVEDs, arrivals
both-facts-one-tick **4/4**, and four handovers at the latch at
v = 0.1146 / 0.0694 / 0.1144 / 0.0026 m/s.

### 4.5 The second overturn — §5 × §8 measured irreconcilable, dissolved by §9

Run 16 measured both halves of §8 and the file keeps both, beside the
constant, un-tuned.

**What it delivered.** Of eight alignment legs, **5 of 5** transits
opened by one were dispatched **with the truck moving** — the addendum
prints each pair —

```
align 2/8 end=(-17.51, 10.00) dispatched at v=-0.191
                    ->  transit 3/8 dispatched at v=-0.301  (IN MOTION)
align 4/8 end=(  0.00,  5.49) dispatched at v=-0.304
                    ->  transit 5/8 dispatched at v=-0.311  (IN MOTION)
transits handed over IN MOTION off an alignment leg: 5/5
standing starts handed a long transit goal: 0
```

— handover velocities spanning **-0.269 to -0.311 m/s**, two of them off
a straight ring run at turn **-0.042** and **-0.084 rad** against run
15's standing-start 0.78 to 1.56. **9** preemption requests, **none**
rejected.

**What it cost.** The same addendum prints the other three: `align 2/8
end=(-8.49, 10.00) -> NOT followed by its own next leg`, three times.
**3 of 8 alignment legs never closed.** All three at a right angle, all
with `best` equal to `ALIGN_M` itself — the session's four BLOCKEDs are
at **4.55, 4.73, 4.26** and 5.54 m against `ALIGN_M` 4.5135 — and the
body twist flipped sign **14 times in 30 s** on the first and 6 on the
second. Not a planner refusal (Smac answered) and not a creep (0
plateaus): the **two-sense tie** the file already names at
`FLIP_ABOVE_RAD`, re-opened because §8's longer goal is now far enough
that both senses cost the same, with nothing holding a choice across
replans since §5 took DSP away.

`nav2_legs.py` states the meeting rather than tuning around it:

> AMENDMENTS 8 requires the handover to sit past the arc, which requires
> `ALIGN_M >= arc + P + straighten`; AMENDMENTS 5 removed the node that
> held a driving sense across replans. **Nothing inside this file can
> satisfy both.**

§9 dissolved it by deleting the disputed object: **there is no goal at a
turn any more.** The ring is one `FollowPath`, the sense is decided once
at dispatch, and `ALIGN` retires with its reason recorded — the function
is kept, and kept tested, as the record of what two waves measured. §5
stands (no DSP anywhere), §8's in-motion property is inherited trivially
(one Path spans the chain), and D12's mechanism is still true; it just
has nothing left to be true about.

---

## 5. The bar run — `run19-c9-session`, 2026-09-02

One truck. Two orders from the fleet manager, back to back, `S1 → S4`
each, submitted through `fleet_cli.py`. No operator intervention.

### 5.1 Both orders, end to end

`fleet.log` — the fleet's own words:

```
14:14:40,677  queued ft-8415d232: S1 -> S4
14:14:40,678  assigned ft-8415d232 to f1 (nearest idle to S1: f1 9.75 m)
14:15:27,228  f1 arrived at S1 with ft-c2b4efb5 - pick running
14:15:30,240  dwell done - f1 drives ft-8415d232 to S4 as ft-7a26dc21
14:19:10,762  f1 completed ft-8415d232 at S4
14:19:32,321  queued ft-fb6d6b16: S1 -> S4
14:19:32,322  assigned ft-fb6d6b16 to f1 (nearest idle to S1: f1 51.26 m)
14:23:09,414  f1 arrived at S1 with ft-04c2129a - pick running
14:23:12,426  dwell done - f1 drives ft-fb6d6b16 to S4 as ft-3c2407fd
14:26:47,413  f1 completed ft-fb6d6b16 at S4
```

**270.1 s** and **435.1 s**, `queue 0` throughout, `done=2` at the end.
The second is longer for a reason the log itself gives: the assignment
distance to S1 was **51.26 m**, not 9.75 m — the truck started that order
from S4, where the first one left it, and not from the spawn. That is
the property the wave was for. A cycle that only works from the spawn
pose is a demo.

On the wire, `/f1/auto/state` carried four EN-ROUTE edges and four
ARRIVED edges with an **empty note on every one**, and no BLOCKED:

| order | route label | points | EN-ROUTE (sim s) | ARRIVED (sim s) |
|---|---|---|---|---|
| 1 leg 1 | `ft-c2b4efb5` | 3 | 251.40 | 292.80 |
| 1 leg 2 | `ft-7a26dc21` | 12 | 295.61 | 491.70 |
| 2 leg 1 | `ft-04c2129a` | 11 | 514.40 | 713.80 |
| 2 leg 2 | `ft-3c2407fd` | 12 | 716.70 | 910.90 |

The vehicle's own VDA node counter ran clean under all four — 11 → 10 →
… → 0, `driving=True`, `errors=[]` on every row, `lastNode` landing on
`S1` and `S4`. Two waves earlier that same counter was running 10 → 9 →
8 underneath a watchdog calling the truck stalled (D16).

### 5.2 The chains, with `remain=`

Four ring chains dispatched, each with the ruler D16 installed:

| chain | granted | ends | `len` | `remain=` at dispatch | poses | corners | dropped | samples | first → last | worst rise |
|---|---|---|---|---|---|---|---|---|---|---|
| `ft-c2b4efb5` | 2 pts | (-13.00, 10.00) | 4.00 | **4.00** | 41 | 0 | 0 | 3 | 4.00 → 1.58 m | **0.000** |
| `ft-7a26dc21` | 11 pts | (-7.00, -10.00) | 44.14 | **43.89** | 444 | 3 | 1 | 35 | 43.89 → 1.63 m | **0.000** |
| `ft-04c2129a` | 10 pts | (-13.00, 10.00) | 43.91 | **43.91** | 443 | 3 | 0 | 35 | 43.91 → 1.08 m | **0.000** |
| `ft-3c2407fd` | 11 pts | (-7.00, -10.00) | 44.14 | **43.89** | 444 | 3 | 1 | 34 | 43.89 → 1.79 m | **0.000** |

`len` is the sum of the driven primitives and `remain=` the arclength
left at dispatch; they differ by what a rounded corner cuts, which is
why both are printed. `dropped=1` on the two chains out of the S1 bay is
D14 doing its job **silently and on the record**: a chain that started
one vertex in is a chain whose first metre nobody granted, and the field
is on `ChainPath` for exactly that reason.

The four station-spur legs keep the ordinary straight ruler, and the
`v=` at dispatch is §8's in-motion property inherited through §9:

| dispatched | goal | `goal_yaw` | `truck_yaw` | `v` | `turn` | samples | first → last | worst rise |
|---|---|---|---|---|---|---|---|---|
| 14:14:54 → S1 | (-13.00, 4.15) | -1.571 | +3.127 | **-0.187** | +1.585 | 7 | 5.73 → 0.52 m | 0.000 |
| 14:18:25 → S4 | (-7.00, -4.15) | +1.571 | -0.002 | **-0.192** | +1.573 | 9 | 5.77 → 0.47 m | 0.000 |
| 14:22:25 → S1 | (-13.00, 4.15) | -1.571 | -3.132 | **-0.181** | +1.561 | 9 | 5.75 → 0.87 m | 0.000 |
| 14:26:03 → S4 | (-7.00, -4.15) | +1.571 | +0.012 | **-0.180** | +1.559 | 9 | 5.74 → 0.32 m | **0.020** |

Every bay goal is `(x, ±4.15)` against an end of `(x, ±4.25)` — D13's
0.10 m aim-past, on the wire, four times out of four, with `goal_yaw`
and the goal's own displacement axis agreeing by construction. The one
0.020 m rise is on a straight-line ruler over 5.74 m of spur; it is a
truck settling into a bay, and it is printed because `worst rise` is
printed unconditionally.

### 5.3 The corridor, chain by chain

The addendum checks each chain against **its own grant**, not against a
route the truck was never given, and prints the bound before the
measurement:

> the arc a rounded corner cuts is the bound: `r*(1-cos(t/2))`
> = **0.366 m** at a right angle and r = 1.25 m

| chain | poses of truth | worst offset from the grant | worst northward of `y = 10.0` |
|---|---|---|---|
| `ft-c2b4efb5` | 64 | 0.260 m | +0.243 m |
| `ft-7a26dc21` | 790 | 0.273 m | +0.273 m |
| `ft-04c2129a` | 789 | **0.330 m** | **+0.295 m** |
| `ft-3c2407fd` | 788 | 0.265 m | +0.261 m |

against run-10's **+2.43 m**. And zero cusps: 914 / 11 566 / 11 543 /
11 448 commands per chain, **0 commanded traction sign flips in 45 471**,
where run 16 carried 14 in 30 s.

### 5.4 The PLC, and the one `/speed_limit` edge

| clock | sim s | V_Limit | case | Motor | where |
|---|---|---|---|---|---|
| 14:14:21 | 0.00 | 1500 | 1 | True | boot |
| 14:15:15 | 282.10 | **300** | 1 | True | warning field, S1 spur |
| 14:15:43 | 307.71 | 1500 | 1 | True | out of the spur |
| 14:18:34 | 461.69 | **300** | 1 | True | S4 spur |
| 14:19:46 | 527.10 | 1500 | 1 | True | out |
| 14:22:57 | 702.65 | **300** | 1 | True | S1 spur |
| 14:23:26 | 729.20 | 1500 | 1 | True | out |
| 14:26:11 | 882.22 | **300** | 1 | True | S4 spur |

**Motor-False edges: 0.** `estop_healthy` True and `case=1` on every
row. **PF demand edges: 0** — the protective fields never demanded, only
the warning fields, which is the design.

nav2's `/speed_limit` shows exactly **one** edge all session
(`speed_limit=0.3 percentage=False`, 14:15:15) and that is D4's fix
looking the way it should. The published limit is
`min(permission, envelope)`, and the derived controller's envelope is
**0.300 m/s** — the adapter's own boot banner prints
`nav2 envelope 0.300 m/s`. So 1500 mm/s and 300 mm/s both land on 0.300
and nav2 sees one value from first publication onward. A permission is a
permission to go slower. Before D4, `1500` went through as `1.5` and the
truck entered the spur at 700 mm/s.

Every session in the campaign shows exactly this: one `/speed_limit`
edge, always `0.3`.

### 5.5 Rig cost

```
RTF   n=8565  min 0.0555  max 2.051  mean 0.8394  p95 1.1756
CPU (% of one core, /proc deltas, n=173 each)
  adapter            min 40.4  max  60.0  mean  50.2  p95  56.6
  bt_navigator       min  9.7  max  21.0  mean  13.1  p95  18.9
  controller_server  min 12.6  max  17.9  mean  15.7  p95  17.5
  gz_server          min 133.3 max 182.6  mean 163.7  p95 175.4
  planner_server     min 14.6  max  20.7  mean  17.2  p95  18.7
```

Wave C1's one-truck RTF baseline was median 0.9998, mean 0.88, before
any chain building. Runs 12 through 18 held mean 0.872–0.893 with p95
pinned at 1.001. Run 19's mean of **0.839** and p95 of **1.176** is the
first session to move off that plateau in both directions at once, and
its adapter and `gz_server` means are both above every earlier
session's — §6 says what is and is not known about why.

---

## 6. Residuals, by name

- **Four trucks are not measured, and the numbers say why it matters.**
  The adapter costs **~50 % of one core per truck** in run 19 (mean
  50.2, max 60.0; runs 12–18 sat at 41–45) and `gz_server` already sits
  at **163.7 % mean / 182.6 % max** with **one** truck in the world.
  G1 built for four and drove one. The RTF measurement Decision 2 names
  as the arbiter of the controller mapping has therefore not been taken
  at fleet scale.
- **Run 19's `gz_server` ran 27 points above every earlier session and
  nothing here explains it.** Runs 12–18 all measured `gz_server` mean
  133.7–136.7 %; run 19 measured 163.7 %. The chain builder is python in
  the adapter and cannot touch the physics server. It is unexplained,
  it is the same session every headline number in this file comes from,
  and it is written down rather than smoothed.
- **S1 → S4 is the only field-driven pair.** Across all nineteen runs
  the wire carries `lastNode=S1` 303 times and `lastNode=S4` four times,
  and no other station — and every session before run 19 prints
  `within 0.60 m of S4 (-7.0, -4.25): err_m None`, with run 16's
  reduction spelling out why: *"no sample: the truck never came within
  0.60 m of S4 this session."* The floor has **twelve** stations,
  including four annex bays whose clearance is 3.000 m against S1/S4's
  18.250 — the tightest geometry `bay_clearance_m` guards is the
  geometry that has never been driven. The suite plans every route
  `route.py` can build on this floor; the *truck* has driven one pair.
- **The chain watchdog has never fired a true positive.** D16 replaced
  the ruler and run 19 measured `worst rise 0.000 m` on all four chains
  — which is the fix working, and also means the new `chain_metric` path
  into BLOCKED has never been exercised by a genuinely stuck truck in
  the field. Its one stated caveat — nearest-point projection needs a
  corridor that does not come back near itself — is asserted by the
  suite over every ring chain `route.py` plans on this floor, and by the
  suite only.
- **The F-PLC is `--virtual`.** PLCSIM Advanced is expired; every Motor,
  V_Limit and case number in this file comes from the virtual model on
  the Windows side. This campaign did not re-measure it against the real
  PLCSIM.
- **A 1.703 m swing on the bay turn.** Run 19's worst perpendicular
  offset from the *published route* is 1.703 m, at truth
  `(-5.2798, -8.2968)` at 14:18:48 — which falls **outside all four
  chain windows**, on a station-spur leg. The chains hold 0.330 m; the
  Smac manoeuvre into the bay swings. It cost nothing here (no PF
  demand, no Motor-False) and nothing in this campaign bounds it.
- **`station_approach` is inherited, not re-argued.** m5v3's
  `EVIDENCE_STALL.md` §8.2 left that class on MPPI deliberately, so as
  not to delete measured evidence. m6v2's station spur runs the RPP tree
  with the 0.25 m stateful checker; the m5v3 residual is not discharged
  by that and is carried forward as it stands.
- **The deploy discipline is deferred, and `m6v2.sh` says so in its own
  header.** The vehicle children run from `m6/` source, not from
  `m6/deploy`, because the vehicle set is still moving under the
  adapter — freezing a shape that is not yet a shape would put a
  re-freeze in every debug cycle that learned nothing from it. m6's
  rule, *vehicle code changes and `m6.sh deploy` is mandatory*, returns
  the day it stabilises.
- **The retired modules still carry their tests.** `m6/` is
  byte-untouched by rule, so `test_nav_node.py`,
  `test_nav_core_escalation.py`, `test_follower.py` and `test_avoid.py`
  are green tests of code no longer in the motion path. They are the
  record `nav2_state.py`'s grammar is pinned against and must not be
  deleted before that pin moves.
- **Three wave-commit figures are not reproducible from the archives
  they name**, and this file used the archive instead in every case:
  the C8 commit's `0.338 m` of corridor offset for session c (the
  session's own reduction carries 0.578 m perpendicular, +0.353 m
  northward); the C8 commit's `|wz| under 0.011 / 0.22` on the spur
  (`wz` appears in the capture tool but no reduction computes it); and
  the C5 commit's scanner arithmetic, *"the left scanner at 1.033 m
  against a 1.000 m field — a 33 mm nominal margin"*. §4.2 makes the
  same point from figures that are on disk. The instruments behind those
  three were ad-hoc and were not kept beside their sessions; the
  instruments that were kept are under
  `m6_ver2/logs/run1[5-9]-*/instruments/`.
- **Wave C7 printed no suite count.** C6 closed at 488 and C8 opened at
  499. The eleven tests between them are in the tree and in `git`; no
  commit message states the intermediate number and this file will not
  reconstruct one.
- **Runs 1–10 have no reduction.** The `READING.txt` instrument arrived
  with wave C5. Their numbers in §3 come from the wave commit messages
  and the module docstrings that quote them line for line — both on
  disk, neither a session archive that can be re-reduced by a different
  method.

### What this file does not claim

- **It does not claim the sixteen classes are the last sixteen.** It
  claims each is named, mechanised, fixed, and re-measured in a later
  run directory that is on disk.
- **It does not claim a fleet.** One truck, one station pair, two
  orders. The first bullet of §6 is the honest headline of what G2 has
  to answer.
- **It does not re-derive anything the specs derive.** `ALIGN_M`,
  `ARRIVE_BIAS_M`, `LEAD_OVERHANG_M`, `TIE_BAND_RAD` and
  `MIN_TURN_RADIUS_M` each carry their own arithmetic beside them in
  `nav2_legs.py`, and the suite pins every one.
- **It changed no code.** `571 passed` at `8aa03a4`, the same number
  wave C9 closed on, re-run to prove it.
