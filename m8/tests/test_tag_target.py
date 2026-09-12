"""The tag wiring: three lookups in, three narrowing arguments out.

`EVIDENCE_M8_C1C2_FIX.md` miss 1 / open 7: without a `target_u` the
lateral test has to be gross - 0.70 m, because the pallet camera is
mounted 0.40 m off the centreline - and a 0.30 m shift is inside that
threshold by construction. The argument existed and nothing passed it.

These hold the conversion and the one thing it must never do: hand
`m8_core` an optical depth where a horizontal distance belongs. On this
rig's 0.5236 rad mount that is a 15 % error and it reads fine until it
does not.

No ROS. The TF buffer is a stub, which is the point - `read_tag` is
duck-typed on `lookup_transform` so this file is importable by a python
that has never sourced ROS.
"""
import math

import pytest
import scenes

from m8_core.abort import SHIFTED_LATERAL_M, classify
from m8_core.pocket import DOCK_ENVELOPE_M, TAG_WINDOW_M, range_window
from m8_nodes.tag_target import (
    TAG_STALE_S,
    TagTarget,
    from_transforms,
    kwargs_for,
    read_tag,
)

FX = FY = 337.357
CX, CY = 320.0, 240.0
PITCH = 0.5236            # config.yaml vehicle.cam_mount.pitch


class _Stub(object):
    """A tf2 Buffer with a fixed answer, or a raise. Nothing else."""

    def __init__(self, table):
        self.table = table
        self.asked = []

    def lookup_transform(self, target, source, _time):
        self.asked.append((target, source))
        value = self.table.get((target, source))
        if value is None:
            raise RuntimeError("no transform {} -> {}".format(target, source))

        class _T(object):
            class transform(object):
                class translation(object):
                    x, y, z = value
        return _T()


def _tf_table(optical=(0.0, 0.0, 2.0), tag_base=(-3.0, 0.0, 0.2),
              cam_base=(-0.9, 0.4, 1.1)):
    from m8_core.topics import FRAME_BASE, FRAME_CAM_OPTICAL, FRAME_TAG
    return {(FRAME_CAM_OPTICAL, FRAME_TAG): optical,
            (FRAME_BASE, FRAME_TAG): tag_base,
            (FRAME_BASE, FRAME_CAM_OPTICAL): cam_base}


# -------------------------------------------------- the two quantities
def test_the_horizontal_range_is_not_the_optical_depth():
    """The whole reason `expected_range` is taken in base_link.

    A tag 2.0 m along a camera pitched 0.5236 rad down is 1.73 m away on
    the floor. Reading the 2.0 m into a window meant for the 1.73 m puts
    the window 0.27 m off - two thirds of the window's own half width.
    """
    depth = 2.0
    horizontal = depth * math.cos(PITCH)
    tag_base = (-0.9 - horizontal, 0.4, 0.2)
    target = from_transforms((0.0, 0.0, depth), tag_base, (-0.9, 0.4, 1.1),
                             FX, FY, CX, CY, stamp=1.0)
    assert target is not None
    assert target.z == pytest.approx(depth)
    assert target.range_m == pytest.approx(horizontal, abs=1e-9)
    assert abs(target.z - target.range_m) > 0.25


def test_the_marker_is_behind_the_pallet_and_the_window_says_so():
    """The plant regression this constant exists because of.

    Session e3-20260912-181548: `expected_range` was the range to the
    MARKER, the window opened around the bay back panel, the pallet fell
    outside it, and 57 clean frames turned into `pallet_absent`. Every
    one of the 57 carried a tag; not one carried only the self-mask.
    """
    from m8_nodes.tag_target import FACE_AHEAD_OF_MARKER_M
    # The constant is config, not the bench reading: pallet depth 0.80 m
    # plus wall clearance 0.02 m.
    assert FACE_AHEAD_OF_MARKER_M == pytest.approx(0.80 + 0.02)
    marker = TagTarget(u=271.9, v=87.0, z=2.818, range_m=3.1055,
                       lateral_m=-0.4019, stamp=1.0)
    assert marker.face_range_m == pytest.approx(3.1055 - 0.82)
    # The plant staged that pose at a camera-to-face range of 2.2452 m.
    # What is left is the residual, and it is an order inside the window.
    assert abs(marker.face_range_m - 2.2452) < 0.05
    lo, hi = range_window(marker.face_range_m)
    assert lo <= 2.2452 <= hi
    # The uncorrected marker range would have excluded the pallet.
    lo_bad, hi_bad = range_window(marker.range_m)
    assert not (lo_bad <= 2.2452 <= hi_bad)


