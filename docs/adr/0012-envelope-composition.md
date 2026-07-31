# ADR 0012: The autonomy envelope's third element, and the ADR 0011 D1 disclosures

Status:        accepted (2026-07-31). Owner-approved on that date, on the
adversarial architecture review recorded in
`docs/reports/m5-judge-architecture-review.md` (findings 4 and 3); the two
decisions below are the owner's rulings, recorded here.

What this ADR does, stated before anything else:

- It **refines ADR 0011 D3**
  (`docs/adr/0011-sensored-autonomy-architecture.md`). It does **not** supersede
  ADR 0011, and it does not supersede D3. **Exactly one clause changes**: in D3's
  opening paragraph the envelope is composed as *"a **motion enable**, a **speed
  ceiling** and a **zone permit**"*, and the words **"and a zone permit"** — that
  term and nothing else — are replaced per D1 below. The enable, the ceiling, the
  onboard closure of the navigation loop at its own rate, the mode-scoped reading
  of the M4 phrasing and the velocity-smoother consequence all stand word for
  word.
- It **discharges a duty ADR 0011 D1 imposed and the tracking files did not
  carry**, and pins two facts D1's scaling claim rests on as **unverified** (D2
  below). D1's architectural reading is unchanged: the forklift's F-runtime group
  is the vehicle's onboard safety controller.
- It **supersedes nothing, renumbers nothing and changes no gate criterion.** The
  gate order stays as ADR 0010 set it and `docs/roadmap.md` remains the live
  order. The M5 and M6 rows are untouched, and the M7 row's B4 statement is
  untouched — D2.2 discloses the substrate B4 will be demonstrated on, it does
  not weaken B4.
- **Invariants 1–13 are untouched.** This ADR exists precisely to keep
  **invariant 5** (order assignment, traffic and zone reservation belong to the
  fleet manager) and **invariant 10** (one owner per data item) intact: it removes
  from the PLC a datum the fleet manager will own at M6, rather than negotiating
  either invariant.
- **No accepted ADR is edited**; CLAUDE.md §8 forbids it. ADR 0011 keeps its text
  and its word "zone permit" forever. The forward pointer lives here and in
  `docs/roadmap.md`, on the ADR 0005, 0008 and 0011 precedent.

---

Context:

**The owner ruled both decisions on 2026-07-31**, on an adversarial review of the
M5 architecture. Two of that review's findings needed a ruling rather than an
edit, and this ADR is where they are recorded.

**The collision (review finding 4(a)).** ADR 0011 D3 gives the PLC an autonomy
envelope whose third element is a **zone permit**. At M5 that collides with
nothing: no fleet manager exists, so the PLC is the only writer of any zone
verdict. At M6 a fleet manager exists and zone reservation is its subject matter
— ADR 0010 D3, and invariant 5 in the contract — while the PLC would still be
publishing a zone permit in the envelope. That is two owners for one datum, which
invariant 10 forbids outright, and the failure is not abstract: brief m5-17 is
about to mint the envelope's node names, so the choice today is between one
sentence now and a term that means two things in the node model, the VDA 5050
subset and the station handshake at once. The project's own LESSONS rule of
2026-07-31 — that a recommendation hardens into a decision by repetition — is the
reason the cheap moment is the moment before the name exists.

**The disclosure gap (review finding 3(a) and 3(b)).** ADR 0011 D1 declared the
single hosting 1513F-1 PN a **simulation artifact** *"disclosed as one wherever
the twin is described"*. The review found that disclosure present in the ADR and
**absent from the two tracking files that restate D1 most often** —
`docs/roadmap.md` and `docs/PLAN.md`. It also found the consequence of that
artifact unrecorded anywhere: one simulated CPU hosting what the architecture
calls per-vehicle safety means the cell and vehicle chains share an execution
substrate, which the M7 criterion's B4 statement reads against.

**The scaling facts (review finding 3(c)).** ADR 0011 pins twelve external facts,
F1–F12, each to a document edition or explicitly to practice, and records F4 as
unverified rather than asserting it. Its D1 sentence *"It scales. At M6 four
forklifts each carry their own safety instance"* rests on two facts that table
does not contain. They are recorded below in the same discipline, as absences with
what would settle them, because by the LESSONS rule of 2026-07-26 an unpinned
vendor-adjacent claim ages silently — and this one sits in the document built to
forbid exactly that.

