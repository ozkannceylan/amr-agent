#!/usr/bin/env python3
"""virtual_plc.py — the first build's CPU, answered in software.

The PLCSIM Advanced trial expired. This process stands where PLCSIM Advanced
stood: it serves the commissioned 43-node OPC UA address space
(docs/interfaces/opcua-nodes.md sections 9-13), runs the standard program
(standard_program.py, 20 ms) and the F-program's behavioural model
(f_program.py, 100 ms), and plays the automated stand-in writer's role
(bridge/standin_writer/standin_writer.ps1) toward the same two TCP links.

TWO ERAS, ONE PROCESS. The same address space also carries the M3
demonstration cell's 15-node subtree (opcua-nodes.md section 9), and
demo_cell_program.py runs FB_DemoCellControl in the same 20 ms cadence.
Historically these were two CPUs (the cell's PLC_1, the vehicle's F-CPU);
here one server answers both, and which era a run meets is decided by which
subtree its clients configure. The cell's link half (BridgeLinkOk) keeps its
M5-era home in standard_program.py's companion fragment — one tag, one
writer.

  - field link  :45015  ZONE 0|1 / WARN 0|1 / PING   (SPEC 7.2)
  - speed link  :45016  SPD A|B <int> / MOT <p> <v> / PING   (SPEC 11.2)

and the same operator surface: console commands and a command file
(estop open|close, zone open|close, reset press|release, reset pulse <ms>,
status, quit), the named mutex Global\\amr-standin-writer, and a 50 ms cycle
advancing StandInHeartbeat. .archive/demo.sh detects this process exactly as
it detected the writer: the mutex plus the two listeners.

IT IS NOT A PLC AND CARRIES NO SAFETY INTEGRITY — the same sentence the
writer's own design said about itself (STANDIN-WRITER-DESIGN.md). The F-side
model reproduces the documented behaviour of the F-networks; it is nobody's
F-runtime group.

Run (Windows, beside the repo):
  python m5\\m5_ver1\\virtual_plc\\virtual_plc.py --command-file C:\\Temp\\m5v1_cmds
"""

import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asyncua import Server, ua  # noqa: E402

import demo_cell_program as cellprog  # noqa: E402
import f_program  # noqa: E402
import standard_program as std  # noqa: E402

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

CYCLE_WRITER = 0.050   # SPEC 7.1
CYCLE_STANDARD = 0.020  # OB30
CYCLE_F = 0.100         # OB123, read back 2026-08-04 (m5-03)
FIELD_LINK_STALE_MAX = 1.0    # SPEC 7.2
MOTION_SILENCE_MAX = 0.250    # SPEC 11.2 writer design value
HB_WRAP = 30000               # wraps 30000 -> 0, inside positive Int16
PULSE_MIN_MS = 1
PULSE_MAX_MS = 60000
MUTEX_NAME = r"Global\amr-standin-writer"

INTERFACE_NAMESPACE_URI = "http://DemoCell"
SERVER_INTERFACES_NAMESPACE_URI = "http://www.siemens.com/simatic-s7-opcua"

# ---------------------------------------------------------------------------
# The address space — opcua-nodes.md sections 9-13, the same 43 nodes the
# bridge's test double serves, with the same types, start values and access
# rights. (name, type, start, writable-by-a-client)
# ---------------------------------------------------------------------------