def test_the_window_from_the_tag_also_excludes_the_trucks_own_forks():
    """A second, independent answer to the fork problem - at range.

    The tines reach 0.975 m. At staging the tag-derived window starts at
    1.885 m, so the tines are outside it before any mask is applied. At
    1.0 m they are inside it again, which is exactly where the self-mask
    is needed and why the two are not alternatives.
    """
    from m8_core.selfmask import TINE_REACH_M
    staging = TagTarget(1, 1, 2.8, range_m=3.1055, lateral_m=-0.40,
                        stamp=1.0)
    lo, _hi = range_window(staging.face_range_m)
    assert lo > TINE_REACH_M
    close = TagTarget(1, 1, 1.7, range_m=1.8583, lateral_m=-0.40, stamp=1.0)
    lo_close, _ = range_window(close.face_range_m)
    assert lo_close < TINE_REACH_M


def test_the_pixel_column_is_not_passed_and_the_metre_reference_is():
    """The marker is a DIFFERENT OBJECT, 0.73 m above the pallet.

    Seeding `segment` on its pixel ranks the marker board first. The
    lateral reference in METRES has no such problem - it is a distance
    across the axis, not a claim about which blob to look at.
    """
    target = TagTarget(u=271.9, v=87.0, z=2.818, range_m=3.1055,
                       lateral_m=-0.4019, stamp=1.0)
    kwargs = target.as_kwargs()
    assert set(kwargs) == {"expected_range", "target_lateral_m"}
    assert "target_u" not in kwargs and "target_v" not in kwargs
    assert kwargs["target_lateral_m"] == pytest.approx(-0.4019)


def test_a_metre_reference_does_not_drift_with_range_where_a_column_does():
    """The measurement that forced the change, reproduced offline.

    A reference column is only a reference at one depth. The plant read
    the marker 12 px from the pallet centre at staging, 27 at 1.5 m and
    57 at 1.0 m - the same two objects, drifting apart in pixels as the
    truck closed in. In metres the marker sat at -0.4019 / -0.3979 /
    -0.3994 m: the mount offset, and no drift.
    """
    # ONE number in metres, correct at every range.
    for distance in (scenes.STAGING_M, scenes.APPROACH_M, scenes.CLOSE_M):
        frame, _scene = scenes.clean(distance)
        assert classify(frame, target_lateral_m=-0.40) is None

    # ONE column in pixels, correct at exactly one range. Taken at
    # staging and carried to 1.5 m it is off by a real distance on the
    # floor - and this scene is the KIND case, because the pallet is its
    # own reference here. On the plant the reference was 0.85 m further
    # away than the pallet, which is what turned 12 px into 57.
    at_staging, _v = scenes.px_of(*scenes.clean(scenes.STAGING_M))
    frame, scene = scenes.clean(scenes.APPROACH_M)
    at_approach, _v2 = scenes.px_of(frame, scene)
    drift_m = abs(at_staging - at_approach) / frame.fx * scene.pocket_centre()[2]
    assert drift_m > 0.05


def test_the_tag_projects_through_the_live_intrinsics():
    target = from_transforms((0.20, -0.10, 2.0), (-3.0, 0.0, 0.2),
                             (-0.9, 0.4, 1.1), FX, FY, CX, CY, stamp=1.0)
    assert target.u == pytest.approx(CX + 0.20 / 2.0 * FX)
    assert target.v == pytest.approx(CY - 0.10 / 2.0 * FY)


@pytest.mark.parametrize("bad", [
    {"tag_in_optical": None},
    {"tag_in_optical": (0.0, 0.0, -1.0)},          # behind the camera
    {"tag_in_optical": (0.0, 0.0, float("nan"))},
    {"tag_in_base": None},
    {"cam_in_base": None},
    {"fx": None},
])
def test_an_unusable_reading_is_none_and_not_a_guess(bad):
    kwargs = {"tag_in_optical": (0.0, 0.0, 2.0),
              "tag_in_base": (-3.0, 0.0, 0.2),
              "cam_in_base": (-0.9, 0.4, 1.1),
              "fx": FX, "fy": FY, "cx": CX, "cy": CY}
    kwargs.update(bad)
    assert from_transforms(stamp=1.0, **kwargs) is None


