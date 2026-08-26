#!/usr/bin/env python3
"""rf2o_twist_core.py - what the laser odometry's output has to have done
to it before a filter may read it. Arithmetic only.

    python3 m5_ver3/nodes/rf2o_twist_core.py --selftest

nodes/rf2o_twist.py is the rclpy shell around this file, m5v3.sh starts
it as the stack child `rf2ocov`, and BOTH exist only when
`m5v3.sh start --rf2o` was given.

WHY A RELAY EXISTS AT ALL, AND WHY NONE OF IT IS A PARAMETER.
`rf2o_laser_odometry` at the revision this track pins (config.yaml
rf2o.commit) publishes a `nav_msgs/Odometry` with THREE properties
robot_localization cannot be handed as they stand. It declares seven
parameters and not one of them is about any of these:

  1. THE FRAME ITS NUMBERS ARE IN IS NOT THE SCAN'S FRAME, and on this
     vehicle it is rotated from it by exactly pi. rf2o builds its point
     cloud with beam bearings running from -fovh/2 to +fovh/2 - it
     assumes the aperture is centred on the sensor's own x axis and
     never reads `angle_min`. forklift_ver3's nav lidar is a 270 deg
     window from +0.7853982 to +5.4977871 rad, deliberately centred on
     model -x so that the blind 90 deg points ASTERN and the truck
     drives into the full aperture (model.sdf says so where the numbers
     are). So rf2o's whole solution is the true one rotated by the
     window's centre bearing, and MEASURED ON THIS RIG the truck driving
     forwards at 0.695 m/s came out as `linear.x` **+0.58**: right
     magnitude, wrong sign, because cos(pi) = -1. A rotation is exactly
     recoverable and scan_centre_rad() below recovers it, from the same
     `angle_min`/`angle_max` the scan itself carries rather than from a
     constant typed into a config file.

  2. THE COVARIANCE IS ALL ZEROS - measured on the wire, all 36 entries
     of both matrices. `publish()` default-constructs the message and
     assigns position, orientation, linear.x, linear.y and angular.z and
     nothing else. robot_localization does NOT treat a zero variance as
     "unknown, ignore this": for a channel it has been configured to
     fuse it substitutes a very small number, which is the opposite of
     ignoring it. config.yaml's rf2o.covariance: block is measured and
     EVIDENCE_FUSION.md 10.2 is the measurement.

  3. THE PUBLISHED `twist.linear.x` IS THE SCANNER'S FORWARD SPEED AND
     THE MESSAGE CALLS IT THE VEHICLE'S. Upstream computes
     `lin_speed = acu_trans(0,2) / dt`, where `acu_trans` is the
     accumulated scan-to-scan transform in the LASER's frame, and then
     stamps the message `child_frame_id: base_frame_id`. The POSE it
     publishes IS composed through the mount
     (`robot_pose_ = laser_pose_ * laser_pose_on_robot_inv_`); the TWIST
     is not. On this vehicle the scanner stands 0.55 m forward and
     0.40 m to starboard of base_link, so in a turn the two speeds
     differ by the lever-arm term - 0.107 m/s at the square's measured
     peak yaw rate, 15 % of cruise, and a BIAS across the whole corner
     rather than noise about it. base_vx() is that correction.

  AND `twist.linear.y` IS A HARD-CODED 0.0, WHICH IS WHY NOTHING HERE
  CORRECTS IT. Upstream computes a local lateral velocity
  (`kai_loc_(1)`) and then writes a literal zero into the message
  instead - measured, all 911 samples of a 60 s capture are exactly
  0.0. The lateral half of the lever arm needs the scanner's OWN vy,
  which never leaves that process, so no arithmetic outside it can
  reconstruct base_link's vy. The honest answer is not to invent one:
  ekf_rf2o.yaml leaves this arm's vy flag FALSE and says so, and the
  vehicle's real lateral velocity goes on coming from the wheel
  odometry, which computes it from d and yaw rate.

WHAT THE YAW RATE NEEDS, WHICH IS NOTHING. A rotation of the frame by a
constant angle does not change an angular velocity, and the lever arm
does not either. rf2o derives `ang_speed` from successive yaws of its own
ROBOT pose, so it passes through this file untouched - and that it does
is checked against the ground truth on a turning profile rather than
asserted (EVIDENCE_FUSION.md 10.1).

WHAT THIS FILE DELIBERATELY DOES NOT DO. There is no magnitude gate and
no scale factor. rf2o under-reports this plant's forward speed by about
a sixth and that is a MEASUREMENT of the algorithm on this floor, not a
defect to divide out; a gain fitted against the ground truth would make
the arm's own error disappear into a constant and there would be nothing
left to A/B. The only sample this file drops is one that is NOT A NUMBER,
and that is not a judgement: a single NaN reaching robot_localization
poisons the whole state vector permanently and no filter recovers.

NO ROS ANYWHERE IN THIS FILE, so tests/test_rf2o_twist_core.py reaches
every decision in it on the owner's Windows python, with no rclpy and no
simulator - the split nodes/wheel_odom_core.py and nodes/wheel_odometry.py
are written to.
"""
import argparse
import collections
import math
import sys

