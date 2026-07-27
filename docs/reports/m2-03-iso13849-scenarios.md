brief:               docs/briefs/m2-03-iso13849-scenarios.md
status:              done
files_changed:
  - docs/safety/PL-SCENARIOS.md (new)
  - docs/safety/SRS.md (one pointer line at the end of §4, as permitted)
invariants_touched:  none

summary:
  12 scenarios, SC-01 … SC-12. Eleven carry a full hazard → S/F/P → PLr →
  covering SF → Category/architecture → ISO 13849-2-style validation test →
  AT chain; SC-12 deliberately carries no risk graph and no PLr, because its
  subject (SF-09, supervision loss) is not a safety function.

  Every SF in SRS §3 is covered. SF-01 carries three scenarios (demand in
  motion, demand at rest against unexpected start-up, single broken channel);
  SF-05 carries two (the stopping duty and the inhibiting duty, because a
  design that implements only the first passes one and fails the other
  lethally). All six risk-graph parameter values are exercised; PLr b, c and d
  are reached; a and e are not, and §3.3 says why in both directions.

  Single-fault / Category 3 behaviour is demonstrated by SC-03 (open conductor
  in one channel of the two-channel e-stop loop), which separates the three
  mechanisms the Cat 3 sentence actually needs: polarity (wire NC / program NO
  makes the fault produce the safe reaction), redundancy, and discrepancy
  diagnosis.

  Honesty frame is §0, restated at the end as §5 for a reader who skipped it:
  no certification, no validation to ISO 13849-2, no SISTEMA, no MTTFd/DCavg/
  CCF/PFHd, no certified or selected components, no test executed. Every PL is
  a derived target, never an achieved figure. Section 5 also states explicitly
  that Category 3 does not imply PL d without adequate MTTFd and DC, neither of
  which is quantified here.

  Network independence is asserted per scenario rather than once: twelve
  reaction rows, all "none". SC-08 and SC-12 exist partly to demonstrate the
  network powerless rather than merely absent.

  N2 in §1.4 states, once and bindingly, that every scenario touching equipment
  the M3 demonstration cell also models refers to the F-CPU instance, that the
  demo cell has no F-CPU, and that its red mushroom is a process stop per
  ADR 0004 and opcua-nodes.md §9.6.

open_questions:
  - SC-11 is the one scenario where the SF mapping needed an argument rather
    than a lookup. The hazard (reset pressed with a person still in the zone)
    derives PLr d, while the SRS targets PL c for SF-08. Resolved in the
    document, not by adjusting either number, but by stating that the reset
    button is not what holds the hazard: SF-07 remains live and inhibited at
    PL d, and SF-08 cannot energize anything by construction. Owner should
    confirm this reading, since it is the presentation's sharpest claim.
  - SC-09 derives PLr c for the charger interlock while the SRS assigns it the
    PL d / Cat 3 group target. The document treats this as correct (PLr is a
    floor; the architecture is shared with SF-01 and exceeding the floor is not
    an error) rather than as a discrepancy. Owner should confirm.
  - Two severity choices are genuinely arguable and are flagged in place rather
    than settled: SC-06's S1 holds only under a layout precondition (free space
    behind the person at creep speed), and SC-09's S2 is retained only because
    the platform's charge voltage is not fixed at spec time.

srs_inconsistencies_found_not_fixed:
  1. **Stale gate numbers throughout SRS.md.** The SRS was written before
     ADR 0004 renumbered the gates. It says F-CPU functions are verified at
     M7, vehicle behaviours at M3/M4, the coupled zone scenario at M8, and arm
     safety at M9 (§1.3, §3 header, every "Verified at gate" cell in §4).
     Under docs/roadmap.md the safety layer is now **M9**, the simulated
     vehicle **M5**, the VDA 5050 client **M6**, the demonstration **M10** and
     arm integration **M11**. ADR 0004's "old numbering is kept" allowance
     covers reports and briefs by name; the SRS is a contract document, and
     its §4 traceability table currently points readers at gates that mean
     something else now. PL-SCENARIOS.md carries a one-paragraph note under §0
     recording the discrepancy and follows the SRS's numbering rather than
     silently diverging from it. Recommend a dedicated brief to renumber the
     SRS; not done here, as the brief forbids editing SRS.md beyond the
     pointer line.
  2. **SF-08 has a PL target but no Category.** SRS §5 gives "PL c for SF-08"
     without naming an architecture, while every other function gets
     "PL d, Category 3". PL c is reachable from Cat 1, 2 or 3 depending on
     MTTFd and DC, so the line is under-specified. In practice SF-08 inherits
     Cat 3 by construction, since it runs in the same F-CPU on the same F-I/O;
     PL-SCENARIOS.md SC-11 says "inherited, not separately designed" rather
     than inventing a category the SRS does not state.
  3. **SF-03's bumper latch is missing from the no-auto-resume list.** SRS §2
     lists the latched stops as SF-01, SF-02, SF-05, SF-06, SF-07, and names
     SF-03 as the exception. But SF-03's own reset row says bumper trips
     (physical contact) *do* latch and require the SF-08 onboard reset. The
     §2 row is therefore correct about the protective field and silent about
     the bumper. Minor, but it is the kind of line a reviewer reads as the
     summary and never checks.
  4. **AT-01 has no at-rest sub-test.** All four AT-01 observations are framed
     around a demand while the conveyor is running. SC-02's hazard is
     unexpected start-up with the cell idle, and its key observation — a
     transfer command refused while the latch is set — is not one of AT-01's
     listed cases. Flagged inside SC-02 and in the §4 mapping as an added
     observation for the plc agent when AT-01 is authored, rather than written
     into the SRS.

lessons_candidates:
  - 2026-07-27 | Mapped a scenario's derived PLr straight onto the PL target of
    the SF named in its title | The reset scenario (SC-11) derives PLr d while
    SRS targets PL c for SF-08, and the mismatch looks like an error until you
    notice the hazard is actually held by the still-inhibited SF-07 | A PLr
    belongs to the hazard, not to the function that happens to be named in the
    scenario title; state which function actually holds the hazard, and target
    the named function only against its own credible failure
  - 2026-07-27 | Derived the F parameter for a fault-injection scenario from
    how often the fault occurs | F in the ISO 13849 risk graph is the person's
    exposure to the hazard zone, not the fault rate, the demand rate or the
    machine's duty cycle; deriving it from the fault understates the risk | In
    any fault scenario, inherit S, F and P from the demand scenario the fault
    disables; only the required architecture changes, never the PLr
  - 2026-07-27 | Treated a PLr that came out above the SRS target as a document
    inconsistency to reconcile | It was the opposite in one direction and a real
    finding in the other: SC-09's PLr c under a PL d target is correct because
    PLr is a floor and the architecture is shared, while SC-06's PLr b under a
    function with no PL claim is a genuine gap the document must name | When a
    derived PLr and an implemented PL disagree, say which is the floor and which
    is the build, and never close the gap by re-arguing a parameter

next_suggested:      Verifier pass against the brief's done_when, then a small arch-docs or safety brief to renumber the SRS's gate references to the ADR 0004 order.
