# Report — m5-53 HMI v2b, the map pane

    brief:               m5-53 (dispatch prompt; task 7 of
                         docs/superpowers/plans/2026-08-06-m5-closure.md)
    status:              done
    files_changed:
      - hmi/V2B-DESIGN.md                        (new — the design and the three rulings)
      - hmi/hmi_server.py                        (MonitorProxy, three GET-only /monitor
                                                  paths, the display-ramp constants, the
                                                  H6 beacon exclusion, a uniform 405)
      - hmi/static/index.html                    (zone G: the map pane, ~400 lines of
                                                  CSS/HTML/JS; zones A–F untouched)
      - hmi/config.yaml                          (monitor.base_url — an address)
      - hmi/config-v2b-double.yaml               (new — the double-first configuration)
      - hmi/tools/viz_double.py                  (new — a stand-in for the monitoring
                                                  service, its section 5 surface copied)
      - hmi/tools/check_hmi_map_pane.py          (new — the backend half, 7 checks)
      - hmi/tools/capture_v2b_screens.mjs        (new — the page half, 10 passes, CDP)
      - hmi/EVIDENCE_HMI.md                      (new section J)
      - hmi/README.md                            ("This layer must not access": viz/)
      - hmi/V3-PLAN.md                           (two stale lines: m5-13 has since ruled
                                                  the read-only phrase; both were the only
                                                  bare occurrences left in this layer)
      - hmi/evidence/capture-v2b-2026-08-06.log        (run log)
      - hmi/evidence/check-map-pane-2026-08-06.log     (backend-half log)
      - hmi/evidence/screenshots/v2b-00..14-*.png      (15 shots, gitignored, local)
      - hmi/evidence/screenshots/MANIFEST-v2b-2026-08-06.txt
      - hmi/evidence/hmi-cycles-2026-08-06-v2b-secondtab-*.csv  (three files, one
                                                  per backend session; the rule is one
                                                  CSV per session, never a shared path)
      - docs/reports/m5-53-hmi-v2b-map.md              (this report)
    invariants_touched:  none.
                         Inv 1 / 2 — nothing added is a safety device or a command
                           path; the pane is one-way and read-only, and the failure
                           of the monitoring service is a degraded view, not a stop.
                         Inv 4 — no server was added. The HMI is still an OPC UA
                           client only, and the new surface is HTTP GET on loopback.
                         Inv 8 — the monitoring service is addressed on loopback,
                           enforced at start; a non-loopback URL refuses to boot.
                         Inv 10 — no age, no pose and no obstacle class is recomputed
                           here; the payload is passed through key for key and the
                           checker asserts the key sets are identical.
                         Inv 11 — the edge used is CLAUDE.md section 3's already-drawn
                           `MON --o HMI`. No new topology edge; nothing imported from
                           viz/, bridge/ or fleet/; no ROS 2, no gz, no MQTT.
                         The eight-node OPC UA write set did not grow. No dependency
                           was added: stdlib `urllib` on the backend, canvas 2d on the
                           page, and the CDP instrument speaks Node 22's built-in
                           WebSocket.
    open_questions:
      - THE MEASUREMENT THIS BUILD COULD NOT MAKE. The display ramp's two
        endpoints (1000 / 5000 ms) are DISPLAY VALUES, not measured ones. The
        bound worth having is a bound on the inter-arrival time of /amcl_pose
        WHILE THE VEHICLE IS MOVING, with its n. The only committed capture of
        that topic (viz/EVIDENCE_MONITORING.md section 8) is of a STANDING
        vehicle — 30 messages, a 463-second age — which is the residual itself,
        not a sample of the moving case. Requested from whoever next runs the
        vehicle stack: the inter-arrival distribution of /amcl_pose over a
        moving traverse, n stated. Until then the ramp is marked a design value
        wherever it appears.
      - THE JOIN HAS NOT BEEN MADE AGAINST THE REAL viz/. Every value in
        section J came from hmi/tools/viz_double.py, whose surface is copied key
        for key from viz/DESIGN.md section 5 and viz/EVIDENCE_MONITORING.md
        section 7, and the checker asserts the key sets are identical. The real
        service needs rclpy, a vehicle image and Gazebo and lives in WSL; the
        page, its backend and the browser live on Windows. One joint run —
        vehicle up in domain 51, real viz on 8089, this backend pointed at it —
        is the outstanding item, and it is a request rather than something this
        brief could do inside its own scope.
      - ONE JUDGEMENT CALL, FLAGGED FOR THE VERIFIER rather than buried. The
        display ramp is a millisecond in the HMI. V2B-DESIGN section 4.2 argues
        it is outside ADR 0008 D3's prohibition on four grounds: the age is READ
        rather than measured here; no PLC node carries a pose, a pose age or a
        localization verdict, so there is no verdict this could duplicate;
        nothing rides on it — it changes pixels and is read by no other part of
        the page; and it states how old the information is, never whether the
        estimate is good. If the verifier reads it the other way, the fallback
        that needs no ruling is to delete the ramp and render the age as text
        only — the age itself is non-negotiable, the ramp is the presentation.
      - A LOAD-BEARING MECHANISM WAS CHANGED, deliberately and in the safe
        direction: the three /monitor paths no longer refresh the section 10.8
        H6 page-liveness beacon (V2B-DESIGN section 2.2). A monitoring-plane
        fetch proves the browser is running and proves nothing about the channel
        that carries the operator's requests. The change can only make the
        beacon go stale sooner. It was tested in the form that could only pass
        if the exclusion were real — GET /state blocked at the browser while the
        map pane kept polling — and the second-tab check was re-run for the same
        reason.
      - hmi/tools/check_hmi_writes.py and check_hmi_h6_and_reset.py call
        os.killpg and do not run on Windows at all. That is a pre-existing
        platform limitation rather than a v2b regression, and their subject
        matter is covered by section J.7, J.8 and the new checker; but the two
        harnesses are now unrunnable on the showcase machine and somebody should
        own that.
      - CLAUDE.md section 4's repository layout still does not list viz/, which
        m5-13b already requested. Unchanged here; it is the owner's file.
    next_suggested:      one joint run of the real viz/ service against this backend,
                         which would also produce the /amcl_pose inter-arrival figure
                         the ramp is waiting on.

