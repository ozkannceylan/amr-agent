#!/usr/bin/env python3
"""Check the bridge's connect logic against `bridge-design.md` §3.1 and §3.2.

Both rule sets are commissioning facts about the S7-1500 that the pre-
commissioning code did not satisfy (§12 open item 9, brief m3-21):

  §3.1  the browse path crosses TWO namespaces —
        `Objects` -> `ServerInterfaces` (`http://www.siemens.com/simatic-s7-opcua`)
        -> `DemoCell` (`http://DemoCell`) -> `Input/` ... — both indices resolved
        by URI at every session establishment, each path element qualified with
        the index of the namespace THAT element belongs to, no fallback index and
        no scanning of the namespace array;
  §3.2  every session parameter the bridge sends is a request. The granted
        session timeout is read back on every connect and the keep-alive period
        is derived from the granted value, never from the request.

This harness drives `PlcClient._connect` and `PlcClient._disconnect` — the
bridge's own session establishment and teardown, deliberately, because a
reimplementation here would test this file instead of the bridge. Reaching for
those two underscore-prefixed methods is the harness's business, not an
interface: nothing is stubbed, and no code path in `amr_bridge/` is
special-cased for a test.

Run it against the test double (never against PLCSIM, `bridge-design.md` §10):

    "$VENV/bin/python" bridge/test_double/plc_test_double.py \
        --endpoint opc.tcp://127.0.0.1:4840/amr-agent/celldouble/ &
    "$VENV/bin/python" bridge/tools/check_connect_conformance.py

The double registers the real server's two URIs behind filler namespaces, so its
indices differ from PLCSIM's; a run that passes against both is a run in which no
index was written down anywhere.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asyncua import ua  # noqa: E402

from amr_bridge import config as config_mod  # noqa: E402
from amr_bridge.instrumentation import Counters, Recorder  # noqa: E402
from amr_bridge.opcua_side import (  # noqa: E402
    KEEPALIVE_EXCHANGES_PER_TIMEOUT,
    NamespaceNotFound,
    PlcClient,
    derive_keepalive_period_s,
)
from amr_bridge.slots import SlotSet  # noqa: E402

#: Phase-0 observation, 2026-07-27: PLCSIM Advanced published the
#: `ServerInterfaces` folder at namespace index 3. Recorded here so the harness
#: can assert the double is NOT at that index — evidence that the indices differ
#: between the two servers, never a value to configure (§3.1 N3).
PLCSIM_SERVER_INTERFACES_INDEX = 3

#: `opcua-nodes.md` §9: 7 Input/, BridgeHeartbeat, ConveyorSpeedCommand,
#: 5 Status/ and BridgeLinkOk.
EXPECTED_NODE_COUNT = 15


class Checks:
    def __init__(self) -> None:
        self.failures = 0

    def ok(self, passed: bool, statement: str, detail: str = "") -> None:
        if passed:
            print(f"   ok   {statement}" + (f" — {detail}" if detail else ""))
        else:
            self.failures += 1
            print(f"   FAIL {statement}" + (f" — {detail}" if detail else ""))

    def result(self) -> int:
        print("\nRESULT:", "PASS" if self.failures == 0 else f"FAIL ({self.failures})")
        return 1 if self.failures else 0


def _client(cfg: config_mod.Config, recorder: Recorder) -> PlcClient:
    """A PlcClient with no ROS side: the connect logic under test touches
    neither the slots nor the publisher."""
    return PlcClient(
        cfg,
        SlotSet(config_mod.INPUT_KEYS),
        recorder,
        Counters(),
        lambda value: time.monotonic_ns(),
    )


async def check_namespaces(checks: Checks, client: PlcClient, cfg: config_mod.Config) -> None:
    print("\n1. §3.1 — both namespaces resolved by URI, indices not hardcoded")
    indices = client.namespace_indices
    checks.ok(
        set(indices) == set(config_mod.NAMESPACE_KEYS),
        "both namespace URIs were resolved at session establishment",
        ", ".join(f"{cfg.namespace_uris[key]} -> {index}" for key, index in indices.items()),
    )
    si = indices.get(config_mod.NS_SERVER_INTERFACES)
    interface = indices.get(config_mod.NS_INTERFACE)
    checks.ok(si != interface, "the two indices differ, so one index cannot qualify both elements",
              f"ServerInterfaces {si}, DemoCell {interface}")
    checks.ok(
        si != PLCSIM_SERVER_INTERFACES_INDEX,
        "this server's ServerInterfaces index differs from PLCSIM's phase-0 index",
        f"{si} here vs {PLCSIM_SERVER_INTERFACES_INDEX} on PLCSIM — a hardcoded index "
        "could not resolve on both servers",
    )
    checks.ok(
        len(client.resolved_node_keys) == EXPECTED_NODE_COUNT,
        f"all {EXPECTED_NODE_COUNT} §9 nodes resolved through Objects/ServerInterfaces/DemoCell",
        f"{len(client.resolved_node_keys)} nodes",
    )
    path = "/".join(f"{indices[ns]}:{name}" for ns, name in cfg.interface_path)
    print(f"        interface path in force this session: Objects/{path}")


async def check_addressing_is_not_accidental(checks: Checks, client: PlcClient) -> None:
    """The two rules of §3.1 N1/N3 stated as failures: the paths that the
    pre-commissioning config used cannot resolve against this shape."""
    print("\n2. §3.1 N1/N3 — the paths that would 'work by accident' do not resolve")
    indices = client.namespace_indices
    interface = indices[config_mod.NS_INTERFACE]
    si = indices[config_mod.NS_SERVER_INTERFACES]
    objects = client.opcua_client.nodes.objects

    async def expect_no_match(path: list[str], statement: str) -> None:
        try:
            await objects.get_child(path)
        except ua.UaStatusCodeError as exc:
            checks.ok(True, statement, type(exc).__name__)
        else:
            checks.ok(False, statement, "the path resolved, so this server is not the §3.1 shape")

    await expect_no_match(
        [f"{interface}:DemoCell"],
        "DemoCell does not hang directly under Objects (N1: the pre-m3-21 path)",
    )
    await expect_no_match(
        [f"{interface}:DemoCell", f"{interface}:Input", f"{interface}:ConveyorBeltPosition"],
        "the single-namespace path from Objects addresses nothing (N1)",
    )
    await expect_no_match(
        [f"{interface}:ServerInterfaces", f"{interface}:DemoCell"],
        "ServerInterfaces is not in the interface namespace (N3)",
    )
    await expect_no_match(
        [f"{si}:ServerInterfaces", f"{si}:DemoCell"],
        "DemoCell is not in the Siemens namespace (N3)",
    )


def check_session_parameters(
    checks: Checks, client: PlcClient, cfg: config_mod.Config
) -> tuple[float, float]:
    print("\n3. §3.2 — the granted session timeout is read back and the keep-alive derived from it")
    requested_ms = cfg.requested_session_timeout_ms
    granted_ms = client.granted_session_timeout_ms
    keepalive_s = client.keepalive_period_s
    assert granted_ms is not None and keepalive_s is not None
    direction = "below" if granted_ms < requested_ms else ("above" if granted_ms > requested_ms else "equal to")
    checks.ok(
        granted_ms != requested_ms,
        "the server revised the request, so the two values are distinguishable in this run",
        f"requested {requested_ms:.0f} ms, granted {granted_ms:.0f} ms ({direction} the request)",
    )
    checks.ok(
        abs(keepalive_s - derive_keepalive_period_s(granted_ms)) < 1e-9,
        "the keep-alive period is the granted timeout / "
        f"{KEEPALIVE_EXCHANGES_PER_TIMEOUT}",
        f"{keepalive_s:.3f} s",
    )
    checks.ok(
        abs(keepalive_s - derive_keepalive_period_s(requested_ms)) > 1e-9,
        "it is NOT the value the request would have produced",
        f"{derive_keepalive_period_s(requested_ms):.3f} s would have been the wrong answer",
    )
    checks.ok(
        keepalive_s * KEEPALIVE_EXCHANGES_PER_TIMEOUT <= granted_ms / 1000.0 + 1e-9,
        f"at least {KEEPALIVE_EXCHANGES_PER_TIMEOUT} exchanges fall inside the granted window",
        f"{KEEPALIVE_EXCHANGES_PER_TIMEOUT} x {keepalive_s:.3f} s <= {granted_ms / 1000.0:.3f} s",
    )
    return granted_ms, keepalive_s


async def check_keepalive_in_force(
    checks: Checks,
    client: PlcClient,
    cfg: config_mod.Config,
    recorder: Recorder,
    granted_ms: float,
    keepalive_s: float,
) -> None:
    """Let the session sit idle for longer than the granted timeout and measure
    the cadence of the keep-alive exchanges that hold it open.

    What this establishes and what it does not: the session surviving is
    over-determined — `asyncua`'s own health probe also touches the server — so
    survival alone is not proof. The *measured spacing* of the bridge's own
    keep-alive rows is, because the granted and requested timeouts imply
    different periods.
    """
    idle_s = max(granted_ms / 1000.0 * 1.5, keepalive_s * 3.0 + 1.0)
    print(f"\n4. §3.2 S3 — idle for {idle_s:.1f} s (> the granted "
          f"{granted_ms / 1000.0:.1f} s) with no cycle running")
    before = client.counters.keepalive_probes
    await asyncio.sleep(idle_s)
    probes = client.counters.keepalive_probes - before
    checks.ok(probes >= 2, "the bridge's own keep-alive exchanges fired while the cycle was idle",
              f"{probes} exchanges in {idle_s:.1f} s")
    checks.ok(client.counters.keepalive_failures == 0, "no keep-alive exchange failed")

    recorder.maybe_flush(force=True)
    stamps = []
    with open(recorder.path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["event"] == "session" and row["name"] == "keepalive" and row["t_end_ns"]:
                stamps.append(int(row["t_end_ns"]))
    spacings = [(b - a) / 1e9 for a, b in zip(stamps, stamps[1:])]
    if spacings:
        measured = sum(spacings) / len(spacings)
        from_request = derive_keepalive_period_s(cfg.requested_session_timeout_ms)
        print(f"        measured spacing {['%.3f' % s for s in spacings]} s")
        checks.ok(
            abs(measured - keepalive_s) < abs(measured - from_request),
            "the measured cadence matches the grant-derived period, not the request-derived one",
            f"measured {measured:.3f} s; grant-derived {keepalive_s:.3f} s; "
            f"request-derived {from_request:.3f} s",
        )
    else:
        checks.ok(False, "keep-alive exchanges were recorded in the evidence file")

    # The session must still be usable: the point of the keep-alive.
    try:
        value = await client.nodes[config_mod.OUTPUT_KEY].read_value()
        checks.ok(True, "the session outlived the granted timeout while idle",
                  f"ConveyorSpeedCommand read back as {value}")
    except Exception as exc:
        checks.ok(False, "the session outlived the granted timeout while idle", repr(exc))


async def check_missing_namespace_fails(
    checks: Checks, cfg: config_mod.Config, recorder: Recorder
) -> None:
    """§3.1 N4 — a URI the server does not publish is a connect failure, with no
    fallback index and no scan of the namespace array."""
    print("\n5. §3.1 N4 — a missing namespace URI fails the connect, in both namespaces")
    for key in config_mod.NAMESPACE_KEYS:
        broken = copy.deepcopy(cfg)
        broken.opcua["namespace_uris"][key] = "http://NoSuchNamespace"
        probe = _client(broken, recorder)
        try:
            await probe._connect()
        except NamespaceNotFound as exc:
            checks.ok(True, f"a wrong {key} URI raises NamespaceNotFound",
                      str(exc).split(".")[0])
        except Exception as exc:  # pragma: no cover - would be a defect
            checks.ok(False, f"a wrong {key} URI raises NamespaceNotFound", repr(exc))
        else:
            checks.ok(False, f"a wrong {key} URI raises NamespaceNotFound",
                      "the connect succeeded — something fell back to an index")
        finally:
            await probe._disconnect("conformance probe")


async def run(args: argparse.Namespace) -> int:
    cfg = config_mod.load(args.config)
    if args.endpoint:
        cfg.opcua["endpoint"] = args.endpoint
    checks = Checks()
    print("bridge connect conformance — bridge-design.md §3.1 / §3.2")
    print(f"  config   {cfg.path}")
    print(f"  endpoint {cfg.opcua['endpoint']}")
    print(f"  evidence {args.evidence_csv}")

    recorder = Recorder(args.evidence_csv, flush_interval_s=1.0)
    client = _client(cfg, recorder)
    try:
        await client._connect()   # the bridge's own session establishment
        await check_namespaces(checks, client, cfg)
        await check_addressing_is_not_accidental(checks, client)
        granted_ms, keepalive_s = check_session_parameters(checks, client, cfg)
        if not args.skip_idle:
            await check_keepalive_in_force(
                checks, client, cfg, recorder, granted_ms, keepalive_s)
    finally:
        await client._disconnect("conformance check done")

    await check_missing_namespace_fails(checks, cfg, recorder)
    recorder.close()
    return checks.result()


def main() -> int:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(
        description="check the bridge connect logic against bridge-design.md §3.1/§3.2")
    parser.add_argument("--config", default=os.path.join(here, "config", "bridge.yaml"))
    parser.add_argument("--endpoint", default=None, help="override opcua.endpoint")
    parser.add_argument("--evidence-csv",
                        default=os.path.join(here, "evidence", "connect-conformance-latest.csv"))
    parser.add_argument("--skip-idle", action="store_true",
                        help="skip the idle keep-alive measurement (it takes > the granted timeout)")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
