#!/usr/bin/env python3
"""safe_speed_channels.py - the drive shaft, read twice, plus the
corroboration that a claimed zero speed is checked against.

WHAT THIS NODE IS

    /forklift/gz/drive_speed/read_a  ->  /forklift/drive_speed/channel_a
    /forklift/gz/drive_speed/read_b  ->  /forklift/drive_speed/channel_b
    /forklift/scan                  ->  /forklift/drive_speed/motion_present
                                        /forklift/drive_speed/motion_observation_valid

  model.sdf carries two JointStatePublisher instances on
  drive_wheel_joint, each on its own topic. This node puts a READING HEAD
  on each of them - its own mounting phase on the count grid, its own
  read jitter - differences each head's quantised angle over one publish
  interval, and publishes the two resulting tread speeds for the
  F-program to cross-compare.

  Beside them it publishes a MOTION-PRESENT observation taken from the
  navigation lidar, which shares no shaft with the drive axis.

ITS HONEST NAME IS A SINGLE-CHANNEL TESTED SYSTEM

  One shaft, one measured quantity, two readings of it. That is what a
  real safe encoder is, and it is what this models. The arrangement is
  never called two-channel, here or anywhere else in this repository:
  both readings die together with the shaft they read, and the phrase
  would claim a redundancy that does not exist. What the two readings
  buy is DIAGNOSTIC COVERAGE OF THE READING PATH - a head that freezes,
  drifts, or stops publishing is visible to a comparison, where a single
  head's failure is not.

  The hole the shared shaft leaves is closed deliberately and
  separately, by the motion-present observation below.

THE MOTION-PRESENT CHECK IS A STAND-IN, AND IS LABELLED ONE

  A decoupled encoder reports zero on both channels while the vehicle
  rolls, and the cross-comparison agrees perfectly with itself. Real
  systems close that hole with a MECHANICAL FAULT EXCLUSION argued on the
  shaft coupling - a statement about how the thing is built, made once at
  design time, not a monitored signal (docs/safety/SLS-STANDARDS-BASIS.md
  finding F4). This project has no construction argument available, so it
  substitutes an OBSERVATION and says so. That is what the word stand-in
  means here, and it appears beside this check in every artefact.

WHAT THIS NODE IS NOT

  Not a safety function and not a safe measurement. No Category, no
  Performance Level, no SIL, no PFH, no diagnostic-coverage figure is
  claimed for it or for anything downstream of it (ADR 0011 D5). It is
  standard Python reading a simulator's joint state across a bridge and a
  graph, and the readings reach the F-program as STANDARD DATA over the
  process path - a stand-in for a safe measurement channel. It latches
  nothing, limits nothing, stops nothing and inhibits nothing. The
  protective stop, the e-stop chain and safe torque off are onboard and
  hardwired and appear nowhere in this file (invariant 1).

  It does not LIMIT the speed either, and that split is the design. The
  standard program lowers the envelope ceiling; the F-program monitors
  these readings against the SLS limit and demands a stop. That is the
  certified pattern rather than this project's invention
  (SLS-STANDARDS-BASIS.md F5), and it is why no speed value ever leaves
  the F-program - only a demand (ADR 0014).

WHAT A CHANNEL REPORTS

  Drive-wheel TREAD SPEED, |omega| * r, not body speed. The drive wheel
  is steered, so body speed along the heading is tread speed * cos(delta)
  and is therefore never larger; monitoring tread speed against a
  body-speed limit is conservative in the demanding direction, and it
  keeps the steer axis - a second shaft with its own faults - out of the
  speed measurement entirely.

  SIGNED, not absolute. Reverse is a direction and not a fault, and a
  monitor that squares the sign away cannot tell one channel reading
  +0.3 from the other reading -0.3.

FRESHNESS, AND WHY A CHANNEL GOES SILENT RATHER THAN STALE

  A channel whose plant read is older than safe_speed.read_fresh_max_s
  is NOT published, and its differencing state is dropped so the next
  reading is not differenced across the gap. Two reasons, both hard: a
  frozen speed is the one value a monitor must never be handed, and an
  integrator that fills gaps invents distance. The consumer's duty is
  the matching half and is written in config.yaml's `topics:` block - no
  message inside its own window means NO READING, never the last value
  seen.

Usage:

    python3 agv/forklift/scripts/safe_speed_channels.py
    python3 agv/forklift/scripts/safe_speed_channels.py --seed 7
    python3 agv/forklift/scripts/safe_speed_channels.py \
        --csv agv/forklift/evidence/encoder/<run>.csv
    python3 agv/forklift/scripts/safe_speed_channels.py --selftest

`--csv` is the MEASUREMENT facility that EVIDENCE_ODOMETRY.md section 14
is taken with. It logs, per tick, both raw plant angles, both reported
angles, both channel speeds, the noise-free speed over the same window,
and the motion observation. The noise-free column is a REFERENCE for
measurement and is read by nothing on the vehicle.
"""

