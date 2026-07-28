# bridge

## This layer must not access

Per ADR 0005 D1. Every item is a hard boundary, not a preference.

- **Fleet manager code, state or configuration.** The bridge and the fleet
  manager are separate processes that share no state and call no code of each
  other's (ADR 0004, ADR 0005). Nothing under `fleet/` is imported here.
- **VDA 5050 and MQTT, in any form.** No broker connection, no topic, no
  message schema, no client library (invariant 3).
- **Order, traffic and zone-reservation concepts.** No order id, no
  assignment, no reservation, no vehicle (invariants 5, 6).
- **PLC program logic** — sequencing, interlocks, timers, latching. If logic
  appears to be needed, it belongs in the PLC (invariants 5, 6).
- **Any control decision whatsoever.** The no-logic rule of
  `docs/interfaces/bridge-design.md` §1.1 is the binding statement: the bridge
  applies no process decision to any signal, and the only numeric operation
  anywhere in it is unit-preserving type conversion (ROS `float64` → S7 `Real`,
  i.e. IEEE-754 double → single narrowing). No threshold, no scaling, no
  offset, no clamp, no ramp, no rounding, no averaging, no meaning-changing
  debounce, no latch, no re-issue after an outage, no "safe" default value.
- **Any safety function or safety path.** Nothing here is a safety device and
  nothing here carries safety integrity. Safety is onboard the vehicle and in
  the F-CPU; loss of this process is a degraded mode, never a safety event
  (invariants 1, 2). The panel's red mushroom carried by this bridge is a
  **process** stop, never an emergency stop (opcua-nodes.md §9.6).
- **The OPC UA server role.** The PLC is the server, this process is the
  client, and that direction is never inverted (invariant 4). The bridge never
  listens on a socket, in any configuration — including against the test
  double.
- **Nodes it is not allowed to write.** Only the `DemoCell/Input/` nodes (seven
  since `PanelResetPressed`, opcua-nodes.md §9.3) and
  `DemoCell/Link/BridgeHeartbeat` (opcua-nodes.md §9.1). Every write goes
  through one helper that rejects anything else; see
  `tools/check_write_allowlist.py`.
- **Secrets.** Endpoint credentials, certificates and keys live outside this
  repository and are referenced by absolute path (invariant 13).

Owns: the ROS 2 ↔ OPC UA signal transport for the M3 demonstration cell, its
configuration, its own liveness heartbeat, and its measurement instrumentation.

---

## What it is

One OS process that is an **OPC UA client** and a **ROS 2 node**, and nothing
else. Its whole job is to carry each signal of `docs/interfaces/opcua-nodes.md`
§9.9 from one side to the other, unchanged, and to write its own heartbeat.

```
   Gazebo cell (ROS 2)                          S7-1500 / PLCSIM (OPC UA server)
            |                                                    ^
   8 signals, 7 /cell/* topics                                    | client session
            v                                                    |
   +-------------------------------------------------------------------+
   |  bridge process                                                   |
   |  subscriber callbacks -> latest-value slots -> 50 ms cycle task   |
   |  cycle: read Output -> publish to cell -> write Inputs -> HB      |
   +-------------------------------------------------------------------+
```

| File | Contents |
|---|---|
| `run_bridge.py` | launcher |
| `amr_bridge/config.py` | config loading; **rejects unknown keys** so a threshold cannot be smuggled in through configuration |
| `amr_bridge/slots.py` | the depth-1 latest-value slots — the only buffering that exists, so nothing can be derived from discarded samples |
| `amr_bridge/ros_side.py` | subscriptions, one publisher, field addressing |
| `amr_bridge/opcua_side.py` | session, node resolution, type verification, the 50 ms cycle, the write allowlist, reconnect, and the heartbeat read-back that notices a restarted server |
| `amr_bridge/instrumentation.py` | per-event CSV recording (always on), one file per session |
| `config/bridge.yaml` | endpoint, **both** namespace URIs, BrowseName paths, topic names, cycle period, evidence paths — no thresholds, no tolerances, no timers, and no namespace index |
| `test_double/` | TEST SCAFFOLDING: an OPC UA server standing in for the S7-1500 |
| `tools/` | evidence summariser, panel stimulus (scaffolding), allowlist check, connect-conformance check, session-lifecycle check, read-only PLC observer (scaffolding) |
| `EVIDENCE_LATENCY.md`, `EVIDENCE_SIGNAL_LOSS.md`, `EVIDENCE_CONNECT.md`, `EVIDENCE_LIFECYCLE.md`, `evidence/` | dated captures, each qualified by the environment that produced it |

Where the no-logic rule is visible in the code:

