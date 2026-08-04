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
    --phase idle     the fused heading with the vehicle commanded to
                     rest, over an idle longer than the one that turned
                     the m5-08 map. NO GROUND TRUTH IS READ IN THIS
                     PHASE, by construction and not by habit: the
                     vehicle's own encoders establish that it did not
                     move, its own gyro says what would have been
                     integrated, and the fused heading is compared with
                     ITSELF at the start of the window. There is nothing
                     for truth to contribute to a question of the form
                     "did this number change while nothing happened".
    --phase postidle THE SAME QUESTION IN THE OTHER REGIME: the idle
                     AFTER a drive. It drives `_PROFILE` first and then
                     measures, so it differs from --phase idle in one
                     thing, whether the vehicle has moved. It also
                     records the encoders' sub-count residual, every
                     standstill re-arm, both IMU streams and the
                     filter's own yaw rate, and attributes the heading
                     it measures to gate-open, filter-relaxing and
                     filter-quiet intervals - which is what tells a gate
                     that admits samples apart from a filter that turns
                     without one. No ground truth here either.
    --phase replay   NO ROS AND NO SIMULATOR. Reads a series written by
                     --phase postidle and replays candidate standstill
                     rules over the recorded counts, so "what would a
                     different rule have done" is answered from a
                     committed artifact rather than by re-measuring.

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
  python3 agv/forklift/scripts/check_odometry.py --phase idle --idle 60
  python3 agv/forklift/scripts/check_odometry.py --phase postidle \
      --idle 210 --csv agv/forklift/evidence/postidle.csv

  The four live phases need a running stack and they set use_sim_time on
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

    section('6. the standstill verdict, driven through count series')
    check_standstill_window(checker, cfg)
    return checker


