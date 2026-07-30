# Report m5r-07 — sim/ gate-reference reconciliation per ADR 0010

```
brief:               docs/briefs/m5r-07-sim-docs-sweep.md
status:              done
files_changed:       sim/README.md
                     sim/scenarios/DEFERRED.md
                     sim/scenarios/forklift_commissioning.md
                     sim/scenarios/config/nav2_params.yaml
                     sim/setup/WSL_ENVIRONMENT.md
                     sim/setup/install.sh
                     sim/worlds/warehouse.sdf
                     sim/worlds/forklift_arena.sdf
                     sim/worlds/BRINGUP_EVIDENCE.md
                     sim/worlds/FORKLIFT_ARENA_EVIDENCE.md
                     sim/launch/warehouse_bringup.launch.py
                     sim/launch/forklift_bringup.launch.py
                     docs/reports/m5r-07-sim-docs-sweep.md (this file)
invariants_touched:  none
open_questions:      see below, 6 items
next_suggested:      interface sweep re-points docs/interfaces/bridge-design.md
                     items 8 and 15 at the new sim/README heading recorded below
```

## The heading the interface sweep must cite

`sim/README.md` line 189, exact text:

```
## Navigation scenario (RB-KAIROS, parked — resumes at M5 on the forklift)
```

(em dash U+2014, single spaces, no trailing punctuation). It replaces
`## Navigation scenario (M5, deferred)`. `docs/interfaces/bridge-design.md`
items 8 and 15 quote the old text and say the heading names the wrong gate;
under ADR 0010 the vehicle gate is M5, so the number was right and the
platform was not. Both items are outside `sim/` and were not edited.

## What changed, by mapping rule

| Rule applied | Where |
|---|---|
| navigation work → **M5, on the forklift**, RB-KAIROS retired | README contents (warehouse.sdf, nav2_params.yaml), README §4 retirement note, README "Running the bringup", README navigation-scenario heading + prose, README M3-cell cross-reference, DEFERRED.md, WSL_ENVIRONMENT.md §1/§2/§3.1, warehouse.sdf header + sensor note, warehouse_bringup.launch.py header, BRINGUP_EVIDENCE.md gate note, nav2_params.yaml header, install.sh header |
| door / charger handshakes → **M6** | README "Known behavior" (was "later gates (M6/M7)"), warehouse.sdf DoorGap, ConveyorStation, ChargerStation comments (were "in later gates") |
| coupled cell-plus-vehicle scenario (AT-07 coupled) → **M6** | README forklift-arena section, forklift_arena.sdf header, forklift_bringup.launch.py header, FORKLIFT_ARENA_EVIDENCE.md model list (all were "roadmap M9 work") |
| ADR 0004 cited for **gate order** → cite ADR 0010 | README navigation-scenario prose, DEFERRED.md |
| ADR 0008 D5 "no navigation claim" is overtaken by ADR 0010 D1/D2 | FORKLIFT_ARENA_EVIDENCE.md item 6, forklift_bringup.launch.py header — both now read "no navigation claim **at M4**" with the ADR 0010 forward pointer |
| "docs/briefs/m5-*" filename guess removed | DEFERRED.md — now "the resuming brief's name is assigned at briefing" |
| §12 "T6 (M5, early)" reconciled **once** with the widened M5 | forklift_commissioning.md, one new paragraph after the "Not one of the five roadmap criteria" note; heading, steps, Pass lines, non-claims and the "M5 proper" rows all untouched |

**M4 references: untouched.** No removed line in the diff contains `M4`
(`git diff -- sim | grep "^-" | grep -w M4` is empty). The two new `M4`
mentions are additions qualifying ADR 0008 D5 claims, not renumberings.

**Not decided here, written as open:** whether the warehouse world is reused
at M5 or replaced by the enlarged M6 world. It is written as "decided at
briefing" in four places — README contents block, README navigation-scenario
section, DEFERRED.md, and the `warehouse.sdf` header.

