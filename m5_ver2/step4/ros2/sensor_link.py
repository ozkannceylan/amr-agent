"""sensor_link.py - the Back scanner's verdict, to the PLC writer.

Subscribes /forklift/safety/fields and sends the BACK device's (pf, wf) to
Windows over UDP 5101, where step4.py writes PF_OSSD and WF_Clear.

ONLY THE BACK SENSOR. The F-PLC has one sensor input configured, so left and
right are HMI-only in this step. That is the owner's constraint, not a
simplification, and this file is where it is enforced.

SENDING NOTHING IS THE SAFE FAILURE. An unparseable report, a missing back
entry or a non-boolean verdict all send no datagram, and step4.py's own
timeout then writes both inputs False. This file never invents a verdict.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step4/ros2/sensor_link.py
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
# leaving and arrives at step4.py looking FRESH. At rest that pair is
# 0/0, which step4.py and the design both name the most dangerous lie
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
    """The 5101 wire format, or None if either half cannot be trusted.

    ONE DATAGRAM CARRIES BOTH so step4.py has one staleness rule rather
    than two, and there is no state where the field verdict is fresh and
    the encoders are not.
    """
    try:
        report = json.loads(fields_json)
    except (ValueError, TypeError):
        return None
    back = report.get("back") if isinstance(report, dict) else None
    if not isinstance(back, dict):
        return None
    if not isinstance(back.get("pf"), bool):
        return None
    if not isinstance(back.get("wf"), bool):
        return None
    enc = parse_encoders(encoders_json)
    if enc is None:
        return None
    return json.dumps({"pf": back["pf"], "wf": back["wf"],
                       "enc_a": enc[0], "enc_b": enc[1],
                       "ts": time.monotonic()}).encode()


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
            "back scanner + encoders -> {}:{}".format(self.target, UDP_PORT))

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
        # step4.py's own timeout then writes the trip values for both.
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
