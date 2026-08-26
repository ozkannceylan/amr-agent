#!/usr/bin/env python3
"""test_localization_core.py - the arithmetic behind every ABSOLUTE figure
in EVIDENCE_LOCALIZATION_V3.md, checked without a simulator, without a
map on disk and without ROS.

    python -m pytest m5_ver3/tests/ -q

WHAT IS NEW HERE AND WHY IT NEEDS ITS OWN FILE. F2 scored an estimate in
the frame it was born in: the odom frame is the vehicle at spawn, and
tests/test_evidence_core.py locks that transform. F3 scores an ABSOLUTE
pose, and an absolute pose on this stack is THREE transforms deep -

    map -> odom      the localiser's, republished at the scan rate
    odom -> base     the EKF's, at 50 Hz
    world <- map     the committed registration, derived once and frozen

- so a figure in EVIDENCE_LOCALIZATION_V3.md is wrong if ANY of the three
is composed the wrong way round, and two of the three are near a half
turn on this vehicle. That is the failure class this file exists for.

THE HALF TURN IS THE TRAP, AND IT IS THE TRAP TWICE OVER. The vehicle
spawns at yaw pi and the map frame is the odom frame, so the committed
registration's theta is -179.813 deg: at a half turn a rotation is very
nearly its own inverse, so a sign error leaves EVERY MAGNITUDE EXACTLY
RIGHT and puts the answer on the wrong side of the origin. Every
transform test below is therefore run at a quarter turn as well, where
the sign is visible, and the composition tests use two DIFFERENT angles
so that an implementation which adds the yaws but forgets to rotate the
translation cannot pass.

NOTHING HERE READS A FILE. The registration is a dict built in the test,
the grids are rasterised by the test, and the trajectories are generated
from closed-form arithmetic. tools/map_register.py is the shell that puts
the real artifacts in front of this.
"""
import math

import pytest

import evidence_core
import map_core


TWO_PI = 2.0 * math.pi

#: The COMMITTED registration of m5_ver3/maps/warehouse_v3, copied here as
#: three numbers so that one test can exercise the real half turn without
#: this file learning how to open a map. It is a fixture and not an
#: assertion about the artifact: map_register.load_registration() is what
#: binds those numbers to that grid, and it does it by md5.
WAREHOUSE_V3 = {
    "theta_rad": -3.138328398,
    "t_x_m": -17.111857467,
    "t_y_m": 9.798692466,
    "residual_rms_m": 0.029052,
    "residual_max_m": 0.117891,
}


def _close(a, b, tol=1e-9):
    return abs(a - b) < tol


def _angle_close(a, b, tol=1e-9):
    return abs(evidence_core.normalise_angle(a - b)) < tol


# ----------------------------------------------------------------------
# MapFrame - world coordinates and map coordinates, one spelling
# ----------------------------------------------------------------------

def test_the_map_frame_round_trips_at_the_half_turn_this_map_actually_has():
    frame = evidence_core.MapFrame.from_registration(WAREHOUSE_V3)
    for x, y, yaw in ((-17.0, 10.0, math.pi), (0.0, 0.0, 0.0),
                      (12.5, -7.25, -1.9)):
        mx, my, myaw = frame.to_map(x, y, yaw)
        wx, wy, wyaw = frame.to_world(mx, my, myaw)
        assert _close(wx, x) and _close(wy, y)
        assert _angle_close(wyaw, yaw)


def test_the_map_frame_round_trips_at_a_quarter_turn_where_a_sign_shows():
    # THE HALF TURN CANNOT CATCH A REVERSED ROTATION and this is the
    # control that can: at +90 deg, R and R^T send a point to opposite
    # sides of the origin and the round trip is the only thing that
    # still closes.
    frame = evidence_core.MapFrame(math.pi / 2.0, 3.0, -4.0)
    mx, my, myaw = frame.to_map(2.0, 0.0, 0.0)
    # R(pi/2).(2,0) = (0,2), plus t = (3,-2)
    assert _close(mx, 3.0) and _close(my, -2.0)
    assert _angle_close(myaw, math.pi / 2.0)
    wx, wy, wyaw = frame.to_world(mx, my, myaw)
    assert _close(wx, 2.0) and _close(wy, 0.0) and _angle_close(wyaw, 0.0)