**Substance unchanged.** No scenario procedure step, no world geometry, no
measurement and no evidence figure was altered. The three SDF edits are
comment text only (`git diff` shows no line outside a `<!-- -->` block), and
`sim/setup/install.sh` still passes `bash -n` with LF endings intact.

## Sweep method and result

Whitespace-normalised (`re.sub(r'\s+',' ',text)`) full-file search across
every file in `sim/` except `maps/map.pgm`, for: `M5`…`M12` tokens, `ADR 000x`
citations, `RB-KAIROS`/`rbkairos`, `roadmap M<n>`, `later gates?`, and the
prose gate names (vehicle/navigation/safety/fleet/arm/demonstration gate,
PLC integration, arm integration, Hermes, `AT-0n`). The brief's location list
was treated as a starting point; the sweep found **eleven locations it did not
name**: README §4 and "Running the bringup" (RB-KAIROS platform assumptions),
README line 42 (nav2_params description), three `warehouse.sdf` station
comments plus its header and sensor note, `warehouse_bringup.launch.py`
header, `BRINGUP_EVIDENCE.md` title, `nav2_params.yaml` header,
`install.sh` header, and `FORKLIFT_ARENA_EVIDENCE.md` item 6.

Post-edit re-sweep: **zero** `M7`–`M12` tokens remain anywhere in `sim/`.
Every surviving `M5`/`M6` token names its ADR 0010 gate. Every surviving
`RB-KAIROS` mention is inside prose that states the retirement or sits in a
file whose header now does.

## Open questions

1. **Warehouse world reuse (M5 or M6)** — deliberately not decided, per the
   brief. Four "decided at briefing" markers now exist in `sim/`; whichever
   way M5 briefing rules, they are the sites to close.
2. **`docs/interfaces/bridge-design.md` items 8 and 15** still quote the old
   heading and still assert the vehicle gate is M6 (ADR 0008 D1 reading).
   Outside `sim/`; requested, not edited. Exact replacement text is above.
3. **Two "M3" labels were corrected, not just gate numbers above M4.**
   `warehouse.sdf` read "M3 warehouse world" and
   `warehouse_bringup.launch.py` read "M3 bringup" — but neither is M3 work
   (M3 is the fixed-equipment cell). They were round labels from the m3
   briefs. Both now name the parked navigation scenario and its M5 landing,
   with "written in the m3 round" kept so the provenance survives (ADR 0010
   D7). Flagged because the brief's ruling was M0–M4 keep their numbers, and
   this is a mislabel correction rather than a renumbering. Revert on request.
4. **`BRINGUP_EVIDENCE.md` gained a dated gate note**, not a retitle: the
   heading "M3 bringup evidence" and every figure below it are unchanged, and
   the added paragraph says only which gate the run now belongs to. Judged to
   be inside "the gate name it cites"; called out because the brief forbids
   changing evidence text.
5. **No simulator in this session's container** (`gz` and `/opt/ros/jazzy`
   both absent), so the three edited SDFs were not load-checked. The edits are
   comment-text only and were checked for the `--`-inside-a-comment hazard of
   LESSONS 2026-07-27: none introduced. Separately, `warehouse.sdf`,
   `forklift_arena.sdf` and `cell.sdf` all **already** fail strict
   `ElementTree` parsing at HEAD, from `--` inside their ASCII layout diagrams
   (`--- Aisle A ---` and similar). Pre-existing, unrelated to this brief, and
   tolerated by libsdformat's parser — but worth a separate look, since
   LESSONS records that exact failure mode for `cell.sdf` once already.
6. **`sim/README.md`'s contents block still lists
   `scenarios/EVIDENCE_NAV.md` as a "dated capture of a successful headless
   run"**, while `DEFERRED.md` states no evidence file exists and the file is
   not in the tree. Pre-existing and not a gate reference, so left alone; it
   belongs to whichever brief resumes the scenario.
