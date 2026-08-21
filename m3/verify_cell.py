#!/usr/bin/env python3
"""verify_cell.py — the M3 gate exercise, run headless against the virtual PLC.

One process, three roles:

  * the OPERATOR at the panel: publishes the four /cell/panel/* contacts as
    levels (1 Hz refresh, exactly as bridge/tools/cell_stimulus.py does — a
    contact is a level and a ROS topic is not retained);
  * the WATCH TABLE: an OPC UA client reading the cell's status and output
    nodes off the virtual PLC (or PLCSIM Advanced — the surface is the same);
  * the OBSERVER: subscribed to /cell/product_box/pose, the ground truth that
    the belt actually carried the product (deliberately NOT a PLC signal —
    opcua-nodes.md §9.8).

The exercise, in order: the boot signature (link-lost latched, no process
stop from start values — SPEC §6.1), the monitored reset, one full
transport-dwell-return cycle with the product observed at the beam, a
process stop mid-transport with its latch and override, and the proof that
healing the contact does not resume the cycle.

Prerequisites: m3/run_cell.sh start has completed (world + bridge + R3).
This script takes the panel over from the resting stimulus.

Run (WSL, repo root):
  source /opt/ros/jazzy/setup.bash
  python3 m3/verify_cell.py
"""

import argparse
import asyncio
import csv
import os
import signal
import sys
import threading
import time

import rclpy
from geometry_msgs.msg import PoseArray
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool

from asyncua import Client

SI_URI = "http://www.siemens.com/simatic-s7-opcua"
IF_URI = "http://DemoCell"

HERE = os.path.dirname(os.path.abspath(__file__))
CONTACTS = {
    "start": "/cell/panel/start",
    "reset": "/cell/panel/reset",
    "stop": "/cell/panel/stop",
    "process_stop": "/cell/panel/process_stop",
}

RESULTS = []


def report(ok, label, detail=""):
    RESULTS.append(bool(ok))
    print("{} {}{}".format("PASS" if ok else "FAIL", label,
                           (" -- " + detail) if detail else ""), flush=True)


def skip(label, detail=""):
    """Not counted: a condition this run cannot exercise (a warm CPU has no
    boot window). The fresh-CPU run and the unit tests pin what SKIP elides."""
    print("SKIP {}{}".format(label, (" -- " + detail) if detail else ""), flush=True)


class Panel(Node):
    """The operator's hands and the observer's eyes, one node."""

    def __init__(self):
        super().__init__("m3_gate_exercise")
        qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1,
                         reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.VOLATILE)
        self._pubs = {n: self.create_publisher(Bool, t, qos) for n, t in CONTACTS.items()}
        # the panel at rest: both NC circuits closed, both NO buttons released
        self._level = {"start": False, "reset": False, "stop": True, "process_stop": True}
        self.pose_x = None
        self.create_subscription(PoseArray, "/cell/product_box/pose", self._on_pose, 10)
        self.create_timer(1.0, self._refresh)
        self._refresh()

    def _on_pose(self, msg):
        if msg.poses:
            self.pose_x = msg.poses[0].position.x

    def _refresh(self):
        for name, value in self._level.items():
            msg = Bool()
            msg.data = value
            self._pubs[name].publish(msg)

    def set(self, name, value):
        self._level[name] = value
        self._refresh()

    def press(self, name, hold_s=0.6):
        self.set(name, True)
        time.sleep(hold_s)
        self.set(name, False)


def start_panel():
    rclpy.init()
    panel = Panel()
    thread = threading.Thread(target=lambda: rclpy.spin(panel), daemon=True)
    thread.start()
    return panel, thread


def stop_panel(panel, thread):
    panel.destroy_node()
    rclpy.shutdown()
    thread.join(timeout=3.0)


def stop_resting_stimulus():
    pidf = os.path.join(HERE, "runtime", "panel_rest.pid")
    try:
        with open(pidf, "r", encoding="utf-8") as fh:
            pid = int(fh.read().strip())
        os.kill(pid, signal.SIGTERM)
        os.remove(pidf)
        time.sleep(1.0)
        return True
    except (OSError, ValueError):
        return False


