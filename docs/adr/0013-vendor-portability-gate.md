# ADR 0013: Vendor portability is a gate of its own, after the main line

Status:        accepted (2026-07-31). Owner-approved on that date; the five
decisions below are the owner's rulings, recorded here.

What this ADR does, stated before anything else:

- It **places the Beckhoff/TwinCAT portability work as a gate of its own, after
  M6 and M7** (D1). It **assigns that gate no number**: `docs/roadmap.md` is the
  single source for gate numbering (LESSONS 2026-07-30), and the number, the row
  and its final criterion wording are a separate roadmap brief's, taken once M6
  and M7 are settled.
- It **supersedes nothing and renumbers nothing.** The gate order of ADR 0010
  (`docs/adr/0010-milestone-restructure-forklift-first.md`) stands, M0–M7 keep
  their numbers, and **no existing gate criterion is changed, weakened or
  widened.** M5 stays the current gate.
- It **rules on the open items of the research**
  (`docs/reports/mv-01-beckhoff-portability-research.md` §G): gate placement
  (§G item 1) is ruled here; mirror scope is ruled to the extent D2 states it;
  the directory shape (§G item 2), the endpoint-liveness guard (§G item 4) and
  the TE9100 watch (§G item 5) are **not** ruled here and are named as open.
- It **discharges the ADR the research required before implementation** (§F.7)
  only in part, and says so: §F.7 items 3 and 4 — the standard-program-only
  scope and the startup-selection ruling — are D2 and D4 here. §F.7 items 1 and
  2 — the TwinCAT namespace URI as read from the installed server, and the
  chosen symbol layout with its resulting interface-node path — are **tool-derived
  identifiers and are not recorded in this ADR**, because no tool has spoken.
  They belong to the ADR written after the stage-0 probe (D5), on the ADR 0006
  discipline.
- **Invariants 1–13 are untouched.** The research walked all thirteen (§F.6) and
  found none needing change; that finding is stated here, not re-walked. Gate
  order is not an invariant.
- **No accepted ADR is edited**; CLAUDE.md §8 forbids it. ADR 0006 remains true
  of the Siemens interface and stands beside this ADR rather than under it.

---

Context:

**The evidence base is `docs/reports/mv-01-beckhoff-portability-research.md`**
(report mv-01, 2026-07-31). Every external vendor claim below is cited to that
report rather than restated: it carries the sources, the per-claim verification
grade (`[fetched]` / `[snippet]`), the verification date **2026-07-31**, and the
pinned document version where one exists (TF6100 manual
`TF6100_TC3_OPC_UA_Server_EN` **v1.4.0, 2025-09-16**). Two owner scope
corrections landed during that research and are already incorporated in it: the
two controllers never run at the same time, and the controller is selected at
system startup.

**What forced a gate rather than a work item.** Three findings of mv-01, and one
project rule:

1. **The safety mirror has no released execution path.** The TwinSAFE logic
   simulator **TE9100** is at *"product announcement | estimated market release
   on request"* (mv-01 §B.2, `[fetched]` 2026-07-31). A product at announcement
   status carries no date this project can plan against.
2. **The standard-program mirror needs nothing that does not exist today.** The
   contracted programs use no process image and no fieldbus on either vendor, so
   no simulated I/O, no EtherCAT master and no TE1111 is required (mv-01 §A.1);
   the ported corpus falls entirely into "ports unchanged" and "mechanical
   token-level edits" (mv-01 §E); and the runtime form the owner's machine can
   host — the user-mode runtime, non-real-time, 1 ms minimum cycle — is inside
   this project's 20 ms cadence (mv-01 §A.1, §A.4).
3. **The clients need no vendor knowledge.** What differs between the two
   controllers — the endpoint, the two namespace URI values and the browse path
   from `Objects` down to the interface node — is **already configuration data**
   in both the bridge and the HMI, not code (mv-01 §C.3, §F.3).
4. **The project's own rule:** a gate closes on observable behaviour, and a gate
   is not started before the previous one is verified (CLAUDE.md §6). Work whose
   completion may have to wait on a vendor's unannounced release therefore
   cannot sit on the critical path without putting that rule at risk.

**Why the sequencing matters more than the size.** The mirror is ≈6–9 briefs and
3–4 owner tool sessions (mv-01 §F.5). That is small enough to fit anywhere and
large enough to disturb whatever it is placed inside. The decisive property is
not size but **dependency on a date nobody controls**.

