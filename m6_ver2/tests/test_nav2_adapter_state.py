"""nav2_state.py - the contract the fleet layer is not being told about.

EVERY STRING IN THIS FILE IS PINNED AGAINST ITS PRODUCER AND NOT TYPED
TWICE. The words on `/[vid]/auto/state` are read by vda_agent.cb_nav and
by the HMI, neither of which is being modified, so the adapter has to
reproduce m6/ipc/nav_core.py's grammar byte for byte. Where the literal
lives in a method (`on_route`, `_cancel`) the pin DRIVES a real NavCore
into the refusal and reads its `note`; where it lives in the rclpy shell
(`nav_node.py`, which cannot be imported without ROS) the pin reads the
shell's source text. A pin that re-typed the string would only prove
that this file agrees with itself.
"""
import json
import math
import os

import pytest

import follower
import nav_core
from status_contract import MODE_AUTO

import nav2_state


NAV_NODE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.pardir, os.pardir, "m6", "ipc", "nav_node.py")


def _nav_core_note(setup):
    """The note a real NavCore ends up with after `setup` runs on it."""
    core = nav_core.NavCore()
    setup(core)
    return core.note


def _shell_source():
    with open(os.path.normpath(NAV_NODE), "r", encoding="utf-8") as handle:
        return handle.read()


def _accepted():
    state = nav2_state.NavState()
    state.on_mode(MODE_AUTO)
    state.set_pose_ok(True)
    assert state.on_route([(0.0, 10.0), (7.0, 10.0)], 0.25, "order-1")
    return state


# ----------------------------------------------------------------------
# the vocabulary
# ----------------------------------------------------------------------

def test_the_state_words_are_nav_cores_own():
    assert nav2_state.IDLE == nav_core.IDLE
    assert nav2_state.EN_ROUTE == nav_core.EN_ROUTE
    assert nav2_state.HOLD == nav_core.HOLD
    assert nav2_state.SAFETY_STOP == nav_core.SAFETY_STOP
    assert nav2_state.ARRIVED == nav_core.ARRIVED
    assert nav2_state.BLOCKED == nav_core.BLOCKED
    assert nav2_state.AVOID == nav_core.AVOID
    assert nav2_state.NUDGE == nav_core.NUDGE


def test_avoid_and_nudge_are_reserved_and_never_emitted():
    # Decision 3: nav2's costmap and BT recoveries replace the
    # escalation. The words stay in the contract document; the adapter
    # has no path that assigns them.
    assert nav2_state.AVOID in nav2_state.STATES
    assert nav2_state.NUDGE in nav2_state.STATES
    assert nav2_state.AVOID not in nav2_state.EMITTED
    assert nav2_state.NUDGE not in nav2_state.EMITTED


# ----------------------------------------------------------------------
# the refusal grammar, byte for byte
# ----------------------------------------------------------------------

def test_route_refused_malformed_points():
    def setup(core):
        core.on_mode(MODE_AUTO)
        core.on_route([("a", "b"), (1.0, 1.0)], None, "L")
    assert nav2_state.ROUTE_REFUSED_MALFORMED == _nav_core_note(setup)


def test_route_refused_fewer_than_two_points():
    def setup(core):
        core.on_mode(MODE_AUTO)
        core.on_route([(0.0, 0.0)], None, "L")
    assert nav2_state.ROUTE_REFUSED_SHORT == _nav_core_note(setup)


def test_route_refused_unusable_arrive_m():
    def setup(core):
        core.on_mode(MODE_AUTO)
        core.on_route([(0.0, 0.0), (1.0, 1.0)], 0.0, "L")
    assert nav2_state.ROUTE_REFUSED_ARRIVE_M == _nav_core_note(setup)


def test_route_refused_not_in_auto_mode():
    def setup(core):
        core.on_mode("teleop")
        core.on_route([(0.0, 0.0), (1.0, 1.0)], None, "L")
    assert nav2_state.ROUTE_REFUSED_MODE == _nav_core_note(setup)


def test_goal_refused_not_in_auto_mode():
    def setup(core):
        core.on_mode("teleop")
        core.on_goal("S5", (0.0, 0.0))
    assert nav2_state.GOAL_REFUSED_MODE == _nav_core_note(setup)


