# 🚦 Quantum-Enhanced Adaptive Urban Traffic Optimization

A hybrid **QUBO + QAOA** signal-timing optimizer for multi-intersection traffic networks,
with an **Emergency Green Corridor**, live **classical-vs-quantum comparison**, and
**fuel/CO₂ impact estimation** — built as a fully self-contained, deployable web dashboard.

Built for [Hackhere] hackathon submission (see `Quantum-Enhanced Adaptive Urban Traffic
Optimization` problem statement).

---

## Why it's a web app, not a localhost demo

The original prototype depended on the SUMO traffic simulator via `traci`, which needs a
native binary and a display server — that cannot run on a normal web host. This version
replaces it with `simulator/network.py`, a pure-Python stochastic traffic simulator with the
same interface, so the whole system is deployable straight from this repo to
**[Streamlit Community Cloud](https://share.streamlit.io)** for free, with zero server
management:

1. Push this repo to GitHub.
2. On Streamlit Community Cloud: **New app** → select this repo → main file `app.py` → Deploy.
3. Share the resulting `https://<yourapp>.streamlit.app` link with the judges.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py        # full interactive dashboard
python main.py               # quick CLI trace for a 30s terminal walkthrough
```

---

## Problem statement → implementation map

| Requirement | Where it's implemented |
|---|---|
| Multi-intersection network (4–8) | `simulator/network.py` — `TrafficNetwork` |
| QUBO/Ising + QAOA optimization | `optimization/qubo.py` + `optimization/quantum_qaoa.py` |
| Adaptive signals | `core/engine.py` applies the optimizer's decision back to the network every iteration |
| Emergency Green Corridor | `emergency/corridor.py` — shortest-path dispatch + forced green override + restore |
| Dynamic event handling | `events/event_simulator.py` — congestion spike, accident, road closure, emergency vehicle |
| Environmental analysis (fuel/CO₂) | `environment/emissions.py` |
| Classical comparison | `optimization/classical_baseline.py`, run in parallel every iteration in `core/engine.py` |
| Interactive dashboard | `app.py` — network map, live controls, quantum internals, emissions trend, judges explainer |

## What makes the quantum part real

Each QAOA circuit gate angle is derived directly from the QUBO's own coefficients
(`RZ`/`RZZ` scaled by `γ`), and `γ`/`β` are tuned across several rounds by a classical
optimizer (`scipy.optimize.minimize`, COBYLA) that minimizes the *sampled* QUBO cost from
the circuit. That classical ↔ quantum feedback loop — visible live in the dashboard's
"Quantum Optimization" tab — is what makes this a hybrid optimizer, not a fixed circuit
picking the best of random noise.

**Scale note (say this to judges proactively, don't wait to be asked):** with up to 8 real
intersections but only a handful of qubits practical to simulate quickly on a classical Aer
backend during a live demo, the system classically pre-ranks the most congested/priority
junctions and gives *those* qubits (3 per junction — one-hot over the three timing options).
Every other junction still gets a timing decision from the classical rule, so nothing goes
unserved. This is a standard near-term hybrid pattern (problem decomposition), documented
here rather than hidden.

## Who this is for

Municipal traffic-control teams and smart-city planners evaluating adaptive signal control
before a hardware rollout, and emergency-dispatch coordinators who need a demonstrably
faster ambulance route without fully deregulating the rest of the network.

## What's unique vs. a purely classical adaptive system

The QUBO formulation jointly optimizes several interacting constraints at once — per-junction
timing choice, a shared-cycle time budget across the corridor, and emergency priority — in a
single objective, rather than stacking independent per-junction if/else rules. That kind of
joint combinatorial optimization is exactly what QAOA is suited to explore.

## Honest limitation, shown not hidden

During an active emergency-vehicle event, the dashboard's environmental-impact trend can
show a temporary *negative* improvement vs. the classical baseline. That's expected: the
Emergency Corridor forces max green on the ambulance route, trading some network-wide
efficiency for emergency response time. The system surfaces that trade-off instead of
smoothing it over.

## Repository structure

```
app.py                       # Streamlit dashboard (entry point for deployment)
main.py                      # CLI demo trace
simulator/network.py         # self-contained traffic network + arrivals/service model
optimization/qubo.py         # QUBO formulation (N intersections, emergency-weighted)
optimization/quantum_qaoa.py # real QAOA circuit + COBYLA parameter tuning
optimization/classical_baseline.py  # rule-based comparison baseline
emergency/corridor.py        # Emergency Green Corridor (dispatch/override/restore)
environment/emissions.py     # fuel/CO2 estimation + classical-vs-quantum comparison
events/event_simulator.py    # dynamic event triggers
core/engine.py                # orchestrates one full iteration of the pipeline
```
