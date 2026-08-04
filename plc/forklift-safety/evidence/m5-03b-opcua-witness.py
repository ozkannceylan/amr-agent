"""Independent witness for the stand-in stimulus proof.

Polls ForkliftSafetyMirror over OPC UA - the CPU's own server, a different
protocol and a different stack from the PLCSIM Advanced API that does the
writing. SafetyInputStandIn is NOT exposed on this server, so nothing this
process sees can be an echo of the writer's process image.
"""
import asyncio, time, sys
from asyncua import Client

EP = "opc.tcp://192.168.53.1:4840"
NODES = {
    "EStopDemand": 'ns=3;s="ForkliftSafetyMirror"."EStopDemand"',
    "ZoneStopDemand": 'ns=3;s="ForkliftSafetyMirror"."ZoneStopDemand"',
    "SafetyResetRequired": 'ns=3;s="ForkliftSafetyMirror"."SafetyResetRequired"',
    "SafetyResetFault": 'ns=3;s="ForkliftSafetyMirror"."SafetyResetFault"',
    "ForkliftResetRequired": 'ns=3;s="ForkliftStatus"."ForkliftResetRequired"',
}
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 50.0


def stamp(t):
    lt = time.localtime(t)
    return time.strftime("%H:%M:%S", lt) + ".%03d" % int((t % 1) * 1000)


async def main():
    async with Client(url=EP, timeout=10) as c:
        nodes = {k: c.get_node(v) for k, v in NODES.items()}
        order = list(NODES)
        print("# OPC UA witness on", EP)
        print("# columns:", ", ".join(order))
        prev = None
        t_end = time.time() + DURATION
        n = 0
        while time.time() < t_end:
            vals = await c.read_values([nodes[k] for k in order])
            n += 1
            cur = tuple(bool(v) for v in vals)
            if cur != prev:
                bits = "".join("1" if b else "0" for b in cur)
                tag = "baseline" if prev is None else "CHANGE"
                print(f"{stamp(time.time())}  {bits}  {tag}", flush=True)
                prev = cur
        print(f"# {n} polls over {DURATION:.0f} s, final {''.join('1' if b else '0' for b in prev)}")


asyncio.run(main())
