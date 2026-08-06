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
                +- Forklift/  Hmi/ Input/ Output/ Status/ Link/

— with the `DemoCell/` address space of docs/interfaces/opcua-nodes.md §9 **and
the `Forklift/` subtree of §10, §12 and §13**: same BrowseNames, same folder
paths, same data types, same access levels, same start values, so the bridge and
the loop mechanics can be verified in a container without TIA Portal or PLCSIM
Advanced.

**All 43 nodes, including the eight the bridge never touches** — a node absent
from the double cannot be proven untouched (§10). The five `Forklift/Hmi/`
requests and `Forklift/Link/HmiHeartbeat` are therefore served with the
*Writable* standing §10.3 gives them, so a bridge write to one **would
succeed**: the conformance check proves the *bridge's own allowlist* refuses
them, not that the server refused. A double that refused everything would make
that check vacuous. Conversely `Output/` and `Status/` are served not writable,
so the server-side half of the two-independent-enforcements arrangement is
exercised too.

Serving the `Hmi/` group is **not playing the HMI** (§10). This file stores
those values; it runs no operator interface, forms no request and holds no
session of the kind `hmi/` will.

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

  S1  --command-file PATH   The file's contents are copied into the `Output/`
                            nodes: a bare float goes to
                            `DemoCell/Output/ConveyorSpeedCommand`, and
                            `Name=value` lines address any output node by
                            BrowseName, which is how the three
                            `Forklift/Output/*Ref` setpoints are driven. This
                            is a HUMAN writing setpoints by hand through a
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
  S5  --warm-restart-file PATH
                            Touch that file and every node in the address space
                            goes back to its start value, in place, with the
                            server and every open session left alone. It stands
                            in for a CPU warm restart, which reinitialises the
                            data block underneath a surviving OPC UA session —
                            the 2026-07-28 failure in which the PLC read open
                            stop circuits for minutes because the bridge's
                            write-on-change cache saw nothing change. It is a
                            bulk assignment of start values and nothing else: no
                            program runs, no value is computed from another and
                            no restart logic of any kind is modelled.

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
import sys
import time
from datetime import datetime, timezone

from asyncua import Server, ua
from asyncua.server.internal_session import InternalSession

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# One rule for evidence-file naming in the whole bridge tree: the observation log
# is written once per double session and never truncated either (LESSONS
# 2026-07-28). The import is one function; the double still holds no bridge state
# and imports nothing else from the package.
from amr_bridge.instrumentation import session_csv_path  # noqa: E402

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

# §9.7 — link. BridgeHeartbeat is the one node of the M3 cell outside Input/
# that a client may write, and it is the bridge's. The forklift group adds no
# second heartbeat (§10.11); it adds the HMI's, which is a different client's.
LINK = [
    ("BridgeHeartbeat", ua.VariantType.UInt16, 0, True),
    ("BridgeLinkOk", ua.VariantType.Boolean, False, False),
]

# --------------------------------------------------------------------------- #
# opcua-nodes.md §10 — the forklift commissioning cell. 18 nodes, of which the
# bridge touches 12: it never reads and never writes the five Hmi/ requests or
# Link/HmiHeartbeat (bridge-design.md §4.10).
# --------------------------------------------------------------------------- #

# §10.4 — the operator's requests. WRITABLE (§10.3), so a bridge write to one
# would SUCCEED. That is the point: the allowlist check proves the bridge
# refuses them, not that this server did.
FORKLIFT_HMI = [
    ("HmiTractionRequest", ua.VariantType.Float, 0.0),
    ("HmiSteerRequest", ua.VariantType.Float, 0.0),
    ("HmiForkRequest", ua.VariantType.Float, 0.0),
    ("HmiTeleopRequest", ua.VariantType.Boolean, False),
    ("HmiResetRequest", ua.VariantType.Boolean, False),
]

