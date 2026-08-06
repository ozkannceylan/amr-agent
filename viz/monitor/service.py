#!/usr/bin/env python3
"""service.py - the read-only monitoring service.

ONE PROCESS, n VEHICLE DOMAINS, NO PRESENCE IN THE OPERATOR DOMAIN.

    python3 viz/monitor/service.py                    # every allocated vehicle
    python3 viz/monitor/service.py --vehicle F001     # one of them
    python3 viz/monitor/service.py --self-check       # no ROS, no network
    python3 viz/monitor/service.py --refcount-demo /forklift/imu --vehicle F001

WHAT IT IS. For each serial in `allocation.yaml` it creates one rclpy context
initialised with that vehicle's domain ID, one zero-endpoint node in that
context, one executor thread, and a subscribe-only presence: the map, the
localization pose, the navigation lidar and the vehicle's own TF. It serves
what it has seen over HTTP GET on loopback. It publishes nothing, calls
nothing, and offers nothing to any vehicle's graph -

    read-only by construction of the process and proven by test; not enforced
    by the middleware.

WHERE THE VEHICLE LIST COMES FROM, AND WHY NOT FROM HERE. The serial to domain
mapping has exactly one owner, `agv/forklift/vehicles/allocation.yaml`, read
through exactly one code path, `agv/forklift/scripts/vehicle_identity.py`
(invariant 10, ADR 0016 D2). This process imports that path rather than parsing
that file, so a mapping this service used and a mapping a vehicle started with
cannot disagree. When the table moves sim-side (ADR 0016 preamble), the import
below moves with it and nothing else in this layer changes.

THIS PROCESS SETS NO `ROS_DOMAIN_ID` AND NEEDS NONE. Each context carries its
own domain, which is the whole mechanism. An inherited `ROS_DOMAIN_ID` in the
operator's shell is irrelevant to it and is reported at start so a session that
exported one is not surprised.

NOTHING HERE IS A CONTROL PATH.
"""

