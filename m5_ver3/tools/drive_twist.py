#!/usr/bin/env python3
"""drive_twist.py - drive the COMMAND PATH, and score what came out of it.

    python3 m5_ver3/tools/drive_twist.py describe --profile corner_creep
    python3 m5_ver3/tools/drive_twist.py record   --profile straight
    python3 m5_ver3/tools/drive_twist.py analyse                # no ROS

WHAT IT IS FOR. F4 Task 1 builds a line - Nav2's controller, a velocity
smoother, a tricycle converter, two motor terminals - and every claim
about it has to be measured with no Nav2 in the room, or the measurement
is about the planner as well. So this publishes a config-tabled TWIST
PROFILE into the top of that line and records what comes out of every
joint of it, including the plant's own answer.

    topics.cmd_vel          <- this file publishes
    topics.speed_limit      <- this file publishes (the envelope demo)
      topics.cmd_vel_smoothed   -> recorded
      topics.steer_cmd          -> recorded  (the terminal, ROS side)
      topics.traction_cmd       -> recorded  (the terminal, ROS side)
      topics.joint_state        -> recorded  (what the AXES did)
      topics.odom_ground_truth  -> recorded  (what the TRUCK did)

WHY IT IS NOT tools/drive_route.py WITH A SECOND SHAPE OF ROW. That file
addresses the two motor terminals ON THE GZ SIDE and imports no rclpy at
all - that is what its whole header is about and what lets it drive a
plant with no ROS node running. A twist profile is a ROS publisher by
construction: it enters the chain above a lifecycle node and a converter,
in a different message type and a different unit. Bolting it on would put
an rclpy import at the top of the one driving tool that does not need
one. config.yaml's twist_route: block carries the same argument.

THE TWO FILES ARE STILL SIBLINGS AND SHARE EVERY IDIOM: a config-tabled
profile, the plant's own clock, refusals before the first command, and a
standing zero on every exit path including a refusal partway through.

  AND THE TABLE IS REFUSED RATHER THAN CLAMPED, which is exactly the line
  config.yaml's vehicle.steer_limit_rad comment draws. The CONVERTER
  clamps, because it is taking live commands from a stack and has to make
  one of them legal; this is reading a table somebody wrote down, and a
  table that asks for something the converter would have to clamp is a
  table to correct. A row that WANTS a clamp says `expect_clamp` and is
  then allowed exactly that one.

WHAT IT MEASURES, AND IT IS THE COMMAND PATH RATHER THAN THE PLANT.
tools/sensor_evidence.py already scores the ESTIMATE against the ground
truth and its tables are about estimation; nothing it records touches
`/cmd_vel*` or either terminal. What this scores is the four things only
a command path can get wrong:

  THE CONVERSION, live. Every settled sample's (steer, tread) is put back
  through the forward model and compared with the smoothed twist that
  produced it. A residual here is the converter disagreeing with its own
  arithmetic on the wire, which no unit test can see.
  THE SLEW. The largest steer rate and tread acceleration the terminals
  actually carried, against the limits config.yaml configures.
  THE DELIVERY. What the truck did, from ground truth, against what was
  commanded - the F1.5 delivered-fraction instrument moved up one layer.
  THE SPEED LIMIT. What the traction terminal carried before, during and
  after a nav2_msgs/SpeedLimit stood on topics.speed_limit.

WHAT LEAVING IT IS. Every exit path publishes a ZERO twist and LIFTS any
speed limit it set, and then waits for the converter's own ramp to reach
the terminal. That is not politeness on either count: model.sdf's
JointController holds its last command for ever, and a speed limit left
standing on the graph would silently halve the next run on this stack
without appearing in its table.
  NEITHER IS A BRAKE FOR A SAFETY PURPOSE and nothing here is a safety
  function. The nav2 collision monitor - which this phase does not run -
  "does not provide hard real-time safety certifications" and does not
  replace a safety-rated PLC. It complements the F-PLC; it is not the
  F-PLC. The same sentence governs topics.speed_limit.

IT DRIVES A LIVE STACK AND IT DOES NOT START ONE. m5v3.sh owns bringup;
this attaches to whatever is up on this domain, exactly as
tools/rtf_probe.sh and tools/drive_route.py do.

WHY THE ROS IMPORTS ARE INSIDE record(). `analyse` and `describe` need no
ROS at all and run on the Windows python the owner runs pytest under -
which is tools/sensor_evidence.py's own split, and the reason
tests/test_drive_twist.py can reach the arithmetic below.
"""
import argparse
import collections
import datetime
import hashlib
import math
import os
import sys

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in (_HERE, os.path.normpath(os.path.join(_HERE, os.pardir, "nodes"))):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

import _common                                        # noqa: E402
import cmd_vel_tricycle_core as core                   # noqa: E402
import evidence_core as ec                             # noqa: E402

TOOL = "drive_twist"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.ros_domain_id",
    "topics.cmd_vel", "topics.cmd_vel_smoothed", "topics.speed_limit",
    "topics.steer_cmd", "topics.traction_cmd", "topics.joint_state",
    "topics.odom_ground_truth",
    "vehicle.wheelbase_m", "vehicle.wheel_radius_m",
    "vehicle.steer_limit_rad", "vehicle.steer_rate_limit_radps",
    "wheel_odom.steer_joint_name", "wheel_odom.drive_joint_name",
    "navcmd.rate_hz", "navcmd.speed_max_mps", "navcmd.accel_mps2",
    "navcmd.steer_command_limit_rad", "navcmd.creep_speed_mps",
    "navcmd.zero_speed_mps", "navcmd.yawrate_refusal_radps",
    "smoother.params_file", "smoother.node_name",
    "twist_route.clock_timeout_s", "twist_route.chain_timeout_s",
    "twist_route.profiles",
    "evidence.dir", "evidence.wait_first_s", "evidence.min_samples",
    "evidence.corner.settle_s", "evidence.corner.window_s",
    "paths.traction_file",
)

#: One row of a twist profile. `speed_limit_mps` is None where the row
#: says nothing about the envelope, which is a DIFFERENT instruction from
#: "lift it": a table that re-published `0.0` on every row would be
#: exercising the interface once per segment rather than where it says.
Segment = collections.namedtuple(
    "Segment", "hold_s v_mps w_radps speed_limit_mps expect_clamp")

