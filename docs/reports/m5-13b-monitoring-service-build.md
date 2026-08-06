# Report — m5-13b monitoring service build

    brief:               m5-13b (dispatch prompt; no file in docs/briefs/)
    status:              done
    files_changed:
      - viz/README.md                                   (new — the boundary statement, DESIGN §1 verbatim)
      - viz/monitor/subscribe_only.py                   (new — the one entity factory)
      - viz/monitor/vehicle_link.py                     (new — one vehicle: context, node, refcounted subs, value store)
      - viz/monitor/http_face.py                        (new — GET-only HTTP surface)
      - viz/monitor/service.py                          (new — the process)
      - viz/tools/check_construction.py                 (new — DESIGN §8.2 and §8.6, static)
      - viz/tools/zero_endpoint_probe.py                (new — §8.1's mechanism, passing and failing side by side)
      - viz/tools/http_probe.py                         (new — DESIGN §8.3, §8.4, §8.5)
      - viz/EVIDENCE_MONITORING.md                      (new — the dated runs; headings written before the first command)
      - docs/reports/m5-13b-monitoring-service-build.md (this report)
    invariants_touched:  none.
                         Inv 1 — untouched by construction: nothing on this
                           plane is a command path, and the layer touches no
                           safety datum.
                         Inv 4 / 11 — no OPC UA, no MQTT, no PLC, no hmi/
                           internals; the two edges used are the already-drawn
                           CLAUDE.md §3 circle-ended edges (NAV --o MON,
                           MON --o HMI). No new topology edge.
                         Inv 10 — the layer originates only arrival ages, which
                           watch itself; the serial→domain mapping is read
                           through the vehicle layer's one code path
                           (vehicle_identity.load_allocation) rather than
                           re-parsed; the forbidden-call list has one owner and
                           the checker reads it rather than copying it.
                         Nothing outside viz/ was written.
    open_questions:
      - CLAUDE.md §4's repository-layout listing does not carry viz/. The §3
        topology already draws the MON box, so invariant 11 is satisfied, but
        the directory list is now one entry short of the tree. It is the
        owner's file — requested, not made.
      - docs/PLAN.md and docs/TODO.md are outside this agent's scope and are
        not updated here (roadmap criterion (e)'s monitoring half is now
        built; HMI v2b is the remaining consumer).
      - R1 in EVIDENCE §10: amcl publishes /amcl_pose only on a filter update,
        so a standing vehicle produces no pose stream at all. The service
        renders that as a growing age, correctly. How a pose minutes old is
        DRAWN so it cannot read as live is HMI v2b's question, and it should
        be in that brief rather than discovered on the page.
      - n > 1 is unproven here and is stated as unproven: allocation.yaml
        carries one vehicle, so the multi-context mechanism ran with one
        context. DESIGN §4's cross-domain isolation probe (scratch domains
        71/72) was not re-run. The second vehicle is the test.
      - Dependencies added: none. domain_bridge stays rejected and unused;
        the map is served as raw gzipped int8 cells specifically so no image
        library was needed.
    next_suggested:      brief HMI v2b against DESIGN §5's endpoint table and
                         EVIDENCE §7's actual payloads, carrying R1 as a
                         rendering requirement.

## What was built

`viz/`, a new top-level layer, exactly as `viz/DESIGN.md` §1 ruled it. One
process, one rclpy `Context` per vehicle domain, one zero-endpoint node per
context, one executor thread, a refcounted subscription manager, and a GET-only
stdlib HTTP face on `127.0.0.1:8089` — its own port, not the HMI backend's
8088. `viz/README.md` opens with "This layer must not access", verbatim from
DESIGN §1.

## The claim, and how it is proven rather than asserted

The phrase survives unchanged everywhere — **read-only by construction of the
process and proven by test; not enforced by the middleware** — and a checker
sweeps for the short form with whitespace, blockquote markers, comment markers
and *adjacent Python string literals* normalised first. It classifies all 11
occurrences in `viz/` and prints each; DESIGN §2's own "Never the unqualified…"
sentence is classified as a prohibition notice rather than exempted.

