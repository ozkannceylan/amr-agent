#!/usr/bin/env python3
"""measure_pose_arrivals.py — the inter-arrival distribution of the vehicle's
localization pose, measured from the HMI's own side of the monitoring plane.

    #############################################################
    #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
    #############################################################

WHY IT EXISTS. `hmi/V2B-DESIGN.md` §4.3 publishes the map pane's display ramp
(`POSE_AGE_RAMP_START_MS` .. `POSE_AGE_RAMP_FULL_MS`) as **display values, not
measured ones**, and states plainly what could not be derived at the time: a
bound on the inter-arrival time of the localization pose **while the vehicle is
moving**, with its n. The only capture that existed was of a STANDING vehicle
(`viz/EVIDENCE_MONITORING.md` §8), which is the residual itself and not a
sample of the moving case. This tool takes the missing measurement.

WHAT IT DOES NOT DO, AND CANNOT. It creates nothing, writes nothing and decides
nothing. It issues `GET` at a fixed rate against a URL and writes what came
back into a CSV. It contains no threshold, applies none, and forms no verdict:
the summary it prints is arithmetic over the samples, and whether a threshold
survives it is a sentence a human writes in an evidence file. It holds no ROS
2 client of any kind — `hmi/README.md`'s boundary forbids that — and it reads
the pose only through the monitoring service's GET face, which is the same path
the operator's page reads it through.

HOW AN ARRIVAL IS TIMED, WHICH IS THE WHOLE TRICK. Polling cannot time an
arrival: the poll is slower than the event and its jitter would land in every
figure. But the payload carries `pose_age_ms`, measured by the monitoring
service on its own steady clock at the instant it answers, so

    arrival_instant  =  (this reply's instant)  −  (the age in that reply)

and the difference of two such instants is a difference of two of the
monitoring service's own measurements. The poll rate then decides only how
often a NEW arrival is noticed, never how accurately it is placed. A new
arrival is noticed by `messages_received.pose` increasing — never by the age
falling, which cannot distinguish one new message from three.

AND THE ONE THING THAT WOULD SILENTLY CORRUPT IT. If the counter advances by
more than one between two polls, the interval that was just measured contains
that many arrivals and is NOT an inter-arrival sample. Those intervals are
recorded, counted and reported separately rather than averaged in; a run whose
gaps are a large fraction of its samples is a run whose poll rate was too low
for the topic, and it says so instead of quietly reporting a stretched
distribution.

TWO CORRECTIONS THIS FILE CARRIES BECAUSE THE FIRST RUN NEEDED THEM, recorded
rather than quietly applied:

1. **The first interval of a run is not a sample.** Seeding the previous
   arrival from whatever pose happened to be standing when the run began makes
   the first interval span however long the vehicle had been parked BEFORE the
   run — 132.8 s in run 1, which duly became the reported maximum of a
   measurement whose whole subject is the moving case. Interval measurement
   therefore begins at the first arrival observed **inside** the run, and the
   run before it is discarded rather than repaired (`docs/LESSONS.md`
   2026-08-06 #104).

2. **"While moving" has to be qualified by the data, not by the operator's
   intention.** The localization publishes only after its own update
   thresholds are exceeded (a translation or a rotation), so a long
   inter-arrival is ambiguous: it can mean the estimator was slow, or it can
   mean the vehicle barely moved. This tool therefore records the pose itself
   and reports, per interval, the distance and the rotation between the two
   arrivals and the implied speed. An interval is a **moving** sample only if
   the vehicle covered ground in it; the threshold that classifies them is an
   argument with no default hidden in the code, and both populations are
   printed so nobody has to take the split on trust.

    python hmi/tools/measure_pose_arrivals.py --seconds 120 \
        --csv hmi/evidence/pose-arrivals-<date>-<run>.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
import urllib.request

#: The HMI backend's own re-served view of the monitoring plane — the path the
#: page reads. `--url` can be pointed straight at the monitoring service
#: instead, and the payload shape is detected rather than assumed.
DEFAULT_URL = "http://127.0.0.1:8088/monitor/state"


def fetch(url: str, timeout: float):
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def unwrap(payload):
    """Accept either the backend's envelope or the service's bare state."""
    if isinstance(payload, dict) and "state" in payload and "monitor" in payload:
        return payload.get("state"), payload.get("monitor")
    return payload, None


FIELDS = ("t_s", "reachable", "reason", "pose_age_ms", "pose_count",
          "obstacles_age_ms", "x_m", "y_m", "yaw_rad", "arrival_s",
          "interval_s", "messages_in_interval", "interval_m", "interval_rad")


def blank(t, reachable, reason):
    row = {k: "" for k in FIELDS}
    row["t_s"] = round(t, 4)
    row["reachable"] = reachable
    row["reason"] = reason
    return row


def summarise(name, samples):
    """Arithmetic over a population. No threshold, no verdict."""
    if not samples:
        print(f"\n{name}: no samples")
        return
    s = sorted(samples)

    def q(p):
        return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]

    print(f"\n{name}, n = {len(s)}, seconds:")
    print(f"  min {s[0]:.4f}   median {statistics.median(s):.4f}   "
          f"mean {statistics.fmean(s):.4f}")
    print(f"  p90 {q(0.90):.4f}   p95 {q(0.95):.4f}   p99 {q(0.99):.4f}   "
          f"max {s[-1]:.4f}")
    print(f"  in ms: median {statistics.median(s) * 1000:.0f}   "
          f"p90 {q(0.90) * 1000:.0f}   p95 {q(0.95) * 1000:.0f}   "
          f"max {s[-1] * 1000:.0f}")


def report(intervals, moving_speed):
    """The one summary path. Polling and re-analysis both come through here."""
    single = [i for i in intervals if i[1] == 1]
    gapped = [i for i in intervals if i[1] > 1]
    measurable = [i for i in single if i[2] is not None and i[0] > 0]

    def speed(i):
        return i[2] / i[0]

    moving = [i for i in measurable if speed(i) >= moving_speed]
    barely = [i for i in measurable if speed(i) < moving_speed]

    print(f"arrival intervals seen    {len(intervals)}  (the first arrival of "
          f"the run only SEEDS; no interval is emitted for it)")
    print(f"  single-message          {len(single)}")
    print(f"  spanned >1 message      {len(gapped)}  <- NOT inter-arrivals")
    print(f"  with a pose on both ends {len(measurable)}")
    print(f"MOVING   (>= {moving_speed} m/s across the interval)   {len(moving)}")
    print(f"STALLED  (<  {moving_speed} m/s across the interval)   {len(barely)}")

    summarise("MOVING inter-arrival of the pose", [i[0] for i in moving])
    if moving:
        speeds = [speed(i) for i in moving]
        print(f"  ground per interval: median "
              f"{statistics.median([i[2] for i in moving]):.3f} m; implied "
              f"speed median {statistics.median(speeds):.3f} m/s, min "
              f"{min(speeds):.3f}, max {max(speeds):.3f} m/s")
    summarise("STALLED intervals (the vehicle, not the estimator — context, "
              "not the measurement)", [i[0] for i in barely])
    if gapped:
        print("\nintervals that contained more than one arrival (poll too "
              "slow for those instants):")
        for g, d, *_ in gapped[:12]:
            print(f"  {g:.4f} s carried {d} messages")
    return moving, barely


def analyse(args) -> int:
    """Re-derive the summary from a CSV this tool wrote."""
    with open(args.analyse, newline="", encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n")
        rows = list(csv.DictReader(handle))
    print(f"re-analysing {args.analyse}")
    print(f"  its header line: {header}")
    intervals = []
    for row in rows:
        if not row.get("interval_s"):
            continue
        intervals.append((
            float(row["interval_s"]),
            int(row["messages_in_interval"]),
            None if not row.get("interval_m") else float(row["interval_m"]),
            None if not row.get("interval_rad") else float(row["interval_rad"]),
        ))
    print(f"  {len(rows)} samples, {len(intervals)} intervals\n")
    report(intervals, args.moving_speed)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--serial", default=None,
                    help="appended as ?serial= when the URL is the backend's")
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--rate", type=float, default=20.0,
                    help="polls per second. Must be well above the topic's own "
                         "rate or gaps dominate; the run reports how many it saw")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--timeout", type=float, default=2.0)
    ap.add_argument("--label", default="", help="written into the CSV header line")
    ap.add_argument("--moving-speed", type=float, default=0.10,
                    help="an interval counts as a MOVING sample when the pose "
                         "advanced at this speed or better across it [m/s]. "
                         "DISTANCE cannot do this job and the first two runs "
                         "showed why: the localization publishes only after a "
                         "fixed distance, so every interval covers about that "
                         "distance BY CONSTRUCTION and a distance test passes "
                         "everything, a stall included. Both populations are "
                         "printed, so the split is visible rather than trusted")
    ap.add_argument("--analyse", default=None,
                    help="re-derive the summary from a CSV this tool already "
                         "wrote, instead of polling. The classifier can then "
                         "be changed without re-driving the vehicle, and a "
                         "committed capture stays re-checkable")
    args = ap.parse_args()

    if args.analyse:
        return analyse(args)

    url = args.url
    if args.serial:
        url += ("&" if "?" in url else "?") + "serial=" + args.serial

    rows = []
    period = 1.0 / args.rate
    started = time.monotonic()
    deadline = started + args.seconds
    last_count = None
    last_arrival = None
    last_pose = None
    intervals = []          # (interval_s, n_messages, metres, radians)
    unreachable = 0
    next_poll = started

    print(f"measure_pose_arrivals: GET {url} at {args.rate:.0f} Hz "
          f"for {args.seconds:.0f} s   label={args.label!r}")
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now < next_poll:
            time.sleep(min(period, next_poll - now))
            continue
        next_poll += period
        t = time.monotonic()
        try:
            state, meta = unwrap(fetch(url, args.timeout))
        except Exception as exc:                       # noqa: BLE001
            unreachable += 1
            rows.append(blank(t - started, False,
                              f"{type(exc).__name__}: {exc}"))
            continue
        if not state:
            unreachable += 1
            reason = (meta or {}).get("reason") if meta else "no state in payload"
            rows.append(blank(t - started, False, reason))
            continue

        age = state.get("pose_age_ms")
        count = (state.get("messages_received") or {}).get("pose")
        pose = state.get("pose") or {}
        row = blank(t - started, True, "")
        row.update({"pose_age_ms": age, "pose_count": count,
                    "obstacles_age_ms": state.get("obstacles_age_ms"),
                    "x_m": pose.get("x_m"), "y_m": pose.get("y_m"),
                    "yaw_rad": pose.get("yaw_rad")})

        if count is not None and age is not None:
            arrival = (t - started) - age / 1000.0
            row["arrival_s"] = round(arrival, 4)
            if last_count is not None and count > last_count:
                delta = count - last_count
                # The FIRST arrival seen inside the run only seeds the
                # measurement; the interval before it reaches back to whenever
                # the vehicle was last moving, which is not this run's data.
                if last_arrival is not None:
                    gap = arrival - last_arrival
                    metres = radians = None
                    if last_pose and pose:
                        metres = math.hypot(pose["x_m"] - last_pose["x_m"],
                                            pose["y_m"] - last_pose["y_m"])
                        radians = abs(math.atan2(
                            math.sin(pose["yaw_rad"] - last_pose["yaw_rad"]),
                            math.cos(pose["yaw_rad"] - last_pose["yaw_rad"])))
                    row["interval_s"] = round(gap, 4)
                    row["messages_in_interval"] = delta
                    row["interval_m"] = None if metres is None else round(metres, 4)
                    row["interval_rad"] = (None if radians is None
                                           else round(radians, 4))
                    intervals.append((gap, delta, metres, radians))
                last_arrival = arrival
                last_pose = dict(pose) if pose else None
            elif last_count is None:
                # Seed only — no interval is emitted for it.
                last_pose = dict(pose) if pose else None
            last_count = count
        elif count is not None:
            last_count = count
        rows.append(row)

    achieved = time.monotonic() - started
    print()
    print(f"run seconds               {achieved:.1f}")
    print(f"samples polled            {len(rows)}  "
          f"(effective {len(rows) / achieved:.1f} Hz against {args.rate:.0f} Hz "
          f"asked — each poll is two upstream GETs)")
    print(f"polls with no answer      {unreachable}")
    report(intervals, args.moving_speed)

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as handle:
            handle.write(f"# measure_pose_arrivals {args.label} url={url} "
                         f"rate={args.rate} seconds={args.seconds} "
                         f"moving_speed={args.moving_speed}\n")
            writer = csv.DictWriter(handle, fieldnames=list(FIELDS))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nwrote {len(rows)} samples to {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
