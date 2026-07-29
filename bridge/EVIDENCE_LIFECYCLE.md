# EVIDENCE — session lifecycle: reconnect, server restart, evidence files (m3-35)

Dated capture of the three ways the bridge failed during the owner's live PLCSIM
run of 2026-07-28 (`docs/LESSONS.md`, rows 62, 64 and 68), and of the three
behaviours that replace them:

| # | The live failure | The behaviour now | Proven by |
|---|---|---|---|
| 1 | A CPU download dropped the session **mid-read** and the process died on an unhandled exception instead of entering the §8.1 reconnect path | any exception out of an await that touches the session becomes `SessionBroken` and reconnects; `run()` carries a last-resort guard for a step that forgets | §2.1 (double killed under a running cycle) and §2.2 (the exact `asyncua` exception injected) |
| 2 | A CPU **warm restart** reverted every input to its start value under a surviving session; write-on-change never repaired the contacts whose slot values had not changed, so the PLC read open stop circuits for minutes | the bridge reads its **own heartbeat** back once per cycle; a value it did not write means the server restarted, the write cache is invalidated and every slot with a real sample is rewritten in the next cycle | §2.3 (session lost) and §2.4 (session **not** lost — the live case) |
| 3 | `--evidence-csv` truncated at every start; seven restarts erased a day of 20 Hz data | the path given is a **stem**; one file per session, created with `"x"` so even a name collision refuses instead of truncating | §2.5 (mechanics) and §3 (two real process starts) |

**Server: the test double, not a PLC.** Every number below was produced by
`bridge/test_double/plc_test_double.py`. The harness **kills and restarts its
server**, which is why it may never be pointed at PLCSIM Advanced
(`docs/interfaces/bridge-design.md` §10) — it refuses an endpoint that looks like
the commissioned instance. Nothing here is evidence about the PLC program, about
PLCSIM's timing or about the network path; see §5.

| Item | Value |
|---|---|
| Date | **2026-07-28**, 18:48–18:51 local (CSV stamps are UTC, i.e. 16:48–16:51) |
| Host | WSL2 Ubuntu 24.04, kernel `5.15.167.4-microsoft-standard-WSL2`, headless |
| Repo | `/mnt/c/Users/ozkan/projects/amr-agent` (Windows checkout, driven from WSL) |
| venv | `/home/ozkan/amr-bridge-venv` (`--system-site-packages`), `asyncua 2.0.1` |
| Config | `bridge/config/bridge.yaml`, endpoint overridden to the double: `opc.tcp://127.0.0.1:4841/…` (§2), `:4842/…` (§3) |
| Session grant | requested 10 000 ms, **granted 8000 ms**, keep-alive 2.667 s — unchanged by this work |
| Raw evidence | `evidence/session-lifecycle-2026-07-28.csv.gz` and the four files listed in §6 |

---

## 1. What was wrong, in the code

### 1.1 The exception that killed the process

`asyncua`'s `UASocketProtocol.send_request` (asyncua 2.0.1,
`asyncua/client/ua_client.py`) ends like this:

```python
except UaError as ex:
    raise ex
except Exception as ex:
    if self.state is not UASocketState.OPEN:
        raise ConnectionError("Connection is closed") from None
    raise Exception("Unhandled exception while sending request to OPC UA server") from ex
```

A request that was already in flight when the server went away fails its future;
if the socket state has not yet flipped to `CLOSED` — the race a CPU download
wins easily — what comes out is a **bare `Exception`**. The bridge caught
`(ua.UaError, ConnectionError, OSError, asyncio.TimeoutError, TimeoutError)`, so
it caught neither that nor anything else outside the list, and the exception left
`_output_path` → `_cycle` → `run()` → `asyncio.run` and ended the process. The
counters recorded nothing, because nothing ran.

The fix is not a longer error tuple. Every site where the cycle awaits the
session now routes **any** exception into `SessionBroken` through
`_session_broken`, which counts an unanticipated type separately
(`unexpected_session_errors`) so the evidence still says *how* the session was
lost. `_BRIDGE_DEFECTS` (`WriteNotPermitted`, `TypeMismatch`,
`NamespaceNotFound`) is the deliberate exception to the breadth: those mean this
process is wrong, and a reconnect loop would hide them.

