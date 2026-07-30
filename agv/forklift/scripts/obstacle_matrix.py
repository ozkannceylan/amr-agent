#!/usr/bin/env python3
"""obstacle_matrix.py - drive obstacle_zone.py through its contracted cases.

WHY THIS EXISTS
  The stop-zone evaluator's contract is written down in three places -
  agv/forklift/README.md's two obstacle rows, docs/reports/m4f-02b and
  m4f-04i, and plc/forklift/SPEC.md, which reads the two topics - and the
  cases that matter most are the ones a rendered scanner cannot easily be
  made to produce: a dead sensor, a garbage window, an empty message, an
  open horizon. Those were checked once by an uncommitted harness while
  the evaluator was being written. This is that harness, committed, so
  the claim "the evaluator still behaves as contracted" survives the next
  change of source, sensor or sector rather than being re-asserted.

  It publishes synthetic scans shaped like the FRONT SAFETY SCANNER's
  measurement channel - 275 samples, +-137.5 deg, 0.10 to 5.50 m - onto
  the topic obstacle_zone.py subscribes to, and reads its two outputs
  back. Nothing is stubbed: the real node runs, in its own process, with
  the repository's own config.yaml.

  Bearings in the case table are given in the VEHICLE frame, and this
  harness converts them into scan angles with the sensor's mount yaw
  taken from model.sdf. That is what makes the two sector cases below
  meaningful: an obstacle at +45 deg off the bow sits at scan angle zero,
  so a node whose sector was centred on its own scan zero would report it
  as dead ahead.

Usage (isolate the transport if anything else may be running):
  ROS_DOMAIN_ID=79 /usr/bin/python3 agv/forklift/scripts/obstacle_matrix.py
"""

import math
import os
import signal
import subprocess
import sys
import time

import yaml

import sensor_tf

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_MODEL = os.path.join(_DIR, 'model.sdf')
_CONFIG = os.path.join(_DIR, 'config.yaml')
_ZONE = os.path.join(_THIS_DIR, 'obstacle_zone.py')

_SENSOR = 'safety_scanner_front'
_NAN = float('nan')
_INF = float('inf')


def sensor_spec(model_path, sensor_name):
    """Aperture, sample count and range window of one sensor, from the SDF."""
    import xml.etree.ElementTree as ET
    model = ET.parse(model_path).getroot().find('model')
    for link in model.findall('link'):
        for sensor in link.findall('sensor'):
            if sensor.get('name') != sensor_name:
                continue
            horizontal = sensor.find('./lidar/scan/horizontal')
            ranges = sensor.find('./lidar/range')
            return {
                'samples': int(horizontal.findtext('samples')),
                'angle_min': float(horizontal.findtext('min_angle')),
                'angle_max': float(horizontal.findtext('max_angle')),
                'range_min': float(ranges.findtext('min')),
                'range_max': float(ranges.findtext('max')),
            }
    raise SystemExit('no sensor named {} in {}'.format(sensor_name, model_path))


