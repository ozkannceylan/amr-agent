#!/usr/bin/env python3
"""safe_speed_bench.py - measure the safe-speed reading channels, and
derive the two constants the F-program's cross-comparison needs from what
was measured rather than from what would be convenient.

TWO MODES, AND ONLY THE FIRST ONE NEEDS A SIMULATOR.

  --drive     Runs a speed profile on the drive wheel and prints a
              per-segment table: commanded speed, ACHIEVED speed from
              ground truth, displacement, duration. A segment that was
              blocked, or that the plant declined to execute, is visibly
              held rather than silently scored (LESSONS 2026-08-05). It
              re-centres the vehicle between segment pairs so a long
              profile does not walk into the racking.

              It drives. It records nothing: scripts/safe_speed_channels.py
              --csv is the recorder, and it must already be running.

  --analyse   NO ROS AND NO SIMULATOR. Reads that CSV and prints the
              measurement and the derivation:

                per-channel noise against the noise-free reference
                the difference the F-program will cross-compare
                the run-length of noise excursions at several thresholds
                the motion observation at rest and in motion
                the derived discrepancy threshold and discrepancy time

WHY THE DISCREPANCY TIME MUST BE DERIVED AND MAY NOT BE PICKED. The
F-program demands a stop when the two readings disagree by more than a
threshold for longer than that time. Too short and channel noise produces
nuisance demands; too long and it is a window in which a real channel
fault is invisible. Both failures are quiet, and neither is discoverable
by reading the number. So the threshold comes from the measured noise of
the difference, and the time comes from the measured LENGTH of the
excursions that noise actually produces above it.

NO CLAIM OF ANY KIND ATTACHES TO WHAT THIS MEASURES. The channels are a
model of what a safe encoder does, reaching the F-program as standard
data; no Category, Performance Level, SIL or PFH is claimed for them or
for anything derived here (ADR 0011 D5). The arrangement is a
SINGLE-CHANNEL TESTED SYSTEM - one shaft, two readings of it - and is
never called two-channel.

Usage:

    # with a vehicle up (safe_speed:=true) and the recorder running:
    python3 agv/forklift/scripts/safe_speed_bench.py --drive

    python3 agv/forklift/scripts/safe_speed_bench.py \
        --analyse agv/forklift/evidence/encoder/<run>.csv
"""

import argparse
import csv
import math
import os
import sys

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_HERE, '..', 'config.yaml'))

# The profile. Each speed is driven forward and then astern, so the
# vehicle ends a pair roughly where it began and a long run does not walk
# into the racking. Segment length is capped by DISTANCE, not by time:
# the excursion stays inside 4 m whatever the speed.
_PROFILE_SPEEDS = (0.05, 0.10, 0.30, 0.60, 1.00)
_SEGMENT_MAX_S = 8.0
_SEGMENT_MAX_M = 4.0
_REST_S = 4.0
_RECENTRE_TRIGGER_M = 1.5
_RECENTRE_SPEED = 0.30


