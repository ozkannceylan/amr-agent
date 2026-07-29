# Report m4f-01f — the speed-limit flag's reading, ruled

```
brief:               docs/briefs/m4f-01f-speedlimit-flag-reading.md
status:              done
files_changed:
  - docs/interfaces/opcua-nodes.md   (edited) §10.7, the
                                     `ForkliftSpeedLimitActive` meaning cell —
                                     one line
  - docs/reports/m4f-01f-speedlimit-flag-reading.md   (new) this report
invariants_touched:  none
open_questions:      two, listed below
next_suggested:      Request against `plc/`: SPEC §6.5's paragraph quotes the
                     §10.7 wording this commit replaced, so its "could be read
                     as the narrower verdict" sentence is now stale.
```

## The ruling

§10.7 said the flag meant "the carriage is raised past the cap's height **and** the traction setpoint
is being limited below what the operator asked for" — a conjunction that reads as the narrow *biting*
verdict, which is not what the program computes. It now states the **wide** reading, matching
`plc/forklift/SPEC.md` §6.5 as corrected by `bc6a570` (`ForkliftSpeedLimitActive := ForkliftTeleopActive
AND forkRaised`):

- **`TRUE` while the fork-height cap is the multiplier in force** — teleop active and the carriage
  raised — **regardless of the momentary demand**, so the flag is steady while that condition holds and
  never follows the operator's control.
- **The discarded reading is named** so it cannot be re-derived: *"the cap is biting"*. Under §10.6's
  scale semantics the capped setpoint is below the uncapped one at **every** non-zero demand, so that
  verdict degenerates to "the operator is asking for something" and would drop out each time the
  control crossed centre.
- **The cost of the wide reading is stated rather than left to be found**: it reads `TRUE` at zero
  demand too, when nothing is being reduced yet. That is the price of a flag that is readable on a
  display and stable in a recording, and it is the right trade for both.

Two things inside that same cell improved as a side effect, disclosed rather than slipped in. The
trigger now cites **§6.5's `forkRaised`** instead of restating it as "raised past the cap's height":
the old phrasing silently excluded the implausible-height case, which `forkRaised`'s
`(NOT heightValid) OR …` deliberately includes so a broken transducer takes the restrictive direction.
And the "Informational — the reduction itself happens in the setpoint (§10.6)", **Not** SF-04 and
no-PL-claimed clauses are carried through **verbatim**. **One line changed in the whole document**; no
node, type, count, constant, start value or access right moved.

## Sweep

Subject sweep over the flag's name — `ForkliftSpeedLimitActive`, `SpeedLimit`, `speed limit` — across
the whole of §10, whitespace-normalised so a name wrapped across a line break still matches
(LESSONS 2026-07-27), plus the neighbouring statements that could carry the narrow reading without
naming the flag (LESSONS 2026-07-29 — sweep by subject, not by phrasing):

| Site | Verdict |
|---|---|
| §10.7 meaning cell | **The target.** Ruled |
| §10.3 per-tag ownership row, `Status/ForkliftSpeedLimitActive` \| PLC \| HMI, bridge (logging only) | Writer and readers only. Carries no reading of the flag; untouched |
| §10.6 `ForkliftTractionSpeedRef` | Already the scale, as of m4f-01e. It is what makes the narrow verdict degenerate, and the new cell cites it for exactly that |
| §10.7 interface-expectations paragraph — "the fork-height speed cap's **height and reduced speed**" | Names the two constants as process decisions this document does not make. No reading of the flag |
| §10.1 "the fork-height speed cap … **standard-program process interlocks** … not SF-04" | Classification and the safety disclaimer. No reading of the flag |
| §10.11, §10.12 | The flag's name does not appear |

**No statement in §10 now carries the narrow reading**, and the two occurrences of the flag's name are
the ownership row and the ruled cell. With m4f-01e's clause in §10.6 and this one in §10.7, the cap
thread is closed on the interface side: the setpoint row says the cap is a scale, and the status row
says the flag reports that scale being in force rather than its effect on the current demand.

## Open questions

1. **The requesting document quotes wording that no longer exists, and it is `plc/`.**
   `plc/forklift/SPEC.md` §6.5 (line 660) reads: "`opcua-nodes.md` §10.7 describes it as *'the carriage
   is raised past the cap's height and the traction setpoint is being limited below what the operator
   asked for'*, which could be read as the narrower verdict; the wider reading is implemented because
   it is the one that is useful on a display and stable in a recording." That quotation is now stale in
   both halves — the wording is replaced and §10.7 no longer admits the narrower verdict, so the
   sentence should become agreement rather than a caveat. A revision that resolves another document's
   request updates that document in the same change (LESSONS 2026-07-26); this brief forbids editing
   `plc/`, so it is recorded as a request instead of half-applied. It is one sentence, and a concurrent
   `plc` agent is working in that file.
2. **The cap thread's remaining loose ends are not this layer's.** m4f-04e's request 2 —
   `plc/forklift/double/`'s check still named "the cap LIMITS, it does not command" over a computation
   that is correct, which needs a re-run rather than an edited transcript — and its request 3, the
   `sim/scenarios/forklift_commissioning.md` §11 rows recording that their findings closed. Both were
   already open before this brief and neither is in `docs/interfaces/`.
