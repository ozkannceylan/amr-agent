#!/usr/bin/env python3
"""fleet_odom_firewall.py - the fleet layer reads the ESTIMATE, not the
simulator's truth.

    python3 m6_ver2/tools/fleet_odom_firewall.py --all
    python3 m6_ver2/tools/fleet_odom_firewall.py --vid f1
    python3 m6_ver2/tools/fleet_odom_firewall.py --all --check

SPEC_ADAPTER.md Decision 4, and it is the one place on this branch where
a FLEET-layer artifact is varied at all.

WHAT IS WRONG WITHOUT IT. m6's fleet layer counts route progress on
odometry: vda_agent subscribes `topics.gz_odom` and `_settle_arrival`
will not call a node reached until `Progress.reached == len(nodes)` off
that stream; the HMI draws the truck from the same key. On the m6 branch
that key names `/<vid>/gz/odom`, which is gz's OdometryPublisher - the
SIMULATOR'S OWN TRUTH, bridged straight off the plant. A fleet that
counts arrivals on truth while the autonomy stack drives on an AMCL/EKF
estimate is a fleet whose arrivals are measured with an instrument the
vehicle cannot see, and every localisation error becomes a silent
disagreement between "where the order says I am" and "where the
controller thinks I am".
  IT IS ALSO A CLAIM NO REAL TRUCK CAN MAKE. Ground truth is a
simulator artefact. Anything downstream of it that works only because it
is exact is work that will be redone on hardware, and that is the whole
reason the firewall is a rule and not a preference.

WHAT THIS TOOL DOES, AND IT IS EXACTLY ONE THING. It re-runs m6's own
derivation (m6/tools/instantiate_vehicle.py, which owns those bytes) and
then applies ONE counted keyed override to the gitignored product:

    topics.gz_odom:  /<vid>/gz/odom  ->  /<vid>/est/odom

`/<vid>/est/odom` is what m6_ver2/nav2_adapter/nav2_adapter_node.py
publishes at 20 Hz: the AMCL/EKF pose carried into m6 world coordinates
through the committed registration, with the EKF's body twist on it so
vda_agent's `driving` flag stays honest. The fleet layer is not
recompiled, not patched and not read differently - it reads the SAME KEY
and now receives the estimate, which restores nav_core's "same
measurement made twice": Progress counts on the estimate the adapter
latches ARRIVED on.

WHY THE OVERRIDE AND NOT AN EDIT OF THE SOURCE. agv/forklift/config.yaml
belongs to three stacks and AMR-DEC-006 freezes m6/ and m5_ver3/ byte
for byte in G1. m6/vehicles/<vid>/config.yaml is a GITIGNORED BUILD
PRODUCT (.gitignore:59), so the only thing varied here is a file that is
rebuilt from tracked bytes on demand - which is also why this tool
regenerates before it overrides rather than editing whatever it finds.

WHY THE KEY IS NOT RENAMED. `gz_odom` now lies about its source, and
that is a NAMED LEFTOVER rather than an oversight: renaming it means
editing vda_agent.py, hmi_node.py, nav_node.py, m6_world.launch.py and
two m6 tests - the frozen fleet layer - for a spelling. SPEC_ADAPTER.md
Decision 4 records the rename as owed the day that layer unfreezes.

WHERE THE TRUTH STILL LIVES, because a firewall that deleted the
evidence would be a different mistake. m6_ver2/world.launch.py still
bridges `/<vid>/gz/odom` gz->ROS for scoring, and it takes the name from
the OTHER derived family - m6_ver2/vehicles/<vid>/config.yaml's
`topics.odom_ground_truth`, which is the m5v3 schema's own spelling of
the same wire and is read by nothing in the fleet path. So the truth is
on the wire and its name is nowhere in a file the fleet reads, which is
what `check()` below asserts.

THE ONE RISK, NAMED. m6/vehicles/ is shared with the plain m6 cell, and
m6/gazebo/m6_world.launch.py bridges `topics.gz_odom` gz->ROS. After
this tool has run, that launch would bridge `/<vid>/est/odom` FROM gz -
a channel gz does not publish, and a second publisher on the estimate if
it did. The two cells are already mutually exclusive (m6v2.sh refuses to
start over a plain m6 world), and the repair is one command:

    ( cd m6 && python3 tools/instantiate_vehicle.py --all )

That is why the note this tool writes beside the file says what was
changed and how to undo it, in the directory a reader of that file is
already standing in.
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, os.pardir))
REPO = os.path.normpath(os.path.join(_M6V2, os.pardir))
_M6 = os.path.join(REPO, "m6")
for _sub in (_HERE, os.path.join(_M6, "tools"), os.path.join(_M6, "ipc")):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

# THE DOTTED-KEY INDEX IS BORROWED AND THE REFUSAL GRAMMAR IS NOT.
# instantiate_truck.key_lines() is a pure line scanner with no opinion
# about this tool, so a second copy of it here would be a second answer
# to "where does this key live". Its refuse() names ITS tool, so the
# refusals below are this file's own.
import instantiate_truck as itk                           # noqa: E402
import instantiate_vehicle                                # noqa: E402
import status_contract                                    # noqa: E402

TOOL = "fleet_odom_firewall"
#: Bumped when the override changes shape, so a note written by an older
#: tool is refused rather than trusted.
TOOL_VERSION = "1"

SPEC = "m6_ver2/SPEC_ADAPTER.md Decision 4"

#: The key the FLEET reads. vda_agent.py:199 and hmi_node.py:211 both
#: subscribe `topics["gz_odom"]` out of contract(vid)["config_path"],
#: and that is the whole reason this file exists.
ODOM_KEY = "topics.gz_odom"

#: What m6's own derivation writes there, and what it must not stay.
TRUTH_TEMPLATE = "/{vid}/gz/odom"
#: What the adapter publishes: the estimate in m6 world coordinates.
EST_TEMPLATE = "/{vid}/est/odom"

#: The record, written beside the file it describes. A reader who opens
#: m6/vehicles/<vid>/config.yaml and finds an `est` topic under a key
#: called `gz_odom` should not have to grep the repository to find out
#: who did it.
NOTE = "FLEET_ODOM_FIREWALL.json"


def refuse(check, owner, *lines):
    """Say no, name the check and the file that owns it, and exit 1."""
    pad = " " * (len(TOOL) + 2)
    out = ["{}: REFUSED at check '{}'".format(TOOL, check),
           "{}owned by: {}".format(pad, owner)]
    out.extend("{}{}".format(pad, line) for line in lines)
    sys.stderr.write("\n".join(out) + "\n")
    sys.stderr.flush()
    raise SystemExit(1)


def truth_odom_topic(vid):
    """`/<vid>/gz/odom` - the simulator's own pose, evidence only."""
    return TRUTH_TEMPLATE.format(vid=_known(vid))


