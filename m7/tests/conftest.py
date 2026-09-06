"""Put m7/ on sys.path so tests import gate and gateway as modules."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M7 = os.path.normpath(os.path.join(_HERE, ".."))
if _M7 not in sys.path:
    sys.path.insert(0, _M7)
