"""Classical C2 abort classifier. Never proceed. No ROS.

`EVIDENCE_M8_E3.md` measured A1 aborting on 540 of 540 static frames,
90 of 90 of them clean, because it read the floor as the pallet face.
The first test below is the one that would have caught it offline.
"""
import pytest
import scenes

from m8_core.abort import classify, propose
from m8_core.contract import ABORT_REASONS, KIND_DOCK_ABORT
from m8_core.pocket import DepthFrame


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
