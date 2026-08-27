"""The converter shell's pure helpers, and the promises its file makes.

nodes/cmd_vel_tricycle.py is WIRING - subscriptions, a clock, message
assembly - and almost none of it can be reached without a graph. What CAN
be reached is the three functions that decide what the node SAYS, and
they are the ones an operator reads when something is wrong: the seed's
joint lookup, the status body and the status level.

  THE LEVEL IS THE ONE WORTH A TEST. It is not "did anything get
  clamped" - a curvature clamp is a hard corner and a traction clamp is
  a fast one, and both are ordinary. It is REFUSALS and MECHANICAL STEER
  CLAMPS, which on this stack are both structural: a refusal means
  something upstream is commanding a differential base, and a steer clamp
  cannot happen from a twist at all because the measured curvature
  ceiling stands inside the mechanical stop. Either one is a bug report.

NO ROS ANYWHERE. The module keeps every ROS import inside main(), which
is what lets this suite import it on the Windows python - and this file
is the reason that property is no longer theoretical.
"""
import os
import re

import pytest

import cmd_vel_tricycle as shell

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class FakeJointState(object):
    def __init__(self, name, position):
        self.name = name
        self.position = position


class FakeDiagnosticStatus(object):
    OK = 0
    WARN = 1
    ERROR = 2


def counters(**over):
    out = dict(commands=0, published=0, engagements=0, timeouts=0,
               curvature_clamps=0, steer_clamps=0, traction_clamps=0,
               refusals=0, declines=0, speed_limits=0, not_finite=0,
               lateral_terms=0)
    out.update(over)
    return out


# ----------------------------------------------------------------------
# the seed
# ----------------------------------------------------------------------

def test_the_steer_joint_is_found_by_NAME_and_never_by_index():
    # A node that read index 0 instead would seed the ramp from the fork
    # carriage and be wrong by a metre of travel.
    msg = FakeJointState(["fork_joint", "steer_joint", "drive_wheel_joint"],
                         [0.4, -0.25, 12.0])
    assert shell.joint_position(msg, "steer_joint") == -0.25


def test_a_joint_state_without_the_steer_joint_seeds_NOTHING():
    msg = FakeJointState(["fork_joint"], [0.4])
    assert shell.joint_position(msg, "steer_joint") is None


def test_a_joint_state_with_no_position_for_it_seeds_nothing_either():
    # gz's JointStatePublisher carries position and velocity, but a
    # message truncated between the two lists is a message this node
    # cannot read - and reading it as zero would centre the ramp's
    # origin on a claim nobody made.
    msg = FakeJointState(["steer_joint", "drive_wheel_joint"], [0.4])
    assert shell.joint_position(msg, "drive_wheel_joint") is None


def test_a_non_finite_position_is_not_a_seed():
    msg = FakeJointState(["steer_joint"], [float("nan")])
    assert shell.joint_position(msg, "steer_joint") is None


def test_a_seed_of_zero_IS_a_seed_and_is_not_confused_with_none():
    msg = FakeJointState(["steer_joint"], [0.0])
    assert shell.joint_position(msg, "steer_joint") == 0.0


# ----------------------------------------------------------------------
# what the status topic says
# ----------------------------------------------------------------------

def test_the_status_says_whether_the_node_is_engaged():
    pairs = dict(shell.status_pairs(counters(), None, False, None, 0.0))
    assert pairs["engaged"] == "false"
    pairs = dict(shell.status_pairs(counters(), None, True, 0.0, 0.0))
    assert pairs["engaged"] == "true"


def test_every_counter_reaches_the_wire():
    body = counters(refusals=3, traction_clamps=7)
    pairs = dict(shell.status_pairs(body, None, True, 0.0, 0.0))
    for name, value in body.items():
        assert pairs[name] == str(value)


def test_no_speed_limit_is_reported_as_none_and_not_as_zero():
    # 0.0 IS the message's own spelling of "no limit", so a status that
    # printed 0.0 would be indistinguishable from a stop.
    pairs = dict(shell.status_pairs(counters(), None, True, 0.0, 0.0))
    assert pairs["speed_limit_mps"] == "none"
    pairs = dict(shell.status_pairs(counters(), 0.3, True, 0.0, 0.0))
    assert pairs["speed_limit_mps"] == "0.300000"


