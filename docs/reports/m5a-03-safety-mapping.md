# Report m5a-03 — the twin demonstration mapped onto the SRS

```
brief:               docs/briefs/m5a-03-safety-mapping.md
status:              done
files_changed:       docs/safety/TWIN-DEMO-MAP.md (new)
                     docs/reports/m5a-03-safety-mapping.md (this report)
invariants_touched:  none
```

## What the addendum says

One page, table-first, adding no SF number, no AT identifier, no risk-graph
parameter, no PLr and no PL value. Every ISO 13849 reference is quoted from
`SRS.md` §5 or its `PL-SCENARIOS.md` derivation.

- **§2** gives, per function, the SRS trigger/reaction/safe-state/reset text it
  instantiates, what the twin actually does, the PLr floor with its scenario
  reference (SF-01 → SC-01/02/03, SF-07 → SC-10, SF-08 → SC-11) and the SRS §5
  target. SF-08's PL c under SC-11's PLr d is stated as correct — the hazard is
  held by SF-07, the floor is not re-argued, and the twin derives nothing
  because it introduces no hazard and exposes no person.
- **§3** rules all twelve AT sub-cases in scope or deferred. In scope: AT-01
  (a), (d); AT-07 (a), (b), (c); AT-08 (a), (c), (d). Deferred: AT-01 (b) and
  AT-07 (d) (the B3 case), AT-01 (c) (no second channel, so **no Category is
  demonstrated**), AT-08 (b) (no controlled sub-0.2 s stimulus). Nothing is
  marked passed.
- **§4** carries nine non-claims, including the two the brief named and three
  the mapping produced: **no safety reaction path exists** — SF-01/SF-07
  de-energize hardwired outputs and this plant has none, so the observable stop
  is the standard program's permissive dropping and its setpoints zeroing, a
  process consequence travelling over the very network that may never carry a
  reaction.
- **§5** gives the recording's three spoken statements, the stand-in rule and a
  say/never-say table. The naming discipline now cuts both ways: "e-stop" is
  correct for the F-side stand-in and stays forbidden for the M3 mushroom, the
  lidar stop and the HMI process banner.
- **§6** places six rules on the downstream specs, chiefly R1 — the SF-08 reset
  is an F-input stand-in and **never a client write**, per SC-11's network row.

The 2026-07-29 F-run is recorded as evidence that the F-logic executes and is
counted in no sub-case, for ADR 0009's three reasons (network-fed input, level
acknowledgement, standard program running).

## The stand-in sentence

§5.1 carries it to be used as written; §5.2 states the rule behind it. A
stand-in substitutes for **wiring**, not for a safety input: it carries no
Category, no PL, no channel count, no diagnostic coverage; and a stand-in fed
over the network is doubly disqualified, because a reaction whose input arrives
over OPC UA cannot execute with the session down, which the M5 criterion
requires.

## open_questions

1. **The zone stand-in's channel decides three sub-case rulings.** ADR 0009
   rejects a network-carried safety input and moves the F-inputs to the
   simulated F-I/O / engineering interface. AT-07 (a)–(c) are ruled *in scope*
   on that basis. If m5a-04 §7 finds no way to drive an F-input channel on the
   PLCSIM instance and the zone stand-in stays network-fed, those three drop to
   *deferred* and the T6 run keeps only its logic value. Worth an owner ruling
   if the tool forces it.
2. **AT-08 (b) needs timed injection.** A hand-driven stand-in cannot produce a
   sub-0.2 s pulse. If m5a-04 §7 provides timed injection it moves into scope;
   otherwise it stays deferred and the monitored **window** is demonstrated
   nowhere at this opening, even though the edge is.
3. **Both B3 sub-cases stay untouched by the early opening.** AT-01 (b) and
   AT-07 (d) cannot be run on the twin: halting the standard program removes the
   observable rather than testing it, because the consequence is produced by the
   standard program. The roadmap M5 row requires B3 for all three ATs at the
   gate proper.
4. **Whether the F-program implements the full 0.2 s–3 s window** is m5a-04's
   call. The addendum leaves the SRS text standing and defers only the sub-case
   that cannot be stimulated.

## next_suggested

m5a-04 can proceed; its §7 simulated-input strategy is the deciding input for
open questions 1 and 2, and its report should say which way each fell.
