# Report m3-26 — live loop against the commissioned PLC

brief:               docs/briefs/m3-26-live-loop-run.md
status:              done
files_changed:
  - bridge/EVIDENCE_LATENCY.md      (Section B rewritten with the run; header and §B.0/§B.0.3 reconciled)
  - bridge/EVIDENCE_SIGNAL_LOSS.md  (pointer to §B.7 so the PLCSIM repeat is not silently missing)
  - bridge/README.md                (tools table; new section on observing the PLC without a watch table)
  - bridge/config/bridge.yaml       (opcua.endpoint -> opc.tcp://192.168.53.1:4840; the only config change)
  - bridge/tools/observe_plc.py     (NEW: read-only 15-node observer, test scaffolding)
  - bridge/evidence/latency-2026-07-27-plcsim-main.csv.gz
  - bridge/evidence/latency-2026-07-27-plcsim-caseA2.csv.gz
  - bridge/evidence/latency-2026-07-27-plcsim-caseD.csv.gz
  - bridge/evidence/latency-2026-07-27-plcsim-l7.csv.gz
  - bridge/evidence/plc-observe-2026-07-27-plcsim-main.csv.gz
  - bridge/evidence/plc-observe-2026-07-27-plcsim-l7.csv.gz
invariants_touched:  none
open_questions:
  - Two PLC program defects were found and NOT fixed; both are plc/ work
    (EVIDENCE_LATENCY.md §B.13). F1: ProductPresentAtSensor never asserted
    despite a genuine 1.8 s beam block at 0.540 m, so no transport cycle ever
    reached its dwell and every one ran to the +2.40 m soft limit instead.
    F2: signal-loss case D went undetected for 26 s, because the frozen
    read-back held a NON-ZERO speed (blinding D1) and SPEC.md §7 part 3 arms
    PositionRef once at the start of motion and never re-arms it, so D2's
    freeze-band comparison can never be satisfied mid-motion.
  - Gate exit items (a) and (b) are NOT claimed. They are defined against the
    TIA watch table; the OPC UA-side equivalent is recorded and labelled as the
    weaker instrument it is. Both stay owner-outstanding, with six other items,
    in §B.12.
  - Signal-loss case C, and T4.8/T4.9b, were not performed: each requires
    stopping or cold-starting the owner's CPU, which the brief forbids.
  - bridge/tools/observe_plc.py is a new file in bridge/. It was needed because
    an agent cannot open a watch table. If the orchestrator would rather it not
    be committed, Section B's figures survive without it (the CSVs are here);
    only their reproducibility does not.
next_suggested:      A plc brief to fix F1 and F2 in plc/demo-cell/SPEC.md, then one owner-run pass with the watch table open to close (a) and (b).

---

## Step 0 — connectivity, done first, and it passed

The brief's stop condition did not trigger. WSL2 reaches the Windows-side
PLCSIM adapter without any workaround:

```
ping 192.168.53.1        3/3 received, rtt 0.510/0.650/0.835 ms, ttl 254
TCP connect :4840        open
asyncua connect + read   15 nodes, ns 3 (Siemens) and 4 (http://DemoCell)
```

The path is WSL2 `eth0` → Hyper-V `vEthernet (WSL)` → host route → `Ethernet 2`
(192.168.53.241, on-link) → 192.168.53.1. `Find-NetRoute` and `Get-NetRoute`
confirm the only route to `192.168.53.0/24` is that on-link one, so **Tailscale
is not in the measurement path** — invariant 8 evidenced from the routing table
rather than asserted. That closes one of the two items the brief expected to
stay owner-outstanding; the CPU's configured scan cycle genuinely does stay
outstanding.

The first read also reproduced the owner's cold-start reading exactly:
`BridgeLinkOk` False, `CellProcessStopActive` True, `CellResetRequired` True,
`ConveyorSpeedCommand` 0.0.

## Did the loop run end to end?

**Yes.** Gazebo → bridge → OPC UA → the running S7-1500 program → back to the
Gazebo actuator, closed, repeatedly, for 502 s of connected time across four
bridge sessions. A start press in ROS produced `ConveyorSpeedCommand = +0.15`
from the PLC and the belt moved in Gazebo; a stop circuit opening produced
`0.0` and the belt stopped, measured six times at a median of **46.8 ms**
(§B.5). 20.00–20.02 Hz on every session, **0 cycle overruns, 0 write errors,
0 read errors, 0 reconnects**.

What did **not** work is the part of the PLC program above the transport layer:
the cycle never reached its dwell, and one of the four signal-loss reactions
did not fire. Those are findings about the program, recorded as such.

## The run, segment by segment — this is also the video's narrative

One Gazebo GUI session, one continuous panel stimulus, one continuous read-only
observer, T1 → T4 in ascending complexity.

| Segment | What is visible |
|---|---|
| **1 · T1** (0–36 s) | Panel at rest; heartbeat starts 0.8 s after connect; `BridgeLinkOk → True`. Each contact toggled alone and each input node follows. A start press is **refused** while a latch is pending. The reset's rising edge clears the cold-start latches. Belt still. |
| **2 · T2** (36–68 s) | The money shot: start → `ConveyorSpeedCommand 0.0 → +0.15` → **the belt moves and carries the product**. It runs past the photo-eye (F1) to +2.4123 m, where the **soft-limit abort** stops it and demands a reset. |
| **3 · T2.5–2.8** (68–132 s) | Interlock drop mid-motion, then **30 s untouched with nothing moving** (no auto-resume), then reset — *and still nothing moves* — then a separate start on the other button, which re-homes the belt at −0.15. |
| **4 · L7 + T4.9** (132–220 s) | Repeated interlock drops. Then the stuck reset: `reset` held `true` **across** a latch never clears it (18 s), and only the new rising edge after release does. |
| **5 · case A** (220–300 s) | `kill -9` the bridge. Heartbeat freezes at 4537, `BridgeLinkOk → False` 0.50 s later. Bridge restarts; **the cycle does not**. Reset, then start. |
| **6 · case B** (300–356 s) | `SIGTERM`. Program behaviour identical to A. |
| **7 · case D** (356–392 s) | `kill -9` the **simulation**. The scene freezes while the heartbeat keeps advancing and the PLC keeps commanding +0.15 into a dead cell — the defect, on screen. |

## Video — operational artifact, NOT in the repo

```
C:\Users\ozkan\AppData\Local\Temp\claude\C--Users-ozkan-projects-amr-agent\96ed9196-53d1-466d-b9c4-05bd13397dcc\scratchpad\plc-drives-cell.gif
```

Animated GIF, **4.5 MB, 820×471, 406 frames, 28.4 s playback** (captured at
2 fps over 415 s, every 2nd frame kept, so playback is ≈7× real time). A single
representative still is beside it as `plc-drives-cell-still.png` (14 KB).

Verified, not assumed: reopened with Pillow and walked frame by frame —
**406 frames**, **0 blank or near-uniform frames**, and 129 of 405 consecutive
pairs differ (the rest are the genuinely static stretches, chiefly the 30 s
no-auto-resume wait, which is a *criterion*, not dead air). The belt slab and
the product box are visibly in different positions across the run.

Method: Gazebo's `/gui/screenshot` was not attempted — a prior agent established
it lies under WSLg — and ffmpeg/scrot/import/grim are absent. Option (b) was
used: repeated `System.Drawing` `CopyFromScreen` of the maximised WSLg Gazebo
window from Windows, assembled with Pillow. No frame files were left behind and
none are in the repo.

## Measurements captured (all in EVIDENCE_LATENCY.md Section B)

* **§B.2 connect** — both namespaces resolved by URI to **3** and **4**,
  `browse path: Objects/3:ServerInterfaces/4:DemoCell`, 15 nodes, all DataTypes
  verified. **Session timeout: requested 10 000 ms, granted 10 000 ms** — the
  brief expected a 30 000 ms grant and a 10.000 s keep-alive; the actual derived
  keep-alive is **3.333 s**. The two observations reconcile: 30 000 ms is the
  CPU's cap and a request under it is honoured unchanged.
* **§B.3 rate** — 20.00 / 20.01 / 20.02 / 20.01 Hz, `cycle_overruns` **0** on
  all four sessions. Session #1 has no counter tail and no `disconnect` row
  because it was SIGKILLed — correct case-A behaviour, and the sharpest A-vs-B
  artefact in the evidence.
* **§B.4 statistics** — count/min/median/p95/max for **all seven inputs**
  (Section A predates the reset). Real-CPU `L2` medians 1.07–1.31 ms against the
  double's 0.9–1.0 ms, so §A.7's "lower bound" caveat holds with a small margin.
* **§B.5 L7** — 6 samples, **min 36.4, median 46.8, p95 47.7, max 47.7 ms**,
  derived post-hoc from rows the bridge already records (no code change), with
  the 0–50 ms poll quantisation stated as the upper bound it makes it.
* **§B.6 startup rule** — heartbeat withheld until all **seven** inputs carry a
  real sample, at every one of four connects.
* **§B.7 signal loss** — A, B, D repeated against the live program; C not
  possible. `HEARTBEAT_STALE_TIME` measured at **0.50 s** three times, so
  SPEC.md open item 1 closes at 500 ms with ~9 beats of margin.
* **§B.8 session hold** — **11.79 s** after SIGKILL, **0.0 s** after SIGTERM,
  against a granted 10 000 ms.

## Discipline notes

* Only `opcua.endpoint` changed to make the run work. No code behaviour was
  altered, no test was made to pass, nothing outside `bridge/` was written.
* TIA Portal was not driven, nothing was downloaded, the TIA project was not
  touched, and no node outside the seven `DemoCell/Input/` nodes and
  `Link/BridgeHeartbeat` was ever written. The observer is read-only.
* The test double was never started; `CurrentSessionCount` read 1 before the
  bridge connected, which corroborates it.
* Isolated with `GZ_PARTITION=m326live` and `ROS_DOMAIN_ID=93`; only processes
  this run started were killed, and none is left running.
* Not committed. The working tree carries the changes for the orchestrator to
  commit by pathspec.
