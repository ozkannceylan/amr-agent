# Step 1 — E-Stop chain, end to end

Run **2026-08-12 02:33–02:43 CEST**. PLCSIM Advanced `PLC_2` in RUN, vehicle side
from `step1.sh start` (partition `step1`, domain 91), `step1.py` on Windows
64-bit Python. Every number below was measured in this run.

Lamp colour and enable line are read from `/plc/status`, not from the window:
`hmi_node.lamp_state()` is a function of `estop_healthy` alone and
`enable_text()` of `motor` alone, so the topic is the stronger evidence.

**No stop is asserted from stillness.** Each one is asserted on three things
together: the terminal `/forklift/gz/actuator/traction_cmd`, the contactor's own
`/forklift/safety/torque_off_applied` with `sto_contactor.py` confirmed alive,
and the forklift pose sampled before and after.

| # | Step | Input | Expected | Measured |
|---|---|---|---|---|
| 1 | Fresh start | stack up, `step1.py` running | lamp red → neutral once status flows; `Motor` OFF; forklift still | Before: `estop=False motor=False` → **red**, enable OFF. On start: `estop=True motor=False` → **neutral**, enable still OFF. Terminal `0.0`, applied `True`, pose `x=-3.000000` unchanged over 19 s. **PASS** |
| 2 | Acknowledge | `a` | `Motor` ON; "Drive enable: ON" | PLC `Motor=True`; `/plc/status motor=True`; applied → `False` +8 ms; `cmd_gate: drive enable ON`. **PASS** |
| 3 | Drive | joystick forward, 0.40 m/s | forklift moves, pose changes | Terminal carried `3.3333` rad/s (= 0.40 ÷ 0.12 m wheel); pose `x −3.000000 → −0.824513` = **2.175 m in 6.999 s (0.311 m/s)**. **PASS** |
| 4 | E-Stop, joystick held | `es0` | stops while joystick still held; lamp red | Joystick still publishing 0.400 throughout. Terminal: last non-zero, then **163 rows all `0.0`**. Applied → **`True`**, contactor alive. Pose `6.072616 → 6.299881` (0.379 m/s) → `6.333985` and **identical at +1 s, +3 s, +6 s**; stopping distance 0.034 m. `estop→False` → lamp **red**; `motor→False` +50 ms. **PASS** |
| 5 | Release, no ack | `es1` | lamp neutral, `Motor` still OFF, forklift still stopped | `estop=True` → lamp **neutral**, but `motor` stays **False** (PLC: `E-Stop=True Motor=False`). Applied stays `True`; **291 terminal rows all `0.0`**; pose `6.333985` unchanged over 10 s with joystick still held. The latch, visible. **PASS** |
| 6 | Acknowledge | `a` | motion restored | `motor=True`, applied → `False` +12 ms, `drive enable ON`; terminal `3.3333` again; pose `6.333985 → 8.482258` = **2.148 m in 6.188 s (0.347 m/s)**. **PASS** |
| 7 | Kill the bridge | `taskkill /F` on `step1.py` while driving | forklift stops within budget; lamp red | **0.278 s** and **0.281 s** (two samples), against a **< 0.45 s** budget. `/plc/status` → fail-safe at +0.300 s → lamp **red**; applied → `True` at +0.311 / +0.312 s. Sample 1 pose: moving `13.294819 → 13.662596` (0.37 m/s), then `13.796548` **identical at +1 s, +3 s, +6 s**. **PASS** |
| 8 | Teardown | `step1.sh stop` | all processes down, no orphans | All 8 swept (`gz sim`, launch, `parameter_bridge`, `sto_contactor`, `forklift_io`, `plc_link`, `cmd_gate`, `hmi_node`); `pgrep -af` after: none; pid file removed. **PASS** |

Row 7 timing is measured entirely on the WSL clock, from the arrival of the last
`/plc/status` carrying a fresh sender timestamp — the last datagram `step1.py`
sent — to the first `traction_cmd = 0.0` after which no non-zero follows; the
conservative bound taken from the previous fresh datagram is 0.328 s and 0.331 s.
The Windows and WSL wall clocks were measured to disagree by ~0.2 s, so no
cross-machine interval is reported anywhere in this table.

The joystick was driven by `ros2 topic pub` at 20 Hz in the `/hmi/cmd_vel` field
contract (`linear.x` m/s, `angular.z` steer angle rad), not dragged; `hmi_node.py`
stayed up and publishes its centred zeros at 20 Hz on the same topic, so the
terminal alternates commanded value and zero at ~40 Hz and measured speed is
~78 % of commanded. `step1.py` was driven through a harness that pumps its stdout
continuously.

**Verdict: 8 of 8 steps pass. The E-Stop chain reaches the Gazebo forklift
through the real safety PLC, and the ESTOP1 latch holds across it.**

**Open item, outside the chain:** after ~90 s of my test driving into a wall and
repeated 1.2 m/s reversals, the plant stopped responding to forward commands
(0.016 m in 10.3 s with the terminal correctly carrying `3.3333` and `motor=True`)
while reverse still worked. It is downstream of the actuator terminal, so no row
above depends on it and every row above was measured before it appeared — but it
is undiagnosed and it is why row 7 has one pose-clean sample rather than three.
