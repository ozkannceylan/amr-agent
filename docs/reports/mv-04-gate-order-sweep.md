# Report mv-04 — sweep the gate order after M8

```
brief:               docs/briefs/mv-04-gate-order-sweep.md
status:              done
files_changed:       [CLAUDE.md, README.md, docs/TODO.md]
invariants_touched:  none
open_questions:      see below
next_suggested:      verifier re-reads CLAUDE.md §6 as the gate-criteria source
                     it is pointed at (.claude/agents/verifier.md line 15), now
                     that the row it was missing exists.
```

## Method — why this inventory is fresh

Started from `git ls-files` over all **611 tracked files**, not from any earlier
round's list, and ran two machine passes over every readable one:

1. **Whitespace-normalised subject sweep.** Each file's whitespace collapsed to
   single spaces before matching, so a phrase broken by a line wrap still hits
   (LESSONS 2026-07-27, the `sim/` "hold time" entry). Patterns: gate tokens
   `M0`–`M9` word-bounded; and the RANGE statements the brief named —
   `M0 to M7` / `M0–M7`, `<number> gates`, `last|final gate`, `after M<n>`,
   `above|beyond|past M<n>`, `M<n> onward`, `gate order|set|list|numbering`,
   `milestone table|list|order`, `end-to-end demonstration`, `four recordings`.
2. **Gate-name sweep.** The same pass keyed on the gate *names* rather than the
   numbers — "repo skeleton", "interface contracts", "safety requirements spec",
   "fixed equipment I/O loop", "forklift commissioning cell", "sensored
   autonomous forklift", "fleet at scale", "LLM operations layer", "vendor
   portability", "TwinCAT/Beckhoff" — because a gate list can enumerate the set
   with no `M` token in it at all and would be invisible to pass 1.

`CLAUDE.md` was included explicitly and read in full first, as the brief and
LESSONS 2026-07-30 require.

**False positives confirmed and discarded**, both as the brief predicted: brief
and report ids (`after m5-01`, `past m5-15`, `m4f-09`) carry round numbers, not
gate numbers; and CLAUDE.md §9's `not M12` is a PLC memory-marker example — it is
two digits and never matched the word-bounded token pattern anyway.

## What the two passes found

Pass 2 is the decisive one. Exactly **three live files enumerate the gate set**:

| File | Gate names present | Verdict |
|---|---|---|
| `docs/roadmap.md` | 10 (incl. vendor portability, TwinCAT) | the source |
| `CLAUDE.md` | 8 — stopped at M7 | **corrected** |
| `README.md` | 8 — stopped at M7 | **corrected** |

Every other live file mentioning a gate references *one* gate as the landing
point for its own work (`M6` for the station handshake, `M5` for the safety
functions, `roadmap M6 work` in the sim files). None states a set, a range or a
count, so none was made stale by an eighth row. `docs/PLAN.md` states the current
gate and the closed ones and agrees with `roadmap.md` on all of them.

## Changes

### 1. `CLAUDE.md` §6 — the M8 row

The table gained the M8 row, wording taken from `roadmap.md`'s row and compressed
to the summary length the other rows use. No criterion is restated in new words;
no gate is renumbered; M0–M7 are byte-identical.

The line under the table was also corrected: *"the live gate order (ADR 0010)"* →
*"(ADR 0010, with M8 added by ADR 0013)"*. That sentence is itself a statement of
which decision governs the order, and it named only ADR 0010.

### 2. `README.md` — the row, and two range statements

- **Milestone table** gained `| M8 | Vendor portability: a second Beckhoff/TwinCAT
  PLC layer | planned |`, in the short-row style of the rows above it.
- **"the LLM operations layer closes the program"** → *"closes the main line"*.
  M8 sits after M7, so "the program" was no longer the thing M7 closes;
  `roadmap.md` calls it the main line and that word is borrowed rather than
  invented.
