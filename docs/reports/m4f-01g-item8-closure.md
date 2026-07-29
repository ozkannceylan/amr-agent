# Report m4f-01g — §10.12 item 8 closed by the implementation

```
brief:               docs/briefs/m4f-01g-item8-closure.md
status:              done
files_changed:
  - docs/interfaces/opcua-nodes.md   (edited) §10.12 item 8 closed; the §10.8
                                     prose citation re-pointed — four lines
  - docs/reports/m4f-01g-item8-closure.md   (new) this report
invariants_touched:  none
open_questions:      two, listed below
next_suggested:      `sim/` — m4f-07b's open question 3: five statements in
                     forklift_commissioning.md go stale with 7675960, and H6
                     applies to the stimulus helper.
```

## What changed

**Item 8 is closed, naming the commit.** It was written as a request against `hmi/` with five asks;
all five are implemented and demonstrated, so the item now reads **Closed by `7675960`, 2026-07-29**
(`docs/reports/m4f-07b-h6-and-holdable-reset.md`), against `hmi/EVIDENCE_HMI.md` **§E** —
`check_hmi_h6_and_reset.py`, 34 checks, no failures, against the PLC logic double. Both kernels are
cited and distinguished rather than merged:

- **K1 (§E.2–E.3) is this item's closure.** The page's poll is frozen with the backend alive; all five
  requests read at rest 1063 ms after the last request against the 1000 ms window; the heartbeat
  increments straight through the drop; `HmiLinkOk` stays `TRUE` and `ForkliftResetRequired` stays
  `FALSE`. That is H6's process behaviour with nothing latched, and recovery follows the release rule —
  a page that thaws holding both Bools asserted gets neither carried.
- **K2 (§E.4) is the same commit's other half**, `plc/forklift/SPEC.md` §11 T5.4 driven from the
  operator's endpoint. It closes `m4f-08` finding 3, **not** this item, and the row says so, so a later
  reader does not conclude the held reset was ever an interface request.

**The residual is carried, not erased.** Item 8 records that `EVIDENCE_HMI.md` §D holds an unrun
pass: section C's browser exercise predates the change and was not re-run, so the page's DOM handlers
are unexercised since — E.4 drives the endpoint the page posts to, not the events themselves. The row
states that it is `hmi/`'s to close and that it does not reopen this item, which is the honest reading:
the backend behaviour H6 specifies is demonstrated, the markup that drives it is not re-demonstrated.

**Both citations now point where the closure lives.** §10.8's prose and item 8 previously quoted
"`EVIDENCE_HMI.md` §D's 'a browser that crashes with the joystick held'". That row still exists in §D
but now reads struck through and closed, so quoting it as the open gap was the superseded wording. Both
now cite **§E**, and the only remaining §D reference in the document is the new one, for the residual —
which is genuinely what §D carries.

**Nothing else changed.** Four lines: three in item 8's cell and its owner cell, one in the §10.8 prose
bullet. No H-rule or P-rule was touched, no node, count, constant, start value or access right moved,
and §10.12's other seven items are byte-identical.

## Sweep

Every `EVIDENCE_HMI.md` citation in the document, and every occurrence of `§D` and `§E`, checked by
line: **two** citations existed and **both** were re-pointed; the document now carries one §D reference
(the residual, correct) and four §E references (the closure, §E.2–E.3 for K1, §E.4 for K2). The §A.8,
§A.9 and §B.8 citations inside item 8's H5 half were left untouched — m4f-07b's scope notes confirm
H5's two paths are unchanged and were re-verified by the pass A re-run (checks `G`, `I`, `H`), so those
citations are still accurate.

## Open questions

1. **m4f-07b's consequence reaches `sim/`, and this document cannot carry it.** H6's window is over the
   page's *requests*, so any instrument that drives `/control` and then waits more than one window is a
   crashed browser and is correctly treated as one. `sim/scenarios/forklift_stimulus.py` needs the same
   standing beacon the two `hmi/` harnesses gained, and
   `sim/scenarios/forklift_commissioning.md` carries five statements that the reset can be held "only
   by re-posting above the write rate" which 7675960 makes stale. Both are m4f-07b's open question 3,
   owned by `sim/`.
2. **The gate-facing residual is unchanged by this bookkeeping.** Everything in §E is against the PLC
   logic double on loopback; PLCSIM was never contacted, and §10.12 item 1 still stands — every value
   in §10 is a design value until the owner reads the `Forklift/` subtree back out of the tool.
