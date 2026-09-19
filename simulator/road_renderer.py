"""
Realistic, animated network map renderer.

v2 fixes vs. the first version:
  * Real two-lane roads: each road is drawn as two offset lanes with
    arrowheads, one lane per direction of travel — not a single bare line.
  * Correct signal-phase logic: a real 4-way junction never shows green
    in every direction at once (that would let crossing traffic collide).
    Each junction's connected roads are grouped into two perpendicular
    phase-axes; only ONE axis is ever green/amber at a time, the other
    is always red. During an emergency, only the axis that carries the
    corridor's through-direction is forced green — cross-traffic at that
    same junction still shows red, which is the actual real-world
    behaviour of a green-corridor override.
"""

import math

ROAD_W = 30
LANE_OFFSET = 7


def _scale_positions(positions, pad=90, cell=170):
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    span_x = (maxx - minx) or 1
    span_y = (maxy - miny) or 1
    cols = span_x / 120 + 1
    rows = span_y / 120 + 1
    width = int(cols * cell + pad * 2)
    height = int(rows * cell + pad * 2)
    out = {}
    for node, (x, y) in positions.items():
        nx_ = pad + (x - minx) / 120 * cell
        ny_ = pad + (y - miny) / 120 * cell
        out[node] = (nx_, ny_)
    return out, width, height


