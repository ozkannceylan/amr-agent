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
  * STRINGER_NEAR_M - 0.04 m of ground between an obstruction and the
    face is an obstruction in the fork path. It is read off the FLOOR
    MODEL by `pocket.fork_path_fraction`: height above the floor plane
    picks the band a fork travels through, horizontal distance along
    the floor decides what is in front of what. No intercept is read,
    which is the whole of A1's mistake, and the region searched is the
    whole standing object - a bar in front of the face projects BELOW
    the face rows and at 1.0 m misses them completely.

THE WORD POLICY, AND WHY IT IS NOT A THRESHOLD. `EVIDENCE_M8_C1C2_FIX.md`
measured the thresholds above working - every staged fault was aborted
on, clean static frames read `none` at staging and 1.5 m - and the live
false-abort rate still 0.884. The thresholds were not what was wrong.
The WORDS were: "no segmented face" was answered with `pallet_absent`
whatever the reason, and inside 1.2 m the reason is that the truck's own
forks are continuous with the pallet. The bay was full every time.

Two rules replace it, and neither moves a number:

  * `pallet_absent` is a claim about the world and needs evidence - a
    candidate that was measured and found not to be a pallet. See
    `word_for_refusals` and the three sets below it.
  * A standing object that runs off the edge of the image is measured on
    a PART, so it supports no word that claims something about the whole
    pallet. An obstruction seen inside the visible region is still an
    obstruction, so `stringer_in_path` survives clipping.

The output of both rules is silence, which is not `proceed`: the node
publishes nothing and the dock consumer is told nothing at all.
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
    blob_touches_border,
    face_yaw,
    find_pocket_pair,
    fork_path_fraction,
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

# --- WHICH WORD "NO FACE" DESERVES ---------------------------------------
# `EVIDENCE_M8_C1C2_FIX.md` measured this classifier aborting on 88 % of
# the frames of two docks `opennav_docking` finished with error 0, and
# almost all of those aborts were one word: `pallet_absent`, said inside
# 1.2 m where C1 refuses because the truck's own forks are continuous
# with the pallet. The bay was not empty. The classifier had no other
# word and said the wrong one.
#
# `pallet_absent` is a CLAIM ABOUT THE WORLD and it needs evidence. The
# evidence is a candidate that was measured and found not to be a pallet.
# A refusal that says the frame could not be measured is not evidence of
# anything, and a refusal that says the pallet may be there and merged
# with something else is evidence AGAINST the claim.
#
# Silence is the correct output when the frame cannot support a word.
# `proceed` is still not a reason and not a kind: returning None means
# the node publishes nothing, not that it endorses the dock.

# Measured and not a pallet - the candidate got through the fit and was
# rejected on its own geometry. This is what an empty bay looks like:
# the only surface in the window is the floor, or the only things
# standing in it are the wrong size to be a EUR pallet.
MEASURED_NOT_A_PALLET = frozenset((
    "candidate_falls_away_like_a_floor",
    "face_width_not_pallet_sized",
    "face_height_not_pallet_sized",
))

# The pallet may be in this frame and the segmentation could not isolate
# it. `face_is_too_small_a_share` is E1's finding 2 by name: the face IS
# there, merged with a second surface, and holds 23-25 % of the blob.
# Saying `pallet_absent` over this refusal is saying the opposite of what
# the refusal found.
COULD_STILL_BE_THE_PALLET = frozenset((
    "face_is_too_small_a_share",
))

# Everything else `segment` can raise - too_few_points_in_window,
# too_few_face_inliers, seed_plane_unsolvable,
# face_plane_behind_the_camera, no_dominant_plane, empty_frame - says
# only that there was too little to measure. It neither supports the
# claim nor blocks it, and it is deliberately not listed: a refusal name
# added to `pocket` later defaults to saying nothing, which is the safe
# default for a word policy.


