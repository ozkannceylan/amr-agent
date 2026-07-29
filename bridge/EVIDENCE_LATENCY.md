# EVIDENCE_LATENCY.md — measured bridge performance

Date of run: **2026-07-27** (08:49:14 – 08:52:34 UTC)
Host: Linux 6.18.5 x86_64, container, CPU only, no display
ROS 2 Jazzy, Gazebo Sim 8.11.0 (Harmonic), Python 3.12.3, `asyncua` 2.0.1
Raw per-event rows: **`evidence/latency-2026-07-27.csv.gz`** (76 191 rows)

This file has three clearly separated sections, one of which now has two parts.
**Section A** is the in-container run against the test double, produced by
m3-04. **Section B** is the run against **PLCSIM Advanced with the standard
program in RUN**, on which the M3 gate closes (`bridge-design.md` §9.4); it has
**two parts**, each a different day, a different program build and a different
set of artifacts:

* **part 1** — 2026-07-27, brief `m3-26`, against the m3-05 build;
* **part 2** — 2026-07-28, the owner session, brief `m3-33`, against the
  rebuilt program of §B2.9. Part 2 does not re-run, re-measure, restate or
  correct a single figure of part 1. Where the two disagree in *character* it is
  because the build changed, and part 2 says which build each of its own figures
  was taken against.

**Section C** is a short WSL run added by m3-13.

Each section — and each part of Section B — stays qualified by the environment
and the program build that produced it, and none is re-run or edited by a later
one (LESSONS 2026-07-27).

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

# Section B, part 1 — PLCSIM Advanced, live run with the program in RUN

**Performed 2026-07-27, 23:10–23:37 local (UTC+02:00), under brief `m3-26`,
against the owner's running PLCSIM Advanced instance** with the S7-1500
standard program of `plc/demo-cell/SPEC.md` (m3-05) in RUN, at the owner's
explicit request. The bridge was pointed at it by **configuration only** —
one line, `opcua.endpoint` — with no code change and no change to the security
fields, exactly as §B.0.3 item 1 predicted.

> **Two gate items are NOT claimed here.** Exit items **(a)** and **(b)** of
> `plc/demo-cell/SPEC.md` §11 are defined against the **TIA watch table** of
> that document's §9, which is a GUI artifact this run could not produce. What
> §B.2–§B.5 give instead is the **OPC UA-side equivalent**: the same tags read
> from the server by a second, read-only client. That is a strictly weaker
> instrument — it sees what the server published, not what the program held,
> and it cannot see any §9 Group 4 internal (`SeqStep`, `SpeedRequest`, the
> latches, `ResetDeviceFault`, timer `ET`s). **It is not the watch table and
> does not close (a) or (b).** Both remain owner-outstanding (§B.12).

> **This run also found two defects in the PLC program**, both recorded in
> §B.13 rather than worked around: the **presence verdict never asserted**, so
> no transport cycle ever reached its dwell; and **signal-loss case D was not
> detected** for 26 s. Nothing was adjusted to make anything pass.

## B.0 Commissioned target environment — commissioning phase 0, owner-verified in tool 2026-07-27

This subsection is an **environment record, not a measurement**. It states the
stack that phase 0 of commissioning brought up, and that the m3-26 run of
§B.1 onwards was then executed against. It answers **item 1** for the stack *as
commissioned*; the two elements phase 0 did not fix are picked up later — the
network path with the Tailscale confirmation is **measured in §B.9**, and the
CPU's configured scan cycle remains **owner-outstanding** (§B.12).

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
| Session timeout | requested **3 600 000 ms**, granted **30 000 ms** — the server **revises** the request; a revision downwards in this instance, and the grant for the bridge's own request may land either side of it (§B.0.3) |

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

### B.0.3 Consequences for the run, as facts

1. **The security fields stay as configured.** The server is `None` + anonymous,
   so `security_policy: "none"` with `certificate_path`, `private_key_path` and
   `username` null is the correct setting for this endpoint — invariant 13 is
   untouched because there is no secret to place.
2. **The requested session timeout is a request, and what the CPU grants for it
   was unknown.** The config asks for 10 000 ms
   (`requested_session_timeout_ms`). Phase 0 saw this server grant 30 000 ms
   for a 3 600 000 ms request, so the grant for a 10 000 ms request could land
   either side of it. **Measured in the m3-26 run (§B.2): granted 10 000 ms —
   the request as made, not revised at all**, giving a derived keep-alive of
   **3.333 s**, not the 10.000 s that a 30 000 ms grant would have produced.
   The two observations are consistent: 30 000 ms is this CPU's **cap**, and a
   request below the cap is honoured unchanged. The **granted** value is the
   only one any behaviour uses (`bridge-design.md` §3.2), and this run confirms
   the bridge derives from it rather than from the request.
