"""smoother.yaml's limits, RECOMPUTED from the numbers they came from.

WHY THIS FILE EXISTS. `smoother.yaml` is a ROS parameter file and
`config.yaml` is not one - that is the ownership split every params file
on this track carries (ekf.yaml's header states it first). But four of the
six limits in it are DERIVED from config.yaml's `navcmd:` block, and a
derivation written out by hand is a copy: the vehicle's measured cruise,
its measured acceleration and its measured steer ceiling all appear in
`smoother.yaml` multiplied together, and nothing in either file would
notice if one of them moved.

  IT IS `vehicle.imu_mount`'s HABIT WITH AN ASSERTION INSTEAD OF A
  WARNING. That copy is diffed against model.sdf by
  `sensor_evidence.py analyse`, which prints. This one is diffed here,
  which fails - because a smoother whose angular cap no longer matches
  the converter's curvature ceiling does not look wrong from any angle:
  every node is ALIVE, every topic is at rate, and the only symptom is a
  commanded arc quietly truncated before the node that owns the geometry
  ever sees it.

AND ONE THING THAT IS NOT A DERIVATION AND IS CHECKED ANYWAY: the message
type. `enable_stamped_cmd_vel` decides whether the smoother emits
`Twist` or `TwistStamped`, and `nodes/cmd_vel_tricycle.py` subscribes ONE
of those. The published research this phase was planned from
(docs/reports/m5v3-02 section 5) says Jazzy defaults to TwistStamped; this
rig measured False. Whichever is true, the two files have to agree, and a
disagreement is a converter that hears nothing at all.

NO ROS AND NO GAZEBO: this reads three files off disk.
"""
import math
import os

import pytest

import cmd_vel_tricycle_core as core

