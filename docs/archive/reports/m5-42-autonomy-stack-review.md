# m5-42 — the autonomy stack: everything standing between here and criterion (d)

    brief:               docs/briefs/m5-42-autonomy-stack-review.md
    status:              done — criterion (d) decomposed with a verdict per
                         clause, AT-02/03/04 read in the SRS and analysed
                         against what is built, the defect register verified
                         and extended, and the ordered work list in §5.
    files_changed:
      - docs/reports/m5-42-autonomy-stack-review.md   (this file; the review is read-only)
    invariants_touched:  none — this brief reads
    open_questions:      folded into the findings; the two owner decisions are
                         items 1 and 2 of §5
    next_suggested:      issue §5 item 1 (the safety-spec AT round) first —
                         nothing AT-shaped can even be scheduled until the
                         observables and the SF-02/SF-03 semantics are ruled

Verdict on the gate question: **criterion (d) is not closeable today, and two
of its AT clauses are not closeable by anything currently planned** — not
because the work is large (it is), but because AT-02, AT-03 and AT-04, read
word for word in the SRS, demand observables and mechanisms that no design in
this repository produces: VDA 5050 state messages that nothing at M5 emits, a
vehicle e-stop channel that does not exist, a bumper the model does not carry,
and an auto-releasing protective-field inhibit that the built F-latch
contradicts. That is said per CLAUDE.md §10 rather than redefined. Everything
else in (d) is reachable by the list in §5. The honest total is **well beyond
one working session** — §6 sizes it.

---

## 1. Criterion (d), clause by clause

Roadmap M5 row, criterion (d), word for word decomposed. The artifact deciding
each verdict is named.

| # | Clause | Verdict | Deciding artifact |
|---|---|---|---|
| d1 | "SLAM builds a map of the **warehouse world**" | **met, with one live defect** | `sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md`, the committed grid, the m5-08d world→map registration (residual max 0.141 m). The map is a frozen artifact scored in its own right (PLANT-CHANGE-INVENTORY §2.2), so neither the plant change nor the platform question re-qualifies it. **But** `sim/launch/warehouse_slam.launch.py` still carries the lifecycle emit-before-register race (TODO, sim carried): the run that produced the map cannot currently be repeated, and if the recorded showcase is to *show* SLAM building the map — the clause is written as observable behaviour — the launch must work. |
| d2 | "the M5 autonomy environment by owner ruling … the map and the Nav2 tuning carry forward; the commissioning arena keeps its M4 role" | **met** (a ruling, recorded) | roadmap M5 row text itself; no work. |
| d3 | "Nav2 drives the forklift autonomously to commanded goals" | **partially met** | Forward: met on the showcase platform — EVIDENCE_NAV2 §11.6 five repeats 5/5 clean on the experimental model equal to the ruled change, §12.1 committed-tree stamp REACHED clean (m5-40 r0). Reverse: **not met** — §12.2 establishes RPP has no reverse reference point on a trailing-axle vehicle (real, un-masked, not a deadband artefact), and every reverse figure including §12's own is now taken at a reverse cap the tree no longer has (§4 below). Plural "goals": the evidence is one route plus the B/B′/C/D case set; the refusal case (D) works. Whether (d) requires a reverse-commanding goal in the showcase is unruled; if the showcase goals are forward, d3 closes on a stamped re-run set at the current tree. |
| d4 | "with AT-02, AT-03 and AT-04 passing" | **not yet attempted, and not closeable as written** | SRS.md §3 (AT-02 line 93, AT-03 line 105, AT-04 line 117). No report in the repository has ever run any of the three; no brief exists for them. Full analysis in §2 — each has at least one observation no current or planned design can produce. |
| d5 | "and the inhibit demonstrably acting below the navigation stack" | **not met — never demonstrated on the real chain** | The enforcement point exists and is proven below the smoother against a **topic double** (EVIDENCE_ENVELOPE, m5-11). But no run has ever carried a PLC-formed envelope across the real bridge to the gate: `bridge/config/bridge.yaml` is cell-only, no committed configuration maps the forklift group to the live CPU (m5-41 report, verified against the live tag list), and m5-23 Part B's "supervision has never crossed the boundary" is still true. The F-latched stop has likewise never reached the vehicle. |