#: The streams a session carries, and the columns each one keeps.
STREAMS = collections.OrderedDict((
    ("cmd_vel", ("t_s", "v_mps", "w_radps")),
    ("cmd_vel_smoothed", ("t_s", "v_mps", "w_radps")),
    ("steer_cmd", ("t_s", "steer_rad")),
    ("traction_cmd", ("t_s", "wheel_radps")),
    ("joint_state", ("t_s", "steer_rad", "drive_radps")),
    ("ground_truth", ("t_s", "x", "y", "yaw", "vx", "wz")),
))


# ======================================================================
# the table, and what it is checked against before anything is published
# ======================================================================

def limits(cfg):
    """Every ceiling the converter enforces, in one record.

    READ FROM config.yaml AND DERIVED BY THE CORE, so this bench and the
    node it drives cannot disagree about where the geometry stops. A
    second copy of tan(1.25)/1.05 here would be a bench that passed a
    table the node would clamp.
    """
    wheelbase_m = cfg.f("vehicle.wheelbase_m")
    return dict(
        wheelbase_m=wheelbase_m,
        wheel_radius_m=cfg.f("vehicle.wheel_radius_m"),
        steer_limit_rad=cfg.f("vehicle.steer_limit_rad"),
        steer_rate_limit_radps=cfg.f("vehicle.steer_rate_limit_radps"),
        steer_command_limit_rad=cfg.f("navcmd.steer_command_limit_rad"),
        curvature_max_1pm=core.curvature_max(
            cfg.f("navcmd.steer_command_limit_rad"), wheelbase_m),
        traction_max_mps=cfg.f("navcmd.speed_max_mps"),
        accel_mps2=cfg.f("navcmd.accel_mps2"),
        creep_speed_mps=cfg.f("navcmd.creep_speed_mps"),
        zero_speed_mps=cfg.f("navcmd.zero_speed_mps"),
        yawrate_refusal_radps=cfg.f("navcmd.yawrate_refusal_radps"))


def convert(lim, v, w):
    """One row through the converter's own arithmetic."""
    return core.twist_to_tricycle(
        v, w, wheelbase_m=lim["wheelbase_m"],
        steer_limit_rad=lim["steer_limit_rad"],
        curvature_max_1pm=lim["curvature_max_1pm"],
        traction_max_mps=lim["traction_max_mps"],
        creep_speed_mps=lim["creep_speed_mps"],
        zero_speed_mps=lim["zero_speed_mps"],
        yawrate_refusal_radps=lim["yawrate_refusal_radps"])


def read_profile(cfg, name):
    """The named profile, checked row by row before anything is driven.

    EVERY REFUSAL HAPPENS BEFORE THE FIRST COMMAND - drive_route.py's
    rule, for its reason: a bad row halfway down would otherwise be
    discovered with the truck already at cruise, and the operator's next
    problem would be a moving vehicle rather than a typo.
    """
    profiles = cfg.raw("twist_route.profiles")
    if not isinstance(profiles, dict) or name not in profiles:
        cfg.refuse("config.yaml defines twist_route.profiles." + name,
                   _common.CONFIG,
                   "it defines: {}".format(
                       ", ".join(sorted(profiles))
                       if isinstance(profiles, dict) else "<not a mapping>"))
    rows = profiles[name]
    if not isinstance(rows, list) or not rows:
        cfg.refuse("the profile is a non-empty list of segments",
                   _common.CONFIG,
                   "twist_route.profiles.{} reads {!r}".format(name, rows))

    lim = limits(cfg)
    out = []
    for i, row in enumerate(rows):
        where = "twist_route.profiles.{}[{}]".format(name, i)
        if not isinstance(row, dict):
            cfg.refuse("every segment is a mapping", _common.CONFIG,
                       "{} reads {!r}".format(where, row))
        try:
            hold_s = float(row["hold_s"])
            v = float(row["v_mps"])
            w = float(row["w_radps"])
        except (KeyError, TypeError, ValueError) as exc:
            cfg.refuse("every segment has numeric hold_s, v_mps and w_radps",
                       _common.CONFIG, "{} reads {!r}".format(where, row),
                       "the value that would not read: {}".format(exc))
        if hold_s <= 0.0:
            cfg.refuse("every segment holds for a positive time",
                       _common.CONFIG,
                       "{} holds for {} s".format(where, hold_s))
        limit = row.get("speed_limit_mps")
        if limit is not None:
            try:
                limit = float(limit)
            except (TypeError, ValueError):
                cfg.refuse("speed_limit_mps is a number where it is given",
                           _common.CONFIG,
                           "{} reads {!r}".format(where, row["speed_limit_mps"]))
            if limit < 0.0:
                cfg.refuse("speed_limit_mps is not negative", _common.CONFIG,
                           "{} asks for {:+.4f}".format(where, limit),
                           "nav2_msgs/SpeedLimit spells NO LIMIT as 0.0; a "
                           "negative value has no meaning on that message.")
        expect = str(row.get("expect_clamp", "")).strip().lower()
        if expect not in ("", "traction", "curvature"):
            cfg.refuse("expect_clamp names a clamp this node has",
                       _common.CONFIG,
                       "{} reads {!r}".format(where, expect),
                       "the two are 'traction' and 'curvature'.")

        # THE CEILINGS ARE A REFUSAL AND NOT A CLAMP. See the header.
        out_conv = convert(lim, v, w)
        if out_conv.refused:
            cfg.refuse("every segment is a command the converter can "
                       "execute", _common.CONFIG,
                       "{} asks for v={:+.6f} m/s, w={:+.6f} rad/s".format(
                           where, v, w),
                       out_conv.reason)
        if out_conv.curvature_clamped and expect != "curvature":
            cfg.refuse("every segment's curvature is inside the measured "
                       "ceiling", _common.CONFIG,
                       "{} asks for kappa = {:+.6f} 1/m (R {:.4f} m)".format(
                           where, w / v if v else float("inf"),
                           abs(v / w) if w else float("inf")),
                       "navcmd.steer_command_limit_rad puts the ceiling at "
                       "{:.6f} 1/m (R {:.4f} m).".format(
                           lim["curvature_max_1pm"],
                           1.0 / lim["curvature_max_1pm"]),
                       "The CONVERTER would clamp this, because it takes "
                       "live commands. A TABLE is",
                       "corrected instead - or it says expect_clamp: "
                       "curvature and means it.")
        if out_conv.traction_clamped and expect != "traction":
            cfg.refuse("every segment's tread speed is inside the measured "
                       "ceiling", _common.CONFIG,
                       "{} needs {:+.6f} m/s of tread (v / cos delta) "
                       "against a ceiling of {:.3f}".format(
                           where, v / math.cos(out_conv.steer_rad or 0.0),
                           lim["traction_max_mps"]),
                       "The CONVERTER would clamp this, CURVATURE "
                       "PRESERVING - the arc is unchanged",
                       "and the vehicle drives it slower. A TABLE says "
                       "expect_clamp: traction if it",
                       "means to observe that, and is corrected if it does "
                       "not.")
        if expect and not (out_conv.curvature_clamped
                           or out_conv.traction_clamped):
            cfg.refuse("a segment that expects a clamp gets one",
                       _common.CONFIG,
                       "{} says expect_clamp: {} and the converter clamps "
                       "nothing on it.".format(where, expect),
                       "A row that asks to observe a clamp and does not "
                       "produce one is a row whose",
                       "table has drifted away from the limits it was "
                       "written against.")
        out.append(Segment(hold_s, v, w, limit, expect or None))
    return out


