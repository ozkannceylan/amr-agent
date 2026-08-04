#!/usr/bin/env python3
"""localization_run.py - drive the named localization tests and score them.

A MEASUREMENT HARNESS, NOT PART OF THE VEHICLE STACK. Nothing here runs on
a vehicle. It exists to produce the four figures
agv/forklift/EVIDENCE_LOCALIZATION.md reports, and every one of them is
scored ABSOLUTELY through the committed registration.

FOUR SUBCOMMANDS

  map-pose    carry a WORLD pose into the MAP frame through the committed
              T(world -> map). Used once per run to state AMCL's initial
              pose prior, and by nothing else.

  profile     print a named drive profile and exit. Needs no ROS.

  drive       drive a named profile open loop.

  analyse     read a mapping_evidence.py CSV and report the absolute error,
              segmented into the motion phases the dwell measurement needs.
              Needs no ROS.

THE DRIVER SUBSCRIBES TO NOTHING. Not to ground truth, not to the EKF, not
to /amcl_pose, not to the scan. Every profile below is a list of

    (label, seconds of SIMULATION time, ground speed m/s, steer rad)

played out on a clock and nothing else. That is a stronger statement than
"no ground truth reaches the estimator": there is no feedback path of ANY
kind from the run into the stimulus, so the drive cannot bend towards a
pose that scores better. The committed mapping route
(sim/scenarios/warehouse_mapping_route.py) closes its loop on ground truth
because it must reproduce a 111 m circuit to the centimetre; these profiles
are short and straight and need no such thing.

The price of open loop is that the vehicle ends up approximately, not
exactly, where the profile says. Every figure in the evidence is therefore
reported against the ground-truth pose the vehicle ACTUALLY reached, which
is recorded in the CSV, and never against the intended one.

WHAT `drive` PUBLISHES: two topics, both raw joint commands into the model,
converted from engineering units with the SAME constants
agv/forklift/scripts/forklift_io.py uses, read from agv/forklift/config.yaml
so nothing is written twice. It publishes no pose, no transform and no
odometry. NO --once PUBLISHES: every command is a repeated publish at a
stated rate (docs/LESSONS.md, 2026-07-28).

NO CONTROL LOGIC. No interlock, no latch, no stop decision, no threshold.
Nothing here is a safety device: the protective stop and safe torque off are
onboard and hardwired and are reachable from no message this file publishes
(invariant 1).

WHY A WORLD -> MAP CONVERSION LIVES IN A HARNESS AND NOT IN THE LAUNCH. A
real forklift has no world frame and no registration; it is told where it
is in the frame of the map it was given. The registration exists here only
because the SCORER's reference is the simulator's own pose, which is in the
world frame. Keeping the conversion in the harness keeps it out of the
vehicle's bringup, and `map-pose` reaches it through
sim/maps/warehouse/register_map.py - the module that DERIVED it - rather
than parsing a copy (invariant 10).

USAGE (after sourcing /opt/ros/jazzy/setup.bash; `drive` needs rclpy, so
run it with /usr/bin/python3. Isolate BOTH transports.)

  python3  agv/forklift/scripts/localization_run.py profile --profile dwell
  python3  agv/forklift/scripts/localization_run.py map-pose \\
      --x -6.00 --y -5.50 --yaw 0.0
  /usr/bin/python3 agv/forklift/scripts/localization_run.py drive \\
      --profile dwell --marks /tmp/dwell.marks
  python3  agv/forklift/scripts/localization_run.py analyse \\
      --csv /tmp/dwell.csv --marks /tmp/dwell.marks
"""

import argparse
import math
import os
import sys
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_REPO_ROOT = os.path.normpath(os.path.join(_FORKLIFT_DIR, '..', '..'))
_DEFAULT_CONFIG = os.path.join(_FORKLIFT_DIR, 'config.yaml')

#: Command publication rate, Hz. The same 20 Hz the M4 stimuli use; these
#: profiles hold a control rather than steer, so nothing here needs more.
COMMAND_HZ = 20.0


# --------------------------------------------------------------------------- #
# The profiles. Stated here, in advance, and computed from nothing.
# --------------------------------------------------------------------------- #
#
# Each leg is (label, simulation seconds, ground speed m/s, steer rad).
#
# GEOMETRY THE DISTANCES BELOW ARE TAKEN FROM, quoted from
# sim/scenarios/warehouse_mapping_route.py and agv/forklift/model.sdf so
# that a reader can check them without opening either:
#
#   the profile's speeds move the REAR AXLE MIDPOINT, which is 0.50 m
#   behind base_link;
#   the NAVIGATION LIDAR rides 1.05 m ahead of the rear axle and 0.40 m to
#   its RIGHT, at z = 1.80 m;
#   sim/worlds/WAREHOUSE_LANDMARKS.md section 5 indexes the degenerate
#   stretches by SENSOR position, so a sensor target x maps to a rear axle
#   target of x - 1.05 when the vehicle faces +x.
#
# East A is "Aisle A, y = +7.00, x in [+2.0, +7.0], worst pose (+7.00,
# +7.00), aniso 0.034" - the worst of the three named stretches.

