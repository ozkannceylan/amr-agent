#!/usr/bin/env python3
"""HMI-owned OPC UA double — the `Forklift/` address space, section 11 mirrors
optional.

    #############################################################
    #  THIS IS TEST SCAFFOLDING. IT IS NOT PART OF THE HMI.       #
    #############################################################

Neither `bridge/test_double/plc_test_double.py` nor `plc/forklift/double/
server.py` serves `Forklift/Safety/` yet — `docs/interfaces/opcua-nodes.md`
§11 landed 2026-07-29, after both were written, and extending either is outside
this layer's write access. This process is the hmi layer's OWN minimal
stand-in, written independently of both — it imports nothing from `bridge/` or
`plc/` — so `check_hmi_safety_mirrors.py` has something to run brief m5a-07's
evidence against without touching either agent's tree.

It is not a substitute for either double and settles nothing about them: any
divergence resolves toward `opcua-nodes.md`, never toward this file, and
nothing observed here is evidence about the TIA Portal build or about the
bridge.

Like `bridge/test_double/plc_test_double.py`, this is a DUMB address space: it
runs no program and forms no verdict. `Forklift/Output/*`, `Forklift/Status/*`
and `Forklift/Link/HmiLinkOk` hold their start values for the whole run — the
honest answer, and not a defect, exactly as that double's own docs say of
itself.

What moves in this double is only the four `Forklift/Safety/` mirrors, and only
when `--with-safety-mirrors` is given. They are never client-writable, in this
double or on any real server (§11.4 MR1) — `check_hmi_safety_mirrors.py` moves
them SERVER-SIDE, holding the same `Node` objects `add_variable` returns here,
which is not a client write and is not gated by `set_writable`. That refusal is
demonstrated, not assumed: the harness also attempts one client write against
this double and records the refusal.

Own port, per the brief: 4860, `opc.tcp://127.0.0.1:4860/amr-agent/
safetymirrordouble/`. Distinct from every port already spoken for in this
project — 4840 (PLCSIM), 4842-4846 (the bridge's test doubles), 4847 (this
layer's own instance of the bridge double), 4850 (the PLC logic double), and
4897/4898 (m4f-07c's one-off re-run instances, `EVIDENCE_HMI.md` §F.4).

Run standalone (for interactive use — e.g. opening a real browser against
`hmi/config-safety-mirror-double.yaml`'s HTTP port once `hmi_server.py` is
pointed at this double):
    python hmi/tools/safety_mirror_double.py --with-safety-mirrors

`check_hmi_safety_mirrors.py` imports `SafetyMirrorDouble` and runs the server
in its own process instead of spawning this file, so it can hold the mirror
`Node` objects directly with no IPC of any kind.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from asyncua import Server, ua

LOG = logging.getLogger("hmi-safety-mirror-double")

NS_SIEMENS = "http://www.siemens.com/simatic-s7-opcua"
NS_DEMOCELL = "http://DemoCell"

F = ua.VariantType.Float
B = ua.VariantType.Boolean
U = ua.VariantType.UInt16

#: Every node hmi_server.py's REQUIRED reads and writes need to resolve so the
#: session establishes, exactly opcua-nodes.md §10.3 — (group, tag, type, start
#: value, client-writable). `DemoCell/Link/*` is deliberately absent: the HMI
#: never reads or writes it (only `Forklift/Link/*`).
FORKLIFT_GROUPS: tuple[tuple[str, str, ua.VariantType, object, bool], ...] = (
    ("Hmi", "HmiTractionRequest", F, 0.0, True),
    ("Hmi", "HmiSteerRequest", F, 0.0, True),
    ("Hmi", "HmiForkRequest", F, 0.0, True),
    ("Hmi", "HmiTeleopRequest", B, False, True),
    ("Hmi", "HmiResetRequest", B, False, True),
    ("Input", "ForkliftForkHeight", F, 0.0, True),
    ("Input", "ForkliftLinearSpeed", F, 0.0, True),
    ("Input", "ForkliftObstacleInStopZone", B, True, True),
    ("Input", "ForkliftObstacleMinDistance", F, 0.0, True),
    ("Output", "ForkliftTractionSpeedRef", F, 0.0, False),
    ("Output", "ForkliftSteerAngleRef", F, 0.0, False),
    ("Output", "ForkliftForkSpeedRef", F, 0.0, False),
    ("Status", "ForkliftTeleopActive", B, False, False),
    ("Status", "ForkliftObstacleStopActive", B, False, False),
    ("Status", "ForkliftSpeedLimitActive", B, False, False),
    ("Status", "ForkliftResetRequired", B, True, False),
    ("Link", "HmiHeartbeat", U, 0, True),
    ("Link", "HmiLinkOk", B, False, False),
)

#: opcua-nodes.md §11.2 and §11.6 — the four mirrors, fail-safe start values
#: TRUE, TRUE, TRUE, FALSE. Never client-writable, here or anywhere (§11.4
#: MR1): `SafetyMirrorDouble.set_mirror` moves these SERVER-SIDE only.
SAFETY_MIRRORS: tuple[tuple[str, bool], ...] = (
    ("EStopDemand", True),
    ("ZoneStopDemand", True),
    ("SafetyResetRequired", True),
    ("SafetyResetFault", False),
)

#: Ports already spoken for elsewhere in this project (module docstring).
#: Refusing them here is this double's own guard against colliding with a
#: concurrent agent's instance, on the bridge test double's own precedent
#: (`plc/forklift/double/server.py`'s forbidden-port check).
FORBIDDEN_PORTS: frozenset[int] = frozenset(
    {4840, 4847, 4850, 4897, 4898} | set(range(4842, 4847))
)


class SafetyMirrorDouble:
    """Minimal `Forklift/` address space, the section 11 mirrors optional."""

    def __init__(self, with_safety_mirrors: bool) -> None:
        self.with_safety_mirrors = with_safety_mirrors
        self.nodes: dict[str, object] = {}

    async def build(self, server: Server) -> None:
        idx_siemens = await server.register_namespace(NS_SIEMENS)
        idx_democell = await server.register_namespace(NS_DEMOCELL)

        objects = server.nodes.objects
        # `ServerInterfaces` belongs to the Siemens namespace, not the
        # interface's own (opcua-nodes.md §2.1) — reusing the interface's index
        # here fails to browse, exactly as the two real doubles document.
        server_ifaces = await objects.add_folder(idx_siemens, "ServerInterfaces")
        democell = await server_ifaces.add_folder(idx_democell, "DemoCell")
        forklift = await democell.add_folder(idx_democell, "Forklift")

        folders: dict[str, object] = {}
        for group, tag, vtype, start, writable in FORKLIFT_GROUPS:
            if group not in folders:
                folders[group] = await forklift.add_folder(idx_democell, group)
            node = await folders[group].add_variable(
                idx_democell, tag, ua.Variant(start, vtype))
            if writable:
                await node.set_writable(True)
            self.nodes[f"Forklift/{group}/{tag}"] = node

        if self.with_safety_mirrors:
            safety = await forklift.add_folder(idx_democell, "Safety")
            for tag, start in SAFETY_MIRRORS:
                node = await safety.add_variable(idx_democell, tag, ua.Variant(start, B))
                # Deliberately NOT set_writable(True): §11.4 MR1 — no client
                # writes any of the four, on this double or on any real server.
                self.nodes[f"Forklift/Safety/{tag}"] = node
            LOG.info("Forklift/Safety/ IS served — 4 nodes, start values "
                     "True/True/True/False (opcua-nodes.md §11.6)")
        else:
            LOG.info("Forklift/Safety/ is NOT served on this instance — the "
                     "F-layer fallback of opcua-nodes.md §11.6, §11.8 item 5")

        LOG.info("namespace %d = %s", idx_siemens, NS_SIEMENS)
        LOG.info("namespace %d = %s", idx_democell, NS_DEMOCELL)
        LOG.info("address space built: %d node(s) under Forklift/", len(self.nodes))

    async def set_mirror(self, tag: str, value: bool) -> None:
        """Server-side write, standing in for the F-program's copy (§11.3).

        Not a client write: it holds the same `Node` object `build()` created
        and calls `write_value` directly, which asyncua does not gate behind
        `set_writable` — that attribute governs remote UA Write service calls
        from a CLIENT SESSION, not this process's own address-space code.
        """
        await self.nodes[f"Forklift/Safety/{tag}"].write_value(ua.Variant(value, B))
        LOG.info("Forklift/Safety/%s -> %s (server-side, standing in for the "
                 "F-program's copy, §11.3)", tag, value)


async def run(port: int, with_safety_mirrors: bool,
              ready: asyncio.Event | None = None) -> None:
    if port in FORBIDDEN_PORTS:
        raise SystemExit(
            f"port {port} is reserved by another double or a prior evidence "
            f"run; refusing to start (own port, per the brief)")
    endpoint = f"opc.tcp://127.0.0.1:{port}/amr-agent/safetymirrordouble/"
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("HmiSafetyMirrorDouble")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    double = SafetyMirrorDouble(with_safety_mirrors)
    await double.build(server)
    async with server:
        LOG.info("serving %s — TEST SCAFFOLDING, not part of the HMI, not a "
                 "substitute for bridge/test_double/ or plc/forklift/double/",
                 endpoint)
        if ready is not None:
            ready.set()
        while True:
            await asyncio.sleep(3600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=4860)
    parser.add_argument("--with-safety-mirrors", action="store_true",
                        help="also serve Forklift/Safety/ at its fail-safe "
                             "start values (opcua-nodes.md §11.2, §11.6)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    try:
        asyncio.run(run(args.port, args.with_safety_mirrors))
    except KeyboardInterrupt:
        LOG.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
