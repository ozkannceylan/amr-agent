"""step1_tc.py - TwinCAT step 1: the e-stop chain and the wire, nothing else.

The Beckhoff port of m5_ver2/step1: the six scanner inputs and both
encoders are PINNED healthy every cycle (True / True, 0 / 0) because they
are a precondition for Motor and not the subject. Steps 2+ take them over
from the scanners, exactly like m5_ver2 did.

Single-writer rule carries over: this is the ONLY process that writes the
TwinCAT PLC. ADS by symbol name, local user-mode runtime, port 851.
The 5100 wire toward WSL is byte-identical to m5_ver2 - plc_link.py
cannot tell the vendors apart.

Usage (Windows, TwinCAT runtime in Run mode):
  python beckhoff\\windows\\step1_tc.py
"""

import json
import socket
import subprocess
import threading
import time
import tkinter as tk

# ----------------------------- CONFIG -----------------------------
AMS_NET_ID = "127.0.0.1.1.1"   # the local runtime's AMS NetId
ADS_PORT = 851                 # TwinCAT 3 PLC runtime 1
UDP_PORT = 5100                # Windows -> WSL, the status wire
CYCLE_S = 0.02                 # 20 ms, the m5_ver2 writer cycle
ACK_PULSE_S = 0.30
STATUS_EVERY = 10

# Pinned-healthy field picture, written every cycle. NOT the subject of
# step 1 - step 2 (back scanner) and step 3 (encoders) replace these.
PINNED = {
    "GVL_IO.PF_OSSD": True, "GVL_IO.WF_Clear": True,
    "GVL_IO.PF_OSSD_right": True, "GVL_IO.WF_Clear_right": True,
    "GVL_IO.PF_OSSD_left": True, "GVL_IO.WF_Clear_left": True,
    "GVL_IO.ENC_A": 0, "GVL_IO.ENC_B": 0,
}
ESTOP_TAG = "GVL_IO.EStop"          # Siemens `E-Stop`; ST cannot hyphenate
ACK_TAG = "GVL_IO.Acknowledge"
READ_TAGS = ("GVL_IO.Motor", "GVL_IO.EStop", "GVL_IO.CASE_B0",
             "GVL_IO.CASE_B1", "GVL_IO.V_Limit")
# ------------------------------------------------------------------


def resolve_udp_target():
    """The WSL guest IP, discovered rather than hard-coded (NAT: the
    address moves on every WSL restart)."""
    out = subprocess.check_output(
        ["wsl.exe", "hostname", "-I"], text=True, timeout=10)
    parts = out.split()
    if not parts:
        raise RuntimeError("`wsl.exe hostname -I` returned no address")
    return parts[0]


def status_payload(estop_healthy, motor, case, v_limit, ts):
    """The wire format plc_link.py parses."""
    return json.dumps({
        "estop_healthy": bool(estop_healthy),
        "motor": bool(motor),
        "case": int(case),
        "v_limit": int(v_limit),
        "ts": float(ts),
    }).encode()


def decode_case(b0, b1):
    """CASE_B0/CASE_B1 -> monitoring case; 00 decodes to 0, which the
    vehicle maps to case 3, the largest field. Fail direction, keep."""
    return (1 if b0 else 0) + (2 if b1 else 0)


def connect_plc():
    import pyads
    plc = pyads.Connection(AMS_NET_ID, ADS_PORT)
    try:
        plc.open()
        plc.read_by_name("GVL_IO.Motor")   # proves runtime AND symbols
    except Exception as exc:
        raise SystemExit(
            "Cannot reach the TwinCAT PLC at {} port {}: {}\n"
            "- timeout / port not found: runtime not in Run mode - "
            "Activate Configuration in XAE.\n"
            "- symbol not found: the running project is not the one with "
            "GVL_IO (beckhoff/RUNBOOK.md part 2)."
            .format(AMS_NET_ID, ADS_PORT, exc))
    return plc


