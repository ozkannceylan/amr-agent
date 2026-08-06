#!/usr/bin/env python3
"""check_hmi_map_pane.py - the v2b map pane's backend half, exercised.

    #############################################################
    #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
    #############################################################

What it proves, each check printed with the values it read (hmi/V2B-DESIGN.md
section 7 items 1, 4 and 6; the DOM half is `capture_v2b_screens.mjs`, because
an endpoint test that never presses the page is the residual EVIDENCE_HMI.md
section C already carries):

  1  the source: exactly one outbound request construction in `hmi/`, and it is
     GET. No other client of any kind reaches the monitoring service
  2  the method matrix: GET only on the three /monitor paths, and the process's
     write surface is still exactly POST /control
  3  nothing is cached: two fetches a second apart carry two different ages,
     and the upstream payload is passed through key for key
  4  the map: the whole grid, byte-identical to what the service served, cells
     equal to width x height
  5  the monitoring service stopped mid-run: the pane's source goes unreachable
     and the PROCESS plane is untouched - session still CONNECTED, heartbeat
     still advancing, backend still alive and not logging in a loop
  6  the H6 beacon excludes /monitor: polling ONLY the map pane lets the page
     beacon go STALE, which is the whole point of excluding it
  7  a non-loopback monitor URL refuses to start the process

It starts its own doubles and its own backend, on their own ports, and stops
them. Nothing recorded against a double closes any criterion.

Run:
    python hmi/tools/check_hmi_map_pane.py
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
HMI = HERE.parent
REPO = HMI.parent

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(("   PASS  " if ok else "   FAIL  ") + name + ("  " + detail if detail else ""))
    if not ok:
        FAILURES.append(name + " " + detail)
    return ok


def http(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 5.0):
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def wait_for(what, fn, timeout=40.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = fn()
            if last:
                return last
        except Exception as exc:                      # noqa: BLE001
            last = repr(exc)
        time.sleep(0.2)
    raise SystemExit(f"timed out waiting for {what} (last: {last})")


# --------------------------------------------------------------------------- #
# 1. the source sweep
# --------------------------------------------------------------------------- #

def check_source():
    print("\n=== CHECK 1  the source: one outbound request construction, and it is GET ===")
    src = (HMI / "hmi_server.py").read_text(encoding="utf-8")
    constructions = re.findall(r"urllib\.request\.Request\((.{0,120})", src, re.S)
    check("exactly one urllib.request.Request(...) in hmi_server.py",
          len(constructions) == 1, f"found {len(constructions)}")
    if constructions:
        check("and it is constructed with method=\"GET\"",
              'method="GET"' in constructions[0].replace("'", '"'),
              constructions[0].split("\n")[0].strip())
    # No other way out of this process toward anything.
    forbidden = ["http.client", "import requests", "socket.create_connection",
                 "aiohttp", "httpx"]
    for token in forbidden:
        check(f"no {token!r} anywhere in hmi_server.py", token not in src)
    check("no request body is ever sent upstream: no data= on the Request",
          "urllib.request.Request(self.base_url + path, method=\"GET\")" in src)
    # The write allowlist is untouched by this version.
    names = re.search(r"HMI_WRITABLE_PATHS: dict\[str, tuple\[str, \.\.\.\]\] = \{(.*?)\n\}",
                      src, re.S)
    n = len(re.findall(r'^\s{4}"', names.group(1), re.M)) if names else -1
    check("the OPC UA write allowlist is still exactly eight nodes", n == 8, f"n={n}")


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--hmi-port", type=int, default=8096)
    ap.add_argument("--viz-port", type=int, default=8098)
    ap.add_argument("--opcua-port", type=int, default=4862,
                help="must match config-v2b-double.yaml's endpoint")
    args = ap.parse_args()

    hmi_base = f"http://127.0.0.1:{args.hmi_port}"
    viz_base = f"http://127.0.0.1:{args.viz_port}"

    check_source()

    print("\n=== CHECK 7  a non-loopback monitoring URL refuses to start ===")
    out = subprocess.run(
        [args.python, str(HMI / "hmi_server.py"), "--config",
         str(HMI / "config-v2b-double.yaml"), "--monitor-url",
         "http://10.11.12.13:8089", "--run-seconds", "1"],
        cwd=REPO, capture_output=True, text=True)
    check("refused, naming invariant 8",
          out.returncode != 0 and "invariant 8" in (out.stderr + out.stdout),
          (out.stderr.strip().splitlines() or ["(no output)"])[-1][:160])

    procs = []

    def start(name, argv, env=None):
        log = open(os.path.join(os.environ.get("TEMP", "/tmp"),
                                f"check_map_{name}.log"), "w", encoding="utf-8")
        p = subprocess.Popen(argv, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                             env=env)
        procs.append((name, p, log))
        print(f"   started {name} pid {p.pid}")
        return p

    try:
        viz = start("viz", [args.python, str(HERE / "viz_double.py"),
                            "--port", str(args.viz_port), "--scenario", "live",
                            "--run-seconds", "300"])
        start("plc", [args.python, str(HERE / "v2a_scenario_double.py"),
                      "--port", str(args.opcua_port), "--scenario", "coldstart",
                      "--run-seconds", "300", "--with-safety-mirrors"])
        time.sleep(3.5)
        start("hmi", [args.python, str(HMI / "hmi_server.py"),
                      "--config", str(HMI / "config-v2b-double.yaml"),
                      "--http-port", str(args.hmi_port),
                      "--monitor-url", viz_base,
                      "--run-seconds", "300"])
        wait_for("the HMI backend to connect",
                 lambda: json.loads(http(hmi_base + "/state")[2])["session"]["state"]
                 == "CONNECTED")

        # --- 2 -------------------------------------------------------------
        print("\n=== CHECK 2  the method matrix ===")
        paths = ["/monitor/vehicles", "/monitor/state", "/monitor/map?serial=F001",
                 "/", "/state", "/control"]
        verbs = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "FROB"]
        print("   {:34s}".format("path") + "".join(f"{v:>8s}" for v in verbs))
        matrix = {}
        for path in paths:
            row = []
            for verb in verbs:
                body = b"{}" if verb in ("POST", "PUT", "PATCH") else None
                row.append(http(hmi_base + path, verb, body)[0])
            matrix[path] = row
            print("   {:34s}".format(path) + "".join(f"{c:>8d}" for c in row))
        for path in ["/monitor/vehicles", "/monitor/state", "/monitor/map?serial=F001"]:
            row = matrix[path]
            check(f"{path}: GET answers, every other verb refused",
                  row[0] == 200 and all(c in (405,) for c in row[1:]), str(row))
        check("POST /control is still accepted - the write surface is unchanged",
              matrix["/control"][1] == 200, str(matrix["/control"]))
        check("POST is refused everywhere else",
              matrix["/state"][1] == 404 and matrix["/monitor/state"][1] == 405)

        # --- 3 -------------------------------------------------------------
        print("\n=== CHECK 3  nothing cached; the upstream payload passes through ===")
        a = json.loads(http(hmi_base + "/monitor/state")[2])
        upstream = json.loads(http(viz_base + "/vehicles/F001/state")[2])
        time.sleep(1.0)
        b = json.loads(http(hmi_base + "/monitor/state")[2])
        check("the two fetches carry different ages - no cache",
              a["state"]["pose_age_ms"] != b["state"]["pose_age_ms"],
              f'{a["state"]["pose_age_ms"]} then {b["state"]["pose_age_ms"]}')
        check("the key set is the monitoring service's, unrenamed",
              set(a["state"]) == set(upstream),
              str(sorted(set(a["state"]) ^ set(upstream)) or "identical"))
        meta = a["monitor"]
        check("the envelope carries only THIS backend's own channel facts and the ramp",
              set(meta) >= {"reachable", "fetch_ms", "age_ramp_start_ms",
                            "age_ramp_full_ms", "poll_period_ms"},
              str(sorted(meta)))
        check("the display ramp is published to the page, not invented by it",
              isinstance(meta["age_ramp_start_ms"], (int, float))
              and meta["age_ramp_full_ms"] > meta["age_ramp_start_ms"],
              f'{meta["age_ramp_start_ms"]} .. {meta["age_ramp_full_ms"]} ms')
        # The raster check is a COMPARISON, not a display: no field on the poll
        # may be as long as the cell count, and the whole payload must be orders
        # of magnitude smaller than the grid it describes (LESSONS 2026-08-05: a
        # checker that prints two values without comparing them is a display).
        cell_count = a["state"]["map_cells"]
        longest = max((len(json.dumps(v)), k) for k, v in a["state"].items())
        check("/monitor/state carries no raster - the map rides as a cell COUNT",
              isinstance(cell_count, int) and longest[0] < cell_count
              and len(json.dumps(a)) < cell_count,
              f"map_cells={cell_count}; whole payload {len(json.dumps(a))} bytes; "
              f"largest field {longest[1]} at {longest[0]} bytes")

        # --- 4 -------------------------------------------------------------
        print("\n=== CHECK 4  the map: whole grid, byte-identical ===")
        s_hmi, h_hmi, body_hmi = http(hmi_base + "/monitor/map?serial=F001")
        s_viz, h_viz, body_viz = http(viz_base + "/vehicles/F001/map")
        # THE ONE FIELD THAT CANNOT BE EQUAL, AND WHY THIS IS NOT A WEAKENING.
        # These are two independent GETs, so the service compresses twice, and
        # RFC 1952 puts a wall-clock MTIME in bytes 4..8 of every gzip header.
        # Comparing those four bytes tests when the two requests landed relative
        # to a second boundary and nothing else: the original form of this check
        # passed at m5-53 and failed at m5-53b on the identical proxy path, and
        # a probe pinned the difference to offset 4 alone with the decompressed
        # cells equal in every case. Everything else is still compared bit for
        # bit — the whole deflate stream included, so a re-encode by this
        # backend would still fail — and the cells are now compared as well,
        # which the raw comparison alone never did.
        MTIME = slice(4, 8)
        stripped_hmi = body_hmi[:MTIME.start] + body_hmi[MTIME.stop:]
        stripped_viz = body_viz[:MTIME.start] + body_viz[MTIME.stop:]
        check("the proxied body is byte-identical to the service's, but for the "
              "gzip header's wall-clock MTIME (two compressions, RFC 1952)",
              stripped_hmi == stripped_viz,
              f"{len(body_hmi)} vs {len(body_viz)} bytes; "
              f"{len(stripped_hmi)} compared")
        check("and the CELLS themselves are identical - nothing was re-encoded",
              gzip.decompress(body_hmi) == gzip.decompress(body_viz),
              f"{len(gzip.decompress(body_hmi))} cells")
        cells = gzip.decompress(body_hmi)
        w, hh = int(h_hmi["X-Map-Width"]), int(h_hmi["X-Map-Height"])
        check("cells == width x height - the WHOLE map, never a crop",
              len(cells) == w * hh, f"{len(cells)} == {w} x {hh}")
        check("the X-Map-* headers survived the proxy",
              all(k in h_hmi for k in ("X-Map-Version", "X-Map-Resolution-M",
                                       "X-Map-Origin-X-M", "X-Map-Frame")),
              str([k for k in h_hmi if k.lower().startswith("x-map-")]))
        res = float(h_hmi["X-Map-Resolution-M"])
        print(f"   {w} x {hh} at {res} m = {w*res:.1f} x {hh*res:.1f} m, "
              f"{len(cells)} cells in {len(body_hmi)} transported bytes")

        # --- 6 (before 5: it needs a live service) --------------------------
        print("\n=== CHECK 6  the H6 beacon does not count a map fetch ===")
        stale_after = json.loads(http(hmi_base + "/state")[2])["page"]["stale_after_ms"]
        http(hmi_base + "/state")          # one real page poll, to start LIVE
        time.sleep(0.3)
        deadline = time.monotonic() + (stale_after / 1000.0) * 2.5
        while time.monotonic() < deadline:
            http(hmi_base + "/monitor/state")
            time.sleep(0.1)
        page = json.loads(http(hmi_base + "/state")[2])["page"]
        check("polling ONLY /monitor let the page beacon go STALE",
              page["state"] == "STALE" or page["drops"] >= 1,
              f'state={page["state"]} drops={page["drops"]} '
              f'window={stale_after} ms')

        # --- 5 -------------------------------------------------------------
        print("\n=== CHECK 5  the monitoring service stopped mid-run ===")
        before = json.loads(http(hmi_base + "/state")[2])
        viz.terminate()
        viz.wait(timeout=10)
        time.sleep(1.0)
        env = json.loads(http(hmi_base + "/monitor/state")[2])
        check("the pane's source reports unreachable, with a reason",
              env["monitor"]["reachable"] is False and env["monitor"]["reason"],
              str(env["monitor"]["reason"])[:90])
        check("and it serves NO state at all - not a last value",
              env["state"] is None and env["vehicles"] is None)
        code = http(hmi_base + "/monitor/map?serial=F001")[0]
        check("the raster path answers a failure, never stale bytes", code == 502,
              str(code))
        after = json.loads(http(hmi_base + "/state")[2])
        check("the PROCESS plane is untouched: session still CONNECTED",
              after["session"]["state"] == "CONNECTED", after["session"]["state"])
        check("the heartbeat kept advancing across the outage",
              after["heartbeat"]["value"] != before["heartbeat"]["value"]
              and after["heartbeat"]["running"] is True,
              f'{before["heartbeat"]["value"]} -> {after["heartbeat"]["value"]}')
        time.sleep(2.0)
        log_path = os.path.join(os.environ.get("TEMP", "/tmp"), "check_map_hmi.log")
        lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
        noisy = [ln for ln in lines if "monitor" in ln.lower()
                 and ("Traceback" in ln or "ERROR" in ln)]
        check("the backend logged no error storm about the dead service",
              len(noisy) == 0, f"{len(noisy)} lines")

    finally:
        for name, p, log in procs:
            try:
                p.terminate()
                p.wait(timeout=8)
            except Exception:                          # noqa: BLE001
                p.kill()
            log.close()
        print("\n   all children stopped")

    print("\nMAP PANE CHECK " + ("PASS" if not FAILURES else "FAIL"))
    for f in FAILURES:
        print("   " + f)
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
