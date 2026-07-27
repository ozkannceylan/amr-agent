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

## lessons_candidates

2026-07-27 | Diagnosed the WSL 'bash\r' failure as stored CRLF in the repo | The index was LF-clean all along; only Windows' system-level core.autocrlf=true smudged the checkout, so no file content was ever wrong | Read `git ls-files --eol` before treating a line-ending failure as a content problem: `i/lf w/crlf` means fix the checkout policy, `i/crlf` means fix the content

2026-07-27 | Assumed `* text=auto` would be enough to make shell scripts executable from WSL | `text=auto` only normalizes the index; with core.autocrlf=true the working tree is still smudged to CRLF, so the shebang stays broken | Any file executed through a shebang needs explicit `eol=lf`, not just `text=auto`; in this repo that is `*.sh` and the seven `*.py` files that begin with `#!`

2026-07-27 | Relied on git's text/binary heuristic for the Nav2 map | The heuristic only scans the first 8000 bytes for a NUL, and map.pgm is regenerated by make_map.py, so a map with a uniform top band would silently reclassify as text and be corrupted by normalization | Mark generated binaries `-text` explicitly rather than trusting detection, because the cost of a misdetected binary is corruption while the cost of the rule is one line

2026-07-27 | Compared `git status` between Windows and WSL and found a file listed on one side only | `.claude/settings.local.json` is covered by the owner's Windows global ignore, which WSL git cannot resolve because $HOME differs | Ignore rules that must hold for both sides of a /mnt/c checkout belong in the repo's .gitignore, never in a per-user global ignore file
