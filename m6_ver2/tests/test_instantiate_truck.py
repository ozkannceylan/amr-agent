"""The pins on tools/instantiate_truck.py - SPEC_NAMESPACING.md 5.

NO ROS AND NO SIMULATOR IS REACHED FROM HERE. The derivation is a pure
file transform, so its whole safety argument is testable on the owner's
Windows python, and this suite is where the argument is kept honest.

The EXPECTED table below was measured off the donor BY HAND (a grep and
a counter, not the tool) and then frozen. That independence is the
point: if the tool and this table disagree, one of the two is wrong and
neither gets to be the judge of the other. A donor edit that spells a
topic another way changes a count here and the suite says so by name.

sys.path is set up in this module rather than a conftest.py because
m6_ver2/tests/ is shared with the adapter's own suite and a conftest
belongs to whoever writes it first, which is a race, not a design.
"""
import json
import os
import re
import sys

import pytest
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_M6V2, ".."))
for _sub in (os.path.join(_M6V2, "tools"), os.path.join(_REPO, "m6", "ipc")):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

import instantiate_truck as itk                            # noqa: E402
from status_contract import VEHICLES                       # noqa: E402


# ----------------------------------------------------------------------
# THE FROZEN COUNT TABLE. One row per derived artifact, measured off
# m5_ver3/ on 2026-09-02.
#
#   forklift_gz  - /forklift/gz/ occurrences the blanket rewrite moves
#   m5v3         - /m5v3/ occurrences the blanket rewrite moves
#   agv_forklift - agv/forklift/ occurrences it must NOT move: those are
#                  REPO PATHS into the m5-ver2 crib, not this truck's gz
#                  namespace, and a naive /forklift/ rewrite turns
#                  `agv/forklift/nav2.yaml` into `agv/f1/nav2.yaml` -
#                  a false statement about a file that exists. The two
#                  populations partition /forklift/ exactly, and
#                  test_prefix_populations_partition proves it.
#   keyed        - dotted-key value rewrites; keyed_same - assertions
#   lines        - donor line count, which the wrap check is built on
# ----------------------------------------------------------------------
EXPECTED = {
    "config.yaml": {
        "forklift_gz": 20, "m5v3": 9, "agv_forklift_kept": 8,
        "gt_frame_mentions_kept": 2,
        "keyed_rewritten": 33, "keyed_asserted": 9,
        "lines": 5542, "wrapped": False,
    },
    "nav2.yaml": {
        "forklift_gz": 2, "m5v3": 2, "agv_forklift_kept": 3,
        "keyed_rewritten": 6, "keyed_asserted": 4,
        "lines": 2273, "wrapped": True, "wrap_keys": 7,
    },
    "amcl.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 1,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "lines": 524, "wrapped": True, "wrap_keys": 2,
    },
    "ekf.yaml": {
        "forklift_gz": 2, "m5v3": 0, "agv_forklift_kept": 1,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "lines": 368, "wrapped": True, "wrap_keys": 1,
    },
    "smoother.yaml": {
        "forklift_gz": 2, "m5v3": 0, "agv_forklift_kept": 2,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "lines": 257, "wrapped": True, "wrap_keys": 1,
    },
    "collision_monitor.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 0,
        "keyed_rewritten": 2, "keyed_asserted": 0,
        "lines": 343, "wrapped": True, "wrap_keys": 1,
    },
    "docking.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 0,
        "keyed_rewritten": 2, "keyed_asserted": 0,
        "lines": 69, "wrapped": True, "wrap_keys": 2,
    },
    "apriltag.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 0,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "lines": 33, "wrapped": True, "wrap_keys": 1,
    },
    "ekf_rf2o.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 0,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "lines": 130, "wrapped": False,
    },
    "model.sdf": {
        "forklift_gz": 42, "m5v3": 0, "agv_forklift_kept": 6,
        "gz_frame_id": 7, "gt_odom_frame": 2, "gt_base_frame": 2,
        "pallet_s5_kept": 2,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "lines": 2252, "wrapped": False,
    },
    "navigate_to_pose_tricycle_v3.xml": {
        "forklift_gz": 0, "m5v3": 2, "agv_forklift_kept": 1,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "lines": 242, "wrapped": False,
    },
    "navigate_to_pose_tricycle_v3_rpp.xml": {
        "forklift_gz": 0, "m5v3": 1, "agv_forklift_kept": 0,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "lines": 111, "wrapped": False,
    },
}