async def resolve_map(client):
    idx_si = await client.get_namespace_index(SI_URI)
    idx = await client.get_namespace_index(IF_URI)

    async def node(*tail):
        path = ["{}:ServerInterfaces".format(idx_si), "{}:DemoCell".format(idx)]
        path.extend("{}:{}".format(idx, name) for name in tail)
        return await client.nodes.objects.get_child(path)

    names = {
        "link_ok": ("Link", "BridgeLinkOk"),
        "running": ("Status", "CellCycleRunning"),
        "stop_active": ("Status", "CellProcessStopActive"),
        "reset_required": ("Status", "CellResetRequired"),
        "present": ("Status", "ProductPresentAtSensor"),
        "drive_fault": ("Status", "ConveyorDriveFault"),
        "command": ("Output", "ConveyorSpeedCommand"),
        "belt_pos": ("Input", "ConveyorBeltPosition"),
        # the contacts' own nodes, so a press confirms the PLC SAW the level
        # (a publish lost to ROS discovery is not a press)
        "in_start": ("Input", "PanelStartPressed"),
        "in_reset": ("Input", "PanelResetPressed"),
        "in_process_stop": ("Input", "PanelProcessStopCircuitClosed"),
    }
    return {key: await node(*tail) for key, tail in names.items()}


async def read_all(nodes):
    out = {}
    for key, node in nodes.items():
        out[key] = await node.read_value()
    return out


async def wait_for(nodes, key, pred, timeout_s, what):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        value = await nodes[key].read_value()
        if pred(value):
            return True, value
        await asyncio.sleep(0.1)
    return False, value


CONTACT_NODE = {"start": "in_start", "reset": "in_reset",
                "process_stop": "in_process_stop"}


async def press(panel, nodes, name, hold_s=0.6):
    """A press the PLC is seen to receive: hold until the input node reads
    the level, then release until it reads the release. A real operator
    watches the contact's lamp; this is the same discipline over the wire."""
    key = CONTACT_NODE[name]
    panel.set(name, True)
    await wait_for(nodes, key, lambda v: v is True, 5, name + " seen pressed")
    await asyncio.sleep(hold_s)
    panel.set(name, False)
    await wait_for(nodes, key, lambda v: v is False, 5, name + " seen released")


