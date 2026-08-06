#!/usr/bin/env python3
"""speed_link_rig.py - the local proving rig for the speed-source link.

WHAT THIS IS, AND WHAT IT IS EMPHATICALLY NOT

  It is the instrument that lets agv/ prove ITS HALF of the SPEC
  section 11.2 link before the other half exists. It has three modes:

    plant   publishes the two raw gz drive-shaft reads and a navigation
            scan, so scripts/safe_speed_channels.py can run with no
            Gazebo and no PLC. It STIMULATES the producer; it does not
            simulate the vehicle.

    inject  publishes directly onto the two channel topics, including
            values the producer can never emit (NaN, out-of-range), so
            the carrier's refusals can be exercised at the ROS seam
            rather than only in a unit check.

    sink    a local listener that speaks the writer's half of the
            section 11.2 vocabulary: port 45016, one client at a time,
            a 50 ms cycle, per-channel freshness sequences that advance
            ONLY in a cycle that received a fresh line, and the
            MOTION_SILENCE_MAX = 250 ms rule that drives MotionPresent
            TRUE when MOT stops arriving.

  IT IS NOT THE STAND-IN WRITER. It writes to no PLC, holds no PLCSIM
  API session, touches no DB, carries none of the writer's mutex, log or
  allowlist obligations, and is not a substitute for bridge/. It exists
  so that the sentence "the readings reach the link at the spec's rate,
  and a stopped producer produces silence rather than repetition" can be
  DEMONSTRATED on this side of the seam. The far end - the writer's
  45016 extension and the F-program's speed networks - is owed a joint
  run and this rig does not stand in for it.

  IT IS NOT A SAFETY FUNCTION, carries no Category, Performance Level,
  SIL or PFH, and neither does anything it observes.

  IT MODELS THE CONSUMER, WHICH MEANS ITS AGREEMENT PROVES LESS THAN IT
  LOOKS. A rig written from the same paragraph as the client can agree
  with the client and both be wrong about the writer. What it does prove
  is what the CLIENT emits, cycle by cycle, against the rule the spec
  states - which is the half agv/ owns.

Usage (after sourcing /opt/ros/jazzy/setup.bash):

    python3 agv/forklift/scripts/speed_link_rig.py sink \\
        [--port 45016] [--csv PATH] [--seconds N]
    python3 agv/forklift/scripts/speed_link_rig.py plant \\
        [--speed 0.30] [--stop-after 6.0] [--seconds N]
    python3 agv/forklift/scripts/speed_link_rig.py inject \\
        --channel a --value nan [--seconds N]
"""

import argparse
import csv
import math
import os
import socket
import sys
import time
from datetime import datetime, timezone

import yaml

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_DEFAULT_CONFIG = os.path.join(_FORKLIFT_DIR, 'config.yaml')

#: The writer's own cycle, SPEC section 7.1. Not a knob here either.
SINK_CYCLE_S = 0.050

#: SPEC section 11.2: no MOT line for this long, or the link down, and
#: MotionPresent is driven TRUE. An unobservable vehicle is MOVING.
MOTION_SILENCE_MAX_S = 0.250


