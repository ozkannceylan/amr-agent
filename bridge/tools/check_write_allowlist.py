#!/usr/bin/env python3
"""Check that the bridge cannot write a node it is not allowed to write.

The rule (`opcua-nodes.md` §9.1, §10.1; `bridge-design.md` §3, §4.10): the
bridge writes **only** the `Input/` nodes of the groups the run configures, plus
the single `DemoCell/Link/BridgeHeartbeat`. With both groups configured that is
**12** keys — 7 `DemoCell/Input/`, 4 `DemoCell/Forklift/Input/`, and the
heartbeat. Nothing under any `Hmi/`, `Output/`, `Status/` or other `Link/` name
is in it, in any configuration.

Four independent checks, and the third is the one the forklift group makes
necessary:

  1. **Derived, not hand-maintained.** The allowlist comes from the configured
     groups (§4.10, consequence 1). Checked by loading all three configurations
     the design admits and reading the list each one produces.
  2. **Client side.** `PlcClient._write` raises `WriteNotPermitted` for any key
     outside that list, before a byte reaches the network — including every node
     of the HMI's group.
  3. **The HMI group, against a server that would have accepted the write.**
     `Forklift/Hmi/*` is marked *Writable from HMI/OPC UA* (§10.3) and the
     commissioned CPU runs with access control disabled, so per-*client* scoping
     is policy, not enforcement (ADR 0008 D2.5). This check writes those nodes
     from an independent client and shows the write **succeeding**, which is what
     makes check 2 mean something: a refusal proven against a server that
     refuses everything proves nothing about the bridge (§4.10, consequence 5).
  4. **Server side.** A direct write to a read-only node — the `Output/` and
     `Status/` folders of both groups — is refused by the server's access level.
     Two independent enforcements, the arrangement §10.3 describes.

Plus the startup half of consequence 4: the **config loader** rejects a
configuration that places an `Hmi…` node in a writable position, so the defect
is caught at startup rather than at the first write attempt.

Run with the test double up ($VENV is the --system-site-packages venv, wherever
the account can write it — see bridge/README.md):

    "$VENV/bin/python" bridge/test_double/plc_test_double.py \
        --endpoint opc.tcp://127.0.0.1:4842/amr-agent/celldouble/ &
    "$VENV/bin/python" bridge/tools/check_write_allowlist.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asyncua import Client, ua  # noqa: E402

from amr_bridge import config as config_mod  # noqa: E402
from amr_bridge.instrumentation import Counters, Recorder  # noqa: E402
from amr_bridge.opcua_side import PlcClient, WriteNotPermitted, expected_types  # noqa: E402
from amr_bridge.slots import SlotSet  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDPOINT = os.environ.get("BRIDGE_ENDPOINT", "opc.tcp://127.0.0.1:4842/amr-agent/celldouble/")
# Both namespaces of the commissioned browse path (bridge-design.md §3.1).
# Resolved by URI here for the same reason the bridge resolves them: the indices
# differ between PLCSIM and the test double, so neither may be written down.
INTERFACE_NAMESPACE = "http://DemoCell"                        # TIA-derived, ADR 0006
SERVER_INTERFACES_NAMESPACE = "http://www.siemens.com/simatic-s7-opcua"  # vendor-fixed

#: Nodes the server itself refuses: PLC-owned setpoints and verdicts, both
#: groups. (folder path under the interface node, BrowseName, value to try)
READ_ONLY_ON_THE_SERVER = [
    (["Output"], "ConveyorSpeedCommand", ua.Variant(0.0, ua.VariantType.Float)),
    (["Status"], "CellCycleRunning", ua.Variant(False, ua.VariantType.Boolean)),
    (["Status"], "ConveyorDriveFault", ua.Variant(False, ua.VariantType.Boolean)),
    (["Link"], "BridgeLinkOk", ua.Variant(False, ua.VariantType.Boolean)),
    (["Forklift", "Output"], "ForkliftTractionSpeedRef", ua.Variant(0.0, ua.VariantType.Float)),
    (["Forklift", "Output"], "ForkliftSteerAngleRef", ua.Variant(0.0, ua.VariantType.Float)),
    (["Forklift", "Output"], "ForkliftForkSpeedRef", ua.Variant(0.0, ua.VariantType.Float)),
    (["Forklift", "Status"], "ForkliftTeleopActive", ua.Variant(False, ua.VariantType.Boolean)),
    (["Forklift", "Status"], "ForkliftObstacleStopActive", ua.Variant(False, ua.VariantType.Boolean)),
    (["Forklift", "Link"], "HmiLinkOk", ua.Variant(False, ua.VariantType.Boolean)),
]

#: The six nodes of §4.10: written by the HMI, read by the PLC, **never touched
#: by the bridge in either direction**. The server accepts writes to all of
#: them, which is exactly why the refusal has to come from the bridge.
HMI_GROUP = [
    (["Forklift", "Hmi"], "HmiTractionRequest", ua.Variant(0.42, ua.VariantType.Float), 0.0),
    (["Forklift", "Hmi"], "HmiSteerRequest", ua.Variant(-0.33, ua.VariantType.Float), 0.0),
    (["Forklift", "Hmi"], "HmiForkRequest", ua.Variant(0.75, ua.VariantType.Float), 0.0),
    (["Forklift", "Hmi"], "HmiTeleopRequest", ua.Variant(True, ua.VariantType.Boolean), False),
    (["Forklift", "Hmi"], "HmiResetRequest", ua.Variant(True, ua.VariantType.Boolean), False),
    (["Forklift", "Link"], "HmiHeartbeat", ua.Variant(7, ua.VariantType.UInt16), 0),
]


class Checks:
    def __init__(self) -> None:
        self.failures = 0
        self.total = 0

    def ok(self, passed: bool, statement: str, detail: str = "") -> None:
        self.total += 1
        if passed:
            print(f"   ok   {statement}" + (f" — {detail}" if detail else ""))
        else:
            self.failures += 1
            print(f"   FAIL {statement}" + (f" — {detail}" if detail else ""))

    def result(self) -> int:
        print(f"\n{self.total} checks, {self.total - self.failures} passed, {self.failures} failed")
        print("RESULT:", "PASS" if self.failures == 0 else f"FAIL ({self.failures})")
        return 1 if self.failures else 0


def _offline_client(cfg: config_mod.Config, workdir: str) -> PlcClient:
    """A `PlcClient` that never connects: the allowlist guard is the first thing
    `_write` does, before any node lookup or network access."""
    recorder = Recorder(os.path.join(workdir, "allowlist-probe.csv"), flush_interval_s=60.0)
    return PlcClient(cfg, SlotSet(cfg.input_keys), recorder, Counters(), lambda key, value: 0)


async def check_allowlist_is_derived(checks: Checks, workdir: str) -> config_mod.Config:
    print("\n1. §4.10 — the allowlist is DERIVED from the configured groups")
    sizes = {}
    both = None
    for name, filename, groups, inputs in (
        ("cell only", "bridge.yaml", ("cell",), 7),
        ("forklift only", "bridge-double-forklift.yaml", ("forklift",), 4),
        ("both", "bridge-double-both.yaml", ("cell", "forklift"), 11),
    ):
        cfg = config_mod.load(os.path.join(HERE, "config", filename))
        sizes[name] = len(cfg.write_allowlist)
        checks.ok(
            tuple(cfg.groups) == groups and len(cfg.input_keys) == inputs
            and cfg.write_allowlist == frozenset(cfg.input_keys + (config_mod.HEARTBEAT_KEY,)),
            f"{name}: {len(cfg.write_allowlist)} keys = {len(cfg.input_keys)} configured "
            f"Input/ node(s) + the one heartbeat",
            f"{filename}: {cfg.touched_node_count} nodes touched",
        )
        if name == "both":
            both = cfg
    assert both is not None
    checks.ok(sizes["both"] == 12, "with both groups the allowlist holds exactly 12 keys",
              ", ".join(sorted(both.write_allowlist)))
    forbidden = {name for _, name, *_ in HMI_GROUP}
    checks.ok(
        not (forbidden & set(expected_types(both))),
        "the six nodes of §4.10 are in no set at all — not the allowlist, not the "
        "read set, not the diagnostics poll",
        f"{len(expected_types(both))} node keys resolved, {both.touched_node_count} nodes touched",
    )
    return both


async def check_client_side(checks: Checks, cfg: config_mod.Config, workdir: str) -> None:
    print("\n2. client side — PlcClient._write refuses every key outside the allowlist")
    client = _offline_client(cfg, workdir)
    attempts = (
        [(name, value.VariantType, value.Value) for _, name, value in READ_ONLY_ON_THE_SERVER]
        + [(name, value.VariantType, value.Value) for _, name, value, _ in HMI_GROUP]
    )
    for name, variant, value in attempts:
        try:
            await client._write(name, value, variant)
            checks.ok(False, f"{name}: the write was NOT refused")
        except WriteNotPermitted as exc:
            checks.ok(True, f"{name}: WriteNotPermitted", str(exc).split(".")[0][:96])


async def check_hmi_group_against_a_server_that_accepts(checks: Checks) -> None:
    print("\n3. §4.10 — the HMI group, against a server that WOULD have accepted the write")
    async with Client(ENDPOINT) as opc:
        idx = await opc.get_namespace_index(INTERFACE_NAMESPACE)
        idx_si = await opc.get_namespace_index(SERVER_INTERFACES_NAMESPACE)
        for folders, name, value, start in HMI_GROUP:
            path = [f"{idx_si}:ServerInterfaces", f"{idx}:DemoCell"] + [
                f"{idx}:{element}" for element in folders + [name]]
            node = await opc.nodes.objects.get_child(path)
            try:
                await node.write_value(ua.DataValue(value))
                read_back = await node.read_value()
                # Float, so the read-back is the single-precision neighbour of
                # what was written, exactly as it is for every Real the bridge
                # carries. Compared with a tolerance for that reason and no other.
                accepted = (bool(read_back) == bool(value.Value)
                            if isinstance(value.Value, bool)
                            else abs(float(read_back) - float(value.Value)) < 1e-5)
            except ua.UaStatusCodeError as exc:
                accepted = False
                read_back = type(exc).__name__
            checks.ok(
                accepted,
                f"the server ACCEPTS a write to Forklift/{'/'.join(folders[1:] + [name])} "
                "from another client",
                f"read back {read_back!r}; the bridge's refusal is therefore its own",
            )
            # Leave the group as it was found: this file is scaffolding, and a
            # stale operator request left behind would be misleading evidence.
            await node.write_value(ua.DataValue(ua.Variant(start, value.VariantType)))


async def check_server_side(checks: Checks) -> None:
    print("\n4. server side — the double refuses a direct write to a read-only node")
    async with Client(ENDPOINT) as opc:
        idx = await opc.get_namespace_index(INTERFACE_NAMESPACE)
        idx_si = await opc.get_namespace_index(SERVER_INTERFACES_NAMESPACE)
        for folders, name, value in READ_ONLY_ON_THE_SERVER:
            path = [f"{idx_si}:ServerInterfaces", f"{idx}:DemoCell"] + [
                f"{idx}:{element}" for element in folders + [name]]
            node = await opc.nodes.objects.get_child(path)
            try:
                await node.write_value(ua.DataValue(value))
                checks.ok(False, f"DemoCell/{'/'.join(folders + [name])}: the server "
                                 "ACCEPTED the write")
            except ua.UaStatusCodeError as exc:
                checks.ok(True, f"DemoCell/{'/'.join(folders + [name])}", type(exc).__name__)


def check_loader_rejects_an_hmi_node(checks: Checks, workdir: str) -> None:
    print("\n5. §4.10 consequence 4 — the config loader rejects an Hmi node at startup")
    source = os.path.join(HERE, "config", "bridge-double-both.yaml")
    with open(source, "r", encoding="utf-8") as handle:
        text = handle.read()
    cases = [
        (
            "an Hmi request in a writable position",
            '        ForkliftForkHeight:            ["Forklift", "Input", "ForkliftForkHeight"]',
            '        ForkliftForkHeight:            ["Forklift", "Hmi", "HmiForkRequest"]',
        ),
        (
            "the HMI's heartbeat in the diagnostics poll",
            '        HmiLinkOk:                     ["Forklift", "Link", "HmiLinkOk"]',
            '        HmiLinkOk:                     ["Forklift", "Link", "HmiHeartbeat"]',
        ),
    ]
    for statement, before, after in cases:
        assert before in text, before
        path = os.path.join(workdir, "hmi-probe.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace(before, after))
        try:
            config_mod.load(path)
        except config_mod.ConfigError as exc:
            checks.ok(True, f"rejected: {statement}", str(exc).split(".")[0][-88:])
        else:
            checks.ok(False, f"rejected: {statement}", "the configuration loaded")


async def main() -> int:
    parser = argparse.ArgumentParser(description="check the bridge's write allowlist")
    parser.add_argument("--endpoint", default=None, help="test double endpoint")
    args = parser.parse_args()
    global ENDPOINT
    if args.endpoint:
        ENDPOINT = args.endpoint

    checks = Checks()
    print("bridge write allowlist — opcua-nodes.md §9.1/§10.1, bridge-design.md §3/§4.10")
    print(f"  endpoint {ENDPOINT}  (TEST DOUBLE)")
    with tempfile.TemporaryDirectory(prefix="amr-allowlist-") as workdir:
        cfg = await check_allowlist_is_derived(checks, workdir)
        await check_client_side(checks, cfg, workdir)
        await check_hmi_group_against_a_server_that_accepts(checks)
        await check_server_side(checks)
        check_loader_rejects_an_hmi_node(checks, workdir)
    return checks.result()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
