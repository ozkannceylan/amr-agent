#!/usr/bin/env python3
"""TEST SCAFFOLDING — OPC UA test double standing in for the S7-1500.

    ############################################################
    #  THIS IS NOT A PLC AND IT IS NOT A MODEL OF ONE.          #
    ############################################################

What it is (bridge-design.md §10): a minimal OPC UA *server* that exposes the
commissioned two-namespace shape of §3.1 —

    Objects
      +- ServerInterfaces   ns http://www.siemens.com/simatic-s7-opcua
           +- DemoCell      ns http://DemoCell                (ADR 0006)
                +- Input/ Output/ Status/ Link/  and their variables

— with the `DemoCell/` address space of docs/interfaces/opcua-nodes.md §9: same
BrowseNames, same folder paths, same data types, same access levels, so the
bridge and the loop mechanics can be verified in a container without TIA Portal
or PLCSIM Advanced.

Two server behaviours are copied **deliberately**, and they are the only two:

* the two namespace URIs are the real server's, so browse-by-URI resolves
  identically here and against PLCSIM — but they are registered behind filler
  namespaces so the **indices differ from PLCSIM's** (§10). A bridge that
  hardcoded either index must fail against this double;
* the session timeout is **revised**, as the S7-1500 revises it (§3.2). This is
  the only way to test that the keep-alive is derived from the granted value.

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
  S4  --min/--max-session-timeout-ms
                            The window this double grants session timeouts
                            within, so a client's request is revised in one
                            direction or the other. Session housekeeping in a
                            server, not a process decision, and not the PLC's
                            values.

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

# The real S7-1500 server interface's URI, which TIA Portal derives from the
# interface name as http://<interface name> and does not let anyone edit
# (ADR 0006). The double must register the same URI as the server it stands in
# for, or the bridge's browse-by-URI resolution would fail against it alone.
INTERFACE_NAMESPACE_URI = "http://DemoCell"
# Vendor-fixed namespace of the ServerInterfaces folder every S7-1500 publishes.
# The interface node hangs under that folder, and the folder is NOT in the
# interface's namespace (bridge-design.md §3.1 N1/N3).
SERVER_INTERFACES_NAMESPACE_URI = "http://www.siemens.com/simatic-s7-opcua"

# TEST SCAFFOLDING — deliberate index shift (§10). Registered before the two
# real URIs so neither lands on the index PLCSIM Advanced happens to use
# (phase 0 observed ServerInterfaces at index 3). asyncua's own namespaces
# occupy 0 and 1, so these take 2, 3, 4 and the two real URIs follow at 5 and 6.
# The numbers are not a contract: the point is only that they differ from the
# real server's, so no hardcoded index can survive both.
INDEX_SHIFT_NAMESPACE_URIS = (
    "urn:amr-agent:test-double:index-shift:1",
    "urn:amr-agent:test-double:index-shift:2",
    "urn:amr-agent:test-double:index-shift:3",
)

# TEST SCAFFOLDING — the session-timeout window this double grants within.
# asyncua's server revises a client's RequestedSessionTimeout to
# min(max(requested, min), max), which is the shape of the S7-1500's own
# revision. The default max is below the bridge's configured request (10 000 ms),
# so the default run is granted LESS than it asked for; --min-session-timeout-ms
# above the request reproduces the other direction, which is what the
# commissioned CPU did (30 000 ms granted against a 3 600 000 ms request).
# It is scaffolding: the clamp's *shape* is imitated, its value is not the PLC's.
DEFAULT_MIN_SESSION_TIMEOUT_MS = 5000.0
DEFAULT_MAX_SESSION_TIMEOUT_MS = 8000.0

# opcua-nodes.md §9.3 — client-WRITABLE input image.
INPUTS = [
    ("ConveyorBeltPosition", ua.VariantType.Float, 0.0),
    ("ConveyorBeltSpeed", ua.VariantType.Float, 0.0),
    ("ProductSensorRange", ua.VariantType.Float, 0.0),
    ("PanelStartPressed", ua.VariantType.Boolean, False),
    ("PanelResetPressed", ua.VariantType.Boolean, False),
    ("PanelStopCircuitClosed", ua.VariantType.Boolean, False),
    ("PanelProcessStopCircuitClosed", ua.VariantType.Boolean, False),
]
# Start values are those of bridge-design.md §6.3 — the fail-safe pre-connection
# state, which belongs to the PLC's data block and NOT to the bridge.
# PanelResetPressed starts FALSE for the opposite reason to the two stop nodes:
# a stop fails to *stopped*, a reset fails to *not reset* (opcua-nodes.md §9.3,
# §3.1). Because the bridge writes no input before its first real sample, FALSE
# is also what a client reads for as long as nothing publishes /cell/panel/reset.

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


async def build(server: Server, idx_server_interfaces: int, idx: int) -> dict:
    """Build the commissioned shape: the ServerInterfaces folder in the Siemens
    namespace, the interface node and everything below it in the interface
    namespace (§3.1). `idx` is the interface namespace index; every node under
    `DemoCell` uses it."""
    nodes: dict[str, object] = {}
    objects = server.nodes.objects
    server_interfaces = await objects.add_folder(idx_server_interfaces, "ServerInterfaces")
    demo = await server_interfaces.add_folder(idx, "DemoCell")
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

    # SCAFFOLDING: shift the indices away from the real server's before
    # registering the two URIs the bridge resolves (§10).
    for filler in INDEX_SHIFT_NAMESPACE_URIS:
        LOG.info("SCAFFOLD: index-shift namespace %s at index %d",
                 filler, await server.register_namespace(filler))
    idx_server_interfaces = await server.register_namespace(SERVER_INTERFACES_NAMESPACE_URI)
    idx = await server.register_namespace(INTERFACE_NAMESPACE_URI)
    nodes = await build(server, idx_server_interfaces, idx)
    LOG.info("namespace %s registered at index %d (ServerInterfaces folder)",
             SERVER_INTERFACES_NAMESPACE_URI, idx_server_interfaces)
    LOG.info("namespace %s registered at index %d (DemoCell interface and below)",
             INTERFACE_NAMESPACE_URI, idx)
    LOG.info("browse path: Objects/%d:ServerInterfaces/%d:DemoCell — two namespaces, "
             "indices deliberately unlike PLCSIM's", idx_server_interfaces, idx)

    # SCAFFOLDING: revise every client's requested session timeout into this
    # window, as the S7-1500 does (§3.2). Not a model of the PLC's value.
    server.iserver.min_session_timeout_ms = args.min_session_timeout_ms
    server.iserver.max_session_timeout_ms = args.max_session_timeout_ms
    LOG.info("SCAFFOLD: session timeout granted within [%.0f, %.0f] ms — a request "
             "outside it is revised, in either direction",
             args.min_session_timeout_ms, args.max_session_timeout_ms)

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
    parser.add_argument("--min-session-timeout-ms", type=float,
                        default=DEFAULT_MIN_SESSION_TIMEOUT_MS,
                        help="S4 scaffolding: shortest session timeout this double grants; "
                             "set it above the bridge's request to reproduce a grant ABOVE "
                             "the request, as the commissioned CPU did")
    parser.add_argument("--max-session-timeout-ms", type=float,
                        default=DEFAULT_MAX_SESSION_TIMEOUT_MS,
                        help="S4 scaffolding: longest session timeout this double grants; "
                             "the default is below the bridge's configured request, so the "
                             "grant is clamped down")
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
