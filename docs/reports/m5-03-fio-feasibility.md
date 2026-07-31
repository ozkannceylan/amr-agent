# Report m5-03 — F-I/O feasibility procedure (ADR 0011 D2 condition)

```
brief:               docs/briefs/m5-03-fio-feasibility.md
status:              done
files_changed:       [plc/forklift-safety/FIO-FEASIBILITY.md,
                      docs/reports/m5-03-fio-feasibility.md]
invariants_touched:  none — the procedure settles a tool question and changes
                     no design; invariant 1 is the reason ADR 0011 D2 wants the
                     path and is untouched either way the verdict falls
open_questions:      four, below — one is a brief/ADR attribution correction
next_suggested:      the owner runs it on a project copy and fills §7; the
                     result decides whether a SPEC §7 + §4.2-step-8 brief is
                     issued or whether SPEC §10 open item 1 closes as confirmed
```

`plc/forklift-safety/FIO-FEASIBILITY.md` is an owner-executable procedure, not a
specification: it builds nothing that survives it and it decides nothing. Header
states that it blocks the PLC half of M5 only and that the vehicle-side waves
proceed regardless, that its author has executed none of it, and that every value
it produces is a design value until a *Record* table carries it with a date
(ADR 0006). **§7 verdict is empty** — five blank question rows, a blank overall
verdict, and a blank owner sentence. No outcome is asserted anywhere; each step's
meaning table gives readings and what each would mean, never which one occurs.

**§0 makes the fallback genuinely inert.** ADR 0011 D2 says taking the fallback
"requires building nothing and removing nothing", which is true of the fallback
and not of the probe — adding a PROFINET IO system and an F-DI is a hardware
change to a build that currently compiles, downloads and runs (ADR 0009 context).
So the procedure runs on an **archived copy**, and every abort is "delete the
copy". That was not in the brief; it is what the ADR 0009 D4 pattern requires to
be true here.

**LESSONS discipline is §0.2**, applied once and referenced by every step:
in-force watch-table values never defaults; solid-green diff circles after every
download, with the F-collective signature online-vs-offline as the F-side
instrument; *Change device* re-verification extended to CPU-firmware and
safety-system-version changes; the `_1` collision sweep after every download
(adding a station mints tag names and an F-I/O DB); tool-derived identifiers
marked owner-verified-in-tool; and expectations stated as the rule.

**The five steps.** (1) Read the installed PLCSIM Advanced version and the
project's safety system version, plus CPU firmware and TIA version, against
F1/F2, with F4 handled explicitly — a V6.0+ installation is *not* an abort,
because an unverified list cannot answer either way and steps 2–4 then settle it
empirically; the remedy path is a safety-system-version change with its refusal
text recorded verbatim. (2) Configure an ET 200SP F-DI, compile, download, read
CPU RUN, safety mode activated and the F-runtime group executing, recording the
address range, PROFIsafe addresses, F-monitoring time and the generated F-I/O DB
name. (3) Read reintegration, `QBAD`, `PASS_OUT`, per-channel `QBAD_I_*` and
value status after STOP→RUN, with F5's warning that simulated value status does
not drive QBAD/PASS_OUT as real F-I/O does turned into an instrument: the three
are read together and a divergence is recorded rather than resolved. (4) The API
write **by tag name** — tag-list enumeration is the decisive read-back, the exact
tag string is recorded verbatim, and the value is read back three ways in the same
observation (API, watch table, QBAD/PASS_OUT) and held, because a write that
lands and reverts is `SPEC.md` §2.1 point 4 observed. F7's prohibition is made
binding: a by-address write is not a fallback for a failed by-name write, it is
the thing the manual forbids. (5) PIP 1 with SYNC_PI/SYNC_PO as pre/post
processing, run only if step 4 was a clean yes or a *timing-shaped* no —
determinism cannot create a channel that is not there.

Every step names its abort and sends it to §6, which states the fallback once:
the standard-DB stand-in, labelled a stand-in wherever it appears, carrying the
S015 validity check visibly in the F-code (F6), with D1 explicitly not reopened.

Nothing forbidden was written: no safety logic, no F-block network, no field
evaluation. §0.3 says so in the document and explains why the probe needs none —
the channel is observed at the process image and in the F-I/O DB, which is where
an operand takes its value from. Only `plc/forklift-safety/` and this report were
touched; nothing was committed.

## Open questions

1. **Brief/ADR attribution correction.** The brief's `done_when` item (3) says
   the F-I/O "reintegrates from the second cycle as **F2** predicts". F2 is the
   V4.0 manual's narrower version list; the reintegration-from-the-second-cycle
   statement, the 0/1 initialisation and the value-status/QBAD divergence are all
   **F5** (SIMATIC Safety programming manual A5E02714440-AM §10.7.4, §12.1). The
   document cites **F5**. Flagged rather than silently followed.
2. **"From the second cycle" is not observable in a watch table**, so §3 does not
   ask for it. It asks for the outcome F5 predicts — whether passivation clears
   without an acknowledgement — and explicitly forbids reporting a cycle count
   the tool did not print. If the orchestrator needs the cycle count itself, that
   is a different instrument (a trace/logic-analyser recording) and a different
   brief.
3. **A variation is a design change.** If the ET 200SP path fails where a
   centrally plugged F-DI or another F-I/O family might not, ADR 0011 D2 names
   ET 200SP specifically, so the document tells the owner to record and report
   rather than substitute. That decision, if it arises, is the owner's.
4. **A yes verdict licenses no keystroke.** The document says the follow-on —
   `SPEC.md` §7, the three pins at §4.2 step 8, and re-reading the AT-07 and
   AT-01 (c) consequences of §2.1 — is its own brief. `SPEC.md` §2.1 and §10 open
   item 1 are written as falsifiable and would need that revision brief either
   way: confirmed-by-observation on a no, rewritten on a yes.
