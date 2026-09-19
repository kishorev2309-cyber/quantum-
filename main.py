"""
CLI demo: runs N iterations of the full hybrid pipeline and prints a
readable trace. Useful for a 30-second terminal walkthrough before
switching to the web dashboard (`streamlit run app.py`) during judging.
"""

import sys

from simulator.network import TrafficNetwork
from emergency.corridor import EmergencyCorridor
from events.event_simulator import trigger_event
from core.engine import run_iteration, apply_quantum_result

ITERATIONS = 6
NUM_INTERSECTIONS = 6


def main():
    print("=" * 72)
    print("  QUANTUM-ENHANCED ADAPTIVE URBAN TRAFFIC OPTIMIZATION")
    print("=" * 72)

    network = TrafficNetwork(num_intersections=NUM_INTERSECTIONS, seed=42)
    corridor = EmergencyCorridor(network)

    for i in range(1, ITERATIONS + 1):
        print(f"\n--- Iteration {i} " + "-" * 50)
        network.step()

        if i == 3:
            msg, _ = trigger_event(network, corridor, "congestion_spike")
            print(f"[EVENT] {msg}")

        if i == 4:
            msg, _ = trigger_event(network, corridor, "emergency_vehicle")
            print(f"[EVENT] {msg}")

        result = run_iteration(network, emergency_corridor=corridor, k=4)
        apply_quantum_result(network, result)

        if i == 5 and corridor.active:
            corridor.restore()
            print("[EVENT] Emergency corridor cleared, signals restored.")

        print(f"Selected junctions for quantum optimization: {result['selected_junctions']}")
        print(f"Quantum (QAOA) decisions: {result['quantum_decisions']}")
        print(f"Classical decisions:      {result['classical_decisions']}")
        em = result["emissions"]
        print(
            f"Waiting-time improvement: {em['waiting_improvement_pct']}%  |  "
            f"Fuel saved: {em['fuel_improvement_pct']}%  |  "
            f"CO2 reduced: {em['co2_improvement_pct']}%"
        )

    print("\n" + "=" * 72)
    print("  Demo complete. Run `streamlit run app.py` for the full dashboard.")
    print("=" * 72)


if __name__ == "__main__":
    sys.exit(main() or 0)
