# test_double — TEST SCAFFOLDING

```
############################################################
#  THIS IS NOT A PLC AND IT IS NOT A MODEL OF ONE.         #
############################################################
```

`plc_test_double.py` is a minimal OPC UA **server** that stands in for the
S7-1500 on PLCSIM Advanced (`docs/interfaces/bridge-design.md` §10). It exposes
the commissioned two-namespace shape of §3.1 with the `DemoCell/` address space
of `docs/interfaces/opcua-nodes.md` §9 — same BrowseNames, same folder paths,
same data types, same access levels:

```
Objects
  +- ServerInterfaces   ns http://www.siemens.com/simatic-s7-opcua   (vendor-fixed)
       +- DemoCell      ns http://DemoCell                           (ADR 0006)
            +- Input/ Output/ Status/ Link/   and their variables
```

The interface URI is `http://DemoCell` and not a chosen URN because TIA Portal
derives a server interface's namespace URI from the interface name as
`http://<interface name>` and the field is not editable (**ADR 0006**). The
double registers the two URIs the real server presents, so the bridge resolves
both by browsing identically against either server.

`DemoCell` deliberately does **not** hang under `Objects`, and the parent folder
deliberately sits in a *different* namespace: those are the two facts phase-0
commissioning established, and reproducing them is what makes the double able to
fail a bridge that assumes otherwise (§3.1 N1, N3).

It exists so the bridge and the loop mechanics can be verified automatically in
this container, without the owner's TIA Portal / PLCSIM environment.

## Invariant 4 is preserved

The server role belongs to the PLC; the double merely plays that role. The
bridge is a client against the double and against PLCSIM, with **no code path
difference and no server mode**.

## What it proves

About the **bridge**: signal traversal in both directions, node types, polarity,
latest-sample decimation, the startup rule, liveness behaviour, reconnect,
no-auto-resume, the bridge-side latency figures, and the two connect
requirements — both namespaces resolved by URI under `ServerInterfaces`, and the
keep-alive derived from a **granted** session timeout (`EVIDENCE_CONNECT.md`).

Two server behaviours are copied on purpose, and they are the only two:

| # | Behaviour | Why it is here |
|---|---|---|
| 1 | The two URIs are registered **behind three filler namespaces**, so `ServerInterfaces` lands at index 5 and `DemoCell` at 6, where phase 0 saw `ServerInterfaces` at 3 | A bridge that hardcoded either index must fail against one of the two servers. Passing against both is the evidence that no index was written down |
| 2 | A client's requested session timeout is **revised** into `[--min-session-timeout-ms, --max-session-timeout-ms]`, default `[5000, 8000]` ms | The S7-1500 revises it too (30 000 ms granted for a 3 600 000 ms request). It is the only way to test that the keep-alive is derived from the granted value and not from the request. The default window is below the bridge's 10 000 ms request; `--min-session-timeout-ms 30000` reproduces a grant *above* the request |

Neither is a model of the PLC: the *shape* of the clamp is imitated, its values
are not the CPU's, and the indices are chosen to be wrong on purpose.

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
| S4 | `--min-session-timeout-ms`, `--max-session-timeout-ms` | the window this double grants session timeouts within, so a request is revised in one direction or the other | Session housekeeping in a *server*, applied to no signal. It decides nothing about any value in the address space |

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

It logs the two registered indices and the granted-timeout window at startup, so
every recorded run states which addresses and which grant it produced.
