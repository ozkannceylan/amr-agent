"""nav_core.py's state machine. Pure; the ROS shell is nav_node.py."""
import json
import math

import follower
import nav_core
from stations import STATIONS
from status_contract import MODE_AUTO, MODE_TELEOP

# On S1's spur foot, forks EAST (model yaw pi -> travel yaw 0) along
# the pick aisle - the way the S7 route leaves. The heading is
# load-bearing since the reverse phase exists: parked facing the other
# way the truck would back out first, which is a different test.
_S1, _S7, _S10 = STATIONS["S1"], STATIONS["S7"], STATIONS["S10"]
AT_S1 = (_S1["x"], 0.0, math.pi)
S7_XY = (_S7["x"], _S7["y"])


def _core_en_route():
    core = nav_core.NavCore()
    core.on_mode(MODE_AUTO)
    core.on_goal("S7", AT_S1[:2])
    return core


def test_fresh_core_is_idle_and_still():
    core = nav_core.NavCore()
    assert core.state == "IDLE"
    assert core.step(AT_S1, math.inf, math.inf, True, 1500) == (0.0, 0.0)


def test_goal_in_auto_mode_plans_and_drives():
    core = _core_en_route()
    assert core.state == "EN-ROUTE"
    assert core.route[-1] == S7_XY
    linear, _ = core.step(AT_S1, math.inf, math.inf, True, 1500)
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
    assert core.step(AT_S1, math.inf, math.inf, True, 1500) == (0.0, 0.0)


def test_guard_hold_stops_and_recovers():
    core = _core_en_route()
    assert core.step(AT_S1, 1.2, math.inf, True, 1500) == (0.0, 0.0)
    assert core.state == "HOLD"
    linear, _ = core.step(AT_S1, math.inf, math.inf, True, 1500)
    assert linear < 0.0
    assert core.state == "EN-ROUTE"


def test_motor_false_is_safety_stop_and_resumes():
    core = _core_en_route()
    assert core.step(AT_S1, math.inf, math.inf, False, 1500) == (0.0, 0.0)
    assert core.state == "SAFETY-STOP"
    linear, _ = core.step(AT_S1, math.inf, math.inf, True, 1500)
    assert linear < 0.0
    assert core.state == "EN-ROUTE"


def test_v_limit_caps_the_command():
    # Pose heading east along the dock aisle (yaw pi -> travel 0), so
    # the follower would cruise at 0.7 - the cap is what holds it at
    # the PLC's 0.3, not the corner band.
    core = _core_en_route()
    heading_east = AT_S1
    linear_full, _ = core.step(heading_east, math.inf, math.inf, True, 1500)
    assert abs(linear_full) > 0.3          # premise: not corner-limited
    linear, _ = core.step(heading_east, math.inf, math.inf, True, 300)
    assert abs(linear) <= 0.3 + 1e-9


def test_arrival_latches_until_a_new_goal():
    core = _core_en_route()
    at_goal = (S7_XY[0], S7_XY[1], 0.0)
    assert core.step(at_goal, math.inf, math.inf, True, 1500) == (0.0, 0.0)
    assert core.state == "ARRIVED"
    assert core.step(at_goal, math.inf, math.inf, True, 1500) == (0.0, 0.0)


def test_mode_teleop_cancels_the_goal():
    core = _core_en_route()
    core.on_mode(MODE_TELEOP)
    assert core.state == "IDLE"
    assert core.route is None
    assert core.step(AT_S1, math.inf, math.inf, True, 1500) == (0.0, 0.0)


def test_empty_goal_cancels():
    core = _core_en_route()
    core.on_goal("", AT_S1[:2])
    assert core.state == "IDLE"


def test_state_json_carries_the_display_fields():
    core = _core_en_route()
    report = json.loads(core.state_json(AT_S1, 4.2))
    assert report["state"] == "EN-ROUTE"
    assert report["goal"] == "S7"
    assert report["route"][-1] == [S7_XY[0], S7_XY[1]]
    assert report["pose"] == list(AT_S1)
    assert report["guard_min"] == 4.2
    assert report["reversing"] is False


