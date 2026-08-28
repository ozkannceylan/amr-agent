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
import re
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
    "vehicle.spawn.x", "vehicle.spawn.y",
    "vehicle.spawn.yaw",
    "map.dir", "map.name", "map.registration.file",
    "nav.params_file", "nav.bt_xml", "nav.goals", "nav.default_goal",
    "nav.cases", "nav.health.action_timeout_s",
    "nav.goal_timeout_s", "nav.settle_s", "nav.prelude_s",
    "nav.watchdog.required_closing_m", "nav.watchdog.closing_allowance_s",
    "nav.analyse.arrival_window_s", "nav.analyse.at_rest_mps",
    "nav.analyse.jump_response_s", "nav.analyse.map_gap_s",
    "nav.analyse.cusp_speed_mps", "nav.analyse.follow_speed_mps",
    "nav.analyse.corridor_boxes", "nav.analyse.corridor_give_up_m",
    "nav.analyse.transit_margin_m",
    "nav.analyse.curvature_span",
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

#: The streams that exist only because NAV2 PRODUCED SOMETHING - a plan,
#: or a twist. All five are empty on a goal the planner refuses, and
#: that emptiness is the measurement rather than a fault: see load(),
#: analyse_session() and config.yaml nav.goals.rack_sw3. The five that
#: are NOT here come from the plant and the estimator, which run whether
#: or not anything was commanded, and are still refused empty by name.
NAV_OUTPUT_STREAMS = ("cmd_vel", "cmd_vel_smoothed", "steer_cmd",
                      "traction_cmd", "plan")

#: The subset of those that a MOVING vehicle must have. `plan` is not
#: one: a planner can plan a path the controller then refuses to follow,
#: and that is a different failure from this one.
COMMANDED_STREAMS = ("cmd_vel", "cmd_vel_smoothed", "steer_cmd",
                     "traction_cmd")

#: One goal, resolved. `pose_yaw` is what goes on the wire; `travel_yaw`
#: is what the table said and what a reader pictures.
Goal = collections.namedtuple(
    "Goal", "name x y travel_yaw pose_yaw repeat note")

#: One CASE, resolved - F4 Task 3. A goal is a pose; a case is what an
#: operator asks for, which on this floor is sometimes two poses and a
#: rule for when the second arrives. `second` is None for a one-goal
#: case, and then `when` and `preempt_at_m` mean nothing and are not
#: read.
Case = collections.namedtuple(
    "Case", "name first second when preempt_at_m repeat note")

#: The two rules a second goal can arrive by, and there is no third.
#: `preempt` sends it while the first is still running (navigate_to_pose
#: is a single-goal server, so nav2 aborts the first); `after` sends it
#: once the first has returned and the vehicle has settled.
CASE_WHEN = ("preempt", "after")


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


def read_case(cfg, name):
    """One row of config.yaml's nav.cases, or a refusal naming them all.

    A CASE IS ONE OR TWO GOALS AND ONE RULE, and every one of the three
    parts is checked here rather than at the moment it is used: a case
    that names a goal the table does not hold is a refusal before the
    stack is touched, not an exception forty metres into a drive.
    """
    cases = cfg.raw("nav.cases")
    if not isinstance(cases, dict) or not cases:
        cfg.refuse("config.yaml's nav.cases is a table of cases",
                   _common.CONFIG,
                   "it reads {!r}".format(cases))
    if name not in cases:
        cfg.refuse("nav.cases names the case that was asked for",
                   _common.CONFIG + " (nav.cases)",
                   "there is no case called {!r}. The table holds:".format(
                       name),
                   *["  {:<18} {}".format(key, row.get("note", ""))
                     for key, row in cases.items()])
    row = cases[name]
    for key in ("goal", "repeat"):
        if key not in row:
            cfg.refuse("nav.cases.{} carries {}".format(name, key),
                       _common.CONFIG + " (nav.cases)",
                       "that row reads {!r}".format(row))
    first = read_goal(cfg, str(row["goal"]))
    second = None
    when = None
    preempt_at = None
    if row.get("then"):
        second = read_goal(cfg, str(row["then"]))
        when = str(row.get("when", ""))
        if when not in CASE_WHEN:
            cfg.refuse("nav.cases.{}'s `when` is one of {}".format(
                           name, "/".join(CASE_WHEN)),
                       _common.CONFIG + " (nav.cases)",
                       "it reads {!r}, and a second goal with no rule "
                       "for when it arrives".format(when),
                       "is two different experiments wearing one name.")
        if when == "preempt":
            if "preempt_at_m" not in row:
                cfg.refuse("nav.cases.{} carries preempt_at_m".format(name),
                           _common.CONFIG + " (nav.cases)",
                           "`when: preempt` needs the believed distance "
                           "to the FIRST goal at which",
                           "the second is sent. Without it there is no "
                           "trigger and nothing fires.")
            preempt_at = float(row["preempt_at_m"])
            if preempt_at <= 0.0:
                cfg.refuse("nav.cases.{}'s preempt_at_m is positive".format(
                               name),
                           _common.CONFIG + " (nav.cases)",
                           "it reads {!r}. It is a REMAINING distance, "
                           "so zero would fire".format(row["preempt_at_m"]),
                           "only on a goal already reached and negative "
                           "would never fire at all.")
    return Case(name=name, first=first, second=second, when=when,
                preempt_at_m=preempt_at, repeat=int(row["repeat"]),
                note=str(row.get("note", "")))


