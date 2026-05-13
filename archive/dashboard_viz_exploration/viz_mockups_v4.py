"""
Hybrid mockup: Cumulative distribution shift + per-profile diverging bars.
Generates both positive (learning) and negative (summer loss) versions.

Run: python scripts/viz_mockups_v4.py
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "mockups"
OUT.mkdir(exist_ok=True)

PROFILES = ["Lower Emergent", "Higher Emergent", "Developing", "Transitioning", "Grade Level"]
PROFILE_COLORS = ["#DC143C", "#FF8C00", "#FFD700", "#9ACD32", "#228B22"]


def build_hybrid(tp_a, tp_b, filename, subtitle):
    cum_a = np.cumsum(tp_a["values"]).tolist()
    cum_b = np.cumsum(tp_b["values"]).tolist()
    deltas = [b - a for a, b in zip(tp_a["values"], tp_b["values"])]

    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.6, 0.4],
        horizontal_spacing=0.08,
        subplot_titles=[
            "Cumulative Distribution Shift",
            "Per-Profile Change (pp)",
        ],
    )

    # --- Left panel: Cumulative shift ---

    fig.add_trace(go.Scatter(
        x=PROFILES,
        y=cum_a,
        mode="lines+markers+text",
        name=tp_a["label"],
        line=dict(color="#4A90D9", width=3),
        marker=dict(size=10),
        text=[f"{v}%" for v in cum_a],
        textposition="top center",
        textfont=dict(size=11),
        legendgroup="start",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=PROFILES,
        y=cum_b,
        mode="lines+markers+text",
        name=tp_b["label"],
        line=dict(color="#E74C3C", width=3),
        marker=dict(size=10),
        text=[f"{v}%" for v in cum_b],
        textposition="bottom center",
        textfont=dict(size=11),
        legendgroup="end",
    ), row=1, col=1)

    # Shade gap with appropriate color
    net_shift = sum(cum_a[i] - cum_b[i] for i in range(len(PROFILES) - 1))
    if net_shift > 0:
        fill_color = "rgba(34, 139, 34, 0.15)"
        shade_order = cum_a + cum_b[::-1]
    else:
        fill_color = "rgba(220, 20, 60, 0.15)"
        shade_order = cum_b + cum_a[::-1]

    fig.add_trace(go.Scatter(
        x=PROFILES + PROFILES[::-1],
        y=shade_order,
        fill="toself",
        fillcolor=fill_color,
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ), row=1, col=1)

    # Gap annotations (skip Grade Level since always 100%)
    for i in range(len(PROFILES) - 1):
        gap = cum_a[i] - cum_b[i]
        if gap != 0:
            mid_y = (cum_a[i] + cum_b[i]) / 2
            fig.add_annotation(
                x=PROFILES[i], y=mid_y,
                text=f"<b>{gap:+d}pp</b>",
                showarrow=False,
                font=dict(size=10, color="#228B22" if gap > 0 else "#DC143C"),
                bgcolor="rgba(255,255,255,0.8)",
                xref="x1", yref="y1",
            )

    # --- Right panel: Diverging bars ---

    bar_colors = [PROFILE_COLORS[i] for i in range(len(PROFILES))]

    fig.add_trace(go.Bar(
        y=PROFILES,
        x=deltas,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{d:+d}" for d in deltas],
        textposition="outside",
        textfont=dict(size=12),
        showlegend=False,
        hovertemplate="%{y}: %{x:+d}pp<extra></extra>",
    ), row=1, col=2)

    fig.add_vline(x=0, line_color="#333333", line_width=1.5, row=1, col=2)

    # Layout
    fig.update_layout(
        title=(
            f"<b>Hybrid: Cumulative Shift + Per-Profile Change</b>"
            f"<br><span style='font-size:13px;color:#666'>{subtitle}</span>"
        ),
        height=450,
        width=950,
        legend=dict(orientation="h", y=-0.12, xanchor="center", x=0.3),
        margin=dict(l=20, r=40, t=90, b=60),
    )

    # Left panel axes
    fig.update_xaxes(title=None, row=1, col=1)
    fig.update_yaxes(title="Cumulative %", range=[0, 105], row=1, col=1)

    # Right panel axes
    fig.update_xaxes(title="Change (pp)", row=1, col=2)
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(PROFILES)),
        row=1, col=2,
    )

    fig.write_html(str(OUT / filename))
    print(f"  {filename}")


# Positive shift (learning period)
build_hybrid(
    tp_a={"label": "BoSY 2024-25", "values": [18, 25, 30, 17, 10]},
    tp_b={"label": "EoSY 2024-25", "values": [8, 15, 25, 28, 24]},
    filename="8_hybrid_positive.html",
    subtitle="BoSY 2024-25 → EoSY 2024-25 (upward shift)",
)

# Negative shift (summer loss)
build_hybrid(
    tp_a={"label": "EoSY 2024-25", "values": [8, 15, 25, 28, 24]},
    tp_b={"label": "BoSY 2025-26", "values": [20, 27, 28, 16, 9]},
    filename="8_hybrid_negative.html",
    subtitle="EoSY 2024-25 → BoSY 2025-26 (downward shift / summer loss)",
)

print(f"\nMockups written to {OUT}/")
