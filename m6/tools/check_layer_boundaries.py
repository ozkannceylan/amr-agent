#!/usr/bin/env python3
"""Mechanical restatements of ADR 0001 that CI can fail a PR on.

The fleet tree must not import ROS or a vehicle ROS node (invariant 11,
m6/fleet README: "No ROS lives here"). vda_orders.py is the shared
door used by both ends of the wire and must stay stdlib-only, so the
two ends cannot drift by one of them growing a ROS or MQTT dependency
the other does not have.

A check that needs judgement is not this script.
"""
from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
FLEET = REPO / "m6" / "fleet"
VDA_ORDERS = REPO / "m6" / "ipc" / "vda_orders.py"

# Vehicle ROS nodes and ROS itself. Pure ipc modules (route, stations,
# vda_messages, vda_orders, nav_core, follower, avoid, status_contract)
# are the documented crossings and are allowed.
FLEET_FORBIDDEN = frozenset({
    "rclpy",
    "geometry_msgs",
    "nav_msgs",
    "std_msgs",
    "sensor_msgs",
    "builtin_interfaces",
    "tf2_ros",
    "launch",
    "launch_ros",
    "cmd_gate",
    "cmd_mux",
    "encoder_link",
    "field_eval",
    "sensor_link",
    "plc_link",
    "nav_node",
    "vda_agent",
    "hmi_node",
    "map_panel",
    "ros_optional",
})


def _imported_roots(path: pathlib.Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.append((node.lineno, node.module.split(".")[0]))
    return found


def check_fleet() -> list[str]:
    findings: list[str] = []
    for path in sorted(FLEET.glob("*.py")):
        for lineno, name in _imported_roots(path):
            if name in FLEET_FORBIDDEN:
                rel = path.relative_to(REPO)
                findings.append(
                    f"{rel}:{lineno}: fleet must not import {name!r} "
                    "(ADR 0001 inv. 11 / m6/fleet README)"
                )
    return findings


def check_vda_orders() -> list[str]:
    findings: list[str] = []
    stdlib = set(sys.stdlib_module_names)
    for lineno, name in _imported_roots(VDA_ORDERS):
        if name not in stdlib:
            rel = VDA_ORDERS.relative_to(REPO)
            findings.append(
                f"{rel}:{lineno}: vda_orders.py must stay stdlib-only, "
                f"found import {name!r}"
            )
    return findings


def main() -> int:
    findings = check_fleet() + check_vda_orders()
    if findings:
        print("layer-boundary check FAILED:")
        for line in findings:
            print(f"  {line}")
        return 1
    print("layer-boundary check passed "
          f"({len(list(FLEET.glob('*.py')))} fleet modules, vda_orders stdlib-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
