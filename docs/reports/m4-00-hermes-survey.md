# Report m4-00 — Hermes survey

brief:               docs/briefs/m4-00-hermes-survey.md
status:              done — revision 2, surveyed against the real `hermes-assistant` checkout (owner correction). Revision 1's `rookie-assistant` findings are retained in §9 as the superseded predecessor survey
files_changed:       docs/reports/m4-00-hermes-survey.md (this file only; nothing in either external repository was modified)
invariants_touched:  none by this survey. It surfaces the invariant-8 question (§5) and an invariant-11 topology gap (§7) for owner decision, and decides neither
open_questions:      §10 lists eight items this checkout cannot settle; the live running config already provably differs from the deploy-managed one (§10 item 1)
next_suggested:      after decisions 1, 2, 3 and 6, an interface brief for the M4 command node group; no M4 implementation brief before that

Method: static reading only. Nothing was connected to — no VPS, no Telegram, no
tailnet address, no GitHub API, no upstream repository. No secret value appears in
this report; secrets are referenced by path and kind. Both external checkouts were
opened read-only and are unchanged.

---

## 0. Provenance of this revision

The brief's input path `C:\Users\ozkan\projects\hermes-assistant` did not exist,
and revision 1 of this report surveyed the best available candidate,
`C:\Users\ozkan\projects\rookie-assistant`. The owner then corrected the record:
the real Hermes is **`https://github.com/ozkannceylan/hermes-assistant`**, never
present on disk, and provided a fresh clone at

```
…\scratchpad\hermes-assistant
```

**Sections 1-8 below are authoritative and are read from that clone.** All file
paths in them are relative to it. Section 9 retains the predecessor findings,
demoted and labelled superseded.

**Freshness of the clone.** `HEAD` is `fd645b8` *feat(security): gitleaks
pre-push gate for self-sync + CI deploy gate*, dated **2026-07-21**; `main` tracks
`origin/main` with a clean tree. That is seven days old at the time of writing —
not stale in the way revision 1's snapshot was, but not today either, and the
deploy job runs `git reset --hard origin/main`, so `main` may have moved. One
concrete proof that the repository is not authoritative about the *running* system
sits inside the repository: `config/hermes-config.yaml` is a synced snapshot of
the live config (`_config_version: 33`, `stt.enabled: true`, `plugins.enabled:
[]`) and it names model `deepseek-v4-pro`, while the deploy-managed
`config/hermes/config.yaml` names `glm-5.2`. The live config drifts from the
deployed one, and this repo records both.

---

## 1. What it is

