"""Classical C1 pocket pose on synthetic depth. No ROS, no Gazebo."""
import math

import pytest

from m8_core.contract import KIND_DOCK_TARGET_REFINE, validate_proposal
from m8_core.pocket import make_plane_depth, observe, propose


def _clean_pallet():
    # Face at 1.20 m, two deeper columns = pockets.
    return make_plane_depth(
        48, 36, 1.20,
        pockets=((10, 16, 10, 26, 1.55),
                 (32, 38, 10, 26, 1.55)))


def test_a_two_pocket_face_yields_a_refine():
    frame = _clean_pallet()
    obs = observe(frame)
    assert obs is not None
    assert obs.face_z == pytest.approx(1.20, abs=0.08)
    proposal = propose(frame)
    assert proposal is not None
    validate_proposal(proposal)
    assert proposal.kind == KIND_DOCK_TARGET_REFINE
    assert proposal.evidence.sensor_name == "pallet_cam"
    assert 0.0 < proposal.confidence <= 1.0


def test_a_tilted_face_reports_dtheta():
    frame = make_plane_depth(
        48, 36, 1.20, a=0.12,
        pockets=((10, 16, 10, 26, 1.55),
                 (32, 38, 10, 26, 1.55)))
    proposal = propose(frame)
    assert proposal is not None
    assert abs(proposal.pose_delta().dtheta) > 0.05


def test_an_empty_or_tiny_frame_yields_nothing():
    empty = make_plane_depth(8, 8, float("nan"))
    # nan plane: overwrite with invalids
    from m8_core.pocket import DepthFrame
    bad = DepthFrame(8, 8, tuple([float("nan")] * 64), frame_id="x",
                     sim_stamp=1.0)
    assert propose(bad) is None
    assert observe(empty) is None or propose(empty) is None


def test_tag_target_shifts_the_delta():
    frame = _clean_pallet()
    a = propose(frame, tag_u=frame.cx, tag_z=1.20)
    b = propose(frame, tag_u=frame.cx + 8.0, tag_z=1.20)
    assert a is not None and b is not None
    assert a.pose_delta().dy != b.pose_delta().dy
    assert math.isfinite(a.pose_delta().hypot_xy())