#: The length of a ROS covariance on a pose or a twist: 6x6, row-major.
COVARIANCE_LENGTH = 36


def scan_centre_rad(angle_min, angle_max):
    """The bearing rf2o's frame is rotated from the scan frame BY.

    rf2o lays its beams out from -fovh/2 to +fovh/2 about the sensor's
    own x axis, where `fovh = |angle_max - angle_min|`, and never reads
    `angle_min` at all. So its frame's x axis points along the MIDDLE of
    the aperture, and the angle between that and the sensor frame's own
    x axis is the window's centre bearing - which is this.

    ZERO FOR EVERY SCANNER THAT IS WRITTEN THE USUAL WAY. A symmetric
    window (-a, +a) gives 0 and this correction becomes the identity, so
    a stack whose lidar is spelled conventionally pays nothing for this
    function existing. forklift_ver3's is not spelled that way, on
    purpose and for a reason model.sdf argues where the numbers are, and
    it gives pi.

    IT IS NOT FOLDED INTO (-pi, pi]. It is used only as the argument of
    a sine and a cosine, which do not care, and folding it would hide
    the size of the correction from the line that logs it.
    """
    return 0.5 * (float(angle_min) + float(angle_max))


def rotate(x, y, rad):
    """(x, y) turned by `rad`. The plane rotation, written once.

    Both the twist and the pose need it - the twist because rf2o's
    velocity is in its own rotated frame, the pose because its position
    is - and one function is one place for the sign of the sine to be
    wrong in.
    """
    cos, sin = math.cos(rad), math.sin(rad)
    return x * cos - y * sin, x * sin + y * cos


def base_vx(vx_laser, yaw_rate, mount_y):
    """base_link's forward speed, from the SCANNER's forward speed.

    THE RIGID-BODY RELATION, WRITTEN OUT. For two points of one rigid
    body, `v_P = v_O + w x r_OP`. Here O is base_link's origin, P is the
    scanner's, `r = (mount_x, mount_y, 0)` and `w = (0, 0, yaw_rate)`, so

        w x r = (-yaw_rate * mount_y,  yaw_rate * mount_x,  0)

    and the x component gives `v_laser_x = v_base_x - yaw_rate*mount_y`,
    which inverts to the line below.

    THE LONGITUDINAL OFFSET DOES NOT APPEAR, and that is the relation
    and not an omission: `mount_x` lands entirely on the LATERAL
    component, which this arm does not publish (see the file header).
    Passing it in would suggest it was used.

    IT IS VALID ONLY FOR AN UNROTATED MOUNT - see mount_rotation_is_zero.
    That is a different rotation from scan_centre_rad's: this one is
    where the LINK is bolted, that one is where inside the link's own
    aperture rf2o thinks zero is.
    """
    return vx_laser + yaw_rate * mount_y


#: One incoming sample, decided. `publish` False means the sample is
#: dropped and `reason` is the line the node's counters and its log
#: report it under; a dropped sample has no vx and no yaw_rate, because
#: there was no number to have.
RelayDecision = collections.namedtuple(
    "RelayDecision", "publish vx yaw_rate reason")


