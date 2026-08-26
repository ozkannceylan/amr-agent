"""wheel_odometry.py's PURE helpers - the parts of the ROS shell that are
decisions rather than plumbing.

    python3 -m pytest m5_ver3/tests/ -q

THIS FILE IMPORTS THE SHELL, AND THAT IS SAFE BY THE SHELL'S OWN DESIGN.
nodes/wheel_odometry.py keeps every rclpy import inside main(), so the
module imports on a python that has never heard of ROS - which is the
python this suite runs on. Its header says the reason; this file is the
first thing that depends on it, so if an rclpy import ever moves to the
top of that file the whole suite stops collecting and says so here.

WHY THE WATCHDOG'S THROTTLE IS A FUNCTION AND NOT AN `if` INSIDE alive().
alive() is the node's last instrument: it speaks exactly when nothing
else can, which means nobody is watching when it gets the decision wrong.
An `if` buried in a callback that only runs on a stack that is already
broken is untestable in practice - the state it needs (a dead steer
topic, twenty minutes of silence) is not a state a test can put a live
node into. As a pure function of six numbers it is eight assertions on a
laptop, and the node keeps only the counters.
"""
import pytest

import wheel_odometry


# config.yaml, section WHEEL ODOMETRY. Written out rather than read, for
# test_wheel_odom_core.py's reason: a test that read the file would pass
# for any value in it, including one changed by accident.
ALIVE_EVERY_S = 5.0
WARN_AFTER_S = 15.0
WARN_MAX = 12
WARN_BACKOFF_S = 300.0


def tick(silent_s, warns=0, last_warn_s=None, warn_max=WARN_MAX,
         backoff_s=WARN_BACKOFF_S):
    return wheel_odometry.alive_tick(
        silent_s=silent_s, warn_after_s=WARN_AFTER_S, warns=warns,
        warn_max=warn_max, backoff_s=backoff_s, last_warn_s=last_warn_s)


# ---------------------------------------------------------------- info

def test_a_short_silence_is_info_and_is_always_spoken():
    """A bringup is silence, and calling it a fault teaches the operator
    to ignore the line. Below the threshold every tick speaks, at info."""
    for silent_s in (0.0, 5.0, 10.0, 14.999):
        out = tick(silent_s)
        assert out.speak is True
        assert out.level == "info"
        assert out.backed_off is False


def test_the_info_stream_needs_no_cap_because_the_threshold_is_one():
    """There is no warn_max for info and there must not be: the info
    ticks are bounded by warn_after_s itself - three of them at a 5 s
    cadence - so a cap would be a second bound on an already bounded
    thing. The warns are the unbounded stream and the ones capped."""
    assert WARN_AFTER_S / ALIVE_EVERY_S == 3
    out = tick(14.0, warns=999, last_warn_s=0.0)
    assert out.speak is True and out.level == "info"


# ---------------------------------------------------------------- warn

def test_the_threshold_itself_is_a_warn():
    out = tick(WARN_AFTER_S)
    assert out.speak is True
    assert out.level == "warn"
    assert out.backed_off is False


def test_every_warn_up_to_the_cap_is_spoken_at_the_full_cadence():
    """The first minute of a fault is the minute an operator is reading
    the log, so nothing is throttled inside it."""
    for warns in range(WARN_MAX):
        out = tick(WARN_AFTER_S + warns * ALIVE_EVERY_S, warns=warns,
                   last_warn_s=WARN_AFTER_S + (warns - 1) * ALIVE_EVERY_S)
        assert out.speak is True
        assert out.level == "warn"
        assert out.backed_off is False


def test_past_the_cap_a_tick_inside_the_backoff_says_nothing():
    """This is the whole of the debt: bounded rate, unbounded total. Past
    the cap the cadence is the backoff and not alive_every_s."""
    last = WARN_AFTER_S + (WARN_MAX - 1) * ALIVE_EVERY_S
    out = tick(last + ALIVE_EVERY_S, warns=WARN_MAX, last_warn_s=last)
    assert out.speak is False
    assert out.backed_off is True


def test_past_the_cap_a_tick_at_the_backoff_speaks_again():
    """IT NEVER GOES SILENT, AND THAT IS DELIBERATE. A watchdog that
    stops printing makes its last line's timestamp look like the moment
    the fault ended. One line every backoff_s keeps the statement current
    for the cost of 12 lines an hour instead of 720."""
    last = WARN_AFTER_S + (WARN_MAX - 1) * ALIVE_EVERY_S
    out = tick(last + WARN_BACKOFF_S, warns=WARN_MAX, last_warn_s=last)
    assert out.speak is True
    assert out.level == "warn"
    assert out.backed_off is True


def test_the_backoff_interval_restarts_from_the_line_that_was_spoken():
    """Not from the cap, and not from zero: the interval is measured
    against the last line that actually reached the log, so a reader sees
    one line per backoff_s for as long as the fault lasts."""
    spoken_at = 1000.0
    assert tick(spoken_at + WARN_BACKOFF_S - 0.001, warns=WARN_MAX + 40,
                last_warn_s=spoken_at).speak is False
    assert tick(spoken_at + WARN_BACKOFF_S, warns=WARN_MAX + 40,
                last_warn_s=spoken_at).speak is True


def test_a_cap_of_zero_backs_off_from_the_very_first_warn():
    """The edge an operator would reach for to make a noisy rig quiet.
    With no warn spoken yet there is no interval to measure, so the first
    one is spoken and the backoff starts from it."""
    first = tick(WARN_AFTER_S, warns=0, last_warn_s=None, warn_max=0)
    assert first.speak is True and first.backed_off is True
    assert tick(WARN_AFTER_S + 1.0, warns=1, last_warn_s=WARN_AFTER_S,
                warn_max=0).speak is False


def test_a_backoff_shorter_than_the_cadence_cannot_speed_the_watchdog_up():
    """alive_every_s is the only thing that decides how often the timer
    fires. A backoff below it is not an error and is not clamped here -
    the function answers about the tick it was handed, and ticks it was
    never handed do not exist."""
    out = tick(100.0, warns=WARN_MAX, last_warn_s=99.0, backoff_s=0.1)
    assert out.speak is True and out.backed_off is True


# ------------------------------------------------- the other pure parts

def test_covariance_diagonal_is_row_major_and_zero_elsewhere():
    out = wheel_odometry.covariance_diagonal([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert len(out) == 36
    for i in range(6):
        assert out[i * 6 + i] == float(i + 1)
    assert sum(1 for v in out if v != 0.0) == 6


def test_a_stamp_that_rounds_up_carries_into_the_second():
    """seconds_to_stamp's one branch. 1.9999999999 nanoseconds-rounds to
    1e9, which is not a legal nanosec field."""
    class FakeTime(object):
        def __init__(self):
            self.sec = 0
            self.nanosec = 0

    out = wheel_odometry.seconds_to_stamp(FakeTime, 1.9999999999)
    assert out.sec == 2
    assert out.nanosec == 0


def test_joint_index_returns_none_rather_than_guessing():
    class FakeMsg(object):
        name = ["a", "b", "c"]

    assert wheel_odometry.joint_index(FakeMsg, "b") == 1
    assert wheel_odometry.joint_index(FakeMsg, "z") is None


if __name__ == "__main__":       # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
