# Report m5-07d — the estimator must not turn while the vehicle is still

```
brief:               docs/briefs/m5-07d-stationary-handling.md
status:              done
files_changed:       agv/forklift/scripts/imu_gate.py         (new)
                     agv/forklift/scripts/wheel_odometry.py
                     agv/forklift/scripts/check_odometry.py
                     agv/forklift/ekf.yaml
                     agv/forklift/config.yaml
                     agv/forklift/launch/vehicle.launch.py
                     agv/forklift/EVIDENCE_ODOMETRY.md
                     agv/forklift/README.md
                     docs/reports/m5-07d-stationary-handling.md
invariants_touched:  none. Invariant 10 shaped the split: the standstill
                     verdict is formed by the node that already owns the
                     encoder model and by no other, and the gate reads it
                     off a topic rather than re-quantising the joint
                     angles with its own idea of the count grid
open_questions:      six, below
next_suggested:      the SLAM brief can rebuild the map; its frame no
                     longer depends on the idle before the drive, and
                     m5-08c finding 1's registration is still owed either
                     way
```

## The numbers

| | before (`imu_gate:=false`) | after |
|---|---|---|
| fused heading over a **60 s idle**, vehicle commanded to rest | **−7.70°** (−7.71 °/min) | **0.00°** (0.00 °/min) |
| the same over a **240 s idle** | (−35.79° is what the gyro integrated) | **0.00°** |
| **drift accumulated WHILE MOVING**, same route, same manoeuvre set | **−12.9765°** over 110.74 s | **−12.8761°** over 110.74 s |
| whole-run heading error over the 106.49 m route | −17.0501° | −12.9381° |
| whole-run position error | 5.0619 m | 3.2929 m |

Both columns are runs of this build at `gz sim --seed 1`, which fixes the
bias draw, so they differ in one launch argument and nothing else. The
left column reproduces m5-07c's headline (5.21 m / −17.18°) to within the
run-to-run spread. Full evidence, with the environment table, the file
md5s and the reproduce recipe: `agv/forklift/EVIDENCE_ODOMETRY.md` §12.

## The mechanism, and why it is legitimate

**A zero angular rate update, gated on the encoders.** `wheel_odometry.py`
publishes one new boolean — both encoder counts unchanged for 0.50 s —
and a new node `imu_gate.py` forwards the IMU to the filter unchanged
**except** in that condition, when it forwards nothing. `ekf.yaml`'s
`imu0` moved from `/forklift/imu` to `/forklift/imu_gated`. That is the
whole change.

It is physics, not convenience, and the argument is one line of
kinematics: a tricycle's instantaneous centre of rotation lies on its
rear axle line and its drive wheel does not, so `|v_D| ≥ |ψ̇|·L` and a
drive encoder count that does not change **bounds the body rotation over
that interval at 0.0101°**. The rate is therefore known to be zero
independently of the gyro, and what the gyro reports in that condition is
bias. Declining to offer it as a rotation measurement is what every
inertial navigator does under that name. The steer count is in the test
too, because a parked forklift steering on the spot is the one manoeuvre
in which a drive encoder could hold while a contact patch slides.

**Configuration was preferred and was not available.** `robot_localization`
3.8.3 — the exact installed build — has no stationary handling in its
parameter set; the search and the two near misses considered by name
(`dynamic_process_noise_covariance`, the `ToggleFilterProcessing`
service) are recorded in EVIDENCE §12.2 with the reason each was
rejected. So the mechanism is one node outside the filter and the
filter's own configuration changed by one string.

**Two choices that could have gone the other way, stated because they are
what makes the result honest.** The gate *suppresses* rather than
rewriting, so a zeroed rate can never be mistaken downstream for a
reading the device took. And it *estimates no bias and carries nothing
into motion* — that would have flattered the moving case, which is the
phenomenon gate M5 exists to correct. It also fails **open** in every
direction, and the launch refuses `imu_gate:=true wheel_odom:=false`, the
one configuration in which the gate would run and be permanently
ineffective while looking like it worked.

## Did the moving case improve? No — 0.10°, which is the noise floor

−12.9765° → −12.8761°. The expected white-noise random walk over the same
interval is `σ_gyro·√(Δt·T) = 1.745e-3·√(0.01·110.74) = 0.1052°`, so the
difference is **0.95 σ**. It could not have been otherwise: while the
gate is open the filter receives the raw message unchanged, and the
counters say the gate was open for every sample of the drive — 1 024
suppressed samples at 100 Hz is 10.24 s against 10.22 s of verdict-true
time, and the gate logged exactly two transitions in the whole 121 s
route.

