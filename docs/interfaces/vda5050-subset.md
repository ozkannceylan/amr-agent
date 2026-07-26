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
| nodePosition.theta | number, ±π | no | Target orientation; sent for station nodes |
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
| edgeStates | array | yes | Remaining edges; empty when idle |
| edgeStates[].edgeId, .sequenceId, .released | string / integer / boolean | yes | As in order |
| driving | boolean | yes | Vehicle is driving/rotating |
| paused | boolean | no (sent) | Pause state, linked to startPause/stopPause |
| newBaseRequest | boolean | no (sent) | Vehicle near end of base; fleet manager should extend |
| agvPosition | object | no (sent) | Vehicle pose |
| agvPosition.x, .y, .theta | number | yes (in object) | Pose on map |
| agvPosition.mapId | string | yes (in object) | Map ID |
| agvPosition.positionInitialized | boolean | yes (in object) | Localization valid flag |
| agvPosition.localizationScore | number 0..1 | no | AMCL confidence; logging/monitoring only |
| velocity.vx, .vy, .omega | number | no | Vehicle-frame velocity; monitoring only |
| batteryState | object | yes | Battery info |
| batteryState.batteryCharge | number (%) | yes (in object) | Drives charging decisions in fleet manager |
| batteryState.charging | boolean | yes (in object) | Linked state of startCharging/stopCharging |
| operatingMode | enum AUTOMATIC / SEMIAUTOMATIC / MANUAL / SERVICE / TEACHIN | yes | Only AUTOMATIC vehicles receive orders |
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
| safetyState.eStop | enum AUTOACK / MANUAL / REMOTE / NONE | yes (in object) | Which acknowledge type is pending |
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

Supported actions — all are **predefined standard actions** from spec 6.8.1,
instant scope, no custom names:

| actionType | Params (per spec) | blockingType we send | Linked state | Use in this project |
|---|---|---|---|---|
| startPause | – | HARD | `paused` | Fleet-level hold (traffic, operator) |
| stopPause | – | HARD | `paused` | Resume after hold |
| cancelOrder | – | HARD | – | Abort order; vehicle stops (controlled), deletes order, cancels actions; reports FAILED if no order (spec 6.6.3.2) |
| startCharging | – | HARD | `batteryState.charging` | Start charging at charge station (also valid as node action) |
| stopCharging | – | HARD | `batteryState.charging` | Release vehicle from charger before new order |
| initPosition | x, y, theta (float64); mapId, lastNodeId (string) | HARD | `agvPosition.*`, `lastNodeId` | Set initial pose in simulation / after localization loss |
| stateRequest | – | NONE | – | Force immediate state message |
| factsheetRequest | – | NONE | – | Request factsheet publication |

Standard actions **not supported**: pick, drop, detectObject, finePositioning,
waitForTrigger, logReport, enableMap, downloadMap, deleteMap (no load handling
device in scope, single static map). The factsheet's `protocolFeatures.agvActions`
list is the machine-readable statement of exactly the eight actions above.

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
| protocolFeatures.agvActions | array of {actionType, actionScopes, …} | yes | Exactly the eight actions of section 6 |
| agvGeometry.envelopes2d | array | no | Footprint polygon for traffic planning |
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

**Currently used extensions: none.**
