# EVIDENCE_LATENCY.md — measured bridge performance

Date of run: **2026-07-27** (08:49:14 – 08:52:34 UTC)
Host: Linux 6.18.5 x86_64, container, CPU only, no display
ROS 2 Jazzy, Gazebo Sim 8.11.0 (Harmonic), Python 3.12.3, `asyncua` 2.0.1
Raw per-event rows: **`evidence/latency-2026-07-27.csv.gz`** (76 191 rows)

This file has three clearly separated sections. **Section A** is the
in-container run against the test double, produced by m3-04. **Section B** is
the run against PLCSIM Advanced, which the owner executes and on which the M3
gate closes (`bridge-design.md` §9.4). **Section C** is a short WSL run added
by m3-13. Section B carries no measurement yet; its **§B.0** records the
commissioned target environment (commissioning phase 0, 2026-07-27) that those
measurements will run against.

**Scope of Section A.** It was captured before the panel reset existed, so its
input image is the six nodes of the day and every "all six" in it is a true
statement about that run. The cell has carried `/cell/panel/reset` since
`adc9cd0` and the node model has carried `DemoCell/Input/PanelResetPressed`
since `79a7f1e`, which makes the input image **seven** nodes from m3-13 onward.
Section A is not re-run or edited here (LESSONS 2026-07-27: evidence is
qualified by the environment that produced it); Section C records the seven-node
behaviour on its own date and platform. Section B item 5 is written against six
inputs and should be read as "all inputs".

---

# Section A — test double, in-container, agent-run

> Every number in this section was produced against
> `bridge/test_double/plc_test_double.py`, a Python OPC UA server, over
> loopback. **It is not a PLC.** It has no scan cycle, no process image and no
> program. See §A.7 for what that means for each figure.

## A.1 Configuration

| Item | Value |
|---|---|
| Server | test double, `opc.tcp://127.0.0.1:4840/amr-agent/celldouble/`, loopback, security `None` |
| Namespace | `urn:amr-agent:cell:plc`, resolved by browsing to index **2** (never hardcoded) |
| Nodes resolved | 14, by BrowseName path, once per session; all DataTypes verified against opcua-nodes.md §9 |
| Cycle period | 50 ms (20 Hz target) |
| Status poll | 1 Hz, logged only |
| Cell | `sim/launch/cell_bringup.launch.py`, headless, fresh start (belt 0.000 m, product at −1.000 m) |
| Simulator | 2 ms fixed step, **real-time factor 0.9979** (`gz topic -e -t /stats`) |
| Run duration | **200.0 s**, 4000 cycles |
| Instrumentation | always on; the measured code path is the production code path |

Run script: the double, the cell, the bridge (`--duration 200`) and the panel
stimulus are started in that order; `DemoCell/Output/ConveyorSpeedCommand` is
driven through the double's S1 scaffolding to
`0.15 → 0.0 → −0.15 → 0.0 → 0.15 → 0.0 → −0.15 → 0.0` m/s, and the three panel
contacts are toggled on a fixed timeline. Two full product traverses of the
photo-eye beam in each direction are included, plus a process-stop press and a
stop press.

## A.2 Both directions carried real values

**Cell → PLC.** Server-side observation from the double (5 Hz sampling of its
own address space). Value transitions, monotonic seconds on the double's host:

```
ProductSensorRange     4283.6  1.4400883913040161   beam clear
                       4317.0  0.7455381751060486   product edge entering the beam
                       4317.2  0.5400331616401672   BEAM BLOCKED
                       4319.2  1.4400883913040161   BEAM CLEAR
                       4374.3  0.5400331616401672   blocked again (reverse traverse)
                       4376.3  1.4400883913040161   clear
                       4415.7  0.5400331616401672   blocked (3rd traverse)
                       4417.7  1.4400883913040161   clear
                       4454.3  0.5400331616401672   blocked (4th traverse)
                       4456.3  1.4400883913040161   clear
PanelStartPressed      4267.9 False -> 4306.1 True -> 4307.2 False -> 4426.1 True -> 4427.1 False
PanelStopCircuitClosed 4267.9 False -> 4286.2 True -> 4386.2 False -> 4391.2 True
PanelProcessStop…      4267.9 False -> 4286.2 True -> 4346.1 False -> 4361.2 True
ConveyorBeltPosition   continuous, 20 Hz, 0.000 -> 2.500 -> 0.256 (mechanical stops at ±2.50 m)
```

