# Report pub-01 — public-readiness audit

brief:               docs/briefs/pub-01-public-readiness-audit.md
status:              done
files_changed:       docs/reports/pub-01-public-readiness-audit.md (this file only; nothing else was modified, nothing was committed, nothing was published)
invariants_touched:  none. Invariant 13 is the subject and is not breached as written — no credential value exists in the tree or in history
open_questions:      the ten owner decisions in §7; decisions 1, 2 and 3 gate publication
next_suggested:      resolve decisions 1-3, then re-run this audit against the rewritten history before any visibility change

**Verdict: FAIL — no-go.** Publication must not proceed in the current state. The
blocker is not a secret value; it is a 539-line security survey of the owner's
live private infrastructure (finding 1), present at HEAD *and* in history in two
revisions. Everything else on this list is cheap to fix.

**A note on this report's own discipline.** This file will itself be public if
the repository is. It therefore cites the sensitive material by **file, line and
kind** and does not reproduce the identifiers. Copying them here would create a
second copy of the leak in the same tree, surviving any fix applied only to the
original.

---

## 0. What was audited, and against what

| | |
|---|---|
| Committed state | `main` at `7cb60a5`, 86 commits, 292 tracked files |
| History | `git log -p --all`, all 8 refs, plus tags, stash, reflog and unreachable objects |
| Concurrency | Two agents were working in the tree. `main` advanced from `fe92315` to `7cb60a5` mid-audit (`40b20db`, `7cb60a5`); both new commits were re-swept and are clean (§5.6). Uncommitted edits under `bridge/` and the untracked `bridge/tools/check_session_lifecycle.py` were **not** read as final; `README.md` + `assets/` had not landed at the time of writing |
| Visibility, verified | `gh repo view`: `amr-agent` **PRIVATE**, `hermes-assistant` **PRIVATE**, `rookie-assistant` **PRIVATE** |
| Push state | `origin/main` is at `8d0ba7b`; **53 commits are unpushed**. Publication pushes all 53 at once |

---

## 1. BLOCKING — `docs/reports/m4-00-hermes-survey.md` discloses live private infrastructure

The M4 survey did its job well and stayed inside its brief: it reads "no secret
value appears in this report", and that is **true** — I verified it. The problem
is orthogonal to secret values. The file is a competent, current, attacker-ready
description of a production host that is not this project's, and both surveyed
repositories are private.

What it discloses, by line, kind only:

| Lines | Kind |
|---|---|
| 140-143 | Hosting provider, instance class, region, OS, host name, tailnet node name, RAM, and the **names of four unrelated co-tenant stacks** on the same box, one on 80/443 |
| 151-164 | The complete deploy chain: trigger, CI secret-scan gate and its pinned version, how CI joins the tailnet and under which tag, the SSH user@host, the reset-and-deploy script, the health check, and the one-time provisioning script including a directory mode and an SSH host alias |
| 166-176 | A seven-row table of **where each secret lives** — absolute paths on the VPS, the deploy key filename, and the exact **names of three GitHub repository Secrets**. Values are absent; locations are complete |
| 54, 97, 405 | Loopback service ports, current and predecessor |
| 22, 383, 402 | The two private repository URLs / slugs, and a local checkout path for each |
| 62-89, 124-129, 326-345, 456-472, 525-530 | The **security posture as tested and untested**: which controls are enforced, which were verified live and on what date, which fail open (two named), and which have never been tested — including "the *deny* side of the allowlist has never been tested live" |
| 108-120, 131-136, 178-185 | The authorisation model, that an admin tier exists, that the owner's numeric Telegram ID sits in the clear in two files of the private repo, and that a cron path can act with no human present |
| 232-266 | A reachability analysis naming every condition that would have to become true for the VPS to reach the PLC endpoint — i.e. a checklist |

Publishing this hands a reader the host, the tenants, the deploy path, the secret
inventory, the tested-versus-untested control list and the two fail-open
mechanisms of a private system. It is the single most damaging file in the
repository and it is not close.

**History makes it worse, and deleting the file does not fix it.** The survey has
two committed revisions:

- `58718d2` — revision 1, surveying `rookie-assistant`. Its secret-location table
  is **longer** than revision 2's: it enumerates additional credential *kinds*
  including an infrastructure-provider API key, a VPN auth key and a gateway
  token, names the predecessor's `.env` path, and records the existence and size
  of two untracked local `.env` files.
- `c7d1b29` — revision 2, the current text.

Both are reachable from `main`. A `git rm` at HEAD leaves both intact. The fix is
history rewrite or fresh history (decision 1).

