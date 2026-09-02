"""The pins on tools/fleet_odom_firewall.py - SPEC_ADAPTER.md Decision 4.

WHAT IS BEING PINNED IS A NEGATIVE, and that is why it needs a suite.
The firewall's whole claim is that the ground truth reaches NOTHING the
fleet layer reads. A positive - "the estimate is on the wire" - can be
seen in a running system; the negative cannot, because a fleet counting
route progress on `/<vid>/gz/odom` behaves EXACTLY like one counting on
`/<vid>/est/odom` right up to the moment localisation is wrong, which is
the moment the measurement was supposed to catch.

NOTHING HERE STARTS A SIMULATOR AND NOTHING HERE WRITES THE REAL BUILD
PRODUCT. The tool's two halves are separable on purpose: `override()` is
a pure text transform and every destructive test runs it over a
derivation made into tmp_path. What IS read from the real tree is the
file the fleet actually opens - contract(vid)["config_path"] - because
the state of that file is the only thing the claim is about.
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, os.pardir))
_REPO = os.path.normpath(os.path.join(_M6V2, os.pardir))
for _sub in (os.path.join(_M6V2, "tools"),
             os.path.join(_REPO, "m6", "tools"),
             os.path.join(_REPO, "m6", "ipc")):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

yaml = pytest.importorskip("yaml")

import fleet_odom_firewall as firewall                    # noqa: E402
import instantiate_truck as itk                           # noqa: E402
import instantiate_vehicle                                # noqa: E402
import status_contract                                    # noqa: E402
from status_contract import VEHICLES                      # noqa: E402

VIDS = sorted(VEHICLES)


@pytest.fixture(scope="module")
def fresh(tmp_path_factory):
    """m6's own derivation, into a throwaway root. NOT firewalled."""
    root = str(tmp_path_factory.mktemp("m6_vehicles"))
    for vid in VIDS:
        instantiate_vehicle.instantiate(vid, out_root=root)
    return root


def _body(root, vid):
    return itk.read_text(os.path.join(root, vid, "config.yaml"))


def _topics(text):
    return yaml.safe_load(text)["topics"]


# ----------------------------------------------------------------------
# what m6's own tool writes, measured rather than assumed
# ----------------------------------------------------------------------

def test_m6s_own_derivation_points_the_fleet_at_ground_truth(fresh):
    """The state this tool exists to change.

    If m6's tool ever stopped writing the truth there, this file would
    be solving a problem that had gone away - and `override()` would
    refuse rather than pretend, which is the next test.
    """
    for vid in VIDS:
        topics = _topics(_body(fresh, vid))
        assert topics["gz_odom"] == firewall.truth_odom_topic(vid)
        assert topics["gz_odom"] == "/{}/gz/odom".format(vid)


def test_the_override_moves_exactly_one_key(fresh):
    for vid in VIDS:
        before = _body(fresh, vid)
        after = firewall.override(before, vid, "test")
        left = before.split("\n")
        right = after.split("\n")
        assert len(left) == len(right)
        differing = [i for i in range(len(left)) if left[i] != right[i]]
        assert len(differing) == 1, differing
        assert "gz_odom:" in left[differing[0]]
        assert _topics(after)["gz_odom"] == firewall.est_odom_topic(vid)
        # and every OTHER topic is untouched
        was, now = _topics(before), _topics(after)
        assert {k: v for k, v in was.items() if k != "gz_odom"} == \
               {k: v for k, v in now.items() if k != "gz_odom"}


def test_the_ground_truth_is_no_VALUE_in_a_fleet_read_config(fresh):
    """THE FIREWALL ITSELF, stated as a property of the file.

    VALUES and not substrings, deliberately: agv/forklift/config.yaml
    carries a whole paragraph ASKING for this rename and it spells
    `/<vid>/gz/odom_ground_truth` inside it, which contains the truth
    topic as a prefix. A grep would fail on a comment that is on this
    tool's side. What matters is that nothing the fleet layer READS -
    and it reads by key - resolves to the truth.
    """
    for vid in VIDS:
        after = firewall.override(_body(fresh, vid), vid, "test")
        truth = firewall.truth_odom_topic(vid)
        named = [key for key, value in _topics(after).items()
                 if value == truth]
        assert named == [], named
        # the whole file, not just topics:, because a value anywhere is
        # a value something could grow a reader for
        flat = yaml.safe_load(after)
        stack = [flat]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
            else:
                assert node != truth, node
        # and it is STILL a comment in the file, which is history and
        # not a wire - the rename request m5-07b made and this branch
        # could not act on.
        assert "odom_ground_truth" in after


