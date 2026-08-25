# amr-agent

**A simulated forklift, a real fail-safe PLC program deciding what it is
allowed to do — and now an autopilot driving under that decision.**

The vehicle lives in Gazebo. The decisions live in a Siemens S7-1516F
safety program, built in TIA Portal and run on S7-PLCSIM Advanced —
e-stop chain, three safety laser scanners, a two-channel speed
cross-check, a monitored reset. On top of that chain sits a lean
autonomy layer: ten stations painted into the warehouse, a waypoint
router, a roof lidar guarding the path, and an operator screen where you
pick a station and press GO. The safety program can refuse all of it at
any moment, and the point of this repo is watching it do exactly that.

The project's purpose is a simulation environment for **demonstrating
safety functions** and exercising **PL d-style requirements** against a
live F-program — e-stop, protective and warning fields, speed
monitoring, monitored reset — with autonomous and teleoperated motion
running underneath them.

![AMR-AGENT — the layer pyramid: deterministic safety at the base, teleoperation over PLC↔ROS 2, autonomy, VDA 5050 fleet, LLM supervision on top; safety never traverses the network](assets/amr-agent-infographic.png)

*The stack, bottom-up: the four lower layers are running today (M6 —
four forklifts under a VDA 5050 fleet manager); the LLM layer is the
road ahead (M7). Safety never traverses the network — the LLM sees
everything, acts through the fleet layer only, and can bypass no
interlock.*

## Watch it run

**1 · Safety + Autonomous Drive:**