**Also in history, benign but worth knowing:** `bd2ea9a` added
`docs/HANDOFF.md` and `6eb83c4` reverted it. I read the reverted content in full
— it contains no secret and nothing beyond ordinary project state. It is not a
problem; it is listed so the revert is not mistaken for a redaction later.

## 2. BLOCKING — secondary spread of the same identifiers outside the survey

The survey is the concentration, not the whole of it. A fix applied only to
`docs/reports/m4-00-hermes-survey.md` leaves these:

| File | Line | What leaks |
|---|---|---|
| `docs/TODO.md` | 7 | Private repo slug and pinned commit; hosting provider; framework and version; the caveat about the running config |
| `docs/adr/0007-safety-first-gate-order.md` | 25-26 | Provider and region, cited as the reason for the gate order — inside an **accepted, immutable** ADR |
| `docs/briefs/m4r-01-adr-0007-reordering.md` | 38 | Provider |
| `docs/briefs/m4-00-hermes-survey.md` | 7, 14 | Local checkout path for the private repo; "their AI assistant living on a VPS, reached via Telegram" |
| `docs/reports/m4r-01`, `m4r-02`, `docs/briefs/m3r-02`, `m4r-02`, `docs/PLAN.md`, `docs/roadmap.md` | various | Generic only — "Hermes", "Telegram", "an assistant on a VPS", invariant 8. **No fix needed**; a portfolio may say this much |