def check_standstill_window(checker, cfg):
    """Drive StandstillWindow through series whose answer is known.

    NO ROS, NO SIMULATOR. The defect brief m5-07e fixed - a slow axis
    relaxation discarding a standstill the vehicle had been holding
    throughout - cost a 210 s live run to find. Every case below is the
    same question asked as a table, so the next one costs nothing
    (LESSONS 2026-07-29).
    """
    sys.path.insert(0, _THIS_DIR)
    import wheel_odometry as wo

    still = cfg['standstill']
    window_s = float(still['window_s'])
    tol = int(still['steer_tolerance_counts'])
    hz = float(cfg['odometry']['publish_hz']) * 10.0   # the joint-state rate

    def run(drive_of, steer_of, seconds, dt=1.0 / hz, start=100.0):
        """Feed a series and return the fraction of samples verdict-true,
        counted only after the first window has had time to fill."""
        sw = wo.StandstillWindow(window_s, tol, bool(still['include_steer_axis']))
        true_n = total = 0
        n = int(round(seconds / dt))
        for i in range(n):
            t = start + i * dt
            verdict = sw.update(t, drive_of(i * dt), steer_of(i * dt))
            if i * dt >= window_s + dt:
                total += 1
                true_n += 1 if verdict else 0
        return true_n / float(total) if total else float('nan')

    zero = lambda s: 0
    checker.check('a vehicle whose counts never move reads standstill',
                  run(zero, zero, 10.0) == 1.0,
                  'verdict true for {:.1%} of the samples after the first '
                  'window'.format(run(zero, zero, 10.0)))

    # The window has to elapse before the verdict forms, and not before.
    sw = wo.StandstillWindow(window_s, tol, True)
    dt = 1.0 / hz
    seen_true_at = None
    for i in range(int(round(3.0 / dt))):
        if sw.update(100.0 + i * dt, 0, 0) and seen_true_at is None:
            seen_true_at = i * dt
    checker.check('the verdict waits the whole window before it forms',
                  seen_true_at is not None
                  and abs(seen_true_at - window_s) <= 2.0 * dt,
                  'first true at {:.4f} s against a {:.3f} s window'.format(
                      seen_true_at if seen_true_at is not None
                      else float('nan'), window_s))

    # THE DEFECT THIS SECTION EXISTS FOR. A steer axis relaxing by one
    # count every 11 s, with the drive count dead still - the measured
    # post-drive behaviour of this vehicle (EVIDENCE_ODOMETRY.md 13).
    creep = run(zero, lambda s: int(s // 11.0), 120.0)
    checker.check('a steer axis creeping one count every 11 s stays '
                  'standstill', creep == 1.0,
                  'verdict true for {:.1%} of the samples'.format(creep))

    # ... and the drive axis doing the same must NOT, because that is the
    # bound. One count per 11 s of drive is 1.7e-5 m/s of tread, but the
    # gate may not assume it: the tolerance that carries the bound is zero.
    drive_creep = run(lambda s: int(s // 11.0), zero, 120.0)
    checker.check('a DRIVE axis creeping one count every 11 s does not',
                  drive_creep < 1.0,
                  'verdict true for {:.1%} of the samples - the gate opens '
                  'around each count'.format(drive_creep))

    # A commanded steer manoeuvre must open the gate at once. The profile
    # slews 0.35 rad in about a second; even a tenth of that rate is
    # hundreds of counts inside one window.
    steer_step_rad = 2.0 * math.pi / float(
        cfg['odometry']['steer_encoder_counts_per_rev'])
    rate_rps = 0.035
    slew = run(zero, lambda s: int(round(s * rate_rps / steer_step_rad)), 10.0)
    checker.check('a steer axis slewing at {:.3f} rad/s opens the gate'
                  .format(rate_rps), slew == 0.0,
                  'verdict true for {:.1%} of the samples, at {:.1f} '
                  'counts per window'.format(
                      slew, rate_rps * window_s / steer_step_rad))

    # A gap longer than the window is not a standstill, whatever the
    # counts say across it.
    sw = wo.StandstillWindow(window_s, tol, True)
    for i in range(int(round(2.0 / dt))):
        sw.update(100.0 + i * dt, 0, 0)
    after_gap = sw.update(100.0 + 2.0 + 5.0 * window_s, 0, 0)
    checker.check('a joint-state gap longer than the window clears the '
                  'verdict', after_gap is False,
                  'verdict after a {:.2f} s gap: {}'.format(
                      5.0 * window_s, after_gap))

    # A clock that ran backwards is a simulator reset, not a standstill.
    sw = wo.StandstillWindow(window_s, tol, True)
    for i in range(int(round(2.0 / dt))):
        sw.update(100.0 + i * dt, 0, 0)
    checker.check('a clock that runs backwards clears the verdict',
                  sw.update(50.0, 0, 0) is False,
                  'verdict on a stamp 50 s in the past: {}'.format(
                      sw.standstill))

    checker.check('the drive tolerance is zero, which is the bound itself',
                  wo.DRIVE_TOLERANCE_COUNTS == 0,
                  'DRIVE_TOLERANCE_COUNTS = {}'.format(
                      wo.DRIVE_TOLERANCE_COUNTS))

    odo = cfg['odometry']
    bound_deg = math.degrees(float(odo['rolling_radius_m'])
                             * (2.0 * math.pi
                                / float(odo['drive_encoder_counts_per_rev']))
                             / float(cfg['model']['wheelbase_m']))
    checker.note('the verdict permits at most {:.4f} deg of body rotation '
                 'over the window from the drive term ({:.4f} deg/s), and '
                 'the steer term carries no bound at all - it is a rate '
                 'guard, at {:.3f} deg/s'.format(
                     bound_deg, bound_deg / window_s,
                     math.degrees(tol * steer_step_rad / window_s)))


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
        # The vehicle's OWN verdict that its wheels are not turning, and
        # the count of gyro samples the gate let through. Both are read
        # from the vehicle rather than recomputed here: this script owns
        # no encoder model and inventing a second one would be two answers
        # to one question (invariant 10). They are recorded in every
        # driven phase, gate or no gate, because wheel_odometry.py
        # publishes the verdict either way - which is what makes the
        # before-and-after split of the route comparable.
        self.standstill = []   # (t, bool), stamped on receipt
        self.gated_gyro = 0
        from std_msgs.msg import Bool
        node.create_subscription(Bool, cfg['topics']['wheel_standstill'],
                                 self.cb_standstill, qos)
        if want_tf:
            from sensor_msgs.msg import Imu
            node.create_subscription(Imu, cfg['topics']['imu'],
                                     self.cb_imu, qos)
            node.create_subscription(Imu, cfg['topics']['imu_gated'],
                                     self.cb_gated_imu, qos)

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

    def cb_gated_imu(self, msg):
        self.gated_gyro += 1

    def cb_standstill(self, msg):
        # std_msgs/Bool carries no stamp, so the simulation clock is read
        # here. At 50 Hz the receipt time is within a cycle of the stamp
        # the message would have had, which is inside every window this
        # script measures.
        self.standstill.append(
            (self.node.get_clock().now().nanoseconds * 1e-9, bool(msg.data)))

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


def _moving_window(standstill):
    """(first moving t, last moving t, seconds held still) from the verdict.

    The window the vehicle was actually driving in, taken from the
    VEHICLE'S OWN encoder verdict and not from the profile's nominal
    timings or from ground truth. It exists so that the drift accumulated
    WHILE MOVING can be separated from the drift accumulated while the
    profile was parked - the two are different claims, and a stationary
    correction is only honest if the first of them does not move.
    """
    moving = [t for t, still in standstill if not still]
    if not moving:
        return None
    still_s = 0.0
    for (t0, s0), (t1, _) in zip(standstill, standstill[1:]):
        if s0:
            still_s += t1 - t0
    return (moving[0], moving[-1], still_s)


def _yaw_error_at(pairs, t_s):
    """Heading error of the pair nearest t_s, or None."""
    if not pairs:
        return None
    r, e = min(pairs, key=lambda pe: abs(pe[0][0] - t_s))
    return wrap_pi(e[3] - r[3])


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
    recorder.standstill.clear()
    recorder.gated_gyro = 0

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

            section('6b. the same run, split into moving and standing')
            window = _moving_window(recorder.standstill)
            pairs = _pair(truth, recorder.ekf)
            if window is None:
                checker.check(
                    'the standstill verdict shows the vehicle moving', False,
                    '{} messages on {}, none of them false - the vehicle '
                    'never moved, so this run measures nothing'.format(
                        len(recorder.standstill),
                        cfg['topics']['wheel_standstill']))
            else:
                t_go, t_halt, still_s = window
                err_go = _yaw_error_at(pairs, t_go)
                err_halt = _yaw_error_at(pairs, t_halt)
                span_s = t_halt - t_go
                print('  THE SPLIT IS TAKEN FROM THE VEHICLE\'S OWN ENCODER')
                print('  VERDICT, not from the profile\'s nominal timings and')
                print('  not from ground truth. Its purpose is to show which')
                print('  part of the run a change to standstill handling can')
                print('  possibly have touched.')
                print('')
                print('  recorded window            {:.2f} s'.format(
                    recorder.standstill[-1][0] - recorder.standstill[0][0]))
                print('  of which the wheels were')
                print('    reported standing still  {:.2f} s'.format(still_s))
                print('  first / last moving sample {:.2f} s .. {:.2f} s'
                      .format(t_go, t_halt))
                print('  gyro samples on {:<10} {}'.format(
                    cfg['topics']['imu'], len(recorder.gyro_z)))
                print('  gyro samples on {:<10} {}   (zero means the gate is'
                      .format(cfg['topics']['imu_gated'],
                              recorder.gated_gyro))
                print('    not running and the filter is remapped onto the '
                      'raw topic, not that it lost its gyro)')
                if err_go is not None and err_halt is not None:
                    moved = wrap_pi(err_halt - err_go)
                    print('')
                    print('  heading error at the first moving sample  '
                          '{:+.4f} deg'.format(math.degrees(err_go)))
                    print('  heading error at the last moving sample   '
                          '{:+.4f} deg'.format(math.degrees(err_halt)))
                    print('  DRIFT ACCUMULATED WHILE MOVING            '
                          '{:+.4f} deg over {:.2f} s'.format(
                              math.degrees(moved), span_s))
                    if recorder.gyro_z:
                        bias = statistics.fmean(recorder.gyro_z) - \
                            (net_sweep / duration)
                        print('  bias x MOVING seconds                     '
                              '{:+.4f} deg'.format(
                                  math.degrees(bias * span_s)))
                        print('  bias x RECORDED seconds                   '
                              '{:+.4f} deg'.format(
                                  math.degrees(bias * duration)))
                    checker.note(
                        'the moving-only figure is the one to compare across '
                        'builds. A change that only affects standing intervals '
                        'leaves it alone and shortens the whole-run figure by '
                        'bias x the standing seconds; a change that also '
                        'flatters the moving case moves it, and would be '
                        'doing something other than what it claims.')

    section('7. the drift against what it has to exercise')
    stats = fusion_stats or wheel_stats
    if stats and stats['final_distance_m'] <= 0.0:
        # A run in which the vehicle never moved. It has happened - a
        # stack brought up with nodes:=false has no forklift_io.py, so the
        # profile's speed commands reach nothing and every table above
        # reads zero. Say so rather than dividing by it.
        checker.check('the vehicle travelled a measurable distance', False,
                      'path length 0.00 m. The profile commanded motion and '
                      'none happened: check that forklift_io.py is running '
                      '(nodes:=true) and that the traction command topic has '
                      'a subscriber.')
        stats = None
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


# ====================================================================== #
# Phase: idle
# ====================================================================== #

def phase_idle(checker, idle_s):
    """Does the fused heading hold while the vehicle is commanded to rest?

    THE QUESTION THIS ANSWERS, AND WHY IT NEEDS NO GROUND TRUTH. The
    committed warehouse map of brief m5-08 came out about 2 deg rotated
    from the building because the estimator integrated gyro bias through
    the idle between bringup and the first drive command. That is not a
    claim about where the vehicle is; it is a claim that a number MOVED
    while nothing happened. Its own start value is the reference, the
    vehicle's own encoders establish that nothing happened, and the
    vehicle's own gyro says what would have been integrated. Ground truth
    is not an input to any of the three, and reading it here would put the
    simulator's pose inside a measurement whose whole point is that the
    vehicle can make it alone.
    """
    from std_msgs.msg import Bool, Float64
    from sensor_msgs.msg import Imu
    from rclpy.qos import QoSProfile
    from tf2_msgs.msg import TFMessage

    cfg = load_config(_CONFIG)
    frames = cfg['frames']
    rclpy, node = _live_node('check_odometry_idle')
    qos = QoSProfile(depth=200)

    fused = []       # (t, yaw) from /tf, the EKF's own transform
    gyro = []        # (t, wz) raw, the counterfactual
    gated = []       # (t, wz) as offered to the filter
    counts = []      # (t, drive_rad, steer_rad) the vehicle's own encoders
    verdict = []     # (t, bool)

    def cb_tf(msg):
        for tf in msg.transforms:
            if (tf.header.frame_id == frames['odom']
                    and tf.child_frame_id == frames['base']):
                q = (tf.transform.rotation.x, tf.transform.rotation.y,
                     tf.transform.rotation.z, tf.transform.rotation.w)
                fused.append((tf.header.stamp.sec
                              + tf.header.stamp.nanosec * 1e-9, yaw_of(q)))

    def cb_imu(msg):
        gyro.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                     msg.angular_velocity.z))

    def cb_gated(msg):
        gated.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                      msg.angular_velocity.z))

    def cb_joints(msg):
        model = cfg['model']
        if model['drive_joint_name'] not in msg.name:
            return
        i_d = msg.name.index(model['drive_joint_name'])
        i_s = msg.name.index(model['steer_joint_name'])
        counts.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                       msg.position[i_d], msg.position[i_s]))

    def cb_verdict(msg):
        verdict.append((node.get_clock().now().nanoseconds * 1e-9,
                        bool(msg.data)))

    node.create_subscription(TFMessage, cfg['topics']['tf'], cb_tf, qos)
    node.create_subscription(Imu, cfg['topics']['imu'], cb_imu, qos)
    node.create_subscription(Imu, cfg['topics']['imu_gated'], cb_gated, qos)
    from sensor_msgs.msg import JointState
    node.create_subscription(JointState, cfg['topics']['joint_states'],
                             cb_joints, qos)
    node.create_subscription(Bool, cfg['topics']['wheel_standstill'],
                             cb_verdict, qos)
    pub_speed = node.create_publisher(
        Float64, cfg['topics']['cmd_traction_speed'], QoSProfile(depth=10))
    pub_steer = node.create_publisher(
        Float64, cfg['topics']['cmd_steer_angle'], QoSProfile(depth=10))

    section('1. the vehicle, commanded to rest')
    if not _wait_clock(rclpy, node):
        checker.check('the simulation clock is running', False)
        return checker
    checker.check('the simulation clock is running', True)

    # Discovery first, then the rest command, then a settle. A model
    # dropped onto the floor is still ringing for a second or so, and the
    # window must not start inside that.
    _sim_sleep(rclpy, node, 5.0)
    zero = Float64()
    zero.data = 0.0
    pub_speed.publish(zero)
    pub_steer.publish(zero)
    _sim_sleep(rclpy, node, 5.0)

    for buf in (fused, gyro, gated, counts, verdict):
        del buf[:]
    print('  idle window: {:.1f} simulated seconds, speed and steer both '
          'commanded 0'.format(idle_s))
    _sim_sleep(rclpy, node, idle_s)

    section('2. did the wheels move at all? (the vehicle\'s own encoders)')
    ok = len(counts) > 100 and len(fused) > 100
    checker.check('the streams this phase needs were recorded', ok,
                  '{} joint states, {} transforms, {} raw gyro samples'
                  .format(len(counts), len(fused), len(gyro)))
    if not ok:
        node.destroy_node()
        rclpy.shutdown()
        return checker

    odo = cfg['odometry']
    drive_step = 2.0 * math.pi / float(odo['drive_encoder_counts_per_rev'])
    steer_step = 2.0 * math.pi / float(odo['steer_encoder_counts_per_rev'])
    drive_counts = set(int(round(c[1] / drive_step)) for c in counts)
    steer_counts = set(int(round(c[2] / steer_step)) for c in counts)
    span_s = counts[-1][0] - counts[0][0]
    checker.check('the drive encoder reported exactly one count all window',
                  len(drive_counts) == 1,
                  '{} distinct counts over {:.2f} s'.format(
                      len(drive_counts), span_s))
    checker.check('the steer encoder reported exactly one count all window',
                  len(steer_counts) == 1,
                  '{} distinct counts'.format(len(steer_counts)))
    # The kinematic bound this buys, computed rather than quoted.
    bound_rad = (float(odo['rolling_radius_m']) * drive_step
                 / float(cfg['model']['wheelbase_m']))
    print('  one drive count bounds the body rotation over the interval it')
    print('  is held at {:.3e} rad = {:.4f} deg (tricycle: the centre of'
          .format(bound_rad, math.degrees(bound_rad)))
    print('  rotation lies on the rear axle line and the drive wheel does')
    print('  not, so the body cannot turn without the drive wheel travelling)')

    section('3. what the gyro reported, and what reached the filter')
    wz = [g[1] for g in gyro]
    mean_wz = statistics.fmean(wz)
    integrated = 0.0
    for a, b in zip(gyro, gyro[1:]):
        integrated += 0.5 * (a[1] + b[1]) * (b[0] - a[0])
    still_frac = (sum(1 for _, s in verdict if s) / len(verdict)
                  if verdict else float('nan'))
    print('  raw gyro z, mean over the window   {:+.6f} rad/s  ({:+.4f} '
          'deg/s)'.format(mean_wz, math.degrees(mean_wz)))
    print('  THAT MEAN IS THE BIAS, and the encoders above are why: a rate')
    print('  measured while the vehicle provably is not rotating is not a')
    print('  rate. No ground truth was consulted to say so.')
    print('  raw gyro z, integrated over the')
    print('    window                           {:+.6f} rad  ({:+.4f} deg)'
          .format(integrated, math.degrees(integrated)))
    print('  = the heading this estimator would have gained by standing '
          'still')
    print('  standstill verdict true for        {:.1f} % of the window'
          .format(100.0 * still_frac))
    print('  gyro samples on {:<18} {}'.format(cfg['topics']['imu'],
                                               len(gyro)))
    print('  gyro samples on {:<18} {}'.format(cfg['topics']['imu_gated'],
                                               len(gated)))
    print('  READ THAT PAIR WITH THE LAUNCH ARGUMENT IN HAND. With')
    print('  imu_gate:=true the second row is what the filter was offered.')
    print('  With imu_gate:=false the gate node is not running, the gated')
    print('  topic has no publisher, and the launch remaps the filter onto')
    print('  the raw topic instead - so a zero there means "no gate", not')
    print('  "no gyro".')

    section('4. did the fused heading hold?')
    yaw0 = fused[0][1]
    drift = [wrap_pi(y - yaw0) for _, y in fused]
    held_s = fused[-1][0] - fused[0][0]
    worst = max(drift, key=abs)
    final = drift[-1]
    print('  fused heading at the start of the window   {:+.6f} rad'
          .format(yaw0))
    print('  fused heading at the end                   {:+.6f} rad'
          .format(fused[-1][1]))
    print('')
    print('  {:<34} {:>12} {:>12}'.format('', '[rad]', '[deg]'))
    print('  {:<34} {:>12.6f} {:>12.4f}'.format(
        'net change over the window', final, math.degrees(final)))
    print('  {:<34} {:>12.6f} {:>12.4f}'.format(
        'largest excursion from the start', worst, math.degrees(worst)))
    print('  {:<34} {:>12.6f} {:>12.4f}'.format(
        'the gyro would have given', integrated, math.degrees(integrated)))
    if held_s > 0:
        print('')
        print('  per minute of idle, measured   fused {:+.4f} deg/min '
              'against gyro {:+.4f} deg/min'.format(
                  math.degrees(final) * 60.0 / held_s,
                  math.degrees(integrated) * 60.0 / held_s))
    print('  window length                  {:.2f} simulated seconds'
          .format(held_s))
    checker.note('this phase asserts no pass threshold on the hold. The '
                 'number is the deliverable and the two rows above it are '
                 'the comparison: what the heading did against what the '
                 'unfiltered gyro would have made it do over the same '
                 'seconds.')

    node.destroy_node()
    rclpy.shutdown()
    return checker


