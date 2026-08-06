# m5-43 — restate AT-02, AT-03 and AT-04 against M5's scope

    gate:                M5 (criterion (d)); unblocks every acceptance test
    agent:               safety-spec
    goal:                The three acceptance tests criterion (d) names become executable at M5 — against the observables this gate actually has — without becoming tests the work cannot fail.
    invariants_touched:  none expected — invariant 1 and ADR 0011 D5 both press here
    inputs:
      - docs/reports/m5-42-autonomy-stack-review.md — **the finding you are resolving.** Its AT sections are specific; do not re-derive them, verify them
      - docs/safety/ — the SRS in full, **AT-02, AT-03 and AT-04 verbatim**, SF-01, SF-03, SF-07, and **B4**
      - docs/roadmap.md criterion (d)
      - plc/forklift-safety/SPEC.md §1 (which SF each demand is), §7, §9 T6
      - agv/forklift/FIELD-EVALUATION.md and EVIDENCE_FIELD_EVALUATION.md — what the intrusion actually drives today
      - bridge/standin_writer/EVIDENCE_BUILD.md and docs/reports/m5-41-writer-run.md — **the consumer-view instrument**, which is why running these is now agent work
      - docs/interfaces/vda5050-subset.md and opcua-nodes.md §12
      - docs/adr/0011 D5 — the claim boundary
      - docs/LESSONS.md
    deliverable:         the restated acceptance tests in docs/safety/, and docs/reports/m5-43-at-semantics.md
    done_when:           Each of AT-02, AT-03 and AT-04 is executable against something that exists at M5, each states what would make it FAIL, and every descoped element is named with the gate it moves to rather than deleted.
    forbidden:
      - writing a test the work cannot fail — that is the failure mode here, and it is the same one criterion (a) was rescued from
      - claiming or implying an achieved PL, Category, SIL or PFH; ADR 0011 D5 permits PLr **targets** only
      - inventing an observable — if a test needs one that does not exist, either name the existing one that stands in or descope the clause and say where it lands
      - making the cell e-stop stop a vehicle. SRS **B4** forbids it and this brief does not get to weaken that
      - editing outside `docs/safety/` — an ADR or a roadmap change is **requested** in your report
      - deleting a requirement to make a test pass; descoping is explicit and dated, deletion is not

---

## 1. The five problems, verified then resolved

m5-42 read the tests rather than assuming them. Verify each, then rule:

1. **AT-02 asserts a vehicle e-stop channel that does not exist.** The
   F-program's only e-stop channel is **SF-01, the cell e-stop**, and SRS **B4**
   plus SF-01's own safe-state row say it has **no path to any vehicle**. So the
   test as written asks for something the architecture forbids. Say what AT-02
   tests **at M5** instead — and if the honest answer is that the vehicle e-stop
   is an M6 or M7 subject, say that and land it there.
2. **AT-02/03/04 demand VDA 5050 `safetyState` / `state` observables that
   nothing at M5 produces.** Name the M5 observables that stand in — the
   `Forklift/Safety/` mirror nodes and the vehicle-side topics are the
   candidates — and say for each which VDA 5050 field it will become at M6, so
   the restatement is a **staging post and not a fork**.
3. **AT-03(b)'s 2 s auto-release contradicts what is built.** SRS SF-03's
   inhibit release is automatic after 2 s clear — the SRS's one documented
   exception to no-auto-resume — but the channel the intrusion actually drives
   is `ZoneStopDemand`, which is the **SF-07 latched pattern**. One of those two
   is what M5 demonstrates. Rule which, and say plainly what happens to the
   other.
4. **AT-03(c) needs a bumper the model does not have.** Descope it with its
   landing gate, or say what stands in. Do not quietly drop it.
5. **AT-03(d) and AT-04 need field-evaluation phases 2–3 and an SLS / creep
   enforcer that is designed nowhere.** Say what M5 can demonstrate of them now,
   what it cannot, and where the remainder lands.

## 2. The rule that governs the restatement

**A restated test must still be failable.** The owner has already rescued one
gate criterion from being unfalsifiable; do not spend that lesson. For each
restated test, write the sentence that says **what a failing run looks like**.
If you cannot write that sentence, the test is not a test.

And the restatement is a **narrowing of the instrument, not of the claim**.
AT-03 exists to show that an intrusion stops the vehicle and that recovery is
disciplined. If your restatement no longer shows that, you have descoped the
substance rather than the observable, and that is the owner's call, not yours —
flag it.

## 3. Use the instrument that now exists

m5-41 built and proved a **consumer-view instrument**: the F-block's own
instance data read from a separate process, with an OPC UA witness on the
consequence. That is why the review found these tests are now **agent work
rather than owner work at a watch table** — which is the single most useful
fact in this round. Write the tests so an agent can run them with it.

## 4. What to hand back

- anything needing an ADR or a roadmap edit — **requested**, not made;
- the AT-10 / AT-11 landing question the review raises beside this one;
- any place where a restatement makes another document stale. A conditional
  resolution propagates with its condition attached (LESSONS 2026-07-30).

## 5. Working discipline

- Read `docs/LESSONS.md` first.
- **Write as it settles**, not in one pass.
- Nothing heavy — another agent may hold the simulator.
- **Do not commit.** The orchestrator commits by pathspec.
