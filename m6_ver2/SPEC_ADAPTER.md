# M6V2 NAV2 ADAPTER — SPEC (G0-T2)

> **AMENDED BY AMR-DEC-006 (2026-09-02), read this first.**
> This spec stands EXCEPT:
> - The namespacing sentence in Decision 6 ("namespaced `/fN/tf`,
>   `/fN/tf_static` and UNPREFIXED frame names") is **SUPERSEDED** by
>   SPEC_NAMESPACING.md §2: ONE shared `/tf`+`/tf_static`, per-truck
>   PREFIXED frames (`fN/odom`, `fN/base_link`), ONE shared `map`
>   frame. Decision 4's TF composition therefore matches
>   `map -> fN/odom` and `fN/odom -> fN/base_link` on the shared tree.
> - Module homes: `m6/nav2_adapter/` becomes **`m6_ver2/nav2_adapter/`**
>   and `vehicles/fN/...` paths live under `m6_ver2/vehicles/` —
>   `m6/` and `m5_ver3/` stay byte-untouched in G1.
> Decision 1's command seam is CONFIRMED by DEC-006 and overrides
> SPEC_NAMESPACING.md §3.3's pre-contactor rewiring.

Mission: per truck, retire `m6/ipc/nav_node.py` + `nav_core.py` +
`follower.py` (+ `avoid.py`) as the motion engine and put a NAV2
ADAPTER in their place that presents the byte-identical contract to the
untouched fleet layer (`vda_agent.py`, `vda_orders.py`,
`vda_messages.py`, `m6/fleet/*`, `cmd_mux.py`, `cmd_gate.py`, `hmi/*`),
driving a per-truck instance of the m5_ver3 Nav2 stack underneath. The
contract, verified in source:

- `/[vid]/auto/route` JSON `{points, arrive_m, label}` — refused by
  name, never repaired (`nav_core.on_route`)
- `/[vid]/auto/goal` — empty string is the one cancel door; non-empty
  is an HMI station GO (`nav_core.on_goal`)
- `/[vid]/auto/state` JSON at 10 Hz: `{state, goal, note, route, pose,
  reversing, arrive_m, guard_min}` with vocabulary IDLE / EN-ROUTE /
  HOLD / SAFETY-STOP / ARRIVED / AVOID / NUDGE / BLOCKED
- `/[vid]/auto/cmd_vel` Twist: `linear.x` = traction m/s, forward
  (forks-first) NEGATIVE; `angular.z` = STEER ANGLE rad, positive
  driver-right (`cmd_gate.py` header owns the field contract)
- vda_agent behaviors that must keep working against the adapter:
  `NAV_SETTLE_S` 0.3 refusal reconciliation, the 5 s cancel pump
  reading IDLE+no-goal, `_settle_arrival`'s two-fact rule (nav ARRIVED
  for our label AND `Progress.reached == len(nodes)` on odometry), and
  the BLOCKED edge → `pathBlocked` WARNING.

---

## DECISION 1 — Where Nav2's output joins the safety-gated chain

**The chain (recommended; CONFIRMED by DEC-006):**

```
Nav2 controller_server (/fN ns)  -> /fN/cmd_vel            (Twist: v m/s signed, w rad/s)
  -> nav2_velocity_smoother      -> /fN/cmd_vel_smoothed   (accel-shaped twist)
    -> ADAPTER translate          -> /fN/auto/cmd_vel      (traction m/s fwd-negative, STEER ANGLE rad)
      -> cmd_mux (HMI vs auto)    -> /fN/vehicle/cmd_vel
        -> cmd_gate (Motor, staleness, V_Limit clamp)
          -> forklift_io -> sto_contactor -> gz actuator terminals
```

**What ports from m5v3, what stays m6, what dies:**

