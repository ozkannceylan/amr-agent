"""Configuration loading, and the configured signal set (bridge-design.md §2.1).

The config file carries addresses, cadences and housekeeping only. This loader
rejects unknown keys so that a threshold, tolerance or timer cannot be smuggled
in through configuration (bridge-design.md §2, §1.1).

**Groups, not a fixed signal list.** The bridge carries *signal groups*: named
sets of slots that travel together because they belong to one plant and one
node-model section — the **cell** group (`opcua-nodes.md` §9) and the
**forklift** group (§10). The config declares which groups a run carries; the
union of their slots is that run's **configured signal set**, and it is the only
set any rule counts (§2.1):

* G1 — a group absent from the config contributes nothing: no subscription, no
  slot, no node resolution, no write, no poll, no diagnostics read and **no
  entry in the write allowlist**. It is not a disabled feature that idles;
* G2 — every per-signal rule (startup R3, write-on-change and refresh, the
  reconnect refresh and the rewrite after a detected server restart) applies to
  every slot in the configured set and to no other. **No rule names a fixed
  count**;
* G3 — groups are not a runtime mode. The set is fixed at startup by the config
  and logged there;
* G4 — a group adds slots, not kinds: Real, Bool and UInt16 only;
* G5 — one heartbeat for the whole process, not one per group.

The group *definitions* below are a transcription of the node model's tables
(§9.3/§9.4/§9.5 and §10.5/§10.6/§10.7), in the order those sections document
them. The *addresses* — BrowseName paths and topic names — stay in the config
file. The **write allowlist is derived** from the configured groups by
`Config.write_allowlist`; there is no second, hand-maintained list beside it
(§4.10, consequence 1).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterator

import yaml

# Keys the loader accepts, per section. Anything else is a configuration error.
_SCHEMA: dict[str, set[str]] = {
    "opcua": {
        "endpoint", "namespace_uris", "security_policy", "certificate_path",
        "private_key_path", "username", "requested_session_timeout_ms",
        "session_name", "reconnect_interval_s", "reconnect_backoff_max_s",
    },
    "nodes": {"interface_path", "heartbeat", "groups"},
    "ros": {"node_name", "topics", "joint_name", "analog_reliability"},
    "cycle": {"period_s", "status_poll_period_s"},
    "evidence": {"csv_path", "flush_interval_s"},
    "logging": {"level"},
}

#: Top-level key that is a list rather than a section: the configured signal set.
GROUPS_KEY = "groups"

# The two namespaces the browse path crosses (bridge-design.md §3.1 N2). Both
# are resolved to an index by URI at every session establishment; neither index
# is ever configured, hardcoded or derived from the other. The forklift group
# adds a LEVEL, not a namespace (§3.1 N7): `DemoCell/Forklift/…` resolves under
# the same interface node as `DemoCell/Input/…`.
NS_SERVER_INTERFACES = "server_interfaces"   # vendor-fixed Siemens namespace
NS_INTERFACE = "interface"                   # = the TIA server interface name (ADR 0006)
NAMESPACE_KEYS: tuple[str, ...] = (NS_SERVER_INTERFACES, NS_INTERFACE)

#: Value kinds a group may bring (§2.1 G4). Nothing else exists.
REAL = "real"      # S7 Real / OPC UA Float
BOOL = "bool"      # S7 Bool / OPC UA Boolean
#: S7 UInt / OPC UA UInt16. The bridge has generated a UInt16 since m3-04 — its
#: own heartbeat — but until the §12 group it had never CARRIED one from or to a
#: topic (`opcua-nodes.md` §12.10). It is a value type §2.1 G4 already admits and
#: `std_msgs/UInt16` needs no new dependency: a group adds slots, not kinds.
UINT16 = "uint16"

#: --------------------------------------------------------------------------
#: The warning-field slot's freshness window (`opcua-nodes.md` §13.2 **W1**,
#: `bridge-design.md` §4.11 row 23).
#:
#: The producer publishes `/forklift/warning_field/occupied` **at its evaluation
#: tick rather than on transitions, so that its ABSENCE is visible**
#: (`agv/forklift/FIELD-EVALUATION.md` §12 phase 2, LESSONS 2026-08-04). An OPC
#: UA node is a held value, so the seam is by construction the republishing
#: layer that rule exists to defeat: the bridge is the last layer that can
#: observe the silence, and it converts it into an explicit `TRUE`.
#:
#: **This is a freshness window over the bridge's OWN INPUT CHANNEL** — the
#: timer class §7.2 admits, beside the bridge's own 20 Hz cycle. It is not a
#: debounce, not a fault delay and not a dwell over a plant value: the verdict
#: is the field evaluation's and is never computed here; what is timed is
#: whether this bridge has heard from its producer.
#:
#: **The rule is the multiple, not the millisecond** (the `UI_POLL_STALE_TIME`
#: and `HMI_STALE_TIME` discipline, `opcua-nodes.md` §10.8 P3): ten of the
#: producer's own ticks. If the producer's rate changes, the window is
#: re-derived from the new tick, and if a commissioning measurement shows a
#: worst-case inter-arrival above the window the multiple is re-derived from the
#: measurement rather than the tick being quietly reinterpreted.
#:
#: **Its own constant, shared with nothing** (§10.8 P4). Four stale windows now
#: exist in this cell and no two share a derivation: `HEARTBEAT_STALE_TIME`
#: (PLC, 500 ms), `HMI_STALE_TIME` (PLC, 600 ms), `UI_POLL_STALE_TIME` (HMI
#: backend, 1.0 s) and `FIELD_LINK_STALE_MAX` (the stand-in writer, 1.0 s, over
#: the *protective* link and a different transport). Retuning one must not
#: silently retune another.
WARNING_PRODUCER_TICK_S = 0.05          # 20 Hz, agv/forklift/config.yaml field.evaluate_hz
WARNING_STALE_TICK_MULTIPLE = 10        # the rule; the number below is derived from it
WARNING_FIELD_STALE_MAX_S = WARNING_PRODUCER_TICK_S * WARNING_STALE_TICK_MULTIPLE  # 0.50 s


@dataclass(frozen=True)
class StaleAssert:
    """A slot whose SILENCE is itself a value, asserted explicitly.

    The ordinary slot rule is R1: no sample, no write, no default, ever. A slot
    carrying one of these is the documented exception the node model rules for
    one node (`opcua-nodes.md` §13.2 W1): while its latest sample is older than
    `window_s`, the value written to the node is `asserted_value` instead of the
    slot's value, so a reader of the node never sees a stale reading presented
    as a fresh one.

    R1 is **not** weakened: before the first sample there is still no write at
    all, and the node's DB start value — the same non-permissive value — covers
    those scans (W3).
    """

    node_key: str
    window_s: float
    #: The value silence means. Transcribed from the node model, never chosen
    #: here: it is the node's own start value and its fail direction.
    asserted_value: bool
    reference: str


#: Write cadence of an input slot (§5). Not a timer and not a policy the bridge
#: chooses per run: it is transcribed from the node model's own cadence column,
#: per signal, and it is why the two `Forklift/Vehicle/` nodes differ from each
#: other despite sharing a type (`opcua-nodes.md` §12.6, last paragraph).
CYCLIC = "cyclic"          # written every cycle from the slot's latest value
ON_CHANGE = "on_change"    # written when the value changes, plus every refresh

#: The one node the bridge writes for itself, shared by every configured group
#: (§2.1 G5, opcua-nodes.md §9.7, §10.11: there is no second heartbeat). It is a
#: §9 node used by every configuration, which is why a forklift-only run touches
#: 13 nodes and not 12.
HEARTBEAT_KEY = "BridgeHeartbeat"

#: Node tables a group may configure. `inputs` and the heartbeat are the only
#: writable positions in the whole model (§3, §4.10).
NODE_TABLES: tuple[str, ...] = ("inputs", "outputs", "diagnostics")
WRITABLE_TABLES: tuple[str, ...] = ("inputs",)


@dataclass(frozen=True)
class SignalGroup:
    """One signal group: the slots of one plant and one node-model section."""

    name: str
    #: Where the authoritative node table lives. Quoted in log lines and errors.
    reference: str
    #: (node key, kind, cadence) for every input the bridge WRITES, in the node
    #: model's documented order. The cell's order is §9.3's (panel contacts
    #: grouped by failure direction); the forklift's is §10.5's; the envelope
    #: group's is §12.10's. The cadence is transcribed from the same table.
    inputs: tuple[tuple[str, str, str], ...]
    #: (node key, ROS topic key, kind) for every output the bridge READS and
    #: applies. The kind is the published message's type: a group that carries a
    #: `UInt16` output publishes `std_msgs/UInt16`, not a widened Float64.
    outputs: tuple[tuple[str, str, str], ...]
    #: Nodes read at the diagnostics rate, logged and applied to nothing.
    diagnostics: tuple[str, ...]
    #: (node key, ROS topic key, kind) for inputs that arrive as a whole
    #: `std_msgs` message whose single field is the value. Addressing only.
    scalar_inputs: tuple[tuple[str, str, str], ...]
    #: Topic keys carried by a message type with several fields, where the
    #: bridge selects a field by name or index (§4.5). Handled by their own
    #: callbacks on the ROS side.
    structured_topics: tuple[str, ...]
    #: True if this group needs `ros.joint_name` (the belt encoder's joint).
    needs_joint_name: bool = False
    #: Slots whose silence is asserted rather than held (§13.2 W1). Empty for
    #: every group but the warning group.
    stale_asserts: tuple[StaleAssert, ...] = ()
    #: Node keys this group may find ABSENT from the server without failing the
    #: connect (`opcua-nodes.md` §11.6: *"no client's connect may fail over this
    #: group"*). Addressing only: an absent node is resolved on no session, read
    #: in no cycle and published on no topic — never replaced by a value. The
    #: tolerance is per node and per group, so a mistyped BrowseName anywhere
    #: else is still the fatal configuration error it has always been (§3.1 N4),
    #: and absence is re-tested at every session establishment rather than
    #: remembered.
    optional_nodes: tuple[str, ...] = ()

    @property
    def input_keys(self) -> tuple[str, ...]:
        return tuple(key for key, _kind, _cadence in self.inputs)

    @property
    def output_keys(self) -> tuple[str, ...]:
        return tuple(key for key, _topic, _kind in self.outputs)

    @property
    def topic_keys(self) -> tuple[str, ...]:
        """Every topic key this group needs in `ros.topics.<group>`."""
        return (
            self.structured_topics
            + tuple(topic for _, topic, _ in self.scalar_inputs)
            + tuple(topic for _, topic, _ in self.outputs)
        )


#: Demonstration cell — `opcua-nodes.md` §9, ADR 0004, gate M3.
CELL_GROUP = SignalGroup(
    name="cell",
    reference="opcua-nodes.md §9",
    inputs=(
        ("ConveyorBeltPosition", REAL, CYCLIC),
        ("ConveyorBeltSpeed", REAL, CYCLIC),
        ("ProductSensorRange", REAL, CYCLIC),
        ("PanelStartPressed", BOOL, ON_CHANGE),
        ("PanelResetPressed", BOOL, ON_CHANGE),
        ("PanelStopCircuitClosed", BOOL, ON_CHANGE),
        ("PanelProcessStopCircuitClosed", BOOL, ON_CHANGE),
    ),
    outputs=(("ConveyorSpeedCommand", "cmd_speed", REAL),),
    diagnostics=(
        "CellCycleRunning",
        "CellProcessStopActive",
        "CellResetRequired",
        "ProductPresentAtSensor",
        "ConveyorDriveFault",
        "BridgeLinkOk",
    ),
    scalar_inputs=(
        ("PanelStartPressed", "panel_start", BOOL),
        ("PanelResetPressed", "panel_reset", BOOL),
        ("PanelStopCircuitClosed", "panel_stop", BOOL),
        ("PanelProcessStopCircuitClosed", "panel_process_stop", BOOL),
    ),
    structured_topics=("joint_state", "product_scan"),
    needs_joint_name=True,
)

#: Forklift commissioning cell — `opcua-nodes.md` §10, ADR 0008, gate M4.
#: Four inputs, three outputs, five diagnostics. The five `Forklift/Hmi/`
#: requests and `Forklift/Link/HmiHeartbeat` appear NOWHERE in this definition:
#: the bridge never reads and never writes them, in any configuration (§4.10).
FORKLIFT_GROUP = SignalGroup(
    name="forklift",
    reference="opcua-nodes.md §10",
    inputs=(
        ("ForkliftForkHeight", REAL, CYCLIC),
        ("ForkliftLinearSpeed", REAL, CYCLIC),
        # TRUE is the non-permissive state and it is carried UNINVERTED (§4.7
        # row 12, opcua-nodes.md §10.5). The polarity belongs to the vehicle
        # layer at one end and to the PLC at the other; inverting it in
        # transport would put it in two places.
        ("ForkliftObstacleInStopZone", BOOL, ON_CHANGE),
        ("ForkliftObstacleMinDistance", REAL, CYCLIC),
    ),
    outputs=(
        ("ForkliftTractionSpeedRef", "cmd_traction_speed", REAL),
        ("ForkliftSteerAngleRef", "cmd_steer_angle", REAL),
        ("ForkliftForkSpeedRef", "cmd_fork_speed", REAL),
    ),
    diagnostics=(
        "ForkliftTeleopActive",
        "ForkliftObstacleStopActive",
        "ForkliftSpeedLimitActive",
        "ForkliftResetRequired",
        # The PLC's verdict on the OTHER client's liveness. Logged so a
        # recording shows both link verdicts side by side; it gates nothing
        # (§4.9). Reading `HmiLinkOk` is admitted by §10.3's reader column;
        # reading `HmiHeartbeat` is not, and it is absent here.
        "HmiLinkOk",
    ),
    scalar_inputs=(
        ("ForkliftForkHeight", "fork_height", REAL),
        ("ForkliftLinearSpeed", "linear_speed", REAL),
        ("ForkliftObstacleInStopZone", "obstacle_in_stop_zone", BOOL),
        ("ForkliftObstacleMinDistance", "obstacle_min_distance", REAL),
    ),
    structured_topics=(),
)

#: The autonomy envelope, the drive mode and the vehicle's report back —
#: `opcua-nodes.md` §12, ADR 0011 D3 as refined by ADR 0012 D1, gate M5.
#:
#: **A THIRD GROUP, not an enlargement of the forklift group.** A group is "a
#: named set of slots that travel together because they belong to one plant and
#: one node-model section" (`bridge-design.md` §2.1); these six slots are §12's,
#: they live in four DBs of their own, and every committed count of the forklift
#: group (4in/3out/5diag, 13 nodes, a 5-key allowlist) stays true untouched.
#: `opcua-nodes.md` §12.13 item 1 leaves the choice open — "whether these six
#: slots join the forklift group or form a third" — and names the **interface
#: agent** as its owner. This definition is therefore the bridge's proposal
#: carried into code so it could be run and measured; it is not the interface
#: ruling, and `bridge-design.md` does not yet carry this group at all
#: (requested in the m5-44 report).
#:
#: **Nothing here is logic.** The envelope is formed in the PLC and carried
#: unchanged: no threshold on the ceiling, no interpretation of the enable, no
#: comparison of the mode in force against the mode applied — that comparison is
#: the PLC's own (`FB_ForkliftTeleop.scl`, §14) and a bridge that made it would
#: be a second owner of a verdict (invariant 10, §1.1).
#:
#: The two HMI-written nodes of §12 — `Mode/HmiDriveModeRequest` and
#: `ProcessStop/HmiProcessStopRequest` — appear NOWHERE below, in either
#: direction, exactly as the five `Forklift/Hmi/` requests do not (§4.10,
#: `opcua-nodes.md` §12.10's "deliberately reach no topic" table).
ENVELOPE_GROUP = SignalGroup(
    name="envelope",
    reference="opcua-nodes.md §12",
    inputs=(
        # The vehicle's control layer owns both values; the bridge writes both
        # nodes (§12.2, "value owner and node writer are different roles"). The
        # two cadences are §12.6's own, and they differ despite the shared type:
        # the mode applied is a level and is written on change, the heartbeat is
        # a counter whose whole meaning is that it keeps moving.
        ("ForkliftVehicleModeApplied", UINT16, ON_CHANGE),
        ("ForkliftVehicleHeartbeat", UINT16, CYCLIC),
    ),
    outputs=(
        # The mode in force — the authoritative answer to "what mode is the
        # machine in" (§12.3 M1), republished so the vehicle can select its
        # control law from the node it read rather than from what it sent.
        ("ForkliftDriveModeActive", "mode_in_force", UINT16),
        # The three envelope elements. A PERMISSION, A BOUND AND A READINESS —
        # never a command (§12.1, E6). The ceiling is unsigned and is not a
        # setpoint (E2); the bridge neither clamps it nor compares it with
        # anything (§1.1).
        ("ForkliftMotionEnable", "envelope_motion_enable", BOOL),
        ("ForkliftSpeedCeiling", "envelope_speed_ceiling", REAL),
        ("ForkliftEquipmentPermit", "envelope_equipment_permit", BOOL),
    ),
    diagnostics=(
        # The operator's latched process stop: a PLC verdict, read for the log
        # and applied to nothing. It deliberately reaches NO topic — the stop
        # reaches the vehicle through the envelope and the setpoints, and a
        # second path would be a second owner of one reaction (§12.7 PS6,
        # §12.10's own table).
        "ForkliftProcessStopActive",
    ),
    scalar_inputs=(
        ("ForkliftVehicleModeApplied", "mode_applied", UINT16),
        ("ForkliftVehicleHeartbeat", "vehicle_heartbeat", UINT16),
    ),
    structured_topics=(),
)

#: The warning-field verdict — `opcua-nodes.md` §13, `bridge-design.md` §4.11
#: row 23, gate M5. **One node, one topic, one direction.**
#:
#: `TRUE` = the warning field is occupied, **or the verdict is stale, silent or
#: has never been heard**. The value is the field evaluation's
#: (`agv/forklift/scripts/field_evaluation.py`, m5-47); the bridge is the node's
#: writer and never its author (invariant 10, §12.2's "value owner and node
#: writer are different roles"). Nothing is inverted, thresholded, latched or
#: debounced here: the only thing this group adds beyond a carried Bool is the
#: `StaleAssert` above, which times the bridge's own input channel.
#:
#: **Why a fourth group rather than three more rows in the envelope group, and
#: what is requested of the interface agent.** `bridge-design.md` §4.11 carries
#: row 23 inside the envelope group's section — whose title distinguishes
#: "§12's nine nodes" from "the §13 warning slot" — and this definition is the
#: bridge's implementation of that row, with the packaging chosen for two
#: reasons and stated so it can be overruled in one edit:
#:
#: 1. §2.1's own definition of a group is "one plant and one node-model
#:    section". §13 is its own section, its own folder `Forklift/Warning/`, its
#:    own one-member DB `ForkliftWarning`, and its producer is the field
#:    evaluation rather than the vehicle's control layer;
#: 2. **the node does not exist on the controller in force.** It is created by
#:    `plc/forklift/TIA-BUILD-PROCEDURE.md` chunk X, after step 338. A group
#:    that is declared separately is the only shape in which the committed
#:    `bridge/config/bridge.yaml` keeps resolving against the CPU that is
#:    running today (`_check_group_tables` requires a configured group to name
#:    exactly its section's nodes, so folding row 23 into the envelope group
#:    would make every envelope run fail at node resolution until chunk X
#:    lands). LESSONS 2026-08-06: probe the server before editing a client
#:    config written against a different build of the program.
#:
#: Either way the derived consequences §4.11 states hold unchanged: the write
#: allowlist gains exactly this one key when the group is configured, and it is
#: still derived from the configured groups rather than hand-maintained.
WARNING_GROUP = SignalGroup(
    name="warning",
    reference="opcua-nodes.md §13",
    inputs=(
        # Written on change — plus the explicit `TRUE` of W1 when the window
        # expires, plus the refresh on every (re)connect and after a detected
        # server restart (W4). The expiry needs no cadence of its own: the
        # asserted value simply becomes the value this slot writes, so the
        # on-change comparison emits it as the change it is.
        ("ForkliftWarningFieldOccupied", BOOL, ON_CHANGE),
    ),
    outputs=(),
    diagnostics=(),
    scalar_inputs=(
        ("ForkliftWarningFieldOccupied", "warning_field_occupied", BOOL),
    ),
    structured_topics=(),
    stale_asserts=(
        StaleAssert(
            node_key="ForkliftWarningFieldOccupied",
            window_s=WARNING_FIELD_STALE_MAX_S,
            asserted_value=True,
            reference="opcua-nodes.md §13.2 W1",
        ),
    ),
)

#: The F-program's SS1 second-stage demand, carried to the vehicle's torque-off
#: stand-in — `opcua-nodes.md` §11 and its **§11.2b SD1–SD10**, gate M5.
#: **One node, one topic, one direction: the bridge READS and republishes.**
#:
#: `TorqueOffDemand` is the one mirror in §11 that a consumer acts on (§11.2b
#: **SD2**). The value is the F-program's, mirrored into a standard DB by the
#: standard program; the bridge is a reader of that mirror and never its author,
#: and it writes nothing anywhere in `Forklift/Safety/` — read-only to every
#: client (§11.4 **MR1**). That is not a rule this file restates and hopes for:
#: this group declares **no inputs**, and the write allowlist is *derived* from
#: the configured groups' inputs (`Config.write_allowlist`), so configuring the
#: group adds exactly zero writable keys.
#:
#: **`SpeedMonitorDemand` is deliberately absent, and so are the other four
#: mirrors** (**SD1**). The speed monitor's reaction is the PLC's permissive,
#: formed from F-data directly; what reaches the vehicle is the consequence —
#: the permissive drops, the setpoints take `0.0`, the envelope goes
#: non-permissive — through no stop topic of its own. A slot here would be a
#: second path to one reaction, which is a second owner of it (§12.7 **PS6**).
#: The remaining four are display-only. **Nothing but a demand Bool crosses this
#: seam**: no speed, no limit, no margin, no channel reading and no value that
#: was exceeded (**SD7**, ADR 0014 D4).
#:
#: **SD5 — and it is the deliberate opposite of the warning group above.**
#: This group has **no `StaleAssert`, no freshness window and no synthesised
#: value in either polarity**, and that asymmetry is the ruling rather than an
#: oversight. `WARNING_GROUP` converts its producer's silence into an explicit
#: `TRUE` because silence there must not read as a fresh clear. Here a stale,
#: silent or never-resolved demand is **NOT torque-off**: the consumer latches on
#: an *observed* `TRUE` and releases on an *observed* `FALSE`, and a link that
#: never speaks leaves it closed. Three reasons, none of them interchangeable —
#: loss of supervision is a degraded mode and not a safety event (invariant 2);
#: the controlled stop a lost link calls for already exists one layer up in the
#: envelope gate's freshness rule (§12.4 **E5**), so inferring a stop here would
#: be a second owner of it; and torque removal is asserted, never inferred,
#: because a safety reaction riding the network's silence is exactly what
#: invariant 1 keeps off the network. A later reader who finds this asymmetry
#: surprising is reading it correctly: **the reason is in this comment and the
#: other behaviour is in no line of this package.**
#:
#: **The node may legitimately be absent, and absence is not an error** (§11.6).
#: The leaf is created by the same TIA delta that adds the copy statements to the
#: standard program (`plc/forklift/TIA-FIX-PROCEDURE.md` chunks AD–AF); until
#: that delta is applied the server has a `Forklift/Safety/` folder with four
#: mirrors and not six — measured, not assumed, against the controller in force
#: on 2026-08-06 with `bridge/tools/probe_server_paths.py`. §11.6 rules that **no
#: client's connect may fail over this group** and that a bridge which cannot
#: resolve the leaf *"logs the absence and publishes nothing rather than
#: synthesising either polarity"*. `optional_nodes` is that rule and only that
#: rule: it changes node **resolution**, never a value, and an absent node
#: produces no message at all — which SD5 makes the correct outcome rather than a
#: fallback.
SAFETY_GROUP = SignalGroup(
    name="safety",
    reference="opcua-nodes.md §11 (SD1–SD10 in §11.2b)",
    inputs=(),
    outputs=(
        # Read every cycle in the output phase and republished unchanged: no
        # inversion, no latch, no edge, no debounce, no window. The latch is the
        # consumer's (SD2) and the demand is the F-program's (invariant 10); a
        # bridge that held, stretched or re-timed this Bool would be a second
        # owner of a safety reaction's timing.
        ("TorqueOffDemand", "torque_off_demand", BOOL),
    ),
    diagnostics=(),
    scalar_inputs=(),
    structured_topics=(),
    # SD5: empty, deliberately. See the block comment above.
    stale_asserts=(),
    optional_nodes=("TorqueOffDemand",),
)

#: Every group this bridge knows how to carry. A config may declare any
#: non-empty subset; the union of the declared ones is the configured signal set.
GROUPS: dict[str, SignalGroup] = {
    CELL_GROUP.name: CELL_GROUP,
    FORKLIFT_GROUP.name: FORKLIFT_GROUP,
    ENVELOPE_GROUP.name: ENVELOPE_GROUP,
    WARNING_GROUP.name: WARNING_GROUP,
    SAFETY_GROUP.name: SAFETY_GROUP,
}

#: BrowseName elements the bridge must never address, in either direction, in
#: any configuration (§4.10). `Hmi` is the folder; `HmiHeartbeat` is the other
#: client's counter. `HmiLinkOk` is deliberately NOT here: it is a PLC verdict
#: the bridge may read for logging (§4.9, opcua-nodes.md §10.3).
FORBIDDEN_PATH_ELEMENT = "Hmi"
FORBIDDEN_LEAF = "HmiHeartbeat"


class ConfigError(Exception):
    """The configuration file is wrong. Never coerced around."""


@dataclass
class Config:
    path: str
    groups: tuple[str, ...] = ()
    opcua: dict[str, Any] = field(default_factory=dict)
    nodes: dict[str, Any] = field(default_factory=dict)
    ros: dict[str, Any] = field(default_factory=dict)
    cycle: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    logging: dict[str, Any] = field(default_factory=dict)

    # --- the configured signal set (§2.1) ----------------------------------

    @property
    def signal_groups(self) -> tuple[SignalGroup, ...]:
        """The groups this run carries, in the order the config declares them."""
        return tuple(GROUPS[name] for name in self.groups)

    @property
    def input_kinds(self) -> dict[str, str]:
        return {
            key: kind
            for group in self.signal_groups
            for key, kind, _cadence in group.inputs
        }

    @property
    def input_cadences(self) -> dict[str, str]:
        return {
            key: cadence
            for group in self.signal_groups
            for key, _kind, cadence in group.inputs
        }

    @property
    def output_kinds(self) -> dict[str, str]:
        return {
            key: kind
            for group in self.signal_groups
            for key, _topic, kind in group.outputs
        }

    @property
    def input_keys(self) -> tuple[str, ...]:
        """Every input slot of the configured set, group order then node order.

        This is the "every" of R3, of the reconnect refresh and of the restart
        rewrite (§2.1 G2). It is 7 for a cell-only run, 4 for a forklift-only
        run and 11 with both groups — and no rule anywhere writes those numbers
        down.
        """
        return tuple(key for group in self.signal_groups for key in group.input_keys)

    @property
    def cyclic_input_keys(self) -> tuple[str, ...]:
        """Inputs written cyclically from the slot's latest value (§5).

        Every Real of every configured group, and the vehicle's heartbeat
        counter. The cadence comes from the node model per signal, never from
        the value's type: `ForkliftVehicleHeartbeat` and
        `ForkliftVehicleModeApplied` are both `UInt16` and are written
        differently (`opcua-nodes.md` §12.6).
        """
        return tuple(
            key for key, cadence in self.input_cadences.items() if cadence == CYCLIC
        )

    @property
    def on_change_input_keys(self) -> tuple[str, ...]:
        """Inputs written on change, plus a full refresh on every (re)connect
        and after a detected server restart (§5, §8.1)."""
        return tuple(
            key for key, cadence in self.input_cadences.items() if cadence == ON_CHANGE
        )

    @property
    def output_keys(self) -> tuple[str, ...]:
        return tuple(key for group in self.signal_groups for key in group.output_keys)

    @property
    def output_topic_keys(self) -> dict[str, str]:
        """Output node key -> the ROS topic key it is republished on."""
        return {
            key: topic
            for group in self.signal_groups
            for key, topic, _kind in group.outputs
        }

    @property
    def diagnostic_keys(self) -> tuple[str, ...]:
        return tuple(key for group in self.signal_groups for key in group.diagnostics)

    @property
    def stale_asserts(self) -> dict[str, StaleAssert]:
        """Node key -> the slot's silence rule, for the configured groups only.

        Empty for every configuration that does not carry the warning group, so
        no other slot acquires a window by being in the same run (§10.8 P4).
        """
        return {
            rule.node_key: rule
            for group in self.signal_groups
            for rule in group.stale_asserts
        }

    @property
    def optional_node_keys(self) -> frozenset[str]:
        """Node keys whose ABSENCE from the server is not a connect failure, for
        the configured groups only (`opcua-nodes.md` §11.6).

        Empty in every configuration that does not carry a group declaring one,
        so no node becomes optional by sharing a run with one that is.
        """
        return frozenset(
            key for group in self.signal_groups for key in group.optional_nodes
        )

    @property
    def write_allowlist(self) -> frozenset[str]:
        """The complete set of node keys this run may write — **derived** from
        the configured groups, never hand-maintained beside them (§4.10).

        The `Input/` nodes of each configured group plus the one heartbeat key:
        8 keys with the cell group alone, 5 with the forklift group alone, 12
        with both. Nothing under any `Hmi/`, `Output/`, `Status/` or other
        `Link/` name is in it, in any configuration. Enforced at the single
        write helper, `opcua_side.PlcClient._write`.
        """
        return frozenset(self.input_keys + (HEARTBEAT_KEY,))

    @property
    def touched_node_count(self) -> int:
        """Nodes this run touches at all: the configured inputs, outputs and
        diagnostics, plus the single shared heartbeat (§2.1's table — 15 for the
        cell group, 13 for the forklift group, 27 for both)."""
        return len(self.input_keys) + len(self.output_keys) + len(self.diagnostic_keys) + 1

    def group_of(self, key: str) -> str:
        for group in self.signal_groups:
            if key in group.input_keys or key in group.output_keys or key in group.diagnostics:
                return group.name
        return "-" if key != HEARTBEAT_KEY else "shared"

    def describe(self) -> str:
        """One line naming the configured set, for the startup log (§2.1 G3)."""
        per_group = ", ".join(
            f"{group.name} {len(group.input_keys)}in/{len(group.output_keys)}out/"
            f"{len(group.diagnostics)}diag ({group.reference})"
            for group in self.signal_groups
        )
        silence = "; ".join(
            f"{rule.node_key} asserts {rule.asserted_value} after "
            f"{rule.window_s:.3f}s of silence ({rule.reference})"
            for rule in self.stale_asserts.values()
        )
        optional = ", ".join(sorted(self.optional_node_keys))
        return (
            f"configured signal set: {'+'.join(self.groups)} — {per_group}; "
            f"{len(self.input_keys)} input slots, {len(self.output_keys)} output slots, "
            f"{len(self.diagnostic_keys)} diagnostics, {self.touched_node_count} nodes "
            f"touched, write allowlist {len(self.write_allowlist)} keys"
            + (f"; silence rule: {silence}" if silence else "")
            + (f"; may be absent without failing the connect: {optional} "
               "(opcua-nodes.md §11.6)" if optional else "")
        )

    # --- addressing helpers (translation, never logic) ---------------------

    @property
    def namespace_uris(self) -> dict[str, str]:
        """The two namespace URIs of §3.1, keyed by NAMESPACE_KEYS. URIs only —
        an index never appears in configuration (§3.1 N2, N5)."""
        return self.opcua["namespace_uris"]

    @property
    def interface_path(self) -> list[tuple[str, str]]:
        """`Objects` → … → the server interface node, as
        `(namespace key, BrowseName)` pairs.

        Each element carries the namespace **that element** belongs to (§3.1
        N3): on the commissioned server `ServerInterfaces` is Siemens-owned and
        `DemoCell` is not, so one index cannot qualify both.
        """
        return [(el["namespace"], el["browse_name"]) for el in self.nodes["interface_path"]]

    @property
    def interface_namespace(self) -> str:
        """Namespace key of the interface node. `Input/`, `Output/`, `Status/`,
        `Link/`, `Forklift/` and their variables live in it too (§3.1 N7)."""
        return self.interface_path[-1][0]

    def node_table(self, group: str, table: str) -> dict[str, list[str]]:
        return (self.nodes["groups"][group].get(table) or {})

    def iter_configured_nodes(self) -> Iterator[tuple[str, str, str, list[str]]]:
        """(group name, table, node key, BrowseName elements) for every node this
        run addresses, the shared heartbeat included."""
        for name in self.groups:
            for table in NODE_TABLES:
                for key, elements in self.node_table(name, table).items():
                    yield name, table, key, list(elements)
        for key, elements in (self.nodes.get("heartbeat") or {}).items():
            yield "shared", "heartbeat", key, list(elements)

    def browse_path(self, key: str) -> list[tuple[str, str]]:
        """Full `(namespace key, BrowseName)` path for a node key, from the
        `Objects` folder: the interface path of §3.1, then the node's own
        elements relative to the interface node (§3.1 N1). The forklift group's
        elements simply start with `Forklift` (§3.1 N7)."""
        ns = self.interface_namespace
        for _group, _table, candidate, elements in self.iter_configured_nodes():
            if candidate == key:
                return [*self.interface_path, *((ns, name) for name in elements)]
        raise ConfigError(f"no BrowseName path configured for node {key!r}")

    def topics(self, group: str) -> dict[str, str]:
        return self.ros["topics"][group]

    @property
    def requested_session_timeout_ms(self) -> int:
        """What the bridge **asks** for. §3.2 S1: a request and nothing more —
        the value in force is the one the server grants, read back at connect."""
        return int(self.opcua["requested_session_timeout_ms"])

    @property
    def evidence_csv_path(self) -> str:
        """Absolute path of the raw evidence file.

        Housekeeping, not logic: nothing about a transported value depends on
        where the CSV lands. The committed default names no machine. `~` and
        `$VARS` are expanded; a path that is still relative afterwards is
        resolved against the bridge directory (the parent of `config/`), which
        is the same anchor `main._parse_args` already uses to find the default
        config file. An absolute path is used as written, so a PLCSIM run can
        still point at any location the operator wants.
        """
        raw = os.path.expandvars(os.path.expanduser(str(self.evidence["csv_path"])))
        if os.path.isabs(raw):
            return raw
        bridge_dir = os.path.dirname(os.path.dirname(self.path))
        return os.path.abspath(os.path.join(bridge_dir, raw))


def load(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping")

    expected_top = set(_SCHEMA) | {GROUPS_KEY}
    unknown_sections = set(raw) - expected_top
    if unknown_sections:
        raise ConfigError(f"{path}: unknown section(s) {sorted(unknown_sections)}")
    missing_sections = expected_top - set(raw)
    if missing_sections:
        raise ConfigError(f"{path}: missing section(s) {sorted(missing_sections)}")

    for section, allowed in _SCHEMA.items():
        got = set(raw[section] or {})
        unknown = got - allowed
        if unknown:
            raise ConfigError(
                f"{path}: unknown key(s) in [{section}]: {sorted(unknown)}. "
                "The bridge carries no thresholds, tolerances or timers; a key "
                "for one of those is rejected here by design (bridge-design.md §2)."
            )

    cfg = Config(
        path=os.path.abspath(path),
        groups=_check_groups(path, raw[GROUPS_KEY]),
        opcua=raw["opcua"],
        nodes=raw["nodes"],
        ros=raw["ros"],
        cycle=raw["cycle"],
        evidence=raw["evidence"],
        logging=raw["logging"],
    )

    _check_group_tables(path, cfg)
    if HEARTBEAT_KEY not in (cfg.nodes.get("heartbeat") or {}):
        raise ConfigError(
            f"{path}: [nodes.heartbeat] must contain {HEARTBEAT_KEY} — one heartbeat "
            "serves every configured group (bridge-design.md §2.1 G5)"
        )
    if len(cfg.nodes.get("heartbeat") or {}) != 1:
        raise ConfigError(
            f"{path}: [nodes.heartbeat] carries {len(cfg.nodes['heartbeat'])} nodes. "
            "There is exactly one, shared by every group; a second heartbeat is "
            "deliberately absent from the model (opcua-nodes.md §10.11)."
        )
    _check_topics(path, cfg)
    _check_namespaces(path, cfg)
    _check_interface_path(path, cfg)
    _check_browse_names(path, cfg)
    _check_hmi_group_untouched(path, cfg)
    return cfg


def _check_groups(path: str, declared: Any) -> tuple[str, ...]:
    """§2.1 — the config declares which groups the run carries. The set is fixed
    here, at startup, and nothing switches a group on or off later (G3)."""
    if not isinstance(declared, list) or not declared:
        raise ConfigError(
            f"{path}: [groups] must be a non-empty list naming the signal groups this "
            f"run carries, from {sorted(GROUPS)} (bridge-design.md §2.1)"
        )
    unknown = [name for name in declared if name not in GROUPS]
    if unknown:
        raise ConfigError(f"{path}: [groups] names unknown group(s) {unknown}; known: {sorted(GROUPS)}")
    if len(set(declared)) != len(declared):
        raise ConfigError(f"{path}: [groups] names a group twice: {declared}")
    return tuple(declared)


def _check_group_tables(path: str, cfg: Config) -> None:
    """G1 — a group absent from [groups] contributes nothing, so it carries no
    node table either; and a configured group names exactly the nodes its
    section documents, never a subset and never an extra."""
    tables = cfg.nodes.get("groups")
    if not isinstance(tables, dict):
        raise ConfigError(f"{path}: [nodes.groups] must be a mapping of group name -> node tables")
    if set(tables) != set(cfg.groups):
        raise ConfigError(
            f"{path}: [nodes.groups] carries {sorted(tables)} but [groups] declares "
            f"{list(cfg.groups)}. A group that is not configured contributes nothing and "
            "has no node table; a configured group must have one (bridge-design.md §2.1 G1)."
        )
    for group in cfg.signal_groups:
        section = tables[group.name]
        if not isinstance(section, dict) or set(section) - set(NODE_TABLES):
            raise ConfigError(
                f"{path}: [nodes.groups.{group.name}] must contain only {list(NODE_TABLES)}"
            )
        expected = {
            "inputs": set(group.input_keys),
            "outputs": set(group.output_keys),
            "diagnostics": set(group.diagnostics),
        }
        for table, want in expected.items():
            got = set(section.get(table) or {})
            if got != want:
                raise ConfigError(
                    f"{path}: [nodes.groups.{group.name}.{table}] must name exactly the "
                    f"{len(want)} nodes of {group.reference}. Missing {sorted(want - got)}, "
                    f"unexpected {sorted(got - want)}."
                )


def _check_topics(path: str, cfg: Config) -> None:
    topics = cfg.ros.get("topics")
    if not isinstance(topics, dict):
        raise ConfigError(f"{path}: [ros.topics] must be a mapping of group name -> topic names")
    if set(topics) != set(cfg.groups):
        raise ConfigError(
            f"{path}: [ros.topics] carries {sorted(topics)} but [groups] declares "
            f"{list(cfg.groups)} (bridge-design.md §2.1 G1)"
        )
    for group in cfg.signal_groups:
        got = set(topics[group.name] or {})
        want = set(group.topic_keys)
        if got != want:
            raise ConfigError(
                f"{path}: [ros.topics.{group.name}] must name exactly {sorted(want)}. "
                f"Missing {sorted(want - got)}, unexpected {sorted(got - want)}."
            )
    if any(group.needs_joint_name for group in cfg.signal_groups):
        if not str(cfg.ros.get("joint_name") or "").strip():
            raise ConfigError(
                f"{path}: [ros.joint_name] is required by the cell group: the belt "
                "encoder's joint is selected by name in every JointState message (§4.5)"
            )
    elif cfg.ros.get("joint_name"):
        raise ConfigError(
            f"{path}: [ros.joint_name] is configured but no group needs it. A group "
            "that is not configured contributes nothing, addressing included (§2.1 G1)."
        )


def _check_namespaces(path: str, cfg: Config) -> None:
    """Both URIs of §3.1 N2 must be present, and only those two."""
    uris = cfg.opcua.get("namespace_uris")
    if not isinstance(uris, dict):
        raise ConfigError(f"{path}: [opcua.namespace_uris] must be a mapping of two URIs")
    if set(uris) != set(NAMESPACE_KEYS):
        raise ConfigError(
            f"{path}: [opcua.namespace_uris] must have exactly the keys "
            f"{list(NAMESPACE_KEYS)} — the browse path crosses two namespaces "
            "(bridge-design.md §3.1 N2), got " + str(sorted(uris))
        )
    for key, uri in uris.items():
        if not isinstance(uri, str) or not uri.strip():
            raise ConfigError(f"{path}: [opcua.namespace_uris.{key}] must be a non-empty URI string")
        if uri.strip().isdigit():
            raise ConfigError(
                f"{path}: [opcua.namespace_uris.{key}] is {uri!r}, a namespace *index*. "
                "Indices are resolved by URI at every session establishment and are "
                "never configured (bridge-design.md §3.1 N2/N4)."
            )


def _check_interface_path(path: str, cfg: Config) -> None:
    """§3.1 N1/N3: the interface node is reached through the `ServerInterfaces`
    folder, and every element names the namespace it belongs to."""
    elements = cfg.nodes.get("interface_path")
    if not isinstance(elements, list) or not elements:
        raise ConfigError(
            f"{path}: [nodes.interface_path] must be a non-empty list of "
            "{namespace, browse_name} elements: DemoCell does not hang directly "
            "under Objects (bridge-design.md §3.1 N1)"
        )
    for position, element in enumerate(elements):
        if not isinstance(element, dict) or set(element) != {"namespace", "browse_name"}:
            raise ConfigError(
                f"{path}: [nodes.interface_path][{position}] must have exactly the "
                "keys {namespace, browse_name}"
            )
        if element["namespace"] not in NAMESPACE_KEYS:
            raise ConfigError(
                f"{path}: [nodes.interface_path][{position}].namespace is "
                f"{element['namespace']!r}, not one of {list(NAMESPACE_KEYS)}"
            )
    if elements[-1]["namespace"] != NS_INTERFACE:
        raise ConfigError(
            f"{path}: the last element of [nodes.interface_path] is the server "
            f"interface node and must sit in the {NS_INTERFACE!r} namespace "
            "(bridge-design.md §3.1 N2)"
        )


def _check_browse_names(path: str, cfg: Config) -> None:
    """A BrowseName carries no namespace index. A configured `4:DemoCell` would
    hardcode an index that §3.1 N2 forbids, so it is rejected here."""
    named: list[tuple[str, str]] = [
        (f"nodes.interface_path[{position}]", element["browse_name"])
        for position, element in enumerate(cfg.nodes["interface_path"])
    ]
    for group, table, key, elements in cfg.iter_configured_nodes():
        where = f"nodes.heartbeat.{key}" if table == "heartbeat" else f"nodes.groups.{group}.{table}.{key}"
        if not elements:
            raise ConfigError(f"{path}: [{where}] must be a non-empty list")
        named += [(where, name) for name in elements]
    for where, name in named:
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{path}: [{where}] contains an empty BrowseName")
        if ":" in name:
            raise ConfigError(
                f"{path}: [{where}] is {name!r}. A BrowseName is configured without a "
                "namespace index; the index is resolved by URI at every session "
                "establishment (bridge-design.md §3.1 N2)."
            )


def _check_hmi_group_untouched(path: str, cfg: Config) -> None:
    """§4.10 — the bridge never reads and never writes `Forklift/Hmi/*` or
    `Forklift/Link/HmiHeartbeat`, in any configuration, in either direction.

    Caught here, at startup, rather than at the first write attempt (§4.10,
    consequence 4). The server would accept such a write — the group is marked
    writable and the commissioned CPU runs with access control disabled — so the
    refusal has to come from this side, and it is checkable from the BrowseName
    alone because the two clients' writable sets are disjoint by prefix.

    `Link/HmiLinkOk` is deliberately NOT caught: it is a PLC verdict the bridge
    may read for logging (§4.9), and its writer is the PLC.
    """
    for group, table, key, elements in cfg.iter_configured_nodes():
        where = f"nodes.heartbeat.{key}" if table == "heartbeat" else f"nodes.groups.{group}.{table}.{key}"
        if FORBIDDEN_PATH_ELEMENT in elements[:-1]:
            raise ConfigError(
                f"{path}: [{where}] addresses {'/'.join(elements)}, which is inside the "
                "HMI's request group. The bridge never reads and never writes "
                "Forklift/Hmi/* in any configuration (bridge-design.md §4.10): operator "
                "intent is the HMI's to write and the PLC's to interpret."
            )
        if elements[-1] == FORBIDDEN_LEAF:
            raise ConfigError(
                f"{path}: [{where}] addresses {'/'.join(elements)}, the HMI's own "
                "liveness counter. Its only contract reader is the PLC; a bridge that "
                "logged it would be a second observer of the operator's liveness "
                "(bridge-design.md §4.10)."
            )
        if table in WRITABLE_TABLES and elements[-1].startswith(FORBIDDEN_PATH_ELEMENT):
            raise ConfigError(
                f"{path}: [{where}] puts {elements[-1]} in a writable position. Every "
                "Hmi-prefixed tag belongs to the other client's writable set "
                "(opcua-nodes.md §10.1, bridge-design.md §4.10)."
            )
