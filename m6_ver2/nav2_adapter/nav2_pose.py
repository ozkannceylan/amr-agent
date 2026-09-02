#!/usr/bin/env python3
"""nav2_pose.py - the believed pose, and the frame it is carried into.

    python3 m6_ver2/nav2_adapter/nav2_pose.py --selftest

NO ROS AND NO tf2 IN THIS FILE. The shell matches the two edges off the
shared `/tf` and hands this module two tuples; the composition, the
registration inverse, the staleness rule and the Odometry rows are all
data in and data out. That is what makes them testable at all: a
zero-order hold is a rule about WHICH SAMPLE, and a rule is only
testable where the samples are arguments.

THE TWO EDGES, AND WHY BOTH NAMES ARE MATCHED. Per AMR-DEC-006 there is
ONE shared `/tf` tree with per-truck PREFIXED frames, so the believed
pose of truck fN is

    map -> fN/odom          published by that truck's AMCL
      o  fN/odom -> fN/base_link   published by that truck's EKF

and `/tf` also carries three other trucks' edges plus whatever a costmap
decided to publish. Matching on a PARENT alone is not enough; the shell
matches on BOTH frame names, which is tools/sensor_evidence.py's rule
and drive_goal.on_tf's.

THE PARENT IS HELD, NOT INTERPOLATED. A running node has the LATEST
`map -> fN/odom` and the arriving `fN/odom -> fN/base_link`, and it
composes on arrival - which is all a running node can do. m5v3 measured
what that costs against an offline replay that interpolates the parent:
centimetres, and on a run whose distance-to-goal swings by metres that
was enough to move a watchdog mark across its threshold once. Neither
reading is wrong; the difference is the reconstruction, and this file
does the one a node can do and says so.

THE REGISTRATION INVERSE, AND WHY IT IS WORTH A FILE. AMCL answers in
the MAP frame - a grid that was BUILT, with its own rotation from the
building - and every consumer above the adapter (vda_orders.Progress,
the HMI's sketch, stations.py, route.py) works in m6 world coordinates.
The committed transform carries one to the other:

    p_map = R(theta) . p_world + t     (map_register derived it)
    p_world = R(-theta) . (p_map - t)  (this direction, the inverse)
    yaw_world = yaw_map - theta

AT A HALF TURN A ROTATION IS VERY NEARLY ITS OWN INVERSE. warehouse_v3's
theta is -179.813 deg, so applying the wrong one leaves every magnitude
EXACTLY right and puts the truck on the other side of the building - a
failure that looks like a localiser fault and is not one. So the
transform is not re-implemented here: evidence_core.MapFrame is the one
spelling on this track and this file delegates to it, having loaded it
through map_register.load_registration, which REFUSES a transform whose
.pgm has changed underneath it. The registration was fitted against
m6/gazebo/warehouse_ver3.sdf, which IS m6's live world, so the frame
closes.

THE GROUND-TRUTH FIREWALL. `/fN/gz/odom` is consumed by NOTHING in the
adapter or in the fleet path. What this file produces is the ESTIMATE,
published as `nav_msgs/Odometry` on `/fN/est/odom`, and the per-truck
config re-points the `topics.gz_odom` key at it so the untouched
vda_agent reads the estimate without knowing anything changed. The
consequence is the one that was wanted: `Progress` now counts on the
same odometry the adapter's ARRIVED reads - the same measurement made
twice, which is the invariant that made those two agree.
"""
import argparse
import collections
import math
import os
import sys

import _donors                                            # noqa: F401

import evidence_core as ec                                # noqa: E402
import map_core as mc                                     # noqa: E402
import map_register                                       # noqa: E402
from status_contract import is_stale                      # noqa: E402


class Nav2PoseError(ValueError):
    """A transform, a sample or a frame name this file will not guess at."""


#: ONE EDGE OF `/tf`, AS THE SHELL READ IT. `t` is the transform's own
#: stamp on the plant's clock - not its arrival time - because every
#: rate and every staleness budget on this track is scored on sim-time
#: stamps.
TfSample = collections.namedtuple("TfSample", "t x y yaw")

# ------------------------------ staleness ------------------------------

