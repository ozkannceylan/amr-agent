# EVIDENCE_HMI — the commissioning HMI against two doubles

Briefs `docs/briefs/m4f-07-hmi-backend-ui.md` (sections A–D) and
`docs/briefs/m4f-07b-h6-and-holdable-reset.md` (section E, and the two amendments
marked as such in A.5 and D). Every figure below is quoted as the harness or the
process printed it; nothing here is arithmetic done while writing.

**Neither server in this file is a PLC, and the live PLCSIM Advanced instance was
never contacted.** Both harnesses refuse a non-loopback endpoint outright, and
the two configurations used name loopback ports 4847 and 4850. `hmi/config.yaml`,
which addresses the commissioned CPU, was not run.

| Item | Value |
|---|---|
| Date | **2026-07-29**. Sections A–D: runs started `08:16:29` and `08:17:03` guest local (UTC+2). Section E and the two amendments: runs started `12:46:04`, `12:47:04` and `12:48:04` the same day |
| Host | WSL2 Ubuntu 24.04, `/mnt/c` checkout, headless |
| venv | `/home/ozkan/amr-hmi-venv`, created `python3 -m venv ~/amr-hmi-venv && ~/amr-hmi-venv/bin/pip install asyncua==2.0.1` — **plain venv, deliberately not `--system-site-packages`** |
| Python | `3.12.3 (main, Jun 19 2026, 12:46:00) [GCC 13.3.0]` |
| asyncua | `2.0.1`, the version `bridge/requirements.txt` pins and the bridge venv carries (`pip show asyncua` in `/home/ozkan/amr-bridge-venv`) |
| Dependencies | `asyncua` and the standard library. `~/amr-hmi-venv/bin/python -c 'import rclpy'` answers `ModuleNotFoundError: No module named 'rclpy'` — the boundary is a property of the environment, not only of the source |
| Pass A server | `bridge/test_double/plc_test_double.py` on **4847**, this layer's own port (m4f-06 used 4842–4846) |
| Pass B server | `plc/forklift/double/server.py` on **4850**, the PLC layer's logic double |
| Configs | `hmi/config-double.yaml` (pass A), `hmi/config-logic-double.yaml` (pass B) |
| Raw evidence | `evidence/harness-2026-07-29-m4f07-*.log`, `evidence/hmi-2026-07-29-m4f07-*.log`, `evidence/hmi-cycles-2026-07-29-m4f07-*.csv`, `evidence/double-observe-2026-07-29-m4f07-*.csv`; and for section E, `evidence/harness-2026-07-29-m4f07b-*.log`, `evidence/hmi-2026-07-29-m4f07b-h6reset.log`, `evidence/hmi-cycles-2026-07-29-m4f07b-h6reset-*.csv` |

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

**Re-run in full under `m4f-07b`** — **42 checks, no failures**
(`evidence/harness-2026-07-29-m4f07b-passA.log`). Two things changed in the
instrument and both are consequences of §10.8 as amended: check `E` now tests a
held level rather than a pulse (A.5), and the harness carries a `PageBeacon` that
polls `GET /state` at 5 Hz for the whole run. Playing the operator now means
polling like the operator's *page*, because H6's window is over the page's
requests: a harness that posts a control and then reads OPC UA for three seconds
is a crashed browser as far as the backend is concerned, and is correctly treated
as one. Every figure quoted in A.1–A.10 is from the original run unless it says
otherwise.

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

## A.5 Release writes zeros, and both Bools are levels

```
C. release writes zeros immediately (the deadman)
   ok   all three Real requests read zero — 0.0, 0.0, 0.0

D. HmiTeleopRequest is a level, asserted and withdrawn (§10.4)
   ok   asserted — True
   ok   and still asserted half a second later with no operator action — a level, not an edge — True
   ok   withdrawn by writing FALSE — False
```

