#!/usr/bin/env python3
"""nav_plan_health.py - did THIS truck's nav arm come up able to PLAN, or
come up merely ACTIVE?

    python3 m6_ver2/tools/nav_plan_health.py --vid f1   # 0 healthy, 1 refused
    python3 m6_ver2/tools/nav_plan_health.py --vid f1 --selftest

WHY IT EXISTS, AND IT IS A GAP m6_ver2/truck.sh NAMED RATHER THAN
CLOSED. `truck.sh start` proves that all six nav lifecycle nodes reached
ACTIVE - four servers and the two costmap SUB-NODES inside them - and
that `/<vid>/navigate_to_pose` is on the graph. Neither of those is the
question. A nav2 stack that is ACTIVE over an EMPTY COSTMAP is a stack
that plans nothing and says nothing about it.

  THE FAILURE, CONCRETELY, AND IT IS SHARPER ON THIS BRANCH THAN IT WAS
  ON m5_ver3's. global_costmap's static layer subscribes to `/map` on a
  TRANSIENT-LOCAL topic. Here that map is served ONCE, by a single
  un-namespaced map_server the WORLD owns, and latched for four
  late-joining AMCLs and four static layers
  (SPEC_NAMESPACING.md 4). If the durability is wrong, if the topic name
  drifted from the derived config's, or if the shared server was never
  activated, the layer waits for a message that has already been
  published and will not be published again. The costmap then holds
  nothing but NO_INFORMATION, and with `allow_unknown: false` the
  planner refuses every goal - after `max_planning_time`, once, into its
  own log. Every process is up, every lifecycle state reads active,
  `truck.sh status` reads ALIVE, and the first anybody hears of it is a
  fleet order that never moves.
    ONE SHARED MAP MEANS ONE FAILURE CAN TAKE ALL FOUR TRUCKS, and it
  can also take exactly one of them - a single AMCL that missed the
  latched publication. So the gate is PER TRUCK and runs in each
  truck's own bringup, not once for the cell.

WHAT IT DOES. One `ComputePathToPose` over a deliberately trivial goal:
`nav.health.goal_ahead_m` (2.00 m) straight ahead of the SEED pose, down
the middle of the 8.00 m ring leg the truck spawns on. SUCCEEDED is not
enough - the planner answers SUCCEEDED with a near-empty path when the
start is already inside its own `tolerance` of the goal, and that is
indistinguishable from a plan through an unconfigured costmap by any
other reading - so the result's path has to carry at least
`nav.health.min_poses`.

  THE START IS THE SEED AND NOT THE VEHICLE'S CURRENT POSE
  (`use_start: true`). This gate runs at bringup with the truck standing
  where the world spawned it, so the two are the same pose - but only
  one of them is DERIVED, from status_contract.VEHICLES through the
  committed registration, by the one piece of arithmetic
  (nav2_seed.seed_in_map) that also seeded the localiser and gated it. A
  gate that read the current pose off tf would be a gate whose goal
  moved with whatever it was measuring - and on this branch it would
  read it off a SHARED /tf carrying four trucks.

WHAT IT IS NOT. It is not an instrument: it measures nothing, records
nothing and writes no session. It is a BRINGUP GATE, run by
m6_ver2/truck.sh after nav_can_answer, and it refuses the whole bringup
if it says no. IT COMMANDS NO MOTION - `compute_path_to_pose` is the
PLANNER's action and never reaches the controller, so nothing is
published on the command path and the vehicle does not move.

WHAT IS PORTED AND WHAT IS NEW. The shape, the two-question order and
the refusal text are m5_ver3/tools/nav_health.py's, and that file is
frozen by AMR-DEC-006 and reads m5_ver3/config.yaml, so it cannot be
pointed at this truck. What is NEW here is the namespace:

  - the action is `/<vid>/compute_path_to_pose`, composed ABSOLUTELY
    rather than left relative under `-r __ns:=/<vid>`. Both work on a
    correctly namespaced child; only one of them can PRINT which truck
    it asked when it refuses, and only one of them still asks the right
    truck if the remap is ever dropped from the spawn line. truck.sh
    spells `/$VID/navigate_to_pose` the same way and for the same
    reason.
  - the config is the DERIVED m6_ver2/vehicles/<vid>/config.yaml, read
    through nav2_adapter_node.vehicle_config - the one reader on this
    branch - so this gate and the node it gates cannot read two files.
  - the LIFECYCLE half of nav_health is deliberately NOT ported.
    truck.sh's nav_can_answer already waits on all six namespaced nodes
    and on the navigate action, with its own refusal naming the costmap
    blocking rule. Making that wait twice would be a second answer to a
    question already asked; this file asks the one it cannot.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, os.pardir))
_ADAPTER = os.path.join(_M6V2, "nav2_adapter")
if _ADAPTER not in sys.path:
    sys.path.insert(0, _ADAPTER)

import _donors                                            # noqa: E402,F401

import nav2_seed                                          # noqa: E402
from nav2_adapter_node import own_args, vehicle_config    # noqa: E402
from status_contract import VEHICLES                      # noqa: E402

TOOL = "nav_plan_health"

#: MAINTENANCE OBLIGATION, the same one every reader on this track
#: carries: a key read below is a key listed here - AND THE CONVERSE.
#: The map/registration triple is not read in this file; it is read by
#: nav2_seed.seed_in_map THROUGH the cfg this file hands it, so it is a
#: key this program reads and load_config refuses a missing one by its
#: dotted name before anything is asked of the graph.
REQUIRED_KEYS = (
    "isolation.ros_domain_id",
    "frames.map", "topics.map",
    "map.dir", "map.name", "map.registration.file",
    "nav.health.timeout_s", "nav.health.goal_ahead_m",
    "nav.health.min_poses", "nav.health.action_timeout_s",
)

#: The planner's OWN action name, which is nav2's and not this track's.
#: It is not in config.yaml for the reason topics.amcl_pose is not: it
#: is the SERVER's advertised name, and this file is the only thing here
#: that says it.
PLAN_ACTION = "compute_path_to_pose"

#: The planner plugin the goal names. It has to be one of the derived
#: nav2.yaml's `planner_plugins`, and an empty string would make the
#: server pick its first - the same thing today, and no longer the same
#: thing the moment a second plugin is declared.
PLANNER_ID = "GridBased"


def plan_action(vid):
    """`/<vid>/compute_path_to_pose` - this truck's planner and no other.

    ABSOLUTE, AND THAT IS THE POINT. Four planner servers advertise this
    action under four namespaces; a relative name would be resolved by
    whatever `__ns` the spawn line happened to carry, so a dropped remap
    would silently gate f1's bringup on f2's planner.
    """
    if vid not in VEHICLES:
        raise SystemExit(
            "{}: {!r} is not a fleet vehicle id: {}".format(
                TOOL, vid, sorted(VEHICLES)))
    return "/{}/{}".format(vid, PLAN_ACTION)


def goal_ahead(seed, ahead_m):
    """`ahead_m` along the seed's own heading, in the map frame.

    ALONG THE HEADING AND NOT ALONG +x. The map frame is about a half
    turn from the building (registration.yaml theta_rad), so a goal
    written as `x + 2` would be two metres in a direction nobody chose -
    and at these seeds it would be two metres BEHIND the vehicle, which
    a Reeds-Shepp planner would happily solve with a cusp and a three
    point turn. The gate would pass and would have proved something
    else.

    IT IS THE SAME HEADING AS THE SEED, so the goal is a straight line
    the vehicle is already pointed down. The geometry is a straight line
    either way and this gate makes no claim about direction.
    """
    x, y, yaw = seed
    return (x + math.cos(yaw) * ahead_m, y + math.sin(yaw) * ahead_m, yaw)


def _selftest(vid):
    """Everything but the graph: the config, the seed, the arithmetic.

    NO ROS AND NO SIMULATOR. What it cannot check is the only thing this
    tool exists for - whether a planner answered with a path - and it
    says so rather than printing a pass it never tested.
    """
    cfg = vehicle_config(vid, TOOL, REQUIRED_KEYS)
    _frame, seed = nav2_seed.seed_in_map(cfg, vid)
    ahead_m = cfg.f("nav.health.goal_ahead_m")
    ahead = goal_ahead(seed, ahead_m)
    fails = []
    print("{} selftest for {}".format(TOOL, vid))
    print("  action  {}".format(plan_action(vid)))
    print("  seed    map ({:+.4f}, {:+.4f}) yaw {:+.5f}".format(*seed))
    print("  goal    map ({:+.4f}, {:+.4f}) yaw {:+.5f}, {:g} m ahead"
          .format(ahead[0], ahead[1], ahead[2], ahead_m))
    # THE GOAL IS AHEAD_M AWAY AND IT IS AHEAD, not beside and not
    # behind: the two numbers a wrong heading would leave right and
    # wrong respectively.
    span = math.dist(seed[:2], ahead[:2])
    if abs(span - ahead_m) > 1e-9:
        fails.append("the goal is {:g} m away, not {:g}".format(span, ahead_m))
    forward = ((ahead[0] - seed[0]) * math.cos(seed[2])
               + (ahead[1] - seed[1]) * math.sin(seed[2]))
    if forward <= 0.0:
        fails.append("the goal is not ahead of the seed")
    if plan_action(vid) != "/{}/compute_path_to_pose".format(vid):
        fails.append("the action name is not this truck's")
    for line in fails:
        print("  FAIL {}".format(line))
    if not fails:
        print("  pass  the goal is {:g} m straight ahead of the seed, "
              "in the map frame".format(ahead_m))
    print("  it will demand at least {} pose(s) back inside {:g}s"
          .format(cfg.i("nav.health.min_poses"),
                  cfg.f("nav.health.action_timeout_s")))
    print("  NOT CHECKED HERE: whether a planner answered. That needs a "
          "graph, and it is what this tool is for.")
    print("{} problems".format(len(fails)))
    return 1 if fails else 0


def _common_config():
    """The config path the refusals name - this truck's, not the donor's.

    vehicle_config() rebound it; read back rather than re-derived so a
    refusal can never name a file this process did not open.
    """
    import _common
    return _common.CONFIG


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description="one trivial plan against this truck's planner, to "
                    "catch a nav arm that is ACTIVE over an empty "
                    "costmap. Commands no motion.")
    parser.add_argument("--vid", required=True,
                        help="f1..f4 - m6/ipc/status_contract's own ids")
    parser.add_argument("--selftest", action="store_true",
                        help="the config, the seed and the goal "
                             "arithmetic. No ROS.")
    args = parser.parse_args(own_args(argv))
    if args.vid not in VEHICLES:
        parser.error("{!r} is not a fleet vehicle id: {}".format(
            args.vid, sorted(VEHICLES)))
    if args.selftest:
        return _selftest(args.vid)

    cfg = vehicle_config(args.vid, TOOL, REQUIRED_KEYS)
    # THE SEED, AND THE REGISTRATION VERIFIED ON THE WAY PAST.
    # seed_in_map hashes the grid against the committed registration at
    # the moment the transform is USED, which is the other half of the
    # check the seed gate already made before the localiser was armed.
    _frame, seed = nav2_seed.seed_in_map(cfg, args.vid)
    ahead = goal_ahead(seed, cfg.f("nav.health.goal_ahead_m"))
    action_name = plan_action(args.vid)

    try:
        import time

        import rclpy
        from geometry_msgs.msg import PoseStamped
        from nav2_msgs.action import ComputePathToPose
        from rclpy.action import ActionClient
    except ImportError as exc:
        import _common
        _common.refuse(
            TOOL, "rclpy and nav2_msgs are importable",
            "{} (paths.ros_setup)".format(_common.CONFIG),
            "python3 could not import what this gate needs: {}".format(exc),
            "it runs INSIDE WSL with /opt/ros/jazzy sourced, which is "
            "what m6_ver2/truck.sh does before it spawns anything.")

    budget_s = cfg.f("nav.health.timeout_s")
    action_s = cfg.f("nav.health.action_timeout_s")
    rclpy.init(args=sys.argv)
    node = rclpy.create_node("nav_plan_health_" + args.vid)
    # SIM TIME, LIKE EVERY OTHER CHILD IN THIS CELL. The wait below is
    # on the WALL clock (a plant that has stopped has also stopped its
    # own), but a node that disagreed with the graph about `now` would
    # stamp a goal the servers read as ancient.
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])

    def bail(check, owner, *lines):
        try:
            node.destroy_node()
            rclpy.shutdown()
        except Exception:                                 # pragma: no cover
            pass
        cfg.refuse(check, owner, *lines)

    def stamped(pose):
        msg = PoseStamped()
        msg.header.frame_id = cfg.s("frames.map")
        msg.pose.position.x = float(pose[0])
        msg.pose.position.y = float(pose[1])
        msg.pose.orientation.z = math.sin(float(pose[2]) / 2.0)
        msg.pose.orientation.w = math.cos(float(pose[2]) / 2.0)
        return msg

    action = ActionClient(node, ComputePathToPose, action_name)
    if not action.wait_for_server(timeout_sec=budget_s):
        bail("the planner advertised {} inside {:g}s".format(
                 action_name, budget_s),
             "{} ({} nav.health.timeout_s) on domain {}".format(
                 action_name, _common_config(),
                 cfg.s("isolation.ros_domain_id")),
             "truck.sh's nav_can_answer said every lifecycle node is "
             "ACTIVE and that",
             "/{}/navigate_to_pose is on the graph, and the PLANNER's "
             "own action is not.".format(args.vid),
             "IF IT IS ADVERTISED UNNAMESPACED (/{}) the planner_server "
             "lost its".format(PLAN_ACTION),
             "__ns remap, and four trucks would then share one planner.",
             "THE STACK IS INCOMPLETE, and what is left of it is STILL "
             "UP.")

    goal = ComputePathToPose.Goal()
    goal.start = stamped(seed)
    goal.goal = stamped(ahead)
    goal.planner_id = PLANNER_ID
    goal.use_start = True

    send = action.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, send, timeout_sec=action_s)
    handle = send.result() if send.done() else None
    if handle is None or not handle.accepted:
        bail("the planner ACCEPTED one trivial goal inside {:g}s".format(
                 action_s),
             "{} ({} nav.health.action_timeout_s)".format(
                 action_name, _common_config()),
             "the goal was {} and the server {}.".format(
                 "not answered" if handle is None else "answered",
                 "never replied" if handle is None else "REJECTED it"),
             "seed  map ({:+.4f}, {:+.4f}) yaw {:+.4f}".format(*seed),
             "goal  map ({:+.4f}, {:+.4f}) yaw {:+.4f}".format(*ahead),
             "THE STACK IS INCOMPLETE, and what is left of it is STILL "
             "UP.")
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=action_s)
    if not result_future.done() or result_future.result() is None:
        bail("the planner RETURNED inside {:g}s".format(action_s),
             "{} ({} nav.health.action_timeout_s, nav2.yaml "
             "max_planning_time)".format(action_name, _common_config()),
             "the goal was accepted and no result came back. "
             "max_planning_time is 5.0 s",
             "in nav2.yaml, so a server that has not answered in "
             "{:g}s is not searching -".format(action_s),
             "it is blocked, most often waiting for a costmap that "
             "never received a map.",
             "  ros2 topic info {} -v".format(cfg.s("topics.map")),
             "THE STACK IS INCOMPLETE, and what is left of it is STILL "
             "UP.")
    outcome = result_future.result()
    poses = list(outcome.result.path.poses)
    code = int(getattr(outcome.result, "error_code", 0))
    want = cfg.i("nav.health.min_poses")
    if len(poses) < want:
        bail("one trivial plan came back with a PATH in it",
             "{} and this truck's nav2.yaml (planner_server "
             "GridBased)".format(action_name),
             "the action returned status {} with error_code {} and "
             "{} pose(s); {} were required.".format(
                 outcome.status, code, len(poses), want),
             "seed  map ({:+.4f}, {:+.4f}) yaw {:+.4f}".format(*seed),
             "goal  map ({:+.4f}, {:+.4f}) yaw {:+.4f}, which is "
             "{:g} m straight ahead".format(
                 ahead[0], ahead[1], ahead[2],
                 cfg.f("nav.health.goal_ahead_m")),
             "THIS IS THE CHECK NOTHING ELSE ON THIS BRINGUP CAN MAKE. "
             "Every node is ACTIVE,",
             "every log is clean, and the planner has nothing to plan "
             "in: with",
             "`allow_unknown: false` a global costmap that never "
             "received the frozen",
             "grid is wall-to-wall NO_INFORMATION and refuses every "
             "goal.",
             "THE MAP IS SHARED ON THIS BRANCH - one un-namespaced "
             "map_server, latched",
             "ONCE for four static layers - so read, in order:",
             "  ros2 topic info {} -v   "
             "# is the world's server publishing it?".format(
                 cfg.s("topics.map")),
             "  ros2 topic echo --once "
             "/{}/global_costmap/costmap --field info".format(args.vid),
             "  this truck's planner_server log under "
             "m6_ver2/logs/{}/".format(args.vid),
             "error_code 203/204 = start or goal outside the map, "
             "205/206 = occupied,",
             "208 = no valid path. 0 with an empty path is an "
             "unconfigured costmap.",
             "THE STACK IS INCOMPLETE, and what is left of it is STILL "
             "UP.")

    planning_s = (outcome.result.planning_time.sec
                  + outcome.result.planning_time.nanosec * 1e-9)
    print("  plan:   the planner PLANS. {:g} m ahead of the seed, "
          "{} poses in {:.4f} s".format(
              cfg.f("nav.health.goal_ahead_m"), len(poses), planning_s))
    print("          map ({:+.4f}, {:+.4f}) -> ({:+.4f}, {:+.4f}) on {}, "
          "planner_id {}".format(seed[0], seed[1], ahead[0], ahead[1],
                                 action_name, PLANNER_ID))
    print("          NOTHING WAS COMMANDED: compute_path_to_pose is the "
          "PLANNER's action")
    print("          and never reaches the controller. The truck did "
          "not move.")
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:                                     # pragma: no cover
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