def describe(cfg, name, segments):
    """The schedule, printed before it is driven and by `describe` alone.

    IT PRINTS WHAT THE CONVERTER WILL DO, not only what is asked for -
    through the converter's own arithmetic, so the two cannot disagree.
    The distances are NOMINAL: the smoother ramps into every step and the
    tyre slips, so what the truck covers is the ground truth's to report.
    """
    lim = limits(cfg)
    print("profile    {}".format(name))
    print("segments   {}".format(len(segments)))
    print("ceilings   tread |v_w| <= {:.3f} m/s, accel {:.3f} m/s^2, "
          "steer slew {:.3f} rad/s".format(
              lim["traction_max_mps"], lim["accel_mps2"],
              lim["steer_rate_limit_radps"]))
    print("           curvature |k| <= {:.6f} 1/m (R {:.4f} m), which is "
          "{:.4f} rad of".format(lim["curvature_max_1pm"],
                                 1.0 / lim["curvature_max_1pm"],
                                 lim["steer_command_limit_rad"]))
    print("           steer - MEASURED, inside the {:.4f} rad mechanical "
          "stop".format(lim["steer_limit_rad"]))
    print("")
    print("   #   hold_s   t_end_s      v_mps    w_rad_s     kappa    "
          "steer_rad   tread_mps  wheel_rad_s  note")
    t_end = 0.0
    # THE ENVELOPE IS CARRIED ACROSS ROWS, exactly as the node carries
    # it: a nav2_msgs/SpeedLimit stands until another one replaces it, so
    # a row that says nothing about the limit is driven UNDER whatever
    # the last row that spoke set. A table that reset it every row would
    # be exercising the interface once per segment rather than where it
    # says it does.
    standing = None
    for i, seg in enumerate(segments):
        t_end += seg.hold_s
        if seg.speed_limit_mps is not None:
            standing = core.speed_limit_mps(
                False, seg.speed_limit_mps, lim["traction_max_mps"])
        v, w = core.apply_speed_limit(seg.v_mps, seg.w_radps, standing)
        out = convert(lim, v, w)
        kappa = w / v if v else 0.0
        note = []
        if out.steer_rad is None:
            note.append("below creep: zero tread, steer HELD")
        if out.curvature_clamped:
            note.append("CURVATURE CLAMPED")
        if out.traction_clamped:
            note.append("tread clamped (arc unchanged)")
        if seg.speed_limit_mps is not None:
            note.append("speed limit {}".format(
                "LIFTED" if seg.speed_limit_mps == 0.0
                else "{:.3f} m/s".format(seg.speed_limit_mps)))
        elif standing is not None:
            note.append("under a standing {:.3f} m/s limit".format(standing))
        print("  {:2d}   {:6.3f}   {:7.3f}  {:+9.4f}  {:+9.4f}  {:+8.4f}   "
              "{:>9}   {:+9.4f}  {:+10.4f}  {}".format(
                  i, seg.hold_s, t_end, v, w, kappa,
                  "HOLD" if out.steer_rad is None
                  else "{:+.6f}".format(out.steer_rad),
                  out.wheel_mps,
                  core.wheel_rate_radps(out.wheel_mps, lim["wheel_radius_m"]),
                  ", ".join(note) or "-"))
    print("")
    print("sim time   {:.3f} s".format(t_end))
    print("           negative v_mps is FORWARD - forks first, model -x, "
          "the travel direction.")
    print("           A NEGATIVE STEER ANGLE IS DRIVER-LEFT, and while "
          "travelling forward it")
    print("           produces a POSITIVE w_radps: w = v_w sin(delta)/L "
          "has two negative")
    print("           factors, so the model's yaw goes UP. Left is world "
          "+y from the spawn.")
    return t_end


# ======================================================================
# the analysis. NO ROS BELOW THIS LINE.
# ======================================================================

def smoother_label(cfg):
    """What smoother this session was recorded behind, as key=value.

    READ OFF THE FILE ON DISK AND NOT OUT OF A RUNNING NODE. What binds a
    session is what was on disk when it ran, which is the same rule
    m5v3.sh's `loc=` label follows for the frozen map: a hash of the
    artifact, taken at the moment it was used.
    """
    path = os.path.join(_common.REPO, cfg.s("smoother.params_file"))
    with open(path, "rb") as handle:
        raw = handle.read()
    params = yaml.safe_load(raw.decode("utf-8"))
    params = params[cfg.s("smoother.node_name")]["ros__parameters"]
    return collections.OrderedDict((
        ("smoother_feedback", params.get("feedback", "UNKNOWN")),
        ("smoother_md5", hashlib.md5(raw).hexdigest()[:8]),
    ))


def session_dir(cfg, name):
    return os.path.join(_common.REPO, cfg.s("evidence.dir"), name)


def sessions_in(cfg):
    root = os.path.join(_common.REPO, cfg.s("evidence.dir"))
    if not os.path.isdir(root):
        return []
    return sorted(name for name in os.listdir(root)
                  if name.startswith("twist-")
                  and os.path.isdir(os.path.join(root, name)))


def load(cfg, session):
    """Every stream of one session, plus its labels."""
    path = session_dir(cfg, session)
    tables = {}
    for stream in STREAMS:
        tables[stream] = ec.read_csv(os.path.join(path, stream + ".csv"))
    with open(os.path.join(path, "session.txt"), encoding="utf-8") as handle:
        fields = ec.parse_state_file(handle.read())
    return tables, fields


def window(t, lo, hi):
    """The indices of `t` inside [lo, hi)."""
    return [i for i, value in enumerate(t) if lo <= value < hi]


def mean_over(table, name, indices):
    column = table.column(name)
    values = [column[i] for i in indices]
    return ec.mean(values) if values else float("nan")


