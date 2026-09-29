# Integration and continuation plan — 2026-09-29

Written from a review of every remote branch as of 2026-09-29. It does
two things: it records **what each line of work planned and how far it
got**, with the numbers taken from the branches themselves; and it fixes
**the order in which the work continues**. Alternatives that were
weighed and not taken are kept in §3 so the choice can be reversed with
the evidence in hand.

Standing cautions, repeated because every derived artifact must carry
them: ground truth is a score, not a command. No PL / SIL / PFH claims.
The collision monitor is not a safety function. The F-PLC never receives
M8 input. Frames never leave the truck. Commits carry no AI trailer and
no model identifiers.

---

## 1. Where the repository stands

### 1.1 `main` — `667949c`, 2026-08-28

M0–M6 shipped. The last three commits on `main` are the CI gate
(ADR 0017: `.github/workflows/ci.yml`, `m6/ipc/ros_optional.py`,
`m6/tools/check_layer_boundaries.py`, PR template, CODEOWNERS) and the
README infographic. **Nothing measured after 2026-08-28 is on `main`.**
The README's milestone table reads M7 = "LLM operations layer" ⏳ and
M8 = "Beckhoff/TwinCAT vendor portability" ⏳.

Verified here, native, no ROS: `python3 -m pytest m6/tests
--ignore=m6/tests/test_vda_agent_mqtt.py` → **560 passed, 9 skipped**;
`check_layer_boundaries.py` exits 0.

### 1.2 The three live lines

All three were cut from `b90eec9` (the commit before the CI gate), so
each is **3 commits behind `main`** and none carries `.github/`,
`ros_optional.py` or the boundary checker. Each was trial-merged with
`main` here: the merge is clean for all three, and the `m6` suite on
`m5-ver3-close` + `main` is the same **560 passed**.

