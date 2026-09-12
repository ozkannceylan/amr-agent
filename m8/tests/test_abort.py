"""Classical C2 abort classifier. Never proceed. No ROS.

`EVIDENCE_M8_E3.md` measured A1 aborting on 540 of 540 static frames,
90 of 90 of them clean, because it read the floor as the pallet face.
The first test below is the one that would have caught it offline.
"""
import pytest
import scenes

from m8_core.abort import (
    STRINGER_NEAR_FRAC,
    STRINGER_NEAR_M,
    classify,
    propose,
)
from m8_core.contract import ABORT_REASONS, KIND_DOCK_ABORT
from m8_core.pocket import (
    DepthFrame,
    blob_touches_border,
    fork_path_fraction,
    make_plane_depth,
    segment,
)


@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M,
                                      scenes.CLOSE_M])
def test_a_clean_pallet_is_not_an_abort_at_any_range(distance):
    frame, _scene = scenes.clean(distance)
    assert classify(frame) is None
    assert propose(frame) is None


def test_an_empty_bay_is_pallet_absent():
    frame, _scene = scenes.absent()
    assert classify(frame) == "pallet_absent"


def test_too_few_valid_pixels_is_pallet_absent():
    frame = DepthFrame(16, 12, tuple([float("nan")] * 192),
                       frame_id="x", sim_stamp=1.0)
    assert classify(frame) == "pallet_absent"


@pytest.mark.parametrize("yaw", [0.25, -0.25])
def test_a_yawed_pallet_is_pallet_rotated(yaw):
    frame, _scene = scenes.rotated(yaw)
    assert classify(frame) == "pallet_rotated"


def test_a_face_with_both_pockets_filled_is_pocket_blocked():
    frame, _scene = scenes.no_pockets()
    assert classify(frame) == "pocket_blocked"


@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M,
                                      scenes.CLOSE_M])
def test_a_bar_in_front_of_the_face_is_stringer_in_path(distance):
    """Including at 1.0 m, where the bar projects below the face rows.

    Searching only the face box read `none` here: a bar 0.08 m in front
    of the face is lower in the image than the face is, so at close
    range it leaves the face box entirely.
    """
    frame, _scene = scenes.stringer(distance)
    assert classify(frame) == "stringer_in_path"


def test_a_grossly_offset_pallet_is_pallet_shifted():
    frame, _scene = scenes.shifted(0.75)
    assert classify(frame) == "pallet_shifted"


def test_the_mount_offset_alone_is_not_a_shift():
    """The pallet camera sits 0.40 m off the centreline on this rig.

    A correctly staged pallet is therefore always off-axis, and calling
    that a shift is a false abort on every clean dock.
    """
    frame, scene = scenes.clean()
    assert scene.pocket_centre()[0] == pytest.approx(-0.40, abs=0.01)
    assert classify(frame) is None


def test_a_target_column_tightens_the_lateral_test():
    frame, _scene = scenes.clean()
    assert classify(frame) is None
    # Same frame, a target claimed far to the right: now it is a shift.
    assert classify(frame, target_u=frame.width - 1) == "pallet_shifted"


def test_proceed_is_never_returned():
    frames = [scenes.clean()[0], scenes.absent()[0], scenes.rotated(0.25)[0],
              scenes.no_pockets()[0], scenes.stringer()[0],
              DepthFrame(16, 12, tuple([float("nan")] * 192),
                         frame_id="x", sim_stamp=1.0)]
    for frame in frames:
        reason = classify(frame)
        if reason is not None:
            assert reason in ABORT_REASONS
            assert reason != "proceed"
            p = propose(frame)
            assert p.kind == KIND_DOCK_ABORT
            assert p.abort_reason() == reason


# ------------------------------------------- the fork path is floor-model
@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M,
                                      scenes.CLOSE_M])
