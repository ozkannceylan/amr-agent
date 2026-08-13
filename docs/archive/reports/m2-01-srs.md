brief:               docs/briefs/m2-01-srs.md
status:              done
files_changed:       [docs/safety/SRS.md]
invariants_touched:  none
open_questions:
  - SF-03 reset is the one documented exception to the section 9 no-auto-resume
    rule: the protective-field inhibit releases automatically after 2 s clear
    (ISO 3691-4 style practice), while motion restart still requires a fresh
    navigation command and bumper trips still latch. Justified in the SF-03
    table; owner should confirm this reading of the house rule.
  - Concrete numbers (100/200 ms reaction, 500 ms ramp, 0.3 m/s creep, 2 s
    clear time, 0.2-3 s reset window, 5 s watchdog) are proposed design
    targets; owner may adjust before M7 test authoring.
  - SF-05/SF-06/SF-07 assume dedicated F-I/O inputs (door safety switch,
    docked-position switch, zone device) separate from the standard program's
    process sensors; the plc agent must reflect this in the I/O plan at M7.
next_suggested:      Verifier pass against the done_when criteria, then close M2 in roadmap/PLAN/TODO.
