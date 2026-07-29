# EVIDENCE — connect conformance to the commissioned server (m3-21)

Dated capture of the bridge's **session establishment**: the two-namespace
browse path of `docs/interfaces/bridge-design.md` §3.1 and the granted-timeout /
derived-keep-alive rules of §3.2. Both are commissioning facts about the
S7-1500 (phase 0, 2026-07-27) that the pre-commissioning client did not satisfy
(§12 open item 9).

**Server: the test double, not a PLC.** Every number below was produced by
`bridge/test_double/plc_test_double.py` in WSL2. Nothing here is evidence about
the PLC program, about PLCSIM's timing, or about the network path — see
"What this does not establish" at the end. `EVIDENCE_LATENCY.md` Section B
remains the owner-run PLCSIM capture, and it is where this run must be repeated.

> **A second dated capture, m4f-06 (2026-07-29), sits at the end of this file**:
> the forklift signal group carried both ways, the write allowlist derived from
> the configured groups, the HMI-group negative test, and the rewrite after a
> server restart over all eleven configured inputs. The m3-21 capture below is
> unchanged, and the cell conformance it records was re-run there.

| Item | Value |
|---|---|
| Date | **2026-07-27**, 22:00–22:09 local (`/tmp/m321_observe.csv` stamps are UTC) |
| Host | WSL2 Ubuntu 24.04.4, kernel `5.15.167.4-microsoft-standard-WSL2`, headless |
| Repo | `/mnt/c/Users/ozkan/projects/amr-agent` (Windows checkout, driven from WSL) |
| venv | `/home/ozkan/amr-bridge-venv` (`--system-site-packages`), `asyncua 2.0.1` |
| Config | `bridge/config/bridge.yaml`, unmodified, endpoint `opc.tcp://127.0.0.1:4840/amr-agent/celldouble/` |
| Isolation | `ROS_DOMAIN_ID=88`, `GZ_PARTITION=m321bridge` |
| Raw evidence | `evidence/connect-conformance-2026-07-27.csv` (run 1) |

The double is configured to make both rules falsifiable:

| Double behaviour | Setting | Why |
|---|---|---|
| Two namespaces, **indices unlike PLCSIM's** | three filler namespaces registered first, so `ServerInterfaces` lands at **5** and `DemoCell` at **6**, where phase 0 saw `ServerInterfaces` at **3** | a bridge that hardcoded either index cannot resolve on both servers |
| Session timeout **revised** | `--min/--max-session-timeout-ms`, default window `[5000, 8000]` ms | the bridge requests 10 000 ms, so the grant is **8000 ms — below the request** |

---

## 1. Conformance harness, grant clamped BELOW the request

`bridge/tools/check_connect_conformance.py` drives `PlcClient._connect`, the
bridge's own session establishment — not a reimplementation.

```
bridge connect conformance — bridge-design.md §3.1 / §3.2
  config   /mnt/c/Users/ozkan/projects/amr-agent/bridge/config/bridge.yaml
  endpoint opc.tcp://127.0.0.1:4840/amr-agent/celldouble/

1. §3.1 — both namespaces resolved by URI, indices not hardcoded
   ok   both namespace URIs were resolved at session establishment — http://www.siemens.com/simatic-s7-opcua -> 5, http://DemoCell -> 6
   ok   the two indices differ, so one index cannot qualify both elements — ServerInterfaces 5, DemoCell 6
   ok   this server's ServerInterfaces index differs from PLCSIM's phase-0 index — 5 here vs 3 on PLCSIM
   ok   all 15 §9 nodes resolved through Objects/ServerInterfaces/DemoCell — 15 nodes
        interface path in force this session: Objects/5:ServerInterfaces/6:DemoCell

2. §3.1 N1/N3 — the paths that would 'work by accident' do not resolve
   ok   DemoCell does not hang directly under Objects (N1: the pre-m3-21 path) — BadNoMatch
   ok   the single-namespace path from Objects addresses nothing (N1) — BadNoMatch
   ok   ServerInterfaces is not in the interface namespace (N3) — BadNoMatch
   ok   DemoCell is not in the Siemens namespace (N3) — BadNoMatch

3. §3.2 — the granted session timeout is read back and the keep-alive derived from it
   ok   the server revised the request, so the two values are distinguishable in this run — requested 10000 ms, granted 8000 ms (below the request)
   ok   the keep-alive period is the granted timeout / 3 — 2.667 s
   ok   it is NOT the value the request would have produced — 3.333 s would have been the wrong answer
   ok   at least 3 exchanges fall inside the granted window — 3 x 2.667 s <= 8.000 s

4. §3.2 S3 — idle for 12.0 s (> the granted 8.0 s) with no cycle running
   ok   the bridge's own keep-alive exchanges fired while the cycle was idle — 4 exchanges in 12.0 s
   ok   no keep-alive exchange failed
        measured spacing ['2.668', '2.668', '2.669'] s
   ok   the measured cadence matches the grant-derived period, not the request-derived one — measured 2.669 s; grant-derived 2.667 s; request-derived 3.333 s
   ok   the session outlived the granted timeout while idle — ConveyorSpeedCommand read back as 0.0

5. §3.1 N4 — a missing namespace URI fails the connect, in both namespaces
   ok   a wrong server_interfaces URI raises NamespaceNotFound
   ok   a wrong interface URI raises NamespaceNotFound

RESULT: PASS
```

