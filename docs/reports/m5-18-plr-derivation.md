# Report m5-18 — PLr targets for the M5 functions, and the claim boundary landed

```
brief:               docs/briefs/m5-18-plr-derivation.md
status:              done
files_changed:       [docs/safety/PL-SCENARIOS.md, docs/safety/SRS.md,
                      docs/safety/TWIN-DEMO-MAP.md]
invariants_touched:  none. Invariants 1, 2, 7 and 10 constrain the new text and
                     are cited in it (SC-14's network row and its validation
                     observation (c) are invariant 1 written in speed units;
                     SF-10 and SF-11 coin no mirror node under invariant 10).
                     No ADR proposal is raised.
open_questions:      six, listed below; two are requests for files outside
                     docs/safety/
next_suggested:      verifier pass over docs/safety/, then the request in open
                     question 1 (plc/forklift-safety/SPEC.md §1.2 N7) as a
                     one-line plc brief.
```

---

## What this report is

The brief's edits were made by an agent that was lost to a container suspension
after its edits and before any verification or report; they are committed as
`b87d1bf`, labelled `wip`. This report is the verification of that commit
against the brief's `done_when`, plus the fixes the verification found. The
working tree carries the fixes; nothing is committed here.

**Inherited** below means the committed work already satisfied the item and was
left alone. **Fixed** means this session changed it.

## done_when, item by item

### 1. The three M5 functions each carry an S/F/P derivation with a PLr — inherited, one correction

`SC-13` (two-scanner protective stop and the measured residual), `SC-14`
(safely limited speed, with its speed source stated) and `SC-15` (SS1
sequencing, as a single-fault scenario) are in PL-SCENARIOS' house pattern —
hazard paragraph, S/F/P rows with the arguable direction named, PLr, covering
SF, architecture, network, validation test, maps-to — and all three derive
**PLr d**. The ISO 13849 discipline holds:

- SC-14 and SC-15 **inherit** S, F and P from the demand scenario each acts on
  (SC-13 and SC-05) rather than re-deriving them, and say so in the rows
  themselves (LESSONS 2026-07-27, fault scenarios).
- Neither takes F from a fault rate. §1.2 was extended to name the four
  disguises the document now contains — SC-03's wire-break rate, SC-11's
  coincidence rate, SC-14's ceiling-violation rate, SC-15's brake failure rate
  — and rejects all four.
- SC-13 names **SF-03** as its covering function and then says plainly that
  SF-03 does **not** cover the residual, with the hazard inside the residual
  held by SF-10. That is the SC-11 shape: the PLr belongs to the hazard, not to
  the function in the title.
- No gap is closed by re-arguing a parameter. Where SC-13's P would go to P2
  (a person committed between load and rack upright), the response routes to
  SC-04 and to a change in the machine, exactly as SC-01/05/07/11 do.

**Fixed — SC-13's hazard paragraph double-counted R1.** It read that the load
costs 39.9° "and at close range a **further** 5.0° … stands behind the
carriage (R1)". R1's arc is 169.4–174.4°, which lies **inside** R3's
164.5–204.4°: while a load is present R1 adds nothing to the sector. The
paragraph now says R1 lies inside the arc, adds nothing to it while loaded, is
the part that survives when the load does not, and closes at 3 m.

**Fixed — SC-13's stimulus was ambiguous.** "pallet on the tines at rest
travel" reads as a stationary vehicle in a test whose next clause has the
vehicle travelling. It now says "with the carriage at **zero travel**, the
condition the residual is measured at", which is what the evidence table's
0.00 m row means.

### 2. The measured residuals as exposure qualifiers, mitigation as risk reduction — inherited

- **R3 (39.9°, bearings 164.5–204.4°, 30.0° of it the pallet)** is the subject
  of SC-13, cited to `agv/forklift/EVIDENCE_SENSOR_COVERAGE.md`, and it drives
  the derivation rather than decorating it: F2 is explicitly the person's
  exposure and explicitly *not* the frequency of load occlusion.
