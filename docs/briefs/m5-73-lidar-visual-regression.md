# m5-73 — the lidar visual worked once; find what took it away

    gate:                M5
    agent:               agv-ros2, run as a regression hunt
    goal:                Find the change that made the Gazebo lidar visual render at the world origin instead of on the vehicle, and put it back.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-72-scanner-pose-and-latched-zone-stop.md — the measurement that cleared the sensor and located the visual fault
      - agv/forklift/model.sdf and its git history — this file has been edited repeatedly and each edit was inventoried
      - agv/forklift/PLANT-CHANGE-INVENTORY.md — the inventory method used for every previous model change
      - agv/forklift/EVIDENCE_SENSOR_COVERAGE.md, EVIDENCE_MODEL.md
      - sim/launch/, agv/forklift/launch/, demo.sh — how the model is spawned now versus before
      - docs/LESSONS.md
    deliverable:         the fix, and a dated evidence section showing the fan on the vehicle at two poses
    done_when:           The ray fan is drawn on the vehicle and stays on it while the vehicle drives, demonstrated at two poses, with the field evaluation's readings shown unchanged by the fix.
    forbidden:
      - changing any sensor pose, angle, range or ray count to chase the visual. m5-72 proved the geometry is correct; a fix that moves the sensor is fixing the wrong thing
      - touching plc/ or TIA
      - changing scan_fresh_max_s or any safety timeout. That is a separate, owner-ruled decision
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. The owner's claim, and take it seriously

**"This sensor visualisation was already working. It should work again."**

That makes this a **regression**, not a missing feature — and regressions have a
commit. Find it before theorising.

## 2. What is already known, so you do not re-derive it

m5-72 established by measurement, at two vehicle poses:

- **the scanner geometry is correct.** Returns agree with the navigation lidar's
  view of the same racking to a median of 0.072 m (n=156) and 0.017 m (n=114).
  A constant mount displacement would show the same non-zero median at both
- **the visual fault is `world_pose`.** All three `gz.msgs.LaserScan` streams
  publish it as the **identity pose**, which anchors the drawn fan at the world
  origin — 3.00 m ahead and 5.50 m left of the vehicle at the spawn pose
- **the reading is byte-identical** after teleporting the vehicle 4.5 m and
  rotating it 45°, so the fan stands still while the vehicle moves
- **there is one `Forklift`.** `gz model --list` says so; the second-vehicle
  hypothesis is dead

So the question is narrow: **why is `world_pose` identity, and when did it stop
being the sensor's pose?**

## 3. Hunt the change, do not guess at the mechanism

`model.sdf` has been edited several times this gate — the steer gain, the second
encoder channel, the brake and controller disable — and each edit was
inventoried. The spawn path also changed: `demo.sh` composes
`vehicle.launch.py` with a world and spawn pose parsed out of
`warehouse_bringup.launch.py`, which is not how the model was launched when the
visual last worked.

Both are candidates. **A sensor whose link nesting or frame attachment changed,
and a model spawned by a different path, produce the same symptom.** Use the
history: find a commit where the visual demonstrably worked, and bisect the
difference.

If you find that it never worked in the current composition and the owner is
remembering a different launch path, **say that plainly** — it is still the
answer to their question, and it changes the fix from "revert" to "make the
composed path do what the standalone rig did".

## 4. Prove the fix does not move the measurement

This is the part that matters more than the visual.

The field evaluation's readings are load-bearing: every field figure in this
project comes through them, and m5-72 just certified them. **Show that your fix
changes the drawn fan and leaves the readings alone** — same comparison against
the navigation lidar, same two poses, same agreement.

A cosmetic fix that perturbs the measurement would be a bad trade, and nobody
would notice until a field figure disagreed with its own history.

## 5. Working discipline

- Read `docs/LESSONS.md` first.
- Demonstrate at two poses with the vehicle driving between them. A static
  screenshot cannot distinguish "on the vehicle" from "coincidentally nearby".
- **Do not commit.** The orchestrator commits by pathspec.
