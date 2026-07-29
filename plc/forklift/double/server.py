#!/usr/bin/env python3
"""PLC logic double for the forklift commissioning cell -- asyncua server.

REHEARSAL STAND-IN. The TIA Portal build described by plc/forklift/SPEC.md is the
plant. This process exists so the teleop loop can be rehearsed without TIA, and
any divergence resolves toward TIA + SPEC, never toward this.

What it serves, per docs/interfaces/opcua-nodes.md section 10.3 and section 2.1:

    Objects                                   standard OPC UA namespace
      ServerInterfaces                        ns http://www.siemens.com/simatic-s7-opcua
        DemoCell                              ns http://DemoCell
          Link/                               the shared M3 link surface
            BridgeHeartbeat  BridgeLinkOk
          Forklift/
            Hmi/     5 request tags           client-writable
            Input/   4 plant-state tags       client-writable
            Output/  3 setpoint tags          read-only
            Status/  4 verdict tags           read-only
            Link/    HmiHeartbeat (writable)  HmiLinkOk (read-only)

The namespace URI is NOT chosen here in any meaningful sense: on a real S7-1500
TIA derives it as http://<interface name> and the field is not editable (ADR
0006). Naming the interface node DemoCell is what produces http://DemoCell, and
that is what a client browses for. A misnamed interface presents as
NamespaceNotFound at connect, which is the intended fail-loud behaviour.

Only DemoCell/Link/ of the M3 cell is served. The 15-node M3 demonstration cell
is NOT implemented: this double stands in for FB_ForkliftTeleop, and of
FB_DemoCellControl it carries only the heartbeat fragment that produces the one
tag section 7 consumes (see logic.py).
"""

import argparse
import asyncio
import logging
import os
import sys
import time

import yaml
from asyncua import Server, ua

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logic import (  # noqa: E402
    Db,
    DemoCellStatics,
    FB_DemoCellControl_link_fragment,
    FB_ForkliftTeleop,
    Statics,
)

NS_SIEMENS = "http://www.siemens.com/simatic-s7-opcua"
NS_DEMOCELL = "http://DemoCell"

LOG = logging.getLogger("forklift-double")

# Tag tables. (name, VariantType, client-writable). Writability mirrors
# opcua-nodes.md section 10.3's "Writable from HMI/OPC UA" column exactly: it is
# the enforcement point, so a client defect that tried to write an actuator
# setpoint is refused by the server rather than by convention.
F = ua.VariantType.Float
B = ua.VariantType.Boolean
U = ua.VariantType.UInt16

GROUPS = {
    "Hmi": [
        ("HmiTractionRequest", F, True),
        ("HmiSteerRequest", F, True),
        ("HmiForkRequest", F, True),
        ("HmiTeleopRequest", B, True),
        ("HmiResetRequest", B, True),
    ],
    "Input": [
        ("ForkliftForkHeight", F, True),
        ("ForkliftLinearSpeed", F, True),
        ("ForkliftObstacleInStopZone", B, True),
        ("ForkliftObstacleMinDistance", F, True),
    ],
    "Output": [
        ("ForkliftTractionSpeedRef", F, False),
        ("ForkliftSteerAngleRef", F, False),
        ("ForkliftForkSpeedRef", F, False),
    ],
    "Status": [
        ("ForkliftTeleopActive", B, False),
        ("ForkliftObstacleStopActive", B, False),
        ("ForkliftSpeedLimitActive", B, False),
        ("ForkliftResetRequired", B, False),
    ],
    "Link": [
        ("HmiHeartbeat", U, True),
        ("HmiLinkOk", B, False),
    ],
}

# The shared M3 link surface. The bridge writes BridgeHeartbeat; the PLC owns
# BridgeLinkOk (opcua-nodes.md section 9.7).
DEMOCELL_LINK = [
    ("BridgeHeartbeat", U, True),
    ("BridgeLinkOk", B, False),
]

# Which DB each group's values live in, for the scan's read and write phases.
CLIENT_WRITTEN = [
    ("Hmi", "ForkliftHmi"),
    ("Input", "ForkliftInput"),
]
PROGRAM_WRITTEN = [
    ("Output", "ForkliftOutput"),
    ("Status", "ForkliftStatus"),
]


def _start_value(db: Db, dbname: str, tag: str):
    return getattr(getattr(db, dbname), tag)