The line to draw: the *architecture question* ("an assistant reached by Telegram
wants to command the cell; is that engineering access or cell traffic?") is
excellent portfolio material and should stay. The *identifiers* — provider,
region, host names, co-tenants, paths, secret names, control test status — carry
no architectural content and should go. §7 decision 2 puts the redaction-versus-
excision choice on the owner.

## 3. BLOCKING — no LICENSE

Verified absent: `git ls-files` matches no `LICENSE`, `LICENCE`, `COPYING` or
`NOTICE` at any path, and `gh repo view` reports `licenseInfo: null`.

Without one, "public" means readable but not usable: no permission to copy,
modify or reuse is granted, and a portfolio reviewer who wants to run the thing
has no standing to. This is decision 3 and it is a one-file fix.

Related and already tracked: `docs/TODO.md:44` records that the ARIAC asset
harvest is blocked because *that* project declares "TODO: License declaration"
and has no top-level LICENSE. The project already applies this standard
outward; it should meet it inward before publishing.

## 4. MEDIUM — tooling disclosure, and what is genuinely clean

**Clean, verified, no action:** CLAUDE.md §7 as written covers commit messages,
branch names, PR titles and PR bodies. All four pass.

- 86 commits. Author **and** committer are `Ozkan Ceylan
  <ozkannceylan@gmail.com>` on 85 of them. The 86th is `03afa60`, GitHub's own
  "Initial commit" with the standard `noreply` identity — expected, not a leak.
- No `Co-Authored-By`, no generated-with footer, no tooling mention in any
  message. Conventional commits throughout.
- All 8 refs conform to the branch template. No `claude/*` ref exists in any
  ref, tag, stash or reflog — the stray provisioned branch recorded in
  `docs/LESSONS.md:7` was deleted locally and remotely, as claimed.

**Not clean under §7's *spirit*, which check 2 asks about.** The repository
discloses its authoring toolchain structurally, not accidentally:

1. `CLAUDE.md` at the root, by filename and by content (§5's orchestrator /
   subagent / brief / report model).
2. `.claude/settings.json` and ten `.claude/agents/*.md`, each carrying
   `model: <vendor model id>` frontmatter. This was already flagged as F9 in
   `docs/reports/m3-23-verify-commissioning.md:216-222` and left as the owner's
   call; publication is the moment that call has to be made.
3. Two **hard leaks of a tool-specific temp path**, including a session UUID:
   `docs/reports/m3-26-live-loop-run.md:96` and
   `docs/briefs/pub-02-readme-and-media.md:15`. These are not filenames that
   happen to read that way — they are absolute paths into a named tool's
   scratch directory, in committed content.
4. `docs/LESSONS.md:7` and `docs/reports/m0-04-verify.md:20` name the
   provisioned branch by its full tool-prefixed name.

Two honest framings are available and the owner picks (decision 4). Either the
agentic method **is** the portfolio — in which case keep all of it deliberately,
and item 3 is still a bug because a session UUID is not method — or it is not,
in which case §7's spirit says remove it and item 3 must go regardless.

## 5. LOW — personal residue, size, hygiene, claims

### 5.1 Untracked files

| File | Contents | Recommendation |
|---|---|---|
| `HANDOVER.local.md` | Session handover. Self-labelled "LOCAL FILE, NOT COMMITTED. Delete after reading." No secret; does describe the agentic working model and one machine-admin command | Delete. If the pattern recurs, add `*.local.md` to `.gitignore` — the `.local` convention is already established there for `.claude/*.local.json` |
| `check_nodes.py` | 20-line asyncua browse script. Only network value is the documented `192.168.53.1:4840` endpoint | Either delete, or move to `bridge/tools/` and commit deliberately — it is genuinely useful and harmless. Do not leave it loose at the root |
| `bridge/tools/check_session_lifecycle.py` | In-flight work from the concurrent bridge agent | Not audited as final. Re-check before publication |

### 5.2 Screenshots — one confirmed problem

`plc/demo-cell/evidence/watch-table/Screenshot 2026-07-28 144116.png` is a
**full-desktop capture**. Beyond Gazebo and TIA it shows the Windows taskbar with
roughly fifteen personal applications identifiable by icon (media, messaging,
smart-home, a third-party AI assistant), an unread-message badge, the system
clock and date, the keyboard layout, and the TIA title bar with a local project
path. Recommendation: crop to the two application windows and re-commit. The
evidence value is entirely in the watch table.

Method and residual risk, stated so it is not over-read: I extracted PNG
dimensions for all 71 captures and inspected the three tallest (≥1200 px), on
the reasoning that a capture containing the taskbar must be near-full-height.
`144116` has it; `135105` (2555×1391) is cropped just above it and is clean;
`201756` is a TIA dialog only. The remaining 68 were **not** individually
reviewed — an owner spot-check is decision 8. Many do show the TIA title bar
with a local project path, which is the same low-grade exposure as §5.3.

### 5.3 Machine paths

Present in ~20 committed files. Judged **acceptable**, with one exemplary case
worth keeping as-is: `bridge/README.md` §"The venv — the mechanism, not one
machine's path" parameterises `REPO`/`VENV`, states the requirement abstractly,
and then gives two labelled worked examples. That is how a machine path should
appear in a public repository. `sim/setup/WSL_ENVIRONMENT.md` and the evidence
files are environment records where the literal path *is* the datum.

The only information these carry is the OS account name, which equals the
public GitHub handle. No new exposure. No action.

### 5.4 Secrets sweep — negative, as claimed

Zero matches across the tree **and** `git log -p --all` for: tailnet key prefix,
cloud access-key ids, GitHub token prefixes (classic, fine-grained, app), OpenAI
key shape, Slack token shapes, Google API key shape, JWT shape, and any
`-----BEGIN`/PEM header. No tracked file is named `.env`, `*.pem`, `*.key`,
`*.crt`, `*.pfx`, `id_rsa`, or `*token*`/`*secret*`/`*credential*`. Every
`password`/`secret`/`token` hit is either the VDA 5050 handshake-token protocol,
a config field documented as `null` with the value living outside the repository,
or prose asserting invariant 13. `bridge/config/bridge.yaml:43-48` is exactly
right: policy, certificate and key paths present, all `null`, with a comment
saying the files live outside the repo.

Emails: only `ozkannceylan@gmail.com`, in two verification reports quoting the
committer identity. Identical to the git author field. No action.

IPs: `192.168.53.x` (documented PLCSIM subnet) plus, in history and tree,
`172.19.176.1` / `172.19.180.72` / `172.17.0.1` / `10.255.255.254` (WSL and
Docker NAT, ephemeral per boot) and `169.254.83.107` (an APIPA address recording
that the Tailscale adapter had *no* address — the absence is the evidence). All
private, none routable, none stable. No action. Two strings that grep as IPs are
not — `5.15.167.4` is a kernel version and `6.6.3.2` a VDA 5050 spec section.

One incidental: `sim/setup/WSL_ENVIRONMENT.md:291` includes an IPv6 link-local
whose EUI-64 embeds the Hyper-V synthetic adapter MAC. Regenerated per VM, not
hardware. Noted for completeness only.

No real Wi-Fi SSID, hardware MAC or LAN hostname appears anywhere. The home-LAN
subnet collision is described as a `192.168.0.x` overlap without naming the
router or the network.

### 5.5 Size, line endings, README

- Largest blob in history: **4.33 MB** (`bridge/evidence/latency-2026-07-28-plcsim-t1t4.csv.gz`).
  **Nothing exceeds 10 MB.** Whole `.git` is 17 MB. The 71 screenshots are the
  bulk of the tree at roughly 8 MB. Healthy for a public clone; no action.
- **CRLF policy holds.** The index is 100 % clean: 111 `i/lf`, 89 `i/-text`,
  5 `i/none`, and **zero** `i/crlf` or `i/mixed`. 87 files show `w/crlf` in the
  working tree, which is Windows' system-level `autocrlf` doing exactly what
  `.gitattributes` documents at lines 1-8. `*.sh`/`*.py eol=lf` and
  `*.pgm`/`*.gz -text` are all present and correct.
- **Root `README.md` is an 11-byte GitHub stub** (`# amr-agent`) from
  `03afa60`, untouched since. `assets/` does not exist yet. pub-02 is writing
  both; not written here, per the brief. Flagging only that publication without
  that deliverable would present an empty front door.

### 5.6 Concurrency re-sweep

`40b20db` and `7cb60a5` (913 new lines of evidence, plus tracking) were swept
independently for key shapes, credential vocabulary, tooling names, IPs and
machine paths. The only hits are `192.168.53.1` and one labelled venv path. Clean.

### 5.7 Claims check — pass, with one advisory

- `bridge/README.md` "How to run it": abstract, parameterised, two labelled
  examples. A public reader can follow it. **Pass.**
- `sim/setup/install.sh`: targets Ubuntu 24.04/amd64, `ROBOTNIK_WS` is
  env-overridable with its default stated in the header, every step idempotent.
  **Pass.** *Advisory:* the header documents the authoring container's HTTPS
  proxy quirk (`api.github.com` blocked, `raw.githubusercontent.com` allowed) as
  a target condition rather than an artefact. A public reader on an open network
  will not hit it. One clause of rewording, not a blocker.
- CLAUDE.md §4's claim that every top-level directory carries a README opening
  with "This layer must not access": verified for all six —
  `agv/`, `bridge/`, `fleet/`, `plc/`, `sim/`, `docs/`. **Pass.**

### 5.8 Advisory for the public reader — PLC security posture

`docs/interfaces/opcua-nodes.md` §9.10 and the survey's §6 record the
commissioned PLC as message security `None`, CPU access control disabled with
Anonymous holding full rights, and default DB visibility bypassing the
interface's read-only access levels. That is honest engineering documentation of
a tracked open item on a simulated CPU behind a non-routable virtual adapter,
and it should stay. But read next to finding 1's reachability checklist it
composes into something it is not. Whichever way decision 2 goes, the new README
should frame the cell as simulation-only and not reachable from any network.

## 6. Findings, numbered

| # | Severity | Finding | Evidence |
|---|---|---|---|
| 1 | **blocking** | Live private infrastructure fully described — host, tenants, deploy chain, secret inventory, GitHub Secret names, tested/untested controls, two fail-open mechanisms, reachability checklist. Both surveyed repos verified private | `docs/reports/m4-00-hermes-survey.md`, table in §1 above |
| 2 | **blocking** | Same disclosure in history, in two revisions, revision 1 listing *more* credential kinds. `git rm` at HEAD is insufficient | `58718d2`, `c7d1b29` |
| 3 | **blocking** | Identifiers spread beyond the survey, including into an accepted immutable ADR | `docs/TODO.md:7`, `docs/adr/0007:25-26`, `docs/briefs/m4r-01:38`, `docs/briefs/m4-00-hermes-survey.md:7,14` |
| 4 | **blocking** | No LICENSE at any path; `licenseInfo: null` | `git ls-files`, `gh repo view` |
| 5 | medium | Tool-specific temp path with session UUID in committed content, twice | `docs/reports/m3-26-live-loop-run.md:96`, `docs/briefs/pub-02-readme-and-media.md:15` |
| 6 | medium | Authoring toolchain disclosed structurally: `CLAUDE.md`, `.claude/settings.json`, 10 agent files with vendor `model:` frontmatter, tool-prefixed branch name in two docs. Not a §7 breach as written; §7's spirit is the owner's call | §4 above; prior flag F9 at `docs/reports/m3-23-verify-commissioning.md:216` |
| 7 | low | Full-desktop screenshot exposing personal taskbar, clock and local project path | `plc/demo-cell/evidence/watch-table/Screenshot 2026-07-28 144116.png` |
| 8 | low | 68 of 71 screenshots not individually reviewed; method and reasoning stated in §5.2 | — |
| 9 | low | Untracked residue at the root: `HANDOVER.local.md`, `check_nodes.py` | §5.1 |
| 10 | low | Root README is an 11-byte stub; `assets/` absent. pub-02 in flight | `03afa60` |
| 11 | advisory | `install.sh` header states an authoring-container proxy quirk as a target condition | `sim/setup/install.sh:4-5` |
| 12 | advisory | PLC "security None / access control disabled" documentation needs simulation-only framing once public | `docs/interfaces/opcua-nodes.md` §9.10 |
| 13 | pass | Secrets: zero credential values in tree or history. Invariant 13 holds | §5.4 |
| 14 | pass | Attribution: 85/86 commits authored and committed by the owner; no AI/tooling in any message, branch or ref | §4 |
| 15 | pass | Size: largest blob 4.33 MB, nothing over 10 MB, `.git` 17 MB | §5.5 |
| 16 | pass | CRLF: index has zero `i/crlf` and zero `i/mixed`; `.gitattributes` correct | §5.5 |
| 17 | pass | Run instructions are machine-independent and correctly labelled | §5.7 |

## 7. Owner decision list

1. **How to remove finding 1 from history.** Three options. (a) `git filter-repo`
   over the two paths, force-push — keeps 86 commits and their story, rewrites
   every hash, and the pushed `origin/main` at `8d0ba7b` must be force-updated.
   (b) Publish a **fresh-history** public repository (orphan commit, or squash to
   one), keep this one private as the working record — cleanest, cheapest, loses
   the commit narrative that is itself portfolio material. (c) Keep history and
   publish nothing. My recommendation: **(a)** if the 86-commit history is part
   of what you are showing, **(b)** if it is not. Not (c). *Nothing else on this
   list matters until this is decided.*
2. **Redact or excise the Hermes material.** Excise = drop the survey and its
   identifier spread entirely. Redact = keep the architecture question, the
   invariant-8 analysis and the ten decisions, strip provider, region, host
   names, co-tenants, paths, GitHub Secret names and control test status. Note
   the ADR 0007 hit is inside an accepted immutable ADR, so redacting it means a
   superseding ADR, which is a small piece of real work. **Recommend redact** —
   the invariant-8 tension is one of the strongest things in the repository.
3. **License.** One file, gates everything about reuse.
   - **MIT** — shortest, most permissive, universally recognised. No patent
     grant, no attribution-preservation beyond the notice. The default for a
     portfolio project whose goal is to be read and reused freely.
   - **Apache-2.0** — permissive plus an express patent grant and a
     contributor-patent-retaliation clause; requires a NOTICE-style attribution
     on redistribution. The right choice if industrial-automation content and
     patents are a live concern, or if an employer may adopt it. Longer, and its
     `NOTICE` handling is a small ongoing obligation.
   - **BSD-3-Clause** — MIT plus a no-endorsement clause preventing your name
     being used to promote derived works. Choose it if that specific protection
     matters to you; otherwise it buys little over MIT.
   *Recommendation: MIT for a portfolio, Apache-2.0 if you expect employer
   adoption.* Also decide whether the evidence corpus (71 screenshots, 17 gzipped
   captures) falls under the code license or a separate data statement.
4. **Rule on the toolchain disclosure (finding 6).** Keep the agentic method as
   a deliberate part of the portfolio, or remove it under §7's spirit. Note that
   `.claude/agents/*.md` carry a vendor model id, and that CLAUDE.md §7 itself
   mandates tracking `.claude/settings.json` — so "remove it" means amending §7.
   Finding 5 must be fixed either way.
5. **Fix finding 5** — two lines, no judgement needed, but it is in history too
   and rides on decision 1's rewrite.
6. **Crop or drop the taskbar screenshot** (finding 7). Also in history; rides on
   decision 1.
7. **Untracked residue** (finding 9): delete `HANDOVER.local.md`, and either
   delete `check_nodes.py` or promote it to `bridge/tools/`. Consider
   `*.local.md` in `.gitignore`.
8. **Decide whether to review the remaining 68 screenshots** or accept the
   sampling in §5.2 as sufficient.
9. **Decide the fate of the 5 stale remote feature branches** (all ancestors of
   `main`, all template-conformant, all publish by default) and confirm the
   53-commit push is intended as one event.
10. **Re-run this audit after decisions 1-3 land**, against the rewritten
    history. A rewrite is exactly the operation that silently reintroduces what
    it was meant to remove.

Fix 1-4 and the verdict becomes go. Nothing on this list is expensive except
deciding what to do about history, and that decision is one command either way.
