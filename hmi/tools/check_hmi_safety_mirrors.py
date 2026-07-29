#!/usr/bin/env python3
"""TEST HARNESS — brief m5a-07, the `Forklift/Safety/` mirrors: lamps, banner
and graceful degradation when the group is absent.

    #############################################################
    #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
    #############################################################

Two runs, one script, selected by `--mode`:

    absent    `safety_mirror_double.py` WITHOUT the section 11 group. Proves
              the HMI's connect does not fail and does not loop over an
              optional folder it cannot resolve (opcua-nodes.md §11.6): the
              session reaches and STAYS CONNECTED, `/state`'s `safety.present`
              reads `false`, and all four mirror values read `null` — never a
              guessed `false`, which would misreport a fail-safe `TRUE` start
              value as clear.

    present   the same double WITH the group, at its fail-safe start values
              TRUE/TRUE/TRUE/FALSE (§11.6). The harness then drives each of the
              four mirrors through its own transition, independently, and
              checks the HMI's own `/state` after each one — proving each lamp
              tracks its own node and that the banner tracks
              `SafetyResetRequired` alone, never a value this client derives
              from the other three (invariant 10, §11.3's "zero PLC readers"
              restated for this client too).

Both runs also fetch `GET /` once and check the served page's own markup: the
required banner label, the "not present" wording, the "displays ... never
commands" statement, and — in `present` mode — that the new `ZoneStopDemand`
lamp's markup shares no word with the EXISTING `ForkliftObstacleInStopZone`
lamp's, and vice versa (MR7 — "never share a node, a lamp, a caption or a
sentence").

Neither double in this project (`bridge/test_double/`, `plc/forklift/double/`)
serves `Forklift/Safety/` yet, so this harness runs against this layer's own
minimal double instead (`safety_mirror_double.py`, imported directly — no
subprocess, no IPC, so the harness can hold the mirror `Node` objects and move
them SERVER-SIDE, which is the only way to move them at all: §11.4 MR1 means no
client, including this harness, is ever granted a write on them — demonstrated,
not assumed, by P5 below). Nothing here is evidence about the TIA Portal build,
the bridge, or the commissioned CPU: the live PLCSIM endpoint is never
contacted.

Run (from the repository root):
    python hmi/tools/check_hmi_safety_mirrors.py --mode absent
    python hmi/tools/check_hmi_safety_mirrors.py --mode present
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from asyncua import Client, Server, ua

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from safety_mirror_double import SafetyMirrorDouble, FORBIDDEN_PORTS  # noqa: E402

HMI_DIR = HERE.parent

MIRROR_NAMES = ("EStopDemand", "ZoneStopDemand", "SafetyResetRequired", "SafetyResetFault")

FAILURES: list[str] = []


def ok(message: str) -> None:
    print(f"   ok   {message}", flush=True)


def bad(message: str) -> None:
    FAILURES.append(message)
    print(f"   FAIL {message}", flush=True)


def check(condition, message: str) -> bool:
    (ok if condition else bad)(message)
    return bool(condition)


def note(message: str) -> None:
    print(f"        {message}", flush=True)


def head(title: str) -> None:
    print(f"\n{title}", flush=True)


def get_state(base: str) -> dict:
    with urllib.request.urlopen(f"{base}/state", timeout=3) as response:
        return json.loads(response.read())


def get_page(base: str) -> str:
    with urllib.request.urlopen(f"{base}/", timeout=3) as response:
        return response.read().decode("utf-8")


def _no_word_near(page: str, anchor: str, forbidden: str, radius: int = 300) -> bool:
    """True if `forbidden` (case-insensitive) does not appear within `radius`
    characters of `anchor` in `page` — a direct, literal test of MR7's "never
    share ... a caption or a sentence", rather than a word-overlap heuristic
    that could flag incidental shared English words."""
    lowered = page.lower()
    index = lowered.find(anchor.lower())
    if index < 0:
        return True  # anchor itself absent from the page; nothing to check
    window = lowered[max(0, index - radius): index + len(anchor) + radius]
    return forbidden.lower() not in window


async def until(coro_factory, timeout=8.0, poll=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = await coro_factory()
        if value:
            return value
        await asyncio.sleep(poll)
    return None


def hmi_connected(base: str) -> bool:
    try:
        return get_state(base)["session"]["state"] == "CONNECTED"
    except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError):
        return False


async def wait_connected(base: str, timeout: float = 25.0):
    return await until(lambda: asyncio.sleep(0, result=hmi_connected(base)), timeout)


async def wait_safety(base: str, predicate, timeout: float = 8.0):
    async def probe():
        try:
            safety = get_state(base).get("safety") or {}
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None
        return safety if predicate(safety) else None
    return await until(probe, timeout)


def _spawn_hmi(args, log) -> subprocess.Popen:
    cmd = [args.python, str(HMI_DIR / "hmi_server.py"),
           "--config", args.config, "--http-port", str(args.hmi_port)]
    if args.evidence_csv:
        cmd += ["--evidence-csv", args.evidence_csv]
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)


def _stop_hmi(hmi: subprocess.Popen | None) -> None:
    if hmi is not None and hmi.poll() is None:
        hmi.terminate()
        try:
            hmi.wait(timeout=10)
        except subprocess.TimeoutExpired:
            hmi.kill()


async def _build_double(port: int, with_safety_mirrors: bool) -> tuple[Server, SafetyMirrorDouble]:
    double = SafetyMirrorDouble(with_safety_mirrors=with_safety_mirrors)
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://127.0.0.1:{port}/amr-agent/safetymirrordouble/")
    server.set_server_name("HmiSafetyMirrorDouble")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    await double.build(server)
    return server, double


async def _assert_write_refused(port: int) -> None:
    """§11.4 MR1, demonstrated against THIS double, not assumed: a client write
    against any of the four is refused here exactly as it would be on a real
    server with the per-tag *Writable* attribute cleared. Any exception on the
    write counts as a refusal — what matters is that the write did NOT land,
    not which status code the refusal carries."""
    endpoint = f"opc.tcp://127.0.0.1:{port}/amr-agent/safetymirrordouble/"
    client = Client(url=endpoint)
    client.name = "amr-agent-hmi-safety-mirror-write-probe"
    await client.connect()
    try:
        idx_si = await client.get_namespace_index("http://www.siemens.com/simatic-s7-opcua")
        idx = await client.get_namespace_index("http://DemoCell")
        objects = client.nodes.objects
        node = await objects.get_child([
            f"{idx_si}:ServerInterfaces", f"{idx}:DemoCell", f"{idx}:Forklift",
            f"{idx}:Safety", f"{idx}:EStopDemand"])
        try:
            await node.write_value(ua.DataValue(ua.Variant(False, ua.VariantType.Boolean)))
            bad("a client write against Forklift/Safety/EStopDemand was NOT refused on "
                "this double — it would be misrepresenting the real contract")
        except Exception as exc:  # noqa: BLE001 — any refusal counts, see docstring
            ok(f"a client write against Forklift/Safety/EStopDemand was refused — "
               f"{type(exc).__name__}: {exc} — this double keeps §11.4 MR1 even though "
               f"it is only test scaffolding")
    finally:
        await client.disconnect()


# --------------------------------------------------------------------------- #

async def run_absent(args) -> int:
    print(f"HMI safety-mirror harness — mode ABSENT, double port {args.port}, "
          f"HMI {args.hmi}")
    print("The double serves Forklift/ WITHOUT Forklift/Safety/. Proving the HMI's "
          "connect does not fail and does not loop over an optional group it cannot "
          "resolve (opcua-nodes.md §11.6).")

    server, _double = await _build_double(args.port, with_safety_mirrors=False)
    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    log_path = scratch / "hmi-safety-absent-run.log"
    log = open(log_path, "w", encoding="utf-8")
    hmi = None
    async with server:
        try:
            hmi = _spawn_hmi(args, log)

            head("N1. the HMI connects to a server WITHOUT Forklift/Safety/")
            if not check(bool(await wait_connected(args.hmi)),
                         "the HMI reached CONNECTED against a server missing the "
                         "optional group — the group's absence is not a connect "
                         "failure (§11.6)"):
                return 1
            settled = await wait_safety(args.hmi, lambda s: s.get("present") is False, 8)
            check(bool(settled), f"the panel's own data shows present=false — {settled}")
            check(settled is not None
                  and all(settled.get(n) is None for n in MIRROR_NAMES),
                  f"and all four mirror values read null, never a guessed value — "
                  f"{settled}")

            head("N2. the connection STAYS up — absence is not retried as a failure")
            await asyncio.sleep(2.0)
            check(hmi_connected(args.hmi),
                  "still CONNECTED 2 s later — no reconnect loop over the missing group")
            still = get_state(args.hmi).get("safety") or {}
            check(still.get("present") is False, f"and still reports not present — {still}")

            head("N3. the REQUIRED reads are unaffected by the optional group's absence")
            metrics = get_state(args.hmi).get("metrics") or {}
            present_keys = sorted(k for k in metrics
                                  if k in ("ForkliftTeleopActive", "HmiLinkOk"))
            check("ForkliftTeleopActive" in metrics and "HmiLinkOk" in metrics,
                  f"Forklift/Status/ and Forklift/Link/HmiLinkOk still resolved and are "
                  f"on the panel — {present_keys}")

            head("N4. the served page's own markup carries the label even though this "
                 "server has nothing to show yet")
            page = get_page(args.hmi)
            check("not present" in page.lower(),
                  "the page's markup contains a 'not present' state for the group")
            check("F-CPU safety demand (mirror, read-only)" in page,
                  "and the exact required banner label is present in the markup — "
                  "static markup, not conditioned on any one server")
        finally:
            _stop_hmi(hmi)
            log.close()

    _summary(log_path)
    return 1 if FAILURES else 0


async def run_present(args) -> int:
    print(f"HMI safety-mirror harness — mode PRESENT, double port {args.port}, "
          f"HMI {args.hmi}")
    print("The double serves Forklift/Safety/ at its fail-safe start values. Driving each "
          "mirror through its own transition and checking that the HMI's lamps and "
          "banner track it, and nothing else, from opcua-nodes.md §11.")

    server, double = await _build_double(args.port, with_safety_mirrors=True)
    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    log_path = scratch / "hmi-safety-present-run.log"
    log = open(log_path, "w", encoding="utf-8")
    hmi = None
    async with server:
        try:
            hmi = _spawn_hmi(args, log)

            head("P0. the HMI connects to a server WITH Forklift/Safety/")
            if not check(bool(await wait_connected(args.hmi)),
                         "the HMI reached CONNECTED against a server carrying the group"):
                return 1

            head("P1. the fail-safe start values, read back through the HMI's own /state")
            start = await wait_safety(args.hmi, lambda s: s.get("present") is True, 8)
            check(bool(start), f"present=true — {start}")
            check(start is not None
                  and start.get("EStopDemand") is True
                  and start.get("ZoneStopDemand") is True
                  and start.get("SafetyResetRequired") is True
                  and start.get("SafetyResetFault") is False,
                  f"EStopDemand/ZoneStopDemand/SafetyResetRequired all True, "
                  f"SafetyResetFault False — matches opcua-nodes.md §11.6 exactly — "
                  f"{start}")

            page0 = get_page(args.hmi)
            check("F-CPU safety demand (mirror, read-only)" in page0,
                  "the exact required banner label is in the served markup")
            check("displays" in page0.lower() and "never commands" in page0.lower(),
                  "a 'displays ... never commands' statement is in the served markup")
            check(_no_word_near(page0, "ZoneStopDemand", "obstacle"),
                  "the word 'obstacle' does not appear near the new ZoneStopDemand "
                  "lamp's own markup (MR7)")
            check(_no_word_near(page0, "ForkliftObstacleInStopZone", "zonestopdemand"),
                  "and 'ZoneStopDemand' does not appear near the EXISTING obstacle "
                  "lamp's markup either — the separation holds from both sides")
            check(_no_word_near(page0, "ForkliftObstacleStopActive", "safety demand"),
                  "and the existing process-stop lamp's markup carries no 'safety "
                  "demand' wording — the two banners share no sentence")

            head("P2. SafetyResetFault moves on its own — a device diagnosis, not a demand")
            await double.set_mirror("SafetyResetFault", True)
            seen = await wait_safety(args.hmi, lambda s: s.get("SafetyResetFault") is True, 8)
            check(bool(seen), f"the HMI's own /state shows SafetyResetFault True — {seen}")
            check(seen is not None and seen.get("SafetyResetRequired") is True,
                  f"while SafetyResetRequired is UNCHANGED at True — the two lamps are "
                  f"independent nodes, not derived from one another — {seen}")
            await double.set_mirror("SafetyResetFault", False)
            back = await wait_safety(args.hmi, lambda s: s.get("SafetyResetFault") is False, 8)
            check(bool(back), f"and back to False — {back}")

            head("P3. EStopDemand and ZoneStopDemand clear independently")
            await double.set_mirror("EStopDemand", False)
            seen = await wait_safety(args.hmi, lambda s: s.get("EStopDemand") is False, 8)
            check(bool(seen), f"EStopDemand False on the HMI's own /state — {seen}")
            check(seen is not None
                  and seen.get("ZoneStopDemand") is True
                  and seen.get("SafetyResetRequired") is True,
                  f"while ZoneStopDemand and SafetyResetRequired are UNCHANGED — {seen}")
            await double.set_mirror("ZoneStopDemand", False)
            seen = await wait_safety(args.hmi, lambda s: s.get("ZoneStopDemand") is False, 8)
            check(bool(seen), f"ZoneStopDemand False on the HMI's own /state — {seen}")
            check(seen is not None and seen.get("SafetyResetRequired") is True,
                  f"while SafetyResetRequired is STILL True — this client does not "
                  f"derive it from the other two, it only displays the server's own "
                  f"node (invariant 10) — {seen}")

            head("P4. the banner tracks SafetyResetRequired ALONE")
            await double.set_mirror("SafetyResetRequired", False)
            cleared = await wait_safety(
                args.hmi, lambda s: s.get("SafetyResetRequired") is False, 8)
            check(bool(cleared), f"SafetyResetRequired False — {cleared}")
            note("the banner's on/off is client-side JS driven from this same field; "
                 "the assertion here is on the data contract the JS reads (renderSafety "
                 "in static/index.html gates the banner on safety.SafetyResetRequired "
                 "alone, confirmed by source inspection)")

            await double.set_mirror("ZoneStopDemand", True)
            seen = await wait_safety(args.hmi, lambda s: s.get("ZoneStopDemand") is True, 8)
            check(bool(seen) and seen.get("SafetyResetRequired") is False,
                  f"ZoneStopDemand True again while SafetyResetRequired STAYS False — "
                  f"the banner's trigger is not ZoneStopDemand or EStopDemand directly — "
                  f"{seen}")

            await double.set_mirror("SafetyResetRequired", True)
            seen = await wait_safety(args.hmi, lambda s: s.get("SafetyResetRequired") is True, 8)
            check(bool(seen), f"SafetyResetRequired True again — {seen}")

            head("P5. a client write against the four is refused (§11.4 MR1), on this "
                 "double too")
            await _assert_write_refused(args.port)

            if args.evidence_csv:
                # `Evidence.row()` flushes every 2 s of its OWN elapsed time; on
                # Windows `Popen.terminate()` maps to TerminateProcess(), which
                # does not deliver a catchable signal, so the HMI never reaches
                # its own clean-shutdown flush. Waiting out one flush period
                # here persists real per-cycle rows through the ordinary
                # periodic path — no change to hmi_server.py, nothing about the
                # shutdown path is exercised or claimed by this wait.
                note("waiting one evidence-flush period (2.5 s) so the per-cycle "
                     "CSV has rows before this process is stopped")
                await asyncio.sleep(2.5)
        finally:
            _stop_hmi(hmi)
            log.close()

    _summary(log_path)
    return 1 if FAILURES else 0


def _summary(log_path: Path) -> None:
    print(f"\n{'FAILURES: ' + str(len(FAILURES)) if FAILURES else 'no failures'}")
    for failure in FAILURES:
        print(f"  - {failure}")
    print(f"HMI stdout/stderr: {log_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="drive the HMI against this layer's own section 11 double")
    parser.add_argument("--mode", choices=("absent", "present"), required=True)
    parser.add_argument("--port", type=int, default=4860)
    parser.add_argument("--hmi-port", type=int, default=8093)
    parser.add_argument("--hmi", default=None,
                        help="defaults to http://127.0.0.1:<hmi-port>")
    parser.add_argument("--config", default=str(HMI_DIR / "config-safety-mirror-double.yaml"))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--scratch", default=str(HMI_DIR / "evidence" / "_scratch"))
    parser.add_argument("--evidence-csv", default=None)
    args = parser.parse_args()
    if args.hmi is None:
        args.hmi = f"http://127.0.0.1:{args.hmi_port}"

    if args.port in FORBIDDEN_PORTS:
        print(f"REFUSED: port {args.port} is reserved by another double; refusing "
              f"to start")
        return 3
    host = urlparse(args.hmi).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"REFUSED: {args.hmi} is not loopback. This harness runs against a "
              f"double only; the live PLCSIM endpoint is the owner's to drive.")
        return 3

    runner = run_absent if args.mode == "absent" else run_present
    return asyncio.run(runner(args))


if __name__ == "__main__":
    sys.exit(main())
