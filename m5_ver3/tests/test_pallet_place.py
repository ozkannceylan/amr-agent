"""pallet_place.py + DetachableJoint pins - F5 Task 3.

NO GAZEBO AND NO WORLD EDIT. Constraint 21: the pallet is a create
service, like the marker. Constraint 23: the joint plugin's topics
are config.yaml's, and attach is pallet_core.attach_ok, not contact.
"""
import os

import pytest

yaml = pytest.importorskip("yaml")

import furniture as furn                              # noqa: E402
import pallet_core as pc                              # noqa: E402
import pallet_place as pp                             # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
_SDF = os.path.join(_M5V3, "gazebo", "forklift_ver3", "model.sdf")


def load_yaml(*parts):
    with open(os.path.join(_M5V3, *parts), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="module")
def cfg():
    return load_yaml("config.yaml")


def test_the_create_request_names_a_file_not_an_inline_sdf(cfg):
    pose = {"x": 7.0, "y": 3.03, "z": 0.072, "yaw": 1.5708}
    path = pp.model_path(cfg["pallet"])
    req = furn.create_request(path, cfg["pallet"]["name"], pose)
    assert "sdf_filename:" in req
    assert 'name: "pallet_s5"' in req
    assert "allow_renaming: false" in req


def test_place_never_opens_the_committed_world_file():
    src = open(pp.__file__, encoding="utf-8").read()
    assert "warehouse_ver3.sdf" not in src
    assert "create_request" in src


def test_detachable_joint_topics_match_config(cfg):
    sdf = open(_SDF, encoding="utf-8").read()
    pal = cfg["pallet"]
    topics = cfg["topics"]
    assert "gz-sim-detachable-joint-system" in sdf
    assert "<parent_link>{}</parent_link>".format(pal["parent_link"]) in sdf
    assert "<child_model>{}</child_model>".format(pal["name"]) in sdf
    assert "<child_link>{}</child_link>".format(pal["child_link"]) in sdf
    assert "<attach_topic>{}</attach_topic>".format(
        topics["pallet_attach"]) in sdf
    assert "<detach_topic>{}</detach_topic>".format(
        topics["pallet_detach"]) in sdf
    assert "<output_topic>{}</output_topic>".format(
        topics["pallet_joint_state"]) in sdf


def test_mast_velocity_limit_is_the_configured_one(cfg):
    sdf = open(_SDF, encoding="utf-8").read()
    joint = sdf.split('<joint name="mast_joint"')[1].split("</joint>")[0]
    assert "<velocity>{}</velocity>".format(
        cfg["pallet"]["mast_limit_mps"]) in joint
    assert float(cfg["pallet"]["lift_m"]) < 1.6
    assert float(cfg["pallet"]["lift_m"]) / float(
        cfg["pallet"]["mast_limit_mps"]) <= 2.0


def test_attach_is_the_predicate_not_a_contact_sensor():
    assert "def attach_ok" in open(pc.__file__, encoding="utf-8").read()
    place = open(pp.__file__, encoding="utf-8").read()
    assert "ContactSensor" not in place
    assert "bumper" not in place.lower()


def test_config_keys_the_spawner_reads_all_exist(cfg):
    import _common
    loaded = _common.Config("pallet_place", cfg)
    for key in pp.REQUIRED_KEYS:
        loaded.raw(key)


def test_fork_cmd_is_the_model_topic(cfg):
    sdf = open(_SDF, encoding="utf-8").read()
    assert "<topic>{}</topic>".format(cfg["topics"]["fork_cmd"]) in sdf


def test_self_collide_stays_false():
    # Empty pockets mean tines are not in contact at attach. Flipping
    # self_collide would change the unladen plant F1.5 measured.
    sdf = open(_SDF, encoding="utf-8").read()
    assert "<self_collide>false</self_collide>" in sdf


def test_m5v3_spawns_the_pallet_inside_the_dock_guard():
    script = open(os.path.join(_M5V3, "m5v3.sh"), encoding="utf-8").read()
    assert "pallet_place.py" in script
    assert "PALLET_SDF" in script
    guard = script.split('if [ "$DOCK" = true ]; then')
    assert any("pallet_place.py" in block.split("\nfi", 1)[0]
               for block in guard[1:]), (
        "pallet_place.py is not inside an `if [ \"$DOCK\" = true ]` block")
    assert any("pallet_bench.py" in block.split("\nfi", 1)[0]
               and "detach" in block.split("\nfi", 1)[0]
               for block in guard[1:]), (
        "pallet_bench.py detach is not inside a dock guard")


def test_reseat_request_is_the_same_derivation_place_spawns_at(cfg):
    """A reseat and a fresh place must never disagree: both read
    pallet_place._pose. The request also carries the yaw-only
    quaternion, normalised by construction."""
    import math
    import _common
    bench_cfg = _common.Config("pallet_place", cfg)
    pose = pp._pose(bench_cfg)
    req = pp.reseat_request(bench_cfg)
    assert 'name: "pallet_s5"' in req
    assert "x: {:.9f}".format(pose["x"]) in req
    assert "y: {:.9f}".format(pose["y"]) in req
    assert "z: {:.9f}".format(pose["z"]) in req
    z = math.sin(pose["yaw"] / 2.0)
    w = math.cos(pose["yaw"] / 2.0)
    assert z * z + w * w == pytest.approx(1.0, abs=1e-12)


def test_reseat_is_a_set_pose_teleport_never_a_respawn():
    """The ghost-attach fix as a pin: reseat must go through
    /world/<world>/set_pose on the SAME entity, and must not call the
    remove or create services at all."""
    src = open(pp.__file__, encoding="utf-8").read()
    body = src.split("def reseat(cfg):", 1)[1].split("def main(", 1)[0]
    assert "set_pose" in body
    assert "/create" not in body
    assert "/remove" not in body


def test_the_cycle_restores_by_reseat_and_not_by_remove_plus_place():
    """pallet_cycle.py's restore_for_attach: entity churn is the
    ghost-attach window; the steps list must name reseat and must not
    name remove."""
    import pallet_cycle
    src = open(pallet_cycle.__file__, encoding="utf-8").read()
    body = src.split("def restore_for_attach(", 1)[1].split(
        "def burst(", 1)[0]
    assert '("pallet_place.py", "reseat")' in body
    assert '"remove"' not in body
