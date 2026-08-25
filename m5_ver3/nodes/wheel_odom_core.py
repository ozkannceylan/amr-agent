#!/usr/bin/env python3
"""wheel_odom_core.py - the vehicle's own motion estimate, as arithmetic.

    python3 m5_ver3/nodes/wheel_odom_core.py --selftest

NO ROS AND NO GAZEBO IN THIS FILE, and that is what lets the owner run
this track's pytest on the Windows python, where there is no rclpy at all.
nodes/wheel_odometry.py is the shell that subscribes, converts and
publishes; everything that could be WRONG about the estimate is here,
where a test can reach it (m6/ipc/nav_core.py against nav_node.py is the
same split).

WHAT IT COMPUTES. One front-steer tricycle, dead-reckoned from two
readings: the drive shaft's angle and the steer axis's angle. Nothing
else. It reads no ground truth, no IMU, no scan and no clock of its own -
the caller supplies the timestamp, so the estimate is a function of its
inputs and of nothing in the room.

    Geometry, from config.yaml's VEHICLE block (which took it from
    agv/forklift/config.yaml, which derived it from model.sdf's link
    poses): the single steered wheel is also the driven wheel and leads
    at model x = +0.55; the two passive wheels trail on an axle at
    x = -0.50. So the wheelbase is L = 1.05 m and base_link stands
    d = +0.50 m FORWARD of the rear axle midpoint R.

    Let delta be the steer angle, v_w the drive wheel's tread speed and
    psi the model's yaw. The rear wheels cannot slide sideways, so the
    velocity of R is purely longitudinal; the drive wheel's contact sits
    at R + (L, 0) in the body frame and cannot slide sideways either, so

        v_R    = v_w * cos(delta)
        psidot = v_w * sin(delta) / L

    and base_link, a different point of the same rigid body:

        v_Bx = v_R
        v_By = d * psidot

    THAT LATERAL TERM IS REAL AND IT IS NOT AN ERROR. base_link genuinely
    moves sideways whenever the vehicle turns, because it is not on the
    rear axle. Reporting v_By = 0 - what differential-drive odometry
    copied onto a tricycle does - tells the F2 EKF the body is not doing
    something it is doing.

    Integration is EXACT over each interval rather than Euler: with v_w
    and delta held, R travels a circular arc, and this file integrates
    the arc and then places base_link on the result.

SIGNS, AND THEY ARE THE REPO'S AND NOT THIS FILE'S. Model yaw 0 points
the forks at world -x, so the TRAVEL heading is model yaw + pi, forward
travel is a NEGATIVE tread speed, and facing the travel direction world
+y is the driver's right. m6/ipc/follower.py's header and
m6/tests/test_follower.py's header are where those three sentences live;
tests/test_wheel_odom_core.py locks all three here with worked examples.

  ONE PLACE THE TWO CONVENTIONS DIFFER, AND IT WILL BITE F2 IF IT IS NOT
  READ. follower.py says "positive angular.z is a driver-right turn",
  which is the DRIVER'S CONSOLE convention that hmi_node.knob_to_twist
  owns: push the stick forward for negative linear.x, turn the knob right
  for positive angular.z. It is a mirror, not a frame. What this file
  publishes is a nav_msgs/Odometry twist, which by that message's own
  contract is expressed in base_link - the MODEL frame - where a
  driver-right turn is a DECREASING yaw and therefore a NEGATIVE
  angular.z. The two are opposite on purpose and neither is wrong. An EKF
  fed this twist must read it as base_link, and anything that compares it
  with a follower command has to flip the sign of the yaw rate first.

THE TWO ERRORS THIS FILE EXISTS TO MAKE. An odometry computed off a joint
that agrees with the simulator is GROUND TRUTH WITH EXTRA STEPS: the F2
EKF would have nothing to correct and every localisation figure taken
against it would be circular (model.sdf says the same thing beside the
wheel-slip system). So two named, measured, configured errors are built
in, and both are config.yaml's to set:

  QUANTISATION, on the POSITION count grid. The drive reading is floored
  onto a grid of counts_per_rev counts per revolution - the last edge the
  head SAW, never the nearest edge, because the nearest edge may not have
  happened - and the velocity is then differenced OUT of the quantised
  positions. Quantising the velocity instead would be a different device:
  it would lose the sub-count residue every sample and a slow run would
  simply never move.
    THE SIGNAL IT RIDES IS THE PLANT'S OWN SHAFT ANGLE. gz's
    JointStatePublisher on drive_wheel_joint carries position as well as
    velocity, so nothing here integrates a rate into a fake position -
    the count grid is applied to the angle the simulator reports, which
    is what a real disc is bolted to.

  A WHEEL-RADIUS SCALE ERROR. The radius this file multiplies by is the
  radius the VEHICLE BELIEVES, and it is deliberately not the radius the
  physics rolls on. A loaded polyurethane drive tyre's effective rolling
  radius is smaller than its free radius, so a truck calibrated on a free
  tyre over-reports distance for ever.

  A STEER BIAS, and it is SENSOR SIDE. It is added to the steer READING
  before the kinematics, never to a command: a steer encoder's zero is
  set against mechanical straight-ahead by a calibration, and what is
  modelled is that calibration's residual. The wheel goes where it is
  told; the estimator is wrong about where that is.

ONE READING HEAD, AND THE FILE SAYS SO OUT LOUD. model.sdf publishes the
SAME joint on two topics, read_a and read_b, and m6/ipc/encoder_link.py's
header names what that arrangement is: a SINGLE-CHANNEL TESTED SYSTEM,
one shaft and one measured quantity with two readings of it, never a
two-channel one. The odometry of a real truck rides ONE encoder, so the
shell subscribes read_a and this file is fed from it. AVERAGING a AND b
WOULD BE A LIE OF EXACTLY THE KIND THAT DOCUMENTATION FORBIDS: it would
claim a redundancy the shaft does not have, and it would halve a
quantisation noise that is common to both readings anyway.

WHAT THIS IS NOT. It is not the vehicle's pose - it is one sensor's
opinion of it, in the sense the IMU's yaw rate is another, published so
that F2's EKF can fuse the two. A dead-reckoned pose has unbounded error
by construction. It is not a safety function and not a real-time
controller: a late call here degrades an estimate, and inhibits nothing.
"""
import argparse
import collections
import math
import sys

