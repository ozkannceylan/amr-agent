> **Relocated 2026-08-21:** this tree moved from `m5_ver2/step6/` to `/m6`
> and took the milestone's name (owner ruling: it is Milestone 6, not a
> step of m5_ver2). Code identities followed (`m6.sh`, `windows/m6.py`,
> `GZ_PARTITION=m6`). Historical references below to `m5_ver2/step6` and
> `step6.*` are TRUE RECORDS of where things lived when measured — do not
> rewrite them; mentally substitute `/m6` when following instructions.

# Step 6 context

**Step 6 is Step 5 run twice in one world.** One warehouse, two forklifts,
`f1` and `f2`, each with its own full vehicle stack, its own UDP port pair,
its own commissioning HMI and its own Windows writer. They share the Gazebo
world, the machine's CPU, and — for now — their TF frame ids (the one
limitation, at the foot of this section). M6.1's claim is that the second
vehicle needed no second copy of the CODE: every node is the same script
under a different environment, and the only per-vehicle files in the tree
are generated. `m5_ver2/CLAUDE.md` still holds the PLC tag table and the
safety-program behaviour, unchanged, for both trucks.

## The VEHICLES table is the one home for every per-vehicle difference

`ipc/status_contract.py`:

```python
VEHICLES = {
    "f1": {"plc_port": 5110, "sensor_port": 5111,
           "spawn": {"x": "-3.00", "y": "-5.50", "z": "0.05", "yaw": "0.0"}},
    "f2": {"plc_port": 5120, "sensor_port": 5121,
           "spawn": {"x": "3.00", "y": "-5.50", "z": "0.05",
                     "yaw": "3.14159"}},
}
```

Everything else is derived from it:

- **Topic names.** `contract(vid)` returns `/f1/plc/status`,
  `/f1/safety/fields`, `/f1/vehicle/cmd_vel` and the rest. The step5
  `/forklift/...` family exists nowhere on the wire — measured, see
  PROOF.md.
- **Ports.** 5110/5111 and 5120/5121. The 5100/5101 family is left to
  step4 and step5 on purpose, so a concurrently running step5 stack
  collides with nothing here.
- **The env var.** WSL nodes read their vehicle from `VEHICLE`, which
  `step6.sh` stamps on every spawn; the Windows writer sets the same
  variable from `--vehicle` **before** importing `status_contract`. That
  ordering is load-bearing: the module binds its per-vehicle constants
  once, at first import, and refuses by name if `VEHICLE` is absent.
- **`vehicles/f1/` and `vehicles/f2/`** are GENERATED, by
  `tools/instantiate_vehicle.py`, from `gazebo/forklift_ver2/model.sdf`
  and `agv/forklift/config.yaml`, by counted prefix rewrite. They are
  gitignored and `step6.sh deploy` remakes them before it freezes the
  image. **Never hand-edit a file under `vehicles/`** — edit the source
  and redeploy. Both sources stay untouched: `config.yaml` belongs to
  three stacks and `forklift_ver2/model.sdf` is the inherited plant.
- **The spawn poses.** f2 faces f1 down the main aisle, 6.00 m away in
  the open south block. Both were validated live (Gate 1): each truck
  settles to floor level at exactly the table's coordinates, zero roll,
  zero pitch.

`step6.sh` repeats the ID LIST — `VEHICLES=(f1 f2)` — and the two PLC
ports as literals in its pre-flight guard, because a shell cannot import
Python. `windows/step6.py` repeats the ID list once more, as its
`--vehicle` argparse choices, because the parser has to exist before the
module may be imported at all. Those are the only three duplications, all
three carry a maintenance note, and the third is now pinned by a test
(`tests/test_vehicles_table.py`).

## The writers: one process, one PLC, per truck

The single-writer rule is per PLC, and each vehicle has its own:

```
python m5_ver2\step6\windows\step6.py --vehicle f1 --virtual
python m5_ver2\step6\windows\step6.py --vehicle f2 --virtual
```

`--virtual` puts `windows/virtual_fplc.py` in the F-PLC's place, in
process. **f2 has never run against a real PLC** and cannot until a PLCSIM
license returns — `PLC_INSTANCE`'s `f2 -> "PLC_3"` half is reserved and
unreachable. Results earned under `--virtual` are rig results, not
F-program validation.

## The VDA 5050 agent: one per truck, and it is not a safety path

**M6.2 gave each vehicle `ipc/vda_agent.py`**, started by `step6.sh` beside
that vehicle's nav node, and the stack was twenty processes then: the
broker, the world, and nine per truck. M6.3 made it twenty-one — one fleet
manager over the pair of them, in its own section below. **M6.5 made it
thirty-nine**: the same three, nine per truck, four trucks. The agent is the
only door into this stack from off the machine.