Two defects the checker caught while it was being written, both recorded in
EVIDENCE §2: a long claim inside a `print()` wraps as `'… of the process '
'and proven by test …'`, which hid the phrase from the first version of the
sweep and made three files read BARE; and the checker's own `CLAIM` constant
was itself a literal instance of the short form, now assembled from two pieces
so the file is not an instance of what it forbids and needs no exemption.

**The zero-publisher proof, with the failing variant beside it.** DESIGN §4's
finding reproduced exactly. Two nodes in one scratch domain, differing only in
whether the residual publisher is destroyed:

```
$ ros2 node info /viz_probe_flags_only      $ ros2 node info /viz_probe_full_recipe
  Subscribers: /probe_scan                    Subscribers: /probe_scan
  Publishers:                                 Publishers:
    /parameter_events                         Service Servers:
  Service Servers:                            ...
```

Every opt-out the framework offers was set on both. The counterexample is
constructed inside `subscribe_only.py` on purpose, so the factory stays the
only place in the layer that builds an rclpy object at all.

**On the running node, in the vehicle's own domain** (EVIDENCE §6): subscribers
5 — `/map`, `/amcl_pose`, `/forklift/scan`, `/tf`, `/tf_static` — and
publishers 0, service servers 0, service clients 0, action servers 0, action
clients 0. Repeated in §6.1 with the vehicle stopped, when the monitor was
alone in domain 51: `/parameter_events` and `/rosout` still appear on
`ros2 topic list`, and asking who publishes them names `_ros2cli_147480` (the
command asking) and the CLI daemon — the instrument, not the subject. That is
why the check is `node info` on the node and never a topic list of the domain.

## Proven against a running vehicle

Gazebo headless (`GZ_PARTITION=viz13b`) plus the vehicle image in domain 51,
started separately; the monitoring service started from a shell with **no
`ROS_DOMAIN_ID` at all**, and the operator side received the whole map, live
pose and live obstacles over HTTP from outside that DDS domain. The map is
606 × 410 cells at 0.05 m — 30.3 × 20.5 m, full extent, byte-identical across
fetches, 248 460 cells transporting as 5 077 gzipped bytes. `/state` is 6 kB of
values with the map present only as an integer cell count. The method matrix is
8 verbs × 6 paths: 405 on everything but GET, including an invented verb, with
no request body ever read. Stopping the whole vehicle image mid-run took the
obstacle age from 68 ms to 63.8 s while the message counters froze; the service
neither exited nor logged anything but its one status line per 5 s.

The camera lifecycle of DESIGN §7 is built and was exercised on `/forklift/imu`
by a second short-lived instance: two viewers create one subscription, a
non-last close leaves it in place, the last close destroys it — observed three
times from inside the vehicle's domain — with publishers 0 before, during and
after, and no message of any kind entering that domain.

## The five V3-PLAN §2 constraints, as built

1. **Serial-rooted at n = 1** — every path is `/vehicles/<serial>/…`; the serial
   and its domain come from `allocation.yaml` through the vehicle layer's one
   code path, and the payload names the table it read.
2. **The whole map, never a crop** — full extent served; the page pans.
3. **No bulk pixels on the JSON poll** — `/state`'s largest field is the 5.4 kB
   obstacle coordinate list; the raster has its own endpoint.
4. **The D3(c) mechanism** — one multi-context process; `domain_bridge` not
   used and no dependency added.
5. **Selection as subscription lifecycle only** — the refcounted manager, with
   the permanent map/pose/scan/tf subscriptions as entries in the same manager.

## Scope compliance

Only `viz/` and this report were written. `agv/`, `hmi/`, `plc/` and `bridge/`
were read and not touched. Nothing was committed and no branch was created.
The run was taken alone — no simulator, no ROS process, no daemon and nothing
on either port before it started, all recorded in EVIDENCE §1 — and the
teardown was observed rather than assumed: every process gone by `pgrep`, both
CLI daemons stopped, `/dev/shm` returned to what it held before.