def test_the_committed_translation_carries_the_spawn_pose_onto_the_map_origin():
    # THE ONE NUMBER THAT SAYS THE REGISTRATION IS NOT NONSENSE. The map
    # frame IS the odom frame of the mapping run and that odom frame is
    # the vehicle at spawn, so the spawn pose has to land within a
    # fraction of a metre of the map's origin. EVIDENCE_MAP_V3.md 6.3
    # states the same thing from the other side (t is the spawn pose to
    # 0.11 m and 0.20 m).
    frame = evidence_core.MapFrame.from_registration(WAREHOUSE_V3)
    mx, my, myaw = frame.to_map(-17.0, 10.0, math.pi)
    assert math.hypot(mx, my) < 0.30
    assert abs(evidence_core.normalise_angle(myaw)) < 0.01


def test_a_map_frame_without_a_yaw_returns_two_numbers_and_not_three():
    # map_core.world_to_map/map_to_world have this contract and their own
    # callers depend on it; MapFrame is what they delegate to now, so the
    # contract is locked here.
    frame = evidence_core.MapFrame(0.3, 1.0, 2.0)
    assert len(frame.to_map(1.0, 1.0)) == 2
    assert len(frame.to_world(1.0, 1.0)) == 2
    assert len(frame.to_map(1.0, 1.0, 0.0)) == 3


def test_map_core_still_speaks_the_transform_through_the_one_spelling():
    # TWO COPIES OF A MECHANISM DRIFT THE WAY TWO COPIES OF A VALUE DO.
    # map_core's two functions are the older spelling and they are kept
    # (map_register.py and its 82 tests call them by name), but they now
    # delegate, so this asserts the two agree rather than that both are
    # right.
    frame = evidence_core.MapFrame.from_registration(WAREHOUSE_V3)
    for x, y, yaw in ((-17.0, 10.0, math.pi), (4.0, -11.0, 0.4)):
        assert map_core.world_to_map(WAREHOUSE_V3, x, y, yaw) == \
            frame.to_map(x, y, yaw)
        assert map_core.map_to_world(WAREHOUSE_V3, x, y, yaw) == \
            frame.to_world(x, y, yaw)


def test_a_registration_missing_a_number_is_refused_and_not_defaulted():
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.MapFrame.from_registration({"theta_rad": 0.0,
                                                  "t_x_m": 1.0})
    assert "t_y_m" in str(exc.value)


def test_the_instrument_floor_travels_with_the_frame():
    # EVERY ABSOLUTE FIGURE IS STATED BESIDE THE FLOOR IT SITS ON
    # (EVIDENCE_MAP_V3.md 6.4). The floor is a property of the
    # registration, so it is carried by the object that carries the
    # registration and not looked up again at each print site.
    frame = evidence_core.MapFrame.from_registration(WAREHOUSE_V3)
    assert _close(frame.residual_rms_m, 0.029052)
    assert _close(frame.residual_max_m, 0.117891)
    # And a frame built from three bare numbers has no floor rather than
    # a floor of zero, because "0.0 m" is a claim and "unknown" is not.
    assert evidence_core.MapFrame(0.0, 0.0, 0.0).residual_max_m is None


# ----------------------------------------------------------------------
# compose_se2 - map -> odom -> base_link
# ----------------------------------------------------------------------

def test_composing_with_the_identity_changes_nothing_either_way():
    identity = (0.0, 0.0, 0.0)
    pose = (1.5, -2.5, 0.7)
    assert evidence_core.compose_se2(identity, pose) == pose
    got = evidence_core.compose_se2(pose, identity)
    assert _close(got[0], pose[0]) and _close(got[1], pose[1])
    assert _angle_close(got[2], pose[2])


def test_the_parent_rotation_turns_the_child_translation():
    # THE FAILURE THIS CATCHES IS THE ONE THAT LOOKS RIGHT: adding the
    # two translations and adding the two yaws. That is composition with
    # the rotation left out, and it is EXACT whenever the parent's yaw is
    # zero - which it is on a stack whose odom frame has not drifted yet.
    parent = (0.0, 0.0, math.pi / 2.0)
    child = (2.0, 0.0, 0.0)
    x, y, yaw = evidence_core.compose_se2(parent, child)
    assert _close(x, 0.0) and _close(y, 2.0)
    assert _angle_close(yaw, math.pi / 2.0)


