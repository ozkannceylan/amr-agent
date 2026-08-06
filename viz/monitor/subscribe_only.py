#!/usr/bin/env python3
"""subscribe_only.py - THE ONE ENTITY FACTORY OF THIS LAYER.

WHAT THIS MODULE IS. Every rclpy object the monitoring service ever creates is
created here, and the public API of this module can create exactly two kinds of
thing: a zero-endpoint node inside a named DDS domain, and a subscription on
that node. There is no code path in this module that produces a publisher, a
service, an action or a parameter write, and there is no other module in
`viz/` that constructs an rclpy object at all.

THE CLAIM THIS SUPPORTS, IN ITS ONLY ADMISSIBLE FORM:

    read-only by construction of the process and proven by test; not enforced
    by the middleware.

Never the unqualified short form. Nothing in DDS stops this process from
creating a publisher - "no publisher" is a property of this source file that
one edit would flip, and this project does not run DDS-Security access control
(viz/DESIGN.md section 2 states the cost and records what would remove the
limitation). What makes it construction rather than habit is that the flip
would have to happen HERE, in a file whose whole subject is that it does not,
and that the running graph is asked rather than the source trusted.

WHY THE CONSTRUCTOR FLAGS ARE NOT ENOUGH, WHICH IS THE POINT OF THE RECIPE
BELOW. On Jazzy a node built with `enable_rosout=False`,
`start_parameter_services=False`, `enable_logger_service=False` and the
`start_type_description_service=False` override still carries ONE publisher:
`/parameter_events`, created by `Node.__init__` itself and reachable by no
flag. A node advertised as having no publisher would have had one, in exactly
the check meant to prove it (docs/LESSONS.md 2026-08-06). The one explicit
teardown below is what actually reaches zero, and
`viz/tools/zero_endpoint_probe.py` shows both variants side by side on a
running graph so the difference is observable rather than described.

THE FORBIDDEN-CALL LIST, AND WHY IT LIVES IN THIS FILE. `viz/DESIGN.md`
section 2.1 requires that a grep of this layer's source for the entity-creating
call names hits only this module's list. The list is therefore data, with one
owner (invariant 10): `viz/tools/check_construction.py` READS it from the lines
below rather than carrying a second copy that could drift from this one.

    forbidden-call: create_publisher
    forbidden-call: create_service
    forbidden-call: create_client
    forbidden-call: ActionServer
    forbidden-call: ActionClient
    forbidden-call: set_parameters

Those six names appear nowhere else in this layer's source. The occurrence
above is the definition of the check, and it is the only one the check
tolerates.

NOTHING HERE IS A CONTROL PATH. It joins domains, listens, and hands messages
to a callback. It sends nothing, on any transport.
"""

import threading

import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)


class ReadOnlyViolation(RuntimeError):
    """Raised when this module is asked for something it must not build."""


#: QoS for a latched topic - the map, and `/tf_static`. A subscriber that is
#: merely RELIABLE/VOLATILE joins a latched publisher's topic and then waits
#: for the next message, which for a map server is never: the map was
#: published once, before this process existed. TRANSIENT_LOCAL is what makes
#: joining late work at all.
LATCHED = QoSProfile(depth=1,
                     history=HistoryPolicy.KEEP_LAST,
                     reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)

#: QoS for a live stream - pose, scan, `/tf`. VOLATILE on the reader side is
#: compatible with a TRANSIENT_LOCAL writer as well as a VOLATILE one, so this
#: profile matches every producer in the vehicle image without a per-topic
#: table that could go stale.
LIVE = QoSProfile(depth=10,
                  history=HistoryPolicy.KEEP_LAST,
                  reliability=ReliabilityPolicy.RELIABLE,
                  durability=DurabilityPolicy.VOLATILE)


def _strip_residual_publisher(node):
    """Destroy the one publisher `Node.__init__` makes regardless of flags.

    Returns the topic name that was destroyed, or None if this rclpy build did
    not make one - in which case nothing is wrong and nothing is assumed: the
    caller's verification is `ros2 node info` on the running node, never this
    return value.
    """
    residual = getattr(node, '_parameter_event_publisher', None)
    if residual is None:
        return None
    topic = residual.topic_name
    node.destroy_publisher(residual)
    node._parameter_event_publisher = None  # noqa: SLF001 - see the docstring
    return topic


