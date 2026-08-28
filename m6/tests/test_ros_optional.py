"""ros_optional.py's contract: overlay optional at import, required at main."""
import pytest

import ros_optional


def test_require_refuses_to_start_without_the_overlay():
    if ros_optional.available:
        pytest.skip("Jazzy overlay is sourced")
    with pytest.raises(SystemExit) as caught:
        ros_optional.require()
    assert "jazzy" in str(caught.value).lower()


def test_node_is_object_when_the_overlay_is_absent():
    if ros_optional.available:
        pytest.skip("Jazzy overlay is sourced")
    assert ros_optional.Node is object
    assert ros_optional.rclpy is None
