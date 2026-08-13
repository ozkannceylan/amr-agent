# Report m4f-04g — the SPEC's §6.5 caveat becomes agreement

```
brief:               docs/briefs/m4f-04g-spec-caveat-agreement.md
status:              done
files_changed:       [plc/forklift/SPEC.md,
                      docs/reports/m4f-04g-spec-caveat-agreement.md]
invariants_touched:  none
open_questions:      none
next_suggested:      nothing outstanding on the cap semantics in plc/ — the
                     SPEC, the double and the node model now say one thing
```

One sentence in §6.5, replaced by four that record agreement. **One hunk in the
whole file** (`@@ -660,5 +660,10 @@`), and nothing else moved.

## What the sentence said, and what it says

§6.5 quoted `opcua-nodes.md` §10.7's *old* meaning cell — "the carriage is raised
past the cap's height **and** the traction setpoint is being limited below what
the operator asked for" — and observed that it "could be read as the narrower
verdict", then justified implementing the wider one anyway. That was true when it
was written. `1618dff` replaced the cell with the wide reading, so the caveat was
quoting a wording that no longer exists and describing a live disagreement that
had been settled.

It now records the ruling in the form §6.4 already uses for the steer exemption:
**§10.7 now states this wider reading and the caveat is withdrawn** (commit
`1618dff`, 2026-07-29), the flag is `TRUE` *"while teleop is active and the
carriage is raised … regardless of the momentary demand"*, §10.7 names **"the cap
is biting"** as the discarded reading so it cannot be re-derived, and **the ruling
ratifies what this section already implements** — no statement, constant, tag or
start value moved on either side. The replaced conjunction is described as the
revision it replaces rather than presented as a live quotation of the contract.

**Both antecedents were preserved deliberately.** The paragraph immediately below
begins "Under a scale **the narrower verdict** collapses to…" and later says
"exactly the flicker **the wider reading** exists to avoid". Deleting the caveat
outright would have stranded both phrases, so the replacement still introduces
"the narrower verdict" (as the reading the replaced revision invited) and "the
wider reading" (as the one §10.7 now states). That paragraph is byte-identical —
the brief allows one sentence and it needed no more.

**The quotations were checked against the contract, not from memory.** All four
fragments I attribute to §10.7 appear verbatim in the current
`docs/interfaces/opcua-nodes.md`, and the old phrasing I describe as replaced is
confirmed absent from it. This matters because the defect being fixed was a stale
quotation of that same cell (LESSONS 2026-07-27: a spec value authored without
checking the source it cites is a design value, not a fact).

## Verification

- **§7 fence byte-identical including comments**, `sha256/16` `c46abb76835666b8`
  before and after — the same hash m4f-04b, m4f-04d and m4f-04e recorded — and
  **118 statement lines** both sides.
- **§3.1 tags, §3.2 statics, §3.3 constants byte-identical.**
- **§9 byte-identical**, section preamble and all five groups, including the
  Group 4 row m4f-04e touched.
- **§6.6 and §6.7 byte-identical**; §6.5 is the only section whose hash moved.
- **All 43 §11 step rows byte-identical**, all six pass counts untouched.

## Sweep

Subject sweep over the flag's name — `ForkliftSpeedLimitActive`, `SpeedLimit`,
`speed limit` — plus the phrasings a stale caveat takes (`could be read`,
`ambigu*`, `contradict*`, `arguably`), across the whole SPEC and
whitespace-normalised so a name wrapped across a line break still matches
(LESSONS 2026-07-27), read by subject rather than by the sentence the brief
quoted (LESSONS 2026-07-29).

Seven occurrences of the flag remain: §3.1's tag row, §4.3's browse tree, §6.5's
pseudo-code and its prose, §7's assignment, §9's Group 4 row, and four §11 T5.3
steps. **None describes the interface document as ambiguous, and none states the
narrow reading as the implemented one.** The `contradict`/`arguably` hits are
§6.4's steer ruling — a different subject, already written in the settled form —
and §10's stale-build tell.

## Note on the two items my m4f-04f report left open

Both were closed by other agents while this work ran, and I confirmed each in the
tree rather than taking it on report: `opcua-nodes.md` §10.6 and §10.7 in `3b944b2`
and `1618dff`, and the `sim/` finding marks in `1ed9b80`. No action was taken on
any of them here — `docs/interfaces/` and `sim/` are outside this agent's write
scope and on this brief's forbidden list.

## Scope notes

- Nothing outside `plc/forklift/SPEC.md` and this report was written.
  `plc/forklift/double/` and `docs/interfaces/` were not touched; the double's
  K2 kernel already carries the same wide reading in its own label (`ae08ebc`).
- The concurrent `hmi/` working-tree changes were neither read for this work nor
  staged.
- This document remains specification, not verification. The gate closes on the
  owner's PLCSIM run of §11.