**Facts this ADR needs and does not have.** No new external fact is asserted here.
Two are recorded as **unverified**, in the F4 pattern, continuing ADR 0011's
numbering:

| # | Fact needed | Status | What would settle it |
|---|---|---|---|
| F13 | The **maximum number of F-runtime groups an S7-1500 F-CPU supports**, which bounds how many per-vehicle safety instances one simulated CPU can carry. If the bound is below four, M6's four "instances" are F-FB instances inside one group — one monitoring time, one collective signature, one common fault container — which is not the per-vehicle architecture D1 declares | recorded **unverified**, 2026-07-31 | The SIMATIC Safety Programming and Operating Manual's F-runtime-group section and the 1513F-1 PN (**6ES7 513-1FM03-0AB0**) technical data, each cited with its edition and order number per the ADR 0011 evidence discipline, **and** read back in TIA Portal against this project — the ADR 0006 rule that a tool-derived value is a design value until the tool states it |
| F14 | The **PLCSIM Advanced instance budget available to this project** — how many simultaneous simulated CPU instances the installed version and licence permit — which is what the alternative hosting (four simulated CPUs) costs | recorded **unverified**, 2026-07-31 | The S7-PLCSIM Advanced Function Manual for the **installed** version, cited by edition and order number, plus the installed licence read back in the tool. F4 already records the V6.0-and-later support list as unverified, so the manual edition must be the one this project runs, not the one already cited |

Neither fact bears on M5. Both bear on M6, where the four-forklift claim is the
gate's own subject matter, and M6 already carries an entry condition — an
owner-ruled deep-research brief before any implementation (roadmap M6 row, ADR
0010 D3 and D6(d)). That brief is the natural place to settle F13 and F14; this
ADR asks for it there and changes no criterion to say so.

---

Decision:

### D1 — The envelope's third element is a **fixed-equipment / station permit**, not a zone permit

In autonomous mode the standard program publishes, at its own cycle, an autonomy
envelope of three elements: a **motion enable**, a **speed ceiling** and a
**fixed-equipment / station permit** — the PLC's statement that **the equipment it
owns is ready for the vehicle to act on it**: the door is open, the conveyor is
ready, the charging bay is clear, the station handshake is satisfied.

**Exactly what is replaced, and exactly what is not.**

- Replaced: in ADR 0011 D3's opening paragraph, the third term of the envelope,
  the words **"and a zone permit"**. They read, from this ADR forward, **"and a
  fixed-equipment / station permit"**.
- Not replaced, and not reopened: the **motion enable** and the **speed ceiling**;
  the ruling that the navigation control loop closes **onboard the vehicle at its
  own rate**; D3's rationale against routing velocity samples through the PLC
  (invariant 9, the Nav2 progress checker, the absence of prior art); the
  mode-scoped reading of the M4 phrasing, under which *"the PLC forms all motion
  setpoints"* continues to hold for **teleoperated** mode and the M4 gate criterion
  stays closed and unchanged; and the implementation consequence that the velocity
  smoother runs closed-loop against measured odometry.
- Not a second replaced clause: D3's rationale sentence that supervision belongs
  at **order and zone level** rather than at velocity level remains true as
  written. Zone-level supervision does not leave the system — it leaves the
  **PLC**. At M6 it is the fleet manager's, which is where invariant 5 always put
  it and what VDA 5050 describes.

**Why.** Invariant 5 gives order assignment, traffic and zone reservation to the
fleet manager, and invariant 10 allows one owner per data item. A PLC-issued zone
permit would create the second owner at M6. What the PLC keeps is what is
genuinely its own under the same invariant's second sentence — fixed equipment,
its interlocks and its handshakes — so the envelope loses nothing the PLC had a
title to. Invariant 6 is untouched as well: a station permit is a **permission**
the vehicle's own control layer consumes, not an actuator command, and the fleet
manager still issues orders and reads state rather than commanding actuators.

**The consequence, recorded as ruling text rather than left to be discovered.** At
M6 a vehicle's motion is bounded by **both** a PLC station permit **and** a
fleet-manager zone reservation. These are **different data with different
owners**, answering different questions:

| Datum | Owner | The question it answers |
|---|---|---|
| Fixed-equipment / station permit | PLC standard program | *Is the equipment I own ready for you to act on it?* |
| Zone reservation | Fleet manager | *May you be here?* |

**No document, node name, message field, caption or spoken line may conflate
them**, and neither may be named with the other's word. This is the same naming
discipline ADR 0004 set for the demonstration process stop and ADR 0010 restated
for the three ways to say "stop".

