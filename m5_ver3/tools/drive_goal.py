#!/usr/bin/env python3
"""drive_goal.py - send Nav2 a GOAL, and score what the truck did.

    python3 m5_ver3/tools/drive_goal.py describe --goal aisle_end
    python3 m5_ver3/tools/drive_goal.py record   --goal aisle_end
    python3 m5_ver3/tools/drive_goal.py analyse                # no ROS

WHAT IT IS FOR. F4 Task 2 puts a planner and a controller over a stack
that already knows where it is, and this is the instrument that says
what that closed loop delivered. It publishes ONE thing - a
`navigate_to_pose` goal - and records every joint of what came back:

    nav2's bt_navigator  <- this file sends ONE goal
      topics.cmd_vel            -> recorded  (the CONTROLLER's output)
      topics.cmd_vel_smoothed   -> recorded
      topics.steer_cmd          -> recorded  (the terminal, ROS side)
      topics.traction_cmd       -> recorded  (the terminal, ROS side)
      topics.odom_ground_truth  -> recorded  (what the TRUCK did)
      topics.tf: map -> odom    -> recorded  (the LOCALISER's edge)
      topics.tf: odom -> base   -> recorded  (the ESTIMATOR's edge)
      /plan                     -> recorded  (every plan, with its poses)
      the action's own feedback -> recorded

WHY IT IS NOT tools/drive_twist.py WITH A SECOND KIND OF PROFILE. That
file drives a TABLE: a list of twists somebody wrote down, published
open loop, with nothing on the stack reading a pose. This drives a GOAL,
and everything between the goal and the terminals is decided by a
planner and a controller reading the localiser's own output. The two
benches measure opposite things - one measures a path that cannot
respond, the other measures the response - and the sessions they write
carry different questions. They share every idiom: a config-tabled
subject, the plant's own clock, refusals before the first command, and a
label chain that refuses to record a run it cannot attribute.

WHAT IT MEASURES, AND EVERY FIGURE NAMES ITS INSTRUMENT:

  THE ARRIVAL, ABSOLUTELY. Where the truck ENDED, from the ground truth,
  against the goal pose in the building's own frame. And beside it,
  where the STACK BELIEVED it ended - `map` -> `base_link` composed off
  /tf and carried into the building by the committed registration, which
  is F3's own instrument (EVIDENCE_LOCALIZATION_V3.md 5). The two
  differ by the localisation error, and the goal checker only ever saw
  the second one.
  THE DEVIATION FROM THE PLAN. Every /plan is recorded with its poses,
  and each truth sample is scored against the plan that was standing at
  the time. This is the figure nav2 issue #5714 says Ackermann robots
  lose in turns, and on this vehicle every ordinary leg is a nav2
  REVERSE leg - so the defect is not a corner case here, it is the
  common case. F4 constraint 19: measured and recorded, not tuned
  around.
  THE PATH's OWN SMOOTHNESS. Total steer travel at the terminal, the
  worst steer step, the commanded curvature, and the number of CUSPS -
  a Reeds-Shepp path reverses at a cusp and this vehicle stops, slews
  the steer axis across and sets off the other way for each one.
  THE CONTROLLER'S FREQUENCY, off its own /cmd_vel stamps, against
  nav2.yaml's `controller_frequency`.
  THE REAL-TIME FACTOR, over the drive itself, with the whole stack up -
  which is not the same measurement tools/rtf_probe.sh makes on an idle
  one.
  THE JUMPS, AND WHAT THE CONTROLLER DID ABOUT THEM. Every step in
  `map` -> `odom` (evidence_core.tf_jumps, which counts CORRECTIONS and
  not re-broadcasts) with the controller's own response in the window
  after it. EVIDENCE_LOCALIZATION_V3.md 13.10 handed F4 those peaks as
  a budget; this is what they cost with a loop closed round them.

WHAT LEAVING IT IS. Every exit path CANCELS the goal if it is still
running and then publishes nothing at all - the controller's own
`publish_zero_velocity` leaves a standing zero on /cmd_vel, and
model.sdf's JointController holds its last command for ever. This file
never publishes a twist itself, on any path, because F4 constraint 18
says the command path has one publisher at a time and a bench that
raced the controller for it would be measuring the race.
  IT IS NOT A BRAKE FOR A SAFETY PURPOSE and nothing here is a safety
  function. The collision monitor - which this task does not run -
  "does not provide hard real-time safety certifications" and does not
  replace a safety-rated PLC. It complements the F-PLC; it is not the
  F-PLC.

IT DRIVES A LIVE STACK AND IT DOES NOT START ONE. m5v3.sh owns bringup;
this attaches to whatever is up on this domain, exactly as
tools/drive_twist.py, tools/rtf_probe.sh and tools/drive_route.py do -
and it REFUSES a stack whose state file says `nav=off`, because a goal
sent to a stack with no bt_navigator on it is a goal nothing will ever
answer.

WHY THE ROS IMPORTS ARE INSIDE record(). `analyse` and `describe` need
no ROS at all and run on the Windows python the owner runs pytest under,
which is sensor_evidence.py's own split and the reason
tests/test_drive_goal.py can reach the arithmetic below.
"""
import argparse
import collections
import datetime
import hashlib
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import evidence_core as ec                            # noqa: E402
import map_register                                   # noqa: E402

