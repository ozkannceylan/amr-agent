"""Verify the §12 / §14.2 node set on the CPU's own OPC UA server, from outside TIA.

Runs the checks `docs/interfaces/opcua-nodes.md` §12.11 step 6 and
`plc/forklift/SPEC.md` §14.13 step 8 ask for, so that no value has to be read
aloud off a screen and transcribed:

  1. resolves the namespace indices by URI and hardcodes neither
     (`plc/forklift/SPEC.md` §4.3),
  2. reads the server interface's namespace URI back rather than asserting it
     (ADR 0006 - the interface name IS the URI, and it is a derived value),
  3. walks the whole `DemoCell` interface and flags every BrowseName ending in
     a TIA collision suffix (`_1`, `_2`, ...). TIA appends them without asking,
     in DB statics and interface rows both, and a suffixed browse name cuts a
     client with no error dialog (LESSONS 2026-07-30),
  4. checks the four new folders and the nine BrowseNames of §12.3-§12.7,
     character for character, and reads each value with its data type,
  5. attempts ONE write to a `Forklift/Envelope/` node and records the refusal
     with its status code. A read proves the nodes exist; only the refused
     write proves "a permission is not a command" is enforced by the server
     rather than by convention.

The write probe writes back the value the node ALREADY holds, so a server that
wrongly accepts it changes nothing; the program re-publishes the node every OB
call in any case.

Usage:  python m5-25-node-verify.py [endpoint]
        default endpoint opc.tcp://192.168.53.1:4840 (opcua-nodes.md §9.10)

Requires asyncua. Exit code 0 = every check passed, 1 = something failed.
"""
import asyncio
import re
import sys

from asyncua import Client, ua

EP = sys.argv[1] if len(sys.argv) > 1 else "opc.tcp://192.168.53.1:4840"

IFACE_URI = "http://DemoCell"          # derived by TIA from the interface name
SIEMENS_URI = "http://www.siemens.com/simatic-s7-opcua"
IFACE_NAME = "DemoCell"

# opcua-nodes.md §12.3-§12.7 / plc/forklift/SPEC.md §14.2, quoted.
EXPECTED = {
    "Mode": ["HmiDriveModeRequest", "ForkliftDriveModeActive"],
    "Envelope": ["ForkliftMotionEnable", "ForkliftSpeedCeiling",
                 "ForkliftEquipmentPermit"],
    "Vehicle": ["ForkliftVehicleModeApplied", "ForkliftVehicleHeartbeat"],
    "ProcessStop": ["HmiProcessStopRequest", "ForkliftProcessStopActive"],
}
# Start values, §14.2. Printed beside the reading; NOT asserted, because a
# running program legitimately moves them - the cold-start check is a separate
# step of the procedure, taken at a fresh CPU start.
START = {
    "HmiDriveModeRequest": "0", "ForkliftDriveModeActive": "0",
    "ForkliftMotionEnable": "False", "ForkliftSpeedCeiling": "0.0",
    "ForkliftEquipmentPermit": "False",
    "ForkliftVehicleModeApplied": "0", "ForkliftVehicleHeartbeat": "0",
    "HmiProcessStopRequest": "True", "ForkliftProcessStopActive": "True",
}
WRITE_PROBE = ("Envelope", "ForkliftMotionEnable")
SUFFIX = re.compile(r"_\d+$")

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


async def walk(node, path, names):
    for c in await node.get_children():
        qn = await c.read_browse_name()
        names.append((path + "/" + qn.Name, qn.Name))
        await walk(c, path + "/" + qn.Name, names)


