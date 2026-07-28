# Report m4-00 — Hermes survey (redacted)

brief:               docs/briefs/m4-00-hermes-survey.md
status:              done — revision 3, **redacted for publication**
files_changed:       docs/reports/m4-00-hermes-survey.md (this file only; nothing in any external repository was modified)
invariants_touched:  none by this survey. It surfaces the invariant-8 question (§3) and an invariant-11 topology gap (§4) for owner decision, and decides neither
open_questions:      the ten decisions in §6; no checkout is authoritative about what the deployed system currently runs
next_suggested:      after decisions 1, 2, 3 and 6, an interface brief for the M4 command node group; no M4 implementation brief before that

---

## 0. Why this report is redacted

Revisions 1 and 2 of this survey inventoried the owner's **separate private
infrastructure** in the detail a survey brief invites: hosting provider and
region, host and tailnet node names, co-tenant services, the deployment chain,
a table of where each credential lives on the host, repository secret *names*,
which security controls had been verified and which had not, named fail-open
mechanisms, and a reachability path toward the cell network. No credential
*value* ever appeared — but the aggregate was a targeting map for a system that
is not part of this repository, and this repository is intended to be public.

The publication audit (`docs/reports/pub-01-public-readiness-audit.md`) raised
it; the owner ruled on 2026-07-28 that the operational detail is removed from
the working tree while the architectural content is kept. **The detail is not
recoverable from this file.** Earlier revisions remain in git history by the
owner's explicit decision, taken with the repository still private and
unpushed; anyone relying on this file should treat §1-§6 as the whole of what
the project needs.

What M4 needs from Hermes is not its infrastructure. It is: what kind of
component it is, what it can and cannot reach, what it may be allowed to write,
and where it sits in the topology. That is what follows.

## 1. What Hermes is, at the level M4 needs

| Aspect | Finding |
|---|---|
| Kind | A general-purpose AI assistant process, third-party framework, deployed as a container on a rented Linux VPS. This repository ships none of its source. |
| Interface to the owner | Telegram, by **long polling** — not a webhook. There is no inbound HTTP surface to the assistant, and the deployment is structurally consistent with that (loopback-only binding, default-deny firewall, no TLS termination for it). |
| Extensibility | Capabilities are added as declarative skill documents plus whatever command-line tooling the image carries. Adding a capability does not require changing the framework. |
| Autonomy | It is **not** purely reactive: it runs scheduled jobs, a periodic heartbeat, and can delegate to subagents. A command originating from it need not have a human in the loop. |
| Guardrails | Real enforcement exists and is not merely prose: a deny list of forbidden command patterns proven live, a write-confined filesystem root, environment stripping with an explicit passthrough list, and scheduled-job actions denied by default. Two gates yield rather than block when their own machinery fails — which matters for decision 9. |
| Industrial protocols | **None.** No OPC UA, no MQTT, no PLC or fieldbus client of any kind exists anywhere in it. Any such capability is new work. |
| Self-modification | The assistant can push to the repository that deploys it, and a push to the default branch *is* the deployment path. This bears directly on decision 4: amr-agent's interface contract should not live where the assistant can rewrite it unreviewed. |

## 2. What it can reach, and what it cannot

The framework's own outbound-request guard **blocks private (RFC1918) and
Tailscale CGNAT address ranges** for its web tool. So the assistant cannot
simply HTTP its way onto the cell network even where routing would allow it:
any Hermes-side path to the PLC is shaped like *a local command-line tool
invoked by the agent*, not like a web request. That constraint is independent
of how the invariant-8 question is decided, and it is the single most useful
fact this survey produced.

Tailnet reachability between the assistant's host and the cell machine was
**not** established at survey time and is not assumed anywhere here.

## 3. The invariant-8 tension, both readings

CLAUDE.md §2 invariant 8: *Tailscale is engineering access only. It is not a
data path for cell traffic.* `docs/interfaces/opcua-nodes.md` §1 classes every
request node as **process data**. A Telegram-triggered command therefore reads
two ways, and the project must choose:

- **Engineering-access reading.** Hermes holds the OPC UA client; the tailnet
  carries the write. Simplest to build. But it puts process data on the tailnet,
  which is what invariant 8 exists to prevent, and it makes an AI assistant a
  direct client of the control server.