DEMOCELL_INPUT = [
    ("ConveyorBeltPosition", ua.VariantType.Float, 0.0, True),
    ("ConveyorBeltSpeed", ua.VariantType.Float, 0.0, True),
    ("ProductSensorRange", ua.VariantType.Float, 0.0, True),
    ("PanelStartPressed", ua.VariantType.Boolean, False, True),
    ("PanelResetPressed", ua.VariantType.Boolean, False, True),
    ("PanelStopCircuitClosed", ua.VariantType.Boolean, False, True),
    ("PanelProcessStopCircuitClosed", ua.VariantType.Boolean, False, True),
]
DEMOCELL_OUTPUT = [("ConveyorSpeedCommand", ua.VariantType.Float, 0.0, False)]
DEMOCELL_STATUS = [
    ("CellCycleRunning", ua.VariantType.Boolean, False, False),
    ("CellProcessStopActive", ua.VariantType.Boolean, False, False),
    ("CellResetRequired", ua.VariantType.Boolean, False, False),
    ("ProductPresentAtSensor", ua.VariantType.Boolean, False, False),
    ("ConveyorDriveFault", ua.VariantType.Boolean, False, False),
]
DEMOCELL_LINK = [
    ("BridgeHeartbeat", ua.VariantType.UInt16, 0, True),
    ("BridgeLinkOk", ua.VariantType.Boolean, False, False),
]
FORKLIFT_HMI = [
    ("HmiTractionRequest", ua.VariantType.Float, 0.0, True),
    ("HmiSteerRequest", ua.VariantType.Float, 0.0, True),
    ("HmiForkRequest", ua.VariantType.Float, 0.0, True),
    ("HmiTeleopRequest", ua.VariantType.Boolean, False, True),
    ("HmiResetRequest", ua.VariantType.Boolean, False, True),
]
FORKLIFT_INPUT = [
    ("ForkliftForkHeight", ua.VariantType.Float, 0.0, True),
    ("ForkliftLinearSpeed", ua.VariantType.Float, 0.0, True),
    ("ForkliftObstacleInStopZone", ua.VariantType.Boolean, True, True),
    ("ForkliftObstacleMinDistance", ua.VariantType.Float, 0.0, True),
]
FORKLIFT_OUTPUT = [
    ("ForkliftTractionSpeedRef", ua.VariantType.Float, 0.0, False),
    ("ForkliftSteerAngleRef", ua.VariantType.Float, 0.0, False),
    ("ForkliftForkSpeedRef", ua.VariantType.Float, 0.0, False),
]
FORKLIFT_STATUS = [
    ("ForkliftTeleopActive", ua.VariantType.Boolean, False, False),
    ("ForkliftObstacleStopActive", ua.VariantType.Boolean, False, False),
    ("ForkliftSpeedLimitActive", ua.VariantType.Boolean, False, False),
    ("ForkliftResetRequired", ua.VariantType.Boolean, False, False),
]
FORKLIFT_LINK = [
    ("HmiHeartbeat", ua.VariantType.UInt16, 0, True),
    ("HmiLinkOk", ua.VariantType.Boolean, False, False),
]
FORKLIFT_MODE = [
    ("ForkliftDriveModeActive", ua.VariantType.UInt16, 0, False),
    ("HmiDriveModeRequest", ua.VariantType.UInt16, 0, True),
]
FORKLIFT_ENVELOPE = [
    ("ForkliftMotionEnable", ua.VariantType.Boolean, False, False),
    ("ForkliftSpeedCeiling", ua.VariantType.Float, 0.0, False),
    ("ForkliftEquipmentPermit", ua.VariantType.Boolean, False, False),
]
FORKLIFT_VEHICLE = [
    ("ForkliftVehicleModeApplied", ua.VariantType.UInt16, 0, True),
    ("ForkliftVehicleHeartbeat", ua.VariantType.UInt16, 0, True),
]
FORKLIFT_PROCESS_STOP = [
    ("ForkliftProcessStopActive", ua.VariantType.Boolean, True, False),
    ("HmiProcessStopRequest", ua.VariantType.Boolean, True, True),
]
FORKLIFT_WARNING = [
    ("ForkliftWarningFieldOccupied", ua.VariantType.Boolean, True, True),
]
# section 11: the six mirrors. Read-only to every client (MR1); the start
# values are the sources' boot truth (section 11.6).
FORKLIFT_SAFETY = [
    ("EStopDemand", ua.VariantType.Boolean, True, False),
    ("ZoneStopDemand", ua.VariantType.Boolean, True, False),
    ("SafetyResetRequired", ua.VariantType.Boolean, True, False),
    ("SafetyResetFault", ua.VariantType.Boolean, False, False),
    ("SpeedMonitorDemand", ua.VariantType.Boolean, False, False),
    ("TorqueOffDemand", ua.VariantType.Boolean, True, False),
]


