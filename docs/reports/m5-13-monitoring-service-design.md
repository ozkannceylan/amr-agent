# Report — m5-13 monitoring service design

    brief:               docs/briefs/m5-13-monitoring-service-design.md
    status:              done
    files_changed:
      - viz/DESIGN.md                                    (new — the design, no code)
      - docs/reports/m5-13-monitoring-service-design.md  (this report)
    invariants_touched:  none. No new topology edge: the ruling gives the
                         already-drawn MON box a directory; both circle-ended
                         edges in CLAUDE.md §3 carry the design unchanged
                         (invariant 11). Invariant 10 is carried as DESIGN §6's
                         forwarded / forbidden-to-derive split. Invariant 1 is
                         untouched by construction — nothing on this plane is a
                         command path.
    open_questions:
      - viz/ is outside agv-ros2's standing write scope. viz/DESIGN.md was
        created because the dispatch instruction says to name the design
        document per the ruled directory so the orchestrator can commit it by
        pathspec; if the orchestrator prefers, the file relocates without
        content change. viz/README.md is NOT created — its required
        "must not access" text is specified verbatim in DESIGN §1 and its
        creation is requested for the build brief (or an infra brief, since it
        establishes a top-level layer).
      - whether the new top-level layer wants its own short ADR for the
        record, ADR 0005-style. ADR 0011 D4 explicitly delegated the directory
        ruling to this brief, so none is required for authority; one may still
        be wanted for the shelf. Owner's call.
      - the allocation table's sim-side move (ADR 0016 preamble) changes the
        import path DESIGN §5 names; tracked there, nothing blocks on it.
    next_suggested:      brief the build (viz/) and HMI v2b in that order,
                         both from DESIGN §5's endpoint table; fold §8's
                         acceptance checks into the build brief's done_when.

## The two rulings, one line each with the reason

1. **Directory: `viz/`, its own top-level layer.** The ADR 0005 test fails
   `agv/` outright: hosting a process that holds contexts in every vehicle
   domain and serves the operator would carve two exceptions into the exact
   boundary ADR 0016 D1/D2 built ("one domain per vehicle, one image, no
   operator-facing endpoint") — DESIGN §1 states the carve-outs agv/README
   would need, and rules on them. agv/README.md needs no change.
2. **Read-only: recorded limitation, language downgraded.** The phrase
   becomes "read-only by construction of the process and proven by test; not
   enforced by the middleware", everywhere, with a grep check that the
   unqualified form is absent (DESIGN §2, §8.6). SROS2 enforcement is
   rejected with its cost stated plainly: enforced access control binds every
   participant in the domain, so ~20 vehicle processes ×4 vehicles would need
   keystore identities plus a CA/key-distribution story the project
   deliberately lacks — disproportionate to constrain one operator process.
   What would remove the limitation is recorded, not scheduled.

## The D3c mechanism ruling input

One multi-context process (one rclpy Context per vehicle domain,
zero-endpoint nodes, subscriptions only); `domain_bridge` recorded as the
rejected alternative — a new dependency whose fixed forwarded set means
full-time forwarding of image topics whether watched or not, and whose
mechanism is republishing, which forecloses subscription-lifecycle camera
selection (DESIGN §3).

## What was run (cheap probes, WSL Jazzy, scratch domains 71/72)

- Multi-context isolation in one process: PASS, no cross-domain leak;
  runtime subscription create/destroy: PASS.
- Zero-endpoint node: the constructor flags alone do NOT reach zero on
  Jazzy — `/parameter_events` survives and needs one explicit
  `destroy_publisher`; with the full recipe: publishers 0, services 0,
  subscription still creatable. The recipe is in DESIGN §2.2/§4 so the build
  cannot rediscover it.

## The five V3-PLAN §2 constraints

All five carried in the design itself, each with its location, in DESIGN §9's
table: (1) serial-rooted `/vehicles/<serial>/…` surface at n = 1 (§5);
(2) whole map, never a crop, in the endpoint contract (§5); (3) values-only
JSON poll with every raster on its own endpoint, checked at §8.3 (§5);
(4) mechanism ruled against camera load (§3); (5) camera selection as
refcounted subscription lifecycle, no message into any vehicle domain (§7).

## Scope compliance

Design only — no code, no dependency added (stdlib HTTP, existing rclpy and
identity code path; the raw-cells map transport exists to avoid an image
library). Nothing committed, no branch created. plc/, bridge/ and hmi/
untouched. Probes were scratchpad-only, scratch domains, no Gazebo.
