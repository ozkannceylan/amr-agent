"""nav2_watch.py - the no-progress rule and the BLOCKED notes.

THE RULE IS PINNED AGAINST THE ONE IT IS A PORT OF. drive_goal's
ClosingWatch is m5v3's measured instrument (F4 Task 2: 130.199 m driven
and 459 plans published for a goal 2.910 m away); this file's job is to
prove the port answers identically over the same samples, not to have
its own opinion about closing.

THE NOTES ARE THE WIRE'S ONLY WHY. `/auto/state.note` is the single
field that says what stopped the truck, and vda_agent quotes it verbatim
into a VDA `pathBlocked` errorDescription. So the formats are asserted
character by character.
"""
import math
import os

import pytest

import drive_goal

import nav2_watch


def _stream(distances, dt=1.0):
    return [(i * dt, d) for i, d in enumerate(distances)]


# ----------------------------------------------------------------------
# ClosingWatch, against its producer
# ----------------------------------------------------------------------

def test_a_run_that_keeps_closing_is_never_stalled():
    watch = nav2_watch.ClosingWatch(required_closing_m=0.50,
                                    allowance_s=30.0)
    for t, d in _stream([20.0, 15.0, 10.0, 5.0, 1.0], dt=5.0):
        assert watch.step(t, d) is None


def test_the_orbit_is_caught_and_the_creep_is_not():
    # THE FAILURE THE RULE EXISTS FOR: a vehicle orbiting its goal moves
    # 0.30 m every second and satisfies SimpleProgressChecker completely.
    orbit = [(float(t), 2.910 + 0.05 * math.sin(t)) for t in range(0, 60)]
    watch = nav2_watch.ClosingWatch(0.50, 30.0)
    verdicts = [watch.step(t, d) for t, d in orbit]
    assert any(v is not None for v in verdicts)


def test_a_millimetre_a_second_does_not_reset_the_clock():
    # WHY THE MARGIN AND NOT ANY IMPROVEMENT AT ALL.
    creep = [(float(t), 5.0 - 0.001 * t) for t in range(0, 60)]
    watch = nav2_watch.ClosingWatch(0.50, 30.0)
    assert any(watch.step(t, d) is not None for t, d in creep)


def test_the_verdict_is_identical_to_drive_goals_over_the_same_samples():
    samples = _stream([9.0, 8.0, 7.5, 7.4, 7.4, 7.4, 7.4, 7.4, 7.4],
                      dt=6.0)
    mine = nav2_watch.no_progress_at(samples, 0.50, 30.0)
    theirs = drive_goal.no_progress_at(samples, 0.50, 30.0)
    assert theirs is not None
    assert (mine.t, mine.distance, mine.mark, mine.since_s) == (
        theirs.t, theirs.distance, theirs.mark, theirs.since_s)


def test_the_stalled_record_carries_the_same_four_fields():
    assert nav2_watch.Stalled._fields == drive_goal.Stalled._fields


def test_a_localisation_jump_away_from_the_goal_cannot_provoke_it():
    # A map -> odom correction that moves the belief AWAY is not an
    # improvement, so it can only delay this guard, never fire it early.
    watch = nav2_watch.ClosingWatch(0.50, 10.0)
    assert watch.step(0.0, 10.0) is None
    assert watch.step(1.0, 40.0) is None          # the jump
    assert watch.step(2.0, 9.0) is None           # a real improvement
    assert watch.mark == 9.0


def test_a_non_finite_distance_is_refused_by_name():
    watch = nav2_watch.ClosingWatch(0.50, 30.0)
    with pytest.raises(nav2_watch.Nav2WatchError):
        watch.step(0.0, float("nan"))


# ----------------------------------------------------------------------
# the notes
# ----------------------------------------------------------------------

def test_the_no_progress_note_names_the_instrument_and_the_numbers():
    stalled = nav2_watch.Stalled(t=41.0, distance=2.93, mark=2.91,
                                 since_s=30.4)
    assert (nav2_watch.blocked_note_no_progress(stalled)
            == "blocked: no progress - best 2.91 m, 30 s without closing")


def test_the_planner_note_carries_the_code_and_nothing_else():
    assert (nav2_watch.blocked_note_for_error(205)
            == "blocked: planner refused (error_code 205)")
    for code in (203, 206, 208, 201, 299):
        assert "planner refused" in nav2_watch.blocked_note_for_error(code)


def test_the_controller_note_is_a_different_sentence():
    assert (nav2_watch.blocked_note_for_error(106)
            == "blocked: controller gave up (error_code 106)")
    for code in (104, 105, 100, 199):
        assert "controller gave up" in nav2_watch.blocked_note_for_error(code)


def test_a_code_outside_both_families_still_gets_a_why():
    # A note is the wire's only WHY, so an unrecognised code may not
    # produce an empty one. The number is still there to look up.
    note = nav2_watch.blocked_note_for_error(701)
    assert "701" in note and note.startswith("blocked: ")


def test_a_code_that_is_not_a_number_is_refused_by_name():
    with pytest.raises(nav2_watch.Nav2WatchError):
        nav2_watch.blocked_note_for_error("ABORTED")


def test_the_arrived_short_note_states_both_radii():
    assert (nav2_watch.arrived_short_note(0.41, 0.25)
            == "arrived short: 0.41 m against arrive_m 0.25")


def test_the_error_code_legend_is_the_repos_own():
    # drive_goal prints this legend to the operator when a plan is
    # refused; the same four planner codes and their names live here so
    # the adapter's log line reads the same as the tool's.
    assert nav2_watch.error_code_name(205) == "START_OCCUPIED"
    assert nav2_watch.error_code_name(208) == "NO_VALID_PATH"
    assert nav2_watch.error_code_name(106) == "NO_VALID_CONTROL"
    assert nav2_watch.describe_error(205) == "205 START_OCCUPIED"
    assert nav2_watch.describe_error(999) == "999"


def test_every_legend_name_is_pinned_to_the_file_that_states_it():
    # NOTHING IN THE LEGEND IS REMEMBERED RATHER THAN READ. The planner
    # names are drive_goal's own printed legend; the controller names
    # are the ones SPEC_ADAPTER.md's BLOCKED table calls out. A code
    # whose name appears in neither file has no business being here.
    with open(drive_goal.__file__, "r", encoding="utf-8") as handle:
        tool = handle.read()
    spec = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        os.pardir, "SPEC_ADAPTER.md")
    with open(os.path.normpath(spec), "r", encoding="utf-8") as handle:
        contract = handle.read()
    for code in (203, 205, 206, 208):
        assert nav2_watch.error_code_name(code) in tool, code
    for code in (104, 105, 106):
        assert nav2_watch.error_code_name(code) in contract, code


# ----------------------------------------------------------------------
# the selftest
# ----------------------------------------------------------------------

def test_the_selftest_is_green():
    assert nav2_watch._selftest() == 0
