# Brief m4f-04d — T5.4 procedure correction from the double's finding

```
gate:                M4
agent:               plc
goal:                SPEC section 11's T5.4 measures the property section 6.7
                     actually claims, and section 12 item 4 carries its
                     cross-reference.
invariants_touched:  none
inputs:              [docs/reports/m4f-04c-plc-logic-double.md (the finding and
                      the suggested correction), plc/forklift/SPEC.md sections
                      6.7, 11, 12, plc/forklift/double/check_kernels.py K4 (the
                      demonstrated correct form)]
deliverable:         plc/forklift/SPEC.md — section 11 T5.4 steps corrected,
                     section 12 item 4 cross-referenced
done_when:           T5.4 no longer releases the reset while the zone is
                     occupied only to re-assert after it clears (a fresh rising
                     edge the program honours by design); the corrected steps
                     test both properties the way K4 does — the reset refused
                     while the zone reads occupied, and a reset held
                     continuously across the zone clearing does not clear the
                     latch, with a fresh edge after cause-clear clearing it —
                     and the T5.4 pass count re-derives from its own corrected
                     step table; section 12 item 4 gains the cross-reference to
                     opcua-nodes.md section 10.12 item 7; the SCL, constants,
                     tags and every other section stay byte-identical (prose
                     and step tables only).
forbidden:           [any change to section 7 SCL, constants, tags or other
                      test scenarios, editing plc/forklift/double/, mentioning
                      any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly SPEC.md plus
your report docs/reports/m4f-04d-t54-procedure-correction.md; message style
`fix(plc): correct the T5.4 reset procedure per the double's finding`.
