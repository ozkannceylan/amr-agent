"""cmd_mux.py's selection rule. No ROS graph is started."""
import cmd_mux
from status_contract import MODE_AUTO, MODE_TELEOP

HMI = (0.5, 0.2)
AUTO = (-0.7, -0.1)


def test_teleop_mode_passes_the_joystick():
    assert cmd_mux.select(MODE_TELEOP, HMI, AUTO, 100.0, 100.0) == HMI


def test_auto_mode_passes_the_autopilot():
    assert cmd_mux.select(MODE_AUTO, HMI, AUTO, 100.0, 100.1) == AUTO


def test_no_mode_yet_is_teleop():
    # A mux that has not been told a mode obeys the human, not the robot.
    assert cmd_mux.select(None, HMI, AUTO, 100.0, 100.0) == HMI


def test_unknown_mode_word_is_teleop():
    assert cmd_mux.select("banana", HMI, AUTO, 100.0, 100.0) == HMI


def test_auto_with_a_stale_autopilot_is_zeros_not_joystick():
    # nav_node died mid-drive: the truck must stop, not obey a joystick
    # nobody is holding. STATUS_STALE_S after the last /auto/cmd_vel.
    assert cmd_mux.select(MODE_AUTO, HMI, AUTO, 100.0, 100.5) == (0.0, 0.0)


def test_auto_that_never_spoke_is_zeros():
    assert cmd_mux.select(MODE_AUTO, HMI, AUTO, None, 100.0) == (0.0, 0.0)