# §10.5 — plant state, client-writable: this is the bridge's forklift input
# image. Start values are §10.9's, and `ForkliftObstacleInStopZone` is the one
# start value in that section that is not the type's zero — TRUE is the
# non-permissive state and absence of data is an obstacle.
FORKLIFT_INPUTS = [
    ("ForkliftForkHeight", ua.VariantType.Float, 0.0),
    ("ForkliftLinearSpeed", ua.VariantType.Float, 0.0),
    ("ForkliftObstacleInStopZone", ua.VariantType.Boolean, True),
    ("ForkliftObstacleMinDistance", ua.VariantType.Float, 0.0),
]

# §10.6 — PLC → plant setpoints. NOT writable: neither client writes an
# actuator output, and the server enforces that half of the rule.
FORKLIFT_OUTPUTS = [
    ("ForkliftTractionSpeedRef", ua.VariantType.Float, 0.0),
    ("ForkliftSteerAngleRef", ua.VariantType.Float, 0.0),
    ("ForkliftForkSpeedRef", ua.VariantType.Float, 0.0),
]

# §10.7 — PLC verdicts, read-only for both clients. This double runs no program,
# so it forms none of them: they keep their start values for the whole run.
FORKLIFT_STATUS = [
    ("ForkliftTeleopActive", ua.VariantType.Boolean, False),
    ("ForkliftObstacleStopActive", ua.VariantType.Boolean, False),
    ("ForkliftSpeedLimitActive", ua.VariantType.Boolean, False),
    ("ForkliftResetRequired", ua.VariantType.Boolean, False),
]

# §10.8 — the HMI's watchdog: its counter is writable (the HMI's to write, and
# a node the bridge must never touch); the PLC's verdict is not.
FORKLIFT_LINK = [
    ("HmiHeartbeat", ua.VariantType.UInt16, 0, True),
    ("HmiLinkOk", ua.VariantType.Boolean, False, False),
]

# --------------------------------------------------------------------------- #
# opcua-nodes.md §12 — the autonomy envelope, the drive mode and the operator's
# process stop; and §13 — the warning-field verdict. Ten nodes, added 2026-08-06
# (m5-55) to close `bridge-design.md` §12 item 17: until now the envelope group
# was testable only against the live CPU, and a node absent from the double
# cannot be exercised at all, let alone proven untouched (§10).
#
# Start values are §12.8's and §13's own, and §12.8's rule — *every start value
# in §12 is the non-permissive one* — is transcribed here rather than
# reinterpreted: the two `ProcessStop/` nodes and the §13 node start `TRUE`,
# which is not the type's zero, and the rest start at zero because zero is the
# non-permissive value for them.
# --------------------------------------------------------------------------- #

# §12.3 — the mode. The PLC's answer is read-only; the HMI's request is writable
# and is a node the bridge must never touch, in either direction (§4.10).
FORKLIFT_MODE = [
    ("ForkliftDriveModeActive", ua.VariantType.UInt16, 0, False),
    ("HmiDriveModeRequest", ua.VariantType.UInt16, 0, True),
]

# §12.4 — the three envelope elements. NOT writable: a permission is not a
# command, and the server enforces that half independently of the bridge's own
# allowlist (§12.2). The commissioned CPU refuses these with BadNotWritable.
FORKLIFT_ENVELOPE = [
    ("ForkliftMotionEnable", ua.VariantType.Boolean, False),
    ("ForkliftSpeedCeiling", ua.VariantType.Float, 0.0),
    ("ForkliftEquipmentPermit", ua.VariantType.Boolean, False),
]

# §12.6 — what the vehicle's control layer reports back. Client-writable: this
# is the bridge's second input image, and the bridge writes it while the VALUE
# belongs to the vehicle (§12.2, "value owner and node writer are different
# roles").
FORKLIFT_VEHICLE = [
    ("ForkliftVehicleModeApplied", ua.VariantType.UInt16, 0),
    ("ForkliftVehicleHeartbeat", ua.VariantType.UInt16, 0),
]