| Aspect | Finding | Evidence |
|---|---|---|
| Framework | **NousResearch `hermes-agent`**, MIT, **Python 3.13 + Node 22 on Debian 13**, upstream release **pinned to `v2026.7.7.2`**. Not OpenClaw — a different runtime from the predecessor | `README.md`; `CLAUDE.md` "base pinned to hermes-agent v2026.7.7.2"; `docs/STATUS-ANALYSIS.md` §2 |
| Repository shape | Still a deployment repository — **no application source**: Dockerfile, compose, `config/`, `scripts/`, `.github/`, docs, plus the agent's own workspace state (`SOUL.md`, `AGENTS.md`, `MEMORY.md`, `HEARTBEAT.md`, `USER.md`, `memory/*.md`, `skills/`) | `git ls-files` — 86 files, 41 of them `memory/*.md` |
| Image | Base built locally from a shallow clone of the upstream tag, then a thin app layer adding `jq`, `gnupg`, `rclone`, `gogcli 0.11.0`. No `USER` directive — s6-overlay `/init` starts as root and drops to the remapped user | `scripts/build-hermes-base.sh`; `Dockerfile` |
| Runtime layout | One process, `gateway run`: 20+ platform adapters, session management, cron scheduler and delivery all inside it. Container `hermes`, uid/gid remapped to 1000 to match the host deploy user. State dir `/data/hermes` (host) ↔ `/opt/data` (container) holding `config.yaml`, `gateway.json`, `SOUL.md`, `skills/`, `cron/jobs.json`, `sessions/`, `logs/`, `memories/`, `pairing/`, `workspace/`, `secrets/google/`. A `hermes-dashboard` service exists but only under the opt-in `dashboard` profile, bound `127.0.0.1:9119` | `docker-compose.yml`; `docs/STATUS-ANALYSIS.md` §2.1; `scripts/bootstrap-hermes.sh` |
| Model | `provider: ollama-cloud`, `default: glm-5.2` — bare id, `auto` does not work and the `:cloud` suffix must not be used. OpenRouter and Groq keys present for fallback and STT | `config/hermes/config.yaml`; `docs/RUNBOOK.md` §"Key facts" |
| Agent limits | `max_turns: 90`, `reasoning_effort: medium`, context compression at 0.50, `session_reset: none` (sessions persist) | `config/hermes/config.yaml` |
| How it executes actions | A **toolset** model: skills declare `requires_toolsets: [terminal]` and `dependencies: [delegate_task, session_search, file, memory, cronjob]`. `terminal.backend: local` — the container *is* the sandbox, by explicit decision, and no Docker socket is ever mounted. Terminal `cwd` is `/opt/data/workspace`, timeout 180 s. Subagents exist (`delegate_task`, max 3 concurrent) | `config/hermes/config.yaml`; `config/hermes/skills/*/SKILL.md`; `skills/productivity/self-sync/SKILL.md`; `docs/STATUS-ANALYSIS.md` K6 |
| How new capabilities are added | Four ways: (a) **a skill** — a directory with `SKILL.md` carrying YAML front matter (`name`, `description`, `version`, `dependencies`, `platforms`, `metadata.hermes.tags/category/requires_toolsets`) and shell steps in the body; (b) **a cron job** — `hermes cron create` or the `cronjob` tool writing `/opt/data/cron/jobs.json` with `deliver="telegram:<id>"`; (c) **a CLI installed in the image**, the `gog` pattern; (d) plugins — currently none (`plugins.enabled: []`) | `config/hermes/skills/gog-workspace/SKILL.md`, `…/security-digest/SKILL.md`; `skills/productivity/{self-sync,drive-backup}/SKILL.md`; `config/hermes-config.yaml` |
| Two skill trees | `config/hermes/skills/**` is repo-managed and installed by `deploy.sh` into `/data/hermes/skills/`. The top-level `skills/**` (`self-sync`, `drive-backup`) is **agent-authored workspace content committed by the agent itself**, and `deploy.sh` does *not* install it | `scripts/deploy.sh` (`cp -r config/hermes/skills/. /data/hermes/skills/`); `skills/productivity/self-sync/SKILL.md` |
| The agent can ship to production | The self-sync pipeline pushes workspace files to this repository, and push-to-`main` is the deploy trigger. Two gitleaks gates stand in the way — `scripts/scan-secrets.sh` (pinned v8.30.1, **fails closed** when the binary is missing) before push, and a CI `secret-scan` job that `needs`-gates deploy — but neither is a review gate | `skills/productivity/self-sync/SKILL.md` §"Secret Scan Gate"; `scripts/scan-secrets.sh`; `.github/workflows/deploy.yml` |

**Guardrails that are enforcement rather than prose** — the biggest change from
the predecessor, and the material fact for M4:

- `approvals.mode: smart` with `approvals.cron_mode: deny` — an unattended cron
  session cannot run anything that would need an approval.
- `approvals.deny`, an fnmatch glob list ported from the predecessor's
  `deny-patterns.txt` and **extended with domain rules**: `gog gmail send*`,
  `gog * delete*`, `rm * /data/obsidian-vault*`, `rm * /data/website-content*`.
- An always-on hardline blocklist (`rm -rf /`, `dd`, `mkfs`, fork bombs) and hard
  write-blocks on `~/.ssh`, `.env`, `auth.json`.
- **`HERMES_WRITE_SAFE_ROOT`** — a filesystem write boundary set in compose to
  `/opt/data:/data/obsidian-vault:/data/website-content`. Anything outside is
  hard-blocked; verified live.
- Automatic stripping of `KEY`/`TOKEN`/`SECRET`/`PASSWORD` environment variables
  from `terminal`/`execute_code`, with an explicit `terminal.env_passthrough`
  allowlist (today `CONTENT_API_TOKEN`, `GITHUB_TOKEN`, `GOOGLE_CLIENT_ID`,
  `GOOGLE_CLIENT_SECRET`) — a per-command credential-scoping mechanism.
- Secret redaction in tool output, logs and replies, on by default.
- Prompt-injection scanning of context files, strong enough that `SOUL.md` had to
  be reworded to survive it (`/opt/hermes/tools/threat_patterns.py`, scope
  `context`; a file that trips it is **silently dropped from the prompt**).
- Tirith pre-exec scanning: `tirith_enabled: true`, `tirith_timeout: 5`,
  **`tirith_fail_open: true`** — note the last: if the scanner fails, the command
  proceeds.

Evidence: `config/hermes/config.yaml`; `docker-compose.yml`;
`docs/STATUS-ANALYSIS.md` §2.3; `docs/SECURITY-VERIFICATION.md`;
`docs/RUNBOOK.md`.

## 2. Telegram path

