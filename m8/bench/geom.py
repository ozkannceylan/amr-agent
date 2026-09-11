"""geom.py - the arithmetic behind the M8 plant benches. No ROS, no numpy.

What the camera SHOULD see, from world state: rigid transforms through
vehicle.cam_mount and vehicle.cam_optical (m5_ver3/config.yaml), the
pinhole projection, the pallet's +X face and pocket-pair centre in the
pallet frame, and the rms the EVIDENCE files quote.

Conventions, all inherited and pinned by tests:
  * RPY rotates R = Rz(yaw) Ry(pitch) Rx(roll) - tf2 setRPY and the
    Gazebo <pose> rpy (m5_ver3/tools/tag_core.rpy_rotate).
  * Optical frame is REP-103: +X right, +Y down, +Z forward.
  * The pallet origin is its geometric centre; +X is the opening face
    (m5_ver3/tools/pallet_core.spawn_pose); z origin sits at height/2.

Ground truth is a score, not a command. Nothing here is published.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence, Tuple

Vec3 = Tuple[float, float, float]
Mat3 = Tuple[Vec3, Vec3, Vec3]


# ----------------------------------------------------------------- linear
def rot_rpy(roll: float, pitch: float, yaw: float) -> Mat3:
    """Rotation matrix for R = Rz(yaw) Ry(pitch) Rx(roll)."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def rot_quat(x: float, y: float, z: float, w: float) -> Mat3:
    """Rotation matrix of a unit quaternion (x, y, z, w)."""
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )


def mat_vec(m: Mat3, v: Vec3) -> Vec3:
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


def mat_t_vec(m: Mat3, v: Vec3) -> Vec3:
    """Transpose(m) @ v - the inverse rotation."""
    return (m[0][0] * v[0] + m[1][0] * v[1] + m[2][0] * v[2],
            m[0][1] * v[0] + m[1][1] * v[1] + m[2][1] * v[2],
            m[0][2] * v[0] + m[1][2] * v[1] + m[2][2] * v[2])


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def yaw_of_quat(x: float, y: float, z: float, w: float) -> float:
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def quat_from_rpy(roll: float, pitch: float, yaw: float):
    """(x, y, z, w) of R = Rz(yaw) Ry(pitch) Rx(roll) - tf2 setRPY."""
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return (sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy)


def wrap(rad: float) -> float:
    return math.atan2(math.sin(rad), math.cos(rad))


# ------------------------------------------------------------- the camera
class CameraChain:
    """base_link -> pallet_cam_link -> pallet_cam_optical, from config.yaml.

    mount = (x, y, z, roll, pitch, yaw) of vehicle.cam_mount,
    optical = the same six of vehicle.cam_optical.
    """

    def __init__(self, mount: Sequence[float], optical: Sequence[float]):
        self.t_mount = (float(mount[0]), float(mount[1]), float(mount[2]))
        self.r_mount = rot_rpy(float(mount[3]), float(mount[4]), float(mount[5]))
        self.t_opt = (float(optical[0]), float(optical[1]), float(optical[2]))
        self.r_opt = rot_rpy(float(optical[3]), float(optical[4]), float(optical[5]))

    def base_to_optical(self, p_base: Vec3) -> Vec3:
        p_cam = mat_t_vec(self.r_mount, sub(p_base, self.t_mount))
        return mat_t_vec(self.r_opt, sub(p_cam, self.t_opt))

    def optical_to_base(self, p_opt: Vec3) -> Vec3:
        p_cam = add(mat_vec(self.r_opt, p_opt), self.t_opt)
        return add(mat_vec(self.r_mount, p_cam), self.t_mount)

    def world_to_optical(self, p_world: Vec3, base_pos: Vec3,
                         base_quat_xyzw: Sequence[float]) -> Vec3:
        r_base = rot_quat(*base_quat_xyzw)
        p_base = mat_t_vec(r_base, sub(p_world, base_pos))
        return self.base_to_optical(p_base)

    def optical_to_world(self, p_opt: Vec3, base_pos: Vec3,
                         base_quat_xyzw: Sequence[float]) -> Vec3:
        r_base = rot_quat(*base_quat_xyzw)
        return add(mat_vec(r_base, self.optical_to_base(p_opt)), base_pos)

    def camera_world(self, base_pos: Vec3, base_quat_xyzw: Sequence[float]) -> Vec3:
        return self.optical_to_world((0.0, 0.0, 0.0), base_pos, base_quat_xyzw)


def intrinsics_from_hfov(width: int, height: int, hfov_rad: float):
    """Square-pixel pinhole (fx, fy, cx, cy) from the SDF horizontal fov.

    The bench prefers CameraInfo when the bridge has delivered one; this
    is the stand-in and the cross-check.
    """
    fx = (width / 2.0) / math.tan(hfov_rad / 2.0)
    return fx, fx, width / 2.0, height / 2.0


