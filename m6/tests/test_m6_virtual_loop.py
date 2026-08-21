"""m6.control_loop itself, driven against the virtual F-PLC.

WHAT LEVEL OF EVIDENCE THIS IS, EXACTLY
  test_virtual_fplc.py proves the MODEL. These tests prove the LOOP that
  drives it: the real `m6.control_loop` - the same function the Windows
  writer runs against PLCSIM - over real UDP sockets, with
  `virtual_fplc.VirtualFPLC` in the PLC's place. Everything between the
  sensor datagram and the status payload is production code: the drain,
  the staleness rule, the six field writes, the encoder writes, the ack
  pulse, the Motor read and the wire format. Only Gazebo and Tk are
  absent.

  So: loop-level evidence, not a full-stack run. The autonomous leg under
  `--virtual` is still owed a live smoke against the ROS side.

WHY EVERY SCENARIO RUNS TWICE
  Since M6.1 the writer is one process per vehicle and the port pair is
  the vehicle's, not the project's - so a loop that only ever ran on
  f1's pair would leave f2's writer unproven and would happily survive a
  VEHICLES table that handed both trucks the same port. Each scenario
  therefore runs once per vehicle, on the pair status_contract gives
  that vehicle, and the port literals have left this file with the rest
  of them.

HOW THE ASSERTIONS ARE TIMED
  Every wait polls for its condition against a deadline, so a slow machine
  costs seconds and never a false failure. The one fixed window is the
  latch watch, which exists to see nothing happen.
"""
import json
import socket
import threading
import time
from types import SimpleNamespace

import pytest

import m6
from virtual_fplc import VirtualFPLC

# Twice the live 10 Hz of sensor_link, so one late thread wake-up can
# never be mistaken for the silent link that test C is about.
FEED_PERIOD_S = 0.05
DEADLINE_S = 3.0          # no assertion here waits longer than this
LATCH_WATCH_S = 0.40      # room for several healed datagrams to land
WIRE_KEYS = {"estop_healthy", "motor", "case", "v_limit", "ts"}


def _datagram(pf=True, enc=(0, 0)):
    """One sensor packet: healthy, except for what the caller changes."""
    return json.dumps({
        "pf": pf, "wf": True, "pf_right": True, "wf_right": True,
        "pf_left": True, "wf_left": True,
        "enc_a": enc[0], "enc_b": enc[1], "ts": time.time()}).encode()


def _feed(sock, port, ctl):
    """Stand in for sensor_link.py until `ctl` says stop."""
    while ctl["run"]:
        if ctl["send"]:
            try:
                sock.sendto(_datagram(ctl["pf"], ctl["enc"]),
                            ("127.0.0.1", port))
            except OSError:
                return          # the rig is being torn down
        time.sleep(FEED_PERIOD_S)