yaml = pytest.importorskip("yaml")

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def read(name):
    with open(os.path.join(_M5V3, name), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def config():
    return read("config.yaml")


def params():
    cfg = config()
    smoother = read(cfg["smoother"]["params_file"].split("/", 1)[1])
    return smoother[cfg["smoother"]["node_name"]]["ros__parameters"]


def derived():
    cfg = config()
    navcmd = cfg["navcmd"]
    kappa = core.curvature_max(float(navcmd["steer_command_limit_rad"]),
                               float(cfg["vehicle"]["wheelbase_m"]))
    return float(navcmd["speed_max_mps"]), float(navcmd["accel_mps2"]), kappa


# ----------------------------------------------------------------------
# the file is addressed to the node m5v3.sh starts
# ----------------------------------------------------------------------

def test_the_parameter_file_is_addressed_to_the_node_that_is_started():
    # rclcpp applies NOTHING from a block addressed to a node that is not
    # running and does not complain about it. m5v3.sh greps for the same
    # string before anything starts; this is the same check where a test
    # can reach it.
    cfg = config()
    smoother = read(cfg["smoother"]["params_file"].split("/", 1)[1])
    assert cfg["smoother"]["node_name"] in smoother


def test_the_params_file_path_in_config_resolves():
    cfg = config()
    assert cfg["smoother"]["params_file"].startswith("m5_ver3/")
    assert os.path.isfile(
        os.path.join(_M5V3, cfg["smoother"]["params_file"].split("/", 1)[1]))


# ----------------------------------------------------------------------
# the four derived numbers
# ----------------------------------------------------------------------

def test_the_linear_speed_cap_is_the_measured_cruise():
    speed, _, _ = derived()
    assert params()["max_velocity"][0] == pytest.approx(speed)
    assert params()["min_velocity"][0] == pytest.approx(-speed)


def test_the_angular_cap_is_the_speed_cap_times_the_curvature_ceiling():
    # SO IT NEVER BINDS FIRST. The geometry has one owner - the converter
    # - and a smaller cap here would truncate a twist that node would
    # have accepted, taking the speed with it because scale_velocities is
    # on.
    speed, _, kappa = derived()
    assert params()["max_velocity"][2] == pytest.approx(speed * kappa,
                                                        abs=5e-7)
    assert params()["min_velocity"][2] == pytest.approx(-speed * kappa,
                                                        abs=5e-7)


def test_the_linear_acceleration_is_the_measured_ramp():
    _, accel, _ = derived()
    assert params()["max_accel"][0] == pytest.approx(accel)
    assert params()["max_decel"][0] == pytest.approx(-accel)


def test_the_angular_acceleration_is_the_SAME_RATIO_as_the_speeds():
    # It is what makes the ramp proportional: v and w rise and fall
    # together, so the arc survives the whole ramp - and the closed-loop
    # floor from rest is the same number at every curvature, which is
    # what config.yaml's creep deadband is sized against.
    _, accel, kappa = derived()
    assert params()["max_accel"][2] == pytest.approx(accel * kappa, abs=5e-7)
    assert params()["max_decel"][2] == pytest.approx(-accel * kappa, abs=5e-7)


def test_the_two_ratios_are_the_same_ratio():
    p = params()
    assert (p["max_velocity"][2] / p["max_velocity"][0]
            == pytest.approx(p["max_accel"][2] / p["max_accel"][0], rel=1e-6))


# ----------------------------------------------------------------------
# and the ones that are arguments rather than arithmetic
# ----------------------------------------------------------------------

def test_the_lateral_axis_is_pinned_at_zero():
    # This vehicle has no lateral degree of freedom at all, so a stray vy
    # is limited to nothing rather than passed to a converter that would
    # only report it and discard it.
    p = params()
    for key in ("max_velocity", "min_velocity", "max_accel", "max_decel"):
        assert p[key][1] == 0.0


def test_the_deadband_is_zero_on_every_axis():
    # A deadband above the closed-loop floor is a DEADLOCK and not a
    # margin - config.yaml navcmd.creep_speed_mps carries the arithmetic.
    assert params()["deadband_velocity"] == [0.0, 0.0, 0.0]


def test_the_feedback_is_the_one_the_A_B_ruled_for():
    # OPEN_LOOP, against the crib's CLOSED_LOOP, on a measurement:
    # 0.339 m/s^2 of ramp against 0.150, and a stop from cruise in 0.71 m
    # against one that never completed inside the profile. smoother.yaml
    # carries the table and EVIDENCE_NAV_V3.md carries the two sessions.
    #   THE ADDRESS IS STILL NOT IN THIS FILE. m5v3.sh passes odom_topic
    #   per estimator arm, so a parameter file cannot pin the wrong one -
    #   and it can never be the ground truth, which no arm publishes.
    p = params()
    assert p["feedback"] == "OPEN_LOOP"
    assert "odom_topic" not in p


def test_the_curvature_survives_the_limiter():
    assert params()["scale_velocities"] is True


def test_the_message_type_agrees_with_the_converter_that_subscribes():
    # geometry_msgs/Twist on both sides. MEASURED on this rig 2026-08-27
    # as the Jazzy default, against published research that says
    # otherwise - so it is stated rather than inherited, and the
    # converter's own subscription is checked against the same value.
    assert params()["enable_stamped_cmd_vel"] is False
    with open(os.path.join(_M5V3, "nodes", "cmd_vel_tricycle.py"),
              encoding="utf-8") as handle:
        shell = handle.read()
    assert "from geometry_msgs.msg import Twist" in shell
    assert "TwistStamped" not in shell.split('"""', 2)[-1]


def test_the_node_self_transitions_and_does_not_bond():
    # Two lifecycle facts, both measured. autostart_node is why m5v3.sh
    # polls for ACTIVE instead of driving the transitions; the zero bond
    # is amcl.yaml's own argument, which this file does not repeat.
    p = params()
    assert p["autostart_node"] is True
    assert p["bond_heartbeat_period"] == 0.0


def test_the_smoother_dead_man_is_LONGER_than_the_converters():
    # The layer nearer the plant must not be the slower one to notice.
    assert (float(config()["navcmd"]["command_timeout_s"])
            < float(params()["velocity_timeout"]))


def test_no_topic_or_frame_is_spelled_in_the_parameter_file():
    # The ownership split, as an assertion. Every ADDRESS on this chain
    # is config.yaml's and reaches this node as a `-p` override from
    # m5v3.sh - including odom_topic, which has to follow the estimator
    # arm and therefore cannot be pinned here at all.
    for key, value in params().items():
        assert "topic" not in key, key
        assert not (isinstance(value, str) and value.startswith("/")), value


def test_the_stop_distance_from_cruise_is_stated_and_true():
    # v^2 / 2a, quoted in smoother.yaml's own comment. It is the number
    # F4 Task 2's controller look-ahead has to clear.
    speed, accel, _ = derived()
    assert speed * speed / (2.0 * accel) == pytest.approx(0.70, abs=0.005)
