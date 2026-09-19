"""
QUBO formulation for multi-intersection green-time selection.

Fixes vs. the original prototype:
  * Generalized to any number of intersections (was hardcoded to 2).
  * Adds an `emergency_boost` term so a QUBO-selected corridor
    intersection is pushed towards the longest green time without
    a manual override needing to bypass the optimizer.
  * K controls how many of the most-congested intersections get a
    quantum variable each (each needs 3 qubits, one per timing
    option) -- this is a deliberate classical pre-filter so the
    quantum circuit stays small enough to simulate quickly, while
    every intersection still gets served (the rest fall back to the
    classical rule in `optimization/classical_baseline.py`).
"""

GREEN_OPTIONS = [20, 30, 40]


def build_qubo(intersection_data, k=4, emergency_nodes=None):
    """
    Returns (Q, selected_junctions, variable_info).

    Q: dict[(i, j)] -> coefficient
    selected_junctions: the up-to-k junctions represented as qubits
    variable_info: list of {"index", "junction", "green_time"}
    """
    emergency_nodes = emergency_nodes or set()

    ranked = sorted(
        intersection_data,
        key=lambda j: (
            j in emergency_nodes,
            intersection_data[j]["queue"] * 10 + intersection_data[j]["waiting_time"],
        ),
        reverse=True,
    )
    selected = ranked[: min(k, len(ranked))]

    if not selected:
        return {}, [], []

    variable_info = []
    variable_index = 0
    for junction in selected:
        for green_time in GREEN_OPTIONS:
            variable_info.append(
                {"index": variable_index, "junction": junction, "green_time": green_time}
            )
            variable_index += 1

    Q = {}

    def add_term(i, j, value):
        key = (min(i, j), max(i, j))
        Q[key] = Q.get(key, 0) + value

    ONE_CHOICE_PENALTY = 100
    CYCLE_PENALTY = 2
    CYCLE_BUDGET = 30 * len(selected)  # aim for ~30s average across selected junctions
    EMERGENCY_WEIGHT = 60  # extra pull towards long green for corridor junctions

    # 1. Congestion objective: longer green = lower cost, scaled by
    #    how congested / capacity-constrained the junction is.
    for item in variable_info:
        junction = item["junction"]
        green_time = item["green_time"]
        data = intersection_data[junction]

        congestion = data["queue"] * 10 + data["waiting_time"]
        capacity_pressure = data.get("vehicles", 0) / max(1, data.get("capacity", 40))
        congestion *= 1 + capacity_pressure

        reduction = (green_time - 20) / 20  # 0, 0.5, 1.0 for 20/30/40s
        cost = congestion * (1 - reduction)

        if junction in emergency_nodes:
            # reward long green heavily for emergency-corridor junctions
            cost -= EMERGENCY_WEIGHT * reduction

        add_term(item["index"], item["index"], cost)

    # 2. Exactly-one-timing-per-junction constraint: (sum x_i - 1)^2 expanded
    for junction in selected:
        indices = [item["index"] for item in variable_info if item["junction"] == junction]
        for i in indices:
            add_term(i, i, -ONE_CHOICE_PENALTY)
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                add_term(indices[a], indices[b], 2 * ONE_CHOICE_PENALTY)

    # 3. Shared-cycle constraint: keep total green time near budget, expand (sum g_i x_i - budget)^2
    green_values = {item["index"]: item["green_time"] for item in variable_info}
    for i, g in green_values.items():
        coefficient = CYCLE_PENALTY * (g * g - 2 * CYCLE_BUDGET * g)
        add_term(i, i, coefficient)

    indices = list(green_values.keys())
    for a in range(len(indices)):
        for b in range(a + 1, len(indices)):
            i, j = indices[a], indices[b]
            coefficient = CYCLE_PENALTY * 2 * green_values[i] * green_values[j]
            add_term(i, j, coefficient)

    return Q, selected, variable_info


def evaluate_cost(Q, bitstring):
    bits = [int(b) for b in bitstring]
    cost = 0.0
    for (i, j), coefficient in Q.items():
        cost += coefficient * bits[i] * bits[j]
    return cost
