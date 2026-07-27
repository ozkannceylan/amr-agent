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
- **Nodes it is not allowed to write.** Only the six `DemoCell/Input/` nodes
  and `DemoCell/Link/BridgeHeartbeat` (opcua-nodes.md §9.1). Every write goes
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
   7 /cell/* topics                                               | client session
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
| `config/bridge.yaml` | endpoint, namespace URI, BrowseName paths, topic names, cycle period, evidence paths — no thresholds, no tolerances, no timers |
| `test_double/` | TEST SCAFFOLDING: an OPC UA server standing in for the S7-1500 |
| `tools/` | evidence summariser, panel stimulus (scaffolding), allowlist check |
| `EVIDENCE_LATENCY.md`, `EVIDENCE_SIGNAL_LOSS.md`, `evidence/` | dated captures from this container |

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
* nothing is published on `/cell/conveyor/cmd_speed` unless it was read from
  the server in the same cycle — no default, no replay, no zero on shutdown.

## How to run it

Install once (see `requirements.txt` for why it is a venv):

```
python3 -m venv --system-site-packages /opt/amr-bridge-venv
/opt/amr-bridge-venv/bin/pip install -r /home/user/amr-agent/bridge/requirements.txt
```

Then, in three terminals:

```
# 1. the cell
source /opt/ros/jazzy/setup.bash
ros2 launch /home/user/amr-agent/sim/launch/cell_bringup.launch.py

# 2. an OPC UA server on the configured endpoint
#    - in production: the S7-1500 / PLCSIM Advanced
#    - in this container: the test double, see below

# 3. the bridge
source /opt/ros/jazzy/setup.bash
/opt/amr-bridge-venv/bin/python /home/user/amr-agent/bridge/run_bridge.py \
    --config /home/user/amr-agent/bridge/config/bridge.yaml
```

Options: `--duration <s>` (stop after N seconds; used for measurement runs),
`--evidence-csv <path>` (override the raw evidence file). Stop it with
SIGINT/SIGTERM — it closes the session and writes nothing on the way out.

Pointing it at PLCSIM Advanced or real hardware is a **configuration** change
only: `opcua.endpoint`, and the security fields if the server requires them.
The code path is identical.

Summarise a run:

```
/opt/amr-bridge-venv/bin/python /home/user/amr-agent/bridge/tools/summarize_latency.py \
    /home/user/amr-agent/bridge/evidence/latency-2026-07-27.csv
```

### What the bridge logs at startup

`namespace ... resolved to index N` (browsed by URI, never hardcoded),
`all node DataTypes match opcua-nodes.md §9`, the publisher-side QoS of every
subscribed topic (mismatched QoS is silent in ROS 2), and
`heartbeat withheld: no real sample yet for ...` until every input has carried
a real cell sample.

## How to run the test double

The double is **test scaffolding**, never part of a demonstration run, and
never on the same endpoint as PLCSIM Advanced. Details and its limits:
`test_double/README.md`.

```
/opt/amr-bridge-venv/bin/python /home/user/amr-agent/bridge/test_double/plc_test_double.py \
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

Panel contacts have no physics in the cell, so an unattended run needs a
stand-in for the human at the panel:

```
/opt/amr-bridge-venv/bin/python /home/user/amr-agent/bridge/tools/cell_stimulus.py \
    --script "0:stop=true,0:process_stop=true,0:start=false,20:start=true,21:start=false" \
    --duration 200 --pose-log /tmp/pose.csv
```

Check the write allowlist against a running double:

```
/opt/amr-bridge-venv/bin/python /home/user/amr-agent/bridge/tools/check_write_allowlist.py
```

## What the test double does not prove

**The PLC program.** The double runs no standard program: no scan cycle, no
process image, no interlocks, no cycle-running flag, no reset, no threshold.
`DemoCell/Status/*` and `BridgeLinkOk` are PLC verdicts and stay at their start
values for a whole run against the double. Nothing observed against it is
evidence for `plc/demo-cell/SPEC.md`, and the M3 gate closes against PLCSIM
Advanced, owner-run (`EVIDENCE_LATENCY.md`, second section).