#: THE ESTIMATE'S OWN BUDGET, and it is nav_node.py's number for
#: nav_node.py's reason: odom at 20 Hz and scan at 10 Hz, so 0.5 s is
#: dead. Nothing fresh inside it and the pose is GONE - zeros flow, new
#: routes are refused "no pose", and `/auto/state` carries the note
#: "pose stale".
SENSOR_STALE_S = 0.5
#: AND IF IT PERSISTS A FULL SECOND, THE GOAL IS CANCELLED and the route
#: is HELD for resume. Two budgets and not one, because a dropped sample
#: is not a dead localiser: the first is a posture the truck rides out
#: at a standstill, the second is an admission that nav2 is steering off
#: a belief nobody is updating. It is twice the first, which is four
#: missed EKF publishes past the point of calling it stale.
POSE_CANCEL_S = 1.0

FRESH = "fresh"
STALE = "stale"
CANCEL = "cancel"


def pose_health(now_s, last_sample_s):
    """FRESH, STALE or CANCEL for the newest `fN/odom -> fN/base_link`.

    NEVER HAVING HAD A SAMPLE IS THE WORST CASE AND NOT THE BEST -
    status_contract.is_stale's rule, imported: silence is a demand, and
    a boot that had not yet heard from the EKF would otherwise look
    exactly like a healthy one.
    """
    if is_stale(last_sample_s, now_s, POSE_CANCEL_S):
        return CANCEL
    if is_stale(last_sample_s, now_s, SENSOR_STALE_S):
        return STALE
    return FRESH


# ---------------------------- the TF compose ----------------------------

def _checked(sample, what):
    try:
        row = TfSample(float(sample.t), float(sample.x), float(sample.y),
                       float(sample.yaw))
    except (AttributeError, TypeError, ValueError):
        raise Nav2PoseError(
            "the {} edge is {!r}, which is not a TfSample".format(
                what, sample))
    if not all(math.isfinite(value) for value in row):
        raise Nav2PoseError(
            "the {} edge carries a non-finite number ({!r}): a pose "
            "composed off one is a goal sent at random, and every "
            "distance measured against it is NaN for ever".format(
                what, tuple(row)))
    return row


def compose(map_odom, odom_base):
    """`map -> fN/base_link` from the two edges, or None.

    NONE IS NOT AN ERROR, IT IS THE BOOT POSTURE. Before AMCL's first
    answer there is no anchor and before the EKF's there is no child;
    the adapter's answer to that is IDLE with "localiser not ready", not
    a raised exception in a 20 Hz callback.

    The stamp carried out is the CHILD's: the anchor is held, so the
    moment this pose describes is the moment the fast edge arrived.
    """
    if map_odom is None or odom_base is None:
        return None
    anchor = _checked(map_odom, "map -> odom")
    child = _checked(odom_base, "odom -> base_link")
    cos_p, sin_p = math.cos(anchor.yaw), math.sin(anchor.yaw)
    return TfSample(
        t=child.t,
        x=anchor.x + cos_p * child.x - sin_p * child.y,
        y=anchor.y + sin_p * child.x + cos_p * child.y,
        yaw=ec.normalise_angle(anchor.yaw + child.yaw))


# -------------------------- the registration ---------------------------

def load_frame(path):
    """The committed transform, with its grid checked underneath it.

    Refused BY NAME on a missing or stale registration: a transform
    whose grid was rebuilt has a different rotation from the building,
    and a consumer that carried the old theta across the rebuild would
    be wrong by the difference with no way to find out.
    """
    try:
        record = map_register.load_registration(path)
        return ec.MapFrame.from_registration(record)
    except (OSError, mc.MapError, ec.EvidenceError) as exc:
        raise Nav2PoseError(
            "the committed registration at {} is not usable: {}".format(
                path, exc))


def to_world(frame, x, y, yaw=None):
    """A MAP-frame pose in m6 world coordinates.

    p_world = R(-theta) . (p_map - t), yaw_world = yaw_map - theta.
    DELEGATED AND NOT RE-DERIVED - evidence_core.MapFrame is the one
    spelling of this transform on this track, and two copies of a
    MECHANISM drift the way two copies of a VALUE do. See the header for
    what the half turn does to a second copy that got it backwards.
    """
    return frame.to_world(x, y, yaw)