def plan_cusps(poses):
    """Where a planned path CHANGES DIRECTION, as (index, x, y, s).

    `plan_directions` counts the segments each way; this says WHERE the
    changes are, which is the only form the question can be asked in
    when what is wanted is what the vehicle did AROUND one. A cusp is a
    sign change in the segment's travel direction against the pose's own
    heading - nav2 FORWARD (counterweight-first here) to nav2 REVERSE
    (forks-first) or back - and the vehicle has to come to a standstill
    at every one of them, slew the steer axis across and set off again.

    `s` is the arc length from the start of the path to the cusp, which
    is what says whether a cusp is on the way to the goal or a flourish
    at the end of it: a position-only goal checker latches on the box
    and a cusp beyond that point is planned and never driven.

    `run` IS THE FIFTH FIELD AND IT IS THE ONE THAT SEPARATES A
    MANOEUVRE FROM LATTICE NOISE. It is how far the path travels in the
    NEW direction before the next cusp or the end, and a Reeds-Shepp
    path off an SE2 lattice routinely carries a one-pose blip - forward
    for 0.07 m and back again - which is a sign change in the
    arithmetic and nothing at all in the vehicle. Measured on this
    floor the planner's pose spacing is 0.067-0.106 m
    (EVIDENCE_NAV_V3.md 16.2), so a run at or under one spacing is one
    pose. A caller that wants real direction changes filters on this;
    this function does not, because a threshold is a policy and this is
    an instrument.
    """
    out = []
    marks = []
    sign = 0
    s = 0.0
    for i, (a, b) in enumerate(zip(poses, poses[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        step = math.hypot(dx, dy)
        if step == 0.0:
            continue
        this = 1 if math.cos(a[2]) * dx + math.sin(a[2]) * dy > 0.0 else -1
        if sign != 0 and this != sign:
            marks.append((i, a[0], a[1], s))
        sign = this
        s += step
    for n, mark in enumerate(marks):
        end = marks[n + 1][3] if n + 1 < len(marks) else s
        out.append(mark + (end - mark[3],))
    return out


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
    except Exception as exc:            # mc.MapError / EvidenceError
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
    tree_path = os.path.join(_common.REPO, cfg.s("nav.bt_xml"))
    with open(tree_path, "rb") as handle:
        tree_raw = handle.read()
    found = re.search(rb'<Timeout[^>]*msec="([0-9]+)"', tree_raw)
    window = mppi_window(path)
    return collections.OrderedDict((
        ("nav_params", cfg.s("nav.params_file")),
        ("nav_params_md5", hashlib.md5(raw).hexdigest()[:8]),
        # AND THE SAME FILE HASHED AS A CONFIGURATION RATHER THAN AS
        # BYTES, WHICH IS THE ONE THAT MEANS WHAT THE LABEL IS FOR.
        # `nav=on@<md5>` is the raw bytes, so a DOCUMENTATION-ONLY edit
        # re-labels a configuration and `analyse` then refuses to table
        # a measured set beside the very file it was measured on. That
        # is not hypothetical: it happened to F4 Task 2's shipped set
        # (`d430334b` -> `6555ac39`, comments only) and twice more
        # during F4 Task 2.5.
        #   This is the parsed parameter tree, dumped canonically with
        # its keys sorted, so it changes if and only if a VALUE changes.
        # Two sessions with the same `nav_config_md5` were driven by the
        # same stack whatever the comments around it said, and a reader
        # can prove it rather than argue it.
        #   THE `nav=` LABEL IS NOT CHANGED and this does not replace
        # it: that label is written by m5v3.sh, which cannot
        # canonicalise YAML in bash, and the two have to agree. This is
        # recorded BESIDE it.
        ("nav_config_md5", config_md5(path)),
        # AND THE TREE, WHICH THE `nav=` LABEL DOES NOT CARRY. `nav=on@
        # <md5>` is nav2.yaml's hash alone, so two runs behind two
        # DIFFERENT behaviour trees wear the same label and `analyse`
        # would table them together. F4 Task 2.5 put a navigation budget
        # in the tree, which makes that a live hazard rather than a
        # theoretical one, so the tree's own hash and the budget it
        # carries are written beside it. A session recorded before this
        # existed simply has no such lines, which is `loc=none`'s rule:
        # a missing line is an older bench and not a value.
        # AND THE FOUR NUMBERS THAT DECIDE WHETHER PathAlignCritic
        # SCORES, because a session outlives the file it was driven by.
        # EVIDENCE_NAV_V3.md 16.2's whole finding is a horizon against a
        # gate, and a scan of an OLD session against TODAY's nav2.yaml
        # is a measurement of a stack that run was never driven by.
        # With these on the session, analyse() uses the run's own.
        ("nav_time_steps", window.steps),
        ("nav_model_dt", window.model_dt),
        ("nav_vx_max", window.vx_max),
        ("nav_align_gate", window.gate),
        ("nav_bt", cfg.s("nav.bt_xml")),
        ("nav_bt_md5", hashlib.md5(tree_raw).hexdigest()[:8]),
        ("nav_budget_ms", int(found.group(1)) if found else 0),
    ))


def config_md5(path):
    """The md5 of a ROS parameter file's PARAMETERS, not of its bytes.

    Comments and whitespace are not configuration. `yaml.safe_load` then
    a canonical `yaml.safe_dump` with sorted keys reduces the file to
    exactly what rclcpp will apply, and hashing that gives a label that
    moves when the STACK moves and stays still when only the argument
    for it is rewritten.
    """
    import yaml
    with open(path, "r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle)
    canonical = yaml.safe_dump(parsed, default_flow_style=False,
                               sort_keys=True).encode("utf-8")
    return hashlib.md5(canonical).hexdigest()[:8]


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


def describe_case(cfg, case):
    """What a CASE is: one or two goals, and the rule for the second."""
    print("case       {}".format(case.name))
    if case.note:
        print("           {}".format(case.note))
    print("repeat     {} session(s) required for the evidence".format(
        case.repeat))
    print("")
    print("--- goal 1 of {} ---".format(1 if case.second is None else 2))
    first = describe(cfg, case.first)
    if case.second is None:
        print("")
        print("ONE GOAL. This case is the acceptance set's own shape and "
              "what it adds is")
        print("the POSE, not the sequence.")
        return (first, None)
    print("")
    if case.when == "preempt":
        print("--- goal 2 of 2, sent WHILE goal 1 is still running ---")
        print("trigger    the BELIEVED distance to goal 1 falls below "
              "{:.2f} m".format(case.preempt_at_m))
        print("           map -> base_link, the pose the goal checker "
              "and the watchdog see.")
        print("           navigate_to_pose is a SINGLE-GOAL server: nav2 "
              "aborts goal 1 and")
        print("           takes goal 2. Nothing here cancels anything.")
    else:
        print("--- goal 2 of 2, sent AFTER goal 1 has returned ---")
        print("trigger    goal 1's result, then {:g} s of settle".format(
            cfg.f("nav.settle_s")))
        print("           It is a second errand from wherever the first "
              "one ended, which is")
        print("           the only way this bench can start a run from a "
              "pose that is not the spawn.")
    second = describe(cfg, case.second)
    return (first, second)


# ----------------------------------------------------------------------
# the session on disk
# ----------------------------------------------------------------------

def session_dir(cfg, name):
    return os.path.join(_common.REPO, cfg.s("evidence.dir"), name)


def sessions_in(cfg):
    """Every FINISHED goal session under evidence.dir.

    A DIRECTORY WITHOUT A session.txt IS A RECORDING THAT DID NOT
    FINISH, and it is skipped rather than half-read. `record` makes the
    directory before it subscribes to anything and writes every CSV and
    the session file together at the end, so an interrupted run - a
    Ctrl-C, a stack that went down mid-drive - leaves an empty
    directory. Reading one raises out of the CSV reader four frames
    down, naming a file rather than the run.
      NAMED SESSIONS ARE NOT FILTERED. An operator who asks for one by
    name gets that reader's refusal, which is the right answer to
    "analyse this particular thing".
    """
    root = os.path.join(_common.REPO, cfg.s("evidence.dir"))
    if not os.path.isdir(root):
        return []
    return sorted(name for name in os.listdir(root)
                  if (name.startswith("goal-") or name.startswith("case-"))
                  and os.path.isfile(os.path.join(root, name,
                                                  "session.txt")))


def load(cfg, session):
    path = session_dir(cfg, session)
    # THE FOUR COMMAND STREAMS MAY BE EMPTY AND THE FIVE POSE STREAMS
    # MAY NOT. A goal the planner refuses produces a recording in which
    # the controller published nothing at all - which is the fail-fast's
    # own demonstration (config.yaml nav.goals.rack_sw3) - and a reader
    # that refused it would be a bench unable to read its own most
    # important run. Every other stream comes from the plant or the
    # estimator and is still refused empty by name.
    tables = {name: ec.read_csv(os.path.join(path, name + ".csv"),
                                allow_empty=name in NAV_OUTPUT_STREAMS)
              for name in STREAMS}
    with open(os.path.join(path, "session.txt"), encoding="utf-8") as handle:
        fields = ec.parse_state_file(handle.read())
    return tables, fields


def rows_of(table, columns):
    cols = [table.column(name) for name in columns]
    return list(zip(*cols)) if cols and cols[0] else []


def plans_of(table, frame=None):
    """`plan.csv` as [(t, [(x, y, yaw), ...]), ...], newest last.

    EVERY PLAN AND NOT THE FIRST ONE. The tree replans at 1 Hz, so a
    deviation measured against the plan the run STARTED with would be a
    deviation from a path that stopped existing seconds later - and it
    would grow with every legitimate replan. Each truth sample is scored
    against the plan that was standing at its own time.

    AND `frame` IS NOT OPTIONAL IN PRACTICE, WHICH COST A WHOLE RUN TO
    LEARN. nav2 publishes /plan in the MAP frame and the ground truth is
    the BUILDING's; warehouse_v3's map is a half turn and 19 m from the
    world, so a deviation computed without carrying the plan across the
    committed registration reads about 20 m on a vehicle that is
    tracking its path perfectly. The default of None is for the tests
    that exercise the grouping alone.
    """
    out = collections.OrderedDict()
    for t, index, _i, x, y, yaw in rows_of(
            table, ("t_s", "plan", "i", "x", "y", "yaw")):
        key = int(index)
        if key not in out:
            out[key] = (float(t), [])
        pose = (float(x), float(y), float(yaw))
        if frame is not None:
            pose = frame.to_world(*pose)
        out[key][1].append(pose)
    return [out[key] for key in sorted(out)]


def plan_directions(poses):
    """(forward, reverse) segment counts of a planned path.

    WHICH WAY THE PLANNER MEANT THE VEHICLE TO GO, and on this track it
    is the first question to ask of any path. A pose carries a heading;
    the segment to the NEXT pose either advances along that heading
    (nav2 FORWARD, which on this vehicle is counterweight-first) or
    against it (nav2 REVERSE, which is forks-first and is this truck's
    ordinary direction of travel). A Reeds-Shepp path may contain both,
    and every change between them is a CUSP the vehicle has to stop at.
    """
    forward = reverse = 0
    for a, b in zip(poses, poses[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx == 0.0 and dy == 0.0:
            continue
        if math.cos(a[2]) * dx + math.sin(a[2]) * dy > 0.0:
            forward += 1
        else:
            reverse += 1
    return (forward, reverse)


#: What a goal SWITCH cost the command stream. F4 Task 3.
Preempt = collections.namedtuple(
    "Preempt", "gap_s min_v_after mean_v_before mean_v_after recover_s "
               "n_before n_after")


def preempt_response(cmd_rows, t_switch, span_s):
    """What the CONTROLLER's own output did across a goal switch.

    THE MEASUREMENT PREEMPT SEMANTICS COMES DOWN TO. `navigate_to_pose`
    is a single-goal action server, so a second goal DISPLACES the first
    one: nav2 aborts it, the tree halts, a new tree ticks and a new plan
    is computed. Every one of those is a chance for the command stream
    to stop - and a command stream that stops is a vehicle that brakes
    in the middle of an aisle for a re-task that changed nothing about
    where it is going next.

    Four numbers, all off `topics.cmd_vel` and none off the plant:
      `gap_s`         the largest interval between two consecutive
                      commands in the window. At `controller_frequency`
                      20.0 this is 0.05 s when nothing happened.
      `min_v_after`   the smallest |v| commanded after the switch. Zero
                      is a controller that published a stop.
      `mean_v_*`      the mean |v| either side, so the two can be read
                      together - a small `min_v_after` on a leg that was
                      slowing anyway is not a preemption cost.
      `recover_s`     how long until |v| came back to 95 % of the mean
                      it held before the switch, or None if it never did
                      inside the window.
    """
    before = [row for row in cmd_rows if t_switch - span_s <= row[0] < t_switch]
    after = [row for row in cmd_rows if t_switch <= row[0] < t_switch + span_s]
    if not before or not after:
        return None
    stamps = [row[0] for row in before + after]
    gap = max(b - a for a, b in zip(stamps, stamps[1:])) if len(stamps) > 1 \
        else 0.0
    mean_before = math.fsum(abs(row[2]) for row in before) / len(before)
    mean_after = math.fsum(abs(row[2]) for row in after) / len(after)
    recover = None
    for row in after:
        if mean_before > 0.0 and abs(row[2]) >= 0.95 * mean_before:
            recover = row[0] - t_switch
            break
    return Preempt(gap_s=gap,
                   min_v_after=min(abs(row[2]) for row in after),
                   mean_v_before=mean_before, mean_v_after=mean_after,
                   recover_s=recover, n_before=len(before),
                   n_after=len(after))


#: psi's spread over the driven part of a run. F4 Task 3.
Swing = collections.namedtuple("Swing", "n mean sd worst")


def heading_swing(goal_travel_yaw, truth_rows, speeds, lo, hi, min_speed):
    """How far the TRAVEL HEADING wandered from the route's own, as psi.

    THE STATISTIC 16.4c's RESIDUAL IS BIMODAL IN, AND UNTIL F4 TASK 3 IT
    HAD NO INSTRUMENT. That section reported a psi standard deviation of
    0.2072 and 0.1957 on two runs that arrived and 0.5447 on one that
    did not, and every one of those three was computed by hand for the
    table. A residual that a later task has to decide about needs a
    figure it can re-run, so this is that figure.

    psi is the vehicle's TRAVEL heading - pose yaw + pi, because the
    forks are at model -x - against the goal's own travel heading, off
    the GROUND TRUTH. Samples under  are dropped for
    `curvature_demand`'s reason: a heading held at a standstill is not a
    heading the vehicle is driving, and a run that stops for thirty
    seconds would otherwise report whatever it happened to be pointing
    at, thirty seconds' worth.
    """
    psis = []
    for i, row in enumerate(truth_rows):
        if not (lo <= row[0] <= hi):
            continue
        if abs(speeds[i]) < min_speed:
            continue
        travel = ec.normalise_angle(row[3] + math.pi)
        psis.append(ec.normalise_angle(travel - goal_travel_yaw))
    if not psis:
        return None
    mean = math.fsum(psis) / len(psis)
    sd = math.sqrt(math.fsum((p - mean) ** 2 for p in psis) / len(psis))
    return Swing(n=len(psis), mean=mean, sd=sd,
                 worst=max(abs(p) for p in psis))


#: One direction's deviation population. F4 Task 3, fix round 1.
Split = collections.namedtuple("Split", "n mean worst")


def deviation_by_direction(truth_rows, cmd_rows, plans, lo, hi, deadband):
    """(nav2 FORWARD, nav2 REVERSE) deviation from the plan, split.

    THE #5714 A/B AS A COMMITTED INSTRUMENT, AND IT EXISTS BECAUSE THE
    FIRST CUT OF EVIDENCE_NAV_V3.md 17.4 COMPUTED IT BY HAND. nav2 issue
    #5714 says MPPI's Ackermann model tracks worse in REVERSE; on this
    vehicle nav2's REVERSE is ordinary travel, because the forks are at
    model -x - so the only way to ask the question is a session that
    drove BOTH ways, and the only honest way to answer it is one
    function that both populations come out of.

    EACH TRUTH SAMPLE IS ATTRIBUTED TO WHAT THE CONTROLLER WAS ASKING
    FOR AT THAT MOMENT, not to a window somebody cut. The most recent
    `/cmd_vel` at or before the sample decides which population it joins;
    below `deadband` the sign of a command is not a direction
    (`navcmd.creep_speed_mps` - the converter answers a standing zero and
    a HELD steer axis there) and the sample joins neither. The deviation
    itself is the same figure `analyse` reports for the whole run: the
    distance from the truth to the plan STANDING AT THE TIME.

    A DIRECTION THAT WAS NEVER DRIVEN READS None AND NOT ZERO. Almost
    every session on this track is forks-first from end to end, so the
    FORWARD half is absent on all of them, and reporting 0.0 for it
    would be a tracking claim about a leg that does not exist.
    """
    both = {1: [], -1: []}
    cmd_i = 0
    sign = 0
    for row in truth_rows:
        t = float(row[0])
        if not (lo <= t <= hi):
            continue
        while cmd_i < len(cmd_rows) and float(cmd_rows[cmd_i][0]) <= t:
            v = float(cmd_rows[cmd_i][2])
            if abs(v) > deadband:
                sign = 1 if v > 0.0 else -1
            else:
                sign = 0
            cmd_i += 1
        if sign == 0:
            continue
        standing = plan_standing_at(plans, t)
        if not standing:
            continue
        both[sign].append(min(math.hypot(row[1] - p[0], row[2] - p[1])
                              for p in standing))

    def stat(values):
        if not values:
            return None
        return Split(n=len(values),
                     mean=math.fsum(values) / len(values),
                     worst=max(values))
    return (stat(both[1]), stat(both[-1]))


def driven_cusps(cmd_rows, deadband):
    """Where the COMMAND changed direction, as (t, v_before, v_after).

    A CUSP IN THE PLAN IS A PLANNER'S INTENTION; THIS IS THE VEHICLE'S.
    `analyse` already counts these - "direction changes in the command" -
    and this says WHERE each one is, because what a reverse leg costs is
    a question about the samples around it and not about the count.
    Below `deadband` the sign of a command is not a direction
    (`navcmd.creep_speed_mps`), so a crossing is only counted where a
    real command changed hands.
    """
    out = []
    last = None
    for row in cmd_rows:
        v = row[2]
        if abs(v) <= deadband:
            continue
        sign = 1 if v > 0.0 else -1
        if last is not None and sign != last[0]:
            out.append((row[0], last[1], v))
        last = (sign, v)
    return out


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


#: The truth row nearest the goal, and what the error was THERE.
#: `distance` is the same magnitude `arrival()` returns; `dx`/`dy` are
#: its signed components in the BUILDING's frame; `along`/`across` are
#: the same vector projected onto the GOAL's own travel heading, which
#: is the only frame in which the word "cross-track" means anything at
#: a goal.
Approach = collections.namedtuple(
    "Approach", "t x y yaw dx dy distance dyaw along across")


def closest_approach(goal, rows, lo, hi):
    """The nearest the vehicle ever GOT to the goal, and the error there.

    WHY THE ARRIVAL FIGURE IS NOT THIS FIGURE, AND WHY BOTH ARE PRINTED.
    `arrival()` scores where the truck came to REST, which on a run that
    did not arrive is wherever the controller gave up - 6.7 m past the
    goal on one of this task's and 40 m on another. That number says the
    run failed and says nothing at all about WHY. This one says how
    close it came and which way it was out when it was closest, which
    is the difference between "it never got there" and "it went past on
    the wrong side by 0.97 m".

    THE WINDOW IS [t_sent, t_done] AND NOT THE WHOLE RECORDING. Before
    the goal was sent the vehicle was standing at the spawn; after the
    result the bench is watching it coast. Neither is an approach. A
    window with no truth sample in it is None and not a distance - a run
    whose action was rejected has no approach to report.

    THE PROJECTION IS ONTO THE GOAL'S TRAVEL HEADING and never onto the
    vehicle's. What a goal box is a criterion about is where the truck
    is relative to the PLACE, and the place's own frame is the direction
    the route arrives along; taking the frame from the vehicle would
    rotate the split by the heading error being reported beside it.
    `across` is positive to the LEFT of that heading, which is
    evidence_core.track_error()'s own convention.
    """
    inside = [row for row in rows if lo <= float(row[0]) <= hi]
    if not inside:
        return None
    best = min(inside, key=lambda row: math.hypot(float(row[1]) - goal.x,
                                                  float(row[2]) - goal.y))
    dx, dy, distance, dyaw = arrival(goal, (best[1], best[2], best[3]))
    split = ec.track_error(dx, dy, goal.travel_yaw)
    return Approach(float(best[0]), float(best[1]), float(best[2]),
                    float(best[3]), dx, dy, distance, dyaw,
                    split.along, split.cross)


#: Where a run stopped closing on its goal, and what the distance was
#: there. `t` is the plant's clock; `distance` is straight-line metres
#: from the BELIEVED pose to the goal, which is the pose the goal
#: checker sees.
Stalled = collections.namedtuple("Stalled", "t distance mark since_s")


class ClosingWatch:
    """Is this run still getting CLOSER to its goal?

    THE QUESTION nav2's OWN PROGRESS CHECKER CANNOT ASK.
    `nav2_controller::SimpleProgressChecker` is satisfied by
    `required_movement_radius` of MOVEMENT in `movement_time_allowance`,
    and a vehicle that has driven past its goal and is orbiting it
    satisfies that completely - it moves 0.30 m every second. The
    failure F4 Task 2 measured is 130.199 m driven and 459 plans
    published for a goal 2.910 m away, and no amount of tightening a
    movement test reaches it, because the vehicle was moving the whole
    time. This asks about the GOAL instead.

    THE RULE, AND IT IS A FAILURE TO IMPROVE RATHER THAN A SPEED.
    A MARK is kept: the smallest distance the run has earned. Whenever
    the vehicle beats the mark by at least `closing_m` the mark moves
    and the clock restarts. If `allowance_s` passes without the mark
    moving, the run has stopped closing and `step` returns the verdict.

    WHY THE MARGIN AND NOT ANY IMPROVEMENT AT ALL. A vehicle creeping in
    at a millimetre a second improves on its mark forever, and a rule
    that reset on that would never fire on the one case it exists for.

    AND WHY A LOCALISATION JUMP CANNOT PROVOKE IT. A `map` -> `odom`
    correction that moves the belief AWAY from the goal is not an
    improvement, so it neither moves the mark nor counts as progress;
    one that moves the belief TOWARD the goal moves the mark and makes
    the rule more lenient. Either way it can only delay this guard.

    IT COMMANDS NOTHING AND IT IS NOT A SAFETY FUNCTION. What it
    produces is a verdict; what the caller does with it - cancel, or
    write it down - is the caller's.
    """

    def __init__(self, closing_m, allowance_s):
        self.closing_m = float(closing_m)
        self.allowance_s = float(allowance_s)
        self.mark = None
        self.t_mark = None

    def step(self, t, distance):
        """None while it is still closing; a `Stalled` when it is not."""
        t = float(t)
        distance = float(distance)
        if self.mark is None or distance <= self.mark - self.closing_m:
            self.mark = distance
            self.t_mark = t
            return None
        since = t - self.t_mark
        if since > self.allowance_s:
            return Stalled(t=t, distance=distance, mark=self.mark,
                           since_s=since)
        return None


def no_progress_at(samples, closing_m, allowance_s):
    """`ClosingWatch` run over a whole recording, or None.

    ONE IMPLEMENTATION AND TWO ENTRY POINTS. `record` steps the watch
    live off /tf and `analyse` runs this over a session already on disk.
    Two copies of a rule drift exactly the way two copies of a value do,
    so this is a loop over the same object and not a second rule.

    THE RULE IS THE SAME OBJECT AND THE INPUT IS NOT QUITE, WHICH IS
    WORTH SAYING BECAUSE IT HAS ALREADY MATTERED ONCE. Live, `record`
    composes `map` -> `base_link` on every `odom` -> `base_link` message
    using the LATEST `map` -> `odom` - a zero-order hold, which is all a
    running node can do. Offline, `analyse` uses
    evidence_core.compose_rows(), which INTERPOLATES the parent because
    that is what a tf2 listener would have returned. The two differ by
    centimetres, and on a run whose distance-to-goal is swinging by
    metres that is enough to move a mark across the threshold: session
    `goal-ring_corner-20260827-180823` was abandoned by the live watch
    and is not caught by this replay of it. Neither reading is wrong and
    the difference is the reconstruction, not the rule.
    """
    watch = ClosingWatch(closing_m, allowance_s)
    for t, distance in samples:
        verdict = watch.step(t, distance)
        if verdict is not None:
            return verdict
    return None


#: How much of the yaw rate the PLAN required did the controller
#: actually command. `gain` is None when the plan asked for no turn at
#: all over the whole window, because there is then nothing to be a
#: fraction of.
Following = collections.namedtuple(
    "Following", "n gain r demand_rms required commanded")


def plan_curvature_at(poses, x, y, span):
    """The PLAN's own curvature, 1/m, at the pose nearest (x, y).

    A PLANNED PATH CARRIES A HEADING PER POSE and the rate that heading
    turns per metre of path IS the curvature the vehicle would have to
    hold to stay on it. Taken over ONE segment that is a difference of
    two noisy yaws over 0.1 m; `span` poses of it is the same quantity
    with the quantisation averaged out, and on this floor's 0.083-0.105
    m plan spacing four poses is about 0.4 m - well inside the 1.25 m
    radius being measured and well outside the spacing.

    None where the span has no length in it: the tail of a path, or a
    cusp where consecutive poses sit on top of each other.
    """
    if len(poses) < 2:
        return None
    points = [(px, py) for px, py, _ in poses]
    near = min(range(len(points)),
               key=lambda i: math.hypot(points[i][0] - x, points[i][1] - y))
    far = min(near + int(span), len(poses) - 1)
    if far <= near:
        return None
    arc = ec.polyline_length(points[near:far + 1])
    if arc < 1e-6:
        return None
    return ec.normalise_angle(poses[far][2] - poses[near][2]) / arc


def curvature_demand(cmd_rows, truth_rows, plans, lo, hi, deadband, span):
    """(required, commanded) yaw rates over a run, sample for sample.

    THE MERGE IS A WALK AND NOT A SEARCH, because both streams are in
    time order and a run that did not arrive carries ten thousand
    commands against ten thousand truth samples and four hundred plans.

    SAMPLES BELOW `deadband` ARE DROPPED. Curvature is a demand PER
    METRE and the yaw rate it implies is that demand times the speed;
    at a stop the demand is real and the yaw rate it asks for is zero,
    so a vehicle standing at a cusp would contribute a pile of (0, 0)
    pairs that flatter any gain towards whatever the intercept is.
    """
    required, commanded = [], []
    truth_i, plan_i = 0, -1
    for row in cmd_rows:
        t = row[0]
        if not (lo <= t <= hi):
            continue
        while (truth_i + 1 < len(truth_rows)
               and truth_rows[truth_i + 1][0] <= t):
            truth_i += 1
        while plan_i + 1 < len(plans) and plans[plan_i + 1][0] <= t:
            plan_i += 1
        if plan_i < 0 or not truth_rows or abs(row[2]) < deadband:
            continue
        here = truth_rows[truth_i]
        demand = plan_curvature_at(plans[plan_i][1], here[1], here[2], span)
        if demand is None:
            continue
        required.append(demand * abs(row[2]))
        commanded.append(row[3])
    return (required, commanded)


def curvature_following(required, commanded):
    """The gain of the commanded yaw rate on the yaw rate the plan needed.

    WHY THE DEVIATION FIGURE CANNOT ANSWER THIS AND THIS CAN. The tree
    replans at 1 Hz and every plan is anchored at the vehicle's own
    pose, so the vehicle is ON its path by construction and a deviation
    measured against the plan standing at the time can be small on a
    controller that is not steering the path at all - which is exactly
    what F4 Task 2 measured (mean 0.040-0.113 m) on runs that missed
    their goals by a metre. This asks the other question: the plan
    carries a curvature at the vehicle, that curvature times the
    vehicle's speed IS a yaw rate, and the controller either commanded
    it or did not.

    THE GAIN IS A REGRESSION THROUGH THE ORIGIN AND NOT A RATIO OF
    MEANS. A leg that turns one way and then the other has a mean
    demand near zero, and a ratio of means would read a perfect
    controller as a dead one. sum(a*b)/sum(a*a) is the least-squares
    slope of commanded on required with no intercept - it is 1.0 for a
    controller that obeys, 0.0 for one that ignores.

    `r` IS BESIDE IT BECAUSE THE TWO SAY DIFFERENT THINGS. A gain near
    zero with a correlation near zero is a controller not listening; a
    gain near zero with a high correlation is one listening and
    saturated. Both were seen while this instrument was being written.
    """
    required = [float(v) for v in required]
    commanded = [float(v) for v in commanded]
    if not required:
        raise ec.EvidenceError(
            "curvature_following: an empty window has no gain in it")
    if len(required) != len(commanded):
        raise ec.EvidenceError(
            "curvature_following: {} required against {} commanded - "
            "these are two readings of the SAME samples".format(
                len(required), len(commanded)))
    denominator = sum(value * value for value in required)
    gain = (sum(a * b for a, b in zip(required, commanded)) / denominator
            if denominator > 1e-12 else None)
    return Following(n=len(required), gain=gain,
                     r=ec.correlation(required, commanded),
                     demand_rms=math.sqrt(denominator / len(required)),
                     required=ec.summarise(required),
                     commanded=ec.summarise(commanded))


#: One rung of the approach corridor: the moment the BELIEVED pose
#: first came inside a candidate goal box, and what the heading was
#: doing there. `truth` is the ground truth at that same moment.
Rung = collections.namedtuple("Rung", "box t believed truth dyaw")


def first_approach(goal, rows, lo, hi, give_up_m):
    """The rows of the FIRST run at the goal, cut where it gave up.

    A RUN THAT MISSES ITS GOAL COMES BACK AT IT, and on this vehicle it
    comes back through a Reeds-Shepp loop with the heading anywhere at
    all. Every rung of the corridor below has to be read off ONE pass,
    because what it is a table about is what an approach COSTS - and a
    second pass is a different approach, from a different heading,
    after a manoeuvre the first one did not make.

    The cut is the first local minimum the run then walks `give_up_m`
    back out of. A run that arrives is never cut and returns whole.
    """
    inside = [row for row in rows if lo <= float(row[0]) <= hi]
    best = None
    for i, row in enumerate(inside):
        distance = math.hypot(float(row[1]) - goal.x, float(row[2]) - goal.y)
        if best is None or distance < best:
            best = distance
        elif distance > best + give_up_m:
            return inside[:i]
    return inside


def approach_corridor(goal, believed, truth, lo, hi, boxes, give_up_m):
    """What each candidate goal box would have cost in HEADING.

    THE QUESTION F5's DOCKING INHERITS, AND IT IS A CURVE RATHER THAN A
    NUMBER. A goal box is latched on the BELIEVED pose the first time
    the vehicle is inside it, so the box decides how far into its own
    endgame the vehicle drives - and on a tricycle the endgame is where
    the heading is spent. Inside `GoalCritic.threshold_to_consider` the
    path critics have handed over to a point attraction with no heading
    in it, and nulling a residual lateral offset against a 1.25 m
    minimum radius costs yaw at a rate this table measures.

    For each box: the first BELIEVED row inside it, the TRUTH at that
    same moment, and the heading error against the goal's pose yaw. A
    box the run never reached is absent rather than reported as its own
    closest approach, which would read as a rung that was met.
    """
    walk = first_approach(goal, believed, lo, hi, give_up_m)
    if not walk:
        return ([], None)
    closest = min(math.hypot(float(r[1]) - goal.x, float(r[2]) - goal.y)
                  for r in walk)
    out = []
    for box in sorted((float(b) for b in boxes), reverse=True):
        for row in walk:
            distance = math.hypot(float(row[1]) - goal.x,
                                  float(row[2]) - goal.y)
            if distance > box:
                continue
            here = None
            for candidate in truth:
                if float(candidate[0]) <= float(row[0]):
                    here = candidate
                else:
                    break
            out.append(Rung(
                box=box, t=float(row[0]), believed=distance,
                truth=(math.hypot(float(here[1]) - goal.x,
                                  float(here[2]) - goal.y)
                       if here is not None else None),
                dyaw=abs(ec.normalise_angle(float(row[3]) - goal.pose_yaw))))
            break
    return (out, closest)


#: The four numbers in nav2.yaml that decide whether PathAlignCritic
#: scores at all. `horizon_m` is what one sampled trajectory reaches at
#: the transit ceiling; `gate` is the critic's own offset_from_furthest.
MppiWindow = collections.namedtuple(
    "MppiWindow", "horizon_m gate steps model_dt vx_max")

#: One align-gate scan. `index` is the reachable path index summarised
#: over the plans of a run; `cleared` counts the plans that could have
#: cleared the gate; `at_rest` counts the plans dropped for being
#: published while the vehicle was not moving.
GateScan = collections.namedtuple(
    "GateScan", "n cleared at_rest index reach window")


def mppi_window(path):
    """`MppiWindow` read off a nav2 parameter file.

    THE HORIZON IS A DISTANCE AND time_steps IS A COUNT, which is the
    whole of EVIDENCE_NAV_V3.md 16.2. This is the one place that
    multiplies the three numbers together, so a reader never has to.
    """
    import yaml
    with open(path, "r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle)
    follow = parsed["controller_server"]["ros__parameters"]["FollowPath"]
    steps = int(follow["time_steps"])
    model_dt = float(follow["model_dt"])
    vx_max = float(follow["vx_max"])
    return MppiWindow(horizon_m=steps * model_dt * vx_max,
                      gate=int(follow["PathAlignCritic"]
                               ["offset_from_furthest"]),
                      steps=steps, model_dt=model_dt, vx_max=vx_max)


def plan_reach(poses, horizon_m):
    """The path index a trajectory `horizon_m` long can reach along a plan.

    Walked on ARC LENGTH, because that is what a trajectory spends, and
    resolved to the NEAREST pose rather than the first one at or beyond
    the horizon - which is what nav2's own findPathFurthestReachedPoint
    does with the trajectory's last point. A horizon longer than the
    plan stops at its last pose.
    """
    if len(poses) < 2:
        return 0
    walked, best, best_gap = 0.0, 0, abs(horizon_m)
    for i in range(1, len(poses)):
        walked += math.hypot(poses[i][0] - poses[i - 1][0],
                             poses[i][1] - poses[i - 1][1])
        gap = abs(walked - horizon_m)
        if gap < best_gap:
            best, best_gap = i, gap
        if walked >= horizon_m:
            break
    return best


def align_gate_scan(plans, truth_rows, speeds, window, lo, hi, min_speed):
    """Could `PathAlignCritic` have scored on these plans, ever?

    nav2 1.3.12, path_align_critic.cpp, the third statement of score():
    the critic RETURNS unless `furthest_reached_path_point` is at least
    `offset_from_furthest`, and utils.hpp computes that index from the
    LAST point of every sampled trajectory. It is therefore the
    prediction horizon measured in path points, and this scan is that
    index per published plan.

    IT IS AN UPPER BOUND AND THAT IS DELIBERATE. A trajectory that
    followed the plan exactly would reach the index returned here; a
    real sample curves away from it and reaches the same index or a
    lower one. So a scan that says the gate was never cleared is a
    stronger claim than a scan that says it usually was not - the BEST
    case did not reach it either.

    PLANS PUBLISHED AT A STANDSTILL ARE DROPPED AND COUNTED. A horizon
    is a speed times a time; at rest it is zero, and the index would be
    an artefact rather than a measurement.
    """
    inside = [(at, poses) for at, poses in plans if lo <= at <= hi]
    if not inside or not truth_rows:
        return None
    indices, reaches, cleared, at_rest = [], [], 0, 0
    cursor = 0
    for at, poses in inside:
        while (cursor + 1 < len(truth_rows)
               and truth_rows[cursor + 1][0] <= at):
            cursor += 1
        speed = abs(float(speeds[cursor])) if cursor < len(speeds) else 0.0
        if speed < min_speed:
            at_rest += 1
            continue
        reach = window.steps * window.model_dt * speed
        index = plan_reach(poses, reach)
        indices.append(float(index))
        reaches.append(reach)
        if index >= window.gate:
            cleared += 1
    if not indices:
        return None
    return GateScan(n=len(indices), cleared=cleared, at_rest=at_rest,
                    index=ec.summarise(indices),
                    reach=ec.summarise(reaches), window=window)


#: How much of a run's lateral miss the heading error alone explains.
#: `predicted` is the integral, `measured` is what the ground truth did,
#: `ratio` is the first over the second - 1.0 leaves nothing for
#: anything else.
Account = collections.namedtuple(
    "Account", "n predicted measured ratio psi from_along to_along")


def heading_account(goal, truth_rows, speeds, lo, hi, transit_margin_m):
    """Does the heading error account for the whole lateral miss?

    THE MEASUREMENT THAT KILLED TWO SUSPECTS AT ONCE (16.1 (b) and (c)).
    A vehicle traveling at |v| with its course psi off the goal's own
    travel heading moves sideways at |v| * sin(psi). Integrating that
    over the transit predicts the ACROSS component the run should have
    accumulated; comparing it with what the ground truth actually did
    says how much is left for anything else. On F4 Task 2's two runs
    that reached the goal's station the answer was 0.974 and 1.059 -
    which leaves no room for a 0.83 m localisation jump or for a replan
    loop, and is what killed both hypotheses. EVIDENCE_NAV_V3.md 16.1
    carries the same two figures and analyse_session() prints them.

    THE WINDOW STOPS `transit_margin_m` SHORT OF THE GOAL, ALONG TRACK,
    and that is not a convenience. Past that point the vehicle is in an
    endgame where psi sweeps through a right angle as it hooks round;
    integrating that would be an account of the pirouette and not of the
    transit the miss accumulated over.

    None when the run never came within the margin at all - there is no
    transit to account for, and a ratio of two numbers that are both
    noise is not a finding.
    """
    inside = [(i, row) for i, row in enumerate(truth_rows)
              if lo <= float(row[0]) <= hi]
    predicted, first, last, psis, n = 0.0, None, None, [], 0
    previous = None
    for i, row in inside:
        split = ec.track_error(float(row[1]) - goal.x,
                               float(row[2]) - goal.y, goal.travel_yaw)
        if split.along > -abs(transit_margin_m):
            break
        psi = ec.normalise_angle(
            ec.normalise_angle(float(row[3]) + math.pi) - goal.travel_yaw)
        psis.append(psi)
        if first is None:
            first = split.cross
        last = split.cross
        if previous is not None and i < len(speeds):
            predicted += (abs(float(speeds[i])) * math.sin(psi)
                          * (float(row[0]) - previous))
        previous = float(row[0])
        n += 1
    if n < 2 or first is None:
        return None
    measured = last - first
    return Account(n=n, predicted=predicted, measured=measured,
                   ratio=(predicted / measured)
                   if abs(measured) > 1e-6 else None,
                   psi=ec.summarise(psis),
                   from_along=None, to_along=None)


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
    # AND WHY IT ENDED, BY NAME. A session recorded before F4 Task 2.5
    # has no `outcome` line at all, which is `loc=none`'s rule: a
    # missing line is an older bench and not a value, so it is named as
    # such rather than defaulted to `ran`.
    outcome = fields.get("outcome")
    if outcome is None:
        print("outcome   UNRECORDED - this session predates the "
              "fail-fast guards")
    elif outcome == "no_progress":
        print("outcome   NO PROGRESS - the bench's watchdog abandoned it. "
              "It was {} m".format(fields.get("no_progress_distance_m", "?")))
        print("          from the goal in the pose the checker sees, "
              "having gone {} s".format(fields.get("no_progress_since_s",
                                                   "?")))
        print("          without closing {} m on its best of {} m. "
              "config.yaml".format(
                  cfg.s("nav.watchdog.required_closing_m"),
                  fields.get("no_progress_mark_m", "?")))
        print("          nav.watchdog owns the rule; "
              "drive_goal.ClosingWatch is it.")
    elif outcome == "timeout":
        print("outcome   TIMEOUT - nav.goal_timeout_s, which is the LAST "
              "resort and not")
        print("          a fail-fast. A run that reaches it got past both "
              "guards.")
    else:
        print("outcome   {} - nav2 finished this run itself".format(outcome))
    if fields.get("nav_config_md5"):
        same = fields.get("nav_params_md5") == fields.get("nav_config_md5")
        print("config    the PARAMETERS this run was driven by hash to "
              "{}".format(fields["nav_config_md5"]))
        if not same:
            print("          (the FILE hashes to {} - the difference "
                  "between the two is".format(
                      fields.get("nav_params_md5", "?")))
            print("          comments, and only the first of them is a "
                  "claim about the stack)")
    if fields.get("nav_budget_ms"):
        print("budget    the tree carries a {:g} s navigation budget "
              "({}@{})".format(
                  float(fields["nav_budget_ms"]) / 1000.0,
                  os.path.basename(fields.get("nav_bt", "?")),
                  fields.get("nav_bt_md5", "?")))

    # A RUN IN WHICH THE VEHICLE NEVER MOVED IS A RECORDING AND NOT A
    # BROKEN ONE, and F4 Task 2.5 is why this exception exists. The
    # fail-fast has to be demonstrated on a goal that CANNOT be reached;
    # `nav.goals.rack_sw3` is inside a rack, the planner refuses it
    # ("no valid path found") and the controller therefore publishes
    # nothing at all - so `cmd_vel`, `cmd_vel_smoothed` and both
    # terminals are EMPTY. Refusing that session would mean this bench
    # could not read its own most important demonstration, and the
    # streams that are empty are empty for the reason being
    # demonstrated.
    #   THE POSE STREAMS ARE STILL REQUIRED. Ground truth and both /tf
    # edges come from the plant and the estimator, which run whether or
    # not anything is commanded, so a session missing THOSE is a
    # recording that went wrong and is still refused by name.
    commanded = tables["cmd_vel"].n > 0
    for stream, table in tables.items():
        if stream in ("plan", "feedback"):
            continue
        if not commanded and stream in COMMANDED_STREAMS:
            continue
        if table.n < cfg.i("evidence.min_samples"):
            raise ec.EvidenceError(
                "{}: {} recorded {} rows, under evidence.min_samples"
                .format(session, stream, table.n))

    # ---- the case, if this session is one -----------------------------
    # F4 TASK 3. A session with no `case=` line is a ONE-GOAL run and
    # every block below reads exactly as it always has; `loc=none`'s
    # rule, one label over.
    if fields.get("case"):
        print("case      {}  -  {}".format(
            fields["case"],
            (cfg.raw("nav.cases").get(fields["case"]) or {}).get("note", "")))
        print("          goal 1 {}, sent at t+0.000 s".format(
            fields.get("case_first", "?")))
        if fields.get("case_second"):
            print("          goal 2 {}, {}".format(
                fields["case_second"],
                "PREEMPT at a believed {} m"
                .format(fields.get("case_preempt_at_m", "?"))
                if fields.get("case_when") == "preempt"
                else "sent AFTER goal 1 returned"))
            print("          THE ARRIVAL BELOW IS SCORED AGAINST GOAL 2, "
                  "which is where the")
            print("          vehicle ended. Goal 1's own result is in the "
                  "LEGS block.")

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
    world = []
    if parent and child:
        gap_s = cfg.f("nav.analyse.map_gap_s")
        composed = ec.compose_rows(parent, child, gap_s)
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

    # ---- and the nearest it ever GOT, which is the other question ----
    # THE ARRIVAL FIGURE ABOVE SCORES WHERE THE TRUCK STOPPED. On a run
    # that did not arrive that is wherever the controller gave up, and
    # it says the run failed without saying why. This says how close it
    # came and which way it was out when it was closest - the difference
    # between "it never got there" and "it went past on the wrong side".
    near = closest_approach(goal, truth, t_sent, t_done)
    if near is None:
        print("CLOSEST   no ground-truth sample between the goal being "
              "sent and the result")
    else:
        print("CLOSEST   t+{:.1f}s  ({:+.4f}, {:+.4f}) yaw {:+.4f}   "
              "d = {:.4f} m".format(near.t - t_sent, near.x, near.y,
                                    near.yaw, near.distance))
        print("          dx {:+.4f}  dy {:+.4f}   (metres east and north "
              "in the building)".format(near.dx, near.dy))
        print("          ALONG {:+.4f}  ACROSS {:+.4f}   of the goal's "
              "own travel heading".format(near.along, near.across))
        print("          across is + to the LEFT of it. THE GOAL BOX IS "
              "A CRITERION ABOUT")
        print("          A MOVING VEHICLE, because `stateful` latches "
              "the first time it is")
        print("          inside - which is why this row and not the "
              "resting one is the one")
        print("          the box has to be sized against.")
    # AND THE SAME SCAN OVER THE POSE THE CHECKER ACTUALLY SAW. The box
    # is evaluated on `map` -> `base_link`, not on the ground truth, so
    # a run can arrive with the TRUTH outside the box and a run can miss
    # with the truth inside it. Printing only one of the two would make
    # the other look like an instrument error.
    nearb = closest_approach(goal, world, t_sent, t_done) if world else None
    if nearb is not None:
        print("          BELIEVED closest t+{:.1f}s  d = {:.4f} m   "
              "ALONG {:+.4f}  ACROSS {:+.4f}".format(
                  nearb.t - t_sent, nearb.distance, nearb.along,
                  nearb.across))
        print("          truth - believed AT THAT MOMENT = {:.4f} m; the "
              "box saw the second".format(
                  math.hypot(near.x - nearb.x, near.y - nearb.y)
                  if near is not None else float("nan")))

    # ---- AND WHAT EACH CANDIDATE BOX WOULD HAVE COST IN HEADING ------
    # DELIVERABLE 4's INSTRUMENT. The CLOSEST row above says where the
    # vehicle got to. This says what it would have cost to demand more:
    # the box decides how far into the endgame the vehicle drives, and
    # the endgame is where a tricycle spends its heading. nav2.yaml's
    # general_goal_checker quotes this table and F5's docking inherits
    # the ruling it carries.
    if world:
        rungs, closest_seen = approach_corridor(
            goal, world, truth, t_sent, t_done,
            cfg.raw("nav.analyse.corridor_boxes"),
            cfg.f("nav.analyse.corridor_give_up_m"))
        if rungs:
            print("CORRIDOR  the FIRST approach, cut where it gave up. "
                  "Closest belief on it:")
            print("          {:.4f} m.  box | believed | truth | "
                  "|heading error|".format(closest_seen))
            for rung in rungs:
                print("          {:5.2f} m  {:8.4f}  {:8s}  {:.4f} rad "
                      "({:4.1f} deg)  t+{:.1f}s".format(
                          rung.box, rung.believed,
                          "{:.4f}".format(rung.truth)
                          if rung.truth is not None else "-",
                          rung.dyaw, math.degrees(rung.dyaw),
                          rung.t - t_sent))
            print("          A BOX THE RUN NEVER REACHED IS ABSENT and "
                  "not reported as its")
            print("          own closest approach. The heading column is "
                  "what a tighter box")
            print("          would have had to accept - it is not "
                  "required by this checker")
            print("          (nav2.yaml general_goal_checker is "
                  "position-only) and it is")
            print("          what a station-class arrival would have to "
                  "buy back with a")
            print("          STRAIGHT final leg. EVIDENCE_NAV_V3.md 16.6.")

    if not commanded:
        print("")
        print("STILL     THE CONTROLLER NEVER PUBLISHED A TWIST, so every "
              "block below this")
        print("          one is absent rather than empty. {} plan(s) were "
              "published and".format(len(plans_of(tables["plan"]))))
        print("          the vehicle did not move: on this track that is "
              "what a goal the")
        print("          planner REFUSES looks like from the outside. Read "
              "the outcome")
        print("          line above and m5_ver3/logs/planner_server.log.")
        return

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
    deadband = cfg.f("nav.analyse.cusp_speed_mps")
    curves = [c for c in (curvature_of(row[2], row[3], deadband)
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
    # CARRIED INTO THE BUILDING FIRST. nav2 publishes /plan in the MAP
    # frame; the truth is the world's. See plans_of().
    plans = plans_of(tables["plan"], frame)
    print("")
    print("PLAN      {} plan(s) published; the tree replans at 1 Hz".format(
        len(plans)))
    if plans:
        for label, (_at, poses) in (("first", plans[0]), ("last", plans[-1])):
            fwd, rev = plan_directions(poses)
            print("          {:<5} plan {:>4} poses, {:7.3f} m, {} forward "
                  "and {} REVERSE segments".format(
                      label, len(poses),
                      ec.polyline_length([(x, y) for x, y, _ in poses]),
                      fwd, rev))
        print("          nav2 FORWARD is counterweight-first on this "
              "vehicle; nav2 REVERSE")
        print("          is forks-first, which is its ordinary direction "
              "of travel.")
        deviation = []
        for row in truth:
            if not (t_sent <= row[0] <= t_done):
                continue
            poly = plan_standing_at(plans, row[0])
            if not poly:
                continue
            deviation.append(ec.point_to_polyline(
                row[1], row[2], [(x, y) for x, y, _ in poly]))
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

    # ---- COULD THE ALIGN CRITIC HAVE SCORED AT ALL? ------------------
    # THE FIGURE THE WHOLE DIAGNOSIS TURNS ON, AS AN INSTRUMENT.
    # PathAlignCritic returns without scoring unless the prediction
    # horizon reaches `offset_from_furthest` path points, and
    # EVIDENCE_NAV_V3.md 16.2 is what that cost. The four numbers come
    # off the nav2.yaml ON DISK, so a session driven behind a different
    # one is scanned against the wrong horizon - which is why the label
    # is checked and named rather than assumed.
    params = os.path.join(_common.REPO, cfg.s("nav.params_file"))
    if fields.get("nav_time_steps"):
        mppi = MppiWindow(
            horizon_m=(float(fields["nav_time_steps"])
                       * float(fields["nav_model_dt"])
                       * float(fields["nav_vx_max"])),
            gate=int(fields["nav_align_gate"]),
            steps=int(fields["nav_time_steps"]),
            model_dt=float(fields["nav_model_dt"]),
            vx_max=float(fields["nav_vx_max"]))
        from_session = True
    else:
        mppi = mppi_window(params)
        from_session = False
    scan = align_gate_scan(plans, truth, speed, mppi, t_sent, t_done,
                           cfg.f("nav.analyse.follow_speed_mps"))
    print("")
    print("ALIGN     PathAlignCritic scores only where the horizon "
          "reaches its gate.")
    print("          horizon {:.4f} m = time_steps {} x model_dt {:g} x "
          "vx_max {:g};".format(mppi.horizon_m, mppi.steps,
                                mppi.model_dt, mppi.vx_max))
    print("          gate offset_from_furthest = {}".format(mppi.gate))
    print("          read off {}".format(
        "THIS SESSION" if from_session
        else "the nav2.yaml ON DISK - this session predates the four "
             "window fields"))
    on_disk = nav_label(cfg)["nav_params_md5"]
    if not from_session and fields.get("nav_params_md5") not in (None,
                                                                on_disk):
        print("          THIS SESSION WAS DRIVEN BEHIND {} AND THE FILE "
              "ON DISK IS {}.".format(fields["nav_params_md5"], on_disk))
        print("          The four numbers above are the FILE's. If the "
              "two differ in a")
        print("          VALUE the scan below is about a stack this run "
              "was not driven by;")
        print("          nav_config_md5 is what says which.")
    if scan is None:
        print("          no plan was published while the vehicle was "
              "moving - nothing to scan")
    else:
        print("          {} plan(s) scanned, {} dropped at a "
              "standstill".format(scan.n, scan.at_rest))
        print("            reachable path index: {}".format(scan.index))
        print("            horizon reached, m:   {}".format(scan.reach))
        print("          COULD HAVE CLEARED THE GATE: **{} of {}**"
              .format(scan.cleared, scan.n))
        print("          THE INDEX IS AN UPPER BOUND - a trajectory that "
              "followed the plan")
        print("          exactly would reach it and a real sample "
              "reaches it or less - so")
        print("          `0 of n` is the stronger claim, not the weaker "
              "one.")

    # ---- AND HOW MUCH OF THE MISS THE HEADING ALONE EXPLAINS ---------
    # 16.1 (b) and (c) died to this one. A vehicle at |v| with its
    # course psi off the goal's travel heading moves sideways at
    # |v|*sin(psi); integrating it over the transit says how much of the
    # ACROSS miss is just that, and how much is left for the localiser,
    # the jumps or the replans.
    account = heading_account(goal, truth, speed, t_sent, t_done,
                              cfg.f("nav.analyse.transit_margin_m"))
    if account is not None:
        print("")
        print("HEADING   the lateral miss, accounted for by the heading "
              "error alone")
        print("          over the transit ({} samples, stopped {:g} m "
              "short along track):".format(
                  account.n, cfg.f("nav.analyse.transit_margin_m")))
        print("            predicted  {:+.4f} m   = integral of "
              "|v|*sin(psi) dt".format(account.predicted))
        print("            measured   {:+.4f} m   = what the ACROSS "
              "component did".format(account.measured))
        print("            ratio      {}".format(
            "{:.3f}".format(account.ratio) if account.ratio is not None
            else "none (nothing drifted)"))
        print("            psi        {}".format(account.psi))
        print("          A RATIO NEAR 1.0 LEAVES NOTHING FOR ANYTHING "
              "ELSE. F4 Task 2's")
        print("          two runs read 0.974 and 1.059, which is what "
              "killed the jump")
        print("          and replan hypotheses. EVIDENCE_NAV_V3.md 16.1.")

    # ---- IS THE CONTROLLER STEERING THE PATH, OR MERELY ON IT? -------
    # THE QUESTION THE DEVIATION FIGURE ABOVE CANNOT ASK. Every plan is
    # anchored at the vehicle's own pose, so a vehicle that never turns
    # is on its path by construction and the deviation stays small. F4
    # Task 2 measured 0.040-0.113 m of it on runs that missed by a
    # metre. This takes the plan's own curvature at the vehicle, turns
    # it into the yaw rate that curvature requires at the speed being
    # driven, and asks what fraction of it the controller commanded.
    # EVIDENCE_NAV_V3.md 16 is what it found.
    if plans and cmd:
        required, commanded = curvature_demand(
            cmd, truth, plans, t_sent, t_done,
            cfg.f("nav.analyse.follow_speed_mps"),
            cfg.i("nav.analyse.curvature_span"))
        if required:
            follow = curvature_following(required, commanded)
            print("          CURVATURE FOLLOWING over {} commanded twists "
                  "above the creep".format(follow.n))
            print("            the plan required   {}".format(
                follow.required))
            print("            the controller gave {}".format(
                follow.commanded))
            print("            DEMAND rms {:.4f} rad/s   GAIN {}   "
                  "r {}".format(
                      follow.demand_rms,
                      "{:.4f}".format(follow.gain)
                      if follow.gain is not None
                      else "none (the plan asked for no turn at all)",
                      "{:+.3f}".format(follow.r) if follow.r is not None
                      else "none"))
            print("          GAIN 1.0 is a controller that obeys its "
                  "plan's curvature and")
            print("          0.0 is one that ignores it - but IT IS ONLY "
                  "A MEASUREMENT OF THE")
            print("          CONTROLLER WHERE THE DEMAND IS REAL, so the "
                  "two are read")
            print("          together. F4 Task 2's runs asked for a "
                  "demand rms of 0.06-0.09")
            print("          rad/s - a quarter of wz_max - and got gains "
                  "of 0.049, -0.011")
            print("          and -0.052. A CLOSED LOOP ASKS FOR ALMOST "
                  "NOTHING, because it")
            print("          never leaves the line, so a small gain over "
                  "a small demand is a")
            print("          plan with no correction in it - which is "
                  "the point rather than")
            print("          a fault. EVIDENCE_NAV_V3.md 16.2.")

    # ---- the jumps, and what the controller did about them -----------
    print("")
    if parent:
        jumps = ec.tf_jumps(parent)
        print("JUMPS     {} corrections in {} broadcasts over {:.1f} s "
              "({:.3f} /s)".format(jumps.n, jumps.samples, jumps.span_s,
                                   jumps.per_s or 0.0))
        if jumps.n:
            # THE F3 FIGURE IS THE OPEN-LOOP ONE AND A CLOSED-LOOP RUN
            # IS EXPECTED TO EXCEED IT. Without this pointer a legal
            # 1.19 m step reads as a breach of the contract, which is
            # the opposite of what the two addenda say: 13.10a moved
            # the closed-loop bound to 0.8310 m and 13.10b to 1.1919 m
            # on the amcl arm / 0.8845 m on slam, with no maximum
            # established. The HEADING half has held at F3's figure
            # through all three.
            print("          worst step {:.4f} m / {:.4f} rad; F3 handed "
                  "over 0.2591 m / 0.0764 rad OPEN LOOP".format(
                      jumps.max_dpos_m, jumps.max_dyaw_rad))
            print("          a CLOSED loop is expected to exceed the "
                  "position half and does:")
            print("          EVIDENCE_LOCALIZATION_V3.md 13.10a -> "
                  "0.8310 m, 13.10b -> 1.1919 m (amcl)")
            print("          / 0.8845 m (slam), and 13.10b establishes "
                  "NO maximum. Size on your own arm.")
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

    # ---- how far the heading wandered, which 16.4c had no instrument
    # for ------------------------------------------------------------
    # THE WINDOW IS THE LAST LEG'S AND NOT THE WHOLE RUN'S, because psi
    # is measured against the GOAL's travel heading and a two-goal case
    # spends its first leg driving somewhere else. On a one-goal run the
    # two are the same instant.
    t_swing = float(fields["t_goal2_sent_s"])         if fields.get("t_goal2_sent_s") else t_sent
    swing = heading_swing(goal.travel_yaw, truth, speed, t_swing, t_done,
                          cfg.f("nav.analyse.follow_speed_mps"))
    if swing is not None:
        print("")
        print("SWING     psi, the vehicle's TRAVEL heading against the "
              "goal's own, off the")
        print("          ground truth, over the {} samples above "
              "{:g} m/s{}".format(
                  swing.n, cfg.f("nav.analyse.follow_speed_mps"),
                  " of the LAST leg" if t_swing != t_sent else ""))
        print("          mean {:+.4f}   sd {:.4f}   worst |psi| {:.4f} rad"
              .format(swing.mean, swing.sd, swing.worst))
        print("          IT IS ONLY A SWING ON A STRAIGHT LEG. A route "
              "with a corner in it")
        print("          spends part of its run legitimately pointed "
              "somewhere else, and this")
        print("          statistic reads that as spread: `spine_north` "
              "and `ring_corner` are")
        print("          straight, `aisle_end` and the station goals are "
              "not.")
        print("          16.4c's RESIDUAL IS BIMODAL IN THIS STATISTIC: "
              "a run either locks")
        print("          onto its route at about 0.20 rad of swing or "
              "oscillates at about")
        print("          0.55 and does not recover. It is which side of "
              "a stability")
        print("          boundary the run landed on, not a degradation.")

    # ---- the legs, the switch and the cusps ---------------------------
    # F4 TASK 3, AND ALL THREE ARE ABSENT ON A ONE-GOAL RUN WITH NO
    # DIRECTION CHANGE IN IT - which is every session §15 and §16
    # recorded. Nothing above this line moved.
    if fields.get("case") and commanded:
        t_leg1 = float(fields.get("t_leg1_end_s", t_sent))
        t_two = float(fields["t_goal2_sent_s"]) \
            if fields.get("t_goal2_sent_s") else None
        print("")
        print("LEGS      what each errand cost, off the ground truth and "
              "the action's own")
        print("          status. nav2's codes: 4 SUCCEEDED, 5 CANCELED, "
              "6 ABORTED.")
        legs = [("1 " + fields.get("case_first", "?"), t_sent,
                 t_two if t_two is not None else t_leg1,
                 int(fields.get("leg1_status", -1)),
                 int(fields.get("leg1_error_code", -1)))]
        if t_two is not None:
            legs.append(("2 " + fields.get("case_second", "?"), t_two,
                         t_done, int(fields.get("action_status", -1)),
                         int(fields.get("error_code", -1))))
        for label, lo, hi, status, code in legs:
            inside = [row for row in truth if lo <= row[0] <= hi]
            driven = math.fsum(
                math.hypot(b[1] - a[1], b[2] - a[2])
                for a, b in zip(inside, inside[1:])) if len(inside) > 1 else 0.0
            print("          leg {:<22} {:7.2f} s  {:7.3f} m  status {:>2}"
                  "  error {}".format(label, hi - lo, driven, status, code))
            # AND THE #5714 SPLIT, PER LEG. nav2's FORWARD is
            # counterweight-first on this vehicle and its REVERSE is
            # ordinary travel, so a leg that drove one way prints one
            # row and a session that drove both ways prints the A/B
            # issue #5714 is about. A direction never driven is ABSENT
            # and not zero.
            fwd, rev = deviation_by_direction(
                truth, cmd, plans, lo, hi,
                cfg.f("nav.analyse.cusp_speed_mps"))
            for name, half in (("nav2 REVERSE  (forks-first)", rev),
                               ("nav2 FORWARD  (counterweight)", fwd)):
                if half is None:
                    print("            {:<30} not driven on this leg"
                          .format(name))
                else:
                    print("            {:<30} n {:>5}  deviation mean "
                          "{:.4f}  max {:.4f} m".format(
                              name, half.n, half.mean, half.worst))

        if fields.get("t_preempt_s"):
            t_switch = float(fields["t_preempt_s"])
            print("")
            print("PREEMPT   goal 2 was sent at t+{:.3f} s, with goal 1 "
                  "still running and".format(t_switch - t_sent))
            print("          the believed distance to goal 1 at {:.4f} m "
                  "(trigger {} m)".format(
                      float(fields["preempt_distance_m"]),
                      fields.get("case_preempt_at_m", "?")))
            print("          NOTHING WAS CANCELLED AND NOTHING WAS "
                  "PUBLISHED BY THIS BENCH.")
            print("          navigate_to_pose is a single-goal server: "
                  "nav2 aborted goal 1")
            print("          itself, which is the `status {}` on the leg "
                  "above.".format(fields.get("leg1_status", "?")))
            span = cfg.f("nav.analyse.jump_response_s")
            answer = preempt_response(cmd, t_switch, span)
            if answer is None:
                print("          (no commands either side of the switch "
                      "inside {:g} s)".format(span))
            else:
                print("          over +-{:g} s of {}: {} commands before, "
                      "{} after".format(span, cfg.s("topics.cmd_vel"),
                                        answer.n_before, answer.n_after))
                # THE COMPARISON IS THE RUN'S OWN MEDIAN PERIOD AND
                # NOT A NUMBER OUT OF A FILE, because what a gap has to
                # be read against is what this controller was actually
                # holding on this run.
                stamps = sorted(row[0] for row in cmd)
                steps = sorted(b - a for a, b in zip(stamps, stamps[1:]))
                median_dt = steps[len(steps) // 2] if steps else 0.0
                print("          WORST GAP IN THE COMMAND STREAM  "
                      "{:.4f} s  (this run's median period {:.4f} s)"
                      .format(answer.gap_s, median_dt))
                print("          smallest |v| commanded AFTER the switch "
                      "{:.4f} m/s".format(answer.min_v_after))
                print("          mean |v| before {:.4f} -> after {:.4f} "
                      "m/s".format(answer.mean_v_before,
                                   answer.mean_v_after))
                print("          back to 95 % of the pre-switch mean in "
                      "{}".format(
                          "{:.3f} s".format(answer.recover_s)
                          if answer.recover_s is not None
                          else "NEVER, inside the window"))
                print("          A GAP AT THE CONTROLLER'S OWN PERIOD IS "
                      "NO GAP AT ALL. What this")
                print("          block is looking for is a vehicle that "
                      "BRAKED for a re-task")
                print("          that changed nothing about where it was "
                      "going next.")
            # AND WHEN THE NEW GOAL'S PLAN EXISTED, which is the other
            # half of a preemption: a command stream that never stopped
            # is worth nothing if it was following the old path.
            first_new = None
            for at, poses in plans:
                if at < t_switch or not poses:
                    continue
                end = poses[-1]
                if math.hypot(end[0] - goal.x, end[1] - goal.y) < 0.5:
                    first_new = at
                    break
            print("          a plan ENDING AT GOAL 2 was published {}"
                  .format("{:.3f} s after the switch".format(
                      first_new - t_switch) if first_new is not None
                      else "NEVER on this run"))

    if commanded:
        cusps_driven = driven_cusps(
            cmd, cfg.f("nav.analyse.cusp_speed_mps"))
        plan_now = plan_standing_at(plans, t_done) if plans else None
        cusps_planned = plan_cusps(plan_now) if plan_now else []
        if cusps_driven or cusps_planned:
            print("")
            print("CUSPS     a Reeds-Shepp cusp is a direction change the "
                  "vehicle has to stop")
            print("          at, slew the steer axis across and set off "
                  "the other way for.")
            print("          nav2 issue #5714 is open on tracking through "
                  "exactly these, worst")
            print("          in REVERSE turns - and on this vehicle every "
                  "ordinary leg IS a")
            print("          nav2 reverse leg. F4 constraint 19: measured, "
                  "not tuned around.")
            print("          DRIVEN (a sign change in the commanded v, "
                  "above the {:g} m/s".format(
                      cfg.f("nav.analyse.cusp_speed_mps")))
            print("          deadband): {}".format(len(cusps_driven)))
            span = cfg.f("nav.analyse.jump_response_s")
            for t_c, v_a, v_b in cusps_driven:
                inside = [row for row in truth
                          if t_c - span <= row[0] < t_c + span]
                errs = []
                for row in inside:
                    standing = plan_standing_at(plans, row[0])
                    if standing:
                        errs.append(min(math.hypot(row[1] - p[0],
                                                   row[2] - p[1])
                                        for p in standing))
                print("            t+{:7.2f} s  {:+.4f} -> {:+.4f} m/s   "
                      "deviation over +-{:g} s: {}".format(
                          t_c - t_sent, v_a, v_b, span,
                          "mean {:.4f} max {:.4f} m".format(
                              math.fsum(errs) / len(errs), max(errs))
                          if errs else "(no plan standing)"))
            print("          PLANNED (the last plan of the run): {}".format(
                len(cusps_planned)))
            for _i, x, y, s, run in cusps_planned:
                print("            world ({:+.3f}, {:+.3f})  {:.3f} m "
                      "along it, then {:.3f} m the other way{}".format(
                          x, y, s, run,
                          "   <- ONE POSE, lattice noise"
                          if run <= 0.11 else ""))
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
        # AND `monitor` IS THE FIFTH SINCE F4 TASK 3, for nav='s reason
        # one link further down the command path: a session recorded
        # with a guard between the smoother and the converter went
        # through a DIFFERENT LINE from one recorded without, and the
        # two produce CSVs of identical shape off identical topics.
        #   A SESSION WITH NO monitor= LINE READS `UNLABELLED` AND IS
        # NOT INFERRED TO BE `off`. It was recorded by a bench older
        # than the label, which is a fact about the BENCH; `loc=none`'s
        # rule, one label over.
        key = "  ".join(fields.get(k, "UNLABELLED")
                        for k in ("traction", "arm", "loc", "nav",
                                  "monitor", "dock"))
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
                   "{} different traction/arm/loc/nav/monitor/dock combinations "
                   "are in this set:".format(len(seen)), *lines)
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

def probe(cfg, goal):
    """Ask the PLANNER alone what it would do, and command no motion.

    F4 TASK 3, AND IT EXISTS BECAUSE A CASE HAS TO BE CHOSEN RATHER THAN
    GUESSED. The reverse-leg case needs a start/goal pair the planner
    solves with a CUSP; whether any given pair produces one is a
    property of SmacPlannerHybrid's Reeds-Shepp expansion over this
    floor's inflation, and the only honest way to find out is to ask it.

    IT IS tools/nav_health.py's ACTION AND NOT drive_goal's.
    `compute_path_to_pose` is the PLANNER's; it never reaches the
    controller, nothing is published on /cmd_vel and the truck does not
    move. What comes back is scored by the same two committed functions
    `analyse` uses on a recorded plan - `plan_directions` and
    `plan_cusps` - so a probe and a drive cannot disagree about what a
    cusp is.
    """
    try:
        import rclpy
        from nav2_msgs.action import ComputePathToPose
        from geometry_msgs.msg import PoseStamped
        from rclpy.action import ActionClient
        from rclpy.node import Node
    except ImportError as exc:
        cfg.refuse("rclpy and nav2_msgs are importable",
                   _common.CONFIG + " (paths.ros_setup)",
                   "python3 could not import what this bench needs: "
                   "{}".format(exc),
                   "it runs INSIDE WSL with /opt/ros/jazzy sourced.")

    print("=== m5v3 nav plan probe ===")
    # WHERE THIS BRINGUP'S LOGS ARE, read off the state file the running
    # stack wrote. Until F4's closing wave every bringup truncated the
    # last one's, so the refusal below used to point at a file the next
    # start had already replaced.
    log_dir = os.path.join("m5_ver3", cfg.s("paths.log_dir").split("/")[-1])
    state_path = os.path.join(_common.REPO, cfg.s("paths.traction_file"))
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as handle:
            log_dir = ec.stack_log_dir(
                ec.parse_state_file(handle.read()),
                os.path.join(_common.REPO, cfg.s("paths.log_dir")))
    frame, at_map = goal_in_map(cfg, goal)
    describe(cfg, goal)
    print("")
    print("NOTHING IS COMMANDED. compute_path_to_pose is the PLANNER's "
          "action and never")
    print("reaches the controller. The truck does not move.")
    print("")

    rclpy.init(args=None)
    node = Node("m5v3_plan_probe")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    wait_s = cfg.f("evidence.wait_first_s")
    action = ActionClient(node, ComputePathToPose, "compute_path_to_pose")
    if not action.wait_for_server(timeout_sec=wait_s):
        cfg.refuse("planner_server advertised compute_path_to_pose "
                   "within {:g}s".format(wait_s),
                   "compute_path_to_pose on domain {}".format(
                       cfg.s("isolation.ros_domain_id")),
                   "is the nav arm up? "
                   "'bash m5_ver3/m5v3.sh status'")
    request = ComputePathToPose.Goal()
    request.goal = PoseStamped()
    request.goal.header.frame_id = cfg.s("frames.map")
    request.goal.pose.position.x = float(at_map[0])
    request.goal.pose.position.y = float(at_map[1])
    request.goal.pose.orientation.z = math.sin(float(at_map[2]) / 2.0)
    request.goal.pose.orientation.w = math.cos(float(at_map[2]) / 2.0)
    # use_start FALSE: plan from where the vehicle IS, which is what a
    # driven goal would do. There is no start pose in this request.
    request.use_start = False
    send = action.send_goal_async(request)
    rclpy.spin_until_future_complete(node, send, timeout_sec=wait_s)
    handle = send.result() if send.done() else None
    if handle is None or not handle.accepted:
        print("REFUSED    planner_server did not accept the request.")
        node.destroy_node()
        rclpy.shutdown()
        return 1
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future,
                                     timeout_sec=cfg.f("nav.health."
                                                       "action_timeout_s"))
    outcome = result_future.result() if result_future.done() else None
    if outcome is None:
        print("REFUSED    the planner did not answer inside the budget.")
        node.destroy_node()
        rclpy.shutdown()
        return 1
    status = int(outcome.status)
    poses = [(p.pose.position.x, p.pose.position.y,
              math.atan2(2.0 * (p.pose.orientation.w * p.pose.orientation.z),
                         1.0 - 2.0 * (p.pose.orientation.z ** 2)))
             for p in outcome.result.path.poses]
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    if status != 4 or not poses:
        print("NO PATH    action status {}, error_code {} - the planner "
              "REFUSED this goal.".format(
                  status, int(getattr(outcome.result, "error_code", -1))))
        print("           THAT IS A MEASUREMENT AND THE PLANNER SAID WHY. "
              "Read it here, and it")
        print("           will still be there after the next bringup "
              "(config.yaml paths.log_dir):")
        print("             {}/planner_server.log".format(log_dir))
        print("           nav2 numbers ComputePathToPose's own codes from "
              "200: 203 START_OUTSIDE_MAP,")
        print("           205 START_OCCUPIED, 206 GOAL_OCCUPIED, 208 "
              "NO_VALID_PATH. FollowPath numbers")
        print("           from 100, so a 2xx here is the PLANNER and never "
              "the controller.")
        return 1
    world = [frame.to_world(*pose) for pose in poses]
    length = math.fsum(math.hypot(b[0] - a[0], b[1] - a[1])
                       for a, b in zip(world, world[1:]))
    forward, reverse = plan_directions(world)
    cusps = plan_cusps(world)
    print("PLAN       {} poses, {:.3f} m of path, status {}".format(
        len(poses), length, status))
    print("           first world ({:+.3f}, {:+.3f})  last ({:+.3f}, "
          "{:+.3f})".format(world[0][0], world[0][1],
                            world[-1][0], world[-1][1]))
    print("           segments: {} nav2-FORWARD (counterweight-first), "
          "{} nav2-REVERSE".format(forward, reverse))
    print("           (forks-first, which is this truck's ordinary "
          "direction of travel)")
    print("CUSPS      {}".format(len(cusps)))
    for i, x, y, s, run in cusps:
        print("           pose {:>4}  world ({:+.3f}, {:+.3f})  "
              "{:.3f} m along the path, then {:.3f} m the other "
              "way{}".format(i, x, y, s, run,
                             "   <- ONE POSE, lattice noise"
                             if run <= 0.11 else ""))
    if not cusps:
        print("           none - the planner solved this pair in ONE "
              "direction. A pair")
        print("           that cannot produce a cusp cannot measure "
              "tracking through one.")
    return 0


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

    # ONE GOAL, OR A CASE THAT IS TWO OF THEM AND A RULE. F4 Task 3.
    # `goal` below is always the goal the ARRIVAL is scored against,
    # which is the LAST one sent either way; `first` is what is sent at
    # t_sent. On a one-goal run the two are the same object.
    case = getattr(args, "case_row", None)
    if case is None:
        goal = first_goal = read_goal(cfg, args.goal)
        print("=== m5v3 nav goal ===")
        at_map = at_first = describe(cfg, goal)
        at_second = None
    else:
        print("=== m5v3 nav case ===")
        at_first, at_second = describe_case(cfg, case)
        first_goal = case.first
        goal = case.second or case.first
        at_map = at_second if at_second is not None else at_first
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
    # A CASE'S SESSION IS NAMED FOR THE CASE AND NOT FOR ONE OF ITS TWO
    # GOALS, because neither of them is what was driven. `sessions_in`
    # takes both prefixes and `analyse` reads the goal off session.txt,
    # never off the directory name.
    session = "{}-{}-{}".format("case" if case else "goal",
                                case.name if case else goal.name, stamp)
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

    # THE BELIEVED POSE, LIVE. `analyse` composes these two edges off the
    # CSVs afterwards (evidence_core.compose_rows); the watchdog below
    # needs the same pose while the run is still happening, so the
    # newest of each edge is kept and composed on arrival. It is the MAP
    # frame throughout and no registration is in it - the goal was
    # carried into the map before it was sent, and the goal checker
    # works in exactly that frame.
    latest = {"map_odom": None, "odom_base": None}

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
            row = (stamp_s(tr.header), tr.transform.translation.x,
                   tr.transform.translation.y, yaw_of(tr.transform.rotation))
            captured[name].append(row)
            latest[name] = row
            if name == "odom_base" and watching[0]:
                anchor = latest["map_odom"]
                if anchor is not None:
                    cos_p = math.cos(anchor[3])
                    sin_p = math.sin(anchor[3])
                    bx = anchor[1] + cos_p * row[1] - sin_p * row[2]
                    by = anchor[2] + sin_p * row[1] + cos_p * row[2]
                    believed_track.append(
                        (row[0], math.hypot(bx - target[0][0],
                                            by - target[0][1]), bx, by))

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

    watching = [False]
    believed_track = []
    # WHICH GOAL THE BELIEVED DISTANCE IS MEASURED TO, and it MOVES on a
    # two-goal case. The watchdog, the preempt trigger and the goal
    # checker all have to be asking about the same pose at the same
    # moment, so there is one place that says which pose that is.
    target = [at_first]
    watch = [ClosingWatch(cfg.f("nav.watchdog.required_closing_m"),
                          cfg.f("nav.watchdog.closing_allowance_s"))]

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

    def on_feedback(msg):
        fb = msg.feedback
        captured["feedback"].append(
            (now_s(), fb.distance_remaining,
             fb.navigation_time.sec + fb.navigation_time.nanosec * 1e-9,
             float(fb.number_of_recoveries)))

    def send_goal(which, at):
        """One navigate_to_pose goal on the wire. Returns its handle."""
        request = NavigateToPose.Goal()
        request.pose = PoseStamped()
        request.pose.header.frame_id = map_frame
        request.pose.pose.position.x = float(at[0])
        request.pose.pose.position.y = float(at[1])
        request.pose.pose.orientation.z = math.sin(float(at[2]) / 2.0)
        request.pose.pose.orientation.w = math.cos(float(at[2]) / 2.0)
        send = action.send_goal_async(request, feedback_callback=on_feedback)
        rclpy.spin_until_future_complete(node, send, timeout_sec=wait_s)
        got = send.result() if send.done() else None
        if got is None or not got.accepted:
            cfg.refuse("bt_navigator ACCEPTED the goal",
                       "{} and {} (nav.goals.{})".format(
                           NAV_ACTION, _common.CONFIG, which.name),
                       "map ({:+.4f}, {:+.4f}) yaw {:+.4f} was {}.".format(
                           at[0], at[1], at[2],
                           "not answered" if got is None else "REJECTED"),
                       "nothing further was driven.")
        return got

    # ---- LEG 1 --------------------------------------------------------
    t_sent = now_s()
    watching[0] = True
    handle = send_goal(first_goal, at_first)
    cancelled = 0
    status = -1
    error_code = -1
    print("goal sent  {} at t = {:.3f} s of sim time".format(
        first_goal.name, t_sent))
    result_future = handle.get_result_async()
    budget_s = cfg.f("nav.goal_timeout_s")
    deadline = time.monotonic() + budget_s
    outcome_name = "ran"
    stalled = None
    # THE PREEMPT TRIGGER, F4 Task 3. Armed only on `when: preempt`, and
    # it fires exactly once: the moment the BELIEVED distance to goal 1
    # first falls below the case's own threshold, goal 2 goes on the
    # wire while goal 1 is still running. navigate_to_pose is a
    # SINGLE-GOAL server, so nav2 aborts goal 1 itself - this bench
    # cancels nothing and publishes no twist (F4 constraint 18).
    preempt_armed = bool(case and case.when == "preempt")
    leg1 = {"status": -1, "error_code": -1, "t_end": None,
            "trigger_distance": None}
    preempt = {"t_s": None, "distance_m": None}
    leg1_future = None

    def drain(queue):
        """One believed sample through the trigger and then the watch."""
        while queue and stalled is None:
            sample = queue.pop(0)
            if preempt_armed and preempt["t_s"] is None \
                    and sample[1] <= case.preempt_at_m:
                preempt["t_s"] = sample[0]
                preempt["distance_m"] = sample[1]
                return "preempt"
            hit = watch[0].step(sample[0], sample[1])
            if hit is not None:
                return hit
        return None

    while not result_future.done():
        # THE NO-PROGRESS GUARD, F4 Task 2.5. Stepped on the pose the
        # GOAL CHECKER sees, it gives up on a run that has stopped
        # closing on its goal - the failure nav2's own progress checker
        # cannot see, because that one asks whether the vehicle MOVED.
        # config.yaml nav.watchdog owns both numbers and ClosingWatch
        # is the rule.
        #   IT PUBLISHES NOTHING. It cancels the action, exactly as the
        # timeout below does, and the controller's own
        # publish_zero_velocity leaves the standing zero on /cmd_vel
        # (F4 constraint 18).
        hit = drain(believed_track)
        if hit == "preempt":
            print("")
            print("PREEMPT    the believed distance to {} reached "
                  "{:.4f} m at t = {:.3f} s".format(
                      first_goal.name, preempt["distance_m"],
                      preempt["t_s"]))
            print("           (trigger {:.2f} m, config.yaml "
                  "nav.cases.{}.preempt_at_m)".format(
                      case.preempt_at_m, case.name))
            print("           sending {} NOW, with {} still running. "
                  "Nothing is cancelled".format(case.second.name,
                                                first_goal.name))
            print("           and nothing is published on the command "
                  "path: navigate_to_pose is a")
            print("           SINGLE-GOAL server and nav2 aborts the "
                  "first goal itself.")
            leg1["trigger_distance"] = preempt["distance_m"]
            break
        if hit is not None:
            stalled = hit
        if stalled is not None:
            print("")
            print("NO PROGRESS  the goal has not come {:.2f} m closer in "
                  "{:.0f} s -".format(watch[0].closing_m,
                                      watch[0].allowance_s))
            print("             ABANDONING. believed distance "
                  "{:.4f} m at t = {:.3f} s;".format(
                      stalled.distance, stalled.t))
            print("             the best it ever earned was {:.4f} m, "
                  "{:.1f} s earlier.".format(stalled.mark, stalled.since_s))
            print("             This is a NAMED failure and not a "
                  "timeout: it is written")
            print("             into the session as outcome=no_progress "
                  "and config.yaml")
            print("             nav.watchdog owns the two numbers "
                  "above.")
            outcome_name = "no_progress"
            cancelled = 1
            cancel = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(node, cancel, timeout_sec=10.0)
            break
        if time.monotonic() > deadline:
            print("")
            print("TIMEOUT    {:g}s elapsed and the goal has not "
                  "returned - CANCELLING.".format(budget_s))
            outcome_name = "timeout"
            cancelled = 1
            cancel = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(node, cancel, timeout_sec=10.0)
            break
        rclpy.spin_once(node, timeout_sec=0.05)
    t_leg1 = now_s()
    if result_future.done() and result_future.result() is not None:
        outcome = result_future.result()
        status = int(outcome.status)
        error_code = int(getattr(outcome.result, "error_code", -1))
    leg1["status"] = status
    leg1["error_code"] = error_code
    leg1["t_end"] = t_leg1
    t_sent2 = None
    if case is None or case.second is None:
        print("result     t = {:.3f} s, status {}, error_code {}".format(
            t_leg1, status, error_code))
        t_done = t_leg1
    else:
        print("leg 1      t = {:.3f} s, status {}, error_code {}".format(
            t_leg1, status, error_code))
        # ---- LEG 2 ----------------------------------------------------
        # `after` settles first, because the second errand starts from
        # where the first one ENDED and a vehicle still rolling has not
        # ended anywhere yet (config.yaml nav.settle_s, and the same
        # 1.02 m of stopping distance the arrival is settled for).
        if case.when == "after" and stalled is None:
            settle_first = cfg.f("nav.settle_s")
            print("settle     {:g} s before the second goal".format(
                settle_first))
            end = now_s() + settle_first
            while now_s() < end:
                rclpy.spin_once(node, timeout_sec=0.05)
        if stalled is not None:
            print("SKIPPED    goal 2 is NOT sent: the watchdog abandoned "
                  "goal 1, and a second")
            print("           errand from a vehicle that never finished "
                  "the first one would be")
            print("           a measurement of neither.")
            t_done = t_leg1
        else:
            # LEG 1's OWN RESULT IS STILL IN FLIGHT ON A PREEMPTION and
            # it is the measurement: what nav2 does to a goal that is
            # displaced by another is what "preempt semantics" means.
            # The future is kept and read after the run.
            leg1_future = result_future
            target[0] = at_second
            watch[0] = ClosingWatch(
                cfg.f("nav.watchdog.required_closing_m"),
                cfg.f("nav.watchdog.closing_allowance_s"))
            believed_track[:] = []
            t_sent2 = now_s()
            handle = send_goal(case.second, at_second)
            print("goal sent  {} at t = {:.3f} s of sim time".format(
                case.second.name, t_sent2))
            result_future = handle.get_result_async()
            deadline = time.monotonic() + budget_s
            while not result_future.done():
                hit = drain(believed_track)
                if hit is not None:
                    stalled = hit
                    print("")
                    print("NO PROGRESS  on goal 2. believed distance "
                          "{:.4f} m at t = {:.3f} s;".format(
                              stalled.distance, stalled.t))
                    print("             best {:.4f} m, {:.1f} s "
                          "earlier. ABANDONING.".format(
                              stalled.mark, stalled.since_s))
                    outcome_name = "no_progress"
                    cancelled = 1
                    cancel = handle.cancel_goal_async()
                    rclpy.spin_until_future_complete(node, cancel,
                                                     timeout_sec=10.0)
                    break
                if time.monotonic() > deadline:
                    print("")
                    print("TIMEOUT    {:g}s on goal 2 - CANCELLING."
                          .format(budget_s))
                    outcome_name = "timeout"
                    cancelled = 1
                    cancel = handle.cancel_goal_async()
                    rclpy.spin_until_future_complete(node, cancel,
                                                     timeout_sec=10.0)
                    break
                rclpy.spin_once(node, timeout_sec=0.05)
            t_done = now_s()
            status = -1
            error_code = -1
            if result_future.done() and result_future.result() is not None:
                outcome = result_future.result()
                status = int(outcome.status)
                error_code = int(getattr(outcome.result, "error_code", -1))
            print("result     t = {:.3f} s, status {}, error_code "
                  "{}".format(t_done, status, error_code))
            if leg1_future is not None and leg1_future.done() \
                    and leg1_future.result() is not None:
                leg1["status"] = int(leg1_future.result().status)
                leg1["error_code"] = int(getattr(
                    leg1_future.result().result, "error_code", -1))
                print("leg 1      the DISPLACED goal returned status {}, "
                      "error_code {}".format(leg1["status"],
                                             leg1["error_code"]))
    watching[0] = False

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
        # F4 TASK 3'S FIVE LINES, AND A SESSION WITHOUT THEM IS A
        # ONE-GOAL RUN rather than a case whose second leg went missing.
        # `loc=none`'s rule: a missing line is an older bench, not a
        # value. `goal=` stays the goal the ARRIVAL is scored against,
        # which is what every consumer of this field already means by
        # it.
        if case is not None:
            handle_out.write("case={}\n".format(case.name))
            handle_out.write("case_first={}\n".format(case.first.name))
            if case.second is not None:
                handle_out.write("case_second={}\n".format(case.second.name))
                handle_out.write("case_when={}\n".format(case.when))
                if case.when == "preempt":
                    handle_out.write("case_preempt_at_m={:.6f}\n".format(
                        case.preempt_at_m))
            handle_out.write("leg1_status={}\n".format(leg1["status"]))
            handle_out.write("leg1_error_code={}\n".format(
                leg1["error_code"]))
            handle_out.write("t_leg1_end_s={:.9f}\n".format(leg1["t_end"]))
            if preempt["t_s"] is not None:
                handle_out.write("t_preempt_s={:.9f}\n".format(
                    preempt["t_s"]))
                handle_out.write("preempt_distance_m={:.9f}\n".format(
                    preempt["distance_m"]))
            if t_sent2 is not None:
                handle_out.write("t_goal2_sent_s={:.9f}\n".format(t_sent2))
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
        # WHY THE RUN ENDED, BY NAME. `action_status` says what nav2
        # returned and `cancelled` says whether this bench asked for
        # it; neither says WHICH of the bench's guards asked. `ran` is
        # a run nav2 finished by itself - arrived, or aborted.
        handle_out.write("outcome={}\n".format(outcome_name))
        if stalled is not None:
            handle_out.write("no_progress_t_s={:.9f}\n".format(
                stalled.t))
            handle_out.write(
                "no_progress_distance_m={:.9f}\n".format(
                    stalled.distance))
            handle_out.write("no_progress_mark_m={:.9f}\n".format(
                stalled.mark))
            handle_out.write("no_progress_since_s={:.9f}\n".format(
                stalled.since_s))
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
    for name in ("describe", "record", "probe"):
        one = sub.add_parser(name)
        one.add_argument("--goal", default=None)
        # A CASE IS TWO GOALS AND A RULE (config.yaml nav.cases). It is
        # mutually exclusive with --goal by the refusal below rather
        # than by argparse, because the refusal can say why.
        one.add_argument("--case", default=None)
    ana = sub.add_parser("analyse")
    ana.add_argument("sessions", nargs="*")
    args = parser.parse_args(argv)
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    if args.cmd in ("describe", "record", "probe"):
        if args.goal and args.case:
            cfg.refuse("exactly one of --goal and --case was given",
                       _common.CONFIG + " (nav.goals, nav.cases)",
                       "--goal {} and --case {} were both given. A case "
                       "NAMES its goals;".format(args.goal, args.case),
                       "a --goal beside one would be a second opinion "
                       "about which pose this is.")
    if args.cmd == "describe":
        if args.case:
            case = read_case(cfg, args.case)
            describe_case(cfg, case)
            return 0
        describe(cfg, read_goal(cfg, args.goal or cfg.s("nav.default_goal")))
        return 0
    if args.cmd == "probe":
        if args.case:
            case = read_case(cfg, args.case)
            return probe(cfg, case.second or case.first)
        return probe(cfg, read_goal(cfg, args.goal
                                    or cfg.s("nav.default_goal")))
    if args.cmd == "record":
        if args.case:
            args.case_row = read_case(cfg, args.case)
            args.goal = args.case_row.first.name
        else:
            args.case_row = None
            args.goal = args.goal or cfg.s("nav.default_goal")
        return record(cfg, args)
    if args.cmd == "analyse":
        return analyse(cfg, args.sessions)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
