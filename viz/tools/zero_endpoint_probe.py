#!/usr/bin/env python3
"""zero_endpoint_probe.py - the check passing, and what failing looks like.

    python3 viz/tools/zero_endpoint_probe.py --domain 73 --hold 120

WHY THIS TOOL EXISTS. `viz/DESIGN.md` section 8.1 asks for a publishers-zero
`ros2 node info` on the running monitor node. That check only means something
if it CAN fail, and on Jazzy it very nearly does: a node built with

    enable_rosout=False, start_parameter_services=False,
    enable_logger_service=False, start_type_description_service=False

still advertises `/parameter_events`, created by `Node.__init__` itself and
reachable by no flag. A build that trusted those four switches would advertise
a publisher while claiming none - in exactly the check meant to prove it
(docs/LESSONS.md 2026-08-06).

WHAT IT DOES. It holds two nodes alive in ONE scratch domain, both subscribing
so neither is trivially empty:

    viz_probe_flags_only     the four switches, no teardown  - the COUNTEREXAMPLE
    viz_probe_full_recipe    the four switches AND the one explicit teardown

While it holds, run from a shell in that domain:

    ROS_DOMAIN_ID=<domain> ros2 daemon stop
    ROS_DOMAIN_ID=<domain> ros2 node info /viz_probe_flags_only
    ROS_DOMAIN_ID=<domain> ros2 node info /viz_probe_full_recipe

The first lists a publisher. The second lists none. The difference is one line
of source, and that is the whole content of the word "construction" in this
layer's claim -

    read-only by construction of the process and proven by test; not enforced
    by the middleware.

THE DAEMON IS STOPPED FIRST, EVERY TIME. A cold `ros2` CLI daemon cache is not
node state, and a warm one from another domain is worse than useless
(docs/LESSONS.md 2026-08-05).

SCRATCH DOMAIN. The default is 73 - outside the vehicle band 51-54 and outside
the operator domain 10, so this probe can never be mistaken for, or collide
with, a vehicle. It touches no simulator, so `GZ_PARTITION` is not its concern.
"""

import argparse
import os
import sys
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_THIS_DIR, '..', 'monitor')))

from sensor_msgs.msg import LaserScan                          # noqa: E402

from subscribe_only import LIVE, SubscribeOnlyNode             # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--domain', type=int, default=73)
    parser.add_argument('--hold', type=float, default=120.0)
    parser.add_argument('--topic', default='/probe_scan')
    args = parser.parse_args(argv)

    if 51 <= args.domain <= 54 or args.domain == 10:
        print('REFUSED: domain {} is a vehicle domain or the operator domain '
              'in allocation.yaml. This probe runs in a scratch domain so it '
              'can never be mistaken for a vehicle.'.format(args.domain),
              file=sys.stderr)
        return 2

    variants = [
        ('viz_probe_flags_only', False,
         'the four constructor switches alone - THE COUNTEREXAMPLE'),
        ('viz_probe_full_recipe', True,
         'the same switches AND the one explicit teardown'),
    ]

    nodes = []
    print('scratch domain {}\n'.format(args.domain))
    for name, strip, note in variants:
        node = SubscribeOnlyNode(name, args.domain, strip_residual=strip)
        node.subscribe(args.topic, LaserScan, lambda _m: None, LIVE)
        node.spin_in_thread()
        nodes.append(node)
        census = node.endpoint_census()
        print('{:<24} {}'.format(name, note))
        print('   strip_residual={}  destroyed={!r}'.format(
            strip, node.residual_publisher_destroyed))
        print('   process-side census: {}'.format(census))
        print('   this census is the PROCESS\'s view. The fact is what the '
              'graph advertises:')
        print('   ROS_DOMAIN_ID={} ros2 node info /{}\n'.format(
            args.domain, name))

    print('holding {:.0f} s. Stop the CLI daemon first:'.format(args.hold))
    print('   ROS_DOMAIN_ID={} ros2 daemon stop'.format(args.domain))
    sys.stdout.flush()
    try:
        time.sleep(args.hold)
    except KeyboardInterrupt:
        pass
    finally:
        for node in nodes:
            node.shutdown()
        print('probe down')
    return 0


if __name__ == '__main__':
    sys.exit(main())
