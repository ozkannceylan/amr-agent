#!/usr/bin/env python3
"""Read-only witness of the warning-field node, on its own OPC UA session.

TEST INSTRUMENT. It connects as a **second client**, resolves both namespaces by
URI exactly as the bridge does, and polls three things:

  * `DemoCell/Forklift/Warning/ForkliftWarningFieldOccupied` — the node under
    test (`opcua-nodes.md` §13);
  * `DemoCell/Link/BridgeHeartbeat` — the bridge's own liveness counter, a node
    this witness cannot write;
  * from those two, **a model of the consumer's own term** (below).

It writes nothing, ever. Nothing it computes reaches any process.

**The consumer model, and what it is not.** `opcua-nodes.md` §13.2 **W2** says
the PLC never reads this node bare:

    #warningFieldOccupied := node OR NOT #bridgeLinkOk

and `#bridgeLinkOk` is formed **outside** the node — from the heartbeat, with
the boot polarity §10.8 **P2** fixes: `FALSE` until the counter has been *seen
to change*, because "not yet proven stale" is not "alive" (LESSONS 2026-07-28).
This file reproduces that term so a run can show it catching a **frozen** node
that the node's own value cannot report. It is a **model in a witness**, not the
PLC and not evidence about `FB_ForkliftTeleop.scl`; the real term runs in the
standard program and nothing here substitutes for reading it there.

`HEARTBEAT_STALE_TIME` is the PLC's constant (`plc/demo-cell/SPEC.md` §3.3,
`T#500ms` ≈ ten missed beats). It is quoted here, not chosen here, and it is a
different constant from the bridge's own warning window — the two watch
different things and neither is derived from the other (§10.8 **P4**).

Usage (venv python, no ROS needed):
    python3 bridge/tools/observe_warning_node.py --config bridge/config/bridge-double-m5.yaml \\
        --csv /tmp/warning-witness.csv --seconds 60
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
import time

from asyncua import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amr_bridge import config as bridge_config  # noqa: E402

WARNING_KEY = "ForkliftWarningFieldOccupied"
HEARTBEAT_KEY = "BridgeHeartbeat"

#: The PLC's constant, quoted (`plc/demo-cell/SPEC.md` §3.3). Not the bridge's
#: warning window and never shared with it.
HEARTBEAT_STALE_TIME_S = 0.500


class LinkVerdict:
    """`BridgeLinkOk` as the PLC forms it: a seen-alive latch plus a stale timer.

    Boot polarity is the point (§10.8 P2, LESSONS 2026-07-28): the verdict is
    `FALSE` from the first sample and stays `FALSE` until the counter has
    actually moved. A verdict formed from the stale timer alone would read
    `TRUE` for the whole first window of every run.
    """

    def __init__(self, window_s: float = HEARTBEAT_STALE_TIME_S) -> None:
        self._window_s = window_s
        self._seen_alive = False
        self._last_value = None
        self._last_change_s = None

    def update(self, value: int, now_s: float) -> bool:
        if self._last_value is None:
            self._last_value = value
            return False
        if value != self._last_value:      # inequality only, never +1 (§10.8 P1)
            self._last_value = value
            self._last_change_s = now_s
            self._seen_alive = True
        stale = (
            self._last_change_s is None
            or (now_s - self._last_change_s) > self._window_s
        )
        return self._seen_alive and not stale


async def observe(args) -> int:
    cfg = bridge_config.load(args.config)
    client = Client(url=cfg.opcua["endpoint"], timeout=4, auto_reconnect=False)
    client.name = "amr-agent-warning-witness"
    await client.connect()
    try:
        ns_index = {}
        for key, uri in cfg.namespace_uris.items():
            ns_index[key] = await client.get_namespace_index(uri)
        nodes = {}
        for key in (WARNING_KEY, HEARTBEAT_KEY):
            path = [f"{ns_index[ns]}:{name}" for ns, name in cfg.browse_path(key)]
            nodes[key] = await client.nodes.objects.get_child(path)
        print(f"witness session up on {cfg.opcua['endpoint']}; "
              f"namespaces {ns_index}; polling every {args.period_s * 1000:.0f} ms")

        verdict = LinkVerdict()
        transitions = []
        started = time.monotonic()
        # Exclusive create — a witness never truncates an earlier capture.
        with open(args.csv, "x", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([
                "t_s", "wall_s", "warning_node", "bridge_heartbeat",
                "bridge_link_ok_model", "consumer_verdict_model"])
            last = None
            while (time.monotonic() - started) < args.seconds:
                now = time.monotonic()
                node_value = bool(await nodes[WARNING_KEY].read_value())
                beat = int(await nodes[HEARTBEAT_KEY].read_value())
                link_ok = verdict.update(beat, now)
                consumer = node_value or (not link_ok)
                row = (node_value, link_ok, consumer)
                writer.writerow([
                    f"{now - started:.4f}", f"{time.time():.4f}",
                    int(node_value), beat, int(link_ok), int(consumer)])
                if row != last:
                    transitions.append((now - started, node_value, link_ok, consumer))
                    print(f"{now - started:9.4f}  node={int(node_value)}  "
                          f"linkOk={int(link_ok)}  consumer={int(consumer)}", flush=True)
                    last = row
                handle.flush()
                await asyncio.sleep(args.period_s)
        print(f"witness finished: {args.csv}; {len(transitions)} transition(s)")
    finally:
        await client.disconnect()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True,
                        help="a bridge config file — used ONLY for the endpoint and "
                             "the browse paths; this witness starts no bridge")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--period-s", type=float, default=0.05,
                        help="poll period; every figure this witness reports is "
                             "quantised by it, and the runs say so")
    args = parser.parse_args()
    return asyncio.run(observe(args))


if __name__ == "__main__":
    raise SystemExit(main())
