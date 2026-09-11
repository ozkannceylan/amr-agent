"""A synthetic depth camera that sees what the plant camera sees.

WHY THIS FILE EXISTS. The A1 offline suite was green while the plant
was failing, because every offline fixture was one flat surface filling
the frame (`pocket.make_plane_depth`). There was no floor in any of
them, so the defect `EVIDENCE_M8_E1.md` measured - the fit lands on the
floor because the pallet face is 2.9-6.6 % of a fixed ROI - could not
appear offline. This renderer puts the floor back.

It is an INSTRUMENT, not a claim. It renders exact ray/plane
intersections plus Gaussian range noise; gz renders a GPU depth camera
on a mesh. Agreement here is necessary, never sufficient - E1 and E3 on
the plant are the score.

Conventions match `bench/geom.py`: optical frame is REP-103 (+X right,
+Y down, +Z forward), the camera sits `cam_height` above a flat floor
and is pitched `cam_pitch` radians down, without roll.

    up      = (0, -cos p, -sin p)      world vertical in optical
    forward = (0, -sin p,  cos p)      horizontal viewing direction
    right   = (1, 0, 0)

A point P is at height ``cam_height + P.up`` above the floor and at
horizontal distance ``P.forward`` from the camera.

Pallet dimensions default to `m5_ver3/gazebo/pallets/pallet_s5.sdf`:
1.200 m face, 0.144 m tall, 0.800 m deep, two pockets 0.160 m wide
(|lateral| 0.200-0.360) and 0.122 m tall. Named approximations: a
pocket is rendered as a hole - the ray passes through to the floor
behind rather than onto the pocket ceiling - and the deck top is a
single horizontal rectangle.
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple

from .pocket import DepthFrame

PLANT_WIDTH = 640
PLANT_HEIGHT = 480
PLANT_FX = 337.357          # EVIDENCE_M8_E1 "Camera": CameraInfo on the plant
PLANT_NOISE_M = 0.008       # model.sdf depth noise stddev
PLANT_CAM_HEIGHT = 1.10     # vehicle.cam_mount z
PLANT_CAM_PITCH = 0.5236    # vehicle.cam_mount pitch
PLANT_MAX_RANGE_M = 6.0

Vec3 = Tuple[float, float, float]


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


class Scene:
    """The rig's geometry, and the depth it produces for a ray."""

    def __init__(self,
                 cam_height: float = PLANT_CAM_HEIGHT,
                 cam_pitch: float = PLANT_CAM_PITCH,
                 face_distance: float = 2.245,
                 lateral: float = -0.400,
                 yaw: float = 0.0,
                 pallet: bool = True,
                 pockets: bool = True,
                 face_width: float = 1.200,
                 face_height: float = 0.144,
                 pallet_depth: float = 0.800,
                 pocket_inner: float = 0.200,
                 pocket_outer: float = 0.360,
                 pocket_height: float = 0.122,
                 obstacles: Sequence[Tuple[float, float, float, float, float]] = (),
                 wall_distance: Optional[float] = None,
                 max_range: float = PLANT_MAX_RANGE_M):
        self.h = float(cam_height)
        self.up: Vec3 = (0.0, -math.cos(cam_pitch), -math.sin(cam_pitch))
        self.fwd: Vec3 = (0.0, -math.sin(cam_pitch), math.cos(cam_pitch))
        self.right: Vec3 = (1.0, 0.0, 0.0)
        self.pallet = bool(pallet)
        self.pockets = bool(pockets)
        self.face_width = float(face_width)
        self.face_height = float(face_height)
        self.pallet_depth = float(pallet_depth)
        self.pocket_inner = float(pocket_inner)
        self.pocket_outer = float(pocket_outer)
        self.pocket_height = float(pocket_height)
        self.obstacles = tuple(obstacles)
        self.wall_distance = wall_distance
        self.max_range = float(max_range)
        # Face normal, rotated about the world vertical. up x fwd = -right.
        c, s = math.cos(yaw), math.sin(yaw)
        self.n: Vec3 = (self.fwd[0] * c - self.right[0] * s,
                        self.fwd[1] * c - self.right[1] * s,
                        self.fwd[2] * c - self.right[2] * s)
        # In-face horizontal direction; equals `right` when yaw is zero.
        self.t: Vec3 = (self.right[0] * c + self.fwd[0] * s,
                        self.right[1] * c + self.fwd[1] * s,
                        self.right[2] * c + self.fwd[2] * s)
        # Face centre at floor level.
        self.c0: Vec3 = _add(_add(_scale(self.right, lateral),
                                  _scale(self.fwd, face_distance)),
                             _scale(self.up, -self.h))
        self.d_face = _dot(self.n, self.c0)

    # ------------------------------------------------------------- truth
    def pocket_centre(self) -> Vec3:
        """Optical (X, Y, Z) of the pocket-pair centre - E1's truth point."""
        return _add(self.c0, _scale(self.up, 0.5 * self.pocket_height))

    def height_of(self, p: Vec3) -> float:
        return self.h + _dot(self.up, p)

    # ------------------------------------------------------------- render
    def _face_hit(self, r: Vec3) -> Optional[float]:
        if not self.pallet:
            return None
        den = _dot(self.n, r)
        if den <= 1e-9:
            return None
        z = self.d_face / den
        if z <= 0.0:
            return None
        p = _scale(r, z)
        s = _dot((p[0] - self.c0[0], p[1] - self.c0[1], p[2] - self.c0[2]), self.t)
        if abs(s) > 0.5 * self.face_width:
            return None
        height = self.height_of(p)
        if height < 0.0 or height > self.face_height:
            return None
        if (self.pockets
                and self.pocket_inner <= abs(s) <= self.pocket_outer
                and height <= self.pocket_height):
            return None                 # a pocket is a hole, not a surface
        return z

    def _deck_hit(self, r: Vec3) -> Optional[float]:
        if not self.pallet:
            return None
        den = _dot(self.up, r)
        if den >= -1e-9:
            return None
        z = (self.face_height - self.h) / den
        if z <= 0.0:
            return None
        p = _scale(r, z)
        s = _dot((p[0] - self.c0[0], p[1] - self.c0[1], p[2] - self.c0[2]), self.t)
        if abs(s) > 0.5 * self.face_width:
            return None
        q = _dot(self.n, p) - self.d_face
        if q < 0.0 or q > self.pallet_depth:
            return None
        return z

    def _floor_hit(self, r: Vec3) -> Optional[float]:
        den = _dot(self.up, r)
        if den >= -1e-9:
            return None
        z = -self.h / den
        return z if z > 0.0 else None

    def _obstacle_hit(self, r: Vec3) -> Optional[float]:
        best = None
        den = _dot(self.fwd, r)
        if den <= 1e-9:
            return None
        for lat0, lat1, h0, h1, dist in self.obstacles:
            z = dist / den
            if z <= 0.0:
                continue
            p = _scale(r, z)
            lat = _dot(p, self.right)
            height = self.height_of(p)
            if lat0 <= lat <= lat1 and h0 <= height <= h1:
                if best is None or z < best:
                    best = z
        return best

    def _wall_hit(self, r: Vec3) -> Optional[float]:
        if self.wall_distance is None:
            return None
        den = _dot(self.fwd, r)
        if den <= 1e-9:
            return None
        z = self.wall_distance / den
        return z if z > 0.0 else None

    def depth(self, x: float, y: float) -> float:
        """Depth in metres along +Z for the ray (x, y, 1), or nan."""
        r: Vec3 = (x, y, 1.0)
        best = None
        for z in (self._face_hit(r), self._deck_hit(r), self._obstacle_hit(r),
                  self._floor_hit(r), self._wall_hit(r)):
            if z is not None and (best is None or z < best):
                best = z
        if best is None or best > self.max_range:
            return float("nan")
        return best


