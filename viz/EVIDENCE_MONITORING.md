# EVIDENCE_MONITORING.md

The dated runs behind `viz/` — the read-only monitoring service of ADR 0011 D4,
built to `DESIGN.md` and checked against `DESIGN.md` §8.

**What this file is for.** The central claim of this layer is

> **read-only by construction of the process and proven by test; not enforced
> by the middleware.**

The second half of that sentence is why the first half needs evidence. Nothing
in DDS stops this process from creating a publisher, so "no publisher" is a
property of source that one edit flips — and on Jazzy the framework's own
opt-out flags do **not** reach it (§4). Every section below is a command and
its actual output. §4 and §6 are the ones that matter: the check passing on a
live node, and what it looks like when it would fail.

**Written before the first run.** The headings below were created before any
command was issued and each result was appended as it landed, so no section is
a summary reconstructed after the fact.

---

## 0. Environment, and what qualifies every figure

| | |
|---|---|
| Host | the owner's WSL2 machine, Ubuntu 24.04.4 LTS, kernel 5.15.167.4-microsoft-standard-WSL2, ROS 2 **Jazzy**, 20 logical cores, 15.4 GiB |
| Packages, read rather than assumed (`dpkg -l`) | `ros-jazzy-rclpy` **7.1.11-1noble.20260615.133206**, `ros-jazzy-nav2-bringup` **1.3.12-1noble.20260616.082701**, `ros-jazzy-robot-localization` **3.8.3-1noble.20260615.152020**, `ros-jazzy-fastrtps` **2.14.6-1noble.20260303.233638**, `ros-jazzy-rmw-fastrtps-cpp` **8.4.4-1noble.20260615.124621**, `ros-jazzy-fastcdr` **2.2.7-1noble.20260225.051855** — the set m5-21 left in place |
| Middleware | default `rmw_fastrtps_cpp`; `RMW_IMPLEMENTATION` unset in every shell below |
| Checkout | `/mnt/c/Users/ozkan/projects/amr-agent`, driven from WSL |
| Run started | **2026-08-06T05:07Z** (freedom check), static checks 05:1xZ, scratch probe 05:2xZ, the live vehicle run in §5 onward |
| Rendering | software rasterisation; the sim side is headless (`gz sim -r -s`), no GUI in any run below |
| Isolation | vehicle domain **51** from `allocation.yaml`; scratch domain **73** for §4; `GZ_PARTITION=viz13b` for the simulator. The two transports are isolated separately — `ROS_DOMAIN_ID` does not isolate Gazebo (`docs/LESSONS.md` 2026-07-27) |

**What every figure here is a figure of.** One vehicle, one host, one session.
Nothing in this file is a bound. The endpoint censuses are properties of the
construction and reproduce exactly; anything time-shaped is one draw.

**The plant this ran against.** The current tree, after the 2026-08-05 steer
`p_gain` change (6000 → 60000). This layer commands nothing and its results do
not depend on the plant's behaviour, but the vehicle it watched was the
current one and is named as such.

---

## 1. The machine was free, and what was checked

Measurement runs alone (`docs/LESSONS.md` 2026-07-30). What was checked, and
its output, before anything was started:

```
$ /tmp/free_check.sh
---- utc ----
2026-08-06T05:07:58Z
---- gz sim ----
(none)
---- ros/vehicle processes ----
(none)
---- ros2 daemon ----
(none)
---- viz processes ----
(none)
---- stranded fastdds shm segments ----
764
---- listeners on 8088/8089 ----
(none)
---- load / mem ----
 07:07:58 up 2 days, 22:23,  2 users,  load average: 0.00, 0.01, 0.00
               total        used        free      shared  buff/cache   available
Mem:           15808        1566       13300          93        1357       14241
```

No simulator, no ROS process, no `ros2` daemon, nothing listening on this
service's port or the HMI backend's. **764 stranded Fast DDS shared-memory
segments** from earlier sessions were present and were removed before the
first run (the §12.7 fault of `EVIDENCE_VEHICLE_IMAGE.md`); `/dev/shm` then
held two unrelated `lttng-ust` entries and nothing else.