**Why §4 measures the cadence rather than only the survival.** The session
surviving a 12 s idle window is *over-determined*: `asyncua`'s own health probe
also touches the server every second, so survival alone would prove nothing
about the derivation. The **spacing** of the bridge's own keep-alive rows does:
2.668 s is granted/3, and 3.333 s — what the request would have produced — is
excluded by measurement, not by argument.

## 2. Same harness, grant raised ABOVE the request

The commissioned CPU granted **more** than it was asked for (30 000 ms against a
3 600 000 ms request), so §3.2 must hold in both directions. Double restarted
with `--min-session-timeout-ms 30000 --max-session-timeout-ms 60000`:

```
3. §3.2 — the granted session timeout is read back and the keep-alive derived from it
   ok   the server revised the request — requested 10000 ms, granted 30000 ms (above the request)
   ok   the keep-alive period is the granted timeout / 3 — 10.000 s
   ok   it is NOT the value the request would have produced — 3.333 s would have been the wrong answer
   ok   at least 3 exchanges fall inside the granted window — 3 x 10.000 s <= 30.000 s

4. §3.2 S3 — idle for 45.0 s (> the granted 30.0 s) with no cycle running
   ok   the bridge's own keep-alive exchanges fired while the cycle was idle — 4 exchanges in 45.0 s
        measured spacing ['10.003', '10.002', '10.003'] s
   ok   the measured cadence matches the grant-derived period, not the request-derived one
   ok   the session outlived the granted timeout while idle

RESULT: PASS
```

30 000 ms is the value the commissioned S7-1500 granted, so **10.000 s is the
keep-alive the owner's PLCSIM run should log** — one number to check the live
capture against.

## 3. The production path: `run_bridge.py`, unmodified config

No harness, no test hook — the process the owner will start:

```
22:04:29,764 WARNING asyncua.client.client Requested session timeout to be 3600000ms, got 8000ms instead
22:04:29,766 INFO bridge.opcua session timeout: requested 10000 ms, granted 8000 ms — clamped BELOW the request; the granted value is the only one in force (§3.2 S2)
22:04:29,766 INFO bridge.opcua secure channel lifetime: requested 3600000 ms, granted 3600000 ms — revised by the same mechanism (§3.2 S6)
22:04:29,766 INFO bridge.opcua keep-alive interval 2.667 s = granted 8000 ms / 3 (§3.2 S3); derived from the request it would have been 3.333 s, which is not used
22:04:29,769 INFO bridge.opcua namespace http://www.siemens.com/simatic-s7-opcua (server_interfaces) resolved to index 5
22:04:29,770 INFO bridge.opcua namespace http://DemoCell (interface) resolved to index 6
22:04:29,781 INFO bridge.opcua browse path: Objects/5:ServerInterfaces/6:DemoCell
22:04:29,788 INFO bridge.opcua all node DataTypes match opcua-nodes.md §9
22:04:29,788 INFO bridge.opcua session established, 15 nodes resolved
```

**Read the library's warning line with care.** `asyncua` prints
"Requested session timeout to be 3600000ms" — 3 600 000 is its *secure channel*
default, not the session timeout the bridge asked for (the library logs the
wrong attribute). It is one reason the bridge logs both numbers itself instead
of relying on that line.

## 4. Full-loop regression against the new address space

The change is to addressing and session housekeeping, so the loop was re-run to
show nothing else moved: headless `sim/launch/cell_bringup.launch.py`, the
double, `tools/cell_stimulus.py` for the four panel contacts, and the bridge for
40 s.

