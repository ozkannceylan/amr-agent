# FIELD-EVALUATION — protective and warning field evaluation for the forklift twin (m5-12, design)

**This is a design document. No code exists behind it yet**; the build brief
follows it. It specifies how the two safety scanners' measurement data become
protective- and warning-field verdicts, how those verdicts are shaped and
transported to the stand-in writer of `plc/forklift-safety/SPEC.md` §7, and
what happens under every way the input can fail.

**This is not a safety claim, in whole or in part** (ADR 0011 D5). The
evaluation designed here is a **model of what a safety-rated scanner does
internally**, feeding a **stand-in for wiring**. It runs as standard software
on a rendered depth image that has no integrity, no fault reaction and no
diagnostic coverage. Every PL and Category named below is a **PLr target**
from `docs/safety/SRS.md` and `docs/safety/PL-SCENARIOS.md`, never an
achievement. No response time, stopping distance or field depth derived here
is a figure any machine is characterised by.

| Item | Value |
|---|---|
| Date | 2026-08-05 |
| Brief | `docs/briefs/m5-12-field-evaluation-design.md` |
| Consumer | the stand-in writer, `plc/forklift-safety/SPEC.md` §7.2 — **not designed here** |
| Serves | roadmap M5 criterion (a): "a protective-field intrusion in Gazebo trips an F-latched stop … with no hand at a watch table anywhere in the chain" |
| SRS functions modelled | SF-03 (protective stop, **target** Cat 3 PL d), SF-04 (warning-field creep, no PL claim, PLr b floor per SC-06) — both as stand-ins |

---

## 1. What this is, and where it sits in the chain

```
Gazebo gpu_lidar (10 Hz, two scanners, measurement channels)
    → FIELD EVALUATION (this design; WSL, one node)
        → one TCP link, WSL client → Windows writer, port 45015 (SPEC §7.2)
            → stand-in writer, 50 ms republish, PLCSIM Advanced API by tag name
                → SafetyInputStandIn.ZoneDeviceCircuitClosed
                    → F-OB (100 ms) → ZoneStopDemand latches → …
```

The scanners see the world; this node decides **"there is something in the
protective field"** and hands that verdict, safety-shaped, to the writer. It
is the piece that makes criterion (a)'s chain originate in Gazebo rather than
in a script. The latch, the monitored reset and the observable stop are all
downstream and are all already specified (SPEC §5, §7); this node reports
**levels** and latches nothing.

**Two fields, as a real installation has them:**

- **protective field** — intrusion opens the zone channel and stops the
  vehicle (via the F-latch and the envelope);
- **warning field** — larger; intrusion demands creep speed (SF-04's
  behaviour) and does not stop.

## 2. The consumer contract, and that this output suits it

`plc/forklift-safety/SPEC.md` §7.2 already fixes the transport and is not
re-designed here:

| Property | SPEC §7.2 says | This design's fit |
|---|---|---|
| Transport | one TCP connection, WSL client → Windows listener, port 45015 | the evaluation node is that client |
| Payload | newline text: `ZONE 0` / `ZONE 1` **at every verdict transition**, `PING` at 1 Hz | `ZONE 0` = intrusion (channel open), `ZONE 1` = clear (closed); one `ZONE <current>` line is sent immediately on every (re)connect, because a fresh connection is a transition from unknown |
| Writer cycle | 50 ms level republish | **compatible, and comfortably**: verdict transitions occur at scan cadence (10 Hz) or slower, so the writer always holds a level younger than its own cycle. No change to §7 is needed |
| Link silent > 1 s | writer drives the zone channel **open** (`FIELD_LINK_STALE_MAX`) | this is the evaluation's own death handled by its consumer, in the demanding direction; the evaluation adds nothing to it and relies on it |
| Level repair | TCP delivers or the connection dies; a dead connection is an intrusion at the writer | no level-repair traffic is added beyond the spec's vocabulary. Silence here is *not* a standing order (LESSONS 2026-08-04) precisely because the consumer's contract converts silence into the demanding value |

