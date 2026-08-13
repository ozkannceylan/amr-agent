# Report — m5-45 SLS/SS1 standards research

    brief:               docs/briefs/m5-45-sls-standards-research.md
    status:              done
    files_changed:
      - docs/safety/SLS-STANDARDS-BASIS.md   (new — the deliverable)
      - docs/reports/m5-45-sls-standards-research.md (this report)
    invariants_touched:  none
    open_questions:
      - U2/U4 (see deliverable §1): the PLr ISO 3691-4 assigns to speed
        control specifically, and ISO 13849-1's SRP/CS wording, are unreached;
        both are marked with what would settle them. Nothing found blocks
        phase 3.
      - The owner's ruling on §4 of the deliverable: whether phases 3 and 4
        gate M5. Recommended yes (SRS traceability already commits SF-10/
        SF-11 to M5, and SF-03's R3 residual is carried by SF-10); the
        contrary ruling requires an SRS restatement brief.
    next_suggested:      Owner rules on §4; then brief phase 3 with the two
                         design-spec wording amendments requested in §5.

## Summary

All five of the design's decisions **survive**; none is contradicted. The
big one — decision 5, standard program limits while the F-program monitors
and demands — is not merely defensible but is the certified pattern verbatim:
the Siemens G120 Safety Integrated manual (04/2018, read in full at the SLS
sections) places "the inverter limits the speed setpoint" in its **standard
functions** column while the safety side monitors actual speed and executes
the safe stop, and declares that architecture conformant with IEC/EN
61800-5-2's SLS definition. The owner is right **in effect but by
consequence, not by clause**: no reached source shows a placement rule
naming a safety PLC; the mechanism is that the safety *function*
(measurement + monitoring + reaction) must meet the PLr the risk assessment
assigns, so it lands in the safety layer wherever a PLr stands — while the
limiting itself is standard logic earning no safety credit. Function homes
confirmed at attribution level: IEC 61800-5-2 defines STO/SS1/SLS; ISO
3691-4 (type C, driverless trucks) requires *functions at a PLr* — per the
TÜV Rheinland whitepaper: personnel detection and braking SRP/CS at PLr d,
27-function table at "4.11", and 0.3 m/s max with detection muted, which
independently corroborates the SRS's figure. Decision 2 (two channels, one
shaft) matches real safe-encoder practice (HEIDENHAIN: two independently
generated position values cross-compared by the safe control; SIL2/PLd as a
single-encoder system) with two requested wording amendments: real
single-encoder systems are classed "single-channel tested systems", and the
shared-shaft hole is handled in reality by mechanical **fault exclusion**
(EN 61800-5-2 Table D16, as HEIDENHAIN cites it), so the design's
motion-present check should be labelled a stand-in for that. Normative texts
were never reached and no clause number is stated except as a source cites
it; two automated PDF summaries returned fabricated quotes during the work
and every quotation in the deliverable was re-verified against locally
extracted source text.
