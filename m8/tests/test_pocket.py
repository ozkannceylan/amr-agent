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


# --------------------------------------------- step 3: the occluder-aware share
# `EVIDENCE_M8_E3_WORDS.md` step 3 was gated on a plant-measured step 2
# and left NOT DONE. Step 2 is measured (`e3-20260912-184020`,
# `e3-20260912-190415`). What the measurement then showed, and what
# these tests defend:
#
# The share gate asks whether the fitted face is a large share of what
# was fitted. When the truck's own tines reach toward the pallet the
# seed mode is still THE FACE - measured on the rendered close poses,
# the face bin holds 109 of 850 candidate points at 1.0 m while the
# tines spread a ramp of 635 across every bin in front of it. The face
# is not a small share of what could have been the face; it is a small
# share of A DIFFERENT SURFACE STANDING IN FRONT OF IT. A point nearer
# than the seed band was never a candidate for being part of the seeded
# plane, so it is not in the denominator that judges it.
#
# The same points also walked the TRIM off the face: at 0.90 m and
# closer the three trim passes reached into the tine ramp and the plane
# tilted until it read `candidate_falls_away_like_a_floor`, which the
# word policy treats as evidence of an empty bay.
#
# NO THRESHOLD MOVES. The occluder is "nearer than the seed band", and
# `FACE_SEED_BAND_M` is the band that already defines what the seeded
# surface is.
def _fit_trace(frame, self_mask=None):
    trace = {}
    seg = pocket.segment(frame, trace=trace, self_mask=self_mask)
    return seg, trace


def test_the_forks_leave_the_share_denominator_and_the_face_is_found():
    """The tines are in front of the face, so they do not judge it."""
    frame, _scene = scenes.forks(1.0)
    seg, trace = _fit_trace(frame)
    assert trace["occluder_points"] > 0
    assert trace["share_denominator"] < trace["after_deck_cut"]
    assert seg is not None, trace.get("refused")
    assert trace["inlier_frac"] > 0.9


@pytest.mark.parametrize("distance", [0.9, 0.8, 0.711])
def test_inside_the_tines_reach_the_occluder_rule_runs_out(distance):
    """Where step 3 stops, measured, and what has to take over.

    An occluder is something IN FRONT of the face, and the rule finds
    one here - 347 to 550 points of the blob leave the denominator. It
    is not enough. Closer than about 0.90 m the tines are no longer only
    in front of the pallet: they are INSIDE it, which is the whole point
    of a fork, and the part of a tine near its tip sits at the FACE'S
    OWN horizontal distance, inside the seed band. Removing what is in
    front leaves that part behind, the three trim passes reach it, the
    plane tilts, and the candidate reads
    `candidate_falls_away_like_a_floor`.

    This is not a gap to widen the occluder rule into - widening the
    band is how a geometry constant stops meaning what it says. It is
    what `selfmask.tine_footprint` is for: LATERAL is the one thing that
    still separates a tine from a pallet at this range, and the two
    lateral bands are bolted to the truck.
    """
    frame, _scene = scenes.forks(distance)
    seg, trace = _fit_trace(frame)
    assert trace["occluder_points"] > 0
    assert seg is None
    assert trace["refused"] == "candidate_falls_away_like_a_floor"


def test_an_empty_bay_has_nothing_in_front_and_keeps_its_denominator():
    """The discriminator is physical, not fitted.

    With the bay empty the tines are the nearest thing in the frame and
    the seed mode lands on their near end, so there is nothing in front
    of the seed at all and the denominator is untouched. That is why
    `forks_empty_bay` keeps saying `pallet_absent` while `forks` stops:
    the difference between them is whether anything stands BEHIND the
    obstruction, and the frame answers that on its own.
    """
    frame, _scene = scenes.forks_empty_bay(0.8)
    _seg, trace = _fit_trace(frame)
    assert trace["occluder_points"] == 0
    assert trace["share_denominator"] == trace["after_deck_cut"]


def test_the_occluder_is_kept_when_too_little_would_be_left():
    """Removing points is only allowed while a fit still has a face.

    A candidate whose seeded surface is thinner than `MIN_FACE_POINTS`
    once the occluder is gone is not a face measured behind an occluder;
    it is too little to measure, and the gates that said so before must
    still be the ones that say so. This is a guard, not a regime: no
    fixture here trips it, and the denominator never drops below the
    bar the final inlier set is held to.
    """
    for frame, _scene in (scenes.clean(scenes.STAGING_M),
                          scenes.clean(scenes.CLOSE_M),
                          scenes.forks(0.8),
                          scenes.forks_empty_bay(0.8)):
        _seg, trace = _fit_trace(frame)
        assert trace["share_denominator"] >= pocket.MIN_FACE_POINTS