- **Cell-traffic reading.** The tailnet carries *intent only*; a small,
  auditable cell-side executor performs the OPC UA write. Invariant 8 survives
  untouched, the assistant cannot reach the cell even if compromised, and the
  portfolio claim becomes demonstrable: *the assistant asks, it cannot act.*
  Costs one more component.

This survey decides nothing. Note only that the framework constraint in §2
already pushes the implementation toward a local-tool shape, which the second
reading formalises.

## 4. Layer placement, and why it needs an ADR

CLAUDE.md §3's topology has **no operator, HMI or assistant box at all**.
Hermes is not the fleet manager (it assigns no orders) and not the bridge (it
translates no signals), so M4 as written adds a layer to a locked diagram.
That is precedent-covered: ADR 0005 made `bridge/` top level for exactly this
reason — a component that cannot live inside an existing layer without
weakening that layer's boundary is its own layer. `bridge/` cannot host the
command client: its README forbids any control decision.

## 5. Write scope, from the node model

No existing node may legitimately take a command. `DemoCell/Input/*` has the
bridge as its sole writer, `Output/` is the actuator the PLC owns, `Status/` is
read-only by contract, and `opcua-nodes.md` §9.8 records a client-writable
command node as **deliberately absent**. M4 therefore needs a new group,
designed as a handshake rather than a poke: a request with an opaque token, and
PLC-owned `Ready`/`Busy`/`Done`/`Fault` verdicts — the pattern the station
handshake tables already use.

Enforcement caveat, on the cell side and unrelated to Hermes: the commissioned
CPU runs with access control disabled and security `None` (a deliberate
demonstration setting, `opcua-nodes.md` §9.10), and default data-block
visibility bypasses interface-level read-only marks (§9.8 open item). Until
both are addressed, "Hermes may only write the command group" is **policy, not
enforcement**.

## 6. Owner decisions required before M4 is briefed

1. **Rule the invariant-8 question** — engineering access, or intent-only with
   a cell-side executor (§3).
2. **Amend ADR 0004's M4 premise or change the deployment.** The ADR assumed
   the assistant runs on the same machine as the PLC; it does not. ADR 0007
   already moved this gate to M11, so the amendment belongs with whichever ADR
   opens it.
3. **Approve or refuse a new operator/assistant layer** in the §3 topology, by
   ADR, on the ADR 0005 precedent (§4).
4. **Decide where the command-path code lives.** The evidence points to a new
   top-level amr-agent layer, with the assistant carrying only a skill document
   and a closed verb list — because it can push to its own deployment path
   unreviewed (§1).
5. **Decide the transport shape**, given that the assistant cannot reach
   private addresses with its web tool and its working pattern for local
   services is a command-line invocation (§2): an OPC UA client inside its
   container, or an HTTP command endpoint that amr-agent owns.
6. **Decide the command node group in principle** — a new request/handshake
   group with an opaque token and PLC-owned verdicts (§5).
7. **Decide the authorisation model for a cell command.** The assistant has an
   admin tier distinct from its user allowlist; the *deny* side of that
   allowlist had not been exercised from a second identity at survey time.
   A cell command deserves an explicit, tested authorisation path.
8. **Decide whether "Telegram-triggered" excludes autonomously originated
   commands** — scheduled jobs, heartbeat and subagents mean a command need not
   have a human in the loop (§1). The M4 gate criterion uses that word.
9. **Decide whether M4 requires a barrier outside the assistant.** Its gates
   are real but two yield under their own failure, while the PLC side currently
   enforces nothing (§5). A cell-side executor with a closed verb list is the
   obvious barrier, and it is the same component decision 1's second reading
   needs.
10. **Decide whether tailnet reachability work is in scope, and whether the
    assistant may ever be a dependency of the demonstration or only a
    convenience over it.** Invariant 2 makes loss of network a degraded mode;
    a demonstration that needs the assistant to be reachable contradicts that
    posture.

## 7. Provenance and limits

Static reading only: nothing was connected to — no host, no Telegram, no
tailnet address, no live endpoint. The surveyed checkout was one week old at
survey time, and its own synced configuration snapshot already disagreed with
its deploy-managed configuration, which is the proof that **no checkout is
authoritative about what the deployed system currently runs**. Any M4 brief
must re-verify the runtime facts of §1 and §2 against the deployment at the
time it is written, not against this report.

Revision 1 additionally surveyed a predecessor repository, which the two
projects' own documentation confirms Hermes succeeds. That material added
nothing architectural and is not reproduced here.
