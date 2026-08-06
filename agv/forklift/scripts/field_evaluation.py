#!/usr/bin/env python3
"""field_evaluation.py - protective-field evaluation for the forklift twin.

    agv/forklift/FIELD-EVALUATION.md is the AUTHORITY for everything this
    node does. agv/forklift/config.yaml `field:` holds every constant.
    plc/forklift-safety/SPEC.md section 7.2 is the consumer contract.
    THIS FILE BUILDS PHASES 1 AND 2 OF THAT DESIGN AND NOTHING ELSE:
    the protective field and its dedicated link (phase 1, m5-12b) and
    the warning field and its topic (phase 2, m5-47). Phase 3 - case
    selection A/B/C - is not built, and no speed is enforced here.

WHAT THIS NODE IS

  A MODEL OF WHAT A SAFETY-RATED SCANNER DOES INSIDE ITS OWN HOUSING.
  A device of the class modelled here takes its own rays, tests them
  against a configured protective-field contour, and drives an OSSD pair.
  This node does that arithmetic in Python, off two rendered depth images
  that have crossed a bridge and a ROS graph, and hands the verdict to a
  STAND-IN FOR WIRING:

    Gazebo gpu_lidar x2 (10 Hz, the NON-SAFE MEASUREMENT channels)
      -> this node: contour, per-device verdict, OSSD-equivalent pair,
                    union aggregation, failure rules
        -> one TCP connection, WSL client -> Windows listener, port 45015
          -> the stand-in writer -> SafetyInputStandIn.ZoneDeviceCircuitClosed
            -> the F-program latches ZoneStopDemand

  It is the piece that makes M5 criterion (a)'s chain ORIGINATE IN GAZEBO
  rather than in a script or at a console.

WHAT THIS NODE IS NOT, AND THIS IS NOT A DISCLAIMER BUT A SPECIFICATION

  IT IS NOT A SAFETY FUNCTION AND CARRIES NO CLAIM: no Category, no
  Performance Level, no SIL, no PFH, no channel count, no diagnostic
  coverage (ADR 0011 D5, FIELD-EVALUATION.md section 10). One software
  process, one scan source per device, no redundancy, no test pulses, no
  fault reaction beyond the verdicts below. Every PL and Category named
  in the documents behind it is a PLr TARGET out of docs/safety/, never
  an achievement. No depth or response time here is a figure any machine
  is characterised by.

  IT LATCHES NOTHING AND STOPS NOTHING. It reports LEVELS. The latch, the
  monitored reset and the observable stop are all downstream and all
  already specified (SPEC sections 5 and 7). The protective stop, the
  e-stop chain and safe torque off are onboard and hardwired
  (invariant 1).

TWO FIELDS, AND THEY LEAVE THIS NODE BY DIFFERENT ROADS

  PROTECTIVE FIELD - intrusion opens the zone channel and stops the
  vehicle. It crosses ONLY the dedicated TCP link below. No topic, ever.

  WARNING FIELD - larger (3.35 m against 1.35 m, both derived in
  FIELD-EVALUATION.md sections 4 and 6.1), and occupation demands a
  SPEED REDUCTION to the creep ceiling rather than a stop. It is process
  data: it crosses one non-safe ROS topic, published AT THE TICK so that
  its absence is visible, and its consumer owes a stale rule of its own.
  This node enforces no speed and latches nothing, in either field.

  The two contours carry the same clips and the warning depth is the
  larger, so the warning boundary is at or beyond the protective one at
  every ray and the verdicts are NESTED: every protective intrusion is
  also a warning occupation. The node checks that at contour build and
  logs the count, rather than assuming it.

THE PROTECTIVE VERDICT HAS NO ROS TOPIC, AND THAT IS THE DESIGN

  config.yaml's `topics:` block carries an owner ruling (m5-06,
  2026-07-30): "every channel a subscriber can reach is a measurement
  channel. The safe channel has no topic on either transport, ever."
  The protective verdict is the safe-channel equivalent, so it crosses
  ONLY the dedicated SPEC 7.2 link - exactly as a real device's OSSD pair
  crosses only its own copper, and for the same reason: a safe-shaped
  output must never appear where a process subscriber can quietly become
  its consumer. scripts/check_sensor_frames.py section 4 checks that rule
  by machine, so publishing one would fail a committed check.

  The evidence for a verdict is therefore this node's TRANSITION LOG plus
  the writer's session log, correlated (SPEC section 7.6), and not a
  topic echo.

THE THREE CLASSES OF SAMPLE, AND WHY THE MIDDLE ONE IS NOT MISSING DATA

  A BEYOND-RANGE RETURN IS A MEASUREMENT - "clear to range_max" - AND NOT
  AN ABSENCE. On 2026-07-29 this vehicle's obstacle evaluator treated an
  all-inf forward sector as "no valid data" and the fail-safe latched a
  process stop in open space, with a healthy 10 Hz scan behind the false
  verdict (docs/LESSONS.md). The demanding direction is NOT "stop on
  everything"; it is "never call unknown clear", and a beyond-range
  return is not unknown.

  Validity is written AFFIRMATIVELY with the fault in the ELSE branch
  (LESSONS 2026-07-27), so a NaN - which makes every comparison false -
  falls through to the fault class rather than passing as a value, and no
  later edit can re-open that trap by negating a test.

THE SAFE DIRECTION IS THE DEMANDING ONE: UNKNOWN MEANS INTRUSION

  Applied to every failure, per FIELD-EVALUATION.md section 8:
    dead scanner       -> intrusion      (only a fresh scan proves clear)
    stale but arriving -> intrusion      (a republished old scan is a
                                          picture of a world that may
                                          have changed)
    one device down    -> intrusion      (coverage is a property of the
                                          UNION; driving on the surviving
                                          half is driving with known
                                          blind sectors)
    invalid samples    -> intrusion      (an invalid ray cannot prove its
                                          sector clear)
    empty horizon      -> CLEAR          (see above: it is a measurement)

  The verdict BOOTS INTRUSION and stays there until a fresh, advancing,
  fully-valid, fully-clear scan has been seen from every device.
  "Not yet proven stale" is not "alive" (LESSONS 2026-07-28).

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 agv/forklift/scripts/field_evaluation.py \
      [--config PATH] [--model PATH] [--ros-args -p use_sim_time:=true]
"""

import argparse
import errno
import math
import os
import select
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import rclpy
import yaml
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_DEFAULT_CONFIG = os.path.join(_FORKLIFT_DIR, 'config.yaml')
_DEFAULT_MODEL = os.path.join(_FORKLIFT_DIR, 'model.sdf')

#: The two devices this evaluation covers. The union of the two IS the
#: coverage (EVIDENCE_SENSOR_COVERAGE.md); neither alone watches the
#: circle, which is why one failed device demands a stop.
DEVICES = ('front', 'rear')

#: A sample either measures a distance, measures that the path is clear to
#: the end of the sensor's window, or is not an answer at all.
CLASS_DISTANCE = 'distance'
CLASS_CLEAR = 'clear'
CLASS_INVALID = 'invalid'


