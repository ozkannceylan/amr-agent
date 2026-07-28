# Brief m3-37 — M3 gate verification

gate:                M3
agent:               verifier
goal:                a ruling on whether M3's four exit criteria are met, with every unmet part named
invariants_touched:  none
inputs:              [docs/roadmap.md M3 row (the criterion as written), plc/demo-cell/SPEC.md §11, bridge/EVIDENCE_LATENCY.md (Sections A, B parts 1-3, C), bridge/EVIDENCE_SIGNAL_LOSS.md, bridge/EVIDENCE_CONNECT.md, bridge/EVIDENCE_LIFECYCLE.md, bridge/evidence/ (the committed artifacts), plc/demo-cell/evidence/watch-table/ (70 owner captures, timestamp-named), docs/reports/m3-2x and m3-3x, docs/LESSONS.md, docs/PLAN.md, docs/TODO.md, git log]
deliverable:         docs/reports/m3-37-gate-verification.md
done_when:           each of the four exit items carries an explicit met / not-met ruling with the artifact that establishes it; the two knowingly-open items are ruled on by name (do they block closure or not); and the report ends with a single unambiguous verdict — pass, pass-with-findings, or fail — and, if it closes, the exact sentence docs/roadmap.md should carry
forbidden:           [modifying any file except the deliverable report, committing, connecting to any endpoint, running Gazebo or the bridge, re-measuring anything, softening a finding to let the gate close, closing the gate in roadmap.md yourself (state the sentence, the orchestrator writes it)]

## The criterion, verbatim from docs/roadmap.md

> All four are demonstrated and recorded: (a) Gazebo sensor state is visible as
> PLC input bits in a TIA watch table, (b) PLC output bits drive the Gazebo
> actuator, verified visually, (c) latency and update rate are measured and
> written down, (d) signal-loss behaviour is defined and tested — what the PLC
> sees when the bridge stops, and what the equipment does.

Rule against **that** text, not against §11's thirteen-then-fourteen step list.
§11 is the procedure someone chose for demonstrating the criterion; a step that
was never run does not automatically unmet an exit item, and a step that passed
does not automatically meet one. Say which is which.

## What you must weigh explicitly

1. **The build history.** The gate was demonstrated across several program
   builds in one day (the m3-05 build, the three-delta build, the
   PRESENCE_FILTER fix, a full re-download, the ±0.10 narrowed build, and the
   §6.8 rebuild). Section B parts 1-3 label them. Rule on whether the exit
   items are established **against a single coherent build** or assembled
   across builds, and whether that assembly is legitimate for this criterion.
2. **The two knowingly-open items.** T4.11's reaction re-record with a
   per-session CSV (row 15) and T4.11b (row 16, blocked on a fault-injection
   facility that does not exist, SPEC §12 item 6). Both concern belt-feedback
   plausibility, which is a defence added *during* the gate, not part of the
   four criteria as written. Rule whether they block closure.
3. **4.9b's status.** Part 3 records the bridge-restart form as a pass and the
   CPU-cold-start form as not yet run, so 4.9b is not a pass in full. Decide
   what that means for item (d) — a monitored-reset property is arguably
   inside (d)'s "what the equipment does".
4. **The owner captures as instruments.** Items (a) and (b) are defined
   against the TIA watch table, and the only Group 4 instrument in this gate
   is those 70 captures. Verify by opening the ones that matter that they show
   what the evidence claims. Name the captures you relied on.
5. **Honesty of the record.** Part 3 lists six corrections it made to its own
   brief, including that the orchestrator's "build E" was really a later
   build, that no 20 ms instrument exists, and that one attribution rests on
   arithmetic over an unsampled window. Check those admissions hold and that
   nothing elsewhere in the evidence over-claims.
6. **Tracking coherence and attribution**, as in m3-23: PLAN, TODO, roadmap
   and the report directory agree; no AI/tooling mention; layer boundaries
   held; the publication redaction did not damage any evidence chain.