| Counter | Value | Reading |
|---|---|---|
| `cycles` | **800** in 40.0 s | 20.0 Hz achieved, the §5 cadence |
| `heartbeat_writes` | **792** | the startup rule held the first 8 cycles, then the heartbeat advanced (R3) |
| `write_errors`, `read_errors`, `reconnects` | **0, 0, 0** | every §9.9 signal traversed the two-namespace path |
| `keepalive_probes` | **0** | correct: a 50 ms cycle touches the server ~20 ×/s, so an idle period never elapses. The keep-alive adds no traffic to a healthy run |

Server-side view at the end of the run (`/tmp/m321_observe.csv`, the double's own
log): `BridgeHeartbeat 792`, `ProductSensorRange 1.4400883913040161`,
`PanelStopCircuitClosed True`, `PanelProcessStopCircuitClosed True`,
`PanelStartPressed False`, `PanelResetPressed False` — the input image of a real
cell, addressed through `Objects/5:ServerInterfaces/6:DemoCell`.

## 5. Reconnect: every new session re-resolves and re-derives (§8.1, §3.2 S4)

The double was killed under a live bridge and restarted 5 s later:

```
22:08:09,146 WARNING bridge.opcua session broken: read ConveyorSpeedCommand: client is disconnected — degraded mode, no signal invented
22:08:09,146 INFO    bridge.opcua session closed (session broken); no farewell value written, nothing zeroed
22:08:10,148 WARNING bridge.opcua connect failed: [Errno 111] Connect call failed ('127.0.0.1', 4840); retrying in 2.0s
22:08:12,151 WARNING bridge.opcua connect failed: [Errno 111] Connect call failed ('127.0.0.1', 4840); retrying in 4.0s
22:08:16,161 INFO    bridge.opcua session timeout: requested 10000 ms, granted 8000 ms — clamped BELOW the request; ...
22:08:16,161 INFO    bridge.opcua keep-alive interval 2.667 s = granted 8000 ms / 3 (§3.2 S3); ...
22:08:16,162 INFO    bridge.opcua namespace http://www.siemens.com/simatic-s7-opcua (server_interfaces) resolved to index 5
22:08:16,163 INFO    bridge.opcua namespace http://DemoCell (interface) resolved to index 6
22:08:16,171 INFO    bridge.opcua browse path: Objects/5:ServerInterfaces/6:DemoCell
22:08:16,176 INFO    bridge.opcua session established, 15 nodes resolved
```

Both indices, all 15 NodeIds, the grant and the keep-alive are established again
on the new session; nothing is carried across. `auto_reconnect` is off in the
client deliberately, so a session can only be created by the code that does all
of that (`_connect`).

This particular run had **no panel stimulus**, so the four panel slots were
empty throughout and the heartbeat stayed withheld by R3 before *and* after the
reconnect. R4's "refresh all seven inputs from the current slots, then resume
the heartbeat" is captured in `EVIDENCE_SIGNAL_LOSS.md` §C.4, not here.

## 6. Connect failures no longer leave a session behind

A namespace or NodeId failure happens **after** `CreateSession`. The retry loop
now closes that half-open session before sleeping — visible in the raw evidence
as a `session,disconnect,conformance probe` row after each failed probe of §5.
On a server that limits concurrent sessions, retrying every second without this
would exhaust them while looking like a namespace problem.

## 7. A stale or index-bearing config fails loudly

The loader's guards were exercised against mutated copies of the committed
config, so a checkout that still carries the pre-commissioning shape cannot start
the bridge and silently browse the wrong path:

```
   ok   the pre-m3-21 shape (namespace_uri + nodes.root) is rejected
          unknown key(s) in [opcua]: ['namespace_uri'] ...
   ok   a missing second namespace URI is rejected
          [opcua.namespace_uris] must have exactly the keys ['server_interfaces', 'interface'] ...
   ok   a namespace index written where a URI belongs is rejected
          [opcua.namespace_uris.interface] is '4', a namespace *index* ...
   ok   a BrowseName carrying an index is rejected
          [nodes.interface_path[1]] is '4:DemoCell' ...
   ok   an interface_path whose last element is not the interface namespace is rejected
```

---

## What this does not establish

