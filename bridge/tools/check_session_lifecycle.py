#!/usr/bin/env python3
"""Check the bridge's session lifecycle against the three failures the live run
of 2026-07-28 produced (LESSONS, brief m3-35).

    1. IN-FLIGHT REQUEST FAILURE. A CPU download dropped the session while a
       read was in flight and the process died instead of reconnecting: the
       exception `asyncua` raised was not one of the anticipated session error
       types. Checked twice here — once by killing the double under a running
       cycle, and once by injecting the exact exception `asyncua`'s
       `UASocketProtocol.send_request` produces for an in-flight failure whose
       socket state has not yet flipped:

           except Exception as ex:
               if self.state is not UASocketState.OPEN:
                   raise ConnectionError("Connection is closed") from None
               raise Exception("Unhandled exception while sending request to OPC UA server") from ex

       A bare `Exception`. No caller's error tuple contains it.

    2. SERVER RESTART UNDER A SURVIVING SESSION. A CPU warm restart reverted
       every input to its start value; write-on-change never repaired the
       contacts whose slot values had not changed, so the PLC read open stop
       circuits for minutes. Checked in both flavours: a restart that drops the
       session (the double killed and relaunched) and one that does not (the
       double's S5 warm-restart scaffolding), because only the second needs the
       heartbeat read-back to be noticed at all.

    3. EVIDENCE FILE TRUNCATION. `--evidence-csv` truncated at every start and
       seven restarts erased a day of 20 Hz data. The naming rule and the
       refusal are checked here; that two consecutive *process* starts produce
       two files is recorded in `EVIDENCE_LIFECYCLE.md`, because it is a property
       of the process, not of this module.

Like `check_connect_conformance.py`, this harness drives the bridge's own
`PlcClient` — its `run()` loop, its reconnect path, its write cache. Nothing in
`amr_bridge/` is stubbed or special-cased for a test. Two things stand in for
the world outside the bridge, and neither is bridge code:

* the **slots** are filled by this harness instead of by ROS callbacks. All
  three behaviours live on the OPC UA side of the slots, and `slots.Slot` cannot
  tell who called `put`;
* the **server** is the test double, whose lifecycle this harness owns so it can
  be killed, relaunched and warm-restarted on cue.

Where the real bridge would die, the client task here ends with an exception, so
"the process never exits" is checked as "the run task is still running": in the
bridge `client.run()` is awaited by `asyncio.run` in `main`, and an exception out
of it is process death.

Run it against the test double only, never against PLCSIM (`bridge-design.md`
§10). The harness starts and stops the double itself:

    "$VENV/bin/python" bridge/tools/check_session_lifecycle.py
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asyncua import Client  # noqa: E402

from amr_bridge import config as config_mod  # noqa: E402
from amr_bridge.instrumentation import (  # noqa: E402
    Counters,
    EvidenceFileExists,
    Recorder,
    session_csv_path,
)
from amr_bridge.opcua_side import PlcClient  # noqa: E402
from amr_bridge.slots import SlotSet  # noqa: E402

#: The exception text `asyncua` raises for an in-flight request failure while the
#: socket still reads as OPEN. Quoted from
#: `asyncua/client/ua_client.py::UASocketProtocol.send_request` (asyncua 2.0.1).
ASYNCUA_INFLIGHT_MESSAGE = "Unhandled exception while sending request to OPC UA server"

#: Slot values the harness feeds. The two stop circuits are TRUE on purpose:
#: those are the values whose reversion to the start value FALSE the live run
#: left unrepaired, and FALSE is "stop circuit open" (opcua-nodes.md §9.3).
SLOT_VALUES: dict[str, object] = {
    "ConveyorBeltPosition": 1.25,
    "ConveyorBeltSpeed": 0.35,
    "ProductSensorRange": 0.42,
    "PanelStartPressed": False,
    "PanelResetPressed": False,
    "PanelStopCircuitClosed": True,
    "PanelProcessStopCircuitClosed": True,
}

#: Start values the double reverts to (bridge-design.md §6.3). Every one of them
#: differs from the value above, so a repaired image is distinguishable from a
#: reverted one on every node.
REVERTED_VALUES: dict[str, object] = {
    "ConveyorBeltPosition": 0.0,
    "ConveyorBeltSpeed": 0.0,
    "ProductSensorRange": 0.0,
    "PanelStartPressed": False,
    "PanelResetPressed": False,
    "PanelStopCircuitClosed": False,
    "PanelProcessStopCircuitClosed": False,
}


class Checks:
    def __init__(self) -> None:
        self.failures = 0

    def ok(self, passed: bool, statement: str, detail: str = "") -> None:
        if passed:
            print(f"   ok   {statement}" + (f" — {detail}" if detail else ""), flush=True)
        else:
            self.failures += 1
            print(f"   FAIL {statement}" + (f" — {detail}" if detail else ""), flush=True)

    def result(self) -> int:
        print("\nRESULT:", "PASS" if self.failures == 0 else f"FAIL ({self.failures})")
        return 1 if self.failures else 0


# ---------------------------------------------------------------------------- #
# The double's lifecycle — owned here so it can be killed and relaunched
# ---------------------------------------------------------------------------- #


class Double:
    """The test double as a child process. Scaffolding around scaffolding."""

    def __init__(self, python: str, script: str, endpoint: str, workdir: str) -> None:
        self._python = python
        self._script = script
        self.endpoint = endpoint
        self.warm_restart_file = os.path.join(workdir, "warm_restart_trigger")
        self.observe_stem = os.path.join(workdir, "double-observe.csv")
        self._log_path = os.path.join(workdir, "double.log")
        self._proc: Optional[subprocess.Popen] = None
        self.starts = 0

    async def start(self) -> None:
        self.starts += 1
        log = open(self._log_path, "a", encoding="utf-8")
        log.write(f"\n===== double start {self.starts} at {time.strftime('%H:%M:%S')} =====\n")
        log.flush()
        self._proc = subprocess.Popen(
            [self._python, self._script,
             "--endpoint", self.endpoint,
             "--observe-csv", self.observe_stem,
             "--warm-restart-file", self.warm_restart_file],
            stdout=log, stderr=subprocess.STDOUT,
        )
        await self._await_endpoint(up=True, timeout_s=30.0)

    def kill(self) -> None:
        """SIGKILL: no goodbye, no clean session close — a server that vanishes."""
        if self._proc is not None and self._proc.poll() is None:
            self._proc.send_signal(signal.SIGKILL)
            self._proc.wait(timeout=10)

    async def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.send_signal(signal.SIGINT)
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.kill()
        self._proc = None

    def warm_restart(self) -> None:
        """Touch the S5 trigger: every node back to its start value, in place,
        with the session left up."""
        with open(self.warm_restart_file, "w", encoding="utf-8") as handle:
            handle.write("1\n")

    async def _await_endpoint(self, up: bool, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            reachable = await _endpoint_reachable(self.endpoint)
            if reachable == up:
                return
            await asyncio.sleep(0.2)
        raise TimeoutError(f"endpoint {self.endpoint} never came {'up' if up else 'down'}")

    def observe_files(self) -> list[str]:
        """One observation file per double start, oldest first."""
        stem, ext = os.path.splitext(self.observe_stem)
        directory = os.path.dirname(stem) or "."
        return [
            os.path.join(directory, name)
            for name in sorted(os.listdir(directory))
            if name.startswith(os.path.basename(stem)) and name.endswith(ext)
        ]

    def observe_rows(self, latest_only: bool = False) -> list[dict]:
        """Rows the double observed: every start's, or only the current one's."""
        rows: list[dict] = []
        files = self.observe_files()
        for path in (files[-1:] if latest_only else files):
            with open(path, newline="", encoding="utf-8") as handle:
                rows.extend(csv.DictReader(handle))
        return rows


async def _endpoint_reachable(endpoint: str) -> bool:
    client = Client(url=endpoint, timeout=2)
    try:
        await client.connect()
    except Exception:
        return False
    try:
        await client.disconnect()
    except Exception:
        pass
    return True


async def read_back_inputs(cfg: config_mod.Config) -> dict[str, object]:
    """Read the seven inputs and the heartbeat over an INDEPENDENT read-only
    session, so what is checked is the server's own values rather than anything
    the bridge's session is holding. Addressed through `cfg.browse_path`, the
    bridge's own addressing helper, so no path is duplicated here."""
    client = Client(url=cfg.opcua["endpoint"], timeout=4)
    await client.connect()
    try:
        indices = {
            key: await client.get_namespace_index(uri)
            for key, uri in cfg.namespace_uris.items()
        }
        values: dict[str, object] = {}
        for key in list(config_mod.INPUT_KEYS) + [config_mod.HEARTBEAT_KEY]:
            path = [f"{indices[ns]}:{name}" for ns, name in cfg.browse_path(key)]
            values[key] = await (await client.nodes.objects.get_child(path)).read_value()
        return values
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------- #
# The bridge under test
# ---------------------------------------------------------------------------- #


