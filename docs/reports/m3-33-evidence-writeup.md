# Report m3-33 — the 2026-07-28 live run, written into the evidence documents

brief:               docs/briefs/m3-33-evidence-writeup.md
status:              done
files_changed:       bridge/EVIDENCE_LATENCY.md (+903 / −10), bridge/EVIDENCE_SIGNAL_LOSS.md (+247 / −19) — one logical change, **not committed**
invariants_touched:  none

---

## What was written

`EVIDENCE_LATENCY.md` Section B now has **two parts**. Part 1 (2026-07-27,
m3-26) is untouched except for its heading, which now says "part 1", and two
forward-pointer blockquotes added to §B.7 and §B.12 so the older accounting cannot
be read as the current one. **No m3-26 figure was changed, deleted or restated.**

Part 2 (§B2.0 – §B2.14) is the 2026-07-28 owner session, with every one of
Section B's nine items either filled or explicitly owner-outstanding with a
reason, a step-by-step T4 roster with a verdict per step, and a disposition of all
thirteen of §B.12's rows by number plus eight new ones.

`EVIDENCE_SIGNAL_LOSS.md` gained the **PLCSIM section item 6 requires**, beside
the container run rather than instead of it: all four cases against a CPU running a
program, with both runs' figures labelled by day and build, D split into its
at-rest and mid-motion sub-cases, and the reset behaviour a test double has no
program to show. Its opening blockquote was reframed (its m3-26 figures left
intact) and its closing "what none of this establishes" paragraph now points at
the new section instead of asking for it.

## The measurement the brief asked me to derive

**Freeze to reaction = 2.301 s**, from `latency-2026-07-28-plcsim-t1t4.csv.gz`:

```
last ConveyorBeltPosition write carrying a new value   t_end_ns=79555975237383  0.9636000372489671
                             (previous write            t_start_ns=79555927354297  0.9630000372251254)
ConveyorSpeedCommand 0.15 -> 0.0, server acknowledged  t_end_ns=79558275899123
```

`ConveyorDriveFault` is **not** timestamped in the CSV — it appears only in the
1 Hz `diagnostics` rows, which carry no clock — so the reaction is timed by the
20 Hz `read_rt` row for the command the fault zeroes. Corroborated three ways: the
1 Hz diagnostics bracket the fault between rel 629.655 and 630.705; the 5 Hz
observer reproduces the whole event independently at **2.207 s**; and 2.301 s lies
inside `SPEC.md` §6.6.2's specified window [≈2.1 s, 3.2 s], which is the only
available evidence about *which* term fired, since the frozen speed read-back was
0.1500000059 (D1 blind by construction) and no watch-table capture exists for the
event. **The transcript's 2.79 s is recorded as the transcript's coarser
observation and is nowhere quoted as the measurement.**

## Corrections to the brief, found in the artifacts

1. **T4.11's speed blips are not in the committed CSV.** The file contains seven
   contiguous `|ConveyorBeltSpeed| > 0.05` episodes and every one is a full stroke
   of 8.85–11.15 s; there is no ~100–150 ms episode anywhere, because the CSV
   begins at 17:49:06 and the presses were at 17:30:45 / 17:36:50. The blips were
   lost to LIMITATION 1. The finding stands on the transcript and on the code; the
   measurement has no artifact, and §11 4.11 now nominates that very CSV as its
   instrument — outstanding row 15.
2. **The artifact gap is wider than the brief's three limitations.** There is
   **no committed bridge artifact of any kind for 17:14:07 – 17:49:06**: the log
   path in use there was truncated three further times. The T1.4 re-run and all of
   T4.11 fall in it. Recorded as outstanding row 21.
3. **A second lost publish.** The transcript records three capstone process-stop
   presses; the CSV carries writes for two. R3 `7/5` leaves no room for an
   unwritten `false`, so the program was never presented with the third, and the
   1 Hz log confirms the cycle at that moment ended cleanly with no latch. Same
   `--once` race as the 17:49:38 start press.