- **"Each of the last three gates closes on its own recording"** → *"M4, M5, M6
  and M7 each close on their own recording."* This is the case the brief warned
  about: no number in the sentence was wrong, but "the last three" silently
  re-pointed from {M5, M6, M7} to {M6, M7, M8} the moment M8 landed — and M8 is
  the one gate that does **not** close on a recording. Replaced with the fixed
  set, which is also what `roadmap.md`'s four-recordings paragraph says.
- **A new paragraph** after the gate-order narrative states M8's placement and
  its reason, from `roadmap.md`: after M6 and M7 so no main-line gate waits on a
  vendor's release date, closing on committed evidence.

### 3. `docs/TODO.md` — the header only

Was: *"M4 … is the open gate, in closing; the m5r restructure round (ADR 0010)
is in flight."* Both halves were false against `roadmap.md` and `PLAN.md`. Now
states M5 as the open gate, M4 closing on the owner's recorded showcase and the
m4f-09 verification, and m5r closed. **The queues beneath the header were not
touched** — no item added, removed or reworded.

## Beyond the three named targets — one addition, flagged for the owner

`README.md` also carried **"Current gate: M4 — Forklift commissioning cell"**,
contradicting `roadmap.md` line 3 the same way the TODO header did. The brief did
not name it, but the sweep found it and fixing one instance of a falsehood while
leaving its twin in the public-facing file would be half a fix (LESSONS
2026-07-30, and 2026-07-28 on a lesson applied only to the input that taught it).
Corrected to M5 open / M4 closing, in `roadmap.md`'s own words.

That forced one consequential cell: the M5 status read `planned`, which
contradicts "current gate: M5" three lines above it. It now reads
**`in progress`**. This is the only status cell changed and the only edit in this
report not derivable from the brief's done_when — **revert both with one edit if
the owner reads README status differently.**

## Files inspected

Machine-inspected, all 611 tracked files, by both passes above. Read by eye, in
full or at every gate-statement passage:

**Read in full:** `CLAUDE.md`, `README.md`, `docs/roadmap.md`, `docs/PLAN.md`,
`docs/TODO.md`, `docs/LESSONS.md`, `docs/briefs/mv-04-gate-order-sweep.md`,
`docs/reports/mv-03-roadmap-round.md`.

