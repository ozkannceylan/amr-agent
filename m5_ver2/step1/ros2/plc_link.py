"""plc_link.py - the vehicle side of the PLC link.

Binds UDP :5100, republishes what step1.py sends as two ROS topics:

    /plc/status                            std_msgs/String  (the JSON)
    topics.safety_torque_off_demand        std_msgs/Bool    (= not motor)

WHY IT NEVER GOES QUIET
  sto_contactor.py latches on an OBSERVED True and releases on an OBSERVED
  False, so a demand link that stops speaking leaves the contactor closed.
  That is correct in its own layer - it refuses to put a safety reaction on
  network silence - but it means the failure has to be SAID rather than
  implied. So when the link goes stale this node keeps publishing at 20 Hz,
  with motor False and the demand True. Silence here would be a moving
  vehicle.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step1/ros2/plc_link.py
"""

import json
import os
import socket
import time

import rclpy
import yaml
from rclpy.node import Node
from std_msgs.msg import Bool, String

# ----------------------------- CONFIG -----------------------------
BIND_ADDR = "0.0.0.0"
UDP_PORT = 5100
STALE_S = 0.5
PUBLISH_HZ = 20.0
STATUS_TOPIC = "/plc/status"
# ------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "agv", "forklift", "config.yaml"))

_REQUIRED_KEYS = {"estop_healthy", "motor", "ts"}

#: What the vehicle is told when the link is stale or has never spoken.
FAILSAFE = {"estop_healthy": False, "motor": False, "ts": 0.0}


def parse_status(data):
    """Decode one datagram, or None if it is not a packet we trust.

    A packet missing a key is rejected rather than defaulted: defaulting
    `motor` would be inventing an enable.
    """
    try:
        msg = json.loads(data.decode())
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(msg, dict) or not _REQUIRED_KEYS.issubset(msg):
        return None
    return msg


def is_stale(last_rx_s, now_s, stale_s=STALE_S):
    """True when nothing has arrived within the window, or ever."""
    if last_rx_s is None:
        return True
    return (now_s - last_rx_s) >= stale_s


def load_topics(path=CONFIG_YAML):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["topics"]


class PlcLink(Node):

    def __init__(self):
        super().__init__("plc_link")
        topics = load_topics()
        self.pub_status = self.create_publisher(String, STATUS_TOPIC, 10)
        self.pub_demand = self.create_publisher(
            Bool, topics["safety_torque_off_demand"], 10)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((BIND_ADDR, UDP_PORT))
        self.sock.setblocking(False)

        self.last_rx = None
        self.last_msg = dict(FAILSAFE)
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)
        self.get_logger().info(
            "bound {}:{}, publishing {} and {}".format(
                BIND_ADDR, UDP_PORT, STATUS_TOPIC,
                topics["safety_torque_off_demand"]))

    def drain(self):
        """Take the newest datagram and discard any backlog."""
        newest = None
        while True:
            try:
                data = self.sock.recv(512)
            except BlockingIOError:
                break
            parsed = parse_status(data)
            if parsed is not None:
                newest = parsed
        return newest

    def tick(self):
        now = time.monotonic()
        fresh = self.drain()
        if fresh is not None:
            self.last_msg, self.last_rx = fresh, now
        if is_stale(self.last_rx, now):
            self.last_msg = dict(FAILSAFE)

        self.pub_status.publish(String(data=json.dumps(self.last_msg)))
        self.pub_demand.publish(Bool(data=not self.last_msg["motor"]))


def main():
    rclpy.init()
    node = PlcLink()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
