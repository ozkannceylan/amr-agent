#!/usr/bin/env python3
"""dock_core.py - the arithmetic behind F5 Task 2's dock. --selftest

    python3 m5_ver3/tools/dock_core.py --selftest

WHAT IS IN HERE. Numbers the docking server is about to be told, as
functions of the plant and of tag_core's station geometry:

  THE HALF TURN. Forks are model -x. A dock pose whose yaw is the
  travel heading would put the counterweight at the pallet. Same
  function as drive_goal.pose_yaw, kept here so a test can pin both
  without importing that file's ROS-shaped record() body as a
  dependency of this one.

  CURVATURE. opennav_docking's SmoothControlLaw has no min-radius
  clamp (docs/reports/m5v3-02 §3). v_angular_max = v_linear_min / R
  is the bound that keeps |v|/|ω| at or above the plant's measured
  1.25 m floor.

  STAGING OFFSET SIGN. getStagingPose does
  (x,y) += (cos(yaw), sin(yaw)) * staging_x_offset. This truck's
  docked pose_yaw points +x at the aisle, so the T1 staging pose
  is a POSITIVE offset, not the package default -0.7.

  TAG → DOCK. SimpleNonChargingDock applies
  external_detection_translation_* along the yaw it built from the
  AprilTag pose. From the marker to the docked base_link is +x of
  that yaw, length fork_reach + tip_standoff.

  HANDOVER. Nav2's controller and the docking controller share
  topics.cmd_vel. They must not both have a goal. overlap_refused
  is that predicate.

NO ROS, NO GAZEBO, NO FILE PATHS.
"""
import math
import sys

import evidence_core as ec                            # noqa: E402


ERROR_NAMES = {
    0: "NONE",
    901: "DOCK_NOT_IN_DB",
    902: "DOCK_NOT_VALID",
    903: "FAILED_TO_STAGE",
    904: "FAILED_TO_DETECT_DOCK",
    905: "FAILED_TO_CONTROL",
    906: "FAILED_TO_CHARGE",
    999: "UNKNOWN",
}


def pose_yaw(travel_yaw_rad):
    """The base_link yaw that puts the FORKS along `travel_yaw_rad`."""
    return ec.normalise_angle(float(travel_yaw_rad) + math.pi)


def v_angular_max(v_linear_min, radius_m):
    """The ω cap that keeps |v|/|ω| >= R at the slowest commanded v."""
    radius = float(radius_m)
    vmin = float(v_linear_min)
    if radius <= 0.0:
        raise ValueError("turning radius must be positive, not {}".format(
            radius))
    if vmin < 0.0:
        raise ValueError("v_linear_min must be >= 0, not {}".format(vmin))
    if vmin == 0.0:
        return 0.0
    return vmin / radius


def curvature_respects_radius(v_mps, w_radps, radius_m):
    """True when the commanded (v, ω) is a feasible bicycle arc."""
    v = abs(float(v_mps))
    w = abs(float(w_radps))
    radius = float(radius_m)
    if w < 1e-12:
        return True
    return (v / w) + 1e-12 >= radius


def docked_world(station, dock):
    """base_link pose at the load, in the WORLD, with the half-turn yaw."""
    import tag_core as tc
    geo = tc.station_geometry(
        float(station["x"]), float(station["y"]), float(station["yaw"]),
        marker_ahead_m=float(dock["marker_ahead_m"]),
        fork_reach_m=float(dock["fork_reach_m"]),
        tip_standoff_m=float(dock["tip_standoff_m"]),
        staging_run_in_m=float(dock["staging_run_in_m"]))
    travel = float(station["yaw"])
    return {
        "x": geo["docked"][0],
        "y": geo["docked"][1],
        "travel_yaw": travel,
        "pose_yaw": pose_yaw(travel),
        "staging": geo["staging"],
        "marker": geo["marker"],
    }


def staging_x_offset(pose_yaw_rad, staging_xy, docked_xy):
    """getStagingPose's offset, signed along the docked pose's +x.

    staging = docked + (cos(yaw), sin(yaw)) * offset. A POSITIVE offset
    is the aisle, because pose_yaw points the counterweight that way.
    """
    yaw = float(pose_yaw_rad)
    dx = float(staging_xy[0]) - float(docked_xy[0])
    dy = float(staging_xy[1]) - float(docked_xy[1])
    return dx * math.cos(yaw) + dy * math.sin(yaw)


def tag_to_dock_translation_x(fork_reach_m, tip_standoff_m):
    """Plugin `external_detection_translation_x`.

    SimpleChargingDock applies this along the yaw it built from the
    AprilTag pose (Z-out, then roll -1.57 / pitch 1.57). That +X
    points into the tag. The docked base_link is on the camera side,
    so the offset is NEGATIVE — the package default is -0.20 for
    the same reason. Magnitude is fork_reach + tip_standoff.

    A positive value here sends the approach through the tag at
    v_linear_max; measured 2026-08-28 (dock-s5-20260828-181917).
    """
    return -(float(fork_reach_m) + float(tip_standoff_m))


def overlap_refused(nav_goal_active, dock_goal_active):
    """Constraint 22: one motion authority at a time."""
    return bool(nav_goal_active) and bool(dock_goal_active)


def named_error(code):
    return ERROR_NAMES.get(int(code), "UNKNOWN")


def align_omega(current_yaw, target_yaw, wmax):
    """Signed ω that shrinks heading error, capped at the plant bound.

    This tricycle cannot spin in place. The caller must send v_linear_min
    with this ω so |v|/|ω| stays at the 1.25 m floor. Used when Nav2's
    position-only latch leaves the tag out of the camera (904).
    """
    err = ec.normalise_angle(float(target_yaw) - float(current_yaw))
    cap = abs(float(wmax))
    if abs(err) < 1e-6 or cap == 0.0:
        return 0.0
    return cap if err > 0.0 else -cap


def arrival(target, pose_xyyaw):
    """dx, dy, dist, heading error of a pose against the docked target."""
    dx = float(pose_xyyaw[0]) - float(target["x"])
    dy = float(pose_xyyaw[1]) - float(target["y"])
    dist = math.hypot(dx, dy)
    dyaw = ec.normalise_angle(float(pose_xyyaw[2]) - float(target["pose_yaw"]))
    return dx, dy, dist, dyaw


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv != ["--selftest"]:
        sys.stderr.write("usage: dock_core.py --selftest\n")
        return 2
    wmax = v_angular_max(0.10, 1.25)
    assert abs(wmax - 0.08) < 1e-12
    assert curvature_respects_radius(0.10, 0.08, 1.25)
    assert not curvature_respects_radius(0.10, 0.09, 1.25)
    assert overlap_refused(True, True)
    assert not overlap_refused(True, False)
    assert named_error(904) == "FAILED_TO_DETECT_DOCK"
    assert abs(align_omega(0.0, 0.4, 0.08) - 0.08) < 1e-12
    assert abs(align_omega(0.4, 0.0, 0.08) + 0.08) < 1e-12
    print("dock_core selftest ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
