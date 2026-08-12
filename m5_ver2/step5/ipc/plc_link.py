"""plc_link.py - the vehicle side of the PLC link.

Binds UDP :5100, republishes what step5.py sends as two ROS topics:

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
  python3 m5_ver2/step5/ipc/plc_link.py
"""

import json
import os
import socket
import time

import rclpy
import yaml
from rclpy.node import Node
from std_msgs.msg import Bool, String

from status_contract import (
    FAILSAFE, STATUS_TOPIC, is_stale, parse_status)

# ----------------------------- CONFIG -----------------------------
BIND_ADDR = "0.0.0.0"
UDP_PORT = 5100
# THIS NODE'S OWN UDP TIMEOUT, and NOT status_contract.STATUS_STALE_S.
# That one is the ROS-side timeout consumers of /plc/status apply to a
# topic; this one is measured on the datagrams arriving here from
# step5.py, on a different clock with a different budget. They are not
# interchangeable and must not be merged. 0.28 s is deliberately off a
# multiple of the 0.05 s tick below: 5 ticks must not trip and 6 must,
# with margin at both ends rather than on a boundary - an exact multiple
# (0.25 or 0.30) puts microseconds of jitter in charge of which tick
# fires, which cost Task 3 two rounds.
STALE_S = 0.28
PUBLISH_HZ = 20.0
# ------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "agv", "forklift", "config.yaml"))


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
        """Take the newest datagram and discard any backlog.

        BOUNDED so that tick() always returns: a flood on :5100 would hold
        an unbounded loop resident and the node would fall silent while
        still looking alive. 64 is ~25 tick periods of the ~50 Hz sender,
        against the ~2.5 datagrams one tick legitimately brings.

        THE TRADE THE BOUND MAKES, which is new behaviour: above 64 in a
        tick the backlog survives the call, so `newest` can be an older
        packet stamped with this tick's `now` - stale state read as
        FRESH. Silence is the worse failure, so that is the right way to
        fail here, but the bound is not free and does not read as free.
        """
        newest = None
        for _ in range(64):
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
        # An exception out of tick() escapes rclpy.spin, and a dead node
        # leaves the contactor closed and the plant enabled.
        try:
            fresh = self.drain()
        except OSError as exc:
            self.get_logger().warn("recv failed: {}".format(exc))
            fresh = None
        if fresh is not None:
            self.last_msg, self.last_rx = fresh, now
        if is_stale(self.last_rx, now, STALE_S):
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
