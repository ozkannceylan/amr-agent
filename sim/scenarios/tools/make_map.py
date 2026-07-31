#!/usr/bin/env python3
"""make_map.py - deterministic occupancy grid for a world SDF.

Design choice (documented per brief m3-02): instead of SLAM-mapping the
world (non-deterministic, slow), this script writes the map directly from
the known, static world geometry.

WHAT CHANGED AT m5-08, AND WHY.

  This script used to carry a hand-copied list of rectangles taken from
  sim/worlds/warehouse.sdf, with a docstring promising that "if the world
  changes, re-run this script". That promise could not be kept: re-running
  it re-rasterised the SAME stale list. When m5-08 rewrote the warehouse
  world for M5 autonomy, every rectangle in that list became wrong, and
  nothing in the script could have said so.

  The rectangles are now READ FROM THE WORLD FILE at run time, at a scan
  plane the caller must name. Same extraction as
  scenarios/tools/landmark_map.py, which is imported rather than copied for
  exactly the reason above.

WHY `--z` IS REQUIRED AND HAS NO DEFAULT.

  A planar occupancy grid is a slice, and which slice it is decides what the
  map is FOR. The forklift's navigation lidar sweeps z = 1.80 m, so a map
  meant for AMCL to match scans against is the 1.80 m slice. A map meant for
  planning wants the geometry a vehicle can collide with, which is a
  different and lower slice. In the warehouse world the two differ
  substantially: at 1.80 m the reserve rack level is only partly loaded and
  the aisles have depth, while at 0.15 m every bay is full and the aisles
  are smooth corridors.

  Choosing between them is a NAVIGATION decision and belongs to the Nav2
  configuration brief, not to this tool. So this tool refuses to guess.

THIS TOOL NO LONGER HAS A COMMITTED OUTPUT, AND THAT IS THE POINT OF IT.
`scenarios/maps/` used to hold a map.pgm/map.yaml rasterised from the
pre-m5-08 warehouse world for the retired vehicle platform. Brief m5-08b
DELETED it: the world it described had been rewritten, its only consumers
were the two parked scripts beside this one, and a second map in a
repository whose warehouse map now has an owner is a datum with two
answers (invariant 10).

Nothing was lost, because THIS FILE is the artifact and its output is not.
Rasterising the current world takes seconds and is deterministic. What was
never decided - which plane a static map represents - is still not decided
here, and this tool still refuses to guess.

THE MAP THAT IS COMMITTED IS NOT THIS TOOL'S. `sim/maps/warehouse/` holds a
map slam_toolbox built from the vehicle's own scans and its own drifting
odometry (sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md). The two are different
kinds of thing and must not be confused: that one is what the vehicle can
actually perceive and localise against, this one is what the world file
says is there. This tool remains useful as the second opinion - a
SLAM map that disagrees with a rasterised one is a finding - and as the
generator for whatever static map m5-10 decides Nav2 wants.

Output: map.pgm + map.yaml (trinary, 0.05 m/px). Occupied = 0 (black), free
= 254 (white). Python standard library only.

Usage:
  python3 make_map.py --z 1.80 [--world PATH] [--out DIR]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from landmark_map import load_rects            # noqa: E402

RESOLUTION = 0.05          # m / pixel
ORIGIN_X, ORIGIN_Y = -15.5, -10.5   # world coords of the lower-left pixel
WIDTH_M, HEIGHT_M = 31.0, 21.0      # covers walls at |x|<=15.2, |y|<=10.2

FREE, OCCUPIED = 254, 0


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument('--z', type=float, required=True,
                    help='scan plane the grid represents [m]. No default: '
                         'see the module docstring')
    ap.add_argument('--world', default=os.path.normpath(
        os.path.join(here, '..', '..', 'worlds', 'warehouse.sdf')))
    ap.add_argument('--out', default=os.path.normpath(
        os.path.join(here, '..', 'maps')))
    ap.add_argument('--geometry', choices=('visual', 'collision'),
                    default='collision',
                    help='a map for AMCL to match lidar scans against is the '
                         'visual set, which is what a gpu_lidar renders; a '
                         'map of what a vehicle can hit is the collision set')
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rects = load_rects(args.world, args.z, kind=args.geometry)

    w_px = round(WIDTH_M / RESOLUTION)
    h_px = round(HEIGHT_M / RESOLUTION)
    grid = bytearray([FREE]) * (w_px * h_px)

    def fill(x0, x1, y0, y1):
        j0 = max(0, int((x0 - ORIGIN_X) / RESOLUTION))
        j1 = min(w_px - 1, int((x1 - ORIGIN_X) / RESOLUTION))
        i0 = max(0, int((y0 - ORIGIN_Y) / RESOLUTION))
        i1 = min(h_px - 1, int((y1 - ORIGIN_Y) / RESOLUTION))
        for i in range(i0, i1 + 1):          # i: row counted from BOTTOM
            row = (h_px - 1 - i) * w_px       # PGM stores top row first
            for j in range(j0, j1 + 1):
                grid[row + j] = OCCUPIED

    for x0, x1, y0, y1, _name in rects:
        fill(x0, x1, y0, y1)

    pgm_path = os.path.join(args.out, 'map.pgm')
    with open(pgm_path, 'wb') as f:
        f.write(b'P5\n# generated by sim/scenarios/tools/make_map.py from '
                + os.path.basename(args.world).encode()
                + f' at z = {args.z:.2f} m ({args.geometry})\n'.encode())
        f.write(f'{w_px} {h_px}\n255\n'.encode())
        f.write(bytes(grid))

    yaml_path = os.path.join(args.out, 'map.yaml')
    with open(yaml_path, 'w', newline='\n') as f:
        f.write(
            'image: map.pgm\n'
            'mode: trinary\n'
            f'resolution: {RESOLUTION}\n'
            f'origin: [{ORIGIN_X}, {ORIGIN_Y}, 0.0]\n'
            'negate: 0\n'
            'occupied_thresh: 0.65\n'
            'free_thresh: 0.25\n')

    occ = sum(1 for v in grid if v == OCCUPIED)
    print(f'wrote {pgm_path} ({w_px}x{h_px} px, {occ} occupied cells, '
          f'{len(rects)} rectangles at z = {args.z:.2f} m) and {yaml_path}')


if __name__ == '__main__':
    main()
