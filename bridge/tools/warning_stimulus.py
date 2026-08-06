#!/usr/bin/env python3
"""TEST SCAFFOLDING — a scripted stand-in for the warning-field producer.

    ############################################################
    #  THIS IS NOT THE FIELD EVALUATION AND IT DOES NOT        #
    #  EVALUATE A FIELD. It publishes a scripted Bool.         #
    ############################################################

The real producer is `agv/forklift/scripts/field_evaluation.py` (m5-47): it
derives the warning verdict from two scanners and publishes it on
`/forklift/warning_field/occupied` **at its 20 Hz evaluation tick rather than on
transitions, so that its ABSENCE is visible**. This file publishes the same
topic, at the same tick, from a written script — no scan, no contour, no
debounce, no clear-hold, no verdict of any kind. It exists so that the bridge's
own silence rule (`opcua-nodes.md` §13.2 W1) can be exercised without the
simulator, and so that the one stimulus that matters — **the producer going
away** — can be applied exactly and timed.

    --script occupied:2,clear:3,silence:2.5,clear:2

Each phase is `state:seconds`; `silence` means *publish nothing at all*, which
is the stimulus this tool exists for.

**Two rules this file keeps, both learned the hard way in this repository:**

* **A stimulus that cannot apply its stimulus fails LOUD and aborts** (LESSONS
  2026-08-06). Before the script starts, this tool waits for at least one
  subscriber on the topic and exits non-zero if none appears: a run whose
  publisher was talking to nobody would show the node going occupied on silence
  for the wrong reason, and would look exactly like a pass.
* **Every run carries its own positive control.** A `silence` phase asserts an
  absence, and stillness is not evidence (LESSONS 2026-08-06): the phase before
  it must be a `clear` phase that is *seen to reach the node*, so the same run
  shows the same pipeline delivering `FALSE` when the producer is alive. This
  tool refuses a script whose first phase is `silence`, or in which a `silence`
  phase is not preceded by a live phase.

Timestamps are `CLOCK_MONOTONIC` on this host and are differenced only against
themselves (`bridge-design.md` §9.1 C1/C2). The phase boundary log is the
run's own record of when the stimulus was applied.

Usage (after sourcing /opt/ros/jazzy/setup.bash and the venv):
    python3 bridge/tools/warning_stimulus.py --script clear:3,silence:2 --events <path>
"""

from __future__ import annotations

import argparse
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool

TOPIC_DEFAULT = "/forklift/warning_field/occupied"
#: The producer's own tick (`agv/forklift/config.yaml` field.evaluate_hz = 20).
TICK_S = 0.05

LIVE_STATES = {"occupied": True, "clear": False}


class StimulusError(Exception):
    """The stimulus cannot be applied. Always fatal, never a warning that lets
    the run continue and report a result anyway."""


def parse_script(text: str) -> list[tuple[str, float]]:
    phases: list[tuple[str, float]] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        state, _, seconds = token.partition(":")
        state = state.strip().lower()
        if state not in LIVE_STATES and state != "silence":
            raise StimulusError(
                f"{token!r}: state must be one of occupied, clear, silence")
        phases.append((state, float(seconds)))
    if not phases:
        raise StimulusError("empty script")
    for index, (state, _) in enumerate(phases):
        if state != "silence":
            continue
        if index == 0 or phases[index - 1][0] == "silence":
            raise StimulusError(
                "a `silence` phase must be preceded by a live phase, so the run "
                "carries its own positive control: without one, a node that reads "
                "occupied proves nothing about the silence — it is what a dead "
                "publisher, a wrong topic name and a mismatched QoS all look like "
                "(LESSONS 2026-08-06)")
    return phases


class WarningStimulus(Node):
    def __init__(self, topic: str) -> None:
        super().__init__("warning_field_stimulus")
        # Matched to what the bridge subscribes with for a level signal
        # (`amr_bridge/ros_side.py` `_contact_qos`): KEEP_LAST depth 1,
        # RELIABLE, VOLATILE. A mismatch here is silent in ROS 2 — the
        # subscriber simply receives nothing — which is precisely the failure
        # this tool must never produce quietly.
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE)
        self._pub = self.create_publisher(Bool, topic, qos)
        self._topic = topic
        self.published = 0

    def wait_for_subscriber(self, timeout_s: float) -> int:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            count = self._pub.get_subscription_count()
            if count:
                return count
        raise StimulusError(
            f"no subscriber on {self._topic} after {timeout_s:.1f} s. Aborting "
            "rather than running: a stimulus nobody receives still produces a "
            "plausible-looking result, and that result would be a lie")

    def send(self, occupied: bool) -> None:
        message = Bool()
        message.data = occupied
        self._pub.publish(message)
        self.published += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--topic", default=TOPIC_DEFAULT)
    parser.add_argument("--script", required=True,
                        help="phases as state:seconds, comma separated; "
                             "states are occupied, clear, silence")
    parser.add_argument("--events", default=None,
                        help="write the phase boundary log here as well as to stdout")
    parser.add_argument("--subscriber-timeout-s", type=float, default=20.0)
    args = parser.parse_args()

    try:
        phases = parse_script(args.script)
    except StimulusError as exc:
        print(f"STIMULUS ABORTED: {exc}", file=sys.stderr)
        return 2

    rclpy.init()
    node = WarningStimulus(args.topic)
    lines: list[str] = []

    def note(text: str) -> None:
        print(text, flush=True)
        lines.append(text)

    try:
        count = node.wait_for_subscriber(args.subscriber_timeout_s)
        t0 = time.monotonic()
        note(f"# warning_stimulus on {args.topic}, {count} subscriber(s), "
             f"tick {TICK_S:.3f}s, t0 = monotonic {t0:.6f}")
        for state, seconds in phases:
            start = time.monotonic()
            note(f"{start - t0:9.4f} PHASE {state} for {seconds:.2f}s "
                 f"(monotonic {start:.6f})")
            end = start + seconds
            while time.monotonic() < end:
                if state != "silence":
                    node.send(LIVE_STATES[state])
                rclpy.spin_once(node, timeout_sec=0.0)
                time.sleep(TICK_S)
            if state == "silence":
                note(f"{time.monotonic() - t0:9.4f} silence ended after "
                     f"{seconds:.2f}s — nothing was published in it")
        note(f"{time.monotonic() - t0:9.4f} DONE, {node.published} message(s) published")
    except StimulusError as exc:
        print(f"STIMULUS ABORTED: {exc}", file=sys.stderr)
        return 2
    finally:
        node.destroy_node()
        rclpy.shutdown()
        if args.events:
            # Exclusive create: an event log is never truncated (LESSONS
            # 2026-07-28).
            with open(args.events, "x", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