# ------------------- leaving a spur station backwards -------------------
# Measured 2026-08-13: arriving at S10 the forks point north AT the rack,
# and the route out runs south. Turning around there swung the truck
# 1.235 m closer to the rack and put the back scanner 0.938 m off it -
# inside the 1.0 m protective field. Backing straight out is the fix, and
# reversing is the GUARDED direction on this vehicle: the PLC's back
# scanner is primary on that side.
# stations.yaw is the APPROACH heading (forks into the bay). The model
# mesh has forks at yaw 0 pointing world -x, so model yaw is approach + pi.
AT_S10 = (_S10["x"], _S10["y"], _S10["yaw"] + math.pi)


def _core_at_s10():
    core = nav_core.NavCore()
    core.on_mode(MODE_AUTO)
    core.on_goal("S7", AT_S10[:2])
    return core


def test_departing_a_spur_backs_straight_out():
    core = _core_at_s10()
    linear, steer = core.step(AT_S10, math.inf, math.inf, True, 1500)
    assert linear > 0.0            # positive linear.x = counterweight first
    assert steer == 0.0            # straight back, no arc into the rack
    assert core.state == "EN-ROUTE"
    assert core.reversing
    assert json.loads(core.state_json(AT_S10, 4.2))["reversing"] is True


def test_the_back_out_keeps_reversing_down_the_spur():
    # Half way out the target has swung to about 125 deg - still astern,
    # and inside the hysteresis band it would hold anyway.
    core = _core_at_s10()
    core.step(AT_S10, math.inf, math.inf, True, 1500)
    linear, steer = core.step(
        (_S10["x"], (_S10["y"] + -10.0) / 2.0, AT_S10[2]),
        math.inf, math.inf, True, 1500)
    assert linear > 0.0
    assert steer == 0.0
    assert core.reversing


def test_past_the_corner_the_truck_drives_forward_again():
    # Backed onto the dock aisle, the target is about 60 deg off - under
    # the 75 deg exit angle, so the phase lets go and the forks lead.
    # On the south ring, travel east (model yaw pi). The reverse phase
    # exits under 75 deg; facing the next node ends it.
    core = _core_at_s10()
    core.step(AT_S10, math.inf, math.inf, True, 1500)
    linear, _ = core.step(
        (_S10["x"], -10.0, math.pi), math.inf, math.inf, True, 1500)
    assert linear < 0.0
    assert not core.reversing


def test_the_reverse_guard_holds_the_back_out():
    # Something behind the counterweight stops the back-out exactly the
    # way the forward guard stops the drive - and the FORWARD guard being
    # clear is no argument.
    core = _core_at_s10()
    assert core.step(AT_S10, math.inf, 1.2, True, 1500) == (0.0, 0.0)
    assert core.state == "HOLD"


def test_a_short_spur_station_arrives_at_its_own_radius():
    # Every station declares 0.25 m. 0.20 m out is ARRIVED...
    core = _core_en_route()                    # goal S7
    near = (_S7["x"], _S7["y"] + 0.20, -math.pi / 2)
    assert core.step(near, math.inf, math.inf, True, 1500) == (0.0, 0.0)
    assert core.state == "ARRIVED"


def test_an_aligned_station_still_demands_the_tight_radius():
    # ...and 0.70 m out is NOT arrived at S10. Same distance, different
    # station, still outside 0.25 m.
    core = nav_core.NavCore()
    core.on_mode(MODE_AUTO)
    core.on_goal("S10", AT_S1[:2])
    near = (_S10["x"], _S10["y"] + 0.70, AT_S10[2])
    linear, _ = core.step(near, math.inf, math.inf, True, 1500)
    assert core.state == "EN-ROUTE"
    # 0.70 m is outside 0.25 m; the sign of linear is not the claim.


