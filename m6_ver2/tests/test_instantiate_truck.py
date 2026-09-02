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
#   keyed_inserted / inserted_lines
#                - blocks written UNDER an asserted anchor, and how many
#                  lines they add. An insertion is the one edit a count
#                  taken over the DONOR cannot see, so it is counted
#                  here and the residue pin takes it back out.
#   bt_goal_checker
#                - the one attribute each behaviour tree gains: with two
#                  goal checkers declared, nav2_controller will not fall
#                  back to "the only plugin loaded" and an unnamed
#                  checker aborts every FollowPath.
#   lines        - donor line count, which the wrap check is built on
# ----------------------------------------------------------------------
EXPECTED = {
    "config.yaml": {
        "forklift_gz": 20, "m5v3": 9, "agv_forklift_kept": 8,
        "gt_frame_mentions_kept": 2,
        "keyed_rewritten": 33, "keyed_asserted": 9,
        # nav.bt_xml_station: a key the donor does not have, written
        # under nav.bt_xml_rpp with its nine comment lines and a blank.
        "keyed_inserted": 1, "inserted_lines": 11,
        "lines": 5542, "wrapped": False,
    },
    "nav2.yaml": {
        "forklift_gz": 2, "m5v3": 2, "agv_forklift_kept": 3,
        # THE ONLY ROW WHERE gz_survivors IS NOT forklift_gz, and the
        # difference is the masked scan (M6V2-G1-B4). The blanket
        # rewrite carries both obstacle layers' `topic:` onto this
        # truck's gz namespace and a keyed rule then moves them OFF it,
        # onto scan_mask_node's output - so the two literals the blanket
        # counted are gone from the finished file. See
        # instantiate_truck.MASKED_SCAN_TEMPLATE.
        "gz_survivors": 0,
        # 9 and not 8 since M6V2-G1-B5: goal_checker_plugins gains the
        # station checker's name beside the general one.
        "keyed_rewritten": 9, "keyed_asserted": 4,
        # TWO blocks: station_goal_checker's, written under
        # general_goal_checker's last line (26), and the amendment to
        # FollowPathRPP's paragraphs about the 0.60 m box, written
        # under its last parameter (24).
        "keyed_inserted": 2, "inserted_lines": 50,
        "lines": 2273, "wrapped": True, "wrap_keys": 7,
    },
    "amcl.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 1,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0,
        "lines": 524, "wrapped": True, "wrap_keys": 2,
    },
    "ekf.yaml": {
        "forklift_gz": 2, "m5v3": 0, "agv_forklift_kept": 1,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0,
        "lines": 368, "wrapped": True, "wrap_keys": 1,
    },
    "smoother.yaml": {
        "forklift_gz": 2, "m5v3": 0, "agv_forklift_kept": 2,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0,
        "lines": 257, "wrapped": True, "wrap_keys": 1,
    },
    "collision_monitor.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 0,
        "keyed_rewritten": 2, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0,
        "lines": 343, "wrapped": True, "wrap_keys": 1,
    },
    "docking.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 0,
        "keyed_rewritten": 2, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0,
        "lines": 69, "wrapped": True, "wrap_keys": 2,
    },
    "apriltag.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 0,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0,
        "lines": 33, "wrapped": True, "wrap_keys": 1,
    },
    "ekf_rf2o.yaml": {
        "forklift_gz": 0, "m5v3": 0, "agv_forklift_kept": 0,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0,
        "lines": 130, "wrapped": False,
    },
    "model.sdf": {
        "forklift_gz": 42, "m5v3": 0, "agv_forklift_kept": 6,
        "gz_frame_id": 7, "gt_odom_frame": 2, "gt_base_frame": 2,
        "pallet_s5_kept": 2,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0,
        "lines": 2252, "wrapped": False,
    },
    "navigate_to_pose_tricycle_v3.xml": {
        "forklift_gz": 0, "m5v3": 2, "agv_forklift_kept": 1,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0, "bt_goal_checker": 1,
        "lines": 242, "wrapped": False,
    },
    "navigate_to_pose_tricycle_v3_rpp.xml": {
        "forklift_gz": 0, "m5v3": 1, "agv_forklift_kept": 0,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0, "bt_goal_checker": 1,
        "lines": 111, "wrapped": False,
    },
    # THE THIRD TREE, DERIVED FROM THE SECOND ONE'S DONOR. Every count
    # is the rpp row's, because it is the same donor bytes; the one
    # difference is which goal checker its FollowPath names, and that
    # is a value rather than a count - test_the_third_tree_differs_by_
    # exactly_the_goal_checker is where it is pinned.
    "navigate_to_pose_tricycle_v3_rpp_station.xml": {
        "forklift_gz": 0, "m5v3": 1, "agv_forklift_kept": 0,
        "keyed_rewritten": 0, "keyed_asserted": 0,
        "keyed_inserted": 0, "inserted_lines": 0, "bt_goal_checker": 1,
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
                # gz_survivors is a fact about the FINISHED file, not
                # about the pipeline's counters, so the manifest does
                # not carry it - test_the_crib_paths_are_not_rewritten
                # is where it is checked.
                if key in ("lines", "wrapped", "wrap_keys",
                           "gz_survivors"):
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
            # THE WRAP SEES THE FILE THE INSERTIONS ALREADY GREW, so
            # the donor line count is not the number it wraps - the
            # difference is exactly the block this table declares.
            grown = want["lines"] + want["inserted_lines"]
            assert entry["counts"]["wrap_lines_in"] == grown, name
            assert entry["counts"]["wrap_lines_out"] == grown + 1, name
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
            cfg["nav"]["bt_xml_station"],
        }
        assert len(pointed) == 9
        for path in pointed:
            assert path.startswith("m6_ver2/vehicles/{}/".format(vid)), path
            assert os.path.exists(os.path.join(root, vid,
                                               os.path.basename(path))), path