def test_goal_refused_unknown_station_carries_the_id():
    def setup(core):
        core.on_mode(MODE_AUTO)
        core.on_goal("S99", (0.0, 10.0))
    assert nav2_state.goal_refused_unknown("S99") == _nav_core_note(setup)


def test_cancelled():
    def setup(core):
        core.on_mode(MODE_AUTO)
        core.on_route([(0.0, 10.0), (7.0, 10.0)], None, "L")
        core.on_goal("", (0.0, 10.0))
    assert nav2_state.NOTE_CANCELLED == _nav_core_note(setup)


def test_mode_left_auto():
    def setup(core):
        core.on_mode(MODE_AUTO)
        core.on_route([(0.0, 10.0), (7.0, 10.0)], None, "L")
        core.on_mode("teleop")
    assert nav2_state.NOTE_MODE_LEFT_AUTO == _nav_core_note(setup)


def test_the_no_pose_refusals_are_the_shells_own_literals():
    # nav_node.py is the rclpy shell being retired; it cannot be
    # imported on a python without rclpy, so the pin is on its bytes.
    source = _shell_source()
    assert '"{}"'.format(nav2_state.ROUTE_REFUSED_NO_POSE) in source
    assert '"{}"'.format(nav2_state.GOAL_REFUSED_NO_POSE) in source
    assert '"{}"'.format(nav2_state.ROUTE_REFUSED_UNREADABLE) in source


# ----------------------------------------------------------------------
# acceptance
# ----------------------------------------------------------------------

def test_en_route_is_assigned_synchronously_on_acceptance():
    # vda_agent measures NAV_SETTLE_S (0.3 s) from the moment it sent
    # the route: a state tick that still said IDLE inside that window
    # would be read as "nav is not driving this order" and the agent
    # would drop `executing` on a truck that is about to move.
    state = nav2_state.NavState()
    state.on_mode(MODE_AUTO)
    state.set_pose_ok(True)
    assert state.on_route([(0.0, 10.0), (7.0, 10.0)], 0.25, "order-1")
    assert state.state == nav2_state.EN_ROUTE
    assert state.goal == "order-1"
    assert state.note == ""


def test_nothing_is_assigned_until_everything_has_passed():
    # nav_core.on_route's rule, and the reason it has one: a refusal
    # that landed after `state` was already EN-ROUTE wrote "route
    # refused" over a vehicle that was driving.
    state = _accepted()
    assert not state.on_route([(0.0, 0.0)], 0.25, "order-2")
    assert state.state == nav2_state.EN_ROUTE
    assert state.goal == "order-1"
    assert state.route == [(0.0, 10.0), (7.0, 10.0)]
    assert state.note == nav2_state.ROUTE_REFUSED_SHORT


def test_a_non_finite_coordinate_is_refused_and_not_repaired():
    state = nav2_state.NavState()
    state.on_mode(MODE_AUTO)
    state.set_pose_ok(True)
    assert not state.on_route(
        [(0.0, 0.0), (float("nan"), 1.0)], 0.25, "L")
    assert state.note == nav2_state.ROUTE_REFUSED_MALFORMED
    assert state.state == nav2_state.IDLE


def test_an_absent_arrive_m_is_the_one_way_to_ask_for_the_default():
    state = nav2_state.NavState()
    state.on_mode(MODE_AUTO)
    state.set_pose_ok(True)
    assert state.on_route([(0.0, 10.0), (7.0, 10.0)], None, "L")
    assert state.arrive_m == follower.ARRIVE_M


def test_a_station_go_plans_through_route_py_and_takes_its_radius():
    state = nav2_state.NavState()
    state.on_mode(MODE_AUTO)
    state.set_pose_ok(True)
    assert state.on_goal("S5", (-17.0, 10.0))
    assert state.state == nav2_state.EN_ROUTE
    assert state.goal == "S5"
    assert state.route[-1] == (7.0, 4.25)
    assert state.arrive_m == 0.25


# ----------------------------------------------------------------------
# the boot posture and the staleness rule
# ----------------------------------------------------------------------

