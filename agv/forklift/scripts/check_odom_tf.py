#!/usr/bin/env python3
"""check_odom_tf.py - is odom -> base_link published, and does it track?

WHY THIS EXISTS
  SLAM and Nav2 need a continuous motion estimate on TF: `odom` ->
  `base_link`, moving with the vehicle. `scripts/sensor_tf.py` publishes
  the three STATIC sensor transforms, which are the leaves of the tree;
  this file is about the one moving edge underneath them, and about the
  claim that the edge is right rather than merely present.

  A transform that exists but lags, freezes or disagrees with the pose it
  was derived from is the expensive failure: nothing logs a word, the
  costmap simply drifts. So the four things a consumer actually depends
  on are measured here rather than asserted:

    1. it is published CONTINUOUSLY while the vehicle moves, at a rate
       this program measures rather than quotes from the model file,
    2. the whole chain resolves under tf2 - odom -> base_link -> each
       sensor frame - through a real TransformListener buffer, which is
       the code path Nav2 uses,
    3. the frame names on the wire are the names a Nav2 / slam_toolbox
       configuration will be pointed at,
    4. it TRACKS: driven around, the transform moves with the vehicle,
       and its residual against the ground-truth odometry topic is a
       number.

WHAT IT IS NOT
  Not a localisation check, and not an accuracy claim about any real
  vehicle. The transform under test is GROUND TRUTH out of the simulator:
  it carries no wheel slip, no encoder quantisation and no heading drift,
  so residual figures here are transport figures, not odometry-error
  figures. A real odom -> base_link drifts without bound. See
  EVIDENCE_ODOM_TF.md, which says so in its first paragraph for the same
  reason.

WHAT IT CHECKS, IN ORDER
  1  model.sdf: the OdometryPublisher publishes the transform itself, and
     it is the only publisher of this datum in this directory
     (invariant 10 - one owner per datum).
  2  config.yaml mirrors the two topic names.
  3  launch/vehicle.launch.py bridges the gz transform onto /tf, in the
     right direction and with the right pair of types.
  4  (--live) the running graph: rate, continuity, the chain under tf2,
     motion, and the residual against the odometry topic.

Usage (checks 1-3 need no ROS and no simulator):
  /usr/bin/python3 agv/forklift/scripts/check_odom_tf.py
  /usr/bin/python3 agv/forklift/scripts/check_odom_tf.py --live [--drive]

Exit status is 0 only if every check performed passed.
"""

import argparse
import importlib.util
import math
import os
import sys
import time
import xml.etree.ElementTree as ET

import yaml

import sensor_tf
from check_sensor_frames import Checker, section

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_MODEL = os.path.join(_DIR, 'model.sdf')
_CONFIG = os.path.join(_DIR, 'config.yaml')
_LAUNCH = os.path.join(_DIR, 'launch', 'vehicle.launch.py')

#: The gz system that owns this datum, and the ROS types the bridge has to
#: use to carry its transform output.
_ODOM_PLUGIN = 'gz::sim::systems::OdometryPublisher'
_ROS_TF_TYPE = 'tf2_msgs/msg/TFMessage'
_GZ_TF_TYPE = 'gz.msgs.Pose_V'

#: Continuity: no gap between consecutive transforms longer than this many
#: nominal periods. Three is chosen against what a consumer notices - Nav2
#: controllers run at 20 Hz and tolerate a missed cycle, not a stall.
_MAX_GAP_PERIODS = 3.0

#: Residual tolerances between the transform and the odometry topic. Both
#: come from the same pose in the same system, so anything above float
#: noise here is a transport defect (a dropped message paired against the
#: wrong stamp, a truncated field, a lagging bridge), not odometry error.
_TOL_RESIDUAL_M = 1e-6
_TOL_RESIDUAL_RAD = 1e-6

#: A drive is only evidence of tracking if the vehicle actually moved.
_MIN_TRAVEL_M = 1.0
_MIN_YAW_RAD = 0.20