def make_scene_depth(width: int = PLANT_WIDTH,
                     height: int = PLANT_HEIGHT,
                     fx: Optional[float] = None,
                     fy: Optional[float] = None,
                     noise: float = PLANT_NOISE_M,
                     seed: int = 7,
                     frame_id: str = "scene",
                     sim_stamp: float = 1.0,
                     **scene_kwargs) -> Tuple[DepthFrame, Scene]:
    """Render one depth frame of the scene. Returns (frame, scene).

    `fx` defaults to the plant's 337.357 scaled to `width`, so a 320x240
    fixture sees the same field of view as the 640x480 plant camera at a
    quarter of the cost.
    """
    if fx is None:
        fx = PLANT_FX * (width / float(PLANT_WIDTH))
    if fy is None:
        fy = fx
    cx, cy = width / 2.0, height / 2.0
    scene = Scene(**scene_kwargs)
    rng = random.Random(seed)
    buf: List[float] = []
    for v in range(height):
        y = (v - cy) / fy
        for u in range(width):
            z = scene.depth((u - cx) / fx, y)
            if math.isfinite(z) and noise > 0.0:
                z += rng.gauss(0.0, noise)
            buf.append(z)
    frame = DepthFrame(width, height, tuple(buf), fx, fy, cx, cy,
                       frame_id=frame_id, sim_stamp=sim_stamp)
    return frame, scene