## What was built

Roadmap criterion (e)'s last clause — the HMI *"shows a real-time map with live
obstacles"* — as a third column on the existing operator page. The whole
warehouse map, the vehicle's pose, the navigation lidar's returns, and **the
age of every one of them**.

## The problem this version is actually about

AMCL publishes `/amcl_pose` **only on a filter update**, so a standing vehicle
has no pose stream at all — `viz/EVIDENCE_MONITORING.md` §8 recorded
`pose_age_ms = 463 157` beside healthy everything-else. A page that draws that
as a vehicle sitting on the map is silently wrong and looks exactly like a
working display.

The ruling taken: **this page has no rendering that means "live".** Every
marker carries the age of the datum it came from, in the marker itself, in
every state; as the age grows the marker fades and hollows; past the display
ramp it is drawn with no fill at all and labelled `LAST KNOWN POSITION — as of
N s, not a current position`, with the banner saying so in words. Nothing was
ever drawn as current, so there is nothing for a stale value to decay into.
Every step of the ramp under-claims.

The proof is at the pixel level, not in a caption: the capture reads the page's
own canvas back with `getImageData` and counts pixels at the marker's exact
fill colour — **53 fresh, 0 stale**.

And the consequence that is not a defect, stated on the page itself: because
the localization publishes only on a filter update, a **standing** vehicle
always crosses the ramp. The banner says the page cannot tell a standing
vehicle from a stopped one and does not guess.

## Where the data comes from, and why the browser does not fetch it directly

`viz/` sends no CORS header, and editing that layer so the HMI can reach it
would invert the boundary its own DESIGN §1 asserts. So the HMI **backend**
fetches over loopback and re-serves under its own origin — the `MON --o HMI`
edge realised in the backend half rather than the browser half. Two
consequences, both improvements: the page's "no external request of any kind"
sentence stays literally true and needed no restatement (which `V3-PLAN.md` §1
had expected v2b to have to make), and an unreachable monitoring service is
caught in one place instead of as an opaque browser error.

`MonitorProxy` constructs exactly one `urllib.request.Request` in the whole
layer and constructs it `method="GET"`; the checker asserts that, asserts that
no other HTTP client exists in the file, and asserts the three inbound paths
answer 405 to every verb but GET — the write helper's allowlist pattern applied
to a second transport.

## Evidence

`hmi/EVIDENCE_HMI.md` §J, written as the states landed. Fifteen screenshots in
`hmi/evidence/screenshots/` (gitignored; the manifest and §J's table are what
travel), each named for the state it shows, each captioned by the instrument as
it landed, and each accompanied by the DOM readout it was taken from.

The states the owner asked for, all photographed: the map with the vehicle
live; **the map with a STALE pose**; obstacles present; obstacles absent; the
monitoring service down; and the v2a states unbroken. Four more that the
failure analysis demanded: the scan stopped arriving (returns drawn hollow with
their age, never emptied), no map yet, no monitoring service configured at all
(a different fact from "not answering"), and the H6 deadman firing while the
map pane kept polling.

Two instruments, deliberately split so a DOM handler cannot pass by proxy:
`capture_v2b_screens.mjs` presses the page with real input events over CDP (10
passes, every check passing), `check_hmi_map_pane.py` exercises the socket and
sweeps the source (7 checks, all passing). Both logs are committed beside the
evidence.

Everything was produced against two doubles. No PLC, no F-CPU, no vehicle, no
Gazebo, no ROS 2 process and no instance of the real monitoring service took
part, and nothing rehearsed against a double closes any criterion.