The 1.440 m / 0.540 m levels are exactly those `sim/worlds/CELL_EVIDENCE.md`
recorded for the cell, carried to the PLC input image as a **raw range**. No
threshold is applied anywhere in the bridge; `DemoCell/Status/ProductPresentAtSensor`
stayed `False` for the whole run because the double has no program to form it.

**PLC → cell.** `DemoCell/Output/ConveyorSpeedCommand` was set on the double
only (the bridge never writes it — §A.5). The belt ran and the product was
carried:

```
wall_s   sim_s   box_x    belt_pos  belt_vel  range
 20.15    32.1   -1.0      0.0      -0.0      1.4401     command 0.0
 30.50    42.1    0.2833   1.284     0.15     1.4401     command 0.15, product carried
 40.50    52.1    1.4999   2.5       0.0      1.4401     belt at the +2.50 m mechanical stop
 90.67   102.1    0.2463   1.2454   -0.15     1.4401     command -0.15, reversing
100.76   112.1   -0.739    0.2611   -0.0      1.4401     command 0.0
130.83   142.1    0.5431   1.5439    0.15     0.54       product standing in the beam
```

`box_x` tracks `belt_pos` with a constant −1.000 m offset for the whole run:
the product is **carried by the belt**, not teleported. The command reached the
cell unchanged — `ros2 topic echo /cell/conveyor/cmd_speed --once` during the
forward move returned `data: 0.15000000596046448`, which is the `Float`
round-trip of 0.15 widened back to `float64`, i.e. the narrowing is visible and
is the only numeric operation performed.

## A.3 Startup rule (§6) — no heartbeat until every input is real

Bridge log, first seconds:

```
08:49:14,806 namespace urn:amr-agent:cell:plc resolved to index 2
08:49:14,825 all node DataTypes match opcua-nodes.md §9
08:49:14,825 session established, 14 nodes resolved
08:49:14,826 heartbeat withheld: no real sample yet for ConveyorBeltPosition, ConveyorBeltSpeed,
             ProductSensorRange, PanelStartPressed, PanelStopCircuitClosed,
             PanelProcessStopCircuitClosed (startup rule R3)
08:49:14,880 heartbeat withheld: no real sample yet for ProductSensorRange, PanelStartPressed,
             PanelStopCircuitClosed, PanelProcessStopCircuitClosed (startup rule R3)
08:49:14,980 heartbeat withheld: no real sample yet for PanelStartPressed,
             PanelStopCircuitClosed, PanelProcessStopCircuitClosed (startup rule R3)
08:49:17,682 heartbeat withheld: no real sample yet for PanelStartPressed,
             PanelStopCircuitClosed (startup rule R3)
08:49:17,732 startup rule satisfied: all six DemoCell/Input nodes carry a real cell
             sample; heartbeat begins advancing at 1
```

Server side, the same instant (columns: wall, monotonic, sessions, heartbeat,
BeltPosition, BeltSpeed, Range, Start, Stop, ProcessStop, SpeedCommand):

```
08:49:17.364  4285.828  1  0  2.636e-22  1.022e-28  1.440088  False  False  False  0.0
08:49:17.565  4286.029  1  0  2.636e-22  2.306e-28  1.440088  False  False  False  0.0
08:49:17.766  4286.230  1  1  2.636e-22  1.159e-28  1.440088  False  True   True   0.0
08:49:17.967  4286.431  1  5  2.636e-22 -1.917e-28  1.440088  False  True   True   0.0
```

The heartbeat advances from 0 for the first time in the same 200 ms window in
which the two stop contacts first carry real values. Analog values were being
written some seconds earlier (R2: each input node is written as soon as its own
source produces a sample); the heartbeat waited for **all six**.
Counters: `heartbeat_suppressed_cycles = 58` (2.9 s), `heartbeat_writes = 3942`.
The PLC-side predicate of §6.2 therefore holds for this run.

## A.4 Statistics — count, min, median, p95, max (never a bare mean)

