# Task 1 (m5-46) — validate the loop: the m5-44 chain, five times, with the ceiling clamp

    brief:               docs/superpowers/plans/2026-08-06-m5-closure.md, Phase 1 Task 1 (m5-46).
                         Issued in-session; no file in docs/briefs/. The report was directed to
                         this path rather than docs/reports/ by the dispatching instruction —
                         CLAUDE.md §5's home for it is docs/reports/m5-46-*.md, and it is worth
                         a copy or a redirect there before the verifier runs.
    status:              done — five complete repeats of the m5-44 chain on one protocol, plus
                         the ceiling clamp m5-44 could not exercise and five repeats of the
                         link-loss case. Three earlier runs were discarded for harness defects
                         and are named in the evidence rather than deleted.
    files_changed:
      - bridge/EVIDENCE_ENVELOPE_BRIDGE.md        (+370 lines, 0 deletions — §7–§12 appended;
                                                   everything above line 408 byte-identical,
                                                   confirmed by git diff --numstat)
      - bridge/evidence/latency-2026-08-06-m546-r1…r5-…csv.gz          (5 bridge sessions)
      - bridge/evidence/latency-2026-08-06-m546-r1a/r1b/r1c-…csv.gz    (3 discarded runs)
      - bridge/evidence/m546-envelope-chain-2026-08-06-r1…r5.csv.gz    (5 witness captures)
      - bridge/evidence/m546-envelope-chain-…-r1a/r1b/r1c.csv.gz       (3 discarded)
      - bridge/evidence/m546-bridge-r1…r5.log.gz, m546-bridge-r1a/r1b/r1c.log.gz
      - bridge/evidence/m546-envelope-stack.log.gz, m546-obstacle-zone.log.gz,
        m546-arena.log.gz, m546-hmi.log.gz, m546-run-events.txt.gz
      - bridge/standin_writer/logs/standin-writer-20260806T074032Z-pid38804.log
      - .superpowers/sdd/2026-08-06-m5-closure/task-1-report.md
    invariants_touched:  none. Nothing was added to the bridge and nothing in it was changed:
                         no source file, no config file, no threshold, no latch, no timer over a
                         plant signal. `bridge/config/bridge.yaml` and `bridge/amr_bridge/config.py`
                         are untouched (git diff empty), so the envelope group's marking as the
                         bridge's proposal pending the interface ruling stands exactly as m5-44
                         left it. No velocity value crossed the OPC UA seam in either direction
                         (ADR 0014): what crossed was a ceiling, an enable, a permit and a mode.
                         Nothing in TIA was opened, compiled or downloaded.
    open_questions:      below
    next_suggested:      Task 2 (m5-47), the interface round — it is still the blocking item, and
                         this session added a second figure set that will want a home in
                         bridge-design.md's §4.6/§4.7 rows

---

## What the repeat count changed

The point of the task was the distribution, and it earned its keep three times.

