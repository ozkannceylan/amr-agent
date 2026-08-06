"""The ROS 2 half of the bridge: subscriptions into slots, publishers out.

Every callback does exactly three things: select the field (addressing, §4.5),
timestamp the sample, overwrite the slot. There is no filtering, no threshold,
no debounce, no latching and no edge detection here — all of that is PLC work
(§1.1).

The node carries **the groups the config declares** (§2.1). A group that is not
configured has no subscription, no publisher and no slot here: it does not
exist in the run. Adding the forklift group added slots, not kinds — its seven
topics are `std_msgs/Float64` and `std_msgs/Bool`, both of which the cell group
already carried (§2.1 G4).

Callbacks are named `cb_*` in this project: `rclpy.node.Node` owns attributes
such as `self._clock`, and a callback that collides with one is silently
shadowed (LESSONS 2026-07-27).
"""

from __future__ import annotations

import logging
import math
import time
from typing import Callable, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import JointState, LaserScan
from std_msgs.msg import Bool, Float64, UInt16

from .config import BOOL, REAL, UINT16, Config

#: The message type each value kind travels in, both directions. Marshalling,
#: not logic: the kind comes from the node model's own type column and this map
#: is the whole of the translation (§2.1 G4, §4.5).
_MSG_TYPE = {REAL: Float64, BOOL: Bool, UINT16: UInt16}
from .instrumentation import ActuationProbe, Counters, Recorder
from .slots import SlotSet

LOG = logging.getLogger("bridge.ros")


def _stamp_ns(msg) -> Optional[int]:
    try:
        stamp = msg.header.stamp
    except AttributeError:
        return None
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