# §12.7 — the operator's process stop. Both start TRUE (§12.8).
FORKLIFT_PROCESS_STOP = [
    ("ForkliftProcessStopActive", ua.VariantType.Boolean, True, False),
    ("HmiProcessStopRequest", ua.VariantType.Boolean, True, True),
]

# §13 — the warning-field verdict, in its own folder and its own one-member DB.
# Client-writable (the bridge writes it) and START VALUE `TRUE`: before the
# chain has ever spoken, the field reads occupied and the ceiling is reduced.
# That start value is doing real work in this double — it is what a reader sees
# for as long as the bridge has written nothing, and it is what a warm restart
# reverts to (S5, `_start_values`).
FORKLIFT_WARNING = [
    ("ForkliftWarningFieldOccupied", ua.VariantType.Boolean, True),
]

#: The eight nodes the bridge must never read and never write (§4.10): the five
#: `Forklift/Hmi/` requests, `Link/HmiHeartbeat`, and §12's two HMI-written
#: requests. Served — and the two §12 ones served WRITABLE — so that their being
#: untouched is observed rather than assumed.
BRIDGE_MUST_NOT_TOUCH: tuple[str, ...] = tuple(
    name for name, _, _ in FORKLIFT_HMI) + (
    "HmiHeartbeat", "HmiDriveModeRequest", "HmiProcessStopRequest")


async def build(server: Server, idx_server_interfaces: int, idx: int) -> dict:
    """Build the commissioned shape: the ServerInterfaces folder in the Siemens
    namespace, the interface node and everything below it in the interface
    namespace (§3.1). `idx` is the interface namespace index; every node under
    `DemoCell` uses it — the forklift group adds a LEVEL, not a namespace
    (§3.1 N7)."""
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

    # §10.3's folder tree, beside the four M3 folders and under the same
    # interface node.
    forklift = await demo.add_folder(idx, "Forklift")
    fk_folders = {
        "Hmi": await forklift.add_folder(idx, "Hmi"),
        "Input": await forklift.add_folder(idx, "Input"),
        "Output": await forklift.add_folder(idx, "Output"),
        "Status": await forklift.add_folder(idx, "Status"),
        "Link": await forklift.add_folder(idx, "Link"),
    }
    for folder, table in (("Hmi", FORKLIFT_HMI), ("Input", FORKLIFT_INPUTS)):
        for name, vtype, start in table:
            node = await fk_folders[folder].add_variable(idx, name, ua.Variant(start, vtype))
            await node.set_writable()      # §10.3: writable from HMI/OPC UA
            nodes[name] = node
    for folder, table in (("Output", FORKLIFT_OUTPUTS), ("Status", FORKLIFT_STATUS)):
        for name, vtype, start in table:
            nodes[name] = await fk_folders[folder].add_variable(
                idx, name, ua.Variant(start, vtype))
    for name, vtype, start, writable in FORKLIFT_LINK:
        node = await fk_folders["Link"].add_variable(idx, name, ua.Variant(start, vtype))
        if writable:
            await node.set_writable()
        nodes[name] = node

    # §12 and §13 — four more folders beside the five above, under the same
    # interface node and in the same namespace: a group adds a LEVEL, never a
    # namespace (§3.1 N7). The folder names are §12.2's and §13's own, and the
    # commissioned CPU publishes exactly these beside the others (ten in total,
    # `EVIDENCE_ENVELOPE_BRIDGE.md` §1).
    m5_folders = {
        "Mode": await forklift.add_folder(idx, "Mode"),
        "Envelope": await forklift.add_folder(idx, "Envelope"),
        "Vehicle": await forklift.add_folder(idx, "Vehicle"),
        "ProcessStop": await forklift.add_folder(idx, "ProcessStop"),
        "Warning": await forklift.add_folder(idx, "Warning"),
    }
    for folder, table in (("Mode", FORKLIFT_MODE), ("ProcessStop", FORKLIFT_PROCESS_STOP)):
        for name, vtype, start, writable in table:
            node = await m5_folders[folder].add_variable(idx, name, ua.Variant(start, vtype))
            if writable:
                await node.set_writable()
            nodes[name] = node
    for name, vtype, start in FORKLIFT_ENVELOPE:
        # Deliberately NOT writable, so the server-side half of §12.2's two
        # independent enforcements is exercised here as it is on the CPU.
        nodes[name] = await m5_folders["Envelope"].add_variable(
            idx, name, ua.Variant(start, vtype))
    for folder, table in (("Vehicle", FORKLIFT_VEHICLE), ("Warning", FORKLIFT_WARNING)):
        for name, vtype, start in table:
            node = await m5_folders[folder].add_variable(idx, name, ua.Variant(start, vtype))
            await node.set_writable()
            nodes[name] = node
    return nodes


