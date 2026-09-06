# M7 development plan

Companion to `m7/ARCHITECTURE.md`. Phases are small, each ends at a gate,
each gate is a test that runs without ROS (the `fleet/` invariant: no
ROS lives here). Nothing in `m6/` is edited until m6-ver2 closes; the
one `fleet_cli` registration is Phase 2b and is a one-line change held
back for that reason.

## Tree

```
m7/
  ARCHITECTURE.md  PLAN.md  README.md
  gate/        proposal.py (state machine, pure)   policy.py (pure)   policy.yaml
               audit.py (append-only JSONL)
  gateway/     server.py (MCP server; paho for the two fleet topics)
               tools.py (tool definitions + JSON schemas)
  console/     approve.py (list / approve / reject; same reader helpers as fleet_cli)
               client.py (Anthropic Messages API tool-use loop; config-driven model id)
  schemas/     submit.schema.json  proposal.schema.json  decision.schema.json  audit.schema.json
  tests/       test_proposal_fsm.py  test_policy.py  test_audit.py
               test_gateway_topics.py (G1)  test_gate_verdicts.py (G2)
               test_decision_auth.py (G3)  test_e2e_stub.py (G4)
  tools/       check_m7_boundaries.py (G1 static half)
  m7.sh        start / stop gateway + console against the m6 broker
```

Dependencies: `paho-mqtt` 2.x (already used by `m6/fleet`), `jsonschema`,
`anthropic` (console only), an MCP server library pinned in
`m7/requirements.txt`. No ROS.

## Phases

| Phase | Deliverable | Gate | Touches m6/? |
|---|---|---|---|
| 1a | `gate/` pure modules + schemas + tests | G2 (unit) | no |
| 1b | `gateway/server.py` with the four tools, paho on two topics, audit wired | G1, G2 | no |
| 2a | `console/approve.py` standalone (`python3 m7/console/approve.py list\|approve\|reject`) | G3 | no |
| 2b | register `approve` as a `fleet_cli` subcommand (one import, one `add_parser`) | G3 re-run | **yes, after m6-ver2 closes** |
| 3 | `console/client.py`, tool-use loop, `m7.sh` | G4 on the manager stub | no |
| 4 | live run on `warehouse_ver3`, audit review, `m7/PROOF.md` | G5 | no |
| 5 | SPEC.md + conformance suite from the audit schema (vault Route D) | — | no |

Phase order is fixed. Phase 3 does not start until G1–G3 are green,
because the client is the one piece that cannot be tested without
spending model calls.

## Definition of done per phase

- Tests green under `pytest m7/tests`, no ROS, no broker for 1a; a
  local mosquitto (`m6/tools/install_broker.sh`) for 1b onward.
- Every module header names which invariant binds it, as `m6/fleet`
  files do.
- Every measured number in `PROOF.md` names the file it came from.
- No PL / SIL / PFH wording anywhere; the words "safety function" appear
  only in the sentence that says M7 is not one.

## Risks named now

- MCP library churn: pin the version, wrap it in `gateway/server.py`
  only, keep `gate/` free of it so the gate survives a library swap.
- Model-call cost during Phase 3: cap with a per-session budget in the
  client config; tests use a scripted client, never a live model.
- A second operator surfaces races the single-operator CLI never hit
  (two submits for the same pallet). The policy's duplicate-key rule and
  the manager's own queue handle the known ones; unknown ones are G4
  findings, recorded, not smoothed.
