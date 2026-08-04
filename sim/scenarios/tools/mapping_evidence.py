#!/usr/bin/env python3
"""mapping_evidence.py - record and read a SLAM mapping run.

THREE JOBS, THREE SUBCOMMANDS, AND NONE OF THEM STEERS ANYTHING.

  publishers  capture who publishes /tf and which EDGES appear on it. This
              is the proof that the EKF alone owns
              forklift/odom -> forklift/base_link: a count that was
              captured, not asserted.

  record      sample three pose streams and the map->odom correction into
              one CSV: the simulator's ground truth, the EKF's estimate,
              and SLAM's map->base_link. Nothing here is fed back to any
              of them.

  analyse     read that CSV against sim/worlds/WAREHOUSE_LANDMARKS.md
              section 5 - the degenerate stretches, by name and by extent -
              and report what actually happened in each one. IT HAS TWO
              SCORING MODES AND `--score` IS MANDATORY; see below.

THE TWO SCORING MODES, AND WHY CHOOSING IS NOT OPTIONAL

  `analyse` reports an estimate's error against ground truth, and there
  are two different quantities that phrase can mean. They differ by an
  order of magnitude, one of them is circular if used for the wrong
  question, and until 2026-08-04 this tool computed the circular one
  silently and without a name. `--score` now has no default: the caller
  states which quantity is wanted, because getting it wrong is not
  visible in the output.

  --score absolute
      THE LOCALISATION SCORE. The estimate's `map -> base_link` is carried
      into the world frame through the COMMITTED, PRE-DERIVED transform in
      sim/maps/warehouse/warehouse_registration.yaml, which was fitted to
      the map's walls before this run existed and contains no figure from
      it. NO PER-RUN ANCHORING HAPPENS ANYWHERE. A localiser that is
      consistently 0.3 m wrong scores 0.3 m, which is the whole point.
      The registration's own residual is printed as a FLOOR: an error
      below it is not a measurement of the localiser.

      This is the mode an AMCL gate is scored in. It is the only mode in
      which the words "localisation error" may be used.

  --score anchored-drift
      DRIFT SINCE THE START OF THE DRIVE, and nothing else. The rigid
      SE(2) transform carrying the estimate's FIRST drive sample exactly
      onto truth is applied to every sample, so the error curve starts at
      zero by construction and any constant offset or rotation of the
      estimate vanishes into the anchor.

      VALID for: how far a mapping run's estimate wandered from where it
      started - which is the right question about a map being built, since
      a SLAM map's frame is legitimately its own.

      INVALID for: any localisation score. It cannot see a constant error
      and it cannot see a wrong frame; an AMCL converged into the wrong
      part of a shallow basin scores near zero in it. It is also anchored
      on ONE sample, so yaw noise in that sample rotates the entire error
      curve - about 0.11 m at this route's lever arm.

      This mode produced the 0.185 m rms / 0.014 m final figures in
      sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md. Those remain correct as drift
      figures and must never be quoted as localisation accuracy
      (docs/reports/m5-08c-slam-judge.md finding 2).

  One more difference, and it is deliberate. `anchored-drift` DROPS the
  parked segments at each end of the run, because with a first-sample
  anchor they charge the route with heading error the route did not
  produce. `absolute` KEEPS EVERY SAMPLE: with no anchor there is nothing
  to protect, and a localiser's error while the vehicle stands still is a
  measurement in its own right - it is exactly the dwell case
  m5-08c finding 3 says the AMCL gate must contain.

WHY THE GROUND TRUTH IS IN THE CSV AT ALL. It is the reference an estimate
is SCORED against, which is the only legitimate use of it and the reason
agv/forklift/model.sdf still publishes it. It reaches no estimator: this
tool subscribes and writes a file, it publishes no topic and broadcasts no
transform, and slam_toolbox and the EKF are both running from inputs that
do not include it.

THE STRETCH EXTENTS ARE READ OUT OF WAREHOUSE_LANDMARKS.md AT RUN TIME,
from the table in its section 5, rather than copied into this file. A
copied list goes stale the moment the world changes - which is the same
rule sim/scenarios/tools/landmark_map.py already follows for the world's
rectangles.

USAGE (after sourcing /opt/ros/jazzy/setup.bash; the record and publishers
subcommands need rclpy, so run them with /usr/bin/python3):

  /usr/bin/python3 sim/scenarios/tools/mapping_evidence.py publishers \\
      --seconds 10
  /usr/bin/python3 sim/scenarios/tools/mapping_evidence.py record \\
      --csv /tmp/run.csv --seconds 600
  /usr/bin/python3 sim/scenarios/tools/mapping_evidence.py analyse \\
      --csv /tmp/run.csv --score anchored-drift
  /usr/bin/python3 sim/scenarios/tools/mapping_evidence.py analyse \\
      --csv /tmp/run.csv --score absolute

`analyse` and `closures` need no rclpy and run under any python3.
"""

import argparse
import math
import os
import re
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, '..', '..', '..'))
_LANDMARKS = os.path.join(
    _REPO_ROOT, 'sim', 'worlds', 'WAREHOUSE_LANDMARKS.md')

#: Frames. Quoted from agv/forklift/config.yaml's `frames:` block, which
#: mirrors model.sdf, and from sim/config/slam_toolbox_warehouse.yaml.
MAP_FRAME = 'map'
ODOM_FRAME = 'forklift/odom'
BASE_FRAME = 'forklift/base_link'

