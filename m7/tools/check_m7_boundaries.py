#!/usr/bin/env python3
"""Mechanical restatement of G1 that CI can fail a PR on.

Architecture hygiene, not a safety function: M7 is not one. The
gateway must not import a ROS client library, must not mention a
vehicle-topic prefix, and must not name a velocity command topic.

A check that needs judgement is not this script. Needles are the
ones named in HAND_OFF.md: the vehicle-topic prefix, the ROS client
library, and the velocity command topic.
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
M7 = REPO / "m7"

# Exact tokens HAND_OFF names. The checker file itself is skipped so
# the needles can be written here once.
NEEDLES = (
    "uagv/",
    "rclpy",
    "cmd_vel",
)

SKIP_NAMES = frozenset({"check_m7_boundaries.py"})
SKIP_PARTS = frozenset({"tests", "__pycache__"})


def _iter_py() -> list[pathlib.Path]:
    found = []
    for path in sorted(M7.rglob("*.py")):
        if path.name in SKIP_NAMES:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        found.append(path)
    return found


def check() -> list[str]:
    findings: list[str] = []
    for path in _iter_py():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO)
        for index, line in enumerate(text.splitlines(), start=1):
            for needle in NEEDLES:
                if needle in line:
                    findings.append(
                        "{}:{}: m7 must not contain {!r} "
                        "(ARCHITECTURE.md G1 / fleet invariant: no ROS here)"
                        .format(rel, index, needle)
                    )
    return findings


def main() -> int:
    findings = check()
    if findings:
        print("m7 boundary check FAILED:")
        for line in findings:
            print("  {}".format(line))
        return 1
    print("m7 boundary check passed ({} modules, needles={})".format(
        len(_iter_py()), ", ".join(NEEDLES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