**What this leaves to the interface layer.** The envelope's node names, their
group and their access rights remain `docs/interfaces/opcua-nodes.md`'s under
invariant 10, exactly as ADR 0011 left them. This ADR rules the **datum**, not the
name. The one constraint it does impose on m5-17 is negative: the node minted for
the envelope's third element must not be named for a zone, because the word now
belongs to another layer's datum.

### D2 — The ADR 0011 D1 disclosures are landed, and its two scaling facts are recorded unverified

**D2.1 — The artifact sentence lands in the tracking files.** `docs/roadmap.md`
and `docs/PLAN.md` each gain **one sentence** stating that the single 1513F-1 PN
hosting the vehicle's onboard safety controller is a **simulation artifact**, not
an architectural claim that one F-CPU guards a fleet. D1's promise was
*"wherever the twin is described"*; these are the two files that describe it most
often and carried the reading without the disclosure.

**D2.2 — The shared execution substrate, recorded as a consequence and not as a
claim.** Because one simulated CPU hosts what the architecture calls per-vehicle
safety, **the cell chain and the vehicle chain share an execution substrate in
simulation**. The M7 criterion's boundary statement **B4** — *"the vehicle chain
does not depend on the cell"* — therefore **does not hold at the simulation's
execution layer**, even though it holds architecturally: a CPU STOP, a download or
an F-runtime-group fault takes both chains at once. The demonstrable half of B4
— a demand on one chain not propagating to the other — is unaffected and remains
demonstrable.

This is disclosed **in advance of the M7 run rather than in its question period**.
It is **not** a criterion change: B4 stands exactly as `docs/roadmap.md` words it,
and the M7 brief inherits this sentence as a statement it must make when the run
is narrated. Removing the limitation rather than disclosing it would require
separate simulated CPUs per vehicle, which is F14's question and is not ruled
here.

**D2.3 — F13 and F14 are unverified, and "it scales" travels with them.** Until
both are pinned per the table above, ADR 0011 D1's sentence *"It scales"* is
quoted **together with the two unknowns**, never alone as a settled property. The
M6 deep-research brief that the roadmap already requires as that gate's entry
condition is the place to settle them, before any M6 implementation reads four
per-vehicle safety instances as a given.

---

Consequences:

What becomes harder:

- **Two permits with two owners now exist on one screen.** Every M6 document has
  to keep the station permit and the zone reservation apart in name and in
  sentence, and the failure mode is a plausible-sounding conflation rather than an
  obvious error.
- **A word is retired that an accepted ADR keeps forever.** ADR 0011 D3 will read
  "zone permit" for as long as the repository exists, because accepted ADRs are
  never edited. Every reader who lands there must be carried here by the pointer
  in this ADR and in `docs/roadmap.md`, and any later document that quotes D3's
  envelope must quote this refinement with it.
- **The station permit needs a definition before it can be formed.** Which
  equipment it covers, at what granularity (per station, per equipment item), and
  what "ready" means for each are open and land at m5-16 (formation, PLC) and
  m5-17 (nodes, interface). The datum is ruled; its shape is not.
- **The four-vehicle claim now travels with two named unknowns.** That is the
  point — but it means anyone quoting D1's scaling sentence carries F13 and F14
  with it, and the M6 entry brief inherits an answer it must actually produce.
- **The M7 narration gains a required sentence.** B4's substrate disclosure has to
  be spoken and written when the run is recorded, which is one more thing the
  showcase script must not omit.

What becomes easier:

- **Invariant 10 stays a rule rather than a negotiation at M6.** The ownership
  seam is drawn before either side is built, so the fleet manager arrives owning
  zone reservation with no counterpart to reconcile, and no M6 traffic deadlock is
  debugged across an ownership boundary nobody drew.
- **m5-17 mints one name with one owner.** The interface brief inherits a ruled
  datum instead of an ambiguity it would have had to rule for itself.
- **The envelope maps onto the picture VDA 5050 already tells.** The fleet's zone
  reservation and the PLC's station handshake are two things M6 must demonstrate
  anyway; the envelope now names one of them rather than duplicating the other.
- **The PLC's role in autonomy is still sayable in one line**, and is now true at
  M6 as well: *the PLC owns the enable, the ceiling and the readiness of its own
  equipment; the fleet manager owns the traffic; the vehicle closes the loop.*
