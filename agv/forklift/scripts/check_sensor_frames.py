#!/usr/bin/env python3
"""check_sensor_frames.py - do the four documents agree about the sensors?

WHY THIS EXISTS
  agv/forklift/ states the same sensor facts in four places, because the
  four are read by different things: model.sdf by Gazebo, config.yaml by
  the Python nodes, README.md by a person, and /tf_static by Nav2. Three
  of them are copies. A copy that is only ASSERTED to agree is a copy
  that will disagree, and the failure mode is silent: a transform that is
  right in the document and wrong on the wire moves an obstacle by half a
  metre and nothing logs a word.

  So the agreement is checked here, and every claim about it in
  README.md and in EVIDENCE_SENSOR_TF.md is this program's output.

WHAT IT CHECKS, IN ORDER
  1  model.sdf supports a static sensor transform at all: sensor links
     fixed to base_link, gz_frame_id naming its own link, identity sensor
     pose, base_link at the model origin. (These are sensor_tf.py's own
     preconditions, run through sensor_tf.py, so the check exercises the
     node's derivation rather than a second copy of it.)
  2  README.md's scanner table against model.sdf: frame name, x, y, z,
     yaw. This is the check with real independence - the README numbers
     were typed by a person.
  3  config.yaml's frames: block against model.sdf's link names and
     <robot_base_frame>.
  4  config.yaml's gz topics against model.sdf's <topic> elements, both
     directions, plus the channel-naming rule: every scanner channel that
     is reachable by a subscriber is a MEASUREMENT channel and says so in
     its name. A safe channel has no topic.
  5  obstacle.sector_centre_rad against the mount yaw of the sensor whose
     channel obstacle_zone.py reads, and the resulting sector against
     that sensor's aperture.
  6  (--live only) the running graph: /tf_static carries exactly these
     transforms, tf2 resolves each of them from the base frame, and each
     scan's header.frame_id is the frame published for it.

Usage (checks 1-5 need no ROS and no simulator):
  python3 agv/forklift/scripts/check_sensor_frames.py
  python3 agv/forklift/scripts/check_sensor_frames.py --live [--timeout S]

Exit status is 0 only if every check performed passed.
"""

import argparse
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

import yaml

import sensor_tf

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_MODEL = os.path.join(_DIR, 'model.sdf')
_CONFIG = os.path.join(_DIR, 'config.yaml')
_README = os.path.join(_DIR, 'README.md')

#: Position tolerance [m] and angle tolerance [rad] between any two of the
#: four sources.
#:
#: The angle tolerance is not arbitrary and is not cosmetic. model.sdf
#: writes the front scanner's yaw as 0.7853982 rad - seven decimals of a
#: radian - while README.md writes the same angle as +45 deg, so the two
#: differ by 2.1e-6 deg BY CONSTRUCTION and no editing of either document
#: removes it. The tolerance therefore sits above that rounding (3.7e-8
#: rad) and far below anything physical: 1e-6 rad is 0.2 arcsec, which is
#: 5.5 micrometres of lateral error at the 5.50 m end of this sensor's
#: range.
_TOL_M = 1e-6
_TOL_RAD = 1e-6

#: The word that marks a non-safe measurement channel in a topic name.
_MEASUREMENT = 'measurement'


class Checker(object):
    """Collects pass/fail rows so the summary is counted, not claimed."""

    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=''):
        self.rows.append((bool(ok), name, detail))
        print('{}  {:<58} {}'.format('ok  ' if ok else 'FAIL', name, detail))
        return bool(ok)

    def note(self, text):
        print('      {}'.format(text))

    @property
    def failed(self):
        return [row for row in self.rows if not row[0]]

    def summary(self):
        print('')
        print('RESULT: {} ({} check(s), {} failing)'.format(
            'PASS' if not self.failed else 'FAIL',
            len(self.rows), len(self.failed)))
        return 0 if not self.failed else 1


