"""fleet_cli.py - the operator's hand and the operator's screen.

Two commands and no state of its own:

  python3 fleet/fleet_cli.py submit S1 S4 [--task-id ...]
  python3 fleet/fleet_cli.py status [--watch]

AND IT READS THE FLOOR TOO (M6.4). The status document carries a
`traffic` block - who holds which piece of floor, who is waiting on
whom, who yielded and how much of each task is base rather than horizon
- and the TRAFFIC section prints it. That section is how an operator
tells a truck that is WAITING from a truck that is broken: a held-back
vehicle is standing at the end of its base on purpose, and the element
it wants is named beside it.

THE OPERATOR NAMES STATIONS, NEVER VEHICLES. `submit FROM TO` is a
transport - take a pallet from here to there - and which truck does it
is the fleet's decision, made from where the trucks actually are
(fleet_core.nearest_idle). A CLI that took a vehicle id would be a
remote control with a queue bolted on, and the first thing it would do
is send work to a truck that is charging. The only way to name a
vehicle from here is not to have one.

IT PUBLISHES AND IT READS. There is no request/response with the
manager and no socket of its own: a submission is one QoS 1 publish to
`fleet/task/submit`, and the screen is the RETAINED `fleet/status`
document the manager keeps up to date. So the CLI can be started, read
and killed at any moment without the fleet noticing, and two of them
side by side are two readers of the same retained truth.

WHAT THIS TOOL CANNOT PROMISE, AND SAYS SO. A submission is not
retained: the broker hands it to whoever is subscribed at that instant
and forgets it. If no manager is running, the task is GONE - not
queued, not pending, gone. So `submit` looks at the retained status
document before it exits and warns when nothing behind it is alive.
That check is honest about its own limits too: a retained document
outlives its manager, which is why the age is what is judged and not
its mere presence.

THE STALENESS RULE IS THE MANAGER'S OWN PROMISE. It republishes the
document on every change and at least every 2 s, so a document older
than a few periods means the publisher is gone - and the ages inside
it were computed when it was built, so everything below a stale header
is that much older again. The header says the number rather than
hiding it: an operator who can see "document age 612.4 s" knows more
than one reading a screen that still says EN-ROUTE.

paho 2.x, and VDA_MQTT_PORT overrides the port the same way it does for
vda_agent, send_order and the manager - a rig moved off 1883 moves
together or not at all.
"""
import argparse
import json
import os
import queue
import sys
import time
import uuid

import paho.mqtt.client as mqtt

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "ipc")))
from stations import STATIONS                       # noqa: E402
from work_generator import MIN_LEN_M, WorkGenerator  # noqa: E402

MQTT_HOST = "127.0.0.1"
MQTT_PORT = int(os.environ.get("VDA_MQTT_PORT", "1883"))
SUBMIT_TOPIC = "fleet/task/submit"
STATUS_TOPIC = "fleet/status"
STATUS_WAIT_S = 3.0      # a retained message arrives on the SUBACK; this
                         # is a broker that is up but slow, not a wait
PUBLISH_WAIT_S = 5.0     # QoS 1 means a PUBACK, and that is worth waiting
STATUS_PERIOD_S = 2.0    # the manager's own promise (fleet_manager.py)
STALE_AFTER_S = 3 * STATUS_PERIOD_S


def new_task_id():
    """`ft-<hex8>`. The prefix is the fleet's mark on everything it
    owns - orders wear it too, and it is how a restarted manager tells
    its own work from an order somebody else put on a truck."""
    return "ft-{}".format(uuid.uuid4().hex[:8])


def build_submission(from_station, to_station, task_id=None):
    """The submit payload, or ValueError naming what is wrong.

    THE SAME THREE RULES THE MANAGER WILL APPLY (fleet_manager's
    _why_refused), asked here first so a typo costs a line of stderr
    instead of a silent entry in a refusal list nobody is watching.
    The fourth rule - a taskId already in the book - CANNOT be asked
    here: the queue is the manager's and this process has no copy of
    it. That refusal comes back in the status document's REFUSED
    section, which is why `status` renders it.
    """
    if task_id is not None and (not isinstance(task_id, str)
                                or not task_id.strip()):
        raise ValueError("--task-id must be a non-empty string")
    for role, station in (("FROM", from_station), ("TO", to_station)):
        if station not in STATIONS:
            raise ValueError("unknown {} station {!r} - stations are: {}"
                             .format(role, station, ", ".join(STATIONS)))
    if from_station == to_station:
        raise ValueError(
            "FROM and TO are the same station ({}) - a transport goes "
            "somewhere".format(from_station))
    return {"taskId": task_id or new_task_id(),
            "from": from_station, "to": to_station}