import argparse
import csv
import math
import os
import random
import sys

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_HERE, '..', 'config.yaml'))

# The joint both reading channels read. Named here rather than taken from
# the message, because a channel that silently started reporting a
# different joint would be a fault this node exists to be incapable of.
_DRIVE_JOINT_KEY = 'drive_joint_name'


def load_config(path):
    """Read the named-constant file. Every value this node uses is in it."""
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


class ReadingHead(object):
    """One reading head on the code disc.

    It holds the two things that make one head's reading differ from
    another's on the same shaft: a fixed MOUNTING PHASE on the count
    grid, drawn once, and a READ JITTER drawn per sample. Both come from
    the node's seeded generator, so a run is reproducible from its seed
    the way a gz sensor bias is.

    The phase is not an error and does not bias the speed: it cancels
    out of a difference of two readings from the same head. What it does
    is de-correlate the QUANTISATION of two heads that would otherwise
    round in lockstep.
    """

    def __init__(self, name, counts_per_rev, jitter_rad, rng):
        self.name = name
        self.count_rad = 2.0 * math.pi / float(counts_per_rev)
        self.jitter_rad = float(jitter_rad)
        self.phase_rad = rng.uniform(0.0, self.count_rad)
        self._rng = rng

    def read(self, true_angle_rad):
        """The angle this head reports for a true shaft angle.

        Jitter is applied to the angle the head is looking at, and the
        quantisation is applied after it, because that is the order the
        physical device does them in: the reading is uncertain, and then
        it is counted.
        """
        noisy = true_angle_rad + self.phase_rad
        if self.jitter_rad > 0.0:
            noisy += self._rng.gauss(0.0, self.jitter_rad)
        return math.floor(noisy / self.count_rad) * self.count_rad


def tread_speed(angle_now_rad, angle_prev_rad, dt_s, radius_m):
    """Signed tread speed from two readings of one head.

    Returns None for a non-positive interval rather than dividing by it:
    a speed formed over no time is not a small speed, it is not a speed.
    """
    if dt_s is None or dt_s <= 0.0:
        return None
    return radius_m * (angle_now_rad - angle_prev_rad) / dt_s


def quantile(sorted_xs, q):
    """The q-quantile of an already sorted list, by nearest rank."""
    if not sorted_xs:
        return None
    i = int(round(q * (len(sorted_xs) - 1)))
    return sorted_xs[min(len(sorted_xs) - 1, max(0, i))]


def motion_observation(prev_ranges, ranges, dt_s, range_min, range_max,
                       min_pairs, q):
    """Absolute range change per second at quantile q, over usable pairs.

    Usable means finite and strictly inside the sensor's own window in
    BOTH scans. A beyond-range return is a measurement of clear space
    and not missing data (LESSONS 2026-08-04), but it carries no
    information about how far anything moved, so it yields no pair - and
    a horizon made entirely of them yields no observation rather than a
    comfortable one.

    WHY A QUANTILE AND NOT THE MEAN, AND WHY NOT THE MEDIAN EITHER. The
    mean is moved by one crossing object. The median was tried and
    measured to FAIL: a straight wall parallel to the direction of
    travel returns the SAME range profile from every point along it -
    r(theta) = d / sin(theta), with no dependence on where the vehicle
    is - so in an aisle a majority of the usable rays do not change at
    all while the vehicle drives, and the median of the changes sits at
    almost nothing. Measured over 6538 sustained-motion samples the
    median came to 0.072 of the body speed with a worst case of 0.00024,
    and 1037 of those samples read as NOT MOVING (EVIDENCE_ODOMETRY.md
    section 15.5). A high quantile asks a different and answerable
    question: did a SUBSTANTIAL MINORITY of the horizon change, which
    the features an aisle does have will do, while a single crossing
    object cannot reach the quantile on its own.

    Returns (rate_mps, n_pairs, quantiles), where quantiles maps a few
    fixed q values to their rate, for the measurement mode. rate_mps is
    None when the observation could not be made, which the caller
    resolves to MOVING.
    """
    if prev_ranges is None or ranges is None:
        return None, 0, {}
    if dt_s is None or dt_s <= 0.0:
        return None, 0, {}
    n = min(len(prev_ranges), len(ranges))
    deltas = []
    for i in range(n):
        a = prev_ranges[i]
        b = ranges[i]
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        if not (range_min < a < range_max and range_min < b < range_max):
            continue
        deltas.append(abs(b - a))
    if len(deltas) < min_pairs:
        return None, len(deltas), {}
    deltas.sort()
    marks = {}
    for qq in (0.50, 0.75, 0.90, 0.95, 1.00):
        marks[qq] = quantile(deltas, qq) / dt_s
    return quantile(deltas, q) / dt_s, len(deltas), marks


