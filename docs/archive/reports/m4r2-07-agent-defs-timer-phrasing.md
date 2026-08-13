# Report m4r2-07 — agent definitions match the client-logic ruling

```
brief:               docs/briefs/m4r2-07-agent-defs-timer-phrasing.md
status:              done
files_changed:
  - .claude/agents/hmi.md      (edited) the client-logic hard rule, one line
  - .claude/agents/bridge.md   (edited) the client-logic hard rule, one line
  - docs/reports/m4r2-07-agent-defs-timer-phrasing.md   (new) this report
invariants_touched:  none — §10.1's existing ruling is propagated, not extended
open_questions:      two, both inherited and outside this deliverable
next_suggested:      Verifier on the m4f-01d / m4r2-07 pair.
```

## What changed

One hard-rule line in each file, replaced in place. `git diff --numstat` is `1 1` for
each, and equals `git diff --ignore-cr-at-eol --numstat`, so both are real content
changes and not line endings. Nothing else in either file moved.

Both lines now carry §10.1's ruling in the source's own terms:

| Element | Where it came from |
|---|---|
| The forbidden list — no interlock, latch, sequencing, setpoint formation, reaction to plant state, or verdict the PLC also computes | §10.1 "No logic in either client", verbatim list |
| `The line is not "no timer"` | §10.1's own sentence, kept as the explicit retirement of the flat phrasing |
| The timers each client legitimately owns | bridge: its 20 Hz cycle (`bridge-design.md` §5). HMI: its 10 Hz write cycle with the 5 Hz floor (§10.8 H2) and its window over the operator's page (§10.8 H6) |
| The test — what does the timer watch: its own cycle or its own input channel, never the plant, never a verdict the PLC also computes | §10.1, stated last in each line so it survives a hurried read |
| What is still forbidden — debounce, fault delay, dwell, stale window over a plant signal, "write only if stable for X ms" | §10.1; the threshold and the delay are process decisions |

The bridge line keeps "no threshold" and the HMI line keeps "no actuator output" and its
ADR 0008 D3 clause naming teleop routing, the fork-height speed cap, the fork soft limits
and the lidar obstacle stop. Each line keeps its closing "if a brief seems to require
logic here, stop and report". Nothing was dropped in the rewrite.

## Checks

- **Sweep by subject, not by remembered phrasing** (LESSONS 2026-07-29). Both files were
  whitespace-normalised to a single line and searched for `timer(s)`, `timing`, `debounce`,
  `dwell`, `stale`, `threshold(s)`, `latch(es)`, `interlock(s)`, `sequencing`. Exactly one
  occurrence of each term per file, all inside the one client-logic bullet — so one sentence
  per file was the whole surface, and no wrapped second occurrence was hiding across a line
  break. The enumeration in m4f-01d's open question 1 was treated as a starting point and
  confirmed independently, not taken as exhaustive.
- **Both forward citations were resolved before being written into a definition.**
  `bridge-design.md` §5 is the update model and tabulates the 20 Hz / 50 ms cycle;
  §10.8 H2 is the 10 Hz nominal / 5 Hz floor and H6 is the page-liveness window. A pointer
  in an agent definition is read by an agent that will not verify it, so neither was copied
  on the strength of §10.1 citing it.
- **Character set unchanged.** Both files already used `§` (U+00A7) and the em dash
  (U+2014) throughout; the edit introduced no new non-ASCII character. The ASCII-only rule
  (LESSONS 2026-07-27) governs dotfile *config* comments read by a codepage-defaulting
  shell, not these UTF-8 markdown definitions, and reformatting them would have breached
  "nothing else in either file changes".
- **No other agent definition and no CLAUDE.md line was touched**, per the brief's
  `forbidden`.

## Open questions

Both are carried forward from m4f-01d unchanged. Neither is actionable here — this brief's
write scope was the two definitions.

1. **`opcua-nodes.md` §9.7 and `bridge-design.md` §7.2 still share a sentence that reads
   flat out of context** — "No timer, threshold or reaction exists in the bridge". Judged
   consistent in context by m4f-01d and left. It now matters slightly more than it did:
   the bridge definition sends its agent to `bridge-design.md` §5 for the cycle timer, so
   an agent reading that document can meet the flat sentence three sections later. A
   one-clause qualification in `bridge-design.md` §7.2 would close it; that file belongs to
   the interface agent.
2. **ADRs 0004, 0005 and 0007 each restate "no timers" for the bridge.** Accepted ADRs are
   never edited (CLAUDE.md §8) and the binding statement is `bridge-design.md` §1.1, which
   is precise. Recorded so it is not rediscovered as a defect; no action available.