def word_for_refusals(frame: DepthFrame, trace: dict) -> Optional[str]:
    """The word a frame with no segmented face deserves - usually none.

    `trace["refusals"]` is every candidate `segment` tried and the gate
    that stopped each one. The rule, in the order it is applied:

      1. If ANY candidate could still be the pallet, say nothing. One
         merged fork-and-pallet blob is enough to make `pallet_absent`
         false, whatever the other seven candidates were.
      2. A candidate that was measured and is not pallet-sized is
         evidence of an empty bay - UNLESS it ran off the edge of the
         image, because a clipped object reads too narrow or too short
         for reasons that have nothing to do with what it is. The floor
         fallback is not a clipped object: it is the whole frame by
         construction, and it is the purest empty-bay evidence there is.
      3. With no evidence either way, say nothing.

    Frame-level refusals (`no_dominant_plane`, `empty_frame`) leave the
    list empty and therefore return None, which is right: a frame with
    no floor model supports no claim about what is standing on it.
    """
    evidence = False
    for item in trace.get("refusals") or ():
        why = item.get("why")
        if why in COULD_STILL_BE_THE_PALLET:
            return None
        if why in MEASURED_NOT_A_PALLET:
            bbox = item.get("blob")
            if (item.get("standing") and bbox is not None
                    and blob_touches_border(frame, bbox)):
                continue
            evidence = True
    return "pallet_absent" if evidence else None


def classify(frame: DepthFrame,
             target_u: Optional[float] = None,
             target_v: Optional[float] = None,
             expected_range: Optional[float] = None) -> Optional[str]:
    """Return an ABORT_REASONS member, or None if the frame looks clean.

    The `target_*` and `expected_range` arguments are the live tag's
    reading if the caller has one. None of them is ground truth and
    none is required - a tagless frame is classified on the range
    window and the floor model alone.

    NO THRESHOLD BELOW MOVED when the word policy was written. What
    changed is which words the frame is allowed to support: a refusal
    is not automatically `pallet_absent` (see `word_for_refusals`), and
    a segment that runs off the edge of the image cannot support a word
    about the WHOLE object - its yaw, its pocket pair, its lateral
    offset are all measured on a part. An obstruction seen inside the
    visible region is still an obstruction, so `stringer_in_path`
    survives clipping; every word that is a claim about the whole pallet
    does not.
    """
    valid = frame.valid_count()
    if valid < ABSENT_VALID_FRAC * frame.width * frame.height:
        # Nothing within range anywhere in the frame - not even a floor.
        # This is the one reading that is evidence of an empty bay on its
        # own, and it is also what a blind camera looks like. The word is
        # kept, and sensor health is m8_health's, not a reason word's.
        return "pallet_absent"

    trace: dict = {}
    seg = segment(frame, expected_range=expected_range,
                  tag_u=target_u, tag_v=target_v, trace=trace)
    if seg is None:
        return word_for_refusals(frame, trace)

    # A standing object that runs off the image is measured on a part.
    # The floor fallback (`seg.floor is None`) is the whole frame by
    # construction and is not a clipped object.
    clipped = seg.floor is not None and blob_touches_border(frame, seg.blob)

    if not clipped and abs(face_yaw(seg.face, seg.up)) > ROTATED_ABS_RAD:
        return "pallet_rotated"

    if fork_path_fraction(frame, seg, STRINGER_NEAR_M) > STRINGER_NEAR_FRAC:
        return "stringer_in_path"

    pair = find_pocket_pair(frame, seg)
    if pair is None:
        return None if clipped else "pocket_blocked"
    u_mid, v_mid, _span = pair

    z = seg.face.depth_at(frame.x_of(u_mid), frame.y_of(v_mid))
    if z is None:
        return None if clipped else "pocket_blocked"
    tu = frame.cx if target_u is None else float(target_u)
    lateral = (u_mid - tu) / frame.fx * z
    if abs(lateral) > SHIFTED_LATERAL_M:
        return None if clipped else "pallet_shifted"
    return None


def propose(frame: DepthFrame,
            ttl_ms: int = DEFAULT_TTL_MS,
            confidence: float = 0.8,
            target_u: Optional[float] = None,
            target_v: Optional[float] = None,
            expected_range: Optional[float] = None) -> Optional[object]:
    reason = classify(frame, target_u=target_u, target_v=target_v,
                      expected_range=expected_range)
    if reason is None:
        return None
    return make_proposal(
        KIND_DOCK_ABORT, reason, float(confidence),
        Evidence(frame.frame_id, frame.sim_stamp, SENSOR_PALLET_CAM),
        int(ttl_ms))