TOOL = "drive_goal"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.ros_domain_id",
    "topics.cmd_vel", "topics.cmd_vel_smoothed",
    "topics.steer_cmd", "topics.traction_cmd",
    "topics.odom_ground_truth", "topics.tf",
    "frames.map", "frames.odom", "frames.base_link",
    "vehicle.wheelbase_m", "vehicle.spawn.x", "vehicle.spawn.y",
    "vehicle.spawn.yaw",
    "map.dir", "map.name", "map.registration.file",
    "nav.params_file", "nav.goals", "nav.default_goal",
    "nav.goal_timeout_s", "nav.settle_s", "nav.prelude_s",
    "nav.analyse.arrival_window_s", "nav.analyse.at_rest_mps",
    "nav.analyse.jump_response_s", "nav.analyse.map_gap_s",
    "nav.analyse.cusp_speed_mps",
    "evidence.dir", "evidence.wait_first_s", "evidence.min_samples",
    "paths.traction_file",
)

#: nav2's own action name and its own plan topic. Neither is in
#: config.yaml, for topics.amcl_pose's reason: they are the SERVERS'
#: advertised names and this file is the only thing on this track that
#: says them.
NAV_ACTION = "navigate_to_pose"
PLAN_TOPIC = "/plan"

#: The streams a session carries, and the columns each keeps. `t_s` is
#: the PLANT's clock throughout; `t_wall` appears only where a figure
#: needs both (the real-time factor is the ratio of the two).
STREAMS = collections.OrderedDict((
    ("cmd_vel", ("t_s", "t_wall", "v_mps", "w_radps")),
    ("cmd_vel_smoothed", ("t_s", "v_mps", "w_radps")),
    ("steer_cmd", ("t_s", "steer_rad")),
    ("traction_cmd", ("t_s", "wheel_radps")),
    ("ground_truth", ("t_s", "x", "y", "yaw", "vx", "wz")),
    ("map_odom", ("t_s", "x", "y", "yaw")),
    ("odom_base", ("t_s", "x", "y", "yaw")),
    ("plan", ("t_s", "plan", "i", "x", "y", "yaw")),
    ("feedback", ("t_s", "distance_remaining", "navigation_time",
                  "recoveries")),
))

#: One goal, resolved. `pose_yaw` is what goes on the wire; `travel_yaw`
#: is what the table said and what a reader pictures.
Goal = collections.namedtuple(
    "Goal", "name x y travel_yaw pose_yaw repeat note")


# ----------------------------------------------------------------------
# the table
# ----------------------------------------------------------------------

def pose_yaw(travel_yaw_rad):
    """The base_link yaw that puts the FORKS along `travel_yaw_rad`.

    THE ONE PLACE THE HALF TURN IS ADDED, and it is a function so that
    exactly one thing on this track knows about it. This vehicle's forks
    are at model -x (gazebo/forklift_ver3/model.sdf: "yaw 0 points the
    forks at world -x, so the travel heading is yaw + pi"), so a pose
    that carries the direction of travel as its own yaw would arrive
    COUNTERWEIGHT-FIRST - with the nav lidar's 90 degree blind sector
    leading - and would still look like a successful goal from every
    angle a table has.
    """
    return ec.normalise_angle(float(travel_yaw_rad) + math.pi)


def read_goal(cfg, name):
    """One row of config.yaml's nav.goals, or a refusal naming them all."""
    goals = cfg.raw("nav.goals")
    if not isinstance(goals, dict) or not goals:
        cfg.refuse("config.yaml's nav.goals is a table of goals",
                   _common.CONFIG,
                   "it reads {!r}".format(goals))
    if name not in goals:
        cfg.refuse("nav.goals names the goal that was asked for",
                   _common.CONFIG + " (nav.goals)",
                   "there is no goal called {!r}. The table holds:".format(
                       name),
                   *["  {:<14} ({:>7}, {:>7})  {}".format(
                       key, row.get("x", "?"), row.get("y", "?"),
                       row.get("note", "")) for key, row in goals.items()])
    row = goals[name]
    for key in ("x", "y", "travel_yaw_rad", "repeat"):
        if key not in row:
            cfg.refuse("nav.goals.{} carries {}".format(name, key),
                       _common.CONFIG + " (nav.goals)",
                       "that row reads {!r}".format(row))
    travel = float(row["travel_yaw_rad"])
    return Goal(name=name, x=float(row["x"]), y=float(row["y"]),
                travel_yaw=travel, pose_yaw=pose_yaw(travel),
                repeat=int(row["repeat"]), note=str(row.get("note", "")))


def goal_in_map(cfg, goal):
    """The goal pose in the MAP frame, through the committed registration.

    THE SAME ARITHMETIC THAT SEEDS THE LOCALISER, and it is a call into
    map_register rather than a second copy for that reason. It verifies
    the registration against the grid on disk on the way past, so a goal
    is never carried into the map by a transform that no longer belongs
    to it (F3 constraint 16).
    """
    path = os.path.join(_common.REPO, cfg.s("map.dir"), cfg.s("map.name"),
                        cfg.s("map.registration.file"))
    try:
        record = map_register.load_registration(path)
        frame = ec.MapFrame.from_registration(record)
    except Exception as exc:                       # mc.MapError / EvidenceError
        cfg.refuse("the committed registration belongs to the grid on disk",
                   path, str(exc))
    return frame, frame.to_map(goal.x, goal.y, goal.pose_yaw)


