"""m6.py - the ONLY process that writes to ONE vehicle's safety PLC.

Runs on Windows, on 64-bit Python, against the S7-PLCSIM Advanced
instance its --vehicle names ("PLC_2" for f1). Every 20 ms it writes the
field-device picture the safety program needs and reads back the one
output that matters.

ONE WRITER PER VEHICLE, WHICH IS THE SINGLE-WRITER RULE AND NOT AN
EXCEPTION TO IT
  The rule is one writer per PLC, and since M6.1 each vehicle has its
  own. --vehicle is what makes this process a particular truck's
  writer: it stamps env VEHICLE, and status_contract turns that into the
  two UDP ports, the panel title and the PLCSIM instance name. A fleet
  of N trucks is N of these processes, each on its own port pair, each
  writing its own PLC; the ids on offer are whatever the VEHICLES table
  holds (f1..f4 since M6.5), and m6.sh prints one command line per
  vehicle on `start`.

THE PANEL AND THE LOOP ARE TWO THREADS, ON PURPOSE
  Tk stops pumping events while a window is dragged or resized. If the PLC
  cycle lived in the Tk event loop, grabbing the title bar would freeze the
  sole writer with Motor still energised. So the cycle runs in its own
  thread and the panel only reads a snapshot of it.

WHY THE SCANNER INPUTS AND THE ENCODERS ARE WRITTEN EVERY CYCLE
  Motor is the AND of the ESTOP1 enables. They watch the protective
  fields and the encoder cross-check, so unless this loop holds those
  healthy the drive enable can never energise, no matter what the e-stop
  button does. In Step 1 they were a precondition and not the subject;
  from Step 2 they ARE the subject and come from the plant. Since
  2026-08-12 the owner's program carries ESTOP1 instances for the right
  and left scanners too, so this loop writes all six field inputs:
  PF_OSSD, WF_Clear, PF_OSSD_right, WF_Clear_right, PF_OSSD_left,
  WF_Clear_left.

THE FAIL DIRECTION
  Any exception or closing the window leaves through the same `finally`:
  E-Stop and all six scanner inputs are written False. The vehicle side
  then sees the link go quiet and fails safe on its own 0.28 s rule.

Usage (Windows, 64-bit Python, PLCSIM Advanced already in RUN):
  python m6\\windows\\m6.py --vehicle f1
With no PLCSIM license (any Python, no pythonnet):
  python m6\\windows\\m6.py --vehicle f1 --virtual
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk

# ---------------------------- THE VEHICLE --------------------------
# NOT required=True: pytest imports this module with its own argv, and
# a hard requirement here would kill collection. The flag sets the env;
# status_contract's import below is what refuses, loudly and by name,
# when neither the flag nor the env named a vehicle.
#
# THE IDS ARE A LITERAL AND THEY CANNOT BE ANYTHING ELSE. They are the
# VEHICLES table's keys, spelled a second time, because reading them from
# that table would mean importing it BEFORE env VEHICLE is set - which
# binds the module to no vehicle for the life of the process (see the
# ordering note below). tests/test_vehicles_table.py asserts this tuple
# against the table on every run, so the duplication is GUARDED rather
# than trusted: a vehicle added there fails the suite until it reaches
# here. It is a module constant and not an inline argument because
# tools/scripted_writer.py builds a parser of its own and must offer the
# same ids - it borrows this one rather than becoming a third spelling.
VEHICLE_IDS = ("f1", "f2", "f3", "f4")
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("--vehicle", choices=VEHICLE_IDS)
_parser.add_argument("--virtual", action="store_true")
_ARGS, _ = _parser.parse_known_args()
if _ARGS.vehicle:
    os.environ["VEHICLE"] = _ARGS.vehicle
# THE ORDER HERE IS LOAD-BEARING. status_contract binds its per-vehicle
# constants ONCE, at its first import, off env VEHICLE - so the env has
# to be set BEFORE the import below, and nothing above it may import
# that module. Set it after and this process is a writer for no vehicle
# at all: it holds the constants refusal instead of a pair of ports.
sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "ipc")))
from status_contract import PLC_PORT, SENSOR_PORT, VID  # noqa: E402

# ----------------------------- CONFIG -----------------------------
# ONE PLCSIM ADVANCED INSTANCE HAS EVER EXISTED AND IT IS f1's. PLC_2 is
# the owner's, running the real F-program. PLC_3 was RESERVED for f2 and
# is entirely unused - there is one license and it has not returned - and
# nothing at all was reserved for f3 or f4, which joined at M6.5. So f2,
# f3 and f4 are --virtual trucks, and the acceptance record has to say
# which truck proved what against real hardware: only ever f1.
#
# A VEHICLE WITH NO INSTANCE IS NOT A KeyError HERE. This dict indexed
# with [VID] and f3 in the table would kill the module at import - for
# every truck, including the --virtual ones that are this rig's normal
# case, and including pytest's collection. .get() leaves it None and
# connect_plc refuses by name, which is both later and narrower: the
# only run that can hit it is one that asked for real hardware.
PLC_INSTANCE = {"f1": "PLC_2", "f2": "PLC_3"}.get(VID)
VIRTUAL = _ARGS.virtual  # no PLCSIM: virtual_fplc.py plays the F-PLC
API_DLL_DIR = r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0"
UDP_TARGET = None      # None -> ask `wsl.exe hostname -I`. A string overrides.
UDP_PORT = PLC_PORT    # Windows -> WSL, this vehicle's status stream
CYCLE_S = 0.02         # 20 ms
ACK_PULSE_S = 0.30
STATUS_EVERY = 10      # refresh the panel's status text every Nth cycle
# SENSOR_PORT - WSL -> Windows, the back scanner's verdict - is the
# other half of the pair imported above. Neither port is a literal here:
# both are this vehicle's, and status_contract's VEHICLES table is the
# one place either of them is chosen.
#
# Four missed sends at field_eval's 10 Hz. Budget to PF_OSSD False:
# SENSOR_STALE_S 0.40 + CYCLE_S 0.02 = < 0.42 s, and the Step 1 chain
# (< 0.45 s from Motor dropping) runs AFTER this one, not beside it.
SENSOR_STALE_S = 0.40
ENC_OFFSET_MM_S = 400   # the `oa` fault, 8x the F-program's 50 mm/s limit
# WHAT A DEAD LINK WRITES TO THE ENCODERS, AND WHY NOT 0/0.
# 0/0 reads as "stopped and healthy" - the most dangerous lie available,
# because the vehicle may be moving and nothing is watching. 0/3000
# disagrees by 3000 against a 50 mm/s cross-check AND exceeds the
# 2800 mm/s ceiling, so a dead link is a demanded stop by two independent
# routes inside the F-program.
ENC_STALE_A = 0
ENC_STALE_B = 3000
# One wire key per PLC tag, in write order. The bare pf/wf pair is the
# back scanner, keeping the wire format Step 2 shipped; right and left
# joined 2026-08-12 when the owner configured their F-DI channels.
SENSOR_TAGS = (
    ("pf", "PF_OSSD"), ("wf", "WF_Clear"),
    ("pf_right", "PF_OSSD_right"), ("wf_right", "WF_Clear_right"),
    ("pf_left", "PF_OSSD_left"), ("wf_left", "WF_Clear_left"),
)

# ------------------------------ PANEL -----------------------------
BG = "#9e9e9e"          # the grey the owner asked for
FG = "#141414"
GUI_REFRESH_MS = 100
# (lit, unlit) per button. Lit means the state is HELD, not that the mouse
# is down: the panel has to be readable from two metres away and say what
# the PLC is being told right now.
LAMPS = {
    "red":   ("#e53935", "#9c6b6b"),
    "green": ("#2e7d32", "#6d8f6f"),
    "blue":  ("#1565c0", "#6b7f9c"),
    "amber": ("#ef6c00", "#a8895f"),
}
ENC_LAMP = {"ok": "green", "fa": "amber", "oa": "amber"}
ENC_TEXT = (("ok", "OK"), ("fa", "FREEZE A"), ("oa", "OFFSET A"))
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


def status_payload(estop_healthy, motor, case, v_limit, ts):
    """The wire format plc_link.py parses. Five keys, no more."""
    return json.dumps({
        "estop_healthy": bool(estop_healthy),
        "motor": bool(motor),
        "case": int(case),
        "v_limit": int(v_limit),
        "ts": float(ts),
    }).encode()


def decode_case(b0, b1):
    """CASE_B0/CASE_B1 -> monitoring case.

    B0 is bit 0 and B1 is bit 1, so 01 is case 1, 10 is case 2, 11 is
    case 3. Pattern 00 is deliberately invalid in the F-program
    (m5_ver2/CLAUDE.md section 3.2) and decodes to 0, which field_eval
    maps to case 3 - the largest field. That is the fail-safe direction
    and must not be "corrected" to 1.
    """
    return (1 if b0 else 0) + (2 if b1 else 0)


def parse_sensor(data):
    """One 5101 datagram from sensor_link.py, or None if untrusted.

    The booleans must BE booleans: a truthy non-bool written straight to
    PF_OSSD would enable the plant off an invalid packet. The encoder
    values must be ints, and not bools, since isinstance(True, int) is
    True in Python and a JSON `true` would otherwise be written as 1 mm/s.
    """
    try:
        msg = json.loads(data.decode())
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(msg, dict):
        return None
    for key, _tag in SENSOR_TAGS:
        if not isinstance(msg.get(key), bool):
            return None
    for key in ("enc_a", "enc_b"):
        v = msg.get(key)
        if not isinstance(v, int) or isinstance(v, bool):
            return None
    return msg


def apply_encoder_fault(a, b, mode, last_a):
    """The field fault, injected where a real one would be.

    THIS IS THE ONLY PLACE IN THE PROJECT THAT LIES. The vehicle sends what
    the shaft did; a broken encoder corrupts the reading on its way to the
    card, and the PLCSIM API is the card's wiring. Putting the modes here
    also keeps every operator command on one panel.

    The three names are m5-plc-debug/encoder.py's, so the owner's muscle
    memory carries over:

      ok  pass both channels through as measured
      fa  channel A FROZEN at its last value - trips once the vehicle moves
      oa  channel A OFFSET by +400 mm/s - trips the cross-check at once

    The F-program faults on |ENC_A - ENC_B| > 50, so +400 is eight times
    the limit and cannot be mistaken for noise.
    """
    if mode == "fa":
        return (last_a, b)
    if mode == "oa":
        return (a + ENC_OFFSET_MM_S, b)
    return (a, b)


def connect_plc():
    """CreateInterface, with the -4 case reported rather than worked around."""
    if VIRTUAL:
        from virtual_fplc import VirtualFPLC
        print("VIRTUAL F-PLC (model) - PLCSIM Advanced is not in this loop")
        return VirtualFPLC()
    if PLC_INSTANCE is None:
        raise SystemExit(
            "no PLCSIM Advanced instance is reserved for {}: PLC_2 is f1's "
            "and it is the only one that has ever run. Start this writer "
            "with --virtual.".format(VID))
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


def control_loop(plc, target, tx, rx, state, live):
    """The 20 ms cycle. The only toucher of `plc`, on one thread.

    `state` is written by the panel and read here; `live` is the other way
    round. Both hold plain scalars, so a torn read is impossible and no
    lock is needed -- and no lock means the panel can never stall a write.
    """
    fields = {key: False for key, _tag in SENSOR_TAGS}
    enc_a, enc_b = ENC_STALE_A, ENC_STALE_B
    last_a = 0
    last_sensor_rx = float("-inf")
    cycle = 0
    try:
        while state["run"]:
            now = time.monotonic()

            # Drain 5101, keeping the newest trusted datagram.
            for _ in range(64):
                try:
                    msg = parse_sensor(rx.recv(512))
                except BlockingIOError:
                    break
                except OSError:
                    break
                if msg is not None:
                    for key, _tag in SENSOR_TAGS:
                        fields[key] = msg[key]
                    enc_a, enc_b = apply_encoder_fault(
                        msg["enc_a"], msg["enc_b"],
                        state["enc_mode"], last_a)
                    last_a = enc_a
                    last_sensor_rx = now

            # A DEAD LINK IS A VIOLATED FIELD. Holding the last value would
            # leave the plant enabled with nothing watching the scanner -
            # the hole Step 1's review found in cmd_gate, where a consumer
            # trusted a topic because its producer was designed never to
            # fall silent. Silence still has to be caught here.
            if now - last_sensor_rx >= SENSOR_STALE_S:
                fields = {key: False for key, _tag in SENSOR_TAGS}
                enc_a, enc_b = ENC_STALE_A, ENC_STALE_B

            # STEP 1 WROTE THESE TRUE UNCONDITIONALLY, BECAUSE THEY WERE A
            # PRECONDITION AND NOT THE SUBJECT. HERE THEY ARE THE SUBJECT.
            for key, tag in SENSOR_TAGS:
                plc.WriteBool(tag, fields[key])
            # And these were Step 1's placeholder for exactly this.
            plc.WriteInt16("ENC_A", enc_a)
            plc.WriteInt16("ENC_B", enc_b)
            plc.WriteBool("E-Stop", state["estop"])
            plc.WriteBool("Acknowledge", now < state["ack_until"])

            motor = plc.ReadBool("Motor")
            estop_healthy = plc.ReadBool("E-Stop")
            case = decode_case(plc.ReadBool("CASE_B0"), plc.ReadBool("CASE_B1"))
            # V_Limit (%MW100) is computed in the standard OB1, not in
            # the safety program. Step 1 read neither it nor the case
            # bits; Step 2 took the case bits, and this is the other
            # half. It is the only value on the 5100 wire the F-program
            # does not itself act on - the vehicle has to obey it.
            v_limit = plc.ReadInt16("V_Limit")
            tx.sendto(
                status_payload(estop_healthy, motor, case, v_limit, now),
                (target, UDP_PORT))

            live["motor"] = bool(motor)
            cycle += 1
            if cycle % STATUS_EVERY == 0:
                pf3, wf3 = ("/".join(
                    "T" if fields[p + s] else "F"
                    for s in ("", "_right", "_left")) for p in ("pf", "wf"))
                live["line"] = (
                    "E-Stop={:<5}  Motor={:<5}  ack={}\n"
                    "PF b/r/l={}  WF b/r/l={}\n"
                    "case={}  V_Limit={:<5}  enc={}/{} {}".format(
                        str(estop_healthy), str(motor),
                        str(now < state["ack_until"]), pf3, wf3,
                        case, v_limit, enc_a, enc_b, state["enc_mode"]))
            time.sleep(CYCLE_S)
    except Exception as exc:
        state["error"] = "control loop stopped: {}".format(exc)
        _say(state["error"])
    finally:
        # Whatever brought us here, the plant goes safe before we let go.
        state["run"] = False
        _say("shutting down: writing the trip values")
        for tag in ("E-Stop",) + tuple(tag for _key, tag in SENSOR_TAGS):
            try:
                plc.WriteBool(tag, False)
            except Exception as exc:
                _say("could not trip {}: {}".format(tag, exc))
        tx.close()


def _latch(button, lamp, held):
    """Draw a button as held down, or as released."""
    lit, unlit = LAMPS[lamp]
    button.configure(bg=lit if held else unlit,
                     relief=tk.SUNKEN if held else tk.RAISED)


def _button(parent, text, lamp, command, font, width):
    """A latching-looking button. takefocus=0 so Space cannot fire it."""
    lit, unlit = LAMPS[lamp]
    return tk.Button(
        parent, text=text, command=command, font=font, width=width,
        fg="white", bg=unlit, activebackground=lit, activeforeground="white",
        relief=tk.RAISED, bd=5, highlightthickness=0, takefocus=0,
        cursor="hand2")


def run_panel(state, live):
    """Build the panel and pump it. Returns when the window closes."""
    big = ("Segoe UI", 13, "bold")
    root = tk.Tk()
    root.title("Forklift {} PLC Control Panel".format(VID)
               + (" - VIRTUAL F-PLC (model)" if VIRTUAL else ""))
    root.configure(bg=BG)
    root.resizable(False, False)

    tk.Label(root, text="Forklift {} PLC Control Panel".format(VID),
             bg=BG, fg=FG,
             font=("Segoe UI", 19, "bold")).pack(pady=(16, 4))

    lamp = tk.Label(root, text="MOTOR STOPPED", fg="white", bg="#4a4a4a",
                    font=("Segoe UI", 12, "bold"), width=28, pady=6)
    lamp.pack(pady=(4, 14))

    def push():
        state["estop"] = False

    def release():
        state["estop"] = True

    def reset():
        # The F-program wants a rising edge; the loop makes the falling one
        # 0.30 s later, so the operator cannot hold Acknowledge on.
        state["ack_until"] = time.monotonic() + ACK_PULSE_S

    btn_push = _button(root, "PUSH EMERGENCY STOP", "red", push, big, 26)
    btn_push.pack(pady=5)
    btn_release = _button(
        root, "RELEASE EMERGENCY STOP", "green", release, big, 26)
    btn_release.pack(pady=5)
    btn_reset = _button(root, "RESET", "blue", reset, big, 26)
    btn_reset.pack(pady=(5, 14))

    enc_row = tk.Frame(root, bg=BG)
    enc_row.pack(pady=(0, 12))
    tk.Label(enc_row, text="ENCODER", bg=BG, fg=FG,
             font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
    enc_buttons = {}
    for mode, text in ENC_TEXT:
        b = _button(enc_row, text, ENC_LAMP[mode],
                    lambda m=mode: state.update(enc_mode=m),
                    ("Segoe UI", 9, "bold"), 10)
        b.configure(bd=3)
        b.pack(side=tk.LEFT, padx=3)
        enc_buttons[mode] = b

    status = tk.Label(root, text="waiting for the first cycle",
                      font=("Consolas", 10), bg="#2b2b2b", fg="#e0e0e0",
                      justify=tk.LEFT, anchor="w", width=48, height=3,
                      padx=10, pady=6)
    status.pack(padx=16, pady=(0, 16), fill=tk.X)

    def refresh():
        # The buttons show the STATE, not the click: red is down whenever
        # the PLC is being told the chain is open, however it got there.
        _latch(btn_push, "red", not state["estop"])
        _latch(btn_release, "green", state["estop"])
        _latch(btn_reset, "blue", time.monotonic() < state["ack_until"])
        for mode, b in enc_buttons.items():
            _latch(b, ENC_LAMP[mode], state["enc_mode"] == mode)
        motor = live["motor"]
        lamp.configure(text="MOTOR ENABLED" if motor else "MOTOR STOPPED",
                       bg="#2e7d32" if motor else "#4a4a4a")
        if state["run"]:
            status.configure(text=live["line"], fg="#e0e0e0", bg="#2b2b2b")
        else:
            # The loop is gone and the plant is already tripped. Say so and
            # keep the window up rather than vanishing with the reason.
            status.configure(text=state["error"] or "LINK STOPPED",
                             fg="white", bg="#8e1c1c")
        root.after(GUI_REFRESH_MS, refresh)

    def close():
        state["run"] = False
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    refresh()
    root.mainloop()


def main():
    state = {"estop": True, "ack_until": 0.0, "run": True,
             "enc_mode": "ok", "error": ""}
    live = {"line": "waiting for the first cycle", "motor": False}

    target = resolve_udp_target()
    print("streaming PLC state to {}:{}".format(target, UDP_PORT))
    plc = connect_plc()
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("0.0.0.0", SENSOR_PORT))
    rx.setblocking(False)
    print("listening for the back scanner on 0.0.0.0:{}".format(SENSOR_PORT))

    worker = threading.Thread(
        target=control_loop, args=(plc, target, tx, rx, state, live),
        daemon=True)
    worker.start()
    run_panel(state, live)
    # The window is gone; wait for the cycle to run its trip writes. 2 s is
    # a hundred cycles - if it has not finished by then it never will.
    state["run"] = False
    worker.join(timeout=2.0)


if __name__ == "__main__":
    main()
