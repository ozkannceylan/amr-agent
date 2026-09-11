#!/usr/bin/env python3
"""e4_slot.py — slot-table confusion matrix vs world-state occupancy.

NOT_RUN without the m5-ver3 plant. This file does not invent a matrix.
"""
import sys


def main(argv=None):
    print("NOT_RUN: E4 needs the m5-ver3 plant")
    print("  required: warehouse_ver3 racks, world-state occupancy, pallet_cam")
    print("  this process did not score empty/occupied/blocked")
    return 2


if __name__ == "__main__":
    sys.exit(main())
