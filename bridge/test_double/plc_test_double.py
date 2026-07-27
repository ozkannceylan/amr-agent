#!/usr/bin/env python3
"""TEST SCAFFOLDING — OPC UA test double standing in for the S7-1500.

    ############################################################
    #  THIS IS NOT A PLC AND IT IS NOT A MODEL OF ONE.          #
    ############################################################

What it is (bridge-design.md §10): a minimal OPC UA *server* that exposes
namespace `urn:amr-agent:cell:plc` with the `DemoCell/` address space of
docs/interfaces/opcua-nodes.md §9 — same BrowseNames, same folder paths, same
data types, same access levels — so the bridge and the loop mechanics can be
verified in a container without TIA Portal or PLCSIM Advanced.

What it is NOT, and what nothing observed against it proves:

* It runs **no standard program**. There is no scan cycle, no process image,
  no interlock, no cycle-running flag, no reset and no threshold in this file.
* Nothing observed here is evidence for `plc/demo-cell/SPEC.md`.
* `DemoCell/Status/*` and `DemoCell/Link/BridgeLinkOk` are PLC verdicts. This
  double has no program, so it never forms them: they keep their start values
  for the whole run, and that is the honest answer, not a defect.

Scaffolding behaviours, each explicitly labelled below and in the evidence
files, exist only to exercise the loop:

  S1  --command-file PATH   The file's contents (one float, m/s) are copied
                            into `DemoCell/Output/ConveyorSpeedCommand`. This
                            is a HUMAN writing a setpoint by hand through a
                            back door in the double. It is NOT PLC logic: no
                            input value is consulted, there is no sequence,
                            no interlock and no condition of any kind.
  S2  --observe-csv PATH    Server-side observation log: what the "PLC" sees.
  S3  --echo-input KEY      Optional: copies one nominated input value into
                            ConveyorSpeedCommand, for the closed-loop L7
                            interval of §9.2. Off by default. Still NOT PLC
                            logic — it is a wire, not a decision.

Operational rule (§10): never start this double as part of a demonstration
run, and never on the same endpoint as PLCSIM Advanced. Every evidence file
states which server produced each number.

Run:
    /opt/amr-bridge-venv/bin/python bridge/test_double/plc_test_double.py \
        --endpoint opc.tcp://127.0.0.1:4840/amr-agent/celldouble/ \
        --command-file /tmp/scaffold_speed --observe-csv /tmp/double_observe.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import time
from datetime import datetime, timezone

from asyncua import Server, ua
from asyncua.server.internal_session import InternalSession

LOG = logging.getLogger("plc-double")

NAMESPACE_URI = "urn:amr-agent:cell:plc"

# opcua-nodes.md §9.3 — client-WRITABLE input image.
INPUTS = [
    ("ConveyorBeltPosition", ua.VariantType.Float, 0.0),
    ("ConveyorBeltSpeed", ua.VariantType.Float, 0.0),
    ("ProductSensorRange", ua.VariantType.Float, 0.0),
    ("PanelStartPressed", ua.VariantType.Boolean, False),
    ("PanelStopCircuitClosed", ua.VariantType.Boolean, False),
    ("PanelProcessStopCircuitClosed", ua.VariantType.Boolean, False),
]
# Start values are those of bridge-design.md §6.3 — the fail-safe pre-connection
# state, which belongs to the PLC's data block and NOT to the bridge.

# §9.4 — PLC-owned output, read-only for the client.
OUTPUTS = [("ConveyorSpeedCommand", ua.VariantType.Float, 0.0)]

# §9.5 — PLC-derived status, read-only. This double forms none of them.
STATUS = [
    ("CellCycleRunning", ua.VariantType.Boolean, False),
    ("CellProcessStopActive", ua.VariantType.Boolean, False),
    ("CellResetRequired", ua.VariantType.Boolean, False),
    ("ProductPresentAtSensor", ua.VariantType.Boolean, False),
    ("ConveyorDriveFault", ua.VariantType.Boolean, False),
]

# §9.7 — link. BridgeHeartbeat is the one node outside Input/ the client may write.
LINK = [
    ("BridgeHeartbeat", ua.VariantType.UInt16, 0, True),
    ("BridgeLinkOk", ua.VariantType.Boolean, False, False),
]


async def build(server: Server, idx: int) -> dict:
    nodes: dict[str, object] = {}
    objects = server.nodes.objects
    demo = await objects.add_folder(idx, "DemoCell")
    folders = {
        "Input": await demo.add_folder(idx, "Input"),
        "Output": await demo.add_folder(idx, "Output"),
        "Status": await demo.add_folder(idx, "Status"),
        "Link": await demo.add_folder(idx, "Link"),
    }
    for name, vtype, start in INPUTS:
        node = await folders["Input"].add_variable(idx, name, ua.Variant(start, vtype))
        await node.set_writable()          # client-writable per §9.3
        nodes[name] = node
    for name, vtype, start in OUTPUTS:
        nodes[name] = await folders["Output"].add_variable(idx, name, ua.Variant(start, vtype))
    for name, vtype, start in STATUS:
        nodes[name] = await folders["Status"].add_variable(idx, name, ua.Variant(start, vtype))
    for name, vtype, start, writable in LINK:
        node = await folders["Link"].add_variable(idx, name, ua.Variant(start, vtype))
        if writable:
            await node.set_writable()
        nodes[name] = node
    return nodes


async def scaffold_command_file(nodes: dict, path: str, period: float = 0.1) -> None:
    """S1 — TEST SCAFFOLDING. Copies a hand-written float from a file into
    ConveyorSpeedCommand. A back door for a human, not PLC logic."""
    last = None
    while True:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read().strip()
            if text and text != last:
                value = float(text)
                await nodes["ConveyorSpeedCommand"].write_value(
                    ua.DataValue(ua.Variant(value, ua.VariantType.Float)))
                LOG.info("SCAFFOLD S1: ConveyorSpeedCommand := %s (hand-written, not PLC logic)", value)
                last = text
        except FileNotFoundError:
            pass
        except ValueError:
            LOG.warning("SCAFFOLD S1: %s does not contain a float", path)
        await asyncio.sleep(period)


async def scaffold_echo(nodes: dict, key: str, period: float = 0.02) -> None:
    """S3 — TEST SCAFFOLDING. A wire from one nominated input straight to
    ConveyorSpeedCommand, so the closed-loop L7 interval has something to
    measure. It is a wire, not a decision; a real PLC does nothing like it."""
    while True:
        value = await nodes[key].read_value()
        await nodes["ConveyorSpeedCommand"].write_value(
            ua.DataValue(ua.Variant(float(value), ua.VariantType.Float)))
        await asyncio.sleep(period)


async def observe(nodes: dict, path: str, period: float = 0.2) -> None:
    """S2 — TEST SCAFFOLDING. Server-side record of what the "PLC" sees:
    session count, the heartbeat and the whole input image."""
    columns = (
        ["wall_utc", "monotonic_s", "active_sessions", "BridgeHeartbeat"]
        + [name for name, _, _ in INPUTS]
        + ["ConveyorSpeedCommand"]
    )
    with open(path, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(columns)
    while True:
        row = [
            datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            round(time.monotonic(), 3),
            InternalSession._current_connections,
            await nodes["BridgeHeartbeat"].read_value(),
        ]
        for name, _, _ in INPUTS:
            row.append(await nodes[name].read_value())
        row.append(await nodes["ConveyorSpeedCommand"].read_value())
        with open(path, "a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(row)
        await asyncio.sleep(period)


async def log_sessions(period: float = 0.5) -> None:
    last = -1
    while True:
        current = InternalSession._current_connections
        if current != last:
            LOG.info("active OPC UA sessions: %d", current)
            last = current
        await asyncio.sleep(period)


async def run(args: argparse.Namespace) -> None:
    server = Server()
    await server.init()
    server.set_endpoint(args.endpoint)
    server.set_server_name("amr-agent PLC TEST DOUBLE (not a PLC)")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    idx = await server.register_namespace(NAMESPACE_URI)
    nodes = await build(server, idx)
    LOG.info("namespace %s registered at index %d", NAMESPACE_URI, idx)

    tasks = [asyncio.create_task(log_sessions())]
    if args.command_file:
        tasks.append(asyncio.create_task(scaffold_command_file(nodes, args.command_file)))
    if args.observe_csv:
        tasks.append(asyncio.create_task(observe(nodes, args.observe_csv)))
    if args.echo_input:
        tasks.append(asyncio.create_task(scaffold_echo(nodes, args.echo_input)))

    async with server:
        LOG.info("TEST DOUBLE listening on %s — this is scaffolding, not a PLC", args.endpoint)
        try:
            while True:
                await asyncio.sleep(1.0)
        finally:
            for task in tasks:
                task.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(description="OPC UA test double for the S7-1500 (TEST SCAFFOLDING)")
    parser.add_argument("--endpoint", default="opc.tcp://127.0.0.1:4840/amr-agent/celldouble/")
    parser.add_argument("--command-file", default=None,
                        help="S1 scaffolding: file whose float contents drive ConveyorSpeedCommand")
    parser.add_argument("--observe-csv", default=None, help="S2 scaffolding: server-side observation log")
    parser.add_argument("--echo-input", default=None,
                        help="S3 scaffolding: copy this input into ConveyorSpeedCommand (L7 only)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        LOG.info("test double stopped")


if __name__ == "__main__":
    main()