def decide(vx_raw, vy_raw, yaw_rate_raw, centre_rad, mount_y):
    """One rf2o twist, put into base_link - or dropped, with the reason.

    TWO CORRECTIONS, IN THIS ORDER AND NOT THE OTHER ONE.
      rf2o's frame -> the SCANNER's frame:  a rotation by the aperture's
          centre bearing. It is a rotation, so it must be applied while
          the velocity is still a vector in one frame.
      the scanner's frame -> base_link:     the lever arm. It is a
          translation of the reference POINT within one frame, so it is
          applied after the frame is right.
    Doing them the other way round would add the lever-arm term in
    rf2o's rotated frame and then turn the sum, which puts the correction
    on the wrong axis by the same angle.

    THE FINITE CHECK IS MADE ON THE INPUTS **AND** ON THE RESULT.
    `inf * 0` is NaN, so a finite vx beside an infinite yaw rate becomes
    a NaN vx two lines later; a check made only on what the message
    carried would pass that sample through.

    A TWIST OF ZEROS IS PUBLISHED AND IS NOT "MISSING". A truck standing
    still has exactly that twist, and dropping it would make this arm
    fall silent whenever the vehicle stopped - which robot_localization
    reads as a sensor that has gone away (sensor_timeout), not as a
    vehicle that has.
    """
    for name, value in (("vx", vx_raw), ("vy", vy_raw),
                        ("yaw rate", yaw_rate_raw)):
        if not _finite(value):
            return RelayDecision(
                False, None, None,
                "{} is not a number ({!r})".format(name, value))
    vx_laser, _ = rotate(float(vx_raw), float(vy_raw), centre_rad)
    vx = base_vx(vx_laser, float(yaw_rate_raw), mount_y)
    if not _finite(vx):
        return RelayDecision(
            False, None, None,
            "the corrected vx is not a number ({!r} from vx {!r}, vy {!r}, "
            "yaw rate {!r})".format(vx, vx_raw, vy_raw, yaw_rate_raw))
    return RelayDecision(True, vx, float(yaw_rate_raw), None)


def _finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def covariance_is_absent(covariance):
    """Is this covariance the one rf2o publishes - i.e. no covariance?

    THE RELAY MAY ONLY WRITE OVER NOTHING. config.yaml's rf2o.covariance
    is a measured stand-in for a number the upstream node does not
    produce; the day it starts producing one - a newer pin, a fork, a
    patch - that number is the author's opinion of their own estimator
    and overwriting it silently would be this relay lying about which of
    the two the filter used. nodes/rf2o_twist.py refuses by name
    instead, and this is the test it refuses on.

    THE WHOLE MATRIX AND NOT THE DIAGONAL, because a version that filled
    only the off-diagonal terms would still be a version with an
    opinion. A NaN anywhere is NOT absent either: NaN != 0.0, and a
    matrix with one in it is a matrix to refuse rather than to overwrite.
    """
    if len(covariance) != COVARIANCE_LENGTH:
        raise ValueError(
            "a covariance is {} numbers and this is {}".format(
                COVARIANCE_LENGTH, len(covariance)))
    return all(value == 0.0 for value in covariance)


