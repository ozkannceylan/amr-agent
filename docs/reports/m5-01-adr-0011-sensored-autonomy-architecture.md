# Report m5-01 — ADR 0011: sensored autonomy architecture

```
brief:               docs/briefs/m5-01-adr-0011-sensored-autonomy-architecture.md
status:              done
files_changed:       [docs/adr/0011-sensored-autonomy-architecture.md]
invariants_touched:  none. Invariants 1-13 stand unchanged. Two consequences are
                     recorded in the ADR's preamble as consequences, not as
                     changes: (i) CLAUDE.md §3 gains one monitoring-plane edge
                     (D4), which invariant 11 reads against — the diagram
                     amendment is a separate owner-approved infra brief and this
                     ADR is its authority; (ii) D3 amends the M4 GATE-CRITERION
                     phrasing "the PLC forms all motion setpoints" for
                     AUTONOMOUS mode only. The M4 criterion itself is unchanged
                     and already closed on teleop.
open_questions:      see list below
next_suggested:      the infra brief amending CLAUDE.md §3 with the
                     monitoring-plane edge in a third arrow style, and the
                     roadmap/PLAN note that ADR 0010 D6(a) is closed by ADR 0011
                     D4
```

## What was written

`docs/adr/0011-sensored-autonomy-architecture.md`, status **accepted
(2026-07-30)**, owner-approved on that date, in the CLAUDE.md §8 format
(Status, Context, Decision, Consequences, Alternatives) and the ADR 0009 /
ADR 0010 house style.

The five owner rulings of 2026-07-30 are recorded as D1–D5:

| | Decision |
|---|---|
| D1 | The forklift's F-runtime group is the **vehicle's onboard safety controller**; scanner → F-program → STO is internal to the vehicle. The single hosting 1513F-1 is disclosed as a simulation artifact |
| D2 | The scanner reaches the F-program through **configured ET 200SP F-DI stimulated by the PLCSIM Advanced API by tag name** — the simulation's equivalent of wiring. Feasibility condition and named fallback in the ADR 0009 D4 pattern |
| D3 | In autonomous mode the PLC issues a **motion envelope** (enable, speed ceiling, zone permit); the navigation loop closes onboard |
| D4 | A **read-only monitoring plane** joins the topology: no write endpoint, no publisher, read-only by construction. Closes ADR 0010 D6(a) |
| D5 | **Claim boundary**: `PLr` targets only, no achieved PL/SIL/PFH; the seven-item non-claim list reproduced in full; no TIA safety acceptance test or program signature claimed |

Brief conformance:

- **External facts.** All twelve are in one Context table (F1–F12) with source and
  the verification date **2026-07-30**. Nothing outside that table is asserted as
  external fact. F4 (PLCSIM Advanced V6.0+ supported safety system versions) is
  recorded **unverified**, as the brief requires. F9 (field-set switching
  practice) and F10 (SLS/STO) are marked as practice / as-quoted rather than as
  pinned clauses, per the LESSONS rule of 2026-07-26.
- **D2's feasibility condition** names what is settled, where it is settled (the
  first M5 brief, in the tool), the trigger, the named fallback (the present
  standard-DB stand-in, labelled as a stand-in with the S015 validity check
  visible in the F-code), that the fallback is inert by construction, and that it
  does not reopen D1.
- **D5's non-claim list is reproduced in full**, as seven numbered items.
- **Relationships** to ADRs 0002, 0005, 0008, 0009 and 0010 are each stated, in a
  dedicated table plus in-line where a decision rests on one.
- **Six rejected alternatives** are recorded with their reasons.
- The **directory of the monitoring service is not ruled**: recommended `agv/`,
  recorded as an implementation question for the first monitoring brief, with the
  `viz/` alternative and the ADR 0005 D1 test named as the deciding test.
- No deadline is mentioned anywhere; the withdrawal date of EN ISO 13849-1:2015
  was deliberately omitted from F12 for that reason.
- No other file was touched: no ADR edited, no CLAUDE.md, no
  roadmap.md / PLAN.md / TODO.md, no code, no specification.

## Open questions

1. **Component datasheet figures appear in fact F8.** The brief's facts block
   supplies the SICK microScan3 Pro figures — Type 3, Cat 3 / PL d, PFH
   8×10⁻⁸ h⁻¹ — expressly "quoted as the modelled class, never as this system's
   achievement", and the ADR carries them with an explicit guard sentence
   immediately below the table plus item 7 of D5's non-claim list. Flagged so the
   verifier reads that placement deliberately rather than as a stray PL/PFH
   string: **the document makes no achieved-PL, SIL or PFH claim for anything in
   this repository.** If the owner prefers the figures dropped entirely, that is
   a superseding ADR, not an edit (CLAUDE.md §8).
2. **CLAUDE.md §3 and this ADR now disagree** until the infra brief adds the
   monitoring-plane edge. The ADR states it is the newer statement, on the ADR
   0005 and ADR 0008 precedent, but the disagreement is live in the meantime and
   the verifier will see it.
3. **`docs/roadmap.md` still lists ADR 0010 D6(a) as open** ("The map-view data
   path is decided by its own ADR at M5 briefing"). D4 has now decided it. The
   roadmap, PLAN.md and TODO.md must not disagree with this ADR; the update is
   outside this brief's deliverable and is requested rather than made.
4. **The F-DI's order number and parameterisation values are not fixed** by this
   ADR, and D2's primary path is conditional on F4 being resolved in the tool.
   The first M5 brief carries both.
5. **`plc/forklift-safety/SPEC.md` open item 1** — "the F-input channel ruling of
   §2.1 is a design assessment, not a tool read-back" — is now answered in
   direction by D2 but not in fact. F3 supplies the probable cause (TIA V18/V19
   defaulting to a safety system version above the supported list); confirming it
   is the same tool step D2's feasibility condition asks for.