**Long-polling, stated four independent times rather than inferred.**
`docker-compose.yml` header: "gateway needs no inbound ports (Telegram
long-polling)". `docs/STATUS-ANALYSIS.md` §2.1: "Telegram **long-polling** →
inbound port gerekmez". The migration plan: "Zero public ports. Hermes never binds
anything except `127.0.0.1` (dashboard 9119 only). Telegram is long-polling." And
a compose variable exists precisely because the adapter's DoH fallback-IP
discovery hung `start_polling()`: `HERMES_TELEGRAM_DISABLE_FALLBACK_IPS: "1"`.
`docs/RUNBOOK.md` adds an operational rule that only makes sense for a poller:
never call `getUpdates` against the live bot — it steals the update and
409-crashes the poller — use the non-consuming `getWebhookInfo` for diagnostics.
There is no webhook, no inbound port and no TLS terminator in front of the agent.

**Who parses.** The gateway's Telegram adapter inside the upstream image; this
repository contributes configuration only (§10 item 2).

**Where authorisation happens — two layers plus pairing, and one new
distinction.**

- `TELEGRAM_ALLOWED_USERS`, injected from `/opt/hermes/.env` into the container.
- `config/hermes/gateway.json` → `platforms.telegram.extra.allow_from` **and
  `allow_admin_from`**, both a single literal numeric owner ID (value not
  reproduced here).
- Framework default: the gateway denies any user not in an allowlist or paired;
  `hermes pairing approve telegram <CODE>` is the pairing flow.

The new distinction is `allow_admin_from` versus `allow_from` — an admin tier
exists at the platform layer, which M4 could use to separate "chat with Hermes"
from "command the cell" (decision 7).

**What is verified and what is not.** `docs/CUTOVER-CHECKLIST.md` records the DM
path confirmed working against a parallel-phase bot. But
`docs/SECURITY-VERIFICATION.md` lists under **Pending**: "Allowlist enforcement
from a second Telegram account (expect deny/pairing prompt, no agent reply)". So
as of this checkout the *deny* side of the allowlist has never been tested live.
Everything else in that table passed on the live VPS on 2026-07-17 — including a
real attempt to make the agent run `gog gmail send`, which the deny rule
hard-blocked and the agent did not try to circumvent.

**Commands can also originate unattended.** Ten cron jobs deliver to the owner's
Telegram (`MEMORY.md` §"Cron Jobs"): morning report, evening check-in, three
German-course jobs, a 6-hourly heartbeat, the security digest, self-sync at 23:30
and two vault syncs. A cron session is a full agent session with tools, subject to
`cron_mode: deny`. "Telegram-triggered" is therefore not the only way an action
starts, which matters for the M4 criterion (decision 8).

## 3. Deployment

**What runs on the VPS.** The same machine as the predecessor: Hetzner CX22,
Ubuntu, host name `openclawd`, tailnet name `rookie-vps`, 3.7 GiB RAM shared with
other stacks (`website-nextjs`, `website-caddy` on 80/443, `ozvatan-*`,
`belegpilot-*`). Hermes occupies `/opt/hermes` (repo) and `/data/hermes` (state),
container `hermes`, `mem_limit: 1536m`, `pids_limit: 256`,
`no-new-privileges:true`, `tmpfs /tmp`, bridge networks `hermes-net` plus the
external `shared-internal` (which must already exist — the website stack owns it).
Host services inherited unchanged: `obsidian-headless`, `ollama`, `tailscaled`,
`docker`. Host cron `config/cron/hermes-maintenance`: nightly encrypted backup at
03:30 UTC, local retention prune 05:00, Drive-side prune weekly.

**How it is deployed and updated.** Push to `main` (ignoring `docs/**`,
`README.md`, `CLAUDE.md`) → job `secret-scan` runs **gitleaks v8.30.1** over the
checkout and `needs`-gates everything → `deploy` joins the tailnet as an ephemeral
`tag:ci` node (`tailscale/github-action@v4`) → SSH `deploy@rookie-vps` →
`git reset --hard origin/main` → `bash scripts/deploy.sh`, which installs
`config.yaml`, `gateway.json`, `SOUL.md` and `workspace/AGENTS.md` into
`/data/hermes`, copies `config/hermes/skills/`, builds the pinned base image if
missing, rebuilds the app image, restarts the gateway, sleeps 45 s and runs
`scripts/health-check.sh` (container up, gateway process alive, no
traceback/fatal/unauthorized in 10 minutes of logs, **nothing bound publicly**,
`/data` under 85 %). One-time provisioning is `scripts/bootstrap-hermes.sh`:
creates `/data/hermes/{workspace,skills,secrets/google,logs}` at mode 0700, clones
through a repo-scoped deploy key exposed as SSH host alias `github-hermes`,
requires `shared-internal`, seeds `.env` at 0600.

**Where configuration and secrets live — paths and kinds only, no values read.**

