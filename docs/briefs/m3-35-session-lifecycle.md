# Brief m3-35 — bridge session-lifecycle conformance

gate:                M3
agent:               bridge
goal:                the bridge survives what the live run threw at it: an in-flight request failure reconnects instead of killing the process, a server restart triggers a full slot rewrite, and no evidence CSV is ever truncated by a restart
invariants_touched:  none
inputs:              [bridge/ (code and test double), docs/LESSONS.md (2026-07-28 rows), docs/reports/m3-33* and m3-34* (read only, may still be uncommitted — use LESSONS and this brief as the requirement source), docs/interfaces/bridge-design.md §8]
deliverable:         bridge client code, test double and README updated as one conformance change, proven against the test double
done_when:           a recorded test-double run shows all three behaviours — (1) the double killed mid-read: the bridge logs the failure, enters the §8.1 reconnect path and resumes on the double's return, process never exits; (2) the double restarted with reverted values: the bridge detects the restart (heartbeat node reverted below its last-written value, or session loss — state which signal it keys on) and rewrites EVERY input slot in the first cycle of the new session, verified by reading the double's values back; (3) two consecutive bridge starts given the same --evidence-csv argument produce two files (a per-session suffix or refusal — never truncation), with the README documenting the new behaviour
forbidden:           [adding process logic (thresholds, latches, timers beyond connection management), changing the OPC UA node set or bridge.yaml semantics beyond what the CSV naming needs, connecting to the live PLCSIM endpoint, editing files outside bridge/, adding dependencies]

## The three findings, as recorded (LESSONS 2026-07-28)

1. **Reconnect crash.** A CPU download dropped the session mid-read;
   `_output_path`'s `read_value` raised through `send_request` and the process
   died before the reconnect path could run. Catch in-flight request failures
   wherever the 50 ms cycle touches the session, route them into the same
   reconnect that connect failures use, and keep the instrumentation counters
   honest about the gap.
2. **Write-on-change cache vs server restart.** A CPU warm restart reverted
   all inputs to start values; the bridge's change-gated writes never repaired
   the ones whose slot values had not changed, so the PLC read open stop
   circuits for minutes. On restart detection, invalidate the write cache and
   rewrite every slot that has a real sample. SPEC §12 gained item 7 for this
   (m3-34) — the guard's guarantee depends on it.
3. **Evidence CSV truncation.** --evidence-csv truncates at every start; seven
   restarts erased a day of 20 Hz data. One file per session, deterministic
   naming, and the README updated so no future run repeats it.

Test each against the double only; the double may need a restart-with-reverted-
values mode — build it as scaffolding, clearly marked, no PLC logic.
