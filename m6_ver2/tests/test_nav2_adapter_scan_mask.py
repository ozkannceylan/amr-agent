"""scan_mask.py - the truck's own mast, taken out of the scan.

WHY THIS FILTER EXISTS AT ALL. The ver2-lineage nav lidar sees its own
mast uprights: probed live 2026-08-13, the near upright at -3..-6 deg
and 1.287-1.292 m and the far one at -26..-29 deg and 1.447-1.483 m,
both body-fixed. follower.sector_min already skips them for the SPEED
guard. AMCL and the two costmaps do not: a return at 1.29 m that travels
with the vehicle marks occupied cells ON the robot, under its own
footprint, and SmacPlannerHybrid then refuses every plan with
ComputePathToPose 205 START_OCCUPIED. Real nav scanners ship the same
feature and call it contour masking.

THE PIN IS THE CROSS-CHECK AND NOT A RESTATEMENT. Masking the scan and
then reading it with NO mask has to give the same answer as reading the
raw scan WITH the mask - follower.sector_min is the second reader, and
it is the one that has been right since M6.
"""
import math

import pytest

import follower

import scan_mask


ANGLE_MIN = -math.pi
ANGLE_INC = math.radians(1.0)
N = 360


def _scan(default=8.0):
    return [default] * N


def _index_at_offset(offset_deg):
    """The ray whose body bearing (offset from the fork ray) is this."""
    angle = follower.norm_ang(math.radians(offset_deg) + math.pi)
    return int(round((angle - ANGLE_MIN) / ANGLE_INC)) % N


# ----------------------------------------------------------------------
# what gets masked
# ----------------------------------------------------------------------

def test_the_near_upright_is_the_truck_and_not_the_world():
    ranges = _scan()
    ranges[_index_at_offset(-5.0)] = 1.290
    out = scan_mask.mask_ranges(ranges, ANGLE_MIN, ANGLE_INC)
    assert out.ranges[_index_at_offset(-5.0)] == math.inf
    assert out.n_masked == 1


def test_the_far_upright_is_the_truck_too():
    ranges = _scan()
    ranges[_index_at_offset(-27.0)] = 1.470
    out = scan_mask.mask_ranges(ranges, ANGLE_MIN, ANGLE_INC)
    assert out.ranges[_index_at_offset(-27.0)] == math.inf
    assert out.n_masked == 1


def test_something_beyond_the_windows_ceiling_is_the_world():
    # THE COST, STATED, IS BOUNDED BY THE CEILING. A return inside a
    # window but further away than the mast can be is a real body.
    ranges = _scan()
    ranges[_index_at_offset(-5.0)] = 3.400
    out = scan_mask.mask_ranges(ranges, ANGLE_MIN, ANGLE_INC)
    assert out.ranges[_index_at_offset(-5.0)] == 3.400
    assert out.n_masked == 0


def test_a_close_body_outside_the_windows_survives():
    ranges = _scan()
    ranges[_index_at_offset(0.0)] = 1.290      # dead astern of the mast
    ranges[_index_at_offset(-15.0)] = 1.300    # between the two uprights
    out = scan_mask.mask_ranges(ranges, ANGLE_MIN, ANGLE_INC)
    assert out.n_masked == 0
    assert out.ranges[_index_at_offset(0.0)] == 1.290
    assert out.ranges[_index_at_offset(-15.0)] == 1.300


def test_a_clear_scan_comes_back_unchanged_and_is_a_copy():
    ranges = _scan()
    out = scan_mask.mask_ranges(ranges, ANGLE_MIN, ANGLE_INC)
    assert out.ranges == ranges
    assert out.ranges is not ranges
    assert out.n_masked == 0


def test_the_invalid_returns_are_left_exactly_as_they_arrived():
    ranges = _scan()
    ranges[10] = math.inf
    ranges[11] = float("nan")
    out = scan_mask.mask_ranges(ranges, ANGLE_MIN, ANGLE_INC)
    assert out.ranges[10] == math.inf
    assert math.isnan(out.ranges[11])
    assert out.n_masked == 0


def test_an_empty_mask_masks_nothing():
    ranges = _scan()
    ranges[_index_at_offset(-5.0)] = 1.290
    out = scan_mask.mask_ranges(ranges, ANGLE_MIN, ANGLE_INC, self_mask=())
    assert out.n_masked == 0


# ----------------------------------------------------------------------
# the cross-pin against the reader that already gets this right
# ----------------------------------------------------------------------

def test_masking_the_scan_equals_masking_the_reader():
    ranges = _scan()
    ranges[_index_at_offset(-5.0)] = 1.290
    ranges[_index_at_offset(-27.0)] = 1.470
    ranges[_index_at_offset(-15.0)] = 2.500     # a real body, kept
    masked = scan_mask.mask_ranges(ranges, ANGLE_MIN, ANGLE_INC).ranges
    with_mask = follower.sector_min(ranges, ANGLE_MIN, ANGLE_INC, 0.05, 25.0)
    without = follower.sector_min(masked, ANGLE_MIN, ANGLE_INC, 0.05, 25.0,
                                  self_mask=())
    assert with_mask == without == 2.500


def test_the_geometry_is_followers_own_constant():
    assert scan_mask.SELF_MASK is follower.SELF_MASK
    assert scan_mask.SELF_MASK == ((-9.0, -1.0, 1.6), (-31.0, -23.0, 1.7))


def test_the_mast_returns_the_windows_were_cut_for_are_all_inside_them():
    # The four probed bearings and their measured ranges. If a window is
    # ever narrowed, this is what notices.
    for offset_deg, r in ((-3.0, 1.287), (-6.0, 1.292),
                          (-26.0, 1.447), (-29.0, 1.483)):
        ranges = _scan()
        ranges[_index_at_offset(offset_deg)] = r
        assert scan_mask.mask_ranges(
            ranges, ANGLE_MIN, ANGLE_INC).n_masked == 1


# ----------------------------------------------------------------------
# refusals
# ----------------------------------------------------------------------

def test_a_zero_angle_increment_is_refused_by_name():
    with pytest.raises(scan_mask.Nav2ScanError) as caught:
        scan_mask.mask_ranges(_scan(), ANGLE_MIN, 0.0)
    assert "angle_increment" in str(caught.value)


def test_a_non_finite_angle_is_refused_by_name():
    with pytest.raises(scan_mask.Nav2ScanError):
        scan_mask.mask_ranges(_scan(), float("nan"), ANGLE_INC)


def test_a_malformed_window_is_refused_by_name():
    with pytest.raises(scan_mask.Nav2ScanError) as caught:
        scan_mask.mask_ranges(_scan(), ANGLE_MIN, ANGLE_INC,
                              self_mask=((1.0, -1.0, 1.6),))
    assert "lo" in str(caught.value)


def test_an_empty_scan_is_an_empty_scan():
    out = scan_mask.mask_ranges([], ANGLE_MIN, ANGLE_INC)
    assert out.ranges == [] and out.n_masked == 0


# ----------------------------------------------------------------------
# the selftest
# ----------------------------------------------------------------------

def test_the_selftest_is_green():
    assert scan_mask._selftest() == 0
