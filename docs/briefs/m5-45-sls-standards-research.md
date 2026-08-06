# m5-45 — the standards basis for SLS and SS1 on this vehicle

    gate:                M5
    agent:               safety-spec   (research; produces no requirement change without saying so)
    goal:                Establish what the standards actually require of SLS, SS1 and their speed measurement on a driverless industrial truck — and say which of the design's five decisions survive contact with that.
    invariants_touched:  none
    inputs:
      - docs/superpowers/specs/2026-08-06-sls-ss1-fplc-design.md — **the design you are checking**, especially §3, §4 and §7
      - docs/safety/SRS.md — SF-10, SF-11, AT-10, AT-11, and SF-04 beside them
      - docs/safety/PL-SCENARIOS.md
      - docs/adr/0011 **D5** — the claim boundary this project may never exceed
      - agv/forklift/model.sdf, config.yaml — the drive and its measurement today
      - plc/forklift-safety/SPEC.md
      - docs/LESSONS.md
    deliverable:         docs/safety/SLS-STANDARDS-BASIS.md and docs/reports/m5-45-sls-standards-research.md
    done_when:           Every claim carries a source, a version and a verification date; anything that could not be reached is marked unreached rather than paraphrased; and each of the design's five decisions is marked survives / needs amending / contradicted.
    forbidden:
      - stating a clause number you did not read. If the text is behind a paywall, say so and cite what you could actually reach
      - paraphrasing a standard from memory and presenting it as verified — that is the specific failure this brief exists to prevent
      - claiming or implying an achieved PL, Category, SIL or PFH for this project (ADR 0011 D5)
      - changing a requirement in the SRS; this brief researches, and any needed change is **requested**
      - writing outside `docs/safety/` and your report

---

## 1. The question behind the question

The owner ruled that **SLS and the controlled stop are managed by the F-PLC**,
and believes that is a standards requirement. The design was built on that plus
a recollection that **IEC 61800-5-2** defines STO, SS1 and SLS while **ISO
3691-4** governs driverless industrial trucks. **None of it is checked.**

So: is the owner right, and in what sense? "Safety functions live in the safety
layer" may be a requirement, a convention, or a consequence of something else
(the PL the risk assessment demands). The answer changes what M5 must build.

## 2. What to establish

1. **The function definitions.** What STO, SS1 and SLS actually are, and which
   document is their normative home.
2. **Whether a driverless truck is required to have them**, and by which
   document — and whether that requirement is on the *function* or on the
   *performance level* it must reach.
3. **The speed measurement.** SLS needs speed. What does the standard require of
   that measurement — is a single channel ever acceptable, what does a two-channel
   arrangement buy, and is discrepancy monitoring a requirement or a technique?
4. **What a safe encoder actually is.** The design assumes one shaft, two
   channels, cross-compared. Verify that against how safe encoders are really
   built and specified.
5. **Whether the standard program may do the limiting** while the safety layer
   monitors and trips. The design rests on this split, and it is the decision
   most likely to be wrong.

## 3. The constraint you must respect

**ISO and IEC standards are paywalled.** You will probably not be able to read
the normative text. That is fine, and it is why this brief exists rather than a
memory dump.

So: cite what you **can** reach — vendor safety manuals, drive and encoder
datasheets, safety-controller application guides, published summaries — and
**grade every source**. A drive manufacturer's safety manual describing SS1's
two stages is good evidence about the function; it is not the standard's text
and must not be presented as such.

Where you cannot reach something, write **"unreached"** and say what would
settle it. An honest gap is worth more here than a confident paraphrase, and
this project has a lesson about exactly that.

## 4. Then judge the design

Take the design's five decisions in turn and mark each **survives**, **needs
amending** or **contradicted**, with the source:

1. compliance as architectural fidelity plus a simulated safe-measurement
   structure;
2. two channels on one shaft with independent noise;
3. STO as controller-disable plus holding brake;
4. the loop-before-the-map sequencing (this one is a project decision, not a
   standards question — say so if so);
5. **the standard program limits, the safety program monitors.**

If a decision is contradicted, say what the standard-consistent version would
be and what it would cost here.

## 5. The question the owner will ask next

**Does a properly finished single vehicle need phases 3 and 4 before M5 can
close?** Give your reading, with the reasoning visible, and mark it as your
recommendation rather than a finding. The ruling is the owner's.

## 6. Working discipline

- Read `docs/LESSONS.md` first. The one that governs this brief: an ADR citing
  external sources records the verification date and a pinned reference, because
  a claim with no re-checkable source silently ages.
- **Write findings as they land**, not in one pass.
- Nothing heavy — another agent may hold the simulator.
- **Do not commit.** The orchestrator commits by pathspec.
