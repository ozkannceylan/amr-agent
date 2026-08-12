"""sensor_link.py - the Back scanner's verdict, to the PLC writer.

Subscribes /forklift/safety/fields and sends the BACK device's (pf, wf) to
Windows over UDP 5101, where step2.py writes PF_OSSD and WF_Clear.

ONLY THE BACK SENSOR. The F-PLC has one sensor input configured, so left and
right are HMI-only in this step. That is the owner's constraint, not a
simplification, and this file is where it is enforced.

SENDING NOTHING IS THE SAFE FAILURE. An unparseable report, a missing back
entry or a non-boolean verdict all send no datagram, and step2.py's own
timeout then writes both inputs False. This file never invents a verdict.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step2/ros2/sensor_link.py
"""

import json
import socket
import subprocess
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# ----------------------------- CONFIG -----------------------------
UDP_TARGET = None       # None -> the WSL default gateway, i.e. the Windows host
UDP_PORT = 5101
FIELDS_TOPIC = "/forklift/safety/fields"
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


def back_payload(fields_json):
    """The 5101 wire format, or None if the report cannot be trusted."""
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
    return json.dumps({"pf": back["pf"], "wf": back["wf"],
                       "ts": time.monotonic()}).encode()


class SensorLink(Node):

    def __init__(self):
        super().__init__("sensor_link")
        self.target = resolve_udp_target()
        self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.create_subscription(String, FIELDS_TOPIC, self.cb_fields, 10)
        self.get_logger().info(
            "back scanner -> {}:{}".format(self.target, UDP_PORT))

    def cb_fields(self, msg):
        payload = back_payload(msg.data)
        if payload is not None:
            self.tx.sendto(payload, (self.target, UDP_PORT))


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