class Harness:
    """A `PlcClient` with its slots fed by this harness instead of by ROS."""

    def __init__(self, cfg: config_mod.Config, recorder: Recorder) -> None:
        self.cfg = cfg
        self.recorder = recorder
        self.counters = Counters()
        self.slots = SlotSet(config_mod.INPUT_KEYS)
        self.published: list[float] = []
        self.client = PlcClient(cfg, self.slots, recorder, self.counters, self._publish)
        self.task: Optional[asyncio.Task] = None
        self._feeder: Optional[asyncio.Task] = None

    def _publish(self, value: float) -> int:
        self.published.append(value)
        return time.monotonic_ns()

    def fill_slots(self) -> None:
        recv = time.monotonic_ns()
        for key, value in SLOT_VALUES.items():
            self.slots[key].put(value, recv, None)

    async def _feed(self) -> None:
        """The cell, standing in for Gazebo: fresh analog samples at 20 Hz. The
        values do not change — a repaired image must be distinguishable from a
        reverted one, and a moving value would make that ambiguous."""
        while True:
            self.fill_slots()
            await asyncio.sleep(0.05)

    def start(self) -> None:
        self.fill_slots()
        self._feeder = asyncio.ensure_future(self._feed())
        self.task = asyncio.ensure_future(self.client.run())

    @property
    def alive(self) -> bool:
        return self.task is not None and not self.task.done()

    def death(self) -> str:
        if self.task is None or not self.task.done():
            return ""
        exc = self.task.exception()
        return "returned cleanly" if exc is None else f"{type(exc).__name__}: {exc}"

    async def stop(self) -> None:
        if self._feeder is not None:
            self._feeder.cancel()
        self.client.stop()
        if self.task is not None:
            try:
                await asyncio.wait_for(self.task, timeout=15)
            except Exception:
                pass


