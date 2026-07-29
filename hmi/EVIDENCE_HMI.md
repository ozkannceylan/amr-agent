# EVIDENCE_HMI — the commissioning HMI against two doubles

Brief `docs/briefs/m4f-07-hmi-backend-ui.md`. Every figure below is quoted as the
harness or the process printed it; nothing here is arithmetic done while writing.

**Neither server in this file is a PLC, and the live PLCSIM Advanced instance was
never contacted.** Both harnesses refuse a non-loopback endpoint outright, and
the two configurations used name loopback ports 4847 and 4850. `hmi/config.yaml`,
which addresses the commissioned CPU, was not run.

| Item | Value |
|---|---|
| Date | **2026-07-29**, runs started `08:16:29` and `08:17:03` guest local (UTC+2) |
| Host | WSL2 Ubuntu 24.04, `/mnt/c` checkout, headless |
| venv | `/home/ozkan/amr-hmi-venv`, created `python3 -m venv ~/amr-hmi-venv && ~/amr-hmi-venv/bin/pip install asyncua==2.0.1` — **plain venv, deliberately not `--system-site-packages`** |
| Python | `3.12.3 (main, Jun 19 2026, 12:46:00) [GCC 13.3.0]` |
| asyncua | `2.0.1`, the version `bridge/requirements.txt` pins and the bridge venv carries (`pip show asyncua` in `/home/ozkan/amr-bridge-venv`) |
| Dependencies | `asyncua` and the standard library. `~/amr-hmi-venv/bin/python -c 'import rclpy'` answers `ModuleNotFoundError: No module named 'rclpy'` — the boundary is a property of the environment, not only of the source |
| Pass A server | `bridge/test_double/plc_test_double.py` on **4847**, this layer's own port (m4f-06 used 4842–4846) |
| Pass B server | `plc/forklift/double/server.py` on **4850**, the PLC layer's logic double |
| Configs | `hmi/config-double.yaml` (pass A), `hmi/config-logic-double.yaml` (pass B) |
| Raw evidence | `evidence/harness-2026-07-29-m4f07-*.log`, `evidence/hmi-2026-07-29-m4f07-*.log`, `evidence/hmi-cycles-2026-07-29-m4f07-*.csv`, `evidence/double-observe-2026-07-29-m4f07-*.csv` |

Every process had stopped before its files were read: `ss -ltn` reported **no
listeners on 4847/4850/8089/8090** afterwards (LESSONS 2026-07-28 — a session is
ended by observation, never by assumption).

**Why a plain venv.** The repository convention is a venv with
`--system-site-packages`, because the bridge and the simulation need `rclpy` from
the system ROS install. This layer must not have `rclpy` at all
(`hmi/README.md`), so a plain venv makes the boundary enforceable rather than
merely stated, and the brief's recipe is followed verbatim.

---

# A. Against the bridge test double — the contract

`hmi/tools/check_hmi_writes.py`, **40 checks, no failures**. The harness plays two
roles from outside the HMI: the *operator*, by posting to the HMI's own loopback
`/control` endpoint — the same endpoint the browser posts to — and an
*independent observer*, over its own OPC UA session, so every "the write landed"
below is the server's answer and not the HMI's.

The double runs no standard program. `Forklift/Status/*` and `HmiLinkOk`
therefore hold their start values for the whole run, which is the honest answer
and not a defect; section B is where they move.

## A.1 The write allowlist is in code, and a config cannot widen it

```
J. the write allowlist refuses a configuration naming anything else
   ok   the HMI refuses to start on that configuration — exit 2
   ok   and says why — ConfigError: /tmp/amr-hmi/hmi-config-doctored.yaml: the write set must be exactly the six HMI-writable nodes (HmiForkRequest, HmiHeartbeat, HmiResetRequest, HmiSteerRequest, HmiTeleopRequest, HmiTractionRequest); this file names ForkliftTractionSpeedRef, HmiForkRequest, HmiHeartbeat, HmiSteerRequest, HmiTeleopRequest, HmiTractionRequest
```

The doctored file replaced `HmiResetRequest` with `Forklift/Output/
ForkliftTractionSpeedRef` — an actuator setpoint. Per-*client* write scoping is
policy rather than server enforcement on the commissioned CPU (ADR 0008 D2.5), so
the policy is kept in `hmi_server.py`: `HMI_WRITABLE_PATHS` is the allowlist,
every write passes through the single helper `HmiClient._writable`, and
`validate_config` refuses to start a process whose configuration names anything
else. Widening the write set needs a code change, not a config edit.