3. **The browse root is not the same as the test double's, and this is not an
   endpoint-only change.** On this server `DemoCell` is nested one level deeper,
   under `ServerInterfaces`, and `ServerInterfaces` belongs to the **Siemens**
   namespace, not to `http://DemoCell` — so a single-namespace path from
   `Objects`, which is what `bridge/config/bridge.yaml` resolved before m3-21,
   cannot address it (`opcua-nodes.md` §2.1: two indices are resolved by URI at
   connect, neither is hardcoded, and the parent folder never shares the
   interface's namespace). **Closed by m3-21**: the config now carries both URIs
   and an `interface_path` whose elements each name their own namespace, and the
   client resolves both indices at every session establishment. The recorded
   test-double run is `EVIDENCE_CONNECT.md`; the sentence above about
   `opcua.endpoint` and the security fields therefore holds again for this run,
   and Section B is no longer blocked on a client change.

Sections A and C are unaffected: each remains qualified by the environment that
produced it, and neither is re-run or edited here.

## B.1 What was run, and how it was instrumented

Four bridge sessions across two Gazebo sessions, all against the one live
endpoint. The panel was driven only by `tools/cell_stimulus.py` on a fixed
timeline; no input node was ever forced or written by hand.

| Session | Evidence CSV (gzipped) | Span | Ended by | Purpose |
|---|---|---|---|---|
| bridge #1 | `evidence/latency-2026-07-27-plcsim-main.csv.gz` | 225.1 s | **SIGKILL** (case A) | T1, T2, the L7 demand, T4.9 |
| bridge #2 | `evidence/latency-2026-07-27-plcsim-caseA2.csv.gz` | 68.1 s | **SIGTERM** (case B) | T4.2, T4.3 |
| bridge #3 | `evidence/latency-2026-07-27-plcsim-caseD.csv.gz` | 64.2 s | SIGTERM | T4.6, T4.7 |
| bridge #4 | `evidence/latency-2026-07-27-plcsim-l7.csv.gz` | 144.9 s | `--duration` | supplementary L7 samples |

Because the watch table was unavailable, the PLC side was observed instead by
**`tools/observe_plc.py`** (added by this brief), a **read-only** second OPC UA
client sampling all 15 `DemoCell` nodes plus the standard
`Server/ServerDiagnosticsSummary/CurrentSessionCount` at **10 Hz**:

* `evidence/plc-observe-2026-07-27-plcsim-main.csv.gz` — 3 907 rows, 394 s
* `evidence/plc-observe-2026-07-27-plcsim-l7.csv.gz` — the supplementary run

Every timing in §B.8 is quantised by that 0.1 s period and is an observation of
**what the server published**, never of the OB call in which the program acted.
`CurrentSessionCount` read **1** before the bridge connected, confirming that no
other client (and in particular **no test double**, `bridge-design.md` §10) was
on this endpoint at any point.

## B.2 Connect lines, as logged (item 9)

Identical on all four sessions, re-emitted at every session establishment:

```
session timeout: requested 10000 ms, granted 10000 ms - granted as requested;
                 the granted value is the only one in force (§3.2 S2)
secure channel lifetime: requested 3600000 ms, granted 3600000 ms
keep-alive interval 3.333 s = granted 10000 ms / 3 (§3.2 S3)
namespace http://www.siemens.com/simatic-s7-opcua (server_interfaces) -> index 3
namespace http://DemoCell (interface)                                 -> index 4
browse path: Objects/3:ServerInterfaces/4:DemoCell
all node DataTypes match opcua-nodes.md §9
session established, 15 nodes resolved
```

Four things this settles, none of which Section A could:

1. **Both namespaces resolve by URI on the real CPU**, to **3** and **4** —
   different from the double's 5 and 6, which is exactly why no index is
   hardcoded (§3.1 N4). ADR 0006's derived URI `http://DemoCell` is present on
   the server as specified.
2. **15 nodes**, matching `opcua-nodes.md` §9 and §B.0.1, with every DataType
   verified against the document.
3. **The granted session timeout is 10 000 ms, not 30 000 ms** — see §B.0.3
   item 2. The derived keep-alive is therefore **3.333 s**. The brief's
   expectation of a 10.000 s keep-alive against a 30 000 ms grant did **not**
   hold, and the measured value is reported instead.
4. **`reconnects = 0` in every session.** No session was lost in 502 s of
   connected time other than by the deliberate kills.

## B.3 Cycle rate and overruns (item 2)

| Session | cycles | achieved rate | period min / med / p95 / max (ms) | `cycle_overruns` |
|---|---|---|---|---|
| #1 main | 4 503 | **20.00 Hz** | 42.236 / 50.015 / 51.439 / 57.162 | **0** |
| #2 caseA2 | 1 362 | 20.01 Hz | 45.344 / 50.007 / 51.403 / 55.117 | **0** |
| #3 caseD | 1 284 | 20.02 Hz | 45.784 / 49.996 / 51.305 / 54.516 | **0** |
| #4 l7 | 2 899 | 20.01 Hz | 48.177 / 49.987 / 50.931 / 51.671 | **0** |

The 20 Hz expectation of `opcua-nodes.md` §9.2 is met against the real CPU.
`cycle_overruns` is the bridge's own definition — the cycle's *work* overran the
50 ms deadline — so an R1 above 50 ms is scheduling jitter and is not counted as
one; there were 0 of the former and a long tail of the latter, and the bridge
never compensates for either.

Session #1 was SIGKILLed, so `main.py`'s `finally` block never ran and its CSV
carries **no** `run`/`counter`/`R3` tail. That is case A behaving correctly, not
a lost measurement: the rate above is derived from the `R1` rows that are
present, and the counters below are quoted from the sessions that ended
cleanly. Session #1's file also carries **no `session,disconnect` row**, where
#2, #3 and #4 all carry `clean shutdown` — the sharpest artefact of A versus B
anywhere in this evidence.

Counters, session #4 (145.0 s, clean exit):

| counter | value |  | counter | value |
|---|---|---|---|---|
| cycles | 2 900 | | write_errors | **0** |
| cycle_overruns | **0** | | read_errors | **0** |
| publishes | 2 900 | | reconnects | **0** |
| heartbeat_writes | 2 892 | | nonfinite_range_samples | 0 |
| heartbeat_suppressed_cycles | 8 | | missing_joint_name / empty_scan | 0 / 0 |

## B.4 Statistics — count, min, median, p95, max (item 2)

Milliseconds, `CLOCK_MONOTONIC`, produced by `tools/summarize_latency.py`.
**All seven inputs appear**, which Section A could not do (it predates
`PanelResetPressed`). Session #1, the main run:

| ID | signal | count | min | median | p95 | max |
|---|---|---|---|---|---|---|
| L1 | `ConveyorBeltPosition` | 4504 | 0.374 | 1.252 | 5.919 | 11.334 |
| L1 | `ConveyorBeltSpeed` | 4504 | 0.246 | 0.829 | 5.389 | 10.461 |
| L1 | `ProductSensorRange` | 4504 | 0.330 | 19.022 | 37.608 | 50.126 |
| L1 | `PanelStartPressed` | 19 | 4.905 | 27.110 | 50.389 | 50.389 |
| L1 | `PanelResetPressed` | 15 | 5.353 | 17.796 | 45.895 | 45.895 |
| L1 | `PanelStopCircuitClosed` | 5 | 11.427 | 19.355 | 23.834 | 23.834 |
| L1 | `PanelProcessStopCircuitClosed` | 9 | 4.937 | 31.232 | 49.246 | 49.246 |
| L2 | `ConveyorBeltPosition` | 4504 | 0.520 | 1.307 | 3.044 | 8.135 |
| L2 | `ConveyorBeltSpeed` | 4504 | 0.441 | 1.128 | 2.937 | 7.601 |
| L2 | `ProductSensorRange` | 4504 | 0.424 | 1.069 | 2.758 | 37.524 |
| L2 | `PanelStartPressed` | 19 | 0.469 | 0.931 | 2.653 | 2.653 |
| L2 | `PanelResetPressed` | 15 | 0.579 | 1.165 | 2.615 | 2.615 |
| L2 | `PanelStopCircuitClosed` | 5 | 0.595 | 1.170 | 1.710 | 1.710 |
| L2 | `PanelProcessStopCircuitClosed` | 9 | 0.493 | 1.092 | 1.942 | 1.942 |
| L2 | `BridgeHeartbeat` | 4500 | 0.406 | 1.039 | 2.751 | 7.963 |
| L3 | `ConveyorBeltPosition` | 4504 | 0.970 | 2.760 | 7.788 | 13.035 |
| L3 | `ConveyorBeltSpeed` | 4504 | 0.755 | 2.316 | 7.097 | 11.527 |
| L3 | `ProductSensorRange` | 4504 | 0.848 | 20.368 | 38.906 | 64.703 |
| L3 | `PanelStartPressed` | 19 | 5.791 | 27.826 | 51.209 | 51.209 |
| L3 | `PanelResetPressed` | 15 | 7.969 | 18.963 | 47.631 | 47.631 |
| L3 | `PanelStopCircuitClosed` | 5 | 12.369 | 19.952 | 25.006 | 25.006 |
| L3 | `PanelProcessStopCircuitClosed` | 9 | 5.798 | 33.178 | 50.280 | 50.280 |
| L5 | `cmd_speed` | 4504 | 0.053 | 0.120 | 0.261 | 1.862 |
| L6 | `cmd_speed → belt_velocity ≥ 50 %` (**sim**) | 5 | 2.000 | 4.000 | 4.000 | 4.000 |
| R1 | cycle period | 4503 | 42.236 | 50.015 | 51.439 | 57.162 |
| — | OPC UA read round trip (`ConveyorSpeedCommand`) | 4504 | 0.605 | 1.723 | 3.830 | 9.483 |

Reading them against Section A, which is the point of having both:

* **L2 is the number Section A could not honestly produce**, because a Python
  server over loopback is not an S7-1500 over a virtual adapter. The real CPU's
  write handling costs a median of **1.07–1.31 ms** and a p95 of **2.8–3.0 ms**
  — the same order as the double's 0.9–1.0 ms, so the double was not
  flattering. §A.7's "every number here is a lower bound" is confirmed, and the
  margin is small.
* **L1 is unchanged in character**: decimation age, not cost. The photo-eye's
  median 19.0 ms is still roughly half its 33 ms source period.
* **The panel-contact counts are small on purpose.** Contacts are written on
  change (§5), so 19 / 15 / 5 / 9 writes in 225 s is one per commanded
  transition plus the connect refresh, and the 1 Hz republished identical levels
  produce nothing. The decimation ratios (session #4) run from 8.4 : 1 for
  `PanelStartPressed` to 47.7 : 1 for `PanelStopCircuitClosed`, and 25.01 : 1
  for the belt encoder — 72 326 samples received, 2 892 written, the other
  69 434 overwritten in a depth-1 slot and contributing to nothing.
* **L3's `ProductSensorRange` maximum of 64.7 ms** is the one figure materially
  worse than Section A's, and it is an L1 tail (a late scan sample), not an
  L2 tail.

## B.5 L7 — the closed loop, now that a real program answers (item 4)

This is the number Section A could not produce at all (§A.6): it requires a
program that *reacts*, not a server that echoes. **The bridge does not emit an
L7 row**; the value below is derived after the run from rows the bridge already
recorded, all on one clock:

> **start** = `t_end_ns` of the `L2` row for the nominated input write — the
> instant the **server acknowledged** it.
> **end** = `t_end_ns` of the first `read_rt` row for `ConveyorSpeedCommand`
> whose value differs from the one in force before.

The nominated input is the one `plc/demo-cell/SPEC.md` §11 T3 names: a stop
circuit **opening while the belt runs**, whose answer is
`ConveyorSpeedCommand → 0.0` — a real program reaction, not an echo.

| # | nominated input | cmd before | cmd after | L7 (ms) | session |
|---|---|---|---|---|---|
| 1 | `PanelProcessStopCircuitClosed` | −0.150 | 0.000 | **36.4** | #1 main |
| 2 | `PanelProcessStopCircuitClosed` | +0.150 | 0.000 | **46.6** | #4 l7 |
| 3 | `PanelProcessStopCircuitClosed` | +0.150 | 0.000 | **47.4** | #4 l7 |
| 4 | `PanelStopCircuitClosed` | +0.150 | 0.000 | **46.9** | #4 l7 |
| 5 | `PanelProcessStopCircuitClosed` | +0.150 | 0.000 | **47.7** | #4 l7 |
| 6 | `PanelProcessStopCircuitClosed` | +0.150 | 0.000 | **46.4** | #4 l7 |

**count 6, min 36.4, median 46.8, p95 47.7, max 47.7 ms.**

What that interval does and does not contain, stated so the number is not
over-read:

* it **contains** the server's transfer of the written value into the process
  image, **at least one OB30 scan**, the server's sampling of the program's
  output, and **the bridge's own poll phase of 0–50 ms**, because the output is
  read once per 50 ms cycle;
* it is therefore **quantised by the 50 ms poll** and is an **upper bound** on
  the PLC's reaction, never a measurement of it. The clustering at 46–48 ms
  with a single 36.4 ms outlier is the poll phase showing through, not the
  program varying;
* **L4 cannot be separated out from the client side** (§A.6), so it is not.

Only session #1's single event fell inside the main run: the timeline's later
interlock drops all landed while the command was already `0.0`, for the reason
in §B.13 F1, so they produced no observable reaction and are correctly absent
from the table. Session #4 was run afterwards for the sole purpose of
collecting the remaining five, with the same code and the same config.

## B.6 Startup rule against the real DB start values (item 5)

Now with **seven** inputs, not the six of Section A. From the bridge log, at
every one of the four connects:

```
heartbeat withheld: no real sample yet for ConveyorBeltPosition,
  ConveyorBeltSpeed, ProductSensorRange, PanelStartPressed, PanelResetPressed,
  PanelStopCircuitClosed, PanelProcessStopCircuitClosed (startup rule R3)
...
startup rule satisfied: all 7 DemoCell/Input nodes carry a real cell sample;
  heartbeat begins advancing at 1
```

`heartbeat_suppressed_cycles` = 8 (#4), 11 (#2), 17 (#3) — i.e. the heartbeat
was withheld for 0.4–0.85 s while the seven inputs filled, and `BridgeLinkOk`
went `True` **0.8 s** after process start in the main run. Before that the
observer read the program's own start values through the server, and
`BridgeLinkOk` was `False`, exactly as `SPEC.md` §3.1/§6.1 require.

**A cold start of the CPU was not part of this run** and could not be — it means
stopping the owner's CPU. T4.8 and T4.9b stay owner-outstanding (§B.12).

One observation that bears on the cold start anyway. Before any bridge had ever
connected, the owner read `CellProcessStopActive` **True** and
`CellResetRequired` **True**, and the independent probe at the start of this
brief read the same. `CellResetRequired` is explained by `LinkLostLatch`.
`CellProcessStopActive` requires `ProcessStopLatch`, which §7 part 4 gates on
`linkOk` — and `linkOk` **is** `True` for the first ~25 OB calls, because
`HeartbeatStaleTimer.Q` is still `False` in the scan the timer starts. During
that 500 ms window the stop circuits still read their non-permissive start value
`FALSE`, so the latch sets. **This is an inference from the specification, not
an observation of the cold start** — the CPU was already running when this brief
began — but it is consistent with everything measured and needs no defect to
explain it.

## B.7 Signal-loss cases against PLCSIM (item 6)

Repeating `EVIDENCE_SIGNAL_LOSS.md`'s four cases against a CPU that is actually
running a program. Timings from the 10 Hz observer, so ±0.1 s.

| Case | How it was produced | What the program did | Verdict |
|---|---|---|---|
| **A** — bridge SIGKILL | `kill -9` bridge #1 at t=227.6 s | heartbeat froze at **4537**; `BridgeLinkOk → False` **0.50 s** later; `CellResetRequired → True` in the same sample; command already `0.0` | **as specified** |
| **B** — bridge SIGTERM | `kill -15` bridge #2 at t=311.4 s | heartbeat froze at **1352**; `BridgeLinkOk → False` **0.51 s** later; `CellResetRequired → True` | **identical to A at the program**, as §8 requires |
| **C** — link loss / CPU stop | **not performed** | — | **owner-outstanding**: it requires stopping the CPU or its adapter, which this brief is forbidden to do |
| **D** — simulation killed, bridge alive | `kill -9` the gz server at t≈363 s | heartbeat **kept advancing** (**750** at the freeze to **1268** at the drop, §B.13 F2), `BridgeLinkOk` stayed **True**, input image froze bit-identically — and **`ConveyorDriveFault` never latched** for 26 s | **FAILED — see §B.13 F2** |

The 0.50 / 0.51 s figures are `HEARTBEAT_STALE_TIME` = 500 ms measured three
times independently (a third instance at t=389.2 gave 0.50 s), so that constant
needs no revision: `SPEC.md` open item 1 closes at **500 ms**, and the worst
cycle period seen here was 57.2 ms, about 9 missed beats of margin.

**No auto-resume, three times.** After each link restoration the cycle stayed
down until a *separate* start press: +36.0 s, +39.0 s and +8.9 s, each after a
reset. A returning heartbeat restarted nothing, and the first command delivered
after every reconnect was `0.0`.

**T4.9, the stuck reset — passes exactly.** With `reset` published `true` and
**left published**, a process stop was latched at t=194.8 (`CellProcessStopActive`
and `CellResetRequired → True`) and stayed latched for the whole 18 s the button
was held. Releasing at t=212.7 changed nothing; the *new* rising edge at t=214.8
cleared both in the same 0.1 s sample. There is no edge to act on while the
contact is held, and no elapsed time makes one appear.

**T4.7 could not be executed**: it presupposes a latched `ConveyorDriveFault`,
which §B.13 F2 explains never occurred. The reset and start pressed at t=372.8
and t=376.8 therefore acted on a cell with no latch pending and a cycle already
running, and changed nothing. m3-29 has since **inverted** the step — its pass
is now that the reset is *refused* while the frozen image still claims motion —
so what is recorded here is the non-execution of the old step, and the inverted
one is outstanding (§B.12 item 12).

### T4 as-run accounting — seven of the twelve steps ran

> **Forward pointer, added by m3-33 (no figure below is changed).** This
> accounting is part 1's, against the **m3-05** build, and it stays as recorded.
> The 2026-07-28 owner session re-ran most of T4 against a rebuilt program; its
> roster, with a verdict per step, is **§B2.7**, and the disposition of the
> thirteen outstanding rows of §B.12 is **§B2.12**. Where a step appears in both,
> part 2's result is the later one and part 1's is not amended to match.

`SPEC.md` §11 T4 lists **twelve** steps. The table below is derived from what
this run executed, not from the scenario table as it stands today, so that any
count taken from this evidence has a denominator that matches the record.

| Step | As run | Recorded in |
|---|---|---|
| 4.1 **(A)** | ran, as specified | §B.7 case A |
| 4.2 | ran, as specified | §B.7, "No auto-resume, three times" |
| 4.3 | ran, as specified | §B.7, same paragraph |
| 4.4 **(B)** | ran, identical to A at the program | §B.7 case B |
| 4.5 **(C)** | **not run** | §B.7 case C; §B.12 item 5 |
| 4.6 **(D)** | ran — **failed**; the step as written then is **superseded** by m3-29's mid-motion T4.6 (§B.12 item 10) | §B.7 case D; §B.13 F2 |
| 4.7 | attempted, **not executable** — no latch to re-latch; the step as written then is **superseded** by m3-29's inverted T4.7 (§B.12 item 12) | §B.7, above |
| 4.8 | **not run** — cold start of the CPU | §B.12 item 6 |
| 4.9 | ran, passes exactly | §B.7, above |
| 4.9b | **not run** — cold start of the CPU | §B.12 item 6 |
| 4.10 | ran, measured | §B.8 |
| 4.11 | **not run — it postdates this run** | §B.12 item 9 |

**T4.11 did not exist when this run was executed.** It was added to `SPEC.md`
§11 by m3-27, after the fact, and running it needs both a narrowed-constant
recompile in TIA and a program built to the m3-27 specification — where the
build in RUN here was the m3-05 one this section's header names. It is
owner-outstanding (§B.12 item 9).

**T4.6b did not exist either, and T4.6 and T4.7 no longer mean what this run
tested.** m3-29 re-specified case-D detection after this run: T4.6 became the
**mid-motion** test, with the freeze-to-latch elapsed time recorded as a number
against a ≤ 3.2 s bound; T4.6b was **added** for the at-rest D1 path; and T4.7
was **inverted** — the monitored reset is now *refused* while the frozen image
still claims motion, where the step this run attempted promised a re-latch
within 1 s. All three postdate the recorded run, and all three need a program
rebuilt to the m3-29 `SPEC.md` §6.6/§7 form. They are owner-outstanding
(§B.12 items 10–12).

**The rows above are therefore annotated, not renumbered, and no as-run figure
is restated.** What ran, ran, against the m3-05 build. The twelve rows are the
§11 T4 list as it stood when this accounting was written; the list now has
**thirteen** steps, and the revised or added ones appear as outstanding rows
rather than as a larger denominator (LESSONS 2026-07-28).

**No pass claim over all twelve T4 steps is therefore supported by this
evidence**: seven steps ran, one of those failed, one was attempted and found
not executable, and four did not run. The accounting this section asked of
`plc/` is now in place: `SPEC.md` §11 T4 reads *"Pass: all thirteen"* and states
in the same place that thirteen is the specified list and not a claim about a
run, and that a step added after a run gains an outstanding row rather than a
larger denominator.

## B.8 Session behaviour on a real server (item 7)

The one in-container result known not to transfer (`EVIDENCE_SIGNAL_LOSS.md`
§A.4), now measured on the CPU via `CurrentSessionCount`:

| Event | Session dropped after | Against a granted timeout of |
|---|---|---|
| bridge **SIGKILL** (case A) | **11.79 s** | 10 000 ms |
| bridge **SIGTERM** (case B) | **0.0 s** — closed in the same sample | 10 000 ms |

The killed client's session outlives it by roughly the granted timeout plus the
server's reaping granularity, which is the expected shape (§3.2 S5). **This is
the only measurable difference between A and B**, it lives at the session layer,
and the standard program neither sees it nor should: §8 requires A and B to be
indistinguishable to the program, and §B.7 confirms they were.

## B.9 Environment and the network path (item 1)

| Item | Value |
|---|---|
| Engineering tool / simulator | TIA Portal V21 / S7-PLCSIM Advanced V7.0 (§B.0) |
| CPU | CPU 1513-1 PN, firmware V3.1, **simulated, not hardware** |
| Endpoint / security | `opc.tcp://192.168.53.1:4840`, policy **None**, anonymous |
| Bridge host | WSL2 Ubuntu 24.04, kernel 5.15.167.4-microsoft-standard-WSL2, headless GUI via WSLg (llvmpipe), repo on `/mnt/c` |
| Runtime | ROS 2 Jazzy, Gazebo Sim 8.11.0, Python 3.12, `asyncua` 2.0.1 in `/home/ozkan/amr-bridge-venv` |
| Isolation | `ROS_DOMAIN_ID=93`, `GZ_PARTITION=m326live` |

**The network path, measured rather than asserted (invariant 8).** The bridge
runs in WSL2 and the PLCSIM adapter is Windows-side, so whether WSL2's NAT
reaches it was the first thing tested, before anything else:

```
WSL:  ping 192.168.53.1        -> 3/3, rtt 0.510/0.650/0.835 ms, ttl 254
WSL:  TCP connect to :4840     -> open
WSL:  asyncua connect + read   -> 15 nodes, ns 3 and 4 resolved
WSL:  ip route                 -> default via 172.19.176.1 dev eth0 (172.19.180.72/20)
Win:  Find-NetRoute 192.168.53.1 -> InterfaceAlias "Ethernet 2", NextHop 0.0.0.0 (on-link)
Win:  Get-NetRoute 192.168.53.0/24 -> "Ethernet 2" only, metric 256
```

So the path is: **WSL2 `eth0` 172.19.180.72 → Hyper-V `vEthernet (WSL)`
172.19.176.1 → host route → `Ethernet 2` (PLCSIM virtual adapter)
192.168.53.241 → instance 192.168.53.1.** One router hop, consistent with
TTL 254. There is **no switch and no VPN in it**.

**Tailscale is not in that path.** Its adapter exists and is `Up`, but
`Get-NetRoute` shows the only route to `192.168.53.0/24` is the on-link route on
`Ethernet 2`; Tailscale carries none. Invariant 8 holds for this measurement,
and the evidence is the routing table rather than a statement of intent. (Its
IPv4 is an APIPA `169.254.83.107`, i.e. no tailnet address was even assigned.)

**The CPU's configured scan cycle is not recorded here** — the OB30 period is a
TIA project setting and the CPU's cycle-time diagnostics are not on the
`DemoCell` interface. It stays owner-outstanding (§B.12).

## B.10 Which server produced each number (item 8)

Every figure in Section B came from `opc.tcp://192.168.53.1:4840`, the PLCSIM
Advanced instance with the program in RUN. **The test double was not running at
any point during this run**, on this endpoint or any other, and
`CurrentSessionCount` = 1 before the bridge connected corroborates it. The
connect-conformance harness was likewise kept off this endpoint
(`bridge-design.md` §10); `EVIDENCE_CONNECT.md` remains a test-double record.

## B.11 The one configuration change, and nothing else

`bridge/config/bridge.yaml` → `opcua.endpoint` was changed from the test
double's loopback URL to `opc.tcp://192.168.53.1:4840`. **No other file in
`bridge/` was edited to make this run work**, no security field moved (the
server is None + anonymous, so the configured nulls were already correct), no
namespace index was hardcoded, and no code path differs from the one Sections A
and C exercised. `tools/observe_plc.py` was **added** for the observation
described in §B.1; it writes nothing and is not in the transport path.

## B.12 What this run did not establish — owner-outstanding

> **Forward pointer, added by m3-33.** The thirteen rows below are part 1's list
> as it stood on 2026-07-27. Several were addressed by the 2026-07-28 owner
> session and several were not; **§B2.12 dispositions every one of them by number**
> and carries part 2's own outstanding list. No row below is edited or deleted —
> a closed row is recorded as closed in §B2.12, in the run that closed it.

| # | Item | Why it is still open |
|---|---|---|
| 1 | **Gate exit item (a)** — Gazebo sensor state as PLC inputs *in the watch table* | The instrument is the TIA watch table of `SPEC.md` §9. §B.4 and the observer show the same tags over OPC UA, which is a weaker view and **is not the watch table** |
| 2 | **Gate exit item (b)** — PLC output driving the actuator *in the watch table* | Same. The OPC UA-side equivalent is in §B.4/§B.7 and the loop demonstrably ran (§B.5), but (b) as written is not met by it |
| 3 | **The CPU's configured scan cycle** and the CPU's max cycle time | TIA/CPU diagnostics, not on the `DemoCell` interface (§B.9) |
| 4 | **L4 on the PLC side** | Needs the watch table to timestamp the output change inside the CPU; from the client it stays the bound of §A.6 |
| 5 | **Signal-loss case C** | Requires stopping the CPU or its adapter (§B.7) |
| 6 | **T4.8 / T4.9b — cold start of the CPU** | Requires cold-starting the owner's CPU; see the inference in §B.6 |
| 7 | **T4.10 for hardware** | §B.8 measures PLCSIM Advanced; real S7-1500 hardware may reap differently |
| 8 | **T2.2–T2.4, the dwell at the beam** | Not reachable while §B.13 F1 stands |
| 9 | **T4.11 — belt-feedback plausibility by the narrowed-constant method** | It postdates this run: m3-27 added it to `SPEC.md` §11 afterwards. It needs a TIA recompile with a narrowed constant, and a program built to the m3-27 spec at all — the build in RUN here was m3-05 |
| 10 | **T4.6 as re-specified (D ii, mid-motion)** — `ConveyorDriveFault` latching within 3.2 s of the freeze, with the **elapsed time recorded as a number** from the last changing `ConveyorBeltPosition` sample | The step postdates this run: m3-29 rewrote it after the fact, and what this evidence records against the old step is a **failure** on the m3-05 build (§B.13 F2, 26 s undetected). It needs the **m3-29 rebuild** — the re-armed `PositionRef` window and `PositionFrozen` of §6.6/§7 — downloaded to the CPU, plus the §9 Group 4 watch table to read `PositionRef`, `PositionFrozen` and `PositionWindowTimer.ET` |
| 11 | **T4.6b (D i, at rest)** — the D1 path: Gazebo killed during the step-20 dwell, latch within `DRIVE_FAULT_DELAY`, `PositionFrozen` staying `FALSE` | The step did not exist when this run was made; m3-29 added it. Same **m3-29 rebuild** required. It additionally needs the dwell to be reachable at all, which item 8 above (§B.13 F1) still blocks — a cell that never asserts presence never enters step 20 |
| 12 | **T4.7 as inverted** — the monitored reset **refused** while the frozen image still claims motion, then honoured once the simulation is restarted | m3-29 inverted the pass condition after this run; the old step was attempted here and found not executable at all, because no latch was ever raised (§B.7). It needs the **m3-29 rebuild** and can only follow a T4.6 that actually latches |
| 13 | **Rebuild baseline for the next run** — which `SPEC.md` revision the downloaded program was built to, captured **with** the evidence | Every figure in Section B was taken against the **m3-05** build, named in this section's header. The m3-29 download changes that baseline, and items 9–12 are all defined against it, so the program version at the next download (SPEC revision and TIA compile) is recorded at the time of the run rather than inferred afterwards; without it no later figure can be attributed to a specification |

## B.13 Findings that belong to the PLC program

Both were found by running the specification, are recorded exactly as observed,
and **nothing was changed to work around either**. Neither is a bridge defect:
the bridge carried the correct values in both cases, which is how they became
visible.

### F1 — the presence verdict never asserted, so no cycle ever reached its dwell

The photo-eye works and the bridge carries it faithfully. During the first
transport, the PLC's own `ProductSensorRange` node went **1.4401 → 0.5400 m and
held there for 2.11 s** — 21× the `PRESENCE_FILTER` of 100 ms — and `0.540` is
precisely the "product in the beam" value `SPEC.md` §9 predicts.
`RANGE_MIN`/`RANGE_MAX` are 0.05/3.00, so `RangeValid` was true throughout.

**`ProductPresentAtSensor` stayed `False` for the entire 394 s run** — it never
once changed state. Consequently `SeqStep` never advanced 10 → 20, there was no
dwell, no reversal at the beam, and the transport step instead ran on to the
soft limit: at **t=54.7600, position 2.4123 m ≥ `SOFT_LIMIT` 2.40**, the step
aborted, `SequenceFaultLatch` set, `CellCycleRunning → False`,
`ConveyorSpeedCommand → 0.0` and `CellResetRequired → True`. The same thing
happened on every subsequent transport.

**Provenance of the two timings above.** Both come from
`evidence/plc-observe-2026-07-27-plcsim-main.csv.gz`, on that file's own
`t_mono_s` clock — the observer's relative clock, quantised to its 0.1 s
sampling period, and *not* the bridge sessions' clock. Taking "blocked" as a
sample of `Input/ProductSensorRange` below 1.0 m, the first block runs from
**t=47.0044** to a last blocked sample at **t=49.1175**, with the first clear
sample at **t=49.2179**: 22 consecutive rows at `0.5400331616401672`, i.e.
**2.11 s** first-to-last blocked and 2.21 s to the first clear reading. The
soft-limit abort is the single row **t=54.7600**, in which
`Input/ConveyorBeltPosition` reads `2.4123001098632812` — the run's maximum —
and `Status/CellCycleRunning` goes True→False, `Status/CellResetRequired`
False→True and `Output/ConveyorSpeedCommand` +0.15→0.0 together.

The readings this finding carried when it was first written — *47.10 → 48.92,
1.8 s* for the block and *t=54.96* for the abort — **reproduce from no
committed file**, on either clock; they were run observations, not figures
taken from the record. Both were conservative: the block was longer than
stated, so the gap between "beam blocked" and "verdict never asserted" is
wider, and nothing downstream of either number changes.

Two things worth separating:

* **The soft-limit abort of §6.5 works, and is what kept the cell safe** — the
  program stopped the belt 0.09 m before the ±2.50 m mechanical stop, every
  time, and required a monitored reset afterwards.
* **The presence verdict of §6.2 did not run.** The evidence cannot say which
  half is at fault (the filter timers, the hysteresis, or the verdict never
  being written), because none of §9 Group 4 is on the server. **The watch table
  is the instrument that would distinguish them**, and this is the strongest
  reason to run T1/T2 with it open.

The re-home branch of §6.3 was exercised **six times** and worked correctly on
every one: with the belt off home, start selected `SeqStep` 30 at −0.15 m/s and
completed at `ABS(pos) ≤ HOME_WINDOW`. Every instance began from the **positive**
side of home; the branch's behaviour from the negative side was not exercised.

### F2 — signal-loss case D was not detected for 26 s

The gz server was killed at t≈363 s with the belt transporting. The case D
signature appeared exactly as §8 predicts: heartbeat **kept advancing** (**750**
at the freeze to **1268** at the drop), `BridgeLinkOk` stayed **True**, and the
input image froze bit-identically at `position = 0.9273`, `speed = 0.1500`. From
the PLC's side the link looked perfect.

`ConveyorDriveFault` **stayed `False`**. For **26 s** the program commanded
`+0.15 m/s` into a cell that no longer existed. The cycle was finally dropped
only at t=389.7, by `LinkLostLatch`, when bridge #3 was stopped — i.e. by the
heartbeat mechanism, not by the drive-fault mechanism that §8 nominates for
this case.

The reason is visible in the specification itself:

* **D1 cannot fire.** It needs `ABS(ConveyorBeltSpeed) ≤ SPEED_TOLERANCE`, but
  the frozen read-back is **0.1500**, not zero. The in-container case D froze at
  `3.2e-28` because the belt was nearly stopped then; freeze the image *while
  the belt is moving* and D1 is blind by construction. `SPEC.md` §8 already
  anticipates this — it is why D2 exists.
* **D2 cannot fire either, and this is the defect.** In §7 part 3,
  `PosWindowArmed` latches `TRUE` on the first scan of motion and is cleared
  only by `NOT beltMoving`. So `PositionRef` is sampled **once, at the start of
  the motion, and never re-armed while motion continues** — the window never
  slides. The reference D2 arms on is therefore the **motion-start** position,
  which this run puts between **0.0477 m** (the row in which the command
  changes to +0.15) and **0.0618 m** (the first row whose speed read-back
  exceeds `SPEED_TOLERANCE`); the freeze is at **0.9273 m**, so
  `ABS(position − PositionRef)` was ≈ **0.87 m** against a
  `POSITION_FREEZE_BAND` of **0.005 m**, and stayed there. D2's comparison can
  only be satisfied if the freeze happens within roughly the first 33 ms of a
  motion.

**Provenance of the F2 figures.** Same file and clock as F1
(`evidence/plc-observe-2026-07-27-plcsim-main.csv.gz`, `t_mono_s`), corroborated
on the bridge side by `evidence/latency-2026-07-27-plcsim-caseD.csv.gz`. The
command goes to +0.15 at **t=356.8557** (position `0.047700002789497375`); the
first row with `ABS(Input/ConveyorBeltSpeed)` above `SPEED_TOLERANCE` is
**t=356.9566** (position `0.06180000305175781`) — the 0.1 s sampling is why the
armed reference is bracketed rather than exact. The last row in which the image
changes is **t=363.3057**, at `0.9273000359535217` / `0.15000000596046448`; every
later row repeats it bit for bit, and `Status/CellCycleRunning` and
`Link/BridgeLinkOk` drop at **t=389.7431**, 26.4 s after that.
`Status/ConveyorDriveFault` has exactly one distinct value in all 3 907 rows of
the file: `False`. `Link/BridgeHeartbeat` reads **750** in the freezing row and
**1268** in the drop row, 1268 also being bridge #3's `heartbeat_writes` counter,
i.e. its last write.

Two figures this finding carried when it was first written are corrected above
rather than left standing. The heartbeat pair *767 → 1251* quoted two samples
from inside the window instead of its endpoints — and **767 is not a heartbeat
value at all**: it is the index of the freezing `ConveyorBeltPosition` write in
the caseD session file. The travel *from 0.3093* quoted a real value —
`Input/ConveyorBeltPosition` at t=358.7713 — but a mid-motion one, ≈1.9 s after
motion start, not the reference D2 arms on; the ≈0.62 m it produced was the
wrong difference of two right numbers. Both corrections are attribution only:
the delta is two orders of magnitude outside the band either way, and the
finding is unchanged.

**Net effect: a simulation frozen at any non-zero speed after the first fraction
of a second of travel is undetectable by either term.** The honest limit
`SPEC.md` §6.6 already states for the *idle* sub-case turns out to extend to the
moving case as well. Fixing it is a change to `plc/demo-cell/SPEC.md` §6.6/§7 —
a re-arming window, not a bridge change — and belongs to the `plc` agent, not
here.

---

# Section B, part 2 — PLCSIM Advanced, the owner session of 2026-07-28

**Performed 2026-07-28, 15:01–18:01 local (UTC+02:00), by the owner at the
engineering workstation, against the same PLCSIM Advanced instance and the same
endpoint as part 1**, with a **rebuilt** standard program in RUN (§B2.9 lists the
five downloads of the day and names the build behind every figure below). Written
up under brief `m3-33` from the artifacts the session committed. Nothing was
re-run to produce this section, and no figure of part 1 is altered by it.

> **What is new here, in one paragraph.** Part 1 recorded two program defects
> (§B.13): the presence verdict never asserted, and signal-loss case D went 26 s
> undetected. **Both are answered by this run**: the presence verdict asserted
> three times and the dwell was reached (§B2.6a), and case D mid-motion was
> caught in **2.301 s** against a 3.2 s bound (§B2.7a). Two new results are
> failures and are recorded as such: **T4.9b failed** — a reset held from before
> link-up cleared every latch the moment the link came up (§B2.13 F3) — and
> **T4.11's latch step is not testable by the method §11 named for it**
> (§B2.13 F4). One bridge defect was found: after a CPU restart the bridge never
> repaired the reverted input image (§B2.13 F5).

## B2.0 The artifacts, the windows they cover, and three limitations

Every figure in this section is labelled with the artifact it comes from. Where
only the orchestrator's session transcript carries a value, it is marked
**[transcript]** with its wall-clock timestamp and is never presented as a
measurement.

| Artifact (all gzipped, in `evidence/`) | Rate | Window it covers |
|---|---|---|
| `latency-2026-07-28-plcsim-t1t4.csv.gz` | **20 Hz** per-event | **17:49:06 – 18:01:00 only** — one bridge session, 712.255 s, clean shutdown |
| `bridgelog-2026-07-28-sessionA-t4-era.log.gz` | 1 Hz diagnostics | 15:01:10 – 16:57:31, three bridge processes appended into one file |
| `bridgelog-2026-07-28-sessionB-t48.log.gz` | 1 Hz | 17:00:11 – 17:01:06 (T4.8) |
| `bridgelog-2026-07-28-sessionC-t49b.log.gz` | 1 Hz | 17:02:20 – 17:14:07 (T4.9b) |
| `bridgelog-2026-07-28-sessionD-final.log.gz` | 1 Hz | 17:49:06 – 18:01:00, the same session as the 20 Hz CSV |
| `plc-observe-2026-07-28-t4a-caseAB.csv.gz` | **5 Hz** read-only observer, 1 992 rows / 400.0 s | T4.1, T4.2, T4.3, T4.4 and T4.10 |
| `plc-observe-2026-07-28-capstone.csv.gz` | 5 Hz, 891 rows / 178.7 s | the three capstone rounds and the T4.6 re-measure |
| `plc-observe-2026-07-28-final-cycle-press.csv.gz` | 5 Hz, 45 rows | the final cycle's start press |
| `cmdlog-2026-07-28-*.log.gz` | — | **LIMITATION 2**: both contain `data: 0.0` and nothing else. Treated as absent; no figure here rests on them |
| `plc/demo-cell/evidence/watch-table/` | owner captures | 71 files named by timestamp, **24 of them from 2026-07-28** (13:40 – 17:41). Read-only and outside this file's scope to edit. **Six are read and cited by content below** — `171656`, `171712`, `171727`, `173247`, `173615` and `174127`; the rest are referenced by filename only, and a filename timestamp is treated as a *candidate* for an event, never as coverage of it |

**LIMITATION 1 — the 20 Hz record exists for the last twelve minutes only.**
`--evidence-csv` truncates its file at every bridge start, and the day used one
path across every restart, so each restart wiped the earlier 20 Hz rows
(LESSONS 2026-07-28). What survives is the final session. The 1 Hz diagnostics
logs were salvaged beside it and cover most of the rest — but not all of it:
there is **no committed bridge artifact of any kind for 17:14:07 – 17:49:06**,
because the log path in use there was truncated three further times. Two things
fall in that hole, and both are marked [transcript] wherever they appear below:
the **T1.4 re-run** (17:14:37 – 17:15:06) and the whole of **T4.11**.

**LIMITATION 3 — the observer sees the server, not Group 4.** Both instruments
here are OPC UA clients, so `SeqStep`, `SpeedRequest`, `PositionRef`,
`PositionFrozen`, `ResetDeviceFault` and every timer `ET` are invisible to them.
They exist only in the owner's watch-table captures — of which **five cover
2026-07-28 events this section describes** (§B2.7c and §B2.13 F4) and **none
covers the T4.6 re-measure or T4.6b**. Where a `SPEC.md` §11 pass condition names
a Group 4 tag and no capture covers the moment, this section says so and does not
substitute an inference for it.

**A fourth limitation, found while writing and stated because it bounds every
wall-clock figure derived from the CSV.** The CSV is timestamped on
`CLOCK_MONOTONIC`; the logs are timestamped on the wall clock. Over the final
session the wall clock advanced **1.767 s more** than monotonic (log span
17:49:06.101 → 18:01:00.123 = 714.022 s against `run,duration_s` = 712.255 s),
so a wall time obtained by adding a monotonic offset to a single anchor is good
to no better than ±2 s across the session (LESSONS 2026-07-27: verify which clock
the code samples). **Every CSV figure below is therefore quoted on the CSV's own
clock** — seconds relative to the first cycle, whose `t_start_ns` is
`78927973078344` and which the log independently places at 17:49:06.101 — and
wall-clock times are quoted only from the logs or from the transcript.

## B2.1 What was run, and how the two clocks were tied together

Seven bridge processes across the afternoon, all against the one live endpoint,
all driven by `ros2 topic pub` on `/cell/panel/*` and by the committed
`tools/observe_plc.py` as a **read-only** second client at 5 Hz (part 1 used
10 Hz; the period is in the CSVs' own `t_mono_s` column and is 0.2 s here).

Two cross-clock alignments are used, and each is stated with its residual rather
than asserted:

* **`plc-observe-…-t4a-caseAB.csv` ↔ `sessionA` log.** `CurrentSessionCount`
  rises 1 → 2 at observer `t_mono_s` = 118.1373, which is the restarted bridge's
  session; the log times that establishment at 15:14:12.330. That puts observer
  t = 0 at **15:12:14.19**. Cross-check: the observer's heartbeat stops changing
  at t = 110.504, which maps to 15:14:04.69, **0.03 s** from the log's
  `signal 15: stopping` at 15:14:04.723.
* **`plc-observe-…-capstone.csv` ↔ the 20 Hz CSV.** The observer's
  `ConveyorSpeedCommand` 0.15 → 0.0 at t = 98.1821 is the CSV's read at rel
  630.3028; the offset is **532.121 s**, and the capstone's start press
  (observer 4.4193, CSV write 536.5556) reproduces it to **0.016 s**.

## B2.2 Connect lines, as logged (item 9) — **filled**

Identical in all four committed logs and in the CSV's own `session` rows:

```
session timeout: requested 10000 ms, granted 10000 ms - granted as requested
secure channel lifetime: requested 3600000 ms, granted 3600000 ms
keep-alive interval 3.333 s = granted 10000 ms / 3 (§3.2 S3)
namespace http://www.siemens.com/simatic-s7-opcua (server_interfaces) -> index 3
namespace http://DemoCell (interface)                                 -> index 4
browse path: Objects/3:ServerInterfaces/4:DemoCell
all node DataTypes match opcua-nodes.md §9
session established, 15 nodes resolved
```

Seven independent session establishments across two hours reproduce part 1's
result unchanged: both namespaces resolve **by URI** to 3 and 4, the browse path
crosses the Siemens namespace into `http://DemoCell`, 15 nodes resolve with every
DataType checked, and the granted session timeout is **10 000 ms — the request as
made** (so `min(request, cap)` again, not the 30 000 ms cap; LESSONS 2026-07-28).
`reconnects = 0` in the final session, and the `sessionA` log carries **no
`session broken`, no `connect failed` and no reconnect line at all** between
15:14:24 and 16:57:31 — a fact §B2.13 F5 needs.

## B2.3 Cycle rate and overruns (item 2) — **filled**

Final session, 712.255 s, from `tools/summarize_latency.py`:

| cycles | achieved rate | period min / med / p95 / max (ms) | `cycle_overruns` |
|---|---|---|---|
| 14 244 | **20.00 Hz** | 40.095 / 50.003 / 50.978 / 61.394 | **1** |

The single overrun is recorded with its size: the `overrun` row gives
`interval_ns = 3 927 528`, i.e. the cycle's work passed its 50 ms deadline by
**3.93 ms**, once in 14 244 cycles. It is not compensated for, and the next
period is not shortened to catch up. `opcua-nodes.md` §9.2's 20 Hz expectation is
met against the real CPU for the third time (Section A, part 1, part 2).

Counters, whole session:

| counter | value | | counter | value |
|---|---|---|---|---|
| cycles | 14 244 | | write_errors | **0** |
| cycle_overruns | **1** | | read_errors | **0** |
| publishes | 14 244 | | reconnects | **0** |
| heartbeat_writes | 14 012 | | keepalive_probes / failures | 0 / 0 |
| heartbeat_suppressed_cycles | 232 | | nonfinite_range_samples | 0 |
| missing_joint_name / empty_scan | 0 / 0 | | | |

R3 decimation, same session: `ConveyorBeltPosition` and `ConveyorBeltSpeed`
352 380 / 14 243 = **24.74 : 1**, `ProductSensorRange` 21 403 / 14 243 =
**1.50 : 1**, and the four contacts 14/13, 11/11, 2/1, 7/5 — written on change,
so their counts are transitions and not a cadence. The two unwritten contact
samples are **the two lost publishes of §B2.14**, and the R3 ratio is how they
were found.

## B2.4 Statistics — count, min, median, p95, max (item 2) — **filled**

Milliseconds, `CLOCK_MONOTONIC`, `tools/summarize_latency.py`, final session.
All seven inputs appear. `PanelStopCircuitClosed` has a single write for the
whole session because the contact was closed once at startup and never opened
again — its row is a count of 1 and is shown as such rather than omitted.

| ID | signal | count | min | median | p95 | max |
|---|---|---|---|---|---|---|
| L1 | `ConveyorBeltPosition` | 14243 | 0.367 | 1.259 | 2.255 | **4998.110** |
| L1 | `ConveyorBeltSpeed` | 14243 | 0.251 | 0.537 | 2.368 | **4999.814** |
| L1 | `ProductSensorRange` | 14243 | 0.282 | 16.569 | 32.090 | **5401.180** |
| L1 | `PanelStartPressed` | 13 | 6.670 | 27.837 | 43.230 | 43.230 |
| L1 | `PanelResetPressed` | 11 | 3.488 | 25.518 | 38.381 | 38.381 |
| L1 | `PanelStopCircuitClosed` | 1 | 39.724 | 39.724 | 39.724 | 39.724 |
| L1 | `PanelProcessStopCircuitClosed` | 5 | 0.913 | 12.625 | 37.883 | 37.883 |
| L2 | `ConveyorBeltPosition` | 14243 | 0.470 | 1.028 | 1.804 | 7.043 |
| L2 | `ConveyorBeltSpeed` | 14243 | 0.353 | 0.834 | 1.695 | 27.469 |
| L2 | `ProductSensorRange` | 14243 | 0.310 | 0.860 | 1.689 | 8.775 |
| L2 | `PanelStartPressed` | 13 | 0.531 | 0.885 | 1.490 | 1.490 |
| L2 | `PanelResetPressed` | 11 | 0.572 | 1.048 | 1.764 | 1.764 |
| L2 | `PanelStopCircuitClosed` | 1 | 0.886 | 0.886 | 0.886 | 0.886 |
| L2 | `PanelProcessStopCircuitClosed` | 5 | 0.469 | 0.521 | 1.718 | 1.718 |
| L2 | `BridgeHeartbeat` | 14012 | 0.297 | 0.820 | 1.689 | 6.781 |
| L3 | `ConveyorBeltPosition` | 14243 | 0.927 | 2.350 | 3.674 | 4999.802 |
| L3 | `ConveyorBeltSpeed` | 14243 | 0.765 | 1.627 | 3.478 | 5000.617 |
| L3 | `ProductSensorRange` | 14243 | 0.819 | 17.485 | 33.101 | 5402.518 |
| L3 | `PanelStartPressed` | 13 | 7.559 | 28.477 | 43.781 | 43.781 |
| L3 | `PanelResetPressed` | 11 | 4.143 | 27.189 | 39.670 | 39.670 |
| L3 | `PanelStopCircuitClosed` | 1 | 40.614 | 40.614 | 40.614 | 40.614 |
| L3 | `PanelProcessStopCircuitClosed` | 5 | 1.781 | 13.149 | 38.393 | 38.393 |
| L5 | `cmd_speed` | 14244 | 0.055 | 0.101 | 0.184 | 1.640 |
| L6 | `cmd_speed → belt_velocity ≥ 50 %` (**sim**) | 7 | 2.000 | 4.000 | 4.000 | 4.000 |
| R1 | cycle period | 14243 | 40.095 | 50.003 | 50.978 | 61.394 |
| R2 | `ConveyorBeltPosition` | 14242 | 38.304 | 49.994 | 51.487 | 63.489 |
| R2 | `ConveyorBeltSpeed` | 14242 | 32.714 | 50.004 | 51.799 | 69.478 |
| R2 | `ProductSensorRange` | 14242 | 24.762 | 50.004 | 52.058 | 76.685 |
| — | OPC UA read round trip (`ConveyorSpeedCommand`) | 14244 | 0.532 | 1.149 | 2.169 | 9.093 |

Reading them against part 1, which is the point of having both:

* **L2 — the bridge's own cost against the real CPU — is unchanged in character
  and slightly better**: median 0.83–1.03 ms against part 1's 1.07–1.31 ms, p95
  1.69–1.80 ms against 2.76–3.04 ms, over 3.2× as many samples. Nothing in the
  bridge changed between the two runs, so this is the CPU and the host on a
  different afternoon, not an improvement.
* **The three L1 maxima of ~5.0 s are not outliers or jitter — they are
  signal-loss case D, measured by accident.** L1 is the age of the sample in its
  slot when the cycle takes it, so when Gazebo dies the same sample is re-taken
  every 50 ms and its age grows without bound. The freeze of §B2.7a lasted from
  rel 628.0015 to rel 632.9823, **4.981 s**, and `ConveyorBeltPosition`'s L1
  maximum is 4 998.110 ms. This is worth stating plainly for what it is *not*: the
  bridge **records** the growing age and **acts on none of it** — no timeout, no
  substituted value, no fault (`bridge-design.md` §1.1). The detection is the
  PLC's, and it is §B2.7a.
* **L1cs is still negative for part of the belt traffic** (min −14.598 ms for
  `ConveyorBeltSpeed`, −28.299 ms for `ProductSensorRange`), reproducing the
  measurement-definition correction of §A.5 on a third dataset. Nothing is
  clipped.
* **L6 is 2.000 ms on three of the seven command changes and 4.000 ms on four**,
  i.e. one or two 2 ms physics steps, confirming §C.4: L6 is a property of the
  belt's mechanical state at the instant the command changes, not a constant.

## B2.5 L7 — the closed loop (item 4) — **filled, on a different input than §11 T3 nominates**

The derivation is §B.5's, unchanged: **start** = `t_end_ns` of the `L2` row for
the nominated input write, the instant the server acknowledged it; **end** =
`t_end_ns` of the first `read_rt` row for `ConveyorSpeedCommand` whose value
differs from the one in force.

**The input §11 T3 nominates produced no L7 in this run, and the reason is worth
recording rather than working around.** A process stop opening while the belt
runs answers with `ConveyorSpeedCommand → 0.0`. The capstone script pressed
process stop 6 s after each start press — but the product reaches the beam
**8.85 s** after the start press, and at the beam step 20 commands `0.0` on its
own. Both delivered presses therefore landed *during the dwell*, **0.75 s** and
**0.76 s** after the command had already reached `0.0`, so there was no command
change left for them to cause. This is the same shape part 1 hit (§B.5, "the
timeline's later interlock drops all landed while the command was already 0.0"),
arrived at from the opposite direction: there the cell never reached the beam, here
it reached it too soon.

What the run does give, at the same 20 Hz and by the same derivation, is the
**start press**, whose answer is `0.0 → ±0.15` and is equally a program reaction
rather than an echo:

| # | `PanelStartPressed` write ack (rel s) | cmd before → after | L7 (ms) |
|---|---|---|---|
| 1 | 164.2068 | 0.0 → +0.150 | **45.643** |
| 2 | 536.5556 | 0.0 → +0.150 | **45.922** |
| 3 | 560.0063 | 0.0 → −0.150 | **46.404** |
| 4 | 583.3557 | 0.0 → +0.150 | **46.882** |
| 5 | 606.9543 | 0.0 → −0.150 | **47.690** |
| 6 | 621.7071 | 0.0 → +0.150 | **45.447** |

**count 6, min 45.447, median 46.163, p95 47.690, max 47.690 ms.**

The caveats are part 1's and are not weakened by the change of input: the
interval **contains** the transfer into the process image, at least one OB30 scan,
the server's sampling of the output and **the bridge's own 0–50 ms poll phase**,
so it is an **upper bound** on the PLC's reaction and never a measurement of it.
The 2.2 ms spread across six events is the poll phase showing through, not the
program varying — and the cluster sits where part 1's did (median 46.8 ms), which
is the useful comparison.

For the nominated input the run gives a **bound from the 5 Hz observer instead of
a measurement**: the process-stop write was acknowledged at rel 546.2562 and
`CellProcessStopActive`, `CellResetRequired` and `CellCycleRunning → FALSE` were
all present in the **first observer sample after it**, 0.12 s later; the third
round repeats it at 593.0566 with 0.11 s. So the whole reaction completed inside
one 200 ms observer period, twice — which is consistent with the 46 ms figure
above and is not a substitute for it.

## B2.6 Startup rule against the real DB start values (item 5) — **filled**

The R3 startup rule was exercised at **seven** session establishments. The
sharpest record is `sessionB` (T4.8), where the panel levels were published one
at a time and the withheld list shrinks by one input per publish:

```
17:00:11,374 heartbeat withheld: ... ProductSensorRange, PanelStartPressed, PanelResetPressed,
             PanelStopCircuitClosed, PanelProcessStopCircuitClosed (startup rule R3)
17:00:11,432 heartbeat withheld: ... PanelStartPressed, PanelResetPressed,
             PanelStopCircuitClosed, PanelProcessStopCircuitClosed (R3)
17:00:19,043 heartbeat withheld: ... PanelStartPressed, PanelResetPressed,
             PanelProcessStopCircuitClosed (R3)
17:00:23,541 heartbeat withheld: ... PanelStartPressed, PanelResetPressed (R3)
17:00:27,842 heartbeat withheld: ... PanelResetPressed (R3)
17:00:32,143 startup rule satisfied: all 7 DemoCell/Input nodes carry a real cell
             sample; heartbeat begins advancing at 1
```

**20.84 s of held session with no heartbeat**, one input at a time, and the
heartbeat begins on the seventh and not on the sixth. `BridgeLinkOk` first reads
`True` in the very next diagnostics poll (17:00:33,096); the first poll of the
session, 17:00:11,380, read `BridgeLinkOk False` with `CellProcessStopActive` and
`CellResetRequired` both `True`. In the final session the same rule gives
`heartbeat_suppressed_cycles = 232`, i.e. **11.6 s** withheld while the seven
filled, with `BridgeLinkOk` going `True` at the 17:49:18,413 poll — 12.3 s after
process start.

### B2.6a The presence verdict now asserts, and the dwell is reached — §B.13 F1 is answered

Part 1's F1 was that `ProductPresentAtSensor` never changed state in 394 s. In
this run it changed state **six times** (three assertions and three releases,
1 Hz log and 5 Hz observer), and the reaction is measurable at 20 Hz:

| Event | first blocked `ProductSensorRange` write ack (rel s) | `ConveyorSpeedCommand → 0.0` ack (rel s) | interval |
|---|---|---|---|
| final clean cycle | 173.0059 (0.540033) | 173.1515 (from +0.150) | **145.6 ms** |
| capstone round 1 | 545.3552 (0.540033) | 545.5060 (from +0.150) | **150.8 ms** |
| capstone round 3 | 592.1554 (0.540033) | 592.3023 (from +0.150) | **146.9 ms** |

That interval contains `PRESENCE_FILTER` = 100 ms, at least one OB30 scan and the
bridge's 0–50 ms read poll, so **145.6–150.8 ms is exactly what a working 100 ms
filter looks like from a client** — and it is the figure `SPEC.md` §11 T1.4 asks
for ("`ProductPresentAtSensor` follows ~100 ms later"). The beam values are the
same 1.440088 / 0.540033 pair every earlier run recorded.

**The in-force filter time is confirmed at the watch table, which is the
instrument LESSONS 2026-07-28 requires for it.** F1's root cause was an instance
DB holding a stale `PT` of `T#1M_40S` where the interface default read `T#100ms`,
and the rule that came out of it is to read the *in-force* value online rather
than the default. Capture `plc/demo-cell/evidence/watch-table/Screenshot 2026-07-28 171656.png`
shows `"FB_DemoCellControl_DB".PresenceOnTimer.PT` monitoring at **`T#100MS`**,
beside `.ET T#0MS` and `.IN FALSE` on an idle cell. That is the fix, read from the
CPU, on a committed artifact — and it is the reason the three intervals above are
what they are.

Downstream of the verdict, in the final clean cycle: the command held `0.0` from
rel 173.1506 to rel 175.2007 — a dwell of **2.050 s** against `DWELL_TIME` =
`T#2s` — then reversed to −0.150, the beam cleared at rel 175.4533, the command
returned to `0.0` at rel 184.1017 and `CellCycleRunning` dropped. Forward stroke
**8.899 s**, return stroke **8.899 s**, position 0.0414 m → 1.3743 m → 0.0393 m.
**`SeqStep` 10 → 20 → 30 → 40 → 0 therefore ran end to end** — the sequence part 1
could never enter. `SeqStep` itself is Group 4 and is not on the server
(LIMITATION 3); what is recorded here is the setpoint and the timing the steps
produce.

## B2.7 Signal-loss cases and the T4 roster (item 6)

Case A, B and D were produced against the rebuilt program; case C was produced in
a form part 1 could not attempt. `EVIDENCE_SIGNAL_LOSS.md` now carries the PLCSIM
section this item requires, with the same figures and the four cases in its own
A/B/C/D order; what follows here is the T4 accounting.

| Case | How it was produced | What the program did | Verdict |
|---|---|---|---|
| **A** — bridge SIGKILL | `kill -9` the bridge mid-cycle, 15:12:27.385 **[transcript]** | heartbeat froze at **11873**; `BridgeLinkOk → False`, `CellCycleRunning → False`, `CellResetRequired → True` and command `0.0` **all in the same 0.2 s observer sample**, 0.60 s after the last heartbeat change (bracket 0.40–0.80 s, consistent with `HEARTBEAT_STALE_TIME` 500 ms) | **as specified** |
| **B** — bridge SIGTERM | `kill -15`, logged 15:14:04.723 | heartbeat froze at **1377**; the identical four-way transition 0.60 s later | **indistinguishable from A at the program**, as §8 requires |
| **C** — CPU STOP → RUN under a **surviving** bridge session | owner pressed STOP, then RUN, ~16:51:30 **[transcript]** | the restart reverted the inputs to start values; `CellProcessStopActive` and `CellResetRequired` latched and **stayed latched for 4 min 31.1 s** (16:52:08.875 → 16:56:40.008, 1 Hz log), because the bridge never repaired the reverted image | **program correct, bridge defective** — §B2.13 F5 |
| **C** — CPU STOP → RUN with the bridge **stopped** | a second STOP → RUN at 17:16:56 – 17:17:27, captured in the watch table before / during / after | `ProductSensorRange` reverted **1.440088 → 0.0**; `ProcessStopLatch` went **FALSE → TRUE** and `SensorFaultLatch` **FALSE → TRUE**, with `BridgeLinkOk` reading `FALSE` and `LinkLostLatch` `TRUE` on both sides | **as specified**, and it is the only Group 4 record of a restart — §B2.7c |
| **D (ii)** — Gazebo killed **mid-motion**, bridge alive | `kill -9 gz sim` 6.25 s into a forward stroke | heartbeat **kept advancing in every one of the 891 observer samples**, `BridgeLinkOk` stayed `True` and `CurrentSessionCount` stayed 2 throughout; the image froze at position **0.9636 m** and speed **0.1500 m/s**; `ConveyorDriveFault` latched, cycle dropped, command → `0.0`, `CellResetRequired → True` | **detected in 2.301 s** — §B2.7a |
| **D (i)** — Gazebo killed **during the dwell** | `kill -9 gz sim` 16:33:32.399 **[transcript]**, presence `True` | step 30 commanded −0.150 into a dead cell at the end of the 2 s dwell; fault, cycle drop and `CellResetRequired` first seen together at 16:33:35.486 (1 Hz log) — `DRIVE_FAULT_DELAY` = 1 s after the setpoint went non-zero | **as specified**, on the D1 path |

### B2.7a T4.6, the re-measure — the number the step asks for

`SPEC.md` §11 T4.6 asks for the elapsed time **from the last changing sample of
`ConveyorBeltPosition` to `ConveyorDriveFault` going `TRUE`**, recorded as a
number, against a bound of **≤ 3.2 s** and a floor of **≈ 2.1 s** (§6.6.2).

The 20 Hz CSV carries the freeze exactly. The last write that carried a **new**
position value is

```
L2 ConveyorBeltPosition  t_start_ns=79555974575410  t_end_ns=79555975237383
                         value=0.9636000372489671        (rel 628.0015 / 628.0022)
      preceding write    value=0.9630000372251254        (rel 627.9543)
```

and the next 99 writes repeat `0.9636000372489671` bit for bit. `ConveyorDriveFault`
is not itself timestamped in the CSV — it appears only in the 1 Hz `diagnostics`
rows — so the reaction is timed by the thing the fault causes and the CSV does
timestamp at 20 Hz, `ConveyorSpeedCommand` leaving `+0.15`:

```
read_rt ConveyorSpeedCommand  t_start_ns=79558274098549  t_end_ns=79558275899123
                              0.15000000596046448 -> 0.0     (rel 630.3010 / 630.3028)
```

> **Freeze to reaction = (79558275899123 − 79555975237383) / 1e9 = 2.301 s.**

Three things corroborate it, from two other instruments:

* the 1 Hz diagnostics bracket the fault itself: `ConveyorDriveFault` reads
  `False` in the poll following rel 629.655 and `True` in the poll following rel
  630.705, so the latch and the zeroed command are the same event;
* the 5 Hz observer reproduces the whole sequence independently — last changing
  position sample at its t = 95.9752 (0.9636000394), and
  `ConveyorDriveFault True` with `CellCycleRunning False`, command `0.0` and
  `CellResetRequired True` together at t = 98.1821: **2.207 s** at 0.2 s
  granularity, where both endpoints may be up to one sample late;
* 2.301 s lies **inside** §6.6.2's specified window [≈2.1 s, 3.2 s]. That is
  itself evidence about *which term fired*: D1 would have latched about 1 s after
  the freeze, and the frozen speed read-back was **0.1500000059**, not zero, so D1
  was blind by construction. The re-armed D2 window of §6.6.1 is the only term
  that can produce a verdict in this window.

**What is not established, and is not inferred away.** T4.6's pass also names
Group 4: `PositionRef` re-sampling at the frozen position and `PositionFrozen →
TRUE` at the next window expiry. **No owner capture covers this event.** The
2026-07-28 captures were swept by filename and then opened: the last **watch
table** of the day is `Screenshot 2026-07-28 173615.png` at 17:36:15, and the only
later capture, `174127.png` at 17:41:27, is the CPU's *Cycle time* panel and
carries no tag at all (§B2.9). The re-measure was at ~17:59:36, twenty-three
minutes after the last watch table. So the *term* is a reasoned inference from the
elapsed time and the non-zero frozen speed, not a reading. It is carried as an
outstanding row (§B2.12 row 18). The same is true of T4.6b at 16:33 — the
2026-07-28 captures jump from 14:41:16 to 17:09:20, so nothing covers it either.

The freeze was well inside the stroke, as the step requires: the command went to
`+0.150` at rel 621.7526 and the freeze is at rel 628.0015 — **6.25 s in** — with
the belt 0.9285 m from where it started (0.0351 m at rest). The transcript's
run-time figure for the same event was **2.79 s** at the shell's 0.25 s poll
granularity plus the 1 Hz diagnostics lag **[transcript, kill at 17:59:35.618]**;
it is the same event seen through a coarser instrument and **2.301 s is the
measurement**.

For comparison and not as a claim, part 1's D-mid-motion figure on the m3-05 build
was `ConveyorDriveFault` **`False` in every one of 3 907 samples, 26.3 s
undetected** (§B.13 F2). The m3-29 re-arm is what changed between the two.

### B2.7b The T4 roster of this run, step by step

`SPEC.md` §11 T4 defined **thirteen** steps when this session ran, and defines
**fourteen** at the time of writing (m3-34 split the belt-plausibility latch out
as **4.11b**). The rows below are the **thirteen-step table the run was made
against**; 4.11b is listed as an outstanding row and **not** as a fourteenth
as-run row, because the denominator of a run that already happened does not grow
(`SPEC.md` §11 rule 2, LESSONS 2026-07-28).

| Step | Build | As run | Verdict |
|---|---|---|---|
| 4.1 **(A)** | C | `kill -9` mid-cycle; four-way reaction one 0.2 s sample after the heartbeat froze | **pass** — §B2.7 case A. The belt kept running in Gazebo **[transcript]**; the §8 residual is unchanged |
| 4.2 | C | fresh bridge session at observer t = 20.8926; its heartbeat first appears (at **3**, a new process's counter) in the sample at t = 41.789, the same sample in which `BridgeLinkOk` returns `True`; **nothing moved for the next 36.97 s** until the reset at 78.7596, command `0.0` throughout | **pass on what the step then asked**; `HeartbeatSeenAlive` and `ResetDeviceFault` are Group 4 and were not read, and m3-34 added both to the step — see §B2.12 |
| 4.3 | C | reset rising edge 78.7596 cleared `CellResetRequired` in the same sample and **moved nothing**; the separate start at 85.5945 started the cycle (at −0.150: the re-home branch, belt off home) | **pass on what the step then asked**; re-run needed against the corrected build (§B2.12) |
| 4.4 **(B)** | C | `SIGTERM` logged 15:14:04.723; heartbeat froze at 1377; identical transition 0.60 s later | **pass — identical to 4.1 at the program** |
| 4.5 **(C)** | C | CPU STOP → RUN with the bridge session surviving; latches held 4 min 31.1 s and no reset could clear them | **ran; program correct, and a bridge defect found** (§B2.13 F5). Not a clean pass: the step's second half needs the bridge to supply real samples, which it did not |
| 4.6 **(D ii)** | **F** | freeze at rel 628.0015 → reaction at rel 630.3028 | **pass on the elapsed-time bound: 2.301 s against ≤ 3.2 s, ≥ 2.1 s.** `PositionFrozen` not read (no capture) |
| 4.6b **(D i)** | C | Gazebo killed during the dwell; fault 1 s after step 30 commanded −0.150 into a dead cell (16:33:35.486) | **pass on the reaction and the timing.** `PositionFrozen` staying `FALSE` is **[transcript, owner capture 16:33:32]** and that capture is **not** in the committed directory |
| 4.7 (inverted) | C | after the 16:38 case-D fault, the reset attempted at 16:38:23 **[transcript]** was **refused** — `CellResetRequired` and `ConveyorDriveFault` read `True` in every 1 Hz poll from 16:38:17.014 to 16:38:52.035, **35.0 s** — and cleared only after the simulation was revived; a **separate** start press then re-ran the cycle (16:38:59.241 → clean end 16:39:19.958) | **pass, in the inverted form m3-29 specified.** The "re-latches within 1 s of a start press against a dead cell" half is separately shown by the accidental idle variant: cycle at 16:32:44.616, fault at 16:32:45.620 |
| 4.8 | C | the R3 half ran and is recorded in §B2.6 | **partial.** The **cold start of the CPU was not performed** — the CPU stayed in RUN all afternoon. The pre-check reading of all seven inputs at their §3.1 start values with the bridge down is **[transcript, 17:00:07]**; the log corroborates only `BridgeLinkOk False` with both latches set |
| 4.9 | C | `reset` published `true` and left published; a stop latched at 16:40:29.177 and stayed latched for **20.56 s** of continuous hold; a fresh edge cleared it at 16:40:49.737 | **pass exactly.** Repeated a second time in the same log (16:41:09.235 → 16:41:16.651) |
| 4.9b | C | fresh bridge 17:02:20.941 with `reset` held `true` from before link-up | **FAILED** — every latch clear within 0.655 s of the heartbeat starting. §B2.13 F3 |
| 4.10 | C | `CurrentSessionCount` sampled at 5 Hz across both kills | **measured**, §B2.8 |
| 4.11 | **E** | reaction path **demonstrated [transcript]** at 17:30:45 and 17:36:50; latch step **not testable by the specified method** | **partial, and the instrument the step now names did not survive.** §B2.13 F4 |

**No pass over T4 is claimed from this evidence, and the arithmetic is stated
rather than implied.** Of the thirteen steps the run was made against: **eight
pass** (4.1, 4.4, 4.6, 4.6b, 4.7, 4.9, and 4.2/4.3 against the step as it then
read), **one is measured with no pass/fail to give** (4.10), **two are partial**
(4.8, 4.11), **one ran and exposed a bridge defect instead of completing**
(4.5), and **one FAILED** (4.9b). Against the **fourteen**-step table as it stands
now, five of those results additionally do not carry over, because m3-34's §6.8
delta changes the observable behaviour of every step that crosses a CPU start or a
link-up — 4.2, 4.3, 4.5, 4.8 and 4.9b — and 4.11b did not exist. All of that is
§B2.12; none of it is absorbed into a larger as-run denominator.

### B2.7c The one Group 4 record of a CPU restart — the 17:16:56 / 17:17:12 / 17:17:27 triple

Three owner captures of the §9 Group 4 watch table, before / during / after a
second CPU STOP → RUN, **with the bridge stopped** (it had been down since
17:14:07). They are the only committed watch-table record of a restart, and they
carry readings no OPC UA client in this run could reach. All three show the same
16-row table; only the changing cells are given.

| Tag | `171656.png` — before, CPU **RUN** | `171712.png` — CPU **STOP** | `171727.png` — after, CPU **RUN** |
|---|---|---|---|
| `"DemoCellInput".ProductSensorRange` | **1.440088** | 1.440088 | **0.0** |
| `PresenceOnTimer.PT` | **T#100MS** | T#100MS | **T#0MS** |
| `"DemoCellLink".BridgeLinkOk` | FALSE | FALSE | FALSE |
| `ProcessStopLatch` | **FALSE** | FALSE | **TRUE** |
| `LinkLostLatch` | TRUE | TRUE | TRUE |
| `SensorFaultLatch` | **FALSE** | FALSE | **TRUE** |
| `SeqStep` / `ResetDeviceFault` / `PositionFrozen` | 0 / FALSE / FALSE | 0 / FALSE / FALSE | 0 / FALSE / FALSE |
| `PositionRef` | 0.1995 | 0.1995 | **0.0** |
| CPU operator panel | RUN/STOP **green** | RUN/STOP **yellow** | RUN/STOP **green** |

Four things this settles that nothing else in the run does:

1. **The restart reverts the input image to the DB start values of §3.1, and the
   captures show it happening**: `ProductSensorRange` 1.440088 → **0.0**. The
   1.440088 on the left is the bridge's last written value, still standing two and
   a half minutes after the bridge stopped — the freeze of `EVIDENCE_SIGNAL_LOSS.md`
   case A — and 0.0 on the right is the DB's own start value. §8 case C's "lost
   entirely when the server restarts" is now a reading rather than an inference.
2. **The reverted start value is caught by §6.2's plausibility window, not passed
   as a measurement.** `0.0` is below `RANGE_MIN` = 0.05, so `RangeValid` is false
   and `SensorFaultLatch` sets after `RANGE_FAULT_DELAY`. That is the affirmative
   window doing exactly the job LESSONS 2026-07-27 asked of it.
3. **`ProcessStopLatch` went TRUE across the restart while `BridgeLinkOk` reads
   `FALSE` and the inputs stand at start values.** §7 part 4 gates that latch on
   `linkOk`, so on this build the latch can only have formed inside the **500 ms
   boot window** in which `NOT HeartbeatStaleTimer.Q` is still `TRUE` — and by the
   time of the capture the timer had expired, leaving a set latch beside a `FALSE`
   verdict. **This is the old-build cold-start signature, captured**, and it is
   precisely the reading m3-34's §6.1 changes to `ProcessStopLatch FALSE`. See
   §B2.12a: it is recorded as correct for the build that produced it, and is not
   reconciled to the corrected expectation.
4. **`PositionRef` was reinitialised** 0.1995 → 0.0, i.e. the restart cleared the
   instance DB as §3.1's "no tag is declared Retain" requires. `PositionFrozen`
   stayed `FALSE` throughout, which is the correct verdict for a belt that is not
   claiming motion.

**One reading is not explained here and is handed to `plc/` rather than
diagnosed** — see §B2.13 F6: `PresenceOnTimer.PT` reads `T#100MS` before the
restart and `T#0MS` after it.

## B2.8 Session behaviour on a real server (item 7) — **filled**

`CurrentSessionCount` from `plc-observe-2026-07-28-t4a-caseAB.csv.gz`, raw
transitions on the observer's own clock, with the observer itself always one of
the counted clients:

```
t = 0        count 2   bridge #1 + observer
t = 13.4576  (last heartbeat change of bridge #1 — the SIGKILL)
t = 20.8926  count 3   bridge #2 connects; the killed session is still counted
t = 33.5542  count 2   the killed session is reaped
t = 110.504  (last heartbeat write of bridge #2 — the SIGTERM)
t = 110.705  count 1   closed in the next 0.2 s sample
t = 118.1373 count 2   bridge #3 connects
```

| Event | Session still counted for | Against a granted timeout of |
|---|---|---|
| bridge **SIGKILL** | **20.10 s** after the last heartbeat change (13.4576 → 33.5542) | 10 000 ms |
| bridge **SIGTERM** | **≤ 0.2 s** — gone in the next sample | 10 000 ms |

**Reported raw, with no interpretation offered.** The SIGKILL hold is twice the
granted timeout and 1.7× part 1's 11.79 s for the same granted value on the same
instance; this evidence does not say why, and nothing in the program or the bridge
consumes the figure (`SPEC.md` §11 4.10 forbids it as an input). The transcript's
run-time estimate was **≈22 s** **[transcript]**, measured from the shell's kill
instant rather than from the last heartbeat, which accounts for the difference. As
in part 1, this is the **only** measurable difference between A and B, it lives at
the session layer, and §B2.7 confirms the program saw none of it.

## B2.9 Environment, the program builds of the day, and the network path (item 1) — **filled**

The stack is **§B.0's, unchanged**: TIA Portal V21, S7-PLCSIM Advanced V7.0, a
simulated CPU 1513-1 PN at firmware V3.1, endpoint `opc.tcp://192.168.53.1:4840`,
security `None` + anonymous, browse path through `ServerInterfaces` into
`http://DemoCell`. Bridge host: WSL2 Ubuntu 24.04, ROS 2 Jazzy, Gazebo Sim
8.11.0, Python 3.12, `asyncua` 2.0.1 in `/home/ozkan/amr-bridge-venv`, repo on
`/mnt/c`.

**The network path is part 1's measurement (§B.9) and is not re-measured here.**
Same host, same adapters, same instance: WSL2 `eth0` → Hyper-V `vEthernet (WSL)`
→ `Ethernet 2` (the PLCSIM virtual adapter) → the instance, one router hop, no
switch and no VPN. **Tailscale is not in it** — invariant 8 held by routing table
in §B.9 and nothing in this run changed a route.

**The program was rebuilt five times during the session**, and this is what each
letter above means. Rebuild baseline: `plc/demo-cell/SPEC.md` @ `39a21b6`.

| Build | Downloaded | Content |
|---|---|---|
| **A** | before 2026-07-28 | the m3-05 program part 1 measured |
| **B** | ~13:00 **[transcript]** | the three-delta build: the released dwell timer, the belt plausibility window, the re-armed case-D window |
| **C** | ~14:38, in force **[transcript]** | + the `PRESENCE_FILTER` fix. **Every 1 Hz-log figure in this section, 15:01 – 17:14, is build C** |
| **D** | ~17:33 **[transcript]** | a full re-download restoring project/CPU consistency; same source as C |
| **E** | ~17:35 **[transcript]** | `BELT_SPEED_MIN`/`MAX` narrowed to ±0.10 — the **modified** program T4.11 requires, not a gate build |
| **F** | ~17:45 **[transcript]** | ±1.00 restored. **Every 20 Hz-CSV figure in this section, 17:49 – 18:01, is build F** |

**The CPU's cycle time is recorded, from a committed artifact.** It is not on the
`DemoCell` interface and no client in this run could read it — but the owner
captured TIA's *Cycle time* panel, and the capture is committed at
`plc/demo-cell/evidence/watch-table/Screenshot 2026-07-28 174127.png` (17:41:27).
The panel reads:

| | |
|---|---|
| Shortest | **1.004 ms** |
| Current/last | **1.023 ms** |
| Longest | **2.556 ms** |
| bar-chart axis | 1.023 → **150** ms |

**§B.12 item 3 closes on this**, and it is the figure `SPEC.md` §11 T3's second
PLC-side obligation asks for. Two limits on what the capture shows, stated so it
is not over-read: the panel is TIA's **CPU cycle-time** panel, so it does not
itself name the OB30 period — the 20 ms is `SPEC.md` §3.3's configured value
standing beside this reading, not something the capture proves — and the `150` at
the right of the axis is an unlabelled axis limit, not a value the panel attributes
to anything. **No decomposition of L7 is derived from these numbers**; what they
establish is only that the CPU was running its program in ~1 ms with a worst case
of 2.556 ms, i.e. two orders of magnitude inside the 20 ms interrupt period it is
called from, and that the OB30 contribution to §B2.5's 45–48 ms is therefore small
rather than dominant.

## B2.10 Which server produced each number (item 8) — **filled**

Every figure in this section came from `opc.tcp://192.168.53.1:4840`, the PLCSIM
Advanced instance with the standard program in RUN. **The test double was not
running at any point**, on this endpoint or any other, and the
connect-conformance harness was kept off it (`bridge-design.md` §10).
`CurrentSessionCount` corroborates it directly: across 400 s of observation the
count took the values **1, 2 and 3 only**, and each transition is accounted for by
a bridge process starting or a killed session being reaped (§B2.8) — with the
count reaching **1** at t = 110.705, when the observer was demonstrably the only
client on the endpoint. There was no room for a fourth client and none appeared.

## B2.11 Configuration and code changes — **none**

`bridge/config/bridge.yaml` was already pointed at the PLCSIM endpoint by part 1.
**No file in `bridge/` was edited to make this run work**: no code change, no
security field, no hardcoded namespace index, no new tool. `tools/observe_plc.py`
and `tools/cell_stimulus.py` are the committed ones. The one operational change
was the `--evidence-csv` path, which was **not** varied per session — and that is
LIMITATION 1, i.e. the change that should have been made and was not.

## B2.12 Disposition of every outstanding row, and this run's own list

> **Rows 14–22 below were dispositioned again after the §6.8 rebuild re-run of the
> same evening — see §B3.4.** Closed there: row **20**, row **21**'s rule, row
> **14**'s failing form, and 4.3 of row **17**. Partly closed: the rest of rows
> **14** and **17**. Still open: rows **15**, **16**, **18**, **19** and **22**.
> Nothing in this subsection is edited.

**Part 1's thirteen rows (§B.12), by number.** No row of §B.12 is edited; this is
where each one stands after 2026-07-28.

| §B.12 # | Now | Where |
|---|---|---|
| 1 | **still open** — gate exit item (a) in the *watch table*. This run's instrument is again OPC UA-side | owner captures exist for 2026-07-28 (24 files) and are the owner's to interpret; this file does not |
| 2 | **still open** — gate exit item (b), same reason | as above |
| 3 | **CLOSED.** The CPU's cycle times are recorded — 1.004 / 1.023 / 2.556 ms — from the owner's committed capture of TIA's *Cycle time* panel, `watch-table/Screenshot 2026-07-28 174127.png` | §B2.9 |
| 4 | **still open** — L4 on the PLC side needs the watch table to timestamp the output change inside the CPU | §A.6 bound stands |
| 5 | **ran, in one of its two forms.** Case C as a **CPU STOP → RUN** was performed; a *network/adapter* break with the CPU running was not | §B2.7 case C, §B2.13 F5 |
| 6 | **split.** T4.9b **ran and failed** — no longer untested, and no longer a cold-start-only question. T4.8's R3 half ran; its **cold start did not** | §B2.7b, §B2.13 F3 |
| 7 | **still open** — T4.10 on real hardware. §B2.8 measures PLCSIM Advanced, and the two PLCSIM figures (11.79 s, 20.10 s) already differ by 1.7× for the same granted timeout | §B2.8 |
| 8 | **CLOSED.** The dwell at the beam was reached: presence asserted in 145.6–150.8 ms and the dwell ran 2.050 s | §B2.6a |
| 9 | **superseded and re-opened as two rows.** m3-34 reduced 4.11 to the reaction path — demonstrated **[transcript]** — and moved the latch to the new **4.11b** | rows 15 and 16 below |
| 10 | **CLOSED.** T4.6 as re-specified ran on build F: **2.301 s**, inside [2.1, 3.2] s | §B2.7a |
| 11 | **CLOSED for the reaction, open for the term.** 4.6b ran on build C with the correct D1 timing; `PositionFrozen FALSE` is transcript-only | §B2.7b |
| 12 | **CLOSED.** 4.7 in its inverted form ran and passed: 35.0 s of refusal across a reset attempt, then honoured after the revive | §B2.7b |
| 13 | **CLOSED.** The build behind every figure in part 2 is named in §B2.9 and carried per figure | §B2.9 |

**Part 2's own outstanding rows.**

| # | Item | Why it is open, and what it needs |
|---|---|---|
| 14 | **T4.9b re-run — two preconditions, not one** | (i) the owner's **§6.8 rebuild** (`HeartbeatSeenAlive` as the first term of `BridgeLinkOk`, and `ResetDeviceFault` re-armed per **link session** rather than per program run), and (ii) the step re-run against that build in **both** of its forms — (a) fresh bridge with the reset held, which is the form this run used and failed, and (b) CPU start with the reset held. Neither the failure nor the fix is a bridge change; see `docs/reports/m3-34-link-polarity-spec.md`. A pass is claimable only against the corrected build |
| 15 | **T4.11 — the reaction path, re-recorded** | The step now says to read the pass **off the 20 Hz evidence CSV, not the watch table** — and the CSV that carried it was overwritten by a later bridge start (LIMITATION 1). The reaction is demonstrated **[transcript, 17:30:45 and 17:36:50]** and is corroborated by no committed file. Needs one short re-run on build E with a **per-session CSV name**, which is also the fix for LIMITATION 1 |
| 16 | **T4.11b — the latch, the reset refusal, the reset that clears it** | **BLOCKED on a facility that does not exist**: `SPEC.md` §12 item 6 asks `bridge/` for an explicitly opt-in fault-injection mode that writes a nominated `DemoCell/Input/` Real as `NaN`, `inf` or an out-of-window value **and holds it until disarmed**. Not blocked on any rebuild. Requested here, not built: it is a `bridge/` deliverable and needs its own brief |
| 17 | **4.2, 4.3, 4.5 and 4.8 re-run against the corrected build** | Each crosses a CPU start or a link-up, so §6.8 changes its observable signature (`SPEC.md` §6.8, *which recorded results survive*). Their results above are correct **for build C** and are labelled as such |
| 18 | **The Group 4 reading of `PositionFrozen` / `PositionRef` for T4.6 and T4.6b** | No capture covers either moment: the day's last watch table is 17:36:15 and the 17:41:27 capture is the cycle-time panel, against a re-measure at ~17:59:36; and the captures jump 14:41:16 → 17:09:20 across T4.6b at 16:33. Which term fired is inferred in §B2.7a, not read |
| 19 | **Case C as a link break with the CPU running** | STOP → RUN was performed in **both** of its bridge states — session surviving (§B2.13 F5) and bridge stopped (§B2.7c) — but stopping the adapter with the program still running was not |
| 22 | **Why `PresenceOnTimer.PT` reads `T#0MS` after a CPU restart** | §B2.13 F6. An observation of five committed captures, handed to `plc/` undiagnosed. If the `PT` is not re-asserted at the call site every scan, `PRESENCE_FILTER` is 0 after any restart until something rewrites it — which is the failure mode LESSONS 2026-07-28 already recorded once, from the other direction |
| 20 | **A bridge that repairs the input image after a server restart** | §B2.13 F5, carried as `SPEC.md` §12 open item 7. A `bridge/` deliverable, requested here rather than written |
| 21 | **The 17:14:07 – 17:49:06 window has no committed bridge artifact at all** | The T1.4 re-run of 17:14:37 – 17:15:06 and all of T4.11 fall in it, and neither the CSV nor a 1 Hz log survives. Both are transcript-only above. Nothing needs re-running to *fix the past*; the rule is one CSV and one log per bridge session, uniquely named |

### B2.12a The cold-start signature is now a moving target, deliberately

Every process-stop reading in this section is **correct for build C**, whose
`BridgeLinkOk` is `NOT HeartbeatStaleTimer.Q` and therefore boots `TRUE` for the
first 500 ms of every CPU run. m3-34 changed that on purpose: with
`HeartbeatSeenAlive` conjoined, `BridgeLinkOk` is `FALSE` from the first scan and
the expected reading becomes `CellProcessStopActive` / `ProcessStopLatch`
**`FALSE`** (`SPEC.md` §6.1, §11 4.5 and 4.8). **The readings are not reconciled
to the new expectation and must not be.** Three of them, and what each actually
shows, because they are not the same observation three times:

* **`sessionB` 17:00:11,380 and `sessionC` 17:02:21,015** read
  `CellProcessStopActive True` in their first diagnostics poll. Both are **held**
  latches: a latch is a level bit, and this evidence does not time when either was
  formed. They say nothing about the boot window either way.
* **T4.5's first restart (16:52:08.875)** formed its latch because a *surviving*
  bridge session's heartbeat resumed over a reverted input image — the F5
  mechanism, and nothing to do with the boot polarity.
* **T4.5's second restart (§B2.7c, 17:17:27)** is the one that does read the boot
  window, and it reads it unambiguously: `ProcessStopLatch` **`TRUE`** beside
  `BridgeLinkOk` **`FALSE`** with the inputs at start values and the bridge
  stopped. §7 part 4 gates that latch on `linkOk`, so the only scan in which it
  could have formed is one inside the 500 ms window. **That capture is the
  old-build signature, and after the §6.8 rebuild the same three captures should
  read `ProcessStopLatch FALSE`.** It is the cheapest available before/after test
  of the fix, and re-run row 14 is where the "after" belongs.

`LinkLostLatch` and `CellResetRequired` are `TRUE` in every one of these readings
and are expected to stay `TRUE` after the rebuild; nothing about the required
monitored reset is weakened by the correction.

## B2.13 Findings

Four new findings — F3 and F4 against the program, F5 against the bridge, F6 an
observation handed on undiagnosed. F1 and F2 are part 1's and are **answered**
rather than restated (§B2.6a, §B2.7a). Nothing was adjusted to make anything pass.

### F3 — T4.9b failed: a reset held from before link-up cleared every latch

`bridgelog-2026-07-28-sessionC-t49b.log.gz`, in full, four lines:

```
17:02:20,941 bridge ROS 2 node cell_plc_bridge spinning
17:02:21,015 PLC diagnostics: {... CellProcessStopActive: True, CellResetRequired: True,
                                   ConveyorDriveFault: False, BridgeLinkOk: False}
17:02:30,610 startup rule satisfied: all 7 DemoCell/Input nodes carry a real cell sample;
             heartbeat begins advancing at 1
17:02:31,265 PLC diagnostics: {... CellProcessStopActive: False, CellResetRequired: False,
                                   ConveyorDriveFault: False, BridgeLinkOk: True}
```

The bridge was started fresh with `/cell/panel/reset` already publishing `true`
and latches pending. `SPEC.md` §11 4.9b requires that no reset be possible: the
guard should read `TRUE` before, through and after link-up, and the edge that
arrives with the first attributable sample should be **refused**. Instead
**every latch was clear in the first diagnostics poll after the heartbeat
started**, 0.655 s later, in the same poll in which `BridgeLinkOk` first read
`True`. The transcript's run-time reading was "by 17:02:36" **[transcript]**; the
log puts it 5 s earlier.

**Root cause, code-confirmed and now fixed in the specification.** The build
implements `BridgeLinkOk := NOT HeartbeatStaleTimer.Q`, which reads "not *yet*
proven stale" and is therefore `TRUE` for the first `HEARTBEAT_STALE_TIME` of
every CPU run. In that window the reset input's start value `FALSE` satisfied
"seen open with the link up", so `ResetDeviceFault` cleared on the first scan;
the held `true` then registered as a genuine rising edge the moment real samples
arrived. LESSONS 2026-07-28 states the rule this became: *a link verdict is FALSE
until the heartbeat has been seen to change at least once; "not yet proven stale"
is not "alive", and every guard that rides on link-up inherits the boot polarity.*
The correction is `SPEC.md` §6.1, §6.7 and the §6.8 implementation delta, recorded
in `docs/reports/m3-34-link-polarity-spec.md`. **It is a PLC change; nothing
bridge-side is implicated, and the bridge's behaviour in this capture was
correct** — it withheld the heartbeat until all seven inputs were real, exactly as
R3 requires, which is *why* the link-up instant is so sharply visible.

### F4 — T4.11's latch cannot form by the method the step named, and the CSV that showed it is gone

`BELT_SPEED_MIN`/`MAX` were narrowed to ±0.10 (build E) and start pressed. The
run's own record is that the reaction path worked and the latch never formed:
C5 dropped the cycle and zeroed the setpoint within one scan, the plant then
recovered *inside* the narrowed window in ~100–150 ms — under `BELT_FAULT_DELAY`
= 200 ms — so `BeltFeedbackFaultLatch` was released before `Q` could be reached.
**The test is extinguished by the reaction it triggers.** LESSONS 2026-07-28
records it, m3-34 acted on it: §11 4.11 is now the reaction path alone with the
latch explicitly not expected, and the latch moved to the new **4.11b** on a
fault-injection facility that does not exist (§12 item 6).

**Two figures here do not reproduce, and that is the second half of the finding.**
The brief for this write-up expected the ~100–150 ms speed blips to be citable
from the 20 Hz CSV — the very instrument §11 4.11 now nominates. They are not in
it. The committed CSV contains **seven** contiguous episodes of
`|ConveyorBeltSpeed| > 0.05`, and every one is a full stroke of 8.85–11.15 s;
there is no episode of any length near 100–150 ms anywhere in the file, because
the file begins at 17:49:06 and the presses were at **17:30:45 and 17:36:50**
**[transcript]** — before the bridge restart that truncated it. LESSONS 2026-07-28
records **five** such presses; the two above are the two the transcript
timestamps.

**The two owner captures nearest in time were opened, and they corroborate weakly
and non-contemporaneously — which is all that can honestly be claimed of them.**
Both are the §9 Group 4 watch table:

| | `173247.png` (17:32:47) | `173615.png` (17:36:15) |
|---|---|---|
| relation to a press | **2:02 after** the 17:30:45 press | **0:35 before** the 17:36:50 press |
| `BeltFeedbackFaultLatch` | **FALSE** | **FALSE** |
| `BridgeLinkOk` | TRUE | TRUE |
| `SeqStep` | 0 | 0 |
| `ProcessStopLatch` / `LinkLostLatch` / `SensorFaultLatch` | FALSE / FALSE / FALSE | **TRUE / TRUE / TRUE** |
| `ResetDeviceFault` / `PositionFrozen` | FALSE / FALSE | FALSE / FALSE |

`BeltFeedbackFaultLatch` reading `FALSE` in both is consistent with the latch never
forming, and that is the whole of the corroboration. **Neither capture is
contemporaneous with a press**: the event is shorter than one watch-table update,
which is exactly why §11 4.11 now nominates the CSV instead. The second capture
additionally shows **three latches already pending 35 s before the second press**,
so unless a reset intervened in those 35 s that press could not have started a
cycle at all — and this evidence cannot say which happened.

**One inconsistency the sweep exposed, which no committed artifact resolves.** The
first press is timestamped **17:30:45** while the ±0.10 download is timestamped
**~17:35**, with a full re-download at ~17:33 between them (§B2.9, all
**[transcript]**) — so on those timestamps the first press predates the narrowed
constant it is supposed to have exercised. Either the download times are loose or
the two presses were against different builds. It is left standing rather than
resolved by choosing, and it is a second reason outstanding row 15 wants a short
re-run whose build and CSV are recorded together.

**So: the finding stands on the transcript and on the code, and the measurement it
rests on has no committed artifact.** Outstanding row 15.

### F5 — the bridge does not repair a reverted input image, so a CPU restart cannot be recovered from

This is a **bridge** defect, found by the program behaving correctly. The owner
put the CPU to STOP and back to RUN at ~16:51:30 **[transcript]** while a bridge
session was live. The restart reverted every input to its start value. The
program then did exactly what its rules say: the stop circuits read open, so
`CellProcessStopActive` and `CellResetRequired` latched, the command stayed `0.0`
and nothing ran.

The 1 Hz log measures how long that lasted: the latches first appear at
**16:52:08.875** and clear at **16:56:40.008** — **4 min 31.1 s** — and the
monitored reset was correctly refused throughout, because the cause had not gone.
The owner cleared it by force-toggling the levels **[transcript, ~17:05]**, after
which the reset behaved normally.

**The mechanism, from the same artifact.** The `sessionA` log carries **no
`session broken`, no `connect failed`, no reconnect and no read or write error**
between 15:14:24 and 16:57:31. The session survived the STOP → RUN; the bridge
therefore never re-established anything, and because it writes **on change**, the
slots whose values had not changed were never rewritten. The PLC read open stop
circuits for four and a half minutes from a bridge that believed it had already
sent the closed ones. LESSONS 2026-07-28 states the rule: *the bridge must detect
a server restart — the heartbeat node reverting, or session/subscription loss —
and rewrite every slot; until then, force-republish every level with a toggle
after any CPU restart.* `SPEC.md` §12 open item 7 now names it as a dependency of
the reset guard's guarantee and of §8 case C. It is **`bridge/` work and is
requested here rather than written**, because this brief's deliverable is the
evidence, not the fix (outstanding row 20).

One residual of the same event, recorded because it is a real limit and not a
defect: while the CPU was in STOP the server held the last command, `+0.15`, and
the belt kept running in Gazebo **[transcript]**. That is §A.7's residual again —
on real equipment the drive is dropped by a wired enable, not by an OPC UA value.
No safety function is involved and none is claimed (invariants 1 and 2).

### F6 — `PresenceOnTimer.PT` reads `T#100MS` before a CPU restart and `T#0MS` after it

Recorded because it is what the committed captures show, and **handed to `plc/`
undiagnosed** — it is a timer inside `FB_DemoCellControl` and nothing bridge-side
reaches it.

| Capture | `PresenceOnTimer.PT` |
|---|---|
| `171656.png`, 17:16:56, CPU in RUN before the restart | **`T#100MS`** |
| `171712.png`, 17:17:12, CPU in STOP | `T#100MS` |
| `171727.png`, 17:17:27, CPU in RUN after the restart | **`T#0MS`** |
| `173247.png`, 17:32:47 | `T#0MS` |
| `173615.png`, 17:36:15 | `T#0MS` |

The restart reinitialised the instance DB, which §3.1 requires — `PositionRef`
went 0.1995 → 0.0 in the same triple, and no tag in this program is `Retain`. The
question is why the `PT` did not come straight back: a TON called with
`PT := #PRESENCE_FILTER` at its call site every scan has that value in its
instance from the first call, so a `PT` of `T#0MS` on a running CPU says the
constant is not reaching the call every scan. If that reading is what it appears to
be, then **after any CPU restart `PRESENCE_FILTER` is effectively 0 until something
rewrites it** — the same class of failure as LESSONS 2026-07-28's stale
`T#1M_40S`, reached from the opposite direction, and the reason that lesson says to
verify the in-force value online rather than trusting a default.

**Three reasons this is a question and not a finding of fact.** It rests on
monitor values in screenshots and not on a code reading; a `PT` of `T#0MS` with
`IN` false and `ET` `T#0MS` may be how this CPU reports an instance whose timer has
not yet been enabled since reinitialisation; and the presence verdict demonstrably
worked afterwards — the three 145.6–150.8 ms intervals of §B2.6a were measured at
17:51 and 17:58, after all of these captures, and are consistent with a 100 ms
filter and not with a 0 ms one. That last point is the strongest argument that
nothing is broken in the delivered behaviour, and it is also why this is worth one
watch-table row at the next download rather than a brief of its own.
Outstanding row 22.

## B2.14 Two publishes that never arrived — tooling, not program

Both were suspected at run time as program refusals and both are settled by the
CSV, in the order LESSONS 2026-07-28 requires: **verify delivery before
interpreting a refusal.**

* **A start press at 17:49:38 [transcript] never reached the bridge.** The CSV
  carries no `PanelStartPressed` write between rel 27.6058 and rel 164.2057, and
  R3 reports `PanelStartPressed 14/13` — thirteen writes, all accounted for by
  transitions elsewhere, and only one received sample unwritten. A received
  `true` at that moment would have been a change and would have been written. It
  was not received.
* **One of the three capstone process-stop presses never reached the bridge.**
  The transcript records presses at 17:58:12, 17:58:36 and 17:58:59
  **[transcript]**; the CSV carries `PanelProcessStopCircuitClosed` writes for two
  of them (rel 546.2544 and 593.0557, each with its release) and R3 reports
  `7/5`. The level before the missing press was `True`, so a received `false`
  would have been a change and would have been written. The program was never
  presented with that press, and the 1 Hz log shows no `CellProcessStopActive`
  transition anywhere near it — the cycle that ended at that moment ended
  **cleanly**, its command having already reached `0.0` at rel 568.9518.

Both are the `ros2 topic pub --once` race of LESSONS 2026-07-28: `--once` exits
on the first matched subscriber, and this cell has more than one. Neither is a
program defect and neither is a bridge defect.

One further run-time misreading is recorded so it is not mistaken for an event: a
"wedged bridge" reported at 17:41–17:46 was a **stale log artifact on the
orchestrator's side** — a live process whose log's last line was minutes old —
and not a PLC event **[transcript]**. LESSONS 2026-07-28 carries the rule (a
polled log line is evidence only together with its age).

---

# Section B, part 3 — the §6.8 rebuild re-run, 2026-07-28 19:15–19:31

**Performed 2026-07-28, ~19:15–19:31 local (UTC+02:00), by the owner at the same
workstation, against the same PLCSIM Advanced instance and endpoint as parts 1
and 2**, with the `plc/demo-cell/SPEC.md` §6.8 delta implemented and downloaded.
Written up under brief `m3-36` from the artifacts the session committed. **No
figure of part 1 or part 2 is altered by this section**, and nothing was re-run to
produce it.

> **What this section is.** §6.8 says behaviour differs from the earlier build
> only at CPU start and at link-up, and names the five steps that cross one of
> those boundaries: §11 **4.8, 4.2, 4.3, 4.9b and 4.5**. All five were re-run.
> Four pass on their server-visible conditions, one passes and is the reversal of
> part 2's **F3**, and the bridge defect **F5** is fixed and measured. What does
> *not* close is stated as plainly as what does: three of the five carry a
> `SPEC.md` §9 **Group 4** condition that no instrument in this run can see, and
> the one direct reading that would settle the boot polarity — 4.8's cold start
> with the bridge **down** — was again not taken.

## B3.0 The build letter, the provenance, and the artifacts

**Naming correction, made here so nothing collides.** The `m3-36` brief calls the
§6.8 rebuild "**build E**". §B2.9 already uses **E** for the ±0.10 narrowed
program of T4.11 and **F** for the ±1.00 restored one. The §6.8 rebuild is
therefore **build G** throughout this section, and every occurrence of "build E"
in the `m3-36` brief means **build G** here. Nothing in §B2.9's table is edited.

| Build | Downloaded | Content |
|---|---|---|
| **G** | ~19:15 **[transcript]** | build F + the five edits of `SPEC.md` §6.8 as committed at `0080bff` — `HeartbeatSeenAlive` declared and latched, `BridgeLinkOk := HeartbeatSeenAlive AND NOT HeartbeatStaleTimer.Q`, and `ResetDeviceFault` re-armed per **link session** rather than per program run. **Every figure in this section is build G** |

**The owner's pre-run verification, recorded as the build's provenance.** Taken in
the watch table with the bridge **down**, before any step below **[transcript]**:

| Read | Value | Why it is the check §6.8 asks for |
|---|---|---|
| block comparison circles | solid green | the stale-build tell of LESSONS 2026-07-28; project and CPU consistent |
| `HeartbeatStaleTimer.PT` | `T#500MS` **in force** | a new static shifts DB offsets, and a download without reinitialisation preserves stale instance values (LESSONS 2026-07-28, F1) |
| `HeartbeatSeenAlive` | **TRUE** | the new static exists and latches — *but see the qualification below* |
| `BridgeLinkOk` | **FALSE** | the verdict is false with no bridge writing |
| `ResetDeviceFault` | **TRUE** | the per-link-session re-arm working; it was cleared-and-stuck under build C/D |
| `LinkLostLatch` | TRUE | unchanged by the correction, as §6.1 says it should be |
| `ProcessStopLatch` | **FALSE** | the corrected cold-start signature: the panel is not accused of a stop never seen |

**One qualification on that reading, because it changes what it proves.**
`HeartbeatSeenAlive` reads `TRUE` **because the bridge had already written briefly
after the download** — so this is a reading taken *after* a link session, not at
the first scan of a CPU run. `ProcessStopLatch FALSE` beside `BridgeLinkOk FALSE`
is therefore consistent with build G and **does not discriminate it from build
C**: under build C the same standing state (heartbeat static long enough for
`HeartbeatStaleTimer.Q`) also yields `BridgeLinkOk FALSE` and no part-4 latch.
The reading that discriminates is one taken **inside** the first
`HEARTBEAT_STALE_TIME` of a CPU run with the bridge down, and it is still owed —
see §B3.4 row 17 and §B3.5.

**Artifacts.** Two bridge sessions, one appended 1 Hz log, one observer file.

| Artifact (all gzipped, in `evidence/`) | Rate | Window it covers |
|---|---|---|
| `bridgelog-2026-07-28-rerun68.log.gz` | 1 Hz diagnostics | **19:20:58.718 – 19:31:02.312**, two bridge processes appended into one file. Session 1 ends at 19:22:35.985 (`kill -9`); session 2 begins 19:22:41.168 |
| `latency-2026-07-28-plcsim-rerun68-20260728T172058Z-pid36542.csv.gz` | **20 Hz** per-event | session 1, 37 325 event rows, first cycle `t_start_ns` `84425710159621`, span **94.959 s** |
| `latency-2026-07-28-plcsim-rerun68-20260728T172241Z-pid37442.csv.gz` | **20 Hz** per-event | session 2, 199 851 event rows, first cycle `t_start_ns` `84527737630835`, span **498.978 s** |
| `plc-observe-2026-07-28-t45-rerun.csv.gz` | **5 Hz** read-only observer, **1 196 rows / 239.994 s** | **4.5 only** — it begins at session-2 rel ≈ 144.63 s and ends at rel ≈ 384.63 s |

**LIMITATION 1 of part 2 is gone, and this run is its proof.** `--evidence-csv`
now derives a unique per-session path — the log records it at every start ("the
previous session's file is not touched") — and the two CSVs above are the two
sessions of one run, **neither truncating the other**. That is the rule §B2.12
row 21 asked for, in force and demonstrated.

**What the observer does not cover, said rather than glossed.** The 4.8 pre-check
of 19:20:5x was observed into a file the session did **not** commit (`o68_pre`).
The committed observer file starts ~144 s into session 2, so **4.8, 4.2, 4.3 and
4.9b have no observer coverage at all** — their record is the 1 Hz log and the
20 Hz CSV. It also **ends 4.478 s before 4.5's recovery reset**, so the recovery
is likewise log-and-CSV only.

**Clock discipline is part 2's, unchanged (§B2.0's fourth limitation), and the
divergence recurs.** Neither CSV carries a `run,duration_s` row to compare against
(see below), so the check here is coarser than part 2's: session 1's log spans
97.267 s against 94.959 s between its first cycle and its last row, and session
2's spans 501.144 s against 498.978 s. The endpoints are not the same instants, so
this is a ~2 s indication rather than part 2's measured 1.767 s — but it points the
same way, and it is enough to keep the same rule. **Every duration below is quoted
on the CSV's monotonic clock as seconds relative to that session's first cycle**,
and wall-clock times are quoted **only from the log**. No monotonic figure is
converted to a wall time anywhere in this section. Where the brief's transcript
timestamp and the artifact disagree, the artifact is quoted and the transcript
figure is named beside it.

Neither CSV carries a `run` summary row, and the two have **different reasons**.
Session 1's process was `kill -9`'d (§B3.1 4.9b), so nothing was flushed. Session
2's process was **still running when its CSV was archived**, and still running
long afterwards: the committed file ends mid-cycle, and the working file on disk —
excluded from the record by `bridge/.gitignore` (`evidence/*-pid*.csv`) — was
observed **still growing at 22:04 the same evening**, 2 h 41 min after that
session began, at ~39 kB/s. That working file **restarts without a header row** at
the monotonic instant the archive ends, which is what a still-appending writer
produces when the original is moved or removed underneath it; session 1, whose
process was already dead, left no such file. So the committed session-2 CSV is a
**snapshot of a live session, not the record of a finished one** — treat its span
as the window it covers, never as the session's length. Either way **no counter
block reached either committed file**, so the R1/R2/R3 received-versus-written
ratios this file usually quotes are unavailable for build G. The per-event
`R1`/`R2` rows are all present, so cycle rate could be recomputed from them — but
this section does not do so and claims no rate or statistics figure. **§B2.3 and
§B2.4 stand as the last measured set**, and the only two timing figures taken from
these CSVs are the rewrite interval (§B3.2) and the individual event timestamps
quoted per step.

## B3.1 The five re-runs, step by step, with a verdict each

### 4.8 — startup rule against the real DB start values — **PASS on its R3 half; its cold-start half did not run**

The bridge was started at 19:20:58.718 with the PLC standing at start values and
`BridgeLinkOk FALSE`, and the seven inputs were then published one at a time.

Session-1 CSV, the write of each input and the first heartbeat:

| Node | first write (session-1 rel) | gap |
|---|---|---|
| `PanelStopCircuitClosed` `True` | **7.856 s** | — |
| `PanelProcessStopCircuitClosed` `True` | **12.106 s** | +4.249 s |
| `PanelStartPressed` `False` | **16.405 s** | +4.299 s |
| `PanelResetPressed` `False` | **20.655 s** | +4.250 s |
| `BridgeHeartbeat` = **1** | **20.656 s** | **+158 µs** after the seventh write completed |

The three analogues were already real at connect: the log's connect line reads
`input image rewritten after cache invalidation: 3 of 7 nodes` and names the four
panel contacts as withheld under **R1**, and the R3 line shrank in step with the
table above — four withheld, then three, then two, then one, then
`startup rule satisfied: all 7 DemoCell/Input nodes carry a real cell sample;
heartbeat begins advancing at 1` at **19:21:19,657**. `BridgeLinkOk` first reads
`True` in the next poll, **19:21:20,563**.

**The 158 µs is the sharpest measurement of R3 this project has.** The heartbeat's
very first write followed the seventh input's write by 158 µs, in the same bridge
cycle: the bar is "all seven real", not "seven real and a wait".

**Two corrections to the brief's account of this step, from the artifacts.** The
publishes were **~4.25 s apart, not 3 s** — the CSV's write spacing is 4.249 /
4.299 / 4.250 s and the log's R3 lines are spaced to match. And the *order* is as
the brief has it: stop, process stop, start, reset.

**What did not run.** §11 4.8's first clause is "**cold-start the CPU** with the
bridge stopped", and its pass conditions are Group 4 reads at the first scan —
`HeartbeatSeenAlive` and `BridgeLinkOk` `FALSE` from the first scan, `LinkLostLatch`
and `ResetDeviceFault` `TRUE`, `CellProcessStopActive` `FALSE`. No CPU cold start
was performed in this run, and the one committed instrument that saw the pre-run
state is the bridge's own first diagnostics poll at **19:20:58,919** —
`CellProcessStopActive` **`False`**, `CellResetRequired` `True`, `BridgeLinkOk`
`False`, with the input image not yet real. **That is consistent with build G and
does not discriminate it from build C**, for the reason given in §B3.0: by
19:20:58 the heartbeat had been static long enough that both builds' verdicts read
`FALSE`. §11 4.8 is therefore **half re-run**: its R3 half is measured above, its
cold-start half is untested and stays outstanding.

### 4.2 — 30 s hands-off after link-up — **PASS on its server-visible half**

From the log: after `BridgeLinkOk` went `True` at **19:21:20,563** the diagnostics
dictionary was **byte-identical in every poll until 19:21:58,703** — 38.140 s with
`CellCycleRunning` `False`, `CellResetRequired` **`True`** (the `LinkLostLatch`
from the outage) and the command at `0.0`. The CSV bounds the hands-off
independently: **no panel input was written at all between session-1 rel 20.655 s
and rel 58.906 s — 38.251 s** — so the 30 s the step asks for is measured, not
asserted. **No auto-resume**: the cycle did not restart on a returning heartbeat,
and the first command delivered after link-up was `0.0`.

**What is missing.** 4.2's other three pass conditions are Group 4:
`HeartbeatSeenAlive` already `TRUE` from before the outage, `ResetDeviceFault`
`TRUE` throughout the outage, and `ResetDeviceFault` **clearing within one
watch-table update of link-up**. All three are internal statics (§3.2), invisible
to any OPC UA client, and **no watch-table capture covers 19:21:20**. The owner's
pre-run reading (§B3.0) gives `ResetDeviceFault TRUE` at one instant while the
bridge was down; the clearing at link-up has no committed capture. Recorded as
missing, not inferred.

### 4.3 — reset clears, and nothing moves until a separate start — **PASS, in full**

Every condition of this step is server-visible, and all of them hold.

| | log | session-1 CSV rel |
|---|---|---|
| `reset` rising edge published | — | **58.906 s** (`True`), released 61.357 s |
| latches clear | `CellResetRequired` `True → False` **19:21:58,703** | — |
| **and nothing moved** | `CellCycleRunning` stayed `False`; command `0.0` | — |
| separate `start` on the other button | — | **66.554 s** (`True`), released 69.008 s |
| cycle runs | `CellCycleRunning` `False → True` **19:22:05,996** | — |
| presence asserts | `ProductPresentAtSensor` `True` **19:22:15,294**, `False` 19:22:18,344 | — |
| clean end | `CellCycleRunning` `True → False` **19:22:26,546** | — |

Two deliberate actions on two different buttons, the reset moving nothing, and a
full clean cycle: CLAUDE.md §9's "after a safety stop the machine never resumes
automatically" read off the artifacts rather than argued.

### 4.9b — reset held from before link-up, **bridge-restart form** — **PASS. This is the reversal of F3**

The form that matters, and the reason it is the form that matters, is LESSONS
2026-07-28: the §6.8 boot-polarity fix closes 4.9b at CPU start and **relocates**
it to bridge restart, where the reset image freezes and the first attributable
`TRUE` is a genuine rising edge. Only the bridge-restart form exercises the
per-link-session re-arm. It is also §11 4.9b variant **(a)**, the variant part 2
ran and failed.

Setup and result, on the artifacts:

| | source | value |
|---|---|---|
| process stop pressed, to latch | session-1 CSV | `PanelProcessStopCircuitClosed` `False` at rel **90.356 s**, closed again rel 93.608 s |
| latch formed | log | `CellProcessStopActive` `False → True`, `CellResetRequired` `False → True`, **19:22:29,644** |
| bridge `kill -9` | log | session 1's last poll **19:22:35,985** |
| bridge restarted | log | session 2 spinning **19:22:41,168**; `BridgeLinkOk` still `False`, both latches still `True` |
| **the held reset arrives as the new session's first reset sample** | session-2 CSV | `PanelResetPressed` **`True`** written at rel **2.904 s** |
| heartbeat begins | log / CSV | **19:22:47,956**, `heartbeat begins advancing at 1`; CSV rel **6.655 s**, 118 µs after the seventh write |
| **the reset stood `TRUE` at the PLC before the link could exist** | session-2 CSV | **3.751 s** before the first heartbeat write |
| link up | log | `BridgeLinkOk` `False → True` **19:22:48,467** |
| **the latches did not clear** | log | `CellProcessStopActive` and `CellResetRequired` `True` in **every** poll from 19:22:41,310 to 19:23:15,407 — 34 consecutive polls, 27 of them after link-up |
| release alone does not clear | session-2 CSV | `PanelResetPressed` `False` at rel **30.607 s** = **+23.952 s** after the heartbeat began — latches still `True` |
| a **fresh** edge clears them | session-2 CSV | `PanelResetPressed` `True` at rel **34.857 s** = **+28.202 s** after the heartbeat began, and **+4.250 s** after the release |
| cleared | log | `CellProcessStopActive` **and** `CellResetRequired` `True → False`, **19:23:16,409** |

**So the held reset was refused for 28.202 s across a link-up, and the release
that ended it bought a further 4.250 s of refusal — because a release is not an
edge.** Set against part 2's **F3** on build C, the same step, same instruments:

| | build C (F3, `sessionC-t49b`) | **build G** (here) |
|---|---|---|
| heartbeat begins | 17:02:30,610 | 19:22:47,956 |
| `BridgeLinkOk` first `True` | 17:02:31,265 | 19:22:48,467 |
| latches at that moment | **all clear** — in the same poll | **all still set** |
| interval from heartbeat start to latches clearing | **0.655 s**, unbidden | **28.202 s**, and only on a fresh edge |

That is the pass build C could not produce, and it is a pass on a reading rather
than on an argument: the *only* thing that cleared the latches was a rising edge
that began after the link was up.

**One condition of the step is still not read.** 4.9b's pass line says "the watch
table says why: `ResetDeviceFault TRUE` beside `BridgeLinkOk TRUE`".
`ResetDeviceFault` is Group 4 and no capture covers 19:22:48–19:23:16. The
*behaviour* the guard produces is measured above; the guard's own bit is inferred
from it. The brief's transcript places `PanelResetPressed TRUE` at the PLC through
19:23:10 and the clearing edge at 19:23:16 — the CSV puts the release at rel
30.607 s and the fresh edge at rel 34.857 s, consistent with it.

### 4.5 — link loss with the CPU stopped, bridge session surviving — **PASS on its server-visible half; the corrected signature confirmed where it can be seen**

A cycle was started at **19:25:12,069** (start press at session-2 rel 149.207 s,
command read back at `+0.15` at rel 149.253 s) and ran for **32.349 s** of
transport. The owner then took the CPU to STOP and back to RUN **[transcript,
~19:25:43]**.

**1. The bridge detected the restart under a live session and repaired the image.**
Measured in §B3.2 below; the headline is that it did, in **10 ms**, rewriting
**7 of 7** input nodes, and that this closes **F5** and §B2.12 row 20.

**2. The PLC's reaction, and the corrected signature.**

| | source | value |
|---|---|---|
| cycle down, and the link-lost latch appears | log | `CellCycleRunning` `True → False` **and** `CellResetRequired` `False → True`, together, **19:25:44,065** |
| the same three transitions, at 5 Hz | observer | one sample, t = **36.9459**: command `0.15 → 0.0`, `CellCycleRunning` `True → False`, `CellResetRequired` `False → True` |
| **`CellProcessStopActive` stayed `FALSE`** | observer **and** log | **zero** `True` samples in all 1 196 observer rows; `False` in every 1 Hz poll from 19:23:16,409 to 19:31:02,312 |
| `ConveyorDriveFault` | observer and log | `False` throughout |

**This is the corrected signature, and the contrast with build C is the point.**
Part 2's **F5** recorded the same event — CPU STOP → RUN under a surviving bridge
session — producing `CellProcessStopActive` **`True`** and a process stop latched
from reverted stop contacts (§B2.12a's first and second bullets, 16:52:08.875). On
build G the same event latched **no** process stop. `CellResetRequired` still went
`TRUE`, still required a monitored reset, and still refused to auto-resume:
nothing about the required reset is weakened, and the reason the program now gives
is the true one.

**The attribution, with its arithmetic, because two changes landed together.** The
bridge's rewrite (§B3.2) removes F5's mechanism on its own, so it is fair to ask
whether the boot-polarity fix is doing any work here. It is, and the timings say
so: the CPU's first OB call follows RUN by **1.004–2.556 ms** (§B2.9's cycle-time
capture, taken on build F — the nearest measurement, standing beside the argument
rather than proving it for build G), while the bridge's repair lands **10 ms after
it detects the revert**, and detection can be up to one 50 ms bridge cycle after
RUN. So the stop contacts stood at their start values for roughly 10–60 ms of
program execution — **inside** build C's 500 ms boot window, where
`BridgeLinkOk` read `TRUE` and §7 part 4 would latch, and **outside** build G's,
where `HeartbeatSeenAlive` is still `FALSE` because no heartbeat *change* has been
seen. **That is an inference over a window no instrument sampled, and it is
recorded as one.** The direct reading remains 4.8's cold start with the bridge
down, where no rewrite can mask anything.

**Which latch set `CellResetRequired` is likewise inferred, not read.**
`CellResetRequired` is `latchPending` (§6.7). `CellProcessStopActive` and
`ConveyorDriveFault` both read `False` across the event, so the pending latch is
`LinkLostLatch` or `SensorFaultLatch`, and only `LinkLostLatch` has a cause at
that instant. No watch-table capture covers 19:25:43 — the same gap as §B2.12
row 18, one event later.

**3. Recovery: a reset that moved nothing, then a separate start.**

| | source | value |
|---|---|---|
| the cell sat latched | log | `CellResetRequired` `True`, `CellCycleRunning` `False`, command `0.0`, **19:25:44,065 → 19:29:11,709 (3 min 27.6 s)** |
| reset | session-2 CSV | `PanelResetPressed` `True` rel **389.106 s**, released rel 391.606 s |
| latch clears, **and nothing moves** | log | `CellResetRequired` `True → False` **19:29:11,709**, `CellCycleRunning` still `False` |
| separate start | session-2 CSV | `PanelStartPressed` `True` rel **395.907 s**, released rel 398.458 s |
| full clean cycle | log | `CellCycleRunning` `True` **19:29:18,909**; presence `True` **19:29:25,112**, `False` 19:29:27,210; clean end **19:29:35,462** |
| the return stroke ran | session-2 CSV | command read `−0.15` at rel 395.953 s, back to `0.0` at rel 412.404 s |

The 3 min 27.6 s of latched idle is **the owner's own gap, not a refusal**, and is
not comparable to F5's 4 min 31.1 s — there the reset was *attempted and correctly
refused* because the image was still stale. Here the image had been truthful since
10 ms after the restart, and the first reset attempted was honoured.

**What 4.5 still does not establish.** Its pass line asks for the restart
signature **off the watch table** — `HeartbeatSeenAlive` `FALSE` and `BridgeLinkOk`
`FALSE` at the first scan, `LinkLostLatch` set. `HeartbeatSeenAlive` is not on the
server at all; `BridgeLinkOk` was never sampled `FALSE` (§B3.3); no capture covers
the moment. And the step's **STOP residual** — the frozen command leaving the belt
running in Gazebo — has **no committed sample in this run**: see §B3.3.

## B3.2 The rewrite on restart, measured — F5 is fixed

The committed log carries the detection and the repair as two lines, and the
interval between them is the figure:

```
19:25:43,501 WARNING BridgeHeartbeat reads 0 but this session last wrote 3499: the server
                     restarted under a live session, so its input image is stale.
                     Invalidating the write cache (§8.1).
19:25:43,501 INFO    write cache invalidated (BridgeHeartbeat reverted to 0): every input slot
                     with a real sample is rewritten in the next cycle
19:25:43,511 INFO    input image rewritten after cache invalidation: 7 of 7 nodes
                     (ConveyorBeltPosition, ConveyorBeltSpeed, ProductSensorRange,
                      PanelStartPressed, PanelResetPressed, PanelStopCircuitClosed,
                      PanelProcessStopCircuitClosed)
```

**Detection to a repaired input image: 10 ms** — 19:25:43,501 → 19:25:43,511, at
the log's 1 ms resolution, and **7 of 7** nodes, not a subset. It is the only
`WARNING` line in the whole file, and the log carries no `session broken`, no
`connect failed` and no reconnect: **the session survived the restart**, exactly
as in F5. What changed is that surviving it is no longer the same as missing it.

**The 20 Hz CSV measures the same interval finer, and agrees.** Session-2 rows, in
file order:

| row | monotonic | rel |
|---|---|---|
| `L2,BridgeHeartbeat` = **3499** — the last write of the pre-restart image | 84709294837340 | 181.557 s |
| `read_rt,BridgeHeartbeat` = **0**, `restart-detection read-back; transports nothing` | starts 84709338274975, completes 84709340062831 | 181.601 → **181.602 s** |
| `session,server_restart_detected`, note `this session last wrote 3499; write cache invalidated` | — | — |
| seven `L2` writes, `ConveyorBeltPosition` first … `PanelProcessStopCircuitClosed` last | last completes 84709349766834 | **181.612 s** |
| `session,input_image_rewritten` = **`7/7`**, note **`written in one cycle`** | — | — |
| `L2,BridgeHeartbeat` = **3500** — the counter continues, it does not restart | 84709350446952 | 181.613 s |

* **detection read complete → last of the seven writes complete: 9.704 ms.**
* from the *start* of the detecting read: **11.492 ms**.
* the whole repair fell inside **one** bridge cycle — the containing `R1,cycle` is
  **50.789 ms** — and the CSV's own row says so: `written in one cycle`.
* its cost was **one** cycle overrun of **0.906 ms** past the deadline.

**The mechanism F5 named is what the L1 ages prove was repaired.** F5's defect was
that a bridge writing **on change** never rewrites a slot whose value has not
changed. At the rewrite, the seven `L1` intervals — time since that value's last
ROS-side sample — were:

| Node | last ROS-side change before the rewrite |
|---|---|
| `PanelStopCircuitClosed` | **177.473 s** |
| `PanelProcessStopCircuitClosed` | **176.224 s** |
| `PanelResetPressed` | **144.310 s** |
| `PanelStartPressed` | **29.894 s** |
| `ProductSensorRange` | 26.850 ms |
| `ConveyorBeltSpeed` | 3.761 ms |
| `ConveyorBeltPosition` | 2.644 ms |

The four contacts are precisely the slots F5 left stale — and the two stop
circuits, unchanged for nearly three minutes, are the two whose start values
latched a process stop in part 2. **Under the write-on-change rule alone none of
the four would have been written at all.**

**So: F5's comparable figure was 4 min 31.1 s of a stale image, ended by hand with
a force-toggle. Build G's is 10 ms, ended by the bridge.** More than four orders
of magnitude, and the difference between a manual recovery procedure and none.
`SPEC.md` §12 open item 7 — the requirement the reset guard's guarantee and §8
case C both depend on — is satisfied by behaviour; the note in that document is
`plc/`'s to make and is requested in §B3.5, not written here.

## B3.3 The observer's blind spots, stated rather than glossed

The 5 Hz observer file is continuous across the restart — **1 196 rows over
239.994 s, sample period min 0.2001 s / median 0.2008 s / max 0.2031 s, no gap and
no failed read** — and across the whole of it:

* **no heartbeat decrease.** `BridgeHeartbeat` rises monotonically 2 763 → 7 563 at
  20.0005 counts/s, with **zero** decreasing samples.
* **no `BridgeLinkOk` `FALSE` sample.** Zero, in 1 196 rows. The 1 Hz log agrees:
  `True` in every poll from 19:22:48,467 to 19:31:02,312.
* **no `CurrentSessionCount` change.** Constant at 2.

**None of that means the link did not drop, and it must not be read that way.**
The two samples that bracket the entire event are 200.7 ms apart:

| observer t | `BridgeHeartbeat` | `BridgeLinkOk` | `CellCycleRunning` | `CellResetRequired` | command |
|---|---|---|---|---|---|
| **36.7452** | 3498 | True | True | False | +0.15 |
| **36.9459** | 3502 | True | **False** | **True** | **0.0** |

Counts 3 499, 3 500 and 3 501 were never sampled — and 3 499 is the value the
bridge says it last wrote before reading 0. The revert to 0 and the repair
occupied **9.704 ms** (§B3.2) inside that 200.7 ms interval, so a 200 ms sampler
had roughly a 5 % chance of catching it and did not. **The observer's silence on
the heartbeat is a sampling artefact of a transient shorter than its period.**

The `BridgeLinkOk` silence has the same cause and a bound to go with it. On the
RUN transition the DB reinitialises, so `BridgeLinkOk` starts at `FALSE` and
`HeartbeatSeenAlive` at `FALSE`; the verdict can return `TRUE` only once a
heartbeat *change* has been seen, which is one bridge cycle after the repair
wrote 3 500. **The `FALSE` window is therefore bounded at roughly one OB call plus
one 50 ms bridge cycle — a quarter of the observer's period at most.** Neither
instrument could have sampled it.

**Why a naive reader might also expect a heartbeat *plateau* during the STOP, and
why there is none.** `BridgeHeartbeat` is written by the **bridge**, not by the
program. A halted CPU does not stop it advancing: the server accepts the writes
and the observer reads a smooth ramp for as long as the STOP lasts. The heartbeat
is blind to a CPU STOP by construction — which is the same property §7.3 case D
already records from the other direction.

**Two consequences, recorded because they are what the artifacts can and cannot
support.**

1. **The evidence that the link dropped is the PLC's own latch, not a sampled
   verdict.** `CellResetRequired` went `TRUE` in the same 200 ms sample as the
   cycle dropping, and `LinkLostLatch` can only set from `BridgeLinkOk FALSE`.
   A latch is a **level**, so a 200 ms sampler catches it; the transient that set
   it, it cannot. *The brief describes this reaction as "20 ms-resolution": there
   is no 20 ms instrument in this run.* The finest sampler of any `Status/` node
   here is the **5 Hz observer**, and the 1 Hz log is the only other one. The
   argument stands on the latch being a level, not on resolution.
2. **The STOP residual has no committed sample.** §11 4.5 asks that the frozen
   command leaving the belt running in Gazebo be recorded. It cannot be, from
   these artifacts: while the CPU is in STOP the program writes nothing, so
   `ConveyorSpeedCommand` **holds** `+0.15`, and a held value is indistinguishable
   from a live one. The command read `+0.15` in the bridge's last read before the
   event and `0.0` in the first read after it, 50 ms apart on the CSV's clock. The
   residual is real, its mechanism is §A.7's and unchanged, and **its duration is
   not measured by anything in this run** — nor, therefore, is how long the CPU
   was actually in STOP. The transcript records the action; the artifacts record
   only its effect.

## B3.4 Disposition of §B2.12's rows after this run

§B2.12 is not edited; this is where each of its rows 14–22 stands after build G.
**Nothing here is a gate ruling.**

| §B2.12 # | Now | Where |
|---|---|---|
| **14** — T4.9b re-run, two preconditions | **precondition (i) met, form (a) CLOSED, form (b) still open.** The §6.8 rebuild is downloaded and its provenance recorded (§B3.0). Variant **(a)**, fresh bridge with the reset held — the variant part 2 ran and failed — **passed on build G**, and the pass is a reading. Variant **(b)**, CPU start with `reset` already publishing, **did not run**: 4.5's restart *is* a CPU start, but no reset was held across it — no *change-driven* `PanelResetPressed` write occurs between session-2 rel 37.307 s and rel 389.106 s, and the only write of that node inside the gap is the restart rewrite of §B3.2 (rel 181.601–181.612 s), which sent `False`. The restart therefore fell inside a **released** reset. §11 4.9b is one step that must hold for **both** forms, so **the step is not yet a pass** | §B3.1 4.9b |
| **15** — T4.11's reaction path, re-recorded | **still open, and deliberately not attempted here.** T4.11 is not in §6.8's re-run list, and build G carries `BELT_SPEED_MIN`/`MAX` at ±1.00 — the CSV shows full ±0.15 strokes with no C5 intervention — so the narrowed-constant method was not in force. What *has* changed is the instrument the step nominates: the per-session CSV exists and is demonstrated (§B3.0), so the re-run is now possible without reproducing LIMITATION 1. The measurement itself is still uncorroborated by any committed file | §B2.13 F4; §B3.0 |
| **16** — T4.11b, the latch and its reset | **still open and still BLOCKED.** `SPEC.md` §12 item 6's hold-until-disarmed fault-injection facility does not exist; nothing in this run builds or approaches it. Not runnable, not a pass by default | §B2.13 F4 |
| **17** — 4.2, 4.3, 4.5 and 4.8 re-run against the corrected build | **4.3 CLOSED in full. 4.2 and 4.5 closed on their server-visible halves; their Group 4 halves are not read. 4.8 half re-run** — its R3 half is measured, its **cold start did not happen**. The one reading that would discriminate build G's boot polarity from build C's — `ProcessStopLatch`/`BridgeLinkOk` inside the first `HEARTBEAT_STALE_TIME` of a CPU run with the bridge **down** — is still owed, and §B2.12a's "cheapest available before/after test" is therefore still not performed | §B3.1, §B3.0 |
| **18** — Group 4 `PositionFrozen`/`PositionRef` for T4.6 and T4.6b | **unchanged.** No case-D step was re-run and no watch table was captured in this run. The same gap recurs one event later: no capture covers 19:25:43 either, so which latch set `CellResetRequired` at 4.5 is inferred, not read | §B3.1 4.5 |
| **19** — case C as a link break with the CPU running | **unchanged.** STOP → RUN was performed a third time; the adapter was again never stopped under a running program | — |
| **20** — a bridge that repairs the input image after a server restart | **CLOSED.** The facility exists and is measured: restart detected under a surviving session, **7 of 7** nodes rewritten, **10 ms** from the log's own two timestamps, **9.704 ms** on the CSV's clock, inside one 50.789 ms cycle, on slots whose last ROS-side change was up to **177.473 s** earlier. F5 is fixed. `SPEC.md` §12 item 7 is satisfied by behaviour; the note in that document is requested, not written | **§B3.2** |
| **21** — the 17:14:07 – 17:49:06 hole, and the one-CSV-per-session rule | **the rule is CLOSED; the hole is permanent.** Two uniquely named CSVs, one per session, neither truncating the other, and the log names the path at every start. Part 2's hole is a fact about a past run and nothing here changes it | §B3.0 |
| **22** — why `PresenceOnTimer.PT` reads `T#0MS` after a CPU restart | **not advanced, and one coarse datum added.** A **full clean cycle ran after the CPU restart** — presence asserted 19:29:25,112, released 19:29:27,210, clean end 19:29:35,462 — so the presence verdict works post-restart. That is the same class of argument F6 already makes for itself and is **not** a resolution: at 1 Hz (the observer had stopped) nothing here can measure a 100 ms filter, and `PresenceOnTimer.PT` is Group 4. Still one watch-table row at the next download | §B2.13 F6 |

## B3.5 What part 3 does not establish, and what it requests elsewhere

**Not established, in one list.** A CPU **cold start** with the bridge down, which
is 4.8's other half and the only direct test of the boot polarity; **4.9b variant
(b)**; any **Group 4** value whatsoever — no watch-table capture was taken in this
run, so `HeartbeatSeenAlive`, `ResetDeviceFault`, `LinkLostLatch`,
`ProcessStopLatch`, `SeqStep`, `PositionRef`, `PositionFrozen` and every timer `ET`
are unread and appear above only as inferences that are labelled as such; the
duration of the CPU's STOP and hence the **STOP residual**; an **adapter** break
under a running program; **T4.11**'s reaction re-record; and **T4.11b**, which has
no facility to run on. Cycle-rate and R3 statistics for build G are absent because
neither process was shut down cleanly.

**Requested outside `bridge/`, not written here.**

1. **`docs/interfaces/bridge-design.md`** — §8.1's *Detection* row defines a broken
   session as "a failed read or write, or a session/keep-alive failure". A server
   that **restarts under a surviving session** produces none of those, and §7.3
   case C assumes the session breaks. The implemented behaviour — detect
   `BridgeHeartbeat` reverting below what this session last wrote, invalidate the
   write cache, rewrite every slot with a real sample — is in the code and now in
   this evidence, and the design document does not carry it. It needs a row, and
   the bridge's own log cites "§8.1" for a rule that is not yet there.

   > **SATISFIED, 2026-07-29** (`bridge-design.md` revised by m4f-05, and that
   > document's §12 item 13 records the resolution). §8.1 now carries *Restart
   > detection*, *Restart repair* and *Restart residual*; §7.3 gains **case E**;
   > §2's cycle description gains **step 0**; §4.3 gains row **9r**; and §9.2
   > gains **RB**. The log line's "§8.1" citation resolves to a rule that exists,
   > and the test the design words as an exact inequality is what the code does —
   > "not lower than", because the counter wraps. Marked here by `bridge/`, which
   > owns this file (m4f-06).
   >
   > **One correction is requested back**, from the m4f-06 run: §8.1's *Restart
   > residual* row states only the one-value-in-65536 case, and the residual is
   > materially larger. A revert that lands between the cycle's step-0 read-back
   > and its own step-4 heartbeat write is erased by that write — measured at
   > **5.255 ms median of a 50.015 ms cycle, ~10 %** — and it was observed
   > leaving an open stop circuit and an obstacle bit standing for **4.0 s** under
   > an advancing heartbeat. Evidence and the request:
   > `EVIDENCE_CONNECT.md` § m4f-06.4 and
   > `docs/reports/m4f-06-bridge-forklift-slots.md`.
2. **`plc/demo-cell/SPEC.md`** — §12 open item 7 is satisfied by behaviour (§B3.2)
   and should record it; §6.7's guarantee, which is conditional on a truthful
   input image, can now name the mechanism that makes it so. §11 4.9b's as-run
   status is variant (a) passed, variant (b) outstanding. `plc/`'s to write.
3. **Build letters** — the `m3-36` brief's "build E" is this section's **build G**,
   because §B2.9 already spends E and F. Any tracking file that adopted the
   brief's letter should be corrected to G.
4. **A watch-table capture at the next CPU cold start with the bridge down.** It is
   one capture, it is the only direct test of the §6.8 boot polarity, and it is the
   single highest-value reading still missing from this file.

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
