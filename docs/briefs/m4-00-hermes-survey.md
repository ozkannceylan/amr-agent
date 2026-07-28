# Brief m4-00 — Hermes survey, the definition M4 is blocked on

gate:                M4 (pre-gate definition work only; M3 is still open and M4 implementation must not start)
agent:               ad-hoc surveyor (read only, like the verifier)
goal:                the Hermes component is defined well enough that M4 can be briefed: what it is, where it runs, how Telegram reaches it, how it would reach the PLC, and what it may write
invariants_touched:  none by this survey; the survey must surface the invariant-8 question for an owner ADR decision, not answer it
inputs:              [C:\Users\ozkan\projects\hermes-assistant (external repository, READ ONLY), docs/roadmap.md M4 row, docs/interfaces/opcua-nodes.md, CLAUDE.md §2 and §3]
deliverable:         docs/reports/m4-00-hermes-survey.md
done_when:           the report answers every question below with evidence (file paths in the external repo), lists what could not be determined, and closes with the decision list the owner must rule on before M4 is briefed
forbidden:           [modifying anything in hermes-assistant, modifying anything in amr-agent except the report, copying secrets or tokens into the report (reference paths only), connecting to the VPS or Telegram or any live endpoint, deciding the invariant-8 question, writing the interface contract (that is a later interface brief)]

## What the owner has stated

Hermes is their AI assistant living on a VPS, reached via Telegram, and on
the same tailnet as this laptop. The M4 gate criterion: a Telegram-
triggered Hermes agent writes a command node over OPC UA and the commanded
action is observed in Gazebo, with Hermes never writing actuator outputs
and never bypassing PLC interlocks.

## Questions the report must answer

1. **What it is.** Language, framework, runtime layout, how it executes
   actions (tool/plugin/skill mechanism), how new capabilities are added.
2. **Telegram path.** How a Telegram message becomes an action: polling or
   webhook, which component parses it, where authorisation happens (who
   may command it, is there an allowlist).
3. **Deployment.** What runs on the VPS, how it is deployed/updated, where
   its configuration and secrets live (paths only), whether it can also
   run locally for testing.
4. **OPC UA capability.** Does anything in it already speak OPC UA or
   could a client be added cleanly; where would the amr-agent integration
   code most naturally live — in hermes-assistant, in amr-agent, or in a
   third place — and what does the repo's own structure suggest?
5. **Network reality.** From its config, how the VPS reaches the laptop
   (tailnet names/IPs — paths only, no keys), and therefore what the
   Hermes→PLC path would actually traverse. State the invariant-8 tension
   plainly: Tailscale is engineering access, not a cell data path — is a
   Telegram-triggered command "engineering access" or "cell traffic"?
   Present both readings with their consequences; decide nothing.
6. **Write scope.** Given opcua-nodes.md, which nodes could a Hermes
   command path legitimately touch (command/handshake nodes, never
   actuator outputs, never Status), and what enforcement exists server-side
   versus what must be policy.
7. **Layer placement.** Where Hermes sits in the §3 topology — it is not
   the fleet manager and not the bridge; name the adjacency it would need
   so invariant 11 (layers talk only to adjacent layers) holds, and
   whether that needs an ADR like the bridge's ADR 0005.

## Decision list format

End with a numbered list titled "Owner decisions required before M4 is
briefed", each item one sentence plus the evidence pointer.
