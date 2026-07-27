#!/usr/bin/env python3
"""TEST SCAFFOLDING — read-only observer of the DemoCell address space.

This is the PLCSIM-side counterpart of the test double's ``--observe-csv``
(`test_double/README.md`), and it exists for one reason: **an agent cannot open
a TIA Portal watch table.** `plc/demo-cell/SPEC.md` §9 makes the watch table the
instrument for gate exit items (a) and (b); this file is *not* that instrument
and does not stand in for it. It samples the same 15 nodes over OPC UA, which
is a strictly weaker view: it sees what the **server** publishes, not what the
program holds, it cannot see any of the §9 Group 4 internals (`SeqStep`,
`SpeedRequest`, the latches, `ResetDeviceFault`, timer `ET`s), and its sampling
instants are its own, not the OB's.

What it does, and nothing else:

* opens **its own** OPC UA session, separate from the bridge's;
* reads the 15 `DemoCell` nodes plus the standard
  ``Server/ServerDiagnosticsSummary/CurrentSessionCount`` on a fixed period;
* appends one CSV row per sample, timestamped on ``CLOCK_MONOTONIC`` (the same
  clock family the bridge's evidence uses, never wall time).

It **writes no node**, in any code path — there is no write call in this file.
It is an observer, so it applies no threshold, forms no verdict and derives no
value; every column is a raw read. Running it changes nothing about the loop
except that the CPU serves one more read-only session.

    python3 bridge/tools/observe_plc.py \\
        --endpoint opc.tcp://192.168.53.1:4840 \\
        --out bridge/evidence/plc-observe.csv --period 0.1 --duration 300
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import time

from asyncua import Client

SERVER_INTERFACES_URI = "http://www.siemens.com/simatic-s7-opcua"

# (folder, leaf) in browse order. Mirrors opcua-nodes.md §9 / SPEC.md §3.1.
NODES = [
    ("Input", "ConveyorBeltPosition"),
    ("Input", "ConveyorBeltSpeed"),
    ("Input", "ProductSensorRange"),
    ("Input", "PanelStartPressed"),
    ("Input", "PanelResetPressed"),
    ("Input", "PanelStopCircuitClosed"),
    ("Input", "PanelProcessStopCircuitClosed"),
    ("Output", "ConveyorSpeedCommand"),
    ("Status", "CellCycleRunning"),
    ("Status", "CellProcessStopActive"),
    ("Status", "CellResetRequired"),
    ("Status", "ProductPresentAtSensor"),
    ("Status", "ConveyorDriveFault"),
    ("Link", "BridgeHeartbeat"),
    ("Link", "BridgeLinkOk"),
]


async def main_async(args: argparse.Namespace) -> None:
    client = Client(url=args.endpoint)
    client.name = "amr-agent-observer"
    client.session_timeout = 30000

    async with client:
        namespaces = await client.get_namespace_array()
        ns_server = namespaces.index(SERVER_INTERFACES_URI)
        ns_iface = namespaces.index(args.interface_uri)
        interfaces = await client.nodes.objects.get_child(
            [f"{ns_server}:ServerInterfaces"])
        demo_cell = await interfaces.get_child([f"{ns_iface}:DemoCell"])
        handles = []
        for folder, leaf in NODES:
            handles.append(await demo_cell.get_child(
                [f"{ns_iface}:{folder}", f"{ns_iface}:{leaf}"]))
        # Standard OPC UA diagnostics: i=2277 is
        # Server/ServerDiagnosticsSummary/CurrentSessionCount.
        session_count = client.get_node("i=2277")

        columns = ["t_mono_s"] + [f"{f}/{n}" for f, n in NODES] + ["CurrentSessionCount"]
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(columns)

        t0 = time.monotonic()
        rows: list[list] = []
        last_flush = t0
        while time.monotonic() - t0 < args.duration:
            tick = time.monotonic()
            try:
                values = await client.read_values(handles + [session_count])
            except Exception as exc:  # noqa: BLE001 — an observer never aborts a run
                values = [f"ERR:{type(exc).__name__}"] * (len(handles) + 1)
            rows.append([round(tick - t0, 4)] + list(values))
            if tick - last_flush >= 2.0:
                with open(args.out, "a", newline="", encoding="utf-8") as handle:
                    csv.writer(handle).writerows(rows)
                rows, last_flush = [], tick
            sleep_for = args.period - (time.monotonic() - tick)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
        if rows:
            with open(args.out, "a", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="read-only DemoCell observer (TEST SCAFFOLDING)")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--interface-uri", default="http://DemoCell",
                        help="derived from the TIA server interface name (ADR 0006)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--period", type=float, default=0.1)
    parser.add_argument("--duration", type=float, default=300.0)
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
