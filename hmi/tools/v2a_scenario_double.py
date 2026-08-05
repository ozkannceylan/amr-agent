#!/usr/bin/env python3
"""HMI-owned OPC UA scenario double — the `Forklift/` address space including
`opcua-nodes.md` §12, with scripted sequences replayed from `plc/forklift/
SPEC.md` §14.

    #############################################################
    #  THIS IS TEST SCAFFOLDING. IT IS NOT PART OF THE HMI.      #
    #############################################################

Why it exists, and what it deliberately is not
----------------------------------------------

`hmi/V2A-DESIGN.md` §10 splits the double v2a needs in two:

* the §14 behaviour belongs in `plc/forklift/double/`, because that double is
  the transliteration of `plc/forklift/SPEC.md` and §14 is a numbered part of
  that spec. Extending it is the **plc agent's** work and is requested in the
  m5-27 report — it is not done here and this file is not a substitute for it;
* until that lands, the build proceeds against an **hmi-owned scenario double**
  on the `safety_mirror_double.py` precedent, which serves the §12 nodes at
  their §12.8 boot values and **replays scripted sequences** derived from
  §14.4's tables.

The distinction is the whole point and it is enforced by how this file is
written. **There is no arbiter here and no verdict is computed.** Every state
change on this server comes from a straight-line `async` script that waits for
a value the HMI wrote, sleeps a scripted delay, and assigns a recorded answer.
A refusal is a **different script**, not a computed branch; an adopt window is a
**scripted delay**, not a state machine. Nothing in this file evaluates
`#modeEntryAdmitted`, `#motionPermissive`, `#vehicleAlive` or any other §14
term, and nothing in it may be cited as evidence about the standard program.
**Divergence resolves toward `SPEC.md` and toward TIA, never toward this file.**

Why the delay is realistic and not zero
---------------------------------------

LESSONS 2026-07-31: the obvious steady-state form of a commanded-vs-reported
comparison made autonomous mode permanently unreachable, and it was found by an
executable double run **with a 200 ms adopt window rather than an instantaneous
one**. `--adopt-delay` therefore defaults to a realistic value and the scripts
below open the window in two stages, so the HMI's "selection not in force" and
"vehicle adopting" renderings are each exercised for long enough to be seen and
photographed.

Address space
-------------

Every node `hmi_server.py` resolves, at the start values the node model gives:

* §9.7's two `DemoCell/Link/` tags (`BridgeHeartbeat`, `BridgeLinkOk`);
* §10's eighteen `Forklift/` nodes, per-tag writability as §10.3;
* §12's nine nodes in `Mode/`, `Envelope/`, `Vehicle/`, `ProcessStop/`, with
  §12.2's per-tag access rights — **all three `Envelope/` nodes and every PLC
  verdict refuse a client write**, which is part of what the build's checks
  demonstrate — and §12.8's start values, the two `TRUE`s included;
* §11's four `Forklift/Safety/` mirrors, only with `--with-safety-mirrors`, so
  both lamp renderings (live, and absent-group) are demonstrable.

Own port: 4861. Distinct from every port already spoken for in this project —
4840 (PLCSIM), 4842-4846 (the bridge's test doubles), 4847 (this layer's own
instance of the bridge double), 4850 (the PLC logic double), 4860
(`safety_mirror_double.py`), 4897/4898 (m4f-07c's re-run instances).

Run:
    python hmi/tools/v2a_scenario_double.py --scenario coldstart \\
        --with-safety-mirrors
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time

from asyncua import Server, ua

LOG = logging.getLogger("hmi-v2a-scenario-double")

NS_SIEMENS = "http://www.siemens.com/simatic-s7-opcua"
NS_DEMOCELL = "http://DemoCell"

F = ua.VariantType.Float
B = ua.VariantType.Boolean
U = ua.VariantType.UInt16

#: `DemoCell/Link/` — `opcua-nodes.md` §9.7. The HMI reads neither; they are
#: served so the diagnostics drawer's bridge row has something behind it and so
#: a scenario can move the bridge's liveness.
DEMOCELL_LINK: tuple[tuple[str, ua.VariantType, object, bool], ...] = (
    ("BridgeHeartbeat", U, 0, True),
    ("BridgeLinkOk", B, False, False),
)

#: `Forklift/` — `opcua-nodes.md` §10.3, eighteen nodes, (group, tag, type,
#: start value, client-writable).
FORKLIFT_M4: tuple[tuple[str, str, ua.VariantType, object, bool], ...] = (
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

#: `Forklift/` §12 — nine nodes, four folders. Access rights are §12.2's table:
#: `Envelope/*` refuses every client write, and so does every PLC verdict. The
#: two `Vehicle/` nodes are writable because the **bridge** writes them; this
#: double's scripts move them server-side all the same, standing in for a
#: bridge that is not running.
FORKLIFT_M5: tuple[tuple[str, str, ua.VariantType, object, bool], ...] = (
    ("Mode", "HmiDriveModeRequest", U, 0, True),
    ("Mode", "ForkliftDriveModeActive", U, 0, False),
    ("Envelope", "ForkliftMotionEnable", B, False, False),
    ("Envelope", "ForkliftSpeedCeiling", F, 0.0, False),
    ("Envelope", "ForkliftEquipmentPermit", B, False, False),
    ("Vehicle", "ForkliftVehicleModeApplied", U, 0, True),
    ("Vehicle", "ForkliftVehicleHeartbeat", U, 0, True),
    ("ProcessStop", "HmiProcessStopRequest", B, True, True),
    ("ProcessStop", "ForkliftProcessStopActive", B, True, False),
)

#: `opcua-nodes.md` §11.2 / §11.6 — fail-safe start values TRUE, TRUE, TRUE,
#: FALSE. Never client-writable, here or on any real server (§11.4 MR1).
SAFETY_MIRRORS: tuple[tuple[str, bool], ...] = (
    ("EStopDemand", True),
    ("ZoneStopDemand", True),
    ("SafetyResetRequired", True),
    ("SafetyResetFault", False),
)

#: A plausible resting plant sample, inside every window `plc/forklift/SPEC.md`
#: §3.3 declares. Applied once at start so the diagnostics drawer never renders
#: a start value as if it were a measurement.
PLANT_SAMPLE: dict[str, object] = {
    "Forklift/Input/ForkliftForkHeight": 0.20,
    "Forklift/Input/ForkliftLinearSpeed": 0.0,
    "Forklift/Input/ForkliftObstacleInStopZone": False,
    "Forklift/Input/ForkliftObstacleMinDistance": 3.50,
}

#: Ports already spoken for elsewhere in this project (module docstring).
FORBIDDEN_PORTS: frozenset[int] = frozenset(
    {4840, 4847, 4850, 4860, 4897, 4898} | set(range(4842, 4847))
)

HEARTBEAT_MODULUS = 65536


class ScenarioDouble:
    """The address space, plus the primitives a script is written from.

    The primitives are deliberately few and deliberately dumb: *observe a value
    the HMI wrote*, *wait*, *assign a recorded answer*. There is no third kind.
    """

    def __init__(self, with_safety_mirrors: bool) -> None:
        self.with_safety_mirrors = with_safety_mirrors
        self.nodes: dict[str, object] = {}
        self.types: dict[str, ua.VariantType] = {}

    # -- address space ------------------------------------------------------ #

    async def build(self, server: Server) -> None:
        idx_siemens = await server.register_namespace(NS_SIEMENS)
        idx = await server.register_namespace(NS_DEMOCELL)

        objects = server.nodes.objects
        # `ServerInterfaces` belongs to the Siemens namespace, not the
        # interface's own (opcua-nodes.md §2.1).
        server_ifaces = await objects.add_folder(idx_siemens, "ServerInterfaces")
        democell = await server_ifaces.add_folder(idx, "DemoCell")
        forklift = await democell.add_folder(idx, "Forklift")

        link = await democell.add_folder(idx, "Link")
        for tag, vtype, start, writable in DEMOCELL_LINK:
            await self._add(link, idx, f"Link/{tag}", tag, vtype, start, writable)

        folders: dict[str, object] = {}
        for group, tag, vtype, start, writable in FORKLIFT_M4 + FORKLIFT_M5:
            if group not in folders:
                folders[group] = await forklift.add_folder(idx, group)
            await self._add(folders[group], idx, f"Forklift/{group}/{tag}",
                            tag, vtype, start, writable)

        if self.with_safety_mirrors:
            safety = await forklift.add_folder(idx, "Safety")
            for tag, start in SAFETY_MIRRORS:
                # Deliberately NOT set_writable: §11.4 MR1 — no client writes
                # any of the four, on this double or on any real server.
                await self._add(safety, idx, f"Forklift/Safety/{tag}", tag,
                                B, start, False)
            LOG.info("Forklift/Safety/ IS served — 4 mirrors, start values "
                     "True/True/True/False (opcua-nodes.md §11.6)")
        else:
            LOG.info("Forklift/Safety/ is NOT served on this instance — the "
                     "absent-group case of opcua-nodes.md §11.6")

        LOG.info("namespace %d = %s | namespace %d = %s",
                 idx_siemens, NS_SIEMENS, idx, NS_DEMOCELL)
        LOG.info("address space built: %d node(s)", len(self.nodes))

    async def _add(self, folder, idx: int, key: str, tag: str,
                   vtype: ua.VariantType, start, writable: bool) -> None:
        node = await folder.add_variable(idx, tag, ua.Variant(start, vtype))
        if writable:
            await node.set_writable(True)
        self.nodes[key] = node
        self.types[key] = vtype

    # -- the three primitives ----------------------------------------------- #

    async def get(self, key: str):
        return await self.nodes[key].read_value()

    async def set(self, key: str, value, note: str = "") -> None:
        """Assign a recorded answer, server-side.

        Not a client write: this holds the `Node` object `build()` created, so
        `set_writable` does not gate it — that attribute governs remote UA
        Write calls from a client session, never this process's own
        address-space code. It is how a PLC verdict moves on a double that has
        no PLC behind it.
        """
        vtype = self.types[key]
        if vtype is B:
            value = bool(value)
        elif vtype is F:
            value = float(value)
        else:
            value = int(value)
        await self.nodes[key].write_value(ua.DataValue(ua.Variant(value, vtype)))
        LOG.info("SET %-46s -> %-6s %s", key, value, note)

    async def wait_value(self, key: str, wanted, note: str,
                         timeout: float = 600.0) -> bool:
        """Wait until a value the HMI wrote reads `wanted`. Observation only."""
        LOG.info("WAIT %s == %s   (%s)", key, wanted, note)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self.get(key) == wanted:
                LOG.info("SEEN %s == %s", key, wanted)
                return True
            await asyncio.sleep(0.02)
        LOG.warning("TIMEOUT waiting for %s == %s", key, wanted)
        return False

    async def wait_rise(self, key: str, note: str, timeout: float = 600.0) -> bool:
        """Wait for a `FALSE -> TRUE` transition of a value the HMI wrote.

        The edge is observed, never manufactured: this double does not decide
        what an edge means — the PLC does (§10.8 P6), and the script that calls
        this simply replays what the PLC answered when it saw one.
        """
        LOG.info("WAIT rising edge on %s   (%s)", key, note)
        deadline = time.monotonic() + timeout
        seen_low = not bool(await self.get(key))
        while time.monotonic() < deadline:
            value = bool(await self.get(key))
            if value and seen_low:
                LOG.info("SEEN rising edge on %s", key)
                return True
            seen_low = seen_low or not value
            await asyncio.sleep(0.02)
        LOG.warning("TIMEOUT waiting for a rising edge on %s", key)
        return False

    async def wait_change(self, key: str, note: str, timeout: float = 600.0):
        """Wait until a value the HMI wrote differs from what it reads now."""
        before = await self.get(key)
        LOG.info("WAIT %s to change from %s   (%s)", key, before, note)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = await self.get(key)
            if value != before:
                LOG.info("SEEN %s change %s -> %s", key, before, value)
                return value
            await asyncio.sleep(0.02)
        LOG.warning("TIMEOUT waiting for %s to change", key)
        return before


# --------------------------------------------------------------------------- #
# The scripts. Straight-line replays of `plc/forklift/SPEC.md` §14, one rule
# cited per step. No branch below evaluates a §14 term; a refusal is its own
# script.
# --------------------------------------------------------------------------- #

async def vehicle_beat(d: ScenarioDouble, period: float = 0.1) -> None:
    """Stand in for the bridge carrying the vehicle layer's counter (§12.6).

    A counter that changes is all `ForkliftVehicleHeartbeat` ever means; the
    verdict built on it is the PLC's (V2) and no consumer of this double
    derives one — the HMI renders the raw value in its drawer and nothing else.
    """
    value = 0
    while True:
        value = (value + 1) % HEARTBEAT_MODULUS
        await d.set("Forklift/Vehicle/ForkliftVehicleHeartbeat", value)
        await asyncio.sleep(period)


async def bridge_beat(d: ScenarioDouble, period: float = 0.1) -> None:
    value = 0
    while True:
        value = (value + 1) % HEARTBEAT_MODULUS
        await d.set("Link/BridgeHeartbeat", value)
        await asyncio.sleep(period)


async def link_up(d: ScenarioDouble) -> None:
    """The PLC's link verdict, replayed.

    P1/P2: the verdict is FALSE until the counter has been seen to CHANGE at
    least once. This script therefore waits for a change and never for a value.
    """
    await d.wait_change("Forklift/Link/HmiHeartbeat",
                        "P1/P2 — the counter must be seen to CHANGE, "
                        "not merely to be non-zero")
    await asyncio.sleep(0.2)
    await d.set("Forklift/Link/HmiLinkOk", True,
                "the PLC now attributes requests to an operator (§10.9)")
    await d.set("Link/BridgeLinkOk", True, "bridge liveness, §9.7")


async def cold_start_clearing(d: ScenarioDouble) -> None:
    """§14.9's cold-start signature, then the operator's §9 sequence.

    Two things this replays that the screen has to make visible:

    * **PS1** — releasing the button does NOT clear the latch. The script
      waits for the release and assigns nothing, deliberately;
    * **PS2/PS3** — the latch clears on the RISING EDGE of `HmiResetRequest`,
      and only after the live-world term (`HmiProcessStopRequest` FALSE) holds.
    """
    await d.wait_value("Forklift/ProcessStop/HmiProcessStopRequest", False,
                       "the operator releases the process stop (§9 step 3)")
    LOG.info("PS1 — the request cleared and the LATCH DOES NOT: assigning "
             "nothing here is the point of this step")
    await d.wait_rise("Forklift/Hmi/HmiResetRequest",
                      "PS2 — the monitored reset, on its rising edge")
    await asyncio.sleep(0.15)
    await d.set("Forklift/ProcessStop/ForkliftProcessStopActive", False,
                "PS3 — live-world term held: the stop was released first")
    await d.set("Forklift/Status/ForkliftResetRequired", False,
                "PS5 — the single answer to 'is a reset pending'")
    LOG.info("PS4 — clearing the latch energizes nothing: no setpoint, no "
             "enable and no envelope element moves in this step")


async def mode_echo(d: ScenarioDouble, adopt: float, *, refuse: bool = False,
                    vehicle_adopts: bool = True,
                    disagree_latch_after: float | None = None) -> None:
    """Replay the answer the PLC and the vehicle give to a mode selection.

    **This is an echo with a scripted delay, not an arbiter.** It evaluates no
    entry condition: `refuse=True` is the X5 script, `refuse=False` the X1/X2
    script, and which one runs is chosen on the command line by whoever is
    rehearsing, never computed here.

    The window is opened in two stages because the screen renders two different
    in-flight states (V2A-DESIGN §5.2) and both must be exercised:

        selected != in force            "selection not in force"
        selected == in force != applied "vehicle adopting"
    """
    while True:
        selected = int(await d.wait_change(
            "Forklift/Mode/HmiDriveModeRequest",
            "the operator moved the selector"))
        if refuse:
            LOG.info("X5 — this script replays a REFUSED entry: the selection "
                     "is consumed, the mode in force stays 0 (None), and "
                     "re-entry needs the selector moved away and back")
            continue
        await asyncio.sleep(adopt)
        await d.set("Forklift/Mode/ForkliftDriveModeActive", selected,
                    "X1/X2 — the PLC's verdict, after a scripted adopt delay")
        if not vehicle_adopts:
            LOG.info("this script replays a vehicle that never adopts: "
                     "ForkliftVehicleModeApplied is left where it is, so the "
                     "disagreement does not resolve")
            if disagree_latch_after is not None:
                await asyncio.sleep(disagree_latch_after)
                await d.set("Forklift/Envelope/ForkliftMotionEnable", False)
                await d.set("Forklift/Envelope/ForkliftSpeedCeiling", 0.0)
                await d.set("Forklift/Status/ForkliftResetRequired", True,
                            "§14.7 — a persistent mode disagreement latches; "
                            "the verdict is the PLC's and it arrives here as "
                            "ForkliftResetRequired")
            continue
        await asyncio.sleep(adopt)
        await d.set("Forklift/Vehicle/ForkliftVehicleModeApplied", selected,
                    "§12.6 — the vehicle reports what it is applying")
        if selected == 2:
            await d.set("Forklift/Envelope/ForkliftMotionEnable", True,
                        "§14.5 — the envelope is formed; it permits, it never "
                        "commands")
            await d.set("Forklift/Envelope/ForkliftSpeedCeiling", 0.80,
                        "a ceiling, not a setpoint (E2)")
            await d.set("Forklift/Envelope/ForkliftEquipmentPermit", True,
                        "§14.5 EQ — the equipment register's conjunction")
        else:
            await d.set("Forklift/Envelope/ForkliftMotionEnable", False)
            await d.set("Forklift/Envelope/ForkliftSpeedCeiling", 0.0)
            await d.set("Forklift/Envelope/ForkliftEquipmentPermit", False)


async def teleop_echo(d: ScenarioDouble) -> None:
    """`ForkliftTeleopActive` follows the enable, once Teleop is in force.

    The PLC's verdict, replayed: this script does not test a permissive, and
    the mode term below is a script precondition, not an interlock.
    """
    while True:
        await d.wait_rise("Forklift/Hmi/HmiTeleopRequest",
                          "the teleop enable's rising edge (§10.7)")
        if int(await d.get("Forklift/Mode/ForkliftDriveModeActive")) == 1:
            await asyncio.sleep(0.1)
            await d.set("Forklift/Status/ForkliftTeleopActive", True)
            await d.set("Forklift/Output/ForkliftTractionSpeedRef", 0.35)
            await d.wait_value("Forklift/Hmi/HmiTeleopRequest", False,
                               "the operator released the enable")
            await d.set("Forklift/Status/ForkliftTeleopActive", False)
            await d.set("Forklift/Output/ForkliftTractionSpeedRef", 0.0)
        else:
            LOG.info("the enable edge arrived while the mode in force is not "
                     "Teleop — this script replays the PLC answering nothing")


async def process_stop_latch(d: ScenarioDouble) -> None:
    """PS1, replayed for a stop the operator engages during a run."""
    while True:
        await d.wait_rise("Forklift/ProcessStop/HmiProcessStopRequest",
                          "the operator engaged the process stop")
        await asyncio.sleep(0.15)
        await d.set("Forklift/ProcessStop/ForkliftProcessStopActive", True,
                    "PS1 — latched by the standard program")
        await d.set("Forklift/Status/ForkliftResetRequired", True, "PS5")
        await d.set("Forklift/Status/ForkliftTeleopActive", False, "PS6")
        await d.set("Forklift/Output/ForkliftTractionSpeedRef", 0.0, "PS6")
        await d.set("Forklift/Envelope/ForkliftMotionEnable", False, "PS6")
        await d.set("Forklift/Envelope/ForkliftSpeedCeiling", 0.0, "PS6")
        await d.set("Forklift/Envelope/ForkliftEquipmentPermit", False, "PS6")
        await d.wait_rise("Forklift/Hmi/HmiResetRequest",
                          "PS2 — the monitored reset")
        if bool(await d.get("Forklift/ProcessStop/HmiProcessStopRequest")):
            LOG.info("PS3 — the live-world term does NOT hold (the stop is "
                     "still engaged): this script replays a REFUSED reset")
            continue
        await asyncio.sleep(0.15)
        await d.set("Forklift/ProcessStop/ForkliftProcessStopActive", False)
        await d.set("Forklift/Status/ForkliftResetRequired", False)
        await d.set("Forklift/Mode/ForkliftDriveModeActive", 0,
                    "§12.3 — after a latch the sequence is: leave the mode, "
                    "press reset, select the mode again")


async def link_drop(d: ScenarioDouble, after: float) -> None:
    """The PLC withdrawing its link verdict, on a schedule.

    What it is for: the screen must render the process-stop control
    UNAVAILABLE whenever `HmiLinkOk` is FALSE (V2A-DESIGN §4.3), and that
    rendering has to be photographed with the backend's session still up, so
    the two causes are visibly separate.
    """
    await asyncio.sleep(after)
    await d.set("Forklift/Link/HmiLinkOk", False,
                "P5 — the PLC no longer attributes requests to an operator")


async def safety_demand(d: ScenarioDouble, after: float) -> None:
    """An F-layer demand appearing on the mirrors (§11.2), display only."""
    await asyncio.sleep(after)
    await d.set("Forklift/Safety/EStopDemand", True)
    await d.set("Forklift/Safety/ZoneStopDemand", False)
    await d.set("Forklift/Safety/SafetyResetRequired", True)
    await d.set("Forklift/Safety/SafetyResetFault", False)


async def safety_healthy(d: ScenarioDouble, after: float) -> None:
    await asyncio.sleep(after)
    await d.set("Forklift/Safety/EStopDemand", False)
    await d.set("Forklift/Safety/ZoneStopDemand", False)
    await d.set("Forklift/Safety/SafetyResetRequired", False)
    await d.set("Forklift/Safety/SafetyResetFault", False)


# --------------------------------------------------------------------------- #

SCENARIOS = ("coldstart", "refused", "disagree", "linkdrop", "boot")


async def play(d: ScenarioDouble, args: argparse.Namespace) -> None:
    for key, value in PLANT_SAMPLE.items():
        await d.set(key, value, "a plausible resting plant sample")

    tasks = [asyncio.create_task(bridge_beat(d)),
             asyncio.create_task(vehicle_beat(d))]

    if args.scenario == "boot":
        LOG.info("scenario 'boot': every §12 value stays at its §12.8 start "
                 "value and no link verdict is ever granted. This is the "
                 "cold-start screen with nothing done to it")
        await asyncio.sleep(args.run_seconds)
        return

    tasks.append(asyncio.create_task(link_up(d)))
    if args.with_safety_mirrors:
        tasks.append(asyncio.create_task(
            safety_healthy(d, args.safety_healthy_after)))
        if args.safety_demand_after is not None:
            tasks.append(asyncio.create_task(
                safety_demand(d, args.safety_demand_after)))

    if args.scenario == "coldstart":
        tasks += [asyncio.create_task(cold_start_clearing(d)),
                  asyncio.create_task(mode_echo(d, args.adopt_delay)),
                  asyncio.create_task(teleop_echo(d)),
                  asyncio.create_task(process_stop_latch(d))]
    elif args.scenario == "refused":
        tasks += [asyncio.create_task(cold_start_clearing(d)),
                  asyncio.create_task(mode_echo(d, args.adopt_delay,
                                                refuse=True))]
    elif args.scenario == "disagree":
        tasks += [asyncio.create_task(cold_start_clearing(d)),
                  asyncio.create_task(
                      mode_echo(d, args.adopt_delay, vehicle_adopts=False,
                                disagree_latch_after=args.disagree_latch_after))]
    elif args.scenario == "linkdrop":
        tasks += [asyncio.create_task(cold_start_clearing(d)),
                  asyncio.create_task(mode_echo(d, args.adopt_delay)),
                  asyncio.create_task(link_drop(d, args.link_drop_after))]

    await asyncio.sleep(args.run_seconds)
    for task in tasks:
        task.cancel()


async def run(args: argparse.Namespace) -> None:
    if args.port in FORBIDDEN_PORTS:
        raise SystemExit(
            f"port {args.port} is reserved by another double or a prior "
            f"evidence run; refusing to start")
    endpoint = f"opc.tcp://127.0.0.1:{args.port}/amr-agent/v2ascenariodouble/"
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("HmiV2aScenarioDouble")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    double = ScenarioDouble(args.with_safety_mirrors)
    await double.build(server)
    async with server:
        LOG.info("serving %s — TEST SCAFFOLDING, not part of the HMI, not a "
                 "substitute for plc/forklift/double/", endpoint)
        LOG.info("scenario %r, adopt delay %.0f ms", args.scenario,
                 args.adopt_delay * 1000.0)
        await play(double, args)
    LOG.info("run complete")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=4861)
    parser.add_argument("--scenario", choices=SCENARIOS, default="coldstart")
    parser.add_argument("--adopt-delay", type=float, default=1.2,
                        help="the vehicle's adopt-and-report time, per stage. "
                             "REALISTIC BY DEFAULT: an adopt window that only "
                             "ever completes in zero time has not been tested "
                             "(LESSONS 2026-07-31)")
    parser.add_argument("--with-safety-mirrors", action="store_true")
    parser.add_argument("--safety-healthy-after", type=float, default=3.0)
    parser.add_argument("--safety-demand-after", type=float, default=None)
    parser.add_argument("--link-drop-after", type=float, default=20.0)
    parser.add_argument("--disagree-latch-after", type=float, default=6.0)
    parser.add_argument("--run-seconds", type=float, default=900.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        LOG.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
