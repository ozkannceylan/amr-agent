#!/usr/bin/env python3
"""nav2_envelope.py - the speed nav2 is CONFIGURED to be allowed to drive.

    python3 m6_ver2/nav2_adapter/nav2_envelope.py --selftest
    python3 m6_ver2/nav2_adapter/nav2_envelope.py --vid f1

NO ROS IN THIS FILE, and no arithmetic about a truck either: it reads
one number out of one file and names where it came from. It is its own
module rather than three lines in nav2_cmd.py because nav2_cmd is
arithmetic that a test can drive with plain floats, and a YAML read is
neither.

======================= WHY IT EXISTS, MEASURED =======================

m6_ver2/logs/run3-speed-limit-latch, 2026-09-02. The adapter published
the PLC's unrestricted permission as an ABSOLUTE `nav2_msgs/SpeedLimit`
- V_Limit 1500 mm/s went out as `speed_limit 1.5` - onto a controller
whose configured ceiling is 0.300 m/s.

    nav2's setSpeedLimit REPLACES a controller's maximum. It does not
    intersect with it.

MPPI scales its whole envelope by `speed_limit / vx_max`, so 1.5 on a
0.300 controller multiplied vx_max, vx_min AND wz_max by five; RPP
assigns `desired_linear_vel = speed_limit` outright. The next
/f1/cmd_vel row carried -1.5, the tricycle converter clamped the shaft
at config.yaml's `navcmd.speed_max_mps` of 0.700, and the truck entered
the S1 spur at 700 mm/s. The WARNING field there drops V_Limit
1500 -> 300 BY DESIGN. Wheel 700, permission 300: the F-program's speed
monitor latched and Motor went False, 3.31 s after the goal was sent.

A PERMISSION IS A PERMISSION TO GO SLOWER. It may narrow the envelope
and it may never widen it - which is a min(), and a min() needs to know
the other operand. This file is the other operand.

===================== ONE HOME, AND IT IS nav2's ======================

The envelope is read from the DERIVED nav2.yaml the controller_server
is actually launched with (config.yaml `nav.params_file` names it, and
that key is the only path involved). It is deliberately NOT copied into
config.yaml: a ceiling spelled in two files is two ceilings, and the
first one edited is the one that is right.

THE LOWEST CONFIGURED CONTROLLER WINS. This stack runs two - MPPI on
transit legs and RPP on station approaches (nav2.yaml
`controller_plugins`) - and a SpeedLimit REPLACES whichever one is
active. A message sized for the faster of them would widen the slower
one the moment the behaviour tree switched, which on this truck is the
moment it enters a station spur. So the number is the MINIMUM over the
configured controllers, and `controller_ceilings` returns the whole
table beside it so an operator can see which one is binding.

`vx_min` IS NOT IN IT. An asymmetric envelope's reverse end is a
permission the planner needs to solve Reeds-Shepp geometry at all, not
a ceiling on forward travel; taking the min over both ends would shrink
the whole truck to whatever creep the counterweight-first direction is
allowed.
"""
import argparse
import os
import sys

import yaml

import _donors                                            # noqa: F401


TOOL = "nav2_envelope"

#: nav2's own spelling of the block this file reads.
CONTROLLER_SERVER = "controller_server"
PARAMS = "ros__parameters"
PLUGINS = "controller_plugins"

#: How each controller plugin spells its forward speed ceiling, in the
#: order they are looked for. MPPI carries `vx_max`; RPP carries ONE
#: magnitude in `desired_linear_vel` and applies the sign afterwards.
#: A plugin that spells it a third way is refused BY NAME rather than
#: silently defaulted, because a defaulted envelope is the defect above.
ENVELOPE_KEYS = ("vx_max", "desired_linear_vel")

#: path -> parsed document. The params file is a gitignored BUILD
#: PRODUCT (SPEC_NAMESPACING.md 3) that cannot change under a running
#: node, and 136 kB of commented YAML per Adapter() would otherwise be
#: paid by every test in the shell suite for a number that never moves.
_PARSED = {}


class Nav2EnvelopeError(ValueError):
    """A params file this module will not guess the speed envelope of."""


def read_params(path):
    """The derived nav2.yaml as a mapping, parsed once per process."""
    path = os.path.abspath(path)
    if path in _PARSED:
        return _PARSED[path]
    if not os.path.isfile(path):
        raise Nav2EnvelopeError(
            "{} is not there, so nav2's speed envelope cannot be read and "
            "the adapter will not guess it. The per-vid tree is a "
            "gitignored BUILD PRODUCT: derive it with python3 "
            "m6_ver2/tools/instantiate_truck.py --all".format(path))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise Nav2EnvelopeError(
            "{} is not readable as YAML: {}".format(path, exc))
    if not isinstance(doc, dict):
        raise Nav2EnvelopeError(
            "{} does not parse to a mapping - a nav2 params file is "
            "<namespace>: <node>: ros__parameters:".format(path))
    _PARSED[path] = doc
    return doc


