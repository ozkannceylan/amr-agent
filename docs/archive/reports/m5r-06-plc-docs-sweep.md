# Report m5r-06 — plc/ gate-reference reconciliation per ADR 0010

```
brief:               docs/briefs/m5r-06-plc-docs-sweep.md
status:              done
files_changed:       [plc/demo-cell/SPEC.md,
                      plc/forklift/SPEC.md,
                      plc/forklift-safety/SPEC.md,
                      docs/reports/m5r-06-plc-docs-sweep.md]
invariants_touched:  none
open_questions:      see below (4)
next_suggested:      align m5r-08's opcua-nodes.md §11 wording with the
                     "M5 opening wave" term used here, so the two documents
                     name ADR 0009's opening the same way.
```

## What was swept, and how

Every file in `plc/` was searched **whitespace-normalised** (line breaks collapsed
before matching) for `M5`…`M12` tokens and for gate names carrying no number
(*safety layer*, *simulated vehicle*, *VDA 5050 client*, *fleet manager*, *PLC
integration*, *demonstration*, *arm*, *Hermes*, *showcase*, *criterion*,
*roadmap*, *gate*). The brief's location list was used as a starting point only
and was verified by independent search; it was accurate, and the search found no
additional stale live reference. `plc/forklift/double/` (the executable stand-in,
its evidence and its config) carries no gate reference above M4.

Every hit was read for its **subject** and mapped from that, never by arithmetic
on the number. All `M3` and `M4` references, the `Forklift M4 gate` watch table
and every other TIA artifact name are untouched. No program logic, no test
procedure step, no pass count and no evidence claim changed.

## Changes, per hit

| File | Was | Now | Why |
|---|---|---|---|
| `demo-cell/SPEC.md` §12 | *"…SF-01…SF-08 \| `SRS.md`, gate M9"* | gate **M5**, **and M6 for SF-05 and SF-06** | Subject is the safety functions. ADR 0010 D7 lands SF-01/02/03/04/07/08 at M5 and SF-05/SF-06 at M6 with the stations, so the row spans two gates and now says which is which |
| `demo-cell/SPEC.md` §12 | *"The M1 target-cell logic … \| Gate M8"* | **Gate M6** (ADR 0010 D3) | Subject is the target cell's conveyor handshake, door and charger — fixed equipment, which merges into the fleet gate |
| `forklift/SPEC.md` §7 comment, §13 heading | *"the M5-early coupling delta"* | *"the M5 **opening-wave** coupling delta"* | ADR 0010 D2 makes ADR 0009's early opening the opening wave of M5 itself. Banner comment re-padded to its original 77-character width; no code changed |
| `forklift/SPEC.md` §13 | — | one new paragraph, *"Why this reads opening wave and not early"* | The single reconciliation for this document. States that ADR 0010 **extends** ADR 0009, so D3's coupling architecture and §13's three non-weakening statements are unchanged |
| `forklift-safety/SPEC.md` title | *"(M5 early, cell-scope core)"* | *"(M5 **opening wave**, cell-scope core)"* | Same reconciliation, in the document's self-description |
| `forklift-safety/SPEC.md` §1.2 **N5** | *"the recorded cell + safety showcase … the accurate statement is 'M5's cell-scope core is being built early'"* | widened-M5 statement + *"being built **first**"* + a definition of **"M5 proper"** | The one place the SPEC explains its own status. Names ADR 0010 D2's widened M5 (safety scanners on the F-side, navigation stack, HMI v2, **safety + autonomy** showcase) once, so no later occurrence re-argues it |
| `forklift-safety/SPEC.md` §1.2 **N7** | SF-02/03/04 + vehicle SF-08 *"at M6"*; SF-09 *"at M7"*; SF-05/06 *"at M9"* | **M5** (vehicle-chain content of the same gate); SF-09 **M6**; SF-05/06 **M6** | ADR 0010 D7 states all three landings explicitly — SF-09 was **not** ambiguous. The row's heading now reads *"out of scope **of this document**"*, because after the merge the vehicle chain shares this document's gate and a bare renumber would have made the row self-contradictory |
| `forklift-safety/SPEC.md` §6.4 | fixed-cell `Safety/SafetyResetRequired` *"(SF-08, M9)"* | **(SF-08, M5)** | Subject is the **fixed cell's instance of SF-08**, which lands at M5 with its vehicle instance. **Corrected — see the correction note below** |
| `forklift-safety/SPEC.md` §10 | *"Real F-I/O, M5 proper"* | *"Real F-I/O **on the forklift twin**, M5 proper — the forklift's F-I/O is M5 content, while the fixed cell's F-I/O **behind SF-05 and SF-06** arrives with the stations at M6 … SF-08 is M5 in both its instances"* | Says which F-I/O, as the brief's ruling requires; narrowed in the same correction so no reader can take "the fixed cell's F-I/O" as an SF-08 claim |

## Deliberately left unchanged