**The whole-run figures did improve, and every degree of it is in the
standing intervals.** Split by the vehicle's own verdict:

| | before the drive | while moving | after the drive | total |
|---|---|---|---|---|
| before | −3.2865° | **−12.9765°** | −0.7871° | −17.0501° |
| after | −0.0596° | **−12.8761°** | −0.0024° | −12.9381° |

4.0116° of the 4.1120° improvement is the two standing columns; 0.1004°
is the moving column and is the noise above.

**Position improved by 1.77 m and that is not a drift claim either.** The
ungated run began driving with its heading already −3.29° wrong, and a
heading offset present at the start rotates the whole subsequent path
about the start point: the final pose is 30.88 m from the origin, and
`30.88 × 0.05632 rad = 1.739 m` against a measured 1.769 m — 2 %
agreement from geometry with no free parameter. The vehicle drifts
exactly as far as it did; it now starts from where it is pointing.

## What was not touched, checked rather than asserted

`model.sdf`'s md5 is **byte-identical** to the one m5-07c recorded, so
every datasheet-derived noise figure stands. No message covariance, no
`odometry:` variance, no `process_noise_covariance` and no
`initial_estimate_covariance` was added or edited. `_PROFILE` — the route
and manoeuvre set — is unchanged, which is what makes the before and
after comparable. No ground truth reaches an estimator, and `--phase
idle` subscribes to no ground-truth topic at all: the vehicle's own
encoders establish that it did not move, its own gyro says what would
have been integrated, and the fused heading is compared with itself.

## Open questions

1. **The seed is a measurement facility and a claim about gz that should
   be re-checked on WSL.** `gz sim --seed` fixes the sign and magnitude
   of the drawn bias; verified here across four seeds (§12.5). Nothing on
   the vehicle reads it and the default is empty. If a later brief relies
   on it, re-verify on the target platform.
2. **The one credible way this mechanism is wrong: gross drive-wheel
   skid.** A vehicle slid bodily across a floor — towed, pushed, on ice —
   could rotate with both counts held, and the gate would suppress a real
   rotation. No commanded motion in this simulation reaches that state
   and nothing here tests it. It is stated in EVIDENCE §12.8 rather than
   guarded against.
3. **The gate costs up to 0.50 s of ungated gyro at every stop**, by
   design — it closes only after the window and opens on the first count.
   The measured residual is 0.40 s worth, ≈ 0.06°. A shorter window would
   cost less and trust a standstill sooner; nothing here establishes how
   short is still safe against encoder dither, because none was observed.
4. **To the SLAM brief.** `m5-08c` finding 1's world→map registration is
   still owed. A SLAM map's frame is legitimately its own even when its
   heading no longer drifts, and a rebuilt map should now be square to
   the building — but **that is a measurement of the map, not of this
   change**, and this brief did not run SLAM.
5. **To `sim/`, unchanged and now with a second reason.**
   `sim/launch/forklift_bringup.launch.py` still has no IMU bridge, no
   wheel odometry and no EKF (m5-07c open question 3); it now also needs
   `scripts/imu_gate.py`, or a stack brought up through it will drift
   while parked in exactly the way the committed map recorded.
   `agv/forklift/launch/vehicle.launch.py` is the working reference.
   The `/forklift/odom` rename request (m5-07b, m5-07c) also stands.
6. **Container only.** Every figure here is from the project container.
   The owner's WSL host has never run this configuration.

## Notes

- **Nothing outside `agv/` and this report was written.** `git status`
  also shows `plc/forklift/SPEC.md` modified; that is not this brief's
  and was not touched here — the orchestrator should commit by pathspec.
- **No dependency was added.** `robot_localization` was already present
  and its version is unchanged; `imu_gate.py` imports `rclpy`,
  `sensor_msgs` and `std_msgs` only.
- **No new transform publisher.** `imu_gate.py` contains no transform
  broadcaster. `check_odom_tf.py` still passes 15/15 and
  `check_sensor_frames.py` 22/22 static, and `check_odometry.py --phase
  static` still passes 23/23.
- One harness defect was found and fixed on the way: a run brought up
  with `nodes:=false` commands motion that never happens, and section 7
  divided by the zero path length. It now says so instead.
- Runs were isolated on **both** transports (`GZ_PARTITION` and
  `ROS_DOMAIN_ID`, unique per run), headless throughout, driven to
  completion in the foreground, and every process was confirmed gone with
  `ps -eo pid,args` after each. **No RTF figure was taken and none is
  quoted** (LESSONS 2026-07-30).
- Nothing committed, nothing staged, no branch created.