| Not established here | Why |
|---|---|
| Anything about the PLC program | The double runs none. `Status/*` and `BridgeLinkOk` held their start values, as always against the double |
| PLCSIM's namespace indices | Phase 0 observed `ServerInterfaces` at 3; **3 is evidence that the indices differ between servers, not a value to configure**. The passing run above is against 5 and 6 |
| PLCSIM's grant | 30 000 ms was observed for a 3 600 000 ms request. What it grants for the configured 10 000 ms request is an owner-run observation, and it may land either side of it |
| Session-loss timing on a real server | Unchanged from `EVIDENCE_SIGNAL_LOSS.md`: the double drops a session within ~2 s of a client kill; the S7-1500 may hold it for the granted timeout (§3.2 S5) |
| Any latency figure | This file measures no signal path. `EVIDENCE_LATENCY.md` owns L1–L7 |
| Security | The double is policy `None`, anonymous. The commissioned CPU is too (phase 0), so no certificate path is exercised on either side |

## What the owner should check in the PLCSIM run

1. Two `namespace ... resolved to index N` lines, with **PLCSIM's** indices, and
   `browse path: Objects/<n>:ServerInterfaces/<m>:DemoCell` — no config change
   between that run and this one except `opcua.endpoint`.
2. `session timeout: requested 10000 ms, granted <N> ms`, and the keep-alive line
   showing `<N>/3`. If the CPU grants 30 000 ms, the keep-alive must read
   **10.000 s**.
3. `all node DataTypes match opcua-nodes.md §9` and `15 nodes resolved`.
4. That `bridge/tools/check_connect_conformance.py` is **not** run against
   PLCSIM: its idle test deliberately stops exercising a session, and
   `bridge-design.md` §10 keeps the double and PLCSIM off the same endpoint.

---
---

# 2026-07-29 — the forklift signal group against the double (m4f-06)

Dated capture of the **configured signal set** of `bridge-design.md` §2.1 in
force: the forklift group (`opcua-nodes.md` §10) carried both ways beside the
cell group, the write allowlist **derived** from the configured groups, the
`Forklift/Hmi/` group proven untouched against a server that would have accepted
the write, and the restart rewrite covering every configured input.

**Server: the test double, not a PLC**, exactly as above. Nothing here is
evidence about the PLC program, about the forklift function block, or about the
commissioned `Forklift/` subtree — which is a **design value until the owner
reads it back out of TIA Portal** (`opcua-nodes.md` §10.2 step 6,
`bridge-design.md` §12 item 10). The bridge was never pointed at PLCSIM in this
run; both configurations name a loopback endpoint and the harness refuses a
`192.168.*` one.

| Item | Value |
|---|---|
| Date | **2026-07-29**, run started `2026-07-29T05:20:47Z` (log lines are guest local, UTC+2) |
| Host | WSL2 Ubuntu 24.04, `/mnt/c` checkout, headless |
| venv | `/home/ozkan/amr-bridge-venv` (`--system-site-packages`), `asyncua 2.0.1` |
| Isolation | `ROS_DOMAIN_ID=61`; four double endpoints, ports 4842–4846, none of them PLCSIM's |
| Configs | `bridge/config/bridge-double-both.yaml`, `bridge-double-forklift.yaml`, and `bridge/config/bridge.yaml` **unmodified** for the two cell harnesses |
| Bridge | the real process, `bridge/run_bridge.py`, started as a child of the harness — nothing stubbed |
| Plant | `bridge/tools/check_forklift_slots.py`'s own ROS 2 node, publishing the §9.9 and §10.10 topics at 10 Hz. Stimulus, in the standing of `tools/cell_stimulus.py` |
| Raw evidence | `evidence/latency-2026-07-29-m4f06-double-both-20260729T052049Z-pid54159.csv.gz`, `…-double-forklift-20260729T052122Z-pid54208.csv.gz`, `evidence/bridgelog-2026-07-29-m4f06-*.log.gz`, `evidence/double-observe-2026-07-29-m4f06-*.csv.gz`, `evidence/console-2026-07-29-m4f06.log.gz`, `evidence/connect-conformance-2026-07-29.csv` |

Four runs, in order, each with its own double: the forklift slots harness, the
write-allowlist check, and the two **existing cell harnesses on the unmodified
cell config**. Every process had stopped before its capture was archived
(LESSONS 2026-07-28).

## m4f-06.1 The configured signal set, as the bridge states it at startup

```
    configured signal set: cell+forklift — cell 7in/1out/6diag (opcua-nodes.md §9), forklift 4in/3out/5diag (opcua-nodes.md §10); 11 input slots, 4 output slots, 11 diagnostics, 27 nodes touched, write allowlist 12 keys
```

and, for the forklift-only run:

