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
  python3 m5_ver2/step6/hmi/hmi_node.py
"""

import json
import math
import os
import time
import tkinter as tk

# THE WINDOW NO LONGER SITS BESIDE THE CONTRACT. Step 5 split the nodes into
# ipc/ (the PLC-facing links) and hmi/ (this window), so status_contract is
# one directory across rather than one directory along, and the import below
# needs the path said out loud.
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "ipc")))

import rclpy
import yaml
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String

import map_panel
from status_contract import (
    AUTO_GOAL_TOPIC, AUTO_STATE_TOPIC, CONFIG_PATH, ENCODERS_TOPIC, FAILSAFE,
    FIELDS_TOPIC, HMI_CMD_TOPIC, MODE_AUTO, MODE_TELEOP, MODE_TOPIC,
    STATUS_STALE_S, STATUS_TOPIC, VID, is_stale, parse_status,
    speed_limit_mm_s)

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
# The knob greys out in auto. It is HONESTY, not a second interlock: the
# mux stops forwarding /hmi/cmd_vel the instant auto is selected, so a
# knob that still looked live would be the same lying display this
# window exists to prevent.
KNOB_TELEOP = "#37474f"
KNOB_AUTO = "#b0bec5"
LAMP_RED = "#c62828"
LAMP_NEUTRAL = "#455a64"
LAMP_GREEN = "#2e7d32"
LAMP_ORANGE = "#ef6c00"

SENSOR_NAMES = ("Back", "Left", "Right")

_LEVEL_LAMP = {
    "SAFE": (LAMP_GREEN, "Safe"),
    "WARNING": (LAMP_ORANGE, "Warning Field"),
    "PROTECTIVE": (LAMP_RED, "Protective Field"),
}
# ------------------------------------------------------------------


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


def sensor_lamp(name, level):
    """(colour, text) for one scanner lamp.

    An unknown level - no message yet, a stale topic, a level this build
    does not know - shows PROTECTIVE. A display that has lost its source
    must not show a comfortable state, which is the rule Step 1 arrived at
    the hard way when a dead callback left "Drive enable: ON" on screen.
    """
    colour, word = _LEVEL_LAMP.get(level, _LEVEL_LAMP["PROTECTIVE"])
    return (colour, "{} Sensor : {}".format(name, word))


def encoder_lamp(healthy):
    """(colour, text) for the encoder lamp.

    None - no report yet, or a stale topic - reads as a fault, by the
    same rule as every other indicator here.

    IT READS THE TRUE CHANNELS. A fault injected in step6.py corrupts
    the reading on its way to the PLC, so this lamp can say Healthy
    while the PLC faults. That disagreement is correct and worth
    seeing: the vehicle believes its encoders, the field wiring is
    broken. README_step6.md says so.
    """
    if healthy is True:
        return (LAMP_GREEN, "Encoder : Healthy")
    return (LAMP_RED, "Encoder : Fault")


def enable_text(motor, v_limit=None):
    """The drive-enable line, with the PLC's speed permission beside it.

    A sixth lamp would be clutter; the limit belongs next to the enable
    because they answer the same question - what may the truck do right
    now. It is the number that explains why a healthy vehicle is
    creeping rather than driving.
    """
    base = "Drive enable: {}".format("ON" if motor else "OFF")
    if v_limit is None:
        return base
    return "{}  \u00b7  limit {:.2f} m/s".format(base, v_limit / 1000.0)


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
    limit = speed_limit_mm_s(status.get("v_limit"))
    return (colour, text, enable_text(status["motor"], limit))


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class Hmi(Node):

    def __init__(self, root):
        super().__init__("hmi_node")
        cfg = load_config()
        self.speed_max = float(cfg["limits"]["traction_speed_max_mps"])
        self.steer_max = float(cfg["model"]["steer_limit_rad"])

        self.pub = self.create_publisher(Twist, HMI_CMD_TOPIC, 10)
        self.create_subscription(String, STATUS_TOPIC, self.cb_status, 10)
        self.create_subscription(String, FIELDS_TOPIC, self.cb_fields, 10)
        self.create_subscription(
            String, ENCODERS_TOPIC, self.cb_encoders, 10)
        # THE MODE PUBLISHER IS LATCHED, AND IT HAS TO BE. cmd_mux and
        # nav_node both subscribe TRANSIENT_LOCAL so a node started after
        # this window still learns the mode; a VOLATILE publisher here is
        # incompatible with those subscriptions and delivers NOTHING to
        # either - measured in Task 6, where the Auto button silently did
        # nothing at all.
        latched = QoSProfile(
            depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.pub_mode = self.create_publisher(String, MODE_TOPIC, latched)
        self.pub_goal = self.create_publisher(String, AUTO_GOAL_TOPIC, 10)
        # The odom topic name is config.yaml's - the file that owns it -
        # read the way nav_node and encoder_link read theirs.
        self.create_subscription(
            Odometry, cfg["topics"]["gz_odom"], self.cb_odom, 10)
        self.create_subscription(
            String, AUTO_STATE_TOPIC, self.cb_auto_state, 10)
        self.mode = MODE_TELEOP
        self.pub_mode.publish(String(data=self.mode))   # latch the default
        self.pose = None
        self.auto_state = None
        self.last_auto_rx = None
        # Same rule as /plc/status: a report that stopped arriving is not a
        # clear field. field_eval publishes at 10 Hz, so the window shares
        # STATUS_STALE_S rather than inventing a third budget.
        self.fields = {}
        self.last_fields_rx = None
        self.encoders = {}
        self.last_encoders_rx = None
        self.knob = (0.0, 0.0)
        # A window that has not heard from the PLC claims nothing about
        # the chain: last_status_rx of None reads as stale, so the first
        # display is the safe one.
        self.status = FAILSAFE
        self.last_status_rx = None
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)

        self.root = root
        # The id in the title bar: two identical cabs are open at once.
        root.title("Forklift HMI - " + VID)
        cx = cy = KNOB_RADIUS_PX + 20

        # Two columns: Step 4's window on the left, unchanged in every
        # respect but its parent, and Step 5's warehouse sketch on the
        # right. The lamps keep their order and their width.
        body = tk.Frame(root)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body)
        left.pack(side="left", anchor="n")

        self.canvas = tk.Canvas(left, width=2 * cx, height=2 * cy,
                                bg="#eceff1", highlightthickness=0)
        self.canvas.pack(padx=10, pady=10)
        self.canvas.create_oval(cx - KNOB_RADIUS_PX, cy - KNOB_RADIUS_PX,
                                cx + KNOB_RADIUS_PX, cy + KNOB_RADIUS_PX,
                                outline="#90a4ae", width=2)
        self.dot = self.canvas.create_oval(cx - 14, cy - 14, cx + 14, cy + 14,
                                           fill=KNOB_TELEOP, outline="")
        self.dot_colour = KNOB_TELEOP
        self.centre = (cx, cy)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # Built from the same decision the tick uses, so the window never
        # shows a state it has not been told, not even for one tick.
        self.shown = display_state(
            self.status, self.last_status_rx, time.monotonic())
        colour, lamp_text, enable_line = self.shown
        self.lamp = tk.Label(
            left, text=lamp_text, fg="white", bg=colour,
            font=("TkDefaultFont", 16, "bold"), padx=16, pady=10)
        self.lamp.pack(fill="x", padx=10)
        self.enable = tk.Label(left, text=enable_line,
                               font=("TkDefaultFont", 11))
        self.enable.pack(pady=(6, 8))

        self.sensor_lamps = {}
        for name in SENSOR_NAMES:
            colour, text = sensor_lamp(name, None)
            w = tk.Label(left, text=text, fg="white", bg=colour,
                         font=("TkDefaultFont", 11, "bold"), padx=10, pady=6)
            w.pack(fill="x", padx=10, pady=2)
            self.sensor_lamps[name] = w
        ecol, etext = encoder_lamp(None)
        self.encoder_widget = tk.Label(
            left, text=etext, fg="white", bg=ecol,
            font=("TkDefaultFont", 11, "bold"), padx=10, pady=6)
        self.encoder_widget.pack(fill="x", padx=10, pady=(6, 2))
        tk.Frame(left, height=6).pack()

        # STOP is the goal cancel, not a brake: nav_core reads an empty
        # station id as "cancelled" and parks. The e-stop is the brake.
        self.panel = map_panel.MapPanel(
            body, on_mode=self.set_mode, on_go=self.send_goal,
            on_stop=lambda: self.send_goal(""))
        self.panel.frame.pack(side="left", anchor="n")

    def set_mode(self, mode):
        """Radio change. Leaving auto is also the goal cancel - the mux
        stops listening to nav the same instant (its own rule), so the
        two cannot disagree for longer than one message."""
        self.mode = mode
        self.pub_mode.publish(String(data=mode))
        if mode != MODE_AUTO:
            self.pub_goal.publish(String(data=""))

    def send_goal(self, station_id):
        self.pub_goal.publish(String(data=station_id))

    def cb_odom(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        self.pose = (p.x, p.y, 2.0 * math.atan2(q.z, q.w))

    def cb_auto_state(self, msg):
        try:
            report = json.loads(msg.data)
        except ValueError:
            report = None
        self.auto_state = report if isinstance(report, dict) else None
        self.last_auto_rx = time.monotonic()

    def on_drag(self, event):
        # Display-only in auto: the mux ignores /hmi/cmd_vel there, so a
        # knob that still moved would claim an authority it has not got.
        if self.mode == MODE_AUTO:
            return
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

    def cb_fields(self, msg):
        """Same shape as cb_status: record what and when, draw on the tick."""
        try:
            report = json.loads(msg.data)
        except ValueError:
            report = {}
        self.fields = report if isinstance(report, dict) else {}
        self.last_fields_rx = time.monotonic()

    def cb_encoders(self, msg):
        try:
            report = json.loads(msg.data)
        except ValueError:
            report = {}
        self.encoders = report if isinstance(report, dict) else {}
        self.last_encoders_rx = time.monotonic()

    def refresh(self):
        """Redraw only on a CHANGE. configure() at 20 Hz would mark both
        labels dirty every tick for a display that changes a few times a
        session."""
        now = time.monotonic()
        shown = display_state(self.status, self.last_status_rx, now)
        if shown != self.shown:
            self.shown = shown
            colour, lamp_text, enable_line = shown
            self.lamp.configure(bg=colour, text=lamp_text)
            self.enable.configure(text=enable_line)

        # A stale /forklift/safety/fields shows the safe display, by the
        # same rule and the same constant as /plc/status above.
        stale = is_stale(self.last_fields_rx, now, STATUS_STALE_S)
        for name, widget in self.sensor_lamps.items():
            entry = None if stale else self.fields.get(name.lower())
            lvl = entry.get("level") if isinstance(entry, dict) else None
            colour, text = sensor_lamp(name, lvl)
            if widget.cget("text") != text:
                widget.configure(bg=colour, text=text)

        enc_stale = is_stale(self.last_encoders_rx, now, STATUS_STALE_S)
        healthy = None if enc_stale else self.encoders.get("healthy")
        ecol, etext = encoder_lamp(healthy)
        if self.encoder_widget.cget("text") != etext:
            self.encoder_widget.configure(bg=ecol, text=etext)

        knob = KNOB_AUTO if self.mode == MODE_AUTO else KNOB_TELEOP
        if knob != self.dot_colour:
            self.dot_colour = knob
            self.canvas.itemconfigure(self.dot, fill=knob)

        if self.pose is not None:
            self.panel.update_pose(*self.pose)
        # A stale /auto/state reads as NO data, not as the last state:
        # nav goes silent exactly when it loses pose, and a screen still
        # showing EN-ROUTE over a dead autopilot is the same lie the lamp
        # rules above exist to remove.
        auto_stale = is_stale(self.last_auto_rx, now, STATUS_STALE_S)
        self.panel.update_auto(None if auto_stale else self.auto_state)

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
