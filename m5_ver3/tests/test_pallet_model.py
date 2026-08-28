"""pallet_model.py's SDF writer - F5 Task 3.

NO GAZEBO. Pockets are empty tunnels on the fork spacing; the deck sits
above the tines. A collision that filled a pocket would fail here rather
than as DetachableJoint refusing attach-in-contact.
"""
import os

import pytest

yaml = pytest.importorskip("yaml")

import pallet_core as pc                              # noqa: E402
import pallet_model as pm                             # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def load_yaml(*parts):
    with open(os.path.join(_M5V3, *parts), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="module")
def cfg():
    return load_yaml("config.yaml")


@pytest.fixture
def sdf(cfg):
    return pm.sdf_from_spec(cfg["pallet"])


def _boxes(sdf, kind):
    """Collision/visual AABBs in the pallet frame, from pose + box size."""
    out = []
    token = "<{} name=".format(kind)
    start = 0
    while True:
        i = sdf.find(token, start)
        if i < 0:
            break
        chunk = sdf[i:i + 400]
        pose = chunk.split("<pose>")[1].split("</pose>")[0].split()
        size = chunk.split("<size>")[1].split("</size>")[0].split()
        cx, cy, cz = float(pose[0]), float(pose[1]), float(pose[2])
        sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
        out.append((cx, cy, cz, sx, sy, sz))
        start = i + len(token)
    return out


def _contains(box, point):
    cx, cy, cz, sx, sy, sz = box
    x, y, z = point
    return (abs(x - cx) <= sx / 2.0 + 1e-9
            and abs(y - cy) <= sy / 2.0 + 1e-9
            and abs(z - cz) <= sz / 2.0 + 1e-9)


def test_the_sdf_is_a_dynamic_model_named_from_config(cfg, sdf):
    name = cfg["pallet"]["name"]
    text, meta = sdf
    assert '<model name="{}">'.format(name) in text
    assert "<static>false</static>" in text
    assert '<link name="{}">'.format(cfg["pallet"]["child_link"]) in text
    assert meta["name"] == name


def test_pockets_are_empty_where_the_tines_sit(cfg, sdf):
    pal = cfg["pallet"]
    text, _meta = sdf
    collisions = _boxes(text, "collision")
    assert collisions, "pallet must have collisions (floor, nav lidar)"
    z_min, z_max = pc.pocket_z(float(pal["height_m"]),
                               float(pal["deck_thickness_m"]))
    z_mid = (z_min + z_max) / 2.0
    for y in pc.pocket_centres_y(float(pal["fork_spacing_m"])):
        for x in (-0.2, 0.0, 0.2):
            point = (x, y, z_mid)
            assert not any(_contains(box, point) for box in collisions), point


def test_the_deck_sits_above_the_tine_top(cfg, sdf):
    pal = cfg["pallet"]
    text, _meta = sdf
    collisions = _boxes(text, "collision")
    tine_top_model = 0.10 - float(pal["height_m"]) / 2.0
    deck_bottom = pc.pocket_z(float(pal["height_m"]),
                              float(pal["deck_thickness_m"]))[1]
    assert deck_bottom > tine_top_model
    # The highest collision's bottom face is the deck; it must clear 0.10 m world.
    tops = [(cz + sz / 2.0) for (_cx, _cy, cz, _sx, _sy, sz) in collisions]
    assert max(tops) == pytest.approx(float(pal["height_m"]) / 2.0, abs=1e-6)


def test_writer_never_opens_the_committed_world_file():
    src = open(pm.__file__, encoding="utf-8").read()
    assert "warehouse_ver3.sdf" not in src


def test_model_path_is_under_this_tree(cfg):
    path = pm.model_path(cfg["pallet"])
    assert path.endswith("pallet_s5.sdf")
    assert "m5_ver3" in path.replace("\\", "/")
    assert "warehouse_ver3" not in path
