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
| `amr_bridge/opcua_side.py` | session, node resolution, type verification, the 50 ms cycle, the write allowlist, reconnect |
| `amr_bridge/instrumentation.py` | per-event CSV recording (always on) |
| `config/bridge.yaml` | endpoint, **both** namespace URIs, BrowseName paths, topic names, cycle period, evidence paths — no thresholds, no tolerances, no timers, and no namespace index |
| `test_double/` | TEST SCAFFOLDING: an OPC UA server standing in for the S7-1500 |
| `tools/` | evidence summariser, panel stimulus (scaffolding), allowlist check, connect-conformance check |
| `EVIDENCE_LATENCY.md`, `EVIDENCE_SIGNAL_LOSS.md`, `EVIDENCE_CONNECT.md`, `evidence/` | dated captures, each qualified by the environment that produced it |

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
honoured as written. The default (`evidence/latency-latest.csv`) is truncated at
every start, so a capture worth keeping is given its own dated name with
`--evidence-csv`.

Pointing it at PLCSIM Advanced or real hardware is a **configuration** change
only: `opcua.endpoint`, and the security fields if the server requires them.
The code path is identical. The two namespace URIs are the same for the test
double and for the CPU — only the *indices* differ, and no index is written down
anywhere. Renaming the TIA server interface is the one change that also requires
editing `opcua.namespace_uris.interface`, because that name **is** the URI
(ADR 0006).

Summarise a run:

```
"$VENV/bin/python" "$REPO/bridge/tools/summarize_latency.py" \
    "$REPO/bridge/evidence/latency-latest.csv"
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

## What the test double does not prove

**The PLC program.** The double runs no standard program: no scan cycle, no
process image, no interlocks, no cycle-running flag, no reset, no threshold.
`DemoCell/Status/*` and `BridgeLinkOk` are PLC verdicts and stay at their start
values for a whole run against the double. Nothing observed against it is
evidence for `plc/demo-cell/SPEC.md`, and the M3 gate closes against PLCSIM
Advanced, owner-run (`EVIDENCE_LATENCY.md`, second section).
