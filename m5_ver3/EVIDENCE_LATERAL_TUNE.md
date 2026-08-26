# EVIDENCE — the plant's lateral scrub, diagnosed and tuned (F1.5)

**Gate:** m5-ver3 phase **F1.5**, owner-approved 2026-08-26 on the back of
F1's measurement. **Branch** `m5-ver3`, **base commit** `32c8964`.
**Scope rule for this gate (constraint 12):** the tuning surface is the
**WheelSlip system's parameters only** — the compliances, the per-wheel
entries, and their normal-force derivations. Friction `mu`, inertias,
masses and geometry are out; a target unreachable inside that surface is
a BLOCKED report and not a licence to widen it.

**What F1 handed over.** `EVIDENCE_SENSORS.md` §4: at 0.3 m/s and π/4 of
steer the plant delivered **0.410** of the yaw its geometry promises, and
one steer angle did not have one delivered fraction — it had a fraction
that depended on the vehicle's heading, by 16.6 % over the four corners
of a square. F1 recorded that and changed nothing, which is what
constraint 7 required of it.

**What this gate did.** Diagnosed where the yaw was being lost, tuned it
inside constraint 12, and re-measured everything the tune could have
broken. The headline:

| | before (F1) | after (F1.5) |
|---|---|---|
| `corner_creep` delivered, π/4 at 0.3 m/s | **0.4099** | **1.0054** |
| effective turning radius vs kinematic 1.0434 m | 2.5190 m | 0.9859 m |
| yaw-rate wander inside one held corner | 10.1 % of its mean | **0.0 %** (sd 0.000045 rad/s) |
| longitudinal slip at 0.7 m/s cruise | 0.96162 % | **0.95603 %** |
| `square` ground-truth closure | 0.6786 m | **0.0670 m** |
| `square` four-corner heading spread | 16.6 % | 11.5 % |
| `straight` wheel-odometry end error | 0.5800 m | 0.5778 m |

**And the change that produced it is not a tuned number.** Neither
compliance moved. What moved is *which wheels carry the system*: the two
rear wheels, which had no entry at all, now carry the same 7.0 the drive
wheel does, at their own normal force. §2 is why that was the repair and
§3 is the ladder that shows nothing on the drive wheel alone got there.

---

## 1. The rig, and what every figure below was taken on

Unchanged from F1 and stated so a figure can be placed: WSL Ubuntu 24.04,
ROS 2 Jazzy, gz-sim 8.11.0, GPU gate passed (`D3D12 (NVIDIA GeForce RTX
4050 Laptop GPU)`), partition `m5v3`, domain 97, **headless**, nothing
else on the machine. Every rig figure here is one full
`m5v3.sh stop` → edit `model.sdf` → `m5v3.sh start --headless` → measure
cycle, which is the cycle `EVIDENCE_MODEL_V3.md` §7 used for the
longitudinal ladder.

| Instrument | What it produced here |
|---|---|
| `tools/drive_route.py corner_creep` | the held π/4 corner every ladder row is scored on |
| `tools/sensor_evidence.py record --drive P` | the CSVs; `analyse` reduces them with no ROS |
| `analyse`'s *does the tricycle model hold* block | delivered fraction, effective radius, in-corner wander |
| `analyse`'s **where the yaw went** block (new, §2.2) | the split of the deficit between the two contact patches |
| `analyse`'s *every held corner* table | the four-corner heading spread |
| `analyse`'s **CLOSURE** line (new) | the square's ground-truth closure |
| `tools/slip_bench.sh` | longitudinal slip at the 0.7 m/s cruise |
| `tools/rtf_probe.sh` | real-time factor of the running world |

**Real-time factor, spot check (`rtf_probe.sh`, 30 s, headless).** Two
passes, both on the **tuned** plant: mean **0.9989** / median 0.9999 /
floor 0.9592 / ceiling 1.0463, and mean **0.9988** / median 0.9998 /
floor 0.9596 / ceiling 1.0635. `EVIDENCE_SENSORS.md` §5's two passes on
the untuned one read mean 0.9992 and 0.9984, median 0.9999 and 0.9998,
with the floor wandering 0.936 to 0.969 — which that section already
calls the noisiest of the four statistics. **Two more contact patches
carrying a plugin cost nothing measurable**: the means fall inside the
same 0.9984–0.9992 spread the plant showed before the tune, and the
median has not moved from 0.9999 across four tasks.

---

## 2. The diagnosis: the yaw is lost at the steered wheel, and the rear axle is why

### 2.1 The question the brief asked first

Where does the yaw go — the steered wheel sliding sideways, the rear axle
sliding sideways, or both? That is not a matter of opinion: a tricycle's
yaw rate is an exact function of its rear axle's body velocity, its yaw
rate and its steer angle, and rearranging it charges the deficit to one
contact patch or the other with nothing left over.

