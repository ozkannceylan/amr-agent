"""Steps 58-59 of plc/forklift/TIA-FIX-PROCEDURE.md, from outside TIA.

Reads the two new Forklift/Safety/ leaves and attempts ONE write to
SpeedMonitorDemand. The write probe writes back the value the node already
holds, so a server that wrongly accepts it changes nothing.
"""
import asyncio
import sys

from asyncua import Client, ua

EP = sys.argv[1] if len(sys.argv) > 1 else "opc.tcp://192.168.53.1:4840"
IFACE_NAME = "DemoCell"
LEAVES = ["SpeedMonitorDemand", "TorqueOffDemand"]


async def child_by_name(node, name):
    for c in await node.get_children():
        qn = await c.read_browse_name()
        if qn.Name == name:
            return c
    return None


async def main():
    print("# m5-59 Forklift/Safety leaf probe")
    print("# endpoint: %s" % EP)
    async with Client(url=EP) as c:
        objects = c.nodes.objects
        sifaces = await child_by_name(objects, "ServerInterfaces")
        iface = await child_by_name(sifaces, IFACE_NAME)
        forklift = await child_by_name(iface, "Forklift")
        safety = await child_by_name(forklift, "Safety")

        print("\n[58] read the two new leaves:")
        nodes = {}
        for name in LEAVES:
            n = await child_by_name(safety, name)
            if n is None:
                print("     FAIL  no leaf named %r under Forklift/Safety" % name)
                continue
            nodes[name] = n
            v = await n.read_value()
            dv = await n.read_data_type_as_variant_type()
            al = await n.read_attribute(ua.AttributeIds.AccessLevel)
            print("     Forklift/Safety/%-20s %-8s %-6s access=%s"
                  % (name, dv.name, v, ua.AccessLevel.parse_bitfield(
                      al.Value.Value)))

        print("\n[59] write probe on Forklift/Safety/SpeedMonitorDemand "
              "(writes back the value it already holds):")
        n = nodes.get("SpeedMonitorDemand")
        held = await n.read_value()
        try:
            await n.write_value(ua.DataValue(ua.Variant(held, ua.VariantType.Boolean)))
            print("     ACCEPTED - the server allowed a client write to a "
                  "Forklift/Safety/ mirror. THIS IS A FAILURE.")
        except ua.UaStatusCodeError as e:
            print("     REFUSED: %s" % e)


asyncio.run(main())
