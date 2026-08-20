"""encoder_link.py - the drive shaft's two reading channels, in mm/s.

forklift_ver2/model.sdf runs two JointStatePublisher systems on the SAME
joint, drive_wheel_joint, publishing /forklift/gz/drive_speed/read_a and
read_b. This node turns each into the millimetres per second the PLC's
ENC_A and ENC_B tags are scaled in, and publishes both plus a health
verdict.

A SINGLE-CHANNEL TESTED SYSTEM, NEVER A TWO-CHANNEL ONE
  One shaft, one measured quantity, two readings of it. Both readings die
  with the shaft they read. That is what a real safe encoder is, and
  calling the arrangement two-channel would claim a redundancy it does not
  have. The language is model.sdf's and config.yaml's; this file keeps it.
  No Category, no Performance Level, no SIL, no PFH is claimed.

WHY THE SYNTHETIC NOISE IS GONE
  m5-plc-debug/encoder.py added rand(-5, 5) to each channel because it had
  one speed number and needed two. Here the plant renders each channel
  independently, so any disagreement is the simulation's own and not a
  number this file invented.

THIS NODE NEVER LIES ABOUT WHAT IT MEASURED
  The fault modes live in step6.py, on the Windows side, because a broken
  encoder is a field fault and the PLCSIM API is the wiring. What leaves
  here is what the shaft did.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step6/ipc/encoder_link.py
"""

import json
import os
import time

import rclpy
import yaml
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String

import status_contract

# ----------------------------- CONFIG -----------------------------
CHANNELS = ("a", "b")
PUBLISH_HZ = 20.0
# The joint publishers run at the world rate (about 493 Hz in a 500 Hz
# world), so five missed samples is a very long time. This window is
# generous on purpose: it catches a DEAD publisher, not a late one.
ENC_STALE_S = 0.3
# |ENC_A - ENC_B| > 50 mm/s is the F-program's cross-check
# (m5_ver2/CLAUDE.md section 3.2). Mirrored here for the lamp only - the
# PLC's verdict is the one that stops the vehicle.
DISAGREE_MM_S = 50
# ------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "agv", "forklift", "config.yaml"))


def load_config(path=CONFIG_YAML):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def channel_topics(cfg):
    """The two reading channels, from the file that owns their names.

    config.yaml:873-874 holds topics.gz_drive_speed_read_a and _b, and
    the launch file bridges them from there. Hard-coding them here
    would make one name have two sources in one step: rename the config
    key and the bridge and this subscriber break differently, with a
    silently red encoder lamp as the only symptom.
    """
    return {c: cfg["topics"]["gz_drive_speed_read_{}".format(c)]
            for c in CHANNELS}


def omega_to_mm_s(omega_rad_s, wheel_radius_m):
    """Shaft rate -> tread speed in mm/s, the unit ENC_A and ENC_B carry.

    Rounded to an int because the PLC tags are Int. Sign is preserved:
    reversing is a negative reading, and the F-program's cross-check works
    on the difference either way.
    """
    return int(round(omega_rad_s * wheel_radius_m * 1000.0))


def healthy(a, b, disagree=DISAGREE_MM_S):
    """The lamp's verdict, mirroring the F-program's cross-check.

    Either channel missing is a fault: no reading is not a matching pair.
    """
    if a is None or b is None:
        return False
    return abs(a - b) <= disagree


class EncoderLink(Node):

    def __init__(self):
        super().__init__("encoder_link")
        cfg = load_config()
        self.wheel_radius = float(cfg["model"]["wheel_radius_m"])
        topics = channel_topics(cfg)
        self.mm_s = {c: None for c in CHANNELS}
        self.last_rx = {c: None for c in CHANNELS}
        self.pub = self.create_publisher(
            String, status_contract.ENCODERS_TOPIC, 10)
        for c in CHANNELS:
            self.create_subscription(
                JointState, topics[c],
                lambda msg, ch=c: self.cb_channel(ch, msg), 10)
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)
        self.get_logger().info(
            "wheel radius {:.3f} m | disagreement limit {} mm/s".format(
                self.wheel_radius, DISAGREE_MM_S))

    def cb_channel(self, channel, msg):
        if not msg.velocity:
            return
        self.mm_s[channel] = omega_to_mm_s(msg.velocity[0], self.wheel_radius)
        self.last_rx[channel] = time.monotonic()

    def tick(self):
        now = time.monotonic()
        vals = {}
        for c in CHANNELS:
            stale = status_contract.is_stale(
                self.last_rx[c], now, ENC_STALE_S)
            # A stale channel is reported as ABSENT, not as its last value.
            # Holding the last speed would say "still moving at 400 mm/s"
            # about a publisher that stopped, and holding zero would say
            # "stopped" about a vehicle that may not be.
            vals[c] = None if stale else self.mm_s[c]
        self.pub.publish(String(data=json.dumps({
            "a": vals["a"], "b": vals["b"],
            "healthy": healthy(vals["a"], vals["b"]),
            "ts": now,
        })))


def main():
    rclpy.init()
    node = EncoderLink()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