def test_composition_matches_the_matrix_product_at_two_different_angles():
    parent = (3.0, -1.0, 0.4)
    child = (-2.0, 0.5, -1.1)
    got = evidence_core.compose_se2(parent, child)
    c, s = math.cos(parent[2]), math.sin(parent[2])
    assert _close(got[0], parent[0] + c * child[0] - s * child[1])
    assert _close(got[1], parent[1] + s * child[0] + c * child[1])
    assert _angle_close(got[2], parent[2] + child[2])


def test_composing_a_pose_with_its_inverse_returns_the_origin():
    pose = (4.0, -3.0, 2.2)
    assert evidence_core.compose_se2(
        pose, evidence_core.invert_se2(pose)) == pytest.approx(
            (0.0, 0.0, 0.0), abs=1e-12)
    assert evidence_core.compose_se2(
        evidence_core.invert_se2(pose), pose) == pytest.approx(
            (0.0, 0.0, 0.0), abs=1e-12)


def test_the_composed_yaw_is_wrapped_and_not_allowed_to_run_away():
    got = evidence_core.compose_se2((0.0, 0.0, 3.0), (0.0, 0.0, 3.0))
    assert -math.pi <= got[2] <= math.pi
    assert _angle_close(got[2], 6.0 - TWO_PI)


# ----------------------------------------------------------------------
# compose_rows - the TF lookup a consumer would have made
# ----------------------------------------------------------------------

def _rows(times, pose_of):
    return [(t,) + tuple(pose_of(t)) for t in times]


def test_the_composed_stream_is_sampled_where_the_child_is_sampled():
    # THE CHILD IS THE 50 Hz EDGE AND THE PARENT IS THE 15 Hz ONE. A
    # consumer looking up map -> base_link gets an answer at whatever
    # rate it asks; the honest rate here is the FASTER edge's, because
    # that is the one that carries the vehicle's motion.
    parent = _rows([0.0, 1.0, 2.0], lambda t: (t, 0.0, 0.0))
    child = _rows([0.0, 0.25, 0.5, 0.75, 1.0], lambda t: (0.0, 0.0, 0.0))
    got = evidence_core.compose_rows(parent, child, 1.5)
    assert [row[0] for row in got] == [0.0, 0.25, 0.5, 0.75, 1.0]
    # the parent ramps 0 -> 1 over the second, linearly, which is what
    # tf2 itself would interpolate between two stamped transforms
    assert _close(got[2][1], 0.5)


def test_the_composed_stream_is_the_product_and_not_the_sum():
    parent = _rows([0.0, 1.0], lambda t: (0.0, 0.0, math.pi / 2.0))
    child = _rows([0.0, 1.0], lambda t: (2.0, 0.0, 0.0))
    got = evidence_core.compose_rows(parent, child, 1.5)
    for _, x, y, yaw in got:
        assert _close(x, 0.0) and _close(y, 2.0)
        assert _angle_close(yaw, math.pi / 2.0)


def test_a_parent_that_wrapped_is_interpolated_the_short_way_round():
    # THE MAP -> ODOM YAW SITS NEAR pi ON THIS VEHICLE FOR PART OF EVERY
    # RUN, and a resample of a wrapped series would sweep the estimate
    # the whole way round the circle between two samples 0.02 rad apart.
    parent = _rows([0.0, 1.0],
                   lambda t: (0.0, 0.0, math.pi - 0.01 if t == 0.0
                              else -math.pi + 0.01))
    child = _rows([0.5], lambda t: (0.0, 0.0, 0.0))
    got = evidence_core.compose_rows(parent, child, 1.5)
    assert abs(abs(got[0][3]) - math.pi) < 1e-9


def test_a_gap_in_the_parent_wider_than_the_bound_is_refused():
    parent = _rows([0.0, 5.0], lambda t: (0.0, 0.0, 0.0))
    child = _rows([2.5], lambda t: (0.0, 0.0, 0.0))
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.compose_rows(parent, child, 0.5)


