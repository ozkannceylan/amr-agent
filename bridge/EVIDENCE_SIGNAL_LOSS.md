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

> **The PLCSIM repeat has since been performed — it is in
> `EVIDENCE_LATENCY.md` §B.7, not here.** Brief `m3-26` (2026-07-27) ran cases
> **A**, **B** and **D** against the live CPU with the standard program in RUN,
> on the seven-node input image. Headline results, so this file is not silently
> stale: A and B were **indistinguishable to the program**, with
> `BridgeLinkOk → False` **0.50 s** after the last heartbeat change in both;
> case **D was NOT detected** — the frozen read-back held a **non-zero**
> `ConveyorBeltSpeed`, which blinds term D1, and term D2 could not fire either
> (§B.13 F2). Case **C was not performed**: it requires stopping the CPU. The
> session-hold figure of "What none of this establishes" is now measured:
> **11.79 s** after SIGKILL, **0.0 s** after SIGTERM (§B.8).
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

## What none of this establishes

The **reaction**. The double has no program, so `CellCycleRunning`,
`CellProcessStopActive`, `CellResetRequired`, `ProductPresentAtSensor`,
`ConveyorDriveFault` and `BridgeLinkOk` stayed `False` in every case above.
What the equipment does when the heartbeat goes stale — drop the cycle-running
flag, command `0.0`, require a monitored edge-triggered reset before the cycle
may run again, and never restart on a returning heartbeat alone — is
`plc/demo-cell/SPEC.md` content and must be re-run against PLCSIM Advanced
(`EVIDENCE_LATENCY.md`, Section B, item 6).

Loss of the bridge is a **degraded mode, not a safety event** (invariant 2), and
no safety function appears anywhere in these four cases (invariant 1).