| Location | Kind of secret | Read by me? |
|---|---|---|
| `/opt/hermes/.env` on the VPS | Telegram bot token; the Telegram allowlist ID; Ollama / OpenRouter / Groq API keys; GitHub token; Google OAuth client id, client secret and refresh token; `gog` keyring password; website content API token; GPG backup passphrase; pinned `HERMES_VERSION` (names from `.env.example`) | No — not reachable, and not connected to |
| `/data/hermes/secrets/google/{token.json,credentials.json}` (dir 0700) | Google OAuth token and client credentials, read-write so refresh persists | No |
| `/opt/hermes/secrets/rclone.conf` | Google Drive remote credentials for backups | No |
| `~/.ssh/hermes_deploy` on the VPS | Repo-scoped GitHub deploy key | No |
| GitHub repository Secrets | `SSH_PRIVATE_KEY`, `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET` | No |
| `/data/obsidian-headless/.env` on the VPS | Obsidian Sync auth token (host service) | No |
| `.env.example` (tracked) | Placeholders only — the authoritative list of variable **names** | Names only |

`.gitignore` covers `.env`, `.env.*` (except the example), `token.json`,
`credentials.json`, `auth.json`, `rclone.conf`, `/secrets/`, `/data/`, `*.pem`,
`*.key`, `*.gpg`, and two independent gitleaks gates back it up. Worth flagging
without reproducing: the repository does carry non-secret **identifiers** in the
clear — the owner's numeric Telegram ID in `config/hermes/gateway.json` and
`CLAUDE.md`, a Google account address and a Drive folder id inside a skill. Those
are not credentials, but the Telegram ID is an authorisation input, and M4 should
not assume it is private.

**Can it run locally?** Closer than the predecessor, still not a documented path.
Upstream ships its own Dockerfile and compose, the `hermes` CLI supports headless
chat (`docker exec hermes hermes chat -Q -q "…"`), and everything is env-driven.
But this repo's compose hard-binds three absolute host paths (`/data/hermes`,
`/data/obsidian-vault`, `/data/website-content` — literals, unlike the
predecessor's variables) and requires the external `shared-internal` network, so
it cannot come up unmodified off the VPS. There is no override file and no dev
documentation. A local instance for M4 testing is a small but real piece of work.

## 4. OPC UA capability

**Still nothing industrial.** `git grep -in -E
"opc.?ua|asyncua|modbus|s7-1500|plcsim|\bplc\b|amr-agent|mqtt|vda.?5050"` over all
tracked files returns no protocol hits at all; the only ROS 2 / Gazebo matches are
prose about the owner's interests and other projects (`SOUL.md` line 109,
`MEMORY.md` line 22, `memory/2026-06-19.md`). No MCP configuration exists (`mcp`
appears only in two memory lines about a Berlin meetup).

**The framework's own SSRF guard picks the insertion shape.**
`docs/STATUS-ANALYSIS.md` §2.3 records that hermes-agent's SSRF protection
**blocks RFC1918 and CGNAT — the latter being the Tailscale range** — for its web
tool, which is exactly why the existing website revalidation call is made with
`curl` from the `terminal` tool instead. Any reach into a private or tailnet
address must therefore go through `terminal`: an installed binary or script, never
the built-in fetcher. Two clean shapes remain:

- *a skill plus a client binary* — the upstream image is Python 3.13 and
  `asyncua==2.0.1` is already this project's pinned OPC UA client (ADR 0005 D2),
  so a small client is mechanically easy; or
- *a skill plus `curl` to a command endpoint amr-agent owns* — byte-for-byte the
  pattern already working against `website-nextjs`, with a bearer token, and it
  fits `terminal.env_passthrough` as the credential-scoping mechanism (exactly how
  `CONTENT_API_TOKEN` is handled today).

**Where the integration code belongs: amr-agent, as its own layer** — unchanged
from revision 1, and the real repository strengthens the argument. `hermes-assistant`
has no application source; more importantly it is a repository **the agent itself
can push to**, and push-to-`main` is the deploy path, gated only by secret
scanning. Putting amr-agent's node model, write allowlist or OPC UA credentials
there would place the cell's contract in a tree an LLM can modify and ship.
`bridge/` cannot host it either — `bridge/README.md` forbids "**Any control
decision whatsoever**", and choosing what to request is a control decision. What
`hermes-assistant` should carry is a `SKILL.md` naming a closed verb list and the
one command it may run; nothing about nodes, namespaces or endpoints.

## 5. Network reality, and the invariant-8 tension

**This repository contains no tailnet configuration at all.** There is no
`setup-tailscale.sh`, no ACL document, no `TAILSCALE_SETUP.md`; the migration
inherited the environment explicitly — "VPS, Tailscale, SSH modeli, UFW/fail2ban —
aynen" (`docs/STATUS-ANALYSIS.md` §4). What Hermes uses the tailnet for is SSH and
CI: `ssh deploy@rookie-vps` by MagicDNS, and the deploy/backup/security-scan
workflows joining as ephemeral `tag:ci` nodes. Zero public ports from the
assistant, verified live on 2026-07-17 by `ss -tlnp`
(`docs/SECURITY-VERIFICATION.md`); the only public listeners on the box belong to
the website's Caddy.