### 1.2 The write cache that outlived the server

Contacts are written on change (`bridge-design.md` §5), and the per-session cache
that makes that possible is only correct while the server still holds what the
bridge wrote. A warm restart makes it wrong: the data block reverts, the bridge's
cache still says "already written", and `PanelStopCircuitClosed` stays `FALSE` —
stop circuit **open** — until something changes it. The bridge now reads its own
`BridgeHeartbeat` back at the top of every cycle. It is the only node outside
`Input/` the bridge may write (`opcua-nodes.md` §9.1), so a value it did not
write is not a process fact to interpret but a session fact: this is not the
server this session wrote to.

> **Confirmed against the two-client write set, 2026-07-29** (`bridge-design.md`
> §12 item 14, m4f-06). The sentence still holds with the forklift group
> configured: the write set is the `Input/` nodes of the configured groups plus
> this one heartbeat, so `BridgeHeartbeat` remains the only node outside an
> `Input/` folder that the bridge writes. It also remains a valid *witness*,
> because the second client's counter is `Forklift/Link/HmiHeartbeat` — a node
> the bridge never touches — and the two writable sets are disjoint by BrowseName
> prefix (`opcua-nodes.md` §10.1). What this run did **not** know is how wide the
> witness's blind spot is; that is measured in `EVIDENCE_CONNECT.md` § m4f-06.4.

### 1.3 The evidence file that truncated

`Recorder.__init__` opened its file with `"w"`. Now the path is a stem,
`session_csv_path` appends `-<UTC second>-pid<pid>`, and the open mode is `"x"`.

---

## 2. Conformance harness — `bridge/tools/check_session_lifecycle.py`

The harness drives the bridge's own `PlcClient.run()`, its reconnect path and its
write cache. Nothing in `amr_bridge/` is stubbed or special-cased. Two things
outside the bridge stand in for the world: the **slots** are filled by the
harness rather than by ROS callbacks (all three behaviours live on the OPC UA
side of the slots, and `Slot` cannot tell who called `put`), and the **server**
is the double, whose lifecycle the harness owns. Where the real bridge would die,
the client task here ends with an exception — so "the process never exits" is
checked as "the run task is still running", which in `main` is the same thing.

```
"$VENV/bin/python" bridge/tools/check_session_lifecycle.py \
    --workdir /tmp/amr-sl-run --evidence-csv /tmp/amr-sl-run/session-lifecycle.csv
```

Slot values are chosen so a repaired image is distinguishable from a reverted one
on every node, and the two stop circuits are `TRUE` — the values whose reversion
to `FALSE` the live run left unrepaired:

| Node | Slot value | Value the double reverts to |
|---|---|---|
| `ConveyorBeltPosition` / `ConveyorBeltSpeed` / `ProductSensorRange` | 1.25 / 0.35 / 0.42 | 0.0 |
| `PanelStartPressed` / `PanelResetPressed` | FALSE | FALSE |
| `PanelStopCircuitClosed` / `PanelProcessStopCircuitClosed` | **TRUE** | **FALSE** (circuit open) |

Full transcript (`evidence/session-lifecycle-2026-07-28-harness.log.gz`; the
`asyncua` "Requested session timeout … got 8000ms instead" lines are its own
secure-channel warning and are elided):

```
bridge session-lifecycle conformance — brief m3-35, LESSONS 2026-07-28
  config   /mnt/c/Users/ozkan/projects/amr-agent/bridge/config/bridge.yaml
  endpoint opc.tcp://127.0.0.1:4841/amr-agent/celldouble/  (TEST DOUBLE, started by this harness)
  workdir  /tmp/amr-sl-run
  evidence /tmp/amr-sl-run/session-lifecycle-20260728T164826Z-pid34942.csv
   ok   0. the bridge connected to the double and the heartbeat is advancing — 11 writes after 0.5s
```

