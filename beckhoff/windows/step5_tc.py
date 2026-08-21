"""step5_tc.py - the ONLY process that writes to the TwinCAT PLC.

The Beckhoff port of m5_ver2/step5/windows/step5.py: same panel, same two
threads, same 20 ms cycle, same UDP wire toward WSL - only the PLC API
swaps, PLCSIM Advanced Runtime API -> ADS by symbol name over pyads,
against the local TwinCAT runtime (user mode runtime, port 851).

THE WIRE IS BYTE-IDENTICAL. 5100 out carries {estop_healthy, motor, case,
v_limit, ts}; 5101 in carries the six field verdicts and the encoders.
plc_link.py and sensor_link.py cannot tell the vendors apart, which is the
point: the WSL side runs unchanged.

THE NAME MAPPING LIVES HERE AND NOWHERE ELSE. ST identifiers cannot carry
a hyphen, so Siemens `E-Stop` is `GVL_IO.EStop` at the ADS seam; the wire
keys keep the m5_ver2 spelling. One table, TAGS below.

THE FAIL DIRECTION IS UNCHANGED. Any exception or closing the window
leaves through the same `finally`: EStop and all six scanner inputs are
written False. A dead 5101 link writes fields False and encoders 0/3000 -
a demanded stop by two independent routes (cross-check AND ceiling).

Usage (Windows, TwinCAT runtime in Run mode, `pip install pyads`):
  python beckhoff\\windows\\step5_tc.py
"""

import json
import socket
import subprocess
import threading
import time
import tkinter as tk

# ----------------------------- CONFIG -----------------------------
AMS_NET_ID = "127.0.0.1.1.1"   # the local runtime's AMS NetId
ADS_PORT = 851                 # TwinCAT 3 PLC runtime 1 (pyads.PORT_TC3PLC1)
UDP_TARGET = None      # None -> ask `wsl.exe hostname -I`. A string overrides.
UDP_PORT = 5100
CYCLE_S = 0.02         # 20 ms, the m5_ver2 writer cycle
ACK_PULSE_S = 0.30
STATUS_EVERY = 10      # refresh the panel's status text every Nth cycle
SENSOR_PORT = 5101     # WSL -> Windows, the scanners' verdicts
SENSOR_STALE_S = 0.40  # silence here writes the field inputs False
ENC_OFFSET_MM_S = 400  # the `oa` fault, 8x the cross-check limit
# A dead link's encoder picture: 0/3000 disagrees by 3000 against the
# 50 mm/s cross-check AND exceeds the 2800 mm/s ceiling. 0/0 would read
# as "stopped and healthy" - the most dangerous lie available.
ENC_STALE_A = 0
ENC_STALE_B = 3000
# One wire key per ADS symbol, in write order. The wire keys are the
# m5_ver2 spellings; only the right column knows this is TwinCAT.
SENSOR_TAGS = (
    ("pf", "GVL_IO.PF_OSSD"), ("wf", "GVL_IO.WF_Clear"),
    ("pf_right", "GVL_IO.PF_OSSD_right"),
    ("wf_right", "GVL_IO.WF_Clear_right"),
    ("pf_left", "GVL_IO.PF_OSSD_left"),
    ("wf_left", "GVL_IO.WF_Clear_left"),
)
ESTOP_TAG = "GVL_IO.EStop"          # Siemens `E-Stop`; ST cannot hyphenate
ACK_TAG = "GVL_IO.Acknowledge"
ENC_A_TAG, ENC_B_TAG = "GVL_IO.ENC_A", "GVL_IO.ENC_B"
READ_TAGS = ("GVL_IO.Motor", "GVL_IO.EStop", "GVL_IO.CASE_B0",
             "GVL_IO.CASE_B1", "GVL_IO.V_Limit")

# ------------------------------ PANEL -----------------------------
BG = "#9e9e9e"
FG = "#141414"
GUI_REFRESH_MS = 100
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
    """First whitespace-separated token: the WSL eth0 address."""
    parts = text.split()
    if not parts:
        raise RuntimeError("`wsl.exe hostname -I` returned no address")
    return parts[0]


def resolve_udp_target(configured=UDP_TARGET):
    """The WSL guest IP, discovered rather than hard-coded (NAT, not
    mirrored: 127.0.0.1 does not reach the guest, and the address moves
    on every WSL restart)."""
    if configured:
        return configured
    out = subprocess.check_output(
        ["wsl.exe", "hostname", "-I"], text=True, timeout=10)
    return _first_token(out)


def _say(msg):
    """Print, but never let a dead stdout stop a PLC write."""
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
    """CASE_B0/CASE_B1 -> monitoring case; 00 decodes to 0, which the
    vehicle's field_eval maps to case 3, the largest field. Fail-safe
    direction, do not 'correct' to 1."""
    return (1 if b0 else 0) + (2 if b1 else 0)


def parse_sensor(data):
    """One 5101 datagram from sensor_link.py, or None if untrusted.

    Booleans must BE booleans - a truthy non-bool written to PF_OSSD would
    enable the plant off an invalid packet - and the encoder values must
    be ints and not bools (isinstance(True, int) is True in Python)."""
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
    """The field fault, injected where a real one would be - the only
    place in the project that lies. Same three modes as m5_ver2:
      ok  pass through   fa  channel A frozen   oa  channel A +400 mm/s"""
    if mode == "fa":
        return (last_a, b)
    if mode == "oa":
        return (a + ENC_OFFSET_MM_S, b)
    return (a, b)


