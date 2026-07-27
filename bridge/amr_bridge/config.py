"""Configuration loading.

The config file carries addresses, cadences and housekeeping only. This loader
rejects unknown keys so that a threshold, tolerance or timer cannot be smuggled
in through configuration (bridge-design.md §2, §1.1).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

# Keys the loader accepts, per section. Anything else is a configuration error.
_SCHEMA: dict[str, set[str]] = {
    "opcua": {
        "endpoint", "namespace_uris", "security_policy", "certificate_path",
        "private_key_path", "username", "requested_session_timeout_ms",
        "session_name", "reconnect_interval_s", "reconnect_backoff_max_s",
    },
    "nodes": {"interface_path", "inputs", "heartbeat", "output", "diagnostics"},
    "ros": {"node_name", "topics", "joint_name", "analog_reliability"},
    "cycle": {"period_s", "status_poll_period_s"},
    "evidence": {"csv_path", "flush_interval_s"},
    "logging": {"level"},
}

# The two namespaces the browse path crosses (bridge-design.md §3.1 N2). Both
# are resolved to an index by URI at every session establishment; neither index
# is ever configured, hardcoded or derived from the other.
NS_SERVER_INTERFACES = "server_interfaces"   # vendor-fixed Siemens namespace
NS_INTERFACE = "interface"                   # = the TIA server interface name (ADR 0006)
NAMESPACE_KEYS: tuple[str, ...] = (NS_SERVER_INTERFACES, NS_INTERFACE)

# The seven input nodes of opcua-nodes.md §9.3, in the order they are
# documented — panel contacts grouped by failure direction (NO, NO, NC, NC),
# not by panel layout.
INPUT_KEYS: tuple[str, ...] = (
    "ConveyorBeltPosition",
    "ConveyorBeltSpeed",
    "ProductSensorRange",
    "PanelStartPressed",
    "PanelResetPressed",
    "PanelStopCircuitClosed",
    "PanelProcessStopCircuitClosed",
)

# Analog (Real/Float) inputs, written cyclically from the latest sample.
ANALOG_INPUT_KEYS: tuple[str, ...] = (
    "ConveyorBeltPosition",
    "ConveyorBeltSpeed",
    "ProductSensorRange",
)

# Boolean (Bool/Boolean) inputs, written on change plus a full refresh on
# every (re)connect.
BOOL_INPUT_KEYS: tuple[str, ...] = (
    "PanelStartPressed",
    "PanelResetPressed",
    "PanelStopCircuitClosed",
    "PanelProcessStopCircuitClosed",
)

HEARTBEAT_KEY = "BridgeHeartbeat"
OUTPUT_KEY = "ConveyorSpeedCommand"

#: The complete set of node keys this process may ever write.
#: opcua-nodes.md §9.1: "Only the DemoCell/Input/ nodes and
#: DemoCell/Link/BridgeHeartbeat. Nothing else on the server is
#: client-writable." Enforced in opcua_side.PlcClient._write.
WRITE_ALLOWLIST: frozenset[str] = frozenset(INPUT_KEYS + (HEARTBEAT_KEY,))


class ConfigError(Exception):
    """The configuration file is wrong. Never coerced around."""


@dataclass
class Config:
    path: str
    opcua: dict[str, Any] = field(default_factory=dict)
    nodes: dict[str, Any] = field(default_factory=dict)
    ros: dict[str, Any] = field(default_factory=dict)
    cycle: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    logging: dict[str, Any] = field(default_factory=dict)

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
        `Link/` and their variables live in it too (§3.1)."""
        return self.interface_path[-1][0]

    def browse_path(self, key: str) -> list[tuple[str, str]]:
        """Full `(namespace key, BrowseName)` path for a node key, from the
        `Objects` folder: the interface path of §3.1, then the node's own
        elements relative to the interface node (§3.1 N1)."""
        for section in ("inputs", "heartbeat", "output", "diagnostics"):
            table = self.nodes.get(section) or {}
            if key in table:
                ns = self.interface_namespace
                return [*self.interface_path, *((ns, name) for name in table[key])]
        raise ConfigError(f"no BrowseName path configured for node {key!r}")

    @property
    def requested_session_timeout_ms(self) -> int:
        """What the bridge **asks** for. §3.2 S1: a request and nothing more —
        the value in force is the one the server grants, read back at connect."""
        return int(self.opcua["requested_session_timeout_ms"])

    @property
    def diagnostic_keys(self) -> tuple[str, ...]:
        return tuple((self.nodes.get("diagnostics") or {}).keys())

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

    unknown_sections = set(raw) - set(_SCHEMA)
    if unknown_sections:
        raise ConfigError(f"{path}: unknown section(s) {sorted(unknown_sections)}")
    missing_sections = set(_SCHEMA) - set(raw)
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
        opcua=raw["opcua"],
        nodes=raw["nodes"],
        ros=raw["ros"],
        cycle=raw["cycle"],
        evidence=raw["evidence"],
        logging=raw["logging"],
    )

    configured_inputs = tuple((cfg.nodes.get("inputs") or {}).keys())
    if set(configured_inputs) != set(INPUT_KEYS):
        raise ConfigError(
            f"{path}: [nodes.inputs] must name exactly the seven §9.3 nodes, got "
            f"{sorted(configured_inputs)}"
        )
    if HEARTBEAT_KEY not in (cfg.nodes.get("heartbeat") or {}):
        raise ConfigError(f"{path}: [nodes.heartbeat] must contain {HEARTBEAT_KEY}")
    if OUTPUT_KEY not in (cfg.nodes.get("output") or {}):
        raise ConfigError(f"{path}: [nodes.output] must contain {OUTPUT_KEY}")

    _check_namespaces(path, cfg)
    _check_interface_path(path, cfg)
    _check_browse_names(path, cfg)
    return cfg


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
    for section in ("inputs", "heartbeat", "output", "diagnostics"):
        for key, elements in (cfg.nodes.get(section) or {}).items():
            if not isinstance(elements, list) or not elements:
                raise ConfigError(f"{path}: [nodes.{section}.{key}] must be a non-empty list")
            named += [(f"nodes.{section}.{key}", name) for name in elements]
    for where, name in named:
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{path}: [{where}] contains an empty BrowseName")
        if ":" in name:
            raise ConfigError(
                f"{path}: [{where}] is {name!r}. A BrowseName is configured without a "
                "namespace index; the index is resolved by URI at every session "
                "establishment (bridge-design.md §3.1 N2)."
            )
