"""mqtt_link.py - the paho shell. Wiring only; every decision is upstream.

Owns the broker connection and the spec 6.14 mechanics that MUST be set
before connecting: the last will (CONNECTIONBROKEN, QoS 1, retained) that
the BROKER publishes if this process dies without saying OFFLINE.

Events are handed to one callback as (kind, payload):
    ("broker", True/False)      connected / connection lost
    ("order", dict)             an order message, already JSON-parsed
    ("instantActions", dict)    ditto
paho runs these on ITS network thread - the callback must only queue.

The keepalive is the supervision watchdog's clock: paho notices a dead
broker within about 1.5 keepalives, so the vehicle config's supervision_s
budget is keepalive_s * 1.5 and the two are set together in cell.yaml.
"""
import json

import paho.mqtt.client as mqtt

import protocol


class MqttLink:

    def __init__(self, ident, host, port, keepalive_s, on_event, now_fn):
        self.ident = ident
        self._on_event = on_event
        self._now = now_fn
        self._headers = protocol.Headers()   # the will's headerId is ours too
        try:                                 # paho 2.x wants the API named
            self._c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except AttributeError:               # paho 1.x has no such name
            self._c = mqtt.Client()
        self._c.on_connect = self._connected
        self._c.on_disconnect = self._disconnected
        self._c.on_message = self._message
        self._c.will_set(
            protocol.topic(ident, "connection"),
            json.dumps(protocol.connection_payload(
                ident, self._headers, protocol.BROKEN, now_fn())),
            qos=1, retain=True)
        self._host, self._port, self._keepalive = host, port, keepalive_s

    def start(self):
        self._c.connect_async(self._host, self._port,
                              int(self._keepalive))
        self._c.loop_start()                 # paho's own thread from here on

    def stop(self):
        self._c.loop_stop()
        self._c.disconnect()

    def publish(self, sub, payload, qos, retain):
        self._c.publish(protocol.topic(self.ident, sub),
                        json.dumps(payload), qos=qos, retain=retain)

    # ----- paho's thread below: queue, never decide -----

    def _connected(self, _c, _u, _flags, rc):
        if rc == 0:
            for sub in ("order", "instantActions"):
                self._c.subscribe(protocol.topic(self.ident, sub), qos=0)
            self._on_event("broker", True)

    def _disconnected(self, _c, _u, rc):
        self._on_event("broker", False)

    def _message(self, _c, _u, m):
        msg = protocol.parse(m.payload)
        if msg is None:
            return
        sub = m.topic.rsplit("/", 1)[-1]
        if sub in ("order", "instantActions"):
            self._on_event(sub, msg)
