# TODO

## owner (blocking)
- Elevated `w32tm /resync`, before any PLCSIM correlation. Correction to the earlier entry: w32time is running, startup type Manual, so Start-Service was never needed; only /resync requires elevation and a non-elevated run fails with 0x80070005. Separately the WSL guest is ~3.7 s ahead of the host and hwclock is not installed in the distro, so closing that gap needs `wsl --shutdown` once no agent is working inside WSL. Bridge latency uses monotonic_ns and is unaffected; WSL-to-PLCSIM timestamp correlation is not.
- PLC: implement the TIA Portal program and run PLCSIM Advanced; capture watch-table evidence for gate items (a) and (b) and fill Section B of bridge/EVIDENCE_LATENCY.md. Do not start before m3-12 lands — SPEC.md still specifies the superseded conflated reset.
- Hermes: define the component (which repo, how Telegram reaches it, what it may write over OPC UA) before M4 can be briefed.

## infra
- m3-07 WSL environment rebuild — in progress, unblocked. Gazebo Sim 8.11.0 is installed via the ROS vendor packages, so investigations 1 and 7 can now be answered. Done when the gz version and the headless behaviour are recorded against a real install.
- m3-08 WSL loop re-run — not yet issued, blocked on m3-07. Done when the cell, test double and bridge loop from bridge/README.md is re-run under WSL and WSL evidence sections are appended without disturbing the container evidence.

## plc
- m3-12 spec reset retarget — brief written, deliberately not issued (owner paused new work). Done when plc/demo-cell/SPEC.md reads 15 server-visible tags rather than 14 everywhere, PanelResetPressed is the reset device throughout, and no trace of the gesture-based start/reset conflation remains, with the reset still edge triggered and non-auto-resuming.

## interface
- m3-03e bridge-design staleness sweep — not yet issued. Three separate briefs have each found the document describing a pre-delivery state, so the remaining work is an audit rather than another single correction. Known: §11 records asyncua as absent and pending approval with a bare pip install path though it is approved and pinned at 2.0.1; and m3-11 reports six inputs becoming seven in five places, plus a signal-map row and a FALSE pre-first-publish default for the reset. Done when every section is checked against the delivered bridge/ artefacts and either corrected or confirmed, with the confirmation list in the report.

## bridge
- Reset contact bridge entry, found by m3-10. bridge/config/bridge.yaml has no /cell/panel/reset mapping and bridge/tools/cell_stimulus.py still drives three contacts. Done when the reset is bridged and stimulable with its pre-first-publish default false. A default of true would clear a latch at startup, the auto-resume CLAUDE.md §9 forbids.
- bridge/config/bridge.yaml evidence.csv_path points at the container path /home/user/amr-agent/..., found by m3-07. Done when the path is not machine-specific.
- bridge/README.md states the venv is /opt/amr-bridge-venv; on WSL /opt needs root and it landed at /home/ozkan/amr-bridge-venv. Done when the documented path matches what a non-root WSL user actually gets.

## verifier
- m3-06 verify M3 — done when the loop is independently re-run from committed instructions and the owner-executed remainder is stated explicitly. Run last, after m3-12 and m3-03e.

## carried forward
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