class Log:
    """One file per session, never truncated — the writer's rule."""

    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.path = os.path.join(LOG_DIR,
                                 "virtual-plc-{}-pid{}.log".format(stamp, os.getpid()))
        self.fh = open(self.path, "x", encoding="utf-8")

    def _line(self, klass, detail):
        return "{} | {} | {}\n".format(
            time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
            + ".{:03d}Z".format(int(time.time() * 1000) % 1000), klass, detail)

    def file_only(self, klass, detail):
        self.fh.write(self._line(klass, detail))
        self.fh.flush()

    def say(self, klass, detail):
        line = self._line(klass, detail)
        self.fh.write(line)
        self.fh.flush()
        print(line, end="", flush=True)


# ---------------------------------------------------------------------------
# The writer role — standin_writer.ps1's behaviour, same constants, same
# commands, same refusals. It owns the SafetyInputStandIn image.
# ---------------------------------------------------------------------------


class WriterRole:
    def __init__(self, img, log, command_file, console_ok):
        self.img = img
        self.log = log
        self.command_file = command_file
        self.console_ok = console_ok
        self.running = True
        self.field_client = None          # one field-evaluation client at a time
        self.field_last = 0.0             # last well-formed field line, monotonic
        self.speed_client = None
        self.speed_last_mot = 0.0
        self.cmd_offset = 0
        self.cmd_partial = ""
        self._cmd_warned = False
        # The operator's channels boot in the demand direction, as the writer's
        # $st did: e-stop OPEN, zone OPEN, reset unpressed.
        self.img.EStopCircuitClosed = False
        self.img.ZoneDeviceCircuitClosed = False
        self.img.ResetButtonPressed = False
        self._pulse_end = None            # monotonic deadline of a reset pulse

    # ---- the operator's commands, Invoke-Command2's vocabulary --------------
    def command(self, raw):
        cmd = " ".join(raw.split())
        if not cmd:
            return
        low = cmd.lower()
        if low in ("estop open", "estop close"):
            v = low.endswith("close")
            self.img.EStopCircuitClosed = v
            self.log.say("OPERATOR", "estop {} -> EStopCircuitClosed := {}".format(low[6:], v))
        elif low in ("zone open", "zone close"):
            if self.field_client is not None:
                self.log.say("REFUSED", "'{}': the field-evaluation link is up and owns "
                                        "the zone channel; one channel, one source at any moment".format(cmd))
            else:
                v = low.endswith("close")
                self.img.ZoneDeviceCircuitClosed = v
                self.log.say("OPERATOR", "zone {} -> ZoneDeviceCircuitClosed := {}".format(low[5:], v))
        elif low == "reset press":
            self.img.ResetButtonPressed = True
            self._pulse_end = None
            self.log.say("OPERATOR", "reset press -> ResetButtonPressed := True (held until countermanded)")
        elif low == "reset release":
            self.img.ResetButtonPressed = False
            self._pulse_end = None
            self.log.say("OPERATOR", "reset release -> ResetButtonPressed := False")
        elif low.startswith("reset pulse "):
            try:
                ms = int(low.rsplit(" ", 1)[1])
            except ValueError:
                self.log.say("REFUSED", "'{}': the pulse width must be an integer number of milliseconds".format(cmd))
                return
            if not (PULSE_MIN_MS <= ms <= PULSE_MAX_MS):
                self.log.say("REFUSED", "'{}': the pulse width must be {}..{} ms".format(cmd, PULSE_MIN_MS, PULSE_MAX_MS))
            elif self.img.ResetButtonPressed:
                self.log.say("REFUSED", "'{}': ResetButtonPressed is already held; a second "
                                        "actuation needs the first to end".format(cmd))
            else:
                self.img.ResetButtonPressed = True
                self._pulse_end = time.monotonic() + ms / 1000.0
                self.log.say("OPERATOR", "reset pulse {0} -> ResetButtonPressed := True now, False after "
                                         "{0} ms (the F-program judges the hold)".format(ms))
        elif low == "status":
            self.log.say("OPERATOR", "status -- estop={} zone={} reset={} hb={} "
                                     "field_link={} speed_link={}".format(
                self.img.EStopCircuitClosed, self.img.ZoneDeviceCircuitClosed,
                self.img.ResetButtonPressed, self.img.StandInHeartbeat,
                self.field_client is not None, self.speed_client is not None))
        elif low == "quit":
            self.running = False
            self.log.say("OPERATOR", "quit")
        else:
            self.log.say("REFUSED", "'{}': unrecognised command. Known: estop open|close, "
                                    "zone open|close, reset press|release, reset pulse <ms>, status, quit. "
                                    "There is deliberately no operator command for the speed readings, the "
                                    "motion observation or the warning field: those come from a source or "
                                    "they are missing".format(cmd))

    # ---- the two TCP links ---------------------------------------------------
    def field_line(self, line):
        line = line.strip()
        low = line.lower()
        if low in ("zone 0", "zone 1"):
            v = low.endswith("1")
            self.field_last = time.monotonic()
            self.img.ZoneDeviceCircuitClosed = v
            self.log.say("FIELD", "ZONE {} -> ZoneDeviceCircuitClosed := {} ({})".format(
                line[-1], v, "field clear, circuit closed" if v
                else "intrusion or evaluation fault, circuit open"))
        elif low in ("warn 0", "warn 1"):
            v = low.endswith("1")
            self.field_last = time.monotonic()
            self.img.WarningFieldClear = v
            self.log.say("FIELD", "WARN {} -> WarningFieldClear := {} ({})".format(
                line[-1], v, "warning field clear" if v
                else "warning field occupied -- the limit is selected"))
        elif low == "ping":
            self.field_last = time.monotonic()
        elif line:
            self.log.say("REFUSED", "field link: malformed line '{}' -- it refreshes nothing; "
                                    "bytes are not proof of a live verdict".format(line))

    def speed_line(self, line):
        line = line.strip()
        parts = line.split()
        if len(parts) == 3 and parts[0].upper() == "SPD" and parts[1].upper() in ("A", "B"):
            try:
                v = int(parts[2])
            except ValueError:
                self.log.say("REFUSED", "speed link: malformed line '{}'".format(line))
                return
            if not (-32768 <= v <= 32767):
                self.log.say("REFUSED", "speed link: '{}' out of Int16 range".format(line))
                return
            if parts[1].upper() == "A":
                self.img.SpeedReadingA = v
                self.img.SpeedSeqA = (self.img.SpeedSeqA + 1) % HB_WRAP
            else:
                self.img.SpeedReadingB = v
                self.img.SpeedSeqB = (self.img.SpeedSeqB + 1) % HB_WRAP
            self.log.file_only("SPEED", line)
        elif len(parts) == 3 and parts[0].upper() == "MOT":
            self.img.MotionPresent = parts[1] == "1"
            self.img.MotionObservationValid = parts[2] == "1"
            self.speed_last_mot = time.monotonic()
            self.log.file_only("SPEED", line)
        elif len(parts) == 1 and parts[0].upper() == "PING":
            pass
        elif line:
            self.log.say("REFUSED", "speed link: malformed line '{}'".format(line))

    def field_down(self, why):
        if self.field_client is not None:
            self.field_client = None
            self.img.ZoneDeviceCircuitClosed = False
            self.img.WarningFieldClear = False
            self.log.say("LINK", "down ({}); ZoneDeviceCircuitClosed driven FALSE (open) AND "
                                 "WarningFieldClear driven FALSE -- loss of the field source reads as "
                                 "intrusion and as warning-occupied, never as a clear field".format(why))

    def speed_down(self, why):
        if self.speed_client is not None:
            self.speed_client = None
            self.log.say("SPEEDLINK", "down ({})".format(why))

    async def cycle(self):
        """One writer cycle: heartbeat, pulse deadline, stale reapers, command file."""
        self.img.StandInHeartbeat = (self.img.StandInHeartbeat + 1) % HB_WRAP

        if self._pulse_end is not None and time.monotonic() >= self._pulse_end:
            self.img.ResetButtonPressed = False
            self._pulse_end = None
            self.log.say("OPERATOR", "reset pulse elapsed -> ResetButtonPressed := False")

        if self.field_client is not None and \
                time.monotonic() - self.field_last > FIELD_LINK_STALE_MAX:
            self.field_down("stale: no well-formed line for {} ms".format(int(FIELD_LINK_STALE_MAX * 1000)))

        # MOT silence: the motion channel reads MOVING (SPEC 11.2 writer rule).
        if self.speed_client is not None and self.speed_last_mot and \
                time.monotonic() - self.speed_last_mot > MOTION_SILENCE_MAX:
            if not self.img.MotionPresent:
                self.img.MotionPresent = True
                self.img.MotionObservationValid = False
                self.log.say("SPEEDLINK", "MOT silent for {} ms -> MotionPresent driven TRUE "
                                          "(moving): silence can never corroborate a standstill".format(
                                              int(MOTION_SILENCE_MAX * 1000)))

        if self.command_file:
            await self._poll_command_file()

    async def _poll_command_file(self):
        try:
            if not os.path.exists(self.command_file):
                return
            with open(self.command_file, "r", encoding="utf-8") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                if size < self.cmd_offset:      # truncated or replaced under us
                    self.cmd_offset = 0
                    self.cmd_partial = ""
                if size <= self.cmd_offset:
                    return
                fh.seek(self.cmd_offset)
                text = self.cmd_partial + fh.read()
                self.cmd_offset = size
            lines = text.split("\n")
            self.cmd_partial = lines[-1]
            for line in lines[:-1]:
                if line.strip():
                    self.log.say("OPERATOR", "command file: {}".format(line.strip()))
                    self.command(line)
        except OSError as exc:
            if not self._cmd_warned:
                self._cmd_warned = True
                self.log.say("REFUSED", "command file {} unreadable ({}); the writer keeps its "
                                        "cycle and its links, and the console is unaffected".format(
                                            self.command_file, exc))