Milliseconds. p95 is the nearest-rank percentile. Produced by
`tools/summarize_latency.py` from the raw CSV.

| ID | signal | clock | count | min | median | p95 | max |
|---|---|---|---|---|---|---|---|
| L1 | `ConveyorBeltPosition` | monotonic | 3999 | 0.427 | 1.307 | 2.418 | 314.698 |
| L1 | `ConveyorBeltSpeed` | monotonic | 3999 | 0.246 | 0.803 | 2.440 | 315.358 |
| L1 | `ProductSensorRange` | monotonic | 3997 | 0.305 | 17.115 | 32.450 | 330.188 |
| L1 | `PanelStartPressed` | monotonic | 5 | 11.239 | 11.990 | 47.423 | 47.423 |
| L1 | `PanelStopCircuitClosed` | monotonic | 3 | 11.629 | 11.992 | 48.273 | 48.273 |
| L1 | `PanelProcessStopCircuitClosed` | monotonic | 3 | 11.677 | 12.427 | 13.323 | 13.323 |
| L2 | `ConveyorBeltPosition` | monotonic | 3999 | 0.442 | 1.026 | 1.695 | 22.566 |
| L2 | `ConveyorBeltSpeed` | monotonic | 3999 | 0.302 | 0.878 | 1.576 | 44.065 |
| L2 | `ProductSensorRange` | monotonic | 3997 | 0.307 | 0.857 | 1.574 | 10.684 |
| L2 | `PanelStartPressed` | monotonic | 5 | 0.744 | 0.932 | 1.168 | 1.168 |
| L2 | `PanelStopCircuitClosed` | monotonic | 3 | 0.804 | 0.967 | 1.203 | 1.203 |
| L2 | `PanelProcessStopCircuitClosed` | monotonic | 3 | 0.474 | 0.479 | 1.055 | 1.055 |
| L2 | `BridgeHeartbeat` | monotonic | 3942 | 0.277 | 0.845 | 1.528 | 22.262 |
| L3 | `ConveyorBeltPosition` | monotonic | 3999 | 1.078 | 2.464 | 3.617 | 315.350 |
| L3 | `ConveyorBeltSpeed` | monotonic | 3999 | 0.685 | 2.042 | 3.520 | 315.986 |
| L3 | `ProductSensorRange` | monotonic | 3997 | 0.843 | 18.054 | 33.447 | 330.820 |
| L3 | `PanelStartPressed` | monotonic | 5 | 12.265 | 12.795 | 48.296 | 48.296 |
| L3 | `PanelStopCircuitClosed` | monotonic | 3 | 12.798 | 12.835 | 49.242 | 49.242 |
| L3 | `PanelProcessStopCircuitClosed` | monotonic | 3 | 12.153 | 13.490 | 13.804 | 13.804 |
| L5 | `cmd_speed` | monotonic | 4000 | 0.057 | 0.109 | 0.167 | 1.152 |
| L6 | `cmd_speed → belt_velocity ≥ 50 %` | **sim** | 4 | 4.000 | 4.000 | 4.000 | 4.000 |
| R1 | cycle period | monotonic | 3999 | 22.008 | 50.003 | 51.023 | 79.179 |
| R2 | `ConveyorBeltPosition` | monotonic | 3998 | 21.255 | 50.016 | 51.239 | 79.342 |
| R2 | `ConveyorBeltSpeed` | monotonic | 3998 | 21.182 | 49.990 | 51.517 | 80.010 |
| R2 | `ProductSensorRange` | monotonic | 3996 | 7.096 | 49.994 | 51.745 | 92.345 |
| — | OPC UA read round trip (`ConveyorSpeedCommand`) | monotonic | 4000 | 0.504 | 0.916 | 1.706 | 30.440 |

**Achieved cycle rate: 19.99 Hz** (3999 intervals in 200.0 s; median period
50.003 ms). Per-node achieved write rate: `ConveyorBeltPosition` 19.99 Hz,
`ConveyorBeltSpeed` 19.99 Hz, `ProductSensorRange` 19.98 Hz. The three contacts
are written **on change** (§5), so their rate is not a cadence:
`PanelStartPressed` 5 writes, `PanelStopCircuitClosed` 3, `PanelProcessStopCircuitClosed`
3, in 200 s — one per commanded transition plus the connect refresh, and none
for the 1 Hz republished identical levels.

