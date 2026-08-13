# Report m4f-06b — committed rehearsal config for the forklift loop

```
brief:               docs/briefs/m4f-06b-rehearsal-config.md
status:              done
invariants_touched:  none
```

## files_changed

| File | What |
|---|---|
| `bridge/config/rehearsal-forklift.yaml` | new, and the only file added. Forklift group alone, endpoint `opc.tcp://127.0.0.1:4850` (the PLC logic double), per-session evidence stem `evidence/latency-rehearsal-forklift.csv` |

**No code changed.** `git diff` over `bridge/` is empty; the deliverable is one
config file that the shipped loader already understands.

**`bridge/config/bridge.yaml` is byte-identical**, checked by content hash rather
than by inspection — `git hash-object bridge/config/bridge.yaml` reads
`95958b6f0d00964481dfb2133acabfc088fc672f` before and after, and the file appears
in no diff.

## Validation — the config loader, quoted as printed

```
$ "$VENV/bin/python" -c "import sys; sys.path.insert(0,'bridge')
from amr_bridge import config as c; cfg = c.load('bridge/config/rehearsal-forklift.yaml'); ..."

loaded   /mnt/c/Users/ozkan/projects/amr-agent/bridge/config/rehearsal-forklift.yaml
endpoint opc.tcp://127.0.0.1:4850
session  amr-agent-bridge-rehearsal
configured signal set: forklift — forklift 4in/3out/5diag (opcua-nodes.md §10); 4 input slots, 3 output slots, 5 diagnostics, 13 nodes touched, write allowlist 5 keys
inputs       ('ForkliftForkHeight', 'ForkliftLinearSpeed', 'ForkliftObstacleInStopZone', 'ForkliftObstacleMinDistance')
outputs      {'ForkliftTractionSpeedRef': 'cmd_traction_speed', 'ForkliftSteerAngleRef': 'cmd_steer_angle', 'ForkliftForkSpeedRef': 'cmd_fork_speed'}
diagnostics  ('ForkliftTeleopActive', 'ForkliftObstacleStopActive', 'ForkliftSpeedLimitActive', 'ForkliftResetRequired', 'HmiLinkOk')
allowlist    5 ['BridgeHeartbeat', 'ForkliftForkHeight', 'ForkliftLinearSpeed', 'ForkliftObstacleInStopZone', 'ForkliftObstacleMinDistance']
browse path ForkliftObstacleInStopZone: ServerInterfaces/DemoCell/Forklift/Input/ForkliftObstacleInStopZone
evidence stem /mnt/c/Users/ozkan/projects/amr-agent/bridge/evidence/latency-rehearsal-forklift.csv
per-session   latency-rehearsal-forklift-19700101T000000Z-pid1234.csv
```

The loader is a pure read: it resolves no node and opens no socket, so this
validation neither needed nor contacted the endpoint. Every count is §2.1's
forklift-only row — **13** nodes touched (twelve of §10's eighteen plus the one
shared heartbeat, which is a §9 node every configuration uses) and a **5-key**
allowlist derived from the configured group. The last line is
`session_csv_path` shown with a fixed clock and pid, so per-session evidence
naming is visibly intact: the configured path is a stem and a rehearsal start
cannot truncate an earlier capture.

The header comment states the three things the brief asks for, in the first
block of the file: that it is the **rehearsal** config against a logic double,
that **gate evidence runs on the live `bridge.yaml` against PLCSIM Advanced**,
and that **`bridge.yaml` stays cell-only until the owner's TIA read-back** of the
`Forklift/` subtree.

## open_questions

1. **Not run against anything.** The brief scopes this to loader validation and
   the double on 4850 belongs to a concurrent agent, so no session was opened —
   against that double or anything else, PLCSIM included. What a rehearsal run
   will need from the logic double, stated here because it is an interface
   expectation and not a request to edit another tree: both namespace URIs
   published (`http://www.siemens.com/simatic-s7-opcua` and `http://DemoCell`),
   the `Objects → ServerInterfaces → DemoCell → Forklift/…` browse path, and the
   §10.3 data types and access rights. A missing URI is a connect failure by
   design (§3.1 N4) — the bridge never browses around it, so a double that
   publishes a different shape presents as `NamespaceNotFound` or an
   unresolvable NodeId rather than as a degraded run.
2. **The rehearsal inherits the m4f-06 finding unchanged**: the restart-detection
   residual measured at ~10 % of the cycle
   (`docs/reports/m4f-06-bridge-forklift-slots.md`, open question 1). Nothing in
   this config affects it, and a rehearsal is not the place it gets closed.
3. **Two forklift configs now exist beside each other and are not
   interchangeable**: `bridge-double-forklift.yaml` targets the bridge's own test
   double on 4843 and is what `tools/check_forklift_slots.py` drives;
   `rehearsal-forklift.yaml` targets the PLC logic double on 4850. Same signal
   set, different servers, different evidence stems. If the two ever need to run
   at once, they already differ in port and stem, so neither collides with the
   other.

## next_suggested

After the rehearsal, fold its findings into the PLCSIM run on `bridge.yaml` —
which gains the forklift group only after the owner's TIA read-back.
