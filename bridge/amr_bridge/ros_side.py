"""The ROS 2 half of the bridge: subscriptions into slots, one publisher out.

Every callback does exactly three things: select the field (addressing, §4.5),
timestamp the sample, overwrite the slot. There is no filtering, no threshold,
no debounce, no latching and no edge detection here — all of that is PLC work
(§1.1).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import JointState, LaserScan
from std_msgs.msg import Bool, Float64

from .config import Config
from .instrumentation import ActuationProbe, Counters, Recorder
from .slots import SlotSet

LOG = logging.getLogger("bridge.ros")


def _stamp_ns(msg) -> Optional[int]:
    try:
        stamp = msg.header.stamp
    except AttributeError:
        return None
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


class CellInterface(Node):
    """ROS 2 node side. Depth-1 subscriptions: the middleware queue performs
    the latest-sample decimation, so nothing accumulates in bridge code
    (§4.6)."""

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
        self._joint_name = cfg.ros["joint_name"]

        # Sim time, kept for accounting only (§9.1 C3/C4). Never differenced
        # against a monotonic reading.
        self.set_parameters([rclpy.parameter.Parameter("use_sim_time", value=True)])

        analog_reliability = (
            ReliabilityPolicy.RELIABLE
            if cfg.ros["analog_reliability"] == "reliable"
            else ReliabilityPolicy.BEST_EFFORT
        )
        analog_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=analog_reliability, durability=DurabilityPolicy.VOLATILE,
        )
        contact_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE,
        )

        topics = cfg.ros["topics"]
        self.create_subscription(JointState, topics["joint_state"], self._on_joint_state, analog_qos)
        self.create_subscription(LaserScan, topics["product_scan"], self._on_scan, analog_qos)
        self.create_subscription(
            Bool, topics["panel_start"],
            lambda m: self._on_contact("PanelStartPressed", m), contact_qos)
        self.create_subscription(
            Bool, topics["panel_stop"],
            lambda m: self._on_contact("PanelStopCircuitClosed", m), contact_qos)
        self.create_subscription(
            Bool, topics["panel_process_stop"],
            lambda m: self._on_contact("PanelProcessStopCircuitClosed", m), contact_qos)

        self._cmd_pub = self.create_publisher(Float64, topics["cmd_speed"], contact_qos)

    # --- subscriber callbacks ---------------------------------------------

    def _on_joint_state(self, msg: JointState) -> None:
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

    def _on_scan(self, msg: LaserScan) -> None:
        recv_ns = time.monotonic_ns()
        if not len(msg.ranges):
            self._counters.empty_scan += 1
            LOG.error("empty LaserScan.ranges; no sample taken")
            return
        value = float(msg.ranges[0])  # single-beam sensor: index 0 is the beam
        # inf / NaN are written through UNCHANGED (§4.5). No substitution, no
        # clamping — only a log line and a count for the evidence file.
        if value != value or value in (float("inf"), float("-inf")):
            self._counters.nonfinite_range_samples += 1
            LOG.warning("non-finite ProductSensorRange sample %r written through unchanged", value)
            self._recorder.row("nonfinite", "ProductSensorRange", clock="-", value=value)
        self._slots["ProductSensorRange"].put(value, recv_ns, _stamp_ns(msg))

    def _on_contact(self, key: str, msg: Bool) -> None:
        recv_ns = time.monotonic_ns()
        # No inversion, no latch, no stretch, no debounce (§1.1). std_msgs/Bool
        # has no header, so there is no sim timestamp for a contact.
        self._slots[key].put(bool(msg.data), recv_ns, None)

    # --- publisher ---------------------------------------------------------

    def publish_cmd_speed(self, value: float) -> int:
        """Publish the value just read from the PLC, unchanged. Returns the
        monotonic timestamp taken after publish() returns (L5 end)."""
        msg = Float64()
        msg.data = value          # no ramp, no clamp, no interlock, no zeroing
        self._cmd_pub.publish(msg)
        done_ns = time.monotonic_ns()
        self._counters.publishes += 1
        self._probe.note_publish(value, self.sim_time_ns())
        return done_ns

    def sim_time_ns(self) -> Optional[int]:
        now = self.get_clock().now().nanoseconds
        return int(now) if now else None

    # --- startup diagnostics ----------------------------------------------

    def log_endpoint_compatibility(self) -> list[str]:
        """§4.6: mismatched QoS is silent in ROS 2, so the publisher-side QoS
        of every subscribed topic is logged at startup."""
        lines = []
        for topic in (
            self._cfg.ros["topics"]["joint_state"],
            self._cfg.ros["topics"]["product_scan"],
            self._cfg.ros["topics"]["panel_start"],
            self._cfg.ros["topics"]["panel_stop"],
            self._cfg.ros["topics"]["panel_process_stop"],
        ):
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
        subs = self.get_subscriptions_info_by_topic(self._cfg.ros["topics"]["cmd_speed"])
        lines.append(
            f"{self._cfg.ros['topics']['cmd_speed']}: {len(subs)} subscriber(s) "
            + ", ".join(f"reliability={s.qos_profile.reliability.name}" for s in subs)
        )
        for line in lines:
            LOG.info("QoS %s", line)
            self._recorder.row("qos", line.split(":")[0], clock="-", note=line)
        return lines
