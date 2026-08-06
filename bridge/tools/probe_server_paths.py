#!/usr/bin/env python3
"""Read-only probe of the commissioned OPC UA server's Forklift subtree.

Why this exists, and what it does NOT claim. Before the bridge is pointed at a
signal group, the browse paths that group needs must be established **against
the server**, not against a design document: a browse name that has silently
gained a `_1` suffix cuts a client with no error dialog (LESSONS 2026-07-30),
and a block that was published in an earlier build may not be published now
(`DataBlocksGlobal`, 2026-08-05).

Two questions, kept apart because they are different claims (LESSONS 2026-08-05):

* **advertised** — the name appears when the parent folder is browsed;
* **addressable** — reading it through the path the bridge will actually use
  returns a value rather than `BadNodeIdUnknown`.

This tool answers both, per node, and prints them in separate columns. It is a
client, it writes nothing, and it is not part of any bridge run: it resolves the
same two namespaces by URI that `bridge-design.md` §3.1 N2 requires of the
bridge, walks the same interface path, and then reads. No value it reads is
applied to anything.

Usage:
    python bridge/tools/probe_server_paths.py --endpoint opc.tcp://192.168.53.1:4840
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import sys

from asyncua import Client, ua

NS_SERVER_INTERFACES = "http://www.siemens.com/simatic-s7-opcua"
NS_INTERFACE = "http://DemoCell"

# The paths the bridge would address, relative to the interface node. Sourced
# from opcua-nodes.md §10 (M4 forklift group) and §12 (envelope/mode/vehicle/
# process stop), transcribed, not invented.
FORKLIFT_M4 = [
    ("Forklift", "Input", "ForkliftForkHeight"),
    ("Forklift", "Input", "ForkliftLinearSpeed"),
    ("Forklift", "Input", "ForkliftObstacleInStopZone"),
    ("Forklift", "Input", "ForkliftObstacleMinDistance"),
    ("Forklift", "Output", "ForkliftTractionSpeedRef"),
    ("Forklift", "Output", "ForkliftSteerAngleRef"),
    ("Forklift", "Output", "ForkliftForkSpeedRef"),
    ("Forklift", "Status", "ForkliftTeleopActive"),
    ("Forklift", "Status", "ForkliftObstacleStopActive"),
    ("Forklift", "Status", "ForkliftSpeedLimitActive"),
    ("Forklift", "Status", "ForkliftResetRequired"),
    ("Forklift", "Link", "HmiLinkOk"),
]
ENVELOPE_S12 = [
    ("Forklift", "Mode", "ForkliftDriveModeActive"),
    ("Forklift", "Envelope", "ForkliftMotionEnable"),
    ("Forklift", "Envelope", "ForkliftSpeedCeiling"),
    ("Forklift", "Envelope", "ForkliftEquipmentPermit"),
    ("Forklift", "Vehicle", "ForkliftVehicleModeApplied"),
    ("Forklift", "Vehicle", "ForkliftVehicleHeartbeat"),
    ("Forklift", "ProcessStop", "ForkliftProcessStopActive"),
]
SHARED = [("Link", "BridgeHeartbeat"), ("Link", "BridgeLinkOk")]


async def browse_children(node) -> list[str]:
    out = []
    for child in await node.get_children():
        try:
            out.append((await child.read_browse_name()).Name)
        except Exception as exc:  # noqa: BLE001 - diagnostic tool
            out.append(f"<unreadable: {exc}>")
    return out


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="opc.tcp://192.168.53.1:4840")
    args = parser.parse_args()

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    print(f"# probe_server_paths  endpoint={args.endpoint}  utc={stamp}")

    client = Client(url=args.endpoint)
    client.session_timeout = 10000
    await client.connect()
    try:
        uris = await client.get_namespace_array()
        ns_si = uris.index(NS_SERVER_INTERFACES)
        ns_if = uris.index(NS_INTERFACE)
        print(f"namespace array ({len(uris)} entries):")
        for index, uri in enumerate(uris):
            print(f"  [{index}] {uri}")
        print(f"resolved by URI: ServerInterfaces ns={ns_si}  interface ns={ns_if}")

        objects = client.nodes.objects
        server_interfaces = await objects.get_child([ua.QualifiedName("ServerInterfaces", ns_si)])
        interface = await server_interfaces.get_child([ua.QualifiedName("DemoCell", ns_if)])
        print(f"interface node: {interface}")

        print("\n# advertised children (browse), one level at a time")
        print(f"DemoCell/: {sorted(await browse_children(interface))}")
        forklift = await interface.get_child([ua.QualifiedName("Forklift", ns_if)])
        subfolders = sorted(await browse_children(forklift))
        print(f"DemoCell/Forklift/: {subfolders}")
        for folder in subfolders:
            try:
                node = await forklift.get_child([ua.QualifiedName(folder, ns_if)])
                print(f"  Forklift/{folder}/: {sorted(await browse_children(node))}")
            except Exception as exc:  # noqa: BLE001
                print(f"  Forklift/{folder}/: <browse failed: {exc}>")

        print("\n# addressable? read each path the bridge would use")
        print(f"{'path':<52} {'status':<22} value")
        failures = 0
        for group_name, paths in (
            ("shared", SHARED),
            ("forklift (§10)", FORKLIFT_M4),
            ("envelope (§12)", ENVELOPE_S12),
        ):
            print(f"-- {group_name}")
            for path in paths:
                text = "/".join(path)
                try:
                    node = await interface.get_child(
                        [ua.QualifiedName(name, ns_if) for name in path]
                    )
                    value = await node.read_value()
                    dtype = (await node.read_data_type_as_variant_type()).name
                    print(f"{text:<52} {'OK ' + dtype:<22} {value!r}")
                except Exception as exc:  # noqa: BLE001
                    failures += 1
                    print(f"{text:<52} {'FAIL':<22} {type(exc).__name__}: {exc}")
        print(f"\nunreachable paths: {failures}")
        return 0 if failures == 0 else 1
    finally:
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