```
    configured signal set: forklift — forklift 4in/3out/5diag (opcua-nodes.md §10); 4 input slots, 3 output slots, 5 diagnostics, 13 nodes touched, write allowlist 5 keys
   ok   and the session resolved exactly those 13 — 2026-07-29 07:21:22,162 INFO    bridge.opcua session established, 13 nodes resolved for group(s) forklift
```

Both match §2.1's table — 15 / 13 / 27 nodes touched — and the 13 includes the
shared `DemoCell/Link/BridgeHeartbeat`, which is a §9 node every configuration
uses.

## m4f-06.2 Every input slot carries a ROS value into its node

```
A. every configured input slot carries a ROS value into its node (§4.1, §4.7)
   ok   an independent read-only session sees all 11 published values on their nodes — BridgeHeartbeat=13
   ok   ForkliftForkHeight carried unchanged — 0.8399999737739563
   ok   ForkliftLinearSpeed carried unchanged — -0.6200000047683716
   ok   ForkliftObstacleMinDistance carried unchanged — 3.75
   ok   ForkliftObstacleInStopZone carried unchanged — False

A'. the same slots carry a SECOND value, and the field bit both ways, uninverted (§4.7 row 12)
   ok   ForkliftForkHeight followed the plant to its second value — 0.10999999940395355 (was 0.84)
   ok   ForkliftLinearSpeed followed the plant to its second value — 1.3700000047683716 (was -0.62)
   ok   ForkliftObstacleInStopZone followed the plant to its second value — True (was False)
   ok   ForkliftObstacleMinDistance followed the plant to its second value — 0.05000000074505806 (was 3.75)
   ok   publishing TRUE on /forklift/obstacle/in_stop_zone writes TRUE — the non-permissive polarity is NOT inverted in transport — True
   ok   and publishing FALSE writes FALSE again — a level, not an edge — False
```

The read-backs are the single-precision neighbours of the published `float64`
values — `0.84 → 0.8399999737739563` — which is the `float64 → Real` narrowing
§4.7 permits and the only numeric operation anywhere on the path. The values
were read over an **independent** OPC UA session, so what is shown is the
server's own copy, not anything the bridge's session was holding.

## m4f-06.3 Every output slot republishes node changes to its ROS topic

```
B. every output slot republishes node changes to its ROS topic (§4.2, §4.8)
   ok   ConveyorSpeedCommand -> /cell/conveyor/cmd_speed = 0.15 (first round) — received 0.15000000596046448
   ok   ForkliftTractionSpeedRef -> /forklift/cmd/traction_speed = 0.55 (first round) — received 0.550000011920929
   ok   ForkliftSteerAngleRef -> /forklift/cmd/steer_angle = -0.9 (first round) — received -0.8999999761581421
   ok   ForkliftForkSpeedRef -> /forklift/cmd/fork_speed = 0.12 (first round) — received 0.11999999731779099
        all four arrived within 1.3 ms of each other (0.2s after the setpoints were written)
   ok   ConveyorSpeedCommand -> /cell/conveyor/cmd_speed = -0.05 (second round) — received -0.05000000074505806
   ok   ForkliftTractionSpeedRef -> /forklift/cmd/traction_speed = -0.25 (second round) — received -0.25
   ok   ForkliftSteerAngleRef -> /forklift/cmd/steer_angle = 1.05 (second round) — received 1.0499999523162842
   ok   ForkliftForkSpeedRef -> /forklift/cmd/fork_speed = 0.0 (second round) — received 0.0
        all four arrived within 1.1 ms of each other (0.1s after the setpoints were written)
```

The setpoints were written into the double's `Output/` nodes by hand through the
S1 back door (scaffolding, a human writing a number). `ForkliftForkSpeedRef = 0.0`
means *hold*, and the bridge translates it into nothing: it publishes `0.0`. The
"within 1.3 ms" line is the spread of the four arrival timestamps — one cycle
phase for all four output slots, as §4.8 requires.

## m4f-06.4 A server restart under a surviving session — and a residual larger than §8.1 states

