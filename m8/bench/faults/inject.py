"""inject.py - the staged fault set (E3) as WORLD STATE, and its undo.

bench/faults/README.md names five faults; this file stages each one on
the live plant with gz services only (set_pose on the pallet, create /
remove of two static boxes). The classifier is never told which fault
is up: the label is the world state, read back through `gz model -p`
and written beside every frame.

`clean` is the design pose with no box. `proceed` is not a fault and
not an output of anything here.

Faults, relative to the pallet design pose (pallet +X = opening face,
pointing at the oncoming forks; `along` is that +X; `lateral` is +Y):

  pallet_absent     pallet teleported to the truck spawn point, an
                    empty patch of floor 25 m away
  pallet_rotated    pallet yaw + ROTATED_RAD about its own centre
  pallet_shifted    pallet + SHIFTED_M along its +Y. On S5 that is WEST,
                    toward the camera's own 0.40 m lateral offset: the
                    pocket pair moves from optical X -0.40 to -0.10 m
                    (measured 2026-09-11; the tag board does not move,
                    so the pair is 0.30 m off the tag-derived heading)
  pocket_blocked    m8_pocket_block 0.06 m in front of the face
  stringer_in_path  m8_stringer 0.60 m in front of the face, on the floor

Values are bench constants, not config: they describe THIS staged set
and are copied into each session's manifest.
"""
from __future__ import annotations

import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

FAULTS = ("pallet_absent", "pallet_rotated", "pallet_shifted",
          "pocket_blocked", "stringer_in_path")
CONDITIONS = ("clean",) + FAULTS

ROTATED_RAD = 0.35
SHIFTED_M = 0.30
BLOCK_AHEAD_M = 0.06
BLOCK_Z_M = 0.06
STRINGER_AHEAD_M = 0.60
STRINGER_Z_M = 0.03
ABSENT_XY = (-17.0, 10.0)          # config.yaml vehicle.spawn (x, y)

BOXES = {
    "pocket_blocked": ("m8_pocket_block", os.path.join(_HERE, "m8_pocket_block.sdf"),
                       BLOCK_AHEAD_M, BLOCK_Z_M),
    "stringer_in_path": ("m8_stringer", os.path.join(_HERE, "m8_stringer.sdf"),
                         STRINGER_AHEAD_M, STRINGER_Z_M),
}


def describe() -> dict:
    return {
        "rotated_rad": ROTATED_RAD, "shifted_m": SHIFTED_M,
        "block_ahead_m": BLOCK_AHEAD_M, "block_z_m": BLOCK_Z_M,
        "stringer_ahead_m": STRINGER_AHEAD_M, "stringer_z_m": STRINGER_Z_M,
        "absent_xy": ABSENT_XY,
        "boxes": {k: os.path.basename(v[1]) for k, v in BOXES.items()},
    }


def _face_offset_pose(plant, ahead_m, z_m):
    """World pose `ahead_m` in front of the design face, on the spur axis."""
    d = plant.pallet_design
    yaw = d["yaw"]
    ux, uy = math.cos(yaw), math.sin(yaw)              # pallet +X
    half = plant.pallet_dims["depth_m"] / 2.0
    return {"x": d["x"] + ux * (half + ahead_m),
            "y": d["y"] + uy * (half + ahead_m),
            "z": z_m, "yaw": yaw}


def restore(plant) -> dict:
    """Design pose, no boxes. Returns what was done."""
    done = {}
    for name, _path, _a, _z in BOXES.values():
        if plant.gz_model_pose(name) is not None:
            done[name] = "removed" if plant.gz_remove(name) else "REMOVE FAILED"
    done["pallet"] = plant.pallet_place_or_reseat()
    return done


def inject(plant, condition: str) -> dict:
    """Stage `condition` from a restored world. Returns the manifest."""
    if condition not in CONDITIONS:
        raise ValueError("unknown condition {!r}".format(condition))
    d = plant.pallet_design
    manifest = {"condition": condition, "design": dict(d)}
    if condition == "clean":
        pass
    elif condition == "pallet_absent":
        ok = plant.gz_set_pose(plant.pallet_name, ABSENT_XY[0], ABSENT_XY[1],
                               d["z"], d["yaw"])
        manifest["set_pose_ok"] = ok
    elif condition == "pallet_rotated":
        ok = plant.gz_set_pose(plant.pallet_name, d["x"], d["y"], d["z"],
                               d["yaw"] + ROTATED_RAD)
        manifest["set_pose_ok"] = ok
    elif condition == "pallet_shifted":
        yaw = d["yaw"]
        lx, ly = -math.sin(yaw), math.cos(yaw)         # pallet +Y
        ok = plant.gz_set_pose(plant.pallet_name, d["x"] + lx * SHIFTED_M,
                               d["y"] + ly * SHIFTED_M, d["z"], yaw)
        manifest["set_pose_ok"] = ok
    else:
        name, path, ahead, z = BOXES[condition]
        pose = _face_offset_pose(plant, ahead, z)
        ok = plant.gz_create(path, name, pose)
        manifest["create_ok"] = ok
        manifest["box_pose"] = pose
    return manifest


def readback(plant) -> dict:
    """World state after staging: every model this set can move."""
    out = {"pallet": plant.gz_model_pose(plant.pallet_name)}
    for name, _path, _a, _z in BOXES.values():
        out[name] = plant.gz_model_pose(name)
    return out