---

## 2. The static construction checks — DESIGN §8.2 and §8.6

```
$ python3 viz/tools/check_construction.py
CHECK A - entity-creating calls, 6 names, scope viz/**/*.py
  create_publisher   ok   1 hit(s): viz/monitor/subscribe_only.py:41
  create_service     ok   1 hit(s): viz/monitor/subscribe_only.py:42
  create_client      ok   1 hit(s): viz/monitor/subscribe_only.py:43
  ActionServer       ok   1 hit(s): viz/monitor/subscribe_only.py:44
  ActionClient       ok   1 hit(s): viz/monitor/subscribe_only.py:45
  set_parameters     ok   1 hit(s): viz/monitor/subscribe_only.py:46

CHECK B - the read-only claim, whitespace-normalised, scope viz/**
  qualified    viz/DESIGN.md
  prohibition notice viz/DESIGN.md
  qualified    viz/EVIDENCE_MONITORING.md
  qualified    viz/README.md
  qualified    viz/monitor/http_face.py
  qualified    viz/monitor/service.py
  qualified    viz/monitor/service.py
  qualified    viz/monitor/service.py
  qualified    viz/monitor/subscribe_only.py
  qualified    viz/tools/check_construction.py
  qualified    viz/tools/zero_endpoint_probe.py
  11 occurrence(s) examined

CHECK A PASS   CHECK B PASS
CONSTRUCTION CHECKS PASS
```

*(the checker prints an 140-character context window under each verdict line;
they are elided above and reproduce on re-run.)*

**The one "prohibition notice"** is `DESIGN.md` §2's own sentence *"Never the
unqualified …"*, which names the short form in order to forbid it. It is
classified rather than exempted, and the classification is printed.

**Two things this check caught while it was being written**, both recorded
because they are the reason the check is not a formality:

1. **Adjacent Python string literals hide the phrase.** A long claim inside a
   `print()` wraps as `'… of the process ' 'and proven by test …'`, which puts
   a quote-space-quote in the middle of the sentence. Three files read as
   **BARE** on the first run for that reason alone. The sweep now un-wraps
   blockquote markers, comment markers **and** adjacent literals before
   searching — the 2026-07-27 whitespace lesson, with a third wrapping this
   layer supplied.
2. **The checker reported itself.** Its own `CLAIM = '…'` constant was a
   literal instance of the short form. Rather than exempt the file, the
   constant is now assembled from two pieces, so the checker is not an
   instance of what it forbids and needs no exemption. The forbidden-call list
   is handled the same way: it lives once, in `subscribe_only.py`, and the
   checker **reads** it instead of holding a second copy that could drift
   (invariant 10).

---

## 3. The service's own self-check — no ROS, no socket

```
$ python3 viz/monitor/service.py --self-check
allocation table, through the vehicle layer's one code path:
   /mnt/c/Users/ozkan/projects/amr-agent/agv/forklift/vehicles/allocation.yaml
   vehicles {'F001': 51}  vehicle_range (51, 54)  operator_domain 10

the forbidden-call list, read from the factory that owns it:
   6 names: create_publisher, create_service, create_client, ActionServer, ActionClient, set_parameters

the construction checks (DESIGN 8.2 and 8.6):
   PASS

the HTTP face, without binding a socket:
   request methods defined on the handler: ['do_GET']
   do_POST resolves to _method_not_allowed (the core refusal)

SELF-CHECK PASS
```

The vehicle list came from `vehicle_identity.load_allocation()` — the vehicle
layer's own single code path — and not from a second parse of the YAML.

---

## 4. Zero endpoints: the check passing, and what failing looks like

This is the section DESIGN §4 predicted and the section the whole claim rests
on. Two nodes, one scratch domain, one difference in source: whether the
residual publisher is torn down.

```
$ python3 viz/tools/zero_endpoint_probe.py --domain 73 --hold 150
scratch domain 73

viz_probe_flags_only     the four constructor switches alone - THE COUNTEREXAMPLE
   strip_residual=False  destroyed=None
   process-side census: {'subscriptions': 1, 'publishers': 1, 'services': 0, 'clients': 0, 'timers': 0}

viz_probe_full_recipe    the same switches AND the one explicit teardown
   strip_residual=True  destroyed='/parameter_events'
   process-side census: {'subscriptions': 1, 'publishers': 0, 'services': 0, 'clients': 0, 'timers': 0}
```