# ---- the screen ----
# FIXED WIDTHS, NOT COLUMNS SIZED TO THE DATA. A table that reflows when
# a truck reports a longer mode string is a table the eye has to re-read
# every 2 s; --watch reprints this thing continuously and the point of it
# is that the same fact stays in the same place. Anything longer than its
# column is truncated with a visible '~' rather than silently cut.
VEHICLE_COLS = (("VEHICLE", 8), ("CONNECTION", 17), ("MODE", 10),
                ("POSITION", 16), ("ORDER", 12), ("AGE s", 7),
                ("FLAGS", 16))
TASK_COLS = (("TASK", 12), ("STATE", 14), ("FROM", 5), ("TO", 5),
             ("ASSIGNEE", 9), ("ORDER", 12), ("AGE s", 8), ("LAST", 44))


def _cell(value, width):
    text = "-" if value is None or value == "" else str(value)
    if len(text) > width:
        text = text[:width - 1] + "~"
    return text.ljust(width)


def _row(columns, values):
    return " ".join(_cell(v, w) for (_, w), v in zip(columns, values)) \
        .rstrip()


def _head(columns):
    return " ".join(name.ljust(width) for name, width in columns).rstrip()


def _age(seconds):
    """Always a number of seconds, one decimal, however big it gets.

    No "2 minutes ago" and no "-" for a large value: a growing number is
    the one thing on this screen that tells an operator the feed behind
    a row has died, and a friendlier unit would round that signal away.
    """
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        return "-"
    return "{:.1f}".format(seconds)


def _position(pos):
    if not isinstance(pos, (list, tuple)) or len(pos) != 2:
        return None
    try:
        return "{:.2f}, {:.2f}".format(float(pos[0]), float(pos[1]))
    except (TypeError, ValueError):
        return None


def _flags(row):
    flags = [name for name, key in (("LOST", "lost"),
                                    ("standby", "not_eligible"))
             if row.get(key)]
    return ",".join(flags) if flags else None


def _dict(doc, key):
    value = doc.get(key)
    return value if isinstance(value, dict) else {}


def _list(doc, key):
    value = doc.get(key)
    return value if isinstance(value, list) else []


