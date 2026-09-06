#!/usr/bin/env python3
"""e5_cost.py — RTF / frame-age / inference latency with M8 on the rig.

NOT_RUN without the m5-ver3 plant. This file does not invent an RTF.
"""
import sys


def main(argv=None):
    print("NOT_RUN: E5 needs the m5-ver3 plant on the measured rig")
    print("  required: GPU preflight, RTF before/after, frame-age histogram")
    print("  this process did not publish an RTF cost or a latency p95")
    print("  health budgets in m8_core.gate are placeholders until this runs")
    return 2


if __name__ == "__main__":
    sys.exit(main())