# THE ONLY MAGIC NUMBER IN THIS FILE, AND IT IS NOT BEHAVIOURAL. Below
# this yaw increment the exact-arc form (s/dpsi)(sin psi' - sin psi, ...)
# loses its meaning to cancellation, and above it the straight-line limit
# it is replaced by is wrong by O(dpsi^2/24). At 1e-9 rad both errors are
# smaller than a double can express over one count of tread (0.74 mm), so
# the seam is invisible either way - tests/test_wheel_odom_core.py checks
# that it is. It is not in config.yaml because it decides nothing about
# the vehicle: it is where two spellings of the same arc swap over.
_STRAIGHT_RAD = 1e-9

#: What one call to WheelOdometry.update() produced. A plain record, so
#: the shell can put it on a message and a test can read it, and neither
#: has to reach into the estimator's own attributes to find out what
#: happened.
Estimate = collections.namedtuple(
    "Estimate", "t_s dt_s count x y yaw vx vy yaw_rate")


class DriveEncoder(object):
    """One incremental reading head on the drive shaft.

    It holds the count grid and nothing else: no phase, no jitter, no
    noise. agv/forklift/scripts/safe_speed_channels.py models phase and
    jitter because it is about two heads DISAGREEING, which is a
    cross-comparison's whole subject. This file is about one head, where
    a mounting phase cancels out of every difference and would change no
    figure this track measures.
    """

    def __init__(self, counts_per_rev):
        counts_per_rev = int(counts_per_rev)
        if counts_per_rev <= 0:
            raise ValueError(
                "counts_per_rev must be positive, got {!r} - check "
                "config.yaml wheel_odom.counts_per_rev".format(
                    counts_per_rev))
        self.counts_per_rev = counts_per_rev
        self.count_rad = 2.0 * math.pi / float(counts_per_rev)

    def count(self, shaft_angle_rad):
        """The count index this shaft angle has reached.

        FLOOR AND NOT ROUND. A head reports the last edge it saw; to
        round it would have to know about an edge that has not happened
        yet. Flooring is not an odd function, which is the property that
        keeps a direction change from gaining a count.
        """
        return int(math.floor(shaft_angle_rad / self.count_rad))

    def angle(self, shaft_angle_rad):
        """The same reading as an angle, back on the grid."""
        return self.count(shaft_angle_rad) * self.count_rad