def traffic_lines(doc, now=None):
    """The TRAFFIC section, or nothing at all.

    NOTHING AT ALL IS A REAL ANSWER: a retained document written by a
    pre-M6.4 manager has no `traffic` block, and a screen that answered
    that with "(none)" would be claiming an empty floor rather than an
    old document. The section simply is not printed.

    A truck can be STUCK without holding or waiting for anything: when
    not one node of a route is free the fleet hands the whole prefix
    back rather than sit in the wait-for graph with no task, and the
    sentence is carried in the document instead of in the ledger.

    The element strings are the MANAGER's - `(1.0,0.0)` for a node and
    `(1.0,0.0)-(2.0,0.0)` for the floor between two - because a
    frozenset of coordinate pairs does not survive JSON and the fleet is
    the one that knows what it reserved. This function only lays them
    out.
    """
    block = doc.get("traffic")
    if not isinstance(block, dict):
        return []
    if not block.get("enabled"):
        return ["", "TRAFFIC (OFF - --no-traffic: every route is granted "
                    "whole, which is the M6.3 behaviour)"]
    holds, waiting = _dict(block, "holds"), _dict(block, "waiting")
    bases, yielded = _dict(block, "bases"), _list(block, "yielded")
    lines = ["", "TRAFFIC (on)"]
    if not holds and not waiting and not bases and not _dict(block, "stuck"):
        lines.append("  (nothing reserved - no truck is on the floor)")
    for name in sorted(holds):
        lines.append("  {} holds  {}".format(
            _cell(name, 10), " ".join(str(e) for e in _list(holds, name))))
    for name in sorted(waiting):
        lines.append("  {} WAITS  {}{}".format(
            _cell(name, 10), waiting[name],
            "   (yielded)" if name in yielded else ""))
    for name in sorted(set(yielded) - set(waiting)):
        lines.append("  {} yielded - holding nothing ahead, retrying "
                     "every pass".format(_cell(name, 10)))
    for name in sorted(_dict(block, "stuck")):
        lines.append("  {} STUCK  {}".format(
            _cell(name, 10), _dict(block, "stuck")[name]))
    for task_id in sorted(bases):
        split = bases[task_id]
        if isinstance(split, (list, tuple)) and len(split) == 2:
            lines.append("  {} base {} released + {} horizon".format(
                _cell(task_id, 12), split[0], split[1]))
    for entry in _list(block, "yields"):
        if isinstance(entry, dict):
            lines.append("  gave way: {} ({}) to {} - youngest task in the "
                         "deadlock".format(
                             entry.get("vehicle"), entry.get("task"),
                             ", ".join(entry.get("with") or [])))
    for entry in _list(block, "idle"):
        # A truck that no longer reserves the node it is standing on is
        # the one thing on this screen an operator could otherwise read
        # as the fleet having forgotten it. THE AGE IS PRINTED because
        # these entries persist as long as the truck stands: on the
        # 2026-08-24 operator recording four of them held the screen
        # unchanged for eleven minutes and read as live warnings. The
        # entry has carried `ts` since M6.5; this is its first reader.
        if isinstance(entry, dict):
            ts = entry.get("ts")
            age = ""
            if isinstance(ts, (int, float)) and now is not None:
                age = "   ({:.0f} s ago)".format(max(0.0, now - ts))
            lines.append("  idle timeout: {} gave back {} element(s) at {} "
                         "- it is still standing there{}".format(
                             entry.get("vehicle"), entry.get("freed"),
                             entry.get("node"), age))
    for entry in _list(block, "aside"):
        # A STEP-ASIDE IS THE ONE ORDER IN THIS SYSTEM WITH NO TASK
        # BEHIND IT, so without this row an operator watching a truck
        # leave its node would find nothing on the screen that explains
        # it - no task, no base, no assignment. The sentence names who
        # it was moved for.
        if isinstance(entry, dict):
            lines.append("  step aside: {} {} -> {} to clear {}{}".format(
                entry.get("vehicle"), entry.get("from"), entry.get("to"),
                ", ".join(entry.get("for") or []),
                "" if entry.get("state") == "done"
                else "   ({})".format(entry.get("state"))))
    for entry in _list(block, "blocked"):
        if isinstance(entry, dict):
            lines.append("  ** BLOCKED: {} **".format(entry.get("why")))
    for entry in _list(block, "closed"):
        # A closed node is the floor telling a PERSON where to walk: a
        # vehicle reported a body there, nothing is granted onto it,
        # and the clock says how long the fleet will keep planning
        # around it before it asks again.
        if isinstance(entry, dict):
            lines.append("  ** CLOSED {} - body reported by {}, {} s "
                         "left **".format(entry.get("node"),
                                          entry.get("by"),
                                          entry.get("left_s")))
    return lines


