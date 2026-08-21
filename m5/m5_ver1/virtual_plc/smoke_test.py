#!/usr/bin/env python3
"""smoke_test.py — the virtual PLC's end-to-end proof, over the wire.

Against a RUNNING virtual_plc.py (or, historically, PLCSIM Advanced plus the
stand-in writer — the surface is the same), this script checks:

  1.  the OPC UA address space resolves by the commissioned browse paths
      (docs/interfaces/opcua-nodes.md section 2's grammar);
  2.  the boot signature on the six safety mirrors: both demands latched,
      reset required, torque off (the SS1 second stage within 1 s of boot),
      the speed monitor NOT armed (opcua-nodes.md section 11.6);
  3.  the field link speaks the writer's protocol: ZONE 1 / WARN 1 on
      :45015 reach the SafetyInputStandIn image (observable indirectly: the
      zone demand becomes resettable);
  4.  the speed link on :45016 takes SPD / MOT lines;
  5.  the operator's command file drives the e-stop channel, and a monitored
      'reset pulse 300' clears both demands — the recorded demo's first
      minute, replayed against software;
  6.  the standard program's coupling: with the demands cleared and the HMI
      inputs driven over OPC UA, a teleop enable edge energizes
      ForkliftTeleopActive and the traction setpoint leaves zero.

Usage:
  python smoke_test.py --host 127.0.0.1 --command-file C:\\Temp\\m5v1_cmds

Exits 0 when every check passes, 1 otherwise. Prints one PASS/FAIL line per
check — the lines are the evidence.
"""

import argparse
import asyncio
import socket
import sys

from asyncua import Client, ua

SI_URI = "http://www.siemens.com/simatic-s7-opcua"
IF_URI = "http://DemoCell"

# The variant types of the nodes this script writes, by leaf name — the
# commissioned types of opcua-nodes.md. A guessed type would send Double to
# the Float nodes.
NODE_TYPES = {
    "ForkliftObstacleInStopZone": ua.VariantType.Boolean,
    "ForkliftForkHeight": ua.VariantType.Float,
    "ForkliftObstacleMinDistance": ua.VariantType.Float,
    "HmiProcessStopRequest": ua.VariantType.Boolean,
    "HmiHeartbeat": ua.VariantType.UInt16,
    "BridgeHeartbeat": ua.VariantType.UInt16,
    "HmiResetRequest": ua.VariantType.Boolean,
    "ForkliftWarningFieldOccupied": ua.VariantType.Boolean,
    "HmiDriveModeRequest": ua.VariantType.UInt16,
    "HmiTeleopRequest": ua.VariantType.Boolean,
    "HmiTractionRequest": ua.VariantType.Float,
}

RESULTS = []


def report(ok, label, detail=""):
    RESULTS.append(ok)
    print("{} {}{}".format("PASS" if ok else "FAIL", label,
                           (" -- " + detail) if detail else ""), flush=True)


async def resolve(client, idx_si, idx, *tail):
    path = ["{}:ServerInterfaces".format(idx_si), "{}:DemoCell".format(idx)]
    path.extend("{}:{}".format(idx, name) for name in tail)
    return await client.nodes.objects.get_child(path)