# The seven frames model.sdf stamps on bridged messages, donor spelling.
DONOR_SDF_FRAMES = [
    "safety_scanner_back_link", "safety_scanner_left_link",
    "safety_scanner_right_link", "nav_lidar_link", "nav_lidar_3d_link",
    "pallet_cam_optical", "imu_link",
]

# m5v3.sh:426-433 - the six config entries that expand to the seven
# top-level keys nav2.yaml has to be addressed to.
NAV_SECTION_KEYS = [
    "nav.planner.node_name", "nav.controller.node_name",
    "nav.behavior.node_name", "nav.bt.node_name",
    "nav.lifecycle.node_name", "nav.costmap_sections",
]

VIDS = sorted(VEHICLES)


# --------------------------- the fixtures ------------------------------

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Every vid derived once, into a throwaway root.

    Module-scoped on purpose: the suite must not depend on anyone having
    run --all first, and it must not write into m6_ver2/vehicles/, which
    belongs to the operator's last real derivation.
    """
    root = str(tmp_path_factory.mktemp("vehicles"))
    return root, {vid: itk.instantiate(vid, out_root=root) for vid in VIDS}


def _donor(source):
    return itk.read_text(os.path.join(itk.REPO, source.src))


def _derived(root, vid, source):
    return itk.read_text(os.path.join(root, vid, source.name))


def _cfg(root, vid):
    """The derived config.yaml, parsed."""
    return yaml.safe_load(_derived(root, vid, itk.source("config.yaml")))


# ----------------------------- the pins --------------------------------

def test_expected_table_covers_every_derived_artifact():
    assert sorted(EXPECTED) == sorted(s.name for s in itk.SOURCES)


def test_prefix_populations_partition_the_donor():
    """/forklift/ is exactly the gz namespace plus the crib paths.

    If a donor ever grows a third spelling this fails here, before the
    blanket rewrite gets a chance to guess at it.
    """
    for source in itk.SOURCES:
        body = _donor(source)
        want = EXPECTED[source.name]
        assert body.count("/forklift/gz/") == want["forklift_gz"], source.name
        assert (body.count("agv/forklift/")
                == want["agv_forklift_kept"]), source.name
        assert body.count("/m5v3/") == want["m5v3"], source.name
        assert (body.count("/forklift/")
                == want["forklift_gz"] + want["agv_forklift_kept"]), (
                    source.name)
        assert len(body.split("\n")) == want["lines"], source.name


def test_counts_match_the_frozen_table(built):
    root, manifests = built
    for vid in VIDS:
        counts = manifests[vid]["sources"]
        assert sorted(counts) == sorted(EXPECTED)
        for name, want in EXPECTED.items():
            got = counts[name]["counts"]
            for key, value in want.items():
                if key in ("lines", "wrapped", "wrap_keys"):
                    continue
                assert got.get(key) == value, (vid, name, key, got)


def test_wrap_is_one_line_and_two_spaces(built):
    root, manifests = built
    for vid in VIDS:
        for name, want in EXPECTED.items():
            entry = manifests[vid]["sources"][name]
            assert entry["wrapped"] is want["wrapped"], name
            if not want["wrapped"]:
                continue
            assert entry["counts"]["wrap_lines_in"] == want["lines"], name
            assert entry["counts"]["wrap_lines_out"] == want["lines"] + 1, name
            body = _derived(root, vid, itk.source(name))
            head, rest = body.split("\n", 1)
            assert head.rstrip("\r") == vid + ":"
            for line in rest.split("\n"):
                if line.strip():
                    assert line.startswith("  "), (name, line[:40])


def test_residue_inverts_to_the_donor_byte_for_byte(built):
    """The one pin that proves nothing ELSE moved.

    The blanket rewrite collapses two donor prefixes onto one derived
    prefix, so the inverse cannot be a string replace - it needs the
    ORDER of the origins back. That order is the only thing taken from
    the donor here; the bytes are not, and any undeclared edit survives
    the inversion and fails the comparison.
    """
    root, _ = built
    for vid in VIDS:
        for source in itk.SOURCES:
            donor = _donor(source)
            back = itk.invert_text(source, _derived(root, vid, source), vid,
                                   itk.blanket_origins(donor))
            assert back == donor, (vid, source.name)


def test_regeneration_is_idempotent(tmp_path):
    first = str(tmp_path / "a")
    second = str(tmp_path / "b")
    for vid in VIDS:
        one = itk.instantiate(vid, out_root=first)
        itk.instantiate(vid, out_root=first)          # over its own output
        two = itk.instantiate(vid, out_root=second)
        assert one == two
        for source in itk.SOURCES:
            a = itk.read_text(os.path.join(first, vid, source.name))
            b = itk.read_text(os.path.join(second, vid, source.name))
            assert a == b, (vid, source.name)
        a = itk.read_text(os.path.join(first, vid, itk.MANIFEST))
        b = itk.read_text(os.path.join(second, vid, itk.MANIFEST))
        assert a == b, vid


def test_every_donor_node_key_appears_once_under_the_vid(built):
    root, _ = built
    for vid in VIDS:
        for name, want in EXPECTED.items():
            if not want["wrapped"]:
                continue
            source = itk.source(name)
            donor_keys = list(yaml.safe_load(_donor(source)))
            body = _derived(root, vid, source)
            wrapped = yaml.safe_load(body)
            assert list(wrapped) == [vid], name
            assert sorted(wrapped[vid]) == sorted(donor_keys), name
            assert len(donor_keys) == want["wrap_keys"], name
            for key in donor_keys:
                assert body.count("\n  " + key + ":") == 1, (name, key)


def test_nav_sections_resolve_to_vid_scoped_fqns(built):
    root, _ = built
    for vid in VIDS:
        cfg = _cfg(root, vid)
        sections = []
        for dotted in NAV_SECTION_KEYS:
            node = cfg
            for part in dotted.split("."):
                node = node[part]
            sections.extend(str(node).split())
        assert len(sections) == 7
        nav2 = yaml.safe_load(_derived(root, vid, itk.source("nav2.yaml")))
        for section in sections:
            assert section in nav2[vid], (vid, section)
            fqn = "/{}/{}".format(vid, section)
            assert fqn.startswith("/" + vid + "/")
        # and the two costmaps keep their second level, so the FQN the
        # server builds is /<vid>/local_costmap/local_costmap
        for costmap in ("local_costmap", "global_costmap"):
            assert costmap in nav2[vid][costmap]


def test_no_two_vids_share_a_frame_literal(built):
    """m6/CONTEXT.md:263-290's defect, inverted into a gate."""
    root, _ = built
    seen = {}
    for vid in VIDS:
        body = _derived(root, vid, itk.source("model.sdf"))
        frames = set(re.findall(r"<gz_frame_id>([^<]+)</gz_frame_id>", body))
        frames |= set(re.findall(r"<odom_frame>([^<]+)</odom_frame>", body))
        frames |= set(re.findall(
            r"<robot_base_frame>([^<]+)</robot_base_frame>", body))
        assert len(frames) == 9, vid
        for frame in frames:
            assert frame.startswith(vid + "/"), (vid, frame)
            assert frame not in seen, (frame, seen.get(frame), vid)
            seen[frame] = vid
        cfg = _cfg(root, vid)
        for key, donor in (("odom", "odom"), ("base_link", "base_link"),
                           ("imu", "imu_link"),
                           ("nav_lidar", "nav_lidar_link"),
                           ("rf2o_odom", "rf2o_odom"),
                           ("pallet_cam", "pallet_cam_link"),
                           ("pallet_cam_optical", "pallet_cam_optical")):
            assert cfg["frames"][key] == "{}/{}".format(vid, donor)
    # ONE shared map frame, and it is the only shared one.
    for vid in VIDS:
        assert _cfg(root, vid)["frames"]["map"] == "map"


