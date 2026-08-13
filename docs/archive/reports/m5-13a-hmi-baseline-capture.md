# m5-13a — HMI baseline capture

brief:               none in `docs/briefs/`; task issued directly to the `hmi`
                     agent as m5-13a — bring up the existing M4 commissioning
                     HMI against a double and photograph it, as the baseline
                     HMI v2 inherits
status:              done

files_changed:
- `hmi/evidence/hmi-page-01-reset-required-2026-07-31.png` … `hmi-page-11-safety-demand-banner-2026-07-31.png` (11 PNGs, new)
- `hmi/evidence/capture-2026-07-31-m5-13a.log` (new) — the capture run's own output: the DOM readout printed immediately before each screenshot, plus every browser console message
- `hmi/tools/capture_screens.mjs` (new) — instrument: spawns the doubles, the plant driver and the HMI, drives Chromium through Playwright with real pointer events, screenshots, and stops every process it started
- `hmi/tools/screens_plant_driver.py` (new) — instrument: plays the bridge and the plant, holding the four `Forklift/Input/` nodes and `DemoCell/Link/BridgeHeartbeat` at values a JSON command file names. Writes no `Forklift/Hmi/` node and no `Forklift/Link/HmiHeartbeat`, and models no plant dynamics
- `hmi/EVIDENCE_HMI.md` — new **section H** (the eleven images, what each shows, the config and double behind it, and what is deliberately not shown); §C gains a dated note on why screenshots are now committed; §D's held-RESET residual row and §G.6's "no live-browser confirmation" row are struck through and pointed at H
- `hmi/README.md` — the `tools/` row now names the two new instruments

**No HMI source changed.** `hmi_server.py`, `static/index.html` and every config
are untouched; this task photographed the layer, it did not modify it.

invariants_touched:  none. The HMI stayed an OPC UA client of a loopback double
                     (invariant 4), wrote only the six HMI-writable nodes, and
                     formed no verdict; the plant driver writes only what the
                     bridge writes and the two writable sets stay disjoint
                     (invariant 10). No ROS 2, Gazebo, MQTT or VDA 5050 is
                     imported or referenced by either new file, and neither
                     endpoint left loopback (invariants 3, 8, 11)

open_questions:
- **A cosmetic defect in the M4 page, recorded in H.2 rather than fixed.** The
  RESET button looks identical held and not held: `button#reset` follows
  `button:active, button.held` in the stylesheet and an id beats a class, so the
  amber styling wins in both states. The fork-jog buttons, which carry no id
  rule, do light up. Behaviour is correct (`HmiResetRequest` goes `true`); only
  the operator's feedback is missing. Fixing it is an HMI v2 decision, not this
  task's, so nothing was changed.
- **Node and Playwright are environment tooling, not a proposed dependency.**
  `capture_screens.mjs` is the repository's first `.mjs` file and runs on the
  pre-installed `/opt/node22` with `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`.
  Nothing in `hmi/` imports it and the HMI's own venv is unchanged (plain venv,
  `asyncua==2.0.1`, `import rclpy` still fails). If the owner wants the images
  reproducible on the WSL2 machine, Playwright and a Chromium have to exist
  there too — otherwise section H's images are container-only, and section H
  says which environment produced them.
- **`.gitattributes` has no `*.mjs` rule.** `* text=auto` covers it and the file
  is run by `node`, not through a shebang, so the CRLF hazard of LESSONS
  2026-07-27 does not apply; flagged only because the file is a new kind for
  this repository and `.gitattributes` is outside this agent's write scope.
- **§C's "no screenshot is committed" was reversed, deliberately and in place.**
  The reasoning is written out in the dated note added to §C and in section H's
  opening. If the orchestrator wants that reversal in `docs/LESSONS.md`, the
  entry is the orchestrator's to append.
- Everything in section H is against doubles. Nothing was learned about the
  commissioned S7-1500, the TIA build or any F-CPU, and no image is a safety
  claim.

next_suggested:      HMI v2 briefs can quote section H figure-by-figure as the
                     "before" state; the RESET held-styling item is the smallest
                     concrete thing on that list.
