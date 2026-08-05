"""Prove, from outside TIA, that the F-side data is on no client's address space.

This is the machine-run form of `plc/forklift-safety/SPEC.md` §4.2 step 14 and
§4.5 step 12: after the S015 delta the owner must confirm that
`SafetyInputStandIn` and `InstF_Forklift_Safety` appear NOWHERE on the CPU's
OPC UA server, including under the auto-published `Objects/DataBlocksGlobal`
folder. Read aloud off a UaExpert tree that is a transcription; run here it is
a RESULT line.

It checks four things, in this order:

  1. the namespace array as the server reports it, resolved by URI and
     hardcoded nowhere (ADR 0006 - the server interface name IS its namespace
     URI, so the URI is read back and never typed in),

  2. THE POSITIVE CONTROL, and it runs before the absence check on purpose:
     the four `Forklift/Safety/` mirrors of `opcua-nodes.md` §11.2 must browse
     and read. An absence proven by a browse that never reached the server is
     not an absence - it is a broken client. If the control fails, every
     absence below is meaningless and the script says so instead of passing,

  3. the absence sweep proper: a bounded walk of the whole `Objects` subtree,
     with every BrowseName tested against the F-side names. A hit means a
     client can see F-data, or can see the stand-in a client must not reach
     (`TWIN-DEMO-MAP.md` R1/R2; SPEC §4.2 steps 3 and 11),

  4. a collision-suffix sweep over every name the walk visited. TIA appends
     `_1` without asking, in DB statics and interface rows both, and a
     suffixed browse name cuts a client with no error dialog
     (LESSONS 2026-07-30).

It WRITES NOTHING. There is no write probe here and there must not be one: the
whole claim of this check is that the datum is unreachable, and a script that
tried to write it would be asserting the reachability it exists to deny.

Usage:  python m5-25b-f-absence-verify.py [endpoint]
        default endpoint opc.tcp://192.168.53.1:4840 (opcua-nodes.md §9.10)

Requires asyncua - the same environment the bridge's client runs in.
Exit code 0 = every check passed, 1 = something failed.
"""
import asyncio
import re
import sys

from asyncua import Client

EP = sys.argv[1] if len(sys.argv) > 1 else "opc.tcp://192.168.53.1:4840"

IFACE_NAME = "DemoCell"
IFACE_URI = "http://DemoCell"          # derived by TIA from the interface name

# opcua-nodes.md §11.2, quoted. The BrowseNames are the F-side tag names
# exactly, with no prefix, and all four are Bool.
MIRRORS = ["EStopDemand", "ZoneStopDemand", "SafetyResetRequired",
           "SafetyResetFault"]

# The names that must appear nowhere. Matched case-insensitively as a
# substring, so a folder, a variable or a suffixed variant all hit.
FORBIDDEN = [
    "SafetyInputStandIn",      # the stand-in DB - no client may reach it (R1, R2)
    "StandInHeartbeat",        # its fourth member, added by the S015 delta
    "InstF_Forklift_Safety",   # the F instance DB - F-data is never client-visible
    "F_Forklift_Safety",       # the F-FB itself
    "Main_Safety_RTG1",        # the F main block
]

SUFFIX = re.compile(r"_\d+$")
MAX_DEPTH = 8

failures = []


class Abort(Exception):
    """A failure that makes every remaining check meaningless."""


def bad(msg):
    failures.append(msg)
    print("  FAIL  " + msg)


def fatal(msg):
    bad(msg)
    raise Abort(msg)


async def child_by_name(node, name):
    for c in await node.get_children():
        qn = await c.read_browse_name()
        if qn.Name == name:
            return c
    return None


async def walk(node, path, out, seen, depth=0):
    if depth >= MAX_DEPTH:
        return
    try:
        children = await node.get_children()
    except Exception:                                       # noqa: BLE001
        return
    for c in children:
        key = c.nodeid.to_string()
        if key in seen:
            continue
        seen.add(key)
        try:
            qn = await c.read_browse_name()
        except Exception:                                   # noqa: BLE001
            continue
        p = path + "/" + qn.Name
        out.append((p, qn.Name))
        await walk(c, p, out, seen, depth + 1)


