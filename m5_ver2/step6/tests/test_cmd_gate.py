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


def test_nan_clamps_to_zero_and_not_to_the_limit():
    # Every comparison against NaN is False, so min() and max() both keep
    # their first operand and the naive clamp returns +limit: garbage in,
    # MAXIMUM SPEED out. Zero is the only defensible answer for a value
    # that is not a number.
    assert cmd_gate.clamp(float("nan"), 1.31) == 0.0
    assert cmd_gate.clamp(float("nan"), 1.50) == 0.0


def test_infinities_still_clamp_to_the_limit():
    # Pinned beside the NaN case so the NaN guard cannot be written in a
    # way that also swallows the infinities, which DO have a sign and a
    # correct clamped value.
    assert cmd_gate.clamp(float("inf"), 1.31) == 1.31
    assert cmd_gate.clamp(float("-inf"), 1.31) == -1.31


def test_a_nan_traction_command_does_not_become_full_speed():
    traction, _ = cmd_gate.gated_command(
        float("nan"), 0.0, True, SPEED_MAX, STEER_MAX)
    assert traction == 0.0


def test_a_nan_steer_command_does_not_become_the_mechanical_stop():
    _, steer = cmd_gate.gated_command(
        0.0, float("nan"), True, SPEED_MAX, STEER_MAX)
    assert steer == 0.0


def test_motor_is_read_out_of_the_status_json():
    assert cmd_gate.motor_from_status(
        '{"estop_healthy": true, "motor": true, "case": 3, "v_limit": 1500, "ts": 1.0}') is True
    assert cmd_gate.motor_from_status(
        '{"estop_healthy": true, "motor": false, "case": 3, "v_limit": 1500, "ts": 1.0}') is False


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
    # fires. 0.25 is 2.5 ticks, clear of both.
    #
    # WHY A TOLERANCE AND NOT `ticks != round(ticks)`. Not for floating
    # point reasons - 0.30 * 10.0 is EXACTLY 3.0 (0.3 as a double is
    # 1.11e-16 under 0.3, and ten times that lands inside half an ulp of
    # 3.0), so an equality test would catch 0.30 perfectly well. The
    # tolerance earns its place by rejecting values NEAR a boundary as
    # well as ON one: 0.201 and 0.299 sit a millisecond from a tick and
    # jitter across it exactly as 0.30 would, and both sail through an
    # equality test.
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


def test_the_effective_limit_is_the_smaller_of_the_two_permissions():
    # speed_max is the VEHICLE's, v_limit is the PLC's right now. With the
    # warning field clear the two are equal at 1500 mm/s; with it occupied
    # the PLC's 300 wins and the truck creeps instead of being stopped by
    # the speed monitor for exceeding a ceiling nothing was obeying.
    assert min(SPEED_MAX, 1500 / 1000.0) == SPEED_MAX
    assert min(SPEED_MAX, 300 / 1000.0) == 0.3


def test_a_command_above_the_creep_ceiling_is_clamped_not_refused():
    traction, _ = cmd_gate.gated_command(1.5, 0.0, True, 0.3, STEER_MAX)
    assert traction == 0.3


def test_the_creep_ceiling_still_allows_reverse():
    traction, _ = cmd_gate.gated_command(-1.5, 0.0, True, 0.3, STEER_MAX)
    assert traction == -0.3


def test_every_name_cmd_gate_uses_from_the_contract_is_imported():
    """Guards the wiring, which the pure-function tests cannot see.

    Step 5's first live start died with NameError: status_contract is not
    defined - cmd_gate imports names FROM the contract rather than the
    module, and a patch written against the module form compiled fine and
    passed every test, because nothing here constructs the node. Importing
    the module is the cheapest check that its module-level names resolve.
    """
    import cmd_gate as m
    for name in ("V_LIMIT_CREEP_MM_S", "speed_limit_mm_s", "parse_status",
                 "is_stale", "STATUS_TOPIC", "STATUS_STALE_S"):
        assert hasattr(m, name), name


def test_command_never_received_is_zeros():
    assert cmd_gate.command_or_zeros((0.8, 0.2), None, 100.0) == (0.0, 0.0)


def test_fresh_command_passes():
    assert cmd_gate.command_or_zeros((0.8, 0.2), 99.9, 100.0) == (0.8, 0.2)


def test_stale_command_is_zeros_while_enabled():
    # THE step4 14.8 m CLASS: mux dead, Motor True, last setpoint held.
    # At CMD_STALE_S the gate stops repeating the corpse's command.
    stale_at = 100.0 + cmd_gate.CMD_STALE_S
    assert cmd_gate.command_or_zeros((0.8, 0.2), 100.0, stale_at) == (0.0, 0.0)
