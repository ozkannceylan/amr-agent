# Step 6 — two forklifts in one warehouse

One world, two vehicles. **`f1`** and **`f2`** each run a full copy of Step 5's
vehicle stack — mux seam, autopilot, `Motor`-gated `cmd_gate`, STO contactor,
commissioning HMI — on its **own topic namespace, its own UDP port pair and
its own Windows writer**. They share the Gazebo world and the machine's CPU,
and nothing else: there is no cross-vehicle channel in M6.1, by design.

Step 6 adds three things to Step 5 and closes one debt:

- **The `VEHICLES` table** in `ipc/status_contract.py` — the single home for
  every per-vehicle difference (ports, topic names, spawn pose, config path).
- **Derived vehicles.** `vehicles/f1/` and `vehicles/f2/` are *generated* from
  `gazebo/forklift_ver2/model.sdf` and `agv/forklift/config.yaml` by
  `tools/instantiate_vehicle.py`. They are gitignored and rebuilt by `deploy`.
  **Never hand-edit them.**
- **A writer that takes `--vehicle`.** One process per PLC, per truck. The
  single-writer rule holds per vehicle; it is not an exception to it.
- **Debt closed:** `cmd_gate` now publishes zeros when it is enabled and its
  *command* input has gone quiet (`CMD_STALE_S = 0.25 s`) — the one fail-open
  silence path step5's final review named.