## A.2 Namespaces are resolved by URI at every session, never hardcoded

The same binary, against two different servers, in this file's two passes:

```
pass A   session established with opc.tcp://127.0.0.1:4847/amr-agent/celldouble/ — 6 writable node(s), 12 read-only node(s); browse prefix 5:ServerInterfaces/6:DemoCell
pass B   session established with opc.tcp://127.0.0.1:4850/ — 6 writable node(s), 12 read-only node(s); browse prefix 2:ServerInterfaces/3:DemoCell
```

Two servers, two different index pairs, one unchanged configuration: the indices
are resolved from `http://www.siemens.com/simatic-s7-opcua` and `http://DemoCell`
at every session establishment, each path element carries the index of *its own*
namespace, and neither is derived from the other (`bridge-design.md` §3.1
N2/N3). A client that had hardcoded either index would have failed against one of
these two.

The session timeout is **requested, not granted**:

```
pass A   session timeout requested 10000 ms, granted 8000 ms (the granted value is the only one any behaviour uses)
pass B   session timeout requested 10000 ms, granted 10000 ms (the granted value is the only one any behaviour uses)
```

`asyncua` also prints its own warning, `Requested session timeout to be 3600000ms,
got 8000ms instead`, which names the library's secure-channel default rather than
what this client asked for — the same discrepancy m3-21 recorded for the bridge
(`bridge-design.md` §3.2). The line above is the HMI's own and carries the two
numbers that matter.

## A.3 The controls map to the three Reals, in the units the nodes declare

```
B. the joystick and the fork buttons map to the three Real requests (§10.4)
   ok   HmiTractionRequest is the joystick's Y as a fraction — 0.6200000047683716
   ok   HmiSteerRequest is the joystick's X in rad, X * 1.31 — -0.6549999713897705
   ok   HmiForkRequest is the fork button as a fraction — 1.0
```

The read-backs are the single-precision neighbours of the posted values, which is
the `float64 → Real` narrowing §10.4's Float type implies. `HmiSteerRequest` is
an **angle**, so the joystick's normalised X is expressed in rad against the
engineering range §10.4 declares (`STEER_REQUEST_MAX_RAD = 1.31`); the other two
are **fractions**, so the HMI never learns the plant's maximum speeds and the PLC
owns them (invariant 10).

## A.4 All six nodes every cycle, regardless of change

```
A. all six nodes are written EVERY cycle regardless of change (§10.4, H1)
   ok   another client overwrote HmiTractionRequest on the server — -0.8999999761581421
   ok   the HMI rewrote its own value with no operator action — 0.6200000047683716 after 98 ms; a write-on-change client would have left the overwrite standing
   ok   and the heartbeat advanced across the same window — 5 -> 6
```

This is the §10.4 / §10.8 H1 policy made falsifiable rather than asserted. The
harness overwrote a request node from its own session; the HMI repaired it inside
one cycle with nobody touching a control. The failure recorded on 2026-07-28 — a
reverted server image that a write-on-change client never repairs — cannot form
on this side.

From the per-cycle evidence CSV:

```
hmi-cycles-2026-07-29-m4f07-bridgedouble-20260729T061631Z-pid60432.csv
  cycles n=79  write RTT median 1.185 ms  p95 2.408 ms  max 12.868 ms
  cycle period median 100.00 ms  p95 100.90 ms  max 2119.60 ms
  heartbeat 1 -> 79, distinct consecutive changes 78 of 78 intervals
```

**78 of 78** — the counter changed at every single cycle boundary in the file,
which is the whole of this client's heartbeat obligation. The `max 2119.60 ms`
period is the reconnect gap of A.8: the CSV records only cycles that ran, so the
interval that spans a dead server appears as one long period. The backend's own
period measurement does **not** include it — the cycle loop starts a fresh
measurement after every reconnect — which is why that gap does not trip the 5 Hz
floor of A.9.

## A.5 Release writes zeros, the enable is a level, the reset is one cycle

