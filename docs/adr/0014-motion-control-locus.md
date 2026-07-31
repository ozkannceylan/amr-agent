# ADR 0014: The motion control locus — the loop closes onboard, the rejected alternative and its reasoning, and the bounded reading of ADR 0011 D1

Status:        accepted (2026-07-31). Owner-approved on that date, on the
research recorded in `docs/reports/mc-01-motion-control-locus-research.md`; the
five decisions below are the owner's rulings, recorded here.

What this ADR does, stated before anything else:

- It **confirms ADR 0011 D3** (`docs/adr/0011-sensored-autonomy-architecture.md`)
  **as refined by ADR 0012 D1** (`docs/adr/0012-envelope-composition.md`). It
  changes **no word** of either, refines neither, and supersedes nothing. D1 below
  is a confirmation on new evidence, not a new ruling about where the loop closes.
- It **records the rejection of the alternative the owner proposed**, with the
  argument that decided it, so that the question is re-opened only by new evidence
  and never re-litigated from memory (D2).
- It **bounds how ADR 0011 D1 is read** (D3). ADR 0011 is **not edited** — CLAUDE.md
  §8 forbids it, and D1 keeps its text forever. What this ADR fixes is the scope a
  reader may give the word *onboard* in it, because that scope had already begun to
  drift and the drift is documented.
- It **restates the command interface as three seams** (D4) against contracts that
  already exist. It **mints no node, no tag and no topic name**, defines no PLC or
  vehicle logic, and adds nothing to `docs/interfaces/opcua-nodes.md` §12.
- It **records a disclosure obligation as a requirement** (D5), not as a caveat:
  in autonomous mode the PLC's authority is permissive and *checked, not compelled*,
  and the M5 showcase must narrate it.
- **Invariants 1–13 are untouched.** Six bear directly on this decision — **1, 5, 6,
  9, 10 and 11** — and the check is shown per invariant below rather than asserted.
- **No gate criterion is changed, weakened or widened.** `docs/roadmap.md` remains
  the live gate order (ADR 0010), M5 stays the current gate, and D5's narration
  requirement is a statement the showcase must make, not a new criterion item. The
  roadmap and the tracking files are edited by their own briefs, not by this one.

---

Context:

**What forced the decision.** At the M5 briefing the owner proposed an alternative
motion architecture — the vehicle computer plans and hands the PLC incremental
motion work, the PLC forms every setpoint as it did at M4 — and, rather than ruling
it from first principles, commissioned research against named industrial products.
That research is `docs/reports/mc-01-motion-control-locus-research.md`. It is this
ADR's **evidence base and is cited, not restated**: §A (how named products divide
it), §C (rates and latency), §D (the safety layer's placement), §E (the four
interface granularities), §F (the two architectures judged), §G (the M6
consequence), §K (the invariant walk) and §L (relationship to the recorded ADRs).

**Why an ADR and not a report.** mc-01 §M open question 3 asked exactly this, and
the owner ruled it: a report is evidence, and the next architecture review must find
a **decision**. The project's own LESSONS rule of 2026-07-31 — that a recommendation
hardens into a decision by repetition — is the reason the ruling is written while
the answer is one document old rather than after five documents have quoted it.

**Verification discipline.** All external sources in mc-01 were checked
**2026-07-31** and are graded there as **[fetched]** (page retrieved, statement
quoted from it) or **[snippet]** (statement from a search-result excerpt of the
named page). This ADR asserts **no external fact of its own** and re-verifies none:
mc-01 §N is the pinned source table, with URLs and grades, and the LESSONS rule of
2026-07-26 applies to it — **a `[snippet]`-grade claim that is ever made
load-bearing beyond mc-01 must be re-verified and re-pinned before it is relied
on.** Facts already pinned in ADR 0011's evidence table (F8–F11) are reused by that
reference and are not re-verified here.

**The recorded absence, carried forward as falsifiable.** mc-01 §E and §N record
that **no named free-navigating AGV/AMR product was found that ships a
segment/increment interface between a navigation computer and a setpoint-forming
controller, and none that routes its trajectory-following loop across a wireless or
best-effort network.** What would settle it is a vendor integration manual
demonstrating either. If one surfaces, D2 below is **re-argued against it**, not
defended.

### The figures this ADR quotes, with provenance

**No figure in this table is a property of a real vehicle, and none may ever be
presented as one.** This project has no vehicle and no PLC hardware: the machine
that produced G1 and G2 is a **simulated** CPU under S7-PLCSIM Advanced talking to a
Python bridge, and G3–G6 are arithmetic over those numbers and over stated inputs.