def controller_params(doc):
    """`controller_server`'s `ros__parameters` block, wherever it is nested.

    FOUND BY WALKING rather than by an assumed path. The derived files
    are wrapped under `<vid>:` (SPEC_NAMESPACING.md 3) and the donor's
    are not; a hard-coded `doc["f1"]["controller_server"]` would be a
    third opinion about which truck this is.
    """
    stack = [doc]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        server = node.get(CONTROLLER_SERVER)
        if isinstance(server, dict) and isinstance(server.get(PARAMS), dict):
            return server[PARAMS]
        stack.extend(value for value in node.values()
                     if isinstance(value, dict))
    raise Nav2EnvelopeError(
        "this params file names no {}.{} block, so there is no speed "
        "envelope in it to narrow. nav2.yaml is the file the "
        "controller_server is launched with (config.yaml "
        "nav.params_file)".format(CONTROLLER_SERVER, PARAMS))


def controller_ceilings(doc):
    """{plugin name: its forward speed ceiling in m/s}, one row per plugin.

    NAMED AND NOT SUMMED. When the envelope moves, the operator has to
    be able to see WHICH controller moved it; a bare float is
    unarguable and undebuggable.
    """
    block = controller_params(doc)
    plugins = block.get(PLUGINS)
    if not plugins:
        raise Nav2EnvelopeError(
            "{}.{}.{} is empty or absent: a controller_server with no "
            "controller has no envelope, and the adapter will not invent "
            "one".format(CONTROLLER_SERVER, PARAMS, PLUGINS))
    ceilings = {}
    for name in plugins:
        params = block.get(name)
        if not isinstance(params, dict):
            raise Nav2EnvelopeError(
                "{} is named in {} but carries no parameter block, so its "
                "speed ceiling cannot be read".format(name, PLUGINS))
        found = [key for key in ENVELOPE_KEYS if key in params]
        if not found:
            raise Nav2EnvelopeError(
                "{} carries none of {} - this module knows how MPPI and "
                "RPP spell their forward speed ceiling and will not guess "
                "a third plugin's. Add its key to "
                "nav2_envelope.ENVELOPE_KEYS.".format(
                    name, ", ".join(ENVELOPE_KEYS)))
        ceilings[name] = min(abs(float(params[key])) for key in found)
    return ceilings


def envelope_max_mps(doc):
    """The one number: the LOWEST configured controller ceiling, m/s."""
    return min(controller_ceilings(doc).values())


def envelope_max_mps_of(path):
    """The same number, out of the params file at `path`."""
    return envelope_max_mps(read_params(path))


def params_path(vid, repo=None):
    """Where this truck's derived nav2.yaml is. The instantiator's layout."""
    repo = repo or _donors.REPO
    return os.path.join(repo, "m6_ver2", "vehicles", vid, "nav2.yaml")


def _selftest(vid="f1"):
    """No ROS, no graph. Reads the derived file if it has been built."""
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    doc = {"f1": {CONTROLLER_SERVER: {PARAMS: {
        PLUGINS: ["FollowPath", "FollowPathRPP"],
        "FollowPath": {"vx_max": 0.300, "vx_min": -0.300},
        "FollowPathRPP": {"desired_linear_vel": 0.100}}}}}
    check("the two spellings are both read",
          controller_ceilings(doc) == {"FollowPath": 0.300,
                                       "FollowPathRPP": 0.100})
    check("the LOWEST controller ceiling is the envelope, because a "
          "SpeedLimit replaces rather than intersects",
          envelope_max_mps(doc) == 0.100)
    check("vx_min is not the envelope",
          envelope_max_mps({CONTROLLER_SERVER: {PARAMS: {
              PLUGINS: ["FollowPath"],
              "FollowPath": {"vx_max": 0.300,
                             "vx_min": -0.050}}}}) == 0.300)
    try:
        envelope_max_mps({"x": {CONTROLLER_SERVER: {PARAMS: {
            PLUGINS: ["Weird"], "Weird": {"top_speed": 1.0}}}}})
        check("an unknown plugin is refused BY NAME", False)
    except Nav2EnvelopeError as exc:
        check("an unknown plugin is refused BY NAME", "Weird" in str(exc))
    try:
        controller_params({"planner_server": {}})
        check("a file with no controller_server is refused", False)
    except Nav2EnvelopeError as exc:
        check("a file with no controller_server is refused",
              CONTROLLER_SERVER in str(exc))

    path = params_path(vid)
    if os.path.isfile(path):
        table = controller_ceilings(read_params(path))
        check("{}'s derived nav2.yaml reads: {} -> envelope {:.3f} m/s"
              .format(vid, ", ".join("{} {:.3f}".format(name, value)
                                     for name, value in sorted(table.items())),
                      envelope_max_mps_of(path)),
              min(table.values()) > 0.0)
    else:
        print("note  {} is not derived yet, so only the rules were "
              "checked".format(os.path.relpath(path, _donors.REPO)))

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="nav2's own configured speed envelope, read once "
                    "from the params file the controller_server is "
                    "launched with.")
    parser.add_argument("--vid", help="f1..f4 - print that truck's "
                                      "derived envelope and exit")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-simulator checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest(args.vid or "f1")
    if args.vid:
        path = params_path(args.vid)
        table = controller_ceilings(read_params(path))
        for name, value in sorted(table.items()):
            print("{:<24} {:.3f} m/s".format(name, value))
        print("{:<24} {:.3f} m/s  ({})".format(
            "ENVELOPE", envelope_max_mps_of(path),
            os.path.relpath(path, _donors.REPO)))
        return 0
    parser.error("--vid or --selftest")


if __name__ == "__main__":
    sys.exit(main())
