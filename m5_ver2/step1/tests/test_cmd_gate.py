"""cmd_gate.py's gate decision. No ROS graph is started."""
import cmd_gate

SPEED_MAX = 1.50
STEER_MAX = 1.31


def test_enabled_gate_passes_a_command_through():
    assert cmd_gate.gated_command(
        0.8, 0.4, True, SPEED_MAX, STEER_MAX) == (0.8, 0.4)


def test_inhibited_gate_zeroes_both_axes():
    assert cmd_gate.gated_command(
        0.8, 0.4, False, SPEED_MAX, STEER_MAX) == (0.0, 0.0)


def test_inhibited_gate_zeroes_steer_as_well_as_traction():
    # Steering a truck that is not allowed to move is still motion at the
    # steer joint, and the brief's zero is a zero Twist, not a zero speed.
    _, steer = cmd_gate.gated_command(0.0, 1.31, False, SPEED_MAX, STEER_MAX)
    assert steer == 0.0


def test_speed_is_clamped_to_the_vehicle_limit():
    traction, _ = cmd_gate.gated_command(9.0, 0.0, True, SPEED_MAX, STEER_MAX)
    assert traction == SPEED_MAX


def test_reverse_speed_is_clamped_symmetrically():
    traction, _ = cmd_gate.gated_command(-9.0, 0.0, True, SPEED_MAX, STEER_MAX)
    assert traction == -SPEED_MAX


def test_steer_is_clamped_to_the_mechanical_stop():
    _, steer = cmd_gate.gated_command(0.0, 5.0, True, SPEED_MAX, STEER_MAX)
    assert steer == STEER_MAX


def test_clamp_is_symmetric_and_leaves_interior_values_alone():
    assert cmd_gate.clamp(0.5, 1.31) == 0.5
    assert cmd_gate.clamp(-0.5, 1.31) == -0.5
    assert cmd_gate.clamp(2.0, 1.31) == 1.31
    assert cmd_gate.clamp(-2.0, 1.31) == -1.31


def test_motor_is_read_out_of_the_status_json():
    assert cmd_gate.motor_from_status(
        '{"estop_healthy": true, "motor": true, "ts": 1.0}') is True
    assert cmd_gate.motor_from_status(
        '{"estop_healthy": true, "motor": false, "ts": 1.0}') is False


def test_unparseable_status_is_read_as_inhibited():
    assert cmd_gate.motor_from_status("{garbage") is False