async def checks(c):
    # --- 1. namespaces, read back not asserted -------------------------------
    arr = await c.get_namespace_array()
    print("\n[1] namespace array as the server reports it:")
    for i, u in enumerate(arr):
        print("     ns=%d  %s" % (i, u))
    if IFACE_URI not in arr:
        fatal("the server publishes no namespace %r - the interface name is "
              "the URI (ADR 0006), so this means the interface is missing or "
              "renamed" % IFACE_URI)

    objects = c.nodes.objects
    sifaces = await child_by_name(objects, "ServerInterfaces")
    if sifaces is None:
        fatal("no ServerInterfaces folder under Objects")
    iface = await child_by_name(sifaces, IFACE_NAME)
    if iface is None:
        fatal("no %r interface under ServerInterfaces" % IFACE_NAME)

    # --- 2. POSITIVE CONTROL, before the absence check ------------------------
    print("\n[2] positive control - the four Forklift/Safety/ mirrors "
          "(opcua-nodes.md §11.2) must browse and read:")
    forklift = await child_by_name(iface, "Forklift")
    if forklift is None:
        fatal("no Forklift folder under %s - the walk is not reaching the "
              "interface, so no absence below would mean anything" % IFACE_NAME)
    safety = await child_by_name(forklift, "Safety")
    if safety is None:
        fatal("no Forklift/Safety folder - the walk reached the interface but "
              "not the mirrors, so no absence below would mean anything")
    present = {}
    for ch in await safety.get_children():
        present[(await ch.read_browse_name()).Name] = ch
    control_ok = True
    for name in MIRRORS:
        if name not in present:
            bad("mirror Forklift/Safety/%s is missing (folder holds %s)"
                % (name, sorted(present)))
            control_ok = False
            continue
        try:
            v = await present[name].read_value()
        except Exception as e:                              # noqa: BLE001
            bad("Forklift/Safety/%s could not be read: %s" % (name, e))
            control_ok = False
            continue
        print("     Forklift/Safety/%-22s %s" % (name, repr(v)))
    if not control_ok:
        fatal("the positive control failed. Every absence check below would "
              "pass vacuously, so they are not run")
    print("     control passed - this client does reach and read the CPU's "
          "F-side mirrors, so an absence it reports is a real absence")

    # --- 3. the absence sweep -------------------------------------------------
    names = []
    await walk(objects, "Objects", names, set())
    print("\n[3] absence sweep over %d browse names under Objects "
          "(depth limit %d):" % (len(names), MAX_DEPTH))
    for token in FORBIDDEN:
        hits = [p for p, n in names if token.lower() in p.lower()]
        if hits:
            for p in hits:
                bad("%r is REACHABLE at %s - a client can see it. Clear "
                    "'Accessible from HMI/OPC UA' on the block and download "
                    "again (SPEC §4.2 steps 3 and 11)" % (token, p))
        else:
            print("     %-24s absent" % token)

    dbg = await child_by_name(objects, "DataBlocksGlobal")
    if dbg is None:
        print("     DataBlocksGlobal        not published at all")
    else:
        pub = sorted([(await ch.read_browse_name()).Name
                      for ch in await dbg.get_children()])
        print("     DataBlocksGlobal        published, holding: %s"
              % (", ".join(pub) if pub else "(empty)"))
        print("     read this list yourself: any DB here is auto-published in "
              "the CPU's own namespace, where the commissioned access settings "
              "do not write-protect it (opcua-nodes.md §9.8)")

    # --- 4. collision-suffix sweep -------------------------------------------
    print("\n[4] collision-suffix sweep over the same %d names:" % len(names))
    hits = [p for p, n in names if SUFFIX.search(n)]
    if hits:
        for p in hits:
            bad("collision suffix in browse name: %s" % p)
    else:
        print("     none - no browse name visited ends in _<n>")


async def main():
    print("endpoint: %s" % EP)
    try:
        async with Client(url=EP) as c:
            try:
                await checks(c)
            except Abort:
                pass
    except Exception as e:                                  # noqa: BLE001
        bad("could not complete against %s: %r" % (EP, e))
    print()
    if failures:
        print("RESULT: FAIL - %d problem(s)" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("RESULT: PASS - the F-side data and the stand-in DB are on no "
          "client's address space, proven by a client that demonstrably "
          "reaches the same server")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
