# Report m5-judge — adversarial architecture review of the M5 decisions (ADR 0011 D1–D5)

```
brief:               adversarial review of the M5 architecture (ADR 0011, ADR 0010,
                     CLAUDE.md §2/§3/§9, roadmap row M5, and the landed
                     implementation), commissioned 2026-07-31
status:              done
files_changed:       [docs/reports/m5-judge-architecture-review.md]
invariants_touched:  none — read-only review; findings 3 and 4 name invariant
                     tensions that need owner rulings, not edits made here
open_questions:      none of mine; the findings ARE the open questions
next_suggested:      rule finding 1 (fallback vs criterion (a)) before m5-03 runs,
                     because its answer changes what a "no" verdict costs
```

**Method note.** No `code-review` skill exists in this session's skill roster
(the available `review` skill targets GitHub PRs and `security-review` targets
pending branch changes; neither covers this task). Per the brief's instruction
not to guess at names, this review was conducted with my own discipline: every
D1–D5 decision was attacked along the commissioned lines plus lines of my own,
against the committed tree at `b8713ff` (plus the two in-flight m5-04b working
edits in `agv/`, read but not judged as committed state). Nothing outside this
file was written.

**Reading rule for this report.** Each finding names the claim attacked, the
concrete failure scenario, the carrying file and line, the verdict
(wrong / undocumented / survives), and the change I would make. Findings are
ranked most severe first. Where a decision survives, the attack that failed is
shown, not just the verdict.

---

## Finding 1 — SEVERE. D2's "inert" fallback cannot satisfy the M5 gate criterion (a) as written, and no document says which one yields

**The claim attacked.** ADR 0011 D2: *"The fallback is inert by construction. It
is the path the project already runs; taking it requires building nothing and
removing nothing"* (`docs/adr/0011-sensored-autonomy-architecture.md:148-149`),
inside an ADR whose preamble says it *"settles the architecture inside M5
without changing the gate's criteria"* (`docs/roadmap.md:33-35`).

**The attack.** The fallback is inert with respect to the **build**. It is fatal
with respect to the **gate**. Roadmap row M5, criterion (a)
(`docs/roadmap.md:74`): *"a safety laser scanner is added to the model and its
signals reach the F-CPU safety program's F-blocks, a protective-field intrusion
tripping an F-latched stop."* The named fallback is the standard-DB stand-in
*"driven by Modify from the watch table over the engineering connection"*
(`plc/forklift-safety/FIO-FEASIBILITY.md:502-504`, `plc/forklift-safety/SPEC.md`
§7). Under the fallback, the scanner's signals do **not** reach the F-blocks —
an operator watches the Gazebo intrusion and plays the device by hand at a watch
table. That is exactly the demonstration SPEC.md §2.1 already calls
disqualifying in another context: *"the operator at the engineering interface
played the device, and the safety program did this with it"*
(`plc/forklift-safety/SPEC.md:190-193`). It is also, with labels, the very
demonstration the same ADR's Alternatives section rejected as primary: *"safety
logic reading unsafe data while claiming realism"*
(`docs/adr/0011-sensored-autonomy-architecture.md:357-360`).

**The concrete failure scenario.** m5-03 runs; step 3 finds the F-DI passivated
(the outcome `SPEC.md` §2.1 predicts and `FIO-FEASIBILITY.md:340` names as the
abort). The fallback is taken, correctly, per the procedure. Wave C and E work
proceeds. At m5-19 the verifier reads criterion (a) against the build and must
fail the gate: no scanner signal reaches any F-block, and CLAUDE.md §10 forbids
redefining the criterion. The project then discovers, at gate verification, a
contradiction that was decidable on 2026-07-30. Alternatively — the worse
branch — the showcase is recorded with wording that lets the watch-table
stimulus read as the scanner path, which is the exact laundering D2's labelling
burden exists to prevent.

**What is genuinely wrong versus undocumented.** The fallback's existence is
right and well-engineered (the m5-03 copy rule is genuinely good work). What is
wrong is the sentence "without changing the gate's criteria" standing beside a
named fallback that cannot meet criterion (a). Nobody has written the sentence
CLAUDE.md §10 requires: *if the F-I/O probe answers no, criterion (a) cannot be
met as written*.