def load_config(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def utc_stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


# ------------------------------------------------------------------------ #
# sink
# ------------------------------------------------------------------------ #

class Sink(object):
    """The writer's half of section 11.2, as an observable local model.

    THE MEMBER SET IT HOLDS is SPEC section 11.3's seven, minus the
    warning selector, which rides the other link and is not this rig's
    business:

        SpeedReadingA/B   Int mm/s, start 0
        SpeedSeqA/B       Int, start 0, ADVANCED ONLY BY A FRESH LINE
        MotionPresent     Bool, start TRUE
        MotionObservationValid  Bool, start FALSE

    THE SEQUENCE RULE IS THE WHOLE POINT. Per 50 ms cycle, per channel:
    if at least one SPD line arrived since the previous cycle, write the
    latest value and increment the sequence; else write NEITHER. A frozen
    sequence is what the F-program reads as a missing channel, and a
    missing channel is a demand.
    """

    def __init__(self, port, csv_path, log):
        self.port = int(port)
        self.log = log
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(('0.0.0.0', self.port))
        self.listener.listen(4)
        self.listener.setblocking(False)
        self.client = None
        self.peer = None
        self.buf = b''

        # The members.
        self.reading = {'a': 0, 'b': 0}
        self.seq = {'a': 0, 'b': 0}
        self.motion_present = True
        self.motion_valid = False

        # Per-cycle arrival state.
        self.pending = {'a': None, 'b': None}
        self.pending_mot = None
        self.last_mot_rx = None
        self.last_seq_change = {'a': None, 'b': None}

        self.counts = {'SPD': 0, 'MOT': 0, 'PING': 0, 'BAD': 0}
        self.refused_connections = 0

        self.csv_handle = None
        self.csv = None
        if csv_path:
            os.makedirs(os.path.dirname(os.path.abspath(csv_path)),
                        exist_ok=True)
            self.csv_handle = open(csv_path, 'x', newline='',
                                   encoding='utf-8')
            self.csv = csv.writer(self.csv_handle)
            self.csv.writerow([
                't_s', 'link_up', 'reading_a_mmps', 'seq_a', 'a_advanced',
                'seq_a_frozen_s', 'reading_b_mmps', 'seq_b', 'b_advanced',
                'seq_b_frozen_s', 'motion_present', 'motion_valid',
                'mot_silence_s'])

    def say(self, cls, detail):
        self.log.write(cls, detail)
        print('{} | {} | {}'.format(utc_stamp(), cls, detail), flush=True)

    # ---- the socket --------------------------------------------------

    def accept(self, now):
        while True:
            try:
                sock, peer = self.listener.accept()
            except BlockingIOError:
                return
            except OSError:
                return
            if self.client is not None:
                # The writer's contract: accept, close, log as refused.
                self.refused_connections += 1
                try:
                    sock.close()
                except OSError:
                    pass
                self.say('LINK', 'refused a second connection from {}: one '
                                 'speed-source client at a time'.format(peer))
                continue
            sock.setblocking(False)
            self.client = sock
            self.peer = peer
            self.buf = b''
            self.say('LINK', 'up: speed-source client connected from {}'
                     .format(peer))

    def read(self, now):
        if self.client is None:
            return
        try:
            data = self.client.recv(65536)
        except BlockingIOError:
            return
        except OSError as exc:
            self.drop('recv failed: {}'.format(exc))
            return
        if not data:
            self.drop('client closed the connection (EOF)')
            return
        self.buf += data
        while b'\n' in self.buf:
            line, self.buf = self.buf.split(b'\n', 1)
            self.ingest(line.decode('ascii', 'replace').strip(), now)

    def drop(self, why):
        try:
            self.client.close()
        except OSError:
            pass
        self.client = None
        self.say('LINK', 'down ({}). From here the sequences freeze and '
                         'MotionPresent is driven TRUE'.format(why))

    # ---- the vocabulary ----------------------------------------------

    def ingest(self, line, now):
        parts = line.split()
        if not parts:
            return
        if parts[0] == 'PING' and len(parts) == 1:
            self.counts['PING'] += 1
            return
        if parts[0] == 'SPD' and len(parts) == 3 and parts[1] in ('A', 'B'):
            try:
                value = int(parts[2])
            except ValueError:
                self.counts['BAD'] += 1
                self.say('REFUSED', 'malformed SPD value: {!r}'.format(line))
                return
            self.counts['SPD'] += 1
            self.pending[parts[1].lower()] = value
            return
        if parts[0] == 'MOT' and len(parts) == 3:
            try:
                present = int(parts[1])
                valid = int(parts[2])
            except ValueError:
                self.counts['BAD'] += 1
                self.say('REFUSED', 'malformed MOT line: {!r}'.format(line))
                return
            self.counts['MOT'] += 1
            self.pending_mot = (bool(present), bool(valid))
            self.last_mot_rx = now
            return
        self.counts['BAD'] += 1
        self.say('REFUSED', 'not in the section 11.2 vocabulary: {!r}'
                 .format(line))

    # ---- the 50 ms cycle ---------------------------------------------

    def cycle(self, now, t0):
        advanced = {'a': 0, 'b': 0}
        for key in ('a', 'b'):
            value = self.pending[key]
            self.pending[key] = None
            if value is None:
                # WRITE NEITHER. This is the rule the whole design rests
                # on: no fresh line, no value, no sequence increment.
                continue
            self.reading[key] = value
            self.seq[key] = (self.seq[key] + 1) % 32768
            self.last_seq_change[key] = now
            advanced[key] = 1

        if self.pending_mot is not None:
            self.motion_present, self.motion_valid = self.pending_mot
            self.pending_mot = None

        silence = None
        if self.last_mot_rx is not None:
            silence = now - self.last_mot_rx
        if self.client is None or silence is None \
                or silence > MOTION_SILENCE_MAX_S:
            if not self.motion_present:
                self.say('MOTION', 'MotionPresent driven TRUE: no MOT line '
                                   'for {} - an unobservable vehicle is '
                                   'MOVING, never still'.format(
                                       'the whole session' if silence is None
                                       else '{:.3f} s'.format(silence)))
            self.motion_present = True

        if self.csv is not None:
            frozen = {}
            for key in ('a', 'b'):
                last = self.last_seq_change[key]
                frozen[key] = '' if last is None else '{:.3f}'.format(
                    now - last)
            self.csv.writerow([
                '{:.3f}'.format(now - t0),
                int(self.client is not None),
                self.reading['a'], self.seq['a'], advanced['a'], frozen['a'],
                self.reading['b'], self.seq['b'], advanced['b'], frozen['b'],
                int(self.motion_present), int(self.motion_valid),
                '' if silence is None else '{:.3f}'.format(silence)])
            self.csv_handle.flush()

    def close(self):
        if self.client is not None:
            try:
                self.client.close()
            except OSError:
                pass
        try:
            self.listener.close()
        except OSError:
            pass
        if self.csv_handle is not None:
            self.csv_handle.close()


def run_sink(args, log):
    sink = Sink(args.port, args.csv, log)
    sink.say('START', 'local sink listening on 0.0.0.0:{} - a MODEL of the '
                      'writer half of SPEC 11.2, not the stand-in writer. It '
                      'writes to no PLC.'.format(args.port))
    t0 = time.monotonic()
    deadline = None if args.seconds is None else t0 + args.seconds
    next_cycle = t0
    try:
        while deadline is None or time.monotonic() < deadline:
            now = time.monotonic()
            sink.accept(now)
            sink.read(now)
            if now >= next_cycle:
                next_cycle += SINK_CYCLE_S
                if next_cycle < now:
                    next_cycle = now + SINK_CYCLE_S
                sink.cycle(now, t0)
            time.sleep(0.002)
    except KeyboardInterrupt:
        pass
    finally:
        sink.say('EXIT', 'received SPD {}, MOT {}, PING {}, malformed {}; '
                         'refused {} extra connections; final SeqA {}, '
                         'SeqB {}, MotionPresent {}'.format(
                             sink.counts['SPD'], sink.counts['MOT'],
                             sink.counts['PING'], sink.counts['BAD'],
                             sink.refused_connections, sink.seq['a'],
                             sink.seq['b'], sink.motion_present))
        sink.close()
    return 0


# ------------------------------------------------------------------------ #
# plant and inject - the two ROS-side stimuli
# ------------------------------------------------------------------------ #

def run_plant(args, log, cfg):
    """Publish the two raw gz reads and a navigation scan.

    IT STIMULATES THE PRODUCER, IT DOES NOT SIMULATE THE VEHICLE. The
    shaft turns at a constant commanded speed and the horizon shifts
    with the distance travelled, which is enough for
    safe_speed_channels.py to difference two reading heads and to make
    a motion observation. No dynamics, no contact, no steering - and
    nothing measured here is a vehicle measurement.

    --stop-after stops PUBLISHING at the given time. It does not publish
    a zero, and that distinction is the point of the whole run: a
    stopped source must reach the F-program as a demand, so the stimulus
    has to be able to go silent the way a dead source does.
    """
    import rclpy
    from rclpy.clock import Clock, ClockType
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from sensor_msgs.msg import JointState, LaserScan

    topics = cfg['topics']
    joint = cfg['model']['drive_joint_name']
    radius = float(cfg['safe_speed']['rolling_radius_m'])
    rate = float(cfg['safe_speed']['publish_hz'])

    rclpy.init(args=[sys.argv[0]])
    node = Node('speed_link_rig_plant')
    qos = QoSProfile(depth=int(cfg['qos']['depth']))
    pub_a = node.create_publisher(JointState, topics['gz_drive_speed_read_a'],
                                  qos)
    pub_b = node.create_publisher(JointState, topics['gz_drive_speed_read_b'],
                                  qos)
    pub_scan = node.create_publisher(LaserScan, topics['scan'], qos)

    state = {'angle': 0.0, 'travel': 0.0, 'last': None, 'scans': 0,
             'reads': 0, 'silent': False}
    t0 = time.monotonic()

    def stamp_now(msg):
        now = node.get_clock().now().to_msg()
        msg.header.stamp = now
        return msg

    def cb_read():
        now = time.monotonic()
        elapsed = now - t0
        if args.stop_after is not None and elapsed >= args.stop_after:
            if not state['silent']:
                state['silent'] = True
                log.write('PLANT', 'stopping publication at {:.3f} s - the '
                                   'source goes SILENT. It does not publish '
                                   'a zero and it does not repeat its last '
                                   'value.'.format(elapsed))
                print('PLANT SILENT at {:.3f} s'.format(elapsed), flush=True)
            return
        last = state['last']
        state['last'] = now
        if last is not None:
            dt = now - last
            state['angle'] += args.speed / radius * dt
            state['travel'] += args.speed * dt
        msg = JointState()
        stamp_now(msg)
        msg.name = [joint]
        msg.position = [state['angle']]
        msg.velocity = [args.speed / radius]
        pub_a.publish(msg)
        pub_b.publish(msg)
        state['reads'] += 1

    def cb_scan():
        if state['silent']:
            return
        msg = LaserScan()
        stamp_now(msg)
        msg.header.frame_id = 'lidar_link'
        msg.angle_min = -math.pi
        msg.angle_max = math.pi
        msg.angle_increment = 2.0 * math.pi / 360.0
        msg.range_min = 0.10
        msg.range_max = 8.0
        # A horizon that shifts with distance travelled. Standing still
        # therefore produces an unchanged profile and no motion, which
        # is the regime that has to be distinguishable.
        msg.ranges = [
            3.0 + 0.8 * math.sin(0.10 * i + 3.0 * state['travel'])
            for i in range(360)]
        pub_scan.publish(msg)
        state['scans'] += 1

    steady = Clock(clock_type=ClockType.STEADY_TIME)
    node.create_timer(1.0 / rate, cb_read, clock=steady)
    node.create_timer(0.10, cb_scan, clock=steady)

    log.write('START', 'plant stimulus: {:.3f} m/s tread, {:.1f} Hz reads, '
                       '10 Hz scan, stop_after={}'.format(
                           args.speed, rate, args.stop_after))
    deadline = None if args.seconds is None else t0 + args.seconds
    try:
        while deadline is None or time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        log.write('EXIT', 'published {} reads and {} scans'.format(
            state['reads'], state['scans']))
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


def run_inject(args, log, cfg):
    """Publish straight onto a channel topic, including impossible values.

    The producer cannot emit a NaN - it declines to publish instead - so
    the carrier's non-finite refusal cannot be reached through it. This
    mode reaches it, at the ROS seam, with the carrier's own subscriber
    doing the receiving. Each run publishes the named value and then,
    after --control-after, a finite in-range POSITIVE CONTROL on the
    same topic: a refusal and a dead subscriber look identical without
    one (LESSONS 2026-08-06).
    """
    import rclpy
    from rclpy.clock import Clock, ClockType
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from std_msgs.msg import Float64

    topics = cfg['topics']
    key = 'drive_speed_channel_{}'.format(args.channel)
    value = float(args.value)

    rclpy.init(args=[sys.argv[0]])
    node = Node('speed_link_rig_inject')
    qos = QoSProfile(depth=int(cfg['qos']['depth']))
    pub = node.create_publisher(Float64, topics[key], qos)

    t0 = time.monotonic()
    state = {'sent': 0, 'control': 0, 'phase': 'value'}

    def cb_pub():
        elapsed = time.monotonic() - t0
        if args.control_after is not None and elapsed >= args.control_after:
            if state['phase'] != 'control':
                state['phase'] = 'control'
                log.write('INJECT', 'switching to the POSITIVE CONTROL: '
                                    '{} m/s, finite and in range, on the '
                                    'same topic'.format(args.control))
                print('INJECT CONTROL at {:.3f} s'.format(elapsed), flush=True)
            pub.publish(Float64(data=float(args.control)))
            state['control'] += 1
            return
        pub.publish(Float64(data=value))
        state['sent'] += 1

    steady = Clock(clock_type=ClockType.STEADY_TIME)
    node.create_timer(1.0 / float(cfg['safe_speed']['publish_hz']), cb_pub,
                      clock=steady)
    log.write('START', 'injecting {!r} on {} (channel {})'.format(
        value, topics[key], args.channel))
    deadline = None if args.seconds is None else t0 + args.seconds
    try:
        while deadline is None or time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        log.write('EXIT', 'published {} of the injected value and {} '
                          'positive-control values'.format(
                              state['sent'], state['control']))
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


# ------------------------------------------------------------------------ #

class RigLog(object):
    def __init__(self, directory, mode):
        os.makedirs(directory, exist_ok=True)
        name = 'rig-{}-{}-pid{}.log'.format(
            mode, datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
            os.getpid())
        self.path = os.path.join(directory, name)
        self.handle = open(self.path, 'x', encoding='utf-8')

    def write(self, cls, detail):
        self.handle.write('{} | {} | {}\n'.format(utc_stamp(), cls, detail))
        self.handle.flush()

    def close(self):
        try:
            self.handle.close()
        except OSError:
            pass


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Local proving rig for the SPEC 11.2 speed-source link. '
                    'Not the stand-in writer; writes to no PLC.')
    parser.add_argument('mode', choices=('sink', 'plant', 'inject'))
    parser.add_argument('--config', default=_DEFAULT_CONFIG)
    parser.add_argument('--log-dir', default=None)
    parser.add_argument('--seconds', type=float, default=None,
                        help='run for this long and exit (bounded runs only)')
    parser.add_argument('--port', type=int, default=45016)
    parser.add_argument('--csv', default=None,
                        help='sink: per-cycle member record')
    parser.add_argument('--speed', type=float, default=0.30,
                        help='plant: constant tread speed, m/s')
    parser.add_argument('--stop-after', type=float, default=None,
                        help='plant: go SILENT at this elapsed time')
    parser.add_argument('--channel', default='a', choices=('a', 'b'))
    parser.add_argument('--value', default='nan',
                        help='inject: the value to publish (nan, inf, 40.0)')
    parser.add_argument('--control', type=float, default=0.25,
                        help='inject: the positive-control value')
    parser.add_argument('--control-after', type=float, default=None,
                        help='inject: switch to the positive control here')
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    log_dir = args.log_dir or os.path.join(_FORKLIFT_DIR, 'evidence',
                                           'speed-link')
    log = RigLog(log_dir, args.mode)
    print('rig session log: {}'.format(log.path))
    try:
        if args.mode == 'sink':
            return run_sink(args, log)
        if args.mode == 'plant':
            return run_plant(args, log, cfg)
        return run_inject(args, log, cfg)
    finally:
        log.close()


if __name__ == '__main__':
    sys.exit(main())
