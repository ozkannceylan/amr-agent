#!/usr/bin/env python3
"""Read-only witness of the PLC's own view, over OPC UA. TEST INSTRUMENT.

Written for m5-58, the full-stack validation. It is a **client that only
reads**: no write, no subscription the server acts on, nothing it computes
reaching any consumer. Every value below is the controller's, sampled; not one
of them is derived here.

Why it exists, and why it is a *second* witness. `observe_envelope_chain.py`
records the vehicle end of the chain off the ROS graph. This records the PLC
end off the OPC UA server, which is a different protocol stack reading a
different memory. When the two agree that the envelope was withdrawn and the
vehicle stopped, neither is echoing the other (LESSONS 2026-08-04: look for a
second witness on a different protocol stack). It also reads the six
`Forklift/Safety/` mirrors, which the F-program owns; four of the six appear on
no ROS topic at all — so the latch state is read from the controller rather than
inferred from the vehicle standing still (LESSONS 2026-08-06: stillness is not
evidence).

What it does NOT read: `"SafetyInputStandIn"` and `"InstF_Forklift_Safety"` are
not published by the server interface, deliberately. The writer's own
`standin_writer/testing/observe_consumer.ps1` is the instrument for those, and
it reads them through the PLCSIM Advanced API instead.

Usage (after sourcing /opt/ros/jazzy/setup.bash is NOT required; this is a
plain asyncua client):

    python3 bridge/tools/observe_safety_mirrors.py \
        --endpoint opc.tcp://192.168.53.1:4840 \
        --csv <path> --seconds 300 --hz 10
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import sys
import time

from asyncua import Client

NS_SERVER_INTERFACES = "http://www.siemens.com/simatic-s7-opcua"
NS_INTERFACE = "http://DemoCell"

#: (column name, path under the interface node). Transcribed from
#: `opcua-nodes.md` §10, §12 and §13 and confirmed against the controller in
#: force by `probe_server_paths.py` on 2026-08-06.
PATHS = [
    # The F-program's mirrors (§6.4). SIX since the 2026-08-07 fix session
    # (F-signature 29FD2C52): `SpeedMonitorDemand` and `TorqueOffDemand` were
    # added by TIA-FIX-PROCEDURE chunks AD-AF and read back on the controller in
    # force by `probe_server_paths.py` before this list was extended (LESSONS
    # 2026-08-06: probe the server before editing a client-side path list).
    # All six are read-only at the server, access level RD.
    ("EStopDemand", ("Forklift", "Safety", "EStopDemand")),
    ("ZoneStopDemand", ("Forklift", "Safety", "ZoneStopDemand")),
    ("SafetyResetRequired", ("Forklift", "Safety", "SafetyResetRequired")),
    ("SafetyResetFault", ("Forklift", "Safety", "SafetyResetFault")),
    ("SpeedMonitorDemand", ("Forklift", "Safety", "SpeedMonitorDemand")),
    ("TorqueOffDemand", ("Forklift", "Safety", "TorqueOffDemand")),
    # The envelope the standard program forms (§12).
    ("DriveModeActive", ("Forklift", "Mode", "ForkliftDriveModeActive")),
    ("MotionEnable", ("Forklift", "Envelope", "ForkliftMotionEnable")),
    ("SpeedCeiling", ("Forklift", "Envelope", "ForkliftSpeedCeiling")),
    ("EquipmentPermit", ("Forklift", "Envelope", "ForkliftEquipmentPermit")),
    # The warning verdict as the PLC received it (§13).
    ("WarningFieldOccupied", ("Forklift", "Warning", "ForkliftWarningFieldOccupied")),
    # The setpoints the standard program formed, and the plant reading behind
    # them (§10).
    ("TractionSpeedRef", ("Forklift", "Output", "ForkliftTractionSpeedRef")),
    ("SteerAngleRef", ("Forklift", "Output", "ForkliftSteerAngleRef")),
    ("LinearSpeed", ("Forklift", "Input", "ForkliftLinearSpeed")),
    ("ObstacleInStopZone", ("Forklift", "Input", "ForkliftObstacleInStopZone")),
    ("ObstacleMinDistance", ("Forklift", "Input", "ForkliftObstacleMinDistance")),
    # Status, and the two link verdicts.
    ("TeleopActive", ("Forklift", "Status", "ForkliftTeleopActive")),
    ("ObstacleStopActive", ("Forklift", "Status", "ForkliftObstacleStopActive")),
    ("SpeedLimitActive", ("Forklift", "Status", "ForkliftSpeedLimitActive")),
    ("ResetRequired", ("Forklift", "Status", "ForkliftResetRequired")),
    ("ProcessStopActive", ("Forklift", "ProcessStop", "ForkliftProcessStopActive")),
    ("HmiLinkOk", ("Forklift", "Link", "HmiLinkOk")),
    ("VehicleModeApplied", ("Forklift", "Vehicle", "ForkliftVehicleModeApplied")),
    ("VehicleHeartbeat", ("Forklift", "Vehicle", "ForkliftVehicleHeartbeat")),
    ("BridgeHeartbeat", ("Link", "BridgeHeartbeat")),
]

#: Printed as a transition line when they change. The rest are recorded to the
#: CSV only, so the console stays readable during a run.
WATCH = (
    "EStopDemand", "ZoneStopDemand", "SafetyResetRequired", "SafetyResetFault",
    "SpeedMonitorDemand", "TorqueOffDemand",
    "MotionEnable", "SpeedCeiling", "EquipmentPermit", "DriveModeActive",
    "WarningFieldOccupied", "ObstacleInStopZone", "TeleopActive",
    "ProcessStopActive", "SpeedLimitActive",
)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", default="opc.tcp://192.168.53.1:4840")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--hz", type=float, default=10.0)
    ap.add_argument("--label", default="", help="free text recorded in the header")
    args = ap.parse_args()

    period = 1.0 / args.hz
    started = datetime.datetime.now(datetime.timezone.utc)

    async with Client(args.endpoint) as opc:
        uris = await opc.get_namespace_array()
        ns_si = uris.index(NS_SERVER_INTERFACES)
        ns_if = uris.index(NS_INTERFACE)
        objects = opc.get_objects_node()
        interface = await objects.get_child(
            [f"{ns_si}:ServerInterfaces", f"{ns_if}:DemoCell"])

        nodes = []
        names = []
        for name, path in PATHS:
            nodes.append(await interface.get_child([f"{ns_if}:{p}" for p in path]))
            names.append(name)

        print(f"# observe_safety_mirrors  endpoint={args.endpoint}")
        print(f"# started={started.isoformat()}  label={args.label!r}")
        print(f"# {len(nodes)} nodes, {args.hz} Hz, {args.seconds} s -> {args.csv}")
        sys.stdout.flush()

        t0 = time.monotonic()
        last = {}
        rows = 0
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["t_s", "utc"] + names)
            next_tick = t0
            while time.monotonic() - t0 < args.seconds:
                next_tick += period
                vals = await opc.read_values(nodes)
                now = time.monotonic() - t0
                utc = datetime.datetime.now(
                    datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
                w.writerow([f"{now:.3f}", utc] + list(vals))
                rows += 1
                if rows % 20 == 0:
                    fh.flush()
                for name, val in zip(names, vals):
                    if name in WATCH and last.get(name) != val:
                        if name in last:
                            print(f"{now:8.3f}  {utc}  {name}: "
                                  f"{last[name]} -> {val}")
                            sys.stdout.flush()
                        last[name] = val
                sleep = next_tick - time.monotonic()
                if sleep > 0:
                    await asyncio.sleep(sleep)
                else:
                    next_tick = time.monotonic()
        print(f"# {rows} rows written to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