```
C. a server restart under a surviving session rewrites EVERY configured input (§8.1, §7.3 case E)
   ok   before the restart the server holds the plant's values
        S5 warm restart 1: every node back to its start value in place, sessions left up
        (timed out after 3.0s waiting for the heartbeat read-back to notice the revert)
        that revert was masked by the bridge's own heartbeat write in the same cycle; triggering another
        S5 warm restart 2: every node back to its start value in place, sessions left up
   ok   the bridge detected the restart from its own heartbeat reading back a value it did not write — 101 ms after trigger 2; 1 earlier revert(s) masked (§8.1 restart residual — larger than the design's one-in-65536; see the m4f-06 report)
   ok   the write cache was invalidated and the image rewritten in one cycle
        2026-07-29 07:21:17,082 INFO    bridge.opcua input image rewritten after cache invalidation: 11 of 11 configured input nodes (ConveyorBeltPosition, ConveyorBeltSpeed, ProductSensorRange, ForkliftForkHeight, ForkliftLinearSpeed, ForkliftObstacleMinDistance, PanelStartPressed, PanelResetPressed, PanelStopCircuitClosed, PanelProcessStopCircuitClosed, ForkliftObstacleInStopZone)
   ok   the count in the log is every input of the configured set — log says 11 of 11
   ok   the rewrite is in the bridge's evidence file as 11/11 — written in one cycle; configured set cell+forklift
        input_image_rewritten rows in the evidence file: 0/11, 11/11
   ok   no session was lost, so nothing but the read-back could have noticed (§7.3 case E) — 0 broken-session row(s)
   ok   an independent session sees the whole image repaired — the two stop circuits and the forklift field bit included — repaired 862 ms after the trigger
```

**The rewrite count is read out of the bridge's own log line and out of its
evidence file — `11 of 11`, `11/11` — never computed here** (LESSONS
2026-07-27). The `0/11` row is the connect-time invalidation: at that instant no
slot had a real sample yet, and R1 forbids inventing one.

**The residual, measured.** One revert in this run was **masked**: it landed
between the cycle's step-0 heartbeat read-back and the cycle's own step-4
heartbeat write, so that write restored the witness and the next read-back
compared equal. The double's own 5 Hz observation log — the server's view, "what
the PLC sees" — shows what that costs. Every transition of the two level signals
in the whole phase, from `evidence/double-observe-2026-07-29-m4f06-both.csv.gz`:

```
2026-07-29T05:20:49.035+00:00 HB=0   stop=False zone=True     start values, heartbeat not yet running (R3)
2026-07-29T05:20:50.040+00:00 HB=1   stop=True  zone=False    R3 satisfied; the plant's values are written
2026-07-29T05:20:50.845+00:00 HB=17  stop=True  zone=True     the field bit driven TRUE by the plant (A')
2026-07-29T05:20:51.850+00:00 HB=37  stop=True  zone=False    and back to FALSE
2026-07-29T05:21:13.166+00:00 HB=463 stop=False zone=True     revert 1 — MASKED: the heartbeat keeps advancing
2026-07-29T05:21:17.179+00:00 HB=544 stop=True  zone=False    revert 2 detected, image rewritten 11/11
```

For **4.0 s** — 81 heartbeat increments — the server held an open stop circuit
and an obstacle in the stop field under a heartbeat that never faltered. That is
§7.3 case E exactly, and it ended only because the harness triggered a second
revert. On the commissioned cell the PLC would have qualified those inputs as
attributable, because the predicate §6.2 gives it is the heartbeat.

The window is measurable from the committed CSV — it is the interval from the
`read_rt BridgeHeartbeat` start to the `L2 BridgeHeartbeat` response, per cycle:

```
cycles n=558 median 50.015 ms p95 50.704 ms
masked window (HB read start -> HB write response) n=556 median 5.255 ms p95 7.886 ms max 10.143 ms
as a fraction of the median cycle: 10.5 %
```

So roughly **one revert in ten is invisible to the witness**, not one in 65536.
`bridge-design.md` §8.1's *Restart residual* row states only the
lands-on-the-same-value case. This is a **requested correction to that row**, not
a change made here: closing it needs a second witness, and §8.1 itself rules that
a second witness needs an owner. It is carried in
`docs/reports/m4f-06-bridge-forklift-slots.md`. Note that it is **not** a
forklift property: it was reproduced the same morning by the cell-only
`check_session_lifecycle.py` on the unmodified cell config.

Both harnesses now trigger reverts until one is caught, up to a bound, and report
how many were masked — a measurement instead of a coin toss.

## m4f-06.5 The HMI group: never touched, against a server that would accept the write

