"""Every process this stack starts is a process `stop` can find - as a
test, because the day it was not, it cost a measurement session.

WHAT THIS LOCKS. `m5v3.sh`'s `spawn` records the pid of the `ros2 run`
WRAPPER, and that wrapper FORKS the real executable: two processes per
node, and the pidfile knows about one of them. `stop`'s second pass - the
SWEEP over `tools/_common.sh`'s `M5V3_PATTERNS`, filtered by `ours()` - is
what catches the other. A child whose executable no pattern nominates is
therefore ORPHANED by a `stop` that prints "down." and exits zero.

MEASURED, 2026-08-27, when F3 Task 3 added `localization_slam_toolbox_node`
to `start()` and not to that list. NINE of them accumulated across nine
bringups, every one still publishing `map` -> `odom` on domain 97 out of a
world that no longer existed. What it looked like from the outside was two
completely different faults: an EKF that "never came up" - its topic lost
in a graph carrying nine stale participants - and a localiser answering
0.659 m from its seed, BIT-IDENTICALLY, on three consecutive bringups,
which reads exactly like the snap-relocalisation pathology
docs/reports/m5v3-04 predicts for that arm. Neither was real.

WHY IT IS A TEST AND NOT A COMMENT. `tools/_common.sh` already carries the
maintenance obligation in prose ("a process added to m5v3.sh's start() is
added HERE, or stop orphans it and still prints down.") and the obligation
was still missed. A list is the one kind of duplicate that fails silently:
nothing breaks, the stack just quietly does not go down.

NO ROS, NO GAZEBO AND NO RUNNING STACK: this reads two files off disk.
"""
import os
import re

import pytest

yaml = pytest.importorskip("yaml")

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _patterns():
    """The M5V3_PATTERNS array, as the shell spells it."""
    with open(os.path.join(_M5V3, "tools", "_common.sh"),
              encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"^M5V3_PATTERNS=\((.*?)\)\s*$", text,
                      re.DOTALL | re.MULTILINE)
    assert match, "tools/_common.sh no longer defines M5V3_PATTERNS"
    return re.findall(r'"([^"]+)"', match.group(1))


def _config():
    with open(os.path.join(_M5V3, "config.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


#: Every child `m5v3.sh start` spawns through `ros2 run`, as
#: (dotted config key of the PACKAGE, dotted key of the EXECUTABLE), and
#: the flag that brings it up. A child added to that script is a row
#: added here.
SPAWNED = [
    ("rf2o.package", "rf2o.executable", "--rf2o"),
    ("fuse.package", "fuse.executable", "--fuse"),
    ("localization.map_server.package", "localization.map_server.executable",
     "--localize amcl"),
    ("localization.amcl.package", "localization.amcl.executable",
     "--localize amcl"),
    ("localization.slam.package", "localization.slam.executable",
     "--localize slam"),
]


def _dotted(config, key):
    node = config
    for part in key.split("."):
        node = node[part]
    return str(node)


def _nominated(name, patterns):
    return [p for p in patterns if p in name]


@pytest.mark.parametrize("package_key,executable_key,flag", SPAWNED)
def test_every_spawned_child_is_nominated_by_a_pattern(
        package_key, executable_key, flag):
    # EITHER NAME WILL DO AND THAT IS THE POINT. `ros2 run` forks, so the
    # wrapper's command line reads `ros2 run <package> <executable>` and
    # the node's own reads <prefix>/lib/<package>/<executable>: a pattern
    # matching either string is on BOTH command lines. What may not
    # happen is neither.
    config = _config()
    package = _dotted(config, package_key)
    executable = _dotted(config, executable_key)
    patterns = _patterns()
    assert _nominated(package, patterns) or _nominated(executable, patterns), (
        "{} spawns {}/{} and no pattern in tools/_common.sh nominates it. "
        "`stop` would kill the `ros2 run` wrapper out of the pidfile, leave "
        "the node itself running, and print \"down.\"".format(
            flag, package, executable))


def test_the_localisation_node_is_nominated_by_its_EXECUTABLE():
    # AND NOT BY `slam_toolbox`, WHICH IS DELIBERATE. That package name is
    # also on the OFFLINE mapper's command line - tools/build_map.sh runs
    # sync_slam_toolbox_node on isolation.map_ros_domain_id - and a
    # pattern that nominated it would lean the whole safety of the sweep
    # on ours() rather than on the pattern. ours() would in fact spare it
    # (the replay carries no GZ_PARTITION), and a sweep that is one
    # environment variable away from killing an unrelated build is not
    # the design this file argues for.
    config = _config()
    patterns = _patterns()
    executable = _dotted(config, "localization.slam.executable")
    mapper = _dotted(config, "map.slam.executable")
    assert executable in patterns
    assert not _nominated(mapper, patterns)


def test_the_two_static_transforms_share_one_pattern():
    # The IMU's mount and the nav lidar's are two processes of one
    # executable; one pattern finds both, which is why there is one.
    assert "static_transform_publisher" in _patterns()


def test_no_pattern_is_empty_or_whitespace():
    # An empty pattern matches every process on the machine, and only
    # ours() would then stand between the sweep and the rest of the
    # system.
    for pattern in _patterns():
        assert pattern.strip() == pattern and pattern.strip()
