"""R3 — frames never leave the truck.

Static: no image topic in any PLC/MQTT bridge config, and m8_core
never emits image bytes. The vehicle-local ros_gz image_bridge
(m5_ver3/m5v3.sh) stays on the truck and is not a bridge config.
"""
import ast
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_REPO = Path(__file__).resolve().parents[2]
_M8 = _REPO / "m8"

# The Gazebo↔PLC translator and its virtual-cell siblings. These are
# the configs that would carry a frame off the vehicle if anyone added
# a camera slot. ros_gz image_bridge is not in this set on purpose.
_BRIDGE_CONFIG_DIRS = (
    _REPO / "bridge" / "config",
)
_BRIDGE_CONFIG_FILES = (
    _REPO / "m3" / "bridge.cell.virtual.yaml",
    _REPO / "m4" / "bridge.forklift.virtual.yaml",
)

_IMAGE_TOPIC_MARKERS = (
    "/image",
    "depth_image",
    "rgb/image",
    "compressedimage",
    "sensor_msgs/image",
    "sensor_msgs/compressedimage",
    "image_transport",
    "/camera/",
    "camera/image",
    "/cam/image",
    "/cam/depth",
    "color/image",
)

_IMAGE_MSG_TYPES = (
    "sensor_msgs/Image",
    "sensor_msgs/CompressedImage",
    "sensor_msgs.msg.Image",
    "sensor_msgs.msg.CompressedImage",
)


def _yaml_files():
    files = []
    for folder in _BRIDGE_CONFIG_DIRS:
        if folder.is_dir():
            files.extend(sorted(folder.glob("*.yaml")))
            files.extend(sorted(folder.glob("*.yml")))
    for path in _BRIDGE_CONFIG_FILES:
        if path.is_file():
            files.append(path)
    assert files, "no bridge configs found — the scan has nothing to hold"
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


def _looks_like_image_topic(text):
    low = text.lower().replace(" ", "")
    return any(marker in low for marker in _IMAGE_TOPIC_MARKERS)


def test_bridge_configs_are_present_and_parse():
    files = _yaml_files()
    names = {p.name for p in files}
    assert "bridge.yaml" in names
    for path in files:
        with path.open(encoding="utf-8") as handle:
            yaml.safe_load(handle)


def test_no_image_topic_in_any_bridge_config():
    hits = []
    for path in _yaml_files():
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        for value in _walk_strings(data):
            if _looks_like_image_topic(value):
                hits.append("{}: {}".format(path.relative_to(_REPO), value))
    assert hits == [], (
        "R3: an image topic in a bridge config would take frames off "
        "the truck:\n  " + "\n  ".join(hits))


def test_bridge_ros_topics_are_scalars_not_images():
    """Every ros.topics value in the PLC bridge is a /forklift/... name
    that is Bool/Float64/UInt16 in the node model — never an Image."""
    for path in (_REPO / "bridge" / "config").glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        topics = (data.get("ros") or {}).get("topics") or {}
        for group, table in topics.items():
            if not isinstance(table, dict):
                continue
            for key, topic in table.items():
                assert isinstance(topic, str) and topic.startswith("/"), (
                    path, group, key, topic)
                assert not _looks_like_image_topic(topic), (path, topic)
                assert "image" not in key.lower()
                assert "camera" not in key.lower()
                assert "rgb" not in key.lower()


def test_m8_core_does_not_import_image_or_ros_types():
    banned = {
        "rclpy", "sensor_msgs", "cv_bridge", "cv2", "PIL", "image_transport",
    }
    hits = []
    for path in sorted((_M8 / "m8_core").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in banned:
                    hits.append("{} imports {}".format(path.name, name))
        text = path.read_text(encoding="utf-8")
        for msg in _IMAGE_MSG_TYPES:
            if msg in text:
                hits.append("{} names {}".format(path.name, msg))
    assert hits == [], hits


def test_m8_publish_topics_are_not_image_topics():
    from m8_core.topics import PUBLISH_TOPICS
    for topic in PUBLISH_TOPICS:
        assert not _looks_like_image_topic(topic), topic


def test_vda_map_fragments_are_numbers_and_enums_only():
    from m8_core.contract import Evidence, KIND_DOCK_ABORT, make_proposal
    from m8_core.vda_map import to_vda
    proposal = make_proposal(
        KIND_DOCK_ABORT, "pallet_absent", 0.5,
        Evidence("f", 1.0), 200)
    frag = to_vda(proposal)
    blob = str(frag)
    for marker in _IMAGE_TOPIC_MARKERS + _IMAGE_MSG_TYPES:
        assert marker.lower() not in blob.lower(), marker