def section(title):
    print('')
    print('== {} {}'.format(title, '=' * max(0, 72 - len(title))))


def _norm(text):
    """Normalise the typography a Markdown table brings with it."""
    return (text.replace('−', '-')     # minus sign
                .replace('–', '-')     # en dash
                .replace('°', '')      # degree sign
                .replace('`', '')
                .replace('*', '')
                .strip())


def read_readme_scanners(path):
    """Pull (sensor, frame, x, y, z, yaw_deg) from README's scanner table.

    The table is a contract table a person maintains, so it is parsed
    rather than trusted: a row that stops matching this shape is itself a
    finding and is reported as one.
    """
    rows = {}
    pattern = re.compile(
        r'^\|\s*`(?P<sensor>[a-z0-9_]+)`\s*\|\s*`(?P<frame>[a-z0-9_]+)`\s*\|'
        r'\s*(?P<pose>[^|]+)\|')
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            match = pattern.match(line)
            if not match:
                continue
            parts = [_norm(p) for p in match.group('pose').split(',')]
            if len(parts) != 4:
                raise ValueError(
                    'README row for {} does not carry four pose values: '
                    '{!r}'.format(match.group('sensor'), match.group('pose')))
            rows[match.group('sensor')] = {
                'frame': match.group('frame'),
                'pose': tuple(float(p) for p in parts),
            }
    return rows


def read_sdf_sensors(path):
    """Sensor name -> link, topic, type and, for a lidar, its aperture.

    NOT EVERY SENSOR ON THIS MODEL IS A SCANNER. Since brief m5-07c the
    model also carries an IMU, which has no aperture, no sample count and
    no range. The aperture fields are therefore present only for sensors
    that declare a <lidar>, and the one check that uses them - section 5,
    the process consumer's sector - selects the front safety scanner by
    topic and so never reaches a sensor that lacks them. Reading the
    aperture unconditionally would have crashed this checker on the IMU
    with an AttributeError that says nothing about what is wrong.
    """
    model = ET.parse(path).getroot().find('model')
    sensors = {}
    for link in model.findall('link'):
        for sensor in link.findall('sensor'):
            spec = {
                'link': link.get('name'),
                'type': sensor.get('type'),
                'topic': (sensor.findtext('topic') or '').strip(),
            }
            horizontal = sensor.find('./lidar/scan/horizontal')
            ranges = sensor.find('./lidar/range')
            if horizontal is not None and ranges is not None:
                spec.update({
                    'samples': int(horizontal.findtext('samples')),
                    'angle_min': float(horizontal.findtext('min_angle')),
                    'angle_max': float(horizontal.findtext('max_angle')),
                    'range_min': float(ranges.findtext('min')),
                    'range_max': float(ranges.findtext('max')),
                })
            sensors[sensor.get('name')] = spec
    return sensors


