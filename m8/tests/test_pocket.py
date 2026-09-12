"""Classical C1 pocket pose on synthetic depth. No ROS, no Gazebo.

The scenes here carry a floor. That is the whole point: the A1 suite
was green on floorless fixtures while `EVIDENCE_M8_E1.md` measured C1
fitting the floor at every range on the plant.
"""
import math

import pytest
import scenes

from m8_core.contract import KIND_DOCK_TARGET_REFINE, validate_proposal
from m8_core import pocket
from m8_core.pocket import (
    DepthFrame,
    _least_squares_plane,
    dominant_plane,
    make_plane_depth,
    observe,
    propose,
)


def _estimate(frame, obs):
    """What the bench reads out of an observation: (lateral, range)."""
    return (obs.pocket_u - frame.cx) / frame.fx * obs.face_z, obs.face_z


# ------------------------------------------------------- the baseline defect
def test_a1s_fixed_band_and_depth_model_still_land_on_the_floor():
    """The defect E1 measured, locked in an offline fixture.

    A1 fitted ``z = a x + b y + c`` over a fixed central band. Refit it
    here on a plant-faithful frame and two things hold at once: the
    vertical slope comes out steeply negative, which is the floor and
    not a pallet face, and the model's own residual is enormous, because
    a plane is not a straight line in depth. That second number is why
    the intercept could not be trusted even when it happened to land
    near the pallet - it is a fitted constant of a model that does not
    describe the surface. Neither is fixable by moving a threshold.
    """
    frame, _scene = scenes.clean(scenes.STAGING_M)
    v0, v1 = frame.height // 4, (3 * frame.height) // 4
    u0, u1 = frame.width // 6, (5 * frame.width) // 6
    pts = []
    for v in range(v0, v1):
        for u in range(u0, u1):
            z = frame.at(u, v)
            if z is not None:
                pts.append((frame.x_of(u), frame.y_of(v), z))
    a, b, c, n = _least_squares_plane(pts)
    assert b < -2.0, "A1's band is not the floor in this fixture"
    rms = math.sqrt(sum((z - (a * x + b * y + c)) ** 2
                        for x, y, z in pts) / n)
    assert rms > 0.30, "A1's depth model fits this floor after all"


def test_the_floor_is_still_the_dominant_plane_and_is_now_used():
    """The fix does not make the floor go away - it anchors on it."""
    frame, _scene = scenes.clean(scenes.STAGING_M)
    floor = dominant_plane(frame)
    assert floor is not None
    assert floor.dz_dy(0.0, 0.0) < -2.0          # falls away downward
    assert floor.depth_at(0.0, 0.0) == pytest.approx(2.20, abs=0.10)


# -------------------------------------------------------------- the bar
@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M,
                                      scenes.CLOSE_M])
def test_c1_meets_the_tag_bar_at_every_range_e1_scored(distance):
    frame, scene = scenes.clean(distance)
    obs = observe(frame)
    assert obs is not None, "no pose at {} m".format(distance)
    lat, rng = _estimate(frame, obs)
    truth = scene.pocket_centre()
    err = math.hypot(lat - truth[0], rng - truth[2])
    assert err < scenes.TAG_BAR_M, "{:.4f} m vs bar {}".format(
        err, scenes.TAG_BAR_M)


@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M,
                                      scenes.CLOSE_M])
def test_the_derived_roi_is_the_pallet_and_not_the_band(distance):
    frame, _scene = scenes.clean(distance)
    obs = observe(frame)
    assert obs is not None
    assert obs.floor_found
    assert obs.face_width_m == pytest.approx(1.20, abs=0.15)
    assert obs.pocket_span_m == pytest.approx(0.56, abs=0.06)
    # The ROI moves with the pallet; A1's fixed rows never did.
    assert obs.roi_v1 - obs.roi_v0 < frame.height // 3


# ------------------------------------------------------------------ yaw
@pytest.mark.parametrize("yaw", [-0.10, 0.0, 0.10])
def test_c1_reports_a_real_yaw_not_a_slope_proxy(yaw):
    frame, _scene = scenes.rotated(yaw)
    obs = observe(frame)
    assert obs is not None
    assert obs.face_yaw == pytest.approx(yaw, abs=0.02)
    if yaw != 0.0:
        # A1's atan(dz/dx) is the yaw times D/cos^2(mount pitch); on
        # this rig that is about a factor of two. Hold the difference so
        # nobody quietly puts the proxy back.
        assert abs(math.atan(obs.face_a) - yaw) > 0.05


