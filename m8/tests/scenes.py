"""Cached plant-faithful depth scenes for the offline suite.

Rendering is the expensive part (about 0.1 s per 320x240 frame), so
every fixture is memoised. 320x240 keeps the plant's field of view -
`make_scene_depth` scales fx with the width - at a quarter of the cost.

The A1 fixtures were one flat surface filling the frame and no floor,
which is why the offline suite was green while `EVIDENCE_M8_E1.md` and
`EVIDENCE_M8_E3.md` were failing on the plant. These have the floor.
"""
from functools import lru_cache

from m8_core.pocket import DepthFrame
from m8_core.scene import make_scene_depth

W, H = 320, 240

# The three poses E1 scored, by camera-to-face horizontal distance.
STAGING_M = 2.245
APPROACH_M = 1.5
CLOSE_M = 1.0

# EVIDENCE_M8_E1 "Bar": tag chain at staging, rms over 211 samples.
TAG_BAR_M = 0.0706


@lru_cache(maxsize=None)
def clean(distance: float = APPROACH_M):
    """Square pallet, pockets open, nothing in the fork path."""
    return make_scene_depth(width=W, height=H, face_distance=distance)


@lru_cache(maxsize=None)
def rotated(yaw: float = 0.25, distance: float = APPROACH_M):
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            yaw=yaw)


@lru_cache(maxsize=None)
def absent(distance: float = APPROACH_M):
    """Floor and nothing else - the bay is empty."""
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            pallet=False)


@lru_cache(maxsize=None)
def no_pockets(distance: float = APPROACH_M):
    """A pallet-sized face with both pockets filled in."""
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            pockets=False)


@lru_cache(maxsize=None)
def stringer(distance: float = APPROACH_M):
    """A 0.30 m bar across the left pocket, 0.08 m in front of the face."""
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            obstacles=((-0.55, -0.25, 0.0, 0.13,
                                        distance - 0.08),))


@lru_cache(maxsize=None)
def shifted(lateral: float = 0.75, distance: float = APPROACH_M):
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            lateral=lateral)


@lru_cache(maxsize=None)
def far(distance: float = 4.5):
    """A pallet outside the dock envelope entirely."""
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            max_range=8.0)


@lru_cache(maxsize=None)
def two_pallets(distance: float = APPROACH_M):
    """Two pallets side by side. Returns (frame, left_scene, right_scene).

    Composited by taking the nearer of two renders per pixel, which is
    what occlusion does. Both renders carry the same floor, so the
    result is one floor and two separate standing blobs - the frame a
    tag has to disambiguate.
    """
    left, s_left = make_scene_depth(width=W, height=H,
                                    face_distance=distance, lateral=-0.60)
    right, s_right = make_scene_depth(width=W, height=H,
                                      face_distance=distance, lateral=0.80,
                                      seed=11)
    merged = []
    for a, b in zip(left.depths, right.depths):
        a_ok = a == a and a > 0.0
        b_ok = b == b and b > 0.0
        if a_ok and b_ok:
            merged.append(min(a, b))
        elif a_ok:
            merged.append(a)
        elif b_ok:
            merged.append(b)
        else:
            merged.append(float("nan"))
    frame = DepthFrame(left.width, left.height, tuple(merged), left.fx,
                       left.fy, left.cx, left.cy, "two", 1.0)
    return frame, s_left, s_right


def px_of(frame, scene):
    """Pixel the scene's pocket centre projects to - a tag's reading."""
    x, y, z = scene.pocket_centre()
    return frame.cx + x / z * frame.fx, frame.cy + y / z * frame.fy
