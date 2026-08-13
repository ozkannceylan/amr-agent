# Report — m5-53b: the HMI map pane joined to the REAL monitoring service

    brief:               m5-53b (dispatch prompt; task 7b, the successor to
                         m5-53's two named residuals)
    status:              done
    files_changed:
      - hmi/tools/capture_v2b_real_screens.mjs   (new — the joint-run instrument.
                                                  Does NOT spawn a monitoring
                                                  double; drives and stops the
                                                  real WSL-side service and the
                                                  vehicle. 22 checks, all passing)
      - hmi/tools/measure_pose_arrivals.py       (new — the measurement m5-53
                                                  requested. HTTP GET only; no
                                                  ROS 2 client anywhere in it)
      - hmi/EVIDENCE_HMI.md                      (new section K; and §J.10's two
                                                  residuals marked closed in the
                                                  same edit, per LESSONS 2026-07-26)
      - hmi/V2B-DESIGN.md                        (§2.1 gains the crossing; §4.3
                                                  gains the measurement. The two
                                                  ramp constants are UNCHANGED)
      - hmi/evidence/capture-v2b-real-2026-08-06.log
      - hmi/evidence/pose-arrivals-2026-08-06-run1-moving.csv       (the run that
                                                  exposed the instrument defect)
      - hmi/evidence/pose-arrivals-2026-08-06-run2-moving.csv
      - hmi/evidence/pose-arrivals-2026-08-06-run3b-moving-fast.csv
      - hmi/evidence/pose-arrivals-2026-08-06-run4-moving-slow.csv
      - hmi/evidence/screenshots/v2b-real-00..07-*.png   (8 shots, gitignored,
                                                  local; named `v2b-real-*` so no
                                                  reader confuses them with §J's
                                                  `v2b-*` captures of the double)
      - hmi/evidence/screenshots/MANIFEST-v2b-real-2026-08-06.txt
      - docs/reports/m5-53b-hmi-viz-joint-run.md        (this report)
    invariants_touched:  none.
                         NO SOURCE FILE UNDER TEST WAS EDITED. `hmi_server.py`
                           and `hmi/static/index.html` are byte-identical to the
                           build m5-53 photographed; the two new files are
                           instruments in `tools/`. Nothing outside `hmi/` was
                           written — `viz/`, `plc/`, `bridge/`, `agv/` and `sim/`
                           are untouched.
                         Inv 4 — no server was added; the HMI is still an OPC UA
                           client only and the monitoring surface is HTTP GET.
                         Inv 8 — the crossing is loopback. WSL2 relays the
                           WINDOWS loopback address to the Linux service, so the
                           backend's loopback rule is satisfied literally, on the
                           address `config.yaml` already named. Never a remote
                           transport, never the tailnet.
                         Inv 10 — no age, pose or obstacle class is recomputed;
                           the measurement instrument DERIVES nothing about the
                           plant, it differences two of the monitoring service's
                           own timestamps.
                         Inv 11 — the edge used is the already-drawn `MON --o
                           HMI`. Nothing imported from `viz/`, `bridge/` or
                           `fleet/`; no ROS 2, gz or MQTT client in `hmi/`.
                         The eight-node OPC UA write set did not grow. No
                           dependency added: stdlib `urllib`/`csv` on the backend
                           side, Node 22's built-in WebSocket for CDP.
    open_questions:
      - THE OWNER'S RULING IS NEEDED ON THE DISPLAY RAMP, and it is the only
        item that blocks nothing but should not be left silent. The measurement
        was taken (§K.4, n = 26 / 77 / 37 over three driving runs) and the
        chosen endpoints only partly survive it. `POSE_AGE_RAMP_START_MS =
        1000` sits at the MEDIAN of brisk driving (831 / 910 ms), so a normally
        driven vehicle is drawn perpetually part-faded; `POSE_AGE_RAMP_FULL_MS
        = 5000` survives brisk driving with 2.4x margin but is crossed by a
        vehicle genuinely being driven at 0.15 m/s (p90 6010 ms, max 6446 ms).
        BOTH failures under-claim, so this is fidelity and not safety.
        §K.4.2 proposes 2500 / 8000 ms with its cost stated (a dead localization
        on a moving vehicle would go undisclosed for up to 0.88 m instead of
        0.35 m) and DID NOT APPLY IT: widening a ramp makes the page claim more,
        which is not a direction an agent takes on its own measurement.
      - THE PLC IS STILL A DOUBLE. Zones A-F were driven by
        `v2a_scenario_double.py` because the controller was with the owner at
        TIA. Only the map pane is joined to reality; the process-plane claims of
        M4 and M5 are untouched by this run and nothing here re-proves them.
      - THE MOTION STIMULUS HAS NO HOME. Driving the vehicle needs an rclpy
        publisher, which cannot live in `hmi/` (this layer must not access
        ROS 2) and which this brief may not write into `agv/` or `sim/`. It ran
        from the session scratchpad and its source is quoted verbatim in
        §K.6 so the run is reproducible. REQUEST: `sim/scenarios/` should own a
        small rclpy drive stimulus. The existing
        `forklift_stimulus.py plant` cannot serve — it shells out to
        `ros2 topic pub -r`, the exact form `viz/EVIDENCE_MONITORING.md` §5
        recorded failing to take (0.036 m in 14 s).
      - A VEHICLE-LAYER OBSERVATION, offered and not acted on. In every driving
        run the forklift moved 10-17 s and then STALLED for the rest of the leg
        — implied speed 0.006 m/s while traction was still commanded at 20 Hz —
        resuming only on the next reversal. Visible in all four CSVs as the
        stalled population (24 of 132 intervals in one run). Nothing in this
        report depends on it and it is not a monitoring-plane matter, but it
        will affect anyone driving this vehicle.
      - ONE REQUEST FOR `viz/`, small: nothing needed changing for this run, but
        `viz/EVIDENCE_MONITORING.md` §8's standing-vehicle capture is now
        joined by a moving-vehicle one and that layer may want to cite §K.4 —
        the `update_min_d / speed` relation is a fact about the vehicle's
        localization that the monitoring service's own staleness prose would
        benefit from. Not made here; `viz/` is outside this brief's scope.
      - CLAUDE.md §4's repository layout still does not list `viz/`, which
        m5-13b already requested and m5-53 repeated. Unchanged; it is the
        owner's file.
    next_suggested:      rule on §K.4.2 option A or B, then the same joint run
                         against the real PLC once TIA is free — that is the last
                         double left on the operator page.

## The crossing, which was the task

The monitoring service needs `rclpy` and runs in WSL; the page, its backend and
the browser run on Windows. **They meet on the address the HMI already had, and
neither layer needed a change.** WSL2 relays the *Windows* loopback address to a
Linux service bound to `127.0.0.1`, so `http://127.0.0.1:8089` on Windows
reaches `viz/monitor/service.py` inside WSL with no proxy, no bind change and no
port forward — and the backend's loopback rule (invariant 8) is satisfied
literally rather than by exception. It was proved with a two-server probe before
anything was built on it, because the usual report is the opposite. The
conditions it depends on are tabulated in `EVIDENCE_HMI.md` §K.1: WSL2 NAT with
`localhostForwarding`, and **no Windows-side listener on 8089**, which would win
silently.

**One fact the double could not have shown.** Across that relay a dead service
presents as a **timeout**, not the refusal a Windows-resident double produces:
the pane's reason line read `URLError: <urlopen error timed out>` after
`1537 ms`. The pane greys and says so either way — the bounded timeout in
`MonitorProxy` is what makes the difference between "grey after 1.5 s" and
"hung" — but a later reader must not expect a refusal here.

## What was proven, with the vehicle up

Real Gazebo, real forklift image in domain 51, Nav2 active, `process has died`
count 0, and the real `viz/monitor/service.py` reporting
`subs 5 publishers 0 services 0 clients 0`. **22 checks, all passing**, eight
captures:

- the whole real map arriving and rendering — `606 x 410 cells at 0.050 m`,
  whole map, never a crop, and the grid the page painted asserted equal to the
  grid the vehicle published;
- the live pose with its age, drawn solid, `6.99, 11.62 m -42 deg as of 0.6 s`;
- real lidar returns as obstacles — `243 distance, 117 beyond range, 0 invalid,
  of 360` — placed in the map frame by the vehicle's own TF, with no verdict of
  any kind on the row;
- **the stale path on a genuinely standing vehicle.** Nothing was frozen and no
  staleness simulated: the stimulus stopped, the forklift stood, and AMCL
  stopped publishing because a standing vehicle produces no filter update. The
  marker went from **54 px of fill to 0 px** — asserted at the pixel level, so
  the picture changed and not the caption — and the label became `LAST KNOWN, as
  of 9.2 s` while the lidar layer beside it was still `0.1 s` old. The two ages
  moved independently, which is the fact that makes a single "vehicle alive"
  verdict impossible and is why this pane makes none;
- **the real service killed mid-session**: pane grey, `—` in every row, canvas
  empty, zones A-F identical field for field before and after, heartbeat still
  advancing, backend still `CONNECTED`. Restarted, the pane recovered by itself
  with no operator action.

The second-tab check was **not** re-run, and deliberately: that obligation is
conditional on touching the posting path, and no file under test was touched.

## The measurement m5-53 could not take

`/amcl_pose` inter-arrival **while moving**, through the same `/monitor/state`
path the page reads, with no browser running and nothing else on the machine.

| Run | Commanded | n | median | p95 | max |
|---|---|---|---|---|---|
| run 2 | 0.35 m/s | 26 | 831 ms | 1205 ms | 1550 ms |
| run 3b | 0.35 m/s | 77 | 910 ms | 1502 ms | 2099 ms |
| run 4 | 0.15 m/s | 37 | 2314 ms | 6196 ms | 6446 ms |

**The structure behind the numbers is the finding.** AMCL is
**distance-triggered** (`update_min_d: 0.25`), not periodic, and every measured
interval covered 0.28-0.30 m of ground at every speed. So the inter-arrival is
`update_min_d / speed`, and **a threshold written in milliseconds is a threshold
written about a speed**: `1000 ms` means "fade below 0.25 m/s" and `5000 ms`
means "call it last-known below 0.05 m/s". Neither sentence was intended when
the numbers were chosen. The verdict and the proposal are above; the recommended
form is to re-state both endpoints as *derived from `update_min_d` and a named
speed*, because written that way they carry their own re-check rule — and one
regime already in this repository, the smoother's 0.025 m/s from-rest floor
(LESSONS 2026-08-05 #124), implies a ~10 s inter-arrival at which no fixed ramp
keeps a creeping vehicle solid.

**Two instrument defects were found by the first runs and are recorded rather
than quietly fixed** (§K.4.3): run 1's reported maximum of 132.8 s was its own
boundary artifact, the interval spanning the parking time *before* the run; and
the first "while moving" classifier used DISTANCE, which passed 35 of 35
intervals — a 50.9-second stall included — because a distance-triggered
estimator makes every interval cover that distance by construction. The
classifier is now implied speed, it is an argument with no hidden default, both
populations print side by side, and every committed CSV stays re-analysable with
`--analyse` so the split can be moved without re-driving the vehicle.

## Addendum, 2026-08-06 — the owner ruled, and the ramp was changed

**Ruling: option B.** `POSE_AGE_RAMP_START_MS` and `POSE_AGE_RAMP_FULL_MS` are
now **2500** and **8000 ms**. Open question 1 above is CLOSED; everything else
in this report stands as written.

    files_changed (addendum):
      - hmi/hmi_server.py                  (the two constants, at their one home,
                                            with the ruling, its date, the cost
                                            and the re-tune rule beside them)
      - hmi/V2B-DESIGN.md                  (§4.3 rewritten around the ruling)
      - hmi/tools/measure_pose_arrivals.py (docstring: the values are measured
                                            now, and this is still how to
                                            re-check them)
      - hmi/tools/capture_v2b_real_screens.mjs  (a `rampband` pass and a
                                            `--prefix` so a re-run cannot
                                            overwrite the run it is compared to)
      - hmi/tools/check_hmi_map_pane.py    (CHECK 4's gzip-MTIME flake, fixed
                                            by comparing MORE, not less)
      - hmi/EVIDENCE_HMI.md                (new §K.7)
      - hmi/evidence/check-map-pane-2026-08-06-ramp2500-8000.log
      - hmi/evidence/capture-v2b-real-ramp-2026-08-06.log
      - hmi/evidence/screenshots/v2b-real-ramp-08..10-*.png  (3 shots)
      - hmi/evidence/screenshots/MANIFEST-v2b-real-ramp-2026-08-06.txt

**One home, and it was verified to be one.** The page reads both endpoints from
`/monitor/state` on every poll; `config.yaml` is forbidden a threshold by its
own header; a sweep of `hmi/static/index.html` and the instruments for a
hard-coded `1000`/`5000` came back empty. Nothing was changed in a second place
because there is no second place.

**The three things kept attached to the numbers**, in `V2B-DESIGN.md` §4.3 and
again beside the constants themselves: why the old pair was wrong (`1000 ms` sat
at the *median* of brisk driving, so the page called a driving vehicle stale
about half the time; `5000 ms` was crossed by a vehicle genuinely driven at
0.15 m/s; both failures under-claimed); **the cost** (0.88 m of undisclosed
travel instead of 0.35 m if localization dies mid-motion — the first trade of
that margin on this pane); and the finding that forbids a blind re-tune (the
localizer is distance-triggered, so each endpoint is a covert statement about a
**speed**, and no fixed pair survives from the 0.025 m/s creep floor to full
travel).

**Did any check move? Yes — two, and neither was weakened.**

1. **`check_hmi_map_pane.py` CHECK 4 was a latent flake, not a regression.** It
   failed on a proxy path the ruling does not touch (`871 vs 871 bytes`). A
   probe compressed the same grid at three inter-request gaps and pinned the
   difference to **byte 4 alone** — the wall-clock `MTIME` RFC 1952 puts in
   every gzip header — with the decompressed cells equal every time. Two
   independent GETs mean two compressions, so the old assertion was really
   testing which side of a second boundary the requests landed on; m5-53's run
   got lucky. The fix excises those four bytes (the whole deflate stream is
   still compared bit for bit) and **adds** a comparison of the decompressed
   cells, which the raw test never made. Seven checks, all PASS.
2. **The new `rampband` pass failed its first attempt, correctly**, and the
   failure was the check doing its job: it gated on the *backend's* age and
   photographed a 0.9 s pose while claiming it was in the 1000–2500 ms band —
   an age that is solid under both ramps and therefore illustrates nothing. The
   gate now reads the age **the page is displaying**, since the pane polls on
   its own 500 ms period. Re-run: 1.1 s and 5.3 s, both inside their bands, ten
   checks all passing.

**Re-captured: only what changes.** Exactly two age bands change appearance, and
both were photographed under the distinct prefix `v2b-real-ramp-*` so §K.3's
captures are untouched and the two runs sit side by side: 1000–2500 ms went from
fading to **solid** (1.1 s, 52 px of fill), and 5000–8000 ms went from
`LAST KNOWN POSITION` to **faded but not last-known** (5.3 s). A third shot
confirms the label still arrives past 8000 ms — widening moved *when* it
arrives, it did not remove it. The before-halves already existed and were not
re-taken: `v2b-real-07` (2.7 s, 0 px) and `v2b-real-04` (9.2 s, `LAST KNOWN`).
Everything else — a 0.6 s pose, the service-down and recovery states — renders
identically under both pairs and was deliberately left alone.

## Housekeeping

The evidence was written in two tranches — the measurement after its runs, the
captures after theirs — rather than sentence by sentence as each state landed.
Both tranches were written before this report and both quote tool output rather
than recollection. The WSL stack (Gazebo, the vehicle, the monitoring service)
and every Windows-side instrument process were stopped at the end of the run and
the machine was confirmed clean, so nothing is left holding the owner's cores
while TIA is open.