**One m5-44 figure reproduced as a figure.** The PLC round trip — the bridge's
write of the field bit acknowledged, to the bridge reading `ForkliftMotionEnable`
`FALSE` — came out **37.2 – 45.3 ms, mean 43.2, n = 5**, with m5-44's single
41.6 ms sitting inside it and four of five runs within 1.7 ms of each other. So
did the arrival spread (1.2 – 2.2 ms against m5-44's "within 1.8 ms") and the
link-loss reaction (508.1 – 542.9 ms against m5-44's 519.7 ms, all five inside
the gate's `[500, 550] ms` window by construction).

**One reproduced only as a range, and m5-44 had drawn its top.** Gate adoption
came out **9.7 – 44.5 ms, n = 5**. m5-44's 44.5 ms is not this chain's adoption
latency; it is the **maximum** of a 4.6x-wide distribution, and the same chain
adopted in 9.7 ms in r1. Quoting the single observation would have overstated the
figure by up to four times.

**One does not transfer at all, and saying so is the finding.** m5-44's 162.5 ms
command-to-zero is not a stopping figure. The gate ramps at a fixed 0.50 m/s², so
the duration is proportional to the speed it ramps *from*: m5-44 withdrew at
0.1018 m/s (0.204 s predicted, 162.5 ms measured), these five withdrew at the full
0.600 m/s ceiling (1.200 s predicted, 1156 – 1209 ms measured). **The deceleration
repeats; the duration is a function of the speed**, and a stopping time quoted
without it says nothing.

## The gap, closed

**The ceiling clamp is exercised on the real chain for the first time.** A 20 Hz
demand of **0.900 m/s** was held on the gate's input against the **0.600 m/s**
ceiling the PLC formed, in all five runs: **9352 non-zero `/cmd_vel_gated`
samples, 9121 of them exactly at the carried ceiling, and 0 above it.** The
maximum is `0.600000024` — bit for bit the `float64` widening of the PLC's `Real`
0.6 that the bridge read off the CPU, not a 0.6 configured on the vehicle, which
is what shows the bound came from the controller. m5-44 §4.1's explicit
"this run does not exercise the ceiling clamp" is answered.

## One run behaved differently and is not averaged away

**r4.** Its first `|odom vx| < 0.005 m/s` came at **+877.7 ms**, before the
command reached zero — the plant decelerated ahead of the commanded ramp — and it
is not a standstill: the vehicle crept again, to 0.0071 m/s, and settled only at
**+1128.1 ms**. In the other four the first crossing and the settled standstill
are the same sample. The evidence table quotes the settled figure for all five so
the column compares like with like, and states r4's transient beside it. Its PLC
round trip is also the low outlier at 37.2 ms.

## Three runs discarded, and what each of them cost

Named in the evidence, files kept, no figure taken from any of them.

1. **`r1a`** — `SIGTERM` sent with **no demand live**. The gate counts and logs its
   stale close on the transition *out of* `PASSING`, and `PASSING` needs an
   arriving command; with no demand the gate sits in `HOLD_ZERO` and a link loss
   changes nothing it can report. m5-44's r4 had a live publisher, which is why it
   saw one. **A degraded-mode test needs the system in the state the degradation
   degrades.**
2. **`r1b`** — `gz service … set_pose` **returns `data: true` and does nothing**
   when the request carries only `name:`; it resolves on the entity id. The run
   therefore started jammed against the wall the previous run had stopped at,
   inside the scanner's blind range so the scan read *clear*, and drove a stalled
   vehicle for 60 s: 162.5 rad of wheel (19.5 m) against 0.63 m of model. The
   reset now reads the id, sends it and **verifies against the pose**.
3. **`r1c`** — the corrected reset worked and the 60 s trip window was simply too
   short for the route. Probed afterwards, the field trips at `x ≈ 14.1`.

## A collision caught before it was committed

The witness captures were first written as
`envelope-chain-2026-08-06-r1…r5.csv.gz` — **m5-44's own naming, same date, same
run letters** — and copying them into `bridge/evidence/` overwrote three committed
m5-44 captures. Caught by `git status` before any commit; the three were restored
from the index and verified with `gzip -t`, and mine now carry an `m546-` prefix.
`envelope-chain-2026-08-06-r1/r2/r3/r4-linkloss.csv.gz` are m5-44's committed
files, unmodified. **A run identifier unique only within one session is not a file
name** — the same rule the bridge's own per-session CSV suffix already follows.

## Protocol, stated so the next repeat is the same one

Stack from m5-44's own launch lines. Per run: fresh bridge session → cell to rest,
process stop released, monitored reset tapped, `ForkliftResetRequired` seen
`False` → witness up **before** the envelope → `drive_mode := 2` → 0.900 m/s
demand → traverse → field trips → PLC withdraws → demand held live a further 4 s →
pose commanded back and **verified** → recovery and a permissive envelope again →
0.30 m/s demand made live → `SIGTERM`. Route: spawn `(-4.5, 7.0)` yaw 0 down the
aisle at `y = 7.0`. Machine checked idle and recorded before the timed runs
(`load 0.00 0.00 0.00`, `pgrep` empty); one simulator, one agent measuring.
Throwaway harness scripts live outside the repository, as m5-44's did; nothing was
added to `bridge/`.

## open_questions

1. **The plant's traction authority is the least settled part of this chain.** The
   same 17.8 m of route took **32 s in one run and 148 s in another** — a factor
   of 4.6 — at an unchanging clamped 0.600 m/s command, while the trip *place*
   repeated to 49 mm in `x`. That, r4's early deceleration, and m5-44's open
   question 4 (the closed-loop smoother cannot accelerate this plant from rest)
   are plausibly one fault. It is `agv/`'s, it is undiagnosed here, and it will
   shape any AT that needs the vehicle moving at a chosen speed. Data:
   `bridge/evidence/m546-envelope-chain-2026-08-06-r1…r5.csv.gz`.
2. **m5-44's REQUEST 5 did not reproduce.** The `/cmd_vel_gated` 0.30/0.0
   alternation it handed to `agv/` was not seen in any of these five runs, in
   either demand phase; the held-zero windows are 320–322 consecutive exact zeros,
   five times out of five. That does not close the item — the conditions may
   differ — but the observation is now `n = 1` of 1 against `n = 0` of 5.
3. **The recovery sequence has no repeat count.** It ran correctly before every
   run, but m5-44 §4.2's latch behaviour was not re-timed and this session claims
   nothing about it.
4. **`bridge-design.md` still does not carry the envelope group.** Unchanged from
   m5-44 and still the blocking item (`opcua-nodes.md` §12.13 item 1). This session
   deliberately touched neither `config.py`'s marking nor `bridge.yaml`.
5. **The stale-close bound is a construction, not a measurement.** All five land in
   `[508, 543] ms` and the gate's own `stale_window_s + one cycle` is `[500, 550]`.
   The five runs are consistent with it; they do not independently establish it.

## REQUESTS — files outside `bridge/`

1. **`docs/LESSONS.md`, orchestrator** — three entries this session earned, none of
   which is in the file: (a) *a service's own boolean return is not evidence that
   it acted — `gz set_pose` returns `true` and silently no-ops without an entity
   id; verify a commanded state against the state itself*; (b) *a degraded-mode
   test must put the system in the state the degradation degrades — a stale-link
   test with no command flowing measures nothing, because the verdict it looks for
   is a transition out of a state the system was never in*; (c) *a run identifier
   unique only within one session is not a file name — dated per-run evidence from
   two sessions collides on date and letter and the second session overwrites the
   first.*
2. **`agv/forklift/`, agv-ros2 agent** — open question 1, the traction authority.
3. **`docs/TODO.md` / `docs/PLAN.md`, orchestrator** — Task 1 is closed by this
   report; Task 2 (m5-47) remains the blocking interface round.