def motion_present(rate_mps, threshold_mps):
    """The instantaneous verdict, written so that unknown means moving.

    Affirmative form on purpose: the only way to reach False is an
    observation that was made and came out below the threshold. A None
    rate - no scan, a stale scan, too few usable pairs, an empty horizon
    - falls through to True without a negation anywhere for it to hide
    in (the shape config.yaml's `field:` evaluator uses, and the shape
    LESSONS 2026-08-04 exists to enforce).
    """
    if rate_mps is None:
        return True
    return rate_mps > threshold_mps


def _make_node_class(Node, JointState, LaserScan, Bool, Float64, QoSProfile):

    class SafeSpeedChannels(Node):
        """Two reading heads on one shaft, and one corroboration."""

        def __init__(self, cfg, seed, csv_path):
            super().__init__('safe_speed_channels')
            topics = cfg['topics']
            ss = cfg['safe_speed']
            self._joint = cfg['model'][_DRIVE_JOINT_KEY]
            self._radius = float(ss['rolling_radius_m'])
            self._period = 1.0 / float(ss['publish_hz'])
            self._read_fresh_max = float(ss['read_fresh_max_s'])
            self._scan_fresh_max = float(ss['scan_fresh_max_s'])
            self._min_pairs = int(ss['min_ray_pairs'])
            self._motion_hold = float(ss['motion_hold_s'])
            self._motion_threshold = float(ss['motion_threshold_mps'])

            if seed is None:
                seed = int.from_bytes(os.urandom(4), 'big')
            self._seed = seed
            rng = random.Random(seed)
            self._heads = {
                'a': ReadingHead('a', ss['counts_per_rev'],
                                 ss['read_jitter_rad'], rng),
                'b': ReadingHead('b', ss['counts_per_rev'],
                                 ss['read_jitter_rad'], rng),
            }

            # Latest raw plant read per channel: (stamp_s, angle_rad,
            # plant_velocity_radps). The plant velocity is logged by the
            # measurement mode and read by nothing on the vehicle.
            self._raw = {'a': None, 'b': None}
            # Previous reported angle per channel: (stamp_s, angle_rad).
            self._prev_report = {'a': None, 'b': None}
            self._prev_true = {'a': None, 'b': None}

            self._quantile = float(ss['observation_quantile'])
            self._baseline = int(ss['observation_baseline_scans'])
            # The last few scans, newest last. The observation compares
            # the newest against the one `observation_baseline_scans`
            # back, so the baseline is a config value and not the scan
            # period by accident.
            self._scans = []           # [(stamp_s, ranges, rmin, rmax)]
            self._motion_until = None  # hold deadline, seconds

            qos = QoSProfile(depth=int(cfg['qos']['depth']))
            self._pub_a = self.create_publisher(
                Float64, topics['drive_speed_channel_a'], qos)
            self._pub_b = self.create_publisher(
                Float64, topics['drive_speed_channel_b'], qos)
            self._pub_motion = self.create_publisher(
                Bool, topics['drive_speed_motion_present'], qos)
            self._pub_motion_valid = self.create_publisher(
                Bool, topics['drive_speed_motion_observation_valid'], qos)

            self.create_subscription(
                JointState, topics['gz_drive_speed_read_a'],
                self.cb_read_a, qos)
            self.create_subscription(
                JointState, topics['gz_drive_speed_read_b'],
                self.cb_read_b, qos)
            self.create_subscription(
                LaserScan, topics['scan'], self.cb_scan, qos)

            # GROUND TRUTH, IN THE MEASUREMENT MODE ONLY. The simulator's
            # own pose and body speed are subscribed ONLY when a CSV is
            # asked for, and are written to it and nowhere else. Nothing
            # on the vehicle may read them: an estimate scored against
            # its own input cannot be wrong, and the whole reason this
            # column exists is to score the motion-present observation
            # against a body speed the observation never sees.
            self._truth = None
            self._csv_handle = None
            self._csv = None
            if csv_path:
                from nav_msgs.msg import Odometry
                self.create_subscription(
                    Odometry, topics['odom'], self.cb_truth_odom, qos)
            if csv_path:
                self._csv_handle = open(csv_path, 'w', newline='',
                                        encoding='utf-8')
                self._csv = csv.writer(self._csv_handle)
                self._csv.writerow([
                    't_s', 'true_angle_a_rad', 'true_angle_b_rad',
                    'reported_a_rad', 'reported_b_rad',
                    'v_a_mps', 'v_b_mps', 'v_ref_a_mps', 'v_ref_b_mps',
                    'plant_omega_radps', 'diff_mps',
                    'motion_rate_mps', 'motion_pairs',
                    'motion_present', 'motion_valid',
                    'truth_vx_mps', 'truth_x_m', 'truth_y_m',
                    'obs_q50', 'obs_q75', 'obs_q90', 'obs_q95', 'obs_max'])

            self.create_timer(self._period, self.cb_publish)

            self.get_logger().info(
                'safe-speed reading channels up: SINGLE-CHANNEL TESTED '
                'SYSTEM (one shaft, two readings), seed {}, head phases '
                'a={:.6e} rad b={:.6e} rad, count {:.6e} rad, radius '
                '{:.4f} m, {:.1f} Hz. STAND-IN, no integrity claim: these '
                'readings reach the F-program as standard data.'.format(
                    self._seed, self._heads['a'].phase_rad,
                    self._heads['b'].phase_rad,
                    self._heads['a'].count_rad, self._radius,
                    1.0 / self._period))
            self.get_logger().info(
                'motion-present observation is a STAND-IN for the '
                'mechanical fault exclusion a real system argues on the '
                'shaft coupling; threshold {:.6f} m/s, >= {} ray pairs, '
                'every uncertainty resolves to MOVING.'.format(
                    self._motion_threshold, self._min_pairs))

        # ---- subscriptions ------------------------------------------

        def _now(self):
            return self.get_clock().now().nanoseconds * 1e-9

        def _store_read(self, key, msg):
            try:
                idx = list(msg.name).index(self._joint)
            except ValueError:
                # The read carries some other joint. Dropping it is the
                # only honest option: this node does not guess which
                # column is the drive shaft.
                return
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            vel = msg.velocity[idx] if idx < len(msg.velocity) else float('nan')
            self._raw[key] = (stamp, msg.position[idx], vel)

        def cb_read_a(self, msg):
            self._store_read('a', msg)

        def cb_read_b(self, msg):
            self._store_read('b', msg)

        def cb_truth_odom(self, msg):
            """Measurement mode only. Logged; never read by this node."""
            self._truth = (msg.twist.twist.linear.x,
                           msg.pose.pose.position.x,
                           msg.pose.pose.position.y)

        def cb_scan(self, msg):
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            if self._scans and stamp == self._scans[-1][0]:
                return
            self._scans.append((stamp, list(msg.ranges),
                                float(msg.range_min), float(msg.range_max)))
            # One more than the baseline needs, so a longer baseline is a
            # config change and not a code change.
            while len(self._scans) > self._baseline + 4:
                self._scans.pop(0)

        # ---- the tick ------------------------------------------------

        def _channel(self, key, now):
            """One channel's reading, or None with its state dropped."""
            raw = self._raw[key]
            if raw is None or (now - raw[0]) > self._read_fresh_max:
                self._prev_report[key] = None
                self._prev_true[key] = None
                return None, None, None
            stamp, angle, _vel = raw
            reported = self._heads[key].read(angle)
            prev = self._prev_report[key]
            prev_true = self._prev_true[key]
            speed = None
            ref = None
            if prev is not None and stamp > prev[0]:
                speed = tread_speed(reported, prev[1], stamp - prev[0],
                                    self._radius)
                ref = tread_speed(angle, prev_true[1], stamp - prev_true[0],
                                  self._radius)
            self._prev_report[key] = (stamp, reported)
            self._prev_true[key] = (stamp, angle)
            return speed, reported, ref

        def _motion(self, now):
            """The observation, its validity, and the held verdict."""
            rate = None
            pairs = 0
            marks = {}
            fresh = (self._scans
                     and (now - self._scans[-1][0]) <= self._scan_fresh_max)
            if fresh and len(self._scans) > self._baseline:
                new = self._scans[-1]
                old = self._scans[-1 - self._baseline]
                rate, pairs, marks = motion_observation(
                    old[1], new[1], new[0] - old[0], new[2], new[3],
                    self._min_pairs, self._quantile)
            valid = rate is not None
            instant = motion_present(rate, self._motion_threshold)
            if instant:
                self._motion_until = now + self._motion_hold
            held = instant or (self._motion_until is not None
                               and now < self._motion_until)
            return held, valid, rate, pairs, marks

        def cb_publish(self):
            now = self._now()
            v_a, rep_a, ref_a = self._channel('a', now)
            v_b, rep_b, ref_b = self._channel('b', now)
            held, valid, rate, pairs, marks = self._motion(now)

            if v_a is not None:
                self._pub_a.publish(Float64(data=float(v_a)))
            if v_b is not None:
                self._pub_b.publish(Float64(data=float(v_b)))
            self._pub_motion.publish(Bool(data=bool(held)))
            self._pub_motion_valid.publish(Bool(data=bool(valid)))

            if self._csv is not None:
                raw_a = self._raw['a']
                raw_b = self._raw['b']
                diff = (v_a - v_b) if (v_a is not None and v_b is not None) \
                    else ''
                self._csv.writerow([
                    '{:.6f}'.format(now),
                    '' if raw_a is None else '{:.9f}'.format(raw_a[1]),
                    '' if raw_b is None else '{:.9f}'.format(raw_b[1]),
                    '' if rep_a is None else '{:.9f}'.format(rep_a),
                    '' if rep_b is None else '{:.9f}'.format(rep_b),
                    '' if v_a is None else '{:.9f}'.format(v_a),
                    '' if v_b is None else '{:.9f}'.format(v_b),
                    '' if ref_a is None else '{:.9f}'.format(ref_a),
                    '' if ref_b is None else '{:.9f}'.format(ref_b),
                    '' if raw_a is None else '{:.9f}'.format(raw_a[2]),
                    '' if diff == '' else '{:.9f}'.format(diff),
                    '' if rate is None else '{:.9f}'.format(rate),
                    pairs, int(held), int(valid),
                    '' if self._truth is None else '{:.9f}'.format(
                        self._truth[0]),
                    '' if self._truth is None else '{:.9f}'.format(
                        self._truth[1]),
                    '' if self._truth is None else '{:.9f}'.format(
                        self._truth[2])]
                    + ['' if q not in marks else '{:.9f}'.format(marks[q])
                       for q in (0.50, 0.75, 0.90, 0.95, 1.00)])
                self._csv_handle.flush()

        def destroy_node(self):
            if self._csv_handle is not None:
                self._csv_handle.close()
                self._csv_handle = None
            return super().destroy_node()

    return SafeSpeedChannels