def control_loop(plc, target, tx, state, live):
    """The 20 ms cycle. The only toucher of `plc`, on one thread."""
    cycle = 0
    try:
        while state["run"]:
            now = time.monotonic()
            writes = dict(PINNED)
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
                live["line"] = (
                    "EStop={:<5}  Motor={:<5}  ack={}\n"
                    "case={}  V_Limit={:<5}  fields PINNED healthy\n"
                    "streaming to {}:{}".format(
                        str(estop_healthy), str(motor),
                        str(now < state["ack_until"]),
                        case, v_limit, target, UDP_PORT))
            time.sleep(CYCLE_S)
    except Exception as exc:
        state["error"] = "control loop stopped: {}".format(exc)
    finally:
        # Whatever brought us here, the plant goes safe before we let go.
        state["run"] = False
        trip = {tag: False for tag in PINNED if not tag.endswith(("ENC_A", "ENC_B"))}
        trip[ESTOP_TAG] = False
        trip["GVL_IO.ENC_A"] = 0
        trip["GVL_IO.ENC_B"] = 0
        try:
            plc.write_list_by_name(trip)
        except Exception:
            pass
        tx.close()


BG = "#9e9e9e"
FG = "#141414"


def run_panel(state, live):
    """Same three buttons as the m5_ver2 step 1 panel: the operator's
    muscle memory is part of what the port preserves."""
    big = ("Segoe UI", 13, "bold")
    root = tk.Tk()
    root.title("Forklift 1 PLC Control Panel - TwinCAT step1")
    root.configure(bg=BG)
    root.resizable(False, False)

    tk.Label(root, text="Forklift 1 PLC Control Panel", bg=BG, fg=FG,
             font=("Segoe UI", 19, "bold")).pack(pady=(16, 4))
    lamp = tk.Label(root, text="MOTOR STOPPED", fg="white", bg="#4a4a4a",
                    font=("Segoe UI", 12, "bold"), width=28, pady=6)
    lamp.pack(pady=(4, 14))

    def button(text, lit, unlit, command):
        return tk.Button(root, text=text, command=command, font=big,
                         width=26, fg="white", bg=unlit,
                         activebackground=lit, activeforeground="white",
                         relief=tk.RAISED, bd=5, highlightthickness=0,
                         takefocus=0, cursor="hand2")

    btn_push = button("PUSH EMERGENCY STOP", "#e53935", "#9c6b6b",
                      lambda: state.update(estop=False))
    btn_push.pack(pady=5)
    btn_release = button("RELEASE EMERGENCY STOP", "#2e7d32", "#6d8f6f",
                         lambda: state.update(estop=True))
    btn_release.pack(pady=5)
    btn_reset = button("RESET", "#1565c0", "#6b7f9c",
                       lambda: state.update(
                           ack_until=time.monotonic() + ACK_PULSE_S))
    btn_reset.pack(pady=(5, 14))

    status = tk.Label(root, text="waiting for the first cycle",
                      font=("Consolas", 10), bg="#2b2b2b", fg="#e0e0e0",
                      justify=tk.LEFT, anchor="w", width=48, height=3,
                      padx=10, pady=6)
    status.pack(padx=16, pady=(0, 16), fill=tk.X)

    def refresh():
        motor = live["motor"]
        lamp.configure(text="MOTOR ENABLED" if motor else "MOTOR STOPPED",
                       bg="#2e7d32" if motor else "#4a4a4a")
        if state["run"]:
            status.configure(text=live["line"])
        else:
            status.configure(text=state["error"] or "LINK STOPPED",
                             fg="white", bg="#8e1c1c")
        root.after(100, refresh)

    def close():
        state["run"] = False
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    refresh()
    root.mainloop()


def main():
    state = {"estop": True, "ack_until": 0.0, "run": True, "error": ""}
    live = {"line": "waiting for the first cycle", "motor": False}

    target = resolve_udp_target()
    print("streaming PLC state to {}:{}".format(target, UDP_PORT))
    print("fields PINNED healthy (step 1) - scanners arrive at step 2")
    plc = connect_plc()
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    worker = threading.Thread(
        target=control_loop, args=(plc, target, tx, state, live),
        daemon=True)
    worker.start()
    run_panel(state, live)
    state["run"] = False
    worker.join(timeout=2.0)
    plc.close()


if __name__ == "__main__":
    main()