4. **T4.10's SIGKILL hold reproduces as 20.10 s**, not ≈22 s: measured from the
   last heartbeat change (observer t = 13.4576) to `CurrentSessionCount` falling
   (t = 33.5542). The transcript's ≈22 s was measured from the shell's kill
   instant and is recorded as such. Reported raw, no interpretation, as instructed.
5. **Two transcript-cited owner captures are not in the committed directory** —
   16:33:32 (T4.6b `PositionFrozen FALSE`) and 17:14:55 (T1.4 `ET` filled); the
   2026-07-28 captures jump 14:41:16 → 17:09:20 and the last **watch table** of the
   day is 17:36:15. Six captures **are** present and are now read by content — see
   the addendum below, which corrects this row's original claim that none of them
   could be cited.
6. **Wall-clock times must not be derived from the CSV.** The wall clock advanced
   **1.767 s more** than `CLOCK_MONOTONIC` over the final session (log span
   714.022 s against `run,duration_s` 712.255 s), so every CSV figure in part 2 is
   quoted on the CSV's own clock and wall times come only from the logs or, marked
   `[transcript]`, from the session record. This is LESSONS 2026-07-27 (verify
   which clock the code samples) reappearing in a smaller form.

## What the run closed, and what it did not

**Closed:** §B.12 items **3** (the CPU cycle times — see the addendum), 8 (the
dwell was reached — presence asserts in 145.6–150.8 ms and the dwell ran 2.050 s,
answering part 1's finding F1), 10 (T4.6 re-specified: 2.301 s), 12 (T4.7 inverted:
35.0 s of refusal, then honoured after the revive, then a separate start), 13 (the
build behind every figure is named). Item 11 is closed for the reaction and open
for the term; item 5 ran in one of its two forms; item 6 split.

**Section B items 1, 2, 4, 5, 6, 7, 8 and 9 are all filled**, with no remaining
`[transcript]`-only row inside item 1. L4 is unchanged as the bound of §A.6.

**Item 4 (L7) is filled on a different input than §11 T3 nominates, and the
reason is recorded rather than worked around.** Both delivered process-stop
presses landed *during the dwell*, 0.75 s and 0.76 s after the command had already
reached `0.0` at the beam, so no command change remained for them to cause. The
start press gives the same derivation on the same clock: **count 6, min 45.447,
median 46.163, p95 47.690, max 47.690 ms** — the same cluster as part 1's 46.8 ms
median, still an upper bound quantised by the 50 ms poll. For the nominated input,
the 5 Hz observer gives a bound only: the whole reaction completed inside one
200 ms sample, twice.

## Three findings, none softened

* **F3 — T4.9b FAILED.** `bridgelog-…-sessionC-t49b.log.gz`: latches set and
  `BridgeLinkOk False` at 17:02:21.015, heartbeat begins 17:02:30.610, **every
  latch clear at 17:02:31.265** in the same poll in which the link first read
  `True`. Root cause `BridgeLinkOk := NOT HeartbeatStaleTimer.Q`, which boots
  `TRUE`. A **PLC** defect; the bridge's behaviour in the capture was correct and
  is what makes the link-up instant visible. Cross-referenced to LESSONS
  2026-07-28 and to `docs/reports/m3-34-link-polarity-spec.md`.
* **F4 — T4.11's latch cannot form by the method §11 named.** The plant recovers
  inside the narrowed window in ~100–150 ms, under `BELT_FAULT_DELAY`; the test is
  extinguished by the reaction it triggers. Recorded together with the fact that
  its own figures no longer reproduce (correction 1 above).