def _selftest():
    """Checks that need no simulator, no ROS and no network."""
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    rng = random.Random(1)
    head = ReadingHead('a', 4096, 0.0, rng)
    q = 2.0 * math.pi / 4096

    # Quantisation: a reported angle always sits on the count grid,
    # offset by the head's own phase.
    r0 = head.read(0.0)
    check('reported angle on the count grid',
          abs(r0 / q - round(r0 / q)) < 1e-9)

    # A head with no jitter is monotone in the true angle and never
    # reports more than one count ahead of it.
    ok = True
    prev = None
    for i in range(2000):
        ang = i * q / 7.0
        rep = head.read(ang)
        if prev is not None and rep < prev:
            ok = False
        if not (-q <= rep - (ang + head.phase_rad) <= 0.0 + 1e-12):
            ok = False
        prev = rep
    check('jitter-free head is monotone and within one count', ok)

    # Two heads on one shaft do not report the same angle at every
    # sample - that is the point of the mounting phase.
    rng2 = random.Random(4)
    h1 = ReadingHead('a', 4096, 0.0, rng2)
    h2 = ReadingHead('b', 4096, 0.0, rng2)
    # Swept finely enough to cross both heads' count boundaries: a coarse
    # sweep can step over one head's boundary and land past the other's,
    # and then a real disagreement never shows.
    diffs = {round((h1.read(i * q / 997.0) - h2.read(i * q / 997.0)) / q)
             for i in range(3000)}
    check('two phased heads do not agree at every sample', len(diffs) > 1)

    # Speed: no interval is not a small speed.
    check('zero interval yields no speed',
          tread_speed(1.0, 0.0, 0.0, 0.12) is None)
    check('speed sign follows the shaft',
          tread_speed(-1.0, 0.0, 1.0, 0.5) == -0.5)

    # The motion observation: an all-inf horizon is not "no change".
    inf = float('inf')
    rate, pairs, _ = motion_observation([inf] * 360, [inf] * 360, 0.1,
                                        0.1, 8.0, 36, 0.90)
    check('empty horizon yields no observation', rate is None and pairs == 0)
    check('no observation means MOVING', motion_present(rate, 1e-6) is True)

    # Too few pairs is also no observation.
    ranges_a = [inf] * 360
    ranges_b = [inf] * 360
    for i in range(10):
        ranges_a[i] = 3.0
        ranges_b[i] = 3.0
    rate, pairs, _ = motion_observation(ranges_a, ranges_b, 0.1, 0.1, 8.0,
                                        36, 0.90)
    check('ten pairs is fewer than the minimum', rate is None and pairs == 10)

    # A majority that does not move, with a minority that does, reads as
    # not moving: the median is what makes a crossing pedestrian not a
    # statement about the vehicle.
    ranges_a = [3.0] * 360
    ranges_b = [3.0] * 360
    for i in range(60):
        ranges_b[i] = 3.0 + 0.5
    rate, pairs, marks = motion_observation(ranges_a, ranges_b, 0.1, 0.1,
                                            8.0, 36, 0.75)
    check('a sixth of the horizon moving does not reach q75',
          rate == 0.0 and pairs == 360)
    check('the same minority does reach the maximum',
          abs(marks[1.00] - 5.0) < 1e-9)

    # A majority that moves reads as moving.
    ranges_b = [3.02] * 360
    rate, _, _ = motion_observation(ranges_a, ranges_b, 0.1, 0.1, 8.0, 36,
                                    0.75)
    check('the quantile follows a moving majority', abs(rate - 0.2) < 1e-9)

    # Beyond-range in one scan only still yields no pair for that ray.
    ranges_b = [3.0] * 360
    ranges_b[0] = inf
    rate, pairs, _ = motion_observation(ranges_a, ranges_b, 0.1, 0.1, 8.0,
                                        36, 0.75)
    check('a ray beyond range in one scan yields no pair', pairs == 359)

    for name in ran:
        print('{}  {}'.format('FAIL' if name in fails else 'pass', name))
    # The count is derived from the checks that ran, not typed beside
    # them: a hand-written denominator is how a test silently leaves the
    # denominator behind (LESSONS 2026-07-28).
    print('{}/{} checks passed'.format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Two reading channels on one drive shaft - a '
                    'single-channel tested system - plus the '
                    'motion-present stand-in. Publishes readings; '
                    'decides nothing.')
    parser.add_argument('--config', default=_DEFAULT_CONFIG,
                        help='named-constant file (default: %(default)s)')
    parser.add_argument('--seed', type=int, default=None,
                        help='fix the head phases and the jitter draw, so '
                             'a measurement is reproducible. Empty is the '
                             'default and is what a demonstration uses.')
    parser.add_argument('--csv', default=None,
                        help='measurement facility: per-tick record, '
                             'including a noise-free reference column no '
                             'vehicle node reads')
    parser.add_argument('--selftest', action='store_true',
                        help='run the checks that need no simulator')
    args, ros_argv = parser.parse_known_args(argv)

    if args.selftest:
        return _selftest()

    cfg = load_config(args.config)

    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from sensor_msgs.msg import JointState, LaserScan
    from std_msgs.msg import Bool, Float64

    node_class = _make_node_class(Node, JointState, LaserScan, Bool,
                                  Float64, QoSProfile)

    rclpy.init(args=[sys.argv[0]] + ros_argv)
    node = node_class(cfg, args.seed, args.csv)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