def check_static(checker):
    """Checks 1-5. No ROS, no simulator, no running anything."""
    with open(_CONFIG, 'r', encoding='utf-8') as handle:
        cfg = yaml.safe_load(handle)

    section('1. model.sdf supports a static sensor transform')
    try:
        base_frame, frames = sensor_tf.read_model(_MODEL)
        checker.check(
            'sensor_tf.read_model accepts the model',
            True, '{} frame(s), parent {}'.format(len(frames), base_frame))
    except (sensor_tf.ModelError, ET.ParseError) as exc:
        checker.check('sensor_tf.read_model accepts the model', False, str(exc))
        return checker, None, None, None
    print('')
    print(sensor_tf.format_table(base_frame, frames))

    by_link = dict((frame.link, frame) for frame in frames)
    sdf_sensors = read_sdf_sensors(_MODEL)

    section('2. README.md scanner table vs model.sdf')
    readme = read_readme_scanners(_README)
    checker.check('README declares one row per SDF sensor',
                  set(readme) == set(sdf_sensors),
                  'README {} / SDF {}'.format(
                      sorted(readme), sorted(sdf_sensors)))
    for name in sorted(sdf_sensors):
        if name not in readme:
            continue
        frame = by_link[sdf_sensors[name]['link']]
        x, y, z, yaw_deg = readme[name]['pose']
        deltas = (abs(x - frame.xyz[0]), abs(y - frame.xyz[1]),
                  abs(z - frame.xyz[2]),
                  abs(math.radians(yaw_deg) - frame.rpy[2]))
        checker.check(
            'README frame name for {}'.format(name),
            readme[name]['frame'] == frame.link,
            '{} vs {}'.format(readme[name]['frame'], frame.link))
        checker.check(
            'README pose for {}'.format(name),
            max(deltas[:3]) <= _TOL_M and deltas[3] <= _TOL_RAD,
            'dx {:.2e} dy {:.2e} dz {:.2e} m, dyaw {:.2e} rad'.format(*deltas))

    section('3. config.yaml frames: block vs model.sdf')
    frames_cfg = cfg.get('frames', {})
    checker.check('config frames.base == SDF <robot_base_frame>',
                  frames_cfg.get('base') == base_frame,
                  '{} vs {}'.format(frames_cfg.get('base'), base_frame))
    for sensor_name, spec in sorted(sdf_sensors.items()):
        checker.check(
            'config frames.{} == SDF link/gz_frame_id'.format(sensor_name),
            frames_cfg.get(sensor_name) == spec['link'],
            '{} vs {}'.format(frames_cfg.get(sensor_name), spec['link']))

    section('4. topic contract and the channel-naming rule')
    topics = cfg['topics']
    sdf_topics = set()
    for element in ET.parse(_MODEL).getroot().iter('topic'):
        sdf_topics.add((element.text or '').strip())
    # <topic> is what a sensor and most systems use; the OdometryPublisher
    # names its two outputs <odom_topic> and <tf_topic> instead. All three
    # element names have to be swept, or a topic the model publishes could
    # sit outside the contract without a check noticing.
    for tag in ('odom_topic', 'tf_topic'):
        for element in ET.parse(_MODEL).getroot().iter(tag):
            sdf_topics.add((element.text or '').strip())
    cfg_gz_topics = set(v for k, v in topics.items() if k.startswith('gz_'))
    # gz_-prefixed topics OWNED BY VEHICLE SOFTWARE, not by the model.
    # The original rule here read "every config gz_ topic exists in
    # model.sdf", which was true until m5-50 moved the model's joint
    # controllers onto the actuator terminals: since then the three raw
    # command names are ROS-side topics that KEEP the /gz/ prefix to say
    # "raw plant command", and m5-73 added three gz-transport topics
    # published by scripts/scan_viz_repeater.cc rather than by the model.
    # Each exception is named by config KEY with its owner, so a NEW
    # unexplained gz_ topic still fails the check - and a second check
    # below refuses if the model ever starts publishing one of these
    # names itself, which would put two owners on one topic.
    software_owned_keys = {
        # m5-50: sto_contactor.py subscribes these on ROS and forwards to
        # the actuator terminals; the model no longer listens here.
        'gz_steer_cmd', 'gz_traction_cmd', 'gz_fork_cmd',
        # m5-73: scan_viz_repeater.cc publishes these on the gz
        # transport, world_pose repaired, for the GUI only.
        'gz_viz_scan_nav', 'gz_viz_safety_scanner_front',
        'gz_viz_safety_scanner_rear',
    }
    software_owned = set(topics[k] for k in software_owned_keys
                         if k in topics)
    checker.check('every SDF topic is declared in config.yaml',
                  sdf_topics <= cfg_gz_topics,
                  'missing: {}'.format(sorted(sdf_topics - cfg_gz_topics)))
    checker.check('every non-software-owned config gz_ topic is in model.sdf',
                  cfg_gz_topics - software_owned <= sdf_topics,
                  'extra: {}'.format(
                      sorted(cfg_gz_topics - software_owned - sdf_topics)))
    checker.check('no software-owned gz_ topic is also published by the model',
                  not (software_owned & sdf_topics),
                  'two owners: {}'.format(sorted(software_owned & sdf_topics)))

    scanner_topics = sorted(spec['topic'] for spec in sdf_sensors.values()
                            if spec['link'].startswith('safety_scanner'))
    checker.check(
        'every reachable safety-scanner channel is named a measurement one',
        all(topic.endswith('/' + _MEASUREMENT) for topic in scanner_topics),
        '; '.join(scanner_topics))
    ros_names = set(v for k, v in topics.items() if not k.startswith('gz_'))
    suspect = sorted(name for name in sdf_topics | ros_names
                     if re.search(r'ossd|safe_|/safe\b|protective', name))
    checker.check('no safe channel appears as a topic on either transport',
                  not suspect, 'suspect: {}'.format(suspect) if suspect else '')

    section('5. the process consumer reads a sector that is straight ahead')
    source_topic = topics['safety_scanner_front_measurement']
    gz_source = topics['gz_safety_scanner_front_measurement']
    source = [name for name, spec in sdf_sensors.items()
              if spec['topic'] == gz_source]
    checker.check('the consumed ROS topic is the front measurement channel',
                  source_topic.endswith('safety_scanner_front/' + _MEASUREMENT)
                  and len(source) == 1,
                  '{} <- {}'.format(source_topic, gz_source))
    if len(source) == 1:
        spec = sdf_sensors[source[0]]
        mount_yaw = by_link[spec['link']].rpy[2]
        centre = float(cfg['obstacle']['sector_centre_rad'])
        half = float(cfg['obstacle']['sector_half_angle_rad'])
        checker.check(
            'sector_centre_rad == -(mount yaw of {})'.format(source[0]),
            abs(centre + mount_yaw) <= _TOL_RAD,
            'centre {:.7f} + yaw {:.7f} = {:.2e} rad'.format(
                centre, mount_yaw, centre + mount_yaw))
        low, high = centre - half, centre + half
        checker.check(
            'the sector lies inside that sensor\'s aperture',
            spec['angle_min'] <= low and high <= spec['angle_max'],
            'sector [{:.1f}, {:.1f}] deg in aperture [{:.1f}, {:.1f}] deg'
            .format(math.degrees(low), math.degrees(high),
                    math.degrees(spec['angle_min']),
                    math.degrees(spec['angle_max'])))
        checker.note(
            'in the vehicle frame that is [{:+.1f}, {:+.1f}] deg about the '
            'driving direction'.format(
                math.degrees(low + mount_yaw), math.degrees(high + mount_yaw)))
        checker.note(
            'clear-horizon value this consumer will publish is the scan\'s '
            'own range_max = {:.2f} m'.format(spec['range_max']))

    return checker, base_frame, frames, cfg