* **F5 — the bridge does not repair a reverted input image.** After a CPU
  STOP → RUN under a surviving session the latches held **4 min 31.1 s**
  (16:52:08.875 → 16:56:40.008) and the reset was correctly refused. Mechanism
  proven from the same artifact: the `sessionA` log carries no `session broken`,
  no reconnect and no read/write error for the whole 1 h 43 m, so nothing was
  re-established and write-on-change never repaired the unchanged slots. **This is
  a `bridge/` defect and I did not fix it** — the brief's deliverable is the
  evidence, and touching code was forbidden. Requested below.

## Addendum — the cycle-time capture, and the watch-table sweep

**The cycle-time figures do reproduce, and §B.12 item 3 is now closed.** I opened
`plc/demo-cell/evidence/watch-table/Screenshot 2026-07-28 174127.png` and it shows
exactly what the coordinator described: a TIA *Cycle time* panel reading
**Shortest 1.004 ms / Current-last 1.023 ms / Longest 2.556 ms**, with a bar chart
whose axis runs 1.023 → 150 ms. §B2.9 now records the three values from that file
and §B2.12 row 3 reads CLOSED. Two limits on what the capture proves are stated
there rather than glossed: the panel is the **CPU** cycle-time panel and does not
itself name the OB30 period (the 20 ms is `SPEC.md` §3.3's configured value
standing beside the reading), and the `150` is an unlabelled axis limit, not a
value the panel attributes to anything. I also **withdrew the L7 decomposition** I
had hung on these numbers — "an OB30 scan is ~1 ms of the 46 ms" claimed more than
a cycle-time panel can support, and the text now says only that the OB30
contribution is small rather than dominant.

**The sweep found substantially more than I had credited, and one thing less.** I
swept the 24 filenames from 2026-07-28 against every "no capture covers X" claim
and then opened the six candidates. Three claims survived, two were wrong, and the
pixels added a finding:

* **The 17:16:56 / 17:17:12 / 17:17:27 triple is real, and it is the only Group 4
  record of a CPU restart anywhere in this gate.** New **§B2.7c** reads it: the
  three captures show `ProductSensorRange` reverting **1.440088 → 0.0** across the
  restart, `SensorFaultLatch` setting because 0.0 is below `RANGE_MIN`, `PositionRef`
  reinitialising 0.1995 → 0.0, and the CPU operator panel going green → yellow →
  green. It also gave `EVIDENCE_SIGNAL_LOSS.md` case C the **bridge-stopped**
  sub-case it was missing — the 1.440088 standing two and a half minutes after the
  bridge stopped is that file's own case-A freeze, seen from inside the CPU.