- **`plc/README.md`** — its only gate reference is M4 (line 19). Untouched.
- **`forklift-safety/SPEC.md`** lines 29, 123, 196, 1142 and the three *"M5
  proper"* cells of §9.2 — each already names M5, which is still the right gate.
  N5 now defines *"M5 proper"* once, so those cells were not re-argued per
  occurrence.
- **`forklift/SPEC.md`** line 1597 (*"`SRS.md`, gate M5"*): the subject is the
  **twin's** safety functions, all of which land at M5 under ADR 0010 D7. The
  meaning holds; verified rather than assumed.
- All ADR 0009 citations. ADR 0010 extends ADR 0009 and does not supersede it,
  so ADR 0009 stays the authority for scope, coupling and fallback; ADR 0010 is
  cited only where it is what moved the landing point.

## open_questions

1. **The demo-cell §12 safety row now names two gates.** The brief ruled
   line 1683 → M5, but the row's subject is `SF-01…SF-08`, and ADR 0010 D7 puts
   SF-05 and SF-06 at M6. A bare "M5" would have been a knowingly incomplete
   reference, so the row names both. If the orchestrator wants the brief's
   literal single-gate form, this is a one-line revert.
2. **"The carried TODO item" near demo-cell lines 1683/1684 could not be
   identified.** There is no literal `TODO` anywhere in `plc/`, and no item in
   §12's *Open items carried out of this specification* table is closed by these
   two lines or by anything else in this sweep. Per the brief's *"otherwise
   leave it"*, nothing was closed. If a specific item was meant, name it.
3. **`forklift/SPEC.md` §12 open item 7 is stale but out of this brief's
   scope.** It records that `plc/README.md` has no `forklift/SPEC.md` row and no
   forklift boundary sentence; both now exist (README lines 19 and 32–36). It is
   not a gate reference, so it was not touched. It wants a one-line closure in a
   later plc brief.
4. **Cross-document term choice.**  `docs/interfaces/opcua-nodes.md` §11 and its
   folder-tree line still read *"M5 early"* and are the subject of the parallel
   brief m5r-08. This sweep chose **"M5 opening wave"** for `plc/`. If m5r-08
   picks different words, the two documents will describe the same status
   differently — worth fixing the term in one place before both land.

## Correction — SF-08 is M5, not M6 (applied after the first pass)

**The brief's enumeration was wrong, and the first pass followed it.** The
location list read *"1024 (fixed-cell SF-08 'M9' → M6)"*, so §6.4's fixed-cell
`Safety/SafetyResetRequired` note was renumbered to M6. That mapping does not
survive an authority check, and the correction was raised by the orchestrator as
**m5r-09 finding 6**:

- **ADR 0010 D7** sends only **SF-05 and SF-06** to M6 (with the stations) and
  **SF-09** to M6. It places *"SF-01, SF-07 and the cell instance of SF-08 at
  M5, on the twin"* and *"SF-02, SF-03, SF-04 and the vehicle instance of SF-08
  at M5"*.
- **`docs/safety/SRS.md` §4**, as remapped by m5r-05, line 185: `SF-08 |
  Monitored reset | OPC Safety/SafetyResetRequired | AT-08 | M5 (cell and
  vehicle instances, one gate)`.

Both instances of SF-08 are therefore **M5**. Two lines changed:

| Line | Was (first pass) | Now |
|---|---|---|
| `plc/forklift-safety/SPEC.md` §6.4, line 1024 | *"`Safety/SafetyResetRequired` for the **fixed cell** (SF-08, M6)"* | **(SF-08, M5)** |
| `plc/forklift-safety/SPEC.md` §10, line 1348 | *"…while the fixed cell's follows its equipment to M6 (ADR 0010 D2, D3)."* | *"…while the fixed cell's F-I/O **behind SF-05 and SF-06** arrives with the stations at M6 (ADR 0010 D2, D3). **SF-08 is M5 in both its instances** (SRS §4)."* |

The second line was not itself wrong — it spoke of F-I/O following equipment,
not of SF-08 — but it sat two rows from the defect and could be read as
inheriting it, so it now names which F-I/O follows the stations and states
SF-08's landing outright.

**Re-swept by subject, not by the corrected line.** Every occurrence of `SF-08`
and of `SafetyResetRequired` in `plc/forklift-safety/SPEC.md` (36 hits,
whitespace-normalised) was re-read with 160 characters of context on each side;
five carry a gate number, and after this correction none of them places SF-08 at
M6. The only M6 landings left anywhere in `plc/` are SF-09, SF-05/SF-06, the
target cell's fixed equipment and the fixed-cell F-I/O behind SF-05/SF-06 — each
of which ADR 0010 puts there by name.

This is LESSONS 2026-07-29 again, from the other side: a brief's enumeration is a
starting point for *where to look*, never a ruling on *what the answer is*. The
first pass verified the location list by independent search but took its
per-line mappings as given; the mappings needed checking against ADR 0010 D7 and
the SRS the same way the locations did.
