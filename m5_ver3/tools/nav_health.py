#!/usr/bin/env python3
"""nav_health.py - did the NAV ARM come up able to PLAN, or come up
merely active?

    python3 m5_ver3/tools/nav_health.py     # exit 0 healthy, 1 refused

WHY IT EXISTS, AND IT IS THE THIRD TIME THIS TRACK HAS HAD TO ASK.
`m5v3.sh start --nav` already proves that all five nav children are
ALIVE and that the lifecycle manager drove every one of them to ACTIVE.
Neither of those is the question, for exactly the reason
tools/ekf_health.py exists on the estimator and
tools/localization_health.py on the localiser: a nav2 server that is
ACTIVE over an EMPTY COSTMAP is a server that plans nothing and says
nothing about it.

  THE FAILURE, CONCRETELY. `global_costmap`'s static layer subscribes to
  the map on a TRANSIENT-LOCAL topic. If that durability is wrong, if
  the map topic name has drifted from config.yaml's, or if map_server
  was never activated, the layer waits for a message that has already
  been published and will not be published again. The costmap then
  contains nothing but NO_INFORMATION, and with `allow_unknown: false`
  the planner refuses every goal - after `max_planning_time`, once, into
  its own log. Every process is up, every lifecycle state reads active,
  `status` reads ALIVE, and the first anybody hears of it is a goal that
  times out several minutes into a measured run.

WHAT IT DOES. Two questions, in order, and the second is the one nothing
else can answer:

  1. IS EVERY LIFECYCLE NODE ACTIVE - all SIX of them. There are four
     children but six lifecycle nodes, because each costmap is a
     lifecycle node of its own inside its server
     (/local_costmap/local_costmap, /global_costmap/global_costmap) and
     a costmap can stall in `configuring` while its parent reports
     active.
  2. DOES THE PLANNER RETURN A PATH. One `compute_path_to_pose` over a
     deliberately trivial goal: `nav.health.goal_ahead_m` straight ahead
     of the seed pose, down the middle of the 8.00 m ring leg the truck
     spawns on. SUCCEEDED is not enough - the result's path has to carry
     at least `nav.health.min_poses`, because the planner answers
     SUCCEEDED with a near-empty path when the start is already inside
     its own `tolerance` of the goal, and that is indistinguishable from
     a plan through an unconfigured costmap by any other reading.

  THE START IS THE SEED AND NOT THE VEHICLE'S CURRENT POSE
  (`use_start: true`), and that is deliberate. This gate runs at bringup
  with the truck standing where it was spawned, so the two are the same
  pose - but only one of them is DERIVED, from vehicle.spawn through the
  committed registration, by the one piece of arithmetic
  (map_register.seed_pose) that also seeds the localiser and gates it.
  A gate that read the current pose off tf would be a gate whose goal
  moved with whatever it was measuring.

  AND IT IS NOT ONE OF THE THREE GOALS. `nav.goals` are 13 to 33 m
  routes; planning one here would take seconds at every bringup and
  could fail for reasons that belong to the route rather than to the
  stack.

WHAT IT IS NOT. It is not an instrument. It measures nothing, records
nothing and writes no session; tools/drive_goal.py is the instrument. It
is a BRINGUP GATE, run once by `m5v3.sh start --nav`, and it refuses the
whole bringup if it says no. It commands NO MOTION: `compute_path_to_pose`
is the PLANNER's action and never reaches the controller, so nothing is
published on topics.cmd_vel and the vehicle does not move.

WHY THIS ONE IMPORTS rclpy WHEN tools/navcmd_health.py REFUSES TO.
navcmd_health asks "did a message arrive", and for that a middleware
import is one more thing that can be wrong with the gate than the
question deserves. This one asks "how many poses are in the result of an
action", and the only subprocess that could answer it is
`ros2 action send_goal`, whose answer is a PRETTY-PRINTED result that
would have to be scraped - a gate that counts poses by counting lines of
someone else's formatting is a gate that passes on a truncated print.
tools/drive_twist.py already imports rclpy on this track for the same
kind of reason.
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import map_register                                   # noqa: E402

TOOL = "nav_health"

# MAINTENANCE OBLIGATION: a key read below is a key listed here - AND
# THE CONVERSE. The six map/spawn keys are not read in this file: they
# are read by map_register.seed_pose(), THROUGH THE cfg THIS FILE HANDS
# IT, so they are keys this program reads and they are listed here for
# the reason the obligation exists - load_config() refuses a missing one
# by its dotted name before anything is started, where seed_pose would
# refuse it four frames down with the localiser already up.
REQUIRED_KEYS = (
    "isolation.ros_domain_id",
    "frames.map",
    "map.dir", "map.name", "map.registration.file",
    "vehicle.spawn.x", "vehicle.spawn.y", "vehicle.spawn.yaw",
    "nav.planner.node_name", "nav.controller.node_name",
    "nav.behavior.node_name", "nav.bt.node_name",
    "nav.costmap_sections",
    "nav.health.timeout_s", "nav.health.goal_ahead_m",
    "nav.health.min_poses", "nav.health.action_timeout_s",
)

#: The planner's own action, which is nav2's name and not this track's.
#: It is not in config.yaml for the reason topics.amcl_pose is not: it is
#: the SERVER's advertised name, and this file is the only thing here
#: that says it.
PLAN_ACTION = "compute_path_to_pose"

#: The planner plugin the goal names. It has to be one of nav2.yaml's
#: `planner_plugins`, and an empty string would make the server pick its
#: first - which is the same thing today and would stop being it the
#: moment a second plugin is declared.
PLANNER_ID = "GridBased"


def lifecycle_nodes(cfg):
    """Every node this arm drives, in the order a reader wants them.

    SIX, NOT FOUR. `nav.costmap_sections` names the two costmap
    SUB-NODES, which have no process of their own - `status` never names
    them and the sweep never sees them - and each is a lifecycle node
    inside its server, in a namespace of its own name. A costmap stalled
    in `configuring` leaves its parent reporting `active`.
    """
    names = [cfg.s("nav.controller.node_name"),
             cfg.s("nav.planner.node_name"),
             cfg.s("nav.behavior.node_name"),
             cfg.s("nav.bt.node_name")]
    for section in cfg.s("nav.costmap_sections").split():
        names.append("{}/{}".format(section, section))
    return names


def goal_ahead(seed, ahead_m):
    """`ahead_m` along the seed's own heading, in the map frame.

    ALONG THE HEADING AND NOT ALONG +x. The map frame is about a half
    turn from the building (registration.yaml theta_rad), so a goal
    written as `x + 2` would be two metres in a direction nobody chose -
    and at THIS seed it would be two metres BEHIND the vehicle, which a
    Reeds-Shepp planner would happily solve with a cusp and a three
    point turn. The gate would pass and would have proved something
    else.

    IT IS THE SAME HEADING AS THE SEED, so the goal is a straight line
    the vehicle is already pointed down - and the direction it is
    pointed IS +x of base_link, which on this truck is the counterweight
    end. A path to it is a nav2-forward path; the geometry is a straight
    line either way and this gate makes no claim about direction.
    """
    x, y, yaw = seed
    return (x + math.cos(yaw) * ahead_m, y + math.sin(yaw) * ahead_m, yaw)


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    budget_s = cfg.f("nav.health.timeout_s")
    try:
        import time

        import rclpy
        from geometry_msgs.msg import PoseStamped
        from lifecycle_msgs.srv import GetState
        from nav2_msgs.action import ComputePathToPose
        from rclpy.action import ActionClient
        from rclpy.node import Node
    except ImportError as exc:
        cfg.refuse("rclpy and nav2_msgs are importable",
                   _common.CONFIG + " (paths.ros_setup)",
                   "python3 could not import what this gate needs: "
                   "{}".format(exc),
                   "it runs INSIDE WSL with /opt/ros/jazzy sourced, which "
                   "is what m5v3.sh does before it spawns anything.")

    # THE SEED, AND THE REGISTRATION VERIFIED ON THE WAY PAST. seed_pose()
    # hashes the grid against the committed registration at the moment
    # the transform is USED, which is the other half of the check
    # m5v3.sh already made before it started anything (F3 constraint 16).
    _frame, seed = map_register.seed_pose(cfg)
    ahead = goal_ahead(seed, cfg.f("nav.health.goal_ahead_m"))

    rclpy.init(args=None)
    node = Node("m5v3_nav_health")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    deadline = time.monotonic() + budget_s

    def bail(check, owner, *lines):
        try:
            node.destroy_node()
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse(check, owner, *lines)

    # ---- 1. every lifecycle node ACTIVE -------------------------------
    # ON THE WALL CLOCK AND NOT THE PLANT'S, which is drive_twist's rule:
    # what is being waited for is a SERVICE, and a plant that has stopped
    # has also stopped its clock - a budget measured on that clock would
    # never expire.
    states = {}
    for name in lifecycle_nodes(cfg):
        client = node.create_client(GetState, "/{}/get_state".format(name))
        state = ""
        while state != "active":
            if time.monotonic() > deadline:
                bail("every nav lifecycle node reached ACTIVE inside "
                     "{:g}s".format(budget_s),
                     "{} (config.yaml nav.health.timeout_s) and "
                     "nav2.yaml's nav_lifecycle_manager".format(
                         os.path.join("m5_ver3", "logs")),
                     "/{} is in state {!r} and the manager has had the "
                     "whole budget.".format(name, state or "unreachable"),
                     "WHAT IS ACTIVE SO FAR: {}".format(
                         ", ".join("{}={}".format(k, v)
                                   for k, v in states.items()) or "(none)"),
                     "A nav2 lifecycle node left short of ACTIVE "
                     "subscribes to nothing,",
                     "advertises no action and logs nothing that reads as "
                     "an error - and",
                     "`status` reads ALIVE. The two costmaps are "
                     "lifecycle nodes of their",
                     "OWN inside their servers, so a costmap stalled in "
                     "`configuring` leaves",
                     "its parent reporting active.",
                     "THE STACK IS INCOMPLETE, and what is left of it is "
                     "STILL UP.",
                     "read m5_ver3/logs/{}.log.".format(name.split("/")[0]))
            if client.wait_for_service(timeout_sec=0.5):
                future = client.call_async(GetState.Request())
                rclpy.spin_until_future_complete(node, future, timeout_sec=2.0)
                if future.done() and future.result() is not None:
                    state = future.result().current_state.label
            rclpy.spin_once(node, timeout_sec=0.05)
        states[name] = state
        node.destroy_client(client)
    print("  nav:    {} lifecycle nodes ACTIVE - {}".format(
        len(states), ", ".join(states)))

    # ---- 2. one trivial plan ------------------------------------------
    action = ActionClient(node, ComputePathToPose, PLAN_ACTION)
    if not action.wait_for_server(
            timeout_sec=max(1.0, deadline - time.monotonic())):
        bail("the planner advertised {} inside {:g}s".format(
                 PLAN_ACTION, budget_s),
             "{} (nav2.yaml planner_server) on domain {}".format(
                 PLAN_ACTION, cfg.s("isolation.ros_domain_id")),
             "planner_server is ACTIVE - the check above said so - and "
             "its action server",
             "is not on the graph. An ACTIVE server that advertises "
             "nothing is a server",
             "whose on_activate did not finish.",
             "THE STACK IS INCOMPLETE, and what is left of it is STILL "
             "UP.")

    def stamped(pose):
        msg = PoseStamped()
        msg.header.frame_id = cfg.s("frames.map")
        msg.pose.position.x = float(pose[0])
        msg.pose.position.y = float(pose[1])
        msg.pose.orientation.z = math.sin(float(pose[2]) / 2.0)
        msg.pose.orientation.w = math.cos(float(pose[2]) / 2.0)
        return msg

    goal = ComputePathToPose.Goal()
    goal.start = stamped(seed)
    goal.goal = stamped(ahead)
    goal.planner_id = PLANNER_ID
    goal.use_start = True

    action_s = cfg.f("nav.health.action_timeout_s")
    send = action.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, send, timeout_sec=action_s)
    handle = send.result() if send.done() else None
    if handle is None or not handle.accepted:
        bail("the planner ACCEPTED one trivial goal inside "
             "{:g}s".format(action_s),
             "{} (config.yaml nav.health.action_timeout_s)".format(
                 PLAN_ACTION),
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
             "{} (config.yaml nav.health.action_timeout_s, nav2.yaml "
             "max_planning_time)".format(PLAN_ACTION),
             "the goal was accepted and no result came back. "
             "max_planning_time is 5.0 s",
             "in nav2.yaml, so a server that has not answered in "
             "{:g}s is not searching -".format(action_s),
             "it is blocked, most often waiting for a costmap that never "
             "received a map.",
             "  ros2 topic info {} -v".format("/map"),
             "THE STACK IS INCOMPLETE, and what is left of it is STILL "
             "UP.")
    outcome = result_future.result()
    poses = list(outcome.result.path.poses)
    code = int(getattr(outcome.result, "error_code", 0))
    want = cfg.i("nav.health.min_poses")
    if len(poses) < want:
        bail("one trivial plan came back with a PATH in it",
             "{} and nav2.yaml (planner_server GridBased)".format(
                 PLAN_ACTION),
             "the action returned status {} with error_code {} and "
             "{} pose(s); {} were required.".format(
                 outcome.status, code, len(poses), want),
             "seed  map ({:+.4f}, {:+.4f}) yaw {:+.4f}".format(*seed),
             "goal  map ({:+.4f}, {:+.4f}) yaw {:+.4f}, which is "
             "{:g} m straight ahead".format(
                 ahead[0], ahead[1], ahead[2],
                 cfg.f("nav.health.goal_ahead_m")),
             "THIS IS THE CHECK NOTHING ELSE ON THE STACK CAN MAKE. "
             "Every node is ACTIVE,",
             "every log is clean, and the planner has nothing to plan "
             "in: with",
             "`allow_unknown: false` a global costmap that never "
             "received the frozen",
             "grid is wall-to-wall NO_INFORMATION and refuses every "
             "goal. Read, in order:",
             "  ros2 topic info /map -v          "
             "# is anything publishing it?",
             "  ros2 topic echo --once "
             "/global_costmap/costmap --field info",
             "  m5_ver3/logs/planner_server.log",
             "error_code 203/204 = start or goal outside the map, "
             "205/206 = occupied,",
             "208 = no valid path. 0 with an empty path is an "
             "unconfigured costmap.",
             "THE STACK IS INCOMPLETE, and what is left of it is STILL "
             "UP.")

    planning_s = (outcome.result.planning_time.sec
                  + outcome.result.planning_time.nanosec * 1e-9)
    print("  nav:    the planner PLANS. {:g} m ahead of the seed, "
          "{} poses in {:.4f} s".format(
              cfg.f("nav.health.goal_ahead_m"), len(poses), planning_s))
    print("          map ({:+.4f}, {:+.4f}) -> ({:+.4f}, {:+.4f}), "
          "planner_id {}".format(seed[0], seed[1], ahead[0], ahead[1],
                                 PLANNER_ID))
    print("          NOTHING WAS COMMANDED: compute_path_to_pose is the "
          "PLANNER's action")
    print("          and never reaches the controller. The truck did not "
          "move.")
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
