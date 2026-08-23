"""apply_command - the panel's three controls, as data.

WHAT THESE PROVE AND WHAT THEY DO NOT
  scripted_writer runs the REAL m6.control_loop; that loop already has
  its own evidence in test_m6_virtual_loop.py and nothing here repeats
  it. What is new in the driver is the translation from a UDP datagram to
  a `state` mutation, and that is one pure function - so it is the only
  thing tested here, exhaustively, including the datagrams that must do
  nothing at all.

WHY "DOES NOTHING" IS THE INTERESTING HALF
  This socket sits on the writer of a safety PLC. A malformed datagram
  that clears E-Stop, or an `enc_mode` the owner's panel cannot produce,
  would be a plant command nobody typed. Every rejection below is a
  refusal to invent an operator action.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "tools")))

import scripted_writer as sw  # noqa: E402


def _rig():
    """The two dicts m6.main() builds, at their start-up values."""
    state = {"estop": True, "ack_until": 0.0, "run": True,
             "enc_mode": "ok", "error": ""}
    live = {"line": "waiting for the first cycle", "motor": False}
    return state, live


def _apply(state, live, msg, now=100.0):
    return sw.apply_command(state, msg, now, 0.30, live)


def test_estop_is_set_and_cleared_by_the_bool_and_nothing_else():
    state, live = _rig()
    assert _apply(state, live, {"estop": False}) is None
    assert state["estop"] is False
    _apply(state, live, {"estop": True})
    assert state["estop"] is True
    # 1 is not True here. A truthy non-bool arriving on this socket would
    # be an enable off a packet nobody meant to send.
    _apply(state, live, {"estop": 0})
    assert state["estop"] is True


def test_ack_opens_the_pulse_window_measured_from_now():
    state, live = _rig()
    assert _apply(state, live, {"ack": True}, now=500.0) is None
    assert state["ack_until"] == 500.0 + 0.30
    # The window is the caller's clock, not the wall clock: control_loop
    # compares it against time.monotonic().
    _apply(state, live, {"ack": True}, now=900.0)
    assert state["ack_until"] == 900.0 + 0.30
    # `false` is not a press, so it must not re-arm anything.
    _apply(state, live, {"ack": False}, now=1000.0)
    assert state["ack_until"] == 900.0 + 0.30


def test_enc_mode_takes_only_the_modes_the_panel_can_produce():
    state, live = _rig()
    assert set(sw.ENC_MODES) == {"ok", "fa", "oa"}
    for mode in sw.ENC_MODES:
        _apply(state, live, {"enc_mode": mode})
        assert state["enc_mode"] == mode
    for junk in ("stale", "OK", "", None, 3):
        _apply(state, live, {"enc_mode": junk})
        assert state["enc_mode"] == "oa", (
            "{!r} is not a panel mode and must not reach the loop".format(
                junk))


def test_status_answers_with_the_loops_own_three_values():
    state, live = _rig()
    live["motor"] = True
    live["line"] = "E-Stop=True   Motor=True   ack=False"
    state["error"] = ""
    reply = json.loads(_apply(state, live, {"status": True}))
    assert reply == {"motor": True, "line": live["line"], "error": ""}
    # A dead loop reports itself: the error is how a script learns the
    # writer stopped rather than the plant simply being safe.
    state["error"] = "control loop stopped: boom"
    live["motor"] = False
    reply = json.loads(_apply(state, live, {"status": True}))
    assert reply["motor"] is False
    assert reply["error"] == "control loop stopped: boom"


def test_quit_lowers_run_which_is_what_trips_the_plant():
    state, live = _rig()
    assert _apply(state, live, {"quit": True}) is None
    assert state["run"] is False


def test_junk_answers_nothing_and_changes_nothing():
    state, live = _rig()
    before = dict(state)
    for msg in ({}, {"reset": True}, {"motor": True}, [], "estop", 7, None,
                {"estop": "true"}, {"quit": "yes"}, {"status": 1}):
        assert _apply(state, live, msg) is None
        assert state == before, "{!r} moved the state".format(msg)


def test_watchdog_presses_reset_when_motor_is_down_and_estop_is_healthy():
    live = {"motor": False, "line": "MOTOR STOPPED"}
    state = {"estop": True}
    press, line = sw.latch_watch(
        live, state, now=100.0, last_reset=0.0, hold_s=3.0)
    assert press is True
    assert "RESET" in line and "100.0" in line


def test_watchdog_is_silent_while_motor_is_up():
    live = {"motor": True, "line": "MOTOR ENABLED"}
    press, line = sw.latch_watch(
        live, {"estop": True}, now=100.0, last_reset=0.0, hold_s=3.0)
    assert press is False
    assert line is None


def test_watchdog_never_presses_through_a_held_estop():
    # An e-stop is the operator's own hand. Acknowledging it away would
    # be inventing an operator action nobody asked for.
    # False is the pressed button: m6.py writes it to "E-Stop" as NC open.
    live = {"motor": False, "line": "E-STOP"}
    press, _line = sw.latch_watch(
        live, {"estop": False}, now=100.0, last_reset=0.0, hold_s=3.0)
    assert press is False


def test_watchdog_waits_out_its_hold_before_pressing_again():
    live = {"motor": False, "line": "MOTOR STOPPED"}
    press, _line = sw.latch_watch(
        live, {"estop": True}, now=101.0, last_reset=100.0, hold_s=3.0)
    assert press is False
    press, _line = sw.latch_watch(
        live, {"estop": True}, now=104.0, last_reset=100.0, hold_s=3.0)
    assert press is True
