#!/usr/bin/env python3
"""vehicle_identity.py - resolve one forklift's identity, with no ROS.

WHAT THIS IS. The single code path that joins a per-vehicle config file
(vehicles/<serial>.yaml) to the serial -> DDS domain mapping
(vehicles/allocation.yaml). Both the launcher (vehicle_image.py) and the
vehicle image's launch file import it, so there is one reader of the mapping
and not two that could disagree (invariant 10, ADR 0016 D2).

WHY IT REFUSES RATHER THAN GUESSES. A domain ID is what makes one vehicle's
graph invisible to another. Every failure of that lookup - a serial with no
allocation, an ID outside the safe 0-101 range, an ID outside the reserved
vehicle band, two vehicles allocated the same ID, a per-vehicle file that
carries a domain of its own - fails CLOSED here, before a single process
starts. A vehicle that quietly lands in the wrong domain looks exactly like a
working vehicle until something else is in that domain too.

It imports no ROS and starts nothing:

    python3 agv/forklift/scripts/vehicle_identity.py --self-check
    python3 agv/forklift/scripts/vehicle_identity.py --vehicle F001
"""

import argparse
import os
import sys

import yaml

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
DEFAULT_VEHICLES_DIR = os.path.join(_FORKLIFT_DIR, 'vehicles')
ALLOCATION_BASENAME = 'allocation.yaml'

#: The environment variable that IS the boundary. Named once.
DOMAIN_ENV = 'ROS_DOMAIN_ID'


class IdentityError(RuntimeError):
    """A refusal. Every message names the file and the rule that failed."""


class VehicleIdentity(object):
    """One machine: its serial, its domain, where it stands.

    Attributes are read-only by convention. Nothing here is a behavioural
    constant - those stay in config.yaml, which every vehicle shares.
    """

    def __init__(self, serial, domain_id, spawn, initial_pose,
                 config_path, allocation_path):
        self.serial = serial
        self.domain_id = domain_id
        self.spawn = spawn                  # world frame; simulation only
        self.initial_pose = initial_pose    # map frame; what AMCL is seeded with
        self.config_path = config_path
        self.allocation_path = allocation_path

    def describe(self):
        return '\n'.join([
            'serial                {}'.format(self.serial),
            'domain id             {}   (from {})'.format(
                self.domain_id, os.path.basename(self.allocation_path)),
            'per-vehicle config    {}'.format(self.config_path),
            'spawn   world frame   x {:+.4f}  y {:+.4f}  z {:+.4f}  yaw {:+.6f}'
            .format(self.spawn['x_m'], self.spawn['y_m'],
                    self.spawn['z_m'], self.spawn['yaw_rad']),
            'initial map frame     x {:+.6f}  y {:+.6f}  yaw {:+.6f}'.format(
                self.initial_pose['x_m'], self.initial_pose['y_m'],
                self.initial_pose['yaw_rad']),
        ])


def _load_yaml(path, what):
    if not os.path.isfile(path):
        raise IdentityError('{} not found at {}'.format(what, path))
    with open(path, 'r', encoding='utf-8') as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise IdentityError('{} at {} did not parse as a mapping'.format(
            what, path))
    return loaded


def _require(block, key, path, what):
    if key not in block:
        raise IdentityError('{} at {} has no `{}`'.format(what, path, key))
    return block[key]


def load_allocation(vehicles_dir=None):
    """Read and VALIDATE the serial -> domain table.

    The validation is the point. An allocation table that is merely parsed is
    a list of numbers; one that is checked is an allocation.
    """
    vehicles_dir = vehicles_dir or DEFAULT_VEHICLES_DIR
    path = os.path.join(vehicles_dir, ALLOCATION_BASENAME)
    doc = _load_yaml(path, 'the domain allocation table')

    safe_lo, safe_hi = _require(doc, 'domain_range', path, 'allocation')
    veh_lo, veh_hi = _require(doc, 'vehicle_range', path, 'allocation')
    operator = _require(doc, 'operator_domain', path, 'allocation')
    vehicles = _require(doc, 'vehicles', path, 'allocation')

    if not isinstance(vehicles, dict) or not vehicles:
        raise IdentityError(
            '{}: `vehicles` must be a non-empty serial -> domain mapping. An '
            'empty table means no vehicle can start, which is a stop rather '
            'than a default.'.format(path))

    if not (safe_lo <= veh_lo <= veh_hi <= safe_hi):
        raise IdentityError(
            '{}: vehicle_range [{}, {}] is not inside domain_range [{}, {}]. '
            'An ID above {} collides with the Linux ephemeral port range '
            '(ADR 0016 F1).'.format(path, veh_lo, veh_hi, safe_lo, safe_hi,
                                    safe_hi))

    if not (safe_lo <= operator <= safe_hi):
        raise IdentityError(
            '{}: operator_domain {} is outside the safe range [{}, {}].'
            .format(path, operator, safe_lo, safe_hi))
    if veh_lo <= operator <= veh_hi:
        raise IdentityError(
            '{}: operator_domain {} sits inside vehicle_range [{}, {}]. The '
            'operator side is not a vehicle and must not be able to become '
            'one by allocation.'.format(path, operator, veh_lo, veh_hi))

    seen = {}
    for serial, domain in vehicles.items():
        if not isinstance(domain, int) or isinstance(domain, bool):
            raise IdentityError(
                '{}: domain for {} is {!r}, not an integer.'.format(
                    path, serial, domain))
        if not (veh_lo <= domain <= veh_hi):
            raise IdentityError(
                '{}: {} is allocated domain {}, outside vehicle_range '
                '[{}, {}].'.format(path, serial, domain, veh_lo, veh_hi))
        if domain in seen:
            raise IdentityError(
                '{}: domain {} is allocated to both {} and {}. Two vehicles '
                'in one domain is exactly the shared graph ADR 0016 D1 '
                'exists to prevent, and it would look like one working '
                'vehicle with duplicate node names.'.format(
                    path, domain, seen[domain], serial))
        seen[domain] = serial

    return {
        'path': path,
        'domain_range': (safe_lo, safe_hi),
        'vehicle_range': (veh_lo, veh_hi),
        'operator_domain': operator,
        'vehicles': dict(vehicles),
    }