def test_a_new_goal_clears_the_reverse_phase():
    core = _core_at_s10()
    core.step(AT_S10, math.inf, math.inf, True, 1500)
    assert core.reversing
    core.on_goal("", AT_S10[:2])
    assert not core.reversing


# ------------------- a route that arrives already planned -------------------
# M6.2: the VDA agent hands nav a finished polyline, so on_route enters the
# same EN-ROUTE state on_goal reaches after planning. plan= is a lambda that
# plans nothing, which is the point: this door must never call the planner.


def test_on_route_installs_an_external_polyline():
    core = nav_core.NavCore(plan=lambda xy, sid: None)
    core.on_mode(MODE_AUTO)
    core.on_route([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]], 0.3, "order-1")
    assert core.state == nav_core.EN_ROUTE
    assert core.goal == "order-1"
    assert core.route == [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    assert core.arrive_m == 0.3


def test_on_route_refused_outside_auto():
    core = nav_core.NavCore(plan=lambda xy, sid: None)
    core.on_mode(MODE_TELEOP)
    core.on_route([[0.0, 0.0], [1.0, 0.0]], 0.3, "order-1")
    assert core.state == nav_core.IDLE and "auto" in core.note


def test_on_route_refuses_a_degenerate_polyline():
    core = nav_core.NavCore(plan=lambda xy, sid: None)
    core.on_mode(MODE_AUTO)
    core.on_route([[0.0, 0.0]], 0.3, "order-1")
    assert core.state == nav_core.IDLE and core.route is None


def test_empty_goal_still_cancels_an_external_route():
    core = nav_core.NavCore(plan=lambda xy, sid: None)
    core.on_mode(MODE_AUTO)
    core.on_route([[0.0, 0.0], [1.0, 0.0]], 0.3, "order-1")
    core.on_goal("", (0.0, 0.0))
    assert core.state == nav_core.IDLE and core.route is None


def test_on_route_refuses_a_non_finite_coordinate():
    # json.loads reads the bare literal NaN and float("nan") passes
    # float(), so unchecked this installed: step() answered (-0.7, nan),
    # cruise traction with a NaN steer, arrived() false forever, and a
    # state_json no strict parser will read. inf goes the same way.
    for bad in (float("nan"), float("inf"), float("-inf")):
        core = nav_core.NavCore(plan=lambda xy, sid: None)
        core.on_mode(MODE_AUTO)
        core.on_route([[0.0, 0.0], [10.0, bad]], 0.3, "order-1")
        assert core.state == nav_core.IDLE and core.route is None


def test_a_bad_arrive_m_refuses_the_route_instead_of_half_taking_it():
    # The radius used to be converted AFTER goal, route and state were
    # set, so "abc" raised with the truck EN-ROUTE and nav_node then
    # wrote "route refused" over a driving vehicle. Zero, negative and
    # NaN are worse: they install and arrived() is never true.
    for bad in ("abc", -1, 0, float("nan"), float("inf")):
        core = nav_core.NavCore(plan=lambda xy, sid: None)
        core.on_mode(MODE_AUTO)
        core.on_route([[0.0, 0.0], [1.0, 0.0]], bad, "order-1")
        assert core.state == nav_core.IDLE
        assert core.route is None and core.goal is None
        assert "arrive_m" in core.note


def test_an_absent_arrive_m_takes_the_follower_default():
    # Absent is the one way to ask for the default - nav_node sends
    # req.get("arrive_m"), so a request without the key arrives as None.
    core = nav_core.NavCore(plan=lambda xy, sid: None)
    core.on_mode(MODE_AUTO)
    core.on_route([[0.0, 0.0], [1.0, 0.0]], None, "order-1")
    assert core.state == nav_core.EN_ROUTE
    assert core.arrive_m == follower.ARRIVE_M
