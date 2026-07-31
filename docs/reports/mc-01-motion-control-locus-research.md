# Report mc-01 — where motion control belongs: research against industrial practice

```
brief:               docs/briefs/mc-01-motion-control-locus-research.md
status:              done
files_changed:       [docs/reports/mc-01-motion-control-locus-research.md]
invariants_touched:  none. The recommendation CONFIRMS the recorded state
                     (ADR 0011 D3 as refined by ADR 0012 D1) on industrial
                     evidence; no ADR needs superseding. §L states exactly
                     which decisions Architecture B would have required
                     superseding, so the cost of the road not taken is on
                     record.
open_questions:      three, in §M — the onboard-controller naming for the
                     public narrative, the envelope-latency measurement
                     brief, and whether the owner wants this locus ruling
                     pinned in an ADR of its own
next_suggested:      read §J (the flow) to the owner and confirm the shared
                     reading before m5-11 and m5-16 are briefed
```

Verification dates: all external sources checked **2026-07-31** unless stated.
Two verification grades, per the mv-01 convention:

- **[fetched]** — the page was retrieved and the statement quoted from it.
- **[snippet]** — the statement comes from a search-result excerpt of the named
  page, not re-read in full context.

Facts already pinned in ADR 0011's evidence table (F8–F11) are reused by that
reference and not re-verified here. Every latency number in §C is arithmetic
from stated inputs, not a product claim.

---

## Recommendation, first

**Architecture A, confirmed and sharpened.** The vehicle's own computer closes
the path-following loop onboard and writes the actuator commands; the PLC
publishes the low-rate envelope (enable, ceiling, station permit) and owns the
fixed equipment; the F-layer is the vehicle's onboard safety controller whose
SLS/STO authority is independent of who forms the setpoints. This is what
ADR 0011 D3 and ADR 0012 D1 already record — and the research finds it is also
what every named industrial AGV/AMR stack does, once one looks at **where the
box that closes the loop physically sits and what kind of link it commands the
drives over**. Architecture B's reading is not wrong about real forklifts; it
is wrong about which box in *this* project corresponds to the box that real
forklifts use. §F carries the full defence.

The one-line seam law that the whole industrial record supports:

> **Per-sample motion crosses only deterministic onboard links. Networks carry
> orders, permissions and state — never the loop.**

---

## A. How real AGV and AMR systems actually divide it (question 1)

