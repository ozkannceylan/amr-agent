#!/usr/bin/env python3
"""warehouse_mapping_route.py - drive the stated mapping route through
sim/worlds/warehouse.sdf.

WHAT THIS IS
  The scripted stimulus for the m5-08b mapping run. It drives one FIXED,
  STATED route so that the map is an artifact somebody else can rebuild,
  rather than a picture produced by a drive nobody can repeat.

  THE ROUTE IS A CONSTANT IN THIS FILE (see ROUTE below) AND IS NOT AN
  ARGUMENT. Nothing in this script looks at the map, at the scan, at the
  SLAM pose or at any quality measure, so it cannot steer towards whatever
  makes the map improve. It knows the waypoints and it knows where the
  vehicle is, and that is all it knows.

WHAT DRIVES THE STEERING, STATED PLAINLY
  The controller closes its loop on /forklift/odom, WHICH IS THE
  SIMULATOR'S GROUND TRUTH (agv/forklift/config.yaml says so; the topic
  name does not). That is deliberate and it is the only defensible choice
  here:

    - this script stands in for the human at the tiller of a real mapping
      run, and a human sees the aisle, not the odometry. Modelling the
      driver's eyes with the simulator's pose is modelling the human;
    - it makes the PHYSICAL route reproducible to the centimetre, which is
      the whole point of stating a route;
    - closing the loop on the estimate instead would put the vehicle 5 m
      from where the route says by the end of the circuit
      (agv/forklift/EVIDENCE_ODOMETRY.md), and a mapping run that ends up
      somewhere else is not the run that was stated.

  NO GROUND TRUTH REACHES ANY ESTIMATOR OR THE MAP. This script publishes
  exactly two topics, both of them raw joint commands into the model. It
  publishes no pose, no transform and no odometry; slam_toolbox and the EKF
  never see it, and neither has any input that depends on it. The
  separation the two-phase odometry plan exists to protect is intact: the
  DRIVER has truth, the ESTIMATOR does not.

WHAT THIS BYPASSES, SO IT IS NOT MISREAD AS SOMETHING IT IS NOT
  The PLC. Under ADR 0008 every teleoperated command reaches the simulation
  through HMI -> PLC standard program -> bridge, and nothing here does. So
  THIS RUN IS NOT EVIDENCE ABOUT THE M4 COMMAND PATH and must never be
  offered as such - it is the same standing as
  sim/scenarios/forklift_stimulus.py's `plant` subcommand. It is evidence
  about what a lidar carried around this world builds, which is the M5
  question.

  It also bypasses agv/forklift/scripts/forklift_io.py, publishing the raw
  gz joint commands directly. The two unit conversions that node would have
  done are done here from the SAME named constants in
  agv/forklift/config.yaml - nothing is hardcoded and nothing is
  re-derived.

NO CONTROL LOGIC BEYOND PATH FOLLOWING. No interlock, no latch, no stop
decision. Nothing here is a safety device: the protective stop and safe
torque off are onboard and hardwired and are reachable from no message this
file publishes (invariant 1).

NO --once PUBLISHES. Every command is a repeated publish at a stated rate
(docs/LESSONS.md, 2026-07-28).

USAGE (after sourcing /opt/ros/jazzy/setup.bash, with a warehouse bringup
already running and BOTH transports isolated):

  export GZ_PARTITION=<run> ROS_DOMAIN_ID=<n>
  /usr/bin/python3 sim/scenarios/warehouse_mapping_route.py
  /usr/bin/python3 sim/scenarios/warehouse_mapping_route.py --print-route
  /usr/bin/python3 sim/scenarios/warehouse_mapping_route.py --legs 1-3
"""

import argparse
import math
import os
import sys
import time

import yaml

# --------------------------------------------------------------------------- #
# THE ROUTE. Stated here, in advance, and not computed from anything.
# --------------------------------------------------------------------------- #