* **It also forced a correction to my own §B2.12a, which had over-reached.** I had
  attributed three `CellProcessStopActive True` readings to build C's boot window.
  Two of them are **held** latches whose formation this evidence does not time, and
  the third (T4.5's first restart) formed by the F5 mechanism — a surviving
  session's heartbeat resuming over reverted inputs — not by boot polarity. The
  capture at 17:17:27 is the *one* reading that does show the boot window, and
  unambiguously: `ProcessStopLatch` **TRUE** beside `BridgeLinkOk` **FALSE** with
  the inputs at start values and the bridge stopped, which on this build can only
  have formed inside the 500 ms window. §B2.12a is rewritten to say that, and it
  makes those three captures **the cheapest available before/after test of m3-34's
  §6.8 fix** — after the rebuild they should read `ProcessStopLatch FALSE`.
* **`PresenceOnTimer.PT` reads `T#100MS` before the restart and `T#0MS` after it**,
  and `T#0MS` in both later captures. Recorded as **F6** and **handed to `plc/`
  undiagnosed**, with the three reasons it is a question and not a fact stated in
  place — including the strongest counter-argument, that the presence verdict
  demonstrably worked afterwards (§B2.6a's three 145.6–150.8 ms intervals were
  measured at 17:51 and 17:58, after all these captures, and fit a 100 ms filter,
  not a 0 ms one). New outstanding **row 22**: one watch-table row at the next
  download settles it.
* **The same triple gave §B2.6a the in-force `PRESENCE_FILTER`**: `171656.png`
  shows `PresenceOnTimer.PT` monitoring at **`T#100MS`**, which is the online
  reading LESSONS 2026-07-28 requires after a timer fix and which part 1's F1
  never had.
* **The two T4.11-era captures corroborate weakly and I say so.** `173247.png` is
  2:02 **after** the first press and `173615.png` is 0:35 **before** the second;
  both show `BeltFeedbackFaultLatch` **FALSE**, which is consistent with the latch
  never forming and is not evidence about either press — the event is shorter than
  one watch-table update, which is why §11 4.11 now nominates the CSV. Worse for
  the second press: that capture shows **three latches already pending 35 s
  before it**, so unless a reset intervened the press could not have started a
  cycle at all, and this evidence cannot say which happened. F4 states both.
* **The two "no capture" claims that stood, now stated precisely.** Nothing covers
  the T4.6 re-measure: the last watch table of the day is **17:36:15**, and the
  only later capture (17:41:27) is the cycle-time panel and carries no tag at all —
  twenty-three minutes before the event. Nothing covers T4.6b either; the captures
  jump 14:41:16 → 17:09:20 across it. My earlier phrasing "the captures stop at
  17:41:27" was true but misleading, because 17:41:27 is not a watch table.

**One inconsistency the sweep exposed that no artifact resolves**, recorded in F4
rather than decided: the first T4.11 press is timestamped **17:30:45** while the
±0.10 download is timestamped **~17:35**, with a full re-download at ~17:33 between
them. On those timestamps the press predates the narrowed constant it is supposed
to have exercised. Either the download times are loose or the two presses were
against different builds.

## The m3-34 additions, as folded in

1. **The T4 denominator is fourteen, and the as-run rows are thirteen.** §B2.7b
   states explicitly that its rows are the thirteen-step table *the run was made
   against*, that the document now defines fourteen, and that **4.11b** is an
   outstanding row and not a fourteenth as-run row (`SPEC.md` §11 rule 2). The
   pass arithmetic is spelled out over that denominator: eight pass, one measured,
   two partial, one ran-and-exposed-a-bridge-defect, one failed — and five results
   additionally do not carry over to the corrected build.
2. **T4.9b's outstanding row (14) carries two preconditions**: the owner's §6.8
   rebuild (`HeartbeatSeenAlive` + per-link-session `ResetDeviceFault`) *and* a
   re-run against that build in **both** of its forms, with the m3-34 report cited.
3. **The cold-start signature is labelled, not reconciled.** §B2.12a says the
   `CellProcessStopActive True` readings of `sessionB`, `sessionC` and T4.5 are
   correct **for build C**, that m3-34 deliberately changes the expected value to
   `FALSE`, and that they must not be reconciled to the new expectation. Rows 14
   and 17 are where the corrected signature gets recorded.
4. **Row 16** carries 4.11b as blocked on the bridge fault-injection facility
   (`SPEC.md` §12 item 6), explicitly *not* blocked on a rebuild. **Row 17**
   carries 4.2, 4.3, 4.5 and 4.8 for re-run against the corrected build.

## Requests for files outside bridge/

1. **A brief for `SPEC.md` §12 open item 7** — the bridge must detect a server
   restart (heartbeat node reverting, or session/subscription loss) and rewrite
   every slot. It is now a named dependency of §6.7's reset guarantee and of §8
   case C, and F5 measures what it costs when absent. `bridge/` work; I am not
   permitted to implement it under this brief.
2. **A brief for `SPEC.md` §12 open item 6** — the opt-in, hold-until-disarmed
   fault-injection mode. It is the only route to T4.11b and therefore to §6.2.2's
   latch. Also `bridge/` work.
3. **A one-line change to the `--evidence-csv` convention** wherever the run
   procedure is written down (`SPEC.md` §11 preconditions is the likely home): one
   CSV *and one log* per bridge session, uniquely named. LIMITATION 1 cost this
   gate the T4.11 record and the day's earlier 20 Hz data, and LESSONS 2026-07-28
   already carries the rule without anything enforcing it.
4. **`docs/TODO.md` / `docs/PLAN.md`** — m3-34's report already asks for the
   cold-start line to be restated; §B2.12a is the evidence-side counterpart, and
   the two should not be updated separately.

## Working-tree note for the orchestrator — commit by pathspec

1. **Four modified files and one new untracked file under `bridge/` are not
   mine.** `amr_bridge/instrumentation.py`, `amr_bridge/main.py`,
   `amr_bridge/opcua_side.py` and `test_double/plc_test_double.py` were clean when
   this session began and changed at 18:36–18:42 while I was writing, and
   `bridge/tools/check_session_lifecycle.py` appeared untracked in the same
   window. The new
   symbols in them — `session_csv_path()` / `EvidenceFileExists`,
   `_invalidate_write_cache()` / `_note_outage()`, `_session_broken()` — are a
   sibling agent implementing exactly what LIMITATION 1, F5 and LESSONS
   2026-07-28's in-flight-exception row ask for. **I did not read them for
   correctness, did not touch them, and my deliverable does not depend on them.**
   Commit my two evidence files and this report by pathspec, not with a bare
   `git commit` (LESSONS 2026-07-27).
2. **My outstanding rows 15, 20 and 21 may be resolved by that work in the same
   window.** Rows 20 (rewrite every slot after a server restart) and 21 (one
   uniquely-named CSV and log per bridge session) are written as requests because
   they were open when I measured them, and I have **not** claimed either fixed —
   nothing here is verified against the new code. If that work lands, those rows
   want reconciling in the same commit rather than left contradicting a landed fix.
   Row 15 still needs a **re-run**, not just the fix: the T4.11 record itself is
   gone and only a fresh run restores it.
3. **Line endings.** One of my edits went through a Python rewrite and converted
   `EVIDENCE_LATENCY.md`'s working copy from CRLF to LF; I restored it, and
   `git ls-files --eol` now reports `i/lf w/crlf` for both evidence files, matching
   every sibling. `git diff --numstat` and `git diff --numstat --ignore-cr-at-eol`
   both report 903/10, so every added line is real content and none is
   line-ending noise (LESSONS 2026-07-27).

open_questions:
- Does anything now block M3's exit item (d) other than **4.11b**, which is
  blocked on a facility that does not exist? Eight of the thirteen steps the run
  was made against pass, and the one outright failure (4.9b) has its fix specified
  in §6.8 and needs a rebuild plus a re-run, not new work. That is a gate call.
- The two PLCSIM session-hold figures for the same granted 10 000 ms timeout are
  **11.79 s** (part 1) and **20.10 s** (part 2). Both are reported raw, and
  nothing consumes either. If a reason is wanted, it needs a deliberate
  measurement rather than a third accidental sample.
- Two transcript-cited captures are absent and, more importantly, **no capture was
  ever taken for T4.6's or T4.6b's Group 4 reading**. Should the owner be asked to
  capture `PositionRef` / `PositionFrozen` / `PositionWindowTimer.ET` during the
  §6.8 re-run, or is the inferred term (§B2.7a) acceptable for the gate? The
  re-run is already required for other reasons, so the marginal cost is one
  screenshot.
- **F6 is a `plc/` question I deliberately did not answer.** If
  `PresenceOnTimer.PT` really is not re-asserted at its call site every scan, then
  `PRESENCE_FILTER` is 0 after every CPU restart — but the presence timings
  measured *after* those captures fit a 100 ms filter, so the reading may be an
  artifact of how the CPU reports a reinitialised instance. It needs a code look,
  not more evidence.

next_suggested: brief `bridge/` for `SPEC.md` §12 items 6 and 7 — one is the only
route to T4.11b, the other is what F5 measures the absence of — and pair them with
the per-session evidence-file convention so the next run's 20 Hz record survives.
