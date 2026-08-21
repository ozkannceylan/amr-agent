#!/usr/bin/env python3
"""The section 7 constants and the IEC primitives, imported from the one place
they were already transliterated: plc/forklift/double/logic.py (the M4 logic
double). One transliteration, one home — a divergence between that file and
SPEC.md section 7 is a bug there, and this re-export changes nothing about it.

Loaded by file path so neither tree needs to be a package.
"""

import importlib.util
import os

_LOGIC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "..", "..", "plc", "forklift", "double", "logic.py")

_spec = importlib.util.spec_from_file_location("amr_m5_logic_double", _LOGIC)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

K = _mod.K                          # section 3.3's constants, to the digit
Ton = _mod.Ton                      # the IEC TON, measured-period semantics
LIMIT = _mod.LIMIT                  # SCL LIMIT(MN, IN, MX)
HEARTBEAT_STALE_TIME = _mod.HEARTBEAT_STALE_TIME  # T#500ms, demo-cell section 3.3