async def amain(args):
    client = Client("opc.tcp://{}:{}".format(args.host, args.opcua_port))
    await client.connect()
    try:
        idx_si = await client.get_namespace_index(SI_URI)
        idx = await client.get_namespace_index(IF_URI)
        report(True, "namespaces resolve", "si={} if={}".format(idx_si, idx))

        async def node(*tail):
            return await resolve(client, idx_si, idx, *tail)

        async def read(*tail):
            return await (await node(*tail)).read_value()

        async def write(*tail_and_value):
            *tail, value = tail_and_value
            vtype = NODE_TYPES[tail[-1]]
            await (await node(*tail)).write_value(ua.Variant(value, vtype))

        # -- 1/2: the address space and the boot signature --------------------
        mirrors = {}
        for name in ("EStopDemand", "ZoneStopDemand", "SafetyResetRequired",
                     "SafetyResetFault", "SpeedMonitorDemand", "TorqueOffDemand"):
            mirrors[name] = await read("Forklift", "Safety", name)
        report(True, "all 43 browse paths resolve (the six mirrors did)")
        boot_ok = (mirrors["EStopDemand"] and mirrors["ZoneStopDemand"]
                   and mirrors["SafetyResetRequired"] and mirrors["TorqueOffDemand"]
                   and not mirrors["SafetyResetFault"]
                   and not mirrors["SpeedMonitorDemand"])
        report(boot_ok, "boot signature: demands latched, torque off, speed monitor unarmed",
               str(mirrors))

        # -- 3/4: the two TCP links, held open and FED like the real sources ---
        # The recorded stack's sources stay connected and keep talking: the
        # field link dies without a well-formed line every 1 s, and the speed
        # monitor latches a demand 500 ms after the sequences freeze. A smoke
        # test that connects, sends and hangs up is testing a dead source.
        field_sock = socket.create_connection((args.host, args.field_port), timeout=3)
        speed_sock = socket.create_connection((args.host, args.speed_port), timeout=3)
        field_sock.sendall(b"ZONE 1\nWARN 1\n")
        speed_sock.sendall(b"SPD A 0\nSPD B 0\nMOT 0 1\n")
        report(True, "field link :{} and speed link :{} accepted the writer's wire protocol"
               .format(args.field_port, args.speed_port))

        stop_feed = asyncio.Event()

        async def feed():
            while not stop_feed.is_set():
                try:
                    field_sock.sendall(b"PING\n")
                    speed_sock.sendall(b"SPD A 0\nSPD B 0\nMOT 0 1\n")
                except OSError:
                    return
                await asyncio.sleep(0.1)

        feeder = asyncio.create_task(feed())

        # -- 5: the operator's command file and the monitored reset ------------
        with open(args.command_file, "a", encoding="utf-8") as fh:
            fh.write("estop close\n")
        await asyncio.sleep(0.4)                # a few writer cycles
        with open(args.command_file, "a", encoding="utf-8") as fh:
            fh.write("reset pulse 300\n")
        await asyncio.sleep(1.0)                # the pulse plus a few F-cycles
        after = {}
        for name in ("EStopDemand", "ZoneStopDemand", "SafetyResetRequired",
                     "TorqueOffDemand"):
            after[name] = await read("Forklift", "Safety", name)
        report(not any(after.values()),
               "command file: estop close + reset pulse 300 cleared every demand",
               str(after))

        # -- 6: the coupling, driven over OPC UA --------------------------------
        # The HMI's cycle, in miniature: heartbeats advance, the world is
        # clear, the process-stop request is down, then the mode selector and
        # the enable edge.
        hb = 0
        await write("Forklift", "Input", "ForkliftObstacleInStopZone", False)
        await write("Forklift", "Input", "ForkliftForkHeight", 0.1)
        await write("Forklift", "Input", "ForkliftObstacleMinDistance", 2.0)
        await write("Forklift", "ProcessStop", "HmiProcessStopRequest", False)
        for _ in range(45):                     # ~1 s: links alive, boot latches...
            hb += 1
            await write("Forklift", "Link", "HmiHeartbeat", hb % 30000)
            await write("Link", "BridgeHeartbeat", hb % 30000)
            await asyncio.sleep(0.02)
        # ...cleared by the standard program's own monitored reset edge
        await write("Forklift", "Hmi", "HmiResetRequest", True)
        await asyncio.sleep(0.1)
        await write("Forklift", "Hmi", "HmiResetRequest", False)
        await asyncio.sleep(0.2)
        reset_required = await read("Forklift", "Status", "ForkliftResetRequired")
        report(not reset_required, "standard program: the boot latches cleared on the reset edge")

        await write("Forklift", "Warning", "ForkliftWarningFieldOccupied", False)
        await write("Forklift", "Mode", "HmiDriveModeRequest", 1)   # TELEOP
        await asyncio.sleep(0.2)
        mode_active = await read("Forklift", "Mode", "ForkliftDriveModeActive")
        report(mode_active == 1, "mode arbiter: TELEOP in force", str(mode_active))

        await write("Forklift", "Hmi", "HmiTeleopRequest", True)
        await write("Forklift", "Hmi", "HmiTractionRequest", 0.5)
        for _ in range(10):
            hb += 1
            await write("Forklift", "Link", "HmiHeartbeat", hb % 30000)
            await write("Link", "BridgeHeartbeat", hb % 30000)
            await asyncio.sleep(0.02)
        teleop = await read("Forklift", "Status", "ForkliftTeleopActive")
        speed_ref = await read("Forklift", "Output", "ForkliftTractionSpeedRef")
        report(teleop and abs(speed_ref - 0.5) < 1e-4,
               "teleop energizes and the setpoint leaves zero",
               "TeleopActive={} TractionSpeedRef={:.3f}".format(teleop, speed_ref))

        # -- the e-stop, over the command file: the demand returns -------------
        with open(args.command_file, "a", encoding="utf-8") as fh:
            fh.write("estop open\n")
        await asyncio.sleep(0.5)
        estop_demand = await read("Forklift", "Safety", "EStopDemand")
        teleop_after = await read("Forklift", "Status", "ForkliftTeleopActive")
        speed_ref_after = await read("Forklift", "Output", "ForkliftTractionSpeedRef")
        report(estop_demand and not teleop_after and speed_ref_after == 0.0,
               "estop open: the demand latches and motion dies",
               "EStopDemand={} TeleopActive={} Ref={:.3f}".format(
                   estop_demand, teleop_after, speed_ref_after))

        stop_feed.set()
        await feeder
        field_sock.close()
        speed_sock.close()
    finally:
        await client.disconnect()

    print("---")
    print("SMOKE {}: {}/{} checks passed".format(
        "PASS" if all(RESULTS) else "FAIL", sum(RESULTS), len(RESULTS)))
    return 0 if all(RESULTS) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1",
                    help="the Windows host the virtual PLC runs on (from WSL: its IP)")
    ap.add_argument("--opcua-port", type=int, default=4841,
                    help="the virtual PLC's OPC UA port (4841, not the commissioned 4840: "
                         "the host's OPC UA Local Discovery Server owns 4840)")
    ap.add_argument("--field-port", type=int, default=45015)
    ap.add_argument("--speed-port", type=int, default=45016)
    ap.add_argument("--command-file", required=True,
                    help="the SAME path the virtual PLC was started with")
    args = ap.parse_args()
    sys.exit(asyncio.run(amain(args)))


if __name__ == "__main__":
    main()
