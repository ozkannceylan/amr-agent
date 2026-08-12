"""cmd_mux.py - one seam: which human-side source drives the vehicle.

BELOW the autonomy, ABOVE the gate. The mux picks between the joystick
and the autopilot; cmd_gate then applies Motor, staleness and V_Limit
to whatever won. Safety never depends on this file choosing well - a
wrong pick is still a gated, clamped, zeroable command.

TELEOP IS THE FLOOR. No mode yet, an unreadable mode word, any surprise:
the joystick wins. The one exception is a SELECTED autopilot that went
silent - forwarding the joystick then would hand a moving truck to
whoever happens to hold it, and forwarding the last auto command would
be a dead man's setpoint; zeros are the only honest output. Teleop mode
deliberately keeps Step 4's semantics exactly (no staleness rule): the
HMI publishes at 20 Hz for the life of the window, and the e-stop is
the brake (README_step4.md, run order note).

MODE IS LATCHED (TRANSIENT_LOCAL, depth 1), so a mux that starts after
the HMI still learns the current mode from the last publish.
"""
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String

from status_contract import (
    AUTO_CMD_TOPIC, HMI_CMD_TOPIC, MODE_AUTO, MODE_TOPIC, STATUS_STALE_S,
    VEHICLE_CMD_TOPIC, is_stale)

# ----------------------------- CONFIG -----------------------------
ZERO_HZ = 10.0   # republish floor while auto is selected and silent
# ------------------------------------------------------------------


def select(mode, hmi_cmd, auto_cmd, auto_rx_s, now_s):
    """The whole decision: (linear, angular) to forward."""
    if mode != MODE_AUTO:
        return hmi_cmd
    if is_stale(auto_rx_s, now_s, STATUS_STALE_S):
        return (0.0, 0.0)
    return auto_cmd


class CmdMux(Node):

    def __init__(self):
        super().__init__("cmd_mux")
        self.mode = None
        self.hmi = (0.0, 0.0)
        self.auto = (0.0, 0.0)
        self.auto_rx = None
        self.pub = self.create_publisher(Twist, VEHICLE_CMD_TOPIC, 10)
        latched = QoSProfile(
            depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(String, MODE_TOPIC, self.cb_mode, latched)
        self.create_subscription(Twist, HMI_CMD_TOPIC, self.cb_hmi, 10)
        self.create_subscription(Twist, AUTO_CMD_TOPIC, self.cb_auto, 10)
        self.create_timer(1.0 / ZERO_HZ, self.tick)

    def cb_mode(self, msg):
        self.mode = msg.data

    def cb_hmi(self, msg):
        self.hmi = (msg.linear.x, msg.angular.z)
        if self.mode != MODE_AUTO:
            self.publish()

    def cb_auto(self, msg):
        self.auto = (msg.linear.x, msg.angular.z)
        self.auto_rx = time.monotonic()
        if self.mode == MODE_AUTO:
            self.publish()

    def tick(self):
        """The floor: while auto is selected and silent, the zeros above
        must still FLOW - cmd_gate forwards on receipt, and a stopped
        stream would leave the plant holding its last setpoint."""
        if self.mode == MODE_AUTO:
            self.publish()

    def publish(self):
        linear, angular = select(
            self.mode, self.hmi, self.auto, self.auto_rx, time.monotonic())
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = CmdMux()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