def test_an_unseeded_steer_axis_is_reported_as_none_and_not_as_zero():
    pairs = dict(shell.status_pairs(counters(), None, False, None, 0.0))
    assert pairs["steer_rad"] == "none"
    pairs = dict(shell.status_pairs(counters(), None, False, 0.0, 0.0))
    assert pairs["steer_rad"] == "+0.000000"


def test_the_last_published_pair_is_on_the_wire_with_its_sign():
    pairs = dict(shell.status_pairs(counters(), None, True, 0.75, -0.700))
    assert pairs["steer_rad"] == "+0.750000"
    assert pairs["wheel_mps"] == "-0.700000"


def test_the_status_body_is_ordered_so_two_reads_can_be_diffed():
    body = shell.status_pairs(counters(), None, True, 0.0, 0.0)
    keys = [key for key, _ in body]
    assert keys[0] == "engaged"
    assert keys[-3:] == ["speed_limit_mps", "steer_rad", "wheel_mps"]
    assert keys[1:-3] == sorted(keys[1:-3])


# ----------------------------------------------------------------------
# and the level, which is the only thing in the message that judges
# ----------------------------------------------------------------------

def test_a_quiet_converter_is_OK():
    assert shell.status_level(counters(), FakeDiagnosticStatus) == \
        FakeDiagnosticStatus.OK


def test_clamps_alone_are_NOT_a_warning():
    # A curvature clamp is a hard corner and a traction clamp is a fast
    # one. Both are counted, logged and ordinary; raising the level for
    # them would teach an operator to ignore the level.
    body = counters(curvature_clamps=40, traction_clamps=900, declines=12)
    assert shell.status_level(body, FakeDiagnosticStatus) == \
        FakeDiagnosticStatus.OK


def test_a_refusal_IS_a_warning():
    # It means something upstream is commanding a differential base.
    body = counters(refusals=1)
    assert shell.status_level(body, FakeDiagnosticStatus) == \
        FakeDiagnosticStatus.WARN


def test_a_MECHANICAL_steer_clamp_is_a_warning_because_it_cannot_happen():
    # The measured curvature ceiling stands inside the mechanical stop,
    # so a twist can never reach it. If this counter moves, the two
    # limits in config.yaml have crossed.
    body = counters(steer_clamps=1)
    assert shell.status_level(body, FakeDiagnosticStatus) == \
        FakeDiagnosticStatus.WARN


# ----------------------------------------------------------------------
# the promises the file itself makes
# ----------------------------------------------------------------------

def read_shell():
    with open(os.path.join(_M5V3, "nodes", "cmd_vel_tricycle.py"),
              encoding="utf-8") as handle:
        return handle.read()


def test_no_ROS_is_imported_at_module_level():
    # The property this whole suite depends on. An rclpy import at the
    # top of this file stops the suite COLLECTING on the machine the
    # owner runs it on, and no amount of care downstream fixes that.
    body = read_shell().split('"""', 2)[-1]
    head = body.split("def main(", 1)[0]
    for banned in ("import rclpy", "from rclpy", "from geometry_msgs",
                   "from std_msgs", "from sensor_msgs", "from nav2_msgs",
                   "from diagnostic_msgs"):
        assert banned not in head, banned


def test_the_converter_never_subscribes_the_ground_truth():
    # F2 global constraint 13 and F4 constraint 18: ground truth is a
    # measurement reference and is never in the control loop. The
    # cheapest guarantee is that the file does not contain the address.
    assert "odom_ground_truth" not in read_shell()


def test_every_key_the_node_reads_is_declared_in_REQUIRED_KEYS():
    # The maintenance obligation, as a test rather than as prose. A key
    # read but not declared is refused at the callback instead of at
    # startup; a key declared but not read is a claim about this file
    # that is not true, and it survives every other check.
    body = read_shell()
    declared = set(shell.REQUIRED_KEYS)
    # \s* on both sides: this file wraps at 79 columns, so half of these
    # calls have a newline between the paren and the key.
    used = set(re.findall(r'cfg\.[sfi]\(\s*"([a-z0-9_.]+)"\s*\)', body))
    assert used - declared == set()
    assert declared - used == set()