def floor_margin_m(frame):
    """What the committed registration says it is worth, in metres.

    THE SAME FIGURE `floor_sentence` PRINTS, as a number. It is the
    registration's MAX residual against the building, and it is the
    widest two beliefs of one truck may honestly disagree by: the
    adapter reads the estimate through this transform and nav2 reads
    AMCL's map pose directly, so a boundary they are both checking at
    0.25 m is a boundary they can straddle (nav2_watch.arrival_is_short,
    defect D6).

    A TRANSFORM THAT STATES NO RESIDUAL IS WORTH NOTHING HERE, and says
    so with a zero rather than with a guess - which restores exactly the
    behaviour that had no margin at all.
    """
    residual = getattr(frame, "residual_max_m", None)
    return 0.0 if residual is None else abs(float(residual))


def floor_sentence(frame):
    """The sentence every absolute figure through this frame is read with.

    The registration's own residual against the building: no error at or
    below the MAX is a measurement of the localiser. Carried so a print
    site has it in hand instead of looking it up again.
    """
    return frame.floor()


# ------------------------- the Odometry message -------------------------

def odometry_rows(stamp_s, world_pose, body_twist, frame_id,
                  child_frame_id):
    """`nav_msgs/Odometry`'s fields as plain dicts, in WORLD coordinates.

    `frame_id` AND `child_frame_id` ARE REQUIRED ARGUMENTS. Per
    AMR-DEC-006 the frames are per-truck prefixed and the world frame's
    name is a deployment fact, so this file does not know one and will
    not invent one - a pure module that defaulted a frame name would be
    the one place a rename could pass silently.

    THE TWIST IS THE EKF's BODY VELOCITY AND NOT A DIFFERENCE OF POSES.
    vda_agent's `driving` flag reads it; a differenced estimate would
    make a standing truck look alive on localisation noise, and the
    fleet would believe an order was progressing.
    """
    for name, value in (("frame_id", frame_id),
                        ("child_frame_id", child_frame_id)):
        if not value:
            raise Nav2PoseError(
                "{} is {!r}: the estimate is published on a shared /tf "
                "tree with per-truck prefixed frames (AMR-DEC-006), so "
                "an unnamed frame is a message four trucks would "
                "answer to".format(name, value))
    try:
        x, y, yaw = (float(world_pose[0]), float(world_pose[1]),
                     float(world_pose[2]))
        vx, wz = float(body_twist[0]), float(body_twist[1])
        stamp = float(stamp_s)
    except (TypeError, ValueError, IndexError):
        raise Nav2PoseError(
            "the estimate is {!r} with twist {!r} at {!r}, which is not "
            "a pose".format(world_pose, body_twist, stamp_s))
    if not all(math.isfinite(value) for value in (x, y, yaw, vx, wz, stamp)):
        raise Nav2PoseError(
            "the estimate carries a non-finite number (pose {!r}, twist "
            "{!r}): it would reach vda_orders.Progress, which counts "
            "released nodes against it".format(
                (x, y, yaw), (vx, wz)))
    return {
        "header": {"stamp_s": stamp, "frame_id": frame_id},
        "child_frame_id": child_frame_id,
        "pose": {
            "position": {"x": x, "y": y, "z": 0.0},
            # YAW ONLY. The estimate is planar because the floor is: the
            # EKF is 2D (world_frame odom, two_d_mode) and a roll or
            # pitch here would be a number nothing measured.
            "orientation": {"x": 0.0, "y": 0.0,
                            "z": math.sin(yaw / 2.0),
                            "w": math.cos(yaw / 2.0)},
        },
        "twist": {"linear": {"x": vx, "y": 0.0, "z": 0.0},
                  "angular": {"x": 0.0, "y": 0.0, "z": wz}},
    }


