# Report — m5-30 HMI v3 plan

    brief:               issued in-session (no brief file); owner feedback of
                         2026-08-05 on the v2a screenshots, boundary ruled the
                         same day (v2b stays in M5; only beyond-criterion parts
                         are v3)
    status:              done
    files_changed:
      - hmi/V3-PLAN.md                      (new — the plan, no code)
      - docs/reports/m5-30-hmi-v3-plan.md   (this report)
    invariants_touched:  none. The plan adds zero OPC UA nodes and zero HMI
                         writes; every new datum rides the ADR 0011 D4
                         monitoring plane, and the plane's read-only property
                         is carried as a per-phase observable check
                         (publishers zero in the vehicle domain), not a
                         promise.
    open_questions:
      - the owner decisions the plan leaves open are listed once in
        V3-PLAN.md §7: m5-13 mechanism + directory (standing), read-only
        enforcement vs recorded limitation (standing), camera
        count/placement/resolution/rate and viewing concurrency, the map goal
        tool (§12.13 item 4), and the monitoring-plane content widening
        beyond map/pose/obstacles.
    next_suggested:      fold V3-PLAN.md §2 (the five m5-13 shaping
                         constraints) into the m5-13 brief when it is written —
                         that is the only time-critical piece of this plan.

## The one thing worth reading first

**v3 does force v2b design decisions, and they are cheap today and expensive
later.** m5-13 has not been briefed, so V3-PLAN.md §2 states five constraints
to hand its brief:

1. **Per-vehicle (serialNumber-rooted) namespace on the monitoring service's
   page-facing surface from day one**, even at n = 1 — M6 is four vehicles
   (ADR 0016) and a surface baked at n = 1 is the LESSONS-104 defect one
   layer up.
2. **Serve the whole warehouse map, not a vehicle-centred crop** — a crop
   satisfies criterion (e) and forecloses the owner's ask 2; the full map
   costs v2b nothing.
3. **Bulk pixels never ride the JSON poll** — every raster (map now, camera
   frames at v3) is its own HTTP stream per kind.
4. **The D3c mechanism ruling should see v3's load**: `domain_bridge`
   forwards a fixed named topic set (heavyweight image topics forwarded
   whether watched or not, config churn per camera); a multi-context
   subscriber can create/destroy camera subscriptions on demand. Load
   information for the owner's ruling, not a pre-emption of it.
5. **"Camera selection" must be implementable as subscription lifecycle
   only** — never a service call, parameter write or publisher into a
   vehicle domain. An m5-13 design that would need a vehicle-side toggle to
   start a stream forecloses ask 4 and must be caught at briefing.

## What the plan contains

- **Boundary section**: what v2b is expected to deliver (criterion (e)'s map
  clause via m5-13 + the reserved third column, plus the restated
  "no external request" header sentence the m5-29 review names) and what v3
  adds on top — mode-conditional joystick, RViz-grade interaction, the full
  information inventory, cameras. v3 replaces nothing in v2b.
- **Five phases** in the m5-22 §4 house style, each with one observable
  done-condition, files touched, a does-NOT list and its owner-decision flag:
  V3-1 joystick-only-in-teleop (rendering only; the eight-node write stream
  provably continues in every mode); V3-2 the information page built from a
  datum inventory; V3-3 the RViz-grade map (explicitly refusing RViz's
  2D-goal tool — §12.13 item 4 is the owner's); V3-4 the camera added to the
  model and **measured before anything consumes it** (the model has no
  camera today, so this is agv + sim work); V3-5 camera streams on the page
  by subscription lifecycle, with the vehicle-domain publishers-zero check in
  the done-condition.
- **The inventory** (§4): "every piece of information" turned into a table by
  single owner — PLC-owned, F-mirror, vehicle-layer via monitoring plane,
  backend-own — with a "must NOT derive" column per row (no vehicle-alive
  from the raw counter, no mode from anything but `ForkliftDriveModeActive`,
  no localization-quality verdict, no camera-OK beyond the page's own stream
  age). One flag raised: path/goal-state display is a **content widening of
  ADR 0011 D4's "map, pose, obstacles"** — read-only and PLC-free, but a
  scope statement to be made in a document, not accreted.
- **The camera budget** (§6): the measured facts quoted as TODO/m5-22 print
  them (910 rays free headless, GUI ~8 RTF points, 2.7–2.9 cores per stack,
  four projected at 12–14 of 20); the camera cost stated as **unmeasured and
  unclaimable**, with the two framing facts (llvmpipe software rendering;
  unknown whether Gazebo renders an unsubscribed camera) and the exact probe
  that would measure it (four cells: headless/GUI × unsubscribed/subscribed,
  m5-22 §3 recipe). The give-order if it does not fit: resolution, rate,
  one-at-a-time, fewer camera-vehicles, then the owner drops the ask against
  numbers.
- **Structural read-only** (§5): five mechanisms, led by "v3 adds zero OPC UA
  nodes and zero writes", plus the standing qualification that
  read-only-by-construction is a source-code property until m5-13 rules
  enforcement (judge finding 6) — inherited, not solved here.

## Scope compliance

No code, no template, no configuration written; nothing committed; no branch
created. No node or topic invented — the camera topic is a request to `agv/`,
the stream endpoints a request to whichever directory m5-13 rules, and MJPEG
is named as the no-new-dependency candidate with anything beyond it flagged
as proposed-and-waiting. Writes confined to `hmi/V3-PLAN.md` and this report.
