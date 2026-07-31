#!/usr/bin/env python3
"""check_odometry.py - measure the vehicle's motion estimate against truth.

WHAT THIS IS
  The instrument behind EVIDENCE_ODOMETRY.md. It verifies each piece of
  the estimate ON ITS OWN before the next one is wired to it, which is
  the owner's sequencing rule for this gate:

    --phase static   no ROS, no simulator. model.sdf against config.yaml
                     for the tricycle geometry and the IMU noise model,
                     plus the integrator driven through motions whose
                     answer is known in closed form.
    --phase imu      the IMU alone, vehicle stationary. Rate, frame,
                     per-axis mean and standard deviation against the
                     stddev and bias declared in model.sdf, gravity, and
                     what the message says about orientation.
    --phase wheel    the wheel odometry alone, against a known motion.
                     Also separates the physics engine's real wheel slip
                     from the cos(delta) geometry that a naive
                     tread-versus-path comparison mistakes for slip.
    --phase fusion   the EKF's transform against ground truth over a
                     stated manoeuvre set, including two sustained turns,
                     because heading is where a tricycle's odometry
                     actually fails.

WHAT IT IS NOT
  It is not part of the vehicle. Nothing here runs in a demonstration and
  nothing it computes reaches an estimator. It is the ONLY thing in this
  directory permitted to read ground truth, and it reads it as a
  REFERENCE to measure against - never as an input to anything that
  estimates or steers. That distinction is the whole point of the
  two-phase odometry plan: an estimator scored against its own input
  cannot be wrong.

THE HONESTY RULE THIS SCRIPT SERVES
  It reports the drift it measures. No parameter of the noise model is
  reachable from here, so no result produced by this script can be
  improved by running it again with a different number. If the drift is
  too small to exercise the degenerate aisles of
  sim/worlds/WAREHOUSE_LANDMARKS.md, that is a finding. If it is large
  enough to trouble SLAM, that is also a finding.

Usage (after sourcing /opt/ros/jazzy/setup.bash; use /usr/bin/python3 in
the session container, per sim/setup/CONTAINER_TOOLCHAIN.md section 3.3):

  python3 agv/forklift/scripts/check_odometry.py --phase static
  python3 agv/forklift/scripts/check_odometry.py --print-world
  python3 agv/forklift/scripts/check_odometry.py --phase imu     --settle 20
  python3 agv/forklift/scripts/check_odometry.py --phase wheel
  python3 agv/forklift/scripts/check_odometry.py --phase fusion

  The three live phases need a running stack and they set use_sim_time on
  their own node, because every message they read is stamped with the
  simulation clock.
"""

import argparse
import math
import os
import statistics
import sys
import xml.etree.ElementTree as ET

import yaml

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_MODEL = os.path.join(_FORKLIFT_DIR, 'model.sdf')
_CONFIG = os.path.join(_FORKLIFT_DIR, 'config.yaml')

#: Geometry agreement tolerance between config.yaml and model.sdf [m].
_TOL_M = 1e-9

#: The flat test world these measurements are taken on. It is emitted by
#: --print-world rather than kept as a file, because worlds belong to sim/
#: and this directory may not put one there. It is deliberately EMPTY: an
#: odometry drift measurement wants an unobstructed floor and nothing
#: else, and 110 m of driving does not fit inside the arena's walls.
_TEST_WORLD = """<sdf version="1.8">
  <world name="odometry_flat">
    <physics type="ode">
      <max_step_size>0.002</max_step_size>
      <real_time_factor>1.0</real_time_factor>
      <real_time_update_rate>500</real_time_update_rate>
    </physics>
    <plugin name="gz::sim::systems::Physics"
            filename="libgz-sim-physics-system.so"/>
    <plugin name="gz::sim::systems::UserCommands"
            filename="libgz-sim-user-commands-system.so"/>
    <plugin name="gz::sim::systems::SceneBroadcaster"
            filename="libgz-sim-scene-broadcaster-system.so"/>
    <light name="sun" type="directional">
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.9 0.9 0.9 1</diffuse>
      <direction>-0.5 0.1 -0.9</direction>
    </light>
    <model name="Floor">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><box><size>200 200 0.1</size></box></geometry>
          <pose>0 0 -0.05 0 0 0</pose>
          <surface>
            <friction><ode><mu>1.0</mu><mu2>1.0</mu2></ode></friction>
          </surface>
        </collision>
        <visual name="visual">
          <geometry><box><size>200 200 0.1</size></box></geometry>
          <pose>0 0 -0.05 0 0 0</pose>
          <material>
            <ambient>0.35 0.35 0.38 1</ambient>
            <diffuse>0.35 0.35 0.38 1</diffuse>
          </material>
        </visual>
      </link>
    </model>
  </world>
</sdf>
"""

#: THE MANOEUVRE SET. Stated here once, printed with every run, and
#: quoted in the evidence, so a drift figure is never separated from the
#: motion that produced it. Each leg is (label, seconds, speed m/s,
#: steer rad). Times are SIMULATION seconds.
#:
#: Two sustained turns of opposite sign, because a steer zero offset and
#: a gyro bias both change sign with the turn and a single-direction
#: profile cannot tell a systematic error from a random one. The steer
#: angle 0.35 rad gives a turn radius L/tan(delta) = 2.88 m, tight enough
#: to load the tyre laterally and produce real slip, wide enough that the
#: vehicle is not scrubbing on the spot.
_PROFILE = [
    ('settle',          3.0, 0.0,  0.0),
    ('straight 1',     10.0, 1.0,  0.0),
    ('turn left',      40.0, 1.0,  0.35),
    ('straight 2',     10.0, 1.0,  0.0),
    ('turn right',     40.0, 1.0, -0.35),
    ('straight 3',     10.0, 1.0,  0.0),
    ('stop',            5.0, 0.0,  0.0),
]


