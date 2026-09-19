"""
Orchestration layer: runs one iteration of the full pipeline described
in the problem statement's architecture:

  Traffic -> QUBO -> Quantum Circuit -> Signal Decision -> Network
                                    (in parallel) -> Classical baseline, for comparison

Each iteration produces BOTH a classical and a quantum decision from
the *same* traffic snapshot, applies each to its own copy of the
network state, and reports metrics for both -- this is what makes the
"Classical Comparison" requirement real instead of two disconnected
scripts.
"""

import copy

from optimization.qubo import build_qubo
from optimization.quantum_qaoa import run_qaoa, decode_solution
from optimization.classical_baseline import optimize_all as classical_optimize
from environment.emissions import compare as compare_emissions


def run_iteration(network, emergency_corridor=None, k=4):
    """
    network: simulator.network.TrafficNetwork (already stepped)
    emergency_corridor: emergency.corridor.EmergencyCorridor or None
    Returns a dict with everything the dashboard needs for this iteration.
    """
    snapshot = network.get_state()

    emergency_nodes = emergency_corridor.corridor_nodes() if emergency_corridor else set()

    # --- Classical baseline (applied to an isolated copy of the state) ---
    classical_decisions = classical_optimize(snapshot)
    classical_state = copy.deepcopy(snapshot)
    for junction, decision in classical_decisions.items():
        classical_state[junction]["green_time"] = decision["green_time"]

    # --- Quantum / QAOA path ---
    Q, selected, variable_info = build_qubo(snapshot, k=k, emergency_nodes=emergency_nodes)

    quantum_state = copy.deepcopy(snapshot)
    quantum_decisions = {}
    qaoa_history = []

    if Q:
        best, counts, qaoa_history, tuned_params = run_qaoa(Q, variable_info)
        quantum_decisions = decode_solution(best["bitstring"], variable_info)
        for junction, decision in quantum_decisions.items():
            quantum_state[junction]["green_time"] = decision["green_time"]
        # junctions not selected by the quantum pre-filter still get the
        # classical rule applied, so every intersection has a timing
        for junction in quantum_state:
            if junction not in quantum_decisions:
                quantum_state[junction]["green_time"] = classical_decisions[junction]["green_time"]
    else:
        quantum_state = classical_state
        best = None

    # emergency override always wins on corridor junctions
    if emergency_corridor and emergency_corridor.active:
        for junction in emergency_corridor.path:
            if junction in quantum_state:
                quantum_state[junction]["green_time"] = 40

    emissions = compare_emissions(classical_state, quantum_state)

    return {
        "snapshot": snapshot,
        "selected_junctions": selected,
        "classical_decisions": classical_decisions,
        "classical_state": classical_state,
        "quantum_decisions": quantum_decisions,
        "quantum_state": quantum_state,
        "quantum_best": best,
        "qaoa_history": qaoa_history,
        "emissions": emissions,
    }


def apply_quantum_result(network, iteration_result):
    """Push the quantum path's chosen green times back into the live network."""
    for junction, data in iteration_result["quantum_state"].items():
        if junction in network.state:
            network.state[junction]["green_time"] = data["green_time"]
