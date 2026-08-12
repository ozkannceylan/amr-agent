"""field_eval.py - what a safety laser scanner does inside its own housing.

Three gpu_lidar scans in, three (pf, wf) verdicts out. The arithmetic is
m5-plc-debug/microscan3.py's, which the owner validated against the PLC;
this file ports it to ROS and does not change a threshold.

    FIELDS = {1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}   case: (PF, WF)
    N_SCAN = 3 consecutive scans, +0.20 m hysteresis when re-clearing

pf AND wf ARE TRUE WHEN THE FIELD IS CLEAR, matching the PLC tags PF_OSSD
("True = protective field clear, OSSD high") and WF_Clear. Inverting this
inverts the safety function.

THREE FAIL-SAFE DIRECTIONS, ALL OF THEM "VIOLATED"
  No scan within SCAN_STALE_S: violated. Silence is not clear.
  An empty ranges array: violated. A broken device is not an empty room.
  An unreadable monitoring case: case 3, the largest field. Not knowing
  which case applies means assuming the most demanding one.

WHAT THIS IS NOT
  Not a safety function. One software process, one scan source per device,
  no redundancy, no test pulses. No Category, no Performance Level, no SIL,
  no PFH is claimed. 1oo2 is the fail-safe input card's property and in
  PLCSIM the pair collapses to one process-image bit.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step3/ros2/field_eval.py
"""

import json
import math
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String

import status_contract

# ----------------------------- CONFIG -----------------------------
FIELDS = {1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}   # case: (PF, WF) [m]
N_SCAN = 3                  # consecutive scans before a state change
HYSTERESIS_M = 0.20         # extra margin required to RE-CLEAR
RANGE_MAX_M = 8.0           # must match forklift_ver2/model.sdf's <max>
SCAN_STALE_S = 0.5          # five missed scans at 10 Hz
PUBLISH_HZ = 10.0
FIELDS_TOPIC = "/forklift/safety/fields"
SENSORS = ("back", "left", "right")
SCAN_TOPIC = "/forklift/gz/safety_scanner_{}/measurement"

# MUTED SECTORS: the rays that see the vehicle itself. Inclusive index
# pairs into the 275-ray scan.
#
# A real microScan3 does not have this problem because its configured
# field is a CONTOUR shaped around the vehicle. Step 2 evaluates a radius
# (design section 4.1), so the equivalent has to be done here: blank the
# angular sectors that are structure rather than surroundings. This is
# the same thing a real integrator does when muting a sector at
# commissioning, and it is not a workaround for a modelling error - the
# owner's own drawing shows the left and right fans notched where the
# body blocks them.
#
# MEASURED, NOT ASSUMED, on the spawn pose in an empty aisle, taking every
# ray returning under 1.2 m:
#   back   idx   0.. 2 and 272..274   the drive wheel, at the fan's edges
#   left   idx   7..65               the mast and carriage, inboard-forward
#   right  idx 209..267              the mirror image of left
# Widened by a few rays each side so a small mount change does not leak a
# self-return into the minimum.
#
# THE COST, STATED: an obstacle inside a muted sector is invisible to that
# device. The sectors point at the vehicle's own structure, so an obstacle
# there is already unreachable - but this is the one place in Step 3 where
# a real object could be ignored, and it is why the sectors are listed
# explicitly rather than derived at runtime from "whatever looks close".
SELF_MUTE = {
    "back": ((0, 4), (270, 274)),
    "left": ((5, 68),),
    "right": ((206, 269),),
}
# ------------------------------------------------------------------


def fields_for_case(case):
    """(PF, WF) thresholds. Anything unreadable selects the largest field."""
    return FIELDS[case] if case in FIELDS else FIELDS[3]


def min_range(ranges, range_max=RANGE_MAX_M, mute=()):
    """Nearest real return, with non-returns treated as the horizon.

    gz reports a no-return as inf and can report nan. A naive min() over
    [inf, inf] gives inf and over a list holding nan gives nan, and neither
    compares usefully against a threshold. Both become range_max first.

    `mute` is a sequence of inclusive (start, end) index pairs pointing at
    the vehicle's own structure - see SELF_MUTE. Those rays are dropped
    before the minimum, because one ray grazing the mast would otherwise
    hold the device in PROTECTIVE for ever.

    An EMPTY array is a broken device, not an empty room, so it returns 0.0
    - the violated end of the scale. A scan that is ENTIRELY muted returns
    0.0 too, for the same reason: nothing was actually looked at.
    """
    if not len(ranges):
        return 0.0
    muted = set()
    for lo, hi in mute:
        muted.update(range(lo, hi + 1))
    looked = [r for i, r in enumerate(ranges) if i not in muted]
    if not looked:
        return 0.0
    finite = [r for r in looked if math.isfinite(r)]
    if not finite:
        return range_max
    return min(range_max, min(finite))


