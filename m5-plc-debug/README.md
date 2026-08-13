# m5-plc-debug — the hand-debug chapter

Between the layered M5 and the rebuild in [`m5_ver2/`](../m5_ver2/), the
safety-PLC ↔ Gazebo loop was taken apart here and tested piece by piece
until every signal was understood. These four scripts are that record —
kept because `m5_ver2/` was built on what they proved, and its briefs
cite them.

| Script | What it isolated |
|---|---|
| `plc_bridge.py` | The PLCSIM Advanced API path: tag-name writes/reads against `PLC_2`, the tag set that later became the contract table |
| `microscan3.py` | The scanner field model: case → (PF, WF) radii, N-scan debounce, re-clear hysteresis — carried verbatim into the vehicle's field evaluation |
| `encoder.py` | The two-channel speed readings and the cross-check the F-program faults on |
| `world_sim.py` | The minimal Gazebo side the above were tested against |

Historical, working, not maintained. The living versions of these ideas
are in `m5_ver2/step5/ipc/` and the PLC facts in
[`m5_ver2/CLAUDE.md`](../m5_ver2/CLAUDE.md).
