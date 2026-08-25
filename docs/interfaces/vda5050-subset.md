# VDA 5050 subset used by this project

Reference document. Defines which parts of VDA 5050 this project uses, traceable
field by field to the official schemas. Anything not listed as "used" is not
consumed and not produced by project code.

## 1. Source of truth

| Item | Value |
|---|---|
| Standard | VDA 5050 — Interface for the communication between AGV and master control |
| Version used | **2.1.0** (git tag `2.1.0`, commit `511d01d`, repo github.com/VDA5050/VDA5050) |
| Retrieved | 2026-07-26, via clone of the official repository |
| Files used | `VDA5050_EN.md`, `json_schemas/{order,state,instantActions,connection,factsheet}.schema` |
| Note | Repo `main` is already version 3.0.0. This project pins the v2 line (`majorVersion` = `v2`) per the M1 brief. Moving to 3.x is an interface change requiring review. |

Every field listed below exists in the referenced 2.1.0 schema files. No field
is invented. Schema section references use the spec's chapter numbers.

## 2. Transport, topics, serialization

Topic structure (spec 6.3, local broker form — mandatory topic names, suggested levels):

```
interfaceName/majorVersion/manufacturer/serialNumber/topic
uagv/v2/<manufacturer>/<serialNumber>/order
```

| Level | Value in this project |
|---|---|
| interfaceName | `uagv` |
| majorVersion | `v2` |
| manufacturer | AGV manufacturer string, set by the agv layer (no `/` or `$`, chars A-Z a-z 0-9 _ . : -) |
| serialNumber | unique per vehicle, same character set |
| topic | `order`, `instantActions`, `state`, `connection`, `factsheet` |

Serialization: JSON, encoded UTF-8 (spec 6.1.2). Booleans are JSON booleans,
enums are UPPERCASE strings, timestamps ISO 8601 UTC `YYYY-MM-DDTHH:mm:ss.ffZ`.

QoS and retain (spec 6.2, 6.14, 6.15):

| Topic | Publisher | Subscriber | QoS | Retained | Notes |
|---|---|---|---|---|---|
| order | fleet manager | AGV | 0 | no | mandatory |
| instantActions | fleet manager | AGV | 0 | no | mandatory |
| state | AGV | fleet manager | 0 | no | event-driven, at latest every 30 s (spec 6.10) |
| connection | AGV / broker (last will) | fleet manager | 1 | **yes** | mandatory, see section 7 |
| factsheet | AGV | fleet manager | 0 | **yes** | published on connect and on `factsheetRequest` |

Topics of the standard **not used**: `visualization` (optional; no consumer in
this project), zone sets via `zoneSetId` (zone reservation is fleet-manager
internal, not expressed through VDA 5050 zone sets).

"Master control" in the spec text is the fleet manager in this project.

## 3. Common message header

Every message on every topic carries these fields (spec 6.4; required in all
five schemas):

| Field | Type | Required | Meaning in this project |
|---|---|---|---|
| headerId | uint32 | yes | Per-topic counter, +1 per sent message |
| timestamp | string (ISO 8601 UTC) | yes | Send time |
| version | string | yes | Full protocol version, `"2.1.0"` |
| manufacturer | string | yes | Matches topic level |
| serialNumber | string | yes | Matches topic level; vehicle identity |

(Factsheet: `headerId`/`timestamp` are optional in `factsheet.schema`; we send them anyway.)

## 4. Topic `order` (fleet manager → AGV)

Source: `order.schema`. Header per section 3, plus:

### Used fields

| Field | Type | Required | Meaning in this project |
|---|---|---|---|
| orderId | string | yes | Transport order identity, assigned by fleet manager |
| orderUpdateId | integer ≥ 0 | yes | Base extension counter, unique per orderId |
| nodes | array of node | yes | Route waypoints; ≥ 1 node for a valid order |
| edges | array of edge | yes | Connections between nodes; empty for single-node order |

node (required per schema: `nodeId`, `sequenceId`, `released`, `actions`):

