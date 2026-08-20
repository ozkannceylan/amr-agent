"""cmd_gate.py - stage 1 of the stop: the command is zeroed.

Forwards the mux's winner (`/vehicle/cmd_vel`) to the vehicle's
engineering-unit command topics while the safety program says Motor, and
publishes continuous zeros when it does not.

CONTINUOUS ZEROS, NOT ONE ZERO
  A single zero leaves a simulated vehicle coasting: forklift_io.py
  republishes steer and traction on receipt only, so one zero is one
  message and then silence. The gate therefore keeps publishing zeros at
  10 Hz for as long as the inhibit lasts.

THE /vehicle/cmd_vel FIELD CONTRACT (unchanged from /hmi/cmd_vel), NOT STANDARD Twist
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
  python3 m5_ver2/step6/ipc/cmd_gate.py
"""

import time

import rclpy
import yaml
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Float64, String

from status_contract import (
    CONFIG_PATH, STATUS_STALE_S, STATUS_TOPIC, V_LIMIT_CREEP_MM_S,
    VEHICLE_CMD_TOPIC, is_stale, parse_status, speed_limit_mm_s)

# ----------------------------- CONFIG -----------------------------
ZERO_HZ = 10.0
# STATUS_STALE_S - the timeout on /plc/status - is imported and not
# declared here: the screen and the vehicle have to stop trusting a
# silent status at the same instant, so it has one home. Its derivation,
# including why it is 2.5 of THIS file's ticks, is at that home.
# ------------------------------------------------------------------


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

    is_stale is the shared contract's, not a second staleness rule
    written here, and it already reads a last_rx_s of None - never
    received - as stale.
    """
    if not motor_ok:
        return False
    return not is_stale(last_rx_s, now_s, stale_s)


def motor_from_status(json_text):
    """Read `motor` out of a /plc/status payload. Anything unreadable is
    inhibited: a gate that cannot understand the PLC does not pass."""
    msg = parse_status(json_text.encode())
    if msg is None:
        return False
    return bool(msg["motor"])


def load_config(path=CONFIG_PATH):
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
        # Until the PLC says otherwise, the permission is the creep
        # ceiling. A gate that has not heard cannot grant full speed.
        self.v_limit = V_LIMIT_CREEP_MM_S
        self.last_status_rx = None
        self.was_live = False
        self.cmd = (0.0, 0.0)

        self.create_subscription(String, STATUS_TOPIC, self.cb_status, 10)
        self.create_subscription(Twist, VEHICLE_CMD_TOPIC, self.cb_cmd, 10)
        self.create_timer(1.0 / ZERO_HZ, self.tick)
        self.get_logger().info(
            "speed limit {:.2f} m/s, steer stop +-{:.2f} rad".format(
                self.speed_max, self.steer_max))

    def cb_status(self, msg):
        self.last_status_rx = time.monotonic()
        self.motor_ok = motor_from_status(msg.data)
        parsed = parse_status(msg.data.encode())
        self.v_limit = speed_limit_mm_s(
            parsed.get("v_limit") if parsed else None)

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
        # THE EFFECTIVE LIMIT IS THE SMALLER OF TWO PERMISSIONS.
        # speed_max is the VEHICLE's (config.yaml, 1.50 m/s); v_limit
        # is the PLC's right now. With the warning field clear the two
        # are equal at 1500 mm/s, so nothing changes in open space;
        # with it occupied the PLC's 300 mm/s wins and the truck creeps
        # instead of being stopped by the speed monitor for exceeding a
        # ceiling nothing was obeying.
        limit = min(self.speed_max, self.v_limit / 1000.0)
        traction, steer = gated_command(
            self.cmd[0], self.cmd[1], self.enabled(),
            limit, self.steer_max)
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
