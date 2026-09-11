#!/usr/bin/env python3
"""e1_pocket.py — score C1 against gz pallet pose at staging.

NOT_RUN without the m5-ver3 plant. This file does not invent an rms.
"""
import sys

BAR = "tag rms 0.0706 m / 211 samples at staging (R1). Not a number this script produced."


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    print("NOT_RUN: E1 needs the m5-ver3 plant")
    print("  required: gz-sim 8.11, forklift_ver3, warehouse_ver3,")
    print("            pallet_cam D455 depth, GPU preflight, mix refusals")
    print("  bar (quoted, not scored here):", BAR)
    print("  this process did not synthesize a pocket pose or an rms")
    return 2


if __name__ == "__main__":
    sys.exit(main())