def test_both_costmaps_read_the_masked_scan(built):
    """M6V2-G1-B4's rule, and the reason it is a DERIVATION and not a flag.

    nav2's costmaps are SUB-NODES with no command line, so the topic
    their obstacle layer marks and clears from is a FILE literal and
    this tool is the only thing that can change it. What it has to be
    changed to is NOT the bridge's raw scan: the vehicle's own mast
    stands in the nav lidar's beam at 1.29-1.48 m (follower.SELF_MASK),
    and a layer that marks those returns puts lethal cells ON THE ROBOT
    - 205 START_OCCUPIED, on every plan, for ever, with nothing in any
    log naming the truck as the obstacle.

    ONE SPELLING, and everything else asks this module for it:
    m6_ver2/truck.sh passes it to scan_mask_node and to AMCL and then
    checks this file against the answer.
    """
    donor = itk.read_text(os.path.join(itk.REPO, "m5_ver3", "nav2.yaml"))
    assert donor.count("topic: /forklift/gz/scan_nav") == 2
    root, _ = built
    for vid in VIDS:
        masked = itk.masked_scan_topic(vid)
        assert masked == "/{}/scan_nav_masked".format(vid)
        body = _derived(root, vid, itk.source("nav2.yaml"))
        assert body.count("topic: " + masked) == 2
        # AND THE RAW SCAN IS GONE FROM THAT FILE. A costmap left on it
        # is the failure this rule exists to prevent, and it is not
        # visible from anywhere else.
        raw = _cfg(root, vid)["topics"]["scan_nav"]
        assert raw == "/{}/gz/scan_nav".format(vid)
        assert raw not in body
        # AMCL is pointed at the masked scan on its COMMAND LINE (it is
        # not a sub-node), so amcl.yaml holds no scan topic at all -
        # asserted, because a second copy there would be one nobody
        # checks.
        assert "scan_topic:" not in _derived(root, vid,
                                             itk.source("amcl.yaml"))


def test_the_masked_scan_name_refuses_a_stranger():
    with pytest.raises(SystemExit):
        itk.masked_scan_topic("forklift")


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
            # gz_survivors, and it is `forklift_gz` on every row but
            # one: the blanket rewrite's count is what it MOVED, and a
            # keyed rule that runs after it may move a literal off the
            # gz namespace again. nav2.yaml's masked scan is that case
            # and it is spelled out in the table above.
            assert (body.count("/{}/gz/".format(vid))
                    == want.get("gz_survivors", want["forklift_gz"])), name


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


# ----------------------------------------------------------------------
# THE STATION GOAL CHECKER AND THE THIRD TREE - M6V2-G1-B5
#
# SPEC_ADAPTER.md Decision 2 gives the final leg into a bay a 0.25 m
# checker and leaves every transit leg on 0.60. nav2 delivers that
# through the behaviour tree - `goal_checker_id` is FollowPath's own
# input port - so the change is one plugin block, one list entry and one
# attribute, in three files that have to agree.
# ----------------------------------------------------------------------

