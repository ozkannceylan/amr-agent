#!/usr/bin/env python3
"""nav2_run.py - the measurement harness for the forklift's Nav2 stack.

WHAT IT DOES
  `goal`      converts a WORLD pose into the MAP frame through the
              committed registration, sends it to /navigate_to_pose,
              records the run at 10 Hz and prints what the stack did -
              including what it did when it REFUSED.
  `analyse`   scores a recording: goal error measured ABSOLUTELY in the
              world frame, cross-track error against the plan the vehicle
              was actually given, direction reversals, and the gap between
              where the vehicle THOUGHT it finished and where it really
              did.
  `convcheck` CHECKS THE Twist -> TRICYCLE CONVERSION AGAINST A COMMANDED
              MOTION. It publishes a timed sequence of known twists into
              the converter's own input topic and measures what the VEHICLE
              then did, from ground truth. A round trip through the algebra
              proves the algebra; only this proves the vehicle turns on the
              radius it was asked for. It needs the bringup and the
              converter, and it needs NO planner, controller or localizer.

WHAT IT IS NOT. It is not part of the vehicle. It publishes no transform,
no command and no pose; it drives nothing and it corrects nothing. It is
an instrument, and it is the only thing in this stack allowed to look at
ground truth.

THE REFERENCE IS EXACT AND IT REACHES NOTHING ELSE. /forklift/odom is the
simulator's own pose of the model despite its name (agv/forklift/config.yaml
carries the standing rename request). It is subscribed HERE and by nothing
that navigates: not by the EKF, not by AMCL, not by any costmap. An
estimate scored against its own input cannot be wrong.

THE GOAL IS GIVEN IN THE MAP FRAME, WHICH IS ALL A REAL VEHICLE COULD
KNOW. There is no world frame on a forklift and no T(world -> map) on one
either. The conversion lives here, in the harness, for the same reason
localization.launch.py refuses to carry it: putting it in the vehicle's own
software would make the vehicle depend on a transform that exists only
because this is a simulation. The transform is reached through
sim/maps/warehouse/register_map.py, the module that DERIVED it, which
verifies the grid md5 before returning it (invariant 10).

THE FLOOR TRAVELS WITH EVERY FIGURE. The registration's residual max is
0.141 m and no rigid transform fits the committed grid to the building
better than that. Any error at or below it is reported as "at the
instrument's resolution" by the same rule EVIDENCE_LOCALIZATION.md follows,
applied by this tool and not by the reader.

Usage (after sourcing /opt/ros/jazzy/setup.bash):

  python3 agv/forklift/scripts/nav2_run.py goal \\
      --x 0.0 --y 7.0 --yaw 0.0 --csv run.csv --plan run-plan.csv

  python3 agv/forklift/scripts/nav2_run.py analyse \\
      --csv run.csv --plan run-plan.csv
"""

import argparse
import csv
import json
import math
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_REPO_ROOT = os.path.normpath(os.path.join(_FORKLIFT_DIR, '..', '..'))

#: The columns of the run CSV, in order. Written out so a reader of the
#: file does not have to run the tool to know what a column is.
_RUN_FIELDS = [
    't_sim',            # simulation time [s]
    'gt_x', 'gt_y', 'gt_yaw',        # GROUND TRUTH, world frame, exact
    'amcl_x', 'amcl_y', 'amcl_yaw',  # map -> forklift/base_link, map frame
    'cmd_v', 'cmd_w',   # the Twist the converter was handed [m/s, rad/s]
    'steer', 'traction',             # what the converter emitted
    'refusals',         # monotonic count of refused in-place rotations
]


def _wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def _yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


# --------------------------------------------------------------------------- #
# the committed registration, through the module that derived it
# --------------------------------------------------------------------------- #

def load_registration(path=None):
    """Reached through sim/maps/warehouse/register_map.py, never parsed
    here. It verifies the grid md5, so a run scored against a rebuilt map
    FAILS HERE instead of producing a plausible wrong number."""
    module_dir = os.path.join(_REPO_ROOT, 'sim', 'maps', 'warehouse')
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    try:
        import register_map
    except ImportError:
        raise SystemExit(
            'cannot import {}/register_map.py, which owns the world->map '
            'transform.'.format(module_dir))
    if path is None:
        path = register_map.DEFAULT_REGISTRATION
    return register_map.load_registration(path)


def world_to_map(rec, x, y, yaw):
    """p_map = R(theta) p_world + t, the registration's own direction."""
    th = rec['theta_rad']
    c, s = math.cos(th), math.sin(th)
    return (c * x - s * y + rec['t_x_m'],
            s * x + c * y + rec['t_y_m'],
            _wrap(yaw + th))


def map_to_world(rec, x, y, yaw):
    """p_world = R(-theta) (p_map - t)."""
    th = rec['theta_rad']
    c, s = math.cos(-th), math.sin(-th)
    mx, my = x - rec['t_x_m'], y - rec['t_y_m']
    return (c * mx - s * my, s * mx + c * my, _wrap(yaw - th))


def against_floor(value_m, floor_m):
    """The reporting rule, applied by the tool and not by the reader."""
    if value_m <= floor_m:
        return '{:.4f} m (at the instrument\'s resolution, floor {:.4f} m)' \
            .format(value_m, floor_m)
    return '{:.4f} m ({:.2f} x floor)'.format(value_m, value_m / floor_m)


# --------------------------------------------------------------------------- #
# the recorder, shared by `goal` and `stage`
# --------------------------------------------------------------------------- #
#
# ONE RECORDER, TWO COMMANDS, SO THE TWO CSVs ARE COMPARABLE. A staged run
# has to be scored against the m5-31 baseline (EVIDENCE_NAV2.md section 8.2),
# and a figure taken by a second implementation of the same recording is a
# figure with an extra difference in it. `goal` and `stage` therefore build
# the identical node, subscribe to the identical topics and write the
# identical columns; only the sequencing above them differs.

def _build_recorder(cmd_topic, node_name='nav2_run'):
    """Construct the recording node. `rclpy.init()` must already have run."""
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry, Path
    from nav2_msgs.action import NavigateToPose
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from std_msgs.msg import Float64, UInt32
    import tf2_ros

    class Runner(Node):
        def __init__(self):
            # use_sim_time is an OVERRIDE at construction, not a
            # set_parameters call afterwards: the clock has to be on /clock
            # before the first get_clock().now(), or the node reads the
            # system clock once and every deadline computed from it is
            # 1.8e9 s out.
            super().__init__(
                node_name,
                parameter_overrides=[Parameter('use_sim_time', value=True)])

            self.gt = None
            self.cmd = (0.0, 0.0)
            self.steer = float('nan')
            self.traction = float('nan')
            self.refusals = 0
            self.first_plan = None
            self.last_plan = None
            self.plan_count = 0

            self.tf_buffer = tf2_ros.Buffer()
            self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

            self.create_subscription(Odometry, '/forklift/odom',
                                     self.cb_ground_truth, 10)
            self.create_subscription(Twist, cmd_topic, self.cb_cmd, 10)
            self.create_subscription(
                Float64, '/forklift/cmd/steer_angle', self.cb_steer, 10)
            self.create_subscription(
                Float64, '/forklift/cmd/traction_speed', self.cb_traction, 10)
            self.create_subscription(
                UInt32, '/forklift/nav/tricycle_refusals',
                self.cb_refusals, 10)
            self.create_subscription(Path, '/plan', self.cb_plan, 10)

            self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Callbacks are cb_* so none can shadow an rclpy Node attribute.
        def cb_ground_truth(self, msg):
            p = msg.pose.pose
            self.gt = (p.position.x, p.position.y, _yaw_of(p.orientation))

        def cb_cmd(self, msg):
            self.cmd = (msg.linear.x, msg.angular.z)

        def cb_steer(self, msg):
            self.steer = msg.data

        def cb_traction(self, msg):
            self.traction = msg.data

        def cb_refusals(self, msg):
            self.refusals = msg.data

        def cb_plan(self, msg):
            poses = [(p.pose.position.x, p.pose.position.y,
                      _yaw_of(p.pose.orientation)) for p in msg.poses]
            if not poses:
                return
            self.plan_count += 1
            if self.first_plan is None:
                self.first_plan = poses
            self.last_plan = poses

        def map_pose(self):
            try:
                tr = self.tf_buffer.lookup_transform(
                    'map', 'forklift/base_link', rclpy.time.Time())
            except Exception:
                return None
            t = tr.transform.translation
            return (t.x, t.y, _yaw_of(tr.transform.rotation))

        def sim_time(self):
            return self.get_clock().now().nanoseconds * 1e-9

    return Runner()