class _RaisingNode:
    """Fault injection at the session boundary: one read that fails the way
    `asyncua` fails an in-flight request. Not a stub of bridge code — it stands
    in for the server-side half of a session that has just gone away, and the
    bridge calls it exactly as it calls a resolved node."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.calls = 0

    async def read_value(self):
        self.calls += 1
        raise self._exc

    async def write_value(self, _value):
        self.calls += 1
        raise self._exc


async def await_until(
    predicate: Callable[[], bool], timeout_s: float, description: str
) -> tuple[bool, float]:
    """Bounded foreground polling. Never a detached wait."""
    started = time.monotonic()
    deadline = started + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True, time.monotonic() - started
        await asyncio.sleep(0.02)
    print(f"        (timed out after {timeout_s:.1f}s waiting for {description})", flush=True)
    return False, time.monotonic() - started


def evidence_rows(recorder: Recorder, event: str, name: str = "") -> list[dict]:
    recorder.maybe_flush(force=True)
    rows = []
    with open(recorder.path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["event"] == event and (not name or row["name"] == name):
                rows.append(row)
    return rows


# ---------------------------------------------------------------------------- #
# 1. an in-flight request failure reconnects instead of killing the process
# ---------------------------------------------------------------------------- #


async def check_kill_under_a_running_cycle(
    checks: Checks, harness: Harness, double: Double
) -> None:
    print("\n1a. §8.1 — the double killed under a running 50 ms cycle", flush=True)
    before = dict(
        reconnects=harness.counters.reconnects,
        heartbeats=harness.counters.heartbeat_writes,
        read_errors=harness.counters.read_errors,
        write_errors=harness.counters.write_errors,
    )
    double.kill()
    print(f"        SIGKILL sent to the double (pid gone), cycle was at heartbeat "
          f"{harness.client.heartbeat}", flush=True)

    seen, _ = await await_until(
        lambda: harness.counters.reconnects > before["reconnects"], 20.0,
        "the bridge to mark the session broken")
    checks.ok(seen, "the failure was routed into the §8.1 reconnect path")
    checks.ok(harness.alive, "the run loop is still running — in the bridge this is the "
                             "process still being alive", harness.death() or "task running")
    at_the_wire = (
        harness.counters.read_errors > before["read_errors"]
        or harness.counters.write_errors > before["write_errors"]
    )
    checks.ok(at_the_wire,
              "the failure came out of a request the cycle had in flight, not out of a "
              "later connect attempt",
              f"read_errors {before['read_errors']}->{harness.counters.read_errors}, "
              f"write_errors {before['write_errors']}->{harness.counters.write_errors}")
    broken = evidence_rows(harness.recorder, "session", "broken")
    checks.ok(bool(broken), "the broken session is in the evidence file",
              broken[-1]["note"] if broken else "no row")
    published_before = len(harness.published)
    await asyncio.sleep(1.0)
    checks.ok(len(harness.published) == published_before,
              "nothing was published to the cell while disconnected (§8.3 N3)",
              f"{len(harness.published) - published_before} publishes in 1.0 s of outage")

    await double.start()
    print(f"        double relaunched on {double.endpoint}", flush=True)
    resumed, waited = await await_until(
        lambda: harness.counters.heartbeat_writes > before["heartbeats"] + 5, 30.0,
        "the heartbeat to advance again on a new session")
    checks.ok(resumed, "the cycle resumed on the double's return, in the same process",
              f"{waited:.1f}s after the double came back")
    checks.ok(harness.counters.session_outages >= 1,
              "the outage is counted, so the gap in the 20 Hz evidence is stated",
              f"{harness.counters.session_outages} outage(s), longest "
              f"{harness.counters.session_outage_max_ns / 1e9:.2f}s")
    resumed_rows = evidence_rows(harness.recorder, "session", "resumed")
    checks.ok(bool(resumed_rows), "the evidence file carries the gap as a row",
              f"{int(resumed_rows[-1]['interval_ns']) / 1e9:.2f}s with no cycle"
              if resumed_rows else "no row")


async def check_injected_inflight_exception(
    checks: Checks, harness: Harness
) -> None:
    print("\n1b. §8.1 — the exact exception asyncua raises for an in-flight failure", flush=True)
    print(f"        injecting Exception({ASYNCUA_INFLIGHT_MESSAGE!r}) into the "
          f"ConveyorSpeedCommand read of one cycle", flush=True)
    before = dict(
        reconnects=harness.counters.reconnects,
        unexpected=harness.counters.unexpected_session_errors,
        unrouted=harness.counters.unrouted_cycle_errors,
        heartbeats=harness.counters.heartbeat_writes,
    )
    shim = _RaisingNode(Exception(ASYNCUA_INFLIGHT_MESSAGE))
    # The bridge re-resolves every NodeId on the next session (§8.1), so the shim
    # is gone by the time the reconnect completes: nothing has to undo it.
    harness.client._nodes[config_mod.OUTPUT_KEY] = shim

    routed, _ = await await_until(
        lambda: harness.counters.reconnects > before["reconnects"], 15.0,
        "the injected bare Exception to be routed")
    checks.ok(routed, "a bare `Exception` from a request in flight breaks the session "
                      "instead of leaving the process")
    checks.ok(harness.alive, "the run loop survived it", harness.death() or "task running")
    checks.ok(harness.counters.unexpected_session_errors > before["unexpected"],
              "it is counted as an unanticipated session error, so the evidence names "
              "the failure class",
              f"unexpected_session_errors {before['unexpected']}->"
              f"{harness.counters.unexpected_session_errors}")
    checks.ok(harness.counters.unrouted_cycle_errors == before["unrouted"],
              "it was routed by the step that raised it, not by the last-resort guard "
              "in run()",
              f"unrouted_cycle_errors stayed at {harness.counters.unrouted_cycle_errors}")
    unexpected_rows = evidence_rows(harness.recorder, "session", "unexpected_error")
    checks.ok(bool(unexpected_rows), "the exception type is in the evidence file",
              unexpected_rows[-1]["value"] if unexpected_rows else "no row")
    resumed, waited = await await_until(
        lambda: harness.counters.heartbeat_writes > before["heartbeats"] + 5, 30.0,
        "the cycle to resume after the injected failure")
    checks.ok(resumed, "the cycle resumed on a new session", f"{waited:.1f}s later")
    checks.ok(shim.calls == 1,
              "the shim was called once and is gone: every NodeId was re-resolved on "
              "the new session (§8.1)", f"{shim.calls} call(s)")


# ---------------------------------------------------------------------------- #
# 2. a restarted server gets its whole input image rewritten
# ---------------------------------------------------------------------------- #


def _truthy(text: str) -> bool:
    return str(text).strip().lower() in ("true", "1")


def _matches_text(image: dict[str, str], expected: dict[str, object]) -> bool:
    """Compare a CSV row's text against an expected image."""
    for key, want in expected.items():
        text = image.get(key, "")
        if isinstance(want, bool):
            if _truthy(text) != want:
                return False
        else:
            try:
                if abs(float(text) - float(want)) > 1e-6:
                    return False
            except ValueError:
                return False
    return True


