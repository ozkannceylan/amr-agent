"""Classical C1 pocket pose — depth-plane fit + pocket segmentation.

ARCHITECTURE.md §6: a scorable baseline, no learned weights. Input is
a depth buffer (metres, 32FC1 layout). Output is a DOCK_TARGET_REFINE
Proposal or None if the frame cannot support a pose.

The delta is vs a tag-derived target the caller supplies. Ground truth
is not an input. This module does not claim a plant rms — E1 does.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from .contract import (
    KIND_DOCK_TARGET_REFINE,
    Evidence,
    PoseDelta,
    SENSOR_PALLET_CAM,
    make_proposal,
)

# D455-class defaults from m5_ver3/config.yaml (sensors.pallet_cam).
# Used only when CameraInfo has not arrived. Not a measured claim.
DEFAULT_WIDTH = 64
DEFAULT_HEIGHT = 48
DEFAULT_FX = 35.0
DEFAULT_FY = 35.0
DEFAULT_TTL_MS = 200


@dataclass(frozen=True)
class DepthFrame:
    """Row-major depths in metres. non-finite = invalid."""

    width: int
    height: int
    depths: Tuple[float, ...]
    fx: float = DEFAULT_FX
    fy: float = DEFAULT_FY
    cx: float = 0.0
    cy: float = 0.0
    frame_id: str = "frame"
    sim_stamp: float = 0.0

    def __post_init__(self):
        if self.cx == 0.0 and self.cy == 0.0 and self.width > 0:
            object.__setattr__(self, "cx", self.width / 2.0)
            object.__setattr__(self, "cy", self.height / 2.0)

    def at(self, u: int, v: int) -> Optional[float]:
        if u < 0 or v < 0 or u >= self.width or v >= self.height:
            return None
        z = self.depths[v * self.width + u]
        if not math.isfinite(z) or z <= 0.0:
            return None
        return float(z)

    def valid_count(self) -> int:
        return sum(1 for z in self.depths if math.isfinite(z) and z > 0.0)


@dataclass(frozen=True)
class PocketObservation:
    """Numbers the refine is built from. Logged in proposal.extra."""

    face_z: float
    face_a: float
    face_b: float
    pocket_u: float
    pocket_v: float
    inliers: int
    valid: int


def _col_median(frame: DepthFrame, u: int, v0: int, v1: int) -> Optional[float]:
    vals = []
    for v in range(v0, v1):
        z = frame.at(u, v)
        if z is not None:
            vals.append(z)
    if len(vals) < 2:
        return None
    vals.sort()
    return vals[len(vals) // 2]


def fit_face_plane(frame: DepthFrame) -> Optional[Tuple[float, float, float, int]]:
    """Least-squares z = a*x + b*y + c on the central band.

    x,y are optical-frame pixels scaled by 1/fx, 1/fy (dimensionless).
    Returns (a, b, c, n) or None.
    """
    v0 = frame.height // 4
    v1 = (3 * frame.height) // 4
    u0 = frame.width // 6
    u1 = (5 * frame.width) // 6
    # Normal equations for z = a x + b y + c
    sxx = sxy = sx = syy = sy = sz = sxz = syz = n = 0.0
    for v in range(v0, v1):
        for u in range(u0, u1):
            z = frame.at(u, v)
            if z is None:
                continue
            x = (u - frame.cx) / frame.fx
            y = (v - frame.cy) / frame.fy
            sxx += x * x
            sxy += x * y
            sx += x
            syy += y * y
            sy += y
            sz += z
            sxz += x * z
            syz += y * z
            n += 1.0
    if n < 12:
        return None
    # 3x3 solve via Cramer's rule on
    # [sxx sxy sx] [a]   [sxz]
    # [sxy syy sy] [b] = [syz]
    # [sx  sy  n ] [c]   [sz ]
    det = (sxx * (syy * n - sy * sy)
           - sxy * (sxy * n - sy * sx)
           + sx * (sxy * sy - syy * sx))
    if abs(det) < 1e-12:
        return None
    det_a = (sxz * (syy * n - sy * sy)
             - sxy * (syz * n - sy * sz)
             + sx * (syz * sy - syy * sz))
    det_b = (sxx * (syz * n - sy * sz)
             - sxz * (sxy * n - sy * sx)
             + sx * (sxy * sz - syz * sx))
    det_c = (sxx * (syy * sz - sy * syz)
             - sxy * (sxy * sz - syz * sx)
             + sxz * (sxy * sy - syy * sx))
    return det_a / det, det_b / det, det_c / det, int(n)


def find_pockets(frame: DepthFrame,
                 face_z: float) -> Optional[Tuple[float, float]]:
    """Two columns deeper than the face — the EUR-pallet pockets.

    Returns (u_mid, v_mid) of the pocket pair, or None.
    """
    v0 = frame.height // 3
    v1 = (2 * frame.height) // 3
    deeper = []
    for u in range(frame.width):
        med = _col_median(frame, u, v0, v1)
        if med is not None and med > face_z + 0.04:
            deeper.append(u)
    if len(deeper) < 2:
        return None
    # Split into left/right clusters at the median u of deeper columns.
    mid = deeper[len(deeper) // 2]
    left = [u for u in deeper if u < mid]
    right = [u for u in deeper if u >= mid]
    if not left or not right:
        return None
    u_mid = 0.5 * (sum(left) / len(left) + sum(right) / len(right))
    v_mid = 0.5 * (v0 + v1)
    return u_mid, v_mid


def observe(frame: DepthFrame) -> Optional[PocketObservation]:
    plane = fit_face_plane(frame)
    if plane is None:
        return None
    a, b, c, n = plane
    pockets = find_pockets(frame, c)
    if pockets is None:
        return None
    u_mid, v_mid = pockets
    return PocketObservation(
        face_z=c, face_a=a, face_b=b,
        pocket_u=u_mid, pocket_v=v_mid,
        inliers=n, valid=frame.valid_count())


def propose(frame: DepthFrame,
            tag_u: Optional[float] = None,
            tag_v: Optional[float] = None,
            tag_z: Optional[float] = None,
            ttl_ms: int = DEFAULT_TTL_MS) -> Optional[object]:
    """Build a DOCK_TARGET_REFINE vs the tag-derived target.

    tag_* default to the image centre / fitted face — the shadow
    node's stand-in when no AprilTag pose is latched. That is not
    ground truth and is not a command.
    """
    obs = observe(frame)
    if obs is None:
        return None
    tu = frame.cx if tag_u is None else float(tag_u)
    tv = frame.cy if tag_v is None else float(tag_v)
    tz = obs.face_z if tag_z is None else float(tag_z)
    # Optical: +x right, +y down, +z forward. Dock delta in metres:
    # dx along the approach (depth residual), dy lateral, dtheta from
    # the horizontal slope of the face (a in z = a x + …).
    dx = obs.face_z - tz
    dy = ((obs.pocket_u - tu) / frame.fx) * obs.face_z
    dtheta = math.atan(obs.face_a)
    conf = min(1.0, obs.inliers / max(1.0, 0.35 * frame.width * frame.height))
    extra = {
        "face_z": obs.face_z,
        "pocket_u": obs.pocket_u,
        "pocket_v": obs.pocket_v,
        "inliers": obs.inliers,
        "algorithm": "classical_plane_pockets",
    }
    return make_proposal(
        KIND_DOCK_TARGET_REFINE,
        PoseDelta(dx, dy, dtheta),
        conf,
        Evidence(frame.frame_id, frame.sim_stamp, SENSOR_PALLET_CAM),
        int(ttl_ms),
        extra=extra)


def make_plane_depth(width: int, height: int, z0: float,
                     a: float = 0.0, b: float = 0.0,
                     pockets: Sequence[Tuple[int, int, int, int, float]] = (),
                     fx: float = DEFAULT_FX, fy: float = DEFAULT_FY) -> DepthFrame:
    """Synthetic depth for tests. pockets are (u0,u1,v0,v1,z)."""
    cx, cy = width / 2.0, height / 2.0
    buf = []
    for v in range(height):
        for u in range(width):
            x = (u - cx) / fx
            y = (v - cy) / fy
            z = z0 + a * x + b * y
            for u0, u1, v0, v1, pz in pockets:
                if u0 <= u < u1 and v0 <= v < v1:
                    z = pz
                    break
            buf.append(z)
    return DepthFrame(width, height, tuple(buf), fx, fy, cx, cy,
                      frame_id="synth", sim_stamp=1.0)