**One reading recorded, not decided.** mv-01 §F.6 notes that on Beckhoff the
endpoint is served by a separate server process coupled to the runtime on the
same host. That is the server side of the same boundary — a vendor implementation
detail of "the PLC" — and invariant 4 stands unchanged in direction and in force:
both clients remain clients, and nothing in this proposal listens.

---

Decision:

### D1 — Vendor portability is a gate of its own, placed after M6 and M7

Not inside M5, and not between M5 and M6. The gate sits **after the main line**:
after the fleet gate and after the LLM operations gate with its end-to-end
demonstration.

The reason is the one that survives argument: **the gate must be free to wait.**
The safety half of the mirror depends on TE9100, whose release date is "on
request" (mv-01 §B.2). A gate placed between M5 and M6 would put a vendor's
unannounced schedule in front of the fleet gate, the LLM gate and the recorded
demonstration behind them. Placed after the main line, waiting costs the project
nothing: the demonstrations that carry the project's architectural claim are
already recorded and closed by the time this gate opens.

**This gate is given no number here.** Numbering, the roadmap row and the final
criterion wording are a separate arch-docs brief, written once M6 and M7 are
settled, because `docs/roadmap.md` is the single source for gate numbering and
every other table follows it via a brief (LESSONS 2026-07-30).

### D2 — Scope: the full mirror, standard program first, safety when it becomes possible

**The gate's ambition is the full mirror.** Its **closing criterion is written
entirely over the standard program**, and the safety mirror **widens the
demonstration without conditioning the closure**.

**The closing criterion, in the form the roadmap brief carries it.** The gate
closes when all five are demonstrated and captured in committed evidence
(whether the gate additionally carries a showcase recording in ADR 0007's sense
is the roadmap brief's question, not this ADR's):

- **(a)** The **same byte-identical bridge and commissioning HMI** establish
  sessions against both controllers, differing between the two sessions only in
  the configuration values those clients already hold as data — the endpoint, the
  namespace URIs and the browse path to the interface node — and the existing
  connect-conformance instrument passes against **each** server: every contracted
  standard-program node resolved by namespace URI and relative browse path,
  BrowseName, data type and access rights verified, **two evidence files, one per
  vendor**.
- **(b)** The **forklift scenario procedures** that were run for M4 —
  `plc/forklift/SPEC.md` §11 T5.1–T5.6 — run to their recorded outcome against
  the TwinCAT controller in **its own session**, with the Siemens evidence
  **kept beside** the new set rather than replaced, and each evidence file
  stating the environment that produced it, including the qualifier
  *"user-mode runtime, no real time"* on the TwinCAT session (LESSONS
  2026-07-27, mv-01 §A.4).
- **(c)** The controller in force is **selected at system startup, immutable for
  the session** (D4), and the **server-reported** controller identity — read from
  the server's own standard status nodes, never a configuration label — is
  visible throughout every recorded run, so a viewer can tell the two sessions
  apart without being told which is which.
- **(d)** The **drift check runs and passes** on both implementations against
  `docs/interfaces/opcua-nodes.md` (D5).
- **(e)** The public claim landed in the repository states the **asymmetry**: the
  F-safety layer exists on the Siemens controller only, and the reason, with the
  TE9100 status quoted and dated.

**The safety mirror.** If, when the gate opens, TE9100 is released and its own
documentation supports the mirror, the safety layer is added to the gate's
demonstration and the evidence widens accordingly — its own brief, its own
feasibility probe, TE9100's documentation quoted and dated, on the
`FIO-FEASIBILITY` pattern applied to the second vendor. **It is not a criterion
item and no criterion item names it.**

**The named fallback, and the criterion tested against it in the same breath.**
The fallback is: **TE9100 is still unreleased when the gate opens.** Taken item
by item, with the fallback in force:

| Item | Under the fallback |
|---|---|
| (a) | **Satisfied.** The conformance set is the standard-program contract. The four `Forklift/Safety/` mirror nodes are simply **absent** from the Beckhoff server, which is a **tolerated server state today**: the HMI declares that group optional and greys it rather than guessing a value (mv-01 §B.3, citing `hmi/README.md` and `hmi/config.yaml`). **No client change is needed for the absent case** — which is precisely why the construction works. |
| (b) | **Satisfied.** T5.1–T5.6 are standard-program scenarios. The safety scenarios (T6, AT-\*) are **not in the criterion** and are not run against Beckhoff; the evidence says why. |
| (c) | **Satisfied.** Startup selection and server-reported identity are vendor-neutral and safety-neutral. |
| (d) | **Satisfied.** The drift check reads the node model as its reference; a group absent on one server by ruled scope is a recorded exclusion, not a drift finding. |
| (e) | **Satisfied — this item is the fallback stated in public.** |