```
C. release writes zeros immediately (the deadman)
   ok   all three Real requests read zero — 0.0, 0.0, 0.0

D. HmiTeleopRequest is a level, asserted and withdrawn (§10.4)
   ok   asserted — True
   ok   and still asserted half a second later with no operator action — a level, not an edge — True
   ok   withdrawn by writing FALSE — False

E. HmiResetRequest is momentary: TRUE for one write cycle, then FALSE
   ok   the pulse was observed TRUE on the server — 9 of 90 samples over 1.0 s
   ok   and it spanned 1 heartbeat value(s) — one write cycle, sampled across a 100 ms cycle boundary
   ok   and it reads FALSE again afterwards, so the PLC sees the node low between presses and can arm its edge per link session (§10.8 P6) — False
```

The reset pulse is bounded by the heartbeat, not by a clock: nine samples at
100 Hz all carried the **same** `HmiHeartbeat` value, so the `TRUE` spanned
exactly one write cycle. Because every other cycle writes `FALSE`, the PLC always
sees the node low between presses, which is what lets it clear
`ResetDeviceFault` and arm the edge inside the current link session (§10.8 P6).
The edge, the arming and the hold stay in the program; this client only carries
the operator's action.

## A.6 The metrics panel reads status and applies it to nothing

```
M. the metrics panel reads Input/Output/Status/Link and nothing else
   ok   ForkliftForkHeight reached the panel — 1.2300000190734863
   ok   ForkliftLinearSpeed — -0.4399999976158142
   ok   ForkliftObstacleMinDistance — 2.75
   ok   ForkliftTractionSpeedRef is on the panel beside the measured speed — 0.0
   ok   the four status lamps and HmiLinkOk are on the panel — ForkliftTeleopActive=False, ForkliftObstacleStopActive=False, ForkliftSpeedLimitActive=False, ForkliftResetRequired=False, HmiLinkOk=False
   ok   and no Forklift/Hmi/ node is read back into the display — the requests are this client's output, not its state
   ok   the panel is polled at 5 Hz — age 30.7 ms
```

Twelve read nodes: four `Forklift/Input/`, three `Forklift/Output/`, four
`Forklift/Status/` and `Forklift/Link/HmiLinkOk`. `Forklift/Hmi/` is deliberately
absent from the read set — reading its own writes back would invite treating the
server's copy as this client's state. Nothing read here is combined with anything
or applied to anything: the panel displays and the PLC decides.

## A.7 Write round-trip, as the HMI reports it to the operator

```
F. the heartbeat advances every cycle (H1)
   ok   the counter changed over 2.0 s — 30 -> 50, 20 increments
        HMI-reported write RTT last 1.01 ms, median of 10 1.302 ms; measured cycle period 100.0 ms (target 100.0 ms)
        heartbeat 50 after 50 write cycles; last good write 28.3 ms ago
```

Twenty increments in 2.0 s is the 10 Hz cadence. The round-trip is measured
around the whole write phase — the five requests as one batched call, then the
heartbeat — so it is the number that would grow first if the CPU or the network
slowed, and it is on the operator's panel as *last* and *median of 10*.

## A.8 Session lost and regained

```
G. session lost and regained (§10.8 H4, H5 on reconnect)
   ok   a full traction demand is standing before the loss — 1.0
   ok   the HMI reports RECONNECTING while the server is gone — ConnectionError: client is disconnected
   ok   and the heartbeat is not advancing, because there is nowhere to write it
   ok   the HMI reconnected on its own, with no operator action
   ok   and the requests come back AT REST, not at the standing demand — 0.0, 0.0, 0.0, teleop=False
   ok   the counter is NOT reset across the reconnect (H4) — 56 before the loss, 74 after, and the double came back up with its own start value 0
```

and in the HMI's own log:

```
08:16:37,210 WARNING hmi session lost: ConnectionError: client is disconnected
08:16:37,210 INFO    hmi controls returned to rest (deadman: ConnectionError: client is disconnected)
08:16:37,210 WARNING hmi final zeros write attempt FAILED (ConnectionError: client is disconnected): ConnectionError: client is disconnected
08:16:38,221 WARNING hmi connect failed: ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 4847) (retry in 1.0 s)
08:16:39,239 INFO    hmi session established with opc.tcp://127.0.0.1:4847/amr-agent/celldouble/ — 6 writable node(s), 12 read-only node(s); browse prefix 5:ServerInterfaces/6:DemoCell
```

Two things are worth naming.

