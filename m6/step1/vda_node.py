"""vda_node.py - the VDA 5050 client's ROS shell. Wiring only.

One more vehicle-side node beside the step 5 stack: it subscribes the same
topics the HMI does (auto state, PLC status, fields, mode), publishes the
same goal seam the GO button uses, and speaks MQTT through mqtt_link. Every
decision - what to publish, when, what the goal should be - is client_core's;
this file marshals threads and parses JSON.

Run it on the owner's machine beside a started step 5 stack:

    source /opt/ros/jazzy/setup.bash
    export GZ_PARTITION=step5 ROS_DOMAIN_ID=95
    python3 m6/step1/vda_node.py [m6/step1/vehicles/FL1.yaml]

MQTT events arrive on paho's thread; they are queued and drained on the ROS
timer, so client_core runs on exactly one thread and needs no lock.
"""
import json
import os
import queue
import sys
import time

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "vda"))

import client_core                                    # noqa: E402
import protocol                                       # noqa: E402
from mqtt_link import MqttLink                        # noqa: E402


def load_cfg(vehicle_yaml):
    with open(os.path.join(_HERE, "cell.yaml")) as f:
        cell = yaml.safe_load(f)
    with open(vehicle_yaml) as f:
        veh = yaml.safe_load(f)
    return cell, veh


def main():
    vehicle_yaml = (sys.argv[1] if len(sys.argv) > 1
                    else os.path.join(_HERE, "vehicles", "FL1.yaml"))
    cell, veh = load_cfg(vehicle_yaml)

    # The step 5 contract comes from the DEPLOYED image, like every other
    # vehicle node: one contract, one home, frozen by the manifest.
    ipc = os.path.normpath(os.path.join(_HERE, veh["step5_ipc"]))
    sys.path.insert(0, ipc)
    import stations                                   # the deployed copy
    import status_contract as sc

    import rclpy
    from rclpy.node import Node
    from rclpy.qos import (DurabilityPolicy, QoSProfile)
    from std_msgs.msg import String

    ident = protocol.identity(cell["manufacturer"], veh["serial"])
    client = client_core.Client(ident, stations.STATIONS, {
        "map_id": cell["map_id"],
        "state_interval_s": veh["state_interval_s"],
        "battery_charge_pct": veh["battery_charge_pct"],
        "factsheet": veh["factsheet"]})

    rclpy.init()
    node = Node("vda_client")
    inbox = queue.Queue()
    link = MqttLink(ident, cell["broker"]["host"], cell["broker"]["port"],
                    cell["broker"]["keepalive_s"],
                    lambda kind, payload: inbox.put((kind, payload)),
                    time.time)
    goal_pub = node.create_publisher(String, sc.AUTO_GOAL_TOPIC, 10)

    def run(effects):
        for eff in effects:
            if eff[0] == "goal":
                goal_pub.publish(String(data=eff[1]))
            elif eff[0] == "publish":
                _, sub, payload, qos, retain = eff
                link.publish(sub, payload, qos, retain)

    def on_json(handler):
        def cb(msg):
            try:
                run(handler(json.loads(msg.data), time.time()))
            except ValueError:
                pass
        return cb

    node.create_subscription(String, sc.AUTO_STATE_TOPIC,
                             on_json(client.on_nav_state), 10)
    node.create_subscription(String, sc.STATUS_TOPIC,
                             on_json(client.on_plc_status), 10)
    node.create_subscription(String, sc.FIELDS_TOPIC,
                             on_json(client.on_fields), 10)
    latched = QoSProfile(depth=1,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)
    node.create_subscription(
        String, sc.MODE_TOPIC,
        lambda m: run(client.on_mode(m.data, time.time())), latched)

    def drain():
        while True:
            try:
                kind, payload = inbox.get_nowait()
            except queue.Empty:
                break
            now = time.time()
            if kind == "broker":
                run(client.on_broker(payload, now))
            elif kind == "order":
                run(client.on_order(payload, now))
            elif kind == "instantActions":
                run(client.on_instant_actions(payload, now))
        run(client.tick(time.time()))

    node.create_timer(0.1, drain)
    link.start()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        run(client.shutdown(time.time()))
        link.stop()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
