# SLS-STANDARDS-BASIS — what the standards actually require of SLS, SS1 and their speed measurement

    status:        research finding (m5-45); changes no requirement
    gate:          M5
    checked:       docs/superpowers/specs/2026-08-06-sls-ss1-fplc-design.md §3, §4, §7
    verified:      all sources fetched and read 2026-08-06
    claim rule:    ADR 0011 D5 — this document states no achieved PL, Category,
                   SIL or PFH for anything in this project, and none of its
                   findings may be read as one

## 0. Method, and the honesty rule this document runs on

The normative texts of IEC 61800-5-2, ISO 3691-4 and ISO 13849-1 are paywalled
and were **not read**. Every finding below therefore rests on graded secondary
sources — vendor safety manuals for certified products, a certification body's
whitepaper, published engineering articles — each cited with version and
verification date. **No clause number appears here unless the cited source
itself states it, and it is then attributed to the source, never to the
standard as read.** Where nothing reachable settles a point, the point is
marked **unreached** with a note on what would settle it.

One methodological event is recorded because it validates the brief's premise:
two automated summaries of fetched PDFs returned fabricated "quotes"
(a sin²+cos² sentence and a two-encoders-for-PLe sentence attributed to the
SICK DFS60S datasheet that appear nowhere in it). Every quotation below was
re-verified against the locally extracted text of the source file itself.

## 1. Sources, graded

| ID | Source | Version / date | Grade | Verified |
|---|---|---|---|---|
| S1 | Siemens, *Safety Integrated — SINAMICS G110M, G120, G120C, G120D and SIMATIC ET 200pro FC-2, Function Manual* (A5E34261271B AF), publikacje.siemens-info.com/pdf/668 | Edition 04/2018, FW V4.7 SP10 | **A** — manufacturer's safety function manual for a certified drive family; describes the certified architecture and quotes the standard's SLS definition | 2026-08-06 |
| S2 | TÜV Rheinland, *ISO 3691-4:2020 — A Standard for Automated Guided Vehicles* (whitepaper DE21_I07_FSCS_2100831_en), tuv.com | 2021 (document code DE21) | **A−** — a notified/certification body summarising the standard it assesses against; still a summary, not the text | 2026-08-06 |
| S3 | SICK, *DFS60S Pro product family overview* (safety incremental encoder), sick.com via motionworld.com mirror | 2024-03-01 | **B+** — manufacturer datasheet of a certified safe encoder; authoritative for what that product is, silent on why | 2026-08-06 |
| S4 | HEIDENHAIN, *Technical Information: Safety-Related Position Measuring Systems* (ID 596632-06-A-02) | 11/2019 | **A** — manufacturer's technical information on certified safe-encoder architecture, including the EN 61800-5-2 fault-model consequence (Table D16 as S4 cites it) | 2026-08-06 |
| S5 | Pilz (R. Fenion), *Safe motion standard EN 61800-5-2: more than Safe Torque Off*, machinebuilding.net | 2015-07-08 | **B** — safety-vendor engineering article; good for function definitions, dated | 2026-08-06 |
| S6 | Synapticon, *Safe stop functions: SS1, SS2 and SOS*, Motion Control Academy, synapticon.com | undated, live 2026-08-06 | **B** — drive-vendor educational page; good for SS1-t vs SS1-r mechanics | 2026-08-06 |

**Unreached** (each with what would settle it):