```
D1. the six nodes of §4.10 never moved on the server
   ok   Forklift/Hmi/HmiTractionRequest still holds its start value — 0.0
   ok   Forklift/Hmi/HmiSteerRequest still holds its start value — 0.0
   ok   Forklift/Hmi/HmiForkRequest still holds its start value — 0.0
   ok   Forklift/Hmi/HmiTeleopRequest still holds its start value — False
   ok   Forklift/Hmi/HmiResetRequest still holds its start value — False
   ok   Forklift/Link/HmiHeartbeat still holds its start value — 0
   ok   not one of the six appears anywhere in the bridge's log — not written, not read, not logged (§4.10) — none of HmiTractionRequest, HmiSteerRequest, HmiForkRequest, HmiTeleopRequest, HmiResetRequest, HmiHeartbeat
   ok   while HmiLinkOk IS logged: the PLC's verdict on the other client is a diagnostic the bridge may read, and the distinction is visible in the log
```

and, from `bridge/tools/check_write_allowlist.py` against a double serving that
group **writable**:

```
1. §4.10 — the allowlist is DERIVED from the configured groups
   ok   cell only: 8 keys = 7 configured Input/ node(s) + the one heartbeat — bridge.yaml: 15 nodes touched
   ok   forklift only: 5 keys = 4 configured Input/ node(s) + the one heartbeat — bridge-double-forklift.yaml: 13 nodes touched
   ok   both: 12 keys = 11 configured Input/ node(s) + the one heartbeat — bridge-double-both.yaml: 27 nodes touched
   ok   with both groups the allowlist holds exactly 12 keys — BridgeHeartbeat, ConveyorBeltPosition, ConveyorBeltSpeed, ForkliftForkHeight, ForkliftLinearSpeed, ForkliftObstacleInStopZone, ForkliftObstacleMinDistance, PanelProcessStopCircuitClosed, PanelResetPressed, PanelStartPressed, PanelStopCircuitClosed, ProductSensorRange
   ok   the six nodes of §4.10 are in no set at all — not the allowlist, not the read set, not the diagnostics poll — 27 node keys resolved, 27 nodes touched

2. client side — PlcClient._write refuses every key outside the allowlist
   ok   HmiTractionRequest: WriteNotPermitted — HmiTractionRequest is not in this run's write allowlist
   …  (16 keys refused: 4 cell Output/Status/Link, 6 forklift Output/Status/Link, the 5 Hmi requests, HmiHeartbeat)

3. §4.10 — the HMI group, against a server that WOULD have accepted the write
   ok   the server ACCEPTS a write to Forklift/Hmi/HmiTractionRequest from another client — read back 0.41999998688697815; the bridge's refusal is therefore its own
   …  all five requests and HmiHeartbeat accepted from an independent client, then restored

4. server side — the double refuses a direct write to a read-only node
   ok   DemoCell/Forklift/Output/ForkliftTractionSpeedRef — BadUserAccessDenied
   …  10 read-only nodes, both groups, all BadUserAccessDenied

5. §4.10 consequence 4 — the config loader rejects an Hmi node at startup
   ok   rejected: an Hmi request in a writable position
   ok   rejected: the HMI's heartbeat in the diagnostics poll

39 checks, 39 passed, 0 failed
RESULT: PASS
```

That is the negative test the design asks for: the refusal is the **bridge's**,
proven against a server that accepts the same write from another client, and it
is enforced twice — at the write helper and at the config loader.

## m4f-06.6 Figures, as the run printed them

Phase A, both groups, 559 cycles (~28 s of steady state at 20 Hz):

```
PHASE A figures, from latency-both-20260729T052049Z-pid54159.csv
        cycle interval R1            50.02 ms (n=558)
        heartbeat read-back RB       0.72 ms (n=556)
        per input slot — L2 write round trip:
          ConveyorBeltPosition           0.42 ms (n=557)
          ConveyorBeltSpeed              0.36 ms (n=557)
          ProductSensorRange             0.30 ms (n=557)
          PanelStartPressed              0.33 ms (n=2)
          PanelResetPressed              0.29 ms (n=2)
          PanelStopCircuitClosed         0.37 ms (n=2)
          PanelProcessStopCircuitClosed  0.31 ms (n=2)
          ForkliftForkHeight             0.29 ms (n=557)
          ForkliftLinearSpeed            0.28 ms (n=557)
          ForkliftObstacleInStopZone     0.26 ms (n=4)
          ForkliftObstacleMinDistance    0.29 ms (n=557)
        per output slot — L5 read-response to publish:
          ConveyorSpeedCommand           0.12 ms (n=559)
          ForkliftTractionSpeedRef       0.08 ms (n=559)
          ForkliftSteerAngleRef          0.06 ms (n=559)
          ForkliftForkSpeedRef           0.06 ms (n=559)
        R3 samples received/written per slot: ConveyorBeltPosition 278/557, ConveyorBeltSpeed 278/557, ProductSensorRange 278/557, PanelStartPressed 278/2, PanelResetPressed 278/2, PanelStopCircuitClosed 278/2, PanelProcessStopCircuitClosed 278/2, ForkliftForkHeight 278/557, ForkliftLinearSpeed 278/557, ForkliftObstacleInStopZone 278/4, ForkliftObstacleMinDistance 278/557
        counters: cycles=559, heartbeat_readbacks=556, heartbeat_suppressed_cycles=2, heartbeat_writes=557, inputs_rewritten_after_restart=11, publishes=2236, server_restarts_detected=1
```

