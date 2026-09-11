"""Cached plant-faithful depth scenes for the offline suite.

Rendering is the expensive part (about 0.1 s per 320x240 frame), so
every fixture is memoised. 320x240 keeps the plant's field of view -
`make_scene_depth` scales fx with the width - at a quarter of the cost.

The A1 fixtures were one flat surface filling the frame and no floor,
which is why the offline suite was green while `EVIDENCE_M8_E1.md` and
`EVIDENCE_M8_E3.md` were failing on the plant. These have the floor.
"""
from functools import lru_cache

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