def test_the_boot_posture_is_idle_with_the_localiser_note():
    state = nav2_state.NavState()
    assert state.state == nav2_state.IDLE
    assert state.note == nav2_state.NOTE_LOCALISER_NOT_READY


def test_routes_are_refused_until_there_is_a_pose():
    state = nav2_state.NavState()
    state.on_mode(MODE_AUTO)
    assert not state.on_route([(0.0, 10.0), (7.0, 10.0)], 0.25, "L")
    assert state.note == nav2_state.ROUTE_REFUSED_NO_POSE
    assert not state.on_goal("S5", (-17.0, 10.0))
    assert state.note == nav2_state.GOAL_REFUSED_NO_POSE


def test_a_stale_pose_holds_and_says_so():
    state = _accepted()
    state.set_pose_ok(False)
    assert state.state == nav2_state.HOLD
    assert state.note == nav2_state.NOTE_POSE_STALE
    # THE ROUTE IS HELD. "No picture" is not a cancel.
    assert state.route is not None and state.goal == "order-1"
    state.set_pose_ok(True)
    assert state.state == nav2_state.EN_ROUTE


# ----------------------------------------------------------------------
# ARRIVED, and the latch
# ----------------------------------------------------------------------

def test_arrived_latches_on_the_first_tick_inside_arrive_m():
    state = _accepted()
    assert not state.check_arrival((3.0, 10.0))
    assert state.state == nav2_state.EN_ROUTE
    assert state.check_arrival((6.8, 10.0))
    assert state.state == nav2_state.ARRIVED
    assert state.reversing is False


def test_the_latch_answers_true_once_and_then_holds_the_state():
    state = _accepted()
    assert state.check_arrival((6.8, 10.0))
    assert not state.check_arrival((6.8, 10.0))
    assert state.state == nav2_state.ARRIVED
    # AND IT SURVIVES DRIVING BACK OUT. Latched means latched: the
    # vehicle rolling past its own tolerance does not un-arrive it.
    assert not state.check_arrival((0.0, 10.0))
    assert state.state == nav2_state.ARRIVED


def test_arrived_keeps_the_goal_because_the_fleet_reads_it():
    # vda_agent._settle_arrival needs nav ARRIVED *for our label*; an
    # arrival that dropped the goal would never settle an order.
    state = _accepted()
    state.check_arrival((6.8, 10.0))
    assert state.goal == "order-1"
    assert state.route is not None


def test_the_latch_is_per_label():
    state = _accepted()
    state.check_arrival((6.8, 10.0))
    assert state.on_route([(7.0, 10.0), (7.0, 4.25)], 0.25, "order-2")
    assert state.state == nav2_state.EN_ROUTE
    assert not state.check_arrival((7.0, 9.0))
    assert state.check_arrival((7.0, 4.35))
    assert state.state == nav2_state.ARRIVED


def test_the_radius_is_followers_own_measurement():
    state = _accepted()
    assert follower.arrived((6.8, 10.0), (7.0, 10.0), state.arrive_m)
    assert not follower.arrived((6.7, 10.0), (7.0, 10.0), state.arrive_m)
    assert not state.check_arrival((6.7, 10.0))


# ----------------------------------------------------------------------
# BLOCKED, SAFETY-STOP and cancel
# ----------------------------------------------------------------------

def test_blocked_keeps_the_goal_or_the_fleet_never_hears_about_it():
    # vda_agent's blocked_now is `goal == orderId`; a BLOCKED that
    # cleared the goal would be a pathBlocked nobody reports.
    state = _accepted()
    state.block("blocked: planner refused (error_code 205)")
    assert state.state == nav2_state.BLOCKED
    assert state.goal == "order-1"
    assert state.note == "blocked: planner refused (error_code 205)"


def test_safety_stop_holds_the_route_and_resumes_without_a_ritual():
    state = _accepted()
    state.safety_stop()
    assert state.state == nav2_state.SAFETY_STOP
    assert state.route == [(0.0, 10.0), (7.0, 10.0)]
    assert state.goal == "order-1"
    assert state.resume()
    assert state.state == nav2_state.EN_ROUTE
    assert state.route == [(0.0, 10.0), (7.0, 10.0)]


