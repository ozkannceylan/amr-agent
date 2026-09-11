# m8 — per-vehicle propose → veto intelligence

Read `ARCHITECTURE.md` first, then `PLAN.md`. Status 2026-09-06: Phase
A0 is green (H0). Phase A1 **offline** is green (`EVIDENCE_A1_OFFLINE.md`,
79 passed): classical C1/C2/C3 cores, thin rclpy shells,
`launch/m8_shadow.launch.py`. The gate still refuses every proposal.
Plant benches E1/E3/E4/E5 are stubs (`NOT_RUN`). Phase B (abort live)
has not started.

```
pytest m8/tests
```

No ROS and no Gazebo are required for that suite. The shells import
rclpy only inside `main()`.
