# Brief m4f-07b — H6 liveness and the holdable reset

```
gate:                M4
agent:               hmi
goal:                The HMI conforms to section 10.8 as amended: the
                     operator-liveness deadman exists, and the reset can be
                     physically held so T5.4 is executable from the page.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md sections 10.8 (H5/H6) and
                      10.12 item 8, docs/reports/m4f-01c-hmi-shutdown-liveness-
                      rules.md, docs/reports/m4f-08-commissioning-scenarios.md
                      (finding 3: the reset cannot be held from the page),
                      plc/forklift/SPEC.md section 11 T5.4 (the held-reset
                      procedure), hmi/ sources, plc/forklift/double/ (test
                      target)]
deliverable:         hmi/ — hmi_server.py and static/index.html amended,
                     EVIDENCE_HMI.md extended
done_when:           H6 is implemented as ruled: the page's GET /state poll is
                     the liveness beacon; when it is stale for
                     UI_POLL_STALE_TIME (1.0 s, five poll periods) the backend
                     zeros all five request writes while the heartbeat
                     CONTINUES, nothing latches, and each Bool is re-carried
                     only after the page has been seen to send it low
                     (recovery as release, never resume); the reset button
                     becomes press-and-hold capable — TRUE written every cycle
                     while held, FALSE on release — which the PLC still
                     edge-detects, and which makes SPEC section 11 T5.4's
                     held-reset steps executable from the page; both behaviours
                     are demonstrated against the PLC logic double on 4850 with
                     transcripts in EVIDENCE_HMI.md quoted as printed — the H6
                     kernel (kill the page poll with the backend alive, observe
                     zeros under a continuing heartbeat, then recover per the
                     release rule) and the T5.4 kernel (hold across zone-clear:
                     latch stands; release and re-assert: latch clears); no new
                     dependency, no new node, writes stay Hmi-only.
forbidden:           [touching bridge/ plc/ sim/ agv/ or docs/interfaces/,
                      connecting to the live PLCSIM endpoint, changing the H5
                      shutdown behaviour, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly your hmi/
files plus your report docs/reports/m4f-07b-h6-and-holdable-reset.md; message
style `feat(hmi): implement operator liveness and the holdable reset`.