def est_odom_topic(vid):
    """`/<vid>/est/odom` - the adapter's estimate, in world coordinates.

    ONE SPELLING FOR THE WHOLE BRANCH. m6_ver2/world.launch.py asks this
    module for it rather than composing a second copy, the way truck.sh
    asks instantiate_truck for the masked scan.
    """
    return EST_TEMPLATE.format(vid=_known(vid))


def _known(vid):
    from status_contract import VEHICLES
    if vid not in VEHICLES:
        refuse("the vid is one the fleet table knows",
               "m6/ipc/status_contract.py VEHICLES",
               "{!r} is not among {}".format(vid, sorted(VEHICLES)))
    return vid


def config_path(vid):
    """The file the FLEET reads for this truck, from the fleet's table.

    contract(vid)["config_path"] and not a path composed here: vda_agent
    opens exactly that, so a firewall applied to any other file would be
    a firewall applied to nothing.
    """
    return status_contract.contract(_known(vid))["config_path"]


def override(body, vid, path):
    """The one counted keyed rewrite. Refuses on anything it did not expect.

    A VALUE ASSERTION AND A COUNT, like every other derivation on this
    branch: the line has to read what m6's tool writes before it is
    allowed to read what this one writes, and the truth topic has to be
    gone from every VALUE afterwards.
    """
    truth, est = truth_odom_topic(vid), est_odom_topic(vid)
    index = itk.key_lines(body).get(ODOM_KEY, "missing")
    if index == "missing":
        refuse("the fleet's odom key is in the derived config", SPEC,
               "{} has no {}.".format(path, ODOM_KEY),
               "m6/tools/instantiate_vehicle.py derives that file from",
               "agv/forklift/config.yaml, and the key is what "
               "vda_agent.py",
               "subscribes. If it has been renamed, this firewall and the",
               "fleet layer have stopped talking about the same wire.")
    if index is None:
        refuse("the fleet's odom key appears exactly once", SPEC,
               "{} spells {} more than once.".format(path, ODOM_KEY))
    lines = body.split("\n")
    carriage = "\r" if lines[index].endswith("\r") else ""
    head, sep, value = lines[index].rstrip("\r").partition(":")
    if not sep or value.strip() != truth:
        refuse("the derived value is the one m6's own tool writes", SPEC,
               "{}:{} reads {!r}".format(path, index + 1, value.strip()),
               "and this tool was written against {!r}.".format(truth),
               "An override onto a value it does not recognise is a "
               "guess.")
    lines[index] = "{}: {}{}".format(head, est, carriage)
    out = "\n".join(lines)
    # THE FIREWALL, CHECKED RATHER THAN ASSUMED. A comment may still
    # cite the truth topic - agv/forklift/config.yaml carries a whole
    # paragraph asking for the rename - so what is asserted is that no
    # VALUE in the file names it. Values are what anything reads.
    rows = out.split("\n")
    named = [dotted for dotted, where in itk.key_lines(out).items()
             if where is not None
             and rows[where].rstrip("\r").partition(":")[2].strip() == truth]
    if named:
        refuse("no key in a fleet-read config names the ground truth",
               SPEC,
               "{} still points {} at {}".format(path, ", ".join(named),
                                                 truth),
               "The fleet layer reads this file by KEY, so a second key",
               "carrying the truth is the firewall with a door in it.")
    return out


