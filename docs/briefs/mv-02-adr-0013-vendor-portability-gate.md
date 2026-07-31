# Brief mv-02 — ADR 0013: vendor portability as a gate after the main line

```
gate:                new gate (placement decided here)
agent:               arch-docs
goal:                ADR 0013 records the owner rulings of 2026-07-31 that
                     place the Beckhoff/TwinCAT portability work as its own
                     gate after M6 and M7, and set its scope, its precondition
                     and its drift obligation.
invariants_touched:  none. The research walked all thirteen and found no
                     invariant needing change; the ADR states that finding
                     rather than repeating the walk.
inputs:              [docs/reports/mv-01-beckhoff-portability-research.md
                      (the evidence base — cite it, do not restate it),
                      docs/adr/0010-milestone-restructure-forklift-first.md
                      (the precedent for a gate-order ADR),
                      docs/adr/0006-tia-derived-namespace-uri.md (the failure
                      class the stage-0 probe exists to prevent),
                      docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md
                      (the feasibility-condition-with-named-fallback pattern),
                      docs/interfaces/opcua-nodes.md, docs/roadmap.md,
                      the rulings block below]
deliverable:         docs/adr/0013-vendor-portability-gate.md
done_when:           the ADR states the five decisions below with context,
                     consequences and rejected alternatives; the gate's
                     closing criterion is written so that the NAMED FALLBACK
                     SATISFIES IT (see the discipline note — this is the one
                     thing that must not be got wrong); the stage-0 probe is
                     a stated precondition with the unread tool facts listed;
                     the drift obligation is a deliverable of the gate rather
                     than an intention; the invariant finding is stated;
                     status reads accepted with the owner-approval date
                     2026-07-31.
forbidden:           [editing any other ADR or docs/roadmap.md (a separate
                      brief renumbers); assigning the gate a number (the
                      roadmap brief does that, after M6 and M7 are known);
                      restating the research's findings as if they were the
                      ADR's own evidence — cite the report; claiming any
                      TwinCAT behaviour the research marked unverified;
                      calling the trial licences "free"; writing any
                      implementation detail or config; committing (the
                      orchestrator commits)]
```

## Discipline note — the one thing to get right

A lesson recorded today: *a named fallback is tested against the gate
criterion in the same breath as it is named.* ADR 0011 D2 failed this — its
fallback could not satisfy M5's criterion (a) at all, and nobody noticed until
an adversarial review.

So write this gate's criterion around what the STANDARD PROGRAM mirror proves,
and make the safety mirror an addition that widens the demonstration rather
than a condition of closing it. Then the fallback — TE9100 still unreleased
when the gate opens — leaves the criterion intact instead of voiding it. State
this construction explicitly in the consequences, so a later reader sees it was
deliberate.

## Decisions to record (owner-approved 2026-07-31)

1. **Vendor portability is a gate of its own, placed after M6 and M7.** Not
   inside M5, and not between M5 and M6. Rationale: the TwinSAFE software
   simulator TE9100 carries no release date ("product announcement, estimated
   market release on request", per the research, verified 2026-07-31), and the
   owner ruled the gate should be free to wait for it. A gate between M5 and
   M6 that waits on a vendor's unannounced schedule would block the fleet
   gate, the LLM gate and the demonstration behind it. Placed after the main
   line, waiting costs nothing.

2. **Scope: the full mirror, standard program first, safety when it becomes
   possible.** The gate closes on the standard program's portability. The
   safety mirror is included in the gate's ambition and is demonstrated if
   TE9100 exists when the gate opens; if it does not, the gate still closes
   and the safety layer is recorded as Siemens-only with the reason. The HMI
   already tolerates an absent `Forklift/Safety/` group by design, so the
   absent case needs no client change — record that as the reason the
   construction works.

3. **The claim, stated exactly.** Not "identical addresses" — the research
   found that phrase has no referent, since neither system uses addresses in
   the sense the phrase implies (Siemens optimised DBs, TwinCAT GVL symbols).
   The claim is: **the contract below the interface node is identical —
   BrowseNames, data types, access rights, start values and handshake
   semantics — and the same byte-identical bridge and HMI drive either
   vendor's controller through the same scenario procedures, in separate
   sessions, with both evidence sets kept.** Record that the two clients need
   no code-level vendor knowledge, and that what differs (namespace URI, the
   path from Objects to the interface node) already exists as configuration in
   both of them.

4. **The controller is selected at system startup and is immutable for the
   session.** The two controllers never run concurrently. A mid-run switch is
   out of scope by owner ruling, and the sound reason is recorded rather than
   merely asserted: a controller switch is a controller restart, and
   CLAUDE.md §9 already forbids resuming from stale sequence state. Which
   component owns the selection datum is an implementation question for the
   gate's own briefs, not for this ADR — but invariant 10 applies to it and
   the ADR says so.

5. **Stage-0 owner probe is a hard precondition, and the drift check is a
   deliverable.** Nothing in the design may be built before the owner reads
   back, from an installed TwinCAT, the facts the research could only take
   from documentation: the namespace URI actually served (the documented form
   embeds the machine hostname, which would make a machine rename a breaking
   change), the exact BrowseName strings of struct members, and whether the
   OPC UA server serves the user-mode runtime the owner's WSL2 machine
   requires. This is the ADR 0006 failure class — a tool-derived identifier
   taken from a specification — and the probe exists to prevent its repeat.
   Separately: because this gate now sits after M6, the node model will have
   grown underneath it (M6 adds station handshakes), so **a mechanical drift
   check between the two implementations and the contract is a deliverable of
   this gate**, not an intention. The ADR requires one; it does not design it.

## Alternatives to record as rejected

- Inside M5: M5 already carries sensors, safety, SLAM, Nav2 and HMI v2;
  adding a second vendor would blur the gate's closure.
- Between M5 and M6, waiting for TE9100: makes a vendor's unannounced
  schedule into this project's schedule and blocks three gates behind it.
- Between M5 and M6, scoped to the standard program only: viable, and it was
  the owner's first instinct, but it spends a gate slot on the main line for
  work that gains nothing from being early — the contract is more stable
  after M6, not less.
- Claiming identical addressing: no referent, and an industrial reader would
  see through it immediately.

## Git

Report to docs/reports/mv-02-adr-0013-vendor-portability-gate.md in the
standard report format. Do not commit — the orchestrator commits.