class WheelOdometry(object):
    """Dead reckoning for one front-steer tricycle. See the file header.

    The integrated state is the REAR AXLE MIDPOINT, because that is the
    point whose velocity is purely longitudinal and therefore the only
    one whose motion is an arc of the steer angle. base_link is placed on
    it afterwards. Doing it the other way round - integrating base_link
    directly - quietly drops the lateral term and there is no symptom
    until something fuses the twist.
    """

    def __init__(self, wheelbase_m, wheel_radius_m, rear_axle_offset_m,
                 counts_per_rev, wheel_radius_scale=1.0, steer_bias_rad=0.0):
        self.wheelbase_m = float(wheelbase_m)
        if self.wheelbase_m <= 0.0:
            raise ValueError(
                "wheelbase_m must be positive, got {!r} - check "
                "config.yaml vehicle.wheelbase_m".format(wheelbase_m))
        # THE RADIUS THE VEHICLE BELIEVES, formed once, here. The true
        # radius is never stored: nothing in this file is entitled to
        # know it, and an estimator holding both numbers is one edit away
        # from using the right one.
        self.odom_radius_m = float(wheel_radius_m) * float(wheel_radius_scale)
        # d, the distance base_link stands FORWARD of the rear axle.
        # config.yaml records the rear axle's x in base_link (-0.50), so
        # the sign flips here and once only.
        self.base_offset_m = -float(rear_axle_offset_m)
        self.steer_bias_rad = float(steer_bias_rad)
        self.encoder = DriveEncoder(counts_per_rev)
        self.reset()

    # ------------------------------------------------------------------

    def reset(self, x=0.0, y=0.0, yaw=0.0):
        """Put base_link at a pose and forget every reading.

        THE DEFAULT IS THE ORIGIN, AND THAT IS THE RIGHT DEFAULT. The
        odom frame is defined as wherever the estimate started, which is
        also what gz's OdometryPublisher does with the ground truth this
        estimate is scored against - so the two curves leave the same
        point and their divergence is the reading, with no spawn pose
        needed by either of them.
        """
        self.yaw = float(yaw)
        # The rear axle, from the base_link pose asked for.
        self._rx = float(x) - self.base_offset_m * math.cos(self.yaw)
        self._ry = float(y) - self.base_offset_m * math.sin(self.yaw)
        self._count = None
        self._t_s = None
        self.count = 0
        self.vx = 0.0
        self.vy = 0.0
        self.yaw_rate = 0.0

    @property
    def x(self):
        """base_link, placed on the rear axle it was integrated from."""
        return self._rx + self.base_offset_m * math.cos(self.yaw)

    @property
    def y(self):
        return self._ry + self.base_offset_m * math.sin(self.yaw)

    # ------------------------------------------------------------------

    def update(self, t_s, drive_angle_rad, steer_angle_rad):
        """One encoder sample in, one Estimate out - or None.

        None means THERE IS NO ESTIMATE, not that the estimate is zero:
        the first reading of a run is not an interval, and neither is a
        repeated or a backwards timestamp. In all three cases the state
        is left exactly as it was, so the next good sample differences
        against the last GOOD one and no counts are lost. That property
        is what lets the shell drop a sample - for a stale steer reading,
        say - without the distance going missing: the count grid is
        ABSOLUTE, so a gap costs resolution in time and nothing in space.
        """
        t_s = float(t_s)
        count = self.encoder.count(drive_angle_rad)
        if self._count is None or self._t_s is None:
            self._count = count
            self._t_s = t_s
            return None
        dt_s = t_s - self._t_s
        if dt_s <= 0.0:
            return None

        # THE QUANTISED ROTATION, and it is a difference of two counts
        # rather than a quantised difference. See the file header.
        d_shaft = (count - self._count) * self.encoder.count_rad
        # The tread the vehicle BELIEVES it laid down.
        ds = d_shaft * self.odom_radius_m
        # The steer angle the vehicle BELIEVES the wheel is at.
        delta = float(steer_angle_rad) + self.steer_bias_rad

        s_rear = ds * math.cos(delta)
        d_yaw = ds * math.sin(delta) / self.wheelbase_m
        yaw_next = self.yaw + d_yaw
        if abs(d_yaw) > _STRAIGHT_RAD:
            radius = s_rear / d_yaw
            self._rx += radius * (math.sin(yaw_next) - math.sin(self.yaw))
            self._ry += radius * (math.cos(self.yaw) - math.cos(yaw_next))
        else:
            # The limit of the line above, evaluated at the mid-heading so
            # that a long nearly straight leg does not accumulate the
            # half-increment as a cross-track error.
            mid = self.yaw + 0.5 * d_yaw
            self._rx += s_rear * math.cos(mid)
            self._ry += s_rear * math.sin(mid)
        self.yaw = yaw_next

        self._count = count
        self._t_s = t_s
        self.count = count
        self.yaw_rate = d_yaw / dt_s
        self.vx = s_rear / dt_s
        self.vy = self.base_offset_m * self.yaw_rate
        return Estimate(t_s=t_s, dt_s=dt_s, count=self.count,
                        x=self.x, y=self.y, yaw=self.yaw,
                        vx=self.vx, vy=self.vy, yaw_rate=self.yaw_rate)


