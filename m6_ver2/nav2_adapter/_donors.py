"""_donors.py - where the untouched trees are, said once.

    python3 m6_ver2/nav2_adapter/_donors.py --selftest

THE SEAM, NAMED. AMR-DEC-006 freezes `m6/` and `m5_ver3/` byte for byte
in G1, so the adapter may neither be installed beside them nor copy
anything out of them. What is left is to IMPORT, and importing across
three sibling directories on a tree that is deliberately not a colcon
package (m6/tests/conftest.py's reason, unchanged) needs somebody to say
where they are. This file is that somebody, and it is the only one:

    m6/ipc          follower, stations, route, status_contract, nav_core
                    - the contract being reproduced, and the geometry
                      the leg classifier reads
    m5_ver3/nodes   cmd_vel_tricycle_core - the (v, w) -> (steer angle,
                    tread) inverse kinematics, IMPORTED and not copied:
                    a number that lives in two places is two numbers,
                    and so is an atan2
    m5_ver3/tools   map_register, evidence_core, drive_goal - the
                    committed registration with its md5 binding, the one
                    spelling of the world <-> map transform, and the
                    ClosingWatch this track's watchdog is a port of

THE ALTERNATIVE WEIGHED AND REJECTED was a thin re-export module per
donor - a `nav2_tricycle.py` whose whole content is
`from cmd_vel_tricycle_core import twist_to_tricycle`. A re-export is a
SECOND NAME for one function: the day the donor's signature changes, the
re-export still imports cleanly and every caller breaks one layer
further in, with a traceback that names the wrong file. One directory on
sys.path fails at import, by name, at the top of the stack.

NO ROS IS REACHED THROUGH ANY OF THIS. Every module named above keeps
its rclpy imports inside a shell or inside a function (`drive_goal`
imports rclpy inside `record`/`plan`, `follower` and `route` have none
at all), which is what lets this package's suite run on a python where
`import rclpy` fails.
"""
import argparse
import os
import sys

#: This package's own directory - m6_ver2/nav2_adapter.
HERE = os.path.dirname(os.path.abspath(__file__))
#: The repository root, two levels up. Derived and never configured:
#: a path that can be set is a path that can be set wrong.
REPO = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))

#: (directory, what it is for) in import order. The adapter's own
#: directory comes first so a name defined here always wins.
DONORS = (
    (HERE, "the adapter's own pure modules"),
    (os.path.join(REPO, "m6", "ipc"), "the m6 contract being reproduced"),
    (os.path.join(REPO, "m5_ver3", "nodes"), "the tricycle kinematics"),
    (os.path.join(REPO, "m5_ver3", "tools"), "the registration and the "
                                             "closing watchdog"),
)


class DonorError(RuntimeError):
    """A donor directory this package cannot run without is not there."""


def install():
    """Put every donor directory on sys.path. Idempotent.

    Called at import time by every pure module in this package, which is
    what makes `python3 m6_ver2/nav2_adapter/nav2_cmd.py --selftest` work
    from anywhere without a wrapper, a PYTHONPATH or a shell.
    """
    missing = [(path, why) for path, why in DONORS
               if not os.path.isdir(path)]
    if missing:
        raise DonorError(
            "the adapter cannot find {}: {}. m6_ver2/nav2_adapter is "
            "built on m6/ and m5_ver3/ standing beside it in the same "
            "checkout (AMR-DEC-006 - they are frozen, not vendored), so "
            "a copy of this directory on its own is not a thing that "
            "runs.".format(
                ", ".join(why for _, why in missing),
                ", ".join(path for path, _ in missing)))
    for path, _why in DONORS:
        if path not in sys.path:
            sys.path.insert(0, path)
    return [path for path, _ in DONORS]


install()


def _selftest():
    """Every donor import this package makes, made once, out loud."""
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    check("the repo root is two levels up from this file",
          os.path.isdir(os.path.join(REPO, "m6_ver2")))
    for path, why in DONORS:
        check("{} is on disk ({})".format(why, os.path.relpath(path, REPO)),
              os.path.isdir(path))
    try:
        import follower                                   # noqa: F401
        import route                                      # noqa: F401
        import status_contract                            # noqa: F401
        from stations import STATIONS                     # noqa: F401
        check("the m6 contract imports without ROS", True)
    except ImportError as exc:                            # pragma: no cover
        check("the m6 contract imports without ROS ({})".format(exc), False)
    try:
        import cmd_vel_tricycle_core                      # noqa: F401
        check("the tricycle kinematics import without ROS", True)
    except ImportError as exc:                            # pragma: no cover
        check("the tricycle kinematics import without ROS ({})".format(exc),
              False)
    try:
        import evidence_core                              # noqa: F401
        import map_register                               # noqa: F401
        import drive_goal                                 # noqa: F401
        check("the registration and the watchdog import without ROS", True)
    except ImportError as exc:                            # pragma: no cover
        check("the registration and the watchdog import without ROS "
              "({})".format(exc), False)
    check("rclpy was NOT dragged in by any of them",
          "rclpy" not in sys.modules)

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="where m6_ver2/nav2_adapter's donor trees are. This "
                    "file is a path seam; --selftest is the only thing "
                    "it does on its own.")
    parser.add_argument("--selftest", action="store_true",
                        help="prove every donor import works, no ROS")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a path seam; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
