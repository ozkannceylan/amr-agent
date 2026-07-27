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
        "endpoint", "namespace_uri", "security_policy", "certificate_path",
        "private_key_path", "username", "session_timeout_ms", "session_name",
        "reconnect_interval_s", "reconnect_backoff_max_s",
    },
    "nodes": {"root", "inputs", "heartbeat", "output", "diagnostics"},
    "ros": {"node_name", "topics", "joint_name", "analog_reliability"},
    "cycle": {"period_s", "status_poll_period_s"},
    "evidence": {"csv_path", "flush_interval_s"},
    "logging": {"level"},
}

# The six input nodes of opcua-nodes.md §9.3, in the order they are documented.
INPUT_KEYS: tuple[str, ...] = (
    "ConveyorBeltPosition",
    "ConveyorBeltSpeed",
    "ProductSensorRange",
    "PanelStartPressed",
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

    def browse_path(self, key: str) -> list[str]:
        """BrowseName path for a node key, relative to the Objects folder."""
        root = self.nodes["root"]
        for section in ("inputs", "heartbeat", "output", "diagnostics"):
            table = self.nodes.get(section) or {}
            if key in table:
                return [root, *table[key]]
        raise ConfigError(f"no BrowseName path configured for node {key!r}")

    @property
    def diagnostic_keys(self) -> tuple[str, ...]:
        return tuple((self.nodes.get("diagnostics") or {}).keys())


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
            f"{path}: [nodes.inputs] must name exactly the six §9.3 nodes, got "
            f"{sorted(configured_inputs)}"
        )
    if HEARTBEAT_KEY not in (cfg.nodes.get("heartbeat") or {}):
        raise ConfigError(f"{path}: [nodes.heartbeat] must contain {HEARTBEAT_KEY}")
    if OUTPUT_KEY not in (cfg.nodes.get("output") or {}):
        raise ConfigError(f"{path}: [nodes.output] must contain {OUTPUT_KEY}")
    return cfg