| Line | Tip | Ahead of `main` | What it is | Gate state |
|---|---|---|---|---|
| **A** `m5-ver3-close` | `d4f2cdc` 2026-09-18 | 142 | m5-ver3 showcase vehicle (AMR-DEC-003) **plus** M8 propose→veto (`m8/`). Integration target of PRs #9, #11, #12, #13 | m5-ver3 F1–F5 + G5 closed; M8 A0 closed (H0), A1 offline closed, **H1 open**, Phase B **HOLD** |
| **B** `m7m8/arch-plan-2026-09-06` | `2255ec1` 2026-09-11 | 12 | M7 gated fleet console (`m7/`), the M7/M8 architecture, `HAND_OFF.md`, the `m8.dockAbort` / `m8.slotState` subset amendment (PRs #8, #10) | Phases 1a–3 closed (G1–G4); **Phase 4 (live, G5) and 5 not started** |
| **C** `m6-ver2` | `b20003a` 2026-09-02 | 134 (115 shared with A) | Nav2 adapter replaces `m6/ipc/nav_node`+`nav_core`+`follower` under the unchanged fleet layer (AMR-DEC-006, `m6_ver2/`) | G0, G1 closed; G2/G2b closed; **the 1–4 truck ladder is measured and 4 trucks do not drive** |

#### Line A — what was planned, what landed

**m5-ver3** (`tasks/TODO.md` § m5-ver3, `m5_ver3/EVIDENCE_*.md`): real
instrument profiles (TiM571, nanoScan3, D455, OS0 fitted not bridged),
wheel odometry + EKF (F2), the frozen map (F3), Nav2 for a tricycle
(F4), the S5 dock and pallet cycle (F5), the stall/creep root cause (G5).
Every phase has an EVIDENCE file and a closed ledger row. Verified here:
`pytest m5_ver3/tests` → **1216 passed, 2 skipped**. For one truck this
track is **complete**; whether it rejoins the fleet was never assumed
(`m5_ver3/CONTEXT.md`) — that question is what line C answers.

**M8** (`m8/PLAN.md`, seven EVIDENCE files, 220 tests):

| Phase | Planned | Landed |
|---|---|---|
| A0 | `m8_core` + `Proposal.msg` + `vda_map`, no ROS | ✅ H0, 2026-09-06 |
| A1 offline | shadow nodes, launch, synthetic tests | ✅ 79 tests, 2026-09-06 — and the suite was green while the plant failed, because no fixture had a floor (`tasks/LESSONS.md` 2026-09-11) |
| A1 plant E1 | pocket pose vs tag bar rms 0.0706 m | ✅ **bar met** 2026-09-12: staging 30/30 at 0.0564 m; 1.0 m refused by design (own forks continuous with the pallet) |
| A1 plant E3 | false-abort < 0.10 live | ✅ **both bars met** 2026-09-18, paired on one bringup: unwired 0.319 → **0.061**, wired 0.124 → **0.098**. The wired margin is **one frame wide** (13/132; 14 would be 0.106) |
| A1 plant E4, E5 | slot state; RTF cost | ❌ **NOT_RUN** |
| H1 | E1, E3, E5 written | **open** — has numbers, not a pass, because E4/E5 are unrun |
| B | gate accepts `DOCK_ABORT` only | **HOLD** by the evidence's own words: "two sessions of four docks are not a number a gate opens on" |
| C–F | refine, slot table to fleet, speed arbiter, learned candidate | not started |

Open by name (`EVIDENCE_M8_E3_FLOOR.md` § Open): (1) `pallet_rotated`
is a relative angle and is 7 of the 8 remaining unwired false aborts —
needs a vehicle pose C2 takes by design; (2) the wired margin;
(3) countable checks position not yaw; (4) `blocked_by_box` word, tag
residual 0.0325 m, `pallet_shifted` threshold; (5) **the rig dropped gz
services four times** (`set_pose`, `create`) — a rig fault the bench
works around in halves; (6) E4/E5; (7) Phase B.

#### Line B — what was planned, what landed

`m7/PLAN.md` phases 1a → 5. Verified here: `pytest m7/tests` →
**77 passed**; `check_m7_boundaries.py` passes (10 modules, no `uagv/`,
`rclpy`, `cmd_vel`).

| Phase | Planned | Landed |
|---|---|---|
| 1a | gate FSM, policy, audit, schemas | ✅ G2 |
| 1b | MCP gateway, two publish topics, audit wired | ✅ G1 |
| 2a | `console/approve.py` standalone | ✅ G3 |
| 2b | `approve` registered on `fleet_cli` — "after m6-ver2 closes" | ✅ done 2026-09-11 (one import, one `add_parser` in `m6/fleet/fleet_cli.py`); the hold was lifted in practice |
| 3 | tool-use client, `m7.sh`, scripted model | ✅ G4 on the manager stub |
| 4 | live run on `warehouse_ver3`, audit review, `m7/PROOF.md` | ❌ **G5 not run** |
| 5 | SPEC.md + conformance suite from the audit schema | ❌ not started |

`HAND_OFF.md` unfinished list still true: vault sync of `m7/` and `m8/`
summaries; owner confirmation of the M8 branch base (it was
`m5-ver3-close` in practice).

#### Line C — what was planned, what landed

AMR-DEC-006: the m5v3 stack in `/fN` namespaces, one `/tf`, one `map`;
the adapter presents the byte-identical `/auto` contract; fleet layer
untouched. G1 bar: two consecutive clean fleet-DONE orders S1→S4 on one
truck, zero BLOCKED, zero cusps in 45 471 commands, Motor-False edges 0;
suite 571. G2/G2b: the liveness predicate fixed and **the ladder
measured** (`b20003a`):

| trucks | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| RTF driving, mean | 0.839 | 0.735 | 0.408 | 0.252 |
| safety scan Hz (nominal 10) | – | 7.02 | 3.93 | 2.42 |
| STALE-fault rows | – | 0 | 3 | 836 |
| Motor-False edges | 0 | 2 | 1 | 7 (5 starvation) |

At four trucks nothing drove. Delivered scan rate is nominal × RTF to
three digits at every rung. Open (`EVIDENCE_G1.md` §6): four trucks not
viable on this rig, `gz_server` 158–190 % of a core, adapter ~50 % per
truck; annex bays never driven; F-PLC still `--virtual`; deploy
discipline deferred; dead nav modules' tests still in `m6/`.

### 1.3 Everything else

| Branch | State | Action |
|---|---|---|
| `cursor/ci-cd-akisi-canvas-74d8` | PR #7 **open draft** since 08-28, 1 doc commit (Turkish CI walkthrough) | owner: land or close |
| `m8/c1c2-plane-roi-fix`, `m8/c2-words-and-selfmask`, `m8/c2-steps-3-4-unwired` | merged into A via #11, #12, #13 | delete after A lands |
| `cursor/m8-phase-a0-d3a5`, `m8/h1-e1-e3-2026-09-11` | ancestors of A | delete |
| `cursor/m7-phase-1a-1b-cd70`, `cursor/vda-m8-subset-753f` | ancestors of B | delete |
| `m5-ver3`, `cursor/m5ver3`, `cursor/cloud-agent-*` | ancestors of A and C | delete |
| `cursor/plan-cicd-integration-74d8` | merged as #5 | delete |
| `m6` | 4 behind `main`, 0 ahead | delete |

### 1.4 Two disagreements the tree carries today

1. **The README's M8 is not the tree's `m8/`.** README row M8 =
   Beckhoff/TwinCAT portability; `m8/ARCHITECTURE.md` = per-vehicle
   propose→veto intelligence. The Beckhoff work already lives on `main`
   under `beckhoff/` (runbook, TE9000 spec, ST stand-in, pyads writer)
   and is blocked on the TE9100 runtime being a product announcement.
   Resolution in §4.1: the propose→veto track **is** M8 (that is what the
   architecture, plan, evidence and PRs #9–#13 all call it); the
   Beckhoff row becomes **M9 — vendor portability**, status "substrate
   in tree, runtime pending".
2. **The M7 Phase 2b hold.** `HAND_OFF.md` said 2b waits for m6-ver2 to
   close; PR #8 did it anyway. `m6-ver2` never edits `m6/fleet/`, so
   there is no conflict in bytes (verified: the two lines overlap only
   on `.gitignore`, `HAND_OFF.md`, `m8/{ARCHITECTURE,PLAN,README}.md`).
   The plan records the fact instead of pretending the hold held.

---

## 2. The decision

**Land what is measured, then continue on the plant.** Three months of
evidence sit on three branches that no CI gate has ever run. The only
work that can be done without the rig — integration, CI coverage of the
new pure-Python suites, the M7 conformance spec, the docs that make the
tree tell the truth — is also the work that de-risks everything after
it. The rig-bound work (M8 E4/E5 and open item 1, M7 G5, m6-ver2 G3) is
ordered behind it and is the owner's, because only the owner has the
rig.

---

## 3. Options weighed

| # | Option | Needs the rig? | For | Against | Verdict |
|---|---|---|---|---|---|
| 1 | **Integrate A + B + C into `main`** behind the existing CI, extend CI to `m5_ver3/`, `m7/`, `m8/` tests | no | 1 513 tests (1216 + 77 + 220) join a gate; one tree instead of three; `main` stops describing a system a month behind; all three merges are clean or docs-only conflicts | CODEOWNERS review is the owner's; the README rewrite is a judgement the owner may edit | **taken — Phase 1** |
| 2 | M8 continue: open item 1 (relative yaw), E4, E5, then the Phase B decision | **yes** | it is the next thing the evidence itself names; H1 cannot close without E4/E5 | cannot be run from a cloud VM; the rig's gz service drops (4×) are unfixed | **taken — Phase 3, owner-executed** |
| 3 | M7 Phase 4 live run → `m7/PROOF.md` (G5) | **yes** + model budget | the only unmeasured M7 phase | needs the M6 cell up and a per-session budget; G4 already covers the logic on a stub | **Phase 3, after M8 E4/E5** |
| 3b | M7 Phase 5 — SPEC.md + conformance suite from `audit.schema.json` | no | pure docs/tests; makes the audit contract portable | zero user-visible motion | **taken — Phase 2** |
| 4 | m6-ver2 G3 — make 3–4 trucks drive on the Nav2 adapter | **yes** | it is the open claim of AMR-DEC-006 | the ladder says the cost is `gz_server`, not the adapter; the fix is rate/sensor budget or a different rig, i.e. a decision, not a patch | **deferred; decision item for the owner (§5)** |
| 5 | Hygiene only: delete branches, close #7, fix the M8 label | no | cheap | does nothing about the unmerged evidence | **folded into Phase 1** |
| 6 | Start Phase B (abort live) now | yes | it is the next M8 phase in the table | the evidence file says HOLD twice and the wired margin is one frame; opening a gate on that would be closing a phase by narrowing the claim | **refused** |

---

## 4. Phases

Phase order is fixed. Every phase ends at a check that can be run
without the rig, or says in its own EVIDENCE file that it could not.

### Phase 1 — integration (no rig)

Branch: `cursor/integrate-m5v3-m7-m8-73d0`, cut from `origin/main`.

| Step | Do | Check |
|---|---|---|
| 1.1 | `git merge origin/m5-ver3-close` (clean, verified) | `pytest m6/tests` ≥ 560 passed; `pytest m5_ver3/tests` 1216 passed; `pytest m8/tests` 220 passed; `check_layer_boundaries.py` 0 |
| 1.2 | `git merge origin/m7m8/arch-plan-2026-09-06` — conflicts **only** in `m8/PLAN.md` and `m8/README.md` (add/add): take the `m5-ver3-close` versions, they are the newer supersets. `HAND_OFF.md` and `.gitignore` auto-merge | `pytest m7/tests` 77 passed; `check_m7_boundaries.py` 0; `fleet_cli.py approve --help` runs |
| 1.3 | `git merge origin/m6-ver2` — conflict **only** in `tasks/TODO.md`: keep both sections in date order (the file is a ledger; nothing is dropped) | `pytest m6_ver2/tests` at its own count (571 at `8aa03a4`); `m6` and `m5_ver3` counts unchanged |
| 1.4 | Extend `.github/workflows/ci.yml`: add `pytest m5_ver3/tests`, `pytest m7/tests`, `pytest m8/tests` and `m7/tools/check_m7_boundaries.py` to the **native** job (none needs ROS or a broker); `m7/requirements.txt` installed for the m7 tests only. Floors written into the PR template: m6 550, m5_ver3 1200, m7 75, m8 215 | the four jobs green on the PR |
| 1.5 | Add a static R3/R4 check to the `invariants` job: `pytest m8/tests/test_no_frames_leave.py m8/tests/test_plc_isolation.py` | green |
| 1.6 | Docs, in `main`'s own prose: README milestone table (M7 "phases 1–3 in tree, G5 pending", M8 = propose→veto with the E1/E3 numbers and "Phase B HOLD", **M9** = Beckhoff/TwinCAT "substrate in tree, TE9100 pending"); "How the repo is laid out" gains `m5_ver3/`, `m6_ver2/`, `m7/`, `m8/`; `RUNBOOK.md` gains one pointer each to `m5_ver3/RUNBOOK.md`, `m6_ver2/m6v2.sh`, `m7.sh`, `m8/README.md`; `docs/README.md` lists `docs/reports/`; `HAND_OFF.md` gets a dated closing note pointing here | links resolve (`git grep -n "](m[5-8]"` paths exist) |
| 1.7 | One PR to `main`, title in the repo's style, body from the template, every count pasted | CODEOWNERS review; merge is the owner's |
| 1.8 | After merge: delete the branches in §1.3 marked delete; owner decides PR #7 | `git branch -r` shows `main` + live lines only |

**Done-when:** `main` carries `m5_ver3/`, `m6_ver2/`, `m7/`, `m8/`;
CI runs 1 500+ tests natively; the README milestone table matches the
tree; no branch is more than one PR away from `main`.

**Risk named now:** merging C after A changes `tasks/TODO.md` and nothing
else that A touched — but C's `m6_ver2/tests` were last run against C's
own `m5_ver3/`, which is 27 commits older than A's. Step 1.3's check is
the m6_ver2 suite on the merged tree; a red there is a finding for the
PR body, not something to fix by pinning the older `m5_ver3/`.

### Phase 2 — M7 Phase 5, the conformance spec (no rig)

Branch cut from `main` after Phase 1 lands.

| Step | Do | Check |
|---|---|---|
| 2.1 | `m7/SPEC.md`: the four MCP tools, the two topics, the proposal FSM, the decision authority rule (G3), the audit row — written from `m7/schemas/*.json` and `ARCHITECTURE.md` §2–§4, not from memory | every field in SPEC names its schema file |
| 2.2 | `m7/tests/test_conformance.py`: run the G4 stub (`test_e2e_stub.py`'s scripted client) to produce an audit JSONL, then score that log against `audit.schema.json` and the FSM **without the gateway**; a second scripted client violates each policy rule once and is refused once. `m7/audit/` holds only `.gitkeep` today — the fixture is generated, not committed | 100 % of FSM transitions and policy rules exercised, counted |
| 2.3 | `m7/PLAN.md` Phase 5 row → closed; Phase 4 row → "G5 pending rig" with the exact commands in `m7/README.md` | `pytest m7/tests` count written in the PR |

**Done-when:** an audit log from any future live run can be scored
without the gateway running.

### Phase 3 — the plant (rig; owner-executed, agent-prepared)

Order inside the phase is the order the evidence argues for.

| Step | Do | Check / evidence |
|---|---|---|
| 3.1 | **M8 open item 1**: C2 takes the vehicle pose (odometry/AMCL, the pose it already publishes) and reports pallet yaw in the **map** frame, so a turning truck stops reading as a rotated pallet. Offline first: the renderer fixture gains a moving camera; test pins "relative yaw ≠ pallet yaw" | `pytest m8/tests` green; then **paired** live sessions on one bringup vs `d4f2cdc`, bar population stated as a population |
| 3.2 | **M8 E4** (`e4_slot.py`): slot state on the three staged poses, reason-exact counts | `EVIDENCE_M8_E4.md` with numbers, or NOT_RUN with the reason |
| 3.3 | **M8 E5** (`e5_cost.py`): RTF with and without the shadow nodes, same bringup, mean and integrated | `EVIDENCE_M8_E5.md`; `classify` median/max already read 0.109 / 0.237 s and are not an RTF claim |
| 3.4 | **H1 decision**: with E1, E3, E4, E5 written, H1 either closes or stays open with the cause named. **Phase B opens only if** the unwired live false-abort is < 0.10 on ≥ 3 bringups and the wired margin is more than one frame | `m8/PLAN.md` row A1 → closed or the reason |
| 3.5 | **Rig fault, open item 5**: before 3.1, reproduce the gz service drop with `m8/bench/plant.py probe` looping over a bringup; record the count; if it reproduces, an `m5v3.sh` preflight refusal for a dead `set_pose`/`create` service (the bench already refuses to count what it cannot join) | count in the EVIDENCE file of whichever bench hit it first |
| 3.6 | **M7 G5**: `./m7.sh start` against the M6 cell, one operator session with a capped budget, audit reviewed line by line | `m7/PROOF.md`, every number naming its file |

**Done-when:** H1 has a verdict; Phase B is open or HOLD with a
three-bringup number behind it; M7 has a PROOF.

### Phase 4 — m6-ver2 scaling decision (rig; owner decision first)

Not a build phase until §5 item 2 is decided. Whichever way it goes, the
first step is the same instrument: the ladder re-run with `gz_server`
CPU attributed per sensor topic, because the adapter is ~50 % of a core
per truck and `gz_server` is 158–190 % **on one truck** — the cost that
does not scale is the plant's, not the adapter's.

---

## 5. Decisions the owner holds

1. **M8 / M9 naming** (§1.4). The plan assumes the tree's naming wins and
   Beckhoff becomes M9. Reversing it is a README edit.
2. **m6-ver2's four-truck claim.** Either (a) the Nav2 adapter is the
   per-vehicle engine for ≤ 2 trucks on this rig and M6's four-truck
   cell stays on the old nav as the fleet demonstration; or (b) the
   sensor budget per truck is cut (rates, headless, OS0 unfitted) until
   four drive; or (c) a second machine hosts the plant. This is a
   decision about what the repo claims, not a patch.
3. **PR #7** (Turkish CI walkthrough): land, rewrite, or close.
4. **Branch base for M8 Phase 3** (the last open item of `HAND_OFF.md`):
   `main` after Phase 1, so that `m8/` work is one PR from `main` again.
5. **Vault sync** (`HAND_OFF.md`): outside this repo; not planned here.

---

## 6. Order and dependencies

```
Phase 1 (integrate)  ──►  Phase 2 (M7 SPEC)   [no rig, agent]
        │
        └──►  Phase 3.5 → 3.1 → 3.2 → 3.3 → 3.4 → 3.6   [rig, owner]
                                                  │
                          §5.2 decision  ──►  Phase 4  [rig]
```

Phase 2 and Phase 3 are independent once Phase 1 has landed. Nothing in
this plan opens M8 Phase B, changes an ADR 0001 invariant, or touches
`plc/`, `beckhoff/`, the F-program or `docs/safety/`.