The fallback therefore **leaves the criterion intact rather than voiding it**,
and it is **inert by construction**: taking it requires building nothing,
removing nothing and editing no document, because nothing was written on the
assumption that TE9100 ships (ADR 0009 D4's rule that a fallback needing a
document edit to take effect is not a fallback).

**What is not claimed under the fallback:** no TwinSAFE or FSoE capability, no
safety rating, no achieved PL — nothing safety-related exists on the Beckhoff
side to claim. The Beckhoff side is not the easier one; today it is harder than
the still-open Siemens case (mv-01 §B.2).

### D3 — The claim, stated exactly

**Not "identical tags and addresses on both PLCs".** That phrase has no referent:
**neither implementation uses addresses at all** — the Siemens build uses
optimized DBs with no absolute offsets, and the TwinCAT mirror would use
symbolic GVL access (mv-01 verdict, §D). A claim with no referent is worse than
a modest one; an industrial reader sees through it immediately.

**The claim this project makes is:**

> The **contract below the interface node is identical** — the same relative
> browse paths, the same BrowseNames, the same data types, the same access
> rights, the same start values, the same handshake and watchdog semantics — and
> portability is **demonstrated, not asserted**: the same byte-identical bridge
> and commissioning HMI, and the same scenario procedures, run against the
> Siemens controller in one session and the Beckhoff controller in another, with
> the controller selected at startup and fixed for the session, and both evidence
> sets kept.

Three properties are recorded as part of the claim, because they are what makes
it true rather than aspirational:

1. **The two clients need no code-level vendor knowledge**, and the research
   found no point at which they must branch on vendor (mv-01 §F.3).
2. **What differs is already configuration in both clients** — endpoint, the two
   namespace URI values, the browse path elements from `Objects` to the interface
   node (mv-01 §C.3). Vendor-specific *values*, not vendor-specific *logic*.
3. **One document owns the contract**: `docs/interfaces/opcua-nodes.md`, under
   invariant 10, unchanged. Both vendor specifications are derived documents that
   cite it; neither may introduce, rename or retype a node.

Both namespace URIs are **tool-derived on both vendors** and cannot be made
equal — the Siemens form is ADR 0006's finding; the TwinCAT form is documentation
-grade and unverified until stage 0 (D5). Where exact matching is impossible, the
quirk stays out of the client by ADR 0006 D4's rule, which is vendor-neutral and
stands: clients browse by URI and by configured path, never by index and never by
assumption. **No vendor string appears in client code.**

### D4 — The controller is selected at system startup and is immutable for the session

The two controllers **never run concurrently**. The system must be *capable* of
either; exactly one is active per session; the selection is made at startup and
does not change while the system runs.

**Mid-run switching is out of scope by owner ruling (2026-07-31)**, and the sound
reason is recorded rather than merely asserted: **a controller switch is a
controller restart.** The newly selected controller starts from its own state —
latches, edge memories, heartbeat one-shots, monitored-reset arming — and
CLAUDE.md §9 already forbids resuming from stale sequence state and forbids
automatic resume after a stop. No switching flow, state carry-over or in-flight
hand-off is designed, now or later, without a new owner ruling.

**Which component owns the selection datum is not decided here.** It is an
implementation question for the gate's own briefs. What binds those briefs is
**invariant 10**: the selection is one datum with exactly one owner, documented
before it is consumed, and no consumer recomputes or re-derives it. The
controller *identity displayed to the operator* is a separate datum with a
different owner — the server's own reported identity, displayed and never
configured — and D2(c) requires the displayed value to be that one.

### D5 — The stage-0 owner probe is a hard precondition, and the drift check is a deliverable

**D5.1 — Nothing in the design may be built before the stage-0 probe runs.** The
probe is an owner-in-tool session (mv-01 §F.5 stage 0) that reads back, from an
installed TwinCAT, the facts the research could only take from vendor
documentation. At minimum, and stated as unread tool facts:

