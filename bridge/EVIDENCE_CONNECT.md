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