Take the rear-axle midpoint P, body x forward, its ground velocity in
body axes `(u, w)`, yaw rate `ψ̇`. The steered contact stands `L` ahead of
P, so its ground velocity is `(u, w + ψ̇L)` and resolving that across the
wheel plane at steer angle `δ` gives the two slip velocities the tyres
actually see:

```
  s_f = -u·sin δ + (w + ψ̇L)·cos δ        across the steered wheel
  s_r = w                                 across the rear axle
```

and therefore, by rearrangement and no assumption at all,

```
  ψ̇ = u·tan δ/L  +  s_f/(L·cos δ)  -  s_r/L
      \__________/   \____________/     \_____/
       kinematic       front term        rear term
```

### 2.2 The reduction, and it is a committed tool

`evidence_core.scrub_split()` computes exactly that, per interval, off the
ground truth's own track (moved onto the rear axle) with the steer reading
resampled onto the truth's clock. `sensor_evidence.py analyse` prints it
under the fidelity block for every measured corner and adds three columns
to the per-corner table. It prints its own `residual` — the identity's
closure — because a reader should not have to take the algebra on this
file's word.

**Instrument:** `analyse` over `drive-corner_creep-20260826-062618`
(the untuned plant, re-driven today so the before and after are the same
day and the same stack). `odom_truth.csv` md5
`6a048fb4649ffc69787e54cbbda20689`, `joint_state.csv` md5
`5a112036cd17e51df86b8aa615d4900e`.

```
  steady window   [36.138, 45.760] s of sim time, 193 truth samples
  steer commanded -0.785398 rad     held (measured) -0.788531 rad
  tread commanded -0.300 m/s        rear-axle ground speed 0.2092 m/s
  yaw rate        +0.083067 rad/s
  kinematic v_rear*tan(d)/L  0.200537 -> delivered 0.4142

  --- where the yaw went: the steered wheel, or the rear axle? ---
  rear-axle velocity in its own body frame: along -0.209242 m/s, across +0.000673 m/s
  steered contact:  across the wheel plane -0.086465 m/s, along it -0.209834 m/s
  slip angles     steered -0.3909 rad (-22.39 deg)   rear +0.0032 rad (+0.18 deg)
  the driven patch slides 0.124924 m/s in all, 43.8 deg off its own wheel plane
  longitudinal slip AT THE STEERED CONTACT, in this corner: 30.0552%
  yaw budget      kinematic +0.200536 = steered +0.116827 + rear +0.000641 + delivered +0.083067
  DEFICIT         +0.117469 rad/s (58.6% of kinematic): steered wheel 99.5%, rear axle 0.5%
  identity closes to 0.000e+00 rad/s (192 intervals) - it is algebra, so this is rounding.
```

**The answer, stated before a single value was changed:**

> **99.5 % of the missing yaw is the steered wheel sliding sideways. The
> rear axle is not sliding at all** — 0.67 mm/s of lateral velocity, a
> slip angle of 0.18°, against the steered wheel's 86 mm/s and 22.4°.

Two readings beside it that matter as much:

- **The drive joint is not the shortfall.** Over the 4812 joint samples
  inside that window `drive_wheel_joint_vel` reads **−2.500000 rad/s**,
  minimum and maximum both, against a command of −2.500000. The tread
  speed at the tyre is exactly 0.300 m/s. Every millimetre of the loss is
  at the contact patch. (Same reading `EVIDENCE_MODEL_V3.md` §7 makes for
  the straight, made again for the corner.)
- **The driven patch is not "scrubbing sideways", it is sliding.** Its
  contact velocity along its own wheel plane is 0.2098 m/s against
  0.300 m/s of tread — **30.06 % longitudinal slip at the steered
  contact**, in a corner, on a plant whose straight-line longitudinal slip
  is 0.96 %. The total slide is 0.1249 m/s at 43.8° off the wheel plane.

### 2.3 A rear axle that does not slide is not an innocent rear axle

The split says the rear axle is not sliding. That is a fact about
velocities, and the obvious reading of it — "so the rear wheels are fine,
tune the front" — is the wrong one, because **a tricycle's rear axle is
not supposed to slide.** Its lateral velocity is zero in the ideal
kinematics too. Zero is what a correct rear axle reads and it is also what
a *rigidly stuck* one reads, and the split cannot tell those apart.

What can is a force balance, and it does not close:

- The WheelSlip system's compliance is `param · r·|ω_spin| / N_ref` in
  (m/s)/N — `4.63e-4` at the creep corner's 0.30 m/s of tread,
  `1.08e-3` at the bench's 0.70 m/s. **The formula is calibrated**: on a
  straight the drive wheel has only the three joints' damping to
  overcome, 7.2 N at cruise, and `7.2 × 1.08e-3 / 0.7` predicts **1.1 %**
  of slip against the **0.96 %** the bench measures.