def body_motion(table, indices):
    """Forward speed and yaw rate from the GROUND TRUTH POSE.

    DIFFERENCED FROM THE POSE AND NOT READ OFF THE TWIST, deliberately.
    The twist is recorded beside it and reported, but the pose is the
    reading this track already scores everything against - and a body
    speed derived from two positions and a heading cannot be a claim
    about which frame the publisher expressed a velocity in.
    """
    if len(indices) < 3:
        return float("nan"), float("nan")
    t = table.column("t_s")
    x, y = table.column("x"), table.column("y")
    yaw = ec.unwrap([table.column("yaw")[i] for i in indices])
    first, last = indices[0], indices[-1]
    dt = t[last] - t[first]
    if dt <= 0.0:
        return float("nan"), float("nan")
    speeds = []
    for a, b in zip(indices[:-1], indices[1:]):
        step = t[b] - t[a]
        if step <= 0.0:
            continue
        dx, dy = x[b] - x[a], y[b] - y[a]
        heading = 0.5 * (table.column("yaw")[a] + table.column("yaw")[b])
        # PROJECTED ON THE HEADING, so a body speed is signed the way
        # base_link's own linear.x is: forward travel - forks first - is
        # NEGATIVE, because model yaw 0 points the forks at world -x.
        speeds.append((dx * math.cos(heading) + dy * math.sin(heading)) / step)
    return (ec.mean(speeds) if speeds else float("nan"),
            (yaw[-1] - yaw[0]) / dt)


def ratio(delivered, commanded):
    if commanded == 0.0 or not math.isfinite(commanded):
        return float("nan")
    return delivered / commanded


def _ratio_text(delivered, commanded):
    """A ratio, or a dash where the denominator is a standstill.

    A DASH AND NOT A ZERO OR A nan. A segment commanded at rest has no
    ratio at all - dividing by it would print `inf` or `nan` in a column
    the reader is scanning for numbers near one, and both of those read
    as failures rather than as "not asked".
    """
    if not commanded or not math.isfinite(commanded):
        return "-"
    value = delivered / commanded
    return "-" if not math.isfinite(value) else "{:.4f}".format(value)


#: The worst thing one interval of a terminal stream did: the STEP it
#: carried, the interval it carried it over, the rate that implies and
#: when.
Worst = collections.namedtuple("Worst", "step dt rate at")


def max_step(t, values):
    """The largest |step| between consecutive samples of a series.

    THE STEP AND NOT THE RATE IS WHAT THE LIMITER CONTROLS, and reporting
    the rate alone reads as a violation where there is none. The ramp is
    `limit * dt` per TICK, with dt taken as one nominal period whatever
    the timer actually did (nodes/cmd_vel_tricycle.py caps it there -
    forklift_io.py's rule, and under-travel is the conservative
    direction). So a tick that fires 6 ms early still carries the full
    period's step, and dividing by the short interval reports a rate
    above the limit for a ramp that never exceeded it.
      BOTH ARE PRINTED, with the interval beside them, so the reader can
      see which is which rather than being told.
    """
    worst = Worst(0.0, float("nan"), 0.0, float("nan"))
    for a, b in zip(range(len(t) - 1), range(1, len(t))):
        dt = t[b] - t[a]
        if dt <= 0.0:
            continue
        step = abs(values[b] - values[a])
        if step > worst.step:
            worst = Worst(step, dt, step / dt, t[b])
    return worst


def round_trip(cfg, tables, windows):
    """The terminals, checked against the arithmetic that produced them.

    WHAT IT CHECKS ON THE WIRE. For every traction sample inside a
    settled window, the steer angle in force at that instant and the
    tread speed it carried are put back through tricycle_to_twist() -
    and compared with what nodes/cmd_vel_tricycle_core.py says that pair
    should have been, given the SMOOTHED twist that reached the node and
    the speed limit standing at the time. A residual here is the
    converter disagreeing with its own arithmetic somewhere between the
    callback and the terminal - a unit conversion, a stale held value, a
    message assembled from the wrong variable - and no test that calls
    the function directly can see any of it.

    IT IS THE CLAMPED TWIST AND NOT THE COMMANDED ONE, which is the whole
    difference between a round trip and a complaint. Where the converter
    clamps - the traction ceiling on a corner at cruise, the envelope on
    a limited segment - the terminal is DELIBERATELY not the conversion
    of what arrived, and comparing it against that would report the
    node's own design as an error of 0.2 m/s.

    ONLY SETTLED WINDOWS, because outside them the terminals carry the
    RAMP and not the conversion: the node's output is deliberately not
    the instantaneous answer while it is slewing towards it.
    """
    radius_m = cfg.f("vehicle.wheel_radius_m")
    wheelbase_m = cfg.f("vehicle.wheelbase_m")
    lim = limits(cfg)
    max_gap_s = 2.0 / cfg.f("navcmd.rate_hz")
    traction, steer = tables["traction_cmd"], tables["steer_cmd"]
    smoothed = tables["cmd_vel_smoothed"]
    rows = [(value, standing) for value in traction.column("t_s")
            for lo, hi, standing in windows if lo <= value < hi]
    if len(rows) < 3:
        return float("nan"), float("nan"), 0
    t = [value for value, _ in rows]
    try:
        wheel = ec.resample(traction.column("t_s"),
                            traction.column("wheel_radps"), t, max_gap_s)
        angle = ec.resample(steer.column("t_s"),
                            steer.column("steer_rad"), t, max_gap_s)
        got_v = ec.resample(smoothed.column("t_s"),
                            smoothed.column("v_mps"), t, max_gap_s)
        got_w = ec.resample(smoothed.column("t_s"),
                            smoothed.column("w_radps"), t, max_gap_s)
    except ec.EvidenceError:
        return float("nan"), float("nan"), 0
    worst_v = worst_w = 0.0
    for i, (_, standing) in enumerate(rows):
        v, w = core.apply_speed_limit(got_v[i], got_w[i], standing)
        want = convert(lim, v, w)
        # What the terminal ACTUALLY carried, read as a twist.
        was_v, was_w = core.tricycle_to_twist(angle[i], wheel[i] * radius_m,
                                              wheelbase_m)
        worst_v = max(worst_v, abs(was_v - want.v_mps))
        worst_w = max(worst_w, abs(was_w - want.w_radps))
    return worst_v, worst_w, len(rows)


