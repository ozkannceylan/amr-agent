"""costmap_probe.py's arithmetic and its refusals - F5 Task 1.

NO ROS AND NO RUNNING STACK. `record` is the only function that imports
rclpy, and it is not imported here. What is locked is the GRID READER:
how cells are tallied, when two captures are the same geometry, and the
two refusals that would let a difference about a localiser (or about a
resized map) sit in a table about a costmap layer.
"""
import os

import pytest

yaml = pytest.importorskip("yaml")

import costmap_probe as probe                         # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


class _Cfg(object):
    class Refused(Exception):
        pass

    def s(self, dotted):
        return {
            "map.dir": "m5_ver3/maps",
            "map.name": "warehouse_v3",
            "map.registration.file": "registration.yaml",
            "evidence.dir": "m5_ver3/logs/evidence",
        }[dotted]

    def refuse(self, check, owner, *lines):
        self.check = check
        self.owner = owner
        self.lines = list(lines)
        raise self.Refused(check)


HEADER = {
    "width": "4",
    "height": "2",
    "resolution": "0.050000000",
    "origin_x": "0.000000000",
    "origin_y": "0.000000000",
    "frame_id": "map",
}

STATE = ("traction=nominal\narm=wheel+imu\n"
         "loc=amcl@deadbeef\nnav=on@cafebabe\n")


def write_capture(root, name, cells, state=STATE, header=None):
    os.makedirs(root, exist_ok=True)
    meta = dict(HEADER)
    if header:
        meta.update(header)
    meta["cells"] = str(len(cells))
    with open(os.path.join(root, name + ".txt"), "w", encoding="utf-8") as fh:
        for key, value in meta.items():
            fh.write("{}={}\n".format(key, value))
    raw = bytes((int(v) & 0xFF) for v in cells)
    with open(os.path.join(root, name + ".bin"), "wb") as fh:
        fh.write(raw)
    with open(os.path.join(root, "state.txt"), "w", encoding="utf-8") as fh:
        fh.write(state)


# ----------------------------------------------------------------------
# tally
# ----------------------------------------------------------------------

def test_tally_treats_255_as_unknown_and_100_as_lethal():
    counts = probe.tally([0, 100, 255, 50])
    assert counts == {"lethal": 1, "unknown": 1, "free": 1, "other": 1}


def test_tally_accepts_already_signed_unknown():
    counts = probe.tally([-1, 0, 100])
    assert counts["unknown"] == 1
    assert counts["lethal"] == 1
    assert counts["free"] == 1


# ----------------------------------------------------------------------
# geometry
# ----------------------------------------------------------------------

def test_identical_headers_match():
    assert probe.geometry_matches(HEADER, dict(HEADER)) == []


def test_a_resized_grid_is_named_by_the_keys_that_moved():
    other = dict(HEADER)
    other["width"] = "8"
    other["frame_id"] = "odom"
    assert probe.geometry_matches(HEADER, other) == ["width", "frame_id"]


# ----------------------------------------------------------------------
# compare refusals and diffs
# ----------------------------------------------------------------------

def test_compare_refuses_a_geometry_mismatch(tmp_path, capsys):
    a = str(tmp_path / "a")
    b = str(tmp_path / "b")
    write_capture(a, "grid", [0] * 8)
    write_capture(b, "grid", [0] * 16, header={"width": "8"})
    with pytest.raises(_Cfg.Refused) as caught:
        probe.compare(_Cfg(), a, b, "grid")
    assert "same grid" in str(caught.value)


def test_compare_refuses_a_loc_mix(tmp_path):
    a = str(tmp_path / "a")
    b = str(tmp_path / "b")
    write_capture(a, "grid", [0] * 8)
    other = STATE.replace("amcl@deadbeef", "slam@cafef00d")
    write_capture(b, "grid", [0] * 8, state=other)
    with pytest.raises(_Cfg.Refused) as caught:
        probe.compare(_Cfg(), a, b, "grid")
    assert "same artifact" in str(caught.value)


def test_compare_counts_a_new_lethal_and_does_not_invent_a_lowered_cell(
        tmp_path, capsys):
    a = str(tmp_path / "a")
    b = str(tmp_path / "b")
    write_capture(a, "grid", [0, 0, 0, 0, 0, 0, 0, 0])
    write_capture(b, "grid", [0, 100, 0, 0, 0, 0, 0, 0])
    rc = probe.compare(_Cfg(), a, b, "grid")
    assert rc == 0
    out = capsys.readouterr().out
    assert "NEW LETHAL 1" in out
    assert "LETHAL LOST 0" in out


def test_a_lowered_cell_is_reported_because_max_cannot_produce_one(
        tmp_path, capsys):
    a = str(tmp_path / "a")
    b = str(tmp_path / "b")
    write_capture(a, "grid", [100, 0, 0, 0, 0, 0, 0, 0])
    write_capture(b, "grid", [0, 0, 0, 0, 0, 0, 0, 0])
    rc = probe.compare(_Cfg(), a, b, "grid")
    assert rc == 0
    out = capsys.readouterr().out
    assert "LOWERED   1 cells" in out
    assert "A LOWERED CELL IS THE ONE RESULT THIS LAYER CANNOT" in out


def test_unknown_to_free_is_not_counted_as_raised_or_lowered(
        tmp_path, capsys):
    a = str(tmp_path / "a")
    b = str(tmp_path / "b")
    write_capture(a, "grid", [-1, 0, 0, 0, 0, 0, 0, 0])
    write_capture(b, "grid", [0, 0, 0, 0, 0, 0, 0, 0])
    probe.compare(_Cfg(), a, b, "grid")
    out = capsys.readouterr().out
    assert "RAISED    0 cells" in out
    assert "LOWERED   0 cells" in out
    assert "KNOWN/UNKNOWN CHANGED  1 cells" in out


def test_describe_needs_nothing_but_config(capsys):
    import _common
    cfg = _common.load_config(probe.TOOL, probe.REQUIRED_KEYS)
    rc = probe.describe(cfg)
    assert rc == 0
    out = capsys.readouterr().out
    assert "IT COMMANDS NOTHING" in out


def test_every_required_key_is_in_config_yaml():
    tree = yaml.safe_load(open(os.path.join(_M5V3, "config.yaml"),
                               encoding="utf-8"))
    import _common
    cfg = _common.Config(probe.TOOL, tree)
    for key in probe.REQUIRED_KEYS:
        cfg.raw(key)
