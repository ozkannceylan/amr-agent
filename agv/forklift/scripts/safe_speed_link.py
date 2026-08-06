#!/usr/bin/env python3
"""safe_speed_link.py - the carrier that puts the two speed readings and
the motion observation on the wire to the stand-in writer.

WHAT THIS NODE IS

    /forklift/drive_speed/channel_a            ->  SPD A <int mm/s>
    /forklift/drive_speed/channel_b            ->  SPD B <int mm/s>
    /forklift/drive_speed/motion_present       ->  MOT <p> <v>
    /forklift/drive_speed/motion_observation_valid

  One TCP connection, WSL client -> Windows listener on the stand-in
  writer, port 45016, newline-delimited ASCII. The grammar, the port,
  the scaling and the never-send-non-finite rule are
  plc/forklift-safety/SPEC.md section 11.2; nothing here invents a
  payload and nothing here extends the vocabulary beyond SPD, MOT and
  PING.

  It is a CARRIER. It forms no verdict, applies no threshold, holds no
  state that outlives a reading, and decides nothing about speed. The
  producer is scripts/safe_speed_channels.py; the monitor is the
  F-program. This is the wire between them.

THE ONE PROPERTY IT EXISTS TO PRESERVE

  A CHANNEL GOES SILENT RATHER THAN REPEAT.

  A reading that stops arriving stops being sent. It is never sent as
  zero, never sent as the value it last had, and never sent twice. The
  writer increments a channel's freshness sequence only in a cycle that
  received a fresh line for it, so silence here freezes that sequence;
  the F-program converts a frozen sequence into an INVALID CHANNEL
  within SPEED_STALE_MAX and an invalid channel into a LATCHED DEMAND in
  the same F-cycle (SPEC section 11.5 SL1-SL8, section 11.6). A missing
  reading is a demand - never a zero and never the last value.

  Every send in this file is therefore consume-once: a value is sent in
  the tick that received it and the slot is emptied by the sending. There
  is no path in this file that can emit a reading twice, and the selftest
  asserts it directly rather than by reading the code.

  THE SAME RULE APPLIES TO THIS NODE'S OWN GAPS. If the link is down, or
  the producer stalls, or a value is not sendable, this node sends
  NOTHING for that channel. It does not repair, resend, interpolate or
  hold. The demanding direction is the consumer's contract and duplicating
  it here would only hide which layer noticed.

WHAT IT IS NOT

  Not a safety function, not a safe transport, and not a measurement.
  No Category, Performance Level, SIL, PFH or diagnostic-coverage figure
  is claimed for it or for anything downstream of it (ADR 0011 D5). The
  readings arrive at the safety program as STANDARD DATA over a stand-in
  path. The protective stop, the e-stop chain and safe torque off are
  onboard and hardwired and appear nowhere in this file (invariant 1).

  It is not an OPC UA client and it never becomes one. Routing a speed
  over the OPC UA session would put the demand's formation on the client
  seam and put a motion value on the seam ADR 0014 closed; SPEC section
  11.2 rules that the stand-in writer carries these readings and that
  nothing else may.

TIMING RUNS ON A STEADY CLOCK, NEVER ON THE SIMULATION'S

  Every window in this node - the tick, the two freshness windows, the
  keepalive, the reconnect - is measured on time.monotonic(). The data
  whose failure these windows exist to notice arrives over the same
  graph that carries /clock, so a node that timed its own watchdog on
  simulation time would stop watching at the exact moment its subject
  stopped talking (LESSONS 2026-08-06). Message age is measured at
  ARRIVAL, not from a header stamp, for the same reason.

Usage (after sourcing /opt/ros/jazzy/setup.bash):

    python3 agv/forklift/scripts/safe_speed_link.py
    python3 agv/forklift/scripts/safe_speed_link.py --host 127.0.0.1
    python3 agv/forklift/scripts/safe_speed_link.py --selftest
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
from datetime import datetime, timezone

import yaml

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_DEFAULT_CONFIG = os.path.join(_FORKLIFT_DIR, 'config.yaml')

#: The two reading channels, in the order SPEC section 11.2 names them.
#: The wire letter is upper case; the config and topic keys are lower.
CHANNELS = ('a', 'b')


def load_config(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def utc_stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def derive_writer_host(configured, env_names):
    """Read the Windows-side address back from THIS HOST's configuration.

    ADR 0006 and SPEC section 7.2: the address WSL must dial is
    host-configuration-derived and is a READ-BACK value, never taken
    from a document. `auto` means derive it here and LOG which source
    produced it, so the value in force is visible in the evidence rather
    than assumed.

    scripts/field_evaluation.py holds the sibling copy of this
    derivation for port 45015. The two are deliberately separate
    functions rather than one import: field_evaluation.py imports rclpy
    at module scope, and this node's selftest must run with no ROS and
    no network. The duplication is flagged in this brief's report as a
    request to factor once agv/ has a shared module for it.

    Returns (address, how).
    """
    if configured and str(configured).strip().lower() != 'auto':
        return str(configured).strip(), 'config safe_speed.link.host'

    for name in env_names:
        env = os.environ.get(name, '').strip()
        if env:
            return env, 'environment {}'.format(name)

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
        'safe_speed.link.host is "auto" and no address could be read back '
        'from this host: no AMR_SPEED_LINK_HOST, no AMR_FIELD_LINK_HOST, no '
        'default route, no resolv.conf nameserver. Set the address '
        'explicitly rather than letting the node guess - it is a read-back '
        'value (ADR 0006).')


# ------------------------------------------------------------------------ #
# The scaling, and the two refusals
# ------------------------------------------------------------------------ #

#: Why a reading was not put on the wire. None means it was.
REFUSE_NONFINITE = 'non-finite'
REFUSE_RANGE = 'outside the Int wire range'


def scale_reading(value_mps, int_min, int_max):
    """m/s -> signed Int mm/s, or (None, why) if it may not be sent.

    SPEC section 11.2: the scaling is round(v * 1000), signed, applied
    on this side so that the wire, the writer log and the DB member all
    carry the same integer and can be diffed.

    TWO REFUSALS, BOTH SILENT ON THE WIRE.

      * A NON-FINITE value is never scaled and never sent. This is the
        analogue-plausibility lesson (LESSONS 2026-07-27) applied at the
        source: a NaN makes every comparison false, so a NaN that
        reached the F-program's window as a value would fall to the
        permissive side of a negated test. The F-side window is the
        independent second application and this one does not replace it.

      * A value that will not fit an S7 Int is not sent either. A
        wrapped Int is a value, and a wrong one, in a place where the
        only alternative reading is "missing" - and missing is a demand.
        The F-side plausibility window is +/-4000 mm/s (SPEC 11.3), so
        anything refused here would have been refused there too; what
        this refusal buys is that no wrapped number ever reaches the
        comparison at all.

    Returns (int_value, None) or (None, reason).
    """
    if value_mps is None or not math.isfinite(value_mps):
        return None, REFUSE_NONFINITE
    scaled = int(round(value_mps * 1000.0))
    if scaled < int_min or scaled > int_max:
        return None, REFUSE_RANGE
    return scaled, None


class Slot(object):
    """One channel's pending reading. Consume-once, by construction.

    `take()` is the ONLY way a value leaves this object and it empties
    the slot in the same call. There is no accessor that returns the
    value without clearing it, so no caller can send one twice - the
    never-repeat property is a property of this class rather than of the
    discipline of its callers.
    """

    __slots__ = ('value', 'arrived')

    def __init__(self):
        self.value = None
        self.arrived = None

    def put(self, value, now):
        # A later arrival in the same tick replaces an unsent earlier
        # one. The writer takes the latest value in its own 50 ms cycle
        # (SPEC 11.2), so coalescing here matches the consumer exactly
        # and the freshness sequence still advances once per cycle.
        self.value = value
        self.arrived = now

    def take(self, now, fresh_max_s):
        """(value, age) if there is a fresh unsent reading, else (None, age).

        Emptied either way: a reading too old to send is DISCARDED, not
        held for a later tick. Holding it would be the beginning of
        repeating it.
        """
        if self.arrived is None:
            return None, None
        age = now - self.arrived
        value = self.value
        self.value = None
        self.arrived = None
        if age > fresh_max_s:
            return None, age
        return value, age


# ------------------------------------------------------------------------ #
# The link
# ------------------------------------------------------------------------ #

class SpeedLink(object):
    """One TCP connection to the stand-in writer's 45016 listener.

    THE SOCKET IS NON-BLOCKING THROUGHOUT, INCLUDING THE CONNECT, and
    that is load-bearing rather than tidy. A blocking connect against a
    listener that is not there stalls the executor for the whole
    timeout, the subscriptions queue behind it, and the node then reads
    its own freshness windows as violated - a node failing itself in the
    demanding direction for a defect entirely in its link code. That is
    the measured m5-12 failure, and the same shape as LESSONS 2026-07-29.

    THE LISTENER REFUSES A SECOND CONNECTION - it accepts, closes and
    logs (bridge/STANDIN-WRITER-DESIGN.md). A refused connection
    therefore looks like a successful connect followed immediately by
    EOF, so this class must notice the close rather than assume the link
    it just formed is usable. It notices it the only way a sender can:
    the next send fails, the link goes down, and the reconnect timer
    runs. Reconnect is attempted forever, at reconnect_period_s, and
    every attempt is logged with its outcome.

    THIS CLASS ADDS NOTHING TO ITS OWN DEATH BEHAVIOUR. While the link
    is down it sends nothing and invents no level-repair traffic. The
    writer's contract converts silence into frozen sequences and
    MotionPresent TRUE; duplicating that here would only obscure which
    layer noticed.
    """

    def __init__(self, host, port, ping_period_s, reconnect_period_s,
                 connect_timeout_s, emit):
        self.host = host
        self.port = int(port)
        self.ping_period_s = float(ping_period_s)
        self.reconnect_period_s = float(reconnect_period_s)
        self.connect_timeout_s = float(connect_timeout_s)
        self.emit = emit

        self.sock = None
        self.up = False
        self.connecting = False
        self.connect_deadline = 0.0
        self.next_attempt = 0.0
        self.next_ping = 0.0

        self.attempts = 0
        self.connects = 0
        self.drops = 0
        self.pings = 0
        self.sent = {'a': 0, 'b': 0, 'mot': 0}

    # ---- connection management ---------------------------------------

    def service(self, now):
        """Advance the connection state machine. Never blocks."""
        if self.connecting:
            self._poll_connect(now)
            return
        if not self.up:
            if now >= self.next_attempt:
                self.next_attempt = now + self.reconnect_period_s
                self._begin_connect(now)
            return
        self._drain_peer()
        if self.up and now >= self.next_ping:
            self.next_ping = now + self.ping_period_s
            self.pings += 1
            # Not logged per ping, deliberately: this is a TRANSITION
            # log, and a keepalive is not a transition. 1 Hz of PING in
            # the file would bury the lines that carry a reading's fate.
            # The count is reported at exit so the traffic is accounted
            # for rather than hidden.
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
            self._connected(now)
            return
        if err in (errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY):
            self.connecting = True
            self.connect_deadline = now + self.connect_timeout_s
            return
        self._connect_failed(os.strerror(err))

    def _poll_connect(self, now):
        try:
            _r, writable, _x = select.select([], [self.sock], [], 0)
        except (OSError, ValueError) as exc:
            self.connecting = False
            self._connect_failed(str(exc))
            return
        if writable:
            err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            self.connecting = False
            if err != 0:
                self._connect_failed(os.strerror(err))
                return
            self._connected(now)
            return
        if now >= self.connect_deadline:
            self.connecting = False
            self._connect_failed(
                'no completion within {:.1f} s'.format(self.connect_timeout_s))

    def _connect_failed(self, why):
        self._close_socket()
        self.emit('LINK', (
            'connect attempt {} to {}:{} failed: {}. While the link is down '
            'this node sends nothing; the writer freezes both freshness '
            'sequences and drives MotionPresent TRUE, which is the '
            'demanding direction and its contract, not ours to duplicate'
        ).format(self.attempts, self.host, self.port, why))

    def _connected(self, now):
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self.up = True
        self.connects += 1
        self.next_ping = now + self.ping_period_s
        self.emit('LINK', (
            'up: connected to the stand-in writer at {}:{} (attempt {}, '
            'connection {}). NO READING IS REPLAYED ONTO A NEW CONNECTION: '
            'the first SPD line a fresh link carries is the first reading '
            'that arrives after it, so a reconnect can never resurrect a '
            'value measured before the gap'
        ).format(self.host, self.port, self.attempts, self.connects))

    def _drain_peer(self):
        """Notice a peer close promptly, including a refused second client.

        The writer's listener accepts a second connection, closes it and
        logs the refusal. Without this read the refusal would be
        invisible until a send happened to fail; with it, the EOF is
        seen on the next tick and the link goes down where it belongs.
        The writer sends nothing on this link, so any readable byte is
        also unexpected and is logged rather than parsed - this node
        never takes instruction from the wire.
        """
        try:
            readable, _w, _x = select.select([self.sock], [], [], 0)
        except (OSError, ValueError) as exc:
            self.close('select failed: {}'.format(exc))
            return
        if not readable:
            return
        try:
            data = self.sock.recv(4096)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return
            self.close('recv failed: {}'.format(exc))
            return
        if not data:
            # TWO CAUSES PRODUCE THIS BYTE-FOR-BYTE, and this node cannot
            # tell them apart from its own end: the listener refusing us
            # as a second client, and the listener going away. Naming
            # only one would put an attribution in the evidence that the
            # observation does not support - the writer's own session log
            # is what separates them. Both are named, neither is claimed.
            self.close('peer closed the connection (EOF) - either the '
                       'listener refused this as a second speed-source '
                       'client, or the writer stopped. This end cannot '
                       'tell those apart; the writer session log can')
            return
        self.emit('LINK', 'unexpected {} bytes from the writer, ignored: '
                          'this link is one-way and this node takes no '
                          'instruction from it'.format(len(data)))

    # ---- sending -----------------------------------------------------

    def send_reading(self, channel, value_int):
        line = 'SPD {} {}\n'.format(channel.upper(), value_int)
        if self._send(line, None):
            self.sent[channel] += 1
            return True
        return False

    def send_motion(self, present, valid):
        line = 'MOT {} {}\n'.format(1 if present else 0, 1 if valid else 0)
        if self._send(line, None):
            self.sent['mot'] += 1
            return True
        return False

    def _send(self, text, detail):
        if not self.up or self.sock is None:
            return False
        try:
            self.sock.sendall(text.encode('ascii'))
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                # The line is DROPPED, not queued. A queued reading is a
                # reading that will arrive stale, which is the one thing
                # this link may not deliver.
                self.emit('LINK', 'send buffer full, {} dropped rather than '
                                  'queued'.format(text.strip()))
                return False
            self.close('send failed: {}'.format(exc))
            return False
        if detail is not None:
            self.emit('SEND', detail)
        return True

    def _close_socket(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def close(self, why):
        was_up = self.up
        self.connecting = False
        self._close_socket()
        self.up = False
        if was_up:
            self.drops += 1
            self.emit('LINK', 'down ({}). Both freshness sequences stop '
                              'advancing at the writer within one of its '
                              'cycles, and the F-program reads both channels '
                              'as missing - a demand, not a zero'.format(why))


# ------------------------------------------------------------------------ #
# The transition log
# ------------------------------------------------------------------------ #

class TransitionLog(object):
    """One file per session, unique name per start, refusing a collision.

    Same line shape as the writer's and the field evaluation's -
    `stamp | CLASS | detail` - so the three logs interleave without a
    parser. One evidence file per session; never share a path across
    restarts (LESSONS 2026-07-28).
    """

    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True)
        name = 'safe-speed-link-{}-pid{}.log'.format(
            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'), os.getpid())
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


# ------------------------------------------------------------------------ #
# The node
# ------------------------------------------------------------------------ #

def _make_node_class(Node, Bool, Float64, QoSProfile, Clock, ClockType):

    class SafeSpeedLink(Node):
        """Carries the readings. Decides nothing."""

        def __init__(self, cfg, host_override, port_override, log):
            super().__init__('safe_speed_link')
            topics = cfg['topics']
            ss = cfg['safe_speed']
            link_cfg = ss['link']
            self.log = log

            self._period = 1.0 / float(ss['publish_hz'])
            self._reading_fresh_max = float(link_cfg['reading_fresh_max_s'])
            self._motion_fresh_max = float(link_cfg['motion_fresh_max_s'])
            self._int_min = int(link_cfg['wire_int_min'])
            self._int_max = int(link_cfg['wire_int_max'])

            host, how = derive_writer_host(
                host_override if host_override else link_cfg.get('host'),
                ('AMR_SPEED_LINK_HOST', 'AMR_FIELD_LINK_HOST'))
            port = port_override if port_override else link_cfg['port']
            self.link = SpeedLink(host, port, link_cfg['ping_period_s'],
                                  link_cfg['reconnect_period_s'],
                                  link_cfg['connect_timeout_s'], self._emit)
            self._emit('LINK', 'writer address {}:{} read back from {}'
                       .format(host, port, how))

            self._slots = {key: Slot() for key in CHANNELS}
            self._motion = Slot()
            self._motion_valid = Slot()
            # Last motion pair actually put on the wire, for the
            # transition log only. It is READ BY NO SEND PATH: a
            # transition record must never become a reason to re-send.
            self._logged_motion = None
            # Silence bookkeeping. EVERY silent tick is counted and the
            # totals are reported at exit; the LOG LINE is raised only
            # once a silence has lasted long enough for the F-program to
            # be able to see it at all.
            self._logged_silence = {'a': False, 'b': False, 'mot': False}
            self._silent_ticks = {'a': 0, 'b': 0, 'mot': 0}
            self._silent_total = {'a': 0, 'b': 0, 'mot': 0}
            self._silent_since = {'a': None, 'b': None, 'mot': None}
            self._refusals = {REFUSE_NONFINITE: 0, REFUSE_RANGE: 0}
            self._stale_drops = {'a': 0, 'b': 0, 'mot': 0}

            qos = QoSProfile(depth=int(cfg['qos']['depth']))
            self.create_subscription(
                Float64, topics['drive_speed_channel_a'], self.cb_speed_a, qos)
            self.create_subscription(
                Float64, topics['drive_speed_channel_b'], self.cb_speed_b, qos)
            self.create_subscription(
                Bool, topics['drive_speed_motion_present'],
                self.cb_motion_present, qos)
            self.create_subscription(
                Bool, topics['drive_speed_motion_observation_valid'],
                self.cb_motion_valid, qos)

            # THE TICK RUNS ON STEADY TIME, NOT ON THE SIMULATION'S. The
            # readings and /clock share a transport, so a tick on
            # simulation time would stop at the moment its subject
            # stopped talking (LESSONS 2026-08-06).
            self._tick_clock = Clock(clock_type=ClockType.STEADY_TIME)
            self.create_timer(self._period, self.cb_tick,
                              clock=self._tick_clock)

            self.get_logger().info(
                'safe-speed link up: carrier for SPD/MOT/PING to the '
                'stand-in writer at {}:{} ({}), tick {:.1f} Hz. A CHANNEL '
                'GOES SILENT RATHER THAN REPEAT - a reading that stops '
                'arriving stops being sent, and the F-program reads the '
                'frozen sequence as a demand. STAND-IN path, no integrity '
                'claim: these readings arrive at the safety program as '
                'standard data.'.format(host, port, how, 1.0 / self._period))

        # ---- plumbing ------------------------------------------------

        def _emit(self, cls, detail):
            self.log.write(cls, detail)
            self.get_logger().info('{}: {}'.format(cls, detail))

        # ---- subscriptions -------------------------------------------
        #
        # Arrival time is this node's steady clock, never the message's
        # header and never the simulation's: the age that matters is how
        # long since THIS node last heard from the producer.

        def cb_speed_a(self, msg):
            self._slots['a'].put(float(msg.data), time.monotonic())

        def cb_speed_b(self, msg):
            self._slots['b'].put(float(msg.data), time.monotonic())

        def cb_motion_present(self, msg):
            self._motion.put(bool(msg.data), time.monotonic())

        def cb_motion_valid(self, msg):
            self._motion_valid.put(bool(msg.data), time.monotonic())

        # ---- the tick ------------------------------------------------

        def _note_silence(self, key, silent, now, detail):
            """Count every silent tick; log the ones that can be seen.

            THE THRESHOLD IS DERIVED, NOT COSMETIC. The client tick and
            the producer's publish both run at 20 Hz on independent
            clocks, so they beat: a single tick occasionally finds no
            new message and the next finds two, which the consume-once
            slot coalesces exactly as the writer's own 50 ms cycle
            would. One such tick is invisible to the F-program - its
            OB samples at 100 ms and its stale window is 500 ms - so
            logging it as an event would bury the silences that ARE
            events under traffic that is not.

            NOTHING IS HIDDEN BY THIS. Every silent tick is counted, the
            totals go in the exit line, and the resumption line carries
            the measured duration of the silence, so a 50 ms beat and a
            dead producer are told apart by a number rather than by
            their absence.
            """
            if silent:
                self._silent_total[key] += 1
                self._silent_ticks[key] += 1
                if self._silent_since[key] is None:
                    self._silent_since[key] = now
                if self._silent_ticks[key] == 2 \
                        and not self._logged_silence[key]:
                    self._logged_silence[key] = True
                    self._emit('SILENT', detail)
                return
            was = self._silent_ticks[key]
            since = self._silent_since[key]
            self._silent_ticks[key] = 0
            self._silent_since[key] = None
            if self._logged_silence[key]:
                self._logged_silence[key] = False
                self._emit('SILENT', '{}: sending again after {:.3f} s of '
                                     'silence ({} ticks)'.format(
                                         key, 0.0 if since is None
                                         else now - since, was))

        def cb_tick(self):
            now = time.monotonic()
            self.link.service(now)

            for key in CHANNELS:
                value, age = self._slots[key].take(
                    now, self._reading_fresh_max)
                if value is None:
                    if age is not None:
                        self._stale_drops[key] += 1
                        self._emit('REFUSED', (
                            'channel {}: a reading {:.3f} s old was DISCARDED '
                            'rather than sent - past the {:.2f} s window, and '
                            'a late reading is a non-reading'
                        ).format(key.upper(), age, self._reading_fresh_max))
                    self._note_silence(key, True, now, (
                        'channel {}: no fresh reading, so NO LINE is sent. '
                        'The writer freezes SpeedSeq{} and the F-program '
                        'reads the channel as missing - a demand, never a '
                        'zero and never the last value'
                    ).format(key.upper(), key.upper()))
                    continue
                scaled, why = scale_reading(value, self._int_min,
                                            self._int_max)
                if scaled is None:
                    self._refusals[why] += 1
                    self._emit('REFUSED', (
                        'channel {}: reading {!r} m/s is {} and was NOT '
                        'SCALED and NOT SENT. The sequence freezes and the '
                        'channel reads as missing, which is a demand'
                    ).format(key.upper(), value, why))
                    self._note_silence(key, True, now, (
                        'channel {}: refusing to send'.format(key.upper())))
                    continue
                if self.link.send_reading(key, scaled):
                    self._note_silence(key, False, now, '')
                else:
                    self._note_silence(key, True, now, (
                        'channel {}: the link would not take the line, so '
                        'the reading is DROPPED. It is not queued and not '
                        'resent - a queued reading arrives stale, which is '
                        'the one thing this link may not deliver'
                    ).format(key.upper()))

            self._service_motion(now)

        def _service_motion(self, now):
            present, p_age = self._motion.take(now, self._motion_fresh_max)
            valid, v_age = self._motion_valid.take(now, self._motion_fresh_max)
            if present is None or valid is None:
                if p_age is not None or v_age is not None:
                    self._stale_drops['mot'] += 1
                self._note_silence('mot', True, now, (
                    'motion: no fresh observation pair, so NO MOT LINE is '
                    'sent. The writer drives MotionPresent TRUE after its own '
                    'MOTION_SILENCE_MAX - an unobservable vehicle is MOVING, '
                    'never still'))
                return
            if self.link.send_motion(present, valid):
                self._note_silence('mot', False, now, '')
                pair = (present, valid)
                if pair != self._logged_motion:
                    self._logged_motion = pair
                    self._emit('MOTION', 'MOT {} {} (present={}, '
                                         'observation valid={})'.format(
                                             1 if present else 0,
                                             1 if valid else 0,
                                             present, valid))

        # ---- teardown ------------------------------------------------

        def report(self):
            return (
                'link attempts {}, connections {}, drops {}; sent SPD A {}, '
                'SPD B {}, MOT {}, PING {}; refused non-finite {}, '
                'out-of-range {}; silent ticks A {}, B {}, MOT {}; '
                'discarded stale A {}, B {}, MOT {}'.format(
                    self.link.attempts, self.link.connects, self.link.drops,
                    self.link.sent['a'], self.link.sent['b'],
                    self.link.sent['mot'], self.link.pings,
                    self._refusals[REFUSE_NONFINITE],
                    self._refusals[REFUSE_RANGE],
                    self._silent_total['a'], self._silent_total['b'],
                    self._silent_total['mot'],
                    self._stale_drops['a'], self._stale_drops['b'],
                    self._stale_drops['mot']))

        def destroy_node(self):
            self._emit('EXIT', self.report())
            self.link.close('node shutting down')
            return super().destroy_node()

    return SafeSpeedLink


# ------------------------------------------------------------------------ #
# Checks that need no simulator, no ROS and no network
# ------------------------------------------------------------------------ #

def _selftest():
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    lo, hi = -32768, 32767

    # --- the scaling -------------------------------------------------
    check('positive reading scales to signed mm/s',
          scale_reading(0.3, lo, hi) == (300, None))
    check('reverse is a direction, not a fault',
          scale_reading(-0.3, lo, hi) == (-300, None))
    check('zero is a value and is sent',
          scale_reading(0.0, lo, hi) == (0, None))
    check('the SLS limit lands exactly on its constant',
          scale_reading(0.300, lo, hi)[0] == 300)
    check('a millimetre per second survives the seam',
          scale_reading(0.001, lo, hi) == (1, None))

    # --- the refusals ------------------------------------------------
    nan = float('nan')
    inf = float('inf')
    check('NaN is never scaled and never sent',
          scale_reading(nan, lo, hi) == (None, REFUSE_NONFINITE))
    check('+inf is never scaled and never sent',
          scale_reading(inf, lo, hi) == (None, REFUSE_NONFINITE))
    check('-inf is never scaled and never sent',
          scale_reading(-inf, lo, hi) == (None, REFUSE_NONFINITE))
    check('None is never scaled and never sent',
          scale_reading(None, lo, hi) == (None, REFUSE_NONFINITE))
    check('a reading past the Int wire range is refused, not wrapped',
          scale_reading(40.0, lo, hi) == (None, REFUSE_RANGE))
    check('the negative wire bound is refused too',
          scale_reading(-40.0, lo, hi) == (None, REFUSE_RANGE))
    check('the wire bounds themselves are sendable',
          scale_reading(hi / 1000.0, lo, hi)[0] == hi
          and scale_reading(lo / 1000.0, lo, hi)[0] == lo)
    # POSITIVE CONTROL for the two refusals: the same call site, a
    # finite in-range value, DOES produce a line. A refusal that could
    # not be told from a dead code path proves nothing.
    check('positive control: a finite in-range reading is not refused',
          scale_reading(0.25, lo, hi) == (250, None))

    # --- consume-once ------------------------------------------------
    slot = Slot()
    slot.put(0.5, 100.0)
    first = slot.take(100.01, 0.25)
    second = slot.take(100.02, 0.25)
    check('a reading is taken exactly once',
          first[0] == 0.5 and abs(first[1] - 0.01) < 1e-9)
    check('the second take of one reading yields nothing',
          second == (None, None))

    slot.put(0.5, 200.0)
    slot.put(0.7, 200.01)
    check('a later arrival replaces an unsent earlier one',
          slot.take(200.02, 0.25)[0] == 0.7)

    slot.put(0.5, 300.0)
    stale = slot.take(300.5, 0.25)
    check('a reading past its window is not returned',
          stale[0] is None and abs(stale[1] - 0.5) < 1e-9)
    check('a discarded stale reading is not held for the next tick',
          slot.take(300.6, 0.25) == (None, None))
    # POSITIVE CONTROL for the silence: the same slot, a fresh arrival,
    # yields a value on the very next take. A stopped producer and a
    # broken slot look identical without this (LESSONS 2026-08-06).
    slot.put(0.9, 300.7)
    check('positive control: a fresh arrival is yielded immediately',
          slot.take(300.71, 0.25)[0] == 0.9)

    # An empty slot never invents a value, however long it is polled.
    empty = Slot()
    invented = [empty.take(t / 10.0, 0.25)[0] for t in range(50)]
    check('an empty slot never invents a reading',
          all(v is None for v in invented))

    # --- the wire grammar --------------------------------------------
    # Formed here exactly as the sender forms it, so the grammar the
    # selftest asserts is the grammar that goes on the wire.
    check('SPD line shape', 'SPD {} {}\n'.format('a'.upper(), -31)
          == 'SPD A -31\n')
    check('MOT line shape', 'MOT {} {}\n'.format(1, 0) == 'MOT 1 0\n')

    # --- the host derivation -----------------------------------------
    check('an explicit address overrides the derivation',
          derive_writer_host('192.168.1.5', ())
          == ('192.168.1.5', 'config safe_speed.link.host'))
    os.environ['AMR_SPEED_LINK_SELFTEST_HOST'] = '10.1.2.3'
    check('an environment address is read back and named',
          derive_writer_host('auto', ('AMR_SPEED_LINK_SELFTEST_HOST',))
          == ('10.1.2.3', 'environment AMR_SPEED_LINK_SELFTEST_HOST'))
    del os.environ['AMR_SPEED_LINK_SELFTEST_HOST']

    # --- the config the node will actually read ----------------------
    cfg = load_config(_DEFAULT_CONFIG)
    link_cfg = cfg['safe_speed']['link']
    check('the config carries the spec port 45016', link_cfg['port'] == 45016)
    check('the config keepalive is the spec 1 Hz',
          abs(link_cfg['ping_period_s'] - 1.0) < 1e-9)
    check('the motion window is shorter than the writer silence budget',
          link_cfg['motion_fresh_max_s'] < 0.250)
    check('the reading window matches the producer read window',
          link_cfg['reading_fresh_max_s']
          == cfg['safe_speed']['read_fresh_max_s'])
    check('the wire range is the S7 Int range',
          (link_cfg['wire_int_min'], link_cfg['wire_int_max']) == (-32768, 32767))

    for name in ran:
        print('{}  {}'.format('FAIL' if name in fails else 'pass', name))
    # Derived from the checks that ran, never typed beside them
    # (LESSONS 2026-07-28).
    print('{}/{} checks passed'.format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Carries the two speed readings and the motion '
                    'observation to the stand-in writer over the SPEC '
                    'section 11.2 link. Decides nothing.')
    parser.add_argument('--config', default=_DEFAULT_CONFIG,
                        help='named-constant file (default: %(default)s)')
    parser.add_argument('--host', default=None,
                        help='override safe_speed.link.host; the derivation '
                             'and its source are logged either way')
    parser.add_argument('--port', type=int, default=None,
                        help='override safe_speed.link.port')
    parser.add_argument('--log-dir', default=None,
                        help='session transition log directory (default: '
                             'agv/forklift/evidence/speed-link/)')
    parser.add_argument('--selftest', action='store_true',
                        help='run the checks that need no simulator, no ROS '
                             'and no network')
    args, ros_argv = parser.parse_known_args(argv)

    if args.selftest:
        return _selftest()

    cfg = load_config(args.config)

    import rclpy
    from rclpy.clock import Clock, ClockType
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from std_msgs.msg import Bool, Float64

    node_class = _make_node_class(Node, Bool, Float64, QoSProfile, Clock,
                                  ClockType)

    log_dir = args.log_dir or os.path.join(_FORKLIFT_DIR, 'evidence',
                                           'speed-link')
    log = TransitionLog(log_dir)
    print('speed-link session log: {}'.format(log.path))

    rclpy.init(args=[sys.argv[0]] + ros_argv)
    node = node_class(cfg, args.host, args.port, log)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except rclpy.executors.ExternalShutdownException:
        # SIGINT to the process, which is how a bounded evidence run
        # ends this node. It is an ordinary shutdown and the exit line
        # below still gets written.
        pass
    finally:
        node.destroy_node()
        log.close()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
