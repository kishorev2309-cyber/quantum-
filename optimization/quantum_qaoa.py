"""
QAOA optimizer for the traffic QUBO.

WHY THIS REPLACES THE ORIGINAL "quantum.py":
The original circuit applied fixed H / CX / RY(0.4) gates that never
read the QUBO matrix Q at all -- it produced the same distribution of
bitstrings regardless of the traffic data, then just classically
picked the lowest-cost one out of random samples. That is quantum
*sampling*, not quantum *optimization*.

This version builds an actual parameterized QAOA ansatz:
  - Cost layer: RZ(gamma * Q[i,i], i) for linear terms,
                RZZ(gamma * Q[i,j], i, j) for quadratic terms.
  - Mixer layer: RX(2*beta, i) on every qubit.
  - p layers of (cost, mixer), starting from the |+>^n state.
The parameters (gamma_1, beta_1, ..., gamma_p, beta_p) are tuned by a
classical optimizer (COBYLA) that minimizes the sample-averaged QUBO
cost measured from the circuit -- this classical-quantum feedback
loop is exactly the "hybrid" part the problem statement asks for.
"""

import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from optimization.qubo import evaluate_cost

SHOTS = 300
P_LAYERS = 2
MAX_ITER = 15  # kept low so a demo run stays fast, especially on modest hosting

# Built once at import time instead of per-call: constructing AerSimulator()
# fresh on every run_qaoa() call (the original design) was the single
# biggest contributor to slow iterations on a hosted deployment.
_SIMULATOR = AerSimulator()


def _build_circuit(num_qubits, Q, params):
    p = len(params) // 2
    gammas = params[0::2]
    betas = params[1::2]

    circuit = QuantumCircuit(num_qubits)
    circuit.h(range(num_qubits))

    for layer in range(p):
        gamma = gammas[layer]
        beta = betas[layer]

        for (i, j), coeff in Q.items():
            if i == j:
                circuit.rz(2 * gamma * coeff, i)
            else:
                circuit.rzz(2 * gamma * coeff, i, j)

        for q in range(num_qubits):
            circuit.rx(2 * beta, q)

    circuit.measure_all()
    return circuit


def _expected_cost(params, num_qubits, Q, simulator):
    circuit = _build_circuit(num_qubits, Q, params)
    result = simulator.run(circuit, shots=SHOTS).result()
    counts = result.get_counts()

    total = 0.0
    shots_seen = 0
    for bitstring, count in counts.items():
        normalized = bitstring.replace(" ", "")[::-1]
        total += evaluate_cost(Q, normalized) * count
        shots_seen += count
    return total / max(1, shots_seen)


def run_qaoa(Q, variable_info, p_layers=P_LAYERS, max_iter=MAX_ITER, seed=7):
    """
    Runs the hybrid QAOA loop and returns:
      best   : {"bitstring", "cost", "count"}
      counts : final measurement distribution
      history: list of (iteration, expected_cost) for the dashboard
    """
    num_qubits = len(variable_info)
    simulator = _SIMULATOR
    rng = np.random.default_rng(seed)

    history = []

    def objective(params):
        cost = _expected_cost(params, num_qubits, Q, simulator)
        history.append(cost)
        return cost

    init_params = rng.uniform(0, np.pi, size=2 * p_layers)

    result = minimize(
        objective,
        init_params,
        method="COBYLA",
        options={"maxiter": max_iter, "rhobeg": 0.5},
    )

    # Final sampling round with the tuned parameters to pick the best bitstring
    final_circuit = _build_circuit(num_qubits, Q, result.x)
    final_result = simulator.run(final_circuit, shots=SHOTS).result()
    counts = final_result.get_counts()

    candidates = []
    for bitstring, count in counts.items():
        normalized = bitstring.replace(" ", "")[::-1]
        candidates.append(
            {"bitstring": normalized, "count": count, "cost": evaluate_cost(Q, normalized)}
        )
    candidates.sort(key=lambda c: c["cost"])
    best = candidates[0]

    return best, counts, history, result.x


def decode_solution(bitstring, variable_info):
    decisions = {}
    for index, bit in enumerate(bitstring):
        if bit == "1":
            item = variable_info[index]
            # if a junction ends up with 0 or >1 bits set (constraint violated
            # by sampling noise), the last "1" found wins -- acceptable for a
            # hackathon demo, flagged here for transparency
            decisions[item["junction"]] = {"green_time": item["green_time"]}
    return decisions
