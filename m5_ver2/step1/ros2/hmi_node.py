"""hmi_node.py - the operator's window: a joystick and an e-stop lamp.

THE LAMP AND THE ENABLE LINE ARE SEPARATE, AND THAT IS THE POINT
  The lamp reads the e-stop chain; the line under it reads the drive
  enable. After a release without an acknowledge they DISAGREE - lamp
  inactive, enable OFF - and that disagreement IS the ESTOP1 latch. Making
  it visible is a Step 1 goal, not a display quirk.

THE FIELD CONTRACT ON /hmi/cmd_vel, WHICH IS NOT STANDARD Twist
  linear.x   traction speed  [m/s]   +-1.50  (limits.traction_speed_max_mps)
  angular.z  STEER ANGLE     [rad]   +-1.31  (model.steer_limit_rad)

  See cmd_gate.py for why an angle and not a yaw rate.

Usage (after sourcing /opt/ros/jazzy/setup.bash; WSLg provides DISPLAY):
  python3 m5_ver2/step1/ros2/hmi_node.py
"""

import math
import os
import tkinter as tk

import rclpy
import yaml
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String

import plc_link

# ----------------------------- CONFIG -----------------------------
PUBLISH_HZ = 20.0
SPIN_MS = 20              # tkinter's after() period for pumping rclpy
KNOB_RADIUS_PX = 100.0
HMI_TOPIC = "/hmi/cmd_vel"
LAMP_RED = "#c62828"
LAMP_NEUTRAL = "#455a64"
# ------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "agv", "forklift", "config.yaml"))


def knob_to_twist(dx, dy, radius, speed_max, steer_max):
    """Knob offset in pixels -> (linear.x [m/s], angular.z [rad]).

    Canvas y grows downward, so dragging up is a negative dy and has to be
    negated to mean forward. Dragging right steers right, which is a
    NEGATIVE angular.z under REP-103 (positive z is counter-clockwise).
    """
    nx = max(-1.0, min(1.0, dx / radius))
    ny = max(-1.0, min(1.0, dy / radius))
    return (-ny * speed_max, -nx * steer_max)


def lamp_state(estop_healthy):
    """(colour, text) for the lamp. Healthy is not an alarm colour."""
    if estop_healthy:
        return (LAMP_NEUTRAL, "E-Stop Inactive")
    return (LAMP_RED, "E-Stop Active")


def enable_text(motor):
    return "Drive enable: {}".format("ON" if motor else "OFF")


def load_config(path=CONFIG_YAML):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class Hmi(Node):

    def __init__(self, root):
        super().__init__("hmi_node")
        cfg = load_config()
        self.speed_max = float(cfg["limits"]["traction_speed_max_mps"])
        self.steer_max = float(cfg["model"]["steer_limit_rad"])

        self.pub = self.create_publisher(Twist, HMI_TOPIC, 10)
        self.create_subscription(String, "/plc/status", self.cb_status, 10)
        self.knob = (0.0, 0.0)
        self.create_timer(1.0 / PUBLISH_HZ, self.publish)

        self.root = root
        root.title("Step 1 - forklift teleoperation")
        cx = cy = KNOB_RADIUS_PX + 20

        self.canvas = tk.Canvas(root, width=2 * cx, height=2 * cy,
                                bg="#eceff1", highlightthickness=0)
        self.canvas.pack(padx=10, pady=10)
        self.canvas.create_oval(cx - KNOB_RADIUS_PX, cy - KNOB_RADIUS_PX,
                                cx + KNOB_RADIUS_PX, cy + KNOB_RADIUS_PX,
                                outline="#90a4ae", width=2)
        self.dot = self.canvas.create_oval(cx - 14, cy - 14, cx + 14, cy + 14,
                                           fill="#37474f", outline="")
        self.centre = (cx, cy)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.lamp = tk.Label(
            root, text="E-Stop Inactive", fg="white", bg=LAMP_NEUTRAL,
            font=("TkDefaultFont", 16, "bold"), padx=16, pady=10)
        self.lamp.pack(fill="x", padx=10)
        self.enable = tk.Label(root, text=enable_text(False),
                               font=("TkDefaultFont", 11))
        self.enable.pack(pady=(6, 12))

    def on_drag(self, event):
        cx, cy = self.centre
        dx, dy = event.x - cx, event.y - cy
        dist = math.hypot(dx, dy)
        if dist > KNOB_RADIUS_PX:               # keep the dot on the ring
            dx, dy = dx * KNOB_RADIUS_PX / dist, dy * KNOB_RADIUS_PX / dist
        self.knob = (dx, dy)
        self.canvas.coords(self.dot, cx + dx - 14, cy + dy - 14,
                           cx + dx + 14, cy + dy + 14)

    def on_release(self, _event):
        """Release snaps to centre and the next publish is a zero."""
        cx, cy = self.centre
        self.knob = (0.0, 0.0)
        self.canvas.coords(self.dot, cx - 14, cy - 14, cx + 14, cy + 14)

    def cb_status(self, msg):
        """Anything unreadable is displayed as the SAFE state, and
        plc_link's parser decides what readable means.

        A bare json.loads read `[1,2]` - valid JSON, wrong shape - and
        raised AttributeError in the callback, which took the pump with
        it: window open, "Drive enable: ON", /hmi/cmd_vel dead. Measured,
        not argued. parse_status refuses the wrong shape, a missing key
        and a non-boolean alike, so the display and cmd_gate.py agree on
        what a readable status IS rather than keeping two rules.
        """
        state = plc_link.parse_status(msg.data.encode())
        if state is None:
            state = plc_link.FAILSAFE
        colour, text = lamp_state(state["estop_healthy"])
        self.lamp.configure(bg=colour, text=text)
        self.enable.configure(text=enable_text(state["motor"]))

    def publish(self):
        linear, angular = knob_to_twist(
            self.knob[0], self.knob[1], KNOB_RADIUS_PX,
            self.speed_max, self.steer_max)
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.pub.publish(msg)


def main():
    rclpy.init()
    root = tk.Tk()
    node = Hmi(root)

    def pump():
        # Ctrl-C AND SIGTERM CLOSE THE WINDOW. rcl installs its own
        # handler for both: it shuts the context down and does NOT end
        # the process, so without this check spin_once raises "the given
        # context is not valid" on every tick for ever - measured at
        # 90896 lines of traceback against one SIGTERM - and the window
        # never goes away. Leaving through mainloop is what runs the
        # tidy-up below.
        if not rclpy.ok():
            root.quit()
            return
        # THE RESCHEDULE COMES FIRST. after() is a one-shot, so a
        # spin_once that raises skips the next booking and the loop is
        # gone - no publishing, no lamp - while Tk prints the traceback
        # and leaves the window open, looking alive.
        root.after(SPIN_MS, pump)
        rclpy.spin_once(node, timeout_sec=0.0)

    root.after(SPIN_MS, pump)
    try:
        root.mainloop()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
