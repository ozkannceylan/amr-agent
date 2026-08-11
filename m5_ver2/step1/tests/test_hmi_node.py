"""hmi_node.py's mapping and labels. No window is opened."""
import pytest

import cmd_gate
import hmi_node

R = 100.0
SPEED_MAX = 1.50
STEER_MAX = 1.31

#: What a live link is carrying when the truck is released and enabled.
#: Displaying THIS while nothing is arriving is the failure the staleness
#: tests below exist for.
HEALTHY = {"estop_healthy": True, "motor": True, "ts": 0.0}


def test_centre_is_a_full_stop():
    assert hmi_node.knob_to_twist(
        0.0, 0.0, R, SPEED_MAX, STEER_MAX) == (0.0, 0.0)


def test_dragging_up_drives_forward():
    # Canvas y grows DOWNWARD, so "up" is a negative dy.
    linear, _ = hmi_node.knob_to_twist(0.0, -R, R, SPEED_MAX, STEER_MAX)
    assert linear == pytest.approx(SPEED_MAX)


def test_dragging_down_drives_in_reverse():
    linear, _ = hmi_node.knob_to_twist(0.0, R, R, SPEED_MAX, STEER_MAX)
    assert linear == pytest.approx(-SPEED_MAX)


def test_dragging_right_steers_right_which_is_negative_z():
    # REP-103: positive z is counter-clockwise, so a right turn is negative.
    _, angular = hmi_node.knob_to_twist(R, 0.0, R, SPEED_MAX, STEER_MAX)
    assert angular == pytest.approx(-STEER_MAX)


def test_dragging_left_steers_left_which_is_positive_z():
    _, angular = hmi_node.knob_to_twist(-R, 0.0, R, SPEED_MAX, STEER_MAX)
    assert angular == pytest.approx(STEER_MAX)


def test_a_drag_beyond_the_ring_saturates_rather_than_exceeding():
    linear, angular = hmi_node.knob_to_twist(
        5 * R, -5 * R, R, SPEED_MAX, STEER_MAX)
    assert linear == pytest.approx(SPEED_MAX)
    assert angular == pytest.approx(-STEER_MAX)


def test_half_deflection_is_half_command():
    linear, _ = hmi_node.knob_to_twist(0.0, -R / 2, R, SPEED_MAX, STEER_MAX)
    assert linear == pytest.approx(SPEED_MAX / 2)


def test_lamp_is_red_and_says_active_when_the_chain_is_broken():
    colour, text = hmi_node.lamp_state(False)
    assert text == "E-Stop Active"
    assert colour == hmi_node.LAMP_RED


def test_lamp_is_neutral_and_says_inactive_when_the_chain_is_healthy():
    colour, text = hmi_node.lamp_state(True)
    assert text == "E-Stop Inactive"
    assert colour == hmi_node.LAMP_NEUTRAL


def test_the_enable_line_is_separate_from_the_lamp():
    # The latch is exactly the state where these two disagree, and showing
    # that disagreement is a Step 1 goal.
    assert hmi_node.enable_text(True) == "Drive enable: ON"
    assert hmi_node.enable_text(False) == "Drive enable: OFF"


# ---- the display's own timeout on /plc/status ----
#
# Every base below is 0.0 so the float subtraction inside is_stale is
# EXACT, which is the convention Tasks 3 and 4 settled on: from a base of
# 10.0, 10.25 - 10.0 is not 0.25 and the assertions would pin an answer
# for a reason that has nothing to do with this node.


def test_a_fresh_status_is_shown_as_it_arrived():
    assert hmi_node.display_state(HEALTHY, 0.0, 0.10) == (
        hmi_node.LAMP_NEUTRAL, "E-Stop Inactive", "Drive enable: ON")


def test_the_latch_display_survives_the_staleness_rule():
    # The whole point of the window, guarded against the new rule: while
    # the status IS arriving, released-but-not-acknowledged must still
    # show a NEUTRAL lamp over an OFF enable line. A rule that forced the
    # lamp red here would hide the latch instead of showing it.
    colour, lamp, enable = hmi_node.display_state(
        {"estop_healthy": True, "motor": False, "ts": 0.0}, 0.0, 0.10)
    assert (colour, lamp) == (hmi_node.LAMP_NEUTRAL, "E-Stop Inactive")
    assert enable == "Drive enable: OFF"


def test_a_status_that_stopped_arriving_shows_the_safe_display():
    # The failure this exists for: plc_link's PROCESS dies, /plc/status
    # simply stops, and the last thing it said was healthy and enabled.
    # cmd_gate stops the truck; without this the SCREEN still says ON.
    assert hmi_node.display_state(HEALTHY, 0.0, 0.30) == (
        hmi_node.LAMP_RED, "E-Stop Active", "Drive enable: OFF")


def test_a_status_that_never_arrived_shows_the_safe_display():
    # is_stale reads last_rx of None as stale, so start-up needs no
    # branch of its own: a window that has heard nothing claims nothing.
    assert hmi_node.display_state(HEALTHY, None, 5.0) == (
        hmi_node.LAMP_RED, "E-Stop Active", "Drive enable: OFF")


def test_the_display_timeout_is_the_configured_constant():
    # Pins STATUS_STALE_S itself. Every other test here passes the window
    # implicitly and would stay green if the constant were edited.
    assert hmi_node.display_state(HEALTHY, 0.0, 0.24)[0] == \
        hmi_node.LAMP_NEUTRAL
    assert hmi_node.display_state(HEALTHY, 0.0, 0.25)[0] == hmi_node.LAMP_RED


def test_the_display_and_the_gate_time_out_together():
    # Same number AND same name as cmd_gate's. If they drifted apart the
    # screen and the vehicle would stop trusting a silent /plc/status at
    # different instants, and whichever went first would be lying.
    assert hmi_node.STATUS_STALE_S == cmd_gate.STATUS_STALE_S


def test_the_display_timeout_is_off_the_pump_tick_boundary():
    # Design spec 7.2. Both operands of the >= inside is_stale are read
    # during a pump, so the elapsed value tested is quantised to SPIN_MS;
    # a timeout at an exact multiple of it sits ON a boundary and
    # microseconds of jitter decide which pump trips the display. This is
    # what rules out the 5 ms pump period - 0.25 s is exactly 50 of them.
    pumps = hmi_node.STATUS_STALE_S * 1000.0 / hmi_node.SPIN_MS
    assert abs(pumps - round(pumps)) > 0.1
