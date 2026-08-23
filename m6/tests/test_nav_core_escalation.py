"""HOLD stops being terminal. The escalation, as a table.

WHAT THIS FILE IS REALLY FOR is the first test in it. Everything else
here is bookkeeping that a careful reader could check by eye; the sign
of the scan frame against the world frame cannot be checked by eye, it
is wrong half the time by construction, and when it is wrong the truck
steers AWAY from the only free floor in the room.
"""
import math

import avoid
import follower
import nav_core
from status_contract import MODE_AUTO

CLEAR = 9.9            # a guard reading that stops nothing
BLOCKED_M = 1.0        # inside follower.GUARD_HOLD_M (1.50)
N = 360
ANGLE_MIN = -math.pi
ANGLE_INC = 2.0 * math.pi / N


def core(route=None):
    c = nav_core.NavCore()
    c.mode = MODE_AUTO
    c.on_route(route or [[0.0, 0.0], [10.0, 0.0]], 0.25, "t-1")
    return c


def walled():
    return avoid.buckets([BLOCKED_M] * N, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)


def scan_with_gap_to_one_side():
    """A wall ahead of a truck travelling +x, clear floor to one side.

    The truck's forks lead at model yaw + pi, and the scan's fork end is
    at angle pi. So 'ahead' is pi and the wall is put there, spread
    asymmetrically so exactly one side of it is free.
    """
    ranges = [8.0] * N
    for i in range(N):
        off = math.degrees(follower.norm_ang(
            ANGLE_MIN + i * ANGLE_INC - math.pi))
        if -25.0 <= off <= 60.0:
            ranges[i] = BLOCKED_M
    return avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)


def drive_to_patience(c, bkts, pose=(0.0, 0.0, math.pi), now=100.0):
    """Two ticks: one that starts the stop, one at the end of patience."""
    c.step(pose, BLOCKED_M, CLEAR, True, 1500, buckets=bkts, now=now)
    return c.step(pose, BLOCKED_M, CLEAR, True, 1500, buckets=bkts,
                  now=now + nav_core.HOLD_PATIENCE_S)


def drive_until(c, bkts, want, pose=(0.0, 0.0, math.pi), now=100.0,
                limit=40):
    """Tick a wedged truck until it reaches `want`, and return the clock.

    THE COUNT IS NOT PINNED ON PURPOSE. How many ticks it takes to reach
    BLOCKED is HOLD_PATIENCE_S, NUDGE_TIMEOUT_S and NUDGE_MAX arguing
    with each other, and a test that writes that product down has to be
    rewritten every time one of them moves - which is how a test stops
    being about the behaviour and starts being about the arithmetic.
    """
    step_s = max(nav_core.HOLD_PATIENCE_S, nav_core.NUDGE_TIMEOUT_S) + 1.0
    for _ in range(limit):
        c.step(pose, BLOCKED_M, CLEAR, True, 1500, buckets=bkts, now=now)
        if c.state == want:
            return now
        now += step_s
    raise AssertionError(
        "never reached {} in {} ticks - last state {}".format(
            want, limit, c.state))


def test_the_scan_sign_puts_the_steer_toward_the_gap():
    """THE PIN. A wall ahead and floor on ONE side: the steer must have
    the sign that turns toward the floor, whatever the mounting is."""
    c = core()
    bkts = scan_with_gap_to_one_side()
    free = avoid.free_heading(bkts, math.pi)
    assert free is not None, "the staging left no gap - this proves nothing"
    off = follower.norm_ang(free - math.pi)
    assert off != 0.0, "the staging left the wanted heading free"

    linear, steer = drive_to_patience(c, bkts)
    assert c.state == nav_core.AVOID, c.state
    assert linear != 0.0
    # follower.steer carries a leading minus: a target CLOCKWISE of the
    # travel heading (negative alpha) needs POSITIVE steer. So the steer
    # must come out the opposite sign to the offset the gap sits at,
    # once SCAN_SIGN has put that offset in the world's terms.
    assert (steer > 0.0) == (off * nav_core.SCAN_SIGN < 0.0), (
        "the truck steered away from the only free floor in the room - "
        "SCAN_SIGN is inverted (steer {:.3f}, gap offset {:.3f})"
        .format(steer, off))


def test_a_clear_guard_never_enters_the_escalation():
    c = core()
    linear, _steer = c.step((0.0, 0.0, math.pi), CLEAR, CLEAR, True, 1500,
                            buckets=scan_with_gap_to_one_side(), now=100.0)
    assert c.state == nav_core.EN_ROUTE
    assert linear != 0.0


