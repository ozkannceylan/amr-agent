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
  python3 m5_ver2/step2/ros2/hmi_node.py
"""

import math
import os
import time
import tkinter as tk

import rclpy
import yaml
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String

from status_contract import (
    FAILSAFE, STATUS_STALE_S, STATUS_TOPIC, is_stale, parse_status)

# ----------------------------- CONFIG -----------------------------
PUBLISH_HZ = 20.0
# tkinter's after() period for pumping rclpy. THROUGHPUT, and nothing
# else: spin_once handles ONE work item per call and a live link offers
# 40 a second (the 20 Hz tick, the 20 Hz status). At 20 ms the pump ran
# 49 times a second against those 40 - no headroom - and /hmi/cmd_vel
# measured 16.5 Hz against this file's own PUBLISH_HZ. At 4 ms it
# measures 20.01 Hz. Any period with that headroom does; nothing depends
# on this exact value, and after() is a floor rather than a period.
SPIN_MS = 4
# STATUS_STALE_S - the timeout on /plc/status - is imported and not
# declared here: the screen and the vehicle stop trusting a silent
# status at the same instant because it is now literally the same
# constant, and not two that a test holds equal. Its derivation,
# including why an exact multiple of THIS file's tick is accepted, is at
# that home.
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

    THE FORK END IS FORWARD, AND IT IS THE MODEL'S -x. model.sdf puts the
    front safety scanner at +0.70 x and the tines at the opposite end, so
    the body +x this node commands points at the counterweight. The owner
    drives a forklift forks-first, so dragging up commands NEGATIVE
    linear.x.

    Both signs flip together. Reversing which end leads also reverses which
    way a given steer angle turns the vehicle as the driver sees it, so the
    steer sign flips with the speed sign to keep "push right, go right".

    Canvas y grows downward, so dragging up is already a negative dy and
    needs no negation here.
    """
    nx = max(-1.0, min(1.0, dx / radius))
    ny = max(-1.0, min(1.0, dy / radius))
    return (ny * speed_max, nx * steer_max)


def lamp_state(estop_healthy):
    """(colour, text) for the lamp. Healthy is not an alarm colour."""
    if estop_healthy:
        return (LAMP_NEUTRAL, "E-Stop Inactive")
    return (LAMP_RED, "E-Stop Active")


def enable_text(motor):
    return "Drive enable: {}".format("ON" if motor else "OFF")


def display_state(status, last_rx_s, now_s, stale_s=STATUS_STALE_S):
    """The whole display decision: (lamp colour, lamp text, enable text).

    A /plc/status that STOPPED is shown as the safe state, not as the
    last good one. Nothing announces silence, so the only way to see it
    is to look at the clock on the tick; a frozen screen reading "E-Stop
    Inactive / Drive enable: ON" over a dead link is the same lying
    display this window exists to prevent, and cmd_gate having stopped
    the truck within 0.35 s only means it is the SCREEN that is wrong.

    is_stale is the shared contract's, not a third staleness rule
    written here, and it already reads a last_rx_s of None as stale, so
    "never received" needs no branch. That matters at start-up: a lamp
    reading "E-Stop Inactive" before the PLC has said anything claims a
    healthy chain on no evidence.
    """
    if is_stale(last_rx_s, now_s, stale_s):
        status = FAILSAFE
    colour, text = lamp_state(status["estop_healthy"])
    return (colour, text, enable_text(status["motor"]))


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
        self.create_subscription(String, STATUS_TOPIC, self.cb_status, 10)
        self.knob = (0.0, 0.0)
        # A window that has not heard from the PLC claims nothing about
        # the chain: last_status_rx of None reads as stale, so the first
        # display is the safe one.
        self.status = FAILSAFE
        self.last_status_rx = None
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)

        self.root = root
        root.title("Step 2 - forklift teleoperation")
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

        # Built from the same decision the tick uses, so the window never
        # shows a state it has not been told, not even for one tick.
        self.shown = display_state(
            self.status, self.last_status_rx, time.monotonic())
        colour, lamp_text, enable_line = self.shown
        self.lamp = tk.Label(
            root, text=lamp_text, fg="white", bg=colour,
            font=("TkDefaultFont", 16, "bold"), padx=16, pady=10)
        self.lamp.pack(fill="x", padx=10)
        self.enable = tk.Label(root, text=enable_line,
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
        """Record WHAT arrived and WHEN. The screen is drawn on the tick,
        because the state that matters most - a status that stopped - is
        announced by no message at all.

        Anything unreadable is recorded as the SAFE state, and the shared
        contract's parser decides what readable means: a bare json.loads
        read `[1,2]` - valid JSON, wrong shape - and raised AttributeError
        here, which took the pump with it, leaving the window open reading
        "Drive enable: ON" with /hmi/cmd_vel dead. Measured, not argued.
        """
        state = parse_status(msg.data.encode())
        self.status = FAILSAFE if state is None else state
        self.last_status_rx = time.monotonic()

    def refresh(self):
        """Redraw only on a CHANGE. configure() at 20 Hz would mark both
        labels dirty every tick for a display that changes a few times a
        session."""
        shown = display_state(
            self.status, self.last_status_rx, time.monotonic())
        if shown == self.shown:
            return
        self.shown = shown
        colour, lamp_text, enable_line = shown
        self.lamp.configure(bg=colour, text=lamp_text)
        self.enable.configure(text=enable_line)

    def tick(self):
        """The 20 Hz tick, and the only thing that can notice a
        /plc/status that stopped: no message arrives to announce it, so
        the silence has to be found by looking at the clock."""
        self.publish()
        self.refresh()

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
        # the process, so without this spin_once raises "the given
        # context is not valid" every tick for ever - 90896 lines of
        # traceback against one SIGTERM - and the window never goes away.
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