**What I would change.** One paragraph, owner-ruled, before m5-03 executes:
either (i) criterion (a) is formally weakened for the fallback case by an ADR
(a criterion change, honestly made), or (ii) the fallback is upgraded — the
PLCSIM Advanced API writing `SafetyInputStandIn` **standard** tags by name
would keep the Gazebo-to-F-program automation while keeping the S015/stand-in
labelling, and TWIN-DEMO-MAP R2's "engineering interface" wording plausibly
admits it — but that is a design change someone must rule, not a reading anyone
may assume. Today the documents define the fallback as manual, full stop.

---

## Finding 2 — SEVERE. Three committed contracts already state D2's UNPROVEN primary path as settled fact

**The claim attacked.** The brief's own suspicion, confirmed. ADR 0011 D2 is
explicitly conditional — *"the first M5 brief settles in the tool"*
(`docs/adr/0011:130-137`), F4 records the V6.0+ support list as unverified —
and `docs/roadmap.md:38-41` carries the conditional faithfully
("conditional on this tool's safety system version supporting F-I/O
simulation"). But:

- `agv/forklift/model.sdf:100-101`: *"The safe channel reaches the F-program
  through the PLCSIM Advanced API (ADR 0011 decision 2), never through a
  topic."* Indicative mood, no condition, in the file that declares itself THE
  AUTHORITY.
- `agv/forklift/README.md:87` (channel table): the safe channel is *"delivered
  to the F-program through the PLCSIM Advanced API … this project's analogue of
  the copper an OSSD pair runs on."* No condition.
- `docs/PLAN.md:21-23`: *"the scanner reaches the F-program through configured
  F-DI stimulated by the PLCSIM Advanced API — the simulation's wiring, never
  the process network."* The conditional survives only in wave-0 item 3, twelve
  lines away; the architecture summary a reader actually quotes has lost it.
- `agv/forklift/EVIDENCE_SENSOR_COVERAGE.md:531-533` (§10c): *"the simulation
  analogue of that path is the PLCSIM Advanced API into the F-program"* —
  stated as the reason the scanners are not bridged, no condition.

**Why this matters concretely.** If m5-03 answers no, four documents in three
directories must be corrected in the same breath as the fallback is taken —
and the fallback procedure's own consequence list (`FIO-FEASIBILITY.md`
§6) names none of them. A fallback whose adoption leaves the model file, the
vehicle README, the plan and the coverage evidence all asserting the dead path
is not "requires building nothing and removing nothing." The laundering the
brief asked about is not hypothetical; it has already happened by repetition,
exactly the mechanism the m5-02 report warned about for the monitoring
directory (*"the recommendation will harden into a decision by repetition"*,
`docs/reports/m5-02-topology-monitoring-plane.md:104-107`).

**Also under this heading: the "vehicle waves don't depend on the verdict"
claim is overdrawn.** `FIO-FEASIBILITY.md:11-16` says the vehicle-side waves
proceed regardless *"because none of them depends on which side of the CPU
boundary the scanner signal enters."* False for m5-12: its deliverable is
*"output shaped as OSSD-equivalent channel pairs"* (`docs/PLAN.md:73-74`) —
pair-shaped precisely for a 1oo2 F-DI that exists only on the primary path.
Under the fallback there are three single Bools and a watch table; m5-12's
delivery half has no consumer. The evaluation logic survives either verdict;
its output contract does not.

**Wrong versus undocumented.** The wording pattern is wrong (fact-mood
statements of an unproven path); the m5-12 dependency is undocumented.