def test_child_samples_outside_the_parent_span_are_dropped_and_not_invented():
    # The localiser joins the graph AFTER the filter does - map_server has
    # to load a 1712 x 1196 grid first - so the first second of every
    # session has an odom pose and no map pose. Those samples are not
    # scoreable and are dropped, which makes the run SHORTER rather than
    # WRONG (score_drift's own rule, applied one layer up).
    parent = _rows([1.0, 2.0], lambda t: (0.0, 0.0, 0.0))
    child = _rows([0.0, 0.5, 1.0, 1.5, 2.0, 2.5], lambda t: (0.0, 0.0, 0.0))
    got = evidence_core.compose_rows(parent, child, 1.5)
    assert [row[0] for row in got] == [1.0, 1.5, 2.0]


def test_a_composed_stream_with_nothing_in_it_is_refused_by_name():
    parent = _rows([10.0, 11.0], lambda t: (0.0, 0.0, 0.0))
    child = _rows([0.0, 1.0], lambda t: (0.0, 0.0, 0.0))
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.compose_rows(parent, child, 0.5)
    assert "overlap" in str(exc.value)


# ----------------------------------------------------------------------
# rows_to_world - the absolute estimate, in the building's own frame
# ----------------------------------------------------------------------

def test_a_map_frame_trajectory_comes_back_out_in_world_coordinates():
    frame = evidence_core.MapFrame.from_registration(WAREHOUSE_V3)
    world = [(0.0, -17.0, 10.0, math.pi), (1.0, -6.0, 10.0, math.pi)]
    in_map = [(t,) + frame.to_map(x, y, yaw) for t, x, y, yaw in world]
    back = evidence_core.rows_to_world(in_map, frame)
    for got, want in zip(back, world):
        assert _close(got[0], want[0])
        assert _close(got[1], want[1], 1e-9)
        assert _close(got[2], want[2], 1e-9)
        assert _angle_close(got[3], want[3])


def test_scoring_an_absolute_estimate_removes_no_initial_offset():
    # GLOBAL CONSTRAINT 5, ON THE ABSOLUTE LAYER. An estimate that is
    # 0.40 m out at its first sample and stays there has an error of
    # 0.40 m, and a score anchored to its own start would report zero.
    truth = [(float(i) * 0.1, float(i) * 0.1, 0.0, 0.0) for i in range(51)]
    est = [(t, x + 0.40, y, yaw) for t, x, y, yaw in truth]
    score = evidence_core.score_drift(truth, est,
                                      evidence_core.world_frame(), 0.5)
    assert _close(score.rms_m, 0.40, 1e-9)
    assert _close(score.end_error_m, 0.40, 1e-9)
    assert _close(score.max_error_m, 0.40, 1e-9)


def test_the_world_frame_is_the_identity_and_leaves_the_truth_alone():
    frame = evidence_core.world_frame()
    assert frame.apply(3.0, -4.0, 1.0) == pytest.approx((3.0, -4.0, 1.0))


def test_a_sheared_map_shows_up_in_the_absolute_score_and_is_not_absorbed():
    # THE REGISTRATION IS RIGID BY CONSTRUCTION AND THAT IS THE POINT
    # (EVIDENCE_MAP_V3.md 6.4): a grid whose metres are not the
    # building's cannot be made to fit by any rotation and translation,
    # so the mismatch lands in the FIGURE instead of being hidden in the
    # transform. Here the map is 1 % long in x - a shear of exactly the
    # kind the committed map has 0.265 deg of - and a localiser that is
    # PERFECT in that map is therefore wrong in the building by 1 % of x.
    frame = evidence_core.MapFrame(0.0, 0.0, 0.0)
    truth = [(float(i), float(i), 0.0, 0.0) for i in range(11)]
    stretched = [(t, x * 1.01, y, yaw) for t, x, y, yaw in truth]
    est = evidence_core.rows_to_world(stretched, frame)
    score = evidence_core.score_drift(truth, est,
                                      evidence_core.world_frame(), 0.5)
    assert _close(score.end_error_m, 0.10, 1e-9)
    assert score.rms_m > 0.0


# ----------------------------------------------------------------------
# tf_jumps - what a correction costs the consumer
# ----------------------------------------------------------------------