_PROFILES = {

    # (c) THE DWELL. Approach East A from the well-conditioned west half,
    # stop deep inside it, stand there for over two minutes, then drive on.
    #
    # Spawn (rear axle): (-5.00, +7.00), facing +x.
    # 13.2 s at 0.80 m/s = 10.56 m, so the axle stops near x = +5.56 and the
    # SENSOR near x = +6.61 - inside [+2.0, +7.0] and 0.4 m short of the
    # worst pose, deliberately short of the boundary so a stop that
    # overshoots by a few centimetres is still inside the stretch.
    #
    # 130 s of dwell against a 120 s criterion: the margin absorbs the
    # coast-down at the start and the sampler's own start-up, so the
    # measured stationary interval is over 120 s rather than about it.
    'dwell': [
        ('settle',            4.0,  0.00, 0.0),
        ('approach East A',  13.2,  0.80, 0.0),
        ('DWELL',           130.0,  0.00, 0.0),
        ('resume east',       5.0,  0.80, 0.0),
        ('stop',              8.0,  0.00, 0.0),
    ],

    # (d) THE REVERSE. The same stretch, FORK FIRST.
    #
    # In model.sdf +x is "forward, the driving direction, the steer and
    # drive end"; the mast and the fork tines are at -x. So fork first IS
    # backwards, and it is a traversal this world has never been driven:
    # the committed route crosses East A west to east, facing and moving
    # +x.
    #
    # THE ASYMMETRY IS REAL AND IT IS NOT THE SCAN'S FIELD OF VIEW. The
    # navigation lidar returns 360 deg. What is asymmetric is where it
    # SITS: at (+0.55, -0.40) in base_link, which is 0.55 m towards the
    # drive end and 0.40 m off the mast centreline, with the mast rails
    # standing to z = 2.05 - above the sensor's own z = 1.80. So the mast
    # occludes a bearing sector towards -x, and driving fork first points
    # that occluded sector at the space the vehicle is entering.
    #
    # Spawn (rear axle): (+9.00, +7.00), facing +x - the SAME heading the
    # committed route holds through this aisle, so the only variable that
    # changes against the route's pass is the direction of travel.
    # 14.2 s at -0.60 m/s = -8.52 m, carrying the sensor from x = +10.05
    # down to x = +1.53: the whole of [+2.0, +7.0] and out the far side.
    # 0.60 m/s rather than the route's 0.80: a reversing forklift is driven
    # slower, and the slower pass gives the filter MORE scans over the
    # stretch, not fewer, so a worse result cannot be blamed on sampling.
    'reverse': [
        ('settle',                    4.0,  0.00, 0.0),
        ('reverse through East A',   14.2, -0.60, 0.0),
        ('stop',                      8.0,  0.00, 0.0),
    ],

    # (d) THE CONTROL FOR THE REVERSE. The same stretch, the same length,
    # the same speed, the same exact prior, the same body heading - driven
    # FORWARDS. It exists because "the reverse traversal cost nothing" is
    # only a statement if there is a forward traversal of the same shape to
    # compare it against, and the committed route's East A pass is not one:
    # that pass runs at 0.80 m/s and arrives after 75 m of driving, so a
    # difference between it and the reverse pass could be either the
    # direction or the history.
    #
    # Spawn (rear axle): (+0.50, +7.00), facing +x. 14.2 s at +0.60 m/s
    # carries the sensor from x = +1.55 up to +10.07 - the exact reverse of
    # the profile above, sample for sample.
    'forward': [
        ('settle',                    4.0,  0.00, 0.0),
        ('forward through East A',   14.2,  0.60, 0.0),
        ('stop',                      8.0,  0.00, 0.0),
    ],

    # (b) THE CONVERGENCE DRIVE. Straight, then a symmetric weave, then
    # straight, along the dock aisle from the well-conditioned west half
    # into the East dock stretch.
    #
    # Spawn (rear axle): (-9.50, -5.50), facing +x.
    # 22 s of motion at 0.80 m/s = 17.6 m, ending near axle x = +8.1.
    #
    # THE WEAVE IS THERE FOR HEADING OBSERVABILITY, not for distance. A
    # deliberately wrong prior is wrong in heading as well as position, and
    # a filter driven in a dead straight line is given very little to
    # separate a heading error from a lateral one. The three weave legs are
    # +3 s / -6 s / +3 s at 0.12 rad, which returns both the heading and
    # the lateral offset to zero by construction: at 0.80 m/s and a 1.05 m
    # wheelbase that is +-15.7 deg of yaw and a peak excursion of about
    # 0.66 m, against an aisle half width of 1.90 m.
    'converge': [
        ('settle',      4.0,  0.00,  0.00),
        ('east 1',      5.0,  0.80,  0.00),
        ('weave left',  3.0,  0.80,  0.12),
        ('weave right', 6.0,  0.80, -0.12),
        ('weave left',  3.0,  0.80,  0.12),
        ('east 2',      5.0,  0.80,  0.00),
        ('stop',        8.0,  0.00,  0.00),
    ],
}

