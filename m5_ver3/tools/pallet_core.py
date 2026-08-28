#!/usr/bin/env python3
"""pallet_core.py - pocket geometry and the attach predicate. F5 Task 3.

    python3 m5_ver3/tools/pallet_core.py --selftest

CONSTRAINT 23. Attach is a geometric predicate: both fork tips inside
the pocket volumes, yaw and height inside the configured bounds.
Contact physics is not a signal.

CONSTRAINT 21. The spawn pose is derived from tag_core's marker and
the pallet's own depth, never typed into the world file.

NO ROS, NO GAZEBO, NO FILE PATHS.
"""
import math
import sys


def wrap_angle(rad):
    return math.atan2(math.sin(float(rad)), math.cos(float(rad)))


def fork_spacing_m(left_y, right_y):
    return abs(float(left_y) - float(right_y))


def pocket_centres_y(fork_spacing_m):
    half = float(fork_spacing_m) / 2.0
    return (half, -half)


def pocket_opening_m(tine_width_m, clearance_y_m):
    return float(tine_width_m) + 2.0 * float(clearance_y_m)


def pocket_z(height_m, deck_thickness_m):
    """Pocket z in the pallet frame (origin at the geometric centre)."""
    half = float(height_m) / 2.0
    return (-half, half - float(deck_thickness_m))


def pocket_aabb(center_y, opening_m, depth_m, z_min, z_max):
    half = float(opening_m) / 2.0
    return {
        "x_min": -float(depth_m) / 2.0,
        "x_max": float(depth_m) / 2.0,
        "y_min": float(center_y) - half,
        "y_max": float(center_y) + half,
        "z_min": float(z_min),
        "z_max": float(z_max),
    }


def point_in_aabb(point, box):
    x, y, z = point
    return (box["x_min"] <= x <= box["x_max"]
            and box["y_min"] <= y <= box["y_max"]
            and box["z_min"] <= z <= box["z_max"])


def attach_ok(tips, pockets, yaw_err, height_err, yaw_max, height_max):
    if abs(wrap_angle(yaw_err)) > float(yaw_max):
        return False
    if abs(float(height_err)) > float(height_max):
        return False
    if len(tips) != len(pockets) or not tips:
        return False
    return all(point_in_aabb(tip, box) for tip, box in zip(tips, pockets))


def fork_tip_world(base_x, base_y, pose_yaw, fork_reach_m, tine_y, tine_z):
    """Tip in world, from docked base_link. Forks are model -x."""
    cy, sy = math.cos(float(pose_yaw)), math.sin(float(pose_yaw))
    bx, by = -float(fork_reach_m), float(tine_y)
    return (float(base_x) + cy * bx - sy * by,
            float(base_y) + sy * bx + cy * by,
            float(tine_z))


def world_to_local(origin_xyz, yaw, world_xyz):
    dx = float(world_xyz[0]) - float(origin_xyz[0])
    dy = float(world_xyz[1]) - float(origin_xyz[1])
    dz = float(world_xyz[2]) - float(origin_xyz[2])
    cy, sy = math.cos(float(yaw)), math.sin(float(yaw))
    return (cy * dx + sy * dy, -sy * dx + cy * dy, dz)


def spawn_pose(marker_xy, travel_yaw, wall_clearance_m, depth_m,
               height_m, tag_thickness_m):
    """Pallet origin: geometric centre, openings facing the truck.

    Pallet +X is pose_yaw (travel + pi), so the +X face is the opening
    the forks enter. The south face sits wall_clearance past the tag
    board, along the spur, toward the aisle.
    """
    ux = math.cos(float(travel_yaw))
    uy = math.sin(float(travel_yaw))
    offset = float(tag_thickness_m) / 2.0 + float(wall_clearance_m)
    south_x = float(marker_xy[0]) - ux * offset
    south_y = float(marker_xy[1]) - uy * offset
    half = float(depth_m) / 2.0
    return {
        "x": south_x - ux * half,
        "y": south_y - uy * half,
        "z": float(height_m) / 2.0,
        "yaw": wrap_angle(float(travel_yaw) + math.pi),
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--selftest"]:
        assert fork_spacing_m(0.28, -0.28) == 0.56
        print("pallet_core selftest: ok")
        return 0
    print("pallet_core.py --selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