def project(p_opt: Vec3, fx: float, fy: float, cx: float, cy: float):
    """Pixel (u, v) of an optical-frame point; None behind the camera."""
    if p_opt[2] <= 1e-9:
        return None
    return (cx + fx * p_opt[0] / p_opt[2], cy + fy * p_opt[1] / p_opt[2])


def backproject(u: float, v: float, z: float, fx: float, fy: float,
                cx: float, cy: float) -> Vec3:
    return ((u - cx) / fx * z, (v - cy) / fy * z, z)


# ------------------------------------------------------------- the pallet
class PalletTruth:
    """The pallet's +X face in the world, from its gz pose and config.yaml.

    depth_m is along the pallet's +X (0.80), length_m along +Y (1.20),
    height_m the deck top (0.144). Blocks span z in [-h/2, h/2 - deck]
    in the pallet frame; the pocket pair is centred on the face at
    y = 0 and pocket mid-height.
    """

    def __init__(self, pose_xyz: Vec3, yaw: float, depth_m: float,
                 length_m: float, height_m: float, deck_thickness_m: float):
        self.origin = (float(pose_xyz[0]), float(pose_xyz[1]), float(pose_xyz[2]))
        self.yaw = float(yaw)
        self.depth = float(depth_m)
        self.length = float(length_m)
        self.height = float(height_m)
        self.deck = float(deck_thickness_m)
        self._r = rot_rpy(0.0, 0.0, self.yaw)

    def local_to_world(self, p_local: Vec3) -> Vec3:
        return add(mat_vec(self._r, p_local), self.origin)

    def pocket_mid_z_local(self) -> float:
        z_min = -self.height / 2.0
        z_max = self.height / 2.0 - self.deck
        return 0.5 * (z_min + z_max)

    def face_centre(self) -> Vec3:
        return self.local_to_world((self.depth / 2.0, 0.0, 0.0))

    def pocket_pair_centre(self) -> Vec3:
        return self.local_to_world((self.depth / 2.0, 0.0, self.pocket_mid_z_local()))

    def face_corners(self) -> Tuple[Vec3, Vec3, Vec3, Vec3]:
        hx = self.depth / 2.0
        hy = self.length / 2.0
        hz = self.height / 2.0
        return (self.local_to_world((hx, -hy, -hz)),
                self.local_to_world((hx, hy, -hz)),
                self.local_to_world((hx, hy, hz)),
                self.local_to_world((hx, -hy, hz)))

    def face_ends_at_pocket_height(self) -> Tuple[Vec3, Vec3]:
        hx = self.depth / 2.0
        hy = self.length / 2.0
        z = self.pocket_mid_z_local()
        return (self.local_to_world((hx, -hy, z)), self.local_to_world((hx, hy, z)))


def face_yaw_in_optical(left: Vec3, right: Vec3) -> float:
    """atan(dZ/dX) of the face line in the optical frame.

    This is the quantity m8_core.pocket reports as dtheta = atan(a) for
    the plane z = a x + b y + c, with x = (u - cx) / fx: a is dZ per
    unit normalised x, which at the face is dZ/dX to first order.
    """
    dx = right[0] - left[0]
    dz = right[2] - left[2]
    if abs(dx) < 1e-9:
        return math.copysign(math.pi / 2.0, dz)
    return math.atan(dz / dx)


def bbox(points: Iterable[Tuple[float, float]]):
    us = [p[0] for p in points]
    vs = [p[1] for p in points]
    if not us:
        return None
    return (min(us), max(us), min(vs), max(vs))


def overlap_fraction(inner, outer) -> float:
    """Area of (inner intersect outer) over the area of outer.

    Boxes are (u0, u1, v0, v1). Used to say how much of C1's plane ROI
    the pallet face actually covers.
    """
    if inner is None or outer is None:
        return 0.0
    u0 = max(inner[0], outer[0])
    u1 = min(inner[1], outer[1])
    v0 = max(inner[2], outer[2])
    v1 = min(inner[3], outer[3])
    if u1 <= u0 or v1 <= v0:
        return 0.0
    area_outer = (outer[1] - outer[0]) * (outer[3] - outer[2])
    if area_outer <= 0:
        return 0.0
    return ((u1 - u0) * (v1 - v0)) / area_outer


# --------------------------------------------------------------- the score
def rms(values: Sequence[float]) -> float:
    vals = [float(v) for v in values]
    if not vals:
        return float("nan")
    return math.sqrt(sum(v * v for v in vals) / len(vals))


def mean(values: Sequence[float]) -> float:
    vals = [float(v) for v in values]
    return sum(vals) / len(vals) if vals else float("nan")


def summarise(values: Sequence[float]) -> dict:
    vals = sorted(float(v) for v in values)
    if not vals:
        return {"n": 0, "mean": float("nan"), "rms": float("nan"),
                "min": float("nan"), "max": float("nan"),
                "median": float("nan")}
    return {"n": len(vals), "mean": mean(vals), "rms": rms(vals),
            "min": vals[0], "max": vals[-1],
            "median": vals[len(vals) // 2]}
