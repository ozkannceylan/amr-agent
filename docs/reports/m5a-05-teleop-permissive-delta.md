# Report m5a-05 — the teleop permissive learns the safety demand

```
brief:               docs/briefs/m5a-05-teleop-permissive-delta.md
status:              done
files_changed:       plc/forklift/SPEC.md (new §13; §7 SCL delta; four
                     minimal amendments in §2, §3.1, §6.3, §11, §12)
                     docs/reports/m5a-05-teleop-permissive-delta.md (this file)
invariants_touched:  none — the standard program reads F-data and writes none
                     of it; the safety demand still never traverses the network
                     and what leaves the CPU is a process consequence and a copy
open_questions:      see "Open questions and requests" below (4)
next_suggested:      hmi/ brief for the three-lamp safety display, or the
                     double's F-flag kernel — both listed as §13.8 items
```

## What it is

`plc/forklift/SPEC.md` **§13 — the M5-early safety coupling delta**, written as an
explicit before/after the owner applies on top of the program that is already
built, plus the SCL delta itself in §7. §1–§12 stay the M4 specification; §13 is
the delta on top of it. Eight subsections: the whole delta on one screen with the
exact counts (13.1), four preconditions (13.2), the before/after with the three
forms the term must not take (13.3), the read set, the write set and three
cross-reference checks (13.4), what changes in behaviour and what deliberately
does not (13.5), the T5 impact scenario by scenario (13.6), the fallback as four
states (13.7), watch rows and open items (13.8).

## The delta, as the owner applies it

| # | Where | Change |
|---|---|---|
| **E1** | §7, new **part 0** | Four unconditional mirror copies into `ForkliftSafetyMirror`, then `#safetyDemandClear` from the two F-side demand flags |
| **E2** | §7, part 4 | `#motionPermissive` gains **one** conjunct |
| **E3** | §7 preamble, §6.3 table | `#safetyDemandClear` declared **Temp**; the `MotionPermissive` row states the term |
| **E4** | TIA, outside this document | DB `ForkliftSafetyMirror` and folder `Forklift/Safety/`, per `opcua-nodes.md` §11.3 / §11.5 — that document owns those steps and §13 does not restate them |
| **E5** | §11 preconditions | One precondition line plus the refusal signature. **No step row, no pass line, no count changes** |

The term, in the affirmative form `plc/forklift-safety/SPEC.md` §6.1 fixes:

```pascal
#safetyDemandClear := NOT "InstF_Forklift_Safety".EStopDemand
                  AND NOT "InstF_Forklift_Safety".ZoneStopDemand;
#motionPermissive  := #worldOk AND #safetyDemandClear AND NOT #latchPending;
```

**The three setpoint assignments are byte-identical.** Each is still one
unconditional `IF … ELSE` with a mandatory `ELSE` to `0.0`, executed on every OB
call as the last action of the FB. The delta reaches them the way every other
interlock does — through `#motionPermissive` — and adds no branch, no hold, no
second writer and no analogue path.

## The count, exactly, and the fence hash

| Metric | Before | After |
|---|---|---|
| SCL statements added / modified / removed | — | **+5 / 1 / 0** |
| Statement lines in the §7 fence (non-blank, non-comment) | **118** | **125** (+7: four copy lines, two for the wrapped term, one because the permissive now occupies two lines) |
| Lines ending in `;` — the independent check on "five statements" | **53** | **58** (+5) |
| Fence size including its ` ```pascal ` / ` ``` ` markers | 218 lines | 252 lines (the other 27 added lines are comments) |
| `sha256/16` of the fence **including** its markers, LF, trailing newline | `a100896d41e7a315` | **`55306f610e09a9f7`** |

The hash convention is the one m4f-04i recorded and I reproduced it exactly on the
pre-edit blob (`a100896d41e7a315`, 118 statement lines) before making any change,
so the two values are comparable. **This is the first revision to move the fence
since it was written** — m4f-04b, ‑04d, ‑04e, ‑04g and ‑04i all asserted
byte-identity against it, and a revision asserting byte-identity from here on
quotes `55306f610e09a9f7`, not the old value. `sha256/16` of the fence *excluding*
markers is `f6f4767451851eab`, recorded because m4f-04i noted the two conventions
disagree and only one of them reproduces the earlier reports' string.

## Rulings taken