| Piece | Fate | Why |
|---|---|---|
| nav2 servers + `nav2.yaml` (per-truck instance) | ports | the stack being adopted |
| `smoother.yaml` / nav2_velocity_smoother | ports | Nav2's output steps on every replan; m6's plant has no ramp of its own |
| `nodes/cmd_vel_tricycle_core.py` `twist_to_tricycle` | ports **as an import, not a copy** | the (v,w)→(steer angle, tread) inverse kinematics the adapter needs; one home for tan/atan and the yaw-rate-at-standstill refusal |
| `nodes/cmd_vel_tricycle.py` (the shell) | does NOT port | it publishes gz actuator topics directly, bypassing mux/gate — the exact thing m6 forbids. The smoother already shapes accel |
| m6 `cmd_mux`, `cmd_gate`, `forklift_io`, `sto_contactor` | stay, byte-untouched | PLC authority. cmd_gate keeps the last word on Motor/staleness/V_Limit; the mux keeps HMI teleop as the floor |
| m6 `follower` speed policy | retired from control | Nav2's envelope is already 0.300 m/s both directions, AT the PLC creep ceiling — the latched-stop class is structurally absent. Cost, stated: the dock aisle loses its 0.7 m/s cruise |
| `follower.sector_min` + SELF_MASK | kept as a REPORTING import only | `/auto/state.guard_min` stays honest for the HMI; no control role |

**Sign audit (must be pinned by test):** both stacks share model yaw 0
= forks at −x, so Nav2's ordinary reverse leg already commands negative
`linear.x` — the traction sign passes through UNCHANGED. What changes
type is `angular.z`: yaw RATE in, STEER ANGLE out, via
`twist_to_tricycle`. m5v3 states "positive steer is driver-right =
negative angular.z in base_link"; m6 states "positive angular.z is a
driver-right turn" — so the adapter emits `angular.z = +steer_rad`
(driver-right positive) and a worked-example sign test in the
`test_follower` idiom locks it, because getting it wrong steers at the
rack.

**The `/speed_limit` slot:** three layers, all pointing the same way
("approach the limit from below" — the Step-3 lesson `nav_core`
already obeys):
1. Adapter subscribes `/fN/plc/status`, and on V_Limit change publishes
   `nav2_msgs/SpeedLimit` (absolute, `v_limit/1000` m/s) on
   `/fN/speed_limit` → controller_server plans at the permission.
2. Adapter applies `core.apply_speed_limit` (curvature-preserving
   whole-twist scale) in translation as the authoritative cap at
   source.
3. cmd_gate still clamps — unchanged, last word.

**SAFETY-STOP against an active NavigateToPose — cancel, not starve
(recommended):** on Motor False or `/plc/status` stale
(`STATUS_STALE_S`, same silence-is-a-demand rule as `nav_node`), the
adapter CANCELS the active goal, latches state SAFETY-STOP, publishes
zeros on `/auto/cmd_vel` (the stream keeps flowing), and — nav_core's
"SAFETY-STOP HOLDS THE ROUTE" — keeps the leg queue and route intact.
On Motor returning, it re-sends the current leg goal from the current
pose; state returns to EN-ROUTE with no operator ritual. Alternative
weighed and rejected: leaving the goal running while zeroing output
starves `SimpleProgressChecker` (0.30 m / 15 s), which aborts with an
error code the adapter would then have to lie about; a cancel is the
clean, named path.

## DECISION 2 — Route execution

**Leg model (recommended): sequential `NavigateToPose` goals with
rolling preemption; NOT NavigateThroughPoses, NOT one goal to the far
end, NOT one goal per node.**

- One goal straight to the final released node lets SmacPlannerHybrid
  choose its own corridor — the traffic ledger granted a *specific*
  polyline, and a freespace shortcut through an ungranted aisle breaks
  the fleet's floor model. Rejected.
- NavigateThroughPoses keeps the corridor but is one action = one
  behavior tree = ONE controller for the whole route — which kills the
  per-leg controller rule (the tree travels in the goal's
  `behavior_tree` field, per `drive_goal.send_goal`). Rejected.
- One goal per graph node makes the truck decelerate into every node.
  Rejected as the steady state, kept as the mechanism:

