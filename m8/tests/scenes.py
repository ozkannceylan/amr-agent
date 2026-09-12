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


# --- the plant's own findings, rendered -----------------------------------
# EVIDENCE_M8_C1C2_FIX finding 2: a vehicle-fixed structure 0.5-1.0 m from
# this camera at about 0.1 m above the floor, present at every pose, and
# at 1.0 m continuous with the pallet - no range discontinuity at the
# junction, so depth-aware connectivity cannot split them either. Two
# tines, centred on the vehicle centreline, which is 0.40 m to the RIGHT
# of this camera's optical axis (the pallet sits at lateral -0.40).
FORK_REACH_M = (0.50, 1.00)
FORK_HEIGHT_M = 0.10
FORK_TINES = ((-0.68, -0.52), (-0.28, -0.12))


def _fork_slabs(reach=FORK_REACH_M):
    return tuple((lat0, lat1, FORK_HEIGHT_M, reach[0], reach[1])
                 for lat0, lat1 in FORK_TINES)


@lru_cache(maxsize=None)
def forks(distance: float = CLOSE_M):
    """A clean pallet WITH the truck's own forks reaching toward it.

    At 1.0 m the tines end where the pallet begins and the two are one
    standing object to this camera; at 1.5 m and staging there is clean
    floor between them and they are separate components. That is the
    difference the plant measured and the offline suite could not see.
    """
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            slabs=_fork_slabs())


@lru_cache(maxsize=None)
def forks_empty_bay(distance: float = CLOSE_M):
    """The forks with NO pallet: the bay really is empty."""
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            pallet=False, slabs=_fork_slabs())


@lru_cache(maxsize=None)
def blocked_by_box(distance: float = APPROACH_M):
    """The plant's `m8_pocket_block`, rendered.

    0.10 x 0.72 x 0.10 m across BOTH openings, 0.06 m in front of the
    face (bench/faults/inject.py). E3 read this as `pallet_absent` 84
    times in 90: the box changes the segmented object enough that C1
    refuses before the pocket test is reached.
    """
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            obstacles=((-0.76, -0.04, 0.0, 0.10,
                                        distance - 0.06),))


@lru_cache(maxsize=None)
def ridge(distance: float = APPROACH_M):
    """The plant's `m8_stringer`: a ridge on the floor 0.60 m out.

    0.08 x 1.00 x 0.06 m, a SEPARATE component from the pallet, which is
    why `fork_path_fraction` - which searches the pallet's own standing
    object - never sees it. Named open in EVIDENCE_M8_C1C2_FIX miss 2.
    """
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            obstacles=((-0.90, 0.10, 0.0, 0.06,
                                        distance - 0.60),))


@lru_cache(maxsize=None)
def clipped(distance: float = APPROACH_M, lateral: float = 1.45):
    """A pallet running off the edge of the image.

    Its width in metres is a lower bound, its plane is fitted to a part,
    and every word that is a claim about the whole pallet is a claim this
    frame cannot support.
    """
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