The 20 Hz expectation of `opcua-nodes.md` §9.2 is met (open item 7 of the
design closes without a revision): the median period is 50.003 ms and there
were **0 cycle overruns**.

### R3 decimation ratio — discarded samples contributed to nothing

| signal | samples received | samples written | ratio |
|---|---|---|---|
| `ConveyorBeltPosition` | 98 937 | 3 999 | 24.74 : 1 |
| `ConveyorBeltSpeed` | 98 937 | 3 999 | 24.74 : 1 |
| `ProductSensorRange` | 6 021 | 3 997 | 1.51 : 1 |
| `PanelStartPressed` | 196 | 5 | 39.20 : 1 |
| `PanelStopCircuitClosed` | 194 | 3 | 64.67 : 1 |
| `PanelProcessStopCircuitClosed` | 194 | 3 | 64.67 : 1 |

98 937 belt samples arrived (≈495 Hz, the physics rate) and 3 999 were written.
The other 94 938 were overwritten in a depth-1 slot and contributed to nothing:
no average, no edge count, no travel integral — there is no data structure in
the bridge that could hold them.

### Counters for the run

| counter | value |
|---|---|
| cycles | 4000 |
| cycle_overruns (> 50 ms) | **0** |
| write_errors | 0 |
| read_errors | 0 |
| reconnects | 0 |
| publishes on `/cell/conveyor/cmd_speed` | 4000 |
| heartbeat_writes | 3942 |
| heartbeat_suppressed_cycles | 58 |
| non-finite `ProductSensorRange` samples | 0 |
| JointState messages without `belt_joint` | 0 |
| empty `LaserScan.ranges` | 0 |

### QoS observed at startup (§4.6)

```
/cell/conveyor/joint_state : publisher RELIABLE VOLATILE
/cell/product_sensor/scan  : publisher RELIABLE VOLATILE
/cell/panel/start          : publisher RELIABLE VOLATILE
/cell/panel/stop           : publisher RELIABLE VOLATILE
/cell/panel/process_stop   : publisher RELIABLE VOLATILE
/cell/conveyor/cmd_speed   : 1 subscriber, RELIABLE
```

Subscriptions are `KEEP_LAST` depth 1 (`RELIABLE`, `VOLATILE`) on all five, so
reliability matches the publisher and no subscription is silently starved.

## A.5 Reading the numbers

* **L1 is decimation age, not cost.** It is the time a sample sits in its slot
  before the cycle takes it. For the ~500 Hz belt encoder that is a fraction of
  the 2 ms source period (median 1.3 ms); for the 30 Hz photo-eye it is roughly
  uniform over the 33 ms source period (median 17.1 ms, p95 32.5 ms). Neither
  is a latency the bridge adds — it is the price of writing at 20 Hz instead of
  at the source rate, and it is reported separately for exactly that reason.
* **L2 is the bridge's own cost**: serialisation plus the OPC UA round trip
  plus the server's write handling. Median ≈ 0.9–1.0 ms, p95 ≈ 1.6 ms over
  loopback to a Python server.
* **L3 = L1 + L2** measured end to end from the same clock (not by adding
  statistics). Belt inputs: median 2.0–2.5 ms, p95 ≈ 3.6 ms. Photo-eye: median
  18.1 ms, p95 33.4 ms, dominated by L1.
* **The maxima are real and are not clipped.** The ~315 ms L1/L3 outliers are
  single events where no new ROS sample arrived for that long (one per signal
  in 200 s; p95 stays at 2.4 ms). The 79 ms R1 maximum and the 22 ms minimum
  are the same event seen from the cycle: an overrun-free but jittery pair of
  cycles. The bridge logs and counts such events and **never compensates** for
  them — no catch-up burst, no skipped-cycle logic.
* **L5 is small because it is only the publish call** (0.11 ms median). It is
  the bridge-attributable part of the PLC → cell path; the transport time to
  gz and the actuation are L6 and the simulator's business.
