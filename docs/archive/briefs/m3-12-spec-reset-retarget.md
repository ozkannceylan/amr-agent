gate:                M3
agent:               plc
goal:                Move the demonstration cell's monitored reset off the conflated start button and onto the real PanelResetPressed contact, so the spec the owner builds from matches the delivered cell and node model.
invariants_touched:  none
inputs:              [plc/demo-cell/SPEC.md, docs/interfaces/opcua-nodes.md §9.3, docs/reports/m3-11-panel-reset-node.md, docs/reports/m3-10-panel-reset-contact.md]
deliverable:         plc/demo-cell/SPEC.md, amended
done_when:           The spec reads 15 server-visible tags rather than 14 everywhere it states a count or lists them; PanelResetPressed is the reset device throughout; every trace of the gesture-based start/reset conflation is gone, including the hold timer and the CellResetRequired gating of the start edge that existed only to separate the two; and the reset remains monitored, edge triggered and non-auto-resuming.
forbidden:           [editing docs/interfaces/, sim/ or bridge/, inventing tags absent from opcua-nodes.md, describing the reset as a safety function or safety-rated, generating TIA project binaries, weakening the no-auto-resume rule, claiming any part of the spec has been verified in TIA Portal or PLCSIM]

## What changed underneath this spec

The spec was written when the cell had no reset device, so it had to put reset
on `PanelStartPressed`, separated by gesture (0.2–3 s hold, latch released on
the falling edge) and by state (a start edge honoured only when
`CellResetRequired` was false). The owner ruled on 2026-07-27 that the cell
gets a real reset contact. Both halves now exist and are committed:

- `adc9cd0` — `/cell/panel/reset`, `std_msgs/Bool`, **normally open**,
  momentary, verified against a running cell to energize nothing.
- `79a7f1e` — `DemoCell/Input/PanelResetPressed`, `Bool`/`Boolean`,
  **fail state FALSE**, start value FALSE, written by the bridge only.

## The five places m3-11 identified

Its report names five locations in this file, most importantly §3.1's "exactly
the 14 nodes" claim and its 14-row table, which become 15. **Verify the list
yourself by searching the file** — LESSONS records a brief whose enumerated
list was one short, and the fix for that is independent search, not trust.

## What must survive the change

The reset gets simpler, not weaker. All of this still holds:

- **Edge triggered.** A held or welded reset must not count as a reset. With a
  normally open momentary contact the rising edge is now the natural trigger,
  so the hold-timer machinery exists only to be deleted — but the *edge*
  requirement is not what was being deleted.
- **The reset energizes nothing.** It clears latches. It does not start the
  belt. Reset and start remain two deliberate, separate actions — that property
  was the point of the gesture separation and it must not be lost now that the
  devices are physically separate.
- **No auto-resume, stated per signal-loss case**, exactly as before.
- **Fail state FALSE is a safety-relevant property here.** Say why at the point
  of use: a normally open reset means a cut wire, a welded-open contact or an
  absent publisher all read false, so a broken reset cannot clear a latch. This
  is the opposite polarity to the two stop inputs, and a reader who assumes one
  convention across the panel will implement it wrongly.

## Watch out for

The old design used `CellResetRequired` to gate the start edge purely to keep
one button doing two jobs. Removing that gate is correct **only if** nothing
else depended on it. Check before deleting: if `CellResetRequired` still needs
to block a start for an independent reason, keep that behaviour and say why.
m3-11 also reworded §9.5 of the node model — no *client* may clear
`CellResetRequired` by writing a node — so confirm the spec agrees with that.

## Discipline

Nothing in this document is verified. You cannot run TIA Portal or PLCSIM, and
the status line must continue to say so. If the amendment reveals that another
document must change, name it in your report and leave it — `bridge-design.md`
already has a queued sweep and the two `bridge/` files have queued requests.

## Reporting

`docs/reports/m3-12-spec-reset-retarget.md` in the CLAUDE.md report shape, then
`lessons_candidates` (may be "none"). State the locations you changed, confirm
the count is 15 everywhere, and confirm no gesture-separation logic remains.