def stop_metrics(cfg, tables, t_stop):
    """What the whole chain does when it is told to stop, from `t_stop`.

    THREE NUMBERS AND NOT ONE, because a stop is three different claims:
    when the TERMINAL reached zero (the command path), when the TRUCK
    reached rest (the plant), and how far it went in between (what a
    controller's look-ahead and a goal tolerance have to clear). The
    third is integrated from the ground-truth POSE, which is the only one
    of the three that a slipping tyre cannot flatter.

    IT IS THE HEADLINE F4 TASK 2 INHERITS. smoother.yaml predicts
    v^2 / 2a = 0.70 m from cruise; whether the chain delivers that is a
    measurement and not an arithmetic.
    """
    tread_zero_mps = 0.01
    rest_mps = 0.02
    radius_m = cfg.f("vehicle.wheel_radius_m")
    t = tables["traction_cmd"].column("t_s")
    tread = [radius_m * value
             for value in tables["traction_cmd"].column("wheel_radps")]
    at_zero = [a for a, b in zip(t, tread)
               if a >= t_stop and abs(b) < tread_zero_mps]
    # THE TREAD AT THE MOMENT OF THE STOP, AND IT IS NOT THE BODY SPEED.
    # The terminal ramps the WHEEL's tread; the truck carries the BODY's
    # v = v_w cos(delta). On a corner those differ by cos of the steer
    # angle - at the commanded lock, by a third - so a deceleration
    # computed from the body speed over the terminal's own ramp time
    # reads far below the configured limit for a ramp that ran at
    # exactly it. Both are reported.
    entry_tread = [b for a, b in zip(t, tread) if a >= t_stop]
    gt = tables["ground_truth"]
    gtt, x, y = gt.column("t_s"), gt.column("x"), gt.column("y")
    speeds = []
    for a, b in zip(range(len(gtt) - 1), range(1, len(gtt))):
        dt = gtt[b] - gtt[a]
        if dt <= 0.0:
            continue
        speeds.append((gtt[b], math.hypot(x[b] - x[a], y[b] - y[a]) / dt))
    at_rest = [a for a, b in speeds if a >= t_stop and b < rest_mps]
    moving = [(a, b) for a, b in speeds if a >= t_stop]
    entry = moving[0][1] if moving else float("nan")
    travelled = 0.0
    for a, b in zip(range(len(gtt) - 1), range(1, len(gtt))):
        if gtt[b] < t_stop or (at_rest and gtt[b] > at_rest[0]):
            continue
        travelled += math.hypot(x[b] - x[a], y[b] - y[a])
    return dict(entry_mps=entry,
                entry_tread_mps=abs(entry_tread[0]) if entry_tread
                else float("nan"),
                terminal_s=(at_zero[0] - t_stop) if at_zero else float("nan"),
                rest_s=(at_rest[0] - t_stop) if at_rest else float("nan"),
                travel_m=travelled if at_rest else float("nan"))