#: Where each profile expects the vehicle to be spawned: the REAR AXLE
#: midpoint in the world frame, and the heading. These are passed to
#: sim/launch/warehouse_bringup.launch.py, which spawns base_link, so the
#: spawn argument is this point plus 0.50 m along the heading. Stated here
#: because a profile and its start pose are one statement, and splitting
#: them across two files is how they come to disagree.
_STARTS = {
    'dwell':    (-5.00, 7.00, 0.0),
    'reverse':  (9.00, 7.00, 0.0),
    'forward':  (0.50, 7.00, 0.0),
    'converge': (-9.50, -5.50, 0.0),
}


def profile_summary(name):
    legs = _PROFILES[name]
    start = _STARTS[name]
    lines = []
    lines.append('profile {!r}'.format(name))
    lines.append('  rear axle start (world): ({:+.2f}, {:+.2f}) yaw {:+.2f} rad'
                 .format(*start))
    lines.append('  base_link spawn  (world): ({:+.2f}, {:+.2f}) yaw {:+.2f} '
                 'rad'.format(start[0] + 0.50 * math.cos(start[2]),
                              start[1] + 0.50 * math.sin(start[2]),
                              start[2]))
    lines.append('')
    lines.append('  {:<24} {:>8} {:>10} {:>10} {:>10}'.format(
        'leg', 'sim s', 'speed m/s', 'steer rad', 'travel m'))
    total_s, travel = 0.0, 0.0
    for label, seconds, speed, steer in legs:
        total_s += seconds
        travel += seconds * speed
        lines.append('  {:<24} {:>8.1f} {:>10.2f} {:>10.2f} {:>10.2f}'.format(
            label, seconds, speed, steer, seconds * speed))
    lines.append('  {:<24} {:>8.1f} {:>10} {:>10} {:>10.2f}'.format(
        'TOTAL', total_s, '', '', travel))
    return '\n'.join(lines)


# --------------------------------------------------------------------------- #
# map-pose: the committed world -> map transform, through the module that
# derived it
# --------------------------------------------------------------------------- #

def load_registration(path=None):
    """The committed T(world -> map), via sim/maps/warehouse/register_map.py.

    INVARIANT 10. This harness does not parse the registration file and
    carries no copy of the transform. `register_map.load_registration`
    verifies the grid md5 before returning, so a run scored against a map
    that has been rebuilt since the transform was derived FAILS HERE
    instead of producing a plausible wrong number - which is the
    stop-and-report the brief asks for."""
    module_dir = os.path.join(_REPO_ROOT, 'sim', 'maps', 'warehouse')
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    try:
        import register_map
    except ImportError:
        raise SystemExit(
            'cannot import {}/register_map.py, which owns the world->map '
            'transform. Absolute scoring cannot run without it.'
            .format(module_dir))
    if path is None:
        path = register_map.DEFAULT_REGISTRATION
    return register_map.load_registration(path)


def world_to_map(record, x, y, yaw):
    """p_map = R(theta) p_world + t, the registration's own direction."""
    theta = record['theta_rad']
    c, s = math.cos(theta), math.sin(theta)
    return (c * x - s * y + record['t_x_m'],
            s * x + c * y + record['t_y_m'],
            _wrap(yaw + theta))


def map_to_world(record, x, y, yaw):
    """p_world = R(-theta) (p_map - t)."""
    theta = record['theta_rad']
    c, s = math.cos(-theta), math.sin(-theta)
    mx, my = x - record['t_x_m'], y - record['t_y_m']
    return (c * mx - s * my, s * mx + c * my, _wrap(yaw - theta))


def cmd_map_pose(args):
    record = load_registration(args.registration)
    mx, my, myaw = world_to_map(record, args.x, args.y, args.yaw)
    print('committed registration  theta {:+.9f} rad ({:+.6f} deg)  '
          't ({:+.6f}, {:+.6f}) m'.format(
              record['theta_rad'], math.degrees(record['theta_rad']),
              record['t_x_m'], record['t_y_m']))
    print('FLOOR  residual rms {:.4f} m, MAX {:.4f} m'.format(
        record['residual_rms_m'], record['residual_max_m']))
    print('world  ({:+.4f}, {:+.4f}) yaw {:+.6f} rad ({:+.3f} deg)'.format(
        args.x, args.y, args.yaw, math.degrees(args.yaw)))
    print('map    ({:+.4f}, {:+.4f}) yaw {:+.6f} rad ({:+.3f} deg)'.format(
        mx, my, myaw, math.degrees(myaw)))
    print('')
    print('initial_pose_x:={:.6f} initial_pose_y:={:.6f} '
          'initial_pose_yaw:={:.6f}'.format(mx, my, myaw))
    return 0


