"""fleet_stub.py - master control from the command line. Wiring only.

Step 1's dispatcher: enough fleet side to exercise the vehicle's client for
real, and nothing more. Step 3 replaces it with the fleet manager; the
message builders it will keep are in dispatch_core.

    python3 m6/step1/fleet/fleet_stub.py watch
    python3 m6/step1/fleet/fleet_stub.py send FL1 S7 [S3 ...]
    python3 m6/step1/fleet/fleet_stub.py pause FL1 | resume FL1 | cancel FL1

`watch` prints one line per state/connection message from any vehicle.
`send` refuses while the vehicle is not assignable (OFFLINE, MANUAL, or an
order still pending) - the same rule the real fleet manager will apply.
"""
import json
import os
import sys
import time
import uuid

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "vda"))
sys.path.insert(0, _HERE)

import paho.mqtt.client as mqtt                       # noqa: E402

import dispatch_core                                  # noqa: E402
import protocol                                       # noqa: E402


def _connect(cell):
    try:
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    except AttributeError:
        c = mqtt.Client()
    c.connect(cell["broker"]["host"], cell["broker"]["port"],
              int(cell["broker"]["keepalive_s"]))
    return c


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    with open(os.path.join(_HERE, "..", "cell.yaml")) as f:
        cell = yaml.safe_load(f)
    # Station truth comes from the deployed step 5 image, same as the node.
    with open(os.path.join(_HERE, "..", "vehicles", "FL1.yaml")) as f:
        veh = yaml.safe_load(f)
    sys.path.insert(0, os.path.normpath(
        os.path.join(_HERE, "..", veh["step5_ipc"])))
    import stations

    cmd = sys.argv[1]
    disp = dispatch_core.Dispatcher(cell["manufacturer"])
    c = _connect(cell)

    def on_message(_c, _u, m):
        msg = protocol.parse(m.payload)
        if msg is None:
            return
        sub = m.topic.rsplit("/", 1)[-1]
        if sub == "state":
            disp.on_state(msg)
            print("[state {}] mode={} order={} last={} nodes={} drv={} "
                  "err={}".format(
                      msg.get("serialNumber"), msg.get("operatingMode"),
                      msg.get("orderId"), msg.get("lastNodeId"),
                      len(msg.get("nodeStates", [])), msg.get("driving"),
                      [e.get("errorType") for e in msg.get("errors", [])]))
        elif sub == "connection":
            disp.on_connection(msg)
            print("[connection {}] {}".format(
                msg.get("serialNumber"), msg.get("connectionState")))

    c.on_message = on_message
    base = "/".join((protocol.INTERFACE, protocol.MAJOR, "+", "+"))
    c.subscribe(base + "/state", qos=0)
    c.subscribe(base + "/connection", qos=1)
    c.loop_start()

    if cmd == "watch":
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0
    serial = sys.argv[2]
    time.sleep(1.0)                     # let the retained/live state arrive
    if cmd == "send":
        if not disp.assignable(serial):
            print("refused: {} is not assignable (offline, manual, or an "
                  "order is pending)".format(serial))
            return 1
        order = dispatch_core.transport_order(
            disp.next_order_id(), 0, stations.STATIONS, sys.argv[3:],
            cell["map_id"])
        topic, msg = disp.order_message(serial, order, time.time())
        c.publish(topic, json.dumps(msg), qos=0)
        print("sent {} -> {}: {}".format(
            msg["orderId"], serial, " ".join(sys.argv[3:])))
    elif cmd in ("pause", "resume", "cancel"):
        atype = {"pause": "startPause", "resume": "stopPause",
                 "cancel": "cancelOrder"}[cmd]
        acts = dispatch_core.instant_action(atype, str(uuid.uuid4()))
        topic, msg = disp.action_message(serial, acts, time.time())
        c.publish(topic, json.dumps(msg), qos=0)
        print("sent {} -> {}".format(atype, serial))
    else:
        print(__doc__)
        return 2
    time.sleep(0.5)                     # let paho flush before exit
    c.loop_stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
