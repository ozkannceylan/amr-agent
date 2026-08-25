"""record_operator's pure helper: the clock strip.

The recorder's job is lining the floor up with the screen; the clock
strip is what lets a viewer line EITHER up with the wall. It is pure
arithmetic on (sim_s, wall_s) samples and is tested here without a
camera, a broker or ROS - main() owns all three.
"""
import os
import sys

import pytest

pytest.importorskip("paho.mqtt.client")

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in ("tools", "fleet"):
    sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", _sub)))

import record_operator as ro                        # noqa: E402


def test_the_clock_strip_names_sim_wall_and_rtf():
    clock = ro.RateClock()
    clock.note(sim_s=100.0, wall_s=1000.0)
    clock.note(sim_s=130.0, wall_s=1050.0)   # 30 sim s over 50 wall s
    line = clock.line()
    assert "sim 130.0 s" in line
    assert "RTF" in line and "0.60" in line


def test_one_sample_is_not_a_rate():
    """A single frame gives a clock but no rate - the strip must say
    the time and stay silent about RTF rather than print a 0.00 that
    reads as a dead rig."""
    clock = ro.RateClock()
    clock.note(sim_s=100.0, wall_s=1000.0)
    line = clock.line()
    assert "sim 100.0 s" in line
    assert "RTF" not in line


def test_the_rate_window_slides():
    """The RTF is a recent number, not a run average: a stall five
    minutes ago must stop dragging the figure once the window has
    passed it."""
    clock = ro.RateClock(window_s=60.0)
    clock.note(sim_s=0.0, wall_s=0.0)
    clock.note(sim_s=1.0, wall_s=100.0)      # ancient, terrible
    clock.note(sim_s=31.0, wall_s=150.0)     # recent, 30/50 = 0.60
    assert "0.60" in clock.line()