### 2.1 An in-flight request failure reconnects; the process does not exit

```
1a. §8.1 — the double killed under a running 50 ms cycle
        SIGKILL sent to the double (pid gone), cycle was at heartbeat 11
session broken: read BridgeHeartbeat: ConnectionError: client is disconnected — degraded mode, no signal invented
   ok   the failure was routed into the §8.1 reconnect path
   ok   the run loop is still running — in the bridge this is the process still being alive — task running
   ok   the failure came out of a request the cycle had in flight, not out of a later connect attempt — read_errors 0->1, write_errors 0->0
   ok   the broken session is in the evidence file — read BridgeHeartbeat: ConnectionError: client is disconnected
connect failed: [Errno 111] Connect call failed ('127.0.0.1', 4841); retrying in 2.0s
   ok   nothing was published to the cell while disconnected (§8.3 N3) — 0 publishes in 1.0 s of outage
        double relaunched on opc.tcp://127.0.0.1:4841/amr-agent/celldouble/
   ok   the cycle resumed on the double's return, in the same process — 0.9s after the double came back
   ok   the outage is counted, so the gap in the 20 Hz evidence is stated — 1 outage(s), longest 3.02s
   ok   the evidence file carries the gap as a row — 3.02s with no cycle
```

`SIGKILL` was chosen over `SIGINT` on purpose: no session close, no goodbye, a
server that simply stops answering. The failure surfaced out of the cycle's read
(`read_errors 0->1`), which is what "in flight" means here — the round trip was
attempted against a socket that had gone. Which of the cycle's six round trips
loses the race is not controllable, and the row records whichever one it was; in
this run it was the heartbeat read-back.

The gap is now a row rather than a silence:

```
session,resumed,monotonic,82480793083009,82483812912258,3019829249,,gap in the evidence: no cycle ran in this interval
```

### 2.2 The exact exception `asyncua` raises for an in-flight failure

The kill above produced a `ConnectionError`, which the old tuple would have
caught. The exception that actually killed the live run is the bare `Exception`
of §1.1, and it is injected here at the session boundary — one node object whose
`read_value` raises exactly that, called by the bridge exactly as it calls a
resolved node. It needs no undoing: §8.1 re-resolves every NodeId on the new
session, so the shim is gone by the time the reconnect completes.

```
1b. §8.1 — the exact exception asyncua raises for an in-flight failure
        injecting Exception('Unhandled exception while sending request to OPC UA server') into the ConveyorSpeedCommand read of one cycle
read ConveyorSpeedCommand raised Exception, which is not one of the anticipated session error types; routed into the §8.1 reconnect path anyway
session broken: read ConveyorSpeedCommand: Exception: Unhandled exception while sending request to OPC UA server — degraded mode, no signal invented
   ok   a bare `Exception` from a request in flight breaks the session instead of leaving the process
   ok   the run loop survived it — task running
   ok   it is counted as an unanticipated session error, so the evidence names the failure class — unexpected_session_errors 0->1
   ok   it was routed by the step that raised it, not by the last-resort guard in run() — unrouted_cycle_errors stayed at 0
   ok   the exception type is in the evidence file — Exception
   ok   the cycle resumed on a new session — 1.3s later
   ok   the shim was called once and is gone: every NodeId was re-resolved on the new session (§8.1) — 1 call(s)
```

`unrouted_cycle_errors` staying at 0 is the check that the *step* routed it. A
non-zero value there would mean the last-resort guard in `run()` did the work,
which keeps the process alive but is a missing `except` to go and find.

### 2.3 A restart that drops the session: the whole image rewritten