Because the tailnet setup was inherited, the tailnet *facts* still come from the
predecessor repository, and they are unchanged: the VPS joined with
`--accept-routes=false` and `--advertise-tags=tag:server`, and the documented ACL
has `tag:server` as the **destination** of every rule with **no rule whose `src`
is `tag:server`**. The reachability analysis therefore stands, and it is still
negative. For `rookie-vps` to open `opc.tcp://192.168.53.1:4840` — the
commissioned PLCSIM endpoint, `docs/interfaces/opcua-nodes.md` §9.10 — all of the
following would have to become true: an ACL rule with `src tag:server`; the laptop
advertising `192.168.53.0/24` as a subnet route; the VPS run with
`--accept-routes=true`; the Windows host firewall permitting it; and the
container's egress reaching `tailscale0`, where the `hermes` container sits on
`hermes-net` and `shared-internal` with no tailnet interface of its own (§10 item
5). And at the last recorded measurement the laptop had no tailnet address at all:
`bridge/EVIDENCE_LATENCY.md` §B.9 shows the Tailscale adapter `Up` with an APIPA
`169.254.83.107`, and `Get-NetRoute` showing the only route to `192.168.53.0/24`
on-link on `Ethernet 2`.

**New evidence bearing on the question.** hermes-agent's own SSRF protection
treats RFC1918 *and* the Tailscale CGNAT range as blocked destinations for the
agent's HTTP tool. That is not a ruling on invariant 8 — it is a framework default
about a different threat — but it belongs in front of the owner: even the
assistant's authors treat "the agent reaches a private or tailnet address" as the
exception that requires a deliberate bypass.

**The invariant-8 question, stated plainly and left open.** Invariant 8:
*Tailscale is engineering access only. It is not a data path for cell traffic.*

*Reading A — a Telegram command is engineering access.* A human operator asking
the cell for something is the same category as opening TIA Portal or SSHing in,
and the tailnet has always been the transport for that. Under this reading Hermes
may hold the OPC UA client, invariant 8 is untouched, and M4 is honest provided
the path carries only operator-initiated, aperiodic commands — never cyclic
process data — and never sits between the PLC and the fleet manager, the case ADR
0001 names. What is new is that this reading now comes with a real enforcement
story rather than a promise: the write would run through `terminal` with a token
scoped by `env_passthrough`, whole command shapes can be forbidden by
`approvals.deny` globs (a mechanism already proven live against `gog gmail send`),
and `cron_mode: deny` keeps unattended sessions out of it. The cost is unchanged:
the cell's ability to accept a command depends on a remote-access overlay and a
cloud VPS in another country, so the demonstration must also show the cell
operating normally with both unreachable.

*Reading B — a command that moves equipment is cell traffic.* The project's own
interface document classes every request/handshake node as process data
(`opcua-nodes.md` §1: "Every node here is process data"), and a write that causes
motion is process data by that definition; putting Tailscale beneath it places a
VPN in a cell data path, which is what invariant 8 exists to forbid — PLC↔fleet
manager being the named instance, not the whole rule. Under this reading Hermes is
**not** the OPC UA client: the tailnet carries *intent* to an authenticated
cell-side command service, which performs the write on the cell network. This is
also the only reading compatible with ADR 0004's own wording — "a Hermes agent
running on the **same server**" (`docs/adr/0004-…` line 43) — which the real
deployment contradicts exactly as the predecessor survey found: Hermes is a
Hetzner VPS in Falkenstein, the PLC is on this laptop. ADR 0004 is accepted and
immutable, so that conflict closes with a superseding ADR under either reading.

I decide neither.

## 6. Write scope

**The node-side answer is unchanged, because it is a property of the node model,
not of Hermes.** The `DemoCell` interface carries exactly 15 nodes: `Input/` ×7
(client-writable but owned by the Gazebo cell, with the bridge as sole writer per
§9.1 — a second writer breaks invariant 10, and writing `PanelStartPressed` would
be impersonating the operator panel), `Output/ConveyorSpeedCommand` ×1 (actuator,
read-only, and writing it is exactly what the gate criterion forbids), `Status/`
×5 (read-only PLC verdicts) and `Link/` ×2 (the bridge's heartbeat and the PLC's
verdict on it). §9.8 states that "a client-writable conveyor command node, or a
run/stop bit alongside `ConveyorSpeedCommand`" is **deliberately absent**. M4
therefore needs a **new request/handshake node group** in the shape the same
document already uses for the fleet manager (§5-7: a client-written request bit
plus an opaque token, answered by PLC-owned `Ready`/`Busy`/`Done`/`Fault` and a
token echo, with the PLC deciding whether and when to act). Specifying it is an
interface brief, not this survey.

