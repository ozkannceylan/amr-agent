"""m8/bench/geom.py against numbers derived by hand from config.yaml.

Staging on S5 (EVIDENCE_DOCKING_V3 2.1): base_link (7.000, 6.575),
pose_yaw +pi/2 (forks south). cam_mount (-0.90, 0.40, 1.10, 0, 0.5236, pi).
Pallet origin (7.000, 3.030, 0.072) yaw +pi/2; +X face at y = 3.430.
"""
import math
import sys
from pathlib import Path

_M8 = Path(__file__).resolve().parents[1]
if str(_M8) not in sys.path:
    sys.path.insert(0, str(_M8))

from bench import geom  # noqa: E402

MOUNT = (-0.90, 0.40, 1.10, 0.0, 0.5235988, 3.1415927)
OPTICAL = (0.0, 0.0, 0.0, -1.57079632679, 0.0, -1.57079632679)
BASE = (7.0, 6.575, 0.05)
QUAT = (0.0, 0.0, math.sin(math.pi / 4), math.cos(math.pi / 4))  # yaw +pi/2


def _close(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_rpy_matches_tag_core_convention():
    # tag_core.rpy_rotate: optical +Z (look) is body +X at rpy(-pi/2,0,-pi/2)
    r = geom.rot_rpy(*OPTICAL[3:])
    look = geom.mat_vec(r, (0.0, 0.0, 1.0))
    assert _close(look, (1.0, 0.0, 0.0))
    right = geom.mat_vec(r, (1.0, 0.0, 0.0))   # optical +X -> body -Y
    assert _close(right, (0.0, -1.0, 0.0))


def test_camera_world_position_at_staging():
    chain = geom.CameraChain(MOUNT, OPTICAL)
    cam = chain.camera_world(BASE, QUAT)
    # R(+pi/2) maps (-0.90, 0.40) -> (-0.40, -0.90)
    assert _close(cam, (6.6, 5.675, 1.15), 1e-6)


def test_face_centre_in_optical_at_staging():
    chain = geom.CameraChain(MOUNT, OPTICAL)
    pallet = geom.PalletTruth((7.0, 3.03, 0.072), math.pi / 2,
                              0.80, 1.20, 0.144, 0.022)
    face = pallet.face_centre()
    assert _close(face, (7.0, 3.43, 0.072))
    p = chain.world_to_optical(face, BASE, QUAT)
    # Camera looks south, pitched 30 deg down. Face is 2.245 m south,
    # 0.40 m east (= camera LEFT, optical -X), 1.078 m below.
    horiz = 2.245
    drop = 1.15 - 0.072
    pitch = 0.5235988
    z_exp = horiz * math.cos(pitch) + drop * math.sin(pitch)
    y_exp = -horiz * math.sin(pitch) + drop * math.cos(pitch)
    assert abs(p[0] - (-0.40)) < 1e-6
    assert abs(p[1] - y_exp) < 1e-6
    assert abs(p[2] - z_exp) < 1e-6
    assert p[2] > 2.0


def test_round_trip_world_optical():
    chain = geom.CameraChain(MOUNT, OPTICAL)
    q = (0.1, -0.2, 0.3, 0.9)
    pt = (1.0, -2.0, 0.5)
    back = chain.optical_to_world(chain.world_to_optical(pt, BASE, q), BASE, q)
    assert _close(back, pt, 1e-9)


def test_projection_and_backprojection():
    fx, fy, cx, cy = geom.intrinsics_from_hfov(640, 480, 1.518)
    assert abs(fx - 320.0 / math.tan(0.759)) < 1e-9
    uv = geom.project((-0.4, 0.1, 2.0), fx, fy, cx, cy)
    assert uv[0] < cx and uv[1] > cy
    p = geom.backproject(uv[0], uv[1], 2.0, fx, fy, cx, cy)
    assert _close(p, (-0.4, 0.1, 2.0), 1e-9)
    assert geom.project((0.0, 0.0, -1.0), fx, fy, cx, cy) is None


def test_face_yaw_zero_when_square_to_camera():
    chain = geom.CameraChain(MOUNT, OPTICAL)
    pallet = geom.PalletTruth((7.0, 3.03, 0.072), math.pi / 2,
                              0.80, 1.20, 0.144, 0.022)
    left, right = pallet.face_ends_at_pocket_height()
    lo = chain.world_to_optical(left, BASE, QUAT)
    ro = chain.world_to_optical(right, BASE, QUAT)
    assert abs(geom.face_yaw_in_optical(lo, ro)) < 1e-6
    # A world yaw of 0.35 rad is NOT 0.35 rad in the optical frame: the
    # camera is pitched 30 deg down, so the along-axis component of the
    # face line is scaled by cos(pitch). C1's dtheta = atan(a) lives in
    # the optical frame, so the truth it is scored against must too.
    rotated = geom.PalletTruth((7.0, 3.03, 0.072), math.pi / 2 + 0.35,
                               0.80, 1.20, 0.144, 0.022)
    left, right = rotated.face_ends_at_pocket_height()
    lo = chain.world_to_optical(left, BASE, QUAT)
    ro = chain.world_to_optical(right, BASE, QUAT)
    expected = math.atan(math.tan(0.35) * math.cos(0.5235988))
    assert abs(abs(geom.face_yaw_in_optical(lo, ro)) - expected) < 1e-6
    assert 0.30 < expected < 0.31


def test_pocket_pair_centre_height():
    pallet = geom.PalletTruth((7.0, 3.03, 0.072), math.pi / 2,
                              0.80, 1.20, 0.144, 0.022)
    z_local = pallet.pocket_mid_z_local()
    assert abs(z_local - (-0.011)) < 1e-9
    assert abs(pallet.pocket_pair_centre()[2] - 0.061) < 1e-9


def test_overlap_fraction_and_rms():
    assert geom.overlap_fraction((0, 10, 0, 10), (5, 15, 5, 15)) == 0.25
    assert geom.overlap_fraction(None, (0, 1, 0, 1)) == 0.0
    assert abs(geom.rms([3.0, 4.0]) - math.sqrt(12.5)) < 1e-12
    s = geom.summarise([1.0, 2.0, 3.0])
    assert s["n"] == 3 and s["median"] == 2.0 and s["max"] == 3.0
    assert math.isnan(geom.rms([]))


def test_quat_from_rpy_matches_rot_rpy():
    for rpy in ((0.0, 0.0, math.pi / 2), (0.1, -0.2, 0.3), (0.0, 0.5235988, math.pi)):
        q = geom.quat_from_rpy(*rpy)
        a = geom.rot_quat(*q)
        b = geom.rot_rpy(*rpy)
        for i in range(3):
            assert _close(a[i], b[i], 1e-9)
    q = geom.quat_from_rpy(0.0, 0.0, math.pi / 2)
    assert abs(geom.wrap(geom.yaw_of_quat(*q) - math.pi / 2)) < 1e-9