> Something looks wrong? Read **[Not a bug](#not-a-bug)** before you debug it.

**Evidence: [PROOF.md](PROOF.md) — read its ledger before you trust anything
here.** Gate 1 (RTF), Gate 5 (lifecycle) and the fail-safe half of Gate 4 are
measured. Gates 2, 3, 6 and Gate 4's driving half are **NOT RUN**: they need
the two Windows writers and two hands, and PROOF.md carries a numbered runbook
for each.

## Run order

The PLC goes first, **per vehicle**. A truck cannot be enabled without its own
writer, and each writer serves exactly one truck.

| # | Where | Do this |
|---|---|---|
| 1 | Windows | **Nothing, for M6.1.** Both trucks run `--virtual` (step 7), so no PLCSIM instance is needed. Against a real PLC, only **f1** has one: start `PLC_2` from the Control Panel, download from TIA Portal, CPU in RUN. f2's `PLC_3` is reserved and has never run — no license. |
| 2 | WSL | `cd /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6` |
| 3 | WSL | `./step6.sh deploy` — **regenerates `vehicles/f1/` and `vehicles/f2/` first** (from `gazebo/forklift_ver2/model.sdf` + `agv/forklift/config.yaml`), then freezes `ipc/` + both derived pairs into `deploy/` with a sha256 `MANIFEST`. Prints `deployed 20 files`. **`start` refuses without one.** |
| 4 | WSL | `./step6.sh start` — **9.1 s**, measured: the broker goes up first, the world gets a five-second head start before the vehicle nodes, then one more second before `start` checks that all twenty are still alive. Do **not** source ROS first; the script does it. |
| 4a | Screen | **Three windows:** the **Gazebo window** with the warehouse and both trucks facing each other 6.00 m apart in the south block, and **two HMIs** — `Forklift HMI - f1` and `Forklift HMI - f2`. `start --headless` skips the Gazebo one. |
| 5 | WSL | Read the **twenty** pid lines: `broker`, `world`, then f1's nine (`plc_link cmd_gate cmd_mux field_eval encoder_link sensor_link nav_node vda_agent hmi`), then f2's nine. `WARNING: <name> exited during startup` sends you to that log in `logs/`. A `THE STACK IS INCOMPLETE.` line means stop and read it. |
| 6 | Windows | `cd C:\Users\ozkan\projects\amr-agent` |
| 7 | Windows | `python m5_ver2\step6\windows\step6.py --vehicle f1 --virtual` — **64-bit Python** (pythonnet). A grey **panel** opens, titled `Forklift f1 PLC Control Panel - VIRTUAL F-PLC (model)`; the console prints `streaming PLC state to <wsl-ip>:5110` and `listening for the back scanner on 0.0.0.0:5111`. |
| 8 | Windows | Open a **second** terminal, `cd` again, then `python m5_ver2\step6\windows\step6.py --vehicle f2 --virtual` — same panel titled `Forklift f2 ...`, same two lines on **5120** and **5121**. |
| 9 | Panels | Click **RESET** on f1's panel. Once. Then **RESET** on f2's. Each lamp reads `MOTOR ENABLED`; each HMI turns neutral and reads `Drive enable: ON`. |
| 10a | HMI windows | **Teleop:** leave a truck's radio on `Teleop` and drag *that* HMI's joystick. Only that truck moves. |
| 10b | HMI windows | **Auto:** click `Auto`, click a station dot on that HMI's sketch, press **GO**. Both trucks can be routed at the same time. **STOP** cancels a goal — it is not a brake. |
| 10c | WSL | **Auto, over MQTT:** `python3 m5_ver2/step6/tools/send_order.py f1 S4 --watch` sends the same drive as a VDA 5050 order. Same precondition as **GO**: that truck must be in `Auto`. See [VDA 5050](#vda-5050--orders-over-mqtt). |
| 11 | Panels | Finished: **close both windows**. Each writes its own truck's trip values on the way out. |
| 12 | WSL | `./step6.sh stop` |

**No PLCSIM license? That is the normal case here.** `--virtual` puts
`windows/virtual_fplc.py` in the F-PLC's place, in process, with the measured
semantics (design: `docs/superpowers/specs/2026-08-20-virtual-fplc-design.md`).
Results earned this way are **rig results, not F-program validation** — and f2
has *only ever* been a virtual truck.

**`--headless` when you are timing something.** Rendering here is llvmpipe
software rasterisation. The Gazebo window costs regularity more than speed:
measured over 60 samples on the one-vehicle stack, real-time factor mean
**0.998 headless against 0.806 with the window**, and the window's floor is
0.127 against 0.926. An interval measured with it open is worth less than one
measured without. (Those are step5's numbers, and they compare the WINDOW's
cost, not the stack's. Step 6's own headless figure under M6.1's full
17-pid stack — before the broker and the two VDA agents joined it — is
**0.75**, see [PROOF.md](PROOF.md). The three processes M6.2 added are idle
loops at 10 Hz and 0.5 Hz; the figure has not been re-measured with them.)

**`vehicles/` is generated — regenerate it, do not edit it.** `deploy` runs
`tools/instantiate_vehicle.py --all` before it freezes anything, so the image
can never ship yesterday's derivation. To change a truck, edit
`gazebo/forklift_ver2/model.sdf` or `agv/forklift/config.yaml` and redeploy. To change
a *port*, a *spawn pose* or a *topic prefix*, edit the `VEHICLES` table in
`ipc/status_contract.py` — and remember `step6.sh` repeats the ID list and the
two PLC ports as literals, with a maintenance note at each.

**Close both panels before `stop`, in that order.** `stop` is not a brake —
Gazebo's joint controllers hold their last setpoint, so killing the stack under
a moving truck only leaves it moving (measured once at 14.8 m on a standing
command). The e-stop is the brake.

Neither script touches PLCSIM. Only you stop a PLC, from the Control Panel.

### The Windows panel — buttons, not stdin

`step6.py` is a **tkinter panel**, and there is one per truck. It has no
stdin reader; typing at the console it was launched from does nothing. Every
button below acts on the vehicle its `--vehicle` flag named, and on no other.
Step 4's `es0` / `es1` / `a` / `q` commands are these buttons now:

| Control | Effect | Was |
|---|---|---|
| **PUSH EMERGENCY STOP** | `E-Stop` written `False` | `es0` |
| **RELEASE EMERGENCY STOP** | `E-Stop` written `True`. Does **not** re-enable; see [Not a bug](#not-a-bug). | `es1` |
| **RESET** | 300 ms `Acknowledge` pulse — a rising edge, with the falling edge made by the loop so you cannot hold it on | `a` |
| **ENCODER: OK / FREEZE A / OFFSET A** | encoder fault injection (`OFFSET A` is +400 mm/s, 8x the F-program's 50 mm/s cross-check limit) | `ok` / `fa` / `oa` |
| **Closing the window** | quit through the same trip path an exception takes | `q` |
| `MOTOR ENABLED` / `MOTOR STOPPED` lamp | the PLC's `Motor` output, read back every cycle | (new) |

The buttons show the **state**, not the click: PUSH is drawn down whenever the
PLC is being told the chain is open, however it got there. The panel and the
PLC cycle are two threads on purpose — Tk stops pumping events while a window
is dragged, and the sole writer must not freeze with `Motor` energised.

### Four things `step6.sh` does that are easy to miss

- **`start` runs every process under `setsid`**, so the stack survives closing
  the terminal you started it from. Before that, closing it killed five of six
  and left `gz sim` alone in a live simulator.
- **`start` stamps `VEHICLE` on every child**, and that one word is what turns
  a shared script into f1's or f2's. `env` execs in place, so the pid recorded
  is still the node's own. The world launch is the exception and carries no
  `VEHICLE` at all: it serves both trucks from one process and reads the table
  env-free.
- **`stop` validates the PID file before it signals anything.** Each recorded
  pid must still have `m5_ver2/step6` in its `/proc/<pid>/cmdline`, and each
  candidate must carry this stack's `GZ_PARTITION`. A second stack you have
  running — an M5 demo in partition `m5demo`, or a step5 stack — cannot be
  taken down by it, even after a reboot has recycled the recorded pids. It
  names every pid it sweeps and every pid it kills, then sweeps once more with
  KILL after a two-second grace, because Tk's mainloop ignores TERM.
- **`start` pre-flights UDP :5110 and :5120** — the table's two `plc_port`
  values — and refuses if either is held, naming the vehicle whose port it is.
  Without that guard a second stack takes the PLC link and `plc_link` binds
  nothing, in one warning line among twenty — measured twice while building
  M6.1, when there were seventeen of them, and silent. The guard is pipe-free
  and fail-closed: an `ss` that dies mid-pipe cannot make it fall through, and
  a missing `ss` prints `note: ss not found - the UDP :5110/:5120 and TCP
  :1883 pre-flights are SKIPPED.` rather than pretending it checked. The
  5100/5101 family is deliberately **not** checked — it is step4's and
  step5's, and refusing over it would refuse a start that is perfectly legal
  beside them. The sensor ports (5111/5121) are not checked either, and cannot
  be: they are bound on the *Windows* side. **TCP :1883 joined this guard with
  the broker**, read from its own socket table rather than a shared one — in a
  single `ss -tuln` a TCP socket on :5110 would answer for f1's UDP link and
  refuse a start that is perfectly legal.

## VDA 5050 — orders over MQTT

Each truck runs its own **VDA 5050 2.1.0 client**, `ipc/vda_agent.py`, started
by `step6.sh` beside that truck's nav node. It is the one door into this stack
from outside the machine: an order arrives over MQTT, the agent decides whether
the truck may take it, and if it may, hands `nav_node` the same kind of route
the HMI's **GO** button produces. **Owner ruling 2026-08-21: full-route orders
from day one** — master control sends `nodes` + `edges`, the vehicle drives the
released nodes in sequence and does not re-route.

**This channel is reporting and process command only.** `state.safetyState`
*narrates* what the F-model already did; nothing published here can stop a
truck, and nothing here is in the safety chain. A broker that goes away is
degraded mode, handled as a **controlled stop through the normal chain** — the
agent publishes the empty goal, keeps the order, and re-issues the remaining
nodes from the truck's current pose when supervision returns. The brake is
still the e-stop.

### The two things a fresh checkout does not have

Neither is committed, both are per-user, and `start` refuses without the first:

```bash
bash tools/install_broker.sh                             # WSL, no sudo
pip3 install --user --break-system-packages paho-mqtt    # 2.1.0, measured
```

`install_broker.sh` `apt-get download`s mosquitto and the four libraries its
binary demands, then unpacks them under `~/.local/mosquitto-vendored`. Nothing
goes system-wide and the binary is not in git — that script is how it
reproduces. `step6.sh` starts it as the stack's first process on
**`127.0.0.1:1883`**, localhost-only and anonymous, which is what a
config-less mosquitto 2.x does by default and is the posture M6.2 wants.
**M6.3 moves the broker to the fleet side**, where a broker belongs: one for
every truck, on a machine that is not a vehicle.

`--break-system-packages` is neither optional nor carelessness. Ubuntu noble
marks this interpreter externally-managed (PEP 668), and a vehicle node that
imports **both** `rclpy` and `paho` cannot live in a plain venv. The flag only
bypasses the marker; the install still lands in `~/.local` and touches no OS
site-packages. The code is written against paho **2.x** — it names
`CallbackAPIVersion.VERSION2` explicitly, because 2.x otherwise defaults to
the 1.x callback signatures with a warning and hands the callbacks the wrong
argument count on the first reconnect.

### The topics

The root is VDA's own, `uagv/v2/<manufacturer>/<serialNumber>`, with this
project's manufacturer and the vehicle id as the serial number:

```
uagv/v2/amragent/f1/…        uagv/v2/amragent/f2/…
```

| Topic | Direction | What rides on it |
|---|---|---|
| `order` | in | one full route: `nodes` + `edges`, all released. Accepted only in AUTOMATIC, only when nothing is executing, and only at `orderUpdateId` 0 — updates land with M6.3. A re-delivery of the order already held is ignored in silence (VDA's own rule); everything else refused comes back as an `orderError` on `state`. |
| `instantActions` | in | `cancelOrder`, `stateRequest`, `factsheetRequest`. Anything else is answered `FAILED` plus an `unsupportedAction` error — the factsheet is the list. |
| `state` | out | every 2 s, and immediately on every event worth knowing: pose, `driving`, `operatingMode`, `nodeStates` draining, `lastNodeId` advancing, `errors[]`. |
| `connection` | out | `ONLINE` on connect, retained; the LWT makes it `CONNECTIONBROKEN` if the agent dies. |
| `factsheet` | out | on connect and on request, retained. |

### Sending one, until M6.3 exists

There is no fleet manager yet, so `tools/send_order.py` is master control's
hand — **M6.3 deletes it**:

```bash
python3 m5_ver2/step6/tools/send_order.py f1 S4 --watch
```

It reads that truck's pose off the truck's own `state` (no ROS: the
single-writer and one-stack rules stay unbroken), plans with the same
`route.plan_route` the HMI uses, and publishes the result as an order — so the
route the "fleet" sends is the route the vehicle would have planned, and
full-route following is exercised without inventing a second planner.
`--watch` then prints the vehicle's own account once a second until `ARRIVED`.
Station ids are `stations.py`'s: `S1`…`S10`.

**The truck must be in AUTOMATIC**, exactly as **GO** requires — the writer
running, the panel RESET, that HMI on `Auto`. Sent to a truck that is not, the
order is refused at the door and the vehicle says so rather than going quiet:

```
sent o-bf8b6e46 to f1 -> S4 (4 nodes, arrive 0.25 m)
  [WARN] [vda_agent]: order rejected: vehicle not in AUTOMATIC   (logs/vda_agent_f1.log)
  state.errors[]: orderError WARNING "vehicle not in AUTOMATIC" -> orderId o-bf8b6e46
```

That error rides the one `state` published at the rejection and is not a
standing one, so it shows up in `--watch`'s next line and not after it. With
no order executing there is then nothing for `--watch` to wait for and it
never reaches `ARRIVED` — Ctrl-C it. (Known, accepted: M6.3 deletes this
tool.)

### What the factsheet declares

Only what is implemented — it is a *truthful* factsheet, not an aspirational
one. Three instant actions, `cancelOrder`, `stateRequest` and
`factsheetRequest`; `order.edge.maxSpeed` declared `NOT_SUPPORTED` (parsed,
not enforced, until M6.4); pause, charging and `initPosition` absent because
this vehicle has no pause pair, no battery reality, and a pose that is
already ground truth.

The geometry is measured off the truck's own model rather than rounded off a
datasheet, and each number carries its derivation in `ipc/vda_messages.py`:
`width` 0.90 m is the chassis box, `length` 2.735 m runs counterweight face
to fork tip, `heightMax` 2.20 m is the carriage at full mast travel, and
`speedMax` is read out of *that vehicle's* `config.yaml`
(`traction_speed_max_mps`, 1.5) — so a per-vehicle limit change reaches the
fleet's view of the truck through the same file that changes the truck.
**Three fields are labelled sim stubs** and say so in the source, because
neither file knows them: `maxLoadMass`, `accelerationMax`, `decelerationMax`.

**The field-by-field contract is [`docs/interfaces/vda5050-subset.md`](../../docs/interfaces/vda5050-subset.md)**,
amended 2026-08-21 for M6.2: which fields are used, which are deliberately
omitted, and why this project's error names are camelCase.

---

# Inherited reference — Step 5's manual, below

**Everything from here down came across with `cp -r step5 step6` and describes
the ANCESTOR.** The mechanisms are step6's — the mux seam, the arrival radius
rule, the sketch panel, the field contract, "Not a bug" — but the NAMES are
step5's. Wherever the text below says:

| It says | Step 6 means |
|---|---|
| `/forklift/plc/status`, `/hmi/cmd_vel`, `/vehicle/cmd_vel`, … | `/f1/...` and `/f2/...`, one set per truck |
| `5100` / `5101` | `5110` / `5111` for f1, `5120` / `5121` for f2 |
| `step5.sh`, `step5.py`, `m5_ver2/step5/` | `step6.sh`, `step6.py --vehicle <vid>`, `m5_ver2/step6/` |
| `GZ_PARTITION=step5`, `ROS_DOMAIN_ID=95` | `step6`, `96` |
| "nine pids" | twenty (seventeen before M6.2) |
| `agv/forklift/config.yaml` as the vehicle's config | `vehicles/<vid>/config.yaml`, derived from it |

**Do not copy a command out of the text below and run it.** The run order at
the top of this file is the one that is current. Nothing below has been
re-measured on this tree — the numbers in *Measured, so you know what good
looks like* are step5's, on one vehicle, and `PROOF.md` is the only ledger for
step6's own claims.

## How a command reaches the wheels

```
  HMI joystick ──▶ /hmi/cmd_vel ─┐
                                 ├─▶ cmd_mux ──▶ /vehicle/cmd_vel ──▶ cmd_gate ──▶ sto_contactor ──▶ plant
  nav_node ──────▶ /auto/cmd_vel ┘   (mode)                            (Motor,
                                                                        staleness,
                                                                        V_Limit)
        ▲                                    ▲
        │ /hmi/mode (latched)                │ /plc/status
        └────────── HMI ─────────────────────┘
```

**`cmd_mux` is one seam and one decision: which human-side source drives the
vehicle.** Below the autonomy, above the gate. Teleop is the floor — no mode
yet, an unreadable mode word, any surprise at all and the joystick wins,
because a wrong pick is still a gated, clamped, zeroable command and safety
must never depend on this file choosing well. The one exception is a
*selected* autopilot that went **silent**: forwarding the joystick then would
hand a moving truck to whoever happens to hold it, and forwarding the last auto
command would be a dead man's setpoint, so the mux emits zeros — and keeps
emitting them at `ZERO_HZ`, because `cmd_gate` forwards on receipt and a
stopped stream leaves the plant holding its last setpoint.

**`nav_node` + `nav_core` + `follower` + `route` are the autopilot.** `route`
plans over a fixed graph of aisle centrelines (main aisle `y = 5.65`, dock
aisle `y = -5.5`, three connectors at `x = -12.5 / 0.0 / +12.0`, one short spur
per station) with plain Dijkstra, so a route that exists drives aisle middles
by construction. `follower` is pure geometry: pure pursuit with the true
target distance as its denominator, a speed policy of stacked bands (slowest
wins), a ±35° lidar sector that follows the *direction of travel*, and a
reverse phase for backing out of spurs. `nav_core` holds the states the
operator's screen shows — `IDLE`, `EN-ROUTE`, `HOLD`, `SAFETY-STOP`,
`ARRIVED` — and none of them is read by the safety chain. `nav_node` is wiring
only: pose from the bridged ground-truth odometry (owner ruling: the nav lidar
**guards**, it does not localise), both sector minima per scan, and a stale
`/plc/status` treated as `Motor` False.

**SAFETY-STOP holds the route.** A `Motor` drop mid-drive is a latched ESTOP1
demand; the truck stays where the stop left it and the route is still the
route. When `Motor` returns — one RESET on the panel — driving resumes without
a re-plan and without a second GO. A re-plan from the same pose would produce
the same polyline, and a re-click ritual would only teach the operator to
automate the click.

### Topics

| Topic | Type | From -> To | Notes |
|---|---|---|---|
| `/hmi/cmd_vel` | `Twist` | hmi_node -> cmd_mux | 20 Hz for the life of the window. Not standard `Twist` — see the field contract below. |
| `/auto/cmd_vel` | `Twist` | nav_node -> cmd_mux | 20 Hz (`TICK_HZ`), zeros included |
| `/vehicle/cmd_vel` | `Twist` | cmd_mux -> cmd_gate | **the one seam.** Everything the plant ever sees passed through here. |
| `/hmi/mode` | `String` | hmi_node -> cmd_mux, nav_node | **latched: TRANSIENT_LOCAL, depth 1.** `"teleop"` or `"auto"`. |
| `/auto/goal` | `String` | hmi_node -> nav_node | station id (`"S7"`), or `""` for cancel |
| `/auto/state` | `String` (JSON) | nav_node -> hmi_node | 10 Hz (`STATE_EVERY = 2`). Carries `state`, `goal`, `note`, `route`, `pose`, `reversing`, `arrive_m`, `guard_min`. |
| `/plc/status` | `String` (JSON) | plc_link -> cmd_gate, hmi_node, nav_node | 20 Hz, republished even when the link is dead |
| `/forklift/gz/odom` | `Odometry` | bridge -> nav_node, hmi_node | measured **19.87 - 20.00 Hz** |
| `/forklift/gz/scan_nav` | `LaserScan` | bridge -> nav_node | measured **9.86 - 10.02 Hz** |

`/hmi/mode` **must** be published TRANSIENT_LOCAL, and this is not a
preference. `cmd_mux` and `nav_node` both subscribe TRANSIENT_LOCAL so a node
started after the window still learns the current mode; a **VOLATILE publisher
is incompatible with those subscriptions and delivers nothing at all** —
measured in Task 6, where the Auto radio silently did nothing. The same rule
bites from the command line: a `ros2 topic pub --once` latched publisher dies
before a late subscriber matches, and its retained sample dies with it. Use
`-t 3 -w 2`, or better, use the HMI, which is the real path and publishes
durably for the life of the window.

The topic names above are the five `status_contract.py` owns plus
`/plc/status`. The two gz source names are **not** there: `config.yaml` owns
`topics.gz_odom` and `topics.gz_scan_nav`, and the launch file and `nav_node`
both read them from it (owner ruling 2026-08-12). One name, one source.

## The sketch panel

The right half of the HMI window is a 450 x 300 px plan view at 15 px/m,
**drawn from `stations.py`, not from the SDF** — the same rectangles the router
avoids and the same station poses the world paints, with `test_stations_sdf.py`
tying all three together so they cannot drift apart silently.

- **Ten station dots**, labelled `S1`..`S10`. Click within 12 px of one to
  select it; it turns orange.
- **Teleop / Auto radios.** Leaving Auto also publishes an empty goal, so the
  cancel and the mode change cannot disagree for longer than one message.
- **GO** sends the selected station id. **STOP** sends `""`, which `nav_core`
  reads as "cancelled" and parks. **STOP is the goal cancel, not a brake** —
  the e-stop is the brake.
- **The green triangle** is the truck; its nose is the travel direction (the
  forks, i.e. model yaw + π), from `/forklift/gz/odom`.
- **The dashed green line** is the planned route, straight from `/auto/state`.
- **The status line** under the buttons reads `mode <teleop|auto>  <state>
  <goal>` plus the autopilot's note when there is one.

The ten stations, with the arrival radius each one declares:

| id | name | pose (x, y) | spur | `arrive_m` |
|---|---|---|---|---|
| S1 | HOME | (-3.0, -5.50) | 0.00 (on the dock aisle) | 0.25 |
| S2 | CHARGE-1 | (-9.8, -6.60) | 1.10 | **0.80** |
| S3 | CHARGE-2 | (-7.4, -6.60) | 1.10 | **0.80** |
| S4 | DOCK-DOOR | (6.0, -8.00) | 2.50 | 0.25 |
| S5 | CONVEYOR | (11.6, 5.65) | 0.00 (on the main aisle) | 0.25 |
| S6 | PICK-A-W | (-8.0, 6.50) | 0.85 | **0.80** |
| S7 | PICK-A-E | (8.0, 6.50) | 0.85 | **0.80** |
| S8 | PICK-B-W | (-8.0, 4.80) | 0.85 | **0.80** |
| S9 | PICK-B-E | (8.0, 4.80) | 0.85 | **0.80** |
| S10 | PICK-B-S | (-6.0, -2.50) | 3.00 | 0.25 |

S5..S10 park the truck **centre** exactly 2.400 m off the face they serve. That
is a scanner dimension, not a style: the side safety scanners sit ~0.8 m
fork-ward of centre, so a fork-first approach puts them 0.8 m closer to the
face than the pose suggests. Measured 2026-08-13, a 1.79 m centre standoff
parked the right scanner **0.990 m** off rack B and tripped the 1.0 m case-1
protective field with the truck exactly on its lane. `2.4 = 0.8 scanner offset
+ 1.0 protective field + 0.2 field hysteresis + 0.4 pursuit residual`, and
`test_route.py` pins it so a station cannot drift back inside the field.

## Not a bug

Everything in this table is deliberate. None of it should be "fixed".

| What you see | Why it is correct |
|---|---|
| **The HMI window opens RED — "E-Stop Active", "Drive enable: OFF" — before `step5.py` is running.** This is the single most likely thing to be misread as a fault. | Nothing is publishing `/plc/status` yet. `hmi_node.py`, `cmd_gate.py` and `nav_node.py` each apply the same staleness rule (`STATUS_STALE_S`), and a display that has been told nothing shows the **safe** state, not a comfortable one. A lamp reading "E-Stop Inactive" before the PLC has said anything would be claiming a healthy chain on no evidence. It turns neutral within a tick of `step5.py` starting. |
| **The sketch's status line reads `auto: no data` at startup, and after every STOP.** | Same rule, one topic further out. `/auto/state` is published only while `nav_node` has a pose, so a silent or stale topic means the panel has been told nothing about the autopilot — and it says so instead of showing the last thing it heard. It fills in the moment nav speaks. |
| **`Motor` is OFF at a fresh start with nothing tripped, and one RESET is required before anything moves.** | `ACK_NEC = true` in the ESTOP1 blocks: one `Acknowledge` rising edge is required after PLC startup before `Motor` can ever be True. |
| **After every stack restart you need one RESET, even though nothing was pressed.** | Bouncing the WSL stack silences port 5101, so `step5.py` stops receiving field verdicts and — correctly — writes `PF_OSSD` and its `_right`/`_left` counterparts False in its fail-safe direction. That is a demand, and a demand latches. Expected, every time. The same happens on the way out of every `step5.py` run: closing the window writes `E-Stop` and all six scanner inputs False. |
| After **RELEASE EMERGENCY STOP** the lamp goes neutral **but the forklift stays stopped** and the line still reads `Drive enable: OFF`. | The ESTOP1 latch. A demand latches; the input returning to healthy does not re-enable it. That disagreement between the lamp and the enable line *is* the latch made visible, and showing it is the point. RESET restores motion, on the next command message — invisible, because both the HMI and the autopilot publish continuously. |
| **GO does nothing and the status line says `goal refused: not in auto mode`.** | The radio is on Teleop. `nav_core.on_goal` refuses the goal **and does not store it**, so switching to Auto afterwards cannot arm a latent goal — you press GO again. Pinned by `test_goal_in_teleop_mode_is_refused`. |
| **`start` prints a loud `WARNING: deploy is STALE`.** | A feature, and the whole point of `deploy`. The vehicle runs the frozen copy in `deploy/`; editing a file in `ipc/` changes **nothing** until you redeploy, which is exactly what a real vehicle does. The banner is a warning and not a refusal, because watching that happen is the exercise. Rerun `step5.sh deploy` to ship. |
| **The truck creeps near racking, well under the 0.7 m/s cruise.** | `V_Limit`. With the back warning field occupied the standard program computes 300 mm/s instead of 1500, and `nav_core` obeys it at the source rather than letting the gate clamp a plant that is still doing 0.7. Step 3 measured the trap this avoids: a latched stop 0.68 s after enable, driving 0.5 m/s with racks 1.75 m away. How the **right/left** warning fields compose into `V_Limit` is TIA-side and **unmapped** — two live observations contradict a back-only rule (see PROOF.md, open item 4). The practical effect is this creep. |
| **Auto arrivals are 0.80 m at six stations and 0.25 m elsewhere.** | Geometry, not tolerance creep. S6..S9 sit on 0.85 m spurs entered perpendicular, and S2/S3 on 1.1 m spurs; the truck must turn 90° and stop in less floor than its own turning circle. Measured 2026-08-13 at S7 with a single tight radius: the truck overshot, could not converge, and settled into a stable **limit cycle at 0.643 - 0.742 m** — its minimum turning radius, ~0.69 m — lapping indefinitely. A vehicle cannot reach a point inside its own turning circle. `stations.py` now declares the honest number per station and `test_route.py` pins the **rule** (`0.80 if 0.0 < spur < 2.0 else 0.25`), not the list. Tightening it needs longer spurs or a back-in maneuver, not a gain. |
| **A box spawned into the running world is invisible to the guard — and to all three safety scanners.** | Measured on this machine: runtime-spawned models return nothing from any `gpu_lidar` here. It is a platform property, not a Step 5 defect. Obstacle work must pre-seed geometry into the world file. Obstacle HOLD as a capability was descoped by the owner on 2026-08-13; PROOF.md records the parked design and its evidence. |
| Steering still responds while traction is dead (teleop). | Deliberate. If the joystick went dead too, you could not tell a safety stop from a broken HMI — which is the one thing this window exists to distinguish. `angular.z` is therefore a steer *angle*, commanded directly. |
| **The joystick knob greys out and moves nothing in Auto.** | Display only. The mux ignores `/hmi/cmd_vel` while auto is selected, so the knob would be lying if it looked live. Switch the radio back to Teleop and it is live again on the next message. |
| `forklift_io` logs `waiting for source data: joint_states=False, odom=False` every 5 s, forever — **even though Step 5 bridges odometry.** | Two different names. Step 5 bridges `topics.gz_odom` (`/forklift/gz/odom`), which is what `nav_node` and the sketch consume; `forklift_io` subscribes to `topics.odom` (`/forklift/odom`), the renamed ROS name nothing publishes here. Joint states remain deliberately unbridged — no consumer. The warning gates only two derived state scalars and the fork target seed, never the traction or steer command path. |
| **The Gazebo window is slow, and the real-time factor in its bottom bar sits well under 1.** | Rendering on this machine is llvmpipe *software* rasterisation. WSLg exposes `/dev/dri`, OGRE binds it over EGL, and Mesa then falls back to `kms_swrast` — measured, there is no GPU here (`sim/setup/WSL_ENVIRONMENT.md` §4.7). A headless run of this same world holds ~1.0. Nothing in the command path reads the clock rate, so this costs appearance and not correctness. |
| No Gazebo window appears after `start --headless`, or after `ros2 launch` run by hand. | Correct: `--headless` passes `gui:=false`, which is also the launch file's own default, and the server then runs `-s --headless-rendering` — server only, no client process. The HMI is the only window. The spawn is confirmed by `Entity creation successful.` in `logs/world.log`. |
| `logs/plc_link.log`, `logs/cmd_gate.log` and the rest end in an `rclpy.executors.ExternalShutdownException` traceback. | That is what a clean SIGTERM looks like in these nodes — `step5.sh stop` sent it. It is the house pattern in `agv/`, and it appears *after* the node's normal startup line, not instead of it. |
| `logs/world.log` is full of yellow `XML Element[gz_frame_id] ... not defined in SDF` and `libEGL warning: egl: failed to create dri2 screen`. | The first comes from parsing `model.sdf`; the second is Mesa refusing the DRI device and falling back to software, and it appears on **both** paths — with the GUI up it arrives from the client too, alongside `OGRE EXCEPTION ... Couldn't open X display` and a QML binding-loop warning. All of it is a property of this machine, not of this run, and nothing in the command path reads it. |
| The vehicle guard ignores a narrow band of bearings right behind the fork end. | `SELF_MASK` — contour masking, the same feature real nav scanners ship. The nav lidar renders the truck's **own two mast uprights** inside the travel sector; before the mask `sector_min` returned 1.287 m on every scan and the autopilot held forever. The cost is stated in full at the constant: an obstacle inside an ~8° sliver under 1.6/1.7 m is invisible to *this* guard. The uprights shadow those bearings anyway, and the PLC's protective fields are unaffected. |

## The `/hmi/cmd_vel` field contract

**This is not standard `Twist`.** It is a deliberate deviation, stated in the
docstring of `hmi_node.py`, `cmd_gate.py` and `cmd_mux.py`, and `/auto/cmd_vel`
and `/vehicle/cmd_vel` carry the same two fields with the same meanings.

| Field | Carries | Range | Limit comes from |
|---|---|---|---|
| `linear.x` | traction speed **[m/s]** | ±1.50 | `limits.traction_speed_max_mps` |
| `angular.z` | steer **angle [rad]** — *not* a yaw rate | ±1.31 | `model.steer_limit_rad` |

Why an angle: the bicycle relation `delta = atan(L*w/v)` is undefined at
`v = 0`, so a proper `Twist` would leave a stopped forklift unsteerable —
exactly the state an e-stop test puts it in, and exactly when you need to be
able to tell a safety stop from a dead joystick. Both limits are read from
`agv/forklift/config.yaml` at startup, never copied as literals.

Dragging right steers right, which is a **negative** `angular.z` under REP-103.

**Signs, derived once and locked by tests.** Model yaw 0 points the forks at
world -x, so the *travel* heading is model yaw + π and forward traction is a
**negative** `linear.x`. Positive `angular.z` is a driver-right turn. That is
why `follower.steer()` carries a leading minus, and why a reversing command is
the only positive `linear.x` the autopilot ever emits.

## CONFIG

Verified against the code at `fb976b0`. Each constant has exactly one home.

### The autopilot — `ipc/follower.py`

| Name | Value | Note |
|---|---|---|
| `LOOKAHEAD_M` | `1.2` | pure-pursuit walk along the polyline |
| `LD_MIN_M` | `0.35` | **denominator floor.** The pursuit divides by the *true* distance to the target, not by the constant; on a long leg they are the same number (pinned by a test) and they differ only on an end-clamped target, which was the whole bug. Below this floor the atan2 saturates toward the mechanical stop anyway, and zero would be undefined. |
| `WHEELBASE_M` | `1.2` | front-steer tricycle, drive wheel to rear axle |
| `CRUISE_MPS` | `0.7` | |
| `CORNER_MPS` | `0.3` | applies above `CORNER_STEER_RAD` |
| `APPROACH_MPS` | `0.25` | applies inside `APPROACH_ZONE_M` |
| `APPROACH_ZONE_M` | `2.0` | final-leg distance where `APPROACH_MPS` applies |
| `ARRIVE_M` | `0.25` | the **default and the tight case**. A station may declare its own — see the `arrive_m` rule below. |
| `CORNER_STEER_RAD` | `0.3` | |
| `GUARD_SLOW_M` | `3.0` | **deliberately outside the case-1 warning field (2.5 m)**, so on a straight aisle the lidar slows the truck to the PLC's creep ceiling *before* `WF_Clear` can drop `V_Limit` under a truck still doing 0.7 m/s. The PLC keeps the last word; this policy exists so it rarely has to say it. |
| `GUARD_HOLD_M` | `1.5` | full stop, steer included |
| `GUARD_SLOW_MPS` | `0.3` | = the PLC creep ceiling, 300 mm/s |
| `GUARD_HALF_ANGLE_RAD` | `radians(35.0)` | half-width of the guard sector, centred on the **direction of travel** — π forward, 0 reversing |
| `REVERSE_MPS` | `0.25` | backing out is a walk |
| `REVERSE_ENTER_RAD` | `2.0944` (120°) | enter the reverse phase above this bearing error |
| `REVERSE_EXIT_RAD` | `1.3090` (75°) | leave it below this. **The 45° dead band is what stops the phase chattering** at a corner, where the target sits near the perpendicular. |
| `SELF_MASK` | `((-9.0, -1.0, 1.6), (-31.0, -23.0, 1.7))` | `(travel-offset lo°, hi°, ceiling m)` windows. A return inside a window at or under its ceiling is the truck's own mast, not the world. Probed live 2026-08-13: near upright -3..-6° @ 1.287-1.292 m, far -26..-29° @ 1.447-1.483 m — 2-3° and 1.9-3.1° of margin respectively. Pass `self_mask=()` to see the raw scan. |

### The arrival radius rule — `ipc/stations.py`

`arrive_m` is **geometry, not tolerance creep**. Each station's spur is the
distance from its own aisle to its pose, and the rule is:

```
arrive_m = 0.80 if 0.0 < spur < 2.0 else 0.25
```

`test_route.py::test_arrival_radius_follows_the_spur_length` computes each spur
from `STATIONS` and `route.MAIN_Y`/`DOCK_Y` and asserts that rule, so it pins
the **rule and not the list**: a station that moves re-derives its own radius,
and a station that moves and does not is a test failure. The predicate is
`0.0 < spur` and not `spur >= 0` on purpose — S1 and S5 sit *on* their aisle,
need no turn at all, and keep the tight radius.

### The autopilot's ROS shell — `ipc/nav_node.py`

| Name | Value | Note |
|---|---|---|
| `TICK_HZ` | `20.0` | one command per tick, zeros included |
| `STATE_EVERY` | `2` | `/auto/state` every 2nd tick -> 10 Hz |
| `SENSOR_STALE_S` | `0.5` | odom at 20 Hz and scan at 10 Hz: 0.5 s is dead. A stale **pose** parks the autopilot (zeros flow); a stale **scan** reads as `guard_min 0.0`, the HOLD band — not as a clear road. |

Both sector minima are computed on **every** scan, forward and reverse,
because the phase is decided after the callback runs: reducing the scan to one
number there would be guessing which way the truck is about to go.

### The mux seam — `ipc/cmd_mux.py`

| Name | Value | Note |
|---|---|---|
| `ZERO_HZ` | `10.0` | the floor: while auto is selected the mux publishes on every tick, so a silent autopilot's zeros still **flow**. `cmd_gate` forwards on receipt, and a stopped stream would leave the plant holding its last setpoint. |

The staleness window on `/auto/cmd_vel` is `STATUS_STALE_S`, borrowed rather
than reinvented. Teleop mode deliberately keeps Step 4's semantics exactly, no
staleness rule: the HMI publishes at 20 Hz for the life of the window, and the
e-stop is the brake.

### The chain from Step 4, unchanged

| File | Name | Value | Note |
|---|---|---|---|
| `windows/step5.py` | `PLC_INSTANCE` | `"PLC_2"` | error `-4` (`DoesNotExist`) = instance not running, or the name differs |
| | `API_DLL_DIR` | `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0` | |
| | `UDP_TARGET` | `None` | `None` → first token of `wsl.exe hostname -I`. WSL2 here is **NAT, not mirrored**: `127.0.0.1` does not reach the guest, and the guest IP is reassigned on every WSL restart. A string overrides the discovery. |
| | `UDP_PORT` / `SENSOR_PORT` | `5100` / `5101` | out to WSL / in from WSL |
| | `CYCLE_S` | `0.02` | 20 ms loop, so ~50 Hz on the wire. The port map's "20 Hz" is `plc_link`'s republish rate, not this one. |
| | `SENSOR_STALE_S` | `0.40` | this writer's own timeout on 5101. Silence here writes the field inputs False — which is why a stack bounce always costs one RESET. |
| | `ACK_PULSE_S` | `0.30` | |
| | `ENC_OFFSET_MM_S` | `400` | the `OFFSET A` fault, 8x the F-program's 50 mm/s cross-check limit |
| | `STATUS_EVERY` / `GUI_REFRESH_MS` | `10` / `100` | status text refresh, ~5 Hz / panel redraw |
| `ipc/plc_link.py` | `BIND_ADDR` | `"0.0.0.0"` | |
| | `UDP_PORT` | `5100` | |
| | `STALE_S` | `0.28` | **this node's own UDP timeout.** Deliberately not a multiple of the 0.05 s tick: 5 ticks must not trip and 6 must, with margin at both ends. Do not round it to 0.25 or 0.30. |
| | `PUBLISH_HZ` | `20.0` | it republishes at 20 Hz even when the link is dead — silence here would be a moving vehicle |
| `ipc/status_contract.py` | `STATUS_TOPIC` | `"/plc/status"` | |
| | `HMI_CMD_TOPIC` | `"/hmi/cmd_vel"` | moved here in Step 5 so the mux does not become a third spelling |
| | `VEHICLE_CMD_TOPIC` | `"/vehicle/cmd_vel"` | cmd_mux -> cmd_gate, the one seam |
| | `AUTO_CMD_TOPIC` / `AUTO_GOAL_TOPIC` / `AUTO_STATE_TOPIC` | `"/auto/cmd_vel"` / `"/auto/goal"` / `"/auto/state"` | |
| | `MODE_TOPIC` | `"/hmi/mode"` | with `MODE_TELEOP` / `MODE_AUTO` = `"teleop"` / `"auto"` |
| | `FIELDS_TOPIC` / `ENCODERS_TOPIC` / `SCAN_TOPIC` | `/forklift/safety/fields`, `/forklift/safety/encoders`, `/forklift/gz/safety_scanner_{}/measurement` | |
| | `STATUS_STALE_S` | `0.25` | **the ROS-side timeout on `/plc/status`**, shared by the gate, the HMI and now the autopilot, so the screen and the vehicle stop trusting a silent status at the same instant |
| | `V_LIMIT_FULL_MM_S` / `V_LIMIT_CREEP_MM_S` | `1500` / `300` | the only two values the F-program computes. An unreadable `V_Limit` becomes the **creep** ceiling — not knowing means assuming the most demanding permission. |
| `ipc/cmd_gate.py` | `ZERO_HZ` | `10.0` | load-bearing on the 0.45 s budget — do not lower it. The gate now subscribes `/vehicle/cmd_vel`, not `/hmi/cmd_vel`. |
| `hmi/hmi_node.py` | `PUBLISH_HZ` | `20.0` | |
| | `SPIN_MS` | `4` | tkinter's pump period. Throughput only: at 20 ms `/hmi/cmd_vel` measured 16.5 Hz against a declared 20. |
| | `KNOB_RADIUS_PX` | `100.0` | |
| | `LAMP_RED` / `LAMP_NEUTRAL` | `#c62828` / `#455a64` | |
| `hmi/map_panel.py` | `SCALE` | `15.0` | px per metre: 30 x 20 m -> 450 x 300 px |
| | `PICK_RADIUS_PX` | `12.0` | click tolerance on a station dot |
| `ipc/route.py` | `MAIN_Y` / `DOCK_Y` | `5.65` / `-5.5` | the two aisle centrelines |
| | `MAIN_X` / `DOCK_X` / `CONNECT_X` | see the file | node x-positions; several repeat station x-coordinates because a spur must land on a node, not between two |
| `step5.sh` | `GZ_PARTITION` | `step5` | exported to every child; it is what scopes `stop`. Overridable from the environment. The GUI client inherits it, which is what makes it show *this* world rather than an empty scene. |
| | `ROS_DOMAIN_ID` | `95` | does **not** isolate Gazebo — gz transport is not DDS |
| | `GUI` | `true` | `start` opens the Gazebo window; `start --headless` sets it false. `gazebo/step5_world.launch.py` declares `gui` with the opposite default (`false`), so a bare `ros2 launch` is unchanged. |
| | `DEPLOY` | `m5_ver2/step5/deploy` | the "image". `deploy` rebuilds it from scratch (`rm -rf` first), lays it out at **source depth** so every relative path inside still resolves, and writes a `MANIFEST` of sha256 sums plus the source git rev and a timestamp. `start` refuses without it and warns loudly when the source has moved on. |
| | UDP :5100 pre-flight | fail-closed | `case` match on `*:5100[!0-9]*` — the **non-digit** is what tells `:5100` from `:51000`, and a `grep ':5100 '` trailing-space pattern misses a line ending exactly at the port. Measured. |

**`STALE_S` (0.28), `STATUS_STALE_S` (0.25), `SENSOR_STALE_S` (0.5 in
`nav_node`, 0.40 in `step5.py`) are four different constants on four different
clocks.** They are not interchangeable, and merging any two breaks a timing
budget. `is_stale()` therefore takes its window as a **required** argument: a
default would quietly be one budget for a caller that meant another.

No ROS or gz topic name is a literal anywhere in Step 5 outside
`status_contract.py`; every name `config.yaml` owns is read from `config.yaml`.

## Deploy: what ships and what does not

`step5.sh deploy` freezes **`ipc/` + `agv/forklift/config.yaml`** — 13 files —
into `deploy/`. Owner ruling 2026-08-12: Docker Desktop cannot pass DDS across
its VM here, so the container is simulated; the **boundary** it draws is the
one a real image would have.

**The HMI is deliberately not deployed, and that divergence is the
deliverable.** `hmi/hmi_node.py` and `hmi/map_panel.py` run from the **source
tree** — they are the operator's panel on a commissioning laptop, not software
on the industrial PC. Every vehicle node runs from the frozen copy.

The honest consequence, stated because it will bite someone: **an edit to
`ipc/status_contract.py` changes the HMI immediately and the vehicle not at
all.** The HMI imports the source module; `cmd_gate`, `cmd_mux`, `nav_node`
and the rest import the deployed one. A contract change made without a
redeploy is exactly the kind of divergence the STALE banner exists to catch —
so read the banner, and redeploy.

## How to see the torque removal

The HMI deliberately shows lamps and no more, so the second stage of the stop —
`sto_contactor.py` opening its latch at the plant's own inputs — is checked
from the command line instead:

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=step5 ROS_DOMAIN_ID=95
ros2 topic echo /forklift/safety/torque_off_applied
```

`True` while inhibited, `False` when the drive is enabled. The terminal the
model actually listens on is `/forklift/gz/actuator/traction_cmd` — echo that
one to see the command reaching the plant.

Two habits, both learned the expensive way on this stack:

- **Name the type when you echo `/auto/state`:**
  `ros2 topic echo /auto/state std_msgs/msg/String`. Type discovery under a
  short timeout is unstable here.
- **Raise the truncation:** `--truncate-length 3000`. The default 128
  characters cuts `/auto/state` off before `guard_min`, which blinded a whole
  round of measurement. And a YAML `data: ` with nothing after it parses as the
  string `"None"`, so a cancel must be sent as `"data: ''"`.
- **Keep instrumentation to one subscriber per run.** A burst of `ros2 topic
  echo` processes starting produces a DDS discovery storm that has stalled the
  5101 link for ~150 ms — long enough for the Windows writer to take its
  fail-safe direction and latch ESTOP1 (PROOF.md, open item 2).

## Measured, so you know what good looks like

The autonomy rows were measured live against `PLC_2` on 2026-08-13 and are
sourced in [PROOF.md](PROOF.md). **The teleop-side rows below the deploy row
are carried from the Step 1 chain** — the command path they measure is
unchanged by Step 5, but they have not been re-taken on this tree, and a
re-measurement should say so.

| Event | Measured |
|---|---|
| `/hmi/cmd_vel` publish rate | 20.01 Hz |
| `/forklift/gz/odom` after the bridge | 19.87 - 20.00 Hz |
| `/forklift/gz/scan_nav` after the bridge | 9.86 - 10.02 Hz |
| Motor enable from cold | one RESET after startup -> `Motor` True; `estop_healthy`, `case` and `V_Limit` stream on 5100 at ~50 Hz |
| Right/left ESTOP1 re-arm after a stack bounce | a **single** Acknowledge cleared both; `Motor` returned True (the `ACK`-wired-false worry is not borne out) |
| Auto arrival, aligned station (S10) | **0.216 m** and **0.245 m**, Motor-false samples **0 / 637** |
| Auto arrival, short-spur station (S7 / S9 / S6) | **0.765 m** / **0.770 m** / **0.761 m**, all inside the declared 0.80 m |
| Auto arrival, home (S1) | **0.214 m** |
| Reverse departure from a spur | **2.996 m** straight back with model yaw moving **0.0002 rad**; repeated at 3.105 m and 3.320 m |
| Long leg after the departure | 29 m driven with **848 consecutive** SAFE/SAFE/SAFE field samples |
| Steering stability | **1 sign flip in 259** steering samples on a full leg |
| Deploy | 13 files; `stop` swept 13 / killed 8, UDP :5100 free afterwards |
| Forklift drives (teleop positive control) | 2.847 m in 8 s at 0.4 m/s commanded |
| Vehicle stops after the PLC link dies (`step5.py` closed) | detected in ≤ 350 ms; budget < 0.45 s end to end |
| Vehicle stops after `plc_link` itself dies | ≤ 295 ms; budget < 0.35 s |
| HMI display returns to the safe state | 301 ms |
| Real-time factor, `start --headless` | mean **0.998**, median 0.9999, min 0.926 over 60 samples |
| Real-time factor, `start` (window up) | mean **0.806**, median 0.997, min 0.127, max 1.763 over 60 samples |

**Read those last two rows as "the median is still 1.0, the floor is not."**
The window does not slow the simulation down on average so much as make it
*lumpy*: the server stalls while llvmpipe draws a frame and then runs fast to
catch up, so an interval measured with the window open is worth less than the
same interval measured without it. The timing rows above were all measured
headless, and a re-measurement of them should be too.

## Unit tests — step6's own, and the number to expect

**`302 passed, 0 skipped`** under WSL:

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step6/tests/ -q
```

A **skip** is a failure here: it means a module did not import and its tests
silently did not run. On Windows the same suite gives `199 passed, 2 skipped,
7 errors` with `--continue-on-collection-errors` — the seven are `No module
named 'rclpy'` and the two skips `No module named 'paho'`, neither of which
Windows has or is supposed to.

## Validation checklist

**Step 6's ledger is [PROOF.md](PROOF.md), and it is deliberately unfinished.**
Of the M6.1 spec's six proof gates: Gate 1 (two-vehicle RTF) and Gate 5 (clean
lifecycle, twice) are measured with the output kept, Gate 4 has its fail-safe
half measured and its driving half owed, and Gates 2, 3 and 6 are **NOT RUN** —
they need the two Windows writers and a hand on two joysticks, which no agent
may supply. PROOF.md gives each of the four a numbered runbook: one action per
step, and where to write the number down.

Nothing there is ticked on the strength of a copied file, and an unticked gate
is not a passed one.
