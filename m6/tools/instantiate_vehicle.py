"""instantiate_vehicle.py - derive one vehicle's model.sdf and config.yaml.

The sources write every gz topic explicitly and absolutely under
/forklift/, so two spawns of one file would SHARE topics. This tool is
the only thing that may vary them: a counted, mechanical prefix rewrite
/forklift/ -> /<vid>/ into m6/vehicles/<vid>/. The sources are never
edited - agv/forklift/config.yaml belongs to three stacks, and
m6/gazebo/forklift_ver2/model.sdf is the inherited plant.

The count assertion is the safety of the mechanism: a source edit that
spells a topic any other way would silently escape the rewrite, so the
derived file must contain exactly as many /<vid>/ as the source has
/forklift/, or this tool refuses.

Usage:
  python3 m6/tools/instantiate_vehicle.py --all
  python3 m6/tools/instantiate_vehicle.py f1
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6 = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_M6, ".."))
sys.path.insert(0, os.path.join(_M6, "ipc"))

PREFIX = "/forklift/"
SRC_MODEL = os.path.join(_M6, "gazebo", "forklift_ver2", "model.sdf")
SRC_CONFIG = os.path.join(_REPO, "agv", "forklift", "config.yaml")
OUT_ROOT = os.path.join(_M6, "vehicles")


def count_prefix(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read().count(PREFIX)


def _derive(src, dst, vid):
    with open(src, encoding="utf-8") as handle:
        body = handle.read()
    want = body.count(PREFIX)
    derived = body.replace(PREFIX, "/{}/".format(vid))
    got = derived.count("/{}/".format(vid))
    if got != want or PREFIX in derived:
        raise SystemExit(
            "instantiate_vehicle: rewrite miscount on {} ({} -> {})"
            .format(src, want, got))
    with open(dst, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(derived)


def instantiate(vid, out_root=OUT_ROOT):
    """Write <out_root>/<vid>/{model.sdf,config.yaml}; return the dir."""
    from status_contract import VEHICLES
    if vid not in VEHICLES:
        raise SystemExit(
            "instantiate_vehicle: unknown vehicle {!r}, valid: {}"
            .format(vid, sorted(VEHICLES)))
    out_dir = os.path.join(out_root, vid)
    os.makedirs(out_dir, exist_ok=True)
    _derive(SRC_MODEL, os.path.join(out_dir, "model.sdf"), vid)
    _derive(SRC_CONFIG, os.path.join(out_dir, "config.yaml"), vid)
    return out_dir


def main():
    from status_contract import VEHICLES
    parser = argparse.ArgumentParser()
    parser.add_argument("vehicle", nargs="?", help="one vehicle id")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    vids = sorted(VEHICLES) if args.all else [args.vehicle]
    if vids == [None]:
        parser.error("name a vehicle or pass --all")
    for vid in vids:
        print("instantiated", instantiate(vid))


if __name__ == "__main__":
    main()