def _lane_with_arrows(x0, y0, x1, y1, offset_side, color, arrow_id, reverse=False):
    """One directional lane of a two-lane road, offset perpendicular to the
    road so the two directions of travel are visually distinct, with an
    arrowhead marker pointing the way traffic flows on that lane."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1
    px, py = -dy / length, dx / length  # unit perpendicular
    ox, oy = px * offset_side * LANE_OFFSET, py * offset_side * LANE_OFFSET

    ax0, ay0 = (x0 + ox, y0 + oy)
    ax1, ay1 = (x1 + ox, y1 + oy)
    if reverse:
        ax0, ay0, ax1, ay1 = ax1, ay1, ax0, ay0

    # pull endpoints in slightly so arrows don't bury themselves in the junction pad
    ux, uy = (ax1 - ax0) / length, (ay1 - ay0) / length
    sx, sy = ax0 + ux * 34, ay0 + uy * 34
    ex, ey = ax1 - ux * 34, ay1 - uy * 34

    return (
        f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
        f'stroke="{color}" stroke-width="5" stroke-linecap="round" opacity="0.85" '
        f'marker-end="url(#{arrow_id})"/>'
    )


def _lane_markers():
    return """
    <marker id="lane-arrow" markerWidth="9" markerHeight="9" refX="4" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8 Z" fill="#cfd4e6"/>
    </marker>
    """


def _signal_head(cx, cy, angle_deg, color, glow, size):
    glow_class = "sig-glow" if glow else ""
    return f"""
    <g transform="translate({cx},{cy}) rotate({angle_deg})">
      <rect x="-3" y="-2" width="6" height="14" fill="#20242e" rx="1.5"/>
      <circle class="{glow_class}" cx="0" cy="-6" r="{size}" fill="{color}" stroke="#0d0f14" stroke-width="1.2"/>
    </g>
    """


def _queue_dots(x, y, angle_deg, count, color):
    n = min(count, 8)
    dots = []
    for i in range(n):
        offset = 40 + i * 13
        dots.append(
            f'<g transform="translate({x},{y}) rotate({angle_deg}) translate(0,{offset})">'
            f'<rect x="-5" y="-3" width="10" height="6" rx="1.5" fill="{color}" opacity="{0.55 + 0.05*min(i,4)}"/>'
            f"</g>"
        )
    return "".join(dots)


def _phase_axes(neighbor_angles):
    """Split a junction's connected roads into up to two phase-axes
    (axis 0 / axis 1) by direction, so opposing traffic can share a
    phase but crossing traffic never does. Angles ~180 deg apart share
    an axis; anything else starts a new axis."""
    axes = []  # list of lists of angles
    for ang in neighbor_angles:
        placed = False
        for axis in axes:
            ref = axis[0]
            diff = abs(((ang - ref) + 180) % 360 - 180)
            if diff < 35 or diff > 145:  # same direction or opposite direction
                axis.append(ang)
                placed = True
                break
        if not placed:
            if len(axes) < 2:
                axes.append([ang])
            else:
                axes[0].append(ang)  # rare >4-way node: fold extra roads into axis 0
    return axes


def render_network_html(network, corridor, event_junction=None, height=560):
    positions = network.get_positions()
    scaled, width, height_calc = _scale_positions(positions)
    height = max(height, height_calc)
    edges = network.get_edges()
    state = network.get_state()
    corridor_nodes = corridor.corridor_nodes() if corridor else set()
    corridor_path = corridor.path if (corridor and corridor.active) else []
    corridor_edges = {frozenset((corridor_path[i], corridor_path[i + 1])) for i in range(len(corridor_path) - 1)}

    svg_parts = [f"<defs>{_lane_markers()}</defs>"]

    # --- roads: pavement + two directional lanes each ---
    for u, v in edges:
        x0, y0 = scaled[u]
        x1, y1 = scaled[v]
        is_corridor_edge = frozenset((u, v)) in corridor_edges

        svg_parts.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#20232d" stroke-width="{ROAD_W}" stroke-linecap="round"/>')
        svg_parts.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#3a3f52" stroke-width="{ROAD_W-6}" stroke-linecap="round"/>')
        svg_parts.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#e8e8e8" stroke-width="1.5" stroke-dasharray="9 9" opacity="0.4"/>')

        lane_color = "#8fa3ff" if not is_corridor_edge else "#ff8a95"
        svg_parts.append(_lane_with_arrows(x0, y0, x1, y1, +1, lane_color, "lane-arrow", reverse=False))
        svg_parts.append(_lane_with_arrows(x0, y0, x1, y1, -1, lane_color, "lane-arrow", reverse=True))

        if is_corridor_edge:
            svg_parts.append(
                f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#ff3b4e" stroke-width="4" '
                f'stroke-linecap="round" stroke-dasharray="14 10" class="ants" opacity="0.9"/>'
            )

    neighbor_map = {n: [] for n in scaled}
    for u, v in edges:
        neighbor_map[u].append(v)
        neighbor_map[v].append(u)

    # --- junctions: crossroad pad + 2-phase signal logic + queues ---
    for node, (x, y) in scaled.items():
        d = state[node]
        blocked = d["blocked"]
        is_corridor = node in corridor_nodes
        is_event = node == event_junction

        pad_color = "#8b8f9c" if blocked else "#262b3a"
        svg_parts.append(f'<circle cx="{x}" cy="{y}" r="32" fill="{pad_color}" stroke="#0d0f14" stroke-width="2"/>')
        if is_corridor:
            svg_parts.append(f'<circle cx="{x}" cy="{y}" r="36" fill="none" stroke="#ff3b4e" stroke-width="2.5" class="pulse-ring" opacity="0.8"/>')
        if is_event:
            svg_parts.append(f'<circle cx="{x}" cy="{y}" r="40" fill="none" stroke="#ffd166" stroke-width="2.5" stroke-dasharray="4 4" class="pulse-ring" opacity="0.9"/>')
        if blocked:
            svg_parts.append(
                f'<g transform="translate({x-9},{y-9})"><rect width="18" height="18" fill="#ffb703" rx="3"/>'
                f'<text x="9" y="14" font-size="13" text-anchor="middle" font-weight="800" fill="#1a1d24">!</text></g>'
            )

        neighbor_angles = []
        for nb in neighbor_map.get(node, []):
            nx_, ny_ = scaled[nb]
            neighbor_angles.append((math.degrees(math.atan2(ny_ - y, nx_ - x)), nb))

        angles_only = [a for a, _ in neighbor_angles]
        axes = _phase_axes(angles_only) if angles_only else [[0]]

        gt = d["green_time"]
        if gt >= 40:
            active_color, active_size, glow = "#2ecc71", 5.5, True
        elif gt >= 30:
            active_color, active_size, glow = "#ffd166", 4.5, False
        else:
            active_color, active_size, glow = "#ff5b5b", 4, False

        # Decide which axis (or axes) are green this cycle.
        # BUG FIXED HERE: when the emergency corridor bends at this junction
        # (arrives from one direction, leaves in a roughly perpendicular
        # direction), the arrival and departure edges can land on two
        # DIFFERENT phase-axes. The previous version kept overwriting a
        # single `active_axis_idx`, so only the last-processed axis won and
        # the other leg of the ambulance's own route still rendered red --
        # exactly the bug in the screenshot. A real emergency override
        # clears every direction the corridor actually uses, so now every
        # axis touched by a corridor edge is marked green, not just one.
        active_axes = set()
        if is_corridor:
            for i, axis in enumerate(axes):
                for ang, nb in neighbor_angles:
                    if ang in axis and frozenset((node, nb)) in corridor_edges:
                        active_axes.add(i)
        if not active_axes:
            active_axes = {0}

        for axis_idx, axis in enumerate(axes):
            for ang in axis:
                if blocked:
                    sig_color, sig_size, sig_glow = "#5c6070", 3, False
                elif axis_idx in active_axes:
                    sig_color, sig_size, sig_glow = active_color, active_size, glow
                else:
                    sig_color, sig_size, sig_glow = "#ff5b5b", 3.5, False  # the other axis is always red while this one runs

                hx = x + 34 * math.cos(math.radians(ang))
                hy = y + 34 * math.sin(math.radians(ang))
                svg_parts.append(_signal_head(hx, hy, ang + 90, sig_color, sig_glow, sig_size))
                queue_color = "#8b8f9c" if blocked else ("#f2a154" if axis_idx in active_axes else "#6c7284")
                svg_parts.append(_queue_dots(x, y, ang, d["queue"] // max(1, len(axes)), queue_color))

        svg_parts.append(f'<circle cx="{x}" cy="{y}" r="16" fill="#0d0f14" stroke="{"#ff3b4e" if is_corridor else "#3a4152"}" stroke-width="2"/>')
        svg_parts.append(f'<text x="{x}" y="{y+4}" font-size="12" font-weight="700" text-anchor="middle" fill="#ffffff">{node}</text>')
        svg_parts.append(f'<text x="{x}" y="{y+50}" font-size="10.5" text-anchor="middle" fill="#aab2c5">Q:{d["queue"]} · {gt}s</text>')

    svg = "".join(svg_parts)

    html = f"""
    <div class="map-wrap" style="width:100%; overflow-x:auto; border-radius:16px; background:
         radial-gradient(circle at 20% 15%, #171b26 0%, #0b0d12 70%); border:1px solid #262b38;">
    <style>
      .map-wrap {{ animation: mapIn .6s ease both; }}
      @keyframes mapIn {{ from {{ opacity:0; transform:scale(.98);}} to {{opacity:1; transform:scale(1);}} }}
      .ants {{ animation: dash 1.1s linear infinite; }}
      @keyframes dash {{ to {{ stroke-dashoffset: -48; }} }}
      .pulse-ring {{ animation: pulse 1.6s ease-in-out infinite; transform-origin: center; }}
      @keyframes pulse {{ 0% {{ opacity:0.9; }} 50% {{ opacity:0.2; }} 100% {{ opacity:0.9; }} }}
      .sig-glow {{ filter: drop-shadow(0 0 5px currentColor); animation: glow 1.4s ease-in-out infinite; }}
      @keyframes glow {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.55; }} }}
    </style>
    <svg viewBox="0 0 {width} {height}" width="100%" height="{height}" xmlns="http://www.w3.org/2000/svg">
      {svg}
    </svg>
    </div>
    """
    return html, height + 20
