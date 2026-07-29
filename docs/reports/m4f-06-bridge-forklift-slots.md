# Report m4f-06 — bridge implementation: forklift slots

```
brief:               docs/briefs/m4f-06-bridge-forklift-slots.md
status:              done
invariants_touched:  none
```

## files_changed

| File | What |
|---|---|
| `bridge/amr_bridge/config.py` | the **signal-group model** of `bridge-design.md` §2.1: group definitions transcribed from `opcua-nodes.md` §9/§10, a `groups:` declaration in the config, and `Config.write_allowlist` **derived** from the configured groups. Rejects a config that names an `Hmi` node in any position, or a group table for a group the run does not carry |
| `bridge/amr_bridge/opcua_side.py` | every count now comes from the configured set: the allowlist at the single write helper, R3's "every input", the reconnect refresh and the restart rewrite. Four output slots read and published in one cycle phase. Log lines worded per configured set instead of naming `DemoCell/Input` |
| `bridge/amr_bridge/ros_side.py` | per-group subscriptions and one publisher per output slot; `PlantInterface` replaces `CellInterface`; callbacks renamed `cb_*`; non-finite logging generalised to every Real |
| `bridge/amr_bridge/main.py`, `slots.py`, `instrumentation.py`, `__init__.py` | slots built from `cfg.input_keys`; the run logs and records its configured set; `nonfinite_range_samples` → `nonfinite_real_samples` |
| `bridge/config/bridge.yaml` | restructured for groups. **Still cell-only and still the PLCSIM endpoint**: the `Forklift/` subtree is a design value until the owner's TIA read-back (`opcua-nodes.md` §10.2 step 6), so the commissioned config must not browse for it yet |
| `bridge/config/bridge-double-both.yaml`, `bridge-double-forklift.yaml` | new — the other two configurations §2.1 admits, against the double (ports 4842/4843) |
| `bridge/test_double/plc_test_double.py` (+ `README.md`) | serves all **33** nodes including the `Forklift/` subtree; the five `Hmi/` requests and `HmiHeartbeat` are served **writable**, `Output/`+`Status/` read-only; S1 drives any `Output/` node by name; S5 reverts the forklift nodes too; the observation log carries both groups and the `Hmi/` columns |
| `bridge/tools/check_write_allowlist.py` | rewritten: the allowlist is read from all three configurations, 16 keys are refused client-side, and the **HMI negative test** writes the six nodes from an independent client to show the server *accepts* them — then restores them |
| `bridge/tools/check_forklift_slots.py` | new harness: runs the real bridge as a child process against its own doubles, publishes the plant topics, drives the setpoints, and checks every claim of the brief |
| `bridge/tools/check_connect_conformance.py`, `check_session_lifecycle.py` | updated for the new API; node count and rewrite count derived from the config instead of literals |
| `bridge/README.md`, `EVIDENCE_CONNECT.md`, `EVIDENCE_LATENCY.md`, `EVIDENCE_LIFECYCLE.md`, `evidence/*2026-07-29*` | the dated capture, the archived run artefacts, and the two design requests below |

## The recorded run — 2026-07-29, test double, WSL2, `ROS_DOMAIN_ID=61`

`EVIDENCE_CONNECT.md` § m4f-06 carries it with the figures quoted as printed.
No PLCSIM endpoint was contacted; both double configs name loopback and the
harness refuses a `192.168.*` one.

| Run | Result |
|---|---|
| `check_forklift_slots.py` (both groups, then forklift-only) | **46 checks, 46 passed** |
| `check_write_allowlist.py` (HMI negative test) | **39 checks, 39 passed** |
| `check_connect_conformance.py`, unmodified `bridge.yaml` | **PASS** — 15 nodes, group `cell` |
| `check_session_lifecycle.py`, unmodified `bridge.yaml` | **PASS** — rewrite `7/7` |

Each done_when item, and where it is met: every forklift input slot carries a ROS
value into its node and follows it to a second value, the field bit **uninverted
both ways** (§ m4f-06.2); all four output slots republish node changes to their
topics, arriving within 1.3 ms of each other (§ m4f-06.3); the restart rewrite
reads **`11 of 11`** out of the bridge's log and **`11/11`** out of its evidence
file (§ m4f-06.4); the HMI group is refused by the bridge against a server that
accepts the same write from another client, and never moved on the server
(§ m4f-06.5); the cell harnesses pass on the unmodified config (§ m4f-06.7); the
evidence stems still produce one file per session. A forklift-only run reaches
its heartbeat on **four** inputs having subscribed to no `/cell/*` topic, and
touches **13** nodes — §2.1's table, with the shared heartbeat.

## open_questions

1. **`docs/interfaces/bridge-design.md` §8.1 *Restart residual* understates the
   residual — requested correction, not implemented.** The row admits only the
   revert that lands on the value this session last wrote ("one in 65536"). The
   real blind spot is a **window of the cycle**: a revert landing between the
   step-0 read-back and the step-4 heartbeat write is erased by that write, so
   the next read-back compares equal. Measured from the committed CSV:
   **5.255 ms median of a 50.015 ms cycle, ~10 %**, and one masked revert left an
   open stop circuit and an obstacle bit standing for **4.0 s** under an
   advancing heartbeat. It is **not** a forklift property — the cell-only
   lifecycle harness reproduced it the same morning on the unmodified config, and
   it is present in the m3-35 code as shipped. Not patched here: §8.1 itself
   rules that closing it needs a second witness and a second witness needs an
   owner, and a fix would change a cycle shape the design specifies. Both restart
   harnesses now trigger reverts until one is caught and report how many were
   masked, so the property is measured rather than flaked over.
2. **The commissioned config stays cell-only, by choice.** `bridge/config/bridge.yaml`
   does not carry the forklift group, because a run against PLCSIM would then
   browse for a subtree that is a design value until `opcua-nodes.md` §10.2 step 6
   is executed. Adding `groups: ["cell", "forklift"]` and the forklift tables is a
   one-file edit **after** the owner's read-back; nothing else changes.
3. **`docs/interfaces/bridge-design.md` §12 item 11 can be closed** (the
   configured-signal-set model is implemented and recorded) and **item 13's
   requesting half is marked satisfied in `bridge/EVIDENCE_LATENCY.md`**, with the
   correction of (1) requested back. **Item 14's bridge half is confirmed** in
   `EVIDENCE_LIFECYCLE.md` §1.2: `BridgeHeartbeat` is still the only node outside
   an `Input/` folder the bridge writes, and still a valid witness because the
   HMI's counter is a node the bridge never touches. `docs/interfaces/` is not
   mine to edit.
4. **One counter was renamed**: `nonfinite_range_samples` → `nonfinite_real_samples`,
   because the rule is now the same for every Real of every group and a per-signal
   counter would have become a second list to maintain. The per-signal detail
   stays in the CSV's `nonfinite` rows. Older evidence files carry the old name.
5. **No new dependency**, none requested. Four more subscriptions, three more
   publications and eleven more nodes, all on message and value types the bridge
   already carried — §2.1 G4 held.
6. **For `docs/LESSONS.md`, if the orchestrator agrees**: the rclpy shadowing
   lesson is not only about callbacks. `rclpy.node.Node` owns `self._publishers`
   as a **list**, so a dict assigned to that attribute broke `create_publisher`
   on its own next call — the same trap as `_clock`, one attribute over. The
   bridge's are `_out_pubs` / `_out_topics`.

## next_suggested

Re-run `check_forklift_slots.py` unchanged after the owner's TIA read-back of the
`Forklift/` subtree, with `bridge.yaml` carrying both groups against PLCSIM.