**Owner ruling 2026-08-21: full-route orders from day one.** Master control
sends `nodes` + `edges`; the vehicle drives the released nodes exactly, in
sequence, and does not re-route. The single-node alternative was rejected
because M6.4's edge and zone reservation needs the route to be *in* the
order. `tools/send_order.py` is what sends one until a fleet manager exists,
and it plans with the same `route.plan_route` the HMI's GO uses — so the
route the "fleet" sends is the route the vehicle would have planned, and
full-route following is exercised without a second planner being invented.

**The invariant this channel lives under: it is REPORTING and process
command only.** `state.safetyState` narrates what the F-model already did.
Nothing published on MQTT can stop a truck and nothing on it is in the
safety chain — the chain is the F-program's, and the brake is the e-stop.
The one thing that follows and is easy to get wrong: **supervision loss is
not a safety event.** Broker gone means degraded mode, handled as a
controlled stop through the NORMAL chain — the agent publishes the empty
goal, nav goes IDLE and commands zero through `cmd_mux` and `cmd_gate` like
any cancelled goal, and `Motor` never drops. The order is KEPT, not dropped:
on reconnect the remaining released nodes are re-issued as a fresh route
from the pose the truck is at now. `_resume` re-checks AUTOMATIC before it
publishes, so supervision that comes back during a teleop shift holds the
order instead of asking for a drive nav would only refuse.

**The agent believes nav, not itself.** Publishing a route is a request:
`nav_core` refuses one it cannot drive and cancels one already running when
the mode leaves auto, and it says so in `/auto/state`'s note. So the agent
reconciles — a nav gone IDLE with a refusal note and no goal ends
`executing`, loudly, on the state. That reconciler is deliberately deaf for
`NAV_SETTLE_S = 0.3` s after a route goes out (`ipc/vda_agent.py`), because
a `/auto/state` already in flight when the route is published still
describes the world BEFORE it, and reading that as a refusal would strand a
truck that is about to drive. nav publishes at 10 Hz, so 0.3 s is three
periods of margin; the cost is a bounded ~0.4 s window in which a genuine
refusal is not yet believed, and the next state closes it.

**M6.3 came for two things and took one.** `tools/send_order.py` was master
control's hand until master control existed; it is now SUPERSEDED — kept, with
a header saying so, as a low-level one-truck probe, because a debugging tool
that talks straight to a vehicle's door is worth having and deleting it would
only mean rewriting it the next time an order is refused. The **broker** did
not move: a broker belongs to one machine that is not a vehicle, and this rig
*is* one machine — the trucks, the fleet manager and the broker share it. When
the cell ever gets a machine of its own, `PATTERNS`, `recorded()`, the `:1883`
pre-flight, the two `BROKER_*` variables and the `spawn fleet` line in `m6.sh`
are the places that come out together.

## The fleet manager: one for the cell, and it is not a safety path

**M6.3 put master control above the trucks** — two then, four since M6.5, and
it never had to learn the difference: it discovers its fleet on the wire and
reads no vehicle table at all. `fleet/fleet_manager.py` is paho-only — no ROS,
no `VEHICLE`, no DDS domain — started by `m6.sh` as the stack's last
pid; `fleet/fleet_cli.py` is the operator's hand and screen. Work enters
the cell as a **transport**: two station ids,
`fleet_cli.py submit S1 S4`. Which truck drives it is the FLEET's decision,
made from the trucks' own reported positions over the vehicle's own route
graph, and there is deliberately no way to name a vehicle from the CLI.

**Owner rulings 2026-08-21, and they are the shape of the code:**

- **A transport is TWO LEGS.** An order to the pickup, a dwell standing in for
  the fork cycle (`DWELL_S = 3.0 s`), an order to the dropoff. That is why the
  task machine has a `DWELL` wedged between two `ASSIGNED` states rather than
  one order per task. There is no `dwell_done` event: a timer expiring is not
  something that happened to the task, it is permission for the manager to
  build leg 2, and the only thing that leaves `DWELL` is the leg-2 order
  actually going out.
- **On loss mid-task the task RETURNS TO THE QUEUE HEAD** and the other truck
  may take it; the lost vehicle gets nothing until it is idle-confirmed again.
  The interrupted transport is the oldest work in the cell, and re-queueing it
  behind newer tasks would punish it twice.
- **`OFFLINE` is a loss, exactly as `CONNECTIONBROKEN` is** — absorbed as a
  ruling during M6.3's review, where it began as a deviation. A clean goodbye
  and a will differ in how politely the link ended, not in whether the fleet
  still has a path to that truck, and the loss ruling is about the TASK.

