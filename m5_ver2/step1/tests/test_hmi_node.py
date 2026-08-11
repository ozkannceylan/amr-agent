"""hmi_node.py's mapping and labels. No window is opened."""
import pytest

import hmi_node

R = 100.0
SPEED_MAX = 1.50
STEER_MAX = 1.31


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