# --------------------------------------------------------------------------- #
# drive
# --------------------------------------------------------------------------- #

def cmd_drive(args):
    import yaml

    import rclpy
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.qos import QoSProfile
    from std_msgs.msg import Float64

    with open(args.config, 'r', encoding='utf-8') as handle:
        cfg = yaml.safe_load(handle)

    wheel_radius_m = float(cfg['model']['wheel_radius_m'])
    steer_limit_rad = float(cfg['model']['steer_limit_rad'])
    speed_limit_mps = float(cfg['limits']['traction_speed_max_mps'])
    topics = cfg['topics']

    legs = _PROFILES[args.profile]

    rclpy.init(args=None)
    # use_sim_time IS NOT OPTIONAL. The leg durations below are SIMULATION
    # seconds. On the system clock a profile would play out against wall
    # time while the plant ran at whatever real time factor this host
    # reaches, and the distances in the profile table would be fiction.
    node = Node('localization_run',
                parameter_overrides=[
                    Parameter('use_sim_time', Parameter.Type.BOOL, True)])
    qos = QoSProfile(depth=int(cfg['qos']['depth']))
    pub_traction = node.create_publisher(Float64, topics['gz_traction_cmd'], qos)
    pub_steer = node.create_publisher(Float64, topics['gz_steer_cmd'], qos)

    def sim_now():
        return node.get_clock().now().nanoseconds * 1e-9

    def command(speed_mps, steer_rad):
        speed = max(-speed_limit_mps, min(speed_limit_mps, speed_mps))
        steer = max(-steer_limit_rad, min(steer_limit_rad, steer_rad))
        traction = Float64()
        # The same conversion forklift_io.py makes: ground speed [m/s] ->
        # drive wheel spin rate [rad/s].
        traction.data = speed / wheel_radius_m
        pub_traction.publish(traction)
        out = Float64()
        out.data = steer
        pub_steer.publish(out)

    # Discovery. A publisher that has not met its subscriber drops its
    # first messages, and the first message of this profile is a zero that
    # nothing would notice going missing - but the second leg's is not.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        if (pub_traction.get_subscription_count() > 0
                and pub_steer.get_subscription_count() > 0):
            break
    node.get_logger().info(
        'subscribers: traction {}, steer {}'.format(
            pub_traction.get_subscription_count(),
            pub_steer.get_subscription_count()))

    # Wait for the simulation clock to be running before timing anything
    # against it.
    deadline = time.monotonic() + 20.0
    while sim_now() <= 0.0 and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    if sim_now() <= 0.0:
        node.destroy_node()
        rclpy.shutdown()
        raise SystemExit('no simulation clock on /clock after 20 s; is the '
                         'bringup running and is use_sim_time set?')

    marks = []
    started = sim_now()
    node.get_logger().info('profile {!r}: {} legs, t0 = {:.3f} sim s'.format(
        args.profile, len(legs), started))
    period = 1.0 / COMMAND_HZ
    try:
        for label, seconds, speed, steer in legs:
            leg_start = sim_now()
            marks.append((leg_start, label, speed, steer))
            node.get_logger().info(
                'leg {!r}: {:.1f} s at {:+.2f} m/s, steer {:+.2f} rad '
                '(t {:+.1f} s)'.format(label, seconds, speed, steer,
                                       leg_start - started))
            while rclpy.ok() and sim_now() - leg_start < seconds:
                command(speed, steer)
                rclpy.spin_once(node, timeout_sec=period)
        # Zero both commands, repeatedly. forklift_io.py and the gz systems
        # act on receipt only, so a stale non-zero value would simply stand.
        for _ in range(int(COMMAND_HZ)):
            command(0.0, 0.0)
            rclpy.spin_once(node, timeout_sec=period)
        marks.append((sim_now(), 'END', 0.0, 0.0))
        node.get_logger().info(
            'profile complete: {:.1f} s of simulation time; traction and '
            'steer commanded to zero'.format(sim_now() - started))
    except KeyboardInterrupt:
        for _ in range(int(COMMAND_HZ)):
            command(0.0, 0.0)
            rclpy.spin_once(node, timeout_sec=period)
    finally:
        if args.marks:
            with open(args.marks, 'w', encoding='utf-8') as handle:
                handle.write('sim_s,label,speed_mps,steer_rad\n')
                for sim_s, label, speed, steer in marks:
                    handle.write('{:.4f},{},{:.4f},{:.4f}\n'.format(
                        sim_s, label, speed, steer))
            print('wrote {} leg marks to {}'.format(len(marks), args.marks))
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


# --------------------------------------------------------------------------- #
# analyse
# --------------------------------------------------------------------------- #

