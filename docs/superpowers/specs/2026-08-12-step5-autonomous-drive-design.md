# Step 5 — Simple autonomous drive on top of the Step 4 safety loop

Date: 2026-08-12 · Owner-approved design (brainstorm Q&A recorded below)
Scope: `m5_ver2/step5/` only. Step 4 stays frozen; the PLC program is never
touched.

## Goal

Take Step 4 as-is and add a lean autonomous drive above it:

- A warehouse sketch (kroki) beside the teleoperation GUI, showing 10
  stations, the forklift's live position and heading, and a
  teleop/autonomous selector with GO / STOP.
- The 10 stations visible both in Gazebo (floor paint) and on the sketch.
- Autonomy drives with the roof-mounted nav lidar as its obstacle guard;
  pose comes from Gazebo ground truth.
- The safety layer keeps running underneath, unchanged: PLC `Motor`,
  `V_Limit`, `cmd_gate`, `sto_contactor` all stay authoritative.
- The vehicle software runs "as if deployed to the industrial PC": from a
  frozen deploy copy with a manifest, not from the source tree.

## Owner decisions (2026-08-12)

| Question | Ruling |
|---|---|
| Localization | Gazebo ground-truth pose; the nav lidar is an obstacle guard, not a localizer |
| Routing | Fixed waypoint graph on the aisle centrelines + Dijkstra |
| Deploy boundary | IPC software only (plc_link, sensor_link, field_eval, encoder_link, cmd_gate, cmd_mux, nav_node) |
| Docker | **Skipped.** Docker Desktop's VM cannot pass DDS multicast; the deploy is simulated with a frozen copy + manifest instead |

## What already exists and is reused unmodified

`forklift_ver2/model.sdf` already carries both new data sources; Step 4
deliberately did not bridge them. Step 5 only opens the bridge:

- `nav_lidar` — roof mast, 360°, 8 m, 10 Hz, gz topic `/forklift/gz/scan_nav`.
- Ground-truth odometry — `/forklift/gz/odom`, 20 Hz
  (`gz-sim-odometry-publisher-system`; ground truth, zero drift, and the
  model file itself documents that it is the phase-1 interim pose source).

No change to `model.sdf` is needed.

## Architecture

