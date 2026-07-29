# Report m4f-05d — restart-residual row at its measured size

```
brief:               docs/briefs/m4f-05d-restart-residual-row.md
status:              done
files_changed:       [docs/interfaces/bridge-design.md,
                      docs/reports/m4f-05d-restart-residual-row.md]
invariants_touched:  none
open_questions:      1 — the second witness is now a sized owner decision, not a
                     theoretical one
next_suggested:      Put the second-witness decision to the owner with the
                     measured figure attached; §8.1 states the gap, nobody owns
                     closing it
```

## The residual row, at the size m4f-06 measured

§8.1's *Restart residual* row now carries **two cases** instead of one, with the
second the large one. Every figure is quoted as the run printed it (LESSONS
2026-07-27) from `bridge/EVIDENCE_CONNECT.md` § m4f-06.4:

- **(a) The value-collision case, retained**: a revert landing on exactly the value
  this session last wrote — one heartbeat value in 65536.
- **(b) The window case, new**: a revert landing between the cycle's **step-0
  heartbeat read-back and its own step-4 heartbeat write** is erased by that write,
  so the next read-back compares **equal** and the restart goes undetected. Window
  `median 5.255 ms p95 7.886 ms max 10.143 ms` of a `median 50.015 ms` cycle,
  `as a fraction of the median cycle: 10.5 %` — **roughly one revert in ten, not
  one in 65536**.
- **What it cost in the run that measured it**: one masked revert left the server
  holding an **open stop circuit and `ForkliftObstacleInStopZone` `TRUE` for 4.0 s
  — 81 heartbeat increments — under a heartbeat that never faltered**, which is
  §7.3 case E surviving its own detector. On the commissioned cell the PLC would
  have qualified those inputs as attributable, because the predicate it is given is
  the heartbeat.
- **Pre-existing and not forklift-specific**: reproduced the same morning by the
  cell-only `check_session_lifecycle.py` on the unmodified cell config, and present
  in the m3-35 code as shipped.
- **Both restart harnesses now trigger reverts until one is caught, up to a bound,
  and report how many were masked** — the property is measured on every run rather
  than flaked over.

**The second-witness requirement is unchanged, word for word**, and is now marked
an **open owner decision**: closing the gap needs a second witness and a second
witness needs an owner. The measurement sizes the gap; it does not decide it, and
nothing here proposes a mechanism.

## §12 closures

| Item | Now |
|---|---|
| 11 | **Closed by m4f-06, 2026-07-29, commit `71d3b76`.** All four requirements hold in shipped code — allowlist derived from configured groups (and an `Hmi` node in any position rejected), R3's count from the configured set, the same for reconnect refresh and restart repair, log lines worded per configured set. Figures as printed: `check_forklift_slots.py` 46 checks/46 passed, `check_write_allowlist.py` 39/39, restart rewrite `11 of 11` in the log and `11/11` in the evidence file, forklift-only run reaching its heartbeat on four inputs and touching 13 nodes. Records that the commissioned `bridge.yaml` **stays cell-only by choice** until item 10's read-back |
| 13 | **Both halves closed.** `bridge/` marked its own request `SATISFIED, 2026-07-29` in `EVIDENCE_LATENCY.md` Section B item 1 (`71d3b76`). The item also notes that the same evidence requested one correction **back** — the understated residual — which is why it closes with a corrected row rather than the row it was resolved with |
| 14 | **Bridge half confirmed** per `bridge/EVIDENCE_LIFECYCLE.md` §1.2: with the forklift group configured, `BridgeHeartbeat` remains the only node outside an `Input/` folder the bridge writes, and remains a valid *witness* because the other client's counter is `Forklift/Link/HmiHeartbeat`, which it never touches. The item now also records what that confirmation did **not** establish — how wide the witness's blind spot is — pointing at the corrected §8.1 row. **The `plc/` half stays open** (`plc/demo-cell/SPEC.md` §4.3, `plc/`'s to correct) |

## The subject sweep — and one hit beyond the named deliverable

Subjects `residual` (8 hits), `restart` (63) and `heartbeat` (92), whitespace-
normalised over the whole file. I read all 8 residual hits in full and filtered the
other two subjects to every hit making a **size or completeness claim** about the
restart detector — the only claims that can rest on the old understatement.

**One statement outside the brief's named deliverable was still asserting it**, and
I corrected it rather than only reporting it, because this brief's `forbidden` list
does not exclude other parts of this file and the `done_when` sweep clause requires
zero remaining:

- **§7.3 case E**, final cell, read "It is caught by the **bridge**, not by the
  PLC… §8.1's restart-detection row." Unqualified detection — true only while the
  miss was 1-in-65536. It now adds: *caught, but not always at the first revert*;
  one landing inside the read-then-write window waits for the next, measured at
  roughly one in ten, with the 4.0 s exposure named. One clause, no structural
  change.

Read and left alone, with the reason:

| Where | Why it is not a dependency |
|---|---|
| §7.1 wrap-period row (`65536 / 20 Hz ≈ 54.6 minutes`) | Counter arithmetic, unrelated to the residual |
| §8.1 *Restart detection* / *Restart repair* | Both conditional on a difference being seen; the exception lives in the row directly below them, which now states it |
| §6.1 R4 | "after **every** reconnect and after a **detected** server restart" — already qualified by detection |
| §8.2 case D, §8.4 residuals (belt/forklift during an outage) | A different residual entirely — the plant holding its last command while the bridge is down |
| §4.3 row 9r, §4.6 read-back cost row, §9.2 **RB** | Describe the mechanism and its cost, assert no completeness. RB is in fact the instrument the window was measured with — the `read_rt` row whose start bounds it — and its "measured rather than asserted" wording is now literally true |
| §9.3 instrumentation list | Counts what the **bridge** records (read-backs, restarts detected, inputs rewritten). The masked count is a **harness** figure, not a bridge counter, so the list stays accurate. Worth a bridge-side counter one day; not this brief's, and not a design requirement I should invent here |
| §10 evidence-file table, §12 items 9/10/12 | Restart mentioned as scope or provenance, no size claim |

Residue check as a second instrument: `one heartbeat value in 65536`, `one in
65536`, `invisible to the test`, `next restart is still caught` — the surviving
occurrences are all inside the new row's case (a), where they are correct and
deliberately kept, and `next restart is still caught` is **gone** (0 matches),
because that was the sentence the measurement falsified.

## Open questions

1. **The second witness is now a sized decision.** §8.1 says closing the residual
   needs a second witness and that a second witness needs an owner. The gap is no
   longer theoretical: ~10 % of reverts, with a measured 4.0 s exposure holding an
   open stop circuit under a live heartbeat. Whatever is decided, this document
   states the gap honestly and nothing in the code hides it — but nobody currently
   owns closing it, and the brief correctly forbade me from inventing the rule.