**What I would change.** A one-line conditional marker ("primary path per ADR
0011 D2, pending m5-03") in the four locations named, added now while the edit
is cheap; and the m5-12 brief written with two output shapes, or issued after
the verdict.

---

## Finding 3 — MAJOR. D1's independence claim breaks at the execution level, and its scaling claim rests on facts the ADR's own evidence table never pinned

**The claim attacked.** D1: the F-runtime group is the vehicle's **onboard**
safety controller; *"It scales. At M6 four forklifts each carry their own
safety instance… The simulation's single 1513F-1 hosting that instance is a
simulation artifact and is disclosed as one wherever the twin is described"*
(`docs/adr/0011:92-95`).

**Attack (a): the disclosure duty is already unmet.** `docs/roadmap.md:35-37`
states *"the forklift's F-runtime group is the vehicle's own onboard safety
controller, so the scanner-to-stop chain is internal to the vehicle"* — no
artifact sentence. `docs/PLAN.md:18-19` likewise. The two tracking files that
restate D1 most often are the two that dropped its disclosure. "Wherever the
twin is described" is a strong promise and it failed within its own round.

**Attack (b): shared-CPU execution contradicts B4's substance.** The declared
onboard controller executes on the same CPU as the fixed cell's standard and
safety programs (`plc/forklift-safety/SPEC.md:40-41`). B4 — landing at M7,
per roadmap:76 and :98 — requires *"the vehicle chain does not depend on the
cell."* In this simulation a cell CPU STOP, a download, or an F-runtime-group
fault kills the vehicle's "onboard" safety controller together with the cell.
The demonstrable half of B4 (an e-stop *demand* on one chain not propagating to
the other) can still be shown; the dependence half is false at the execution
level and will stay false for as long as one CPU hosts both. That is a
simulation artifact — but B4 is a **gate criterion**, and nothing in ADR 0011,
the roadmap or the SRS boundary statements records that B4 will be demonstrated
on an execution substrate that violates it. A reviewer watching the M7 run is
owed that sentence in advance, not in the Q&A.

**Attack (c): the M6 scaling facts are unpinned.** ADR 0011's evidence table
pins twelve external facts, F1–F12, to the manual editions they came from —
admirable discipline — and pins **neither** of the two facts its scaling claim
needs: the maximum number of F-runtime groups one F-CPU hosts (SIMATIC Safety
bounds this per CPU family; if the bound is two, four per-vehicle groups on the
shared 1513F-1 are impossible and the four "instances" collapse to F-FB
instances inside one group — one monitoring time, one collective signature,
one common fault container, which is not "what the physical world does"), and
the PLCSIM Advanced instance budget if the honest answer is instead four
simulated CPUs. By the ADR's own LESSONS rule (a vendor claim without a pinned
reference ages silently), "it scales" is currently an unpinned vendor-adjacent
claim in the one document built to forbid those.

**Verdict.** D1's architectural reading itself **survives** — the onboard
interpretation is the correct real-world architecture, the wireless-PROFIsafe
rejection is sound, and the ADR is honest that the reading is a declaration.
What fails is the perimeter: the disclosure has already leaked, B4's collision
is unrecorded, and the scaling claim is asserted where every neighbouring claim
is pinned. All three are documentation failures, curable now; attack (b)
becomes a real failure the day the M7 brief is written without it.

**What I would change.** Add the artifact sentence to roadmap:35 and PLAN:18;
add an F13 row pinning the F-runtime-group-per-CPU limit and the PLCSIM
instance budget (or recording them unverified, F4-style); and record in the M6
entry condition that the deep-research brief must answer how four safety
instances are actually hosted before D1's "it scales" is quoted again.

---

## Finding 4 — MAJOR. D3's zone permit plants a two-owner collision with invariant 5 at M6, and the envelope sentence claims for the PLC what only other layers can make true

**The claim attacked.** D3: *"the PLC forms and owns the motion envelope; no
motion occurs outside it"* — envelope = motion enable, speed ceiling, **zone
permit** (`docs/adr/0011:153-157, 172-176`).

**Attack (a): who owns "may the vehicle be in zone X"?** Invariant 5
(`CLAUDE.md` §2): *"Order assignment, traffic and **zone reservation** belong
to the fleet manager."* At M5 there is no fleet manager, so the PLC issues the
zone permit and nothing collides. At M6 the fleet manager reserves zones —
that is the gate's own subject matter (ADR 0010 D3) — and the PLC still
publishes a zone permit in the envelope. Two writers for one datum is exactly
what invariant 10 forbids, and the seam is undecided: ADR 0011's what-is-not-
decided list defers the envelope's node names to `opcua-nodes.md` (m5-17) but
never asks who owns the zone verdict once the layer that invariant 5 assigns it
to exists. Concrete failure: m5-17 mints `Forklift/Envelope/ZonePermit` with
the PLC as owner; the M6 fleet manager arrives owning zone reservation; either
the FM writes the PLC's permit (inverting invariant 4's direction of authority
for that datum) or the vehicle consumes two zone verdicts from two owners.
Every M6 traffic deadlock thereafter is a debugging session across an ownership
boundary nobody drew. **This is the trap D3 sets for M6**, and it is cheap to
disarm now: one sentence in m5-17 ruling whether the PLC's zone permit is (i) a
fixed-equipment interlock (PLC-owned, about door/charger/station zones only)
or (ii) a traffic instrument that the fleet manager will own at M6, with the
PLC term retiring or becoming a pass-through. As drawn it reads as (ii) wearing
(i)'s clothes.