- The measured 0.1249 m/s of slide at the steered contact therefore
  implies a contact force of about **270 N**, pointing very nearly along
  body +y.
- A steady 0.3 m/s turn on a 1.04 m radius needs a net lateral force of
  about 50 N and **zero net yaw moment**. 270 N at the steered contact,
  0.633 m ahead of the centre of mass, is +171 N·m; no lateral force at
  the rear axle can balance both that moment and the 50 N at once — the
  books are about **260 N·m** short.
- A pure yaw couple at the rear axle is the only thing that closes them,
  and it is exactly what two **rigid** contact patches 0.10 m wide do when
  they are forced to yaw about their own vertical axes: they cannot,
  without sliding, and with no compliance to slide against they resist
  with a Coulomb couple. Bounding it: a 0.10 m wide patch carrying 3448 N
  can hold at most `mu · N · 0.05` of yaw torque, which for the rear
  wheels' `mu` of 0.4 to 0.9 is 69 to 155 N·m each and **138 to 310 N·m
  for the pair**. The 263 N·m the books are short of is inside that.

The force balance is an inference and it is labelled one — it rests on
the compliance formula above rather than on a contact force this rig can
read. What it is good for is turning "the rear axle reads zero" into a
falsifiable prediction, which is the next paragraph.

**So the mechanism, named with a measurement and then tested rather than
argued:** the rear pair is not sliding *because it cannot*, and the price
of that is paid by the only patch that can — the steered one, which
slides at 22° to keep the vehicle turning at all. **Prediction: give the
rear pair a compliance and the steered wheel stops sliding.** §3 is that
experiment; it is row 6.

---

## 3. The ladder

Every row is one full stop / edit `model.sdf` / start headless cycle. The
creep column is `analyse`'s `corner_creep` fidelity — `commanded` is
`ψ̇ / (v_tread·sin δ/L)`, the figure `EVIDENCE_SENSORS.md` §4.1's headline
and this gate's acceptance are stated in; `measured` is
`ψ̇ / (v_rear·tan δ/L)`, which has the longitudinal slip already inside the
speed. The slip column is `slip_bench.sh` at the 0.7 m/s cruise, **from a
fresh start every time** (§6.2 says why that sentence is here). The wander
column is the in-corner spread that `EVIDENCE_SENSORS.md` §4.2 is about.

| # | drive lat / long | rear lat / long | creep, commanded | creep, measured | in-corner wander | cruise slip | verdict |
|---|---|---|---|---|---|---|---|
| 0 | 7.0 / 7.0 | *no entry* | **0.4099** | 0.4142 | 10.1 % | 0.96162 % | the plant F1 measured — the baseline |
| 1 | **1.0** / 7.0 | *no entry* | 0.7125 | 0.6130 | 26.6 % | **0.10688 %** | rejected: 0.107 % is a fifth of the band's floor, and the wander nearly trebled |
| 2 | **0.1** / 7.0 | *no entry* | 0.6965 | 0.5665 | 30.7 % | **0.01070 %** | rejected: *worse* than row 1 on the corner, and 0.011 % is a fiftieth of the floor |
| 3 | 7.0 / **1.0** | *no entry* | 0.6478 | 0.7178 | 7.2 % | 0.95842 % | rejected: 0.65 is not 0.90, and this is the best the drive wheel alone does |
| 4 | 7.0 / **0.1** | *no entry* | 0.6240 | 0.6528 | 4.8 % | 0.96140 % | rejected: past the turning point — stiffer is worse again |
| 5 | 7.0 / 7.0 | **0.1 / 0.1** | 0.7702 | 0.7934 | 2.3 % | 0.96221 % | rejected: a nearly-rigid rear pair is nearly the baseline |
| 6 | 7.0 / 7.0 | **7.0 / 7.0** | **1.0054** | 1.0583 | **0.0 %** | **0.95603 %** | **ACCEPTED** |
| 7 | 7.0 / 7.0 | **1.0 / 1.0** | 0.9915 | 1.0402 | 0.0 % | 0.95994 % | rejected: inside the target, but see §3.3 |
| 8 | 7.0 / 7.0 | **20.0 / 20.0** | 0.9641 | 1.0134 | 0.0 % | 0.94853 % | rejected: the rear axle crabs at 4.31° |
| 9 | **3.0** / 7.0 | 7.0 / 7.0 | 0.9878 | 1.0292 | **1.0 %** | **0.31881 %** | rejected: the wander returns and the cruise slip falls out of the band |

Sessions, in row order: `drive-corner_creep-20260826-` `062618`,
`063035`, `063154`, `070838`, `070944`, `063717`, `063404`, `063604`,
`063818`, `063948`. Row 6 was re-driven twice more after it was accepted
(`064158`, `071656`) and §4.1 reports all three.

