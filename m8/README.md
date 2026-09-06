# m8 — per-vehicle propose → veto intelligence

Read `ARCHITECTURE.md` first, then `PLAN.md`. Status 2026-09-06: Phase
A0 is in the tree (`m8_core`, `m8_msgs`, H0 tests). Nothing consumes a
proposal yet — Phase A is shadow, the gate refuses all. Start at A1
only after H0 is green.

```
pytest m8/tests
```

No ROS is required for that suite.