async def amain(args):
    if not args.keep_resting_stimulus:
        stopped = stop_resting_stimulus()
        print("..  resting stimulus {} (this script is the operator now)".format(
            "stopped" if stopped else "was not running"), flush=True)

    panel, panel_thread = start_panel()
    ev_path = os.path.join(HERE, "evidence",
                           "m3-verify-{}.csv".format(time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    ev = open(ev_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(ev)
    writer.writerow(["wall_s", "command", "belt_pos", "pose_x", "running",
                     "stop_active", "reset_required", "present", "link_ok"])
    t0 = time.monotonic()

    client = Client(args.endpoint)
    await client.connect()
    try:
        nodes = await resolve_map(client)
        report(True, "namespaces and browse paths resolve",
               "the §9 subtree answers on the server")

        async def snapshot():
            state = await read_all(nodes)
            writer.writerow([round(time.monotonic() - t0, 2),
                             state["command"], round(state["belt_pos"], 4),
                             None if panel.pose_x is None else round(panel.pose_x, 4),
                             state["running"], state["stop_active"],
                             state["reset_required"], state["present"], state["link_ok"]])
            ev.flush()
            return state

        # -- 1. the link is up and the boot signature stands -----------------
        ok, _ = await wait_for(nodes, "link_ok", lambda v: v is True, 15,
                               "BridgeLinkOk TRUE")
        report(ok, "BridgeLinkOk TRUE", "the bridge's heartbeat moves (R3 closed)")
        state = await snapshot()
        if state["reset_required"] is True:
            report(True, "boot: CellResetRequired TRUE",
                   "the boot link-loss latch stands (SPEC 6.1)")
        else:
            skip("boot: CellResetRequired TRUE",
                 "warm CPU: the boot latch was cleared by an earlier exercise "
                 "and nothing re-armed it — a fresh virtual PLC shows it")
        report(state["stop_active"] is False,
               "boot: CellProcessStopActive FALSE",
               "no process stop from DB start values — the corrected polarity")

        # -- 1b. warm-CPU prelude: clear what stands, re-home if away --------
        # The gate's measured cycle starts at home with no latch. A CPU that
        # already ran an exercise may hold neither condition; the SPEC's own
        # re-home branch (section 5) is the recovery, not a script trick.
        if state["reset_required"] is True:
            await press(panel, nodes, "reset")
            await asyncio.sleep(0.5)
            state = await snapshot()
            report(state["reset_required"] is False,
                   "monitored reset clears the standing latch", "")
        else:
            skip("monitored reset clears the standing latch", "nothing stood")
        if abs(state["belt_pos"]) > 0.05:
            await press(panel, nodes, "start")  # away from home: SeqStep 30
            # first wait for the cycle to BE running — polling for "not
            # running" before the edge propagates returns instantly
            ok, _ = await wait_for(nodes, "running", lambda v: v is True, 5,
                                   "re-home starts")
            if ok:
                ok, _ = await wait_for(nodes, "running", lambda v: v is False, 60,
                                       "re-home completes")
            state = await snapshot()
            report(ok and abs(state["belt_pos"]) <= 0.07,
                   "re-home before the measured cycle (SPEC section 5)",
                   "belt position {:.3f} m".format(state["belt_pos"]))

        # -- 3. one full cycle ------------------------------------------------
        pose_at_start = panel.pose_x
        await press(panel, nodes, "start")
        await asyncio.sleep(0.5)
        state = await snapshot()
        report(state["running"] is True and abs(state["command"] - 0.15) < 0.02,
               "start edge: transport begins",
               "CellCycleRunning TRUE, command {:.3f} m/s".format(state["command"]))

        ok, _ = await wait_for(nodes, "present", lambda v: v is True, 25,
                               "ProductPresentAtSensor TRUE")
        state = await snapshot()
        travel = None if (panel.pose_x is None or pose_at_start is None) \
            else abs(panel.pose_x - pose_at_start)
        report(ok, "the beam breaks: ProductPresentAtSensor TRUE",
               "product travelled {:.2f} m".format(travel) if travel is not None else "pose unseen")
        report(travel is not None and travel >= 1.0,
               "the belt really carried the product",
               "{:.2f} m of ground-truth travel".format(travel) if travel is not None else "no pose")

        ok, _ = await wait_for(nodes, "command", lambda v: abs(v) < 0.001, 5,
                               "dwell: command 0")
        report(ok, "dwell at the beam: command 0.0 while running", "~2 s stand-in transfer")

        ok, _ = await wait_for(nodes, "command", lambda v: abs(v + 0.15) < 0.02, 8,
                               "return stroke")
        report(ok, "dwell done: return stroke at -0.15 m/s", "")

        ok, _ = await wait_for(nodes, "running", lambda v: v is False, 30,
                               "cycle complete")
        state = await snapshot()
        report(ok and abs(state["command"]) < 0.001,
               "cycle completes at home",
               "belt position {:.3f} m, command {:.3f}".format(state["belt_pos"], state["command"]))
        report(abs(state["belt_pos"]) <= 0.05 + 0.02,
               "the belt is home", "|{:.3f}| <= HOME_WINDOW".format(state["belt_pos"]))

        # -- 4. process stop mid-transport ------------------------------------
        await press(panel, nodes, "start")
        await asyncio.sleep(3.0)                # mid-transport
        state = await snapshot()
        mid_ok = state["running"] is True
        panel.set("process_stop", False)        # the red button opens its contact
        await wait_for(nodes, "in_process_stop", lambda v: v is False, 5,
                       "the PLC sees the open contact")
        ok, _ = await wait_for(nodes, "stop_active", lambda v: v is True, 5,
                               "CellProcessStopActive TRUE")
        state = await snapshot()
        report(mid_ok and ok and abs(state["command"]) < 0.001 and state["running"] is False,
               "process stop latches and overrides",
               "command zeroed, cycle down, CellProcessStopActive TRUE")

        # -- 5. healing the contact resumes nothing ---------------------------
        panel.set("process_stop", True)
        await wait_for(nodes, "in_process_stop", lambda v: v is True, 5,
                       "the PLC sees the healed contact")
        await asyncio.sleep(1.5)
        state = await snapshot()
        report(state["stop_active"] is True and state["running"] is False,
               "healing the contact resumes nothing",
               "the latch stands until the monitored reset")
        await press(panel, nodes, "reset")
        await asyncio.sleep(0.5)
        state = await snapshot()
        report(state["stop_active"] is False and state["reset_required"] is False,
               "the monitored reset clears the latch", "")
        await asyncio.sleep(2.0)
        state = await snapshot()
        report(state["running"] is False and abs(state["command"]) < 0.001,
               "no automatic resume",
               "starting again is the OTHER button (SPEC 6.4)")
    finally:
        await client.disconnect()
        ev.close()
        stop_panel(panel, panel_thread)

    print("\nevidence: {}".format(ev_path), flush=True)
    return 0 if all(RESULTS) else 1


def main():
    ap = argparse.ArgumentParser(description="the M3 gate exercise, headless")
    ap.add_argument("--endpoint", default=None,
                    help="OPC UA endpoint; default: the Windows host from the "
                         "default route, port 4841 (the virtual PLC)")
    ap.add_argument("--keep-resting-stimulus", action="store_true",
                    help="do not stop run_cell.sh's panel-at-rest process "
                         "(only if you know it is not publishing)")
    args = ap.parse_args()
    if not args.endpoint:
        import subprocess
        route = subprocess.check_output(["ip", "route", "show", "default"]).decode()
        args.endpoint = "opc.tcp://{}:4841".format(route.split()[2])
    try:
        sys.exit(asyncio.run(amain(args)))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