#: The committed registration, relative to the repository root. Named
#: here so --selftest can find it; the runtime takes its path from the
#: per-truck config.
REGISTRATION = os.path.join(
    _donors.REPO, "m5_ver3", "maps", "warehouse_v3", "registration.yaml")


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_nav2_adapter_pose.py is the real suite - it writes the
    inverse out longhand and compares, which is the check that matters
    at a half turn - and this is the version an operator can run on the
    rig, against the registration actually committed.
    """
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    anchor = TfSample(1.0, 1.0, 0.0, math.pi / 2.0)
    child = TfSample(1.37, 1.0, 0.0, 0.0)
    row = compose(anchor, child)
    check("the anchor rotates the child and then translates it",
          abs(row.x - 1.0) < 1e-12 and abs(row.y - 1.0) < 1e-12)
    check("the composed stamp is the CHILD's - the parent is held",
          row.t == 1.37)
    check("no anchor yet is the boot posture and not an error",
          compose(None, child) is None and compose(anchor, None) is None)
    try:
        compose(TfSample(1.0, float("nan"), 0.0, 0.0), child)
        check("a non-finite edge is refused by name", False)
    except Nav2PoseError:
        check("a non-finite edge is refused by name", True)

    try:
        frame = load_frame(REGISTRATION)
    except Nav2PoseError as exc:                          # pragma: no cover
        print("FAIL  the committed registration loads: {}".format(exc))
        return 1
    check("the committed registration loads with its grid verified "
          "(theta {:+.6f} rad)".format(frame.theta_rad), True)
    check("  {}".format(floor_sentence(frame)), True)

    spawn = (-17.0, 10.0, 3.14159)
    in_map = frame.to_map(*spawn)
    check("f1's spawn is map ({:+.6f}, {:+.6f}) yaw {:+.6f}".format(*in_map),
          abs(in_map[0] + 0.079305540) < 1e-9
          and abs(in_map[1] + 0.145762011) < 1e-9)
    back = to_world(frame, *in_map)
    check("and the inverse puts it back where the truck is",
          abs(back[0] - spawn[0]) < 1e-9 and abs(back[1] - spawn[1]) < 1e-9
          and abs(ec.normalise_angle(back[2] - spawn[2])) < 1e-9)

    theta, tx, ty = frame.theta_rad, frame.t_x_m, frame.t_y_m
    worst = 0.0
    for mx, my in ((0.0, 0.0), (12.5, -3.25), (-30.0, 18.0)):
        dx, dy = mx - tx, my - ty
        want = (math.cos(-theta) * dx - math.sin(-theta) * dy,
                math.sin(-theta) * dx + math.cos(-theta) * dy)
        got = to_world(frame, mx, my)
        worst = max(worst, abs(got[0] - want[0]), abs(got[1] - want[1]))
    check("the inverse IS R(-theta).(p - t) written out longhand "
          "({:.2e})".format(worst), worst < 1e-9)

    check("half a second of silence is a pose that is GONE",
          pose_health(10.0, 9.5) == STALE)
    check("a full second cancels the goal and holds the route",
          pose_health(10.0, 9.0) == CANCEL)
    check("a fresh sample is fresh", pose_health(10.0, 9.9) == FRESH)
    check("never having had one is the worst case, not the best",
          pose_health(10.0, None) == CANCEL)

    rows = odometry_rows(12.5, spawn, (-0.300, -0.050), "map",
                         "f1/base_link")
    quat = rows["pose"]["orientation"]
    yaw = math.atan2(2.0 * quat["w"] * quat["z"],
                     1.0 - 2.0 * quat["z"] ** 2)
    check("the estimate goes out as a world pose and a BODY twist",
          rows["pose"]["position"]["x"] == -17.0
          and rows["twist"]["linear"]["x"] == -0.300
          and abs(ec.normalise_angle(yaw - spawn[2])) < 1e-9)
    for bad, what in (
            (lambda: odometry_rows(0.0, (float("nan"), 0.0, 0.0),
                                   (0.0, 0.0), "map", "f1/base_link"),
             "a non-finite estimate"),
            (lambda: odometry_rows(0.0, (0.0, 0.0, 0.0), (0.0, 0.0), "",
                                   "f1/base_link"),
             "an unnamed frame"),
            (lambda: load_frame(REGISTRATION + ".missing"),
             "a registration that is not there")):
        try:
            bad()
            check("{} is refused by name".format(what), False)
        except Nav2PoseError:
            check("{} is refused by name".format(what), True)

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the TF composition, the registration inverse and "
                    "the staleness rule for m6_ver2's nav2 adapter. The "
                    "node that uses it is nav2_adapter_node.py.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-simulator checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
