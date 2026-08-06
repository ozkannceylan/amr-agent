"""The OPC UA half of the bridge: a client, and only ever a client.

invariant 4 / opcua-nodes.md §9.1: the PLC is the server, the bridge is the
client, and that direction is never inverted. This module opens an outbound
session; it never listens on a socket and there is no server mode anywhere in
this package — including against the test double (bridge-design.md §1, §10).

The 50 ms cycle, in the order fixed by §2, with one connection-management step
in front of it:

    verify own heartbeat -> read Output -> publish to cell -> write Inputs
                                                           -> write Heartbeat

No step of that cycle consults a process value to decide whether to perform
another step. There is no interlock here. The leading step reads back the one
node the bridge wrote itself and compares it with what it wrote; it is session
bookkeeping (a restarted server holds a different value), it transports nothing
and it applies nothing to any signal.

Two live-run failures of 2026-07-28 are fixed here and are the reason for the
breadth of the exception handling below (LESSONS):

* a CPU download dropped the session while a read was in flight. `asyncua`'s
  `send_request` re-raises an in-flight failure as a **bare `Exception`** when
  the socket state has not yet flipped to CLOSED, so a narrow `except` on UA and
  OS error types missed it and the process died instead of reconnecting. Every
  await that touches the session now routes *any* exception into the same
  `SessionBroken` path a failed connect uses, and `run` carries a last-resort
  guard for a step that forgets to;
* a CPU warm restart reverted every input to its start value **under a
  surviving session**, and write-on-change never repaired the contacts whose
  slot values had not changed. The heartbeat read-back detects that and
  invalidates the write cache, so the next input path rewrites every slot.

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

from .config import BOOL, HEARTBEAT_KEY, REAL, UINT16, Config
from .instrumentation import Counters, Recorder
from .slots import SlotSet

LOG = logging.getLogger("bridge.opcua")

#: The three value kinds the model carries, and nothing else: a group adds
#: slots, not kinds (bridge-design.md §2.1 G4, opcua-nodes.md §10.3).
_KIND_VARIANT = {
    REAL: ua.VariantType.Float,
    BOOL: ua.VariantType.Boolean,
    UINT16: ua.VariantType.UInt16,
}
_EXPECTED_DATATYPE_NODEID = {
    ua.VariantType.Float: ua.NodeId(ua.ObjectIds.Float),
    ua.VariantType.Boolean: ua.NodeId(ua.ObjectIds.Boolean),
    ua.VariantType.UInt16: ua.NodeId(ua.ObjectIds.UInt16),
}
_DIAGNOSTIC_TYPE_DEFAULT = ua.VariantType.Boolean


def expected_types(cfg: Config) -> dict[str, ua.VariantType]:
    """The documented DataType of every node this run addresses, derived from
    the configured groups (§2.1 G1) — inputs by their kind, the outputs and the
    heartbeat by the one type each has, the diagnostics all Boolean."""
    types: dict[str, ua.VariantType] = {
        key: _KIND_VARIANT[kind] for key, kind in cfg.input_kinds.items()
    }
    types[HEARTBEAT_KEY] = ua.VariantType.UInt16
    for key, kind in cfg.output_kinds.items():
        types[key] = _KIND_VARIANT[kind]
    for key in cfg.diagnostic_keys:
        types[key] = _DIAGNOSTIC_TYPE_DEFAULT
    return types

#: Error types a broken session was *expected* to raise. This tuple is no longer
#: the filter — anything raised by an await that touches the session is treated
#: as a broken session (§8.1) — it is kept only to tell an anticipated failure
#: from an unanticipated one in the counters, because the 2026-07-28 crash came
#: out as a type that is not in this list.
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


#: Exceptions that mean *this process is wrong*, not *the link is broken*. They
#: are never routed into the reconnect path: reconnecting cannot fix a
#: mis-addressed node or a write to a node the bridge may not write, and a retry
#: loop would hide the defect behind one warning per second. §8.1 is a path for
#: a lost link, not a way to survive a defect.
_BRIDGE_DEFECTS = (WriteNotPermitted, TypeMismatch, NamespaceNotFound)


class PlcClient:
    def __init__(
        self,
        cfg: Config,
        slots: SlotSet,
        recorder: Recorder,
        counters: Counters,
        publish_output: Callable[[str, float], int],
    ) -> None:
        self._cfg = cfg
        self._slots = slots
        self._recorder = recorder
        self._counters = counters
        self._publish_output = publish_output

        # The configured signal set (§2.1). Read once, at construction: the set
        # is fixed at startup by the config and nothing switches a group on or
        # off while the process runs (G3). Every count below — the allowlist,
        # R3's "every input", the restart rewrite — comes from here and from
        # nowhere else, so no rule in this file names a number.
        self._input_keys = cfg.input_keys
        # Cadence per slot, from the node model's own cadence column — not from
        # the value's type (§5, `opcua-nodes.md` §12.6).
        self._cyclic_input_keys = cfg.cyclic_input_keys
        self._on_change_input_keys = cfg.on_change_input_keys
        self._input_variants = {
            key: _KIND_VARIANT[kind] for key, kind in cfg.input_kinds.items()
        }
        self._output_keys = cfg.output_keys
        self._output_topic_keys = cfg.output_topic_keys
        # Slots whose SILENCE is a value (§13.2 W1). A dict that is empty in
        # every configuration that does not carry the warning group, so no other
        # slot acquires a window by sharing a run with this one (§10.8 P4).
        self._stale_asserts = cfg.stale_asserts
        #: Per-slot: is that slot currently past its window? Kept only so the
        #: entry and exit of a silence are LOGGED once each rather than every
        #: cycle. It gates nothing: the value written is recomputed from the
        #: sample's own age on every cycle, not from this flag.
        self._silent_now: dict[str, bool] = {}
        self._write_allowlist = cfg.write_allowlist
        self._expected_types = expected_types(cfg)

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

        # Per-session state, cleared on every (re)connect (R4) and whenever the
        # server is found to have restarted underneath a surviving session.
        self._written_this_session: set[str] = set()
        self._last_on_change_written: dict[str, object] = {}
        self._last_write_start: dict[str, int] = {}
        # The heartbeat value THIS session last wrote, or None if it has written
        # none yet. The bridge is the only client permitted to write that node
        # (opcua-nodes.md §9.1), so a server holding anything else is a server
        # that restarted. None also means "no comparison is possible yet", which
        # is the state right after a connect.
        self._last_heartbeat_written: Optional[int] = None
        # Set when the write cache has just been invalidated, so the next input
        # path can record how much of the image it rewrote. Evidence only.
        self._rewrite_pending = False

        self._running = True
        self._connected = False

    # ------------------------------------------------------------------ #
    # Session failure routing (§8.1 detection row)
    # ------------------------------------------------------------------ #

    def _session_broken(self, what: str, exc: BaseException) -> SessionBroken:
        """Convert any failure of an await that touched the session into the one
        exception the run loop reconnects on.

        The breadth is deliberate and is the 2026-07-28 fix: `asyncua`'s
        `UASocketProtocol.send_request` re-raises an in-flight request failure as
        ``Exception("Unhandled exception while sending request to OPC UA server")``
        when the socket state has not yet flipped to CLOSED, and that type is in
        no error list a caller would think to write. A session failure the
        anticipated list does not name is still a session failure; it is counted
        separately so the evidence says which kind was seen.
        """
        if not isinstance(exc, _SESSION_ERRORS):
            self._counters.unexpected_session_errors += 1
            LOG.warning(
                "%s raised %s, which is not one of the anticipated session error "
                "types; routed into the §8.1 reconnect path anyway",
                what, type(exc).__name__,
            )
            self._recorder.row(
                "session", "unexpected_error", clock="-", value=type(exc).__name__,
                note=f"{what}: {exc}",
            )
        return SessionBroken(f"{what}: {type(exc).__name__}: {exc}")

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

        # R4: a new session starts with nothing written and no heartbeat, so the
        # first cycle of it writes every input slot that carries a real sample.
        self._invalidate_write_cache("new session")
        self._connected = True
        self._start_keepalive()
        self._recorder.row("session", "connect", clock="-", note=opc["endpoint"])
        LOG.info(
            "session established, %d nodes resolved for group(s) %s",
            len(self._nodes), "+".join(self._cfg.groups))

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
        for key in self._expected_types:
            path = [f"{self._ns_index[ns_key]}:{name}" for ns_key, name in self._cfg.browse_path(key)]
            self._nodes[key] = await client.nodes.objects.get_child(path)
        LOG.info("browse path: Objects/%s", "/".join(
            f"{self._ns_index[ns_key]}:{name}" for ns_key, name in self._cfg.interface_path))

    async def _verify_types(self) -> None:
        for key, expected in self._expected_types.items():
            actual = await self._nodes[key].read_data_type()
            if actual != _EXPECTED_DATATYPE_NODEID[expected]:
                raise TypeMismatch(
                    f"{key}: server DataType {actual} != documented {expected.name}"
                )
        LOG.info(
            "all %d node DataTypes match the node model (%s)",
            len(self._expected_types),
            ", ".join(group.reference for group in self._cfg.signal_groups))

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

    # ------------------------------------------------------------------ #
    # Write cache — per-session, invalidated by a server restart (§8.1)
    # ------------------------------------------------------------------ #

    def _invalidate_write_cache(self, reason: str) -> None:
        """Forget what this session has written, so the next input path writes
        **every** slot that carries a real sample.

        This is what write-on-change costs and how it is paid for: the cache is
        an optimisation over the wire, and it is only ever correct while the
        server still holds what the bridge wrote. A reverted server holds start
        values, so the cache has to go.

        R1 is untouched: a slot that has never carried a real sample is still not
        written, and no value is invented here. Nothing is latched, timed or
        thresholded — a dict is emptied.
        """
        self._written_this_session.clear()
        self._last_on_change_written.clear()
        self._last_missing_logged = []
        self._last_heartbeat_written = None
        self._rewrite_pending = True
        LOG.info("write cache invalidated (%s): every input slot with a real sample "
                 "is rewritten in the next cycle", reason)

    async def _verify_own_heartbeat(self) -> None:
        """Detect a server that restarted underneath a surviving session (§8.1).

        The signal it keys on is `DemoCell/Link/BridgeHeartbeat` — the one node
        the bridge writes for itself. The bridge is the only client permitted to
        write it (opcua-nodes.md §9.1), so if the server holds anything other
        than the value this session last wrote, the server's copy of the whole
        input image is not the one this session established: a CPU warm restart
        reinitialised the data block. That is the 2026-07-28 failure, in which
        the PLC read open stop circuits for minutes because write-on-change saw
        nothing change.

        The test is an exact inequality against the last value written in this
        session. Not "lower than", because the counter wraps at 65536 and a wrap
        is not a restart; and not a tolerance or a timer, because there is none
        to choose. Session bookkeeping, not process logic: the value read is
        applied to nothing and transported nowhere.

        Residual, stated rather than patched: a revert that happens while the
        last written value was exactly the value the server reverts to (0) is
        invisible to this test. It is one heartbeat value in 65536 and the next
        restart is still caught. A session loss is caught by the reconnect path
        instead, which invalidates the same cache.
        """
        last = self._last_heartbeat_written
        if last is None:
            return  # nothing written in this session yet; nothing to compare
        start = time.monotonic_ns()
        try:
            value = int(await self._nodes[HEARTBEAT_KEY].read_value())
        except _BRIDGE_DEFECTS:
            raise
        except Exception as exc:
            self._counters.read_errors += 1
            raise self._session_broken(f"read {HEARTBEAT_KEY}", exc) from exc
        end = time.monotonic_ns()
        self._counters.heartbeat_readbacks += 1
        # The step's own cost, recorded as the read round trip it is, so what it
        # adds to the 50 ms cycle is measurable rather than asserted.
        self._recorder.row(
            "read_rt", HEARTBEAT_KEY, t_start_ns=start, t_end_ns=end,
            interval_ns=end - start, value=value,
            note="restart-detection read-back; transports nothing",
        )
        if value == last:
            return
        self._counters.server_restarts_detected += 1
        LOG.warning(
            "%s reads %d but this session last wrote %d: the server restarted "
            "under a live session, so its input image is stale. Invalidating the "
            "write cache (§8.1).", HEARTBEAT_KEY, value, last,
        )
        self._recorder.row(
            "session", "server_restart_detected", clock="-", value=value,
            note=f"this session last wrote {last}; write cache invalidated",
        )
        self._invalidate_write_cache(f"{HEARTBEAT_KEY} reverted to {value}")

    async def _disconnect(self, reason: str) -> None:
        """§7.3 B: on a clean shutdown the bridge writes no farewell value and
        zeroes nothing. It just stops."""
        self._connected = False
        await self._cancel_keepalive()
        # A grant belongs to one session (§3.2 S4); it does not survive it.
        self._granted_session_timeout_ms = None
        self._keepalive_period_s = None
        self._ns_index = {}
        # The heartbeat value in the server belongs to the session that wrote it.
        self._last_heartbeat_written = None
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
        if key not in self._write_allowlist:
            # The allowlist is DERIVED from the configured groups (§4.10,
            # consequence 1): the `Input/` nodes of each configured group plus
            # the one shared heartbeat. It is never a second list maintained
            # beside the config, so it cannot drift from it. A rejection is a
            # DEFECT SIGNAL naming the rule, not a skipped write to retry.
            raise WriteNotPermitted(
                f"{key} is not in this run's write allowlist. The bridge writes only "
                f"the Input/ nodes of the configured group(s) {'+'.join(self._cfg.groups)} "
                f"and {HEARTBEAT_KEY} — {len(self._write_allowlist)} keys: "
                f"{sorted(self._write_allowlist)} (bridge-design.md §3, §4.10; "
                "opcua-nodes.md §9.1, §10.1)."
            )
        node = self._nodes[key]
        start = time.monotonic_ns()
        try:
            await node.write_value(ua.DataValue(ua.Variant(value, variant_type)))
        except _BRIDGE_DEFECTS:
            raise
        except Exception as exc:
            # Any failure of a write in flight, not only the anticipated types.
            self._counters.write_errors += 1
            raise self._session_broken(f"write {key}", exc) from exc
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

        # 0. is the server still the one this session wrote to? Connection
        #    management: it reads back the bridge's own heartbeat and transports
        #    nothing (§8.1).
        await self._verify_own_heartbeat()

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
        """Every configured output slot, read and published in the SAME cycle
        phase, so the process keeps one cadence and one ordering guarantee to
        hand the PLC (§4.8, §5.1 "one cadence"). A group brings output slots,
        never a cadence of its own."""
        for key in self._output_keys:
            node = self._nodes[key]
            start = time.monotonic_ns()
            try:
                value = await node.read_value()
            except _BRIDGE_DEFECTS:
                raise
            except Exception as exc:
                # THE 2026-07-28 CRASH SITE. A download dropped the session while
                # this read was in flight; the exception asyncua raised was not one
                # of the anticipated types and it left the process through `run`.
                self._counters.read_errors += 1
                raise self._session_broken(f"read {key}", exc) from exc
            read_end = time.monotonic_ns()
            self._recorder.row(
                "read_rt", key, t_start_ns=start, t_end_ns=read_end,
                interval_ns=read_end - start, value=value,
            )
            # Marshalling only: Float -> float64 widening, Boolean -> Bool,
            # UInt16 -> UInt16, unit and encoding unchanged. No ramp, no clamp,
            # no interlock, no zeroing, on any slot — and no interpretation of
            # the three envelope elements or of the mode (§4.8, §1.1). N1: only
            # a value read in this cycle is published; nothing is replayed or
            # defaulted (§8.3).
            published_at = self._publish_output(key, value)
            # Per slot, never averaged across slots: a forklift setpoint and a
            # conveyor setpoint share a cycle, not a meaning (§9.3, "per group").
            self._recorder.row(
                "L5", self._output_topic_keys[key], t_start_ns=read_end, t_end_ns=published_at,
                interval_ns=published_at - read_end, value=value,
            )

    async def _input_path(self, cycle_start: int) -> None:
        rewriting = self._rewrite_pending
        written: list[str] = []

        # Cyclic slots: write the slot's latest value every cycle (§5). Every
        # Real of every configured group — the cell's three and the forklift's
        # three — and the vehicle's heartbeat counter, whose whole meaning is
        # that it keeps moving (`opcua-nodes.md` §12.6).
        for key in self._cyclic_input_keys:
            take_ns = time.monotonic_ns()
            sample = self._slots[key].get()
            if sample is None:
                continue  # R1: no sample, no write. No default, ever.
            start, end = await self._write(key, sample.value, self._input_variants[key])
            self._record_write(key, sample, cycle_start, take_ns, start, end)
            written.append(key)

        # Level signals: write on change, plus a full refresh whenever the
        # per-session write cache is empty — after every (re)connect, and after a
        # server restart was detected under a surviving session (§8.1). The four
        # panel contacts, the forklift's field bit and the vehicle's applied
        # mode are treated identically; the field bit's TRUE is the
        # non-permissive state and is carried uninverted (§4.7 row 12), and the
        # applied mode is a readback the bridge neither validates nor compares
        # with the mode in force — that comparison is the PLC's (§12.6 M4).
        for key in self._on_change_input_keys:
            take_ns = time.monotonic_ns()
            sample = self._slots[key].get()
            if sample is None:
                continue
            # For every slot but the warning slot this IS `sample.value`; for
            # that one it is the sample's value while the sample is fresh and
            # the asserted value once it is not (§13.2 W1).
            value = self._value_for_write(key, sample, take_ns)
            if self._last_on_change_written.get(key) == value and key in self._written_this_session:
                continue
            start, end = await self._write(key, value, self._input_variants[key])
            self._last_on_change_written[key] = value
            self._record_write(key, sample, cycle_start, take_ns, start, end, written=value)
            written.append(key)

        if rewriting:
            # Evidence for the repair, recorded once per invalidation. A slot with
            # no real sample is absent here because R1 forbids writing it, not
            # because the repair skipped it.
            self._rewrite_pending = False
            self._counters.inputs_rewritten_after_restart += len(written)
            skipped = [key for key in self._input_keys if key not in written]
            LOG.info(
                "input image rewritten after cache invalidation: %d of %d configured "
                "input nodes (%s)%s",
                len(written), len(self._input_keys), ", ".join(written),
                f"; no real sample yet for {', '.join(skipped)} (R1)" if skipped else "",
            )
            self._recorder.row(
                "session", "input_image_rewritten", clock="-",
                value=f"{len(written)}/{len(self._input_keys)}",
                note="written in one cycle; configured set "
                     + "+".join(self._cfg.groups)
                     + (f"; R1 withheld {','.join(skipped)}" if skipped else ""),
            )

    def _value_for_write(self, key: str, sample, now_ns: int):
        """The value this cycle writes for a slot — `sample.value`, unless the
        slot carries a silence rule and its sample is older than that rule's
        window (`opcua-nodes.md` §13.2 **W1**).

        **What is timed here is this bridge's own input channel**, never the
        plant: the question asked is "have I heard from my producer inside my
        window", and the answer is a property of the transport. The verdict
        itself is the field evaluation's and is not recomputed, compared,
        thresholded, latched or debounced anywhere in this process (§1.1); the
        producer publishes at its evaluation tick *so that* its absence is
        visible, and this is the last layer that can see the absence before an
        OPC UA node — a held value by construction — turns it into a standing
        clear (LESSONS 2026-08-04).

        Recomputed from the sample's own age on **every** cycle, deliberately:
        that is what makes the refresh paths safe. §8.1's full rewrite after a
        detected server restart writes what this method returns, so a restart
        that reverted the node to its non-permissive start value can never be
        "repaired" back to a stale `FALSE` by a dead producer's last sample.
        """
        rule = self._stale_asserts.get(key)
        if rule is None:
            return sample.value
        age_ns = now_ns - sample.recv_ns
        silent = age_ns > int(rule.window_s * 1e9)
        if silent != self._silent_now.get(key, False):
            self._silent_now[key] = silent
            self._note_silence_transition(key, rule, silent, age_ns)
        return rule.asserted_value if silent else sample.value

    def _note_silence_transition(self, key: str, rule, silent: bool, age_ns: int) -> None:
        """Log and record the entry into and exit from a silence. Evidence only:
        nothing downstream reads these, and the value written is derived from the
        sample's age rather than from anything recorded here."""
        if silent:
            self._counters.silence_assertions += 1
            self._counters.silence_max_age_ns = max(
                self._counters.silence_max_age_ns, age_ns)
            LOG.warning(
                "SILENCE on %s: no sample for %.3f s, past the %.3f s window — "
                "writing the asserted %s (%s). A read of this node is never an "
                "implied clear: the silence is asserted, not held",
                key, age_ns / 1e9, rule.window_s, rule.asserted_value, rule.reference,
            )
        else:
            LOG.info(
                "%s fresh again after %.3f s: the slot's own value is carried once "
                "more (%s)", key, age_ns / 1e9, rule.reference,
            )
        self._recorder.row(
            "silence", key, clock="-", interval_ns=age_ns,
            value=rule.asserted_value if silent else "",
            note=("entered: asserted value written" if silent else "left: sample carried")
                 + f"; window {rule.window_s:.3f}s ({rule.reference})",
        )

    def _record_write(
        self, key: str, sample, cycle_start: int, take_ns: int, start: int, end: int,
        written=None,
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
        # L2 input write: start of write -> server write response. `value` is
        # what actually went on the wire, which differs from the sample only for
        # a slot inside its silence rule (§13.2 W1) — and the note says so, so
        # the CSV never shows an asserted value as if a producer had sent it.
        asserted = written is not None and written != sample.value
        self._recorder.row(
            "L2", key, t_start_ns=start, t_end_ns=end,
            interval_ns=end - start,
            value=sample.value if written is None else written,
            note="asserted on silence, not a received sample (§13.2 W1)" if asserted else "",
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
        # R3 counts EVERY INPUT IN THE CONFIGURED SIGNAL SET (§6.1) — what the
        # config declares, not what the interface offers. A cell-only run counts
        # 7, a forklift-only run 4, both groups 11, and a group that is not
        # configured contributes no slot and cannot hold the heartbeat back.
        missing = [key for key in self._input_keys if key not in self._written_this_session]
        if missing:
            self._counters.heartbeat_suppressed_cycles += 1
            if missing != self._last_missing_logged:
                # Logged when the set changes, not every cycle.
                LOG.info(
                    "heartbeat withheld: %d of %d configured input(s) carry no real "
                    "sample yet — %s (startup rule R3)",
                    len(missing), len(self._input_keys), ", ".join(missing),
                )
                self._last_missing_logged = list(missing)
            return
        self._last_missing_logged = []
        if not self._heartbeat_started:
            self._heartbeat_started = True
            LOG.info(
                "startup rule R3 satisfied: all %d input nodes of the configured set "
                "(%s) carry a real plant sample; heartbeat begins advancing at %d",
                len(self._input_keys), "+".join(self._cfg.groups), self._heartbeat + 1)
            self._recorder.row(
                "startup", "heartbeat_start", clock="-", value=self._heartbeat + 1,
                note=f"R3 over {len(self._input_keys)} configured input(s): "
                     + ",".join(self._input_keys))
        self._heartbeat = (self._heartbeat + 1) % 65536
        start, end = await self._write(HEARTBEAT_KEY, self._heartbeat, ua.VariantType.UInt16)
        # What the next cycle's read-back is compared against (§8.1). Recorded
        # only after the write returned, so a failed write leaves the previous
        # expectation in force rather than an unwritten one.
        self._last_heartbeat_written = self._heartbeat
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
            except _BRIDGE_DEFECTS:
                raise
            except Exception as exc:
                self._counters.read_errors += 1
                raise self._session_broken(f"read {key}", exc) from exc
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
        #: When the session broke, so the resumed session can state the size of
        #: the hole it left in the evidence.
        broken_at_ns: Optional[int] = None

        while self._running:
            if duration_s is not None and (time.monotonic() - started) >= duration_s:
                break
            if not self._connected:
                try:
                    await self._connect()
                    if broken_at_ns is not None:
                        self._note_outage(broken_at_ns)
                        broken_at_ns = None
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

            broken: Optional[SessionBroken] = None
            try:
                await self._cycle(cycle_start)
                if (time.monotonic() - last_status) >= status_period:
                    last_status = time.monotonic()
                    await self._poll_diagnostics()
            except SessionBroken as exc:
                broken = exc
            except _BRIDGE_DEFECTS:
                # A defect in this process. Reconnecting cannot fix it and
                # retrying would hide it, so it leaves the loop.
                raise
            except Exception as exc:
                # LAST RESORT (2026-07-28). A cycle step that touches the session
                # without routing its own failure would otherwise leave the
                # process — which is exactly how the bridge died mid-run. The
                # reconnect is the same one; the counter says a site was missed,
                # which is a defect to find, not a runtime condition.
                self._counters.unrouted_cycle_errors += 1
                LOG.error(
                    "unrouted %s escaped the cycle: %s. Treated as a broken session "
                    "so the process survives; the raising step should route it itself",
                    type(exc).__name__, exc,
                )
                self._recorder.row(
                    "session", "unrouted_cycle_error", clock="-",
                    value=type(exc).__name__, note=str(exc),
                )
                broken = SessionBroken(f"unrouted {type(exc).__name__}: {exc}")

            if broken is not None:
                self._counters.reconnects += 1
                broken_at_ns = time.monotonic_ns()
                LOG.warning("session broken: %s — degraded mode, no signal invented", broken)
                self._recorder.row("session", "broken", clock="-", note=str(broken))
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

    def _note_outage(self, broken_at_ns: int) -> None:
        """Record the hole the outage left in the evidence.

        The instrumentation is only honest if it says where it stopped: a 20 Hz
        file with a 26 s gap and no gap row reads like 26 s of steady data.
        """
        gap_ns = time.monotonic_ns() - broken_at_ns
        self._counters.session_outages += 1
        self._counters.session_outage_total_ns += gap_ns
        self._counters.session_outage_max_ns = max(self._counters.session_outage_max_ns, gap_ns)
        LOG.info("session resumed after %.3f s without a link; no rows exist for that "
                 "interval and none are invented", gap_ns / 1e9)
        self._recorder.row(
            "session", "resumed", t_start_ns=broken_at_ns, t_end_ns=broken_at_ns + gap_ns,
            interval_ns=gap_ns, note="gap in the evidence: no cycle ran in this interval",
        )

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
