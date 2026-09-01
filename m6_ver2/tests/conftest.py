"""Put the adapter and its donor trees on sys.path.

m6_ver2 is deliberately not a colcon package, exactly as m5_ver3 and m6
are not (m6/tests/conftest.py's reason, unchanged): plain files run with
python3, so there is nothing to install and the tests reach the modules
by path.

NO ROS IS IMPORTED FROM ANYWHERE THIS FILE REACHES, and that is the
whole point of the pure-core split the adapter is written to. Every
module under nav2_adapter/ is arithmetic; the rclpy shell
(nav2_adapter_node.py, A-T9) keeps its ROS imports inside itself. So
this suite collects and passes on the Windows python the owner runs
pytest under - the one where `import rclpy` fails and nine of m6's own
test files therefore cannot be collected at all.

THE DONOR DIRECTORIES ARE NOT LISTED HERE. nav2_adapter/_donors.py is
the one place that says where m6/ipc, m5_ver3/nodes and m5_ver3/tools
are; this file puts the adapter on the path and then imports that seam,
which installs the rest. A second list here would be a second answer to
the same question, and it would be the one that kept working after the
first one broke.
"""
import os
import sys

# The suite runs as one vehicle; per-vehicle behaviour is pure and is
# tested through arguments. f1 is arbitrary, and it is set for the same
# reason m6/tests/conftest.py sets it: status_contract reads it.
os.environ.setdefault("VEHICLE", "f1")

# THE SUITE GETS ITS OWN DDS DOMAIN even though nothing here talks to a
# network - m6/tests/conftest.py's rule, kept because the day a shell
# test appears is the day an inherited domain reaches a driving truck.
os.environ["ROS_DOMAIN_ID"] = "89"

_HERE = os.path.dirname(os.path.abspath(__file__))
_ADAPTER = os.path.normpath(os.path.join(_HERE, os.pardir, "nav2_adapter"))
if _ADAPTER not in sys.path:
    sys.path.insert(0, _ADAPTER)

# The seam, imported for its side effect: it installs m6/ipc,
# m5_ver3/nodes and m5_ver3/tools, so a test module may import a donor
# (follower, nav_core, drive_goal) before it imports the adapter module
# it is about - which is the order that reads best in a test file.
import _donors                                            # noqa: E402,F401
