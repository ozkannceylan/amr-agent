gate:                M3
agent:               infra (ad-hoc, owner-approved this session)
goal:                Make shell scripts check out with LF on Windows so sim/setup/install.sh executes in WSL, and stop WSL-side git from reporting the whole tree as modified.
invariants_touched:  none
inputs:              [docs/reports/m3-07-wsl-environment.md, sim/setup/install.sh]
deliverable:         .gitattributes at the repository root
done_when:           sim/setup/install.sh runs in WSL without the 'bash\r' shebang failure; git status from inside WSL reports the tree clean; git status from Windows reports the tree clean; and both are demonstrated with quoted command output.
forbidden:           [committing anything, editing sim/setup/install.sh or any file whose only defect is its line endings, editing docs/ other than the report, changing .gitignore, running git config --system or --global, touching plc/ bridge/ fleet/ agv/ content]

## Why this exists

m3-07 could not run `sim/setup/install.sh` under WSL: the shebang failed with
`/usr/bin/env: 'bash\r': No such file or directory`. The committed blob is
LF-clean. Windows Git's **system-level** `autocrlf = true`, combined with the
repo having no `.gitattributes`, checks the working tree out as CRLF.

The second-order problem is the more dangerous one: WSL-side git reports every
tracked file as modified while Windows-side git reports the tree clean. A
`git commit -a` run from WSL would churn the entire repository.

Do **not** fix this by editing `install.sh`, and do **not** fix it by changing
the user's global or system git config. The repo must carry its own policy.

## Required content

At minimum:

```
* text=auto
*.sh text eol=lf
```

Decide, and justify in your report, whether any other pattern needs an explicit
rule — in particular anything binary or anything that must keep CRLF. Look at
what the repo actually contains before adding patterns. Do not add speculative
rules for file types the project does not have.

## Procedure

1. Confirm the starting state: `git status` must be clean before you begin. If
   it is not, STOP and report — another agent's work is in flight and a
   renormalize would stage it.
2. Create `.gitattributes`.
3. Renormalize the index so stored content matches the policy, then refresh the
   working tree so `.sh` files are re-checked-out with LF.
4. **Verify, with quoted output:**
   - `install.sh` executes in WSL far enough to prove the shebang resolves. It
     will still fail at the `apt` step for lack of sudo — that is expected and
     is not your blocker. Reaching a genuine `apt`/sudo error is a pass.
   - `git status` from WSL reports clean.
   - `git status` from Windows reports clean.
5. Report exactly which paths ended up staged. The tree was clean at step 1, so
   anything staged beyond `.gitattributes` is a line-ending normalization and
   must be listed by count and kind.

**Do not commit.** Leave the changes staged and report. The orchestrator
commits.

## Reporting

`docs/reports/m3-09-line-ending-policy.md` in the CLAUDE.md report shape, then a
`lessons_candidates` section (may be "none") in
`date | what was attempted | what went wrong | the rule now` format.
