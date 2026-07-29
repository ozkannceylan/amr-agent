# Report m4f-01b — steer-gating ruling and §10.12 closures

```
brief:               docs/briefs/m4f-01b-steer-gating-correction.md
status:              done
files_changed:       [docs/interfaces/opcua-nodes.md,
                      docs/reports/m4f-01b-steer-gating-correction.md]
invariants_touched:  none
open_questions:      2 — one mandatory follow-up edit in a file this brief
                     forbids, one narration sweep in plc/
next_suggested:      A one-file correction of `bridge-design.md` §1.1's steer row
                     and `plc/forklift/SPEC.md` §6.4/§7/§12, both quoting the now
                     -withdrawn exemption; drop-in text below
```

## The ruling, and where it landed

`opcua-nodes.md` §10.6 said two incompatible things about `ForkliftSteerAngleRef`.
The ruling in the brief is adopted: **all three setpoints, the steer angle
included, take `0.0` in the interlock-failed `ELSE`.** It ratifies what
`plc/forklift/SPEC.md` §6.4 already implements, so **no PLC logic changes** — only
the contract's own wording and the notes that quote it.

Five edits, all inside §10:

| Where | Change |
|---|---|
| §10.6 table row | The exemption sentence ("Steering is **not** gated to zero on a stop…") is **gone**. The row now reads: formed from `HmiSteerRequest`, clamped to the mechanical range, **gated to `0.0` exactly as the other two are**; `0.0` is a commanded centre, not a hold |
| §10.6, after the gating paragraph | The ruling, stated as a withdrawal rather than a silent deletion, with the three grounds: a hold needs stored state and the zero needs none (CLAUDE.md §9); one rule over three analogue outputs is what survives being read in a hurry; and what the exemption protected against does not occur, because all three assignments execute in the same call, so the wheel is re-aimed on a machine whose traction setpoint has already gone to `0.0`. **The visible consequence is stated**: the steered wheel returns to centre while the machine is stopping, in every stop scenario, and is not a defect. Reversing it is one branch in the PLC spec and one row here — no node, count, right or start value moves either way |
| §10.8 **P5** | "every motion setpoint" was the phrase the exemption was read out of (`plc/forklift/SPEC.md` §6.4 flags it as readable either way). Now **"all three setpoints of §10.6, the steer angle included"**, with the discarded reading named so it cannot be re-derived |
| §10.7 | The M4 conflation written out where teleop is defined: no start request exists, so `HmiTeleopRequest` doubles as enable and post-reset start, and the operator **releases and re-asserts** it after a reset — an enable held through the reset produces no edge and the machine stays stopped. The `ForkliftTeleopActive` row gains "**entered on a rising edge**, never restored by a returning permissive", which is what P5 already required of it |
| §10.12 | **Item 4 closed** by m4f-04: `TRACTION_SPEED_MAX` = 1.00 m/s meets the window-at-least-twice-the-cap relation at its bound (±2.00 ≥ 2 × 1.00), with the direction kept live — a higher cap re-derives the window *here* first (1.50 m/s would need ±3.00 m/s) and never tightens the margin. **Item 3 records the open request** for a `ForkliftDriveFault` node: until it exists, case D has no verdict on this plant, confirmed from the PLC side as SPEC §8 **case P**. **Item 7 added**: the `HmiStartRequest` request, post-gate, because a sixth request node moves the node count, the DB, a start value, the HMI write set and the enable edge together |

Nothing was renamed, no node was added, the count stays **18**, and no `plc/` or
`bridge-design.md` file was touched.

## The sweep, and the one statement I could not fix

Whitespace-normalised over every `.md`, `.py`, `.yaml`, `.sdf`, `.xml`, `.json`
and `.scl` file in the repo, for nine phrasings of the removed row. **Inside §10
nothing depends on it.** Outside it, two places quote the withdrawn exemption and
**both are on this brief's forbidden list**:

**1. `docs/interfaces/bridge-design.md` §1.1, the forklift no-logic table.** Its
verdict (the bridge does neither the clamp nor any centring — owner: PLC) survives
the ruling; its *reason* is now false, because it cites the exemption. Drop-in
replacement for that row's middle cell:

> Both are process decisions the PLC makes and states: the clamp is the PLC's, and
> so is the centring — all three setpoints, the steer angle included, are driven to
> `0.0` in the mandatory `ELSE` when the interlocks fail (§10.6), which is
> precisely why the transport must not do it (§10.7)

Its §7-side line "drive **every motion setpoint** to `0.0` in the mandatory `ELSE`
of §10.6" is not wrong, but wants "all three setpoints" for the same reason P5 did.
**Until this lands, two same-gate interface documents disagree** — the shape that
failed a gate on 2026-07-26 (LESSONS).

**2. `plc/forklift/SPEC.md`** carries the contradiction as *live*, in three places:
§6.4's subsection "The steer setpoint, and a contradiction in the contract
document" and its closing "is raised for correction … and is **not** resolved",
the §7 SCL comment above the steer assignment, and §12 item 2. All three are now
historically true but presently stale: the contract has ruled, and it ruled the way
the SPEC built. **No code or constant changes** — the fix is narration, and the
one-branch reversal note in §6.4 is worth keeping as the reversal path.

## Not edited, deliberately

- **ADR 0008 D2.3** says "every motion setpoint". An accepted ADR is never edited
  (CLAUDE.md §8); §10.6's ruling and P5 are the interpretive statement for that
  phrase, and they resolve it in the direction D2.3's own "mandatory `ELSE`"
  wording points. `hmi/README.md` quotes the same pattern and stays true.
- **§10.5's `ForkliftLinearSpeed` window** keeps its ±2.00 m/s and still declines
  to name the cap. Item 4's closure records the constant; the interface does not
  adopt it, or it would become a second owner of a PLC process decision.
- **Item 7 is a request, not a node.** Adding `HmiStartRequest` now would change
  §10.3's counts and rights mid-commissioning; the conflation is correct behaviour
  meanwhile, per the LESSONS 2026-07-27 rule it follows.

## Open questions

1. **The `bridge-design.md` row above needs an owner.** It is inside
   `docs/interfaces/` and therefore inside my write access, but explicitly on this
   brief's forbidden list, so it is requested rather than made. One brief, or one
   line appended to whichever revision touches that file next.
2. **`plc/forklift/SPEC.md` §6.4, §7 and §12 item 2** need the same treatment in
   `plc/`. Suggested wording: *ruled by `opcua-nodes.md` §10.6 — the exemption is
   withdrawn and the zero this document implements is what the contract now says.*