**The loss-return race is real, and it is logged rather than pretended away.**
A lost vehicle that comes back holding an order whose task the fleet has
already given to somebody else is sent exactly one `cancelOrder` — the only
flow in which the manager cancels anything at all. The M6.2 agent *resumes* a
kept order on reconnect (see the section above), so the returning truck may
drive for the seconds the cancel takes to land. The manager says so in its own
log at the moment it happens and PROOF.md's Gate 4 measures the window.

**Adopt-by-waiting is not a mechanism; it falls out of the idle rule.** A
restarted manager has no journal and no tasks — the queue is in memory, it
re-syncs from retained `connection` topics and the states that follow, and the
operator resubmits. A truck still driving an `ft-` leg is simply *not idle*, so
nothing is assigned to it and nothing needs cancelling; it is adopted by being
left alone. **Startup cancels nothing, ever.** The one subtlety underneath:
what counts as executing is an orderId AND a non-empty `nodeStates`, because
the M6.2 agent keeps its orderId after arrival forever — orderId alone would
mean no truck is ever idle again.

**The screen is the retained document, and its ages are computed when it is
built.** `fleet/status` (retained, QoS 1, republished on change and every 2 s)
is the operator's only window. A dead feed therefore shows an age that GROWS
rather than a frozen row that still reads EN-ROUTE — the Gate 6 carry-in. The
manager sets NO last-will for itself on purpose: a truck's death is a protocol
event, the fleet's is not, and a retained document going stale is a signal that
cannot lie the way a "manager: ALIVE" flag can. `fleet_cli.py status` prints
the document's own age in its header for exactly that reason.

**What this layer may never become** is written down in `fleet/README.md` as
three standing invariants, and every file under `fleet/` cites them: no ROS
lives here; the only path to a vehicle is VDA 5050 over MQTT, so the worst
master control can command is a route and a cancel; and losing the fleet must
DEGRADE, never endanger — kill the manager and every truck keeps its order,
the guards keep guarding, the F-CPU keeps the chain, and the e-stop is still
the brake.

**M6.4 takes traffic.** Two trucks in one aisle are still each other's problem:
there is no edge or zone reservation, no deadlock resolution and no speed
supervision between them — `order.edge.maxSpeed` is parsed and not enforced.
The route is IN the order (the full-route ruling) precisely so that M6.4's
reservations have something to reserve.

## What is proven, and what is not

**`PROOF.md` is the ledger, and every gate in it is now measured — which is
not the same as passed.** M6.1's six, M6.2's six VDA gates, M6.3's six fleet
gates, M6.4's six traffic gates and M6.5's five live gates all ran on this
machine with their output kept. **Four stand measured and NOT ticked**, each
with its run written up in full: M6.4's Gate 2 (closed later by M6.5's), and
M6.5's Gate 3 (four crossing transports, 0 of 4 completed), Gate 4 (the
acceptance run, 1 of 8) and Gate 5 (three clauses of four). What stopped the
last three is floor geometry rather than the fleet layer — a spawn pose
inside its own warning field, a turning radius wider than the corner it is
asked to turn, and a ledger that deconflicts processes and has never claimed
to see a body. Read PROOF's closing section, **What Milestone 6 claims, and
what it does not**, before quoting a number out of this tree; do not read an
unticked gate as a passed one.

**The four-truck figures are conditional on a GPU that is not configured.**
`GALLIUM_DRIVER=d3d12` and `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA` are not
in this machine's `~/.bashrc`; without them the world renders on llvmpipe and
says nothing about it. With them, the full 39-pid stack ran at 0.575–0.580 of
real time across the whole acceptance run.

Loop-level evidence sits beside it: `tests/test_m6_virtual_loop.py` drives
the real `m6.control_loop` against `VirtualFPLC` over real UDP sockets,
parameterised over **every port pair in the table** — four since M6.5, so
three scenarios become twelve runs. **481 tests pass under WSL** (370 at
M6.2, 439 at M6.4, 453 before the table grew to four, 466 at the M6.5 gate
run), and the suite needs
`source /opt/ros/jazzy/setup.bash` first or it aborts in collection.

## Full-stack RTF: about 0.75, and Gate 1 does not cover it

Gate 1's 0.934-0.995 is **server-only** — `gz sim -s` and two models, no
ROS stack. With M6.1's whole 17-pid stack up headless — before M6.2's broker
and two agents joined it, and not re-measured since —
`/world/warehouse/stats` means **0.755** and **0.734** over two 60 s samples (PROOF.md has the
per-10 s buckets). That is a consistent load floor, not scheduling noise:
the ROS side costs roughly a quarter of real time. It breaks nothing —
every loop in the tree is wall-clock timed, so rates are unaffected and
only *simulated* time per wall second stretches — but a third vehicle's
headroom is now the machine's, not the simulator's, and that is an M6.2
number.

