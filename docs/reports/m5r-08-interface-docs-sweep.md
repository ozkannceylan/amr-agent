# Report m5r-08 — docs/interfaces/ gate-reference reconciliation per ADR 0010

```
brief:               docs/briefs/m5r-08-interface-docs-sweep.md
status:              done
files_changed:       [docs/interfaces/bridge-design.md,
                      docs/interfaces/opcua-nodes.md,
                      docs/reports/m5r-08-interface-docs-sweep.md]
invariants_touched:  none
open_questions:      see below (5)
next_suggested:      one interface brief for vda5050-subset.md's platform-derived
                     field values (seriesName, agvClass, agvKinematic), which
                     ADR 0010 D1 makes stale but which are field definitions, not
                     gate references.
```

## Sweep method

Every file in `docs/interfaces/` was searched **whitespace-normalised**
(`re.sub(r'\s+',' ',text)` over the whole file, so a phrase broken across a line
break still matches — LESSONS 2026-07-27) for: `M5`…`M12` tokens; gate names
carrying no number (*safety layer*, *simulated vehicle*, *vehicle gate*,
*navigation gate*, *VDA 5050 client*, *fleet manager gate*, *PLC integration*,
*arm gate*, *arm integration*, *demonstration gate*, *Hermes*); *later gate*,
*old M<n>*, *roadmap M<n>*, *gate order*, *renumber*, *deferred*, *parked*,
*early*; `RB-KAIROS` / `rbkairos`; and every `ADR 000n` citation, each read to see
whether it was cited **for gate order** (which ADR 0010 supersedes) or for
substance (which it does not).

The brief's location list was treated as a starting point and verified by
independent search. It named `bridge-design.md` §1 and items 8/15 and
`opcua-nodes.md` §11 status prose. The sweep confirmed items 8 and 15, and found
**one location the brief did not name**: `opcua-nodes.md` **§10.3's folder tree**
(line 559), whose `Safety/` comment also read *"M5 early"*. `bridge-design.md`
§1's table needed no edit — both its rows read `M3` and `M4`, which keep their
numbers.

Every hit was mapped from its **subject**, never by arithmetic on the number.

## Changes, per hit

| File / location | Was | Now | Why |
|---|---|---|---|
| `bridge-design.md` §12 item 8 | *"**Re-opened by ADR 0008 D1** … the vehicle gate is M6. `sim/`'s to correct"* | **Closed.** History kept (corrected → re-opened → closed); ADR 0010 named as superseding the ADR 0008 D1 shift; vehicle/navigation work is **M5**, on the in-house forklift, RB-KAIROS retired | ADR 0010 D1/D2/D7. The number was right and the platform was not — the item's assertion, not its history, was stale |
| `bridge-design.md` §12 item 15 | *"**Open, `sim/`'s.** ADR 0008 D1 shifted every gate above M3 by one, so the vehicle gate is M6 and this heading names the wrong one"* | **Closed by m5r-07, 2026-07-30**, quoting the heading now in force: `## Navigation scenario (RB-KAIROS, parked — resumes at M5 on the forklift)` | The requested fix landed in `sim/`; the requesting document is updated in the same change (LESSONS 2026-07-26) |
| `opcua-nodes.md` §10.3 folder tree | `Safety/   read-only F-safety mirrors (§11, M5 early)` | `(§11, M5 opening wave)` | Same term as `plc/forklift-safety/SPEC.md` (m5r-06). Not named by the brief; found by sweep |
| `opcua-nodes.md` §11 heading | *"Forklift safety mirrors (M5 early)"* | *"(M5 **opening wave**)"* | ADR 0010 D2 makes ADR 0009's early opening the opening wave of M5 itself |
| `opcua-nodes.md` §11 preamble | *"opens the cell-scope core of M5 **early** on the M4 forklift twin under a fallback rule"* | *"opens the cell-scope core of M5 **first**, on the M4 forklift twin, under a fallback rule"*, plus **one** new paragraph: *"Why this reads opening wave and not early, stated once for the whole section"* | The single reconciliation for this document. Names ADR 0010's **extension** of ADR 0009, the widened M5 and its landing on this twin, once — so no later occurrence re-argues it |
| `opcua-nodes.md` §11.8 | criterion mirror clause quoted as *"the `Safety/` mirrors are read-only and no client write can create, prevent or clear a safety reaction"*; *"…about the safety layer on the fixed cell; whether it is satisfied by this group, by a **fixed-cell group**, or by both is decided at M5"*; *"being built **early**"* | quote taken from `docs/roadmap.md` row M5 item (b) as it now reads; the safety layer is where **ADR 0010 D2/D7** land it — **this twin**; the deferral is now *"whether it is satisfied **as built**"*, kept open on the acceptance tests (AT-01/07/08) and the §11 open item 2 read-back; *"being built **first**"* | The old quote was the pre-ADR-0010 roadmap wording and no longer appears in `docs/roadmap.md`; a quote is taken as the source reads it |

