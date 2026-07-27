# Report — m3-25 reconcile SPEC.md with the commissioned implementation

brief:               docs/briefs/m3-25-spec-commissioning-reconcile.md
status:              done
files_changed:       [plc/demo-cell/SPEC.md]
invariants_touched:  none
open_questions:      One new finding, recorded as §12 open item 5 and not acted on: `ConveyorBeltPosition` and `ConveyorBeltSpeed` carry no plausibility window, and a `NaN` position silently disarms both soft-limit aborts. Closing it changes control behaviour, which this brief forbids.
next_suggested:      A brief deciding §12 open item 5 — whether an affirmative window test on `ConveyorBeltPosition` is added to `WorldOk`, following the §6.2 form.

## What changed

Two defects, corrected at their source in `plc/demo-cell/SPEC.md`. No tag,
BrowseName, node count, constant, threshold or sequence transition was altered,
no owner PLCSIM observation was written into the document as specification text,
and the header's "specification, not verification" paragraph is untouched and
still accurate — it says nothing here was executed *by its author*.

### 1. The dwell timer, §7 part 7 (with §3.2, §6.5)

The call was `#DwellTimer(IN := TRUE, PT := #DWELL_TIME);` placed **inside**
`CASE` branch 20. Both halves of that are wrong and they are the same wrongness:
a literal `IN` can never go false, and a call site inside the branch it times
stops executing the moment the step is left, so even a correct `IN` would never
be evaluated as a release. The TON was therefore armed once and stayed done.

The fix is not a release statement bolted on at step exit; it is moving the call
to where the release happens by itself:

```pascal
END_CASE;
#DwellTimer(IN := (#SeqStep = 20), PT := #DWELL_TIME);
#StepTimer(IN := (#SeqStep = 10) OR (#SeqStep = 30), PT := #STEP_TIMEOUT);
```

`DwellTimer` now sits beside `StepTimer`, which was already written this way —
unconditional, outside the `CASE`, `IN` being the step-active condition. Branch
20 keeps `IF #DwellTimer.Q THEN #SeqStep := 30; END_IF;` and gained a comment
saying where the call went and why.

Traced against the surrounding code, all four exit paths release it: the normal
exit (branch 20 sets `SeqStep := 30`, the post-`CASE` call then sees `IN` false),
the `NOT #runPermissive` abort (part 6 sets `SeqStep := 0` *before* the `CASE`),
step 40, and the `ELSE` guard. Entry is clean too — the scan before step 20 is
entered had `SeqStep = 10`, so the timer was already released and `Q` false. The
dwell now costs `DWELL_TIME` plus one 20 ms OB call, and the second and every
later cycle dwells as the first did.

Supporting edits so the document does not disagree with itself: the §3.2 row for
`DwellTimer`/`StepTimer` states the unconditional-call rule; the §6.5 step table
notes the release; and §6.5 gained a normative subsection giving the `IN`/`PT`
table for both step timers, naming the two forbidden forms, and stating the
underlying rule — *a TON's `IN` is its release, so it must be an expression that
can go false, evaluated at a call site that still runs after the step has been
left.* It also records why the other six timers are not affected.

### 2. Range plausibility, §6.2 and §7 part 2, closing §12 open item 1

The open item was framed as "confirm the `IS_VALID` mnemonic in your TIA
version", which made the real question — *may the check be dropped?* — look like
a tooling detail. It is now answered with its condition attached.

`RangeValid` is stated as the affirmative `AND` of the two window comparisons,
with the fault taken in the `ELSE` (via `NOT RangeValid` into
`RangeInvalidTimer` → `SensorFaultLatch`). A normative block states that this
form is the mechanism, not a style preference, and carries a two-row table
showing the forms are equivalent for every real number and **opposite for
`NaN`**: affirmative gives `FALSE AND FALSE` → fault, while
`NOT (x < MIN OR x > MAX)` gives `NOT (FALSE OR FALSE)` → *valid*, passing a dead
photo-eye downstream as a measurement. `IS_VALID` is then described as optional
and redundant **given that form**, with the explicit statement that omitting it
under any other form is a defect and that anyone inverting the test must add the
check back in the same edit. The `IS_VALID` requirement is conditioned, not
deleted — it is still shown as a writable option with its TIA menu path.

