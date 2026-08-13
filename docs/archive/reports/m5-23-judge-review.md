# m5-23 — adversarial judge review of the M5 work

    brief:               docs/briefs/m5-23-judge-review.md
    status:              done
    files_changed:
      - docs/reports/m5-23-judge-review.md (this file; the review is read-only)
    invariants_touched:  none
    open_questions:      folded into the findings below
    next_suggested:      rewrite the eleven Claude-Session commits before any
                         push; then bisect the Nav2 route failure before any
                         further autonomy evidence is taken

Verdict: **fail** — two blocker-class findings (F1, F2), one of which (F1) is a
contract violation sitting in the local history right now. The architecture and
the claim discipline held under attack; the evidence hygiene did not.

---

## Part A — findings, ranked

### F1 — BLOCKER. Eleven commits carry `Claude-Session:` trailers, violating CLAUDE.md §7

**File/claim attacked:** the git history itself, against §7's "Never mention
Claude, AI assistance or tooling in commit messages" and the LESSONS 2026-07-26
rule that author metadata counts as attribution.

**What I found:** `git log --grep='Claude-Session'` returns **11 commits**,
2026-08-04 through 2026-08-05, from `d379cc8` (criterion (a) ruling) through
`9f4cf03` (vehicle image), every one ending
`Claude-Session: https://claude.ai/code/session_…`. That set includes the
ADR 0015 commit (`90c439b`), both m5-03b evidence commits (`626cae6`,
`a5ccb3f`), the m5-11 gate commit (`f02ece7`) and the m5-21/m5-24 commits — the
core M5 evidence trail. No remote branch contains the oldest of them, so they
are local-only and rewritable.

**Why it fails:** §7 is "not negotiable" and this is the same class the
verifier already failed the project on once (author fields, M0). The commits
that carry the gate's own evidence are the ones tainted.

**What would make it stand:** nothing — the trailers must go. Rewrite the
eleven messages (filter-branch/rebase on the two affected branches) before any
push, and add whatever hook or setting stops the trailer being appended again,
because the pattern shows it landed on every commit of two consecutive
sessions, i.e. it is mechanical, not a one-off lapse.

### F2 — BLOCKER (gate). Criterion (d) has no evidence on the showcase platform, and the one attempt on it failed — and the tracking blocker misstates which environment the committed figures came from

**Files/claims attacked:** `agv/forklift/EVIDENCE_NAV2.md` (SUCCEEDED in
13.40 s at 0.183 m), `agv/forklift/EVIDENCE_LOCALIZATION.md` (rms 0.124 m /
max 0.263 m), `docs/TODO.md` "BLOCKER-CLASS — Nav2 route regression", roadmap
M5 criterion (d).

**What I found, from the artifacts:**

1. `EVIDENCE_NAV2.md` §0 states plainly: *"These runs are container runs …
   Nothing here has been reproduced on the owner's WSL machine, and the M5
   showcase runs there."* `EVIDENCE_LOCALIZATION.md` says the same for the
   m5-08e figures. So the committed m5-10 and m5-08e figures are **container**
   evidence, produced on a 4-core headless container.
2. The TODO blocker item says the committed figures were measured "under the
   overlay" and instructs "treat every Nav2 figure in the evidence as qualified
   by the overlay it was measured under." **That is wrong for m5-10 and
   m5-08e:** the `.deb` overlay was the WSL machine's packaging (built for
   m5-11, retired by m5-21); the m5-10/m5-08e figures never touched it. The
   brief for this review inherited the same misattribution. This is LESSONS
   2026-07-31 (entry 90) recurring: an environment qualifier read from memory
   of the surrounding events, not from the evidence file's own environment
   block.
3. Consequence, judged as the brief asks: the 2026-08-05 TIMEOUT on the
   untouched m5-10 chain is therefore **not yet shown to be a regression at
   all**. There is no committed evidence that this route ever completed on the
   WSL machine, under the overlay or under system packages. The candidate
   causes are wider than the TODO states: the m5-21 stack change, **or** a
   plain container-vs-WSL platform difference — which is LESSONS 2026-07-27
   (entry 20), the exact mistake M3 already paid for: container evidence
   standing in for the demonstration platform.

**Which figures are now unqualified claims:** every m5-10 navigation outcome
(the four cases, 13.40 s, 0.183 m, the reverse divergence, the refusal) and
every m5-08e localization figure (0.124/0.263 m, the convergence and dwell
numbers) are container-only; none is known to hold where the showcase runs.
The m5-11 gate splits: the **zero-residual pass-through is a design property**
that reproduced exactly on the installed WSL stack four times (m5-21) and in
the vehicle image (m5-24) — it stands. The m5-11 **timing and distance
numbers** (0.850 s / 0.1738 m stop, 0.5176 s stale detection, the latency
figures) are n=1 draws on the retired overlay; m5-21 measured the latency
moving 60–71x across runs and five of the six observations remain un-re-run
(tracked).