* the single numeric operation is the `float64 → ua.VariantType.Float`
  narrowing in `opcua_side._input_path`, and the `Float → float64` widening in
  `_output_path`;
* inputs are held in depth-1 **slots**, never queues — `slots.py`;
* ROS subscriptions use `KEEP_LAST` depth 1, so the decimation is done by the
  middleware queue rather than by bridge code;
* every write passes `PlcClient._write`, which raises `WriteNotPermitted` for
  any node outside the §9.1 allowlist;
* `inf`/`NaN` range samples are written through unchanged, logged and counted;
* the reset contact is carried as a **level**, exactly like the other three:
  no edge detection, no hold timer, no latch and no pre-first-publish default
  anywhere in this process — before `/cell/panel/reset` first publishes, the
  bridge writes the node not at all and it keeps the PLC's own `FALSE` start
  value (R1);
* nothing is published on `/cell/conveyor/cmd_speed` unless it was read from
  the server in the same cycle — no default, no replay, no zero on shutdown.

## How to run it

### The venv — the mechanism, not one machine's path

`requirements.txt` explains why a venv is needed at all: `pip` will not replace
Debian's `cryptography`, so `asyncua` is installed beside it rather than over
it. What the bridge actually requires is only this:

* a venv created with **`--system-site-packages`**, so `rclpy` from
  `/opt/ros/jazzy` still imports inside it;
* created **anywhere the account running the bridge can write**. The path is
  not a project constant. `/opt` needs root on an ordinary Linux install, so
  outside a container it is usually the wrong choice;
* `/opt/ros/jazzy/setup.bash` sourced in **every** shell that runs the bridge,
  the cell or `gz`.

Set the two locations once per shell and the commands below are identical
everywhere:

```
REPO=<repo checkout>          # the directory containing this README's parent
VENV=<venv location>          # writable by the account running the bridge

python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install -r "$REPO/bridge/requirements.txt"
```

The two worked examples this project has actually used:

| Environment | `REPO` | `VENV` | Why |
|---|---|---|---|
| Development container (all committed evidence) | `/home/user/amr-agent` | `/opt/amr-bridge-venv` | runs as root, `/opt` is writable, nothing else shares the image |
| WSL2 Ubuntu 24.04 on the owner's machine | `/mnt/c/Users/ozkan/projects/amr-agent` | `/home/ozkan/amr-bridge-venv` | no passwordless sudo, so `/opt` is not writable (`sim/setup/WSL_ENVIRONMENT.md` §3.2) |

Both resolve the same dependency set — `asyncua 2.0.1` inside the venv,
Debian's `cryptography` left in place under `/usr/lib/python3/dist-packages`.

### Running

Three terminals:

```
# 1. the cell
source /opt/ros/jazzy/setup.bash
ros2 launch "$REPO/sim/launch/cell_bringup.launch.py"

# 2. an OPC UA server on the configured endpoint
#    - in production: the S7-1500 / PLCSIM Advanced
#    - for development: the test double, see below

# 3. the bridge
source /opt/ros/jazzy/setup.bash
"$VENV/bin/python" "$REPO/bridge/run_bridge.py" \
    --config "$REPO/bridge/config/bridge.yaml"
```

Options: `--duration <s>` (stop after N seconds; used for measurement runs),
`--evidence-csv <path>` (override the raw evidence file). Stop it with
SIGINT/SIGTERM — it closes the session and writes nothing on the way out.

`evidence.csv_path` in the config is **relative to the `bridge/` directory** and
therefore names no machine; `~` and `$VARS` are expanded and an absolute path is
honoured as written.

### One evidence file per session — never a truncation

Both `evidence.csv_path` and `--evidence-csv` are **stems**, not file names. The
recorder appends a per-session suffix and creates the file with `"x"`:

```
--evidence-csv bridge/evidence/latency-session.csv
  ->            bridge/evidence/latency-session-20260728T165131Z-pid35575.csv
```

The suffix is the UTC second the session started plus the pid, so it is derivable
from the run's own first log line (`evidence for this session: …`) rather than
random, and two starts in the same second still differ. Two consecutive starts
given the same argument therefore produce **two files**, and if a name ever does
collide the recorder refuses to start rather than overwrite — `"x"`, never `"w"`.

Because every file the code writes ends in `-pid<number>.csv`, one line in
`bridge/.gitignore` (`evidence/*-pid*.csv`) keeps ordinary runs out of `git
status` while leaving every dated, committed capture visible — none of those
carries a pid.

