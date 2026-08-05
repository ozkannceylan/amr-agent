# HMI v2a — design (m5-27)

**Design document, not code.** The build is m5-28. Every control and indicator
below names the OPC UA node it reads or writes; every node named exists in
`docs/interfaces/opcua-nodes.md` (§10, §11, §12) — **no node is invented here**.
Authority order: `opcua-nodes.md` wins over this design; `plc/forklift/SPEC.md`
§14 owns every arbitration rule, latch, threshold and delay this design
displays. Where this document describes PLC behaviour it is describing the
consumer's contract, never respecifying it.

**Scope.** M5 criterion (e), first half: the M4 HMI **visually reduced**,
gaining **mode selection**, the **process-stop control that ADR 0010 D6(b)
calls the emergency button**, and **safety lamps** showing F-layer state. The
live map is v2b (m5-13, ADR 0011 D4) and is not designed here; §11 says what
v2a must not foreclose.

---

## 1. The one resolved ambiguity, stated first

**An operator who sees a big red button on a screen believes it stops the
machine. On this screen it does not and cannot** (invariant 1: safety never
traverses the network). ADR 0010 D6(b) rules what the control actually is, and
this design implements that ruling exactly:

> The control is a **process-stop request** (`HmiProcessStopRequest`) that the
> PLC standard program latches and acts on, **plus a read-only display of
> F-layer state** (the four `Forklift/Safety/` mirrors). Nothing more.

**Conclusion: D6(b) is satisfiable without weakening invariant 1.** The design
does not paper over the gap between what the button looks like and what it
does; it closes the gap by making the button look like what it does (§4). The
one sentence the interface must make true for the operator:

> *"This button asks the PLC's standard program to stop the machine over the
> network. It is not an emergency stop and there is no emergency stop on this
> screen."*

---

## 2. Node contract — everything v2a reads and writes

### 2.1 Writes — eight nodes, every cycle, nothing else

Per `opcua-nodes.md` §12.1: the every-cycle write set becomes **eight**. §10.8
H1 governs all eight unchanged — every node this client writes is written every
cycle, never on change, so a reverted DB is repaired by the next cycle. H3's
ordering holds: the heartbeat is written **last**.

| # | Node (`Forklift/…`) | Type | Control that produces it | New in v2a |
|---|---|---|---|---|
| 1 | `Hmi/HmiTractionRequest` | Float | traction control (unchanged from v1) | — |
| 2 | `Hmi/HmiSteerRequest` | Float | steer control (unchanged) | — |
| 3 | `Hmi/HmiForkRequest` | Float | fork jog control (unchanged) | — |
| 4 | `Hmi/HmiTeleopRequest` | Bool | teleop enable, press-and-hold (unchanged) | — |
| 5 | `Hmi/HmiResetRequest` | Bool | reset button, press-and-hold (unchanged) | — |
| 6 | `Mode/HmiDriveModeRequest` | UInt16 | **mode selector** (§5) | ✔ |
| 7 | `ProcessStop/HmiProcessStopRequest` | Bool | **process-stop control** (§4) | ✔ |
| 8 | `Link/HmiHeartbeat` | UInt16 | the write cycle itself, written last (H3) | — |

The write helper's allowlist grows by exactly nodes 6 and 7 and refuses
everything else, unchanged in mechanism.

### 2.2 Reads — display only, feeding no logic

All at the existing 5 Hz read poll. **No value read here enters any verdict,
timer or interlock in this process**; every read drives pixels only.

| Group | Nodes | Shown as |
|---|---|---|
| `Forklift/Mode/` | `ForkliftDriveModeActive` | the machine's mode — the **authoritative** answer (§12.3 M1), §5 |
| `Forklift/Vehicle/` | `ForkliftVehicleModeApplied`, `ForkliftVehicleHeartbeat` | vehicle report row, §5.3 |
| `Forklift/Envelope/` | `ForkliftMotionEnable`, `ForkliftSpeedCeiling`, `ForkliftEquipmentPermit` | envelope panel, read-only, §6 |
| `Forklift/ProcessStop/` | `ForkliftProcessStopActive` | the latched stop state beside the control, §4 |
| `Forklift/Status/` | `ForkliftTeleopActive`, `ForkliftObstacleStopActive`, `ForkliftSpeedLimitActive`, `ForkliftResetRequired` | status row (v1, visually reduced) |
| `Forklift/Input/` | all four (§10.5) | diagnostics drawer, collapsed by default (§3) |
| `Forklift/Output/` | all three (§10.6) | diagnostics drawer, collapsed by default |
| `Forklift/Link/` | `HmiLinkOk` | link strip, §8 |
| `Forklift/Safety/` | `EStopDemand`, `ZoneStopDemand`, `SafetyResetRequired`, `SafetyResetFault` | the four safety lamps, §7 |

