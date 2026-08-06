# m5-64 — judging the fix round (8a5f656..HEAD) before the TIA session

    brief:               issued in-session by the orchestrator (no brief file); scope = the five commits 8a5f656..HEAD
    status:              done
    invariants_touched:  none
    verdict:             pass-with-findings

## What was reviewed, and how

The five commits (m5-59 triage + procedure, m5-60 node rows, m5-61 WARN sender,
m5-62 bridge slot, m5-63 bridge-design repairs) against `docs/VALIDATION-M5.md`,
CLAUDE.md §2/§9, `docs/LESSONS.md`, and the evidence files each claim cites.
The F2 arithmetic was re-derived independently; the smoother-floor claim was
cross-read against `agv/forklift/EVIDENCE_NAV2.md`, `nav2.yaml` and
`config.yaml`; the SD5 asymmetry was argued adversarially against the consumer's
committed code (`sto_contactor.py`); evidence counts were traced to tool output
where committed; attribution and PL/Category/SIL/PFH sweeps ran
whitespace-normalised over every changed file. No run was repeated (the stack
was down and the review is read-only); where a figure could not be reproduced
it was traced to a committed log instead, and that distinction is stated per
finding.

## Verdict on the six questions, in the orchestrator's priority order

**1. Honesty of claims — PASS, with finding 2 and finding 4.**
`bridge/EVIDENCE_TORQUE_OFF_SLOT.md` is qualified where it needs to be:
double-only stated in §0 *and* §1, the positive control is same-value/same-path/
same-run (§3.1), no sentence claims motion or stillness of the vehicle, the
latency pair is labelled draws with n and load, and the boot-TRUE deafness is
declared a stage-visible property rather than buried. The positive control is
real, not decorative: phases 2 and 3 differ in the demand and nothing else.
m5-61 likewise tests silence rather than asserting it and leaves F4's
vehicle-side effect explicitly unclaimed. Two honesty gaps remain: the
harness's own console (the only place "25 checks, 25 passed" is *printed*) was
not archived (finding 2), and `docs/VALIDATION-M5.md` still publishes the two
band numbers m5-59 proved wrong (finding 4).