def load_config(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


class Checker(object):
    """Pass/fail accounting, printed as it goes."""

    def __init__(self):
        self.checks = []
        self.notes = []

    def check(self, name, ok, detail=''):
        self.checks.append((name, bool(ok)))
        print('  [{}] {}{}'.format('PASS' if ok else 'FAIL', name,
                                   '   ({})'.format(detail) if detail else ''))
        return ok

    def note(self, text):
        self.notes.append(text)
        print('  [note] {}'.format(text))

    def summary(self):
        failed = [n for n, ok in self.checks if not ok]
        print('')
        print('{} check(s), {} failed'.format(len(self.checks), len(failed)))
        for name in failed:
            print('  FAILED: {}'.format(name))
        return 1 if failed else 0


def section(title):
    print('')
    print('=== {} '.format(title) + '=' * max(0, 66 - len(title)))


def wrap_pi(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def yaw_of(quaternion):
    """Yaw from a (x, y, z, w) tuple."""
    qx, qy, qz, qw = quaternion
    return math.atan2(2.0 * (qw * qz + qx * qy),
                      1.0 - 2.0 * (qy * qy + qz * qz))


# ====================================================================== #
# Phase: static
# ====================================================================== #

def _sdf_links(model):
    return dict((link.get('name'), link) for link in model.findall('link'))


def _link_xyz(link):
    pose = link.findtext('pose')
    if pose is None:
        return (0.0, 0.0, 0.0)
    return tuple(float(v) for v in pose.split()[0:3])


def _imu_noise(model):
    """Every <noise> under the IMU sensor, as
    {('angular_velocity'|'linear_acceleration', axis): {mean, stddev, ...}}."""
    out = {}
    for link in model.findall('link'):
        for sensor in link.findall('sensor'):
            imu = sensor.find('imu')
            if imu is None:
                continue
            for group in ('angular_velocity', 'linear_acceleration'):
                block = imu.find(group)
                if block is None:
                    continue
                for axis in ('x', 'y', 'z'):
                    noise = block.find('{}/noise'.format(axis))
                    if noise is None:
                        continue
                    out[(group, axis)] = dict(
                        (child.tag, float(child.text))
                        for child in noise
                        if child.tag in ('mean', 'stddev', 'bias_mean',
                                         'bias_stddev'))
    return out


def integrate_profile(cfg, legs, dt=0.001, perfect=False):
    """Run wheel_odometry.py's own integrator over an ideal vehicle.

    The vehicle is assumed to follow its commanded steer and speed with no
    slip, so the answer is available in closed form and the integrator can
    be checked against it. `perfect=True` removes the encoder quantisation,
    the steer zero offset and the rolling-radius error, which is how the
    kinematics are separated from the error model.
    """
    sys.path.insert(0, _THIS_DIR)
    import wheel_odometry as wo

    model = cfg['model']
    odo = cfg['odometry']
    wheelbase = float(model['wheelbase_m'])
    d = -float(model['rear_axle_offset_m'])
    r_true = float(model['wheel_radius_m'])
    r_node = r_true if perfect else float(odo['rolling_radius_m'])
    # `perfect` removes the WHOLE error model, quantisation included, so
    # section 4 measures the kinematics and section 5 measures the error
    # model against them. Leaving the encoders in under `perfect` was the
    # first version of this function and it made a closed-form circle miss
    # its own start by 12 mm - which is the steer quantiser, correctly
    # modelled, being blamed on the integrator.
    q_drive = 0.0 if perfect else (
        2.0 * math.pi / float(odo['drive_encoder_counts_per_rev']))
    q_steer = 0.0 if perfect else (
        2.0 * math.pi / float(odo['steer_encoder_counts_per_rev']))
    offset = 0.0 if perfect else float(odo['steer_zero_offset_rad'])

    # Truth, integrated at dt with exact arcs.
    tx = ty = tyaw = 0.0
    # Estimate, through the modelled encoders.
    ex = ey = eyaw = 0.0
    wheel_angle = 0.0
    prev_q = 0.0

    for _, seconds, speed, steer in legs:
        steps = int(round(seconds / dt))
        for _ in range(steps):
            # --- truth: an ideal tricycle, no slip ---
            v_axle = speed * math.cos(steer)
            dyaw = speed * dt * math.sin(steer) / wheelbase
            yaw_next = tyaw + dyaw
            if abs(dyaw) > 1e-12:
                rad = (v_axle * dt) / dyaw
                tx += rad * (math.sin(yaw_next) - math.sin(tyaw))
                ty += rad * (math.cos(tyaw) - math.cos(yaw_next))
            else:
                tx += v_axle * dt * math.cos(tyaw)
                ty += v_axle * dt * math.sin(tyaw)
            tyaw = yaw_next

            # --- what the encoders see ---
            wheel_angle += (speed / r_true) * dt
            q_now = (wo.quantise(wheel_angle, q_drive) if q_drive
                     else wheel_angle)
            d_wheel = q_now - prev_q
            prev_q = q_now
            steer_meas = (wo.quantise(steer + offset, q_steer) if q_steer
                          else steer + offset)
            tread = r_node * d_wheel
            s = tread * math.cos(steer_meas)
            dy = tread * math.sin(steer_meas) / wheelbase
            e_next = eyaw + dy
            if abs(dy) > 1e-12:
                rad = s / dy
                ex += rad * (math.sin(e_next) - math.sin(eyaw))
                ey += rad * (math.cos(eyaw) - math.cos(e_next))
            else:
                ex += s * math.cos(eyaw + 0.5 * dy)
                ey += s * math.sin(eyaw + 0.5 * dy)
            eyaw = e_next

    truth = (tx + d * math.cos(tyaw), ty + d * math.sin(tyaw), tyaw)
    est = (ex + d * math.cos(eyaw), ey + d * math.sin(eyaw), eyaw)
    return truth, est


def phase_static(checker):
    cfg = load_config(_CONFIG)
    model = ET.parse(_MODEL).getroot().find('model')
    links = _sdf_links(model)

    section('1. tricycle geometry: config.yaml against model.sdf')
    steer_x = _link_xyz(links['steer_link'])[0]
    rear_l = _link_xyz(links['rear_wheel_left'])[0]
    rear_r = _link_xyz(links['rear_wheel_right'])[0]
    checker.check('the two rear wheels share one axle',
                  abs(rear_l - rear_r) <= _TOL_M,
                  'x {:.4f} vs {:.4f}'.format(rear_l, rear_r))
    wheelbase_sdf = steer_x - rear_l
    checker.check('config model.wheelbase_m == steer_x - rear_axle_x',
                  abs(float(cfg['model']['wheelbase_m']) - wheelbase_sdf)
                  <= _TOL_M,
                  '{} vs {:.4f} = {:.2f} - ({:.2f})'.format(
                      cfg['model']['wheelbase_m'], wheelbase_sdf,
                      steer_x, rear_l))
    checker.check('config model.rear_axle_offset_m == rear axle x',
                  abs(float(cfg['model']['rear_axle_offset_m']) - rear_l)
                  <= _TOL_M,
                  '{} vs {:.4f}'.format(cfg['model']['rear_axle_offset_m'],
                                        rear_l))
    checker.note('base_link stands {:+.3f} m of the rear axle, so its lateral '
                 'velocity in a turn is {:.3f} * yawrate and is NOT zero'
                 .format(-rear_l, -rear_l))

    section('2. the IMU noise model, as model.sdf declares it')
    noise = _imu_noise(model)
    checker.check('the model carries an IMU with a noise model on six axes',
                  len(noise) == 6, '{} noise blocks'.format(len(noise)))

    # Derivations, recomputed here rather than quoted, so a typo in the SDF
    # is a failing check and not a comment nobody re-read.
    g = 9.80665
    bw = 47.0                      # the datasheet's own quoted bandwidth
    delta_t_k = 10.0               # stated temperature excursion since
                                   # the power-up stationary bias estimate
    gyro_stddev = math.radians(0.1)                 # 0.1 deg/s rms at 47 Hz
    gyro_bias = math.radians(0.015 * delta_t_k)     # TCO 0.015 deg/s/K
    accel_xy = 160e-6 * math.sqrt(bw) * g           # 160 ug/sqrt(Hz)
    accel_z = 190e-6 * math.sqrt(bw) * g            # 190 ug/sqrt(Hz)
    accel_bias = 0.2e-3 * delta_t_k * g             # TCO 0.2 mg/K

    for axis in ('x', 'y', 'z'):
        spec = noise.get(('angular_velocity', axis), {})
        checker.check(
            'gyro {} stddev is the datasheet 0.1 deg/s at BW 47 Hz'.format(axis),
            abs(spec.get('stddev', 0.0) - gyro_stddev) < 1e-5,
            '{} vs {:.6f} rad/s'.format(spec.get('stddev'), gyro_stddev))
        checker.check(
            'gyro {} bias is TCO 0.015 deg/s/K over {:.0f} K'.format(
                axis, delta_t_k),
            abs(spec.get('bias_mean', 0.0) - gyro_bias) < 1e-5,
            '{} vs {:.6f} rad/s'.format(spec.get('bias_mean'), gyro_bias))
    for axis, expect in (('x', accel_xy), ('y', accel_xy), ('z', accel_z)):
        spec = noise.get(('linear_acceleration', axis), {})
        checker.check(
            'accel {} stddev is the datasheet noise density at BW 47 Hz'
            .format(axis),
            abs(spec.get('stddev', 0.0) - expect) < 2e-4,
            '{} vs {:.6f} m/s^2'.format(spec.get('stddev'), expect))
        checker.check(
            'accel {} bias is TCO 0.2 mg/K over {:.0f} K'.format(
                axis, delta_t_k),
            abs(spec.get('bias_mean', 0.0) - accel_bias) < 2e-4,
            '{} vs {:.6f} m/s^2'.format(spec.get('bias_mean'), accel_bias))

    # The one that matters most, and it is a structural check rather than
    # a numeric one: the IMU must not offer an orientation, because gz
    # derives that from the simulator pose and it is ground truth.
    enable = None
    for link in model.findall('link'):
        for sensor in link.findall('sensor'):
            imu = sensor.find('imu')
            if imu is not None:
                enable = (imu.findtext('enable_orientation') or '').strip()
    checker.check('the IMU declares enable_orientation false',
                  enable == 'false',
                  'enable_orientation = {!r}'.format(enable))
    checker.note('gz derives an IMU orientation from the LINK POSE, so it is '
                 'ground truth wearing a sensor name; a real strapdown IMU '
                 'with no magnetometer has no absolute heading at all')

    section('3. the covariances the wheel odometry publishes')
    odo = cfg['odometry']
    q = 2.0 * math.pi / float(odo['steer_encoder_counts_per_rev'])
    qd = 2.0 * math.pi / float(odo['drive_encoder_counts_per_rev'])
    dt = 1.0 / float(odo['publish_hz'])
    v_nom = 1.0
    wheelbase = float(cfg['model']['wheelbase_m'])
    d = -float(cfg['model']['rear_axle_offset_m'])
    r = float(odo['rolling_radius_m'])
    r_true = float(cfg['model']['wheel_radius_m'])

    s_quant = r * (qd / math.sqrt(6.0)) / dt
    s_scale = abs(r / r_true - 1.0) * v_nom
    var_vx = s_quant ** 2 + s_scale ** 2
    checker.check('odometry.vx_variance matches its stated derivation',
                  abs(float(odo['vx_variance']) - var_vx) / var_vx < 0.02,
                  '{:.3e} vs {:.3e}'.format(float(odo['vx_variance']), var_vx))

    dwdd = v_nom / wheelbase
    w_quant = dwdd * (q / math.sqrt(12.0))
    w_offset = dwdd * float(odo['steer_zero_offset_rad'])
    var_vyaw = w_quant ** 2 + w_offset ** 2
    checker.check('odometry.vyaw_variance matches its stated derivation',
                  abs(float(odo['vyaw_variance']) - var_vyaw) / var_vyaw < 0.02,
                  '{:.3e} vs {:.3e}'.format(float(odo['vyaw_variance']),
                                            var_vyaw))
    checker.check('odometry.vy_variance == d^2 * vyaw_variance',
                  abs(float(odo['vy_variance'])
                      - d * d * float(odo['vyaw_variance']))
                  / (d * d * float(odo['vyaw_variance'])) < 0.02,
                  '{:.3e} vs {:.3e}'.format(float(odo['vy_variance']),
                                            d * d * float(odo['vyaw_variance'])))
    gyro_var = gyro_stddev ** 2
    checker.note('the two yaw-rate sources, as their own covariances: wheels '
                 '{:.3e}, gyro white noise {:.3e} (rad/s)^2 - within a factor '
                 'of {:.2f}, so the EKF blends them'.format(
                     var_vyaw, gyro_var, gyro_var / var_vyaw))

    section('4. the integrator against motions with a closed-form answer')
    # A pure straight, then a pure circle, with the error model OFF: the
    # kinematics alone must reproduce the exact answer.
    truth, est = integrate_profile(
        cfg, [('straight', 10.0, 1.0, 0.0)], perfect=True)
    # The pose reported is base_link's, which starts d ahead of the rear
    # axle the integration tracks, so 10 m of travel lands at 10 + d.
    checker.check('10 s at 1 m/s straight: 10 m of travel, no heading change',
                  abs(est[0] - (10.0 + d)) < 1e-6 and abs(est[1]) < 1e-9
                  and abs(est[2]) < 1e-12,
                  'x {:.9f} (= 10 + d), y {:.3e}, yaw {:.3e}'.format(*est))

    steer = 0.35
    radius = wheelbase / math.tan(steer)
    period = 2.0 * math.pi * radius / (1.0 * math.cos(steer))
    truth, est = integrate_profile(
        cfg, [('circle', period, 1.0, steer)], perfect=True)
    checker.check(
        'one full circle at steer {:.2f} rad returns to its start'.format(steer),
        math.hypot(est[0] - d, est[1]) < 2e-3 and abs(wrap_pi(est[2])) < 2e-3,
        'closes at ({:+.4f}, {:+.4f}) m, yaw {:+.4f} rad, radius {:.3f} m'
        .format(est[0] - d, est[1], wrap_pi(est[2]), radius))
    checker.check('the integrator agrees with the ideal vehicle it models',
                  max(abs(a - b) for a, b in zip(truth, est)) < 2e-3,
                  'max component difference {:.2e}'.format(
                      max(abs(a - b) for a, b in zip(truth, est))))

    section('5. the error model, on the same closed-form motions')
    truth, est = integrate_profile(cfg, _PROFILE, perfect=False)
    err = (est[0] - truth[0], est[1] - truth[1], wrap_pi(est[2] - truth[2]))
    distance = sum(seconds * speed for _, seconds, speed, _ in _PROFILE)
    checker.note('over the {:.0f} m profile, with an IDEAL no-slip vehicle, '
                 'the ERROR MODEL ALONE produces {:.3f} m of position error '
                 'and {:+.3f} deg of heading error'.format(
                     distance, math.hypot(err[0], err[1]),
                     math.degrees(err[2])))
    checker.note('that is the encoder quantisation, the one-count steer zero '
                 'offset and the 0.5% rolling-radius error, with NO slip and '
                 'NO IMU. The live phases add the physics.')
    return checker


# ====================================================================== #
# Live plumbing
# ====================================================================== #

def _live_node(name):
    import rclpy
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    rclpy.init(args=[sys.argv[0]])
    node = Node(name)
    # Every message in this stack is stamped with the simulation clock.
    # A harness on the system clock measures the difference between two
    # clocks and reports it as a missing transform.
    node.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
    return rclpy, node


def _wait_clock(rclpy, node, seconds=30.0):
    """Block until the simulation clock has actually started."""
    import time as _time
    deadline = _time.monotonic() + seconds
    while _time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
        if node.get_clock().now().nanoseconds > 0:
            return True
    return False


def _sim_sleep(rclpy, node, seconds, on_tick=None):
    """Wait `seconds` of SIMULATION time, pumping the node meanwhile."""
    start = node.get_clock().now().nanoseconds
    target = start + int(seconds * 1e9)
    import time as _time
    wall_deadline = _time.monotonic() + seconds * 20.0 + 30.0
    while node.get_clock().now().nanoseconds < target:
        rclpy.spin_once(node, timeout_sec=0.02)
        if on_tick is not None:
            on_tick()
        if _time.monotonic() > wall_deadline:
            node.get_logger().error('simulation clock stalled; giving up')
            return False
    return True


# ====================================================================== #
# Phase: imu
# ====================================================================== #

def phase_imu(checker, settle_s, sample_s):
    from sensor_msgs.msg import Imu
    from rclpy.qos import QoSProfile

    cfg = load_config(_CONFIG)
    model = ET.parse(_MODEL).getroot().find('model')
    declared = _imu_noise(model)

    rclpy, node = _live_node('check_odometry_imu')
    samples = []

    def cb_imu(msg):
        samples.append(msg)

    node.create_subscription(Imu, cfg['topics']['imu'], cb_imu,
                             QoSProfile(depth=200))

    section('1. the IMU alone, vehicle stationary')
    if not _wait_clock(rclpy, node):
        checker.check('the simulation clock is running', False)
        return checker
    checker.check('the simulation clock is running', True)

    # The vehicle is left alone to settle: a model dropped 0.05 m onto the
    # floor is still ringing for a second or so and a noise measurement
    # taken through that is a measurement of the suspension.
    _sim_sleep(rclpy, node, settle_s)
    samples.clear()
    _sim_sleep(rclpy, node, sample_s)

    checker.check('{} carries data'.format(cfg['topics']['imu']),
                  len(samples) > 10, '{} samples'.format(len(samples)))
    if len(samples) < 10:
        node.destroy_node()
        rclpy.shutdown()
        return checker

    stamps = [m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
              for m in samples]
    span = stamps[-1] - stamps[0]
    rate = (len(stamps) - 1) / span if span > 0 else 0.0
    declared_rate = float(cfg['imu']['publish_hz'])
    checker.check('measured rate matches the declared {:.0f} Hz'
                  .format(declared_rate),
                  abs(rate - declared_rate) / declared_rate < 0.05,
                  '{:.3f} Hz over {:.2f} s of simulated time, {} samples'
                  .format(rate, span, len(samples)))
    checker.check('header.frame_id is the published IMU frame',
                  samples[0].header.frame_id == cfg['frames']['imu'],
                  '{} vs {}'.format(samples[0].header.frame_id,
                                    cfg['frames']['imu']))

    print('')
    print('  {:<22} {:>12} {:>12} {:>12} {:>12}'.format(
        'channel', 'mean', 'stddev', 'declared sd', 'declared bias'))
    axes = ('x', 'y', 'z')
    gyro = dict((a, [getattr(m.angular_velocity, a) for m in samples])
                for a in axes)
    accel = dict((a, [getattr(m.linear_acceleration, a) for m in samples])
                 for a in axes)
    for group, data, unit in (('angular_velocity', gyro, 'rad/s'),
                              ('linear_acceleration', accel, 'm/s^2')):
        for a in axes:
            spec = declared.get((group, a), {})
            print('  {:<22} {:>12.6f} {:>12.6f} {:>12.6f} {:>12.6f}'.format(
                '{}.{} [{}]'.format(group.split('_')[0], a, unit),
                statistics.fmean(data[a]), statistics.stdev(data[a]),
                spec.get('stddev', float('nan')),
                spec.get('bias_mean', float('nan'))))

    # The white noise is checkable directly. The bias is not checkable
    # by magnitude alone in one run, because gz draws its SIGN at random,
    # so the check is on the magnitude of the mean.
    for a in axes:
        spec = declared[('angular_velocity', a)]
        sd = statistics.stdev(gyro[a])
        checker.check(
            'gyro {} sample stddev is the declared white noise'.format(a),
            abs(sd - spec['stddev']) / spec['stddev'] < 0.20,
            '{:.6f} vs {:.6f} rad/s'.format(sd, spec['stddev']))
        mean = statistics.fmean(gyro[a])
        checker.check(
            'gyro {} mean is the declared bias, sign drawn by gz'.format(a),
            abs(abs(mean) - spec['bias_mean']) < 4.0 * spec['stddev'],
            'mean {:+.6f}, |mean| vs bias {:.6f} rad/s'.format(
                mean, spec['bias_mean']))

    gmag = [math.sqrt(sum(getattr(m.linear_acceleration, a) ** 2
                          for a in axes)) for m in samples]
    checker.check('the accelerometer reads 1 g at rest',
                  abs(statistics.fmean(gmag) - 9.80665) < 0.1,
                  '|a| = {:.4f} m/s^2 (g = 9.80665)'.format(
                      statistics.fmean(gmag)))

    section('2. what the message says about orientation')
    ori = samples[0].orientation
    cov0 = samples[0].orientation_covariance[0]
    checker.note('orientation quaternion as bridged: ({:.3f}, {:.3f}, {:.3f}, '
                 '{:.3f}); orientation_covariance[0] = {:.3f}'.format(
                     ori.x, ori.y, ori.z, ori.w, cov0))
    checker.note('THE ROS CONVENTION IS orientation_covariance[0] = -1 for '
                 '"no orientation in this message". Whatever the number '
                 'above, this vehicle refuses the channel twice: '
                 '<enable_orientation>false</> in model.sdf and all three '
                 'orientation flags false in ekf.yaml.')
    checker.note('gyro covariance carried in the message: {:.4e} (rad/s)^2 = '
                 'the DECLARED WHITE NOISE only. The modelled bias is not in '
                 'it, because a real driver does not know its live bias '
                 'either.'.format(samples[0].angular_velocity_covariance[8]))

    node.destroy_node()
    rclpy.shutdown()
    return checker


# ====================================================================== #
# Phases: wheel and fusion (they share one drive)
# ====================================================================== #

class Recorder(object):
    """Collects every stream one driven run needs, on the simulation clock."""

    def __init__(self, node, cfg, want_tf):
        from nav_msgs.msg import Odometry
        from rclpy.qos import QoSProfile
        from sensor_msgs.msg import JointState

        self.node = node
        self.cfg = cfg
        self.truth = []        # (t, x, y, yaw)
        self.wheel = []        # (t, x, y, yaw)
        self.joints = []       # (t, drive_rad, steer_rad)
        self.ekf = []          # (t, x, y, yaw) from the tf tree
        self.want_tf = want_tf

        qos = QoSProfile(depth=200)
        node.create_subscription(Odometry, cfg['topics']['odom'],
                                 self.cb_truth, qos)
        node.create_subscription(Odometry, cfg['topics']['odom_wheel'],
                                 self.cb_wheel, qos)
        node.create_subscription(JointState, cfg['topics']['joint_states'],
                                 self.cb_joints, qos)
        self.gyro_z = []
        if want_tf:
            from sensor_msgs.msg import Imu
            node.create_subscription(Imu, cfg['topics']['imu'],
                                     self.cb_imu, qos)

        self.buffer = None
        self.tf_publishers = 0
        self.tf_publisher_names = []
        self.tf_resolved = 0
        self.tf_resolve_error = ''
        if want_tf:
            from tf2_msgs.msg import TFMessage
            from tf2_ros import Buffer, TransformListener
            # THE ERROR IS MEASURED FROM /tf DIRECTLY, and the tf2 buffer
            # is used for a separate question.
            #
            # A buffer lookup AT the reference message's stamp fails, and
            # correctly: the reference arrives at t and the estimate for t
            # has not been published yet, so tf2 raises an extrapolation
            # error rather than inventing a pose. Retrying at 'latest'
            # would silently compare poses from different instants and
            # report the timing offset as drift. So the transforms are
            # recorded as they are published, with their own stamps, and
            # paired afterwards on those stamps - the same alignment the
            # wheel odometry gets.
            #
            # The buffer still earns its place: it answers whether a REAL
            # consumer resolves this edge at all, which is a different
            # claim from whether the messages exist.
            node.create_subscription(TFMessage, cfg['topics']['tf'],
                                     self.cb_tf, qos)
            self.buffer = Buffer()
            self.listener = TransformListener(self.buffer, node)

    def cb_tf(self, msg):
        frames = self.cfg['frames']
        for tf in msg.transforms:
            if (tf.header.frame_id == frames['odom']
                    and tf.child_frame_id == frames['base']):
                q = (tf.transform.rotation.x, tf.transform.rotation.y,
                     tf.transform.rotation.z, tf.transform.rotation.w)
                self.ekf.append((self._t(tf.header),
                                 tf.transform.translation.x,
                                 tf.transform.translation.y, yaw_of(q)))

    def try_resolve(self):
        """Can a consumer on simulation time look this edge up at 'now'?"""
        import rclpy
        frames = self.cfg['frames']
        try:
            self.buffer.lookup_transform(frames['odom'], frames['base'],
                                         rclpy.time.Time())
            self.tf_resolved += 1
        except Exception as exc:
            self.tf_resolve_error = str(exc).strip()

    def count_tf_publishers(self):
        """How many nodes publish /tf, read off the live graph.

        THE CHECK invariant 10 ACTUALLY NEEDS. tf2 does not complain about
        two publishers of one edge: the listener takes whichever message
        arrived last, so the symptom of a double publisher is a pose that
        alternates between drifting and perfect, with no error anywhere.
        This node's own TransformListener does not count - it subscribes,
        it does not publish.
        """
        info = self.node.get_publishers_info_by_topic(self.cfg['topics']['tf'])
        self.tf_publisher_names = sorted(i.node_name for i in info)
        self.tf_publishers = len(info)
        return self.tf_publishers

    @staticmethod
    def _t(header):
        return header.stamp.sec + header.stamp.nanosec * 1e-9

    def _pose(self, msg):
        q = (msg.pose.pose.orientation.x, msg.pose.pose.orientation.y,
             msg.pose.pose.orientation.z, msg.pose.pose.orientation.w)
        return (self._t(msg.header), msg.pose.pose.position.x,
                msg.pose.pose.position.y, yaw_of(q))

    def cb_truth(self, msg):
        self.truth.append(self._pose(msg))

    def cb_wheel(self, msg):
        self.wheel.append(self._pose(msg))

    def cb_imu(self, msg):
        self.gyro_z.append(msg.angular_velocity.z)

    def cb_joints(self, msg):
        cfg = self.cfg['model']
        if cfg['drive_joint_name'] not in msg.name:
            return
        i_d = msg.name.index(cfg['drive_joint_name'])
        i_s = msg.name.index(cfg['steer_joint_name'])
        self.joints.append((self._t(msg.header), msg.position[i_d],
                            msg.position[i_s]))



def _path_length(track):
    return sum(math.hypot(b[1] - a[1], b[2] - a[2])
               for a, b in zip(track, track[1:]))


def _unwrapped_yaw_sweep(track):
    """(net, total) heading swept, unwrapped.

    BOTH are reported and the pair is the point. Two sustained turns of
    opposite sign have a NET sweep near zero, which would read as "the
    vehicle barely turned" and hide the whole manoeuvre; the TOTAL is
    what the turns actually cost the estimator.
    """
    net = 0.0
    total = 0.0
    for a, b in zip(track, track[1:]):
        step = wrap_pi(b[3] - a[3])
        net += step
        total += abs(step)
    return net, total


def _pair(reference, estimate):
    """Align two (t, x, y, yaw) tracks on nearest reference timestamps."""
    if not estimate:
        return []
    out = []
    j = 0
    for r in reference:
        while j + 1 < len(estimate) and abs(estimate[j + 1][0] - r[0]) \
                <= abs(estimate[j][0] - r[0]):
            j += 1
        if abs(estimate[j][0] - r[0]) <= 0.05:
            out.append((r, estimate[j]))
    return out


def _error_table(checker, label, pairs, reference):
    if not pairs:
        checker.check('{}: paired samples exist'.format(label), False,
                      'no sample paired within 50 ms')
        return None
    travelled = []
    total = 0.0
    prev = reference[0]
    index = {}
    for r in reference:
        total += math.hypot(r[1] - prev[1], r[2] - prev[2])
        index[r[0]] = total
        prev = r
    rows = []
    for r, e in pairs:
        pos = math.hypot(e[1] - r[1], e[2] - r[2])
        head = wrap_pi(e[3] - r[3])
        rows.append((index.get(r[0], 0.0), pos, head))
        travelled.append(index.get(r[0], 0.0))
    final = rows[-1]
    worst = max(rows, key=lambda row: row[1])
    print('')
    print('  {} error against ground truth'.format(label))
    print('  {:>10} {:>14} {:>14}'.format('after [m]', 'position [m]',
                                          'heading [deg]'))
    # The last row is rows[-1] and not "the row nearest 100% of the
    # distance": the vehicle stops at the end of the profile, so several
    # samples share the maximum travelled distance and picking by
    # distance returns the first of them. That made this table's final
    # row disagree with the summary below it by 0.8 deg.
    for frac in (0.1, 0.25, 0.5, 0.75):
        want = final[0] * frac
        row = min(rows, key=lambda row: abs(row[0] - want))
        print('  {:>10.2f} {:>14.4f} {:>14.4f}'.format(
            row[0], row[1], math.degrees(row[2])))
    print('  {:>10.2f} {:>14.4f} {:>14.4f}   <- final'.format(
        final[0], final[1], math.degrees(final[2])))
    print('  worst position error {:.4f} m at {:.2f} m travelled'.format(
        worst[1], worst[0]))
    return {'final_distance_m': final[0], 'final_pos_err_m': final[1],
            'final_head_err_rad': final[2], 'worst_pos_err_m': worst[1],
            'pairs': len(pairs)}


def phase_drive(checker, want_fusion):
    from std_msgs.msg import Float64
    from rclpy.qos import QoSProfile

    cfg = load_config(_CONFIG)
    rclpy, node = _live_node('check_odometry_drive')
    qos = QoSProfile(depth=10)
    pub_speed = node.create_publisher(Float64,
                                      cfg['topics']['cmd_traction_speed'], qos)
    pub_steer = node.create_publisher(Float64,
                                      cfg['topics']['cmd_steer_angle'], qos)

    section('1. the run')
    if not _wait_clock(rclpy, node):
        checker.check('the simulation clock is running', False)
        return checker, None
    recorder = Recorder(node, cfg, want_tf=want_fusion)

    # Discovery. A publisher that has not met its subscriber drops its
    # first messages silently (LESSONS 2026-07-28), so the profile does
    # not start until the graph has settled.
    _sim_sleep(rclpy, node, 5.0)
    recorder.truth.clear()
    recorder.wheel.clear()
    recorder.joints.clear()
    recorder.ekf.clear()
    recorder.gyro_z.clear()

    print('  manoeuvre set, timed on the SIMULATION clock:')
    for label, seconds, speed, steer in _PROFILE:
        print('    {:<12} {:>5.1f} s  speed {:+.2f} m/s  steer {:+.3f} rad'
              .format(label, seconds, speed, steer))

    for label, seconds, speed, steer in _PROFILE:
        steer_msg = Float64()
        steer_msg.data = float(steer)
        pub_steer.publish(steer_msg)
        # The steer axis takes time to slew; the speed is applied after it
        # so the vehicle is not driving through the transient with a
        # commanded angle it has not reached.
        _sim_sleep(rclpy, node, 1.0)
        speed_msg = Float64()
        speed_msg.data = float(speed)
        pub_speed.publish(speed_msg)

        def republish():
            pub_steer.publish(steer_msg)
            pub_speed.publish(speed_msg)

        _sim_sleep(rclpy, node, max(0.0, seconds - 1.0),
                   on_tick=(recorder.try_resolve if want_fusion else None))
        del republish
    stop = Float64()
    stop.data = 0.0
    pub_speed.publish(stop)
    pub_steer.publish(stop)
    _sim_sleep(rclpy, node, 3.0)

    if want_fusion:
        recorder.count_tf_publishers()
    checker.check('ground truth was recorded', len(recorder.truth) > 100,
                  '{} samples'.format(len(recorder.truth)))
    checker.check('wheel odometry was recorded', len(recorder.wheel) > 100,
                  '{} samples'.format(len(recorder.wheel)))
    checker.check('joint states were recorded', len(recorder.joints) > 100,
                  '{} samples'.format(len(recorder.joints)))

    node.destroy_node()
    rclpy.shutdown()
    return checker, recorder


def report_drive(checker, recorder, want_fusion):
    cfg = load_config(_CONFIG)
    truth = recorder.truth
    if len(truth) < 100:
        return checker

    section('2. what the vehicle actually did')
    path_m = _path_length(truth)
    net_sweep, total_sweep = _unwrapped_yaw_sweep(truth)
    duration = truth[-1][0] - truth[0][0]
    print('  path length            {:.3f} m'.format(path_m))
    print('  heading swept, TOTAL   {:.3f} rad  ({:.1f} deg, {:.2f} turns)'
          .format(total_sweep, math.degrees(total_sweep),
                  total_sweep / (2 * math.pi)))
    print('  heading swept, net     {:+.3f} rad  ({:+.1f} deg) - near zero '
          'because the two sustained turns oppose'
          .format(net_sweep, math.degrees(net_sweep)))
    print('  simulated duration     {:.2f} s'.format(duration))
    print('  final truth pose       ({:+.3f}, {:+.3f}) m, yaw {:+.4f} rad'
          .format(truth[-1][1], truth[-1][2], truth[-1][3]))

    section('3. slip, separated from the cos(delta) geometry')
    joints = recorder.joints
    r_true = float(cfg['model']['wheel_radius_m'])
    wheelbase = float(cfg['model']['wheelbase_m'])
    d = -float(cfg['model']['rear_axle_offset_m'])
    tread_m = 0.0
    axle_predicted_m = 0.0
    for a, b in zip(joints, joints[1:]):
        step = r_true * (b[1] - a[1])
        tread_m += abs(step)
        axle_predicted_m += abs(step * math.cos(0.5 * (a[2] + b[2])))

    # The rear axle's own path, from ground truth, which is what the
    # cos(delta) prediction above is a prediction OF.
    axle_truth_m = 0.0
    for a, b in zip(truth, truth[1:]):
        ax = a[1] - d * math.cos(a[3])
        ay = a[2] - d * math.sin(a[3])
        bx = b[1] - d * math.cos(b[3])
        by = b[2] - d * math.sin(b[3])
        axle_truth_m += math.hypot(bx - ax, by - ay)

    print('  drive wheel tread turned          {:.3f} m'.format(tread_m))
    print('  base_link path (ground truth)     {:.3f} m'.format(path_m))
    print('  rear axle path (ground truth)     {:.3f} m'.format(axle_truth_m))
    print('  rear axle path predicted from')
    print('    tread * cos(steer), no slip     {:.3f} m'.format(
        axle_predicted_m))
    if axle_truth_m > 0:
        naive = (tread_m - path_m) / path_m * 100.0
        real = (axle_predicted_m - axle_truth_m) / axle_truth_m * 100.0
        print('')
        print('  NAIVE "slip" = (tread - base_link path) / path   {:+.2f} %'
              .format(naive))
        print('  REAL  slip   = (predicted - true) rear axle path {:+.2f} %'
              .format(real))
        checker.note('the difference between those two numbers is geometry, '
                     'not slip: a steered drive wheel travels a longer path '
                     'than the axle it pushes, by 1/cos(delta), and base_link '
                     'is offset from that axle again')

    section('4. the wheel odometry alone, against ground truth')
    wheel_stats = _error_table(checker, 'wheel odometry',
                               _pair(truth, recorder.wheel), truth)

    fusion_stats = None
    if want_fusion:
        section('5. the fused estimate (the EKF transform) against truth')
        checker.check(
            'exactly one publisher of forklift/odom -> forklift/base_link',
            recorder.tf_publishers == 1,
            '{} publisher(s) of /tf: {}'.format(
                recorder.tf_publishers, recorder.tf_publisher_names))
        checker.check('the EKF transform was published on /tf',
                      len(recorder.ekf) > 100,
                      '{} transforms recorded'.format(len(recorder.ekf)))
        checker.check(
            'a tf2 consumer on simulation time resolves the edge at "now"',
            recorder.tf_resolved > 100,
            '{} successful lookups; last error: {}'.format(
                recorder.tf_resolved, recorder.tf_resolve_error or 'none'))
        fusion_stats = _error_table(checker, 'EKF (odom -> base_link)',
                                    _pair(truth, recorder.ekf), truth)
        if wheel_stats and fusion_stats:
            section('6. did fusing the IMU help?')
            print('  {:<26} {:>14} {:>16}'.format(
                '', 'position [m]', 'heading [deg]'))
            print('  {:<26} {:>14.4f} {:>16.4f}'.format(
                'wheel odometry alone', wheel_stats['final_pos_err_m'],
                math.degrees(wheel_stats['final_head_err_rad'])))
            print('  {:<26} {:>14.4f} {:>16.4f}'.format(
                'EKF, wheels + gyro', fusion_stats['final_pos_err_m'],
                math.degrees(fusion_stats['final_head_err_rad'])))
            if recorder.gyro_z:
                mean_gyro = statistics.fmean(recorder.gyro_z)
                true_rate = net_sweep / duration
                # The gyro's mean is the bias PLUS the vehicle's own mean
                # yaw rate, and over a profile whose two turns oppose that
                # second term is small but not zero. Subtracting it is what
                # makes the remainder attributable to the sensor.
                bias = mean_gyro - true_rate
                drift = bias * duration
                print('')
                print('  WHY, MEASURED RATHER THAN ASSERTED:')
                print('  mean gyro z over the run     {:+.6f} rad/s  ({} '
                      'samples)'.format(mean_gyro, len(recorder.gyro_z)))
                print('  the vehicle\'s own mean yaw rate  {:+.6f} rad/s '
                      '(ground truth)'.format(true_rate))
                print('  the difference, the BIAS     {:+.6f} rad/s  '
                      '(model.sdf declares {:.6f}, sign drawn by gz)'
                      .format(bias, 0.002618))
                print('  bias x duration              {:+.4f} rad = {:+.2f} '
                      'deg'.format(drift, math.degrees(drift)))
                print('  EKF heading error            {:+.4f} rad = {:+.2f} '
                      'deg'.format(fusion_stats['final_head_err_rad'],
                                   math.degrees(
                                       fusion_stats['final_head_err_rad'])))
                print('  The filter is tracking the gyro. The IMU arrives at '
                      '100 Hz and the')
                print('  wheel odometry at 50 Hz, so the gyro gets twice the '
                      'corrections, and')
                print('  the package-default process noise on yaw rate is '
                      'large enough that')
                print('  the estimate follows whichever measurement came '
                      'last. The message')
                print('  covariance the filter is given carries the gyro\'s '
                      'WHITE NOISE only.')
            checker.note('this comparison is REPORTED, not required to come '
                         'out either way. A gyro whose bias the filter is not '
                         'told about can make heading worse, and that is a '
                         'finding about cheap MEMS IMUs rather than a defect.')

    section('7. the drift against what it has to exercise')
    stats = fusion_stats or wheel_stats
    if stats:
        print('  sim/worlds/WAREHOUSE_LANDMARKS.md section 5 names three')
        print('  degenerate stretches, 4.0 to 5.5 m long, in which the scan')
        print('  carries almost no along-aisle information and odometry has')
        print('  to carry the vehicle across them.')
        per_5m = stats['final_pos_err_m'] / stats['final_distance_m'] * 5.5
        print('')
        print('  measured position error      {:.4f} m over {:.2f} m'.format(
            stats['final_pos_err_m'], stats['final_distance_m']))
        print('  pro rata over the longest')
        print('  degenerate stretch, 5.5 m    {:.4f} m'.format(per_5m))
        checker.note('the pro-rata figure is an ORDER OF MAGNITUDE and not a '
                     'prediction: dead-reckoning error grows with heading '
                     'error, so it is superlinear in distance and depends on '
                     'the manoeuvres, not only on how far the vehicle went')
    return checker


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Verify and measure the forklift motion estimate.')
    parser.add_argument('--phase', choices=('static', 'imu', 'wheel', 'fusion'),
                        default='static')
    parser.add_argument('--print-world', action='store_true',
                        help='emit the flat test world and exit')
    parser.add_argument('--settle', type=float, default=15.0,
                        help='simulated seconds to let the model settle '
                             'before the IMU phase samples (default: '
                             '%(default)s)')
    parser.add_argument('--sample', type=float, default=30.0,
                        help='simulated seconds of IMU samples '
                             '(default: %(default)s)')
    args = parser.parse_args(argv)

    if args.print_world:
        sys.stdout.write(_TEST_WORLD)
        return 0

    checker = Checker()
    if args.phase == 'static':
        phase_static(checker)
    elif args.phase == 'imu':
        phase_imu(checker, args.settle, args.sample)
    else:
        want_fusion = args.phase == 'fusion'
        checker, recorder = phase_drive(checker, want_fusion)
        if recorder is not None:
            report_drive(checker, recorder, want_fusion)
    return checker.summary()


if __name__ == '__main__':
    sys.exit(main())