| # | Figure | Value | Kind | Source and environment |
|---|---|---|---|---|
| **G1** | Closed-loop interval, input write acknowledged → changed output command read back (bridge → OPC UA → PLC scan → back) | **count 6, min 45.447, median 46.163, p95 47.690, max 47.690 ms** | **measured**, and an **upper bound**: the interval contains the transfer into the process image, at least one OB30 scan, the server's sampling of the output **and the bridge's own 0–50 ms poll phase**, so it is never a measurement of the PLC's reaction | `bridge/EVIDENCE_LATENCY.md` §B2.5 via `docs/reports/m3-33-evidence-writeup.md`, owner session **2026-07-28**. Environment (§B2.9): **WSL2 Ubuntu 24.04 bridge host, Windows-side S7-PLCSIM Advanced V7.0, simulated CPU 1513-1 PN FW V3.1**, one router hop, no VPN. **Not a container measurement** |
| **G2** | Presence-to-assertion chain, full path | **145.6–150.8 ms** | **measured**, same caveat class as G1 | `bridge/EVIDENCE_LATENCY.md` §B2.6a, same session and same environment as G1 |
| **G3** | Along-track error of a command delayed by Δt, `d = v·Δt` | 15 mm at 0.3 m/s / 50 ms; 100 mm at 1.0 m/s / 100 ms; **225 mm at 1.5 m/s / 150 ms** | **derived**, arithmetic from stated inputs | mc-01 §C |
| **G4** | Cross-track error entering a curve Δt late, `e ≈ (v·Δt)²/2R`, R = 1.5 m | 0.1 mm at 0.3 m/s / 50 ms; **16.9 mm at 1.5 m/s / 150 ms** | **derived** | mc-01 §C |
| **G5** | Loop-bandwidth ceiling a pure delay imposes, budgeting ~30° (0.52 rad) of phase margin to it | crossover ≈ **1.6 Hz** at Td = 50 ms; ≈ **0.55 Hz** at Td = 150 ms — against the **1–2 Hz** of lateral bandwidth a follower wants at 1.0–1.5 m/s | **derived**. And the delay on this path is **variable** (poll-quantised, scheduler-jittered), which cannot be compensated the way a constant delay can | mc-01 §C |
| **G6** | Docking scatter from command-age jitter | ±100 ms jitter scatters the stop position by **±30 mm even at 0.3 m/s creep**, against an industrial docking figure of **±1 cm**; meeting ±10 mm at 0.3 m/s needs jitter under **~33 ms** | **derived**, against a vendor figure mc-01 grades **[snippet]** (BlueBotics ANT, mc-01 S2) | mc-01 §C, §N |
| **G7** | The speed the model works around | **0.3 m/s** maximum with personnel-detection means muted | external, **pinned** as ADR 0011 **F11** (ISO 3691-4, verified 2026-07-30) | Quoted as the practice the model follows, **never as a conformity statement** (ADR 0011 D5) |

**One consequence of reading G1 honestly.** It is an upper bound that already
contains a 0–50 ms poll phase, so it is neither a floor for a better implementation
nor a ceiling for a worse one. It is quoted here for one purpose: to show what a
supervision channel costs (nothing that matters — §12.4 **E1**) and what the same
channel would cost inside a 20 Hz control loop (G5).

---

Decision:

### D1 — Motion control closes **onboard the vehicle**, and **no motion value at any granularity crosses OPC UA**

The vehicle's own computer runs **perception, localization, planning and the
path-following loop, and writes the actuators** — in the twin, the joint commands
the physics engine consumes. Across the OPC UA seam the vehicle sends **no motion
value at any granularity**: it receives the envelope and the mode in force, and
returns its applied mode and a heartbeat, which is `docs/interfaces/opcua-nodes.md`
§12 exactly as that section already stands.

**This confirms ADR 0011 D3 as refined by ADR 0012 D1.** Nothing in either is
changed, and the mode-scoped reading of the M4 phrasing stands word for word.

**The evidence, in one sentence, cited not restated.** Real systems have exactly
**two** motion seams — continuous velocity setpoints between the follower and the
drives, always over **deterministic onboard links**, and **path or mission download
between fleet and vehicle**, which is the only motion interface that tolerates a
network — and **nothing ships in between** (mc-01 §A, §E). Navigation and vehicle
control co-reside on one onboard controller in every named product surveyed, and the
stationary side dispatches orders and reads state.