def yaw_to_quaternion(yaw):
    """(z, w) of a yaw-only rotation. The shell's message needs it and
    this is arithmetic, so it lives on this side of the split."""
    return math.sin(0.5 * yaw), math.cos(0.5 * yaw)


def normalise_angle(rad):
    """Fold an angle into (-pi, pi].

    The integrated yaw is deliberately NOT folded - a heading that wraps
    mid-arc would put a 2 pi step into any consumer differencing it - so
    this exists for the consumers that want it, and for the selftest.
    """
    return math.atan2(math.sin(rad), math.cos(rad))


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_wheel_odom_core.py is the real suite; this is the version
    an operator can run on the rig, in the shell they are already in,
    without pytest. It covers the same three things a bringup gets wrong:
    the grid, the signs and the two error terms.
    """
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    q = 2.0 * math.pi / 1024

    enc = DriveEncoder(1024)
    check("one count is 2 pi / 1024", abs(enc.count_rad - q) < 1e-15)
    check("the reading floors and never rounds",
          enc.count(0.999 * q) == 0 and enc.count(1.001 * q) == 1)
    check("flooring is not an odd function", enc.count(-1.5 * q) == -2)

    def odom(scale=1.0, bias=0.0):
        return WheelOdometry(1.05, 0.12, -0.50, 1024,
                             wheel_radius_scale=scale, steer_bias_rad=bias)

    def drive(o, shaft, steer, steps):
        o.update(0.0, 0.0, steer)
        last = None
        for i in range(1, steps + 1):
            last = o.update(i * 0.002, shaft * i / steps, steer)
        return last

    check("one reading is not an interval",
          odom().update(0.0, 1.0, 0.0) is None)

    est = drive(odom(), 12.7 * q, 0.0, 1)
    check("travel is a whole number of counts",
          est.count == 12
          and abs(est.x - 12.0 * q * 0.12) < 1e-15)

    est = drive(odom(), 0.99 * q, 0.0, 1)
    check("a sub-count movement is no movement",
          est.x == 0.0 and est.vx == 0.0 and est.yaw == 0.0)

    est = drive(odom(), -500.0 * q, 0.0, 50)
    check("forward travel is a negative shaft and a negative vx",
          est.vx < 0.0 and est.x < 0.0)

    est = drive(odom(), -70.0, 0.2, 400)
    check("positive steer forward is a driver-right turn "
          "(model yaw down, world +y)",
          est.yaw < 0.0 and est.y > 0.0)

    est = drive(odom(), 70.0, 0.2, 400)
    check("the same steer astern turns the other way", est.yaw > 0.0)

    # 1000.5 counts and not 1000: n * q / q is 999.9999999999999 in
    # binary, so asking for a whole count is asking which side of an edge
    # a double landed on. tests/test_wheel_odom_core.py's drive() carries
    # the same note and the same half-count.
    truth = 1000.0 * q * 0.12
    est = drive(odom(scale=1.015), 1000.5 * q, 0.0, 1)
    check("the scale error is exactly 1.5 % of the distance",
          abs((est.x - truth) - 0.015 * truth) < 1e-12)

    est = drive(odom(bias=0.005), 1000.5 * q, 0.0, 1)
    check("the steer bias invents 3.50624e-3 rad over 1000 counts",
          abs(est.yaw - 3.50624e-3) < 1e-7)

    est = drive(odom(), -20.0, 0.3, 200)
    check("base_link carries the lateral term the rear axle does not",
          abs(est.vy - 0.5 * est.yaw_rate) < 1e-15 and est.vy != 0.0)

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    # The denominator is derived from the checks that ran and never typed
    # beside them: a hand-written count is how a suite silently leaves a
    # check behind (LESSONS 2026-07-28).
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="wheel odometry arithmetic for m5-ver3. "
                    "The node that uses it is nodes/wheel_odometry.py.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-Gazebo checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