**Superseded for the shipping configuration, and by measurement rather than
argument.** Every figure in the paragraph above was taken on **llvmpipe**, at
two vehicles, with the mean-of-instantaneous statistic that M6.5's Gate 1
showed is biased low on a bursty run. The number that describes what ships is
M6.5 Gate 4's: the **full 39-pid stack, four trucks, sixteen safety lidars
subscribed and rendering, on D3D12/NVIDIA — 0.575–0.580 integrated over six
consecutive 60 s windows**, held to within 0.005 across ten continuous
minutes. The instantaneous floor is still 0.021–0.035, so the deep stalls are
not gone; `SENSOR_STALE_S` at 0.40 s rode every one of them out, with zero
stale-link events on any truck in that session.

## Known limitation: the TF frames are NOT namespaced

`tools/instantiate_vehicle.py` rewrites topic prefixes. It does **not**
rewrite frame ids. Both derived models still declare:

```xml
<odom_frame>forklift/odom</odom_frame>
<robot_base_frame>forklift/base_link</robot_base_frame>
```

so `/f1/gz/odom` and `/f2/gz/odom` carry **byte-identical**
`frame_id: forklift/odom` / `child_frame_id: forklift/base_link` —
measured live on 2026-08-21.

**Nothing in step6 reads them, which is the only reason this is not a
defect today.** There is no `/tf` topic in the stack at all (65 topics, no
`/tf`), no node greps `frame_id`, and the two consumers of odometry —
`nav_node` and the HMI sketch — take `msg.pose.pose` and nothing else.

**M6.2+ must namespace the frames BEFORE the first consumer appears.** The
moment anything publishes TF, runs a costmap, or opens RViz on both
trucks, two vehicles will be broadcasting the same `forklift/odom ->
forklift/base_link` transform into one tree and the second one wins,
silently. The fix belongs in `instantiate_vehicle.py` next to the topic
rewrite, and it has to move `config.yaml`'s `odometry` frame names in the
same pass — `config.yaml` mirrors `model.sdf`'s frames on purpose and
neither may drift from the other.

---

# Inherited context — Steps 1 to 5

**Everything below this line describes the ANCESTOR.** It came across with
`cp -r step5 step6` and it is kept because the invariants it records are
still the invariants — the self-mask bearings, the station standoffs, the
latched `/hmi/mode`, the six live rounds of 2026-08-13. What it is NOT is
a description of step6's wire: names below are the step5 spellings
(`/forklift/...`, `5100`/`5101`, `step5.sh`, "nine pids") and the step6
equivalents are the per-vehicle ones above. Read it for the WHY; read this
file's head, `PROOF.md` and `README_step6.md` for the WHAT.

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

## The virtual F-PLC rig (2026-08-20)

The PLCSIM Advanced trial expired. `windows/step5.py --virtual` swaps the API
object for `windows/virtual_fplc.py` — a behavioural model of the validated
F-program: five latching ESTOP1 instances, ack-edge semantics, the encoder
cross-check and ceiling, `V_Limit` and the pinned monitoring case. Two owner
rulings are baked in (any violated warning field → `V_Limit` 300; case pinned
at 1) — see `docs/superpowers/specs/2026-08-20-virtual-fplc-design.md`.
Without the flag the writer still expects PLCSIM `PLC_2`, unchanged. The model
claims no safety integrity: a Step 6 result earned on this rig is a rig result
until re-proved against a real or licensed PLC. The owner ran the
full-stack smoke under `--virtual` on 2026-08-20 and reports it working;
Step 6 starts on this rig.

**What has actually been verified, and at what level.**
`tests/test_virtual_fplc.py` pins the model's semantics;
`tests/test_step5_virtual_loop.py` pins the loop around it, running the real
`control_loop` over real UDP sockets with the model in the PLC's place — the
enable after one Acknowledge and the five-key 5100 payload that reports it, a
protective-field trip latching through the heal until the next ack, and the
fail-safe when the 5101 link goes silent. Gazebo and Tk are the only things
absent from that path. The **full stack has not been re-proved under
`--virtual`**: no autonomous leg, and no scanner trip out of a real field
evaluation, has been driven against the model. That run is the owner's first
smoke before Step 6 work starts.

## Known debt carried forward

- **The one silence path that fails open: `/vehicle/cmd_vel` at the gate.**
  `cmd_gate` forwards on receipt and its tick publishes only while
  inhibited, so if `cmd_mux` dies with Motor True the plant holds its last
  setpoint (Step 4 measured the class at 14.8 m) while the HMI still shows
  a live EN-ROUTE. Every other silence path in this tree fails closed; a
  `STATUS_STALE_S`-class window on the gate's command input — zeros when
  enabled-and-silent, symmetric with the mux's own auto-source rule — is
  the Step 6 fix. Final whole-branch review 2026-08-13 named it.
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