**What this adds to ADR 0011 D3, which is why the confirmation is worth recording.**
D3 rested on three counts: the timing-critical loop in Python (invariant 9), the
gate-zeroed command aborting the goal through Nav2's progress checker, and the
absence of published prior art for PLC-in-the-loop Nav2. The research **widens the
third count**: it found no prior art for **any** vendor's navigation loop crossing a
non-deterministic link, in any stack, at any granularity (mc-01 §L). D3's rationale
is therefore stronger than when it was written, on named products rather than on the
original three-count reasoning alone.

**"Motion control in a PLC" is real — as an *onboard* PLC.** Two surveyed products
put exactly the setpoint-forming role in a PLC, one per vehicle, riding on the
vehicle, commanding its drives over a local deterministic fieldbus (mc-01 §A). That
pattern is not rejected here. What D3 below rules is that **this project's S7-1500
is not that box**, and D2 rules that the interface the alternative implies is not one
any surveyed vendor ships.

### D2 — The incremental-work alternative is **rejected**, and the reason is recorded so it is not relitigated from memory

**The proposal, stated fairly and in the owner's own terms** (from
`docs/briefs/mc-01-motion-control-locus-research.md`, "Architecture B"): the safety
laser scanners are wired to the F-PLC and the F-program's most important job in
either drive mode is SLS and STO; **steer-by-wire and motor control flow through the
PLC**; the vehicle computer reads the lidar, builds the map, plans the motion and
**gives the PLC work** — *"this much to the right, this much forward"*; the vehicle
never writes an actuator; the PLC forms every motion setpoint exactly as it does for
the teleoperated joystick at M4, with the mode selector merely changing which source
writes the request. What recommended it inside this project was real: it preserves
M4's central claim into autonomous mode and reuses the M4 PLC logic unchanged.

It was **examined seriously and rejected**, on four grounds. The first is the one
that decides it, and it is written out in full because it must survive being read
three months from now by someone who remembers only the conclusion.

**(1) The structural argument — the corrector needs pose it does not hold.**

- Correcting motion error requires **pose at loop rate**. A follower that corrects at
  20 Hz needs to know where the machine actually is, 20 times a second; without that,
  it is not correcting, it is replaying.
- **Pose is produced onboard**, by SLAM, from the scan — the highest-rate,
  highest-volume data in the system, consumed where it is born on every named product
  (mc-01 §A, §J).
- Therefore exactly **two branches** exist, and both are closed:
  - **Pose streams to the PLC every sample**, so that the PLC can correct. That is
    **the same network-in-the-loop the architecture forbids, merely reversed**: the
    same per-sample traffic across the same non-deterministic link, in the opposite
    direction, paying G1's cost inside the loop and putting a **timing-critical
    dependency in the bridge's Python path**, which invariant 9 forbids outright.
  - **Correction stays onboard.** Then the PLC executes increments it **cannot
    check**, computed from data it **does not hold**, and **contributes only dead
    time** to a loop the machine is already closing.
- **There is no third branch**, and this argument is **independent of latency**: even
  at zero delay, branch two splits the ownership of *"where the vehicle is in its
  motion"* between the sender that holds path and pose and the executor that holds
  segment progress — two owners for one datum, which invariant 10 forbids, appearing
  here in interface form rather than as a variable (mc-01 §E option b).

**(2) The empirical argument — this middle form is not shipped by the vendors
surveyed.** mc-01 §E records it as a falsifiable absence: no named free-navigating
AGV or AMR product ships a segment/increment interface between a navigation computer
and a setpoint-forming controller. The closest real patterns sit **below** the
navigation layer (continuous setpoints, onboard, deterministic link) and **above**
it (path or mission over the network). The alternative sits precisely in the
unoccupied middle: **too granular for the link it would cross, too coarse to be the
drive interface**. This is an absence claim and is recorded as one — see the
falsifiability note in the Context above.

**(3) The quantitative argument.** At warehouse speeds a delayed command costs
G3–G4; a delay inside the loop costs G5 — a follower that wants 1–2 Hz of lateral
bandwidth may cross at ≈0.55 Hz behind a 150 ms delay, and the delay on this path is
variable rather than constant; and a stop triggered across a link with ±100 ms
command-age jitter scatters by G6's ±30 mm against an industry ±1 cm. At the muted
speed of G7 the result is a tuning problem; at ≥1 m/s path following, and at any
speed for ±1 cm docking, it is an engineering problem that does not tune away.

