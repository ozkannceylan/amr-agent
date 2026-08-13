# Report m5a-04b — the safety SPEC learns the mirror ruling

```
brief:               docs/briefs/m5a-04b-safety-spec-crossrefs.md
status:              done
files_changed:       plc/forklift-safety/SPEC.md (§6.4 rewritten against the
                     ruling; §10's "does not specify" mirror row and open
                     item 4 closed)
                     docs/reports/m5a-04b-safety-spec-crossrefs.md (this file)
invariants_touched:  none — prose only. No network, tag, constant,
                     watch-table row or T6 step moved
open_questions:      one, see below — §6's preamble still claims authority over
                     the mirror node group, which §11 now shares
next_suggested:      hmi/ brief for the safety lamps (§11.8 item 5), which is
                     the last consumer of this ruling that has no owner
```

## What changed

**`plc/forklift-safety/SPEC.md` §6.4** no longer describes the mirror ruling as
pending. It reads it back from `docs/interfaces/opcua-nodes.md` §11 (commit
`2d2d497`, 2026-07-29) and states the division of authority in one sentence:
**§11 is authoritative for what the nodes are called, which block holds them and
who may read them; §6 stays authoritative for what the flags mean** — which is
§11's own preamble read from the other side.

| Note | Was | Is |
|---|---|---|
| **1** | "Whether it becomes a mirror node is an interface decision" | **Ruled: `SafetyResetFault` is a mirror node** (§11.2), with the reason §11 decided on. The watch-table row stays regardless — §8 Group 2 reads F-data directly, so the node is an addition to that instrument and never a replacement. The **lamp** question is `hmi/`'s, not the interface's |
| **2** | "the obvious resolution is a distinct path … **That is an interface ruling and is not taken here**" | **Ruled: `DemoCell/Forklift/Safety/`**, a sixth subfolder in the `Forklift/` subtree of the existing `DemoCell` interface, not the top-level `Safety/` group (§11.1). Records *why the path moved rather than a leaf*: §4's leaf is cited by name in `SRS.md` §4 and the twin's is fixed by its F-tag and CLAUDE.md §9, so the path is the only part of the address neither side owns. Adds §11.2's no-prefix ruling, which is what makes this document, the TIA export and §6.1 diff three ways |
| **3** | "they must never share a lamp or a sentence either" | Same rule, now with the resolution: the two flags differ in **both folder and leaf**, and their reset *inputs* sit on opposite sides of the client boundary — one a client write, the other an F-input no client can reach (§11.1's three-values table) |
| **4** | (unchanged, byte-identical) | Ratified rather than edited: §11.6 states "an absent mirror renders as absent, never as clear" and cites this note |

Then the four values the brief asked to be citable **here rather than fetched**,
as a five-row table: **path**, **data block** (`ForkliftSafetyMirror`, and why
the word *Mirror* is in the name), **per-tag access** (✔/✘ per member, with
`InstF_Forklift_Safety` and `SafetyInputStandIn` at ✘/✘), **start values**
(`TRUE`, `TRUE`, `TRUE`, `FALSE`, because a mirror's start value is its source's,
not the type's zero), and **absence**. Closed with the property that decides the
group's character: **zero PLC readers** — the standard program writes the four,
no logic reads them, and the permissive term is derived from F-data directly
(§6.1, §6.2 S3, §11.3).

**§10, two cells.** Open item 4 becomes *Closed by `opcua-nodes.md` §11* with the
ruling's four values in the item and the two things still open **elsewhere** in
its status: the lamp (`hmi/`, §11.8 item 5) and the standard program's copy
statements (`plc/forklift/SPEC.md`, §11.8 item 7). The "does not specify" table's
mirror row no longer says §6.4 "names two collisions **to resolve**" — that was
the last sentence in the file reading as pending, and it was found by the sweep,
not by the brief's enumeration.

## Verification

- **43 of 46 sections byte-identical**, computed as a per-section `sha256/16`
  over the file split at every `##`/`###` heading, before and after. The three
  that moved are `### 6.4`, `## 10 …` (its "does not specify" table) and
  `### Open items carried out of this specification`. **No section was added or
  removed.** This is the discipline the document's own revisions use, run as a
  table rather than asserted.
- **`git diff` is four hunks in those three sections, `+56 −19`** — two in §6.4,
  because note 4 sits unchanged between them, and one in each §10 table. §5's
  thirteen networks, §5.2's latch table, §7's stimulus, §8's four watch groups
  and all **26 T6 steps** are therefore untouched — shown by the hash table, not
  claimed.
- **Sweep over `mirror`, whitespace-normalised** so a wrapped occurrence still
  matches (LESSONS 2026-07-27): **32 hits, every one read in context.** One was
  still pending — the §10 row above — and is fixed. The rest are architecture
  statements (§1.1's diagram, §1.2 N5, §3.0 D2/D7, §3.2, §3.4, §4.2 step 11,
  §6.2 S3/S5, §10's two other rows) that the ruling ratifies rather than
  contradicts, plus one unrelated sense of the word in §5.
- **Second sweep, by the phrasings a pending statement takes** rather than by the
  subject: `not taken here`, `interface decision`, `interface ruling`, `may or
  may not`, `to resolve`, `pending`, `is not taken` — **all now zero**, each
  having been non-zero before the edit or absent throughout.
- **Structure**: §6.4's new table is 4 data rows with a consistent column count
  and a header rule; the open-items table still has exactly items 1–7 with a
  consistent column count.
- **Line endings** `i/lf w/lf`, no CRLF anywhere in the file.
- No word of the deltas, networks, tags, constants or T6 steps changed, and the
  file mentions no date beyond the ruling's own commit date.

## Two things worth the orchestrator's attention

1. **§6's preamble still over-claims, and the brief forbade fixing it.** It
   reads *"This section is authoritative for the standard-side delta and for the
   `Safety/` mirror node group."* Since §11 landed, authority is **shared**:
   §11 owns the node names, the DB and the access rights, and §6 owns what the
   flags mean — which is what §11's preamble says and what §6.4 now states. The
   preamble sits in `## 6. The coupling contract`, a section this brief requires
   byte-identical, so it is **requested, not taken**: one clause, narrowing
   "authoritative for … the mirror node group" to "authoritative for what the
   flags in it mean". It is not a sentence that calls the ruling open, so the
   brief's sweep criterion is satisfied either way.
2. **The standard-side delta landed in the same session** as
   `plc/forklift/SPEC.md` §13 (m5a-05, commit `86ecbdc`), and it asks this
   document for one thing: **the four `ForkliftSafetyMirror` rows belong beside
   §8 Group 2**, where their sources already are — a mirror is worth reading only
   next to the value it copies. Not added here, because this brief requires §8 to
   stay byte-identical. It is carried as item 1 of that document's §13.8.
