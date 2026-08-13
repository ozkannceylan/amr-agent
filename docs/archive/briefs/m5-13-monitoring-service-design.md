# m5-13 — the read-only monitoring service: design

    gate:                M5 (criterion (e) — the real-time map)
    agent:               agv-ros2   (design only; the build follows)
    goal:                A design for the service that carries map, pose and obstacles to the operator, read-only by more than good intentions, and shaped now so HMI v2b and v3 do not have to undo it.
    invariants_touched:  none expected — invariants 1, 6 and 11 all press on this
    inputs:
      - docs/adr/0011-sensored-autonomy-architecture.md **D4** — the monitoring plane: no write endpoint, no publisher
      - docs/adr/0016-per-vehicle-compute-and-deployment.md — **D3c especially**; the plane must reach into per-vehicle domains
      - hmi/V3-PLAN.md **§2** — the five constraints this brief must carry, and why they get expensive later
      - docs/reports/m5-30-hmi-v3-plan.md
      - docs/roadmap.md criterion (e), and the M6 row (four vehicles)
      - docs/reports/m5-judge-architecture-review.md — finding 6, the enforcement question
      - hmi/V2A-DESIGN.md and the built hmi/ — v2b extends this page
      - agv/forklift/vehicles/allocation.yaml, scripts/vehicle_identity.py
      - CLAUDE.md §3 (the topology draws this edge) and §10
      - docs/LESSONS.md
    deliverable:         the design document and docs/reports/m5-13-monitoring-service-design.md
    done_when:           The directory question is ruled with the ADR 0005 test applied, the enforcement question is answered rather than deferred, and all five V3-PLAN §2 constraints are carried with the design saying where each one shows up.
    forbidden:
      - writing code — this brief produces a design
      - adding a dependency without proposing it and waiting (CLAUDE.md §10). `domain_bridge` in particular is a **new dependency**; the v3 plan already found camera load favours a multi-context process over its fixed forwarded set, so design to that and record `domain_bridge` as the rejected alternative with its reason
      - any write path, publisher, service server or action server on the vehicle side — D4 is not a preference
      - designing HMI v2b's page; this is the service it will read
      - touching `plc/`, `bridge/` or `hmi/`

---

## 1. Two questions this brief must answer, not defer

**Where does it live?** ADR 0011 D4 recommends `agv/` and does not rule it;
`viz/` is the alternative and the standing question names the ADR 0005 test —
*a component that cannot live inside a layer without weakening that layer's
boundary is its own layer.* Apply the test properly: this service is not the
vehicle, it reads several vehicles, and it serves the operator. Say what
`agv/README.md`'s "This layer must not access" section would have to become if
it lived there, and rule on the answer.

**Is it read-only by construction or only by source code?** The judge's finding
6 is blunt: today the phrase is a property of how the code happens to be
written, not something enforced at runtime. Decide — real enforcement (SROS2 or
DDS permissions) or the limitation recorded as a limitation. **Do not let the
phrase stand unqualified either way.** If enforcement costs a dependency or a
key-management story the project does not want, say that plainly and record the
limitation with what would remove it.

## 2. The five constraints from V3-PLAN §2 — carry every one

They are time-critical precisely because this brief is where they are free:

1. a **serialNumber-rooted per-vehicle namespace even at n = 1** — retrofitting
   one at four vehicles is the expensive version;
2. **the whole map**, not a crop around the vehicle;
3. **no bulk pixels on the JSON poll**;
4. the **D3c mechanism chosen knowing camera load is coming** — which is what
   argues for a multi-context process;
5. **camera selection implementable as subscription lifecycle only.**

Say for each where it appears in your design. A constraint carried in prose and
not in the design is not carried.

## 3. What it must deliver for criterion (e)

The M5 row requires the HMI to show *"a real-time map with live obstacles"*. So
the service supplies: the map, the vehicle's live pose on it, and obstacles —
for **n vehicles**, since M6 puts four against ten stations and ADR 0016 gives
each its own DDS domain.

Say what the operator-side interface is, concretely enough that HMI v2b can be
briefed from it without a second design decision.

## 4. Invariants that press here

- **D4**: no write endpoint, no publisher. Say how the design makes that
  structurally true rather than merely absent.
- **Invariant 11**: CLAUDE.md §3 draws this edge as circle-ended and one-way.
  If your design implies an edge the diagram does not draw, say so rather than
  relying on it — there is already an open topology gap about `bridge/`.
- **Invariant 10**: the operator page must not recompute a datum some layer
  already owns. Say which values are forwarded and which are forbidden to
  derive.

## 5. Working discipline

- Read `docs/LESSONS.md` first.
- **Write the design as it settles**, not in one pass.
- Nothing heavy — this is design. Cheap probes are fine; say what you ran.
- **Do not commit.** The orchestrator commits by pathspec.
- Prefer a short document and a diagram over prose (CLAUDE.md §10).
