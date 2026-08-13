# Report m4f-04f — the double's K2 label matches the scale ruling

```
brief:               docs/briefs/m4f-04f-double-k2-label.md
status:              done
files_changed:       [plc/forklift/double/check_kernels.py,
                      plc/forklift/double/EVIDENCE_DOUBLE.md,
                      docs/reports/m4f-04f-double-k2-label.md]
invariants_touched:  none
open_questions:      one — the node model's own cap wording, still open from
                     m4f-04e and not reachable from plc/
next_suggested:      the interface clause on opcua-nodes.md §10.6/§10.7, which
                     is the last document where "reduced by the cap" can still
                     be read as a clamp
```

One string in `check_kernels.py`, one interpretation row and one appended run in
`EVIDENCE_DOUBLE.md`. **`logic.py`, `server.py` and `config.yaml` are
byte-identical** — `git diff` on them is empty — so nothing under test moved and
the re-run is not a re-measurement.

## The label, and the assertion under it

```
-    check("the cap LIMITS, it does not command (0.2 x 0.30 = 0.06)",
+    check("the cap SCALES the request, it does not clamp the full-scale product "
+          "(0.2 x 0.30 = 0.060, not 0.20)",
           abs(s["ForkliftTractionSpeedRef"] - 0.06) < 1e-6)
```

**The assertion line is untouched**: same node, same `0.06`, same `1e-6`
tolerance. It was always testing the scale's number — the defect was only ever in
what the check called itself, which is why m4f-04e could rule the SPEC to the
scale while citing this kernel's arithmetic as agreeing with it.

The two neighbouring K2 labels already said `demand x TRACTION_SPEED_MAX = 1.00`
and `demand x TRACTION_SPEED_CAP_RAISED = 0.30` — the scale, correctly — and were
left alone. So was `'in force', not 'biting'`, which labels
`ForkliftSpeedLimitActive` rather than the arithmetic and which `SPEC.md` §6.5 now
defines under the scale.

## The run

Fresh server, one endpoint, **`opc.tcp://127.0.0.1:4851/`**. 4850 was free when
checked, but a concurrent agent may take it at any moment, so this instance was
put on 4851 to make a collision impossible in either direction; the port is
recorded in the evidence beside the transcript. 4840 (PLCSIM Advanced) and
4842–4846 (the bridge's doubles) were never bound, and `server.py` refuses to
start on them. **PLCSIM Advanced was neither contacted nor started.**

`exit 0`, and `all kernel checks passed` as the harness printed it. **The harness
prints no count of its own**, so the evidence states 48 as a count of `PASS` lines
in that transcript, explicitly labelled as a count of the transcript rather than a
figure the tool reported — the same discipline the connect-conformance figure had
to be corrected to (LESSONS 2026-07-27). No `FAIL` line. 48 also matches the check
count the earlier reproduce run recorded, which is the expected result of moving a
label and nothing else.

K2's three printed values are `1.000`, `0.300` and `0.060` — identical to the run
above it in the file. K5 measured **643 ms** against 642 ms and 643 ms previously;
third-digit scheduler noise on a Python loop, inside the same window, and stated
as such rather than as a new claim.

**The run was driven to completion in the foreground and the session ended by
observation**, not assumption: the server was killed, `ss -ltn` then showed 4851
free, and no process from the venv survived (LESSONS 2026-07-27, 2026-07-28).

### Two things worth naming about the capture

- **The old transcript was not edited.** It still carries `the cap LIMITS, it does
  not command` and its 4850 endpoint. A corrected label is proven by re-running,
  not by rewriting the record of a run that used the old one, and the appended
  section says so where a reader meets the discrepancy.
- **Standard error carried exactly one line**, `Requested session timeout to be
  3600000ms, got 600000ms instead`. It is the `asyncua` client's own log, not
  harness output — I ran once with the streams combined and once with them
  separated specifically to establish which stream carried it, and quoted the
  separated run. It is recorded in the evidence with the `granted = min(request,
  cap)` reading (LESSONS 2026-07-28) and with the note that it bears on no kernel
  and is a property of this Python server, not of the CPU.

## One edit beyond the brief's literal deliverable, and why

The brief names the check label and the appended run. I also rewrote the **K2 row
of "What each kernel actually establishes"**, which said "the cap limits rather
than commands". Left alone it would have contradicted the run appended below it
in the same file — one document disagreeing with itself, which is the failure
mode LESSONS 2026-07-26 records. The row now states the scale, keeps the same
numbers (they never changed), and names the relabel so the older transcript above
it is not read as a defect. **It is interpretation, not transcript**, so editing
it breaks no evidence rule; the brief's forbidden list protects the transcript,
and the transcript is untouched.

## Open question

**`docs/interfaces/opcua-nodes.md` §10.6 is the last document where the clamp
reading survives**, carried over unresolved from m4f-04e. Its
`ForkliftTractionSpeedRef` row says the setpoint is "formed inside the PLC from
`HmiTractionRequest` scaled by `TRACTION_SPEED_MAX`, **reduced by the fork-height
speed cap when it applies**" — *reduced* reads either as the scale factor swapping
(what §7 builds, what this kernel now says) or as the product being clamped. The
document does not rule, and §10.12 item 4 states these are PLC constants it does
not set, so nothing is in conflict; but it is where the confusion originated.
**Requested of `interface`**: one clause on that row and the matching one on
§10.7's `ForkliftSpeedLimitActive` description. Not reachable from `plc/`.

## Scope notes

- Nothing outside `plc/forklift/double/` and this report was written. `SPEC.md`
  was not touched by this brief — its correction is m4f-04e, commit `bc6a570`.
- **No dependency was added**, and no new file was created in `plc/`. The run used
  the bridge's existing venv (`asyncua` 2.0.1), which is what the earlier runs in
  this evidence file used.
- The concurrent `hmi/` working-tree changes were neither read for this work nor
  staged.
- **Nothing here is evidence for the gate.** The double is a transliteration of
  `SPEC.md` §7; the gate closes on the owner's PLCSIM run of §11.
