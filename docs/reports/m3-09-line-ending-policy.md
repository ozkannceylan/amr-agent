# m3-09 line ending policy

brief:               docs/briefs/m3-09-line-ending-policy.md
status:              done
files_changed:       [.gitattributes (new, staged), docs/reports/m3-09-line-ending-policy.md (this report)]
invariants_touched:  none
open_questions:
  - `.claude/settings.local.json` is untracked and shows in WSL-side `git status`
    but not Windows-side. It is excluded by the owner's Windows global ignore
    (`C:\Users\ozkan/.config/git/ignore:3`), which WSL git does not read. The
    repo's own `.gitignore` does not cover it. Editing `.gitignore` was
    forbidden by this brief, so this is left for the orchestrator to decide.
  - `plc/` currently holds only Markdown. When TIA Portal exports land
    (`.scl`, `.udt`, `.db`, `.xml`), Siemens tooling may require CRLF and/or a
    UTF-8 BOM. No rule was added for them because the files do not exist yet;
    the rule must be added in the same commit as the first export.
next_suggested:      Re-run the m3-07 WSL environment brief now that install.sh executes.

---

## Starting state

`git status` was clean on both sides for tracked files. The only untracked
entry was this task's own brief. Untracked files are not affected by
`git add --renormalize`, so no other agent's work was at risk.

The defect, confirmed rather than assumed:

    $ git config --show-origin --get-all core.autocrlf
    file:C:/Program Files/Git/etc/gitconfig   true

    $ wsl git status --porcelain | wc -l
    108

Index was LF-clean throughout (`git ls-files --eol` showed `i/lf` for every
text file); only the working tree was CRLF. So this was purely a checkout
policy problem, never a stored-content problem.

## The policy

    * text=auto
    *.sh text eol=lf
    *.py text eol=lf
    *.pgm -text
    *.gz -text

Justification, line by line:

| Rule | Why it is here |
|---|---|
| `* text=auto` | Required minimum. Normalizes text to LF in the object store and makes WSL-side git treat a CRLF working tree as unmodified, which is what removed the 108 phantom modifications. |
| `*.sh text eol=lf` | Required minimum. One tracked `.sh`. A CR terminating the shebang becomes part of the interpreter name. `text=auto` alone is not enough: with `core.autocrlf=true` it still smudges to CRLF on Windows checkout. |
| `*.py text eol=lf` | Seven tracked `.py` files begin with `#!` (`bridge/run_bridge.py`, `bridge/test_double/plc_test_double.py`, the three `bridge/tools/*.py`, `sim/scenarios/run_scenario.py`, `sim/scenarios/tools/make_map.py`). Same failure mode as `.sh`, same platform, files present today. |
| `*.pgm -text` | `sim/scenarios/maps/map.pgm` is binary P5. `text=auto` classifies it correctly today only because a NUL happens to fall in the first 8000 bytes. It is a regenerated artifact (`sim/scenarios/tools/make_map.py`); a map whose top band is uniform would have no leading NUL, flip to "text", and be corrupted by normalization. |
| `*.gz -text` | `bridge/evidence/latency-2026-07-27.csv.gz`. Same argument, lower probability, but this file is measured evidence and a silent corruption would be unrecoverable. |

Rules deliberately **not** added:

- No rule for `.md`, `.yaml`, `.sdf`, `.json`, `.txt`. None are executed; all
  are consumed by parsers that tolerate CRLF. They keep the platform-native
  checkout, which is the behaviour a fresh clone already produces.
- No `eol=crlf` anywhere. The repo currently contains no file that must keep
  CRLF: no `.bat`, `.cmd`, `.ps1`, and no vendor exports.
- Not `* text=auto eol=lf`. That would force the whole tree to LF on Windows
  too. It is the escalation if a tool is later found to trip on CRLF, but it is
  a larger change than the defect requires.

## Verification

### 1. install.sh executes in WSL

    $ wsl -- bash /mnt/c/.../runner.sh
    00 # ! / u s r / b i n / e n v   b
    0000020  a s h  \n
    CR bytes in file: 0
    --- running ./sim/setup/install.sh ---
    Run as root (sudo).
    RESULT: exited non-zero (code 1)

