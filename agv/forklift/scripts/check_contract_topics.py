#!/usr/bin/env python3
"""check_contract_topics.py - is the README's ROS contract actually on the wire?

WHY THIS EXISTS. ADR 0016 Phase 1 moves the vehicle's whole graph into its own
DDS domain. The claim that nothing was lost in the move is only worth what it
is checked against, and "the topic list looked right" is not a check - the
list is thirty names long and the interesting failure is one name missing.
So the contract table in README.md ("### ROS 2, after `launch/vehicle.launch.py`")
is PARSED and diffed against the live graph, in the domain the caller is in.

    # inside the vehicle's domain
    python3 agv/forklift/scripts/check_contract_topics.py --live

    # what the table says, with no ROS at all
    python3 agv/forklift/scripts/check_contract_topics.py --print

IT IS ALSO THE OTHER HALF OF THE BOUNDARY TEST. Run in a domain that is not
the vehicle's, every row is expected to be MISSING, and `--expect-absent`
inverts the verdict so that "I see nothing" is a pass with a name rather than
an empty screen that could equally mean the tool did not run.

A name in the table and not on the wire is a defect. A name on the wire and
not in the table is REPORTED, never failed: Nav2 and the lifecycle machinery
publish plenty this document does not describe, and the table is the vehicle's
contract rather than an inventory of the graph.
"""

import argparse
import fnmatch
import os
import re
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
DEFAULT_README = os.path.join(_FORKLIFT_DIR, 'README.md')

#: The heading whose table is the ROS-side contract. Quoted, so a rename of
#: the section is a loud failure here rather than a silently empty check.
_SECTION = '### ROS 2, after'


def contract_topics(readme_path=None):
    """Read the ROS contract table out of README.md.

    Returns the list of topic names in the order the table states them. A
    name containing `*` is a glob and is matched as one.
    """
    readme_path = readme_path or DEFAULT_README
    with open(readme_path, 'r', encoding='utf-8') as handle:
        lines = handle.read().splitlines()

    start = None
    for index, line in enumerate(lines):
        if line.startswith(_SECTION):
            start = index + 1
            break
    if start is None:
        raise RuntimeError(
            '{} has no section starting "{}". The contract table is what this '
            'check reads; an empty check that passes is worse than no '
            'check.'.format(readme_path, _SECTION))

    names = []
    for line in lines[start:]:
        if line.startswith('###') or line.startswith('## '):
            break
        if not line.startswith('|'):
            continue
        first = line.split('|')[1].strip()
        match = re.match(r'^`([^`]+)`$', first)
        if not match:
            continue                      # header row, separator row
        names.append(match.group(1))
    if not names:
        raise RuntimeError(
            '{}: section "{}" produced no topic rows.'.format(
                readme_path, _SECTION))
    return names


def live_topics():
    """Every topic name the graph shows, from THIS process's domain."""
    import rclpy
    from rclpy.node import Node

    rclpy.init()
    try:
        node = Node('check_contract_topics')
        # Discovery is not instantaneous. Spin briefly rather than asking
        # once: an empty answer taken too early reads exactly like an empty
        # graph, which is the one thing this check must not get wrong.
        deadline = node.get_clock().now().nanoseconds + 5 * 1000 * 1000 * 1000
        found = set()
        while node.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
            found.update(name for name, _ in node.get_topic_names_and_types())
        node.destroy_node()
        return sorted(found)
    finally:
        rclpy.shutdown()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--readme', default=None,
                        help='path to the README carrying the contract table')
    parser.add_argument('--print', dest='print_only', action='store_true',
                        help='print the contract and exit; needs no ROS')
    parser.add_argument('--live', action='store_true',
                        help='diff the contract against the running graph in '
                             'this process\'s ROS_DOMAIN_ID')
    parser.add_argument('--expect-absent', action='store_true',
                        help='invert the verdict: PASS when NO contract topic '
                             'is present. This is the domain-boundary test.')
    args = parser.parse_args(argv)

    contract = contract_topics(args.readme)

    if args.print_only or not args.live:
        print('contract: {} rows from {}'.format(
            len(contract), args.readme or DEFAULT_README))
        for name in contract:
            print('  {}'.format(name))
        return 0

    domain = os.environ.get('ROS_DOMAIN_ID', '(unset -> 0)')
    live = live_topics()
    print('ROS_DOMAIN_ID={}   live topics: {}'.format(domain, len(live)))

    present, missing = [], []
    for name in contract:
        if '*' in name:
            hits = fnmatch.filter(live, name)
            (present if hits else missing).append(
                '{} -> {}'.format(name, ', '.join(hits) if hits else 'nothing'))
        else:
            (present if name in live else missing).append(name)

    print('\ncontract rows present : {} of {}'.format(
        len(present), len(contract)))
    for name in present:
        print('  + {}'.format(name))
    print('\ncontract rows missing : {}'.format(len(missing)))
    for name in missing:
        print('  - {}'.format(name))

    extra = [name for name in live
             if name not in contract
             and not any('*' in c and fnmatch.fnmatch(name, c)
                         for c in contract)]
    print('\non the wire and not in the table (reported, not failed): {}'
          .format(len(extra)))
    for name in extra:
        print('  ? {}'.format(name))

    if args.expect_absent:
        ok = not present
        print('\n{}  (expected NO contract topic in domain {})'.format(
            'PASS: the boundary holds' if ok
            else 'FAIL: {} contract topics are visible from this domain'
                 .format(len(present)), domain))
    else:
        ok = not missing
        print('\n{}'.format(
            'PASS: every contract row is on the wire'
            if ok else 'FAIL: {} contract rows are missing'.format(
                len(missing))))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
