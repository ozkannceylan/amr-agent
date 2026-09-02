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

import nav2_legs
import nav2_path
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


# ----------------------------------------------------------------------
# D6 - TWO BELIEFS, ONE BOUNDARY, run4 2026-09-02
#
# nav2's `station_goal_checker` and the adapter's `arrive_m` are the
# SAME number, 0.25 m, read off two different beliefs: nav2 checks
# AMCL's map pose, the adapter checks the composed estimate through the
# committed registration, and they are sampled at different instants.
# Three arrivals at S1 in one run measured 0.2453, 0.2482 and 0.2502 m -
# and the third one, five tenths of a millimetre outside, made nav2's
# SUCCEEDED an "arrived short" and put the task BLOCKED back on the
# fleet's queue.
#
# THE VERDICT NEEDS A MARGIN AND THE MARGIN IS ALREADY MEASURED: the
# committed registration states its own residual against the building
# (MAX 0.1179 m for warehouse_v3), and two beliefs of one truck cannot
# be asked to agree closer than the transform between their frames is
# known. The verdict this note exists for - m5v3's S7 orbit, a stable
# 0.643-0.742 m ring round a station the truck can never reach - is
# still a mile outside it.
# ----------------------------------------------------------------------

REGISTRATION_MAX_M = 0.1179


def test_two_beliefs_at_the_boundary_are_not_a_miss():
    for distance in (0.2453, 0.2482, 0.2502, 0.30, 0.3679):
        assert not nav2_watch.arrival_is_short(
            distance, 0.25, REGISTRATION_MAX_M), distance


def test_the_s7_orbit_is_still_a_miss():
    for distance in (0.3680, 0.41, 0.643, 0.742):
        assert nav2_watch.arrival_is_short(
            distance, 0.25, REGISTRATION_MAX_M), distance


def test_a_transform_that_states_no_residual_buys_no_margin():
    # A registration with no stated residual is not an excuse for one.
    assert nav2_watch.arrival_is_short(0.2502, 0.25, 0.0)
    assert not nav2_watch.arrival_is_short(0.2500, 0.25, 0.0)


def test_an_unknown_pose_is_always_short():
    assert nav2_watch.arrival_is_short(float("inf"), 0.25, REGISTRATION_MAX_M)


def test_the_margin_is_a_magnitude():
    assert nav2_watch.arrival_is_short(0.40, 0.25, -0.10) is \
        nav2_watch.arrival_is_short(0.40, 0.25, 0.10)


def test_a_margin_that_is_not_a_number_is_refused_by_name():
    with pytest.raises(nav2_watch.Nav2WatchError) as caught:
        nav2_watch.arrival_is_short(0.30, 0.25, None)
    assert "margin" in str(caught.value)


# ----------------------------------------------------------------------
# THE SECOND ACTION SERVER'S OWN CODES (SPEC_ADAPTER.md AMENDMENTS 9)
#
# A ring chain is a `nav2_msgs/FollowPath`, so an aborted chain comes
# back with a CONTROLLER code and never a planner one - there is no
# planner in its path at all. The FollowPath.action file
# (/opt/ros/jazzy/share/nav2_msgs/action/FollowPath.action, nav2 1.3.12)
# declares 101..107, all inside CONTROLLER_CODES, so the table already
# reads every one of them. This is the pin that says so.
# ----------------------------------------------------------------------

def test_every_follow_path_error_code_lands_in_the_controller_row():
    declared = {101: "INVALID_CONTROLLER", 102: "TF_ERROR",
                103: "INVALID_PATH", 104: "PATIENCE_EXCEEDED",
                105: "FAILED_TO_MAKE_PROGRESS", 106: "NO_VALID_CONTROL",
                107: "CONTROLLER_TIMED_OUT"}
    for code, name in declared.items():
        assert code in nav2_watch.CONTROLLER_CODES, code
        note = nav2_watch.blocked_note_for_error(code)
        assert note == "blocked: controller gave up (error_code {})".format(
            code)
        assert nav2_watch.error_code_name(code) == name


def test_the_chain_refusal_note_is_a_sentence_and_not_a_number():
    """It is not nav2 saying no - it is THIS adapter refusing to build.

    A corner too tight to round at the truck own turning radius has no
    nav2 error code, because nav2 was never asked. The note has to carry
    the WHY on its own.
    """
    note = nav2_watch.CHAIN_REFUSED_NOTE
    assert note.startswith("blocked: ")
    assert "polyline" in note
    assert "error_code" not in note


