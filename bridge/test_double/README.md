# test_double — TEST SCAFFOLDING

```
############################################################
#  THIS IS NOT A PLC AND IT IS NOT A MODEL OF ONE.         #
############################################################
```

`plc_test_double.py` is a minimal OPC UA **server** that stands in for the
S7-1500 on PLCSIM Advanced (`docs/interfaces/bridge-design.md` §10). It exposes
the commissioned two-namespace shape of §3.1 with the `DemoCell/` address space
of `docs/interfaces/opcua-nodes.md` §9 **and the `Forklift/` subtree of §10, §12
and §13** — same BrowseNames, same folder paths, same data types, same access
levels, same start values:

```
Objects
  +- ServerInterfaces   ns http://www.siemens.com/simatic-s7-opcua   (vendor-fixed)
       +- DemoCell      ns http://DemoCell                           (ADR 0006)
            +- Input/ Output/ Status/ Link/   and their variables
            +- Forklift/  Hmi/ Input/ Output/ Status/ Link/          (§10)
                          Mode/ Envelope/ Vehicle/ ProcessStop/      (§12)
                          Warning/                                   (§13)
```

**All 43 nodes, including the eight the bridge never touches** (§4.10): a node
absent from the double cannot be proven untouched — and until m5-55 added the
last ten, `opcua-nodes.md` §12 could only be exercised against the live CPU and
§13 against nothing at all (`bridge-design.md` §12 item 17). The forklift group adds a
*level*, not a namespace — `DemoCell/Forklift/…` sits under the same interface
node, so the browse path still crosses exactly two namespaces (§3.1 N7).

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

About the **bridge**: signal traversal in both directions **for every configured
group**, node types, polarity (including `ForkliftObstacleInStopZone` carried
uninverted), latest-sample decimation, the startup rule counted from the
configured set, liveness behaviour, reconnect, the restart detection and repair
of §8.1, no-auto-resume on all four output slots, the bridge-side latency
figures, and the two connect requirements — both namespaces resolved by URI
under `ServerInterfaces`, and the keep-alive derived from a **granted** session
timeout (`EVIDENCE_CONNECT.md`).

**And the write allowlist's refusal of an `Hmi` node.** The five
`Forklift/Hmi/` requests and `Forklift/Link/HmiHeartbeat` are served with the
*Writable from HMI/OPC UA* standing `opcua-nodes.md` §10.3 gives them, so a
bridge write to one **would succeed** — the conformance check proves the
bridge's own allowlist refuses them, not that this server refused. Conversely
`Output/` and `Status/` are served **not** writable in both groups, so the
server-side half of the two-independent-enforcements arrangement is exercised
too. A double that refused everything would make both checks vacuous.

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
in this directory — and none of the forklift's teleop routing, fork-height speed
cap, soft travel limits, obstacle latch, monitored reset or HMI watchdog.
`DemoCell/Status/*`, `DemoCell/Link/BridgeLinkOk`, `Forklift/Status/*` and
`Forklift/Link/HmiLinkOk` are PLC verdicts; this double never forms them, so they
keep their start values for a whole run — that is the honest answer, not a
defect. Nothing observed here is evidence for `plc/demo-cell/SPEC.md` or for the
forklift function block's specification.

**It is not the HMI either.** Serving the `Hmi/` group is not playing the HMI: it
stores those values, runs no operator interface, forms no request and holds no
session of the kind `hmi/` will. Any value a harness places in that group is
scaffolding, and a run against this double proves nothing about ADR 0008's
operator path.

**The commissioned `Forklift/` address space.** What is served is what
`opcua-nodes.md` §10 asks TIA Portal for; the browse path, folder tree, per-tag
rights and node count stay design values until the owner reads them back out of
the tool (§10.2 step 6).

## Scaffolding behaviours, and why each is not PLC logic

| ID | Flag | What it does | Why it is not logic |
|---|---|---|---|
| S1 | `--command-file PATH` | copies hand-written setpoints from a file into the `Output/` nodes: a bare float drives `DemoCell/Output/ConveyorSpeedCommand`, and `Name=value` lines drive any output node, including the three `Forklift/Output/*Ref`, the three `Forklift/Envelope/` elements, `Mode/ForkliftDriveModeActive` and `ProcessStop/ForkliftProcessStopActive` | A human writing setpoints and verdicts through a back door. No input value is consulted; there is no condition, sequence or interlock. **A hand moving the envelope is not a PLC forming one** — the only place an envelope is formed is the standard program |
| S2 | `--observe-csv PATH` | server-side log of session count, the bridge's heartbeat, both groups' input images, the setpoints and the `Hmi/` group at 5 Hz. The path is a **stem**: one file per double session, never a truncation of the last one | Pure observation. The `Hmi` columns are how "the bridge never touched them" is *observed* rather than asserted |
| S3 | `--echo-input KEY` | copies one nominated input into `ConveyorSpeedCommand` so the closed-loop L7 interval has something to measure. Off by default | A wire, not a decision. A real PLC does nothing like it |
| S4 | `--min-session-timeout-ms`, `--max-session-timeout-ms` | the window this double grants session timeouts within, so a request is revised in one direction or the other | Session housekeeping in a *server*, applied to no signal. It decides nothing about any value in the address space |
| S5 | `--warm-restart-file PATH` | touching that file assigns **every** node its declared start value, in place, with the server and every open session left up; the file is removed, so each touch is one restart | A bulk assignment of the start values listed at the top of `plc_test_double.py`. Nothing is sequenced, nothing is derived from anything, and no restart *logic* is modelled — a real CPU warm restart also re-runs startup OBs, reloads retained data and may drop the session, and none of that is here |

S5 exists because the failure of 2026-07-28 is invisible to a double that can
only be killed and relaunched: a CPU warm restart reinitialises the data block
**underneath a surviving session**, so a client that writes on change never
repairs the values it believes it already wrote. The bridge's answer is to read
its own heartbeat back; `../EVIDENCE_LIFECYCLE.md` §2.4 is the recorded run.

Start values are those of `bridge-design.md` §6.3 and `opcua-nodes.md` §10.9 —
the fail-safe pre-connection state, which belongs to the PLC's data block and
never to the bridge (`PanelStopCircuitClosed` `FALSE`, `ProductSensorRange`
`0.0`, …). The forklift group contributes the one start value in either section
that is not the type's zero: **`ForkliftObstacleInStopZone` starts `TRUE`**,
because `TRUE` is its non-permissive state and absence of data is an obstacle.
That is also what makes the S5 restart test sharp — a reverted server holds
`TRUE` while the plant is publishing `FALSE`, and write-on-change alone would
never repair it.
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
    --command-file /tmp/scaffold_speed --observe-csv /tmp/double_observe.csv \
    --warm-restart-file /tmp/double_warm_restart      # optional, S5
```

It logs the two registered indices and the granted-timeout window at startup, so
every recorded run states which addresses and which grant it produced.
