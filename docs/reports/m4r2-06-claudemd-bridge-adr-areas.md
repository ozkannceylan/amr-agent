# Report m4r2-06 — bridge and adr in the CLAUDE.md area list

```
brief:               docs/briefs/m4r2-06-claudemd-bridge-adr-areas.md
status:              done
files_changed:       CLAUDE.md (section 7, the valid-areas line only — 1
                     insertion, 1 deletion),
                     docs/reports/m4r2-06-claudemd-bridge-adr-areas.md (this
                     file). Committed as one pathspec-scoped commit of exactly
                     these two paths.
invariants_touched:  none. Section 2 is byte-identical, and no other line of
                     CLAUDE.md changed. bridge/ has been a contract layer since
                     ADR 0005; this edit only lets the commit convention name it.
open_questions:      none
next_suggested:      none for the area list — every scope in the history is now
                     legal; the orchestrator may record the closure in TODO.md,
                     which never carried this item.
```

## What landed

Line 204 of CLAUDE.md, section 7:

```
-Valid areas: plc, fleet, agv, hmi, sim, safety, interfaces, infra.
+Valid areas: plc, fleet, agv, bridge, hmi, sim, safety, interfaces, adr, infra.
```

`bridge` sits after `agv` and before `hmi`, which is where the layer sits in the
section 4 layout and the section 5 roster. `adr` sits after `interfaces`, next
to the other docs-only scope. Every pre-existing entry keeps its order and its
spelling.

## Verification

`git diff --numstat -- CLAUDE.md` reports `1 1 CLAUDE.md`, and
`git diff --ignore-cr-at-eol --numstat -- CLAUDE.md` reports the same figure, so
the single changed line is real content and not a line-ending artifact of the
Windows checkout. `git ls-files --eol CLAUDE.md` reads `i/lf w/crlf
attr/text=auto`, the expected state under the root `.gitattributes`.

The scope set was counted independently of the m4r2-05 finding, over the subject
rather than a remembered list — every `<type>(<scope>)` prefix in
`git log --all --pretty=%s`, grouped:

| scope | commits | valid area before | valid area after |
|---|---|---|---|
| infra | 93 | yes | yes |
| interfaces | 32 | yes | yes |
| bridge | 19 | **no** | yes |
| plc | 14 | yes | yes |
| sim | 9 | yes | yes |
| safety | 4 | yes | yes |
| adr | 2 | **no** | yes |
| agv | 2 | yes | yes |
| hmi | 1 | yes (since m4r2-05) | yes |

After this edit no scope in the history is unlisted. `fleet` remains listed with
no commits yet, which is correct: the list is the set of legal areas, not a
usage record.

The same line governs branch names as well as commit scopes, so
`feat/bridge-<slug>` and `docs/adr-<slug>` become legal branch names by the same
edit. That is the intended reading of section 7, which defines `<area>` once for
both templates.