def nav_label(cfg):
    """Which nav2.yaml this session was driven behind, as key=value.

    READ OFF THE FILE ON DISK AND NOT OUT OF A RUNNING NODE, which is
    tools/drive_twist.py's smoother_label() and m5v3.sh's `loc=` label,
    one file over: what binds a session is what was on disk at the
    moment it was used.
    """
    path = os.path.join(_common.REPO, cfg.s("nav.params_file"))
    with open(path, "rb") as handle:
        raw = handle.read()
    return collections.OrderedDict((
        ("nav_params", cfg.s("nav.params_file")),
        ("nav_params_md5", hashlib.md5(raw).hexdigest()[:8]),
    ))


def describe(cfg, goal):
    """What this goal is, and where it will be sent. Needs nothing."""
    frame, at = goal_in_map(cfg, goal)
    print("goal       {}".format(goal.name))
    if goal.note:
        print("           {}".format(goal.note))
    print("world      ({:+.3f}, {:+.3f})  travel heading {:+.6f} rad "
          "({:+.1f} deg)".format(goal.x, goal.y, goal.travel_yaw,
                                 math.degrees(goal.travel_yaw)))
    print("pose yaw   {:+.6f} rad ({:+.1f} deg) - the TABLE says which way "
          "the truck".format(goal.pose_yaw, math.degrees(goal.pose_yaw)))
    print("           is POINTED, and this file adds the pi: the forks are "
          "at model -x.")
    print("map        ({:+.6f}, {:+.6f}) yaw {:+.6f}, through the committed "
          "registration".format(*at))
    print("           {}".format(frame.floor()))
    print("from       spawn ({:+.3f}, {:+.3f}) yaw {:+.5f}, straight-line "
          "{:.3f} m".format(
              cfg.f("vehicle.spawn.x"), cfg.f("vehicle.spawn.y"),
              cfg.f("vehicle.spawn.yaw"),
              math.hypot(goal.x - cfg.f("vehicle.spawn.x"),
                         goal.y - cfg.f("vehicle.spawn.y"))))
    print("repeat     {} session(s) required for the evidence".format(
        goal.repeat))
    return at


# ----------------------------------------------------------------------
# the session on disk
# ----------------------------------------------------------------------

def session_dir(cfg, name):
    return os.path.join(_common.REPO, cfg.s("evidence.dir"), name)


def sessions_in(cfg):
    root = os.path.join(_common.REPO, cfg.s("evidence.dir"))
    if not os.path.isdir(root):
        return []
    return sorted(name for name in os.listdir(root)
                  if name.startswith("goal-")
                  and os.path.isdir(os.path.join(root, name)))


def load(cfg, session):
    path = session_dir(cfg, session)
    tables = {name: ec.read_csv(os.path.join(path, name + ".csv"))
              for name in STREAMS}
    with open(os.path.join(path, "session.txt"), encoding="utf-8") as handle:
        fields = ec.parse_state_file(handle.read())
    return tables, fields


def rows_of(table, columns):
    cols = [table.column(name) for name in columns]
    return list(zip(*cols)) if cols and cols[0] else []


def plans_of(table):
    """`plan.csv` as [(t, [(x, y), ...]), ...], newest last.

    EVERY PLAN AND NOT THE FIRST ONE. The tree replans at 1 Hz, so a
    deviation measured against the plan the run STARTED with would be a
    deviation from a path that stopped existing seconds later - and it
    would grow with every legitimate replan. Each truth sample is scored
    against the plan that was standing at its own time.
    """
    out = collections.OrderedDict()
    for t, index, _i, x, y, _yaw in rows_of(
            table, ("t_s", "plan", "i", "x", "y", "yaw")):
        key = int(index)
        if key not in out:
            out[key] = (float(t), [])
        out[key][1].append((float(x), float(y)))
    return [out[key] for key in sorted(out)]


def plan_standing_at(plans, t):
    """The most recent plan at or before `t`, or None."""
    standing = None
    for at, poly in plans:
        if at <= t:
            standing = poly
        else:
            break
    return standing


# ----------------------------------------------------------------------
# the arithmetic `analyse` is made of
# ----------------------------------------------------------------------

def window(t, lo, hi):
    return [i for i, value in enumerate(t) if lo <= value < hi]


def mean_pose(rows, indices):
    """The mean (x, y, yaw) over a set of rows. The yaw is averaged as a
    UNIT VECTOR, because a heading near +-pi averaged as a number lands
    at zero - which is the other side of the map."""
    xs = [rows[i][1] for i in indices]
    ys = [rows[i][2] for i in indices]
    cs = [math.cos(rows[i][3]) for i in indices]
    ss = [math.sin(rows[i][3]) for i in indices]
    return (ec.mean(xs), ec.mean(ys), math.atan2(ec.mean(ss), ec.mean(cs)))


def arrival(goal, pose):
    """(dx, dy, distance, dyaw) of a pose against a goal, in WORLD metres."""
    dx = pose[0] - goal.x
    dy = pose[1] - goal.y
    return (dx, dy, math.hypot(dx, dy),
            ec.normalise_angle(pose[2] - goal.pose_yaw))


def steer_activity(rows):
    """Total travel, worst step and range of the steer terminal.

    THE TOTAL IS THE SMOOTHNESS FIGURE AND THE WORST STEP IS THE LIMIT
    CHECK, and they answer different questions. A path driven with the
    wheel sawing back and forth has a large total and a small worst
    step; one with a single hard correction has the reverse.
    """
    values = [row[1] for row in rows]
    if len(values) < 2:
        return (0.0, 0.0, 0.0)
    steps = [abs(b - a) for a, b in zip(values, values[1:])]
    return (math.fsum(steps), max(steps), max(values) - min(values))


