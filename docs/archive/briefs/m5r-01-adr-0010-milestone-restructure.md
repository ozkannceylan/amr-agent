# Brief m5r-01 — ADR 0010: milestone restructure, forklift-first program

```
gate:                M4 (closing) / M5 (restructured, opening next)
agent:               arch-docs
goal:                ADR 0010 records, as accepted, the owner rulings of 2026-07-30
                     that collapse gates M5-M12 into three forklift-first gates
                     (M5 sensored autonomous forklift, M6 VDA 5050 fleet at scale,
                     M7 LLM operations layer with the final demonstration) and
                     remove the arm gate.
invariants_touched:  none changed. The ADR re-orders and merges gates on the
                     ADR 0004/0007/0008 precedent and supersedes ADR 0002's
                     platform selection. Invariants 1-13 stand; two invariant-
                     sensitive readings are recorded, not altered (see decisions
                     5 and 6).
inputs:              [docs/adr/0002-vehicle-platform.md,
                      docs/adr/0007-safety-first-gate-order.md,
                      docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md,
                      docs/roadmap.md,
                      docs/reports/m4-00-hermes-survey.md (decision list only),
                      the rulings block below]
deliverable:         docs/adr/0010-milestone-restructure-forklift-first.md
done_when:           the ADR states the seven decisions below with context,
                     consequences and rejected alternatives; the open decisions
                     in decision 6 are listed as open, with owner and briefing
                     point, and none of them is resolved in the ADR's own text;
                     relationships to ADRs 0002, 0007, 0008 and 0009 are each
                     explicit (superseded / extended / unchanged); status reads
                     accepted with the owner-approval date 2026-07-30.
forbidden:           [editing any other ADR, editing docs/roadmap.md or
                      docs/PLAN.md or docs/TODO.md or CLAUDE.md or README.md
                      (separate briefs), writing code, deciding any item listed
                      as open in decision 6, inventing scope beyond the rulings
                      block, mentioning any deadline or presentation]
```

## Rulings to record (owner-approved 2026-07-30, in session; the owner's own
## README commits 46caa95/0007b16/2a62d77 of the same day are corroborating intent)

1. **The forklift is the program.** All gates after M4 build on the in-house M4
   forklift. This supersedes ADR 0002's platform selection: RB-KAIROS is retired
   as the navigation platform; the in-house forklift model is the vehicle
   platform from M5 onward. ADR 0002's rejection reasoning stands as history;
   what changes is that the M4 gate produced exactly the modelling investment
   ADR 0002 declined to make.

2. **New M5 — sensored autonomous forklift.** One gate absorbs the former M5
   (safety layer) and M6 (simulated vehicle), both landing on the forklift twin
   rather than the fixed cell / RB-KAIROS:
   - Safety laser scanner(s) added to the forklift model, their signals wired
     into the F-CPU safety program's F-blocks (realism ruling; this widens
     ADR 0009's early cell-scope opening into the gate proper, so ADR 0009 is
     extended, not superseded).
   - A navigation lidar added; SLAM builds the map; Nav2 drives the forklift
     autonomously.
   - Stepwise module verification: each sensor's data is verified correct
     before anything is built on it (per-module evidence, not one end pass).
   - Gazebo visualizes the sensor beams in the GUI (the TurtleBot-style ray
     visualization).
   - HMI v2: inherits the M4 HMI, visually cleaner and less text-heavy; adds
     drive-mode selection (teleop / autonomous), an emergency button, and a
     real-time map view with live obstacles.
   - Exit shape: a realistic forklift with safety sensors and autonomous
     driving, controllable from the HMI, closed by a recorded safety +
     autonomy showcase.
   The former M6 vehicle-chain acceptance tests (AT-02, AT-03, AT-04, inhibit
   below the navigation stack) land here, on the forklift.

