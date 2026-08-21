# m5/ — the Milestone 5 archive

Milestone 5 (teleoperated forklift with a live safety chain: two scanners,
dual encoders, an F-CPU between the HMI and the plant) exists in this repo
in **two builds**, and they are not the same animal:

| Folder | Build | Verdict |
|---|---|---|
| [`m5_ver1/`](m5_ver1/) | The first build, designed under Claude supervision: the full layered stack, recorded on video in August 2026 | **Ran, and was unmaintainable.** Kept runnable through a virtual PLC. Read its [post-mortem](m5_ver1/PLC-PROGRAM.md) |
| [`../m5_ver2/`](../m5_ver2/) | The hand-rebuilt stack: the same milestone re-earned in verified steps, each frozen with a PROOF | The professional safety PLC. Its final step is the repo's current system — and since 2026-08-20 it too runs without PLCSIM (`step5.py --virtual`) |

Why the first build is kept at all: it is the reference for the layered
architecture that M6 scales, its ADRs (`docs/adr/` 0001–0015) remain the
permanent record, and — since 2026-08-21 — it runs again without PLCSIM
Advanced, so its failure modes can be studied live rather than imagined.

Start at [`m5_ver1/README.md`](m5_ver1/README.md).