def analyse_session(cfg, session):
    """One session's tables, printed. Returns the settled rows."""
    tables, fields = load(cfg, session)
    profile = fields.get("profile", "")
    segments = read_profile(cfg, profile)
    lim = limits(cfg)
    settle_s = cfg.f("evidence.corner.settle_s")
    # THE SAME TWO NUMBERS THE CORNER INSTRUMENT USES, and they are not
    # copied here. evidence.corner.settle_s is what tools/
    # sensor_evidence.py discards while a held steer angle slews in, and
    # window_s is the MINIMUM steady state it will average over. A command
    # path has the same two problems - a ramp at the start of every
    # segment, and a figure that must not be read off three samples - so
    # it gets the same two answers rather than a second pair that could
    # drift away from them.
    window_s = cfg.f("evidence.corner.window_s")
    radius_m = lim["wheel_radius_m"]

    print("")
    print("=== {} ===".format(session))
    print("profile   {}".format(profile))
    for key in ("traction", "arm", "loc", "nav"):
        print("{:<9} {}".format(key, fields.get(key, "UNLABELLED")))
    for stream, table in tables.items():
        if table.n < cfg.i("evidence.min_samples"):
            raise ec.EvidenceError(
                "{}: {} recorded {} rows, under evidence.min_samples"
                .format(session, stream, table.n))

    t0 = float(fields["t0_s"])
    print("")
    print("  seg  window_s        commanded            smoothed         "
          "  terminal          achieved          DELIVERED (truth)      "
          "ratio")
    print("                     v_mps   w_rad_s     v_mps   w_rad_s   "
          "steer_rad  tread_mps  steer_rad  tread_mps     v_mps   w_rad_s"
          "     v      w")
    settled = []
    rows = []
    at = t0
    # THE ENVELOPE IS CARRIED ACROSS ROWS, exactly as the node carries it
    # and exactly as describe() prints it: a nav2_msgs/SpeedLimit stands
    # until another one replaces it.
    standing = None
    for i, seg in enumerate(segments):
        if seg.speed_limit_mps is not None:
            standing = core.speed_limit_mps(
                False, seg.speed_limit_mps, lim["traction_max_mps"])
        lo, hi = at + settle_s, at + seg.hold_s
        at += seg.hold_s
        if hi - lo < window_s:
            # A segment that leaves less than one window after its settle
            # has no steady state to average. Reported as a line rather
            # than as a number: a mean over three samples looks exactly
            # like a measurement.
            print("  {:3d}  (only {:.2f}s after the {:g}s settle, under "
                  "the {:g}s window - no steady state)".format(
                      i, max(hi - lo, 0.0), settle_s, window_s))
            continue
        settled.append((lo, hi, standing))
        gt = tables["ground_truth"]
        idx = window(gt.column("t_s"), lo, hi)
        v_truth, w_truth = body_motion(gt, idx)
        row = dict(
            seg=i, lo=lo, hi=hi,
            v_cmd=seg.v_mps, w_cmd=seg.w_radps,
            v_smooth=mean_over(tables["cmd_vel_smoothed"], "v_mps",
                               window(tables["cmd_vel_smoothed"]
                                      .column("t_s"), lo, hi)),
            w_smooth=mean_over(tables["cmd_vel_smoothed"], "w_radps",
                               window(tables["cmd_vel_smoothed"]
                                      .column("t_s"), lo, hi)),
            steer_term=mean_over(tables["steer_cmd"], "steer_rad",
                                 window(tables["steer_cmd"].column("t_s"),
                                        lo, hi)),
            tread_term=radius_m * mean_over(
                tables["traction_cmd"], "wheel_radps",
                window(tables["traction_cmd"].column("t_s"), lo, hi)),
            steer_joint=mean_over(tables["joint_state"], "steer_rad",
                                  window(tables["joint_state"]
                                         .column("t_s"), lo, hi)),
            tread_joint=radius_m * mean_over(
                tables["joint_state"], "drive_radps",
                window(tables["joint_state"].column("t_s"), lo, hi)),
            v_truth=v_truth, w_truth=w_truth)
        row["v_ratio"] = ratio(v_truth, seg.v_mps)
        row["w_ratio"] = ratio(w_truth, seg.w_radps)
        rows.append(row)
        print("  {seg:3d}  {lo:6.2f}-{hi:5.2f}  {v_cmd:+8.4f} {w_cmd:+9.4f}  "
              "{v_smooth:+8.4f} {w_smooth:+9.4f}  {steer_term:+9.5f} "
              "{tread_term:+9.4f}  {steer_joint:+9.5f} {tread_joint:+9.4f}  "
              "{v_truth:+8.4f} {w_truth:+9.4f}  {v_ratio:5.3f} "
              "{w_ratio:6.3f}".format(**row))

    # ---- WHAT THE COMMAND PATH ITSELF DID, SEPARATED FROM THE TYRE ----
    #
    # FOUR RATIOS AND NOT ONE, because "delivered / commanded" folds four
    # different things into one number and only the first of them is this
    # phase's subject:
    #   terminal / commanded   the COMMAND PATH - the smoother, the
    #                          converter and the bridge, end to end
    #   achieved / terminal    model.sdf's JointController tracking the
    #                          order it was given
    #   delivered / achieved   THE TYRE, which is F1.5's subject and not
    #                          this one's
    #   delivered / commanded  the product, which is what a controller
    #                          upstream will experience
    print("")
    print("  seg   terminal/cmd   achieved/term   delivered/achieved   "
          "delivered/cmd      what it separates")
    for row in rows:
        print("  {:3d}   {:>10}   {:>13}   {:>18}   {:>13}      {}".format(
            row["seg"],
            _ratio_text(row["tread_term"], row["v_cmd"] and row["v_cmd"]
                        / math.cos(row["steer_term"] or 0.0)),
            _ratio_text(row["tread_joint"], row["tread_term"]),
            _ratio_text(row["v_truth"], row["tread_joint"]
                        * math.cos(row["steer_joint"] or 0.0)),
            _ratio_text(row["v_truth"], row["v_cmd"]),
            "the path | the controller | the tyre | the product"
            if row is rows[0] else ""))

    worst_v, worst_w, n = round_trip(cfg, tables, settled)
    tick_v = lim["accel_mps2"] / cfg.f("navcmd.rate_hz")
    tick_w = tick_v * lim["curvature_max_1pm"]
    print("")
    print("  conversion round trip over {} settled terminal samples: "
          "worst |dv| {:.3e} m/s, worst |dw| {:.3e} rad/s".format(
              n, worst_v, worst_w))
    print("    the bound is ONE TICK OF THE RAMP and not zero: the "
          "terminals carry the")
    print("    ramp-limited image of the smoothed twist, so a residual "
          "up to {:.4f} m/s".format(tick_v))
    print("    and {:.4f} rad/s is the limiter doing its job. {} and {}."
          .format(tick_w,
                  "dv INSIDE" if worst_v <= tick_v else "dv OUTSIDE",
                  "dw INSIDE" if worst_w <= tick_w else "dw OUTSIDE"))
    # ---- AND THE STOP, which is the figure a controller inherits ----
    at = t0
    stop_at = None
    for seg in segments:
        if seg.v_mps == 0.0 and seg.w_radps == 0.0 and at > t0:
            stop_at = at
            break
        at += seg.hold_s
    if stop_at is not None:
        stop = stop_metrics(cfg, tables, stop_at)
        print("  the stop, commanded at t={:.2f} from {:.4f} m/s of body "
              "speed ({:.4f} m/s of tread):".format(
                  stop_at, stop["entry_mps"], stop["entry_tread_mps"]))
        print("    terminal reached zero  {:.2f} s later  ({:.3f} m/s^2 of "
              "TREAD against the {:.3f} configured)".format(
                  stop["terminal_s"],
                  stop["entry_tread_mps"] / stop["terminal_s"]
                  if stop["terminal_s"] else float("nan"),
                  lim["accel_mps2"]))
        print("    THE TRUCK reached rest {:.2f} s later, after {:.3f} m "
              "(v^2/2a predicts {:.3f} m)".format(
                  stop["rest_s"], stop["travel_m"],
                  stop["entry_mps"] ** 2 / (2.0 * lim["accel_mps2"])))

    steer = max_step(tables["steer_cmd"].column("t_s"),
                     tables["steer_cmd"].column("steer_rad"))
    tread = [radius_m * value
             for value in tables["traction_cmd"].column("wheel_radps")]
    treads = max_step(tables["traction_cmd"].column("t_s"), tread)
    period_s = 1.0 / cfg.f("navcmd.rate_hz")
    print("  slew at the terminals, worst single interval:")
    print("    steer  step {:.6f} rad over {:.4f} s = {:.4f} rad/s   "
          "(ramp {:.6f} rad/tick, limit {:.3f} rad/s) at t={:.2f}".format(
              steer.step, steer.dt, steer.rate,
              lim["steer_rate_limit_radps"] * period_s,
              lim["steer_rate_limit_radps"], steer.at))
    print("    tread  step {:.6f} m/s over {:.4f} s = {:.4f} m/s^2  "
          "(ramp {:.6f} m/s/tick, limit {:.3f} m/s^2) at t={:.2f}".format(
              treads.step, treads.dt, treads.rate,
              lim["accel_mps2"] * period_s, lim["accel_mps2"], treads.at))
    if any(seg.speed_limit_mps is not None for seg in segments):
        print("  speed limit, at the TRACTION TERMINAL:")
        at = t0
        for i, seg in enumerate(segments):
            lo, hi = at + settle_s, at + seg.hold_s
            at += seg.hold_s
            if hi - lo < window_s:
                continue
            idx = window(tables["traction_cmd"].column("t_s"), lo, hi)
            if not idx:
                continue
            print("    seg {:2d}  limit {:>8}  tread {:+.4f} m/s".format(
                i,
                "none" if seg.speed_limit_mps is None
                else ("LIFTED" if seg.speed_limit_mps == 0.0
                      else "{:.3f}".format(seg.speed_limit_mps)),
                radius_m * mean_over(tables["traction_cmd"], "wheel_radps",
                                     idx)))
    return rows


def analyse(cfg, names):
    names = names or sessions_in(cfg)
    if not names:
        cfg.refuse("there is a recorded twist session to analyse",
                   os.path.join(_common.REPO, cfg.s("evidence.dir")),
                   "nothing there is named twist-*.",
                   "record one: python3 {} record --profile straight".format(
                       os.path.relpath(os.path.abspath(__file__),
                                       _common.REPO)))
    print("=== m5v3 command path ===")
    for name in names:
        try:
            analyse_session(cfg, name)
        except ec.EvidenceError as exc:
            cfg.refuse("session {} is readable".format(name),
                       session_dir(cfg, name), str(exc))
    return 0


