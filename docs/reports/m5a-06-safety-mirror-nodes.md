# Report m5a-06 — the `Forklift/Safety/` mirror node group

```
brief:               docs/briefs/m5a-06-safety-mirror-nodes.md
status:              done
files_changed:       docs/interfaces/opcua-nodes.md (new section 11, +322 lines,
                     nothing removed, sections 1-10 byte-identical)
                     docs/reports/m5a-06-safety-mirror-nodes.md (this file)
invariants_touched:  none
```

## What it is

`docs/interfaces/opcua-nodes.md` §11, *Forklift safety mirrors (M5 early)*, in eight
subsections: the path ruling, the four nodes, ownership and access rights, the
seven never-do rules, the TIA click path, start values and the fallback,
deliberately-absent, and the §10 seam with seven open items.

Its first three paragraphs are the required opening: the mirrors are display
diagnostics, no client write can create, prevent or clear a safety reaction, and
the safety demand never traverses the network — the mirror of it does.

## Rulings taken

| # | Ruling |
|---|---|
| **R-1** | **The path is `DemoCell/Forklift/Safety/`** — a sixth subfolder in the `Forklift/` subtree, on the existing `DemoCell` interface, per ADR 0006 discipline (nothing renamed, no second interface, the derived URI untouched). This is the resolution `plc/forklift-safety/SPEC.md` §6.4 note 2 suggested and left to this document, **and it also answers a question ADR 0007 routed here by name**: *"Whether the mirrors appear in the M1 `Safety/` group or in the cell interface is an interface question, requested and not decided here."* |
| **R-2** | **Why the bare `Safety/` path is forbidden, in five parts.** §4 already defines `Safety/SafetyResetRequired` for the fixed cell and the twin's F-flag carries that exact leaf, so the bare path is **one full browse path for two values** — one node, two writers, two meanings, invariant 10 broken at the node. Neither leaf can move (§4's is cited by name in `SRS.md` §4; the twin's is fixed by CLAUDE.md §9's diff rule), so the **path** is the only part of the address that can. The distinct path also **costs no edit to any existing sentence**: `SRS.md` §4/B1, `handshake-tables.md` §1 and its §6 four-node enumeration, and `roadmap.md` row M5 all stay true untouched — a merged group would have made that enumeration incomplete. And it **keeps §9.8's refusal row alive**, which ADR 0007 predicted would be voided: §11 adds nothing to §9's four folders |
| **R-3** | **The BrowseNames are the four F-side tag names exactly, with no prefix**: `EStopDemand`, `ZoneStopDemand`, `SafetyResetRequired`, `SafetyResetFault`. The brief's suggested `SafetyEStopDemand` / `SafetyZoneStopDemand` are **superseded by the F-spec's coupling contract**, which the brief itself makes authoritative. CLAUDE.md §9 requires a node name to mirror its PLC tag exactly, and `plc/forklift-safety/SPEC.md` §3.2 states these mirrors diff against those tags; a prefix would break a three-way diff (this table / the TIA export / F-spec §6.1) and would be the only renamed mirror in the project. The departure from §10.3's `Forklift`-prefix convention is stated: that convention answers *"which client may write this?"*, and here the answer is *none* for every node |
| **R-4** | **`SafetyResetFault` becomes a mirror node** — the fourth-flag decision F-spec §6.4 note 1 left open. It is what this group is; AT-08 (a)'s "reset-fault flagged" half otherwise has no observable outside TIA; it costs one Bool in a DB being created anyway; and the watch table keeps it either way. Whether it becomes a **lamp** stays `hmi/`'s decision and the HMI's three-lamp ask is not enlarged |
| **R-5** | **A new global DB `ForkliftSafetyMirror`**, not new members of `ForkliftStatus` — adding members moves the offsets of the four M4 status tags that live watch tables and evidence depend on (§10.3, LESSONS 2026-07-28). The name deviates from the `Forklift<Folder>` pattern by one word deliberately: `ForkliftSafety` would sit one underscore from `F_Forklift_Safety [FB2]`, and `Mirror` carries the distinction into every fully qualified tag and screenshot |
| **R-6** | **Owner and writer are separate roles, both single.** The **value owner** is the F-program (`InstF_Forklift_Safety`) for all four; the **node writer** is the standard program, copying. Stated with its consequence: **the group has zero PLC readers** — it is a leaf of the data flow, the permissive term is derived from F-data directly, and *if any logic ever reads a mirror the group stops being diagnostics and becomes a causal element*. That is checkable by cross-reference rather than by assertion |
| **R-7** | **Read-only rests on two independent reasons, not one checkbox.** *Writable from HMI/OPC UA* ✘ per tag (CPU enforcement, MR1) **and** the mirrors feeding no logic under an unconditional every-cycle rewrite, so a write that somehow landed would be a display artefact shorter than one PLC scan (MR2) |
| **R-8** | **A mirror's start value is its source's start value, not the type's zero**: `TRUE`, `TRUE`, `TRUE`, `FALSE`, matching the F-side at every CPU start. A display reading "clear" before the first copy is the boot-polarity defect LESSONS 2026-07-28 records for `BridgeLinkOk`, one layer up — **"not yet written" is not "clear"** |
| **R-9** | **The bridge is deliberately not a reader.** The reason is the M5 criterion itself: the reactions must execute with the bridge stopped and the session down, so evidence of an F-demand must not come from the client that has to be able to be dead. Readers are the HMI (display) and the owner at the watch table. `bridge-design.md` and the bridge's test double therefore need no change, and its 33-node count stands |

