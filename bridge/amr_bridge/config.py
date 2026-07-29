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
    #: (node key, kind) for every input the bridge WRITES, in the node model's
    #: documented order. The cell's order is §9.3's (panel contacts grouped by
    #: failure direction); the forklift's is §10.5's.
    inputs: tuple[tuple[str, str], ...]
    #: (node key, ROS topic key) for every output the bridge READS and applies.
    outputs: tuple[tuple[str, str], ...]
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

    @property
    def input_keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.inputs)

    @property
    def output_keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.outputs)

    @property
    def topic_keys(self) -> tuple[str, ...]:
        """Every topic key this group needs in `ros.topics.<group>`."""
        return (
            self.structured_topics
            + tuple(topic for _, topic, _ in self.scalar_inputs)
            + tuple(topic for _, topic in self.outputs)
        )


#: Demonstration cell — `opcua-nodes.md` §9, ADR 0004, gate M3.
CELL_GROUP = SignalGroup(
    name="cell",
    reference="opcua-nodes.md §9",
    inputs=(
        ("ConveyorBeltPosition", REAL),
        ("ConveyorBeltSpeed", REAL),
        ("ProductSensorRange", REAL),
        ("PanelStartPressed", BOOL),
        ("PanelResetPressed", BOOL),
        ("PanelStopCircuitClosed", BOOL),
        ("PanelProcessStopCircuitClosed", BOOL),
    ),
    outputs=(("ConveyorSpeedCommand", "cmd_speed"),),
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
        ("ForkliftForkHeight", REAL),
        ("ForkliftLinearSpeed", REAL),
        # TRUE is the non-permissive state and it is carried UNINVERTED (§4.7
        # row 12, opcua-nodes.md §10.5). The polarity belongs to the vehicle
        # layer at one end and to the PLC at the other; inverting it in
        # transport would put it in two places.
        ("ForkliftObstacleInStopZone", BOOL),
        ("ForkliftObstacleMinDistance", REAL),
    ),
    outputs=(
        ("ForkliftTractionSpeedRef", "cmd_traction_speed"),
        ("ForkliftSteerAngleRef", "cmd_steer_angle"),
        ("ForkliftForkSpeedRef", "cmd_fork_speed"),
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

#: Every group this bridge knows how to carry. A config may declare any
#: non-empty subset; the union of the declared ones is the configured signal set.
GROUPS: dict[str, SignalGroup] = {
    CELL_GROUP.name: CELL_GROUP,
    FORKLIFT_GROUP.name: FORKLIFT_GROUP,
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
        return {key: kind for group in self.signal_groups for key, kind in group.inputs}

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
    def analog_input_keys(self) -> tuple[str, ...]:
        """Real inputs: written cyclically from the latest sample (§5)."""
        return tuple(key for key, kind in self.input_kinds.items() if kind == REAL)

    @property
    def bool_input_keys(self) -> tuple[str, ...]:
        """Bool inputs: written on change, plus a full refresh on every
        (re)connect and after a detected server restart (§5, §8.1)."""
        return tuple(key for key, kind in self.input_kinds.items() if kind == BOOL)

    @property
    def output_keys(self) -> tuple[str, ...]:
        return tuple(key for group in self.signal_groups for key in group.output_keys)

    @property
    def output_topic_keys(self) -> dict[str, str]:
        """Output node key -> the ROS topic key it is republished on."""
        return {key: topic for group in self.signal_groups for key, topic in group.outputs}

    @property
    def diagnostic_keys(self) -> tuple[str, ...]:
        return tuple(key for group in self.signal_groups for key in group.diagnostics)

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
        return (
            f"configured signal set: {'+'.join(self.groups)} — {per_group}; "
            f"{len(self.input_keys)} input slots, {len(self.output_keys)} output slots, "
            f"{len(self.diagnostic_keys)} diagnostics, {self.touched_node_count} nodes "
            f"touched, write allowlist {len(self.write_allowlist)} keys"
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
