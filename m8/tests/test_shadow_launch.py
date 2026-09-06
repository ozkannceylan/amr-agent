"""m8_shadow.launch.py lists the A1 shells and nothing that consumes."""
from pathlib import Path

from m8_core.topics import A1_NODE_FILES

_LAUNCH = Path(__file__).resolve().parents[1] / "launch" / "m8_shadow.launch.py"


def test_shadow_launch_exists_and_names_the_five_a1_nodes():
    text = _LAUNCH.read_text(encoding="utf-8")
    for name in A1_NODE_FILES:
        assert name in text, name
    assert "generate_launch_description" in text
    # Phase E / B+ stay out of this file.
    assert "speed_arbiter" not in text
    assert "m8_gated" not in text
    assert "gazebo" not in text.lower()
    assert "cmd_vel" not in text


def test_shadow_launch_does_not_start_a_plant():
    text = _LAUNCH.read_text(encoding="utf-8")
    for banned in ("gz sim", "gz-sim", "ros_gz", "image_bridge"):
        assert banned not in text
