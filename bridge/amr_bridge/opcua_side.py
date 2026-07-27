"""The OPC UA half of the bridge: a client, and only ever a client.

invariant 4 / opcua-nodes.md §9.1: the PLC is the server, the bridge is the
client, and that direction is never inverted. This module opens an outbound
session; it never listens on a socket and there is no server mode anywhere in
this package — including against the test double (bridge-design.md §1, §10).

The 50 ms cycle, in the order fixed by §2:

    read Output -> publish to cell -> write Inputs -> write Heartbeat

No step of that cycle consults a process value to decide whether to perform
another step. There is no interlock here.

Two connect-time rules of bridge-design.md are load-bearing and are implemented
in `_connect` and the methods it calls:

* §3.1 — the browse path crosses **two** namespaces
  (`Objects` → `ServerInterfaces` → `DemoCell` → …). Both indices are resolved
  by URI at every session establishment, each path element is qualified with
  the index of the namespace *that element* belongs to, and a missing URI is a
  connect failure — never a fallback index and never a scan of the namespace
  array for a likely-looking entry.
* §3.2 — every session parameter the bridge sends is a **request**. The granted
  session timeout is read back from the session on every connect and the
  keep-alive period is derived from it, never from the request. A grant may land
  either side of the request: the commissioned S7-1500 granted 30 000 ms against
  a 3 600 000 ms request.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Optional

from asyncua import Client, ua

from .config import (
    ANALOG_INPUT_KEYS,
    BOOL_INPUT_KEYS,
    HEARTBEAT_KEY,
    INPUT_KEYS,
    OUTPUT_KEY,
    WRITE_ALLOWLIST,
    Config,
)
from .instrumentation import Counters, Recorder
from .slots import SlotSet

LOG = logging.getLogger("bridge.opcua")

_EXPECTED_TYPE = {
    **{key: ua.VariantType.Float for key in ANALOG_INPUT_KEYS},
    **{key: ua.VariantType.Boolean for key in BOOL_INPUT_KEYS},
    HEARTBEAT_KEY: ua.VariantType.UInt16,
    OUTPUT_KEY: ua.VariantType.Float,
}
_EXPECTED_DATATYPE_NODEID = {
    ua.VariantType.Float: ua.NodeId(ua.ObjectIds.Float),
    ua.VariantType.Boolean: ua.NodeId(ua.ObjectIds.Boolean),
    ua.VariantType.UInt16: ua.NodeId(ua.ObjectIds.UInt16),
}
_DIAGNOSTIC_TYPE_DEFAULT = ua.VariantType.Boolean

_SESSION_ERRORS = (ua.UaError, ConnectionError, OSError, asyncio.TimeoutError, TimeoutError)

#: §3.2 S3 — the keep-alive period is a fixed fraction of the **granted**
#: session timeout, small enough that at least this many keep-alive exchanges
#: fall inside the granted window, so two consecutive lost exchanges cannot by
#: themselves expire the session. It is a property of the derivation, not a
#: tunable: it is deliberately not a config key (§2, §3.2 S3).
KEEPALIVE_EXCHANGES_PER_TIMEOUT = 3


def derive_keepalive_period_s(granted_session_timeout_ms: float) -> float:
    """Keep-alive period from the GRANTED session timeout (§3.2 S3).

    Never from the requested value: a period computed from an un-granted
    3 600 000 ms would never fire inside a granted 30 s window, and the session
    would expire while the bridge believed it had an hour.
    """
    return (float(granted_session_timeout_ms) / KEEPALIVE_EXCHANGES_PER_TIMEOUT) / 1000.0


class WriteNotPermitted(Exception):
    """A write was attempted on a node outside the §9.1 allowlist. This is a
    defect in the bridge, never a runtime condition to work around."""


class SessionBroken(Exception):
    """The OPC UA session failed. Loss of the link is a degraded mode, not a
    safety event (invariant 2)."""


class TypeMismatch(Exception):
    """A resolved node's DataType is not the documented one. A fatal
    configuration error, never something to coerce around (§3)."""


class NamespaceNotFound(Exception):
    """A configured namespace URI is not in the server's namespace array.

    §3.1 N4: this is the intended failure mode (ADR 0006 D4). It is a connect
    failure, retried per §8.1. The bridge does not browse around it, does not
    scan the namespace array for a likely-looking entry, and never falls back
    to an index.
    """


class PlcClient:
    def __init__(
        self,
        cfg: Config,
        slots: SlotSet,
        recorder: Recorder,
        counters: Counters,
        publish_cmd: Callable[[float], int],
    ) -> None:
        self._cfg = cfg
        self._slots = slots
        self._recorder = recorder
        self._counters = counters
        self._publish_cmd = publish_cmd

        self._client: Optional[Client] = None
        self._nodes: dict[str, object] = {}
        # Namespace index per namespace key, resolved by URI at every session
        # establishment and dropped with the session (§3.1 N2, §8.1).
        self._ns_index: dict[str, int] = {}
        # §3.2: the granted session timeout and the keep-alive derived from it.
        # Both are properties of ONE session and are re-read on every new one.
        self._granted_session_timeout_ms: Optional[float] = None
        self._keepalive_period_s: Optional[float] = None
        self._keepalive_task: Optional[asyncio.Task] = None
        self._keepalive_error: Optional[str] = None
        self._last_server_touch_ns = 0

        # Heartbeat state. §8.1: the counter is NOT reset across a reconnect.
        self._heartbeat = 0
        self._heartbeat_started = False
        self._last_missing_logged: list[str] = []

        # Per-session state, cleared on every (re)connect (R4).
        self._written_this_session: set[str] = set()
        self._last_bool_written: dict[str, bool] = {}
        self._last_write_start: dict[str, int] = {}

        self._running = True
        self._connected = False

    # ------------------------------------------------------------------ #
    # Session
    # ------------------------------------------------------------------ #

    async def _connect(self) -> None:
        opc = self._cfg.opcua
        requested_session_ms = self._cfg.requested_session_timeout_ms
        # auto_reconnect stays OFF deliberately. Every new session must be
        # established by THIS method, because a new session is where both
        # namespace indices are re-resolved, every NodeId is re-resolved, the
        # granted timeout is re-read and the keep-alive re-derived (§3.1 N2,
        # §3.2 S4, §8.1). A library that silently re-created the session
        # underneath would skip all of that.
        client = Client(url=opc["endpoint"], timeout=4, auto_reconnect=False)
        client.name = opc["session_name"]
        # S1: a REQUEST. The value in force is whatever the server returns.
        client.session_timeout = requested_session_ms
        requested_channel_ms = client.secure_channel_timeout
        if opc.get("security_policy") and opc["security_policy"] != "none":
            # Certificates live outside the repository (invariant 13).
            await client.set_security_string(
                f"{opc['security_policy']},{opc['certificate_path']},{opc['private_key_path']}"
            )
        await client.connect()
        self._client = client
        self._keepalive_error = None
        self._touch()

        self._read_back_session_parameters(requested_session_ms, requested_channel_ms)
        await self._resolve_namespaces(client)
        await self._resolve_nodes(client)
        await self._verify_types()

        # R4: a new session starts with nothing written and no heartbeat.
        self._written_this_session.clear()
        self._last_bool_written.clear()
        self._last_missing_logged = []
        self._connected = True
        self._start_keepalive()
        self._recorder.row("session", "connect", clock="-", note=opc["endpoint"])
        LOG.info("session established, %d nodes resolved", len(self._nodes))

    def _read_back_session_parameters(
        self, requested_session_ms: int, requested_channel_ms: float
    ) -> None:
        """§3.2 S2/S4/S6 — every session parameter the bridge sent was a request;
        the values in force are the ones the server returned, read back here on
        every new session and used from this point on.

        `asyncua` overwrites `Client.session_timeout` with the CreateSession
        response's `RevisedSessionTimeout` (and `secure_channel_timeout` with the
        channel's `RevisedLifetime`), so reading the attributes back after
        `connect()` reads the granted values. The requested numbers come from the
        config and from before the connect, never from these attributes.
        """
        client = self._client
        assert client is not None
        granted_ms = float(client.session_timeout)
        self._granted_session_timeout_ms = granted_ms
        if granted_ms < requested_session_ms:
            verdict = "clamped BELOW the request"
        elif granted_ms > requested_session_ms:
            verdict = "raised ABOVE the request"
        else:
            verdict = "granted as requested"
        LOG.info(
            "session timeout: requested %d ms, granted %d ms — %s; the granted "
            "value is the only one in force (§3.2 S2)",
            requested_session_ms, granted_ms, verdict,
        )
        granted_channel_ms = float(client.secure_channel_timeout)
        LOG.info(
            "secure channel lifetime: requested %d ms, granted %d ms — revised by "
            "the same mechanism (§3.2 S6)",
            requested_channel_ms, granted_channel_ms,
        )

        # S3: the keep-alive period is derived from the GRANTED value only.
        self._keepalive_period_s = derive_keepalive_period_s(granted_ms)
        LOG.info(
            "keep-alive interval %.3f s = granted %d ms / %d (§3.2 S3); derived "
            "from the request it would have been %.3f s, which is not used",
            self._keepalive_period_s, granted_ms, KEEPALIVE_EXCHANGES_PER_TIMEOUT,
            derive_keepalive_period_s(requested_session_ms),
        )
        self._recorder.row(
            "session", "session_timeout_ms", clock="-", value=granted_ms,
            note=f"granted; requested {requested_session_ms} ({verdict})",
        )
        self._recorder.row(
            "session", "secure_channel_lifetime_ms", clock="-", value=granted_channel_ms,
            note=f"granted; requested {requested_channel_ms:.0f}",
        )
        self._recorder.row(
            "session", "keepalive_period_s", clock="-",
            value=round(self._keepalive_period_s, 4),
            note=f"derived from the granted timeout / {KEEPALIVE_EXCHANGES_PER_TIMEOUT} (§3.2 S3)",
        )

    async def _resolve_namespaces(self, client: Client) -> None:
        """§3.1 N2/N3/N4 — both indices resolved by URI, every session, no
        fallback and no scanning."""
        self._ns_index = {}
        for ns_key, uri in self._cfg.namespace_uris.items():
            try:
                index = await client.get_namespace_index(uri)
            except ValueError as exc:
                raise NamespaceNotFound(
                    f"namespace {uri!r} ({ns_key}) is not published by "
                    f"{self._cfg.opcua['endpoint']}. Not browsed around, not guessed "
                    "from the namespace array and not replaced by an index "
                    "(bridge-design.md §3.1 N4)."
                ) from exc
            self._ns_index[ns_key] = index
            LOG.info("namespace %s (%s) resolved to index %d", uri, ns_key, index)
            self._recorder.row(
                "session", f"namespace_index:{ns_key}", clock="-", value=index, note=uri)

    async def _resolve_nodes(self, client: Client) -> None:
        """NodeIds are resolved by qualified BrowseName path once per session and
        never reused across sessions (§3, §8.1). Each element carries the index
        of the namespace *that element* belongs to (§3.1 N3)."""
        self._nodes = {}
        for key in list(INPUT_KEYS) + [HEARTBEAT_KEY, OUTPUT_KEY] + list(self._cfg.diagnostic_keys):
            path = [f"{self._ns_index[ns_key]}:{name}" for ns_key, name in self._cfg.browse_path(key)]
            self._nodes[key] = await client.nodes.objects.get_child(path)
        LOG.info("browse path: Objects/%s", "/".join(
            f"{self._ns_index[ns_key]}:{name}" for ns_key, name in self._cfg.interface_path))

    async def _verify_types(self) -> None:
        for key, expected in _EXPECTED_TYPE.items():
            actual = await self._nodes[key].read_data_type()
            if actual != _EXPECTED_DATATYPE_NODEID[expected]:
                raise TypeMismatch(
                    f"{key}: server DataType {actual} != documented {expected.name}"
                )
        for key in self._cfg.diagnostic_keys:
            actual = await self._nodes[key].read_data_type()
            if actual != _EXPECTED_DATATYPE_NODEID[_DIAGNOSTIC_TYPE_DEFAULT]:
                raise TypeMismatch(f"{key}: server DataType {actual} != documented Boolean")
        LOG.info("all node DataTypes match opcua-nodes.md §9")

    # ------------------------------------------------------------------ #
    # Keep-alive — connection housekeeping, never a signal gate (§3.2)
    # ------------------------------------------------------------------ #

    def _touch(self) -> None:
        """Note that this session was exercised. Housekeeping only: it records
        no value, and nothing transported depends on it."""
        self._last_server_touch_ns = time.monotonic_ns()

    def _start_keepalive(self) -> None:
        self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())

    async def _cancel_keepalive(self) -> None:
        task, self._keepalive_task = self._keepalive_task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # pragma: no cover - teardown
            pass

    async def _keepalive_loop(self) -> None:
        """One session-activity exchange per derived period while the session is
        idle (§3.2 S3).

        In a healthy run this loop does nothing: the 50 ms cycle touches the
        server ~20 times a second, so the session is never idle for a whole
        period. It matters when the cycle is stalled — which is exactly why the
        period must come from the granted timeout and not from the request.

        It is **not** a signal gate: it reads the standard `Server/ServerStatus/
        State` node, applies it to nothing, and can neither delay nor suppress a
        transported value (§3.2, §1.1).
        """
        period_s = self._keepalive_period_s
        client = self._client
        if period_s is None or client is None:  # pragma: no cover - defensive
            return
        period_ns = int(period_s * 1e9)
        try:
            while self._connected:
                await asyncio.sleep(period_s)
                if not self._connected or self._client is not client:
                    return
                if (time.monotonic_ns() - self._last_server_touch_ns) < period_ns:
                    continue  # the cycle already exercised the session
                try:
                    await client.nodes.server_state.read_value()
                except Exception as exc:
                    self._counters.keepalive_failures += 1
                    self._keepalive_error = f"keep-alive exchange failed: {exc}"
                    LOG.warning("%s — degraded mode, no signal invented", self._keepalive_error)
                    self._recorder.row("session", "keepalive_failed", clock="-", note=str(exc))
                    return
                self._counters.keepalive_probes += 1
                touched = time.monotonic_ns()
                self._recorder.row(
                    "session", "keepalive", t_end_ns=touched,
                    interval_ns=touched - self._last_server_touch_ns,
                    note=f"idle session held open; period {period_s:.3f}s derived from the grant",
                )
                self._last_server_touch_ns = touched
        except asyncio.CancelledError:
            return

    async def _disconnect(self, reason: str) -> None:
        """§7.3 B: on a clean shutdown the bridge writes no farewell value and
        zeroes nothing. It just stops."""
        self._connected = False
        await self._cancel_keepalive()
        # A grant belongs to one session (§3.2 S4); it does not survive it.
        self._granted_session_timeout_ms = None
        self._keepalive_period_s = None
        self._ns_index = {}
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception as exc:  # pragma: no cover - best effort
                LOG.debug("disconnect: %s", exc)
        self._client = None
        self._recorder.row("session", "disconnect", clock="-", note=reason)
        LOG.info("session closed (%s); no farewell value written, nothing zeroed", reason)

    # ------------------------------------------------------------------ #
    # Writes — the single choke point for the §9.1 allowlist
    # ------------------------------------------------------------------ #

    async def _write(self, key: str, value, variant_type: ua.VariantType) -> tuple[int, int]:
        if key not in WRITE_ALLOWLIST:
            raise WriteNotPermitted(
                f"{key} is not client-writable (opcua-nodes.md §9.1). The bridge "
                f"writes only the {len(INPUT_KEYS)} DemoCell/Input/ nodes and "
                "BridgeHeartbeat."
            )
        node = self._nodes[key]
        start = time.monotonic_ns()
        try:
            await node.write_value(ua.DataValue(ua.Variant(value, variant_type)))
        except _SESSION_ERRORS as exc:
            self._counters.write_errors += 1
            raise SessionBroken(f"write {key}: {exc}") from exc
        end = time.monotonic_ns()
        return start, end

    # ------------------------------------------------------------------ #
    # Cycle
    # ------------------------------------------------------------------ #

    async def _cycle(self, cycle_start: int) -> None:
        # A failed keep-alive exchange marks the session broken, like a failed
        # read or write (§8.1, detection row).
        if self._keepalive_error is not None:
            raise SessionBroken(self._keepalive_error)

        # 1. read the PLC output and 2. apply it to the cell, unchanged.
        await self._output_path()

        # 3. write the input image.
        await self._input_path(cycle_start)

        # 4. heartbeat, last, and only once every input has carried a real
        #    sample (R3/R4).
        await self._heartbeat_path()

        # The session was exercised by this cycle, so the keep-alive has nothing
        # to do (§3.2). Housekeeping bookkeeping, no value involved.
        self._touch()

    async def _output_path(self) -> None:
        node = self._nodes[OUTPUT_KEY]
        start = time.monotonic_ns()
        try:
            value = await node.read_value()
        except _SESSION_ERRORS as exc:
            self._counters.read_errors += 1
            raise SessionBroken(f"read {OUTPUT_KEY}: {exc}") from exc
        read_end = time.monotonic_ns()
        self._recorder.row(
            "read_rt", OUTPUT_KEY, t_start_ns=start, t_end_ns=read_end,
            interval_ns=read_end - start, value=value,
        )
        # Float -> float64 widening, m/s unchanged. N1: only a value read in
        # this cycle is published; nothing is replayed or defaulted (§8.3).
        published_at = self._publish_cmd(float(value))
        self._recorder.row(
            "L5", "cmd_speed", t_start_ns=read_end, t_end_ns=published_at,
            interval_ns=published_at - read_end, value=value,
        )

    async def _input_path(self, cycle_start: int) -> None:
        # Analogs: cyclic write of the slot's latest value (§5).
        for key in ANALOG_INPUT_KEYS:
            take_ns = time.monotonic_ns()
            sample = self._slots[key].get()
            if sample is None:
                continue  # R1: no sample, no write. No default, ever.
            start, end = await self._write(key, sample.value, ua.VariantType.Float)
            self._record_write(key, sample, cycle_start, take_ns, start, end)

        # Contacts: write on change, plus a full refresh on every (re)connect
        # (the per-session dict is empty after a connect, so the first cycle
        # with a sample writes all four).
        for key in BOOL_INPUT_KEYS:
            take_ns = time.monotonic_ns()
            sample = self._slots[key].get()
            if sample is None:
                continue
            if self._last_bool_written.get(key) == sample.value and key in self._written_this_session:
                continue
            start, end = await self._write(key, sample.value, ua.VariantType.Boolean)
            self._last_bool_written[key] = bool(sample.value)
            self._record_write(key, sample, cycle_start, take_ns, start, end)

    def _record_write(
        self, key: str, sample, cycle_start: int, take_ns: int, start: int, end: int
    ) -> None:
        self._slots[key].note_written()
        self._written_this_session.add(key)
        # L1 input hold: sample received -> the instant the cycle takes it out
        # of its slot. §9.2 words the end point as "start of the cycle that
        # writes it"; with the ROS callbacks on their own thread a sample can
        # arrive AFTER the cycle start and before the slot is read, which makes
        # the literal definition negative. Both reference points are recorded:
        # L1 (slot-take, the true hold time) and L1cs (the literal cycle-start
        # definition, which is L1 minus the output path of the same cycle and
        # is therefore occasionally negative). Nothing is clipped.
        self._recorder.row(
            "L1", key, t_start_ns=sample.recv_ns, t_end_ns=take_ns,
            interval_ns=take_ns - sample.recv_ns, value=sample.value,
        )
        self._recorder.row(
            "L1cs", key, t_start_ns=sample.recv_ns, t_end_ns=cycle_start,
            interval_ns=cycle_start - sample.recv_ns, value=sample.value,
            note="literal §9.2 reference point; may be negative, not clipped",
        )
        # L2 input write: start of write -> server write response.
        self._recorder.row(
            "L2", key, t_start_ns=start, t_end_ns=end,
            interval_ns=end - start, value=sample.value,
        )
        # L3 = L1 + L2, computed from the same clock, not by adding statistics.
        self._recorder.row(
            "L3", key, t_start_ns=sample.recv_ns, t_end_ns=end,
            interval_ns=end - sample.recv_ns, value=sample.value,
        )
        # R2 per-node achieved write rate.
        previous = self._last_write_start.get(key)
        if previous is not None:
            self._recorder.row(
                "R2", key, t_start_ns=previous, t_end_ns=start,
                interval_ns=start - previous,
            )
        self._last_write_start[key] = start

    async def _heartbeat_path(self) -> None:
        missing = [key for key in INPUT_KEYS if key not in self._written_this_session]
        if missing:
            self._counters.heartbeat_suppressed_cycles += 1
            if missing != self._last_missing_logged:
                # Logged when the set changes, not every cycle.
                LOG.info(
                    "heartbeat withheld: no real sample yet for %s (startup rule R3)",
                    ", ".join(missing),
                )
                self._last_missing_logged = list(missing)
            return
        self._last_missing_logged = []
        if not self._heartbeat_started:
            self._heartbeat_started = True
            LOG.info(
                "startup rule satisfied: all %d DemoCell/Input nodes carry a real "
                "cell sample; heartbeat begins advancing at %d",
                len(INPUT_KEYS), self._heartbeat + 1)
            self._recorder.row("startup", "heartbeat_start", clock="-", value=self._heartbeat + 1)
        self._heartbeat = (self._heartbeat + 1) % 65536
        start, end = await self._write(HEARTBEAT_KEY, self._heartbeat, ua.VariantType.UInt16)
        self._counters.heartbeat_writes += 1
        self._recorder.row(
            "L2", HEARTBEAT_KEY, t_start_ns=start, t_end_ns=end,
            interval_ns=end - start, value=self._heartbeat,
        )

    async def _poll_diagnostics(self) -> None:
        """Read-only, applied to nothing, used in no decision (§4.4)."""
        values = {}
        for key in self._cfg.diagnostic_keys:
            try:
                values[key] = await self._nodes[key].read_value()
            except _SESSION_ERRORS as exc:
                self._counters.read_errors += 1
                raise SessionBroken(f"read {key}: {exc}") from exc
        self._touch()
        LOG.info("PLC diagnostics (logged only): %s", values)
        self._recorder.row("diagnostics", "Status/*", clock="-", value=str(values))

    # ------------------------------------------------------------------ #
    # Run loop
    # ------------------------------------------------------------------ #

    async def run(self, duration_s: Optional[float] = None) -> None:
        period = float(self._cfg.cycle["period_s"])
        status_period = float(self._cfg.cycle["status_poll_period_s"])
        retry = float(self._cfg.opcua["reconnect_interval_s"])
        retry_max = float(self._cfg.opcua["reconnect_backoff_max_s"])
        backoff = retry

        started = time.monotonic()
        next_deadline = time.monotonic()
        last_status = 0.0
        last_cycle_start: Optional[int] = None

        while self._running:
            if duration_s is not None and (time.monotonic() - started) >= duration_s:
                break
            if not self._connected:
                try:
                    await self._connect()
                    backoff = retry
                    next_deadline = time.monotonic()
                except Exception as exc:
                    LOG.warning("connect failed: %s; retrying in %.1fs", exc, backoff)
                    self._recorder.row("session", "connect_failed", clock="-", note=str(exc))
                    if self._client is not None:
                        # The socket and session may already be open — a missing
                        # namespace (§3.1 N4) or an unresolvable NodeId fails
                        # AFTER CreateSession. Close it, or every retry would
                        # leave a session behind on a server that limits them.
                        await self._disconnect("connect failed after the session opened")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, retry_max)
                    continue

            cycle_start = time.monotonic_ns()
            self._counters.cycles += 1
            if last_cycle_start is not None:
                self._recorder.row(
                    "R1", "cycle", t_start_ns=last_cycle_start, t_end_ns=cycle_start,
                    interval_ns=cycle_start - last_cycle_start,
                )
            last_cycle_start = cycle_start

            try:
                await self._cycle(cycle_start)
                if (time.monotonic() - last_status) >= status_period:
                    last_status = time.monotonic()
                    await self._poll_diagnostics()
            except SessionBroken as exc:
                self._counters.reconnects += 1
                LOG.warning("session broken: %s — degraded mode, no signal invented", exc)
                self._recorder.row("session", "broken", clock="-", note=str(exc))
                await self._disconnect("session broken")
                # N3: nothing is published on cmd_speed while disconnected.
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, retry_max)
                continue

            self._recorder.maybe_flush()

            next_deadline += period
            now = time.monotonic()
            if now > next_deadline:
                # Overrun: logged and counted, never compensated. No catch-up
                # burst, no skipped-cycle logic (§2).
                self._counters.cycle_overruns += 1
                self._recorder.row(
                    "overrun", "cycle", interval_ns=int((now - next_deadline) * 1e9))
                next_deadline = now
            else:
                await asyncio.sleep(next_deadline - now)

        await self._disconnect("clean shutdown")

    def stop(self) -> None:
        self._running = False

    @property
    def heartbeat(self) -> int:
        return self._heartbeat

    # --- session facts, for logging and for the conformance harness ---------
    # Read-only views of what THIS session negotiated and resolved. Nothing
    # transported depends on them; they exist so a run can be checked and
    # recorded (tools/check_connect_conformance.py).

    @property
    def namespace_indices(self) -> dict[str, int]:
        return dict(self._ns_index)

    @property
    def opcua_client(self) -> Optional[Client]:
        return self._client

    @property
    def nodes(self) -> dict[str, object]:
        return dict(self._nodes)

    @property
    def counters(self) -> Counters:
        return self._counters

    @property
    def granted_session_timeout_ms(self) -> Optional[float]:
        return self._granted_session_timeout_ms

    @property
    def keepalive_period_s(self) -> Optional[float]:
        return self._keepalive_period_s

    @property
    def resolved_node_keys(self) -> tuple[str, ...]:
        return tuple(self._nodes)
