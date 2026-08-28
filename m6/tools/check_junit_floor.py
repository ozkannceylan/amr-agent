#!/usr/bin/env python3
"""Fail if a pytest JUnit file reports errors/failures or too few passes.

Usage: python3 m6/tools/check_junit_floor.py junit-m6.xml 400
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET


def _suite_counts(root: ET.Element) -> tuple[int, int, int, int]:
    """Return tests, failures, errors, skipped from a pytest JUnit tree."""
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if root.tag == "testsuites" and not suites:
        suites = list(root)
    tests = failures = errors = skipped = 0
    for suite in suites:
        tests += int(suite.attrib.get("tests", 0))
        failures += int(suite.attrib.get("failures", 0))
        errors += int(suite.attrib.get("errors", 0))
        skipped += int(suite.attrib.get("skipped", 0))
    return tests, failures, errors, skipped


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_junit_floor.py JUNIT.xml MIN_PASSED", file=sys.stderr)
        return 2
    path, floor_s = sys.argv[1], sys.argv[2]
    floor = int(floor_s)
    tests, failures, errors, skipped = _suite_counts(ET.parse(path).getroot())
    passed = tests - failures - errors - skipped
    print(
        f"junit {path}: tests={tests} passed={passed} "
        f"failed={failures} errors={errors} skipped={skipped} floor={floor}"
    )
    if failures or errors:
        print("floor check FAILED: pytest reported failures or errors")
        return 1
    if passed < floor:
        print(f"floor check FAILED: {passed} passed is below {floor}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