```
2a. §8.1 — a restart that drops the session: every input rewritten in the first cycle of the new one
   ok   an independent read-only session sees the slot values, not the double's start values — BridgeHeartbeat=17
   ok   the rewrite of the whole image is recorded, one cycle, all seven nodes — 7/7
        the relaunched double's own view, from its first sample (5 Hz):
          2026-07-28T16:48:30.534+00:00  HB=     0  stop=False pstop=False  [start values]
          2026-07-28T16:48:30.735+00:00  HB=     0  stop=False pstop=False  [start values]
          2026-07-28T16:48:30.936+00:00  HB=     0  stop=False pstop=False  [start values]
          2026-07-28T16:48:31.137+00:00  HB=     0  stop=False pstop=False  [start values]
          2026-07-28T16:48:31.338+00:00  HB=    12  stop= True pstop= True  [as written]
          2026-07-28T16:48:31.539+00:00  HB=    16  stop= True pstop= True  [as written]
```

The read-back is over an **independent read-only session**, so what is checked is
the server's own values and not something the bridge's session is holding. The
double's own 5 Hz log shows the same thing from the server side: four samples of
start values while the bridge was still reconnecting, then the whole image as
written in the first sample after it did.

### 2.4 A warm restart that does **not** drop the session — the live failure

This is the case the old code could not see. The double's S5 scaffolding reverts
every node to its start value **in place**, with the server up and the session
untouched:

```
2026-07-28 18:48:32,913 WARNING plc-double SCAFFOLD S5: WARM RESTART — every node reset to
its start value in place; sessions untouched (1 client connection(s) still open).
```

```
2b. §8.1 — a warm restart that does NOT drop the session (the 2026-07-28 failure)
   ok   before the restart the server holds the slot values
        S5 warm restart triggered at 2026-07-28T16:48:32.901+00:00: every node back to its start value in place (BridgeHeartbeat was 23)
BridgeHeartbeat reads 0 but this session last wrote 23: the server restarted under a live session, so its input image is stale. Invalidating the write cache (§8.1).
   ok   the bridge detected the restart from its own heartbeat reading back a value it did not write — 20 ms after the trigger
   ok   no session was lost, so nothing but the read-back could have noticed — reconnects stayed at 2
   ok   the write cache was invalidated and the image rewritten — 7 nodes written, 43 ms after the trigger
   ok   all seven nodes were written in ONE cycle, not repaired gradually — 7/7
   ok   an independent read-only session sees the whole image repaired, the two stop circuits included
   ok   the double's own 5 Hz log ends with PanelStopCircuitClosed closed again — last sample True
        the double's view around the restart (5 Hz):
          2026-07-28T16:48:32.345+00:00  HB=    17  stop= True pstop= True  [as written]
          2026-07-28T16:48:32.547+00:00  HB=    17  stop= True pstop= True  [as written]
          2026-07-28T16:48:32.748+00:00  HB=    20  stop= True pstop= True  [as written]
          2026-07-28T16:48:32.949+00:00  HB=    24  stop= True pstop= True  [as written]
          2026-07-28T16:48:33.150+00:00  HB=    28  stop= True pstop= True  [as written]
          2026-07-28T16:48:33.350+00:00  HB=    32  stop= True pstop= True  [as written]
```

Read that window carefully, because it is the whole point:

* **`reconnects` did not move.** No session was lost, so the reconnect path could
  not have repaired anything. The only thing that noticed was the read-back.
* **Detection 20 ms after the trigger, image rewritten 43 ms after it** — inside
  one and two 50 ms cycles respectively. The live failure lasted minutes.
* **The 5 Hz log never samples the reverted image.** The restart landed at
  32.901 and the repair finished by 32.944, between the 32.748 and 32.949
  samples. That is honest rather than convenient: the server-side log at 5 Hz is
  too slow to catch a 43 ms hole, and the proof that the revert happened at all
  is the bridge reading `BridgeHeartbeat = 0` when it had written 23, which
  cannot happen unless the server's copy was reinitialised.
* **`HB=24` at 32.949.** The heartbeat counter continued from 23, so §8.1's
  "the counter is not reset" survives a detected restart too.
* The evidence CSV carries the pair of rows:

```
session,server_restart_detected,-,,,,0,this session last wrote 23; write cache invalidated
session,input_image_rewritten,-,,,,7/7,written in one cycle
```

### 2.5 Evidence files: a per-session name and a refusal

