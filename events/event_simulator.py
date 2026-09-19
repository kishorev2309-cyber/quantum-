"""
Dynamic event handling.

The problem statement requires the system to respond to at least one
of: sudden congestion, accident, road closure, emergency vehicle
arrival. This wires all four into the network + emergency corridor,
so a judge can trigger any of them live during the demo.
"""

EVENT_TYPES = ["congestion_spike", "accident", "road_closure", "emergency_vehicle"]


def trigger_event(network, emergency_corridor, event_type, **kwargs):
    """Returns (message, highlighted_node_or_None)."""
    if event_type == "congestion_spike":
        node = network.trigger_congestion_spike(node=kwargs.get("node"))
        return f"Sudden congestion spike injected at {node}.", node

    if event_type == "accident":
        node = network.trigger_accident(node=kwargs.get("node"))
        return f"Accident simulated at {node} — capacity reduced, junction blocked.", node

    if event_type == "road_closure":
        edge = network.trigger_road_closure(edge=kwargs.get("edge"))
        return f"Road closure simulated on edge {edge[0]}–{edge[1]}.", edge[0]

    if event_type == "emergency_vehicle":
        path = emergency_corridor.dispatch(
            source=kwargs.get("source"), destination=kwargs.get("destination")
        )
        return f"Emergency vehicle dispatched — corridor: {' → '.join(path)}.", (path[0] if path else None)

    raise ValueError(f"Unknown event type: {event_type}")


def clear_all_events(network, emergency_corridor):
    network.clear_events()
    if emergency_corridor.active:
        emergency_corridor.restore()