* **L6 is a simulator property, not a bridge property**, and is measured in
  **sim time**: 4.000 ms in all four command changes, i.e. two 2 ms physics
  steps for the belt to reach 50 % of the commanded velocity. RTF 0.998 makes
  the sim-time and monotonic domains comparable, but they are never
  differenced against each other.

### A measurement-definition correction (reported, not silently applied)

`bridge-design.md` §9.2 defines **L1** as "subscriber callback entry → start of
the cycle that writes it". With the ROS callbacks on their own thread, a sample
can arrive **after** the cycle start and still be the one written, which makes
that interval negative. Both reference points are therefore recorded:

* `L1` (the table above) ends when the cycle takes the sample out of its slot —
  the true hold time, never negative;
* `L1cs` (raw CSV only) ends at the cycle start, the literal §9.2 wording, and
  is negative for 30–50 % of belt samples (min −23.6 ms for `ConveyorBeltSpeed`,
  min −45.9 ms for `ProductSensorRange`). Nothing is clipped.

The difference between the two is the output path of the same cycle (the read
round trip plus the publish, ≈1.0 ms median). §9.2 should be amended to the
slot-take wording; that is `docs/interfaces/bridge-design.md`'s change to make,
not this file's.

## A.6 What was not measured, and why

| ID | Status |
|---|---|
| **L4** (output poll phase) | **Not measurable from the bridge**, by construction: it requires observing the instant the value changes inside the PLC, which no client can see. Stated as a **bound**: ≤ one cycle period (50 ms) plus the server's own sampling, ≈ uniform over 0–50 ms for a change that is not synchronous with the cycle. This is the honest cost of polling instead of subscribing (§5.1) |
| **L7** (closed loop) | **Not measured.** It requires the server to respond to a nominated input — the PLC program, or the double's S3 echo scaffolding. Against the double it would be a transport floor, not a loop time (§9.5), and the brief scopes this run to L1/L2/L3/L5/L6. The S3 hook exists (`--echo-input`) so the owner or a later brief can take it |

## A.7 What this section cannot establish (§9.5)

| Not measurable in-container | Why |
|---|---|
| PLC scan-cycle contribution | The double has no scan cycle |
| S7-1500 OPC UA server behaviour | Its sampling of the process image, write handling relative to the scan, session and monitored-item limits — a Python server reproduces none of them |
| PLCSIM Advanced vs hardware timing fidelity | PLCSIM's timing is not the hardware's |
| Network path | Loopback: no switch, no VPN, no PROFINET load. **Every number here is a lower bound** |
| The PLC's reaction to a stale heartbeat | A property of the PLC program (`plc/demo-cell/SPEC.md`), not of the bridge |
| Anything about `DemoCell/Status/*` | They stayed `False` for 200 s because the double has no program. `BridgeLinkOk` likewise |

One property of the demonstration cell, recorded because it is a real limit and
not a defect: while the bridge is down **no command can reach the cell**, and
gz's `JointController` holds the last velocity it was given, so the belt keeps
running (see `EVIDENCE_SIGNAL_LOSS.md`, cases A and C). On real equipment the
drive is dropped by a wired enable/contactor, not by an OPC UA value; the
simulated cell has no such wiring. No safety function is involved and none is
claimed (invariant 1).

---

# Section B — PLCSIM Advanced, owner-run

**Not yet performed. The M3 gate closes on this section, not on Section A.**

To be captured by the owner, on the engineering workstation, with the S7-1500
standard program of `plc/demo-cell/SPEC.md` (m3-05) loaded into PLCSIM
Advanced and the bridge pointed at it by configuration only
(`opcua.endpoint`, plus the security fields if the server requires them — no
code change).

## B.0 Commissioned target environment — commissioning phase 0, owner-verified in tool 2026-07-27

This subsection is an **environment record, not a measurement**. It states the
stack that phase 0 of commissioning brought up and that the owner-executed
capture list below will run against. Every figure Section B asks for is still
outstanding. It answers **item 1** of that list for the stack *as commissioned*;
confirming it at measurement time stays with the owner, together with the two
elements phase 0 did not fix — the CPU's configured scan cycle, and the network
path in use at that moment with the confirmation that Tailscale is not in it
(invariant 8).

