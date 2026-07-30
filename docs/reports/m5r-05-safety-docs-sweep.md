# Report m5r-05 — docs/safety/ gate-reference reconciliation per ADR 0010

```
brief:               docs/briefs/m5r-05-safety-docs-sweep.md
status:              done
files_changed:       docs/safety/SRS.md
                     docs/safety/PL-SCENARIOS.md
                     docs/safety/TWIN-DEMO-MAP.md
                     docs/reports/m5r-05-safety-docs-sweep.md (this file)
invariants_touched:  none
open_questions:      five, below
next_suggested:      arch-docs rewrites docs/roadmap.md's gate table to ADR 0010
                     (M5–M7, arm row removed); docs/safety/ now names gates that
                     the roadmap table does not yet carry.
```

## What was changed

Gate references only, plus the arm out-of-scope marking. No trigger, reaction,
safe state, reset, acceptance sub-case, risk-graph parameter, PLr or PL target
was altered, and no SF or AT identifier was created, renamed or deleted.

**Mapping applied, by subject.** The SRS's numbers are the *first* numbering
(CLAUDE.md §6 as written at M2: M3 simulated vehicle, M4 VDA 5050 client, M7
safety layer, M8 demonstration, M9 arm). They predate the ADR 0004 round and the
ADR 0007/0008 round, so every reference was read for which gate *name* it means
and then mapped through ADR 0010's table:

| SRS printed | What the sentence is about | Now |
|---|---|---|
| M7 (AT-01, AT-08, SF-01/07/08 rows, header) | safety layer | **M5**, on the forklift twin |
| M3 (AT-02/03/04, SF-02/03/04 rows) | simulated vehicle / vehicle chain | **M5** |
| M7 (AT-05, AT-06 tags) | door and charger F-I/O with the stations | **M6** |
| M4 (AT-09, SF-09 row) | VDA 5050 client + broker | **M6** |
| M8 (AT-07 coupled Gazebo scenario) | coupled cell-and-vehicle run — see Q1 | **M6** |
| M9 (§1.3, SF-20…29 row) | arm gate | **removed, out of scope** |

**SRS.md** — header replaced with a "Gate references" paragraph naming ADR 0010
and the per-function landings; §1.3 rewritten as *out of scope — arm integration
removed from the roadmap (ADR 0010 D5)*, with the SF-20…29 block kept reserved,
its ids never reissued and its ADR 0002 expected contents kept as record; nine AT
gate tags remapped; §4's "Verified at gate" column remapped row by row and its
SF-20…29 row marked out of scope.

**PL-SCENARIOS.md** — §0's numbering note rewritten as prose against ADR 0010
(the old note asserted a third numbering, "the safety layer is M9", and promised
that the SRS's numbers would be left stale; both are now false). §3.1's SF-20…29
row carries the same out-of-scope marking. Found by independent sweep, not in the
brief's location list.

**TWIN-DEMO-MAP.md** — ADR 0010 added to the binding-documents table; the "Gate
numbers" note rewritten to state that one gate, M5 on the twin, now carries both
the safety layer and autonomy; §3's "M5 proper" identified as the F-I/O half of
that gate; NC-1's "They land at M6" corrected to M5 with the scanners and the
navigation stack; NC-6's M5 criterion extended with the vehicle-chain tests and
the recorded safety + autonomy showcase (ADR 0010 D2). M3 (demonstration cell,
panel mushroom) and M4 (teleop demonstration, R6) references were checked and
left: M0–M4 keep their numbers and criteria.

**Verification.** Whitespace-normalised sweep of all three files for `M0`–`M12`
tokens and for the gate names ("safety layer", "simulated vehicle", "arm gate",
"safety gate", "renumber", "roadmap", "RB-KAIROS"). Every surviving token is
M2 (this document's own gate), M3 or M4 (unchanged by ADR 0010), or a remapped
M5/M6/M7. No token was changed by arithmetic.

## Open questions

1. **AT-07's coupled Gazebo scenario — ruled M6, and the reasoning matters.**
   Read literally under the SRS's own numbering, "coupled Gazebo scenario at M8"
   means the *demonstration* gate, which ADR 0010 folds into **M7**. It is ruled
   **M6** instead because the live `docs/roadmap.md` already reassigned that item
   in an earlier round — its M9 row (PLC integration) reads "AT-07's coupled
   Gazebo scenario runs with a vehicle in the monitored zone" — and ADR 0010 maps
   PLC integration to M6. The subject therefore lands with the stations, not with
   the end-to-end run, and this agrees with the brief's ruling. If the owner
   reads that coupled run as part of the M7 demonstration instead, this is the
   one line to change.
2. **SF-09's landing is not ambiguous, but its halves sit apart.** ADR 0010 D7
   states "SF-09 at M6" and AT-09 needs a broker, which first exists at M6 — so
   both are tagged M6. Note that the vehicle software executing the degraded-mode
   stop arrives at M5; only its demand (supervision loss over MQTT) waits for M6.
3. **SF-02's "M7 review" half has no separate home.** The old tag split SF-02
   between sim behaviour (old M3) and a review at the safety gate (old M7); both
   collapse into M5, so the row now reads "M5 (sim behavior and review, one
   gate)". If the owner wants the review to stay a distinct later checkpoint, no
   gate currently carries it.
4. **docs/safety/ now leads docs/roadmap.md.** The roadmap still carries the
   ADR 0008 table (M5 safety on the fixed cell … M11 arm, M12 Hermes) and its
   two-round renumbering paragraph. Until arch-docs rewrites it, the three safety
   documents and the roadmap disagree; the ADR is the authority in the interim.
5. **NC-6 cites ADR 0010 D2 directly because the new M5 criterion text does not
   exist yet** (ADR 0010 explicitly leaves the gates' roadmap wording undecided).
   When the roadmap's M5 row is written, NC-6 should be re-read against it.

## Not done, deliberately

- Nothing outside `docs/safety/` was touched; the roadmap, PLAN and TODO
  corrections implied by items 4 and 5 belong to arch-docs.
- SF-20…29 rows were marked, never deleted, in both documents that carry them.
- No commit was made; the three files and this report are left modified in the
  working tree.
