# EVIDENCE_HMI — the commissioning HMI against two doubles

Briefs `docs/briefs/m4f-07-hmi-backend-ui.md` (sections A–D),
`docs/briefs/m4f-07b-h6-and-holdable-reset.md` (section E, and the two amendments
marked as such in A.5 and D), and `docs/briefs/m4f-07c-s7-write-compat.md`
(section F). Every figure below is quoted as the harness or the process printed
it; nothing here is arithmetic done while writing.

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

> **Revisited 2026-07-31 — section H.** Screenshots are now committed, for a
> reason this section did not have: the page is about to be rewritten as HMI v2,
> and the owner asked for a picture of what v2 inherits. Both halves of the
> objection above are answered rather than dropped — the images are reproducible
> because the script that presses the buttons is committed beside them
> (`tools/capture_screens.mjs`), and they still age against the markup, which is
> why section H states plainly that they are **baseline documentation, not
> evidence and not a gate claim**. The figures in this section remain the
> evidence for what this section claims.

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
| ~~The page's held RESET exercised in a real browser~~ **— closed by section H (H.2)** | Section C's browser pass predated `m4f-07b` and was not re-run: no browser was drivable from that session. The handlers were changed to the same press-and-hold shape the fork buttons already use, and E.4 demonstrated the whole of T5.4 through the endpoint the page posts to — but the DOM events themselves were unexercised since the change. Section H presses the button with real pointer events on 2026-07-31 and records `HmiResetRequest true` while it is held |
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

---

# F. S7-compatible writes — the `m4f-07c` DataValue fix

Brief `docs/briefs/m4f-07c-s7-write-compat.md`. First contact with the real CPU
(2026-07-29) refused every write this backend made:

```
BadWriteNotSupported: The server does not support writing the combination of
value, status and timestamps provided.
```

— session established (6 writable, 12 read-only resolved), first write refused,
deadman fired correctly, reconnect loop correct. Neither double below has ever
raised this: **the double accepts both the pre-fix and post-fix DataValue, so a
harness pass proves the write path is unchanged in every other respect, not that
the real S7-1500 accepts the new form.** That contact is the orchestrator's,
against the endpoint in `hmi/config.yaml`, after this fix is committed. Nothing
in this section is evidence about it.

## F.1 The defect, isolated

`HmiClient._write` built its call as `self.client.write_values(nodes, variants)`,
handing `asyncua`'s `Client.write_values` a bare `ua.Variant` per node.
`write_values` runs every item that is not already a `ua.DataValue` through
`asyncua.common.ua_utils.value_to_datavalue`, which stamps
`SourceTimestamp=datetime.now(timezone.utc)` onto it. `bridge/amr_bridge/opcua_side.py`'s
`PlcClient._write` (read-only reference, not imported) never reaches that branch:
it builds the `ua.DataValue` itself — `ua.DataValue(ua.Variant(value, variant_type))`
— and `value_to_datavalue` returns an already-built `DataValue` UNCHANGED
(`isinstance(val, ua.DataValue)` short-circuits before the timestamp branch). That
is the whole of the difference, confirmed against the installed library rather
than assumed: both forms of the *same* value, serialised with
`asyncua.ua.ua_binary.struct_to_binary` and read back as a wire encoding-mask byte
(venv `/home/ozkan/amr-hmi-venv`, asyncua `2.0.1`, `hmi_server` imported directly
so the post-fix line is the shipped code, not a hand-typed copy of it):

```
post-fix HmiClient._write DataValue for HmiTractionRequest = 0.62
  StatusCode=StatusCode(value=0) SourceTimestamp=None ServerTimestamp=None
  encoding_mask_byte=0b00000011 (0x03)  raw=030a52b81e3f00000000

pre-fix path -- value_to_datavalue() on the same bare Variant (what
write_values(nodes, variants) did internally):
  StatusCode=StatusCode(value=0) SourceTimestamp=datetime.datetime(2026, 7, 29, 16, 40, 4, 821688, tzinfo=datetime.timezone.utc) ServerTimestamp=None
  encoding_mask_byte=0b00000111 (0x07)  raw=070a52b81e3f0000000030eb7fe8781fdd01
```

Bit 2 of the mask (`SourceTimestamp` present) is the only difference between the
two, and a client-supplied source timestamp is exactly what the live failure's
"value, status **and** timestamps" wording names.

## F.2 The fix

`HmiClient._write` now builds one `ua.DataValue` per node before handing the list
to `write_values` — `ua.DataValue(ua.Variant(values[name], WRITE_VARIANT[name]))`
in place of the bare `ua.Variant(...)`. This is still the single write helper
`hmi/README.md` and A.1 describe: `_writable` (which node) and `_write` (how it
is written) remain the one choke point every one of the six nodes passes through,
split into the same two calls per cycle as before — the five requests, then the
heartbeat. Nothing else in `hmi_server.py` changed; there is no second write path
to change.

## F.3 A wire-level fact worth stating precisely

`ua.DataValue`'s `StatusCode` field defaults to `StatusCode()` (Good) through a
dataclass `default_factory`, not to `None`. Passing only a `Variant` into
`DataValue(...)` — this fix, and the bridge pattern it mirrors — therefore still
asserts `StatusCode` present on the wire (mask bit 1, `raw=03…` above), alongside
`Value`. Only `SourceTimestamp` and `ServerTimestamp` are actually absent. The
bridge's identical construction has written to the commissioned CPU since M3
carrying that same Good `StatusCode`, so a default Good status is evidently not
what the CPU's `BadWriteNotSupported` names; the failure text is the OPC UA
specification's fixed wording for the status code and does not itself say which
of "value, status and timestamps" was the one this CPU objected to. This fix
reproduces the bridge's exact, already-proven wire form (mask `0x03`) rather than
the stricter all-`None` form (`StatusCode=None` too, mask `0x01`) a literal
reading of "no StatusCode" would imply — the stricter form has never been written
to the real CPU and this brief forbids contacting it to find out. Flagged for the
orchestrator rather than silently narrowed or silently widened.

## F.4 Both existing kernel harnesses, re-run against a fresh double instance

Neither harness contacted PLCSIM Advanced or the commissioned CPU; both refuse a
non-loopback endpoint outright, and `hmi/config.yaml` was not run. Own ports —
4897 and 8189 for pass A, 4898 and 8190 for pass B — checked clear with `ss -ltn`
immediately before each double started and confirmed clear again after both
processes had exited, distinct from every port either double has ever used
before (4840 PLCSIM, 4842–4846 the bridge's, 4847 and 4850 the earlier HMI
evidence's own).

| Item | Value |
|---|---|
| Date | 2026-07-29. Pass A started `18:36:28`, pass B `18:37:39`, guest local (UTC+2) |
| Host | WSL2 Ubuntu 24.04.4 LTS, `/mnt/c` checkout, headless |
| venv | `/home/ozkan/amr-hmi-venv`, unchanged since the original evidence — plain venv, not `--system-site-packages` |
| Python | `3.12.3` |
| asyncua | `2.0.1`, both venvs |
| Pass A server | `bridge/test_double/plc_test_double.py`, own instance, `opc.tcp://127.0.0.1:4897/amr-agent/celldouble/` |
| Pass B server | `plc/forklift/double/server.py --port 4898`, own instance, `opc.tcp://127.0.0.1:4898/` |
| Configs | scratch copies of `hmi/config-double.yaml` / `hmi/config-logic-double.yaml` with only the endpoint and HTTP ports changed; not committed, kept outside the repository |
| Raw evidence | `evidence/harness-2026-07-29-m4f07c-passA.log`, `evidence/harness-2026-07-29-m4f07c-passB.log`, `evidence/hmi-cycles-2026-07-29-m4f07c-passA-20260729T163628Z-pid116112.csv`, `evidence/hmi-cycles-2026-07-29-m4f07c-passB-20260729T163739Z-pid116383.csv` — present in the working tree; not part of this fix's commit |

**Pass A**, `hmi/tools/check_hmi_writes.py` against the bridge test double — the
harness's own summary line:

```
no failures
```

42 `ok` lines appear in this run's transcript against 0 `FAIL` (the harness
prints no total, so this is a hand count of the transcript, done because a
number is being stated at all, not read off the tool — `docs/LESSONS.md`
2026-07-27). Every check from A's original run (§A) reappears with the same
verdicts against the S7-compatible write path: the allowlist refusal (J), every
node written every cycle regardless of change including the repair-after-overwrite
(A), both Bools as levels including the held reset and the sub-cycle tap (D, E),
the heartbeat advancing every cycle (F), session loss and regain with the counter
surviving the reconnect (G), both stop paths (H, I), and the six-and-only-six
write-set check (K). From this run's own CSV:

```
hmi/evidence/hmi-cycles-2026-07-29-m4f07c-passA-20260729T163628Z-pid116112.csv
  cycles n=78  write RTT median 1.050 ms  p95 1.459 ms  max 1.916 ms
  cycle period median 100.10 ms  p95 100.94 ms  max 4121.60 ms
  heartbeat 1 -> 78, distinct consecutive changes 77 of 77 intervals
```

77 of 77 — the counter changed at every cycle boundary in the file, unaffected by
carrying a `DataValue` instead of a bare `Variant`. The `max 4121.60 ms` period is
check G's own reconnect gap, the same shape §A.4 recorded before.

**Pass B**, `hmi/tools/check_hmi_teleop_loop.py` against the PLC logic double —
the same `no failures` summary line, 33 `ok` lines in this run's transcript
against 0 `FAIL`. Every check from B's original run (§B) reappears: the boot
polarity of the link verdict (P0), the monitored reset clearing latches and
energising nothing (P1), the enable's own edge (P2), the joystick reaching the
plant only through PLC logic (P3), the fork-height speed cap (P4), the obstacle
latch overriding a live command (P5, P6), the release-and-reassert conflation
(P7), the fork jog (P8), and the HMI watchdog's controlled stop (P9) — this time
at `HmiLinkOk went FALSE 607 ms after the HMI stopped`, inside the same `T#600ms`
stale window B.8 (`650 ms`) and the `m4f-07b` re-run (`597 ms`) also measured.
From this run's own CSV:

```
hmi/evidence/hmi-cycles-2026-07-29-m4f07c-passB-20260729T163739Z-pid116383.csv
  cycles n=47  write RTT median 0.925 ms  p95 1.308 ms  max 1.447 ms
  cycle period median 100.00 ms  p95 100.70 ms  max 101.00 ms
  heartbeat 1 -> 47, distinct consecutive changes 46 of 46 intervals
```

46 of 46 again.

## F.5 What is deliberately not shown here

Same as §D, restated for this fix specifically: nothing here is evidence that the
commissioned S7-1500 accepts the new write form. Both doubles accepted the old,
timestamped `DataValue` just as readily as the new one throughout the original
evidence (§A–E) and this re-run — the defect this brief fixes is invisible to
either double and was found only on first contact with the real CPU. F.1's
byte-level comparison is what stands in its place until that contact is made.

---

# G. `Forklift/Safety/` mirrors — lamps, banner and graceful degradation

Brief `docs/briefs/m5a-07-hmi-safety-lamps.md`. Adds the four §11 mirror nodes
to the 5 Hz status poll, a SAFETY DEMAND banner distinct from the process-stop
banner, four lamps, and one line stating the panel displays and never
commands. **Zero new writes**: `HMI_WRITABLE_PATHS`, `WRITE_VARIANT` and
`REQUEST_ORDER` are byte-for-byte unchanged, and `validate_config` still
refuses any configuration whose write set is not exactly the six existing
HMI-writable nodes — the four mirrors were never candidates for that set and
no code path in this file can write them.

**This section's environment differs from A–F, and that is stated rather than
discovered**: it runs on the machine's native Windows, not WSL2 (LESSONS
2026-07-27, "evidence is qualified by the environment that produced it").
Neither `bridge/test_double/plc_test_double.py` nor `plc/forklift/double/
server.py` serves `Forklift/Safety/` yet — `opcua-nodes.md` §11 landed
2026-07-29, after both were written — so this section runs against a new,
minimal double this layer owns, `hmi/tools/safety_mirror_double.py`, imported
directly by `hmi/tools/check_hmi_safety_mirrors.py` (no subprocess, no IPC:
the harness holds the mirror `Node` objects and moves them server-side, which
is the only way to move them at all, since no client — including this
harness — is ever granted a write on them). Own port throughout: `4860`,
distinct from every port this project has used before (4840 PLCSIM, 4842–4846
the bridge's, 4847 and 4850 the earlier HMI evidence's own, 4897/4898 the
`m4f-07c` re-run). Neither PLCSIM Advanced nor the commissioned CPU was
contacted.

