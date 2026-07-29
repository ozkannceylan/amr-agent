brief: docs/briefs/m5a-07-hmi-safety-lamps.md
status: done
files_changed:
  - hmi/hmi_server.py (5 Hz status poll extended: `Forklift/Safety/` resolved
    as an optional group at connect, graceful when absent; `Published`/
    `_poll_metrics` gain a `safety` section. Zero write-side change:
    `HMI_WRITABLE_PATHS`, `WRITE_VARIANT`, `REQUEST_ORDER`,
    `validate_config`'s write check, `Controls`, `_write`, `_writable` are
    byte-for-byte unchanged)
  - hmi/static/index.html (new `#safetybanner`, visually distinct from
    `#stopbanner`; four new lamps in their own section, greyed "not present"
    when the group is absent; one-line "displays and never commands"
    statement; `renderSafety()`. Joystick/enable/reset markup and handlers
    untouched)
  - hmi/config.yaml, hmi/config-double.yaml, hmi/config-logic-double.yaml
    (four new `read:` entries for the mirror group, identical across all
    three)
  - hmi/config-safety-mirror-double.yaml (new — this layer's own double
    instance, port 4860, HTTP 8093)
  - hmi/tools/safety_mirror_double.py (new — minimal, independent OPC UA
    double serving `Forklift/` with the section 11 mirrors optional;
    imports nothing from bridge/ or plc/)
  - hmi/tools/check_hmi_safety_mirrors.py (new — evidence harness, two
    modes, `absent` and `present`)
  - hmi/EVIDENCE_HMI.md (appended section G, quoted as printed, dated
    2026-07-29)
  - hmi/README.md (file table and "What it is" section updated to name the
    new capability, config and tools; no boundary statement changed)
invariants_touched: none
open_questions:
  - No commit was made. My hard rules state "Do not commit. Leave changes
    in the working tree; the orchestrator commits by pathspec," which
    conflicts with this brief's own "Git:" line and your message, both of
    which ask me to commit. I followed the hard rule and left everything
    uncommitted. Pathspec for your own commit: hmi/hmi_server.py
    hmi/static/index.html hmi/config.yaml hmi/config-double.yaml
    hmi/config-logic-double.yaml hmi/config-safety-mirror-double.yaml
    hmi/README.md hmi/EVIDENCE_HMI.md hmi/tools/safety_mirror_double.py
    hmi/tools/check_hmi_safety_mirrors.py
    hmi/evidence/harness-2026-07-29-m5a07-absent.log
    hmi/evidence/harness-2026-07-29-m5a07-present.log
    hmi/evidence/hmi-2026-07-29-m5a07-absent.log
    hmi/evidence/hmi-2026-07-29-m5a07-present.log
    "hmi/evidence/hmi-cycles-2026-07-29-m5a07-present-20260729T173633Z-pid19556.csv"
    docs/reports/m5a-07-hmi-safety-lamps.md. Do NOT sweep in
    hmi/evidence/harness-2026-07-29-m4f07c-pass{A,B}.log or
    hmi/evidence/hmi-cycles-2026-07-29-m4f07c-pass{A,B}-*.csv, which are
    untracked leftovers from an already-closed brief
    (EVIDENCE_HMI.md §F.4 records them as deliberately not part of that
    fix's commit either) — a bare `git add -A`/`git commit` would catch
    them.
  - The brief and opcua-nodes.md §11 disagree on the lamp count (brief:
    "three lamps"; §11.8 item 5: the fourth, SafetyResetFault, is
    "hmi/'s decision" and §11 "does not enlarge that ask"). Your message
    explicitly said "four lamps," so I built four
    (EStopDemand, ZoneStopDemand, SafetyResetRequired, SafetyResetFault),
    which is within what §11.8 item 5 permits. Flagging the brief-text/
    interface-doc/instruction mismatch in case it was meant to be resolved
    differently.
  - Cross-platform finding, informational, nothing in this deliverable
    depends on it: on native Windows, `subprocess.Popen.terminate()` calls
    `TerminateProcess()`, which `hmi_server.py`'s Python-level SIGTERM
    handler cannot catch — unlike WSL2, where every prior EVIDENCE_HMI.md
    section was produced and where a real SIGTERM reaches the handler.
    §10.8 H5's clean-shutdown log line and final evidence flush therefore
    do not fire on this platform when a harness stops the process this
    way; my harness works around it for its own CSV by waiting out one
    2.5 s flush period first (see EVIDENCE_HMI.md §G.5). No code in
    hmi_server.py was changed for this; it is a fact about running this
    layer's existing tooling outside WSL2 for the first time, not a defect
    this brief introduced.
  - Found incidentally while regression-testing against
    plc/forklift/double/server.py (read-only use, nothing in plc/ changed):
    hmi/tools/check_hmi_teleop_loop.py's `DoubleControl.stop()` calls
    `os.killpg`/`os.getpgid`, which do not exist on native Windows, so the
    harness crashes with `AttributeError` after all of its own checks have
    already printed "ok" and "no failures" — the double process is then
    left orphaned (I killed the two stray instances this produced by PID
    after confirming the harness's actual checks all passed). Pre-existing,
    unrelated to this brief, inside hmi/tools/ but out of scope for a
    one-brief-one-deliverable change; noted for a future brief if
    Windows-native evidence runs are wanted for that harness (and
    check_hmi_h6_and_reset.py, which shares the same `DoubleControl` class).
  - No live-browser, DOM-rendered confirmation of the grey "not present"
    styling or the violet banner's visual distinctiveness — verified
    instead through the `/state` data contract and the served page's raw
    markup (EVIDENCE_HMI.md §G.1-G.3), the same kind of gap section C/D
    already record for this layer and state rather than hide.
next_suggested: none — brief closed. If the owner wants a fourth
  Windows-native regression pass of check_hmi_writes.py (against
  bridge/test_double/, which needs the amr_bridge package importable) that
  is additional confidence, not a gap in this brief's own done_when.
