# m7 — gated fleet console

Read `ARCHITECTURE.md` first, then `PLAN.md`.

Phase 1a–2a are in this tree (G1, G2, G3). Nothing here is a safety
function. No ROS lives here. Phase 2b (the `fleet_cli` subcommand
registration) waits for the m6-ver2 track to close.

```
python3 -m pip install -r m7/requirements.txt
python3 -m pytest m7/tests -q
python3 m7/tools/check_m7_boundaries.py
python3 m7/console/approve.py list
python3 m7/console/approve.py approve <id>
python3 m7/console/approve.py reject <id>
```
