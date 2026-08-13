# Brief m5a-07 — safety mirror lamps in the HMI

```
gate:                M5 (early)
agent:               hmi
goal:                The HMI shows the F-layer state: mirror lamps and a
                     distinct safety banner, read-only.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md section 11 (authoritative
                      node names — wait for it if absent),
                      hmi/hmi_server.py, hmi/static/index.html]
deliverable:         hmi/ — the status poll and page extended,
                     EVIDENCE_HMI.md appended
done_when:           the 5 Hz status poll adds the Safety/ mirror nodes; the
                     page gains a SAFETY DEMAND banner visually distinct from
                     the process-stop banner, labelled "F-CPU safety demand
                     (mirror, read-only)" with the standard-program
                     process-stop banner unchanged; three lamps
                     (e-stop demand, zone demand, safety reset required); the
                     page states in one line that this panel displays and
                     never commands; writes stay exactly the six Hmi nodes —
                     zero new writes; a run against the bridge test double
                     (extend your own double instance's served nodes if the
                     bridge double lacks Safety/ — or drive the mirrors via a
                     direct test write to your own double only) shows the
                     lamps and banner switching, appended to EVIDENCE_HMI.md
                     quoted as printed; graceful degradation: mirrors absent
                     on the server (F-layer fallback) renders the panel
                     greyed "not present", never an error.
forbidden:           [any new writable node, touching the joystick/reset
                      logic, connecting to PLCSIM, editing docs/interfaces/,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly your hmi/
files plus your report docs/reports/m5a-07-hmi-safety-lamps.md; message style
`feat(hmi): show the safety mirror state`.