**The narration obligation** (M5 row: "permissive and checked, not compelled
… the narration says so where the autonomy is shown"). The *doctrine* exists
(ADR 0014 D5). The *material* does not: the sentence describes the PLC forming
an envelope the vehicle's own gate enforces, and that composition has never
run — both halves are proven in isolation only. The narration cannot yet be
spoken truthfully over any recorded run; it becomes truthful at §5 item 6, the
first end-to-end run.

## 2. AT-02, AT-03, AT-04 — what each demands, what exists, what is missing

All three are "(Gazebo, M5)" tests. None requires a watch table; the
consumer's-view instrument (`bridge/standin_writer/testing/observe_consumer.ps1`)
and the OPC UA mirror witness are established by m5-41, so **running** the ATs
is agent work with the PLCSIM instance up. **Changing the F-program** (which
two of the three turn out to require) is owner work at the tool, against a plc
spec delta first. If any AT sub-case must run under activated safety mode with
an F-program change, that TIA session is the owner's and the plan says so
below.

### AT-02 (SF-02, vehicle e-stop)

Demands: while driving a Nav2 path, assert the simulated e-stop → the
simulated safety node cuts the drive command **below Nav2** (bypassed, not
asked), standstill within braking distance, **`safetyState.eStop` = `MANUAL`
in the next `state` message**, Nav2 commands during the stop have no effect,
release alone restores nothing, reset + new goal does.

What exists: the envelope gate below the smoother (the "below Nav2" cut
point); the writer's operator E-stop key driving `EStopCircuitClosed`
(m5-41); the F `EStopDemand` latch and monitored reset, observed working.

What is missing, and why nothing planned closes it:

1. **The channel it asserts does not exist.** The F-program's one e-stop
   channel is **SF-01, the cell e-stop** (`plc/forklift-safety/SPEC.md` §1:
   "`EStopDemand` — the logic of SF-01"). SRS B4 and SF-01's own safe-state
   row state that the cell e-stop **has no path to any vehicle** — so driving
   AT-02 from the existing channel would demonstrate the exact coupling B4
   forbids. SF-02 needs its own stimulus channel and demand (a stand-in
   member, an F-network, a writer key), which is a plc spec delta plus an
   owner TIA session — **designed nowhere, briefed nowhere**.
2. **`safetyState.eStop = MANUAL` has no producer.** No VDA 5050 client
   exists at M5 (grep of `agv/` finds none; the client is M6 work by
   ADR 0010's own collapse). The SRS mapping table nevertheless lands SF-02's
   VDA mirror at M5. Either a minimal state publisher is built at M5, or the
   SRS observable is restated for the M5 twin by a safety-spec brief — done
   overtly, because the criterion says "AT-02 passing" and quietly weakening
   the AT is redefining the criterion.
3. The rest of AT-02 (stop below Nav2, commands-have-no-effect, reset + new
   goal) maps onto the envelope chain and is reachable — **after** the bridge
   repoint and the end-to-end run exist (§5 items 3, 6).

### AT-03 (SF-03, protective field stop)

Demands: (a) obstacle into the protective field of the **moving** vehicle →
deceleration next control cycle, standstill before the dimensioned boundary,
`fieldViolation` = true; (b) remove → **inhibit auto-releases after 2 s
clear**, motion resumes only on a fresh Nav2 command; (c) **bumper** trip
latches and survives obstacle removal until reset; (d) two-scanner + measured
R3 residual observation with the reduced monitoring case and its ≤ 0.3 m/s
SLS limit in force (cross-check AT-10), negative observation observed in the
run.

What exists: the field evaluation phase 1 (static protective contour, both
devices, OSSD-equivalent, Gazebo-driven, m5-12b) feeding the writer's zone
channel; the F `ZoneStopDemand` latch.

What is missing:

1. **(b) contradicts the built semantics.** SRS SF-03's inhibit release is
   **automatic** after 2 s clear — the SRS's single documented exception to
   no-auto-resume. The channel the intrusion actually drives is
   `ZoneStopDemand`, which `plc/forklift-safety/SPEC.md` §1 names **the SF-07
   pattern** — a latch cleared **only by the monitored reset** (m5-41:
   "closing both circuits clears no demand"). As wired, AT-03 (b) **fails by
   design**: the vehicle stays stopped until an operator resets, which is
   SF-07's behaviour, not SF-03's. Someone must rule which function holds the
   vehicle protective stop at M5 and where the 2 s auto-release lives
   (vehicle-side consumer, a separate F path, or an SRS restatement) —
   safety-spec ruling first, then plc/agv consequence. **Nothing currently
   planned makes this decision.**
2. **(c) there is no bumper.** `model.sdf` carries none (verified by search);
   FIELD-EVALUATION.md never mentions one; TWIN-DEMO-MAP NC-1 recorded its
   absence at M4 and M5 added scanners, not a bumper. A contact sensor in the
   model plus a channel, or an explicit safety-spec scope ruling, is required.
3. **(d) needs phase 3, which is unbuilt**, plus things phase 3 explicitly
   excludes: monitoring-case selection from direction/lift/load state
   (FIELD-EVALUATION §12 phase 3 — not started), and the SLS limit being **in
   force** (SF-10 enforcement — implemented nowhere; phase 3 says "does NOT
   enforce ceilings"). Also (d) cites R3's measured bearings from
   EVIDENCE_SENSOR_COVERAGE.md — whose producing tool no longer runs (§3).
4. `fieldViolation` = true has the same no-VDA-producer problem as AT-02.
5. (a)'s standstill-before-boundary is measurable only on the full chain
   (field → writer → F → mirror → §14 → bridge → gate), which has never run.

### AT-04 (SF-04, warning field speed reduction)

Demands: obstacle in warning field only → commanded **and actual** speed
≤ 0.3 m/s within one field-report cycle, no stop; clear → nominal resumes
after 2 s; then **disable the speed-reduction handler**, drive at full speed
into the same scenario → SF-03 still stops inside the protective field.

What is missing: **everything above the sensors.** The warning field is
FIELD-EVALUATION phase 2 — not built. The creep **enforcer** (the consumer of
the warning verdict) was deliberately left an open owner/interface question by
phase 2's "does NOT" list — undecided, so there is nothing to disable in the
backup half. The backup observation additionally requires AT-03 (a) working
end to end. "Visible in `state.velocity`" is again a VDA reference; the M5
observable needs restating (the vehicle's odometry topic serves).

### The AT-10/AT-11 discrepancy, named rather than absorbed

Criterion (d) names AT-02/03/04 **only**. The SRS mapping table (§6) and
TWIN-DEMO-MAP NC-6 both land **AT-10 and AT-11 at M5** as well, and AT-03 (d)
cross-checks AT-10 (a). Per the m3-37 rule (LESSONS 70), the gate is ruled
against the criterion text and a stricter side-document does not keep it open
— but the documents should not be left disagreeing: a safety-spec/arch-docs
ruling either moves SF-10/11 verification to M6 in the SRS mapping or the
owner accepts them as M5 work beyond the criterion. AT-10's own text (B1/B3:
unchanged with the bridge stopped and the session down) demands an **onboard**
SLS trip that nothing designed provides; if it stays at M5 it is the largest
unstarted item in the gate.

## 3. The defect register — each verified against its artifact, classified

Classes: **(D)** criterion-(d) blocker · **(E)** evidence-integrity ·
**(H)** housekeeping.

Brief §2's list, checked:

| Defect | Accurate? | Class |
|---|---|---|
| Reverse defect real and un-masked; RPP has no reverse reference point; even straight-route plans open with a 0.092 m Reeds-Shepp reverse | **Yes** (EVIDENCE_NAV2 §12.2: old plant reproduces ABORTED 104 at 2.745 m onset; new plant diverges further, −51.5°, recovers by replanning at 12.470 m travel for a 6.106 m plan). The 0.092 m opening reverse is real (TODO measured-numbers) but is executed at well under either cap, so it does not spread the defect into forward routes materially | **(D) only if a showcase goal commands reverse; (E) otherwise, and an M6 blocker either way** |
| Reverse cap −0.60 → −0.55 (m5-12b) invalidates every reverse-travel figure in EVIDENCE_NAV2.md | **Yes, and it reaches further than anyone has written down** — see §4 | **(E)** |
| `sensor_coverage.py` no longer runs | **Yes** — `load_model` line 286 calls `sensor.find('lidar/scan/horizontal')` on every `<sensor>`; the IMU (added m5-07c, model.sdf line 567) has no `<lidar>`, so the dereference dies before output. EVIDENCE_SENSOR_COVERAGE.md is unreproducible, **and AT-03 (d) cites its R3 bearings** | **(E), escalating to (D)-adjacent when AT-03 (d) is scheduled** |
| FIELD-EVALUATION §6 rear clip band rounds the wrong way | **Yes** — line 244 still reads −131.5°…−72.3°; the band in force (config.yaml lines 992–993) is the corrected −133.0…−71.8. The design doc, which m5-12b was told is the authority, still specifies a field the vehicle sits inside forever | **(E)** — the running code is right; the authority document is wrong |
| `nav2_run.py` startup race and `cmd_goal` settle-loop one-sample-early exit, recorded not fixed | **Yes** (EVIDENCE_NAV2 §12.2; the driver carries a 25 s workaround, the design decision — minimum TF age — is m5-40 OQ2) | **(H)** — an instrument defect with a working workaround |
| EVIDENCE_LOCALIZATION cases (a)/(b), EVIDENCE_VEHICLE_IMAGE proof 3 not re-measured | **Yes** (m5-40 §6 items 3–4; inventory items 6–7, rated low, qualification acceptable meanwhile) | **(E), low** |
| sim/ carried: `warehouse_slam.launch.py` lifecycle race; no `seed` in `warehouse_bringup`; `forklift_bringup` lacks the current stack; arena traction contradiction (ARENA §5's 0.480 m/s vs m5-38's 0.005 m/s, twice) | **Yes, all four confirmed** (launch files read; contradiction is PLANT-CHANGE-INVENTORY §2.1's one "unclear") | SLAM race: **(D)** for the recorded showcase's SLAM clause. Seed: **(E)** (confound removal). forklift_bringup: **(H)** — arena keeps its M4 role. Arena traction: **(E)**, sim-owned |
| Goal-refusal error code carries no reason (208 driven / 207 bench) | **Yes** (TODO measured-numbers; §12.5) | **(H)** at M5; a fleet concern at M6 |

Found beyond the brief's list:

9. **(D)** **The supervision chain has never crossed the boundary.** No
   committed bridge configuration maps the forklift/envelope groups to the
   live CPU (m5-41, verified against the live tag list; `bridge.yaml` is
   cell-only by its own statement). Everything in d5, AT-02 and AT-03 (a)
   waits on this one item — it unblocks the most of anything on the list.
10. **(D)** **SF-02's stimulus channel, SF-03's auto-release locus, the
    bumper, and the M5 restatement of the three VDA observables are all
    undesigned** (§2). These are decisions, not builds — cheap to make, and
    nothing can be scheduled until they are made.
11. **(E)** `nav2.yaml`'s steer-reserve comment (line ~209, "30.06 deg of
    steer authority in reserve") is falsified by m5-40's re-derivation to
    **25.8°** on the new plant (m5-40 §2 row 4). Untracked anywhere — m5-40
    left the file byte-identical deliberately and no TODO line carries it.
12. **(E)** FIELD-EVALUATION §5's depth argument is paired with "phase 1's
    speed regime capped at 0.55 m/s in nav2.yaml" — which means **every
    committed reverse run ever taken exceeded the speed regime the protective
    field is dimensioned for** (all ran at −0.60). No committed reverse run
    exists at the cap the field design requires.
13. **(H)** TWIN-DEMO-MAP NC-6 states the M5 criterion requires AT-10/AT-11;
    the roadmap row does not (§2's discrepancy — one safety-spec/arch-docs
    ruling).

## 4. The question nobody has asked — what is now unqualified

The plant changed 2026-08-05 23:55 (`3f186a5`, p_gain 6000 → 60000) and the
reverse cap changed 2026-08-06 00:44 (`4cc700e`, min_velocity −0.60 → −0.55).
PLANT-CHANGE-INVENTORY.md was written before either edit and knows only the
first. m5-40 executed the inventory **at the old cap**. Forty-nine minutes
later the cap moved. Consequences, by file and figure:

1. **EVIDENCE_NAV2.md §12 — the re-measurement's own outputs are already
   unqualified.** Every §12 reverse figure was taken at −0.60 on a tree that
   now carries −0.55: §12.2's B′ result (SUCCEEDED 57.59 s, 12.470 m of
   travel, divergence onset 5.7 m, worst −51.54°) — the figure m5-40's own
   report nominates as "the number that matters for M6 traffic"; §12.3's
   case B tracking rms **0.0206 m** — the headline of the un-masked reverse
   defect; and §12.2's ruling that section 5.2's bound "stands, on both
   plants" — a bound stated **at 0.60 m/s**, a speed the vehicle can no longer
   command in reverse. TODO's blanket "every reverse-travel figure in
   EVIDENCE_NAV2.md" technically covers §12, but nothing anywhere names §12,
   and a reader of m5-40's report will take §12 as current.
2. **EVIDENCE_NAV2.md §12.1 — the committed-tree stamp no longer stamps the
   committed tree.** Run 0 existed precisely to make the figures rest on the
   file the repository carries; the repository's nav2.yaml changed within the
   hour. Its forward figures (localization max 0.1083 m, cross-track
   +0.0007 m/m) are materially safe — the only reverse in the route is the
   0.092 m opening, which cannot reach 0.55 m/s from rest — but the stamp's
   *claim* is now false, and the current tree has no stamp run at all.
3. **EVIDENCE_NAV2.md §12.6 — the footprint_padding re-derivation's governing
   maximum is an old-cap reverse figure.** The pooled new-plant maximum
   0.2056 m (→ the 0.21 m rule) **is case B′'s figure** — 574 samples of a
   6 m reverse driven at −0.60 with 52 replans. A slower reverse cap changes
   exactly that regime. The derivation's conclusion (keep 0.27) is
   conservative and survives; its stated basis does not.
4. **m5-40's report §2 and TODO's measured-numbers block** quote these same
   §12 values without the cap qualifier; whoever re-runs reverse at −0.55
   must not treat §12 as the comparison baseline without naming the cap as a
   second variable.

The direct answer to "does the vehicle still do what it did": **forward, yes
— measured at the current tree minus one parameter that cannot affect it.
Reverse, unknown: no reverse drive has ever been taken at the cap the tree
now carries, and the freshest reverse evidence in the repository was
invalidated 49 minutes after it was written.**

## 5. The work list — ordered by what unblocks the most

Each item: what — agent/owner — depends on — one observable done-line.

1. **The AT semantics round** — *safety-spec* (with arch-docs for the
   AT-10/11 landing) — depends on nothing — **unblocks every AT**. Rule, in
   one brief: (i) the M5 observables standing in for `safetyState.eStop`,
   `fieldViolation` and `state.velocity` (mirror nodes / vehicle topics), or
   the decision to build a minimal state publisher; (ii) which function holds
   the vehicle protective stop at M5 and where SF-03's 2 s auto-release
   lives, against the built SF-07-pattern latch; (iii) SF-02's stimulus
   channel (own channel, never the SF-01 one — B4); (iv) the bumper: modelled
   or scoped out, explicitly; (v) whether SF-10/11 verification stays at M5
   or moves to M6 in the SRS mapping. *Done when the SRS/TWIN-DEMO-MAP state
   AT-02/03/04 in a form every observation of which names an existing or
   explicitly-commissioned instrument.*
2. **Owner ruling: does any M5 showcase goal command reverse?** — *owner* —
   depends on nothing — decides whether the reverse defect is a (D) blocker
   or an M6 item, and sizes item 8. *Done when the ruling is in TODO/PLAN.*
3. **Bridge forklift-group repoint + envelope slot tables** — *bridge* —
   depends on the live CPU being up (it is) — m5-41's own next_suggested and
   the single highest-leverage build item. *Done when envelope topics carry
   PLC-formed values on the vehicle side and the deferred Group 1 + Group 2
   running-cell capture exists.*
4. **F-program delta for the AT round's consequences** (SF-02 channel; the
   auto-release locus if ruled F-side) — *plc spec (agent), then owner at
   TIA under activated safety mode* — depends on 1. **This is the owner's:
   the plan says so plainly — any F-program change is typed and downloaded
   by the owner, and the writer/observer runs need the PLCSIM instance up.*
   *Done when the new channel's demand and clearance are observed in the
   consumer's view and on the OPC UA mirror, m5-41-style.*
5. **Field evaluation phase 2 (warning field) + the creep-enforcer decision**
   — *agv + interface/owner for the consumer ruling* — depends on 1 (who
   enforces creep). *Done when FIELD-EVALUATION §12 phase 2's done-line is
   observed: warning-only intrusion → creep demanded within one field-report
   cycle, protective field untouched.*
6. **First end-to-end run** — *agent + owner* — depends on 3 (and 4 for the
   e-stop leg): HMI v2a → PLC §14 → bridge → envelope gate → Gazebo vehicle,
   teleop and autonomous, F-latched stop overriding both. This is d5's
   evidence, AT-02's spine, and the material the narration obligation needs.
   *Done when one recorded run shows the gate's stop driven by a PLC-formed
   envelope across the real bridge.*
7. **Run AT-02, AT-03 (a)(b)(d as ruled), AT-04** — *agent* (PLCSIM up;
   owner only if 4 landed changes) — depends on 1, 3, 4, 5, 6, plus
   sensor_coverage.py (item 9) for AT-03 (d)'s R3 citation. *Done when each
   AT's pass line is met with a cited as-run artifact, counts derived from
   the as-run list (LESSONS 60).*
8. **The reverse brief** — *agv* — depends on 2 (scope) and nothing else:
   the RPP reverse-reference-point defect ruling AND the −0.55 re-measure of
   B/B′/C plus a fresh committed-tree stamp, in one brief as TODO already
   says — plus the §12/§12.6 cap-qualifier notes of §4 and the nav2.yaml
   steer-reserve comment (25.8). *Done when EVIDENCE_NAV2 carries a
   current-tree reverse section and §12's figures are qualified in place.*
9. **Fix `sensor_coverage.py` and re-run it** — *agv* — depends on nothing.
   *Done when the tool runs against model.sdf and reproduces
   EVIDENCE_SENSOR_COVERAGE's R3/R8 index sets (or documents the delta).*
10. **FIELD-EVALUATION §6 correction** — *agv* (its authoring agent) —
    depends on nothing. *Done when §6 carries the measured index set 5..65
    and the −133.0…−71.8 band, matching config.yaml.*
11. **`warehouse_slam.launch.py` race fix (+ the `seed` argument beside it)**
    — *sim* — depends on nothing; the fix pattern is proven in
    `agv/forklift/launch/localization.launch.py`. *Done when a SLAM chain
    comes up clean and is captured.*
12. **EVIDENCE_LOCALIZATION (a)/(b) and VEHICLE_IMAGE proof 3 re-runs** —
    *agv* — depends on 8 (same session economics), low priority per the
    inventory. *Done when each file's figures are of the current tree or the
    qualifier is written in place.*
13. **Arena traction reconciliation + ARENA §6 supersession** — *sim* —
    depends on nothing; blocks no criterion. *Done when FORKLIFT_ARENA §5's
    contradiction is resolved by measurement and §6 says which plant it
    describes.*
14. **The recorded safety + autonomy showcase** — *owner* — depends on all
    of 1–11, and on criteria (a)/(b)/(e)'s own residue (outside this brief's
    scope but on the same recording): last, with the ADR 0014 D5 sentence
    narrated over the run item 6 made truthful.

Items 9, 10, 11, 13 can run in parallel with the main line by different
agents, subject to the one-simulator rule (LESSONS 88) — 11 and 13 both run
Gazebo and must serialise with 8.

## 6. The honest size

This is **not one working session**. The main line is four dependent stages —
decisions (1, 2), the boundary crossing (3, 4), the field/AT builds (5, 6, 7),
the reverse/evidence round (8) — plus an owner TIA session if item 4 lands an
F-change, plus the owner's showcase. Realistically: **eight to ten agent
briefs across at least three working sessions, one owner TIA session, and the
owner's recording session**, with the two rulings in items 1–2 costing little
but gating everything AT-shaped. The alternative — closing (d) without them —
would mean quietly reading "AT-02, AT-03 and AT-04 passing" as something
weaker than the SRS says, which CLAUDE.md §10 forbids. The one genuinely cheap
surprise in this review is favourable: running the ATs needs no watch table
and no hand at the tool — m5-41's consumer-view instrument made the F-side
observations agent-executable, so once the chain exists the tests are scripts,
not sessions.
