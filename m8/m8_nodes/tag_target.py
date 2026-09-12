"""The live AprilTag, turned into the three narrowing arguments C1/C2 take.

WHY THIS FILE EXISTS. `EVIDENCE_M8_C1C2_FIX.md` miss 1 and open item 7:

    "without a `target_u` the threshold has to be `SHIFTED_LATERAL_M` =
     0.70 m, because the pallet camera is mounted 0.40 m off the
     centreline and a correctly staged pallet is already that far
     off-axis. A 0.30 m shift is inside the gross threshold by
     construction. The fix is to pass the tag-derived target; the
     argument exists and the node is not yet wired to it."

This is the wiring. It adds NO capability to `m8_core` and moves no
threshold there: `target_u`, `target_v` and `expected_range` have been
optional narrowing arguments since the C1/C2 rework, and a caller that
has no tag passes none of them and gets the dock envelope, unchanged.

THE TWO QUANTITIES ARE NOT THE SAME AND ARE NOT INTERCHANGEABLE.
`m8_core.pocket.range_window` wants HORIZONTAL distance along the floor.
A tag pose in the optical frame gives DEPTH along the optical axis. On
this rig's 0.5236 rad mount they differ by 1/cos(pitch), about 15 %, and
quietly feeding one where the other is meant reads fine until it does
not. So the horizontal figure is taken in a frame whose XY plane IS
horizontal - `base_link` - rather than derived from a pitch this module
would have to be told:

    range_m    = planar distance, in base_link, from the camera origin
                 to the tag: the range to the MARKER
    lateral_m  = the tag across the optical axis, in metres
    z          = the tag's own optical depth, a diagnostic
    u, v       = the tag projected through the live CameraInfo, also
                 diagnostics - see `as_kwargs` for why they are not
                 passed on THIS rig

AND THE TAG ON THIS RIG IS NOT ON THE PALLET. It is the dock marker on
the bay back panel, 0.82 m behind the pallet face by config and 0.8525 m
by plant measurement. The first version of this file read its range
straight into `expected_range` and the plant answered immediately: 57
clean frames turned into `pallet_absent` because the window opened
around the panel and the pallet fell outside it. Every one of those 57
was a tagged frame; not one was a frame carrying only the fork
self-mask. `FACE_AHEAD_OF_MARKER_M` and `as_kwargs` are what came of
that, and both carry the measurement that forced them.

WHAT THE TAG IS AND IS NOT. It is a reading, not ground truth and not a
command. It can only NARROW: `range_window` clamps it to the dock
envelope. A tag that is absent, stale or untransformable yields None and
the caller runs tagless, which is the behaviour the C1/C2 numbers were
measured with.

R1 is tagged pallets first; tagless docking is not removed by this.
"""
from __future__ import annotations

import math
from typing import Optional

TAG_STALE_S = 0.3

# WHAT THE TAG ON THIS RIG ACTUALLY IS, AND IT IS NOT ON THE PALLET.
# config.yaml dock.marker_ahead_m: the marker stands on the bay BACK
# PANEL. A correctly staged pallet stands in front of that panel by its
# own depth plus the wall clearance:
#
#     pallet.depth_m 0.80 + pallet.wall_clearance_m 0.02 = 0.82 m
#
# So the tag is BEHIND the pallet face, and reading its range straight
# into `expected_range` opens the window around the panel instead of
# around the pallet. That is not a small error: the window is +-0.40 m
# wide and the offset is twice its half width. It was MEASURED, on the
# plant, on 2026-09-12 in session e3-20260912-181548 - every one of 57
# `none -> pallet_absent` regressions was on a frame that had a tag and
# none was on a frame with only the fork self-mask.
#
# The plant measured the offset at 0.8525 m mean over 113 frames (per
# pose 0.8603 / 0.8377 / 0.8583, spread inside a pose 0.0005 m). The
# constant below is the CONFIG figure, 0.820 m, and the 0.0325 m
# residual is stated and left: it is an order inside the window it
# opens, and tuning a geometry constant onto a bench reading is how a
# number stops meaning what it says.
FACE_AHEAD_OF_MARKER_M = 0.82


