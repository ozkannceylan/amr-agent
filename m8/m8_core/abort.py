"""Classical C2 abort classifier. Never emits proceed.

ARCHITECTURE.md §3: pallet absent / rotated / shifted / pocket
blocked / stringer in fork path. A clean frame yields None — the
node publishes nothing. `proceed` is not a reason and not a kind.
"""
from __future__ import annotations

from typing import Optional

from .contract import (
    KIND_DOCK_ABORT,
    Evidence,
    SENSOR_PALLET_CAM,
    make_proposal,
)
from .pocket import DepthFrame, _col_median, fit_face_plane, find_pockets, observe

DEFAULT_TTL_MS = 200

# Heuristic thresholds for the synthetic fixtures and as a starting
# point on the plant. E3 will replace them with measured bars; they
# are not a claimed recall.
ABSENT_VALID_FRAC = 0.15
ROTATED_ABS_A = 0.25          # |a| in z = a x + b y + c
SHIFTED_U_FRAC = 0.18         # pocket midline vs image centre
STRINGER_NEAR_FRAC = 0.12     # columns closer than face by 4 cm


def classify(frame: DepthFrame) -> Optional[str]:
    """Return an ABORT_REASONS member, or None if the frame looks clean."""
    valid = frame.valid_count()
    if valid < ABSENT_VALID_FRAC * frame.width * frame.height:
        return "pallet_absent"

    plane = fit_face_plane(frame)
    if plane is None:
        return "pallet_absent"
    a, _b, c, _n = plane

    if abs(a) > ROTATED_ABS_A:
        return "pallet_rotated"

    # Stringer: a band of nearer-than-face columns across the lower
    # third — a ridge in the fork path, not a pocket (pockets are deeper).
    v0 = (2 * frame.height) // 3
    near = 0
    cols = 0
    for u in range(frame.width):
        zs = [frame.at(u, v) for v in range(v0, frame.height)]
        zs = [z for z in zs if z is not None]
        if not zs:
            continue
        cols += 1
        zs.sort()
        if zs[len(zs) // 2] < c - 0.04:
            near += 1
    if cols and (near / cols) > STRINGER_NEAR_FRAC:
        return "stringer_in_path"

    pockets = find_pockets(frame, c)
    if pockets is None:
        # A single off-centre valley is a shift, not a missing pocket
        # pair. Two-cluster failure with no deeper columns is blocked.
        v0 = frame.height // 3
        v1 = (2 * frame.height) // 3
        deeper = []
        for u in range(frame.width):
            med = _col_median(frame, u, v0, v1)
            if med is not None and med > c + 0.04:
                deeper.append(u)
        if deeper:
            u_mid = sum(deeper) / len(deeper)
            if abs(u_mid - frame.cx) > SHIFTED_U_FRAC * frame.width:
                return "pallet_shifted"
        return "pocket_blocked"

    u_mid, _v = pockets
    if abs(u_mid - frame.cx) > SHIFTED_U_FRAC * frame.width:
        return "pallet_shifted"

    # Observe is the last word: if the pocket fit itself failed after
    # the cheap checks, treat as blocked rather than inventing proceed.
    if observe(frame) is None:
        return "pocket_blocked"
    return None


def propose(frame: DepthFrame,
            ttl_ms: int = DEFAULT_TTL_MS,
            confidence: float = 0.8) -> Optional[object]:
    reason = classify(frame)
    if reason is None:
        return None
    return make_proposal(
        KIND_DOCK_ABORT, reason, float(confidence),
        Evidence(frame.frame_id, frame.sim_stamp, SENSOR_PALLET_CAM),
        int(ttl_ms))