def curvature_of(v, w, deadband):
    """w/v where v is a command and not a rounding error, else None.

    BELOW THE DEADBAND THE RATIO IS NOT A CURVATURE. The converter says
    so itself: under navcmd.creep_speed_mps it answers with a standing
    zero and a HELD steer axis, because "the requested curvature is not
    a number the controller meant".
    """
    if abs(float(v)) <= abs(float(deadband)):
        return None
    return float(w) / float(v)


def jump_response(jump_t, cmd_rows, span_s):
    """What the commanded twist did in the `span_s` after a jump.

    IT IS A RANGE AND NOT A DIFFERENCE OF ENDPOINTS. A controller that
    swings and comes back inside the window would show nothing at all
    in a first-to-last subtraction, and a swing is exactly what a jump
    is expected to produce.
    """
    inside = [row for row in cmd_rows if jump_t <= row[0] < jump_t + span_s]
    if len(inside) < 2:
        return None
    vs = [row[2] for row in inside]
    ws = [row[3] for row in inside]
    return (max(vs) - min(vs), max(ws) - min(ws), len(inside))


def real_time_factor(rows):
    """Sim seconds per wall second over a stream that carries both."""
    if len(rows) < 2:
        return None
    sim = float(rows[-1][0]) - float(rows[0][0])
    wall = float(rows[-1][1]) - float(rows[0][1])
    if wall <= 0.0:
        return None
    return sim / wall


# ----------------------------------------------------------------------
# analyse
# ----------------------------------------------------------------------

