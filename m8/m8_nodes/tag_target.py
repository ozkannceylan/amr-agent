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

    expected_range = planar distance, in base_link, from the camera
                     origin to the tag
    target_u, v    = the tag projected through the live CameraInfo
    tag_z          = the tag's own optical depth, which is what a pose
                     delta is measured against

WHAT THE TAG IS AND IS NOT. It is a reading, not ground truth and not a
command. It can only NARROW: `range_window` clamps it to the dock
envelope, and (target_u, target_v) only ORDER the candidate blobs. A tag
that is absent, stale or untransformable yields None and the caller runs
tagless, which is the behaviour the C1/C2 numbers were measured with.

R1 is tagged pallets first; tagless docking is not removed by this.
"""
from __future__ import annotations

import math
from typing import Optional

# The tag board is a few centimetres in front of the pallet face
# (config.yaml dock.tag_thickness_m, dock.marker_ahead_m). That offset is
# NOT modelled here and does not need to be: `expected_range` opens a
# window +-TAG_WINDOW_M = 0.40 m wide, which is an order over it, and
# `m8_core` must not grow a model of this rig's dock furniture.
TAG_STALE_S = 0.3


class TagTarget(object):
    """One tag reading, in the three forms `m8_core` accepts.

    Built by `from_transforms` out of TF lookups the caller already has.
    Nothing here reads a topic, a parameter file or a clock.
    """

    __slots__ = ("u", "v", "z", "range_m", "stamp")

    def __init__(self, u, v, z, range_m, stamp=None):
        self.u = float(u)
        self.v = float(v)
        self.z = float(z)
        self.range_m = float(range_m)
        self.stamp = stamp

    def is_stale(self, now, stale_s=TAG_STALE_S):
        """Same rule as the self-mask: unknown age is stale."""
        if self.stamp is None or now is None:
            return True
        return abs(float(now) - float(self.stamp)) > float(stale_s)

    def as_kwargs(self):
        """The narrowing arguments, ready to splat into classify/observe."""
        return {"target_u": self.u, "target_v": self.v,
                "expected_range": self.range_m}

    def __repr__(self):
        return ("TagTarget(u={:.1f}, v={:.1f}, z={:.3f}, range={:.3f})"
                .format(self.u, self.v, self.z, self.range_m))


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
                     z=z, range_m=range_m, stamp=stamp)


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
