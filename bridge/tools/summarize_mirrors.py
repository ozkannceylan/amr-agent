#!/usr/bin/env python3
"""Read back a capture written by `observe_safety_mirrors.py`. TEST INSTRUMENT.

It computes nothing about the plant. It reports, for one capture:

  * the transitions of every column (or of the columns named with --cols),
    with the row's own `t_s` and UTC stamp;
  * a `--window a b` slice printed row by row, for reading a stopping
    sequence off the sample it actually happened in;
  * `--summary`, the first and last value of every column and the number of
    distinct values it took, which is how a claim that something did NOT
    change is read off a capture rather than asserted.

Nothing here interpolates, smooths, filters or averages: every value printed
is a sample the controller served. A column that never changes prints as one
row, and that is the evidence for a negative claim — together with its n,
which is the sample count printed in the header.

Usage:
    python3 bridge/tools/summarize_mirrors.py CAPTURE.csv
    python3 bridge/tools/summarize_mirrors.py CAPTURE.csv --cols ZoneStopDemand,TractionSpeedRef
    python3 bridge/tools/summarize_mirrors.py CAPTURE.csv --window 8.0 12.0
"""

from __future__ import annotations

import argparse
import csv
import sys

#: Float columns are compared after rounding to this many decimals so that a
#: Real that dithers in its last bit does not read as a transition. It is a
#: DISPLAY tolerance on a recorded number, not a threshold applied to a plant
#: signal: nothing downstream of this script acts on anything.
FLOAT_DECIMALS = 4


def coerce(text: str):
    if text in ("True", "False"):
        return text == "True"
    try:
        value = float(text)
    except ValueError:
        return text
    if value.is_integer() and "." not in text and "e" not in text.lower():
        return int(value)
    return round(value, FLOAT_DECIMALS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture")
    ap.add_argument("--cols", default="",
                    help="comma-separated column subset; default is every column")
    ap.add_argument("--window", nargs=2, type=float, metavar=("FROM", "TO"),
                    help="print every row whose t_s lies in [FROM, TO]")
    ap.add_argument("--summary", action="store_true",
                    help="first value, last value and distinct count per column")
    args = ap.parse_args()

    with open(args.capture, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print("empty capture", file=sys.stderr)
        return 1

    fields = [f for f in rows[0] if f not in ("t_s", "utc")]
    if args.cols:
        wanted = [c.strip() for c in args.cols.split(",") if c.strip()]
        missing = [c for c in wanted if c not in fields]
        if missing:
            print(f"no such column(s): {', '.join(missing)}", file=sys.stderr)
            print(f"available: {', '.join(fields)}", file=sys.stderr)
            return 2
        fields = wanted

    span = float(rows[-1]["t_s"]) - float(rows[0]["t_s"])
    print(f"# {args.capture}")
    print(f"# n = {len(rows)} samples over {span:.2f} s "
          f"({len(rows) / span:.2f} Hz mean), {rows[0]['utc']} .. {rows[-1]['utc']}")

    if args.window:
        lo, hi = args.window
        print(f"\n## rows in t_s [{lo}, {hi}]")
        print("t_s\tutc\t" + "\t".join(fields))
        for row in rows:
            if lo <= float(row["t_s"]) <= hi:
                print(row["t_s"] + "\t" + row["utc"] + "\t"
                      + "\t".join(str(row[f]) for f in fields))
        return 0

    if args.summary:
        print("\n## column\tfirst\tlast\tdistinct\tn")
        for field in fields:
            values = [coerce(r[field]) for r in rows]
            distinct = []
            for value in values:
                if not distinct or distinct[-1] != value:
                    if value not in distinct:
                        distinct.append(value)
            print(f"{field}\t{values[0]}\t{values[-1]}\t{len(set(map(str, values)))}"
                  f"\t{len(values)}")
        return 0

    print("\n## transitions (the sample the change was first seen in)")
    any_change = False
    for field in fields:
        previous = None
        for row in rows:
            value = coerce(row[field])
            if previous is None:
                previous = value
                continue
            if value != previous:
                any_change = True
                print(f"{row['t_s']:>8}  {row['utc']}  {field}: "
                      f"{previous} -> {value}")
                previous = value
    if not any_change:
        print("(none: every column held one value for the whole capture)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
