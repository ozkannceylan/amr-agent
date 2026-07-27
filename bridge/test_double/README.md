# test_double — TEST SCAFFOLDING

```
############################################################
#  THIS IS NOT A PLC AND IT IS NOT A MODEL OF ONE.         #
############################################################
```

`plc_test_double.py` is a minimal OPC UA **server** that stands in for the
S7-1500 on PLCSIM Advanced (`docs/interfaces/bridge-design.md` §10). It exposes
namespace `urn:amr-agent:cell:plc` with the `DemoCell/` address space of
`docs/interfaces/opcua-nodes.md` §9 — same BrowseNames, same folder paths, same
data types, same access levels.

It exists so the bridge and the loop mechanics can be verified automatically in
this container, without the owner's TIA Portal / PLCSIM environment.

## Invariant 4 is preserved

The server role belongs to the PLC; the double merely plays that role. The
bridge is a client against the double and against PLCSIM, with **no code path
difference and no server mode**.

## What it proves

About the **bridge**: signal traversal in both directions, node types, polarity,
latest-sample decimation, the startup rule, liveness behaviour, reconnect,
no-auto-resume, and the bridge-side latency figures.

## What it does not prove

**The PLC program.** It runs no standard program. There is no scan cycle, no
process image, no interlock, no cycle-running flag, no reset and no threshold
in this directory. `DemoCell/Status/*` and `DemoCell/Link/BridgeLinkOk` are PLC
verdicts; this double never forms them, so they keep their start values for a
whole run — that is the honest answer, not a defect. Nothing observed here is
evidence for `plc/demo-cell/SPEC.md`.

## Scaffolding behaviours, and why each is not PLC logic

| ID | Flag | What it does | Why it is not logic |
|---|---|---|---|
| S1 | `--command-file PATH` | copies a hand-written float from a file into `DemoCell/Output/ConveyorSpeedCommand` | A human writing a setpoint through a back door. No input value is consulted; there is no condition, sequence or interlock |
| S2 | `--observe-csv PATH` | server-side log of session count, heartbeat and the whole input image at 5 Hz | Pure observation |
| S3 | `--echo-input KEY` | copies one nominated input into `ConveyorSpeedCommand` so the closed-loop L7 interval has something to measure. Off by default | A wire, not a decision. A real PLC does nothing like it |

Start values are those of `bridge-design.md` §6.3 — the fail-safe
pre-connection state, which belongs to the PLC's data block and never to the
bridge (`PanelStopCircuitClosed` `FALSE`, `ProductSensorRange` `0.0`, …).
`PanelResetPressed` starts `FALSE` too, for the opposite reason: a stop must
fail to *stopped*, a reset to *not reset* (`opcua-nodes.md` §9.3). "No reset"
above means no reset **logic** — the double holds the input node, and forms no
edge, no hold time and no latch from it.

## Operational rules

- Never start the double as part of a demonstration run.
- Never start it on the same endpoint as PLCSIM Advanced.
- Every evidence file states which server produced each number.

## Run

```
"$VENV/bin/python" plc_test_double.py \
    --endpoint opc.tcp://127.0.0.1:4840/amr-agent/celldouble/ \
    --command-file /tmp/scaffold_speed --observe-csv /tmp/double_observe.csv
```
