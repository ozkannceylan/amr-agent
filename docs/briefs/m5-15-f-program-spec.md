# m5-15 — the F-program specification

    gate:                M5 (criteria (a) and (b))
    agent:               plc
    goal:                A specification for the forklift's onboard safety program, complete enough that the owner can type it into TIA Portal without a design decision, written against the automated stand-in stimulus that ADR 0015 settled.
    invariants_touched:  none — ADR 0011 D1 is untouched by this brief and must stay so
    inputs:
      - docs/adr/0015-criterion-a-standin-stimulus.md — **D1 especially**; this is the input path
      - plc/forklift-safety/FIO-FEASIBILITY.md **§6** (the three consequences) and §7 (the verdict)
      - docs/reports/m5-03-fio-probe-run.md, docs/reports/m5-03b-standin-stimulus-proof.md
      - plc/forklift-safety/SPEC.md — all of it; §7, §2 checkpoint F3, §4.2 step 8 and §9 T6 are yours to rewrite
      - docs/safety/ — the SRS (which safety functions are the forklift's), PL-SCENARIOS, TWIN-DEMO-MAP
      - docs/roadmap.md — criterion (a) as amended, and criterion (b)
      - plc/forklift/TIA-BUILD-PROCEDURE.md — chunk J lists what this spec must supply
      - docs/reports/m5-23-judge-review.md — **findings F3 and F4**
      - docs/LESSONS.md
    deliverable:         the rewritten sections of plc/forklift-safety/SPEC.md, and docs/reports/m5-15-f-program-spec.md
    done_when:           A reader at TIA Portal can build the F-program from the spec alone: every block, every tag, every timer with its PT, every reaction, and the S015 validity check written out as code they can type. The three §6 consequences are visible in the document, and §9 T6's stimuli are all automated.
    forbidden:
      - specifying F-I/O configuration as the input path — the probe settled it (ADR 0015); configured F-DI is not used
      - specifying any stimulus by watch-table *Modify* — the tool refuses fail-safe Modify in permanent safety mode (`2206:000002`), so a procedure that plans it cannot run
      - claiming or implying an achieved PL, Category, SIL or PFH — ADR 0011 D5 permits PLr **targets** only, and this is the document where that slips
      - reopening ADR 0011 D1 — which controller the F-program *is* does not depend on how its inputs are stimulated
      - inventing a safety function; the SRS says which are the forklift's
      - writing outside plc/ except your report
      - tuning the monitored-reset window to fix the deviation of §4 — that is safety-spec's, not yours

---

## 1. What changed, and why this spec exists now

ADR 0011 D2 made the input path conditional on a probe. The probe ran (m5-03):
the configured F-DI never leaves passivation on this installation, **and** the
fallback D2 named — watch-table *Modify* — cannot run at all, because TIA
refuses fail-safe *Modify* in permanent safety mode. ADR 0015 replaced both with
an **automated API-driven standard-DB stimulus**, proven twice (m5-03b),
including against a witness that cannot see the written datum.

So this spec is written against `SafetyInputStandIn`, written by the PLCSIM
Advanced API by tag name, with no human in the loop.

## 2. The three consequences, which are binding

From `FIO-FEASIBILITY.md` §6:

1. **The stand-in is labelled a stand-in wherever it appears** — every section,
   caption, watch-table row and spoken line.
2. **The S015 validity check is carried visibly in the F-code**, per F-runtime
   group, written out as code the owner types — not acknowledged in a compile
   log and forgotten. TIA's mechanism for standard data in a safety program is
   **disclosure, not protection**; the check is what makes the disclosure
   honest.
3. **ADR 0011 D1 does not reopen.** Only the input path is a stand-in.

## 3. The gap the judge found — you must close it

m5-23 finding F3, soft spot 2: **`ResetButtonPressed` has no compliant stimulus
left.** ADR 0015 retired *Modify*, and the monitored reset needs an edge. Specify
where that edge comes from, on the same automated path as the other two inputs,
and say how a reset that originates in software is still a **monitored** reset
in the sense CLAUDE.md §9 requires — edge-triggered, so a stuck signal is not a
reset.

Also from F3, soft spot 1: **no instrument distinguishes a field-evaluation
write from a scripted one.** Criterion (a) requires the intrusion to originate in
Gazebo. Say what the F-program can check, and be honest about what it cannot —
if the distinction can only be made outside the F-program, say where.

## 4. What else the spec must carry

- **The automated writer**: its design, its update rate, and its failure
  behaviour — what the F-program sees when the writer dies, and why that is
  safe. The transport crosses WSL to Windows; name it.
- **Every timer with its PT at the call site**, because an interface default
  governs nothing once the instance DB exists (LESSONS 2026-07-28).
- **The reset window deviation, stated not fixed**: `RESET_HOLD_MIN` is 200 ms
  against five F-OB cycles of 500 ms (`FOB_RTG1` is OB123 at 100 ms). Record it
  as an open SRS-window deviation and hand it to safety-spec. Do not tune it.
- **§9 T6 rewritten** so every stimulus is automated, and
  `sim/scenarios/forklift_commissioning.md` §13's dependent rows are named as a
  request to the sim agent.
- **FIO-FEASIBILITY §6 itself** — judge finding F4: its retired *Modify* text is
  still live and the verdict section routes readers into it. It is in plc/ and
  therefore yours.

## 5. Write it so it can be typed

`plc/forklift/TIA-BUILD-PROCEDURE.md` deliberately stops before the F-program
because this spec did not exist. Its chunk J lists what the F-session needs.
Write to that: named blocks, named tags following CLAUDE.md §9, SCL the owner
can type, and a verification per step. Someone else will turn it into numbered
steps — your job is that nothing is left to their judgement.

## 6. Working discipline

- Read `docs/LESSONS.md` first. The F-program traps are dense: a timer released
  only by code that runs in the exit scan, a latch that is a term in its own
  clearing condition, affirmative analogue plausibility, and wire NC / program NO.
- **Write as it settles**, not in one pass.
- **Do not commit.** The orchestrator commits by pathspec.
- Another agent is reviewing `hmi/` right now — do not touch it.