**Attack (b): the enforcement locus.** "No motion occurs outside it" is made
true by the envelope-gate node — Python, in `agv/`, m5-11 — and, for the
ceiling, by the F-side SLS monitoring of m5-15. The PLC standard program can
form the envelope; it cannot enforce it. If the gate node hangs with a stale
non-zero command, motion occurs outside the envelope and the PLC's only role is
to have published a number. The M4 claim was structurally different: no
setpoint existed unless the PLC formed it. The D3 sentence is therefore a claim
about the **system** phrased as a claim about the **PLC**, and the honest
one-line version is: *the PLC owns the envelope; the vehicle's gate node
enforces it in process, and the F-layer's SLS backstops the ceiling.* That
sentence still tells a supervision story a reviewer recognises — D3 does not
need the inflation.

**Attack (c): the public identity sentence has not followed the amendment.**
ADR 0011's own consequence: *"Every document that quotes the M4 phrasing must
quote the mode with it"* (`docs/adr/0011:302-303`). The repository's front page
does not: `README.md:4-5` (*"a Siemens S7-1500 forms every motion setpoint in
between"*) and `README.md:31-33` (*"owns fixed equipment, interlocks and every
motion setpoint"*) are unqualified. True today, false the day m5-11 lands, and
no TODO item exists for it (the README items at `docs/TODO.md:211-215` are
about the layer diagram, not this). Undocumented drift of exactly the kind the
consequence predicted.

**Verdict.** D3's core — envelope supervision, loop onboard — **survives the
attack**. It is the correct industrial pattern; the alternative was tried
against invariant 9 and the Nav2 progress-checker mechanics and rejected for
reasons that hold; VDA 5050 at M6 tells the same story, so the gate inherits
rather than renegotiates. This is a genuine refinement, not a retreat — but
only because the M4 claim survives intact in the mode it was demonstrated in.
The residue is real: (a) needs an owner ruling at m5-17, (b) is one honest
sentence, (c) is one README edit plus a TODO line.

---

## Finding 5 — MAJOR. The measurement/safe channel split has a single ray-cast behind both channels, a live instance where those rays are already known wrong, and the authority file contradicts the build

**The claim attacked.** The two-channel model:
`agv/forklift/README.md:104-107` — *"They are two outputs of one device and
they travel two paths that never meet."*

**Attack (a): common cause, and it is not hypothetical.** Both channels are the
same `gpu_lidar` render. The real microScan3 also derives both outputs from one
measurement core — the split is honest **device** modelling at that level — but
the real device's safe channel adds what earns it the name: certified
self-diagnosis, contamination and dazzle monitoring, a reference contour. The
modelled safe channel adds a Python field evaluation (m5-12) over the identical
rays. So the model's two channels share every failure of the rays, and the
repository already contains the proof that this failure class is live: **R7**
(`EVIDENCE_SENSOR_COVERAGE.md:556`) — the simulated sensor sees *through* the
mast's 0.72 m collision slab because only the two 0.09 m rails are rendered,
8.9° of shadow against a physical 29.0°. On the front scanner the same
mechanism means any visual/collision divergence makes the process stop **and**
the F-side demand blind in the same sector on the same scan — a common-cause
failure that no document names as such. "Two paths that never meet" is true of
the transport and silent about the source. One sentence fixes it: *both
channels fail together when the model's rays are wrong; the split provides
naming hygiene and consumer separation, not redundancy.* Until that sentence
exists, a reader may take the split for a two-channel architecture, which D5
item 1 would then be violated in spirit by.

**Attack (b): the authority file is stale against its own commit.**
`agv/forklift/model.sdf:240-245`, in the committed state (`6068b31`, the m5-06
commit itself): *"scripts/obstacle_zone.py evaluates a comfort zone over the
NAVIGATION lidar … The two safety scanners have no consumer in this directory
at all, by design."* Both sentences are false at HEAD: `obstacle_zone.py:8,200`
subscribes to the front safety scanner's measurement channel, and
`README.md:46` says so. The file that declares *"THIS FILE IS THE AUTHORITY"*
(`model.sdf:104-105`) carries the pre-ruling design as current fact, in the
very commit that reversed it. Concrete failure: a later brief (m5-12 is the
obvious one) reads the authority file, believes the safety scanners are
consumer-free, and re-litigates or contradicts the owner's measurement-channel
ruling. Given this project's r4-class insistence that the process stop and the
safety path never share a description, the authoritative model file describing
the wrong consumer is not a nitpick.

**Attack (c): where the honest work is.** For balance: the naming discipline
(`measurement` in every reachable name, `check_sensor_frames.py` §4 checking it
mechanically), the refusal to bridge the unconsumed rear channel, and the
measured R8 self-occlusion band with its field-geometry (not sample-filter)
mitigation are all genuinely good engineering, and the m5-06 live crate
measurement (0.85 m → `True` where the nav lidar read clear) demonstrates the
ruling's point rather than asserting it. The split **survives as honest device
modelling**; it fails as anything more, and nothing may ever present it as
more.

**What I would change.** Fix the model.sdf comment block (one edit, agv/
agent); add the common-cause sentence to the README's two-channel section and
to the m5-12 brief; resolve R7's mast representation before m5-12 computes any
field over rays that pass through a body the vehicle would collide with — R7 is
already an open question, but m5-12's sequencing on it is not recorded
anywhere, and it must be.

---

## Finding 6 — MODERATE. D4's "read-only by construction" is, as deployed today, the same class of property it rejected foxglove_bridge for

**The claim attacked.** D4: read-only *"by construction, not by
configuration"*; foxglove rejected because its read-only property *"would
depend on configuration rather than construction"*
(`docs/adr/0011:186-189, 372-375`).

**The attack.** Trace what would actually stop someone adding a publisher to
the monitoring service: nothing structural. ROS 2 grants any node in the graph
the ability to create publishers; "no write endpoint and no publisher" is a
property of source code that one future edit flips — precisely the mutability
the foxglove rejection cited, one layer down. The genuinely constructive
option — DDS-level access control (SROS2 permissions confining the
participant to subscribe-only, enforced by the middleware, not by the absence
of code) — appears nowhere in the ADR, the plan, or the m5-13 wave item. The
distinction doing the rhetorical work in D4 is therefore currently a
distinction between *whose* text file gets edited. The ADR's consequences
section deserves credit for admitting the burden (*"'Read-only by construction'
has to be provable"*, `docs/adr/0011:287-289`) and deferring it to the first
monitoring brief — the claim is honestly flagged as unproven. But the brief
that must discharge it (m5-13, `docs/PLAN.md:78-79`) says nothing about **how**,
and the acceptance bar ("show it as a build property rather than a
configuration setting") has no named mechanism to clear it with.

**Topology check.** The §3 edit itself is clean: the `--o` style is genuinely a
third plane, both edges are mechanically-verified one-way, neither touches the
PLC, and invariant 11 now binds the monitoring edge. The m5-02 report's
verification (rendered SVG, marker classes) is exemplary. The sour note is
priority: the monitoring plane — a service that does not exist — got its
owner-approved diagram edge in wave 0, while `bridge/` — the layer every
demonstration since M3 runs through — remains undrawn, tracked only as a TODO
item with no brief number (`docs/TODO.md:64-72`). Invariant 11 thus now
enforces an edge for future code while still unable to see the layer the
current command path uses. The gap is well-recorded (LESSONS 2026-07-30, m5-02
open question 1); its handling is honest but unscheduled, and "unscheduled" is
how this project's own LESSONS say things age.

**Verdict.** D4 **survives with a demand attached**: the m5-13 brief must
either name the enforcement mechanism (SROS2 permissions, or an equivalent
middleware-level denial) or downgrade the language to "read-only by review and
by test" everywhere it appears. And the bridge topology brief should be
numbered into the plan, not left in TODO — it is a smaller edit than m5-02 was.

---

## Finding 7 — MINOR. D5 sweep: substantially clean; three residues

The repository was swept for achieved-PL/SIL/PFH claims, datasheet figures
presented as system results, and unqualified "tested/verified/validated"
safety wording. **The discipline has held remarkably well** — every PL figure
found travels with "target", "floor", "derived" or an explicit non-claim table,
the microScan3 F8 figures appear only as device-class attribution
(`model.sdf:224`, `agv/forklift/README.md:82`, both ADR-referenced), and the
evidence files carry the negative claims at their heads. Residues:

1. `docs/safety/PL-SCENARIOS.md:177, 408, 461` — *"Category 3 is claimed
   rather than Category 1"*, *"the single-fault case that Category 3 is
   claimed for"*, *"Category 3 is a claim about single faults."* Pre-ADR-0011
   wording meaning "targeted", protected by the document's own §0 disclaimers —
   but D5 turned the claim boundary into *"a list … which a verifier can grep
   for"* (`docs/adr/0011:321-323`), and these are the lines that grep will
   surface against item 1 forever. m5-18 (the brief that lands the D5 list in
   the safety documents) should sweep the verb.
2. The D1 disclosure gap in roadmap/PLAN (finding 3a) is also a D5-adjacent
   wording issue: "onboard safety controller" without the artifact sentence is
   the closest thing to an overclaim the sweep found.
3. `docs/roadmap.md:74` criterion (b) says AT-01/07/08 "pass … on PLCSIM
   Advanced" — mode-of-evidence carried correctly; noted as a positive control
   that the qualification pattern is achievable in criterion text, which makes
   finding 1's missing sentence less excusable.

---

## Finding 8 — MODERATE, cross-cutting. M5 is mutating the plant M4's unrecorded showcase must run on

CLAUDE.md §6: *"Do not start a gate before the previous one is verified."* M4
is **closing, not closed** — the formal showcase recording and m4f-09
verification are still in the owner queue (`docs/TODO.md:7-27`,
`docs/roadmap.md:4-6`). Meanwhile M5 briefs m5-04/m5-06 have already deleted
the 180° scanner that M4 criterion (d) was demonstrated on and re-homed the
obstacle stop from a 0.25 m plane to the front safety scanner's 0.15 m plane
(`docs/reports/m5-06-measurement-channel.md:64-66`). Concrete failure: the
owner records the M4 showcase on today's tree — the recording demonstrates a
sensor suite, a plane and a sector-centring that the m4f evidence chain never
measured; or records it on the old tree — the gate's closing evidence then
documents a machine HEAD no longer contains. Either way the m4f-09 verifier
inherits a reconciliation problem that a sequencing rule existed to prevent.
The overlap is disclosed (roadmap says "closing"; the m5-06 report names the
plane change) but the specific collision — criterion (d)'s instrument replaced
before criterion (d)'s recording exists — is written down nowhere. The m4f-09
brief must state which tree the showcase certifies, and the showcase script
should name the 0.15 m plane if run on HEAD.

---

## What survives, stated after the attacks

- **D1's reading** (onboard controller): survives — correct real-world
  architecture, honestly declared; its *perimeter* (disclosure, B4, scaling
  facts) does not, per finding 3.
- **D2's primary path**: survives as a design; its *conditionality* has
  already leaked out of three contracts (finding 2), and its fallback is
  gate-fatal undeclared (finding 1 — the most severe finding in this review).
- **D3**: survives as the correct supervision pattern; the zone permit's M6
  ownership, the enforcement-locus wording, and the public README are the
  residue (finding 4).
- **D4**: survives with a demand — name the mechanism or downgrade the
  language (finding 6).
- **D5**: survives essentially intact; the best-executed of the five
  (finding 7).
- **The channel split**: survives as device modelling with a naming discipline
  that is genuinely enforced; fails as redundancy, which nothing yet claims but
  one stale authority comment invites (finding 5).

**The decision most likely to be regretted: D2.** Not because the F-I/O path is
wrong — because the project has already begun living as though the probe had
answered yes, while its named plan-B cannot close the gate. Every week before
m5-03 runs widens the gap between the two.

## The single most important recommendation

Before m5-03 executes, obtain one owner ruling that answers finding 1 in
writing: **what happens to roadmap M5 criterion (a) if the F-I/O probe answers
no** — criterion amended by ADR, or fallback upgraded to an API-driven
(labelled, S015-checked) standard-DB stimulus that keeps the scanner-to-F-block
automation. Then, in the same brief, restore D2's conditionality to the four
documents that dropped it (`model.sdf`, `agv/forklift/README.md`,
`docs/PLAN.md` summary, `EVIDENCE_SENSOR_COVERAGE.md` §10c). Everything else in
this review can wait a wave; this cannot, because m5-03's verdict is the event
that turns the ambiguity into either a dead sentence or a failed gate.