# ====================================================================== #
# Phase: postidle
# ====================================================================== #
#
# THE REGIME --phase idle DOES NOT REACH. Its idle starts at bringup,
# with every joint at its spawn value, and the heading holds to 0.01 deg
# over it. Brief m5-08d measured the SAME vehicle over a 200.4 s idle
# taken AFTER a drive and found +2.02 deg, with 92-97 % of the gyro
# samples suppressed rather than 100 %. This phase drives the SAME
# `_PROFILE` first and then measures, so the two idles differ in one
# thing: whether the vehicle has moved.
#
# It reads no ground truth, for the reason written over phase_idle: the
# question is whether a number moved while nothing happened, and the
# vehicle's own encoders answer the second half of that.

#: Two gated IMU samples further apart than this belong to two separate
#: openings of the gate. The device runs at 100 Hz, so this is five
#: sample periods - long enough that jitter never splits a burst, short
#: enough that the 0.50 s arming window never merges two.
_BURST_GAP_S = 0.05

#: How long after a burst of gated samples the EKF is still allowed to be
#: settling, for the three-way attribution below. Ten filter cycles.
_TAIL_S = 0.20


def _bursts(stamps, gap_s):
    """Group sorted timestamps into [start, end] runs separated by > gap_s."""
    runs = []
    for t in stamps:
        if runs and t - runs[-1][1] <= gap_s:
            runs[-1][1] = t
        else:
            runs.append([t, t])
    return runs


