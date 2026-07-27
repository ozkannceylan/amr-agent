# TODO

## infra
- m3-07 WSL environment rebuild — BLOCKED on owner elevation. ROS 2 Jazzy and asyncua 2.0.1 verified; Gazebo Harmonic absent and apt needs a sudo password the agent cannot supply, so investigations 1 (gz version) and 7 (headless run) are unanswered. Done when those two are answered against a real Gazebo install.
- m3-09 repo line-ending policy — not yet issued, held until m3-05 stops writing plc/ so a renormalize cannot stage another agent's work in progress. Done when a root .gitattributes checks *.sh out as LF on Windows, install.sh executes in WSL, and WSL-side git reports the tree clean.
- m3-08 WSL loop re-run — not yet issued, blocked on m3-07 elevation and m3-09. Done when the cell, test double and bridge loop from bridge/README.md is re-run under WSL and WSL evidence sections are appended without disturbing the container evidence.

## owner (blocking, this session)
- Elevated apt, unblocks m3-07/m3-08: sudo apt-get update && sudo apt-get install -y ros-jazzy-gz-sim-vendor ros-jazzy-ros-gz
- Elevated w32time, before any PLCSIM correlation: Start-Service w32time; w32tm /resync. Host time service is stopped; the WSL wall clock steps ~2.73 s every 30 s. Bridge latency uses monotonic_ns and is unaffected, but WSL-to-PLCSIM timestamp correlation is currently meaningless.

## bridge (queued, found by m3-07)
- bridge/config/bridge.yaml evidence.csv_path points at the container path /home/user/amr-agent/...; m3-08 needs it parameterised or overridden. Done when the path is not machine-specific.
- bridge/README.md states the venv is /opt/amr-bridge-venv; on WSL /opt needs root and it landed at /home/ozkan/amr-bridge-venv. Done when the documented path matches what a non-root WSL user actually gets.

## interface
- m3-03d bridge-design residual staleness — not yet issued, deliberately held until m3-05 stops reading the file. Done when §9.4 names the delivered artefact latency-<date>.csv.gz rather than .csv, and §12 open item 7 (20 Hz cadence) is marked closed to match EVIDENCE_LATENCY.md §A.4, which records the expectation met with 0 overruns.

## sim + interface (queued, blocked on an owner decision)
- Reset device for the demonstration cell. The panel has Start, Stop and process stop only, so m3-05 had to conflate reset onto PanelStartPressed, separated by gesture and by state. CLAUDE.md §9 requires a separate monitored reset. Done when either the owner accepts the conflation in writing, or sim/ adds a /cell/panel/reset NO contact, docs/interfaces/opcua-nodes.md §9.3 adds PanelResetPressed, and plc/demo-cell/SPEC.md is amended to use it. Do not start before the owner rules.

## verifier
- m3-06 verify M3 — done when the container-side loop is independently re-run from committed instructions and the owner-executed remainder is stated explicitly.

## owner (open points, not delegated)
- PLC: implement the TIA Portal program and run PLCSIM Advanced; capture watch-table evidence for gate items (a) and (b) and the PLCSIM latency section of bridge/EVIDENCE_LATENCY.md.
- Hermes: define the component (repo, Telegram path, OPC UA client role) before M4 can be briefed.

## carried forward
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
