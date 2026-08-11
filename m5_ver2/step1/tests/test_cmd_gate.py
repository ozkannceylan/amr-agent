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


# ---- the gate's OWN timeout on /plc/status (design spec 7.4) ----
#
# Every base below is 0.0 so the float subtraction inside is_stale is
# EXACT, which is the convention Task 3 settled on for STALE_S: from a
# base of 10.0, 10.25 - 10.0 is not 0.25 and the assertions would pin an
# answer for a reason that has nothing to do with this node.


def test_fresh_status_with_motor_true_is_live():
    assert cmd_gate.gate_is_live(True, 0.0, 0.10) is True


def test_stale_status_inhibits_even_though_motor_was_true():
    # The failure this exists for: plc_link's PROCESS dies, /plc/status
    # simply stops, and the last thing it said was "enabled".
    assert cmd_gate.gate_is_live(True, 0.0, 0.30) is False


def test_status_that_has_never_arrived_inhibits():
    assert cmd_gate.gate_is_live(True, None, 5.0) is False


def test_motor_false_inhibits_however_fresh_the_status_is():
    assert cmd_gate.gate_is_live(False, 0.0, 0.0) is False


def test_gate_timeout_is_the_configured_constant():
    # Pins STATUS_STALE_S itself. Every other test here would stay green
    # if the constant were edited to a wrong value.
    assert cmd_gate.gate_is_live(True, 0.0, 0.24) is True
    assert cmd_gate.gate_is_live(True, 0.0, 0.25) is False


def test_gate_timeout_is_off_the_tick_boundary():
    # Task 3's trap, encoded so an edit cannot walk back into it: a
    # timeout at an exact multiple of the tick period sits ON a boundary
    # and microseconds of jitter decide whether the Nth or the N+1th tick
    # fires. 0.25 is 2.5 ticks, clear of both. The tolerance is what makes
    # this catch 0.30, whose float product is 2.9999999999999996 and would
    # slip past an equality test against round().
    ticks = cmd_gate.STATUS_STALE_S * cmd_gate.ZERO_HZ
    assert abs(ticks - round(ticks)) > 0.1


def test_a_live_gate_that_goes_stale_returns_to_zero():
    # The whole point, end to end: the SAME motor_ok, with only the clock
    # advanced, stops passing the command.
    live = cmd_gate.gate_is_live(True, 0.0, 0.10)
    assert cmd_gate.gated_command(
        1.0, 0.5, live, SPEED_MAX, STEER_MAX) == (1.0, 0.5)
    stale = cmd_gate.gate_is_live(True, 0.0, 0.30)
    assert cmd_gate.gated_command(
        1.0, 0.5, stale, SPEED_MAX, STEER_MAX) == (0.0, 0.0)