#: The aisle centrelines the named stretches sit on, in the SENSOR
#: coordinate of WAREHOUSE_LANDMARKS.md section 4. A sample is counted as
#: being in a stretch when the SENSOR is within this of the line.
AISLE_BAND_M = 1.20

#: Navigation lidar pose in the base_link frame, metres
#: (agv/forklift/model.sdf, quoted by WAREHOUSE_LANDMARKS.md section 4).
#: MEMBERSHIP OF A STRETCH IS DECIDED BY THE SENSOR'S POSITION, because the
#: extents in that file are sensor lines; the ERRORS reported are the pose
#: estimate's, which is base_link's. Mixing the two would misplace every
#: stretch boundary by 0.55 m.
LIDAR_DX_M = 0.55
LIDAR_DY_M = -0.40

CSV_HEADER = (
    'sim_s,truth_x,truth_y,truth_yaw,'
    'ekf_x,ekf_y,ekf_yaw,'
    'slam_x,slam_y,slam_yaw,'
    'mo_x,mo_y,mo_yaw,slam_ok\n')


# --------------------------------------------------------------------------- #
# The prediction this run is read against, parsed out of the file that owns it
# --------------------------------------------------------------------------- #

def read_stretches(path=_LANDMARKS):
    """The named degenerate stretches, from section 5 of the landmark file.

    Returns a list of dicts. The table row shape parsed is

      | **East A** | Aisle A, y = +7.00 | x in [+2.0, +7.0] | (+7.00,+7.00) |
        0.034 | 5.0 m |
    """
    rows = []
    pattern = re.compile(
        r'^\|\s*\*\*(?P<name>[^*]+)\*\*\s*\|'
        r'\s*(?P<line>[^|]+?),\s*y\s*=\s*(?P<y>[-+0-9.]+)\s*\|'
        r'\s*x in \[\s*(?P<x0>[-+0-9.]+)\s*,\s*(?P<x1>[-+0-9.]+)\s*\]\s*\|'
        r'\s*\((?P<wx>[-+0-9.]+),\s*(?P<wy>[-+0-9.]+)\)\s*\|'
        r'\s*\*\*(?P<aniso>[0-9.]+)\*\*\s*\|'
        r'\s*(?P<length>[0-9.]+)\s*m\s*\|')
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            match = pattern.match(line.strip())
            if match:
                rows.append({
                    'name': match.group('name').strip(),
                    'line': match.group('line').strip(),
                    'y': float(match.group('y')),
                    'x0': float(match.group('x0')),
                    'x1': float(match.group('x1')),
                    'worst': (float(match.group('wx')), float(match.group('wy'))),
                    'aniso': float(match.group('aniso')),
                    'length': float(match.group('length')),
                })
    if not rows:
        raise SystemExit(
            'no degenerate stretch table found in {} - section 5 has changed '
            'shape and this parser must be updated rather than guessed '
            'around'.format(path))
    return rows


# --------------------------------------------------------------------------- #
# publishers
# --------------------------------------------------------------------------- #

def cmd_publishers(args):
    import rclpy
    from rclpy.node import Node
    from tf2_msgs.msg import TFMessage

    rclpy.init(args=None)
    node = Node('mapping_evidence_publishers')
    node.set_parameters([rclpy.parameter.Parameter(
        'use_sim_time', rclpy.Parameter.Type.BOOL, True)])

    edges = {}

    def cb_tf(msg):
        for transform in msg.transforms:
            key = (transform.header.frame_id, transform.child_frame_id)
            edges[key] = edges.get(key, 0) + 1

    node.create_subscription(TFMessage, '/tf', cb_tf, 50)

    deadline = node.get_clock().now().nanoseconds
    import time as _time
    wall_end = _time.monotonic() + args.seconds
    while rclpy.ok() and _time.monotonic() < wall_end:
        rclpy.spin_once(node, timeout_sec=0.1)
    del deadline

    info = node.get_publishers_info_by_topic('/tf')
    static = node.get_publishers_info_by_topic('/tf_static')

    print('/tf')
    print('  Publisher count: {}'.format(len(info)))
    for entry in sorted(info, key=lambda e: e.node_name):
        print('    Node name: {}   Node namespace: {}   Topic type: {}'.format(
            entry.node_name, entry.node_namespace, entry.topic_type))
    print('  Edges observed over {:.0f} s, parent -> child : messages'.format(
        args.seconds))
    for (parent, child), count in sorted(edges.items()):
        print('    {} -> {} : {}'.format(parent, child, count))
    print('/tf_static')
    print('  Publisher count: {}'.format(len(static)))
    for entry in sorted(static, key=lambda e: e.node_name):
        print('    Node name: {}'.format(entry.node_name))

    node.destroy_node()
    rclpy.shutdown()

    # A verdict, so the capture is a check and not only a printout.
    owners = [e.node_name for e in info]
    if (ODOM_FRAME, BASE_FRAME) not in edges:
        print('\nVERDICT: FAIL - {} -> {} never appeared on /tf'.format(
            ODOM_FRAME, BASE_FRAME))
        return 1
    print('\nVERDICT: {} publisher(s) on /tf: {}'.format(
        len(owners), ', '.join(sorted(owners))))
    return 0


# --------------------------------------------------------------------------- #
# record
# --------------------------------------------------------------------------- #