## The verification step this section asks for

§11.5 step 6 asks the owner to browse with a non-bridge client, read the four
start values, **and then attempt one write and record the refusal with its status
code**. A read proves the nodes exist; only a refused write proves the read-only
claim, and the M5 criterion is a statement about what a client *cannot* do. Its
one honest gap is recorded as open item 3: whether the per-tag *Writable* ✘ also
governs the auto-published `DataBlocksGlobal` path is **expected, not verified**
(§9.8 records that path is not otherwise write-protected at commissioned
settings). MR2's second reason is what keeps that outcome off the safety path.

## The seam this brief could not close

**§10.11's first row says "no safety node, safety mirror, e-stop, protective stop,
STO or safety reset under `DemoCell/Forklift/`", and §11 adds four safety mirrors
under exactly that path.** The brief forbids changing section 10, so the seam is
analysed inside §11 and the cross-reference is **requested, not taken** (§11.8
item 1). Until it lands, the document reads as contradicting itself at §10.11.

The analysis, so the follow-up brief does not have to redo it: the row is not an
error and its invariant-1 half is unchanged — no node in §11 is on a safety path.
**What expired is its premise** ("this plant has no F-CPU"), which ADR 0009
replaced with a 1513F-1 PN running an F-runtime group. The exception is bounded
to four read-only mirrors, so the rest of the row stands word for word. Three
pointers are needed: the §10.11 row, §10.3's folder tree (five subfolders, now
six) and §10.3's node count (set-scoped and true, but silent about this group).
Counts stay set-scoped in the §9.8 sense: §11 is exactly 4 nodes, §10's 18 is
still true of the M4 set, and the interface now carries 15 + 18 + 4 = 37.

Independently swept for scope-dependent statements, whitespace-normalised
(LESSONS 2026-07-27, 2026-07-29). One near-miss found and cleared rather than
edited: §9.6's *"`Safety/EStopActive` in §4 remains the only informational mirror
of SF-01"* stays **true** — §4 mirrors SF-01, and `Forklift/Safety/EStopDemand`
mirrors the twin's instantiation of *the logic of* SF-01, which is the very
distinction `TWIN-DEMO-MAP.md` §5 draws. Recorded as an optional fourth pointer.

## Requests — files outside this agent's scope

| # | Request | For |
|---|---|---|
| 1 | **`docs/interfaces/opcua-nodes.md` §10.11, §10.3 (tree and count) and optionally §9.6**: one cross-reference each to §11. The seam is analysed in §11.8; only the pointers are missing | An interface brief that is allowed to touch §10 |
| 2 | **`plc/forklift-safety/SPEC.md` §6.4 notes 1–3 and §10 open item 4 are answered** — group `Forklift/Safety/`, leaf names unchanged from the F-side, fourth flag gets a node. That document asks to be told and is outside this agent's write scope | A `plc` brief (LESSONS 2026-07-26: the requesting document is updated in the same change, and this one could not be) |

## Notes for the dependent briefs

- **m5a-05** now has final browse paths for its mirror-copy statements: four
  unconditional assignments per cycle, `"ForkliftSafetyMirror".<flag> :=
  "InstF_Forklift_Safety".<flag>`, name for name, published as
  `Forklift/Safety/<flag>`. The DB is new — no `ForkliftStatus` offset moves.
  §11.4 MR5 is the unconditional-write rule and §11.6 the start values.
- **m5a-07** has four nodes, not three. Three lamps remain the ask; the fourth
  node exists and displaying it is `hmi/`'s call. §11.6 fixes the degradation
  contract the brief asks for: an unresolved mirror renders **absent, never
  clear**, and no client's connect may fail over this group.

```
open_questions:
  1. Whether the per-tag Writable ✘ also governs the auto-published
     DataBlocksGlobal path. Expected from the attribute's placement on the DB
     member; unverified in the tool, and §11.5 step 6 asks for the refused write
     that would settle it.
  2. Everything in §11 is a design value until read back out of TIA (ADR 0006):
     the folder, the four BrowseNames, the per-tag rights and the start values.
     No gate criterion may rest on one before then.
  3. Whether the M5 criterion's mirror clause is eventually satisfied by this
     group, by a fixed-cell group, or by both. Left to the gate; §11 closes
     nothing and is not M4 evidence either.

next_suggested: m5a-05 and m5a-07 can both run now against final paths; the §10
cross-reference brief should follow before the verifier reads the node model.
```