[![Safety + Autonomous Drive — station-to-station runs under the live safety chain](https://img.youtube.com/vi/0svQWMT256A/maxresdefault.jpg)](https://youtu.be/0svQWMT256A)

*▶ [**Watch**](https://youtu.be/0svQWMT256A) — pick a station on the
sketch, press GO: reverse-out departures from the rack faces,
pure-pursuit runs down the aisles, the roof lidar guarding the path —
and the F-program holding the drive enable, the fields and the speed
ceiling over every metre of it.*

**2 · Safety + Teleoperation:**

[![Safety + Teleoperation — e-stop, three safety scanners and the encoder cross-check against a driving forklift](https://img.youtube.com/vi/InZRcy_WUXY/maxresdefault.jpg)](https://www.youtube.com/watch?v=InZRcy_WUXY)

*▶ [**Watch**](https://www.youtube.com/watch?v=InZRcy_WUXY) — one
continuous teleoperated session with the safety layer live: the drive
enable refused until the first acknowledge, an e-stop that latches
through its own release, a protective field that stops the truck and
refuses to un-stop while the cause stands, the warning field dropping
the speed ceiling, and an injected encoder fault caught by the
cross-check.*

**3 · VDA 5050 Fleet Management:**

[![VDA 5050 fleet management — four forklifts, the operator's screen and the MQTT wire itself, one uncut take at the warehouse's true speed](https://img.youtube.com/vi/RGjbhj6Tb70/maxresdefault.jpg)](https://www.youtube.com/watch?v=RGjbhj6Tb70)

*▶ [**Watch**](https://www.youtube.com/watch?v=RGjbhj6Tb70) — the M6
cell in one take, three panels: the floor from above, the operator's
own fleet screen, and the VDA 5050 wire told one readable line per
event. Four transport tasks typed at the console ten seconds apart,
each assigned to the nearest idle truck; every order carries its pick,
the trucks report the cycle WAITING → RUNNING → FINISHED and leg 2
follows the report; corridors are reserved edge by edge and grow as
they drain; a swap deadlock resolves itself by a step-aside on camera.
Plays at the plant's true speed — and the reversing at stations is the
forklift backing out of a spur by design.*

*(The first build's own demonstration is linked from
[its archive](m5/m5_ver1/README.md) — and it runs again without PLCSIM,
on a virtual PLC.)*

## The system

Since M6 the cell is a **fleet**: four of the M5 vehicle, cloned by
manifest onto one 48 × 32 m floor with twelve stations, under one
master control that speaks VDA 5050 and nothing else. Per vehicle the
M5 anatomy is unchanged — three layers, each with exactly one writer:

| Layer | Runs on | What |
|---|---|---|
| **Safety PLC** (×4) | Windows — one writer process per truck | The F-program per vehicle: three ESTOP1 chains AND-ed into one `Motor` enable, a speed ceiling (`V_Limit`), monitoring cases. M6 runs four **virtual F-PLCs** ([`m6/windows/virtual_fplc.py`](m6/windows/)) — the same chain, byte-for-byte the same verdicts, no PLCSIM licence needed; [`safety_summary.pdf`](safety_summary.pdf) is the original F-program's Safety Administration printout. The panel window ([`m6/windows/m6.py`](m6/windows/)) or its scripted stand-in ([`m6/tools/scripted_writer.py`](m6/tools/scripted_writer.py)) plays the field wiring: e-stop, reset, encoder faults. |
| **Plant + operator** | WSL2 — Gazebo, ROS 2 Jazzy | The warehouse ([`m6/gazebo/warehouse_ver3.sdf`](m6/gazebo/)): a speed-limited ring, a spine, twelve stations in open cross-aisles, a dock annex, an overhead camera — and four forklift models, each with three safety scanners and a roof nav lidar. One commissioning HMI per vehicle. |
| **Vehicle software** (×4) | WSL2, run **from a frozen deploy copy** | The industrial-PC layer per truck: PLC link, sensor/field/encoder chains, the command gate, the teleop/auto mux, the autopilot — plus the **VDA 5050 agent** ([`m6/ipc/vda_agent.py`](m6/ipc/vda_agent.py)), the truck's only ear to the fleet. Deployed by manifest (`m6/m6.sh deploy`) exactly as a real vehicle would receive an image. |

And above them, the fleet layer — **no ROS in it, by invariant**:

| Layer | Runs on | What |
|---|---|---|
| **Master control** | WSL2 — paho-mqtt only | A local mosquitto broker, the fleet manager ([`m6/fleet/fleet_manager.py`](m6/fleet/)) — FIFO queue, nearest-idle dispatch, a traffic ledger that reserves the floor edge by edge — and the operator console ([`m6/fleet/fleet_cli.py`](m6/fleet/)): submit transports, watch the retained status screen. |

Every command — joystick, autopilot or fleet order — still passes the
same seam: `mux → gate → contactor → plant`, and the gate obeys the
PLC's `Motor` bit and speed ceiling on every message. The fleet layer
**cannot reach a safety function**: its only path to a truck is
VDA 5050 over MQTT, so the worst it can say is a route or a cancel —
and losing it degrades the cell, never endangers it. Silence anywhere
fails closed.

**Quickstart: [RUNBOOK.md](RUNBOOK.md)** — the fleet cell first, the
single M5 vehicle after it. Depth per component:
[`m6/README_m6.md`](m6/README_m6.md) with its measured evidence in
[`m6/PROOF.md`](m6/PROOF.md); the single vehicle in
[`m5_ver2/step5/README_step5.md`](m5_ver2/step5/README_step5.md) and
[`m5_ver2/step5/PROOF.md`](m5_ver2/step5/PROOF.md).

## How VDA 5050 is implemented, roughly

The wire is **VDA 5050 v2.1.0 over MQTT**, pinned to the official
schemas field by field in
[`docs/interfaces/vda5050-subset.md`](docs/interfaces/vda5050-subset.md)
— nothing on the wire is invented, and every deliberate deviation is
recorded there with its reason. Topics, per truck:

```
uagv/v2/amragent/<serial>/order            fleet → truck   the work
uagv/v2/amragent/<serial>/instantActions   fleet → truck   cancelOrder, stateRequest, factsheetRequest
uagv/v2/amragent/<serial>/state            truck → fleet   position, order progress, actionStates, errors, safety
uagv/v2/amragent/<serial>/connection       truck → fleet   ONLINE / OFFLINE / CONNECTIONBROKEN (broker last-will, retained)
uagv/v2/amragent/<serial>/factsheet        truck → fleet   what THIS vehicle actually implements (retained)
```

* **A transport is two orders.** Leg 1 drives to the pickup carrying a
  `pick` action on the station node; leg 2 carries the `drop`. The
  truck runs the fork cycle itself and reports it — `WAITING` from
  acceptance, `RUNNING` on arrival, `FINISHED` when done — and the
  fleet releases leg 2 on the report, never on its own clock.
* **Traffic rides the base/horizon split.** Every leg is planned whole,
  then held in a reservation ledger ([`m6/fleet/traffic.py`](m6/fleet/traffic.py)):
  what the floor grants goes out `released` (the base the truck may
  drive), the rest rides as horizon, and as corridors drain the base is
  extended with `orderUpdateId + 1`. A truck at the end of its base
  stops on its own — no pause action, nothing to un-stick. Reservation
  is process deconfliction, never a collision claim: the scanners and
  the F-model are what stop a truck.
* **One door, used by both ends.** Order validation and acceptance live
  in one pure module ([`m6/ipc/vda_orders.py`](m6/ipc/vda_orders.py)):
  the vehicle validates what it receives with it, and the fleet
  validates every order **through the same function before publishing**
  — the two ends cannot drift apart.
* **The state is honest.** An arrival is two facts (nav finished its
  polyline AND odometry counted every released node); a cancel is a
  closed loop (the actionState stays `RUNNING` until navigation
  confirms the stop, and goes `FAILED` if it never does); a truck's
  death is the broker's retained last-will, and the factsheet declares
  only the actions that actually run — never what would fail.

The wire pane in the video above is exactly this conversation, one
line per event.

## Milestones

| Gate | Scope | Status |
|---|---|---|
| M0 | Repo skeleton, invariants (ADR 0001) | ✅ |
| [M1](m1/) | Interface contracts — VDA 5050 subset, OPC UA node model | ✅ |
| [M2](m2/) | Safety requirements spec | ✅ |
| [M3](m3/) | Fixed equipment I/O loop — Gazebo ↔ PLC both directions, measured | ✅ |
| [M4](m4/) | Forklift commissioning cell — teleop through the PLC standard program | ✅ |
| [M5](m5/) | Sensored autonomous forklift — the safety chain live under teleop **and** autonomy | ✅ |
| [M6](m6/) | VDA 5050 fleet at scale — 4 forklifts, 12 stations, traffic reservation, pick/drop on the wire | ✅ |
| M7 | LLM operations layer + recorded end-to-end demonstration | ⏳ |
| M8 | Beckhoff/TwinCAT vendor portability — same bridge, different PLC | ⏳ |

## How the repo is laid out

| Tree | What it is |
|---|---|
| [`m6/`](m6/) | **The current system** — the VDA 5050 fleet cell: [`m6.sh`](m6/m6.sh) brings it up, [`README_m6.md`](m6/README_m6.md) is the deep runbook, [`PROOF.md`](m6/PROOF.md) the measured evidence. `fleet/` (manager, console, traffic ledger, floor), `ipc/` (per-vehicle nodes + the VDA agent and order rules), `windows/` (panel + virtual F-PLC), `tools/` (preflight, recorders, scripted writer), `gazebo/` (the M6.6 floor). |
| [`m5_ver2/`](m5_ver2/) | **The single vehicle M6 cloned.** Built as five frozen steps, each a verified copy of the last; [`step5/`](m5_ver2/step5/) is the one that runs alone. [`m5_ver2/CLAUDE.md`](m5_ver2/CLAUDE.md) holds the PLC ground truth and working agreements. |
| [`beckhoff/`](beckhoff/) | **The PLC substrate after the TIA trial** — the safety chain on TwinCAT 3.1 (user mode runtime): [research](beckhoff/RESEARCH.md), [runbook](beckhoff/RUNBOOK.md), the [TE9000 safety-application spec](beckhoff/plc/safety/SAFETY-APP.md), its ST stand-in executor and the pyads writer. Same UDP wire; the WSL side runs unchanged. |
| [`m5/`](m5/) | **The M5 archive.** [`m5_ver1/`](m5/m5_ver1/) — the first build (Claude-supervised): runbook, videos, HMI tour, the controller post-mortem, and the virtual PLC that runs it again without PLCSIM Advanced. |
| [`m1/`](m1/) · [`m2/`](m2/) · [`m3/`](m3/) · [`m4/`](m4/) | **The earlier milestone archives.** M1's interface contracts and M2's safety spec (paper gates, still the live documents); M3's fixed-equipment I/O loop and M4's forklift commissioning cell — each with its evidence, photos and recorded runs, and each runnable today against the virtual PLC (see their `RUNBOOK.md`). |
| [`agv/`](agv/) | Shared vehicle assets used in place by both eras: the forklift config, I/O translator and STO contactor. |
| [`m5-plc-debug/`](m5-plc-debug/) | The hand-debug chapter: the safety-PLC ↔ Gazebo loop isolated and made to work, script by script. |
| [`bridge/`](bridge/) · [`fleet/`](fleet/) · [`hmi/`](hmi/) · [`sim/`](sim/) · [`viz/`](viz/) · [`plc/`](plc/) | The claude-supervised layered stack — the first M5, still runnable: [its archive and runbook](m5/m5_ver1/README.md). |
| [`docs/`](docs/) | ADRs 0001–0015, interface contracts, safety spec, validation evidence, and the archived planning history — [index](docs/README.md). |
| [`.archive/`](.archive/) | The legacy entry scripts (`demo.sh`, `stack.sh`) the claude-supervised runbook uses. |

## How it got here

M5 was built twice, deliberately. The first build — the layered stack
above — proved the architecture under Claude supervision. The owner then
took the safety loop apart by hand in `m5-plc-debug/` until every PLC
signal was understood, and rebuilt the vehicle in `m5_ver2/` as five
verified steps: e-stop chain, safety scanners, encoder channels, the
three-scanner teleop loop, and finally the autonomy layer. Each step is
a frozen copy with its own proof; the last one is the system this README
describes. The full account, and how to run the first build, is in
[`m5/m5_ver1/`](m5/m5_ver1/README.md) — including the virtual PLC that
stands in for the expired PLCSIM Advanced trial.

M6 then cloned that vehicle into a fleet, one measured sub-milestone at
a time: the two-vehicle foundation, the VDA 5050 agent, the fleet
manager, traffic reservation, the scale-up to four, a floor rebuilt
around what the vehicle's own geometry demands, and an autonomy round —
watchdog, deadlock resolution, a body-on-the-floor protocol. Every gate
that passed and every one that did not is in
[`m6/PROOF.md`](m6/PROOF.md), at the same length either way.
