"""Latest-value slots — the only buffering in the bridge.

bridge-design.md §2: "Slots, not queues. Each input signal has exactly one
slot: (value, monotonic_receive_time, sim_time), overwritten by every callback.
A queue would accumulate samples the bridge is then tempted to summarise. A
slot makes latest-sample decimation the only possible behaviour."

A Slot holds exactly one Sample. `put` overwrites. There is no history, no
window and no accumulator here, so no average, no min/max hold, no edge count
and no travel integral can be computed from discarded samples (§1.1).

The `received` counter exists only so the evidence file can state the
decimation ratio R3 (§9.2) — how many samples arrived versus how many were
written. It is a count of events, never a value derived from them.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional, Union

Value = Union[float, bool]


@dataclass(frozen=True)
class Sample:
    """One received sample. Timestamps are recorded, never differenced across
    clock domains (§9.1 C1-C3)."""

    value: Value
    #: CLOCK_MONOTONIC on the bridge host, taken at subscriber callback entry.
    recv_ns: int
    #: ROS header stamp = simulation time. Recorded for decimation accounting
    #: only; never differenced against a monotonic reading (C3).
    sim_ns: Optional[int]
    #: Monotonically increasing per slot, so a cycle can tell whether the value
    #: it is about to write is the same sample it wrote last cycle.
    seq: int


class Slot:
    """Depth-1, overwrite-always holder for one signal."""

    __slots__ = ("name", "_lock", "_sample", "_received", "_written", "_seq")

    def __init__(self, name: str) -> None:
        self.name = name
        self._lock = threading.Lock()
        self._sample: Optional[Sample] = None
        self._received = 0
        self._written = 0
        self._seq = 0

    def put(self, value: Value, recv_ns: int, sim_ns: Optional[int]) -> None:
        """Overwrite the slot. The previous sample is discarded and contributes
        to nothing (§1.1)."""
        with self._lock:
            self._seq += 1
            self._received += 1
            self._sample = Sample(value=value, recv_ns=recv_ns, sim_ns=sim_ns, seq=self._seq)

    def get(self) -> Optional[Sample]:
        with self._lock:
            return self._sample

    def note_written(self) -> None:
        with self._lock:
            self._written += 1

    @property
    def has_sample(self) -> bool:
        with self._lock:
            return self._sample is not None

    @property
    def counts(self) -> tuple[int, int]:
        """(received, written) — R3 decimation accounting."""
        with self._lock:
            return self._received, self._written


class SlotSet:
    """The six input slots, addressed by their §9.3 node key."""

    def __init__(self, keys: tuple[str, ...]) -> None:
        self._slots = {key: Slot(key) for key in keys}

    def __getitem__(self, key: str) -> Slot:
        return self._slots[key]

    def keys(self) -> tuple[str, ...]:
        return tuple(self._slots)

    def items(self):
        return self._slots.items()

    def all_have_samples(self) -> bool:
        return all(slot.has_sample for slot in self._slots.values())

    def missing(self) -> list[str]:
        return [name for name, slot in self._slots.items() if not slot.has_sample]
