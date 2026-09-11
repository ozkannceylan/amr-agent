# m8 — per-vehicle propose → veto intelligence

Read `ARCHITECTURE.md` first, then `PLAN.md`. Status 2026-09-11: Phase
A0 is green (H0). Phase A1 **offline** is green (`EVIDENCE_A1_OFFLINE.md`).
Plant benches **E1 and E3 have RUN** on the m5-ver3 plant
(`EVIDENCE_M8_E1.md`, `EVIDENCE_M8_E3.md`, results under
`bench/results/`): the classical C1 does not locate the pocket and the
classical C2 aborts on clean frames — measured, with the cause named,
nothing tuned. E4 / E5 are still stubs (`NOT_RUN`). H1 is therefore
**open**: it has numbers, not a pass. The gate still refuses every
proposal. Phase B (abort live) has not started.

```
pytest m8/tests
```

No ROS and no Gazebo are required for that suite. The shells import
rclpy only inside `main()`. The plant benches need the m5-ver3 stack up
in WSL (`./m5_ver3/m5v3.sh start --headless --localize amcl --nav --dock`)
and a shell with `GZ_PARTITION=m5v3 ROS_DOMAIN_ID=97`; anywhere else
they print `NOT_RUN` and exit 2:

```
python3 m8/bench/plant.py probe
python3 m8/bench/e1_pocket.py --frames 30 --ranges staging,1.5,1.0
python3 m8/bench/e3_abort.py  --frames 30 --ranges staging,1.5,1.0 --cycles 2
```
