# Report m4f-02 — in-house forklift model and vehicle-side nodes

```
brief:               docs/briefs/m4f-02-forklift-model.md
status:              done
files_changed:       agv/forklift/model.sdf
                     agv/forklift/config.yaml
                     agv/forklift/scripts/forklift_io.py
                     agv/forklift/scripts/obstacle_zone.py
                     agv/forklift/launch/vehicle.launch.py
                     agv/forklift/README.md
                     agv/forklift/EVIDENCE_MODEL.md
                     docs/reports/m4f-02-forklift-model.md
invariants_touched:  none
open_questions:      see below
next_suggested:      sim/ adds a world that spawns this model, because the
                     scanner needs gz-sim-sensors-system and agv/ must not
                     own a world
```

## Done_when, against what was measured

Every figure below is quoted in `agv/forklift/EVIDENCE_MODEL.md` as the
tool printed it. Run: WSL2, ROS 2 Jazzy, `gz sim 8.11.0`, headless server
only, `GZ_PARTITION=m4f02model`, `ROS_DOMAIN_ID=61`, llvmpipe.

| Criterion | Result |
|---|---|
| Model spawns | `data: true`, `Available models: Floor, TestWall, Forklift` |
| Steer responds on `/forklift/gz/steer_cmd` | 0.60 rad step to 0.553 in 3 s; step to the stop settles at `-1.3100000000110361` |
| Traction responds on `/forklift/gz/traction_cmd` | 4.0 rad/s commanded, `3.9999999999845994` at the joint, `0.4799968925779739` m/s at odometry |
| Fork responds on `/forklift/gz/fork_cmd` | rises at `0.150000000015` m/s, the joint's declared limit, to 0.8057 for an 0.80 m command |
| Fork holds under gravity at zero command | 2.3 mm over 20 s at gz level, 1.9 mm over 12 s at ROS level, both **toward** the target, rate halving |
| Four ROS topics at declared rates | `average rate: 9.999 / 10.000 / 10.001 / 10.000` |
| Zone TRUE on invalid, non-finite, stale | 17-case matrix, `RESULT: PASS (0 failing case(s))` |
| Every constant in `config.yaml` | mechanical check, `RESULT: PASS`; only `1.0/rate`, `0.0` initial command and a divide-by-zero guard remain inline |
| Environment table | present, in the pattern used by `bridge/EVIDENCE_*.md` |

The zone also crossed its threshold unprompted while driving: `in_stop_zone`
flipped between `min_distance` 1.226307 and 1.076296, bracketing the 1.20 m
value in `config.yaml`, with the scan and the odometry independently
agreeing the vehicle was doing 0.300000 m/s.

## Three defects found by measuring rather than by reasoning

Recorded because each one looks correct in the file and is wrong in the run.

1. **gz's PID inverts which integral clamp is which.** It forms its error
   as (position − target) and negates the sum, so while a carriage sits
   *below* its target it is `i_min` — the clamp that reads as downward —
   that bounds how hard the lift pushes **up**. Tuned the intuitive way,
   the fork stopped and held 15.7 mm short of its target and the same
   inversion buried it 0.15 m under a lowering target. Both directions had
   to be sized against gravity, asymmetrically.
2. **`d_gain` is an explicit damper and has a stability ceiling of about
   inertia/step.** For the steer assembly that is `0.13 / 0.002 = 65`. At
   500 and 1500 the joint hunted at its rate limit while the vehicle
   rolled; at 1200 it stopped responding to its topic entirely while still
   reporting a live command. Damping that has to be large belongs in
   `<dynamics><damping>`, which the engine integrates implicitly. Joint
   damping has its own ceiling too: 80 works, 400 froze the joint.
3. **A declared joint velocity limit does not bind against gravity.** The
   0.15 m/s limit is enforced exactly on the way up and was measured at
   `-0.16974939797667` m/s on the way down, through its own limit, while
   the controller was allowed to push downward. Lowering is now gravity
   through the damping and comes down at 0.140 m/s.

## Open questions

1. **`/forklift/joint_states` publishes at the physics rate**, measured
   `496.785` Hz in a 500 Hz world. The gz joint-state system has no rate
   parameter; an `<update_rate>` child was added and measured to change
   nothing. The nodes drop what they do not need, but any world that
   bridges this topic is choosing that traffic. Worth a decision when
   `sim/` wires the vehicle in, not before.
2. **Two files hold the same numbers.** `wheel_radius_m`,
   `steer_limit_rad` and the fork travel limits live in `model.sdf` and
   are mirrored in `config.yaml`, because SDF cannot be read as YAML. This
   is a documented duplication with `model.sdf` named as authority and a
   mechanical agreement check in the evidence file, not a second owner. If
   invariant 10 is read strictly enough to forbid even that, say so and it
   becomes a generated file instead.
3. **The vehicle carries no payload and no pallet.** Fork tuning and hold
   figures are for the unloaded carriage; a payload changes the weight the
   integral holds and would need re-measuring.
4. **Layout choice worth a sanity check by the owner.** The brief fixes a
   steered driven front wheel and two passive rear wheels, so the load is
   carried at the trailing end with the counterweight over the drive
   wheel, which is coherent but is a reach-truck arrangement rather than a
   classic counterbalance one. Changing it would move the mast, not the
   interfaces.

## Requests outside this directory

- **`sim/` needs to own a world for this vehicle.** The scanner is a
  `gpu_lidar`, so a world that spawns the model must load
  `gz-sim-sensors-system` with a render engine; gz's stock `empty.sdf`,
  which is this launch file's default, does not. Verification therefore
  used a throwaway world outside the repository, quoted verbatim in
  §0 of the evidence file so it is reproducible. Worlds belong to `sim/`
  and nothing was written there.
- **Nothing else.** No dependency was added: the nodes use `rclpy`,
  `PyYAML` and the message packages already present.

## Notes

- Both shebang scripts are already covered by the root `.gitattributes`
  rule `*.py text eol=lf`; `git check-attr` confirms `eol: lf` on all
  three Python files. `.gitattributes` was not edited.
- `model.sdf` is strict-XML parseable, unlike `sim/worlds/cell.sdf`, so
  future SDF tooling using `xml.etree` will not need to special-case it.
- `docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md` was not on
  disk during this work. The brief's facts were treated as the
  owner-approved decisions and nothing here depends on text not read.
- Every run isolated both transports and cleaned up by signalling only its
  own pids. One early harness attempt inferred a process group with `ps`
  and raced the `exec`, leaving a run behind; it was found by `pgrep` and
  killed by exact pid, and the harness now uses the pid it already knows.
