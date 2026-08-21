"""send_order.py - a hand for master control until M6.3 exists.

Builds a FULL-ROUTE VDA 5050 order for one vehicle and one station:
reads the vehicle's current pose from its own MQTT state (no ROS - the
rig rule about starting ROS nodes stays unbroken), plans with the same
route.plan_route the on-board HMI path uses, then publishes the order.
The route the fleet sends is therefore the route the vehicle would have
planned - full-route following is exercised without inventing a second
planner. M6.3 replaces this file.

THE POSE IS NOT A NODE. plan_route prepends the truck's own position so
the follower's first segment starts under it, but an order must not name
that as a waypoint: vda_agent prepends the vehicle's CURRENT pose again
before it hands nav the polyline, and the pose read here is already
seconds old. So the order carries poly[1:] - wp1..wpN-1 and the station
itself, last, wearing the station's arrival radius.

NO TWO NODES LAND ON THE SAME POINT, so build_order does not filter for
it. The graph's nodes are dict keys and cannot share coordinates,
dijkstra never repeats a node, and the pose-drop only ever removes a
point. Swept 2026-08-21 over every station from a 0.5 m grid of the
whole hall plus every graph node and every station as a pose, the
smallest gap between consecutive order nodes was 0.40 m and exact
duplicates were zero. A de-duplicating filter here would buy nothing and
would quietly absorb a graph that had grown a real one.

PAHO 2.x IS WHAT IS INSTALLED (2.1.0, measured), the same as vda_agent:
the client names CallbackAPIVersion.VERSION2 and on_connect carries that
API's five arguments. The subscribe lives INSIDE on_connect rather than
beside connect() so it cannot race the CONNACK, and the client_id
carries this pid - two of these running at once must not evict each
other from the broker the way a shared id would.

Usage (WSL, broker and stack up, vehicle in auto):
  python3 m5_ver2/step6/tools/send_order.py f1 S4 [--watch]
"""
import argparse
import json
import os
import sys
import time
import uuid

import paho.mqtt.client as mqtt

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "ipc")))
import route                                        # noqa: E402
import vda_messages as vm                           # noqa: E402
import vda_orders as vo                             # noqa: E402
from stations import STATIONS                       # noqa: E402

STATE_WAIT_S = 10.0      # the agent publishes every 2 s; five misses
PUBLISH_WAIT_S = 2.0     # qos 0 still has to reach the socket before
WATCH_PERIOD_S = 1.0     # this process lets go of the loop thread


def build_order(order_id, poly, station_id, arrive_m):
    """poly excludes the pose; last point IS the station.

    Interleaved sequenceIds (node 2i, edge 2i+1) and everything
    released - there is no horizon until M6.3 stitches order updates.
    Only the station node carries allowedDeviationXY: arrive_m is that
    station's spur geometry (stations.py), which says nothing about a
    corner, so the waypoints stay silent and vda_orders.Progress applies
    its own default to them.
    """
    nodes, edges = [], []
    for i, (x, y) in enumerate(poly):
        last = i == len(poly) - 1
        node = {"nodeId": station_id if last else "wp{}".format(i + 1),
                "sequenceId": 2 * i, "released": True, "actions": [],
                "nodePosition": {"x": float(x), "y": float(y),
                                 "mapId": "warehouse"}}
        if last:
            node["nodePosition"]["allowedDeviationXY"] = float(arrive_m)
        nodes.append(node)
        if not last:
            edges.append({"edgeId": "e{}".format(i),
                          "sequenceId": 2 * i + 1, "released": True,
                          "startNodeId": node["nodeId"],
                          "endNodeId": "", "actions": []})
    for edge, node in zip(edges, nodes[1:]):
        edge["endNodeId"] = node["nodeId"]
    return {"orderId": order_id, "orderUpdateId": 0,
            "nodes": nodes, "edges": edges}