def _wait(predicate, deadline_s=DEADLINE_S):
    """True as soon as `predicate` holds, False if it never does in time."""
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _holds(predicate, seconds):
    """True if `predicate` held for the whole window."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not predicate():
            return False
        time.sleep(0.01)
    return True


def _status(rig, predicate, deadline_s=DEADLINE_S):
    """The next status payload matching `predicate`, or None."""
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        try:
            data = rig.listener.recv(512)
        except socket.timeout:
            continue
        msg = json.loads(data.decode())
        if predicate(msg):
            return msg
    return None


def _pulse_ack(state):
    """One RESET press - an Acknowledge rising edge the model can see.

    The previous pulse is let fall first. The loop writes Acknowledge as
    `now < ack_until`, so re-arming a pulse that has not expired holds the
    bit True with no new edge, and ESTOP1 re-enables on the edge alone.
    Note the clock: control_loop reads `time.monotonic`, not the wall
    clock, and an `ack_until` in wall-clock seconds would sit forever in
    the future.
    """
    while time.monotonic() < state["ack_until"] + 2 * m6.CYCLE_S:
        time.sleep(0.01)
    state["ack_until"] = time.monotonic() + m6.ACK_PULSE_S


def _enable(rig):
    """Startup to Motor enabled, the way the operator gets there.

    V_Limit on the wire is the proof that the healthy stream reached the
    model: a stale link writes all three warning fields False, which is
    300, so 1500 cannot be read until a trusted datagram has landed. Only
    then is the ack worth spending - one consumed while the inputs are
    still unhealthy clears nothing and there is no second edge.
    """
    assert _status(rig, lambda m: m["v_limit"] == 1500) is not None, (
        "the healthy sensor stream never reached the model: V_Limit stayed "
        "at the stale-link 300")
    _pulse_ack(rig.state)
    assert _wait(lambda: rig.live["motor"]), "Motor never enabled after ack"


@pytest.fixture(params=["f1", "f2"])
def vehicle_ports(request, monkeypatch):
    """Point the module's two port constants at one vehicle's pair.

    The rig below is built from `m6.UDP_PORT`, and `control_loop`
    reads that same global on every send, so patching it here is what
    makes each scenario run as a particular truck. SENSOR_PORT moves
    with it to keep the module one vehicle's throughout: the loop takes
    its rx socket as an argument (only `main` binds SENSOR_PORT), so the
    rig keeps handing it the ephemeral port it always did.
    """
    from status_contract import contract
    c = contract(request.param)
    monkeypatch.setattr(m6, "UDP_PORT", c["plc_port"])
    monkeypatch.setattr(m6, "SENSOR_PORT", c["sensor_port"])
    return request.param


@pytest.fixture
def rig(vehicle_ports):
    """A running control_loop with real sockets on both sides of it.

    Every test reaches it through this fixture, so `vehicle_ports`
    parameterises the whole file - three scenarios, two vehicles, six
    runs - without a test having to name the vehicle it is being.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        listener.bind(("127.0.0.1", m6.UDP_PORT))
    except OSError as exc:
        listener.close()
        pytest.skip(
            "UDP {} is already bound ({}) - a live m6.py or plc_link is "
            "holding the port this rig needs".format(m6.UDP_PORT, exc))
    listener.settimeout(0.05)

    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0))
    rx.setblocking(False)
    sensor_port = rx.getsockname()[1]
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    feed = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    state = {"estop": True, "ack_until": 0.0, "run": True,
             "enc_mode": "ok", "error": ""}
    live = {"line": "", "motor": False}
    ctl = {"run": True, "send": True, "pf": True, "enc": (0, 0)}

    worker = threading.Thread(
        target=m6.control_loop,
        args=(VirtualFPLC(), "127.0.0.1", tx, rx, state, live), daemon=True)
    worker.start()
    feeder = threading.Thread(
        target=_feed, args=(feed, sensor_port, ctl), daemon=True)
    feeder.start()

    yield SimpleNamespace(state=state, live=live, ctl=ctl, listener=listener)

    ctl["run"] = False
    feeder.join(timeout=2.0)
    state["run"] = False
    worker.join(timeout=2.0)          # its `finally` trips the plant first
    for sock in (listener, rx, feed, tx):
        sock.close()
    assert state["error"] == "", state["error"]


def test_an_ack_enables_the_motor_and_the_status_wire_says_so(rig):
    _enable(rig)
    msg = _status(rig, lambda m: m["motor"] is True)
    assert msg is not None, "no status payload ever reported Motor True"
    assert set(msg) == WIRE_KEYS
    assert msg["estop_healthy"] is True
    assert msg["case"] == 1            # the model pins the monitoring case
    assert msg["v_limit"] == 1500      # all three warning fields clear


def test_a_protective_field_trip_latches_through_the_heal(rig):
    _enable(rig)
    rig.ctl["pf"] = False
    assert _wait(lambda: not rig.live["motor"]), "PF False left Motor enabled"
    rig.ctl["pf"] = True
    # The stream never stops, so healed datagrams are landing throughout.
    assert _holds(lambda: not rig.live["motor"], LATCH_WATCH_S), (
        "healing the protective field re-enabled Motor with no Acknowledge")
    _pulse_ack(rig.state)
    assert _wait(lambda: rig.live["motor"]), "the ack did not clear the latch"


def test_a_silent_sensor_link_fails_safe(rig):
    _enable(rig)
    rig.ctl["send"] = False
    # SENSOR_STALE_S later the loop writes the six fields False and the
    # 0/3000 encoder picture, which is a demanded stop by two routes.
    assert _wait(lambda: not rig.live["motor"],
                 m6.SENSOR_STALE_S + 1.0), (
        "Motor stayed enabled with the sensor link silent")