class SubscribeOnlyNode(object):
    """One zero-endpoint node in one DDS domain, with its own context.

    One instance per vehicle. The context is what carries the domain: rclpy
    lets a process hold several, and that is the whole mechanism of ADR 0016
    D3(c) as viz/DESIGN.md section 3 rules it - one process, n domains, no
    republishing anywhere.
    """

    def __init__(self, node_name, domain_id, strip_residual=True):
        """`strip_residual=False` builds the COUNTEREXAMPLE, on purpose.

        The service never passes it. `viz/tools/zero_endpoint_probe.py` does,
        so that the flags-only node and the full-recipe node can be held alive
        side by side in one scratch domain and `ros2 node info` run against
        both: the check passing, and what it looks like when it would fail.
        The counterexample is constructed HERE rather than in the probe so that
        this module remains the only place in the layer that builds an rclpy
        object at all.
        """
        self.node_name = node_name
        self.domain_id = int(domain_id)
        self.strip_residual = bool(strip_residual)

        self._context = Context()
        self._context.init(domain_id=self.domain_id, initialize_logging=False)

        # THE RECIPE. Four switches and one teardown; the teardown is the half
        # that actually reaches zero (see the module docstring).
        self._node = Node(
            node_name,
            context=self._context,
            enable_rosout=False,
            start_parameter_services=False,
            enable_logger_service=False,
            parameter_overrides=[
                Parameter('start_type_description_service',
                          Parameter.Type.BOOL, False),
            ],
            automatically_declare_parameters_from_overrides=False,
        )
        self.residual_publisher_destroyed = (
            _strip_residual_publisher(self._node)
            if self.strip_residual else None)

        self._executor = SingleThreadedExecutor(context=self._context)
        self._executor.add_node(self._node)
        self._thread = None
        self._lock = threading.Lock()
        self._subscriptions = {}

    # -- what the node advertises, asked of the node rather than assumed ----

    def endpoint_census(self):
        """Count what this node offers the graph, from the node itself.

        This is the process's own view. It is NOT the proof: the proof is
        `ros2 node info` against the running node from a shell inside the
        vehicle's domain, because what the graph advertises is the fact and a
        constructor argument is only a request (docs/LESSONS.md 2026-08-06).
        This exists so a self-check can fail early and loudly.
        """
        # rclpy exposes these as generators on Jazzy, not lists. `len()` on a
        # generator raises rather than returning a wrong number, which is the
        # good direction, but the census still has to materialise them.
        node = self._node
        return {
            'subscriptions': len(list(node.subscriptions)),
            'publishers': len(list(node.publishers)),
            'services': len(list(node.services)),
            'clients': len(list(node.clients)),
            'timers': len(list(node.timers)),
        }

    def assert_zero_endpoints(self):
        census = self.endpoint_census()
        offered = {k: v for k, v in census.items()
                   if k in ('publishers', 'services', 'clients') and v}
        if offered:
            raise ReadOnlyViolation(
                '{} in domain {} offers {} to the graph. This layer holds no '
                'endpoint in any vehicle domain (viz/DESIGN.md section 2); a '
                'node that does is a defect, not a configuration.'.format(
                    self.node_name, self.domain_id, offered))
        return census

    # -- the only thing this factory builds ---------------------------------

    def subscribe(self, topic, msg_type, callback, qos=None):
        """Create one subscription. The only entity this API can produce."""
        with self._lock:
            if topic in self._subscriptions:
                raise ReadOnlyViolation(
                    'already subscribed to {} on {}'.format(
                        topic, self.node_name))
            handle = self._node.create_subscription(
                msg_type, topic, callback, qos or LIVE)
            self._subscriptions[topic] = handle
        return handle

    def unsubscribe(self, topic):
        """Destroy one subscription. Nothing leaves this process either way."""
        with self._lock:
            handle = self._subscriptions.pop(topic, None)
        if handle is None:
            return False
        self._node.destroy_subscription(handle)
        return True

    def subscribed_topics(self):
        with self._lock:
            return sorted(self._subscriptions)

    # -- lifecycle -----------------------------------------------------------

    def spin_in_thread(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._spin, name='viz-{}'.format(self.domain_id),
            daemon=True)
        self._thread.start()

    def _spin(self):
        try:
            self._executor.spin()
        except (rclpy.executors.ExternalShutdownException, RuntimeError):
            # A context shut down under a spinning executor is the ordinary
            # way this thread ends. It is not an error and does not deserve a
            # traceback on the operator's terminal.
            pass

    def shutdown(self):
        try:
            self._executor.shutdown()
        finally:
            try:
                self._node.destroy_node()
            finally:
                self._context.try_shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