def _wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def _read_csv(path):
    """Read a sim/scenarios/tools/mapping_evidence.py `record` CSV.

    THE CSV FORMAT IS NOT DEFINED HERE. It is that tool's, quoted by its
    header row, and this reader keys off the header rather than off column
    positions so a column added there does not silently shift a value
    here."""
    rows = []
    with open(path, 'r', encoding='utf-8') as handle:
        header = handle.readline().strip().split(',')
        for line in handle:
            parts = line.strip().split(',')
            if len(parts) != len(header):
                continue
            rows.append(dict(zip(header, (float(v) for v in parts))))
    return rows


def _place_absolute(rows, record):
    """Carry map -> base_link into the world. NO PER-RUN ANCHORING.

    Identical in form to mapping_evidence.py's `place_absolute`, and the
    evidence cross-checks the two implementations against each other on the
    same CSV rather than assuming they agree."""
    theta = record['theta_rad']
    c, s = math.cos(-theta), math.sin(-theta)
    tx, ty = record['t_x_m'], record['t_y_m']
    placed = 0
    for row in rows:
        mx, my = row['slam_x'] - tx, row['slam_y'] - ty
        row['w_x'] = c * mx - s * my
        row['w_y'] = s * mx + c * my
        row['w_yaw'] = _wrap(row['slam_yaw'] - theta)
        row['e_x'] = row['w_x'] - row['truth_x']
        row['e_y'] = row['w_y'] - row['truth_y']
        row['e_norm'] = math.hypot(row['e_x'], row['e_y'])
        row['e_yaw'] = _wrap(row['w_yaw'] - row['truth_yaw'])
        if not math.isnan(row['w_x']):
            placed += 1
    return placed


#: A sample counts as standing still when the ground-truth position has
#: moved less than this over the window below. Both are properties of the
#: REFERENCE, not of any estimate: the reference is exact simulation truth,
#: so "the vehicle is not moving" is a fact here rather than a verdict.
STILL_SPEED_MPS = 0.02
STILL_WINDOW_S = 1.0


def _moving_flags(rows):
    """True where the vehicle is moving, from ground truth alone."""
    flags = []
    for index, row in enumerate(rows):
        lo, hi = index, index
        while lo > 0 and row['sim_s'] - rows[lo]['sim_s'] < STILL_WINDOW_S / 2:
            lo -= 1
        while (hi < len(rows) - 1
               and rows[hi]['sim_s'] - row['sim_s'] < STILL_WINDOW_S / 2):
            hi += 1
        span = rows[hi]['sim_s'] - rows[lo]['sim_s']
        moved = math.hypot(rows[hi]['truth_x'] - rows[lo]['truth_x'],
                           rows[hi]['truth_y'] - rows[lo]['truth_y'])
        flags.append(span > 0 and moved / span > STILL_SPEED_MPS)
    return flags


def _stats(rows, key='e_norm'):
    values = [r[key] for r in rows if not math.isnan(r[key])]
    if not values:
        return None
    return {
        'n': len(values),
        'mean': sum(values) / len(values),
        'max': max(values),
        'min': min(values),
        'rms': math.sqrt(sum(v * v for v in values) / len(values)),
        'first': values[0],
        'last': values[-1],
    }


def _ekf_yaw(row):
    """The EKF's own heading, odom -> base_link, from the recorded pair.

    map -> base_link = (map -> odom) o (odom -> base_link), so the EKF's
    contribution is the difference of the two yaws that the CSV already
    carries. Nothing here re-derives an estimate; it separates two published
    transforms that were recorded side by side."""
    return _wrap(row['slam_yaw'] - row['mo_yaw'])


def _apportion(segment, first, last, span, what):
    """Split a heading change into what AMCL did and what it was handed.

    THIS IS THE WHOLE POINT OF THE DWELL MEASUREMENT. The pose the vehicle
    reports is map -> base_link, and exactly two publishers move it: AMCL
    moves map -> odom, and the EKF moves odom -> base_link. Reporting only
    the total leaves a reader unable to tell a localizer that drifted from a
    localizer that was handed a drifting odometry and passed it through.

    Ground truth appears here only as the fourth row, and only so that any
    REAL body rotation during the window is visible instead of being
    charged to an estimator."""
    total = math.degrees(_wrap(last['slam_yaw'] - first['slam_yaw']))
    amcl = math.degrees(_wrap(last['mo_yaw'] - first['mo_yaw']))
    ekf = math.degrees(_wrap(_ekf_yaw(last) - _ekf_yaw(first)))
    truth = math.degrees(_wrap(last['truth_yaw'] - first['truth_yaw']))
    step = math.hypot(last['mo_x'] - first['mo_x'],
                      last['mo_y'] - first['mo_y'])
    corrections = 0
    for a, b in zip(segment, segment[1:]):
        if (abs(b['mo_x'] - a['mo_x']) > 1e-9
                or abs(b['mo_y'] - a['mo_y']) > 1e-9
                or abs(_wrap(b['mo_yaw'] - a['mo_yaw'])) > 1e-9):
            corrections += 1
    print('  APPORTIONED over {} ({:.1f} s):'.format(what, span))
    print('    total heading, map -> base_link      {:+.4f} deg'.format(total))
    print('    of which AMCL, map -> odom           {:+.4f} deg  '
          '({:.4f} m, {} correction(s))'.format(amcl, step, corrections))
    print('    of which the EKF, odom -> base_link  {:+.4f} deg  '
          '<- WHAT AMCL WAS HANDED'.format(ekf))
    print('    real body rotation, ground truth     {:+.4f} deg'.format(truth))


