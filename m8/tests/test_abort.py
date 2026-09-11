"""Classical C2 abort classifier. Never proceed. No ROS."""
from m8_core.abort import classify, propose
from m8_core.contract import ABORT_REASONS, KIND_DOCK_ABORT
from m8_core.pocket import DepthFrame, make_plane_depth


def _clean():
    return make_plane_depth(
        48, 36, 1.20,
        pockets=((10, 16, 10, 26, 1.55),
                 (32, 38, 10, 26, 1.55)))


def test_a_clean_two_pocket_face_is_not_an_abort():
    assert classify(_clean()) is None
    assert propose(_clean()) is None


def test_proceed_is_never_returned():
    frames = [
        _clean(),
        DepthFrame(16, 12, tuple([float("nan")] * 192),
                   frame_id="x", sim_stamp=1.0),
        make_plane_depth(48, 36, 1.20, a=0.45),
        make_plane_depth(48, 36, 1.20),
        make_plane_depth(
            48, 36, 1.20,
            pockets=((2, 10, 10, 26, 1.55),)),
    ]
    for frame in frames:
        reason = classify(frame)
        if reason is not None:
            assert reason in ABORT_REASONS
            assert reason != "proceed"
            p = propose(frame)
            assert p.kind == KIND_DOCK_ABORT
            assert p.abort_reason() == reason


def test_too_few_valid_pixels_is_pallet_absent():
    frame = DepthFrame(16, 12, tuple([float("nan")] * 192),
                       frame_id="x", sim_stamp=1.0)
    assert classify(frame) == "pallet_absent"


def test_a_yawed_face_is_pallet_rotated():
    frame = make_plane_depth(
        48, 36, 1.20, a=0.45,
        pockets=((10, 16, 10, 26, 1.55),
                 (32, 38, 10, 26, 1.55)))
    assert classify(frame) == "pallet_rotated"


def test_a_one_sided_valley_is_pallet_shifted():
    frame = make_plane_depth(
        48, 36, 1.20,
        pockets=((2, 10, 10, 26, 1.55),))
    assert classify(frame) == "pallet_shifted"


def test_a_flat_face_with_no_pockets_is_pocket_blocked():
    frame = make_plane_depth(48, 36, 1.20)
    assert classify(frame) == "pocket_blocked"


def test_a_near_ridge_in_the_lower_third_is_stringer_in_path():
    # Face 1.20, then paint the bottom rows closer (0.90) across
    # enough columns to trip STRINGER_NEAR_FRAC.
    frame = make_plane_depth(48, 36, 1.20)
    depths = list(frame.depths)
    v0 = (2 * frame.height) // 3
    for v in range(v0, frame.height):
        for u in range(frame.width):
            depths[v * frame.width + u] = 0.90
    ridged = DepthFrame(frame.width, frame.height, tuple(depths),
                        frame.fx, frame.fy, frame.cx, frame.cy,
                        "x", 1.0)
    assert classify(ridged) == "stringer_in_path"
