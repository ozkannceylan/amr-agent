# Report m4f-04j — the SPEC records the as-built bridge watchdog

```
brief:               docs/briefs/m4f-04j-asbuilt-bridge-watchdog.md
status:              done
files_changed:       plc/forklift/SPEC.md (§3.1b rewritten and retitled; §7's
                     watchdog and fence note; §3.1, §3.2, §3.3, §4.1, §4.2,
                     §4.3, §6.1, §8, §9, §10, §11, §12 and the preamble
                     reconciled by sweep)
                     docs/reports/m4f-04j-asbuilt-bridge-watchdog.md (this file)
invariants_touched:  none — invariant 10 holds with a new single owner: one
                     bridge process, one heartbeat, one verdict, and in this
                     project one program forms it
open_questions:      two, both outside plc/ — see below
next_suggested:      interface brief to reconcile opcua-nodes.md §10.1's
                     shared-project sentence with the one-cell project
```

## What the program now says it is

The owner decision of **2026-07-30** is recorded where the change is described,
in a blockquote at the head of the document and again in **§3.1b**, which is
retitled *"Both link verdicts are formed here — the as-built bridge watchdog"*.
The `safe_amr` project has no demonstration cell, so the verdict this document
used to **consume** is now **formed here**, in the shape the M3 cell proved:

| What | As built |
|---|---|
| Input | `"ForkliftLink".BridgeHeartbeat` |
| Constant | `HEARTBEAT_STALE_TIME` = `T#500ms` (§3.3, its own constant, never shared with `HMI_STALE_TIME` — P4) |
| Statics | `LastBridgeHeartbeat`, `BridgeStaleTimer`, `BridgeSeenAlive` (§3.2) |
| Verdict | `BridgeSeenAlive AND NOT BridgeStaleTimer.Q`, pessimistic boot polarity |
| Published | **No node.** The verdict is a Temp; §9 Group 5 watches its two terms |

§7 part 1's bridge half is now the same six lines as the HMI half with the other
client's counter, and it carries the same *"never write it as `NOT
BridgeStaleTimer.Q`"* warning — that form reads `TRUE` for the first 500 ms of
every CPU run, before the bridge has written anything (LESSONS 2026-07-28, one
client over).

## Counts, exactly, and the fence hash

| Metric | Before (after §13) | After |
|---|---|---|
| Statement lines in the §7 fence | **125** | **131** (+6: one consumed assignment replaced by seven lines — change test, timer call, counter copy, a three-line one-shot, verdict) |
| Fence size including its ` ```pascal ` / ` ``` ` markers | 252 | **264** |
| `sha256/16` of the fence **including** markers | `55306f610e09a9f7` | **`2864b018aa0a41d7`** |
| Lines ending in `;` | 58 | 60 |

The `;` metric moved by 2 while six statement lines were added, because several
of the new lines carry a trailing comment. **It is therefore not a statement
count in this fence and must not be read as one** — recorded here and in §7's new
note only because earlier revisions used it. The three fence hashes now form a
chain — `a100896d41e7a315` (M4 baseline) → `55306f610e09a9f7` (§13) →
`2864b018aa0a41d7` (this) — and §7's note is the **single** place the current
value lives, so a total quoted twice cannot go stale in one of them. §13.1's
paragraph was rewritten to state the safety delta's own **+7** rather than the
totals it used to quote, which this change made stale.

## The sweep, and what it forced

The brief named five loci; the sweep criterion reached **21 sections plus one
rename**. That is the enumerated-list rule working as intended (LESSONS
2026-07-27, 2026-07-29): the brief's list was a starting point and the file was
searched independently.

- **`DemoCellControl_DB`: 0 occurrences.**
- **`DemoCellLink`: 4, `FB_DemoCellControl`: 3 — every one inside a statement
  that the project does **not** contain them**: the preamble blockquote, §3.1b's
  owner-decision paragraph and §7's comment saying why the watchdog is local
  (which I rephrased to *"no demonstration-cell FB"* so no identifier that does
  not exist in the project appears in code the owner types). **Zero dependencies
  remain**: no read, no call order, no shared DB bit. I read the brief's "gone"
  as *no reference that treats them as present*, following this document's own
  idiom for words that may appear only in statements of what the cell does not
  have (§2). If a literal zero-occurrence purge is wanted, say so — it costs
  three sentences and makes the correction unexplainable.
- Consequential edits the brief did not list, each needed or the document
  contradicts itself: **§3.2** gains the three statics and **§3.3** the
  constant (without them §7 references undeclared symbols); **§3.1** records
  that `BridgeHeartbeat` is a server-visible tag in `ForkliftLink` and **not one
  of the 18** — it is `opcua-nodes.md` §9.7's single bridge heartbeat, whose
  **data block** moved while its BrowseName did not; **§4.2** gains it to the
  `ForkliftLink` row as *Writable* ✔ (the bridge must write it) and its
  per-client policy sentence names both heartbeats; **§4.3**'s tree shows
  `Link/BridgeHeartbeat` where it showed "the M3 cell, byte-identical";
  **§6.1**, **§8** case B, **§9**, **§10** steps 3, 8, 11 and its preamble,
  **§11** steps 5.1.1, 5.6.1, 5.6.2, 5.6.4, and **§12**'s demo-cell row.
- **§11's pass counts are unchanged** — 9, 8, 5, 10, 6, 5 = **43**, re-derived
  from the step tables. The four touched steps swap an observable that no longer
  exists (`BridgeLinkOk`, a node in the M3 group) for the two watch-table rows
  that do (`BridgeSeenAlive`, `BridgeStaleTimer.ET`). No behaviour, threshold or
  reaction changed, and no step row was added or removed.

## Verification

- **Per-section `sha256/16` against `HEAD`**: 29 of 51 sections byte-identical,
  21 changed, `### 3.1b` renamed (one added, one removed heading). Untouched and
  proved so rather than asserted: §2's boundary statement, §5, §6.2 to §6.7,
  §11's other 39 steps, and the whole of §13 except its count paragraph.
- **`git diff`**: 42 hunks, `+200 −77`.
- **Fence**: measured with the same extractor used for the two earlier hashes,
  both conventions recorded; the inner-only hash is `26ac80f04970a3a7`.
- **Structure**: 33 tables in the file, none ragged; fence markers balanced (28
  backtick fences); no `deadline`, no tooling mention.
- **Line endings** `i/lf w/lf`, no CRLF.
- **What is not verified**: none of this has been executed in TIA Portal or
  PLCSIM by its author. The as-built facts are the owner's, dated, and named as
  such at every point they are used.

## Two open questions, both outside `plc/`

1. **`opcua-nodes.md` §10.1 still describes the shared-project arrangement** —
   *"the verdict is written by the demonstration cell's FB and consumed by the
   forklift FB as a shared DB bit"* — and §10.11's "no second heartbeat" rule is
   what makes the as-built correct. The node set does not move: still one
   heartbeat node, still no verdict node. **Requested, not taken** (this brief
   forbids editing `docs/interfaces/`).
2. **The heartbeat's browse path is a read-back, not a design value.** Every
   bridge configuration resolves it at `Link/BridgeHeartbeat` relative to the
   interface node, i.e. `DemoCell/Link/BridgeHeartbeat`; the DB behind it moved
   and the path must not. §10 step 11 now asks the owner to browse it with the
   independent client and record it with its date (ADR 0006). Until then it is a
   design value, and the bridge's first failure to write would be its symptom.