**Server-side enforcement is still absent on the commissioned PLC.** Message
security `None`, CPU access control *disabled* (Anonymous holds full rights
including OPC UA), and default DB visibility means every `DemoCell` value is also
reachable under `Objects/DataBlocksGlobal`, where the interface's read-only access
levels do not apply — `opcua-nodes.md` §9.10 plus the §9.8 open item, which defers
clearing *Accessible from HMI/OPC UA* to a later gate.

**What has genuinely improved is the Hermes side.** Unlike the predecessor, whose
guardrails were bash hooks matching shell strings plus persona prose, this runtime
offers mechanisms that could hold a command path:

- `approvals.deny` is a live, tested gate — an attempt to run `gog gmail send` was
  hard-blocked and the agent did not bypass it (`docs/SECURITY-VERIFICATION.md`).
  A deny glob over command shapes carrying an `Output/` node path is the same kind
  of rule.
- `HERMES_WRITE_SAFE_ROOT` is an image-level filesystem boundary, verified.
- `terminal.env_passthrough` scopes which credentials a command can even see.
- `cron_mode: deny` keeps unattended sessions from executing approval-worthy work.

Two caveats belong in front of the owner before any of that is called enforcement:
**`tirith_fail_open: true`** means a pre-exec scanner failure is a pass, and
**`approvals.mode: smart`** means the model participates in deciding what needs
asking. Neither is a substitute for a barrier outside the agent. The strongest
available guarantee remains architectural, and the node model already encodes it:
if Hermes can only set a request bit, and the PLC forms every output from its
cycle-running flag and interlocks, then even a fully compromised Hermes can only
*ask*.

## 7. Layer placement

Hermes is neither the fleet manager (it assigns no orders, owns no traffic) nor
the bridge (it translates no signals and must carry no cyclic data). It is an
**operator terminal that happens to be reachable from a phone** — a human
interface above the cell. The adjacency invariant 11 would need:

```
operator (Telegram)
   -> Hermes  (intent: a named command, no protocol, no node ids)
      -> cell-side command client  (the only OPC UA client for commands)
         -> PLC  (OPC UA server; decides acceptance from its interlocks)
```

and the boundaries it must not cross: no adjacency to ROS 2 or Gazebo, none to the
bridge process or its state, none to MQTT/VDA 5050, none to the F-CPU or any
safety path, and no reading of PLC logic state to make its own decisions.

**This needs an ADR.** CLAUDE.md §3 has exactly three subgraphs — Fixed equipment,
Fleet layer, Vehicle — and **no operator/HMI layer at all**. M4 as written
therefore adds a box to a LOCKED diagram, which is the ADR 0005 situation twice
over: a component that cannot live inside an existing layer without weakening that
layer's boundary statement becomes its own layer (LESSONS 2026-07-27;
`bridge/README.md` forbids control decisions, so the command client cannot go
there either).

**One addition the real repository forces.** Hermes has a cron scheduler with ten
live jobs, a 6-hourly heartbeat and `delegate_task` subagents, so a command could
originate with no human in the loop. The M4 criterion says "Telegram-triggered";
whether an autonomously scheduled command is in scope, or explicitly out of it, is
a decision and not a detail (decision 8).

## 8. Lineage: successor, not a separate build

Hermes is a **re-platform on inherited infrastructure**, and both repositories say
so. `README.md`: "Successor to the OpenClaw-based 'Rookie' deployment
(`ozkannceylan/rookie-assistant`)"; `CLAUDE.md`: "Successor of the OpenClaw-based
'Rookie'". The shared lineage is concrete: the `approvals.deny` list is "ported
from rookie deny-patterns.txt"; the `gogcli` version and install block are
identical; `config/hermes/SOUL.md` is `rookie-persona.md` with the name changed
plus an added instruction not to touch the legacy `/data/obsidian-vault/rookie/`
folder; the tailnet host is still `rookie-vps`; the same `shared-internal`
network, Google OAuth client, Drive backup pattern, host `obsidian-headless`
service and CI shape carry over; a vault-sync cron still writes into `rookie/`.
What is genuinely new: the runtime (OpenClaw/Node → hermes-agent/Python 3.13), the
config format (`openclaw.json` → `config.yaml` + `gateway.json` + `.env`), the
guardrail mechanism (bash hooks → `approvals`/Tirith/`HERMES_WRITE_SAFE_ROOT`/env
stripping), the state directory (`/data/openclaw` → `/data/hermes`), the CI secret
gate, and the agent's own self-sync-to-GitHub pipeline. Same box, same
integrations, same security posture, different agent.

---

## 9. Predecessor survey (superseded)