def test_hold_waits_out_its_patience_before_anything_else():
    c = core()
    bkts = scan_with_gap_to_one_side()
    for dt in (0.0, 1.0, nav_core.HOLD_PATIENCE_S - 0.1):
        out = c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500,
                     buckets=bkts, now=100.0 + dt)
        assert c.state == nav_core.HOLD, dt
        assert out == (0.0, 0.0)


def test_a_free_heading_at_patience_gives_avoid_at_the_creep_ceiling():
    c = core()
    linear, steer = drive_to_patience(c, scan_with_gap_to_one_side())
    assert c.state == nav_core.AVOID
    assert abs(linear) == follower.GUARD_SLOW_MPS
    assert abs(steer) <= 1.31, "past the steer stop cmd_gate declares"


def test_no_free_heading_gives_a_nudge_and_it_reverses():
    c = core()
    linear, steer = drive_to_patience(c, walled())
    assert c.state == nav_core.NUDGE
    assert steer == 0.0, "a nudge is straight - an arc is what it avoids"
    assert linear > 0.0, "forward is negative here; a nudge reverses"


def test_a_nudge_that_has_run_its_distance_ends():
    c = core()
    bkts = walled()
    now = 100.0
    drive_to_patience(c, bkts, now=now)
    assert c.state == nav_core.NUDGE
    moved = (nav_core.NUDGE_M + 0.05, 0.0, math.pi)
    c.step(moved, BLOCKED_M, CLEAR, True, 1500, buckets=bkts,
           now=now + nav_core.HOLD_PATIENCE_S + 2.0)
    assert c.state != nav_core.NUDGE


def test_a_nudge_the_truck_cannot_execute_still_ends():
    """A wedged truck never covers NUDGE_M, so a nudge measured only in
    metres would never end - the state machine would grow exactly the
    dead end it exists to remove. NUDGE_TIMEOUT_S is what closes it."""
    c = core()
    bkts = walled()
    pose, now = (0.0, 0.0, math.pi), 100.0
    drive_to_patience(c, bkts, pose=pose, now=now)
    assert c.state == nav_core.NUDGE
    # the truck reports the same position for the whole timeout
    out = c.step(pose, BLOCKED_M, CLEAR, True, 1500, buckets=bkts,
                 now=now + nav_core.HOLD_PATIENCE_S
                 + nav_core.NUDGE_TIMEOUT_S)
    assert c.state != nav_core.NUDGE, "a nudge with no way out of itself"
    assert out == (0.0, 0.0)


def test_nudging_without_getting_anywhere_ends_in_blocked():
    c = core()
    bkts = walled()
    drive_until(c, bkts, nav_core.BLOCKED)
    out = c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500,
                 buckets=bkts, now=1000.0)
    assert c.state == nav_core.BLOCKED, c.state
    assert out == (0.0, 0.0)
    assert "m" in c.note and "deg" in c.note, (
        "BLOCKED must name the bearing and the range: {!r}".format(c.note))


def test_the_guard_clearing_ends_any_state_at_once():
    c = core()
    bkts = walled()
    now = drive_until(c, bkts, nav_core.BLOCKED)
    linear, _ = c.step((0.0, 0.0, math.pi), CLEAR, CLEAR, True, 1500,
                       buckets=bkts, now=now + 1.0)
    assert c.state == nav_core.EN_ROUTE
    assert linear != 0.0


def test_a_new_goal_clears_the_escalation_it_was_stuck_in():
    c = core()
    bkts = walled()
    now = drive_until(c, bkts, nav_core.BLOCKED)
    c.on_route([[0.0, 0.0], [0.0, 10.0]], 0.25, "t-2")
    assert c.state == nav_core.EN_ROUTE
    out = c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500,
                 buckets=bkts, now=now + 1.0)
    assert c.state == nav_core.HOLD, "the new goal inherited the old stop"
    assert out == (0.0, 0.0)


def test_without_a_clock_or_buckets_the_file_behaves_as_it_did():
    """The compatibility contract. Every caller written before M6.7 -
    including test_nav_node.py's - passes neither, and must still see
    the HOLD it was written against."""
    c = core()
    out = c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500)
    assert c.state == nav_core.HOLD
    assert out == (0.0, 0.0)
    for _ in range(50):
        c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500)
    assert c.state == nav_core.HOLD, "the escalation ran with no clock"