def _image_matches(values: dict[str, object], expected: dict[str, object]) -> tuple[bool, str]:
    wrong = []
    for key, want in expected.items():
        got = values.get(key)
        if isinstance(want, bool) or isinstance(got, bool):
            same = bool(got) == bool(want)
        else:
            same = got is not None and abs(float(got) - float(want)) < 1e-6
        if not same:
            wrong.append(f"{key}={got!r} (wanted {want!r})")
    return not wrong, "; ".join(wrong)


async def check_rewrite_after_a_new_session(
    checks: Checks, harness: Harness, cfg: config_mod.Config, double: Double
) -> None:
    print("\n2a. §8.1 — a restart that drops the session: every input rewritten in the "
          "first cycle of the new one", flush=True)
    # The double relaunched in 1a came up with its start values, and the bridge
    # has been running on the new session since. Read the server back.
    values = await read_back_inputs(cfg)
    matched, wrong = _image_matches(values, SLOT_VALUES)
    checks.ok(matched, "an independent read-only session sees the slot values, not the "
                       "double's start values", wrong or f"BridgeHeartbeat={values['BridgeHeartbeat']}")
    rewritten = evidence_rows(harness.recorder, "session", "input_image_rewritten")
    checks.ok(bool(rewritten) and rewritten[-1]["value"] == f"{len(config_mod.INPUT_KEYS)}/"
              f"{len(config_mod.INPUT_KEYS)}",
              "the rewrite of the whole image is recorded, one cycle, all seven nodes",
              rewritten[-1]["value"] if rewritten else "no row")
    print("        the relaunched double's own view, from its first sample (5 Hz):",
          flush=True)
    for row in double.observe_rows(latest_only=True)[:12]:
        image = {key: row[key] for key in config_mod.INPUT_KEYS}
        tag = "start values" if _matches_text(image, REVERTED_VALUES) else (
            "as written" if _matches_text(image, SLOT_VALUES) else "mixed")
        print(f"          {row['wall_utc']}  HB={row['BridgeHeartbeat']:>6}  "
              f"stop={row['PanelStopCircuitClosed']:>5} "
              f"pstop={row['PanelProcessStopCircuitClosed']:>5}  [{tag}]", flush=True)


