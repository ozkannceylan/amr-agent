"""_common.py - refuse in one voice and read config.yaml, for the PYTHON
side of this track. IMPORTED, never executed: it has no main.

    import _common
    CFG = _common.load_config("wheel_odometry", REQUIRED_KEYS)

WHY IT EXISTS, AND IT IS tools/_common.sh's OWN ARGUMENT. That file was
written because m5v3.sh and rtf_probe.sh each carried a copy of the YAML
walk, a copy of refuse() and a copy of the path to ROS, and "two copies of
a MECHANISM drift the same way two copies of a VALUE do - the first one to
be fixed is the one that is right". F1 Task 3 adds two PYTHON entry points
that need the same three things, so they get one file too rather than a
copy each. The mechanism lives here; every value still lives in
config.yaml.

IT REFUSES IN THE SAME VOICE AS THE SHELL, deliberately character for
character: an operator reading logs/ has one refusal format to learn, and
whether the thing that refused was written in bash or in python is not
information they need. Every refusal names the CHECK that said no and the
FILE that owns the answer, because a bare traceback gives neither.

IT RESOLVES config.yaml FROM ITS OWN LOCATION, so a caller cannot point it
at another tree's config by getting its own path arithmetic wrong -
__file__ inside an imported module is that module, whatever imported it.
That is _common.sh's BASH_SOURCE trick, spelled in python.

WHAT IT DOES NOT DO, AND WHY. There is no source_ros() counterpart here.
A python process cannot source a shell script into its own environment,
and it does not need to: by the time this module is imported the caller is
already running under a python that either has rclpy on its path or does
not. m5v3.sh sources ROS before it spawns the node, which is the layer
that can.
"""
import os
import sys

import yaml

_TOOLS = os.path.dirname(os.path.abspath(__file__))
M5V3 = os.path.normpath(os.path.join(_TOOLS, os.pardir))
REPO = os.path.normpath(os.path.join(M5V3, os.pardir))
CONFIG = os.path.join(M5V3, "config.yaml")


def refuse(tool, check, owner, *lines):
    """Say no, name the check and the file that owns it, and exit 1.

    The continuation lines are indented under the tool's own name so a
    refusal reads as one block however it is spelled - _common.sh's
    refuse() computes the same padding the same way.
    """
    pad = " " * (len(tool) + 2)
    out = ["{}: REFUSED at check '{}'".format(tool, check),
           "{}owned by: {}".format(pad, owner)]
    out.extend("{}{}".format(pad, line) for line in lines)
    sys.stderr.write("\n".join(out) + "\n")
    sys.stderr.flush()
    raise SystemExit(1)


class Config(object):
    """config.yaml, already checked for the keys the caller named.

    Values are fetched by their DOTTED name and converted at the point of
    use, so a value that is not a number is refused with the key that
    holds it rather than raised as a ValueError from four frames down.
    """

    def __init__(self, tool, data):
        self.tool = tool
        self.data = data

    def refuse(self, check, owner, *lines):
        refuse(self.tool, check, owner, *lines)

    def raw(self, dotted):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                self.refuse("config.yaml defines " + dotted, CONFIG,
                            "the parse succeeded, so the key is missing or "
                            "renamed, not unreadable")
            node = node[part]
        return node

    def s(self, dotted):
        return str(self.raw(dotted))

    def f(self, dotted):
        value = self.raw(dotted)
        try:
            return float(value)
        except (TypeError, ValueError):
            self.refuse(dotted + " is a number", CONFIG,
                        "it reads {!r}".format(value))

    def i(self, dotted):
        value = self.raw(dotted)
        try:
            return int(value)
        except (TypeError, ValueError):
            self.refuse(dotted + " is a whole number", CONFIG,
                        "it reads {!r}".format(value))


def load_config(tool, required_keys):
    """Read config.yaml and check every key the caller says it reads.

    EVERY KEY A SCRIPT READS IS CHECKED BY NAME AFTER THE PARSE, which is
    _common.sh's rule and exists for its reason: a config.yaml that
    parses but has been reorganised under a node would otherwise reach
    the first callback and fail there, in the middle of a run, with a
    KeyError naming a dict nobody but this file has heard of. Checked
    here it is refused by its DOTTED name before anything starts, which
    is what the operator has to go and edit.

    MAINTENANCE OBLIGATION, the same one the shell scripts carry: a key
    read below is a key listed in the caller's REQUIRED_KEYS.
    """
    try:
        with open(CONFIG, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        refuse(tool, "config.yaml is readable", CONFIG, str(exc))
    if not isinstance(data, dict):
        refuse(tool, "config.yaml is a mapping", CONFIG,
               "it parsed to {}".format(type(data).__name__))
    cfg = Config(tool, data)
    for key in required_keys:
        cfg.raw(key)
    return cfg
