# Brief pub-01 — public-readiness audit (read only)

gate:                none (repository publication, owner-directed)
agent:               verifier
goal:                everything that must not be public is found before the repository goes public
invariants_touched:  none (13 is the subject: no secrets in the repository)
inputs:              [the whole working tree, the full git history, .claude/settings.json, .gitignore, .gitattributes]
deliverable:         docs/reports/pub-01-public-readiness-audit.md
done_when:           every check below carries a finding with evidence, and the report ends with a numbered owner decision list (license choice included) plus a go/no-go verdict
forbidden:           [modifying any file except the report, committing, publishing anything]

## Checks

1. **Secrets, tree and history.** Sweep the working tree AND `git log -p`
   for credentials, tokens, tailnet keys, certificate material, password-like
   strings, private IPs beyond the documented PLCSIM subnet, and email
   addresses other than the owner's committer identity. The endpoint
   192.168.53.1 and the home-LAN collision story are documented facts — flag
   anything beyond them (e.g. real Wi-Fi SSIDs, MACs, hostnames).
2. **Attribution.** Full history: author/committer fields, commit messages,
   branch names — no AI/tooling mention anywhere (CLAUDE.md §7). Also check
   file CONTENTS added this project for tool references that §7's spirit
   covers.
3. **Personal residue.** Untracked files (HANDOVER.local.md, check_nodes.py)
   — recommend ignore or removal; OneDrive/personal paths inside committed
   files (scripts, docs, evidence) — machine-specific absolute paths are
   documented as environment facts in some evidence, judge each; the
   watch-table screenshots for anything personal visible beyond TIA.
4. **License.** No LICENSE file exists (verify). The repository cannot be
   meaningfully public without one — put the choice on the owner decision
   list with one-line trade-offs (MIT / Apache-2.0 / BSD-3).
5. **Size and hygiene.** Largest blobs in history (evidence gz files are
   expected; flag anything over ~10 MB), CRLF policy holding, README absence
   at root (pub-02 is writing one in parallel — do not write it, just note).
6. **Claims check.** CLAUDE.md and docs make claims a public reader will
   test (install.sh, bridge README run instructions). Spot-check that the
   committed instructions do not reference paths that exist only on this
   machine without being labelled as such.