def _read_marks(path):
    """Leg boundaries from `drive --marks`, as (label pair, t0, t1) windows.

    One window per leg: the leg's own start to the next leg's start."""
    rows = []
    with open(path, 'r', encoding='utf-8') as handle:
        handle.readline()
        for line in handle:
            parts = line.strip().split(',')
            if len(parts) < 2:
                continue
            rows.append((float(parts[0]), parts[1]))
    return [((a[1], b[1]), a[0], b[0]) for a, b in zip(rows, rows[1:])]


def _floor_line(value, floor):
    """Every figure is printed beside the floor, and a figure at or below it
    is named as being at the instrument's resolution rather than quoted as a
    smaller number. That rule is applied HERE, once, so it cannot be applied
    inconsistently by a reader."""
    if value <= floor:
        return '{:.3f} m  AT THE INSTRUMENT\'S RESOLUTION (floor {:.3f} m)' \
            .format(value, floor)
    return '{:.3f} m  (floor {:.3f} m)'.format(value, floor)


def cmd_analyse(args):
    rows = _read_csv(args.csv)
    if not rows:
        raise SystemExit('no samples in {}'.format(args.csv))
    record = load_registration(args.registration)
    floor = record['residual_max_m']
    placed = _place_absolute(rows, record)
    scored = [r for r in rows if r['slam_ok'] > 0.5 and not math.isnan(r['w_x'])]
    if not scored:
        raise SystemExit(
            'no sample in {} carries a map -> base_link transform: AMCL '
            'published nothing, which is a failure of the run and not a '
            'result'.format(args.csv))

    print('# {}'.format(args.label or os.path.basename(args.csv)))
    print('')
    print('SCORED ABSOLUTELY. Every `map` pose below was carried into the '
          'world')
    print('frame through the COMMITTED transform, derived from the map\'s '
          'walls')
    print('before this run existed. NO PER-RUN ANCHORING ANYWHERE.')
    print('')
    print('    sim/maps/warehouse/warehouse_registration.yaml')
    print('    theta = {:+.9f} rad = {:+.6f} deg,  t = ({:+.6f}, {:+.6f}) m'
          .format(record['theta_rad'], math.degrees(record['theta_rad']),
                  record['t_x_m'], record['t_y_m']))
    print('    grid md5 verified by register_map.load_registration()')
    print('')
    print('*** FLOOR: registration residual {:.4f} m rms, {:.4f} m MAX.'
          .format(record['residual_rms_m'], record['residual_max_m']))
    print('    No figure at or below {:.4f} m is a measurement of AMCL. It '
          'is'.format(floor))
    print('    reported as "at the instrument\'s resolution", never as a '
          'smaller number.')
    print('')
    print('THE REFERENCE IS EXACT. `truth_*` is the simulator\'s own pose of '
          'the')
    print('model (gz OdometryPublisher), not an estimate of it, so it '
          'carries no')
    print('error of its own and every figure below is attributable to the')
    print('localization chain: navigation lidar -> AMCL, EKF -> AMCL, '
          'against the')
    print('frozen committed grid. It reaches NO estimator.')
    print('')
    print('samples                  {}'.format(len(rows)))
    print('samples with a map pose  {}'.format(placed))
    print('samples scored           {}'.format(len(scored)))
    print('simulation time          {:.1f} s'.format(
        rows[-1]['sim_s'] - rows[0]['sim_s']))

    travelled = 0.0
    for a, b in zip(rows, rows[1:]):
        travelled += math.hypot(b['truth_x'] - a['truth_x'],
                                b['truth_y'] - a['truth_y'])
    print('ground-truth path        {:.2f} m'.format(travelled))
    print('ground truth start       ({:+.3f}, {:+.3f}) yaw {:+.2f} deg'.format(
        rows[0]['truth_x'], rows[0]['truth_y'],
        math.degrees(rows[0]['truth_yaw'])))
    print('ground truth end         ({:+.3f}, {:+.3f}) yaw {:+.2f} deg'.format(
        rows[-1]['truth_x'], rows[-1]['truth_y'],
        math.degrees(rows[-1]['truth_yaw'])))

    whole = _stats(scored)
    print('')
    print('## Whole run, absolute error of map -> base_link')
    print('')
    print('  rms    {}'.format(_floor_line(whole['rms'], floor)))
    print('  max    {}'.format(_floor_line(whole['max'], floor)))
    print('  mean   {}'.format(_floor_line(whole['mean'], floor)))
    print('  min    {}'.format(_floor_line(whole['min'], floor)))
    print('  first  {}'.format(_floor_line(whole['first'], floor)))
    print('  final  {}'.format(_floor_line(whole['last'], floor)))
    yaws = [abs(math.degrees(r['e_yaw'])) for r in scored]
    print('  heading  final {:+.3f} deg, max |{:.3f}| deg, rms {:.3f} deg'
          .format(math.degrees(scored[-1]['e_yaw']), max(yaws),
                  math.sqrt(sum(y * y for y in yaws) / len(yaws))))

    # ---- motion phases, from ground truth alone ----
    flags = _moving_flags(rows)
    index_of = {id(r): i for i, r in enumerate(rows)}
    phases = []
    start = 0
    for i in range(1, len(rows) + 1):
        if i == len(rows) or flags[i] != flags[start]:
            phases.append((flags[start], start, i - 1))
            start = i
    print('')
    print('## Motion phases, segmented from GROUND TRUTH alone')
    print('')
    print('A phase is standing still when the reference moves less than '
          '{:.3f} m/s'.format(STILL_SPEED_MPS))
    print('over a {:.1f} s window. The reference is exact, so this is a fact '
          'about'.format(STILL_WINDOW_S))
    print('the vehicle and not a verdict about an estimate.')
    print('')
    print('| phase | state | sim s | seconds | error mean | error max | '
          'error end | heading end |')
    print('|---|---|---|---|---|---|---|---|')
    for number, (moving, lo, hi) in enumerate(phases, start=1):
        segment = [r for r in rows[lo:hi + 1]
                   if r['slam_ok'] > 0.5 and not math.isnan(r['w_x'])]
        stat = _stats(segment)
        span = rows[hi]['sim_s'] - rows[lo]['sim_s']
        if stat is None:
            print('| {} | {} | {:.1f} | {:.1f} | no map pose | | | |'.format(
                number, 'MOVING' if moving else 'STILL',
                rows[lo]['sim_s'] - rows[0]['sim_s'], span))
            continue
        print('| {} | {} | {:.1f} | {:.1f} | {:.3f} m | {:.3f} m | {:.3f} m '
              '| {:+.3f} deg |'.format(
                  number, 'MOVING' if moving else 'STILL',
                  rows[lo]['sim_s'] - rows[0]['sim_s'], span,
                  stat['mean'], stat['max'], stat['last'],
                  math.degrees(segment[-1]['e_yaw'])))
    del index_of

    # ---- the dwell, if there is one ----
    dwells = [(lo, hi) for moving, lo, hi in phases
              if not moving and rows[hi]['sim_s'] - rows[lo]['sim_s']
              >= args.dwell_min_s]
    if dwells:
        lo, hi = max(dwells, key=lambda p: rows[p[1]]['sim_s']
                     - rows[p[0]]['sim_s'])
        span = rows[hi]['sim_s'] - rows[lo]['sim_s']
        before = [r for r in rows[:lo]
                  if r['slam_ok'] > 0.5 and not math.isnan(r['w_x'])]
        during = [r for r in rows[lo:hi + 1]
                  if r['slam_ok'] > 0.5 and not math.isnan(r['w_x'])]
        after = [r for r in rows[hi + 1:]
                 if r['slam_ok'] > 0.5 and not math.isnan(r['w_x'])]
        print('')
        print('## THE DWELL')
        print('')
        print('Longest stationary phase: {:.1f} s of simulation time, from '
              't {:.1f} s to'.format(span, rows[lo]['sim_s'] - rows[0]['sim_s']))
        print('t {:.1f} s, at ground truth ({:+.3f}, {:+.3f}) yaw {:+.2f} '
              'deg.'.format(rows[hi]['sim_s'] - rows[0]['sim_s'],
                            rows[lo]['truth_x'], rows[lo]['truth_y'],
                            math.degrees(rows[lo]['truth_yaw'])))
        # The navigation lidar's own position, which is what the stretch
        # extents in WAREHOUSE_LANDMARKS.md are indexed by.
        c, s = (math.cos(rows[lo]['truth_yaw']), math.sin(rows[lo]['truth_yaw']))
        sx = rows[lo]['truth_x'] + c * 0.55 - s * (-0.40)
        sy = rows[lo]['truth_y'] + s * 0.55 + c * (-0.40)
        print('Navigation lidar stood at ({:+.3f}, {:+.3f}).'.format(sx, sy))
        print('')
        for label, segment in (('BEFORE (all motion up to the stop)', before),
                               ('DURING (the dwell itself)', during),
                               ('AFTER  (everything past the dwell)', after)):
            stat = _stats(segment)
            if stat is None:
                print('  {:<38} no scored sample'.format(label))
                continue
            print('  {:<38} n={:<5} mean {:.3f} m  max {:.3f} m  '
                  'entry {:.3f} m  exit {:.3f} m'.format(
                      label, stat['n'], stat['mean'], stat['max'],
                      stat['first'], stat['last']))
        if during:
            growth = during[-1]['e_norm'] - during[0]['e_norm']
            dyaw = math.degrees(_wrap(during[-1]['e_yaw'] - during[0]['e_yaw']))
            print('')
            print('  error at dwell entry   {}'.format(
                _floor_line(during[0]['e_norm'], floor)))
            print('  error at dwell exit    {}'.format(
                _floor_line(during[-1]['e_norm'], floor)))
            print('  GROWTH OVER THE DWELL  {:+.4f} m over {:.1f} s'.format(
                growth, span))
            print('')
            _apportion(during, rows[lo], rows[hi], span,
                       'the stationary phase')
    # THE SAME APPORTIONMENT OVER EVERY COMMANDED LEG. Deliberately OUTSIDE
    # the dwell block above: a run with no dwell still has legs worth
    # apportioning, and the first version of this printed nothing at all for
    # the reverse and forward passes because it sat under `if dwells:`.
    #
    # It also gives the SECOND window the dwell needs. The stationary phase
    # above begins where GROUND TRUTH says motion ceased, which is after the
    # coast; a dwell "beginning at the stop" begins at the stop COMMAND,
    # which is earlier, and that is the window
    # docs/reports/m5-07e-gate-leak.md's bound is stated over. Both are
    # printed because they give different numbers and which one is meant has
    # to be said rather than assumed.
    if args.marks:
        print('')
        print('## Apportionment per commanded leg')
        print('')
        for label, t0, t1 in _read_marks(args.marks):
            segment = [r for r in rows if t0 <= r['sim_s'] <= t1
                       and r['slam_ok'] > 0.5
                       and not math.isnan(r['w_x'])]
            if len(segment) < 2:
                continue
            print('  --- {} -> {}  ({:.1f} s) ---'.format(
                label[0], label[1], t1 - t0))
            _apportion(segment, segment[0], segment[-1], t1 - t0,
                       'the commanded window')
            print('')

    # ---- AMCL's corrections ----
    print('')
    print('## Corrections to map -> forklift/odom')
    print('')
    print('Steps above {:.3f} m or {:.2f} deg between consecutive samples.'
          .format(args.jump_m, math.degrees(args.jump_rad)))
    print('')
    jumps = 0
    biggest = 0.0
    for a, b in zip(scored, scored[1:]):
        step = math.hypot(b['mo_x'] - a['mo_x'], b['mo_y'] - a['mo_y'])
        turn = abs(_wrap(b['mo_yaw'] - a['mo_yaw']))
        biggest = max(biggest, step)
        if step > args.jump_m or turn > args.jump_rad:
            jumps += 1
            if jumps <= args.max_jumps:
                print('  {:8.1f} s  {:.3f} m  {:+.2f} deg  at truth '
                      '({:+.2f}, {:+.2f})'.format(
                          b['sim_s'] - rows[0]['sim_s'], step,
                          math.degrees(turn), b['truth_x'], b['truth_y']))
    if jumps > args.max_jumps:
        print('  ... and {} more'.format(jumps - args.max_jumps))
    if jumps == 0:
        print('  none above threshold')
    print('')
    print('total steps above threshold: {}, largest single step {:.4f} m'
          .format(jumps, biggest))
    return 0