def test_a_transform_rebroadcast_unchanged_is_not_a_correction():
    # amcl re-sends map -> odom on EVERY scan whether or not the filter
    # updated (nav2_amcl laserReceived, the latest_tf_valid_ branch), so
    # a stream of 15 Hz samples over a run that corrected four times has
    # four corrections in it and hundreds of repeats. Counting the
    # repeats would report a jump rate of 15 Hz and a mean jump of zero.
    rows = [(0.1 * i, 1.0, 2.0, 0.3) for i in range(50)]
    jumps = evidence_core.tf_jumps(rows)
    assert jumps.n == 0
    assert jumps.samples == 50


def test_every_change_is_one_correction_and_its_size_is_the_step():
    rows = [(0.0, 0.0, 0.0, 0.0), (0.1, 0.0, 0.0, 0.0),
            (0.2, 0.3, 0.4, 0.0),          # 0.5 m
            (0.3, 0.3, 0.4, 0.0),
            (0.4, 0.3, 0.4, 0.25),         # 0.25 rad
            (0.5, 0.3, 0.4, 0.25)]
    jumps = evidence_core.tf_jumps(rows)
    assert jumps.n == 2
    assert _close(jumps.max_dpos_m, 0.5)
    assert _close(jumps.max_dyaw_rad, 0.25)
    assert _close(jumps.dpos.mean, 0.25)


def test_a_jump_across_the_wrap_is_measured_the_short_way():
    rows = [(0.0, 0.0, 0.0, math.pi - 0.05),
            (0.1, 0.0, 0.0, -math.pi + 0.05)]
    jumps = evidence_core.tf_jumps(rows)
    assert jumps.n == 1
    assert _close(jumps.max_dyaw_rad, 0.1, 1e-9)


def test_the_correction_rate_is_per_second_of_the_stream_it_was_measured_on():
    rows = [(0.0, 0.0, 0.0, 0.0), (1.0, 0.1, 0.0, 0.0),
            (2.0, 0.2, 0.0, 0.0), (4.0, 0.3, 0.0, 0.0)]
    jumps = evidence_core.tf_jumps(rows)
    assert jumps.n == 3
    assert _close(jumps.span_s, 4.0)
    assert _close(jumps.per_s, 0.75)


def test_a_stream_with_one_sample_has_no_jumps_and_says_so_without_raising():
    jumps = evidence_core.tf_jumps([(0.0, 0.0, 0.0, 0.0)])
    assert jumps.n == 0 and jumps.samples == 1
    assert jumps.dpos is None and jumps.per_s is None


def test_an_empty_transform_stream_is_refused_and_not_scored_as_still():
    # A LOCALISER THAT NEVER BROADCAST IS NOT A LOCALISER THAT NEVER
    # CORRECTED, and reporting "0 jumps" about it would be the second
    # thing read as the first.
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.tf_jumps([])


# ----------------------------------------------------------------------
# the bringup gate's two questions
# ----------------------------------------------------------------------

def test_the_worst_covariance_entry_is_the_largest_magnitude():
    # A diverged filter on this stack publishes 5.74e87 on the xx
    # diagonal and -5.08e91 off it; a gate reading entry 0 would read the
    # smaller of the two by four orders of magnitude.
    values = [5.74e87] + [0.0] * 6 + [-5.08e91] + [0.0] * 28
    assert evidence_core.worst_of(values) == 5.08e91


def test_an_empty_covariance_is_refused_and_not_scored_as_certain():
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.worst_of([])


def test_a_non_finite_covariance_is_refused_rather_than_compared():
    # A comparison against nan is false in both directions, so a ceiling
    # test written the obvious way round would PASS a blown-up filter.
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.worst_of([0.1, float("nan")])
    assert "finite" in str(exc.value)


def test_a_covariance_under_the_ceiling_returns_what_it_checked():
    assert evidence_core.require_worst_under(0.23, 1.0, "the localiser") \
        == 0.23


def test_a_covariance_over_the_ceiling_is_refused_by_name():
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.require_worst_under(192.0, 1.0, "the localiser")
    assert "the localiser" in str(exc.value)


def test_a_pose_near_its_seed_passes_and_returns_the_distance():
    got = evidence_core.require_pose_near(-0.10, -0.11, -0.08, -0.15,
                                          0.50, "amcl")
    assert _close(got, math.hypot(0.02, 0.04), 1e-12)