def test_a_tilted_face_reports_dtheta():
    frame, _scene = scenes.rotated(0.10)
    proposal = propose(frame)
    assert proposal is not None
    assert abs(proposal.pose_delta().dtheta) > 0.05


# ------------------------------------------------------------- refusals
def test_a_floor_only_frame_yields_no_pose():
    frame, _scene = scenes.absent()
    assert observe(frame) is None
    assert propose(frame) is None


def test_a_face_with_no_pockets_yields_no_pose():
    frame, _scene = scenes.no_pockets()
    assert observe(frame) is None


def test_an_empty_or_tiny_frame_yields_nothing():
    bad = DepthFrame(8, 8, tuple([float("nan")] * 64), frame_id="x",
                     sim_stamp=1.0)
    assert propose(bad) is None
    empty = make_plane_depth(8, 8, float("nan"))
    assert observe(empty) is None or propose(empty) is None


# ------------------------------------------------------------- the wire
def test_a_clean_pallet_yields_a_valid_refine():
    frame, _scene = scenes.clean()
    proposal = propose(frame)
    assert proposal is not None
    validate_proposal(proposal)
    assert proposal.kind == KIND_DOCK_TARGET_REFINE
    assert proposal.evidence.sensor_name == "pallet_cam"
    assert 0.0 < proposal.confidence <= 1.0
    assert proposal.extra["algorithm"] == "classical_floor_anchored_face"


def test_tag_target_shifts_the_delta():
    frame, _scene = scenes.clean()
    a = propose(frame, tag_u=frame.cx, tag_z=1.50)
    b = propose(frame, tag_u=frame.cx + 8.0, tag_z=1.50)
    assert a is not None and b is not None
    assert a.pose_delta().dy != b.pose_delta().dy
    assert math.isfinite(a.pose_delta().hypot_xy())


# ------------------------------------------------- the range window (C1)
def test_the_dock_envelope_alone_refuses_a_pallet_that_is_too_far():
    """Tagless docking gets the window and nothing else."""
    frame, _scene = scenes.far(4.5)
    assert observe(frame) is None


def test_a_tag_can_narrow_the_window_and_can_never_widen_it():
    lo, hi = pocket.DOCK_ENVELOPE_M
    assert pocket.range_window() == (lo, hi)
    near = pocket.range_window(1.5)
    assert lo <= near[0] < near[1] <= hi
    assert near[1] - near[0] < hi - lo
    # A tag claiming the pallet is 10 m away cannot reach past the
    # envelope, so it cannot rescue the frame above either.
    assert pocket.range_window(10.0)[1] <= hi
    assert pocket.range_window(0.0)[0] >= lo
    far_frame, _scene = scenes.far(4.5)
    assert observe(far_frame, expected_range=4.5) is None


def test_a_wrong_expected_range_refuses_rather_than_guessing():
    frame, scene = scenes.clean(scenes.APPROACH_M)
    assert observe(frame, expected_range=1.5) is not None
    # A tag reading a metre out puts the pallet outside the window.
    assert observe(frame, expected_range=2.6) is None
    del scene


def test_the_tag_pixel_chooses_between_two_pallets():
    frame, left, right = scenes.two_pallets()
    for scene in (left, right):
        u, v = scenes.px_of(frame, scene)
        obs = observe(frame, tag_u=u, tag_v=v)
        assert obs is not None
        lat = (obs.pocket_u - frame.cx) / frame.fx * obs.face_z
        assert lat == pytest.approx(scene.pocket_centre()[0], abs=0.05)
    # Tagless the frame still yields a pallet, just not a chosen one.
    assert observe(frame) is not None


@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M,
                                      scenes.CLOSE_M])
def test_the_face_is_a_large_share_of_what_was_fitted(distance):
    """E1's failure regime was the face being 2.9-6.6 % of the fit."""
    frame, _scene = scenes.clean(distance)
    obs = observe(frame)
    assert obs is not None
    assert obs.inlier_frac >= pocket.FACE_INLIER_FRAC_MIN
    assert obs.inlier_frac > 0.20, "back in E1's failure regime"
