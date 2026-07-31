#!/usr/bin/env python3
"""TEST HARNESS — the plant and the bridge, held at values a capture run names.

    #############################################################
    #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
    #############################################################

`check_hmi_teleop_loop.py` plays the bridge and the plant through a fixed
scenario and exits. A screenshot pass needs the same two roles held **still**
while a human-driven browser is doing the pressing, so this process does only
that: it advances `DemoCell/Link/BridgeHeartbeat` and writes the four
`Forklift/Input/` nodes (`opcua-nodes.md` §10.5, §9.7), taking their values from
a small JSON command file that the capture script rewrites between phases.

The three-role separation of `check_hmi_teleop_loop.py` is kept exactly:

    this instrument   plays the BRIDGE and the PLANT. It writes the four
                      `Forklift/Input/` nodes and `DemoCell/Link/BridgeHeartbeat`
                      and nothing else — never a `Forklift/Hmi/` node, never
                      `Forklift/Link/HmiHeartbeat`, both of which are the HMI's.
    the HMI           plays the OPERATOR, driven here by a real browser.
    the double        plays the PLC. It owns every verdict.

It models **no plant dynamics**: an input holds whatever value the command file
names until the file names another. Nothing here derives a value from a PLC
output, and nothing here forms a verdict — what the lamps do is the double's
answer to these inputs, not this file's.

Run (from the repository root):
    ~/amr-hmi-venv/bin/python hmi/tools/screens_plant_driver.py \
        --commands /tmp/amr-hmi-screens/plant.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from asyncua import Client, ua

F = ua.VariantType.Float
B = ua.VariantType.Boolean
U = ua.VariantType.UInt16

#: What this instrument writes, standing in for the bridge (`opcua-nodes.md`
#: §10.5). The five `Forklift/Hmi/` requests and `Forklift/Link/HmiHeartbeat`
#: are deliberately absent: they are the HMI's, and the two writable sets are
#: disjoint by construction.
PLANT_INPUTS: tuple[tuple[str, ua.VariantType], ...] = (
    ("ForkliftForkHeight", F),
    ("ForkliftLinearSpeed", F),
    ("ForkliftObstacleInStopZone", B),
    ("ForkliftObstacleMinDistance", F),
)

#: Plausible resting sample, inside every window `plc/forklift/SPEC.md` §3.3
#: declares. Written once before the heartbeat starts, so no verdict is ever
#: formed from a start value.
DEFAULTS: dict[str, object] = {
    "ForkliftForkHeight": 0.20,
    "ForkliftLinearSpeed": 0.0,
    "ForkliftObstacleInStopZone": False,
    "ForkliftObstacleMinDistance": 3.50,
}

HEARTBEAT_MODULUS = 65536


class PlantAndBridge:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.client: Client | None = None
        self.nodes: dict[str, object] = {}
        self.heartbeat = 0
        self.state: dict[str, object] = dict(DEFAULTS)

    async def connect(self, retries: int = 80) -> None:
        last: Exception | None = None
        for _ in range(retries):
            try:
                client = Client(url=self.endpoint)
                client.name = "amr-agent-hmi-screens-plant"
                await client.connect()
                break
            except Exception as exc:  # noqa: BLE001 — the double may still be starting
                last = exc
                await asyncio.sleep(0.25)
        else:
            raise RuntimeError(f"could not connect to {self.endpoint}: {last}")

        idx_si = await client.get_namespace_index(
            "http://www.siemens.com/simatic-s7-opcua")
        idx = await client.get_namespace_index("http://DemoCell")
        objects = client.nodes.objects
        base = [f"{idx_si}:ServerInterfaces", f"{idx}:DemoCell"]

        async def child(*parts):
            return await objects.get_child(base + [f"{idx}:{p}" for p in parts])

        for name, _vt in PLANT_INPUTS:
            self.nodes[name] = await child("Forklift", "Input", name)
        self.nodes["BridgeHeartbeat"] = await child("Link", "BridgeHeartbeat")
        self.client = client
        print(f"connected {self.endpoint}", flush=True)

    async def write_inputs(self) -> None:
        for name, vtype in PLANT_INPUTS:
            value = self.state[name]
            value = bool(value) if vtype is B else float(value)
            await self.nodes[name].write_value(
                ua.DataValue(ua.Variant(value, vtype)))

    async def beat(self) -> None:
        self.heartbeat = (self.heartbeat + 1) % HEARTBEAT_MODULUS
        await self.nodes["BridgeHeartbeat"].write_value(
            ua.DataValue(ua.Variant(self.heartbeat, U)))

    def apply(self, commanded: dict) -> bool:
        changed = False
        for name, _vt in PLANT_INPUTS:
            if name in commanded and commanded[name] != self.state[name]:
                self.state[name] = commanded[name]
                changed = True
        return changed


def read_commands(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


async def amain(args: argparse.Namespace) -> int:
    host = urlparse(args.endpoint).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"refusing a non-loopback endpoint: {args.endpoint}", file=sys.stderr)
        return 2

    commands = Path(args.commands)
    plant = PlantAndBridge(args.endpoint)
    await plant.connect()

    # Every input carries a real sample BEFORE the heartbeat starts.
    plant.apply(read_commands(commands))
    await plant.write_inputs()
    print(f"inputs {json.dumps(plant.state)}", flush=True)

    deadline = time.monotonic() + args.run_seconds
    while time.monotonic() < deadline:
        if plant.apply(read_commands(commands)):
            print(f"inputs {json.dumps(plant.state)}", flush=True)
        await plant.write_inputs()
        await plant.beat()
        await asyncio.sleep(args.period)

    if plant.client is not None:
        await plant.client.disconnect()
    print(f"done, {plant.heartbeat} beats", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--endpoint", default="opc.tcp://127.0.0.1:4850/")
    parser.add_argument("--commands", required=True,
                        help="JSON file naming the four Forklift/Input/ values")
    parser.add_argument("--period", type=float, default=0.100)
    parser.add_argument("--run-seconds", type=float, default=600.0)
    args = parser.parse_args()
    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
