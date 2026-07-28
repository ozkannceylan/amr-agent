# EVIDENCE_SIGNAL_LOSS.md — the four failure modes of bridge-design.md §7.3

Date of runs: **2026-07-27** (08:54:29 – 08:59:23 UTC)
Host: Linux 6.18.5 x86_64, container, CPU only
Server: **`bridge/test_double/plc_test_double.py`** on
`opc.tcp://127.0.0.1:4840/amr-agent/celldouble/` — a Python OPC UA server, **not
a PLC**. It has no program, so nothing here says what the *equipment* does; it
says what the **input image and the session** look like. The reaction is PLC
content (`plc/demo-cell/SPEC.md`).

"What the server observes" below is the double's own 5 Hz observation log
(`--observe-csv`): wall clock, monotonic seconds, **active OPC UA sessions**,
`BridgeHeartbeat`, the six `DemoCell/Input/` values, `ConveyorSpeedCommand`.

**Scope.** These runs predate the panel reset, so the input image they observe
is six nodes. It has been seven since `DemoCell/Input/PanelResetPressed`
(m3-10/m3-11, bridged in m3-13); every "six" below is a true statement about
*these* runs, and each of the four failure modes applies to the seventh node
identically — it is a contact like the other three, written on change, frozen
at its last written value on a loss, and never defaulted. The four cases were
**not** re-run for it, and m3-08 (or the owner's PLCSIM run) captures them
against the seven-node image.

---

> **The PLCSIM repeat has been performed twice, and now has its own section in
> this file — see "The PLCSIM Advanced repeat" below.** Brief `m3-26`
> (2026-07-27) ran cases **A**, **B** and **D** against the live CPU with the
> standard program in RUN, on the seven-node input image. Headline results, so
> this file is not silently stale: A and B were **indistinguishable to the
> program**, with `BridgeLinkOk → False` **0.50 s** after the last heartbeat
> change in both; case **D was NOT detected** — the frozen read-back held a
> **non-zero** `ConveyorBeltSpeed`, which blinds term D1, and term D2 could not
> fire either (`EVIDENCE_LATENCY.md` §B.13 F2). Case **C was not performed**: it
> requires stopping the CPU. The session-hold figure of "What none of this
> establishes" is now measured: **11.79 s** after SIGKILL, **0.0 s** after
> SIGTERM (§B.8).
>
> The 2026-07-28 owner session then ran **all four cases** against a rebuilt
> program, including case C and a case D **mid-motion** that the program caught in
> **2.301 s**. Both runs are summarised below with the day and the build that
> produced each figure; the full accounting stays in `EVIDENCE_LATENCY.md`
> Section B, part 1 and part 2.
>
> A third session the same evening, **19:15–19:31**, re-ran the five `SPEC.md` §11
> steps that cross a CPU start or a link-up against the **§6.8 rebuild**. Two
> results belong to this file: case **C** with the session surviving now ends in a
> **repaired** input image — **10 ms**, 7 of 7 nodes — instead of a stale one held
> for four and a half minutes, and the same restart no longer latches a process
> stop from reverted contacts. See **"The same case on the §6.8 rebuild"** under
> case C below, and `EVIDENCE_LATENCY.md` **Section B, part 3**.
>
> Nothing below is re-run or edited by that work; each record stays qualified by
> the environment that produced it.

## Target environment for the PLCSIM re-run — commissioning phase 0, owner-verified in tool 2026-07-27

The four cases below were run **in the container, against the test double**, and
are unchanged. The PLCSIM repeat they called for — "What none of this
establishes", below, and `EVIDENCE_LATENCY.md` Section B item 6 — ran against
the stack recorded here, which phase 0 of commissioning brought up on the
owner's engineering workstation.

**What phase 0 proves: the endpoint and the node exposure, and nothing else.**
No PLC program logic ran, and the bridge was not involved — so phase 0 says
nothing about any of the four failure modes below, and nothing about the
*reaction* to them, which is `plc/demo-cell/SPEC.md` content.

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
| Session timeout | requested **3 600 000 ms**, granted **30 000 ms** — the server **revises** the request; a revision downwards in this instance, and the grant for the bridge's own request may land either side of it (`EVIDENCE_LATENCY.md` §B.0.3) |

Independent verification the same day: **15 `DemoCell` nodes read with an
`asyncua` client from Windows, all at their start values, with the bridge not
involved.** That is the full node set of `opcua-nodes.md` §9 as it now stands —
the seven-node input image included — against the 14 nodes these container runs
log, which predate `Input/PanelResetPressed`.

Two facts of this environment bear directly on the cases below, and both are
questions for the re-run rather than answers from it:

- **Case A's session timing is the one result known not to transfer.** The
  double dropped the session within ~2 s of a `SIGKILL` (§A.4). This server
  **revises** the session timeout rather than capping it — it granted 30 000 ms
  for a 3 600 000 ms request, so the grant for the bridge's 10 000 ms request
  may land either side of that request and is not known until the run reads it
  back. How long the S7-1500 holds a session after a bridge kill is bounded by
  the **granted** value, is a property of *this* stack, and must be measured on
  it (`EVIDENCE_LATENCY.md` Section B item 7, and §B.0.3 for the direction).
- **Case C's "server restarted with start values" now has real start values.**
  In phase 0 every node read its DB start value because nothing had run; against
  a *running* program the same reconnect is a different event, and `Status/`
  nodes will carry program-formed values rather than the constant `False` of
  these runs.

One precondition, recorded so the re-run is not attempted too early: on this
server the interface sits under `ServerInterfaces` in a *second* namespace, which
the client must resolve by URI before any of the four cases can be provoked
against it (`opcua-nodes.md` §2.1; see `EVIDENCE_LATENCY.md` §B.0.3). **Met by
m3-21**: the client resolves both namespaces by URI at every session
establishment, and the recorded test-double run is `EVIDENCE_CONNECT.md`. Case
A's re-run should also record the **granted** session timeout, because that is
the bound on how long the server may hold a session whose client vanished
without a FIN/RST (`bridge-design.md` §3.2 S5).

Nothing in the four cases is re-run, re-measured or edited here: each remains
qualified by the environment that produced it.

---

Summary of §7.3 as measured:

| # | Failure | Heartbeat | Input nodes | Session | Matches the design? |
|---|---|---|---|---|---|
| A | bridge crash (`kill -9`) | stops at an arbitrary value | frozen at last written | dropped within ~2 s | yes, except the session drops **immediately** here — see A.4 |
| B | clean shutdown (SIGTERM) | stops at an arbitrary value | frozen at last written | closed cleanly, immediately | yes |
| C | OPC UA connection loss (double stopped) | stops | frozen, then **lost entirely** when the server restarted with start values | broken; bridge reconnects | yes |
| D | sim stopped, bridge alive | **keeps advancing** | frozen at the last real sample | healthy | yes — the input image looks live |

**A and B are indistinguishable in the input image**, and in this container they
are nearly indistinguishable in the session state too. A program that behaves
differently for A and B is wrong (§7.3).

---

# The container run — test double, 2026-07-27 (m3-04)

## A — bridge crash (SIGKILL)

Belt running at 0.05 m/s under a `ConveyorSpeedCommand` of 0.05, heartbeat
advancing, then `kill -9`.

```
08:57:24.629  sessions 1  hb 374  BeltPos 0.3894999921  BeltSpeed 0.05000000074  Range 1.440088  F T T  cmd 0.05
08:57:24.712  kill -9 <bridge pid>
08:57:26.643  sessions 0  hb 376  BeltPos 0.3945000171  BeltSpeed 0.05000000074  Range 1.440088  F T T  cmd 0.05
08:57:36.708  sessions 0  hb 376  BeltPos 0.3945000171  BeltSpeed 0.05000000074  Range 1.440088  F T T  cmd 0.05
08:58:00.063  sessions 0  hb 376  BeltPos 0.3945000171  BeltSpeed 0.05000000074  Range 1.440088  F T T  cmd 0.05
08:58:30.092  sessions 0  hb 376  BeltPos 0.3945000171  BeltSpeed 0.05000000074  Range 1.440088  F T T  cmd 0.05
```

**A.1 The heartbeat stops at an arbitrary value** (376) and never moves again.
This is the only reliable indicator, and it is what the PLC program must
supervise (§7.1: test `BridgeHeartbeat <> LastBridgeHeartbeat`, never subtract).

**A.2 The input image freezes at the last written values and stays plausible.**
`ConveyorBeltSpeed` is frozen at **0.05 m/s** — the PLC's input image says the
belt is moving, forever. Nothing in the bridge writes a farewell value or a
zero, by design (§1.1: "a bridge that stops equipment is a controller").

**A.3 The belt kept running.** 12 s after the crash, with no bridge in
existence:

```
$ ros2 topic echo /cell/conveyor/joint_state --once
name: [belt_joint]  position: [1.155300016954519]  velocity: [0.05000000074505806]
```

The belt travelled 0.39 m → 1.16 m with no supervision, because gz's
`JointController` holds the last velocity it was given and **no command can
reach the cell while the bridge is down** (§8.4). This is a property of the
demonstration cell, not of the bridge; on real equipment the drive is dropped by
a wired enable/contactor. No safety function is involved and none is claimed
(invariant 1).

**A.4 Deviation from the design's expectation, reported.** §7.3 A predicts the
server "still holds the session until the session/subscription timeout". Here
the double saw `sessions 1 → 0` within **2 s**: `SIGKILL` closes the TCP socket
at OS level on a live host, so the server sees the connection drop at once. The
design's wording holds for a host or network loss (no FIN/RST), not for a
process death on a live host. The consequence strengthens the design's own
conclusion: **session state is not a faster or more reliable indicator than the
heartbeat**, and A and B remain indistinguishable in the input image.

**A.5 Restart.** A fresh bridge process re-ran the startup rule and began a new
heartbeat at 1 (the counter is per process; §7.1/§8.1 require the PLC to treat
any *change* as liveness, never arithmetic, so the discontinuity is harmless):

```
08:58:30,960 heartbeat withheld: no real sample yet for ProductSensorRange, PanelStartPressed,
             PanelStopCircuitClosed, PanelProcessStopCircuitClosed (startup rule R3)
08:58:32,711 startup rule satisfied: all six DemoCell/Input nodes carry a real cell sample;
             heartbeat begins advancing at 1
```

---

## B — clean shutdown (SIGTERM)

```
08:55:38.441 bridge: signal 15: stopping; no farewell value, nothing zeroed
08:55:38.489 bridge: session closed (clean shutdown); no farewell value written, nothing zeroed
08:55:38.499 bridge: stopped after 53.0s

server side:
08:55:46.027  sessions 0  hb 524  BeltPos 2.5  BeltSpeed -8.07e-29  Range 1.440088  F T T  cmd 0.0
08:55:46.228  sessions 0  hb 524  BeltPos 2.5  BeltSpeed -8.07e-29  Range 1.440088  F T T  cmd 0.0
08:55:46.429  sessions 0  hb 524  BeltPos 2.5  BeltSpeed -8.07e-29  Range 1.440088  F T T  cmd 0.0
```

The heartbeat stops at 524. The six input values stay exactly as last written.
**Nothing is written on the way out**: no zero, no "safe" value, no farewell.
The session closes cleanly and immediately.

**Difference from A, as seen by the PLC: none in the input image.** The only
difference is *how* the session disappears (an orderly close vs a dropped
socket), and in this container even that difference is ~2 s. §7.3's rule stands:
a program that behaves differently for A and B is wrong.

---

## C — OPC UA connection loss, bridge alive (test double stopped)

Belt running at 0.15 m/s, heartbeat advancing, then the double is killed.

```
08:55:04.633  sessions 1  hb 289  BeltPos 0.8619000315  BeltSpeed 0.15000000596  Range 1.440088  F T T  cmd 0.15
08:55:04.791  kill -9 <test double>
```

**C.1 The bridge detects it on the first failed service call, in the same
cycle, and enters reconnect:**

```
08:55:04,824 WARNING session broken: read ConveyorSpeedCommand: client is disconnected
             — degraded mode, no signal invented
08:55:04,825 INFO    session closed (session broken); no farewell value written, nothing zeroed
08:55:05,827 WARNING connect failed: [Errno 111] Connect call failed ('127.0.0.1', 4840); retrying in 2.0s
08:55:07,830 WARNING connect failed: [Errno 111] Connect call failed ('127.0.0.1', 4840); retrying in 4.0s
08:55:11,831 WARNING connect failed: [Errno 111] Connect call failed ('127.0.0.1', 4840); retrying in 5.0s
```

Retry is a fixed interval with bounded backoff (1 → 2 → 4 → 5 s cap), forever.
It is housekeeping: it never delays or suppresses a value that could be sent.
The bridge process stayed alive throughout (`ps` confirmed).

**C.2 Nothing was published on `/cell/conveyor/cmd_speed` during the outage
(N3).** `ros2 topic hz /cell/conveyor/cmd_speed` for 6 s during the outage
produced **no output at all** — not the last value, not zero, not anything.

**C.3 The belt kept running (§8.4 residual).** During the 21 s outage the belt
travelled from 0.86 m to its **+2.50 m mechanical stop** at the last commanded
0.15 m/s; a `joint_state` sample taken 12 s into the outage read
`position 2.5, velocity ≈ 0` — the belt had run out of travel, not been
stopped. (Repeated at 0.05 m/s in case A.3, where the belt is visibly still
moving mid-travel.)

**C.4 On reconnect: fresh namespace and NodeId resolution, all six inputs
refreshed, then the heartbeat resumes.** The double was restarted, i.e. the
server came back with its **start values** — the §7.3 C case "lost entirely if
the server restarted with DB start values":

```
08:55:26.718  sessions 0  hb 0    BeltPos 0.0  BeltSpeed 0.0  Range 0.0       F F F  cmd 0.0   <- start values
08:55:26.919  sessions 1  hb 293  BeltPos 2.5  BeltSpeed ~0   Range 1.440088  F T T  cmd 0.0   <- +200 ms
```

Within one observation interval of the new session, all six inputs carry real
cell values again and the heartbeat continues at **293** — it was **not reset**
by the reconnect (§8.1). Bridge log: `session established, 14 nodes resolved`
(re-resolved, never reused across sessions).

**C.5 No auto-resume (N4).** The restarted double commands `0.0`, and the first
value the bridge published after reconnect was that `0.0` — the belt does not
resume because the bridge remembers nothing; it does what the server is
commanding **now**. The bridge holds no saved command state and has no notion of
"resume".

---

## D — simulation stopped, bridge alive

The Gazebo server was killed while the bridge and the double kept running,
with `ConveyorSpeedCommand` at 0.05.

```
08:58:46.156  kill -9 <gz sim>
08:58:48.990  sessions 1  hb 326  BeltPos 2.5  BeltSpeed 3.2247698766e-28  Range 1.440088  F T T  cmd 0.05
08:59:04.061  sessions 1  hb 628  BeltPos 2.5  BeltSpeed 3.2247698766e-28  Range 1.440088  F T T  cmd 0.05
08:59:19.144  sessions 1  hb 929  BeltPos 2.5  BeltSpeed 3.2247698766e-28  Range 1.440088  F T T  cmd 0.05
```

**The heartbeat keeps advancing** (326 → 628 → 929, exactly 20 Hz) because the
bridge is alive and writing. **The input image is frozen at the last real
sample**, bit-identical for 30 s, because the slots are never cleared and the
cyclic write repeats the last value. The session stays healthy and the bridge
logs no error: from the PLC's side there is **no difference at all — the input
image looks live**.

This is the honest limitation the design records (§7.3 D): the heartbeat proves
the *bridge* is alive, and says nothing about the *cell*. The bridge cannot
detect it without adding a timer that gates a signal, which is control
(§1.1). Three fixes were considered and rejected in the design; none is
implemented here.

What the PLC *can* see in this exact capture is the drive-fault condition it
already owns: **a live heartbeat, a non-zero `ConveyorSpeedCommand` (0.05) and a
`ConveyorBeltSpeed` of ~0 that never changes**. That is
`DemoCell/Status/ConveyorDriveFault` (§9.5), and its tolerance and delay are
PLC program content. Recommendation carried to `plc/demo-cell/SPEC.md` (m3-05).

---

# The PLCSIM Advanced repeat — the same four cases against a CPU running a program

**This section is `EVIDENCE_LATENCY.md` Section B item 6, delivered here as
`plc/demo-cell/SPEC.md` §11 T4 requires: beside the container run, not instead of
it.** The four cases above stay exactly as recorded against the test double; what
follows is what the same four failures do when a **program** is on the other side.

Two runs contribute, and every figure below names which:

| | Date | Brief | Program build | Instruments |
|---|---|---|---|---|
| **run 1** | 2026-07-27 | `m3-26` | m3-05 | 20 Hz bridge CSV + a 10 Hz read-only OPC UA observer |
| **run 2** | 2026-07-28 | `m3-33` (owner session) | rebuilt — three deltas, then the `PRESENCE_FILTER` fix; the case-D re-measure was taken after a further re-download (`EVIDENCE_LATENCY.md` §B2.9) | 20 Hz bridge CSV for the last 12 min, 1 Hz bridge diagnostics logs, a 5 Hz read-only observer |

Run 2's 20 Hz CSV covers **17:49–18:01 only** — the bridge truncates its evidence
CSV at every start and the path was reused across seven restarts, so earlier
windows survive only as 1 Hz diagnostics. Figures that exist only in the
orchestrator's session transcript are marked **[transcript]** with their
timestamp. Neither run could see `plc/demo-cell/SPEC.md` §9 Group 4 — `SeqStep`,
`PositionRef`, `PositionFrozen`, `ResetDeviceFault` and the timer `ET`s are not on
the server, and exist only in the owner's watch-table captures.

## A — bridge crash (SIGKILL), against the program

| | run 1 (m3-05 build) | run 2 (rebuilt) |
|---|---|---|
| heartbeat | froze at **4537** | froze at **11873** |
| `BridgeLinkOk → False` | **0.50 s** after the freeze | **0.60 s** after the last heartbeat change (bracket 0.40–0.80 s at 0.2 s sampling) |
| in the same sample | `CellResetRequired → True`; command already `0.0` | `CellCycleRunning → False`, `CellResetRequired → True`, command `0.0` — all four together |
| session | held **11.79 s** | still counted **20.10 s** after the last heartbeat change |

**The heartbeat is the only indicator, and it is enough.** `HEARTBEAT_STALE_TIME`
= 500 ms is confirmed by both runs and needs no revision. The reaction is the
program's: drop the cycle, command `0.0`, latch `CellResetRequired`, and require a
monitored reset. **The belt keeps running in Gazebo** until the bridge returns —
§A.3's residual, unchanged, and stated again because a PLC on the other side does
not remove it: no command can reach the cell while the bridge is down.

**No auto-resume, and it was tested three times in run 1 and again in run 2.**
After the link came back the cycle stayed down until a *separate* start press on
the other button: in run 2 the restarted bridge's heartbeat first appears at
observer t = 41.789 — at **3**, because the counter is per process, which is why
the program must test for *change* and never subtract (§A.1, §A.5) — and
**nothing moved for the next 36.97 s**, with the command at `0.0`, until a reset
at t = 78.7596 and a start at t = 85.5945.

## B — clean shutdown (SIGTERM), against the program

Run 2, `SIGTERM` logged 15:14:04.723: heartbeat froze at **1377**, and the
identical four-way transition followed **0.60 s** later — the same figure, the
same set of bits, in the same order as case A.

**The only measurable difference between A and B is at the session layer**, where
the program cannot see it and should not: run 2's SIGTERM session was gone in the
**next 0.2 s sample**, against 20.10 s for the SIGKILL. §7.3's rule holds against
a real program on a real CPU: *a program that behaves differently for A and B is
wrong*, and neither run found one that does.

## C — link loss with the CPU itself stopped, bridge session surviving

**Not performed in run 1** (it requires stopping the owner's CPU). **Performed in
run 2**, in the form that matters most and is not in the container set: the owner
put the CPU to **STOP and back to RUN at ~16:51:30 [transcript]** while a live
bridge session was held.

What happened is the container case C with the roles reversed — here it is the
*server* that came back with start values while the *client* never noticed:

* **the restart reverted every input to its start value.** The program then did
  exactly what its rules say: the stop circuits read open, so
  `CellProcessStopActive` and `CellResetRequired` latched, the command stayed
  `0.0` and nothing ran;
* **the latches held for 4 min 31.1 s** (1 Hz log, 16:52:08.875 → 16:56:40.008)
  and the monitored reset was **correctly refused** throughout, because the cause
  had not gone. The owner cleared it by force-toggling the panel levels
  **[transcript, ~17:05]**, after which the reset behaved normally;
* **the bridge never noticed.** The same log carries **no `session broken`, no
  `connect failed`, no reconnect and no read or write error** for the whole
  1 h 43 m of that process. The session survived the STOP → RUN, so nothing was
  re-established — and because the bridge writes **on change** (§5), the slots
  whose values had not changed were never rewritten.

**That last point is a bridge defect, and it is recorded as one.** §C.1 above
shows the bridge detecting a *lost* server on the first failed service call; a
server that **restarts under a surviving session** produces no failed call at all,
and the write-on-change rule then leaves the PLC reading a stale image
indefinitely. The fix is not a timer and not a threshold — it is *detect the
restart and rewrite every slot* (`plc/demo-cell/SPEC.md` §12 open item 7,
LESSONS 2026-07-28). Until it lands, force-republish every level after any CPU
restart. Full record: `EVIDENCE_LATENCY.md` §B2.13 F5.

> **That fix has since landed and been measured**, later the same evening against
> the §6.8 rebuild — **10 ms** from detection to a repaired image, 7 of 7 nodes.
> The record above is not amended: it stays a true statement about the build and
> the bridge of 16:51. See **"The same case on the §6.8 rebuild"** below, and
> `EVIDENCE_LATENCY.md` §B3.2.

**One residual, recorded because it is a real limit and not a defect:** while the
CPU was in STOP the server held its last command, `+0.15`, and the belt kept
running in Gazebo **[transcript]** — §A.3 again. No safety function is involved
and none is claimed (invariants 1 and 2).

### The same case with the bridge **stopped** — and the only watch-table record of a restart

A second CPU STOP → RUN was performed at 17:16:56 – 17:17:27 with the bridge down
since 17:14:07, and the owner captured the §9 Group 4 watch table before, during
and after it (`plc/demo-cell/evidence/watch-table/Screenshot 2026-07-28 171656.png`,
`171712.png`, `171727.png`). It is the only committed record of a restart from
inside the CPU, and it shows the container case C's "lost entirely when the server
restarts with DB start values" as a reading rather than an inference:

| Tag | before (RUN) | during (STOP) | after (RUN) |
|---|---|---|---|
| `"DemoCellInput".ProductSensorRange` | **1.440088** | 1.440088 | **0.0** |
| `ProcessStopLatch` | **FALSE** | FALSE | **TRUE** |
| `SensorFaultLatch` | **FALSE** | FALSE | **TRUE** |
| `LinkLostLatch` / `"DemoCellLink".BridgeLinkOk` | TRUE / FALSE | TRUE / FALSE | TRUE / FALSE |

The 1.440088 standing on the left is **case A's frozen input image**, two and a
half minutes after the bridge stopped and still plausible — §A.2's "the PLC's input
image says the beam is clear, forever" seen from the PLC side. The 0.0 on the right
is the DB's own start value, and because it is below `RANGE_MIN` it is rejected as
implausible rather than believed, which is the affirmative-window rule doing its
job. The full reading, including what the latch transition says about the program's
boot window, is `EVIDENCE_LATENCY.md` §B2.7c.

**Neither sub-case is a safety event** (invariant 2): both end with the cell
stopped, latched and requiring a monitored reset.

### The same case on the §6.8 rebuild — the bridge now repairs the image, and the PLC no longer accuses the panel

A **third** CPU STOP → RUN was performed at **~19:25:43 [transcript]** in the
re-run of 2026-07-28 19:15–19:31, again with a live bridge session, this time
against the §6.8 rebuild (**build G**; `EVIDENCE_LATENCY.md` §B3.0 explains why it
is not called E) and against a bridge that now carries a restart-detection path.
That path cites `bridge-design.md` §8.1 in its own log line, but **§8.1 does not
yet describe it** — its *Detection* row defines a broken session as a failed read,
write or keep-alive, and a server that restarts under a surviving session produces
none of those. The row is requested in `EVIDENCE_LATENCY.md` §B3.5 and is
`docs/interfaces/`' to write. Artifacts:
`bridgelog-2026-07-28-rerun68.log.gz`,
`latency-2026-07-28-plcsim-rerun68-20260728T172241Z-pid37442.csv.gz`,
`plc-observe-2026-07-28-t45-rerun.csv.gz`. Full accounting:
`EVIDENCE_LATENCY.md` **Section B, part 3**.

**What the bridge did, which is the whole difference.** The session survived the
restart exactly as before — no `session broken`, no `connect failed`, no
reconnect — but the bridge now notices for a different reason: it compares the
heartbeat it reads against the value **this session** last wrote.

```
19:25:43,501 WARNING BridgeHeartbeat reads 0 but this session last wrote 3499: the server
                     restarted under a live session, so its input image is stale.
                     Invalidating the write cache (§8.1).
19:25:43,511 INFO    input image rewritten after cache invalidation: 7 of 7 nodes
```

* **10 ms** from detection to a repaired image, on the log's own two timestamps;
  **9.704 ms** on the CSV's monotonic clock, inside **one** 50.789 ms bridge cycle,
  which the CSV states in its own row: `input_image_rewritten 7/7`,
  `written in one cycle`.
* **7 of 7**, not a subset — and the four that mattered are the ones write-on-change
  could never have sent: at the moment of the rewrite, `PanelStopCircuitClosed` had
  not changed on the ROS side for **177.473 s** and
  `PanelProcessStopCircuitClosed` for **176.224 s**. Those are the two whose start
  values latched a process stop in §C above.
* the heartbeat **continued** at 3500 rather than restarting, per §8.1's continuity
  rule; the PLC needs only *change*, so this is harmless either way.

**What the PLC did, and the signature that changed with it.** The cycle dropped and
the link-lost latch appeared together — `CellCycleRunning True → False` and
`CellResetRequired False → True` in the same 1 Hz poll at **19:25:44,065**, and in
the same 200 ms observer sample as the command going `0.15 → 0.0` — while
**`CellProcessStopActive` stayed `FALSE`**: zero `True` samples in all 1 196
observer rows and `False` in every 1 Hz poll of the session. Against §C above,
where the same failure produced a latched process stop held for 4 min 31.1 s, this
is the corrected signature of `SPEC.md` §6.1: the panel is no longer accused of a
stop that was never seen. Nothing is weakened — `CellResetRequired` still latched,
the command still went to `0.0`, and recovery still took a reset that **moved
nothing** (19:29:11,709) followed by a **separate** start press (19:29:18,909 →
clean end 19:29:35,462).

**Two things this sub-case does not show, said here rather than left to be
assumed.**

* **The `BridgeLinkOk FALSE` window was never sampled**, by either client. The 5 Hz
  observer is continuous across the event with no gap and no failed read, and it
  recorded **no** heartbeat decrease and **no** `BridgeLinkOk FALSE` sample —
  because the revert-and-repair transient is 9.704 ms inside a 200.7 ms sampling
  interval, and because `BridgeHeartbeat` is written by the *bridge*, so a halted
  CPU does not stop it advancing at all. **That silence is a sampling artefact, not
  evidence that the link held.** The evidence that it dropped is the PLC's latch,
  which is a level and therefore survives to be sampled.
* **The STOP residual has no committed sample in this run.** While the CPU is in
  STOP the program writes nothing, so `ConveyorSpeedCommand` *holds* its last
  value and a held value is indistinguishable from a live one. §A.3's residual is
  unchanged and undisputed; its duration, and hence how long the CPU was actually
  in STOP, is not measured by anything here.

## D — simulation stopped, bridge alive: two sub-cases, and only one of them is in the container set

The container capture of §D above froze a belt that was already **parked on its
mechanical stop**, so its frozen speed read-back was ~0 and the drive-fault
condition it demonstrates is the **at-rest** one. That distinction is the whole of
this case, and it cost run 1 a defect: generalising the at-rest capture produced a
detection that was blind mid-motion (LESSONS 2026-07-28).

### D (i) — frozen while the belt was at rest but commanded

Run 2, 16:33 (1 Hz log; kill at 16:33:32.399 **[transcript]** during the dwell,
with presence `True`). The dwell commands `0.0`, so nothing was owed while it ran;
when the dwell ended, step 30 commanded **−0.150 into a cell that no longer
existed**. `ConveyorDriveFault`, `CellCycleRunning → False` and
`CellResetRequired → True` appear together at **16:33:35.486** — one
`DRIVE_FAULT_DELAY` (1 s) after the setpoint went non-zero. This is term **D1**:
a non-zero command against a read-back below `SPEED_TOLERANCE`.

The same path was demonstrated a second time by accident, with the cell idle: a
start press against an already-dead simulation raised the fault within **1.004 s**
(cycle at 16:32:44.616, fault at 16:32:45.620), which is also the "no way to run a
dead cell" half of `SPEC.md` §11 T4.7.

`PositionFrozen` staying `FALSE` here — the reading that names which term fired —
is **[transcript, owner capture 16:33:32]** and that capture is not in the
committed set.

### D (ii) — frozen **mid-motion**: the case the heartbeat cannot see

Run 1, m3-05 build: **not detected at all.** The image froze at position
0.9273 m / speed 0.1500 m/s under a `+0.15` command; `ConveyorDriveFault` was
`False` in every one of 3 907 observer samples, and the cycle was finally dropped
26.3 s later by an unrelated link loss (`EVIDENCE_LATENCY.md` §B.13 F2).

Run 2, rebuilt program, ~17:59:36: **detected in 2.301 s.**

```
last ConveyorBeltPosition write carrying a NEW value   rel 628.0022  0.9636000372489671
                              (previous value          rel 627.9543  0.9630000372251254)
ConveyorSpeedCommand 0.15 -> 0.0, server acknowledged  rel 630.3028
                                              elapsed  2.301 s
```

* the freeze landed **6.25 s into the stroke**, 0.9285 m from where the belt
  started — i.e. nowhere near the ~33 ms window the old one-shot reference could
  see;
* the **heartbeat kept advancing in every one of the 891 observer samples**,
  `BridgeLinkOk` stayed `True` and the session count never moved. From the PLC's
  side the link was perfect for the whole event, which is the point of this case;
* the frozen speed read-back was **0.1500000059** — plausible and non-zero — so
  **term D1 was blind by construction**, exactly as the specification says it is;
* the 5 Hz observer reproduces the event independently at **2.207 s** (both of its
  endpoints may be up to one 0.2 s sample late), and the 1 Hz diagnostics bracket
  `ConveyorDriveFault` going `True` between rel 629.655 and rel 630.705, which
  places the latch and the zeroed command in the same event;
* 2.301 s lies inside the specified detection window of **[≈2.1 s, 3.2 s]**, which
  is the strongest available statement about *which* term fired, since Group 4's
  `PositionFrozen` was not captured for this event.

**What the bridge did during the freeze, and what it did not do.** It kept
writing. The frozen sample's age is visible in the bridge's own statistics as an
`L1` maximum of **4 998 ms** for `ConveyorBeltPosition` — the 4.981 s the freeze
lasted before the revived simulator published again — and the bridge **acted on
none of it**: no timeout, no substituted value, no fault, no farewell (§1.1, and
§D above: "the bridge cannot detect it without adding a timer that gates a signal,
which is control"). The detection is the PLC's, and it is the PLC's alone.

## Reset behaviour after a case-D fault, which the container run has no program to show

Run 2, 16:38, after a mid-motion case-D fault on the rebuilt program: a reset
attempted at 16:38:23 **[transcript]** while the simulation was **still dead** was
**refused** — `CellResetRequired` and `ConveyorDriveFault` read `True` in every
1 Hz poll from 16:38:17.014 to **16:38:52.035, 35.0 s** — because the frozen
read-back still claimed 0.15 m/s and so the cause had not gone. Only after the
simulation was revived did the reset clear the latch, and a **separate** start
press then re-ran the cycle (16:38:59.241 → clean end 16:39:19.958). After the
at-rest D (i) the reset was honoured immediately instead, because D1 clears the
moment the setpoint is zeroed.

That is the difference a program makes to this file: the container run can show
the input image and the session, and nothing about recovery. Two deliberate
actions on two different buttons, no auto-resume, and no way to run a dead cell.

---

## What none of this establishes

The **reaction** — which is why the PLCSIM section above exists. The double has no
program, so `CellCycleRunning`, `CellProcessStopActive`, `CellResetRequired`,
`ProductPresentAtSensor`, `ConveyorDriveFault` and `BridgeLinkOk` stayed `False`
in every one of the four container cases. What the equipment does when the
heartbeat goes stale — drop the cycle-running flag, command `0.0`, require a
monitored edge-triggered reset before the cycle may run again, and never restart
on a returning heartbeat alone — is `plc/demo-cell/SPEC.md` content, and it is
recorded in "The PLCSIM Advanced repeat" above rather than here. **Nothing in the
four container cases is amended by it**: each stays a true statement about a
Python server with no program, and the reaction figures stay qualified by the day
and the program build that produced them.

Three things the PLCSIM section still does not establish, carried as
owner-outstanding rows in `EVIDENCE_LATENCY.md` §B2.12 and re-dispositioned in
§B3.4: case C as a **network or adapter** break with the CPU still running (CPU
STOP → RUN has now been performed three times and in both of its bridge states,
but the adapter was never broken under a running program), the §9 **Group 4**
readings that name which drive-fault term fired in D (i) and D (ii) — no capture
covers either moment, and none covers the 19:25:43 restart either — and a **cold
start of the CPU**, which no run has yet done.

That last one wants splitting now that the §6.8 rebuild has been exercised.
**T4.9b's fresh-bridge form no longer needs a cold start and has passed** on build
G: a reset held from before link-up was refused for 28.202 s across the link-up and
only a fresh rising edge cleared the latches (`EVIDENCE_LATENCY.md` §B3.1). What
still needs a cold start is **T4.8's first clause** — and with it the only direct
reading of the corrected boot polarity, `ProcessStopLatch` and `BridgeLinkOk`
inside the first `HEARTBEAT_STALE_TIME` of a CPU run **with the bridge down**,
where no rewrite can mask the answer — and **T4.9b's second form**, a CPU start
with `reset` already publishing. Neither has been done.

Loss of the bridge is a **degraded mode, not a safety event** (invariant 2), and
no safety function appears anywhere in these four cases (invariant 1).
