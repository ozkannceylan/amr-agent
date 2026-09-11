"""R4 — the F-PLC never receives M8 input.

Static: no M8 topic, node or slot in any PLC link config or in the
vehicle-side PLC republisher. The veto matrix's PLC column stays
orthogonal because nothing in this tree can write it.
"""
import ast
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_REPO = Path(__file__).resolve().parents[2]
_M8 = _REPO / "m8"

_PLC_LINK_PY = (
    _REPO / "m6" / "ipc" / "plc_link.py",
    _REPO / "m6" / "ipc" / "sensor_link.py",
    _REPO / "m6" / "ipc" / "encoder_link.py",
    _REPO / "m6" / "ipc" / "status_contract.py",
)

_M8_MARKERS = (
    "/m8",
    "m8/",
    "m8.",
    "m8_msgs",
    "m8_core",
    "m8_nodes",
    "dock_abort",
    "docktarget",
    "slot_state",
    "slotstate",
    "speed_reduce",
    "speedreduce",
)


def _bridge_yamls():
    files = sorted((_REPO / "bridge" / "config").glob("*.yaml"))
    for extra in (
            _REPO / "m3" / "bridge.cell.virtual.yaml",
            _REPO / "m4" / "bridge.forklift.virtual.yaml"):
        if extra.is_file():
            files.append(extra)
    assert files, "no PLC-link configs found"
    return files


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str):
                yield key
            yield from _walk_strings(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_strings(item)


def _mentions_m8(text):
    low = text.lower().replace(" ", "")
    return any(marker in low for marker in _M8_MARKERS)


def test_plc_link_files_exist():
    for path in _PLC_LINK_PY:
        assert path.is_file(), path
    assert (_REPO / "bridge" / "config" / "bridge.yaml").is_file()


def test_no_m8_token_in_any_plc_bridge_config():
    hits = []
    for path in _bridge_yamls():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for value in _walk_strings(data):
            if _mentions_m8(value):
                hits.append("{}: {}".format(path.relative_to(_REPO), value))
    assert hits == [], (
        "R4: an M8 name in a PLC bridge config would give the F-PLC "
        "an M8 input:\n  " + "\n  ".join(hits))


def test_bridge_opcua_nodes_are_the_documented_forklift_set():
    """The commissioned bridge writes plant scalars. None of them are M8."""
    data = yaml.safe_load(
        (_REPO / "bridge" / "config" / "bridge.yaml").read_text(
            encoding="utf-8"))
    groups = data["nodes"]["groups"]
    names = []
    for group in groups.values():
        for table in group.values():
            if isinstance(table, dict):
                names.extend(table.keys())
    blob = " ".join(names).lower()
    for marker in _M8_MARKERS:
        assert marker not in blob, marker
    # Sanity: the plant slots we expect are still the ones present.
    assert "ForkliftLinearSpeed" in names
    assert "TorqueOffDemand" in names


def test_plc_link_python_does_not_subscribe_or_import_m8():
    hits = []
    for path in _PLC_LINK_PY:
        text = path.read_text(encoding="utf-8")
        if _mentions_m8(text):
            hits.append(str(path.relative_to(_REPO)))
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("m8"):
                    hits.append("{} imports {}".format(path.name, node.module))
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("m8"):
                        hits.append("{} imports {}".format(path.name, alias.name))
    assert hits == [], hits


def test_m8_core_and_nodes_do_not_import_plc_or_opcua():
    banned = {"asyncua", "opcua", "plc_link", "amr_bridge"}
    hits = []
    paths = list((_M8 / "m8_core").glob("*.py"))
    paths += list((_M8 / "m8_nodes").glob("*.py"))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in banned or name == "plc":
                    hits.append("{} imports {}".format(path.name, name))
    assert hits == [], hits


def test_vda_map_does_not_emit_plc_or_cmd_fields():
    from m8_core.contract import (
        Evidence, KIND_SLOT_STATE, SlotRow, make_proposal)
    from m8_core.vda_map import to_vda
    proposal = make_proposal(
        KIND_SLOT_STATE, (SlotRow("A", "empty"),), 0.5,
        Evidence("f", 1.0), 200)
    frag = to_vda(proposal)
    blob = str(frag).lower()
    for banned in ("opcua", "torqueoff", "cmd_vel", "forklift/safety",
                   "motion_enable", "speed_ceiling"):
        assert banned not in blob, banned