#: Every node the S1 back door may drive: the PLC-owned setpoints of §9.4 and
#: §10.6. Nothing else is addressable through it — the scaffolding is a wire to
#: the output nodes, not a general write facility.
_COMMANDABLE = {
    name: vtype
    for name, vtype, _ in list(OUTPUTS) + list(FORKLIFT_OUTPUTS) + list(FORKLIFT_ENVELOPE)
}
# The PLC-owned §12 verdicts a human may drive through the same back door: the
# mode in force and the process-stop latch. Same standing as the setpoints —
# a hand writing a value, with no input consulted and no condition evaluated.
_COMMANDABLE.update({
    "ForkliftDriveModeActive": ua.VariantType.UInt16,
    "ForkliftProcessStopActive": ua.VariantType.Boolean,
})


async def scaffold_command_file(nodes: dict, path: str, period: float = 0.1) -> None:
    """S1 — TEST SCAFFOLDING. Copies hand-written setpoints from a file into the
    `Output/` nodes. A back door for a human, not PLC logic.

    Two accepted forms, so the M3 harnesses keep working unchanged:

        0.15                      -> ConveyorSpeedCommand (a bare float)
        ForkliftSteerAngleRef=0.7 -> that node, one `Name=value` per line

    No input value is consulted, nothing is sequenced and no condition of any
    kind is evaluated. A real PLC forms these setpoints from requests and
    interlocks; none of that exists in this file.
    """
    last = None
    while True:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read().strip()
            if text and text != last:
                for name, value in _parse_command_file(text).items():
                    await nodes[name].write_value(
                        ua.DataValue(ua.Variant(value, _COMMANDABLE[name])))
                    LOG.info("SCAFFOLD S1: %s := %s (hand-written, not PLC logic)", name, value)
                last = text
        except FileNotFoundError:
            pass
        except (ValueError, KeyError) as exc:
            LOG.warning("SCAFFOLD S1: %s is not a setpoint file (%s)", path, exc)
        await asyncio.sleep(period)


def _parse_command_file(text: str) -> dict[str, float]:
    """`0.15` -> the conveyor command; `Name=value` lines -> those nodes."""
    try:
        return {"ConveyorSpeedCommand": float(text)}
    except ValueError:
        pass
    values: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, raw = line.partition("=")
        name = name.strip()
        if name not in _COMMANDABLE:
            raise KeyError(f"{name!r} is not a commandable node; commandable: "
                           f"{sorted(_COMMANDABLE)}")
        values[name] = _coerce(name, raw.strip())
    return values


