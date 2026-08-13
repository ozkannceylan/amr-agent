# Brief m5-03 — F-I/O feasibility in the tool (ADR 0011 D2 condition)

```
gate:                M5
agent:               plc
goal:                an owner-executable procedure that settles, in TIA Portal
                     and PLCSIM Advanced, whether the scanner can reach the
                     F-program through configured F-I/O driven by the PLCSIM
                     Advanced API — the condition ADR 0011 D2 rests on.
invariants_touched:  none
inputs:              [docs/adr/0011-sensored-autonomy-architecture.md (D2 and
                      facts F1-F5), docs/adr/0009-early-cell-scope-safety-on-
                      the-forklift-twin.md (the feasibility-checkpoint
                      pattern), plc/forklift-safety/SPEC.md sections 1 and 10
                      and its open item 1, docs/LESSONS.md]
deliverable:         plc/forklift-safety/FIO-FEASIBILITY.md — a procedure the
                     owner runs, with a verdict section left blank for the
                     owner to fill
done_when:           the procedure has numbered steps, each with what to do,
                     what to read back, and what the reading means; it settles
                     in order (1) the installed PLCSIM Advanced version and the
                     project's safety system version, read from the tool and
                     written down, against the supported list in ADR 0011 F1;
                     (2) whether an ET 200SP F-DI can be added to HW config,
                     compiled and downloaded with the CPU reaching RUN and the
                     F-runtime group executing; (3) whether the F-I/O
                     reintegrates from the second cycle as F2 predicts, and
                     what QBAD/PASS_OUT/value-status actually show, given that
                     simulated value status does not drive QBAD as real F-I/O
                     does; (4) whether the PLCSIM Advanced API can write that
                     F-DI's channel values BY TAG NAME, and what the F-program
                     reads when it does; (5) whether SYNC_PI/SYNC_PO
                     registered as pre/post processing of the F-runtime group
                     changes the picture; each step names the abort condition
                     that sends the design to the ADR 0011 D2 fallback, and
                     the fallback's own consequence (the standard-DB path
                     labelled a stand-in, carrying the S015 validity check
                     visibly in the F-code) is stated once at the end.
forbidden:           [specifying any safety logic, F-block network or field
                      evaluation — this brief settles a tool question only;
                      editing plc/forklift/SPEC.md or plc/demo-cell/SPEC.md;
                      editing files outside plc/forklift-safety/; asserting
                      any outcome as known — every step's result is the
                      owner's to write; recording a version number the tool
                      did not print; committing (the orchestrator commits)]
```

## Discipline this procedure must carry

From LESSONS, because each has already cost this project a session:

- Read values from the **watch table's in-force values**, never from interface
  defaults; a Default value governs nothing once the instance DB exists.
- After every download, check the block diff circles are **solid green**
  before testing; a stale build shows as monitoring-error icons and in-force
  values that contradict the code.
- After any **Change device**, re-verify the server interface, access control
  and runtime licence, then re-download.
- Sweep browse names for TIA's silent **"_1" collision suffixes** after every
  download; it appends them without asking, in DB statics and interface rows
  both.
- A **tool-derived identifier** is a design value until it has been read back
  from the tool; mark every such value as owner-verified-in-tool.
- State an expectation as the **rule**, never as the single value one
  observation produced.

## Framing

Write it as the ADR 0009 feasibility checkpoint was written: a short ordered
procedure whose purpose is to settle a question, not to build anything. The
verdict section stays empty until the owner runs it. Note in the header that
this procedure blocks the PLC half of M5 and nothing else — the vehicle-side
waves proceed regardless of its outcome.

Do not commit. Leave the file untracked and write your report to
docs/reports/m5-03-fio-feasibility.md.