### 3.1 What rows 1 and 2 found, and it is a defect worth its own heading

**`<slip_compliance_lateral>` is the element that governs this wheel's
LONGITUDINAL slip. The two elements' effects are swapped relative to
their names.**

That is measured, not inferred, and it is the whole reason the ladder is
shaped the way it is:

| drive lateral | drive longitudinal | cruise slip on a straight |
|---|---|---|
| 7.0 | 7.0 | 0.96162 % |
| **1.0** | 7.0 | **0.10688 %** |
| **0.1** | 7.0 | **0.01070 %** |
| 7.0 | **1.0** | 0.95842 % |
| 7.0 | **0.1** | 0.96140 % |

Moving the element named *lateral* moves the straight-line longitudinal
slip by a factor of ninety. Moving the element named *longitudinal* moves
it by 0.003 percentage points, which is the run-to-run repeatability.
And the two rows where lateral was moved land on **0.10688 %** and
**0.01070 %** — which are the 1.0 and 0.1 rows of
`EVIDENCE_MODEL_V3.md` §7's ladder, 0.10687 % and 0.01070 %, to within a
hundred-thousandth of a percentage point. That table moved *both*
elements together. So F1's longitudinal tuning table was, throughout, a table of
the element named lateral; it could not tell, because it never moved them
apart.

**What this corrects and what it leaves standing.** It leaves the tuned
value standing: 7.0 is 7.0 whichever name it wears, and the accepted plant
is isotropic so the labels do not reach it. What it corrects is
`EVIDENCE_MODEL_V3.md` §7's sentence *"Lateral compliance was set equal
and not tuned, and it costs nothing on a straight run."* The measurement
that sentence rests on — two micrometres of lateral wander over 21 m — is
correct and is not what the sentence concluded. Lateral compliance costs
the straight run **its entire 0.96 % of longitudinal slip**; what it does
not cost is sideways wander.

**Not chased past that.** Whether gz-sim's WheelSlip system emits the two
values in the other order, or whether the solver's two friction directions
are simply not the wheel's, is a question about code this gate did not
read. What is established is the behaviour, and it is the part anything
downstream needs: **on this plant, do not tune these two elements
separately expecting the names to hold.**

### 3.2 Rows 3 and 4 are the BLOCKED test, and it came back negative

Constraint 12 requires a stop-and-report if WheelSlip alone cannot reach
the target. Rows 3 and 4 stiffen the steered wheel's *true* lateral
direction — 7× and 70× — with the rear pair left as F1 had it:

| | steered lateral slip | delivered |
|---|---|---|
| baseline | 0.086465 m/s | 0.4099 |
| 7× stiffer | 0.037892 m/s | 0.6478 |
| 70× stiffer | 0.049904 m/s | 0.6240 |

It works, and then it stops working. Seven times stiffer more than halves
the sideways slide and buys 0.24 of delivered fraction; seventy times
stiffer gives some of it back. **The drive wheel alone tops out around
0.65 and 0.90 is not reachable from it** — which is exactly what §2.3
predicted, because the thing being fought is at the other end of the
vehicle. The report is therefore not BLOCKED: the target is reachable
inside constraint 12, through the per-wheel entries the constraint
explicitly allows.

### 3.3 Why row 6 and not row 7

Row 7 (rear 1.0) scores 0.9915 commanded against row 6's 1.0054, and
1.0402 measured against 1.0583 — closer to unity on both. It was
rejected anyway, and the reason is that row 6 needs no new number:

- **Row 6 invents nothing.** 7.0 is the compliance F1 measured for this
  vehicle's tyre; the rear wheels are the same 0.12 m polyurethane wheel
  on the same concrete, so they get the same compliance and their own
  load. Row 7 asserts that the rear tyres are seven times stiffer than the
  front one, which is a claim about a tyre that nothing measured.
- **Row 6 is not on a cliff.** The rows either side of it — 1.0 and 20.0 —
  deliver 0.9915 and 0.9641, so the curve is flat to ±0.02 of delivered
  fraction across a factor of twenty in the parameter. A value chosen for
  scoring 0.009 better inside that flat would be a value fitted to one
  run.
- **The rear axle's slip angle is the reading that separates them, and it
  runs the other way.** Row 7: 0.36°. Row 6: 1.66°. Row 8: 4.31°. A real
  counterbalance truck's rear axle at creep does slip a little and 1.66°
  is a plausible little; but this is the argument row 6 does *not* rest
  on, because "plausible" is not measured, and it is recorded here as the
  cost of the choice rather than as a reason for it.

