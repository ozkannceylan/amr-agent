# Report m4f-08 — commissioning scenarios and evidence plan

```
brief:               docs/briefs/m4f-08-commissioning-scenarios.md
                     (as amended by c834726 and 92c5949)
status:              done
files_changed:       sim/scenarios/forklift_commissioning.md      (new)
                     sim/scenarios/forklift_stimulus.py           (new)
                     sim/scenarios/run_forklift_rehearsal.py      (new)
                     sim/README.md                                (arena +
                                                                   scenarios
                                                                   section,
                                                                   Contents)
                     docs/reports/m4f-08-commissioning-scenarios.md (this file)
invariants_touched:  none
open_questions:      five, below — two for plc/, one for hmi/, one for bridge/,
                     one recorded in sim/
next_suggested:      rule finding 1 (the raised-carriage cap: limit or scale)
                     before the owner runs T5.3, since the two forms predict
                     different numbers for the same step.
```

## What was delivered

`sim/scenarios/forklift_commissioning.md` is the M4 gate procedure: the five
roadmap criteria (a)–(e) as owner-runnable scenarios, each with its exact process
start order and `GZ_PARTITION`/`ROS_DOMAIN_ID` values, the operator's steps at
the HMI, the node, topic and `SPEC.md` §9 watch-table row that proves it, and the
evidence artifact to capture — per-session bridge CSV, watch-table PNG, recording
segment. `SPEC.md` §11 owns the six test procedures; this file restates none of
them as an alternative and redefines no criterion. T5.4 is written in the
corrected held-reset K4 form of 6ff866c, including the enable release and
re-assert of 5.4.9. T5.6 is carried as an appendix because it is not one of the
five criteria; it was not rehearsed and says so.

Two helpers: `forklift_stimulus.py` (owner-runnable — hold a control set at the
HMI, move the aisle crate, transcribe `/state`, plus a fenced-off plant smoke
check) and `run_forklift_rehearsal.py` (the agent-side harness that produced the
rehearsal record). No `--once` publish appears in either, or anywhere in the
procedure.

`sim/README.md` gains the arena and scenarios section m4f-03's report requested,
plus its Contents rows.

## The rehearsal

**All five scenarios were rehearsed through the full loop** — HMI → PLC logic
double (20 ms, SPEC §7) → bridge with `rehearsal-forklift.yaml` → arena and back
— in the brief's process order, with a fresh `GZ_PARTITION` and `ROS_DOMAIN_ID`
per scenario (`m4f08reh1`…`5`, domains 71–75). One run, 2026-07-29
10:18:02Z → 10:22:33Z, exit 0: **79 harness checks, 79 passed** (20 + 13 + 9 +
23 + 14). Five per-session bridge CSVs, 1.1–3.3 MB each; every scenario ended
`pgrep -af final: clean` and `listeners 4850/8090: none`.

Every figure in the scenario file is quoted as the harness or the process printed
it and is labelled REHEARSAL EVIDENCE. **PLCSIM was never contacted**: the
harness names one endpoint, `opc.tcp://127.0.0.1:4850`, and the double refuses to
start on 4840. Nothing observed against a double is evidence for the gate, which
closes on the owner's PLCSIM run and its recording.

Steps worth naming because they could have been skipped: **5.4.10 ran** (the
scan interrupted at its source by finishing the arena's `ros_gz_bridge` by exact
pid; the latch formed 0.67 s later from the window test), and **5.5.5's P6 guard
is reproducible** (the HMI's HTTP server starts before its OPC UA session, so a
post landing in that window arms the reset before the first write cycle). The
T5.5 number was taken between two readings of one clock — the HMI's own
per-session CSV `monotonic_s` and the bridge's `read_rt` `t_start_ns`, both
`CLOCK_MONOTONIC`, which is system-wide on Linux: **638 ms** from the last
advancing beat to the setpoint reading `0.0`, against a 600 ms `HMI_STALE_TIME`;
four rehearsals span 638–692 ms.

## Open questions

1. **`SPEC.md` §11 step 5.3.4 contradicts §§7 and 9** on the raised-carriage cap.
   The Pass line predicts `≈+0.20 m/s` for a demand of 0.2 (the cap as a *limit*);
   §9's Group 3 row says `demand × 0.30` and §7 builds it (the cap as a *scale*),
   which gives `+0.060 m/s`. Observed `+0.060`, and `hmi/EVIDENCE_HMI.md` §B.4
   independently recorded the same form. Both satisfy criterion (c); which is
   intended is a `plc/` ruling and was not taken here.
2. **`SPEC.md` §11 step 5.1.1's `ForkliftObstacleStopActive FALSE` is not
   guaranteed** under the specified start order. `obstacle_zone.py` publishes its
   no-data sentinel until its first scan arrives, and whether that reaches an
   evaluating PLC is a race with the bridge's R3 rule. Both outcomes observed;
   a third run showed the guard that bounds it (R3 withheld the heartbeat, so
   §6.1 suspended plant-input evaluation and a 6.29 s sentinel changed nothing).
   Neither outcome is a defect. Requested of `plc/`: a §11 revision stating both,
   with the check on `ForkliftObstacleInStopZone` before the reading is taken.
3. **The HMI's reset cannot be held from its page** — one click is one write
   cycle, while §11 5.4.4–5.4.7 need it standing across the moment the zone
   clears. It is producible only by re-posting to `/control` above the write
   rate, which `forklift_stimulus.py hold` does. Requested of `hmi/`: a
   hold-capable RESET control, so the gate step runs entirely from the operator's
   screen.
4. **No bridge configuration exists for the gate run.** `bridge/config/bridge.yaml`
   is cell-only by choice and `rehearsal-forklift.yaml` points at the double.
   The forklift group against the commissioned endpoint is a one-file addition
   after the TIA read-back, and it is a precondition of T5.1. Requested of
   `bridge/`.
5. **`sim/README.md` still calls the deferred vehicle work M5** in three places,
   while `docs/roadmap.md` under ADR 0008 numbers it M6. Left alone rather than
   half-fixed: the three occurrences are outside this brief's section and a
   partial sweep would make the file disagree with itself. Needs its own brief.

## Scope notes

- Nothing outside `sim/` and this report was written. `plc/forklift/SPEC.md`,
  `agv/forklift/`, `bridge/config/rehearsal-forklift.yaml`, `hmi/` and
  `docs/roadmap.md` were read as contracts and not edited; the HMI was driven
  only through its loopback HTTP endpoints, and no code of another layer is
  imported by either script.
- **No dependency was added.** Both scripts use the standard library only.
- Per-session bridge and HMI CSVs were written to `/tmp/amr-m4f08/`, outside the
  repository, because `sim/` may not write into `bridge/` or `hmi/` and a 20 Hz
  stream is quoted rather than stored. The scenario file is the committed record.
- The rehearsal ran in WSL2 Ubuntu 24.04.4 on the `/mnt/c` checkout, ROS 2 Jazzy,
  `gz sim 8.11.0`, llvmpipe software rasterisation, `asyncua 2.0.1`. The evidence
  is qualified by that environment; the owner's PLCSIM run is a different one.
