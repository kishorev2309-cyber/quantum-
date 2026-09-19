"""Two hand-drawn SVG flowcharts (classical vs quantum pipeline) — no
external graphviz dependency, so nothing extra to install for deploy."""


def _box(x, y, w, h, text, color, subtext=""):
    lines = text.split("\n")
    ty = y + h / 2 - (len(lines) - 1) * 7
    tspans = "".join(f'<tspan x="{x+w/2}" dy="{0 if i==0 else 16}">{t}</tspan>' for i, t in enumerate(lines))
    sub = f'<text x="{x+w/2}" y="{y+h-8}" font-size="9.5" fill="#aab2c5" text-anchor="middle">{subtext}</text>' if subtext else ""
    return f"""
    <g>
      <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{color}" stroke="#0d0f14" stroke-width="1.5"/>
      <text x="{x+w/2}" y="{ty}" font-size="12.5" font-weight="700" fill="#0d0f14" text-anchor="middle">{tspans}</text>
      {sub}
    </g>
    """


def _arrow(x1, y1, x2, y2, color="#5c6070"):
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2.5" '
        f'marker-end="url(#arrow-{color.strip("#")})"/>'
    )


def _defs():
    colors = ["5c6070", "6c8cff", "ff9f6c"]
    markers = "".join(
        f'''<marker id="arrow-{c}" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
              <path d="M0,0 L8,3 L0,6 Z" fill="#{c}"/></marker>'''
        for c in colors
    )
    return f"<defs>{markers}</defs>"


def classical_flow_svg():
    w, h = 260, 560
    steps = [
        ("Traffic snapshot", "#6c8cff", "queue, wait, vehicles"),
        ("Congestion score", "#6c8cff", "queue×10 + waiting"),
        ("Fixed rule lookup", "#6c8cff", "score → 20/30/40s"),
        ("Apply green time", "#6c8cff", "per junction, direct"),
        ("Baseline result", "#3a3f52", "for comparison only"),
    ]
    boxes, arrows = [], []
    bw, bh, gap = 200, 78, 30
    y = 20
    for i, (label, color, sub) in enumerate(steps):
        boxes.append(_box(30, y, bw, bh, label, color, sub))
        if i < len(steps) - 1:
            arrows.append(_arrow(130, y + bh, 130, y + bh + gap, "#5c6070"))
        y += bh + gap
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" xmlns="http://www.w3.org/2000/svg">{_defs()}{"".join(boxes)}{"".join(arrows)}</svg>'


def quantum_flow_svg():
    w, h = 260, 560
    steps = [
        ("Traffic snapshot", "#ff9f6c", "same data as classical"),
        ("Build QUBO matrix", "#ff9f6c", "congestion + 1-choice\n+ cycle-budget terms"),
        ("QAOA circuit", "#ff9f6c", "RZ/RZZ from Q, mixer RX"),
        ("COBYLA tunes γ, β", "#ffce6c", "classical ↔ quantum loop"),
        ("Sample best bitstring", "#ff9f6c", "512 shots, lowest cost"),
        ("Decode + apply", "#ff9f6c", "per junction green time"),
    ]
    boxes, arrows = [], []
    bw, bh, gap = 210, 78, 22
    y = 20
    for i, (label, color, sub) in enumerate(steps):
        boxes.append(_box(25, y, bw, bh, label, color, sub))
        if i < len(steps) - 1:
            if i == 2:  # loop-back arrow from COBYLA to circuit
                arrows.append(_arrow(25, y + bh + gap + bh / 2, 5, y + bh + gap + bh / 2))
                arrows.append(f'<path d="M5,{y+bh+gap+bh/2} L5,{y+bh/2} L25,{y+bh/2}" fill="none" stroke="#ffce6c" stroke-width="2" stroke-dasharray="4 3"/>')
            arrows.append(_arrow(130, y + bh, 130, y + bh + gap, "#5c6070"))
        y += bh + gap
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" xmlns="http://www.w3.org/2000/svg">{_defs()}{"".join(boxes)}{"".join(arrows)}</svg>'
