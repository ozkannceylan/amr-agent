"""The derivation is mechanical, counted, and refuses the unknown."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "tools")))

import instantiate_vehicle as iv


def test_derives_both_files_with_full_prefix_rewrite(tmp_path):
    out = iv.instantiate("f1", out_root=str(tmp_path))
    model = open(os.path.join(out, "model.sdf"), encoding="utf-8").read()
    config = open(os.path.join(out, "config.yaml"), encoding="utf-8").read()
    assert "/forklift/" not in model and "/forklift/" not in config
    assert model.count("/f1/") == iv.count_prefix(iv.SRC_MODEL)
    assert config.count("/f1/") == iv.count_prefix(iv.SRC_CONFIG)


def test_rewrite_touches_only_the_prefix(tmp_path):
    out = iv.instantiate("f2", out_root=str(tmp_path))
    src = open(iv.SRC_MODEL, encoding="utf-8").read()
    derived = open(os.path.join(out, "model.sdf"), encoding="utf-8").read()
    assert derived == src.replace("/forklift/", "/f2/")


def test_idempotent(tmp_path):
    first = iv.instantiate("f1", out_root=str(tmp_path))
    body1 = open(os.path.join(first, "model.sdf"), encoding="utf-8").read()
    second = iv.instantiate("f1", out_root=str(tmp_path))
    body2 = open(os.path.join(second, "model.sdf"), encoding="utf-8").read()
    assert first == second and body1 == body2


def test_unknown_vehicle_refused(tmp_path):
    with pytest.raises(SystemExit):
        iv.instantiate("f9", out_root=str(tmp_path))
