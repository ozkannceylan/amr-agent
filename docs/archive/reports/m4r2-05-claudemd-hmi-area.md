# Report m4r2-05 — hmi in the CLAUDE.md area list

```
brief:               docs/briefs/m4r2-05-claudemd-hmi-area.md
status:              done
files_changed:       CLAUDE.md (section 7, the valid-areas line only — 1
                     insertion, 1 deletion), docs/reports/m4r2-05-claudemd-hmi-area.md
                     (this file). Committed as one pathspec-scoped commit of
                     exactly these two paths.
invariants_touched:  none. Section 2 is byte-identical. The edit executes ADR
                     0008's requested follow-up on the same footing as m4r2-03,
                     which added the section 3 node, the section 4 layout line
                     and the section 5 roster row.
open_questions:      one, below
next_suggested:      a one-line brief adding bridge (and, if the owner wants it
                     de jure, adr) to the same line, so every scope in use is a
                     valid area.
```

## What landed

Line 204 of CLAUDE.md, section 7:

```
-Valid areas: plc, fleet, agv, sim, safety, interfaces, infra.
+Valid areas: plc, fleet, agv, hmi, sim, safety, interfaces, infra.
```

`hmi` is placed after `agv` and before `sim`, which is where the layer sits in
the section 4 layout and in the section 5 roster after m4r2-03. The existing
areas keep their order and their spelling.

`git diff --numstat CLAUDE.md` reports `1 1 CLAUDE.md`, and
`git diff --ignore-cr-at-eol --numstat CLAUDE.md` reports the same, so the
single changed line is real content and not a line-ending artifact of the
Windows checkout (`git ls-files --eol` reads `i/lf w/crlf`, the expected state
under the root `.gitattributes`).

## open_questions

- **`bridge` is a practised commit scope that is still not a valid area, and
  this brief could not add it.** Counting the scopes in `git log --oneline
  --all`: `docs(bridge)` 10 and `feat(bridge)` 9, so 19 commits already use a
  scope the line does not list — more than the single `feat(hmi)` commit this
  edit legalises. `docs(adr)` appears twice and is likewise unlisted, though
  that one may be intentional, since ADRs are arguably `docs(infra)` work. The
  brief's `forbidden` field rules out any other CLAUDE.md change, so both are
  reported rather than fixed. If the owner wants the line to describe practice
  in full, `bridge` is the entry with real history behind it.