The §7 sketch matches: the `IS_VALID` term is dropped from the expression with a
comment recording that it is redundant *only* because the test is affirmative,
plus an explicit "never invert this" warning at the call site where the mistake
would be made.

§12 open item 1 is removed from the table and closed in the prose beneath it,
alongside the previously closed reset-contact item. Items 2–5 renumbered to 1–4.
No file in the repository references SPEC.md's open items by number (checked),
so the renumbering breaks nothing.

## Independent sweep

Both patterns, whitespace-normalised over the whole document per the 2026-07-27
lesson on wrapped prose.

**Literal-`TRUE` timer inputs.** Regex over the normalised text for
`IN\s*:=\s*(TRUE|FALSE)` and for every `*Timer(IN := …)` call site. Before the
edit: eight call sites, exactly one defective (`DwellTimer`). After: all eight
carry real expressions. The three residual `IN := TRUE` string matches are in the
new prose that *forbids* the form.

**Negated out-of-window tests.** Every `NOT` in the document was listed with
context. All of them negate a Bool verdict — `#rangeValid`, `#hbChanged`, the
latches, the two `…CircuitClosed` contacts, `#ResetDeviceFault`,
`#latchPending`, `#runPermissive`, `#PosWindowArmed` — never a comparison
expression. The single near-instance is `#d1 := #cmdMoving AND NOT #beltMoving`,
where `#beltMoving` is an affirmative comparison; a `NaN` speed makes it false,
so `#d1` becomes *true* under a non-zero command. That falls to the fault side
and is correct as written. **No second instance of either pattern exists.**

Two things were checked and deliberately left alone:

- **`PresenceOnTimer` / `PresenceOffTimer` are called inside `IF #rangeValid`**,
  so they are not called at all while the range is implausible and retain `ET`
  and `Q`. Traced both directions: this is not the dwell defect. Their `IN` is a
  live comparison re-evaluated on the first call after `rangeValid` returns, and
  the `ELSIF` structure resolves a stale `Q` in that same scan. The only
  consequence is that the 100 ms filter may be skipped once on resumption, in a
  state where `SensorFaultLatch` has already dropped the cycle. Recorded in
  §6.5 as explicitly out of scope of the step-timer rule rather than left silent.
- **The plausibility gap on the other two Reals** — the new §12 item 5, detailed
  under open_questions above and tabulated in the document with the direction of
  each affected comparison, so that a later fix is not applied in the wrong
  direction or to the wrong tag.

Working tree: `plc/demo-cell/SPEC.md` only, +131/−27, index and worktree both
`i/lf w/lf`, and `git diff --numstat` equals `git diff --ignore-cr-at-eol
--numstat`, so every counted change is real content. Nothing committed.

## lessons_candidates

- 2026-07-27 | Fixed a never-released step TON by adding a release on step exit,
  as the implementation had done | The release statement is a second thing to
  remember and it lives in the branch that stops running; the call site was the
  actual defect, not the missing statement | Call a step's TON unconditionally
  outside the `CASE` with `IN` set to the step-active condition — then the step
  exit releases it with nothing to remember, and the same pattern covers the
  dwell and the watchdog identically.
- 2026-07-27 | An open item read "confirm the `IS_VALID` mnemonic in your TIA
  version" | It framed a correctness condition as a tooling lookup, so the
  implementer resolved it by deleting the call and no document recorded what made
  that safe | When a check is redundant only because of the form of the code
  around it, the open item states the form, not the check; a redundancy whose
  precondition is unwritten is a defect waiting for the next rewrite.
