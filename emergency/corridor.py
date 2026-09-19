"""
Emergency Green Corridor System.

The problem statement calls this out as a major, named feature:
"reduces ambulance or emergency vehicle travel time while minimizing
disruption to normal traffic" -- and it did not exist anywhere in
the original codebase.

Approach:
  1. An emergency vehicle is dispatched from a source junction to a
     destination (e.g. hospital) junction.
  2. Shortest path is computed over the live road graph (accounting
     for any closed edges from `trigger_road_closure`).
  3. Every junction on that path is force-set to the maximum green
     time (40s) for the duration of the event -- this list is also
     fed into `build_qubo(..., emergency_nodes=...)` so the quantum
     optimizer *prefers* long green on that corridor even before the
     override, minimizing the "disruption to normal traffic" the
     override alone would cause elsewhere.
  4. `restore()` reverts overridden junctions to the optimizer's
     normal decision once the emergency clears.
"""

import networkx as nx

MAX_GREEN = 40


class EmergencyCorridor:
    def __init__(self, network):
        self.network = network
        self.active = False
        self.path = []
        self.source = None
        self.destination = None
        self._pre_override_green = {}

    def dispatch(self, source=None, destination=None):
        nodes = list(self.network.graph.nodes)
        self.source = source or nodes[0]
        self.destination = destination or self.network.hospital_node

        try:
            self.path = nx.shortest_path(
                self.network.graph, self.source, self.destination
            )
        except nx.NetworkXNoPath:
            self.path = [self.source]

        self.active = True
        self._apply_override()
        return self.path

    def _apply_override(self):
        self._pre_override_green = {}
        for junction in self.path:
            if junction in self.network.state:
                self._pre_override_green[junction] = self.network.state[junction]["green_time"]
                self.network.state[junction]["green_time"] = MAX_GREEN

    def restore(self):
        for junction, green_time in self._pre_override_green.items():
            if junction in self.network.state:
                self.network.state[junction]["green_time"] = green_time
        self.active = False
        self.path = []
        self._pre_override_green = {}

    def corridor_nodes(self):
        return set(self.path) if self.active else set()

    def estimated_time_saved_seconds(self):
        """
        Rough estimate: each corridor junction forced to max green vs.
        its pre-override timing saves the delta in expected wait per
        vehicle at that junction (used for the dashboard headline stat).
        """
        saved = 0
        for junction, previous in self._pre_override_green.items():
            saved += max(0, MAX_GREEN - previous) * 0.5
        return saved
