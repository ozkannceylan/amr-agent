# m5-43 — restate AT-02, AT-03 and AT-04 against M5's scope

    brief:               docs/briefs/m5-43-at-semantics.md
    status:              done — all five problems ruled, each AT restated in the
                         SRS with a written failing-run sentence, every descoped
                         clause dated with its landing gate
    files_changed:
      - docs/safety/SRS.md            (AT-02, AT-03, AT-04 cells restated in place;
                                       §4 rows SF-02/SF-03/SF-04 aligned)
      - docs/safety/TWIN-DEMO-MAP.md  (NC-1 restatement note; NC-6 corrected to the
                                       criterion text, AT-10/11 named as open)
      - docs/safety/PL-SCENARIOS.md   (SC-13 Maps-to row: M5/deferred split noted,
                                       derivation untouched)
      - docs/reports/m5-43-at-semantics.md
    invariants_touched:  none — invariant 1 and B4 are enforced by the
                         restatement, not weakened by it
    open_questions:      four, below
    next_suggested:      rule the AT-10/AT-11 landing (owner + arch-docs) and the
                         creep-enforcer consumer (owner + interface) — both gate
                         the first AT run and neither costs a build

## The five rulings

1. **AT-02.** M5 has no onboard e-stop channel and B4 forbids driving a vehicle
   stop from SF-01's, so AT-02's M5 form tests SF-02's **stop-and-recovery
   discipline** — cut below Nav2, commands-have-no-effect, release restores
   nothing, reset + fresh goal does — exercised on the F-latched protective
   demand, the one vehicle-stopping demand M5 has. The e-stop stimulus itself
   (two-channel onboard stand-in, STO semantics, vehicle SF-08 instance) and
   `safetyState.eStop` are **deferred, dated, → M6**, with the onboard safety
   model AT-09 already requires there. No new F-channel for SF-02 in the cell
   CPU was specified: a vehicle e-stop whose consequence reaches the vehicle
   over OPC UA would demonstrate the network path SF-02's own row forbids.
2. **VDA observables.** Staging posts, not forks: `fieldViolation` → the field
   evaluation's `ZONE` transition + the `Forklift/Safety/ZoneStopDemand`
   mirror; `state.velocity` → the odometry topic; each named in its AT with the
   M6 field it becomes. `safetyState.eStop` has **no** M5 stand-in, because the
   function it reports has no M5 instance — it defers with AT-02's channel.
3. **Auto-release vs latch.** M5 demonstrates the **latched** channel
   (`ZoneStopDemand`, monitored reset) — the roadmap's own criterion (a) text
   already commits to it. SF-03's 2 s auto-release **stays as the claim** in
   the reset row, verification deferred → M6 with the onboard chain; AT-03 (b)
   now makes the latch **holding** on field-clear the pass condition, so a
   quietly wired auto-release would fail the test.
4. **Bumper.** AT-03 (c) deferred, dated, → M6 with the onboard chain (the
   model carries none; NC-1 already recorded it).
5. **AT-03 (d) / AT-04.** (d) split: the two-scanner same-path observation and
   the bare R3 negative residual observation stay at M5 (phase 1 suffices);
   the SLS-in-force clause lands **wherever AT-10 lands**. AT-04 runs at M5 on
   phase 2 (committed FIELD-EVALUATION §12 work) once the **creep enforcer**
   is decided; until then its actual-speed clause fails by construction —
   written into the test rather than weakened.

Every restated test carries an explicit "a failing run looks like" sentence in
its SRS cell, and every observation names an existing instrument: the
consumer's view (`observe_consumer.ps1`), the OPC UA mirror witness
(`opcua_witness.py` path), the field-evaluation transition log / `ZONE` line,
Gazebo ground truth, the odometry topic. Nothing was invented. No PL, Category,
SIL or PFH is claimed or implied anywhere in the edits; 0.3 m/s appears only as
the design limit the SRS already carries.

## Requested (not made)

- **Roadmap M6 row (arch-docs):** the deferred clauses — onboard e-stop channel
  + AT-02's e-stop half, AT-03 (c) bumper, SF-03 auto-release verification —
  should be carried where M6's criterion already needs the onboard chain for
  AT-09, so the descoped items are tracked and not merely dated in the SRS. No
  edit to criterion (d) is needed: it reads "AT-02, AT-03 and AT-04 passing"
  and those ATs now carry executable M5 forms in the SRS it points into.
- **AT-10/AT-11 landing (owner + arch-docs):** SRS §4 lands them at M5; the
  criterion does not name them; AT-10's B-cases demand an onboard SLS trip
  nothing designed provides, and AT-03 (d)'s deferred clause cross-checks
  AT-10. Recommendation: move SF-10/SF-11 verification to M6 in SRS §4. Not
  moved unilaterally — it widens the M6 gate, which is the owner's call.
- **Creep-enforcer consumer (owner + interface):** the one dependency AT-04
  carries; phase 2 deliberately does not pick it.
- **plc/forklift-safety/SPEC.md N7 (plc agent, one line):** N7 says the
  vehicle chain lands "at M5 in that gate's vehicle-chain content"; after this
  restatement the e-stop channel, bumper and auto-release verification are M6.
  Outside my scope; the SRS is the contract N7 defers to meanwhile.

## Open questions

1. The standard program presumably drops the forklift permissive on
   `EStopDemand` as well as `ZoneStopDemand`. That edge is the cell chain
   guarding its own commanded plant (TWIN-DEMO-MAP T1) and must be narrated as
   exactly that in any showcase — never as a vehicle e-stop. A one-line
   narration rule may be worth adding to TWIN-DEMO-MAP §5.3 if the showcase
   script shows that edge.
2. AT-02 (M5) and AT-03 (M5) share a stimulus deliberately; their observation
   sets are disjoint (stop discipline vs trip/standstill/coverage) and each is
   independently failable. If the verifier prefers one combined run, the pass
   lines still count separately (LESSONS 2026-07-28, as-run counts).
3. Whether AT-03 (a)'s standstill-before-boundary measurement waits on the
   m5-42 §5 item 6 end-to-end run is scheduling, not semantics — the test is
   written against that chain, which is commissioned M5 work.
4. m5-42's AT sections were verified against the SRS rather than re-derived;
   one delta found: the review located the mapping table at "§6" — it is SRS
   §4. No substantive disagreement found.