async def checks(c):
    # --- 1. namespaces, resolved by URI, read back not asserted -------------
    arr = await c.get_namespace_array()
    print("\n[1] namespace array as the server reports it:")
    for i, u in enumerate(arr):
        print("     ns=%d  %s" % (i, u))
    if IFACE_URI not in arr:
        fatal("the server publishes no namespace %r - the interface name is "
              "the URI (ADR 0006), so this means the interface is missing or "
              "renamed" % IFACE_URI)
    print("  read back: the server interface namespace URI is %r" % IFACE_URI)
    if SIEMENS_URI not in arr:
        print("  note: %s is not in the namespace array; ServerInterfaces is "
              "resolved by browse name only" % SIEMENS_URI)

    objects = c.nodes.objects
    sifaces = await child_by_name(objects, "ServerInterfaces")
    if sifaces is None:
        fatal("no ServerInterfaces folder under Objects")
    iface = await child_by_name(sifaces, IFACE_NAME)
    if iface is None:
        fatal("no %r interface under ServerInterfaces" % IFACE_NAME)

    # --- 2. the _1 collision sweep, over the whole interface -----------------
    names = []
    await walk(iface, IFACE_NAME, names)
    print("\n[2] collision-suffix sweep over %d browse names under %s:"
          % (len(names), IFACE_NAME))
    hits = [p for p, n in names if SUFFIX.search(n)]
    if hits:
        for p in hits:
            bad("collision suffix in browse name: %s" % p)
    else:
        print("     none - no browse name under the interface ends in _<n>")

    # --- 3. the ten subfolders under Forklift -------------------------------
    forklift = await child_by_name(iface, "Forklift")
    if forklift is None:
        fatal("no Forklift folder under %s" % IFACE_NAME)
    subs = []
    for ch in await forklift.get_children():
        subs.append((await ch.read_browse_name()).Name)
    print("\n[3] subfolders under Forklift (%d): %s"
          % (len(subs), ", ".join(sorted(subs))))
    for f in EXPECTED:
        if f not in subs:
            bad("folder Forklift/%s is missing" % f)

    # --- 4. the nine nodes, their types and their values ---------------------
    print("\n[4] the nine §12 nodes:")
    print("     %-46s %-10s %-12s %s"
          % ("browse path", "type", "value", "start value (§14.2)"))
    for folder, leaves in EXPECTED.items():
        fnode = await child_by_name(forklift, folder)
        if fnode is None:
            continue
        present = {}
        for ch in await fnode.get_children():
            present[(await ch.read_browse_name()).Name] = ch
        for leaf in leaves:
            path = "Forklift/%s/%s" % (folder, leaf)
            if leaf not in present:
                bad("%s is missing (check for a renamed or suffixed leaf: the "
                    "folder holds %s)" % (path, sorted(present)))
                continue
            n = present[leaf]
            try:
                v = await n.read_value()
                dt = (await n.read_data_type_as_variant_type()).name
            except Exception as e:                          # noqa: BLE001
                bad("%s could not be read: %s" % (path, e))
                continue
            print("     %-46s %-10s %-12s %s"
                  % (path, dt, repr(v), START.get(leaf, "")))
        for extra in sorted(set(present) - set(leaves)):
            bad("Forklift/%s holds an unexpected node %r - §12.4 admits no "
                "fourth node in Envelope/ and §12 mints no other leaf"
                % (folder, extra))

    # --- 5. the refused write ------------------------------------------------
    folder, leaf = WRITE_PROBE
    fnode = await child_by_name(forklift, folder)
    target = await child_by_name(fnode, leaf) if fnode else None
    print("\n[5] write probe on Forklift/%s/%s (writes back the value it "
          "already holds):" % (folder, leaf))
    if target is None:
        bad("write probe target Forklift/%s/%s not found" % (folder, leaf))
        return
    held = await target.read_value()
    try:
        await target.write_value(
            ua.DataValue(ua.Variant(held, ua.VariantType.Boolean)))
    except ua.UaStatusCodeError as e:
        print("     REFUSED: %s" % e)
        print("     record this status code and today's date - it is what "
              "proves 'a permission is not a command' is enforced by the "
              "server (opcua-nodes.md §12.11 step 6)")
    except Exception as e:                                  # noqa: BLE001
        bad("write probe raised something other than a status code: %r" % e)
    else:
        bad("the write was ACCEPTED. Forklift/Envelope/* must be Writable from "
            "HMI/OPC UA = FALSE on all three tags (opcua-nodes.md §12.2, "
            "SPEC §14.2). Fix the DB attribute and download again")


async def main():
    print("# m5-25 node verification")
    print("# endpoint:", EP)
    try:
        async with Client(url=EP, timeout=15) as c:
            await checks(c)
    except Abort:
        pass
    except Exception as e:                                  # noqa: BLE001
        bad("could not complete: %r" % e)
    print("\n" + ("RESULT: PASS - every check above passed" if not failures
                  else "RESULT: FAIL - %d problem(s):" % len(failures)))
    for f in failures:
        print("  - " + f)
    return 1 if failures else 0


sys.exit(asyncio.run(main()))
