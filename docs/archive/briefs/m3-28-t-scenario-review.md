# Brief m3-28 — independent review of T1-T4 as specified versus as run

gate:                M3
agent:               verifier
goal:                the T1-T4 scenario chain is reviewed end to end — specification, execution, and the two defects the live run surfaced — with each defect root-caused to a specific clause or code site
invariants_touched:  none
inputs:              [plc/demo-cell/SPEC.md (§7, §11, §6.2 as revised by m3-25 and m3-27), docs/reports/m3-26-live-loop-run.md, bridge/EVIDENCE_LATENCY.md Section B, bridge/EVIDENCE_SIGNAL_LOSS.md, bridge/evidence/*plcsim*.csv.gz, docs/interfaces/opcua-nodes.md, sim/worlds/ (the product sensor and belt geometry), docs/LESSONS.md]
deliverable:         docs/reports/m3-28-t-scenario-review.md
done_when:           each item below carries a finding with evidence; F1 and F2 each carry a root-cause hypothesis tied to a specific SPEC clause, signal mapping or geometry value, with the discriminating observation that would confirm it; and the report separates spec defects (agent-fixable) from program defects (owner-fixable) explicitly
forbidden:           [modifying any file except the deliverable report, committing, connecting to the live PLCSIM endpoint, running Gazebo or the bridge (work from the recorded evidence), proposing fixes as done rather than as recommendations]

## Review items

1. **T1-T4 as specified.** Are the four scenarios in SPEC.md §11 internally
   consistent after the m3-25 and m3-27 revisions, and do they still cover
   the four M3 exit criteria? Note anything a scenario assumes that the
   revised §6/§7 no longer guarantees.
2. **T1-T4 as run.** Compare the m3-26 report and Section B against the
   scenario definitions step by step: what ran as written, what deviated,
   what was skipped (case C, T4.8, T4.9b) and whether each skip reason
   holds.
3. **F1 root cause.** ProductPresentAtSensor never asserted in 394 s while
   the PLC's own ProductSensorRange node read 0.5400 m for 1.8 s against a
   100 ms filter. Candidate causes to discriminate, using the recorded
   CSVs and the SPEC text: the §6.2 window constants against the actual
   geometry (what range does the beam read with the product present versus
   absent — is 0.5400 m inside or outside PRODUCT_DETECT window?); the
   presence-timer call-site note m3-25 added to §6.5; the BridgeLinkOk
   gate on the verdict; a sampling interaction between the 100 ms filter
   and the 20 ms OB30 cycle. Name the confirming observation for the top
   hypothesis.
4. **F2 root cause.** Signal-loss case D ran 26 s undetected: the frozen
   read-back held non-zero speed (blinding D1) and §7 part 3 samples
   PositionRef once at motion start (blinding D2's 0.005 m freeze band
   against 0.62 m of travel). Confirm both mechanisms from the SPEC text
   and the caseD CSV, and state what a correct D2 would compare — a
   re-armed reference, a rate-of-change test, or something else — as a
   recommendation, not a decision.
5. **Interaction check.** Do the m3-25 dwell-timer form and the m3-27
   belt-feedback fault change what T1-T4 would do on a re-run — in
   particular, would F1's soft-limit runaway now be masked or altered by
   C5 dropping the cycle?
6. **Evidence hygiene.** Are Section B's figures traceable to the
   committed CSVs, and is every owner-outstanding item in §B.12 genuinely
   outside what an agent can produce?
