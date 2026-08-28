"""Put the node directories on sys.path so the tests can import them.

This tree is deliberately not a package (m5_ver2/CLAUDE.md: no colcon
package, plain files run with python3), so there is nothing to install and
the tests reach the modules by path instead.
"""
import os
import sys

# The suite runs as one vehicle; per-vehicle behaviour is tested through
# contract(vid), which is pure. f1 is arbitrary.
os.environ.setdefault("VEHICLE", "f1")

# THE SUITE GETS ITS OWN DDS DOMAIN, and it is set, not defaulted: the
# live stack runs domain 96 and PROOF's runbooks export 96 in the
# operator's shell, so a setdefault would inherit it and let a test's
# publisher reach a driving truck. 89 is nobody's.
os.environ["ROS_DOMAIN_ID"] = "89"

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in ("ipc", "hmi", "windows"):
    _path = os.path.normpath(os.path.join(_HERE, "..", _sub))
    if _path not in sys.path:
        sys.path.insert(0, _path)