**Where the verdict does *not* go: a ROS topic.** `config.yaml` (m5-06 owner
ruling) fixes the rule *"the safe channel has no topic on either transport,
ever — every channel a subscriber can reach is a measurement channel"*. The
protective verdict is the safe-channel equivalent, so it crosses **only** the
dedicated §7.2 link, exactly as a real device's OSSD pair crosses only its
copper. The brief's phase-1 phrase "a verdict on a topic" is read as "on the
link"; the conflict is stated in the m5-12 report rather than resolved
silently. The **warning** verdict is not an OSSD equivalent (SF-04 carries no
claim and runs in vehicle software), so it *may* be a ROS topic; its consumer
is an open question (§12, phase 2).

**What the evaluation reads.** The front scanner's measurement channel is
already bridged (`/forklift/safety_scanner_front/measurement`); the rear one
has no ROS name yet, reserved as
`/forklift/safety_scanner_rear/measurement` for "when a consumer appears"
(`config.yaml`). **This node is that consumer**; the build brief bridges the
rear channel under the reserved name. Stated honestly: in the real device the
safe verdict is formed inside the housing from the same rays; here it is
formed across a bridge and a graph, which is one more reason no claim
attaches (§10).

## 3. The response-time chain — every term, with its source

The protective field's depth is bought with time, so the time is added up
first, worst case per stage. Budgeted terms are design allowances for stages
nobody has measured; each is named again in §11 as a measurement to take, and
per LESSONS 2026-08-05 (m5-11/m5-21) a measured latency on this host is a
draw, not a bound — which is why budgets, not samples, enter the arithmetic.

**Demand formation (Gazebo intrusion → F-latch):**

| # | Stage | Worst case | Source |
|---|---|---|---|
| t1 | intrusion appears → next scan samples it | **100 ms** | `model.sdf`, both scanners 10 Hz |
| t2 | scan transport (gz → bridge → node) + evaluation compute + verdict formed | **30 ms** budget | budget; measurement to take (§11) |
| t3 | `ZONE 0` transit, WSL → Windows TCP | **10 ms** budget | budget; measurement to take (§11) |
| t4 | writer applies it at its next cycle | **50 ms** | SPEC §7.1, writer cycle |
| t5 | next F-OB samples the channel and latches | **100 ms** | `FOB_RTG1` cyclic 100 ms, read back 2026-08-04 (SPEC §7.1) |
| | **T_demand** | **290 ms** | |

**Observable reaction (F-latch → vehicle begins decelerating).** In the twin
the consequence travels the process network by construction (SPEC §7.8): the
standard program reads the F-data and drops the envelope, the bridge carries
it, the envelope gate ramps.

| # | Stage | Worst case | Source |
|---|---|---|---|
| t6 | standard-program scan forms the envelope drop | **20 ms** budget | budget; measurement to take (§11) |
| t7 | bridge republishes the envelope | **50 ms** | 20 Hz, `opcua-nodes.md` §12.10 |
| t8 | gate reacts to the non-permissive envelope | **100 ms** budget | observed 0.0681 s, n = 1 (`EVIDENCE_ENVELOPE.md` §3); budgeted up because n = 1 |
| | **T_react** | **170 ms** | |

**Total response time before deceleration begins: T = 0.46 s.**

**Then the ramp**: the gate decelerates at its configured 0.50 m/s²
(measured 0.4926–0.5024 m/s² across n = 4 stops, `EVIDENCE_ENVELOPE.md`
§10), so braking adds v²/(2·0.50) = v² metres. The measured whole:
**0.850 s and 0.1738 m from 0.40 m/s** (§3 there, n = 1; 0.1719–0.2187 m
across contexts) is the reference this arithmetic must stay consistent
with: 0.40 × 0.068 + 0.40²/1.0 = 0.187 m predicted from the *gate-local*
chain, against 0.1738 m observed — the model is slightly conservative at
the gate, which is the right direction.

**A real device note carried for honesty**: real scanners evaluate 2–8
consecutive scans before switching their OSSDs, adding (n−1) scan periods to
t1. This model trips on **one** scan (§8), defensible only because the
simulated sensor has no noise model (`model.sdf` declares none); a noise
model added later re-opens t1.

## 4. The depth derivation — the heart of this document