def test_the_fork_path_test_reads_the_floor_and_not_an_intercept(distance):
    """A1 compared column depths with `c`, a plane intercept that was the
    floor's, so its stringer word fired on RANGE. The floor-model test
    separates clean from obstructed by a factor of four at every range.
    """
    clean_frame, _a = scenes.clean(distance)
    seg = segment(clean_frame)
    assert seg is not None
    assert fork_path_fraction(clean_frame, seg, STRINGER_NEAR_M) == 0.0

    bar_frame, _b = scenes.stringer(distance)
    bar_seg = segment(bar_frame)
    assert bar_seg is not None
    blocked = fork_path_fraction(bar_frame, bar_seg, STRINGER_NEAR_M)
    assert blocked > 4.0 * STRINGER_NEAR_FRAC


def test_a_solid_face_is_blocked_pockets_not_an_obstruction():
    """The deck top and a filled pocket are not things in the fork path."""
    frame, _scene = scenes.no_pockets()
    seg = segment(frame)
    assert seg is not None
    assert fork_path_fraction(frame, seg, STRINGER_NEAR_M) == 0.0
    assert classify(frame) == "pocket_blocked"


def test_a_frame_with_no_floor_model_claims_no_obstruction():
    """Without a floor there is nothing to measure heights against."""
    frame = make_plane_depth(48, 36, 1.20)
    seg = segment(frame)
    if seg is not None:
        assert seg.floor is None
        assert fork_path_fraction(frame, seg, STRINGER_NEAR_M) == 0.0


# ------------------------------------------- the word a refusal deserves
#
# `EVIDENCE_M8_C1C2_FIX.md` measured 0.884 live false-abort and named the
# cause: inside 1.2 m the truck's own forks are continuous with the
# pallet, C1 refuses, and the classifier had one word for "no face" -
# `pallet_absent`. The bay was not empty. These hold the word policy that
# replaced it. NO THRESHOLD MOVED; the tests above are the proof, since
# all five fault words are still said on the same frames.
def test_the_trucks_own_forks_are_not_an_empty_bay():
    """The 0.884 false-abort, reproduced offline and then removed.

    At 1.0 m the tines and the pallet are one standing object with no
    range discontinuity at the junction, so `segment` refuses with
    `face_is_too_small_a_share` - a refusal that says the face IS there,
    holding 23-25 % of the blob. Answering it with `pallet_absent` says
    the opposite of what the refusal found.
    """
    frame, _scene = scenes.forks(scenes.CLOSE_M)
    trace = {}
    assert segment(frame, trace=trace) is None
    assert trace["refusals"][0]["why"] == "face_is_too_small_a_share"
    assert classify(frame) is None


@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M])
def test_the_forks_do_not_hide_the_pallet_further_out(distance):
    """At 1.5 m and staging there is clean floor between them."""
    frame, _scene = scenes.forks(distance)
    assert segment(frame) is not None
    assert classify(frame) is None


@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M,
                                      scenes.CLOSE_M])
def test_an_empty_bay_is_still_absent_with_the_forks_in_view(distance):
    """The word policy must not buy silence with the empty bay.

    The tines stand above the floor at every pose, so they are candidate
    blobs at every pose. They are measured and they are not pallet-sized,
    which is exactly what an empty bay looks like.
    """
    frame, _scene = scenes.forks_empty_bay(distance)
    assert classify(frame) == "pallet_absent"


def test_a_pallet_running_off_the_image_supports_no_word_about_the_pallet():
    """Border -> None. A clipped object is measured on a part.

    Its width in metres is a lower bound, its plane is fitted to what is
    visible, and its pocket pair may be off-frame. A1's successor said
    `pocket_blocked` here, having found one run of pocket-deep columns
    instead of two - on a pallet that is not blocked at all.
    """
    frame, _scene = scenes.clipped()
    seg = segment(frame)
    assert seg is not None
    assert blob_touches_border(frame, seg.blob)
    assert classify(frame) is None


def test_clipping_does_not_silence_an_obstruction_that_is_in_view():
    """An obstruction seen INSIDE the visible region is still seen.

    Only the words that claim something about the WHOLE pallet - its
    yaw, its pocket pair, its lateral offset - are withheld.
    """
    frame, _scene = scenes.stringer(scenes.CLOSE_M)
    seg = segment(frame)
    assert seg is not None
    assert not blob_touches_border(frame, seg.blob)
    assert classify(frame) == "stringer_in_path"


