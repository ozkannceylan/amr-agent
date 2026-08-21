#!/usr/bin/env python3
"""verify_commissioning.py — the M4 gate exercise, headless, against the
virtual PLC.

The five M4 gate criteria (m4/README.md), exercised through the operator's
own surfaces: the HMI's POST /control and GET /state (the page's API), the
writer's command file (the e-stop/zone/reset devices), and the arena's
AisleCrate moved by sim/scenarios/forklift_stimulus.py — the T5.4 stimulus
itself. Phase (e) kills the HMI and reads the PLC directly over OPC UA,
the watch table's role.

THE CPU IN FORCE IS THE LATER BUILD. The M4 CPU ran the standard program
with no F-side; the virtual PLC runs the M5-commissioned build, whose
section-7 core IS the M4 program. The differences the operator sees are
named at each step: the boot demands and their monitored reset (F-program),
the mode-entry handshake (section 14.8), and the warning-field input the
exercise drives clear (section 14.17) so the M4-era caps are visible.

Prerequisites: m4/run_commissioning.sh start completed in WSL; the virtual
PLC running on Windows with --command-file matching --command-file here.

Run on Windows:
  python m4\\verify_commissioning.py --command-file C:\\Temp\\m4_cmds
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
import urllib.request

RESULTS = []


def report(ok, label, detail=""):
    if ok is None:
        print("SKIP {}{}".format(label, (" -- " + detail) if detail else ""), flush=True)
        return
    RESULTS.append(bool(ok))
    print("{} {}{}".format("PASS" if ok else "FAIL", label,
                           (" -- " + detail) if detail else ""), flush=True)


def get_state(base):
    with urllib.request.urlopen(base + "/state", timeout=3) as h:
        return json.load(h)


def metrics(state):
    return state.get("metrics") or {}


def control(base, **payload):
    req = urllib.request.Request(
        base + "/control", data=json.dumps(payload).encode("ascii"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=3) as h:
        return json.load(h)


def cmd(command_file, line):
    with open(command_file, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def wsl(script):
    return subprocess.run(["wsl", "-e", "bash", "-c", script],
                          capture_output=True, text=True, timeout=60)


def obstacle(args, *ob_args):
    return wsl("source /opt/ros/jazzy/setup.bash && cd {} && python3 sim/scenarios/forklift_stimulus.py obstacle {}".format(
        args.wsl_repo, " ".join(ob_args)))


def wait_metric(base, key, pred, timeout_s):
    end = time.monotonic() + timeout_s
    value = None
    while time.monotonic() < end:
        value = metrics(get_state(base)).get(key)
        if pred(value):
            return True, value
        time.sleep(0.25)
    return False, value


# ---------------------------------------------------------------------------
# Phase (e) reads the PLC directly — the HMI is dead by then.
# ---------------------------------------------------------------------------

SI_URI = "http://www.siemens.com/simatic-s7-opcua"
IF_URI = "http://DemoCell"


async def read_plc_direct(endpoint, leaves):
    from asyncua import Client
    client = Client(endpoint)
    await client.connect()
    try:
        idx_si = await client.get_namespace_index(SI_URI)
        idx = await client.get_namespace_index(IF_URI)

        async def node(*tail):
            path = ["{}:ServerInterfaces".format(idx_si), "{}:DemoCell".format(idx)]
            path.extend("{}:{}".format(idx, name) for name in tail)
            return await client.nodes.objects.get_child(path)

        out = {}
        for key, tail in leaves.items():
            out[key] = await (await node(*tail)).read_value()
        return out
    finally:
        await client.disconnect()


def main():
    ap = argparse.ArgumentParser(description="the M4 gate exercise, headless")
    ap.add_argument("--hmi", default="http://127.0.0.1:8088")
    ap.add_argument("--command-file", required=True)
    ap.add_argument("--wsl-repo", default="/mnt/c/Users/ozkan/projects/amr-agent")
    ap.add_argument("--plc-endpoint", default="opc.tcp://127.0.0.1:4841")
    args = ap.parse_args()

    # -- 0. boot signature ----------------------------------------------------
    m = metrics(get_state(args.hmi))
    if (m.get("EStopDemand") is False and m.get("ZoneStopDemand") is False
            and m.get("SafetyResetRequired") is False):
        report(None, "boot: warm CPU (the virtual PLC outlived the last run) "
               "- the boot-latch checks are skipped, the reset prelude is idempotent")
    else:
        report(m.get("EStopDemand") is True and m.get("ZoneStopDemand") is True
               and m.get("SafetyResetRequired") is True,
               "boot: the F-program's demands stand (the M5-era CPU's signature)",
               json.dumps({k: m.get(k) for k in ("EStopDemand", "ZoneStopDemand",
                                                 "SafetyResetRequired", "TorqueOffDemand")}))

    # -- 1. the monitored reset + mode entry (the later CPU's handshake) ------
    cmd(args.command_file, "estop close")
    cmd(args.command_file, "zone close")
    time.sleep(0.6)
    control(args.hmi, process_stop=False)
    time.sleep(0.4)
    control(args.hmi, reset=True)
    time.sleep(0.2)
    cmd(args.command_file, "reset pulse 2000")
    time.sleep(2.6)
    control(args.hmi, reset=False)
    time.sleep(0.6)
    m = metrics(get_state(args.hmi))
    report(m.get("EStopDemand") is False and m.get("ZoneStopDemand") is False
           and m.get("SafetyResetRequired") is False
           and m.get("ForkliftResetRequired") is False
           and m.get("ForkliftProcessStopActive") is False,
           "the monitored reset cleared every demand and every latch",
           json.dumps({k: m.get(k) for k in ("EStopDemand", "ZoneStopDemand",
                                             "ForkliftResetRequired",
                                             "ForkliftProcessStopActive")}))

    control(args.hmi, drive_mode=1)
    time.sleep(0.8)
    m = metrics(get_state(args.hmi))
    report(m.get("ForkliftDriveModeActive") == 1,
           "mode arbiter: TELEOP in force (section 14.8 — the M5 addition)",
           "DriveModeActive={}".format(m.get("ForkliftDriveModeActive")))

    # -- (a) teleop drive ------------------------------------------------------
    control(args.hmi, teleop=True, traction=0.3)
    time.sleep(2.5)
    m = metrics(get_state(args.hmi))
    speed = m.get("ForkliftLinearSpeed")
    report(m.get("ForkliftTeleopActive") is True
           and abs(m.get("ForkliftTractionSpeedRef", 0.0) - 0.3) < 1e-3
           and isinstance(speed, (int, float)) and speed > 0.05,
           "(a) teleop drive: the vehicle moves under the PLC's setpoint",
           "TeleopActive={} Ref={} LinearSpeed={}".format(
               m.get("ForkliftTeleopActive"), m.get("ForkliftTractionSpeedRef"), speed))
    control(args.hmi, traction=0.0)

    # -- (b) fork raise to the soft limit --------------------------------------
    control(args.hmi, teleop=True, fork=1.0)
    ok, height = wait_metric(args.hmi, "ForkliftForkHeight",
                             lambda v: isinstance(v, (int, float)) and v >= 1.5495, 25)
    report(ok, "(b) the fork rises on command", "ForkHeight={}".format(height))
    ok2, ref = wait_metric(args.hmi, "ForkliftForkSpeedRef",
                           lambda v: isinstance(v, (int, float)) and abs(v) < 1e-9, 4)
    m = metrics(get_state(args.hmi))
    report(ok2, "(b) the soft travel limit zeroes the setpoint while the demand stands",
           "height={:.3f} ForkSpeedRef={} (FORK_TRAVEL_MAX 1.55)".format(
               m.get("ForkliftForkHeight", -1), ref))
    control(args.hmi, fork=0.0)

    # -- (c) the speed cap with the fork raised --------------------------------
    control(args.hmi, teleop=True, traction=1.0)
    time.sleep(1.5)
    m = metrics(get_state(args.hmi))
    report(abs(m.get("ForkliftTractionSpeedRef", 0.0) - 0.30) < 1e-3
           and m.get("ForkliftSpeedLimitActive") is True,
           "(c) fork above 0.50 m: traction capped at 0.30 m/s, limit lamp on",
           "Ref={} SpeedLimitActive={}".format(m.get("ForkliftTractionSpeedRef"),
                                               m.get("ForkliftSpeedLimitActive")))
    control(args.hmi, traction=0.0)
    control(args.hmi, teleop=True, fork=-1.0)
    ok, height = wait_metric(args.hmi, "ForkliftForkHeight",
                             lambda v: isinstance(v, (int, float)) and v <= 0.45, 30)
    control(args.hmi, fork=0.0)
    m = metrics(get_state(args.hmi))
    report(ok and m.get("ForkliftSpeedLimitActive") is False,
           "(c) fork back below 0.50 m: the cap lifts", "ForkHeight={}".format(height))

    # -- (d) the obstacle latch, the refusal, the monitored reset --------------
    obstacle(args, "--home")
    time.sleep(1.5)
    if metrics(get_state(args.hmi)).get("ForkliftObstacleStopActive") is True:
        ok = True    # re-run: the vehicle parked inside the zone last time
    else:
        control(args.hmi, teleop=True, traction=0.8)
        ok, _ = wait_metric(args.hmi, "ForkliftObstacleStopActive",
                            lambda v: v is True, 40)
    m = metrics(get_state(args.hmi))
    report(ok and m.get("ForkliftTeleopActive") is False
           and abs(m.get("ForkliftTractionSpeedRef", 1.0)) < 1e-9
           and m.get("ForkliftResetRequired") is True,
           "(d) the crate in the stop zone: latch, override, zeroed setpoints",
           "ObstacleStopActive={} MinDistance={}".format(
               m.get("ForkliftObstacleStopActive"), m.get("ForkliftObstacleMinDistance")))

    control(args.hmi, traction=0.0, teleop=False)
    control(args.hmi, reset=True)               # refused: the zone is occupied
    time.sleep(1.2)
    control(args.hmi, reset=False)
    m = metrics(get_state(args.hmi))
    report(m.get("ForkliftObstacleStopActive") is True,
           "(d) reset refused while the cause stands", "")

    obstacle(args, "--to-x", "8.0")
    time.sleep(1.5)
    control(args.hmi, reset=True)               # the fresh edge, cause gone
    time.sleep(1.2)
    control(args.hmi, reset=False)
    time.sleep(0.5)
    m = metrics(get_state(args.hmi))
    report(m.get("ForkliftObstacleStopActive") is False
           and m.get("ForkliftResetRequired") is False
           and m.get("ForkliftTeleopActive") is False,
           "(d) crate clear + fresh reset edge: latches clear, nothing resumes", "")

    # -- (e) the HMI's heartbeat stops ------------------------------------------
    control(args.hmi, teleop=True, traction=0.3)
    time.sleep(1.5)
    m = metrics(get_state(args.hmi))
    moving = m.get("ForkliftTeleopActive") is True
    wsl("kill -TERM -$(cat {}/m4/runtime/hmi.pid) 2>/dev/null; rm -f {}/m4/runtime/hmi.pid".format(
        args.wsl_repo, args.wsl_repo))
    time.sleep(2.5)                             # HMI_STALE_TIME is 500 ms
    try:
        plc = asyncio.run(read_plc_direct(args.plc_endpoint, {
            "HmiLinkOk": ("Forklift", "Link", "HmiLinkOk"),
            "TractionSpeedRef": ("Forklift", "Output", "ForkliftTractionSpeedRef"),
            "TeleopActive": ("Forklift", "Status", "ForkliftTeleopActive"),
            "ResetRequired": ("Forklift", "Status", "ForkliftResetRequired"),
        }))
        report(moving and plc["HmiLinkOk"] is False
               and abs(plc["TractionSpeedRef"]) < 1e-9
               and plc["TeleopActive"] is False
               and plc["ResetRequired"] is True,
               "(e) HMI dead: its link verdict drops and the setpoints die",
               "HmiLinkOk={} Ref={} TeleopActive={} ResetRequired={}".format(
                   plc["HmiLinkOk"], plc["TractionSpeedRef"],
                   plc["TeleopActive"], plc["ResetRequired"]))
    except Exception as exc:                    # noqa: BLE001 - the report is the point
        report(False, "(e) HMI dead: direct PLC read", "exception: {}".format(exc))

    print("---")
    print("COMMISSIONING {}: {}/{} checks passed".format(
        "PASS" if all(RESULTS) else "FAIL", sum(RESULTS), len(RESULTS)))
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