3. **New M6 — VDA 5050 fleet at scale.** One gate merges the former M7
   (VDA 5050 client), M8 (fleet manager) and M9 (PLC integration): an enlarged
   warehouse world with 5 loading stations, 5 unloading stations and 4
   forklifts; the fleet manager assigns transport orders over VDA 5050/MQTT
   and avoids traffic conflicts; the PLC owns the stations' fixed equipment
   and serves the station handshake over OPC UA to the fleet manager
   (invariants 3-6 unchanged). The former M9 acceptance tests (AT-05, AT-06,
   AT-09) and the fixed-equipment F-I/O (SF-05/06) land here with the
   stations. Entry condition: a deep-research brief precedes any
   implementation; its findings may propose splitting this gate internally,
   which would be a new owner decision. Closed by a recorded fleet showcase.

4. **New M7 — LLM operations layer, with the final demonstration.** An LLM
   agent (the owner's Hermes agent is the evaluation candidate, not a
   decision) supervises operations in real time, takes safe actions and
   alerts the user. Constraints carried verbatim from the former M12: the LLM
   never writes actuator outputs, never bypasses PLC interlocks, and the cell
   operates normally with the LLM and its transport unreachable. Entry
   condition: the owner decisions listed in docs/reports/m4-00-hermes-survey.md
   are ruled. The former M10 demonstration gate folds into this gate's
   closure: the recorded end-to-end run, the validation report and the README
   architecture narrative are M7 exit criteria, not a separate gate. The
   former M12 (Hermes command path, parked) is unparked and absorbed here.

5. **Arm gate removed.** The former M11 (arm integration) is removed from the
   roadmap entirely, not parked. SRS functions SF-20..29 are to be marked out
   of scope in docs/safety/SRS.md by a separate safety-spec brief; the ADR
   records the ruling and names that follow-up.

6. **Open decisions, recorded as open.** (a) The HMI real-time map view needs
   a data path the topology does not have — the HMI speaks only to the PLC,
   and a SLAM map cannot realistically transit OPC UA process nodes; the data
   path is decided in its own ADR at M5 briefing. (b) The HMI emergency
   button is read under invariant 1 as a process stop command plus a display
   of F-layer state — never a safety e-stop over the network; if the owner
   ever wants more than that, it is an invariant change needing its own ADR
   and is not being made here. (c) The LLM layer's attachment point and
   topology edge are decided at M7 briefing per the m4-00 decision list.
   (d) The internal structure of M6 (whether one gate or staged) is settled
   by the M6 deep-research brief.

7. **Numbering mechanics and recordings.** M0-M4 keep their numbers and
   criteria; M4 remains the current gate and closes on its recorded showcase
   plus the m4f-09 verification (the owner's README "done" mark is corrected
   to closing by the README brief). Old M5-M12 collapse to new M5-M7 as
   above. Existing brief/report filenames keep their written names (standing
   convention; a filename's number names its round). The embedded-recordings
   principle continues: commissioning showcase at M4, safety + autonomy
   showcase at M5, fleet showcase at M6, end-to-end demonstration at M7.

## Alternatives to record as rejected

- Keeping the fixed-cell safety showcase as its own gate: the owner archived
  it — the safety layer is built on the forklift twin instead (ADR 0009
  direction taken to completion); the fixed-cell F-I/O that remains follows
  its equipment to M6.
- Keeping PLC integration as a separate gate after the fleet gate: the M6
  stations are the fixed equipment; separating their PLC from their fleet
  would demonstrate the handshake against nothing.
- A separate final demonstration gate (former M10): folded into M7 by owner
  ruling; the M7 run is the end-to-end demonstration.
- Parking the arm instead of removing it: owner ruled removal; the SRS keeps
  the record via the out-of-scope marking, so nothing is silently lost.

## Git

Repo-local owner identity is already set for this session. Pathspec-scoped
commit of exactly the ADR file, conventional message in the style
`docs(adr): add ADR 0010 milestone restructure`. Report to
docs/reports/m5r-01-adr-0010-milestone-restructure.md in the standard report
format.