def render(doc, now=None):
    """The whole screen for one status document. Pure: dict in, text out.

    `now` is the reader's own wall clock, and the ages of the document
    and of each task are measured against it, so a manager that stopped
    publishing shows a header that grows while the rows underneath stand
    still - exactly the shape of what happened. The per-VEHICLE age is
    the manager's own number, computed when the document was built, and
    it is therefore understated by the document's age; the header says
    so out loud rather than doing arithmetic on somebody else's clock.
    """
    now = time.time() if now is None else now
    ts = doc.get("ts")
    doc_age = (now - ts) if isinstance(ts, (int, float)) else None
    manager = doc.get("manager")
    tasks = doc.get("tasks") if isinstance(doc.get("tasks"), list) else []
    vehicles = doc.get("vehicles") \
        if isinstance(doc.get("vehicles"), dict) else {}
    refused = doc.get("refused") \
        if isinstance(doc.get("refused"), list) else []
    lines = ["fleet/status   manager {}   document age {} s   "
             "queue {}   done {}".format(
                 manager or "?", _age(doc_age),
                 doc.get("queue_len", "?"), doc.get("done_count", "?"))]
    if manager == "OFFLINE":
        lines.append("  ** the manager said OFFLINE on its way out - "
                     "nothing is assigning work. **")
    elif doc_age is not None and doc_age > STALE_AFTER_S:
        lines.append(
            "  ** STALE: this document is {} s old and the manager "
            "republishes every {:.1f} s.".format(_age(doc_age),
                                                 STATUS_PERIOD_S))
        lines.append("     Every row below is that much older again. **")

    # THE SHIFT STRIP: the same rows the tables below print, added up
    # once, where a viewer's eye lands first. A recording is watched at
    # a glance and a glance cannot count table rows (M6 review item 4).
    states = [t.get("state") for t in tasks if isinstance(t, dict)]
    stalled_strip = _dict(doc, "stalled")
    strip = "  shift: {} driving · {} dwell · {} queued · {} done · " \
            "{} refused".format(
                sum(1 for s in states
                    if s in ("ASSIGNED_LEG1", "ASSIGNED_LEG2")),
                sum(1 for s in states if s == "DWELL"),
                doc.get("queue_len", "?"), doc.get("done_count", "?"),
                len(refused))
    if stalled_strip:
        strip += " · NOT MOVING: " + "  ".join(
            "{} {:.0f}s".format(serial, stalled_strip[serial])
            for serial in sorted(stalled_strip))
    lines.append(strip)

    lines += ["", "VEHICLES ({})".format(len(vehicles)),
              _head(VEHICLE_COLS)]
    if not vehicles:
        lines.append("  (none - no truck has published on this broker)")
    for serial in sorted(vehicles):
        row = vehicles[serial] if isinstance(vehicles[serial], dict) else {}
        lines.append(_row(VEHICLE_COLS, (
            serial, row.get("connection"), row.get("operating_mode"),
            _position(row.get("position")), row.get("executing_order"),
            _age(row.get("state_age_s")), _flags(row))))

    lines += ["", "TASKS ({} shown, {} done)".format(
        len(tasks), doc.get("done_count", "?")), _head(TASK_COLS)]
    if not tasks:
        lines.append("  (none - the fleet has no work. A restarted "
                     "manager has no tasks: resubmit.)")
    for task in tasks:
        if not isinstance(task, dict):
            continue
        submitted = task.get("submitted_ts")
        history = task.get("history")
        lines.append(_row(TASK_COLS, (
            task.get("task_id"), task.get("state"), task.get("from"),
            task.get("to"), task.get("assignee"), task.get("order_id"),
            _age((now - submitted)
                 if isinstance(submitted, (int, float)) else None),
            history[-1] if isinstance(history, list) and history else None)))

    lines += traffic_lines(doc, now)

    stalled = _dict(doc, "stalled")
    if stalled:
        lines += ["", "NOT MOVING ({} - has a task, and the floor is not "
                  "holding it)".format(len(stalled))]
        for serial in sorted(stalled):
            lines.append("  {}  still for {} s".format(
                _cell(serial, 8), stalled[serial]))

    if refused:
        lines += ["", "REFUSED ({}, most recent last)".format(len(refused))]
        for item in refused:
            if isinstance(item, dict):
                lines.append("  {}  {}".format(
                    _cell(item.get("taskId"), 12), item.get("why", "")))
    return "\n".join(lines)


# ---- the wire ----
def _die(message, code=1):
    sys.stderr.write("{}\n".format(message))
    return code


def _client(role):
    """The pid is in the client id on purpose: two operators reading the
    same fleet must not evict each other from the broker, which is
    exactly what a shared client id does."""
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                       client_id="fleet-cli-{}-{}".format(role,
                                                          os.getpid()))


def _connect(client, host, port):
    """True, or a named refusal on stderr. The one failure an operator
    meets daily is a stack that is not up, and "connection refused" with
    no port in it sends them to the wrong place."""
    try:
        client.connect(host, port, keepalive=30)
    except OSError as exc:
        sys.stderr.write(
            "no broker at {}:{} ({}) - is the stack up? "
            "./m6.sh start\n".format(host, port, exc))
        return False
    return True


def _close(client):
    try:
        client.disconnect()
    except Exception:
        pass
    client.loop_stop()


def _status_reader(host, port, role):
    """(client, inbox) subscribed to the retained status, or (None, None).

    The subscribe lives INSIDE on_connect so it cannot race the CONNACK,
    which is the same reason send_order does it there.
    """
    inbox = queue.Queue()
    client = _client(role)
    client.on_connect = lambda c, u, f, rc, props=None: \
        c.subscribe(STATUS_TOPIC, qos=1)
    client.on_message = lambda c, u, msg: inbox.put(msg.payload)
    if not _connect(client, host, port):
        return None, None
    client.loop_start()
    return client, inbox