| System | The box that closes the trajectory loop | Where it sits | What it commands, over what | What crosses the network | Grade |
|---|---|---|---|---|---|
| **Kollmorgen NDC8** (CVC600/CVC700 vehicle controller) | The CVC. "The CVC700 software is the heart of the AGV, with software functions that supervise everything from **vehicle navigation** to communication with the **AGV system controller** and the **interfacing sensors and actuators**." | **Onboard**, one per vehicle | The vehicle's drives and steering, over local I/O and CAN (CVC600: "support for WLAN, LAN, CAN, RS-232/422/485") | Orders and traffic coordination, CVC ↔ stationary system controller over WLAN | [snippet], kollmorgen.com CVC700 / oemoffhighway.com CVC600 |
| **BlueBotics ANT lite+** | The ANT unit: it "calculates the vehicle's position (localization), **controls its motion**, and can interface directly with the vehicle's safety laser scanners"; "ANT lite+ **provides commands directly to a vehicle's motor controller**. However, it can also communicate through a PLC (for example, to interface with specific devices)." | **Onboard** | The motor controllers, directly (or via the vehicle's own onboard PLC for auxiliary devices) | Missions: "the transfer of **mission data** from computer to vehicle happens **just once** (instead of commands being sent continuously from server to vehicle)" | **[fetched]**, bluebotics.com ANT lite+ page |
| **Siemens SIMOVE** (Siemens' own AGV kit) | A "common hardware platform (**PLC and PC with Linux**)" carried on the vehicle; SIMOVE ANS+ is the laser/SLAM navigation on that platform; integrator builds name the **S7-1500 (Open Controller) as the vehicle controller** with an IPC beside it | **Onboard**, one platform per vehicle | SINAMICS/MICRO-DRIVE class drives over PROFINET/PROFIdrive on the vehicle | SIMOVE Master Control / Fleetmanager coordinates the fleet; "SIMOVE Safe Velocity" is "a certified failsafe speed software library … providing the fail-safe velocity (SIL/PL)" | [fetched] siemens.com/simove for the platform and Safe Velocity quotes; [snippet] robotics247.com for the S7-1500-as-vehicle-controller naming |
| **Beckhoff + Navitec** (NAViTROL on TwinCAT/BSD) | One onboard Beckhoff IPC: "one controller can easily handle complex machine **safety** in addition to **PLC and motion control**, and now additionally the **navigation**" — Navitrol runs in a Linux VM under the TwinCAT/BSD hypervisor next to the TwinCAT runtime | **Onboard**, one per vehicle | Drives over **EtherCAT**; safety over TwinSAFE/FSoE incl. "safe position and safe velocity" | Fleet/order traffic to the site network | **[fetched]**, blog.beckhoffus.com Navitec article |
| **SEW MAXOLUTION mobile systems** | MOVI-C onboard automation (MOVIKIT modules for kinematics and localization) | **Onboard** | SEW drive electronics on the vehicle bus | "interoperable **VDA 5050** interface for standardized communication between fleet management and heterogeneous vehicle fleets" | [snippet], seweurodrive.com / sewmaxolution.com |
| **ROS 2 / Nav2 AMRs** (the pattern this project's vehicle layer instantiates) | The Nav2 controller server, default **20 Hz**, computing velocity commands against the local costmap and live pose; the velocity smoother can interpolate "at a higher frequency than Nav2's local trajectory planners can provide … if a local trajectory planner is running at 20hz, the velocity smoother can run at 100hz" | **Onboard** | A base/motor controller consuming `cmd_vel`; the drive closes its own wheel loop | Goals in; fleet adapters (VDA 5050) above | **[fetched]**, docs.nav2.org controller-server and velocity-smoother pages |

Two readings fall straight out of this table.

**First: navigation and vehicle control co-reside on one onboard controller in
every named product.** Kollmorgen puts them in the CVC, BlueBotics in the ANT
unit, Siemens on the onboard PLC+IPC pair, Beckhoff on one hypervisored IPC,
SEW in MOVI-C, the ROS world in the onboard computer. **No vendor splits the
path-following loop across a wireless or otherwise non-deterministic network.**
The stationary side — NDC system controller, ANT server, SIMOVE Master
Control/Fleetmanager, any VDA 5050 master — dispatches **orders and missions**
and reads **state**, and BlueBotics states the principle outright: mission data
transfers once, instead of commands being sent continuously from server to
vehicle.

**Second: "motion control in a PLC" is real — as an *onboard* PLC.** SIMOVE and
Beckhoff/Navitec are precisely the pattern the owner's Architecture B
describes: steer-by-wire and motor control flow through a PLC, the navigation
computer gives it work. But in both products that PLC **rides on the vehicle**,
one per vehicle, and commands its drives over a local deterministic fieldbus
(PROFINET/PROFIdrive, EtherCAT). The question for this project is therefore not
"do PLCs do motion control on AGVs" — they do — but "is this project's S7-1500
that PLC?" §F answers that, and the answer is no: this project's S7-1500 is,
by its own specification, the **fixed cell's** PLC — conveyor, door, charger,
station handshake, OPC UA server to the future fleet manager — on the far side
of a non-deterministic link from the vehicle's sensors and actuators, and at M6
it is one box for four vehicles. The box Architecture B is picturing exists in
industry, but in this repository it does not exist as a layer; its motion role
is played, honestly, by the onboard stack `agv/` already carries.

## B. The drive interface — what a PLC genuinely does in such a stack (question 2)

Real vehicles command their wheel and steer drives over **CANopen CiA 402**,
**EtherCAT/CoE (CiA 402 over CoE)** or **PROFIdrive**, and the profile
structure itself settles part of the argument. CiA 402 standardises "the
control word, status word, state machine, and modes of operation" including
**Profile Velocity Mode**; velocity setpoints travel in cyclic RPDOs and actual
values return in TPDOs, and the **drive closes the current/velocity loop
internally** at kilohertz rates [snippet, can-cia.org / kebamerica.com]. STO,
SS1 and SLS are drive-integrated safety functions per IEC 61800-5-2: STO
removes torque-generating energy, SS1 decelerates then applies STO, SLS
prevents the motor exceeding a defined limit and is "normally realised in the
drive and selected by the F-CPU" (ADR 0011 F10, pinned).

So in a real AGV stack, "the PLC does motor control" never means the PLC closes
the fast loop — the drive does that wherever the setpoint comes from. What the
vehicle controller (PLC or otherwise) genuinely does:

- **ramps and kinematic limits** on the setpoint stream it sends;
- **mode words and drive state machine** handling (CiA 402 enable/quick-stop
  sequencing);
- **interlocks and coordination** — lift vs. travel, charging contactor, door
  and station handshakes;
- **safe-state handling** — selecting SLS/SS1/STO through the safety channel
  and honouring the drive's safe state;
- and, in the SIMOVE/Beckhoff shape, **hosting the path follower** that turns
  the navigation solution into the setpoint stream — *because it is onboard
  and the fieldbus under it is deterministic*.

What it does not do, in any named product: receive per-sample motion values
over a radio or best-effort network, or recompute the trajectory the
navigation layer already computed.

The consequence for this project's simulation: the Gazebo joint controllers
(`/forklift/gz/*_cmd` into the physics engine) are the "drives" — they close
the fast loop inside the physics step, which is this project's standing
reading of invariant 9 (`agv/forklift/README.md`). Whatever writes those
topics is playing the drive-commanding vehicle controller. Today that is
`forklift_io` fed by either the bridge (teleop, PLC-formed setpoints) or, at
M5, the onboard Nav2 stack — exactly the two sources §12.9 already arbitrates
by mode.

## C. Rates and latency, with numbers (question 3)

**Rates real systems run.** Nav2's controller server defaults to **20 Hz** with
a smoother interpolating to ~**100 Hz** toward the base [fetched,
docs.nav2.org]; CiA 402 cyclic setpoints on AGV buses typically run 10–100 Hz
with the drive's internal loops in the kHz range [snippet]; this project's own
onboard cadence is 20 Hz (bridge cycle, Nav2 default, OB30 period all 20 ms /
20 Hz — three separate clocks, one number).

**This project's measured link.** M3 measured the bridge→OPC UA→PLC chain at
**~46 ms median one-way** (46.163 median / 47.690 p95, upper-bounded by the
50 ms poll quantisation) and ~145–151 ms for a full presence-to-assertion
chain (`bridge/EVIDENCE_LATENCY.md`, m3-33). The brief's 50–150 ms round-trip
figure is therefore this project's own floor, not a pessimism.

**What a delay does, worked out.** Take v ∈ {0.3, 1.0, 1.5} m/s (warehouse
range; 0.3 m/s is also ISO 3691-4's cap with personnel detection muted —
ADR 0011 F11, pinned), delay Δt ∈ {50, 100, 150} ms, turn radius R = 1.5 m.

*Along-track error of a delayed command (d = v·Δt):*

| | 50 ms | 100 ms | 150 ms |
|---|---|---|---|
| 0.3 m/s | 15 mm | 30 mm | 45 mm |
| 1.0 m/s | 50 mm | 100 mm | 150 mm |
| 1.5 m/s | 75 mm | 150 mm | 225 mm |

*Cross-track error entering a curve Δt late (e ≈ (vΔt)²/2R, R = 1.5 m):*

| | 50 ms | 100 ms | 150 ms |
|---|---|---|---|
| 0.3 m/s | 0.1 mm | 0.3 mm | 0.7 mm |
| 1.5 m/s | 1.9 mm | 7.5 mm | 16.9 mm |

*Loop stability, which is where delay actually bites.* A pure delay Td in a
feedback loop costs phase ωc·Td at crossover ωc. Budgeting a conventional
~30° (0.52 rad) of margin to delay: with Td = 50 ms the steering loop may
cross at ≈1.6 Hz; with Td = 150 ms it must be detuned to ≈**0.55 Hz**. A path
follower at 1.0–1.5 m/s wants roughly 1–2 Hz of lateral bandwidth; at 0.3 m/s
it can live below 0.5 Hz. Worse, the OPC UA path's delay is **variable**
(poll-quantised, GC- and scheduler-jittered across WSL2/Windows), and a
varying delay cannot be compensated the way a constant one can — the practical
result is either detuned, weaving tracking or oscillation.

*Docking.* Industrial docking accuracy is ±10 mm — BlueBotics states ANT
docking precision of "±1 cm time and time again" [snippet, bluebotics.com].
A stop triggered across a link with ±100 ms command-age jitter scatters the
stop position by ±30 mm even at 0.3 m/s creep — three times the industry
figure. Meeting ±10 mm at 0.3 m/s needs command-age jitter under ~33 ms,
which the measured link cannot give and any onboard loop trivially does.

**Verdict, in the brief's three-way terms.** A 50–150 ms round trip in the
command path is:

- a **non-problem** for envelope-level supervision (enable, ceiling, permit):
  §12.4 E1's test — a 2 Hz reader and a 20 Hz reader behave identically apart
  from latency — is exactly the property that makes 150 ms invisible there;
- a **tuning problem** at 0.3 m/s straight-line travel (detune and accept
  centimetres of slop);
- an **engineering problem** — not tunable away — at ≥1 m/s path following and
  at any speed for ±1 cm docking. This is why no vendor builds it that way.

## D. The safety layer's placement — and whether it constrains the motion locus (question 4)

**Where the pieces really terminate.** On real AGVs the safety scanner's OSSD
pair lands on the **vehicle's own onboard safety controller** — a SICK Flexi
Soft, a TwinSAFE group, an onboard F-PLC (SICK's AGV material describes the
scanner switching its OSSDs and the Flexi Soft ensuring "all drives are
stopped immediately and are prevented from starting up again until it is safe
to do so" [snippet, sick.com]). SLS/SS1/STO execute **in the drive**, selected
by the safety controller (IEC 61800-5-2 via ADR 0011 F10, pinned; TwinSAFE
"safe position and safe velocity" over FSoE [fetched, Beckhoff/Navitec];
SIMOVE ships "Safe Velocity" as a certified failsafe speed library [fetched]).
The inhibit mechanism is the drive's own safety function — removing
torque-generating energy (STO) or a monitored ramp into it (SS1) — not a
process command and not a power contactor as first resort. Field-set switching
is keyed to safely measured speed and direction (ADR 0011 F9, pinned), and
warning-field slowdown is a process function while protective-field stop is
the safety function (F9 again).

This **confirms the project's current reading**: ADR 0011 D1's ruling that the
forklift's F-runtime group is the vehicle's onboard safety controller, with
the scanner→F-program→STO chain internal to the vehicle, is the industrial
pattern, and the owner's foundation — scanners on the F-PLC, SLS and STO as
the F-program's most important job in either drive mode — is correct as
stated.

**Does that placement constrain where motion control sits? No — and the reason
is the shape of SLS.** SLS is a *monitoring* function: something measures
speed safely (safe encoder / safely derived channel), the drive or safety
controller compares it against the selected limit, and on violation the
**drive's own stop reaction** fires — regardless of who was writing the
setpoint and of whether that writer is sane, slow, or gone. The safety layer
therefore does not need to form, route or even see the process setpoints; it
needs a safe speed measurement and authority over the drive's safe state, both
of which it has by wiring. Every named vendor exploits exactly this
separation: Navitrol computes trajectories in a Linux VM while TwinSAFE
monitors safe velocity underneath it; ANT computes motion while the scanner
OSSDs cut the drives beneath it; SIMOVE's navigation runs on the IPC while
Safe Velocity monitors on the failsafe side. **The safety layer bounds any
motion controller from below; it anchors none of them in place.** The owner's
foundation is thus fully compatible with Architecture A — the F-layer's
(modelled) SLS remains the enforcement of the speed limit whose *process
reflection* is the envelope's `ForkliftSpeedCeiling`, two data with two owners
exactly as §12.4 E8 already keeps them.

## E. What the vehicle computer sends (question 5 — the heart of the brief)

Four candidate granularities, each with its named practitioners and its
failure behaviour:

**(a) Continuous velocity/steer setpoints, 10–100 Hz.**
*Who:* every Nav2/ROS 2 vehicle (controller → `cmd_vel` → base) [fetched,
docs.nav2.org]; BlueBotics ANT toward the motor controllers ("provides
commands directly to a vehicle's motor controller") [fetched]; Kollmorgen CVC
toward its drives [snippet]; any CiA 402 profile-velocity consumer [snippet].
*Link slow:* commands arrive stale; the follower detunes or weaves (§C); at
150 ms variable delay ≥1 m/s the loop is not shippable.
*Link lost:* the receiver must zero on its own watchdog — Nav2's smoother
sends a zero command after `velocity_timeout` (default 1.0 s) [fetched], and
drive layers carry their own command timeouts.
*State:* the sender holds everything (path, pose, progress); the receiver is
stateless between samples.
*Error correction:* every sample is a fresh correction from fresh pose.
**Industrial verdict: this is the universal interface — but exclusively over
deterministic onboard links.** Nobody streams it over a network.

**(b) Motion segments — "this much right, this much forward" (Architecture
B's interface).**
*Who:* PLCopen motion blocks (MC_MoveRelative) in fixed automation and CNC;
inductive/magnetic line-guided AGVs are loosely analogous (the "segment" is
the physical wire). **No named free-navigating AGV or AMR product ships this
interface between a navigation computer and a setpoint-forming controller** —
the closest real patterns are (a) below the navigation layer and (c) above
it. Marked accordingly: this is an absence claim, falsifiable by a
counter-example, and none surfaced in this research.
*Link slow:* corrections happen only at segment boundaries, so the boundary
rate is the control rate: short segments collapse into option (a) with extra
framing; long segments mean the vehicle executes **open-loop within the
segment** while its pose error accumulates uncorrected.
*Link lost:* the executor completes the current segment blind — predictable,
but it means the machine keeps moving on stale intent; an obstacle appearing
mid-segment needs the abort to cross the link.
*State:* split ownership — sender holds path and pose, executor holds segment
progress — two owners of "where the vehicle is in its motion", which is the
invariant-10 smell in interface form.
*Error correction — the structural defect:* to correct at all, the corrector
needs pose at correction rate. Pose is made onboard (SLAM). Either pose
streams to the PLC per-sample — which recreates option (a)'s network loop in
the opposite direction, with the same §C latency — or correction stays
onboard, at which point the PLC executes increments it cannot check, computed
from data it does not hold, and contributes **only dead time** to the loop.
In teleop the PLC-in-the-middle pattern worked because the loop was closed by
a *human* at human bandwidth, and the PLC added interlocks between operator
and plant. In autonomy the loop is machine-closed at 20 Hz, and the same
insertion point inserts only delay.

**(c) A path/mission to follow.**
*Who:* VDA 5050 itself — the order is a graph of nodes and edges with an
optional **NURBS trajectory** per edge, and the trajectory "can be omitted …
if the AGV plans its own trajectory" [fetched, VDA 5050 v2.0 via
vda.de/bluebotics.com mirror]; BlueBotics ANT missions ("transfer … happens
just once") [fetched]; Kollmorgen system controller → CVC [snippet].
*Link slow/lost:* almost nothing breaks — the executor holds the path and
follows it on local pose; on loss it finishes or stops per its supervision
watchdog (this project's AT-09 shape: controlled stop, order kept).
*State:* executor holds path, pose and progress; sender holds intent.
*Requirement:* the executor **must** run localization and path following
onboard — this option presupposes an intelligent vehicle.
**Industrial verdict: this is the standard *network* interface, fleet → 
vehicle.** It is where VDA 5050 lives, i.e. this project's M6 seam.

**(d) A pose target.**
*Who:* Nav2's goal interface; a VDA 5050 node in the degenerate one-node
order. Maximum executor intelligence; the network carries intent only.
Same loss behaviour as (c).

**The pattern, compressed:** the interface granularity is set by the
intelligence of the *executor*, and the transport is set by the granularity:
per-sample values demand a deterministic local link; paths and goals tolerate
networks. Real systems therefore have exactly **two** motion seams — (a)
onboard between the follower and the drives, and (c)/(d) over the network
between fleet and vehicle — and **nothing ships in between**. Architecture
B's increment interface sits precisely in that unoccupied middle: too
granular for the link it would cross, too coarse to be the drive interface,
with split state ownership as a bonus defect.

**Answer for this project:** across OPC UA the vehicle sends **no motion
value at any granularity** — it sends the §12.6 report (mode applied,
heartbeat), and receives the envelope. The continuous-velocity interface (a)
exists where industry puts it: **onboard**, Nav2 controller → smoother → 
envelope gate → `forklift_io` → Gazebo joints, all inside the vehicle's ROS 2
graph in WSL2. The path interface (c) arrives at M6 as VDA 5050, fleet → 
vehicle, exactly as invariant 3 requires.

## F. The two architectures judged, and the strongest objection answered

**Architecture A restated in controls-engineer terms:** an onboard navigation
controller (localization + planner + 20 Hz follower) commands the drive layer
over a local link; a supervisory PLC publishes permissions at its own scan and
owns fixed equipment; an independent onboard safety chain bounds everything
from below. That is, component for component, the ANT / CVC / Navitrol
architecture with the PLC in the role every cell PLC has: equipment,
interlocks, handshakes, supervision.

**Architecture B restated fairly:** the S7-1500 is read as the forklift's
onboard vehicle controller (the SIMOVE reading); the navigation computer feeds
it work; it forms every setpoint as it did at M4; the network inside the
motion loop is dismissed as a simulation artifact of the twin, not an
architectural property.

**Why B loses on the evidence, despite naming a real pattern:**

1. **The box is miscast.** The SIMOVE/Beckhoff PLC that forms motion
   setpoints is *one per vehicle, onboard, on a deterministic fieldbus*. This
   project's S7-1500 standard program is the **cell's**: it owns conveyor,
   door, charger (§5–§7 of the M3/M4 specs), serves OPC UA to the future
   fleet manager (invariant 4), and at M6 is **one program supervising four
   vehicles**. A single stationary controller cannot be four vehicles' onboard
   motion controller; no vendor ships that topology at any fleet size.
   ADR 0011 D1's onboard reading is scoped to the **F-runtime group** — and
   even there, the single hosting CPU is a disclosed simulation artifact
   whose four-instance scaling is pinned unverified (ADR 0012 F13/F14). B
   extends that reading to the standard program, where it collides with the
   same program's fixed-equipment ownership — the one thing that is
   *unambiguously not onboard*.
2. **The interface B implies is shipped by nobody** (§E option b), and its
   structural defect — the corrector needs pose it doesn't hold — is
   independent of latency.
3. **The latency is not only an artifact.** Even granting B's "no network
   architecturally" reading for a hypothetical real build, the *demonstrated*
   machine is the twin, gates close on observable behaviour (CLAUDE.md §6),
   and the observable behaviour would carry §C's weave and docking scatter in
   every recording. A project whose stated priority is fidelity to industrial
   practice would be demonstrating, on camera, a control topology whose
   measured behaviour industry rejects.
4. **M4's claim does not need rescuing** — it is already preserved,
   mode-scoped: in Teleop the PLC still forms every setpoint (§12.9 C1), the
   M4 logic is untouched (C2), and the mode selector changes the source
   exactly as the owner describes. What B would additionally buy — the same
   sentence in autonomous mode — is bought by making the autonomy loop
   worse than any named product's.

**The strongest objection to A, stated at full strength and answered.**
*"Siemens themselves put the S7-1500 on the vehicle and route motion through
it — SIMOVE is the proof. Choosing A, the project's PLC never touches
autonomous motion, so the PLC work — the project's centrepiece — is reduced
to a permission bit and a ceiling. That is a weaker machine and a weaker
portfolio than the Siemens pattern the owner is pointing at."*

Answer, in three parts. First, SIMOVE proves an **onboard** PLC pattern; the
faithful way to adopt it would be a *second, vehicle-mounted* controller —
a new layer this project does not have and does not need for its claims,
not a new role for the cell PLC; miscasting the cell PLC as onboard is not
the Siemens pattern, it is its violation. Second, the PLC's autonomous-mode
role under A is not decorative: it is the same role SIMOVE's **Master
Control** and the station-owning cell PLCs play — equipment readiness,
handshakes, mode arbitration, supervision verdicts — plus, through the
F-layer, the vehicle's entire safety story; "the PLC owns the envelope, the
fleet manager owns the traffic, the vehicle closes the loop" is a sentence a
controls reviewer recognises as correct practice, which is worth more to
this portfolio than a bigger PLC program doing an unrecognised thing. Third,
the M4 showcase remains fully true and fully PLC-centric in its own mode —
nothing recorded is weakened.

**Honest cost of A, so the defence is not free:** the PLC cannot *enforce*
the envelope, only notice non-compliance (§12.6 already states this); in
process terms the vehicle's obedience is checked, not compelled, and the
compelling backstop is the safety layer — which in this hardware-free project
is modelled, not real (D5 claim boundary). That asymmetry must be narrated,
never papered over. §M carries it as the recommendation's biggest risk.

## G. The M6 consequence (question 6)

**Under A:** fleet manager ↔ vehicles over VDA 5050/MQTT (orders out, state
back — §E option c); fleet manager ↔ PLC over OPC UA (station handshake,
client to server, invariant 4); each vehicle closes its own loop onboard.
Four vehicles cost four VDA 5050 clients and four envelope consumers — the
architecture is restated zero times, which is ADR 0011's "scales to M6"
consequence, now with the industrial names behind it (SEW's VDA 5050
interface, SIMOVE Fleetmanager). The only M6 scaling caveats are the ones
ADR 0012 already pinned (F13/F14, safety-instance hosting) — untouched here.

**Under B:** one stationary PLC forms per-sample (or per-segment) setpoints
for four vehicles across the network while also serving the cell — a
topology with no named precedent at n=1 and compounding at n=4: four 20 Hz
command streams through one OB and one OPC UA server, four vehicles' motion
coupled to one CPU's scan headroom and one radio cell's jitter, and the
fleet manager (VDA 5050's *order*-granularity contract, invariant 3) sitting
above a PLC that now needs path-level data VDA 5050 does not carry to it.
B is not merely weaker at four vehicles; it has no coherent M6 statement.

**Portability (mv-01):** under A the vendor seam carries only the low-rate
contract (envelope, mode, report — nine nodes), so the Beckhoff port
inherits nothing motion-critical and mv-01's byte-identical-client claim
survives. Under B the ported PLC program would contain the path follower,
and the port would re-implement the motion loop per vendor.

## H. The simulation consequence (question 7)

Under **A**, what must be measured and disclosed: (i) envelope propagation
age, PLC write → bridge poll → topic publish (expected ~50–150 ms by the M3
measurements; harmless by E1, but *measured, not asserted*); (ii) the
vehicle-side freshness window E5 against that measurement; (iii) the onboard
loop's own rate and jitter (WSL2-internal — this is the part the simulation
does **not** distort, and that is worth one disclosed sentence: the loop that
industry keeps onboard is genuinely onboard in the twin as well). The
demonstration remains honest with the disclosures the interface documents
already carry.

Under **B**, every recorded motion would include the WSL2↔Windows link
inside the loop; the disclosure would have to accompany **every** recording
("the weave you see is the simulation's link, a real build would not have
it") — a running apology for behaviour the architecture chose, where A's
disclosure is a footnote about a supervision channel. B is demonstrable only
with the disclosure written as a standing caveat over the machine's visible
quality; A is demonstrable as built.

## I. The command interface, specified concretely

Enough for an interface brief and a PLC brief without invention. Three seams,
each with content, rate, loss semantics and state owner. Names are the
existing contract's; nothing new is minted here.

**Seam 1 — supervision (PLC ↔ vehicle, over OPC UA via the bridge). This is
the §12 contract, confirmed unchanged.**

| Item | Specification |
|---|---|
| Down: envelope | `ForkliftMotionEnable` (Bool), `ForkliftSpeedCeiling` (Real, m/s, unsigned), `ForkliftEquipmentPermit` (Bool), plus `ForkliftDriveModeActive` (UInt16 {0,1,2}) |
| Up: report | `ForkliftVehicleModeApplied` (UInt16), `ForkliftVehicleHeartbeat` (UInt16 counter) |
| Rate | PLC forms at its 20 ms scan; bridge polls/republishes at its 20 Hz cycle; **contractually rate-insensitive** (E1: a 2 Hz consumer differs only in latency) |
| Loss, vehicle side | Envelope older than the E5 freshness window (an `agv/` named constant, to be set ≥ 2× measured propagation age, i.e. ≥ ~300 ms on M3 numbers, value owned by m5-11) → **controlled stop onboard**; stale is non-permissive; not a safety event (invariant 2) |
| Loss, PLC side | Heartbeat verdict false (V1–V4 semantics) → envelope published is the non-permissive one; degraded mode, latch policy owned by m5-16 |
| State | PLC owns the envelope and the mode verdict; vehicle owns its report values (bridge writes the nodes); nobody recomputes the other's datum |

**Seam 2 — motion (onboard, ROS 2 inside the vehicle's graph; never crosses
OPC UA).**

| Item | Specification |
|---|---|
| Content | Continuous velocity/steer/fork commands in engineering units on the existing `/forklift/cmd/*` topics, formed by: Nav2 controller (20 Hz) → velocity smoother **closed-loop on measured odometry** (ADR 0011 D3's consequence) → envelope gate node (m5-11) → `forklift_io` → gz joint commands |
| Envelope gate law | enable FALSE **or** envelope stale → controlled stop (own decel ramp); else clamp \|v\| to `ForkliftSpeedCeiling`; gate sits **onboard, below the smoother**, so it acts with the link dead |
| Rate | 20 Hz command formation; smoother may interpolate higher; drive loop closes in the physics engine per step |
| Loss | Nav2 `velocity_timeout` zero-command (1.0 s default, retunable); `forklift_io`/gz apply last-command semantics bounded by the gate — the gate node is the vehicle-side dead-man |
| State | Vehicle owns path, pose, progress, and its own stop ramps |

**Seam 3 — orders (M6, fleet ↔ vehicle, VDA 5050/MQTT).** Order = node/edge
graph, optional NURBS per edge (vehicle may plan its own trajectory); state
reported on change plus periodic minimum per the standard; broker loss →
supervision watchdog → controlled stop, order kept (AT-09 as written). No
motion value at higher granularity ever enters this seam.

**What the PLC does with seam 1, in PLC terms (input to m5-16):** forms the
envelope terms from mode arbitration, link verdicts, standing latches and the
station-permit conjunction, at its own scan, with the non-permissive value in
every ELSE and every start value — the §7 discipline unchanged; supervises
the vehicle heartbeat under V1–V4 with its own named stale constant; never
receives, forms, ramps or forwards an autonomous-mode motion setpoint.

## J. The flow, step by step, from lidar return to wheel motion

Written to be read aloud. Autonomous mode; the teleop contrast and the safety
chain follow it.

1. **The navigation lidar fires and returns ranges.** In the twin, Gazebo
   renders the scan (10 Hz) and the ros_gz bridge puts it on the vehicle's
   `/scan` topic. *Component: the sensor and its onboard transport.* Why
   here: the scan is the highest-rate, highest-volume data in the system;
   every named product consumes it where it is born — on the vehicle.
2. **The vehicle computer turns the scan into a pose.** SLAM/localization
   matches the ranges against the map and says "you are here, facing this
   way." *Component: the vehicle's ROS 2 graph.* Why not the PLC or the
   fleet: they never see the scan, and pose is needed 10–20 times a second by
   the very next step — this is what ANT and the CVC do onboard, for the same
   reason.
3. **The planner draws the path.** From pose, map and live obstacles, Nav2
   plans the route to the current goal. *Component: the vehicle computer.*
   Why: planning consumes map, pose and costmap, all onboard; the fleet (at
   M6) sends the *order*, never the path geometry — VDA 5050 even lets the
   vehicle discard the suggested trajectory and plan its own.
4. **The follower turns path plus pose into "how fast, how much steer" —
   twenty times a second.** This is the loop the whole brief is about, and it
   closes here, onboard, because each cycle needs the pose made in step 2 at
   full freshness — 50 ms of budget, which the OPC UA link alone would spend.
   *Component: Nav2's controller — this stack's equivalent of the CVC700 or
   ANT motion control.*
5. **The envelope gate checks the PLC's permission.** The gate node holds the
   last envelope the bridge republished: enable false, or envelope stale →
   controlled stop; otherwise clamp speed to the ceiling. *Component: the
   vehicle's gate node (m5-11), deliberately onboard.* Why: permission must
   bind **especially** when the link is dead, so the check rides with the
   loop, not across the network — the supervisor's word is enforced at the
   point of motion, exactly as a real vehicle applies its site rules locally.
6. **The smoother ramps it, against what the wheels actually did.** Closed on
   measured odometry, never on its own last output, so a gate-zeroed command
   ramps from reality (ADR 0011 D3's recorded consequence). *Component:
   vehicle computer.*
7. **The drive layer makes it physical.** `forklift_io` converts engineering
   units to joint commands; the Gazebo joint controllers — the twin's
   "drives" — close the fast loop inside the physics step, as a CiA 402
   drive in velocity mode closes its own loop on a real machine. *Component:
   the drive layer.* Why not Python, why not the PLC: the fast loop lives in
   the drive everywhere in industry, and invariant 9 says the same thing in
   this repository's words.
8. **Meanwhile, the PLC speaks at its own pace.** Every 20 ms scan the
   standard program re-forms the envelope — mode arbitration, link verdicts,
   latches, station permit — and the bridge republishes it. The PLC's
   sentences are permissions and readiness, never motion: *may you move, how
   fast at most, is my equipment ready.* *Component: the S7-1500 standard
   program — the cell's supervisor, the same role SIMOVE's Master Control
   and every station PLC plays.*
9. **Beneath everything, the safety chain neither asks nor waits.** The
   safety scanner's (modelled) OSSD channel lands on the F-layer — the
   vehicle's onboard safety controller (ADR 0011 D1) — and a protective-field
   intrusion raises the F-demand: in a real build SS1/STO at the drive, in
   the twin the demand that drops the permissive and the envelope. It
   consumes no network, no envelope and no Nav2 state, and it would fire
   identically with every link dead. *Component: the F-program.* Why: this
   is invariant 1, and §D showed it is also exactly where industry puts it.
10. **In teleop, steps 2–6 fall away and the M4 machine returns unchanged:**
    the operator's request goes HMI → PLC, the PLC forms every setpoint
    under its interlocks, the bridge applies them. The mode selector changes
    **which source writes the request** — the operator through the PLC, or
    the onboard controller under the PLC's envelope — and the two sources
    are never live together (§12.9).

The single sentence of the flow: **the vehicle closes the loop it can only
close where its senses are; the PLC bounds it with the words a supervisor
actually owns; the safety layer underwrites both without asking either.**

## K. Every invariant, checked

| Inv | Verdict under the recommendation |
|---|---|
| 1 | Holds — safety chain onboard/hardwired (modelled per D2); no safety datum on any seam in §I |
| 2 | Holds — every loss reaction in §I is a controlled stop / non-permissive envelope, named as degraded mode |
| 3 | Holds — M6 seam is VDA 5050 unmodified; the envelope is not a fleet interface and carries no order data (E7) |
| 4 | Holds — PLC stays server; vehicle layer is not a client (§12.1); fleet will be a client |
| 5 | Holds — orders/traffic/zones stay fleet-side; PLC keeps equipment, interlocks, handshakes (ADR 0012 D1 confirmed) |
| 6 | Holds — fleet reads state and issues orders; the envelope it may someday read cannot command (E6, refused-write enforcement §12.11) |
| 7 | Holds — F-program's demand path independent of standard program and of every link (§13 coupling unchanged) |
| 8 | Untouched — no Tailscale edge anywhere in §I |
| 9 | Holds and is load-bearing — the deterministic loop stays in the physics engine/drive layer; Python nodes degrade smoothness, never integrity; **B would have violated it** (20 Hz loop through the Python bridge) |
| 10 | Holds — every §I datum has one owner; B's split motion state (§E-b) was the counterexample |
| 11 | Holds — layers touch only adjacent layers; monitoring plane unchanged (D4) |
| 12 | Untouched — Gazebo throughout |
| 13 | Untouched — no secrets involved |

## L. Relationship to the recorded ADRs

**Nothing needs superseding.** The recommendation confirms:

- **ADR 0011 D3** (envelope; loop closes onboard) — confirmed, now on named
  industrial evidence rather than on the original three-count rationale
  alone. Its "no published prior art for PLC-in-the-loop Nav2" alternative
  is strengthened: this research found no prior art for *any* vendor's
  navigation loop crossing a non-deterministic link.
- **ADR 0012 D1** (station permit) — confirmed; the two-permits table maps
  onto the SIMOVE Master-Control/cell-PLC split.
- **ADR 0011 D1** — confirmed **as scoped**: the onboard-safety-controller
  reading covers the F-runtime group. The research adds a boundary worth the
  owner's attention: that reading must **not** be extended to the standard
  program, which is the cell's controller by its own equipment ownership.
  The brief's Architecture B note read D1 as "the S7-1500 represents the
  forklift's onboard controller"; D1's text rules only the F-layer, and this
  report recommends keeping it that way.
- **opcua-nodes.md §12** — confirmed as the seam-1 contract, unchanged.

**Had Architecture B been chosen**, the project would have had to supersede
ADR 0011 D3 (loop location, envelope), ADR 0012 D1 (its refinement),
withdraw opcua-nodes.md §12 (E1, E4, the deliberately-absent rows of §12.12)
and re-mint a per-sample or per-segment command group, amend the bridge's
no-logic contract's cadence story, and record a new reading of ADR 0011 D1
extending "onboard" to the standard program — five documents against the
grain of the evidence in §A–§E. That cost is recorded so the decision's
weight is visible, not to reopen it.

## M. Risks and open questions

**Biggest risk of the recommendation (stated, not hedged):** in autonomous
mode the PLC's authority over motion is *permissive and checked, not
compelled* — the envelope gate that enforces it runs on the vehicle, and the
compelling backstop is a safety layer that is modelled, not real, for as long
as the project is hardware-free (D5). A hostile reviewer can say "the
supervisor's word is honour-system in process terms." The defence is
disclosure plus §12.6's readback design — but the defence must actually be
spoken in the M5 showcase, and the M7 LLM-layer story inherits the same
sentence. Second-order risk: the portfolio's PLC-depth claim now rests on
M4 teleop, the F-layer, and the M6 station handshake — the M6 handshake work
should be scoped generously enough to carry it.

**Open questions for the owner:**

1. Whether the public narrative should name the onboard stack "the vehicle
   controller" explicitly (the CVC/ANT analogy of §J step 4) — one sentence
   in README/roadmap territory, outside this report's write scope.
2. A measurement brief for seam 1: envelope propagation age and jitter,
   PLC → topic, so E5's freshness window is set from a measured number
   (§H item i) rather than from the M3 proxy.
3. Whether this locus ruling should be pinned as its own short ADR (statused
   accepted, citing this report), so the next architecture review finds a
   decision rather than a report. Advisory; arch-docs' call.

## N. Sources

All checked 2026-07-31. Grade per the preamble; [snippet]-grade rows are
candidates for re-verification if any is ever made load-bearing beyond this
report.

| # | Claim it carries | Source | Grade |
|---|---|---|---|
| S1 | ANT lite+ localizes, controls motion, commands motor controllers directly (or via vehicle PLC); mission data transfers once, not continuous server commands; scanner interfacing | https://bluebotics.com/autonomous-navigation-technology/ant-lite-plus/ | [fetched] |
| S2 | ANT docking/positioning accuracy ±1 cm / ±1° | https://bluebotics.com/autonomous-navigation-technology/ant-localization and https://www.antdriven.com/ant-natural-navigation | [snippet] |
| S3 | CVC700 software is "the heart of the AGV", supervising vehicle navigation, communication with the AGV system controller, and interfacing sensors and actuators | https://ndcsolutions.com/cvc700/ and https://www.kollmorgen.com/en-us/products/autonomous-mobile-solutions/cvc700 (kollmorgen.com returned 403 to direct fetch; wording from search excerpt) | [snippet] |
| S4 | CVC600 onboard controller, WLAN/LAN/CAN/RS-232/422/485 interfaces, any wheel configuration and navigation technology | https://www.oemoffhighway.com/electronics/smart-systems/control-units/electrical-electronic-components/control-units/product/10210547/kollmorgen-cvc600-vehicle-controller | [snippet] |
| S5 | SIMOVE: common onboard hardware platform "PLC and PC with Linux"; ANS+ feature-based-SLAM navigation; Master Control / Fleetmanager as the fleet layer; "Safe Velocity" certified failsafe speed library (SIL/PL) | https://www.siemens.com/en-us/products/simove/ | [fetched] |
| S6 | Integrator builds name the S7-1500 Open Controller as the SIMOVE vehicle controller, with ET 200SP, IPC 127E and iWLAN alongside | https://www.robotics247.com/article/siemens_partners_parmley_graham_ar_controls_build_bespoke_automated_guided_vehicles (403 to direct fetch; wording from search excerpt) | [snippet] |
| S7 | Beckhoff+Navitec: Navitrol navigation in a Linux VM under the TwinCAT/BSD hypervisor beside the TwinCAT PLC on one onboard controller; EtherCAT backbone; TwinSAFE/FSoE incl. safe position and safe velocity; "one controller can easily handle complex machine safety in addition to PLC and motion control, and now additionally the navigation" | https://www.blog.beckhoffus.com/post/navitec-agv-amr-navigation | [fetched] |
| S8 | Beckhoff AGV/AMR platform positioning (PC- and EtherCAT-based control for mobile robots) | https://www.beckhoff.com/en-en/industries/warehouse-and-distribution-logistics/agvs-and-mobile-robots/ | [snippet] |
| S9 | SEW MAXOLUTION / MOVI-C onboard automation, MOVIKIT localization/kinematics modules, VDA 5050 fleet interface | https://www.seweurodrive.com/automation/mobile-robotik/technology-modular-system/technology-modular-system.html and https://www.sewmaxolution.com/ | [snippet] |
| S10 | VDA 5050 order = node/edge graph; trajectory as NURBS, omissible "if the AGV plans its own trajectory"; state reporting via nodeStates/edgeStates | https://www.vda.de/dam/jcr:f0c9c019-1506-4dee-998a-e92723fbf025/EN-VDA5050-V2_0_0.pdf (v2.0.0, Jan 2022; mirror at https://bluebotics.com/wp-content/uploads/2022/10/VDA-5050-Recommendation.pdf) | [fetched] |
| S11 | Nav2 controller server default 20 Hz; velocity smoother interpolating to ~100 Hz; `velocity_timeout` default 1.0 s with zero-command on timeout | https://docs.nav2.org/configuration/packages/configuring-controller-server.html and https://docs.nav2.org/configuration/packages/configuring-velocity-smoother.html | [fetched] |
| S12 | CiA 402: control/status word, state machine, modes incl. Profile Velocity; setpoints via RPDO, actuals via TPDO; drive closes its loop internally | https://www.can-cia.org/can-knowledge/cia-402-series-canopen-device-profile-for-drives-and-motion-control and https://www.kebamerica.com/blog/using-cia-402-drive-profile-motion-control-applications/ | [snippet] |
| S13 | AGV scanner OSSDs into onboard safety controller (Flexi Soft): protective field → all drives stopped and restart prevented; warning field → instructs vehicle control to slow (process); field switching for mobile platforms | https://www.sick.com/br/en/sick-and-mastermover-safe-starting-points-for-industry-40/w/blog-mastermover-agv-safety and https://www.machinebuilding.net/safety-laser-scanners-boost-agv-productivity-and-safety | [snippet] |
| S14 | STO/SS1/SLS definitions, SLS realised in the drive and selected by the F-CPU | ADR 0011 evidence table F10 (IEC 61800-5-2 via Siemens drive-safety literature), pinned 2026-07-30 | pinned |
| S15 | ISO 3691-4 Type C standard; 0.3 m/s cap with personnel-detection means muted | ADR 0011 evidence table F11, pinned 2026-07-30 | pinned |
| S16 | Scanner monitoring-case switching cross-validated against safely measured speed/direction; warning-field slowdown is process, protective-field stop is safety | ADR 0011 evidence table F9, pinned 2026-07-30 as practice | pinned |
| S17 | This project's measured link: ~46 ms median one-way (46.163 / p95 47.690, quantised by the 50 ms poll); 145.6–150.8 ms presence-to-assertion chain | `bridge/EVIDENCE_LATENCY.md` via docs/reports/m3-33-evidence-writeup.md, measured 2026-07-27/28 | internal |

**Recorded absence (falsifiable):** no named free-navigating AGV/AMR product
was found that ships a segment/increment interface between a navigation
computer and a setpoint-forming controller (§E option b), and none that
routes its trajectory-following loop across a wireless or best-effort
network. What would settle it: a vendor integration manual demonstrating
either. If one surfaces, §E and §F must be re-argued against it.