Three layers on two real machines. Isolation: `GZ_PARTITION=step5`,
`ROS_DOMAIN_ID=95` (CONTEXT.md's reservation for the next step).

| Layer | Runs | Processes |
|---|---|---|
| PLC field wiring | Windows | `windows/step5.py` — Step 4's file renamed; single-writer rule unchanged |
| Plant + operator | WSL host | `gz sim` (world + station paint), `ros_gz` bridge (+2 topics), `sto_contactor`, `forklift_io`, HMI window |
| Industrial PC | WSL, **from `step5/deploy/` only** | `plc_link`, `sensor_link`, `field_eval`, `encoder_link`, `cmd_gate`, **new** `cmd_mux`, **new** `nav_node` |

### Command chain

```
HMI joystick ──/hmi/cmd_vel──┐
                             ├─ cmd_mux ──/vehicle/cmd_vel── cmd_gate ── sto_contactor ── plant
nav_node ────/auto/cmd_vel──┘      ▲
                                   │ /hmi/mode  ("teleop" | "auto", latched, default teleop)
```

- `cmd_mux` (new, IPC): forwards the selected source to `/vehicle/cmd_vel`.
  Default and fallback is teleop. Mode is a latched `std_msgs/String`.
- `cmd_gate` changes in exactly one way: its input topic becomes
  `/vehicle/cmd_vel`. Every safety behaviour (Motor, staleness,
  `V_Limit` clamp, NaN guard, continuous zeros) is untouched.
- `/hmi/cmd_vel` and `/auto/cmd_vel` both carry the Step 4 field contract:
  `linear.x` = traction speed m/s (forks-first forward is **negative**),
  `angular.z` = steer **angle** rad. Both limits still come from
  `agv/forklift/config.yaml`.
- New topic names (`/vehicle/cmd_vel`, `/auto/cmd_vel`, `/auto/goal`,
  `/auto/state`, `/hmi/mode`, odom and nav-scan ROS names) live in
  `status_contract.py`, the existing one home for names `config.yaml`
  does not own.

## Stations

Ten stations. One source of truth: `ipc/stations.py` (id, name, x, y,
approach yaw). The world file paints each as a flat floor disc + id ring,
6 mm proud, no collision — the same recipe as the charge-bay markings, so
no scan plane ever sees them. A test asserts the SDF paint and
`stations.py` agree, and that every station sits on free floor.

Rack geometry measured from `warehouse_ver2.sdf`: rack runs span
x ∈ [-10.0, -3.1] (west) and [3.1, 10.0] (east); central cross aisle
centreline x = 0; end-aisle centrelines x = -12.5 and x = +12.0;
main aisle centreline y = +5.65; dock aisle centreline y = -5.5.

| id | name | pose (x, y) | serves |
|---|---|---|---|
| S1 | HOME | (-3.0, -5.5) | spawn / park |
| S2 | CHARGE-1 | (-9.8, -6.6) | charge bay 1 apron |
| S3 | CHARGE-2 | (-7.4, -6.6) | charge bay 2 apron |
| S4 | DOCK-DOOR | (6.0, -8.0) | south dock opening |
| S5 | CONVEYOR | (13.0, 5.65) | conveyor face |
| S6 | PICK-A-W | (-8.0, 7.0) | rack A west, main aisle |
| S7 | PICK-A-E | (8.0, 7.0) | rack A east, main aisle |
| S8 | PICK-B-W | (-8.0, 4.3) | rack B north face west |
| S9 | PICK-B-E | (8.0, 4.3) | rack B north face east |
| S10 | PICK-B-S | (-6.0, -1.6) | rack B south face |

## Waypoint graph and routing (`ipc/route.py`, pure functions)

Nodes on the aisle centrelines:

- Main aisle y = 5.65: x ∈ {-12.5, -8, -3, 0, 3, 8, 12.0, 13.0}
- Dock aisle y = -5.5: x ∈ {-12.5, -9.8, -7.4, -6.0, -3, 0, 3, 6, 8, 12.0}
- Connectors x = -12.5, 0, +12.0 join the two aisles.
- Each station hangs off its nearest aisle node by a short spur.

Route = Dijkstra over that graph from the nearest graph node to the goal
station's node, prepended with the vehicle's current position. All ten
stations must be reachable from every node (tested).

## Autonomous drive (`ipc/nav_node.py` + pure helpers)

- **Pose** from the bridged ground-truth odom.
- **Follower**: pure pursuit on the route polyline, lookahead ~1.2 m,
  producing the Step 4 field contract (forward = negative `linear.x`;
  steer sign convention identical to `knob_to_twist`; locked by tests).
- **Speed policy** (target speed, before the gate's own clamp):
  - cruise 0.7 m/s on straight legs;
  - 0.3 m/s when the demanded steer angle exceeds 0.3 rad (corners);
  - 0.25 m/s on the final approach leg;
  - arrival: within 0.25 m of the station → zeros, state `ARRIVED`.
    Arrival is **position-only**: the stored approach yaw orients the
    spur and the paint, but a tricycle cannot rotate in place, so no
    final heading alignment is attempted or claimed.
- **Lidar guard** from `scan_nav`, evaluated in a ±35° sector around the
  direction of travel: min range < 3.0 m → cap 0.3 m/s; < 1.5 m → 0.0
  and state `HOLD` (resumes by itself when the sector clears). Guard
  distances deliberately exceed the case-1 warning field (2.5 m) so the
  lidar slows the truck before the PLC field trips at speed.
- **Safety interplay**: nav subscribes `/plc/status`. Motor False →
  state `SAFETY-STOP`, route held, resume after the operator's
  `Acknowledge` restores Motor. nav additionally caps its command at the
  PLC's live `V_Limit` so a field trip decelerates instead of latching
  the speed monitor.
- **Mode switch** auto→teleop cancels the goal and zeros `/auto/cmd_vel`.
  GO is only accepted in auto mode. Unreachable goal → refused with a
  status message, no motion.
- `/auto/state` (JSON String: state, goal, route, progress) feeds the HMI.

The stop chain is unchanged: nav is a *requester*; `cmd_gate` and
`sto_contactor` remain the deciders.

## HMI (`hmi/hmi_node.py` + new `hmi/map_panel.py`)

Step 4's window grows a right-hand panel (~460×320 px canvas, 15 px/m):

- Static sketch: walls, racks, dock door, charge bays, conveyor, safety
  zone — drawn once from constants that mirror the SDF.
- Ten numbered station discs, clickable to select.
- Forklift arrow (position + heading) from odom at the display tick.
- Selected station highlight + active route polyline + status line
  (mode, goal, EN-ROUTE / ARRIVED / HOLD / SAFETY-STOP).
- Mode selector (Teleop / Auto radio), GO and STOP buttons. Joystick
  drags are ignored by the mux in auto; the knob greys out.

All existing lamps and the staleness rules stay exactly as in Step 4;
a stale `/auto/state` shows the safe text (no claim), same rule as every
other indicator.

## Deploy simulation (instead of Docker)

- `step5.sh deploy` — copies `step5/ipc/` plus `agv/forklift/config.yaml`
  into `step5/deploy/`, then writes `deploy/MANIFEST` (per-file sha256,
  source git hash, timestamp).
- `step5.sh start` — starts plant + HMI from the source tree, but every
  IPC node **from `deploy/`**. No deploy directory → refuse with the
  command to run. Manifest hashes differing from the current source →
  one loud `deploy is STALE` warning (the vehicle then honestly runs the
  old version, which is the point of the exercise).
- `step5.sh stop` — Step 4's ours()/recorded() sweep with the step5
  partition and the two new node names added to `PATTERNS`.

## File layout

```
m5_ver2/step5/
  gazebo/            world (+ station paint), launch (+2 bridge topics), model
  ipc/               vehicle software (the deploy unit):
                     plc_link.py sensor_link.py field_eval.py encoder_link.py
                     cmd_gate.py status_contract.py
                     cmd_mux.py nav_node.py route.py stations.py   (new)
  hmi/               hmi_node.py map_panel.py                      (operator)
  windows/step5.py   PLC writer (renamed copy)
  deploy/            generated by `step5.sh deploy`; never edited by hand
  tests/             Step 4's suite carried + new suites below
  step5.sh           start [--headless] | stop | deploy
```

The `ros2/` directory of Step 4 is split into `ipc/` and `hmi/` because
the deploy boundary needs a directory boundary. `status_contract.py`
lives in `ipc/` (it ships with the vehicle); the HMI imports it from
there — one home, as in Step 4.

## Testing

Carried: all 55 Step 4 tests, renamed where paths changed. New:

- `test_route.py` — graph connectivity, Dijkstra shortest paths, all 10
  stations reachable from every node, spur attachment.
- `test_follower.py` — steer/traction signs (forks-first negative),
  lookahead geometry, corner slowdown, arrival stop.
- `test_nav_node.py` — lidar guard thresholds, HOLD/resume,
  SAFETY-STOP on Motor False and resume, V_Limit cap, goal refusal.
- `test_cmd_mux.py` — default teleop, latched switching, auto ignored in
  teleop mode, goal cancel on auto→teleop.
- `test_stations_sdf.py` — stations.py ↔ world paint agreement, unique
  ids, stations on free floor.
- `test_map_panel.py` — world→canvas transform, click→station pick.

A skip is a failure, as in Step 4.

## Validation checklist (PROOF.md earns every tick)

```
[ ] step5.sh deploy then start: world + paint + HMI with sketch up
[ ] Teleop regression: a once, joystick drives, es0/es1/a behave as Step 4
[ ] Auto: select S7, GO -> drives the aisles, arrives within 0.25 m
[ ] Obstacle on route -> HOLD; removed -> resumes; PLC never latched
[ ] es0 mid-drive -> stops; a -> resumes the same route
[ ] Mode to Teleop mid-drive -> goal cancelled, joystick live instantly
[ ] Stale-deploy check: edit ipc/ source, no deploy -> vehicle runs old
    version and start prints the STALE warning
[ ] step5.sh stop -> clean sweep, PLC untouched
```

## Risks, stated

- **`V_Limit` is live** (Step 3 measured a latched stop 0.68 s after
  enable near racking). Mitigations: lidar guard thresholds above the
  warning field, nav's own V_Limit cap, and station approaches at
  0.25 m/s. A latched stop still costs one `Acknowledge` — accepted.
- The monitoring case is PLC-side; if it selects a larger field than
  case 1 in the aisles, cruise legs will spend time at 0.3 m/s. The demo
  stays correct, only slower.
- llvmpipe rendering makes the GUI lumpy (Step 4 measured RTF floor
  0.127 with the window). Timing evidence is collected headless, as
  before; the sketch adds one canvas redraw at display rate.