| U | What | Why it matters | What would settle it |
|---|---|---|---|
| U1 | IEC 61800-5-2 normative text (definitions of STO, SS1, SLS; fault model Annex/Table D16) | Findings F1, F3, F4 rest on vendor renderings of it | Purchase or library access to IEC 61800-5-2:2016 |
| U2 | ISO 3691-4:2020 normative text — in particular the full safety-function table S2 places at "Table 1, section 4.11" (27 functions with minimum PLr) and the speed-control section S2's relationship diagram labels "4.3" | The PLr the standard puts on **speed control specifically** could not be read anywhere reachable; S2 shows only the two braking rows (d and b) of that table | Access to ISO 3691-4:2020 or :2023; a vendor application note reproducing the full table would be a usable A−/B substitute |
| U3 | ISO 3691-4:2023 (the current edition, iso.org/standard/83545, catalog page seen 2026-08-06) — what changed from 2020 | S2 covers the 2020 edition; all edition-specific statements here are 2020-edition statements | Access to the 2023 text or a graded change summary (the ANSI and Pilz summaries returned HTTP 403) |
| U4 | ISO 13849-1:2023 normative text (SRP/CS definition; the rule that the parts executing a safety function must meet the PLr) | Finding F5's mechanism is stated from the standard's known structure as reflected in S2's usage ("SRP/CS … in reference to ISO 13849-1"), not from the text | Access to ISO 13849-1:2023 |
| U5 | Whether ISO 3691-4 cites IEC 61800-5-2 or names STO/SS1/SLS at all | Decides whether the truck standard requires the *named* drive functions or only functional outcomes at a PLr | Any reachable page of 3691-4's normative references; unreached in every source tried |

## 2. Findings

### F1 — The function definitions and their normative home