async def check_rewrite_after_a_warm_restart(
    checks: Checks, harness: Harness, cfg: config_mod.Config, double: Double
) -> None:
    print("\n2b. §8.1 — a warm restart that does NOT drop the session (the 2026-07-28 "
          "failure)", flush=True)
    before = dict(
        restarts=harness.counters.server_restarts_detected,
        reconnects=harness.counters.reconnects,
        rewritten=harness.counters.inputs_rewritten_after_restart,
    )
    # Confirm the starting point: the server holds the slot values.
    values = await read_back_inputs(cfg)
    matched, wrong = _image_matches(values, SLOT_VALUES)
    checks.ok(matched, "before the restart the server holds the slot values", wrong)
    heartbeat_before = values[config_mod.HEARTBEAT_KEY]

    triggered_ns = time.monotonic_ns()
    triggered_utc = datetime.now(timezone.utc)
    double.warm_restart()
    print(f"        S5 warm restart triggered at {triggered_utc.isoformat(timespec='milliseconds')}: "
          f"every node back to its start value in place (BridgeHeartbeat was "
          f"{heartbeat_before})", flush=True)

    detected, latency_s = await await_until(
        lambda: harness.counters.server_restarts_detected > before["restarts"], 15.0,
        "the heartbeat read-back to notice the revert")
    checks.ok(detected, "the bridge detected the restart from its own heartbeat reading "
                        "back a value it did not write", f"{latency_s * 1000:.0f} ms after the trigger")
    checks.ok(harness.counters.reconnects == before["reconnects"],
              "no session was lost, so nothing but the read-back could have noticed",
              f"reconnects stayed at {harness.counters.reconnects}")

    repaired, repair_s = await await_until(
        lambda: harness.counters.inputs_rewritten_after_restart > before["rewritten"], 10.0,
        "the input image to be rewritten")
    checks.ok(repaired, "the write cache was invalidated and the image rewritten",
              f"{harness.counters.inputs_rewritten_after_restart - before['rewritten']} nodes "
              f"written, {(time.monotonic_ns() - triggered_ns) / 1e6:.0f} ms after the trigger")
    rewritten = evidence_rows(harness.recorder, "session", "input_image_rewritten")
    checks.ok(bool(rewritten) and rewritten[-1]["value"] == f"{len(config_mod.INPUT_KEYS)}/"
              f"{len(config_mod.INPUT_KEYS)}",
              "all seven nodes were written in ONE cycle, not repaired gradually",
              rewritten[-1]["value"] if rewritten else "no row")

    values = await read_back_inputs(cfg)
    matched, wrong = _image_matches(values, SLOT_VALUES)
    checks.ok(matched, "an independent read-only session sees the whole image repaired, "
                       "the two stop circuits included", wrong)

    # The double's own observation log is the server-side view — what "the PLC
    # sees". It samples at 5 Hz and the repair takes about one 50 ms cycle, so it
    # may well never sample the reverted image at all; the printed window says
    # which, and the bridge reading a heartbeat it did not write is the proof that
    # the revert happened whether the 5 Hz log caught it or not.
    await asyncio.sleep(1.0)  # let the 5 Hz log get past the event
    rows = double.observe_rows()
    window = [row for row in rows
              if row["wall_utc"] >= (triggered_utc - timedelta(seconds=0.6)).isoformat(
                  timespec="milliseconds")]
    stop_series = [row["PanelStopCircuitClosed"] for row in rows]
    checks.ok(bool(rows) and _truthy(stop_series[-1]),
              "the double's own 5 Hz log ends with PanelStopCircuitClosed closed again",
              f"last sample {stop_series[-1] if stop_series else 'none'}")
    print("        the double's view around the restart (5 Hz):", flush=True)
    for row in window[:14]:
        image = {key: row[key] for key in config_mod.INPUT_KEYS}
        tag = "reverted" if _matches_text(image, REVERTED_VALUES) else (
            "as written" if _matches_text(image, SLOT_VALUES) else "mixed")
        print(f"          {row['wall_utc']}  HB={row['BridgeHeartbeat']:>6}  "
              f"stop={row['PanelStopCircuitClosed']:>5} "
              f"pstop={row['PanelProcessStopCircuitClosed']:>5}  [{tag}]", flush=True)


