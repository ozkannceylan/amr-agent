# Report — m3-17 namespace correction in the PLC spec

brief:               docs/briefs/m3-17-namespace-plc-spec.md
status:              done
files_changed:       [plc/demo-cell/SPEC.md]
invariants_touched:  none
open_questions:      none
next_suggested:      Verifier check that opcua-nodes.md §2/§9, bridge config and SPEC.md §4.3/§10 now all read `http://DemoCell` and nowhere reads as chosen.

## What changed

Three namespace locations, all in `plc/demo-cell/SPEC.md`. No tag, BrowseName,
node count, constant or unrelated section was touched, and no claim of
verification in TIA Portal was added — the status paragraph of the header still
reads that nothing here was executed by the author. The namespace correction is
attributed in place to the owner's commissioning phase 0 finding of 2026-07-27
and cited to ADR 0006.

1. **§4.3 Server interface (was line 227).** The instruction "Set its namespace
   URI to `urn:amr-agent:cell:plc`" is replaced by: name the interface
   `DemoCell`; TIA Portal derives the URI as `http://<interface name>` and the
   field is not editable; the derived value is read back and confirmed, not
   entered; the bridge browses for `http://DemoCell`. The "namespace not found"
   explanation is kept, now attached to a misnamed interface rather than to a
   mistyped URI.

2. **§4.3 closing paragraph (was line 248).** "they share the namespace URI but
   no node" is replaced by: the M1 fleet-facing nodes live on a separate server
   interface carrying its own derived URI — one namespace per interface, none
   shared (ADR 0006). This is the assumption ADR 0006 D3 voids by name; left as
   written it would have kept implying a URI chosen once and applied to two
   interfaces.

3. **§10 step 6 (was line 841).** The click instruction now says: add the
   interface and name it `DemoCell`; the URI is derived as `http://DemoCell` and
   the field is not editable, so read it back rather than looking for somewhere
   to type it. The failure mode in the *Watch out for* column changed from "URI
   left at the CPU default" to "interface named anything else", which is the only
   way the mismatch can now occur.

## Verification of coverage

Searched the whole file for `urn:`, `namesp*`, `URI`, `brows*`, `index`,
`DemoCell`, `http://` and for chosen-value phrasings (`set its`, `set the`,
`chosen`, `configure the URI`, `type the`), case-insensitively, per the
whitespace-normalised-search lesson of 2026-07-27. The three locations above
were the only ones. `urn:amr-agent` now returns zero matches anywhere under
`plc/`.

Two namespace mentions were inspected and deliberately left alone:

- §10 step 9 ("browse the namespace, confirm 15 nodes") names no URI and is
  correct as written.
- §8's quoted-run phrases are history and were not in scope.

## lessons_candidates

- 2026-07-27 | Corrected a tool-derived value in a spec by replacing the value
  only | The same spec carried a second sentence built on the old value's scope
  ("they share the namespace URI"), which reads as correct until you know the
  derivation is per interface | When a tool-derived value is corrected, sweep for
  statements that depend on its *scope*, not only for the string itself; ADR 0006
  D3 had to name the dependent sentence for it to be found.
- 2026-07-27 | The spec told the commissioning engineer to *set* a value the tool
  computes | An instruction to enter a non-editable field wastes the reader's
  time before it fails | Where a value is tool-derived, the spec instructs the
  input that produces it (the interface name) and asks for the derived value to
  be read back as a confirmation step.