# ---------------------------------------------------------------------------
# The OPC UA server and the three cyclic tasks.
# ---------------------------------------------------------------------------


async def build_address_space(server):
    idx_si = await server.register_namespace(SERVER_INTERFACES_NAMESPACE_URI)
    idx = await server.register_namespace(INTERFACE_NAMESPACE_URI)
    objects = server.nodes.objects
    server_interfaces = await objects.add_folder(idx_si, "ServerInterfaces")
    demo = await server_interfaces.add_folder(idx, "DemoCell")

    nodes = {}

    async def fill(parent, table):
        for name, vtype, start, writable in table:
            node = await parent.add_variable(idx, name, ua.Variant(start, vtype))
            if writable:
                await node.set_writable(True)
            nodes[name] = (node, vtype)

    for folder, table in (("Input", DEMOCELL_INPUT), ("Output", DEMOCELL_OUTPUT),
                          ("Status", DEMOCELL_STATUS), ("Link", DEMOCELL_LINK)):
        await fill(await demo.add_folder(idx, folder), table)

    forklift = await demo.add_folder(idx, "Forklift")
    for folder, table in (("Hmi", FORKLIFT_HMI), ("Input", FORKLIFT_INPUT),
                          ("Output", FORKLIFT_OUTPUT), ("Status", FORKLIFT_STATUS),
                          ("Link", FORKLIFT_LINK), ("Mode", FORKLIFT_MODE),
                          ("Envelope", FORKLIFT_ENVELOPE), ("Vehicle", FORKLIFT_VEHICLE),
                          ("ProcessStop", FORKLIFT_PROCESS_STOP),
                          ("Warning", FORKLIFT_WARNING), ("Safety", FORKLIFT_SAFETY)):
        await fill(await forklift.add_folder(idx, folder), table)
    return nodes