def yaw_of(x, y, z, w):
    """Yaw [rad] of a quaternion, the only angle a planar vehicle has."""
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def wrap(angle):
    """Fold an angle difference into [-pi, pi] so it can be compared."""
    return math.atan2(math.sin(angle), math.cos(angle))


def load_launch_module():
    """Import launch/vehicle.launch.py to read its bridge list as values.

    Reading the module rather than grepping its text is the point: the
    check then holds against the list the launch file actually builds,
    including the config lookups inside it.
    """
    spec = importlib.util.spec_from_file_location('vehicle_launch', _LAUNCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_odometry_plugin(path):
    """The OdometryPublisher element of the model, as a plain dict."""
    root = ET.parse(path).getroot()
    found = [p for p in root.iter('plugin') if p.get('name') == _ODOM_PLUGIN]
    if len(found) != 1:
        return None, len(found)
    plugin = found[0]
    fields = {}
    for child in plugin:
        fields[child.tag] = (child.text or '').strip()
    return fields, 1


def check_static(checker):
    """Checks 1-3. No ROS, no simulator, no running anything."""
    with open(_CONFIG, 'r', encoding='utf-8') as handle:
        cfg = yaml.safe_load(handle)
    topics = cfg['topics']

    section('1. model.sdf owns the transform, and owns it once')
    fields, count = read_odometry_plugin(_MODEL)
    checker.check('model.sdf declares exactly one OdometryPublisher',
                  count == 1, '{} found'.format(count))
    if fields is None:
        return checker, None, None
    checker.check('it names its transform topic explicitly',
                  bool(fields.get('tf_topic')),
                  'tf_topic = {!r} (without it the name is the '
                  'model-scoped default and moves with the spawn name)'
                  .format(fields.get('tf_topic')))
    checker.check('it publishes the transform from the same pose as the '
                  'odometry topic', bool(fields.get('odom_topic')),
                  'odom_topic = {!r}'.format(fields.get('odom_topic')))
    checker.check('the transform is planar, like the vehicle',
                  fields.get('dimensions') == '2',
                  '<dimensions> = {!r}'.format(fields.get('dimensions')))
    checker.note('declared publish frequency {} Hz - a DECLARATION; '
                 'section 4 measures what arrives'
                 .format(fields.get('odom_publish_frequency')))

    base_frame, frames = sensor_tf.read_model(_MODEL)
    checker.check('<robot_base_frame> is the parent of the sensor frames',
                  fields.get('robot_base_frame') == base_frame,
                  '{} vs sensor_tf parent {}'.format(
                      fields.get('robot_base_frame'), base_frame))
    checker.check('the sensor transforms do not also claim the base frame '
                  'as a child',
                  all(frame.link != base_frame for frame in frames),
                  'children: {}'.format(sorted(f.link for f in frames)))

    # One owner per datum (invariant 10). The transform is the model's, so
    # no script here may broadcast one; the only broadcaster in this
    # directory is the STATIC sensor one, which publishes a different
    # topic and different children.
    broadcasters = {}
    scripts_dir = _THIS_DIR
    for name in sorted(os.listdir(scripts_dir)):
        if not name.endswith('.py'):
            continue
        with open(os.path.join(scripts_dir, name), 'r',
                  encoding='utf-8') as handle:
            text = handle.read()
        kinds = sorted(set(
            kind for kind in ('StaticTransformBroadcaster',
                              'TransformBroadcaster')
            if kind + '(' in text))
        # StaticTransformBroadcaster contains TransformBroadcaster as a
        # substring, so a file using only the static one must not be
        # reported as using both.
        if 'StaticTransformBroadcaster' in kinds:
            kinds = ['StaticTransformBroadcaster']
        if kinds:
            broadcasters[name] = kinds
    dynamic = sorted(name for name, kinds in broadcasters.items()
                     if 'TransformBroadcaster' in kinds)
    checker.check('no script in this directory broadcasts a moving '
                  'transform', not dynamic,
                  'broadcasters found: {}'.format(broadcasters))

    section('2. config.yaml mirrors the two names')
    checker.check(
        'config topics.gz_tf_ground_truth == model.sdf <tf_topic>',
        topics.get('gz_tf_ground_truth') == fields.get('tf_topic'),
        '{} vs {}'.format(topics.get('gz_tf_ground_truth'),
                          fields.get('tf_topic')))
    checker.check(
        'the gz name says which source this transform comes from',
        'ground_truth' in (topics.get('gz_tf_ground_truth') or ''),
        '{} - after the EKF lands there are two pose streams and the '
        'reference must be named'.format(topics.get('gz_tf_ground_truth')))
    checker.check('config topics.tf is /tf',
                  topics.get('tf') == '/tf',
                  '{} - the only topic a TransformListener reads'
                  .format(topics.get('tf')))
    checker.check('config frames.base == model.sdf <robot_base_frame>',
                  cfg['frames'].get('base') == fields.get('robot_base_frame'),
                  '{} vs {}'.format(cfg['frames'].get('base'),
                                    fields.get('robot_base_frame')))

    section('3. launch/vehicle.launch.py carries it onto /tf, switchably')
    try:
        launch_module = load_launch_module()
    except ImportError as exc:
        checker.check('launch/vehicle.launch.py imports', False, str(exc))
        return checker, fields, cfg
    expected_arg = '{}@{}[{}'.format(topics['gz_tf_ground_truth'],
                                     _ROS_TF_TYPE, _GZ_TF_TYPE)
    checker.check('the transform bridge carries it, gz -> ROS',
                  expected_arg in launch_module._TF_BRIDGE_ARGS,
                  expected_arg)
    checker.check('it is remapped onto /tf',
                  (topics['gz_tf_ground_truth'], topics['tf'])
                  in launch_module._TF_BRIDGE_REMAPS,
                  '{} -> {}'.format(topics['gz_tf_ground_truth'],
                                    topics['tf']))
    # The seam. The interim source has to be retirable without an edit,
    # or "interim" is a word in a comment rather than a property of the
    # stack: the EKF that takes this edge over must be able to be the ONLY
    # publisher of it, which means this one must be able to not run.
    checker.check(
        'it is on its own bridge node, so it can be switched off',
        expected_arg not in launch_module._BRIDGE_ARGS
        and (topics['gz_tf_ground_truth'], topics['tf'])
        not in launch_module._BRIDGE_REMAPS,
        'not mixed into the main bridge list')
    description = launch_module.generate_launch_description()
    switch = [action for action in description.entities
              if getattr(action, 'name', None) == 'ground_truth_tf']
    default = ''
    if switch:
        default = ''.join(getattr(part, 'text', str(part))
                          for part in switch[0].default_value)
    checker.check(
        'the switch is a declared launch argument',
        len(switch) == 1,
        'ground_truth_tf, default {!r} - set false when the EKF owns the '
        'edge'.format(default))
    return checker, fields, cfg


def _drive_profile(speed_mps, steer_rad):
    """(duration [s], traction [m/s], steer [rad]) legs of the test drive.

    Straight, then a turn, then straight, then stopped. The turn is what
    makes the run a test of the transform's ROTATION as well as its
    translation, and the final stop is what shows the transform keeps
    being published when the vehicle is not moving.
    """
    return [(3.0, speed_mps, 0.0),
            (6.0, speed_mps, steer_rad),
            (3.0, speed_mps, 0.0),
            (2.0, 0.0, 0.0)]


def check_live(checker, fields, cfg, args):
    """Check 4. Needs a running graph, and optionally drives the vehicle."""
    section('4. the running graph')

    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.duration import Duration
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.qos import QoSProfile
    from rclpy.time import Time
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Float64
    from tf2_msgs.msg import TFMessage
    from tf2_ros import Buffer, TransformListener

    topics = cfg['topics']
    base_frame = cfg['frames']['base']
    odom_frame = fields['odom_frame']
    sensor_frames = [cfg['frames'][name] for name in
                     ('nav_lidar', 'safety_scanner_front',
                      'safety_scanner_rear')]
    nominal_period = 1.0 / float(fields['odom_publish_frequency'])

    rclpy.init(args=[sys.argv[0]])
    # use_sim_time, because the messages under test are stamped with the
    # SIMULATION clock and this program has to be able to reason about
    # "now" in the same time base a Nav2 or slam_toolbox consumer will.
    # Every WAIT below is still bounded on the wall clock, so a stalled
    # simulator ends the run rather than hanging it.
    node = Node('check_odom_tf', parameter_overrides=[
        Parameter('use_sim_time', Parameter.Type.BOOL, True)])
    qos = QoSProfile(depth=int(cfg['qos']['depth']))

    tf_samples = []        # (stamp_s, x, y, yaw) of odom -> base_link
    tf_other = set()       # any other parent/child pair seen on /tf
    odom_samples = []      # (stamp_s, x, y, yaw) from the odometry topic
    wheel_samples = []     # (stamp_s, drive wheel angle [rad])

    def cb_tf(msg):
        for tf in msg.transforms:
            stamp = tf.header.stamp.sec + tf.header.stamp.nanosec * 1e-9
            if (tf.header.frame_id == odom_frame
                    and tf.child_frame_id == base_frame):
                rot = tf.transform.rotation
                tf_samples.append((stamp, tf.transform.translation.x,
                                   tf.transform.translation.y,
                                   yaw_of(rot.x, rot.y, rot.z, rot.w)))
            else:
                tf_other.add((tf.header.frame_id, tf.child_frame_id))

    def cb_odom(msg):
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        rot = msg.pose.pose.orientation
        odom_samples.append((stamp, msg.pose.pose.position.x,
                             msg.pose.pose.position.y,
                             yaw_of(rot.x, rot.y, rot.z, rot.w),
                             msg.header.frame_id, msg.child_frame_id))

    def cb_joint_states(msg):
        if 'drive_wheel_joint' not in msg.name:
            return
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        wheel_samples.append(
            (stamp, msg.position[msg.name.index('drive_wheel_joint')]))

    node.create_subscription(TFMessage, topics['tf'], cb_tf, qos)
    node.create_subscription(Odometry, topics['odom'], cb_odom, qos)
    node.create_subscription(JointState, topics['joint_states'],
                             cb_joint_states, qos)
    pub_traction = node.create_publisher(
        Float64, topics['cmd_traction_speed'], qos)
    pub_steer = node.create_publisher(Float64, topics['cmd_steer_angle'], qos)

    # A 60 s cache, against tf2's 10 s default. This is an INSTRUMENT
    # choice, not a recommendation: the residual below pairs every
    # odometry message received during the whole run against the buffer
    # afterwards, and on the default cache the early half of a 15 s drive
    # has already aged out and shows up as unpaired samples. A consumer
    # keeps the default; it only ever asks about the recent past.
    buffer_ = Buffer(cache_time=Duration(seconds=60.0))
    listener = TransformListener(buffer_, node)   # noqa: F841 - keeps it alive

    # Every wait below is bounded on the WALL clock, deliberately. Sim time
    # is the message time base and it is what the samples are stamped with,
    # but a run must not be able to hang because the simulator stopped
    # advancing it.
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline and len(tf_samples) < 5:
        rclpy.spin_once(node, timeout_sec=0.1)
    checker.check('{} carries {} -> {}'.format(topics['tf'], odom_frame,
                                               base_frame),
                  len(tf_samples) >= 5,
                  '{} transform(s) in the first {:.0f} s'.format(
                      len(tf_samples), args.timeout))

    drove = False
    if args.drive and tf_samples:
        legs = _drive_profile(args.speed, args.steer)
        print('      driving: ' + '; '.join(
            '{:.0f} s at {:.2f} m/s, steer {:+.2f} rad'.format(*leg)
            for leg in legs))
        first = len(tf_samples)
        for duration, speed, steer in legs:
            pub_steer.publish(Float64(data=float(steer)))
            leg_end = time.monotonic() + duration
            while time.monotonic() < leg_end:
                pub_traction.publish(Float64(data=float(speed)))
                pub_steer.publish(Float64(data=float(steer)))
                rclpy.spin_once(node, timeout_sec=0.1)
        # Leave the vehicle stopped and straight whatever happens next.
        pub_traction.publish(Float64(data=0.0))
        pub_steer.publish(Float64(data=0.0))
        settle = time.monotonic() + 1.0
        while time.monotonic() < settle:
            rclpy.spin_once(node, timeout_sec=0.1)
        drove = len(tf_samples) > first
    elif tf_samples:
        watch = time.monotonic() + args.watch
        while time.monotonic() < watch:
            rclpy.spin_once(node, timeout_sec=0.1)

    # ---- rate and continuity, over the whole observation window --------
    stamps = [sample[0] for sample in tf_samples]
    if len(stamps) >= 2:
        span = stamps[-1] - stamps[0]
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        rate = (len(stamps) - 1) / span if span > 0 else float('nan')
        checker.check(
            'the transform is published continuously',
            max(gaps) <= _MAX_GAP_PERIODS * nominal_period,
            'largest gap {:.4f} s against a nominal period of {:.4f} s'
            .format(max(gaps), nominal_period))
        checker.note(
            'MEASURED rate {:.3f} Hz over {:.2f} s of simulated time, {} '
            'transforms; interval min {:.4f} s max {:.4f} s mean {:.4f} s'
            .format(rate, span, len(stamps), min(gaps), max(gaps),
                    span / (len(stamps) - 1)))
        checker.check(
            'the measured rate is the declared one within 5 %',
            abs(rate - 1.0 / nominal_period) <= 0.05 / nominal_period,
            '{:.3f} Hz measured vs {:.1f} Hz declared in model.sdf'
            .format(rate, 1.0 / nominal_period))
    else:
        checker.check('the transform is published continuously', False,
                      'fewer than two transforms received')

    checker.check('nothing else publishes on {}'.format(topics['tf']),
                  not tf_other,
                  'other parent -> child pairs seen: {}'.format(
                      sorted(tf_other)) if tf_other else 'one edge only')

    # ---- the frame names on the wire ----------------------------------
    if odom_samples:
        wire_parent = odom_samples[-1][4]
        wire_child = odom_samples[-1][5]
        checker.check(
            'the odometry topic names the same frames as the transform',
            wire_parent == odom_frame and wire_child == base_frame,
            '{} -> {}'.format(wire_parent, wire_child))
        checker.note(
            'these are the strings a Nav2 / slam_toolbox configuration is '
            'pointed at: odom_frame "{}", base_frame "{}"'
            .format(odom_frame, base_frame))
    else:
        checker.check('the odometry topic carries data', False,
                      'nothing on {}'.format(topics['odom']))

    # ---- the chain, through a real listener buffer ---------------------
    # A TransformListener holds its own subscription and its buffer fills
    # independently of this node's, so "published" and "answerable" are
    # different moments (m5-06 open question 5). The wait is bounded and
    # is the same one every consumer of this tree has to make.
    for child in [base_frame] + sensor_frames:
        deadline = time.monotonic() + 10.0
        error = 'buffer never accepted the transform'
        resolved = False
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            try:
                buffer_.lookup_transform(odom_frame, child, Time())
                resolved = True
                break
            except Exception as exc:                   # tf2 raises its own
                error = str(exc).strip()
        checker.check('tf2 resolves {} -> {}'.format(odom_frame, child),
                      resolved, '' if resolved else error)

    # The root above odom is the map frame, and it does not exist yet: no
    # SLAM, no AMCL. Its absence is checked rather than assumed, so the
    # day something publishes it this run says so.
    try:
        buffer_.lookup_transform('map', odom_frame, Time())
        map_present, detail = True, 'a map -> {} transform exists'.format(
            odom_frame)
    except Exception as exc:
        map_present, detail = False, str(exc).strip()
    checker.check('map is absent, as expected before SLAM runs',
                  not map_present, detail)

    # THE TIME BASE, which is a real trap and is cheap to check here.
    # Every message under test is stamped with the SIMULATION clock. A
    # consumer left on the system clock sees stamps decades in the past,
    # asks for "now" and gets nothing, and the failure looks like a
    # missing transform rather than a misconfigured node. Nav2 and
    # slam_toolbox both look up at their own now.
    sim_now = node.get_clock().now()
    checker.check('the simulation clock reaches a consumer of this tree',
                  sim_now.nanoseconds > 0,
                  'node clock reads {:.3f} s with use_sim_time - /clock is '
                  'bridged'.format(sim_now.nanoseconds * 1e-9))
    try:
        buffer_.lookup_transform(odom_frame, base_frame,
                                 sim_now - Duration(seconds=nominal_period))
        fresh, detail = True, 'asked at the node\'s own now minus one period'
    except Exception as exc:
        fresh, detail = False, str(exc).strip()
    checker.check('a consumer on simulation time resolves it at "now"',
                  fresh, detail)
    if tf_samples:
        checker.note(
            'the same lookup from a node left on the SYSTEM clock would ask '
            'for a stamp {:.3e} s ahead of the newest transform and fail: '
            'every consumer of this tree needs use_sim_time'
            .format(time.time() - tf_samples[-1][0]))

    # ---- a captured lookup, in the shape tf2_echo prints ---------------
    if tf_samples:
        for child in [base_frame] + sensor_frames:
            try:
                tf = buffer_.lookup_transform(odom_frame, child, Time())
            except Exception:
                continue
            trans = tf.transform.translation
            rot = tf.transform.rotation
            print('      {} -> {:<26} xyz [{:+.3f} {:+.3f} {:+.3f}]  '
                  'yaw {:+.4f} rad ({:+.2f} deg)'.format(
                      odom_frame, child, trans.x, trans.y, trans.z,
                      yaw_of(rot.x, rot.y, rot.z, rot.w),
                      math.degrees(yaw_of(rot.x, rot.y, rot.z, rot.w))))

    # ---- did it track? -------------------------------------------------
    if len(tf_samples) >= 2:
        travel = sum(math.hypot(b[1] - a[1], b[2] - a[2])
                     for a, b in zip(tf_samples, tf_samples[1:]))
        yaw_swept = sum(abs(wrap(b[3] - a[3]))
                        for a, b in zip(tf_samples, tf_samples[1:]))
        first, last = tf_samples[0], tf_samples[-1]
        checker.note(
            'transform start ({:+.3f}, {:+.3f}) yaw {:+.4f} rad -> end '
            '({:+.3f}, {:+.3f}) yaw {:+.4f} rad'.format(
                first[1], first[2], first[3], last[1], last[2], last[3]))
        if args.drive:
            checker.check(
                'the transform moved with the vehicle',
                drove and travel >= _MIN_TRAVEL_M and yaw_swept >= _MIN_YAW_RAD,
                'path {:.3f} m, yaw swept {:.4f} rad ({:.1f} deg)'.format(
                    travel, yaw_swept, math.degrees(yaw_swept)))
        else:
            checker.note('path {:.3f} m, yaw swept {:.4f} rad - no drive '
                         'requested'.format(travel, yaw_swept))

        if len(wheel_samples) >= 2:
            # A second, independent witness that the motion was real: the
            # drive wheel's own angle, out of the physics engine rather
            # than out of the odometry system. The two are NOT expected to
            # agree exactly - the difference IS slip, and it is the error a
            # real wheel odometry would have had to carry and this ground
            # truth does not.
            radius = float(
                yaml.safe_load(open(_CONFIG, encoding='utf-8'))
                ['model']['wheel_radius_m'])
            wheel_travel = abs(wheel_samples[-1][1] - wheel_samples[0][1]) \
                * radius
            checker.note(
                'drive wheel turned {:.3f} rad = {:.3f} m of tread against '
                '{:.3f} m of transform path: the {:+.3f} m difference is '
                'slip, which THIS transform does not carry'.format(
                    abs(wheel_samples[-1][1] - wheel_samples[0][1]),
                    wheel_travel, travel, wheel_travel - travel))

    # ---- residual against the ground-truth odometry topic --------------
    # For every odometry message, ask the tf2 buffer where the vehicle was
    # at that message's own stamp, and difference the two. This is the
    # consumer's code path, not a message-to-message comparison: it goes
    # through the listener, the buffer and its interpolation.
    residuals = []
    misses = 0
    for stamp, x, y, yaw, _parent, _child in odom_samples:
        try:
            tf = buffer_.lookup_transform(
                odom_frame, base_frame,
                Time(seconds=int(stamp), nanoseconds=int(
                    round((stamp - int(stamp)) * 1e9))))
        except Exception:
            misses += 1
            continue
        residuals.append((
            math.hypot(tf.transform.translation.x - x,
                       tf.transform.translation.y - y),
            abs(wrap(yaw_of(tf.transform.rotation.x, tf.transform.rotation.y,
                            tf.transform.rotation.z, tf.transform.rotation.w)
                     - yaw))))
    if residuals:
        max_xy = max(r[0] for r in residuals)
        rms_xy = math.sqrt(sum(r[0] ** 2 for r in residuals) / len(residuals))
        max_yaw = max(r[1] for r in residuals)
        checker.check(
            'the transform agrees with the odometry topic',
            max_xy <= _TOL_RESIDUAL_M and max_yaw <= _TOL_RESIDUAL_RAD,
            '{} paired sample(s), {} outside the buffer: max {:.3e} m, '
            'RMS {:.3e} m, max {:.3e} rad'.format(
                len(residuals), misses, max_xy, rms_xy, max_yaw))
        checker.note(
            'that residual is a TRANSPORT figure, not an odometry-error '
            'figure: both sides are the same simulator pose, one through '
            'the odometry message and one through the transform')
    else:
        checker.check('the transform agrees with the odometry topic', False,
                      'no odometry sample could be paired with a transform')

    node.destroy_node()
    rclpy.shutdown()
    return checker


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Check that odom -> base_link is published by the model, '
                    'bridged onto /tf, resolvable and tracking.')
    parser.add_argument('--live', action='store_true',
                        help='also check a running graph (needs ROS 2)')
    parser.add_argument('--drive', action='store_true',
                        help='drive the vehicle during the live check, so '
                             'the transform is tested against real motion')
    parser.add_argument('--speed', type=float, default=0.5,
                        help='drive speed [m/s] (default: %(default)s)')
    parser.add_argument('--steer', type=float, default=0.30,
                        help='steer angle for the turning leg [rad] '
                             '(default: %(default)s)')
    parser.add_argument('--timeout', type=float, default=30.0,
                        help='seconds to wait for the first transforms '
                             '(default: %(default)s)')
    parser.add_argument('--watch', type=float, default=5.0,
                        help='seconds to observe when not driving '
                             '(default: %(default)s)')
    args = parser.parse_args(argv)

    checker, fields, cfg = check_static(Checker())
    if args.live and fields is not None:
        check_live(checker, fields, cfg, args)
    return checker.summary()


if __name__ == '__main__':
    sys.exit(main())