**(4) Why M4's teleoperation is genuinely different — a human closed that loop.**
This is the part most likely to be forgotten, because the two architectures look
identical on a block diagram: *operator or planner → PLC → actuator.* They are not
the same, and the difference is **who closes the loop and at what bandwidth**.

- At M4 the **human** closed it. The operator watched the machine, formed the
  correction, and moved the joystick. The loop's bandwidth was the operator's — on
  the order of a hertz — and its slowest element was the person, so tens to a hundred
  milliseconds of transport delay were **inside the noise of the loop it belonged
  to**, and a human adapts to a steady delay by anticipating it. The PLC inserted
  into that path cost nothing it could be blamed for, and **bought something real**:
  it was the interlock layer between operator and plant, forming every setpoint under
  its own permissives. That is why *"the PLC forms all motion setpoints"* was a strong
  claim at M4 and remains one.
- In **autonomous mode the loop is machine-closed at 20 Hz** against a pose that is
  already one sensing period old. The same insertion point now adds **only** delay
  (G5) to a loop with none to spare, and it adds it to a loop whose correction the
  PLC cannot perform anyway (argument 1).
- The consequence is recorded, and it is a scope statement rather than a retreat:
  **the M4 sentence is preserved exactly where it was demonstrated**, mode-scoped —
  in `Teleop` the PLC still forms every motion setpoint (ADR 0011 D3, ADR 0012 D1,
  `opcua-nodes.md` §12.9 **C1**), the M4 gate criterion stays closed and unchanged,
  and the M4 showcase's statements remain true as recorded. **Autonomous mode does
  not inherit that sentence**, and no document, caption or spoken line may make it
  do so.

**What choosing the alternative would have cost, recorded so the weight is visible
and not to reopen it** (mc-01 §L): superseding **ADR 0011 D3**, superseding **ADR
0012 D1**, withdrawing **`opcua-nodes.md` §12** and re-minting a per-sample or
per-segment command group, amending the bridge's no-logic cadence story, and
recording a new reading of **ADR 0011 D1** extending *onboard* to the standard
program — five documents against the grain of the evidence.

**What is *not* rejected, stated because the rejection is narrow.** The owner's
safety foundation — the scanners on the F-layer, and SLS and STO as the F-program's
most important job in either drive mode — is **confirmed** by the same research
(mc-01 §D) and is untouched here. SLS is a **monitoring** function: something
measures speed safely, and on violation the drive's own stop reaction fires
regardless of who was writing the setpoint. **The safety layer bounds any motion
controller from below; it anchors none of them in place.** Rejecting the alternative
rejects an *interface*, not a safety reading.

### D3 — ADR 0011 D1's **"onboard"** is bounded to the **F-runtime group**

**The boundary, in one sentence.** *ADR 0011 D1's word "onboard" covers the
F-runtime group `F_Forklift_Safety` and nothing else: the **standard program** is
the **cell's** PLC — the owner of the fixed equipment, the OPC UA server of
invariant 4, and at M6 one box serving four vehicles — and no reading of D1 makes
it any vehicle's onboard controller.*

**What is inside the boundary.** `F_Forklift_Safety` is, architecturally, the
safety controller carried **by** the forklift, and the chain **scanner → F-program →
STO is internal to the vehicle**. That is ADR 0011 D1 unchanged, it is the
industrial pattern (mc-01 §D), and nothing here narrows it.

**What is outside it, with the three properties that put it there** — each already
recorded elsewhere, none new:

1. **It owns fixed equipment.** Conveyor, door, charger, interlocks and the station
   handshake are the standard program's by CLAUDE.md §1 and invariant 5, and by its
   own specifications. Fixed equipment is the one thing that is unambiguously **not**
   onboard.
2. **It is the OPC UA server** of invariant 4, with the HMI as a client today and the
   fleet manager as a client at M6. A vehicle-borne controller that is also the cell's
   server for a fleet manager is not a topology any surveyed product ships.
3. **At M6 it is one program supervising four vehicles.**

**Why the boundary is stated plainly rather than left to inference: the M6
arithmetic.** Extending the onboard reading to the standard program would make **one
stationary program four vehicles' onboard motion controller at once** — a sentence
with no referent in any surveyed product (mc-01 §A, §G) and none in this
repository's own topology. There is no fleet size at which it becomes coherent; it is
already incoherent at n = 1 and merely more visible at n = 4.