**2. SD5 and the asymmetry — SAFE AS IMPLEMENTED, argued not accepted.**
The load-bearing property is that the latch semantics fail safe across every
silence case: an observed `TRUE` latches and *silence cannot clear it* (release
needs an observed `FALSE` plus a fresh command — verified in
`sto_contactor.py`'s committed behaviour and exercised in phases 4–5). The
never-resolved case leaves the vehicle drivable only in states that are covered
elsewhere or already declared unclaimable: (a) bridge dead — then no envelope
enable flows either, the gate's freshness rule (E5) holds zero, and no teleop
setpoint reaches the plant at all; (b) bridge healthy but leaf absent
(four-shape) — then `TorqueOffDemand` can only be standing as a consequence of
`EStopDemand`/`ZoneStopDemand`/`SpeedMonitorDemand`, each of which kills
`#safetyDemandClear`, so `MotionEnable` is `FALSE` and the setpoint is zeroed
over the same healthy bridge; the *modelled* torque-off not arriving is exactly
the documented, unclaimed pre-AD–AF state (SD10, m5-62 §1). The asymmetry with
W1 is coherent, not merely written down: W1 is a PLC *input* failing toward
demanding; SD5 is a modelled *output reaction* that must not ride network
liveness (invariant 2), and inferring torque-off from silence would put on the
network exactly what invariant 1 keeps off it. One residual, pre-existing and
not opened by this round: bench scripts that publish the command topics
directly bypass the envelope, and with a never-resolved demand the contactor
forwards — engineering access, outside every claim, but worth remembering when
composing runs.

**3. The F2 derivation — VERIFIED, with finding 5.** Every number reproduces
independently: detection `p_in^20 ≥ 0.5` at σ = 5.47 gives z = 2.12 →
W ≥ 11.60; exclusion `(1e-9)^(1/20)` = 0.355 → z = −0.372 → W ≤ 17.97; the
read-backs at W = 15 (0.885, 1.3e-15, 3.7e-30, "1.83 σ") all check. The
"25 mm/s at every steer angle" claim is genuine, not asserted: the smoother's
from-rest floor is `v = min(a_v·dt, a_w·dt/κ)` with a_v·dt = 0.025 m/s and
a_w·dt = 0.02381 rad/s (`config.yaml` line 1203, `EVIDENCE_NAV2.md` §1501);
tread = v/cos δ, κ = tan δ/L with L = 1.05 m, so tread =
min(0.025/cos δ, 0.02381·1.05/sin δ) = min(0.025/cos δ, 0.025/sin δ) ≥ 0.025
for all δ up to the 1.31 rad stop (0.0259 there). No other autonomous regime
commands in-band sustained speed: RPP's `min_approach_linear_velocity` is
0.05 m/s and `regulated_linear_scaling_min_speed` 0.25 m/s, both above the
window at every steer angle; deceleration transits the band in one smoother
tick, far under `SHAFT_DOUBT_TIME`. The teleop sustained-creep residual is
honestly carried on §11.1b's not-covered row 1. The one fragility is finding 5:
the floor rests on the numeric coincidence a_v·dt = a_w·dt·L, and none of
those three constants is recorded as load-bearing against the F-window.

**4. The ordering constraint — SATISFIED, with finding 6.** F3's sender landed
(m5-61) before F1's conjunct lands (tomorrow), so step 8's gate answers Yes and
the 300 mm/s trap is disarmed at the code level. The procedure's own two
ordering constraints (AC before AD; AE gated on step 7) are both correct and
both now satisfiable — the m5-60 rows exist and match the procedure's requested
names character for character. The boot-deafness consequence of the committed
`bridge.yaml` safety group after AD–AF is named (m5-62 OQ2, SD6). The ordering
hazard nobody named is finding 6: the field link's keepalive is still 2 Hz
against m5-59's own window rule, and a single stale reap mid-clip now costs a
visible ~2 s slow-down in the re-recorded 1.000 m/s showcase run.

**5. Invariants — HELD.** Invariant 2 and ADR 0014/SD7 are actively enforced
(no speed, limit, margin or reading crosses the seam; one Bool does). MR1 holds
by construction (the safety group declares no inputs; four write attempts
refused independently by bridge and server, 50/50 in the committed allowlist
log). Invariant 10: `TorqueOffDemand` has one owner end to end; §7.5 B1–B7's
per-reader link verdict skirts recomputation by ruling the verdict *the
reader's own datum*, never presentable as the PLC's — a deliberate consequence
of §10.11's refusal of a second verdict node, defensible and now written down.
Invariant 1: the demand crossing the process network to a *simulated* inhibit is
the closest thing to a touch in the round; m5-60 states it plainly (SD9/SD10),
grounds it in ADR 0011 D5, and asks the owner for an ADR clarification
(§11.8 item 8) rather than authorising itself — that is the §8 discipline
working, and the open question belongs to the owner (finding 7).

**6. The procedure as the owner will run it — EXECUTABLE, with finding 3.**
One action and one observable per step throughout; both conditionals carry a
decision rule made in advance (step 19: re-init harmless, and why; step 54: the
STOP→RUN fallback with the LESSONS 2026-08-05 reason); step 60 explicitly
refuses the unreachable-branch reading; every gate is answered before the
session (step 7: rows landed; step 8: sender landed). Expected values were
cross-checked: the 46 → 48 browse-name expectation matches the committed
`m5-49-node-verify-2026-08-06.log` baseline of 46; the step 26 signature is 13
values as counted; step 24's reachability (IN `TRUE` with no field source) is
consistent with SL17's negation and the LESSONS-145 rule. The one step that can
stall the session as written is step 38 (finding 3).

## Findings, numbered

| # | Finding | Class |
|---|---|---|
| 1 | **Attribution leak in committed evidence.** `agv/forklift/evidence/m5-61-writer-session-nocycle.log` line 11 records the operator command file's full path, which runs through a `\Temp\claude\...\scratchpad\` tooling directory. Repository content must not name the tooling. A second, pre-existing instance (out of this range) sits at `hmi/tools/capture_v2b_real_screens.mjs:76`. Fix: redact the path component in the log line (it is a session artifact, not a measurement; the redaction changes no figure) and fix the `hmi/` literal with the next `hmi/` touch | **Blocking before any push or public visibility.** Not blocking for the TIA session |
| 2 | **The 25/25 harness verdict exists in no committed tool output.** `check_torque_off_slot.py` prints per-check lines and the final "25 checks, 25 passed" to its console, and that console was not archived — `bridge/evidence/` holds the bridge, double and contactor consoles and the witness CSVs, but not the harness's own. The count is therefore prose, the exact shape LESSONS 2026-07-27 (m3-21) forbids; the underlying 20/0 deliveries are reconstructable from the witness CSVs, so the claims are not doubted, only under-evidenced. Fix: archive the harness console in the live phases 1–4 run after AD–AF (which the round already owes) | Fix at the first live run; blocks any gate criterion resting on §11.2b behaviour, which m5-62/m5-63 already state twice |
| 3 | **Step 38's "exactly three hunks" is fragile as written.** `git diff --no-index` compares raw bytes; the expectation presumes TIA's copy-out round-trips the committed body byte-identically outside the three deltas. Whitespace or case normalisation by the editor, or an LF-saving editor against the CRLF working tree, produces a wall of hunks that reads as drift and stalls the session on a defect that does not exist. The stop-and-ask escape exists, but the fix is one line: the step should say that if every line differs, re-run with `--ignore-cr-at-eol -w` before concluding drift | **Worth one edit before tomorrow morning**; otherwise costs session time, not correctness |
| 4 | **`docs/VALIDATION-M5.md` still publishes the wrong band.** §3 and finding 5 say 1.4 … 30.8 mm/s; m5-59 proved the band is ≈ 2 … 50 mm/s (30.784 is `SPEED_DISCREPANCY_MAX`, a different constant; 0.0014 m/s is a rate, not a speed). m5-59 request 4 named this and nobody actioned it. The narration document now contradicts the spec that tomorrow's session implements | Fix before anyone narrates from the document; the run identity is spent tomorrow anyway, so fold into the re-validation rewrite — but annotate now so a reader tonight is not misled |
| 5 | **The 25 mm/s floor's constants are not recorded as load-bearing.** The healthy-vehicle exclusion rests on a_v·dt = a_w·dt·L (0.025 = 0.02381 × 1.05): any future change to the smoother's accel limits, its dt, or the wheelbase silently moves the floor toward the 18.0 mm/s bound. m5-59 OQ3 records only `motion_threshold_mps` as load-bearing. Fix: one row in §11.1b (or `agv/config.yaml` beside the smoother params) naming the three constants and the re-derivation trigger | Documentation, one row; not blocking |
| 6 | **The keepalive debt now sits under the strongest clip.** The field link pings at 2 Hz against `FIELD_LINK_STALE_MAX` = 1 s, failing m5-59's own window rule (needs 5 Hz); a stale reap drops `WarningFieldClear`, and after F4 the teleop vehicle visibly slows for ~2 s (SF-04 clear-hold re-earn measured 2.06 s) mid-showcase. Measured 0 reaps in 998.6 s — but on a lighter stack than the acceptance run will carry, and VALIDATION-M5 §3 measured intermittent scan stalls under the full stack on this machine. The 5 Hz brief (with its protective-path re-observation) should land **before** the 1.000 m/s re-record, not merely someday | Not blocking for TIA; sequencing constraint on the acceptance run |
| 7 | **The seam-(a) ADR clarification is still the owner's open question.** m5-60 §11.8 item 8: a modelled safety reaction is stimulated across the process network because the plant has no wire to carry it. Correctly escalated, correctly not self-authorised; it should not silently age out | Owner decision; nothing waits on it, per m5-60 |
| 8 | **TODO.md and PLAN.md contradict the report directory.** TODO's lead item still says m5-58 "BRIEF WRITTEN, dispatches next" — it ran and produced the validation document; none of m5-59..63 appears; m5-60 request 5 and m5-62 request 5 (close the F1 halves in TODO) are unactioned. PLAN's layer table still claims "Torque-off (agv/): after the demand the vehicle is deaf to commands" — precisely the claim VALIDATION-M5 §6.2 showed was untrue of the chain until m5-62, and untrue of the live CPU still. This is LESSONS 2026-07-27 (#44) recurring and a CLAUDE.md §11 obligation | **Blocking for gate advance and for drafting any narration from the tracking files.** Not blocking for the TIA session |

Clean sweeps, for the record: commit messages, author fields and branch carry no
AI/tooling attribution; every PL / Category / SIL / PFH occurrence in the range
is a negation or a PLr-target statement — no achieved-integrity claim anywhere,
including the new §11.2b, §4.12, the procedure and the SCL comments.

## What is blocking for tomorrow morning, plainly

**Nothing blocks running `plc/forklift/TIA-FIX-PROCEDURE.md` front to back as
written.** Both gates it depends on are satisfied in the committed tree. Take
finding 3's one-line fallback into the session (or just remember it at step 38).
Before the repo is pushed or shown: finding 1. Before the acceptance run that
re-records the 1.000 m/s clip: finding 6's 5 Hz brief. Before the gate
advances or a narration is drafted: findings 2, 4 and 8.

## files_changed

| File | What |
|---|---|
| `docs/reports/m5-64-fix-round-judge.md` | This report |

Nothing else was written. No process was started, no server was contacted, and
nothing was committed.

## open_questions

1. Finding 7 — the owner's ADR-clarification ruling on seam (a).
2. Whether the m5-62 four-shape probe timestamps (§0 says 20:07–20:16 UTC, §1's
   probe says 21:58Z) want a one-line note that the probe post-dates the runs —
   the claims do not depend on the order, but a hostile reader will ask.

## next_suggested

Fix finding 3's one line and finding 1's redaction tonight; run the session;
land the 5 Hz keepalive brief before the acceptance run; reconcile TODO/PLAN
against the full report directory before the verifier is asked about the gate.