| Item | Value |
|---|---|
| Date | **2026-07-29** |
| Host | native Windows 11, this checkout, no WSL involved |
| venv | plain venv (not `--system-site-packages`), created fresh for this section |
| Python | 3.13.2 |
| asyncua | `2.0.1`, the version `bridge/requirements.txt` pins |
| Dependencies | `asyncua` and the standard library; `python -c "import rclpy"` answers `ModuleNotFoundError: No module named 'rclpy'` |
| Double | `hmi/tools/safety_mirror_double.py`, own port `4860`; a dumb address space, no program, exactly the standing `bridge/test_double/` already documents of itself |
| Harness | `hmi/tools/check_hmi_safety_mirrors.py --mode absent` and `--mode present` |
| Config | `hmi/config-safety-mirror-double.yaml`, HTTP port `8093` |
| Raw evidence | `evidence/harness-2026-07-29-m5a07-absent.log`, `evidence/harness-2026-07-29-m5a07-present.log`, `evidence/hmi-2026-07-29-m5a07-absent.log`, `evidence/hmi-2026-07-29-m5a07-present.log`, `evidence/hmi-cycles-2026-07-29-m5a07-present-20260729T173633Z-pid19556.csv` |

## G.1 Absent — the connection is unaffected, the panel greys

`check_hmi_safety_mirrors.py --mode absent`, **no failures**. The double serves
the required `Forklift/` groups and nothing under `Safety/` — the fallback
ADR 0009 D4 describes and §11.6 rules on:

```
N1. the HMI connects to a server WITHOUT Forklift/Safety/
   ok   the HMI reached CONNECTED against a server missing the optional group — the group's absence is not a connect failure (§11.6)
   ok   the panel's own data shows present=false — {'present': False, 'EStopDemand': None, 'ZoneStopDemand': None, 'SafetyResetRequired': None, 'SafetyResetFault': None}
   ok   and all four mirror values read null, never a guessed value — {'present': False, 'EStopDemand': None, 'ZoneStopDemand': None, 'SafetyResetRequired': None, 'SafetyResetFault': None}

N2. the connection STAYS up — absence is not retried as a failure
   ok   still CONNECTED 2 s later — no reconnect loop over the missing group
   ok   and still reports not present — {'present': False, 'EStopDemand': None, 'ZoneStopDemand': None, 'SafetyResetRequired': None, 'SafetyResetFault': None}

N3. the REQUIRED reads are unaffected by the optional group's absence
   ok   Forklift/Status/ and Forklift/Link/HmiLinkOk still resolved and are on the panel — ['ForkliftTeleopActive', 'HmiLinkOk']

N4. the served page's own markup carries the label even though this server has nothing to show yet
   ok   the page's markup contains a 'not present' state for the group
   ok   and the exact required banner label is present in the markup — static markup, not conditioned on any one server
```

The backend's own log names the mechanism, not just the outcome:

```
2026-07-29 19:34:06,249 INFO    hmi optional group Forklift/Safety/ not present on this server (The requested operation has no match to return.(BadNoMatch)) — shown to the operator as 'not present', never as a value; this is not a connect failure (opcua-nodes.md §11.6)
2026-07-29 19:34:06,251 INFO    hmi session established with opc.tcp://127.0.0.1:4860/amr-agent/safetymirrordouble/ — 6 writable node(s), 12 read-only node(s); browse prefix 2:ServerInterfaces/3:DemoCell
```

`BadNoMatch` is `translate_browsepaths_to_nodeids`'s answer to a browse path
with no match at the server — confirmed against the installed library before
being relied on (a throwaway probe server, one resolvable child and one
absent, read back as `asyncua.ua.uaerrors.BadNoMatch`, a subclass of
`ua.uaerrors.UaStatusCodeError`). `_connect`'s optional-group loop catches
exactly that base class, so it also catches whatever more specific subclass a
different server reports for the same condition. **12 read-only nodes**, not
16: the four mirrors were never added to `self._read_nodes`, so `_poll_metrics`
never reads them and never reports a guessed value for them — `present=false`
and four `None`s, matching the harness's own reading of `/state` above exactly.

Both this run's log and G.2's carry a "the operator's page has gone quiet"
WARNING once the harness stops actively polling `/state` between checks: this
harness checks a condition and moves on rather than running the continuous
`PageBeacon` `check_hmi_teleop_loop.py` and `check_hmi_h6_and_reset.py` use,
because this section is about §11's read-only mirrors, not about §10.8 H6.
The five write requests and the enable going to rest is exactly what H6
promises and is outside this section's scope; nothing above depends on them,
and the session stays `CONNECTED` with the heartbeat advancing straight
through it either way.

## G.2 Present — the fail-safe start values, and each lamp moves on its own

`check_hmi_safety_mirrors.py --mode present`, **no failures**. The same
double, `--with-safety-mirrors`, serving the group at its §11.6 start values:

```
P0. the HMI connects to a server WITH Forklift/Safety/
   ok   the HMI reached CONNECTED against a server carrying the group

P1. the fail-safe start values, read back through the HMI's own /state
   ok   present=true — {'present': True, 'EStopDemand': True, 'ZoneStopDemand': True, 'SafetyResetRequired': True, 'SafetyResetFault': False}
   ok   EStopDemand/ZoneStopDemand/SafetyResetRequired all True, SafetyResetFault False — matches opcua-nodes.md §11.6 exactly — {'present': True, 'EStopDemand': True, 'ZoneStopDemand': True, 'SafetyResetRequired': True, 'SafetyResetFault': False}
```

and the session log confirms **16** read-only nodes this time — the 12 of
G.1 plus the four mirrors:

```
2026-07-29 19:36:33,760 INFO    hmi session established with opc.tcp://127.0.0.1:4860/amr-agent/safetymirrordouble/ — 6 writable node(s), 16 read-only node(s); browse prefix 2:ServerInterfaces/3:DemoCell
```

Each mirror was then driven through its own transition, independently, with
the other three left untouched at every step:

```
P2. SafetyResetFault moves on its own — a device diagnosis, not a demand
   ok   the HMI's own /state shows SafetyResetFault True — {'present': True, 'EStopDemand': True, 'ZoneStopDemand': True, 'SafetyResetRequired': True, 'SafetyResetFault': True}
   ok   while SafetyResetRequired is UNCHANGED at True — the two lamps are independent nodes, not derived from one another — {'present': True, 'EStopDemand': True, 'ZoneStopDemand': True, 'SafetyResetRequired': True, 'SafetyResetFault': True}
   ok   and back to False — {'present': True, 'EStopDemand': True, 'ZoneStopDemand': True, 'SafetyResetRequired': True, 'SafetyResetFault': False}

P3. EStopDemand and ZoneStopDemand clear independently
   ok   EStopDemand False on the HMI's own /state — {'present': True, 'EStopDemand': False, 'ZoneStopDemand': True, 'SafetyResetRequired': True, 'SafetyResetFault': False}
   ok   while ZoneStopDemand and SafetyResetRequired are UNCHANGED — {'present': True, 'EStopDemand': False, 'ZoneStopDemand': True, 'SafetyResetRequired': True, 'SafetyResetFault': False}
   ok   ZoneStopDemand False on the HMI's own /state — {'present': True, 'EStopDemand': False, 'ZoneStopDemand': False, 'SafetyResetRequired': True, 'SafetyResetFault': False}
   ok   while SafetyResetRequired is STILL True — this client does not derive it from the other two, it only displays the server's own node (invariant 10) — {'present': True, 'EStopDemand': False, 'ZoneStopDemand': False, 'SafetyResetRequired': True, 'SafetyResetFault': False}

P4. the banner tracks SafetyResetRequired ALONE
   ok   SafetyResetRequired False — {'present': True, 'EStopDemand': False, 'ZoneStopDemand': False, 'SafetyResetRequired': False, 'SafetyResetFault': False}
   ok   ZoneStopDemand True again while SafetyResetRequired STAYS False — the banner's trigger is not ZoneStopDemand or EStopDemand directly — {'present': True, 'EStopDemand': False, 'ZoneStopDemand': True, 'SafetyResetRequired': False, 'SafetyResetFault': False}
   ok   SafetyResetRequired True again — {'present': True, 'EStopDemand': False, 'ZoneStopDemand': True, 'SafetyResetRequired': True, 'SafetyResetFault': False}
```

P4's middle step is the one that actually rules out a wrong wiring: raising
`ZoneStopDemand` back to `True` while `SafetyResetRequired` stays `False`
would light a banner keyed on `ZoneStopDemand` (or on any combination this
client formed itself) and would not light one keyed on `SafetyResetRequired`
alone. It stayed off. `static/index.html`'s `renderSafety` reads
`safety.SafetyResetRequired` and nothing else to decide the banner — confirmed
by inspection of the shipped file, not re-typed here.

This double holds no F-program: every value above is exactly what the harness
wrote server-side, the same honest limitation section A records for
`bridge/test_double/`'s `Forklift/Status/*`. Nothing here is evidence that a
real F-runtime group forms `SafetyResetRequired` as the OR of the other two —
that is `plc/forklift-safety/SPEC.md` §6's claim, unchanged by this section.

## G.3 The served page's own markup

```
   ok   the exact required banner label is in the served markup
   ok   a 'displays ... never commands' statement is in the served markup
   ok   the word 'obstacle' does not appear near the new ZoneStopDemand lamp's own markup (MR7)
   ok   and 'ZoneStopDemand' does not appear near the EXISTING obstacle lamp's markup either — the separation holds from both sides
   ok   and the existing process-stop lamp's markup carries no 'safety demand' wording — the two banners share no sentence
```

The label is `hmi/static/index.html`'s literal text, `F-CPU safety demand
(mirror, read-only)`, inside a banner (`#safetybanner`) that is a different
element from the process-stop banner (`#stopbanner`): a different background
(`--safety: #8b5cf6`, a violet, against the process-stop banner's `--stop`
red), a different border style (`double` against `solid`), its own heading
(`SAFETY DEMAND` against `PROCESS STOP LATCHED`), and its own `.fine` line.
The one-line statement is the safety section's own `.note` paragraph:
*"This panel displays the F-CPU's mirrored state; it never commands. No write
from this HMI reaches these nodes, and no client write anywhere can create,
prevent or clear a safety reaction."* MR7 is checked from both directions
rather than asserted: the word `obstacle` is absent for 300 characters around
`ZoneStopDemand`'s own lamp markup, `ZoneStopDemand` is absent for 300
characters around the *existing* `ForkliftObstacleInStopZone` lamp's, and
`safety demand` is absent near `ForkliftObstacleStopActive`'s — three
independent checks for the one rule MR7 states (`TWIN-DEMO-MAP.md` R4;
`plc/forklift-safety/SPEC.md` §1.3).

## G.4 A client write against the four is refused, on this double too

```
P5. a client write against the four is refused (§11.4 MR1), on this double too
   ok   a client write against Forklift/Safety/EStopDemand was refused — BadUserAccessDenied: User does not have permission to perform the requested operation.(BadUserAccessDenied) — this double keeps §11.4 MR1 even though it is only test scaffolding
```

`safety_mirror_double.py` never calls `set_writable(True)` on any of the four
— the same per-tag mechanism `plc/forklift/double/server.py` uses for
`Forklift/Output/*` and `Forklift/Status/*` — so a defect that tried to write
one is refused by this double exactly as §11.3's DB table says a real server
refuses it. This is not evidence about the commissioned CPU's access rights,
which remain a design value until read back out of the tool (§11.5 step 6);
it is evidence that this brief's own instrument does not misrepresent the
group it is standing in for.

## G.5 Per-cycle figures, present-mode run

```
hmi-cycles-2026-07-29-m5a07-present-20260729T173633Z-pid19556.csv
  cycles n=41  write RTT median 1.477 ms  p95 2.237 ms  max 2.511 ms
  cycle period median 94.40 ms  p95 109.42 ms  max 115.40 ms
  heartbeat 1 -> 41, distinct consecutive changes 40 of 40 intervals
```

40 of 40 — the write cycle and the heartbeat ran exactly as they do without
this section's changes; the §11 poll adds no timer of its own and none is
visible here. **On Windows, `subprocess.Popen.terminate()` calls
`TerminateProcess()`, which the target process cannot catch** — unlike WSL2's
POSIX `SIGTERM`, which `hmi_server.py`'s signal handler intercepts and answers
with §10.8 H5's clean-shutdown line. Neither run in this section exercises
that path or the final evidence flush it triggers; the harness instead waits
2.5 s — one `Evidence.row()` flush period — before stopping the process, so
the CSV above is real per-cycle data written by the ordinary periodic flush,
never by clean shutdown. Nothing about H5 is exercised or claimed by this
section, and `hmi_server.py` is unchanged by this finding — it is recorded
here because it is the first time this layer's evidence has been produced
outside WSL2 (LESSONS 2026-07-27).