def _in_any(t, windows):
    for a, b in windows:
        if a <= t <= b:
            return True
    return False


def _split_yaw(track, bursts, tail_s):
    """Signed yaw change of a (t, yaw) track, split three ways.

    Each consecutive pair contributes its own increment to exactly one
    bucket, chosen by where the midpoint of the pair falls:

      inside  - the gate was open; a gyro sample was being fused
      tail    - within `tail_s` of a burst ending; the filter is still
                relaxing whatever that burst put into its yaw rate state
      quiet   - the gate was closed and had been for longer than that

    A leak that lives in `quiet` is the filter integrating a stale
    twist. A leak that lives in `inside` is the gate letting samples
    through. The buckets are what tells those two apart.
    """
    inside = tail = quiet = 0.0
    tails = [(b, b + tail_s) for _, b in bursts]
    for (ta, ya), (tb, yb) in zip(track, track[1:]):
        d = wrap_pi(yb - ya)
        mid = 0.5 * (ta + tb)
        if _in_any(mid, [(a, b) for a, b in bursts]):
            inside += d
        elif _in_any(mid, tails):
            tail += d
        else:
            quiet += d
    return inside, tail, quiet


def phase_postidle(checker, idle_s, csv_path, want_truth):
    """The gate's behaviour in the regime an AMCL dwell test sits in.

    Drives `_PROFILE`, stops, and then measures the idle - recording the
    encoders, the standstill verdict, both IMU streams, the fused
    heading and the filter's own yaw rate, so that each candidate
    mechanism is ruled in or out by a number rather than by argument.

    `want_truth` adds ONE further stream and it answers ONE question,
    section 7's: the standstill verdict includes the steer count on the
    ground that a parked forklift steering on the spot could scrub its
    drive tyre and take the body round with it. That premise is a claim
    about the world, and truth is the only instrument for it. It is
    recorded as a REFERENCE, reported in its own section, and it enters
    no verdict this phase computes - sections 2 to 6 are identical with
    it and without it. The hold measurement itself needs no truth at all
    and does not consult it.
    """
    from std_msgs.msg import Bool, Float64
    from sensor_msgs.msg import Imu, JointState
    from nav_msgs.msg import Odometry
    from rclpy.qos import QoSProfile
    from tf2_msgs.msg import TFMessage

    cfg = load_config(_CONFIG)
    frames = cfg['frames']
    odo = cfg['odometry']
    still_cfg = cfg['standstill']
    drive_step = 2.0 * math.pi / float(odo['drive_encoder_counts_per_rev'])
    steer_step = 2.0 * math.pi / float(odo['steer_encoder_counts_per_rev'])
    window_s = float(still_cfg['window_s'])
    timeout_s = float(still_cfg['verdict_timeout_s'])

    rclpy, node = _live_node('check_odometry_postidle')
    qos = QoSProfile(depth=500)

    fused = []       # (t, yaw) from /tf - the EKF's own transform
    ekf_wz = []      # (t, wz) the filter's own yaw rate state
    gyro = []        # (t, wz) raw
    gated = []       # (t, wz) as offered to the filter
    joints = []      # (t, drive_rad, steer_rad)
    verdict = []     # (t_arrival, bool) on the node's clock, as the gate sees
    truth = []       # (t, x, y, yaw) REFERENCE ONLY, section 7, never fused

    def cb_truth(msg):
        q = (msg.pose.pose.orientation.x, msg.pose.pose.orientation.y,
             msg.pose.pose.orientation.z, msg.pose.pose.orientation.w)
        truth.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                      msg.pose.pose.position.x, msg.pose.pose.position.y,
                      yaw_of(q)))

    def cb_tf(msg):
        for tf in msg.transforms:
            if (tf.header.frame_id == frames['odom']
                    and tf.child_frame_id == frames['base']):
                q = (tf.transform.rotation.x, tf.transform.rotation.y,
                     tf.transform.rotation.z, tf.transform.rotation.w)
                fused.append((tf.header.stamp.sec
                              + tf.header.stamp.nanosec * 1e-9, yaw_of(q)))

    def cb_filtered(msg):
        ekf_wz.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                       msg.twist.twist.angular.z))

    def cb_imu(msg):
        gyro.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                     msg.angular_velocity.z))

    def cb_gated(msg):
        gated.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                      msg.angular_velocity.z))

    def cb_joints(msg):
        model = cfg['model']
        if model['drive_joint_name'] not in msg.name:
            return
        i_d = msg.name.index(model['drive_joint_name'])
        i_s = msg.name.index(model['steer_joint_name'])
        joints.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                       msg.position[i_d], msg.position[i_s]))

    def cb_verdict(msg):
        verdict.append((node.get_clock().now().nanoseconds * 1e-9,
                        bool(msg.data)))

    topics = cfg['topics']
    node.create_subscription(TFMessage, topics['tf'], cb_tf, qos)
    node.create_subscription(Odometry, topics['odom_filtered'],
                             cb_filtered, qos)
    node.create_subscription(Imu, topics['imu'], cb_imu, qos)
    node.create_subscription(Imu, topics['imu_gated'], cb_gated, qos)
    node.create_subscription(JointState, topics['joint_states'],
                             cb_joints, qos)
    node.create_subscription(Bool, topics['wheel_standstill'],
                             cb_verdict, qos)
    if want_truth:
        node.create_subscription(Odometry, topics['odom'], cb_truth, qos)
    pub_speed = node.create_publisher(
        Float64, topics['cmd_traction_speed'], QoSProfile(depth=10))
    pub_steer = node.create_publisher(
        Float64, topics['cmd_steer_angle'], QoSProfile(depth=10))

    section('1. the drive, then the idle')
    if not _wait_clock(rclpy, node):
        checker.check('the simulation clock is running', False)
        return checker
    checker.check('the simulation clock is running', True)
    _sim_sleep(rclpy, node, 5.0)

    print('  the SAME manoeuvre set as --phase fusion, timed on the')
    print('  simulation clock, then {:.1f} s of idle:'.format(idle_s))
    driving = [leg for leg in _PROFILE if leg[0] != 'stop']
    for label, seconds, speed, steer in driving:
        print('    {:<12} {:>5.1f} s  speed {:+.2f} m/s  steer {:+.3f} rad'
              .format(label, seconds, speed, steer))

    for label, seconds, speed, steer in driving:
        steer_msg = Float64()
        steer_msg.data = float(steer)
        pub_steer.publish(steer_msg)
        _sim_sleep(rclpy, node, 1.0)
        speed_msg = Float64()
        speed_msg.data = float(speed)
        pub_speed.publish(speed_msg)
        _sim_sleep(rclpy, node, max(0.0, seconds - 1.0))

    # Everything recorded from here is the stop transition and the idle.
    # The buffers are cleared BEFORE the stop is commanded, so the
    # deceleration is inside the window and the 0.50 s arming hypothesis
    # has something to be measured against.
    for buf in (fused, ekf_wz, gyro, gated, joints, verdict, truth):
        del buf[:]
    t_stop = node.get_clock().now().nanoseconds * 1e-9
    stop = Float64()
    stop.data = 0.0
    pub_speed.publish(stop)
    pub_steer.publish(stop)
    print('  stop commanded at t = {:.3f} s (simulation clock); recording '
          '{:.1f} s'.format(t_stop, idle_s))
    _sim_sleep(rclpy, node, idle_s)

    ok = len(joints) > 100 and len(fused) > 100 and len(verdict) > 100
    checker.check('the streams this phase needs were recorded', ok,
                  '{} joint states, {} transforms, {} raw gyro, {} gated, '
                  '{} verdicts'.format(len(joints), len(fused), len(gyro),
                                       len(gated), len(verdict)))
    if not ok:
        node.destroy_node()
        rclpy.shutdown()
        return checker

    if csv_path:
        _write_postidle_csv(csv_path, t_stop, joints, verdict, gyro, gated,
                            fused, ekf_wz, truth)
        print('  raw series written to {}'.format(csv_path))

    node.destroy_node()
    rclpy.shutdown()

    # ------------------------------------------------------------------ #
    report_postidle(checker, cfg, t_stop, idle_s, joints, verdict, gyro,
                    gated, fused, ekf_wz, drive_step, steer_step, window_s,
                    timeout_s, truth)
    return checker