STO, SS1 and SLS are defined in **IEC/EN 61800-5-2** (adjustable-speed drives —
functional safety). Every reached vendor source attributes them there and
nowhere else (S1 p. 39; S3 pp. 2, 5 "supports safety functions conforming to
IEC 61800-5-2"; S5; S6). The recollection in the design spec §7 is **confirmed
at the attribution level**: 61800-5-2 is the home of the function definitions,
ISO 3691-4 is the type-C product standard for driverless trucks (S2 p. 3:
"ISO 3691-4 specifies these requirements as a Type C standard for driverless
industrial trucks").

The definitions, as the sources render them:

- **STO** — power that can produce torque is safely removed; corresponds to a
  category 0 stop per IEC 60204-1; the motor runs down uncontrolled (S5).
- **SS1** — controlled braking, then STO; corresponds to a category 1 stop
  (S5, S6). Two variants matter here (S6, quoted verbatim):
  - **SS1-t** (time-controlled): "After the configurable time t_SS1 has
    elapsed, STO is activated — regardless of whether the motor is already at
    a standstill. No encoder feedback required."
  - **SS1-r** (ramp-monitored): "The deceleration is monitored against a
    configured minimum deceleration rate a_SS1 … Requires encoder feedback."
- **SLS** — S1 (p. 39) quotes the standard: *"The SLS function is defined in
  IEC/EN 61800-5-2: 'The SLS function prevents the motor from exceeding the
  defined speed limit.'"* — a vendor's quotation of the definition, not the
  standard read (U1). How "prevents" is realised is the subject of F5.

### F2 — Whether a driverless truck is required to have them, and where the requirement sits

**The requirement, as far as anything reachable shows, is on functions and
their performance levels, not on the 61800-5-2 function names.** No reached
source shows ISO 3691-4 mandating "SLS" or "SS1" by name (U5). What S2 shows
the standard requiring:

- A table of **27 safety functions with a minimum PLr per ISO 13849-1 each**
  (S2 p. 6, citing "Table 1, in section 4.11"). The two rows S2 reproduces:
  braking system control **PLr d** ("PL function controls the deceleration
  function"), parking braking system control **PLr b**.
- **Personnel detection and braking system SRP/CS at PLr d** (S2 p. 8: "The
  standard clarifies that the SRP/CS of the Detection of Personnel and the
  Braking System have to comply with a level of PLr d"). The decisive change
  from EN 1525 is "generate a signal" → "**stop**": the whole chain from
  detection through braking is assessed as the safety function (S2 p. 8).
- **Speed control is one of the standard's safety-protective measures** (S2
  p. 5 relationship diagram, labelled "Speed Control 4.3"), and the zone table
  couples speed to detection state: with personnel detection **muted**, the
  maximum permitted speed is **0.3 m/s** (S2 p. 7, Table A.1 extract, row 1b:
  "Muted — 0,3 m/s"). This independently corroborates the 0.3 m/s figure the
  SRS carries on SF-04/SF-10 and ADR 0011 F11. The **PLr the standard assigns
  to speed control specifically is unreached** (U2).

So the owner's belief decomposes as: a driverless truck **is** required to
have a speed-limiting/speed-monitored regime and a stopping function, with
required performance levels — but the requirement is expressed as *functions
at a PLr* (ISO 13849 language), and the 61800-5-2 names are the drive-level
building blocks industry uses to implement them, not (in anything reached)
obligations in themselves.

### F3 — What the standards require of the speed measurement SLS depends on

Nothing reached states a *prescription* ("thou shalt use two channels").
What certified practice shows instead is that **the measurement must be part
of the safety-rated chain and the required integrity can be reached by
several architectures**:

- **Encoderless**: the SINAMICS G120 family implements SLS, SSM and SDI with
  **no encoder at all** — actual value acquisition from the motor's electrical
  quantities, with a **crosswise comparison between two processors** inside
  the drive (S1 p. 26: "The safety functions integrated in the drive do not
  use an encoder"; p. 133/135, parameter p9542: "Tolerance for the crosswise
  comparison of the actual position between processor 1 and 2"). Restrictions
  apply (no pulling loads, S1 p. 27) — i.e. the *architecture* is admissible
  where its fault assumptions hold.
- **Single safe encoder, externally evaluated**: the SICK DFS60S Pro is one
  sin/cos encoder certified **SIL 2 / PL d / Category 3** whose safety
  functions (SS1, SS2, SOS, SSM, SLS, SDI, SBC) are realised **in combination
  with an external evaluator** (Flexi Soft FX3-MOC) (S3 pp. 5–6).
- **Single serial encoder with two internal position values**: HEIDENHAIN's
  safe encoders transmit "two mutually independent position values and
  additional error bits produced in the encoder", cross-compared by the
  EnDat master in the safe control; usable as **single-encoder systems at
  SIL 2 / PL d / Category 3**, with SIL 3 / PL e possible only through
  "additional measures in the control" (S4 pp. 1–2). Note the classification
  nuance S4 itself states: per EN 61508 this architecture "is regarded as a
  **single-channel tested system**" — two internal values do not
  automatically make a two-channel Category 3/4 structure; diagnostics and
  cross-comparison in the safe control are what carry it.

So: **a single measurement device is demonstrably acceptable at the PL d
level this project's targets sit at**; two-channel/diverse redundancy and
cross-comparison are the *techniques* by which the required diagnostic
coverage is achieved, not free-standing requirements; and discrepancy
monitoring is, in every reached architecture, a technique the *evaluating
safety control* performs. What the normative text itself demands of the
measurement (fault models, DC, CCF treatment) is **unreached** (U1, U4).

### F4 — What a safe encoder actually is

Two real architectures coexist:

1. **Analog sin/cos, single scanning, external analytic monitoring** — the
   DFS60S Pro shape: one optical scanning system, 1 Vpp sine/cosine output,
   certified SIL2/PLd/Cat 3, safety realised by the external drive-monitor
   module (S3). (The commonly described sin²+cos² vector-length check is
   *not* stated in S3 and is deliberately not asserted here — see §0.)
2. **Serial, two independently generated position values in one housing,
   cross-compared by the safe control** — the HEIDENHAIN shape (S4).

**The design's assumption — one shaft, two reading channels, cross-compared —
matches architecture 2 and the Siemens two-processor cross-comparison, and is
therefore a faithful model of real practice at the PL d tier.** Two caveats
from S4 that the design should carry:

- The single-encoder system is a **single-channel tested system** (S4 p. 2);
  the design must not describe its two channels as if they alone constituted
  a Category 3 dual-channel architecture. (The design claims no category, so
  this is a wording hazard, not a present defect.)
- **The shaft/coupling is the acknowledged hole in real systems too, and the
  standard's mechanism for it is fault exclusion, not a second observation**:
  "Table D16 of the EN 61800-5-2 standard … defines the loss or loosening of
  the mechanical connection between the encoder and motor as a fault that
  requires consideration. Since it cannot be guaranteed that the control will
  detect such errors, **fault exclusion is required** for this in many cases"
  (S4 p. 3, S4 citing the standard's table — U1 applies). The design's
  motion-present corroboration is therefore *more* than real practice
  typically does, and should be labelled as the simulation's stand-in for a
  mechanical fault exclusion, not as the standard's required mechanism.

### F5 — Whether the standard program may limit while the safety layer monitors and trips

**Yes — this split is the certified architecture of the largest drive vendor,
stated in so many words.** S1 p. 39, Table 3-6, is laid out in two columns,
"Safely Limited Speed (SLS)" versus "**Standard inverter functions linked
with SLS**", and the setpoint reduction sits in the **standard** column:

> "The inverter limits the speed setpoint to values below the SLS
> monitoring. If the motor rotates faster than the SLS monitoring value,
> then the inverter brakes the motor along the OFF3 ramp."

while the safety column holds the monitoring and the reaction:

> "The inverter monitors the absolute actual speed against the set SLS
> monitoring. … If the motor speed exceeds the SLS monitoring, the inverter
> responds with a 'safe stop' and brakes the motor as quickly as possible."

and Siemens then states: "⇒ The SLS inverter function is in conformance with
IEC/EN 61800-5-2." S5 says the same in principle: "If the monitoring function
detects that the limit value has been violated, the drive must be shut down
safely." The SICK pattern is structurally identical: the Flexi Soft drive
monitor is an evaluator that monitors and switches off; it limits nothing
(S3 pp. 4, 6).

The consequence, stated carefully: **the safety function is the
measurement + monitoring + fault reaction, and that chain must meet the
function's PLr; the limiting/slowing itself may be performed by standard
(non-safety-rated) logic and earns no safety credit.** The safety case never
leans on the limiter working — which is exactly why the monitor exists.
Normative confirmation is unreached (U1, U4); the finding rests on the
certified practice of two independent vendors plus a safety-vendor article.

### F6 — So, in what sense is the owner right?

The owner ruled that SLS and the controlled stop are managed by the F-PLC and
believed it a standards requirement. On the reached evidence:

- **Right in effect.** The monitoring of speed against the limit, the demand,
  and the stop sequencing are the safety function; ISO 3691-4 (per S2) puts
  required PLr on exactly such functions; whatever executes them must be the
  safety-rated part of the control system. In this project's architecture
  that is the F-layer, by construction.
- **Right by consequence, not by clause.** No reached source shows a
  placement rule ("SLS shall reside in a safety PLC"). The mechanism is ISO
  13849's: the parts of the control system executing a safety function must
  meet its PLr — so "safety functions live in the safety layer" is a
  *consequence of the PLr the risk assessment assigns*, not a free-standing
  commandment. (U4 for the normative wording.)
- **And the F-PLC's role is the one the design already chose: monitor and
  trip, not limit.** Certified practice (F5) puts the slowing in standard
  logic and the verification in the safety chain. Had the ruling been read
  the other way — the F-program forming the speed setpoint — it would have
  contradicted both the certified pattern and ADR 0014.

## 3. The design's five decisions, judged

| # | Decision (design spec §2) | Verdict | Basis |
|---|---|---|---|
| 1 | Compliance = architectural fidelity + simulated safe-measurement structure, PLr targets only | **Survives.** Nothing reached contradicts it, and ADR 0011 D5 already forbids the only claims that could overreach. One wording rule follows from F1/F2: the project may say its functions are *modelled on* IEC 61800-5-2's SLS/SS1 and ISO 3691-4's practice, never "in conformance with" (that phrasing is S1's about a certified product, and D5 item 3 bars it here) | F1, F2; ADR 0011 D5 |
| 2 | Two encoder channels on one shaft, independent noise, cross-compared | **Survives, with two amendments requested.** The shape matches real safe encoders (S4) and Siemens's two-processor cross-comparison (S1). Amend: (a) never describe the pair as a two-channel Category architecture — real single-encoder systems are "single-channel tested systems" (S4); (b) label the motion-present check as the simulation's stand-in for the mechanical fault exclusion real systems apply to the shaft coupling (S4, citing EN 61800-5-2 Table D16) | F3, F4 |
| 3 | STO = joint controller disabled + holding brake | **Survives.** STO is removal of torque-producing power, category 0 per IEC 60204-1 as S5 renders it; controller-disable is the honest simulation analogue, and the brake is the standstill-holding measure the SRS already justifies (SF-03 reaction row). The observable — deaf to commands until safety reset — is a fair test of what STO means | F1 |
| 4 | Loop before the map | **Project decision — no standards content.** The brief anticipated this and it is so: sequencing of build phases is not a subject any reached safety source touches | — |
| 5 | The standard program limits, the F-program monitors and demands | **Survives — and it is the certified pattern, verbatim.** Siemens's own manual places "the inverter limits the speed setpoint" in the *standard functions* column and the monitoring + safe stop in the safety column, and declares the whole conformant with the 61800-5-2 SLS definition. The design's three claimed properties (single owner of the ceiling, no speed value leaving the F-program, the safety layer catching a failed slowdown) are consistent with that pattern | F5 |

No decision is contradicted. The feared outcome — that decision 5 was
backwards — is the opposite of what the evidence shows: monitoring-not-
limiting is how the certified world builds SLS.

## 4. Recommendation — do phases 3 and 4 gate M5's closure?

**Recommendation, not a finding; the ruling is the owner's.**

**Recommended: yes, both gate M5, as the repository currently stands** — for
three reasons, the first of which is not optional under the project's own
rules:

1. **The SRS already commits them to M5.** SF-10 and SF-11 carry "Verified at
   gate: M5" in the traceability table, and AT-10/AT-11 are written as M5
   Gazebo tests. Closing M5 without phases 3 and 4 is not a quiet scoping
   choice; it requires restating two SRS rows (a deferral written into the
   traceability, the way SF-05/SF-06 carry M6) — a requirement change this
   research brief is forbidden to make and has not made.
2. **SF-03's coverage argument leans on SF-10.** The measured residual
   sectors (R3 above all) are "carried by SF-10's speed limit instead" —
   SF-03's own coverage-boundary row. A single vehicle "finished to
   standard" whose reduced-coverage regime has no speed enforcement carries
   a documented protective hole covered by a function that does not exist;
   and the standards evidence puts the 0.3 m/s cap on exactly that
   muted/reduced-detection regime (F2, S2 Table A.1 row 1b).
3. **The owner's own framing.** "M5 is one vehicle's control, completed
   exactly as wanted and compliant with the standards" (design spec §1) reads
   on the reached evidence as: the speed-monitored regime and the two-stage
   stop are what the truck standard's function set is *about* (F2). A vehicle
   without them is the review's deferral position the owner already rejected.

The defensible contrary ruling: land phases 3–4 immediately after phase 2 and
close M5 on the working loop, accepting an SRS restatement brief that
formally defers SF-10/SF-11 (and AT-03's dependent (d)-clause) to a named
landing. If the owner takes that path, the deferral must be written, not
implied — the traceability rows may not be left contradicting the gate.

## 5. What this document requests (changes are requested here, made nowhere)

1. **Design spec amendment (decision 2 wording)** — the two caveats in §3
   row 2: "single-channel tested system" honesty, and the motion-present
   check labelled a fault-exclusion stand-in. The spec lives in
   `docs/superpowers/specs/`, outside safety-spec write scope.
2. **A "modelled on, never conformant" wording rule** for every artefact
   phase 3 produces (§3 row 1) — enforceable by the existing D5 sweep.
3. **If the owner rules M5 closes before phases 3–4**: an SRS restatement
   brief for the SF-10/SF-11 traceability rows and AT-03(d), per §4.
4. **Optional, would upgrade U2**: one purchased/library read of ISO 3691-4
   Table 1 (§4.11 as S2 cites it) to pin the PLr the standard assigns to
   speed control specifically; until then the SRS's PL d design targets for
   SF-10/SF-11 rest on S2's braking-row d and personnel-detection d, which
   are adjacent, not identical, functions.
