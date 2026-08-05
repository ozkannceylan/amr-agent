# m5-12 — protective and warning field evaluation: the design

    gate:                M5 (criteria (a) and (b))
    agent:               agv-ros2   (design only; the build follows)
    goal:                A design for turning the two safety scanners' data into protective and warning field verdicts, with the field geometry DERIVED from stopping distance rather than chosen, and the output shaped as OSSD-equivalent channel pairs.
    invariants_touched:  none expected — invariant 1 is what the OSSD shape exists to respect
    inputs:
      - plc/forklift-safety/SPEC.md §7 — **the consumer.** The stand-in writer's zone channel eats your output; its rate and failure behaviour are already specified there
      - docs/roadmap.md criterion (a) — "a protective-field intrusion in Gazebo trips an F-latched stop"
      - agv/forklift/EVIDENCE_SENSOR_COVERAGE.md — the two 275° diagonal scanners, the measured coverage, **R3 and R8**
      - agv/forklift/EVIDENCE_SENSOR_TF.md and m5-06's measurement/safe channel split
      - agv/forklift/EVIDENCE_ENVELOPE.md — the measured stop: 0.850 s and 0.1738 m from 0.40 m/s on a 0.50 m/s² ramp
      - agv/forklift/config.yaml and model.sdf — the vehicle's speed limits and footprint
      - docs/safety/ — the SRS functions this serves, and PL-SCENARIOS
      - docs/adr/0011 D5 — the claim boundary
      - docs/LESSONS.md
    deliverable:         agv/forklift/FIELD-EVALUATION.md and docs/reports/m5-12-field-evaluation-design.md
    done_when:           Every field boundary is a number with a derivation behind it; the OSSD-equivalent contract is specified precisely enough to implement; and the failure behaviour is specified for each way the input can fail, not only for sensor death.
    forbidden:
      - choosing a field size — derive it, and show the arithmetic (see §2)
      - claiming or implying an achieved PL, Category, SIL or PFH; ADR 0011 D5 permits PLr **targets** only
      - designing the writer that consumes this — `plc/forklift-safety/SPEC.md` §7 already specifies it
      - writing code — this brief produces a design document
      - treating a beyond-range return as missing data (LESSONS 2026-07-29: it is a measurement, "clear to range_max")
      - re-deriving the measured numbers in docs/TODO.md; quote them

---

## 1. What this is

The safety scanners see the world. Something must decide **"there is something in
the protective field"** and hand that verdict, as a safety-shaped signal, to the
stand-in writer, which puts it in front of the F-program. This is the piece that
makes criterion (a)'s chain **originate in Gazebo** rather than in a script.

Two fields, as a real installation has them:

- **protective field** — intrusion stops the vehicle;
- **warning field** — intrusion warns, larger, and does not stop.

## 2. Derive the geometry — this is the heart of the brief

A protective field is not a shape somebody liked. Its depth is what the vehicle
needs in order to stop before reaching the intruder. Write the derivation out:

```
depth  =  stopping distance
        + distance travelled during the total response time
        + any allowance the standard asks for
```

You have measurements for most of it already: the gate's stop is **0.850 s and
0.1738 m from 0.40 m/s** on its own 0.50 m/s² ramp; the vehicle's speed ceiling
lives in `config.yaml`. The response chain is longer than the ramp, though —
scan period, evaluation, the writer's republish period, the F-OB cycle at
**100 ms**, and the reaction. **Add them up explicitly**, each with its source.

Consult **ISO 13855** for how the calculation is properly framed (approach
speeds and the positioning of safeguards). Cite it with the clause; if the
project has no access to the text, say what you used instead and mark the
derivation provisional rather than inventing a coefficient.

**Then answer the question that decides the design:** at full speed, does the
required depth fit in front of this vehicle given the measured scanner coverage,
R3 and R8? If it does not, the honest answers are a **speed-dependent field set**
(what real scanners do) or a lower speed ceiling — say which, and show the speed
at which the geometry closes.

## 3. The OSSD-equivalent contract

Real safety scanners present a pair of outputs, both driven, both read, so that a
single failure is detectable. Specify the equivalent here: what the pair is, what
each channel carries, what "both agree" means, what a discrepancy means, and how
long a discrepancy may last before it is a fault.

The **safe direction is the demanding one**: unknown means intrusion. Say that
explicitly for every failure mode you list.

## 4. Failure behaviour, per failure — not one paragraph for all of them

List them separately and give each its own verdict:

1. scanner publishes nothing (dead);
2. scanner publishes, all returns beyond range (**an empty horizon is a
   measurement, not missing data** — LESSONS 2026-07-29, and this exact mistake
   already latched a false stop in open space);
3. scan is stale but arriving;
4. one scanner of the pair fails, the other is healthy;
5. values outside the physical window (NaN, inf, negative).

Write validity **affirmatively** — `valid := (low < x) AND (x < high)` with the
fault in the ELSE (LESSONS 2026-07-27).

## 5. What it must fit

- **R3 and R8** are inherited as field-geometry constraints, not as things to
  design around quietly. R8 is a measured rear self-occlusion band accepted as a
  residual. Say what each does to the achievable field, and whether it leaves a
  gap a person could stand in.
- **The consumer's rate.** `plc/forklift-safety/SPEC.md` §7 says the writer
  republishes every 50 ms over a named WSL→Windows link. Your output must suit
  that; if it cannot, say so now, because the spec is written and changing it is
  a round trip.
- **The measurement / safe channel split** from m5-06 — this evaluation belongs
  on the safe channel, and the design says why that matters.

## 6. The plan

Close with a short phased plan for the build: one observable done-condition per
phase, files touched, does-NOT list. Phase 1 should be the smallest thing that
puts a real intrusion verdict on a topic, because that is what unblocks the
writer and criterion (a).

## 7. Working discipline

- Read `docs/LESSONS.md` first.
- **Write the design as it settles**, not in one pass.
- Nothing heavy — another agent may hold the simulator. If you need a
  measurement the repository lacks, name it rather than estimating it.
- **Do not commit.** The orchestrator commits by pathspec.
