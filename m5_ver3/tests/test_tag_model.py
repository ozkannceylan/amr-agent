"""tag_model.py's SDF writer - F5 Task 1.

NO LIBAPRILTAG AND NO GAZEBO. The shipped S5 marker is generated from
the detector's own library; these tests drive sdf_from_bitmap with the
same 4-bit family tag_core's selftest uses, so a reversed cell placement
fails here rather than as a tag the camera cannot see.
"""
import os

import pytest

yaml = pytest.importorskip("yaml")

import tag_core as tc                                 # noqa: E402
import tag_model as tm                                # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def toy_family():
    return tm.Family(
        "toy", 4, [1, 2, 1, 2], [1, 1, 2, 2], 4, 6, [0b1010])


def toy_sdf():
    fam = toy_family()
    rows = fam.bitmap(0)
    return tm.sdf_from_bitmap("toy_0", rows, 0.40, 4, 0.02)


def test_describe_needs_nothing_but_config(capsys):
    import _common
    cfg = _common.load_config(tm.TOOL, tm.REQUIRED_KEYS)
    assert tm.describe(cfg) == 0
    assert "tag36h11" in capsys.readouterr().out


def test_the_sdf_is_a_static_model_named_for_the_family():
    sdf, meta = toy_sdf()
    assert '<model name="toy_0">' in sdf
    assert "<static>true</static>" in sdf
    assert meta["name"] == "toy_0"


def test_the_tile_size_is_the_printed_square_not_the_black_border():
    sdf, meta = toy_sdf()
    assert meta["tile_m"] == pytest.approx(0.60)
    assert meta["cell_m"] == pytest.approx(0.10)


def test_every_black_cell_becomes_one_visual_and_the_board_is_one_collision():
    sdf, meta = toy_sdf()
    assert sdf.count("<collision name=") == 1
    assert sdf.count('<visual name="ink_') == meta["black_cells"]
    assert meta["black_cells"] > 0


def test_black_ink_sits_on_the_plus_X_face():
    sdf, _meta = toy_sdf()
    assert "<visual name=\"ink_0\">" in sdf
    start = sdf.index("<visual name=\"ink_0\">")
    pose = sdf[start:start + 200]
    assert "0.011" in pose or "0.010" in pose


def test_spawn_pose_faces_the_truck_at_the_marker():
    pose = tm.spawn_pose((7.0, 2.60), -3.141592653589793 / 2.0, 0.80)
    assert pose["x"] == pytest.approx(7.0)
    assert pose["y"] == pytest.approx(2.60)
    assert pose["z"] == pytest.approx(0.80)
    assert pose["yaw"] == pytest.approx(3.141592653589793 / 2.0)


def test_model_name_is_family_underscore_id():
    assert tm.model_name("tag36h11", 0) == "tag36h11_0"


def test_config_dock_keys_the_writer_reads_all_exist():
    tree = yaml.safe_load(open(os.path.join(_M5V3, "config.yaml"),
                               encoding="utf-8"))
    import _common
    cfg = _common.Config(tm.TOOL, tree)
    for key in tm.REQUIRED_KEYS:
        cfg.raw(key)


def test_an_out_of_range_id_is_a_valueerror():
    with pytest.raises(ValueError):
        toy_family().bitmap(1)
