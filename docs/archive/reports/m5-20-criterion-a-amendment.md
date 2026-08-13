# m5-20 — M5 criterion (a) amended by ADR 0015

    brief:               docs/briefs/m5-20-criterion-a-amendment.md
    status:              done
    files_changed:
      - docs/adr/0015-criterion-a-standin-stimulus.md (new)
      - docs/roadmap.md (M5 row criterion (a) rewritten; ADR 0015 preamble
        paragraph added; the ADR 0011 D2 conditional marked settled)
      - docs/PLAN.md (stale "verdict is blank" summary corrected; ruling part
        (2) marked done; m5-15 line pointed at ADR 0015)
      - docs/reports/m5-20-criterion-a-amendment.md
    invariants_touched:  none. The stand-in path is an API write inside the
                         simulation host — no network element, invariant 1
                         holds as before; no invariant names the input path,
                         the stimulus mechanism or any criterion text. ADR
                         0015 is therefore accepted (owner ruling 2026-08-04),
                         not proposed.
    open_questions:      see the sweep list below, and three items after it
    next_suggested:      brief m5-15 against ADR 0015 D1 (it rewrites
                         plc/forklift-safety/SPEC.md §7 and checkpoint F3),
                         and schedule the m5-03b repeat on `safe_amr`

---

## What was done

ADR 0015 records the owner's 2026-08-04 ruling: both remedies. It partially
supersedes ADR 0011 D2 — by name, with the evidence: the "changes no gate
criterion" claim (killed by the judge review's finding 1) and the fallback's
watch-table *Modify* mechanism (killed by the probe's `2206:000002` refusal —
the fallback could not have run as written). D1/D3/D4/D5 and F1–F12 of ADR
0011 stand. Every figure in the ADR is quoted from m5-03, m5-03b or
FIO-FEASIBILITY §7 with units; no new external source is cited, so no new
verification pins were needed.

The amended criterion (a) still requires what was proven — the scanner's
simulated signal reaching the F-blocks and F-logic executing on it — and adds
seven failable observables: automated end to end (no hand at a watch table),
intrusion originating in the Gazebo field evaluation, demand read in the
consumer's view (F-block instance data, never the writer's read-back),
corroboration on a witness that cannot see the stand-in DB, override of both
modes, the monitored edge-triggered reset as the only clearance, and the S015
check plus stand-in labelling visible in the artifact. It names the stand-in
as a stand-in in the criterion text itself and carries the non-claim (no PL,
Category, SIL, PFH) inside the row, not in a footnote.

Criteria (b)–(e): checked, none depends on (a)'s wording — none names the
input path. Unchanged.

## Sweep — documents that now state something the m5-03 verdict falsifies or
## makes stale (listed, NOT edited; each belongs to its own layer's agent)

Swept by subject (F-DI / PLCSIM Advanced API / stand-in / Modify /
SafetyInputStandIn, whitespace-tolerant), not by remembered phrasing.

1. `agv/forklift/model.sdf` (~111–123) — "That path has never been run ...
   verdict section is blank as this is written." Conditional form intact
   (m5-j2), but the verdict is in and the answer was no. agv.
2. `agv/forklift/README.md` (~127–140) — same statement. agv.
3. `agv/forklift/config.yaml` (~562–572) — "SETTLED FACT. ADR 0011 decision 2
   makes it configured F-I/O ... verdict is still blank." agv.
4. `agv/forklift/launch/vehicle.launch.py` (~121–129) — same. agv.
5. `agv/forklift/EVIDENCE_SENSOR_COVERAGE.md` §10c (~545–551) — same. agv.
6. `plc/forklift-safety/SPEC.md` §7 (~1093: "driven by *Modify* from the TIA
   watch table ... That is the whole mechanism"), §2 checkpoint F3, §4.2 step
   8's F-DI re-point note, and the §9 T6 *Modify* steps — the stimulus
   mechanism is superseded by ADR 0015 D1; m5-15 rewrites these. plc.
7. `sim/scenarios/forklift_commissioning.md` §13 (~797) — the T6 rows drive
   `SafetyInputStandIn` by *Modify* at the TIA watch table; retired as a gate
   stimulus by ADR 0015 D1. Follows the SPEC §7 rewrite. sim.
8. `docs/safety/TWIN-DEMO-MAP.md` §3 (~69–71) — "by whichever input path
   brief m5-03 settles in the tool ... That verdict is not presumed here":
   stale, verdict in. Also AT-08 (b)'s deferral condition ("moves into scope
   if, and only if, the F-spec's stimulus strategy provides timed injection")
   is now **triggered** — m5-03b held a commanded 1000 ms; whether the
   sub-case enters scope is the safety-spec agent's ruling. safety-spec.
9. `docs/adr/0011` D2 — the superseded claims; handled by ADR 0015 itself,
   never by editing (CLAUDE.md §8).
10. `docs/adr/0012` (~233) and `docs/adr/0014` (~454) — both list the m5-03
    verdict as deliberately pending. Accepted ADRs, never edited; the forward
    pointer lives in ADR 0015 and the roadmap preamble.
11. `docs/TODO.md`, m5-03 heading — part (2) of the three-part done is now
    closed by this round; TODO is the orchestrator's to reconcile.
12. Noted safe, no action: `docs/safety/PL-SCENARIOS.md` (~50–60) and
    `plc/forklift/SPEC.md` (~2036, ~2932) state explicitly that they hold
    under either verdict — true statements, still true.

## Open questions

1. The m5-03b evidence is qualified by the probe copy `safe_amr_FIOPROBE`;
   the run repeats on `safe_amr` before criterion (a) evidence cites it, and
   the probe copy deletion (FIO-FEASIBILITY §0.1 rule 3) is still owed.
2. Items 1–8 above need their layer briefs; the resolution of a conditional
   propagates like the condition did (LESSONS 2026-07-30).
3. TODO part (2) closure and this report's reconciliation are the
   orchestrator's (TODO is outside arch-docs write scope).