# Client-writable nodes the standard scan reads into its image every cycle.
# (node name, object path into Db) — the process image transfer.
def _input_map(db, cell):
    return [
        ("HmiTractionRequest", db.ForkliftHmi, "HmiTractionRequest"),
        ("HmiSteerRequest", db.ForkliftHmi, "HmiSteerRequest"),
        ("HmiForkRequest", db.ForkliftHmi, "HmiForkRequest"),
        ("HmiTeleopRequest", db.ForkliftHmi, "HmiTeleopRequest"),
        ("HmiResetRequest", db.ForkliftHmi, "HmiResetRequest"),
        ("HmiDriveModeRequest", db.ForkliftMode, "HmiDriveModeRequest"),
        ("HmiProcessStopRequest", db.ForkliftProcessStop, "HmiProcessStopRequest"),
        ("ForkliftForkHeight", db.ForkliftInput, "ForkliftForkHeight"),
        ("ForkliftLinearSpeed", db.ForkliftInput, "ForkliftLinearSpeed"),
        ("ForkliftObstacleInStopZone", db.ForkliftInput, "ForkliftObstacleInStopZone"),
        ("ForkliftObstacleMinDistance", db.ForkliftInput, "ForkliftObstacleMinDistance"),
        ("ForkliftVehicleModeApplied", db.ForkliftVehicle, "ForkliftVehicleModeApplied"),
        ("ForkliftVehicleHeartbeat", db.ForkliftVehicle, "ForkliftVehicleHeartbeat"),
        ("ForkliftWarningFieldOccupied", db.ForkliftWarning, "ForkliftWarningFieldOccupied"),
        ("HmiHeartbeat", db.ForkliftLink, "HmiHeartbeat"),
        ("BridgeHeartbeat", db.DemoCellLink, "BridgeHeartbeat"),
        # The M3 cell's seven device contacts (demo-cell SPEC 3.1) — the second
        # era this CPU answers. Written by a cell-configured bridge, or still.
        ("ConveyorBeltPosition", cell, "ConveyorBeltPosition"),
        ("ConveyorBeltSpeed", cell, "ConveyorBeltSpeed"),
        ("ProductSensorRange", cell, "ProductSensorRange"),
        ("PanelStartPressed", cell, "PanelStartPressed"),
        ("PanelResetPressed", cell, "PanelResetPressed"),
        ("PanelStopCircuitClosed", cell, "PanelStopCircuitClosed"),
        ("PanelProcessStopCircuitClosed", cell, "PanelProcessStopCircuitClosed"),
    ]