def analyse_session(cfg, session):
    tables, fields = load(cfg, session)
    goal = read_goal(cfg, fields["goal"])
    frame, at_map = goal_in_map(cfg, goal)

    print("")
    print("=== {} ===".format(session))
    print("goal      {}   world ({:+.3f}, {:+.3f}) travel {:+.4f} rad, "
          "pose yaw {:+.4f}".format(goal.name, goal.x, goal.y,
                                    goal.travel_yaw, goal.pose_yaw))
    for key in ("traction", "arm", "loc", "nav", "nav_params_md5"):
        print("{:<9} {}".format(key, fields.get(key, "UNLABELLED")))
    print("result    status {}  error_code {}  {}".format(
        fields.get("action_status", "?"), fields.get("error_code", "?"),
        "(cancelled by this bench)" if fields.get("cancelled") == "1" else ""))

    for stream, table in tables.items():
        if stream in ("plan", "feedback"):
            continue
        if table.n < cfg.i("evidence.min_samples"):
            raise ec.EvidenceError(
                "{}: {} recorded {} rows, under evidence.min_samples"
                .format(session, stream, table.n))

    truth = rows_of(tables["ground_truth"], ("t_s", "x", "y", "yaw"))
    speed = tables["ground_truth"].column("vx")
    parent = rows_of(tables["map_odom"], ("t_s", "x", "y", "yaw"))
    child = rows_of(tables["odom_base"], ("t_s", "x", "y", "yaw"))
    cmd = rows_of(tables["cmd_vel"], ("t_s", "t_wall", "v_mps", "w_radps"))
    steer = rows_of(tables["steer_cmd"], ("t_s", "steer_rad"))

    t_sent = float(fields["t_goal_sent_s"])
    t_done = float(fields["t_result_s"])
    t_end = float(truth[-1][0])

    # ---- the arrival, twice ------------------------------------------
    span = cfg.f("nav.analyse.arrival_window_s")
    at_rest = cfg.f("nav.analyse.at_rest_mps")
    rest = window([row[0] for row in truth], t_end - span, t_end + 1.0)
    if not rest:
        raise ec.EvidenceError(
            "{}: the last {:g}s of ground truth is empty".format(
                session, span))
    moving = max(abs(speed[i]) for i in rest)
    truth_pose = mean_pose(truth, rest)
    print("")
    print("ARRIVAL   the truck came to rest at |vx| = {:.5f} m/s "
          "(ceiling {:.3f})".format(moving, at_rest))
    if moving > at_rest:
        print("          IT IS STILL MOVING. The figures below are a place "
              "it drove")
        print("          through, not a place it arrived - nav.settle_s "
              "was too short.")
    dx, dy, dist, dyaw = arrival(goal, truth_pose)
    print("  TRUTH   ({:+.4f}, {:+.4f}) yaw {:+.4f}   error {:+.4f} "
          "{:+.4f} = {:.4f} m, {:+.4f} rad".format(
              truth_pose[0], truth_pose[1], truth_pose[2], dx, dy, dist,
              dyaw))

    # AND WHAT THE STACK BELIEVED, which is the pose the goal checker
    # actually tested. F3's own instrument: map -> base_link off /tf,
    # composed on the estimator's timeline and carried into the building
    # by the committed registration. NOTHING IS ANCHORED.
    believed = None
    if parent and child:
        composed = ec.compose_rows(parent, child, cfg.f("nav.analyse.map_gap_s"))
        world = ec.rows_to_world(composed, frame)
        rest_b = window([row[0] for row in world], t_end - span, t_end + 1.0)
        if rest_b:
            believed = mean_pose(world, rest_b)
            bdx, bdy, bdist, bdyaw = arrival(goal, believed)
            print("  BELIEVED({:+.4f}, {:+.4f}) yaw {:+.4f}   error {:+.4f} "
                  "{:+.4f} = {:.4f} m, {:+.4f} rad".format(
                      believed[0], believed[1], believed[2], bdx, bdy,
                      bdist, bdyaw))
            print("          the goal checker only ever saw this one. "
                  "truth - believed = {:.4f} m".format(
                      math.hypot(truth_pose[0] - believed[0],
                                 truth_pose[1] - believed[1])))
    print("          the instrument floor under both: {}".format(
        frame.floor()))

    # ---- what the controller did -------------------------------------
    print("")
    hz = ec.rate_from_stamps([row[0] for row in cmd])
    print("CONTROL   /cmd_vel {} messages, {}".format(len(cmd), hz))
    rtf = real_time_factor(cmd)
    if rtf is not None:
        print("          real-time factor over the drive: {:.4f} "
              "(sim/wall, from the same stamps)".format(rtf))
    total, worst, sweep = steer_activity(steer)
    print("          steer terminal: {:.4f} rad of travel, worst step "
          "{:.6f} rad, range {:.4f} rad".format(total, worst, sweep))
    curves = [c for c in
              (curvature_of(row[2], row[3], cfg.f("nav.analyse.cusp_speed_mps"))
               for row in cmd) if c is not None]
    if curves:
        print("          commanded curvature: {}".format(
            ec.summarise([abs(c) for c in curves])))
    cusps = ec.sign_changes([row[2] for row in cmd],
                            cfg.f("nav.analyse.cusp_speed_mps"))
    print("          direction changes in the command: {} "
          "(a Reeds-Shepp cusp is one of these)".format(cusps))
    forward = [row[2] for row in cmd if row[2] < 0.0]
    astern = [row[2] for row in cmd if row[2] > 0.0]
    print("          forks-first (nav2 REVERSE) {} samples, worst "
          "{:+.4f} m/s".format(len(forward),
                               min(forward) if forward else 0.0))
    print("          counterweight-first (nav2 forward) {} samples, worst "
          "{:+.4f} m/s".format(len(astern),
                               max(astern) if astern else 0.0))

    # ---- the deviation from the plan ---------------------------------
    plans = plans_of(tables["plan"])
    print("")
    print("PLAN      {} plan(s) published; the tree replans at 1 Hz".format(
        len(plans)))
    if plans:
        print("          first plan {} poses, {:.3f} m; last plan {} poses, "
              "{:.3f} m".format(len(plans[0][1]),
                                ec.polyline_length(plans[0][1]),
                                len(plans[-1][1]),
                                ec.polyline_length(plans[-1][1])))
        deviation = []
        for row in truth:
            if not (t_sent <= row[0] <= t_done):
                continue
            poly = plan_standing_at(plans, row[0])
            if not poly:
                continue
            deviation.append(ec.point_to_polyline(row[1], row[2], poly))
        if deviation:
            print("          DEVIATION of the truth from the plan standing "
                  "at the time:")
            print("            {}".format(ec.summarise(deviation)))
            print("          nav2 #5714 is open on exactly this figure for "
                  "Ackermann robots")
            print("          in turns, worst in REVERSE turns - and on this "
                  "vehicle every")
            print("          ordinary leg IS a nav2 reverse leg. Measured, "
                  "not tuned around.")
        else:
            print("          no truth sample fell inside a standing plan")

    # ---- the driven path itself --------------------------------------
    driven = [row for row in truth if t_sent <= row[0] <= t_end]
    if len(driven) > 1:
        length = ec.path_length([row[1] for row in driven],
                                [row[2] for row in driven])
        straight = math.hypot(driven[-1][1] - driven[0][1],
                              driven[-1][2] - driven[0][2])
        print("          driven {:.3f} m of ground truth against a "
              "{:.3f} m straight line".format(length, straight))
    print("          the goal took {:.2f} s of sim time from send to "
          "result".format(t_done - t_sent))

    # ---- the jumps, and what the controller did about them -----------
    print("")
    if parent:
        jumps = ec.tf_jumps(parent)
        print("JUMPS     {} corrections in {} broadcasts over {:.1f} s "
              "({:.3f} /s)".format(jumps.n, jumps.samples, jumps.span_s,
                                   jumps.per_s or 0.0))
        if jumps.n:
            print("          worst step {:.4f} m / {:.4f} rad; F3 handed "
                  "over 0.2591 m / 0.0764 rad".format(
                      jumps.max_dpos_m, jumps.max_dyaw_rad))
            print("          position steps {}".format(jumps.dpos))
            print("          heading  steps {}".format(jumps.dyaw))
        # AND THE INTERACTION, WHICH IS THE THING NOBODY HAS MEASURED
        # BEFORE ON THIS TRACK. A step in map -> odom moves the vehicle
        # under the controller's own feet; what it does about it lands
        # on /cmd_vel within a tick or two.
        span_j = cfg.f("nav.analyse.jump_response_s")
        worst_v = worst_w = 0.0
        at_worst = None
        responses = 0
        for before, after in zip(parent, parent[1:]):
            step = math.hypot(after[1] - before[1], after[2] - before[2])
            turn = abs(ec.normalise_angle(after[3] - before[3]))
            if step == 0.0 and turn == 0.0:
                continue
            answer = jump_response(after[0], cmd, span_j)
            if answer is None:
                continue
            responses += 1
            if answer[0] > worst_v:
                worst_v, at_worst = answer[0], (after[0], step, turn, answer)
            worst_w = max(worst_w, answer[1])
        print("          {} of them had {:.2g}s of commanded twist after "
              "them".format(responses, span_j))
        if at_worst is not None:
            t_j, step, turn, answer = at_worst
            print("          the largest response: a {:.4f} m / {:.4f} rad "
                  "step at t = {:.2f}".format(step, turn, t_j))
            print("          moved the commanded v by {:.4f} m/s and the "
                  "commanded w by {:.4f} rad/s".format(answer[0], answer[1]))
            print("          over {} samples. worst w swing after any jump: "
                  "{:.4f} rad/s".format(answer[2], worst_w))
    else:
        print("JUMPS     the map -> odom stream is EMPTY. This session was "
              "not localised,")
        print("          and no absolute figure above is one.")
    return 0