**The counter continued: 56 → 74 across an outage in which the server restarted
from its own start value `0`.** That is §10.8 H4 — the heartbeat is a counter, not
a session artefact, and it is not reset by a reconnect.

**No standing demand crossed the outage.** A full `+1.00` traction request was
standing when the link dropped; when the session returned the server read `0.0`
for all three Reals and `False` for the enable. That is not a farewell write —
the farewell write is recorded above as *FAILED*, because there was no session to
carry it. It is the deadman: a dropped session means the browser's control stream
is no longer being carried, which is a release, so the controls returned to rest
and the reconnect published "the current state of its controls", which is what
§10.8 H5 permits.

## A.9 The two stop paths, and why they are different

**Clean shutdown — no farewell value at all (§10.8 H5).**

```
I. clean shutdown writes NO farewell value; the heartbeat stops (H5)
   ok   the heartbeat is frozen after the kill — 79, then 79 1.5 s later
   ok   and the requests RETAIN their last written values — HmiTractionRequest 0.3499999940395355, HmiTeleopRequest True. That is exactly why §10.8 exists: a stopped HMI is not detectable from the requests alone
```

```
08:16:41,488 INFO    hmi shutting down cleanly: no farewell value written, nothing zeroed on the server (§10.8 H5). The heartbeat stops here and the link verdict is the PLC's.
```

This is the better demonstration of the two, because it leaves the server holding
a live-looking demand under a stopped counter — precisely the condition the
watchdog exists to catch. Section B.9 shows the PLC catching it.

**Backend fault — the deadman, one final write attempt, then the counter stops.**

```
H. backend fault: one final zeros write attempt lands, then the heartbeat stops
   ok   a demand is standing when the fault is injected — -0.800000011920929
   ok   the HMI reports DOWN — injected backend fault (TEST SCAFFOLDING)
   ok   the final zeros write LANDED on the server — 0.0, 0.0, 0.0, teleop=False
   ok   and the heartbeat stopped and stayed stopped — 50, then 50 2.0 s later
   ok   the HMI says so itself, on the banner the operator is looking at
```

```
08:16:49,986 INFO    hmi controls returned to rest (deadman: injected backend fault (TEST SCAFFOLDING))
08:16:49,987 WARNING hmi final zeros write attempt LANDED (injected backend fault (TEST SCAFFOLDING)); heartbeat stopped
08:16:49,988 ERROR   hmi HMI has STOPPED WRITING: injected backend fault (TEST SCAFFOLDING). ...
08:16:49,988 ERROR   hmi UI still served on http://127.0.0.1:8089/ with the banner reading DOWN. No node is being written; the PLC owns what the machine does from here.
```

The fault was injected with `--inject-fault-after-s`, a flag labelled TEST
SCAFFOLDING in the CLI help and never used in a demonstration run. It exists
because a fault path that has never executed is not a path. It raises inside the
write cycle, so it takes exactly the same code as any unexpected backend
exception.

**`DOWN` is terminal and the UI stays up.** The write cycle does not resume; the
page keeps being served so the banner can say `DOWN` and say why. Restarting the
process is the operator's action.

The third way this process stops writing is the **5 Hz contractual floor of §10.8
H2** — "below the floor the HMI is not a supervision source and must stop writing
rather than write slowly". It is measured over the last ten cycles, so one
scheduling hiccup is not a stall and a sustained rate below 5 Hz is. It was not
exercised in these runs: the measured period never left `100.0 ms` median /
`100.90 ms` p95.

## A.10 The six, and only the six

```
K. the HMI touched the six HMI-writable nodes and nothing else
   ok   no Forklift/Input/, Output/ or Status/ node name appears anywhere in the HMI's log — none of the twelve
```

and the page itself:

```
UI. the page is served and references nothing outside itself
   ok   GET / serves the operator page — 20626 bytes
   ok   no external stylesheet, font, image, script or @import in the page — none of the eight tokens found
```

---

# B. Against the PLC logic double — the lamps and the metrics move

`hmi/tools/check_hmi_teleop_loop.py`, **33 checks, no failures**, against
`plc/forklift/double/` on port 4850.

**Nothing in this section is evidence about the TIA Portal build.** That double
is the PLC layer's rehearsal stand-in for `plc/forklift/SPEC.md`; any divergence
resolves toward TIA and the spec, never toward the double. What section B *does*
establish is that this HMI drives a server that answers with real §7 verdicts —
which section A could not, because the bridge double runs no program.