| Unread fact | Why it is a precondition |
|---|---|
| **The namespace URI the server actually serves**, its derivation, and whether it can be pinned | The documented form embeds the **machine host name** (mv-01 §C.2, `[snippet]`, **unverified**). If that holds on the installed version, **renaming the Windows computer becomes a breaking change** and the machine name joins the contract-change discipline. |
| **The exact BrowseName strings** of struct-member nodes, and whether the interface node can be the device node or must sit under it | The contract is browse paths and BrowseNames. A path written from documentation is a design value, not a fact. |
| **Whether the OPC UA server serves the user-mode runtime** the owner's Hyper-V/WSL2 machine requires, and whether the toolchains co-reside | mv-01 §A.4 records install-level co-residency as **unverified**; the kernel-mode runtime is documented as unable to start under Hyper-V. |
| **The OPC UA types the server reports** for the contracted PLC types, and whether the clients' generic write form is accepted | Expected, not asserted (mv-01 §C.4). |
| **Which licence IDs the activation demands** | Recorded as the tool asks, not assumed. The project runs on **7-day trial licences generated in the engineering environment, renewable per the vendor's licensing pages** (verified 2026-07-31, mv-01 §A.3). These are **trial licences for commercial products** — the PLC runtime and the OPC UA server are licensed functions — and **no document, README or recording produced under this gate calls them "free"**. |

**This is the ADR 0006 failure class.** `urn:amr-agent:cell:plc` was a
tool-derived identifier taken from a specification, and it could never exist on
the tool that had to realise it. The probe exists to prevent its repeat on the
second vendor, and the rule it enforces is the one ADR 0006 produced: **a
tool-derived value is a design value until the tool states it.** A client
configuration or a vendor specification authored before the probe would repeat
that failure verbatim.

**The probe's output is a record with dates**, and the tool-derived constraints
it establishes are recorded in **their own ADR** (mv-01 §F.7 items 1 and 2),
written after the probe and before any vendor specification or client
configuration. This ADR does not pre-empt it and does not guess its values.

**D5.2 — A mechanical drift check between the two implementations and the
contract is a deliverable of this gate.** Because the gate now sits after M6, the
node model will have **grown underneath it**: M6 adds the fleet-facing station
handshakes. Every addition widens the mirror's catch-up, so the drift check stops
being a safeguard and becomes load-bearing (mv-01 §F.5, the cost it attaches to a
late landing). It is therefore **a deliverable, not an intention** — a mechanism
that runs and fails, not a review habit.

Two properties bind it; **this ADR requires the check and does not design it.**
It **reads `docs/interfaces/opcua-nodes.md` as the reference and fails toward
it** — it may not invent a second owner of any contracted value (invariant 10) —
and it **covers both implementations**, so drift between the two vendors and
drift from the contract are the same finding. Candidate mechanisms are sketched
in mv-01 §F.2; which one is built is the gate's own brief.

---

Consequences:

What becomes harder:

- **The gate waits behind two large gates.** The portability claim is absent from
  the M5, M6 and M7 showcases and lands only afterwards, so the intermediate
  public artifacts describe a single-vendor system. That is the price of the
  placement and it is accepted.
- **The contract keeps moving underneath the mirror.** M6's station handshakes
  land before the mirror is built. D5.2 is what makes that survivable, and it
  converts a nice-to-have into a required deliverable — the gate carries one more
  piece of tooling than it otherwise would.
- **Owner tool time is a real constraint.** Three to four in-tool sessions
  (mv-01 §F.5), none of which an agent can perform, all of which fall after M7's
  commissioning work.
- **A second toolchain joins the machine.** Co-residency with TIA Portal,
  PLCSIM Advanced and WSL2 is unverified until stage 0, and the kernel-mode
  runtime is documented as unavailable under the hypervisor the machine already
  runs permanently — so the mirror is bound to the non-real-time runtime form and
  every measurement it produces carries that qualifier.
- **The asymmetry has to survive into public artifacts.** "Standard program only,
  safety Siemens-only, and here is why" must appear in the README, the evidence
  files and the recording — the same wording discipline ADR 0009 D5 imposed on
  the safety claims, now applied to a scope boundary.
- **Two vendor-derived identifier sets now exist to keep honest.** ADR 0006's
  Siemens derivation and the TwinCAT derivation the probe will record; if the
  host-name coupling holds, the **computer name** becomes contract, which is a
  stranger constraint than an interface name and easier to break by accident.