**Does a gate criterion rest on one:** yes — criterion (d) ("Nav2 drives the
forklift autonomously to commanded goals") currently rests entirely on
container evidence that the only showcase-platform run contradicts. AT-02/03/04
cannot be scheduled until the failure is diagnosed. Derived values are exposed
too: `footprint_padding: 0.27` is set from the container-measured 0.263 m, and
`vehicles/F001.yaml`'s initial pose derives from the committed registration.

**What would make it stand:** a bisect brief that runs the identical goal (i)
on the WSL system-package stack with repeats, (ii) if needed, against the
retained `~/ros-overlay.retired-m5-21` and `/root/m5-21-snapshot`, and states
which of container-vs-WSL, overlay-vs-system, load, or a real defect explains
the delta — then a re-measured m5-10 case set on the platform the showcase
uses. Nothing in m5-24 was tuned, correctly; keep it that way until the cause
is named.

### F3 — Attacked and it held, with two soft spots: amended criterion (a) can fail

**File/claim attacked:** ADR 0015 D2 / the roadmap M5 row — the brief's item 5,
"can the work actually fail it?"

**The attack held.** The amended text is not a description of what m5-03b
built: m5-03b proved only the middle leg (API write → F-block instance data →
independent OPC UA witness). The criterion demands a chain that **does not
exist today** — Gazebo intrusion → field evaluation (m5-12, not started) →
automated writer (does not exist) → F-latched stop that **overrides both
modes** (requires the §14 program, the §12 nodes, the bridge group and the
vehicle gate, none on the CPU/bridge yet). The work as it stands would fail
(a) outright, which is what a live criterion looks like. The seven observables
are individually falsifiable; the m5-03b caveat ("repeats on `safe_amr` before
the gate cites it") is carried in the roadmap row's own text, in TODO and in
the ADR. Attack conceded.

**Soft spot 1 (medium):** the clause "the intrusion must originate in the
Gazebo field evaluation, not in a test script poking the DB directly" names no
instrument. An API write from the field evaluation and one from a script are
byte-identical at the CPU. Unless the gate evidence is required to record the
field evaluation's own output (scan excerpt + channel-pair transition)
time-correlated with the stand-in write, this clause is checkable only by
trusting the run's narration. m5-15/m5-12 should specify that correlated
record as the instrument.

**Soft spot 2 (medium):** `SafetyInputStandIn.ResetButtonPressed` has **no
defined stimulus** after ADR 0015. The SPEC says it is "never a client write";
watch-table *Modify* is retired; the field evaluation has no business pressing
a reset. m5-03b drove it from a test script — fine for a proof, not for the
showcase, where CLAUDE.md §9's monitored reset exists precisely to demand a
deliberate operator action. Some path (plausibly HMI request → standard
program → the same API writer, or a dedicated operator channel of the writer)
must be designed and named, or the showcase's reset step has no compliant way
to happen. ADR 0015's "what it does not decide" list covers the writer's
design but does not name this collision; m5-15 must.

### F4 — MAJOR. The m5-20 sweep list is incomplete by two locations, and one of them is the file the verdict points readers into

**File/claim attacked:** `docs/reports/m5-20-criterion-a-amendment.md`'s
twelve-location sweep, which the brief asked me to check for completeness.

**What I found by independent whitespace-normalised sweep (subject: verdict /
Modify / stand-in / SafetyInputStandIn):**

1. **`plc/forklift-safety/FIO-FEASIBILITY.md` §6** still reads, live: the
   fallback is *"driven by Modify from the watch table over the engineering
   connection. It is inert by construction. It is the path the project already
   runs."* Those are the exact claims ADR 0015 D3 superseded — and the filled
   §5/§7 verdict text says *"take the fallback of §6"*, so the document
   actively routes a reader from the verdict into the retired mechanism and
   the falsified inertness claim. Not on the m5-20 list. (m5-15's rewrite
   scope as tracked covers SPEC.md §7/F3/§4.2/§9 — not this file.)
2. **`docs/PLAN.md` contradicts itself in one file.** Wave 0 records the
   verdict as in (2026-08-04); the "Session handover, 2026-08-04" section
   below it still says FIO-FEASIBILITY's *"verdict section is blank … It
   blocks m5-15 … A NO verdict also reopens roadmap criterion (a)"*. The
   m5-20 report's files_changed claims PLAN's *"stale 'verdict is blank'
   summary corrected"* — falsified by PLAN's own text: the sweep corrected
   the Wave 0 paragraph and stopped at the file boundary of its own earlier
   hit, the precise failure LESSONS entries 76 and 92 describe.

The other ten locations on the list check out, and the twelve stale statements
are correctly tracked rather than edited. **What would make it stand:** add
both locations to the tracked residue (FIO-FEASIBILITY §6 to m5-15's scope or
its own plc touch; the PLAN handover paragraph is the orchestrator's one-line
fix now).

### F5 — Attacked and it held: the claim boundary (ADR 0011 D5)

Whitespace-normalised sweep of the whole corpus for achieved-PL phrasings
(`is claimed`, `achieves`, `meets/reaches PL`, `certified`, `PFH`, `SIL`,
every `Category 3` occurrence): every live pairing in `docs/safety/`,
`plc/`, `sim/` and the README is verbed as **target** or is an explicit
negation. The two grep-bait instances LESSONS 92 records are fixed in both
files. The scanner's vendor figures in PL-SCENARIOS are fenced as the modelled
component's data. README states the non-claim affirmatively. No finding.

### F6 — MEDIUM. The stand-in stimulus path has no diagram edge and no owner

The path the amended criterion (a) rests on — vehicle-side field evaluation
(ROS 2, WSL) → S7-PLCSIM Advanced API (Windows .NET DLL) → CPU memory — is a
cross-host, cross-layer runtime path that appears in no topology (the §3
diagram, already missing `bridge/` per the tracked contract gap, certainly
does not draw it) and in no interface document (`opcua-nodes.md` carries OPC
UA only). ADR 0015 frames it as "this project's stand-in for wiring", which is
a defensible reading of invariant 1 — but the writer crosses agv/, plc/ and
the Windows host, and no roster agent's write scope obviously owns it
(the LESSONS entry-6 pattern: work with no owner). The WSL→Windows transport
for it is undesigned. Needs: an owner ruling on the writer's home at m5-15
briefing, and the edge drawn when the bridge/ topology item lands.

### F7 — HOUSEKEEPING, several items

1. **Two briefless tasks:** m5-03b and m5-13a both ran with no file in
   `docs/briefs/` (each says so honestly). §5's shape is brief → agent →
   report; two exceptions in one week is drift worth stopping.
2. **m5-13a is invisible to the tracking files.** Neither PLAN nor TODO
   mentions it; TODO's hmi item ("capture one screenshot of the held RESET
   there and the §D residual row closes") is **stale-open** — EVIDENCE_HMI §D's
   row is struck through, closed by section H.2 on 2026-07-31.
3. **Two owed LESSONS entries from m5-21 never landed:** the `/dev/shm`
   stranding after a Fast-DDS change, and the `ros2 launch` ghost-node
   survival. (The fastcdr entry and both m5-11 entries did land; m5-24's
   include-scoping entry landed as entry 99.)
4. **Residue tracked but ageing:** `safe_amr_FIOPROBE` still undeleted while
   its evidence is load-bearing (the longer it exists, the weaker "the working
   project was never modified" gets); `Tag_1` unnamed; TIA left on the
   *Program info* tab; `EVIDENCE_NAV2.md` §7's reproduction recipe still lacks
   the `gate:=false` note (a reader following it gets a vehicle that will not
   move).
5. **TODO's "Measured numbers a later session should not re-derive" section**
   presents the container Nav2/localization figures without the qualifier its
   own blocker item (partially incorrectly, see F2) demands. After the F2
   correction, that section should say per figure which environment it binds.

---

## Part B — what must exist before HMI, PLC and vehicle run together in Gazebo

Both brief §2 facts verified against artifacts, with one correction: the
running CPU serves `ForkliftHmi`, `ForkliftInput`, `ForkliftOutput`,
`ForkliftStatus`, `ForkliftLink`, `ForkliftSafetyMirror` and **no envelope,
mode, permit or process-stop node** (m5-03b's browse of
`opc.tcp://192.168.53.1:4840`; the §14 delta is spec only, m5-16).
`bridge/config/bridge.yaml` is `groups: ["cell"]` — it carries **neither the
forklift group nor the envelope group**; the envelope gate has only ever met a
topic double (m5-11, m5-24 OQ5: "no run has exercised supervision across the
boundary"). HMI is v1: no mode selection, no process-stop control, and
`HmiProcessStopRequest`/every §12 value boots non-permissive (§12.8), so the
§14 program is inert until HMI v2a exists.

Ordered sequence. **[O]** = owner-at-the-tool, **[A]** = agent.

1. **[A] Nav2 failure diagnosis** (no brief exists). Depends on: nothing;
   blocks every autonomy step below. Observable: the m5-10 straight-route goal
   re-run with repeats on the WSL system-package stack, outcome and cause
   named (container-vs-WSL / stack / load / defect), figures re-taken on the
   platform the showcase uses.
2. **[A] m5-15 — F-program spec** (brief queued, unblocked). Rewrites
   forklift-safety SPEC §7/§2 F3/§4.2/§9 T6 **and FIO-FEASIBILITY §6 (F4)**;
   specifies the S015 validity check, the automated writer's design, rate and
   failure behaviour, the WSL→Windows transport, **and the reset-origination
   path (F3 soft spot 2)**. Depends on: ADR 0015 (done). Observable: spec
   exists with the stand-in labelled, S015 visible in the F-code listing, and
   every stimulus in §9 T6 automated.
3. **[A] m5-12 — protective/warning field evaluation** (planned, not started).
   Depends on: sensors (done, m5-04/06); independent of 1–2. Observable: a
   crate entering the protective field flips the OSSD-equivalent channel pair
   in a recorded topic echo, with R3/R8 geometry respected.
4. **[A] The stand-in writer** (exists nowhere; owner rules its home, F6).
   Depends on: 2 (design), 3 (its input). Observable: Gazebo intrusion →
   `InstF_Forklift_Safety` demand TRUE with no human act, corroborated on the
   OPC UA mirror — criterion (a)'s chain, minus the override.
5. **[O] One TIA session:** apply the m5-15 F-delta (S015, any stand-in
   growth); type the §14 standard delta (m5-16 spec); add the §12 nodes per
   the §12.11 click path; after download sweep browse names for `_1`
   collisions (LESSONS 81) and read the node set back; **repeat m5-03b on
   `safe_amr`; delete `safe_amr_FIOPROBE`**; delete/rename `Tag_1`. Depends
   on: 2 (and 4's interface being fixed). Observable: a browse shows the §12
   set; the m5-03b repeat log exists against `safe_amr`.
6. **[A] HMI v2a** (m5-14a; hard prerequisite for §14 to act — the
   non-permissive boot values). Depends on: 5 for live runs (double-first
   development possible against a §12-serving double). Observable: from the
   page, process stop cleared, autonomous mode requested, mode-in-force and
   safety lamps following the CPU.
7. **[A] Bridge extension** — forklift group repoint (deferred owner TODO
   item) plus the §12.10 envelope/mode/vehicle slot tables (`opcua-nodes.md`
   §12.13 item 1). Depends on: 5. Observable: **[O]** the deferred
   running-cell Group 1 + Group 2 capture, plus envelope topics carrying
   PLC-formed values; ADR 0014 D5.3's readback closed on both ends.
8. **[decision, O]** ADR 0016 ruling (proposed) + the allocation-table
   location + the monitoring mechanism/directory (phase 3, folds into m5-13).
   Cheap, but sequencing 9–10 depends on which shape (vehicle image vs
   compatibility chain) is the demonstrated one.
9. **[A+O] First true end-to-end run:** HMI v2a → PLC (§14) → bridge (§12
   groups) → envelope gate → Gazebo vehicle, teleop and autonomous, F-stop
   overriding both via the built chain. Depends on: 1, 4, 5, 6, 7. Observable:
   one recorded run where the gate's stop is driven by a PLC-formed envelope
   across the real bridge — the first time supervision crosses the boundary.
10. **[A] m5-13 monitoring service + HMI v2b live map** (after 8's rulings).
    Observable: the map in the HMI with the monitoring process demonstrably
    holding no publisher and no write endpoint.
11. **[O] AT-01/07/08 with sub-cases (criterion (b): standard-program-in-STOP,
    bridge stopped, session down), then the recorded showcase; [A] m5-19 gate
    verification last.** Depends on: all of the above. Observable: the roadmap
    row's criteria each with a cited artifact.

No criterion is unmeetable by what is planned, **provided** step 1 lands (else
(d) has no evidence) and step 2 resolves the reset-origination question (else
(a)'s clearance step cannot be performed compliantly).

## Part C — the honest summary

This project has demonstrated a correctly layered simulation: a real
Gazebo-to-S7-1500 signal loop with measured latency and tested signal-loss
behaviour, a teleoperated forklift whose every setpoint is formed by PLC logic
that was specified, doubled and live-debugged, F-logic executing on
API-stimulated data with two independent witnesses, and a disciplined refusal
to claim safety integrity anywhere. It has not demonstrated the M5 subject
itself: no scanner signal has ever reached the F-blocks from Gazebo, the PLC
envelope has never crossed the bridge to the vehicle, and the autonomy
evidence exists only in a container whose results the demonstration machine
currently fails to reproduce. A reviewer would press hardest on exactly that
seam — that the safety and autonomy halves are each proven in isolation but
have never run as one system — and on the process telling: the corpus's
strongest quality signal is its adversarial self-review, and its weakest is
that the same review keeps finding the same class of environment-qualifier
mistake the lessons file already codified.