def _write_postidle_csv(path, t_stop, joints, verdict, gyro, gated, fused,
                        ekf_wz, truth=()):
    """One row per sample of every stream, tagged, longest stream first.

    Written as a tall table rather than a joined one on purpose: the
    streams run at 500, 100 and 50 Hz and joining them would resample
    somebody's data. Columns: t_rel, stream, value_a, value_b.
    """
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write('t_rel_s,stream,a,b\n')
        for t, d, s in joints:
            handle.write('{:.6f},joint,{:.12f},{:.12f}\n'.format(t - t_stop, d, s))
        for t, v in verdict:
            handle.write('{:.6f},verdict,{:d},\n'.format(t - t_stop, int(v)))
        for t, w in gyro:
            handle.write('{:.6f},gyro,{:.12f},\n'.format(t - t_stop, w))
        for t, w in gated:
            handle.write('{:.6f},gated,{:.12f},\n'.format(t - t_stop, w))
        for t, y in fused:
            handle.write('{:.6f},fused_yaw,{:.12f},\n'.format(t - t_stop, y))
        for t, w in ekf_wz:
            handle.write('{:.6f},ekf_wz,{:.12f},\n'.format(t - t_stop, w))
        # REFERENCE ONLY, and labelled so in the stream name. Nothing that
        # estimates or steers reads this file.
        for t, x, y, yaw in truth:
            handle.write('{:.6f},truth_yaw,{:.12f},{:.12f}\n'
                         .format(t - t_stop, yaw, math.hypot(x, y)))