def analyse(cfg, names):
    found = names or sessions_in(cfg)
    if not found:
        cfg.refuse("there is a recorded goal session to analyse",
                   os.path.join(_common.REPO, cfg.s("evidence.dir")),
                   "nothing there begins with `goal-`.",
                   "record one: python3 m5_ver3/tools/drive_goal.py record "
                   "--goal {}".format(cfg.s("nav.default_goal")))
    # ONE ANALYSE, ONE OF EVERY LABEL - which is
    # tools/sensor_evidence.py's rule and its reason, applied to the one
    # extra label this bench carries: two sessions driven behind two
    # nav2.yamls are two experiments with CSVs of the same shape.
    seen = collections.OrderedDict()
    for name in found:
        _tables, fields = load(cfg, name)
        key = "  ".join(fields.get(k, "UNLABELLED")
                        for k in ("traction", "arm", "loc", "nav"))
        seen.setdefault(key, []).append(name)
    if len(seen) > 1:
        lines = []
        for key, names_in in seen.items():
            lines.append("  {} - {} session(s):".format(key, len(names_in)))
            lines.extend("      " + n for n in names_in)
        cfg.refuse("every session in this analyse is off the SAME stack",
                   "{} (the session.txt of each) and {} (the label "
                   "chain)".format(os.path.join(_common.REPO,
                                                cfg.s("evidence.dir")),
                                   _common.CONFIG),
                   "{} different traction/arm/loc/nav combinations are in "
                   "this set:".format(len(seen)), *lines)
    # AND THE REPEAT COUNT, PRINTED BESIDE WHAT WAS ACTUALLY FOUND.
    # config.yaml's nav.goals[].repeat says what the EVIDENCE has to
    # contain; this is what it does contain, so a repeatability claim
    # cannot be made over one run by accident.
    counts = collections.OrderedDict()
    for name in found:
        _tables, fields = load(cfg, name)
        counts[fields.get("goal", "?")] = counts.get(
            fields.get("goal", "?"), 0) + 1
    print("=== goal sessions ===")
    for key, row in cfg.raw("nav.goals").items():
        print("  {:<14} {} recorded, {} required".format(
            key, counts.get(key, 0), row.get("repeat", "?")))
    for name in found:
        analyse_session(cfg, name)
    return 0


# ----------------------------------------------------------------------
# record
# ----------------------------------------------------------------------