# ======================================================================
# the drive. ROS BELOW THIS LINE, and it is imported inside record().
# ======================================================================

def record(cfg, args):
    """One complete run: subscribe, drive, write the CSVs."""
    try:
        import rclpy
        from geometry_msgs.msg import Twist
        from nav2_msgs.msg import SpeedLimit
        from nav_msgs.msg import Odometry
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from sensor_msgs.msg import JointState
        from std_msgs.msg import Float64
    except ImportError as exc:
        cfg.refuse("rclpy and nav2_msgs are importable",
                   _common.CONFIG + " (paths.ros_setup)",
                   "python3 could not import what this bench needs: "
                   "{}".format(exc),
                   "it runs INSIDE WSL with /opt/ros/jazzy sourced. "
                   "`analyse` needs neither.")

    segments = read_profile(cfg, args.profile)
    print("=== m5v3 twist route ===")
    total_s = describe(cfg, args.profile, segments)
    print("")

    # THE LABEL CHAIN, AND A RUN WITHOUT ONE IS NOT RECORDED. It is
    # tools/sensor_evidence.py's rule and its reason: a session that
    # cannot say which plant, which estimator and which localiser it was
    # taken on is a row that would sit in the wrong table looking exactly
    # like one of them.
    state_path = os.path.join(_common.REPO, cfg.s("paths.traction_file"))
    if not os.path.isfile(state_path):
        cfg.refuse("the stack said which plant it is", state_path,
                   "there is no state file, so this stack was not started "
                   "by 'm5v3.sh start'.",
                   "An unlabelled session is worse than none.")
    with open(state_path, encoding="utf-8") as handle:
        state = ec.parse_state_file(handle.read())
    for key in ("traction", "arm", "loc", "nav"):
        if key not in state:
            cfg.refuse("the state file carries a {}= line".format(key),
                       state_path,
                       "it was written by a script older than the label "
                       "this session needs.")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    session = "twist-{}-{}".format(args.profile, stamp)
    path = session_dir(cfg, session)
    os.makedirs(path)
    print("session    {}".format(path))

    rclpy.init(args=None)
    node = Node("m5v3_drive_twist")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    qos = QoSProfile(depth=10)
    captured = collections.OrderedDict(
        (stream, []) for stream in STREAMS)
    steer_joint = cfg.s("wheel_odom.steer_joint_name")
    drive_joint = cfg.s("wheel_odom.drive_joint_name")

    def now_s():
        return node.get_clock().now().nanoseconds * 1e-9

    def stamp_s(header):
        return float(header.stamp.sec) + float(header.stamp.nanosec) * 1e-9

    def on_smoothed(msg):
        captured["cmd_vel_smoothed"].append(
            (now_s(), msg.linear.x, msg.angular.z))

    def on_steer(msg):
        captured["steer_cmd"].append((now_s(), msg.data))

    def on_traction(msg):
        captured["traction_cmd"].append((now_s(), msg.data))

    def on_joints(msg):
        names = list(msg.name)
        if steer_joint not in names or drive_joint not in names:
            return
        si, di = names.index(steer_joint), names.index(drive_joint)
        if si >= len(msg.position) or di >= len(msg.velocity):
            return
        captured["joint_state"].append(
            (stamp_s(msg.header), msg.position[si], msg.velocity[di]))

    def on_truth(msg):
        q = msg.pose.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        captured["ground_truth"].append(
            (stamp_s(msg.header), msg.pose.pose.position.x,
             msg.pose.pose.position.y, yaw,
             msg.twist.twist.linear.x, msg.twist.twist.angular.z))

    node.create_subscription(Twist, cfg.s("topics.cmd_vel_smoothed"),
                             on_smoothed, qos)
    node.create_subscription(Float64, cfg.s("topics.steer_cmd"), on_steer, qos)
    node.create_subscription(Float64, cfg.s("topics.traction_cmd"),
                             on_traction, qos)
    node.create_subscription(JointState, cfg.s("topics.joint_state"),
                             on_joints, qos)
    node.create_subscription(Odometry, cfg.s("topics.odom_ground_truth"),
                             on_truth, qos)
    pub_cmd = node.create_publisher(Twist, cfg.s("topics.cmd_vel"), qos)
    pub_limit = node.create_publisher(SpeedLimit, cfg.s("topics.speed_limit"),
                                      qos)

    def spin_until(predicate, budget_s, what, owner, *lines):
        """Spin the node until `predicate`, or refuse by name.

        ON THE MACHINE'S CLOCK AND NOT THE PLANT'S. What is being waited
        for here is a MESSAGE, and a plant that has stopped publishing
        has also stopped its clock - a budget measured on that clock
        would never expire.
        """
        import time as _time
        deadline = _time.monotonic() + budget_s
        while not predicate():
            if _time.monotonic() > deadline:
                cfg.refuse(what, owner, *lines)
            rclpy.spin_once(node, timeout_sec=0.05)

    wait_s = cfg.f("evidence.wait_first_s")
    spin_until(lambda: bool(captured["ground_truth"])
               and bool(captured["joint_state"]), wait_s,
               "every recorded stream delivered a message within "
               "{:g}s".format(wait_s),
               "{} and {}".format(cfg.s("topics.odom_ground_truth"),
                                  cfg.s("topics.joint_state")),
               "the plant's own two channels are what this waits on; the "
               "three command-path",
               "topics publish NOTHING until this bench commands, which "
               "is what the chain",
               "check below is for.",
               "is the stack up? 'bash m5_ver3/m5v3.sh status'")
    spin_until(lambda: now_s() > 0.0, wait_s,
               "the plant's clock reached this bench",
               "{} (config.yaml topics.clock, bridged)".format("/clock"),
               "use_sim_time is set and the ROS clock is still at zero, "
               "so nothing has",
               "bridged /clock onto this domain.")

    # THE CHAIN, BEFORE THE PROFILE. One zero twist and the smoother's
    # answer to it: if nothing comes back the smoother is not ACTIVE or
    # not subscribed, and driving on regardless would be measuring an
    # open circuit for the length of the profile.
    zero = Twist()
    pub_cmd.publish(zero)
    chain_s = cfg.f("twist_route.chain_timeout_s")
    spin_until(lambda: (pub_cmd.publish(zero) or
                        bool(captured["cmd_vel_smoothed"])), chain_s,
               "the smoother answered a command within {:g}s".format(chain_s),
               "{} -> {}".format(cfg.s("topics.cmd_vel"),
                                 cfg.s("topics.cmd_vel_smoothed")),
               "a zero twist was published and nothing came back. The "
               "smoother is either not",
               "ACTIVE or not subscribed to this address:",
               "  ros2 lifecycle get /velocity_smoother",
               "  ros2 topic info {}".format(cfg.s("topics.cmd_vel")))

    # EVERY STREAM STARTS EMPTY AGAIN at t0, so the chain check above is
    # not in the table. It was a command, and a command that is not in
    # the profile has no business in the profile's own record.
    for stream in captured:
        captured[stream] = []
    t0 = now_s()
    print("clock      {} reads {:.3f} s of sim time".format("/clock", t0))
    print("")

    period_s = 1.0 / cfg.f("navcmd.rate_hz")
    next_pub = [0.0]
    limit_now = [None]

    def set_limit(value):
        if value == limit_now[0]:
            return
        limit_now[0] = value
        msg = SpeedLimit()
        msg.header.frame_id = ""
        msg.percentage = False
        msg.speed_limit = float(value or 0.0)
        pub_limit.publish(msg)
        print("           speed limit -> {}".format(
            "LIFTED (0.0 = no limit)" if not value
            else "{:.3f} m/s".format(value)))

    try:
        at = t0
        for i, seg in enumerate(segments):
            deadline = at + seg.hold_s
            at = deadline
            if seg.speed_limit_mps is not None:
                set_limit(seg.speed_limit_mps)
            msg = Twist()
            msg.linear.x = seg.v_mps
            msg.angular.z = seg.w_radps
            print("  seg {:2d}  v {:+7.4f} m/s  w {:+8.4f} rad/s  until "
                  "t = {:.3f}".format(i, seg.v_mps, seg.w_radps, deadline))
            sys.stdout.flush()
            while now_s() < deadline:
                # ON THE PLANT'S CLOCK, AT THE COMMAND RATE, and not as
                # fast as the executor will go. spin_once() returns
                # IMMEDIATELY when there is work waiting - and on this
                # stack there always is, because the joint state arrives
                # 493 times a second - so a loop that published on every
                # pass put 24 529 twists onto /cmd_vel in 23 s of a
                # profile that asks for 460. What that measures is the
                # smoother's input queue, not the command path.
                now = now_s()
                if now >= next_pub[0]:
                    next_pub[0] = now + period_s
                    pub_cmd.publish(msg)
                    # RECORDED AT EVERY PUBLISH AND NOT ONCE PER SEGMENT.
                    # What the table says and what reached the wire are
                    # two different claims, and the second one is what
                    # the smoothed stream has to be read against.
                    captured["cmd_vel"].append((now, seg.v_mps, seg.w_radps))
                rclpy.spin_once(node, timeout_sec=0.2 * period_s)
        print("")
        print("profile complete at t = {:.3f} s of sim time".format(at))
    finally:
        # THE LAST THING THAT HAPPENS, WHATEVER HAPPENED. A refusal, a
        # Ctrl-C and a clean finish all leave a zero twist and NO speed
        # limit - see the header for why the second one matters as much
        # as the first.
        set_limit(0.0)
        stop = Twist()
        end = now_s() + 2.0
        next_pub[0] = 0.0
        while now_s() < end:
            now = now_s()
            if now >= next_pub[0]:
                next_pub[0] = now + period_s
                pub_cmd.publish(stop)
            rclpy.spin_once(node, timeout_sec=0.2 * period_s)
        for stream, columns in STREAMS.items():
            with open(os.path.join(path, stream + ".csv"), "w",
                      encoding="utf-8", newline="") as handle:
                handle.write(",".join(columns) + "\n")
                for row in captured[stream]:
                    handle.write(",".join(
                        "{!r}".format(value) if isinstance(value, str)
                        else "{:.9f}".format(value) for value in row) + "\n")
        lim = limits(cfg)
        with open(os.path.join(path, "session.txt"), "w",
                  encoding="utf-8") as handle:
            handle.write("kind=twist\n")
            handle.write("profile={}\n".format(args.profile))
            handle.write("t0_s={:.9f}\n".format(t0))
            handle.write("nominal_s={:.3f}\n".format(total_s))
            for key, value in state.items():
                handle.write("{}={}\n".format(key, value))
            for key in sorted(lim):
                handle.write("limit_{}={!r}\n".format(key, lim[key]))
            # WHICH SMOOTHER THIS RUN WAS TAKEN BEHIND, and it is the
            # traction label's own argument one layer up. Two runs of one
            # profile on one plant with one estimator, differing only in
            # smoother.yaml's `feedback`, produce CSVs of identical shape
            # and a session.txt that could not tell them apart - and the
            # A/B in EVIDENCE_NAV_V3.md 6 is exactly that pair. The MD5
            # is of the whole file, so any other parameter that moved
            # moves it too.
            for key, value in smoother_label(cfg).items():
                handle.write("{}={}\n".format(key, value))
            handle.write("recorded={}\n".format(
                datetime.datetime.now().isoformat()))
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
    for stream in STREAMS:
        print("  {:<18} {} rows".format(stream, len(captured[stream])))
    print("")
    print("analyse it:  python3 {} analyse {}".format(
        os.path.relpath(os.path.abspath(__file__), _common.REPO), session))
    return 0


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    profiles = cfg.raw("twist_route.profiles")
    parser = argparse.ArgumentParser(
        description="drive one of config.yaml's TWIST profiles through the "
                    "velocity smoother and the tricycle converter, and "
                    "score what came out at the plant's own terminals.",
        epilog="the profiles and every number in them live in "
               "m5_ver3/config.yaml under twist_route:.")
    sub = parser.add_subparsers(dest="command")
    names = sorted(profiles) if isinstance(profiles, dict) else []
    for verb, needs_profile in (("describe", True), ("record", True)):
        one = sub.add_parser(verb)
        if needs_profile:
            one.add_argument("--profile", required=True, choices=names)
    one = sub.add_parser("analyse")
    one.add_argument("session", nargs="*",
                     help="session directory names; all of them by default")
    args = parser.parse_args(argv)
    if args.command == "describe":
        describe(cfg, args.profile, read_profile(cfg, args.profile))
        return 0
    if args.command == "record":
        return record(cfg, args)
    if args.command == "analyse":
        return analyse(cfg, args.session)
    parser.print_help()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\ndrive_twist: interrupted.\n")
        sys.exit(130)