def report_postidle(checker, cfg, t_stop, idle_s, joints, verdict, gyro,
                    gated, fused, ekf_wz, drive_step, steer_step, window_s,
                    timeout_s, truth=()):
    """Rule each candidate mechanism in or out, one measurement each."""
    odo = cfg['odometry']
    radius_m = float(odo['rolling_radius_m'])
    wheelbase_m = float(cfg['model']['wheelbase_m'])

    section('2. what the encoders did during the idle')
    d_counts = [int(round(j[1] / drive_step)) for j in joints]
    s_counts = [int(round((j[2] + float(odo['steer_zero_offset_rad']))
                          / steer_step)) for j in joints]
    d_resid = [j[1] / drive_step - round(j[1] / drive_step) for j in joints]
    span_s = joints[-1][0] - joints[0][0]

    d_changes = sum(1 for a, b in zip(d_counts, d_counts[1:]) if a != b)
    s_changes = sum(1 for a, b in zip(s_counts, s_counts[1:]) if a != b)
    d_excursion = max(d_counts) - min(d_counts)
    d_net = d_counts[-1] - d_counts[0]
    s_excursion = max(s_counts) - min(s_counts)
    s_net = s_counts[-1] - s_counts[0]

    print('  over {:.2f} s of idle, at {:.0f} Hz of joint state:'.format(
        span_s, len(joints) / span_s if span_s > 0 else 0.0))
    print('  {:<38} {:>10} {:>10}'.format('', 'drive', 'steer'))
    print('  {:<38} {:>10d} {:>10d}'.format(
        'distinct counts visited', len(set(d_counts)), len(set(s_counts))))
    print('  {:<38} {:>10d} {:>10d}'.format(
        'count CHANGES (each re-arms the window)', d_changes, s_changes))
    print('  {:<38} {:>10d} {:>10d}'.format(
        'count excursion, max - min', d_excursion, s_excursion))
    print('  {:<38} {:>10d} {:>10d}'.format(
        'count NET change, last - first', d_net, s_net))
    print('')
    print('  DITHER OR CREEP: a net change equal to the excursion is the')
    print('  wheel slowly turning; an excursion with a net change of zero')
    print('  and many changes is one count boundary being crossed and')
    print('  re-crossed. The sub-count residual says which boundary:')
    print('  drive angle in counts, residual from the nearest grid point')
    print('    mean   {:+.4f} count   (0.5 is exactly on a boundary)'.format(
        statistics.fmean(d_resid)))
    print('    min    {:+.4f} count'.format(min(d_resid)))
    print('    max    {:+.4f} count'.format(max(d_resid)))
    print('    pk-pk  {:.4f} count  = {:.3e} rad of wheel = {:.3e} m of '
          'tread'.format(max(d_resid) - min(d_resid),
                         (max(d_resid) - min(d_resid)) * drive_step,
                         (max(d_resid) - min(d_resid)) * drive_step * radius_m))
    bound_deg = math.degrees(radius_m * drive_step / wheelbase_m)
    print('  one drive count still bounds the body rotation at {:.4f} deg'
          .format(bound_deg))

    section('3. the verdict, and its freshness')
    still_frac = sum(1 for _, s in verdict if s) / float(len(verdict))
    gaps = [b[0] - a[0] for a, b in zip(verdict, verdict[1:])]
    rises = sum(1 for a, b in zip(verdict, verdict[1:]) if b[1] and not a[1])
    falls = sum(1 for a, b in zip(verdict, verdict[1:]) if a[1] and not b[1])
    false_time = sum((b[0] - a[0]) for a, b in zip(verdict, verdict[1:])
                     if not a[1])
    print('  verdict true for                     {:.2f} % of the window'
          .format(100.0 * still_frac))
    print('  verdict FALSE for                    {:.3f} s'.format(false_time))
    print('  false -> true transitions            {}'.format(rises))
    print('  true -> false transitions            {}'.format(falls))
    print('  largest gap between two verdicts     {:.4f} s'.format(
        max(gaps) if gaps else float('nan')))
    print('  the gate times a verdict out after   {:.4f} s'.format(timeout_s))
    fresh_ok = (max(gaps) < timeout_s) if gaps else False
    checker.check('every verdict arrived inside the gate\'s freshness window',
                  fresh_ok,
                  'largest gap {:.4f} s against a {:.3f} s timeout'.format(
                      max(gaps) if gaps else float('nan'), timeout_s))
    print('  IF THAT CHECK PASSES the freshness hypothesis is OUT: the gate')
    print('  never fell back to open because a verdict went stale.')
    print('')
    print('  re-arm accounting: {} true->false transitions x {:.2f} s of'
          .format(falls, window_s))
    print('  window = {:.2f} s of gate-open time predicted, against {:.3f} s'
          .format(falls * window_s, false_time))
    print('  of verdict-false time measured.')

    section('4. what the gyro reported, and what reached the filter')
    wz = [g[1] for g in gyro]
    mean_wz = statistics.fmean(wz) if wz else float('nan')
    integrated = 0.0
    for a, b in zip(gyro, gyro[1:]):
        integrated += 0.5 * (a[1] + b[1]) * (b[0] - a[0])
    suppressed = len(gyro) - len(gated)
    print('  raw gyro z, mean over the idle       {:+.6f} rad/s ({:+.4f} '
          'deg/s)'.format(mean_wz, math.degrees(mean_wz)))
    print('  raw gyro z, integrated               {:+.6f} rad  ({:+.4f} deg)'
          .format(integrated, math.degrees(integrated)))
    print('  raw samples                          {}'.format(len(gyro)))
    print('  samples offered to the filter        {}'.format(len(gated)))
    print('  suppressed                           {} = {:.2f} %'.format(
        suppressed,
        100.0 * suppressed / len(gyro) if gyro else float('nan')))
    gated_wz = [g[1] for g in gated]
    if gated_wz:
        print('  gated stream, mean                   {:+.6f} rad/s'.format(
            statistics.fmean(gated_wz)))
        print('  gated stream, sum x nominal 0.01 s   {:+.4f} deg'.format(
            math.degrees(statistics.fmean(gated_wz) * len(gated_wz) * 0.01)))
        print('  = the heading the samples that got through would have')
        print('  contributed on their own, if the filter took each at face')
        print('  value. It is the size of the leak the gate itself explains.')

    section('5. where the fused heading actually moved')
    yaw0 = fused[0][1]
    drift = [wrap_pi(y - yaw0) for _, y in fused]
    held_s = fused[-1][0] - fused[0][0]
    final = drift[-1]
    worst = max(drift, key=abs)
    print('  net change over the idle             {:+.6f} rad ({:+.4f} deg)'
          .format(final, math.degrees(final)))
    print('  largest excursion from the start     {:+.6f} rad ({:+.4f} deg)'
          .format(worst, math.degrees(worst)))
    if held_s > 0:
        print('  per minute of idle                   {:+.4f} deg/min'
              .format(math.degrees(final) * 60.0 / held_s))
    print('  window length                        {:.2f} simulated seconds'
          .format(held_s))

    # --- the arming window at the stop transition, on its own ---
    first_open_end = t_stop
    bursts = _bursts([g[0] for g in gated], _BURST_GAP_S)
    if bursts:
        first_open_end = bursts[0][1]
    def _yaw_at(t):
        best = None
        for ts, y in fused:
            if ts <= t:
                best = y
            else:
                break
        return best if best is not None else fused[0][1]
    settle_deg = math.degrees(wrap_pi(_yaw_at(first_open_end) - yaw0))
    rest_deg = math.degrees(final) - settle_deg
    print('')
    print('  the FIRST burst of gated samples after the stop ends at')
    print('  t_stop {:+.3f} s. Heading gained inside it {:+.4f} deg;'
          .format(first_open_end - t_stop, settle_deg))
    print('  heading gained over the remaining {:.1f} s {:+.4f} deg.'
          .format(held_s - (first_open_end - fused[0][0]), rest_deg))
    print('  A leak that is only the settling window is the first number')
    print('  and nothing else. The second number is the one that scales')
    print('  with how long a dwell lasts.')

    section('6. attribution: gate open, filter relaxing, or filter quiet')
    inside, tail, quiet = _split_yaw(fused, bursts, _TAIL_S)
    total = inside + tail + quiet
    open_s = sum(b - a for a, b in bursts)
    print('  {} separate openings of the gate over the idle, {:.3f} s of'
          .format(len(bursts), open_s))
    print('  gate-open time in total ({:.2f} % of the window)'.format(
        100.0 * open_s / held_s if held_s else float('nan')))
    print('')
    print('  {:<44} {:>12} {:>9}'.format('bucket', '[deg]', 'share'))
    for label, value in (('gate OPEN - a gyro sample was being fused', inside),
                         ('within {:.2f} s after an opening - relaxing'
                          .format(_TAIL_S), tail),
                         ('gate CLOSED and quiet', quiet)):
        print('  {:<44} {:>12.4f} {:>8.1f} %'.format(
            label, math.degrees(value),
            100.0 * value / total if total else float('nan')))
    print('  {:<44} {:>12.4f}'.format('total', math.degrees(total)))
    print('')
    print('  READ THIS TABLE AS THE VERDICT ON THE MECHANISM. Weight in the')
    print('  first row is the gate admitting samples. Weight in the third')
    print('  row is the filter turning with no measurement at all, which')
    print('  would be a stale twist and not a gate defect.')

    if ekf_wz:
        wzs = [abs(w) for _, w in ekf_wz]
        print('')
        print('  the filter\'s own yaw rate state over the idle:')
        print('    mean |wz|   {:.3e} rad/s'.format(statistics.fmean(wzs)))
        print('    max  |wz|   {:.3e} rad/s'.format(max(wzs)))
        quiet_wz = [abs(w) for t, w in ekf_wz
                    if not _in_any(t, [(a, b + _TAIL_S) for a, b in bursts])]
        if quiet_wz:
            print('    max  |wz| with the gate closed and settled  {:.3e} '
                  'rad/s'.format(max(quiet_wz)))
            print('    = {:.4f} deg/min if it were held for a whole minute'
                  .format(math.degrees(max(quiet_wz)) * 60.0))

    if truth:
        section('7. REFERENCE ONLY: did the body move while the steer swept?')
        print('  Everything above was measured without truth. This section')
        print('  reads the simulator\'s own pose and asks ONE question that')
        print('  no encoder can answer: the standstill verdict includes the')
        print('  steer count because a parked forklift steering on the spot')
        print('  could scrub its drive tyre and take the body round with it.')
        print('  Over this idle the steer axis swept while the drive count')
        print('  was held. Did the body actually rotate?')
        # THE IDLE IS NOT ONE INTERVAL AND MUST NOT BE SCORED AS ONE. A
        # stop command does not stop a vehicle; it coasts. The drive
        # encoder says exactly when the wheel stopped turning, so the
        # window is split there, on the vehicle's own evidence.
        d_counts_t = [(j[0], int(round(j[1] / drive_step))) for j in joints]
        wheel_stop_t = d_counts_t[0][0]
        for (ta, ca), (tb, cb) in zip(d_counts_t, d_counts_t[1:]):
            if cb != ca:
                wheel_stop_t = tb
        parked_from = wheel_stop_t + window_s

        s_counts = [(j[0], int(round((j[2] + float(cfg['odometry']
                                                   ['steer_zero_offset_rad']))
                                     / steer_step))) for j in joints]
        parked_steer = [c for t, c in s_counts if t >= parked_from]
        sweep = (max(parked_steer) - min(parked_steer)) if parked_steer else 0

        def span(series, index, frm):
            sel = [s for s in series if s[0] >= frm]
            if len(sel) < 2:
                return 0.0, 0.0
            base = sel[0][index]
            net = wrap_pi(sel[-1][index] - base)
            worst = max((abs(wrap_pi(s[index] - base)) for s in sel))
            return net, worst

        t0, x0, y0, yaw0_t = truth[0]
        coast_m = max(math.hypot(x - x0, y - y0) for _, x, y, _ in truth)
        px0 = py0 = None
        for t, x, y, _ in truth:
            if t >= parked_from:
                px0, py0 = x, y
                break
        parked_m = (max(math.hypot(x - px0, y - py0)
                        for t, x, y, _ in truth if t >= parked_from)
                    if px0 is not None else float('nan'))
        net_all, worst_all = span(truth, 3, truth[0][0])
        net_parked, worst_parked = span(truth, 3, parked_from)
        fused_parked, _ = span(fused, 1, parked_from)
        print('')
        print('  the drive wheel stopped turning at   t_stop {:+.3f} s; the'
              .format(wheel_stop_t - t_stop))
        print('  vehicle coasted {:.4f} m getting there, and everything below'
              .format(coast_m))
        print('  the rule is measured from t_stop {:+.3f} s, one window after.'
              .format(parked_from - t_stop))
        print('')
        print('  {:<40} {:>14} {:>14}'.format(
            '', 'whole idle', 'wheel parked'))
        print('  {:<40} {:>14.4f} {:>14.4f}'.format(
            'steer axis swept [deg]',
            (max(c for _, c in s_counts) - min(c for _, c in s_counts))
            * math.degrees(steer_step), sweep * math.degrees(steer_step)))
        print('  {:<40} {:>14.6f} {:>14.6f}'.format(
            'TRUE position excursion [m]', coast_m, parked_m))
        print('  {:<40} {:>14.6f} {:>14.6f}'.format(
            'TRUE heading, largest excursion [deg]',
            math.degrees(worst_all), math.degrees(worst_parked)))
        print('  {:<40} {:>14.6f} {:>14.6f}'.format(
            'TRUE heading, net [deg]',
            math.degrees(net_all), math.degrees(net_parked)))
        print('')
        print('  AND THE NUMBER A DWELL TEST ACTUALLY CARES ABOUT - the')
        print('  estimator\'s ERROR while the wheel was provably parked:')
        print('  {:<40} {:>14.6f}'.format(
            'fused heading, net [deg]', math.degrees(fused_parked)))
        print('  {:<40} {:>14.6f}'.format(
            'TRUE heading, net [deg]', math.degrees(net_parked)))
        print('  {:<40} {:>14.6f}'.format(
            'estimator error accrued [deg]',
            math.degrees(fused_parked - net_parked)))
        parked_s = truth[-1][0] - parked_from
        if parked_s > 0:
            print('  {:<40} {:>14.6f}'.format(
                'per minute of parked dwell [deg/min]',
                math.degrees(fused_parked - net_parked) * 60.0 / parked_s))
            print('  {:<40} {:>14.2f}'.format(
                'over which [s]', parked_s))
        print('  truth samples                        {}'.format(len(truth)))
        print('')
        print('  A true heading excursion far under the steer sweep is the')
        print('  measured answer to the scrub premise ON THIS VEHICLE, IN')
        print('  THIS SIMULATOR, ON THIS FLOOR. It is not a general result')
        print('  and it is not a licence to drop the steer term: a vehicle')
        print('  towed or pushed bodily rotates with BOTH counts held, and')
        print('  no encoder on this machine sees that at all.')

    checker.note('this phase asserts no pass threshold on the hold. The '
                 'section 5 number is the deliverable and sections 2, 3 and '
                 '6 are what attribute it.')
    return checker