#: Waypoints are positions of the vehicle's REAR AXLE MIDPOINT in the world
#: frame, metres. The rear axle is the only point of a tricycle whose
#: velocity is purely longitudinal, so it is the point a bicycle-model path
#: follower tracks (agv/forklift/config.yaml, `rear_axle_offset_m`).
#:
#: WHERE THE OTHER TWO POINTS OF INTEREST RIDE, because the tables in
#: sim/worlds/WAREHOUSE_LANDMARKS.md are indexed by SENSOR pose:
#:
#:   base_link (the model origin)   0.50 m ahead of the tracked point
#:   navigation lidar               1.05 m ahead of it and 0.40 m to its
#:                                  RIGHT
#:
#: So on a straight leg driven along y = -5.50, base_link is at y = -5.50
#: and the lidar sweeps y = -5.90. That is the same 0.40 m offset the
#: spawn pose in sim/launch/warehouse_bringup.launch.py already has, and
#: the same one WAREHOUSE_LANDMARKS.md section 6 used for its live
#: validation (vehicle at (-6.00, -5.50), sensor at (-5.45, -5.90)).
#:
#: THE CIRCUIT IS CLOSED ON PURPOSE. It ends where it began, because loop
#: closure is one of the things this run is testing and a route that never
#: returns anywhere gives it nothing to close.
#:
#: EACH OF THE THREE DEGENERATE STRETCHES OF WAREHOUSE_LANDMARKS.md
#: SECTION 5 IS DRIVEN, and East B is driven twice, so that a second pass
#: through a stretch can be compared against the first.
#:
#: WHY THE END-AISLE LEGS RUN AT x = +-11.90 AND NOT AT +-13.00, WHICH IS
#: THE LINE WAREHOUSE_LANDMARKS.md SAMPLES. Because +-13.00 is not
#: drivable, and the landmark tables are SENSOR sample poses rather than a
#: claim that a vehicle fits there.
#:
#: sim/worlds/warehouse.sdf stands four building columns at x = +-13.400,
#: y = +3.850 and y = -2.550, each 0.25 m square, so a 1.04 m wide vehicle
#: centred on x = 13.00 spans x in [12.48, 13.52] and fouls the column at
#: x in [13.275, 13.525]. THIS WAS NOT DEDUCED FROM THE FILE - it was found
#: by driving it: the FIRST rehearsal of this route stalled at
#: (13.245, -3.558) heading 94.1 deg, which is the vehicle's front left
#: corner in the column at (13.400, -2.550).
#:
#: The SECOND rehearsal, at x = +-12.20, completed the whole circuit, and
#: its minimum footprint-corner clearance over the whole route was
#: 0.196 m - to the same column, at the W2 corner, where pure pursuit
#: overshoots ~0.30 m to the OUTSIDE of the turn. A 0.196 m margin is not a
#: margin a repeatable procedure should stand on, so the four end-aisle
#: waypoints were moved 0.30 m inboard to x = +-11.90 BEFORE the recorded
#: run. That leaves 0.38 m to the rack ends at x = +-11.00 on the straight,
#: and about 0.50 m to the column through the overshoot. The measured
#: figure for the run that actually built the committed map is in
#: sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md.
ROUTE = [
    # (x, y, label)
    (-6.50, -5.50, 'W1  start, dock aisle west half, facing +x'),
    (11.90, -5.50, 'W2  dock aisle W->E   [crosses EAST DOCK, x +1.5..+7.0]'),
    (11.90, 0.65, 'W3  east end aisle S->N'),
    (-11.90, 0.65, 'W4  aisle B E->W      [crosses EAST B, x +3.0..+7.0]'),
    (-11.90, 7.00, 'W5  west end aisle S->N'),
    (11.90, 7.00, 'W6  aisle A W->E      [crosses EAST A, x +2.0..+7.0]'),
    (11.90, 0.65, 'W7  east end aisle N->S  (revisit)'),
    (0.00, 0.65, 'W8  aisle B E->W        (EAST B, second pass)'),
    (0.00, -5.50, 'W9  central cross aisle N->S'),
    (-6.50, -5.50, 'W10 dock aisle E->W, back to W1  (circuit closed)'),
]

#: Cruise speed of the tracked point, m/s. Chosen once, before the run, as a
#: brisk warehouse manoeuvring speed that is still well under the vehicle's
#: 1.50 m/s limit; it is not a tuning knob and was not revisited.
CRUISE_MPS = 0.80

#: Speed used while the steer angle is beyond CORNER_STEER_RAD. A tricycle
#: at 0.80 m/s and a 0.85 m turning radius is a physics problem, not a
#: manoeuvre.
CORNER_MPS = 0.35
CORNER_STEER_RAD = 0.25

#: Pure-pursuit lookahead, m. Below the aisle half width (1.90 m) so a
#: corner cut cannot reach a rack face, and above the wheelbase (1.05 m) so
#: the controller does not oscillate.
LOOKAHEAD_M = 1.40