**The reading was already drifting, and the drift is documented.** ADR 0011 D1's text
rules the **F-runtime group**. `docs/briefs/mc-01-motion-control-locus-research.md`
states, as one of the things that recommended the alternative, that it *"sits
consistently with ADR 0011 D1's reading that the S7-1500 represents the forklift's
**onboard** controller"*. That is a migration from *"the forklift's F-runtime group is
the vehicle's onboard safety controller"* to *"the S7-1500 is the vehicle's onboard
controller"* — two words dropped, and the scope of the claim doubled — and it
happened inside a single briefing document. It is exactly the failure mode the
LESSONS rule of 2026-07-31 names: a phrasing hardens by repetition. This ADR stops it
at one occurrence.

**It compounds a disclosure that already exists.** ADR 0012 D2.1 landed the sentence
that the **single hosting 1513F-1 PN is a simulation artifact**, not an architectural
claim that one F-CPU guards a fleet. An unbounded onboard reading would turn that
disclosed artifact into an asserted architecture — one CPU being, at once, four
vehicles' safety controller *and* four vehicles' motion controller *and* the cell's
equipment owner.

**What D3 does not do.** ADR 0011 is **not edited**: D1 keeps its text, and this ADR
bounds only how that text is read, in the same manner ADR 0012 D1 retired a term
without touching the document that carries it. D1's architectural reading is
unchanged, and so is the standing of its scaling sentence: *"it scales"* continues to
travel with **F13 and F14**, both recorded unverified (ADR 0012 D2.3), and this ADR
neither settles nor weakens them.

### D4 — The command interface, **three seams**

Stated against contracts that already exist. **This decision mints no name, defines
no logic and adds no node**; every name below is `docs/interfaces/opcua-nodes.md`
§12's or the vehicle layer's.

**Seam (a) — supervision. PLC → vehicle, over OPC UA, carried by the bridge.**

| Item | Statement |
|---|---|
| Content down | The **autonomy envelope** of ADR 0011 D3 as refined by ADR 0012 D1 — motion enable, speed ceiling, fixed-equipment / station permit — plus the mode in force, as specified in `opcua-nodes.md` §12 |
| Content up | The vehicle's **applied mode** and its **heartbeat** (§12.6) — a readback, never a second answer to "what mode is the machine in" |
| Rate | Formed at the **PLC's own scan** and republished by the bridge. **Contractually insensitive to its own rate**: §12.4 **E1**'s test — a 2 Hz consumer and a 20 Hz consumer behave identically apart from latency — is what makes G1's ~46 ms invisible here, and any node for which that test fails does not belong in this group |
| Loss, vehicle side | Envelope older than the vehicle's **freshness window** (§12.4 **E5**, an `agv/` named constant) → **controlled stop onboard**; stale is non-permissive |
| Loss, PLC side | Vehicle heartbeat verdict false (§12.6 **V1**–**V4**) → the PLC publishes the **non-permissive** envelope |
| Standing | **Both are degraded-mode behaviour and neither is a safety function** (invariant 2, §12.1) |
| State | The PLC owns the envelope and the mode verdict; the vehicle owns its report values. Neither recomputes the other's datum (invariant 10) |

**Seam (b) — motion. Onboard only; it never crosses OPC UA.**

| Item | Statement |
|---|---|
| Content | The onboard controller's velocity command → a **smoother closed on measured odometry** (ADR 0011 D3's recorded consequence, §12.4 **E4**) → the **envelope gate** → the vehicle's I/O layer → the joint commands the physics engine consumes |
| Gate law | **Enable false, or envelope stale → controlled stop** on the vehicle's own deceleration ramp; **otherwise clamp the magnitude of speed to the ceiling** |
| Gate placement | **The gate sits BELOW the smoother**, so it still acts with the link dead. A gate above the smoother is a gate the smoother can ramp past; a gate that needs the link is a permission that lapses exactly when it matters most |
| State | The vehicle owns path, pose, progress and its own stop ramps |

**Seam (c) — orders. Fleet ↔ vehicle at M6, VDA 5050 over MQTT.**

Node and edge graphs — **the network-tolerant seam**, and the only motion-adjacent
interface that tolerates a network at all (mc-01 §E option c). Invariant 3 is
unchanged and no motion value at higher granularity ever enters it.

**The one sentence that is D1 in interface form:** *no motion value crosses seam (a)
or seam (c) at any granularity, and seam (b) never leaves the vehicle.*

### D5 — The disclosure obligation, written as a **requirement**

