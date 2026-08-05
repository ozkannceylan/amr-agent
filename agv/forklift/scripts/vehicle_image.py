#!/usr/bin/env python3
"""vehicle_image.py - start one forklift's own computer.

WHAT IT IS. The stand-in, in simulation, for the systemd unit a real forklift
would run (ADR 0016 D5): it reads one per-vehicle config, puts the process
into that vehicle's own DDS domain, and hands over to
launch/vehicle_image.launch.py. One image, one config file, one machine.

    python3 agv/forklift/scripts/vehicle_image.py --vehicle F001

WHY THE DOMAIN IS SET HERE AND NOT IN THE LAUNCH FILE. ROS_DOMAIN_ID has to be
in the environment before `ros2 launch` starts. launch_ros' own node is what
transitions the seven lifecycle nodes of the vehicle image, so it must be in
the same domain as they are; a domain set from inside the launch description
would apply to the child processes and leave the launcher itself outside,
where its transitions would go unheard and the stack would stop dead with
nothing in any log that reads as wrong. So: the unit sets the identity, the
launch checks it (vehicle_identity.check_environment_domain) and refuses if it
disagrees.

WHAT IT DELIBERATELY DOES NOT SET. GZ_PARTITION. That is the SIMULATOR's
boundary, not the vehicle's, and the world is shared: every vehicle image and
the sim side belong to one partition. It is inherited from the environment and
this script only warns when it is missing, because a missing partition is a
run that collides with another session's simulator rather than a vehicle
misconfiguration (docs/LESSONS.md 2026-07-27).

NOTHING HERE IS A CONTROL PATH. It sets two environment variables and execs a
launch.
"""

import argparse
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_LAUNCH = os.path.join(_FORKLIFT_DIR, 'launch', 'vehicle_image.launch.py')

if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
import vehicle_identity  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog='Any further `name:=value` arguments are passed through to the '
               'launch file unchanged.')
    parser.add_argument('--vehicle', default='F001',
                        help='serial number, e.g. F001 (default: F001)')
    parser.add_argument('--vehicles-dir', default=None,
                        help='directory holding allocation.yaml and the '
                             'per-vehicle config files')
    parser.add_argument('--dry-run', action='store_true',
                        help='resolve the identity, print what would be '
                             'started and the environment it would run in, '
                             'and exit without starting anything')
    args, passthrough = parser.parse_known_args(argv)

    try:
        identity = vehicle_identity.load_identity(
            args.vehicle, args.vehicles_dir)
    except vehicle_identity.IdentityError as exc:
        print('REFUSED: {}'.format(exc), file=sys.stderr)
        return 2

    inherited = os.environ.get(vehicle_identity.DOMAIN_ENV)
    if inherited is not None and inherited.strip() != str(identity.domain_id):
        # Not a refusal: this script IS the thing that decides the domain, and
        # an inherited shell value is a memory rather than a source. It is
        # said out loud because a session that had exported one is about to
        # find its `ros2` commands looking at a different graph.
        print('note: {} was {!r} in this environment and is being set to {} '
              'from {}'.format(vehicle_identity.DOMAIN_ENV, inherited,
                               identity.domain_id,
                               os.path.basename(identity.allocation_path)))
    os.environ[vehicle_identity.DOMAIN_ENV] = str(identity.domain_id)

    if not os.environ.get('GZ_PARTITION'):
        print('warning: GZ_PARTITION is not set. gz transport is not DDS, so '
              'the domain above does not isolate the simulator: this vehicle '
              'will spawn into whatever gz server is reachable. Set the same '
              'partition the sim side was started with.')

    cmd = ['ros2', 'launch', _LAUNCH, 'vehicle:={}'.format(identity.serial)]
    if args.vehicles_dir:
        cmd.append('vehicles_dir:={}'.format(os.path.abspath(
            args.vehicles_dir)))
    cmd.extend(passthrough)

    print(identity.describe())
    print('{}={}  GZ_PARTITION={}'.format(
        vehicle_identity.DOMAIN_ENV,
        os.environ[vehicle_identity.DOMAIN_ENV],
        os.environ.get('GZ_PARTITION', '(unset)')))
    print(' '.join(cmd))
    sys.stdout.flush()

    if args.dry_run:
        return 0

    os.execvp(cmd[0], cmd)


if __name__ == '__main__':
    sys.exit(main())