def test_resume_from_anything_else_is_not_a_transition():
    state = _accepted()
    assert not state.resume()
    assert state.state == nav2_state.EN_ROUTE


def test_cancel_is_idle_with_no_goal_inside_one_tick():
    # The vda 5 s cancel pump confirms on IDLE + no goal.
    state = _accepted()
    state.cancel()
    assert state.state == nav2_state.IDLE
    assert state.goal is None
    assert state.route is None
    assert state.note == nav2_state.NOTE_CANCELLED
    assert state.arrive_m == follower.ARRIVE_M


def test_leaving_auto_cancels_by_name():
    state = _accepted()
    state.on_mode("teleop")
    assert state.state == nav2_state.IDLE
    assert state.note == nav2_state.NOTE_MODE_LEFT_AUTO
    assert state.goal is None


def test_leaving_auto_while_idle_says_nothing():
    state = nav2_state.NavState()
    state.on_mode(MODE_AUTO)
    state.set_pose_ok(True)
    state.on_mode("teleop")
    assert state.note != nav2_state.NOTE_MODE_LEFT_AUTO


# ----------------------------------------------------------------------
# state_json
# ----------------------------------------------------------------------

def test_the_schema_is_nav_cores_schema():
    core = nav_core.NavCore()
    core.on_mode(MODE_AUTO)
    core.on_route([(0.0, 10.0), (7.0, 10.0)], 0.25, "order-1")
    theirs = json.loads(core.state_json((1.0, 2.0, 0.5), 3.0))
    mine = json.loads(_accepted().state_json((1.0, 2.0, 0.5), 3.0))
    assert sorted(mine) == sorted(theirs)
    for key in theirs:
        assert type(mine[key]) is type(theirs[key]), key
    assert mine == theirs


def test_an_empty_route_is_a_list_and_not_null():
    payload = json.loads(
        nav2_state.NavState().state_json((0.0, 0.0, 0.0), math.inf))
    assert payload["route"] == []
    assert payload["guard_min"] is None


def test_a_non_finite_pose_becomes_null_and_never_a_bare_nan():
    # nav_core.on_route's own docstring names the failure: json.dumps
    # emits a bare NaN that no strict JSON parser will read. The route
    # can no longer carry one (it is refused at the door) but a TF
    # composition can hand this file one, so the DUMP refuses it too.
    text = _accepted().state_json(
        (float("nan"), 2.0, float("inf")), float("nan"))
    assert "NaN" not in text and "Infinity" not in text
    payload = json.loads(text)
    assert payload["pose"] == [None, 2.0, None]
    assert payload["guard_min"] is None


def test_an_infinite_guard_min_is_null_exactly_as_nav_core_writes_it():
    core = nav_core.NavCore()
    theirs = json.loads(core.state_json((0.0, 0.0, 0.0), float("inf")))
    mine = json.loads(
        nav2_state.NavState().state_json((0.0, 0.0, 0.0), float("inf")))
    assert theirs["guard_min"] is None and mine["guard_min"] is None


def test_the_stream_keeps_flowing_on_a_stale_pose():
    # THE ONE DELIBERATE CONTRACT DEVIATION, NAMED (Decision 4).
    # nav_node stops publishing /auto/state entirely on a stale pose;
    # this keeps the 10 Hz stream with the note in it.
    state = _accepted()
    state.set_pose_ok(False)
    payload = json.loads(state.state_json((1.0, 2.0, 0.0), 3.0))
    assert payload["state"] == nav2_state.HOLD
    assert payload["note"] == nav2_state.NOTE_POSE_STALE


def test_an_unknown_state_word_is_refused_by_name():
    state = nav2_state.NavState()
    state.state = "CRUISING"
    with pytest.raises(nav2_state.Nav2StateError) as caught:
        state.state_json((0.0, 0.0, 0.0), 1.0)
    assert "CRUISING" in str(caught.value)


# ----------------------------------------------------------------------
# the selftest
# ----------------------------------------------------------------------

def test_the_selftest_is_green():
    assert nav2_state._selftest() == 0