def field_step(d, clear, cnt, th):
    """One scan against one threshold. Returns (clear, count).

    Verbatim from microscan3.py: the threshold is th while clear and
    th + HYSTERESIS_M while violated, so re-clearing needs the extra margin
    and a target sitting exactly on the contour cannot chatter.
    """
    raw = d > (th if clear else th + HYSTERESIS_M)
    cnt = cnt + 1 if raw != clear else 0
    return (raw, 0) if cnt >= N_SCAN else (clear, cnt)


def level(pf, wf):
    """Display level. Protective outranks warning."""
    if not pf:
        return "PROTECTIVE"
    return "SAFE" if wf else "WARNING"


class Device:
    """One scanner's latched field state."""

    def __init__(self):
        self.pf = self.wf = False      # starts violated, like a cold OSSD
        self.pfc = self.wfc = 0
        self.last_scan = None
        self.d = 0.0                   # last MEASURED range, for the report

    def update(self, d, pf_th, wf_th, now):
        self.pf, self.pfc = field_step(d, self.pf, self.pfc, pf_th)
        self.wf, self.wfc = field_step(d, self.wf, self.wfc, wf_th)
        self.last_scan = now
        self.d = d

    def go_violated(self):
        self.pf = self.wf = False
        self.pfc = self.wfc = 0
        self.d = 0.0


class FieldEval(Node):

    def __init__(self):
        super().__init__("field_eval")
        self.devices = {name: Device() for name in SENSORS}
        self.ranges = {name: None for name in SENSORS}
        self.case = 3
        self.last_status_rx = None
        self.pub = self.create_publisher(String, FIELDS_TOPIC, 10)
        for name in SENSORS:
            self.create_subscription(
                LaserScan, SCAN_TOPIC.format(name),
                lambda msg, n=name: self.cb_scan(n, msg), 10)
        self.create_subscription(
            String, status_contract.STATUS_TOPIC, self.cb_status, 10)
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)
        self.get_logger().info(
            "fields {} | debounce {} scans | hysteresis {:.2f} m".format(
                FIELDS, N_SCAN, HYSTERESIS_M))

    def cb_scan(self, name, msg):
        self.ranges[name] = msg.ranges

    def cb_status(self, msg):
        parsed = status_contract.parse_status(msg.data.encode())
        self.case = parsed.get("case") if parsed else None
        self.last_status_rx = time.monotonic()

    def tick(self):
        now = time.monotonic()
        # A /plc/status that STOPPED must not leave the last case
        # standing. In every recorded run that value is 1 - the
        # SMALLEST protective field, 1.0 m against case 3's 4.5 m - so
        # holding it would keep telling the PLC the field is clear at
        # ranges case 3 calls a demand. None falls through to case 3,
        # which is the fail-safe end.
        case = None if status_contract.is_stale(
            self.last_status_rx, now, status_contract.STATUS_STALE_S
        ) else self.case
        pf_th, wf_th = fields_for_case(case)
        report = {"case": case if case in FIELDS else 3,
                  "pf_th": pf_th, "wf_th": wf_th, "ts": now}
        for name in SENSORS:
            dev = self.devices[name]
            raw = self.ranges[name]
            if raw is None and status_contract.is_stale(
                    dev.last_scan, now, SCAN_STALE_S):
                dev.go_violated()
            elif raw is not None:
                dev.update(min_range(raw, RANGE_MAX_M,
                                     SELF_MUTE.get(name, ())),
                           pf_th, wf_th, now)
            # No new scan but not yet stale: hold the latch AND the last
            # measured range. Reporting 0.0 here would print an intrusion
            # beside a `pf` that says clear - a report that contradicts
            # itself is worse than a stale number.
            report[name] = {"pf": dev.pf, "wf": dev.wf, "d": round(dev.d, 3),
                            "level": level(dev.pf, dev.wf)}
            self.ranges[name] = None
        self.pub.publish(String(data=json.dumps(report)))


def main():
    rclpy.init()
    node = FieldEval()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