**The leg runner:** split the released polyline into LEGS (maximal
near-collinear runs; split at junction turns and at the station spur
foot). Send leg k as `NavigateToPose` (goal = leg end, `behavior_tree`
= leg class's tree); when the BELIEVED distance to leg k's end first
falls below **P = 1.5 m**, preempt with leg k+1 — `navigate_to_pose` is
a single-goal server, nav2 displaces the old goal itself, and F4 Task
3's `Preempt` instrument already measured the cost of exactly this
switch (gap ~0.05 s class). P = 1.5 m sits OUTSIDE MPPI's endgame
(`threshold_to_consider` 1.4 m), so intermediate leg ends never enter
the point-attraction at all. Only the final leg runs to actual
completion. The adapter must label goal handles with a generation
counter so a preempted leg's ABORTED result is never read as a
failure.

**arrive_m is NOT a per-goal Nav2 tolerance** (no such field exists).
Delivered by two mechanisms:
- Intermediate node accounting stays exactly `vda_orders.Progress` in
  the untouched vda_agent (0.8 m `DEFAULT_DEV_M` waypoints by odometry
  — now the estimate, Decision 4). The adapter counts nothing.
- Final arrival: the final (spur) leg runs the RPP tree whose
  `FollowPath` BT node names a second goal checker (`goal_checker_id` =
  `station_goal_checker`, `PositionGoalChecker` at 0.25 m stateful,
  added to the per-truck `nav2.yaml` instance's
  `goal_checker_plugins`); transit legs keep the 0.60 m checker.
  ARRIVED itself is decided by the ADAPTER (Decision 3), latched the
  first tick the believed pose is within `arrive_m` of the final point
  — the same measurement `Progress` makes, on the same estimate, at the
  same radius ("same measurement made twice"). On a Nav2 SUCCEEDED that
  never entered `arrive_m`: do NOT re-send (a 0.4 m goal is inside the
  turning circle — the measured S7 orbit); go BLOCKED with note
  "arrived short: {d} m against arrive_m {r}".

**Extensions (new `/auto/route` mid-drive): continue, don't churn.**
vda_agent already re-sends the remaining released nodes as a fresh
pose-prepended route (`_extend` → `_send_route`). The adapter re-splits
into legs and REPLACES its pending leg queue; the in-flight goal
continues untouched when its leg end survives the re-split (it always
does — the base is kept BY RULE, `_base_kept`), so nothing stops and
`executing` never flickers. Only if the current leg was the last one
and the extension appends beyond it does the adapter preempt-forward
into the new tail.

**Per-leg-class controller/BT (generalizing m5v3's G5 per-origin
rule):**

| Leg class | Definition (geometric, from the polyline + `stations.STATIONS`) | Controller / tree |
|---|---|---|
| station spur | final leg whose end lies on a station point | `rpp` / `nav.bt_xml_rpp` |
| reversal / spur exit | first leg out of a route whose start pose stands on a station point (dead-astern start) | `rpp` / `nav.bt_xml_rpp` |
| transit | everything else | `mppi` / `nav.bt_xml` (default) |

**Where the mapping lives:** the class→tree table is a constant in the
pure module `nav2_legs.py` (mirroring `drive_goal.CONTROLLER_TREE`, one
table, refusal on an unknown name); the tree FILE PATHS live in the
per-truck `m6_ver2/vehicles/fN/config.yaml` nav block; the geometry
comes from `stations.STATIONS`. Named risk, not a blocker: four MPPI
instances at batch 1000 / 20 Hz may sink the RTF — RPP-for-all-legs is
the sanctioned fallback, decided by a gate RTF measurement, not by this
spec.

## DECISION 3 — State reporting

The fleet branches only on BLOCKED and ARRIVED (`vda_agent.cb_nav`);
everything else is operator vocabulary. The adapter keeps the full
vocabulary; AVOID and NUDGE are **retired as emitted states** (Nav2's
costmap + BT recoveries replace the escalation) but remain reserved
words in the contract doc.

| State | Entered when | cmd_vel out | Exits |
|---|---|---|---|
| IDLE | boot; cancel; refusal; mode left auto | zeros flow | route/goal accepted → EN-ROUTE |
| EN-ROUTE | route or station GO accepted (set SYNCHRONOUSLY on acceptance — vda's `NAV_SETTLE_S` window depends on it), leg goals running | translated twists | ARRIVED / BLOCKED / SAFETY-STOP / HOLD / IDLE(cancel) |
| HOLD | BT recovery running (feedback `number_of_recoveries` incremented) or leg-switch settling; also the "no picture" posture (pose/scan stale under `SENSOR_STALE_S` 0.5) with note "pose stale" | zeros | recovery ends → EN-ROUTE; watchdog → BLOCKED |
| SAFETY-STOP | Motor False or `/plc/status` stale; goal cancelled, route HELD | zeros | Motor True → re-goal current leg → EN-ROUTE |
| ARRIVED | believed pose first within `arrive_m` of final point, for this label (latched) | zeros | new route → EN-ROUTE; cancel → IDLE |
| BLOCKED | named Nav2 failure or adapter watchdog; edge-reported once by vda_agent as `pathBlocked` | zeros | new route / cancel |

**BLOCKED sources and their notes** (the note is the wire's only WHY,
so it names the instrument):
- adapter ClosingWatch (port of `drive_goal.ClosingWatch`,
  `required_closing_m`/`allowance_s` from config) fires on the believed
  distance → cancel goal, note
  `"blocked: no progress - best {mark:.2f} m, {since:.0f} s without closing"`.
- action ABORTED with 2xx planner code (203/205/206/208) → note
  `"blocked: planner refused (error_code {n})"`. 205 START_OCCUPIED
  specifically names the costmap-under-the-footprint class.
- action ABORTED with 1xx controller code (incl. 106 NO_VALID_CONTROL,
  104 PATIENCE_EXCEEDED, 105 FAILED_TO_MAKE_PROGRESS) → note
  `"blocked: controller gave up (error_code {n})"`.
- final SUCCEEDED short of `arrive_m` → note above.

**Refusal grammar is part of the contract**, reproduced byte-for-byte:
`"route refused: malformed points"`, `"route refused: fewer than two
points"`, `"route refused: unusable arrive_m"`, `"route refused: not in
auto mode"`, `"goal refused: no pose yet"`, `"cancelled"`, and `"mode
left auto"`. IDLE + note + empty goal is what ends `executing` on the
fleet side; the adapter refuses BEFORE assigning, all-or-nothing,
exactly as `on_route` does.

`reversing` := commanded `linear.x > 0` beyond a deadband (positive =
counterweight-first = m6's reverse). `route` := the polyline held.
`guard_min` := `follower.sector_min` on the live scan, reporting only.

## DECISION 4 — Pose: the estimate, and the ground-truth firewall

**Transform:** the adapter composes `map→fN/odom` (AMCL) ∘
`fN/odom→fN/base_link` (EKF) off the SHARED `/tf` (per DEC-006; the
`drive_goal.on_tf` zero-order-hold idiom — match on BOTH frame names)
and carries it into m6 world coordinates through the committed
`m5_ver3/maps/warehouse_v3/registration.yaml` INVERSE:
`p_world = R(−θ)·(p_map − t)`, `yaw_world = yaw_map − θ`. Loaded via
`map_register.load_registration` so the md5 binding refuses a transform
whose grid changed — the registration was fitted against
`m6/gazebo/warehouse_ver3.sdf`, which IS m6's live world, so the frame
closes. Published two ways: in `/auto/state.pose`, and as
`nav_msgs/Odometry` on **`/fN/est/odom`** at 20 Hz (pose = world
estimate, twist = EKF body velocity, so vda_agent's `driving` flag
stays honest).

**Staleness:** `SENSOR_STALE_S` 0.5 applies to the estimate: no fresh
`odom→base_link` sample within 0.5 s → the pose is GONE — zeros flow,
new routes refused "no pose", state note "pose stale"; if it persists a
full second the active goal is cancelled and the route is held for
resume. One deliberate contract deviation, named: `nav_node` stops
publishing `/auto/state` entirely on stale pose; the adapter keeps the
10 Hz stream with the note — silence was the worse behavior and nothing
downstream depends on it.

**The firewall:** `/fN/gz/odom` ground truth is consumed by NOTHING in
the adapter or fleet path. Mechanism (the one spot where G1 touches
config/launch, not fleet bytes): `m6_ver2/vehicles/fN/config.yaml`
`topics.gz_odom` is re-pointed to `/fN/est/odom` — vda_agent (and the
HMI) read that KEY, byte-untouched, and now receive the estimate;
the world launch bridges the real ground truth from a NEW key
`topics.gz_odom_truth: /fN/gz/odom` so the wire name `score_run.py`
hardcodes still carries truth for evidence only. Named leftover: the
key `gz_odom` now lies about its source; rename it the day the fleet
layer unfreezes. Consequence, wanted: `Progress` now counts on the
estimate — the same odometry the adapter's ARRIVED reads, restoring the
"same measurement twice" invariant.

## DECISION 5 — Cancel and the HMI door

- **Empty `/auto/goal`:** cancel the active goal (`cancel_goal_async`),
  flush the leg queue, drop route/goal, state IDLE note `"cancelled"`.
  The vda 5 s pump confirms on IDLE + no goal; nav2 cancels return in
  well under a second and the adapter's answer is synchronous in its
  own state tick. Cancel with nothing running is already-IDLE, which is
  itself the confirmation. The adapter must process the cancel even
  while a leg goal is between preempt and accept (generation counter
  again).
- **Non-empty `/auto/goal` (HMI station GO): KEPT, planned via
  `route.plan_route` exactly as today.** `route.py` is pure and stays;
  the polyline it returns enters the same leg runner as a vda route.
  Same guards: auto mode only, `"goal refused: unknown station {id}"`,
  `arrive_m` from `STATIONS`.

## DECISION 6 — The seed and per-truck bringup health

One honest seed at boot, never continuous truth feeding — m5v3's own
arm rule ("seeded by a MESSAGE on /initialpose").

Boot sequence per truck (order is load-bearing, from `m5v3.sh`'s
measured ordering):
1. map_server ACTIVE first (world-owned, shared), then AMCL
   configured/activated (AMCL's `on_activate` blocks waiting for a
   latched map).
2. wheel_odometry (off `/fN/gz/joint_state`) + EKF up →
   `fN/odom→fN/base_link` flowing.
3. Seed: take the spawn from `status_contract.VEHICLES[vid]["spawn"]` —
   the known truth at boot — carry it world→map through the
   registration (the `map_register.seed_pose` arithmetic, widened to
   take a pose argument), publish ONE `PoseWithCovarianceStamped` on
   `/fN/initialpose`.
4. Health gate (the `localization_health` idiom): AMCL publishes
   exactly one pose per seed with the truck standing; verify covariance
   under ceiling AND pose within tolerance of the seed; verify
   `navigate_to_pose` server answers; verify smoother/adapter chain
   alive. Refuse loudly by name on any miss.
5. Only then does the adapter leave its boot posture; until then
   `/auto/state` runs IDLE with note `"localiser not ready"` and routes
   are refused.

Namespacing: per SPEC_NAMESPACING.md §1-§2 (DEC-006): `/fN` node
namespace, shared `/tf`, prefixed frames. One world, one `/clock`,
`use_sim_time` everywhere.

---

## Module layout (m5v3 idiom: pure core + thin shell + selftest + named refusals)

Directory `m6_ver2/nav2_adapter/`, one module per G1 task, each pure
module carrying a `_selftest()`:

| Task | Module | Owns |
|---|---|---|
| A-T1 | runner integration (with SPEC_NAMESPACING T4/T5) | bringup ordering, read-back checks, state-file labels; `gz_odom_truth` bridge key |
| A-T2 | `scan_mask.py` + shell | the SELF_MASK contour filter republishing `/fN/gz/scan_nav` → `/fN/scan_nav_masked` for AMCL and both costmaps — the ver2-lineage mast returns at 1.29–1.48 m would otherwise put occupied cells ON the robot (205-class refusals, every plan) |
| A-T3 | `nav2_pose.py` (pure) + est-odom publisher in the shell | TF compose, registration inverse, staleness rule, world-frame Odometry rows |
| A-T4 | `nav2_seed.py` (tool) | per-truck seed + health gates, named refusals |
| A-T5 | `nav2_cmd.py` (pure) | twist→(traction, steer-angle) via `cmd_vel_tricycle_core.twist_to_tricycle`, sign convention, V_Limit clamp, SpeedLimit mapping |
| A-T6 | `nav2_legs.py` (pure) | leg split, class table, preempt threshold arithmetic |
| A-T7 | `nav2_state.py` (pure) | contract state machine, refusal grammar, `state_json` |
| A-T8 | `nav2_watch.py` (pure) | ClosingWatch port, error-code→note table |
| A-T9 | `nav2_adapter_node.py` (shell) | wiring only: subscriptions, action client with goal generations, 20 Hz tick, 10 Hz state |
| A-T10 | config/instantiation (with SPEC_NAMESPACING T1) | nav block (tree paths, watchdog numbers, est-odom seam), `station_goal_checker` added to derived nav2.yaml |
| A-T11 | `m6_ver2/tests/test_nav2_adapter_*.py` | contract pins (below) |

## Test plan

**New contract pins (against a fake action server, no simulator):**
refusal strings byte-exact; EN-ROUTE assigned synchronously on
acceptance (NAV_SETTLE_S safety); cancel → IDLE+`"cancelled"`+no goal
inside one tick (5 s pump satisfied); mode-leave → `"mode left auto"`;
SAFETY-STOP cancels-holds-resumes without touching route/goal; ARRIVED
latch at `arrive_m` on the estimate; BLOCKED once per failure with the
named note; sign worked-examples for `nav2_cmd` (the `test_follower`
idiom); state JSON schema incl. NaN-refusal; leg split/classification
fixtures; preempted-leg ABORTED not read as failure.

**Must keep passing UNMODIFIED:** `test_vda_agent_mqtt`,
`test_vda_orders`, `test_vda_messages`, `test_progress`,
`test_order_builder`, `test_fleet_core`, `test_fleet_manager_mqtt`,
`test_fleet_manager_stub`, `test_fleet_cli`, `test_traffic`,
`test_work_generator`, `test_cmd_gate`, `test_cmd_mux`,
`test_hmi_node`, `test_map_panel`, `test_route`, `test_stations`,
`test_stations_sdf`, `test_status_contract`, `test_vehicles_table`,
`test_plc_link`, `test_sensor_link`, `test_encoder_link`,
`test_field_eval`, `test_virtual_fplc`, `test_send_order`,
`test_fleet_spawn_fairness`; and on the m5v3 side `test_nav2_params`,
`test_smoother_params`, `test_cmd_vel_tricycle_*` (they pin the files
being reused). `test_follower` / `test_nav_core_escalation` /
`test_nav_node` / `test_avoid` keep passing trivially (files stay
in-tree, unused) — retiring them is a named leftover. The ONE m6 test
allowed to change is `test_m6.py` where it pins the bringup child list
— and only in a later gate; in G1 m6.sh is not touched.

## Open questions (named, not blockers)

1. AMCL robustness with three other trucks as un-mapped moving
   obstacles in the scan — m5v3 was single-vehicle; measure at the
   first gate.
2. RTF with four Nav2 stacks; RPP-for-all is the sanctioned fallback.
3. Does the 0.25 m station checker latch reliably on the estimate at
   creep? (Orbit-vs-short tradeoff; gate measurement.)
4. Ver2-lineage vehicle geometry vs ver3 numbers (wheel radius 0.12 vs
   0.1206, turning-radius re-derivation for
   `minimum_turning_radius`/`min_turning_r`).
5. Corridor adherence bound under Nav2 local avoidance vs the traffic
   ledger's grants (legs keep it near; the bound should be measured).
6. Leftovers: rename the `gz_odom` config key; retire the four dead nav
   modules and their tests; dock-axis final leg (out of scope).