def check_live(checker, base_frame, frames, cfg, timeout_s):
    """Check 6. Needs a running graph: the transforms and the scans."""
    section('6. the running graph')

    import rclpy
    from rclpy.duration import Duration
    from rclpy.node import Node
    from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                           ReliabilityPolicy)
    from sensor_msgs.msg import LaserScan
    from tf2_msgs.msg import TFMessage
    from tf2_ros import Buffer, TransformListener

    latched = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                         reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)

    topics = cfg['topics']
    watched = {topics['safety_scanner_front_measurement']:
               cfg['frames']['safety_scanner_front'],
               topics['scan']: cfg['frames']['nav_lidar']}

    rclpy.init(args=[sys.argv[0]])
    node = Node('check_sensor_frames')
    seen_tf = {}
    seen_scan = {}

    def cb_tf_static(msg):
        for tf in msg.transforms:
            seen_tf[tf.child_frame_id] = tf

    def make_scan_cb(topic):
        def cb_scan(msg):
            seen_scan.setdefault(topic, msg)
        return cb_scan

    node.create_subscription(TFMessage, '/tf_static', cb_tf_static, latched)
    for topic in watched:
        node.create_subscription(
            LaserScan, topic, make_scan_cb(topic), QoSProfile(depth=10))

    buffer_ = Buffer()
    listener = TransformListener(buffer_, node)   # noqa: F841 - keeps it alive

    deadline = node.get_clock().now() + Duration(seconds=float(timeout_s))
    while node.get_clock().now() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
        if len(seen_tf) >= len(frames) and len(seen_scan) >= len(watched):
            break

    checker.check('/tf_static carries every sensor frame',
                  set(seen_tf) == set(f.link for f in frames),
                  'received: {}'.format(sorted(seen_tf)))
    for frame in frames:
        tf = seen_tf.get(frame.link)
        if tf is None:
            checker.check('published transform for {}'.format(frame.link),
                          False, 'not received')
            continue
        translation = (tf.transform.translation.x, tf.transform.translation.y,
                       tf.transform.translation.z)
        rotation = (tf.transform.rotation.x, tf.transform.rotation.y,
                    tf.transform.rotation.z, tf.transform.rotation.w)
        d_xyz = max(abs(a - b) for a, b in zip(translation, frame.xyz))
        d_q = max(abs(a - b) for a, b in zip(rotation, frame.quaternion))
        checker.check(
            'published transform for {} matches model.sdf'.format(frame.link),
            tf.header.frame_id == base_frame and d_xyz <= _TOL_M
            and d_q <= 1e-9,
            'parent {} d_xyz {:.2e} m d_quat {:.2e}'.format(
                tf.header.frame_id, d_xyz, d_q))

    # The listener keeps its own subscription to /tf_static, so its buffer
    # fills independently of the check's. Asking it the instant the check's
    # own subscription is satisfied is a race, and it loses about half the
    # time on a loaded host. The wait below is bounded and is the same one
    # any consumer of these frames has to make: a transform is available
    # when the buffer says so, not when the publisher started.
    for frame in frames:
        deadline = node.get_clock().now() + Duration(seconds=10.0)
        error = 'buffer never accepted the transform'
        resolved = False
        while node.get_clock().now() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            try:
                buffer_.lookup_transform(base_frame, frame.link,
                                         rclpy.time.Time())
                resolved = True
                break
            except Exception as exc:                   # tf2 raises its own
                error = str(exc).strip()
        checker.check('tf2 resolves {} -> {}'.format(base_frame, frame.link),
                      resolved, '' if resolved else error)

    for topic, expected_frame in sorted(watched.items()):
        scan = seen_scan.get(topic)
        if scan is None:
            checker.check('{} carries data'.format(topic), False,
                          'nothing received in {} s'.format(timeout_s))
            continue
        checker.check(
            '{} header.frame_id is the published frame'.format(topic),
            scan.header.frame_id == expected_frame,
            '{} vs {}'.format(scan.header.frame_id, expected_frame))
        checker.note(
            '{}: {} samples, [{:+.1f}, {:+.1f}] deg, range [{:.2f}, {:.2f}] m'
            .format(topic, len(scan.ranges), math.degrees(scan.angle_min),
                    math.degrees(scan.angle_max), scan.range_min,
                    scan.range_max))

    node.destroy_node()
    rclpy.shutdown()
    return checker


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Check that model.sdf, config.yaml, README.md and '
                    '/tf_static agree about the three sensor frames.')
    parser.add_argument('--live', action='store_true',
                        help='also check a running graph (needs ROS 2)')
    parser.add_argument('--timeout', type=float, default=20.0,
                        help='seconds to wait for live data (default: '
                             '%(default)s)')
    args = parser.parse_args(argv)

    checker, base_frame, frames, cfg = check_static(Checker())
    if args.live and frames is not None:
        check_live(checker, base_frame, frames, cfg, args.timeout)
    return checker.summary()


if __name__ == '__main__':
    sys.exit(main())
