"""Measurement recording (bridge-design.md §9).

Rules honoured here:

* C1/C2 — every interval is the difference of two readings of the SAME clock.
  Monotonic intervals use `time.monotonic_ns()`; the one sim-time interval
  (L6) is a difference of two `/clock` readings and is labelled `sim`.
* §9.3 — no aggregation inside the loop. Rows are appended to an in-memory
  list and flushed to CSV periodically. Percentiles are computed afterwards by
  tools/summarize_latency.py.
* §9.3 — the instrumentation is always on. There is no "measurement mode" that
  behaves differently from the production path.

Nothing in this module can change, delay or suppress a transported value. It
observes and writes rows.
"""

from __future__ import annotations

import csv
import os
import threading
import time
from typing import Optional

COLUMNS = ["event", "name", "clock", "t_start_ns", "t_end_ns", "interval_ns", "value", "note"]


class Recorder:
    """Append-only per-event CSV recorder."""

    def __init__(self, path: str, flush_interval_s: float = 2.0) -> None:
        self.path = path
        self.flush_interval_s = flush_interval_s
        self._rows: list[list] = []
        self._lock = threading.Lock()
        self._last_flush = time.monotonic()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(self.path, "w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(COLUMNS)

    def row(
        self,
        event: str,
        name: str = "",
        clock: str = "monotonic",
        t_start_ns: Optional[int] = None,
        t_end_ns: Optional[int] = None,
        interval_ns: Optional[int] = None,
        value: object = "",
        note: str = "",
    ) -> None:
        with self._lock:
            self._rows.append([
                event, name, clock,
                "" if t_start_ns is None else t_start_ns,
                "" if t_end_ns is None else t_end_ns,
                "" if interval_ns is None else interval_ns,
                value, note,
            ])

    def maybe_flush(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_flush) < self.flush_interval_s:
            return
        with self._lock:
            rows, self._rows = self._rows, []
            self._last_flush = now
        if not rows:
            return
        with open(self.path, "a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)

    def close(self) -> None:
        self.maybe_flush(force=True)


class Counters:
    """Run-level counters written to the CSV tail (§9.3 'reported statistics')."""

    def __init__(self) -> None:
        self.cycles = 0
        self.cycle_overruns = 0
        self.write_errors = 0
        self.read_errors = 0
        self.reconnects = 0
        self.nonfinite_range_samples = 0
        self.missing_joint_name = 0
        self.empty_scan = 0
        self.publishes = 0
        self.heartbeat_writes = 0
        self.heartbeat_suppressed_cycles = 0

    def as_rows(self) -> list[tuple[str, int]]:
        return [(key, value) for key, value in sorted(vars(self).items())]


class ActuationProbe:
    """L6 — cell actuation, measured in SIM TIME (§9.2 L6, §9.1 C4).

    A *simulator* property, not a bridge property. This probe watches for the
    first belt velocity sample that reaches 50 % of a newly commanded speed and
    records the sim-time interval.

    It is measurement only: it holds no transported value, it is never
    consulted before a publish, and removing it would change nothing about
    what the bridge transports. It cannot gate, delay or alter a signal.
    """

    def __init__(self, recorder: Recorder) -> None:
        self._recorder = recorder
        self._lock = threading.Lock()
        self._pending_cmd: Optional[float] = None
        self._pending_sim_ns: Optional[int] = None
        self._last_published: Optional[float] = None

    def note_publish(self, value: float, sim_ns: Optional[int]) -> None:
        with self._lock:
            changed = self._last_published is None or value != self._last_published
            self._last_published = value
            # Only a change to a non-zero command starts a measurement; a
            # repeated identical command has no observable onset.
            if changed and value != 0.0 and sim_ns is not None:
                self._pending_cmd = value
                self._pending_sim_ns = sim_ns

    def note_belt_velocity(self, velocity: float, sim_ns: Optional[int]) -> None:
        if sim_ns is None:
            return
        with self._lock:
            cmd = self._pending_cmd
            start = self._pending_sim_ns
            if cmd is None or start is None:
                return
            if abs(velocity) < abs(cmd) * 0.5:
                return
            if (velocity >= 0) != (cmd >= 0):
                return
            self._pending_cmd = None
            self._pending_sim_ns = None
        self._recorder.row(
            "L6", "cmd_speed->belt_velocity_50pct", clock="sim",
            t_start_ns=start, t_end_ns=sim_ns, interval_ns=sim_ns - start,
            value=cmd, note="simulator property, not a bridge property",
        )
