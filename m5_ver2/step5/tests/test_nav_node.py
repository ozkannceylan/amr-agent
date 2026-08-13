"""nav_core.py's state machine. Pure; the ROS shell is nav_node.py."""
import json
import math

import nav_core
from status_contract import MODE_AUTO, MODE_TELEOP

AT_S1 = (-3.0, -5.5, 0.0)          # pose on the HOME node, any heading


def _core_en_route():
    core = nav_core.NavCore()
    core.on_mode(MODE_AUTO)
    core.on_goal("S7", AT_S1[:2])
    return core


def test_fresh_core_is_idle_and_still():
    core = nav_core.NavCore()
    assert core.state == "IDLE"
    assert core.step(AT_S1, math.inf, True, 1500) == (0.0, 0.0)


def test_goal_in_auto_mode_plans_and_drives():
    core = _core_en_route()
    assert core.state == "EN-ROUTE"
    assert core.route[-1] == (8.0, 6.5)
    linear, _ = core.step(AT_S1, math.inf, True, 1500)
    assert linear < 0.0            # forks-first forward is negative


def test_goal_in_teleop_mode_is_refused():
    core = nav_core.NavCore()
    core.on_mode(MODE_TELEOP)
    core.on_goal("S7", AT_S1[:2])
    assert core.state == "IDLE"
    assert core.route is None


def test_unknown_station_is_refused_without_motion():
    core = nav_core.NavCore()
    core.on_mode(MODE_AUTO)
    core.on_goal("S99", AT_S1[:2])
    assert core.state == "IDLE"
    assert core.step(AT_S1, math.inf, True, 1500) == (0.0, 0.0)


def test_guard_hold_stops_and_recovers():
    core = _core_en_route()
    assert core.step(AT_S1, 1.2, True, 1500) == (0.0, 0.0)
    assert core.state == "HOLD"
    linear, _ = core.step(AT_S1, math.inf, True, 1500)
    assert linear < 0.0
    assert core.state == "EN-ROUTE"


def test_motor_false_is_safety_stop_and_resumes():
    core = _core_en_route()
    assert core.step(AT_S1, math.inf, False, 1500) == (0.0, 0.0)
    assert core.state == "SAFETY-STOP"
    linear, _ = core.step(AT_S1, math.inf, True, 1500)
    assert linear < 0.0
    assert core.state == "EN-ROUTE"


def test_v_limit_caps_the_command():
    # Pose heading east along the dock aisle (yaw pi -> travel 0), so
    # the follower would cruise at 0.7 - the cap is what holds it at
    # the PLC's 0.3, not the corner band.
    core = _core_en_route()
    heading_east = (-3.0, -5.5, math.pi)
    linear_full, _ = core.step(heading_east, math.inf, True, 1500)
    assert abs(linear_full) > 0.3          # premise: not corner-limited
    linear, _ = core.step(heading_east, math.inf, True, 300)
    assert abs(linear) <= 0.3 + 1e-9


def test_arrival_latches_until_a_new_goal():
    core = _core_en_route()
    at_goal = (8.0, 6.5, 0.0)
    assert core.step(at_goal, math.inf, True, 1500) == (0.0, 0.0)
    assert core.state == "ARRIVED"
    assert core.step(at_goal, math.inf, True, 1500) == (0.0, 0.0)


def test_mode_teleop_cancels_the_goal():
    core = _core_en_route()
    core.on_mode(MODE_TELEOP)
    assert core.state == "IDLE"
    assert core.route is None
    assert core.step(AT_S1, math.inf, True, 1500) == (0.0, 0.0)


def test_empty_goal_cancels():
    core = _core_en_route()
    core.on_goal("", AT_S1[:2])
    assert core.state == "IDLE"


def test_state_json_carries_the_display_fields():
    core = _core_en_route()
    report = json.loads(core.state_json(AT_S1, 4.2))
    assert report["state"] == "EN-ROUTE"
    assert report["goal"] == "S7"
    assert report["route"][-1] == [8.0, 6.5]
    assert report["pose"] == [-3.0, -5.5, 0.0]
    assert report["guard_min"] == 4.2
