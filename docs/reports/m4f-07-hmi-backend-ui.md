# Report m4f-07 — commissioning HMI backend and UI

```
brief:               docs/briefs/m4f-07-hmi-backend-ui.md (as amended, c834726)
status:              done
files_changed:
  - hmi/hmi_server.py                        (new) backend: OPC UA client, write cycle, HTTP server
  - hmi/static/index.html                    (new) operator page, one offline file
  - hmi/config.yaml                          (new) commissioned CPU — owner-run, never run here
  - hmi/config-double.yaml                   (new) bridge test double, port 4847
  - hmi/config-logic-double.yaml             (new) PLC logic double, port 4850
  - hmi/tools/check_hmi_writes.py            (new) evidence harness, pass A
  - hmi/tools/check_hmi_teleop_loop.py       (new) evidence harness, pass B
  - hmi/EVIDENCE_HMI.md                      (new) both recorded runs
  - hmi/evidence/*.csv, *.log                (new) raw evidence, 9 files
  - hmi/README.md                            (edited) two sections: what is here now, how to run it
  - docs/reports/m4f-07-hmi-backend-ui.md    (new) this report
invariants_touched:  none
open_questions:      six, listed below
next_suggested:      Owner reads the Forklift/ subtree back out of TIA Portal
                     (opcua-nodes.md section 10.2 step 6), then runs this HMI
                     against PLCSIM on config.yaml.
```

## What was built

One process: an OPC UA **client** of the PLC and a loopback HTTP server for one
operator's browser. `asyncua` and the standard library; no new dependency, no web
framework, no ROS, no `gz`, nothing imported from `bridge/` or `fleet/`. It writes
the five `Forklift/Hmi/` requests and `Forklift/Link/HmiHeartbeat`, all six every
100 ms cycle regardless of change, heartbeat last; it reads
`Forklift/Input/Output/Status/` and `HmiLinkOk` at 5 Hz for the display and
applies them to nothing.

No interlock, latch, sequencing or actuator output is implemented here. Two
timers exist and both govern the client's **own cycle**: the 10 Hz cadence and
the 5 Hz contractual floor of `opcua-nodes.md` §10.8 H2.

## Evidence

Two passes, `hmi/EVIDENCE_HMI.md`, both on 2026-07-29, both against loopback
doubles. The live PLCSIM endpoint was never contacted; both harnesses refuse a
non-loopback endpoint and `hmi/config.yaml` was not run.

- **Pass A**, bridge test double on 4847: **40 checks, no failures.** Includes the
  §10.4 every-cycle policy proven by overwriting a node from another session and
  watching the HMI repair it in 98 ms; the reset pulse spanning exactly one
  heartbeat value; a reconnect after which the counter continued 56 → 74 while
  the server restarted from 0, and the requests came back at rest rather than at
  the standing `+1.00` demand; and both stop paths.
- **Pass B**, PLC logic double on 4850: **33 checks, no failures.** Lamps and
  metrics actually move — the boot-window `HmiLinkOk` FALSE, the monitored reset,
  the enable edge, the fork-height speed cap reducing 0.60 → 0.180 m/s, the
  obstacle latch dropping every setpoint to 0.0 with the operator's request still
  standing at 0.60, §10.7's release-and-reassert conflation, and `HmiLinkOk`
  going FALSE 650 ms after the HMI was stopped with the PLC then stopping the
  machine on its own.
- The page was additionally loaded and driven in a real browser engine; the
  observed values are transcribed in EVIDENCE_HMI.md §C.

## Corrections and findings worth the orchestrator's attention

1. **A node name in the dispatch was wrong, and §10 was right.** Both the brief's
   `done_when` and the dispatch message named `HmiDriveRequest`. The authoritative
   BrowseName in `docs/interfaces/opcua-nodes.md` §10.4 is **`HmiTractionRequest`**
   — *Traction* rather than *Drive*, decided in m4f-01 because it pairs each
   request with the output it feeds. The implementation followed §10, which both
   documents named as authoritative, and the correction was confirmed
   mid-task by the coordinator. No code was written against the wrong name.
