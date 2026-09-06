# m7 — gated fleet console

Read `ARCHITECTURE.md` first, then `PLAN.md`.

Phase 1a–3 are in this tree (G1, G2, G3, G4). Nothing here is a safety
function. No ROS lives here. Phase 2b (the `fleet_cli` subcommand
registration) waits for the m6-ver2 track to close. Phase 4 is the
live plant.

```
python3 -m pip install -r m7/requirements.txt
python3 -m pytest m7/tests -q
python3 m7/tools/check_m7_boundaries.py
./m7.sh start          # gateway + console against the m6 broker
python3 m7/console/approve.py list
python3 m7/console/approve.py approve <id>
./m7.sh stop
```

The console client is config-driven (`m7/console/client.yaml`) and
tests use a scripted model, never a live API call.