Phase B, forklift only, 223 cycles:

```
PHASE B figures, from latency-forklift-only-20260729T052122Z-pid54208.csv
        cycle interval R1            49.98 ms (n=222)
        heartbeat read-back RB       0.67 ms (n=220)
        per input slot — L2 write round trip:
          ForkliftForkHeight             0.41 ms (n=221)
          ForkliftLinearSpeed            0.34 ms (n=221)
          ForkliftObstacleInStopZone     0.27 ms (n=1)
          ForkliftObstacleMinDistance    0.29 ms (n=221)
        per output slot — L5 read-response to publish:
          ForkliftTractionSpeedRef       0.12 ms (n=223)
          ForkliftSteerAngleRef          0.08 ms (n=223)
          ForkliftForkSpeedRef           0.06 ms (n=223)
        R3 samples received/written per slot: ForkliftForkHeight 111/221, ForkliftLinearSpeed 111/221, ForkliftObstacleInStopZone 111/1, ForkliftObstacleMinDistance 111/221
```

Reading R3: the plant published at 10 Hz and the cycle wrote at 20 Hz, so a
Real's `278/557` is the cyclic rewrite of an unchanged slot — **not** a freshness
statement (§4.7). A level signal's `278/4` is write-on-change plus the refreshes:
one at connect, one per commanded change, one after the restart.

## m4f-06.7 The cell harnesses, on the unmodified cell config

Both existing harnesses were re-run against a double, with
`bridge/config/bridge.yaml` unchanged apart from the `--endpoint` override each
already accepts:

```
RUN 3  cell connect conformance
   ok   all 15 nodes of the configured set resolved through Objects/ServerInterfaces/DemoCell — 15 nodes for group(s) cell
   ok   the node count matches bridge-design.md §2.1's table for this configuration — cell -> 15
   ok   the server revised the request, so the two values are distinguishable in this run — requested 10000 ms, granted 8000 ms (below the request)
   ok   the measured cadence matches the grant-derived period, not the request-derived one — measured 2.669 s; grant-derived 2.667 s; request-derived 3.333 s
RESULT: PASS

RUN 4  cell session lifecycle
   ok   every input of the configured set (7/7) was written in ONE cycle, not repaired gradually — 7/7
   ok   the bridge detected the restart from its own heartbeat reading back a value it did not write — 41 ms after trigger 1; 0 earlier revert(s) masked by the bridge's own heartbeat write in the same cycle
RESULT: PASS
```

The cell run still counts **seven** inputs and **15** nodes; the count comes from
the configured set in both cases and from a literal in neither.

## What this capture does not establish

| Not established here | Why |
|---|---|
| The commissioned `Forklift/` subtree | Its browse path, folder tree, per-tag rights and node count are design values until read back out of TIA Portal (`opcua-nodes.md` §10.2 step 6). The double serves what the document asks for, which is not the same thing as what the CPU will publish |
| Anything about the forklift PLC function block | The double runs no program: `Forklift/Status/*` and `Link/HmiLinkOk` held their start values for the whole run, as they always do against it |
| Anything about the HMI | Serving the `Hmi/` group is not playing the HMI (`bridge-design.md` §10). The values written in the negative test are scaffolding, and they were restored |
| Anything about the vehicle layer | The plant here is the harness's own publisher, not `agv/forklift/`. What it proves is that the bridge carries the topics of §10.10, at the types and polarity documented there |
| PLCSIM timing, the network path, or the PLC's scan | Loopback, in-container, no PLC. `EVIDENCE_LATENCY.md` Section B owns the PLCSIM figures |
| That a masked revert is rare | The opposite: it is measured at ~10 % of the cycle above, and the fix is not the bridge's to choose (§8.1) |
