"""scripted_writer.py - the panel's hands, without the panel.

WHY THIS EXISTS
  m6.py's Tk panel is the owner's tool and is not going anywhere. But
  the gates in PROOF.md have to be RUN, and a script cannot click a
  button. This driver is the same writer process with the panel's three
  controls - E-Stop, RESET, the encoder fault mode - moved onto a UDP
  command socket, so a machine can drive a gate end to end and record
  what it saw.

WHAT IT DELIBERATELY DOES NOT DO
  It does not reimplement the cycle. It imports m6 and runs
  m6.control_loop on the same `state`/`live` dicts main() builds, over
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
  there is nothing else. The mode strings are read off m6.ENC_TEXT
  rather than retyped, for the same reason.

VIRTUAL ONLY, AND REFUSED OTHERWISE
  There is one PLCSIM Advanced license and no instance for this rig, so
  the driver runs against virtual_fplc. It refuses without --virtual
  rather than reaching for a PLC that is not there - and a scripted
  operator has no eyes on a real plant.

Usage (Windows, any Python):
  python m6\\tools\\scripted_writer.py --vehicle f1 \\
      --virtual --ctl-port 5910
"""

import argparse
import json
import os
import socket
import sys
import threading
import time

# m6's module-level argparse reads THIS process's argv, so --vehicle
# and --virtual are already doing their work by the time the import
# returns: env VEHICLE is stamped and status_contract has bound this
# vehicle's port pair. Nothing here may parse argv before that import.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "windows")))

import m6  # noqa: E402

ENC_MODES = tuple(mode for mode, _text in m6.ENC_TEXT)
COMMANDS = ("estop", "ack", "enc_mode", "status", "quit")
CTL_TIMEOUT_S = 0.5     # so `quit` and the log tick are never more than
PRINT_EVERY_S = 2.0     # half a second apart from being noticed
JOIN_S = 2.0            # a hundred cycles: m6.main's own budget


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


# ---- the latch watchdog: a demo-only automatic operator ----
# OWNER RULING, 2026-08-23. PROOF.md residual 10: a protective demand
# LATCHES and only a panel RESET clears it. A ten-minute recording has no
# operator in it, so the first latch costs a truck for the rest of the
# run - and in the 0-of-8 acceptance run four latches inside 0.56 s cost
# all of it. So a recording gets an automatic operator, and it SAYS SO:
# every press below is printed with its timestamp and the line the writer
# was reading, and the count goes into PROOF.md beside the run labelled
# demo-only automatic operator.
#
# WHAT IT DOES NOT DO, AND THIS IS THE WHOLE OF THE HONESTY. It does not
# touch a scanner, a field verdict, the nan rule or the staleness rule -
# an undelivered scan is still a violated field and still demands a stop.
# It presses the button a person would have pressed, after the stop has
# already happened. And it will not press through a HELD e-stop: that is
# the operator's own hand and acknowledging it away would be inventing an
# action nobody asked for.
RESET_HOLD_S = 3.0      # a press per 3 s at most: the F-program wants a
                        # rising edge and the loop makes the falling one
                        # ACK_PULSE_S later; pressing faster than that
                        # stacks edges the PLC never sees separately.


def latch_watch(live, state, now, last_reset, hold_s=RESET_HOLD_S):
    """(press_reset, log_line). Pure - the caller owns the socket."""
    if live.get("motor"):
        return (False, None)
    if state.get("estop"):
        return (False, None)
    if now - last_reset < hold_s:
        return (False, None)
    return (True, "AUTO-RESET t={:.1f} after: {}".format(
        now, str(live.get("line", "")).replace("\n", " | ")))


def serve(state, live, ctl, auto_reset=False, resets=None):
    """The thin shell: read a datagram, apply it, answer if asked.

    Nothing a caller sends may stop the writer, so the whole body is
    guarded: an unparseable datagram, an unknown command or a reply that
    cannot be delivered each cost one stderr line and the loop goes on.
    """
    resets = [0] if resets is None else resets
    last_reset = 0.0
    last_print = 0.0
    while state["run"]:
        now = time.monotonic()
        if now - last_print >= PRINT_EVERY_S:
            last_print = now
            # One record per line so the log file greps.
            print(live["line"].replace("\n", " | "), flush=True)
        if auto_reset:
            press, line = latch_watch(live, state, now, last_reset)
            if press:
                last_reset = now
                resets[0] += 1
                state["ack_until"] = now + m6.ACK_PULSE_S
                print(line, flush=True)
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
                state, msg, time.monotonic(), m6.ACK_PULSE_S, live)
            if reply is not None:
                ctl.sendto(reply.encode(), addr)
        except Exception as exc:      # noqa: BLE001 - see the docstring
            print("ignored {!r}: {}".format(data[:120], exc), file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="the panel's hands, no panel")
    # THE IDS ARE m6's, NOT A SECOND SPELLING OF THE TABLE. m6 already
    # holds the guarded tuple (test_vehicles_table.py asserts it against
    # status_contract.VEHICLES), and this parser is built after that
    # import, so borrowing it costs nothing and cannot drift. A literal
    # here was f1/f2 until M6.5 and would have refused f3 and f4 - the
    # gates need four of these drivers.
    ap.add_argument("--vehicle", choices=m6.VEHICLE_IDS, required=True)
    ap.add_argument("--virtual", action="store_true")
    ap.add_argument("--ctl-port", type=int, required=True)
    ap.add_argument("--auto-reset", action="store_true",
                    help="press RESET on a latched truck (recordings "
                         "only; every press is logged)")
    args = ap.parse_args()
    if not args.virtual or not m6.VIRTUAL:
        raise SystemExit(
            "scripted_writer runs --virtual only: there is no PLCSIM "
            "Advanced instance for this rig, and a scripted operator has "
            "no eyes on a real plant. Use the panel for hardware.")
    # m6 bound its vehicle off the same argv, so a mismatch here means
    # env VEHICLE was already set to something else and this process is a
    # writer for a truck the caller did not name.
    if m6.VID != args.vehicle:
        raise SystemExit(
            "asked for {} but m6 bound {} - env VEHICLE disagrees with "
            "--vehicle".format(args.vehicle, m6.VID))

    state = {"estop": True, "ack_until": 0.0, "run": True,
             "enc_mode": "ok", "error": ""}
    live = {"line": "waiting for the first cycle", "motor": False}

    target = m6.resolve_udp_target()
    print("streaming PLC state to {}:{}".format(target, m6.UDP_PORT))
    plc = m6.connect_plc()
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("0.0.0.0", m6.SENSOR_PORT))
    rx.setblocking(False)
    print("listening for the back scanner on 0.0.0.0:{}"
          .format(m6.SENSOR_PORT))
    ctl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Loopback only. This socket moves a safety input; nothing off this
    # machine gets to press the button.
    ctl.bind(("127.0.0.1", args.ctl_port))
    ctl.settimeout(CTL_TIMEOUT_S)
    print("control channel on 127.0.0.1:{}".format(args.ctl_port), flush=True)

    worker = threading.Thread(
        target=m6.control_loop, args=(plc, target, tx, rx, state, live),
        daemon=True)
    worker.start()
    resets = [0]
    try:
        serve(state, live, ctl, auto_reset=args.auto_reset, resets=resets)
    finally:
        state["run"] = False
        worker.join(timeout=JOIN_S)   # its `finally` trips the plant first
        ctl.close()
        rx.close()
        print("writer for {} is down".format(m6.VID), flush=True)
        print("auto-resets: {}".format(resets[0]), flush=True)


if __name__ == "__main__":
    main()
