# Report m3-35 — bridge session-lifecycle conformance

brief:               docs/briefs/m3-35-session-lifecycle.md
status:              done
invariants_touched:  none

## files_changed

| File | Change |
|---|---|
| `bridge/amr_bridge/opcua_side.py` | every await that touches the session routes **any** exception into `SessionBroken` via `_session_broken` (bridge defects excepted); `run()` gains a last-resort guard and outage accounting; new cycle step 0 `_verify_own_heartbeat` (heartbeat read-back → restart detection) and `_invalidate_write_cache`; `_input_path` records the rewrite |
| `bridge/amr_bridge/instrumentation.py` | `session_csv_path`, `EvidenceFileExists`; `Recorder` writes one file per session and opens with `"x"`, never `"w"`; 9 new counters |
| `bridge/amr_bridge/main.py` | logs the resolved per-session evidence path at start and at stop |
| `bridge/test_double/plc_test_double.py` | scaffolding **S5** `--warm-restart-file`: every node back to its start value in place, sessions left up (a CPU warm restart under a surviving session); `--observe-csv` follows the same one-file-per-session rule |
| `bridge/tools/check_session_lifecycle.py` | **new** conformance harness: owns the double's lifecycle, drives the bridge's own `PlcClient.run()`, 28 checks |
| `bridge/tools/check_connect_conformance.py` | prints the resolved evidence path instead of the stem |
| `bridge/config/bridge.yaml` | `evidence.csv_path` is a stem: `evidence/latency-latest.csv` → `evidence/latency-session.csv` (the word "latest" only made sense while the file was truncated) |
| `bridge/README.md` | new sections: one evidence file per session, and what happens when the link or the server goes away; the new harness; S5 |
| `bridge/test_double/README.md` | S5 row, and the S2 stem rule |
| `bridge/.gitignore` | `evidence/*-pid*.csv` — every generated session file carries a pid, so one rule covers all of them and no dated capture is hidden |
| `bridge/EVIDENCE_LIFECYCLE.md` | **new** dated capture of the run (see the note on the file split below) |
| `bridge/evidence/session-lifecycle-2026-07-28*.gz` | 5 artefacts: bridge CSV, harness transcript, double log, the double's 5 Hz view, the two-start transcript |

**File split, as instructed.** `EVIDENCE_LATENCY.md` and `EVIDENCE_SIGNAL_LOSS.md`
were not opened or edited; a sibling agent holds them. This work's capture is
`bridge/EVIDENCE_LIFECYCLE.md`, and it cross-references `EVIDENCE_LATENCY.md`
Section B as the PLCSIM capture that predates the read-back step.

## The three behaviours, and what proves each

All three are proven against the test double only. The harness refuses an
endpoint that looks like the commissioned instance, because it kills its server.
Reproduce with `bridge/tools/check_session_lifecycle.py` (28 checks, PASS, run
twice from a clean tree with the same result).

1. **In-flight request failure reconnects; the process never exits.** Proven
   twice. (a) The double `SIGKILL`ed under a running 50 ms cycle: the failure came
   out of a request the cycle had in flight (`read_errors 0→1`), the run loop kept
   running, nothing was published while disconnected, and the cycle resumed 0.9 s
   after the double returned. (b) The exact exception is pinned by injection:
   `asyncua`'s `send_request` re-raises an in-flight failure as a bare
   `Exception("Unhandled exception while sending request to OPC UA server")` when
   the socket state has not yet flipped, and that is the type that killed the live
   run. It is now routed by the raising step (`unexpected_session_errors 0→1`,
   `unrouted_cycle_errors` still 0) and the cycle resumed on a new session.
2. **A restarted server gets every input slot rewritten.** The signal it keys on
   is **`DemoCell/Link/BridgeHeartbeat`, read back once per cycle**: the bridge is
   the only client permitted to write it, so any value it did not write means the
   server's copy is not the one this session established. Exact inequality against
   the last write — not "lower than" (the counter wraps) and no timer. Proven in
   both flavours: with the session dropped (double killed and relaunched) and,
   the live case, with the session **surviving** (S5 warm restart, `reconnects`
   unchanged, so nothing but the read-back could have noticed). Detected 20–40 ms
   after the trigger, all 7 nodes rewritten in one cycle 43–61 ms after it, and
   verified by reading the double back over an **independent read-only session** —
   both stop circuits closed again. The heartbeat counter continued across the
   restart, as §8.1 requires.
3. **No evidence CSV is truncated.** The path is a stem; the file carries
   `-<UTC second>-pid<pid>`. Two real `run_bridge.py` starts with the same
   `--evidence-csv` produced two files, and the first one's md5 was identical
   before and after the second start. A name collision raises `EvidenceFileExists`
   rather than truncating, and the refused file keeps its rows.

**Cost of the extra read**, measured in the same run: cycle interval median
50.1 ms over 45–49 cycles with **0 overruns**, read-back median 0.64–0.79 ms. It
is recorded as a `read_rt BridgeHeartbeat` row, so `summarize_latency.py` reports
it beside the output read rather than the claim being asserted.

**No regression:** `check_write_allowlist.py` and `check_connect_conformance.py`
both re-run PASS against the double (the latter still measures the grant-derived
2.667 s keep-alive cadence). No new dependency. No logic added: the read-back
transports nothing, and the invalidation empties two dicts.

## open_questions

1. **`docs/interfaces/bridge-design.md` needs three edits I may not make**
   (interface agent): §2's cycle order now has a leading read-back step
   (`verify own heartbeat → read Output → publish → write Inputs → write
   Heartbeat`); §8.1's detection row should read "any exception from an await that
   touches the session", and the table needs a restart-detection row stating the
   heartbeat read-back and the write-cache invalidation; §9.2/§9.3 should record
   the `read_rt BridgeHeartbeat` interval and the one-file-per-session rule. Until
   that lands, `bridge/README.md` and `EVIDENCE_LIFECYCLE.md` are the only written
   statement of the new behaviour.
2. **The PLCSIM re-run is owner-outstanding.** Every figure here is the double's
   on loopback. The detection and repair latencies scale with the round trip, and
   `EVIDENCE_LATENCY.md` Section B's cycle figures predate the read-back step.
   `plc/demo-cell/SPEC.md` §12 item 7 depends on this behaviour and cannot be
   closed against the double.
3. **Root `.gitattributes` comment is now stale** (infra): it says "Tracked
   shebang files today: 1 `*.sh`, 7 `*.py`" and there are 8 `*.py` after
   `check_session_lifecycle.py`. The `*.py text eol=lf` rule already covers it, so
   nothing is broken — only the count. Related: the root `.gitignore` rule
   `bridge/evidence/*-latest.csv` no longer matches anything the code writes; the
   per-session rule in `bridge/.gitignore` replaces it. I left both in place.
4. **One residual, stated in the code and the evidence file rather than patched:**
   a warm restart that happens while the last written heartbeat was exactly the
   value the server reverts to (0) reads back as equal and is not detected. One
   value in 65 536; the next restart is caught, and a restart that drops the
   session is caught by the reconnect path.

next_suggested:      re-run `check_session_lifecycle.py`'s §2.4 equivalent against PLCSIM Advanced (owner) and have the interface agent fold open question 1 into `bridge-design.md` §2/§8.1/§9.