class ForkliftDouble:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.db = Db()
        self.st = Statics()
        self.dcst = DemoCellStatics()
        self.nodes: dict[str, object] = {}
        self.scans = 0
        self.dt_max = 0.0
        self.dt_sum = 0.0

    async def build(self, server: Server) -> None:
        idx_siemens = await server.register_namespace(NS_SIEMENS)
        idx_democell = await server.register_namespace(NS_DEMOCELL)
        self.idx_siemens = idx_siemens
        self.idx_democell = idx_democell

        objects = server.nodes.objects
        # ServerInterfaces belongs to the Siemens namespace, not to the
        # interface's own. Reusing the interface index here fails to browse.
        server_ifaces = await objects.add_folder(idx_siemens, "ServerInterfaces")
        democell = await server_ifaces.add_folder(idx_democell, "DemoCell")

        # The shared M3 link surface.
        dc_link = await democell.add_folder(idx_democell, "Link")
        for tag, vt, writable in DEMOCELL_LINK:
            n = await dc_link.add_variable(
                idx_democell, tag,
                ua.Variant(_start_value(self.db, "DemoCellLink", tag), vt))
            if writable:
                await n.set_writable(True)
            self.nodes[f"DemoCell/Link/{tag}"] = n

        forklift = await democell.add_folder(idx_democell, "Forklift")
        dbfor = {"Hmi": "ForkliftHmi", "Input": "ForkliftInput",
                 "Output": "ForkliftOutput", "Status": "ForkliftStatus",
                 "Link": "ForkliftLink"}
        for group, tags in GROUPS.items():
            folder = await forklift.add_folder(idx_democell, group)
            for tag, vt, writable in tags:
                n = await folder.add_variable(
                    idx_democell, tag,
                    ua.Variant(_start_value(self.db, dbfor[group], tag), vt))
                if writable:
                    await n.set_writable(True)
                self.nodes[f"Forklift/{group}/{tag}"] = n

        LOG.info("namespace %d = %s", idx_siemens, NS_SIEMENS)
        LOG.info("namespace %d = %s", idx_democell, NS_DEMOCELL)
        LOG.info("address space built: %d nodes under DemoCell", len(self.nodes))

    async def read_inputs(self) -> None:
        """Input image: pull every client-writable value into the DB image."""
        for group, dbname in CLIENT_WRITTEN:
            target = getattr(self.db, dbname)
            for tag, _vt, _w in GROUPS[group]:
                setattr(target, tag,
                        await self.nodes[f"Forklift/{group}/{tag}"].read_value())
        self.db.ForkliftLink.HmiHeartbeat = await self.nodes[
            "Forklift/Link/HmiHeartbeat"].read_value()
        self.db.DemoCellLink.BridgeHeartbeat = await self.nodes[
            "DemoCell/Link/BridgeHeartbeat"].read_value()

    async def write_outputs(self) -> None:
        """Output image: push every program-owned value out."""
        for group, dbname in PROGRAM_WRITTEN:
            src = getattr(self.db, dbname)
            for tag, vt, _w in GROUPS[group]:
                await self.nodes[f"Forklift/{group}/{tag}"].write_value(
                    ua.Variant(getattr(src, tag), vt))
        await self.nodes["Forklift/Link/HmiLinkOk"].write_value(
            ua.Variant(self.db.ForkliftLink.HmiLinkOk, B))
        await self.nodes["DemoCell/Link/BridgeLinkOk"].write_value(
            ua.Variant(self.db.DemoCellLink.BridgeLinkOk, B))

    async def run(self) -> None:
        period = float(self.cfg["logic"]["scan_period_s"])
        endpoint = "opc.tcp://%s:%d%s" % (
            self.cfg["server"]["host"], int(self.cfg["server"]["port"]),
            self.cfg["server"].get("path", "/"))

        server = Server()
        await server.init()
        server.set_endpoint(endpoint)
        server.set_server_name(self.cfg["server"].get("name", "ForkliftLogicDouble"))
        server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        await self.build(server)

        async with server:
            LOG.info("serving %s, scan period %.0f ms", endpoint, period * 1000)
            LOG.info("this is a REHEARSAL STAND-IN; the TIA build is the plant")
            last = time.monotonic()
            while True:
                await asyncio.sleep(period)
                now = time.monotonic()
                dt = now - last
                last = now

                await self.read_inputs()
                # OB30 call order, SPEC.md section 4.1: the M3 block first, so
                # BridgeLinkOk is this scan's verdict and not last scan's.
                FB_DemoCellControl_link_fragment(self.db, self.dcst, dt)
                FB_ForkliftTeleop(self.db, self.st, dt)
                await self.write_outputs()

                self.scans += 1
                self.dt_sum += dt
                self.dt_max = max(self.dt_max, dt)
                if self.scans % 500 == 0:
                    LOG.info("scan %d, mean %.1f ms, max %.1f ms",
                             self.scans, 1000 * self.dt_sum / self.scans,
                             1000 * self.dt_max)


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=os.path.join(here, "config.yaml"))
    ap.add_argument("--port", type=int, default=None,
                    help="override the configured port")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)

    with open(args.config, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if args.port is not None:
        cfg["server"]["port"] = args.port

    port = int(cfg["server"]["port"])
    forbidden = {4840} | set(range(4842, 4847))
    if port in forbidden:
        LOG.error("port %d is reserved (PLCSIM 4840, bridge doubles 4842-4846); "
                  "refusing to start", port)
        return 2

    try:
        asyncio.run(ForkliftDouble(cfg).run())
    except KeyboardInterrupt:
        LOG.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