# ----------------------------------------------------------------------
# DEFECT D16: ONE WATCH, TWO RULERS, AND THE CHAIN'S IS NAMED
#
# The rule above is right and it was fed the wrong number. A RING_CHAIN
# turns away from its own end by construction, so the straight line to
# that end GROWS while the truck drives the corridor correctly - run-18
# killed four consecutive orders on it at 0.30 m/s with the fleet's own
# node counter advancing 10 -> 9 -> 8 underneath.
#
# The rule does not change. What changes is that the watch now carries
# the RULER it is measuring with, so the shell cannot pick the wrong one
# by omission and the note can say which one produced the number.
# ----------------------------------------------------------------------

#: run-18's leg-2 chain, and the pose track that killed it. The route
#: is byte-for-byte the one vda_agent released at 13:23:07.
RUN18_ROUTE = [(-12.999499560306049, 4.493182698768322),
               (-13.0, 4.25), (-13.0, 10.0), (-10.0, 10.0), (-7.0, 10.0),
               (-3.5, 10.0), (0.0, 10.0), (0.0, 0.0), (0.0, -10.0),
               (-3.5, -10.0), (-7.0, -10.0), (-7.0, -4.25)]

RUN18_KILL_WINDOW = [
    (0.00, -12.9995, 4.4932), (1.05, -13.0002, 4.5475),
    (2.17, -13.0031, 4.8560), (3.20, -13.0069, 5.1288),
    (4.25, -13.0085, 5.4222), (5.33, -13.0089, 5.7081),
    (6.41, -13.0022, 6.0326), (7.44, -12.9894, 6.3010),
    (8.51, -12.9822, 6.6010), (9.62, -12.9739, 6.8914),
    (10.65, -12.9705, 7.1877), (11.71, -12.9705, 7.4643),
    (12.82, -12.9750, 7.8016), (13.85, -12.9825, 8.0947),
    (14.90, -13.0060, 8.3786), (15.97, -13.0407, 8.6715),
    (17.06, -13.0743, 8.9462), (18.11, -13.0959, 9.1797),
    (19.20, -13.0855, 9.4067), (20.27, -13.0394, 9.6309),
    (21.31, -12.9474, 9.8344), (22.38, -12.8085, 10.0057),
    (23.48, -12.6253, 10.1464), (24.51, -12.3728, 10.2322),
    (25.58, -12.0715, 10.2269), (26.64, -11.7708, 10.1604),
    (27.69, -11.4903, 10.0769), (28.73, -11.2294, 9.9969),
    (29.81, -10.9416, 9.9238), (30.88, -10.7355, 9.8883),
    (31.71, -10.7046, 9.8837),
]


def _run18_chain():
    legs = nav2_legs.plan_legs(RUN18_ROUTE)
    return legs[0], nav2_legs.chain_path(
        legs[0], current_yaw=-1.567, start_xy=(-12.9995, 4.4932))


def test_the_straight_ruler_is_the_distance_to_the_leg_end():
    metric = nav2_watch.straight_metric((-7.0, -10.0))
    assert metric.name == "dist"
    assert metric.of((-13.0, 4.25)) == math.dist((-13.0, 4.25),
                                                 (-7.0, -10.0))


def test_the_chain_ruler_is_what_is_left_of_the_path():
    _leg, built = _run18_chain()
    metric = nav2_watch.chain_metric(built.poses)
    assert metric.name == "remain"
    assert metric.of((-13.0, 4.25)) == pytest.approx(44.14, abs=0.01)
    assert metric.of((-7.0, -10.0)) == pytest.approx(0.0, abs=0.01)


def test_the_watch_measures_with_the_ruler_it_was_given():
    watch = nav2_watch.ClosingWatch(
        0.50, 30.0, metric=nav2_watch.straight_metric((0.0, 0.0)))
    assert watch.measure((3.0, 4.0)) == pytest.approx(5.0)


def test_a_watch_with_no_ruler_refuses_to_measure_by_name():
    """The rule may be built with two numbers - that is the port the
    drive_goal tests pin - but a shell that forgets to hand it a ruler
    gets an exception and never a silent guess."""
    watch = nav2_watch.ClosingWatch(0.50, 30.0)
    assert watch.metric is None
    assert watch.step(0.0, 9.0) is None
    with pytest.raises(nav2_watch.Nav2WatchError) as caught:
        watch.measure((1.0, 1.0))
    assert "ruler" in str(caught.value) or "metric" in str(caught.value)