def mount_rotation_is_zero(rpy):
    """Is the scanner bolted square to the vehicle?

    base_vx() ADDS TWO SCALARS, and that is only the rigid-body relation
    when the laser LINK's x axis is base_link's x axis. Rotate the mount
    and `lin_speed` becomes a component of a velocity in a frame this
    file never sees.

    THIS IS NOT scan_centre_rad's ROTATION AND THE TWO MUST NOT BE
    CONFLATED. That one is inside the sensor - where rf2o believes the
    middle of its own aperture is - and it is recovered from the scan
    message. This one is where the LINK is bolted on the vehicle, it is
    model.sdf's business, and it is refused rather than corrected
    because correcting it needs the scanner's vy, which the arm does not
    publish.

    NO TOLERANCE, DELIBERATELY. model.sdf mounts nav_lidar_link with
    `0 0 0` and this is a check on a COPIED value (config.yaml
    vehicle.nav_lidar_mount), not a measurement with spread. A tolerance
    here would be a place for a small rotation to hide, and a small
    rotation is exactly the kind whose effect looks like drift.
    """
    return all(float(angle) == 0.0 for angle in rpy)


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_rf2o_twist_core.py is the real suite; this is the version
    an operator can run on the rig, in the shell they are already in,
    without pytest - nodes/wheel_odom_core.py carries the same pair for
    the same reason.
    """
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    # model.sdf's nav_lidar_link pose and its nav_lidar aperture, which
    # config.yaml copies the first of and the scan carries the second.
    mx, my = 0.55, -0.40
    pi = scan_centre_rad(0.7853982, 5.4977871)

    check("this plant's aperture centre is pi", abs(pi - math.pi) < 1e-6)
    check("a conventional symmetric scan needs no rotation at all",
          scan_centre_rad(-2.3561945, 2.3561945) == 0.0)
    check("a pi rotation is exactly a sign flip in the plane",
          abs(rotate(1.0, 0.0, math.pi)[0] + 1.0) < 1e-15)
    check("a zero rotation is the identity",
          rotate(0.7, -0.3, 0.0) == (0.7, -0.3))

    check("a straight run is not corrected by the lever arm",
          base_vx(-0.7, 0.0, my) == -0.7)
    check("the lever arm is yaw rate times the LATERAL offset",
          abs(base_vx(0.0, 1.0, my) - my) < 1e-15)
    check("the longitudinal offset cannot reach vx",
          base_vx(-0.5, 0.3, 0.0) == -0.5 and mx != 0.0)
    check("the square's peak yaw rate is 0.107 m/s of speed the "
          "vehicle does not have",
          abs(abs(base_vx(0.0, 0.2687, my)) - 0.10748) < 1e-5)

    # MEASURED ON THIS RIG: the truck driving forwards at a ground-truth
    # -0.6948 m/s of body vx came out of rf2o as linear.x = +0.58.
    forward = decide(0.58, 0.0, 0.0, pi, my)
    check("rf2o's +0.58 on a forward run comes out NEGATIVE, like every "
          "other estimate on this vehicle",
          forward.publish and forward.vx < 0.0
          and abs(forward.vx + 0.58) < 1e-9)

    good = decide(0.58, 0.0, 0.2687, pi, my)
    check("the rotation is applied before the lever arm",
          abs(good.vx - (-0.58 + 0.2687 * my)) < 1e-9)
    check("the yaw rate passes through both corrections untouched",
          good.yaw_rate == 0.2687)
    check("a standing truck's zero twist is published",
          decide(0.0, 0.0, 0.0, pi, my).publish)
    check("a NaN vx is dropped",
          not decide(float("nan"), 0.0, 0.0, pi, my).publish)
    check("an infinite yaw rate is dropped",
          not decide(0.58, 0.0, float("inf"), pi, my).publish)
    check("a NaN vy is dropped even though vy is not fused",
          not decide(0.58, float("nan"), 0.0, pi, my).publish)
    check("every drop names its reason",
          decide(float("nan"), 0.0, 0.0, pi, my).reason is not None)

    check("36 zeros is an ABSENT covariance",
          covariance_is_absent([0.0] * COVARIANCE_LENGTH))
    one = [0.0] * COVARIANCE_LENGTH
    one[7] = 1e-9
    check("one non-zero entry is a covariance to refuse, not overwrite",
          not covariance_is_absent(one))
    nan = [0.0] * COVARIANCE_LENGTH
    nan[0] = float("nan")
    check("a NaN in the incoming covariance is not absent",
          not covariance_is_absent(nan))
    short = False
    try:
        covariance_is_absent([0.0] * 9)
    except ValueError:
        short = True
    check("anything that is not 36 numbers is not a covariance", short)

    check("an unrotated mount is accepted", mount_rotation_is_zero((0, 0, 0)))
    check("any mount rotation is refused, to any size",
          not mount_rotation_is_zero((0.0, 0.0, 1e-9))
          and not mount_rotation_is_zero((0.1, 0.0, 0.0)))

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    # The denominator is derived from the checks that ran and never typed
    # beside them - nodes/wheel_odom_core.py's rule and its reason.
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the arithmetic behind m5-ver3's rf2o twist relay. "
                    "The node that uses it is nodes/rf2o_twist.py and it "
                    "is started only by `m5v3.sh start --rf2o`.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-Gazebo checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