**Amended by `m4f-07b`, and the earlier form is superseded.** As first built, the
reset was momentary — one write cycle at `TRUE` whatever the operator did — and
check `E` measured exactly that: *"the pulse was observed TRUE on the server — 9
of 90 samples over 1.0 s"*, spanning one `HmiHeartbeat` value. It was not wrong
about what it measured, but it was the wrong contract. `HmiResetRequest` is a
**level** in `opcua-nodes.md` §10.4 and in `hmi/README.md`, and
`plc/forklift/SPEC.md` §11 T5.4 requires the operator to hold it unbroken across
the moment its cause disappears — which a page that shortened every press to one
cycle could not produce at all
(`docs/reports/m4f-08-commissioning-scenarios.md` finding 3). The check now reads,
from the re-run of the whole of pass A (`evidence/harness-2026-07-29-m4f07b-passA.log`,
**42 checks, no failures**):

```
E. HmiResetRequest is a LEVEL, carried for as long as it is held (§10.4)
   ok   held down, it reads TRUE on the server for the whole hold — 85 of 93 samples over 1.0 s
   ok   across 10 distinct heartbeat values, so it is being rewritten every cycle rather than pulsed once (H1) — a hold the PLC can observe across the moment a latch's cause disappears (SPEC §11 T5.4)
   ok   released, it reads FALSE again, so the PLC sees the node low between presses and can arm its edge per link session (§10.8 P6) — False
   ok   and a tap pressed and released inside one write cycle still lands one TRUE cycle — no operator press is dropped by this client — True
   ok   which then falls again by itself, because the button is no longer held — False
```

Ten distinct `HmiHeartbeat` values across a one-second hold is the level being
rewritten every cycle, which is H1 and not a special case for the reset. The last
two lines are the part that is easy to lose: `pointerdown` and `pointerup` can
both land inside one 100 ms write cycle, and an operator press that no cycle
carried is a press the PLC never had the chance to refuse. A single sticky flag,
cleared by the cycle that carried it, makes a tap land exactly one `TRUE` cycle —
the same behaviour the momentary implementation had, now as the floor of a level
rather than as the whole of it. **No timer is involved**, and nothing here waits
for a value to be stable: the flag is about this client's own input channel and
its own cycle (§10.1).

Because the node still reads `FALSE` between presses, the PLC can still clear
`ResetDeviceFault` and arm its edge inside the current link session (§10.8 P6).
The edge, the arming and the hold stay in the program; this client only carries
the operator's action, and it now carries it for as long as the operator makes
it.

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
`plc/forklift/double/` on port 4850. **Re-run unchanged under `m4f-07b` after the
reset became holdable and H6 landed** — again 33 checks, no failures
(`evidence/harness-2026-07-29-m4f07b-passB.log`), with the same `PageBeacon`
standing in for the browser's poll: *"the page beacon stood in for the browser's
5 Hz GET /state throughout — 23 polls (§10.8 H6)"*. The figures quoted in B.1–B.9
are from the original run.

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

**This section predates `m4f-07b`.** The RESET control it exercised was the
momentary one, and the page's markup and handlers have since changed (A.5,
section E). Re-running the browser pass against the held reset is carried in D as
not shown.

---

---

# D. What is deliberately not shown here

| Not shown | Why |
|---|---|
| Anything about the commissioned S7-1500 | Both harnesses refuse a non-loopback endpoint and `hmi/config.yaml` was never run. The live connection is the owner's, later |
| Anything about the TIA Portal build | Section B ran against `plc/forklift/double/`, a rehearsal stand-in. `opcua-nodes.md` §10 is a design value until the owner reads the `Forklift/` subtree back out of the tool (§10.2 step 6) |
| ~~A browser that crashes with the joystick held~~ **— closed by `m4f-07b`, section E** | This was the open item: the page returns the controls to rest on release, blur, hide and unload, but a hard crash left the last requests standing until the PLC's watchdog acted. §10.8 H6 ruled the window and E.2 demonstrates it — the page's own `GET /state` is the beacon, and at `UI_POLL_STALE_TIME` the backend returns every request to rest under a continuing heartbeat. It is a **process** reaction, not a safety function, and the machine is still stopped by the PLC. What is still not covered, and cannot be by any timer this layer runs, is an operator who walks away from a live browser: the poll keeps ticking and no window notices |
| The page's held RESET exercised in a real browser | Section C's browser pass predates `m4f-07b` and was not re-run: no browser was drivable from this session. The handlers were changed to the same press-and-hold shape the fork buttons already use, and E.4 demonstrates the whole of T5.4 through the endpoint the page posts to — but the DOM events themselves are unexercised since the change, and re-running section C against the held reset is the honest next step |
| Two writing clients being *enforced* apart | Per-client scoping is policy, not server enforcement, on a CPU running access control disabled and security `None` (ADR 0008 D2.5). A.1 shows this client keeping the policy; it does not show the server keeping it |
| A measured worst-case write period on the target machine | §10.8 P3 sets `HMI_STALE_TIME` at three worst-case write periods and says to re-derive it from a measurement if the HMI's worst case exceeds 200 ms. The p95 here is `100.90 ms`, well inside, but that is a WSL loopback figure against a double, not the commissioned cell |