Three processes, three roles, and the separation is the point:

| Process | Role | Writes |
|---|---|---|
| `check_hmi_teleop_loop.py` | the **bridge** and the **plant** | `DemoCell/Link/BridgeHeartbeat`, the four `Forklift/Input/` nodes |
| `hmi_server.py` | the **operator** | the five `Forklift/Hmi/` requests, `Forklift/Link/HmiHeartbeat` |
| `plc/forklift/double/server.py` | the **PLC** | every `Forklift/Output/` and `Forklift/Status/` node, `HmiLinkOk`, `BridgeLinkOk` |

The two client writable sets are disjoint by construction and distinguishable by
BrowseName prefix, exactly as §10.1 requires. The harness wrote the four plant
inputs **before** starting its heartbeat, which is the shape of the bridge's R3
rule and is what keeps a verdict from being formed on a start value.

## B.1 The boot polarity of the link verdict

```
P0. both link verdicts form, and the HMI's is FALSE until the counter moves
   ok   HmiLinkOk is FALSE before the HMI has written anything — False. 'Not yet proven stale' is not 'alive' (§10.8 P2)
   ok   the HMI reached CONNECTED against the logic double
   ok   HmiLinkOk went TRUE once the HMI's counter had been seen to change — the PLC's verdict on this client's heartbeat
   ok   BridgeLinkOk is TRUE too — teleop needs both, and they are independent watchdogs on independent clients (§10.8 P7)
   ok   ForkliftResetRequired is TRUE out of the boot window — both link-lost latches were set while the verdicts were FALSE — True
   ok   and the HMI's RESET REQUIRED banner is showing it, read from the node rather than recomputed
```

The HMI makes the counter change; the verdict is the PLC's. The banner the
operator sees is `ForkliftResetRequired` read off a node, not a conclusion this
client reached.

## B.2 Reset clears; a separate edge energizes

```
P1. the monitored reset clears the latches and energizes nothing
   ok   ForkliftResetRequired went FALSE on the rising edge of HmiResetRequest
   ok   and NOTHING energized: ForkliftTeleopActive is still FALSE — False
   ok   and all three setpoints are still 0.0 — 0.0, 0.0, 0.0

P2. a separate rising edge of HmiTeleopRequest enables teleop
   ok   ForkliftTeleopActive went TRUE — the PLC's verdict, not the HMI's request echoed back
   ok   the HMI's teleop lamp followed it
```

## B.3 The joystick reaches the plant only through PLC logic

```
P3. the joystick moves the PLC's setpoints (HMI -> PLC -> plant)
   ok   ForkliftTractionSpeedRef = 0.60 m/s — the request 0.60 scaled by the PLC's TRACTION_SPEED_MAX; the HMI never knew the maximum
   ok   ForkliftSteerAngleRef = -0.6550 rad — the joystick's X at -0.50 of the declared engineering range
   ok   the metrics panel shows the reference beside the measurement — ref 0.600 m/s, measured 0.580 m/s
```

The fraction became a velocity inside the PLC. Change `TRACTION_SPEED_MAX` and
the machine changes without this page changing and without the two having to
agree about a number.

## B.4 The fork-height speed cap, on the operator's panel

```
P4. raising the carriage caps the traction setpoint (process logic in the PLC)
   ok   ForkliftSpeedLimitActive went TRUE with the carriage above the cap height
   ok   and the traction setpoint was reduced below what the operator asked for — 0.180 m/s against a request that still reads 0.60
   ok   the HMI's speed-limit lamp is on and the height reads 0.8999999761581421 m
```

## B.5 A latched process stop over a live command

```
P5. an obstacle in the stop field latches a PROCESS stop over a live command
   ok   ForkliftObstacleStopActive latched
   ok   ForkliftTeleopActive dropped in the same call
   ok   all three setpoints went to 0.0, the steer angle included — 0.0, 0.0, 0.0
   ok   while the operator's request is STILL STANDING at 0.6 — the latch overrides a live command, which is the whole point of the request/outcome split
   ok   and ForkliftResetRequired is TRUE again
   ok   the HMI's large stop banner is up, driven by the node

P6. the field clearing does not release the latch; this machine does not resume by itself
   ok   the field is clear and the latch is still standing — True
```