# ====================================================================== #
# Phase: replay
# ====================================================================== #

class _ReferenceStandstill(object):
    """m5-07d's rule, TRANSCRIBED so it can be compared rather than recalled.

    Both counts must equal the pair recorded when the hold began, within
    `band` counts, and the hold restarts whenever they do not. `band=0`
    is exactly what shipped before brief m5-07e; the banded variants are
    the obvious fix that a reader will ask about, and 13.4 answers by
    running them rather than by arguing.

    It is HERE, in the harness, and not in wheel_odometry.py: the vehicle
    carries one rule and this file carries the ones it is measured
    against.
    """

    def __init__(self, window_s, band, use_steer):
        self.window_s = float(window_s)
        self.band = int(band)
        self.use_steer = bool(use_steer)
        self.ref = None
        self.held_from_s = None

    def update(self, t_s, drive_count, steer_count):
        counts = (drive_count, steer_count if self.use_steer else 0)
        if (self.ref is None or self.held_from_s is None
                or abs(counts[0] - self.ref[0]) > self.band
                or abs(counts[1] - self.ref[1]) > self.band):
            self.ref = counts
            self.held_from_s = t_s
            return False
        held_s = t_s - self.held_from_s
        if held_s < 0.0:
            self.held_from_s = t_s
            return False
        return held_s >= self.window_s