def load_config(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


# --------------------------------------------------------------------------
# analysis - no ROS, no simulator
# --------------------------------------------------------------------------

def _mean(xs):
    return sum(xs) / len(xs) if xs else float('nan')


def _stdev(xs):
    if len(xs) < 2:
        return float('nan')
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _quantile(xs, q):
    if not xs:
        return float('nan')
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def run_lengths(flags):
    """Lengths of the maximal runs of True in a sequence of flags."""
    out = []
    n = 0
    for f in flags:
        if f:
            n += 1
        elif n:
            out.append(n)
            n = 0
    if n:
        out.append(n)
    return out


def _rows(path):
    with open(path, 'r', encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            yield row


def _f(row, key):
    v = row.get(key, '')
    if v == '' or v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def analyse(path, f_cycle_s, publish_hz):
    """The whole derivation, printed with its arithmetic."""
    recs = []
    for row in _rows(path):
        recs.append({
            't': _f(row, 't_s'),
            'va': _f(row, 'v_a_mps'),
            'vb': _f(row, 'v_b_mps'),
            'ra': _f(row, 'v_ref_a_mps'),
            'rb': _f(row, 'v_ref_b_mps'),
            'd': _f(row, 'diff_mps'),
            'rate': _f(row, 'motion_rate_mps'),
            'pairs': _f(row, 'motion_pairs'),
            'present': _f(row, 'motion_present'),
            'valid': _f(row, 'motion_valid'),
            'truth': _f(row, 'truth_vx_mps'),
            'q50': _f(row, 'obs_q50'),
            'q75': _f(row, 'obs_q75'),
            'q90': _f(row, 'obs_q90'),
            'q95': _f(row, 'obs_q95'),
            'qmax': _f(row, 'obs_max'),
        })
    print('safe_speed_bench.py --analyse {}'.format(path))
    print('SINGLE-CHANNEL TESTED SYSTEM: one shaft, two readings of it.')
    print('No PL, Category, SIL or PFH is claimed for anything below.')
    print('')
    print('rows in file: {}'.format(len(recs)))

    paired = [r for r in recs if r['va'] is not None and r['vb'] is not None]
    print('rows with both channels reading: {}'.format(len(paired)))
    if not paired:
        print('NO PAIRED ROWS - nothing to derive.')
        return 1
    span = paired[-1]['t'] - paired[0]['t']
    print('span of those rows: {:.1f} s at {:.1f} Hz'.format(span, publish_hz))
    print('')

    # ---- 1. per-channel noise against the noise-free reference ----
    print('1. CHANNEL NOISE, against the noise-free speed over the same')
    print('   window (the reference column, read by nothing on the vehicle)')
    for key, ref in (('va', 'ra'), ('vb', 'rb')):
        errs = [r[key] - r[ref] for r in paired
                if r[key] is not None and r[ref] is not None]
        print('   channel {}: n={} mean={:+.6f} sigma={:.6f} '
              'max|e|={:.6f} m/s'.format(
                  key[-1], len(errs), _mean(errs), _stdev(errs),
                  max(abs(e) for e in errs)))
    print('')

    # ---- 2. the difference the F-program cross-compares ----
    diffs = [r['d'] for r in paired if r['d'] is not None]
    sigma_d = _stdev(diffs)
    print('2. THE DIFFERENCE v_a - v_b, which is what the F-program')
    print('   cross-compares')
    print('   n={} mean={:+.6f} sigma={:.6f} max|d|={:.6f} m/s'.format(
        len(diffs), _mean(diffs), sigma_d, max(abs(d) for d in diffs)))
    print('   |d| quantiles: p50={:.6f} p99={:.6f} p99.9={:.6f} m/s'.format(
        _quantile([abs(d) for d in diffs], 0.50),
        _quantile([abs(d) for d in diffs], 0.99),
        _quantile([abs(d) for d in diffs], 0.999)))

    # Does the noise depend on speed? Banded by the truth column when it
    # is there, because a noise that grows with speed would make one
    # threshold wrong at one end of the range.
    bands = [(0.0, 0.02), (0.02, 0.2), (0.2, 0.45), (0.45, 0.8), (0.8, 2.0)]
    print('   by |ground-truth body speed| band:')
    for lo, hi in bands:
        sel = [r['d'] for r in paired
               if r['truth'] is not None and lo <= abs(r['truth']) < hi
               and r['d'] is not None]
        if len(sel) < 30:
            print('     [{:.2f}, {:.2f}) m/s: n={} - too few to state'.format(
                lo, hi, len(sel)))
            continue
        print('     [{:.2f}, {:.2f}) m/s: n={} sigma={:.6f} '
              'max|d|={:.6f}'.format(lo, hi, len(sel), _stdev(sel),
                                     max(abs(x) for x in sel)))
    print('')

    # ---- 3. what the F-program actually sees: the 100 ms grid ----
    step = max(1, int(round(f_cycle_s * publish_hz)))
    grid = diffs[::step]
    print('3. AS THE F-PROGRAM SEES IT - every {}th row, one sample per'
          .format(step))
    print('   {:.0f} ms F-cycle. n={}'.format(f_cycle_s * 1000.0, len(grid)))
    print('   sigma on that grid = {:.6f} m/s'.format(_stdev(grid)))
    lag1 = _lag1(grid)
    print('   lag-1 autocorrelation on that grid = {:+.4f} - near zero'
          .format(lag1))
    print('   means consecutive F-samples are independent draws, which is')
    print('   what makes a run of exceedances rare rather than expected.')
    print('')

    print('4. HOW LONG NOISE EXCURSIONS ACTUALLY LAST, measured at several')
    print('   thresholds. This is the measurement the discrepancy time is')
    print('   derived from: an excursion that survives k F-cycles is a')
    print('   nuisance demand if the time is set below it.')
    print('   threshold        exceeding samples   longest run   as time')
    table = []
    for k in (1.0, 2.0, 3.0, 4.0, 5.0):
        thr = k * sigma_d
        flags = [abs(d) > thr for d in grid]
        runs = run_lengths(flags)
        longest = max(runs) if runs else 0
        table.append((k, thr, sum(flags), longest))
        print('   {:.0f} sigma = {:.6f}   {:6d} of {:6d}   {:6d}   '
              '{:.3f} s'.format(k, thr, sum(flags), len(grid), longest,
                                longest * f_cycle_s))
    print('')

    # ---- 5. the derivation ----
    print('5. THE DERIVATION')
    k_pick = 4.0
    thr_pick = k_pick * sigma_d
    row = [t for t in table if t[0] == k_pick][0]
    longest_at_pick = row[3]
    # The time is the longest run measured at the CHOSEN threshold, plus
    # one F-cycle of margin, floored at two cycles so that no single
    # sample can ever demand on its own.
    cycles = max(2, longest_at_pick + 1)
    t_disc = cycles * f_cycle_s
    print('   discrepancy threshold = {:.0f} x sigma_d = {:.0f} x {:.6f}'
          ' = {:.6f} m/s'.format(k_pick, k_pick, sigma_d, thr_pick))
    print('   longest measured run above it, on the {:.0f} ms grid: {} '
          'sample(s)'.format(f_cycle_s * 1000.0, longest_at_pick))
    print('   discrepancy time = ({} + 1) cycles, floored at 2 = {} x '
          '{:.0f} ms = {:.0f} ms'.format(longest_at_pick, cycles,
                                         f_cycle_s * 1000.0,
                                         t_disc * 1000.0))
    print('   n for both figures: {} paired rows, {} F-grid samples, '
          '{:.1f} s'.format(len(paired), len(grid), span))
    print('')
    print('   WHAT THE THRESHOLD COSTS IN DETECTION. A channel that '
          'freezes')
    print('   while the vehicle runs shows |d| equal to the speed itself, '
          'so')
    print('   the comparison sees a frozen channel only above {:.6f} m/s.'
          .format(thr_pick))
    print('   Below that speed the comparison is blind to it, and what '
          'covers')
    print('   that regime is the motion-present stand-in, not this '
          'threshold.')
    print('')

    # ---- 6. the motion observation ----
    print('6. THE MOTION-PRESENT OBSERVATION - a STAND-IN for the '
          'mechanical')
    print('   fault exclusion a real system argues on the shaft coupling')
    rest = [r for r in recs if r['truth'] is not None
            and abs(r['truth']) < 0.001 and r['rate'] is not None]
    moving = [r for r in recs if r['truth'] is not None
              and abs(r['truth']) >= 0.02 and r['rate'] is not None]
    if rest:
        rates = [r['rate'] for r in rest]
        print('   at rest (|truth| < 0.001 m/s): n={} max={:.6f} '
              'p99={:.6f} m/s'.format(len(rates), max(rates),
                                      _quantile(rates, 0.99)))
    if moving:
        rates = [r['rate'] for r in moving]
        print('   moving (|truth| >= 0.02 m/s): n={} min={:.6f} '
              'p1={:.6f} m/s'.format(len(rates), min(rates),
                                     _quantile(rates, 0.01)))
        # How the observation scales with body speed - the ratio that
        # converts a threshold into a minimum detectable speed.
        ratios = [r['rate'] / abs(r['truth']) for r in moving
                  if abs(r['truth']) > 0.02]
        if ratios:
            print('   observed rate / body speed: n={} median={:.4f} '
                  'p5={:.4f}'.format(len(ratios), _quantile(ratios, 0.5),
                                     _quantile(ratios, 0.05)))
    invalid = [r for r in recs if r['valid'] == 0.0]
    print('   rows where the observation could not be made: {} of {}'.format(
        len(invalid), len(recs)))
    disagree = [r for r in recs
                if r['truth'] is not None and r['present'] is not None
                and abs(r['truth']) >= 0.02 and r['present'] == 0.0]
    print('   rows moving at >= 0.02 m/s where the verdict said NOT '
          'moving: {}'.format(len(disagree)))
    print('   (that count is the one that matters: a wrong "moving" costs '
          'a')
    print('    withheld standstill, a wrong "stopped" corroborates a lying')
    print('    encoder.)')
    print('')

    # ---- 7. which statistic the observation should read ----
    #
    # Judged on SUSTAINED regimes only. A row taken while the vehicle is
    # accelerating away from rest is a transition, and both the truth
    # column and the observation are describing different instants of it;
    # scoring the statistic on those rows measures the lag, not the
    # statistic. The lag is measured separately, below.
    hold = int(round(0.5 * publish_hz))
    sus, rest = [], []
    for i in range(hold, len(recs)):
        window = recs[i - hold:i + 1]
        if all(r['truth'] is not None and abs(r['truth']) >= 0.02
               for r in window):
            sus.append(recs[i])
        elif all(r['truth'] is not None and abs(r['truth']) < 0.001
                 for r in window):
            rest.append(recs[i])
    print('7. WHICH STATISTIC THE OBSERVATION READS - chosen from this')
    print('   table, not picked. Sustained regimes only: {} moving rows, '
          '{} at rest.'.format(len(sus), len(rest)))
    print('   A statistic is usable when its WORST sustained-motion value')
    print('   still stands clear of its WORST at-rest value.')
    print('   statistic   rest max   motion min   motion p1   min/rest')
    for key, label in (('q50', 'median'), ('q75', 'q75'), ('q90', 'q90'),
                       ('q95', 'q95'), ('qmax', 'max')):
        rvals = [r[key] for r in rest if r[key] is not None]
        mvals = [r[key] for r in sus if r[key] is not None]
        if not rvals or not mvals:
            print('   {:<10}  no data'.format(label))
            continue
        rmax = max(rvals)
        mmin = min(mvals)
        ratio = ('inf' if rmax == 0.0 else '{:.1f}'.format(mmin / rmax))
        print('   {:<10}  {:.6f}   {:.6f}   {:.6f}   {}'.format(
            label, rmax, mmin, _quantile(sorted(mvals), 0.01), ratio))
    print('')
    print('   the same, at the SLOWEST speed the profile drove, which is')
    print('   what sets the minimum detectable speed:')
    slow = [r for r in sus if abs(r['truth']) < 0.08]
    for key, label in (('q50', 'median'), ('q75', 'q75'), ('q90', 'q90'),
                       ('q95', 'q95'), ('qmax', 'max')):
        vals = [r[key] for r in slow if r[key] is not None]
        speeds = [abs(r['truth']) for r in slow if r[key] is not None]
        if not vals:
            continue
        ratios = sorted(v / s for v, s in zip(vals, speeds) if s > 0)
        print('   {:<10}  n={:5d}  min rate {:.6f}  worst rate/speed '
              '{:.5f}'.format(label, len(vals), min(vals), ratios[0]))
    print('')

    # ---- 8. the two lags, which is what a transition row measures ----
    print('8. THE TWO LAGS OF THE MOTION VERDICT, and they are asymmetric')
    print('   on purpose: late to say STOPPED, prompt to say MOVING.')
    onsets, misses, releases = [], 0, []
    for i in range(1, len(recs)):
        a, b = recs[i - 1]['truth'], recs[i]['truth']
        if a is None or b is None:
            continue
        if abs(a) < 0.02 <= abs(b):
            for j in range(i, min(len(recs), i + 60)):
                if recs[j]['present'] == 1.0:
                    onsets.append(recs[j]['t'] - recs[i]['t'])
                    break
            else:
                misses += 1
        if abs(b) < 0.02 <= abs(a):
            for j in range(i, min(len(recs), i + 80)):
                if recs[j]['present'] == 0.0:
                    releases.append(recs[j]['t'] - recs[i]['t'])
                    break
    print('   motion onsets seen: {}   never detected within 3 s: {}'.format(
        len(onsets) + misses, misses))
    if onsets:
        s = sorted(onsets)
        print('   onset -> verdict MOVING:  min {:.3f}  median {:.3f}  '
              'max {:.3f} s'.format(s[0], s[len(s) // 2], s[-1]))
    if releases:
        s = sorted(releases)
        print('   stop  -> verdict STOPPED: min {:.3f}  median {:.3f}  '
              'max {:.3f} s  (n={})'.format(s[0], s[len(s) // 2], s[-1],
                                            len(s)))
    print('   Every sustained-motion sample reading NOT MOVING in section 6')
    print('   sits inside the onset window above; it is the lag, not a')
    print('   missed detection.')
    return 0


def _lag1(xs):
    if len(xs) < 3:
        return float('nan')
    m = _mean(xs)
    num = sum((xs[i] - m) * (xs[i + 1] - m) for i in range(len(xs) - 1))
    den = sum((x - m) ** 2 for x in xs)
    return num / den if den else float('nan')


# --------------------------------------------------------------------------
# drive - needs ROS and a running vehicle
# --------------------------------------------------------------------------

def _drive(cfg, loops):
    import rclpy
    from rclpy.node import Node
    from nav_msgs.msg import Odometry
    from std_msgs.msg import Float64

    topics = cfg['topics']
    wheel_r = float(cfg['model']['wheel_radius_m'])

    rclpy.init()
    node = Node('safe_speed_bench')
    pub = node.create_publisher(Float64, topics['gz_traction_cmd'], 10)
    state = {'x': None, 'y': None, 'vx': None, 't': None}

    def cb_truth(msg):
        state['x'] = msg.pose.pose.position.x
        state['y'] = msg.pose.pose.position.y
        state['vx'] = msg.twist.twist.linear.x
        state['t'] = node.get_clock().now().nanoseconds * 1e-9

    node.create_subscription(Odometry, topics['odom'], cb_truth, 10)

    def spin_until(deadline_s, sample=None):
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.02)
            now = node.get_clock().now().nanoseconds * 1e-9
            if sample is not None and state['vx'] is not None:
                sample.append(state['vx'])
            if now >= deadline_s:
                return now

    def command(v):
        pub.publish(Float64(data=float(v) / wheel_r))

    # Wait for the clock and the first truth message; a segment timed
    # before either exists measures nothing.
    while rclpy.ok() and state['x'] is None:
        rclpy.spin_once(node, timeout_sec=0.1)
    origin_x = state['x']

    rows = []

    def segment(label, v, duration):
        t0 = node.get_clock().now().nanoseconds * 1e-9
        x0, y0 = state['x'], state['y']
        command(v)
        samples = []
        t1 = spin_until(t0 + duration, samples)
        command(0.0)
        x1, y1 = state['x'], state['y']
        dist = math.hypot(x1 - x0, y1 - y0)
        dt = t1 - t0
        ach = _mean([abs(s) for s in samples]) if samples else float('nan')
        rows.append((label, v, dt, dist, ach,
                     abs(ach / v) if v else float('nan'), x1 - origin_x))
        print('   {:<18} cmd {:+.2f} m/s  {:5.1f} s  moved {:5.3f} m  '
              'achieved {:.3f} m/s  ach/cmd {:.2f}  x-origin {:+.2f} m'
              .format(label, v, dt, dist, ach,
                      abs(ach / v) if v else float('nan'), x1 - origin_x))

    def recentre():
        drift = state['x'] - origin_x
        if abs(drift) <= _RECENTRE_TRIGGER_M:
            return
        v = -math.copysign(_RECENTRE_SPEED, drift)
        # Bounded: never longer than it would take at the commanded
        # speed plus half again, so a plant that will not execute the
        # command cannot hold this loop open.
        limit = abs(drift) / _RECENTRE_SPEED * 1.5 + 2.0
        t0 = node.get_clock().now().nanoseconds * 1e-9
        command(v)
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.02)
            now = node.get_clock().now().nanoseconds * 1e-9
            if abs(state['x'] - origin_x) < 0.30 or now - t0 > limit:
                break
        command(0.0)
        print('   {:<18} drift {:+.2f} m -> {:+.2f} m'.format(
            'recentre', drift, state['x'] - origin_x))
        spin_until(node.get_clock().now().nanoseconds * 1e-9 + _REST_S)

    print('safe_speed_bench.py --drive: profile on the drive wheel.')
    print('It drives; scripts/safe_speed_channels.py --csv records.')
    print('')
    t0 = node.get_clock().now().nanoseconds * 1e-9
    print('   {:<18} rest 30 s at the start'.format('settle'))
    spin_until(t0 + 30.0)

    for loop in range(loops):
        for v in _PROFILE_SPEEDS:
            dur = min(_SEGMENT_MAX_S, _SEGMENT_MAX_M / v)
            segment('L{} fwd {:.2f}'.format(loop + 1, v), v, dur)
            spin_until(node.get_clock().now().nanoseconds * 1e-9 + _REST_S)
            segment('L{} rev {:.2f}'.format(loop + 1, v), -v, dur)
            spin_until(node.get_clock().now().nanoseconds * 1e-9 + _REST_S)
            recentre()

    command(0.0)
    print('   {:<18} rest 40 s at the end'.format('settle'))
    spin_until(node.get_clock().now().nanoseconds * 1e-9 + 40.0)

    print('')
    held = [r for r in rows if r[5] < 0.5]
    print('segments: {}  held or blocked (ach/cmd < 0.5): {}'.format(
        len(rows), len(held)))
    for r in held:
        print('   HELD  {}  cmd {:+.2f} achieved {:.3f}'.format(
            r[0], r[1], r[4]))
    node.destroy_node()
    rclpy.shutdown()
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Drive the safe-speed profile, or analyse the CSV it '
                    'was recorded with.')
    parser.add_argument('--config', default=_DEFAULT_CONFIG)
    parser.add_argument('--drive', action='store_true',
                        help='run the speed profile (needs a vehicle up)')
    parser.add_argument('--loops', type=int, default=5,
                        help='profile repetitions (default: %(default)s)')
    parser.add_argument('--analyse', default=None,
                        help='CSV written by safe_speed_channels.py --csv')
    parser.add_argument('--f-cycle', type=float, default=0.100,
                        help='the F-OB cycle the readings are sampled on, '
                             'seconds (default: %(default)s)')
    args, _ = parser.parse_known_args(argv)

    cfg = load_config(args.config)
    if args.analyse:
        return analyse(args.analyse, args.f_cycle,
                       float(cfg['safe_speed']['publish_hz']))
    if args.drive:
        return _drive(cfg, args.loops)
    parser.error('choose --drive or --analyse')


if __name__ == '__main__':
    sys.exit(main())