This is the clearest statement of what this layer is. The operator's hand was
still on the joystick at `0.60`; the machine stopped anyway, because the request
is a request and the PLC owns the outcome. **This is standard-program process
logic and it implements no SRS function** — not SF-02, SF-03, SF-04, SF-07 or
SF-09 (ADR 0008 D3). Neither the node names, the banner text nor this file calls
it an emergency or a protective stop.

## B.6 §10.7's conflation, exercised

```
P7. §10.7's conflation: an enable held through the reset produces no edge
   ok   the reset cleared the latches with ENABLE still asserted
   ok   and teleop did NOT come back: no rising edge, so the machine stays stopped — False
   ok   released and re-asserted, the enable produces a real edge and teleop returns — release ENABLE, press RESET, assert ENABLE again
```

There is no start request in the node group, so `HmiTeleopRequest` carries both
the enable and the post-reset start action (§10.7, §10.12 item 7). The page states
the sequence on the operator's screen rather than hiding it, and the backend does
**not** drop the enable automatically at a reset — that would be sequencing, and
sequencing is the PLC's.

## B.7 The fork jog

```
P8. the fork buttons move the fork setpoint
   ok   ForkliftForkSpeedRef went non-zero while the FORK UP button was held — 0.15000000596046448
   ok   and back to 0.0 on release, which the plant holds against gravity — 0.0
```

## B.8 Stopping the HMI is a degraded mode with a PLC-owned controlled stop

```
P9. stopping the HMI is a degraded mode with a PLC-owned controlled stop
   ok   the machine is being driven when the HMI is stopped — ForkliftTractionSpeedRef 0.550 m/s
   ok   HmiLinkOk went FALSE 650 ms after the HMI stopped — the heartbeat stopped changing and the PLC's stale timer expired
   ok   teleop dropped and every setpoint went to 0.0 in the PLC's mandatory ELSE — 0.0, 0.0, 0.0
   ok   and the loss LATCHED: a returning heartbeat will not by itself restore teleop
        the HMI's last requests are still on the server, retained; the machine stopped anyway, because the PLC decided it (ForkliftTractionSpeedRef 0.0)
```

The HMI was stopped with `SIGTERM`, so it took the **clean shutdown** path of
A.9: no farewell value, nothing zeroed, the counter simply stopped. The requests
stayed on the server at their last written values. **650 ms later the PLC had
stopped the machine on its own**, against a `T#600ms` stale window.

That is invariant 2 at the operator boundary: losing the link is a degraded mode
with a controlled stop, and the stop belongs to the PLC. Nothing in this layer
implemented it, and nothing in this layer is a safety device.

## B.9 The whole run, as transitions on the server

Every change the harness's independent session observed, in order:

```
08:17:05 BridgeLinkOk=True  HmiLinkOk=True
08:17:05 ForkliftResetRequired=False
08:17:05 ForkliftTeleopActive=True
08:17:06 ForkliftSteerAngleRef=-0.655  ForkliftTractionSpeedRef=0.600
08:17:06 ForkliftSpeedLimitActive=True  ForkliftTractionSpeedRef=0.180
08:17:07 ForkliftObstacleStopActive=True  ForkliftResetRequired=True  ForkliftSpeedLimitActive=False  ForkliftSteerAngleRef=0.000  ForkliftTeleopActive=False  ForkliftTractionSpeedRef=0.000
08:17:08 ForkliftObstacleStopActive=False  ForkliftResetRequired=False
08:17:09 ForkliftSpeedLimitActive=True  ForkliftTeleopActive=True
08:17:09 ForkliftForkSpeedRef=0.150
08:17:09 ForkliftForkSpeedRef=0.000
08:17:10 ForkliftSpeedLimitActive=False
08:17:10 ForkliftTractionSpeedRef=0.550
08:17:10 ForkliftResetRequired=True  ForkliftTeleopActive=False  ForkliftTractionSpeedRef=0.000  HmiLinkOk=False
```

`BridgeLinkOk` never flickers, so the last line is attributable to the HMI link
alone. An earlier revision of the harness waited for the HMI's exit
*synchronously*, which stalled its own bridge pump long enough for
`BridgeHeartbeat` to go stale too — both verdicts then dropped together and the
attribution was lost. The harness now awaits the exit without blocking its event
loop, and the transition list above is what that fixed.

Per-cycle figures for this pass:

```
hmi-cycles-2026-07-29-m4f07-logicdouble-20260729T061705Z-pid60582.csv
  cycles n=46  write RTT median 1.161 ms  p95 2.106 ms  max 2.369 ms
  cycle period median 100.00 ms  p95 100.70 ms  max 101.70 ms
  heartbeat 1 -> 46, distinct consecutive changes 45 of 45 intervals
```

---

# C. The page, in a browser

The two harnesses drive the HTTP endpoints; they do not press the buttons. The
page was therefore loaded in a real browser engine (Chromium, over the same
loopback backend on port 8090, against the logic double with the plant driven as
in section B) and its controls exercised through genuine DOM pointer events.
Values read out of the live page:

```
{ "linkstate": "CONNECTED", "hb": "728", "rtt": "0.9 / 1.1 ms",
  "banner": "on reset-only", "title": "RESET REQUIRED",
  "lastwrite": "70 ms ago", "resetreq": "lamp warn on" }
```

Joystick, dragged to X = +0.55 and Y = +0.64: the knob moved to `left 77.5%`,
`top 18%` — the geometry the axes imply — and the backend reported the requests

```
{ "HmiTractionRequest": 0.64, "HmiSteerRequest": 0.7205000000000001,
  "HmiForkRequest": 1, "HmiTeleopRequest": true, "HmiResetRequest": false }
```

with the PLC answering, one screen later,

```
{ "ForkliftTeleopActive": true, "ForkliftSpeedLimitActive": true,
  "ForkliftTractionSpeedRef": 0.19200000166893005,
  "ForkliftSteerAngleRef": 0.7204999923706055,
  "ForkliftForkSpeedRef": 0, "ForkliftForkHeight": 1.5536727905273438 }
```

Three things are visible in those numbers. The traction reference is
`0.64 × 0.30`, the raised-carriage cap, not `0.64 × 1.00`. The steer angle is
`0.55 × 1.31`, carried through unchanged. And `ForkliftForkSpeedRef` is `0.0`
while the FORK UP button was still held, because the carriage had reached the
soft travel limit and the PLC aborted the jog **in the raising direction only** —
a limit this HMI does not know about and did not implement.

Deadman, on pointer release:

```
before { "HmiTractionRequest": 0.64, "HmiSteerRequest": 0.7205, "HmiForkRequest": 1, "HmiTeleopRequest": true }
after  { "HmiTractionRequest": 0,    "HmiSteerRequest": 0,      "HmiForkRequest": 0, "HmiTeleopRequest": true }
```

The three Reals went to zero and the knob returned to centre, while
`HmiTeleopRequest` stayed `true` — the enable is a level and is released by its
own deliberate action, not by letting go of the stick.

The browser console carried **one** message for the whole session, a `404` for
`/favicon.ico` that the browser requests by itself. The backend now answers that
path with `204 No Content` — answered, not served, because the page carries no
asset of any kind and a standing console error on a commissioning screen is
noise the operator has to learn to ignore.

**No screenshot is committed.** The figures above are the evidence; an image of
the page is not reproducible from this repository and would age against the
markup. Opening `http://127.0.0.1:8088/` while the HMI runs is the check.

---

# D. What is deliberately not shown here

| Not shown | Why |
|---|---|
| Anything about the commissioned S7-1500 | Both harnesses refuse a non-loopback endpoint and `hmi/config.yaml` was never run. The live connection is the owner's, later |
| Anything about the TIA Portal build | Section B ran against `plc/forklift/double/`, a rehearsal stand-in. `opcua-nodes.md` §10 is a design value until the owner reads the `Forklift/` subtree back out of the tool (§10.2 step 6) |
| A browser that crashes with the joystick held | The page returns the controls to rest on release, blur, hide and unload, which covers everything the browser can report. A hard crash leaves the last requests standing until the PLC's watchdog acts — a real gap, carried as an open item rather than closed with an invented timeout |
| Two writing clients being *enforced* apart | Per-client scoping is policy, not server enforcement, on a CPU running access control disabled and security `None` (ADR 0008 D2.5). A.1 shows this client keeping the policy; it does not show the server keeping it |
| A measured worst-case write period on the target machine | §10.8 P3 sets `HMI_STALE_TIME` at three worst-case write periods and says to re-derive it from a measurement if the HMI's worst case exceeds 200 ms. The p95 here is `100.90 ms`, well inside, but that is a WSL loopback figure against a double, not the commissioned cell |
