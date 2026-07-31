# Brief m5-05b — realign the bringup launch to the new topic contract

```
gate:                M5
agent:               sim
goal:                sim/launch/forklift_bringup.launch.py carries data again,
                     and the toolchain evidence names topics that exist.
invariants_touched:  none
inputs:              [sim/launch/forklift_bringup.launch.py,
                      sim/setup/CONTAINER_TOOLCHAIN.md section 6,
                      agv/forklift/README.md and config.yaml as landed by
                      m5-06 (read only — the topic contract is agv/'s),
                      docs/reports/m5-06-measurement-channel.md,
                      docs/reports/m5-07-autonomy-toolchain.md open question 1]
deliverable:         sim/launch/forklift_bringup.launch.py and the stale topic
                     names in sim/setup/CONTAINER_TOOLCHAIN.md
done_when:           the bringup bridges the topics agv/ actually publishes —
                     the navigation lidar, the front scanner's measurement
                     channel, and whatever else the contract table lists — and
                     a captured `ros2 topic echo` sample proves data flows on
                     each; CONTAINER_TOOLCHAIN.md section 6 names only topics
                     that exist; and the report states how the silent-failure
                     mode was checked for, not merely that it was fixed.
forbidden:           [editing agv/ or coining any topic name (the contract is
                      agv/'s — read it and follow it); editing
                      sim/worlds/ (a parallel brief owns the arena) or
                      sim/setup/install.sh; changing the launch's structure
                      beyond the topic list and whatever the rename forces;
                      committing (the orchestrator commits)]
```

## Why this is urgent

The launch currently bridges `/forklift/gz/scan`, a topic m5-04 removed. It
spawns cleanly, logs `Creating GZ->ROS Bridge` for every entry, reports no
error, and carries **no data**. A silent failure is worse than a loud one: the
rehearsal would hang and the cause would not be in any log. m5-07 verified
both directions of this — the same file carried data at 9.997 Hz against the
pre-m5-04 model — so the diagnosis is established and your job is the fix plus
its proof.

Isolate your Gazebo run with **both** `GZ_PARTITION` and `ROS_DOMAIN_ID`; gz
transport does not use DDS, so the ROS variable alone does not isolate the
simulation, and another agent may be running the arena concurrently. Match any
pkill against observed `pgrep -af` output.

Note `agv/forklift/launch/vehicle.launch.py` is the model's **standalone test
rig** — in the composed stack it spawns a second forklift. It is agv/'s file;
do not edit it, and do not use it inside your composed run.

Do not commit. Leave files modified and write your report to
docs/reports/m5-05b-bringup-topic-realign.md.
