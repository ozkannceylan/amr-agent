"""progress - has this truck advanced, and for how long has it not.

Pure arithmetic on positions the fleet already receives. No clock of its
own, no wire, no opinion about WHY a truck is not moving - that
judgement is fleet_manager's, and it is the one that knows a truck the
ledger is holding is behaving perfectly.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import progress                                      # noqa: E402


def test_an_unknown_truck_is_not_stalled():
    """Silence is not a stall. A vehicle that has published no position
    has told the fleet nothing, and a fleet that acted on that would be
    acting on nothing."""
    p = progress.Progress()
    assert p.stalled_for("f1", 100.0) is None


def test_a_truck_that_advances_resets_the_clock():
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    p.note("f1", (progress.PROGRESS_M + 0.1, 0.0),
           100.0 + progress.PROGRESS_S + 5.0)
    assert p.stalled_for("f1", 100.0 + progress.PROGRESS_S + 5.0) is None


def test_a_truck_that_shuffles_does_not_reset_it():
    """AN ANCHOR, NOT A TRAIL. Half a metre back and forth for a minute
    is movement and it is not progress; a 'distance travelled since'
    measure would miss it entirely."""
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    for i in range(20):
        p.note("f1", ((progress.PROGRESS_M / 2.0) * (i % 2), 0.0),
               100.0 + i)
    held = p.stalled_for("f1", 100.0 + progress.PROGRESS_S + 1.0)
    assert held is not None and held > progress.PROGRESS_S


def test_nothing_is_stalled_before_the_window_has_passed():
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    assert p.stalled_for("f1", 100.0 + progress.PROGRESS_S - 0.1) is None
    assert p.stalled_for("f1", 100.0 + progress.PROGRESS_S) is not None


def test_forgetting_a_truck_starts_it_again_from_clean():
    """A truck released from a two-minute wait for a corridor must start
    its clock fresh, or it is given up on the instant the corridor
    drains - the opposite of what the wait was for."""
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    assert p.stalled_for("f1", 200.0) is not None
    p.forget("f1")
    assert p.stalled_for("f1", 200.0) is None


def test_two_trucks_do_not_share_a_clock():
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    p.note("f2", (5.0, 0.0), 100.0)
    p.note("f2", (5.0 + progress.PROGRESS_M + 0.1, 0.0), 150.0)
    assert p.stalled_for("f1", 200.0) is not None
    assert p.stalled_for("f2", 200.0) is not None
    assert p.stalled_for("f1", 200.0) > p.stalled_for("f2", 200.0)


def test_the_give_up_bound_is_longer_than_the_window():
    """Otherwise a task is taken away the instant a stall is noticed,
    with no chance for the floor ahead to drain on its own."""
    assert progress.STALL_GIVE_UP_S > progress.PROGRESS_S


def test_forgetting_a_truck_nobody_knows_is_not_an_error():
    p = progress.Progress()
    p.forget("f9")          # must not raise
    assert p.stalled_for("f9", 100.0) is None