```
depth D(v) = v · T          distance travelled during the total response time
           + v² / (2a)      braking distance at the vehicle's own ramp, a = 0.50 m/s²
           + Z              measurement allowance
           [+ Kp · T]       intruder advance during the response time — provisional, see below
```

**Framing, and its provenance — stated per the brief's rule.** The proper
frame is EN ISO 13855's general minimum-distance equation — current edition
form **S = (K × T) + DDS + Z** (clause 5, "General equations for the
calculation of the overall system stopping performance and minimum
distances"), K = 1600 mm/s for walking approach — applied to a
vehicle-carried field the way ISO 3691-4 and the scanner class's mobile
application manuals apply it: the **vehicle's** motion during T plus its
braking distance is the dominant term, plus device allowances. **The project
has no access to either standard's text; the clause identification above
comes from secondary engineering sources read 2026-08-05, and this derivation
is therefore marked PROVISIONAL** — the structure is standard practice, but
no coefficient below is claimed to be a verbatim normative value. What was
used instead: the general S = K·T + C / S = K·T + DDS + Z form as documented
by machinery-safety engineering references, and the mobile-application
practice of dimensioning against vehicle stopping performance.

**The terms, each with its source:**

| Term | Value | Where it comes from |
|---|---|---|
| T | 0.46 s | §3, summed per stage |
| a | 0.50 m/s² | the gate's own ramp, measured 0.4926–0.5024 over n = 4 (`EVIDENCE_ENVELOPE.md`) |
| Z | **0.05 m** | range resolution 0.01 m (`model.sdf`) + worst observed render deviation 0.0133 m (`EVIDENCE_SENSOR_COVERAGE.md` §13.3) + margin. The analogue of a real device's Zsm |
| Kp | 1600 mm/s, **provisional** | the walking-approach constant of ISO 13855 as reported by secondary sources. Whether the vehicle-carried case must add intruder advance at all is exactly what the unreachable text settles; real AGV field calculations commonly size against a stationary intruder. **The demanding reading is carried**: fields are sized *with* the Kp·T term (= 0.74 m), and both columns are shown |
| v ceilings | 0.60 m/s (`nav2.yaml` max_velocity, the in-force autonomous regime); 1.00 m/s (`TRACTION_SPEED_MAX`, the PLC's ground-speed ceiling); 0.30 m/s (the muted-detection creep cap, SF-10 / SC-13) | quoted, not re-derived |

**The table** (a = 0.50 m/s², T = 0.46 s, Z = 0.05 m):

| v [m/s] | v·T | v²/2a | Z | D without Kp | Kp·T | **D with Kp (bound)** |
|---|---|---|---|---|---|---|
| 0.30 | 0.138 | 0.090 | 0.05 | 0.28 m | 0.74 | **1.02 m** |
| 0.60 | 0.276 | 0.360 | 0.05 | 0.69 m | 0.74 | **1.43 m** |
| 1.00 | 0.460 | 1.000 | 0.05 | 1.51 m | 0.74 | **2.25 m** |

**Detection-capability floor, checked before any depth is accepted.** The
simulated scanners fire 1.00°/ray, so the guaranteed-struck object width at
range r is r × 0.017453. Holding the 70 mm leg-detection criterion of the
modelled device class, a ray is guaranteed to strike a 70 mm object only
within **4.01 m of the sensor**. Every field boundary below is checked
against the 4.0 m floor of whichever device covers that bearing.

## 5. Does the required depth fit? — the question that decides the design

Answered per travel direction, against the measured coverage
(`EVIDENCE_SENSOR_COVERAGE.md`) and the R1, R3, R8 constraints.

**Drive direction (+x).** The front device covers the corridor; the worst
in-corridor point of a field of depth d sits ≈ √((0.16+d)² + 1.0²) from the
front sensor, so the 4.0 m floor allows **d ≤ 3.71 m** ahead of the nose
(x = +0.86). Setting D(v) = 3.71 and solving v² + 0.46v + 0.79 = 3.71 gives
**v = 1.49 m/s** — the geometry closes at essentially the model's own 1.50
m/s tread limit. At the PLC ceiling of 1.00 m/s the required 2.25 m fits with
1.4 m to spare. **Drive-first: fits at every reachable speed.**

**Fork direction (−x), unloaded.** The corridor beyond the tine tips
(x = −1.875) is covered by the **rear** device at 2.6 m or less over most
bearings — inside its floor — but bearings **169.4–174.4°** are occluded from
the rear device by the carriage (R1) and rely on the front device alone, at
≈ 4.0 m for a field boundary 1.41 m past the tine tips. The floor therefore
caps the usable fork-direction depth at that worst bearing to **≈ 1.41 m**.
Solving D(v) = 1.41: v² + 0.46v + 0.79 = 1.41 gives **v = 0.59 m/s** with the
Kp term, **0.97 m/s** without it. **Fork-first at the 1.00 m/s ceiling does
not fit, and at 0.60 m/s it fits only on the non-provisional reading** (1.43
needed vs 1.41 usable misses by 2 cm on the bound reading).

**Fork direction, loaded (R3).** A pallet in the plane costs 39.9° centred on
the fork axis; **no field can watch through the load** and no mounting fixes
it. This is the muted-personnel-detection case, and the honest handling is
the one ISO 3691-4 practice and SC-13 already name: **≤ 0.3 m/s creep**,
enforced by the (modelled) SLS, not by any field.

**The ruling this forces — a speed-dependent field set**, which is what real
scanners do, with one lowered ceiling:

| Case | Condition | Speed ceiling | Protective depth (from vehicle outline / tine tips) |
|---|---|---|---|
| **A — drive-first** | travelling +x, no load in plane, lift out of the R2 window | 1.00 m/s (PLC ceiling) | **2.25 m** ahead; flanks 1.02 m (sized for a 0.3 m/s lateral closing case) |
| **B — fork-first, unloaded** | travelling −x, no load in plane, lift out of the R2 window | **0.55 m/s** (lowered: geometry closes at 0.59) | **1.35 m** past the tine tips (D(0.55) = 0.253 + 0.303 + 0.05 + 0.74) |
| **C — muted** | load intersects the plane, **or** lift travel in the R2 window 0.05–0.10 m | **0.30 m/s** | fork sector 164.5–204.4° **excluded** (unmonitorable); all other bearings 1.02 m |

Case B's 0.55 m/s is a cap on **reverse** speed only and lands as one
`nav2.yaml` value in the build brief (min_velocity −0.55); drive-first keeps
0.60. The ceilings are *reported* by this node with its case selection; the
**enforcement** of a speed cap is never this node's — it belongs to the
envelope/gate chain as process behaviour and to the modelled SF-10 as the
backstop (SC-14). Phase 1 implements case B's geometry as a **static**
all-direction field (§6) so that no case-selection logic sits in front of
criterion (a).

## 6. Field geometry, exactly

All fields are polygons **fixed in each scanner's own frame** (the frame its
message names), derived from the vehicle outline plus the depths of §5, and
**clipped by each device's measured self-return contour minus 0.05 m** — a
field drawn past the vehicle's own returns is permanently violated (R8's
verdict: this is field geometry configured on the device, categorically not a
filter applied to samples).