**"Nothing here closes M5" stays true and stays written** — in the §11 preamble,
in the new paragraph, and in §11.8's opening sentence, all three unchanged in
force.

**M4 references untouched.** Only two removed lines in the diff contain `M4`, and
both are reflows that keep the reference verbatim (*"on the M4 forklift twin"*,
*"cited as M4 evidence … the M4 showcase"*). `git diff` shows no `M4` reference
deleted.

**No substance changed.** No node, BrowseName, datatype, access right, start
value, DB name, count, direction rule or design ruling was edited. `§11.1`'s path
ruling, `§11.2`'s four nodes, `§11.3`'s rights and `§9.8`'s set-scoped refusal row
are byte-identical. `bridge-design.md`'s two edits are both inside §12's
open-items table.

## Post-edit re-sweep

`docs/interfaces/` now contains **zero** `M6`–`M12` tokens. Surviving tokens:
`bridge-design.md` {M3, M4, M5}, `opcua-nodes.md` {M1, M3, M4, M5},
`handshake-tables.md` {M1}, `vda5050-subset.md` {M1}. Every `M5` was read
individually and names its ADR 0010 gate — including the six that already did
(§11.1's two `docs/roadmap.md` row M5 citations, §11.5's *"the M5 criterion is a
statement about what a client cannot do"*, §11.8's opening sentence, and open
item 4's *"the reactions must execute with the bridge stopped"*), all of which
survive the widened M5 unchanged because the new criterion item (b) carries those
clauses forward. The two surviving `RB-KAIROS` mentions in `bridge-design.md` are
inside sentences that state the retirement or quote the corrected `sim/` heading.

ADR citations were checked for purpose: the only two cited **for gate order** were
the ADR 0008 D1 references in items 8 and 15, both now superseded in place. Every
`ADR 0004`, `ADR 0005`, `ADR 0007`, `ADR 0008 D5` and `ADR 0009` citation is cited
for substance (bridge role, no-logic-in-the-bridge, the mirrors question, the
forklift-is-plant ruling) and stands untouched.

## open_questions

1. **`vda5050-subset.md` carries a retired platform, and it is not a gate
   reference.** Line 261 reads *"Vehicle series (**RB-KAIROS** per ADR 0002)"*,
   line 263 sets `typeSpecification.agvClass` = `CARRIER`, and line 262 leaves
   `agvKinematic` to "match platform". ADR 0010 D1 retires RB-KAIROS and makes
   the in-house forklift the vehicle platform from M5 onward, so all three are
   stale. **Not edited**: these are field-value definitions, which this brief
   forbids changing, and the kinematic value depends on the forklift's steering
   model — a decision for M5/M6 briefing, not for a sweep. Wants its own
   interface brief.
2. **§11.8's quoted criterion clause was requoted, not just renumbered.** The old
   quote is not in `docs/roadmap.md` any more; the current row M5 item (b) says
   *"the `Safety/` mirrors remain read-only"*. Flagged because the brief forbids
   substance changes and a quote is closer to substance than a gate number is.
   The clause's meaning is unchanged.
3. **§11.8 lost the "or by a fixed-cell group" alternative.** ADR 0010 D2/D7 land
   the M5 safety layer on the forklift twin and send the fixed cell's F-I/O to M6
   with its stations, so a fixed-cell group at M5 is no longer contemplated. Read
   as a consequence of the ADR rather than a new ruling — the deferral itself is
   kept, now on *"satisfied as built"*. One-sentence revert if the orchestrator
   reads it as a ruling this agent should not have taken.
4. **`bridge-design.md` §12 item 14's `plc/` half is still open and was not
   touched.** `plc/demo-cell/SPEC.md` §4.3's *"Nothing else goes into the
   interface"* is still scope-stale; m5r-06 swept gate references only, and this
   is not one. It wants a line in a later `plc/` brief, and item 14 already
   states the request.
5. **Items 8 and 15 both close, so `bridge-design.md` §12 now carries three open
   rows (10, 12, 14) instead of five.** No other document in the tree references
   either item by number (checked), so nothing else needs updating — but the
   orchestrator's `docs/TODO.md` may carry them.
