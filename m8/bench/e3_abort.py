#!/usr/bin/env python3
"""e3_abort.py — recall / false-abort on the staged fault set.

NOT_RUN without the m5-ver3 plant. This file does not invent rates.
"""
import sys


def main(argv=None):
    print("NOT_RUN: E3 needs the m5-ver3 plant and bench/faults/ staging")
    print("  required: gz-sim, forklift_ver3, pallet_cam, world-state labels")
    print("  this process did not compute recall or a false-abort rate")
    print("  proceed is never an M8 output (enforced in m8_core, not here)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
