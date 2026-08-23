# Step 6 — four forklifts in one warehouse

One world, four vehicles. **`f1`**, **`f2`**, **`f3`** and **`f4`** each run a
full copy of Step 5's vehicle stack — mux seam, autopilot, `Motor`-gated
`cmd_gate`, STO contactor, commissioning HMI — on its **own topic namespace,
its own UDP port pair and its own Windows writer**. They share the Gazebo
world and the machine's CPU, and nothing else: there is no cross-vehicle
channel below the fleet layer, by design.

**It was two until M6.5 and the code did not change to make it four.** The
`VEHICLES` table grew two rows; the launch file, the instantiation tool, the
manager, the ledger, the CLI and `m6.sh`'s loops all read that table and
followed. What four costs is not code but **GPU rendering** — see
[The GPU condition](#the-gpu-condition--two-exports-in-your-shell), which every
four-vehicle number in [PROOF.md](PROOF.md) depends on.

Step 6 adds three things to Step 5 and closes one debt:

- **The `VEHICLES` table** in `ipc/status_contract.py` — the single home for
  every per-vehicle difference (ports, topic names, spawn pose, config path).
- **Derived vehicles.** `vehicles/f1/` … `vehicles/f4/` — one directory per
  row of that table — are *generated* from `gazebo/forklift_ver2/model.sdf`
  and `agv/forklift/config.yaml` by `tools/instantiate_vehicle.py`. They are
  gitignored and rebuilt by `deploy`. **Never hand-edit them.**
- **A writer that takes `--vehicle`.** One process per PLC, per truck. The
  single-writer rule holds per vehicle; it is not an exception to it.
- **Debt closed:** `cmd_gate` now publishes zeros when it is enabled and its
  *command* input has gone quiet (`CMD_STALE_S = 0.25 s`) — the one fail-open
  silence path step5's final review named.

**Since M6.1 this tree has grown a fleet.** M6.2 gave each truck a VDA 5050
client of its own, and M6.3 put one master control above all of them: work
now enters the cell as a *transport* between two stations and the fleet
decides which truck drives it. See **[VDA 5050](#vda-5050--orders-over-mqtt)**
and **[Fleet manager](#fleet-manager--the-cells-master-control)**.

> Something looks wrong? Read **[Not a bug](#not-a-bug)** before you debug it.

**Evidence: [PROOF.md](PROOF.md) — read its ledger before you trust anything
here.** M6.1's six gates, M6.2's six VDA gates, M6.3's six fleet gates,
M6.4's traffic gates and M6.5's five live gates are all measured with their
output kept. **Measured is not the same as passed, and the ledger says which
is which.** M6.5 closed M6.4's blocked **Gate 2** — a spur station is handed
from one truck to another with the entry node never going free — and its
Gate 6 shows the safety chain untouched at four. **Its Gate 3 (four-vehicle
traffic) and Gate 4 (the acceptance run) FAILED and are written up at full
length**: 0 of 4 and 1 of 8. What stopped them is floor geometry, not the
fleet layer, and the two defects are named in this file as well —
[Where the parked trucks
stand](#where-the-parked-trucks-stand-and-why-it-is-a-fleet-decision) and
[Not a bug](#not-a-bug). Read PROOF's closing section, **What Milestone 6
claims, and what it does not**, before quoting any number from here.
A gate that needs hands needs **four** panels now, not two, and no agent may
supply them.

## Run order

The PLC goes first, **per vehicle**. A truck cannot be enabled without its own
writer, and each writer serves exactly one truck.

| # | Where | Do this |
|---|---|---|
| 1 | Windows | **Nothing.** All four trucks run `--virtual` (step 7), so no PLCSIM instance is needed. Against a real PLC, only **f1** has one: start `PLC_2` from the Control Panel, download from TIA Portal, CPU in RUN. f2's `PLC_3` is reserved and has never run, and f3/f4 have nothing reserved at all — one license, four trucks. |
| 2 | WSL | `cd /mnt/c/Users/ozkan/projects/amr-agent/m6` |
| 2a | WSL | `echo $GALLIUM_DRIVER` must print `d3d12`. If it prints nothing, **stop and read [The GPU condition](#the-gpu-condition--two-exports-in-your-shell)** — four trucks on software rendering is not the configuration anything here was measured on. |
| 3 | WSL | `./m6.sh deploy` — **regenerates `vehicles/f1/` … `vehicles/f4/` first** (from `gazebo/forklift_ver2/model.sdf` + `agv/forklift/config.yaml`), then freezes `ipc/` + every derived pair + `fleet/` into `deploy/` with a sha256 `MANIFEST`. Prints `deployed 31 files`. **`start` refuses without one.** |
| 4 | WSL | `./m6.sh start` — the broker goes up first, the world gets a five-second head start before the vehicle nodes, the fleet manager goes up last, then one more second before `start` checks that all **thirty-nine** are still alive. Do **not** source ROS first; the script does it. |
| 4a | Screen | **Five windows:** the **Gazebo window** with the warehouse — f1 on S1 and f2 facing it 6.00 m down the dock aisle, f3 parked at the main aisle's west end and f4 at the dock aisle's east end (they stand at the aisle ENDS on purpose — see [Where the parked trucks stand](#where-the-parked-trucks-stand-and-why-it-is-a-fleet-decision)) — and **four HMIs**, `Forklift HMI - f1` … `- f4`. `start --headless` skips the Gazebo one. |
| 5 | WSL | Read the **thirty-nine** pid lines: `broker`, `world`, then nine per vehicle (`plc_link cmd_gate cmd_mux field_eval encoder_link sensor_link nav_node vda_agent hmi`) for f1, f2, f3, f4 in turn, then `fleet` — the cell's master control, one for the whole fleet. `WARNING: <name> exited during startup` sends you to that log in `logs/`. A `THE STACK IS INCOMPLETE.` line means stop and read it. |
| 6 | Windows | `cd C:\Users\ozkan\projects\amr-agent` |
| 7 | Windows | `python m6\windows\m6.py --vehicle f1 --virtual` — **64-bit Python** (pythonnet). A grey **panel** opens, titled `Forklift f1 PLC Control Panel - VIRTUAL F-PLC (model)`; the console prints `streaming PLC state to <wsl-ip>:5110` and `listening for the back scanner on 0.0.0.0:5111`. |
| 8 | Windows | **One more terminal per remaining truck** — `--vehicle f2`, `f3`, `f4` — each `cd`'d the same way. Same panel, titled for its own truck, on **5120/5121**, **5130/5131** and **5140/5141**. `start` prints the four command lines; that list comes from the table, so it is always the right one. |
| 9 | Panels | Click **RESET** on each panel. Once each. Every lamp reads `MOTOR ENABLED`; every HMI turns neutral and reads `Drive enable: ON`. |
| 10a | HMI windows | **Teleop:** leave a truck's radio on `Teleop` and drag *that* HMI's joystick. Only that truck moves. |
| 10b | HMI windows | **Auto:** click `Auto`, click a station dot on that HMI's sketch, press **GO**. All four trucks can be routed at the same time. **STOP** cancels a goal — it is not a brake. |
| 10c | WSL | **Auto, as fleet work:** `python3 m6/fleet/fleet_cli.py submit S1 S4` queues a *transport* — you name two stations, the fleet picks the truck. Same precondition as **GO**, and the fleet enforces it: a truck not in `Auto` is not idle-confirmed, so the task waits rather than failing. Watch it with `python3 m6/fleet/fleet_cli.py status --watch`. See [Fleet manager](#fleet-manager--the-cells-master-control). |
| 11 | Panels | Finished: **close every panel window**. Each writes its own truck's trip values on the way out. |
| 12 | WSL | `./m6.sh stop` |

**No PLCSIM license? That is the normal case here.** `--virtual` puts
`windows/virtual_fplc.py` in the F-PLC's place, in process, with the measured
semantics (design: `docs/superpowers/specs/2026-08-20-virtual-fplc-design.md`).
Results earned this way are **rig results, not F-program validation** — and
f2, f3 and f4 have *only ever* been virtual trucks. The acceptance record has
to say which truck proved what: only f1 ever ran against a real F-program.

### The GPU condition — two exports in your shell

**Four vehicles need the GPU, and nothing in this repo turns it on.** Put
these two lines in the WSL user's `~/.bashrc`:

```bash
export GALLIUM_DRIVER=d3d12
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
```

**What they buy, measured** (PROOF.md, *M6.5 — sizing the machine for four*,
2026-08-22; same world, same four trucks, same sixteen lidars subscribed,
60 s windows):

| Renderer | Four vehicles, printed RTF | Four vehicles, integrated |
|---|---|---|
| llvmpipe (no exports) | 0.190 / 0.230 / 0.230 | 0.579 |
| **D3D12 / NVIDIA (exports set)** | **0.583 / 0.687 / 0.670** | **0.903 / 0.899 / 0.712** |

Without them Mesa falls back to `kms_swrast` and the twelfth subscribed lidar
takes the world off a cliff (0.981 → 0.274) — the fourth truck is where two
of them stop fitting. With them the renderer is
`D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)` and that cliff is gone.

**They belong to the shell, and `m6.sh` deliberately does not set them.** The
server has to inherit them *before* `gz sim` starts, so a subshell inside the
script would be too late for the process that matters; and two exports at the
top of `m6.sh` would make every m6 run depend on a GPU being present, which is
a portability decision the operator owns and a start-up script does not. The
environment is the operator's, so the condition is *stated* rather than
hidden: every four-vehicle number in PROOF.md is quoted with the renderer it
was measured on.

**Verify before a run, in a fresh shell:**

```bash
glxinfo -B | grep Device                    # your shell -> D3D12 (NVIDIA ...)
grep GL_RENDERER ~/.gz/rendering/ogre2.log  # after a run: what the SERVER took
```

The first reads **your shell** and is the one to run before a gate: it prints
`llvmpipe` exactly when the exports are missing, which is the answer you want
it to give. (Do **not** write `GALLIUM_DRIVER= glxinfo -B` — that empties the
variable for that one command and prints llvmpipe on a perfectly good machine.
To ask the question without touching your shell at all, spell both exports on
the command line as PROOF.md ran them: `GALLIUM_DRIVER=d3d12
MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA glxinfo -B | grep Device`.) The second
is the only line that proves the **server** took it, and it is the one a gate
quotes. The Windows writers need nothing — they render nothing.

**What the whole stack costs on top of that**, measured 2026-08-22 at the
shipped poses (`start --headless`, thirty-nine pids, every scanner bridged,
all four trucks standing still): two 60 s windows gave **0.648 and 0.659**
printed, **0.626 and 0.629** integrated, with an instantaneous floor of
0.026. (Two earlier windows at the pre-review f3/f4 poses read 0.652 / 0.587
printed and 0.613 / 0.606 integrated — the same band, which is what you would
expect from a cost that is sixteen lidars rather than where they stand.) That
is the **idle** stack; the number under a running acceptance run belongs to
Gate 4 in [PROOF.md](PROOF.md), and it is reported there whatever it says.

Two things the exports do **not** fix, both recorded in PROOF.md: the printed
statistic is a mean of instantaneous samples and *understates* a bursty run
(the integrated column is the honest one, and it is why llvmpipe's four trucks
read 0.579 rather than 0.190); and deep stalls still happen — the
instantaneous floor in a four-vehicle window is 0.023–0.043.

### Where the parked trucks stand, and why it is a fleet decision

A spawn pose is not decoration. An idle truck **holds the node it is standing
on** (`fleet/floor.py`, `_hold_standing`), and after `IDLE_HOLD_S` (30 s) the
floor **gives that node back with the truck still on it** (`_idle_floor`,
which says so in its own warning). So a truck parked on a junction spends the
first half-minute of a run blocking it and every minute after that invisible
on it, with the scanners left as the only stop.

M6.5 got this wrong once: f3 and f4 first went in at `(-8.0, 5.65)` and
`(8.0, 5.65)`, which look like open main-aisle floor and are in fact the two
**spur junctions** — the only way in to S6 and S8, and to S5, S7 and S9.
Measured over the real planner and all 90 station-to-station routes:

| Node | On how many of the 90 routes | Nearest station | Clear floor |
|---|---|---|---|
| `(8.0, 5.65)` | **46** | 0.85 m (S7) | 3.25 m |
| `(0.0, 5.65)` | 44 | 8.05 m | 4.35 m |
| `(-3.0, -5.5)` — f1, *on* S1 | 42 | 0.00 m (S1) | 4.50 m |
| `(-8.0, 5.65)` | **34** | 0.85 m (S6) | 3.25 m |
| `(3.0, 5.65)` — **f4** | 36 | 5.07 m | 3.25 m |
| `(-3.0, 5.65)` — **f3** | 20 | 5.07 m | 3.25 m |
| `(3.0, -5.5)` — f2 | 12 | 3.91 m | 4.50 m |
| `(-12.5, 5.65)` — *was f3* | 12 | 4.58 m | **2.50 m** |
| `(8.0, -5.5)` — *tried for f4* | **6** | 3.20 m | 4.45 m |
| `(12.0, -5.5)` — *was f4* | **6** | 6.50 m | **3.00 m** |
| `(12.0, 5.65)` | **6** | **0.40 m** (S5) | 2.00 m |

No node in this graph is route-free — all 26 carry at least one — so the rule
is *least-used floor*, not clean floor. `(12.0, 5.65)`, the main aisle's east
end, is rejected for a reason worth knowing: 6 routes, but **0.40 m from S5's
own station point**, so a truck parked there stands on the conveyor while the
ledger calls it a different node.

**And the least-used node was the wrong thing to optimise on its own. M6.5's
first gate run measured what that cost, and it cost the acceptance run.** The
two quietest nodes in that table are the **end-aisle** ones, and the end
aisles are 5.00 m wide. The left and right scanners are mounted at the
**fork-end corners** (`model.sdf`, `-0.68 ±0.46`), so a truck parked 2.50 m
off the west wall stands with one of them 1.82 m from it — inside its own
2.5 m warning field before anything moves:

| | Old pose | Wall | Fork corner to it | `WF b/r/l` at rest | `V_Limit` |
|---|---|---|---|---|---|
| f3 | `(-12.50, 5.65)` | `x = -15.0` | **1.82 m** | `T/F/F` | **300** |
| f4 | `(12.00, -5.50)` | `x = 15.0` | **2.32 m** | `T/F/F` | **300** |

`cmd_gate` clamps every command to `min(speed_max, v_limit/1000)`, so both
crawled at 0.30 m/s from their first cycle. Worse, a *turn* swings the same
scanner another half-metre out: **f3 latched its protective field 0.971 m from
the west wall turning south out of that pose, eight seconds into the
acceptance run** (PROOF, M6.5 Gate 4, 19:43:15.092), and its hulk held the
west cross-aisle for the remaining ten minutes.

**So the poses moved in off the end walls, and a third rule went into the
guard test.** f3 and f4 now stand on the main aisle at `(-3.00, 5.65)` and
`(3.00, 5.65)`, level with the rack runs' inner ends and 6.00 m apart, back to
back — exactly as f1 and f2 stand on the dock aisle 11.15 m south of them. The
rule is measured off the **world SDF's own collision
boxes at the safety scan plane** — not off `stations.OBSTACLES`, which is
documented as the SDF's shadow and which nothing tests against the file:

* **at rest** — every scanner, at the pose's own yaw, further than
  `WF + hysteresis` (2.70 m) from any solid, *including the other three
  parked trucks*, whose contour is the vehicle SDF's at that plane (the forks
  sit below it and the chassis above it, so neither is in the contour);
* **leaving** — the pose itself further than
  `PF + hysteresis + scanner ring (0.821 m) + the pursuit's turning circle
  (LOOKAHEAD_M / 2 = 0.60 m)` = **2.62 m** from any solid.

| Truck | Pose | At-rest worst scanner | Leaving | Margin |
|---|---|---|---|---|
| f1 | `(-3.00, -5.50)` | 4.04 m - left, south wall | 4.50 m | +1.88 |
| f2 | `(3.00, -5.50)` | 3.99 m - right, the dock door post | 4.50 m | +1.88 |
| **f3** | `(-3.00, 5.65)` | **2.84 m** - right fork corner, rack A's end frame | 3.25 m | +0.63 |
| **f4** | `(3.00, 5.65)` | **2.84 m** - right fork corner, rack B's end frame | 3.25 m | +0.63 |

Read back off the running world with all four at rest: **every device `wf` true
and `V_Limit` 1500 on all four**, which is exactly what the old table could not
say. The two main-aisle trucks measured `3.34 / 2.84 / 2.84` (back/left/right)
against 2.84 computed - the arithmetic and the scanners agree to the
centimetre.

**The rule predicts the run it was written from.** f3's old pose scores
`2.500 - 0.821 - 0.600 = 1.079 m` of scanner clearance through the turn
against the 1.20 m it needs; the truck measured **0.971 m** at the latch - a
rule 0.108 m off the event it explains. `tests/test_vehicles_table.py` pins
all three rules - no spur junction, no pose almost-but-not-quite on a station,
and no truck parked inside a field it cannot clear or turn out of.

**The four poses are a division of the floor.** Each truck is the nearest to
the stations on its own quarter and to no others: f1 `S1 0.00, S3 5.50,
S10 6.00, S2 7.90`; f2 `S4 5.50`; f3 `S6 5.85, S8 5.85`; f4 `S7 5.85,
S9 5.85, S5 8.60`. Every station has a truck within 8.60 m and no truck has to
cross the hall to start a transport it is chosen for.

**Two rules the route-usage table cannot see, both bought at full price on
2026-08-22.** First, **every yaw points the truck at the floor it will be sent
to**: model yaw 0 puts the forks at world `-x` and the *travel* heading is the
model heading flipped, so a truck at yaw 0 drives **west** when it is given
work. Where the first leg goes the other way the follower does not swing round
- it **reverses**, straight, and stays in reverse until the next target is
within `REVERSE_EXIT_RAD` of its travel heading, which turning into a spur
(94 deg) never is. f4 parked at `(8.0, -5.5)` yaw pi was sent to S4, 4.50 m
away and west, reversed straight down the dock aisle, **passed the junction it
should have turned at by 0.18 m** and stopped for good with nav's obstacle
guard **1.477 m off parked f2** (`GUARD_HOLD_M` is 1.5).

Second, **a parked truck must have room to turn into the stations it is
nearest to.** `(8.0, -5.5)` is the quietest clear node on this floor - 6 of
the 90 routes - and it is **2.00 m** from the S4 spur junction, so it wins
every S4 transport and has two metres to set up a turn into a 2.5 m spur. At
yaw 0 f4 drove up at 0.70 m/s, decelerated into the corner and **stalled**:
steer joint at -0.926 rad against a -2.5 rad/s traction command, drive-wheel
velocity 8e-5 rad/s, nav still `EN-ROUTE` with the guard clear at 2.975 m, for
seven minutes. The same spur is reached routinely from the **west**, where the
approach has 3.00 m of run-up. So f4's parking node moved to the main aisle
and S4 went back to f2, whose approach is the proven one. **Least-used floor
is not the only rule**: a pose nobody drives through is worth nothing if the
truck standing on it cannot get out of it and into the stations the fleet will
pick it for.

**f1 is the residual, and it is deliberate.** It keeps step5's proven pose,
which is S1 itself: 42 of the 90 routes. Being *on* a station is a legitimate
place to stand, but S1 is an aisle station rather than a spur, so the idle
timeout does release it — observed on the four-vehicle bring-up run:
`idle timeout: f1 gave back 1 element(s) at (-3.0,-5.5) - it is still standing
there`. Moving f1 would invalidate every step5 and M6.1-M6.4 figure measured
from that pose, so it stays and is named here instead.

**`--headless` when you are timing something.** The Gazebo window costs
regularity more than speed:
measured over 60 samples on the one-vehicle stack, real-time factor mean
**0.998 headless against 0.806 with the window**, and the window's floor is
0.127 against 0.926. An interval measured with it open is worth less than one
measured without. (Those are step5's numbers, measured on **llvmpipe**, and
they compare the WINDOW's cost, not the stack's. Step 6's own headless figure
under M6.1's full 17-pid stack — before the broker and the two VDA agents
joined it — is **0.75**, see [PROOF.md](PROOF.md). Every RTF figure in this
file and in PROOF.md older than 2026-08-22 was measured on llvmpipe and has to
be read as that renderer's; see the section above.)

**`vehicles/` is generated — regenerate it, do not edit it.** `deploy` runs
`tools/instantiate_vehicle.py --all` before it freezes anything, so the image
can never ship yesterday's derivation. To change a truck, edit
`gazebo/forklift_ver2/model.sdf` or `agv/forklift/config.yaml` and redeploy. To change
a *port*, a *spawn pose* or a *topic prefix* — or to add a **vehicle** — edit
the `VEHICLES` table in `ipc/status_contract.py` and nothing else on the WSL
side: since M6.5 `m6.sh` reads the id list *and* the PLC ports out of that
table (`vehicle_table()`), and the launch file, the instantiation tool and the
RTF spike already did. The one place that still repeats it is the Windows
writer's `--vehicle` choices, which cannot import the table before it has
bound a vehicle — `tests/test_vehicles_table.py` fails until that tuple
follows.

**A table edit is not live until you `deploy`.** `m6.sh` and the launch file
read `ipc/status_contract.py` from **source**, but every vehicle node runs
from the frozen copy in `deploy/m6/ipc/` — so a pose or a port changed and not
deployed gives you a truck spawned at the new pose by the launch and a
`plc_link` still binding the old port, which is the *worst* half-applied state
there is. `deploy` first, then `start`; the `WARNING: deploy is STALE` banner
is what tells you the two have parted company.

**Close every panel before `stop`, in that order.** `stop` is not a brake —
Gazebo's joint controllers hold their last setpoint, so killing the stack under
a moving truck only leaves it moving (measured once at 14.8 m on a standing
command). The e-stop is the brake.

Neither script touches PLCSIM. Only you stop a PLC, from the Control Panel.

### The Windows panel — buttons, not stdin

`windows/m6.py` is a **tkinter panel**, and there is one per truck. It has no
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

### Four things `m6.sh` does that are easy to miss

- **`start` runs every process under `setsid`**, so the stack survives closing
  the terminal you started it from. Before that, closing it killed five of six
  and left `gz sim` alone in a live simulator.
- **`start` stamps `VEHICLE` on every child**, and that one word is what turns
  a shared script into f1's, or f3's. `env` execs in place, so the pid recorded
  is still the node's own. The world launch is the exception and carries no
  `VEHICLE` at all: it serves every truck from one process and reads the table
  env-free.
- **`stop` validates the PID file before it signals anything.** Each recorded
  pid must still have `m6` in its `/proc/<pid>/cmdline`, and each
  candidate must carry this stack's `GZ_PARTITION`. A second stack you have
  running — an M5 demo in partition `m5demo`, or a step5 stack — cannot be
  taken down by it, even after a reboot has recycled the recorded pids. It
  names every pid it sweeps and every pid it kills, then sweeps once more with
  KILL after a two-second grace, because Tk's mainloop ignores TERM.
- **`start` pre-flights every vehicle's UDP PLC port** — :5110, :5120, :5130,
  :5140, *read from the table* rather than spelled here or in the script — and
  refuses if any is held, naming the vehicle whose port it is. Without that
  guard a second stack takes the PLC link and `plc_link` binds nothing, in one
  warning line among thirty-nine — measured twice while building M6.1, when
  there were seventeen of them, and silent. The guard is pipe-free and
  fail-closed: an `ss` that dies mid-pipe cannot make it fall through, and a
  missing `ss` names the ports it did not check rather than pretending it did.
  The 5100/5101 family is deliberately **not** checked — it is step4's and
  step5's, and refusing over it would refuse a start that is perfectly legal
  beside them. The sensor ports (5111/5121/5131/5141) are not checked either,
  and cannot be: they are bound on the *Windows* side. **TCP :1883 joined this
  guard with the broker**, read from its own socket table rather than a shared
  one — in a single `ss -tuln` a TCP socket on :5110 would answer for f1's UDP
  link and refuse a start that is perfectly legal.

## VDA 5050 — orders over MQTT

Each truck runs its own **VDA 5050 2.1.0 client**, `ipc/vda_agent.py`, started
by `m6.sh` beside that truck's nav node. It is the one door into this stack
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
reproduces. `m6.sh` starts it as the stack's first process on
**`127.0.0.1:1883`**, localhost-only and anonymous, which is what a
config-less mosquitto 2.x does by default and is the posture M6.2 wants.
**The broker is fleet-side and it stayed here**, which M6.3 settled by
arriving rather than by moving it: a broker belongs to one machine that is not
a vehicle, and this rig *is* one machine — the trucks, the fleet manager
and the broker share it. When the cell ever gets a machine of its own, the
broker and `fleet/` leave together.

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
| `order` | in | one full route: `nodes` + `edges`, all released. Accepted only in AUTOMATIC, only when nothing is executing, and only at `orderUpdateId` 0 — order *updates* are still not implemented, and M6.3 did not need them: the fleet sends a whole leg at a time. A re-delivery of the order already held is ignored in silence (VDA's own rule); everything else refused comes back as an `orderError` on `state`. |
| `instantActions` | in | `cancelOrder`, `stateRequest`, `factsheetRequest`. Anything else is answered `FAILED` plus an `unsupportedAction` error — the factsheet is the list. |
| `state` | out | every 2 s, and immediately on every event worth knowing: pose, `driving`, `operatingMode`, `nodeStates` draining, `lastNodeId` advancing, `errors[]`. |
| `connection` | out | `ONLINE` on connect, retained; the LWT makes it `CONNECTIONBROKEN` if the agent dies. |
| `factsheet` | out | on connect and on request, retained. |

### Sending one by hand — the superseded probe

Work enters the cell as a **transport** now, through the fleet manager
([Fleet manager](#fleet-manager--the-cells-master-control)).
`tools/send_order.py` is what did this job before M6.3 existed and it survives
as a **low-level probe**: one truck, one station, one order, no queue and no
fleet between you and the vehicle's door.

```bash
python3 m6/tools/send_order.py f1 S4 --watch      # superseded; debugging only
```

It reads that truck's pose off the truck's own `state` (no ROS: the
single-writer and one-stack rules stay unbroken), plans with the same
`route.plan_route` the HMI uses, and publishes the result as an order.
`--watch` then prints the vehicle's own account once a second until `ARRIVED`.
Station ids are `stations.py`'s: `S1`…`S10`. Reach for it when the question is
about ONE truck's door and the fleet's queue would only stand between you and
the answer.

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
never reaches `ARRIVED` — Ctrl-C it. The fleet makes the same demand
differently: a truck that is not in AUTOMATIC is not *idle-confirmed*, so a
transport waits in the queue rather than being refused at a door.

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

## Fleet manager — the cell's master control

**M6.3 gave the cell one decision-maker.** `fleet/fleet_manager.py` is a
paho-only process — no ROS, no `VEHICLE`, no DDS domain — started by `m6.sh`
as the stack's twenty-first pid. It turns *transports* into VDA 5050 orders
and gives each one to the nearest idle truck. The operator names two stations;
the fleet names the vehicle.

```bash
python3 m6/fleet/fleet_cli.py submit S1 S4        # a transport: pickup, dropoff
python3 m6/fleet/fleet_cli.py status              # the fleet's own account
python3 m6/fleet/fleet_cli.py status --watch      # reprinted on every update
```

`submit` prints the `ft-` task id it generated and exits 0 (`--task-id` names
one yourself). An unknown station is refused before anything is published,
with the ten real ids in the message. A duplicate task id is refused by the
*manager* — the CLI has no book to check it against — and shows up in the
screen's `REFUSED` block, which is why that block is on the screen.

**A transport is two legs, and the dwell between them is the fork cycle.**
Leg 1 drives the chosen truck to `FROM`; it stands there `DWELL_S = 3.0 s`
(the fork cycle, simulated — owner ruling); leg 2 drives it to `TO`. The task
is `QUEUED → ASSIGNED_LEG1 → DWELL → ASSIGNED_LEG2 → DONE`, and every leg is a
full-route order the truck's own door (`ipc/vda_orders.py`) validates before
it is published.

**Nearest idle, by the vehicle's own router.** Every clause of *idle* is in
`fleet/fleet_core.py` and each one is a refusal somebody has to live with:
ONLINE, AUTOMATIC, nothing left to drive, a state no older than 3 s, not lost,
and not standing down after a rejection or a loss-return. Distance is
`ipc/route.plan_route` summed — the graph the truck itself would drive, not
the crow's flight — so a station the graph cannot reach is not a candidate at
any distance. The choice and both distances go in `logs/fleet.log` at the
moment of choosing.

**The queue is FIFO and a promise.** Only the head is ever placed: if nobody
idle can take it, everything behind it waits. A task interrupted by a lost
vehicle **returns to the head**, not to the back (owner ruling) — it is the
oldest work in the cell and re-queueing it behind newer work would punish it
twice.

**The status document is the operator's screen, and its ages are computed
when it is built.** `fleet/status` is retained, QoS 1, republished on every
change and at least every 2 s. A feed that died shows an age that *grows* — a
vehicle nobody has heard from can never read as EN-ROUTE. The CLI prints the
document's own age in its header for the same reason: the manager sets no
last-will, so a retained document going stale *is* the fleet's death
certificate, and a stale timestamp cannot lie the way a "manager: ALIVE" flag
can.

**The screen is trimmed; the book is not.** The document carries every task in
flight plus the last five `DONE` and a `done_count`; the manager's own list
keeps all of them, because that list is what refuses a duplicate task id for
the whole run. `REFUSED` keeps the last ten and each task's history the last
twenty entries — a retained document republished every 2 s must not grow with
the shift.

**No journal, and the screen says so.** The queue is in memory. A restarted
manager re-syncs from the wire alone — retained `connection` topics, then the
states — and therefore has **no tasks**: the operator resubmits. A truck still
driving one of its `ft-` legs is simply not idle, so the restarted manager
adopts it **by waiting** and never cancels anything at startup.

**`cancelOrder` exists in exactly two flows, and both are the same sentence:
the fleet has taken a task away from a truck that is still driving its
order.** The first is a vehicle that was *lost* and comes back holding an
order somebody else now owns — the M6.2 agent *resumes* a kept order on
reconnect, so the returning truck may drive for the seconds the cancel takes
to land, and PROOF.md's M6.3 Gate 4 measures that window rather than
pretending it away. The second joined at M6.5: a truck **requeued out of a
swap deadlock**. Without a cancel it goes on driving an order no task owns,
never reports idle, and `_idle_floor` will not age a vehicle executing an
order the fleet does not own — so its node stays held for the rest of the
run. That is not a hypothesis: it is what M6.5's Gate 3 measured, and the
cancel is the truck's path back to eligibility.

**A truck that cannot yield is asked to STEP ASIDE.** Wait-die breaks a
deadlock by making the youngest task give up floor — which works when what it
gives up is floor *ahead* of it, and does nothing at all when the contested
element is the **ground under a vehicle**. M6.5's Gate 3 measured both shapes
in one run: one `UNRESOLVABLE` refusal, and the same line logged **3,180
times at 10 Hz for five minutes** while a yield freed four elements and none
of them was the one the blocked truck wanted. So the fleet now moves a truck:
the younger cycle member is cancelled, its task requeued to the head, and it
is sent a **one-node order** to a free node next door — `ft-`-prefixed, built
by `order_builder`, validated by the vehicle's own door and published through
the same funnel as any leg.

The choice of node is pure and is tested on its own
(`floor.step_aside_target`): a graph **neighbour** of the truck's own node,
whose node *and* whose edge are free, preferring floor that is **not on the
route of the trucks it is blocking**, then **not a spur junction**, then the
**nearest**. It is bounded at both ends — **no free neighbour** falls back to
M6.5's named refusal, which is the honest floor; **`ASIDE_MAX` (3)** moves by
one truck without an arrival in between stops the shuffling and names it; and
a move that has not finished in `ASIDE_S` (60 s) is given up and said out
loud. It is never a mystery drive: the traffic block carries an `aside` row
and the CLI prints `step aside: f3 (0.0,-5.5) -> (0.0,5.7) to clear f2`.

**Losing the fleet degrades, it does not endanger.** Kill the manager and
every truck keeps its current order, the on-board guards keep guarding, the
F-CPU keeps the safety chain, and the e-stop is still the brake. Nothing in
`fleet/` can command anything but a route and a cancel. The three standing
invariants this layer is written under are in
**[`fleet/README.md`](fleet/README.md)**; the design is
`docs/superpowers/specs/2026-08-21-m6-3-fleet-manager-design.md`.

---

# Inherited reference — Step 5's manual, below

**Everything from here down came across with `cp -r step5 step6 (now /m6)` and describes
the ANCESTOR.** The mechanisms are m6's — the mux seam, the arrival radius
rule, the sketch panel, the field contract, "Not a bug" — but the NAMES are
step5's. Wherever the text below says:

| It says | Step 6 means |
|---|---|
| `/forklift/plc/status`, `/hmi/cmd_vel`, `/vehicle/cmd_vel`, … | `/f1/...` … `/f4/...`, one set per truck |
| `5100` / `5101` | `5110` / `5111` for f1, then +10 per truck to `5140` / `5141` for f4 |
| `step5.sh`, `step5.py`, `m5_ver2/step5/` | `m6.sh`, `m6.py --vehicle <vid>`, `m6/` |
| `GZ_PARTITION=step5`, `ROS_DOMAIN_ID=95` | `m6`, `96` |
| "nine pids" | thirty-nine (nine per truck + broker + world + fleet; seventeen before M6.2, twenty before M6.3, twenty-one at two trucks) |
| `agv/forklift/config.yaml` as the vehicle's config | `vehicles/<vid>/config.yaml`, derived from it |

**Do not copy a command out of the text below and run it.** The run order at
the top of this file is the one that is current. Nothing below has been
re-measured on this tree — the numbers in *Measured, so you know what good
looks like* are step5's, on one vehicle, and `PROOF.md` is the only ledger for
m6's own claims.

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
plans over a fixed graph of corridor centrelines — a closed ring
(`x = ±20.00`, `y = ±10.00`, 120 m round), a spine down `x = 0.00`, one
pick aisle along `y = 0.00`, and one spur per station with plain Dijkstra, so a route that exists drives aisle middles
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

The twelve stations, with the arrival radius each one declares — and it
is the same radius twelve times, which is the point of M6.6's floor:

| id | name | pose (x, y) | spur | `arrive_m` |
|---|---|---|---|---|
| S1 | PICK-NW-1 | (-13.0, 3.30) | 3.30 | 0.25 |
| S2 | PICK-NW-2 | (-7.0, 3.30) | 3.30 | 0.25 |
| S3 | PICK-SW-1 | (-13.0, -3.30) | 3.30 | 0.25 |
| S4 | PICK-SW-2 | (-7.0, -3.30) | 3.30 | 0.25 |
| S5 | PICK-NE-1 | (7.0, 3.30) | 3.30 | 0.25 |
| S6 | PICK-NE-2 | (13.0, 3.30) | 3.30 | 0.25 |
| S7 | PICK-SE-1 | (7.0, -3.30) | 3.30 | 0.25 |
| S8 | PICK-SE-2 | (13.0, -3.30) | 3.30 | 0.25 |
| S9 | DOCK-DOOR | (-14.0, -15.30) | 5.30 | 0.25 |
| S10 | CHARGE-1 | (-6.0, -15.30) | 5.30 | 0.25 |
| S11 | CHARGE-2 | (6.0, -15.30) | 5.30 | 0.25 |
| S12 | CONVEYOR | (14.0, -15.30) | 5.30 | 0.25 |

**Nothing declares 0.80 any more, and no code was relaxed to get there.**
A vehicle cannot reach a point inside its own turning circle: measured
2026-08-13 at the old S7, a 0.85 m spur produced a stable orbit at
0.643–0.742 m and six of the ten stations had to declare 0.80 m to catch
the first pass. The floor is now drawn with no short spurs — the
shortest is 3.30 m — so the loosened radius has nothing to apply to.

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
| **The four trucks do not all start at full speed.** | `V_Limit` again, and this time the floor is the obstacle. A truck whose 2.5 m warning field is occupied gets `V_Limit` 300 from the F-program and `cmd_gate` clamps to it, so a pose or a corner near a rack face means 0.30 m/s until it clears. That is the field doing its job, and `follower.CORNER_MPS` is 0.30 m/s anyway, so a warning drop *through a corner* costs nothing. **What was a defect and is now fixed is a PARKED pose inside its own field**: f3 and f4 shipped 1.82 m and 2.32 m from the end walls, crawled from their first cycle, and f3 could not turn south out of its own spawn pose without latching PROTECTIVE (PROOF, M6.5 Gate 4). Both moved; `tests/test_vehicles_table.py` now measures the rule off the world SDF. See [Where the parked trucks stand](#where-the-parked-trucks-stand-and-why-it-is-a-fleet-decision). |
| **A box spawned into the running world is invisible to the guard — and to all three safety scanners.** | Measured on this machine: runtime-spawned models return nothing from any `gpu_lidar` here. It is a platform property, not a Step 5 defect. Obstacle work must pre-seed geometry into the world file. Obstacle HOLD as a capability was descoped by the owner on 2026-08-13; PROOF.md records the parked design and its evidence. |
| Steering still responds while traction is dead (teleop). | Deliberate. If the joystick went dead too, you could not tell a safety stop from a broken HMI — which is the one thing this window exists to distinguish. `angular.z` is therefore a steer *angle*, commanded directly. |
| **The joystick knob greys out and moves nothing in Auto.** | Display only. The mux ignores `/hmi/cmd_vel` while auto is selected, so the knob would be lying if it looked live. Switch the radio back to Teleop and it is live again on the next message. |
| `forklift_io` logs `waiting for source data: joint_states=False, odom=False` every 5 s, forever — **even though Step 5 bridges odometry.** | Two different names. Step 5 bridges `topics.gz_odom` (`/forklift/gz/odom`), which is what `nav_node` and the sketch consume; `forklift_io` subscribes to `topics.odom` (`/forklift/odom`), the renamed ROS name nothing publishes here. Joint states remain deliberately unbridged — no consumer. The warning gates only two derived state scalars and the fork target seed, never the traction or steer command path. |
| **The Gazebo window is slow, and the real-time factor in its bottom bar sits well under 1.** | Check `echo $GALLIUM_DRIVER` first. Empty means rendering is llvmpipe *software* rasterisation: WSLg exposes `/dev/dri`, OGRE binds it over EGL and Mesa falls back to `kms_swrast` (`sim/setup/WSL_ENVIRONMENT.md` §4.7 — which concluded "there is no GPU here", and that conclusion was **wrong**: measured 2026-08-22, the RTX 4050 is reachable through D3D12, see [The GPU condition](#the-gpu-condition--two-exports-in-your-shell)). With the exports set the renderer is the NVIDIA card and four trucks hold 0.58–0.69. Either way a headless run of this world is faster than a windowed one, and nothing in the command path reads the clock rate, so this costs appearance and not correctness. |
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
| `hmi/map_panel.py` | `SCALE` | `11.0` | px per metre. WIDTH and HEIGHT are DERIVED from `stations.HALL` rather than written down, so a floor change moves the frame with its contents: 48 x 32 m -> 528 x 352 px |
| | `PICK_RADIUS_PX` | `12.0` | click tolerance on a station dot |
| `ipc/route.py` | `RING_X` / `RING_Y` | `±20.0` / `±10.0` | the ring's four centrelines. 8.00 m clear, so `8.00/2 − 0.46 = 3.54 ≥ FIELD_SLOW_M` and a truck runs at `CRUISE_MPS` on every metre of it |
| | `SPINE_X` / `PICK_Y` | `0.0` / `0.0` | the spine is highway at 8.00 m; the pick aisle is 5.00 m and is therefore a CREEP corridor by construction, not by accident |
| | `NORTH_X` / `SOUTH_X` / `PICK_X` / `LEG_Y` | see the file | node positions. `NORTH_X` carries `±12` and `±6` because those are the four spawn poses and each truck must snap to its own node |
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

## Unit tests — m6's own, and the number to expect

**`485 passed, 0 skipped`** under WSL (the M6.5 fix-up — it was 370 at
M6.2, 466 at the M6.5 gate run, and the nineteen new ones are the three
parked-truck field rules, the nine the step-aside brought with it, the
three that pin the two speed bands to the field thresholds they protect
rather than to a number, and the four that hold the scan-fault branch to
diagnosis and out of the verdict):

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m6/tests/ -q
```

**The `source` line is not optional and its absence does not look like a
missing source.** Skip it and the suite aborts with `Interrupted: 7 errors
during collection` before a single test runs, because `tests/conftest.py`
imports `rclpy` — the same seven errors Windows gives, for the same reason.
`m5_ver2/step5/tests/` behaves identically. A clean-shell run of either suite
reads like a catastrophic failure and is nothing of the kind.

A **skip** is a failure here: it means a module did not import and its tests
silently did not run. On Windows the same suite gives `222 passed, 5 skipped,
7 errors` with `--continue-on-collection-errors` — the seven are `No module
named 'rclpy'` and the five skips `No module named 'paho'` (the two MQTT
integration files, the two fleet-CLI/manager unit files and the send_order
probe), neither of which Windows has or is supposed to.

## Validation checklist

**Step 6's ledger is [PROOF.md](PROOF.md), and every gate in it is now
measured.** All six of the M6.1 spec's proof gates, M6.2's six, M6.3's six,
M6.4's six and M6.5's five, output kept — M6.1's Gate 1 as a *two-vehicle*
RTF gate on llvmpipe, which M6.5 re-measured at four vehicles on the GPU and
then again under the full 39-pid stack during the acceptance run (see [The GPU
condition](#the-gpu-condition--two-exports-in-your-shell)).

**Three gates are measured and NOT ticked, and that is the ledger working.**
M6.5's Gate 3 (0 of 4 transports), Gate 4 (the acceptance run) and Gate 5 each
stand `[ ]` with their runs written up in full — twice over for 3 and 4, because
the 2026-08-22 fix-up re-ran them after the poses and the step-aside were fixed
and **the acceptance run then stopped for a different reason**: 31 s in, all
four trucks latched inside 0.56 s on scanners reporting `d = 0.000`, which is
`field_eval`'s *"a broken device is not an empty room"* answering scans a stack
at an instantaneous RTF of **0.010** never delivered. Three of the four trucks
had by then driven a nine-minute traffic gate **without dropping Motor once**,
which no four-vehicle run had managed before. M6.4's Gate 2 is closed by M6.5's
Gate 2. Nothing here is ticked on the strength of a copied file, and **an
unticked gate is not a passed one**.

Every gate above was machine-measured. The numbered runbooks at the foot of
PROOF.md are kept for the owner's hands-on re-run, which needs **four**
Windows writers and a hand on four panels: one action per step, and where to
write the number down.