| Clip | Value | Source |
|---|---|---|
| Rear device, sensor frame −131.5° … −72.3° | field boundary inside **0.090 m** — effectively the sector is excluded from rear fields; the front device covers those bearings | `EVIDENCE_SENSOR_COVERAGE.md` §13, R8 |
| Rear device, R2 lift window (travel 0.05–0.10 m) | the tine reaches **1.022 m** in that band — handled by case C, not by a travel-dependent contour | §13.5; R2 "must not treat 0.05–0.10 m as equivalent to 0" |
| Front device, bearing ≈ 182.5° | self-return at **1.084 m** (left rear wheel): clip below 1.03 m at that bearing | §13.6 |
| Lateral half-width, both corridors | **0.55 m** = vehicle half-width 0.45 + Z 0.05 + steering-deviation allowance 0.05 | derived; the allowance is a budget, §11 |

**Warning field.** Derived, not chosen: the warning boundary must let a
walking person be met by a protective field already sized for creep, so
W(v) = D_case-C + v·T_w + (v² − 0.09)/(2·0.50) + Kp·(T_w + (v − 0.3)/0.50),
with T_w = 0.30 s (warning chain budget, §11). That gives **W(0.55) ≈ 2.7 m**
fork-first and **W(1.00) ≈ 5.0 m** drive-first — and the second **exceeds the
device class's own reach** (4.95 m all-round, R6). Stated rather than
smoothed: at the full drive-first ceiling the warning field saturates at the
coverage boundary and cannot fully pre-empt a walking approach; SF-04 is
backed unconditionally by SF-03 (SRS SF-04 safe-state row), carries no PL
claim, and the shortfall is a property real installations of this range class
share. The warning field is best-effort by construction and says so.