class TagTarget(object):
    """One tag reading, in the three forms `m8_core` accepts.

    Built by `from_transforms` out of TF lookups the caller already has.
    Nothing here reads a topic, a parameter file or a clock.
    """

    __slots__ = ("u", "v", "z", "range_m", "lateral_m", "stamp")

    def __init__(self, u, v, z, range_m, lateral_m=0.0, stamp=None):
        self.u = float(u)
        self.v = float(v)
        self.z = float(z)
        self.range_m = float(range_m)
        # The tag in METRES across the optical axis. On a marker that
        # stands on the bay centreline this is the centreline offset and
        # nothing else - the plant read -0.4019 / -0.3979 / -0.3994 m at
        # three ranges that differ by more than a metre, which is the
        # 0.40 m camera mount and no drift at all. The pixel column does
        # drift, by 12 / 27 / 57 px at the same three poses, because the
        # marker and the pallet are 0.85 m apart in depth and this camera
        # is off-axis. Metres are what survives that; pixels are not.
        self.lateral_m = float(lateral_m)
        self.stamp = stamp

    @property
    def face_range_m(self):
        """Horizontal range to the PALLET FACE, not to the marker."""
        return max(0.0, self.range_m - FACE_AHEAD_OF_MARKER_M)

    def is_stale(self, now, stale_s=TAG_STALE_S):
        """Same rule as the self-mask: unknown age is stale."""
        if self.stamp is None or now is None:
            return True
        return abs(float(now) - float(self.stamp)) > float(stale_s)

    def as_kwargs(self):
        """The narrowing arguments, ready to splat into classify.

        THREE THINGS ARE PASSED AND TWO ARE DELIBERATELY NOT.

        Passed: `expected_range`, the range to the pallet FACE, and
        `target_lateral_m`, the reference in metres.

        Not passed: `target_u` and `target_v`, which would seed
        `segment`'s choice of candidate blob. On this rig the marker is
        0.73 m ABOVE the pallet and 0.85 m behind it, so its pixel is
        not inside the pallet's blob at any pose - at staging the tag
        lands near row 87 and the pallet occupies rows 202-213. Seeding
        on it ranks the MARKER BOARD first, which is the wrong object,
        and the plant measured what that costs. A tag mounted ON a
        pallet would be a different case and this module would need a
        different answer; the one in front of us is a dock marker.
        """
        return {"expected_range": self.face_range_m,
                "target_lateral_m": self.lateral_m}

    def __repr__(self):
        return ("TagTarget(u={:.1f}, v={:.1f}, z={:.3f}, marker_range={:.3f},"
                " face_range={:.3f}, lateral={:+.3f})"
                .format(self.u, self.v, self.z, self.range_m,
                        self.face_range_m, self.lateral_m))


def from_transforms(tag_in_optical, tag_in_base, cam_in_base,
                    fx, fy, cx, cy, stamp=None,
                    min_depth_m=1e-3) -> Optional[TagTarget]:
    """Build a target, or None when the frame cannot support one.

    `tag_in_optical` is (X, Y, Z) of the tag in the camera's optical
    frame - apriltag_ros broadcasts exactly this as a TF. `tag_in_base`
    and `cam_in_base` are the tag and the camera origin in a frame whose
    XY plane is horizontal; their planar separation is the horizontal
    range, and it is the ONLY place that number comes from.

    Returns None rather than a guess when the tag is behind the camera,
    when an intrinsic is missing, or when either transform is absent.
    """
    if tag_in_optical is None or None in (fx, fy, cx, cy):
        return None
    x, y, z = (float(v) for v in tag_in_optical)
    if not (z > min_depth_m) or not math.isfinite(z):
        return None
    if tag_in_base is None or cam_in_base is None:
        return None
    range_m = math.hypot(float(tag_in_base[0]) - float(cam_in_base[0]),
                         float(tag_in_base[1]) - float(cam_in_base[1]))
    if not math.isfinite(range_m):
        return None
    return TagTarget(u=cx + x / z * float(fx),
                     v=cy + y / z * float(fy),
                     z=z, range_m=range_m, lateral_m=x, stamp=stamp)


def read_tag(buf, time_obj, fx, fy, cx, cy, stamp=None):
    """Three TF lookups, or None. Duck-typed on a tf2_ros Buffer.

    No ROS type is imported here: the caller passes the buffer and the
    `rclpy.time.Time` it wants the lookup at, so this file stays
    importable by a pytest that has never sourced ROS. Any lookup that
    raises is a tagless frame, not an error - apriltag_node stops
    broadcasting the moment the tag leaves view, which is normal.
    """
    from m8_core.topics import FRAME_BASE, FRAME_CAM_OPTICAL, FRAME_TAG

    def origin_of(target_frame, source_frame):
        try:
            tf = buf.lookup_transform(target_frame, source_frame, time_obj)
        except Exception:
            return None
        t = tf.transform.translation
        return (t.x, t.y, t.z)

    return from_transforms(
        origin_of(FRAME_CAM_OPTICAL, FRAME_TAG),
        origin_of(FRAME_BASE, FRAME_TAG),
        origin_of(FRAME_BASE, FRAME_CAM_OPTICAL),
        fx, fy, cx, cy, stamp=stamp)


def kwargs_for(target, now, stale_s=TAG_STALE_S):
    """`{}` when there is no usable tag, the narrowing arguments when there is.

    An empty dict is the tagless case and it is deliberately the same
    object shape as the tagged one: the call site reads
    `classify(frame, **kwargs_for(...))` and has no branch in it, so
    there is no path where a half-applied tag reaches `m8_core`.
    """
    if target is None or target.is_stale(now, stale_s):
        return {}
    return target.as_kwargs()