**In autonomous mode the PLC's authority over motion is permissive and *checked, not
compelled*.** The envelope that expresses that authority is formed by the PLC and
**enforced by a gate node running on the vehicle** (§12.6 states it already: the PLC
forms the envelope and does not enforce it), and the compelling backstop is a safety
layer that is **modelled rather than real while the project is hardware-free** (ADR
0011 D5). A hostile reviewer can fairly say *"the supervisor's word is honour-system
in process terms."* **The answer is disclosure, not silence.** The following are
requirements, not suggestions, and each is checkable:

1. **The M5 showcase narration must state that the PLC forms the envelope and does
   not enforce it**, and that the enforcing gate runs on the vehicle. Not a footnote
   in a document: spoken and written where the autonomy is shown.
2. **It must state that the compelling backstop is the safety layer, and that in this
   project that layer is modelled, not real.** ADR 0011 D5's claim boundary is
   unchanged and binding beneath it — **no achieved PL, Category, SIL or PFH**, and
   *"safety functions tested"* never without *"in simulation, against a model"*.
3. **The gate's evidence must show the readback** that demonstrates the vehicle
   honouring the envelope — the §12.6 report against the envelope the PLC published —
   so that *"checked"* is a demonstrated check and not a word. A supervisor that
   published a bound and received nothing back would be making a claim it could not
   check; the two report nodes exist to be that check, and the evidence must exercise
   them.
4. **Where the project's PLC-depth claim actually rests must be stated rather than
   implied**, and it rests on three things: **M4's teleoperation**, where the PLC
   forms every motion setpoint and it is demonstrated and recorded; **the F-layer**,
   the vehicle's onboard safety controller under ADR 0011 D1 as bounded by D3 above;
   and **M6's PLC-owned station handshake end to end**. The autonomous-mode envelope
   is *supervision* — a real and recognised role, and not the depth claim.
5. **The M7 LLM-operations layer inherits the same sentence**, one layer further out:
   an authority that supervises without commanding is checked rather than compelled,
   and the same disclosure applies to it.

**This changes no gate criterion.** The M5 row already requires the showcase to name
which reactions are F-CPU safety functions and which are process behaviour; D5 adds
what the narration must say about the **envelope's authority**, and any roadmap or
brief wording that carries it is a separate brief's — this ADR does not edit
`docs/roadmap.md`.

---

### Every invariant that bears on this decision, checked rather than asserted

The full walk is mc-01 §K, which found none of the thirteen needing change. The six
the decision actually turns on are restated here so the check is in the decision
record:

| Inv | Check under D1–D5 |
|---|---|
| **1** Safety never traverses the network | Holds, and **D2 strengthens it**: the rejected alternative's branch one would have put per-sample pose on the process network in service of a control loop. No safety datum appears on any of D4's three seams; the scanner → F-program → STO chain is internal to the vehicle (ADR 0011 D1, D2) |
| **5** The PLC does not manage the fleet | Holds. The PLC keeps fixed equipment, interlocks and handshakes; orders, traffic and zone reservation stay fleet-side (ADR 0012 D1). D3 is this invariant read back onto the PLC's identity: a controller that owns the cell's equipment is the cell's |
| **6** The fleet manager never commands actuators | Holds. The envelope is a **permission a vehicle's control layer consumes**, not an actuator command (§12.1, §12.4 **E6**), and it is not writable by any client |
| **9** Hard real time stays out of Python | Holds and is **load-bearing**. The deterministic loop stays in the drive layer; the supervision seam is explicitly rate-insensitive (**E1**). The rejected alternative would have violated it in both of its branches — a 20 Hz command stream or a 20 Hz pose stream through the bridge's Python path |
| **10** Single source of truth per data item | Holds. Every datum in D4 has one owner. The rejected alternative's split of "where the vehicle is in its motion" between planner and executor was the counterexample, and it survives at zero latency |
| **11** Layers talk only to adjacent layers | Holds. The vehicle's control layer is **not** an OPC UA client and never becomes one (§12.1); it reads what the bridge republishes. The monitoring plane is unchanged (ADR 0011 D4) |

Invariants **2, 3, 4, 7, 8, 12 and 13** are untouched: loss reactions are degraded
modes and named as such (2); the M6 seam is VDA 5050 unmodified (3); the PLC stays
the server (4); the F-program's independence is unchanged (7); no Tailscale edge
appears anywhere in D4 (8); Gazebo throughout (12); no secrets (13).

---

Consequences:

What becomes harder:

- **The M5 showcase gains required sentences it must not omit.** D5's five items are
  narration and evidence obligations, and the failure mode is a recording that shows
  the machine behaving correctly while leaving the authority asymmetry unspoken —
  which is precisely the criticism the disclosure answers.
