# HMI v2b — the map pane: design (m5-53)

**Design and build in one brief.** The build is `hmi/static/index.html`,
`hmi/hmi_server.py` and `hmi/tools/`; the evidence is `hmi/EVIDENCE_HMI.md`
section J. Authority order: `viz/DESIGN.md` §5 owns every endpoint and every
payload key this page consumes and is quoted, never restated; `hmi/V2A-DESIGN.md`
owns everything already on the page and is **not modified by this version**;
ADR 0011 D4 owns the monitoring plane; `hmi/V3-PLAN.md` §2's five constraints
were fixed by the monitoring design and are honoured here rather than
rediscovered.

**Scope.** M5 criterion (e)'s last clause, word for word: the HMI *"shows a
real-time map with live obstacles"*. The whole warehouse map, the vehicle's
pose, the navigation lidar's returns — and **the age of every one of them**.

---

## 1. The one resolved ambiguity, stated first

**AMCL publishes `/amcl_pose` only on a filter update.** A vehicle that is
standing still therefore has *no pose stream at all*, and the monitoring
service's own evidence records exactly that: `viz/EVIDENCE_MONITORING.md` §8
shows `pose_age_ms = 463 157` — seven minutes and forty-three seconds — beside
message counters that had stopped at 30 while everything else was healthy.