def note_path(vid):
    return os.path.join(os.path.dirname(config_path(vid)), NOTE)


def apply(vid):
    """Regenerate m6's derived pair, apply the override, record it."""
    vid = _known(vid)
    instantiate_vehicle.instantiate(vid)
    path = config_path(vid)
    if not os.path.isfile(path):
        refuse("m6's derivation wrote the file the fleet table names",
               "m6/tools/instantiate_vehicle.py",
               "no {} after instantiate(); the two tools disagree about"
               .format(path),
               "where a vehicle's config lives.")
    derived = itk.read_text(path)
    out = override(derived, vid, path)
    itk.write_text(path, out)
    record = {
        "tool": TOOL, "tool_version": TOOL_VERSION, "vid": vid,
        "spec": SPEC,
        "config_path": os.path.relpath(path, REPO).replace(os.sep, "/"),
        "key": ODOM_KEY,
        "was": truth_odom_topic(vid), "now": est_odom_topic(vid),
        "m6_derived_sha256": itk.sha256(derived),
        "firewalled_sha256": itk.sha256(out),
        "undo": "( cd m6 && python3 tools/instantiate_vehicle.py --all )",
        "why": "the fleet layer counts route progress on odometry; the "
               "estimate is what the vehicle can see and the ground "
               "truth is a simulator artefact",
    }
    itk.write_text(note_path(vid),
                   json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def check(vid, out_root=None):
    """Name every way the file on disk is not the one this tool writes."""
    vid = _known(vid)
    path = config_path(vid)
    problems = []
    if not os.path.isfile(path):
        return ["{}: not there - nothing has been derived for {}"
                .format(path, vid)]
    note = note_path(vid)
    if not os.path.isfile(note):
        problems.append("{}: no {} - the firewall has not been applied"
                        .format(os.path.dirname(path), NOTE))
    else:
        try:
            recorded = json.loads(itk.read_text(note))
        except ValueError as error:
            recorded = {}
            problems.append("{}: unreadable ({})".format(note, error))
        if recorded and recorded.get("tool_version") != TOOL_VERSION:
            problems.append("{}: written by tool version {}, this is {}"
                            .format(note, recorded.get("tool_version"),
                                    TOOL_VERSION))
    # THE ONLY HONEST FRESHNESS TEST IS TO DO THE WORK AGAIN. m6's tool
    # derives from tracked bytes that may have moved, so the question is
    # not "is the note here" but "is the file on disk what regenerating
    # and overriding would write today".
    import tempfile
    root = out_root or tempfile.mkdtemp()
    instantiate_vehicle.instantiate(vid, out_root=root)
    fresh = itk.read_text(os.path.join(root, vid, "config.yaml"))
    want = override(fresh, vid, os.path.join(root, vid, "config.yaml"))
    if itk.read_text(path) != want:
        problems.append("{}: on disk is not what this tool writes"
                        .format(path))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="point the fleet layer's odom key at the adapter's "
                    "estimate instead of the simulator's ground truth "
                    "(SPEC_ADAPTER.md Decision 4)")
    parser.add_argument("--vid", help="one truck id, f1..f4")
    parser.add_argument("--all", action="store_true",
                        help="every truck in the fleet table")
    parser.add_argument("--check", action="store_true",
                        help="verify what is on disk, write nothing")
    args = parser.parse_args(argv)
    from status_contract import VEHICLES
    if args.all == bool(args.vid):
        parser.error("name --vid or pass --all, not both and not neither")
    vids = sorted(VEHICLES) if args.all else [args.vid]
    if args.check:
        problems = []
        for vid in vids:
            problems.extend("{}: {}".format(vid, line) for line in check(vid))
        if problems:
            refuse("the fleet configs on disk carry the firewall", SPEC,
                   *problems)
        print("{}: {} read the estimate".format(TOOL, " ".join(vids)))
        return 0
    for vid in vids:
        record = apply(vid)
        print("{}: {} {} {} -> {}".format(
            TOOL, record["config_path"], record["key"], record["was"],
            record["now"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