The shebang line terminates with `\n`, the file holds zero CR bytes, and the
script runs to its own precondition guard at `install.sh:28-30` and exits 1.
That is the sudo error the brief called a pass — execution reached the script's
own logic.

Control experiment, same script re-CRLF'd in scratch, to confirm the mechanism
rather than assume it (LESSONS 2026-07-27, cell.sdf):

    $ sed 's/$/\r/' sim/setup/install.sh > /tmp/install_crlf.sh && ./install_crlf.sh
    /usr/bin/env: 'bash\r': No such file or directory
    /usr/bin/env: use -[v]S to pass options in shebang lines

Identical to the m3-07 failure. The variable under test is the line ending and
nothing else.

### 2. git status from WSL — clean

    $ wsl git status
    On branch main
    Your branch is ahead of 'origin/main' by 6 commits.

    Changes to be committed:
      new file:   .gitattributes

    Untracked files:
      .claude/settings.local.json
      docs/briefs/m3-09-line-ending-policy.md

Zero modified tracked files, down from 108.

### 3. git status from Windows — clean

    > git status
    On branch main
    Your branch is ahead of 'origin/main' by 6 commits.

    Changes to be committed:
      new file:   .gitattributes

    Untracked files:
      docs/briefs/m3-09-line-ending-policy.md

## What is staged

    $ git diff --cached --name-status
    A       .gitattributes

**Exactly one path.** No normalization was staged, because the index was
already LF-clean — `git add --renormalize .` produced no index change. Only the
working tree needed refreshing, which does not touch the index.

The 18 `.sh`/`.py` files were deleted and re-checked-out to force the new
smudge filter. Their blobs are byte-identical to HEAD, so they do not appear in
status. `sim/setup/install.sh` retains index mode `100755`. Both binaries
(`map.pgm`, `latency-2026-07-27.csv.gz`) are unchanged against HEAD.

Nothing was committed. No `git config --global` or `--system` was run.
`sim/setup/install.sh` was not edited.

---

## Follow-up: settings.local.json ignore rule

This section records an **orchestrator ruling on the open question raised above**.
The original brief forbade editing `.gitignore`; the orchestrator lifted that
restriction for this one file and assigned the fix here rather than to a new
brief.