# --------------------------------------------------------------------------- #

def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    pro = sub.add_parser('profile', help='print a named profile and exit')
    pro.add_argument('--profile', required=True, choices=sorted(_PROFILES))
    pro.set_defaults(func=lambda a: (print(profile_summary(a.profile)), 0)[1])

    mp = sub.add_parser('map-pose', help='world pose -> map pose')
    mp.add_argument('--x', type=float, required=True)
    mp.add_argument('--y', type=float, required=True)
    mp.add_argument('--yaw', type=float, default=0.0)
    mp.add_argument('--registration', default=None)
    mp.set_defaults(func=cmd_map_pose)

    drv = sub.add_parser('drive', help='drive a named profile, open loop')
    drv.add_argument('--profile', required=True, choices=sorted(_PROFILES))
    drv.add_argument('--config', default=_DEFAULT_CONFIG)
    drv.add_argument('--marks', default=None,
                     help='write one row per leg boundary here')
    drv.set_defaults(func=cmd_drive)

    ana = sub.add_parser('analyse', help='score a recording ABSOLUTELY')
    ana.add_argument('--csv', required=True)
    ana.add_argument('--label', default=None)
    ana.add_argument('--registration', default=None)
    ana.add_argument('--marks', default=None,
                     help='leg marks from `drive`, echoed for the record')
    ana.add_argument('--dwell-min-s', type=float, default=30.0,
                     help='shortest stationary phase reported as a dwell')
    ana.add_argument('--jump-m', type=float, default=0.05)
    ana.add_argument('--jump-rad', type=float, default=0.0087)
    ana.add_argument('--max-jumps', type=int, default=25)
    ana.set_defaults(func=cmd_analyse)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
