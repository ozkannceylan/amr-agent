#!/usr/bin/env python3
"""Summarise a bridge evidence CSV into the statistics table of §9.3.

Reported for every interval: sample count, min, median, p95, max — never a
mean alone (bridge-design.md §9.3). p95 is the nearest-rank percentile
(sorted[ceil(0.95*n)-1]), which needs no interpolation assumption.

    python3 bridge/tools/summarize_latency.py bridge/evidence/latency-<date>.csv

Aggregation happens here, after the run, never inside the cycle (§9.3).
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict


def pct(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    rank = max(1, math.ceil(q * len(values)))
    return sorted(values)[rank - 1]


def fmt(value: float) -> str:
    return f"{value:.3f}"


def main(path: str) -> int:
    intervals: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    counters: dict[str, str] = {}
    ratios: dict[str, str] = {}
    duration = None
    qos: list[str] = []
    events: list[tuple[str, str, str]] = []

    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            event, name, clock = row["event"], row["name"], row["clock"]
            if event in ("L1", "L1cs", "L2", "L3", "L5", "L6", "L7", "R1", "R2", "read_rt"):
                intervals[(event, name, clock)].append(int(row["interval_ns"]) / 1e6)
            elif event == "counter":
                counters[name] = row["value"]
            elif event == "R3":
                ratios[name] = row["value"]
            elif event == "run" and name == "duration_s":
                duration = float(row["value"])
            elif event == "qos":
                qos.append(row["note"])
            elif event in ("session", "startup", "overrun", "nonfinite"):
                events.append((event, name, row["note"] or str(row["value"])))

    print(f"# Evidence summary — {path}")
    if duration is not None:
        print(f"\nRun duration: {duration:.1f} s")

    print("\n## Intervals (milliseconds)\n")
    print("| ID | signal | clock | count | min | median | p95 | max |")
    print("|---|---|---|---|---|---|---|---|")
    for key in sorted(intervals, key=lambda k: (k[0], k[1])):
        event, name, clock = key
        values = intervals[key]
        srt = sorted(values)
        median = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
        print(f"| {event} | `{name}` | {clock} | {len(values)} | {fmt(srt[0])} | "
              f"{fmt(median)} | {fmt(pct(values, 0.95))} | {fmt(srt[-1])} |")

    if intervals:
        r1 = intervals.get(("R1", "cycle", "monotonic"), [])
        if r1 and duration:
            print(f"\nAchieved cycle rate: {len(r1) / duration:.2f} Hz "
                  f"({len(r1)} cycles in {duration:.1f} s), target "
                  f"{1000.0 / (sorted(r1)[len(r1) // 2]):.2f} Hz from the median period.")
        for key, values in sorted(intervals.items()):
            if key[0] == "R2" and duration:
                print(f"Per-node write rate `{key[1]}`: {len(values) / duration:.2f} Hz")

    print("\n## R3 decimation ratio (received / written)\n")
    print("| signal | received | written | ratio |")
    print("|---|---|---|---|")
    for name, value in sorted(ratios.items()):
        received, written = value.split("/")
        ratio = (int(received) / int(written)) if int(written) else float("nan")
        print(f"| `{name}` | {received} | {written} | {ratio:.2f} : 1 |")

    print("\n## Counters\n")
    print("| counter | value |")
    print("|---|---|")
    for name, value in sorted(counters.items()):
        print(f"| {name} | {value} |")

    if qos:
        print("\n## QoS observed at startup\n")
        for line in qos:
            print(f"    {line}")

    if events:
        print("\n## Session / startup events\n")
        for event, name, note in events:
            print(f"    {event:10s} {name:24s} {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
