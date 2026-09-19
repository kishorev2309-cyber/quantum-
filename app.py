import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit.components.v1 as components

from simulator.network import TrafficNetwork
from simulator.road_renderer import render_network_html
from simulator import flowcharts
from emergency.corridor import EmergencyCorridor
from events.event_simulator import trigger_event, clear_all_events
from core.engine import run_iteration, apply_quantum_result

st.set_page_config(page_title="Quantum Traffic Optimizer", page_icon="🚦", layout="wide")

# =============================================================================
# THEME
# =============================================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }

    .stApp {
        background:
          radial-gradient(circle at 10% 0%, rgba(108,140,255,0.10), transparent 45%),
          radial-gradient(circle at 90% 10%, rgba(255,120,120,0.06), transparent 40%),
          linear-gradient(0deg, #2a1750 0%, #170f2e 22%, #0b0d12 55%, #0b0d12 100%);
        background-size: 100% 220%;
        animation: risePurple 14s ease-in-out infinite alternate;
    }
    @keyframes risePurple {
        0%   { background-position: 0% 100%; }
        100% { background-position: 0% 0%; }
    }

    @keyframes fadeSlideUp {
        from { opacity: 0; transform: translateY(14px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .fade-in { animation: fadeSlideUp .7s ease both; }

    .hero {
        text-align:center; padding: 22px 10px 14px 10px; border-radius: 22px;
        background: linear-gradient(120deg, #241a3d, #171227 45%, #1a1420);
        border: 1px solid #3a2f5f; margin-bottom: 18px;
        box-shadow: 0 10px 40px -18px rgba(157,108,255,0.55);
        animation: fadeSlideUp .8s ease both, heroGlow 5s ease-in-out infinite alternate;
    }
    @keyframes heroGlow {
        from { box-shadow: 0 10px 40px -18px rgba(157,108,255,0.35); }
        to   { box-shadow: 0 10px 50px -14px rgba(157,108,255,0.75); }
    }
    .hero h1 {
        font-size: 34px; font-weight: 800; margin: 0;
        background: linear-gradient(90deg, #b28dff, #8ea2ff 40%, #ff9f6c 75%, #ffce6c);
        -webkit-background-clip: text; background-clip: text; color: transparent;
        background-size: 200% auto; animation: shine 6s linear infinite;
    }
    @keyframes shine { to { background-position: 200% center; } }
    .hero p { color: #c6bfe0; margin-top: 6px; font-size: 14.5px; }

    .glass-card {
        background: linear-gradient(160deg, #1a1626, #12101c);
        border: 1px solid #2b2740; border-radius: 16px; padding: 14px 16px;
        transition: transform .18s ease, border-color .18s ease;
        animation: fadeSlideUp .5s ease both;
    }
    .glass-card:hover { transform: translateY(-3px) scale(1.01); border-color: #9d6cff88; }

    .pill { display:inline-block; padding: 2px 10px; border-radius:999px; font-size:11px; font-weight:700; }
    .pill-green { background:#123a2c; color:#3ddc84; }
    .pill-orange { background:#3a2d12; color:#ffb457; }
    .pill-red { background:#3a1418; color:#ff6b6b; }
    .pill-grey { background:#22242e; color:#9aa1b5; }

    div[data-testid="stMetric"] {
        background: linear-gradient(160deg, #1a1626, #12101c);
        border: 1px solid #2b2740; border-radius: 16px; padding: 10px 14px 6px 14px;
        animation: fadeSlideUp .6s ease both;
    }
    div[data-testid="column"]:nth-of-type(1) div[data-testid="stMetric"] { animation-delay: .05s; }
    div[data-testid="column"]:nth-of-type(2) div[data-testid="stMetric"] { animation-delay: .12s; }
    div[data-testid="column"]:nth-of-type(3) div[data-testid="stMetric"] { animation-delay: .19s; }
    div[data-testid="column"]:nth-of-type(4) div[data-testid="stMetric"] { animation-delay: .26s; }

    .timeline-item {
        border-left: 2px solid #3a2f5f; padding: 2px 0 10px 14px; margin-left: 4px;
        font-size: 13.5px; color:#c6cbe0; animation: fadeSlideUp .5s ease both;
    }
    .timeline-item b { color:#b28dff; }

    .section-tag { color:#b28dff; font-weight:700; font-size:12.5px; letter-spacing:0.06em; text-transform:uppercase; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>🚦 Quantum-Enhanced Adaptive Urban Traffic Optimization</h1>
      <p>Hybrid QUBO + QAOA signal control · Emergency Green Corridor · live classical-vs-quantum comparison</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# SESSION STATE
# =============================================================================


def _init_network(n, seed=None):
    st.session_state.num_intersections = n
    st.session_state.network = TrafficNetwork(num_intersections=n, seed=seed)
    st.session_state.corridor = EmergencyCorridor(st.session_state.network)
    st.session_state.history = []
    st.session_state.event_log = []
    st.session_state.iteration = 0
    st.session_state.last_event_junction = None


if "network" not in st.session_state:
    _init_network(6)

network = st.session_state.network
corridor = st.session_state.corridor
junction_ids = list(network.get_state().keys())

# =============================================================================
# SIDEBAR
# =============================================================================

st.sidebar.title("⚙️ Control Panel")

with st.sidebar.expander("🌐 Network size", expanded=False):
    n_choice = st.slider("Number of junctions", 2, 8, st.session_state.num_intersections)
    if st.button("Rebuild network", use_container_width=True):
        _init_network(n_choice)
        st.rerun()

# How many junctions get a real quantum (QAOA) decision this round — kept
# fixed and internal rather than a sidebar control: it's an implementation
# detail (the most congested/priority junctions get one), not something a
# demo needs to fiddle with. Every junction still gets a timing decision
# either way (the rest fall back to the classical rule).
k = min(4, len(junction_ids))

if st.sidebar.button("▶️ Run next round", use_container_width=True, type="primary"):
    network.step()
    st.session_state.iteration += 1
    result = run_iteration(network, emergency_corridor=corridor, k=k)
    apply_quantum_result(network, result)
    st.session_state.history.append(result)

if st.session_state.history and st.sidebar.button("🔁 Re-optimize this round", use_container_width=True):
    result = run_iteration(network, emergency_corridor=corridor, k=k)
    apply_quantum_result(network, result)
    st.session_state.history.append(result)

def _auto_reoptimize():
    """
    Runs one optimization pass against the CURRENT state (no time-advance)
    and records it in history. Called right after every event trigger so
    the signal lights, the Quantum tab, and the Environmental tab all
    react immediately — previously an event only changed the traffic
    state, and nothing re-ran the optimizer until a *separate* "Run next
    round" click, so the lights looked unresponsive and the other two
    tabs stayed on their empty placeholder until that extra click.
    """
    result = run_iteration(network, emergency_corridor=corridor, k=k)
    apply_quantum_result(network, result)
    st.session_state.history.append(result)


st.sidebar.markdown('<span class="section-tag">Dynamic events</span>', unsafe_allow_html=True)
event_target = st.sidebar.selectbox("Target junction", junction_ids, key="evt_target")

col_a, col_b = st.sidebar.columns(2)
with col_a:
    if st.button("🚗 Congestion", use_container_width=True):
        msg, node = trigger_event(network, corridor, "congestion_spike", node=event_target)
        st.session_state.event_log.append(msg)
        st.session_state.last_event_junction = node
        _auto_reoptimize()
    if st.button("🚧 Closure", use_container_width=True):
        edges = network.get_edges()
        my_edges = [e for e in edges if event_target in e]
        edge = my_edges[0] if my_edges else None
        msg, node = trigger_event(network, corridor, "road_closure", edge=edge)
        st.session_state.event_log.append(msg)
        st.session_state.last_event_junction = node
        _auto_reoptimize()
with col_b:
    if st.button("💥 Accident", use_container_width=True):
        msg, node = trigger_event(network, corridor, "accident", node=event_target)
        st.session_state.event_log.append(msg)
        st.session_state.last_event_junction = node
        _auto_reoptimize()

st.sidebar.caption("🚑 Emergency dispatch")
c1, c2 = st.sidebar.columns(2)
with c1:
    src = st.selectbox("From", junction_ids, key="evt_src")
with c2:
    dst = st.selectbox("To", junction_ids, index=min(1, len(junction_ids) - 1), key="evt_dst")
if st.sidebar.button("🚑 Dispatch emergency vehicle", use_container_width=True):
    msg, node = trigger_event(network, corridor, "emergency_vehicle", source=src, destination=dst)
    st.session_state.event_log.append(msg)
    st.session_state.last_event_junction = node
    _auto_reoptimize()

if st.sidebar.button("🧹 Clear all events", use_container_width=True):
    clear_all_events(network, corridor)
    st.session_state.event_log.append("All events cleared, signals restored to normal.")
    st.session_state.last_event_junction = None
    _auto_reoptimize()

if st.sidebar.button("🔄 Reset simulation", use_container_width=True):
    _init_network(st.session_state.num_intersections)
    st.rerun()

latest = st.session_state.history[-1] if st.session_state.history else None

# =============================================================================
# TABS
# =============================================================================

tab_overview, tab_network, tab_quantum, tab_emissions = st.tabs(
    ["📊 Overview", "🗺️ Network Map", "⚛️ Quantum Optimization", "🌱 Environmental Impact"]
)

# ---------------------------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------------------------
with tab_overview:
    state = network.get_state()
    total_vehicles = sum(d["vehicles"] for d in state.values())
    total_queue = sum(d["queue"] for d in state.values())
    total_waiting = sum(d["waiting_time"] for d in state.values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚗 Total vehicles", total_vehicles)
    c2.metric("🚙 Total queue", total_queue)
    c3.metric("⏱ Total waiting (s)", f"{total_waiting:.1f}")
    c4.metric("🔄 Round", st.session_state.iteration)

    if corridor.active:
        st.success(f"🚑 Emergency corridor active: **{' → '.join(corridor.path)}** — forced to max green.")

    st.markdown('<span class="section-tag">Per-intersection state</span>', unsafe_allow_html=True)
    cols = st.columns(3)
    for i, (j, d) in enumerate(state.items()):
        if d["blocked"]:
            pill = '<span class="pill pill-grey">🚧 Blocked</span>'
        elif j in corridor.corridor_nodes():
            pill = '<span class="pill pill-red">🚑 Corridor</span>'
        elif d["queue"] > 8:
            pill = '<span class="pill pill-orange">Congested</span>'
        else:
            pill = '<span class="pill pill-green">Normal</span>'
        fill_pct = min(100, int(d["queue"] / max(1, d["capacity"] / 3) * 100))
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="glass-card" style="margin-bottom:12px; animation-delay:{i*0.07:.2f}s;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="font-size:15px;">{j}</b> {pill}
                  </div>
                  <div style="font-size:12.5px; color:#9aa1b5; margin-top:6px;">Queue {d['queue']} · {d['vehicles']} vehicles</div>
                  <div style="background:#22242e; border-radius:999px; height:7px; margin-top:8px; overflow:hidden;">
                    <div style="width:{fill_pct}%; background:linear-gradient(90deg,#6c8cff,#ff9f6c); height:100%;"></div>
                  </div>
                  <div style="display:flex; justify-content:space-between; font-size:11.5px; color:#7c839a; margin-top:6px;">
                    <span>Green {d['green_time']}s</span><span>Wait {d['waiting_time']:.0f}s</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if st.session_state.event_log:
        st.markdown('<span class="section-tag">Event log</span>', unsafe_allow_html=True)
        for i, msg in enumerate(reversed(st.session_state.event_log[-8:])):
            st.markdown(f'<div class="timeline-item" style="animation-delay:{i*0.06:.2f}s;">{msg}</div>', unsafe_allow_html=True)

    if not latest:
        st.info("👈 Click **Run next round** in the sidebar to run the first QUBO + QAOA optimization pass.")

# ---------------------------------------------------------------------------
# NETWORK MAP
# ---------------------------------------------------------------------------
with tab_network:
    st.caption(
        "Two-lane roads with arrows showing travel direction. Each junction only ever has ONE axis "
        "green at a time (real traffic-light logic) — the other axis stays red, even on an emergency "
        "corridor junction, where only the ambulance's own direction is forced green and cross-traffic "
        "still waits. 🟢 Long green (40s) · 🟡 Mid green (30s) · 🔴 Short green (20s) · ⚪ Blocked · "
        "Red dashed = emergency corridor · Amber ring = last event"
    )
    html, h = render_network_html(network, corridor, event_junction=st.session_state.last_event_junction)
    components.html(html, height=h, scrolling=True)

# ---------------------------------------------------------------------------
# QUANTUM OPTIMIZATION
# ---------------------------------------------------------------------------
with tab_quantum:
    if not latest:
        st.info("Run a round to see the QUBO → QAOA optimization in action.")
    else:
        st.markdown('<span class="section-tag">Two pipelines, same traffic snapshot</span>', unsafe_allow_html=True)
        st.caption("Same traffic data goes into both — a simple fixed rule, and the quantum optimizer — so the comparison is fair.")
        colF1, colF2 = st.columns(2)
        with colF1:
            st.markdown("**📏 Classical baseline**")
            st.markdown(flowcharts.classical_flow_svg(), unsafe_allow_html=True)
        with colF2:
            st.markdown("**⚛️ Quantum (QAOA)**")
            st.markdown(flowcharts.quantum_flow_svg(), unsafe_allow_html=True)

        st.markdown('<span class="section-tag">Where the two decisions differ</span>', unsafe_allow_html=True)
        all_junctions = sorted(set(latest["classical_decisions"]) | set(latest["quantum_decisions"]))
        classical_gt = [latest["classical_decisions"].get(j, {}).get("green_time", 0) for j in all_junctions]
        quantum_gt = [latest["quantum_decisions"].get(j, {}).get("green_time", latest["classical_decisions"].get(j, {}).get("green_time", 0)) for j in all_junctions]

        fig_cmp = go.Figure()
        fig_cmp.add_trace(go.Bar(x=all_junctions, y=classical_gt, name="Classical", marker_color="#8ea2ff"))
        fig_cmp.add_trace(go.Bar(x=all_junctions, y=quantum_gt, name="Quantum (QAOA)", marker_color="#ff9f6c"))
        fig_cmp.update_layout(
            barmode="group", height=300, plot_bgcolor="#0d0f14", paper_bgcolor="#0d0f14",
            margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Green time (s)", legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig_cmp, use_container_width=True)

        quantum_only = {j for j in latest["quantum_decisions"]}
        st.caption(f"This round, the quantum optimizer directly decided: {', '.join(sorted(quantum_only)) or '—'} (busiest junctions get a real quantum decision; the rest use the classical rule, so nothing is left unserved).")

        st.markdown('<span class="section-tag">Which one is winning, in plain terms</span>', unsafe_allow_html=True)
        picks = []
        for j in all_junctions:
            c = latest["classical_decisions"].get(j, {}).get("green_time")
            q = latest["quantum_decisions"].get(j, {}).get("green_time", c)
            if q == c:
                verdict = "Same choice"
            elif q > c:
                verdict = "Quantum gave more green"
            else:
                verdict = "Quantum gave less green"
            picks.append({"Junction": j, "Classical": f"{c}s", "Quantum": f"{q}s", "Verdict": verdict})
        st.dataframe(pd.DataFrame(picks), use_container_width=True, hide_index=True)

        st.markdown('<span class="section-tag">How confident was the quantum optimizer?</span>', unsafe_allow_html=True)
        if latest["quantum_best"]:
            confidence_pct = round(100 * latest["quantum_best"]["count"] / 512, 1)
            st.progress(min(1.0, confidence_pct / 100), text=f"Its best answer came up {confidence_pct}% of the time when sampled — higher means the optimizer is more sure.")

        if latest["qaoa_history"]:
            st.caption("How its confidence improved while it kept tuning itself:")
            hist_df = pd.DataFrame({"Round": range(1, len(latest["qaoa_history"]) + 1), "Cost (lower = better)": latest["qaoa_history"]})
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=hist_df["Round"], y=hist_df["Cost (lower = better)"], mode="lines+markers", line=dict(color="#b28dff", width=3), fill="tozeroy", fillcolor="rgba(178,141,255,0.12)"))
            fig2.update_layout(height=260, plot_bgcolor="#0d0f14", paper_bgcolor="#0d0f14", margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# ENVIRONMENTAL IMPACT
# ---------------------------------------------------------------------------
with tab_emissions:
    if not latest:
        st.info("Run a round to see the environmental comparison.")
    else:
        em = latest["emissions"]

        def _clamp(v, lo=-50, hi=100):
            # raw % improvement can swing wildly when the "before" number is
            # tiny (near-empty traffic), which reads as a broken gauge rather
            # than an honest edge case — clamp what's *displayed*, the raw
            # figures are still available in the expander below.
            return max(lo, min(hi, v))

        def gauge(value, title, color):
            fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=_clamp(value),
                    number={"suffix": "%", "font": {"color": "#eef0f6", "size": 30}},
                    title={"text": title, "font": {"size": 13, "color": "#aab2c5"}},
                    gauge={
                        "axis": {"range": [-50, 100], "tickcolor": "#3a3f52"},
                        "bar": {"color": color},
                        "bgcolor": "#161a25",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [-50, 0], "color": "#2a1620"},
                            {"range": [0, 100], "color": "#141a22"},
                        ],
                    },
                )
            )
            fig.update_layout(height=220, margin=dict(l=10, r=10, t=40, b=5), paper_bgcolor="rgba(0,0,0,0)", font_color="#eef0f6")
            return fig

        g1, g2, g3 = st.columns(3)
        g1.plotly_chart(gauge(em["waiting_improvement_pct"], "⏱ Waiting-time improvement", "#b28dff"), use_container_width=True)
        g2.plotly_chart(gauge(em["fuel_improvement_pct"], "⛽ Fuel saved", "#3ddc84"), use_container_width=True)
        g3.plotly_chart(gauge(em["co2_improvement_pct"], "🌍 CO₂ reduced", "#ff9f6c"), use_container_width=True)

        rows = []
        for it, result in enumerate(st.session_state.history, start=1):
            e = result["emissions"]
            rows.append({"Round": it, "Waiting %": _clamp(e["waiting_improvement_pct"]), "Fuel %": _clamp(e["fuel_improvement_pct"]), "CO2 %": _clamp(e["co2_improvement_pct"])})
        trend_df = pd.DataFrame(rows)

        fig3 = go.Figure()
        for col, color in [("Waiting %", "#b28dff"), ("Fuel %", "#3ddc84"), ("CO2 %", "#ff9f6c")]:
            fig3.add_trace(go.Scatter(x=trend_df["Round"], y=trend_df[col], mode="lines+markers", name=col, line=dict(color=color, width=3)))
        fig3.update_layout(height=360, plot_bgcolor="#0d0f14", paper_bgcolor="#0d0f14", margin=dict(l=10, r=10, t=10, b=10), yaxis_title="% improvement, quantum vs classical", legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig3, use_container_width=True)

        st.caption(
            "A negative value during an active emergency-vehicle event is expected and honest: "
            "the Emergency Corridor deliberately forces max green on the ambulance route, trading "
            "some network-wide efficiency for emergency response time."
        )

        with st.expander("Raw fuel/CO₂ figures"):
            st.json(em)