def test_a_localiser_answering_from_its_own_prior_is_refused():
    # THE FAILURE THE COVARIANCE CEILING CANNOT SEE. nav2_amcl's
    # untouched prior carries the same 0.25 m2 the bringup seeds with, so
    # a filter that never received the seed passes every covariance test
    # and sits at the map origin.
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.require_pose_near(0.0, 0.0, -12.0, 4.0, 0.50, "amcl")
    assert "seed" in str(exc.value)


def test_a_non_finite_pose_is_refused_rather_than_compared():
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.require_pose_near(float("nan"), 0.0, 0.0, 0.0,
                                        0.50, "amcl")


# ----------------------------------------------------------------------
# what the map has to say about a scan - sigma_hit and z_rand, derived
# ----------------------------------------------------------------------

def _grid_with_wall(width, height, col):
    """A grid whose only occupied cells are one vertical line."""
    pixels = bytearray([254] * (width * height))
    for row in range(height):
        pixels[row * width + col] = 0
    return map_core.Grid(width, height, 255, pixels)


_META = {"resolution": 0.05, "origin": (0.0, 0.0, 0.0),
         "occupied_thresh": 0.65, "free_thresh": 0.196, "negate": 0.0}


def test_the_distance_to_the_nearest_occupied_cell_is_euclidean():
    grid = _grid_with_wall(20, 20, 10)
    mask = map_core.occupied_mask(grid, _META)
    # column 10's centre is x = (10 + 0.5) * 0.05 = 0.525; row 9's is
    # y = (20 - 1 - 9 + 0.5) * 0.05 = 0.525. Standing three cells east of
    # that cell's centre, on its own row, the answer is exactly 0.15 m.
    got = map_core.nearest_occupied_distance(
        mask, grid.width, grid.height, _META, 0.525 + 0.15, 0.525, 6)
    assert _close(got, 0.15, 1e-9)


def test_a_point_with_nothing_near_it_returns_no_distance_at_all():
    # NOT A LARGE NUMBER. "Nothing within the search box" is a different
    # fact from "0.31 m away", and the caller counts the two separately -
    # one is the sensor's noise and the other is a surface the map does
    # not contain.
    grid = _grid_with_wall(200, 20, 10)
    mask = map_core.occupied_mask(grid, _META)
    assert map_core.nearest_occupied_distance(
        mask, grid.width, grid.height, _META, 5.0, 0.5, 6) is None


def test_a_point_off_the_grid_has_no_distance_and_does_not_raise():
    grid = _grid_with_wall(20, 20, 10)
    mask = map_core.occupied_mask(grid, _META)
    assert map_core.nearest_occupied_distance(
        mask, grid.width, grid.height, _META, -3.0, -3.0, 6) is None


#: Row 150's centre, so a beam driven along it lands ON a cell centre
#: and the only distance left in the answer is the one the test put
#: there. y = (200 - 1 - 150 + 0.5) * 0.05.
_ROW150_Y = 2.475
_WALL_X = (100 + 0.5) * 0.05


def test_a_scan_against_a_wall_it_matches_reports_the_range_error_and_no_more():
    # THE DERIVATION sigma_hit COMES FROM. `d` is the distance from a
    # beam's endpoint to the nearest occupied cell, and with the pose
    # right that distance IS the range error. Three beams: one exact, one
    # 0.05 m long, one 0.05 m short.
    grid = _grid_with_wall(200, 200, 100)
    mask = map_core.occupied_mask(grid, _META)
    pose = (_WALL_X - 2.0, _ROW150_Y, 0.0)
    got = map_core.scan_support(mask, grid.width, grid.height, _META, pose,
                                [2.0, 2.05, 1.95], [0.0, 0.0, 0.0],
                                0.05, 25.0, 6, grid)
    assert got.n_used == 3
    assert got.n_unexplained == 0
    assert _close(got.max_m, 0.05, 1e-9)
    assert _close(got.rms_m, math.sqrt(0.005 / 3.0), 1e-9)


