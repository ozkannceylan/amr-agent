# EVIDENCE_LATENCY.md — measured bridge performance

Date of run: **2026-07-27** (08:49:14 – 08:52:34 UTC)
Host: Linux 6.18.5 x86_64, container, CPU only, no display
ROS 2 Jazzy, Gazebo Sim 8.11.0 (Harmonic), Python 3.12.3, `asyncua` 2.0.1
Raw per-event rows: **`evidence/latency-2026-07-27.csv.gz`** (76 191 rows)

This file has three clearly separated sections. **Section A** is the
in-container run against the test double, produced by m3-04. **Section B** is
the run against **PLCSIM Advanced with the standard program in RUN**, on which
the M3 gate closes (`bridge-design.md` §9.4); it was executed on 2026-07-27
under brief `m3-26` and now carries measurements. **Section C** is a short WSL
run added by m3-13.

Each section stays qualified by the environment that produced it and none is
re-run or edited by a later one (LESSONS 2026-07-27).

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

# Section B — PLCSIM Advanced, live run with the program in RUN

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
| **D** — simulation killed, bridge alive | `kill -9` the gz server at t≈363 s | heartbeat **kept advancing** (767 → 1251), `BridgeLinkOk` stayed **True**, input image froze bit-identically — and **`ConveyorDriveFault` never latched** for 26 s | **FAILED — see §B.13 F2** |

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
running, and changed nothing.

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

## B.13 Findings that belong to the PLC program

Both were found by running the specification, are recorded exactly as observed,
and **nothing was changed to work around either**. Neither is a bridge defect:
the bridge carried the correct values in both cases, which is how they became
visible.

### F1 — the presence verdict never asserted, so no cycle ever reached its dwell

The photo-eye works and the bridge carries it faithfully. During the first
transport, the PLC's own `ProductSensorRange` node went **1.4401 → 0.5400 m at
t=47.10 s and stayed there until t=48.92 s** — 1.8 s, against a
`PRESENCE_FILTER` of 100 ms — and `0.540` is precisely the "product in the beam"
value `SPEC.md` §9 predicts. `RANGE_MIN`/`RANGE_MAX` are 0.05/3.00, so
`RangeValid` was true throughout.

**`ProductPresentAtSensor` stayed `False` for the entire 394 s run** — it never
once changed state. Consequently `SeqStep` never advanced 10 → 20, there was no
dwell, no reversal at the beam, and the transport step instead ran on to the
soft limit: at **t=54.96 s, position 2.4123 m ≥ `SOFT_LIMIT` 2.40**, the step
aborted, `SequenceFaultLatch` set, `CellCycleRunning → False`,
`ConveyorSpeedCommand → 0.0` and `CellResetRequired → True`. The same thing
happened on every subsequent transport.

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
signature appeared exactly as §8 predicts: heartbeat **kept advancing** (767 →
1251), `BridgeLinkOk` stayed **True**, and the input image froze bit-identically
at `position = 0.9273`, `speed = 0.1500`. From the PLC's side the link looked
perfect.

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
  slides. By the time of the freeze the belt had travelled from 0.3093 to
  0.9273, so `ABS(position − PositionRef)` was ≈ **0.62 m** against a
  `POSITION_FREEZE_BAND` of **0.005 m**, and stayed there. D2's comparison can
  only be satisfied if the freeze happens within roughly the first 33 ms of a
  motion.

**Net effect: a simulation frozen at any non-zero speed after the first fraction
of a second of travel is undetectable by either term.** The honest limit
`SPEC.md` §6.6 already states for the *idle* sub-case turns out to extend to the
moving case as well. Fixing it is a change to `plc/demo-cell/SPEC.md` §6.6/§7 —
a re-arming window, not a bridge change — and belongs to the `plc` agent, not
here.

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