class PlantInterface(Node):
    """ROS 2 node side, for every configured group. Depth-1 subscriptions: the
    middleware queue performs the latest-sample decimation, so nothing
    accumulates in bridge code (§4.6)."""

    def __init__(
        self,
        cfg: Config,
        slots: SlotSet,
        recorder: Recorder,
        counters: Counters,
        probe: ActuationProbe,
    ) -> None:
        super().__init__(cfg.ros["node_name"])
        self._cfg = cfg
        self._slots = slots
        self._recorder = recorder
        self._counters = counters
        self._probe = probe
        self._joint_name = cfg.ros.get("joint_name")

        # Sim time, kept for accounting only (§9.1 C3/C4). Never differenced
        # against a monotonic reading.
        self.set_parameters([rclpy.parameter.Parameter("use_sim_time", value=True)])

        analog_reliability = (
            ReliabilityPolicy.RELIABLE
            if cfg.ros["analog_reliability"] == "reliable"
            else ReliabilityPolicy.BEST_EFFORT
        )
        # Real-valued sources: depth 1 IS the latest-sample decimation, done by
        # the middleware queue rather than by bridge code (§4.6). The forklift's
        # sources publish at 10 Hz against the 20 Hz cycle, so nothing is
        # decimated there — depth 1 is kept anyway, so the queue can never
        # become a place where samples accumulate if a source's rate rises.
        self._analog_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=analog_reliability, durability=DurabilityPolicy.VOLATILE,
        )
        # Level signals — the four panel contacts and the forklift's field bit.
        # RELIABLE because a change must not be dropped by best-effort delivery.
        self._contact_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE,
        )

        #: Every topic this run subscribes to, for the startup QoS report.
        self._subscribed_topics: list[str] = []
        #: Output node key -> publisher, one per configured output slot. NOT
        #: `_publishers`: `rclpy.node.Node` already owns that name and holds a
        #: list in it, so assigning a dict there breaks `create_publisher` on
        #: its own next call. Same shadowing trap as the `_clock` callback of
        #: LESSONS 2026-07-27, one attribute over.
        self._out_pubs: dict[str, object] = {}
        #: Output node key -> topic name, for the QoS report and the log.
        self._out_topics: dict[str, str] = {}
        #: Output node key -> value kind, so `publish_output` marshals into the
        #: message type the node model gives that node and never into a widened
        #: Float64 (`opcua-nodes.md` §12.10's msg-type column).
        self._out_kinds: dict[str, str] = {}

        for group in cfg.signal_groups:
            topics = cfg.topics(group.name)
            for topic_key in group.structured_topics:
                self._subscribe_structured(group.name, topic_key, topics[topic_key])
            for node_key, topic_key, kind in group.scalar_inputs:
                self._subscribe_scalar(node_key, topics[topic_key], kind)
            for node_key, topic_key, kind in group.outputs:
                topic = topics[topic_key]
                self._out_pubs[node_key] = self.create_publisher(
                    _MSG_TYPE[kind], topic, self._contact_qos)
                self._out_topics[node_key] = topic
                self._out_kinds[node_key] = kind
            LOG.info(
                "group %s (%s): %d input slot(s), %d output topic(s)",
                group.name, group.reference, len(group.input_keys), len(group.outputs))

    # --- subscription wiring ----------------------------------------------

    def _subscribe_structured(self, group: str, topic_key: str, topic: str) -> None:
        """A message with several fields, out of which the bridge selects one by
        name or index (§4.5). Only the cell group has any."""
        if topic_key == "joint_state":
            self.create_subscription(JointState, topic, self.cb_joint_state, self._analog_qos)
        elif topic_key == "product_scan":
            self.create_subscription(LaserScan, topic, self.cb_product_scan, self._analog_qos)
        else:  # pragma: no cover - a group definition and this file disagreeing
            raise ValueError(f"group {group}: no callback for structured topic {topic_key!r}")
        self._subscribed_topics.append(topic)

    def _subscribe_scalar(self, node_key: str, topic: str, kind: str) -> None:
        """A `std_msgs` message whose single field `data` is the value. There is
        no index to resolve and no array to select from (§4.5) — the vehicle
        layer publishes scalars and deriving them is its job, not the bridge's."""
        if kind == BOOL:
            self.create_subscription(
                Bool, topic, lambda msg, key=node_key: self.cb_scalar_bool(key, msg),
                self._contact_qos)
        elif kind == UINT16:
            # The vehicle's applied mode and its own cycle counter. RELIABLE,
            # like the level signals: a mode readback that is dropped is a
            # disagreement the PLC would see and time (§12.6 M4), and a dropped
            # heartbeat increment is a liveness gap that never happened.
            self.create_subscription(
                UInt16, topic, lambda msg, key=node_key: self.cb_scalar_uint(key, msg),
                self._contact_qos)
        else:
            self.create_subscription(
                Float64, topic, lambda msg, key=node_key: self.cb_scalar_real(key, msg),
                self._analog_qos)
        self._subscribed_topics.append(topic)

    # --- subscriber callbacks ---------------------------------------------

    def cb_joint_state(self, msg: JointState) -> None:
        recv_ns = time.monotonic_ns()
        # Addressing by name, not by trusting index 0 (§4.5).
        try:
            i = list(msg.name).index(self._joint_name)
        except ValueError:
            self._counters.missing_joint_name += 1
            LOG.error("joint %r absent from JointState; no sample taken", self._joint_name)
            return
        sim_ns = _stamp_ns(msg)
        if i < len(msg.position):
            self._slots["ConveyorBeltPosition"].put(float(msg.position[i]), recv_ns, sim_ns)
        if i < len(msg.velocity):
            velocity = float(msg.velocity[i])
            self._slots["ConveyorBeltSpeed"].put(velocity, recv_ns, sim_ns)
            self._probe.note_belt_velocity(velocity, sim_ns)

    def cb_product_scan(self, msg: LaserScan) -> None:
        recv_ns = time.monotonic_ns()
        if not len(msg.ranges):
            self._counters.empty_scan += 1
            LOG.error("empty LaserScan.ranges; no sample taken")
            return
        value = float(msg.ranges[0])  # single-beam sensor: index 0 is the beam
        self._note_if_non_finite("ProductSensorRange", value)
        self._slots["ProductSensorRange"].put(value, recv_ns, _stamp_ns(msg))

    def cb_scalar_bool(self, key: str, msg: Bool) -> None:
        recv_ns = time.monotonic_ns()
        # No inversion, no latch, no stretch, no debounce (§1.1). This carries
        # the four panel contacts, whose TRUE is the permissive state, and
        # ForkliftObstacleInStopZone, whose TRUE is not — the polarity of each
        # belongs to the layer that publishes it and is not touched here (§4.7).
        # std_msgs/Bool has no header, so there is no sim timestamp.
        self._slots[key].put(bool(msg.data), recv_ns, None)

    def cb_scalar_uint(self, key: str, msg: UInt16) -> None:
        recv_ns = time.monotonic_ns()
        # Carried as published. The bridge does not test the mode against the
        # three defined values, does not subtract heartbeat counts and does not
        # notice a wrap: validity is an affirmative test the PLC makes, and
        # inequality is the only comparison the counter admits (§12.3, §12.6
        # V1). Any of those here would be a second interpreter (§1.1).
        self._slots[key].put(int(msg.data), recv_ns, None)

    def cb_scalar_real(self, key: str, msg: Float64) -> None:
        recv_ns = time.monotonic_ns()
        value = float(msg.data)
        self._note_if_non_finite(key, value)
        self._slots[key].put(value, recv_ns, None)

    def _note_if_non_finite(self, key: str, value: float) -> None:
        """inf / NaN are written through UNCHANGED (§4.5). No substitution, no
        clamping — only a log line and a count for the evidence file. The PLC
        tests each Real affirmatively against its plausibility window and takes
        the fault in the ELSE, so a non-finite value reads there as a sensor
        fault. Repairing it here would hide exactly that."""
        if math.isfinite(value):
            return
        self._counters.nonfinite_real_samples += 1
        LOG.warning("non-finite %s sample %r written through unchanged", key, value)
        self._recorder.row("nonfinite", key, clock="-", value=value)

    # --- publishers --------------------------------------------------------

    def publish_output(self, node_key: str, value) -> int:
        """Publish the value just read from that node, unchanged. Returns the
        monotonic timestamp taken after publish() returns (L5 end).

        No ramp, no clamp, no interlock, no zeroing, on any output slot (§4.2,
        §4.8). `ForkliftForkSpeedRef` of 0.0 means *hold*, and the bridge
        translates it into nothing: it publishes 0.0. The envelope elements are
        carried the same way: `ForkliftMotionEnable` `FALSE` and
        `ForkliftSpeedCeiling` `0.0` are published as they are read, and a
        transport that withheld or reinterpreted either would be deciding
        whether the vehicle may move (`opcua-nodes.md` §12.1, §1.1).
        """
        kind = self._out_kinds[node_key]
        msg = _MSG_TYPE[kind]()
        # Marshalling only. Float -> float64 widening, Boolean -> bool,
        # UInt16 -> uint16; no scale, no offset, no rounding.
        msg.data = (
            float(value) if kind == REAL
            else bool(value) if kind == BOOL
            else int(value)
        )
        self._out_pubs[node_key].publish(msg)
        done_ns = time.monotonic_ns()
        self._counters.publishes += 1
        if node_key == "ConveyorSpeedCommand":
            # L6 is a property of the cell simulator (§9.2). It is measurement
            # only: it holds no transported value and can gate nothing.
            self._probe.note_publish(float(value), self.sim_time_ns())
        return done_ns

    def sim_time_ns(self) -> Optional[int]:
        now = self.get_clock().now().nanoseconds
        return int(now) if now else None

    # --- startup diagnostics ----------------------------------------------

    def log_endpoint_compatibility(self) -> list[str]:
        """§4.6: mismatched QoS is silent in ROS 2 — a mismatched subscription
        simply receives nothing — so the publisher-side QoS of every subscribed
        topic is logged at startup, per configured group."""
        lines = []
        for topic in self._subscribed_topics:
            infos = self.get_publishers_info_by_topic(topic)
            if not infos:
                lines.append(f"{topic}: no publisher yet")
                continue
            for info in infos:
                qos = info.qos_profile
                lines.append(
                    f"{topic}: publisher reliability={qos.reliability.name} "
                    f"durability={qos.durability.name} history={qos.history.name} depth={qos.depth}"
                )
        for node_key, topic in self._out_topics.items():
            subs = self.get_subscriptions_info_by_topic(topic)
            lines.append(
                f"{topic}: {len(subs)} subscriber(s) "
                + ", ".join(f"reliability={s.qos_profile.reliability.name}" for s in subs)
            )
        for line in lines:
            LOG.info("QoS %s", line)
            self._recorder.row("qos", line.split(":")[0], clock="-", note=line)
        return lines