- **The D1 disclosure now travels with the files a reader quotes**, so the
  strongest wording in the M5 architecture — "onboard safety controller" — stops
  being the closest thing in the repository to an overclaim.

What this ADR does **not** decide:

- **The F-I/O question and everything hanging on it.** The review's finding 1 — the
  tension between the M5 criterion (a) and D2's named fallback — is **deliberately
  left open pending m5-03's verdict**, whose §7 is still empty. Nothing here weighs
  on it, and no wording here may be read as anticipating it.
- The station permit's **node name, group, access rights, granularity and
  formation logic** (m5-17 and m5-16, under invariant 10).
- The **enforcement-locus wording** of review finding 4(b) and the **public README
  wording** of finding 4(c). Both are real residues; neither is one of the two
  decisions ruled on 2026-07-31, and `README.md` is outside the authoring agent's
  write scope in any case.
- **How M6 actually hosts four safety instances** — four F-runtime groups on one
  simulated CPU, or four simulated CPUs. That is precisely what F13 and F14 settle.
- Anything about **claims**. ADR 0011 D5 is untouched and binding: this ADR makes
  and implies **no achieved PL, Category, SIL or PFH**, and nothing here is a
  statement about any safety performance level.

Relationship to the ADRs this one stands on, each stated:

| ADR | Relationship |
|---|---|
| **0011** sensored autonomy architecture | **Refined, not superseded.** **D3**: one clause — the envelope's third element — is replaced by D1 here; the rest of D3 stands word for word. **D1**: its reading is unchanged; its disclosure duty is discharged and its two scaling facts are pinned as unverified by D2 here. **D2** (the F-I/O path and its fallback), **D4** (the monitoring plane) and **D5** (the claim boundary) are untouched |
| **0010** milestone restructure | **D2**'s statement of M5's content, **D3**'s M6 subject matter — the fleet manager, VDA 5050 and traffic — and **D6(d)**'s open question about M6's staging are all unchanged. The gate order, the numbering and the D7 landing points are untouched |
| **0009** early cell-scope safety on the twin | Untouched. Its **D3** coupling architecture and **D5** wording discipline carry forward unchanged; the station permit is process data on the process plane and touches neither |
| **0008** commissioning gate and HMI layer | **D3**'s ruling that process interlocks in the standard program implement **no SRS function** governs the station permit as well: it is standard-program process logic, and it is not SF-05, SF-06, SF-07 or any other safety function, however much a station interlock resembles one |
| **0005** bridge layer | The bridge's **no-logic** contract is untouched. The envelope, third element included, is **formed in the PLC and carried by the bridge**, never computed in it |
| **0001** the invariants | **Invariants 5, 6 and 10** are the reason this ADR exists. None of the thirteen is amended, and this ADR would be unnecessary if D3's third element had never claimed a datum invariant 5 assigns elsewhere |

---

Alternatives:

- **Leave "zone permit" in place and separate the two owners at M6** — rejected.
  The collision is cheap to resolve now, while no node bears the name and no
  consumer reads it, and expensive once the fleet manager, the VDA 5050 subset and
  the station handshake all reference a term that means two things. Deferring it
  would also mean m5-17 minting a name this ADR would have to retire.
- **Let the fleet manager write the PLC's zone permit at M6** — rejected. It is the
  other branch of the same collision, named in the review as such: it inverts the
  direction of authority for that datum (invariant 4 makes the PLC the server and
  the fleet manager the client, and a client writing the server's verdict makes the
  PLC a store for a fleet datum), and it leaves the vehicle consuming a zone verdict
  whose true owner is invisible in the node model.
- **Drop the envelope's third element entirely** — rejected. The PLC's legitimate
  say over its own fixed equipment would vanish from the envelope, and it would
  have to be reintroduced at M6 anyway when the stations arrive — at which point
  the envelope would be renegotiated in the middle of the gate that depends on it.
- **Edit ADR 0011 in place** — rejected. Accepted ADRs are never edited in this
  project (CLAUDE.md §8). The cost is that D3 keeps a word this ADR retires; the
  benefit is that the record of what was decided on 2026-07-31, and of what the
  review found on it, survives intact.
- **Record "it scales" as settled and pin F13/F14 later** — rejected. ADR 0011's own
  evidence table pins twelve facts and marks the thirteenth unverified rather than
  asserting it; a scaling claim asserted where every neighbouring claim is pinned
  is the failure the LESSONS rule of 2026-07-26 exists to prevent.
