# Report m5a-04c — the safety SPEC records the as-built edge networks

```
brief:               docs/briefs/m5a-04c-asbuilt-edge-networks.md
status:              done
files_changed:       plc/forklift-safety/SPEC.md (§5.0 note 4 promoted, §5.1
                     networks 3, 4 and the new 14, §3.3 statics, §3.2 as-built
                     note, §1.1 diagram, §2 F2, §3.0 D3, §4.2 steps 4/6/7,
                     §5.2, §8 Group 3)
                     docs/reports/m5a-04c-asbuilt-edge-networks.md (this file)
invariants_touched:  none
open_questions:      one — §5.0 note 6's ordering rule needed an explicit
                     exception, described below
next_suggested:      record the live-verified T6 rows against the F-collective
                     signature they were taken on, in an evidence file of their own
```

## What the primary text now describes

`R_TRIG` and `F_TRIG` are not offered in this CPU's safety instruction set, so
the note-4 fallback **is** the build and now reads as the build:

| Network | As built |
|---|---|
| **N3** `ResetRise` | `AND` of `ResetButtonPressed` and *(negated)* `ResetMemory` → `=` coil |
| **N4** `ResetFall` | `AND` of *(negated)* `ResetButtonPressed` and `ResetMemory` → `=` coil |
| **N14** `ResetMemory` | `=` coil driven from `ResetButtonPressed`, **last network**, after every reader of either edge |

**The counts follow**: fourteen networks and fourteen written operands (§5.0
note 1, §5.1's heading, §1.1's diagram, D3, and click-path step 6), and **ten
statics** — `ResetRiseEdge` and `ResetFallEdge` are gone and `ResetMemory`
replaces them (§3.3, click-path step 4, and step 7, which now offers the
multi-instance dialog for the two `TON`s alone). §3.2 gains an as-built note:
D1–D7 fully applied, interface **3 in / 4 out / 10 static / 2 constant**, the
call's three input pins bound and all four output pins empty — §3.4's write set
as a fact rather than an instruction.

**The `R_TRIG`/`F_TRIG` form is kept, and marked.** §5.0 note 4 carries it as an
indented block headed *"for a CPU that has them — not this build"*: networks 3
and 4 become the two boxes with their multi-instances, network 14 disappears and
`ResetMemory` with it, static count 10 → 11, and **nothing else moves**. It
appears nowhere in §5.1.

**§2 check F2 is answered in the tool**, dated: `RS`, `SR` and `TON` present,
`R_TRIG` and `F_TRIG` absent. The row now also says which of the three has no
substitute — the timer — and that it is present, so §2's fallback does not apply.

## The finding: the ordering rule needed an exception, and it is the whole mechanism

§5.0 note 6 read *"No network reads a value that a later network writes. The
order is the design."* A manual edge **must** break that rule: networks 3 and 4
read `ResetMemory`, network 14 writes it, and what those networks need is the
**previous** F-cycle's value — which is exactly what a variable written after them
still holds. Left unamended, the rule reads as an invitation to "repair" the
forward reference by moving network 14 up, and:

> network 3 would compare the device against itself, `ResetRise` would never be
> `TRUE`, no press could ever be armed, and **no reset could ever succeed** — a
> failure that looks exactly like a broken reset device.

Note 6 now states the single exception and names the symptom; network 14's own
notes repeat it; click-path step 6's *"the order is not cosmetic"* cell names
network 14 as the deliberate exception that stays last. This was not in the
brief's done_when — it surfaced from transliterating the network order, which is
the habit LESSONS 2026-07-29 asks for.

Two smaller points recorded while I was in there: `ResetMemory` starting `FALSE`
reproduces `R_TRIG`'s boot behaviour exactly — a device already pressed at the
first F-cycle **does** produce a rising edge, still refused downstream by
`ResetSeenOpen` rather than suppressed — and network 14 must be an `=` coil, not
an `S`/`R` pair, or the memory sticks and the falling edge never forms.

## Verification

- **Per-section `sha256/16` against `HEAD`**: **36 of 46 sections byte-identical**,
  9 changed, §5.1 renamed (thirteen → fourteen). No section added or removed
  beyond that rename.
- **Per-network hashes inside §5.1**: **N1, N2, N5–N12 byte-identical**, N3 and
  N4 rewritten, N14 new. N13 reports as changed **only because the `---`
  separator introduced before N14 falls inside its chunk** — the `git diff` hunk
  at that point is pure insertion after N13's last line, with no deletion, and
  N13's prose is untouched.
- **No demand-latch or reset-window semantics changed**, which the forbidden list
  protects and the hashes prove: N11, N12 (the `RS` set-dominant latches), N5,
  N6, N7, N9 (the arming and both bounds), §5.2's latch table and §5.3's six
  refusals are all byte-identical. **§9's T6 procedure is untouched — 26 steps,
  section byte-identical.** §6, §7 and §10 likewise.
- **Sweep**: `thirteen`, `Thirteen`, `13 networks`, `eleven statics`, `four
  instances` — **all zero**. `R_TRIG` 8 hits and `F_TRIG` 5, every one read in
  context: the F2 row (says they are absent), §3.2's as-built note (says why the
  static count is 10), §3.3's `ResetMemory` row and N3's notes (compare the hand
  form to what an `R_TRIG` would have held), and the marked not-this-build block.
  **No sentence presents them as the build.** `ResetRiseEdge` and `ResetFallEdge`
  survive only inside that block.
- **Structure**: 39 tables, none ragged; no `deadline`, no tooling mention.
- **`git diff`**: 19 hunks, `+107 −34`. Line endings `i/lf w/lf`.
- **Not verified by me**: the as-built facts are the owner's 2026-07-30 handover,
  including the live-verified reset (arm → 200 ms hold → release → both latches
  clear), the upper bound twice, and the mirrors tracking within one scan. I have
  neither tool installed and this document still claims no execution.

## One request

The live-verified behaviour the brief reports — end-to-end monitored reset, the
3 s bound refusing twice, mirrors tracking the demands within one scan — is
**evidence, and it has no file**. §9's pass rules require a pass claim to name the
**F-collective signature** it was taken against, and none is recorded anywhere
yet. An evidence file under `plc/forklift-safety/` recording those runs with the
signature, the date and which T6 rows they cover would close the gap; it is not
this brief's deliverable and I have not created it.