def test_spawn_and_initialpose_agree_with_the_vehicles_table(built):
    root, _ = built
    for vid in VIDS:
        cfg = _cfg(root, vid)
        assert cfg["vehicle"]["spawn"] == VEHICLES[vid]["spawn"]
        assert cfg["topics"]["initialpose"] == "/{}/initialpose".format(vid)
        assert cfg["topics"]["amcl_pose"] == "/{}/amcl_pose".format(vid)
    poses = {vid: tuple(sorted(_cfg(root, vid)["vehicle"]["spawn"].items()))
             for vid in VIDS}
    assert len(set(poses.values())) == len(VIDS)


def test_dark_command_keys_keep_their_donor_value(built):
    """AMR-DEC-006: the command seam is the adapter's, so these three
    keys are NOT re-pointed. They carry the blanket rewrite because the
    gz terminals are per-truck, and nothing else."""
    root, _ = built
    donor = yaml.safe_load(_donor(itk.source("config.yaml")))
    for vid in VIDS:
        cfg = _cfg(root, vid)
        for key in ("steer_cmd", "traction_cmd", "fork_cmd"):
            expected = donor["topics"][key].replace("/forklift/gz/",
                                                    "/{}/gz/".format(vid))
            assert cfg["topics"][key] == expected, (vid, key)
            assert cfg["topics"][key].endswith("/gz/actuator/" + key)
    named = [rule.dotted for rule in itk.source("config.yaml").rules
             if rule.kind != "dark"]
    for key in ("topics.steer_cmd", "topics.traction_cmd", "topics.fork_cmd"):
        assert key not in named