**What phase 0 proves: the endpoint and the node exposure, and nothing else.**
No PLC program logic ran, and the bridge was not involved in any part of it —
so no statement about the standard program, about bridge latency or about the
signal-loss reactions is made or implied here.

| Item | Value (owner-verified in the tool, 2026-07-27) |
|---|---|
| Engineering tool | TIA Portal **V21** |
| Simulator | **S7-PLCSIM Advanced V7.0**. V3.0 was removed: broken virtual adapter service, and not supported with TIA V21 |
| Target | Simulated, **not hardware**: a PLCSIM Advanced instance |
| CPU | **CPU 1513-1 PN**, firmware **V3.1** |
| OPC UA runtime license | **large**. The compiler demanded large after the firmware change; small was not accepted |
| Instance networking | TCP/IP **Single Adapter**, `<Local>`; instance IP **192.168.53.1/24**, host virtual adapter **192.168.53.241/24** |
| OPC UA endpoint | **`opc.tcp://192.168.53.1:4840`** |
| Security | policy **None**, **anonymous** access via the CPU-level *Disable access control* setting (V3.x firmware exposes no guest-authentication checkbox) |
| Browse path | `Objects` → `ServerInterfaces` (Siemens namespace `http://www.siemens.com/simatic-s7-opcua`) → `DemoCell` (namespace **`http://DemoCell`**, ADR 0006) |
| Session timeout | requested **3 600 000 ms**, granted **30 000 ms** — the server clamps it |

### B.0.1 Independent verification, 2026-07-27

**15 `DemoCell` nodes were read with an `asyncua` client from Windows, all at
their start values. The bridge was not involved.** 15 is exactly the node set
`bridge/config/bridge.yaml` resolves today: 7 `Input/`, `Link/BridgeHeartbeat`,
`Output/ConveyorSpeedCommand`, 5 `Status/` and `Link/BridgeLinkOk`. Section A
and the runs of `EVIDENCE_SIGNAL_LOSS.md` log "14 nodes resolved" because they
predate `Input/PanelResetPressed` (§C); the exposed interface therefore matches
`opcua-nodes.md` §9 as it stands, with no node missing and none extra.

### B.0.2 What this subsection does not establish

Reading a node at its start value is not evidence about a program. In phase 0
every `DemoCell/Status/` node was at its start value **because nothing had run**,
not because a program formed it — the distinction that `§A.7` and
`EVIDENCE_SIGNAL_LOSS.md` ("What none of this establishes") already draw for the
test double applies here for a different reason. Phase 0 adds **no** measurement:
no scan-cycle contribution, no OPC UA server timing under load, no L4/L7, no
network path under PROFINET load, and nothing about the four signal-loss cases.

### B.0.3 Consequences for the pending run, as facts

1. **The security fields stay as configured.** The server is `None` + anonymous,
   so `security_policy: "none"` with `certificate_path`, `private_key_path` and
   `username` null is the correct setting for this endpoint — invariant 13 is
   untouched because there is no secret to place.
2. **The requested session timeout is inside the server's clamp.**
   `session_timeout_ms` is 10 000 in config, below the 30 000 ms this server
   granted for a 3 600 000 ms request, so no clamp is expected on the bridge's
   request; the **granted** value is what the run should report, not the
   requested one.