This replaces the old behaviour, in which the path was truncated at every start:
on 2026-07-28 seven bridge restarts sharing one dated path erased a day of 20 Hz
data and a measurement had to be repeated (`docs/LESSONS.md`). Nothing needs to be
remembered at run time any more; a run cannot destroy an earlier one.
`EVIDENCE_LIFECYCLE.md` §3 is the recorded two-start run. The same rule applies to
the double's `--observe-csv` and to the two conformance harnesses in `tools/`.

### What happens when the link or the server goes away

Both are connection management, and neither invents or withholds a signal
(`bridge-design.md` §8.1):

* **any** exception from an await that touches the session breaks the session and
  reconnects — not only the error types a broken link was expected to raise.
  `asyncua` re-raises an in-flight request failure as a bare `Exception` when the
  socket state has not yet flipped, and on 2026-07-28 that ended the process
  mid-run instead of reconnecting. Unanticipated types are counted
  (`unexpected_session_errors`) so a run still says how the session was lost, and
  `unrouted_cycle_errors` counts anything the last-resort guard in `run()` had to
  catch, which is a missing `except` to go and fix rather than a runtime
  condition. The two exceptions to the breadth are deliberate:
  `WriteNotPermitted` and `TypeMismatch` mean this process is wrong, and a
  reconnect loop would hide them;
* the bridge **reads its own `BridgeHeartbeat` back** at the top of every cycle.
  It is the only node outside `Input/` the bridge may write, so a value it did not
  write means the server restarted underneath a surviving session — a CPU warm
  restart reinitialising the data block. The per-session write cache is then
  dropped and every slot holding a real sample is rewritten in the next cycle,
  because write-on-change otherwise leaves a reverted contact reverted: on
  2026-07-28 the PLC read open stop circuits for minutes for exactly that reason.
  The test is an exact inequality against the last value written, not a threshold
  or a timer, and the value read is applied to nothing. It costs one read per
  cycle (0.79 ms median against the double) and is recorded as a `read_rt` row so
  the cost is measurable rather than asserted.

An outage is written into the evidence file as a `session,resumed` row carrying
its length, so a 20 Hz capture with a hole in it says so.

Pointing it at PLCSIM Advanced or real hardware is a **configuration** change
only: `opcua.endpoint`, and the security fields if the server requires them.
The code path is identical. The two namespace URIs are the same for the test
double and for the CPU — only the *indices* differ, and no index is written down
anywhere. Renaming the TIA server interface is the one change that also requires
editing `opcua.namespace_uris.interface`, because that name **is** the URI
(ADR 0006).

Summarise a run (the file, not the stem — the path the startup line printed):

```
"$VENV/bin/python" "$REPO/bridge/tools/summarize_latency.py" \
    "$REPO/bridge/evidence/latency-session-<UTC>-pid<pid>.csv"
```

### What the bridge logs at startup

Two `namespace ... resolved to index N` lines — the browse path crosses **two**
namespaces (`bridge-design.md` §3.1) and both are browsed by URI, never
hardcoded — then the resolved `browse path: Objects/<n>:ServerInterfaces/
<m>:DemoCell`, the requested and **granted** session timeout side by side with
the keep-alive derived from the granted value (§3.2),
`all node DataTypes match opcua-nodes.md §9`, the publisher-side QoS of every
subscribed topic (mismatched QoS is silent in ROS 2), and
`heartbeat withheld: no real sample yet for ...` until every input has carried
a real cell sample.

Every one of those lines is re-emitted on every reconnect, because a new session
re-resolves both indices and every NodeId, and re-reads what the server granted
(§8.1, §3.2 S4). Note that `asyncua`'s own
`Requested session timeout to be 3600000ms, got …` warning prints its *secure
channel* default rather than the requested session timeout — the bridge's own
line is the one to read.

## How to run the test double

The double is **test scaffolding**, never part of a demonstration run, and
never on the same endpoint as PLCSIM Advanced. Details and its limits:
`test_double/README.md`.

```
"$VENV/bin/python" "$REPO/bridge/test_double/plc_test_double.py" \
    --endpoint opc.tcp://127.0.0.1:4840/amr-agent/celldouble/ \
    --command-file /tmp/scaffold_speed \
    --observe-csv /tmp/double_observe.csv
```

* `--command-file` — writing a float into that file sets
  `DemoCell/Output/ConveyorSpeedCommand`. This is a human turning a knob
  through a back door in the double; it is **not** PLC logic and models
  nothing the PLC does.
* `--observe-csv` — server-side log of session count, heartbeat and the whole
  input image, sampled at 5 Hz. This is what "what the PLC sees" means in the
  evidence files.
* `--echo-input <NodeKey>` — optional wire from one input to
  `ConveyorSpeedCommand`, for the closed-loop L7 interval only. Off by default.
