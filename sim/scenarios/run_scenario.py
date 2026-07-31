#!/usr/bin/env python3
"""run_scenario.py - scripted navigation run of the PARKED navigation
scenario (brief m3-02). NOT current work: see sim/scenarios/DEFERRED.md.

The vehicle platform this script was written against was retired by
ADR 0010 D1, and the vendor workspace its bringup needed is no longer
provisioned by sim/setup/install.sh, so it cannot be run as it stands. The
odometry topic below is a retired-platform value kept as the record of the
parked scenario; m5-10 decides the forklift's topics.

Preconditions (two other terminals, both with /opt/ros/jazzy sourced):
  1. ros2 launch sim/launch/warehouse_bringup.launch.py      (m3-01 bringup)
  2. ros2 launch sim/scenarios/nav_scenario.launch.py        (Nav2 stack)

What it does, all on sim time, with generous wall-clock timeouts because
the headless container runs at real-time factor ~0.1:
  1. waits for /clock and for the navigate_to_pose action server (Nav2
     lifecycle activation),
  2. publishes the initial pose on /initialpose (defaults to the bringup
     spawn pose -10, -6, yaw 0) until AMCL answers on /amcl_pose with a
     reasonable covariance,
  3. sends a NavigateToPose goal (default -6.0, 1.5: Aisle A, reached by
     driving north past the west end of rack row B and turning east - a
     real path around the racks, ~11 m),
  4. samples /amcl_pose and odometry periodically while the goal runs,
  5. awaits the action result and writes EVIDENCE_NAV.md next to this
     script: initial pose, goal, pose samples, final result status
     (SUCCESS = status 4), odometry distance traveled, wall/sim durations.

Exit code 0 only if the goal result is STATUS_SUCCEEDED.

Usage:
  python3 sim/scenarios/run_scenario.py [--goal-x -6.0 --goal-y 1.5 ...]
"""

import argparse
import datetime
import math
import os
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.parameter import Parameter

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