**Gate-statement passages read:** `docs/safety/PL-SCENARIOS.md` (§ "Gate
numbering"), `docs/safety/SRS.md` (§ "Gate references", §4 landing-gate column),
`docs/safety/TWIN-DEMO-MAP.md` (§ "Gate numbers", authority table),
`docs/interfaces/opcua-nodes.md` (§12.5, §12.8, M6 rows),
`docs/interfaces/bridge-design.md`, `docs/interfaces/handshake-tables.md`,
`docs/interfaces/vda5050-subset.md`, `plc/demo-cell/SPEC.md` (out-of-scope
table), `plc/forklift/SPEC.md` (authority table), `plc/forklift-safety/SPEC.md`
(N7, out-of-scope table), `plc/forklift-safety/FIO-FEASIBILITY.md`,
`plc/README.md`, `hmi/README.md`, `hmi/EVIDENCE_HMI.md`, `bridge/README.md`,
`bridge/EVIDENCE_LATENCY.md`, `agv/forklift/README.md`,
`agv/forklift/EVIDENCE_ODOM_TF.md`, `sim/README.md`, `sim/scenarios/DEFERRED.md`,
`sim/scenarios/forklift_commissioning.md`, `sim/setup/WSL_ENVIRONMENT.md`,
`docs/README.md`, `.claude/agents/*.md` (11 files), `.claude/settings.json`.

**The 59 live files carrying a gate token**, the full inventory pass 1 produced
(the 24 above plus): `agv/forklift/EVIDENCE_SENSOR_COVERAGE.md`,
`agv/forklift/EVIDENCE_SENSOR_TF.md`, `agv/forklift/config.yaml`,
`agv/forklift/model.sdf`, `agv/forklift/scripts/obstacle_zone.py`,
`assets/m5-forklift/README.md`, `bridge/amr_bridge/config.py`,
`bridge/test_double/plc_test_double.py`, `plc/forklift/double/EVIDENCE_DOUBLE.md`,
`plc/forklift/double/README.md`, `plc/forklift/double/check_kernels.py`,
`plc/forklift/double/logic.py`, `plc/forklift/double/server.py`,
`hmi/hmi_server.py`, `hmi/tools/capture_screens.mjs`, `stack.sh`,
`sim/setup/CONTAINER_TOOLCHAIN.md`, `sim/setup/install.sh`,
`sim/scenarios/forklift_stimulus.py`, `sim/scenarios/run_forklift_rehearsal.py`,
`sim/scenarios/run_scenario.py`, `sim/scenarios/tools/make_map.py`,
`sim/launch/cell_bringup.launch.py`, `sim/launch/forklift_bringup.launch.py`,
`sim/launch/warehouse_bringup.launch.py`, `sim/worlds/BRINGUP_EVIDENCE.md`,
`sim/worlds/CELL_EVIDENCE.md`, `sim/worlds/FORKLIFT_ARENA_EVIDENCE.md`,
`sim/worlds/WAREHOUSE_EVIDENCE.md`, `sim/worlds/cell.sdf`,
`sim/worlds/forklift_arena.sdf`, `sim/worlds/warehouse.sdf`.

**Historical, inspected and deliberately not edited** (the brief forbids it):
`docs/adr/**` (14 files), `docs/briefs/**`, `docs/reports/**`, `docs/LESSONS.md`.

### The concurrent SLAM agent's territory

`sim/worlds/`, `sim/launch/` and `sim/scenarios/` were **read, not written**.
Their eleven gate references are all single-gate work-landing notes — "the
coupled cell plus vehicle scenario is roadmap M6 work", "M6 enlarges THIS world
to ten stations" — every one of them still true under the M8 addition. **No gate
reference in those directories needed a change**, so no edit was made there and
no file of that agent's was touched. `sim/launch/forklift_bringup.launch.py` and
`sim/launch/warehouse_bringup.launch.py` show as modified in the working tree;
those are that agent's edits, not mine.

## Open questions

1. **`README.md`'s current-gate line and the M5 status cell** were corrected
   beyond the brief's three named targets (section above). Owner to confirm, or
   revert with one edit.
2. **`docs/PLAN.md` does not know M8 exists.** Nothing in it is made false by the
   addition — it scopes itself to the current gate and the closed ones — so it
   was left alone, which is also what `docs/reports/mv-03-roadmap-round.md`
   proposed. If the owner wants M8 visible in the plan, that is a one-line
   arch-docs edit, not this sweep's.
3. **Three documents identify roadmap.md's order as "the gate order of ADR
   0010"** — `docs/safety/SRS.md`, `docs/safety/PL-SCENARIOS.md`,
   `docs/safety/TWIN-DEMO-MAP.md`. Every gate number they state (M5, M6) is
   correct and untouched by ADR 0013, and each sentence names `roadmap.md` as the
   live source in the same breath, so a reader lands on the truth. But the
   attribution is now one ADR short of complete, the same imprecision corrected
   in CLAUDE.md §6. Not corrected here: those are safety-spec's documents and the
   change is attribution, not content. One clause each, at the next safety touch.
4. **`CLAUDE.md` §6 calls M7 "LLM operations layer" while `roadmap.md` and
   `README.md` call it "LLM operations layer and final demonstration".** A
   pre-existing divergence, not created or worsened by this round, and correcting
   it means restating an existing row — which this brief forbids. Flagged for
   whoever next has an authorised CLAUDE.md §6 touch.
5. **M8's showcase question stays open**, as `roadmap.md` and mv-03 leave it.
   Both new rows say "closes on committed evidence" and neither rules the
   recording question in either direction.