def _row(node, now):
    """One recorded sample, in the committed column order."""
    mp = node.map_pose()
    gt = node.gt
    return {
        't_sim': '{:.3f}'.format(now),
        'gt_x': '' if gt is None else '{:.6f}'.format(gt[0]),
        'gt_y': '' if gt is None else '{:.6f}'.format(gt[1]),
        'gt_yaw': '' if gt is None else '{:.6f}'.format(gt[2]),
        'amcl_x': '' if mp is None else '{:.6f}'.format(mp[0]),
        'amcl_y': '' if mp is None else '{:.6f}'.format(mp[1]),
        'amcl_yaw': '' if mp is None else '{:.6f}'.format(mp[2]),
        'cmd_v': '{:.6f}'.format(node.cmd[0]),
        'cmd_w': '{:.6f}'.format(node.cmd[1]),
        'steer': '{:.6f}'.format(node.steer),
        'traction': '{:.6f}'.format(node.traction),
        'refusals': str(node.refusals),
    }


# --------------------------------------------------------------------------- #
# goal
# --------------------------------------------------------------------------- #

def cmd_goal(args):
    import rclpy
    from action_msgs.msg import GoalStatus
    from geometry_msgs.msg import PoseStamped

    rec = load_registration(args.registration)
    gx, gy, gyaw = world_to_map(rec, args.x, args.y, args.yaw)

    rclpy.init()
    node = _build_recorder(args.cmd_topic)

    # ---- wait for the action server and for a transform tree ----
    print('registration  theta {:+.9f} rad  t ({:+.6f}, {:+.6f}) m  '
          'FLOOR rms {:.4f} MAX {:.4f} m'.format(
              rec['theta_rad'], rec['t_x_m'], rec['t_y_m'],
              rec['residual_rms_m'], rec['residual_max_m']))
    print('goal  world ({:+.4f}, {:+.4f}) yaw {:+.4f} rad'
          '  ->  map ({:+.4f}, {:+.4f}) yaw {:+.4f} rad'.format(
              args.x, args.y, args.yaw, gx, gy, gyaw))

    if not node.client.wait_for_server(timeout_sec=args.server_timeout):
        print('FAIL: /navigate_to_pose action server did not appear within '
              '{:.0f} s. Nav2 is not up.'.format(args.server_timeout))
        node.destroy_node()
        rclpy.shutdown()
        return 2

    # BOUNDED POLL ON THE WALL CLOCK, not on sim time: this is a wait for a
    # transform tree to EXIST, and until it does there is no reason to
    # believe /clock has been read either.
    import time as _time
    settle_deadline = _time.monotonic() + args.settle
    while _time.monotonic() < settle_deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        if node.map_pose() is not None and node.gt is not None:
            break
    if node.map_pose() is None:
        print('FAIL: no map -> forklift/base_link transform after {:.0f} s. '
              'The localization stack is not up.'.format(args.settle))
        node.destroy_node()
        rclpy.shutdown()
        return 2
    if node.gt is None:
        print('FAIL: no /forklift/odom. The bringup is not up, and this '
              'harness has no reference to score against.')
        node.destroy_node()
        rclpy.shutdown()
        return 2

    goal = NavigateToPose.Goal()
    goal.pose = PoseStamped()
    goal.pose.header.frame_id = 'map'
    goal.pose.header.stamp = node.get_clock().now().to_msg()
    goal.pose.pose.position.x = gx
    goal.pose.pose.position.y = gy
    goal.pose.pose.orientation.z = math.sin(gyaw / 2.0)
    goal.pose.pose.orientation.w = math.cos(gyaw / 2.0)

    t0 = node.sim_time()
    wall0 = _time.monotonic()
    send_future = node.client.send_goal_async(goal)
    while not send_future.done():
        rclpy.spin_once(node, timeout_sec=0.05)
    handle = send_future.result()

    if not handle.accepted:
        print('')
        print('REFUSED AT ACCEPTANCE: the action server rejected the goal.')
        node.destroy_node()
        rclpy.shutdown()
        return 1
    print('goal ACCEPTED at t_sim {:.2f}'.format(t0))

    result_future = handle.get_result_async()

    rows = []
    next_sample = node.sim_time()
    period = 1.0 / args.record_hz
    while not result_future.done():
        rclpy.spin_once(node, timeout_sec=0.02)
        now = node.sim_time()
        if now >= next_sample:
            next_sample = now + period
            rows.append(_row(node, now))
        if now - t0 > args.timeout:
            print('TIMEOUT after {:.1f} s of simulation time; cancelling'
                  .format(now - t0))
            handle.cancel_goal_async()
            break
        # WALL BACKSTOP. If /clock stalls, the simulation-time deadline
        # above never fires and this harness would wait for ever - which is
        # exactly the "ended a turn waiting on a process" failure
        # docs/LESSONS.md 2026-07-27 records.
        if _time.monotonic() - wall0 > args.wall_timeout:
            print('WALL TIMEOUT after {:.0f} s with simulation time at '
                  '{:.1f} s; cancelling. A stalled /clock is the usual '
                  'cause.'.format(_time.monotonic() - wall0, now - t0))
            handle.cancel_goal_async()
            break

    status_name = 'CANCELLED/TIMEOUT'
    error_code = None
    if result_future.done():
        res = result_future.result()
        status = res.status
        status_name = {
            GoalStatus.STATUS_SUCCEEDED: 'SUCCEEDED',
            GoalStatus.STATUS_ABORTED: 'ABORTED',
            GoalStatus.STATUS_CANCELED: 'CANCELED',
        }.get(status, 'status {}'.format(status))
        error_code = getattr(res.result, 'error_code', None)

    t_end = node.sim_time()

    # ---- what actually happened, printed before anything is scored ----
    mp = node.map_pose()
    gt = node.gt
    print('')
    print('RESULT           {}'.format(status_name))
    print('error_code       {}'.format(
        'none' if error_code in (None, 0) else error_code))
    print('elapsed          {:.2f} s of simulation time'.format(t_end - t0))
    print('plans published  {}'.format(node.plan_count))
    print('refusals         {} rotation-in-place commands refused by the '
          'converter'.format(node.refusals))
    if mp is not None:
        w = map_to_world(rec, *mp)
        print('final BELIEVED   map ({:+.4f}, {:+.4f}) yaw {:+.4f}'
              .format(*mp))
        print('  carried to world ({:+.4f}, {:+.4f}) yaw {:+.4f}'.format(*w))
    if gt is not None:
        print('final TRUTH      world ({:+.4f}, {:+.4f}) yaw {:+.4f}'
              .format(*gt))
        d = math.hypot(gt[0] - args.x, gt[1] - args.y)
        print('ABSOLUTE goal error (truth vs commanded goal): {}'.format(
            against_floor(d, rec['residual_max_m'])))
        print('  heading error {:+.3f} deg'.format(
            math.degrees(_wrap(gt[2] - args.yaw))))

    if args.csv:
        with open(args.csv, 'w', newline='', encoding='utf-8') as fh:
            wr = csv.DictWriter(fh, fieldnames=_RUN_FIELDS)
            wr.writeheader()
            wr.writerows(rows)
        print('wrote {} ({} samples)'.format(args.csv, len(rows)))

    if args.plan:
        payload = {
            'goal_world': [args.x, args.y, args.yaw],
            'goal_map': [gx, gy, gyaw],
            'status': status_name,
            'error_code': error_code,
            'elapsed_s': t_end - t0,
            'plans_published': node.plan_count,
            'refusals': node.refusals,
            'first_plan_map': node.first_plan,
            'last_plan_map': node.last_plan,
        }
        with open(args.plan, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        print('wrote {}'.format(args.plan))

    node.destroy_node()
    rclpy.shutdown()
    return 0 if status_name == 'SUCCEEDED' else 1


# --------------------------------------------------------------------------- #
# stage - THE STAGED APPROACH
# --------------------------------------------------------------------------- #
#
# WHAT THIS IS AND WHY IT IS NOT A TUNING PASS. EVIDENCE_NAV2.md section 8.3
# measured that `xy_goal_tolerance: 0.25` and `yaw_goal_tolerance: 0.15` are
# JOINTLY unreachable in an endgame correction on this vehicle: heading is
# bought with travel at 2.1-2.6 m per radian, so one yaw tolerance of
# correction costs 0.32-0.39 m against a 0.25 m box. r4 spent 55.9 s inside
# the position circle and 47.1 s inside the heading window with ZERO samples
# inside both.
#
# NEITHER TOLERANCE IS TOUCHED HERE, and that is the point. The station goal
# is checked by the committed pair, unchanged. What changes is that the
# vehicle ARRIVES ALREADY ALIGNED, so the correction the geometry forbids is
# never attempted:
#
#   1. a STAGING pose, d = 3.0 m back along the goal heading. d is DERIVED
#      (ARRIVAL-GEOMETRY.md section 4.2): 2*sqrt(R*e0) = 2*sqrt(1.291*0.35)
#      = 1.34 m to remove the staging arrival's lateral offset with two
#      opposed arcs, plus one lookahead (1.60 m, nav2.yaml) of straight tail
#      to converge and centre the steer. It is not a round number chosen to
#      taste and it is not tuned here.
#   2. the staging goal is checked POSITION-ONLY (`staging_goal_checker`,
#      nav2_controller::PositionGoalChecker), selected per goal through
#      nav2's own GoalCheckerSelector -> FollowPath goal_checker_id path.
#      The staging pose does not need a heading; the final leg replans from
#      wherever the vehicle actually stands.
#   3. the station goal is a FRESH, ~straight 3 m leg from a standing start
#      with near-zero initial cross-track, checked by the committed pair.
#   4. a miss is a BOUNDED GO-AROUND: return to staging, re-approach, at
#      most --max-go-arounds times, then FAIL AND SAY SO. An in-circle
#      correction is never attempted, because section 8.3 proved it cannot
#      terminate, and an unbounded retry is that same failure with a new
#      name.
#
# WHERE THIS LOGIC BELONGS IN THE END. In the goal-sending layer, which is
# here, and at M6 in the VDA 5050 client's node-by-node order execution: a
# staging pose is just a node with a loose `allowedDeviationXY/Theta` pair
# and the station is a node with a tight one (ARRIVAL-GEOMETRY.md section 6).
# It is written to be lifted, not kept.

#: The whole-run CSV carries one extra column over `goal`: which leg the
#: sample belongs to. `analyse` reads with DictReader and ignores it, so an
#: approach leg extracted from this file scores exactly as a `goal` run does.
_STAGE_FIELDS = _RUN_FIELDS + ['leg']

#: Pre-registered before the first run, so the verdict is not chosen after
#: seeing the data. A leg is in the SHUFFLE REGIME when, AFTER its first
#: sample inside the goal's position circle, the commanded direction
#: reverses at least this many times. The m5-31 baseline separates cleanly
#: on it: the two clean traverses reversed 0 and 1 times in the endgame,
#: every non-completing run reversed dozens. Counted per leg, so a
#: go-around's deliberate reverse-out - which happens in the RETURN leg -
#: is never miscounted as a shuffle.
_SHUFFLE_REVERSALS = 3
#: Speed deadband for "the vehicle is being commanded to move", the same
#: 0.02 m/s `analyse` uses to classify a command's sign.
_MOVING_MPS = 0.02


def _direction_reversals(v_series):
    """Sign changes in a commanded-speed series, ignoring the deadband."""
    signs = [1 if x > _MOVING_MPS else (-1 if x < -_MOVING_MPS else 0)
             for x in v_series]
    signs = [s for s in signs if s != 0]
    return sum(1 for i in range(len(signs) - 1) if signs[i] != signs[i + 1])


def _localization_stats(rows, rec):
    """Believed pose against ground truth, the EVIDENCE_NAV2.md 8.5 figure.

    The belief is a MAP-frame object and the truth a world-frame one, so the
    belief is carried through the committed registration before it is
    differenced - the same direction 8.5 used."""
    pos, head = [], []
    for r in rows:
        if not r['gt_x'] or not r['amcl_x']:
            continue
        bx, by, byaw = map_to_world(rec, float(r['amcl_x']),
                                    float(r['amcl_y']), float(r['amcl_yaw']))
        pos.append(math.hypot(bx - float(r['gt_x']), by - float(r['gt_y'])))
        head.append(abs(math.degrees(_wrap(byaw - float(r['gt_yaw'])))))
    if not pos:
        return None
    return {
        'n': len(pos),
        'pos_rms': math.sqrt(sum(p * p for p in pos) / len(pos)),
        'pos_max': max(pos),
        'yaw_rms': math.sqrt(sum(h * h for h in head) / len(head)),
        'yaw_max': max(head),
    }


def cmd_stage(args):
    import rclpy
    from action_msgs.msg import GoalStatus
    from geometry_msgs.msg import PoseStamped
    from nav2_msgs.action import NavigateToPose
    from std_msgs.msg import String
    import time as _time

    rec = load_registration(args.registration)

    # The staging pose: d back ALONG THE GOAL HEADING, same heading. Derived
    # in the world frame and carried through the registration exactly as the
    # goal is, so both poses reach Nav2 by the identical path.
    sx = args.x - args.d * math.cos(args.yaw)
    sy = args.y - args.d * math.sin(args.yaw)
    syaw = args.yaw

    goal_map = world_to_map(rec, args.x, args.y, args.yaw)
    stage_map = world_to_map(rec, sx, sy, syaw)

    rclpy.init()
    node = _build_recorder(args.cmd_topic, 'nav2_stage')

    # LATCHED, because the selector node subscribes transient-local with
    # depth 1 and the tree may create that subscription after we publish.
    from rclpy.qos import (QoSProfile, QoSDurabilityPolicy,
                           QoSReliabilityPolicy, QoSHistoryPolicy)
    sel_qos = QoSProfile(depth=1,
                         history=QoSHistoryPolicy.KEEP_LAST,
                         reliability=QoSReliabilityPolicy.RELIABLE,
                         durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
    sel_pub = node.create_publisher(String, args.selector_topic, sel_qos)

    print('registration  theta {:+.9f} rad  t ({:+.6f}, {:+.6f}) m  '
          'FLOOR rms {:.4f} MAX {:.4f} m'.format(
              rec['theta_rad'], rec['t_x_m'], rec['t_y_m'],
              rec['residual_rms_m'], rec['residual_max_m']))
    print('STATION  world ({:+.4f}, {:+.4f}) yaw {:+.4f}  ->  map '
          '({:+.4f}, {:+.4f}) yaw {:+.4f}   checker {}'.format(
              args.x, args.y, args.yaw, goal_map[0], goal_map[1], goal_map[2],
              args.final_checker))
    print('STAGING  world ({:+.4f}, {:+.4f}) yaw {:+.4f}  ->  map '
          '({:+.4f}, {:+.4f}) yaw {:+.4f}   checker {}'.format(
              sx, sy, syaw, stage_map[0], stage_map[1], stage_map[2],
              args.staging_checker))
    print('d = {:.3f} m back along the goal heading; go-arounds bounded at '
          '{}'.format(args.d, args.max_go_arounds))

    if not node.client.wait_for_server(timeout_sec=args.server_timeout):
        print('FAIL: /navigate_to_pose action server did not appear within '
              '{:.0f} s. Nav2 is not up.'.format(args.server_timeout))
        node.destroy_node()
        rclpy.shutdown()
        return 2

    settle_deadline = _time.monotonic() + args.settle
    while _time.monotonic() < settle_deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        if node.map_pose() is not None and node.gt is not None:
            break
    if node.map_pose() is None or node.gt is None:
        print('FAIL: no map -> forklift/base_link transform, or no '
              '/forklift/odom, after {:.0f} s.'.format(args.settle))
        node.destroy_node()
        rclpy.shutdown()
        return 2

    rows = []
    legs = []
    wall0 = _time.monotonic()
    period = 1.0 / args.record_hz
    state = {'next_sample': node.sim_time(), 'leg': 'settle'}

    def pump(seconds_wall):
        """Spin and record for a bounded wall interval. Recording never
        stops between legs: the localization figures are taken over the
        WHOLE run, as EVIDENCE_NAV2.md 8.5 took them."""
        end = _time.monotonic() + seconds_wall
        while _time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.02)
            now = node.sim_time()
            if now >= state['next_sample']:
                state['next_sample'] = now + period
                r = _row(node, now)
                r['leg'] = state['leg']
                rows.append(r)

    def drive(label, wx, wy, wyaw, checker, timeout):
        """One leg. Returns its record; appends its samples to `rows`."""
        state['leg'] = label
        mx, my, myaw = world_to_map(rec, wx, wy, wyaw)

        # SELECT THE CHECKER FIRST, THEN SETTLE, THEN SEND. The selector is
        # a subscription in the tree, so the selection has to be in the
        # subscriber before FollowPath is ticked. Latched publish plus a
        # bounded settle, and the selection is stated in the leg record so
        # a reader can see which checker each leg was scored by.
        sel_pub.publish(String(data=checker))
        pump(args.selector_settle)

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = node.get_clock().now().to_msg()
        goal.pose.pose.position.x = mx
        goal.pose.pose.position.y = my
        goal.pose.pose.orientation.z = math.sin(myaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(myaw / 2.0)

        node.first_plan = None
        row0 = len(rows)
        t0 = node.sim_time()
        send_future = node.client.send_goal_async(goal)
        while not send_future.done():
            rclpy.spin_once(node, timeout_sec=0.05)
        handle = send_future.result()
        if not handle.accepted:
            print('  {}: REFUSED AT ACCEPTANCE'.format(label))
            return {'leg': label, 'checker': checker, 'status': 'REFUSED',
                    'goal_world': [wx, wy, wyaw], 'goal_map': [mx, my, myaw],
                    'elapsed_s': 0.0, 'row0': row0, 'row1': len(rows)}

        result_future = handle.get_result_async()
        timed_out = False
        while not result_future.done():
            rclpy.spin_once(node, timeout_sec=0.02)
            now = node.sim_time()
            if now >= state['next_sample']:
                state['next_sample'] = now + period
                r = _row(node, now)
                r['leg'] = label
                rows.append(r)
            if now - t0 > timeout:
                timed_out = True
                print('  {}: TIMEOUT after {:.1f} s of simulation time; '
                      'cancelling'.format(label, now - t0))
                handle.cancel_goal_async()
                break
            # WALL BACKSTOP over the whole run, not the leg: a stalled
            # /clock makes every simulation-time deadline unreachable, and
            # this harness never waits for ever (docs/LESSONS.md
            # 2026-07-27).
            if _time.monotonic() - wall0 > args.wall_timeout:
                timed_out = True
                print('  {}: WALL TIMEOUT at {:.0f} s with simulation time '
                      'at {:.1f} s; cancelling.'.format(
                          label, _time.monotonic() - wall0, now - t0))
                handle.cancel_goal_async()
                break

        if timed_out:
            # Bounded wait for the cancellation to actually land, so the
            # next leg is not sent while the controller is still driving.
            cancel_end = _time.monotonic() + args.cancel_grace
            while (not result_future.done()
                   and _time.monotonic() < cancel_end):
                rclpy.spin_once(node, timeout_sec=0.05)
                now = node.sim_time()
                if now >= state['next_sample']:
                    state['next_sample'] = now + period
                    r = _row(node, now)
                    r['leg'] = label
                    rows.append(r)

        status_name = 'CANCELLED/TIMEOUT'
        error_code = None
        if result_future.done():
            res = result_future.result()
            status_name = {
                GoalStatus.STATUS_SUCCEEDED: 'SUCCEEDED',
                GoalStatus.STATUS_ABORTED: 'ABORTED',
                GoalStatus.STATUS_CANCELED: 'CANCELED',
            }.get(res.status, 'status {}'.format(res.status))
            error_code = getattr(res.result, 'error_code', None)
        t_end = node.sim_time()

        # Let the stack come to rest before the leg is scored: the
        # controller publishes an explicit zero on a finished goal
        # (`publish_zero_velocity`), and the vehicle takes a moment to stop.
        pump(args.leg_rest)

        leg_rows = rows[row0:]
        rec_leg = {
            'leg': label,
            'checker': checker,
            'status': status_name,
            'error_code': error_code,
            'goal_world': [wx, wy, wyaw],
            'goal_map': [mx, my, myaw],
            'elapsed_s': t_end - t0,
            'samples': len(leg_rows),
            'row0': row0,
            'row1': len(rows),
            'plan_map': node.first_plan,
            'plans_published': node.plan_count,
        }

        # ---- the two mechanism columns, per leg ----
        # (i) believed heading error at the FIRST sample inside the position
        #     circle - the m5-31 8.3 discriminator, which is what explains
        #     WHY a run completes rather than that it did.
        # (ii) direction reversals after that first entry - the shuffle test.
        entry_idx = None
        for i, r in enumerate(leg_rows):
            if not r['amcl_x']:
                continue
            if math.hypot(float(r['amcl_x']) - mx,
                          float(r['amcl_y']) - my) <= args.entry_radius:
                entry_idx = i
                break
        if entry_idx is not None:
            r = leg_rows[entry_idx]
            rec_leg['entry_heading_deg'] = math.degrees(
                _wrap(float(r['amcl_yaw']) - myaw))
            rec_leg['entry_t_sim'] = float(r['t_sim'])
            after = [float(x['cmd_v']) for x in leg_rows[entry_idx:]]
            rec_leg['reversals_after_entry'] = _direction_reversals(after)
        else:
            rec_leg['entry_heading_deg'] = None
            rec_leg['reversals_after_entry'] = 0
        rec_leg['shuffle'] = (
            rec_leg['reversals_after_entry'] >= _SHUFFLE_REVERSALS)

        st = [abs(float(r['steer'])) for r in leg_rows
              if r['steer'] and not math.isnan(float(r['steer']))]
        rec_leg['steer_max_deg'] = math.degrees(max(st)) if st else None

        if node.gt is not None:
            rec_leg['final_truth'] = list(node.gt)
            rec_leg['truth_pos_err_m'] = math.hypot(node.gt[0] - wx,
                                                    node.gt[1] - wy)
            rec_leg['truth_yaw_err_deg'] = math.degrees(
                _wrap(node.gt[2] - wyaw))
        mp = node.map_pose()
        if mp is not None:
            rec_leg['final_believed_map'] = list(mp)
            rec_leg['believed_pos_err_m'] = math.hypot(mp[0] - mx, mp[1] - my)
            rec_leg['believed_yaw_err_deg'] = math.degrees(
                _wrap(mp[2] - myaw))

        print('  {:<12} {:<18} {:>7.2f} s  believed {:.3f} m / {:+.2f} deg'
              '  truth {:.3f} m / {:+.2f} deg  entry-heading {}'
              '  reversals-after-entry {}{}'.format(
                  label, status_name, rec_leg['elapsed_s'],
                  rec_leg.get('believed_pos_err_m', float('nan')),
                  rec_leg.get('believed_yaw_err_deg', float('nan')),
                  rec_leg.get('truth_pos_err_m', float('nan')),
                  rec_leg.get('truth_yaw_err_deg', float('nan')),
                  'none' if rec_leg['entry_heading_deg'] is None
                  else '{:+.2f} deg'.format(rec_leg['entry_heading_deg']),
                  rec_leg['reversals_after_entry'],
                  '  SHUFFLE' if rec_leg['shuffle'] else ''))
        legs.append(rec_leg)
        return rec_leg

    # ----------------------------------------------------------------- #
    # the sequence
    # ----------------------------------------------------------------- #
    print('')
    print('LEGS')
    outcome = 'FAILED'
    go_arounds = 0
    bound_fired = False

    first = drive('stage', sx, sy, syaw, args.staging_checker,
                  args.staging_timeout)
    if first['status'] != 'SUCCEEDED':
        outcome = 'FAILED_AT_STAGING'
    else:
        for attempt in range(args.max_go_arounds + 1):
            leg = drive('approach{}'.format(attempt), args.x, args.y, args.yaw,
                        args.final_checker, args.approach_timeout)
            if leg['status'] == 'SUCCEEDED':
                outcome = 'REACHED'
                break
            if attempt >= args.max_go_arounds:
                # THE BOUND. Not a retry loop with a large number in it: the
                # count is fixed, it is stated, and when it is spent the run
                # reports failure instead of continuing to manoeuvre.
                bound_fired = True
                outcome = 'FAILED_GO_AROUND_BOUND'
                print('  GO-AROUND BOUND REACHED: {} approach(es) attempted, '
                      '{} go-around(s) allowed and spent. Reporting failure '
                      'rather than continuing to manoeuvre.'.format(
                          attempt + 1, args.max_go_arounds))
                break
            go_arounds += 1
            back = drive('goaround{}'.format(attempt), sx, sy, syaw,
                         args.staging_checker, args.staging_timeout)
            if back['status'] != 'SUCCEEDED':
                outcome = 'FAILED_RETURNING_TO_STAGING'
                break

    # ----------------------------------------------------------------- #
    # the verdict
    # ----------------------------------------------------------------- #
    loc = _localization_stats(rows, rec)
    approach_legs = [l for l in legs if l['leg'].startswith('approach')]
    shuffled = [l['leg'] for l in legs if l['shuffle']]

    print('')
    print('RESULT           {}'.format(outcome))
    print('go-arounds       {} used of {} allowed{}'.format(
        go_arounds, args.max_go_arounds,
        '   BOUND FIRED' if bound_fired else ''))
    print('legs             {}'.format(len(legs)))
    total = sum(l['elapsed_s'] for l in legs)
    print('elapsed          {:.2f} s of simulation time over all legs'
          .format(total))
    if approach_legs:
        last = approach_legs[-1]
        print('final approach   {}  believed {:.4f} m / {:+.3f} deg'.format(
            last['status'], last.get('believed_pos_err_m', float('nan')),
            last.get('believed_yaw_err_deg', float('nan'))))
        if last.get('truth_pos_err_m') is not None:
            print('  ABSOLUTE goal error (truth vs commanded goal): {}'
                  .format(against_floor(last['truth_pos_err_m'],
                                        rec['residual_max_m'])))
            print('  heading error {:+.3f} deg'.format(
                last['truth_yaw_err_deg']))
        print('  entry heading  {}   (the 8.594 deg discriminator)'.format(
            'never entered the circle'
            if last['entry_heading_deg'] is None
            else '{:+.3f} deg'.format(last['entry_heading_deg'])))
    print('SHUFFLE REGIME   {}   (>= {} commanded direction reversals after '
          'first entry into the position circle, counted per leg)'.format(
              'NO' if not shuffled else 'YES: ' + ', '.join(shuffled),
              _SHUFFLE_REVERSALS))
    if loc:
        print('LOCALIZATION     believed vs truth over the whole run, '
              'n = {}'.format(loc['n']))
        print('  position       rms {:.4f} m   MAX {:.4f} m   '
              '(0.263 m is what footprint_padding is dimensioned from)'
              .format(loc['pos_rms'], loc['pos_max']))
        print('  heading        rms {:.2f} deg  MAX {:.2f} deg'.format(
            loc['yaw_rms'], loc['yaw_max']))

    # ----------------------------------------------------------------- #
    # artefacts
    # ----------------------------------------------------------------- #
    if args.csv:
        with open(args.csv, 'w', newline='', encoding='utf-8') as fh:
            wr = csv.DictWriter(fh, fieldnames=_STAGE_FIELDS)
            wr.writeheader()
            wr.writerows(rows)
        print('wrote {} ({} samples, all legs)'.format(args.csv, len(rows)))

        # The final approach leg on its own, so `analyse` scores it exactly
        # as it scores a `goal` run - same columns, same plan, one leg.
        if approach_legs:
            last = approach_legs[-1]
            stem, ext = os.path.splitext(args.csv)
            apath = stem + '-approach' + (ext or '.csv')
            with open(apath, 'w', newline='', encoding='utf-8') as fh:
                wr = csv.DictWriter(fh, fieldnames=_STAGE_FIELDS)
                wr.writeheader()
                wr.writerows(rows[last['row0']:last['row1']])
            print('wrote {} ({} samples, final approach leg only)'.format(
                apath, last['row1'] - last['row0']))

    if args.plan:
        last_plan = approach_legs[-1]['plan_map'] if approach_legs else None
        payload = {
            'command': 'stage',
            'staging_distance_m': args.d,
            'staging_world': [sx, sy, syaw],
            'staging_map': list(stage_map),
            'goal_world': [args.x, args.y, args.yaw],
            'goal_map': list(goal_map),
            'status': ('SUCCEEDED' if outcome == 'REACHED' else outcome),
            'outcome': outcome,
            'go_arounds_used': go_arounds,
            'go_arounds_allowed': args.max_go_arounds,
            'go_around_bound_fired': bound_fired,
            'shuffle_legs': shuffled,
            'shuffle_threshold_reversals': _SHUFFLE_REVERSALS,
            'localization': loc,
            'elapsed_s': total,
            'plans_published': node.plan_count,
            'refusals': node.refusals,
            'legs': legs,
            # `first_plan_map` is the FINAL APPROACH leg's plan, so
            # `analyse --csv <...>-approach.csv --plan <this>` reports
            # tracking against the path that leg was actually given.
            'first_plan_map': last_plan,
            'last_plan_map': node.last_plan,
        }
        with open(args.plan, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        print('wrote {}'.format(args.plan))

    node.destroy_node()
    rclpy.shutdown()
    return 0 if outcome == 'REACHED' else 1


# --------------------------------------------------------------------------- #
# plan - the PLANNER on its own, with no plant and no controller
# --------------------------------------------------------------------------- #
#
# WHY THIS EXISTS SEPARATELY FROM `goal`. A `goal` run measures the planner,
# the controller, the converter, the estimator and the physics at once, and
# costs a simulator. `ComputePathToPose` takes an explicit start pose
# (`use_start`), so the PLAN can be measured against a bare planner_server
# and a map_server in a few seconds - which is what makes it honest to state
# what a planner parameter changed, instead of changing several and driving
# once.
#
# WHAT IT MEASURES THAT `analyse` CANNOT: the deviation of the plan from the
# straight line between its own endpoints. In a straight aisle that number
# IS the planner's quality, and it comes straight out of the vehicle's
# lateral budget: the aisle is 3.80 m, the padded footprint is 1.638 m wide,
# so a plan that wanders 0.35 m off the line has spent a third of the
# remaining clearance before the controller has made its first error.

def _lateral_excursion(poses):
    """Largest perpendicular distance from the chord between the ends."""
    if len(poses) < 3:
        return 0.0
    ax, ay = poses[0][0], poses[0][1]
    bx, by = poses[-1][0], poses[-1][1]
    dx, dy = bx - ax, by - ay
    n = math.hypot(dx, dy)
    if n < 1e-9:
        return 0.0
    worst = 0.0
    for p in poses:
        d = abs((p[0] - ax) * dy - (p[1] - ay) * dx) / n
        worst = max(worst, d)
    return worst


def cmd_plan(args):
    import rclpy
    from action_msgs.msg import GoalStatus
    from geometry_msgs.msg import PoseStamped
    from nav2_msgs.action import ComputePathToPose
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    import time as _time

    rec = load_registration(args.registration)
    sx, sy, syaw = world_to_map(rec, args.start_x, args.start_y,
                                args.start_yaw)
    gx, gy, gyaw = world_to_map(rec, args.x, args.y, args.yaw)

    _CODES = {0: 'NONE', 200: 'UNKNOWN', 201: 'INVALID_PLANNER',
              202: 'TF_ERROR', 203: 'START_OUTSIDE_MAP',
              204: 'GOAL_OUTSIDE_MAP', 205: 'START_OCCUPIED',
              206: 'GOAL_OCCUPIED', 207: 'TIMEOUT', 208: 'NO_VALID_PATH'}

    def stamped(x, y, yaw):
        p = PoseStamped()
        p.header.frame_id = 'map'
        p.pose.position.x, p.pose.position.y = x, y
        p.pose.orientation.z = math.sin(yaw / 2.0)
        p.pose.orientation.w = math.cos(yaw / 2.0)
        return p

    rclpy.init()
    node = Node('nav2_plan',
                parameter_overrides=[Parameter('use_sim_time', value=False)])
    client = ActionClient(node, ComputePathToPose, 'compute_path_to_pose')
    if not client.wait_for_server(timeout_sec=args.server_timeout):
        print('FAIL: /compute_path_to_pose did not appear within {:.0f} s'
              .format(args.server_timeout))
        node.destroy_node()
        rclpy.shutdown()
        return 2

    goal = ComputePathToPose.Goal()
    goal.start = stamped(sx, sy, syaw)
    goal.goal = stamped(gx, gy, gyaw)
    goal.use_start = True
    goal.planner_id = args.planner_id

    t0 = _time.monotonic()
    fut = client.send_goal_async(goal)
    while not fut.done():
        rclpy.spin_once(node, timeout_sec=0.05)
    handle = fut.result()
    if not handle.accepted:
        print('REFUSED AT ACCEPTANCE')
        node.destroy_node()
        rclpy.shutdown()
        return 1
    rfut = handle.get_result_async()
    while not rfut.done():
        rclpy.spin_once(node, timeout_sec=0.05)
        if _time.monotonic() - t0 > args.wall_timeout:
            print('WALL TIMEOUT waiting for a plan')
            node.destroy_node()
            rclpy.shutdown()
            return 2
    res = rfut.result()
    wall = _time.monotonic() - t0

    status = {GoalStatus.STATUS_SUCCEEDED: 'SUCCEEDED',
              GoalStatus.STATUS_ABORTED: 'ABORTED',
              GoalStatus.STATUS_CANCELED: 'CANCELED'}.get(
                  res.status, 'status {}'.format(res.status))
    code = getattr(res.result, 'error_code', 0)
    msg = getattr(res.result, 'error_msg', '')
    poses = [(p.pose.position.x, p.pose.position.y, _yaw_of(p.pose.orientation))
             for p in res.result.path.poses]

    print('start world ({:+.3f}, {:+.3f}) yaw {:+.4f} -> map '
          '({:+.3f}, {:+.3f})'.format(args.start_x, args.start_y,
                                      args.start_yaw, sx, sy))
    print('goal  world ({:+.3f}, {:+.3f}) yaw {:+.4f} -> map '
          '({:+.3f}, {:+.3f})'.format(args.x, args.y, args.yaw, gx, gy))
    print('RESULT      {}'.format(status))
    print('error_code  {} {}'.format(code, _CODES.get(code, '')))
    if msg:
        print('error_msg   {}'.format(msg))
    pt = res.result.planning_time
    print('planning    {:.3f} s reported by the server, {:.3f} s wall '
          'round trip'.format(pt.sec + pt.nanosec * 1e-9, wall))
    print('points      {}'.format(len(poses)))
    if poses:
        length, cusps, rev = _path_metrics(poses)
        chord = math.hypot(poses[-1][0] - poses[0][0],
                           poses[-1][1] - poses[0][1])
        print('length      {:.3f} m   (straight line between the ends is '
              '{:.3f} m)'.format(length, chord))
        print('cusps       {}   reverse {:.1f} % of the length'
              .format(cusps, 100 * rev))
        print('EXCURSION   {:.3f} m off the straight line between the ends'
              .format(_lateral_excursion(poses)))
        print('goal gap    {:.3f} m between the last path pose and the '
              'commanded goal'.format(
                  math.hypot(poses[-1][0] - gx, poses[-1][1] - gy)))
    if args.plan:
        with open(args.plan, 'w', encoding='utf-8') as fh:
            json.dump({'goal_map': [gx, gy, gyaw],
                       'start_map': [sx, sy, syaw],
                       'status': status, 'error_code': code,
                       'first_plan_map': poses, 'last_plan_map': poses,
                       'goal_world': [args.x, args.y, args.yaw]}, fh)
        print('wrote {}'.format(args.plan))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if status == 'SUCCEEDED' else 1


# --------------------------------------------------------------------------- #
# convcheck - the conversion against a COMMANDED MOTION
# --------------------------------------------------------------------------- #
#
# WHY THIS IS NOT THE SELF-CHECK. `cmd_vel_to_tricycle.py --self-check`
# round-trips (v, w) -> (delta, v_D) -> (v', w') through an independently
# written forward model. That proves the algebra is self-consistent and
# nothing else: if the wheelbase were wrong, or the traction topic carried
# body speed instead of tread speed, or the steer sign were inverted, the
# round trip would still close exactly.
#
# THIS check closes the loop through the PHYSICS. It publishes a known twist
# on the converter's input topic and measures the resulting body motion from
# the simulator's own pose of the model. The comparison is between the
# COMMANDED (v, w) and the ACHIEVED (v, w) - so wheelbase, wheel radius, the
# tread-speed convention and both signs are all in the measurement.
#
# WHAT IT DOES NOT CONTROL FOR, stated before any figure is read: the
# physics engine produces tyre slip, and a steered wheel on lock scrubs. So
# the achieved radius is not expected to equal the commanded one exactly,
# and the residual reported below is a measurement of conversion PLUS slip,
# never of the conversion alone. It is an upper bound on the conversion's
# own error.

#: (label, v [m/s], w [rad/s]).
#:
#: EVERY SEGMENT IS RETRACED BY THE ONE AFTER IT, and that is not a
#: presentation choice - it is what makes the run measurable at all. An
#: earlier ordering (left arc, mirrored right arc, ...) accumulated
#: translation: over eight 8 s segments it walked the vehicle 7 m across the
#: apron and INTO a rack face, and the two tightest arcs of that run
#: measured 0.09 and 0.00 m/s against a commanded 0.30 - a contact, silently
#: reported as a conversion result. Retracing bounds the whole run inside
#: one segment length of the start.
#:
#: A RETRACE IS THE SAME STEER ANGLE DRIVEN BACKWARDS. From (1),
#: w = v tan(delta)/L, so negating v and w together holds delta and the
#: vehicle runs back along the arc it just drove. That is also why the
#: retrace rows are the reverse-arc measurement this vehicle needs: a
#: Reeds-Shepp reverse segment is exactly this manoeuvre.
def _conv_segments(wheelbase_m):
    v = 0.30
    return [
        ('straight ahead',                                    v,  0.0),
        ('straight astern - retraces the row above',         -v,  0.0),
        ('left,  R = 2.10 m  (delta +26.57 deg)',             v,  v / 2.10),
        ('astern on the same lock, R = 2.10 m - retrace',    -v, -v / 2.10),
        ('left,  R = 1.05 m  (delta +45.0 deg, the tightest planned arc)',
         v,  v / 1.05),
        ('astern on the same lock, R = 1.05 m - retrace',    -v, -v / 1.05),
        ('right, R = 1.05 m  (delta -45.0 deg)',              v, -v / 1.05),
        ('astern on the same lock, R = 1.05 m - retrace',    -v,  v / 1.05),
        ('ROTATION IN PLACE - must be REFUSED',             0.0,  0.50),
    ]


def cmd_convcheck(args):
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from std_msgs.msg import Float64, UInt32
    import time as _time
    import yaml as _yaml

    with open(args.config, encoding='utf-8') as fh:
        cfg = _yaml.safe_load(fh)
    L = cfg['model']['wheelbase_m']
    dmax = cfg['model']['steer_limit_rad']

    class Conv(Node):
        def __init__(self):
            super().__init__(
                'nav2_convcheck',
                parameter_overrides=[Parameter('use_sim_time', value=True)])
            self.gt = None
            self.steer = float('nan')
            self.traction = float('nan')
            self.refusals = 0
            self.pub = self.create_publisher(Twist, args.cmd_topic, 10)
            self.create_subscription(Odometry, '/forklift/odom',
                                     self.cb_ground_truth, 10)
            self.create_subscription(
                Float64, '/forklift/cmd/steer_angle', self.cb_steer, 10)
            self.create_subscription(
                Float64, '/forklift/cmd/traction_speed', self.cb_traction, 10)
            self.create_subscription(
                UInt32, '/forklift/nav/tricycle_refusals',
                self.cb_refusals, 10)

        # cb_* so none can shadow an rclpy Node attribute.
        def cb_ground_truth(self, msg):
            p = msg.pose.pose
            self.gt = (p.position.x, p.position.y, _yaw_of(p.orientation))

        def cb_steer(self, msg):
            self.steer = msg.data

        def cb_traction(self, msg):
            self.traction = msg.data

        def cb_refusals(self, msg):
            self.refusals = msg.data

        def sim_time(self):
            return self.get_clock().now().nanoseconds * 1e-9

    rclpy.init()
    node = Conv()

    # BOUNDED WALL POLL for the reference stream. Until it exists there is
    # nothing to measure against and no reason to believe /clock is read.
    deadline = _time.monotonic() + args.settle
    while _time.monotonic() < deadline and node.gt is None:
        rclpy.spin_once(node, timeout_sec=0.05)
    if node.gt is None:
        print('FAIL: no /forklift/odom after {:.0f} s. The bringup is not up.'
              .format(args.settle))
        node.destroy_node()
        rclpy.shutdown()
        return 2

    rows = []
    results = []
    wall0 = _time.monotonic()
    row_period = 1.0 / args.record_hz
    next_row = node.sim_time()
    for label, v, w in _conv_segments(L):
        msg = Twist()
        msg.linear.x, msg.angular.z = v, w
        t_start = node.sim_time()
        t_meas = t_start + args.slew          # discard the steer slew
        t_end = t_start + args.segment
        p_meas = None
        p_last = None
        t_last = None
        path = 0.0
        ref0 = node.refusals
        steer_seen = []
        traction_seen = []
        while True:
            node.pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=0.02)
            now = node.sim_time()
            gt = node.gt
            if gt is None:
                continue
            if p_last is not None:
                path += math.hypot(gt[0] - p_last[0], gt[1] - p_last[1])
            p_last, t_last = gt, now
            if p_meas is None and now >= t_meas:
                p_meas, t_meas_actual, path0 = gt, now, path
                steer_seen, traction_seen = [], []
            if p_meas is not None:
                if math.isfinite(node.steer):
                    steer_seen.append(node.steer)
                if math.isfinite(node.traction):
                    traction_seen.append(node.traction)
            # THE RECORDING IS RATE LIMITED AND THE MEASUREMENT IS NOT.
            # `rclpy.spin_once` returns as soon as there is work, so this
            # loop turns several thousand times a second; recording every
            # turn produced a 27 MB CSV for 64 s of simulation, in which
            # consecutive rows carry the same 20 Hz ground-truth pose. The
            # integration above still sees every turn.
            if now >= next_row:
                next_row = now + row_period
                rows.append('{:.3f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},'
                            '{:.6f},{:.6f},{}'.format(
                                now, gt[0], gt[1], gt[2], v, w,
                                node.steer, node.traction, node.refusals))
            if now >= t_end:
                break
            if _time.monotonic() - wall0 > args.wall_timeout:
                print('WALL TIMEOUT: /clock has stalled.')
                break

        dt = t_last - t_meas_actual
        dyaw = _wrap(p_last[2] - p_meas[2])
        dpath = path - path0
        # SIGNED speed: the sign of the displacement projected on the
        # heading the vehicle held. A reversing vehicle covers path too.
        dx, dy = p_last[0] - p_meas[0], p_last[1] - p_meas[1]
        along = dx * math.cos(p_meas[2]) + dy * math.sin(p_meas[2])
        sign = 1.0 if along >= 0.0 else -1.0
        v_meas = sign * dpath / dt if dt > 0 else float('nan')
        w_meas = dyaw / dt if dt > 0 else float('nan')
        steer_cmd = (sum(steer_seen) / len(steer_seen)) if steer_seen \
            else float('nan')
        traction_cmd = (sum(traction_seen) / len(traction_seen)) \
            if traction_seen else float('nan')
        results.append({
            'label': label, 'v': v, 'w': w, 'dt': dt,
            'v_meas': v_meas, 'w_meas': w_meas,
            'steer_cmd': steer_cmd, 'traction_cmd': traction_cmd,
            'refused': node.refusals - ref0,
            'dpath': dpath, 'dyaw': dyaw,
        })

    # stop
    msg = Twist()
    for _ in range(20):
        node.pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.02)

    # ------------------------------------------------------------------ #
    print('')
    print('=' * 108)
    print('Twist -> tricycle, CHECKED AGAINST A COMMANDED MOTION')
    print('=' * 108)
    print('L = {:.4f} m   steer stop +-{:.4f} rad ({:.3f} deg)'.format(
        L, dmax, math.degrees(dmax)))
    print('Commanded on {}; achieved read from /forklift/odom, the '
          'simulator\'s own pose of the model.'.format(args.cmd_topic))
    print('delta_pub is what the converter PUBLISHED; delta_meas is '
          'atan(L * w_meas / v_meas), what the vehicle ACTUALLY drove.')
    print('')
    hdr = ('{:<58} {:>7} {:>8} | {:>8} {:>9} | {:>9} {:>9} | {:>8} {:>8} {}'
           .format('segment', 'v_cmd', 'w_cmd', 'v_meas', 'w_meas',
                   'delta_pub', 'delta_meas', 'R_cmd', 'R_meas', 'speed'))
    print(hdr)
    print('-' * len(hdr))
    worst_r = 0.0
    worst_label = ''
    short = []
    for r in results:
        if r['w'] != 0.0 and r['v'] != 0.0:
            R_cmd = '{:+8.3f}'.format(r['v'] / r['w'])
        else:
            R_cmd = '     inf' if r['v'] != 0.0 else '      --'
        if abs(r['w_meas']) > 1e-4 and abs(r['v_meas']) > 1e-4:
            R_meas_v = r['v_meas'] / r['w_meas']
            R_meas = '{:+8.3f}'.format(R_meas_v)
        else:
            R_meas_v = None
            R_meas = '     inf' if abs(r['v_meas']) > 1e-3 else '      --'
        if abs(r['v_meas']) > 1e-4:
            d_meas = math.degrees(math.atan2(
                L * r['w_meas'] * (1.0 if r['v_meas'] >= 0 else -1.0),
                abs(r['v_meas'])))
            d_meas_s = '{:+9.3f}'.format(d_meas)
        else:
            d_meas_s = '       --'
        # THE CONTACT CHECK. A segment that did not achieve the speed it was
        # given is not a conversion measurement: the vehicle was held by
        # something. It is flagged here rather than left for a reader to
        # notice, because an earlier run of this harness drove into a rack
        # and reported the contact as an arc.
        if r['v'] != 0.0:
            ratio = abs(r['v_meas']) / abs(r['v'])
            speed_note = '{:>5.0f}%'.format(100 * ratio)
            if ratio < 0.85:
                speed_note += ' HELD'
                short.append((r['label'], ratio))
        else:
            speed_note = '    --'
        print('{:<58} {:>7.3f} {:>8.4f} | {:>8.4f} {:>9.4f} | {:>9.3f} '
              '{} | {} {} {}'.format(
                  r['label'], r['v'], r['w'], r['v_meas'], r['w_meas'],
                  math.degrees(r['steer_cmd']), d_meas_s, R_cmd, R_meas,
                  speed_note))
        if r['w'] != 0.0 and r['v'] != 0.0 and R_meas_v is not None:
            rel = abs(R_meas_v - r['v'] / r['w']) / abs(r['v'] / r['w'])
            if rel > worst_r:
                worst_r, worst_label = rel, r['label']

    print('')
    print('THE REFUSAL SEGMENT, read on its own terms:')
    ref = results[-1]
    print('  commanded            v = {:+.3f} m/s, w = {:+.4f} rad/s'
          .format(ref['v'], ref['w']))
    print('  refusals counted     {} over {:.2f} s'.format(
        ref['refused'], ref['dt']))
    print('  traction published   {:+.4f} m/s'.format(ref['traction_cmd']))
    print('  the vehicle moved    {:.4f} m and turned {:+.4f} deg'.format(
        ref['dpath'], math.degrees(ref['dyaw'])))
    print('')
    if short:
        print('')
        print('SEGMENTS THAT DID NOT ACHIEVE THEIR COMMANDED SPEED - these '
              'are NOT conversion measurements:')
        for label, ratio in short:
            print('  {:.0f}% of commanded   {}'.format(100 * ratio, label))
        print('  A vehicle that will not accelerate to a speed it is given '
              'is being HELD by something. Check the ground-truth track '
              'against the map before reading any figure on those rows.')
    print('')
    print('WORST RELATIVE RADIUS ERROR over the arcs: {:.2%} ({})'.format(
        worst_r, worst_label))
    print('That figure contains TYRE SLIP as well as the conversion, so it '
          'is an UPPER BOUND on the conversion\'s own error and is never '
          'quoted as the conversion\'s error.')

    if args.csv:
        with open(args.csv, 'w', encoding='utf-8') as fh:
            fh.write('t_sim,gt_x,gt_y,gt_yaw,cmd_v,cmd_w,steer,traction,'
                     'refusals\n')
            fh.write('\n'.join(rows) + '\n')
        print('wrote {} ({} samples)'.format(args.csv, len(rows)))

    node.destroy_node()
    rclpy.shutdown()
    return 0


# --------------------------------------------------------------------------- #
# analyse
# --------------------------------------------------------------------------- #

#: A direction change counts as a cusp only once the new direction has
#: persisted for this many metres. THE REASON IS A MEASUREMENT, not taste:
#: on a path whose points are 0.05 m apart and whose headings come out of a
#: smoother, the sign of (step . heading) flips on single points wherever
#: the step is a few millimetres. Counting those, this function reported
#: "2 cusps, 0.7 % reverse" for a plan down a straight aisle - 0.07 m of
#: "reverse" spread over two points. A tricycle's cusp is a real event: it
#: stops, slews the steer axis across, and sets off the other way. 0.25 m
#: is five path points and half the shortest reverse leg the planner's own
#: 1.05 m turning radius can produce.
_CUSP_MIN_RUN_M = 0.25


def _path_metrics(poses):
    """Length, direction reversals (cusps) and reverse fraction of a path.

    A path point's DIRECTION is the sign of the dot product between the
    step it takes and the heading it carries. A Reeds-Shepp cusp is where
    that sign flips AND STAYS FLIPPED - see `_CUSP_MIN_RUN_M`. Counting it
    from the path's own headings rather than from a velocity means the
    count is a property of the PLAN, available before the vehicle moves."""
    if not poses or len(poses) < 3:
        return 0.0, 0, 0.0
    length = 0.0
    signs = []
    for i in range(len(poses) - 1):
        dx = poses[i + 1][0] - poses[i][0]
        dy = poses[i + 1][1] - poses[i][1]
        step = math.hypot(dx, dy)
        if step < 1e-9:
            continue
        length += step
        yaw = poses[i][2]
        dot = dx * math.cos(yaw) + dy * math.sin(yaw)
        signs.append((1 if dot >= 0.0 else -1, step))

    # Collapse the sign sequence into runs, then drop every run shorter
    # than _CUSP_MIN_RUN_M into its neighbours before counting.
    runs = []
    for sg, step in signs:
        if runs and runs[-1][0] == sg:
            runs[-1][1] += step
        else:
            runs.append([sg, step])
    merged = []
    for sg, run_len in runs:
        if run_len < _CUSP_MIN_RUN_M and merged:
            merged[-1][1] += run_len
        elif merged and merged[-1][0] == sg:
            merged[-1][1] += run_len
        else:
            merged.append([sg, run_len])
    # a second pass, because dropping a short run can join two equal ones
    joined = []
    for sg, run_len in merged:
        if joined and joined[-1][0] == sg:
            joined[-1][1] += run_len
        else:
            joined.append([sg, run_len])

    cusps = max(0, len(joined) - 1)
    reverse_len = sum(r for sg, r in joined if sg < 0)
    return length, cusps, (reverse_len / length if length > 0 else 0.0)


def _cross_track(point, poly):
    """Shortest distance from a point to a polyline."""
    best = float('inf')
    for i in range(len(poly) - 1):
        ax, ay = poly[i][0], poly[i][1]
        bx, by = poly[i + 1][0], poly[i + 1][1]
        dx, dy = bx - ax, by - ay
        den = dx * dx + dy * dy
        if den < 1e-12:
            d = math.hypot(point[0] - ax, point[1] - ay)
        else:
            t = ((point[0] - ax) * dx + (point[1] - ay) * dy) / den
            t = max(0.0, min(1.0, t))
            d = math.hypot(point[0] - (ax + t * dx),
                           point[1] - (ay + t * dy))
        best = min(best, d)
    return best


def cmd_analyse(args):
    rec = load_registration(args.registration)
    floor = rec['residual_max_m']

    with open(args.csv, newline='', encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit('empty recording: {}'.format(args.csv))

    def num(row, key):
        v = row.get(key, '')
        return float(v) if v not in ('', None) else None

    payload = {}
    if args.plan and os.path.exists(args.plan):
        with open(args.plan, encoding='utf-8') as fh:
            payload = json.load(fh)

    print('=' * 74)
    print('nav2_run analyse   {}'.format(os.path.basename(args.csv)))
    print('=' * 74)
    print('FLOOR   registration residual rms {:.4f} m, MAX {:.4f} m'.format(
        rec['residual_rms_m'], floor))
    print('samples {}   simulation span {:.2f} s'.format(
        len(rows), num(rows[-1], 't_sim') - num(rows[0], 't_sim')))

    if payload:
        print('status  {}   error_code {}   plans {}   refusals {}'.format(
            payload.get('status'), payload.get('error_code'),
            payload.get('plans_published'), payload.get('refusals')))

    # ---- the plan the vehicle was given, in world coordinates ----
    plan_world = []
    if payload.get('first_plan_map'):
        plan_world = [map_to_world(rec, *p)
                      for p in payload['first_plan_map']]
        length, cusps, rev = _path_metrics(plan_world)
        print('')
        print('THE PLAN (first published)')
        print('  points        {}'.format(len(plan_world)))
        print('  length        {:.3f} m'.format(length))
        print('  cusps         {}   (direction reversals in the plan)'
              .format(cusps))
        print('  reverse       {:.1f} % of the path length'.format(100 * rev))

    # ---- the drive ----
    gt = [(num(r, 'gt_x'), num(r, 'gt_y'), num(r, 'gt_yaw'), num(r, 't_sim'))
          for r in rows if num(r, 'gt_x') is not None]
    travelled = sum(math.hypot(gt[i + 1][0] - gt[i][0],
                               gt[i + 1][1] - gt[i][1])
                    for i in range(len(gt) - 1))
    v = [num(r, 'cmd_v') for r in rows if num(r, 'cmd_v') is not None]
    tr = [num(r, 'traction') for r in rows
          if num(r, 'traction') is not None and
          not math.isnan(num(r, 'traction'))]
    st = [num(r, 'steer') for r in rows
          if num(r, 'steer') is not None and
          not math.isnan(num(r, 'steer'))]
    moving = [x for x in v if abs(x) > 0.02]

    print('')
    print('THE DRIVE')
    print('  ground-truth path      {:.3f} m'.format(travelled))
    if moving:
        print('  commanded speed        mean {:+.3f}  max {:+.3f}  '
              'min {:+.3f} m/s (moving samples)'.format(
                  sum(moving) / len(moving), max(v), min(v)))
    fwd = sum(1 for x in v if x > 0.02)
    rvs = sum(1 for x in v if x < -0.02)
    print('  command sign           {} forward / {} reverse / {} at rest'
          .format(fwd, rvs, len(v) - fwd - rvs))
    if st:
        print('  steer angle commanded  max |{:.4f}| rad ({:.2f} deg), '
              'stop is 1.3100 rad'.format(
                  max(abs(x) for x in st),
                  math.degrees(max(abs(x) for x in st))))
    if tr:
        print('  drive-wheel speed      max |{:.3f}| m/s, limit is '
              '1.500 m/s'.format(max(abs(x) for x in tr)))
    refs = [int(r['refusals']) for r in rows if r.get('refusals')]
    if refs:
        print('  rotation-in-place      {} refused over the run'
              .format(max(refs)))

    # ---- tracking, against the plan the vehicle was given ----
    if plan_world and len(plan_world) > 1:
        errs = [_cross_track(p, plan_world) for p in gt]
        errs_sorted = sorted(errs)
        print('')
        print('TRACKING (ground truth against the FIRST plan, world frame)')
        print('  rms   {:.4f} m'.format(
            math.sqrt(sum(e * e for e in errs) / len(errs))))
        print('  max   {:.4f} m'.format(max(errs)))
        print('  p95   {:.4f} m'.format(
            errs_sorted[int(0.95 * (len(errs_sorted) - 1))]))
        print('  NOTE: the plan is a MAP-frame object and the truth is a '
              'world-frame one, so this figure contains the localization '
              'error as well as the controller\'s. It is an upper bound on '
              'the controller and is never quoted as the controller\'s own.')

    # ---- the goal ----
    if payload.get('goal_world'):
        gxw, gyw, gyw_yaw = payload['goal_world']
        fx, fy, fyaw, _ = gt[-1]
        d = math.hypot(fx - gxw, fy - gyw)
        print('')
        print('THE GOAL')
        print('  commanded (world)      ({:+.4f}, {:+.4f}) yaw {:+.4f} rad'
              .format(gxw, gyw, gyw_yaw))
        print('  reached   (truth)      ({:+.4f}, {:+.4f}) yaw {:+.4f} rad'
              .format(fx, fy, fyaw))
        print('  ABSOLUTE position error {}'.format(against_floor(d, floor)))
        print('  heading error           {:+.3f} deg'.format(
            math.degrees(_wrap(fyaw - gyw_yaw))))
        amcl = [(num(r, 'amcl_x'), num(r, 'amcl_y'), num(r, 'amcl_yaw'))
                for r in rows if num(r, 'amcl_x') is not None]
        if amcl and payload.get('goal_map'):
            bx, by, byaw = amcl[-1]
            gmx, gmy, gmyaw = payload['goal_map']
            db = math.hypot(bx - gmx, by - gmy)
            print('  BELIEVED error (map)    {:.4f} m, heading {:+.3f} deg'
                  .format(db, math.degrees(_wrap(byaw - gmyaw))))
            print('  belief vs truth         the vehicle thought it was '
                  '{:.4f} m from the goal and was really {:.4f} m'
                  .format(db, d))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Send a goal to the forklift\'s Nav2 stack and score it.')
    sub = parser.add_subparsers(dest='command', required=True)

    g = sub.add_parser('goal', help='send one goal and record the run')
    g.add_argument('--x', type=float, required=True,
                   help='goal x in the WORLD frame [m]')
    g.add_argument('--y', type=float, required=True,
                   help='goal y in the WORLD frame [m]')
    g.add_argument('--yaw', type=float, default=0.0,
                   help='goal yaw in the WORLD frame [rad]')
    g.add_argument('--csv', default=None, help='write the 10 Hz recording here')
    g.add_argument('--plan', default=None,
                   help='write the plan and the result here (JSON)')
    g.add_argument('--timeout', type=float, default=240.0,
                   help='give up after this much SIMULATION time [s]')
    g.add_argument('--wall-timeout', type=float, default=1200.0,
                   help='hard backstop in WALL seconds, for a stalled clock')
    g.add_argument('--settle', type=float, default=30.0,
                   help='WALL seconds to wait for a transform tree and a '
                        'ground-truth reference before sending')
    g.add_argument('--server-timeout', type=float, default=60.0,
                   help='wall seconds to wait for the action server')
    g.add_argument('--record-hz', type=float, default=10.0)
    g.add_argument('--cmd-topic', default='/cmd_vel_smoothed',
                   help='the Twist topic to record as the command')
    g.add_argument('--registration', default=None)
    g.set_defaults(func=cmd_goal)

    p = sub.add_parser(
        'plan',
        help='ask the PLANNER alone for a path between two stated poses. '
             'Needs a planner_server and a map_server; needs no simulator, '
             'no controller and no localizer.')
    p.add_argument('--start-x', type=float, required=True)
    p.add_argument('--start-y', type=float, required=True)
    p.add_argument('--start-yaw', type=float, default=0.0)
    p.add_argument('--x', type=float, required=True,
                   help='goal x in the WORLD frame [m]')
    p.add_argument('--y', type=float, required=True)
    p.add_argument('--yaw', type=float, default=0.0)
    p.add_argument('--planner-id', default='GridBased')
    p.add_argument('--plan', default=None, help='write the plan here (JSON)')
    p.add_argument('--server-timeout', type=float, default=60.0)
    p.add_argument('--wall-timeout', type=float, default=120.0)
    p.add_argument('--registration', default=None)
    p.set_defaults(func=cmd_plan)

    c = sub.add_parser(
        'convcheck',
        help='check the Twist -> tricycle conversion against a COMMANDED '
             'MOTION. Needs the bringup and the converter; needs no '
             'planner, controller or localizer.')
    c.add_argument('--config', default=os.path.join(_FORKLIFT_DIR,
                                                    'config.yaml'))
    c.add_argument('--cmd-topic', default='/cmd_vel_smoothed',
                   help='the converter\'s input topic to publish onto')
    c.add_argument('--segment', type=float, default=8.0,
                   help='SIMULATION seconds per segment')
    c.add_argument('--slew', type=float, default=2.5,
                   help='SIMULATION seconds discarded at the head of each '
                        'segment while the steer axis slews to its new '
                        'angle (model.sdf steer_joint <velocity> 2.0 rad/s, '
                        'so 90 deg takes 0.79 s; this is generous)')
    c.add_argument('--settle', type=float, default=60.0,
                   help='WALL seconds to wait for the ground-truth stream')
    c.add_argument('--wall-timeout', type=float, default=900.0)
    c.add_argument('--record-hz', type=float, default=50.0,
                   help='rows per SIMULATION second in the CSV. The '
                        'measurement integrates every loop turn whatever '
                        'this is; it bounds the file, which was 27 MB for '
                        '64 s before it existed.')
    c.add_argument('--csv', default=None)
    c.set_defaults(func=cmd_convcheck)

    a = sub.add_parser('analyse', help='score a recording')
    a.add_argument('--csv', required=True)
    a.add_argument('--plan', default=None)
    a.add_argument('--registration', default=None)
    a.set_defaults(func=cmd_analyse)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
