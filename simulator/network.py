"""
Self-contained multi-intersection traffic network simulator.

This replaces a SUMO/traci dependency. SUMO requires a native binary
and a display server, so it cannot run on a normal web host (e.g.
Streamlit Community Cloud). This simulator reproduces the same
signals SUMO would give us (queue length, waiting time, vehicle
count, road capacity) using a stochastic arrival/service model over
a networkx graph, so the whole system is pure Python and deployable
as a web app.

If you DO have SUMO installed locally, `simulator/sumo_adapter.py`
(optional, not required for the web build) can swap this out behind
the same interface -- every consumer of this module only depends on
the TrafficNetwork API below, not on how the numbers were produced.
"""

import random
import networkx as nx

GREEN_OPTIONS = [20, 30, 40]


class TrafficNetwork:
    """
    A grid-like network of N signalized intersections.

    Each intersection tracks:
      - queue          : vehicles currently stopped
      - waiting_time    : accumulated seconds of waiting (proxy for delay)
      - vehicles        : vehicles present near the intersection
      - capacity        : max vehicles the intersection can hold before overflow
      - green_time      : current green-light duration (seconds)
      - blocked         : True if an accident/road closure has hit this node
      - arrival_rate    : average vehicles arriving per step (Poisson lambda)
    """

    def __init__(self, num_intersections=6, seed=None):
        if not (2 <= num_intersections <= 8):
            raise ValueError("Supports 2-8 intersections (problem statement's 4-8 range, widened for demo flexibility)")

        self.rng = random.Random(seed)
        self.num_intersections = num_intersections
        self.graph = self._build_grid(num_intersections)
        self.state = {}
        self.hospital_node = list(self.graph.nodes)[0]  # emergency dispatch origin
        self._init_state()
        self.step_count = 0

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_grid(self, n):
        """Build an approximately-square grid graph with n nodes, all roads bidirectional."""
        cols = 3 if n > 4 else 2
        rows = (n + cols - 1) // cols

        g = nx.grid_2d_graph(rows, cols)
        nodes = list(g.nodes)[:n]
        g = g.subgraph(nodes).copy()

        mapping = {node: f"J{i + 1}" for i, node in enumerate(g.nodes)}
        g = nx.relabel_nodes(g, mapping)

        # store approximate coordinates for the dashboard map
        pos = {}
        for (r, c), name in zip(list(nx.grid_2d_graph(rows, cols).nodes)[:n], mapping.values()):
            pos[name] = (c * 120, -r * 120)
        nx.set_node_attributes(g, pos, "pos")

        # make sure the graph is connected even if grid_2d_graph left a stray node
        if not nx.is_connected(g):
            comps = list(nx.connected_components(g))
            for i in range(1, len(comps)):
                a = next(iter(comps[0]))
                b = next(iter(comps[i]))
                g.add_edge(a, b)

        return g

    def _init_state(self):
        for node in self.graph.nodes:
            self.state[node] = {
                "queue": self.rng.randint(0, 3),
                "waiting_time": float(self.rng.randint(0, 20)),
                "vehicles": self.rng.randint(2, 10),
                "capacity": 40,
                "green_time": 30,
                "blocked": False,
                "arrival_rate": self.rng.uniform(0.6, 2.2),
                "signal_colors": ["RED", "RED", "GREEN", "GREEN"],
            }

    # ------------------------------------------------------------------
    # Simulation step
    # ------------------------------------------------------------------

    def step(self):
        """Advance the simulation by one tick, applying arrivals and service."""
        self.step_count += 1

        for node, data in self.state.items():
            if data["blocked"]:
                # road closure / accident: no service, arrivals still pile up
                arrivals = self._poisson(data["arrival_rate"] * 0.5)
                data["queue"] += arrivals
                data["vehicles"] = min(data["capacity"], data["vehicles"] + arrivals)
                data["waiting_time"] += data["queue"] * 1.5
                continue

            arrivals = self._poisson(data["arrival_rate"])
            served = min(data["queue"] + arrivals, max(1, data["green_time"] // 5))

            data["queue"] = max(0, data["queue"] + arrivals - served)
            data["vehicles"] = min(data["capacity"], max(0, data["vehicles"] + arrivals - served))
            # waiting time grows with queue pressure, eases when queue is served
            data["waiting_time"] = max(0.0, data["waiting_time"] + data["queue"] * 1.2 - served * 0.8)

        return self.get_state()

    def _poisson(self, lam):
        # lightweight poisson sample without requiring numpy in the hot loop
        l = pow(2.718281828, -lam)
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= self.rng.random()
            if p <= l:
                return k - 1

    # ------------------------------------------------------------------
    # Event injection (Dynamic Event Handling requirement)
    # ------------------------------------------------------------------

    def trigger_congestion_spike(self, node=None, magnitude=12):
        node = node or self.rng.choice(list(self.state.keys()))
        self.state[node]["queue"] += magnitude
        self.state[node]["vehicles"] = min(
            self.state[node]["capacity"], self.state[node]["vehicles"] + magnitude
        )
        self.state[node]["waiting_time"] += magnitude * 4
        return node

    def trigger_accident(self, node=None):
        node = node or self.rng.choice(list(self.state.keys()))
        self.state[node]["blocked"] = True
        self.state[node]["capacity"] = max(5, self.state[node]["capacity"] // 4)
        return node

    def trigger_road_closure(self, edge=None):
        edges = list(self.graph.edges)
        edge = edge or self.rng.choice(edges)
        if self.graph.has_edge(*edge):
            self.graph[edge[0]][edge[1]]["closed"] = True
        return edge

    def clear_events(self):
        for data in self.state.values():
            data["blocked"] = False
            data["capacity"] = 40
        for u, v in self.graph.edges:
            self.graph[u][v]["closed"] = False

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def apply_green_times(self, decisions):
        """decisions: {junction: {"green_time": int}}"""
        for junction, decision in decisions.items():
            if junction in self.state:
                self.state[junction]["green_time"] = decision["green_time"]

    def get_state(self):
        return {k: dict(v) for k, v in self.state.items()}

    def get_positions(self):
        return nx.get_node_attributes(self.graph, "pos")

    def get_edges(self, respect_closures=True):
        edges = []
        for u, v, data in self.graph.edges(data=True):
            if respect_closures and data.get("closed"):
                continue
            edges.append((u, v))
        return edges