def test_a_beam_that_lands_where_the_map_says_nothing_is_counted_as_unexplained():
    # THE DERIVATION z_rand COMES FROM, and the reason the missing south
    # wall matters: a return the map cannot explain is exactly what
    # nav2_amcl's likelihood field charges to z_rand.
    grid = _grid_with_wall(200, 200, 100)
    mask = map_core.occupied_mask(grid, _META)
    pose = (_WALL_X - 2.0, _ROW150_Y, 0.0)
    # four beams onto the wall, one stopping a metre short of it
    got = map_core.scan_support(mask, grid.width, grid.height, _META, pose,
                                [2.0, 2.0, 1.0, 2.0, 2.0], [0.0] * 5,
                                0.05, 25.0, 6, grid)
    assert got.n_used == 5
    assert got.n_unexplained == 1
    assert got.n_free == 1 and got.n_unknown == 0


def test_without_the_grid_the_count_is_still_made_and_the_split_is_not_invented():
    # THE SPLIT NEEDS THE GRID AND THE COUNT DOES NOT. A caller that has
    # only the occupied mask still learns how many returns the map
    # cannot explain; what it does not get is a fabricated guess at
    # whether they landed on free floor or on unmapped space.
    grid = _grid_with_wall(200, 200, 100)
    mask = map_core.occupied_mask(grid, _META)
    pose = (_WALL_X - 2.0, _ROW150_Y, 0.0)
    got = map_core.scan_support(mask, grid.width, grid.height, _META, pose,
                                [2.0, 1.0], [0.0, 0.0], 0.05, 25.0, 6)
    assert got.n_unexplained == 1
    assert got.n_free == 0 and got.n_unknown == 0 and got.n_off_grid == 0


def test_a_max_range_return_is_not_a_measurement_and_is_not_counted():
    # nav2_amcl's likelihood field skips them by name ("This model
    # ignores max range readings"), so an instrument that derives that
    # model's parameters has to skip them too or it would charge the
    # sensor's blind returns to the map.
    grid = _grid_with_wall(200, 200, 100)
    mask = map_core.occupied_mask(grid, _META)
    pose = ((100 + 0.5) * 0.05 - 2.0, 2.5, 0.0)
    got = map_core.scan_support(mask, grid.width, grid.height, _META, pose,
                               [2.0, 25.0, float("inf"), float("nan"), 0.01],
                               [0.0] * 5, 0.05, 25.0, 6)
    assert got.n_beams == 5
    assert got.n_used == 1
    assert got.n_range == 4


def test_the_scan_is_placed_by_the_pose_and_a_reversed_yaw_shows():
    # THE SAME HALF-TURN TRAP AS EVERY OTHER TRANSFORM HERE: at yaw pi
    # the beam that should have gone west goes east, and against a
    # one-wall map that is the difference between every beam explained
    # and every beam unexplained.
    grid = _grid_with_wall(200, 200, 100)
    mask = map_core.occupied_mask(grid, _META)
    wall_x = (100 + 0.5) * 0.05
    forward = map_core.scan_support(
        mask, grid.width, grid.height, _META, (wall_x + 2.0, 2.5, math.pi),
        [2.0], [0.0], 0.05, 25.0, 6)
    assert forward.n_unexplained == 0
    backward = map_core.scan_support(
        mask, grid.width, grid.height, _META, (wall_x + 2.0, 2.5, 0.0),
        [2.0], [0.0], 0.05, 25.0, 6)
    assert backward.n_unexplained == 1


def test_two_scans_add_up_and_the_totals_are_the_sum():
    grid = _grid_with_wall(200, 200, 100)
    mask = map_core.occupied_mask(grid, _META)
    pose = ((100 + 0.5) * 0.05 - 2.0, 2.5, 0.0)
    one = map_core.scan_support(mask, grid.width, grid.height, _META, pose,
                               [2.0, 1.0], [0.0, 0.0], 0.05, 25.0, 6)
    total = map_core.add_support(one, one)
    assert total.n_beams == 4 and total.n_used == 4
    assert total.n_unexplained == 2
    assert _close(total.rms_m, one.rms_m, 1e-9)


def test_a_support_total_with_no_explained_beam_has_no_rms_rather_than_zero():
    grid = _grid_with_wall(200, 200, 100)
    mask = map_core.occupied_mask(grid, _META)
    pose = ((100 + 0.5) * 0.05 - 2.0, 2.5, 0.0)
    got = map_core.scan_support(mask, grid.width, grid.height, _META, pose,
                               [1.0], [0.0], 0.05, 25.0, 6)
    assert got.n_explained == 0
    assert got.rms_m is None and got.max_m is None
