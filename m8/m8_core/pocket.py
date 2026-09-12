"""Classical C1 pocket pose - floor-anchored ROI + inverse-depth face plane.

ARCHITECTURE.md §6: a scorable baseline, no learned weights. Input is
a depth buffer (metres, 32FC1 layout). Output is a DOCK_TARGET_REFINE
Proposal or None if the frame cannot support a pose.

WHY THIS IS NOT THE A1 GEOMETRY. `EVIDENCE_M8_E1.md` measured the A1
baseline on the plant: the plane it fitted was the FLOOR at all three
ranges (the pallet face is 2.9-6.6 % of the fixed central ROI), it
returned no pose at 2.245 m and 1.5 m, and the pose it did return at
1.0 m was 0.9223 m off with +0.3823 rad of "face yaw" on a square
pallet. Two causes were named there and both are removed here:

  1. THE MODEL. ``z = a*x + b*y + c`` is not the equation of a plane in
     pixel coordinates. For a 3-D plane n.P = D with P = (x*Z, y*Z, Z),
     ``1/Z = (n_x*x + n_y*y + n_z)/D`` - a plane is linear in INVERSE
     depth, never in depth. The floor seen 30 deg down spans roughly
     1.4-5.7 m across one image; no straight line in z goes near it, so
     the residual A1's second pass trimmed on meant nothing. `Plane`
     below carries (alpha, beta, gamma) and is exact for any plane.

  2. THE ROI. A fixed central band is whatever the camera points at,
     and a forklift pallet camera pitched down points at the floor. The
     ROI here is DERIVED per frame: fit the dominant plane (which is
     the floor, and that is now a feature), keep what stands ABOVE it,
     take the largest blob, fit the near surface inside it, and refuse
     unless that surface is pallet-sized IN METRES.

The floor plane is not only rejected, it is used: its normal is the
world vertical, which is what makes `face_yaw` a real yaw instead of
the mount-dependent ``atan(dz/dx)`` proxy A1 reported.

The delta is vs a tag-derived target the caller supplies. Ground truth
is not an input. This module does not claim a plant rms - E1 does.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

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

# --- what this baseline is allowed to assume about a pallet --------------
# m5_ver3/gazebo/pallets/pallet_s5.sdf: face 1.200 m wide and 0.144 m
# tall, two 0.160 m pockets 0.560 m between centres. The windows below
# are those numbers with slack for occlusion and depth noise. They are a
# REFUSAL surface - widening one to make a frame pass is tuning, and a
# tuned number belongs in an EVIDENCE file, not here.
PALLET_FACE_WIDTH_M = (0.60, 1.90)
PALLET_FACE_HEIGHT_M = (0.05, 0.60)
POCKET_SPAN_M = (0.35, 0.80)
POCKET_WIDTH_M = (0.04, 0.45)

# Segmentation. Strides are adapted to the frame in _strides().
COARSE_STRIDE = 4
FACE_STRIDE = 2
DOMINANT_TRIM_PASSES = 3
DOMINANT_TRIM_M = 0.05
OBJECT_CLEARANCE_M = 0.06      # nearer than the dominant plane => stands on it
MIN_BLOB_CELLS = 6
# How many standing objects to try before giving up. A warehouse aisle
# puts walls, racking and the truck's own forks above the floor beside
# the pallet, and the pallet is not the biggest of them.
MAX_BLOB_CANDIDATES = 8
MIN_PLANE_POINTS = 12
MIN_FACE_POINTS = 40

# The blob is not only the face. A pallet seen from a camera 1.10 m up
# shows its DECK TOP, a horizontal rectangle 0.8 m deep that meets the
# face along its top edge and outnumbers it 2.4:1 at staging and 4.2:1
# at 1.0 m. Two things keep it out of the fit:
#   * the top of anything standing on a floor is its deck or its lid.
#     It is horizontal, it is not the face, and it is the only part of
#     the object at the object's own maximum height - so the top
#     DECK_CUT_M of the blob's height range is dropped outright.
#   * what is left is SEEDED on the MODE of horizontal distance from the
#     camera, where a vertical face is one value, a horizontal surface
#     is a ramp, and anything standing in front of the pallet is a
#     second, smaller peak. Least squares over two parallel surfaces
#     0.08 m apart returns a tilted plane through the middle that then
#     holds under trimming, so the mode has to be found before any fit.
#     Trimming after the seed is on perpendicular distance to the plane,
#     never along the ray: a surface seen edge-on is metres away along
#     the ray while being millimetres off the plane.
DECK_CUT_M = 0.03
FACE_SEED_BIN_M = 0.02
FACE_SEED_BAND_M = 0.06
FACE_TRIM_PASSES = 3
FACE_DEEPER_RESIDUAL_M = 0.05
# The floor falls away as the image goes down; a standing face does not.
# dz/dy of the floor on this rig is about -3.8; of the face, +0.7...+1.5.
FACE_MIN_DZ_DY = -0.5

POCKET_MIN_DEPTH_M = 0.04
MIN_POCKET_COLS = 3

# --- the range window ----------------------------------------------------
# A dock approach happens inside a known envelope of HORIZONTAL distance
# from the camera: staging is 2.245 m and the refine regime is the last
# two metres. Anything outside it is not the pallet this dock is about,
# and it is excluded before any fit sees it. These are mission geometry
# and camera geometry. THEY ARE NOT DERIVED FROM BENCH TRUTH - the bench
# knows where the pallet is and this module must never be told.
DOCK_ENVELOPE_M = (0.40, 3.20)
# A live AprilTag gives an expected range. When the caller passes one the
# window tightens to this much either side of it. Tagless docking gets
# the envelope above and nothing else (R1: tagged pallets first).
TAG_WINDOW_M = 0.40
# EVIDENCE_M8_E1 measured the failure regime: the face was 2.9-6.6 % of
# the points A1 fitted. The face must be a large share of what is left
# inside the window after the deck cut, an order clear of that band.
FACE_INLIER_FRAC_MIN = 0.35
# Heights above the floor a fork travels through. The pocket mouth is
# 0.122 m tall. The upper bound is also capped at the segmentation's own
# deck-cut height: the deck top of a EUR pallet sits at 0.144 m, inside
# any band generous enough for a fork, and the deck is most of the blob -
# left in, it buries the fraction (0.035 where the obstruction was 20 %).
FORK_BAND_M = (0.02, 0.20)

MIN_INV_DEPTH = 1e-6


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

    def x_of(self, u: float) -> float:
        return (u - self.cx) / self.fx

    def y_of(self, v: float) -> float:
        return (v - self.cy) / self.fy

    def valid_count(self) -> int:
        return sum(1 for z in self.depths if math.isfinite(z) and z > 0.0)


@dataclass(frozen=True)
class Plane:
    """``alpha*x + beta*y + gamma = 1/Z``. Exact for any 3-D plane.

    The 3-D plane is ``alpha*X + beta*Y + gamma*Z = 1``, so
    (alpha, beta, gamma) is its normal scaled by 1/distance.
    """

    alpha: float
    beta: float
    gamma: float
    n: int

    def inv_depth_at(self, x: float, y: float) -> float:
        return self.alpha * x + self.beta * y + self.gamma

    def depth_at(self, x: float, y: float) -> Optional[float]:
        inv = self.inv_depth_at(x, y)
        if inv <= MIN_INV_DEPTH:
            return None
        return 1.0 / inv

    def dz_dx(self, x: float, y: float) -> Optional[float]:
        inv = self.inv_depth_at(x, y)
        if inv <= MIN_INV_DEPTH:
            return None
        return -self.alpha / (inv * inv)

    def dz_dy(self, x: float, y: float) -> Optional[float]:
        inv = self.inv_depth_at(x, y)
        if inv <= MIN_INV_DEPTH:
            return None
        return -self.beta / (inv * inv)

    def normal(self) -> Tuple[float, float, float]:
        n = math.sqrt(self.alpha ** 2 + self.beta ** 2 + self.gamma ** 2)
        if n <= 0.0:
            return (0.0, 0.0, 1.0)
        return (self.alpha / n, self.beta / n, self.gamma / n)


@dataclass(frozen=True)
class FaceSegment:
    """The pallet face this frame supports, and the ROI it was found in."""

    face: Plane
    floor: Optional[Plane]
    u0: int
    u1: int
    v0: int
    v1: int
    inliers: int
    width_m: float
    height_m: float
    up: Tuple[float, float, float]
    # The whole standing object, not just its face. An obstruction in
    # the fork path is nearer than the face and therefore projects
    # BELOW it; at 1.0 m it misses the face rows entirely, so anything
    # that searched only (u0, u1, v0, v1) would never see it.
    blob: Tuple[int, int, int, int] = (0, 0, 0, 0)
    # Height above the floor at which the deck was cut away, or None
    # when the frame has no floor to measure heights against.
    height_cut: Optional[float] = None
    # Share of the windowed, deck-cut candidates that the face plane
    # holds. E1's failure regime was 2.9-6.6 %.
    inlier_frac: float = 0.0
    # The horizontal-distance window this segmentation was allowed.
    window: Tuple[float, float] = DOCK_ENVELOPE_M

    def centre_px(self) -> Tuple[float, float]:
        return (0.5 * (self.u0 + self.u1), 0.5 * (self.v0 + self.v1))


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
    # Added by the C1/C2 plane+ROI fix: the ROI is derived per frame, so
    # the benches have to be able to log which one was actually used.
    face_yaw: float = 0.0
    roi_u0: int = 0
    roi_u1: int = 0
    roi_v0: int = 0
    roi_v1: int = 0
    face_width_m: float = 0.0
    face_height_m: float = 0.0
    pocket_span_m: float = 0.0
    floor_found: bool = False
    inlier_frac: float = 0.0
    window_lo: float = 0.0
    window_hi: float = 0.0


# --------------------------------------------------------------- linear
def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _col_median(frame: DepthFrame, u: int, v0: int, v1: int) -> Optional[float]:
    vals = []
    for v in range(v0, v1):
        z = frame.at(u, v)
        if z is not None:
            vals.append(z)
    if len(vals) < 2:
        return None
    return _median(vals)


def _least_squares_plane(points: Sequence[Tuple[float, float, float]],
                         min_n: int = MIN_PLANE_POINTS
                         ) -> Optional[Tuple[float, float, float, int]]:
    """Least-squares w = a x + b y + c. points are (x, y, w).

    w is INVERSE depth everywhere in this module - see `Plane`.
    """
    sxx = sxy = sx = syy = sy = sz = sxz = syz = n = 0.0
    for x, y, z in points:
        sxx += x * x
        sxy += x * y
        sx += x
        syy += y * y
        sy += y
        sz += z
        sxz += x * z
        syz += y * z
        n += 1.0
    if n < min_n:
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


def _fit_plane(samples: Sequence[Tuple[float, float, float]],
               min_n: int = MIN_PLANE_POINTS) -> Optional[Plane]:
    """samples are (x, y, z_metres); the fit is on (x, y, 1/z)."""
    inv = [(x, y, 1.0 / z) for x, y, z in samples if z > 0.0]
    fitted = _least_squares_plane(inv, min_n)
    if fitted is None:
        return None
    a, b, c, n = fitted
    return Plane(a, b, c, n)


def _residuals_m(samples: Sequence[Tuple[float, float, float]],
                 plane: Plane) -> List[Tuple[Tuple[float, float, float], float]]:
    out = []
    for s in samples:
        pz = plane.depth_at(s[0], s[1])
        if pz is None:
            continue
        out.append((s, s[2] - pz))
    return out


def _strides(frame: DepthFrame) -> Tuple[int, int]:
    coarse = max(1, min(COARSE_STRIDE, frame.width // 80))
    fine = max(1, min(FACE_STRIDE, frame.width // 160))
    return coarse, fine


def _sample(frame: DepthFrame, stride: int) -> List[Tuple[float, float, float]]:
    pts = []
    for v in range(0, frame.height, stride):
        y = frame.y_of(v)
        for u in range(0, frame.width, stride):
            z = frame.at(u, v)
            if z is None:
                continue
            pts.append((frame.x_of(u), y, z))
    return pts


# ---------------------------------------------------------- segmentation
def dominant_plane(frame: DepthFrame) -> Optional[Plane]:
    """The plane most of the frame lies on. On the plant that is the floor.

    Trimmed least squares in inverse depth: each pass keeps the points
    within max(5 cm, the median absolute residual) of the current plane,
    so the fit walks onto the majority surface instead of averaging the
    surfaces together the way A1's single unweighted pass did.
    """
    coarse, _ = _strides(frame)
    samples = _sample(frame, coarse)
    plane = _fit_plane(samples)
    if plane is None:
        return None
    for _ in range(DOMINANT_TRIM_PASSES):
        scored = _residuals_m(samples, plane)
        if len(scored) < MIN_PLANE_POINTS:
            break
        tol = max(DOMINANT_TRIM_M, _median([abs(r) for _s, r in scored]))
        kept = [s for s, r in scored if abs(r) <= tol]
        refit = _fit_plane(kept)
        if refit is None:
            break
        plane = refit
        samples = kept
    return plane


def range_window(expected_range: Optional[float] = None
                 ) -> Tuple[float, float]:
    """(lo, hi) horizontal distance a pallet is allowed to be at.

    `expected_range` is HORIZONTAL distance along the floor, not optical
    depth - the two differ by 1/cos(mount pitch), about 15 % on this rig,
    and quietly feeding one where the other is meant is the kind of thing
    that reads fine until it does not. A caller holding a tag POSE should
    convert before calling.

    With no `expected_range` this is the dock envelope and nothing else -
    that is the tagless case. With one, from a live tag, it tightens
    around it, and it is clamped to the envelope either way: a tag can
    narrow this window and can never widen it. Never from ground truth:
    `bench/plant.py` knows where the pallet is and must not tell this
    module.
    """
    lo, hi = DOCK_ENVELOPE_M
    if expected_range is None:
        return lo, hi
    return (max(lo, float(expected_range) - TAG_WINDOW_M),
            min(hi, float(expected_range) + TAG_WINDOW_M))


def _blob_candidates(frame: DepthFrame, floor: Plane, stride: int,
                     fwd: Tuple[float, float, float],
                     window: Tuple[float, float],
                     seed_px: Optional[Tuple[float, float]] = None
                     ) -> List[Tuple[int, int, int, int]]:
    """Bounding boxes of things standing above the floor, in the window.

    ALL of them, best first - not just the biggest. A pallet at staging
    is 2.9 % of the frame and a warehouse wall behind it is not; taking
    only the largest component picked the wall on the plant, which then
    failed the pallet-size gate and the frame was refused with a pallet
    in plain view. The gates below decide which candidate is a pallet;
    this function's job is not to decide it early.

    `seed_px` is where a live tag says the target is. It is applied LAST
    and only to ORDER the candidates - it never widens the window and
    never rescues a frame that had no candidate to choose from.
    """
    lo, hi = window
    cells: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for v in range(0, frame.height, stride):
        y = frame.y_of(v)
        for u in range(0, frame.width, stride):
            z = frame.at(u, v)
            if z is None:
                continue
            x = frame.x_of(u)
            d_h = z * (x * fwd[0] + y * fwd[1] + fwd[2])
            if d_h < lo or d_h > hi:
                continue
            pz = floor.depth_at(x, y)
            if pz is None:
                continue
            if pz - z > OBJECT_CLEARANCE_M:
                cells[(u // stride, v // stride)] = (u, v)
    if len(cells) < MIN_BLOB_CELLS:
        return []
    seen = set()
    comps: List[List[Tuple[int, int]]] = []
    for start in cells:
        if start in seen:
            continue
        comp = [start]
        seen.add(start)
        stack = [start]
        while stack:
            i, j = stack.pop()
            for nb in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if nb in cells and nb not in seen:
                    seen.add(nb)
                    comp.append(nb)
                    stack.append(nb)
        comps.append(comp)
    comps = [c for c in comps if len(c) >= MIN_BLOB_CELLS]
    if not comps:
        return []
    comps.sort(key=len, reverse=True)
    if seed_px is not None:
        key = (int(seed_px[0]) // stride, int(seed_px[1]) // stride)

        def rank(comp):
            if key in comp:
                return (0, -len(comp))
            us_ = [cells[c][0] for c in comp]
            vs_ = [cells[c][1] for c in comp]
            return (1, math.hypot(sum(us_) / len(us_) - seed_px[0],
                                  sum(vs_) / len(vs_) - seed_px[1]))

        comps.sort(key=rank)
    boxes = []
    for comp in comps[:MAX_BLOB_CANDIDATES]:
        us = [cells[c][0] for c in comp]
        vs = [cells[c][1] for c in comp]
        # One stride of slack each way: the coarse grid clips the edges.
        boxes.append((max(0, min(us) - stride),
                      min(frame.width, max(us) + 2 * stride),
                      max(0, min(vs) - stride),
                      min(frame.height, max(vs) + 2 * stride)))
    return boxes


def blob_touches_border(frame: DepthFrame,
                        bbox: Tuple[int, int, int, int]) -> bool:
    """Does this standing object run off the edge of the image.

    A clipped object's width and height in metres are LOWER BOUNDS, and
    the plane fitted to it is fitted to a part, so any claim about the
    WHOLE object - its size, its yaw, whether it has two pockets - is a
    claim the frame does not support. `m8_core.abort` is the caller that
    acts on this; nothing in the segmentation is changed by it.

    `_blob_candidates` clamps a box to the frame, so a blob that reached
    an edge sits exactly on 0 or on width / height.
    """
    u0, u1, v0, v1 = bbox
    return bool(u0 <= 0 or v0 <= 0 or u1 >= frame.width or v1 >= frame.height)


def _refuse(trace: Optional[Dict[str, object]], why: str) -> None:
    """Name the gate that stopped this frame, then return None.

    Every refusal in this module goes through here. The plant benches
    log the name, because "no pose" and "no pose BECAUSE the face was
    4 % of what was fitted" are not the same finding.
    """
    if trace is not None and "refused" not in trace:
        trace["refused"] = why
    return None


def _horizontal_forward(up: Tuple[float, float, float]
                        ) -> Tuple[float, float, float]:
    """The optical axis with the vertical component taken out of it."""
    d = up[2]
    f = (-d * up[0], -d * up[1], 1.0 - d * up[2])
    n = math.sqrt(f[0] ** 2 + f[1] ** 2 + f[2] ** 2)
    if n <= 1e-9:
        return (0.0, 0.0, 1.0)
    return (f[0] / n, f[1] / n, f[2] / n)


def _perp_residual(plane: Plane, x: float, y: float, z: float,
                   norm: float) -> Optional[float]:
    """Signed distance from the point to the plane, in metres.

    ``alpha*X + beta*Y + gamma*Z = 1`` with P = (x*z, y*z, z) gives
    ``z*inv_depth - 1`` for the unnormalised residual; dividing by the
    norm of (alpha, beta, gamma) makes it a distance. Perpendicular, not
    along-ray: a surface seen edge-on is metres away along the ray while
    being millimetres off the plane.
    """
    if norm <= 1e-12:
        return None
    return (z * plane.inv_depth_at(x, y) - 1.0) / norm


def _fit_face(frame: DepthFrame, floor: Optional[Plane],
              bbox: Tuple[int, int, int, int], stride: int,
              up: Tuple[float, float, float],
              window: Tuple[float, float],
              trace: Optional[Dict[str, object]] = None
              ) -> Optional[Tuple[Plane, int, Tuple[int, int, int, int],
                                  Optional[float], float]]:
    """Fit the pallet face inside bbox and return its own pixel box.

    Three gates, in order. The RANGE WINDOW drops everything outside the
    dock envelope before a fit exists. The DECK CUT drops the top of the
    object. What is left is seeded on horizontal distance (the face is
    one value, the deck top is a 0.8 m ramp behind it) and trimmed on
    perpendicular distance; an unseeded least-squares pass lands on the
    deck, which has 2.4x the pixels at staging and touches the face, so
    nothing that trims on depth alone can walk off it.

    Returns the inlier FRACTION as well as the count: E1 measured the
    failure regime as the face being 2.9-6.6 % of what was fitted, and a
    count alone cannot tell that apart from a big frame.
    """
    u0, u1, v0, v1 = bbox
    lo, hi = window
    fwd = _horizontal_forward(up)
    floor_norm = 0.0
    if floor is not None:
        floor_norm = math.sqrt(floor.alpha ** 2 + floor.beta ** 2
                               + floor.gamma ** 2)
    raw = []
    for v in range(v0, v1, stride):
        y = frame.y_of(v)
        for u in range(u0, u1, stride):
            z = frame.at(u, v)
            if z is None:
                continue
            x = frame.x_of(u)
            d_h = z * (x * fwd[0] + y * fwd[1] + fwd[2])
            if d_h < lo or d_h > hi:
                continue
            height = 0.0
            if floor is not None:
                pz = floor.depth_at(x, y)
                if pz is None or pz - z <= OBJECT_CLEARANCE_M:
                    continue
                r = _perp_residual(floor, x, y, z, floor_norm)
                if r is None:
                    continue
                height = -r
            raw.append((x, y, z, u, v, d_h, height))
    if trace is not None:
        trace["in_window"] = len(raw)
    if len(raw) < MIN_FACE_POINTS:
        return _refuse(trace, "too_few_points_in_window")
    height_cut = None
    if floor is not None:
        heights = sorted(p[6] for p in raw)
        top = heights[int(0.95 * (len(heights) - 1))] - DECK_CUT_M
        under = [p for p in raw if p[6] <= top]
        if len(under) >= MIN_FACE_POINTS:
            raw = under
            height_cut = top
    candidates = len(raw)
    if trace is not None:
        trace["after_deck_cut"] = candidates
        trace["height_cut"] = height_cut
    counts: Dict[int, int] = {}
    for p in raw:
        key = int(math.floor(p[5] / FACE_SEED_BIN_M))
        counts[key] = counts.get(key, 0) + 1
    mode = min((k for k in counts if counts[k] == max(counts.values())))
    near = (mode + 0.5) * FACE_SEED_BIN_M
    seed = [p for p in raw if abs(p[5] - near) <= FACE_SEED_BAND_M]
    # Enough points to DEFINE a plane is not the same bar as enough to
    # TRUST one. The seed is one mode-wide slice of a face that a yaw
    # spreads across several slices, so it is held to the solver's own
    # minimum; MIN_FACE_POINTS is the gate on the final inlier set.
    if trace is not None:
        trace["seed_range_m"] = near
        trace["seed_points"] = len(seed)
    plane = _fit_plane([(p[0], p[1], p[2]) for p in seed], MIN_PLANE_POINTS)
    if plane is None:
        return _refuse(trace, "seed_plane_unsolvable")
    inliers = seed
    for _ in range(FACE_TRIM_PASSES):
        norm = math.sqrt(plane.alpha ** 2 + plane.beta ** 2 + plane.gamma ** 2)
        kept = []
        for p in raw:
            r = _perp_residual(plane, p[0], p[1], p[2], norm)
            if r is not None and abs(r) <= FACE_DEEPER_RESIDUAL_M:
                kept.append(p)
        refit = _fit_plane([(p[0], p[1], p[2]) for p in kept], MIN_PLANE_POINTS)
        if refit is None:
            break
        plane = refit
        inliers = kept
    frac = len(inliers) / float(candidates)
    if trace is not None:
        trace["face_inliers"] = len(inliers)
        trace["inlier_frac"] = frac
    if len(inliers) < MIN_FACE_POINTS:
        return _refuse(trace, "too_few_face_inliers")
    if frac < FACE_INLIER_FRAC_MIN:
        return _refuse(trace, "face_is_too_small_a_share")
    us = [p[3] for p in inliers]
    vs = [p[4] for p in inliers]
    box = (min(us), max(us) + 1, min(vs), max(vs) + 1)
    return plane, len(inliers), box, height_cut, frac


def _world_up(floor: Optional[Plane]) -> Tuple[float, float, float]:
    """World vertical in the optical frame - the floor's own normal.

    Without a floor the frame cannot say which way is up, so the level
    camera (+Y down) is assumed and named rather than guessed at.
    """
    if floor is None:
        return (0.0, -1.0, 0.0)
    nx, ny, nz = floor.normal()
    return (-nx, -ny, -nz)


def face_yaw(face: Plane, up: Tuple[float, float, float]) -> float:
    """Yaw of the face about the world vertical; camera-forward is zero.

    A1 reported ``atan(dz/dx)``, which is the true yaw multiplied by
    roughly ``D / cos^2(mount pitch)`` - a scale the module cannot know.
    With the floor's normal in hand the yaw is a real angle: project the
    face normal and the optical axes onto the horizontal plane and take
    the angle between them.
    """
    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def unit(a):
        n = math.sqrt(dot(a, a))
        if n <= 1e-12:
            return None
        return (a[0] / n, a[1] / n, a[2] / n)

    def flatten(a):
        d = dot(a, up)
        return unit((a[0] - d * up[0], a[1] - d * up[1], a[2] - d * up[2]))

    n_face = flatten(face.normal())
    forward = flatten((0.0, 0.0, 1.0))
    right = flatten((1.0, 0.0, 0.0))
    if n_face is None or forward is None or right is None:
        return 0.0
    return -math.atan2(dot(n_face, right), dot(n_face, forward))


def segment(frame: DepthFrame,
            expected_range: Optional[float] = None,
            tag_u: Optional[float] = None,
            tag_v: Optional[float] = None,
            trace: Optional[Dict[str, object]] = None
            ) -> Optional[FaceSegment]:
    """Derive the pallet-face ROI for this frame, or refuse.

    ORDER MATTERS and it is the order of the brief. The range window
    comes first and is the only gate a tagless dock gets. The floor
    model comes next. The tag, if there is one, comes LAST and only
    chooses between candidate blobs - it cannot widen the window, it
    cannot invent a face, and `expected_range` is a tag reading, never
    a ground-truth range.

    Every exit is a named refusal the caller can act on: no dominant
    plane; nothing standing above it inside the window; no near surface
    in the blob; a face that is too small a share of what was fitted
    (E1's failure regime was 2.9-6.6 %); a surface that falls away
    downward like a floor; a surface that is not pallet-sized in metres.
    Refusing is the correct output - E1's 0.92 m pose came from a
    pipeline with none of these.
    """
    if frame.width <= 0 or frame.height <= 0:
        return _refuse(trace, "empty_frame")
    coarse, fine = _strides(frame)
    window = range_window(expected_range)
    if trace is not None:
        trace["window_m"] = window
        trace["valid_px"] = frame.valid_count()
    floor = dominant_plane(frame)
    if floor is None:
        return _refuse(trace, "no_dominant_plane")
    if trace is not None:
        trace["floor_dz_dy"] = floor.dz_dy(0.0, 0.0)
        trace["floor_depth_on_axis_m"] = floor.depth_at(0.0, 0.0)
        trace["floor_points"] = floor.n
    seed_px = None
    if tag_u is not None and tag_v is not None:
        seed_px = (float(tag_u), float(tag_v))
    up = _world_up(floor)
    boxes = _blob_candidates(frame, floor, coarse, _horizontal_forward(up),
                             window, seed_px)
    if trace is not None:
        trace["candidates"] = len(boxes)
        trace["tag_seeded"] = seed_px is not None
    attempts: List[Tuple[Optional[Plane], Tuple[int, int, int, int]]] = [
        (floor, b) for b in boxes]
    if not attempts:
        # Nothing stands above the dominant plane inside the window: the
        # dominant plane is the only surface in view, so it is the
        # candidate face and the ROI is the frame. `up` is then unknown -
        # see _world_up - and the sign test on b below is what rejects a
        # floor that reached here.
        attempts = [(None, (0, frame.width, 0, frame.height))]
    last: Dict[str, object] = {}
    # EVERY candidate's refusal, not only the last one's. A caller that
    # has to choose a WORD for "no face" needs the whole set: "the only
    # thing standing here is not pallet-shaped" and "the pallet is here
    # and merged with the truck's own forks" are both one refusal each,
    # and they argue for opposite words. `standing` is False for the
    # floor fallback, which is the frame itself and not a clipped object.
    refusals: List[Dict[str, object]] = []
    for index, (floor_for_fit, bbox) in enumerate(attempts):
        step: Dict[str, object] = {}
        seg = _try_candidate(frame, floor_for_fit, bbox, fine, window, step)
        if seg is not None:
            if trace is not None:
                trace.update(step)
                trace["refusals"] = refusals
                trace["candidate_used"] = index
            return seg
        refusals.append({"why": step.get("refused"), "blob": bbox,
                         "standing": floor_for_fit is not None})
        last = step
    if trace is not None:
        trace.update(last)
        trace["refusals"] = refusals
        trace["candidate_used"] = None
    return None


def _try_candidate(frame: DepthFrame, floor: Optional[Plane],
                   bbox: Tuple[int, int, int, int], fine: int,
                   window: Tuple[float, float],
                   trace: Dict[str, object]) -> Optional[FaceSegment]:
    """Fit one standing object and put it through every gate."""
    trace["blob"] = bbox
    up = _world_up(floor)
    fitted = _fit_face(frame, floor, bbox, fine, up, window, trace)
    if fitted is None:
        return None
    face, n_inliers, box, height_cut, frac = fitted
    u0, u1, v0, v1 = box
    x_c, y_c = frame.x_of(0.5 * (u0 + u1)), frame.y_of(0.5 * (v0 + v1))
    z_c = face.depth_at(x_c, y_c)
    if z_c is None or z_c <= 0.0:
        return _refuse(trace, "face_plane_behind_the_camera")
    # The sign test on b. `b` is dz/dy: on a floor the depth FALLS as the
    # image goes down (-3.8 on this rig), on a face standing on that
    # floor it rises (+0.7...+1.5). The tolerance below zero is for a
    # level camera, where a face reads exactly 0.
    dz_dy = face.dz_dy(x_c, y_c)
    width_m = (u1 - u0) / frame.fx * z_c
    height_m = (v1 - v0) / frame.fy * z_c
    trace["face_box"] = box
    trace["face_z_m"] = z_c
    trace["face_dz_dy"] = dz_dy
    trace["face_width_m"] = width_m
    trace["face_height_m"] = height_m
    if dz_dy is None or dz_dy < FACE_MIN_DZ_DY:
        return _refuse(trace, "candidate_falls_away_like_a_floor")
    if not (PALLET_FACE_WIDTH_M[0] <= width_m <= PALLET_FACE_WIDTH_M[1]):
        return _refuse(trace, "face_width_not_pallet_sized")
    if not (PALLET_FACE_HEIGHT_M[0] <= height_m <= PALLET_FACE_HEIGHT_M[1]):
        return _refuse(trace, "face_height_not_pallet_sized")
    return FaceSegment(face=face, floor=floor, u0=u0, u1=u1, v0=v0, v1=v1,
                       inliers=n_inliers, width_m=width_m,
                       height_m=height_m, up=up, blob=bbox,
                       height_cut=height_cut, inlier_frac=frac,
                       window=window)


# ------------------------------------------------------------- the pockets
def _runs(cols: Sequence[int], max_gap: int = 1) -> List[List[int]]:
    runs: List[List[int]] = []
    for u in sorted(cols):
        if runs and u - runs[-1][-1] <= max_gap + 1:
            runs[-1].append(u)
        else:
            runs.append([u])
    return runs


def find_pocket_pair(frame: DepthFrame, seg: FaceSegment,
                     trace: Optional[Dict[str, object]] = None
                     ) -> Optional[Tuple[float, float, float]]:
    """Two pocket-wide columns of depth behind the face, 0.56 m apart.

    Returns (u_mid, v_mid, span_m) or None. A1 accepted ANY two clusters
    deeper than its plane, which is how the pallet face itself - deeper
    than the floor plane at its own rows - was reported as a pocket pair
    at 1.0 m (EVIDENCE_M8_E1, "What C1 actually fitted").
    """
    v_ref = frame.y_of(0.5 * (seg.v0 + seg.v1))
    deeper = []
    for u in range(seg.u0, seg.u1):
        med = _col_median(frame, u, seg.v0, seg.v1)
        if med is None:
            continue
        fz = seg.face.depth_at(frame.x_of(u), v_ref)
        if fz is None:
            continue
        if med > fz + POCKET_MIN_DEPTH_M:
            deeper.append(u)
    runs = [r for r in _runs(deeper) if len(r) >= MIN_POCKET_COLS]
    if trace is not None:
        trace["deeper_cols"] = len(deeper)
        trace["pocket_runs"] = len(runs)
    if len(runs) < 2:
        return _refuse(trace, "fewer_than_two_pocket_runs")
    runs.sort(key=len, reverse=True)
    pair = sorted(runs[:2], key=lambda r: r[0])
    left, right = pair
    u_left = sum(left) / len(left)
    u_right = sum(right) / len(right)
    u_mid = 0.5 * (u_left + u_right)
    z_ref = seg.face.depth_at(frame.x_of(u_mid), v_ref)
    if z_ref is None or z_ref <= 0.0:
        return None
    span_m = (u_right - u_left) / frame.fx * z_ref
    if trace is not None:
        trace["pocket_span_m"] = span_m
    if not (POCKET_SPAN_M[0] <= span_m <= POCKET_SPAN_M[1]):
        return _refuse(trace, "pocket_span_wrong")
    for run in pair:
        w_m = len(run) / frame.fx * z_ref
        if not (POCKET_WIDTH_M[0] <= w_m <= POCKET_WIDTH_M[1]):
            return _refuse(trace, "pocket_width_wrong")
    vs = []
    for run in pair:
        for u in run:
            for v in range(seg.v0, seg.v1):
                z = frame.at(u, v)
                if z is None:
                    continue
                fz = seg.face.depth_at(frame.x_of(u), frame.y_of(v))
                if fz is not None and z > fz + POCKET_MIN_DEPTH_M:
                    vs.append(v)
    if not vs:
        return None
    return u_mid, float(_median(vs)), span_m


def fork_path_fraction(frame: DepthFrame, seg: FaceSegment,
                       nearer_by: float) -> float:
    """Share of the FORK BAND that is obstructed, read off the floor model.

    This is the test `EVIDENCE_M8_E3.md` caught A1 getting wrong. A1
    compared column depths with `c`, the intercept of a plane fitted to
    a fixed band - which was the floor - so "nearer than the face" meant
    "nearer than the floor's own average" and fired on range, not on
    obstruction. Nothing here reads an intercept.

    Every quantity is in the floor's own model:
      * HEIGHT above the floor plane, so the band a fork travels through
        (FORK_BAND_M) can be named in metres. The floor itself is below
        the band and the deck top is above it, so neither can vote.
      * HORIZONTAL DISTANCE along the floor, so "in front of the face"
        is a distance on the ground and not a depth along a ray. A bar
        in front of the face projects BELOW the face in the image - at
        1.0 m it leaves the face box entirely - which is why the region
        searched is the whole blob.

    Without a floor plane there is no model to read and the answer is
    0.0: C2 must not invent an obstruction out of a frame it cannot
    measure heights in.
    """
    if seg.floor is None:
        return 0.0
    u0, u1, v0, v1 = seg.blob
    if u1 <= u0 or v1 <= v0:
        u0, u1, v0, v1 = seg.u0, seg.u1, seg.v0, seg.v1
    _coarse, stride = _strides(frame)
    fwd = _horizontal_forward(seg.up)
    floor_norm = math.sqrt(seg.floor.alpha ** 2 + seg.floor.beta ** 2
                           + seg.floor.gamma ** 2)
    lo, hi = FORK_BAND_M
    if seg.height_cut is not None:
        hi = min(hi, seg.height_cut)
    blocked = 0
    total = 0
    for v in range(v0, v1, stride):
        y = frame.y_of(v)
        for u in range(u0, u1, stride):
            z = frame.at(u, v)
            if z is None:
                continue
            x = frame.x_of(u)
            # Stand on the floor first. Depth noise puts a few
            # millimetres of scatter on every floor pixel, so a height
            # band alone lets the floor itself into the denominator and
            # the fraction stops meaning anything.
            pz = seg.floor.depth_at(x, y)
            if pz is None or pz - z <= OBJECT_CLEARANCE_M:
                continue
            r = _perp_residual(seg.floor, x, y, z, floor_norm)
            if r is None:
                continue
            height = -r
            if height < lo or height > hi:
                continue
            d_h = z * (x * fwd[0] + y * fwd[1] + fwd[2])
            face_z = seg.face.depth_at(x, y)
            if face_z is None:
                continue
            face_d = face_z * (x * fwd[0] + y * fwd[1] + fwd[2])
            total += 1
            if d_h < face_d - nearer_by:
                blocked += 1
    if total == 0:
        return 0.0
    return blocked / float(total)


def fit_face_plane(frame: DepthFrame,
                   expected_range: Optional[float] = None
                   ) -> Optional[Tuple[float, float, float, int]]:
    """(dz/dx, dz/dy, depth) of the FACE plane on the optical axis, and n.

    The tuple shape is A1's so the benches keep reading the same three
    columns; what changed is that the plane is the pallet face found in
    a derived ROI inside the range window, instead of whatever filled a
    fixed central band.
    """
    seg = segment(frame, expected_range=expected_range)
    if seg is None:
        return None
    a = seg.face.dz_dx(0.0, 0.0)
    b = seg.face.dz_dy(0.0, 0.0)
    c = seg.face.depth_at(0.0, 0.0)
    if a is None or b is None or c is None:
        return None
    return a, b, c, seg.inliers


def observe(frame: DepthFrame,
            expected_range: Optional[float] = None,
            tag_u: Optional[float] = None,
            tag_v: Optional[float] = None,
            trace: Optional[Dict[str, object]] = None
            ) -> Optional[PocketObservation]:
    """The pocket-pair point, or None.

    `expected_range`, `tag_u` and `tag_v` are the live tag's reading if
    the caller has one. All three are optional and all three are only
    ever narrowing: tagless docking runs on the range window alone.
    """
    seg = segment(frame, expected_range=expected_range,
                  tag_u=tag_u, tag_v=tag_v, trace=trace)
    if seg is None:
        return None
    pair = find_pocket_pair(frame, seg, trace)
    if pair is None:
        return None
    u_mid, v_mid, span_m = pair
    x, y = frame.x_of(u_mid), frame.y_of(v_mid)
    z = seg.face.depth_at(x, y)
    a = seg.face.dz_dx(x, y)
    b = seg.face.dz_dy(x, y)
    if z is None or a is None or b is None:
        return None
    return PocketObservation(
        face_z=z, face_a=a, face_b=b,
        pocket_u=u_mid, pocket_v=v_mid,
        inliers=seg.inliers, valid=frame.valid_count(),
        face_yaw=face_yaw(seg.face, seg.up),
        roi_u0=seg.u0, roi_u1=seg.u1, roi_v0=seg.v0, roi_v1=seg.v1,
        face_width_m=seg.width_m, face_height_m=seg.height_m,
        pocket_span_m=span_m, floor_found=seg.floor is not None,
        inlier_frac=seg.inlier_frac, window_lo=seg.window[0],
        window_hi=seg.window[1])


def propose(frame: DepthFrame,
            tag_u: Optional[float] = None,
            tag_v: Optional[float] = None,
            tag_z: Optional[float] = None,
            ttl_ms: int = DEFAULT_TTL_MS,
            expected_range: Optional[float] = None) -> Optional[object]:
    """Build a DOCK_TARGET_REFINE vs the tag-derived target.

    tag_* default to the image centre / fitted face - the shadow
    node's stand-in when no AprilTag pose is latched. That is not
    ground truth and is not a command.

    `tag_z` is the target's optical DEPTH and is what the dx delta is
    measured against. `expected_range` is HORIZONTAL distance and is
    what narrows the range window. They are deliberately separate
    arguments: they are different quantities and passing one as the
    other is a 15 % error on this rig's mount. (tag_u, tag_v) also
    choose between candidate blobs, inside `observe`.
    """
    obs = observe(frame, expected_range=expected_range,
                  tag_u=tag_u, tag_v=tag_v)
    if obs is None:
        return None
    tu = frame.cx if tag_u is None else float(tag_u)
    tv = frame.cy if tag_v is None else float(tag_v)
    tz = obs.face_z if tag_z is None else float(tag_z)
    # Optical: +x right, +y down, +z forward. Dock delta in metres:
    # dx along the approach (depth residual), dy lateral, dtheta the
    # face yaw about the floor's normal.
    dx = obs.face_z - tz
    dy = ((obs.pocket_u - tu) / frame.fx) * obs.face_z
    dtheta = obs.face_yaw
    conf = min(1.0, obs.inliers / max(1.0, 0.02 * frame.width * frame.height))
    extra = {
        "face_z": obs.face_z,
        "pocket_u": obs.pocket_u,
        "pocket_v": obs.pocket_v,
        "inliers": obs.inliers,
        "roi": [obs.roi_u0, obs.roi_u1, obs.roi_v0, obs.roi_v1],
        "face_width_m": obs.face_width_m,
        "face_height_m": obs.face_height_m,
        "pocket_span_m": obs.pocket_span_m,
        "floor_found": obs.floor_found,
        "inlier_frac": obs.inlier_frac,
        "range_window_m": [obs.window_lo, obs.window_hi],
        "algorithm": "classical_floor_anchored_face",
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
    """Synthetic depth for tests. pockets are (u0,u1,v0,v1,z).

    One surface filling the frame: useful for the slot tests and for the
    no-floor fallback. It is NOT a pallet scene - see
    `m8_core.scene.make_scene_depth`, which is the one that reproduces
    what the plant camera actually sees.
    """
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