def load_identity(serial, vehicles_dir=None):
    """Resolve one serial into a VehicleIdentity, or refuse."""
    vehicles_dir = vehicles_dir or DEFAULT_VEHICLES_DIR
    allocation = load_allocation(vehicles_dir)

    if serial not in allocation['vehicles']:
        raise IdentityError(
            '{}: no domain is allocated to serial {!r}. Known: {}. A vehicle '
            'with no allocation is not started with a guessed domain - it is '
            'allocated one first.'.format(
                allocation['path'], serial,
                ', '.join(sorted(allocation['vehicles']))))
    domain_id = allocation['vehicles'][serial]

    config_path = os.path.join(vehicles_dir, '{}.yaml'.format(serial))
    doc = _load_yaml(config_path, 'the per-vehicle config')

    declared = _require(doc, 'serial_number', config_path, 'per-vehicle config')
    if str(declared) != str(serial):
        raise IdentityError(
            '{}: serial_number is {!r} but the file is {}.yaml. The file name '
            'and the datum must be the same machine.'.format(
                config_path, declared, serial))

    # The one thing a per-vehicle file may NOT do (invariant 10).
    for forbidden in ('domain_id', 'domain', 'ros_domain_id'):
        if forbidden in doc:
            raise IdentityError(
                '{} carries `{}`. The serial -> domain mapping has exactly '
                'one owner, {}, and a second copy of a number is how the two '
                'come to disagree (invariant 10).'.format(
                    config_path, forbidden,
                    os.path.basename(allocation['path'])))

    spawn = _require(doc, 'spawn', config_path, 'per-vehicle config')
    initial = _require(doc, 'initial_pose', config_path, 'per-vehicle config')
    for key in ('x_m', 'y_m', 'z_m', 'yaw_rad'):
        _require(spawn, key, config_path, 'per-vehicle config `spawn`')
    for key in ('x_m', 'y_m', 'yaw_rad'):
        _require(initial, key, config_path,
                 'per-vehicle config `initial_pose`')

    return VehicleIdentity(
        serial=str(serial),
        domain_id=int(domain_id),
        spawn={k: float(spawn[k]) for k in ('x_m', 'y_m', 'z_m', 'yaw_rad')},
        initial_pose={k: float(initial[k]) for k in ('x_m', 'y_m', 'yaw_rad')},
        config_path=config_path,
        allocation_path=allocation['path'],
    )


def check_environment_domain(identity):
    """Refuse if the environment we were handed is not this vehicle's domain.

    A launch file cannot change the domain of the processes it starts after
    the fact in any way that is safe - launch_ros' own node talks to the
    lifecycle nodes it transitions, so it has to be in their domain too. So
    the domain is set by the LAUNCHER, before `ros2 launch` runs, and this is
    the check that it was: a vehicle image started by hand in an inherited
    shell domain would come up looking perfectly healthy in somebody else's
    graph.
    """
    raw = os.environ.get(DOMAIN_ENV)
    if raw is None or raw.strip() == '':
        raise IdentityError(
            '{} is not set. The vehicle image runs inside its own DDS domain '
            '(ADR 0016 D1) and does not pick one for itself here. Start it '
            'through scripts/vehicle_image.py, which sets it from {}.'.format(
                DOMAIN_ENV, os.path.basename(identity.allocation_path)))
    try:
        current = int(raw)
    except ValueError:
        raise IdentityError(
            '{} is {!r}, which is not an integer.'.format(DOMAIN_ENV, raw))
    if current != identity.domain_id:
        raise IdentityError(
            '{} is {} but {} is allocated domain {} in {}. Refusing to start: '
            'a vehicle in the wrong domain is invisible to everything that '
            'expects it and visible to whatever else is there.'.format(
                DOMAIN_ENV, current, identity.serial, identity.domain_id,
                os.path.basename(identity.allocation_path)))
    return current