| Field | Type | Required | Meaning in this project |
|---|---|---|---|
| nodeId | string | yes | Waypoint ID from the warehouse map graph |
| sequenceId | integer ≥ 0 | yes | Position in order, runs across nodes and edges |
| released | boolean | yes | true = base (drive it), false = horizon (plan only) |
| nodePosition | object | no (yes for us) | Target pose; we always send it (AUTONOMOUS vehicle needs goal poses) |
| nodePosition.x, .y | number | yes (in object) | World coordinates on map |
| nodePosition.theta | number, ±π | no | **Not sent** (M6 measured deviation from this table's first cut: the vehicle is AUTONOMOUS and plans its own approach; `order_builder.py` sends x/y/mapId, plus `allowedDeviationXY` on the final node only) |
| nodePosition.allowedDeviationXY | number ≥ 0 | no | Arrival tolerance radius in m |
| nodePosition.allowedDeviationTheta | number, ±π | no | Arrival orientation tolerance |
| nodePosition.mapId | string | yes (in object) | Single warehouse map ID |
| actions | array of action | yes | Station actions on this node; empty array if none |

edge (required per schema: `edgeId`, `sequenceId`, `released`, `startNodeId`, `endNodeId`, `actions`):

| Field | Type | Required | Meaning in this project |
|---|---|---|---|
| edgeId | string | yes | Edge ID from the map graph |
| sequenceId | integer ≥ 0 | yes | Position in order |
| released | boolean | yes | Base/horizon flag, as for nodes |
| startNodeId | string | yes | nodeId of start node |
| endNodeId | string | yes | nodeId of end node |
| maxSpeed | number | no | Speed cap on the edge in m/s (e.g. near stations, door) |
| actions | array of action | yes | Empty array in normal use |

action object (shared definition, `order.schema#/definitions/action`, also used
by instantActions):

| Field | Type | Required | Meaning in this project |
|---|---|---|---|
| actionType | string | yes | One of the actions in section 6 |
| actionId | string | yes | Unique, UUID; keyed against `actionStates` in state |
| blockingType | enum NONE / SOFT / HARD | yes | Per action, see section 6 |
| actionParameters | array of {key, value} | no | Only keys defined by the standard action; extension point (section 9) |
| actionDescription | string | no | Free text, logging only |

### Deliberately omitted (exist in schema, not used)

| Field | Why omitted |
|---|---|
| zoneSetId | No zone sets; traffic and zone reservation are fleet-manager internal |
| node.nodeDescription, edge.edgeDescription, nodePosition.mapDescription | Free-text, no consumer |
| edge.trajectory (NURBS), edge.corridor | Nav2 plans its own path; vehicle is AUTONOMOUS |
| edge.orientation, orientationType, rotationAllowed, maxRotationSpeed | Path shaping for line-guided/constrained vehicles; not needed |
| edge.direction, edge.length | Line-guided vehicle fields |
| edge.maxHeight, minHeight | No height-constrained infrastructure in the cell |

### Recorded deviations — order acceptance (M6, `vda_orders.accept_order`)

Measured against the code 2026-08-25; each is deliberate and the reason is
the code's own comment.

1. **An order update is accepted only when `orderUpdateId` is exactly one
   more than the executing order's.** The spec accepts any greater value
   (a skipped update is a discarded one); this vehicle rejects the jump
   with a named `orderError` instead. Both ends of this cell are this
   project's, the fleet rebuilds from the rejection, and a lost extension
   is retried on the next traffic pass — but a third-party master that
   skips ids will be refused. Interop work item if one ever connects.
2. **A new order (different `orderId`) is rejected while one is
   executing** — `cancelOrder` first, always. The spec's append case
   (new order whose first node is the end of the current base) is not
   implemented; the fleet never sends it.
3. **Superseded the same day by item 3** (see section 6's node-action
   table): an order may now carry exactly one pick or drop on its FINAL
   node; anything else — an action on a waypoint, a second action, an
   unknown type, any edge action — is still rejected by name. The
   original deviation as recorded that morning: node and edge actions
   in orders were rejected wholesale (`node N actions
   unsupported`). The transport's fork cycle is the manager's dwell timer
   for now; pick/drop as node actions is planned work, and this clause is
   where it will land.
4. **A duplicate delivery (same `orderId`, same `orderUpdateId`) is
   ignored silently** — no state change, no error. The spec agrees
   (discard); it is recorded here because silence is otherwise easy to
   misread as loss.

## 5. Topic `state` (AGV → fleet manager)

Source: `state.schema`. Published on the events listed in spec 6.10 and at
latest every 30 s. Header per section 3, plus:

### Used fields

| Field | Type | Required | Meaning in this project |
|---|---|---|---|
| orderId | string | yes | Current/last order; "" if none |
| orderUpdateId | integer | yes | Last accepted update; 0 if none |
| lastNodeId | string | yes | Last reached node; "" if none |
| lastNodeSequenceId | integer | yes | sequenceId of last reached node; 0 if none |
| nodeStates | array | yes | Remaining nodes of the order; empty when idle |
| nodeStates[].nodeId, .sequenceId, .released | string / integer / boolean | yes | As in order |
| edgeStates | array | yes | **Always sent `[]`** (M6 recorded deviation: `nodeStates` alone carries the remaining route; no consumer reads edge occupancy off the wire — the fleet's ledger derives edges itself) |
| edgeStates[].edgeId, .sequenceId, .released | string / integer / boolean | yes | Not produced — see the row above |
| driving | boolean | yes | Vehicle is driving/rotating |
| paused | boolean | no (sent) | **Sent hard-false** — startPause/stopPause are not implemented (section 6) |
| newBaseRequest | boolean | no (sent) | Vehicle near end of base; fleet manager should extend |
| agvPosition | object | no (sent) | Vehicle pose |
| agvPosition.x, .y, .theta | number | yes (in object) | Pose on map |
| agvPosition.mapId | string | yes (in object) | Map ID |
| agvPosition.positionInitialized | boolean | yes (in object) | Localization valid flag |
| agvPosition.localizationScore | number 0..1 | no | **Not sent** — sim ground truth has no confidence to report |
| velocity.vx, .vy, .omega | number | no | **Not sent** — `driving` (speed over a 0.02 m/s floor) is the only motion fact on the wire |
| batteryState | object | yes | **Honest sim stub**: always `{batteryCharge: 100.0, charging: false}` — the sim has no battery, the schema requires the object, and a number that pretends to drain would be a lie |
| batteryState.batteryCharge | number (%) | yes (in object) | See above; drives nothing yet |
| batteryState.charging | boolean | yes (in object) | See above; startCharging/stopCharging not implemented (section 6) |
| operatingMode | enum AUTOMATIC / SEMIAUTOMATIC / MANUAL / SERVICE / TEACHIN | yes | Only AUTOMATIC vehicles receive orders. **Produced values: AUTOMATIC and MANUAL only** — the cab has two modes |
| errors | array | yes | Active errors; empty array = none |
| errors[].errorType | string | yes | Error name; extension point (section 9) |
| errors[].errorLevel | enum WARNING / FATAL | yes | FATAL = not in running condition |
| errors[].errorDescription, .errorHint | string | no | Diagnostics |
| errors[].errorReferences[].referenceKey, .referenceValue | string | yes (in item) | e.g. orderId/actionId the error refers to |
| actionStates | array | yes | One entry per received action, keyed by actionId |
| actionStates[].actionId | string | yes | Matches action from order/instantActions |
| actionStates[].actionType | string | no | Informational |
| actionStates[].actionStatus | enum WAITING / INITIALIZING / RUNNING / FINISHED / FAILED | yes | Action lifecycle |
| actionStates[].resultDescription | string | no | Action result text |
| safetyState | object | yes | **Status reporting only — see note below** |
| safetyState.eStop | enum AUTOACK / MANUAL / REMOTE / NONE | yes (in object) | Which acknowledge type is pending. **Produced values: NONE and MANUAL only** — MANUAL covers both a latched demand and an unhealthy chain, because both wait on the panel's acknowledge |
| safetyState.fieldViolation | boolean | yes (in object) | Protective field violated |

**safetyState is not a safety channel.** It reports, after the fact, what the
onboard safety system already did (invariant 1). No layer may trigger or clear
a safety function through MQTT; the fleet manager uses `safetyState` only to
stop assigning orders and to alert an operator.

### Deliberately omitted (exist in schema, not used)

| Field | Why omitted |
|---|---|
| maps | Single static map; map lifecycle actions not supported |
| zoneSetId | No zone sets (see order) |
| distanceSinceLastNode | Line-guided vehicle field |
| loads (loadId, loadType, …) | No load identification hardware in scope; revisit when load handling opens |
| information | Debug/visualization channel; spec forbids using it for control logic; no consumer |
| nodeStates[].nodePosition, nodeStates[].nodeDescription, edgeStates[].edgeDescription, edgeStates[].trajectory | Debug echo of order content; no consumer |
| batteryState.batteryVoltage, .batteryHealth, .reach | Not needed for charging decisions |
| agvPosition.deviationRange, .mapDescription | Logging-only, no consumer |

## 6. Topic `instantActions` (fleet manager → AGV)

Source: `instantActions.schema`. Header per section 3, plus required field
`actions`: array of action objects (identical shape to section 4's action
object; all of `actionId`, `actionType`, `blockingType` required).

**Implemented actions** (M6, measured against `vda_agent.py`) — all
predefined standard actions from spec 6.8.1, instant scope, no custom names:

| actionType | Params (per spec) | blockingType we send | Linked state | Use in this project |
|---|---|---|---|---|
| cancelOrder | – | HARD | – | Abort order; vehicle stops (controlled, **confirmed against nav** — the actionState stays RUNNING until the stop is seen, FAILED if it never is), deletes order; reports FAILED if no order (spec 6.6.3.2) |
| stateRequest | – | NONE | – | Force immediate state message |
| factsheetRequest | – | NONE | – | Request factsheet publication |

The factsheet's `protocolFeatures.agvActions` list is the machine-readable
statement of **exactly these three** — the vehicle must not advertise what
would FAIL. Any other actionType is answered with a FAILED actionState plus
an `unsupportedAction` WARNING in `errors[]` naming the actionId.

**Specified in this table's first cut, NOT implemented** (this document
claimed them before M6.2 was built; recorded 2026-08-25 when the doc was
re-cut against the code): startPause / stopPause (state `paused` is sent
hard-false), startCharging / stopCharging (batteryState is an honest sim
stub, full-and-not-charging), initPosition (spawn poses come from the
VEHICLES table; no localization-loss case in the sim). Each returns to this
table only when its linked state becomes real.

**Node actions** (added 2026-08-25, M6 review item 3 — the same shared
action object, NODE scope):

| actionType | Where | blockingType | Linked state | Use in this project |
|---|---|---|---|---|
| pick | final node of a leg-1 order (the pickup station) — `validate_order` refuses any action elsewhere | HARD | actionStates: WAITING from acceptance, RUNNING on the arrival state, FINISHED after the vehicle's own fork cycle | Leg 2 is sent on FINISHED — the fleet no longer times the dwell blind |
| drop | final node of a leg-2 order (the dropoff station), same rules | HARD | same lifecycle | The transport completes on FINISHED, not on arrival |

The `actionId` is deterministic — `<orderId>:<actionType>` — because a base
extension rebuilds the whole order and a fresh id per rebuild would hand the
vehicle a new action every time the base grew. A cancelOrder FAILs whatever
is WAITING or RUNNING (spec 6.6.3.2). The cycle is **timed, not actuated**:
the mast does not move yet, and `vda_agent.FORK_CYCLE_S` is where actuation
will land.

Standard actions **not in scope**: detectObject, finePositioning,
waitForTrigger, logReport, enableMap, downloadMap, deleteMap (single
static map).

Note: cancelOrder/startPause are process commands. They are not stop functions
in the safety sense; the safety stop path is onboard and in the F-CPU only
(invariant 1).

## 7. Topic `connection` — watchdog and supervision loss

Source: `connection.schema`, spec 6.14. Header per section 3, plus:

| Field | Type | Required | Meaning |
|---|---|---|---|
| connectionState | enum ONLINE / OFFLINE / CONNECTIONBROKEN | yes | Broker-level connection status of the vehicle |

Protocol (as prescribed by spec 6.14, QoS 1, retained):

1. On MQTT connect, the AGV registers a **last-will message** on its
   `connection` topic with `connectionState: CONNECTIONBROKEN`.
2. After connecting, the AGV publishes `ONLINE` (retained).
3. On graceful shutdown, the AGV publishes `OFFLINE`, then disconnects.
4. On unexpected disconnect, the **broker** publishes the last will
   (`CONNECTIONBROKEN`) to subscribers.

### Mapping to architecture invariants

| Concern | Rule |
|---|---|
| What connection loss means | Degraded mode, **not** a safety event (invariant 2) |
| Vehicle side | The VDA 5050 client node runs a supervision watchdog on broker connectivity. On loss of supervision the vehicle performs a **controlled stop** (normal deceleration via Nav2), keeps order data, and resumes only when supervision returns. Spec 6.2: the AGV keeps the order and may fulfill it up to the last released node; this project chooses the stricter controlled stop. |
| Fleet side | On `CONNECTIONBROKEN` the fleet manager marks the vehicle unavailable, stops assigning orders to it, and treats its zone reservations as still held until state is re-synchronized. Spec 6.5: `connection` is a protocol-level check, not a vehicle-health check — vehicle health comes from `state`. |
| What this channel is never | A safety path. E-stop, protective stop and STO are onboard and in the F-CPU (invariant 1). No safety function may depend on MQTT, the broker, or this topic. |

## 8. Topic `factsheet` (AGV → fleet manager)

Source: `factsheet.schema`, spec 6.15. Retained; published on connect and on
`factsheetRequest`. Required top-level objects per schema: `version`,
`manufacturer`, `serialNumber`, `typeSpecification`, `physicalParameters`,
`protocolLimits`, `protocolFeatures`, `agvGeometry`, `loadSpecification`.

### Used fields

| Field | Type | Required | Meaning in this project |
|---|---|---|---|
| typeSpecification.seriesName | string | yes | Vehicle series (RB-KAIROS per ADR 0002) |
| typeSpecification.agvKinematic | enum DIFF / OMNI / THREEWHEEL | yes | Value set by agv layer to match platform |
| typeSpecification.agvClass | enum FORKLIFT / CONVEYOR / TUGGER / CARRIER | yes | CARRIER |
| typeSpecification.maxLoadMass | number (kg) | yes | From platform datasheet |
| typeSpecification.localizationTypes | array, enum incl. NATURAL, REFLECTOR, … | yes | `["NATURAL"]` (AMCL on lidar) |
| typeSpecification.navigationTypes | array, enum PHYSICAL_LINE_GUIDED / VIRTUAL_LINE_GUIDED / AUTONOMOUS | yes | `["AUTONOMOUS"]` — justifies the order-field subset in section 4 |
| physicalParameters.speedMin, speedMax, accelerationMax, decelerationMax, heightMax, width, length | number | yes | From platform datasheet; fleet manager uses them for planning |
| protocolLimits.maxStringLens, maxArrayLens | object | yes | Populated with vehicle limits; 0/absent = no limit |
| protocolLimits.timing.minOrderInterval, minStateInterval | number | yes | Message-rate contract between fleet manager and vehicle |
| protocolFeatures.optionalParameters | array of {parameter, support} | yes | Declares which optional fields of section 4/5 the vehicle supports |
| protocolFeatures.agvActions | array of {actionType, actionScopes, …} | yes | Exactly the **implemented** actions of section 6 — three INSTANT plus, since 2026-08-25, pick and drop with NODE scope (amendment (b): the factsheet must not advertise what would FAIL) |
| agvGeometry.envelopes2d | array | no | **Sent empty** (`agvGeometry: {}`) — the traffic ledger derives geometry from the vehicle table, not from the wire, and M6.4's note in section 4 of this file still wants it |
| loadSpecification.loadSets | array | no | Empty until load handling is in scope |

Concrete numeric values are owned by the agv layer (single source of truth,
invariant 10); this document fixes only which fields are exchanged.

### Deliberately omitted

| Field | Why omitted |
|---|---|
| agvGeometry.wheelDefinitions, envelopes3d | Simulation/visualization detail, no consumer |
| loadSpecification.loadPositions | No multiple load handling devices |
| vehicleConfig | Optional version inventory, no consumer |
| protocolLimits.timing.visualizationInterval | visualization topic unused |

## 9. Extension policy

Invariant 3: VDA 5050 is the contract; no custom schema replaces it. Permitted
extension points, per the standard itself:

| Extension point | Standard basis | Rule in this project |
|---|---|---|
| `actionParameters` on standard actions | Spec 6.8: "Additional parameters can be defined, if they are needed" | Allowed; every added key must be documented here before use |
| Manufacturer-defined actions | Spec 6.8: manufacturer can define additional actions if no predefined action maps | Allowed as last resort; must be declared in `factsheet.protocolFeatures.agvActions` and documented here |
| `errors[].errorType` values, `errorReferences` | Free string + reference list by design | Project error names use PascalCase, documented here before use |
| `information[]` entries | Free-form debug channel, never for control logic | Currently unused |

Adding top-level fields to any message, renaming fields, or deviating from the
topic structure is **not** an extension — it is a contract break and requires
an ADR.

**Currently used extensions: project `errorType` names** (the one extension
point in use, recorded 2026-08-25 — each is a free string per the spec and
each is documented at its producer): `safetyStop` (drive enable down;
`vda_messages.errors_and_safety`), `orderError` (an order or extension
refused, spec-suggested name), `unsupportedAction` (actionType not
implemented), `cancelUnconfirmed` (the empty goal went unanswered past its
deadline; `vda_agent._pump_cancel`), `pathBlocked` (navigation gave up on a body; the escalation's end). The names are camelCase, matching the
spec's own suggested error names, and section 9's "PascalCase" rule is
corrected by this sentence.

## Amendment 2026-08-21 (M6.2)

Additive. The sections above are unchanged and stay the field-by-field
reference; where this amendment and an earlier table disagree, this amendment
is in force and says so explicitly. Written when the vehicle agent
(`m5_ver2/step6/ipc/vda_messages.py`) first put these messages on a wire.

### (a) The vehicle is the step6 forklift

ADR 0010 retired RB-KAIROS as the platform (accepted 2026-07-30) and put
vehicle work on the in-house forklift twin. Section 8's table was written in
M1, before that ruling, and its `seriesName` and `agvClass` cells name the
retired platform. Those two cells are an **M1-era example, superseded here**:

| Field | Section 8 says | In force |
|---|---|---|
| typeSpecification.seriesName | RB-KAIROS per ADR 0002 | `forklift_ver2` |
| typeSpecification.agvClass | CARRIER | `FORKLIFT` |
| typeSpecification.agvKinematic | set by the agv layer | `THREEWHEEL` (tricycle: one steered drive wheel, two rear) |

`physicalParameters` width, length and heightMax are **measured off
`m5_ver2/step6/gazebo/forklift_ver2/model.sdf`**, the file that owns the
geometry, and are not round numbers: 0.90 m, 2.735 m, 2.20 m (carriage at full
mast travel). `speedMax` comes from `limits.traction_speed_max_mps`.
`accelerationMax`, `decelerationMax` and `maxLoadMass` remain declared sim
stubs — the plant models none of the three.

### (b) Actions are phased; the factsheet declares only what is implemented

Section 6 lists eight supported actions and says the factsheet's
`protocolFeatures.agvActions` is "the machine-readable statement of exactly the
eight". **The eight remain the project target.** The factsheet, however, is a
statement about the vehicle in front of it, and it must not advertise an action
that would answer `FAILED`. It therefore declares the **implemented** set, and
that set grows by milestone:

| actionType | Declared from |
|---|---|
| cancelOrder | **M6.2** |
| stateRequest | **M6.2** |
| factsheetRequest | **M6.2** |
| startPause, stopPause | not yet — M6.4 built traffic on base/horizon instead of pause, so the planned "M6.4" date lapsed; `paused` is sent hard-false (recorded 2026-08-25) |
| startCharging, stopCharging | when a battery model exists |
| initPosition | when localization can be re-seeded |

Section 6's list of supported actions is unchanged; what this amendment fixes
is the claim that the factsheet mirrors it in one step rather than in stages.

### (c) `order.edge.maxSpeed` is parsed, not enforced, until M6.4

Section 4 lists `edge.maxSpeed` under **Used fields**. As of M6.2 the vehicle
**accepts and ignores** it: the released route handed to navigation carries
waypoints and an arrival radius only, and speed is capped by
`limits.traction_speed_max_mps` at the command gate, not per edge. The
factsheet therefore declares:

```json
{"parameter": "order.edge.maxSpeed", "support": "NOT_SUPPORTED"}
```

An order carrying `maxSpeed` is **not** rejected for it. Per-edge enforcement
lands with M6.4, at which point the declaration becomes `SUPPORTED` and this
row of section 4 needs no further change.

### (d) Timestamps carry milliseconds

Section 2 writes the timestamp form as `YYYY-MM-DDTHH:mm:ss.ffZ`, quoting the
spec's own example. Messages produced by this project carry **three** fraction
digits — `YYYY-MM-DDTHH:mm:ss.fffZ`, UTC, always `Z`, never a numeric offset.
Both forms satisfy the schemas' `format: date-time`; milliseconds are the
resolution a state stream published at a few hertz actually needs.

### (e) Project error names, and why they are camelCase

Section 9 says project `errors[].errorType` values "use PascalCase". **That
guidance yields here**, and the reason is consistency with the thing the field
already carries: VDA 5050's own predefined error names — `orderError`,
`noRouteError`, `validationError`, `orderUpdateError` — are camelCase, so a
PascalCase project name sitting beside them in the same array would announce
itself as foreign for no benefit. `actionType`, `errorLevel` and every other
enumerated word on this wire is camelCase too. Owner ruling, M6.2: **project
error names are camelCase**, and section 9's sentence is superseded for this
column only. Every name below is documented before use, which is the part of
section 9 that stands unchanged.

The complete set this project emits, all of them from
`m5_ver2/step6/ipc/vda_messages.py` and `ipc/vda_agent.py`:

| errorType | errorLevel | Means |
|---|---|---|
| `safetyStop` | FATAL | Drive enable is down — a latched safety demand or a pending startup acknowledge. Reporting only: the F-model dropped `Motor` long before this message was built. |
| `orderError` | WARNING | The order just delivered was refused and no route was issued; `errorDescription` is the refusal reason and `errorReferences` carries the offending `orderId`. |
| `unsupportedAction` | WARNING | An instant action was answered `FAILED` because this milestone does not implement it; `errorReferences` carries the `actionId`. The factsheet's `agvActions` is the list that would have avoided it. |
| `cancelUnconfirmed` | WARNING | A cancel's empty goal went out repeatedly and navigation never reported a stop inside the deadline — this vehicle may still be moving (`vda_agent._pump_cancel`, the Fleet Gate 4 lesson). Added M6.3, recorded here 2026-08-25. |
| `pathBlocked` | WARNING | Navigation gave up on a body in the path — the end of the HOLD→AVOID→NUDGE escalation. Reported **once**, on the edge into BLOCKED, naming the order; the fleet answers by closing the node ahead and taking the order back (cancelOrder). The order is kept until that cancel arrives. Added 2026-08-25 (M6 review item 5c). |

`unsupportedAction` is reported **once**, on the state that carries the
`FAILED` actionState; that actionState is the standing record afterwards. The
other two are recomputed on every state and therefore persist exactly as long
as the condition does — `safetyStop` for as long as the enable is down,
`orderError` for the single state a refusal produces.

## Amendment 2026-08-25 (M6 review) — the base tables re-cut against the code

The 2026-08-25 review measured this document against the code at the M6.7
tip and found the base tables still describing intentions where the code had
since decided otherwise. Unlike the 2026-08-21 amendment, this one edits the
base tables IN PLACE — a reference whose truth lives in its appendix is how
the drift happened — and the earlier amendments stay as history. What
changed, so a differ knows it was deliberate:

* Section 4: `nodePosition.theta` marked **not sent**; a *Recorded
  deviations — order acceptance* subsection added (orderUpdateId must be
  exactly +1; new order rejected while executing; node/edge actions
  rejected; duplicates ignored).
* Section 5: `edgeStates` always `[]`; `paused` hard-false; `velocity` and
  `localizationScore` not sent; `batteryState` named an honest stub; the
  produced value sets of `operatingMode` (AUTOMATIC/MANUAL) and
  `safetyState.eStop` (NONE/MANUAL) recorded; `cancelUnconfirmed` added to
  the error table.
* Section 6: rewritten around the **three implemented** instant actions;
  the five once promised move to a named not-implemented list. Later
  the same day, item 3 added **pick and drop as NODE actions** with
  their own table — the fork cycle now rides the order and gates leg 2
  and completion, and deviation (3) of section 4 is superseded in
  place.
* Section 8: `protocolFeatures.agvActions` counts the implemented set
  (three instant + two node); `agvGeometry` sent empty.
* Section 9: the "no extensions" claim replaced by the four project
  errorType names in use.