def test_observe_measures_and_steps_in_one_call():
    watch = nav2_watch.ClosingWatch(
        0.50, 10.0, metric=nav2_watch.straight_metric((0.0, 0.0)))
    distance, stalled = watch.observe(0.0, (10.0, 0.0))
    assert distance == pytest.approx(10.0) and stalled is None
    for t in range(1, 20):
        distance, stalled = watch.observe(float(t), (10.0, 0.0))
    assert stalled is not None
    assert stalled.mark == pytest.approx(10.0)


# ----------------------------------------------------------------------
# THE REGRESSION, in the watch's own terms
# ----------------------------------------------------------------------

def test_run18s_kill_window_kills_on_the_straight_ruler():
    """What actually happened: four orders, this note, each time."""
    straight = nav2_watch.straight_metric((-7.0, -10.0))
    watch = nav2_watch.ClosingWatch(0.50, 30.0, metric=straight)
    verdict = None
    for t, x, y in RUN18_KILL_WINDOW:
        _d, stalled = watch.observe(t, (x, y))
        verdict = verdict or stalled
    assert verdict is not None
    assert verdict.mark == pytest.approx(15.686, abs=0.002)
    # THE FIXTURE SAMPLES AT 1 Hz AND THE SHELL AT 20 - so the verdict
    # here lands 0.88 s late and rounds to 31. The note run-18 actually
    # printed is the one a 20 Hz watch produces off the SAME mark, and
    # that is the byte-for-byte claim.
    assert (nav2_watch.blocked_note_no_progress(
                nav2_watch.Stalled(t=30.05, distance=20.93,
                                   mark=verdict.mark, since_s=30.05),
                straight)
            == "blocked: no progress - best 15.69 m, 30 s without closing")


def test_run18s_kill_window_survives_the_chain_ruler():
    """The same thirty seconds, measured along the path the truck drove.

    It falls 7.26 m without one step the wrong way, so the mark moves on
    every single sample and the clock never starts.
    """
    _leg, built = _run18_chain()
    watch = nav2_watch.ClosingWatch(
        0.50, 30.0, metric=nav2_watch.chain_metric(built.poses))
    first = last = None
    for t, x, y in RUN18_KILL_WINDOW:
        distance, stalled = watch.observe(t, (x, y))
        assert stalled is None, (t, distance)
        first = distance if first is None else first
        last = distance
    assert first == pytest.approx(43.896, abs=0.002)
    assert last == pytest.approx(36.631, abs=0.002)


def test_the_note_names_the_ruler_when_it_is_not_the_ordinary_one():
    """A "best 36.64 m" on a chain is not a "best 36.64 m" across a room.

    The note is the wire's only WHY and vda_agent quotes it verbatim
    into a pathBlocked errorDescription, so the sentence has to say
    which ruler produced the number. The straight one is the ordinary
    case and its bytes do not move.
    """
    stalled = nav2_watch.Stalled(t=41.0, distance=36.70, mark=36.64,
                                 since_s=30.4)
    assert (nav2_watch.blocked_note_no_progress(
                stalled, nav2_watch.chain_metric([(0.0, 0.0), (1.0, 0.0)]))
            == "blocked: no progress - best 36.64 m along the chain, "
               "30 s without closing")
    assert (nav2_watch.blocked_note_no_progress(stalled)
            == nav2_watch.blocked_note_no_progress(
                stalled, nav2_watch.straight_metric((0.0, 0.0))))


def test_a_ruler_the_note_table_does_not_know_is_refused_by_name():
    stalled = nav2_watch.Stalled(t=41.0, distance=2.93, mark=2.91,
                                 since_s=30.4)
    made_up = nav2_watch.ClosingMetric(name="furlongs", of=lambda xy: 1.0)
    with pytest.raises(nav2_watch.Nav2WatchError):
        nav2_watch.blocked_note_no_progress(stalled, made_up)


def test_the_chain_ruler_refuses_a_path_that_is_not_one():
    with pytest.raises(nav2_path.Nav2PathError):
        nav2_watch.chain_metric([(0.0, 0.0)])