def test_an_occluder_inside_the_seed_band_is_not_removed():
    """Open item 2 stays open, and this test is what keeps it honest.

    `EVIDENCE_M8_E3_WORDS.md` open item 2 established the cause of
    `blocked_by_box` reading `pallet_absent`: the staged box stands
    0.06 m in front of the face and `FACE_SEED_BAND_M` is 0.06 m, so the
    box is inside the seed band by one millimetre of margin. The
    occluder rule is defined BY that band - nearer than the seed band -
    so it does not reach the box, and this frame is refused exactly as
    it was before. Widening the rule to catch it would be tuning a
    geometry constant onto a staged fault; the fix named in that file is
    a threshold move and it is still out of scope.
    """
    frame, _scene = scenes.blocked_by_box(scenes.CLOSE_M)
    seg, trace = _fit_trace(frame)
    # The box's own near edge does poke past the band - 10 points of
    # 296 - and removing them changes nothing, because the surface that
    # tilts the fit is the part of the box INSIDE the band.
    assert trace["occluder_points"] < 0.05 * trace["after_deck_cut"]
    assert seg is None
    assert trace["refused"] == "candidate_falls_away_like_a_floor"


# ------------------------------------------- the floor, and what it is not
# `e3-20260918-141014`, plant static grid, teleported poses, `clean`
# against `pallet_absent` at the same four poses:
#
#     pose     clean dz/dy   empty bay dz/dy
#     1.00 m      -3.723         -3.797
#     0.90 m      -3.553         -3.790
#     0.80 m      -2.599         -3.789
#     0.70 m      -2.334         -3.783
#
# With the bay empty the fit reads this rig's floor at -3.8 at every
# pose. With a pallet in it, from 0.90 m in, the pallet's own deck top
# drags the majority fit up onto itself. Every height in this module is
# a residual against that plane, so `clean` false aborts at the 0.80 m
# pose were 20 of 20.
#
# The renderer does NOT reproduce that drift - it read -3.79 at every
# one of those poses - so these tests pin the INVARIANT rather than the
# regime. The plant is the score and `EVIDENCE_M8_E3_FLOOR.md` is where
# the regime is measured.
@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M,
                                      scenes.CLOSE_M, 0.9, 0.8, 0.7])
def test_the_pallet_does_not_become_the_floor(distance):
    """The plane a full bay fits is the plane an empty one fits."""
    full, _s = scenes.clean(distance)
    empty, _s2 = scenes.absent(distance)
    a = pocket.dominant_plane(full)
    b = pocket.dominant_plane(empty)
    assert a is not None and b is not None
    # Same surface, measured two ways: the tilt down the image and the
    # depth on the optical axis. Nothing here is a literal off the rig.
    assert abs(a.dz_dy(0.0, 0.0) - b.dz_dy(0.0, 0.0)) < 0.1
    assert abs(a.depth_at(0.0, 0.0) - b.depth_at(0.0, 0.0)) < 0.05
    assert a.dz_dy(0.0, 0.0) < pocket.FACE_MIN_DZ_DY


def test_a_bigger_nearer_surface_does_not_become_the_floor():
    """The floor is the farthest surface, not the biggest one.

    Two fronto-parallel surfaces, the near one holding 60 % of the
    pixels. Nothing stands behind a floor, so the far one is the
    ground and the near one is an object on it - whichever has more
    pixels, because pixels are an accident of range.
    """
    w, h = 64, 48
    near = pocket.make_plane_depth(w, h, 1.0)
    depths = list(near.depths)
    for v in range(0, int(0.4 * h)):
        for u in range(w):
            depths[v * w + u] = 2.0
    frame = pocket.DepthFrame(w, h, tuple(depths), near.fx, near.fy,
                              near.cx, near.cy, "two_surfaces", 1.0)
    plane = pocket.dominant_plane(frame)
    assert plane is not None
    assert abs(plane.depth_at(0.0, 0.0) - 2.0) < 0.05


def test_one_surface_is_still_that_surface():
    """A frame with nothing behind anything does not move."""
    frame = pocket.make_plane_depth(64, 48, 1.4)
    plane = pocket.dominant_plane(frame)
    assert plane is not None
    assert abs(plane.depth_at(0.0, 0.0) - 1.4) < 0.01
    assert plane.n > 0.5 * 64 * 48