**Row 9 is the one that settles the shape of the accepted setting.** With
the rear pair at 7.0 and the drive wheel made anisotropic (3.0 / 7.0), the
delivered fraction stays fine — 0.9878 — but the in-corner wander comes
**back**, from 0.0 % to 1.0 %, and the cruise slip falls out of the band
to 0.319 %. Every setting on this ladder that made one direction of a
contact stiffer than the other reintroduced the heading dependence:
10.1 % at row 0, 26.6 % and 30.7 % at rows 1 and 2, 7.2 % and 4.8 % at
rows 3 and 4, 1.0 % at row 9 — and **0.0 % at every row where all six
compliances are equal.** `EVIDENCE_SENSORS.md` §4.2 named the candidate
mechanism and did not chase it: an axis-aligned friction pyramid, which
is a pair of directions the wheel does not turn with. This is what such a
solver does to a contact patch that is not isotropic, and six equal
numbers is the only setting free of it. That is a measurement, and the
mechanism is still not chased.

---

## 4. The acceptance, item by item

### 4.1 Creep ratio ≥ 0.90 — **1.0054**

**Instrument:** `sensor_evidence.py record --drive corner_creep` then
`analyse`, headless. Three runs on the accepted plant, two of them across
a stack restart and a dozen intervening model edits:

| Session | `odom_truth.csv` md5 | yaw rate | delivered, commanded | delivered, measured | wander |
|---|---|---|---|---|---|
| `drive-corner_creep-20260826-063404` | `f4232e017ffaf37df388685f6a6cad02` | +0.203768 | **1.0054** | 1.0583 | 0.0 % |
| `drive-corner_creep-20260826-064158` | `9688bbaf43c32d937003cef1df4c7d25` | +0.203768 | **1.0054** | 1.0583 | 0.0 % |
| `drive-corner_creep-20260826-071656` | `323af5e9733b38190185e202d5d3ae96` | +0.203767 | **1.0054** | 1.0583 | 0.0 % |

The yaw rate repeats to within **1e-6 rad/s** across three runs. The
plant was already deterministic to a part in seven hundred
(`EVIDENCE_SENSORS.md` §3); it is now deterministic to a part in two
hundred thousand on this figure, because the wander that dominated it is
gone.

**The split on the accepted plant, same block, same run:**

```
  rear-axle velocity in its own body frame: along -0.200810 m/s, across +0.005816 m/s
  steered contact:  across the wheel plane +0.012467 m/s, along it -0.297438 m/s
  slip angles     steered +0.0419 rad (+2.40 deg)   rear +0.0290 rad (+1.66 deg)
  longitudinal slip AT THE STEERED CONTACT, in this corner: 0.8541%
  yaw budget      kinematic +0.192462 = steered -0.016844 + rear +0.005539 + delivered +0.203767
  DEFICIT         -0.011305 rad/s (-5.9% of kinematic)
```

Read across from §2.2: the steered wheel's sideways slide fell from
**86.5 mm/s to 12.5 mm/s** and changed sign, its slip angle from −22.39°
to +2.40°, and the longitudinal slip at the driven contact **in a corner**
fell from 30.06 % to **0.854 %** — which is the same 0.5–2 % band the
straight-line cruise sits in. The corner and the straight now ask the same
thing of the tyre, which is the property that was missing.

**The overshoot is stated and not smoothed.** 1.0054 is 0.5 % *over*
kinematic on the commanded ratio and 1.0583 is 5.8 % over on the measured
one; the effective radius is 0.9859 m against a kinematic 1.0434 m, so
the tuned plant corners **5.5 % tighter than its geometry**, where the
untuned one cornered 2.4× wider. The sign is now the other way and the
size is a **tenth** of what it was: the deficit was 58.6 % of the
kinematic rate and it is now 5.9 % on the other side of it. It comes from the two small slip terms
in the budget above not cancelling: the steered wheel now slips in the
direction that *adds* yaw (+0.0168 rad/s) and the rear axle's 1.66° takes
back only 0.0055 of it. Anything downstream that plans on `v·tan δ/L`
will command a corner **5.8 % wider than it gets** — a number to design
against, not a surprise, a tenth the size of F1's and the other way
round.

### 4.2 Longitudinal slip stays in the F1 band — **0.95603 %**

**Instrument:** `tools/slip_bench.sh`, 0.7 m/s cruise, 5 s settle, 10 s
window, forward and astern, from a fresh `start --headless` with the truck
at the spawn pose.

| Plant | forward | astern | mean vs command | mean vs achieved joint rate |
|---|---|---|---|---|
| F1's published figure (2026-08-25) | 0.95859 % | 0.96215 % | **0.96037 %** | 0.96037 % |
| baseline, re-measured today (row 0) | 0.96073 % | 0.96251 % | **0.96162 %** | 0.96161 % |
| **accepted (row 6)** | 0.95854 % | 0.95351 % | **0.95603 %** | 0.95602 % |