**Residuals inherited, restated for the verdict** (every one is the
installation's, none is silently designed around):

| Residual | Effect on this design |
|---|---|
| **R1** — carriage-occluded patch, bearings 169.4–174.4°, radius ≈ 1.9–2.35 m, ≈ 0.17 m wide | sits **inside** every fork-first field. Unmonitorable and structural (no mount angle removes it). An adult's stance is wider than 0.17 m, so a standing person presents at least one leg outside the patch; a single centred limb is the accepted residual, named here and in case B's evidence narration |
| **R3** — load occlusion 39.9° | case C; no field claim in the load sector, creep cap is the mitigation (SC-13) |
| **R4** — 0.10 m `range_min` annulus | unmonitorable; worse in simulation because gz reports below-minimum strikes as *out of range* (observed, §13.2) — indistinguishable from clear-beyond-range. Fields start at `range_min` by construction; the annulus is named as the stand-in's blind ring; a real device fault-monitors its near zone and adds mechanical protection |
| **R8** — rear self-return band | clipped out per the table above; costs no coverage (front covers the sector) |

## 7. The OSSD-equivalent contract

A real scanner presents **two driven outputs**, both read, so a single
failure is detectable. The equivalent here, per device and stated flatly for
what it buys:

- **The pair**: each device evaluation produces `(A, B)` where **A = "field
  clear"** and **B = NOT A** (antivalent), carried together with a
  monotonically increasing sequence number and the source scan's stamp, in
  **one record emitted atomically**.
- **"Both agree"** means A == ¬B on the same record. A record where A == B is
  a **discrepancy**.
- **Discrepancy tolerance: zero records.** Because the pair travels in one
  atomic record, no timing skew between channels exists to tolerate; any
  disagreement is corruption, is a **device-evaluation fault on the spot**,
  and the fault verdict is **intrusion** (§8 rule 0). This is stricter than a
  hardware pair's discrepancy time and costs nothing here.
- **The aggregation**: vehicle verdict = intrusion **iff any** device reports
  intrusion **or** any device evaluation is faulted or stale. The union is
  what covers the circle, so a single device failure demands a stop — one
  scanner is never "enough to keep driving".
- **What the pair buys, honestly**: detectability of stuck-at and corruption
  in the record path and the aggregation — **shape, not integrity**. Both
  channels are computed by one process from one scan; they share every
  failure of the rays and of the process. That is exactly the sharing
  `README.md` ("Two channels per safety scanner") already declares, and it is
  why no Category is claimed (ADR 0011 D5).

**The transition log is part of the contract** (SPEC §7.6 names it as
criterion (a) evidence, §10 open item 9): one file per session, unique name
per start (LESSONS 2026-07-28), wall-clock stamped, one line for every
per-device verdict transition, every aggregate transition, every fault-class
change, every link state change, each carrying the triggering scan's stamp
and sequence number. A zone transition in the writer's log with no matching
line here is not criterion-(a) evidence, whatever the narration says.

## 8. Failure behaviour — per failure, each with its own verdict

**Rule 0, stated once and applied to every row: the safe direction is the
demanding one — unknown means intrusion.** Never the reverse.

**Sample classification, written affirmatively** with the fault in the ELSE
(LESSONS 2026-07-27; the 2026-07-29 empty-horizon lesson is rule 2):

```
in_range_return  := (range_min <= r) AND (r <= range_max)      # a measurement: object at r
clear_beyond     := (r = +inf)                                 # a measurement: clear to range_max
valid            := in_range_return OR clear_beyond
ELSE                                                           # NaN, negative, finite < range_min,
                                                               # finite > range_max
    -> invalid sample
```

A NaN fails every comparison and falls through to the ELSE — but the form
above is affirmative first, so the omission trap LESSONS 2026-07-27
(2026-07-27 §57) names cannot re-open under a later edit.

| # | Failure | Detection | Verdict | Why this direction is safe |
|---|---|---|---|---|
| 1 | **Scanner publishes nothing (dead)** | freshness, affirmatively: `fresh := (0 <= now - stamp) AND (now - stamp <= 0.30 s)` — three scan periods, this node's own design value, distinct from every other stale window in the repo | that device's evaluation is **stale → intrusion**; aggregate → intrusion; `ZONE 0` sent while the link lives | a dead sensor proves nothing about the field; only a fresh scan can prove clear |
| 2 | **Empty horizon — every return beyond range** | all rays classify `clear_beyond` | **CLEAR.** An `inf` return is a **measurement — "clear to range_max"** — not missing data. The field verdict needs no finite return anywhere; it needs no *invalid* ray inside the field | LESSONS 2026-07-29: the opposite reading latched a false stop in open space on this vehicle. The demanding direction is not "stop on everything"; it is "never call unknown clear" — and a beyond-range return is not unknown. The one dishonesty in this class is inherited R4: gz reports a sub-`range_min` strike as out-of-range too (observed, §13.2), so the 0.10 m annulus reads clear; named as the stand-in's blind ring in §6, not silently accepted |
| 3 | **Scan stale but arriving** (frozen stamp, or stamps not advancing) | `advancing := stamp_new > stamp_last` per message, AND the rule-1 age test on the latest stamp | not fresh **→ intrusion** for that device | a republished old scan is a picture of a world that may have changed; "not yet proven stale" is not "alive" (LESSONS 2026-07-28 boot-polarity: the verdict boots INTRUSION and stays there until the first fresh, advancing, valid scan is seen) |
| 4 | **One scanner fails, the other healthy** | rules 1/3/5 fire per device | failed device → intrusion → **aggregate intrusion; the vehicle stops** | coverage is a property of the **union** (360° only at 3–4 m by both together); driving on the surviving half would be driving with known blind sectors. The healthy device's verdict is still computed and logged, so the evidence shows *which* device failed |
| 5 | **Values outside the physical window** (NaN, negative, finite < range_min, finite > range_max) | the ELSE class above | an invalid sample **inside a field sector counts as an intrusion of that field**; more than 5 % invalid samples in one scan → **device fault → intrusion** and a fault line in the log | an invalid ray cannot prove its sector clear; a sensor producing garbage at rate is not a sensor. The 5 % threshold is a design value; the fault clears only after 3 consecutive scans below it |

**Clear is debounced, intrusion is not.** Intrusion asserts on **one** scan
(the sim sensor has no noise model — §3's honesty note). Clear requires **3
consecutive fully-valid, fully-clear scans** (0.3 s): asymmetric on purpose,
instant to demand and slow to release. Downstream the demand **latches
anyway** (SPEC §5 `ZoneStopDemand`, cleared only by the monitored reset), so
this debounce shapes the reported level, never the latch. SF-04's warning
release keeps its own 2 s clear-hold (SRS SF-04), implemented downstream of
the warning verdict, not here.

## 9. The channel split, and why this evaluation is the safe channel's model

m5-06's split (owner ruling 2026-07-30; `EVIDENCE_SENSOR_TF.md`,
`config.yaml`): the device class emits a **safe channel** and a separate
**non-safe measurement channel**; the gz scan *is* the measurement channel;
the safe verdict is **derived from the same rays by field evaluation, which
is what the real device does internally — that derivation is this design**.
Why the placement matters: the safe-shaped output must never appear where a
process subscriber could quietly become its consumer (no ROS topic, §2), must
reach exactly one consumer (the writer) over a dedicated link whose loss is
demanding at the consumer, and must never feed a navigation consumer. The
measurement channels stay non-safe, keep their topics, and `obstacle_zone.py`
keeps reading the front one untouched — nothing here modifies the M4 comfort
stop.

## 10. What this design does not claim

1. **No achieved PL, Category, SIL, PFH, MTTFd, DCavg or CCF** — ADR 0011
   D5's list, binding. SF-03's Cat 3 PL d and SF-08's PL c are **targets**.
2. **No safety function exists in this node.** One software process, one
   scan source per device, no redundancy, no test pulses, no diagnostics —
   the OSSD shape is a data shape (§7).
3. **No verified normative coefficient.** The ISO 13855 framing is from
   secondary sources; T's budgeted terms are unmeasured; Kp's applicability
   is unresolved. The derivation is **provisional** and §11 names what
   hardens it.
4. **The response chain is the twin's, not a machine's.** t4–t8 exist only
   because the stand-in and the process-network consequence exist; a real
   scanner-to-STO chain contains none of them (ADR 0011 D1: onboard,
   hardwired).
5. **Nothing here enforces a speed.** Cases report; enforcement is the
   envelope chain (process) and the modelled SF-10 (SC-14's subject).

## 11. Measurements to take — named, not estimated

| # | Measurement | Hardens |
|---|---|---|
| 1 | scan-stamp → verdict-formed age, distribution over ≥ 10 min | t2 |
| 2 | `ZONE` line send → writer log receipt (one clock, the WSL side, against the writer's wall-stamped log) | t3 |
| 3 | standard-program F-read → envelope drop, in-CPU | t6 |
| 4 | end-to-end: Gazebo intruder spawn stamp → `ZoneStopDemand` in the consumer's view — this is criterion (a)'s evidence run in any case | T_demand whole |
| 5 | envelope drop → gate first reduced command **through a real bridge** (ADR 0014's own open item, restated) | t7 + t8 |
| 6 | whether Nav2 in the warehouse world ever commands reverse (fork-first) travel, and at what speed | whether case B is reachable autonomously |
| 7 | lateral deviation of the vehicle from its commanded corridor during a full-speed stop | the 0.05 m steering allowance in §6 |

## 12. The build plan

**Phase 1 — the static protective field and the link (unblocks the writer
and criterion (a)).**
One node, `agv/forklift/scripts/field_evaluation.py`, plus a `field:` block
in `config.yaml` (every constant of §3–§8 named there, per this directory's
rule) and the rear-channel bridge line in `launch/vehicle.launch.py`. The
field is **case B's geometry as one static all-direction contour** (fork
sector 1.35 m, drive sector 1.35 m — deliberately the *smaller* derived
depth everywhere, paired with phase 1's speed regime capped at 0.55 m/s in
`nav2.yaml`, so the static field is never undersized for the speed in
force), clipped per §6. Per-device OSSD-equivalent records, aggregate
verdict, TCP client per §2, transition log per §7, failure rules per §8.
**Done when**: with the stack up, (i) an intruder model entering the contour
in Gazebo produces `ZONE 0` on the link and a matching transition-log line;
(ii) removing it produces `ZONE 1` after the 0.3 s clear debounce; (iii)
killing one scanner process/topic produces `ZONE 0` within 0.30 s + transit;
(iv) killing the node itself leaves the writer driving the zone open within
its own 1 s stale rule — each observed in the writer's session log, which is
the consumer's view. **Does NOT**: touch `plc/`, publish the protective
verdict on any ROS topic, implement the warning field, implement case
switching, enforce any speed, add any dependency.

**Phase 2 — the warning field.**
Warning polygon per §6, verdict on a ROS topic (non-safe, named in
`config.yaml`), 2 s clear-hold. **Done when** AT-04's first observation is
demonstrable: obstacle in warning field only → creep demanded within one
field-report cycle, protective field untouched. **Does NOT**: pick the creep
enforcer — the consumer of the warning verdict is an owner/interface
question raised in the m5-12 report.

**Phase 3 — the monitoring-case set.**
Case selection from travel direction, lift travel (R2 window) and load state;
case A/B/C fields per §5; the selected case and ceiling published as state
for evidence. **Done when** the transition log shows the case switching on a
lift traverse through 0.05–0.10 m and on direction reversal, with the field
in force matching §5's table. **Does NOT**: enforce ceilings; touch SF-10's
modelling, which is `docs/safety/`'s.