def _controller_server(root, vid):
    nav2 = yaml.safe_load(_derived(root, vid, itk.source("nav2.yaml")))
    return nav2[vid]["controller_server"]["ros__parameters"]


def test_the_donor_declares_one_checker_and_names_it_nowhere():
    """The state this branch changed, measured on the donor.

    m5_ver3 drove to APPROACH POSES in open corridors: one checker, no
    tree naming it, and nav2's "the only plugin loaded" fallback doing
    the resolution. Every claim below is about a departure from that, so
    the departure is measured rather than assumed.
    """
    donor = yaml.safe_load(_donor(itk.source("nav2.yaml")))
    checkers = donor["controller_server"]["ros__parameters"][
        "goal_checker_plugins"]
    assert checkers == ["general_goal_checker"]
    assert "station_goal_checker" not in donor["controller_server"][
        "ros__parameters"]
    for name in ("navigate_to_pose_tricycle_v3.xml",
                 "navigate_to_pose_tricycle_v3_rpp.xml"):
        assert "goal_checker_id" not in _donor(itk.source(name))
    assert "bt_xml_station" not in _donor(itk.source("config.yaml"))


def test_the_derived_server_declares_both_checkers_general_first(built):
    """ORDER IS PINNED THOUGH NOTHING RESOLVES BY IT ANY MORE.

    With one checker loaded nav2 uses it whatever the goal says; with
    two it uses the one the goal NAMES and aborts on an empty name, so
    the list order decides nothing. It is still pinned: general is the
    checker every transit leg runs and the one whose eight-paragraph
    argument a reader meets first, and a list that quietly reordered
    would be a diff nobody could explain.
    """
    root, _ = built
    for vid in VIDS:
        params = _controller_server(root, vid)
        assert params["goal_checker_plugins"] == ["general_goal_checker",
                                                  "station_goal_checker"]
        assert params["general_goal_checker"]["xy_goal_tolerance"] == 0.60
        station = params["station_goal_checker"]
        # THE PLUGIN NAME IS nav2_controller 1.3.12's OWN, read out of
        # /opt/ros/jazzy/share/nav2_controller/plugins.xml, and its two
        # parameters are the only two the header declares.
        assert station["plugin"] == "nav2_controller::PositionGoalChecker"
        assert station["xy_goal_tolerance"] == 0.25
        assert station["stateful"] is True
        assert sorted(station) == ["plugin", "stateful", "xy_goal_tolerance"]


def test_the_station_box_is_the_fleets_own_arrival_radius(built):
    """0.25 m is not a second opinion about where a truck has arrived.

    follower.ARRIVE_M is the radius vda_agent's Progress counts an
    arrival at and the radius the adapter latches ARRIVED at, and every
    station declares the same number. A checker at any other value would
    finish a goal at a distance nothing else on this vehicle agrees is
    an arrival.
    """
    import follower
    from stations import STATIONS
    root, _ = built
    for vid in VIDS:
        box = _controller_server(root, vid)["station_goal_checker"][
            "xy_goal_tolerance"]
        assert box == follower.ARRIVE_M
        assert {station["arrive_m"] for station in STATIONS.values()} == {box}


def test_every_derived_tree_names_a_goal_checker_that_is_declared(built):
    """NO TREE RELIES ON nav2's DEFAULT, and that is not a style rule.

    ControllerServer::findGoalCheckerId falls back to the only plugin
    loaded when the goal names none - `cmp $0x1,%r15` against the
    checker map's size in libcontroller_server_core.so. Past one, an
    empty id is "Terminating action, invalid goal checker requested",
    which would abort EVERY FollowPath on this stack.
    """
    root, _ = built
    for vid in VIDS:
        declared = _controller_server(root, vid)["goal_checker_plugins"]
        for source in itk.SOURCES:
            if not source.goal_checker:
                continue
            body = _derived(root, vid, source)
            found = re.findall(r'goal_checker_id="([^"]+)"', body)
            assert found == [source.goal_checker], source.name
            assert source.goal_checker in declared, source.name


def test_the_third_tree_differs_by_exactly_the_goal_checker(built):
    """One attribute value, and the diff is asserted line by line."""
    root, _ = built
    rpp = itk.source("navigate_to_pose_tricycle_v3_rpp.xml")
    station = itk.source(itk.STATION_TREE)
    assert station.src == rpp.src
    for vid in VIDS:
        left = _derived(root, vid, rpp).split("\n")
        right = _derived(root, vid, station).split("\n")
        assert len(left) == len(right)
        differing = [index for index in range(len(left))
                     if left[index] != right[index]]
        assert len(differing) == 1, differing
        line = differing[0]
        assert left[line].replace('goal_checker_id="general_goal_checker"',
                                  'goal_checker_id="station_goal_checker"'
                                  ) == right[line]
        assert "<FollowPath " in left[line]


