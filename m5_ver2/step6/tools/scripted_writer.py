"""scripted_writer.py - the panel's hands, without the panel.

WHY THIS EXISTS
  step6.py's Tk panel is the owner's tool and is not going anywhere. But
  the gates in PROOF.md have to be RUN, and a script cannot click a
  button. This driver is the same writer process with the panel's three
  controls - E-Stop, RESET, the encoder fault mode - moved onto a UDP
  command socket, so a machine can drive a gate end to end and record
  what it saw.

WHAT IT DELIBERATELY DOES NOT DO
  It does not reimplement the cycle. It imports step6 and runs
  step6.control_loop on the same `state`/`live` dicts main() builds, over
  the same sockets, to the same target, with the same `finally` trip
  writes. The production path stays the one under test; only the operator
  is synthetic. If the loop is wrong here it is wrong in the owner's hands
  too, and it fails in the same direction - E-Stop and all six scanner
  inputs False on the way out, however we leave.

THE COMMAND SET IS THE PANEL'S AND NOTHING MORE
  Four buttons and a lamp: {"estop": bool}, {"ack": true},
  {"enc_mode": "ok"|"fa"|"oa"}, {"status": true} for the lamp, and
  {"quit": true} for closing the window. Anything else this socket could
  do would be an operator action the owner cannot reproduce by hand, so
  there is nothing else. The mode strings are read off step6.ENC_TEXT
  rather than retyped, for the same reason.

VIRTUAL ONLY, AND REFUSED OTHERWISE
  There is one PLCSIM Advanced license and no instance for this rig, so
  the driver runs against virtual_fplc. It refuses without --virtual
  rather than reaching for a PLC that is not there - and a scripted
  operator has no eyes on a real plant.

Usage (Windows, any Python):
  python m5_ver2\\step6\\tools\\scripted_writer.py --vehicle f1 \\
      --virtual --ctl-port 5910
"""

import argparse
import json
import os
import socket
import sys
import threading
import time

# step6's module-level argparse reads THIS process's argv, so --vehicle
# and --virtual are already doing their work by the time the import
# returns: env VEHICLE is stamped and status_contract has bound this
# vehicle's port pair. Nothing here may parse argv before that import.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "windows")))

import step6  # noqa: E402

ENC_MODES = tuple(mode for mode, _text in step6.ENC_TEXT)
COMMANDS = ("estop", "ack", "enc_mode", "status", "quit")
CTL_TIMEOUT_S = 0.5     # so `quit` and the log tick are never more than
PRINT_EVERY_S = 2.0     # half a second apart from being noticed
JOIN_S = 2.0            # a hundred cycles: step6.main's own budget


def apply_command(state, msg, now, ack_pulse_s, live):
    """One datagram onto `state`. Returns the reply text, or None.

    Pure but for the two dicts it is handed, which is what makes the
    whole translation testable without a socket or a PLC.

    `live` is last because the first four are the command's own; only the
    status reply needs the loop's side of the pair, and it needs it
    read-only.

    EVERY CHECK HERE IS A REFUSAL TO INVENT AN OPERATOR ACTION. `estop`
    must BE a bool - isinstance(1, bool) is False in Python and that is
    the point, since a truthy non-bool would otherwise release the chain
    off a packet nobody meant to send. `ack` and `quit` must be exactly
    True for the same reason. An unknown `enc_mode` is dropped rather
    than defaulted to "ok": defaulting would heal a fault the caller
    asked for.
    """
    if not isinstance(msg, dict):
        return None
    if isinstance(msg.get("estop"), bool):
        state["estop"] = msg["estop"]
    if msg.get("ack") is True:
        # The F-program wants a rising edge; the loop makes the falling
        # one ACK_PULSE_S later off this same monotonic clock.
        state["ack_until"] = now + ack_pulse_s
    if msg.get("enc_mode") in ENC_MODES:
        state["enc_mode"] = msg["enc_mode"]
    if msg.get("quit") is True:
        # Just the flag. control_loop's own `finally` does the trip
        # writes, exactly as closing the panel window would.
        state["run"] = False
    if msg.get("status") is True:
        return json.dumps({"motor": live["motor"], "line": live["line"],
                           "error": state["error"]})
    return None


def serve(state, live, ctl):
    """The thin shell: read a datagram, apply it, answer if asked.

    Nothing a caller sends may stop the writer, so the whole body is
    guarded: an unparseable datagram, an unknown command or a reply that
    cannot be delivered each cost one stderr line and the loop goes on.
    """
    last_print = 0.0
    while state["run"]:
        now = time.monotonic()
        if now - last_print >= PRINT_EVERY_S:
            last_print = now
            # One record per line so the log file greps.
            print(live["line"].replace("\n", " | "), flush=True)
        try:
            data, addr = ctl.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError as exc:
            print("control channel gone: {}".format(exc), file=sys.stderr)
            return
        try:
            msg = json.loads(data.decode())
            if not isinstance(msg, dict) or not set(msg) & set(COMMANDS):
                raise ValueError("no command in {!r}".format(msg))
            reply = apply_command(
                state, msg, time.monotonic(), step6.ACK_PULSE_S, live)
            if reply is not None:
                ctl.sendto(reply.encode(), addr)
        except Exception as exc:      # noqa: BLE001 - see the docstring
            print("ignored {!r}: {}".format(data[:120], exc), file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="the panel's hands, no panel")
    ap.add_argument("--vehicle", choices=("f1", "f2"), required=True)
    ap.add_argument("--virtual", action="store_true")
    ap.add_argument("--ctl-port", type=int, required=True)
    args = ap.parse_args()
    if not args.virtual or not step6.VIRTUAL:
        raise SystemExit(
            "scripted_writer runs --virtual only: there is no PLCSIM "
            "Advanced instance for this rig, and a scripted operator has "
            "no eyes on a real plant. Use the panel for hardware.")
    # step6 bound its vehicle off the same argv, so a mismatch here means
    # env VEHICLE was already set to something else and this process is a
    # writer for a truck the caller did not name.
    if step6.VID != args.vehicle:
        raise SystemExit(
            "asked for {} but step6 bound {} - env VEHICLE disagrees with "
            "--vehicle".format(args.vehicle, step6.VID))

    state = {"estop": True, "ack_until": 0.0, "run": True,
             "enc_mode": "ok", "error": ""}
    live = {"line": "waiting for the first cycle", "motor": False}

    target = step6.resolve_udp_target()
    print("streaming PLC state to {}:{}".format(target, step6.UDP_PORT))
    plc = step6.connect_plc()
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("0.0.0.0", step6.SENSOR_PORT))
    rx.setblocking(False)
    print("listening for the back scanner on 0.0.0.0:{}"
          .format(step6.SENSOR_PORT))
    ctl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Loopback only. This socket moves a safety input; nothing off this
    # machine gets to press the button.
    ctl.bind(("127.0.0.1", args.ctl_port))
    ctl.settimeout(CTL_TIMEOUT_S)
    print("control channel on 127.0.0.1:{}".format(args.ctl_port), flush=True)

    worker = threading.Thread(
        target=step6.control_loop, args=(plc, target, tx, rx, state, live),
        daemon=True)
    worker.start()
    try:
        serve(state, live, ctl)
    finally:
        state["run"] = False
        worker.join(timeout=JOIN_S)   # its `finally` trips the plant first
        ctl.close()
        rx.close()
        print("writer for {} is down".format(step6.VID), flush=True)


if __name__ == "__main__":
    main()
