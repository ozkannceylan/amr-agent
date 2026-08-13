# m3-03e — bridge design staleness sweep

brief:               docs/briefs/m3-03e-bridge-design-staleness-sweep.md
status:              done
files_changed:       [docs/interfaces/bridge-design.md, docs/reports/m3-03e-bridge-design-staleness-sweep.md]
invariants_touched:  none
open_questions:
  1. "§2's diagram label `7 /cell/* topics` cannot be reconciled to one reading, so it was
      left alone. Read as topics it was wrong before the reset (the bridge touched 6: five
      subscriptions plus `cmd_speed`) and is exactly right after it (7). Read as signals it
      was right before (map rows 1–7) and is now one short (8). Changing it would be a
      guess at the original intent; `bridge/README.md` carries the identical string and is
      outside this agent's write access."
  2. "§5.1 still says m3-04 `may run a subscription-based comparison as supplementary
      evidence`. It did not (`EVIDENCE_LATENCY.md` §A.6). Left as written: it is a
      permission, not a promise, and the primary poll path is unaffected."
  3. "`plc/demo-cell/SPEC.md` §8, case A, still reads `the six inputs froze at their last
      written values`. plc/'s file, outside this agent's write access — and m3-12 is
      editing it now, so it may already be handled."
next_suggested:      Verifier pass over bridge-design.md once m3-12 and m3-13 land, so the seven-input statement is checked against the committed bridge/ and plc/ files rather than their intended end state.

---

## Concurrency, and what "confirmed" means in this report

m3-13 (bridge) and m3-12 (plc) were both working while this sweep ran. At the start of
the pass only `docs/TODO.md` was modified; by the end, ten files under `bridge/` and
`plc/demo-cell/SPEC.md` were. Per the brief, **`bridge/config/bridge.yaml`,
`bridge/tools/cell_stimulus.py` and `bridge/README.md` are described by their intended
end state** (m3-10 and m3-11 reports, m3-13 brief), not by their momentary contents. The
same treatment was extended to `bridge/amr_bridge/*.py`, `bridge/requirements.txt`,
`bridge/test_double/plc_test_double.py` and `bridge/tools/check_write_allowlist.py`,
which turned out to be in flight too.

Concretely: every "seven inputs" statement in the corrected document describes the end
state m3-13 delivers. The committed `bridge/` still knows six, and its `INPUT_KEYS`,
`BOOL_INPUT_KEYS` and config schema were read in that state. Behavioural claims
(slot depth, write allowlist, cycle order, no-auto-resume, instrumentation) were checked
against the committed code, which m3-13 is not chartered to change.

The two evidence files were treated as immutable inputs. **No measured number was
altered, and none was introduced except by quoting its source**: the one figure added is
`EVIDENCE_SIGNAL_LOSS.md` §A.4's `sessions 1 → 0` within 2 s, quoted in that file's own
words. `EVIDENCE_LATENCY.md` §A.1's "14 nodes resolved" and §A.3's "all six
DemoCell/Input nodes" are pre-reset measurements and log captures; they are correct for
the run that produced them and were not touched.

## Section by section

| Section | Verdict | Change, or what it was checked against |
|---|---|---|
| Header / authority | corrected | "This document **is** written before any bridge code … **is** implemented against" → past tense; the bridge exists. Authority lines checked against `opcua-nodes.md` §9 and `sim/README.md` § "Demonstration cell (M3)", both present |
| §1 What the bridge is, and is not | confirmed | `main.py` (one process: rclpy executor thread + asyncio client), `opcua_side.py` (client only, no listener anywhere), `bridge/README.md`'s "must not access" list. The `bridge/` layer wording was settled by m3-03c and not re-opened |
| §1.1 NO-LOGIC RULE | corrected | Cross-reference fixed: "field selection/addressing (§4.2)" → **§4.5** (§4.2 is the PLC→cell table; §4.5 is Addressing detail). Each violation row re-checked against `ros_side.py` and `opcua_side.py` — no threshold, latch, debounce, filter, clamp or shutdown zeroing exists |
| §2 Process shape | corrected | Config row now also names session and reconnect housekeeping (§8.1) and the diagnostics poll rate. `bridge.yaml` carries all three, and §2's flat "no timers" otherwise reads as forbidding the reconnect interval that §8.1 explicitly licenses. Concurrency, slots, overrun rows confirmed against `main.py`, `slots.py`, `opcua_side.run()`. Diagram label left — open question 1 |
| §3 Session and address-space rules | corrected | "the **six** `DemoCell/Input/` nodes" → seven. Direction, namespace-by-URI, per-session NodeId resolution and the startup DataType check confirmed against `opcua_side._connect` / `_verify_types`; the single write choke point against `config.WRITE_ALLOWLIST`, `PlcClient._write` and `tools/check_write_allowlist.py` |
| §4 intro | corrected | "**Six** nodes the bridge writes" → Seven |
| §4.1 Cell → PLC | corrected | New row 5: `/cell/panel/reset` → `Input/PanelResetPressed`, `Bool`/`Boolean`, no conversion, on-change + refresh on connect, with the edge/hold/latch-set named as PLC content. Stop and process stop renumbered 6 and 7. One sentence added recording that the order follows `opcua-nodes.md` §9.3's polarity grouping (NO, NO, NC, NC), which is m3-11's decision, not a new one. Row content taken from §9.3, §9.9 and `sim/README.md`'s `PanelResetContact` row |
| §4.2 PLC → cell | corrected | Row number 7 → 8 (forced by the new row). Content confirmed against `opcua_side._output_path`: read, widen, publish, no shaping |
| §4.3 Bridge's own node | corrected | Row number 8 → 9. `UInt16`, increment, wrap confirmed against `_heartbeat_path` (`(self._heartbeat + 1) % 65536`) and its position last in `_cycle` |
| §4.4 Read-only, applied to nothing | confirmed | Node list matches `bridge.yaml` `nodes.diagnostics` exactly (5 `Status/*` + `BridgeLinkOk`); `_poll_diagnostics` logs and records them and returns — no value reaches a decision |
| §4.5 Addressing detail | confirmed | `ros_side._on_joint_state` matches `belt_joint` by name and takes no sample if absent; `_on_scan` uses `ranges[0]`, skips on empty, and passes `inf`/`NaN` through unchanged with a WARN and a counter. Narrowing happens only at the `ua.VariantType.Float` write |
| §4.6 ROS 2 QoS | confirmed | `KEEP_LAST` depth 1 profiles in `ros_side.__init__`; the `/cell/panel/*` row already covers the reset with no wording change. Startup QoS logging exists (`log_endpoint_compatibility`) and its output is in `EVIDENCE_LATENCY.md` §A.4 |
| §5 Update model | corrected | Contacts "(4, 5, 6)" → "(4, 5, 6, 7)" and "all **six** inputs" → seven; output path 7 → 8; heartbeat 8 → 9. The cyclic-analog / on-change-contact split confirmed against `_input_path`'s two loops |
| §5.1 Why poll rather than subscribe | corrected | "An **eight-node** address space" → "The **fifteen-node** `DemoCell/` address space of `opcua-nodes.md` §9". Counted from §9: 7 Input + 1 Output + 5 Status + 2 Link. Eight matched neither the delivered space (14 nodes resolved, `EVIDENCE_LATENCY.md` §A.1) nor the current contract; it appears to have counted only the loop nodes. The argument (a small address space needs no server-side sampling) is unchanged |
| §6 intro | corrected | "no value for the **three** panel contacts" → four |
| §6.1 The rule (R1–R5) | corrected | R3 "all **six**" → all seven; R4 "refreshes all **six** inputs" → seven. R1 confirmed against `_input_path` (`if sample is None: continue` — no default written, ever), R2 against the per-key loop, R5 against `_output_path` publishing only inside a successful read |
| §6.2 What the PLC can rely on | corrected | "every one of the **six** input nodes" → seven |
| §6.3 Fail-safe start values | corrected | **New `PanelResetPressed` = `FALSE` row**, with the reason stated at the row: a `TRUE` start value asserts a reset no operator pressed and clears a latch at startup, the automatic resume CLAUDE.md §9 forbids. The row also records that R1 produces the same result before the first publish — the bridge writes nothing, so the node holds the start value. Matches `opcua-nodes.md` §9.3 (fail state 0) and `SPEC.md` §3.1 |
| §7.1 Heartbeat semantics | confirmed | Counter form, `UInt16`, wrap at 65535 → 0, and "written after the cycle's input writes" confirmed against `_heartbeat_path` and the `_cycle` ordering; observed advancing at 20 Hz in `EVIDENCE_LATENCY.md` §A.3 and `EVIDENCE_SIGNAL_LOSS.md` §D |
| §7.2 Reaction is PLC content | confirmed | No timer, threshold or reaction exists anywhere in `bridge/`; the staleness criterion and `BridgeLinkOk` are in `plc/demo-cell/SPEC.md` §6.1 as this section says they must be |
| §7.3 Failure modes A–D | corrected | Case A's OPC UA session cell rewritten: `EVIDENCE_SIGNAL_LOSS.md` §A.4 measured the double dropping to `sessions 0` within 2 s after `SIGKILL`, because a process death on a live host closes the TCP socket at OS level. The session/subscription-timeout wording now applies only to a host or network loss, where no FIN/RST arrives. The section's conclusion is unchanged and the evidence says the deviation strengthens it. B, C and D confirmed line by line against the same file |
| §7.4 Expectations for the PLC | corrected | Item 1 "the **six** input values" → seven. Items 2 and 3 confirmed against `SPEC.md` §6.4 (setpoint driven to 0.0) and §6.7 (monitored edge-triggered reset; a returning heartbeat restarts nothing) |
| §8.1 OPC UA reconnect | corrected | "refresh all **six** inputs" → seven. Detection, fixed-interval bounded backoff, per-session NodeId re-resolution and heartbeat non-reset confirmed against `opcua_side.run()` / `_connect` and `EVIDENCE_SIGNAL_LOSS.md` §C.1/§C.4. The "not reset across a process restart **if it can be avoided**" hedge correctly covers the delivered per-process counter, which restarts at 1 (§A.5) |
| §8.2 ROS side restart | confirmed | `slots.py` has no clear or expiry, so slots retain their last value as stated; the consequence is `EVIDENCE_SIGNAL_LOSS.md` case D |
| §8.3 The command path never resumes (N1–N5) | confirmed | `_output_path` publishes only a value read in the same cycle; `_handle_signal` and `_disconnect` write nothing on the way out. Measured in `EVIDENCE_SIGNAL_LOSS.md` §C.2 (nothing published during the outage) and §C.5 (first value after reconnect is the server's current command) |
| §8.4 Residual: the belt during an outage | confirmed | `EVIDENCE_SIGNAL_LOSS.md` §A.3 and §C.3 record exactly this: the belt ran on at its last commanded speed with no bridge in existence |
| §9.1 Clock rules | confirmed | `time.monotonic_ns()` throughout `opcua_side`/`ros_side`; `Sample.sim_ns` is recorded and never differenced against a monotonic reading; the one sim-time interval is `ActuationProbe`'s L6, labelled `clock="sim"` |
| §9.2 What is measured | confirmed | The L1 slot-take definition m3-03c settled matches `_record_write`, which emits both `L1` and the literal `L1cs`. L4 is reported as a bound and L7 as unmeasured, per `EVIDENCE_LATENCY.md` §A.6. Not re-opened |
| §9.3 How it is instrumented | confirmed | `instrumentation.Recorder` appends rows and flushes periodically with no in-loop aggregation; percentiles are computed afterwards by `tools/summarize_latency.py`; instrumentation is unconditional. Run length, product traverses and the process-stop press are in `EVIDENCE_LATENCY.md` §A.1–A.2 |
| §9.4 Evidence location | corrected | Added the delivered `bridge/EVIDENCE_SIGNAL_LOSS.md`, which the table omitted, noting its capture is test-double/in-container and its PLCSIM repetition is item 6 of the latency file's Section B. "The evidence file has two clearly separated sections" → "The **latency** evidence file", now that two files are listed. The `.csv.gz` spelling m3-03d settled was left untouched |
| §9.5 What cannot be measured without the real PLC | confirmed | Matches `EVIDENCE_LATENCY.md` §A.7 item for item, and the "establishable with the double alone" list matches what §A.2–A.4 in fact established |
| §10 Test double | corrected | "verified automatically **in this container**" → "on any machine that can run the cell". WSL is now a target platform and the container is not the only environment (LESSONS 2026-07-27). S1/S2/S3 scaffolding labels, the `bridge/test_double/` location, the start values and the never-alongside-PLCSIM rule confirmed against `test_double/README.md` |
| §11 Dependencies | corrected | Four changes, all one defect: `asyncua` recorded as **approved and installed**, pinned `asyncua==2.0.1` per `bridge/requirements.txt` (ADR 0005 D2); the heading's "require owner approval" replaced; the "if the owner declines, m3-04 must be re-briefed" clause removed; the bare `pip install` install path replaced by the mechanism — a `--system-site-packages` venv so one interpreter imports both `rclpy` and `asyncua`, with the container and WSL locations given as examples and the location called an environment fact rather than a design property. "No benefit at eight nodes" → "at this address-space size" |
| §12 items 1, 2, 5, 7 | confirmed | 1 (ADR 0005) and 2 (§6) re-read and still correct; 5 confirmed against `_record_write`, which timestamps before narrowing; 7 left exactly as m3-03d closed it |
| §12 item 3 (`NaN`/`inf`) | corrected | Bridge behaviour unchanged; the PLC-side consequence is **closed** by `SPEC.md` §6.2, which tests the range against its physical window before any process comparison so a `NaN` is a fault rather than "no product" |
| §12 item 4 (case D) | corrected | **Closed** on the PLC side: `SPEC.md` §6.6 takes the recommendation and latches `ConveyorDriveFault` on a non-zero command with a near-zero measured speed |
| §12 item 6 (Real setpoint, not a coil) | corrected | **Closed** by `SPEC.md` §6.4: the setpoint is gated by driving it to zero in a mandatory unconditional `ELSE` |
| §12 item 8 (stale sim heading) | corrected | No longer outstanding: `sim/README.md` line 164 now reads "Navigation scenario (M5, deferred)" |

**24 corrected, 14 confirmed.** Diff: 48 insertions, 36 deletions in one file, of which the
two new table rows and the §11 rewrite account for most. No section was restructured, no
design decision was added, and no item m3-03c or m3-03d settled was re-opened.

## What the enumerated list missed

m3-11 named five places where six becomes seven. The independent sweep found the count
asserted in **nine statements across eight locations**: §3 writable set, §4 intro, §5's
contacts row (twice — the row reference and the refresh count), §6 intro (as "three panel
contacts"), §6.1 R3, §6.1 R4, §6.2's guarantee box, §7.4 item 1, and §8.1's reconnect row.
Two of those — §3 and §4's intro — were nowhere in the list, and the §6 occurrence was
spelled as a contact count rather than a node count, so a search for "six" would have
missed it. Beyond the count, the reset also required a new row in §4.1 and a new row in
§6.3, and forced the renumbering of §4.2, §4.3 and three rows of §5.

---

## lessons_candidates

2026-07-27 | m3-11 listed the five places where "six inputs" becomes seven, and the sweep searched for that string | The count was asserted in nine statements across eight locations, two of them absent from the list, and one spelled as "three panel contacts" so no search for the number would have found it | When a cardinality changes in a contract document, search for the *thing being counted* and for its synonyms (nodes, inputs, contacts, signals), not for the numeral; a numeral search cannot find a count written in another unit

2026-07-27 | A design document described its subject's size as "an eight-node address space" | Nothing tests a number in prose, so it stayed at eight while the contract went to fourteen and then fifteen nodes, and the sentence was still being read as current three briefs after delivery | A size or count stated in prose carries the section of the contract it was counted from, so a reader can re-derive it; an unsourced number in a design document ages invisibly

2026-07-27 | A design document's failure-mode table predicted that a crashed client's session survives until the session timeout | The delivered evidence measured the opposite for the common case — a SIGKILL on a live host closes the socket at once — and the deviation sat unreconciled in the evidence file because reporting it was out of the reporting brief's scope | A deviation recorded in an evidence file is a defect in the document it deviates from; the sweep that closes it belongs in the plan, not in whichever brief happens to notice