2. **`DOWN` was initially a state no operator could see.** The first
   implementation exited the process after a terminal backend fault, taking the
   HTTP server with it — so the banner the brief asks for could show `CONNECTED`
   and `RECONNECTING` but never `DOWN`. Fixed: after the write cycle stops for
   good the page keeps being served with the banner reading `DOWN` and the reason,
   until the operator stops the process.
3. **The first pass-B run mis-attributed a link drop.** The harness waited for the
   HMI's exit synchronously, which stalled its own bridge pump long enough for
   `BridgeHeartbeat` to go stale too; both link verdicts then dropped together and
   "stopping the HMI stops the machine" was no longer attributable to the HMI
   link. The harness now awaits the exit without blocking its event loop. This is
   an instrument defect, not a product one, but it is the shape of thing that
   silently weakens evidence and is recorded for LESSONS.

## Open questions

1. **§10.8 H5 and the brief's final zeros write.** H5 says the HMI "writes no
   farewell value, zeroes nothing on shutdown"; the brief requires the heartbeat
   to stop "after one final zeros write attempt". These were reconciled rather
   than chosen between, and the reconciliation should be ruled on by
   `docs/interfaces/`: a **clean shutdown** writes no farewell value at all (H5
   honoured exactly, and it is the better demonstration — the server is left
   holding a live-looking demand under a stopped counter, which is what the
   watchdog exists to catch); a **backend fault or dropped session** fires the
   deadman first, so what the single final write attempt carries is "the current
   state of its controls", which is the wording H5 itself permits on reconnect. If
   the interface owner reads H5 as forbidding the fault-path write too, it is one
   branch to delete.
2. **A crashed browser leaves the last requests standing.** The page returns the
   controls to rest on release, blur, hide and unload, which covers everything the
   browser can report. A hard crash or a pulled cable does not fire those events,
   and the backend keeps writing the last joystick value under a live heartbeat
   until the PLC's own watchdog acts — which it will not, because the HMI link is
   healthy. Closing this needs a **browser-liveness policy** (a window and a
   reaction) that no document currently states. Inventing one here would have been
   a timer over an operator's presence, which is the sort of decision this layer
   does not take. **Requested of `docs/interfaces/`**, as a §10.8 H-rule.
3. **`HMI_STALE_TIME` is still derived from the 5 Hz floor, not from a
   measurement.** §10.8 P3 says the constant is three worst-case write periods and
   is re-derived if the HMI's measured worst case exceeds 200 ms. The p95 measured
   here is `100.90 ms` — but that is WSL loopback against a double, not the
   commissioned cell. The measurement that P3 actually asks for is one taken
   against PLCSIM, at commissioning.
4. **The steer request's engineering range lives in HMI code.** `1.31` rad is
   §10.4's declared range, held as a named constant beside its citation rather
   than as a config key, so it cannot be retuned as if it were a deployment
   setting. It is the one interface number this layer must know in order to
   express a joystick position in the unit the node declares. If
   `docs/interfaces/` would rather publish it as a node or move the scaling
   elsewhere, that is an interface decision and this is where it currently sits.
5. **No config-file dependency was added, at the cost of a hand-written parser.**
   `config.yaml` is read by a strict subset-of-YAML loader in `hmi_server.py`
   (comments, `key: value`, indent nesting, block lists, JSON-style inline lists)
   because PyYAML would have been a second pip package and the brief allows only
   `asyncua`. It refuses anything it does not understand, naming the line. If the
   owner would rather add PyYAML to a `hmi/requirements.txt`, roughly sixty lines
   come out.
6. **One flag in the product file is test scaffolding.** `--inject-fault-after-s`
   raises inside the write cycle so the backend-fault path is exercised rather
   than assumed; it is labelled TEST SCAFFOLDING in the CLI help and in the
   evidence, and it is never used in a demonstration run. The bridge kept its
   scaffolding in the double instead, but this layer has no double of its own.

## Requested of other layers

- `docs/interfaces/` — the two rulings in open questions 1 and 2, and a view on 4.
- Nothing else. No file outside `hmi/` and this report was written.