def _coerce(name: str, raw: str):
    """Marshal a hand-typed token into the node's own type. `Boolean` accepts
    true/false/1/0, `UInt16` an integer, everything else a float. A token that
    does not fit its node's type is a `ValueError`, never a silently widened
    value: the double must not be the place where a type error is absorbed."""
    vtype = _COMMANDABLE[name]
    if vtype == ua.VariantType.Boolean:
        token = raw.lower()
        if token in ("true", "1"):
            return True
        if token in ("false", "0"):
            return False
        raise ValueError(f"{name}: {raw!r} is not a Boolean")
    if vtype == ua.VariantType.UInt16:
        return int(raw)
    return float(raw)


async def scaffold_echo(nodes: dict, key: str, period: float = 0.02) -> None:
    """S3 — TEST SCAFFOLDING. A wire from one nominated input straight to
    ConveyorSpeedCommand, so the closed-loop L7 interval has something to
    measure. It is a wire, not a decision; a real PLC does nothing like it."""
    while True:
        value = await nodes[key].read_value()
        await nodes["ConveyorSpeedCommand"].write_value(
            ua.DataValue(ua.Variant(float(value), ua.VariantType.Float)))
        await asyncio.sleep(period)


#: Every node in the address space with its start value, in one list, so the
#: warm-restart scaffolding can assign them all without knowing which folder
#: each one lives in.
def _start_values() -> list[tuple[str, ua.VariantType, object]]:
    return (
        [(name, vtype, start) for name, vtype, start in INPUTS]
        + [(name, vtype, start) for name, vtype, start in OUTPUTS]
        + [(name, vtype, start) for name, vtype, start in STATUS]
        + [(name, vtype, start) for name, vtype, start, _ in LINK]
        + [(name, vtype, start) for name, vtype, start in FORKLIFT_HMI]
        + [(name, vtype, start) for name, vtype, start in FORKLIFT_INPUTS]
        + [(name, vtype, start) for name, vtype, start in FORKLIFT_OUTPUTS]
        + [(name, vtype, start) for name, vtype, start in FORKLIFT_STATUS]
        + [(name, vtype, start) for name, vtype, start, _ in FORKLIFT_LINK]
        + [(name, vtype, start) for name, vtype, start, _ in FORKLIFT_MODE]
        + [(name, vtype, start) for name, vtype, start in FORKLIFT_ENVELOPE]
        + [(name, vtype, start) for name, vtype, start in FORKLIFT_VEHICLE]
        + [(name, vtype, start) for name, vtype, start, _ in FORKLIFT_PROCESS_STOP]
        + [(name, vtype, start) for name, vtype, start in FORKLIFT_WARNING]
    )


async def scaffold_warm_restart(nodes: dict, path: str, period: float = 0.05) -> None:
    """S5 — TEST SCAFFOLDING. Touch `path` and every node goes back to its start
    value, in place, while the server and every open session stay up.

    This is what a CPU warm restart looks like from a client that survives it:
    the data block is reinitialised, the OPC UA session is not dropped, and a
    client that writes only on change never repairs the values it believes it
    already wrote (LESSONS 2026-07-28).

    It is a bulk assignment of the start values declared at the top of this file.
    No program runs, no value is derived from another, nothing is sequenced and
    no restart *logic* is modelled — a real CPU does far more, and none of it is
    here. The trigger file is removed afterwards, so each touch is one restart.
    """
    while True:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
            for name, vtype, start in _start_values():
                await nodes[name].write_value(ua.DataValue(ua.Variant(start, vtype)))
            LOG.warning(
                "SCAFFOLD S5: WARM RESTART — every node reset to its start value in "
                "place; sessions untouched (%d client connection(s) still open). "
                "This is a bulk assignment, not a PLC restart sequence.",
                InternalSession._current_connections,
            )
        await asyncio.sleep(period)


