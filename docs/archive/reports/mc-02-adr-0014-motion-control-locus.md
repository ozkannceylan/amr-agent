# Report mc-02 — ADR 0014: the motion control locus, locked

```
brief:               docs/briefs/mc-02-adr-0014-motion-control-locus.md
status:              done
files_changed:       [docs/adr/0014-motion-control-locus.md,
                      docs/reports/mc-02-adr-0014-motion-control-locus.md]
invariants_touched:  none. Invariants 1, 5, 6, 9, 10 and 11 all bear on the
                     decision and the ADR tabulates the check per invariant
                     rather than asserting it; the other seven are named as
                     untouched. No ADR is superseded, no accepted ADR is
                     edited, and no gate criterion is changed.
open_questions:      five, listed below — one is a correction to a premise in
                     this brief, two are forward pointers this brief forbade
                     writing, two are inherited from mc-01 §M
next_suggested:      a roadmap/PLAN brief landing the ADR 0014 forward pointer,
                     D3's boundary sentence and D5's narration obligation
```

## What was written

`docs/adr/0014-motion-control-locus.md`, **accepted, owner-approval date
2026-07-31**, in the CLAUDE.md §8 format (Status / Context / Decision /
Consequences / Alternatives) and the house preamble style of ADR 0011–0013.
Five decisions, matching the brief's rulings block one for one:

| D | Records |
|---|---|
| **D1** | Motion control closes onboard; no motion value at any granularity crosses OPC UA. **Confirms** ADR 0011 D3 as refined by ADR 0012 D1 — explicitly a confirmation, not a supersession or a refinement — and records what it adds: the no-prior-art count widens from "no PLC-in-the-loop Nav2" to "no vendor's navigation loop across a non-deterministic link" |
| **D2** | The incremental-work alternative, stated fairly in the owner's own terms first, then rejected on four grounds: the structural argument written out branch by branch, the vendor absence (recorded as falsifiable), the figures, and the M4 contrast |
| **D3** | The boundary on how ADR 0011 D1's *onboard* is read, with the documented drift, the M6 incoherence, and the note that an unbounded reading compounds the ADR 0012 D2.1 disclosure. ADR 0011 is not edited |
| **D4** | Three seams — supervision, motion (onboard), orders — against contracts that already exist. Mints no name, defines no logic, adds no node. States that the gate sits **below** the smoother and why |
| **D5** | Written as five numbered **requirements**, not a caveat: what the M5 showcase must say, what the gate's evidence must show, and where the PLC-depth claim actually rests. Notes the M7 layer inherits the sentence, and that no gate criterion is changed by it |

**Figures.** All quoted in one provenance table (G1–G7) with kind (measured /
derived / pinned-external), source, and environment. G1 and G2 carry the
upper-bound caveat from the source. The table opens with the sentence that no
figure in it is a property of a real vehicle, and states why: there is no vehicle
and no PLC hardware in this project.

**Rejected alternatives recorded:** the incremental-work interface with its
reasoning; pose streaming to the PLC at loop rate (the forbidden loop reversed,
plus invariant 9 in the bridge's Python path); leaving the ADR 0011 D1 reading
unbounded; adopting the onboard-PLC pattern faithfully via a second
vehicle-mounted controller; editing ADR 0011 in place; leaving the ruling in
mc-01 rather than an ADR; and claiming the PLC enforces the envelope.

## The boundary sentence of decision 3, as written

> *ADR 0011 D1's word "onboard" covers the F-runtime group `F_Forklift_Safety`
> and nothing else: the **standard program** is the **cell's** PLC — the owner of
> the fixed equipment, the OPC UA server of invariant 4, and at M6 one box
> serving four vehicles — and no reading of D1 makes it any vehicle's onboard
> controller.*

The drift is evidenced rather than alleged: `docs/briefs/mc-01-motion-control-locus-research.md`
argues that the alternative *"sits consistently with ADR 0011 D1's reading that
the S7-1500 represents the forklift's **onboard** controller"*. ADR 0011 D1's
text rules the F-runtime group only.

## Open questions

1. **A premise in this brief was corrected, and the correction is in the ADR.**
   The brief asked that measured figures be *"marked as container measurements
   where they are"*. **Neither quoted measurement is a container measurement.**
   G1 (~46 ms, count 6, median 46.163, p95 47.690) and G2 (145.6–150.8 ms) come
   from `bridge/EVIDENCE_LATENCY.md` **§B2.5 / §B2.6a**, the owner session of
   2026-07-28, whose environment (§B2.9) is **WSL2 Ubuntu 24.04 bridge host with
   Windows-side S7-PLCSIM Advanced V7.0 and a simulated CPU 1513-1 PN**. The
   in-container figures in that file are **Section A**'s test-double run, which
   mc-01 does not quote and neither does the ADR. Each row therefore carries its
   real environment, and G1/G2 are marked "not a container measurement". Worth an
   entry in LESSONS if the orchestrator agrees: the environment qualifier is
   read from the evidence file's own environment section, never inherited from a
   brief's framing (this is LESSONS 2026-07-27's rule applied to a citation).
2. **The forward pointer is not landed.** ADR 0011 and ADR 0012 each state that
   their forward pointer lives in the ADR *and* in `docs/roadmap.md`. This brief
   forbade editing `roadmap.md`, `PLAN.md` and `TODO.md`, so ADR 0014 currently
   has no pointer in the live gate order. Requested, not created.
3. **D5's obligations are not yet carried by any tracking file.** D5.1–D5.3 place
   narration and evidence requirements on the M5 showcase, and D5.5 on the M7
   layer. The M5 roadmap row and PLAN are unchanged and do not contradict the ADR
   — checked, both restate ADR 0011 D1 with the correct F-runtime-group scoping
   and both carry ADR 0012 D1's station-permit refinement — but neither yet
   carries D5. Until a brief lands it, the obligation exists only in the ADR.
4. **Inherited from mc-01 §M, unchanged and still open:** the envelope
   propagation-age and jitter measurement, so §12.4 **E5**'s freshness window is
   set from a measured number rather than from G1 as a proxy (§M q2); and whether
   the public narrative names the onboard stack "the vehicle controller" (§M q1,
   `README.md`, outside this agent's write scope). §M q3 — whether the locus
   ruling should be its own ADR — is **closed** by this deliverable.
5. **One `[snippet]`-grade figure is now quoted in a decision record.** G6's ±1 cm
   industrial docking reference is `[snippet]`-grade in mc-01 §N. It is used only
   as the comparison the derived ±30 mm scatter is read against; the ADR states
   that any later claim leaning on it must re-verify and re-pin it first.

## Scope

Nothing outside `docs/adr/` and `docs/reports/` was written. No ADR other than
0014 was touched; `docs/roadmap.md`, `docs/PLAN.md`, `docs/TODO.md` and
`docs/interfaces/opcua-nodes.md` are unmodified. No PLC logic, vehicle logic or
node name is designed in the ADR, and no achieved PL, SIL, Category or PFH is
claimed or implied anywhere in it. Nothing was committed; the working tree
carries both files for the orchestrator to commit by pathspec.
