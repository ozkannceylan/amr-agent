# m5-21 — install the ROS 2 autonomy stack properly on the WSL machine

    brief:               docs/briefs/m5-21-wsl-ros-stack-install.md
    status:              done

    files_changed:
      - sim/setup/WSL_ENVIRONMENT.md   (mod) restructured into Part I (the M3
                                       record, kept) and Part II sections 6-13,
                                       the install and its verification; the two
                                       MISSING rows in section 2 superseded
      - sim/setup/install.sh           (mod) a DDS_PKGS block after the ROS_PKGS
                                       install; +30 lines, no other change
      - docs/reports/m5-21-wsl-ros-stack-install.md   (this file)

    invariants_touched:  none

## What is on the machine now

`ros-jazzy-nav2-bringup` **1.3.12-1noble.20260616.082701** and
`ros-jazzy-robot-localization` **3.8.3-1noble.20260615.152020**, installed
as system packages with 135 dependencies, plus a four-package Fast-DDS
realignment. `~/ros-overlay/prefix` is gone (moved to
`~/ros-overlay.retired-m5-21`, 245 MB, on no search path). With only
`/opt/ros/jazzy` sourced:

```
$ ros2 pkg prefix nav2_bringup        ->  /opt/ros/jazzy
$ ros2 pkg prefix robot_localization  ->  /opt/ros/jazzy
$ echo $AMENT_PREFIX_PATH             ->  /opt/ros/jazzy
```

The full M5 vehicle stack was brought up on a verified-clean machine —
warehouse bringup, `localization.launch.py`, `navigation.launch.py` — and
all seven managed nodes reached **active [3]** (`map_server`, `amcl`,
`controller_server`, `planner_server`, `behavior_server`, `bt_navigator`,
`velocity_smoother`) with **fatal = 0 and process-died = 0 in all three
launch logs**. Evidence is in `WSL_ENVIRONMENT.md` §12.

Nothing was removed and nothing outside the plan was upgraded: the machine
is still 288 `ros-jazzy-*` packages behind the archive, deliberately.
Rollback record at `/root/m5-21-snapshot`, copied readable to
`~/m5-21-snapshot` (§13.2).

## The finding the install produced

**Installing today's Nav2 onto a ROS tree months behind the archive is not
a one-command job, and the failure is silent until a node starts.**
`nav2_amcl` and `controller_server` died at exit 127 with
`undefined symbol: _ZN8eprosima7fastcdr3Cdr9serializeEj` — `ldd` reported
nothing missing, because the fault is a symbol, not a file.

**Upgrading `fastcdr` alone then broke the entire ROS installation**, not
just Nav2: the Gazebo bridge, `sensor_tf`, `wheel_odometry`, `imu_gate` and
`ekf_node` all aborted. Fast-CDR 2.2.5 -> 2.2.7 is not a drop-in despite an
unchanged soname. Restoring the 2.2.5 file restored the machine, which is
what makes the attribution a confirmation rather than a guess. `fastcdr`,
`fastrtps` and both `rmw_fastrtps` packages have to move **together**; that
set was executed and removes nothing, and it is now in `install.sh` behind
`--only-upgrade`.

**`apt-get -s dist-upgrade` was not taken.** It proposes 345 upgrades and
**removes `libglapi-mesa`**, and Mesa is the software rasteriser every
Gazebo run on this machine depends on. A removal is a stop-and-report under
this brief. That upgrade is now an owner decision with a Gazebo re-run
attached to it (§13.3 item 1).

## The re-run measurement — one figure agrees exactly, one does not

`EVIDENCE_ENVELOPE.md` §7, pass-through fidelity, re-run **four** times on
the installed stack:

| | committed (overlay) | A | B | C | D (clean machine) |
|---|---|---|---|---|---|
| matched pairs | 221 | 221 | 224 | 676 | 440 |
| max residual | 0.000e+00 | **0.000e+00** | **0.000e+00** | **0.000e+00** | **0.000e+00** |
| exact matches | 221/221 | **221/221** | **224/224** | **676/676** | **440/440** |
| latency mean | 0.0004 s | 0.0004 s | 0.0012 s | 0.0023 s | **0.0242 s** |
| latency max | 0.0010 s | 0.0014 s | 0.0465 s | 0.0122 s | **0.0713 s** |