def _output_map(db, cell):
    return [
        ("ForkliftTractionSpeedRef", db.ForkliftOutput.ForkliftTractionSpeedRef),
        ("ForkliftSteerAngleRef", db.ForkliftOutput.ForkliftSteerAngleRef),
        ("ForkliftForkSpeedRef", db.ForkliftOutput.ForkliftForkSpeedRef),
        ("ForkliftTeleopActive", db.ForkliftStatus.ForkliftTeleopActive),
        ("ForkliftObstacleStopActive", db.ForkliftStatus.ForkliftObstacleStopActive),
        ("ForkliftSpeedLimitActive", db.ForkliftStatus.ForkliftSpeedLimitActive),
        ("ForkliftResetRequired", db.ForkliftStatus.ForkliftResetRequired),
        ("HmiLinkOk", db.ForkliftLink.HmiLinkOk),
        ("BridgeLinkOk", db.DemoCellLink.BridgeLinkOk),
        ("ForkliftDriveModeActive", db.ForkliftMode.ForkliftDriveModeActive),
        ("ForkliftMotionEnable", db.ForkliftEnvelope.ForkliftMotionEnable),
        ("ForkliftSpeedCeiling", db.ForkliftEnvelope.ForkliftSpeedCeiling),
        ("ForkliftEquipmentPermit", db.ForkliftEnvelope.ForkliftEquipmentPermit),
        ("ForkliftProcessStopActive", db.ForkliftProcessStop.ForkliftProcessStopActive),
        ("EStopDemand", db.ForkliftSafetyMirror.EStopDemand),
        ("ZoneStopDemand", db.ForkliftSafetyMirror.ZoneStopDemand),
        ("SafetyResetRequired", db.ForkliftSafetyMirror.SafetyResetRequired),
        ("SafetyResetFault", db.ForkliftSafetyMirror.SafetyResetFault),
        ("SpeedMonitorDemand", db.ForkliftSafetyMirror.SpeedMonitorDemand),
        ("TorqueOffDemand", db.ForkliftSafetyMirror.TorqueOffDemand),
        # The M3 cell's outputs (demo-cell SPEC 3.1).
        ("ConveyorSpeedCommand", cell.ConveyorSpeedCommand),
        ("CellCycleRunning", cell.CellCycleRunning),
        ("CellProcessStopActive", cell.CellProcessStopActive),
        ("CellResetRequired", cell.CellResetRequired),
        ("ProductPresentAtSensor", cell.ProductPresentAtSensor),
        ("ConveyorDriveFault", cell.ConveyorDriveFault),
    ]