def test_a_clipped_candidate_reading_too_narrow_is_not_evidence():
    """A half-visible pallet reads too narrow, for reasons about framing.

    `face_width_not_pallet_sized` at 0.30 m on an object at the edge of
    the image is a statement about the image, not about the bay.
    """
    from m8_core.abort import word_for_refusals
    frame, _scene = scenes.clean()
    edge = {"refusals": [{"why": "face_width_not_pallet_sized",
                          "blob": (0, 40, 10, 60), "standing": True,
                          "width_m": 0.30}]}
    inside = {"refusals": [{"why": "face_width_not_pallet_sized",
                            "blob": (40, 80, 10, 60), "standing": True,
                            "width_m": 0.30}]}
    assert word_for_refusals(frame, edge) is None
    assert word_for_refusals(frame, inside) == "pallet_absent"


def test_clipping_cannot_explain_an_object_that_read_too_big():
    """Clipping makes a thing read SMALLER. It never makes one read bigger.

    The plant's own finding 1 is this case: at staging the largest thing
    standing above the floor was a warehouse wall 1.3555 m tall, and a
    wall that runs off the top of the image is still too tall to be a
    pallet.
    """
    from m8_core.abort import word_for_refusals
    frame, _scene = scenes.clean()
    tall_and_clipped = {"refusals": [
        {"why": "face_height_not_pallet_sized", "blob": (0, 120, 0, 60),
         "standing": True, "height_m": 1.3555}]}
    assert word_for_refusals(frame, tall_and_clipped) == "pallet_absent"


def test_a_shape_test_survives_clipping_outright():
    """A floor seen through a letterbox is still a floor.

    This is not a size reading, so there is no lower bound for clipping
    to undermine. It is also the refusal the truck's own tines raise -
    they start under the camera and run to the bottom edge of EVERY
    frame - so a rule that discounted any clipped candidate would throw
    away most of what an empty bay has to offer.
    """
    from m8_core.abort import word_for_refusals
    frame, _scene = scenes.clean()
    trace = {"refusals": [{"why": "candidate_falls_away_like_a_floor",
                           "blob": (0, 320, 100, 240), "standing": True}]}
    assert word_for_refusals(frame, trace) == "pallet_absent"


def test_one_could_be_the_pallet_refusal_outvotes_any_number_of_others():
    """Seven candidates that are not pallets do not make the eighth absent."""
    from m8_core.abort import word_for_refusals
    frame, _scene = scenes.clean()
    trace = {"refusals": [
        {"why": "face_height_not_pallet_sized", "blob": (40, 80, 10, 60),
         "standing": True},
        {"why": "face_width_not_pallet_sized", "blob": (90, 130, 10, 60),
         "standing": True},
        {"why": "face_is_too_small_a_share", "blob": (140, 180, 10, 60),
         "standing": True},
    ]}
    assert word_for_refusals(frame, trace) is None


def test_a_refusal_name_nobody_classified_says_nothing():
    """The safe default for a word policy is silence.

    A gate added to `pocket` later must not start claiming an empty bay
    just by existing.
    """
    from m8_core.abort import word_for_refusals
    frame, _scene = scenes.clean()
    trace = {"refusals": [{"why": "some_gate_added_in_2027",
                           "blob": (40, 80, 10, 60), "standing": True}]}
    assert word_for_refusals(frame, trace) is None
    assert word_for_refusals(frame, {}) is None


def test_the_floor_fallback_is_not_a_clipped_object():
    """An all-floor frame IS the whole frame, and it is the purest absence.

    The fallback candidate's box is (0, w, 0, h) by construction, so a
    border rule that did not know about it would silence the one case
    `pallet_absent` is unambiguously right for.
    """
    frame, _scene = scenes.absent()
    trace = {}
    assert segment(frame, trace=trace) is None
    assert trace["refusals"][-1]["standing"] is False
    assert classify(frame) == "pallet_absent"
