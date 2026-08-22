"""traffic - the floor's ledger. Pure: no MQTT, no ROS, no clock.

RESERVATION IS PROCESS DECONFLICTION, NEVER A COLLISION CLAIM. Nothing
here stops a truck. The scanners, the F-model and the onboard guards are
the only things that do, exactly as before traffic existed. What the
ledger buys is that the fleet never *asks* two vehicles onto one piece
of floor, so the guards are not the plan.

Three rules carry the module:

* **An edge is undirected.** One corridor segment is one piece of floor
  whichever way you drive it, so the element is `frozenset({a, b})` and
  `edge(a, b) == edge(b, a)`. That identity is what catches the head-on
  case: two vehicles routed at each other meet in the ledger long before
  they meet in the aisle.
* **A grant is a contiguous prefix.** `hold` walks the requested route
  from the vehicle's end, stops at the first element someone else owns,
  never grants a hole and never ends on an edge - a truck stops at a
  node. The prefix is the VDA 5050 base; the rest is horizon.
* **Deadlock is broken wait-die, by task age.** A blocked vehicle records
  what it waits for, which makes a wait-for graph (vehicle -> owner of
  the element it wants); a cycle in it is a deadlock. The YOUNGEST task
  in the cycle (largest submit time) releases every hold but the node
  its truck stands on and is marked yielded. It keeps its task and its
  route, holds nothing ahead and retries `hold` every pass - so it
  resumes the moment the corridor drains.
"""


def edge(a, b):
    """The undirected element for the floor between nodes `a` and `b`."""
    return frozenset((a, b))


def route_elements(points):
    """[node0, edge01, node1, edge12, node2, ...] in travel order."""
    out = []
    for i, point in enumerate(points):
        if i:
            out.append(edge(points[i - 1], point))
        out.append(point)
    return out


class Reservations:
    """Who holds which piece of floor, who waits on whom, who yielded."""

    def __init__(self):
        self._owner = {}      # element -> vehicle serial
        self._held = {}       # vehicle -> elements, in travel order
        self._waiting = {}    # vehicle -> the element it is blocked on
        self._standing = {}   # vehicle -> the node under the truck
        self._yielded = set()

    def hold(self, vehicle, elements):
        """Grant the longest contiguous prefix of `elements` that is free
        or already this vehicle's, ending at a node. Record the first
        element another vehicle owns as what this one waits on."""
        prefix, blocker = [], None
        for element in elements:
            owner = self._owner.get(element)
            if owner is not None and owner != vehicle:
                blocker = element
                break
            prefix.append(element)
        while prefix and isinstance(prefix[-1], frozenset):
            prefix.pop()          # a truck stops at a node, not on an edge
        if blocker is None:
            self._waiting.pop(vehicle, None)
        else:
            self._waiting[vehicle] = blocker
        held = self._held.setdefault(vehicle, [])
        for element in prefix:
            if self._owner.get(element) != vehicle:
                self._owner[element] = vehicle
                held.append(element)
        return prefix

    def release_through(self, vehicle, node):
        """Free everything held up to and including the edge arriving at
        `node`; keep `node` and everything after it. A node this vehicle
        never held is a no-op - it is behind us or was never ours."""
        held = self._held.get(vehicle, [])
        if node not in held:
            return
        cut = held.index(node)
        for element in held[:cut]:
            if self._owner.get(element) == vehicle:
                del self._owner[element]
        self._held[vehicle] = held[cut:]

    def release_all(self, vehicle, keep=None):
        """Free everything; `keep` (a node) stays held - the truck is
        standing on it. Clears the wait too: a vehicle holding nothing
        ahead is not an edge in the wait-for graph, and that is exactly
        how yielding breaks a cycle."""
        for element in self._held.get(vehicle, []):
            if self._owner.get(element) == vehicle:
                del self._owner[element]
        self._held[vehicle] = []
        self._waiting.pop(vehicle, None)
        if keep is not None and self._owner.get(keep) is None:
            self._owner[keep] = vehicle
            self._held[vehicle] = [keep]

    def owner_of(self, element):
        return self._owner.get(element)

    def held_by(self, vehicle):
        return list(self._held.get(vehicle, []))

    def waiting_on(self, vehicle):
        return self._waiting.get(vehicle)

    def find_cycle(self):
        """A cycle in the wait-for graph - vehicle -> the owner of what
        it wants - as a list of serials, or None. A cycle is a deadlock:
        every one of them is blocked by the next and nobody can move."""
        graph = {v: self._owner[e] for v, e in self._waiting.items()
                 if self._owner.get(e) not in (None, v)}
        for start in sorted(graph):
            seen, node = [], start
            while node in graph and node not in seen:
                seen.append(node)
                node = graph[node]
            if node in seen:
                return seen[seen.index(node):]
        return None

    def resolve_deadlock(self, ages):
        """Wait-die: on a cycle the youngest task (largest submit time)
        gives up everything but the ground under its truck. Returns the
        serial that yielded, or None when there is no cycle."""
        cycle = self.find_cycle()
        if not cycle:
            return None
        loser = max(cycle, key=lambda v: (ages.get(v, float("inf")), v))
        self.release_all(loser, keep=self._standing.get(loser))
        self._yielded.add(loser)
        return loser

    def set_standing(self, vehicle, node):
        self._standing[vehicle] = node

    def yielded(self, vehicle):
        return vehicle in self._yielded

    def clear_yield(self, vehicle):
        self._yielded.discard(vehicle)
