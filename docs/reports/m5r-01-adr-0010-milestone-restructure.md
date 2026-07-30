# Report m5r-01 — ADR 0010: milestone restructure, forklift-first program

```
brief:               docs/briefs/m5r-01-adr-0010-milestone-restructure.md
status:              done
files_changed:       docs/adr/0010-milestone-restructure-forklift-first.md (new)
invariants_touched:  none. Invariants 1-13 stand unchanged. Two invariant-
                     sensitive readings are recorded, not altered: the HMI
                     emergency button under invariant 1 (D6(b)) and the HMI map
                     view's missing data path under invariant 11 (D6(a)).
open_questions:      four, all recorded as open in ADR 0010 D6 and none decided
                     there; plus three follow-ups outside this agent's write
                     scope, listed below
next_suggested:      the roadmap brief, rewriting docs/roadmap.md's gate table to
                     the D7 numbering, followed by PLAN.md and TODO.md in the
                     same round so the three tracking files never disagree
```

## What the ADR records

Status **accepted (2026-07-30)**, owner-approved on that date, seven decisions:

- **D1** the forklift is the vehicle platform from M5 onward; RB-KAIROS retired.
- **D2** new M5, sensored autonomous forklift (old M5 safety + old M6 vehicle).
- **D3** new M6, VDA 5050 fleet at scale (old M7 + M8 + M9), entered by a
  deep-research brief.
- **D4** new M7, LLM operations layer, absorbing old M12 and closing with old
  M10's demonstration.
- **D5** the arm gate removed, not parked.
- **D6** four open decisions, each with owner and briefing point, none resolved
  in the ADR's own text.
- **D7** numbering mechanics, SF and boundary-statement landing points, filename
  convention, four embedded recordings.

Relationships stated explicitly in the status block: ADR 0002 **superseded** in
its platform selection; ADR 0008 D1's gate order above M3 **superseded** while
D2, D3 and D4 stay binding and D5 is overtaken; ADR 0009 **extended**, not
superseded; ADR 0007's showcase rule **unchanged** and its §2 landing points
moved with their gates. No accepted ADR was edited.

The ADR cites no external vendor source, so there is no verification date or
pinned ref to record. It notes instead that retiring RB-KAIROS retires ADR 0002's
2026-07-26 vendor findings with it, and that nothing in the remaining program
depends on them.

## Open questions

Recorded as open inside the ADR (D6), not decided:

1. **(a)** The HMI real-time map view has no data path — the HMI speaks only to
   the PLC and a SLAM map cannot realistically transit OPC UA process nodes.
   Owner, by its own ADR, at M5 briefing.
2. **(b)** Anything beyond the recorded reading of the HMI emergency button as a
   process stop plus a display of F-layer state. Owner, by its own ADR, if ever
   wanted; not scheduled.
3. **(c)** The LLM layer's attachment point and topology edge. Owner, at M7
   briefing, per the m4-00 §6 decision list.
4. **(d)** Whether M6 is one gate or staged. Owner, on the D3 deep-research
   brief's findings, at M6 briefing.

Requested here rather than done, each outside this brief's scope:

5. **docs/roadmap.md, docs/PLAN.md and docs/TODO.md** carry the ADR 0008
   numbering and now disagree with ADR 0010. This is the third renumbering above
   M3; the stale-reference lists in ADR 0007 and ADR 0008 are a starting point,
   not an inventory, and the sweep is by subject with independent search. Two of
   these three files are in this agent's write scope but forbidden by this brief,
   which assigns them to separate briefs.
6. **docs/safety/SRS.md** needs SF-20…29 marked out of scope (D5) and its gate
   tags and "Verified at gate" column moved to the D7 numbering — safety-spec
   agent.
7. **README.md** shows M4 as **done** and lists the pre-restructure gate names
   under the wrong numbers; the M4 mark is corrected to *closing* and the table
   to D7 by the README brief.

One observation for the orchestrator, not a change: the brief's ruling 3 groups
AT-09 with "the former M9 acceptance tests". AT-09 sat at the former M7 (VDA 5050
client) under ADR 0008's numbering. The destination is unaffected, since old M7
and old M9 both merge into new M6, so the ADR records all three tests landing at
M6 and names the gate each came from rather than repeating the grouping.
