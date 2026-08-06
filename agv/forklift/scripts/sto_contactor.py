#!/usr/bin/env python3
"""The STO contactor - torque removal at the plant (m5-50).

WHAT THIS NODE IS
-----------------
It sits between the vehicle's three actuator command topics and the three
terminals model.sdf's joint controllers actually listen on, and it is the
ONLY publisher of those terminals:

    /forklift/gz/steer_cmd     ->  /forklift/gz/actuator/steer_cmd
    /forklift/gz/traction_cmd  ->  /forklift/gz/actuator/traction_cmd
    /forklift/gz/fork_cmd      ->  /forklift/gz/actuator/fork_cmd

While torque is present it forwards one message for one message and
changes no value. On the safety program's TorqueOffDemand it LATCHES OPEN:
it forwards nothing further, drives the traction terminal to a standing
zero (the holding brake) and holds the steer and fork terminals at their
last forwarded values. Authority returns only when the demand falls, which
happens only when the monitored reset clears the demanding latch inside the
F-program - and motion then needs a fresh command, because the value
standing at the terminal is the brake's.

WHAT IT IS NOT
--------------
A stand-in, and labelled one wherever it appears. The safety path it
models is hardwired and onboard (CLAUDE.md invariant 1); this is Python on
the process side of the vehicle, simulating that path's EFFECT ON THE
PLANT so that SS1's second stage is observable rather than nominal. No
Category, no Performance Level, no SIL, no PFH is claimed for it or
implied by it (ADR 0011 D5). It forms no demand: the demand is the
F-program's and arrives over the bridge (invariant 10, one owner).

WHY THE INTERLOCK IS HERE AND NOT IN A COMMAND NODE
---------------------------------------------------
Five committed publishers address the plant's command topics directly -
forklift_io.py, localization_run.py, steer_bench.py, safe_speed_bench.py
and sim/scenarios/warehouse_mapping_route.py. An interlock inside any one
of them would be bypassed by the other four, and "the vehicle is deaf to
commands" would be false for four paths out of five. An interlock at the
model's own inputs cannot be bypassed by anything that speaks ROS.

THE FAIL DIRECTION, STATED RATHER THAN ASSUMED
----------------------------------------------
The ABSENCE of the demand is not torque-off. Loss of supervision is a
degraded mode and not a safety event (invariant 2), and the controlled
stop it calls for already exists one layer up in the envelope gate's stale
rule. So this node latches on an OBSERVED TRUE and releases on an OBSERVED
FALSE, and a link that never speaks leaves it closed. The alternative -
inferring torque-off from silence - would put a safety reaction on the
network's silence, which is the thing invariant 1 exists to prevent, and
would make every run without a bridge a dead vehicle.

The direction that IS fail-safe here is the node's own absence: with this
node not running, nothing publishes the terminals at all and the plant
receives no command from anyone. A forgotten contactor is a vehicle that
does not move, never a vehicle that moves unsupervised.

AND WHAT THAT COSTS, WHICH IS WHY EVERY EVIDENCE RUN NEEDS A POSITIVE
CONTROL: after this node exists, "the vehicle did not move" has two
causes - a correct refusal and a missing contactor - and no observation of
stillness distinguishes them on its own. See
agv/forklift/PLANT-CHANGE-INVENTORY.md section 8.
"""

import argparse
import os
import sys

import yaml

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'config.yaml'))