def _self_check():
    """Exercise the refusals against temporary tables. No ROS, no simulator."""
    import tempfile

    failures = []

    def expect_refusal(label, allocation_doc, vehicle_doc, serial='F001'):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, ALLOCATION_BASENAME), 'w',
                      encoding='utf-8') as handle:
                yaml.safe_dump(allocation_doc, handle)
            if vehicle_doc is not None:
                with open(os.path.join(tmp, '{}.yaml'.format(serial)), 'w',
                          encoding='utf-8') as handle:
                    yaml.safe_dump(vehicle_doc, handle)
            try:
                load_identity(serial, vehicles_dir=tmp)
            except IdentityError as exc:
                print('  refused as intended: {}\n    -> {}'.format(
                    label, ' '.join(str(exc).split())[:96]))
                return
            failures.append(label)
            print('  NOT REFUSED: {}'.format(label))

    good_alloc = {
        'domain_range': [0, 101], 'vehicle_range': [51, 54],
        'operator_domain': 10, 'vehicles': {'F001': 51},
    }
    good_vehicle = {
        'serial_number': 'F001',
        'spawn': {'x_m': 0.0, 'y_m': 0.0, 'z_m': 0.05, 'yaw_rad': 0.0},
        'initial_pose': {'x_m': 0.0, 'y_m': 0.0, 'yaw_rad': 0.0},
    }

    print('refusals:')
    expect_refusal(
        'a domain outside the vehicle range',
        dict(good_alloc, vehicles={'F001': 7}), good_vehicle)
    expect_refusal(
        'two vehicles allocated one domain',
        dict(good_alloc, vehicles={'F001': 51, 'F002': 51}), good_vehicle)
    expect_refusal(
        'a vehicle range outside the safe 0-101 range',
        dict(good_alloc, vehicle_range=[99, 120], vehicles={'F001': 100}),
        good_vehicle)
    expect_refusal(
        'the operator domain inside the vehicle range',
        dict(good_alloc, operator_domain=52), good_vehicle)
    expect_refusal(
        'a serial with no allocation',
        dict(good_alloc, vehicles={'F002': 52}), good_vehicle)
    expect_refusal(
        'a per-vehicle file carrying its own domain id',
        good_alloc, dict(good_vehicle, domain_id=51))
    expect_refusal(
        'a per-vehicle file whose serial does not match its name',
        good_alloc, dict(good_vehicle, serial_number='F009'))
    expect_refusal(
        'a per-vehicle file with no spawn pose',
        good_alloc, {k: v for k, v in good_vehicle.items() if k != 'spawn'})

    print('\nthe committed tables:')
    try:
        identity = load_identity('F001')
        print(identity.describe())
    except IdentityError as exc:
        failures.append('the committed tables did not resolve')
        print('  REFUSED: {}'.format(exc))

    print('\nthe environment check:')
    saved = os.environ.get(DOMAIN_ENV)
    try:
        identity = load_identity('F001')
        for value, should_pass in ((None, False), ('', False),
                                   (str(identity.domain_id + 1), False),
                                   (str(identity.domain_id), True)):
            if value is None:
                os.environ.pop(DOMAIN_ENV, None)
            else:
                os.environ[DOMAIN_ENV] = value
            try:
                check_environment_domain(identity)
                passed = True
            except IdentityError:
                passed = False
            mark = 'ok' if passed == should_pass else 'WRONG'
            if passed != should_pass:
                failures.append('environment check with {!r}'.format(value))
            print('  {}={!r:>6}  accepted={}  {}'.format(
                DOMAIN_ENV, value, passed, mark))
    finally:
        os.environ.pop(DOMAIN_ENV, None)
        if saved is not None:
            os.environ[DOMAIN_ENV] = saved

    print('\n{}'.format('SELF-CHECK PASS' if not failures
                        else 'SELF-CHECK FAIL: {}'.format(failures)))
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--vehicle', default=None,
                        help='serial number to resolve, e.g. F001')
    parser.add_argument('--vehicles-dir', default=None,
                        help='directory holding allocation.yaml and the '
                             'per-vehicle config files')
    parser.add_argument('--self-check', action='store_true',
                        help='exercise every refusal against temporary '
                             'tables and exit')
    args = parser.parse_args(argv)

    if args.self_check:
        return _self_check()
    if not args.vehicle:
        parser.error('give --vehicle <serial> or --self-check')
    try:
        print(load_identity(args.vehicle, args.vehicles_dir).describe())
    except IdentityError as exc:
        print('REFUSED: {}'.format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
