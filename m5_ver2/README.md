# m5_ver2 — the rebuilt vehicle, five frozen steps

The current system was rebuilt here step by step after the layered M5
accumulated more integration debt than it could shed in place. Each step
is a **copy** of the one before, changed for exactly one purpose, proven
against the live PLC, then frozen — a fix lands in the copy being worked
on, never backwards.

| Step | Added | Proof |
|---|---|---|
| [`step1/`](step1/) | E-stop chain end to end, HMI joystick, command gate | its `PROOF.md` |
| [`step2/`](step2/) | Three microScan3 safety scanners, field evaluation, monitoring case | its `PROOF.md` |
| [`step3/`](step3/) | Two encoder channels, fault injection, speed cross-check | its `PROOF.md` |
| [`step4/`](step4/) | The three-scanner teleop loop consolidated | its `PROOF.md` |
| [`step5/`](step5/) | **The current system:** autonomy (stations, router, roof-lidar guard, reverse-out), the teleop/auto mux, the warehouse sketch HMI, the simulated deploy | [`PROOF.md`](step5/PROOF.md) |

Steps 1–4 are frozen predecessors: read them, run their tests, never
edit them. `step5/` is the one that runs — the root
[RUNBOOK](../RUNBOOK.md) starts there.

[`CLAUDE.md`](CLAUDE.md) is this tree's ground truth: the PLC tag table,
the working agreements, and the facts about PLCSIM Advanced that are not
obvious. A future step 6 starts by reading
[`step5/CONTEXT.md`](step5/CONTEXT.md).
