# m7 — gated fleet console

Read `ARCHITECTURE.md` first, then `PLAN.md`.

Phase 1a (pure gate + schemas) and Phase 1b (gateway, G1/G2) are in
this tree. Nothing here is a safety function. No ROS lives here.

```
python3 -m pip install -r m7/requirements.txt
python3 -m pytest m7/tests -q
python3 m7/tools/check_m7_boundaries.py
```

Phase 2a (`console/approve.py`, G3) is next. Phase 2b waits for the
m6-ver2 track to close.
