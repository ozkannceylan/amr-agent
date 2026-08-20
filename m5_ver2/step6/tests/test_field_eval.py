"""field_eval.py's pure decisions. No ROS graph, no Gazebo."""
import math

import field_eval

MAXR = 8.0


def test_min_range_reads_a_beyond_range_non_return_as_the_horizon():
    # gz reports a no-return as +inf: clear to range_max, a measurement
    # (LL-amr-agent-008). Naive min() on [inf, inf] gives inf, which
    # compares uselessly against a threshold.
    assert field_eval.min_range([math.inf, math.inf], MAXR) == MAXR
    assert field_eval.min_range([math.inf, 2.0], MAXR) == 2.0


def test_min_range_reads_below_minimum_and_invalid_as_violations():
    # -inf is gz's below-range_min code: something touches the device -
    # observed in the 2026-08-12 self-view audit, NOT hypothetical. nan is
    # no measurement at all. Neither is proof of clear space, and before
    # this rule both fell through to range_max - a hand on the scanner
    # window read as an open field.
    assert field_eval.min_range([-math.inf, 3.0], MAXR) == 0.0
    assert field_eval.min_range([math.nan, 3.0], MAXR) == 0.0
    assert field_eval.min_range([math.inf, 2.0, math.nan], MAXR) == 0.0


def test_min_range_of_an_empty_scan_is_a_violation_not_a_clear_horizon():
    # No samples at all is a broken device, not an empty room.
    assert field_eval.min_range([], MAXR) == 0.0


def test_min_range_clamps_above_the_maximum():
    assert field_eval.min_range([99.0], MAXR) == MAXR


def test_fields_for_case_matches_the_debug_script():
    assert field_eval.fields_for_case(1) == (1.0, 2.5)
    assert field_eval.fields_for_case(2) == (2.2, 3.7)
    assert field_eval.fields_for_case(3) == (4.5, 6.0)


def test_an_unreadable_case_selects_the_largest_field():
    # microscan3.py:16 and :22 - unknown means assume the most demanding.
    for bad in (0, 4, None, "2", -1):
        assert field_eval.fields_for_case(bad) == (4.5, 6.0)


def test_a_clear_field_needs_no_debounce_to_stay_clear():
    clear, cnt = field_eval.field_step(5.0, True, 0, 2.5)
    assert clear is True and cnt == 0


def test_an_intrusion_takes_three_consecutive_scans():
    clear, cnt = True, 0
    for expected_cnt in (1, 2):
        clear, cnt = field_eval.field_step(1.0, clear, cnt, 2.5)
        assert clear is True and cnt == expected_cnt
    clear, cnt = field_eval.field_step(1.0, clear, cnt, 2.5)
    assert clear is False and cnt == 0


def test_a_single_bad_scan_does_not_trip_the_field():
    clear, cnt = field_eval.field_step(1.0, True, 0, 2.5)
    assert clear is True and cnt == 1
    clear, cnt = field_eval.field_step(5.0, clear, cnt, 2.5)
    assert clear is True and cnt == 0


def test_re_clearing_needs_the_extra_hysteresis_margin():
    # Violated at 2.5; 2.6 is past the threshold but inside the +0.2 band,
    # so it must NOT re-clear.
    clear, cnt = False, 0
    for _ in range(5):
        clear, cnt = field_eval.field_step(2.6, clear, cnt, 2.5)
    assert clear is False
    for _ in range(3):
        clear, cnt = field_eval.field_step(2.8, clear, cnt, 2.5)
    assert clear is True


def test_level_ranks_protective_above_warning():
    assert field_eval.level(True, True) == "SAFE"
    assert field_eval.level(True, False) == "WARNING"
    assert field_eval.level(False, True) == "PROTECTIVE"
    assert field_eval.level(False, False) == "PROTECTIVE"


def test_muted_rays_are_dropped_before_the_minimum():
    # One ray grazing the mast would otherwise hold the device in
    # PROTECTIVE for ever. Index 1 is muted, so 5.0 wins over 0.11.
    assert field_eval.min_range([9.0, 0.11, 5.0], MAXR, ((1, 1),)) == 5.0


def test_muting_does_not_hide_a_real_return_outside_the_sector():
    assert field_eval.min_range([9.0, 0.11, 0.9], MAXR, ((1, 1),)) == 0.9


def test_an_entirely_muted_scan_is_a_violation():
    # Nothing was actually looked at, so it is not a clear horizon.
    assert field_eval.min_range([9.0, 9.0], MAXR, ((0, 1),)) == 0.0


def test_the_mute_table_covers_every_sensor():
    for name in field_eval.SENSORS:
        assert name in field_eval.SELF_MUTE


def test_a_muted_below_minimum_return_is_not_a_violation():
    # The machine's own contour may sit closer than range_min (the drive
    # wheel does). Muting must drop the ray BEFORE the -inf class check,
    # or the vehicle would trip on itself for ever.
    assert field_eval.min_range(
        [-math.inf, 5.0], MAXR, ((0, 0),)) == 5.0


def test_back_mute_covers_the_measured_steer_sweep():
    # The 2026-08-12 audit: across steer -1.31..+1.31 rad the steer yoke
    # and drive wheel return at idx 0..5 and 269..274 (0.10..0.15 m). The
    # first mute table, measured at steer 0 only, ended at idx 4/started
    # at 270 - and the first steering input latched PROTECTIVE in empty
    # space. Every measured self-return index must be muted, with the
    # two-ray margin on top.
    measured = list(range(0, 6)) + list(range(269, 275))
    scan = [math.inf] * 275
    for i in measured:
        scan[i] = 0.12
    assert field_eval.min_range(
        scan, MAXR, field_eval.SELF_MUTE["back"]) == MAXR
