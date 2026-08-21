#!/usr/bin/env python3
"""drive_demo.py — the recorded demo's first two minutes, replayed headless.

Against a stack brought up by `m5/m5_ver1/demo.sh up --headless` with the
virtual PLC on the Windows side, this script does what the operator did on
camera, through the same two surfaces (the writer's command file and the
HMI's POST /control):

  1.  read the boot state: every demand latched, torque off (intended);
  2.  estop close  (command file — the writer's e-stop channel);
  3.  release PROCESS STOP  (HMI standing control);
  4.  the monitored reset: HMI RESET held while `reset pulse 2000` runs at
      the writer — both across the same window, as the runbook demands;
  5.  select TELEOP, deadman on, traction 0.3: the vehicle moves — proven by
      the PLC's own ForkliftLinearSpeed, read back over the HMI's /state;
  6.  estop open: the demand latches and motion dies.

Every step prints one line; the lines are the evidence. Exit 0 iff every
expectation held. Run on Windows (the HMI page's loopback is forwarded from
WSL; the command file is a Windows path):

  python m5\\m5_ver1\\drive_demo.py --command-file C:\\Temp\\m5v1_cmds
"""

import argparse
import json
import sys
import time
import urllib.request

RESULTS = []


def report(ok, label, detail=""):
    RESULTS.append(bool(ok))
    print("{} {}{}".format("PASS" if ok else "FAIL", label,
                           (" -- " + detail) if detail else ""), flush=True)


def get_state(base):
    with urllib.request.urlopen(base + "/state", timeout=3) as h:
        return json.load(h)


def control(base, **payload):
    req = urllib.request.Request(
        base + "/control", data=json.dumps(payload).encode("ascii"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=3) as h:
        return json.load(h)


def cmd(command_file, line):
    with open(command_file, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def metrics(state):
    return state.get("metrics") or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hmi", default="http://127.0.0.1:8088")
    ap.add_argument("--command-file", required=True)
    args = ap.parse_args()

    m = metrics(get_state(args.hmi))
    report(m.get("EStopDemand") is True and m.get("ZoneStopDemand") is True
           and m.get("SafetyResetRequired") is True
           and m.get("ForkliftProcessStopActive") is True,
           "boot: demands latched, process stop active", json.dumps(m))

    cmd(args.command_file, "estop close")
    time.sleep(0.6)
    control(args.hmi, process_stop=False)
    time.sleep(0.4)

    # The monitored reset: HMI RESET held, the writer's pulse across the same
    # window. The HMI re-writes its standing state every 100 ms, so one POST
    # holds the button.
    control(args.hmi, reset=True)
    time.sleep(0.2)
    cmd(args.command_file, "reset pulse 2000")
    time.sleep(2.6)
    control(args.hmi, reset=False)
    time.sleep(0.6)
    m = metrics(get_state(args.hmi))
    cleared = (m.get("EStopDemand") is False and m.get("ZoneStopDemand") is False
               and m.get("SafetyResetRequired") is False
               and m.get("ForkliftResetRequired") is False
               and m.get("ForkliftProcessStopActive") is False)
    report(cleared, "the monitored reset cleared every demand and every latch",
           json.dumps(m))

    control(args.hmi, drive_mode=1)             # TELEOP
    time.sleep(0.6)
    m = metrics(get_state(args.hmi))
    report(m.get("ForkliftDriveModeActive") == 1, "mode arbiter: TELEOP in force",
           "DriveModeActive={}".format(m.get("ForkliftDriveModeActive")))

    control(args.hmi, teleop=True, traction=0.3)
    time.sleep(2.5)
    m = metrics(get_state(args.hmi))
    speed = m.get("ForkliftLinearSpeed")
    report(m.get("ForkliftTeleopActive") is True
           and abs(m.get("ForkliftTractionSpeedRef", 0.0) - 0.3) < 1e-3
           and isinstance(speed, (int, float)) and speed > 0.05,
           "deadman on, traction 0.3: the vehicle MOVES in the warehouse",
           "TeleopActive={} Ref={} LinearSpeed={}".format(
               m.get("ForkliftTeleopActive"), m.get("ForkliftTractionSpeedRef"), speed))

    control(args.hmi, traction=0.0, teleop=False)
    time.sleep(1.0)
    cmd(args.command_file, "estop open")
    time.sleep(0.8)
    m = metrics(get_state(args.hmi))
    report(m.get("EStopDemand") is True
           and m.get("ForkliftTeleopActive") is False
           and m.get("ForkliftTractionSpeedRef") == 0.0,
           "estop open: the demand latches and motion dies",
           "EStopDemand={} TeleopActive={} Ref={}".format(
               m.get("EStopDemand"), m.get("ForkliftTeleopActive"),
               m.get("ForkliftTractionSpeedRef")))

    print("---")
    print("DRIVE {}: {}/{} checks passed".format(
        "PASS" if all(RESULTS) else "FAIL", sum(RESULTS), len(RESULTS)))
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
