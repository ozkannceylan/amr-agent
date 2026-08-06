#!/usr/bin/env python3
"""http_face.py - the operator face: HTTP GET, and nothing else.

WHY HTTP AND NOT A ROS PRESENCE ON THE OPERATOR SIDE. The service holds no
participant in the operator domain at all (viz/DESIGN.md section 3): the
operator domain of `allocation.yaml` stays what that file says it is, a home
for hand-run tools. The page reads this service over loopback HTTP, which is
the CLAUDE.md section 3 `MON --o HMI` edge and carries no command in either
direction.

GET ONLY, AND THE REFUSAL IS IN THE CORE RATHER THAN IN THE HANDLERS. This
class defines exactly one request method, `do_GET`. Every other HTTP verb -
POST, PUT, DELETE, PATCH, and anything a client invents - resolves through
`__getattr__` to one refusal that answers **405** and returns, before any
handler runs and without reading a single byte of a request body. There is no
code path in this file that reads `rfile`. A body that is never read is a body
that cannot be acted on.

THE CONNECTION IS CLOSED ON A REFUSAL, DELIBERATELY. An unread body would
otherwise be parsed as the next request on a keep-alive connection, so the
refusal ends the connection rather than desynchronising it. Refusing and then
mis-parsing would be worse than either.

WHAT A GET MAY CHANGE. Operator-side subscription state, and nothing else:
opening a camera stream takes a refcount that creates a DDS subscription in
that vehicle's context, closing it releases one (DESIGN section 7). Nothing
enters a vehicle domain when a view opens or closes. No GET anywhere in this
file touches the PLC, the bridge, the fleet layer or any actuator.
"""

import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DEFAULT_BIND = '127.0.0.1'

#: Its OWN port, not the HMI backend's 8088. Two services on two planes; a
#: shared port would make the monitoring plane look like part of the process
#: plane to anyone reading a config.
DEFAULT_PORT = 8089


class MonitorHandler(BaseHTTPRequestHandler):
    server_version = 'amr-agent-viz'
    sys_version = ''

    #: Injected by serve(); the service instance this handler reads.
    service = None

    def log_message(self, fmt, *args):          # noqa: A003 - stdlib signature
        # The operator's terminal is not a request log. Errors go through the
        # service's own bounded reporting instead.
        return

    # -- the core refusal ---------------------------------------------------

    def __getattr__(self, name):
        """Answer 405 for every verb but GET, before any handler exists.

        `__getattr__` runs only when normal attribute lookup fails, so the one
        defined method - `do_GET` - is found normally and never reaches here.
        Everything else the stdlib dispatcher looks for lands on the refusal.
        """
        if name.startswith('do_'):
            return self._method_not_allowed
        raise AttributeError(name)

    def _method_not_allowed(self):
        body = json.dumps({
            'error': 'method not allowed',
            'allow': 'GET',
            'why': 'this service is read-only by construction of the process '
                   'and proven by test; not enforced by the middleware '
                   '(viz/DESIGN.md section 2). It has no write surface to '
                   'reach with any verb.',
        }).encode('utf-8')
        self.send_response(405)
        self.send_header('Allow', 'GET')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    # -- sending ------------------------------------------------------------

    def _send(self, code, body, content_type, extra=None):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for key, value in (extra or {}).items():
            self.send_header(key, str(value))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, payload, extra=None):
        self._send(code, json.dumps(payload).encode('utf-8'),
                   'application/json', extra)

    # -- the only request method --------------------------------------------

    def do_GET(self):                            # noqa: N802 - stdlib signature
        path = self.path.split('?', 1)[0].rstrip('/') or '/'
        parts = [p for p in path.split('/') if p]

        if path == '/':
            self._json(200, self.service.describe())
            return
        if parts == ['vehicles']:
            self._json(200, self.service.vehicles())
            return
        if len(parts) >= 2 and parts[0] == 'vehicles':
            serial = parts[1]
            link = self.service.link(serial)
            if link is None:
                self._json(404, {'error': 'no vehicle {!r} is served'.format(
                    serial), 'served': sorted(self.service.links)})
                return
            tail = parts[2:]
            if tail == ['state']:
                self._json(200, link.state())
                return
            if tail == ['map']:
                self._serve_map(link)
                return
            if tail == ['cameras']:
                self._json(200, self.service.cameras(serial))
                return
            if len(tail) == 3 and tail[0] == 'cameras' and tail[2] == 'stream':
                self._serve_camera_stream(serial, tail[1])
                return
        self._json(404, {'error': 'no such path', 'path': path})

    # -- payloads ------------------------------------------------------------

    def _serve_map(self, link):
        """The WHOLE occupancy grid, full extent, never a crop.

        Raw `int8` cells in row-major order, gzipped for transport, with the
        version echoed in a header so the page refetches only when the map
        actually changed. It is served as cells rather than as an image because
        the page's canvas needs the cells anyway and a PNG encoder would be a
        dependency or hand-rolled code for no gain (DESIGN section 5).
        """
        version, cells, meta = link.map_bytes()
        if meta is None:
            self._json(503, {
                'error': 'no map has been received from {} yet'.format(
                    link.serial),
                'map_version': version,
            })
            return
        body = gzip.compress(cells)
        self._send(200, body, 'application/octet-stream', {
            'Content-Encoding': 'gzip',
            'X-Map-Version': version,
            'X-Map-Cells': len(cells),
            'X-Map-Width': meta['width'],
            'X-Map-Height': meta['height'],
            'X-Map-Resolution-M': meta['resolution_m'],
            'X-Map-Origin-X-M': meta['origin']['x_m'],
            'X-Map-Origin-Y-M': meta['origin']['y_m'],
            'X-Map-Frame': meta['frame'],
        })

    def _serve_camera_stream(self, serial, camera_id):
        """Open a view: take a refcount; close it: release one (DESIGN 7).

        No camera exists on the model yet (V3-4 adds one), so the registry is
        empty and this answers 404 before any refcount is taken. The path
        through the refcounted manager is the same one a camera will use, and
        it is exercised end to end by `service.py --refcount-demo`.
        """
        acquired = self.service.open_stream(serial, camera_id)
        if acquired is None:
            self._json(404, {
                'error': 'no camera {!r} on {}'.format(camera_id, serial),
                'cameras': self.service.cameras(serial)['cameras'],
                'note': 'cameras arrive at V3-4 (hmi/V3-PLAN.md). The '
                        'subscription lifecycle that will serve them is '
                        'built and exercised; the sensor is not on the model.',
            })
            return
        try:
            self._json(501, {'error': 'stream encoding is V3-5'})
        finally:
            self.service.close_stream(serial, camera_id)


def serve(service, bind=DEFAULT_BIND, port=DEFAULT_PORT):
    """Start the GET-only server on its own thread. Returns the server."""
    handler = type('BoundMonitorHandler', (MonitorHandler,),
                   {'service': service})
    httpd = ThreadingHTTPServer((bind, port), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, name='viz-http',
                     daemon=True).start()
    return httpd