## G.6 What is deliberately not shown here

| Not shown | Why |
|---|---|
| ~~A live-browser, DOM-rendered confirmation of the grey "not present" styling or the violet banner's visual distinctiveness~~ **— captured in section H (H.4, H.10, H.11)** | Verified two other ways at the time: the data contract (`/state`'s `safety` section, G.1–G.2) and the served markup (G.3) — no browser automation was available to that session. A browser was available on 2026-07-31 and both states are now recorded as images |
| Anything about the commissioned S7-1500 or PLCSIM Advanced | Neither was contacted; both harness modes refuse a non-loopback `--hmi` outright and `hmi/config.yaml` was not run |
| A real F-runtime group forming `SafetyResetRequired` as the OR of the other two | `safety_mirror_double.py` holds no F-program; every mirror value in G.2 is exactly what the harness wrote. That claim is `plc/forklift-safety/SPEC.md` §6's, verified against the F-runtime group directly, not through this HMI |
| §10.8 H5's clean-shutdown path, on this platform | See G.5 — this section's own subprocess stops are hard kills, not caught signals; both the absent- and present-mode HMI logs end without a "shutting down cleanly" line |
| Whether the auto-published `DataBlocksGlobal` path also refuses a write for this group | §11.4's caveat and §9.8's open item; unrelated to this double, which has no such path at all |

---

# H. The M4 page, photographed — baseline before HMI v2

**This section is baseline documentation, not evidence for a gate criterion and
not a claim about anything.** It records what the M4 commissioning page looks
like and how it behaves, in a real browser engine, as it stands *before* the
HMI v2 work of the current gate changes it. Every state below was produced by a
double on loopback; no PLC and no F-CPU exist in any of it.

Sections A–G are still the evidence. An image ages against the markup in a way a
quoted figure does not, so each screenshot is committed together with the DOM
readout the page was showing at the instant of capture — the numbers, not the
picture, are what can be checked later.

| Item | Value |
|---|---|
| Date | **2026-07-31**. One capture run, UTC: pass 1 images written `07:36:56`–`07:37:12`, pass 2 images `07:37:19` (file timestamps) |
| Host | Linux container, Ubuntu 24.04.4, kernel `6.18.5`, headless. **Not WSL2** — sections A–G were produced on the owner's WSL2 machine, and evidence is qualified by the environment that produced it (LESSONS 2026-07-27) |
| venv | `/home/user/amr-hmi-venv`, `python3.12 -m venv` — **plain venv, deliberately not `--system-site-packages`**; `python -c 'import rclpy'` answers `ModuleNotFoundError: No module named 'rclpy'` |
| Python | `3.12.3 (main, Mar  3 2026, 12:15:18) [GCC 13.3.0]` |
| asyncua | `2.0.1`, the pin in `bridge/requirements.txt` |
| Browser | Chromium `141.0.7390.37`, driven headless by Playwright (Node). Both are environment tooling: **nothing in `hmi/` imports either**, and the HMI itself is unchanged by this section |
| Pass 1 server | `plc/forklift/double/server.py` on **4850**, the PLC layer's logic double, with `hmi/config-logic-double.yaml` (HTTP 8090). Images 01–09 |
| Pass 2 server | `hmi/tools/safety_mirror_double.py --with-safety-mirrors` on **4860**, with `hmi/config-safety-mirror-double.yaml` (HTTP 8093). Images 10–11 |
| Instruments | `hmi/tools/capture_screens.mjs` (drives the browser, spawns and stops every process) and `hmi/tools/screens_plant_driver.py` (plays the bridge and the plant: it writes the four `Forklift/Input/` nodes and `DemoCell/Link/BridgeHeartbeat`, and never a `Forklift/Hmi/` node) |
| Images | `evidence/hmi-page-01…11-*-2026-07-31.png`, 1680 px wide, full page |
| Raw evidence | `evidence/capture-2026-07-31-m5-13a.log` — the capture run's own output, including the DOM readout printed immediately before each screenshot and every browser console message. Every figure quoted below is a value from that log or text visible in the image it describes |

The three roles of section B are unchanged, with the browser in the operator's
place: the plant driver plays the bridge and the plant, the page plays the
operator, and the double plays the PLC and owns every verdict. Nothing here is
evidence about the TIA Portal build.

Every process had stopped before the images were read: `ss -ltn` reported **no
listeners on 4850/4860/8090/8093** afterwards (LESSONS 2026-07-28 — a session is
ended by observation, never by assumption).

## H.1 `hmi-page-01-reset-required-2026-07-31.png` — the page at boot

Logic double, nothing touched yet. The amber **RESET REQUIRED** banner, the
`ForkliftResetRequired` lamp, and the reset-sequence hint beside the buttons. The
latch is the double's own start state (`ForkliftObstacleInStopZone` starts
`TRUE`, `plc/forklift/double/logic.py`), formed before the operator arrived —
which is exactly the boot behaviour CLAUDE.md §9 asks for: the machine does not
resume by itself.

```
{ "linkstate": "CONNECTED", "hb": "15", "rtt": "1.8 / 1.7 ms",
  "lamps": { "resetreq": true, "linkok": true, "teleop": false },
  "stopbanner": { "on": true, "title": "RESET REQUIRED" } }
```

## H.2 `hmi-page-02-reset-held-2026-07-31.png` — RESET held down

**This is what section D listed as not shown.** The button is pressed with a real
`pointerdown` and held for 1.5 s before the capture, so the `m4f-07b` DOM
handlers are the ones under the finger, not the HTTP endpoint behind them.
`HmiResetRequest` reads `true` on the page's own request table while the button
is down, and the latch has already cleared on the rising edge:

```
{ "requests": { "reset": "true", "teleop": "false" },
  "lamps": { "resetreq": false }, "stopbanner": { "on": false } }
```

**One finding, and it is cosmetic.** The RESET button looks *identical* held and
not held. `button:active, button.held` sets the live blue, but `button#reset`
follows it in the stylesheet with a higher specificity (an id beats a class), so
the amber styling wins in both states. The fork-jog buttons, which carry no id
rule, do light up while held — visible in H.5. The behaviour is correct in both
cases and only the feedback differs; it is recorded here because an operator
holding a control with no visual acknowledgement is exactly the kind of thing an
HMI v2 pass should fix.

## H.3 `hmi-page-03-connected-teleop-2026-07-31.png` — connected and driving

The reference image of the page in its normal working state: joystick held at
`X = +0.55, Y = +0.64`, ENABLE asserted, the carriage raised to `1.20 m`, and the
PLC answering.

```
{ "linkstate": "CONNECTED", "hb": "71", "rtt": "1.9 / 1.9 ms",
  "requests": { "traction": "0.640", "steer": "0.721", "fork": "0.000",
                "teleop": "true", "reset": "false" },
  "lamps": { "teleop": true, "speed": true, "linkok": true },
  "metrics": { "tref": "0.192", "speed": "0.180", "height": "1.200",
               "sref": "0.721", "period": "100.0", "age": "149" } }
```

`0.192` is `0.64 × 0.30`, the raised-carriage cap — not `0.64 × 1.00`. The HMI
neither applied that cap nor knows its threshold: it displayed the request it
sent and the reference the PLC formed, side by side, and recomputed neither
(invariant 10). Same figure as section C's browser pass, from a different
machine and a different session.

## H.4 `hmi-page-04-safety-mirrors-absent-2026-07-31.png` — `Forklift/Safety/` absent

The section 11 panel on a server that does not carry the group, cropped to the
panel. All four lamps greyed at 40 % opacity with their bulbs neutral, and the
amber "not present" note under them. **Greyed is its own state, never a guessed
`FALSE`** (`opcua-nodes.md` §11.6). The link is `CONNECTED` throughout: an absent
optional group is not a connect failure.

## H.5 `hmi-page-05-fork-jog-held-2026-07-31.png` — the fork jog held

`FORK UP` held, visibly lit blue by the `.held` rule. The request is a
full-scale `1.000` and the PLC answers with `0.150 m/s`, `FORK_SPEED_MAX`:

```
{ "requests": { "fork": "1.000", "teleop": "true" },
  "metrics": { "fref": "0.150", "height": "1.200", "tref": "0.000" } }
```

## H.6 `hmi-page-06-process-stop-latched-2026-07-31.png` — a latched process stop

`ForkliftObstacleInStopZone` was driven `TRUE` by the plant driver *while the
joystick was still held*. The red **PROCESS STOP LATCHED** banner, both stop
lamps lit, `ForkliftResetRequired` back on — and the requests still standing at
`0.560 / 0.655 / true` while every reference reads `0.000`:

```
{ "requests": { "traction": "0.560", "steer": "0.655", "teleop": "true" },
  "lamps": { "obstacle": true, "zone": true, "resetreq": true, "teleop": false },
  "metrics": { "tref": "0.000", "sref": "0.000" } }
```

That gap between a live request and a zero reference is the whole architecture in
one picture: the operator is still asking, and the PLC has already decided. The
banner says so in its own fine print — standard-program process logic, not a
safety function, and this page is not a safety device.

## H.7 `hmi-page-07-page-beacon-stale-2026-07-31.png` — §10.8 H6, seen from the page

The browser context was taken offline for 2.2 s, longer than
`UI_POLL_STALE_TIME = 1000 ms`, and photographed on the first poll after it came
back. The link banner still reads `CONNECTED` and the heartbeat is still
counting; what changed is the **page beacon**, in amber:

```
{ "linkstate": "CONNECTED", "hb": "151", "beacon": "STALE - requests held at rest",
  "requests": { "traction": "0.000", "teleop": "false", "reset": "false" } }
```

The backend returned all five requests to rest, the enable included, **while the
write cycle and the heartbeat kept running**. Nothing latched and no reset is
owed for it: the process is healthy and what was gone is the page.

## H.8 `hmi-page-08-requests-dropped-notice-2026-07-31.png` — after the page returns

The same run one second later. The beacon reads a normal age again and the
amber notice carries the history — "Requests were held at rest 1 time(s) … press
ENABLE again when ready. Nothing latched in the PLC and no reset is owed for
this." Recovery is a release, never a resume: `HmiTeleopRequest` stays `false`
until a person presses ENABLE again.

## H.9 `hmi-page-09-link-lost-2026-07-31.png` — supervision lost

The double was killed under a live session. The banner turns amber
**RECONNECTING** and carries the reason verbatim, the heartbeat reads
`161  STOPPED`, and the whole metrics table greys out at `metrics age 1748 ms`:

```
{ "linkstate": "RECONNECTING", "hb": "161  STOPPED", "lastwrite": "1650 ms ago" }
```

with the reason line under the banner, read off the image itself:

```
ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 4850)
```

The stale values stay on screen, greyed rather than blanked or frozen-looking,
and the page keeps saying in its footer what this is: a degraded mode with a
PLC-owned controlled stop, never a safety event (invariants 1, 2).

## H.10 `hmi-page-10-safety-mirrors-present-2026-07-31.png` — `Forklift/Safety/` present

The same panel against `safety_mirror_double.py --with-safety-mirrors`, cropped.
Three violet lamps lit and one dark, the group's fail-safe start values
`EStopDemand TRUE`, `ZoneStopDemand TRUE`, `SafetyResetRequired TRUE`,
`SafetyResetFault FALSE` (§11.6). Read side by side with H.4 this is the whole of
§11.6's contract: present-and-lit, present-and-dark, and absent are three
distinguishable states on the panel.

## H.11 `hmi-page-11-safety-demand-banner-2026-07-31.png` — the mirror banner

The full page for the same run. The violet **SAFETY DEMAND** banner sits below
the amber process banner, with a different hue, a double border, its own heading
and the label "F-CPU safety demand (mirror, read-only)" — the visual
distinctness §11 asks for, seen rather than inferred from the markup. Its text is
the PLC's own `SafetyResetRequired`, quoted, never an OR this page re-derived:

```
"SafetyResetRequired is TRUE on the F-runtime group -- EStopDemand true,
 ZoneStopDemand true. A monitored reset on that group's own device clears it;
 nothing on this page can."
```

This double is a **dumb address space**: it runs no program, so `HmiLinkOk` is
dark and every `Forklift/Output/` and `Forklift/Status/` value in that image is a
start value, not a verdict. The mirrors are the only thing in image 11 worth
reading.

## H.12 What is deliberately not shown here

