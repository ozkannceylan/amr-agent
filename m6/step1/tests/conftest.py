"""Put the module directories on sys.path so the tests can import them.

This tree is deliberately not a package (m6/CLAUDE.md carries the m5_ver2
house rule: plain files run with python3), so the tests reach the modules by
path. The step 5 SOURCE ipc goes on the path too - stations.py is the one
home for station truth and the tests read the real one, never a copy. The
source and not the deploy, because a fresh clone has no deploy and the tests
must run on any machine.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in ("../vda", "../fleet", "../../../m5_ver2/step5/ipc"):
    _path = os.path.normpath(os.path.join(_HERE, _sub))
    if _path not in sys.path:
        sys.path.insert(0, _path)