* `--warm-restart-file <path>` — touching that file reverts **every** node to its
  start value in place, with the server and every open session left up. It stands
  in for a CPU warm restart, which is the one server event a double that can only
  be killed cannot reproduce. Scaffolding, and not a model of a CPU restart:
  `test_double/README.md` S5.
* `--min-session-timeout-ms` / `--max-session-timeout-ms` — the window the double
  grants session timeouts within. The default `[5000, 8000]` is **below** the
  bridge's 10 000 ms request, so the grant is clamped down; passing
  `--min-session-timeout-ms 30000` reproduces the other direction, which is what
  the commissioned CPU did. Either way the keep-alive is derived from what was
  granted.

The double registers the real server's two namespace URIs behind three filler
namespaces, so its indices (`5` and `6`) differ from PLCSIM's. That is
deliberate: a bridge that hardcoded an index would fail against one server or
the other.

Panel contacts have no physics in the cell, so an unattended run needs a
stand-in for the human at the panel — all four of them, because the heartbeat
does not start until every input node has carried a real sample (§6.1 R3):

```
"$VENV/bin/python" "$REPO/bridge/tools/cell_stimulus.py" \
    --script "0:stop=true,0:process_stop=true,0:start=false,0:reset=false,\
20:start=true,21:start=false,60:reset=true,61:reset=false" \
    --duration 200 --pose-log /tmp/pose.csv
```

`reset` is normally open: `false` is the resting level and a press is a `true`
held for as long as the hand is on the button, then `false`. The stimulus times
nothing — the hold and the edge are the PLC's to read.

Check the write allowlist against a running double:

```
"$VENV/bin/python" "$REPO/bridge/tools/check_write_allowlist.py"
```

Check the connect logic — both namespaces resolved by URI, the granted session
timeout read back and the keep-alive derived from it (`bridge-design.md` §3.1,
§3.2) — against a running double:

```
"$VENV/bin/python" "$REPO/bridge/tools/check_connect_conformance.py"
```

It drives the bridge's own session establishment, and it idles a session for
longer than the granted timeout to measure the keep-alive cadence, so it takes
longer than the grant (`--skip-idle` omits that part). Run it against the double
only, never against PLCSIM: `bridge-design.md` §10. The recorded run is
`EVIDENCE_CONNECT.md`.

Check the session lifecycle — an in-flight request failure reconnecting instead of
ending the process, a restarted server getting its whole input image rewritten,
and the evidence-file naming (`bridge-design.md` §8.1, `docs/LESSONS.md`
2026-07-28):

```
"$VENV/bin/python" "$REPO/bridge/tools/check_session_lifecycle.py"
```

It **starts, kills and relaunches its own test double**, so it must never be
pointed at PLCSIM Advanced — it refuses an endpoint that looks like the
commissioned instance. It drives the bridge's own `PlcClient.run()` with the slots
filled by the harness rather than by ROS, since all three behaviours sit on the
OPC UA side of the slots. The recorded run is `EVIDENCE_LIFECYCLE.md`.

## What the test double does not prove

**The PLC program.** The double runs no standard program: no scan cycle, no
process image, no interlocks, no cycle-running flag, no reset, no threshold.
`DemoCell/Status/*` and `BridgeLinkOk` are PLC verdicts and stay at their start
values for a whole run against the double. Nothing observed against it is
evidence for `plc/demo-cell/SPEC.md`, and the M3 gate closes against PLCSIM
Advanced — run on 2026-07-27 and recorded in `EVIDENCE_LATENCY.md` Section B,
which is also where the two program defects that run found are written down.

## Observing the PLC during a PLCSIM run

`plc/demo-cell/SPEC.md` §9 makes the **TIA watch table** the instrument for gate
exit items (a) and (b). Where that is unavailable, `tools/observe_plc.py` opens
a **second, read-only** OPC UA session and samples the 15 `DemoCell` nodes plus
`Server/ServerDiagnosticsSummary/CurrentSessionCount` to CSV:

```
"$VENV/bin/python" "$REPO/bridge/tools/observe_plc.py" \
    --endpoint opc.tcp://192.168.53.1:4840 \
    --out "$REPO/bridge/evidence/plc-observe.csv" --period 0.1 --duration 300
```

It writes no node and forms no verdict. **It is not the watch table and does not
substitute for it**: it sees what the server published rather than what the
program held, and none of the §9 Group 4 internals (`SeqStep`, `SpeedRequest`,
the latches, `ResetDeviceFault`, timer `ET`s) are on the server at all. Every
figure it produces is qualified that way in `EVIDENCE_LATENCY.md` §B.1.
