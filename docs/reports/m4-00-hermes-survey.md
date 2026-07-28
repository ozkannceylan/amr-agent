# Report m4-00 — Hermes survey

brief:               docs/briefs/m4-00-hermes-survey.md
status:              done — with the input-path correction of §0, which the owner must rule on before any M4 brief cites a path
files_changed:       docs/reports/m4-00-hermes-survey.md (this file only; nothing in the external repository was modified)
invariants_touched:  none by this survey. It surfaces the invariant-8 question (§5) and an invariant-11 topology gap (§7) for owner decision, and decides neither
open_questions:      §8 lists eight items that static reading of this checkout cannot settle; the first is whether the surveyed repository is Hermes at all
next_suggested:      after decisions 1, 2, 3 and 6, an interface brief for the M4 command node group; no M4 implementation brief before that

Method: static reading only. Nothing was connected to — no VPS, no Telegram, no
tailnet address, no GitHub API. No secret value appears in this report; secrets
are referenced by path and kind. The external checkout was opened read-only and
is unchanged (`git status` there reports the same two pre-existing untracked
paths, `.codex-merge-test/` and `scripts/__pycache__/`).

---

## 0. Correction: the brief's input path does not exist

`C:\Users\ozkan\projects\hermes-assistant` **does not exist**, and no directory
matching `*hermes*` exists anywhere under `C:\Users\ozkan\projects` (recursive
`Get-ChildItem -Filter *hermes*`, depth 2) or under `C:\Users\ozkan` at depth 4
(`find -iname "*hermes*"`). The only `hermes` path on the machine is an Obsidian
note folder, `C:\Users\ozkan\OneDrive\Documents\MyNotes\hermes\`. A
case-insensitive content grep for "hermes" across `projects/` (`*.md`, `*.json`,
`*.yml`, `*.yaml`, `*.sh`, `*.py`) returned only numpy's `hermite_e.py` files —
no project refers to Hermes by name.

The checkout surveyed instead is **`C:\Users\ozkan\projects\rookie-assistant`**,
selected on this evidence:

- It is a Telegram-only personal assistant on a Hetzner VPS — the owner's
  description (`docs/ARCHITECTURE.md` §1, `CLAUDE.md` line 3 there).
- The two notes in `MyNotes\hermes\` carry `source: hermes` front matter and one
  is titled *Hermes Migration Test* — "Migration from the previous assistant to
  Hermes is working correctly", dated 2026-07-17 — i.e. Hermes writes into the
  vault that this deployment owns (`/data/obsidian-vault`, synced by the host
  `obsidian-headless` service; `config/systemd/obsidian-headless.service`).
- No other candidate exists: `projects/rookie` is a different, older
  TypeScript/Hetzner project, and nothing else on the machine speaks Telegram.

**Three identities appear in one repository**: `README.md` says *Charlie*, every
config and script says *Rookie*, and the vault notes say *Hermes*. Treat the
name as unsettled, not as three components.

**The checkout is stale.** `HEAD` is `b6b178b`, dated **2026-05-04**;
`.git/FETCH_HEAD` is dated the same day; `git rev-list --left-right --count
origin/main...HEAD` is `0 0`, so the local main matches only a three-month-old
fetch. The deploy job runs `git reset --hard origin/main` on the VPS
(`.github/workflows/deploy.yml`), so **what the VPS runs today may be
substantially different from what this report describes**, and the July rename
to "Hermes" is invisible in this tree. Everything below is a description of the
2026-05-04 snapshot, not of the live VPS. I did not guess past it.

---

## 1. What it is

| Aspect | Finding | Evidence (paths relative to `rookie-assistant/`) |
|---|---|---|
| Framework | **OpenClaw**, an off-the-shelf agent gateway. The repository contains **no application source** — no `src/`, no `package.json`, no test suite. It is a deployment repository: one Dockerfile, one compose file, config, shell scripts, CI, docs | `git ls-files` (63 tracked files); `Dockerfile` line 11 `FROM ghcr.io/openclaw/openclaw:${OPENCLAW_VERSION}` |
| Language | Node.js/TypeScript upstream (`node dist/index.js gateway`), invisible here. Repo-side glue is bash plus two Python 3 scripts | `docker-compose.yml` `command:`; `scripts/*.sh`, `scripts/merge-openclaw-config.py` |
| Runtime layout | One long-running container `rookie-gateway` serving an HTTP gateway bound to `127.0.0.1:18789`, token auth, never public. A second `openclaw-cli` service exists under the `cli` profile for pairing/admin. Vault sync runs as a **host** systemd unit, not in Docker | `docker-compose.yml` (ports, profiles); `config/openclaw/openclaw.json` `gateway.bind: "loopback"` |
| Model | Primary `ollama/glm-5.1:cloud` reached at `http://host.docker.internal:11434`, fallbacks `ollama/minimax-m2.7:cloud` then `openrouter/minimax/minimax-m2.5`. Anthropic/OpenAI/Groq keys are wired in the environment but are not the configured provider | `config/openclaw/openclaw.json` `agents.defaults.model`, `models.providers.ollama`; `docker-compose.yml` env block |
| How it executes actions | `"tools": {"profile": "full"}` with `agents.defaults.sandbox.mode: "off"` — the agent has the full tool profile including **unsandboxed shell and file tools inside the container** | `config/openclaw/openclaw.json` lines 30-32, 72-74 |
| Behaviour definition | A system-prompt file copied to `/data/openclaw/` on every deploy. It is where "Gmail is draft-only", "never delete files", "always confirm destructive actions" live — i.e. these are **prompt policy, not enforcement** | `config/openclaw/rookie-persona.md`; `deploy.yml` `for f in config/openclaw/*.md; ... cp -f` |
| How new capabilities are added | Three mechanisms: (a) **skills** — a directory with `SKILL.md`, YAML front matter carrying `name`, `description`, `trigger`, `schedule`, and a numbered list of shell steps; (b) **hooks** — `PreToolUse`/`PostToolUse` bash scripts; (c) **plugins** — VPS-managed, deliberately never touched by the repo merge | `config/openclaw/skills/security-digest/SKILL.md` (the only skill, `trigger: cron`, `schedule: "0 8 * * *"`); `config/openclaw/hooks/*.sh`; `scripts/merge-openclaw-config.py` `VPS_ONLY_KEYS = {"meta","wizard","audio","commands","plugins"}` |
| Available in-container tooling | `curl`, `jq`, `gnupg`, `rclone`, `git`, `python3`, `python3-venv`, `python3-pip`, plus the `gog` CLI for Google Workspace. Precedent exists for a Python venv on the `/data` volume (`notebooklm-py`) | `Dockerfile` lines 21-40; `scripts/notebooklm-bootstrap.sh` |
| Existing outbound integrations | Google Workspace via `gog`; the Obsidian vault as a mounted directory; and the portfolio website via **an HTTP API on the host plus a shared mounted directory** — the closest existing analogue to an amr-agent command path | `config/openclaw/rookie-persona.md` §"Website Content Management"; `docker-compose.yml` `/data/website-content` mount, `extra_hosts: host.docker.internal:host-gateway`, `CONTENT_API_TOKEN` |
| Guardrails that are real code | `validate-exec.sh` blocks exec/shell calls matching `deny-patterns.txt` (exit 2) and logs ALLOW/BLOCK; `guard-secrets.sh` blocks outbound messages containing API-key/token shapes; `audit-external.sh` appends an audit line per external tool call. All three are **pattern matchers over shell strings** — none of them understands a protocol write | `config/openclaw/hooks/validate-exec.sh`, `deny-patterns.txt`, `guard-secrets.sh`, `audit-external.sh` |

Adding an amr-agent capability therefore means: a `SKILL.md` under
`config/openclaw/skills/`, whatever CLI it calls installed in the image or a
venv, and a `git push` to `main`.

## 2. Telegram path

**Polling, not webhook.** `docs/ARCHITECTURE.md` §2 draws
`Ozkan (Telegram) -> Telegram API -> OpenClaw Gateway (polling)`, and §11 lists
"Webhook mode: switch Telegram from polling to webhook (needs TLS termination)"
as an explicitly *future* item. This is corroborated structurally: the container
publishes only `127.0.0.1:18789`, UFW default-denies inbound, and there is no
reverse proxy or TLS anywhere (`docs/ARCHITECTURE.md` §3, §5.1;
`docker-compose.yml`). Nothing inbound from Telegram is possible, so the
gateway must be reaching out.

**Who parses.** OpenClaw's own Telegram channel, inside the image. The
repository contributes configuration only — `channels.telegram` in
`config/openclaw/openclaw.json` — so message parsing, tool dispatch and skill
loading could not be read here (§8, item 3).

**Where authorisation happens.** In that same config block, and nowhere else:

- `dmPolicy: "allowlist"`, `allowFrom: ["${TELEGRAM_OWNER_ID}"]` — a single
  numeric Telegram user ID, substituted from the environment.
- `groupPolicy: "disabled"` — never responds in groups.
- Plus a one-time pairing approval (`openclaw pairing approve telegram <CODE>`,
  `docs/ARCHITECTURE.md` §10).

So the entire gate on "who may command Hermes" is **one Telegram user ID plus
possession of the bot token**. There is no second factor, no per-command
confirmation enforced by code, and no notion of a privileged command class.
"Ask for explicit confirmation before destructive operations" exists only as
prose in `config/openclaw/rookie-persona.md`. This matters for M4 (§6, decision 8):
a cell command would inherit a trust model designed for reading email and
writing notes.

## 3. Deployment

**What runs on the VPS.** Hetzner Cloud CX22 (2 vCPU / 4 GB / 40 GB), Ubuntu
24.04, Falkenstein/Nuremberg, working directory `/opt/rookie`
(`docs/VPS_CONNECTION_GUIDE.md` §1):

- `docker compose` stack: `rookie-gateway` (always), `rookie-cli` (profile `cli`).
- Host systemd unit `obsidian-headless` running `ob sync --continuous` over
  `/data/obsidian-vault` (`config/systemd/obsidian-headless.service`).
- Host cron: disk alarm every 15 min, backup retention prunes, plugin-runtime
  prune (`config/cron/rookie-maintenance`).
- Volumes `/data/openclaw`, `/data/openclaw/workspace`, `/data/obsidian-vault`,
  `/data/website-content`, and the docker volume `rookie_google-secrets`.
- Networks `rookie-net` (bridge) and `shared-internal` (**external**, defined
  outside this repository — the website stack's network).

**How it is deployed and updated.** Push to `main` (excluding `docs/**`,
`README.md`, `CLAUDE.md`) triggers `.github/workflows/deploy.yml`, which joins
the tailnet as an ephemeral `tag:ci` node via `tailscale/github-action@v4`,
SSHes to `deploy@rookie-vps`, then `git fetch` + `git reset --hard origin/main`,
`docker compose build --pull`, copies `config/openclaw/*.md` into
`/data/openclaw/`, merges `openclaw.json` with
`scripts/merge-openclaw-config.py` (repo-managed sections replace VPS ones;
`botToken`, `accounts`, provider `apiKey`, `meta`, `wizard`, `audio`,
`commands`, `plugins` survive), `docker compose up -d`, then polls health for up
to 10 minutes and probes `openclaw models status` and `openclaw channels
status`. `scripts/deploy.sh` performs the same sequence manually on the box.

**Where configuration and secrets live — paths and kinds only, no values read.**

| Location | Kind of secret | Read by me? |
|---|---|---|
| `/opt/rookie/.env` on the VPS | Telegram bot token, model-provider API keys, Google OAuth client secret and refresh token, GitHub PAT, gateway token, GPG backup passphrase, Tailscale auth key, Tailscale OAuth secret, Obsidian auth token, Hetzner API key, website content API token (names from `.env.example`) | No — not reachable, and not connected to |
| `rookie-assistant/.env` and `rookie-assistant/.env.rookie` (untracked, local) | Same kinds, real values | **No.** Existence and size noted only |
| `rookie-assistant/.env.example` (tracked) | Placeholders only; the authoritative list of variable **names** | Names only |
| Docker volume `rookie_google-secrets` → `/app/secrets/google/{token.json,credentials.json}`; local `rookie-assistant/secrets/google/` | Google OAuth token and client credentials | No |
| GitHub repository Secrets | `SSH_PRIVATE_KEY`, `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET` | No |
| `/data/obsidian-headless/.env` on the VPS | Obsidian Sync auth token | No |

`.gitignore` covers `.env`, `.env.*` (except the example), `secrets/`, `*.pem`,
`*.key`, `token.json`, `credentials.json`, `rclone.conf`, `*.gpg` — consistent
with amr-agent invariant 13, and no secret value is tracked in the repository as
far as the tracked file list shows.

**Can it run locally?** In principle yes, not in practice as documented. All
paths are environment-overridable (`OPENCLAW_CONFIG_DIR`,
`OPENCLAW_WORKSPACE_DIR`, `OBSIDIAN_VAULT_PATH`, `OPENCLAW_GATEWAY_PORT`), and
`docs/ARCHITECTURE.md` §4 lists a `docker-compose.override.yml` "local dev
overrides (not deployed)" — but that file is **gitignored and absent from the
tree**, so no local configuration exists to inspect. Three things are pinned to
the VPS shape: the `shared-internal` external network must already exist, the
`/data/website-content` host mount is absolute, and the model provider is
`host.docker.internal:11434`. `docs/RUNBOOK.md` is ops-on-VPS only. A local test
instance is a small piece of work, but it is work, and it does not exist today.

## 4. OPC UA capability

**Nothing in the repository speaks OPC UA, or any industrial protocol.**
`git grep -in -E "opc.?ua|asyncua|modbus|s7-1500|plcsim|\bplc\b|amr-agent|mqtt|vda.?5050"`
over all tracked files returns **zero matches**. There is also no MCP
configuration anywhere (`mcpServers` does not appear); the only `plugin` hits are
disk-cleanup scripts and the "never install plugins without approval" prose.

**Could a client be added cleanly?** Two shapes are available, and the repo's
own history prefers the second:

- *In-agent client*: a `SKILL.md` plus an OPC UA client in the image or in a
  venv on `/data` (`python3`/`python3-venv` are already installed for
  `notebooklm-py`; `scripts/notebooklm-bootstrap.sh` is the precedent). This
  puts amr-agent's node model, its allowlist and its credentials inside the
  assistant's image — and inside a container whose agent has unsandboxed shell.
- *HTTP boundary*: Hermes calls a small command service that amr-agent owns,
  exactly the pattern already in production for the portfolio website — a host
  service reached via `host.docker.internal`, authenticated with a bearer token
  (`CONTENT_API_TOKEN`), with the persona holding only the verb list. Hermes
  never holds the protocol; it holds an intent and a token.

**Where the integration code should live: in amr-agent, as its own layer.** The
repo structure argues it plainly. `rookie-assistant` has no application source
directory at all, no tests, and no dependency manifest — it is config, scripts,
CI and docs around a third-party image, deployed by a separate pipeline onto a
separate machine. Application code has no home there. On the amr-agent side,
`bridge/` already owns the project's only OPC UA client
(`bridge/amr_bridge/opcua_side.py`, `asyncua==2.0.1` pinned per ADR 0005 D2) and
its write allowlist (`bridge/amr_bridge/config.py`,
`bridge/tools/check_write_allowlist.py`) — but `bridge/README.md` forbids "**Any
control decision whatsoever**", and a command path is a control decision by
construction: it decides what to request and when. Putting it in `bridge/` would
weaken that boundary, which is the exact situation LESSONS 2026-07-27 and ADR
0005 answered by making a component its own top-level layer. See §7 and
decision 4.

## 5. Network reality, and the invariant-8 tension

**What the config says about the tailnet.** The VPS joins as MagicDNS hostname
`rookie-vps` with `--advertise-tags=tag:server`, `--accept-routes=false`,
`--accept-dns=true`, and a reconciliation pass that sets `--ssh=false` so CI can
use OpenSSH (`scripts/setup-tailscale.sh`). UFW default-denies inbound and the
public SSH port is removed once tailnet SSH works
(`config/security/ufw-rules-tailscale.sh`, `docs/TAILSCALE_SETUP.md` step 6);
`docs/VPS_CONNECTION_GUIDE.md` §1-2 states "zero public ports", SSH over
Tailscale only. The recommended ACL (`docs/TAILSCALE_SETUP.md` step 7) is:
`autogroup:member -> tag:server:*` and `tag:ci -> tag:server:22`.

**Direction matters, and the documented ACL has no rule for the direction M4
needs.** Every documented rule has `tag:server` as *destination*. There is no
rule whose `src` is `tag:server`, so as documented the VPS cannot initiate a
connection to the laptop at all. Laptop → VPS is allowed; VPS → laptop is not.

**The PLC is not on the tailnet, and is not trivially reachable from it.** The
commissioned endpoint is `opc.tcp://192.168.53.1:4840` — a PLCSIM Advanced
instance on `192.168.53.1/24` behind the laptop's virtual adapter
`192.168.53.241/24` (`docs/interfaces/opcua-nodes.md` §9.10). For `rookie-vps`
to open that socket, all of the following would have to be true: an ACL rule
with `src tag:server`; the laptop advertising `192.168.53.0/24` as a subnet
route; the VPS started with `--accept-routes=true` (it is explicitly `false`
today); the Windows host firewall permitting forwarded traffic to the PLCSIM
adapter; and the gateway container's egress reaching `tailscale0` on the host
(the container is on Docker bridge networks with no tailnet interface of its
own — plausible via host NAT, unverified statically, §8 item 4).

**And as last measured, the laptop had no tailnet address at all.**
`bridge/EVIDENCE_LATENCY.md` §B.9: the Tailscale adapter is `Up` but its IPv4 is
an APIPA `169.254.83.107`, and `Get-NetRoute` shows the only route to
`192.168.53.0/24` is the on-link route on `Ethernet 2`. The owner's premise
"on the same tailnet as this laptop" is therefore not currently demonstrated on
the laptop side; it is a configuration to be established, not a fact to build on.

**The invariant-8 question, stated plainly and left open.** Invariant 8:
*Tailscale is engineering access only. It is not a data path for cell traffic.*
Both readings are defensible and they lead to different M4 architectures.

*Reading A — a Telegram command is engineering access.* A human operator
reaching into the cell to ask for something is the same category as opening TIA
Portal or SSHing in; the transport for that has always been the tailnet.
Consequences: invariant 8 is untouched, Hermes may hold the OPC UA client, and
M4 is honest provided the path carries only operator-initiated, aperiodic
commands — never cyclic process data — and never sits between the PLC and the
fleet manager, which is the case ADR 0001 names. The cost is that the cell's
ability to accept a command now depends on a remote-access overlay and a cloud
VPS in another country being reachable; the demonstration must then also show
the cell operating normally with both down (invariant 2's degraded mode).

*Reading B — a command that moves equipment is cell traffic.* The project's own
interface document classes every request/handshake node as **process data**
(`opcua-nodes.md` §1: "Every node here is process data"), and a write that
causes motion is process data by that definition. Under this reading, putting
Tailscale beneath the OPC UA write does place a VPN in a cell data path, which
is what invariant 8 exists to forbid; PLC↔fleet-manager is the named instance,
not the whole rule. Consequences: Hermes is **not** the OPC UA client. The
tailnet carries *intent* (Telegram → an authenticated local command service),
and the OPC UA write is performed by a cell-side component on the cell network.
This is also the only reading compatible with ADR 0004's own wording for M4 —
"a Hermes agent running on the **same server**" (`docs/adr/0004` line 43) —
which the surveyed deployment contradicts: Hermes is a Hetzner VPS in
Falkenstein, the PLC is on this laptop. ADR 0004 is accepted and immutable, so
that conflict is closed by a superseding ADR either way (decision 3).

I decide neither. Both are on the table with their consequences, per the brief.

## 6. Write scope

**As the node model stands today, there is no node a Hermes command path could
legitimately write.** The `DemoCell` interface carries exactly 15 nodes
(`opcua-nodes.md` §9.8):

| Group | Nodes | Client access | Why Hermes may not write it |
|---|---|---|---|
| `DemoCell/Input/` | 7 | `R/W` | Owner is the **Gazebo cell**, and §9.1 states the bridge is the only writer. A second writer breaks single ownership (invariant 10), and the values are a *field-contact image* — writing `PanelStartPressed` is impersonating the operator panel, not commanding the cell |
| `DemoCell/Output/ConveyorSpeedCommand` | 1 | `R` | Actuator output, formed in the PLC from the cycle-running flag and interlocks. Writing it is exactly what the gate criterion forbids (invariant 6) |
| `DemoCell/Status/` | 5 | `R` | PLC-derived verdicts; a client write would be a client recomputing the PLC's value (invariant 10) |
| `DemoCell/Link/` | 2 | `BridgeHeartbeat` `R/W` (bridge-owned), `BridgeLinkOk` `R` | The heartbeat means "the bridge wrote recently" and is the bridge's alone (§9.7) |

§9.8 makes it explicit that "a client-writable conveyor command node, or a
run/stop bit alongside `ConveyorSpeedCommand`" is **deliberately absent**. So M4
cannot be built by pointing Hermes at an existing node; it needs a new node
group, and the shape for it already exists in the same document: the
`Conveyor/`, `Door/` and `Charger/` `Handshake/` groups of §5-7 — a client-written
request bit plus an opaque token, answered by PLC-owned
`Ready`/`Busy`/`Done`/`Fault` and a token echo, with the PLC deciding whether and
when to act from its interlocks. Specifying that group is an interface brief, not
this survey.

**Enforcement: server-side versus policy.** Today, essentially all of it is
policy, and on the commissioned server it is weaker than the bridge's:

- On the commissioned PLCSIM, message security is `None` and CPU *access
  control is disabled*, which grants the Anonymous user full rights including
  OPC UA (`opcua-nodes.md` §9.10).
- DB visibility is at its default, so every `DemoCell` value is *also* reachable
  under `Objects/DataBlocksGlobal`, where the interface's read-only access levels
  do not apply. §9.8 records clearing the per-DB *Accessible from HMI/OPC UA*
  attribute as an **open item deferred to a later gate** — i.e. today the
  read-only levels of §9.4/§9.5/§9.7 *can* be circumvented by path.
- The only working enforcement is therefore (a) client-side — the bridge's
  `WRITE_ALLOWLIST` and `PlcClient._write` raising `WriteNotPermitted`, checked
  by `bridge/tools/check_write_allowlist.py` — and (b) the PLC program, where a
  request bit only ever acts through interlocks.

Applied to Hermes, "never writes actuator outputs" would be an assertion about a
component whose configuration is `tools.profile: "full"` with `sandbox.mode:
"off"` — an agent with arbitrary shell in its own container. A client-side
allowlist inside that container is advisory to something that can bypass it, and
the existing hooks match shell-command text, not protocol writes
(`config/openclaw/hooks/deny-patterns.txt`). The defensible options are a
server/PLC-side barrier — re-enable CPU access control with a dedicated OPC UA
user for the command client, set node access levels, clear DB visibility — or an
amr-agent-side executor that is the sole holder of OPC UA credentials and accepts
a closed verb list. Decision 7.

## 7. Layer placement

Hermes is neither the fleet manager (it assigns no orders, owns no traffic) nor
the bridge (it translates no signals and must carry no cyclic data). What it
actually is, is an **operator terminal that happens to be reachable from a
phone** — a human-interface layer above the cell.

The adjacency that invariant 11 would need:

```
operator (Telegram)
   -> Hermes  (intent: a named command, no protocol, no node ids)
      -> cell-side command client  (the only OPC UA client for commands)
         -> PLC  (OPC UA server; decides acceptance from its interlocks)
```

and the boundaries it must not cross: no adjacency to ROS 2 or Gazebo, none to
the bridge process or its state, none to MQTT/VDA 5050, none to the F-CPU or any
safety path, and no reading of PLC logic state to make its own decisions.

**This needs an ADR.** The CLAUDE.md §3 topology has exactly three subgraphs —
Fixed equipment, Fleet layer, Vehicle — and **no operator/HMI layer at all**.
There is no box for Hermes and no box for the command client, so M4 as written
adds a layer to a LOCKED diagram, which is the ADR 0005 situation twice over: a
component that cannot live inside an existing layer without weakening that
layer's boundary statement is its own layer (LESSONS 2026-07-27; `bridge/README.md`
forbids control decisions, so the command client cannot go there either). Whether
the command client is a new top-level directory (`command/`, `hmi/`) or something
else is decision 4; whether the topology gains one box or two is decision 5.

## 8. What could not be determined

1. **Whether the surveyed repository is Hermes.** Three names in one tree
   (Charlie / Rookie / Hermes) and no `hermes-*` checkout on the machine (§0).
2. **What the VPS actually runs.** This checkout is a 2026-05-04 snapshot; the
   deploy job hard-resets the VPS to `origin/main`, which was not fetched. Any
   change since — including a rename or a migration — is invisible here.
3. **OpenClaw's own behaviour.** The image is pulled from `ghcr.io`, so the
   Telegram parsing, the skill loader, the hook dispatcher, and whether any
   tool-level permission or allowlist mechanism exists could not be read.
   Polling-not-webhook is documented and structurally corroborated, not verified
   in code.
4. **Container egress to the tailnet.** The gateway sits on Docker bridge
   networks with no tailnet interface; whether it can route to `100.x` addresses
   and whether MagicDNS names resolve inside it needs a live test, not a file.
5. **The live Tailscale ACL and device list.** Only the *recommended* policy in
   `docs/TAILSCALE_SETUP.md` was available; the tailnet policy file was not read
   and no tailnet address was contacted.
6. **Whether the laptop is on the tailnet now.** The last recorded measurement
   says it was not (`bridge/EVIDENCE_LATENCY.md` §B.9, APIPA address).
7. **The `shared-internal` external network and the website stack** are defined
   outside this repository; whether a command service would join them is unknown.
8. **Whether a newer Hermes repository exists on GitHub.** Deliberately not
   checked — that is a live endpoint, which the brief forbids.

---

## Owner decisions required before M4 is briefed

1. **Confirm which repository and checkout is Hermes, and refresh it,** before
   any M4 brief cites a path — no `hermes-assistant` exists on this machine, and
   the surveyed `C:\Users\ozkan\projects\rookie-assistant` is a 2026-05-04
   snapshot calling itself Rookie (evidence: §0; `HEAD b6b178b` 2026-05-04,
   `.git/FETCH_HEAD` same date, versus
   `OneDrive\Documents\MyNotes\hermes\2026-07-17-hermes-migration-test.md`).
2. **Rule the invariant-8 question**: is a Telegram-triggered command
   *engineering access* (Hermes holds the OPC UA client, the tailnet carries the
   write) or *cell traffic* (the tailnet carries intent only, a cell-side
   executor performs the write) — both readings and their consequences are in §5
   (evidence: CLAUDE.md §2 invariant 8 versus `docs/interfaces/opcua-nodes.md`
   §1, which classes every request node as process data).
3. **Decide whether ADR 0004's M4 premise is amended by a superseding ADR or the
   deployment is changed to match it** — the ADR says "a Hermes agent running on
   the same server", while Hermes runs on a Hetzner VPS in Falkenstein and the
   PLC runs on this laptop (evidence: `docs/adr/0004-gate-reordering-plc-loop-first.md`
   line 43; `rookie-assistant/docs/VPS_CONNECTION_GUIDE.md` §1).
4. **Decide where the command-path code lives** — the evidence points to a new
   top-level amr-agent layer rather than `bridge/` or the assistant repository
   (evidence: `bridge/README.md` "This layer must not access … Any control
   decision whatsoever"; `rookie-assistant` `git ls-files` shows no application
   source, only config, scripts, CI and docs around a third-party image).
5. **Approve or refuse a new operator/HMI box and its adjacency in the §3
   topology, via an ADR on the ADR 0005 precedent** — the locked diagram has no
   operator layer, so M4 as written modifies it (evidence: CLAUDE.md §3; LESSONS
   2026-07-27 entry on `bridge/` becoming top level).
6. **Decide the M4 command node group in principle** — a new request/handshake
   group with an opaque token and PLC-owned `Ready`/`Busy`/`Done`/`Fault`, since
   no existing writable node may legitimately take a command (evidence:
   `opcua-nodes.md` §9.1 the bridge is the sole writer of `Input/`; §9.8 "a
   client-writable conveyor command node … deliberately absent"; §5-7 for the
   pattern to copy).
7. **Decide whether M4 requires server-side enforcement before the
   demonstration** — with CPU access control disabled, security `None`, and DB
   visibility making read-only levels bypassable, "never writes actuator
   outputs" would be policy only, asserted about an agent with unsandboxed shell
   (evidence: `opcua-nodes.md` §9.10 and the §9.8 open item;
   `rookie-assistant/config/openclaw/openclaw.json` `"tools": {"profile":
   "full"}`, `sandbox.mode: "off"`).
8. **Decide the authorisation model for a cell command beyond the Telegram
   allowlist** — today one user ID plus a bot token is the entire gate, and
   confirm-before-acting is prompt text rather than enforcement (evidence:
   `config/openclaw/openclaw.json` `channels.telegram.dmPolicy`/`allowFrom`;
   `config/openclaw/rookie-persona.md` §"Security Rules";
   `config/openclaw/hooks/deny-patterns.txt`, which matches shell strings only).
9. **Decide whether tailnet reachability work is in M4's scope at all** — an ACL
   rule with `src tag:server`, the laptop advertising `192.168.53.0/24`, the VPS
   run with `--accept-routes=true`, and the Windows firewall — or whether M4 is
   scoped so the OPC UA write happens cell-side and none of it is needed
   (evidence: `scripts/setup-tailscale.sh` `--accept-routes=false`;
   `docs/TAILSCALE_SETUP.md` step 7 ACL has no `src tag:server` rule;
   `bridge/EVIDENCE_LATENCY.md` §B.9, the laptop had no tailnet address).
10. **Decide whether Hermes may ever be a dependency of the demonstration or
    only a convenience over it** — i.e. whether the recorded run must show the
    cell operating normally with the VPS and the tailnet unreachable (evidence:
    `docs/roadmap.md` M4 row; CLAUDE.md §2 invariant 2, loss of network is a
    degraded mode).