def _await(inbox, timeout_s):
    try:
        return inbox.get(timeout=timeout_s)
    except queue.Empty:
        return None


def _parse(payload):
    try:
        doc = json.loads(payload.decode())
    except (AttributeError, ValueError, UnicodeDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _liveness(payload, now):
    """What is wrong with the fleet behind this retained document, or
    None when nothing is. A document is not a heartbeat: it outlives the
    process that wrote it, so what is read here is its AGE."""
    if payload is None:
        return ("no retained fleet/status - no fleet manager has ever "
                "published on this broker")
    doc = _parse(payload)
    if doc is None:
        return "the retained fleet/status is not a readable JSON object"
    if doc.get("manager") == "OFFLINE":
        return "the fleet manager said OFFLINE on its way out"
    ts = doc.get("ts")
    age = (now - ts) if isinstance(ts, (int, float)) else None
    if age is None:
        return "the retained fleet/status carries no timestamp"
    if age > STALE_AFTER_S:
        return ("the retained fleet/status is {:.1f} s old - the manager "
                "republishes every {:.1f} s, so it is not running"
                .format(age, STATUS_PERIOD_S))
    return None


def cmd_submit(args):
    try:
        body = build_submission(args.from_station, args.to_station,
                                args.task_id)
    except ValueError as exc:
        return _die(str(exc), 2)
    # The status subscription is opened BEFORE the submission goes out,
    # so the retained document that comes back cannot be one the manager
    # published in reaction to this task - what is being judged is
    # whether anybody was there to react at all.
    client, inbox = _status_reader(args.host, args.port, "submit")
    if client is None:
        return 1
    info = client.publish(SUBMIT_TOPIC, json.dumps(body), qos=1)
    try:
        info.wait_for_publish(timeout=PUBLISH_WAIT_S)
    except (RuntimeError, ValueError):
        pass
    if not info.is_published():
        _close(client)
        return _die("the broker at {}:{} did not acknowledge the "
                    "submission within {:.0f} s - nothing was queued"
                    .format(args.host, args.port, PUBLISH_WAIT_S))
    print("{}  submitted: {} -> {}".format(
        body["taskId"], body["from"], body["to"]))
    trouble = _liveness(_await(inbox, STATUS_WAIT_S), time.time())
    _close(client)
    if trouble:
        # NOT A FAILURE OF THE SUBMISSION - it did reach the broker, and
        # that is all this exit code has ever claimed. It is a warning
        # that the broker had nobody to hand it to, and a submission is
        # not retained: what is not taken now is not taken later.
        sys.stderr.write(
            "WARNING: {}.\n         A submission is not retained - if no "
            "manager is running this task is gone, not waiting.\n"
            .format(trouble))
    return 0


def cmd_status(args):
    client, inbox = _status_reader(args.host, args.port, "status")
    if client is None:
        return 1
    payload = _await(inbox, STATUS_WAIT_S)
    if payload is None:
        _close(client)
        return _die(
            "no retained fleet/status on {}:{} after {:.0f} s - no fleet "
            "manager has published here.\nIs it running? './m6.sh start' "
            "spawns it; its log is logs/fleet.log."
            .format(args.host, args.port, STATUS_WAIT_S))
    try:
        while True:
            doc = _parse(payload)
            if doc is None:
                sys.stderr.write("unreadable fleet/status payload "
                                 "({} bytes)\n".format(len(payload)))
            else:
                print(render(doc, time.time()))
            if not args.watch:
                return 0
            # ONE REPRINT PER RETAINED UPDATE, scrolling, rather than a
            # cleared screen: the manager publishes on every change, so
            # the scrollback IS the fleet's recent history and clearing
            # it would throw away the only record this tool leaves.
            payload = None
            while payload is None:
                payload = _await(inbox, 0.5)
            print("\n{} ---------------------------------------------"
                  .format(time.strftime("%H:%M:%S")))
    except KeyboardInterrupt:
        print("")
        return 0
    finally:
        _close(client)


# ---- the demo driver ----
# A RECORDING NEEDS WORK THAT DOES NOT STOP ARRIVING. `submit` is the
# operator's command and stays exactly what it was: two station ids, one
# transport, one line of output. `demo` is the SHIFT - it keeps
# `--in-flight` transports alive for `--duration` seconds and gets its
# pairs from work_generator, seeded, so the run can be shot twice and be
# the same run both times.
#
# IT SUBMITS THROUGH build_submission AND SUBMIT_TOPIC, the same funnel
# `submit` uses. There is no second wire and no second refusal list; a
# pair the manager will not take comes back in the status document's
# REFUSED section exactly as a typed one does.
DEMO_POLL_S = 2.0


def demo_plan(seed, count, min_len_m=MIN_LEN_M):
    """The `count` submission bodies this seed would send, in order.

    Pure and broker-free, which is what --dry-run prints and what the
    tests assert against: the plan is decidable without a fleet.
    """
    gen = WorkGenerator(seed=seed, min_len_m=min_len_m)
    return [build_submission(*gen.next_pair()) for _ in range(count)]


def _in_flight(doc):
    """How many tasks the manager is not finished with."""
    tasks = _list(doc, "tasks")
    return sum(1 for t in tasks
               if isinstance(t, dict) and t.get("state") != "DONE")


def cmd_demo(args):
    if args.in_flight < 1:
        return _die("--in-flight must be at least 1", 2)
    if args.duration <= 0:
        return _die("--duration must be positive", 2)
    if args.dry_run:
        for body in demo_plan(args.seed, args.count, args.min_len):
            print("{}  {} -> {}".format(
                body["taskId"], body["from"], body["to"]))
        return 0
    gen = WorkGenerator(seed=args.seed, min_len_m=args.min_len)
    client, inbox = _status_reader(args.host, args.port, "demo")
    if client is None:
        return 1
    deadline = time.time() + args.duration
    sent, doc = 0, None
    try:
        while time.time() < deadline:
            fresh = _await(inbox, DEMO_POLL_S)
            if fresh is not None:
                doc = _parse(fresh)
            if doc is None:
                continue
            # ONE SUBMISSION PER PASS, not a burst to the target. The
            # retained document is republished on change and on a 2 s
            # tick, so a burst would be sized against a count the
            # manager has not seen yet and the queue would overshoot.
            if _in_flight(doc) >= args.in_flight:
                continue
            body = build_submission(*gen.next_pair())
            client.publish(SUBMIT_TOPIC, json.dumps(body), qos=1)
            doc = None          # do not re-count a stale document
            sent += 1
            print("{}  {} -> {}".format(
                body["taskId"], body["from"], body["to"]), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        _close(client)
    print("demo: {} transports submitted over {:.0f} s"
          .format(sent, args.duration))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the fleet's operator console - submit transports, "
                    "read the fleet's own account of itself")
    parser.add_argument("--host", default=MQTT_HOST)
    # The same env var the trucks, the manager and send_order read.
    parser.add_argument("--port", type=int, default=MQTT_PORT)
    commands = parser.add_subparsers(dest="command")
    submit = commands.add_parser(
        "submit", help="queue a transport FROM one station TO another")
    submit.add_argument("from_station", metavar="FROM",
                        help="pickup station id ({})".format(
                            ", ".join(STATIONS)))
    submit.add_argument("to_station", metavar="TO",
                        help="dropoff station id")
    submit.add_argument("--task-id", default=None,
                        help="name the task yourself (default ft-<hex8>)")
    status = commands.add_parser(
        "status", help="render the fleet's retained status document")
    status.add_argument("--watch", action="store_true",
                        help="reprint on every update until Ctrl-C")
    demo = commands.add_parser(
        "demo", help="keep the fleet fed for a recording")
    demo.add_argument("--duration", type=float, default=600.0,
                      help="seconds to keep submitting (default 600)")
    demo.add_argument("--in-flight", type=int, default=4,
                      help="transports to keep alive (default 4)")
    demo.add_argument("--seed", type=int, default=7,
                      help="the pair sequence's seed (default 7)")
    demo.add_argument("--min-len", type=float, default=MIN_LEN_M,
                      help="shortest route worth a transport, metres")
    demo.add_argument("--count", type=int, default=25,
                      help="pairs to print under --dry-run (default 25)")
    demo.add_argument("--dry-run", action="store_true",
                      help="print the plan and exit; needs no broker")
    args = parser.parse_args(argv)
    # required=True on add_subparsers is 3.7+, but its error message is
    # 'invalid choice' rather than a usage; the explicit check prints the
    # usage an operator can act on.
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    if args.command == "submit":
        return cmd_submit(args)
    if args.command == "demo":
        return cmd_demo(args)
    return cmd_status(args)


if __name__ == "__main__":
    sys.exit(main())