import argparse
import os
import signal
import sys
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_THIS_DIR, '..', '..'))
_VEHICLE_SCRIPTS = os.path.join(_REPO, 'agv', 'forklift', 'scripts')
for _p in (_THIS_DIR, _VEHICLE_SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import vehicle_identity                                        # noqa: E402

import http_face                                               # noqa: E402


class MonitorService(object):
    """The process. Owns the links and answers the HTTP face's questions."""

    def __init__(self, allocation, serials, node_suffix=''):
        self.allocation = allocation
        #: Appended to each per-vehicle node name. Empty for the service. It
        #: exists so a second, short-lived instance - the section 7 refcount
        #: exercise - can stand beside a running one without a node-name
        #: collision in the vehicle's domain.
        self.node_suffix = node_suffix
        self.links = {}
        self.started_at = time.monotonic()
        #: Camera registry: serial -> {camera_id: topic}. Empty until V3-4
        #: puts a camera on the model. The lifecycle that will serve it is
        #: built and exercised; the sensor is not invented here.
        self.camera_topics = {serial: {} for serial in serials}
        self._serials = list(serials)

    # -- lifecycle -----------------------------------------------------------

    def start(self):
        from vehicle_link import VehicleLink
        for serial in self._serials:
            domain = self.allocation['vehicles'][serial]
            name = 'viz_monitor_{}{}'.format(serial.lower(), self.node_suffix)
            link = VehicleLink(serial, domain, node_name=name).start()
            self.links[serial] = link
            census = link.node.endpoint_census()
            print('watching {:>6}  domain {:<4} node {:<24} '
                  'subs {} publishers {} services {} clients {}'.format(
                      serial, domain, link.node.node_name,
                      census['subscriptions'], census['publishers'],
                      census['services'], census['clients']))
            if link.node.residual_publisher_destroyed:
                print('   {} destroyed at construction - the constructor '
                      'flags alone do not reach zero on Jazzy'.format(
                          link.node.residual_publisher_destroyed))
        return self

    def shutdown(self):
        for link in self.links.values():
            link.shutdown()

    # -- what the HTTP face asks ---------------------------------------------

    def link(self, serial):
        return self.links.get(serial)

    def describe(self):
        return {
            'service': 'amr-agent viz monitoring service',
            'plane': 'read-only monitoring (ADR 0011 D4, CLAUDE.md section 3)',
            'read_only': 'read-only by construction of the process and proven '
                         'by test; not enforced by the middleware',
            'design': 'viz/DESIGN.md',
            'methods': ['GET'],
            'allocation_table': self.allocation['path'],
            'uptime_s': round(time.monotonic() - self.started_at, 1),
            'endpoints': [
                '/vehicles',
                '/vehicles/<serial>/state',
                '/vehicles/<serial>/map',
                '/vehicles/<serial>/cameras',
                '/vehicles/<serial>/cameras/<id>/stream',
            ],
        }

    def vehicles(self):
        return {
            'serials': sorted(self.links),
            'vehicles': [{
                'serial': serial,
                'domain_id': link.domain_id,
                'node': link.node.node_name,
                'state': '/vehicles/{}/state'.format(serial),
                'map': '/vehicles/{}/map'.format(serial),
                'cameras': '/vehicles/{}/cameras'.format(serial),
            } for serial, link in sorted(self.links.items())],
            'allocation_table': self.allocation['path'],
        }

    def cameras(self, serial):
        return {
            'serial': serial,
            'cameras': sorted(self.camera_topics.get(serial, {})),
            'note': 'empty until a camera is added to the model at V3-4 '
                    '(hmi/V3-PLAN.md). Selection is subscription lifecycle '
                    'only: opening a stream creates the DDS subscription in '
                    'that vehicle context, closing it destroys it, and no '
                    'message of any kind enters a vehicle domain.',
        }

    # -- the camera mechanism, whole and unused ------------------------------

    def open_stream(self, serial, camera_id):
        """Take a viewer refcount. Returns the new count, or None if unknown."""
        link = self.links.get(serial)
        topic = (self.camera_topics.get(serial) or {}).get(camera_id)
        if link is None or topic is None:
            return None
        from sensor_msgs.msg import Image
        return link.subscriptions.acquire(topic, Image, lambda _msg: None)

    def close_stream(self, serial, camera_id):
        link = self.links.get(serial)
        topic = (self.camera_topics.get(serial) or {}).get(camera_id)
        if link is None or topic is None:
            return None
        return link.subscriptions.release(topic)


def _resolve_serials(allocation, wanted):
    known = sorted(allocation['vehicles'])
    if not wanted:
        return known
    unknown = [s for s in wanted if s not in allocation['vehicles']]
    if unknown:
        raise vehicle_identity.IdentityError(
            '{}: no domain is allocated to {}. Known: {}. This service does '
            'not guess a domain for a vehicle the allocation table does not '
            'carry.'.format(allocation['path'], ', '.join(unknown),
                            ', '.join(known)))
    return list(wanted)


def _self_check():
    """Exercise everything that needs no ROS and no network."""
    failures = []
    print('allocation table, through the vehicle layer\'s one code path:')
    allocation = vehicle_identity.load_allocation()
    print('   {}'.format(allocation['path']))
    print('   vehicles {}  vehicle_range {}  operator_domain {}'.format(
        allocation['vehicles'], allocation['vehicle_range'],
        allocation['operator_domain']))
    if allocation['operator_domain'] in allocation['vehicles'].values():
        failures.append('a vehicle is allocated the operator domain')

    print('\nthe forbidden-call list, read from the factory that owns it:')
    sys.path.insert(0, os.path.join(_REPO, 'viz', 'tools'))
    import check_construction
    tokens = check_construction.read_forbidden_calls()
    print('   {} names: {}'.format(len(tokens), ', '.join(tokens)))
    if len(tokens) < 6:
        failures.append('the forbidden-call list came back short')

    print('\nthe construction checks (DESIGN 8.2 and 8.6):')
    ok = check_construction.run(verbose=False)
    print('   {}'.format('PASS' if ok else 'FAIL'))
    if not ok:
        failures.append('the construction checks failed')

    print('\nthe HTTP face, without binding a socket:')
    face = http_face.MonitorHandler
    verbs = [n for n in dir(face) if n.startswith('do_')]
    print('   request methods defined on the handler: {}'.format(verbs))
    if verbs != ['do_GET']:
        failures.append('the handler defines a request method besides do_GET')
    probe = face.__getattr__(face, 'do_POST')
    print('   do_POST resolves to {} (the core refusal)'.format(
        getattr(probe, '__name__', probe)))
    if getattr(probe, '__name__', '') != '_method_not_allowed':
        failures.append('do_POST did not resolve to the refusal')

    print('\n{}'.format('SELF-CHECK PASS' if not failures
                        else 'SELF-CHECK FAIL: {}'.format(failures)))
    return 1 if failures else 0


def _refcount_demo(service, topic, rounds, hold_s):
    """Show the camera mechanism on a real topic, with no camera.

    DESIGN section 7 requires camera selection to be expressible as
    subscription lifecycle only. This is that lifecycle, driven against a
    vehicle-domain topic that already exists, so `ros2 node info` in the
    vehicle's domain can be watched creating and destroying a subscription
    while the publisher count stays zero throughout.
    """
    from sensor_msgs.msg import Imu
    for serial, link in sorted(service.links.items()):
        for i in range(rounds):
            before = link.node.subscribed_topics()
            n1 = link.subscriptions.acquire(topic, Imu, lambda _m: None)
            n2 = link.subscriptions.acquire(topic, Imu, lambda _m: None)
            during = link.node.subscribed_topics()
            print('[{}] round {}: viewers 0 -> {} -> {}; subscriptions {} -> {}'
                  .format(serial, i + 1, n1, n2, len(before), len(during)))
            print('     endpoints while open: {}'.format(
                link.node.endpoint_census()))
            time.sleep(hold_s)
            r1 = link.subscriptions.release(topic)
            print('     one viewer left: refcount {}; subscriptions {} '
                  '(the subscription SURVIVES a non-last close)'.format(
                      r1, len(link.node.subscribed_topics())))
            time.sleep(hold_s)
            r0 = link.subscriptions.release(topic)
            after = link.node.subscribed_topics()
            print('     last viewer left: refcount {}; subscriptions {} -> {}'
                  .format(r0, len(during), len(after)))
            print('     endpoints after close: {}'.format(
                link.node.endpoint_census()))
            if after != before:
                print('     MISMATCH: the subscription set did not return to '
                      'what it was before the view opened')
                return 1
            time.sleep(hold_s)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--vehicle', action='append', default=[],
                        help='serial to watch; repeatable. Default: every '
                             'vehicle in the allocation table')
    parser.add_argument('--bind', default=http_face.DEFAULT_BIND)
    parser.add_argument('--port', type=int, default=http_face.DEFAULT_PORT)
    parser.add_argument('--duration', type=float, default=None,
                        help='seconds to run, then exit cleanly')
    parser.add_argument('--status-period', type=float, default=5.0,
                        help='seconds between status lines. This is the only '
                             'thing this process writes while running, and it '
                             'is bounded by construction')
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--refcount-demo', metavar='TOPIC', default=None,
                        help='exercise the camera subscription lifecycle '
                             '(DESIGN section 7) against an existing topic')
    parser.add_argument('--demo-rounds', type=int, default=2)
    parser.add_argument('--demo-hold', type=float, default=4.0)
    parser.add_argument('--no-http', action='store_true')
    parser.add_argument('--node-suffix', default='',
                        help='appended to each per-vehicle node name, so a '
                             'second short-lived instance can stand beside a '
                             'running one without a name collision')
    args = parser.parse_args(argv)

    if args.self_check:
        return _self_check()

    try:
        allocation = vehicle_identity.load_allocation()
        serials = _resolve_serials(allocation, args.vehicle)
    except vehicle_identity.IdentityError as exc:
        print('REFUSED: {}'.format(exc), file=sys.stderr)
        return 2

    inherited = os.environ.get('ROS_DOMAIN_ID')
    print('monitoring service - read-only by construction of the process and '
          'proven by test; not enforced by the middleware')
    print('allocation table  {}'.format(allocation['path']))
    print('ROS_DOMAIN_ID in this shell: {!r} - not used; each context carries '
          'its own domain'.format(inherited))

    service = MonitorService(allocation, serials, args.node_suffix).start()

    stopping = {'now': False}

    def cb_signal(_signum, _frame):
        stopping['now'] = True

    signal.signal(signal.SIGINT, cb_signal)
    signal.signal(signal.SIGTERM, cb_signal)

    httpd = None
    if not args.no_http:
        httpd = http_face.serve(service, args.bind, args.port)
        print('http  GET only  http://{}:{}/  (405 for every other verb)'
              .format(args.bind, args.port))

    rc = 0
    try:
        if args.refcount_demo:
            rc = _refcount_demo(service, args.refcount_demo,
                                args.demo_rounds, args.demo_hold)
        started = time.monotonic()
        last = 0.0
        while not stopping['now']:
            if args.duration is not None and \
                    time.monotonic() - started >= args.duration:
                break
            now = time.monotonic()
            if now - last >= args.status_period:
                last = now
                for serial, link in sorted(service.links.items()):
                    state = link.state()
                    print('[{:>7.1f}s] {} pose_age_ms={} obstacles_age_ms={} '
                          'map_age_ms={} map_version={} msgs={}'.format(
                              now - started, serial, state['pose_age_ms'],
                              state['obstacles_age_ms'], state['map_age_ms'],
                              state['map_version'],
                              state['messages_received']))
                sys.stdout.flush()
            time.sleep(0.1)
    finally:
        if httpd is not None:
            httpd.shutdown()
        service.shutdown()
        print('stopped cleanly')
    return rc


if __name__ == '__main__':
    sys.exit(main())