Checked against §12.2's reader table: every §12 node the HMI touches is listed
there with the HMI as an admitted reader or the single writer. Nothing else on
the server is read or written. In particular v2a does **not** read
`Mode/HmiDriveModeRequest` back from the server as if it were state (§12.3 M2).

---

## 3. Page layout and the visual reduction

One page, one file, offline, no framework — v1's constraints unchanged. The
reduction rule: **v1 shows every node as a labelled number; v2a shows verdicts
as states and hides numbers unless asked.**

```
+--------------------------------------------------------------------------+
| LINK STRIP   session ● | PLC link (HmiLinkOk) ● | data age | mode chip    |
+-----------------------------+--------------------------------------------+
| A  MODE                     | C  STOPS & RESET                           |
|  selector: None|Teleop|Auto |   [ PROCESS STOP ]  (rectangular, §4)      |
|  machine mode (large):      |   process stop latched: ●                  |
|    ForkliftDriveModeActive  |   obstacle stop latched: ●                 |
|  vehicle applying:          |   reset required: ●                        |
|    ForkliftVehicleModeApplied|  [ RESET ] (press-and-hold, unchanged)    |
+-----------------------------+--------------------------------------------+
| B  TELEOP CONTROLS          | D  F-LAYER STATE — READ-ONLY MIRROR        |
|  traction / steer / fork    |   (own banner, own frame, §7)              |
|  [ ENABLE ] press-and-hold  |   e-stop demand      ●                     |
|  de-emphasized when mode    |   zone-stop demand   ●                     |
|  in force is not Teleop     |   safety reset req.  ●                     |
+-----------------------------+   reset device fault ●                     |
| E  ENVELOPE (read-only)     +--------------------------------------------+
|  motion enable ● ceiling m/s| F  DIAGNOSTICS  (collapsed drawer:         |
|  equipment permit ●         |    all §10.5/§10.6 raw values, counters)   |
+-----------------------------+--------------------------------------------+
```

Reduction decisions, each binding on the build:

- **Every Boolean state renders in exactly three ways**: asserted, clear, and
  **unknown** (grey, hatched, value shown as `—`). Unknown is used whenever the
  read poll has failed or the session is down. A stale display never keeps its
  last live look (§12.3 M3, §11.6: *not yet written is not clear*).
- The raw numeric dump of v1 (every input, output and counter) moves into the
  collapsed **diagnostics drawer** F. Nothing is deleted; it is demoted.
- **The machine's mode is the largest text on the page** and it renders
  `ForkliftDriveModeActive` — never the selector's position (M2).
- Zone D carries its own banner — "F-layer state (read-only mirror)" — and is
  visually framed apart from zone C. No lamp, caption or sentence merges a
  C-item with a D-item (§11.4 MR7, §12.7).
- Teleop controls (zone B) grey out when the mode in force is not `Teleop`, but
  **the write stream never stops**: all eight nodes are written every cycle in
  every mode (H1, §12.1). Greying is display, not gating.

---

## 4. The process-stop control — D6(b), concretely

### 4.1 What it does, in one operator sentence

> **"Requests a stop from the PLC's standard program, over the network. The
> PLC latches it; release the button, then press RESET to clear."**

That sentence (or a shorter form of it) is printed under the control,
permanently, not in a tooltip.

### 4.2 What it looks like — and what it must NOT look like

The failure mode is borrowing the visual language of a real emergency stop
(IEC 60204-1 / ISO 13850: red mushroom actuator on a yellow field). Binding
rules for the build:

| Rule | Statement |
|---|---|
| PSU1 | Label: **"PROCESS STOP"**. The words *emergency*, *e-stop*, *not-aus*, *protective* appear nowhere on or near the control — the §10.1/§9.6 naming discipline carried onto the screen. The full browse path already says it three folders deep (`Forklift/ProcessStop/HmiProcessStopRequest`, §12.2) and the screen says the same thing |
| PSU2 | Shape: **rectangular**, same corner radius as every other button. Never round, never a mushroom icon, never a hand icon |
| PSU3 | Colour: **amber/orange family**, and specifically **never red-on-yellow** in any combination. Red is reserved on this page for the F-layer demand lamps (§7), which display the only thing in this cell that carries the word e-stop |
| PSU4 | Placement: inside zone C among the other stop/reset states — never isolated in a corner or oversized to mimic a panel device |
| PSU5 | Two visible states: **ENGAGED** (control depressed-looking, caption "stop requested — release, then RESET") and **RELEASED**. It is a two-state standing control, not a momentary button: pressing engages, pressing again releases. The release is deliberately a separate act because it is the live-world term the PLC's reset tests (§12.7 PS3) |
| PSU6 | The caption block beside it states the honest limitation, once, in small permanent text: *"Software stop via PLC over the network — unavailable if the link is down. This plant is simulated; on real equipment the emergency stop is the hardwired device at the machine, never a screen."* That is the answer to "what does the operator reach for when they need the real thing": on this simulated plant, the F-layer chain exists behind the stand-in and no screen reaches it; on real equipment, the hardwired device. The showcase narration says the same words (roadmap M5 row, ADR 0014 D5) |

### 4.3 Armed / not armed — a button whose effect cannot arrive must not look armed

The control renders **UNAVAILABLE** — greyed, hatched, caption "link down —
request cannot reach the PLC" — whenever either of these is true:

- the backend's OPC UA session is down or its last write cycle failed
  (backend-known, its own channel);
- `HmiLinkOk` reads `FALSE` or is stale on the read poll (the PLC saying it no
  longer attributes requests to an operator, §10.9).