def test_the_shared_names_stay_shared(built):
    root, _ = built
    for vid in VIDS:
        cfg = _cfg(root, vid)
        assert cfg["topics"]["map"] == "/map"
        assert cfg["topics"]["clock"] == "/clock"
        assert cfg["topics"]["tf"] == "/tf"
        assert cfg["topics"]["tf_static"] == "/tf_static"
        assert cfg["isolation"]["map_ros_domain_id"] == "98"
        nav2 = yaml.safe_load(
            _derived(root, vid, itk.source("nav2.yaml")))[vid]
        assert nav2["global_costmap"]["global_costmap"][
            "ros__parameters"]["global_frame"] == "map"
        assert nav2["bt_navigator"]["ros__parameters"]["global_frame"] == "map"
        assert nav2["behavior_server"][
            "ros__parameters"]["global_frame"] == "map"
        assert nav2["global_costmap"]["global_costmap"]["ros__parameters"][
            "static_layer"]["map_topic"] == "/map"


def test_the_bare_shared_names_gained_the_vid(built):
    root, _ = built
    for vid in VIDS:
        topics = _cfg(root, vid)["topics"]
        for key, donor in (("cmd_vel", "/cmd_vel"),
                           ("cmd_vel_smoothed", "/cmd_vel_smoothed"),
                           ("cmd_vel_monitored", "/cmd_vel_monitored"),
                           ("speed_limit", "/speed_limit"),
                           ("slam_pose", "/pose"),
                           ("dock_robot", "/dock_robot"),
                           ("undock_robot", "/undock_robot")):
            assert topics[key] == "/{}{}".format(vid, donor), (vid, key)


def test_isolation_and_the_singleton_paths_moved(built):
    root, _ = built
    for vid in VIDS:
        cfg = _cfg(root, vid)
        assert cfg["isolation"]["gz_partition"] == "m6"
        assert cfg["isolation"]["ros_domain_id"] == "96"
        assert cfg["paths"]["log_dir"] == "m6_ver2/logs/" + vid
        assert cfg["paths"]["pidfile"] == (
            "m6_ver2/vehicles/{}/.pids".format(vid))
        assert cfg["paths"]["traction_file"] == (
            "m6_ver2/vehicles/{}/.traction".format(vid))