Revision 1 surveyed `C:\Users\ozkan\projects\rookie-assistant`, HEAD `b6b178b`
dated 2026-05-04 — the OpenClaw-based "Rookie" deployment, whose `README.md` there
still calls itself "Charlie". Its findings, condensed: an OpenClaw gateway
(`ghcr.io/openclaw/openclaw`) bound to `127.0.0.1:18789` with token auth; model
`ollama/glm-5.1:cloud` via the host ollama proxy; behaviour defined by
`config/openclaw/rookie-persona.md`; capabilities added as `SKILL.md` files
(`config/openclaw/skills/security-digest/`), `PreToolUse`/`PostToolUse` bash hooks
(`validate-exec.sh` + `deny-patterns.txt`, `guard-secrets.sh`,
`audit-external.sh`) and VPS-managed plugins; `"tools": {"profile": "full"}` with
`sandbox.mode: "off"`; Telegram by polling with `dmPolicy: "allowlist"` and a
single `allowFrom` ID; deploy by push-to-`main` → ephemeral `tag:ci` tailnet node →
`git reset --hard origin/main` on `/opt/rookie` with a JSON config merge
(`scripts/merge-openclaw-config.py`); secrets in `/opt/rookie/.env`, a
`google-secrets` docker volume and GitHub Secrets; zero OPC UA, MQTT or MCP
anywhere; and the tailnet configuration (`scripts/setup-tailscale.sh`,
`docs/TAILSCALE_SETUP.md`, `docs/VPS_CONNECTION_GUIDE.md`) that Hermes inherits
but does not restate.

**What carries over and what does not.** Carried over unchanged: the VPS and its
hardening, the tailnet model with its ACL and routing facts (§5 still cites that
repository for them, because Hermes ships no tailnet config of its own), the
`shared-internal` network and website-content pattern, Google OAuth and `gog`, the
Obsidian vault plus host `obsidian-headless`, the CI shape, the persona's content
and security rules, and every strategic conclusion — nothing speaks OPC UA, the
integration code belongs in amr-agent, Hermes is an operator layer absent from the
§3 topology, and no `DemoCell` node may legitimately take a command. Superseded,
and not to be relied on: every runtime, configuration and enforcement detail — the
OpenClaw gateway and its port, `openclaw.json` and its merge script, the
hooks-and-deny-patterns guardrail model, `tools.profile: full` with `sandbox:
off`, the `/data/openclaw` state layout, the plugin mechanism and the model
selection. In particular, revision 1's judgement that node-level restrictions
"would be advisory to a component that can bypass them" was correct about OpenClaw
but is **too pessimistic about Hermes**, which has real approval, write and
env-scoping boundaries (§6). Revision 1's staleness caveat also disappears: this
checkout is a week old rather than three months, and it is the right repository.

---

## 10. What could not be determined

1. **What the VPS runs right now.** The clone is current to 2026-07-21 and I did
   not fetch or connect. Stronger than that: the repository itself shows the live
   config diverging from the deploy-managed one (`config/hermes-config.yaml`
   `deepseek-v4-pro`, `_config_version: 33`, `stt.enabled: true` versus
   `config/hermes/config.yaml` `glm-5.2`), so even a fresh clone would not be
   authoritative about the running configuration.
2. **hermes-agent's own behaviour.** The base image is built from a shallow clone
   of the upstream tag at build time, so the actual toolset inventory, the
   semantics of `approvals.mode: smart`, the exact SSRF-blocked ranges, Tirith's
   behaviour, the pairing flow and `threat_patterns.py` are described in this
   repo's notes, not verified in code here.
3. **Whether the top-level `skills/` tree ever reaches the agent.**
   `scripts/deploy.sh` installs only `config/hermes/skills/`; `self-sync` and
   `drive-backup` live at the repository root as agent-authored workspace content.
4. **Whether the Telegram allowlist actually denies.**
   `docs/SECURITY-VERIFICATION.md` still lists the second-account test as
   pending; only the allow path is evidenced.
5. **Container egress to the tailnet.** `hermes` is on bridge networks with no
   tailnet interface; whether it can route to `100.x` and whether MagicDNS
   resolves inside `hermes-net` needs a live test, not a file.
6. **The live tailnet ACL and device list**, and whether this laptop is on the
   tailnet at all — the last recorded measurement says it was not
   (`bridge/EVIDENCE_LATENCY.md` §B.9).
7. **Cutover state.** `docs/CUTOVER-CHECKLIST.md` has unchecked soak boxes (7-day
   cron, 7-day backups, CI green) and no decommission sign-off, and decision K1
   means a parallel-phase bot token may still be the one in use. Which bot
   identity a cell command would arrive on is therefore unsettled.
8. **Whether Hermes exposes any inbound surface a cell-side component could call
   into.** The API server is documented as off by default and the dashboard is an
   opt-in loopback profile; not verified. This matters only for Reading B, where
   amr-agent might want to *ask* Hermes for confirmation rather than be called.

---