The unavailable caption adds the invariant-2 sentence: *"The PLC's own
watchdog has already stopped the machine"* — link loss latches on the PLC side
(§10.8 P5) and produces the very stop this button would have requested
(§12.7's polarity note). The screen never claims the button is the thing that
would save the situation, because the architecture already did.

### 4.4 Values, boot, and the deadman — the design decisions

| # | Decision |
|---|---|
| PS-A | **The backend boots the control ENGAGED.** At every backend start, its process-stop request value initialises `TRUE`, matching the server's §12.8 boot value. A freshly connected HMI must not flip a non-permissive server value the operator has not touched: the first `FALSE` ever written is an operator's release on the page. This is what makes the cold-start release (§9 step 3) an explicit, visible operator act |
| PS-B | **The stop is excluded from the H6 deadman rest set.** H6 returns the five §10.4 requests to rest when the page goes stale; `HmiProcessStopRequest` instead **holds its last operator-set value**. Both directions of the alternative fabricate an operator act: releasing an engaged stop on a page loss invents the permissive act, and engaging it on every one-second browser hiccup would latch a stop no one requested — heavier than H6's stated proportionality (nothing latches on a page loss). A page loss already stops motion through the enable going to rest; a full process loss already stops it through `HmiLinkOk` (P5). Nothing is left uncovered by the hold |
| PS-C | **No re-arming needed on page return.** H6's per-Bool arming exists to stop phantom rising edges of the enable and the reset. The PLC latches the stop on **level** `TRUE` and no dangerous edge exists on this node: a phantom engage is non-permissive, and a phantom release clears nothing by itself — release only matters as PS3's live-world term during a reset edge, and the reset has its own arming (P6). The arming set stays exactly the two §10.4 Bools |
| PS-D | **Page reload adopts backend state.** On load, the page renders the control from `GET /state` (engaged/released as the backend holds it) and changes it only on operator action. A reload must not silently re-engage or release anything |

Beside the control, `ForkliftProcessStopActive` renders as its own indicator —
"process stop latched" — so the operator sees request and latch as two things:
releasing the button visibly does **not** clear the latch (PS1), which is the
no-auto-resume rule made visible on screen.

---

## 5. Mode selection — designed against the adopt window

LESSONS 2026-07-31 is the standing trap: a term comparing a commanded state
with a reported one, written against the steady state, made autonomous mode
permanently unreachable. The HMI's version of that mistake would be a display
(or worse, a timer) that treats the in-flight window as an error. The design
rule that prevents it:

> **The HMI runs no timer, no debounce and no verdict over any mode value.**
> Every rendering below is a pure function of the values read this poll. The
> only party that times a mode disagreement is the PLC
> (`MODE_DISAGREE_DELAY`, SPEC §14.7), and its verdict reaches this screen as
> `ForkliftResetRequired`.

### 5.1 The control

A three-position selector — **None / Teleop / Autonomous** — writing the §12.3
encoding (`0/1/2`) to `Mode/HmiDriveModeRequest` as a **level**, every cycle.
`None` is a real position, not an absence: leaving a mode is the operator
moving the selector to None (or the other mode), and re-entry after a refusal
or a reset requires moving it **away and back** (SPEC §14.4 X5 — a consumed
selection produces no second transition). The selector is a **standing
selection**, not a deadman control: like the process stop (PS-B), it holds its
last operator-set value across a page loss, because returning it to None would
command a mode exit (X3) no operator made. Backend boot value: `0` (None).

### 5.2 What the operator sees, state by state

Three values render together, visually distinct: **selected** (the selector
itself), **machine mode** (`ForkliftDriveModeActive`, the large text), and
**vehicle applying** (`ForkliftVehicleModeApplied`). The page's mode chip is
derived per poll:

| Screen state | Condition (this poll's values only) | Rendering |
|---|---|---|
| **Settled** | selected = machine mode = vehicle applying | mode name, steady |
| **Changing** | selected ≠ machine mode | chip "selection not in force", neutral colour, **never an alarm**. Caption: *"The PLC has not entered the selected mode. If this persists: return the selector to None, resolve the conditions below, and select again."* — the §14.4 X5 sequence stated as instruction, because a refused selection is consumed and will never be entered without a fresh selection |
| **Adopting** | selected = machine mode ≠ vehicle applying | chip "vehicle adopting", neutral colour. This **is** the adopt window; it lasts as long as the vehicle's own adopt-and-report takes, and the HMI puts no clock on it |
| **Fault** | `ForkliftResetRequired` = `TRUE` | the reset-required indicator in zone C is the fault display, whatever the mode values read. The mode chip itself never says "fault" — the PLC's latch does |
| **Unknown** | read poll stale / session down / link down | all three mode fields render unknown (`—`, grey). The machine mode is **never** shown from a stale value and never inferred (§12.3 M3, M5) |

"Conditions below" in the Changing caption is a list of PLC-published values
already on the page, re-rendered compactly beside the selector — `HmiLinkOk`,
`ForkliftResetRequired`, `ForkliftProcessStopActive`, the four safety lamps —
**not** an HMI-computed diagnosis. The PLC does not publish its standstill
term or per-latch causes; the caption therefore ends with *"see machine
state"* rather than pretending completeness (§12 open items; report OQ2).

### 5.3 The vehicle report row

`ForkliftVehicleModeApplied` renders by the same encoding; when it differs
from the machine mode the row shows both values side by side, labelled
*"vehicle report differs"* in a neutral tone — a display of two data, not a
verdict (§12.3 M4: a persisting disagreement is the **PLC's** fault to declare,
and it arrives here as `ForkliftResetRequired`). `ForkliftVehicleHeartbeat`
renders as its **raw counter value** in the diagnostics drawer only. The HMI
derives no "vehicle alive" lamp from it: that verdict (`#vehicleAlive`, SPEC
§14.7) is the PLC's, it is not published as a node, and an HMI-side staleness
window over it would be timing a process value — the exact thing this layer
must not do.

### 5.4 Autonomy entry is the affirmative action

Selecting `Autonomous` **is** the enable for autonomous motion (§12.3, SPEC
§14.4 X2) — there is no separate autonomous enable node, and v2a mints no
second control for it (the request for one shared start request is
`opcua-nodes.md` §12.13 item 5, owner's, untouched here). The selector's
Autonomous position therefore carries a permanent sub-caption: *"selecting
autonomous permits the vehicle to move under its own control"*. The teleop
enable button stays what it was: press-and-hold, meaningful only in Teleop.

---

## 6. The envelope panel — read-only, and captioned as a permission

Zone E displays the three `Forklift/Envelope/` values the PLC publishes.
Binding renderings:

| Node | Rendering | Rule it carries |
|---|---|---|
| `ForkliftMotionEnable` | "autonomous motion permitted / withheld" | the caption uses *permit/withhold*, never *start/stop/run* — a permission is not a command (§12.1) and the panel must not read as a control the operator is missing |
| `ForkliftSpeedCeiling` | value in m/s; `0.0` renders as "no motion permitted (0.00 m/s)" — visually distinct from **unknown**, which renders `—` | E2: a ceiling, not a setpoint; the label is "speed ceiling", never "speed" |
| `ForkliftEquipmentPermit` | "equipment ready / not stated" | Z-rules: the word *zone* appears nowhere in this panel |

The whole panel is display-only and is titled "Autonomy envelope (published by
PLC)". Nothing in it is clickable.

---

## 7. Safety lamps — four, read-only, honest about absence

The display half of ADR 0010 D6(b). Each lamp reads one `Forklift/Safety/`
mirror (§11.2); the group carries its own banner and frame (zone D), and the
banner text is fixed: **"F-layer state — read-only mirror. Nothing on this
screen can write, clear or reset it."**

| Lamp | Node | Asserted (`TRUE`) | Clear (`FALSE`) | Unknown / absent |
|---|---|---|---|---|
| E-stop demand | `EStopDemand` | **red**, filled, "e-stop demand latched" | outline, "clear" | grey hatched, `—` |
| Zone-stop demand | `ZoneStopDemand` | **red**, filled, "zone-stop demand latched" | outline, "clear" | grey hatched, `—` |
| Safety reset required | `SafetyResetRequired` | amber, filled | outline | grey hatched, `—` |
| Reset device fault | `SafetyResetFault` | amber, filled, "reset device fault" | outline | grey hatched, `—` |

Rules, each binding:

- **A lamp with no data shows no state.** Unknown/absent rendering is used
  when the read poll is stale, the session is down, **or the server does not
  carry the group** — an unresolved BrowseName greys the whole zone with the
  caption "F-layer mirrors not present on this server", never substitutes
  `FALSE`, and never fails the connect (§11.6). A lamp that looks healthy with
  no data is worse than no lamp.
- **Red lives here and only here.** The two demand lamps are the only red
  elements on the page (PSU3), because they are the only display of the only
  thing in this cell named e-stop (§11.2's naming ruling).
- The lamps feed no logic, no sound, no popup, no HMI reaction of any kind —
  pixels only ("zero PLC readers" restated one layer up, §11.3).
- `SafetyResetFault` **is** promoted to a lamp — the decision §11.8 item 5
  left to this layer, taken here: a mirror group shown without its "the reset
  device is lying to you" flag would be a curated view, not a mirror.
- No lamp, caption or layout element merges zone D with zone C's process
  stops. The obstacle latch and the process-stop latch are standard-program
  process logic and stay in zone C with the word *process* on them (MR7).

---

## 8. Link and staleness — what the screen shows when the effect cannot arrive

Three health facts, all backend-known or PLC-published, rendered in the
permanent link strip:

| Item | Source | Renders |
|---|---|---|
| Session | backend's own OPC UA session state and last write outcome | up / **down** |
| PLC link verdict | `HmiLinkOk` (read) | "PLC sees operator: yes / no / —" |
| Data age | backend's own read-poll bookkeeping (its own channel, not a process value) | "data as of *n* ms" — turns to a warning past the poll period and flips every state on the page to unknown when the poll is failing |

On any of: session down, write failures, `HmiLinkOk` `FALSE` or unknown —

- the process-stop control renders UNAVAILABLE (§4.3);
- the mode selector renders its position but adds "not reaching the PLC";
- every read-derived state renders unknown (§3);
- the strip states the degraded-mode fact in one sentence: *"Link down. The
  PLC's watchdog stops the machine and latches; a monitored reset will be
  required."* — invariant 2 shown as reassurance, not alarm.

The only timers this process owns remain the three v1 timers, each watching
itself: the 10 Hz write cycle, the 5 Hz floor, and the H6 window over its own
page. v2a adds **no timer** — no staleness window over any plant or PLC value
beyond the read-poll bookkeeping above, no debounce, no dwell, no delay.

---

## 9. Cold start — the operator's sequence, step by step

Why this section exists: every §12 value boots non-permissive and
`HmiProcessStopRequest` boots `TRUE` (§12.8), so the §14 program is inert
until an HMI clears them (m5-23 Part B step 6). The screen at CPU cold start
shows exactly §14.9's signature — mode None, enable withheld, ceiling 0.00,
permit not stated, process stop latched, reset required — and each row below
says what the operator does and what it changes.

**Preconditions outside the HMI**, shown on screen but not performable from
it: the CPU runs the §14 build; the bridge runs (else `BridgeLinkOk` stays
`FALSE` and everything below still refuses); the F-layer demands are cleared
by the F-side's own reset path — **the safety lamps clear by that path and by
nothing on this screen**; the vehicle layer runs, if autonomous mode is
wanted.

| Step | Operator does | Node written | What changes, and what the screen shows |
|---|---|---|---|
| 1 | starts backend, opens page | all eight begin streaming at 10 Hz; heartbeat advances | Backend boots stop ENGAGED, selector None (PS-A, §5.1) — the stream repeats the server's non-permissive boot values rather than clearing them. Once the PLC sees the heartbeat change, `HmiLinkOk` goes `TRUE`: link strip goes green, process-stop control arms |
| 2 | waits for the strip: session up, PLC link up, bridge link visible via plant data in the drawer | — | Everything still non-permissive: `ForkliftProcessStopActive` `TRUE`, `ForkliftResetRequired` `TRUE`. Nothing has been cleared by connecting — connection clears nothing |
| 3 | **releases the process stop** (press the engaged control) | `HmiProcessStopRequest` → `FALSE` | The request clears; **the latch visibly does not** (PS1): "process stop latched" stays on, reset required stays on. The screen has just demonstrated request ≠ latch |
| 4 | **presses and holds RESET** | `HmiResetRequest` `TRUE` (rising edge, armed per P6 — armed because the backend has been writing it `FALSE` under a live link since step 1) | If every live-world term holds — stop released (step 3), both links up, plausible inputs, no obstacle, F-demands clear — the PLC clears all seven latches: reset-required and process-stop-latched indicators go off. **Nothing moves and nothing energizes** (PS4). If any term still stands the reset is refused and the indicators stay on; the conditions list (§5.2) is where the operator looks |
| 5a | **teleop**: selector → Teleop | `HmiDriveModeRequest` → `1` | At standstill with the permissive holding, machine mode goes Teleop (X1); zone B controls un-grey. Then press-and-hold ENABLE (`HmiTeleopRequest` edge) → `ForkliftTeleopActive` `TRUE` → drive. Two acts, deliberately: selecting the mode, then enabling motion |
| 5b | **autonomous**: selector → Autonomous | `HmiDriveModeRequest` → `2` | Requires additionally that the vehicle layer is answering (X2's `#vehicleAlive`). Machine mode goes Autonomous; **this selection is the affirmative enable** (§5.4); envelope panel shows motion permitted and a non-zero ceiling. The vehicle moves when its own stack commands — the envelope permits, it never causes (§12.1) |

If a selection in step 5 is refused (machine still moving, a latch standing,
vehicle not answering): the chip shows "selection not in force" and the
operator's sequence is the documented one — selector back to None, resolve,
select again (X5; §5.2). After any later latch, the sequence is §12.3's:
*leave the mode, press reset, select the mode again.*

Backend restart mid-session repeats from step 1 (stop boots ENGAGED again,
selector boots None); the PLC side re-arms its reset edge per link session
(P6) and nothing resumes by itself.

---

## 10. The development double — buildable before the CPU has the nodes

The running CPU serves the six Forklift DBs and **no §12 node** (m5-23 Part B);
the §12 set arrives in the owner's TIA session. v2a is therefore developed and
evidenced against a double that serves §12, double-first, exactly as v1 was
built against `plc/forklift/double/` and `tools/safety_mirror_double.py`.

**What the double must serve** (the requirement; where it lives is split
below):

1. The **§10 set the logic double already serves** (18 nodes + the two
   `DemoCell/Link/` tags), unchanged — v2a keeps every v1 behaviour.
2. The **nine §12 nodes** under `Forklift/Mode|Envelope|Vehicle|ProcessStop/`,
   with §12.2's per-tag access rights (the three `Envelope/` nodes and every
   PLC verdict refusing client writes — the refusal is part of what the build's
   checks must demonstrate) and §12.8's start values, the two `TRUE`s included.
3. The **§14 behaviour the screen displays**: the mode arbiter X1–X6 (so the
   adopt window, a refused entry and the away-and-back re-selection can be
   exercised), the process-stop latch and its reset coupling PS1–PS6, and the
   envelope forming/withdrawing with mode and latches. Without this the
   Changing/Adopting states of §5.2 and steps 3–5 of §9 cannot be rehearsed.
4. The **four §11 mirrors** at their §11.6 start values, and a way to run
   without them, so both lamp renderings — live and absent-group — are
   demonstrable (today only `tools/safety_mirror_double.py` serves these).

**Where** — following the project's existing double pattern rather than
inventing one:

- Items 1–3 belong in **`plc/forklift/double/`**: it is the transliteration of
  `SPEC.md` and §14 is a numbered part of that spec. Extending it is the plc
  agent's work and is a **request in the m5-27 report**, not taken here —
  and it is the same executable-double step that caught the 2026-07-31
  arbitration defect, so it pays for itself before the owner types §14 into
  TIA.
- Until that lands, the build may proceed against an **hmi-owned scenario
  double** in `hmi/tools/` on the `safety_mirror_double.py` precedent: serves
  the §12 (and optionally §11) nodes at their boot values and **replays
  scripted sequences** derived from §14.4's tables — cold-start clearing, a
  refused entry, the adopt window, a vehicle disagreement. Scripted, not
  transliterated, deliberately: this layer must not carry a second
  implementation of §14's logic, and a scenario player computes no verdict.
  Divergence resolves toward SPEC + TIA, never toward either double.
- New config files follow the existing naming (`config-*-double.yaml`), ports
  outside the refused set (4840, 4842–4846, 4850, 4860 are taken).

Every recorded number states which server produced it, and nothing rehearsed
against a double closes any criterion (§12.11's design-value rule).

---

## 11. What v2a does NOT do, and what it must not foreclose

**Does not do** — each a boundary, not a deferral:

| Not in v2a | Why |
|---|---|
| The live map, obstacles, pose — anything from the monitoring plane | v2b (m5-13, ADR 0011 D4). The monitoring plane has no write endpoint and never touches the PLC |
| Command or display of navigation goals | how an M5 goal is commanded is an open owner decision (`opcua-nodes.md` §12.13 item 4) and must not be pre-empted by a screen control |
| Any write beyond the eight nodes of §2.1 | the write helper refuses it; per-client scoping remains policy (§12.2's note), honoured here by the allowlist |
| Any write, clear, reset, mute or acknowledge toward the F-layer | invariant 1; the lamps are pixels |
| Any velocity, trajectory or per-sample value across any seam | ADR 0014 D1; the HMI's Reals are requests the PLC scales and owns |
| Any HMI-computed verdict, staleness window over a process value, debounce or fault delay | the PLC owns every verdict this page shows; the HMI's three timers watch only itself (§8) |
| A second stop control, a mode override, or an autonomous-only enable | one datum, one owner (§12.12); the enable/start conflation stays as ruled until §12.13 item 5 is decided |
| Sounds, popups, confirmations on stop or reset | a confirmation dialog on a stop request delays the request; the controls act on press |

**Must not foreclose (v2b):** the layout reserves no fixed pixel budget, but
zones A–F occupy one column-pair such that a map pane can join as a third
column without moving any control the operator has learned; the read poll and
`GET /state` schema stay additive (new keys, never renamed ones); and nothing
in v2a assumes it is the only page or the only data source, so the
monitoring-plane view can arrive beside it without touching the OPC UA client.

---

## 12. Requests and open questions (carried in the m5-27 report)

- **Request (plc agent):** extend `plc/forklift/double/` with the §14 delta
  and the §12 address space (§10 item 1–3 above).
- **Request (interface agent, already §12.13 items 1–2):** none new — v2a
  needs no node §12 lacks. Checked name by name in §2.
- **Owner open question OQ1:** whether a per-cause latch display is wanted.
  Today the operator sees `ForkliftResetRequired` without which of the seven
  latches stands (only the obstacle and process-stop latches have their own
  nodes). Exposing the rest touches §10.11's refusal of latch internals and
  moves node counts — owner's call, not requested here.
- **Owner open question OQ2:** whether a published vehicle-liveness verdict is
  ever wanted for display. v2a shows the raw counter only (§5.3) and works
  without it.
