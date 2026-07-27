"""Bridge entry point.

    python3 -m amr_bridge.main --config bridge/config/bridge.yaml

One process, two halves: an rclpy executor in its own thread and the OPC UA
client on an asyncio loop. They meet only at the latest-value slots
(bridge-design.md §2).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor

from . import config as config_mod
from .instrumentation import ActuationProbe, Counters, Recorder
from .opcua_side import PlcClient
from .ros_side import CellInterface
from .slots import SlotSet

LOG = logging.getLogger("bridge")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description="amr-agent Gazebo cell <-> PLC OPC UA bridge")
    parser.add_argument("--config", default=os.path.join(here, "config", "bridge.yaml"))
    parser.add_argument("--duration", type=float, default=None,
                        help="stop after N seconds (measurement runs); default: run until signalled")
    parser.add_argument("--evidence-csv", default=None, help="override evidence.csv_path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    cfg = config_mod.load(args.config)
    logging.basicConfig(
        level=getattr(logging, cfg.logging["level"].upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    )
    logging.getLogger("asyncua").setLevel(logging.WARNING)

    csv_path = args.evidence_csv or cfg.evidence["csv_path"]
    recorder = Recorder(csv_path, float(cfg.evidence["flush_interval_s"]))
    counters = Counters()
    probe = ActuationProbe(recorder)
    slots = SlotSet(config_mod.INPUT_KEYS)

    rclpy.init(args=None)
    node = CellInterface(cfg, slots, recorder, counters, probe)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    ros_thread = threading.Thread(target=executor.spin, name="rclpy", daemon=True)
    ros_thread.start()
    LOG.info("ROS 2 node %s spinning; config %s", cfg.ros["node_name"], cfg.path)

    client = PlcClient(cfg, slots, recorder, counters, node.publish_cmd_speed)

    def _handle_signal(signum, _frame):
        # §7.3 B / §8.3 N5: a clean shutdown writes no farewell value, zeroes
        # nothing and publishes nothing. It stops.
        LOG.info("signal %s: stopping; no farewell value, nothing zeroed", signum)
        client.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    async def _run() -> None:
        # §4.6: mismatched QoS is silent in ROS 2, so publisher-side QoS is
        # logged once discovery has had time to match. This is a diagnostic
        # print; nothing waits on it and no signal is gated by it.
        async def _qos_report() -> None:
            await asyncio.sleep(3.0)
            node.log_endpoint_compatibility()

        asyncio.ensure_future(_qos_report())
        await client.run(duration_s=args.duration)

    started = time.monotonic()
    try:
        asyncio.run(_run())
    finally:
        duration = time.monotonic() - started
        recorder.row("run", "duration_s", clock="monotonic",
                     interval_ns=int(duration * 1e9), value=round(duration, 3))
        for name, value in counters.as_rows():
            recorder.row("counter", name, clock="-", value=value)
        for name, slot in slots.items():
            received, written = slot.counts
            recorder.row("R3", name, clock="-", value=f"{received}/{written}",
                         note="samples received / samples written (decimation ratio)")
        recorder.close()
        executor.shutdown()
        ros_thread.join(timeout=5.0)
        node.destroy_node()
        rclpy.shutdown()
        LOG.info("stopped after %.1fs; evidence written to %s", duration, csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