---

# E. §10.8 H6 and the held reset — the two kernels of `m4f-07b`

`hmi/tools/check_hmi_h6_and_reset.py`, **34 checks, no failures**, against
`plc/forklift/double/server.py` on port 4850
(`evidence/harness-2026-07-29-m4f07b-h6reset.log`, run started `12:46:04` guest
local). The same three-role separation as section B, with one addition: the
harness also plays **the page**, including the page's own unconditional
`GET /state` at 5 Hz, which is what §10.8 H6 watches. Freezing that poll while
this harness and the HMI both keep running is what a crashed, frozen, closed or
disconnected browser looks like from inside the backend.

Nothing in this section is evidence about the TIA Portal build.

## E.1 The window, and where its number comes from

The backend prints the constant and its derivation at start-up, before anything
has happened:

```
2026-07-29 12:46:07,368 INFO    hmi operator-page window UI_POLL_STALE_TIME = 1000 ms (5 x the page's 200 ms GET /state); with no page talking, the five requests are held at rest and the heartbeat keeps running (§10.8 H6)
```

`UI_POLL_STALE_TIME` is `5.0 * UI_POLL_PERIOD_S` in code, beside its derivation,
and it is deliberately **not** a config key: the rule is the multiple, not the
millisecond, and a window that could be retuned in a YAML file would be a process
decision that had left this layer. It shares nothing with the PLC's
`HMI_STALE_TIME` — different party, different transport, different watcher
(§10.8 P4's principle one level up).

## E.2 K1 — the page dies while the backend stays alive

```
K1. §10.8 H6 — the page's poll stops while the BACKEND STAYS ALIVE
        before: HmiTractionRequest 0.600, HmiTeleopRequest True, page state LIVE, window 1000.0 ms = 200.0 ms poll x 5
   ok   all five requests went to rest 1063 ms after the page went quiet, against a 1000 ms UI_POLL_STALE_TIME — the enable included
        at rest on the server: HmiTractionRequest=0.000, HmiSteerRequest=0.000, HmiForkRequest=0.000, HmiTeleopRequest=False, HmiResetRequest=False
   ok   and the HEARTBEAT KEPT RUNNING across the drop — 17 -> 27 over 1.0 s. The process is healthy and keeps saying so; what is gone is the page
   ok   HmiLinkOk is still TRUE — the PLC was told nothing new (True)
   ok   NOTHING LATCHED: ForkliftResetRequired is FALSE, so no reset is owed for a page that went away (False)
   ok   the machine stopped anyway, and the PLC decided it from requests at rest — teleop False, refs 0.0, 0.0, 0.0
        page section as the backend renders it: {"state": "STALE", "age_ms": 2042.6, "last_request_utc": "2026-07-29T10:46:07.941+00:00", "requests": 9, "drops": 1, "last_drop_utc": "2026-07-29T10:46:08.984+00:00", "stale_after_ms": 1000.0, "poll_period_ms": 200.0, "teleop_armed": false, "reset_armed": false}
   ok   the backend is healthy and says so on the operator's own banner — session CONNECTED, page STALE after 2042.6 ms, drops 1
   ok   and both Bools are disarmed until the page is seen to send them low — teleop_armed False, reset_armed False
```

The backend's own log for the same instant, and it is the whole of what the
backend claims:

```
2026-07-29 12:46:08,984 WARNING hmi the operator's page has gone quiet (no request for 1043 ms, over the 1000 ms UI_POLL_STALE_TIME): all five requests to rest, the enable included. The write cycle and the heartbeat CONTINUE — this process is healthy, the page is not. Nothing latches; each Bool is carried again once the page has been seen to send it low (§10.8 H6).
```

The per-cycle record, from this session's own CSV
(`evidence/hmi-cycles-2026-07-29-m4f07b-h6reset-20260729T104607Z-pid101915.csv`,
seven of fifteen columns shown):

```
cycle,hb_value,HmiTractionRequest,HmiTeleopRequest,HmiResetRequest,page_state,page_age_ms
14,14,0.6,True,False,LIVE,744.2
15,15,0.6,True,False,LIVE,843.4
16,16,0.6,True,False,LIVE,945.0
17,17,0.0,False,False,STALE,1044.0
18,18,0.0,False,False,STALE,1143.1
19,19,0.0,False,False,STALE,1243.5
20,20,0.0,False,False,STALE,1343.8
```

Three things are visible in those seven rows and they are the whole of H6's
shape. The requests go to rest in the first cycle whose measured age exceeds the
window — one cycle of latency on a 100 ms cycle, not a second timer. `hb_value`
keeps incrementing straight through, 16 → 17 → 18: **the counter does not stop**,
because stopping it would say "the HMI is gone", which is false, and would buy the
PLC's heavier reaction — `HmiLinkOk` `FALSE`, `ForkliftResetRequired` latched, a
monitored reset owed before teleop could return. A page that had merely been
backgrounded would then cost a reset. And the PLC is told nothing new: it reads
requests at rest under a live heartbeat, a state §10.6 already handles in one
assignment, which is why `ForkliftResetRequired` stayed `FALSE` throughout.

The machine still stopped. **The PLC stopped it**, from requests at rest, exactly
as it does when the operator lets go of the stick. Nothing in this layer stopped
anything, and nothing in this layer is a safety device: this is invariant 2's
degraded-mode pattern at the operator boundary, and it is process behaviour, not
a safety function (invariant 1, ADR 0008 D3).

## E.3 K1r — recovery is a release, never a resume

```
K1r. recovery is a RELEASE, not a resume
   ok   the three Reals are carried again on the page's very first post — HmiTractionRequest 0.30000001192092896
   ok   but NEITHER Bool is, even though the page posted both TRUE — a page that thaws with the enable still asserted must not produce a rising edge no operator made — teleop False, reset False
   ok   once the page had been seen to send it low, the reset is carried again — True
   ok   and so is the enable — True
   ok   teleop returned with NO monitored reset demanded of the operator: nothing had latched, so nothing had to be cleared
        page section now: {"state": "LIVE", "age_ms": 104.1, "last_request_utc": "2026-07-29T10:46:11.980+00:00", "requests": 25, "drops": 1, "last_drop_utc": "2026-07-29T10:46:08.984+00:00", "stale_after_ms": 1000.0, "poll_period_ms": 200.0, "teleop_armed": true, "reset_armed": true}
```

The page in this step thaws with **both Bools still asserted** — the worst case
the rule exists for — and posts them high in its very first message. The three
Reals are carried at once, because they move nothing while
`ForkliftTeleopActive` is `FALSE`. The two Bools are not, because the PLC cannot
tell a `FALSE → TRUE` produced by a thawing page from one produced by an
operator's hand (§10.7). Each is carried again only after that page has been seen
to send *that* Bool low: P6's per-link-session arming, applied to this client's
own input channel.

In the ordinary case it costs nothing, and the page is built so that it does: it
already returns everything to rest on blur, on hide and on unload, and it now also
does so the moment the backend tells it that its requests were dropped — so a page
coming back from the background has sent both low before it is asked to. The
`drops` counter and the two arming flags survive the recovery and are rendered on
the page, which is how a page that returns learns why its controls were dropped
(§10.12 item 8).

## E.4 K2 — `SPEC.md` §11 T5.4, run entirely from the operator's endpoint

`docs/reports/m4f-08-commissioning-scenarios.md` finding 3: *"The HMI's reset
cannot be held from its page — one click is one write cycle, while §11 5.4.4–5.4.7
need it standing across the moment the zone clears."* Steps 5.4.1 to 5.4.9, in
order, with nothing but posts to `/control` and the page's own poll:

```
K2. SPEC §11 T5.4 5.4.2-5.4.9 — the reset HELD across the zone clearing
   ok   5.4.1 driving at a steady traction demand — ref 0.60 m/s
   ok   5.4.2 ForkliftObstacleStopActive latched
   ok   teleop dropped, all three refs 0.0, ForkliftResetRequired TRUE — 0.0, 0.0, 0.0
   ok   while HmiTractionRequest is STILL STANDING at 0.6000000238418579 — the latch overrides a live command
        5.4.3 holding the traction control for 10 s, posting NOTHING — the page's GET /state poll is the only traffic, and it is what keeps the request carried (§10.8 H6)
   ok   after 10 s of silence the demand still stands at 0.6000000238418579 and the ref is still 0.0 — nothing resumed and nothing crept
   ok   5.4.4 HmiResetRequest reads TRUE on the server in 20 of 20 samples over 1.0 s — the reset is HELD, which is what m4f-08 finding 3 said the page could not produce
   ok   and it is REFUSED while the obstacle is still in the zone: ForkliftObstacleStopActive True, ForkliftResetRequired True — causeGone is false on C3
   ok   5.4.5 the enable is refused while a latch stands, so the machine cannot drive itself clear — ForkliftTeleopActive False — and the reset stayed asserted across both posts (True), so the hold is unbroken
   ok   5.4.6 the zone cleared with the reset STILL ASSERTED — zone False, HmiResetRequest True
   ok   and the latch STANDS: the field clearing does not release it, and the still-asserted reset supplies no edge — the edge it did produce happened while the cause was still standing
        5.4.7 stuck reset: 10 more seconds with the zone clear and the button still down
   ok   the latch NEVER clears for as long as it is held — HmiResetRequest True, ForkliftObstacleStopActive True, ForkliftResetRequired True. No elapsed time makes an edge appear
   ok   5.4.8 released — HmiResetRequest reads FALSE on the server
   ok   and on that FRESH rising edge every latch clears — ForkliftResetRequired FALSE
   ok   ForkliftObstacleStopActive cleared with it — False
   ok   and NOTHING MOVED: teleop is still FALSE though the enable has been asserted throughout, because a level that never fell produces no edge — ref 0.0
   ok   5.4.9 released and re-asserted, the enable produces a real edge, teleop returns and the refs follow the operator again — 0.60 m/s
```

Both ten-second holds are the spec's, not compressed. The 5.4.4 hold is **one
post**: from it until the release at 5.4.8 the backend rewrites the level every
cycle on its own, and the twenty consecutive `TRUE` samples over a second are the
server's answer, read from this harness's independent session.

Two properties of this run are worth naming because they are easy to miss.

- **5.4.3 posts nothing for ten seconds and the demand still stands.** The only
  traffic in that window is the page's `GET /state`. That is precisely why H6
  watches the poll and not the posts: an operator holding a control makes no
  further input, and a window over `/control` would have dropped a demand the
  operator was still making. The 5.4.7 hold is the same shape.
- **The two kernels do not interfere.** A reset held for twenty seconds across
  the clearing of the zone runs under a live H6 window throughout, and the window
  never fires, because the page is still there. The reset that H6 *does* drop, in
  K1, is dropped as part of the deadman and re-armed by release, not by time.

## E.5 What the PLC never learned

`HmiLinkOk` stayed `TRUE` through K1, and `ForkliftResetRequired` stayed `FALSE`.
The PLC ran no new code for any of this and needs none: H6 adds **no node, no
start value and no PLC expectation**, which is what makes it a rule the interface
could take while the group is being commissioned (§10.8). The heavier failure —
the whole process gone — is still caught faster, by the PLC, in 600 ms, and still
latches; B.8 is that case and it is unchanged, measured again in the pass B re-run
at *"HmiLinkOk went FALSE 597 ms after the HMI stopped"*. The two reactions are
proportional on purpose.