- The mitigation is written as risk reduction: *"The reduced field plus creep
  speed is a risk reduction and is written down as one. It does not make the
  sector visible, it does not shorten it, and no sentence in this project may
  say that it does."* The same sentence is mirrored into SRS SF-03's new
  **Coverage boundary** row.
- **R8 (21.8 % of the rear device's own rays)** is handled correctly and
  honestly: the evidence says R8 costs the pair **no** coverage, so it enters
  as an exposure qualifier on *that device's field geometry* and is stated as
  not being a qualifier on this hazard's derivation. Claiming otherwise would
  have inflated the residual.
- Both figures were checked back against the evidence file and match it
  (R3 39.9°/30.0°/164.5–204.4°; R1 5.0° at 2.0 m/169.4–174.4°/closes at 3.0 m;
  R8 60 of 275 rays = 21.8 %).

### 3. The ADR 0011 D5 non-claim list landed in SRS.md — inherited

Landed as **SRS §5.1**, inside §5 *"What this project cannot claim"* — the
section that carries the PL/Category target line itself, so a reader of the only
place in the SRS where a PL figure appears cannot avoid it. All seven items are
reproduced, plus the "no acceptance is claimed" paragraph (TIA safety acceptance
test, program signature). Checked item by item against ADR 0011 D5: faithful,
with item 7 correctly specialised to the one place a datasheet figure appears in
this repository (SC-13's scanner class). PL-SCENARIOS §0 points at it and does
not restate it, which is the right way round.

### 4. The "Category 3 is claimed" grep-bait — inherited in PL-SCENARIOS, fixed in TWIN-DEMO-MAP

The verb was swept through PL-SCENARIOS: §1.3, §3.1, §3.3, §3.4, SC-03's
preamble and SC-09's architecture row now all read *target* / *targeted at* /
*specified on*. A whitespace-normalised sweep of all three safety documents for
`is claimed` / `are claimed` / `is a claim` leaves eight hits, each read:

| Hit | Verdict |
|---|---|
| "No fault exclusion is claimed for the wiring" (SC-03) | negation, legitimate |
| "No fault exclusion is claimed for the brake or the drive" (SC-15) | negation, legitimate |
| "P1 is claimed on the layout precondition …" (SC-05) | a risk-graph *parameter*, not an achieved architecture; legitimate |
| "**No PL is claimed**, and PLr b is therefore not met" (SC-06) | negation, legitimate |
| "no PL is claimed" (SRS SF-04 honesty row) | negation, legitimate |
| "No acceptance is claimed either" (SRS §5.1) | negation, legitimate |
| "no timing is claimed" (TWIN-DEMO-MAP AT-07 (a)) | negation, legitimate |
| "SC-03 is the single-fault scenario **Category 3 is claimed for**" (TWIN-DEMO-MAP §2, SF-01 row) | **grep-bait, survived the sweep in a second file — fixed** |

**Fixed:** that row now reads *"the single-fault scenario the Category 3
**target** exists for"*, matching PL-SCENARIOS §3.1 word for word. **Also
fixed:** TWIN-DEMO-MAP NC-3 opened *"Category 3 is a claim about single
faults…"*; it now reads *"A Category 3 target is a requirement about single
faults…"*, matching the re-verbed PL-SCENARIOS §3.4. The sweep that produced
the committed work had been bounded to one file; per LESSONS 2026-07-29, the
subject is swept, not the file the phrasing was remembered from.

### 5. Gate-order attributions — landed, but the attribution itself was wrong; fixed

All three documents gained an "as amended by ADR 0013" clause with
`docs/roadmap.md` named as the live source. The clause as written said ADR 0013
*"places the vendor-portability gate **M8** after M6 and M7 and assigns it no
number of its own"* — which names a number in the same breath as denying one,
and attributes to the ADR a number the ADR explicitly refused to assign
(ADR 0013 preamble; `docs/roadmap.md` lines 66–70: *"this document assigns the
number M8 here, because this document is the single source for gate
numbering"*).

**Fixed in all three documents** (four sentences): ADR 0013 places the gate
after M6 and M7 and deliberately assigns it **no number**; `docs/roadmap.md`
numbers it **M8** as the single source for gate numbering and settles any
disagreement. This is LESSONS 2026-07-30 (roadmap.md is the single source for
gate numbering) applied to the attribution rather than only to the order.

### 6. No achieved PL, Category, SIL or PFH anywhere for this project's chain — inherited, verified by sweep

Whitespace-normalised sweeps of all three documents for `PFH`, `SIL n`,
`achieved`, `achieves`, `meets PL`, `reaches PL`, `certified`, `TÜV`,
`CE mark`, and for every occurrence of `Category 3`, return only:

- negations and non-claim list items;
- `Category 3, PL d` always prefixed *"SRS §5 target:"* in every scenario
  architecture row, and headed *"Target (SRS §5)"* in the §4 mapping table;
- **one** PFH figure in the whole document set — `8×10⁻⁸ h⁻¹` in SC-13 — which
  is the modelled SICK microScan3 Pro class from ADR 0011 F8, carrying the D5
  guard sentence in the same cell and repeated in §5's closing list. That is
  the brief's permitted form, and it is the only datasheet figure quoted.

**Fixed, an honesty gap rather than a claim:** SF-10's SRS row described two
measured speed channels on a traction drive with no statement that none of it
exists. SC-14 carried *"in this project the entire function is modelled"* but
the SRS row did not. One sentence added: SF-10 and SF-11 are modelled in their
entirety — no drive, no encoder pair, no safety-rated measurement channel — and
§5 with §5.1 governs both rows.

### 7. Nothing presumes the m5-03 F-I/O verdict — inherited, and one older sentence fixed

The statement the brief asks for is landed **once**, in PL-SCENARIOS §0: a PLr
is a demand on the function, not on the path its inputs arrive by; the three
derivations hold unchanged under either outcome of m5-03, because neither
outcome changes a hazard, an exposure or an avoidance possibility. No scenario
restates it. `plc/forklift-safety/FIO-FEASIBILITY.md`'s verdict section is still
empty, so the statement is current.

**Fixed, pre-existing text:** TWIN-DEMO-MAP §3's preamble defined *deferred* as
landing at *"the F-I/O half of that gate, where the forklift's safety scanners
**are** wired into the F-CPU's F-blocks … on real F-I/O outputs"*. That is the
primary path in the indicative mood, i.e. the verdict presumed (LESSONS
2026-07-30: a conditional decision propagates with its condition attached, and
the indicative mood is a claim). It now says the scanners reach the F-blocks by
whichever input path m5-03 settles — ADR 0011 D2's configured F-DI or its named
standard-DB fallback — that the verdict is not presumed, and that no deferral in
the table below it depends on the input path (what defers those sub-cases is the
missing second channel, the missing timed stimulus and the missing output).

## Additional defects found and fixed

**AT-03's sub-case letters did not exist.** The committed work appended a fifth
sub-case labelled **(e)** to SRS AT-03, whose three existing observations had
never been lettered, and then referenced "AT-03 (a)" from SC-13's validation
test and "(a)" from inside AT-03 itself — both dangling. AT-03's three existing
observations are now lettered **(a) (b) (c)** in the AT-06 house pattern and the
added sub-case is **(d)**; the three references in SRS and PL-SCENARIOS follow.
No identifier was renumbered: AT-03 is still AT-03, and the letters were absent
rather than reassigned. The `(e)` label now appears in no safety document, and
no document outside `docs/safety/` ever referenced an AT-03 sub-case.

**Sub-case coverage in TWIN-DEMO-MAP.** NC-1 had been updated to put SF-10 and
SF-11 out of the twin's scope, but the two sentences that enumerate which ATs
land at M5 (§ gate-numbers preamble, NC-6) still listed AT-02/03/04 only. AT-10
and AT-11 added to both, so the addendum does not disagree with its own NC-1.

**Node-model citation.** SRS §4's SF-10 row cited opcua-nodes.md "§8, §11.7" for
the refusal of an SLS node. §8 forbids safety *commands* and §11.7 forbids a set
of `Forklift/Safety/` mirrors; the document that refuses "an SLS or safe-speed
value" **by name** is §12.12. Citation corrected to §12.12 on the §11.7 rule.

## What was checked and left alone

- Scenario, SF and AT identifiers: nothing renumbered.
- The scenario count (twelve → fifteen) is consistent in §0, §3.5 and the §4
  table; §3.1 coverage, §3.2 parameter coverage, §3.3 PLr distribution and §3.4
  single-fault behaviour all absorbed SC-13/14/15 correctly, including the
  "five scenarios say where PLr e would be" recount.
- SC-12 is untouched and still marks where the method stops; the three new
  scenarios take the next numbers rather than being inserted by subject.
- SF-10 and SF-11 coin **no** OPC UA or VDA node (invariant 10 respected; the
  request is stated in the SRS row rather than acted on).
- SC-14's two non-standard rows ("The speed source", "What this does not do to
  SF-04") are a deviation from the row set, precedented by SC-12, and the first
  is what the brief asked for explicitly. Left as authored.
- SF-04 keeps its "no PL is claimed" position; SF-10 is described as
  *enforcement* in the reduced-detection case and does not silently upgrade
  SF-04's warning-field case. The open design question that follows from that
  is recorded, not decided (see below).

## open_questions

1. **`plc/forklift-safety/SPEC.md` §1.2 N7 is now incomplete** — it lists
   SF-02, SF-03, SF-04 and the vehicle instance of SF-08 as the vehicle chain
   out of that document's scope, and does not mention SF-10 or SF-11, which did
   not exist when it was written. One clause, in a `plc` brief. Outside this
   agent's write scope; requested, not made.
2. **The warning-field case and SLS.** SC-06's PLr b rests on SF-04, which only
   *requests* creep speed and carries no PL. Whether the warning-field
   monitoring case should also select an SLS limit — which would move that
   argument off an unrated function onto a rated one — is recorded as open in
   SC-06 and in SRS SF-04, and belongs to the field-design and safety-program
   briefs (m5-12 and the F-side spec). Not decided here.
3. **The residual's field design is not specified anywhere yet.** SC-13
   requires a reduced load-direction monitoring case with a ≤ 0.3 m/s limit,
   and R8 requires the rear device's protective field to be bounded inside its
   self-return contour. Both are device field-geometry decisions with no owning
   document; the evidence file assigns them to m5-12.
4. **SF-10 and SF-11 are M5 acceptance tests with no test harness named.**
   AT-10 and AT-11 are written against a modelled onboard safety system
   (measured-speed channels, SS1 timer, STO). Which `agv/` component models it,
   and where AT-10 (d) / AT-11 gets its "modelled deceleration disabled" switch,
   is an `agv/` or `sim/` question this document only states requirements for.
5. **The `wip` commit `b87d1bf` is now superseded by an uncommitted delta.** The
   orchestrator commits `docs/safety/` and `docs/reports/m5-18-plr-derivation.md`
   by pathspec; `sim/maps/warehouse/register_map.py` in the same working tree
   belongs to a concurrent agent and must not be swept in (LESSONS 2026-07-27,
   bare commits under concurrency).
6. **LESSONS candidates from this recovery**, for the orchestrator to append if
   it agrees: (a) a re-verbing sweep is bounded by the subject, not by the file
   the phrasing was first found in — the same "Category 3 is claimed" sentence
   survived in a second document; (b) an attribution clause that names a number
   while citing an ADR that refused to assign one is a claim about the ADR, and
   must be read back against the ADR's own words; (c) appending a lettered
   sub-case to an acceptance test that has no letters creates two dangling
   references at once.
