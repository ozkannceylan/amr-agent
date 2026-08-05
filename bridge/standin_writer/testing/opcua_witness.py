"""TEST SCAFFOLDING -- the independent witness for the stand-in writer's run.

WHY IT EXISTS. An API write is verified in the consumer's view, never in the
writer's own read-back (docs/LESSONS.md 2026-08-04). This process reaches the
CPU over a DIFFERENT protocol stack from the one the writer uses: OPC UA to
the CPU's own server, against the PLCSIM Advanced API that does the writing.

WHAT IT CAN AND CANNOT SEE. `SafetyInputStandIn` and `InstF_Forklift_Safety`
are absent from this server's address space -- proven by
plc/forklift-safety/evidence/m5-25b-f-absence-2026-08-05.log. So this witness
cannot echo anything the writer wrote, and it cannot see `StandInValid` or
`HeartbeatSeen` either. What it sees is the CONSEQUENCE: the four
`ForkliftSafetyMirror` values the standard program copies out of the F-block.

ADDRESSING. `Forklift/Safety/<name>` under the `DemoCell` server interface,
browsed from `ServerInterfaces` -- opcua-nodes.md §11.2. This is deliberately
NOT the `ns=3;s="ForkliftSafetyMirror"."<member>"` form the m5-03b witness
used: that form is the CPU's own auto-published namespace, whose
`DataBlocksGlobal` folder this server no longer publishes at all.

IT WRITES NOTHING.

Usage:  python opcua_witness.py <seconds> [endpoint]
"""
import asyncio
import sys
import time

from asyncua import Client

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
EP = sys.argv[2] if len(sys.argv) > 2 else "opc.tcp://192.168.53.1:4840"

IFACE = "DemoCell"
MIRRORS = ["EStopDemand", "ZoneStopDemand", "SafetyResetRequired",
           "SafetyResetFault"]


def stamp(t):
    return time.strftime("%H:%M:%S", time.localtime(t)) + ".%03d" % int((t % 1) * 1000)


async def child(node, name):
    for c in await node.get_children():
        if (await c.read_browse_name()).Name == name:
            return c
    return None


async def main():
    async with Client(url=EP, timeout=10) as c:
        node = c.nodes.objects
        for name in ("ServerInterfaces", IFACE, "Forklift", "Safety"):
            node = await child(node, name)
            if node is None:
                print("# FAILED to browse to %s" % name)
                return 1
        present = {}
        for ch in await node.get_children():
            present[(await ch.read_browse_name()).Name] = ch
        missing = [m for m in MIRRORS if m not in present]
        if missing:
            print("# FAILED: mirrors missing: %s" % missing)
            return 1
        nodes = [present[m] for m in MIRRORS]
        print("# OPC UA witness on %s" % EP)
        print("# path: Objects/ServerInterfaces/%s/Forklift/Safety/" % IFACE)
        print("# columns: %s" % ", ".join(MIRRORS))
        prev = None
        n = 0
        t_end = time.time() + DURATION
        while time.time() < t_end:
            vals = await c.read_values(nodes)
            n += 1
            cur = tuple(bool(v) for v in vals)
            if cur != prev:
                bits = "".join("1" if b else "0" for b in cur)
                print("%s  %s  %s" % (stamp(time.time()), bits,
                                      "baseline" if prev is None else "CHANGE"),
                      flush=True)
                prev = cur
        print("# %d polls over %.0f s, final %s"
              % (n, DURATION, "".join("1" if b else "0" for b in prev)))
    return 0


sys.exit(asyncio.run(main()))