# ---------------------------------------------------------------------------- #
# 3. no evidence file is ever truncated
# ---------------------------------------------------------------------------- #


async def check_evidence_files(checks: Checks, workdir: str) -> None:
    print("\n3. evidence files: a per-session name, and a refusal instead of a "
          "truncation", flush=True)
    stem = os.path.join(workdir, "truncation-probe.csv")

    first = Recorder(stem, flush_interval_s=0.01)
    first.row("probe", "session-one")
    first.close()
    checks.ok(first.path != stem, "the path given is a stem; the file written names the "
                                  "session", os.path.basename(first.path))

    # Two consecutive starts differ by pid (and usually by second), so the second
    # start writes its own file and cannot touch the first.
    second_path = session_csv_path(stem, pid=os.getpid() + 1)
    with open(second_path, "x", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(["event"])
    checks.ok(second_path != first.path and os.path.exists(first.path)
              and os.path.exists(second_path),
              "two starts on one stem produce two files",
              f"{os.path.basename(first.path)} + {os.path.basename(second_path)}")
    with open(first.path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    checks.ok(len(rows) == 1 and rows[0]["name"] == "session-one",
              "the first session's rows are still there after the second started",
              f"{len(rows)} row(s)")

    # And if a name ever does collide, the answer is a refusal, never a truncate.
    # Line the probe up just after a UTC second boundary so the name computed
    # here and the name the Recorder computes cannot straddle one.
    collide_stem = os.path.join(workdir, "collision-probe.csv")
    await asyncio.sleep(1.02 - (time.time() % 1.0))
    collide_path = session_csv_path(collide_stem)
    with open(collide_path, "x", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(["event", "name"])
        csv.writer(handle).writerow(["probe", "must-survive"])
    try:
        Recorder(collide_stem)
    except EvidenceFileExists as exc:
        checks.ok(True, "an existing per-session file is refused, not truncated",
                  str(exc).split(";")[0])
    else:
        checks.ok(False, "an existing per-session file is refused, not truncated",
                  "the Recorder was constructed on top of an existing file")
    with open(collide_path, newline="", encoding="utf-8") as handle:
        survivors = list(csv.DictReader(handle))
    checks.ok(len(survivors) == 1 and survivors[0]["name"] == "must-survive",
              "the refused file still holds its rows", f"{len(survivors)} row(s)")


# ---------------------------------------------------------------------------- #


async def run(args: argparse.Namespace) -> int:
    cfg = config_mod.load(args.config)
    cfg.opcua["endpoint"] = args.endpoint
    if args.endpoint.startswith("opc.tcp://192.168."):
        print("refusing to run against what looks like the commissioned PLCSIM "
              "endpoint; this harness kills and restarts its server "
              "(bridge-design.md §10)")
        return 2

    os.makedirs(args.workdir, exist_ok=True)
    checks = Checks()
    print("bridge session-lifecycle conformance — brief m3-35, LESSONS 2026-07-28")
    print(f"  config   {cfg.path}")
    print(f"  endpoint {cfg.opcua['endpoint']}  (TEST DOUBLE, started by this harness)")
    print(f"  workdir  {args.workdir}")

    recorder = Recorder(args.evidence_csv, flush_interval_s=0.5)
    print(f"  evidence {recorder.path}")

    double = Double(args.python, args.double, cfg.opcua["endpoint"], args.workdir)
    harness = Harness(cfg, recorder)
    try:
        await double.start()
        harness.start()
        started, waited = await await_until(
            lambda: harness.counters.heartbeat_writes > 10, 30.0,
            "the first session to establish and the heartbeat to start")
        checks.ok(started, "0. the bridge connected to the double and the heartbeat is "
                           "advancing", f"{harness.counters.heartbeat_writes} writes after "
                                        f"{waited:.1f}s")
        if not started:
            return checks.result()

        await check_kill_under_a_running_cycle(checks, harness, double)
        await check_rewrite_after_a_new_session(checks, harness, cfg, double)
        await check_injected_inflight_exception(checks, harness)
        await check_rewrite_after_a_warm_restart(checks, harness, cfg, double)
        await check_evidence_files(checks, args.workdir)

        # What the restart detection costs: it is one extra read per 50 ms cycle,
        # and a claim about its cost belongs in the same run that made it.
        cycles = [int(row["interval_ns"]) for row in evidence_rows(recorder, "R1", "cycle")]
        connected = sorted(value for value in cycles if value < 500_000_000)
        readbacks = sorted(
            int(row["interval_ns"])
            for row in evidence_rows(recorder, "read_rt", config_mod.HEARTBEAT_KEY)
        )
        print("\nwhat the read-back costs (this run, against the double):")
        if connected:
            print(f"        cycle interval median {connected[len(connected) // 2] / 1e6:.1f} ms "
                  f"over {len(connected)} cycles, {harness.counters.cycle_overruns} overrun(s)")
        if readbacks:
            print(f"        heartbeat read-back median {readbacks[len(readbacks) // 2] / 1e6:.2f} ms, "
                  f"max {readbacks[-1] / 1e6:.2f} ms, n={len(readbacks)}")

        print("\ncounters at the end of the run:")
        for name, value in harness.counters.as_rows():
            if value:
                print(f"        {name} = {value}")
    finally:
        await harness.stop()
        await double.stop()
        recorder.close()
        print(f"\nevidence: {recorder.path}")
        print(f"double log: {os.path.join(args.workdir, 'double.log')}")
    return checks.result()


def main() -> int:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(
        description="check the bridge session lifecycle against LESSONS 2026-07-28")
    parser.add_argument("--config", default=os.path.join(here, "config", "bridge.yaml"))
    parser.add_argument("--endpoint", default="opc.tcp://127.0.0.1:4841/amr-agent/celldouble/",
                        help="the TEST DOUBLE endpoint. This harness kills its server, so "
                             "it must never be pointed at PLCSIM (bridge-design.md §10)")
    parser.add_argument("--evidence-csv",
                        default=os.path.join(here, "evidence", "session-lifecycle.csv"))
    parser.add_argument("--workdir", default="/tmp/amr-session-lifecycle",
                        help="scratch directory for the double's log, its observation "
                             "file and the truncation probe")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--double",
                        default=os.path.join(here, "test_double", "plc_test_double.py"))
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