**Agrees exactly:** the zero residual and every-pair-exact result, in all
four runs. That is the claim §7 makes and it reproduces without
qualification.

**Disagrees, and it is reported rather than reconciled:** the latency
figures. The committed mean 0.0004 s / max 0.0010 s was not reproduced —
mean up to **60x** and max up to **71x** the committed value. Nothing was
tuned and no run was discarded. Run A was on the *old* DDS stack and
matched the committed figure; run D was on a machine verified clear of
orphans and was the worst of the four; the four disagree with each other by
60x. So `0.0004 s` was a sample, not a bound (LESSONS 2026-08-04) — a
finding about the figure, not about either environment.

## Files outside sim/ that need a change — requested, not made

1. **`agv/forklift/EVIDENCE_ENVELOPE.md` §0** — its environment block still
   describes `~/ros-overlay/prefix` as the packaging in force. It needs the
   qualifier that **every figure in that file was measured under an overlay
   that no longer exists**, and that the same upstream versions
   (`nav2_velocity_smoother` 1.3.12, `robot_localization` 3.8.3) are now
   system packages. Its §11 item 7 ("Nav2 and `robot_localization` are not
   installed on this machine") is now false and should point at
   `WSL_ENVIRONMENT.md` Part II.
2. **`agv/forklift/EVIDENCE_ENVELOPE.md` §7** — the latency row reads as a
   property of the gate. It should be re-read as a single-run observation
   with its n, with the four figures above beside it. **The zero-residual
   result needs no change; it reproduced exactly.**
3. **`docs/LESSONS.md`** — three entries this work paid for:
   *a shared library with an unchanged soname is not therefore a drop-in;
   Fast-CDR 2.2.5 -> 2.2.7 kept `libfastcdr.so.2` and broke every ROS 2
   process on the machine, and the version whose file was saved first is the
   only one that could be restored because the old .deb had left the
   archive*;
   *a Fast-DDS version change strands `/dev/shm`, and the resulting
   `open_and_lock_file failed` reads as a broken install*;
   *killing a `ros2 launch` does not kill the nodes it started — five ghosts
   survived minutes and put duplicate names into `ros2 node list`, where a
   live ghost and a new node share a name and either may answer*.
4. **`docs/TODO.md`** — the m5-11 item requesting this install can close;
   the five un-re-run `EVIDENCE_ENVELOPE.md` observations (§13.3 item 3) and
   the dist-upgrade decision (§13.3 item 1) are the items it leaves behind.

## open_questions

1. **No repository dependency was added, and none is proposed.** The 137
   packages are exactly what `install.sh`'s existing `ROS_PKGS` list already
   declared (`navigation2`, `nav2-bringup`, `slam-toolbox`,
   `robot-localization`) plus their dependencies. The four `DDS_PKGS` are
   `--only-upgrade` version alignment of packages ROS 2 already required —
   it can never pull in something that was not installed. **If the
   orchestrator reads that block as a new dependency, it is a one-line
   revert and should be raised before the commit.**
2. **The dist-upgrade is an owner decision.** 345 upgrades and one removal
   (`libglapi-mesa`, a Mesa upgrade artifact). It should be its own brief
   with a Gazebo render re-run in its `done_when`, not a step inside another
   task.
3. **`ros2_control`'s five packages are still absent** and were not
   installed; the forklift does not use them (ADR 0010 D1). Nav2's
   controllers pulled in the interface libraries only.
4. **`~/ros-overlay.retired-m5-21` (245 MB) can be deleted** once this work
   is committed. It is kept only so an m5-11 figure could be re-read against
   the environment that produced it.

## next_suggested

Brief `agv-ros2` to apply the two `EVIDENCE_ENVELOPE.md` corrections above
and to re-run the five remaining observations for their own n, now that the
stack they measure is reproducible from `sim/setup/install.sh`.