def _yaw(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def cmd_record(args):
    import time as _time

    import rclpy
    import tf2_ros
    from nav_msgs.msg import Odometry
    from rclpy.node import Node

    rclpy.init(args=None)
    node = Node('mapping_evidence_recorder')
    node.set_parameters([rclpy.parameter.Parameter(
        'use_sim_time', rclpy.Parameter.Type.BOOL, True)])

    state = {'truth': None, 'ekf': None}

    def cb_truth(msg):
        p = msg.pose.pose.position
        state['truth'] = (p.x, p.y, _yaw(msg.pose.pose.orientation))

    def cb_ekf(msg):
        p = msg.pose.pose.position
        state['ekf'] = (p.x, p.y, _yaw(msg.pose.pose.orientation))

    node.create_subscription(Odometry, args.truth_topic, cb_truth, 10)
    node.create_subscription(Odometry, args.ekf_topic, cb_ekf, 10)

    buffer = tf2_ros.Buffer(cache_time=rclpy.duration.Duration(seconds=30.0))
    listener = tf2_ros.TransformListener(buffer, node)

    handle = open(args.csv, 'w', encoding='utf-8')
    handle.write(CSV_HEADER)

    period = 1.0 / args.rate
    wall_end = _time.monotonic() + args.seconds
    samples = 0
    slam_samples = 0
    next_sample = _time.monotonic()
    try:
        while rclpy.ok() and _time.monotonic() < wall_end:
            rclpy.spin_once(node, timeout_sec=0.02)
            now = _time.monotonic()
            if now < next_sample:
                continue
            next_sample = now + period
            if state['truth'] is None:
                continue
            sim_s = node.get_clock().now().nanoseconds * 1e-9

            slam = (float('nan'),) * 3
            mapodom = (float('nan'),) * 3
            ok = 0
            try:
                tf_mb = buffer.lookup_transform(
                    MAP_FRAME, BASE_FRAME, rclpy.time.Time())
                tf_mo = buffer.lookup_transform(
                    MAP_FRAME, ODOM_FRAME, rclpy.time.Time())
                slam = (tf_mb.transform.translation.x,
                        tf_mb.transform.translation.y,
                        _yaw(tf_mb.transform.rotation))
                mapodom = (tf_mo.transform.translation.x,
                           tf_mo.transform.translation.y,
                           _yaw(tf_mo.transform.rotation))
                ok = 1
                slam_samples += 1
            except (tf2_ros.LookupException, tf2_ros.ExtrapolationException,
                    tf2_ros.ConnectivityException):
                pass

            ekf = state['ekf'] or (float('nan'),) * 3
            handle.write(
                '{:.4f},{:.5f},{:.5f},{:.6f},{:.5f},{:.5f},{:.6f},'
                '{:.5f},{:.5f},{:.6f},{:.5f},{:.5f},{:.6f},{}\n'.format(
                    sim_s, *state['truth'], *ekf, *slam, *mapodom, ok))
            samples += 1
            if samples % 200 == 0:
                handle.flush()
                print('  {} samples, {} with a map->base_link'.format(
                    samples, slam_samples))
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        handle.close()
        del listener
        node.destroy_node()
        # SIGINT already shut the context down; calling shutdown again
        # raises RCLError and would bury the sample count under a traceback.
        if rclpy.ok():
            rclpy.shutdown()
    print('recorded {} samples ({} with SLAM) to {}'.format(
        samples, slam_samples, args.csv))
    return 0


# --------------------------------------------------------------------------- #
# analyse
# --------------------------------------------------------------------------- #

def _read_csv(path):
    rows = []
    with open(path, 'r', encoding='utf-8') as handle:
        header = handle.readline().strip().split(',')
        for line in handle:
            parts = line.strip().split(',')
            if len(parts) != len(header):
                continue
            rows.append(dict(zip(header, (float(v) for v in parts))))
    return rows


def _wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def _sensor_xy(row):
    """Ground-truth position of the NAVIGATION LIDAR, world frame."""
    c, s = math.cos(row['truth_yaw']), math.sin(row['truth_yaw'])
    return (row['truth_x'] + c * LIDAR_DX_M - s * LIDAR_DY_M,
            row['truth_y'] + s * LIDAR_DX_M + c * LIDAR_DY_M)


def anchor(rows, prefix):
    """Anchor an estimate's frame to the world at the run's FIRST sample.

    NEITHER ESTIMATE LIVES IN THE WORLD FRAME AND NEITHER EVER CLAIMED TO.
    `forklift/odom` is anchored at the vehicle's spawn pose, and `map` is
    anchored at whatever pose the EKF was reporting when slam_toolbox
    processed its first scan - which is an arbitrary rotation, not an
    error, because a SLAM map's frame is its own. Differencing either
    against a world-frame ground truth without anchoring measures the
    arbitrary offset and calls it drift.

    So the rigid SE(2) transform that carries the estimate's first pose
    onto the truth's first pose is applied to every sample of that
    estimate. Both error curves therefore start at exactly zero, and every
    number downstream is DRIFT SINCE THE START OF THE RUN, which is the
    quantity that means anything.

    Adds `<prefix>_wx`, `_wy`, `_wyaw` columns in place."""
    first = None
    for row in rows:
        if not math.isnan(row[prefix + '_x']):
            first = row
            break
    if first is None:
        return None
    dyaw = _wrap(first['truth_yaw'] - first[prefix + '_yaw'])
    c, s = math.cos(dyaw), math.sin(dyaw)
    ox = first['truth_x'] - (c * first[prefix + '_x'] - s * first[prefix + '_y'])
    oy = first['truth_y'] - (s * first[prefix + '_x'] + c * first[prefix + '_y'])
    for row in rows:
        ex, ey = row[prefix + '_x'], row[prefix + '_y']
        row[prefix + '_wx'] = ox + c * ex - s * ey
        row[prefix + '_wy'] = oy + s * ex + c * ey
        row[prefix + '_wyaw'] = _wrap(row[prefix + '_yaw'] + dyaw)
    return (ox, oy, dyaw)


def load_registration(path=None):
    """The committed T(world -> map), through the tool that owns it.

    INVARIANT 10. This tool does not parse the registration file and does
    not carry a copy of the transform. It imports
    sim/maps/warehouse/register_map.py, which derived it, and that module's
    `load_registration` verifies the grid md5 before returning - so a run
    scored against a map that has been rebuilt since the transform was
    derived FAILS HERE rather than producing a plausible wrong number."""
    module_dir = os.path.join(_REPO_ROOT, 'sim', 'maps', 'warehouse')
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    try:
        import register_map
    except ImportError:
        raise SystemExit(
            'cannot import {}/register_map.py, which owns the world->map '
            'transform. --score absolute cannot run without it.'
            .format(module_dir))
    if path is None:
        path = register_map.DEFAULT_REGISTRATION
    return register_map.load_registration(path)


def place_absolute(rows, prefix, record):
    """Carry an estimate from the MAP frame into the world, no anchoring.

    The registration is p_map = R(theta) p_world + t, so the inverse
    carries a map-frame pose out into the world:

        p_world = R(-theta) (p_map - t)

    Every sample gets the SAME transform, and that transform was fitted to
    the map's walls before this run existed. Nothing about this run enters
    it, so the error this produces is absolute: a constant offset stays a
    constant offset instead of vanishing into an anchor.

    Fills the same `<prefix>_wx`, `_wy`, `_wyaw` columns `anchor()` fills,
    so everything downstream is identical between the two modes and the
    only difference is which transform was used."""
    theta = record['theta_rad']
    c, s = math.cos(-theta), math.sin(-theta)
    tx, ty = record['t_x_m'], record['t_y_m']
    placed = 0
    for row in rows:
        mx, my = row[prefix + '_x'] - tx, row[prefix + '_y'] - ty
        row[prefix + '_wx'] = c * mx - s * my
        row[prefix + '_wy'] = s * mx + c * my
        row[prefix + '_wyaw'] = _wrap(row[prefix + '_yaw'] - theta)
        if not math.isnan(row[prefix + '_wx']):
            placed += 1
    return placed


def _errors(row, prefix):
    ex = row[prefix + '_wx'] - row['truth_x']
    ey = row[prefix + '_wy'] - row['truth_y']
    eyaw = _wrap(row[prefix + '_wyaw'] - row['truth_yaw'])
    return ex, ey, eyaw


def _passes(rows, stretch, entry_margin=1.5):
    """Split the samples inside a stretch into contiguous passes.

    A pass is a run of consecutive samples in which the vehicle is on the
    stretch's aisle line and inside its x extent. The margin is used only
    to find the sample just before and just after, which is what the entry
    and exit errors are read from."""
    inside = []
    for index, row in enumerate(rows):
        sx, sy = _sensor_xy(row)
        if abs(sy - stretch['y']) > AISLE_BAND_M:
            continue
        if stretch['x0'] <= sx <= stretch['x1']:
            inside.append(index)
    if not inside:
        return []
    groups, current = [], [inside[0]]
    for index in inside[1:]:
        if index - current[-1] <= 5:
            current.append(index)
        else:
            groups.append(current)
            current = [index]
    groups.append(current)
    del entry_margin
    return groups


def cmd_analyse(args):
    rows = _read_csv(args.csv)
    if not rows:
        raise SystemExit('no samples in {}'.format(args.csv))

    # THE TWO PARKED SEGMENTS ARE MEASURED AND THEN DROPPED. Everything
    # before the vehicle first moves and everything after it last moves is
    # the stack idling on the spot. The EKF integrates gyro bias there
    # exactly as it does when moving, so leaving either in charges the
    # ROUTE with heading error the route did not produce - while dropping
    # them silently would hide a real property of this estimator. They are
    # reported first, as two independent measurements of the same at-rest
    # drift rate.
    moved_at, stopped_at = 0, len(rows) - 1
    for index, row in enumerate(rows):
        if math.hypot(row['truth_x'] - rows[0]['truth_x'],
                      row['truth_y'] - rows[0]['truth_y']) > 0.05:
            moved_at = index
            break
    last = rows[-1]
    for index in range(len(rows) - 1, -1, -1):
        if math.hypot(rows[index]['truth_x'] - last['truth_x'],
                      rows[index]['truth_y'] - last['truth_y']) > 0.05:
            stopped_at = index
            break
    head, tail = rows[:moved_at + 1], rows[stopped_at:]
    absolute = args.score == 'absolute'

    if absolute:
        # NO ANCHORING, AND NO TRIMMING EITHER. With a pre-derived
        # transform there is no first sample to protect, and a localiser's
        # error while the vehicle stands still is a measurement rather than
        # a contaminant - it is the dwell case m5-08c finding 3 exists for.
        # The parked segments are REPORTED as their own rows below instead
        # of being dropped.
        registration = load_registration(args.registration)
        placed = place_absolute(rows, 'slam', registration)
        slam_rows = [r for r in rows if r['slam_ok'] > 0.5]
        print('# Localisation run, scored ABSOLUTELY')
        print('')
        print('Every `map` pose below was carried into the world frame '
              'through the')
        print('COMMITTED transform, derived from the map\'s walls before '
              'this run:')
        print('')
        print('    {}'.format(os.path.relpath(
            args.registration or os.path.join(
                _REPO_ROOT, 'sim', 'maps', 'warehouse',
                'warehouse_registration.yaml'), _REPO_ROOT)))
        print('    theta = {:+.6f} rad = {:+.4f} deg,  t = ({:+.4f}, '
              '{:+.4f}) m'.format(registration['theta_rad'],
                                  math.degrees(registration['theta_rad']),
                                  registration['t_x_m'],
                                  registration['t_y_m']))
        print('    grid md5 verified: this transform belongs to this map')
        print('')
        print('NO PER-RUN ANCHORING WAS APPLIED ANYWHERE. A constant error '
              'stays a')
        print('constant error. {} of {} samples carry a map pose.'.format(
            placed, len(rows)))
        print('')
        print('*** FLOOR: the registration\'s own residual is {:.4f} m rms, '
              '{:.4f} m max.'.format(registration['residual_rms_m'],
                                     registration['residual_max_m']))
        print('    No error below that is a measurement of the localiser; '
              'it is a')
        print('    measurement of how well a rigid transform fits a sheared '
              'grid.')
        print('')
        print('The EKF is NOT scored in this mode. `forklift/odom` has no '
              'derived')
        print('registration to the world - only `map` does - and asserting '
              'one from')
        print('the spawn pose is exactly the thing this mode exists to stop.')
        print('')
        for label, segment in (('before', head), ('after', tail)):
            seg = [r for r in segment if r['slam_ok'] > 0.5
                   and not math.isnan(r['slam_wx'])]
            if len(seg) > 1:
                errs = [_errors(r, 'slam') for r in seg]
                norms = [math.hypot(e[0], e[1]) for e in errs]
                span = seg[-1]['sim_s'] - seg[0]['sim_s']
                print('parked {:>6} the drive  {:6.1f} s, absolute error '
                      'mean {:.3f} m, max {:.3f} m  (KEPT, not dropped)'
                      .format(label, span, sum(norms) / len(norms),
                              max(norms)))
        print('')
    else:
        rows = rows[moved_at:stopped_at + 1]
        slam_rows = [r for r in rows if r['slam_ok'] > 0.5]
        anchor_ekf = anchor(rows, 'ekf')
        anchor_slam = anchor(rows, 'slam')

        print('# Mapping run, read against sim/worlds/WAREHOUSE_LANDMARKS.md')
        print('')
        print('SCORED AS ANCHORED DRIFT. Every error below is DRIFT SINCE '
              'THE START OF')
        print('THE DRIVE, not localisation error, and it is not a '
              'localisation score:')
        print('the anchor makes the first sample exactly zero by '
              'construction, so a')
        print('constant offset or a wrong frame is invisible here. For a '
              'localisation')
        print('number use --score absolute (m5-08c finding 2).')
        print('')
        for label, transform in (('forklift/odom', anchor_ekf),
                                 ('map', anchor_slam)):
            if transform:
                print('{:>13} sits at ({:+.3f}, {:+.3f}) in the world and is '
                      'rotated {:+.2f} deg from it'.format(
                          label, transform[0], transform[1],
                          math.degrees(transform[2])))
        print('  (this is a SINGLE-SAMPLE frame relation at the start of '
              'the drive.')
        print('   It is NOT the map artifact\'s rotation from the building - '
              'for that,')
        print('   fit the grid\'s walls: sim/maps/warehouse/register_map.py)')
        print('')
    for label, segment in (('before', head), ('after', tail)):
        # NAN-SAFE. The EKF has not published yet for the first samples of
        # a recording, so segment[0]['ekf_yaw'] is nan and a plain
        # difference printed "+nan deg" as if it were a measurement. Take
        # the first and last samples that actually carry an EKF heading.
        valid = [r for r in segment if not math.isnan(r['ekf_yaw'])]
        if len(valid) > 1:
            drift = _wrap(valid[-1]['ekf_yaw'] - valid[0]['ekf_yaw'])
            span = valid[-1]['sim_s'] - valid[0]['sim_s']
            print('parked {:>6} the drive  {:6.1f} s, EKF heading moved '
                  '{:+7.2f} deg  ({:+.5f} rad/s at rest)'.format(
                      label, span, math.degrees(drift),
                      drift / span if span else 0.0))
        elif len(segment) > 1:
            print('parked {:>6} the drive  {:6.1f} s, EKF heading: no '
                  'sample carried one'.format(
                      label, segment[-1]['sim_s'] - segment[0]['sim_s']))
    print('samples scored           {}{}'.format(
        len(rows), '  (whole recording; parked samples KEPT)' if absolute
        else '  (the drive only; parked segments dropped)'))
    print('samples with a SLAM pose {}'.format(len(slam_rows)))
    print('simulation time          {:.1f} s'.format(
        rows[-1]['sim_s'] - rows[0]['sim_s']))

    travelled = 0.0
    for a, b in zip(rows, rows[1:]):
        travelled += math.hypot(b['truth_x'] - a['truth_x'],
                                b['truth_y'] - a['truth_y'])
    # Turning is integrated on a 1 s stride rather than the 10 Hz sample
    # stride: at 10 Hz the sum of |dyaw| counts the vehicle's suspension
    # and steering jitter as turning and inflates the total.
    coarse = rows[::10]
    turned = sum(abs(_wrap(b['truth_yaw'] - a['truth_yaw']))
                 for a, b in zip(coarse, coarse[1:]))
    print('ground-truth path        {:.2f} m'.format(travelled))
    print('ground-truth turning     {:.1f} deg (1 s stride)'.format(
        math.degrees(turned)))
    print('')
    if absolute:
        print('NOTHING BELOW IS ANCHORED. Every error is an ABSOLUTE '
              'world-frame')
        print('error, taken through the committed transform above, floor '
              '{:.4f} m.'.format(registration['residual_max_m']))
    else:
        print('Both estimates are ANCHORED to the world at the first sample '
              'of')
        print('the drive: neither frame is the world frame and neither '
              'claims to')
        print('be, so every error below is DRIFT SINCE THE START OF THE '
              'DRIVE.')

    # ---- whole-run error, both estimates ----
    print('')
    print('## Whole-run error against ground truth')
    print('')
    print('| estimate | final |dx,dy| | final heading | max |dx,dy| | '
          'rms |dx,dy| |')
    print('|---|---|---|---|---|')
    pairs = (('slam', 'map -> base_link, ABSOLUTE'),) if absolute else (
        ('ekf', 'EKF (dead reckoning)'),
        ('slam', 'SLAM (map -> base_link)'))
    for prefix, label in pairs:
        source = slam_rows if prefix == 'slam' else rows
        source = [r for r in source
                  if not math.isnan(r[prefix + '_wx'])]
        if not source:
            print('| {} | no samples | | | |'.format(label))
            continue
        errs = [_errors(r, prefix) for r in source]
        norms = [math.hypot(e[0], e[1]) for e in errs]
        final = errs[-1]
        print('| {} | {:.3f} m | {:+.2f} deg | {:.3f} m | {:.3f} m |'.format(
            label, math.hypot(final[0], final[1]), math.degrees(final[2]),
            max(norms), math.sqrt(sum(n * n for n in norms) / len(norms))))

    # NOTE ON THE EKF COLUMN. The EKF estimate lives in the odom frame,
    # which starts at the spawn pose, so its error against a world-frame
    # truth is meaningful only because the two frames coincide at t = 0 by
    # construction (the vehicle is spawned at the odom origin).

    # ---- the named stretches ----
    stretches = read_stretches()
    print('')
    print('## The three named degenerate stretches')
    print('')
    print('Extents read from WAREHOUSE_LANDMARKS.md section 5 at run time.')
    print('`along-x` is the error component ALONG the aisle, which is the')
    print('direction those stretches carry no information in.')
    print('')
    # A DWELL AND A REVERSE ARE BOTH EXPRESSIBLE HERE, which m5-08c
    # finding 3 requires of whatever instrument the AMCL gate uses. A
    # dwell inside a stretch keeps the samples contiguous, so it stays ONE
    # pass and shows up as a long `seconds` against a short travelled
    # distance; leaving and re-entering starts a SECOND pass. Neither
    # needs a new subcommand, but `seconds` has to be on the table for a
    # dwell to be readable at all, which is why it is.
    print('| stretch | pass | samples | seconds | entry along-x | '
          'exit along-x | growth | max across-y | heading at exit |')
    print('|---|---|---|---|---|---|---|---|---|')
    for stretch in stretches:
        groups = _passes(slam_rows, stretch)
        if not groups:
            print('| **{}** | - | 0 | - | not driven with a SLAM pose | | | | |'
                  .format(stretch['name']))
            continue
        for number, group in enumerate(groups, start=1):
            first = slam_rows[group[0]]
            last = slam_rows[group[-1]]
            ex0, _, _ = _errors(first, 'slam')
            ex1, ey1, eyaw1 = _errors(last, 'slam')
            across = max(abs(_errors(slam_rows[i], 'slam')[1]) for i in group)
            print('| **{}** | {} | {} | {:.1f} s | {:+.3f} m | {:+.3f} m | '
                  '{:+.3f} m | {:.3f} m | {:+.2f} deg |'.format(
                      stretch['name'], number, len(group),
                      last['sim_s'] - first['sim_s'], ex0, ex1,
                      ex1 - ex0, across, math.degrees(eyaw1)))

    # The same table for the EKF, so "odometry carried it" is a measured
    # statement and not an inference. Anchored mode only: the EKF's frame
    # has no derived world registration, so there is nothing to score it
    # against absolutely.
    if not absolute:
        print('')
        print('The same stretches, for the EKF alone - what the scan matcher '
              'had')
        print('to work against:')
        print('')
        print('| stretch | pass | entry along-x | exit along-x | growth |')
        print('|---|---|---|---|---|')
        for stretch in stretches:
            groups = _passes(rows, stretch)
            for number, group in enumerate(groups, start=1):
                first, last = rows[group[0]], rows[group[-1]]
                if math.isnan(first['ekf_wx']):
                    continue
                ex0, _, _ = _errors(first, 'ekf')
                ex1, _, _ = _errors(last, 'ekf')
                print('| **{}** | {} | {:+.3f} m | {:+.3f} m | {:+.3f} m |'
                      .format(stretch['name'], number, ex0, ex1, ex1 - ex0))

    # ---- loop closure, detected as a step in map -> odom ----
    print('')
    print('## Corrections to map -> forklift/odom')
    print('')
    print('A loop closure re-optimises the graph and moves map -> odom in one')
    print('step. Steps above {:.3f} m or {:.2f} deg between consecutive'.format(
        args.jump_m, math.degrees(args.jump_rad)))
    print('samples are listed; continuous scan matching moves this transform')
    print('smoothly and produces none.')
    print('')
    print('| sim time | step | heading step | at ground truth | on |')
    print('|---|---|---|---|---|')
    jumps = 0
    for a, b in zip(slam_rows, slam_rows[1:]):
        step = math.hypot(b['mo_x'] - a['mo_x'], b['mo_y'] - a['mo_y'])
        turn = abs(_wrap(b['mo_yaw'] - a['mo_yaw']))
        if step > args.jump_m or turn > args.jump_rad:
            jumps += 1
            print('| {:.1f} s | {:.3f} m | {:+.2f} deg | ({:+.2f}, {:+.2f}) '
                  '| {} |'.format(
                      b['sim_s'] - rows[0]['sim_s'], step, math.degrees(turn),
                      b['truth_x'], b['truth_y'], _where(b, stretches)))
    if jumps == 0:
        print('| - | none above threshold | | | |')
    print('')
    print('total map->odom steps above threshold: {}'.format(jumps))
    return 0


def _where(row, stretches):
    """A human-readable location for a correction."""
    sx, sy = _sensor_xy(row)
    for stretch in stretches:
        if (abs(sy - stretch['y']) <= AISLE_BAND_M
                and stretch['x0'] <= sx <= stretch['x1']):
            return stretch['name']
    for label, y in (('aisle A', 7.00), ('aisle B', 0.65),
                     ('dock aisle', -5.50)):
        if abs(sy - y) <= AISLE_BAND_M:
            half = 'east' if sx > 1.8 else (
                'west' if sx < -1.8 else 'cross aisle mouth')
            return '{} {}'.format(label, half)
    if abs(sx) <= 1.8:
        return 'central cross aisle'
    if sx > 11.0:
        return 'east end aisle'
    if sx < -11.0:
        return 'west end aisle'
    return 'other'


# --------------------------------------------------------------------------- #
# closures
# --------------------------------------------------------------------------- #

#: One graph optimisation in slam_toolbox is one Ceres `Solve`, and
#: slam_toolbox runs Compute() only from MapperGraph::CorrectPoses(), which
#: only runs after TryCloseLoop() succeeded. So ONE OF THESE LINES IS ONE
#: LOOP CLOSURE. The line itself is a Ceres warning about the thread count
#: and says nothing about closure; it is used because it is the only thing
#: Ceres prints per solve at default verbosity, and because counting a
#: printed line is not agent arithmetic.
_CERES_RE = re.compile(
    r'^\[async_slam_toolbox_node-\d+\]\s+W\d{8}\s+'
    r'(?P<h>\d\d):(?P<m>\d\d):(?P<s>\d\d\.\d+)\s+\d+\s+preprocessor\.cc')

#: The route driver's own progress line: a ROS wall stamp and the
#: simulation time since the route began, on the same line. Two of these
#: are enough to map one clock onto the other; all of them are used.
_ROUTE_RE = re.compile(
    r'^\[INFO\]\s+\[(?P<wall>\d+\.\d+)\].*warehouse_mapping_route.*'
    r'\bt\s+(?P<sim>[0-9.]+) s')


def cmd_closures(args):
    pairs = []
    with open(args.route_log, 'r', encoding='utf-8') as handle:
        for line in handle:
            match = _ROUTE_RE.match(line.strip())
            if match:
                pairs.append((float(match.group('wall')),
                              float(match.group('sim'))))
    if len(pairs) < 2:
        raise SystemExit('fewer than two timed progress lines in {}'.format(
            args.route_log))
    # Least squares fit sim = a*wall + b. The two clocks differ by the real
    # time factor, so a slope is fitted rather than an offset assumed.
    #
    # THE WALL VALUES ARE CENTRED FIRST, AND THAT IS NOT TIDINESS. They are
    # Unix epochs near 1.79e9, so sum(w*w) is near 3.2e18 and the textbook
    # (n*Sww - Sw*Sw) form loses every significant digit of the difference
    # in float64: the uncentred fit on this run's own data returned a slope
    # of 1.0127 where the data plainly show 0.984, and a max residual of
    # 2.5 s where the true one is 0.06 s.
    n = len(pairs)
    w0 = sum(p[0] for p in pairs) / n
    s0 = sum(p[1] for p in pairs) / n
    sww = sum((p[0] - w0) ** 2 for p in pairs)
    sws = sum((p[0] - w0) * (p[1] - s0) for p in pairs)
    a = sws / sww
    b = s0 - a * w0
    residual = max(abs(a * (w - w0) + s0 - s) for w, s in pairs)

    midnight = math.floor(pairs[0][0] / 86400.0) * 86400.0

    rows = _read_csv(args.csv)
    moved_at = 0
    for index, row in enumerate(rows):
        if math.hypot(row['truth_x'] - rows[0]['truth_x'],
                      row['truth_y'] - rows[0]['truth_y']) > 0.05:
            moved_at = index
            break
    start_sim = rows[moved_at]['sim_s']
    stretches = read_stretches()

    print('# Loop closures')
    print('')
    print('One Ceres solve = one graph optimisation = one loop closure')
    print('(slam_toolbox calls the solver only from CorrectPoses, which runs')
    print('only after TryCloseLoop succeeded). Counted from {}.'.format(
        os.path.basename(args.slam_log)))
    print('')
    print('Wall time is mapped onto route time by least squares over the {} '
          'timed'.format(len(pairs)))
    print('progress lines of the route driver: slope {:.4f} simulation '
          'seconds per'.format(a))
    print('wall second (= the real time factor), max residual {:.3f} s.'.format(
        residual))
    del b
    print('')
    # SOLVES OUTSIDE THE ROUTE WINDOW ARE NOT LOOP CLOSURES AND ARE NOT
    # COUNTED. Deserialising a saved pose graph also runs one solve, so a
    # log that has been used to verify the serialised artifact carries an
    # extra Ceres line minutes after the drive ended. The window is the
    # route's own, from its first progress line to its last.
    window = (min(p[1] for p in pairs) - 10.0, max(p[1] for p in pairs) + 10.0)

    print('| # | route time | at ground truth | on |')
    print('|---|---|---|---|')
    count = 0
    outside = 0
    with open(args.slam_log, 'r', encoding='utf-8') as handle:
        for line in handle:
            match = _CERES_RE.match(line.strip())
            if not match:
                continue
            wall = (midnight + int(match.group('h')) * 3600
                    + int(match.group('m')) * 60 + float(match.group('s')))
            sim = a * (wall - w0) + s0
            if not window[0] <= sim <= window[1]:
                outside += 1
                continue
            count += 1
            nearest = min(
                rows, key=lambda r: abs((r['sim_s'] - start_sim) - sim))
            print('| {} | {:.1f} s | ({:+.2f}, {:+.2f}) | {} |'.format(
                count, sim, nearest['truth_x'], nearest['truth_y'],
                _where(nearest, stretches)))
    print('')
    print('total loop closures during the route: {}'.format(count))
    print('Ceres solves outside the route window, not counted: {}'.format(
        outside))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    pubs = sub.add_parser('publishers', help='capture /tf publishers and edges')
    pubs.add_argument('--seconds', type=float, default=10.0)
    pubs.set_defaults(func=cmd_publishers)

    rec = sub.add_parser('record', help='record the three pose streams')
    rec.add_argument('--csv', required=True)
    rec.add_argument('--seconds', type=float, default=900.0)
    rec.add_argument('--rate', type=float, default=10.0)
    rec.add_argument('--truth-topic', default='/forklift/odom')
    rec.add_argument('--ekf-topic', default='/forklift/odom_filtered')
    rec.set_defaults(func=cmd_record)

    ana = sub.add_parser('analyse', help='read the run against the prediction')
    ana.add_argument('--csv', required=True)
    # MANDATORY, AND MANDATORY IS THE POINT. There is no default because
    # the two modes answer different questions, differ by an order of
    # magnitude, and neither output would look wrong to a reader who had
    # not chosen. Before 2026-08-04 this tool had one unnamed behaviour -
    # the anchored one - and the localisation reading of its numbers was
    # circular (m5-08c finding 2). The fix is a name and a choice, not a
    # better default.
    ana.add_argument('--score', required=True,
                     choices=('absolute', 'anchored-drift'),
                     help='absolute: carry map->base_link into the world '
                          'through the COMMITTED, pre-derived registration; '
                          'no per-run anchoring anywhere; keeps the parked '
                          'samples. THE ONLY MODE IN WHICH "LOCALISATION '
                          'ERROR" MAY BE SAID. || anchored-drift: rigidly '
                          'anchor the estimate onto truth at the first '
                          'drive sample, so the error starts at zero by '
                          'construction. Valid for MAPPING DRIFT, invalid '
                          'for any localisation score - it cannot see a '
                          'constant error or a wrong frame')
    ana.add_argument('--registration', default=None,
                     help='registration file for --score absolute (default: '
                          'sim/maps/warehouse/warehouse_registration.yaml). '
                          'Its grid md5 is verified, so a run scored against '
                          'a rebuilt map fails rather than producing a '
                          'plausible wrong number')
    ana.add_argument('--jump-m', type=float, default=0.05,
                     help='map->odom step counted as a correction, m')
    ana.add_argument('--jump-rad', type=float, default=0.0087,
                     help='map->odom heading step counted as a correction, rad')
    ana.set_defaults(func=cmd_analyse)

    clo = sub.add_parser('closures', help='where the loop closures happened')
    clo.add_argument('--slam-log', required=True,
                     help='stdout of sim/launch/warehouse_slam.launch.py')
    clo.add_argument('--route-log', required=True,
                     help='stdout of sim/scenarios/warehouse_mapping_route.py')
    clo.add_argument('--csv', required=True)
    clo.set_defaults(func=cmd_closures)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