def test_the_leg_table_and_the_derived_config_name_the_same_three_trees(built):
    """THE CROSS-FILE PIN, and it is the one that would fail silently.

    nav2_legs.CLASS_TREE maps a leg class onto a config KEY; the
    derivation writes the key. A table naming a key the derivation does
    not write is a KeyError at boot if you are lucky and a goal carrying
    an empty behavior_tree if you are not.
    """
    import nav2_legs
    root, _ = built
    keys = sorted({key for _controller, key in nav2_legs.CLASS_TREE.values()})
    assert keys == ["nav.bt_xml", "nav.bt_xml_rpp", "nav.bt_xml_station"]
    for vid in VIDS:
        nav = _cfg(root, vid)["nav"]
        for key in keys:
            path = nav[key.split(".", 1)[1]]
            assert path.startswith("m6_ver2/vehicles/{}/".format(vid)), key
            assert os.path.exists(
                os.path.join(root, vid, os.path.basename(path))), key


def test_an_insertion_is_refused_when_its_anchor_has_moved(tmp_path,
                                                           monkeypatch):
    """The anchor's value is a contract, exactly as a rewrite's is."""
    rule = [r for r in itk.source("nav2.yaml").rules if r.inserts][0]
    monkeypatch.setattr(rule, "donor", "false", raising=True)
    with pytest.raises(SystemExit):
        itk.instantiate("f1", out_root=str(tmp_path))


def test_a_block_that_is_already_there_is_refused_by_the_inverse(built):
    """remove_block is the residue pin's other half.

    A derived file carrying the block twice - or not at all - is a file
    this tool did not write, and the inverse says so rather than
    guessing which copy to take out.
    """
    root, _ = built
    # config.yaml AND NOT nav2.yaml: both carry an insertion, and only
    # this one is unwrapped, so the block stands in the derived file
    # with the indentation it was written with. The wrapped file's
    # inverse unwraps before it removes, which is a different claim.
    source = itk.source("config.yaml")
    rule = [r for r in source.rules if r.inserts][0]
    body = _derived(root, "f1", source)
    # RENDERED THE WAY THE DERIVED FILE CARRIES IT. config.yaml is CRLF
    # and the block went in with the anchor line's ending, so a copy
    # joined with bare newlines would not be a copy of anything.
    rows = body.split("\n")
    carriage = "\r" if rows[0].endswith("\r") else ""
    want = [line + carriage for line in rule.new_lines("f1")]
    start = next(index for index in range(len(rows) - len(want) + 1)
                 if rows[index:index + len(want)] == want)
    doubled = "\n".join(rows[:start] + want + rows[start:])
    with pytest.raises(SystemExit):
        itk.invert_text(source, doubled, "f1",
                        itk.blanket_origins(_donor(source)))


def test_the_rpp_block_no_longer_claims_one_box_for_both_controllers(built):
    """COMMENTS ARE REWRITTEN WITH THE CODE, and this is the one comment
    the second goal checker made false.

    RPP 1.3.12 has no goal tolerance of its own - the donor's own block
    says so - it asks the goal checker at every tick and uses the
    answer. Which checker it asks is named by the tree the GOAL carried,
    so the same controller now arrives on 0.60 m leaving a bay and
    0.25 m entering one. The donor sentence "both controllers therefore
    arrive on exactly the same 0.60 m position-only box" is still in the
    derived file, because the donor is not edited - so the amendment has
    to be there too, and above it.
    """
    root, _ = built
    donor = _donor(itk.source("nav2.yaml"))
    # ONE LINE OF IT: the sentence is wrapped across two comment lines
    # in the donor, so a phrase that spans the break would never match.
    claim = "arrive on exactly the same 0.60 m"
    assert claim in donor
    for vid in VIDS:
        body = _derived(root, vid, itk.source("nav2.yaml"))
        assert claim in body
        note = "THE GOAL BOX THIS CONTROLLER ASKS FOR"
        assert body.count(note) == 1
        assert body.index(note) < body.index(claim)
        # the amendment carries the number it is amending TO, so a
        # reader does not have to go and find it
        block = body[body.index(note):body.index(claim)]
        assert "0.25 m box" in block
        assert "getTolerances" in block
