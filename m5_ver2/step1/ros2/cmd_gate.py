"""cmd_gate.py - stage 1 of the stop: the command is zeroed.

Forwards the HMI joystick to the vehicle's engineering-unit command topics
while the safety program says Motor, and publishes continuous zeros when it
does not.

CONTINUOUS ZEROS, NOT ONE ZERO
  A single zero leaves a simulated vehicle coasting: forklift_io.py
  republishes steer and traction on receipt only, so one zero is one
  message and then silence. The gate therefore keeps publishing zeros at
  10 Hz for as long as the inhibit lasts.

THE /hmi/cmd_vel FIELD CONTRACT, WHICH IS NOT STANDARD Twist
  linear.x   traction speed  [m/s]   +-1.50  (limits.traction_speed_max_mps)
  angular.z  STEER ANGLE     [rad]   +-1.31  (model.steer_limit_rad)

  angular.z carries an ANGLE, not a yaw rate. The bicycle relation the
  nav2-era converter uses, delta = atan(L*w/v), is undefined at v = 0, and
  a forklift that cannot be steered while stopped would make an e-stop
  test ambiguous: the operator could not tell a safety stop from a dead
  joystick. Step 1 needs steering visibly alive while traction is
  inhibited, so the angle is commanded directly and no geometry is
  computed anywhere in this file.

THREE WAYS TO BE INHIBITED, AND SILENCE IS ONE OF THEM (spec 7.4)
  motor false, /plc/status STALE, or /plc/status never received.
  plc_link failing safe as a NODE is not the same as failing safe as a
  PROCESS: on a dead UDP link it keeps publishing FAILSAFE at 20 Hz and
  the chain works, but if the process dies the topic simply stops, and
  sto_contactor below releases only on an OBSERVED False. Nothing
  downstream reads silence as a demand, so the gate has to.

THIS IS NOT THE ONLY INTERLOCK, AND NOT THE LAST ONE
  sto_contactor.py removes torque at the plant's own inputs and cannot be
  bypassed by any ROS publisher. This gate is the controlled stop above it.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step1/ros2/cmd_gate.py
"""

import os
import time

import rclpy
import yaml
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Float64, String

import plc_link

# ----------------------------- CONFIG -----------------------------
ZERO_HZ = 10.0
# The gate's OWN timeout on /plc/status. Five missed publishes at
# plc_link's 20 Hz, so ordinary scheduling jitter cannot trip it, and
# deliberately NOT a multiple of 1/ZERO_HZ: 2.5 ticks, clear of the tick
# boundary that cost Task 3 two rounds on STALE_S.
STATUS_STALE_S = 0.25
HMI_TOPIC = "/hmi/cmd_vel"
# ------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "agv", "forklift", "config.yaml"))


def clamp(value, limit):
    """Symmetric clamp to +-limit. NaN becomes 0.0.

    THE NaN GUARD IS NOT DEFENSIVE PADDING. Every comparison against NaN
    is False, so min(limit, nan) and max(-limit, limit) both keep their
    first operand and the bare clamp returns +limit: a NaN linear.x would
    command MAXIMUM FORWARD TRACTION and a NaN angular.z the mechanical
    stop. That inverts this file's own rule one function below - anything
    unreadable is inhibited - by making unreadable input on the COMMAND
    side accelerate while unreadable input on the STATUS side stops.
    `value != value` is true only for NaN and needs no import. The
    infinities are left alone: they have a sign and clamp correctly.
    """
    if value != value:
        return 0.0
    return max(-limit, min(limit, value))


def gated_command(linear_x, angular_z, motor_ok, speed_max, steer_max):
    """The whole gate decision: (traction [m/s], steer [rad])."""
    if not motor_ok:
        return (0.0, 0.0)
    return (clamp(linear_x, speed_max), clamp(angular_z, steer_max))


def gate_is_live(motor_ok, last_rx_s, now_s, stale_s=STATUS_STALE_S):
    """The whole enable decision: enabled AND recently told so.

    is_stale is plc_link's, not a second staleness rule written here, and
    it already reads a last_rx_s of None - never received - as stale.
    """
    if not motor_ok:
        return False
    return not plc_link.is_stale(last_rx_s, now_s, stale_s)


def motor_from_status(json_text):
    """Read `motor` out of a /plc/status payload. Anything unreadable is
    inhibited: a gate that cannot understand the PLC does not pass."""
    msg = plc_link.parse_status(json_text.encode())
    if msg is None:
        return False
    return bool(msg["motor"])


def load_config(path=CONFIG_YAML):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class CmdGate(Node):

    def __init__(self):
        super().__init__("cmd_gate")
        cfg = load_config()
        topics = cfg["topics"]
        self.speed_max = float(cfg["limits"]["traction_speed_max_mps"])
        self.steer_max = float(cfg["model"]["steer_limit_rad"])

        self.pub_traction = self.create_publisher(
            Float64, topics["cmd_traction_speed"], 10)
        self.pub_steer = self.create_publisher(
            Float64, topics["cmd_steer_angle"], 10)

        # A gate that has not heard from the PLC does not pass a command.
        self.motor_ok = False
        self.last_status_rx = None
        self.was_live = False
        self.cmd = (0.0, 0.0)

        self.create_subscription(String, "/plc/status", self.cb_status, 10)
        self.create_subscription(Twist, HMI_TOPIC, self.cb_cmd, 10)
        self.create_timer(1.0 / ZERO_HZ, self.tick)
        self.get_logger().info(
            "speed limit {:.2f} m/s, steer stop +-{:.2f} rad".format(
                self.speed_max, self.steer_max))

    def cb_status(self, msg):
        self.last_status_rx = time.monotonic()
        self.motor_ok = motor_from_status(msg.data)

    def enabled(self):
        """The one place the clock is read. BOTH publish paths consult it,
        so a status that stopped arriving inhibits cb_cmd's fast path too
        and not merely the next tick."""
        return gate_is_live(
            self.motor_ok, self.last_status_rx, time.monotonic())

    def cb_cmd(self, msg):
        self.cmd = (msg.linear.x, msg.angular.z)
        self.publish()

    def tick(self):
        """The 10 Hz floor, and the only thing that notices a /plc/status
        that stopped: no message arrives to announce silence, so the
        inhibit has to be found by looking at the clock."""
        live = self.enabled()
        if live != self.was_live:
            self.was_live = live
            self.get_logger().info(
                "drive enable {}".format("ON" if live else "OFF"))
        if not live:
            self.publish()

    def publish(self):
        traction, steer = gated_command(
            self.cmd[0], self.cmd[1], self.enabled(),
            self.speed_max, self.steer_max)
        self.pub_traction.publish(Float64(data=traction))
        self.pub_steer.publish(Float64(data=steer))


def main():
    rclpy.init()
    node = CmdGate()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
