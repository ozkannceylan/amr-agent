"""pallet_bench.py's gz commands - F5 Task 3.

NO GAZEBO. Attach and lift addresses come from config.yaml. A literal
topic here would drive the wrong joint the same way a typed dock pose
docks 31 m off.
"""
import os

import pytest

yaml = pytest.importorskip("yaml")

import pallet_bench as pb                             # noqa: E402
import pallet_core as pc                              # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def load_yaml(*parts):
    with open(os.path.join(_M5V3, *parts), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="module")
def cfg():
    return load_yaml("config.yaml")


def test_attach_and_detach_are_empty_on_the_configured_topics(cfg):
    attach = pb.empty_pub(cfg["topics"]["pallet_attach"])
    detach = pb.empty_pub(cfg["topics"]["pallet_detach"])
    assert attach[0] == "gz"
    assert cfg["topics"]["pallet_attach"] in attach
    assert cfg["topics"]["pallet_detach"] in detach
    assert "gz.msgs.Empty" in attach
    assert attach != detach


def test_lift_and_lower_are_doubles_on_fork_cmd(cfg):
    lift = pb.double_pub(cfg["topics"]["fork_cmd"],
                         float(cfg["pallet"]["lift_m"]))
    lower = pb.double_pub(cfg["topics"]["fork_cmd"], 0.0)
    assert cfg["topics"]["fork_cmd"] in lift
    assert "gz.msgs.Double" in lift
    assert "data: 0.1" in " ".join(lift)
    assert "data: 0.0" in " ".join(lower)


def test_cycle_names_every_leg_the_plan_asked_for():
    assert pb.CYCLE == (
        "transit", "stage", "dock", "attach", "lift", "undock",
        "carry", "stage", "dock", "lower", "detach", "undock")


def test_bench_never_opens_the_committed_world_file():
    src = open(pb.__file__, encoding="utf-8").read()
    assert "warehouse_ver3" not in src


def test_attach_gate_is_pallet_core(cfg):
    src = open(pb.__file__, encoding="utf-8").read()
    assert "attach_ok" in src
    assert "pallet_core" in src
    assert float(cfg["pallet"]["yaw_max_rad"]) == pytest.approx(
        5.0 * 3.141592653589793 / 180.0, abs=1e-3)


def test_parse_named_pose_reads_gz_pose_v():
    text = (
        'pose {\n'
        '  name: "pallet_s5"\n'
        '  position { x: 7 y: 3.03 z: 0.072 }\n'
        '  orientation { x: 0 y: 0 z: 0.70710678 w: 0.70710678 }\n'
        '}\n'
    )
    pose = pb.parse_named_pose(text, "pallet_s5")
    assert pose["x"] == pytest.approx(7.0)
    assert pose["y"] == pytest.approx(3.03)
    assert pose["z"] == pytest.approx(0.072)
    assert pose["yaw"] == pytest.approx(1.570796, abs=1e-4)
    assert pb.parse_named_pose(text, "nope") is None


def test_seat_request_is_the_docked_pose(cfg):
    req = pb.seat_request(
        __import__("_common").Config("pallet_bench", cfg))
    assert 'name: "forklift_ver3"' in req
    assert "7.000000000" in req or "x: 7.000" in req
    assert "4.575" in req


def test_state_confirms_reads_the_plugins_own_announcement():
    """The gate the 2026-08-30 cycle lacked: `attach ok` must mean the
    JOINT formed, not that the predicate was satisfied before an Empty
    that joined a ghost. gz prints the StringMsg as `data: "attached"`.
    """
    assert pb.state_confirms('data: "attached"', "attached") is True
    assert pb.state_confirms('data: "detached"', "attached") is False
    assert pb.state_confirms("data: attached", "attached") is True
    assert pb.state_confirms("", "attached") is False
    assert pb.state_confirms(None, "attached") is False
    assert pb.state_confirms("garbage with no data line", "attached") is False


def test_attach_gates_on_the_announcement_not_the_predicate_alone():
    src = open(pb.__file__, encoding="utf-8").read()
    assert "state_confirms(state, \"attached\")" in src
    assert "listen_and_publish" in src
    # and the refusal names both topics it used
    assert "the DetachableJoint plugin announced the joint" in src
