"""work_generator - which transport to ask for next. Pure.

No broker, no clock, no ROS: this file decides a station pair and
nothing else, which is what makes the decision reproducible. A seeded
generator is not a convenience here - the GUI take of the recording has
to replay the headless take's scenario exactly, and a seed is the only
thing that makes two runs the same run.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import work_generator as wg                                  # noqa: E402
from stations import STATIONS                                # noqa: E402


def test_the_same_seed_gives_the_same_sequence():
    a = [wg.WorkGenerator(seed=7).next_pair() for _ in range(20)]
    b = [wg.WorkGenerator(seed=7).next_pair() for _ in range(20)]
    assert a[0] == b[0]
    one = wg.WorkGenerator(seed=7)
    two = wg.WorkGenerator(seed=7)
    assert [one.next_pair() for _ in range(20)] == \
           [two.next_pair() for _ in range(20)]


def test_a_different_seed_gives_a_different_sequence():
    one = wg.WorkGenerator(seed=7)
    two = wg.WorkGenerator(seed=8)
    assert [one.next_pair() for _ in range(20)] != \
           [two.next_pair() for _ in range(20)]


def test_it_never_asks_for_a_transport_to_the_same_station():
    gen = wg.WorkGenerator(seed=3)
    for _ in range(500):
        src, dst = gen.next_pair()
        assert src != dst


def test_every_pair_names_a_real_station():
    gen = wg.WorkGenerator(seed=4)
    for _ in range(200):
        for sid in gen.next_pair():
            assert sid in STATIONS


def test_no_pair_is_shorter_than_the_minimum():
    gen = wg.WorkGenerator(seed=5, min_len_m=15.0)
    lengths = {(a, b): d for a, b, d in gen.pairs}
    for _ in range(300):
        assert lengths[gen.next_pair()] >= 15.0


def test_long_routes_are_favoured_over_short_ones():
    # Weight is proportional to length, so the longest quartile of pairs
    # must come up more often than the shortest quartile. Without this
    # the recording is full of shuffles between neighbouring bays.
    gen = wg.WorkGenerator(seed=11)
    ordered = sorted(gen.pairs, key=lambda p: p[2])
    cut = len(ordered) // 4
    short = {(a, b) for a, b, _d in ordered[:cut]}
    long_ = {(a, b) for a, b, _d in ordered[-cut:]}
    drawn = [gen.next_pair() for _ in range(2000)]
    assert sum(p in long_ for p in drawn) > sum(p in short for p in drawn)


def test_it_refuses_a_minimum_no_pair_can_meet():
    with pytest.raises(ValueError, match="no station pair"):
        wg.WorkGenerator(seed=1, min_len_m=500.0)