| # | Ruling |
|---|---|
| **R-a** | **The term lands in `#motionPermissive` only. `#causeGone` is untouched.** Putting it in `#worldOk` would have changed *two* sets — `CauseGone` derives from `WorldOk` — so a standing safety demand would block the **process** reset, making §11 step 5.1.3 unrunnable before the F-side T6.0 and making a client's reset request wait on the F-layer. The brief asks for one term; the two reset paths stay disjoint (`plc/forklift-safety/SPEC.md` §1.3) |
| **R-b** | **The delta sets no latch in the standard program.** The F-latch already holds the state (invariant 10); a standard latch for it would be cleared by `HmiResetRequest`, i.e. by a **client write** dismissing the shadow of a safety demand, which is the reading `TWIN-DEMO-MAP.md` R1/R4 exist to prevent. No auto-resume is still guaranteed, by the enable's edge memory rather than by a latch: an enable held through the stop produces no rising edge when permission returns |
| **R-c** | **Part 0, not part 8.** Every top-level statement in §7 runs on every call, so position does not affect "unconditional". Part 0 keeps every F-data access in one region (making §13.4's cross-reference a single-region check) and leaves parts 1–7 numbered as they were, so §6.4's *"as the last action of the FB"* and every "part 2c / 3 / 4 / 6" reference stays true with no edit |
| **R-d** | **The permissive reads the F-data, never the mirrors** — even though both hold the same value in the same call. Logic reading a mirror turns a display group into a causal element (`opcua-nodes.md` §11.3), and it is invisible in review, so §13.3 tabulates it as a forbidden form beside the other two: deriving the term from `SafetyResetRequired` (an aggregate, which cannot say which demand stands, `opcua-nodes.md` §11.7), and adding any conditional writer around the setpoints |
| **R-e** | **Consistency is not required across F-flags.** Stated in the shape §6.1 uses for the HMI group: no logic requires two F-flags to have come from the same F-cycle, and none may be added. A preemption between two part-0 statements can at worst delay a refusal, or the return of permission, by one 20 ms call — never a wrong steady state, and nothing here is timed (N1) |

## T5 impact — checked scenario by scenario, counts re-derived

**A standing demand reads as motion refused, never as a defect.** The one thing
that genuinely changes is a precondition, and §6.1 predicted it: both stand-in
circuits closed and one monitored F-reset completed before T5.1, because both
demands latch at the first F-cycle of every CPU run by design. §11's shared
precondition block gains one blockquote carrying that line **and** the refusal
signature — enable refused, all three refs `0.0`, **every process latch clear and
`ForkliftResetRequired` `FALSE`** — which is the one signature in the document
that says *read the safety group, not the process latches*.

- **No step row, no pass line and no denominator changed.** Counts re-derived
  from the step tables themselves, not carried forward: T5.1 **9**, T5.2 **8**,
  T5.3 **5**, T5.4 **10**, T5.5 **6**, T5.6 **5** — **43 steps, unchanged**
  (verified by pattern-matching the `| 5.x.n |` row heads, not by reading).
- **T5.1 5.1.3 was the step at risk and it survives**: the process reset tests
  `CauseGone`, which R-a left alone, so it still clears the two link latches even
  with a demand standing.
- **T5.2 5.2.7's "all five latch bits stay `FALSE`" survives** because there is no
  sixth latch (R-b).
- **One evidence rule added**: T5 may be run with the delta applied, but if a
  demand is raised in a session, that segment is T6 evidence and not M4 evidence
  (ADR 0009 D2.2).

## A brief premise corrected, and a premise of the document corrected

1. **The fallback wording.** The brief asks for "with no F-program present the
   F-DB flags read clear ⇒ delta inert". That is not true as stated and the
   safety spec already says so (§6.5: the term is runtime-inert but **not
   compile-inert**). §13.7 therefore states four states rather than one: **A**
   the real fallback — the delta is simply not applied, nothing is edited to take
   it, and §1–§12 stand as M4 with unchanged criteria; **B** applied with no
   demand standing — genuinely inert at runtime, every M4 behaviour exactly as
   specified; **C** applied with the F-program absent — **the standard program
   does not compile**, there are no flags to read, and removing the delta costs
   part 0 plus one conjunct; **D** applied with the F-DB present but its networks
   not built — flags read `FALSE`, the delta is inert, **and it is
   indistinguishable from "all clear" from the standard side**, which is why the
   F-collective signature and not a mirror is the instrument that says which
   F-build is running.
2. **§2's "this plant has no F-CPU" expired with ADR 0009**, the same seam
   `opcua-nodes.md` §11.8 records on its own §10.11 row. Found by subject sweep,
   not by the brief. §2 gains one paragraph: the F-CPU clause is superseded, the
   other two clauses stand word for word (the F-inputs are engineering stand-ins,
   not safety-rated devices; there is still no onboard safety layer of any kind),
   and the boundary statement itself is unchanged and carries **more** weight —
   reading an F-flag and refusing motion is a process consequence of a demand,
   never the safety reaction. §12's "does not specify" row, which cited §2 for
   that premise, gains the same clause.

## Verification

- **`git diff` is ten hunks, `+384 −4`**, and the four deleted lines are exactly
  the four replaced lines: the Temp list line, the `MotionPermissive` table row,
  the `#motionPermissive` statement, and §12's "anything safety-related" row. No other hunk
  exists, which is itself the evidence that §3.2 statics, §3.3 constants, §6.4's
  rules, §6.5–§6.7, §8, §9's five groups, §10's twelve steps and all 43 §11 step
  rows are **byte-identical**.
- **§7 fence**: counted and hashed before and after with the same extractor, both
  conventions recorded above; the pre-edit numbers reproduce m4f-04i's exactly,
  so the comparison is against a reproduced baseline rather than a quoted one.
- **Line endings**: `git ls-files --eol` reads `i/lf w/lf`, and the file contains
  zero CRLF sequences, so no part of this edit is a line-ending artefact
  (LESSONS 2026-07-27).
- **Structure**: all eight §13 tables have a consistent column count and a header
  rule; the three `pascal` fences in §13 are balanced; the whole file's fence
  count stays even.
- **Sweeps**, whitespace-normalised so a name wrapped across a line break still
  matches, and read by **subject** rather than by remembered phrasing (LESSONS
  2026-07-29): `MotionPermissive` / `motionPermissive` (24 hits), `CauseGone` /
  `causeGone` (21), `safetyDemandClear` (17), and the premise sweep
  `F-CPU`, `safety-rated`, `onboard safety`, `server-visible`, `Five new global
  DBs`, `five subfolders`, `18 nodes`, `five groups`, `last action of the FB`,
  `exactly one statement`. Every hit was read in context. Two were false as
  written and are amended (§2, §12); one was a server-visibility claim that
  needed the four mirrors named (§3.1); the rest are **set-scoped and true about
  the set they are about** — §4.2's five DBs, §4.3 and §10's five subfolders and
  18 nodes, §9's five groups — in the sense `opcua-nodes.md` §9.8 and §11.8 fix,
  and §13.4 states the new totals (six subfolders, 22 nodes under `Forklift/`,
  37 on the interface) rather than editing those sentences.
- **`emergency` and `protective` appear nowhere in §13** and nowhere new in the
  file; both still occur only in §2's statements of what this cell does not have.
  `EStopDemand` is used only as the F-side tag and node name `opcua-nodes.md`
  §11.2 rules correct.
- **Tool-derived values are stated as read-backs**: the browse path
  `Objects/ServerInterfaces/DemoCell/Forklift/Safety/EStopDemand` and the URI
  `http://DemoCell` are what the owner should *read back*, never fields to type,
  and §13.4 says the node counts and the refused write are design values until
  recorded with their date (ADR 0006; LESSONS 2026-07-27).

## Open questions and requests

1. **`plc/forklift-safety/SPEC.md` §8 should gain the four mirror rows** beside
   its Group 2, where their sources already are — a mirror is worth reading only
   beside the value it copies. Not taken here: the m5a-04b brief run in the same
   session requires every other section of that file to stay byte-identical.
   Carried as §13.8 item 1.
2. **The logic double is now behind §7** (`plc/forklift/double/`). It
   transliterates the M4 permissive and models no F-flag, so it neither breaks
   nor covers the delta — it does not parse the spec, it is a hand
   transliteration. A kernel for the delta would be cheap (one flag, one
   conjunct, the enable-edge-after-clear case) and is §13.8 item 4.
3. **§12 open item 9's cycle-time measurement now has a second reason to be
   taken**: OB30 carries two FBs and the CPU additionally runs an F-OB. Recorded
   as §13.8 item 5; the F-OB's own cycle and monitoring times stay
   `plc/forklift-safety/SPEC.md` §4.3.
4. **Nothing in §13 is verified.** The delta has not been compiled, downloaded or
   run by its author, who has neither tool installed. F5 of the safety spec's
   feasibility checkpoint — a standard block reading `InstF_Forklift_Safety` and
   compiling — is the single precondition the whole delta rests on, and it is
   unanswered.