def _load(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def _build_node(cfg):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from std_msgs.msg import Bool, Float64

    topics = cfg['topics']
    sto = cfg['sto']

    class StoContactor(Node):
        """One job: join the command topics to the terminals, or refuse
        to."""

        def __init__(self):
            super().__init__('sto_contactor')

            self.hold_period_s = 1.0 / sto['hold_publish_hz']
            self.brake_traction = float(sto['brake_traction_radps'])
            self.hold_last_position = bool(sto['hold_last_position'])
            self.log_throttle_s = sto['log_throttle_s']

            qos = QoSProfile(depth=cfg['qos']['depth'])

            # The terminals. This node is their only publisher.
            self.pub_steer = self.create_publisher(
                Float64, topics['gz_actuator_steer_cmd'], qos)
            self.pub_traction = self.create_publisher(
                Float64, topics['gz_actuator_traction_cmd'], qos)
            self.pub_fork = self.create_publisher(
                Float64, topics['gz_actuator_fork_cmd'], qos)
            self.pub_applied = self.create_publisher(
                Bool, topics['safety_torque_off_applied'], qos)

            self.sub_steer = self.create_subscription(
                Float64, topics['gz_steer_cmd'], self.cb_steer_cmd, qos)
            self.sub_traction = self.create_subscription(
                Float64, topics['gz_traction_cmd'], self.cb_traction_cmd, qos)
            self.sub_fork = self.create_subscription(
                Float64, topics['gz_fork_cmd'], self.cb_fork_cmd, qos)
            self.sub_demand = self.create_subscription(
                Bool, topics['safety_torque_off_demand'],
                self.cb_torque_off_demand, qos)

            # THE LATCH. False is closed, which is torque present. It
            # starts closed because absence of the demand is not
            # torque-off; see the module docstring.
            self.torque_off = False
            # Whether a demand has EVER been seen. Diagnosis only - it is
            # what tells "closed because the chain says torque is
            # present" from "closed because no chain has spoken yet".
            self.demand_seen = False

            # The last value forwarded through each terminal. None means
            # nothing has been forwarded yet and there is therefore
            # nothing to hold.
            self.last_steer = None
            self.last_traction = None
            self.last_fork = None

            self.forwarded = 0
            self.refused = 0

            self.timer_hold = self.create_timer(
                self.hold_period_s, self.cb_hold_cycle)

            self.get_logger().info(
                'STO contactor up, latch CLOSED. Terminals: {}, {}, {}. '
                'Demand in: {}. This is a STAND-IN for a hardwired onboard '
                'inhibit - no PL, Category, SIL or PFH is claimed.'.format(
                    topics['gz_actuator_steer_cmd'],
                    topics['gz_actuator_traction_cmd'],
                    topics['gz_actuator_fork_cmd'],
                    topics['safety_torque_off_demand']))

        # ---- the demand ------------------------------------------------

        def cb_torque_off_demand(self, msg):
            demanded = bool(msg.data)
            self.demand_seen = True
            if demanded == self.torque_off:
                return
            self.torque_off = demanded
            if demanded:
                # THE TERMINAL VALUE FIRST, AND ONLY THEN THE STANDING
                # ORDER. Publishing the brake immediately rather than
                # waiting for the next hold tick is the LESSONS 2026-08-04
                # rule: a state whose purpose is to stop must emit its own
                # terminal value, not leave the previous one standing for
                # up to one period.
                self._publish_brake()
                self.get_logger().warn(
                    'TORQUE OFF: latch OPEN. Traction terminal driven to '
                    '{:.3f} rad/s and held; steer and fork terminals held '
                    'at their last forwarded values. Every command is now '
                    'refused, including a permissive envelope. Only the '
                    'demand falling closes this latch.'.format(
                        self.brake_traction))
            else:
                self.get_logger().warn(
                    'TORQUE RESTORED: latch CLOSED after {} refused '
                    'commands. Nothing moves until a FRESH command '
                    'arrives - the value standing at the traction '
                    'terminal is the brake\'s.'.format(self.refused))
                self.refused = 0
            self._publish_applied()

        # ---- the three command channels --------------------------------

        def cb_steer_cmd(self, msg):
            if self.torque_off:
                self.refused += 1
                return
            self.last_steer = float(msg.data)
            self.pub_steer.publish(msg)
            self.forwarded += 1

        def cb_traction_cmd(self, msg):
            if self.torque_off:
                self.refused += 1
                return
            self.last_traction = float(msg.data)
            self.pub_traction.publish(msg)
            self.forwarded += 1

        def cb_fork_cmd(self, msg):
            if self.torque_off:
                self.refused += 1
                return
            self.last_fork = float(msg.data)
            self.pub_fork.publish(msg)
            self.forwarded += 1

        # ---- the standing orders ---------------------------------------

        def _publish_brake(self):
            from std_msgs.msg import Float64
            msg = Float64()
            msg.data = self.brake_traction
            self.pub_traction.publish(msg)

        def _publish_applied(self):
            from std_msgs.msg import Bool
            msg = Bool()
            msg.data = self.torque_off
            self.pub_applied.publish(msg)

        def cb_hold_cycle(self):
            self._publish_applied()
            if not self.torque_off:
                return
            self._publish_brake()
            if not self.hold_last_position:
                return
            from std_msgs.msg import Float64
            if self.last_steer is not None:
                held = Float64()
                held.data = self.last_steer
                self.pub_steer.publish(held)
            if self.last_fork is not None:
                held = Float64()
                held.data = self.last_fork
                self.pub_fork.publish(held)

    return StoContactor()


def _self_check():
    """Runs without ROS. Checks the two properties that are logic and not
    plumbing: the latch's polarity, and that a refusal is not a forward."""
    failures = []

    class Fake(object):
        def __init__(self):
            self.torque_off = False
            self.forwarded = 0
            self.refused = 0
            self.published = []

        def command(self, value):
            if self.torque_off:
                self.refused += 1
                return
            self.forwarded += 1
            self.published.append(value)

    fake = Fake()
    fake.command(4.0)
    if fake.published != [4.0]:
        failures.append('a closed latch must forward the value unchanged')

    fake.torque_off = True
    fake.command(4.0)
    fake.command(-2.0)
    if fake.published != [4.0]:
        failures.append('an open latch must forward nothing')
    if fake.refused != 2:
        failures.append('an open latch must count what it refused')

    # THE PROPERTY THE OBSERVABLE RESTS ON, ASSERTED AGAINST THE SOURCE
    # RATHER THAN ARGUED IN A COMMENT: the latch has exactly one writer,
    # and it is the demand callback. If any other method could assign it,
    # "stays deaf even if the envelope reopens" would be a claim about
    # code nobody checked.
    with open(os.path.abspath(__file__), encoding='utf-8') as handle:
        source = handle.read().split('def _self_check')[0]
    writers = []
    method = None
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith('def '):
            method = stripped[4:].split('(')[0]
        if 'self.torque_off' in stripped and '=' in stripped.split(
                'self.torque_off')[1][:2]:
            writers.append(method)
    if sorted(set(writers)) != ['__init__', 'cb_torque_off_demand']:
        failures.append(
            'the latch must be written only by __init__ and the demand '
            'callback; found ' + repr(sorted(set(writers))))

    fake.torque_off = False
    fake.command(1.0)
    if fake.published != [4.0, 1.0]:
        failures.append('a closed latch must forward again after release')

    for line in failures:
        print('FAIL ' + line)
    print('self-check: {}'.format('PASS' if not failures else 'FAIL'))
    return 0 if not failures else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=_DEFAULT_CONFIG)
    parser.add_argument('--self-check', action='store_true',
                        help='run the logic checks and exit, no ROS')
    known, rest = parser.parse_known_args(argv)

    if known.self_check:
        return _self_check()

    cfg = _load(known.config)

    import rclpy
    rclpy.init(args=rest)
    node = _build_node(cfg)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