def load_config(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def utc_stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


# ------------------------------------------------------------------------ #
# The scanner poses come out of model.sdf, never out of a mirror.
#
# config.yaml mirrors two SCALARS of the plan outline and says so; it
# mirrors no pose, because sensor_tf.py already established the rule for
# this directory: the transforms are read from the model file itself so
# they cannot drift from the geometry. The same file, the same parse.
# ------------------------------------------------------------------------ #

def _parse_pose(text):
    if not text:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    parts = [float(v) for v in text.split()]
    while len(parts) < 6:
        parts.append(0.0)
    return tuple(parts[:6])


def read_scanner_mounts(model_path):
    """Return {device: (x, y, yaw)} in the vehicle frame, from model.sdf.

    The link carries the mount pose and the <sensor> carries a further
    pose inside it; both are composed, so a sensor moved inside its link
    later cannot silently break this. Only planar terms are used - the
    scan is planar and both scanners are declared level.
    """
    root = ET.parse(model_path).getroot()
    model = root.find('model')
    if model is None:
        raise RuntimeError('{}: no <model> element'.format(model_path))
    wanted = {'safety_scanner_{}'.format(d): d for d in DEVICES}
    mounts = {}
    for link in model.findall('link'):
        lx, ly, _lz, _lr, _lp, lyaw = _parse_pose(link.findtext('pose'))
        for sensor in link.findall('sensor'):
            device = wanted.get(sensor.get('name'))
            if device is None:
                continue
            sx, sy, _sz, _sr, _sp, syaw = _parse_pose(sensor.findtext('pose'))
            cos_y, sin_y = math.cos(lyaw), math.sin(lyaw)
            mounts[device] = (lx + cos_y * sx - sin_y * sy,
                              ly + sin_y * sx + cos_y * sy,
                              lyaw + syaw)
    missing = [d for d in DEVICES if d not in mounts]
    if missing:
        raise RuntimeError(
            '{}: no <sensor name="safety_scanner_{}"> found. The field '
            'evaluation cannot be built against a model whose devices it '
            'cannot locate.'.format(model_path, '/'.join(missing)))
    return mounts


# ------------------------------------------------------------------------ #
# The contour
# ------------------------------------------------------------------------ #

def classify_sample(sample, range_min, range_max):
    """Put one range into one of the three classes, AFFIRMATIVELY.

    Written as FIELD-EVALUATION.md section 8 writes it:

        in_range_return := (range_min <= r) AND (r <= range_max)
        clear_beyond    := (r = +inf)
        valid           := in_range_return OR clear_beyond
        ELSE            -> invalid          (NaN, negative, finite below
                                             range_min, finite above
                                             range_max)

    Both valid classes are positive tests, so NaN reaches neither and
    lands in INVALID. That ordering is the whole guard: under a negated
    out-of-window test a NaN would read as plausible and pass a broken
    sensor as a value (LESSONS 2026-07-27).
    """
    if range_min <= sample and sample <= range_max:
        return CLASS_DISTANCE
    if math.isinf(sample) and sample > 0.0:
        return CLASS_CLEAR
    return CLASS_INVALID


class Contour(object):
    """ONE field of one device, as a boundary radius per ray.

    Two instances exist per device and they differ only in the depth of
    the rectangle they are built from: the PROTECTIVE field, whose
    intrusion opens the zone channel and stops the vehicle, and the
    WARNING field, larger, whose occupation trips a SPEED REDUCTION and
    stops nothing (FIELD-EVALUATION.md section 6.1). Same corridor half
    width, same self-return clips, same class - because they are the same
    kind of object, and a warning field drawn past the vehicle's own
    returns is permanently occupied for exactly the reason a protective
    one is permanently violated.

    Since the warning depth is strictly greater than the protective
    depth and both carry the same clips, the warning boundary is >= the
    protective boundary at every ray. THE TWO VERDICTS ARE THEREFORE
    NESTED, NEVER INDEPENDENT: every protective intrusion is also a
    warning occupation, by construction rather than by a coded rule.

    A real device's protective field IS a contour: for every bearing the
    head fires at, how far out the monitored region reaches. This class
    is that table, derived once per device from

      - the phase-1 static rectangle in the VEHICLE frame (the two
        corridors: the plan outline grown by `protective_depth_m` fore
        and aft and to `corridor_half_width_m` either side), and
      - the measured self-return clips of config `field.self_return_clips`,
        which cap the boundary over the bearing bands where the vehicle's
        own body stands in this device's aperture (R8).

    The rectangle is expressed in the vehicle frame and the mount pose is
    FIXED, so the resulting contour is rigidly fixed in the device's own
    frame exactly as FIELD-EVALUATION.md section 6 requires. Deriving it
    in the vehicle frame is what lets the depths be stated from the
    outline, which is how they were derived.

    A bearing whose boundary falls below the sensor's range_min has NO
    LIVE FIELD there: no sample can lie inside it. Excluded sectors are
    expressed that way rather than as a special case in the loop.
    """

    def __init__(self, mount, rect, clips, angle_min, angle_increment,
                 count, range_min, range_max, label='protective'):
        self.label = label
        self.range_min = range_min
        self.range_max = range_max
        mx, my, myaw = mount
        x_lo, x_hi, y_lo, y_hi = rect
        self.boundary = []
        self.live = []
        for index in range(count):
            theta = angle_min + index * angle_increment
            heading = myaw + theta
            radius = self._rect_exit(mx, my, heading, x_lo, x_hi, y_lo, y_hi)
            for clip in clips:
                lo, hi, cap = clip
                if lo <= math.degrees(theta) <= hi:
                    radius = min(radius, cap)
            radius = min(radius, range_max)
            self.boundary.append(radius)
            self.live.append(radius >= range_min)

    @staticmethod
    def _rect_exit(px, py, heading, x_lo, x_hi, y_lo, y_hi):
        """Distance from an interior point to the rectangle along `heading`.

        Both scanners sit inside the corridor rectangle by construction
        (they are on the vehicle, and the rectangle contains the vehicle),
        so exactly one positive exit distance exists on each axis and the
        nearer of the two is the boundary.
        """
        dx, dy = math.cos(heading), math.sin(heading)
        best = float('inf')
        if dx > 1e-12:
            best = min(best, (x_hi - px) / dx)
        elif dx < -1e-12:
            best = min(best, (x_lo - px) / dx)
        if dy > 1e-12:
            best = min(best, (y_hi - py) / dy)
        elif dy < -1e-12:
            best = min(best, (y_lo - py) / dy)
        return best

    def live_count(self):
        return sum(1 for flag in self.live if flag)


# ------------------------------------------------------------------------ #
# One device's evaluation, including its OSSD-equivalent pair
# ------------------------------------------------------------------------ #

class DeviceEvaluation(object):
    """Everything this node knows about one scanner, and its verdict.

    THE OSSD-EQUIVALENT PAIR, AND WHAT IT BUYS - STATED HONESTLY.
    A real scanner presents two driven outputs, both read, so a single
    failure is detectable. The equivalent here is `(a_clear, b_intrusion)`
    - antivalent, carried with a monotonically increasing sequence number
    and the triggering scan's stamp, in ONE record formed atomically.
    They are accumulated by two SEPARATE accumulators in one pass, so a
    coding slip on one path can actually diverge from the other, and any
    record where a == b is a discrepancy, is a device-evaluation fault on
    the spot, and reads INTRUSION. Discrepancy tolerance is ZERO records:
    the pair travels in one record, so no timing skew exists to tolerate.

    WHAT IT DOES NOT BUY: integrity. Both channels are computed by one
    process from one scan and share every failure of the rays and of the
    process. That is the sharing README.md already declares, and it is why
    no Category is claimed.
    """

    def __init__(self, name, mount, params):
        self.name = name
        self.mount = mount
        self.params = params

        self.contour = None
        self.warning_contour = None
        self.geometry_key = None

        self.seq = 0
        self.last_stamp_s = None
        self.last_rx_monotonic = None
        self.advancing = False        # boots FALSE: one stamp proves nothing

        # The verdict BOOTS INTRUSION and is held there until a fresh,
        # advancing, fully-valid, fully-clear scan has been seen three
        # times running. "Not yet proven stale" is not "alive".
        self.field_clear = False
        self.clear_run = 0

        self.faulted = False
        self.fault_reason = 'boot: no scan yet seen from this device'
        self.below_threshold_run = 0

        self.discrepancy = False
        self.last_record = None
        self.last_invalid_fraction = 0.0
        self.last_intrusion_count = 0

        # THE WARNING FIELD (phase 2). It BOOTS OCCUPIED for the same
        # reason the protective verdict boots INTRUSION: nothing has yet
        # proved it clear, and the demanding direction for a speed
        # reduction is that the reduction is in force.
        #
        # `warning_dirty` is what the last scan saw. `warning_occupied`
        # is the REPORTED level, which is slower to release than the scan
        # by SF-04's 2 s clear-hold; `warning_clear_since` is the steady
        # time at which the hold started, and is None whenever the hold
        # is not running. Steady time, not the simulation clock, for the
        # reason written at the evaluation tick.
        self.warning_dirty = True
        self.warning_occupied = True
        self.warning_clear_run = 0
        self.warning_clear_since = None
        self.last_warning_count = 0
        self.last_warning_nearest = None

    # -------------------------------------------------------------- #

    def ingest(self, msg, rx_monotonic, log):
        """Take one scan. Returns a list of log lines to emit."""
        lines = []
        self.seq += 1
        stamp_s = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

        # Rule 3: stamps must ADVANCE. A republished old scan is a picture
        # of a world that may have changed, and it arrives looking exactly
        # like a fresh one.
        advancing = (self.last_stamp_s is None
                     or stamp_s > self.last_stamp_s)
        if self.last_stamp_s is None:
            advancing = True          # the first scan cannot be compared
        if advancing != self.advancing:
            lines.append(('DEVICE', '{} stamps {} (seq={} stamp={:.6f})'.format(
                self.name, 'advancing' if advancing else 'FROZEN',
                self.seq, stamp_s)))
        self.advancing = advancing
        self.last_stamp_s = stamp_s
        self.last_rx_monotonic = rx_monotonic

        window_ok = (math.isfinite(msg.range_min) and math.isfinite(msg.range_max)
                     and msg.range_min < msg.range_max)
        geometry_ok = (bool(msg.ranges) and math.isfinite(msg.angle_increment)
                       and msg.angle_increment != 0.0
                       and math.isfinite(msg.angle_min))
        if not (window_ok and geometry_ok):
            # A scan whose own validity window or geometry is unusable
            # cannot classify a single sample, so it is UNUSABLE and not
            # clear. This is the demanding direction.
            return lines + self._set_fault(
                '{} scan structurally unusable (range window ok={}, '
                'geometry ok={})'.format(self.name, window_ok, geometry_ok))

        key = (msg.angle_min, msg.angle_increment, len(msg.ranges),
               msg.range_min, msg.range_max)
        if key != self.geometry_key:
            self.contour = Contour(
                self.mount, self.params['rect'], self.params['clips'],
                msg.angle_min, msg.angle_increment, len(msg.ranges),
                msg.range_min, msg.range_max, label='protective')
            self.warning_contour = Contour(
                self.mount, self.params['warning_rect'], self.params['clips'],
                msg.angle_min, msg.angle_increment, len(msg.ranges),
                msg.range_min, msg.range_max, label='warning')
            self.geometry_key = key
            for contour in (self.contour, self.warning_contour):
                lines.append(('DEVICE', (
                    '{} {} contour built: {} rays, {} of them with a live '
                    'field, boundary {:.3f}..{:.3f} m over the live rays, '
                    'mount (x={:.3f} y={:.3f} yaw={:.4f} rad), scan window '
                    '{:.2f}..{:.2f} m').format(
                        self.name, contour.label, len(msg.ranges),
                        contour.live_count(),
                        min(b for b, l in zip(contour.boundary,
                                              contour.live) if l),
                        max(b for b, l in zip(contour.boundary,
                                              contour.live) if l),
                        self.mount[0], self.mount[1], self.mount[2],
                        msg.range_min, msg.range_max)))
            # NESTING, CHECKED RATHER THAN ASSUMED. The warning boundary
            # must be at or beyond the protective boundary at every ray;
            # if it ever is not, a ray could be a protective intrusion
            # and not a warning occupation, and the speed reduction that
            # is supposed to precede the stop would not have happened.
            breaches = sum(1 for w, p in zip(self.warning_contour.boundary,
                                             self.contour.boundary)
                           if w < p - 1e-9)
            lines.append(('DEVICE', (
                '{} nesting check: {} ray(s) where the warning boundary is '
                'inside the protective one (must be 0)').format(
                    self.name, breaches)))

        # ---- the one pass over the rays ----
        #
        # TWO SEPARATE ACCUMULATORS, deliberately: `intrusion_count` and
        # `saw_intrusion` are written at the same sites but are not the
        # same variable, so the antivalent pair below is formed from two
        # paths rather than from one value and its negation.
        intrusion_count = 0
        saw_intrusion = False
        invalid_count = 0
        nearest = None
        warning_count = 0
        warning_nearest = None

        boundary = self.contour.boundary
        live = self.contour.live
        w_boundary = self.warning_contour.boundary
        w_live = self.warning_contour.live
        r_min, r_max = msg.range_min, msg.range_max

        for index, sample in enumerate(msg.ranges):
            if index >= len(boundary):
                break
            sample_class = classify_sample(sample, r_min, r_max)
            if sample_class == CLASS_CLEAR:
                # A MEASUREMENT: clear to range_max. It proves the whole
                # ray, so it can never make a field dirty - protective or
                # warning. This is the 2026-07-29 lesson, in one branch.
                continue
            if sample_class == CLASS_DISTANCE:
                if w_live[index] and sample <= w_boundary[index]:
                    warning_count += 1
                    if warning_nearest is None or sample < warning_nearest:
                        warning_nearest = sample
                if live[index] and sample <= boundary[index]:
                    intrusion_count += 1
                    saw_intrusion = True
                    if nearest is None or sample < nearest:
                        nearest = sample
                continue
            # ELSE: not an answer at all.
            invalid_count += 1
            # An invalid ray cannot prove its sector clear, so inside a
            # live field sector it counts as an intrusion of THAT field.
            # Outside one it raises nothing - there is no field there to
            # be uncertain about. Applied to both fields separately,
            # because their live sectors are not the same set.
            if w_live[index]:
                warning_count += 1
            if live[index]:
                intrusion_count += 1
                saw_intrusion = True

        total = len(msg.ranges)
        invalid_fraction = (invalid_count / float(total)) if total else 1.0
        self.last_invalid_fraction = invalid_fraction
        self.last_intrusion_count = intrusion_count
        self.last_warning_count = warning_count
        self.last_warning_nearest = warning_nearest

        # ---- the warning field's own book-keeping, per scan ----
        #
        # OCCUPATION ASSERTS ON ONE SCAN, exactly like the protective
        # verdict and for the same reason (the simulated sensor declares
        # no noise model). RELEASE IS THE SLOW ONE: it needs the same 3
        # fully-clear scans AND THEN SF-04's 2 s clear-hold, which is
        # started here and expires in warning_verdict() on steady time.
        # The hold is restarted from zero by a single dirty scan.
        self.warning_dirty = (warning_count > 0)
        if self.warning_dirty:
            self.warning_clear_run = 0
            self.warning_clear_since = None
            if not self.warning_occupied:
                lines.append(('WARNING', (
                    '{} warning field OCCUPIED on one scan: {} ray(s) inside '
                    'the warning contour, nearest {:.3f} m (seq={} '
                    'stamp={:.6f})').format(
                        self.name, warning_count,
                        warning_nearest if warning_nearest is not None
                        else float('nan'), self.seq, stamp_s)))
            self.warning_occupied = True
        else:
            self.warning_clear_run += 1
            if (self.warning_clear_run >= self.params['clear_debounce_scans']
                    and self.warning_clear_since is None):
                self.warning_clear_since = rx_monotonic
                if self.warning_occupied:
                    lines.append(('WARNING', (
                        '{} warning field clear on {} consecutive scans; '
                        'SF-04 clear-hold of {:.1f} s started (seq={})'
                    ).format(self.name, self.warning_clear_run,
                             self.params['warning_clear_hold_s'], self.seq)))

        # ---- the OSSD-equivalent record, formed atomically ----
        a_clear = (intrusion_count == 0)
        b_intrusion = saw_intrusion
        record = (self.name, self.seq, stamp_s, a_clear, b_intrusion)
        self.last_record = record
        if a_clear == b_intrusion:
            self.discrepancy = True
            return lines + self._set_fault(
                '{} OSSD-equivalent DISCREPANCY: a_clear={} b_intrusion={} '
                'on one atomic record (seq={} stamp={:.6f}). The pair '
                'travels in one record, so no timing skew exists to '
                'tolerate: any disagreement is corruption.'.format(
                    self.name, a_clear, b_intrusion, self.seq, stamp_s))
        self.discrepancy = False

        # ---- rule 5: a sensor producing garbage at rate is not a sensor ----
        if invalid_fraction > self.params['invalid_fault_fraction']:
            self.below_threshold_run = 0
            return lines + self._set_fault(
                '{} invalid-sample rate {:.1%} over the {:.0%} threshold '
                '({} of {} samples, seq={})'.format(
                    self.name, invalid_fraction,
                    self.params['invalid_fault_fraction'],
                    invalid_count, total, self.seq))
        self.below_threshold_run += 1
        if self.faulted and self.below_threshold_run >= self.params['fault_clear_scans']:
            lines.append(('FAULT', (
                '{} device fault CLEARS after {} consecutive scans under '
                'the invalid threshold (was: {})').format(
                    self.name, self.below_threshold_run, self.fault_reason)))
            self.faulted = False
            self.fault_reason = ''
        if self.faulted:
            return lines

        # ---- the debounce: instant to demand, slow to release ----
        if not a_clear:
            if self.field_clear or self.clear_run:
                lines.append(('DEVICE', (
                    '{} INTRUSION on one scan: {} ray(s) inside the '
                    'contour, nearest {:.3f} m (seq={} stamp={:.6f})').format(
                        self.name, intrusion_count,
                        nearest if nearest is not None else float('nan'),
                        self.seq, stamp_s)))
            self.field_clear = False
            self.clear_run = 0
            return lines

        self.clear_run += 1
        if not self.field_clear and self.clear_run >= self.params['clear_debounce_scans']:
            self.field_clear = True
            lines.append(('DEVICE', (
                '{} CLEAR after {} consecutive fully-valid fully-clear '
                'scans (seq={} stamp={:.6f})').format(
                    self.name, self.clear_run, self.seq, stamp_s)))
        return lines

    def _set_fault(self, reason):
        """Raise or restate a device fault. A fault reads INTRUSION."""
        self.field_clear = False
        self.clear_run = 0
        if self.faulted and reason == self.fault_reason:
            return []
        self.faulted = True
        self.fault_reason = reason
        return [('FAULT', reason)]

    # -------------------------------------------------------------- #

    def freshness(self, now_ros_s, now_monotonic):
        """Affirmative freshness, per section 8 rule 1.

            fresh := (0 <= now - stamp) AND (now - stamp <= scan_fresh_max)

        Two clocks are tested, not one, and the node requires BOTH:

          * the ROS clock against the scan's own stamp - the design's
            rule, and the one that catches a publisher republishing an
            old scan;
          * this node's own monotonic clock against the moment of
            RECEIPT - an addition in the demanding direction, because a
            simulation clock that stops freezes `now` and `stamp`
            together and rule 1 alone would then read fresh for ever.

        Returns (fresh, reason).
        """
        limit = self.params['scan_fresh_max_s']
        if self.last_stamp_s is None or self.last_rx_monotonic is None:
            return False, '{}: no scan yet received'.format(self.name)
        stamp_age = now_ros_s - self.last_stamp_s
        if not (0.0 <= stamp_age and stamp_age <= limit):
            return False, ('{}: scan stamp age {:.3f} s outside '
                           '[0, {:.2f}] s').format(self.name, stamp_age, limit)
        rx_age = now_monotonic - self.last_rx_monotonic
        if not (0.0 <= rx_age and rx_age <= limit):
            return False, ('{}: nothing received for {:.3f} s (limit '
                           '{:.2f} s, this node\'s own monotonic '
                           'clock)').format(self.name, rx_age, limit)
        return True, ''

    def verdict(self, now_ros_s, now_monotonic):
        """(clear, key, reason) for this device. Unknown is intrusion.

        THE KEY IS WHY THIS RETURNS THREE THINGS AND NOT TWO. The reason
        is prose and carries live numbers - a scan age in seconds, a
        sample count - so it differs at every tick and cannot be used to
        decide whether anything has actually CHANGED. The first build
        compared reasons, and one killed device produced 213 near-
        identical "unchanged (INTRUSION), reason now: ... age 0.300 s /
        0.350 s / 0.400 s ..." lines in eleven seconds, burying the four
        line classes that ARE criterion-(a) evidence. The key is the
        stable CLASS of the verdict; the reason travels with it, once,
        when the class changes.
        """
        fresh, why = self.freshness(now_ros_s, now_monotonic)
        if not fresh:
            return False, (self.name, 'stale'), why
        if not self.advancing:
            return (False, (self.name, 'frozen-stamps'),
                    '{}: scan stamps not advancing'.format(self.name))
        if self.discrepancy:
            return (False, (self.name, 'discrepancy'),
                    '{}: OSSD-equivalent discrepancy'.format(self.name))
        if self.faulted:
            return (False, (self.name, 'fault'),
                    '{}: {}'.format(self.name, self.fault_reason))
        if not self.field_clear:
            return (False, (self.name, 'not-clear'),
                    '{}: field not clear'.format(self.name))
        return True, (self.name, 'clear'), '{}: clear'.format(self.name)

    def warning_verdict(self, now_ros_s, now_monotonic):
        """(occupied, key, reason, lines) for this device's WARNING field.

        THE SAME RULE 0, IN THE SAME DIRECTION: unknown means occupied.
        Every failure that makes the protective verdict read INTRUSION
        makes this read OCCUPIED - a dead, stale, frozen, discrepant or
        faulted device cannot prove a warning field clear any more than
        it can prove a protective one clear. The difference between the
        two verdicts is what they COST when they are wrong, and that is
        the consumer's business, not this rule's.

        The release side is where they differ: SF-04's 2 s clear-hold
        expires HERE, on the caller's steady clock, so that it goes on
        expiring while scans arrive and cannot be held open by a device
        that has merely stopped talking.
        """
        lines = []
        fresh, why = self.freshness(now_ros_s, now_monotonic)
        blocked = None
        if not fresh:
            blocked = ((self.name, 'warn-stale'), why)
        elif not self.advancing:
            blocked = ((self.name, 'warn-frozen-stamps'),
                       '{}: scan stamps not advancing'.format(self.name))
        elif self.discrepancy:
            blocked = ((self.name, 'warn-discrepancy'),
                       '{}: OSSD-equivalent discrepancy'.format(self.name))
        elif self.faulted:
            blocked = ((self.name, 'warn-fault'),
                       '{}: {}'.format(self.name, self.fault_reason))
        if blocked is not None:
            # A device that cannot be trusted also cannot be accumulating
            # clear time, so the hold is torn down rather than paused.
            self.warning_clear_since = None
            self.warning_clear_run = 0
            self.warning_occupied = True
            return True, blocked[0], blocked[1], lines

        if self.warning_occupied and self.warning_clear_since is not None:
            held = now_monotonic - self.warning_clear_since
            if held >= self.params['warning_clear_hold_s']:
                self.warning_occupied = False
                lines.append(('WARNING', (
                    '{} warning field RELEASED after the SF-04 clear-hold: '
                    '{:.3f} s of continuous non-occupation on this node\'s '
                    'own steady clock (limit {:.1f} s, seq={})').format(
                        self.name, held,
                        self.params['warning_clear_hold_s'], self.seq)))

        if self.warning_occupied:
            return (True, (self.name, 'warn-occupied'),
                    '{}: warning field occupied'.format(self.name), lines)
        return (False, (self.name, 'warn-clear'),
                '{}: warning field clear'.format(self.name), lines)


# ------------------------------------------------------------------------ #
# The link to the stand-in writer
# ------------------------------------------------------------------------ #

def derive_writer_host(configured):
    """Read the Windows-side address back from THIS HOST's configuration.

    SPEC section 7.2 and ADR 0006: the address WSL must dial is
    host-configuration-derived and is a READ-BACK value; the field
    evaluation takes it from its own configuration, NEVER from a
    document. `auto` therefore means: derive it here, and log which
    source produced it, so the value in force is visible in the evidence
    rather than assumed.

    Returns (address, how).
    """
    if configured and str(configured).strip().lower() != 'auto':
        return str(configured).strip(), 'config field.link.host'

    env = os.environ.get('AMR_FIELD_LINK_HOST', '').strip()
    if env:
        return env, 'environment AMR_FIELD_LINK_HOST'

    try:
        out = subprocess.run(['ip', 'route', 'show', 'default'],
                             capture_output=True, text=True, timeout=5.0)
        for token in out.stdout.split():
            if token.count('.') == 3 and token.replace('.', '').isdigit():
                return token, 'WSL default route (ip route show default)'
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        with open('/etc/resolv.conf', 'r', encoding='utf-8') as handle:
            for line in handle:
                if line.startswith('nameserver'):
                    parts = line.split()
                    if len(parts) > 1:
                        return parts[1], '/etc/resolv.conf nameserver'
    except OSError:
        pass

    raise RuntimeError(
        'field.link.host is "auto" and no address could be read back from '
        'this host: no AMR_FIELD_LINK_HOST, no default route, no resolv.conf '
        'nameserver. Set field.link.host explicitly rather than letting the '
        'node guess - the address is a read-back value (ADR 0006).')


class WriterLink(object):
    """One TCP connection to the stand-in writer's listener.

    THIS NODE ADDS NOTHING TO ITS OWN DEATH BEHAVIOUR, DELIBERATELY. The
    writer's contract already converts silence on this link into the
    demanding value: no well-formed line for FIELD_LINK_STALE_MAX = 1 s
    and it drives ZoneDeviceCircuitClosed FALSE and hands the channel
    back to its operator (SPEC section 7.3 row 2). So silence here is NOT
    a standing order - the consumer converts it - and no level-repair
    traffic is invented beyond the spec's vocabulary of ZONE and PING.

    THE SOCKET IS NON-BLOCKING THROUGHOUT, INCLUDING THE CONNECT, AND THAT
    IS LOAD-BEARING RATHER THAN TIDY. The first build of this class used
    socket.create_connection(timeout=2.0). With no writer listening, every
    attempt blocked this node's single-threaded executor for the whole
    timeout; the scan and /clock queues backed up behind it, and the node
    then read its OWN freshness rule as violated - measured at a stamp age
    of 0.838-0.996 s against a 0.30 s window, while an independent probe
    on the same two topics in the same run measured 0.016 s (front) and
    0.027 s (rear). The node was failing itself, in the demanding
    direction, for a defect that was entirely in its link code. LESSONS
    2026-07-29 states the rule for a harness - never block the event loop
    of the session you observe - and it applies with more force to a node
    whose other job is to notice that a scanner has stopped talking.

    So: connect_ex on a non-blocking socket, completion polled with
    select() at zero timeout on later ticks, and an attempt abandoned by
    DEADLINE rather than by waiting on one.
    """

    def __init__(self, host, port, ping_period_s, reconnect_period_s,
                 connect_timeout_s, clear_digit, intrusion_digit, emit):
        self.host = host
        self.port = int(port)
        self.ping_period_s = ping_period_s
        self.reconnect_period_s = reconnect_period_s
        self.connect_timeout_s = connect_timeout_s
        self.clear_digit = int(clear_digit)
        self.intrusion_digit = int(intrusion_digit)
        self.emit = emit

        self.sock = None
        self.up = False
        self.connecting = False
        self.connect_deadline = 0.0
        self.next_attempt = 0.0
        self.next_ping = 0.0
        self.sent_zone = None
        self.sends = 0
        self.pings = 0
        self.attempts = 0

    def zone_line(self, clear):
        digit = self.clear_digit if clear else self.intrusion_digit
        return 'ZONE {}\n'.format(digit)

    def service(self, now, clear):
        if self.connecting:
            self._poll_connect(now, clear)
            return
        if not self.up:
            if now >= self.next_attempt:
                self.next_attempt = now + self.reconnect_period_s
                self._begin_connect(now)
            return
        if now >= self.next_ping:
            self.next_ping = now + self.ping_period_s
            # NOT LOGGED, and that is the log's SPECIFICATION rather than
            # tidiness: section 7 makes this a TRANSITION log - per-device
            # verdict transitions, aggregate transitions, fault-class
            # changes, link state changes - and a keepalive is none of
            # those. Logging 2 Hz of PING buries the four line classes
            # that ARE criterion-(a) evidence under traffic carrying no
            # verdict; the first run of this node produced 88 PING lines
            # against 6 verdict lines. The count is reported at EXIT, so
            # the keepalive is accounted for rather than hidden.
            self.pings += 1
            self._send('PING\n', None)

    def _begin_connect(self, now):
        self.attempts += 1
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            err = sock.connect_ex((self.host, self.port))
        except OSError as exc:
            self._connect_failed(str(exc))
            return
        self.sock = sock
        if err == 0:
            self.connecting = False
            return
        if err in (errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY):
            self.connecting = True
            self.connect_deadline = now + self.connect_timeout_s
            return
        self._connect_failed(os.strerror(err))

    def _poll_connect(self, now, clear):
        try:
            _r, writable, _x = select.select([], [self.sock], [], 0)
        except (OSError, ValueError) as exc:
            self._connect_failed(str(exc))
            return
        if writable:
            err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            self.connecting = False
            if err != 0:
                self._connect_failed(os.strerror(err))
                return
            self._connected(now, clear)
            return
        if now >= self.connect_deadline:
            self.connecting = False
            self._connect_failed(
                'no completion within {:.1f} s'.format(self.connect_timeout_s))

    def _connect_failed(self, why):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        self.emit('LINK', (
            'connect attempt {} to {}:{} failed: {}. While the link is down '
            'this node sends nothing and the writer drives the zone channel '
            'OPEN after its own 1 s stale window - the demanding direction, '
            'and its contract, not ours to duplicate').format(
                self.attempts, self.host, self.port, why))

    def _connected(self, now, clear):
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self.up = True
        self.next_ping = now + self.ping_period_s
        self.sent_zone = None
        self.emit('LINK', 'up: connected to the stand-in writer at {}:{}'
                  .format(self.host, self.port))
        # ONE ZONE LINE IMMEDIATELY ON (RE)CONNECT. A fresh connection is a
        # transition from unknown, and the writer holds the channel FALSE
        # until its first ZONE line, so this is the line that either
        # confirms the open or closes it. SPEC 7.2 names transitions and
        # PING only; this is argued as a transition and is flagged in the
        # m5-12 report as a reading to confirm.
        self.publish(clear, 'first line on a new connection (a connection '
                            'is a transition from unknown)')

    def publish(self, clear, why):
        line = self.zone_line(clear)
        if self._send(line, '{} -> {}'.format(line.strip(), why)):
            self.sent_zone = clear

    def _send(self, text, detail):
        if not self.up or self.sock is None:
            return False
        try:
            self.sock.sendall(text.encode('ascii'))
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                self.emit('LINK', 'send buffer full, {} not sent'.format(
                    text.strip()))
                return False
            self.close('send failed: {}'.format(exc))
            return False
        self.sends += 1
        if detail is not None:
            self.emit('SEND', detail)
        return True

    def close(self, why):
        self.connecting = False
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        if self.up:
            self.emit('LINK', 'down ({}). The writer converts the silence '
                              'into an open zone channel within its own 1 s '
                              'stale window'.format(why))
        self.up = False
        self.sent_zone = None


# ------------------------------------------------------------------------ #
# The transition log
# ------------------------------------------------------------------------ #

class TransitionLog(object):
    """One file per session, unique name per start, refusing a collision.

    SPEC section 7.6: criterion (a) is decided OUTSIDE the F-program, in
    correlated records, because a WriteBool from this node and one from a
    test script are byte-identical at the CPU. A zone transition in the
    writer's session log with no matching line here is not criterion-(a)
    evidence, whatever the narration says. So this file is a deliverable,
    not a diagnostic.

    The line format is the writer's own - `stamp | CLASS | detail` - so
    the two logs interleave without a parser.
    """

    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True)
        name = 'field-evaluation-{}-pid{}.log'.format(
            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'), os.getpid())
        self.path = os.path.join(directory, name)
        # 'x': refuse a collision rather than overwrite. One evidence file
        # per session; never share a path across restarts (LESSONS
        # 2026-07-28, and the gzip-under-a-live-writer entry after it).
        self.handle = open(self.path, 'x', encoding='utf-8')

    def write(self, cls, detail):
        self.handle.write('{} | {} | {}\n'.format(utc_stamp(), cls, detail))
        self.handle.flush()

    def close(self):
        try:
            self.handle.close()
        except OSError:
            pass


# ------------------------------------------------------------------------ #

class FieldEvaluation(Node):
    """Phase 1 of FIELD-EVALUATION.md: the static contour and the link."""

    def __init__(self, cfg, model_path, config_path):
        super().__init__('field_evaluation')
        field = cfg['field']
        topics = cfg['topics']

        self.log = TransitionLog(
            os.path.join(_FORKLIFT_DIR, field['log_dir']))

        depth = field['protective_depth_m']
        warning_depth = field['warning_depth_m']
        half = field['corridor_half_width_m']
        rect = (field['outline_tine_tip_x_m'] - depth,
                field['outline_nose_x_m'] + depth,
                -half, half)
        # The warning rectangle is the SAME outline grown by the SAME
        # half width and a LARGER depth (FIELD-EVALUATION.md section 6.1).
        # It is derived here from the outline rather than from the
        # protective rectangle, so that the two depths stay independently
        # traceable to the two derivations that produced them.
        warning_rect = (field['outline_tine_tip_x_m'] - warning_depth,
                        field['outline_nose_x_m'] + warning_depth,
                        -half, half)
        if not warning_depth > depth:
            raise RuntimeError(
                'field.warning_depth_m ({}) must be GREATER than '
                'field.protective_depth_m ({}). A warning field that is not '
                'larger than the protective field cannot trip a speed '
                'reduction before the stop it is supposed to precede.'
                .format(warning_depth, depth))

        clips_by_device = {d: [] for d in DEVICES}
        for clip in field.get('self_return_clips') or []:
            clips_by_device[clip['device']].append(
                (clip['bearing_lo_deg'], clip['bearing_hi_deg'],
                 clip['boundary_m']))

        mounts = read_scanner_mounts(model_path)
        common = {
            'rect': rect,
            'warning_rect': warning_rect,
            'warning_clear_hold_s': field['warning_clear_hold_s'],
            'scan_fresh_max_s': field['scan_fresh_max_s'],
            'clear_debounce_scans': field['clear_debounce_scans'],
            'invalid_fault_fraction': field['invalid_fault_fraction'],
            'fault_clear_scans': field['fault_clear_scans'],
        }
        self.devices = {}
        for name in DEVICES:
            params = dict(common)
            params['clips'] = clips_by_device[name]
            self.devices[name] = DeviceEvaluation(name, mounts[name], params)

        self.source_topics = {
            'front': topics['safety_scanner_front_measurement'],
            'rear': topics['safety_scanner_rear_measurement'],
        }

        link_cfg = field['link']
        host, how = derive_writer_host(link_cfg.get('host'))
        self.link = WriterLink(
            host, link_cfg['port'], link_cfg['ping_period_s'],
            link_cfg['reconnect_period_s'], link_cfg['connect_timeout_s'],
            link_cfg['zone_clear_digit'], link_cfg['zone_intrusion_digit'],
            self.emit)

        # THE AGGREGATE BOOTS INTRUSION. Nothing has proved a field clear
        # yet, and "not yet proven stale" is not "alive".
        self.aggregate_clear = False
        self.aggregate_key = None
        self.scan_fresh_max_s = field['scan_fresh_max_s']
        self._last_ros_s = None
        self._last_ros_mono = time.monotonic()
        self.aggregate_reason = 'boot: no device has yet proved its field clear'

        # THE WARNING VERDICT BOOTS OCCUPIED, like everything else here.
        self.warning_occupied = True
        self.warning_key = None
        self.warning_reason = 'boot: no device has yet proved its warning '\
                              'field clear'

        qos = QoSProfile(depth=cfg['qos']['depth'])

        # THE WARNING VERDICT HAS A TOPIC AND THE PROTECTIVE ONE NEVER
        # WILL, and the asymmetry is the design rather than an oversight.
        # The m5-06 ruling bars the SAFE channel from every transport;
        # this is not it. SF-04 carries no PL claim, trips a SPEED
        # REDUCTION rather than a stop, and is backed unconditionally by
        # SF-03 - whose verdict still crosses only the dedicated link.
        #
        # PUBLISHED AT THE TICK, NOT ON TRANSITIONS. A consumer that
        # republishes the last value it saw would turn this node's death
        # into a standing order to keep driving fast (LESSONS 2026-08-04),
        # so the level is on the wire 20 times a second and its ABSENCE is
        # the signal. Any consumer owes a stale rule of its own: no
        # message inside its own window means OCCUPIED, never clear.
        self.pub_warning = self.create_publisher(
            Bool, topics['warning_field_occupied'], qos)

        self.sub_front = self.create_subscription(
            LaserScan, self.source_topics['front'],
            self.cb_scan_front, qos)
        self.sub_rear = self.create_subscription(
            LaserScan, self.source_topics['rear'],
            self.cb_scan_rear, qos)

        # THE EVALUATION TICK RUNS ON STEADY TIME, NOT ON THE SIMULATION
        # CLOCK, AND THIS IS THE MOST LOAD-BEARING LINE IN THE FILE.
        #
        # The first build used the node's default clock. With
        # use_sim_time:=true that is the SIMULATION clock, published on
        # /clock - by the same ros_gz_bridge process that carries both
        # scanner channels. So when the scan source died, /clock died with
        # it, the timer could never become ready again, and the node sat in
        # its wait set for ever: measured three times, at 10 s, 8 s and 8 s
        # after the bridge was stopped, with the process alive, all 34
        # threads sleeping, the main thread in futex_wait_queue_me and its
        # CPU time frozen to the jiffy. It sent no verdict and no keepalive.
        # obstacle_zone.py, an rclpy node subscribing to the SAME topic from
        # the SAME bridge, kept reporting "scan stale" every 5 s throughout -
        # because the launch does not give it use_sim_time.
        #
        # THE RULE, WHICH IS obstacle_zone.py's OWN RULE ONE LEVEL UP: that
        # node already says "a watchdog that trusts the timestamp of the
        # thing it is watching is not a watchdog". The same is true of the
        # CLOCK THE WATCHDOG'S TICK RUNS ON. A freshness test is only as
        # alive as the timer that evaluates it, so the timer runs on a clock
        # nothing in the observed system can stop.
        #
        # use_sim_time is still on, and still needed: the design's rule 1
        # compares the scan's own simulated stamp against the ROS clock, and
        # that comparison is only meaningful in the same time base.
        self._tick_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.timer_evaluate = self.create_timer(
            1.0 / field['evaluate_hz'], self.cb_evaluate,
            clock=self._tick_clock)

        banner = (
            'FIELD EVALUATION - a MODEL of what a safety-rated scanner does '
            'internally, feeding a STAND-IN FOR WIRING. Not a safety '
            'function; no Category, no Performance Level, no SIL, no PFH, no '
            'diagnostic coverage (ADR 0011 D5). It reports levels and '
            'latches nothing.')
        self.emit('START', banner)
        self.emit('START', 'phases 1 and 2 of agv/forklift/FIELD-EVALUATION.md '
                           'section 12: two STATIC all-direction contours - '
                           'protective and warning - with no case selection '
                           'and no speed enforcement anywhere in this node')
        self.emit('START', 'config = {}'.format(config_path))
        self.emit('START', 'model = {} (scanner mounts read from it, not '
                           'mirrored)'.format(model_path))
        for name in DEVICES:
            mount = mounts[name]
            self.emit('START', '{} device: topic {} (NON-SAFE measurement '
                               'channel), mount x={:.3f} y={:.3f} '
                               'yaw={:.7f} rad'.format(
                                   name, self.source_topics[name], *mount))
        self.emit('START', (
            'protective contour: corridors x {:.3f}..{:.3f} m, y '
            '{:+.3f}..{:+.3f} m in the vehicle frame - the plan outline '
            '({:.3f}..{:.3f} m) grown by the protective depth {:.2f} m fore '
            'and aft, half width {:.2f} m. Intrusion opens the zone channel '
            'and stops the vehicle'
        ).format(rect[0], rect[1], rect[2], rect[3],
                 field['outline_tine_tip_x_m'], field['outline_nose_x_m'],
                 depth, half))
        self.emit('START', (
            'warning contour: corridors x {:.3f}..{:.3f} m, y '
            '{:+.3f}..{:+.3f} m in the vehicle frame - the SAME outline and '
            'the SAME half width grown by the warning depth {:.2f} m, '
            'derived in section 6.1 as W = D + v*T_w + (v^2-v_c^2)/2a + '
            'Kp*[T_w+(v-v_c)/a] = 1.35 + 0.210 + 0.270 + 1.520 at v = 0.60 '
            'm/s. Occupation demands a SPEED REDUCTION to the creep ceiling '
            'and stops nothing'
        ).format(warning_rect[0], warning_rect[1], warning_rect[2],
                 warning_rect[3], warning_depth))
        for clip in field.get('self_return_clips') or []:
            self.emit('START', (
                'self-return clip: {} device, sensor frame {:+.1f}..{:+.1f} '
                'deg, boundary capped at {:.3f} m - FIELD GEOMETRY, not a '
                'filter applied to samples').format(
                    clip['device'], clip['bearing_lo_deg'],
                    clip['bearing_hi_deg'], clip['boundary_m']))
        self.emit('START', (
            'failure rules: freshness {:.2f} s, clear debounce {} scans, '
            'invalid-fault threshold {:.0%} clearing after {} scans, '
            'evaluation tick {:.1f} Hz. Unknown means INTRUSION in every '
            'one of them; an empty horizon means CLEAR, because a '
            'beyond-range return is a measurement').format(
                field['scan_fresh_max_s'], field['clear_debounce_scans'],
                field['invalid_fault_fraction'], field['fault_clear_scans'],
                field['evaluate_hz']))
        self.emit('START', (
            'link: {}:{} - the address was read back from this host ({}), '
            'never taken from a document (ADR 0006). ZONE {} = field clear, '
            'ZONE {} = intrusion or this evaluation\'s own fault: the digit '
            'is the CIRCUIT LEVEL').format(
                host, link_cfg['port'], how, link_cfg['zone_clear_digit'],
                link_cfg['zone_intrusion_digit']))
        self.emit('START', (
            'warning verdict: {} [std_msgs/Bool], published at the {:.1f} Hz '
            'evaluation tick and NOT on transitions, so that its ABSENCE is '
            'visible. Occupation asserts on one scan; release needs {} clear '
            'scans AND THEN the SF-04 clear-hold of {:.1f} s on this node\'s '
            'own steady clock. Every failure rule reads OCCUPIED. NO CONSUMER '
            'EXISTS YET, and any consumer owes a stale rule of its own: no '
            'message inside its window means OCCUPIED, never clear').format(
                topics['warning_field_occupied'], field['evaluate_hz'],
                field['clear_debounce_scans'], field['warning_clear_hold_s']))
        self.emit('START', (
            'THE PROTECTIVE VERDICT HAS NO ROS TOPIC and never will: the safe '
            'channel '
            'has no topic on either transport (owner ruling m5-06). This log '
            'and the writer\'s session log are the correlated record SPEC '
            '7.6 requires'))
        self.emit('START', 'log = {}'.format(self.log.path))
        self.emit('AGGREGATE', 'boot verdict INTRUSION: {}'.format(
            self.aggregate_reason))

    # ---------------------------------------------------------------- #
    # Callbacks are named cb_* so that none of them can shadow an rclpy
    # Node attribute (LESSONS 2026-07-27).
    # ---------------------------------------------------------------- #

    def emit(self, cls, detail):
        self.log.write(cls, detail)
        if cls in ('START', 'AGGREGATE', 'WARNING', 'FAULT', 'LINK'):
            self.get_logger().info('{} | {}'.format(cls, detail))

    def cb_scan_front(self, msg):
        self._ingest('front', msg)

    def cb_scan_rear(self, msg):
        self._ingest('rear', msg)

    def _ingest(self, name, msg):
        for cls, detail in self.devices[name].ingest(
                msg, time.monotonic(), self.log):
            self.emit(cls, detail)

    def cb_evaluate(self):
        """Re-form the aggregate every tick, whether or not a scan arrived.

        A device that goes silent has to become an intrusion on the
        freshness rule, and a rule that only runs when a message arrives
        never runs for the message that never comes.
        """
        now_ros_s = self.get_clock().now().nanoseconds * 1e-9
        now_mono = time.monotonic()

        # THE UNION IS THE AGGREGATION: intrusion iff ANY device reports
        # intrusion, or is faulted, or is stale. Coverage is a property of
        # the pair, so one scanner is never "enough to keep driving".
        # THE SIMULATION CLOCK IS ITSELF WATCHED, on steady time. This rule
        # is an ADDITION to FIELD-EVALUATION.md section 8's five, in the
        # demanding direction, and it exists because of what the section-8
        # rules cannot see: when /clock stops, `now_ros_s - stamp` freezes
        # at whatever it was, so rule 1 reads FRESH for ever on a scan that
        # is arbitrarily old. In this twin /clock and both scanner channels
        # come from ONE bridge process, so the failure that stops the scans
        # is exactly the failure that blinds rule 1. Named, not assumed:
        # the node's own monotonic clock is the only one in this test.
        if self._last_ros_s is None or now_ros_s > self._last_ros_s:
            self._last_ros_s = now_ros_s
            self._last_ros_mono = now_mono
        clock_frozen = (
            (now_mono - self._last_ros_mono) > self.scan_fresh_max_s)

        reasons = []
        keys = []
        clear = True
        if clock_frozen:
            clear = False
            keys.append(('clock', 'frozen'))
            reasons.append(
                'the simulation clock has not advanced for {:.3f} s of this '
                'node\'s own steady time (limit {:.2f} s), so no scan can be '
                'proved fresh'.format(now_mono - self._last_ros_mono,
                                      self.scan_fresh_max_s))
        for name in DEVICES:
            device_clear, key, why = self.devices[name].verdict(
                now_ros_s, now_mono)
            keys.append(key)
            if not device_clear:
                clear = False
                reasons.append(why)
        reason = '; '.join(reasons) if reasons else 'both devices clear'
        key = tuple(keys)

        # ---- the WARNING aggregate, by the same union ----
        w_reasons = []
        w_keys = []
        warning = False
        if clock_frozen:
            warning = True
            w_keys.append(('clock', 'frozen'))
            w_reasons.append('the simulation clock has not advanced')
        for name in DEVICES:
            occupied, w_key, w_why, w_lines = \
                self.devices[name].warning_verdict(now_ros_s, now_mono)
            for cls, detail in w_lines:
                self.emit(cls, detail)
            w_keys.append(w_key)
            if occupied:
                warning = True
                w_reasons.append(w_why)
        w_reason = ('; '.join(w_reasons) if w_reasons
                    else 'both devices report the warning field clear')
        w_key = tuple(w_keys)

        if warning != self.warning_occupied:
            self.warning_occupied = warning
            self.warning_key = w_key
            self.emit('WARNING', (
                'warning field {} - {} (front {} ray(s) inside, rear {}). '
                'This demands a SPEED REDUCTION to the creep ceiling and '
                'stops nothing; the protective verdict is separate and is '
                'unaffected by this line').format(
                    'OCCUPIED' if warning else 'CLEAR', w_reason,
                    self.devices['front'].last_warning_count,
                    self.devices['rear'].last_warning_count))
        elif w_key != self.warning_key:
            self.warning_key = w_key
            self.emit('WARNING', 'unchanged ({}), reason now: {}'.format(
                'OCCUPIED' if warning else 'CLEAR', w_reason))

        # EVERY TICK, not on transitions. See the publisher's comment.
        msg = Bool()
        msg.data = warning
        self.pub_warning.publish(msg)

        if clear != self.aggregate_clear:
            self.aggregate_clear = clear
            self.aggregate_key = key
            self.emit('AGGREGATE', '{} - {} (front seq={} rear seq={})'.format(
                'CLEAR' if clear else 'INTRUSION', reason,
                self.devices['front'].seq, self.devices['rear'].seq))
        elif key != self.aggregate_key:
            # The verdict did not change but WHY it holds did - one device
            # recovered while another failed, a fault became a staleness.
            # Logged once per change of class, never once per tick.
            self.aggregate_key = key
            self.emit('AGGREGATE', 'unchanged ({}), reason now: {}'.format(
                'CLEAR' if clear else 'INTRUSION', reason))

        self.link.service(now_mono, clear)
        if self.link.up and self.link.sent_zone != clear:
            self.link.publish(clear, 'aggregate transition')

    def shutdown(self):
        # The link carries LEVELS to a consumer that republishes them, so
        # this node does not "go silent to hand back control": the writer's
        # own stale rule is what converts our death into an open channel,
        # and it is more trustworthy than a dying process's last message
        # (LESSONS 2026-08-04, twice). We therefore close the socket
        # deliberately and say so, rather than inventing a terminal value
        # the spec's vocabulary does not have.
        self.link.close('this node is shutting down')
        for name in DEVICES:
            device = self.devices[name]
            self.emit('EXIT', (
                '{} device: {} scan(s) ingested, last invalid fraction '
                '{:.2%}, last protective intrusion-ray count {}, last '
                'warning-ray count {}, faulted={}').format(
                    name, device.seq, device.last_invalid_fraction,
                    device.last_intrusion_count, device.last_warning_count,
                    device.faulted))
        self.emit('EXIT', (
            'link: {} connect attempt(s), {} line(s) sent, of which {} were '
            'PING keepalives (not logged individually - this is a transition '
            'log)').format(
                self.link.attempts, self.link.sends, self.link.pings))
        self.emit('EXIT', (
            'field evaluation stopped. The writer sees the link die and '
            'drives ZoneDeviceCircuitClosed FALSE within FIELD_LINK_STALE_MAX '
            '= 1 s: loss of the intrusion source reads as an intrusion, never '
            'as a clear field'))
        self.log.close()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Protective-field evaluation for the forklift twin '
                    '(phase 1). A model of a device function feeding a '
                    'stand-in for wiring; not a safety function.')
    parser.add_argument('--config', default=_DEFAULT_CONFIG,
                        help='named-constant file (default: %(default)s)')
    parser.add_argument('--model', default=_DEFAULT_MODEL,
                        help='model file the scanner mounts are read from '
                             '(default: %(default)s)')
    args, ros_argv = parser.parse_known_args(argv)

    cfg = load_config(args.config)

    rclpy.init(args=[sys.argv[0]] + ros_argv)
    node = FieldEvaluation(cfg, args.model, args.config)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