#: A waypoint counts as reached when the tracked point is within this of it
#: AND the lookahead has moved onto the following segment.
WAYPOINT_TOLERANCE_M = 0.60

#: Command publication rate, Hz. Above the 20 Hz the M4 stimuli use, because
#: this one is steering rather than holding a control.
COMMAND_HZ = 20.0

#: Hard stop. A route that has not finished in this much SIMULATION time has
#: gone wrong, and a driver that runs forever is worse than one that gives
#: up. 111 m at CORNER_MPS would take 318 s; this is triple that.
TIMEOUT_SIM_S = 1000.0

#: STALL DETECTION, and it exists because the first rehearsal of this route
#: spent 400 s driving a stationary vehicle into a building column with no
#: complaint from anything. A tracked point that has moved less than
#: STALL_DISTANCE_M in STALL_WINDOW_S of simulation time while a non-zero
#: speed is being commanded is stuck, and a stuck run is aborted where it
#: stuck, with the pose printed, rather than left to time out.
STALL_WINDOW_S = 8.0
STALL_DISTANCE_M = 0.30

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, '..', '..'))
_DEFAULT_CONFIG = os.path.join(_REPO_ROOT, 'agv', 'forklift', 'config.yaml')


def route_length(route):
    """Total path length of the stated route, m."""
    total = 0.0
    for (ax, ay, _), (bx, by, _) in zip(route, route[1:]):
        total += math.hypot(bx - ax, by - ay)
    return total


def print_route(route):
    print('Stated mapping route - rear axle midpoint, world frame, metres')
    print('  the lidar rides 1.05 m ahead of this point and 0.40 m right of it')
    print('')
    running = 0.0
    previous = None
    for x, y, label in route:
        if previous is not None:
            running += math.hypot(x - previous[0], y - previous[1])
        print('  ({:+7.2f}, {:+6.2f})   {:7.2f} m   {}'.format(
            x, y, running, label))
        previous = (x, y)
    print('')
    print('  total {:.2f} m, {} legs, 8 x 90 deg turns = 720 deg of turning'.format(
        running, len(route) - 1))


# --------------------------------------------------------------------------- #
# The controller. Bicycle-model pure pursuit on the rear axle.
# --------------------------------------------------------------------------- #