## Owner decisions required before M4 is briefed

1. **Rule the invariant-8 question**: is a Telegram-triggered command *engineering
   access* (Hermes holds the OPC UA client, the tailnet carries the write) or
   *cell traffic* (the tailnet carries intent only, a cell-side executor performs
   the write)? Both readings, with consequences, are in §5 (evidence: CLAUDE.md §2
   invariant 8 versus `docs/interfaces/opcua-nodes.md` §1, which classes every
   request node as process data; and hermes-agent's own SSRF guard blocking
   RFC1918 + Tailscale CGNAT for its web tool, `docs/STATUS-ANALYSIS.md` §2.3).
2. **Decide whether ADR 0004's M4 premise is amended by a superseding ADR or the
   deployment is changed to match it** — the ADR says "a Hermes agent running on
   the same server", while Hermes runs on a Hetzner CX22 in Falkenstein and the
   PLC runs on this laptop (evidence:
   `docs/adr/0004-gate-reordering-plc-loop-first.md` line 43;
   `hermes-assistant/docs/STATUS-ANALYSIS.md` §1.1, `docs/RUNBOOK.md`).
3. **Approve or refuse a new operator/HMI box and its adjacency in the §3
   topology, via an ADR on the ADR 0005 precedent** — the locked diagram has no
   operator layer, so M4 as written modifies it (evidence: CLAUDE.md §3; LESSONS
   2026-07-27 on `bridge/` becoming top level).
4. **Decide where the command-path code lives.** The evidence points to a new
   top-level amr-agent layer, with `hermes-assistant` carrying only a `SKILL.md`
   and a closed verb list — note that `hermes-assistant` has no application source
   and is a repository **the agent itself pushes to**, with push-to-`main` as the
   deploy path gated only by gitleaks (evidence:
   `skills/productivity/self-sync/SKILL.md` §"Secret Scan Gate";
   `.github/workflows/deploy.yml`; `bridge/README.md` "Any control decision
   whatsoever").
5. **Decide the transport shape**, given that hermes-agent's web tool cannot reach
   private or tailnet addresses and the working pattern for local services is
   `terminal` + `curl` + a token in `terminal.env_passthrough`: an OPC UA client
   inside the agent container, or an HTTP command endpoint amr-agent owns
   (evidence: `docs/STATUS-ANALYSIS.md` §2.3 and K8; `config/hermes/config.yaml`
   `terminal.env_passthrough`; `SOUL.md` §"Content API + Revalidation").
6. **Decide the M4 command node group in principle** — a new request/handshake
   group with an opaque token and PLC-owned `Ready`/`Busy`/`Done`/`Fault`, since
   no existing node may legitimately take a command (evidence: `opcua-nodes.md`
   §9.1, the bridge is the sole writer of `Input/`; §9.8 "a client-writable
   conveyor command node … deliberately absent"; §5-7 for the pattern to copy).
7. **Decide the authorisation model for a cell command.** Hermes now has an admin
   tier (`allow_admin_from`) distinct from the user allowlist, and real deny
   globs — but the *deny* side of the allowlist has never been tested from a
   second account, and which bot identity is live is unsettled (evidence:
   `config/hermes/gateway.json`; `docs/SECURITY-VERIFICATION.md` §Pending;
   `docs/CUTOVER-CHECKLIST.md`; `docs/STATUS-ANALYSIS.md` K1).
8. **Decide whether "Telegram-triggered" excludes autonomously originated
   commands.** Hermes runs ten cron jobs, a 6-hourly heartbeat and
   `delegate_task` subagents, so a command need not have a human in the loop
   (evidence: `MEMORY.md` §"Cron Jobs"; `skills/productivity/self-sync/SKILL.md`;
   `config/hermes/config.yaml` `approvals.cron_mode: deny`).
9. **Decide whether M4 requires a barrier outside the agent before the
   demonstration.** Hermes-side gates are real but two of them yield under
   failure — `tirith_fail_open: true` and `approvals.mode: smart` — while the PLC
   side has access control disabled, security `None`, and a DB path that bypasses
   read-only levels (evidence: `config/hermes/config.yaml`; `opcua-nodes.md`
   §9.10 and the §9.8 open item).
10. **Decide whether tailnet reachability work is in M4's scope, and whether
    Hermes may ever be a dependency of the demonstration or only a convenience
    over it** — the VPS runs with `--accept-routes=false`, the documented ACL has
    no `src tag:server` rule, the laptop had no tailnet address at the last
    measurement, and invariant 2 makes loss of network a degraded mode rather than
    a failure (evidence: `rookie-assistant/scripts/setup-tailscale.sh` and
    `docs/TAILSCALE_SETUP.md` step 7, still the only tailnet config in either
    repo; `bridge/EVIDENCE_LATENCY.md` §B.9; `docs/roadmap.md` M4 row).