def test_every_derived_artifact_path_points_at_this_vids_copy(built):
    root, _ = built
    for vid in VIDS:
        cfg = _cfg(root, vid)
        pointed = {
            cfg["vehicle"]["model"],
            cfg["ekf"]["params_file"],
            cfg["smoother"]["params_file"],
            cfg["monitor"]["params_file"],
            cfg["localization"]["amcl"]["params_file"],
            cfg["nav"]["params_file"],
            cfg["nav"]["bt_xml"],
            cfg["nav"]["bt_xml_rpp"],
        }
        assert len(pointed) == 8
        for path in pointed:
            assert path.startswith("m6_ver2/vehicles/{}/".format(vid)), path
            assert os.path.exists(os.path.join(root, vid,
                                               os.path.basename(path))), path


def test_the_crib_paths_are_not_rewritten(built):
    """agv/forklift/... is a repo path, not this truck's namespace."""
    root, _ = built
    for vid in VIDS:
        for name, want in EXPECTED.items():
            body = _derived(root, vid, itk.source(name))
            assert (body.count("agv/forklift/")
                    == want["agv_forklift_kept"]), name
            assert body.count("/forklift/gz/") == 0, name
            assert body.count("/m5v3/") == 0, name
            assert (body.count("/{}/gz/".format(vid))
                    == want["forklift_gz"]), name


def test_check_refuses_a_stale_derivation(tmp_path, capsys):
    root = str(tmp_path)
    itk.instantiate("f1", out_root=root)
    assert itk.check("f1", out_root=root) == []
    target = os.path.join(root, "f1", "smoother.yaml")
    body = itk.read_text(target)
    itk.write_text(target,
                   body.replace("velocity_smoother", "velocity_smooth"))
    problems = itk.check("f1", out_root=root)
    assert len(problems) == 1 and "smoother.yaml" in problems[0]
    os.remove(os.path.join(root, "f1", "model.sdf"))
    assert any("model.sdf" in p for p in itk.check("f1", out_root=root))


def test_check_refuses_a_missing_derivation(tmp_path):
    problems = itk.check("f1", out_root=str(tmp_path))
    assert problems and "MANIFEST" in problems[0]


def test_unknown_vid_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        itk.instantiate("f9", out_root=str(tmp_path))


def test_a_drifted_donor_value_is_refused(tmp_path, monkeypatch):
    """The keyed rewrite is a contract with the donor, not a search."""
    source = itk.source("config.yaml")
    rule = [r for r in source.rules if r.dotted == "isolation.gz_partition"][0]
    monkeypatch.setattr(rule, "donor", "m5v4", raising=True)
    with pytest.raises(SystemExit):
        itk.instantiate("f1", out_root=str(tmp_path))


def test_manifest_records_the_donor_hashes_and_no_clock(built):
    root, manifests = built
    for vid in VIDS:
        manifest = manifests[vid]
        assert manifest["vid"] == vid
        assert manifest["tool_version"] == itk.TOOL_VERSION
        assert manifest["spawn"] == VEHICLES[vid]["spawn"]
        for name in EXPECTED:
            entry = manifest["sources"][name]
            assert len(entry["donor_sha256"]) == 64
            assert len(entry["derived_sha256"]) == 64
            assert entry["src"].startswith("m5_ver3/")
        blob = itk.read_text(os.path.join(root, vid, itk.MANIFEST))
        assert json.loads(blob) == manifest
        # A manifest that changes when nothing changed cannot be a
        # freshness check, so it carries no timestamp.
        assert "time" not in blob and "stamp" not in blob


def test_manifest_names_what_still_points_at_the_donor(built):
    """The paths G1 does NOT move are disclosed, not hidden."""
    root, manifests = built
    for vid in VIDS:
        left = manifests[vid]["donor_pointed_paths"]
        assert "m5_ver3/docks.yaml" in left
        assert "m5_ver3/maps" in left
        assert not [path for path in left
                    if path in ("m5_ver3/nav2.yaml", "m5_ver3/ekf.yaml",
                                "m5_ver3/amcl.yaml", "m5_ver3/smoother.yaml",
                                "m5_ver3/collision_monitor.yaml")]