What becomes easier:

- **The main line is unblocked, permanently.** No gate on the critical path waits
  on a vendor announcement. If TE9100 never ships, this gate still closes.
- **The criterion cannot be voided by a vendor's schedule, and that construction
  is deliberate.** The closing criterion is written entirely over the standard
  program; the safety mirror widens the demonstration and conditions nothing. This
  is a direct response to the failure of ADR 0011 D2, where a named fallback was
  asserted to change no gate criterion and an adversarial review found it could
  not satisfy the criterion at all (LESSONS 2026-07-30). **The rule the failure
  produced — a named fallback is tested against the gate criterion in the same
  breath as it is named — is discharged in D2's table, item by item.** A later
  reader should see the construction as chosen, not accidental: had the safety
  mirror been made a criterion item with a conditional clause, this gate would
  have inherited an unschedulable dependency in its own exit condition.
- **The contract is at its most stable when the mirror is built.** After M6 the
  fleet-facing node set exists rather than being anticipated, so the mirror
  copies a finished contract instead of chasing one.
- **The claim gets stronger, not weaker, by being stated exactly.** "The same
  unmodified clients pass the same procedures against two vendors' controllers"
  is demonstrable, recorded and checkable; "identical addresses" was neither true
  nor meaningful.
- **The probe pays for itself before it costs anything.** Stage 0 is one owner
  session that turns every documentation-grade claim in mv-01 into a dated
  record, and it happens before a single configuration value is written.

What this ADR does **not** decide: the gate's **number**, its roadmap row and the
final wording of its criterion (a separate arch-docs brief, after M6 and M7);
whether the gate additionally carries a showcase recording in ADR 0007's sense;
the TwinCAT namespace URI, the symbol layout and the interface-node path (D5, the
post-probe ADR); the directory shape for the second vendor's sources (mv-01 §G
item 2); whether the demo cell is mirrored in addition to the forklift cell
(§G item 3); the both-endpoints-alive launcher guard (§G item 4); the TE9100
watch (§G item 5); which component owns the selection datum (D4); the drift
check's mechanism (D5.2); and any implementation detail, configuration value or
file layout of any kind.

---

Alternatives:

- **Inside M5** — rejected. M5 already carries the safety scanner into the
  F-blocks, SLAM, Nav2, HMI v2 and a recorded showcase. Adding a second vendor
  would blur what the gate demonstrates and raise the risk of the project's
  heaviest gate, and the mirror depends on nothing M5 adds. Worse, it would
  immediately trail M5's own node additions — the `Forklift/Safety/` group lands
  there, and the mirror must then deliberately **not** serve it.
- **Between M5 and M6, waiting for TE9100** — rejected. It makes a vendor's
  unannounced schedule into this project's schedule and blocks the fleet gate,
  the LLM gate and the recorded end-to-end demonstration behind a product at
  announcement status.
- **Between M5 and M6, scoped to the standard program only** — rejected, though
  viable, and it was the owner's first instinct. It spends a slot on the critical
  path for work that gains nothing from being early: the contract is **more**
  stable after M6, not less, so the same briefs would do the same work against a
  moving target and delay three gates for the privilege.
- **Making the safety mirror a conditional criterion item** ("closes when the
  standard program mirrors and, if TE9100 has shipped, the safety layer too") —
  rejected, and worth writing down because it is the tempting shape. A criterion
  whose meaning depends on a vendor's release date is not a criterion; it is two,
  and the project would not know which one it was working against. This is the
  ADR 0011 D2 failure pattern in its criterion-side form. D2 puts the whole
  criterion on the standard program and lets the safety mirror widen the
  demonstration instead.
- **Claiming identical tags and addresses on both PLCs** — rejected: the phrase
  has no referent, since neither implementation uses addresses at all (mv-01 §D).
  D3 states the stronger and true claim instead.
- **A parallel low-priority track with no gate** — rejected. Without a gate there
  is no closing criterion, so the mirror would be "done" whenever someone said so,
  and the drift check would have no deadline to be finished by. This project
  judges completion by observable behaviour; that requires a gate.
- **Recording the TwinCAT namespace URI and symbol layout in this ADR from the
  vendor documentation** — rejected: ADR 0006's failure class exactly. Those
  values are read back from an installed tool at stage 0 and recorded in the ADR
  written after it.
