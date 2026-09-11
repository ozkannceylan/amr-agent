"""Classical C2 abort classifier. Never emits proceed.

ARCHITECTURE.md §3: pallet absent / rotated / shifted / pocket
blocked / stringer in fork path. A clean frame yields None - the
node publishes nothing. `proceed` is not a reason and not a kind.

WHY THIS IS NOT THE A1 CLASSIFIER. `EVIDENCE_M8_E3.md` measured it on
the plant: it aborted on 540 of 540 static frames including 90 of 90
clean ones, and on 252 of 252 frames of two live docks the plugin
finished with error 0. The word it chose depended on range - stringer
beyond about 1.6 m, rotated inside it - which is the signature of a
classifier reading the FLOOR: A1 took `c`, the intercept of a plane
fitted to a fixed central band, as the depth of the pallet face, so
"columns nearer than the face" was really "floor rows nearer than the
floor's own average" and "|a| too large" was the floor's slope.

Every test below now runs against the face `pocket.segment` derived
for this frame, inside the ROI that face occupies. The thresholds are
argued from the pallet, not fitted to a corpus:

  * ROTATED_ABS_RAD - a 0.160 m wide, 0.800 m deep pocket admits a
    straight fork only while |yaw| < atan(0.160/0.800) = 0.1974 rad.
    0.15 rad is that limit with margin for the pose error itself.
  * SHIFTED_LATERAL_M - past the pallet's own half width the forks
    miss it. See the caution on `target_u` below.
  * STRINGER_NEAR_M - the pocket mouth is 0.122 m tall; 0.04 m of
    something nearer than the face is inside the fork path. It is
    measured over the whole standing object (`near_face_fraction`),
    because a bar in front of the face projects BELOW the face rows -
    at 1.0 m it misses them completely.
"""
from __future__ import annotations

from typing import Optional

from .contract import (
    KIND_DOCK_ABORT,
    Evidence,
    SENSOR_PALLET_CAM,
    make_proposal,
)
from .pocket import (
    DepthFrame,
    face_yaw,
    find_pocket_pair,
    near_face_fraction,
    segment,
)

DEFAULT_TTL_MS = 200

ABSENT_VALID_FRAC = 0.15
ROTATED_ABS_RAD = 0.15
STRINGER_NEAR_M = 0.04
STRINGER_NEAR_FRAC = 0.06
# CAUTION, and it is the open limitation of this classifier. With no
# `target_u` the only reference is the image centre, and on this rig the
# pallet camera is mounted 0.40 m off the vehicle centreline, so a
# correctly staged pallet already sits 0.40 m off-axis. The threshold
# therefore has to be a GROSS one - half a pallet plus margin - and a
# shift small enough to miss a pocket will not be caught. The node has
# the tag-derived target and should pass it.
SHIFTED_LATERAL_M = 0.70


def classify(frame: DepthFrame,
             target_u: Optional[float] = None) -> Optional[str]:
    """Return an ABORT_REASONS member, or None if the frame looks clean.

    `target_u` is the column the tag-derived dock target projects to. It
    is not ground truth and it is not required; without it the lateral
    test is the gross one described above.
    """
    valid = frame.valid_count()
    if valid < ABSENT_VALID_FRAC * frame.width * frame.height:
        return "pallet_absent"

    seg = segment(frame)
    if seg is None:
        # No pallet-sized surface stands above the dominant plane. On a
        # frame that is all floor the fallback candidate IS the floor,
        # and the dz/dy guard in `segment` is what rejects it.
        return "pallet_absent"

    if abs(face_yaw(seg.face, seg.up)) > ROTATED_ABS_RAD:
        return "pallet_rotated"

    if near_face_fraction(frame, seg, STRINGER_NEAR_M) > STRINGER_NEAR_FRAC:
        return "stringer_in_path"

    pair = find_pocket_pair(frame, seg)
    if pair is None:
        return "pocket_blocked"
    u_mid, v_mid, _span = pair

    z = seg.face.depth_at(frame.x_of(u_mid), frame.y_of(v_mid))
    if z is None:
        return "pocket_blocked"
    tu = frame.cx if target_u is None else float(target_u)
    lateral = (u_mid - tu) / frame.fx * z
    if abs(lateral) > SHIFTED_LATERAL_M:
        return "pallet_shifted"
    return None


def propose(frame: DepthFrame,
            ttl_ms: int = DEFAULT_TTL_MS,
            confidence: float = 0.8,
            target_u: Optional[float] = None) -> Optional[object]:
    reason = classify(frame, target_u=target_u)
    if reason is None:
        return None
    return make_proposal(
        KIND_DOCK_ABORT, reason, float(confidence),
        Evidence(frame.frame_id, frame.sim_stamp, SENSOR_PALLET_CAM),
        int(ttl_ms))
