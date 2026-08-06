#!/usr/bin/env python3
"""http_probe.py - the HTTP acceptance checks of viz/DESIGN.md, against a
running service.

    python3 viz/tools/http_probe.py --serial F001
    python3 viz/tools/http_probe.py --serial F001 --stale 30

CHECK 8.3  every verb but GET is answered 405 on every endpoint, including a
           verb no client should send; the GETs answer with the section 5
           payloads; `/state` carries no raster.
CHECK 8.5  the bytes served on `/map` are the last received grid - `width x
           height` cells, byte-identical across two fetches - and `map_version`
           equals the number of map messages received, which is what "bumps
           exactly once per received map message" means when both numbers come
           from the same running process.
CHECK 8.4  `--stale N` samples `/state` for N seconds and prints every age, so
           a vehicle stack stopped mid-run shows ages GROWING rather than a
           value keeping its live look.

It sends only HTTP. It joins no DDS domain and imports no ROS.
"""

import argparse
import gzip
import http.client
import json
import sys
import time

VERBS = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'FROB']


def request(host, port, verb, path, body=None):
    conn = http.client.HTTPConnection(host, port, timeout=10)
    try:
        conn.request(verb, path, body=body,
                     headers={'Content-Length': str(len(body or b''))})
        resp = conn.getresponse()
        payload = resp.read()
        return resp.status, dict(resp.getheaders()), payload
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8089)
    parser.add_argument('--serial', default='F001')
    parser.add_argument('--stale', type=float, default=0.0,
                        help='seconds to sample /state for check 8.4')
    parser.add_argument('--stale-period', type=float, default=2.0)
    args = parser.parse_args(argv)

    base = '/vehicles/{}'.format(args.serial)
    paths = ['/', '/vehicles', base + '/state', base + '/map',
             base + '/cameras', base + '/cameras/front/stream']
    failures = []

    print('=== CHECK 8.3a  method matrix: GET is the only verb ===')
    print('{:<40} {}'.format('path', '  '.join('{:>7}'.format(v)
                                               for v in VERBS)))
    for path in paths:
        row = []
        for verb in VERBS:
            body = b'{"traction": 1.0}' if verb in ('POST', 'PUT', 'PATCH') \
                else None
            try:
                status, _headers, _payload = request(
                    args.host, args.port, verb, path, body)
            except Exception as exc:                      # noqa: BLE001
                status = 'ERR {}'.format(exc)
            row.append(status)
            if verb != 'GET' and status != 405:
                failures.append('{} {} -> {} (expected 405)'.format(
                    verb, path, status))
        print('{:<40} {}'.format(path, '  '.join('{:>7}'.format(str(s))
                                                 for s in row)))
    status, headers, payload = request(args.host, args.port, 'POST',
                                       base + '/state', b'{"x": 1}')
    print('\nthe 405 body and its Allow header:')
    print('   Allow: {!r}'.format(headers.get('Allow')))
    print('   {}'.format(payload.decode('utf-8')))
    if headers.get('Allow') != 'GET':
        failures.append('the 405 did not carry Allow: GET')

    print('\n=== CHECK 8.3b  the GET payloads ===')
    for path in ['/', '/vehicles', base + '/state', base + '/cameras']:
        status, _h, payload = request(args.host, args.port, 'GET', path)
        print('\nGET {}  -> {}  {} bytes'.format(path, status, len(payload)))
        try:
            doc = json.loads(payload)
        except ValueError:
            failures.append('{} did not answer JSON'.format(path))
            continue
        print(json.dumps(doc, indent=2)[:1400])
        if status != 200:
            failures.append('{} -> {}'.format(path, status))

    print('\n=== CHECK 8.3c  /state carries no raster ===')
    _s, _h, payload = request(args.host, args.port, 'GET', base + '/state')
    state = json.loads(payload)
    print('   /state is {} bytes'.format(len(payload)))
    print('   keys: {}'.format(sorted(state)))
    print('   map_cells is {!r} - a COUNT of cells, not the cells'.format(
        state.get('map_cells')))
    biggest = sorted(((len(json.dumps(v)), k) for k, v in state.items()),
                     reverse=True)[:3]
    print('   largest fields: {}'.format(
        [(k, '{} bytes'.format(n)) for n, k in biggest]))
    if not isinstance(state.get('map_cells'), int):
        failures.append('/state map_cells is not an integer count')
    for key, value in state.items():
        if isinstance(value, str) and len(value) > 1024:
            failures.append('/state field {} is a {}-char blob'.format(
                key, len(value)))

    print('\n=== CHECK 8.5  map integrity ===')
    s1, h1, b1 = request(args.host, args.port, 'GET', base + '/map')
    time.sleep(0.5)
    s2, h2, b2 = request(args.host, args.port, 'GET', base + '/map')
    print('   GET {}/map -> {}  {} transported bytes, gzip'.format(
        base, s1, len(b1)))
    if s1 != 200:
        print('   {}'.format(b1.decode('utf-8')[:400]))
        failures.append('/map -> {}'.format(s1))
    else:
        cells1, cells2 = gzip.decompress(b1), gzip.decompress(b2)
        width, height = int(h1['X-Map-Width']), int(h1['X-Map-Height'])
        print('   headers: version={} cells={} {}x{} res={} origin=({}, {}) '
              'frame={}'.format(
                  h1['X-Map-Version'], h1['X-Map-Cells'], width, height,
                  h1['X-Map-Resolution-M'], h1['X-Map-Origin-X-M'],
                  h1['X-Map-Origin-Y-M'], h1['X-Map-Frame']))
        print('   decompressed: {} cells; width*height = {}'.format(
            len(cells1), width * height))
        print('   two fetches byte-identical: {}'.format(cells1 == cells2))
        print('   map_version stable across fetches: {}'.format(
            h1['X-Map-Version'] == h2['X-Map-Version']))
        occupied = sum(1 for c in cells1 if c not in (0, 255))
        print('   cell value histogram (top 4): {}'.format(
            sorted(((cells1.count(v), v) for v in set(cells1)),
                   reverse=True)[:4]))
        print('   cells that are neither 0 nor 255 (0xFF = -1 unknown): {}'
              .format(occupied))
        if len(cells1) != width * height:
            failures.append('map bytes {} != width*height {}'.format(
                len(cells1), width * height))
        if cells1 != cells2:
            failures.append('two /map fetches differed')
        received = state.get('messages_received', {}).get('map')
        version = state.get('map_version')
        print('   map messages received = {}; map_version = {}  -> one bump '
              'per received message: {}'.format(
                  received, version, received == version))
        if received != version:
            failures.append('map_version {} != map messages received {}'
                            .format(version, received))

    if args.stale > 0:
        print('\n=== CHECK 8.4  ages under a stopped vehicle stack ===')
        print('{:>8}  {:>14} {:>18} {:>14} {:>12}'.format(
            'elapsed', 'pose_age_ms', 'obstacles_age_ms', 'map_age_ms',
            'msgs(pose)'))
        started = time.monotonic()
        while time.monotonic() - started < args.stale:
            _s, _h, payload = request(args.host, args.port, 'GET',
                                      base + '/state')
            doc = json.loads(payload)
            print('{:>8.1f}  {:>14} {:>18} {:>14} {:>12}'.format(
                time.monotonic() - started, str(doc['pose_age_ms']),
                str(doc['obstacles_age_ms']), str(doc['map_age_ms']),
                doc['messages_received']['pose']))
            sys.stdout.flush()
            time.sleep(args.stale_period)

    print('\n{}'.format('HTTP PROBE PASS' if not failures
                        else 'HTTP PROBE FAIL:\n  ' + '\n  '.join(failures)))
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
