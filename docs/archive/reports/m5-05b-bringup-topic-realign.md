# Report m5-05b — realign the bringup launch to the new topic contract

```
brief:               docs/briefs/m5-05b-bringup-topic-realign.md
status:              done
files_changed:       [sim/launch/forklift_bringup.launch.py,
                      sim/setup/CONTAINER_TOOLCHAIN.md]
invariants_touched:  none
open_questions:      see below
next_suggested:      bridge /forklift/gz/safety_scanner_rear/measurement only when a consumer for it exists; agv/ names the ROS topic, this file adds the row.
```

## What was already done, and by whom

`_BRIDGE_ARGS` and `_BRIDGE_REMAPS` were rewritten by the agent lost to the
container suspension and committed as `dc2c69f`, whose own message says
"Verification run and evidence pending". **The file edit is correct.** This
report is the verification it never got, plus the second half of the brief's
deliverable — the stale topic names in `sim/setup/CONTAINER_TOOLCHAIN.md` — which
that agent did not touch at all.

| Part | Authored by | Verified live |
|---|---|---|
| the eight `_BRIDGE_ARGS` entries and four remaps | lost agent, `dc2c69f` | yes, all eight, against a running server |
| that data flows on each bridged ROS topic | claimed nowhere; pending | yes, `hz` and `echo` on every one |
| `CONTAINER_TOOLCHAIN.md` §6 and the stale names | **not done** | written here |

**No change to the topic list was needed.** Every name in the file matches the
contract table in `agv/forklift/README.md`, and every gz-side name is advertised
by the running server. The only edit made here is a one-line cross-reference in
the header comment that the rename had left pointing at the wrong evidence
section.

## Verified live

Two runs: `GZ_PARTITION=m505b_verify` / `ROS_DOMAIN_ID=81`, and a
re-confirmation against the final file state as
`GZ_PARTITION=m505b_confirm` / `ROS_DOMAIN_ID=83`. Both transports isolated,
because gz transport does not use DDS. Full evidence in
`sim/setup/CONTAINER_TOOLCHAIN.md` §6.2.

`ros2 topic hz`, first reported window of each, as the tool printed it:

| Topic | `average rate` | min / max | window |
|---|---|---|---|
| `/forklift/scan` | `9.995` | `0.098s` / `0.104s` | 12 |
| `/forklift/safety_scanner_front/measurement` | `10.001` | `0.098s` / `0.103s` | 11 |
| `/forklift/odom` | `19.998` | `0.049s` / `0.051s` | 22 |
| `/forklift/joint_states` | `500.055` | `0.000s` / `0.005s` | 501 |
| `/clock` | `500.191` | `0.000s` / `0.004s` | 501 |

`ros2 topic echo --once --full-length` captures, shape counted from the
untruncated messages: `/forklift/scan` 360 ranges / 360 intensities /
`frame_id: nav_lidar_link` / `range_max: 8.0`;
`/forklift/safety_scanner_front/measurement` 275 / 275 /
`frame_id: safety_scanner_front_link` / `range_max: 5.5`. Both match the
`<samples>` counts in `model.sdf`, neither capture was truncated.

The **ROS → gz** direction was checked too, because a command entry fails
silently the same way a feedback entry does: `ros2 topic pub -r 5
/forklift/gz/traction_cmd std_msgs/msg/Float64 '{data: 3.0}'` produced `data: 3`
on `gz topic -e -t /forklift/gz/traction_cmd`, and `/forklift/odom` moved from
`x: -5.999999999999972` to `x: -1.6605650436960087`. So the file is proven in
both directions, not only on the topics the rename touched.

## How the silent-failure mode was checked for

The failure mode is a bridge entry for a gz topic nobody publishes: it logs
`Creating GZ->ROS Bridge` exactly as a working entry does, errors nothing, and
carries nothing. Three checks, because "the names are right" is a claim about a
running server and not about a file:

1. **Every gz-side name parsed out of `_BRIDGE_ARGS` and compared to
   `gz topic -l` on the live server** — `declared: 8   not advertised: 0`. A
   typo cannot pass this. The first pass of the cross-check script silently
   dropped one name because the `safety_scanner_front/measurement` entry is a
   wrapped tuple in the source, so it reported 7 of 8; the parser was fixed to
   join adjacent string literals and re-run before the number was believed.
