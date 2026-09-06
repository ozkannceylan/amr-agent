# HAND_OFF — M7 + M8 architecture and plan (2026-09-06, late evening TR)

Written at the owner's stop point: architecture and plan only tonight,
implementation after the Claude weekly reset (Tuesday night). Next hands:
Cursor (or a fresh Claude session). No owner questions are open; every
architecture decision is made in the four documents below.

## Branch and commits

- Branch: `m7m8/arch-plan-2026-09-06`, cut from `origin/main` at
  `667949c`. Pushed.
- Commit 1 (this one): `m7/ARCHITECTURE.md`, `m7/PLAN.md`, `m7/README.md`,
  `m8/ARCHITECTURE.md`, `m8/PLAN.md`, `m8/README.md`, `HAND_OFF.md`.
- No code. Tree is buildable because nothing executable was added.

## Read first, in this order

1. `m7/ARCHITECTURE.md` (§2 topics, §3 tool surface, §4 gate FSM, §8 gates)
2. `m7/PLAN.md` (tree, phases 1a→5, Phase 2b is the only `m6/` touch)
3. `m8/ARCHITECTURE.md` (§1 rulings R1–R5, §5 veto matrix, §7 benches)
4. `m8/PLAN.md` (tree, phases A0→F, branch base is the m5-ver3 plant)
5. Vault research these rest on: `obsidian-vault` branch
   `claude/m7-fleet-protocol-research-hnxsfo`, `projects/active/amr-agent/m7/fable/*`.

## Ownership policy (owner ruling, 2026-09-06)

1. **Heavy implementation goes to Cursor** until the Claude weekly reset.
   Reset per the banner: **Mon Sep 7, 17:00**. The earlier Tuesday
   estimate is obsolete.
2. **Escalation path for a hard blocker.** If Cursor hits a blocker it
   cannot resolve and any Fable / Claude quota remains, escalate that
   specific stuck question back to **this session**
   (`session_01DsWiT7rpWpEp7JBWFBeXym`) as **consult-only**. Not to Ozkan.
3. **After the weekly reset**, Fable may resume heavy work if needed.
4. **No mid-flight question relay to Ozkan.** Sessions decide from the
   vault, the locked rulings, and the four documents above.

Standing boundaries that remain in force under that policy:

- `m6/` and m6-ver2 belong to the separate live m6-ver2 session. M7
  Phase 2b (one `fleet_cli` subcommand registration) waits for that
  track to close.
- `m7/` and `m8/` each edit only their own tree; M8 may add the m5_ver3
  launch lines needed to start beside the vehicle stack, listed in the
  phase's EVIDENCE file.
- Safety chain files (`plc/`, `beckhoff/`, F-program, `docs/safety/`)
  are owner-only. R4: the F-PLC never receives M8 input.
- ADR 0001 invariants change only through a new owner-approved ADR.
  M7 and M8 as decided need none.
- Commits carry no AI trailer and no model identifiers.

## Exact next tasks (in order)

M7 (no ROS, runs anywhere with Python 3 + a local mosquitto):

1. `m7/requirements.txt`: paho-mqtt 2.x, jsonschema, pinned MCP server lib, anthropic (console only).
2. `m7/schemas/submit.schema.json` — copy the body shape `fleet_cli.build_submission` produces; add `proposal`, `decision`, `audit` schemas.
3. `m7/gate/proposal.py` — the FSM in `ARCHITECTURE.md` §4, pure. Tests: every transition, TTL expiry, duplicate idempotency key.
4. `m7/gate/policy.py` + `policy.yaml` — station allowlist, from≠to, per-client pending cap, per-minute cap, stale-status refusal. Tests per rule (G2).
5. `m7/gate/audit.py` — append-only JSONL, one row per transition. Test: 100 % coverage of transitions.
6. `m7/gateway/server.py` — MCP server with the four tools; paho client that subscribes to `fleet/status` and `fleet/proposal/decision`, publishes `fleet/task/submit` and retained `fleet/proposals`. Test G1: assert no `uagv` subscription, exactly two publish topics. Add `m7/tools/check_m7_boundaries.py` (static grep for `uagv/`, `rclpy`, `cmd_vel`).
7. `m7/console/approve.py` — `list | approve <id> | reject <id>`, reusing `fleet_cli`'s reader helpers by import. Test G3: decisions from any other client id are ignored and audited.
8. Then Phase 3 (client) only after G1–G3 are green.

M8 (needs the m5-ver3 plant; cut branch from the branch carrying `m5_ver3/`):

1. `m8/m8_core/contract.py` — Proposal dataclass, monotone rules, TTL. Tests.
2. `m8/m8_core/gate.py` — delta box, freshness, health flag; Phase A behaviour = refuse all, log all. Tests.
3. `m8/m8_core/vda_map.py` — Proposal/Verdict → VDA 2.1.0 `errors[]` (`m8.dockAbort`, WARNING) and `information[]` (`m8.slotState`). Check field names against `docs/interfaces/vda5050-subset.md`. Tests.
4. `m8/tests/test_no_frames_leave.py` (R3) and `test_plc_isolation.py` (R4): static checks over bridge and PLC link configs.
5. `m8/m8_nodes/pocket_pose_node.py` — classical baseline: depth-plane fit + pocket segmentation on `pallet_cam`. Publish Proposal only.
6. `m8/bench/e1_pocket.py` — score against gz pallet pose at staging; write `EVIDENCE_M8_E1.md` with the tag bar (rms 0.0706 m / 211 samples) beside it.
7. `m8/bench/faults/` + `e3_abort.py`, `e4_slot.py`, `e5_cost.py` — Phase A1 gate H1.
8. Phase B (abort live) only after H1 is written.

## Unfinished checklist

- [ ] M7 Phase 1a–1b (G1, G2)
- [ ] M7 Phase 2a (G3); 2b waits for m6-ver2 close
- [ ] M7 Phase 3–5
- [ ] M8 Phase A0–A1 (H0, H1)
- [ ] M8 Phase B–F
- [ ] Vault sync: copy `m7/` and `m8/` architecture summaries into the
      vault under `projects/active/amr-agent/{m7,m8}/` and update
      `wiki/entities/projects/amr-agent.md` with M7 and M8 rows
- [ ] Owner: confirm branch base for
      M8 implementation (`m5-ver3-close` assumed)

## Standing cautions (repeat in every derived artifact)

Ground truth is a score, not a command. No PL / SIL / PFH claims. The
collision monitor is not a safety function. The F-PLC never receives M8
input. Frames never leave the truck. M8 → M7 is VDA state only; M7 → M8
is order / instantActions only.