def main():
    parser = argparse.ArgumentParser(
        description="send one full-route VDA 5050 order to one vehicle")
    parser.add_argument("vehicle")
    parser.add_argument("station")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    # The same env var vda_agent reads, so a rig moved off 1883 moves
    # the truck and its master control together.
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("VDA_MQTT_PORT", "1883")))
    args = parser.parse_args()
    if args.station not in STATIONS:
        raise SystemExit("unknown station {} - known: {}".format(
            args.station, ", ".join(STATIONS)))

    got = {}

    def on_connect(client, userdata, flags, reason_code, properties=None):
        client.subscribe(vm.topic(args.vehicle, "state"), qos=0)

    def on_msg(client, userdata, msg):
        try:
            got["state"] = json.loads(msg.payload.decode())
        except (ValueError, UnicodeDecodeError):
            pass                    # a torn state is not this tool to fix

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="send-order-{}".format(os.getpid()))
    client.on_connect = on_connect
    client.on_message = on_msg
    try:
        client.connect(args.host, args.port)
    except OSError as exc:
        raise SystemExit("no broker at {}:{} - {}".format(
            args.host, args.port, exc))
    client.loop_start()
    try:
        _send(args, client, got)
    finally:
        client.loop_stop()
        client.disconnect()


def _send(args, client, got):
    """Wait for a pose, plan from it, publish, and optionally watch."""
    deadline = time.monotonic() + STATE_WAIT_S
    while "state" not in got and time.monotonic() < deadline:
        time.sleep(0.1)
    if "state" not in got:
        raise SystemExit(
            "no state from {} in {:.0f}s on {} - agent up? broker up?"
            .format(args.vehicle, STATE_WAIT_S,
                    vm.topic(args.vehicle, "state")))
    pos = got["state"].get("agvPosition") or {}
    if "x" not in pos or "y" not in pos:
        raise SystemExit(
            "{} reports no agvPosition - nothing to plan from".format(
                args.vehicle))
    poly = route.plan_route((pos["x"], pos["y"]), args.station)
    if poly is None:
        raise SystemExit("no route to {}".format(args.station))
    arrive_m = STATIONS[args.station].get("arrive_m", 0.25)
    order_id = "o-{}".format(uuid.uuid4().hex[:8])
    msg = build_order(order_id, poly[1:], args.station, arrive_m)
    # M1 s.3: every message on every topic carries the common header, and
    # an order is a message master control sends. One order per run, so a
    # fresh Counters honestly starts this topic's count at 1.
    msg.update(vm.Counters().header("order", args.vehicle))
    reason = vo.validate_order(msg)
    if reason:
        # The vehicle's door would say exactly this a moment later, over
        # MQTT, into a log nobody is watching. Saying it here costs a
        # gate run less.
        raise SystemExit("built an order the vehicle would reject - {}"
                         .format(reason))
    client.publish(vm.topic(args.vehicle, "order"), json.dumps(msg),
                   qos=0).wait_for_publish(timeout=PUBLISH_WAIT_S)
    print("sent", order_id, "to", args.vehicle, "->", args.station,
          "({} nodes, arrive {} m)".format(len(msg["nodes"]), arrive_m))
    if args.watch:
        _watch(got, order_id)


def _watch(got, order_id):
    """Print the vehicle's own account of the order until it is done.

    nodeStates empties only when Progress is complete and orderId stays
    ours after arrival, so the pair is the finish line. errorTypes are
    named rather than counted: safetyStop (the chain is down) and
    orderError (the door refused this order) are the two answers worth
    reading, and a bare count tells neither.
    """
    try:
        while True:
            time.sleep(WATCH_PERIOD_S)
            state = got.get("state", {})
            print("  {} last={} remaining={} driving={} errs={}".format(
                state.get("orderId", "?"), state.get("lastNodeId", "?"),
                len(state.get("nodeStates", [])), state.get("driving"),
                ",".join(e.get("errorType", "?")
                         for e in state.get("errors", [])) or "-"))
            if state.get("orderId") == order_id \
                    and not state.get("nodeStates"):
                print("ARRIVED")
                break
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