3. **The browse root is not the same as the test double's, and this is not an
   endpoint-only change.** `bridge/config/bridge.yaml` resolves
   `[DemoCell, Input, <name>]` from the `Objects` folder with every element in
   the `DemoCell` namespace index. On this server `DemoCell` is nested one level
   deeper, under `ServerInterfaces`, and `ServerInterfaces` belongs to the
   **Siemens** namespace, not to `http://DemoCell` — so a single-namespace path
   from `Objects` cannot address it (`opcua-nodes.md` §2.1: two indices are
   resolved by URI at connect, neither is hardcoded, and the parent folder never
   shares the interface's namespace). No client change is made in this file;
   brief m3-21 owns it. It is recorded here because it qualifies the sentence
   above that only `opcua.endpoint` and the security fields change: against this
   server the *addressing* changes too, and until m3-21 lands, Section B cannot
   be captured.

Sections A and C are unaffected: each remains qualified by the environment that
produced it, and neither is re-run or edited here.

What the owner must capture:

1. **Environment** — PLCSIM Advanced version, TIA Portal version, CPU type and
   firmware, whether hardware or PLCSIM, the network path between the bridge
   host and the PLC (adapter, switch, any VPN — and confirmation that Tailscale
   is *not* in that path, invariant 8), and the PLC's configured scan cycle /
   OPC UA server settings.
2. **The same statistics table as §A.4**, produced by the same command:
   `tools/summarize_latency.py evidence/latency-<date>-plcsim.csv`. Same
   intervals, same statistics: count, min, median, p95, max — never a bare
   mean.
3. **L4 as a bound, plus the PLC's own view.** With the program running, the
   TIA watch table can timestamp the output change on the PLC side; report the
   poll phase as the bound it is, and say what the watch table showed.
4. **L7, the closed loop**, now that a real program responds to an input:
   bridge writes a nominated `DemoCell/Input/` value → PLC scan → the resulting
   `ConveyorSpeedCommand` read back. This is the only end-to-end number, and it
   includes one PLC scan.
5. **The startup rule against the real DB start values** — that
   `BridgeHeartbeat` does not advance until all six inputs carry real samples,
   and that the DB start values of §6.3 are what the program sees before that.
6. **The four signal-loss cases of `EVIDENCE_SIGNAL_LOSS.md` repeated against
   PLCSIM**, including what the standard program *does* in each (the reaction
   is PLC content: drop the cycle-running flag, command 0.0, require a
   monitored edge-triggered reset — and confirmation that a returning heartbeat
   alone does **not** restart the conveyor).
7. **Session behaviour on a real server**: how long the S7-1500 holds a session
   after a bridge SIGKILL, which is the one place the in-container result is
   known not to transfer (see `EVIDENCE_SIGNAL_LOSS.md` §A).
8. **A note on which server produced each number**, per `bridge-design.md` §10:
   the test double must never be running on the same endpoint during this run.

---

# Section C — WSL2, test double, agent-run, 2026-07-27 (m3-13)

Date of run: **2026-07-27** (14:56:38 – 14:57:23 local, `CLOCK_MONOTONIC`
9299–9347 s). Host: WSL2 Ubuntu 24.04, kernel
`5.15.167.4-microsoft-standard-WSL2`, headless, llvmpipe. Repo on `/mnt/c`.
Server: `bridge/test_double/plc_test_double.py` — **not a PLC**; §A.7 applies
here unchanged. Isolation: `ROS_DOMAIN_ID=88`, `GZ_PARTITION=m313bridge`.

**This is not a measurement run and it does not restate §A.4.** It exists to
show one property of the new seventh input, `PanelResetPressed`: that the
bridge never asserts it. The four measured signal-loss cases and the full
statistics table remain m3-08's and Section B's.

Run: `sim/launch/cell_bringup.launch.py` (headless), the test double, the
bridge for 45 s, and `tools/cell_stimulus.py` with a script that **deliberately
does not publish the reset for the first 15 s**:

```
0:stop=true,0:process_stop=true,0:start=false,15:reset=false,20:reset=true,22:reset=false
```

## C.1 Pre-first-publish: the node reads FALSE, because nothing writes it

Bridge log:

```
14:56:38,217 namespace urn:amr-agent:cell:plc resolved to index 2
14:56:38,236 all node DataTypes match opcua-nodes.md §9
14:56:38,242 heartbeat withheld: no real sample yet for ProductSensorRange, PanelStartPressed,
             PanelResetPressed, PanelStopCircuitClosed, PanelProcessStopCircuitClosed (R3)
14:56:38,744 heartbeat withheld: no real sample yet for PanelResetPressed (startup rule R3)
14:56:41,208 QoS /cell/panel/reset: publisher reliability=RELIABLE durability=VOLATILE
14:56:52,758 startup rule satisfied: all 7 DemoCell/Input nodes carry a real cell sample;
             heartbeat begins advancing at 1
```

For 14.0 s the bridge held an established session, wrote the other six inputs,
and wrote `PanelResetPressed` **not at all** (R1: no sample, no write). What
the server saw in that window, from the double's own observation log
(`--observe-csv`, 5 Hz, 84 samples before the first publish):

```
monotonic_s=9299.879  BridgeHeartbeat=0  StartPressed=False  ResetPressed=False  Stop=False  ProcessStop=False
monotonic_s=9300.084  BridgeHeartbeat=0  StartPressed=False  ResetPressed=False  Stop=False  ProcessStop=False
monotonic_s=9317.015  BridgeHeartbeat=4  StartPressed=False  ResetPressed=False  Stop=True   ProcessStop=True
```

The set of distinct `PanelResetPressed` values observed while
`BridgeHeartbeat == 0` is exactly `{False}`. That FALSE is the **server's own
start value**, not a bridge write: the bridge contributed nothing to it. The
same holds against the PLC, whose DB start value for this node is FALSE
(`opcua-nodes.md` §3.1) — so a bridge that starts, connects and finds nobody at
the panel cannot assert a reset, and cannot clear a latch (CLAUDE.md §9).

## C.2 The press traverses, as a level, on change only

Server-side transitions, from the same log:

```
row 108  monotonic_s=9321.920  BridgeHeartbeat=102  ResetPressed=True
row 118  monotonic_s=9323.967  BridgeHeartbeat=143  ResetPressed=False
```

Bridge-side rows for the node (`L2` = write start → server acknowledgement,
`L3` = ROS callback → acknowledgement), all three writes of the run:

```
L2   value=False start_ns=9316826185902  interval_ns=1 460 686
L3   value=False start_ns=9316779050089  interval_ns=48 596 499
L2   value=True  start_ns=9321828715949  interval_ns=1 394 253
L3   value=True  start_ns=9321779227547  interval_ns=50 882 655
L2   value=False start_ns=9323830541544  interval_ns=1 672 320
L3   value=False start_ns=9323779480525  interval_ns=52 733 339
```

Decimation for the run (`R3`, received/written): `PanelResetPressed 32/3`. The
stimulus republished the held level once a second, as a wired contact would be
re-read every scan; the bridge wrote three times, once per actual change. The
other three contacts show `43/1` — one write each, one level each, unchanged
for the whole run.

## C.3 The heartbeat now waits for seven

`heartbeat_suppressed_cycles = 290` (14.5 s at 50 ms) against `cycles = 900`,
`heartbeat_writes = 610`, `write_errors = 0`, `read_errors = 0`,
`reconnects = 0`, `cycle_overruns = 0`. The first heartbeat write
(`t_start_ns = 9316828172801`) is 2.0 ms after the first `PanelResetPressed`
write (`9316826185902`) — the same cycle, in the §2 order: inputs, then
heartbeat. The §6.2 predicate is therefore unchanged in meaning and stronger in
coverage: while the heartbeat advances, all **seven** inputs are attributable to
the running cell.

Consequence for any unattended run: the panel stimulus must publish the reset
at least once, or the heartbeat never starts. The default `--script` in
`tools/cell_stimulus.py` publishes `reset=false` at t=0 for exactly this
reason, and publishing FALSE asserts nothing — it is the resting level of a
normally open contact.

## C.4 L6 is scenario-dependent — added 2026-07-27, from m3-06

Not measured here. `docs/reports/m3-06-verify.md` ("One measurement divergence,
reported not smoothed") records a live WSL re-run in which **the verifier**
measured L6 (`cmd_speed → belt velocity ≥ 50 %`, sim time) at **2.000 ms** — one
physics step — for a 0.15 m/s command from rest mid-travel, and at
**1384.000 ms** for a −0.15 m/s command issued while the belt was pressed
against its +2.50 m mechanical stop (pose log `sim 52.8 belt_pos 2.5
belt_vel 0.0`), with nothing in the bridge different between the two.

The mechanism: **L6 depends on the belt's mechanical state at the instant the
command changes** — a `JointController` unwinding against a joint limit takes
orders of magnitude longer to reach half speed than one starting from rest — so
a single L6 figure quoted without its scenario is incomplete. §A.4's
`4.000 ms in all four command changes` remains correct for the container run it
describes and is unchanged above; it is not a general property of the cell, and
it is not a bridge latency in either case (§A.5: L6 is the simulator's).
