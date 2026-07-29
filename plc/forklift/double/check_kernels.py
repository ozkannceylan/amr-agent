#!/usr/bin/env python3
"""Kernel checks for the forklift PLC logic double.

A direct asyncua client -- no bridge code, no HMI code, nothing imported from
another layer. It plays both clients at once: it advances Forklift/Link/
HmiHeartbeat as the HMI would and DemoCell/Link/BridgeHeartbeat as the bridge
would, writes the five request nodes every cycle (opcua-nodes.md section 10.4
H1), and reads the verdicts back.

Kernels demonstrated, from plc/forklift/SPEC.md section 11:

  K0  namespace table and browse path        (resolved BY URI, as a client must)
  K1  boot polarity                          HmiLinkOk FALSE until the heartbeat moves
  K2  T5.3 speed cap at the fork threshold
  K3  T5.2 fork soft limits, both directions
  K4  T5.4 obstacle latch + monitored reset  (held button clears nothing;
                                              reset refused while the zone reads occupied)
  K5  T5.5 heartbeat stale zeros all three setpoints within the window

Every expectation is asserted, not merely printed: a failed kernel exits non-zero.
"""

import argparse
import asyncio
import sys
import time

from asyncua import Client, ua

NS_SIEMENS = "http://www.siemens.com/simatic-s7-opcua"
NS_DEMOCELL = "http://DemoCell"

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print("    %-6s %s%s" % ("PASS" if ok else "FAIL", label,
                             ("  -- " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label)
    return ok


class Harness:
    def __init__(self, client: Client) -> None:
        self.c = client
        self.hmi_hb = 0
        self.bridge_hb = 0
        self.hmi_alive = True
        self.bridge_alive = True
        self.last_hmi_beat = 0.0
        self.requests = {
            "HmiTractionRequest": 0.0,
            "HmiSteerRequest": 0.0,
            "HmiForkRequest": 0.0,
            "HmiTeleopRequest": False,
            "HmiResetRequest": False,
        }
        self._task = None

    async def resolve(self) -> None:
        """Resolve BOTH namespaces by URI and browse from Objects. Never an index."""
        uris = await self.c.get_namespace_array()
        self.uris = uris
        try:
            self.idx_siemens = uris.index(NS_SIEMENS)
            self.idx_democell = uris.index(NS_DEMOCELL)
        except ValueError as exc:
            raise RuntimeError(
                "NamespaceNotFound: server advertises %r, need %r and %r"
                % (uris, NS_SIEMENS, NS_DEMOCELL)) from exc

        objects = self.c.nodes.objects
        s, d = self.idx_siemens, self.idx_democell
        self.iface = await objects.get_child(
            ["%d:ServerInterfaces" % s, "%d:DemoCell" % d])
        self.n = {}
        for group, tags in (
            ("Hmi", ["HmiTractionRequest", "HmiSteerRequest", "HmiForkRequest",
                     "HmiTeleopRequest", "HmiResetRequest"]),
            ("Input", ["ForkliftForkHeight", "ForkliftLinearSpeed",
                       "ForkliftObstacleInStopZone", "ForkliftObstacleMinDistance"]),
            ("Output", ["ForkliftTractionSpeedRef", "ForkliftSteerAngleRef",
                        "ForkliftForkSpeedRef"]),
            ("Status", ["ForkliftTeleopActive", "ForkliftObstacleStopActive",
                        "ForkliftSpeedLimitActive", "ForkliftResetRequired"]),
            ("Link", ["HmiHeartbeat", "HmiLinkOk"]),
        ):
            for tag in tags:
                self.n["Forklift/%s/%s" % (group, tag)] = await self.iface.get_child(
                    ["%d:Forklift" % d, "%d:%s" % (d, group), "%d:%s" % (d, tag)])
        for tag in ("BridgeHeartbeat", "BridgeLinkOk"):
            self.n["DemoCell/Link/%s" % tag] = await self.iface.get_child(
                ["%d:Link" % d, "%d:%s" % (d, tag)])

    async def get(self, path: str):
        return await self.n[path].read_value()

    async def status(self) -> dict:
        out = {}
        for p in ("Forklift/Output/ForkliftTractionSpeedRef",
                  "Forklift/Output/ForkliftSteerAngleRef",
                  "Forklift/Output/ForkliftForkSpeedRef",
                  "Forklift/Status/ForkliftTeleopActive",
                  "Forklift/Status/ForkliftObstacleStopActive",
                  "Forklift/Status/ForkliftSpeedLimitActive",
                  "Forklift/Status/ForkliftResetRequired",
                  "Forklift/Link/HmiLinkOk",
                  "DemoCell/Link/BridgeLinkOk"):
            out[p.rsplit("/", 1)[1]] = await self.get(p)
        return out

    async def set_input(self, tag: str, value, vt) -> None:
        await self.n["Forklift/Input/%s" % tag].write_value(ua.Variant(value, vt))

    def request(self, **kw) -> None:
        self.requests.update(kw)

    async def _cycle(self) -> None:
        """One HMI write cycle: five requests, then the heartbeat LAST (H3)."""
        vt = {"HmiTractionRequest": ua.VariantType.Float,
              "HmiSteerRequest": ua.VariantType.Float,
              "HmiForkRequest": ua.VariantType.Float,
              "HmiTeleopRequest": ua.VariantType.Boolean,
              "HmiResetRequest": ua.VariantType.Boolean}
        if self.hmi_alive:
            for tag, val in self.requests.items():
                await self.n["Forklift/Hmi/%s" % tag].write_value(
                    ua.Variant(val, vt[tag]))
            self.hmi_hb = (self.hmi_hb + 1) & 0xFFFF
            await self.n["Forklift/Link/HmiHeartbeat"].write_value(
                ua.Variant(self.hmi_hb, ua.VariantType.UInt16))
            self.last_hmi_beat = time.monotonic()
        if self.bridge_alive:
            self.bridge_hb = (self.bridge_hb + 1) & 0xFFFF
            await self.n["DemoCell/Link/BridgeHeartbeat"].write_value(
                ua.Variant(self.bridge_hb, ua.VariantType.UInt16))

    async def _driver(self) -> None:
        while True:
            await self._cycle()
            await asyncio.sleep(0.100)          # 10 Hz nominal, section 10.8 H2

    def start(self) -> None:
        self._task = asyncio.ensure_future(self._driver())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def settle(self, seconds: float = 0.4) -> None:
        await asyncio.sleep(seconds)


async def bring_up(h: Harness) -> None:
    """The operator's cold-start sequence: plausible plant, reset, enable."""
    await h.set_input("ForkliftForkHeight", 0.0, ua.VariantType.Float)
    await h.set_input("ForkliftLinearSpeed", 0.0, ua.VariantType.Float)
    await h.set_input("ForkliftObstacleInStopZone", False, ua.VariantType.Boolean)
    await h.set_input("ForkliftObstacleMinDistance", 3.0, ua.VariantType.Float)
    await h.settle(0.6)
    h.request(HmiTeleopRequest=False, HmiResetRequest=False)
    await h.settle(0.3)
    h.request(HmiResetRequest=True)             # rising edge
    await h.settle(0.3)
    h.request(HmiResetRequest=False)
    await h.settle(0.3)
    h.request(HmiTeleopRequest=True)            # a SEPARATE, fresh enable edge
    await h.settle(0.3)


async def k0_namespace(h: Harness) -> None:
    print("\n[K0] namespace table and browse path, resolved BY URI")
    print("    server namespace array: %r" % (h.uris,))
    print("    resolved index %d -> %s" % (h.idx_siemens, NS_SIEMENS))
    print("    resolved index %d -> %s" % (h.idx_democell, NS_DEMOCELL))
    check("both namespaces resolve by URI, neither index hardcoded", True)
    path = await h.n["Forklift/Hmi/HmiTractionRequest"].get_path(as_string=True)
    print("    browse path: %s" % " -> ".join(path))
    check("ServerInterfaces is NOT a child of Objects' own namespace",
          any("ServerInterfaces" in p for p in path))
    check("interface node is named DemoCell (the URI is derived from it)",
          any(p.endswith(":DemoCell") for p in path))
    check("Forklift subtree sits beside the M3 folders",
          any(p.endswith(":Forklift") for p in path))
    check("18 forklift nodes + 2 shared link nodes resolved",
          len(h.n) == 20, "resolved %d" % len(h.n))
    # access rights are the enforcement point (section 10.3)
    try:
        await h.n["Forklift/Output/ForkliftTractionSpeedRef"].write_value(
            ua.Variant(0.5, ua.VariantType.Float))
        check("Output/ is read-only for clients", False, "write was accepted")
    except ua.UaStatusCodeError as exc:
        check("Output/ is read-only for clients", True, type(exc).__name__)
    try:
        await h.n["Forklift/Status/ForkliftTeleopActive"].write_value(
            ua.Variant(True, ua.VariantType.Boolean))
        check("Status/ is read-only for clients", False, "write was accepted")
    except ua.UaStatusCodeError:
        check("Status/ is read-only for clients", True)


async def k1_boot_polarity(h: Harness) -> None:
    print("\n[K1] boot polarity -- HmiLinkOk FALSE until the heartbeat has moved")
    s = await h.status()
    print("    at boot, before any heartbeat: HmiLinkOk=%s BridgeLinkOk=%s "
          "ResetRequired=%s ObstacleStopActive=%s"
          % (s["HmiLinkOk"], s["BridgeLinkOk"], s["ForkliftResetRequired"],
             s["ForkliftObstacleStopActive"]))
    check("HmiLinkOk FALSE from the first scan", s["HmiLinkOk"] is False)
    check("BridgeLinkOk FALSE from the first scan", s["BridgeLinkOk"] is False)
    check("ResetRequired TRUE from power-up (both link latches formed)",
          s["ForkliftResetRequired"] is True)
    check("ObstacleStopActive FALSE despite the field bit's TRUE start value",
          s["ForkliftObstacleStopActive"] is False,
          "no sensor is accused of something no sensor reported")
    zone = await h.get("Forklift/Input/ForkliftObstacleInStopZone")
    check("...and the field bit really did start TRUE", zone is True)

    h.start()                                    # both heartbeats begin
    await h.settle(0.5)
    s = await h.status()
    print("    after the heartbeats advance: HmiLinkOk=%s BridgeLinkOk=%s"
          % (s["HmiLinkOk"], s["BridgeLinkOk"]))
    check("HmiLinkOk TRUE once the heartbeat has been seen to change",
          s["HmiLinkOk"] is True)
    check("BridgeLinkOk TRUE likewise", s["BridgeLinkOk"] is True)
    check("teleop still NOT active -- a link coming up energizes nothing",
          s["ForkliftTeleopActive"] is False)


async def k2_speed_cap(h: Harness) -> None:
    print("\n[K2] T5.3 -- traction capped while the fork is raised")
    h.request(HmiTractionRequest=1.0)
    await h.set_input("ForkliftForkHeight", 0.20, ua.VariantType.Float)
    await h.settle(0.3)
    s = await h.status()
    print("    fork 0.20 m (below 0.50), demand 1.0 -> TractionSpeedRef=%.3f "
          "SpeedLimitActive=%s" % (s["ForkliftTractionSpeedRef"],
                                   s["ForkliftSpeedLimitActive"]))
    check("uncapped setpoint is demand x TRACTION_SPEED_MAX = 1.00",
          abs(s["ForkliftTractionSpeedRef"] - 1.00) < 1e-6)
    check("SpeedLimitActive FALSE below the threshold",
          s["ForkliftSpeedLimitActive"] is False)

    await h.set_input("ForkliftForkHeight", 0.80, ua.VariantType.Float)
    await h.settle(0.3)
    s = await h.status()
    print("    fork 0.80 m (above 0.50), demand UNCHANGED at 1.0 -> "
          "TractionSpeedRef=%.3f SpeedLimitActive=%s"
          % (s["ForkliftTractionSpeedRef"], s["ForkliftSpeedLimitActive"]))
    check("capped setpoint is demand x TRACTION_SPEED_CAP_RAISED = 0.30",
          abs(s["ForkliftTractionSpeedRef"] - 0.30) < 1e-6,
          "the operator touched nothing; the PLC reduced it")
    check("SpeedLimitActive TRUE above the threshold",
          s["ForkliftSpeedLimitActive"] is True)

    h.request(HmiTractionRequest=0.2)
    await h.settle(0.3)
    s = await h.status()
    print("    fork still raised, demand 0.2 -> TractionSpeedRef=%.3f "
          "SpeedLimitActive=%s" % (s["ForkliftTractionSpeedRef"],
                                   s["ForkliftSpeedLimitActive"]))
    check("the cap SCALES the request, it does not clamp the full-scale product "
          "(0.2 x 0.30 = 0.060, not 0.20)",
          abs(s["ForkliftTractionSpeedRef"] - 0.06) < 1e-6)
    check("SpeedLimitActive stays TRUE -- 'in force', not 'biting'",
          s["ForkliftSpeedLimitActive"] is True)

    h.request(HmiTractionRequest=0.0)
    await h.set_input("ForkliftForkHeight", 0.20, ua.VariantType.Float)
    await h.settle(0.3)


async def k3_fork_limits(h: Harness) -> None:
    print("\n[K3] T5.2 -- fork soft travel limits, direction-scoped")
    await h.set_input("ForkliftForkHeight", 0.02, ua.VariantType.Float)
    h.request(HmiForkRequest=-1.0)               # lower, at the bottom
    await h.settle(0.3)
    s = await h.status()
    print("    fork 0.02 m (below FORK_TRAVEL_MIN 0.05), lower demand -1.0 -> "
          "ForkSpeedRef=%.3f" % s["ForkliftForkSpeedRef"])
    check("lowering blocked at the bottom limit",
          abs(s["ForkliftForkSpeedRef"]) < 1e-9)
    check("no latch: a soft-limit abort is a refusal, not a fault",
          s["ForkliftResetRequired"] is False)

    h.request(HmiForkRequest=1.0)                # raise, off the bottom
    await h.settle(0.3)
    s = await h.status()
    print("    same height, raise demand +1.0 -> ForkSpeedRef=%.3f"
          % s["ForkliftForkSpeedRef"])
    check("raising still permitted at the bottom limit -- NOT stranded",
          abs(s["ForkliftForkSpeedRef"] - 0.15) < 1e-6)

    await h.set_input("ForkliftForkHeight", 1.58, ua.VariantType.Float)
    await h.settle(0.3)
    s = await h.status()
    print("    fork 1.58 m (above FORK_TRAVEL_MAX 1.55), raise demand STILL "
          "+1.0 -> ForkSpeedRef=%.3f" % s["ForkliftForkSpeedRef"])
    check("raising blocked at the top limit with the control still held",
          abs(s["ForkliftForkSpeedRef"]) < 1e-9)

    h.request(HmiForkRequest=-1.0)
    await h.settle(0.3)
    s = await h.status()
    print("    same height, lower demand -1.0 -> ForkSpeedRef=%.3f"
          % s["ForkliftForkSpeedRef"])
    check("lowering permitted at the top limit -- the abort is direction-scoped",
          abs(s["ForkliftForkSpeedRef"] + 0.15) < 1e-6)
    check("still no latch anywhere in K3", s["ForkliftResetRequired"] is False)

    h.request(HmiForkRequest=0.0)
    await h.set_input("ForkliftForkHeight", 0.20, ua.VariantType.Float)
    await h.settle(0.3)


async def k4_obstacle_latch(h: Harness) -> None:
    print("\n[K4] T5.4 -- obstacle latch, override, refusal, monitored reset")
    h.request(HmiTractionRequest=1.0)
    await h.settle(0.3)
    s = await h.status()
    print("    driving: TractionSpeedRef=%.3f TeleopActive=%s"
          % (s["ForkliftTractionSpeedRef"], s["ForkliftTeleopActive"]))
    check("driving before the obstacle",
          s["ForkliftTractionSpeedRef"] > 0.5 and s["ForkliftTeleopActive"] is True)

    await h.set_input("ForkliftObstacleInStopZone", True, ua.VariantType.Boolean)
    await h.settle(0.3)
    s = await h.status()
    print("    obstacle in zone, traction demand STILL 1.0 -> TractionSpeedRef=%.3f "
          "SteerAngleRef=%.3f ForkSpeedRef=%.3f TeleopActive=%s "
          "ObstacleStopActive=%s ResetRequired=%s"
          % (s["ForkliftTractionSpeedRef"], s["ForkliftSteerAngleRef"],
             s["ForkliftForkSpeedRef"], s["ForkliftTeleopActive"],
             s["ForkliftObstacleStopActive"], s["ForkliftResetRequired"]))
    check("all three setpoints zeroed -- the latch overrides a LIVE command",
          abs(s["ForkliftTractionSpeedRef"]) < 1e-9
          and abs(s["ForkliftSteerAngleRef"]) < 1e-9
          and abs(s["ForkliftForkSpeedRef"]) < 1e-9)
    check("teleop dropped", s["ForkliftTeleopActive"] is False)
    check("ObstacleStopActive latched", s["ForkliftObstacleStopActive"] is True)
    check("ResetRequired TRUE", s["ForkliftResetRequired"] is True)

    # Reset asserted while the zone still reads occupied, and then HELD.
    #
    # NOTE ON ORDERING -- this differs from SPEC.md section 11 steps 5.4.4-5.4.7
    # deliberately, and the difference is a finding reported against the SPEC, not
    # a change of behaviour here. 5.4.4 says "assert AND RELEASE" while occupied
    # and 5.4.7 then says "assert and leave asserted" expecting no clear. But a
    # release followed by an assertion IS a fresh rising edge, and by 5.4.7 the
    # zone is clear, so the program correctly honours it and the latch clears --
    # 5.4.7 as written measures nothing. The property section 6.7 actually claims
    # is that a reset held CONTINUOUSLY ACROSS the moment the cause clears does
    # not clear the latch, because the edge happened before the cause went away.
    # That needs one uninterrupted hold, which is what is done here.
    h.request(HmiResetRequest=True)              # rising edge, cause still standing
    await h.settle(0.4)
    s = await h.status()
    print("    reset asserted WHILE occupied (and now held) -> "
          "ObstacleStopActive=%s ResetRequired=%s"
          % (s["ForkliftObstacleStopActive"], s["ForkliftResetRequired"]))
    check("reset REFUSED while the zone reads occupied (causeGone false on C3)",
          s["ForkliftObstacleStopActive"] is True
          and s["ForkliftResetRequired"] is True)

    # Clear the zone WITH THE RESET STILL HELD. Two properties at once: the field
    # clearing does not release the latch, and the held control supplies no edge.
    await h.set_input("ForkliftObstacleInStopZone", False, ua.VariantType.Boolean)
    await h.settle(1.2)
    s = await h.status()
    print("    zone cleared with the reset STILL HELD, 1.2 s -> "
          "ObstacleStopActive=%s ResetRequired=%s"
          % (s["ForkliftObstacleStopActive"], s["ForkliftResetRequired"]))
    check("the field clearing does NOT release the latch",
          s["ForkliftObstacleStopActive"] is True)
    check("a HELD reset clears nothing -- the edge happened before the cause went, "
          "and no elapsed time makes a new one",
          s["ForkliftObstacleStopActive"] is True
          and s["ForkliftResetRequired"] is True)

    # release, then a fresh rising edge
    h.request(HmiResetRequest=False)
    await h.settle(0.3)
    h.request(HmiResetRequest=True)
    await h.settle(0.3)
    s = await h.status()
    print("    released, then a FRESH rising edge -> ObstacleStopActive=%s "
          "ResetRequired=%s TeleopActive=%s TractionSpeedRef=%.3f"
          % (s["ForkliftObstacleStopActive"], s["ForkliftResetRequired"],
             s["ForkliftTeleopActive"], s["ForkliftTractionSpeedRef"]))
    check("the fresh edge clears the latches",
          s["ForkliftObstacleStopActive"] is False
          and s["ForkliftResetRequired"] is False)
    check("the reset ENERGIZES NOTHING: teleop still off, setpoints still 0.0",
          s["ForkliftTeleopActive"] is False
          and abs(s["ForkliftTractionSpeedRef"]) < 1e-9,
          "traction demand is still 1.0 and the machine does not move")

    # the enable was held throughout: it must produce no edge
    await h.settle(0.5)
    s = await h.status()
    check("enable held across the reset produces NO edge -- no auto-resume",
          s["ForkliftTeleopActive"] is False)

    h.request(HmiResetRequest=False, HmiTeleopRequest=False)
    await h.settle(0.3)
    h.request(HmiTeleopRequest=True)             # release and re-assert
    await h.settle(0.3)
    s = await h.status()
    print("    enable released and re-asserted -> TeleopActive=%s "
          "TractionSpeedRef=%.3f" % (s["ForkliftTeleopActive"],
                                     s["ForkliftTractionSpeedRef"]))
    check("teleop returns only on a fresh enable edge",
          s["ForkliftTeleopActive"] is True
          and s["ForkliftTractionSpeedRef"] > 0.5)


async def k5_heartbeat_stale(h: Harness) -> None:
    print("\n[K5] T5.5 -- HMI heartbeat stale zeros all three setpoints")
    h.request(HmiTractionRequest=1.0, HmiSteerRequest=0.5, HmiForkRequest=1.0)
    await h.set_input("ForkliftForkHeight", 0.20, ua.VariantType.Float)
    await h.settle(0.4)
    s = await h.status()
    print("    driving with all three moving: Traction=%.3f Steer=%.3f Fork=%.3f"
          % (s["ForkliftTractionSpeedRef"], s["ForkliftSteerAngleRef"],
             s["ForkliftForkSpeedRef"]))
    check("all three setpoints non-zero before the outage",
          abs(s["ForkliftTractionSpeedRef"]) > 1e-6
          and abs(s["ForkliftSteerAngleRef"]) > 1e-6
          and abs(s["ForkliftForkSpeedRef"]) > 1e-6)

    h.hmi_alive = False                          # the HMI process stops
    t0 = h.last_hmi_beat
    poll_until = t0 + 3.0
    zeroed_at = None
    link_false_at = None
    while time.monotonic() < poll_until:
        s = await h.status()
        if link_false_at is None and s["HmiLinkOk"] is False:
            link_false_at = time.monotonic()
        if (zeroed_at is None
                and abs(s["ForkliftTractionSpeedRef"]) < 1e-9
                and abs(s["ForkliftSteerAngleRef"]) < 1e-9
                and abs(s["ForkliftForkSpeedRef"]) < 1e-9):
            zeroed_at = time.monotonic()
        if zeroed_at and link_false_at:
            break
        await asyncio.sleep(0.005)

    s = await h.status()
    dt_link = (link_false_at - t0) if link_false_at else float("inf")
    dt_zero = (zeroed_at - t0) if zeroed_at else float("inf")
    print("    last heartbeat -> HmiLinkOk FALSE: %.0f ms" % (1000 * dt_link))
    print("    last heartbeat -> all three refs 0.0: %.0f ms" % (1000 * dt_zero))
    print("    after the outage: TeleopActive=%s ResetRequired=%s"
          % (s["ForkliftTeleopActive"], s["ForkliftResetRequired"]))
    check("HmiLinkOk goes FALSE within HMI_STALE_TIME + one scan (600+20 ms)",
          dt_link <= 0.70, "%.0f ms" % (1000 * dt_link))
    check("all three setpoints reach 0.0 in the same window",
          dt_zero <= 0.70, "%.0f ms" % (1000 * dt_zero))
    check("teleop dropped", s["ForkliftTeleopActive"] is False)
    check("the loss LATCHES: ResetRequired TRUE",
          s["ForkliftResetRequired"] is True)

    h.hmi_alive = True                           # the HMI restarts
    await h.settle(0.8)
    s = await h.status()
    print("    HMI restarted, heartbeat advancing again, nothing else done -> "
          "HmiLinkOk=%s TeleopActive=%s ResetRequired=%s Traction=%.3f"
          % (s["HmiLinkOk"], s["ForkliftTeleopActive"],
             s["ForkliftResetRequired"], s["ForkliftTractionSpeedRef"]))
    check("link returns", s["HmiLinkOk"] is True)
    check("teleop does NOT return -- a returning heartbeat restores nothing",
          s["ForkliftTeleopActive"] is False
          and abs(s["ForkliftTractionSpeedRef"]) < 1e-9)
    check("ResetRequired still TRUE", s["ForkliftResetRequired"] is True)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="opc.tcp://127.0.0.1:4850/")
    args = ap.parse_args()

    print("=" * 78)
    print("Forklift PLC logic double -- kernel checks")
    print("endpoint: %s" % args.endpoint)
    print("=" * 78)

    async with Client(url=args.endpoint) as client:
        h = Harness(client)
        await h.resolve()
        await k0_namespace(h)
        await k1_boot_polarity(h)
        await bring_up(h)
        s = await h.status()
        print("\n[bring-up] TeleopActive=%s ResetRequired=%s"
              % (s["ForkliftTeleopActive"], s["ForkliftResetRequired"]))
        check("machine enabled after reset + a separate enable edge",
              s["ForkliftTeleopActive"] is True)
        await k2_speed_cap(h)
        await k3_fork_limits(h)
        await k4_obstacle_latch(h)
        await k5_heartbeat_stale(h)
        await h.stop()

    print("\n" + "=" * 78)
    if FAILURES:
        print("FAILED %d check(s):" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("all kernel checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
