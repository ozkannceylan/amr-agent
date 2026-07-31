# Report mv-03 — the roadmap round for ADR 0013 and ADR 0014

```
brief:               issued in session, no file in docs/briefs/ (the round
                     ADR 0013 D1 names: "the number, the row and its final
                     criterion wording are a separate roadmap brief's")
status:              done
files_changed:       [docs/roadmap.md]
invariants_touched:  none
open_questions:      see below
next_suggested:      docs/TODO.md's header still calls M4 the open gate and the
                     m5r round in flight, both of which roadmap.md and PLAN.md
                     contradict; one tracking-reconciliation brief closes it.
```

## What changed, in four edits

**1. ADR 0013 lands as gate M8.** A new prose paragraph after the ADR 0012 one,
and a new table row below M7. The number is assigned here rather than in the
ADR, which deliberately assigned none (D1: this document is the single source
for gate numbering, LESSONS 2026-07-30). **M8** is the first free number after
the main line, and the row sits after M7 because that is where D1 places the
gate; M0–M7 keep their numbers and no existing criterion is touched, so the
round is an addition and not a renumber — stated in the paragraph so a later
reader does not go looking for a fourth renumbering round.

The paragraph carries the three things the row alone would not say: the
**placement reason** (TE9100 is at product-announcement status with its release
date "on request", verified 2026-07-31, and a gate between M5 and M6 would put
that unannounced schedule in front of the fleet gate, the LLM gate and the
recorded end-to-end demonstration), the **stage-0 owner probe as a hard
precondition** (D5.1, ADR 0006 discipline), and the **drift check as a
deliverable** rather than a review habit (D5.2, because M6's station handshakes
land in the node model before the mirror is built). The row summarises D2's five
criterion items (a)–(e) and states that the criterion is written entirely over
the standard program, with the safety mirror widening the demonstration and
conditioning no item.

**2. M5 item (d) corrected from "the arena" to the warehouse world**, with the
reason attached and the arena's M4 role preserved. This closes the
criterion-versus-work disagreement raised as open question 1 of
docs/reports/m5-08-warehouse-for-autonomy.md, which would have failed
verification with the criterion naming one world and the delivered work another.

**3. ADR 0014 gains a forward pointer** in the same style as those for ADR 0011
and ADR 0012: the loop closes onboard, no motion value crosses the OPC UA seam
at any granularity, ADR 0011 D3 and ADR 0012 D1 are confirmed rather than
refined, and ADR 0011 D1's "onboard" is bounded to the F-runtime group because
the standard program is the cell's PLC.

**4. The M5 showcase sentence carries ADR 0014 D5.** The showcase must now state
that in autonomous mode the PLC's authority over motion is permissive and
checked, not compelled — the PLC forms the envelope and does not enforce it, the
enforcing gate runs on the vehicle, and the compelling backstop is a safety
layer that is modelled rather than real — spoken where the autonomy is shown
rather than left implicit. This is narration, in the same shape as the existing
"naming which reactions are F-CPU safety functions" clause; **no new criterion
item was added**, per ADR 0014 D5's own statement that it changes no gate
criterion.

One consequential edit followed from the M8 row: the "four recordings" paragraph
asserts that a phase gate does not close on an unrecorded run, which M8 would
have contradicted. It now says M8 sits outside that count, its criterion closing
on committed evidence, and that the showcase question is open.

## What was deliberately not done

- **No showcase ruling for M8.** ADR 0013 leaves "whether the gate additionally
  carries a showcase recording in ADR 0007's sense" to this brief, and this
  brief was not instructed to rule it. It is recorded as open in the roadmap
  text rather than decided silently.
- **No PL, SIL, Category or PFH claim** appears in any added text; ADR 0011 D5
  is quoted only as the modelled-not-real disclosure D5 requires.
- **No criterion restated in new words** beyond the four changes. M0–M4, M6 and
  M7 rows are byte-identical to before.
- **ADR 0014 D5.3's readback-evidence obligation is not carried as a criterion
  item.** D5 states it changes no gate criterion, and turning "the evidence must
  exercise the §12.6 readback" into a roadmap item would widen M5. It stays an
  ADR obligation the M5 evidence briefs inherit.
- **docs/PLAN.md was not touched.** Its content is the current gate M5 and its
  brief queue; nothing there is made false by adding M8 or by the (d)
  correction. If the orchestrator wants M8's existence visible in PLAN, that is
  a separate one-line edit.

## Open questions

1. **The date of the world ruling is recorded two ways.**
   docs/reports/m5-08-warehouse-for-autonomy.md cites "the owner's 2026-07-30
   ruling" twice; the instruction for this round gave 2026-07-31. Rather than
   pin the wrong one into the live gate order, the corrected item (d) says "by
   owner ruling" with no date. Owner to confirm the date, after which one word
   closes it.
2. **M8's showcase question is open** (above), and with it whether the
   "recorded run" wording inside criterion item (c), which is ADR 0013 D2's own,
   implies a recording obligation the gate has not been given. Both are ruled at
   the M8 briefing, after M6 and M7.
3. **docs/TODO.md's header disagrees with roadmap.md and PLAN.md.** It opens
   with "M4 ... is the open gate, in closing; the m5r restructure round (ADR
   0010) is in flight", while the roadmap makes M5 the current gate and PLAN
   records m5r CLOSED 2026-07-30. TODO is outside this agent's write scope, so
   it is reported rather than fixed.
4. **The gate count in prose elsewhere in the repository has not been swept.**
   This round changed only docs/roadmap.md. CLAUDE.md §6's gate table, README's
   milestone table and any document that says "M0 to M7" or "eight gates" now
   trail the live order by one row — the LESSONS 2026-07-30 rule says every
   other table follows the roadmap via a brief, and that sweep brief has not
   been issued. It should start from a fresh whole-repo inventory that
   explicitly includes the contract file (LESSONS 2026-07-30, second entry).
5. **ADR 0013 D1 says the numbering brief is written "once M6 and M7 are
   settled".** They are settled as rows and numbers, which is what the
   numbering depends on, so the round was executed; but the ADR's own reading
   may have meant once those gates have closed. If the owner reads it the
   second way, the M8 row is early — it changes no other gate either way.