# ------------------------------------------------------------ staleness
def test_a_stale_or_unstamped_tag_falls_back_to_tagless():
    target = TagTarget(u=300.0, v=250.0, z=2.0, range_m=1.8, stamp=10.0)
    assert kwargs_for(target, 10.0) == target.as_kwargs()
    assert kwargs_for(target, 10.0 + 2.0 * TAG_STALE_S) == {}
    assert kwargs_for(TagTarget(1, 2, 3, 4, stamp=None), 10.0) == {}
    assert kwargs_for(None, 10.0) == {}


def test_tagless_is_an_empty_dict_so_the_call_site_has_no_branch():
    """There is no path where half a tag reaches m8_core."""
    empty = kwargs_for(None, 1.0)
    assert empty == {}
    frame, _scene = scenes.clean()
    assert classify(frame, **empty) is None


# --------------------------------------------------------- the lookups
def test_read_tag_asks_for_exactly_the_three_transforms_it_needs():
    from m8_core.topics import FRAME_BASE, FRAME_CAM_OPTICAL, FRAME_TAG
    buf = _Stub(_tf_table())
    target = read_tag(buf, None, FX, FY, CX, CY, stamp=1.0)
    assert target is not None
    assert set(buf.asked) == {(FRAME_CAM_OPTICAL, FRAME_TAG),
                              (FRAME_BASE, FRAME_TAG),
                              (FRAME_BASE, FRAME_CAM_OPTICAL)}


def test_a_tag_that_is_not_being_broadcast_is_a_tagless_frame():
    """apriltag_node stops broadcasting the moment the tag leaves view.

    That is normal operation, not an error, and it must not raise into
    a depth callback.
    """
    assert read_tag(_Stub({}), None, FX, FY, CX, CY, stamp=1.0) is None


def test_m8_nodes_broadcast_no_transform():
    """M8 looks up. The tree has its owners already."""
    import pathlib
    nodes = pathlib.Path(__file__).resolve().parents[1] / "m8_nodes"
    for path in sorted(nodes.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "TransformBroadcaster" not in text, path.name
        assert "StaticTransformBroadcaster" not in text, path.name


# ---------------------------------------------- what the window does with it
def test_a_tag_narrows_the_window_and_can_never_widen_it():
    lo, hi = range_window(None)
    assert (lo, hi) == DOCK_ENVELOPE_M
    t_lo, t_hi = range_window(1.80)
    assert t_hi - t_lo == pytest.approx(2.0 * TAG_WINDOW_M)
    assert t_lo >= lo and t_hi <= hi
    # A tag far outside the envelope cannot drag the window out with it.
    far_lo, far_hi = range_window(99.0)
    assert far_lo >= lo and far_hi <= hi


def test_the_tag_column_makes_the_lateral_test_symmetric():
    """The threshold does not move. The 0.40 m MOUNTING BIAS comes out.

    Untagged, the reference is the image centre and a correctly staged
    pallet already sits at optical lateral -0.40 m, so |lateral| > 0.70 m
    is really "true shift > +1.10 m, or < -0.30 m". That test is
    asymmetric by 1.40 m: it misses a metre of shift one way and fires on
    a third of a metre the other. Both are measured here.

    With the tag as the reference the same 0.70 m measures the shift
    itself, the same distance either way. A 0.30 m shift is STILL not
    caught - that would need a smaller threshold, and no threshold moved
    in this work. What the tag buys is that the number means what it says.
    """
    assert SHIFTED_LATERAL_M == 0.70
    tag_u, tag_v = scenes.px_of(*scenes.clean(scenes.APPROACH_M))

    def words(lateral):
        frame, _scene = scenes.shifted(lateral)
        return (classify(frame),
                classify(frame, target_u=tag_u, target_v=tag_v))

    # A full metre of shift away from the mount offset, missed untagged.
    assert words(0.60) == (None, "pallet_shifted")
    # A third of a metre toward it, called a shift untagged - at a
    # threshold that says it takes 0.70 m.
    assert words(-0.75) == ("pallet_shifted", None)
    # The correctly staged pallet is not a shift either way.
    assert words(-0.40) == (None, None)