#: Columns after the fixed four: the whole served address space bar the PLC
#: verdicts this double never forms. The `Hmi/` requests and `HmiHeartbeat` are
#: in here deliberately — the bridge must never write them, and a column that
#: holds its start value for a whole run is how that is *observed* rather than
#: assumed (§4.10, §10).
_OBSERVED = (
    [name for name, _, _ in INPUTS]
    + ["ConveyorSpeedCommand"]
    + [name for name, _, _ in FORKLIFT_INPUTS]
    + [name for name, _, _ in FORKLIFT_OUTPUTS]
    + [name for name, _, _ in FORKLIFT_HMI]
    + ["HmiHeartbeat"]
    # §12 and §13. `ForkliftWarningFieldOccupied` is the column this file was
    # extended for: a server-side record of what the "PLC" would read, taken by
    # the server itself rather than by the client that wrote it.
    + [name for name, _, _, _ in FORKLIFT_MODE]
    + [name for name, _, _ in FORKLIFT_ENVELOPE]
    + [name for name, _, _ in FORKLIFT_VEHICLE]
    + [name for name, _, _, _ in FORKLIFT_PROCESS_STOP]
    + [name for name, _, _ in FORKLIFT_WARNING]
)


async def observe(nodes: dict, path: str, period: float = 0.2) -> None:
    """S2 — TEST SCAFFOLDING. Server-side record of what the "PLC" sees:
    session count, the bridge's heartbeat, the whole input image of both
    groups, the setpoints and the group the bridge may not touch.

    One file per double session, like the bridge's own evidence file: the path
    given is a stem and the suffix names the session, so restarting the double
    cannot erase what the previous run observed (LESSONS 2026-07-28)."""
    path = session_csv_path(path)
    columns = ["wall_utc", "monotonic_s", "active_sessions", "BridgeHeartbeat"] + _OBSERVED
    with open(path, "x", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(columns)
    LOG.info("SCAFFOLD S2: observing to %s (one file per double session)", path)
    while True:
        row = [
            datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            round(time.monotonic(), 3),
            InternalSession._current_connections,
            await nodes["BridgeHeartbeat"].read_value(),
        ]
        for name in _OBSERVED:
            row.append(await nodes[name].read_value())
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
    LOG.info("address space: %d nodes — %d in opcua-nodes.md §9, %d in §10, %d in §12, "
             "%d in §13; the %d the bridge must never touch (%s) are served WRITABLE, "
             "so its refusal is the bridge's own and not this server's",
             len(nodes), len(INPUTS) + len(OUTPUTS) + len(STATUS) + len(LINK),
             len(FORKLIFT_HMI) + len(FORKLIFT_INPUTS) + len(FORKLIFT_OUTPUTS)
             + len(FORKLIFT_STATUS) + len(FORKLIFT_LINK),
             len(FORKLIFT_MODE) + len(FORKLIFT_ENVELOPE) + len(FORKLIFT_VEHICLE)
             + len(FORKLIFT_PROCESS_STOP), len(FORKLIFT_WARNING),
             len(BRIDGE_MUST_NOT_TOUCH), ", ".join(BRIDGE_MUST_NOT_TOUCH))

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
    if args.warm_restart_file:
        # Start clean: a leftover trigger file would fire a restart at startup.
        if os.path.exists(args.warm_restart_file):
            os.remove(args.warm_restart_file)
        LOG.info("SCAFFOLD S5: touch %s to revert every node to its start value "
                 "in place, sessions left up", args.warm_restart_file)
        tasks.append(asyncio.create_task(scaffold_warm_restart(nodes, args.warm_restart_file)))

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
                        help="S1 scaffolding: file whose contents drive the Output/ nodes — "
                             "a bare float for ConveyorSpeedCommand, or Name=value lines for "
                             "any output node including the three Forklift/Output/*Ref")
    parser.add_argument("--observe-csv", default=None,
                        help="S2 scaffolding: server-side observation log; the path is a "
                             "stem and one file per double session is written")
    parser.add_argument("--warm-restart-file", default=None,
                        help="S5 scaffolding: touching this file reverts every node to its "
                             "start value in place, with sessions left up — a stand-in for "
                             "a CPU warm restart under a surviving session")
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