def main():
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import Bool, Float64

    with open(_CONFIG, 'r', encoding='utf-8') as handle:
        cfg = yaml.safe_load(handle)
    spec = sensor_spec(_MODEL, _SENSOR)
    base_frame, frames = sensor_tf.read_model(_MODEL)
    mount_yaw = [f.rpy[2] for f in frames if f.link.startswith(_SENSOR)][0]

    topics = cfg['topics']
    source = topics['safety_scanner_front_measurement']
    stop_m = cfg['obstacle']['stop_distance_m']
    timeout_s = cfg['obstacle']['scan_timeout_s']
    half = cfg['obstacle']['sector_half_angle_rad']
    increment = ((spec['angle_max'] - spec['angle_min'])
                 / float(spec['samples'] - 1))
    r_max = spec['range_max']

    centre = cfg['obstacle']['sector_centre_rad']

    def index_of(bearing_deg):
        """Sample index nearest a bearing given in the VEHICLE frame."""
        angle = math.radians(bearing_deg) - mount_yaw
        return int(round((angle - spec['angle_min']) / increment))

    def bearing_of(index):
        """Vehicle-frame bearing [deg] of a sample index."""
        return math.degrees(spec['angle_min'] + index * increment + mount_yaw)

    # The sector edge falls BETWEEN samples: this sensor's 275 samples
    # over 275 deg give 1.0036 deg per sample, so there is no ray at
    # exactly -30 deg. The two edge cases below therefore use the last
    # sample inside the sector and the first one outside it, and print the
    # bearings they actually landed on rather than the ones asked for.
    inside = [i for i in range(spec['samples'])
              if abs(spec['angle_min'] + i * increment - centre) <= half]
    edge_in, edge_out = inside[0], inside[0] - 1

    def scan(fill, overrides=None, range_min=None, range_max=None, empty=False):
        msg = LaserScan()
        msg.header.frame_id = [f.link for f in frames
                               if f.link.startswith(_SENSOR)][0]
        msg.angle_min = spec['angle_min']
        msg.angle_max = spec['angle_max']
        msg.angle_increment = increment
        msg.range_min = spec['range_min'] if range_min is None else range_min
        msg.range_max = r_max if range_max is None else range_max
        ranges = [] if empty else [fill] * spec['samples']
        for index, value in (overrides or {}).items():
            ranges[index] = value
        msg.ranges = [float(v) for v in ranges]
        return msg

    # (name, scan or None to stall, hold [s], expected in_stop_zone,
    #  expected min_distance)
    cases = [
        ('clear sector', scan(5.0), 1.0, False, 5.0),
        ('obstacle dead ahead', scan(5.0, {index_of(0): 0.80}), 1.0, True, 0.80),
        ('obstacle at +10 deg', scan(5.0, {index_of(10): 1.15}), 1.0, True, 1.15),
        ('obstacle at -90 deg', scan(5.0, {index_of(-90): 0.50}), 1.0, False, 5.0),
        ('obstacle at +45 deg (scan zero)',
         scan(5.0, {index_of(45): 0.50}), 1.0, False, 5.0),
        ('last sample inside the edge ({:+.2f} deg)'.format(bearing_of(edge_in)),
         scan(5.0, {edge_in: 0.90}), 1.0, True, 0.90),
        ('first sample outside it ({:+.2f} deg)'.format(bearing_of(edge_out)),
         scan(5.0, {edge_out: 0.90}), 1.0, False, 5.0),
        ('obstacle just outside', scan(5.0, {index_of(0): 1.25}), 1.0, False, 1.25),
        ('all samples NaN', scan(_NAN), 1.0, True, 0.0),
        ('all samples +inf', scan(_INF), 1.0, False, r_max),
        ('all samples -inf', scan(-_INF), 1.0, True, 0.0),
        ('all below range_min', scan(0.05), 1.0, True, 0.0),
        ('all above range_max', scan(r_max + 3.0), 1.0, False, r_max),
        ('empty ranges', scan(0.0, empty=True), 1.0, True, 0.0),
        ('range window NaN', scan(5.0, range_max=_NAN), 1.0, True, 0.0),
        ('range window inverted', scan(5.0, range_min=9.0), 1.0, True, 0.0),
        ('one valid among NaN', scan(_NAN, {index_of(0): 2.0}), 1.0, False, 2.0),
        ('clear again before stall', scan(5.0), 1.0, False, 5.0),
        ('publisher stopped {:.1f} s'.format(3.0 * timeout_s),
         None, 3.0 * timeout_s, True, 0.0),
        ('recovers when it returns', scan(5.0), 1.0, False, 5.0),
    ]

    env = dict(os.environ)
    zone = subprocess.Popen(
        [sys.executable, _ZONE, '--config', _CONFIG], env=env)

    rclpy.init(args=[sys.argv[0]])
    node = Node('obstacle_matrix')
    qos = QoSProfile(depth=10)
    pub = node.create_publisher(LaserScan, source, qos)
    state = {'zone': None, 'distance': None}

    def cb_zone(msg):
        state['zone'] = msg.data

    def cb_distance(msg):
        state['distance'] = msg.data

    node.create_subscription(Bool, topics['obstacle_in_stop_zone'], cb_zone, qos)
    node.create_subscription(
        Float64, topics['obstacle_min_distance'], cb_distance, qos)

    print('obstacle_zone case matrix: source {}'.format(source))
    print('  sector {:+.1f} +-{:.1f} deg in the scan frame = {:+.1f} .. {:+.1f} '
          'deg in the vehicle frame'.format(
              math.degrees(cfg['obstacle']['sector_centre_rad']),
              math.degrees(half),
              math.degrees(cfg['obstacle']['sector_centre_rad'] - half
                           + mount_yaw),
              math.degrees(cfg['obstacle']['sector_centre_rad'] + half
                           + mount_yaw)))
    print('  stop {:.2f} m, timeout {:.2f} s, window [{:.2f}, {:.2f}] m, '
          '{} samples\n'.format(stop_m, timeout_s, spec['range_min'], r_max,
                                spec['samples']))

    def run_for(seconds, message):
        """Publish (or not) for a while, pumping the executor throughout."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if message is not None:
                message.header.stamp = node.get_clock().now().to_msg()
                pub.publish(message)
            rclpy.spin_once(node, timeout_sec=0.05)

    # Wait for the node to come up and publish its first verdict.
    deadline = time.monotonic() + 20.0
    while state['zone'] is None and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if state['zone'] is None:
        zone.terminate()
        raise SystemExit('obstacle_zone published nothing in 20 s')

    failures = 0
    for name, message, hold, want_zone, want_distance in cases:
        run_for(hold, message)
        got_zone, got_distance = state['zone'], state['distance']
        ok = (got_zone == want_zone
              and abs(got_distance - want_distance) < 1e-6)
        failures += 0 if ok else 1
        print('{:<4} {:<34} in_stop_zone={:<5} min_distance={:<10.4f} '
              '(expected {} / {:.3f})'.format(
                  'ok' if ok else 'FAIL', name, str(got_zone), got_distance,
                  want_zone, want_distance))

    print('\nRESULT: {} ({} failing case(s))'.format(
        'PASS' if failures == 0 else 'FAIL', failures))

    node.destroy_node()
    rclpy.shutdown()
    # SIGINT, not SIGTERM: it is what a launch shutdown sends, and it is
    # the signal the node's own KeyboardInterrupt handler expects.
    zone.send_signal(signal.SIGINT)
    zone.wait(timeout=10)
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