A page that draws that value as a vehicle sitting on the map is **silently
wrong and looks exactly like a working display**. It is the failure
`docs/LESSONS.md` 2026-08-06 (#108) exists to prevent, and it is this
version's central design problem.

> **The ruling: this page has no rendering that means "live". Every position
> and every obstacle it draws is labelled with the age of the datum it came
> from, in every state, and the label is part of the marker rather than a
> field beside it. There is nothing for a stale value to decay into, because
> nothing was ever drawn as current in the first place.**

Everything in §4 follows from that sentence.

---

## 2. Ruling: the page reads the monitoring service **through this backend**, same-origin

`viz/` serves `127.0.0.1:8089` and sends no `Access-Control-Allow-Origin`
header, so a `fetch` issued by a page served from `127.0.0.1:8088` is refused
by the browser before it reaches the socket. Three ways out, and the one taken:

| Option | Verdict |
|---|---|
| Add CORS headers to `viz/` | **Rejected.** `viz/DESIGN.md` §1 makes "knows nothing of `hmi/`" a boundary property of that layer. Editing the monitoring service so the HMI can reach it inverts that, for the HMI's convenience. It is also outside this brief's write scope |
| Serve the page from `viz/` | **Rejected.** The operator page is the HMI. Moving it would put an operator interface inside the layer whose boundary statement says it serves no operator-facing endpoint but its own read-only face |
| **This backend fetches, over loopback, and re-serves under its own origin** | **Adopted.** The `MON --o HMI` edge of CLAUDE.md §3, realised in the HMI's backend half rather than in its browser half. Both halves are the HMI |

Two consequences worth stating, because both are improvements rather than
costs:

1. **The page still makes no external request of any kind.** `index.html`'s
   header sentence was written against CDNs, and `hmi/V3-PLAN.md` §1 expected
   v2b to *restate* it for a cross-origin monitoring fetch. It needs no
   restatement: under this ruling every request the page issues goes to the
   origin it was served from. The sentence stands verbatim.
2. **The failure of the monitoring service is caught in one place**, in a
   process that already knows how to render an unreachable source as unknown,
   instead of in the browser as an opaque CORS error.

### 2.1 What the proxy is, exactly

- **Three inbound paths, `GET` only**: `/monitor/vehicles`, `/monitor/state`,
  `/monitor/map`. They are served from `do_GET` and from nowhere else;
  `do_POST` serves exactly `/control` as it always has and answers everything
  else 404.
- **Outbound, one method literal.** `MonitorProxy` is the only code in `hmi/`
  that opens a socket to the monitoring service, it constructs exactly one
  `urllib.request.Request`, and that construction is `method="GET"`. There is
  no code path in this layer that can issue another verb toward `viz/`, and no
  request body is ever sent. `tools/check_hmi_map_pane.py` proves it by
  sweeping the source and by exercising the socket.
- **Loopback enforced at start.** A `monitor.base_url` whose host is not a
  loopback name refuses to start the process. The monitoring plane is local to
  the operator's machine; it is never a remote transport and never the tailnet
  (invariant 8).
- **Bounded, and off the critical path.** The fetch runs in the HTTP handler
  thread of the already-threaded server, never on the asyncio loop that owns
  the OPC UA session, and it carries a hard timeout. A monitoring service that
  hangs cannot stall a write cycle, a heartbeat or a keep-alive
  (`docs/LESSONS.md` 2026-07-29 #79, one layer over).
- **Nothing is cached.** Every `/monitor/state` is a fresh fetch, because the
  ages in it are measured by `viz/` at the instant it answers; a cache would
  freeze exactly the numbers this whole version is built to keep honest. The
  raster is refetched only when `map_version` changes, which is the monitoring
  design's own rule and not a cache of values.

`viz/DESIGN.md` §2 rules that service **read-only by construction of the
process and proven by test; not enforced by the middleware.** That is the
monitoring layer's claim about itself, quoted here in full because it is the
only form it has, and this version adds nothing that could weaken it: the HMI
sends `GET` and nothing else, and no byte this page produces enters a vehicle
domain.

### 2.2 The page-liveness beacon does **not** count a map fetch

`opcua-nodes.md` §10.8 H6's beacon is refreshed by any request the page makes
— and the three `/monitor/*` paths are deliberately excluded from it.

A monitoring-plane fetch proves the browser is running. It proves **nothing
about the channel that carries the operator's requests**, which is what the
deadman exists to watch. Counting it would let a page whose `/state` poll had
died keep the teleop enable armed on the strength of a map refresh.

The exclusion can only make the beacon go stale **sooner** — requests to rest
sooner, the enable dropped sooner — which is the direction that fails safe.
The H6 harness and the second-tab check are re-run against the changed path
(§7).

---

## 3. What is displayed, and what may not be derived

Forwarded, each with its single owner elsewhere (`viz/DESIGN.md` §6):

| Shown | Owner | Note |
|---|---|---|
| the occupancy grid | the vehicle's map server | **whole map, never a crop**; the page pans and zooms a view over it |
| the pose | the vehicle's localization, as published | drawn only with its age, §4 |
| the obstacle points | the navigation lidar, as published, placed in the map frame by the vehicle's own TF | drawn only with their age, §4 |
| every age | the monitoring service's own steady-clock bookkeeping | **read, never recomputed here** |

**Forbidden on this page, and absent from the build:** any
localization-quality verdict; any classification of an obstacle as near, far,
relevant, dangerous or a fault; any stop, mode, fault or "vehicle alive"
verdict; any fusion of a monitoring-plane value with a PLC value; any safety
statement. The map pane and the process zones share a screen and share no
sentence: no caption combines a pose with a latch, and no lamp anywhere is fed
by anything in this section.

**No transform and no fusion.** Obstacle points arrive already in the map
frame. The page applies one map-to-screen view transform — a pan and a zoom,
which is drawing — and computes no pose, no range and no distance of its own.
When the monitoring service reports `placed: false` (it could not reach the
scan's frame through the vehicle's TF) the pane says the scan could not be
placed, and draws nothing. It never reports that as "no obstacles".

---

## 4. The age rendering — the rule, its boundary, and where the numbers come from

### 4.1 The rule

Every drawn datum carries its age in the same visual element as itself:

- The vehicle marker's label is **`pose as of N.N s`** — always, in every
  state, at every age. There is no state in which the marker is drawn without
  it, and the page never uses the word *live* about a pose.
- The obstacle layer's label is **`N returns as of N.N s`**, on the same terms.
- Two ages are shown, never summed: the monitoring service's arrival age
  (its datum, its clock) and this backend's own fetch age (its channel, its
  clock). A sum would be a third number with no owner (invariant 10).

### 4.2 What happens as the age grows — a ramp, not a verdict

The marker's rendering is a **continuous, monotonic function of the reported
age**: opacity falls and the filled marker converts to a hollow, hatched
outline as the age rises between two published endpoints. Past the upper
endpoint the label becomes **`LAST KNOWN POSITION — as of N s, not a current
position`** and the pane carries a banner saying the same thing in words.

The direction is fixed: every step of the ramp **under-claims**. The most a
faded marker can be wrong about is that the vehicle is exactly where it says
while the page is drawing it as merely where it was — which is the safe half
of the pair (`docs/LESSONS.md` 2026-08-06 #101: where one answer is safe and
the other is not, prefer the tail that fails safe).

**Why this is not the forbidden thing.** ADR 0008 D3 and `opcua-nodes.md`
§10.1 forbid this layer timing a *process value* — a debounce, a fault delay,
a dwell, a stale window that produces a verdict the PLC also computes. Four
facts, each checkable, put the ramp outside that:

1. **The age is not measured here.** It is read from the monitoring service,
   which originates it (`viz/DESIGN.md` §6: arrival ages are the only values
   that layer may originate, because they watch only itself). This page runs
   no clock over any plant signal.
2. **There is no PLC verdict to collide with.** The PLC never sees
   `/amcl_pose`; no node in `opcua-nodes.md` carries a pose, a pose age or a
   localization verdict. Nothing here is a second owner of anything.
3. **Nothing rides on it.** The ramp changes pixels. It gates no control,
   latches nothing, enters no request, changes no write, and is not read by
   any other part of the page. Removing it would change the picture and
   nothing else.
4. **It is not a verdict about the vehicle.** It says how old the page's
   information is, not whether the estimate is good — the localization-quality
   verdict `viz/DESIGN.md` §6 forbids is exactly the one not made.

The judgement call is recorded rather than buried: this is a **display ramp
over the monitoring service's own bookkeeping**, and it is the one place in
v2b where a millisecond appears at all.

### 4.3 Where the two numbers come from — and what they are not

They are **display values, not measured values** (`opcua-nodes.md` §12.11's
design-value rule; `docs/LESSONS.md` 2026-07-27 #46). They live in
`hmi_server.py` as named constants beside this citation and are published to
the page on every `/monitor/state` response, so the page invents no
millisecond of its own — the same discipline v2a applies to
`UI_POLL_STALE_TIME` and `WRITE_HEALTH_STALE_TIME`. They are deliberately
**not** in `config.yaml`, whose own header forbids a threshold in that file.

The honest statement of what could not be derived: the ramp's upper endpoint
would ideally be a bound on the inter-arrival time of `/amcl_pose` **while the
vehicle is moving**, measured with its n. No such measurement exists on this
machine. The only committed capture of that topic
(`viz/EVIDENCE_MONITORING.md` §8) is of a **standing** vehicle — 30 messages,
a 463-second age — which is the residual itself, not a sample of the moving
case. The report requests the measurement rather than fabricating a bound from
one confounded capture (`docs/LESSONS.md` 2026-08-04 #94).

**And the consequence that is not a defect:** because AMCL publishes only on a
filter update, a standing vehicle *always* crosses the ramp and always ends up
drawn as a last known position. That is the truth about what the page knows,
and it is the behaviour this design wants. A page that kept the marker solid
while the vehicle stood still would be flattering the data.

### 4.4 Obstacles, and the three classes that are not a verdict

The monitoring service serves the lidar's returns already separated into the
three classes the vehicle's own README rules: `distance` (a range inside the
window — the only class that becomes a point), `clear_beyond_range` (an `inf`
or a range at or past `range_max`, which is the sensor *measuring* a clear
path, not missing data) and `invalid`. The pane prints all three counts as the
sensor reported them and classifies nothing.

Two renderings that exist to stop a specific lie:

- **Zero distance returns** renders as *"no distance returns in this scan"*
  with the three counts beside it. Never "clear", never "no obstacles", never
  a colour that means safe. `docs/LESSONS.md` 2026-08-06 (#80) is the standing
  reminder that an empty horizon is a measurement; §102 is the reminder that
  a consumer can destroy what a publisher's silence was supposed to say.
- **A stale obstacle layer never renders as an empty one.** Past the ramp the
  points are drawn hatched and the label says how old they are. The page has
  no rendering that means "there is nothing there now".

---

## 5. The pane, concretely

```
+-----------------------------+------------------------+---------------------------+
| A  MODE                     | C  STOPS & RESET       | G  MAP  (monitoring plane)|
+-----------------------------+------------------------+  banner: read-only,       |
| B  TELEOP CONTROLS          | D  F-LAYER MIRROR      |    no command, never the  |
|                             +------------------------+    PLC                    |
|                             | E  ENVELOPE            |  serial chip  F001        |
+-----------------------------+------------------------+  [canvas: whole map,      |
| F  DIAGNOSTICS (drawer, full width)                   |   obstacles, vehicle]     |
+-------------------------------------------------------+  pose as of N.N s        |
                                                        |  M returns as of N.N s   |
                                                        |  map vN, W x H at R m    |
                                                        |  fetched N ms ago        |
                                                        +---------------------------+
```

Zones A–F are **untouched**: same ids, same handlers, same renderings, same
`/state` poll. The map is a third column on a wide screen and a full-width row
below the controls on a narrow one, which is the layout v2a's §11 reserved.

| Element | Rule |
|---|---|
| banner | *"Monitoring plane — read-only view of the vehicle's ROS 2 graph. No command, no setpoint, no reset; this pane never touches the PLC."* Permanent, not a tooltip |
| serial | Every path is rooted in the VDA 5050 serial number, at n = 1 as at n = 4, read from `/monitor/vehicles`. With more than one serial served the pane grows a selector row and nothing else changes |
| the map | The **whole** grid painted at one canvas pixel per cell from the raw `int8` cells, refetched only on a `map_version` change. Free / occupied / unknown are the occupancy-grid convention verbatim, and **unknown is drawn as unknown**, never as free |
| view | Fit, zoom and drag-pan. A view transform is drawing; it changes no datum and posts nothing |
| pose | §4. Marker is a heading arrow; the yaw drawn is the yaw published |
| obstacles | §4.4. One small mark per point, at the coordinates served |
| monitoring service unreachable | The whole pane greys: no map, no marker, no points, no counts — and the reason in words. The process zones are untouched, because the two planes are two sources and the failure of one is not the failure of the other |

## 6. What v2b does not do

| Not in v2b | Why |
|---|---|
| Any write, of any kind, anywhere | the write set is the eight nodes of v2a §2.1 and did not grow by one; the monitoring plane has no write surface to write to |
| Any goal, waypoint or navigation command | how an M5 goal is commanded is an open owner decision (`opcua-nodes.md` §12.13 item 4) |
| Nav2 path, costmap, goal state, particle cloud | the v3 content widening, the owner's call at V3-3 (`viz/DESIGN.md` §6) |
| Cameras | V3-4/V3-5. The lifecycle exists in `viz/`; no camera is on the model |
| Any change to zones A–F, to `/state`, to the node contract or to the write helper | v2a is not modified by this version |
| Any verdict, any fusion, any classification, any safety statement | §3 |

## 7. What the build must show

1. Every `/monitor/*` path answers `GET` and refuses every other verb; the
   source carries exactly one outbound request construction and it is `GET`.
2. A pose whose age crosses the ramp is **photographed** at both ends, and the
   stale end says *not a current position* in the DOM, not only in the picture.
3. Obstacles present and obstacles absent, both photographed, with the three
   return counts read out of the DOM in each.
4. The monitoring service stopped mid-run: the pane greys, the process zones
   are unchanged, and the backend neither exits nor logs at more than a
   bounded rate.
5. The v2a states re-photographed with the pane present, showing them
   unbroken.
6. The H6 page-stale behaviour and the m5-29 second-tab check re-run, because
   §2.2 changed the beacon's input set.
