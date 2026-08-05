# m5-23 — adversarial judge review of the M5 work

    gate:                M5
    agent:               verifier   (read-only; adversarial posture)
    goal:                Find what is wrong, weak, overclaimed or unprofessional in the M5 work as it now stands, and state exactly what is missing before M5 can run end to end with HMI, PLC and vehicle together in Gazebo.
    invariants_touched:  none — this brief reads, it does not change
    inputs:
      - CLAUDE.md (the contract, all of it — including §2 invariants and §9 domain conventions)
      - docs/roadmap.md (the M5 row, as amended by ADR 0015)
      - docs/adr/0011, 0012, 0014, 0015
      - docs/PLAN.md, docs/TODO.md, docs/LESSONS.md
      - every docs/reports/m5-*.md
      - agv/forklift/ (the vehicle stack and all its EVIDENCE_*.md)
      - plc/forklift/SPEC.md, plc/forklift-safety/SPEC.md, plc/forklift-safety/FIO-FEASIBILITY.md
      - docs/interfaces/opcua-nodes.md, bridge-design.md
      - bridge/config/, sim/
      - docs/safety/ (SRS, PL-SCENARIOS, TWIN-DEMO-MAP)
    deliverable:         docs/reports/m5-23-judge-review.md
    done_when:           Every finding names the file and the claim it attacks, is ranked by severity, and says what would have to be true for the claim to stand. Part B (§2) lists the end-to-end gap as an ordered, dependency-correct sequence separating owner-at-the-tool work from agent work.
    forbidden:
      - writing anything except the report — you are read-only
      - accepting a report's summary as evidence; go to the artifact the report cites
      - softening a finding because the work is otherwise good
      - inventing a defect to fill a quota; "I attacked X and it held" is a valid and useful finding
      - re-running the simulator (another agent may hold it — LESSONS 2026-07-30)

---

## Part A — judge the work

Attack the M5 corpus. You are not confirming it; you are trying to break it.

Look specifically for:

1. **Overclaim.** Any sentence that asserts more than its evidence carries.
   This project's standing risk is a safety claim: ADR 0011 D5 permits **PLr
   targets only** — never an achieved PL, Category, SIL or PFH. Sweep by
   subject, not by remembered phrasing (LESSONS 2026-08-04); an earlier sweep
   for "Category 3 is claimed" missed a live instance in a second file.
2. **A number that is a sample presented as a bound.** LESSONS 2026-08-04:
   a figure from one instance of an event is n=1. Check the m5-11 figures, the
   localization figures and the Nav2 figures against this.
3. **Evidence qualified by an environment that is not stated.** LESSONS
   2026-07-27. The m5-11 measurements were produced under a `.deb` overlay; the
   m5-03b proof was produced on the probe copy `safe_amr_FIOPROBE`. Are those
   qualifiers where a reader would find them, or only in a report?
4. **Documents that disagree.** PLAN, TODO, roadmap and the reports must not
   contradict each other or CLAUDE.md. The m5-20 sweep listed twelve locations
   stating something the m5-03 verdict falsifies — check that list is complete
   and that nothing new has drifted.
5. **A criterion that cannot fail.** Criterion (a) was just rewritten. Can the
   work actually fail it? If it cannot, say so — that is the most valuable
   finding available in this review.
6. **Layer boundaries and invariants.** Anything that crosses a boundary the
   CLAUDE.md §3 topology does not draw, or that puts safety, a velocity or a
   control loop somewhere it must not be.
7. **Unprofessional residue.** Dead files, stale instructions a reader would
   follow into a wall, TODO items that were deleted with live sub-items,
   evidence that cannot be reproduced from what is written, naming that
   violates CLAUDE.md §9.

8. **The Nav2 route regression found 2026-08-05 (docs/TODO.md, blocker-class).**
   The m5-10 straight-route goal SUCCEEDED in 13.40 s at 0.183 m when
   committed; on 2026-08-05 it TIMED OUT at 90 s at 0.628 m — and on the
   **untouched** m5-10 chain, so the vehicle image did not cause it. Nobody has
   bisected it. Judge the consequence, not the cause: **how much of the
   committed M5 evidence still stands** if the installed stack navigates
   differently from the overlay it was measured on? Say which specific
   figures — m5-08e localization, m5-10 Nav2, m5-11 gate — are now unqualified
   claims, and whether any gate criterion currently rests on one.

For each finding: file, the claim, why it fails, and what would make it stand.
Rank by severity. Say plainly which findings **block the gate** and which are
housekeeping.

## Part B — what is missing to run end to end (the owner asked for this by name)

Separately from Part A, answer one question: **what has to exist before the HMI,
the PLC and the vehicle run together in Gazebo as one system?**

Ground it in what is actually built, not in what the plan says. Two facts
established 2026-08-05 that you should verify rather than assume:

- The running CPU publishes `ForkliftHmi`, `ForkliftInput`, `ForkliftOutput`,
  `ForkliftStatus`, `ForkliftLink` and `ForkliftSafetyMirror` — **and no
  envelope, mode or permit node.** The §14 standard-program delta is specified
  (m5-16) but is not on the CPU.
- The envelope gate node was measured against a **ROS 2 topic double**, not
  against the PLC. `bridge/config/bridge.yaml` is deliberately cell-only and the
  bridge's signal map does not carry the envelope group (m5-11 open question 5,
  `opcua-nodes.md` §12.13 item 1).

Deliver an **ordered sequence** with, for each item:

- what it is, and which existing spec or brief already covers it (or that none
  does);
- whether it is **owner-at-the-tool work** (TIA Portal, PLCSIM) or **agent
  work**, because the owner's time is the scarce resource;
- what it depends on, so nothing is scheduled before the thing it needs — note
  the known trap that HMI v2a is a prerequisite for the §14 program to do
  anything at all, because `HmiProcessStopRequest` starts TRUE;
- how you would know it works, in one observable line.

Where a gate criterion cannot be met by anything currently planned, say so
rather than redefining the criterion (CLAUDE.md §10).

## Part C — the honest summary

Three to six sentences an outside engineer would accept: what this project has
actually demonstrated, what it has not, and where a reviewer would press hardest.
No marketing, no hedging.

## Working discipline

- Read `docs/LESSONS.md` first; several entries are findings you would otherwise
  have to rediscover.
- **Write findings into the report as they land**, not at the end.
- **Do not commit.** The orchestrator commits.
