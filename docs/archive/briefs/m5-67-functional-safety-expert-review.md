# m5-67 — functional safety expert review

    gate:                M5
    agent:               verifier (read only), run as a functional safety reviewer
    scope grant:         read anything; write exactly one file, in the owner's vault (path below). Nothing in the repository.
    goal:                Review this project the way a functional safety engineer reviewing a machine-safety design would, name what is unprofessional or would not survive a real review, and recommend fixes — every recommendation tied to a fact the reviewer actually found.
    invariants_touched:  none. Naming an invariant as wrong is allowed and is a finding; changing one is not.
    inputs:              the whole repository, and outside sources the reviewer verifies itself
    deliverable:         C:\Users\ozkan\OneDrive\Documents\MyNotes\projects\active\amr-agent\SAFETY-REVIEW-2026-08-07.md
    done_when:           Every recommendation carries a source the reviewer read, graded; every finding says what it would cost; and the report is one document the owner can act from.
    forbidden:
      - writing anything inside the repository, or changing any file
      - quoting a standard clause number that the reviewer has not seen in a reachable source
      - taking any quotation from an automated summariser (see §4 — this project has been burned)
      - recommending anything the reviewer cannot tie to a fact it found
      - claiming or implying that this project has achieved a PL, Category, SIL or PFH

---

## 1. What the owner asked for, in their words

Look at the project **with the eye of a safety-PLC expert**, find approaches
that are **not professional**, and make recommendations. **Every recommendation
must be tied to a researched fact — no advice out of thin air.** Then collect
it all into **one report**.

That last constraint is the brief. A plausible-sounding recommendation with no
source is worse than silence here, because it will be believed.

## 2. What this project is, so the review is fair

A portfolio project: a PLC-supervised AGV/AMR cell, everything in simulation
(Gazebo + PLCSIM Advanced), built to demonstrate **correct separation of
concerns between safety, control, fleet and autonomy layers** rather than
feature count. Read `CLAUDE.md` first — it is the contract, and §2 holds
thirteen locked architecture invariants.

**Judge it against what it claims to be.** It does not claim certification. It
claims **PLr targets only**, and its safety input path is a **labelled stand-in**
on a standard data block, disclosed everywhere it appears (ADR 0011 D5,
ADR 0015). A finding that says "this is not certifiable" is not useful. A
finding that says "this is presented as X but is actually Y", or "a real review
would reject this reasoning, and here is why", is exactly what is wanted.

Start here, then follow what you find:

- `CLAUDE.md` — the contract, the invariants, the topology
- `docs/safety/SRS.md` — the safety requirements spec
- `docs/safety/SLS-STANDARDS-BASIS.md` — the standards work already done,
  **including its own list of unreached items U1–U5**
- `docs/adr/` — 0011 (the claim boundary), 0014, 0015, 0016
- `plc/forklift-safety/SPEC.md` — the F-program
- `docs/VALIDATION-M5.md` — what has actually been demonstrated, and what has not
- `docs/LESSONS.md` — the project's own record of its mistakes

## 3. Where to look hardest

Not a checklist to fill in — the reviewer's judgement leads. But these are where
an expert's eye is worth most:

- **The claim boundary.** Is the stand-in disclosed honestly everywhere, or does
  some artefact quietly read as a safety claim? Is anything captioned as the
  PLC's verdict that is really a consumer's own?
- **The reaction chain.** Trigger → reaction → acceptance test, per safety
  function. Are the reactions the right ones, in the right order, with the
  right restart behaviour?
- **The single-channel tested system.** The design calls it that deliberately,
  not "two-channel", and closes the shared-shaft hole with a **motion-present
  check labelled a stand-in** for a mechanical fault exclusion. Does that
  argument hold, or is it doing work it cannot do?
- **SLS placement** — the standard program limits, the F-program monitors and
  demands. Is the split as it is implemented actually the pattern the design
  claims, or has it drifted?
- **Reset and restart discipline**, and whether any latch can be cleared by
  something that is not a monitored reset.
- **The thresholds and windows** — several were derived recently, one after a
  band was found that diagnosed a healthy vehicle as a failed shaft. Are the
  derivations sound? Is anything still a chosen number wearing a derivation's
  clothes?
- **What the demonstration will claim on stage** versus what the evidence
  supports.

## 4. The evidence rules, and they are not negotiable

This project has already been burned twice, and both times are recorded:

1. **Two automated document summaries returned fabricated quotations** during
   the standards-basis round. Every quotation was afterwards re-verified against
   locally extracted source text. **You may not take a quotation from a
   summariser.** If you cannot read the source yourself, you do not quote it.
2. **The normative texts are behind a paywall.** `SLS-STANDARDS-BASIS.md`
   records five unreached items, U1–U5, precisely so nobody pretends otherwise.
   **No clause number may appear unless you saw it in a source you actually
   read** — and if that source is itself citing the standard, say so.

So grade every source, visibly:

- **[read]** — you opened it and read the relevant passage
- **[cites]** — a reachable source citing a normative text you could not open
- **[vendor]** — a manufacturer's safety manual or application note
- **[unreached]** — you could not get it, and the recommendation is marked as
  resting on something you could not verify

**A recommendation with no source does not go in the report.** If you believe
something is wrong but cannot source it, there is a place for that — §6 below —
and it is not the recommendations section.

## 5. Every finding states its cost

An expert review that lists twenty items with no weighting is a list, not a
review. For each finding say:

- **what it would cost to fix** — a document edit, a TIA session, an
  architecture change
- **whether it blocks the presentation**, which is safety-PLC focused and
  close
- **whether it blocks a later claim** the project intends to make

The owner has ruled autonomy a prototype and the safety chain the deliverable.
Weight accordingly.

## 6. Say what you could not check

A section for exactly this: what you would have examined with more access, which
sources you could not reach, and which of your findings would change if you
could. **This section is as valuable as the recommendations** — it is what stops
a reader treating the review as complete when it is not.

## 7. The report

One document, at
`C:\Users\ozkan\OneDrive\Documents\MyNotes\projects\active\amr-agent\SAFETY-REVIEW-2026-08-07.md`.

Written for the owner: an engineer who knows this project deeply, is presenting
it soon, and wants to know what a professional would object to. Lead with what
matters most. Prefer a table to a paragraph. Do not pad.

**Write nothing else, anywhere.** Not in the repository, not a scratch file that
survives. Do not commit.