def _make_node_class(Node, Odometry, Float64, QoSProfile, Parameter):
    """Build the node class once ROS is importable, so --print-route works
    without a ROS environment."""

    class MappingRoute(Node):

        def __init__(self, cfg, route, args):
            # use_sim_time IS SET HERE AND IS NOT OPTIONAL. Every message
            # in this stack is stamped with the simulation clock. A node on
            # the system clock differences two clocks; here that would make
            # TIMEOUT_SIM_S and the leg log wall-clock quantities against a
            # simulation that may not be running at real time, and would
            # put a wall-clock stamp in an evidence file whose every other
            # stamp is simulation time.
            super().__init__(
                'warehouse_mapping_route',
                parameter_overrides=[
                    Parameter('use_sim_time', Parameter.Type.BOOL, True)])

            model = cfg['model']
            topics = cfg['topics']
            limits = cfg['limits']

            # Every constant below is READ from agv/forklift/config.yaml.
            # None is written here, so this file cannot disagree with the
            # vehicle about its own geometry.
            self.wheel_radius_m = float(model['wheel_radius_m'])
            self.wheelbase_m = float(model['wheelbase_m'])
            self.rear_axle_offset_m = float(model['rear_axle_offset_m'])
            self.steer_limit_rad = float(model['steer_limit_rad'])
            self.speed_limit_mps = float(limits['traction_speed_max_mps'])

            self.route = route
            self.args = args
            self.segment = 0
            self.pose = None
            self.started_sim_s = None
            self.last_report_s = 0.0
            self.finished = False
            self.stalled = False
            self.leg_log = []
            self.stall_mark = None

            qos = QoSProfile(depth=int(cfg['qos']['depth']))

            self.pub_traction = self.create_publisher(
                Float64, topics['gz_traction_cmd'], qos)
            self.pub_steer = self.create_publisher(
                Float64, topics['gz_steer_cmd'], qos)

            # GROUND TRUTH, and the only thing this node subscribes to. See
            # the module docstring: the driver has truth, the estimator does
            # not, and nothing this node publishes carries a pose.
            self.sub_truth = self.create_subscription(
                Odometry, topics['odom'], self.cb_truth, qos)

            self.timer = self.create_timer(1.0 / COMMAND_HZ, self.cb_drive)

            self.get_logger().info(
                'route: {} waypoints, {:.2f} m, cruise {:.2f} m/s, '
                'lookahead {:.2f} m'.format(
                    len(route), route_length(route), CRUISE_MPS, LOOKAHEAD_M))

        # ---- input ----

        def cb_truth(self, msg):
            p = msg.pose.pose.position
            q = msg.pose.pose.orientation
            yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                             1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            # base_link -> rear axle midpoint. rear_axle_offset_m is
            # negative (the axle is BEHIND base_link), so this subtracts.
            self.pose = (
                p.x + self.rear_axle_offset_m * math.cos(yaw),
                p.y + self.rear_axle_offset_m * math.sin(yaw),
                yaw,
            )

        def sim_now(self):
            return self.get_clock().now().nanoseconds * 1e-9

        # ---- output ----

        def command(self, speed_mps, steer_rad):
            speed = max(-self.speed_limit_mps,
                        min(self.speed_limit_mps, speed_mps))
            steer = max(-self.steer_limit_rad,
                        min(self.steer_limit_rad, steer_rad))
            traction = Float64()
            # The same conversion agv/forklift/scripts/forklift_io.py makes:
            # ground speed [m/s] -> drive wheel spin rate [rad/s].
            traction.data = speed / self.wheel_radius_m
            self.pub_traction.publish(traction)
            out = Float64()
            out.data = steer
            self.pub_steer.publish(out)

        # ---- the loop ----

        def cb_drive(self):
            if self.finished:
                return
            if self.pose is None:
                self.get_logger().info(
                    'waiting for the vehicle pose', throttle_duration_sec=5.0)
                return

            now = self.sim_now()
            if self.started_sim_s is None:
                self.started_sim_s = now
                self.leg_log.append((now, 0, self.pose[0], self.pose[1]))
                self.get_logger().info('leg 1: {}'.format(
                    self.route[1][2]))
            elapsed = now - self.started_sim_s

            if elapsed > TIMEOUT_SIM_S:
                self.get_logger().error(
                    'route timed out at {:.1f} s of simulation time on leg '
                    '{}'.format(elapsed, self.segment + 1))
                self.stop()
                return

            x, y, yaw = self.pose
            target = self.lookahead_point()
            if target is None:
                self.get_logger().info(
                    'route complete: {:.1f} s of simulation time, '
                    '{} legs'.format(elapsed, len(self.route) - 1))
                self.stop()
                return

            # Pure pursuit, bicycle model, tracked at the rear axle:
            #     delta = atan( 2 L sin(alpha) / Ld )
            # alpha is the bearing of the lookahead point in the body frame.
            dx, dy = target[0] - x, target[1] - y
            alpha = math.atan2(dy, dx) - yaw
            alpha = math.atan2(math.sin(alpha), math.cos(alpha))
            distance = max(1e-3, math.hypot(dx, dy))
            steer = math.atan2(
                2.0 * self.wheelbase_m * math.sin(alpha), distance)

            speed = CORNER_MPS if abs(steer) > CORNER_STEER_RAD else CRUISE_MPS
            self.command(speed, steer)

            # Stall detection. See STALL_WINDOW_S.
            if self.stall_mark is None:
                self.stall_mark = (now, x, y)
            elif now - self.stall_mark[0] >= STALL_WINDOW_S:
                moved = math.hypot(x - self.stall_mark[1],
                                   y - self.stall_mark[2])
                if moved < STALL_DISTANCE_M:
                    self.stalled = True
                    self.get_logger().error(
                        'STALLED on leg {}: moved {:.3f} m in {:.1f} s of '
                        'simulation time while commanding {:.2f} m/s. Pose '
                        '({:+.3f}, {:+.3f}) yaw {:+.1f} deg. The route is '
                        'obstructed here; do not re-run it until the '
                        'waypoints are corrected.'.format(
                            self.segment + 1, moved, now - self.stall_mark[0],
                            speed, x, y, math.degrees(yaw)))
                    self.stop()
                    return
                self.stall_mark = (now, x, y)

            if elapsed - self.last_report_s >= 5.0:
                self.last_report_s = elapsed
                self.get_logger().info(
                    'leg {}  pos ({:+7.2f},{:+6.2f})  yaw {:+6.1f} deg  '
                    'steer {:+5.2f}  v {:.2f}  t {:6.1f} s'.format(
                        self.segment + 1, x, y, math.degrees(yaw),
                        steer, speed, elapsed))

        def lookahead_point(self):
            """The point LOOKAHEAD_M ahead along the remaining polyline.

            Advances the active segment when the tracked point has passed
            the end waypoint of the current one. Returns None when the route
            is done."""
            x, y, _ = self.pose
            while self.segment < len(self.route) - 1:
                ax, ay, _ = self.route[self.segment]
                bx, by, _ = self.route[self.segment + 1]
                seg_x, seg_y = bx - ax, by - ay
                seg_len = math.hypot(seg_x, seg_y)
                if seg_len < 1e-6:
                    self.segment += 1
                    continue
                # Projection of the vehicle onto the segment, in metres from
                # its start.
                t = ((x - ax) * seg_x + (y - ay) * seg_y) / seg_len
                remaining = seg_len - t
                if remaining <= 0.0 or (
                        remaining < WAYPOINT_TOLERANCE_M
                        and math.hypot(bx - x, by - y) < WAYPOINT_TOLERANCE_M):
                    self.segment += 1
                    self.leg_log.append(
                        (self.sim_now(), self.segment, x, y))
                    if self.segment < len(self.route) - 1:
                        self.get_logger().info('leg {}: {}'.format(
                            self.segment + 1, self.route[self.segment + 1][2]))
                    continue
                ahead = min(seg_len, max(0.0, t) + LOOKAHEAD_M)
                if ahead >= seg_len - 1e-6 and self.segment < len(self.route) - 2:
                    # Carry the remainder of the lookahead onto the next
                    # segment, so the turn begins before the corner rather
                    # than at it.
                    over = LOOKAHEAD_M - remaining
                    cx, cy, _ = self.route[self.segment + 2]
                    nx, ny = cx - bx, cy - by
                    n_len = max(1e-6, math.hypot(nx, ny))
                    step = min(over, n_len)
                    return (bx + nx / n_len * step, by + ny / n_len * step)
                return (ax + seg_x / seg_len * ahead,
                        ay + seg_y / seg_len * ahead)
            return None

        def stop(self):
            """Zero both commands, repeatedly, and mark the run finished.

            Repeatedly because a single publish races the subscriber
            (LESSONS 2026-07-28) and because the safe value of both of these
            is zero: forklift_io.py publishes traction and steer on receipt
            only, so a stale non-zero value would simply stand."""
            self.finished = True
            for _ in range(int(COMMAND_HZ)):
                self.command(0.0, 0.0)
                time.sleep(1.0 / COMMAND_HZ)
            self.get_logger().info('traction and steer commanded to zero')

    return MappingRoute


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', default=_DEFAULT_CONFIG,
                        help='agv/forklift/config.yaml (default: %(default)s)')
    parser.add_argument('--print-route', action='store_true',
                        help='print the stated route and exit; needs no ROS')
    parser.add_argument('--legs', default=None,
                        help='drive a sub-range of the legs, e.g. 1-3. For '
                             'rehearsal only: the committed run drives all '
                             'of them')
    parser.add_argument('--leg-log', default=None,
                        help='write one row per leg boundary here')
    args, ros_args = parser.parse_known_args(argv)

    route = ROUTE
    if args.legs:
        first, _, last = args.legs.partition('-')
        lo = int(first) - 1
        hi = int(last) if last else int(first)
        route = ROUTE[lo:hi + 1]

    if args.print_route:
        print_route(route)
        return 0

    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from std_msgs.msg import Float64

    with open(args.config, 'r', encoding='utf-8') as handle:
        cfg = yaml.safe_load(handle)

    rclpy.init(args=ros_args)
    node_class = _make_node_class(
        Node, Odometry, Float64, QoSProfile, rclpy.parameter.Parameter)
    node = node_class(cfg, route, args)
    try:
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        node.stop()
    finally:
        if args.leg_log:
            with open(args.leg_log, 'w', encoding='utf-8') as handle:
                handle.write('sim_s,leg_index,x,y\n')
                for row in node.leg_log:
                    handle.write('{:.3f},{},{:.4f},{:.4f}\n'.format(*row))
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