| Not shown | Why |
|---|---|
| Anything about the commissioned S7-1500, PLCSIM Advanced or the TIA build | Neither was contacted. Both configurations name loopback ports 4850 and 4860; `hmi/config.yaml` was not run |
| Anything about a real F-CPU | The four mirrors in H.10–H.11 are `safety_mirror_double.py`'s start values. No F-program exists behind them, and no safety claim is made or implied by an image of a lamp |
| The page under a real operator's hand, on the commissioning laptop | A headless Chromium driven by a script is not an operator, and no touch device, screen size or lighting condition was evaluated. Ergonomics of the M4 page are untested and stay that way |
| A latch cleared with the full T5.4 sequence | H.2 shows the held reset clearing the boot latch with the enable already low. `SPEC.md` §11 T5.4's whole procedure — release ENABLE, hold RESET across the moment the cause disappears, assert ENABLE again — is section E's, run against the endpoint, and is not repeated here |
| The `page beacon` window measured, rather than illustrated | H.7 is a picture of a state whose numbers section E measured. Nothing in this section times anything |
| Any figure derived by arithmetic while writing | Every quoted value is what the page's own DOM carried at the instant of capture, printed by the capture script beside each shot |

---

# Section I — HMI v2a, the operator screen, state by state (m5-28)

`hmi/V2A-DESIGN.md` is the authority for the screen recorded here; m5-28 built
it. Every image below lives in `hmi/evidence/screenshots/`, which is
**gitignored by owner ruling** — the files stay on the machine that produced
them, and **this list is the only part of the capture that travels with the
repository**. A claim to have screenshotted a state is worth nothing without
its row here.

Every value quoted in this section is what the page's own DOM carried at the
instant of capture, printed by the capture script beside each shot. Nothing
here was derived by arithmetic while writing.

## I.1 Environment

| Item | Value |
|---|---|
| Machine | the **Windows showcase machine**, not the container and not WSL |
| Python | 3.13.2 (MSC v.1942, 64-bit), `asyncua` 2.0.1 |
| Browser | `Chrome/151.0.7922.75`, headless, driven over the Chrome DevTools Protocol |
| Server under the HMI | `hmi/tools/v2a_scenario_double.py` on `opc.tcp://127.0.0.1:4861/amr-agent/v2ascenariodouble/` |
| HMI configuration | `hmi/config-v2a-double.yaml`, HTTP `127.0.0.1:8094` |
| Write cycle / read poll | 100 ms / 200 ms, as that configuration names them |
| Adopt delay in the double | **1.2 s per stage**, `--adopt-delay 1.2` |
| Run log | `hmi/evidence/capture-v2a-2026-08-05-run3.log` — the m5-29b re-capture, after the finding-1 fix. The m5-28 run it replaces is `…-run2.log`, kept beside it |
| Manifest written as the run landed | `hmi/evidence/screenshots/MANIFEST-2026-08-05.txt` |

**Two more logs belong to this section and are read with it.**
`hmi/evidence/capture-v2a-2026-08-05-f1-defect-before-fix.log` is the same
second-tab pass run against the **superseded** page, and it is the reproduction
of m5-29 finding 1 (§I.7). `hmi/evidence/f2-connect-failure-2026-08-05.log` is
the connect refusal `hmi/config.yaml` produces against a server with no §12
nodes (§I.8).

**No PLC was contacted.** Neither the commissioned S7-1500 nor PLCSIM Advanced
took part: the endpoint above is loopback, and the running CPU carries no
`opcua-nodes.md` §12 node at all (m5-23 Part B), which is exactly why the
double exists. **Nothing in this section is evidence about the TIA build, about
a real F-CPU, or about the vehicle layer**, and nothing rehearsed against a
double closes any gate criterion.

## I.2 What produced these, and the three roles

```
v2a_scenario_double.py   plays the PLC and the vehicle. It owns every verdict
                         the page displays. It runs NO arbiter: each state
                         change is a straight-line script that waits for a
                         value the HMI wrote, sleeps a scripted delay and
                         assigns a recorded answer from SPEC.md 14. A refusal
                         is a DIFFERENT SCRIPT, never a computed branch
hmi_server.py            the software under test, backend half
the browser              plays the OPERATOR, through the page, with genuine
                         input events - so the page's own DOM handlers are the
                         code exercised, not the HTTP endpoints behind them
```

The last line is deliberate. §C of this document carries a residual from
exactly that confusion: a page's handlers can pass an endpoint test while being
themselves unexercised. Every press below went through `Input.dispatchMouseEvent`
into the rendered page.

