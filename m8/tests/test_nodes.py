"""Node wiring without rclpy: ROS stays in main(), publish Proposal only."""
import ast
from pathlib import Path

from m8_core.pocket import make_plane_depth
from m8_core.wire import loads_proposal
from m8_nodes.abort_node import proposal_json_from_depth as abort_json
from m8_nodes.m8_health import placeholder_health, unmeasured_health
from m8_nodes.pocket_pose_node import proposal_json_from_depth as pocket_json
from m8_nodes.slot_state_node import proposal_json_from_depth as slot_json
from m8_nodes.veto_gate_node import evaluate_json
from m8_core.gate import Gate, healthy

_NODES = Path(__file__).resolve().parents[1] / "m8_nodes"


def _clean_buf():
    frame = make_plane_depth(
        48, 36, 1.20,
        pockets=((10, 16, 10, 26, 1.55),
                 (32, 38, 10, 26, 1.55)))
    return frame.depths, frame.width, frame.height, frame.sim_stamp


def test_pocket_and_slot_helpers_emit_json_abort_is_silent_on_clean():
    depths, w, h, stamp = _clean_buf()
    p = pocket_json(depths, w, h, stamp)
    s = slot_json(depths, w, h, stamp)
    a = abort_json(depths, w, h, stamp)
    assert p is not None and s is not None
    assert loads_proposal(p).kind == "DOCK_TARGET_REFINE"
    assert loads_proposal(s).kind == "SLOT_STATE"
    assert a is None


def test_veto_gate_helper_refuses_a_well_formed_proposal():
    depths, w, h, stamp = _clean_buf()
    text = pocket_json(depths, w, h, stamp)
    gate = Gate(phase="A")
    verdict_text, row = evaluate_json(gate, text, 1.05, healthy())
    assert row["accepted"] is False
    assert row["reason"] == "phase_a_shadow"
    assert '"accepted": false' in verdict_text


def test_unmeasured_health_is_not_ok_placeholder_is():
    assert unmeasured_health().ok() is False
    assert placeholder_health().ok() is True


def test_rclpy_is_imported_only_inside_main():
    hits = []
    for path in sorted(_NODES.glob("*.py")):
        if path.name in ("__init__.py", "io.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        mains = [n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "main"]
        assert mains, path.name
        main_nodes = set(id(x) for x in ast.walk(mains[0]))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            if "rclpy" in names or "sensor_msgs" in names:
                if id(node) not in main_nodes and not _inside(node, mains[0]):
                    hits.append("{} imports ROS at module level".format(
                        path.name))
    assert hits == [], hits


def _inside(node, parent):
    for child in ast.walk(parent):
        if child is node:
            return True
    return False


def test_node_sources_publish_only_m8_number_topics():
    for path in list(_NODES.glob("*_node.py")) + [_NODES / "m8_health.py"]:
        text = path.read_text(encoding="utf-8")
        assert "create_publisher" in text, path.name
        assert "Image" not in text.split("create_publisher")[1][:80]
        # The depth Image type may be imported for subscribe, never published.
        if "create_subscription" in text and "Image" in text:
            # Thin wrappers import the on-truck name from topics.py;
            # they must not subscribe the colour stream.
            assert "CAM_DEPTH" in text, path.name
            assert "CAM_IMAGE" not in text, path.name
        for banned in ("/forklift/cmd", "/forklift/safety", "cmd_vel",
                       "opcua", "asyncua"):
            assert banned not in text, (path.name, banned)
        # Every publisher target is one of the four M8 wires
        # (imported as names from topics.py).
        if "create_publisher" in text:
            assert any(name in text for name in
                       ("PROPOSAL", "VERDICT", "HEALTH", "LOG")), path.name
