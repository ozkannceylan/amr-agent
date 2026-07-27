#!/usr/bin/env python3
"""Check that the bridge cannot write a node it is not allowed to write.

opcua-nodes.md §9.1: the bridge writes ONLY the `DemoCell/Input/` nodes (seven
since `PanelResetPressed`, m3-11) and `DemoCell/Link/BridgeHeartbeat`.
bridge-design.md §3 requires m3-04 to
enforce that "with a single write helper that rejects a NodeId outside the
allowlist".

Two independent checks:

  1. Client side — `PlcClient._write` raises `WriteNotPermitted` for any key
     outside `config.WRITE_ALLOWLIST`, before a byte reaches the network.
  2. Server side — a direct OPC UA write to a read-only node is refused by
     the server's access level (the test double mirrors §9's access levels).

Run with the test double up ($VENV is the --system-site-packages venv, wherever
the account can write it — see bridge/README.md):
    "$VENV/bin/python" bridge/tools/check_write_allowlist.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asyncua import Client, ua  # noqa: E402

from amr_bridge.config import WRITE_ALLOWLIST  # noqa: E402
from amr_bridge.opcua_side import PlcClient, WriteNotPermitted  # noqa: E402

ENDPOINT = os.environ.get("BRIDGE_ENDPOINT", "opc.tcp://127.0.0.1:4840/amr-agent/celldouble/")
NAMESPACE = "http://DemoCell"          # TIA-derived, not editable — ADR 0006

FORBIDDEN = [
    ("Output", "ConveyorSpeedCommand"),
    ("Status", "CellCycleRunning"),
    ("Status", "ProductPresentAtSensor"),
    ("Status", "ConveyorDriveFault"),
    ("Link", "BridgeLinkOk"),
]


async def main() -> int:
    failures = 0
    print("write allowlist =", sorted(WRITE_ALLOWLIST))
    print(f"  {len(WRITE_ALLOWLIST)} nodes: every DemoCell/Input/ node + BridgeHeartbeat\n")

    print("1. client-side check — PlcClient._write refuses a non-allowlisted key")
    client = PlcClient.__new__(PlcClient)          # no session needed: the guard is first
    for _, name in FORBIDDEN:
        try:
            await PlcClient._write(client, name, False, ua.VariantType.Boolean)
            print(f"   FAIL {name}: the write was NOT refused")
            failures += 1
        except WriteNotPermitted as exc:
            print(f"   ok   {name}: WriteNotPermitted — {str(exc).splitlines()[0]}")

    print("\n2. server-side check — the double refuses a direct write to a read-only node")
    async with Client(ENDPOINT) as opc:
        idx = await opc.get_namespace_index(NAMESPACE)
        for folder, name in FORBIDDEN:
            node = await opc.nodes.objects.get_child(
                [f"{idx}:DemoCell", f"{idx}:{folder}", f"{idx}:{name}"])
            try:
                await node.write_value(ua.DataValue(ua.Variant(False, ua.VariantType.Boolean)))
                print(f"   FAIL DemoCell/{folder}/{name}: the server ACCEPTED the write")
                failures += 1
            except ua.UaStatusCodeError as exc:
                print(f"   ok   DemoCell/{folder}/{name}: {type(exc).__name__}")
    print("\nRESULT:", "PASS" if failures == 0 else f"FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