`capture_v2a_screens.mjs` speaks CDP over the WebSocket built into Node 22 and
**adds no dependency of any kind** — no Playwright, no `node_modules`, nothing
in any venv. That is why it runs on this machine, where `capture_screens.mjs`
(§H's Playwright instrument) does not.

## I.3 The screenshots, one row per state

All files are `hmi/evidence/screenshots/v2a-NN-…-2026-08-05.png`.

| # | File stem | State it shows |
|---|---|---|
| 00 | `cold-start-link-not-granted` | CPU cold start with `HmiLinkOk` still `FALSE`. **PROCESS STOP renders UNAVAILABLE**, every read-derived state renders unknown (hatched, em-dash), and the backend is nonetheless writing `HmiProcessStopRequest` `TRUE` — the §12.8 boot value it must not flip |
| 01 | `cold-start-before-operator` | cold start with the link up, before the operator does anything: the stop **ENGAGED and armed**, process stop latched, reset required, envelope `WITHHELD` / `0.00 m/s` / `not stated`. §14.9's signature, and connecting has cleared nothing |
| 02 | `process-stop-released-latch-stands` | design §9 step 3, the operator releases the stop: `HmiProcessStopRequest` goes `FALSE` and **the latch visibly does not clear**. Request and latch are two things |
| 03 | `reset-held` | step 4, RESET held: `HmiResetRequest` `true` for as long as the button is down |
| 04 | `latches-cleared-nothing-energized` | after the reset: both latches clear and **nothing energized** — teleop inactive, motion withheld, ceiling still `0.00 m/s` |
| 05 | `mode-change-in-flight-not-in-force` | **A MODE CHANGE IN FLIGHT, stage 1.** Selected TELEOP, in force still NONE; chip reads *selection not in force*, neutral, never an alarm. Captured **350 ms into a 1.2 s window** |
| 06 | `mode-change-in-flight-vehicle-adopting` | **A MODE CHANGE IN FLIGHT, stage 2.** In force TELEOP, vehicle still applying NONE; chip reads *vehicle adopting*, and the two data are shown side by side as data, not a verdict |
| 07 | `teleop-mode-in-force` | the in-flight rendering **cleared**: selected = in force = applied, zone B un-greyed |
| 08 | `teleop-enabled-and-driving` | ENABLE asserted and the joystick held — the second, separate act after selecting the mode |
| 09 | `autonomous-mode-in-force` | AUTONOMOUS in force; the selection *was* the affirmative action. Envelope reads `PERMITTED` / `0.80 m/s` / `ready` |
| 10 | `process-stop-engaged` | the stop engaged during an autonomous run: amber, rectangular, depressed, captioned *stop requested — release, then RESET*. It acts on press, with no confirmation dialog |
| 11 | `process-stop-latched` | the PLC has latched it: *process stop latched* and *reset required* assert, and **the envelope goes non-permissive** — the stop reaches the vehicle through the envelope, not through a stop topic of its own |
| 12 | `diagnostics-drawer-open` | zone F opened: every raw input, output, request and counter v1 showed as a labelled number, demoted rather than deleted. `ForkliftVehicleHeartbeat` appears as the **raw counter** and no liveness verdict is derived from it |
| 13 | `mode-selection-refused` | **a disagreement that never resolves**: AUTONOMOUS selected, entry refused and consumed, and 5 s later the chip still reads *selection not in force*. The caption states the away-and-back re-selection; the conditions strip re-renders what the PLC publishes and diagnoses nothing |
| 14 | `vehicle-adopting-unresolved` | a **vehicle that never adopts**: AUTONOMOUS in force, vehicle applying NONE, 2.5 s in — twice the adopt window — still neutral and still not an alarm |
| 15 | `mode-disagreement-declared-by-plc` | the same disagreement after the PLC's own delay elapsed: **RESET REQUIRED** asserts in zone C and the envelope goes non-permissive. The verdict arrived from the PLC; the HMI ran no timer |
| 16 | `link-down-process-stop-unavailable` | `HmiLinkOk` `FALSE` **with the OPC UA session still up**: the stop renders UNAVAILABLE and the strip states the degraded-mode fact. The two causes are visibly separate |
| 17 | `safety-lamps-unknown-link-down` | **zone D cropped from the same frame**: with the reading unattributable, all four F-layer lamps render UNKNOWN rather than clear |
| 18 | `session-down` | the server went away under a live session: the session chip leaves CONNECTED and the stop is UNAVAILABLE on the backend's own channel rather than on `HmiLinkOk` |
| 19 | `backend-not-answering` | the HMI backend itself stopped: the page does **not** keep its last live look — every state goes unknown |
| 20 | `safety-lamps-healthy` | mirrors present and clear: outlined lamps, own banner, own frame, nothing from zone C merged in |
| 21 | `safety-lamps-f-demand-active` | an F-layer e-stop demand asserted — **the only red element on the page** — with the PROCESS STOP beside it still amber |
| 22 | `safety-lamps-group-absent` | the server does not carry `Forklift/Safety/` at all: the zone greys with *not present on this server*, the session stays CONNECTED, no lamp is substituted with `FALSE` |
| 23 | `page-beacon-drop-standing-controls-held` | after this page went quiet and returned: the five teleop requests were held at rest and the enable dropped, while **the process stop and the mode selector kept their operator-set values** |
| 24 | `second-tab-adopts-current-state` | **a SECOND TAB**, opened while the operator was already working in the first: it renders the stop RELEASED and TELEOP selected — the values the backend holds *now* — rather than the §12.8 boot values a page asserting its own defaults would show |
| 25 | `second-tab-backgrounded-stop-stays-engaged` | **the m5-29 finding-1 path walked.** The operator engaged the stop in this tab; the other tab, holding the older position, was then backgrounded with its `visibilitychange` and `blur` handlers fired. The engaged stop is **still engaged**, on the wire and on this screen, and the selector is still TELEOP |

Images 24 and 25 were added by m5-29b. Every image in the table was re-captured
in that run, so no row describes a page that no longer exists: the mode chip's
in-flight tone is now neutral rather than amber (§5.2), and zone A carries the
§8 *not reaching the PLC* caption under the selector when the link is down.

Brief m5-28 §3 asked for a minimum of ten states. The set above is 26, and the
states it adds beyond that list are the ones the design specifies and the list
did not name: the pre-link cold start (00), the release that does **not** clear
the latch (02), the reset that energizes nothing (04), **both halves** of the
adopt window separately (05, 06), the settled state that proves the in-flight
rendering *clears* (07), the diagnostics drawer (12), the two different
never-resolving disagreements (13, 14), the PLC declaring one (15), the session
and backend halves of "down" apart from the link half (18, 19), the
standing-control behaviour under a page drop (23), and the two-page states a
one-page instrument could not reach at all (24, 25).

## I.4 The adopt window, exercised rather than asserted

LESSONS 2026-07-31: the obvious steady-state form of a commanded-versus-reported
comparison made autonomous mode **permanently unreachable**, and it was found by
an executable double running a **200 ms** adopt window rather than an
instantaneous one. This build was tested the same way and with a longer window.

The double opens the window in two stages, each `--adopt-delay` long, because
the screen has two distinct in-flight renderings:

| Stage | Condition | Chip | Where it was captured |
|---|---|---|---|
| 1 | selected ≠ in force | `SELECTION NOT IN FORCE` | image 05, **350 ms into a 1.2 s stage** |
| 2 | selected = in force ≠ applied | `VEHICLE ADOPTING` | image 06, **400 ms into the next 1.2 s stage** |
| — | all three agree | the mode name, steady | image 07 |

Quoted from the run log, image 05 and image 06, unedited:

```
05 selection in flight  strip.mode "SELECTION NOT IN FORCE"
                        machineMode "NONE"   selected [1]   requests.mode "1"
06 vehicle adopting     strip.mode "VEHICLE ADOPTING"
                        machineMode "TELEOP" vehicleMode "NONE" vehicleDiff true
```

**Three things this run establishes and one it does not.** It establishes that
the in-flight rendering appears (05, 06), that it **clears** when the window
closes (07), and that a disagreement which never resolves is rendered without
alarm and without any HMI-side clock — twice, in two different shapes (13, 14),
with the PLC's own declaration arriving later as `ForkliftResetRequired` (15).
It does **not** establish anything about `MODE_DISAGREE_DELAY`, about
`#modeEntryAdmitted`, or about any §14 term: the double replays answers and
computes no verdict, and every one of those belongs to `plc/forklift/SPEC.md`
and to the TIA build.

## I.5 The checks the capture asserted while it ran

The capture script does not only photograph. It reads the rendered DOM at each
step and **asserts**, so a silent rendering regression cannot pass as a
captured screenshot. Run of 2026-08-05 (`…-run3.log`, after the m5-29b fixes):
**51 checks, 51 passed, 0 failed** (counted by `CHECK PASS` / `CHECK FAIL`
lines in the run log; the m5-28 run in `…-run2.log` carried 41 of these, and
m5-29b adds the other 10 — eight in the second-tab pass and two on the §8 selector caption). The load-bearing ones:

| Check | What would have failed it |
|---|---|
| cold start: the stop is UNAVAILABLE and `disabled` while `HmiLinkOk` is `FALSE` | a control that looks armed over a dead link |
| cold start: it is not rendered engaged-looking while unavailable | the two states blurring into one |
| cold start: every read-derived state is UNKNOWN, not clear | *not yet written* read as *clear* |
| cold start: the backend is nonetheless writing the stop engaged | a connecting HMI flipping a non-permissive boot value |
| PS1: the latch did not clear when the request did | request and latch conflated |
| the reset cleared the latches and energized nothing | a reset that starts something |
| adopt stage 1 / stage 2 chips, and machine mode never showing the selector | §12.3 **M2**, showing your own request back as state |
| the in-flight rendering cleared once the window closed | a stuck in-flight state, i.e. the 2026-07-31 defect's shape |
| an unresolved adopt window is still neutral, and the chip never says "fault" | the HMI declaring a verdict the PLC owns |
| M6: teleop-active and motion-enable never both asserted | two live command sources |
| `HmiLinkOk` `FALSE` with the session UP still renders UNAVAILABLE | conflating the two independent causes |
| an F-demand asserts red, and the stop beside it stays amber | red leaking out of zone D |
| an absent mirror group greys and the session stays CONNECTED | an optional group failing a connect, or reading `FALSE` |
| the backend gone: the page renders unknown, not its last look | a frozen display that looks live |
| H6: the five deadman requests went to rest; the heartbeat kept running | the page loss buying the PLC's heavier reaction |
| PS-B / §5.1: the two standing controls held their operator-set values | a page hiccup inventing an operator act in either direction |
| F1(a): a second page renders the backend's standing values, not the boot values | a page asserting its own defaults over an operator's positions |
| F1(b): backgrounding a second page changed neither standing value on the wire | **the m5-29 finding-1 defect** |
| F1(c): every write cycle after that background still carried both values | the same, proved per cycle rather than at two samples |
| §8: the selector says *not reaching the PLC* link-down, and does not say it link-up | a caption the design requires being absent, or stuck on |

## I.6 What is deliberately not shown here

| Not shown | Why |
|---|---|
| Anything about the commissioned S7-1500 or the TIA build | neither was contacted; the CPU carries no §12 node yet, which is why the double exists |
| Anything about a real F-CPU | the four mirrors in 20–22 are the double's scripted values. No F-program exists behind them and no safety claim is made or implied by an image of a lamp |
| Anything about the vehicle's control layer | `ForkliftVehicleModeApplied` and `ForkliftVehicleHeartbeat` were moved by a script standing in for the bridge. No `agv/` node ran |
| Any arbitration, threshold, delay or latch behaviour of the standard program | the double replays recorded answers with scripted delays. Divergence resolves toward `SPEC.md` and toward TIA, never toward the double |
| The page under a real operator's hand | a headless Chrome driven by a script is not an operator. No touch device, screen size, glove or lighting condition was evaluated |
| The live map, obstacles or pose | v2b (m5-13, ADR 0011 D4). v2a designs and builds none of it |
| Any measured latency or timing figure | this section photographs states. The write-cycle and round-trip figures of §E were not re-measured here, and no number in §I is a performance claim |

## I.7 The second tab — m5-29 finding 1, reproduced and then walked again

The m5-28 page rendered its two STANDING controls from a **local copy adopted
once** and re-asserted that copy in **every** post: the 50 ms dirty loop, every
deadman post, `blur`, `pagehide` and `visibilitychange`. One tab and one reload
are safe and the m5-28 evidence for them is genuine. A **second tab** is not:
it holds the position the operator has since changed, and backgrounding it
posts that stale position.

An operator opening a second tab is not doing anything unusual, so this was
**reproduced before it was fixed** rather than argued about. The instrument
gained a two-page pass (`capture_v2a_screens.mjs`, `passSecondTab`) that opens a
real second browser target on the same backend, has the operator engage the stop
in the first, and then backgrounds the second — firing the page's own
`visibilitychange` and `blur` handlers into it.

**The defect, from `capture-v2a-2026-08-05-f1-defect-before-fix.log`** (the same
pass against the superseded page; DOM quotes unedited):

```
B2 the other tab follows the backend    pstop.label "PROCESS STOP"
                                        requests.pstop "true"
A after the other tab was backgrounded  pstop.label "PROCESS STOP — ENGAGED"
                                        requests.pstop "false"
CHECK FAIL  F1(b)   HmiProcessStopRequest=false HmiDriveModeRequest=1
CHECK FAIL  F1(c)   cycles=20 stop-flips=20 mode-flips=0
```

Read the two middle lines together: **the operator's own screen says ENGAGED
while the wire says released.** The stop was released by a browser event, and
every one of the 20 write cycles that followed carried the release
(`hmi-cycles-2026-08-05-secondtab-20260805T115515Z-pid12676.csv`, the backend's
own per-cycle log). Four checks failed. The mode selector has the identical
mechanism, where a stale post is a fresh `#modeSelectRise` at the PLC — X3, or
X2, which is the affirmative autonomous enable.

**The same pass after the fix**, from `…-run3.log`:

```
B2 the other tab follows the backend    pstop.label "PROCESS STOP — ENGAGED"
A after the other tab was backgrounded  pstop.label "PROCESS STOP — ENGAGED"
                                        requests.pstop "true"
CHECK PASS  F1(b)   ...                 CHECK PASS  F1(c)  cycles=23
                                        stop-flips=0 mode-flips=0
```

The second tab now **follows the backend** — it renders ENGAGED because the
backend holds ENGAGED — and backgrounding it changes nothing on the wire, in
any of the 23 write cycles that follow
(`hmi-cycles-2026-08-05-secondtab-20260805T120629Z-pid656.csv`). The deadman
half is untouched: `F1(b2)` confirms the backgrounded page's five teleop
requests still went to rest, which is H6 doing exactly its job.

What changed, in three lines: the page renders both standing controls from
`/state` on **every** poll and holds no copy; a standing key is sent only in the
post triggered by the click that changed it, so no periodic, deadman, blur or
beacon post carries one and a missing key means UNCHANGED; and `do_POST`
republishes the standing section, so `/state` cannot serve a stale position while
the OPC UA session is down. The rendered position catches up on the next 200 ms
poll after a click, and there is deliberately no optimistic local override —
a local override is what the defect was made of.

## I.8 The designed connect failure, made legible

`hmi/config.yaml` is **meant** to fail at connect against today's commissioned
CPU: that CPU carries no `opcua-nodes.md` §12 node until the owner's TIA
session, and a missing REQUIRED node is a genuine connect failure this client
never browses around. m5-29 finding 2: the symptom was a bare
`connect failed: BadNoMatch … (retry in 1.0 s)` naming no node and no path, so
the next person to hit it would debug a working system.

`hmi/evidence/f2-connect-failure-2026-08-05.log` is the refusal as it now
reads, produced by pointing the v2a node set at `plc/forklift/double/server.py`
(port 4850) — a server carrying the §10 set and **no** §12 node, which is the
shape of the CPU today. It names the node (`HmiDriveModeRequest`), its path
under the resolved browse prefix, that the failure is expected, the procedure
that adds the nodes (`plc/forklift/TIA-BUILD-PROCEDURE.md`), the config header
that explains it, and what to run meanwhile. The same string is what `/state`
carries as `session.reason`, so the page's degraded banner says it too.

No PLC was contacted for §I.7 or §I.8, and neither is evidence about the TIA
build, a real F-CPU or the vehicle layer.

---

# Section J — HMI v2b, the map pane (m5-53)

`hmi/V2B-DESIGN.md` is the authority for the pane recorded here. This section
is written **as the states landed**, not assembled afterwards; the run log and
the manifest were written by the instruments themselves, line by line, while
they ran.

Roadmap criterion (e)'s last clause is *"shows a real-time map with live
obstacles"*. What is recorded below is that pane and, at least as important,
**every way it can be wrong**: a pose that has stopped arriving, a scan that
has stopped arriving, a scan with no distance returns at all, no map yet, and
the monitoring service dead.

## J.0 The one thing this section exists to prove

AMCL publishes `/amcl_pose` **only on a filter update**. A standing vehicle
therefore has no pose stream at all, and the monitoring service's own evidence
records it: `viz/EVIDENCE_MONITORING.md` §8 shows `pose_age_ms = 463 157` —
7 min 43 s — beside message counters frozen at 30, with everything else
healthy. A page that draws that as a vehicle sitting on the map is **silently
wrong and looks exactly like a working display**.

So the pane has **no rendering that means "live"**. Every marker carries the
age of the datum it came from, in the marker itself, in every state; as the age
grows the marker fades and hollows; past the display ramp it is labelled a LAST
KNOWN POSITION and the pane says so in words. §J.4 photographs both ends and
asserts the difference **at the pixel level** — the solid marker is gone, not
merely re-captioned.

## J.1 Environment

| Item | Value |
|---|---|
| Machine | the **Windows showcase machine**, not the container and not WSL |
| Python | 3.13.2, `asyncua` 2.0.1 |
| Node | v22.14.0 — the CDP instrument, no Playwright, no `node_modules` |
| Browser | `Chrome/151.0.7922.75`, headless, driven over the Chrome DevTools Protocol |
| Playing the PLC | `hmi/tools/v2a_scenario_double.py` on `opc.tcp://127.0.0.1:4862/amr-agent/v2bscenariodouble/` |
| Playing the monitoring service | `hmi/tools/viz_double.py` on `http://127.0.0.1:8093` |
| Software under test | `hmi/hmi_server.py` + `hmi/static/index.html`, `hmi/config-v2b-double.yaml`, HTTP `127.0.0.1:8097` |
| Display ramp in force | `1000 .. 5000 ms`, published by the backend on every `/monitor/state` and read back by the instrument |
| Manifest, written as the run landed | `hmi/evidence/screenshots/MANIFEST-v2b-2026-08-06.txt` |
| Run log | `hmi/evidence/capture-v2b-2026-08-06.log` |
| Backend-half checks | `hmi/evidence/check-map-pane-2026-08-06.log` |

**No PLC and no vehicle were contacted.** No S7-1500, no PLCSIM Advanced, no
Gazebo, no ROS 2 process and no instance of the real `viz/` service took part:
every endpoint above is loopback and both servers are doubles.
**Nothing in this section is evidence about the TIA build, a real F-CPU, the
vehicle layer or the monitoring service itself**, and nothing rehearsed against
a double closes any gate criterion. Divergence resolves toward `viz/`, never
toward `viz_double.py`.

**What the double is faithful to, and how that is known.** Every payload key,
header, status and refusal in `viz_double.py` is copied from `viz/DESIGN.md` §5
and `viz/EVIDENCE_MONITORING.md` §7 rather than invented, including the map
geometry the real service actually served — 606 × 410 cells at 0.05 m, origin
(−9.145, −4.778), which is 30.3 × 20.5 m at full extent. The backend check
below asserts that the key set the page receives is **identical** to the key
set the service serves, so a divergence in shape would fail rather than pass
quietly.

## J.2 What produced these, and the four roles

```
v2a_scenario_double.py   plays the PLC. It owns every verdict zones A-F show
viz_double.py            plays the READ-ONLY MONITORING SERVICE. It owns the
                         map, the pose, the scan and EVERY AGE. Its ages are
                         steady-clock arithmetic, as the real service's are
hmi_server.py            the software under test, backend half
the browser              plays the OPERATOR, through the page, with genuine
                         input events dispatched into the rendered DOM
```

`capture_v2b_screens.mjs` is a **new file rather than an edit of
`capture_v2a_screens.mjs`**: that script and its captures are the v2a evidence
this version must be shown not to have broken, and a repeat that reuses its
predecessor's names destroys the comparison it exists to make
(`docs/LESSONS.md` 2026-08-06). Every file here is `v2b-*` and overwrote
nothing; `MANIFEST-2026-08-05.txt` and every `v2a-*.png` are untouched beside
them.

Two instruments, and the split is deliberate. The `.mjs` script presses the
page; `tools/check_hmi_map_pane.py` exercises the backend half and sweeps the
source. Section C of this document carries a residual from exactly the
confusion the split prevents — a page's handlers can pass an endpoint test
while being themselves unexercised — so **every visual claim below comes from
the DOM (and in two cases from the canvas's own pixels), and every transport
claim comes from the socket.**

## J.3 The screenshots, one row per state

All files are `hmi/evidence/screenshots/v2b-NN-…-2026-08-06.png`. The captions
in `MANIFEST-v2b-2026-08-06.txt` were appended by the instrument as each shot
landed.

| # | File stem | State it shows |
|---|---|---|
| 00 | `map-live-vehicle-and-obstacles` | **the criterion clause, met**: the whole 606 × 410 map at 0.05 m (30.3 × 20.5 m), the vehicle drawn solid, the lidar returns drawn where the service placed them, and every row carrying an age |
| 01 | `whole-page-map-beside-controls` | the same, on the whole page: the pane is a third column and zones A–F are unchanged |
| 02 | `map-zoomed` | the same map zoomed: a view transform is drawing, and **not one of the eight written values moved** across the zoom |
| 03 | `pose-STALE-last-known-position` | **the hardest state.** Pose 8.4 s old: no fill at all, hollow and dashed, `LAST KNOWN POSITION — as of 8.4 s, not a current position` on the marker, and the banner in words |
| 04 | `whole-page-pose-stale` | the stale pose on the whole page: zones A–F unaffected |
| 05 | `obstacles-absent-empty-horizon` | every beam beyond range: `no distance returns in this scan`, with the counts. Never "clear", never "safe", never "no obstacles" |
| 06 | `obstacles-stale-not-emptied` | the scan stopped arriving 9.7 s ago: the returns are drawn **hollow with their age**, not deleted |
| 07 | `no-map-received` | no map yet: nothing is drawn at all |
| 08 | `monitoring-service-down` | the service killed mid-run: the pane greys and shows no last values; the process zones and the heartbeat are untouched |
| 09 | `monitoring-not-configured` | a backend started with `--no-monitor`: the pane says **not configured**, which is a different fact from **not answering** |
| 10 | `v2a-cold-start-unbroken` | the v2a cold start re-photographed with the pane present |
| 11 | `v2a-stop-released-latch-stands` | PS1 with the pane present: request clears, latch does not |
| 12 | `v2a-teleop-driving-with-map` | TELEOP in force, enable asserted, joystick held forward, live map beside it |
| 13 | `page-beacon-stale-while-map-polls` | **only `GET /state` blocked**: H6 still fired and the enable was dropped while the map pane kept fetching |
| 14 | `second-tab-stop-stays-engaged` | the m5-29 second-tab path walked again, because v2b changed the beacon's input set |

## J.4 The stale pose, at the pixel level

This is the check the whole version exists for, and it is deliberately not a
check on a caption.

```
02a before the pose froze
  pose      "7.03, 7.56 m  -176 deg   as of 0.0 s"
  canvas    {colours: 544, nonBlank: 268380, vehicleFill: 53, obstacleInk: 186}

02b pose STALE
  pose      "13.49, 5.10 m  84 deg   LAST KNOWN, as of 8.4 s"
  obstacles "201 distance returns   705 beyond range, 4 invalid, of 910   as of 0.0 s"
  banner    "POSE STALE - the marker shows where the vehicle WAS 8.4 s ago, not
             where it is. The localization publishes only when its filter
             updates, so this is what a standing vehicle looks like as well as
             what a stopped one does. This page cannot tell those apart and
             does not guess."
  canvas    {colours: 564, nonBlank: 268380, vehicleFill: 0, obstacleInk: 176}
```

`vehicleFill` counts canvas pixels at the marker's **exact** fill colour, read
back with `getImageData` from the page's own canvas: **53 to 0**. The solid
marker is gone from the picture, not merely re-captioned. The display ramp in
force was `1000 .. 5000 ms`, read from the backend by the instrument rather
than assumed.

Two things in that readout matter as much as the marker:

- **`obstacleInk` stayed at 176 and the obstacle row still read `as of 0.0 s`.**
  The two ages are independent and neither is inferred from the other: the pose
  had stopped arriving while the scan had not, and the pane said exactly that.
- **The pose is at `13.49, 5.10 m` while the fresh sample was at `7.03, 7.56`.**
  The vehicle in the double did not teleport — the pose simply stopped being
  published at the instant of the freeze, which is precisely the failure this
  section exists for: without the age, a page would have drawn a vehicle at a
  place it left eight seconds earlier and called it a position.

## J.5 The other four ways the pane can be wrong

| State | What the DOM carried | The rule it shows |
|---|---|---|
| **obstacles absent** | `no distance returns in this scan   906 beyond range, 4 invalid, of 910   as of 0.0 s`; `obstacleInk = 0` | an empty horizon is a **measurement**, not missing data and not an absence of danger (`docs/LESSONS.md` 2026-08-06). The words *clear*, *safe*, *no obstacles* appear nowhere — asserted by the instrument, not by reading |
| **scan stopped arriving** | `201 distance returns   705 beyond range, 4 invalid, of 910   as of 9.7 s`, drawn hollow | a stale obstacle layer is **never** rendered as an empty one. The pane has no rendering that means "there is nothing there now", so a dead sensor cannot read as an empty aisle |
| **no map yet** | `No map has arrived from this vehicle yet`; `vehicleFill = 0`, `obstacleInk = 0` | a position without the map it is expressed in is not a picture |
| **service unreachable** | pose `—`, obstacles `—`, map `—`, `fetch: failed after 1520 ms`, canvas entirely blank; message names the reason | an unreachable source is **not a source of last values** |

## J.6 The process plane is untouched by all of it

From the `monitordown` pass, with the monitoring service killed mid-run while
the operator's mode was in force:

- session `CONNECTED` before and after; machine mode and `reset required`
  identical across the outage;
- the heartbeat kept advancing (`49 -> 90` in the backend check's own window)
  and `heartbeat.running` stayed `true`;
- the backend logged **no error line at all** about the dead service across the
  window — the check greps its log for one and finds zero.

The two planes are two sources, and the failure of one is not the failure of
the other. Nothing on the map pane feeds a control, a request, a lamp or a
verdict on the process side, and no caption on the page combines a value from
one plane with a value from the other.

## J.7 The beacon change, and why it was made and then tested

`V2B-DESIGN.md` §2.2: the three `/monitor/*` paths are **excluded** from the
`opcua-nodes.md` §10.8 H6 page-liveness beacon. A monitoring-plane fetch proves
the browser is running and proves nothing about the channel that carries the
operator's requests.

It was tested in the form that could only fail if the exclusion were absent —
**`GET /state` blocked at the browser while the map pane kept polling at full
rate**:

```
09 /state blocked, map still polling
  page      STALE
  requests  HmiTeleopRequest false, HmiTractionRequest 0
  standing  HmiProcessStopRequest false, HmiDriveModeRequest 1  (untouched)
  heartbeat running
  map pane  "60 ms round trip, http://127.0.0.1:8093"   <- still fetching
```

The block pattern is the exact URL and not `*/state`, which would also have
matched `/monitor/state` and stopped the map pane too — the pass would then
have proved nothing while still reporting a result.

The backend check reaches the same conclusion from the other side: polling
**only** `/monitor/state` for 2.5 windows took the page to `STALE` with
`drops = 2`.

The exclusion can only make the beacon go stale **sooner**. That is the
direction that fails safe, and it is why the change was acceptable at all.

## J.8 The second tab, walked again

v2b changed the beacon's input set, so the m5-29 finding-1 path was re-run
rather than assumed to still hold. A second tab was opened mid-scenario, the
operator engaged the stop in the first, and the second was backgrounded with
its own `visibilitychange` and `blur` handlers dispatched into it:

- the second tab rendered the **backend's** standing values on open, not the
  §12.8 boot values;
- it followed the backend to ENGAGED when the first tab acted;
- backgrounding it moved **neither** standing value, and
  **every one of the 33 write cycles** after the background still wrote the
  stop engaged and the mode TELEOP — read from the backend's own per-cycle
  evidence CSV, not from two lucky samples either side of the event.

## J.9 The backend half — `check_hmi_map_pane.py`, 2026-08-06

Log: `hmi/evidence/check-map-pane-2026-08-06.log`. Every line printed with the
values it read.

```
CHECK 1  exactly one urllib.request.Request(...) in hmi_server.py, and it is
         method="GET"; no http.client, requests, aiohttp, httpx or raw socket
         anywhere; no data= on the Request; the OPC UA write allowlist is still
         exactly eight nodes
CHECK 2  path                                   GET    POST     PUT  DELETE   PATCH OPTIONS    FROB
         /monitor/vehicles                      200     405     405     405     405     405     405
         /monitor/state                         200     405     405     405     405     405     405
         /monitor/map?serial=F001               200     405     405     405     405     405     405
         /                                      200     404     405     405     405     405     405
         /state                                 200     404     405     405     405     405     405
         /control                               404     200     405     405     405     405     405
CHECK 3  two fetches a second apart: pose_age 30.8 then 20.4 ms  -> no cache
         key set identical to the monitoring service's
         ramp published 1000.0 .. 5000.0 ms
         map_cells=248460; whole /monitor/state payload 4806 bytes;
         largest field "obstacles" at 3549 bytes  -> no raster on the poll
CHECK 4  proxied body byte-identical to the service's (871 vs 871 bytes)
         248460 cells == 606 x 410; every X-Map-* header survived
         606 x 410 at 0.05 m = 30.3 x 20.5 m
CHECK 5  service killed: unreachable with a reason, NO state served, raster
         path 502; session still CONNECTED; heartbeat 49 -> 90; zero error
         lines logged
CHECK 6  polling ONLY /monitor: page STALE, drops=2, window 1000.0 ms
CHECK 7  monitor.base_url on a non-loopback host refuses to start, naming
         invariant 8
MAP PANE CHECK PASS
```

`FROB` is in the matrix on purpose: the refusal is the handler's attribute
lookup rather than a list of known verbs, so a verb nobody anticipated lands on
the same 405. The write surface of this process is still exactly
`POST /control`.

## J.10 What is deliberately not shown here, and the residuals

- ~~**No run against the real `viz/` service, and none is claimed.**~~
  **CLOSED by §K (m5-53b).** The join was made: the real service, a real
  forklift in domain 51, Gazebo, Nav2 and AMCL, across the WSL-to-Windows
  loopback relay, with 22 checks passing and eight `v2b-real-*` captures. It
  needed no change to `hmi/` and none to `viz/`. What §K found that this
  section could not: across that crossing a dead service presents as a
  **timeout**, not as the refusal the Windows-resident double produced.
- ~~**The display ramp's two endpoints are display values, not measured
  ones.**~~ **MEASURED in §K.4** — n = 26 / 77 / 37 over three driving runs.
  The endpoints are unchanged here, because §K.4.2 proposes the correction and
  does not apply it: widening a ramp makes the page claim more, which is the
  owner's ruling to make. The finding in one line: the pose inter-arrival is
  `update_min_d / speed`, so both endpoints are statements about a **speed**,
  and `1000 ms` sits at the median of brisk driving rather than above it.
- **n = 1.** One serial exists. Every path is serial-rooted and the pane reads
  the list rather than a constant, but the second vehicle is the test and it
  does not exist yet.
- **Nothing here is evidence about the TIA build, a real F-CPU, the vehicle
  layer, Nav2 or the monitoring service.** Two doubles produced every value.
- `tools/check_hmi_writes.py` and `tools/check_hmi_h6_and_reset.py` are m4-era
  harnesses that call `os.killpg` and **do not run on Windows at all**; that is
  a pre-existing platform limitation, not a v2b regression. Their subject
  matter — the write allowlist, H6 and the reset edge — is covered here by
  §J.7, §J.8 and CHECK 1/2 above. One of their checks did run and pass in
  passing: the allowlist still refuses a doctored config naming a ninth node.

---

# Section K — the joint run: the REAL monitoring service and a REAL vehicle (m5-53b)

**This is the run §J.10 said had not been made.** Every value in §J came from
`hmi/tools/viz_double.py`. Every value here came from `viz/monitor/service.py`
subscribing in a real forklift's own DDS domain, across a WSL-to-Windows
crossing, with Gazebo, Nav2 and AMCL running behind it. Where the two disagree,
this section wins.

**What is still a double, said before anything else is claimed.** The PLC is
`hmi/tools/v2a_scenario_double.py`. The controller was not available to this
session, so **zones A–F remain rehearsed, not proven**, exactly as in §J. Only
the map pane is joined to reality. Nothing in this section is evidence about
the TIA build, the F-CPU or the bridge.

## K.1 The crossing, and why it needed no change to either layer

The monitoring service needs `rclpy` and runs in WSL. The page, its backend and
the browser run on Windows. How they meet is the whole task.

**They meet on the address the HMI already had.** WSL2 relays the *Windows*
loopback address to a Linux service bound to `127.0.0.1`, so
`http://127.0.0.1:8089` on Windows reaches `viz/monitor/service.py` inside WSL
with **no proxy, no bind change, no port forward, and no edit to `hmi/` or
`viz/`**. `hmi/config.yaml`'s `monitor.base_url` was already
`http://127.0.0.1:8089`, and the backend's loopback rule (`LOOPBACK_HOSTS`,
invariant 8) is satisfied by it literally rather than by exception.

Proved before anything was built on it, because the usual report is the
opposite — that only `0.0.0.0`-bound services are relayed:

```
WSL:      python3 -m http.server 8091 --bind 127.0.0.1
          python3 -m http.server 8092 --bind 0.0.0.0
          LISTEN 0 5   127.0.0.1:8091
          LISTEN 0 5     0.0.0.0:8092

Windows:  port 8091 : HTTP 200      <- the 127.0.0.1-bound one is relayed too
          port 8092 : HTTP 200
```

**What a later reader must reproduce, and the conditions it depends on.**

| Condition | Value in this run | If it changes |
|---|---|---|
| WSL networking mode | NAT with `localhostForwarding`; kernel `5.15.167.4-microsoft-standard-WSL2` (mirrored mode needs 6.6+) | mirrored mode also works and also needs no change; a configuration with neither would need a `--bind` on the service, which is `viz/`'s call and not this layer's |
| Windows-side listener on 8089 | none — `netstat` was checked before the run | a Windows process holding 8089 **wins** and the relay silently does not happen, so the HMI would read that process instead. Check the port is free before trusting the address |
| The service's bind | `viz/`'s own default `127.0.0.1:8089`, unchanged | — |
| `hmi/` change required | **none.** No file in this layer was edited to make the crossing | — |

**One real fact the double could not have shown, and it matters.** When the
real service dies, the HMI does **not** see a refused connection. The relay
still accepts, so the fetch **times out**: the pane's reason line read
`URLError: <urlopen error timed out>` after `1537 ms`, where the
Windows-resident double produced an immediate `ConnectionRefusedError`. The
pane greys and says so either way — the bounded timeout in `MonitorProxy` is
exactly what makes the difference between "grey after 1.5 s" and "hung" — but a
reader must not expect a refusal across this crossing.

## K.2 Environment

| Item | Value |
|---|---|
| Windows side | the showcase machine. Python 3.13.2, `asyncua` 2.0.1, Node v22.14.0, `Chrome/151.0.7922.75` headless over CDP |
| WSL side | Ubuntu, kernel `5.15.167.4-microsoft-standard-WSL2`, ROS 2 Jazzy, `gz sim` 8.11.0 |
| Simulation | `gz sim -r -s -v 2 sim/worlds/warehouse.sdf`, `GZ_PARTITION=m553b`, 12 gz topics |
| Vehicle | `agv/forklift/scripts/vehicle_image.py --vehicle F001`, domain 51 from `allocation.yaml`. `process has died` count **0**; `Nav2 active.` |
| **The monitoring service** | **`viz/monitor/service.py --status-period 10` — the real one**, started from a shell with no `ROS_DOMAIN_ID`, reporting `subs 5 publishers 0 services 0 clients 0` |
| Playing the PLC | `hmi/tools/v2a_scenario_double.py` on `opc.tcp://127.0.0.1:4862/…` — **still a double** |
| Software under test | `hmi/hmi_server.py` + `hmi/static/index.html`, `hmi/config-v2b-double.yaml`, `--monitor-url http://127.0.0.1:8089`, HTTP `127.0.0.1:8098` |
| Display ramp in force | `1000 .. 5000 ms`, read back from the backend by the instrument |
| Instrument, captures | `hmi/tools/capture_v2b_real_screens.mjs` → `hmi/evidence/capture-v2b-real-2026-08-06.log`, `screenshots/MANIFEST-v2b-real-2026-08-06.txt` |
| Instrument, measurement | `hmi/tools/measure_pose_arrivals.py` → the four `hmi/evidence/pose-arrivals-2026-08-06-*.csv` |
| Motion stimulus | a throwaway `rclpy` publisher, source quoted in K.6. **Not repository content**: a ROS 2 publisher has no home in `hmi/` |

**Nothing under test was edited by this run.** The two new files are both
instruments in `tools/`; `hmi_server.py` and `hmi/static/index.html` are
byte-identical to the build §J photographed. That is also why the m5-29
second-tab check was **not** re-run: that obligation is conditional on touching
the posting path, and the posting path was not touched.

## K.3 The states, on real data — 22 checks, all passing

`hmi/evidence/capture-v2b-real-2026-08-06.log` is the full transcript. Files
are named `v2b-real-*` so that no reader can confuse them with §J's `v2b-*`
captures of the double, and nothing of §J's was overwritten.

| Screenshot | The state, on real data |
|---|---|
| `v2b-real-00-map-live-real-service-2026-08-06.png` | **The whole real map, the live real pose, real lidar returns.** `v1 606 × 410 cells at 0.050 m (30.3 × 20.5 m, whole map)`; `6.99, 11.62 m −42° as of 0.6 s`; `243 distance returns 117 beyond range, 0 invalid, of 360 as of 0.0 s`; `88 ms round trip` |
| `v2b-real-01-whole-page-real-service-2026-08-06.png` | the same, whole page: the map pane beside the (doubled) process zones |
| `v2b-real-02-map-zoomed-real-service-2026-08-06.png` | the real map zoomed — with the eight written values compared **bit for bit** before and after: unchanged |
| `v2b-real-03-pose-fresh-while-driven-2026-08-06.png` | the baseline: solid marker, `54 px` of marker fill, while the vehicle is under command |
| `v2b-real-04-pose-STALE-standing-vehicle-2026-08-06.png` | **the residual, not simulated.** The stimulus simply stopped. `LAST KNOWN, as of 9.2 s`, marker fill `0 px`, the lidar layer beside it still `79 ms` old |
| `v2b-real-05-whole-page-pose-stale-standing-2026-08-06.png` | the same standing vehicle, whole page: the process zones unaffected |
| `v2b-real-06-real-monitoring-service-stopped-2026-08-06.png` | **the real service killed mid-session.** Pane grey, `—` in every row, canvas empty, session still `CONNECTED`, heartbeat still advancing |
| `v2b-real-07-recovered-after-restart-2026-08-06.png` | the real service restarted: the pane recovered by itself and refetched the whole grid. No operator action |

### K.3.1 The stale path, on a genuinely standing vehicle

The one a double could only imitate. `viz_double.py` was *told* to stop
publishing at a scheduled instant. Here nothing was told anything: the motion
stimulus ended, the forklift stood, and **AMCL stopped publishing because a
standing vehicle produces no filter update**. The page degraded by itself.

```
driven:   "5.61, 12.97 m  -46°   as of 0.5 s"                vehicleFill 54 px
standing: "7.31, 11.46 m  -42°   LAST KNOWN, as of 9.2 s"    vehicleFill  0 px
          obstacles at that same instant: "as of 0.1 s"
```

The assertion is at the pixel level — a census of the canvas at the marker's
exact fill colour `#3aa0dc` — so **the picture changed**, not the caption. And
the two ages moved independently: the lidar kept arriving at 10 Hz throughout,
which is the fact that makes a single "vehicle alive" verdict impossible and is
why this pane makes none.

### K.3.2 The real service stopped mid-session

Killed by PID in WSL while the page was up. `fetch: failed after 1537 ms`, and
the pane's own words:

> The monitoring service is not answering. No map, no position and no obstacles
> are shown, because nothing here is old enough to be worth drawing — an
> unreachable source is not a source of last values.

Zones A–F, read before and after, were identical field for field
(`CONNECTED / TELEOP / clear / not required / inactive`); the heartbeat kept
advancing; the backend did not exit. The service was then restarted and the
pane recovered with no operator action.

## K.4 THE MEASUREMENT — the pose inter-arrival while the vehicle is moving

`V2B-DESIGN.md` §4.3 published the display ramp's endpoints as **display
values** and asked for exactly this: the inter-arrival distribution of the
localization pose **while moving**, with its n.

**How an arrival is timed.** Polling cannot time an arrival. But the payload
carries `pose_age_ms`, measured by the monitoring service on its own steady
clock at the instant it answers, so `arrival = (reply instant) − (age in that
reply)`, and the difference of two of those is a difference of two of the
service's own measurements. The poll rate then decides only how often a new
arrival is *noticed* — by `messages_received.pose` increasing, never by the age
falling, which cannot tell one new message from three. Across all four runs,
**0 intervals spanned more than one message**, so the poll was fast enough
everywhere.

**Conditions.** Measured through the HMI backend's own `/monitor/state` — the
path the page reads — with the vehicle, Gazebo, Nav2 and the real service in
WSL and the backend and the PLC double on Windows. **No browser was running and
no capture was in progress**: the measurement runs and the screenshot runs were
kept apart deliberately (`docs/LESSONS.md` 2026-07-30 #88). Effective poll rate
13.4–15.5 Hz against 20 Hz asked, each poll being two upstream GETs.

| Run | Commanded | n (moving) | median | p90 | p95 | max | achieved speed (median) |
|---|---|---|---|---|---|---|---|
| run 2 | 0.35 m/s, 60 s legs | **26** | 831 ms | 1007 ms | 1205 ms | 1550 ms | 0.346 m/s |
| run 3b | 0.35 m/s, 14 s legs | **77** | 910 ms | 1095 ms | 1502 ms | 2099 ms | 0.328 m/s |
| run 4 | 0.15 m/s, 30 s legs | **37** | 2314 ms | 6010 ms | 6196 ms | 6446 ms | 0.120 m/s |

**The structure behind those numbers is the real finding.** AMCL is
**distance-triggered**, not periodic: `agv/forklift/amcl.yaml` sets
`update_min_d: 0.25` and `update_min_a: 0.2`. Every measured interval covered
0.28–0.30 m of ground, in every run, at every speed. So

> the pose inter-arrival is **`update_min_d / speed`**, and a threshold written
> in milliseconds is therefore a threshold written about a **speed**.

`1000 ms` says *"fade once the vehicle is slower than 0.25 m/s"*. `5000 ms`
says *"call it a last known position once it is slower than 0.05 m/s"*. Neither
sentence was intended when the numbers were chosen; both are now measured
rather than guessed.

### K.4.1 Do the chosen thresholds survive it? Partly — and the failures run in the safe direction

| Endpoint | Verdict |
|---|---|
| `POSE_AGE_RAMP_START_MS = 1000` | **Does not survive.** It sits essentially *at the median* of brisk driving (831 / 910 ms), so a vehicle driven at the commissioning speed is past the ramp start on roughly half of all cycles and is drawn perpetually part-faded. p95 is 1.2–1.5 s and the maximum 2.1 s — all above it |
| `POSE_AGE_RAMP_FULL_MS = 5000` | **Survives brisk driving** with 2.4× margin over the measured maximum (2099 ms). **Does not survive slow driving**: at 0.15 m/s the p90 is 6010 ms and the maximum 6446 ms, so a vehicle that is genuinely being driven gets labelled `LAST KNOWN POSITION` |

**Both failures are in the under-claiming direction** — the page says it knows
less than it does, never more — which is the half of the pair `V2B-DESIGN.md`
§4.2 chose deliberately and which `docs/LESSONS.md` 2026-08-06 #101 asks for.
This is a **fidelity** finding, not a safety one.

### K.4.2 What is proposed, and why it is proposed rather than applied

Not applied. Widening a ramp makes the page claim **more**, and that is not a
direction an agent takes on its own measurement.

| Option | Change | What it buys | What it costs |
|---|---|---|---|
| **A — leave both** | none | the widest under-claiming margin at every speed | a vehicle driven at 0.15 m/s is labelled `LAST KNOWN POSITION` while it is visibly moving, which an operator will read as a defect |
| **B — widen to the measurement** | `START 1000 → 2500 ms`, `FULL 5000 → 8000 ms` | 2500 ms clears the brisk population's measured maximum (2099 ms), so a normally driven vehicle stays solid; 8000 ms clears the slow population's maximum (6446 ms), so `LAST KNOWN` means *not being driven* | if the localization dies while the vehicle keeps moving at 0.35 m/s, the marker stays solid for 2.5 s instead of 1.0 s — up to **0.88 m** of undisclosed travel instead of 0.35 m |

**Recommended: B**, with the two endpoints re-stated in `V2B-DESIGN.md` §4.3 as
*derived from `update_min_d` and a named speed* rather than as bare
milliseconds — because that is what they are, and written that way they carry
their own re-check rule: **if `update_min_d` changes, or if a slower driving
regime becomes normal, they are wrong again.** One such regime already exists
in this repository: the closed-loop smoother's from-rest floor of 0.025 m/s
(`docs/LESSONS.md` 2026-08-05 #124) implies a **~10 s** pose inter-arrival, at
which no fixed ramp keeps a creeping vehicle solid and the honest answer is
that the page cannot distinguish creeping from standing. It already says it
does not guess.

### K.4.3 The instrument defects the first runs found, recorded rather than quietly fixed

1. **Run 1's maximum was an artifact of its own boundary.** Seeding the
   previous arrival from whatever pose was standing when the run began made the
   first interval span the parking time *before* the run — `132.8 s`, which
   duly became the reported maximum of a measurement whose entire subject is
   the moving case. `hmi/evidence/pose-arrivals-2026-08-06-run1-moving.csv` is
   kept as the capture that showed it. Interval measurement now begins at the
   first arrival observed **inside** the run.
2. **"While moving" cannot be qualified by distance.** The first classifier
   asked whether the vehicle had covered ≥ 0.20 m between two arrivals — and
   passed **35 of 35** intervals, a 50.9-second stall included, because a
   distance-triggered estimator makes *every* interval cover that distance by
   construction. The classifier is now **implied speed**, it is an argument
   with no hidden default, and both populations print side by side. Under it
   the same run 2 splits 26 moving / 9 stalled. Both CSVs remain re-analysable
   with `--analyse`, so the split can be moved without re-driving the vehicle.
3. Run 3's CSV write raised `AttributeError` on a renamed argument *after* the
   summary had printed, so its samples were lost. It was repeated as run 3b
   rather than quoted from the console, and the empty file it left was deleted.

### K.4.4 A vehicle-layer observation, offered and not acted on

In every run the forklift moved for 10–17 s and then stalled for the rest of
the leg — implied speed falling to 0.006 m/s while the traction command was
still being published at 20 Hz — and resumed on the next reversal. It is
visible in all four CSVs as the stalled population (24 of 132 intervals in one
run). It is **not** a monitoring-plane or HMI matter and nothing here depends
on it; it is recorded because it will affect anyone driving this vehicle, and
it belongs to the vehicle layer.

## K.5 What this section does *not* prove

- **The PLC is still a double.** Zones A–F are rehearsed. No M4 or M5 process
  claim is touched by this run.
- **n = 1.** One serial. The pane reads the served list rather than a constant,
  but the second vehicle is the test and it does not exist.
- **The read-only claim is unchanged and unshortened.** `viz/DESIGN.md` §2 owns
  it and it appears here only in its full form: **read-only by construction of
  the process and proven by test; not enforced by the middleware.** This run
  added nothing that writes — the HMI still sends `GET` and nothing else toward
  the monitoring service, and the eight-node OPC UA write set did not grow.
- **The crossing is a property of this machine's WSL configuration**, recorded
  in K.1 with the conditions it depends on. It is not a property of `hmi/`.

## K.6 The motion stimulus, quoted so the run is reproducible

It is deliberately **not** a repository file. A ROS 2 publisher into a vehicle
domain cannot live in `hmi/` (this layer must not access ROS 2 at all) and this
brief may not write `agv/` or `sim/`; a permanent home for it is requested in
the report rather than taken. It exists because
`sim/scenarios/forklift_stimulus.py plant` shells out to `ros2 topic pub -r`,
and `viz/EVIDENCE_MONITORING.md` §5 records that exact form failing to take —
0.036 m of travel in 14 s (`docs/LESSONS.md` 2026-07-28 #72).

```python
# scratchpad/drive_f001.py — run as:
#   ROS_DOMAIN_ID=51 python3 drive_f001.py --speed 0.35 --shuttle 14 --seconds 190
import argparse, math, time
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64

ap = argparse.ArgumentParser()
ap.add_argument('--speed', type=float, default=0.35)
ap.add_argument('--steer', type=float, default=0.0)
ap.add_argument('--weave', type=float, default=0.0)
ap.add_argument('--weave-period', type=float, default=20.0)
ap.add_argument('--seconds', type=float, default=60.0)
ap.add_argument('--rate', type=float, default=20.0)
ap.add_argument('--shuttle', type=float, default=0.0)   # reverse every N s
args = ap.parse_args()

rclpy.init()
node = Node('m553b_drive_stimulus')
traction = node.create_publisher(Float64, '/forklift/cmd/traction_speed', 10)
steer = node.create_publisher(Float64, '/forklift/cmd/steer_angle', 10)
time.sleep(2.0)                      # let discovery settle before message one

period, started = 1.0 / args.rate, time.monotonic()
deadline, n, last_leg = started + args.seconds, 0, [-1]
while time.monotonic() < deadline:
    t = time.monotonic() - started
    a = args.steer
    if args.weave:
        a += args.weave * math.sin(2.0 * math.pi * t / args.weave_period)
    v = args.speed
    if args.shuttle:
        leg = int(t // args.shuttle)
        if leg % 2:
            v, a = -v, -a
        if leg != last_leg[0]:
            print('leg {} traction {:+.2f}'.format(leg, v), flush=True)
            last_leg[0] = leg
    traction.publish(Float64(data=float(v)))
    steer.publish(Float64(data=float(a)))
    n += 1
    time.sleep(period)

# THE TERMINAL VALUE, EXPLICITLY, AND HELD. A downstream consumer republishes
# the last command at a fixed rate, so ceasing to publish is a standing order
# to keep driving (docs/LESSONS.md 2026-08-04 #135, #136).
stop_until = time.monotonic() + 1.5
while time.monotonic() < stop_until:
    traction.publish(Float64(data=0.0))
    steer.publish(Float64(data=0.0))
    time.sleep(period)
print('drive_f001: {} command pairs, then zero held 1.5 s'.format(n))
node.destroy_node()
rclpy.shutdown()
```

## K.7 THE RULING APPLIED — the ramp moved to 2500 / 8000 ms (2026-08-06)

The owner ruled on §K.4.2 and chose **option B**. `POSE_AGE_RAMP_START_MS` and
`POSE_AGE_RAMP_FULL_MS` in `hmi_server.py` are now **2500** and **8000 ms**.
There is no second place to change: the page reads both from
`/monitor/state` on every poll, `config.yaml` is forbidden a threshold, and the
sweep for a hard-coded `1000`/`5000` in `hmi/static/index.html` and the
instruments came back empty.

`V2B-DESIGN.md` §4.3 now carries the ruling, its date, the reasoning, **the
cost**, and the re-check rule; the same is written beside the constants
themselves. The three things that had to stay attached to the numbers:

1. **Why the old pair was wrong** — `1000 ms` sat at the *median* of brisk
   driving (831 / 910 ms measured), so the page called a normally driven vehicle
   stale about half the time; `5000 ms` was crossed by a vehicle genuinely being
   driven at 0.15 m/s (p90 6010 ms). Both failures under-claimed rather than
   over-claimed, which is why this was fidelity and not safety.
2. **The cost, carried forward** — widening a ramp makes the page claim *more*.
   If the localization dies while the vehicle keeps moving at 0.35 m/s, the
   marker is now solid for 2.5 s rather than 1.0 s: **up to 0.88 m of
   undisclosed travel instead of 0.35 m**. First trade of that margin on this
   pane, and the reason it needed an owner.
3. **The finding that stops a blind re-tune** — the localizer is
   *distance-triggered*, so inter-arrival = `update_min_d / speed` and each
   endpoint is a covert statement about a speed (`2500 ms` = "fade below
   0.10 m/s"; `8000 ms` = "last known below 0.031 m/s"). **No fixed pair
   survives from the creep floor to full travel**: at the smoother's 0.025 m/s
   from-rest floor the inter-arrival is ~10 s and a creeping vehicle still
   crosses the ramp — correctly, because the page cannot tell creeping from
   standing and says so.

### K.7.1 What was re-run, and what was deliberately not

**Re-run in full: the backend half.** `check_hmi_map_pane.py`, all seven checks
**PASS**, log `hmi/evidence/check-map-pane-2026-08-06-ramp2500-8000.log`. The
ramp check reads back `2500.0 .. 8000.0 ms`. The write allowlist is still
exactly eight nodes and the method matrix is unchanged.

**Not re-captured: the screenshots whose appearance does not change.** A pose at
0.6 s is solid under both pairs; a pose at 9.2 s is a `LAST KNOWN POSITION`
under both; the service-down and recovery states have no pose at all. Re-taking
them would have destroyed a comparison for nothing (`docs/LESSONS.md`
2026-08-06). **Exactly two age bands changed appearance, and both were
photographed** by a new `rampband` pass under the distinct prefix
`v2b-real-ramp-*`, so §K.3's captures are untouched and the two runs sit side by
side.

| Band | Under 1000 / 5000 | Under 2500 / 8000 | New capture |
|---|---|---|---|
| 1000–2500 ms | fading, 0 px of marker fill | **solid** | `v2b-real-ramp-08-band-1000-2500ms-now-solid-2026-08-06.png` — 1.1 s old, **52 px** of fill |
| 5000–8000 ms | `LAST KNOWN POSITION` | **faded, but not last-known** | `v2b-real-ramp-09-band-5000-8000ms-not-yet-last-known-2026-08-06.png` — 5.3 s old, reads `pose as of 5.3 s` |
| past 8000 ms | (past 5000: last-known) | still `LAST KNOWN`, no fill | `v2b-real-ramp-10-past-8000ms-last-known-2026-08-06.png` — 10.1 s old, 0 px |

**The before-halves of both comparisons already exist and were not re-taken:**
`v2b-real-07` caught a **2.7 s** pose with **0 px** of fill under the old ramp,
and `v2b-real-04` caught a **9.2 s** pose labelled `LAST KNOWN`. Ten checks in
the new pass, **all passing**, including that the backend is publishing exactly
`2500 / 8000`, that the obstacle layer is unaffected (the ramp is the *pose's*
and the two ages stay independent), and that the last-known label still arrives
— widening moved *when* it arrives, it did not remove it. Log:
`hmi/evidence/capture-v2b-real-ramp-2026-08-06.log`.

### K.7.2 Two checks moved, and neither was weakened

**CHECK 4 of the backend half was found flaky, and the mechanism was proved
before it was attributed.** It failed on the first run after the ramp change —
`871 vs 871 bytes` — on a proxy path the change does not touch. A probe against
the double compressed the same grid at three inter-request gaps:

```
gap  0.0s  raw equal: True    decompressed equal: True   differing offsets: []
gap  0.4s  raw equal: False   decompressed equal: True   differing offsets: [4]
gap  1.1s  raw equal: False   decompressed equal: True   differing offsets: [4]
           a[0:10]=1f8b08003eaa746a02ff   b[0:10]=1f8b08003faa746a02ff
```

**Byte 4 only** — the wall-clock `MTIME` that RFC 1952 puts in every gzip
header. The check makes two independent GETs, so the service compresses twice;
whether the bytes match was decided by which side of a second boundary the two
requests landed on, and m5-53's run happened to land both inside one second. It
was a latent flake in the instrument, **not** a regression from the ruling.

The fix compares the body with those four bytes excised — the whole deflate
stream still bit for bit, so a re-encode by this backend would still fail — and
**adds** a comparison of the decompressed cells, which the raw test never made.
Strictly more is checked than before.

**The `rampband` pass itself failed its first attempt, correctly.** It gated on
the *backend's* age and photographed a **0.9 s** pose while asserting it was
inside the 1000–2500 ms band. 0.9 s is solid under both ramps, so that capture
would have illustrated nothing about the change it exists to show. The check
caught it; the gate now reads **the age the page is displaying**, because the
map pane polls on its own 500 ms period and the DOM trails the backend by up to
one poll. The re-run landed 1.1 s and 5.3 s, both inside their bands.

### K.7.3 What did not move

Nothing else in this file. The eight-node write set, the method matrix, the H6
beacon exclusion, the whole-map assertions, the process-plane isolation and the
`—`-on-unreachable behaviour are all unchanged and re-passed. The read-only
claim is untouched and appears only in its full form: **read-only by
construction of the process and proven by test; not enforced by the
middleware.** No file outside `hmi/` was written.