def test_the_override_refuses_a_value_it_does_not_recognise(fresh):
    """A guess is the one thing a derivation may not make.

    Applying twice is the case that matters: `apply()` regenerates from
    m6's tool BEFORE it overrides, so a second application starts from
    the truth again. Applied to an already-firewalled body it refuses,
    which is what stops this tool being run over an unknown state.
    """
    once = firewall.override(_body(fresh, "f1"), "f1", "test")
    with pytest.raises(SystemExit):
        firewall.override(once, "f1", "test")
    with pytest.raises(SystemExit):
        firewall.override(_body(fresh, "f1").replace(
            "gz_odom: /f1/gz/odom", "gz_odom: /f1/odom"), "f1", "test")


def test_the_override_refuses_a_config_without_the_key(fresh):
    body = _body(fresh, "f1").replace("  gz_odom: /f1/gz/odom\n", "")
    with pytest.raises(SystemExit):
        firewall.override(body, "f1", "test")


def test_the_override_is_idempotent_over_a_fresh_derivation(tmp_path):
    """Regenerate, override, twice: identical bytes."""
    first, second = str(tmp_path / "a"), str(tmp_path / "b")
    for root in (first, second):
        instantiate_vehicle.instantiate("f1", out_root=root)
    left = firewall.override(_body(first, "f1"), "f1", "test")
    right = firewall.override(_body(second, "f1"), "f1", "test")
    assert left == right
    # and re-deriving over its own output and overriding again lands on
    # the same place, which is what makes preflight safe to re-run
    instantiate_vehicle.instantiate("f1", out_root=first)
    assert firewall.override(_body(first, "f1"), "f1", "test") == left


# ----------------------------------------------------------------------
# the file the fleet actually opens
# ----------------------------------------------------------------------

def test_the_config_the_fleet_table_names_carries_the_estimate():
    """THE ONE READ OF THE REAL TREE, and it is the point of the task.

    vda_agent.py:199 and hmi_node.py:211 open
    contract(vid)["config_path"] and subscribe topics["gz_odom"]. This
    asserts the state of THAT file, on this machine, now.
    """
    for vid in VIDS:
        path = status_contract.contract(vid)["config_path"]
        assert path == firewall.config_path(vid)
        if not os.path.isfile(path):
            pytest.skip("m6's derivation has not been made: run "
                        "m6_ver2/tools/fleet_odom_firewall.py --all")
        topics = _topics(itk.read_text(path))
        assert topics["gz_odom"] == firewall.est_odom_topic(vid)
        assert firewall.truth_odom_topic(vid) not in set(topics.values())


def test_check_is_clean_on_the_real_tree():
    for vid in VIDS:
        if not os.path.isfile(firewall.config_path(vid)):
            pytest.skip("m6's derivation has not been made")
        assert firewall.check(vid) == []


def test_check_refuses_an_unfirewalled_config(tmp_path, monkeypatch):
    """The failure is a FILE, not a process, so the check reads a file.

    One `python3 m6/tools/instantiate_vehicle.py --all` - which m6's own
    cell may legitimately run - puts the truth back under the fleet's
    key. Nothing errors; the world would come up and the trucks would
    drive.
    """
    root = str(tmp_path / "vehicles")
    instantiate_vehicle.instantiate("f1", out_root=root)
    path = os.path.join(root, "f1", "config.yaml")
    monkeypatch.setattr(firewall, "config_path", lambda vid: path)
    problems = firewall.check("f1", out_root=str(tmp_path / "fresh"))
    assert problems
    assert any("not what this tool writes" in line for line in problems)
    assert any(firewall.NOTE in line for line in problems)


def test_check_refuses_a_note_from_an_older_tool(tmp_path, monkeypatch):
    root = str(tmp_path / "vehicles")
    instantiate_vehicle.instantiate("f1", out_root=root)
    path = os.path.join(root, "f1", "config.yaml")
    itk.write_text(path, firewall.override(itk.read_text(path), "f1", path))
    itk.write_text(os.path.join(root, "f1", firewall.NOTE),
                   json.dumps({"tool_version": "0"}) + "\n")
    monkeypatch.setattr(firewall, "config_path", lambda vid: path)
    problems = firewall.check("f1", out_root=str(tmp_path / "fresh"))
    assert any("tool version 0" in line for line in problems)