def connect_plc():
    """Open ADS to the local runtime, with the two usual failures named."""
    import pyads
    plc = pyads.Connection(AMS_NET_ID, ADS_PORT)
    try:
        plc.open()
        plc.read_by_name("GVL_IO.Motor")   # proves runtime AND symbols
    except Exception as exc:
        raise SystemExit(
            "Cannot reach the TwinCAT PLC at {} port {}: {}\n"
            "- 'target port not found' / timeout: the runtime is not in "
            "Run mode. Activate the configuration in XAE and start Run.\n"
            "- 'symbol not found': the PLC project with GVL_IO is not the "
            "one running. Re-activate from beckhoff/RUNBOOK.md part 2."
            .format(AMS_NET_ID, ADS_PORT, exc))
    return plc


def control_loop(plc, target, tx, rx, state, live):
    """The 20 ms cycle. The only toucher of `plc`, on one thread.

    `state` is written by the panel and read here; `live` the other way.
    Plain scalars both ways, so no lock - and no lock means the panel can
    never stall a write. Two ADS calls per cycle (one batched write, one
    batched read) instead of thirteen round trips."""
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
                except (BlockingIOError, OSError):
                    break
                if msg is not None:
                    for key, _tag in SENSOR_TAGS:
                        fields[key] = msg[key]
                    enc_a, enc_b = apply_encoder_fault(
                        msg["enc_a"], msg["enc_b"],
                        state["enc_mode"], last_a)
                    last_a = enc_a
                    last_sensor_rx = now

            # A dead link is a violated field - silence is caught HERE,
            # not trusted because the producer was designed to be loud.
            if now - last_sensor_rx >= SENSOR_STALE_S:
                fields = {key: False for key, _tag in SENSOR_TAGS}
                enc_a, enc_b = ENC_STALE_A, ENC_STALE_B

            writes = {tag: fields[key] for key, tag in SENSOR_TAGS}
            writes[ENC_A_TAG] = enc_a
            writes[ENC_B_TAG] = enc_b
            writes[ESTOP_TAG] = state["estop"]
            writes[ACK_TAG] = now < state["ack_until"]
            plc.write_list_by_name(writes)

            r = plc.read_list_by_name(list(READ_TAGS))
            motor = bool(r["GVL_IO.Motor"])
            estop_healthy = bool(r["GVL_IO.EStop"])
            case = decode_case(r["GVL_IO.CASE_B0"], r["GVL_IO.CASE_B1"])
            v_limit = int(r["GVL_IO.V_Limit"])
            tx.sendto(
                status_payload(estop_healthy, motor, case, v_limit, now),
                (target, UDP_PORT))

            live["motor"] = motor
            cycle += 1
            if cycle % STATUS_EVERY == 0:
                pf3, wf3 = ("/".join(
                    "T" if fields[p + s] else "F"
                    for s in ("", "_right", "_left")) for p in ("pf", "wf"))
                live["line"] = (
                    "EStop={:<5}  Motor={:<5}  ack={}\n"
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
        trip = {tag: False for _key, tag in SENSOR_TAGS}
        trip[ESTOP_TAG] = False
        try:
            plc.write_list_by_name(trip)
        except Exception:
            for tag, value in trip.items():
                try:
                    plc.write_by_name(tag, value)
                except Exception as exc:
                    _say("could not trip {}: {}".format(tag, exc))
        tx.close()


def _latch(button, lamp, held):
    lit, unlit = LAMPS[lamp]
    button.configure(bg=lit if held else unlit,
                     relief=tk.SUNKEN if held else tk.RAISED)


def _button(parent, text, lamp, command, font, width):
    lit, unlit = LAMPS[lamp]
    return tk.Button(
        parent, text=text, command=command, font=font, width=width,
        fg="white", bg=unlit, activebackground=lit, activeforeground="white",
        relief=tk.RAISED, bd=5, highlightthickness=0, takefocus=0,
        cursor="hand2")


def run_panel(state, live):
    """Build the panel and pump it. Returns when the window closes.
    Identical to the m5_ver2 panel but for the title: the operator's
    muscle memory is part of what the port preserves."""
    big = ("Segoe UI", 13, "bold")
    root = tk.Tk()
    root.title("Forklift 1 PLC Control Panel - TwinCAT")
    root.configure(bg=BG)
    root.resizable(False, False)

    tk.Label(root, text="Forklift 1 PLC Control Panel", bg=BG, fg=FG,
             font=("Segoe UI", 19, "bold")).pack(pady=(16, 4))

    lamp = tk.Label(root, text="MOTOR STOPPED", fg="white", bg="#4a4a4a",
                    font=("Segoe UI", 12, "bold"), width=28, pady=6)
    lamp.pack(pady=(4, 14))

    def push():
        state["estop"] = False

    def release():
        state["estop"] = True

    def reset():
        # A rising edge; the loop makes the falling one 0.30 s later, so
        # the operator cannot hold Acknowledge on.
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
        # The buttons show the STATE, not the click.
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
    print("listening for the scanners on 0.0.0.0:{}".format(SENSOR_PORT))

    worker = threading.Thread(
        target=control_loop, args=(plc, target, tx, rx, state, live),
        daemon=True)
    worker.start()
    run_panel(state, live)
    state["run"] = False
    worker.join(timeout=2.0)
    plc.close()


if __name__ == "__main__":
    main()