Rule added to the repository's own `.gitignore`:

    # Machine-local overrides. .claude/settings.json is tracked on purpose (CLAUDE.md section 7).
    .claude/*.local.json

**Pattern choice.** `.claude/*.local.json` rather than the literal
`.claude/settings.local.json`: it covers the `*.local.json` machine-local
override convention across the one directory that deliberately mixes tracked
and untracked settings, while being structurally incapable of matching
`.claude/settings.json`, which carries no `.local` segment and is tracked on
purpose for the attribution settings in CLAUDE.md section 7.

**Placement.** Both `.gitignore` files in this repo are two bare lines of Python
build artifacts with no comments. The new rule is a different concern, so it is
separated by a blank line and carries the one comment the file needs: without
it, the obvious "simplification" is `.claude/`, which would untrack
`settings.json`.

**ASCII only.** The comment first read `CLAUDE.md §7`. The bytes were valid
UTF-8 (`c2 a7`), but Windows PowerShell's default `Get-Content` codepage renders
them as `Â§`, which is how the owner is most likely to read this file. A
cross-platform config parsed by two different git builds should not depend on
an encoding assumption for a decorative character, so it was changed to
`section 7`. The file is now 100% ASCII.

### Verification

`check-ignore` resolves to the repo rule on both platforms, replacing the
per-machine global ignore that previously covered it on Windows only:

    WINDOWS: .gitignore:5:.claude/*.local.json    .claude/settings.local.json
    WSL:     .gitignore:5:.claude/*.local.json    .claude/settings.local.json

Previously Windows resolved to `C:\Users\ozkan/.config/git/ignore:3` and WSL
resolved to nothing. `.claude/settings.json` is confirmed **not** ignored on
either side.

Tracked-file status, both sides sampled back to back:

    === WINDOWS tracked-modified ===      === WSL tracked-modified ===
    M  .gitignore                         M  .gitignore
     M docs/TODO.md                        M docs/TODO.md
     M sim/README.md                       M sim/README.md
     M sim/launch/cell_bringup.launch.py   M sim/launch/cell_bringup.launch.py
     M sim/worlds/CELL_EVIDENCE.md         M sim/worlds/CELL_EVIDENCE.md
     M sim/worlds/cell.sdf                 M sim/worlds/cell.sdf

The two sides are byte-identical including staging state. That agreement, not
emptiness, is the proof the line-ending policy holds: before `.gitattributes`,
WSL reported 108 modified files against Windows' 0.

The tree is **not** clean, and this is not line-ending churn. Concurrent agents
(m3-03d, m3-10) were writing to `sim/` and `docs/` throughout this follow-up;
the file set changed between consecutive commands. Each modification was checked
with `git diff --numstat` against `git diff --ignore-cr-at-eol --numstat` and
the counts are identical, which is what a real content edit looks like. Line
ending churn presents as a whole-file rewrite; none is present.

Only `.gitignore` was staged by this task. No `git rm --cached` was run,
`.gitattributes` was not touched, and nothing was committed here.

### Incident: the rule was swept into an unrelated commit

While this edit sat staged, another process committed with a full-index commit.
The `.gitignore` change was picked up by `a9e9f84 docs(interfaces): close the
cadence item and name the delivered evidence file`, whose message does not
describe it. This violates the CLAUDE.md section 7 rule of one logical change
per commit, and it is the same class of hazard the parent brief guarded against
when it required a clean tree before renormalizing.

The ASCII correction above is still staged and uncommitted, so the orchestrator
can land it with a message that names the rule. Nothing is lost either way; the
committed rule is functionally correct.

---

## lessons_candidates

2026-07-27 | Diagnosed the WSL 'bash\r' failure as stored CRLF in the repo | The index was LF-clean all along; only Windows' system-level core.autocrlf=true smudged the checkout, so no file content was ever wrong | Read `git ls-files --eol` before treating a line-ending failure as a content problem: `i/lf w/crlf` means fix the checkout policy, `i/crlf` means fix the content

2026-07-27 | Assumed `* text=auto` would be enough to make shell scripts executable from WSL | `text=auto` only normalizes the index; with core.autocrlf=true the working tree is still smudged to CRLF, so the shebang stays broken | Any file executed through a shebang needs explicit `eol=lf`, not just `text=auto`; in this repo that is `*.sh` and the seven `*.py` files that begin with `#!`

2026-07-27 | Relied on git's text/binary heuristic for the Nav2 map | The heuristic only scans the first 8000 bytes for a NUL, and map.pgm is regenerated by make_map.py, so a map with a uniform top band would silently reclassify as text and be corrupted by normalization | Mark generated binaries `-text` explicitly rather than trusting detection, because the cost of a misdetected binary is corruption while the cost of the rule is one line

2026-07-27 | Compared `git status` between Windows and WSL and found a file listed on one side only | `.claude/settings.local.json` is covered by the owner's Windows global ignore, which WSL git cannot resolve because $HOME differs | Ignore rules that must hold for both sides of a /mnt/c checkout belong in the repo's .gitignore, never in a per-user global ignore file

2026-07-27 | Left a deliverable staged but uncommitted, per the brief, while other agents worked in parallel | Another process ran a full-index commit and swept the staged .gitignore into `a9e9f84`, whose message describes unrelated interface work | "Leave it staged, the orchestrator commits" is only safe when nothing else is committing; with concurrent agents the orchestrator either commits the deliverable immediately or the agent is told to commit its own path explicitly

2026-07-27 | Verified a line-ending fix by requiring `git status` to be empty on both platforms | Concurrent agents kept the tree dirty, so emptiness was never achievable and the file set changed between consecutive commands | The test for a line-ending policy is that Windows and WSL report the *same* set, not an empty one; confirm each modification is real content by checking `git diff --numstat` equals `git diff --ignore-cr-at-eol --numstat`

2026-07-27 | Wrote a section-symbol into .gitignore as UTF-8 | The bytes were valid, but Windows PowerShell 5.1's `Get-Content` defaults to the ANSI codepage and renders them as mojibake, which is how the owner would read the file | Keep dotfile config comments ASCII-only; a file parsed by two git builds on two platforms should not carry a non-ASCII byte for a decorative character