```
3. evidence files: a per-session name, and a refusal instead of a truncation
   ok   the path given is a stem; the file written names the session — truncation-probe-20260728T164833Z-pid34942.csv
   ok   two starts on one stem produce two files — truncation-probe-20260728T164833Z-pid34942.csv + truncation-probe-20260728T164833Z-pid34943.csv
   ok   the first session's rows are still there after the second started — 1 row(s)
   ok   an existing per-session file is refused, not truncated — /tmp/amr-sl-run/collision-probe-20260728T164834Z-pid34942.csv already exists
   ok   the refused file still holds its rows — 1 row(s)
```

### 2.6 What the read-back costs, and the counters

```
what the read-back costs (this run, against the double):
        cycle interval median 50.1 ms over 45 cycles, 0 overrun(s)
        heartbeat read-back median 0.79 ms, max 1.16 ms, n=44

counters at the end of the run:
        cycles = 48
        heartbeat_readbacks = 44
        heartbeat_writes = 45
        inputs_rewritten_after_restart = 28
        read_errors = 2
        reconnects = 2
        server_restarts_detected = 1
        session_outage_max_ns = 3019829249
        session_outage_total_ns = 4040604600
        session_outages = 2
        unexpected_session_errors = 1

RESULT: PASS
```

28 checks, no failures. `inputs_rewritten_after_restart = 28` is 4 × 7: three
sessions (the first connect, the reconnect after the kill, the reconnect after
the injection) plus the warm restart, each rewriting all seven nodes.

The read-back is one extra read per cycle and it is recorded as the `read_rt`
round trip it is, so it appears in `summarize_latency.py` beside the output read
rather than being asserted to be cheap. Against the double it costs **0.79 ms
median**; the cycle held 50.1 ms with **zero overruns**. What it costs against
PLCSIM Advanced is not established here — see §5.

---

## 3. Two real process starts on one `--evidence-csv`

§2.5 checks the mechanism inside one process. That two consecutive **bridge
process** starts produce two files is a property of the process, so it is run as
one (`evidence/session-lifecycle-2026-07-28-two-starts.log.gz`). The committed
config points at the commissioned PLCSIM instance, which is off limits to this
work, so a scratch copy with one line changed was used:

```
sed "s#^  endpoint: .*#  endpoint: \"opc.tcp://127.0.0.1:4842/amr-agent/celldouble/\"#" \
    bridge/config/bridge.yaml > /tmp/amr-sl-b3/bridge-double.yaml

for START in 1 2; do
  run_bridge.py --config /tmp/amr-sl-b3/bridge-double.yaml \
      --evidence-csv /tmp/amr-sl-b3/evidence/latency-session.csv --duration 6
done
```

```
=== bridge start 1 — same --evidence-csv argument ===
bridge evidence for this session: /tmp/amr-sl-b3/evidence/latency-session-20260728T165123Z-pid35533.csv
    (stem /tmp/amr-sl-b3/evidence/latency-session.csv; the previous session's file is not touched)
bridge stopped after 6.0s; evidence written to .../latency-session-20260728T165123Z-pid35533.csv
--- files after start 1:
    28861  latency-session-20260728T165123Z-pid35533.csv
    f0388b50b46a06ee27f7e9e727663f6c  .../latency-session-20260728T165123Z-pid35533.csv
    410 .../latency-session-20260728T165123Z-pid35533.csv

=== bridge start 2 — same --evidence-csv argument ===
bridge evidence for this session: /tmp/amr-sl-b3/evidence/latency-session-20260728T165131Z-pid35575.csv
bridge stopped after 6.0s; evidence written to .../latency-session-20260728T165131Z-pid35575.csv
--- files after start 2:
    28861  latency-session-20260728T165123Z-pid35533.csv
    28866  latency-session-20260728T165131Z-pid35575.csv
    f0388b50b46a06ee27f7e9e727663f6c  .../latency-session-20260728T165123Z-pid35533.csv
    ea1b82c2b646162b00bef27ca5ccc914  .../latency-session-20260728T165131Z-pid35575.csv
      410 .../latency-session-20260728T165123Z-pid35533.csv
      410 .../latency-session-20260728T165131Z-pid35575.csv
```

