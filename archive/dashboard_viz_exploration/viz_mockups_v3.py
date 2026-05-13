"""
Cumulative distribution shift mockup — negative shift (summer loss).
EoSY 2024-25 -> BoSY 2025-26: learners slide DOWN the proficiency ladder.

Run: python scripts/viz_mockups_v3.py
"""

import plotly.graph_objects as go
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "mockups"
OUT.mkdir(exist_ok=True)

PROFILES = ["Lower Emergent", "Higher Emergent", "Developing", "Transitioning", "Grade Level"]

# EoSY 2024-25 (strong) -> BoSY 2025-26 (regressed)
tp_a = {"label": "EoSY 2024-25", "values": [8, 15, 25, 28, 24]}
tp_b = {"label": "BoSY 2025-26", "values": [20, 27, 28, 16, 9]}

cum_a = np.cumsum(tp_a["values"]).tolist()
cum_b = np.cumsum(tp_b["values"]).tolist()

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=PROFILES,
    y=cum_a,
    mode="lines+markers+text",
    name=tp_a["label"],
    line=dict(color="#4A90D9", width=3),
    marker=dict(size=10),
    text=[f"{v}%" for v in cum_a],
    textposition="bottom center",
    textfont=dict(size=12),
))

fig.add_trace(go.Scatter(
    x=PROFILES,
    y=cum_b,
    mode="lines+markers+text",
    name=tp_b["label"],
    line=dict(color="#E74C3C", width=3),
    marker=dict(size=10),
    text=[f"{v}%" for v in cum_b],
    textposition="top center",
    textfont=dict(size=12),
))

# Shade the gap — red this time since shift is downward
fig.add_trace(go.Scatter(
    x=PROFILES + PROFILES[::-1],
    y=cum_b + cum_a[::-1],
    fill="toself",
    fillcolor="rgba(220, 20, 60, 0.15)",
    line=dict(width=0),
    showlegend=False,
    hoverinfo="skip",
))

for i, profile in enumerate(PROFILES):
    gap = cum_a[i] - cum_b[i]
    if gap != 0:
        mid_y = (cum_a[i] + cum_b[i]) / 2
        fig.add_annotation(
            x=profile, y=mid_y,
            text=f"<b>{gap:+d}pp</b>",
            showarrow=False,
            font=dict(size=11, color="#228B22" if gap > 0 else "#DC143C"),
            bgcolor="rgba(255,255,255,0.8)",
        )

fig.update_layout(
    title=(
        "<b>Cumulative Distribution Shift — Negative (Summer Loss)</b>"
        "<br><span style='font-size:13px;color:#666'>"
        "End curve ABOVE start curve = learners shifted DOWN the proficiency ladder. "
        "Red gap = regression.</span>"
    ),
    height=450,
    width=750,
    xaxis=dict(title="Reading Profile (low → high)"),
    yaxis=dict(title="Cumulative % of Learners", range=[0, 105]),
    legend=dict(orientation="h", y=-0.15, xanchor="center", x=0.5),
    margin=dict(l=60, r=20, t=90, b=60),
)

fig.write_html(str(OUT / "7_cumulative_shift_negative.html"))

print(f"Written to {OUT / '7_cumulative_shift_negative.html'}")
