# Brief m4f-10 — one-command start/stop for the Linux-side M4 stack

```
gate:                M4
agent:               infra (owner-approved 2026-07-30 in session)
goal:                one command starts the whole Linux-side M4 stack (Gazebo
                     arena, vehicle nodes, bridge, HMI) and one command stops
                     exactly what it started, documented in the root README.
invariants_touched:  none — the script launches existing processes with their
                     existing configs; it adds no data path and no logic.
inputs:              [sim/scenarios/forklift_commissioning.md §1 (the stack
                      composition), sim/README.md, bridge/README.md,
                      hmi/README.md, agv/README.md and the TODO note that
                      agv/forklift/launch/vehicle.launch.py is a standalone
                      rig — in the composed stack the two vehicle scripts run
                      directly, docs/LESSONS.md entries on gz process
                      matching (pgrep -af, GZ_PARTITION), venv
                      (/opt/amr-bridge-venv) and *.sh eol=lf]
deliverable:         stack.sh at the repo root, plus a short "Run it" section
                     in README.md documenting `./stack.sh start|stop|status`
done_when:           `./stack.sh start` brings up every Linux-side process of
                     the forklift_commissioning.md §1 composition in the
                     right order, writing one PID file per process under a
                     runtime dir; `./stack.sh stop` terminates exactly those
                     PIDs (SIGTERM first, bounded wait, then SIGKILL) and
                     never blanket-pkills; `./stack.sh status` lists each
                     component up/down; a second `start` while running
                     refuses instead of double-spawning (the double-forklift
                     failure of 2026-07-29); the README section states in one
                     line that the PLC side (TIA/PLCSIM) is started
                     separately on the owner's Windows machine and which
                     bridge config the script uses (the live bridge.yaml as
                     configured — the script never edits configs); the script
                     is committed executable and .gitattributes covers *.sh
                     with eol=lf (verify, add the line only if missing).
forbidden:           [editing any config under bridge/, hmi/, sim/ or agv/;
                      editing sim/README.md (a parallel brief holds it);
                      changing launch files; adding dependencies; deciding
                      rehearsal-double orchestration (note it as a possible
                      later flag in the report instead); committing (the
                      orchestrator commits)]
```

Notes: read the §1 composition from the scenario document rather than
reconstructing it from memory; if a component's start command in the docs
disagrees with what exists in the tree, report the disagreement instead of
inventing a start line. Environment guards: the script should fail with a
clear message when ROS 2 / Gazebo / the bridge venv are absent (it will run
on the owner's WSL, not only in this container), and it must not assume a
display (arena GUI vs headless: honour the same flags the bringup already
uses; default to the GUI case the owner uses for showcases, with a
--headless passthrough if the underlying launch supports it).

Report to docs/reports/m4f-10-stack-launcher.md (uncommitted, standard
format).
