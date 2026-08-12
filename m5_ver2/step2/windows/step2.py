"""step2.py - the ONLY process that writes to the safety PLC.

Runs on Windows, on 64-bit Python, against S7-PLCSIM Advanced instance
"PLC_2". Every 20 ms it writes the field-device picture the safety program
needs and reads back the one output that matters.

WHY PF_OSSD, WF_Clear AND THE ENCODERS ARE WRITTEN EVERY CYCLE
  Motor is the AND of three ESTOP1 enables. Two of them watch the
  protective field and the encoder cross-check, so unless this loop holds
  those healthy the drive enable can never energise, no matter what the
  e-stop button does. They are not Step 1's subject; they are its
  precondition.

THE FAIL DIRECTION
  Any exception, `q`, or Ctrl-C leaves through the same `finally`: E-Stop,
  PF_OSSD and WF_Clear are written False. The vehicle side then sees the
  link go quiet and fails safe on its own 0.5 s rule.

Usage (Windows, 64-bit Python, PLCSIM Advanced already in RUN):
  python m5_ver2\\step2\\windows\\step2.py
"""

import json
import socket
import subprocess
import sys
import threading
import time

# ----------------------------- CONFIG -----------------------------
PLC_INSTANCE = "PLC_2"
API_DLL_DIR = r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0"
UDP_TARGET = None      # None -> ask `wsl.exe hostname -I`. A string overrides.
UDP_PORT = 5100
CYCLE_S = 0.02         # 20 ms
ACK_PULSE_S = 0.30
STATUS_EVERY = 10      # print the status line every Nth cycle (~5 Hz)
# ------------------------------------------------------------------


def _first_token(text):
    """First whitespace-separated token, which is the WSL eth0 address.

    `wsl.exe hostname -I` may append the docker bridge address; only the
    first one is reachable from Windows.
    """
    parts = text.split()
    if not parts:
        raise RuntimeError("`wsl.exe hostname -I` returned no address")
    return parts[0]


def resolve_udp_target(configured=UDP_TARGET):
    """The WSL guest IP, discovered rather than hard-coded.

    WSL2 here is NAT, not mirrored, so 127.0.0.1 does not reach the guest,
    and the guest's address is reassigned on every WSL restart. Discovering
    it each run is the difference between a script that works and one that
    breaks silently next week.
    """
    if configured:
        return configured
    out = subprocess.check_output(
        ["wsl.exe", "hostname", "-I"], text=True, timeout=10)
    return _first_token(out)


def _say(msg):
    """Print, but never let a dead stdout stop a PLC write.

    An unguarded print in the shutdown path raises BrokenPipeError and skips
    the trip writes -- the same fail-safe escape by another door.
    """
    try:
        print(msg)
    except OSError:
        pass


def status_payload(estop_healthy, motor, ts):
    """The wire format plc_link.py parses. Three keys, no more."""
    return json.dumps({
        "estop_healthy": bool(estop_healthy),
        "motor": bool(motor),
        "ts": float(ts),
    }).encode()


def connect_plc():
    """CreateInterface, with the -4 case reported rather than worked around."""
    sys.path.append(API_DLL_DIR)
    import clr
    clr.AddReference("Siemens.Simatic.Simulation.Runtime.Api.x64")
    from Siemens.Simatic.Simulation.Runtime import (
        SimulationRuntimeManager, ETagListDetails)
    try:
        plc = SimulationRuntimeManager.CreateInterface(PLC_INSTANCE)
    except Exception as exc:
        raise SystemExit(
            "Cannot reach PLCSIM Advanced instance '{}': {}\n"
            "If this is error -4 (DoesNotExist), the instance is not running "
            "or the name differs. Start it from the PLCSIM Advanced Control "
            "Panel and download the program from TIA Portal.".format(
                PLC_INSTANCE, exc))
    plc.UpdateTagList(ETagListDetails.IOM)
    return plc


def main():
    state = {"estop": True, "ack_until": 0.0, "run": True}

    def reader():
        print("commands: es0 (press e-stop) | es1 (release) | a (ack) | q")
        while state["run"]:
            try:
                cmd = input().strip().lower()
            except EOFError:
                state["run"] = False
                return
            if cmd == "es0":
                state["estop"] = False
            elif cmd == "es1":
                state["estop"] = True
            elif cmd == "a":
                state["ack_until"] = time.monotonic() + ACK_PULSE_S
            elif cmd == "q":
                state["run"] = False

    target = resolve_udp_target()
    print("streaming PLC state to {}:{}".format(target, UDP_PORT))
    plc = connect_plc()
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    threading.Thread(target=reader, daemon=True).start()

    cycle = 0
    try:
        while state["run"]:
            now = time.monotonic()
            plc.WriteBool("PF_OSSD", True)
            plc.WriteBool("WF_Clear", True)
            plc.WriteInt16("ENC_A", 0)
            plc.WriteInt16("ENC_B", 0)
            plc.WriteBool("E-Stop", state["estop"])
            plc.WriteBool("Acknowledge", now < state["ack_until"])

            motor = plc.ReadBool("Motor")
            estop_healthy = plc.ReadBool("E-Stop")
            tx.sendto(status_payload(estop_healthy, motor, now),
                      (target, UDP_PORT))
            # Cosmetic, and never allowed to gate the PLC writes: an undrained
            # pipe blocks print() without raising, which would freeze the sole
            # writer with Motor still energised and never reach the finally.
            cycle += 1
            if cycle % STATUS_EVERY == 0:
                try:
                    print("\rE-Stop={:<5} Motor={:<5} ack={:<5}   ".format(
                        str(estop_healthy), str(motor),
                        str(now < state["ack_until"])), end="", flush=True)
                except OSError:
                    pass
            time.sleep(CYCLE_S)
    finally:
        _say("\nshutting down: writing the trip values")
        for tag in ("E-Stop", "PF_OSSD", "WF_Clear"):
            try:
                plc.WriteBool(tag, False)
            except Exception as exc:
                _say("could not trip {}: {}".format(tag, exc))
        tx.close()


if __name__ == "__main__":
    main()
