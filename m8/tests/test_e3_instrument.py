"""The E3 instrument's joins, on a machine with no plant.

`e3_abort.py` imports nothing but the standard library at module level -
`bench.plant` and `m8_core` are imported inside the functions that need
them - so the four joins added for the words run can be held here,
without ROS, without gz and without a rig booking.

What these tests are FOR. The 2026-09-12 run reported a live false-abort
rate of 0.884 over 1073 frames and could not say what the 948 aborts
were. The joins below are what turn that one number into a table, so
each one is held against the way it would silently lie:

  * a range band that swallowed an out-of-range value would put frames
    in the wrong row;
  * a retry join that filled forward from nothing would call an unknown
    retry count zero, which is exactly the frames the bar must exclude;
  * a `countable` flag that ignored the pallet readback would average a
    cycle that shoved the pallet into one that did not.
"""
import os
import sys

import pytest

_M8 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

from bench import e3_abort as E3                                # noqa: E402


# ------------------------------------------------------------- regimes
@pytest.mark.parametrize("cam_range_m,band", [
    (2.245, "staging"),          # the staging pose itself
    (2.0, "staging"),            # the edge belongs to the band above it
    (1.999, "approach"),
    (1.2, "approach"),
    (1.1999, "close"),
    (0.5, "close"),
    (0.0, "close"),
])
def test_range_bands_are_half_open_and_cover_the_approach(cam_range_m, band):
    assert E3.regime_of(cam_range_m) == band


def test_a_frame_with_no_truth_pose_is_unknown_not_close():
    # cam_range_m is absent whenever the truth Odometry had not arrived
    # when the depth frame did. Calling that 0.0 m would file it under
    # `close`, the band where C1 is known to refuse, and manufacture the
    # very finding the run is trying to measure.
    assert E3.regime_of(None) == "unknown"
    assert E3.regime_of(float("nan")) == "unknown"
    assert E3.regime_of("") == "unknown"


def test_the_bands_are_slicing_only_and_no_gate_reads_them():
    from m8_core import abort, pocket
    for source in (abort, pocket):
        assert not hasattr(source, "REGIMES")


# -------------------------------------------------------------- retries
def _rows(*stamps):
    return [{"stamp": s, "k": i} for i, s in enumerate(stamps)]


def test_retries_are_held_backwards_from_the_last_feedback_message():
    # The docking server publishes feedback on change, so the value in
    # force at a frame's stamp is the last one published at or before it.
    feedback = [(10.0, 1, 0), (14.0, 5, 1), (18.0, 1, 2)]
    rows = _rows(10.0, 12.0, 14.0, 15.5, 19.0)
    joined = E3._join_retries(rows, feedback)
    assert joined == 5
    assert [r["num_retries"] for r in rows] == [0, 0, 1, 1, 2]
    assert [r["dock_state"] for r in rows] == [1, 1, 5, 5, 1]
    assert all(r["retry_joined"] == 1 for r in rows)


def test_a_frame_before_the_first_feedback_message_is_unknown_not_zero():
    feedback = [(10.0, 1, 0)]
    rows = _rows(9.0, 11.0)
    joined = E3._join_retries(rows, feedback)
    assert joined == 1
    assert rows[0]["retry_joined"] == 0
    assert "num_retries" not in rows[0]
    assert rows[1]["num_retries"] == 0


def test_no_feedback_at_all_joins_nothing_and_says_so():
    rows = _rows(1.0, 2.0)
    assert E3._join_retries(rows, []) == 0
    assert all(r["retry_joined"] == 0 for r in rows)
    assert all("num_retries" not in r for r in rows)


def test_the_join_does_not_depend_on_the_order_frames_arrived_in():
    feedback = [(10.0, 1, 0), (14.0, 5, 1)]
    rows = _rows(15.0, 11.0, 14.0)
    E3._join_retries(rows, feedback)
    by_stamp = {r["stamp"]: r["num_retries"] for r in rows}
    assert by_stamp == {11.0: 0, 14.0: 1, 15.0: 1}


# ------------------------------------------------------------- readback
def test_pallet_movement_is_planar_and_needs_both_readbacks():
    before = (7.0, 3.03, 0.072, 0.0, 0.0, 1.5708)
    after = (7.03, 3.07, 0.072, 0.0, 0.0, 1.5708)
    assert E3._pallet_moved_m(before, after) == pytest.approx(0.05, abs=1e-9)
    assert E3._pallet_moved_m(before, None) is None
    assert E3._pallet_moved_m(None, after) is None


def test_the_moved_tolerance_is_well_under_a_pocket():
    # 0.02 m has to be an order over gz readback jitter and far under the
    # 0.160 m pocket it would take to matter. Both sides, so a future
    # edit that loosens it trips here.
    from m8_core.scene import Scene
    pocket_w = Scene().pocket_outer - Scene().pocket_inner      # 0.160 m
    assert 0.005 < E3.PALLET_MOVED_TOL_M < 0.5 * pocket_w


# ------------------------------------------------------------ the table
def test_by_regime_splits_the_rate_instead_of_averaging_it():
    rows = ([{"regime": "staging", "abort": 0, "reason": "none", "refused": ""}] * 10
            + [{"regime": "close", "abort": 1, "reason": "pallet_absent",
                "refused": "face_is_too_small_a_share"}] * 10)
    table = E3._by_regime(rows)
    assert table["staging"]["rate"] == 0.0
    assert table["close"]["rate"] == 1.0
    assert table["close"]["refusals"]["face_is_too_small_a_share"] == 10
    assert table["staging"]["refusals"]["(segmented)"] == 10


def test_refusal_counts_separate_a_word_from_the_gate_behind_it():
    rows = [{"reason": "pallet_absent", "refused": "face_is_too_small_a_share"},
            {"reason": "pallet_absent", "refused": ""}]
    counts = E3._refusal_counts(rows)
    assert counts["face_is_too_small_a_share"] == 1
    assert counts["(segmented)"] == 1
