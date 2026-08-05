# m5-29 — HMI v2a review: can M5 continue, and can M5 finish?

    gate:                M5
    agent:               verifier   (read-only; adversarial, but the second half is constructive)
    goal:                Answer two questions about HMI v2a — is it sound enough for the rest of M5 to be built on it, and can M5 actually be finished with it — and where the answer is no, produce the plan that fixes it.
    invariants_touched:  none — this brief reads
    inputs:
      - hmi/V2A-DESIGN.md and hmi/EVIDENCE_HMI.md (especially the new §I.3 and §I.5)
      - hmi/ — the built v2a: hmi_server.py, static/index.html, the configs, tools/
      - docs/reports/m5-27-hmi-v2a-design.md and m5-28-hmi-v2a-build.md
      - docs/roadmap.md — the M5 row, **criterion (e)** word for word
      - docs/reports/m5-23-judge-review.md — Part B's ordered sequence, steps 6, 7, 9, 10
      - docs/interfaces/opcua-nodes.md §12, plc/forklift/SPEC.md §14
      - docs/adr/0010 D6(b), docs/adr/0011 D4
      - docs/LESSONS.md
    deliverable:         docs/reports/m5-29-hmi-v2a-review.md
    done_when:           Both questions in §1 are answered with a verdict, every blocking finding carries a concrete fix, and the fixes are ordered so a coding agent can execute them without a further decision.
    forbidden:
      - writing anything except the report — you are read-only, and you do not implement
      - designing v3 — that is the next brief; see §3 for the one thing you DO say about it
      - accepting a report's summary as evidence; open the artifact
      - inventing work to justify a finding; "this is sound, continue" is the most useful answer you can give if it is true

---

## 1. The two questions, and they are different

**Q1 — Is v2a sound enough to build the rest of M5 on?**
The things that come next are m5-13 (the monitoring service), HMI v2b (the live
map), the bridge extension, and the first end-to-end run. Does v2a's structure
support those, or has it made one of them harder than it needed to be? Look at
the backend's shape, the node allowlist, the page's state handling, and the
double arrangement.

**Q2 — Can M5 actually be finished with it?**
Read **criterion (e) word for word** and check v2a against it clause by clause.
State per clause: met, not met, or not yet attempted. Criterion (e) requires a
real-time map with live obstacles — that is v2b and it is **inside** M5 by owner
ruling of 2026-08-05, so "not yet attempted" is the correct answer there, not
"missing". What you are looking for is anything that would make a clause
**unreachable** rather than merely unbuilt.

Where either answer is no, **the fix is planned here and applied before M5
continues.** Order the fixes, say which are blocking and which are not, and make
each one small enough to execute without a second design decision. You do not
implement them; an opus agent does, from your plan.

## 2. Specific things to attack

1. **The three superseded M4 configs.** m5-28 made the eight-node write set
   required, so three M4-era configs naming six nodes are now refused and four
   harnesses in `hmi/tools/` cannot run. Is that acceptable as-is, a thing to fix
   now, or a thing that quietly breaks a procedure someone will follow later?
2. **`hmi/config.yaml` will fail at connect against today's CPU by design.** Is
   that failure legible to whoever hits it, or does it look like a defect?
3. **The standing-control decision.** The stop boots ENGAGED and the page adopts
   backend state on load. Walk the reload, the second browser tab, and two
   operators. Does anything release a control that should not be released?
4. **The adopt-window evidence.** m5-28 says it drove 1.2 s per stage in two
   stages and sampled inside both. Open the evidence and check that the sample
   really is inside the window and that the rendering is shown *clearing*, not
   only appearing.
5. **The UNAVAILABLE rendering under all three causes.** Session down, write
   cycle failing, `HmiLinkOk` false. Confirm all three are actually independent
   in the code, not one condition wearing three names.
6. **Anything in v2a that contradicts the design** it was built from.

## 3. The owner's v3 feedback — context, not scope

The owner has reviewed the screenshots and asked for, in a later version: the
teleop joystick shown **only** in teleop mode; a real-time warehouse map with the
vehicle's live position, RViz-grade; every piece of vehicle information reachable
from this page; and selectable live camera views from the vehicle.

**You do not design any of that.** The next brief does. Your one job with it is
to answer: **does v2a's structure foreclose any of it?** If v2a has made a choice
that would have to be undone to get there — a layout that cannot grow, a state
model that assumes one panel, a polling design that cannot carry video — say so
now, while it is cheap. If it does not foreclose them, say that plainly too.

Note that the map half of the owner's request is already M5's v2b and is not a
v3 item; the owner ruled on 2026-08-05 that v2b stays inside M5 and only the
beyond-criterion parts go to v3.

## 4. Working discipline

- Read `docs/LESSONS.md` first.
- Write findings into the report as they land.
- Nothing heavy — no long simulator runs. Cheap probes are fine; say what you ran.
- **Do not commit.** The orchestrator commits.
- Rank findings by severity and say plainly which block M5 continuing.
