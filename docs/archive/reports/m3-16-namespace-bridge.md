# Report — m3-16 namespace bridge

brief:               docs/briefs/m3-16-namespace-bridge.md
status:              done

files_changed:
  - bridge/config/bridge.yaml — `opcua.namespace_uri` is now `http://DemoCell`,
    with a comment stating the TIA derivation and citing ADR 0006.
  - bridge/test_double/plc_test_double.py — `NAMESPACE_URI` constant, and the
    module docstring's URI statement (line 9), both now `http://DemoCell`.
  - bridge/tools/check_write_allowlist.py — `NAMESPACE` constant now
    `http://DemoCell`.
  - bridge/test_double/README.md — URI statement updated and a paragraph added
    saying why the URI is tool-derived, citing ADR 0006.

invariants_touched:  none

Nothing outside `bridge/` was written. Evidence files
(`EVIDENCE_LATENCY.md`, `EVIDENCE_SIGNAL_LOSS.md`, `evidence/`) are
byte-identical: `git diff` against those paths is empty. They still read
`urn:amr-agent:cell:plc` in three places in `EVIDENCE_LATENCY.md` (§ table row,
and two quoted log lines), which is correct — they record runs made against the
old URI and are history.

## No logic moved

The diff is four string literals plus comments. No control flow, no condition,
no branch, no call and no ordering changed anywhere; `git diff -- bridge/` shows
only the changed lines and added comment lines. The namespace index is still
resolved by browsing at every session establishment
(`opcua_side._connect` → `client.get_namespace_index`), and no index is
hardcoded anywhere.

## Live verification

One bounded foreground run, WSL2 Ubuntu 24.04 on the owner's machine, venv
`/home/ozkan/amr-bridge-venv`, `ROS_DOMAIN_ID=91` and
`GZ_PARTITION=m316nsbridge` isolated. The cell was **not** started: namespace
resolution needs only double + bridge, and the six `/cell/*` topics were driven
by plain `ros2 topic pub` so the startup rule could also be observed. All
processes were reaped by the script; `pgrep` reports none left and port 4840 is
free.

Double registers the URI:

```
2026-07-27 16:32:39,151 INFO    plc-double namespace http://DemoCell registered at index 2
```

Bridge resolves it by browsing, and the startup rule is satisfied:

```
2026-07-27 16:32:44,060 INFO    bridge.opcua namespace http://DemoCell resolved to index 2
2026-07-27 16:32:44,069 INFO    bridge.opcua all node DataTypes match opcua-nodes.md §9
2026-07-27 16:32:44,069 INFO    bridge.opcua session established, 15 nodes resolved
2026-07-27 16:32:44,070 INFO    bridge.opcua heartbeat withheld: no real sample yet for ConveyorBeltPosition, ConveyorBeltSpeed, ProductSensorRange, PanelStartPressed, PanelResetPressed, PanelStopCircuitClosed, PanelProcessStopCircuitClosed (startup rule R3)
2026-07-27 16:32:46,623 INFO    bridge.opcua startup rule satisfied: all 7 DemoCell/Input nodes carry a real cell sample; heartbeat begins advancing at 1
```

Bridge exit code 0 after `--duration 20`.

Allowlist check against the same double:

```
RESULT: PASS
```
(exit code 0; five client-side `WriteNotPermitted` refusals and five
server-side `BadUserAccessDenied` refusals, all `ok`.)

The index resolved to 2 here, the same value the old URI happened to resolve
to. That is a property of this double's registration order, not of the URI, and
nothing reads it as a constant.

open_questions:
  - **Scope deviation, recorded so the owner sees it.** The owner's instruction
    was "config only, no code change". The orchestrator widened it to four
    files and this agent implemented the widened scope. Reason: the test double
    and the allowlist tool each carry the URI as a module constant, and a
    yaml-only change would have broken the committed loop at connect — the
    bridge would have browsed for `http://DemoCell` against a double still
    registering `urn:amr-agent:cell:plc` and failed with "namespace not found".
    The double must mirror the real server for the loop to close at all. The
    three code files carry no logic change; the constants are contract
    representation. The owner may still wish to confirm the widened scope.
  - The brief named the `NAMESPACE_URI` constant in `plc_test_double.py`; an
    independent search found the same URI a second time in that file's module
    docstring (line 9). It was updated too, since leaving it would have made the
    file contradict its own constant. Flagged because it is one occurrence
    beyond the brief's enumerated list.
  - `docs/interfaces/opcua-nodes.md` §2 and `plc/demo-cell/SPEC.md` are outside
    this agent's write access and, as far as this agent can see, still specify
    the old URN that ADR 0006 supersedes. They need their own briefs to the
    `interface` and `plc` agents; `bridge/` and those documents now disagree
    until that happens.
  - No scope note was added to any evidence file. If the owner wants the
    evidence files to say out loud that their runs predate ADR 0006, that is a
    one-line addition to `EVIDENCE_LATENCY.md` and should be its own brief
    rather than an edit smuggled into this one.

next_suggested:      Brief the interface and plc agents to bring opcua-nodes.md §2 and plc/demo-cell/SPEC.md onto http://DemoCell, so no document still specifies the superseded URN.

## lessons_candidates

- 2026-07-27 | Scoped a namespace-URI correction as "config only" | The test
  double and the allowlist tool each carry the URI as a module constant, so a
  yaml-only change would have broken the loop at connect with "namespace not
  found" | A contract value is changed everywhere its stand-ins reproduce it;
  when a config key has a mirror in a test double, the double is part of the
  same change, not a follow-up
- 2026-07-27 | Verified a namespace change would be visible in the bridge log
  alone | The startup rule also had to fire to prove the loop still closes, and
  that needs all seven inputs carrying real samples, which the double cannot
  provide | Six `ros2 topic pub` publishers substitute for the whole Gazebo cell
  when the thing under test is the OPC UA side; reach for the cell only when the
  physics is what is being proven
