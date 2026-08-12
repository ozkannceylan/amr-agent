"""sensor_link.py - all three scanners' verdicts, to the PLC writer.

Subscribes /forklift/safety/fields and sends the back, right and left
devices' (pf, wf) to Windows over UDP 5101, where step5.py writes PF_OSSD,
WF_Clear and their _right/_left counterparts.

ALL THREE SENSORS SINCE 2026-08-12. Through Step 5's build the F-PLC had
one sensor input configured and this file enforced back-only; on that date
the owner added PF_OSSD_right/left and WF_Clear_right/left to the F-DI and
their ESTOP1 networks to the safety program, so right and left stop being
HMI-only here. ALL OR NOTHING: a report missing ANY device sends no
datagram, because pairing fresh back verdicts with invented side verdicts
would need a second staleness rule on step5.py's side of the wire.

SENDING NOTHING IS THE SAFE FAILURE. An unparseable report, a missing
device entry or a non-boolean verdict all send no datagram, and step5.py's
own timeout then writes all six inputs False. This file never invents a
verdict.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step5/ipc/sensor_link.py
"""

import json
import socket
import subprocess
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

import status_contract

# ----------------------------- CONFIG -----------------------------
UDP_TARGET = None       # None -> the WSL default gateway, i.e. the Windows host
UDP_PORT = 5101
# The encoder report's OWN timeout. encoder_link publishes at 20 Hz, so
# this is five missed reports.
#
# WITHOUT IT this node forwards the last encoder pair for ever if
# encoder_link dies: field_eval keeps publishing, so the datagram keeps
# leaving and arrives at step5.py looking FRESH. At rest that pair is
# 0/0, which step5.py and the design both name the most dangerous lie
# available - stopped and healthy, while the vehicle may be moving.
#
# It is the same defect Task 4 found in cmd_gate, one layer up: a
# consumer trusting a topic because its producer was designed never to
# fall silent. Silence still has to be caught by the consumer.
ENCODERS_STALE_S = 0.25
# ------------------------------------------------------------------


def resolve_udp_target(configured=UDP_TARGET):
    """The Windows host, discovered rather than hard-coded.

    From WSL, Windows is the default route's gateway. It is 172.19.176.1
    today and it moves when the WSL network is rebuilt, so discovering it
    each run is the difference between a script that works and one that
    breaks silently later.
    """
    if configured:
        return configured
    out = subprocess.check_output(
        ["ip", "route", "show", "default"], text=True, timeout=10)
    parts = out.split()
    if "via" not in parts:
        raise RuntimeError("no default route: cannot find the Windows host")
    return parts[parts.index("via") + 1]


def parse_encoders(encoders_json):
    """(a, b) in mm/s from the encoder report, or None if untrusted.

    A channel reported absent - the publisher stopped - makes the whole
    pair untrusted rather than defaulting to zero. Zero would say
    "stopped" about a vehicle that may be moving.
    """
    try:
        msg = json.loads(encoders_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(msg, dict):
        return None
    out = []
    for key in ("a", "b"):
        v = msg.get(key)
        if not isinstance(v, int) or isinstance(v, bool):
            return None
        out.append(v)
    return tuple(out)


def payload(fields_json, encoders_json):
    """The 5101 wire format, or None if any part cannot be trusted.

    ONE DATAGRAM CARRIES EVERYTHING so step5.py has one staleness rule
    rather than several, and there is no state where one device's verdict
    is fresh and another's is not. Back keeps the bare "pf"/"wf" keys the
    wire always had; right and left carry the same suffix their PLC tags
    do.
    """
    try:
        report = json.loads(fields_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(report, dict):
        return None
    out = {}
    for name, suffix in (("back", ""), ("right", "_right"),
                         ("left", "_left")):
        dev = report.get(name)
        if not isinstance(dev, dict):
            return None
        if not isinstance(dev.get("pf"), bool):
            return None
        if not isinstance(dev.get("wf"), bool):
            return None
        out["pf" + suffix] = dev["pf"]
        out["wf" + suffix] = dev["wf"]
    enc = parse_encoders(encoders_json)
    if enc is None:
        return None
    out.update(enc_a=enc[0], enc_b=enc[1], ts=time.monotonic())
    return json.dumps(out).encode()


class SensorLink(Node):

    def __init__(self):
        super().__init__("sensor_link")
        self.target = resolve_udp_target()
        self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.encoders = None
        self.last_encoders_rx = None
        self.create_subscription(
            String, status_contract.ENCODERS_TOPIC,
            self.cb_encoders, 10)
        self.create_subscription(
            String, status_contract.FIELDS_TOPIC, self.cb_fields, 10)
        self.get_logger().info(
            "back+right+left scanners + encoders -> {}:{}".format(
                self.target, UDP_PORT))

    def cb_encoders(self, msg):
        self.encoders = msg.data
        self.last_encoders_rx = time.monotonic()

    def cb_fields(self, msg):
        """The field report is the clock: one datagram per evaluation.

        Sending on the encoder topic instead would send at its rate and
        pair a fresh speed with a stale verdict.
        """
        if self.encoders is None:
            return
        # A stale encoder report withholds the WHOLE datagram rather
        # than pairing a fresh field verdict with a stale speed.
        # step5.py's own timeout then writes the trip values for both.
        if status_contract.is_stale(
                self.last_encoders_rx, time.monotonic(),
                ENCODERS_STALE_S):
            return
        data = payload(msg.data, self.encoders)
        if data is not None:
            self.tx.sendto(data, (self.target, UDP_PORT))


def main():
    rclpy.init()
    node = SensorLink()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.tx.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
