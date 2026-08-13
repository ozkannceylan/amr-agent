# m5-74 — a bench panel for the stand-in writer

    gate:                M5
    agent:               bridge
    goal:                Give the writer's operator channel a small window that looks like the wiring bench it stands in for, so the safety inputs are driven by hand without typing commands.
    invariants_touched:  none. The panel adds no path, no seam and no authority the terminal did not already have.
    inputs:
      - bridge/standin_writer/standin_writer.ps1 — the command vocabulary and the state it keeps
      - bridge/STANDIN-WRITER-DESIGN.md — the writer's contract and its disclosure discipline
      - plc/forklift-safety/SPEC.md §7 and §11.3 — the eleven members and which are operator-driven
      - docs/safety/SRS.md B4 — the cell e-stop stops no vehicle, and why this panel is NOT a vehicle panel
      - docs/adr/0011.md D5 — the claim boundary
      - RUNBOOK.md — the panel changes the operating instructions in it
      - docs/LESSONS.md
    deliverable:         the panel, launched with or beside the writer, and a dated section in bridge/STANDIN-WRITER-DESIGN.md
    done_when:           The owner can bring the cell up, close the e-stop circuit, drive a shaped reset, trip and clear a zone, and read the link-driven channels — all from the panel, with the writer's log unchanged in content.
    forbidden:
      - putting any of this into hmi/. The HMI's F-layer pane states that nothing on that screen can write, clear or reset those lamps, and that sentence must stay true
      - adding a network path, a port or a service. The panel runs in or beside the writer's own process on the Windows side
      - giving the panel any control over a link-driven channel — the speed readings, the motion observation or the warning field. The writer refuses those from a human today and must keep refusing
      - a one-click reset. The hold is the mechanism
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. What this is, ruled by the owner 2026-08-07

**A bench panel, not a vehicle panel.** It imitates no real device and claims no
device exists. It presents the **safety input channels the writer stands in
for** — the wiring — and says so on its face.

The owner considered calling it the vehicle's control panel and ruled against
it, because the **vehicle e-stop is deferred to M6** and SRS B4 states the cell
e-stop stops no vehicle. A panel labelled as the vehicle's would imply a
function this gate does not have. This wording keeps the M6 work open and lets
the presentation say the honest thing: *this stands in for that wire.*

So the face of it reads as engineering equipment: **"Safety input channels —
engineering stand-in"**, with the writer's existing banner — **NOT A SAFETY
DEVICE**, no Category, no PL, no SIL, no PFH — at least as visible as it is in
the terminal today.

## 2. What it drives, and what it only shows

**Drivable — the operator channel, exactly what the terminal already accepts:**

| Control | Channel | Shape |
|---|---|---|
| E-stop | `EStopCircuitClosed` | open / closed, latching like a mushroom head |
| Zone device | `ZoneDeviceCircuitClosed` | open / closed — **and see §3** |
| Reset | `ResetButtonPressed` | **press and hold**, with the elapsed hold shown |

**Read-only — everything that arrives from a link:** the warning field, both
speed readings and their sequences, the motion observation, the heartbeat and
the API state.

That split is not cosmetic. The writer today **refuses** an operator command for
a speed, a motion flag or the warning field, and its refusal message says why:
*a human typing one would be inventing a measurement.* The panel must make that
impossible by construction — those are displays, not controls.

## 3. Two behaviours to preserve exactly

- **The zone channel belongs to the field link while one is up.** The writer
  already logs this: with a field client connected, the zone channel is the
  field's and is held FALSE until its first verdict. The panel's zone control
  must show that it is not in force when a link owns the channel — greyed, or
  plainly labelled — rather than appearing to work and doing nothing.
- **The reset is a hold and the F-program judges it.** 200 ms to 3000 ms, edge
  on release. A one-click button would hide the entire monitored-reset
  mechanism, which is a thing this project demonstrates rather than assumes.
  Show the hold as it runs.

## 4. What the panel must tell the owner that the terminal did not

Three facts cost the owner a live session on 2026-08-07, and none of them was
written anywhere they would look:

1. **The e-stop circuit boots OPEN.** Fail-safe and correct, but nothing ever
   closes it until a human does. The panel should make the boot state obvious
   at a glance rather than hiding it in a start-up line.
2. **The HMI's RESET is the process reset and cannot reach the F-side.** The
   panel is where the F-side reset lives, and it can say so in a line.
3. **A refused mode selection is consumed.** Not this panel's channel, but it is
   the third fact in the same failure and belongs in the RUNBOOK beside the
   other two — request it in your report.

## 5. Keep the log

The terminal log is evidence and several committed figures were read from it.
The panel is an input device, not a replacement: **the log's content does not
change.** If the panel makes a change, the log records it in the same words the
typed command would have produced.

## 6. Working discipline

- Read `docs/LESSONS.md` first.
- Demonstrate it against the live CPU: e-stop closed, reset held and accepted,
  a zone tripped and cleared, and the read-only channels moving on their own.
- **Do not commit.** The orchestrator commits by pathspec.