Inside the 0.5–2 % band, **0.0043 percentage points** from F1's published
value and 0.0056 pp from the same plant re-measured today — against a
figure F1 measured as repeating to about ±0.002 pp. The drive
joint reached `5.83333300 rad/s` in every segment of every run, so none
of it is the controller. Giving two free-rolling wheels a finite
compliance did not move the longitudinal slip of the driven one.

### 4.3 The square, re-tabled by measurement — closure **0.0670 m**

The `square` profile's corner hold time was tabled from the *pre-tune*
delivery factors and had to be re-derived. The method is Task 3's — drive
the corner, measure the delivered yaw rate at the steer the axis actually
held, size the hold from it — with one addition §4.3.2 explains.

#### 4.3.1 The measurement run

**Instrument:** `analyse`'s *every held corner* table over
`drive-square-20260826-064858` (corner **5.762 s**, a provisional time
computed from §4.1's fraction and never published as a table).
`odom_truth.csv` md5 `3989c3c0766f884dbc5c6d368137dd0a`.

```
    #        window [s]    span  heading in   held rad   rear m/s    yaw rate  delivered
    1    23.87    27.73    3.80     -2.8381  -1.259172     0.0825   +0.233908     0.8601
    2    32.97    36.84    3.80     -1.3959  -1.258044     0.0802   +0.261246     0.9610
    3    42.11    45.92    3.80     +0.1407  -1.257140     0.0838   +0.227701     0.8378
    4    51.16    55.02    3.80     +1.5348  -1.256432     0.0805   +0.262393     0.9657
  delivered       0.8378 to 0.9657 over 4 corners, spread 14.1% of the mean
```

Mean held rate over the four **0.246312 rad/s**; whole-run ground truth
turned **5.9060 rad**, i.e. 1.476500 rad per corner.

#### 4.3.2 The slew is now inside the arithmetic

`config.yaml`'s `square:` block said the profile could not close exactly
because the steer axis has to slew into every corner and the table was
sized from a rate measured with the axis already there. That is right that
the slew cannot be removed and wrong that it cannot be *measured*:

```
  yaw the held rate accounts for   0.246312 x 5.762  = 1.419250 rad
  yaw the truck actually turned    5.9060 / 4        = 1.476500 rad
  the slew's own contribution                       = 0.057250 rad  (3.28 deg)
  hold for a right angle    (pi/2 - 0.057250)/0.246312 = 6.1448 s
```

and the sign is the surprise: the slew contributes **more** yaw than the
hold window contains, not less, because the axis slews back *out* over the
following segment and the truck keeps turning while it does. A table sized
from the held rate alone would ask for 6.377 s and overshoot every corner
by 3.3°.

`config.yaml` now carries **6.145**.

#### 4.3.3 The re-driven square

**Instrument:** `record --drive square` then `analyse`, over
`drive-square-20260826-065230`. `odom_truth.csv` md5
`01e277aa61457a0a41cede60d9e81868`, `joint_state.csv` md5
`d3a8dbae77211a18c4e56da14d7991af`.

| | F1, untuned plant + untuned table | F1.5, tuned plant + re-tabled |
|---|---|---|
| ground truth turned, of 6.2832 asked | 5.8506 rad (93.1 %) | **6.3124 rad (100.5 %)** |
| **ground-truth closure** | **0.6786 m** | **0.0670 m** |
| four-corner delivered | 0.5504 – 0.6499 | 0.8553 – 0.9599 |
| **heading spread** | **16.6 %** | **11.5 %** |
| estimate turned | 10.1532 rad (1.74× the plant) | 6.8416 rad (1.084×) |
| estimate end error | 1.8707 m | 0.6712 m |

```
    #        window [s]    span  heading in   held rad   rear m/s    yaw rate  delivered
    1    25.25    29.44    4.15     -2.8412  -1.259136     0.0822   +0.235943     0.8676
    2    34.68    38.91    4.20     -1.3219  -1.257948     0.0802   +0.260950     0.9599
    3    44.13    48.39    4.25     +0.3201  -1.256994     0.0832   +0.232433     0.8553
    4    53.63    57.86    4.20     +1.8456  -1.256252     0.0810   +0.258307     0.9507
  delivered       0.8553 to 0.9599 over 4 corners, spread 11.5% of the mean
```

**Closure 0.0670 m against an acceptance of 0.30 m, one run, not driven
at.** The table was computed from the previous run's numbers and driven
once; there was no second fit.

**The heading dependence shrank and did not vanish, and where it survives
is specific.** At π/4 it is gone — the wander inside `corner_creep`'s held
corner is 0.0 %. At −1.25 rad it is **11.5 %** across the four corners,
down from 16.6 %, and it keeps its shape: the two corners entered along a
world *y* heading deliver 0.9599 and 0.9507, the two along *x* deliver
0.8676 and 0.8553 — the same 180° period, the same faster pair. So the
axis-aligned effect of §3.3 is not fully removed by making the contacts
isotropic; it is removed at moderate steer and reduced by a third at the
mechanical stop. **One steer angle on this plant still does not have one
delivered fraction at −1.25 rad**, and `config.yaml`'s corner time is
therefore sized from the mean of the four with the spread stated beside
it.

### 4.4 `straight` drift, re-measured — materially unchanged

**Instrument:** `record --drive straight` then `analyse`, over
`drive-straight-20260826-064555` (`odom_truth.csv` md5
`1a17c5c42a8cfd811bbf9a25a9077fd7`).

| | F1 × 3 (2026-08-25) | F1.5 |
|---|---|---|
| ground-truth path | 11.5935 / 11.5884 / 11.5905 m | 11.5479 m |
| estimate path | 12.0839 / 12.0786 / 12.0801 m | 12.0360 m |
| path error | +4.23 / +4.23 / +4.22 % | **+4.23 %** |
| **end error** | 0.5800 / 0.5798 / 0.5792 m | **0.5778 m** |
| rms over run | 0.5241 / 0.5240 / 0.5231 m | 0.5193 m |
| worst | 0.8016 / 0.8024 / 0.8006 m | 0.8009 m |
| end heading error | −0.0575 rad (all three) | −0.0574 rad |

Confirmed unchanged: the end error moved 1.9 mm off the three-run mean of
0.57967 m, on a figure whose own three-run spread is 0.8 mm, the scale error is the same +4.23 %, and
the heading error is the same 0.057 rad. **The ground-truth path is 43 mm
shorter** (11.5479 against a 11.5908 m mean, −0.37 %) — the one number in
this table that moved by more than its own repeatability. The rear wheels
now have a longitudinal compliance and free-rolling wheels that can slip
a little are a little more drag; the drive wheel's own cruise slip fell
0.006 pp over the same change (§4.2), so the vehicle covers marginally
less ground per revolution of everything. It is recorded rather than
explained away, and it is eight times the ground truth's own 5.1 mm
run-to-run spread on this profile.

### 4.5 The suite

```
  python -m pytest m5_ver3/tests/ -q         82 passed
  python3 m5_ver3/tools/evidence_core.py --selftest      16/16 checks passed
  python3 m5_ver3/nodes/wheel_odom_core.py --selftest    12/12 checks passed
```

74 → 82 tests: eight new ones over the two reductions this gate added.
Four lock the yaw-budget identity (a kinematic corner charges nothing to
either patch; a crabbing axle is charged to the rear and not the front;
the identity closes on a trace that obeys no model; the untuned plant's
own 99.5/0.5 split is reproduced from its measured `u`, `w` and `ψ̇`), and
four lock the closure reduction against being confused with path length.
`evidence_core.py --selftest` gained three checks over the same ground so
the rig has them without pytest.

---

## 5. What this gate changed

| File | Change |
|---|---|
| `gazebo/forklift_ver3/model.sdf` | two `<wheel>` entries for `rear_wheel_left` and `rear_wheel_right`, 7.0 / 7.0 at 3448.3 N each; the plugin comment carries the rear derivation, the correction to *"only the DRIVEN wheel carries it"*, and the ladder's three decisive rows |
| `config.yaml` | `wheel_slip.rear_wheel_normal_force_n`; corrected-by-measurement notes on `wheel_slip:`, on the `square:` delivery-factor table, on the square's geometry and closure paragraphs, on `wheel_odom:`'s scrub note and on `corner_creep:`'s *this is not a tuning run*; `square:`'s corner hold 9.142 → **6.145**; `evidence.corner.window_s` 6 → **3**; new `evidence.corner.split_min_deficit` |
| `tools/evidence_core.py` | `scrub_split()` and `closure()`, and three selftest checks |
| `tools/sensor_evidence.py` | the *where the yaw went* block, three columns on the per-corner table, the CLOSURE line, and the per-window steer resample |
| `tests/test_evidence_core.py` | eight tests |
| `EVIDENCE_MODEL_V3.md`, `EVIDENCE_SENSORS.md` | corrected-by-measurement notes only; **not one measured figure rewritten** |

**Nothing outside `m5_ver3/` was touched** except `tasks/TODO.md`, the
repository's phase ledger, which every m5-ver3 commit writes to and which
carries no behaviour. Inside the track no `mu`, no mass, no inertia and no
geometry moved. The two compliance values are
F1's, unchanged.

---

## 6. Two things that bit, recorded so they do not bite twice

### 6.1 A reduction sized against a plant that no longer exists

`evidence.corner.window_s` was **6 s**, and its comment derived that from
`square:`'s 9.142 s corner, which existed because the untuned plant needed
9.142 s to turn 90°. The tuned plant needs about 5.8 s: the measurement
run of §4.3.1 drove **5.762 s** corners and the steer reading stayed
inside `steer_tol_rad` for **5.11–5.17 s** of each, so 1.0 s of slew-in
and 0.3 s of exit leave 3.81–3.87 s and **`analyse` refused that square
outright** — "4 corner(s) were found at −1.250000 rad and none of them
kept 6s". The refusal was correct and it
named the three constants that owned it. The value is now 3 s, with the
measured held-stretch lengths written beside it, and `corner_creep`'s own
window is untouched because a minimum is not a cap.

### 6.2 A bench that measured a wall

`slip_bench.sh` drives the traction terminal from wherever the truck
happens to be standing. Run straight after a `corner_creep` recording it
reported **35.42935 % forward and 0.95920 % astern**, and only the second
of those is a slip figure. `corner_creep` leaves the truck 2.58 m from the
spawn pointing back the way it came, so the bench's forward segment drove
it west up the corridor: its raw capture
(`/tmp/m5v3_slip_20260826-064238/forward.joint.json`) ends with base_link
frozen at **x = −22.125001**, zero twist, while `drive_wheel_joint` keeps
turning at −5.833333 rad/s. The model's fork tips reach x = −1.875 in
base_link and the truck is at yaw 0, so the tips are at world **−24.000**
— which is `warehouse_ver3.sdf`'s `WallWest` inner face to the
micrometre. The astern segment then drove away from the wall and read
correctly.

**Every bench figure in §4.2 and in the ladder is from a fresh
`start --headless` with the truck at the spawn pose**, which is the cycle
`EVIDENCE_MODEL_V3.md` §7 already specified and this gate re-learned. The
signature is an asymmetry between the two segments, and it is visible
because the bench measures both and prints both — a bench that averaged
them would have reported 18 % and looked like a plant that had gone
wrong.

---

## 7. Parked: the model's centre of mass may be 3.1 mm behind where two files say

**Not acted on. Recorded with the arithmetic so the gate that owns the
mass distribution can act on it.**

`base_link` and `mast` each carry an `<inertial><pose>` that repeats their
own `<link><pose>` — `0.10 0 0.55` and `-0.78 0 1.05` respectively, in
both elements. SDFormat defines `<inertial><pose>` **relative to the link
frame**, so the two compose rather than one replacing the other, and the
centre of mass gz uses is not the one obtained by summing link poses
alone. Summing the composed poses over all sixteen links:

```
  link poses only  (EVIDENCE_MODEL_V3.md 7.1)   sum(m x) -97.151   com x -0.083323
  composed poses                                sum(m x) -100.751  com x -0.086411
```

which through the same static beam gives

```
  N_drive     4537.4 N  ->  4503.8 N      (-0.74 %)
  N_rear_each 3448.3 N  ->  3465.1 N      (+0.49 %)
```

**Why this gate did not change it.** Three reasons, in order of weight.
The masses and inertial poses are out of scope by constraint 12 and this
is a defect in one of them, not in a WheelSlip parameter. The plan
directed the rear derivation to come from *the model's own
mass-distribution comment*, which is the link-pose sum, and a rear wheel
derived by a different method from the drive wheel beside it would be two
opinions about one vehicle. And `wheel_normal_force` enters the compliance
linearly — 0.74 % of a normal force is 0.74 % of a compliance, which on a
0.956 % slip is **0.007 percentage points**, well inside the 0.5–2 % band
and three times the figure's own run-to-run repeatability.

**What acting on it would mean**, for whoever does: `EVIDENCE_MODEL_V3.md`
§7's whole longitudinal ladder was measured at 4537.4 N, so correcting the
constant means re-driving that table, not editing its rows. And the
duplication itself is the larger question — it also puts `base_link`'s
centre of mass at z = 1.10 m and the mast's at z = 2.10 m, which is a
statement about this truck's roll behaviour that nothing on this track has
measured.

---

## 8. What this gate did not do

- **It did not chase the friction-direction mechanism.** §3.3 measures
  that isotropic contacts remove the heading dependence at π/4 and reduce
  it by a third at −1.25 rad; it does not read gz's contact solver, and
  `EVIDENCE_SENSORS.md` §4.2's candidate stays a candidate.
- **It did not touch the estimator.** `nodes/wheel_odom_core.py` is
  unchanged and gains no scrub term. Its errors got smaller because the
  vehicle stopped scrubbing, which is the only honest way for them to.
- **It did not re-open F1's three parked residuals**, the EKF, Nav2, or
  the mass distribution (§7).
- **It did not re-drive `aisle`.** Nothing about a dead-straight
  out-and-back is a lateral manoeuvre, and §4.4 re-measures the straight
  path this gate could plausibly have moved.
- **It drove one square.** `corner_creep` was run three times on the
  accepted plant and repeats to six decimals; `square` and `straight` are
  one run each on it, and that is stated rather than implied.