Two files, and the first one's md5 is byte-for-byte identical before and after
the second start. Under the old code the second start would have left one file
with the second session's rows in it.

These two starts ran without the Gazebo cell, so no topic ever published: the
files hold the session, cycle and output-read rows and no input rows, and the
heartbeat stayed withheld throughout (startup rule R3, working as documented).
The property under test is the file naming, and it does not depend on the cell.

---

## 4. The double's new scaffolding, and what it is not

`--warm-restart-file PATH` (S5). Touching the file assigns every node in the
address space its declared start value, in place, and removes the file so each
touch is one restart. It exists because the failure of §2.4 is invisible to a
double that can only be killed and relaunched.

It is a bulk assignment of the start values declared at the top of
`plc_test_double.py`. No program runs, nothing is sequenced, no value is derived
from another and **no restart logic is modelled** — a real CPU does far more on a
warm restart (retained data, OB handling, diagnostics) and none of it is here.
Like every other behaviour in that file it is labelled scaffolding, and nothing
observed against it is evidence for `plc/demo-cell/SPEC.md`.

The double's `--observe-csv` now follows the same one-file-per-session rule as
the bridge's evidence file, for the same reason.

---

## 5. What this does not establish

* **Nothing about the PLC program.** The double runs no standard program: no scan
  cycle, no interlocks, no cycle-running flag. `DemoCell/Status/*` and
  `BridgeLinkOk` keep their start values for the whole run.
* **Nothing about a real CPU restart.** S5 reverts values; a warm restart on an
  S7-1500 also re-runs startup OBs, reloads retained data and may drop the
  session after all. What is proven is that the bridge repairs the input image
  whether or not the session survives — not that the two cases exhaust what a
  CPU can do.
* **The timing figures are the double's, on loopback.** The 20 ms detection and
  43 ms repair, and the 0.79 ms read-back cost, are properties of this host and
  this server. On PLCSIM Advanced the round trip is longer, so both scale with
  it; the re-run against PLCSIM is **owner-outstanding**, and until it exists
  `EVIDENCE_LATENCY.md` Section B remains the only PLCSIM capture and its cycle
  figures predate the read-back step.
* **Which round trip loses the race is not controlled.** §2.1 kills the server
  and takes whichever request was in flight; §2.2 pins the exception type by
  injection. Neither reproduces a TIA download, which is what happened live.
* **The heartbeat read-back has one blind spot, stated rather than patched.** A
  revert that happens while the last written heartbeat value was exactly the
  value the server reverts to (0) reads back as equal and is not detected. It is
  one heartbeat value in 65 536, the next restart is still caught, and a restart
  that drops the session is caught by the reconnect path instead.
* **`unexpected_session_errors` and `unrouted_cycle_errors` are diagnostics, not
  targets.** A non-zero `unrouted_cycle_errors` in any future run is a missing
  `except` at the raising step; the process surviving is not the whole fix.

---

## 6. Raw artifacts

| File | Contents |
|---|---|
| `evidence/session-lifecycle-2026-07-28.csv.gz` | the bridge's own evidence file for the harness run (§2), including the `resumed`, `server_restart_detected` and `input_image_rewritten` rows |
| `evidence/session-lifecycle-2026-07-28-harness.log.gz` | full harness transcript, 28 checks |
| `evidence/session-lifecycle-2026-07-28-double.log.gz` | the double's log across both of its starts, including the S5 warm-restart line |
| `evidence/session-lifecycle-2026-07-28-double-observe.csv.gz` | the double's 5 Hz server-side view of its second start (§2.3, §2.4) |
| `evidence/session-lifecycle-2026-07-28-two-starts.log.gz` | the two `run_bridge.py` starts of §3 |

Reproduce §2 with one command (it starts, kills and restarts its own server):

```
"$VENV/bin/python" bridge/tools/check_session_lifecycle.py
```