async def standard_loop(nodes, db, st, dc, cell, cst, fst, log):
    inputs = _input_map(db, cell)
    while True:
        t0 = time.monotonic()
        for name, obj, attr in inputs:
            setattr(obj, attr, (await nodes[name][0].read_value()))
        std.scan(db, st, dc, fst, CYCLE_STANDARD)
        # The M3 FB runs after the fragment, consuming this cycle's
        # BridgeLinkOk — the OB30 call order of demo-cell SPEC 4.1.
        cellprog.scan(cell, cst, db.DemoCellLink.BridgeLinkOk, CYCLE_STANDARD)
        for name, value in _output_map(db, cell):
            node, vtype = nodes[name]
            await node.write_value(ua.Variant(value, vtype))
        elapsed = time.monotonic() - t0
        await asyncio.sleep(max(0.0, CYCLE_STANDARD - elapsed))


async def f_loop(img, fst, log):
    while True:
        t0 = time.monotonic()
        f_program.scan(img, fst, CYCLE_F)
        elapsed = time.monotonic() - t0
        await asyncio.sleep(max(0.0, CYCLE_F - elapsed))


async def writer_loop(writer, log):
    while writer.running:
        t0 = time.monotonic()
        await writer.cycle()
        elapsed = time.monotonic() - t0
        log.file_only("CYCLE", "writer cycle {:.1f} ms".format(elapsed * 1000))
        await asyncio.sleep(max(0.0, CYCLE_WRITER - elapsed))


def acquire_mutex(log):
    """The named mutex, so demo.sh's writer_present() finds this process and a
    second virtual PLC refuses to start — the writer's own rule (5.3)."""
    if os.name != "nt":
        log.say("MUTEX", "not Windows: the named mutex exists for demo.sh's Windows-side "
                         "check and is skipped here")
        return None
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if not handle:
        log.say("MUTEX", "CreateMutexW failed; nothing was touched")
        sys.exit(2)
    if ctypes.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        log.say("MUTEX", "refused to start: the mutex {} is already held, so a stand-in "
                         "writer or virtual PLC is already running on this host. Two writers "
                         "on one DB would be a second writer of every tag.".format(MUTEX_NAME))
        sys.exit(3)
    log.say("MUTEX", "held {}".format(MUTEX_NAME))
    return handle


