# m5-11 — envelope gate node

    brief:               docs/briefs/m5-11-envelope-gate-node.md
    status:              done

    files_changed:
      - agv/forklift/scripts/envelope_gate.py            (new) the gate node
      - agv/forklift/scripts/envelope_run.py             (new) the topic double + harness
      - agv/forklift/launch/envelope.launch.py           (new) the gate's measurement stack
      - agv/forklift/EVIDENCE_ENVELOPE.md                (new) the measured runs
      - agv/forklift/evidence/m5-11-*                    (new) 57 recording files, 928 kB
      - agv/forklift/config.yaml                         (mod) `envelope:` constants + 8 topics
      - agv/forklift/launch/navigation.launch.py         (mod) gate started, cmd_topic default
      - agv/forklift/README.md                           (mod) contract table, file table, running it
      - docs/reports/m5-11-envelope-gate-node.md         (this file)

    invariants_touched:  none

## What was built and measured

The gate sits **below** the velocity smoother, in the chain by default
(`navigation.launch.py` starts it and `cmd_topic` now defaults to
`/cmd_vel_gated`; `gate:=false cmd_topic:=/cmd_vel_smoothed` restores the
m5-10 chain). All six acceptance observations were measured **on the
owner's WSL machine**, not in a container, each with its command:

| # | Observation | Result |
|---|---|---|
| 1 | enable drops at 0.40 m/s | stop in **0.850 s / 0.1738 m**; the gate's own 0.50 m/s² ramp, largest emitted step 0.0250 m/s — **not** an abrupt zero |
| 2 | envelope goes stale | detected **0.5176 s** after the last message against the **0.500 s** window; stop **1.320 s / 0.3715 m** |
| 3 | ceiling clamp, four values | emitted **at** the ceiling (mean = max = ceiling) at 0.40/0.20/**0.10** m/s; ratio exactly 1.0000 at 0.60 |
| 4 | gate release, OPEN vs CLOSED | step **+0.5000 m/s / 3.5249 m/s²** open-loop against **+0.0250 m/s / 0.4096 m/s²** closed-loop — **20×** and **8.6×** |
| 5 | pass-through fidelity | residual **0.000e+00** on both components, **221 of 221** exact; added latency 0.4 ms mean |
| 6 | equipment permit | conservative reading implemented: permit FALSE stops. Stop distance **0.1735 m**, within **0.3 mm** of the enable drop |

Plus the deployed chain under a real Nav2 goal (§10), and the D5.3
readback exercised (§9).

**One defect was found by measurement and fixed.** The first build
released the actuator topics at the *last step* of its stop ramp, so the
converter's last emitted value was 0.0250 m/s and `forklift_io` republished
it forever: the vehicle **crept 0.0852 m in 3.3 s** and would have kept
going. The release now waits for an explicit zero. Both runs are in the
evidence.

## open_questions

1. **`opcua-nodes.md` §12 specifies four data without specifying this
   consumer's reaction.** Four conservative readings were implemented and
   named in the code and evidence §2; each can only make the gate more
   restrictive. **Interface agent's call, not taken here**: (a) the
   equipment permit's motion effect — the gate makes `FALSE` a term of the
   gate law; (b) the reaction to a ceiling outside its window; (c) the
   reaction to a mode outside `{0,1,2}`; (d) how the autonomous chain gets
   out of the teleop path's way (§12.9 **C3** hands this to `agv/`, and the
   gate ramps to zero then falls silent).
2. **`envelope.ceiling_max_mps = 1.00` is a second copy of
   `TRACTION_SPEED_MAX`** (`plc/forklift/SPEC.md` §3.3, quoted in §12.4).
   One datum in two files, which invariant 10 does not admit. It is carried
   as a plausibility bound only. **Requested**: either a rule that the
   vehicle reads it from somewhere single-owned, or an explicit note in
   §12.4 that consumers carry a local copy.
3. **`stale_window_s = 0.50 s` is a design value, not a measured one.**
   §12.4 **E5** derives it from the bridge's republish rate, and the double
   has no bridge behind it. ADR 0014's open item asks for the brief that
   measures PLC-write-to-topic age and jitter; this constant is re-derived
   when it lands.
4. **A goal aborted while the envelope is withheld is nobody's yet.** In
   the deployed-chain run Nav2 held on for 235 s and then **ABORTED, code
   105**, exactly as ADR 0011 D3's rationale predicts. Re-issuing the goal
   is order-level behaviour and is not the gate's — M6 / fleet.
5. **The gate's report is published but not yet carried.**
   `/forklift/mode/applied` and `/forklift/vehicle/heartbeat` are exercised
   on the vehicle side; the bridge's signal map does not carry this group
   (`opcua-nodes.md` §12.13 item 1), so D5.3's check is half-closed.

## Files outside agv/ that need a change — requested, not made

1. **`agv/forklift/EVIDENCE_NAV2.md` §7** — forbidden to me by the brief.
   Its reproduction recipe now brings up a **gated** chain, so the vehicle
   correctly will not move without an envelope. It needs the note and the
   argument pair `gate:=false cmd_topic:=/cmd_vel_smoothed`.
2. **`sim/setup/WSL_ENVIRONMENT.md`** — this machine has **no Nav2 and no
   `robot_localization`**, and no passwordless `sudo`. Both were fetched as
   `.deb` files and extracted into `~/ros-overlay/prefix` (12 + 42
   packages, ~40 MB, versions in evidence §0); the archive's
   `fastcdr`/`fastrtps`, `libompl.so.18` and GraphicsMagick had to come
   with them because the system ROS install is 345 packages behind the
   archive. **No system package was installed and no repository dependency
   was added.** That file should record the overlay, and the owner should
   decide whether to `apt` the stack properly instead.
3. **`docs/LESSONS.md`** — two entries this work paid for:
   *a state whose purpose is to stop publishing must publish its terminal
   value before it stops* (the creep, evidence §9); and *a downstream node
   that republishes a held command at a fixed rate makes "go silent" a
   command, not an absence*.

## next_suggested

Brief the bridge to carry the six §12.10 slots and the two
`Forklift/Vehicle/` writes, so the readback of ADR 0014 D5.3 is closed end
to end rather than on the vehicle side only.