def test_the_note_says_what_was_changed_and_how_to_undo_it(tmp_path,
                                                           monkeypatch):
    """A build product varied by a second tool needs a paper trail
    where the file is, not where the tool is."""
    root = str(tmp_path / "vehicles")
    monkeypatch.setattr(instantiate_vehicle, "OUT_ROOT", root)
    real = instantiate_vehicle.instantiate

    def into_tmp(vid, out_root=root):
        return real(vid, out_root=root)

    monkeypatch.setattr(instantiate_vehicle, "instantiate", into_tmp)
    monkeypatch.setattr(firewall, "config_path",
                        lambda vid: os.path.join(root, vid, "config.yaml"))
    record = firewall.apply("f1")
    assert record["key"] == "topics.gz_odom"
    assert record["was"] == "/f1/gz/odom"
    assert record["now"] == "/f1/est/odom"
    assert "instantiate_vehicle.py --all" in record["undo"]
    note = json.loads(itk.read_text(os.path.join(root, "f1", firewall.NOTE)))
    assert note == record
    assert note["firewalled_sha256"] != note["m6_derived_sha256"]
    # a record that changed when nothing changed cannot be a freshness
    # check, so it carries no timestamp
    blob = itk.read_text(os.path.join(root, "f1", firewall.NOTE))
    assert "time" not in blob and "stamp" not in blob


# ----------------------------------------------------------------------
# the two ends of the wire
# ----------------------------------------------------------------------

def test_the_est_topic_is_the_one_the_adapter_publishes():
    """CROSS-FILE PIN. The firewall points a key at an address; the
    adapter publishes it. Two spellings of one topic is a fleet
    subscribed to silence, and nothing on either side would notice."""
    from nav2_adapter_node import REQUIRED_KEYS, vehicle_config, wiring
    for vid in VIDS:
        cfg = vehicle_config(vid, "test_fleet_odom_firewall", REQUIRED_KEYS)
        rows = {wire.label: wire.address for wire in wiring(cfg, vid)
                if wire.kind == "pub"}
        assert firewall.est_odom_topic(vid) == "/{}/{}".format(vid,
                                                               rows["est"])


def test_a_stranger_vid_is_refused_by_both_names():
    for name in (firewall.est_odom_topic, firewall.truth_odom_topic,
                 firewall.config_path):
        with pytest.raises(SystemExit):
            name("forklift")


def test_the_firewall_writes_only_gitignored_build_products():
    ignore = itk.read_text(os.path.join(_REPO, ".gitignore"))
    assert "m6/vehicles/" in ignore
    for vid in VIDS:
        rel = os.path.relpath(firewall.config_path(vid), _REPO)
        assert rel.replace(os.sep, "/").startswith("m6/vehicles/")
        assert os.path.dirname(firewall.note_path(vid)) == \
            os.path.dirname(firewall.config_path(vid))
    # the SOURCES it derives from are tracked and are not written
    for path in (instantiate_vehicle.SRC_CONFIG, instantiate_vehicle.SRC_MODEL):
        assert os.path.isfile(path)
        rel = os.path.relpath(path, _REPO).replace(os.sep, "/")
        assert not rel.startswith("m6/vehicles/")


def test_the_adapter_wires_nothing_that_names_the_ground_truth():
    """SPEC_ADAPTER.md Decision 4: the adapter consumes NOTHING of it.

    The wiring table is DATA - every subscription, publication and
    action this node creates - so the claim is decidable here rather
    than by grepping for a string that appears in prose. The world
    launch still bridges the truth for scoring; nothing on the command
    or contract path may name it.
    """
    from nav2_adapter_node import REQUIRED_KEYS, vehicle_config, wiring
    for vid in VIDS:
        cfg = vehicle_config(vid, "test_fleet_odom_firewall", REQUIRED_KEYS)
        truth = firewall.truth_odom_topic(vid)
        for wire in wiring(cfg, vid):
            assert truth not in str(wire.address), wire
    # and the m5v3 key that DOES name it is not among the keys this
    # node reads at all - a reader is how a firewall gets a door.
    assert "topics.odom_ground_truth" not in REQUIRED_KEYS


def test_the_tests_left_the_real_tree_firewalled():
    """A suite that unfirewalled the tree on its way past would be a
    suite that armed the failure it exists to prevent."""
    for vid in VIDS:
        path = firewall.config_path(vid)
        if not os.path.isfile(path):
            pytest.skip("m6's derivation has not been made")
        assert _topics(itk.read_text(path))["gz_odom"] == \
            firewall.est_odom_topic(vid)