2. **`ros2 topic hz` on every bridged ROS topic**, never a reading of the launch
   log.
3. **A negative control, deliberately reproduced beside the fix.** A second
   `parameter_bridge` was started alone, on the removed `/forklift/gz/scan`,
   against the same live server:

   ```
   [INFO] [ros_gz_bridge]: Creating GZ->ROS Bridge: [/forklift/gz/scan
     (gz.msgs.LaserScan) -> /forklift/gz/scan (sensor_msgs/msg/LaserScan)] (Lazy 0)

   $ ros2 topic hz /forklift/gz/scan
   WARNING: topic [/forklift/gz/scan] does not appear to be published yet

   $ ros2 topic echo /forklift/gz/scan --once
   (no output; exit status 124 — killed by timeout)
   ```

   Identical INFO line, no error, no data. The fix is now *distinguishable*
   from the failure rather than merely believed to differ from it.

One trap found while doing this, recorded in §6.3: the first
`ros2 topic hz /forklift/scan` of a run printed `WARNING: topic [/forklift/scan]
does not appear to be published yet` and then reported `average rate: 9.736` in
the same invocation. **A warning at the start of a window is not the silent
failure**; the silent failure prints that warning and nothing after it. Reading
the warning alone would have condemned a working bridge.

## `CONTAINER_TOOLCHAIN.md`

- **§6 rewritten** from "Known gap" to §6.1 (the gap as this document first
  recorded it, kept) and §6.2/§6.3 (closed, with the run above and the three
  checks). It now names only topics that exist, except inside the negative
  control, where naming the removed topic is the point.
- **§4.1 gained a dated note.** §4, §4.4, §4.5 and §7 still contain
  `/forklift/gz/scan_safety_front` and `_rear`, which m5-06 renamed to
  `.../safety_scanner_*/measurement`. Those sections are a record of a run that
  really happened with those names, so they are **marked in place with a
  translation table and a "do not copy these as a recipe"**, not rewritten. The
  sweep was done by subject across all of `sim/`, not from the brief's
  enumeration (LESSONS 2026-07-29).
- **§8 gained the one-command form** of the bringup, plus the warning that under
  `gui:=true` the beams still need three clicks and the first click selects the
  front safety scanner rather than the navigation lidar.

## Open questions

1. **`/forklift/gz/safety_scanner_rear/measurement` is still not bridged**, per
   `agv/forklift/README.md`'s rule that a measurement channel goes onto the
   process network when something consumes it. That is followed here, not
   decided here. When a consumer appears, `agv/` names the ROS topic.
2. **The `gui:=true` path costs the bridged scan rate**: `average rate: 9.995`
   headless against `8.488` with the GUI attached, on a sensor declared at
   10 Hz (measured under m5-05, `FORKLIFT_ARENA_EVIDENCE.md` §9.6). Any consumer
   whose timeout assumes 10 Hz needs checking before a GUI run is used for
   anything but looking at. `obstacle_zone`'s 0.50 s staleness window survives;
   nothing else was checked.
3. **`ros2 topic echo /clock --once` is not a usable capture** on this topic: at
   500 Hz it printed `A message was lost!!!` instead of a message, three times,
   while exiting 0. A bounded `timeout 6 ros2 topic echo /clock` gives a clean
   sample and is what §6.2 quotes. Worth knowing before someone reads a lost
   message as a dead bridge.
4. **Killing the `ros2 launch` pid does not take the group down.** Both runs
   left the gz server and the `parameter_bridge` alive after the launch pid was
   signalled, matching what `FORKLIFT_ARENA_EVIDENCE.md` §8 already records.
   Every survivor was matched against observed `ps -eo pid,args` output and
   killed by exact pid; a parallel session's Gazebo (`GZ_PARTITION=vizshot5150`)
   was running at the time and was identified by reading `/proc/<pid>/environ`
   before anything was signalled, so that no process belonging to it was touched.