async def amain(args):
    log = Log()
    log.say("START", "virtual PLC — standing where PLCSIM Advanced stood. NOT a PLC; "
                     "no safety integrity. Log: {}".format(log.path))
    mutex = None if args.no_mutex else acquire_mutex(log)

    img = f_program.StandInImage()
    fst = f_program.FStatics()
    db = std.Db()
    st = std.Statics()
    dc = std.DemoCellStatics()
    cell = cellprog.CellDb()
    cst = cellprog.CellStatics()
    writer = WriterRole(img, log, args.command_file, console_ok=not args.no_console)

    server = Server()
    await server.init()
    server.set_endpoint(args.endpoint)
    nodes = await build_address_space(server)

    async def field_client(reader, _writer):
        peer = _writer.get_extra_info("peername")
        if writer.field_client is not None:
            log.say("LINK", "refused a second connection: one field-evaluation client at a time")
            _writer.close()
            return
        writer.field_client = _writer
        writer.field_last = time.monotonic()
        img.ZoneDeviceCircuitClosed = False
        img.WarningFieldClear = False
        log.say("LINK", "up: field-evaluation client {} connected; the zone channel now belongs "
                        "to the field and is held FALSE until its first ZONE line -- a link with "
                        "no verdict yet is not a clear field".format(peer))
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                writer.field_line(data.decode("ascii", "replace"))
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        writer.field_down("the field evaluation closed the connection")

    async def speed_client(reader, _writer):
        peer = _writer.get_extra_info("peername")
        if writer.speed_client is not None:
            log.say("SPEEDLINK", "refused a second connection: one speed source at a time")
            _writer.close()
            return
        writer.speed_client = _writer
        writer.speed_last_mot = time.monotonic()
        log.say("SPEEDLINK", "up: speed source {} connected".format(peer))
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                writer.speed_line(data.decode("ascii", "replace"))
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        writer.speed_down("the speed source closed the connection")

    field_server = await asyncio.start_server(field_client, "0.0.0.0", args.field_port)
    speed_server = await asyncio.start_server(speed_client, "0.0.0.0", args.speed_port)
    log.say("LINK", "listening on 0.0.0.0:{} for the field evaluation; none is required -- "
                    "while none is up the zone channel belongs to the operator".format(args.field_port))
    log.say("SPEEDLINK", "listening on 0.0.0.0:{} for the speed source; none is required -- "
                         "while none is up both sequences stay frozen and the motion channel "
                         "reads MOVING".format(args.speed_port))

    async with server:
        log.say("START", "OPC UA serving {} nodes at {}".format(len(nodes), args.endpoint))
        tasks = [asyncio.create_task(standard_loop(nodes, db, st, dc, cell, cst, fst, log)),
                 asyncio.create_task(f_loop(img, fst, log)),
                 asyncio.create_task(writer_loop(writer, log))]
        console_thread = None
        if not args.no_console:
            import threading

            def console():
                # The operator's keyboard. It only ever sets the three device
                # channels and the pulse deadline -- the same words the
                # PowerShell writer's console took, with the same discipline.
                while writer.running:
                    line = sys.stdin.readline()
                    if not line:
                        return
                    writer.command(line)

            console_thread = threading.Thread(target=console, daemon=True)
            console_thread.start()
        try:
            await tasks[2]          # the writer loop ends on 'quit'
        finally:
            for t in tasks:
                t.cancel()
    field_server.close()
    speed_server.close()
    log.say("STOP", "virtual PLC down; the CPU is yours to stop, as PLCSIM was")
    if mutex is not None:
        import ctypes
        ctypes.windll.kernel32.CloseHandle(mutex)


def main():
    ap = argparse.ArgumentParser(description="The first build's CPU, answered in software.")
    ap.add_argument("--endpoint", default="opc.tcp://0.0.0.0:4841",
                    help="OPC UA endpoint. Default 4841, not the commissioned 4840: that port "
                         "belonged to PLCSIM Advanced's virtual NIC (192.168.53.1) and on the "
                         "host the OPC UA Local Discovery Server owns it")
    ap.add_argument("--field-port", type=int, default=45015)
    ap.add_argument("--speed-port", type=int, default=45016)
    ap.add_argument("--command-file", default="",
                    help="the operator's second keyboard: lines appended here are fed to the "
                         "same command handler as the console")
    ap.add_argument("--no-mutex", action="store_true",
                    help="do not hold Global\\amr-standin-writer (tests, non-Windows)")
    ap.add_argument("--no-console", action="store_true")
    args = ap.parse_args()
    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