The census above is the **process's** view and is not the proof. The proof is
what the graph advertises, asked from a shell in that domain with the CLI
daemon stopped first (`docs/LESSONS.md` 2026-08-05):

```
$ export ROS_DOMAIN_ID=73 && ros2 daemon stop && ros2 node list
/viz_probe_flags_only
/viz_probe_full_recipe

$ ros2 node info /viz_probe_flags_only          <-- THE COUNTEREXAMPLE
/viz_probe_flags_only
  Subscribers:
    /probe_scan: sensor_msgs/msg/LaserScan
  Publishers:
    /parameter_events: rcl_interfaces/msg/ParameterEvent
  Service Servers:

  Service Clients:

  Action Servers:

  Action Clients:


$ ros2 node info /viz_probe_full_recipe
/viz_probe_full_recipe
  Subscribers:
    /probe_scan: sensor_msgs/msg/LaserScan
  Publishers:

  Service Servers:

  Service Clients:

  Action Servers:

  Action Clients:
```

**Read this pair rather than the second half of it.** Both nodes were built
with `enable_rosout=False`, `start_parameter_services=False`,
`enable_logger_service=False` and the `start_type_description_service=False`
override — every opt-out the framework offers. The first still advertises
`/parameter_events` to the graph. A build that trusted those four switches
would have advertised a publisher while claiming none, **in exactly the check
meant to prove the claim** (`docs/LESSONS.md` 2026-08-06 #99). One explicit
`destroy_publisher` at construction is the difference, it lives in
`subscribe_only.py`, and the counterexample is constructed there too so that
the factory remains the only place in this layer that builds an rclpy object
at all.

This is also, exactly, what the word *construction* is claiming and no more:
one line of source. Hence the phrase's second half — **not enforced by the
middleware**.

## 5. The vehicle, up in its own domain

Two sides, started separately, exactly as `EVIDENCE_VEHICLE_IMAGE.md` §1 does
it — because this service must reach into a boundary that is real.

```
$ export GZ_PARTITION=viz13b && gz sim -r -s -v 2 sim/worlds/warehouse.sdf
== gz topics ==        12
== ROS processes on the sim side (expect none) ==   0

$ export GZ_PARTITION=viz13b && python3 agv/forklift/scripts/vehicle_image.py --vehicle F001
serial                F001
domain id             51   (from allocation.yaml)
ROS_DOMAIN_ID=51  GZ_PARTITION=viz13b
...
[INFO] [launch.user]: Nav2 active.
```

`process has died` count: **0**. The three `planner_server` / `controller_server`
inflation-radius `[ERROR]` lines are the vehicle layer's own standing
configuration warnings and are unrelated to this layer.

The subscription set, read from the vehicle's domain before the monitor
joined, so the QoS this layer chose can be checked against the producers
rather than assumed:

| topic | publisher | reliability | durability | what `viz` subscribes with |
|---|---|---|---|---|
| `/map` | `map_server` | RELIABLE | **TRANSIENT_LOCAL** | `LATCHED` — the map was published once, before this process existed; a VOLATILE reader would wait for a next message that never comes |
| `/amcl_pose` | `amcl` | RELIABLE | TRANSIENT_LOCAL | `LIVE` (VOLATILE reader, compatible) |
| `/forklift/scan` | `forklift_bridge` | RELIABLE | VOLATILE | `LIVE` |
| `/tf` | `forklift_ekf` **and** `amcl` | RELIABLE | VOLATILE | `LIVE` |
| `/tf_static` | `sensor_tf` | RELIABLE | TRANSIENT_LOCAL | `LATCHED` |

**A note on the instrument, recorded because it cost time.** `ros2 topic list
--no-daemon` in this domain returned a **partial graph** — no `/map`, no
`/amcl_pose`, no `/forklift/scan`, no `/tf` — while all four were live and
were received by a plain rclpy subscriber in the same domain seconds later.
`ros2 topic echo` likewise reported *"does not appear to be published yet"*
for topics publishing at 50 Hz. Every `ros2` observation in this file was
therefore taken with the daemon **stopped, restarted and given several
seconds to populate**, and the graph reported by a cold or short-window CLI
was not trusted for anything (`docs/LESSONS.md` 2026-08-05 #118, one class
wider than lifecycle state).

**And the stimulus.** A first attempt to give AMCL some motion used
`ros2 topic pub -r 5 /forklift/cmd/traction_speed` for 14 s; ground truth
moved **0.036 m** and the command never took — the delivery failure of
`docs/LESSONS.md` 2026-07-28 #72, in its `-r` form rather than its `--once`
form. Driving from a small rclpy publisher instead moved the vehicle
**-4.46 m → +3.33 m** and turned it, and only then did `/amcl_pose` appear.

**Why the pose stream is intermittent, and why that is the vehicle's property
and not this layer's.** `amcl` publishes `/amcl_pose` on a filter update, so a
standing vehicle produces none. The monitor shows exactly that: the pose count
climbs 0 → 17 during the drive and then stops, and its **age grows** rather
than the value keeping its live look.

```
[  155.2s] F001 pose_age_ms=None    obstacles_age_ms=62.5 map_version=1 msgs={'map': 1, 'pose': 0, 'scan': 1541, 'tf': 9229}
[  160.2s] F001 pose_age_ms=567.1   obstacles_age_ms=70.1 map_version=1 msgs={'map': 1, 'pose': 2, 'scan': 1591, 'tf': 9530}
[  175.2s] F001 pose_age_ms=79.3    obstacles_age_ms=81.8 map_version=1 msgs={'map': 1, 'pose': 13, 'scan': 1741, 'tf': 10430}
[  180.2s] F001 pose_age_ms=288.0   obstacles_age_ms=90.5 map_version=1 msgs={'map': 1, 'pose': 17, 'scan': 1791, 'tf': 10731}
[  185.2s] F001 pose_age_ms=5293.2  obstacles_age_ms=92.6 map_version=1 msgs={'map': 1, 'pose': 17, 'scan': 1841, 'tf': 11031}
[  200.2s] F001 pose_age_ms=20315.5 obstacles_age_ms=46.6 map_version=1 msgs={'map': 1, 'pose': 17, 'scan': 1991, 'tf': 11929}
```

The service was started from an ordinary shell with **no `ROS_DOMAIN_ID` at
all**:

```
$ python3 viz/monitor/service.py --status-period 5
monitoring service - read-only by construction of the process and proven by test; not enforced by the middleware
allocation table  .../agv/forklift/vehicles/allocation.yaml
ROS_DOMAIN_ID in this shell: None - not used; each context carries its own domain
watching   F001  domain 51   node viz_monitor_f001         subs 5 publishers 0 services 0 clients 0
   /parameter_events destroyed at construction - the constructor flags alone do not reach zero on Jazzy
http  GET only  http://127.0.0.1:8089/  (405 for every other verb)
```

---

## 6. `ros2 node info` on the running monitor node, from inside the vehicle's domain

**DESIGN §8.1. This is the check the claim stands on.**

```
$ export ROS_DOMAIN_ID=51 && ros2 daemon stop && ros2 daemon start && sleep 8
$ ros2 node list
/amcl                    /behavior_server        /bt_navigator
/bt_navigator_navigate_to_pose_rclcpp_node       /cmd_vel_to_tricycle
/controller_server       /envelope_gate          /forklift_bridge
/forklift_ekf            /forklift_io            /global_costmap/global_costmap
/imu_gate                /launch_ros_143487      /local_costmap/local_costmap
/map_server              /obstacle_zone          /planner_server
/sensor_tf               /transform_listener_impl_55d766f30a60
/transform_listener_impl_55d803963e50            /transform_listener_impl_55f81fa8cf30
/velocity_smoother       /viz_monitor_f001       /wheel_odometry

$ ros2 node info /viz_monitor_f001
/viz_monitor_f001
  Subscribers:
    /amcl_pose: geometry_msgs/msg/PoseWithCovarianceStamped
    /forklift/scan: sensor_msgs/msg/LaserScan
    /map: nav_msgs/msg/OccupancyGrid
    /tf: tf2_msgs/msg/TFMessage
    /tf_static: tf2_msgs/msg/TFMessage
  Publishers:

  Service Servers:

  Service Clients:

  Action Servers:

  Action Clients:
```

**Subscribers 5. Publishers 0, service servers 0, service clients 0, action
servers 0, action clients 0** — asked of the graph inside the vehicle's own
domain, with the CLI daemon restarted first.

### 6.1 The stronger form: the monitor alone in the domain

After §8 stopped the vehicle stack, domain 51 held the monitor and nothing
else, so the domain's entire topic list is everything the monitor and the
measuring instrument together contribute:

```
$ ros2 node list
/viz_monitor_f001

$ ros2 topic list -t
/amcl_pose [geometry_msgs/msg/PoseWithCovarianceStamped]
/forklift/scan [sensor_msgs/msg/LaserScan]
/map [nav_msgs/msg/OccupancyGrid]
/parameter_events [rcl_interfaces/msg/ParameterEvent]
/rosout [rcl_interfaces/msg/Log]
/tf [tf2_msgs/msg/TFMessage]
/tf_static [tf2_msgs/msg/TFMessage]
```

`/parameter_events` and `/rosout` are on that list, so the list was **not**
taken as the answer — it was asked who publishes them:

```
$ ros2 topic info /parameter_events --verbose
Publisher count: 2
  Node name: _ros2cli_147480                                   <- the command asking
  Node name: _ros2cli_daemon_51_a52415437bdc4f67b62726b55e14ce28  <- the CLI daemon
Subscription count: 0

$ ros2 topic info /rosout --verbose
Publisher count: 1
  Node name: _ros2cli_daemon_51_a52415437bdc4f67b62726b55e14ce28
```

Both publishers belong to the **instrument**, one of them to the very command
asking the question. The monitor publishes neither and does not even subscribe
`/parameter_events` (subscription count 0). This is the shape of the trap §4
describes: a topic list alone would have read as "the monitoring node
advertises `/parameter_events`", which is precisely the false claim the
teardown exists to prevent — and precisely why the check is `ros2 node info`
on the node, not a topic list of the domain.

---

## 7. The HTTP face — DESIGN §8.3 and §8.5

Run from a shell with no ROS environment at all: the operator side receives the
vehicle's map, pose and obstacles **from outside that DDS domain**.

### 7.1 The method matrix — every verb but GET is 405

```
$ python3 viz/tools/http_probe.py --serial F001
=== CHECK 8.3a  method matrix: GET is the only verb ===
path                                         GET     HEAD     POST      PUT   DELETE    PATCH  OPTIONS     FROB
/                                            200      405      405      405      405      405      405      405
/vehicles                                    200      405      405      405      405      405      405      405
/vehicles/F001/state                         200      405      405      405      405      405      405      405
/vehicles/F001/map                           200      405      405      405      405      405      405      405
/vehicles/F001/cameras                       200      405      405      405      405      405      405      405
/vehicles/F001/cameras/front/stream          404      405      405      405      405      405      405      405

the 405 body and its Allow header:
   Allow: 'GET'
   {"error": "method not allowed", "allow": "GET", "why": "this service is read-only by
    construction of the process and proven by test; not enforced by the middleware
    (viz/DESIGN.md section 2). It has no write surface to reach with any verb."}
```

`FROB` is in the matrix on purpose: the refusal is not a list of known verbs
but the handler's attribute lookup itself, so a verb nobody anticipated lands
on the same 405. Each POST/PUT/PATCH above carried a body
(`{"traction": 1.0}`) that was never read — no code path in `http_face.py`
touches `rfile`, and the refusal closes the connection rather than leaving an
unread body to be mis-parsed as the next request.

### 7.2 The GET payloads, serial-rooted at n = 1

```
GET /vehicles  -> 200  298 bytes
{
  "serials": ["F001"],
  "vehicles": [
    {"serial": "F001", "domain_id": 51, "node": "viz_monitor_f001",
     "state": "/vehicles/F001/state", "map": "/vehicles/F001/map",
     "cameras": "/vehicles/F001/cameras"}
  ],
  "allocation_table": ".../agv/forklift/vehicles/allocation.yaml"
}

GET /vehicles/F001/state  -> 200  5719 bytes
{
  "serial": "F001", "domain_id": 51, "node": "viz_monitor_f001",
  "pose": {"x_m": 6.475026054345174, "y_m": 12.54142947704358,
           "yaw_rad": 0.08165466653701614, "frame": "map"},
  "pose_age_ms": 715.6,
  "obstacles": {"frame": "map", "source_frame": "nav_lidar_link", "placed": true,
                "points": [[-0.38, 10.6226], [-0.0635, 10.556], [0.4127, 10.5399], ...],
                "returns": {...}},
  ...
}
```

Every path is rooted in the VDA 5050 **serialNumber**, at n = 1 exactly as at
n = 4, and the serial and its domain came from `allocation.yaml` through
`vehicle_identity.load_allocation` — the vehicle layer's one code path, named
in the payload so a reader can check it. Obstacle points are in the **map
frame**, composed from the vehicle's own `/tf` + `/tf_static`
(`placed: true`, `source_frame: nav_lidar_link`).

### 7.3 No raster on the JSON poll

```
=== CHECK 8.3c  /state carries no raster ===
   /state is 6150 bytes
   keys: ['domain_id', 'map_age_ms', 'map_cells', 'map_meta', 'map_version',
          'messages_received', 'node', 'obstacles', 'obstacles_age_ms', 'pose',
          'pose_age_ms', 'serial', 'subscriptions', 'tf_frames', 'watching_for_s']
   map_cells is 248460 - a COUNT of cells, not the cells
   largest fields: [('obstacles', '5365 bytes'), ('map_meta', '140 bytes'), ('tf_frames', '126 bytes')]
```

The largest field on the poll is the obstacle coordinate list at 5.4 kB —
values, not bulk pixels. The map's 248 460 cells appear on the poll only as
an integer.

### 7.4 Map integrity — the whole grid, never a crop

```
=== CHECK 8.5  map integrity ===
   GET /vehicles/F001/map -> 200  5077 transported bytes, gzip
   headers: version=1 cells=248460 606x410 res=0.05000000074505806
            origin=(-9.145, -4.778) frame=map
   decompressed: 248460 cells; width*height = 248460
   two fetches byte-identical: True
   map_version stable across fetches: True
   cell value histogram (top 4): [(188430, 0), (53603, 255), (6427, 100)]
   cells that are neither 0 nor 255 (0xFF = -1 unknown): 6427
   map messages received = 1; map_version = 1  -> one bump per received message: True

HTTP PROBE PASS
```

606 × 410 at 0.05 m/cell is **30.3 m × 20.5 m** — the whole warehouse map at
full extent, not a vehicle-centred window. The three cell values are the
occupancy-grid convention verbatim: `0` free (188 430), `0xFF` = −1 unknown
(53 603), `100` occupied (6 427). 248 460 raw cells transport as **5 077
gzipped bytes**, which is why no image encoder was needed and no dependency
was proposed. `map_version` equals the number of map messages the process
received, both read from the same running process.

---

## 8. The vehicle stack stopped mid-run — DESIGN §8.4

The whole vehicle image was stopped by signalling its process group, 12 s into
an 80 s sampling window, with the monitoring service left running untouched.

```
--- stopping the vehicle stack at 05:28:27Z: launcher pid 143487 pgid 143463 ---
--- vehicle stack processes remaining ---
(vehicle stack gone)

=== CHECK 8.4  ages under a stopped vehicle stack ===
 elapsed     pose_age_ms   obstacles_age_ms     map_age_ms   msgs(pose)
     0.0        463157.1               69.0       729890.9           30
     5.0        468158.8               68.4       734892.6           30
    10.0        473160.4               68.5       739894.2           30
    15.0        478162.2             3771.0       744896.0           30     <- stack stopped
    20.0        483166.3             8775.1       749900.1           30
    30.0        493169.1            18777.9       759902.9           30
    45.0        508173.7            33782.5       774907.5           30
    60.0        523178.8            48787.6       789912.6           30
    75.0        538183.1            63791.9       804916.9           30

HTTP PROBE PASS
```

The obstacle age goes from **68 ms to 63.8 s** and keeps climbing; no value
keeps its live look. The service's own log across the same window:

```
[  740.9s] F001 pose_age_ms=472914.5 obstacles_age_ms=23.5    ... msgs={'map': 1, 'pose': 30, 'scan': 7391, 'tf': 44325}
[  745.9s] F001 pose_age_ms=477920.5 obstacles_age_ms=3529.3  ... msgs={'map': 1, 'pose': 30, 'scan': 7406, 'tf': 44419}
[  750.9s] F001 pose_age_ms=482926.5 obstacles_age_ms=8535.3  ... msgs={'map': 1, 'pose': 30, 'scan': 7406, 'tf': 44419}
   ...
[  826.0s] F001 pose_age_ms=558021.5 obstacles_age_ms=83630.3 ... msgs={'map': 1, 'pose': 30, 'scan': 7406, 'tf': 44419}
```

The message counters **freeze** at `scan: 7406, tf: 44419` and the ages grow.
The service did not exit — `pgrep` found it alive after the window — and it
logged **one status line every 5 s and nothing else**: 171 lines total across a
15-minute session, no error at any rate, and `stopped cleanly` at teardown.

Every age above is `time.monotonic()` arithmetic. The service never subscribed
`/clock`: the simulated clock arrives over the same `ros_gz` bridge as the
scans, so a staleness clock taken from it would have stopped in the same
instant as the data it was meant to be watching (`docs/LESSONS.md` 2026-08-06
#100).

---

## 9. The camera mechanism, exercised without a camera — DESIGN §7

No camera exists on the model until V3-4, so `/vehicles/F001/cameras` serves an
empty list and the stream path answers 404 before any refcount is taken
(§7.1's matrix). The **lifecycle a camera will use** is built, and was
exercised against a topic that does exist — `/forklift/imu` — by a second,
short-lived service instance standing beside the running one:

```
$ python3 viz/monitor/service.py --no-http --node-suffix _refcount \
      --refcount-demo /forklift/imu --demo-rounds 1 --demo-hold 14

watching   F001  domain 51   node viz_monitor_f001_refcount subs 5 publishers 0 services 0 clients 0
   /parameter_events destroyed at construction - the constructor flags alone do not reach zero on Jazzy
[F001] round 1: viewers 0 -> 1 -> 2; subscriptions 5 -> 6
     endpoints while open: {'subscriptions': 6, 'publishers': 0, 'services': 0, 'clients': 0, 'timers': 0}
     one viewer left: refcount 1; subscriptions 6 (the subscription SURVIVES a non-last close)
     last viewer left: refcount 0; subscriptions 6 -> 5
     endpoints after close: {'subscriptions': 5, 'publishers': 0, 'services': 0, 'clients': 0, 'timers': 0}
```

And the same three moments seen from **inside the vehicle's domain**, which is
where it matters:

```
=== t+9s   TWO viewers hold the stream open ===      === t+35s  last viewer closed ===
/viz_monitor_f001_refcount                           /viz_monitor_f001_refcount
  Subscribers:                                         Subscribers:
    /amcl_pose: ...                                      /amcl_pose: ...
    /forklift/imu: sensor_msgs/msg/Imu   <-- created     /forklift/scan: ...
    /forklift/scan: ...                                  /map: ...
    /map: ...                                            /tf: ...
    /tf: ...                                             /tf_static: ...
    /tf_static: ...                                    Publishers:
  Publishers:
                                                       Service Servers:
  Service Servers:
                                                       Service Clients:
  Service Clients:
                                                       Action Servers:
  Action Servers:
                                                       Action Clients:
  Action Clients:
```

At **t+22 s**, with one of the two viewers closed, `/forklift/imu` is still
listed — the subscription survives a non-last close, which is what a refcount
is for. **Publishers stayed 0 before, during and after**, which is the
V3-PLAN §2 item 5 requirement in full: selecting a view is create/destroy of an
operator-side subscription, and **no message of any kind entered the vehicle
domain** when the view opened or closed.

---

## 10. What is proven here, what is not, and the residuals

**Proven, by the runs above.**

| DESIGN §8 | Where | Verdict |
|---|---|---|
| 1. `ros2 node info` — subscribers > 0, publishers/services/clients/actions 0, daemon restarted first | §6, §6.1, §9 | **pass**, on the live node in the vehicle's own domain, in three separate observations |
| 2. Entity-creating calls only in `subscribe_only.py` | §2 | **pass**, 6 names, one hit each |
| 3. Non-GET → 405; GETs answer the §5 payloads; `/state` carries no raster | §7.1–§7.3 | **pass**, 8 verbs × 6 paths |
| 4. Vehicle stack stopped: ages grow, service survives, logging bounded | §8 | **pass** |
| 5. Map bytes equal the last received grid; `map_version` bumps once per map message | §7.4 | **pass** |
| 6. The unqualified read-only phrase is absent from `viz/` | §2 | **pass**, 11 occurrences classified, 0 bare |

**Not proven, and not claimed.**

- **n > 1.** One vehicle exists (`allocation.yaml` carries `F001: 51` and
  nothing else), so the multi-context mechanism ran with **one** context. The
  cross-domain isolation of several contexts in one process was measured at
  design time (`DESIGN.md` §4, scratch domains 71/72) and **not** re-measured
  here. The surface is n-shaped — serial-rooted paths, per-serial links, the
  vehicle list read from the table — but the second vehicle is the test, and
  it does not exist yet.
- **Any camera figure.** No camera is on the model; §9 exercises the lifecycle,
  not a stream. Nothing here says what a camera costs.
- **Middleware enforcement.** Nothing in DDS prevented any of this. The claim
  is, and stays, *read-only by construction of the process and proven by test;
  not enforced by the middleware*. What would remove the limitation is recorded
  in `DESIGN.md` §2 and is not scheduled.
- **Timing.** No latency figure is quoted anywhere in this file. The ages in
  §5 and §8 are arrival ages of a stream, not a measurement of this layer's
  delay, and one session's timing on this machine has already been shown to
  move by 60× between runs (`docs/LESSONS.md` 2026-08-04).

**Residuals.**

- **R1 — the pose stream is intermittent by the vehicle's design.** `amcl`
  publishes `/amcl_pose` only on a filter update, so a standing vehicle has no
  pose stream at all and the page will render a growing age. That is correct
  behaviour of this layer and a **display question for HMI v2b**: a pose
  minutes old must not be drawn like a live one. Flagged rather than solved
  here, because the fix belongs on the page.
- **R2 — the `ros2` CLI's graph view was unreliable in this domain** in a
  wider way than `docs/LESSONS.md` 2026-08-05 #118 records (topics, not only
  lifecycle state; `--no-daemon` worse than a warmed daemon, not better). Every
  observation in this file was taken with the daemon restarted and given time.
- **R3 — `/map` is a single latched message in this build**, so `map_version`
  reaching 1 and staying there is the whole of the "bumps once per message"
  observation. A vehicle that republished its map would exercise the counter
  further; none does today.
- **R4 — the frame composition is planar.** `/tf` is walked as (x, y, yaw), which
  is exact for this vehicle's tree and would silently drop a pitched or rolled
  sensor mount. The four sensor mounts are fixed and level in `model.sdf`; a
  tilted mount would need the composition widened, and a frame the walk cannot
  reach yields **no points** (`placed: false`) rather than an assumed identity.

**Teardown, observed rather than assumed.** The service, the vehicle image and
Gazebo were all stopped and `pgrep` reported no survivor of any of them; the
`ros2` daemons in domains 51 and 73 and the default domain were stopped; the
service printed `stopped cleanly`; `/dev/shm` was returned to the two unrelated
`lttng-ust` entries it held before the session.