- **The evidence must exercise the readback, not merely publish it.** D5.3 turns two
  existing nodes into something a gate must demonstrate rather than declare, and a
  run that never disagreed proves less than one that shows a disagreement surfacing.
- **A rejected architecture now has a citation, which means it must be re-argued
  properly or not at all.** Anyone reopening D2 has to bring the falsifying artifact
  named in the Context — a vendor integration manual — rather than an intuition.
- **Two motion-ownership sentences continue to exist, one per mode**, and this ADR
  adds the reason they differ. Every document quoting *"the PLC forms all motion
  setpoints"* must quote the mode with it, or it reads as a contradiction of a closed
  gate.
- **The word *onboard* now has a scope that must be honoured in prose.** D3 makes a
  sentence like "the PLC is the vehicle's onboard controller" a documented error
  rather than a loose phrasing, and the sweep discipline of LESSONS 2026-07-29
  applies: sweep by subject, not by remembered phrasing.
- **A `[snippet]`-grade figure sits in a quoted comparison.** G6's ±1 cm industry
  reference is `[snippet]`-grade in mc-01; if any later claim leans on it beyond this
  comparison, it must be re-verified and re-pinned first.

What becomes easier:

- **The locus is a decision rather than a report.** The next architecture review
  finds a ruling with its reasoning attached, which was mc-01 §M's third open
  question and is now closed.
- **The M6 statement is coherent in advance.** Four vehicles cost four VDA 5050
  clients and four envelope consumers, and the architecture is restated zero times
  (mc-01 §G). The alternative had no coherent M6 statement at all.
- **The vendor-portability seam stays thin.** Under D1 the seam carries only the
  low-rate contract, so a port inherits nothing motion-critical — the claim ADR 0013's
  work rests on survives without qualification.
- **The simulation's honesty improves rather than needing a standing apology.** The
  loop industry keeps onboard is genuinely onboard in the twin as well, so the link's
  measured latency (G1) is a property of a **supervision** channel and not of the
  machine's visible motion quality.
- **The PLC's role in autonomy stays sayable in one line**, and D5 makes it sayable
  honestly: *the PLC owns the enable, the ceiling and the readiness of its own
  equipment; the fleet manager owns the traffic; the vehicle closes the loop — and
  the PLC checks that it did.*

What this ADR does **not** decide:

- **The envelope gate node's design**, its arbitration between the two command
  sources, and how the change of source is made without a step in the command — `agv/`'s,
  at m5-11 (§12.9 **C3**).
- **The vehicle-side freshness window's value** (§12.4 **E5**) and the PLC-side stale
  constants and latch policy (§12.6 **V3**, **V4**) — `agv/`'s and
  `plc/forklift/SPEC.md`'s respectively.
- **Node, tag and topic names.** They exist already in `opcua-nodes.md` §12 and are
  neither reopened nor enlarged here; §12.12's deliberately-absent rows stand.
- **How an M5 goal is commanded before a fleet manager exists** — explicitly not
  answered by a node (§12.13 item 4).
- **The envelope propagation measurement** — mc-01 §M open question 2 asks for a
  brief that measures PLC-write-to-topic age and jitter so E5's window is set from a
  measured number rather than from G1 as a proxy. It is requested, not scheduled here.
- **The public narrative's naming of the onboard stack** — mc-01 §M open question 1;
  `README.md` and the roadmap are other briefs' and other agents' files.
- **F13 and F14** (ADR 0012), the **m5-03 F-I/O verdict** (ADR 0011 D2), and
  anything about **claims**: ADR 0011 D5 is untouched and binding, and nothing here is
  a statement about any safety performance level.

Relationship to the ADRs this one stands on, each stated:

| ADR | Relationship |
|---|---|
| **0011** sensored autonomy architecture | **Confirmed, not superseded and not refined.** **D3** (envelope; loop closes onboard) is confirmed on named industrial evidence, and its no-prior-art count is widened by D1 above. **D1** is **not edited**; D3 above bounds only how its word *onboard* is read, and its architectural reading, its scaling sentence and its two unverified facts are untouched. **D2** (the F-I/O path and its fallback), **D4** (the monitoring plane) and **D5** (the claim boundary — binding beneath D5 here) are untouched |
| **0012** envelope composition | **Confirmed.** **D1**'s three-element envelope, with the fixed-equipment / station permit as the third element, is what D4 seam (a) carries; the zone-reservation separation and its naming discipline are unchanged. **D2**'s disclosures are the ones D3 above says an unbounded reading would have compounded |
| **0010** milestone restructure | Untouched. The gate order, the numbering, **D2**'s statement of M5's content and **D7**'s landing points all stand; `docs/roadmap.md` remains the live order and no criterion is changed |
| **0009** early cell-scope safety on the twin | Untouched. Its **D3** coupling architecture and **D5** wording discipline carry forward; the envelope and the vehicle's report are process data on the process plane and touch neither |
| **0008** commissioning gate and HMI layer | **D2**'s commissioning-HMI layer and **D3**'s ruling that teleop routing is standard-program process logic implementing **no** SRS function are unchanged. The M4 claim this ADR preserves mode-scoped is the one demonstrated under it |
| **0005** bridge layer | The bridge's **no-logic** contract is untouched and is one reason D2's rejected branches fail: the bridge carries the envelope and computes nothing, and a per-sample motion or pose stream would have made it a participant in a control loop |
| **0013** vendor portability gate | Untouched, and **strengthened by D1**: the vendor seam carries only the low-rate contract, so the ported program inherits no motion loop. Its gate placement and open items are not reopened |
| **0001** the invariants | **Invariants 1, 5, 6, 9, 10 and 11** are the ones this decision turns on. None of the thirteen is amended, and the check is tabulated above rather than asserted |

---

Alternatives:

- **The incremental-work interface — the vehicle sends "this much to the right, this
  much forward" and the PLC executes it, with steer-by-wire and motor control flowing
  through the PLC** — **rejected**, on D2's four grounds. In short, and never to be
  re-litigated from memory: correcting motion error needs pose at loop rate, pose is
  produced onboard by SLAM, so either pose streams to the PLC per sample (**the
  forbidden network loop, reversed**) or correction stays onboard (**and the PLC adds
  only dead time**); no surveyed vendor ships the interface; the measured and derived
  figures G3–G6 say what it would cost; and M4's teleoperation is not a precedent for
  it, because a **human** closed that loop at human bandwidth, where the PLC's
  insertion was free and bought interlocks.
- **Stream pose to the PLC at loop rate so that the PLC could correct** — **rejected**
  as its own alternative, because it is the branch that survives the first objection
  and fails a different one. It is the forbidden network loop with the arrow reversed:
  the same per-sample traffic over the same non-deterministic link, and it places a
  **timing-critical dependency in the bridge's Python path**, which invariant 9
  forbids. It also makes the bridge a participant in a control loop, against ADR
  0005's no-logic contract.
- **Leave the ADR 0011 D1 reading unbounded** — **rejected**. It was **already
  drifting** toward the standard program inside a single briefing document, and at M6
  the unbounded reading has **one PLC being four vehicles' onboard controllers at
  once**. The cost of bounding it now is one paragraph; the cost of bounding it after
  four documents have repeated the wider reading is a sweep, and the LESSONS rules of
  2026-07-29 and 2026-07-31 both say why.
- **Adopt the onboard-PLC pattern faithfully, by adding a second, vehicle-mounted
  controller** — **rejected for this project**, though it is the only faithful way to
  reproduce the surveyed products that do route motion through a PLC (mc-01 §F). It
  is a **new layer** the project does not have, and none of the project's claims needs
  it: M4's PLC depth is demonstrated, the F-layer is the vehicle's safety controller
  already, and M6's handshake is where the remaining PLC depth lands. Miscasting the
  **cell** PLC as onboard is not that pattern; it is its violation.
- **Edit ADR 0011 D1 to say "F-runtime group" explicitly** — **rejected**. Accepted
  ADRs are never edited in this project (CLAUDE.md §8). The cost is that D1 keeps a
  word a reader can over-read; the benefit is that the record of what was decided on
  2026-07-30, and of the boundary drawn on 2026-07-31, both survive intact — the ADR
  0012 D1 precedent exactly.
- **Leave the locus ruling in the research report and write no ADR** — **rejected**.
  mc-01 is evidence and reads as advice; the next architecture review would have found
  a recommendation and re-argued it, which is how a recommendation hardens into a
  decision without anyone deciding (LESSONS 2026-07-31). A decision with its reasoning
  attached is cheaper than a rediscovery.
- **Claim that the PLC enforces the envelope** — **rejected**, and named as an
  alternative because it is the tempting sentence rather than a considered design. The
  PLC can **notice** non-compliance and cannot **compel** it, `opcua-nodes.md` §12.6
  already says so, and a showcase that implied otherwise would be making the one claim
  in this architecture that the architecture cannot support. D5 is the answer instead.
