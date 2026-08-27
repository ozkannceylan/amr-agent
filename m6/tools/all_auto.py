"""all_auto.py - put every cab in AUTOMATIC, the runbook's one-liner.

WHAT IT REPLACES: four clicks. Each vehicle's HMI window has an Auto
button that publishes "auto" latched on /fN/hmi/mode; a fleet runbook
that says "click Auto on four panels" is a runbook with four chances to
forget one, so this publishes the same message on the same topic at the
same QoS for every vehicle in the table.

WHY IT PUBLISHES FOR A FULL 18 SECONDS instead of firing and exiting:
TRANSIENT_LOCAL durability only serves late joiners while the PUBLISHER
IS ALIVE, and under the loopback-unicast DDS profile
(tools/fastdds_loopback.xml) a fresh participant can take 10-20 s to
walk the ~40-node discovery mesh. Measured 2026-08-25: an 1.6 s
publisher reached three agents and missed the fourth, twice; nine
seconds reached all four; eighteen is that with the margin doubled.

Usage (WSL, ROS sourced, stack up):
  python3 m6/tools/all_auto.py
"""
import os
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "ipc")))
import status_contract                              # noqa: E402

HOLD_S = 18.0
PERIOD_S = 0.2


def main():
    rclpy.init()
    node = Node("m6_all_auto")
    qos = QoSProfile(depth=1,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     reliability=ReliabilityPolicy.RELIABLE)
    vids = sorted(status_contract.VEHICLES)
    pubs = [node.create_publisher(String, "/{}/hmi/mode".format(v), qos)
            for v in vids]
    msg = String()
    msg.data = "auto"
    for _ in range(int(HOLD_S / PERIOD_S)):
        for pub in pubs:
            pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=PERIOD_S)
    print("auto latched on {} cabs ({}) - held {:.0f} s".format(
        len(vids), ", ".join(vids), HOLD_S))
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