STATUS_NAMES = {
    GoalStatus.STATUS_SUCCEEDED: 'SUCCEEDED',
    GoalStatus.STATUS_ABORTED: 'ABORTED',
    GoalStatus.STATUS_CANCELED: 'CANCELED',
}


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class ScenarioRunner(Node):

    def __init__(self):
        super().__init__(
            'nav_scenario_runner',
            parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.amcl_pose = None
        self.odom = None
        self._last_odom_xy = None
        self.distance = 0.0
        self.feedback = None
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self._on_amcl, 10)
        self.create_subscription(
            Odometry, '/robot/robotnik_base_control/odom', self._on_odom, 10)
        self.init_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10)
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def _on_amcl(self, msg):
        self.amcl_pose = msg

    def _on_odom(self, msg):
        self.odom = msg
        xy = (msg.pose.pose.position.x, msg.pose.pose.position.y)
        if self._last_odom_xy is not None:
            d = math.hypot(xy[0] - self._last_odom_xy[0],
                           xy[1] - self._last_odom_xy[1])
            if d > 1e-4:
                self.distance += d
        self._last_odom_xy = xy

    # -- helpers ----------------------------------------------------------

    def spin_until(self, cond, wall_timeout, what):
        """Spin the node until cond() is true. Wall-clock timeout."""
        deadline = time.monotonic() + wall_timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.2)
            if cond():
                return True
        raise TimeoutError(f'timed out after {wall_timeout:.0f}s wall '
                           f'waiting for {what}')

    def sim_now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def publish_initial_pose(self, x, y, yaw):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        cov = [0.0] * 36
        cov[0] = cov[7] = 0.25
        cov[35] = 0.068
        msg.pose.covariance = cov
        self.init_pub.publish(msg)

    def amcl_summary(self):
        if self.amcl_pose is None:
            return 'no /amcl_pose received'
        p = self.amcl_pose.pose.pose
        c = self.amcl_pose.pose.covariance
        return (f'x={p.position.x:.3f} y={p.position.y:.3f} '
                f'yaw={yaw_of(p.orientation):.3f} rad | '
                f'cov diag (xx, yy, yawyaw) = '
                f'({c[0]:.4f}, {c[7]:.4f}, {c[35]:.4f})')

    def amcl_localized(self, limit=0.35):
        if self.amcl_pose is None:
            return False
        c = self.amcl_pose.pose.covariance
        return c[0] < limit and c[7] < limit and c[35] < limit


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--init-x', type=float, default=-10.0)
    ap.add_argument('--init-y', type=float, default=-6.0)
    ap.add_argument('--init-yaw', type=float, default=0.0)
    ap.add_argument('--goal-x', type=float, default=-6.0)
    ap.add_argument('--goal-y', type=float, default=1.5)
    ap.add_argument('--goal-yaw', type=float, default=0.0)
    ap.add_argument('--sample-period', type=float, default=20.0,
                    help='pose sample period, wall seconds')
    ap.add_argument('--activation-timeout', type=float, default=1800.0,
                    help='wall seconds to wait for Nav2 activation')
    ap.add_argument('--goal-timeout', type=float, default=3600.0,
                    help='wall seconds to wait for the goal result')
    ap.add_argument('--evidence', default=os.path.join(_THIS_DIR,
                                                       'EVIDENCE_NAV.md'))
    args = ap.parse_args()

    rclpy.init()
    node = ScenarioRunner()
    log = node.get_logger()
    wall_start = time.monotonic()

    # 1. Sim clock ticking (also proves the bringup is up).
    node.spin_until(lambda: node.sim_now() > 0.0, 600.0, '/clock (sim time)')
    log.info(f'sim clock at {node.sim_now():.1f}s')

    # 2. Nav2 active: navigate_to_pose action server + odom flowing.
    node.spin_until(lambda: node.nav_client.server_is_ready(),
                    args.activation_timeout, 'navigate_to_pose action server')
    node.spin_until(lambda: node.odom is not None, 300.0, 'odometry')
    log.info('Nav2 action server ready, odometry flowing')

    # 3. Initial pose -> AMCL localized. Re-publish every ~3 s wall until
    #    AMCL answers (it publishes /amcl_pose after processing a scan).
    def push_init():
        node.publish_initial_pose(args.init_x, args.init_y, args.init_yaw)
    push_init()
    deadline = time.monotonic() + 600.0
    last_pub = time.monotonic()
    while node.amcl_pose is None and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
        if time.monotonic() - last_pub > 3.0:
            push_init()
            last_pub = time.monotonic()
    if node.amcl_pose is None:
        log.error('AMCL never published /amcl_pose')
        sys.exit(1)
    node.spin_until(node.amcl_localized, 300.0, 'AMCL covariance to settle')
    initial_amcl = node.amcl_summary()
    log.info(f'AMCL localized: {initial_amcl}')

    # 4. Send the goal.
    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = 'map'
    goal.pose.header.stamp = node.get_clock().now().to_msg()
    goal.pose.pose.position.x = args.goal_x
    goal.pose.pose.position.y = args.goal_y
    goal.pose.pose.orientation.z = math.sin(args.goal_yaw / 2.0)
    goal.pose.pose.orientation.w = math.cos(args.goal_yaw / 2.0)

    def on_feedback(fb):
        node.feedback = fb.feedback

    sim_goal_start = node.sim_now()
    node.distance = 0.0
    send_future = node.nav_client.send_goal_async(
        goal, feedback_callback=on_feedback)
    node.spin_until(lambda: send_future.done(), 120.0, 'goal acceptance')
    handle = send_future.result()
    if not handle.accepted:
        log.error('goal REJECTED by bt_navigator')
        sys.exit(1)
    log.info(f'goal accepted: ({args.goal_x}, {args.goal_y}, '
             f'yaw {args.goal_yaw})')

    # 5. Await result, sampling poses periodically.
    result_future = handle.get_result_async()
    samples = []
    next_sample = time.monotonic()
    deadline = time.monotonic() + args.goal_timeout
    while not result_future.done() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
        if time.monotonic() >= next_sample:
            next_sample += args.sample_period
            if node.amcl_pose is not None:
                p = node.amcl_pose.pose.pose
                o = node.odom.pose.pose if node.odom else None
                rem = (node.feedback.distance_remaining
                       if node.feedback else float('nan'))
                samples.append((
                    time.monotonic() - wall_start, node.sim_now(),
                    p.position.x, p.position.y, yaw_of(p.orientation),
                    o.position.x if o else float('nan'),
                    o.position.y if o else float('nan'), rem))
                log.info(f'sample: amcl ({p.position.x:.2f}, '
                         f'{p.position.y:.2f}) remaining {rem:.2f} m')
    if not result_future.done():
        log.error('goal result timed out')
        sys.exit(1)

    status = result_future.result().status
    status_name = STATUS_NAMES.get(status, str(status))
    sim_goal_end = node.sim_now()
    wall_total = time.monotonic() - wall_start
    final_amcl = node.amcl_summary()
    log.info(f'result: status {status} ({status_name}), '
             f'distance {node.distance:.2f} m, final {final_amcl}')

    # 6. Evidence file.
    now = datetime.datetime.now(datetime.timezone.utc)
    rows = '\n'.join(
        f'| {w:7.1f} | {s:7.1f} | {ax:7.2f} | {ay:7.2f} | {ayaw:6.2f} '
        f'| {ox:7.2f} | {oy:7.2f} | {rem:6.2f} |'
        for (w, s, ax, ay, ayaw, ox, oy, rem) in samples)
    with open(args.evidence, 'w') as f:
        f.write(f'''# M3 navigation scenario evidence

Date: {now:%Y-%m-%d %H:%M} UTC. Host: project container, headless
(CPU-only, real-time factor ~0.1), ROS 2 Jazzy, Gazebo Harmonic.

Stack under test:
- `sim/launch/warehouse_bringup.launch.py` (m3-01 bringup, default spawn)
- `sim/scenarios/nav_scenario.launch.py` (map_server + AMCL + NavFn + DWB +
  behaviors + bt_navigator, params from its required `params_file` argument,
  map `sim/scenarios/maps/map.yaml` generated by `tools/make_map.py`)
- this script (`sim/scenarios/run_scenario.py`)

## Initial localization

Initial pose published on /initialpose: ({args.init_x}, {args.init_y}, \
yaw {args.init_yaw}).

First settled /amcl_pose: {initial_amcl}

## Goal

NavigateToPose goal in the `map` frame: \
({args.goal_x}, {args.goal_y}, yaw {args.goal_yaw}) - Aisle A, reached by
driving north past the west end of rack row B and turning east between the
rack rows.

## Pose samples during the run

| wall [s] | sim [s] | amcl x | amcl y | amcl yaw | odom x | odom y | \
remaining [m] |
|---|---|---|---|---|---|---|---|
{rows}

(wall/sim columns show the ~10x slowdown of the headless container;
`remaining` is the NavigateToPose feedback distance_remaining.)

## Result

- Action result status: **{status} ({status_name})** \
(4 = STATUS_SUCCEEDED required)
- Final /amcl_pose: {final_amcl}
- Odometry distance traveled during the goal: {node.distance:.2f} m
- Durations: goal {sim_goal_end - sim_goal_start:.1f} s sim; whole run
  {wall_total:.1f} s wall ({wall_total / 60.0:.1f} min) including Nav2
  activation wait.
''')
    log.info(f'evidence written to {args.evidence}')

    node.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if status == GoalStatus.STATUS_SUCCEEDED else 1)


if __name__ == '__main__':
    main()