def phase_replay(checker, csv_path):
    """Replay candidate standstill rules over a recorded postidle CSV.

    NO ROS AND NO SIMULATOR. The counts are already on disk, so asking
    what a different rule would have done costs nothing and needs no
    second run - which is what makes the comparison in
    EVIDENCE_ODOMETRY.md 13.4 checkable from the committed artifacts
    rather than only reproducible by re-measuring.

    THE PREDICTED LEAK IS AN ESTIMATE AND IS LABELLED ONE. It is the
    gate-open seconds times the measured gyro bias, which is what the
    filter would integrate if it took each admitted sample at face
    value. The real filter blends, so the live number is close but not
    equal - 13.4's -0.505 deg predicted against 13.7's -0.659 deg
    measured on a longer idle. The RANKING is the deliverable, not the
    third decimal.
    """
    sys.path.insert(0, _THIS_DIR)
    import wheel_odometry as wo

    cfg = load_config(_CONFIG)
    odo = cfg['odometry']
    still = cfg['standstill']
    drive_step = 2.0 * math.pi / float(odo['drive_encoder_counts_per_rev'])
    steer_step = 2.0 * math.pi / float(odo['steer_encoder_counts_per_rev'])
    offset = float(odo['steer_zero_offset_rad'])
    window_s = float(still['window_s'])
    shipped_tol = int(still['steer_tolerance_counts'])

    joints = []
    gyro = []
    with open(csv_path, 'r', encoding='utf-8') as handle:
        for line in handle:
            if line.startswith('t_rel'):
                continue
            parts = line.rstrip('\n').split(',')
            if parts[1] == 'joint':
                joints.append((float(parts[0]), float(parts[2]),
                               float(parts[3])))
            elif parts[1] == 'gyro':
                gyro.append(float(parts[2]))

    section('1. the recording')
    ok = len(joints) > 1000 and len(gyro) > 100
    checker.check('the CSV carries a joint and a gyro stream', ok,
                  '{} joint states, {} gyro samples'.format(
                      len(joints), len(gyro)))
    if not ok:
        return checker
    span_s = joints[-1][0] - joints[0][0]
    bias = statistics.fmean(gyro)
    print('  {}'.format(csv_path))
    print('  idle span                      {:.2f} s'.format(span_s))
    print('  measured gyro bias             {:+.6f} rad/s ({:+.4f} deg/s)'
          .format(bias, math.degrees(bias)))

    counts = [(t, int(round(d / drive_step)),
               int(round((s + offset) / steer_step))) for t, d, s in joints]

    section('2. what each rule would have done with these counts')

    def score(rule):
        open_s = 0.0
        prev_t = None
        prev_still = False
        for t, dc, sc in counts:
            if prev_t is not None and not prev_still:
                open_s += t - prev_t
            prev_still = rule.update(t, dc, sc)
            prev_t = t
        return open_s

    rules = [
        ('m5-07d as shipped: both exact, receding reference',
         lambda: _ReferenceStandstill(window_s, 0, True)),
        ('the same rule, drive axis only',
         lambda: _ReferenceStandstill(window_s, 0, False)),
        ('the same rule, +-1 count band on both axes',
         lambda: _ReferenceStandstill(window_s, 1, True)),
        ('the same rule, +-2 count band on both axes',
         lambda: _ReferenceStandstill(window_s, 2, True)),
        ('trailing window, drive exact, steer exact',
         lambda: wo.StandstillWindow(window_s, 0, True)),
        ('trailing window, drive exact, steer tol 1  <- SHIPPED'
         if shipped_tol == 1 else 'trailing window, drive exact, steer tol 1',
         lambda: wo.StandstillWindow(window_s, 1, True)),
        ('trailing window, drive exact, steer tol 2',
         lambda: wo.StandstillWindow(window_s, 2, True)),
        ('trailing window, drive exact, no steer term',
         lambda: wo.StandstillWindow(window_s, 0, False)),
    ]
    print('  {:<52} {:>9} {:>10} {:>12}'.format(
        'rule', 'suppr.', 'open [s]', 'leak [deg]'))
    for label, make in rules:
        open_s = score(make())
        leak = math.degrees(bias) * open_s
        print('  {:<52} {:>8.2f}% {:>10.3f} {:>12.3f}'.format(
            label, 100.0 * (1.0 - open_s / span_s), open_s, leak))
    print('')
    print('  THE LEAK COLUMN IS PREDICTED, not measured: gate-open seconds')
    print('  x the measured bias. The filter blends rather than taking each')
    print('  sample at face value, so the live figure differs; the ranking')
    print('  is what this table is for. The live numbers are section 13.7.')
    print('')
    print('  Read rows 1 and 5 together: making the window trailing while')
    print('  keeping exact equality changes nothing, so the receding')
    print('  reference is not the defect on its own. And rows 3 and 4 are')
    print('  the obvious band fix, which barely helps - a band absorbs')
    print('  dither, and a monotonically creeping axis walks out of any')
    print('  band and re-arms anyway.')
    return checker


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Verify and measure the forklift motion estimate.')
    parser.add_argument('--phase',
                        choices=('static', 'imu', 'wheel', 'fusion', 'idle',
                                 'postidle', 'replay'),
                        default='static')
    parser.add_argument('--csv', default='',
                        help='path for the raw per-sample series of '
                             '--phase postidle (default: not written)')
    parser.add_argument('--truth', action='store_true',
                        help='--phase postidle only: also record the '
                             'simulator pose as a REFERENCE for section 7, '
                             'which asks whether the body rotates while the '
                             'steer axis sweeps. It enters no other section '
                             'and no verdict')
    parser.add_argument('--idle', type=float, default=60.0,
                        help='simulated seconds of idle measured by '
                             '--phase idle (default: %(default)s)')
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
    elif args.phase == 'idle':
        phase_idle(checker, args.idle)
    elif args.phase == 'postidle':
        phase_postidle(checker, args.idle, args.csv, args.truth)
    elif args.phase == 'replay':
        if not args.csv:
            parser.error('--phase replay needs --csv, a series written by '
                         '--phase postidle')
        phase_replay(checker, args.csv)
    else:
        want_fusion = args.phase == 'fusion'
        checker, recorder = phase_drive(checker, want_fusion)
        if recorder is not None:
            report_drive(checker, recorder, want_fusion)
    return checker.summary()


if __name__ == '__main__':
    sys.exit(main())