def record(cfg, args):
    """One goal, sent and scored."""
    try:
        import time

        import rclpy
        from geometry_msgs.msg import Twist
        from nav2_msgs.action import NavigateToPose
        from nav_msgs.msg import Odometry, Path
        from rclpy.action import ActionClient
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from std_msgs.msg import Float64
        from tf2_msgs.msg import TFMessage
    except ImportError as exc:
        cfg.refuse("rclpy and nav2_msgs are importable",
                   _common.CONFIG + " (paths.ros_setup)",
                   "python3 could not import what this bench needs: "
                   "{}".format(exc),
                   "it runs INSIDE WSL with /opt/ros/jazzy sourced. "
                   "`analyse` needs neither.")

    goal = read_goal(cfg, args.goal)
    print("=== m5v3 nav goal ===")
    at_map = describe(cfg, goal)
    print("")

    # THE LABEL CHAIN, AND A RUN WITHOUT ONE IS NOT RECORDED. It is
    # tools/sensor_evidence.py's rule and its reason - plus one more
    # here: a stack with `nav=off` has no bt_navigator on it and a goal
    # sent to it is a goal nothing will ever answer, so that is a
    # refusal rather than a timeout twenty minutes later.
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
    if state["nav"] == "off":
        cfg.refuse("the running stack has a planner on it", state_path,
                   "its nav= line reads `off`, so no bt_navigator, no "
                   "planner_server and no",
                   "controller_server are running - and a "
                   "navigate_to_pose goal sent to a stack",
                   "without them is a goal nothing will ever answer.",
                   "  bash m5_ver3/m5v3.sh stop",
                   "  bash m5_ver3/m5v3.sh start --headless --localize --nav")
    if state["loc"] == "none":
        cfg.refuse("the running stack knows where it is", state_path,
                   "its loc= line reads `none`. Every figure this bench "
                   "produces is a pose in",
                   "the BUILDING, and without a localiser there is no "
                   "map -> odom to carry one.")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    session = "goal-{}-{}".format(goal.name, stamp)
    path = session_dir(cfg, session)
    os.makedirs(path)
    print("session    {}".format(path))

    rclpy.init(args=None)
    node = Node("m5v3_drive_goal")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    qos = QoSProfile(depth=50)
    captured = collections.OrderedDict((name, []) for name in STREAMS)
    map_frame = cfg.s("frames.map")
    odom_frame = cfg.s("frames.odom")
    base_frame = cfg.s("frames.base_link")
    plan_index = [0]

    def now_s():
        return node.get_clock().now().nanoseconds * 1e-9

    def stamp_s(header):
        return float(header.stamp.sec) + float(header.stamp.nanosec) * 1e-9

    def yaw_of(q):
        return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                          1.0 - 2.0 * (q.y * q.y + q.z * q.z))

    def on_cmd(msg):
        # BOTH CLOCKS ON THIS ONE STREAM, because the real-time factor is
        # the ratio of the two and the controller's is the only stream
        # that runs at a fixed rate for the whole drive.
        captured["cmd_vel"].append(
            (now_s(), time.time(), msg.linear.x, msg.angular.z))

    def on_smoothed(msg):
        captured["cmd_vel_smoothed"].append(
            (now_s(), msg.linear.x, msg.angular.z))

    def on_steer(msg):
        captured["steer_cmd"].append((now_s(), msg.data))

    def on_traction(msg):
        captured["traction_cmd"].append((now_s(), msg.data))

    def on_truth(msg):
        q = msg.pose.pose.orientation
        captured["ground_truth"].append(
            (stamp_s(msg.header), msg.pose.pose.position.x,
             msg.pose.pose.position.y, yaw_of(q),
             msg.twist.twist.linear.x, msg.twist.twist.angular.z))

    def on_tf(msg):
        # ONE EDGE OUT OF A TOPIC THAT CARRIES EVERY EDGE, matched on
        # BOTH frame names - tools/sensor_evidence.py's rule and its
        # reason. On a nav stack /tf also carries whatever a costmap
        # decided to publish, so matching on a parent alone is not
        # enough here either.
        for tr in msg.transforms:
            parent, child = tr.header.frame_id, tr.child_frame_id
            if parent == map_frame and child == odom_frame:
                name = "map_odom"
            elif parent == odom_frame and child == base_frame:
                name = "odom_base"
            else:
                continue
            captured[name].append(
                (stamp_s(tr.header), tr.transform.translation.x,
                 tr.transform.translation.y, yaw_of(tr.transform.rotation)))

    def on_plan(msg):
        plan_index[0] += 1
        at = now_s()
        for i, pose in enumerate(msg.poses):
            captured["plan"].append(
                (at, plan_index[0], i, pose.pose.position.x,
                 pose.pose.position.y, yaw_of(pose.pose.orientation)))

    node.create_subscription(Twist, cfg.s("topics.cmd_vel"), on_cmd, qos)
    node.create_subscription(Twist, cfg.s("topics.cmd_vel_smoothed"),
                             on_smoothed, qos)
    node.create_subscription(Float64, cfg.s("topics.steer_cmd"), on_steer, qos)
    node.create_subscription(Float64, cfg.s("topics.traction_cmd"),
                             on_traction, qos)
    node.create_subscription(Odometry, cfg.s("topics.odom_ground_truth"),
                             on_truth, qos)
    node.create_subscription(TFMessage, cfg.s("topics.tf"), on_tf, qos)
    node.create_subscription(Path, PLAN_TOPIC, on_plan, qos)

    def spin_until(predicate, budget_s, what, owner, *lines):
        deadline = time.monotonic() + budget_s
        while not predicate():
            if time.monotonic() > deadline:
                cfg.refuse(what, owner, *lines)
            rclpy.spin_once(node, timeout_sec=0.05)

    wait_s = cfg.f("evidence.wait_first_s")
    spin_until(lambda: bool(captured["ground_truth"])
               and bool(captured["map_odom"]), wait_s,
               "the plant and the localiser both reached this bench "
               "within {:g}s".format(wait_s),
               "{} and {} ({} -> {})".format(
                   cfg.s("topics.odom_ground_truth"), cfg.s("topics.tf"),
                   map_frame, odom_frame),
               "the ground truth is the plant's; the map -> odom edge is "
               "the localiser's, and",
               "without it no figure this bench produces is a pose in the "
               "building.",
               "is the stack up? 'bash m5_ver3/m5v3.sh status'")
    spin_until(lambda: now_s() > 0.0, wait_s,
               "the plant's clock reached this bench",
               "{} (config.yaml topics.clock, bridged)".format("/clock"),
               "use_sim_time is set and the ROS clock is still at zero.")

    action = ActionClient(node, NavigateToPose, NAV_ACTION)
    if not action.wait_for_server(timeout_sec=wait_s):
        cfg.refuse("bt_navigator advertised {} within {:g}s".format(
                       NAV_ACTION, wait_s),
                   "{} on domain {}".format(NAV_ACTION,
                                            cfg.s("isolation.ros_domain_id")),
                   "the state file says nav=on, so the arm was brought up "
                   "- and nothing is",
                   "answering on that action. Read "
                   "m5_ver3/logs/bt_navigator.log.")

    # THE PRELUDE. Everything above was discovery; the record starts
    # here, with the truck standing still and nothing commanding. It is
    # what gives the jump statistics a baseline and what shows the
    # command path was silent until Nav2 spoke.
    for name in captured:
        captured[name] = []
    plan_index[0] = 0
    t0 = now_s()
    prelude_s = cfg.f("nav.prelude_s")
    print("clock      /clock reads {:.3f} s of sim time".format(t0))
    print("prelude    {:g} s standing still".format(prelude_s))
    while now_s() < t0 + prelude_s:
        rclpy.spin_once(node, timeout_sec=0.05)
    idle_cmds = len(captured["cmd_vel"])

    from geometry_msgs.msg import PoseStamped
    request = NavigateToPose.Goal()
    request.pose = PoseStamped()
    request.pose.header.frame_id = map_frame
    request.pose.pose.position.x = float(at_map[0])
    request.pose.pose.position.y = float(at_map[1])
    request.pose.pose.orientation.z = math.sin(float(at_map[2]) / 2.0)
    request.pose.pose.orientation.w = math.cos(float(at_map[2]) / 2.0)

    def on_feedback(msg):
        fb = msg.feedback
        captured["feedback"].append(
            (now_s(), fb.distance_remaining,
             fb.navigation_time.sec + fb.navigation_time.nanosec * 1e-9,
             float(fb.number_of_recoveries)))

    t_sent = now_s()
    send = action.send_goal_async(request, feedback_callback=on_feedback)
    rclpy.spin_until_future_complete(node, send, timeout_sec=wait_s)
    handle = send.result() if send.done() else None
    cancelled = 0
    status = -1
    error_code = -1
    if handle is None or not handle.accepted:
        cfg.refuse("bt_navigator ACCEPTED the goal",
                   "{} and {} (nav.goals.{})".format(NAV_ACTION,
                                                     _common.CONFIG,
                                                     goal.name),
                   "map ({:+.4f}, {:+.4f}) yaw {:+.4f} was {}.".format(
                       at_map[0], at_map[1], at_map[2],
                       "not answered" if handle is None else "REJECTED"),
                   "nothing was driven and nothing was recorded.")
    print("goal sent  t = {:.3f} s of sim time".format(t_sent))
    result_future = handle.get_result_async()
    budget_s = cfg.f("nav.goal_timeout_s")
    deadline = time.monotonic() + budget_s
    while not result_future.done():
        if time.monotonic() > deadline:
            print("")
            print("TIMEOUT    {:g}s elapsed and the goal has not "
                  "returned - CANCELLING.".format(budget_s))
            cancelled = 1
            cancel = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(node, cancel, timeout_sec=10.0)
            break
        rclpy.spin_once(node, timeout_sec=0.05)
    t_done = now_s()
    if result_future.done() and result_future.result() is not None:
        outcome = result_future.result()
        status = int(outcome.status)
        error_code = int(getattr(outcome.result, "error_code", -1))
    print("result     t = {:.3f} s, status {}, error_code {}".format(
        t_done, status, error_code))

    # THE SETTLE. The result arrives when the GOAL CHECKER passes, and
    # the truck is still moving then - up to 2.07 s and 1.02 m from
    # cruise (EVIDENCE_NAV_V3.md 8). An arrival scored at the instant
    # the action returned would be scored before the vehicle arrived.
    settle_s = cfg.f("nav.settle_s")
    print("settle     {:g} s".format(settle_s))
    end = now_s() + settle_s
    while now_s() < end:
        rclpy.spin_once(node, timeout_sec=0.05)

    # NOTHING IS PUBLISHED ON ANY EXIT PATH. The controller's own
    # publish_zero_velocity has already left a standing zero on
    # /cmd_vel; a bench that published its own twist here would be a
    # SECOND publisher on the one address F4 constraint 18 gives to the
    # controller, and would be racing it for the terminals.
    for stream, columns in STREAMS.items():
        with open(os.path.join(path, stream + ".csv"), "w",
                  encoding="utf-8", newline="") as handle_out:
            handle_out.write(",".join(columns) + "\n")
            for row in captured[stream]:
                handle_out.write(",".join(
                    "{:.9f}".format(value) for value in row) + "\n")
    with open(os.path.join(path, "session.txt"), "w",
              encoding="utf-8") as handle_out:
        handle_out.write("kind=goal\n")
        handle_out.write("goal={}\n".format(goal.name))
        handle_out.write("goal_world={:.6f} {:.6f} {:.6f}\n".format(
            goal.x, goal.y, goal.travel_yaw))
        handle_out.write("goal_pose_yaw={:.9f}\n".format(goal.pose_yaw))
        handle_out.write("goal_map={:.9f} {:.9f} {:.9f}\n".format(*at_map))
        handle_out.write("t0_s={:.9f}\n".format(t0))
        handle_out.write("t_goal_sent_s={:.9f}\n".format(t_sent))
        handle_out.write("t_result_s={:.9f}\n".format(t_done))
        handle_out.write("action_status={}\n".format(status))
        handle_out.write("error_code={}\n".format(error_code))
        handle_out.write("cancelled={}\n".format(cancelled))
        handle_out.write("idle_cmd_vel={}\n".format(idle_cmds))
        for key, value in state.items():
            handle_out.write("{}={}\n".format(key, value))
        for key, value in nav_label(cfg).items():
            handle_out.write("{}={}\n".format(key, value))
        handle_out.write("recorded={}\n".format(
            datetime.datetime.now().isoformat()))
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    print("")
    for stream in STREAMS:
        print("  {:<18} {} rows".format(stream, len(captured[stream])))
    print("  {:<18} {}".format("plans", plan_index[0]))
    print("  {:<18} {} (the command path was silent until Nav2 spoke)"
          .format("idle /cmd_vel", idle_cmds))
    print("")
    print("analyse it:  python3 {} analyse {}".format(
        os.path.relpath(os.path.abspath(__file__), _common.REPO), session))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="drive_goal.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd")
    for name in ("describe", "record"):
        one = sub.add_parser(name)
        one.add_argument("--goal", default=None)
    ana = sub.add_parser("analyse")
    ana.add_argument("sessions", nargs="*")
    args = parser.parse_args(argv)
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    if args.cmd == "describe":
        describe(cfg, read_goal(cfg, args.goal or cfg.s("nav.default_goal")))
        return 0
    if args.cmd == "record":
        args.goal = args.goal or cfg.s("nav.default_goal")
        return record(cfg, args)
    if args.cmd == "analyse":
        return analyse(cfg, args.sessions)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
