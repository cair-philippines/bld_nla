"""
Mockup: Ranked schools with delta bar + grade-language heatmap.
Shows top N and bottom N.

Run: python scripts/viz_mockups_v6.py
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "mockups"
OUT.mkdir(exist_ok=True)

GRADE_LANGS = ["G1", "G2 MT", "G2 Fil", "G3 MT", "G3 Fil", "G3 Eng"]

tp_from = "BoSY 2024-25"
tp_to = "EoSY 2024-25"

# Sample schools with overall delta and per grade-lang deltas
schools = [
    {"name": "Sunrise Elementary School", "delta": +1.42,
     "gl_deltas": [+1.8, +1.5, +1.2, +1.6, -0.3, +1.4]},
    {"name": "Mountain View Central School", "delta": +1.18,
     "gl_deltas": [+1.3, +1.1, +1.4, +0.9, +1.2, +1.0]},
    {"name": "Lakeside Integrated School", "delta": +0.95,
     "gl_deltas": [+1.2, -0.4, +1.0, +1.3, +0.8, +1.1]},
    {"name": "Riverside Elementary School", "delta": +0.87,
     "gl_deltas": [+0.9, +1.0, +0.8, -0.5, +1.1, +0.7]},
    {"name": "Valley Elem. School", "delta": +0.82,
     "gl_deltas": [+0.7, +0.9, +1.0, +0.8, +0.6, -0.3]},
    {"name": "Coastal Elementary School", "delta": +0.75,
     "gl_deltas": [+0.5, +0.8, +0.9, +0.7, +1.0, +0.6]},
    {"name": "Hilltop Primary School", "delta": -0.75,
     "gl_deltas": [-0.5, -0.8, -0.3, -1.0, -0.6, -1.2]},
    {"name": "Seaside Elementary School", "delta": -0.88,
     "gl_deltas": [-0.7, -1.0, -0.5, -1.2, -0.8, -0.6]},
    {"name": "Greenfield Central School", "delta": -1.05,
     "gl_deltas": [-1.1, -0.8, -1.3, +0.2, -1.5, -0.9]},
    {"name": "Eastwood Integrated School", "delta": -1.22,
     "gl_deltas": [-1.0, -1.4, -1.1, -1.5, -0.9, -1.3]},
    {"name": "Westpark Elementary School", "delta": -1.45,
     "gl_deltas": [-1.8, -1.2, -1.5, -1.3, -1.6, -1.0]},
]


def build_ranked_heatmap(school_list, title, n=5):
    """Ranked delta bars + grade-language shift heatmap."""

    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.3, 0.7],
        horizontal_spacing=0.06,
        subplot_titles=["Overall Delta", "Shift by Grade / Language"],
    )

    school_names = [f"{i+1}. {s['name']}" for i, s in enumerate(school_list[:n])]
    deltas = [s["delta"] for s in school_list[:n]]
    bar_colors = ["#228B22" if d > 0 else "#DC143C" for d in deltas]

    # Left: ranked horizontal delta bars
    fig.add_trace(go.Bar(
        y=school_names,
        x=deltas,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{d:+.2f}" for d in deltas],
        textposition="outside",
        textfont=dict(size=12),
        showlegend=False,
        hovertemplate="%{y}<br>Delta: %{x:+.2f}<extra></extra>",
    ), row=1, col=1)

    fig.add_vline(x=0, line_color="#333", line_width=1, row=1, col=1)

    # Right: heatmap (schools × grade-langs)
    z_values = [s["gl_deltas"] for s in school_list[:n]]

    # Find symmetric max for color scale
    all_vals = [v for row in z_values for v in row]
    max_abs = max(abs(v) for v in all_vals) if all_vals else 1

    fig.add_trace(go.Heatmap(
        z=z_values,
        x=GRADE_LANGS,
        y=school_names,
        colorscale=[
            [0.0, "#DC143C"],
            [0.35, "#FFCCCC"],
            [0.5, "#FFFFFF"],
            [0.65, "#CCFFCC"],
            [1.0, "#228B22"],
        ],
        zmid=0,
        zmin=-max_abs,
        zmax=max_abs,
        colorbar=dict(
            title="Delta",
            tickformat="+.1f",
            len=0.9,
            x=1.02,
        ),
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:+.2f}<extra></extra>",
        showscale=True,
    ), row=1, col=2)

    # Add text annotations on heatmap cells
    for i, school in enumerate(school_list[:n]):
        for j, gl_delta in enumerate(school["gl_deltas"]):
            text_color = "white" if abs(gl_delta) > max_abs * 0.6 else "black"
            fig.add_annotation(
                x=GRADE_LANGS[j],
                y=school_names[i],
                text=f"{gl_delta:+.1f}",
                showarrow=False,
                font=dict(size=11, color=text_color),
                xref="x2", yref="y2",
            )

    # Layout
    fig.update_layout(
        height=max(300, 80 + n * 55),
        width=950,
        title=(
            f"<b>{title}</b>"
            f"<br><span style='font-size:13px;color:#666'>"
            f"{tp_from} → {tp_to} · N = {n}</span>"
        ),
        margin=dict(l=20, r=80, t=80, b=40),
    )

    # Left axes
    max_d = max(abs(d) for d in deltas)
    fig.update_xaxes(
        range=[-max_d * 1.5, max_d * 1.5],
        row=1, col=1,
    )
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(school_names)),
        tickfont=dict(size=10),
        row=1, col=1,
    )

    # Right axes
    fig.update_xaxes(side="top", tickfont=dict(size=11), row=1, col=2)
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(school_names)),
        showticklabels=False,
        row=1, col=2,
    )

    return fig


# Top 5
top5 = sorted(schools, key=lambda s: s["delta"], reverse=True)[:5]
fig_top = build_ranked_heatmap(top5, "Top 5 Schools by Progress", n=5)
fig_top.write_html(str(OUT / "10_ranked_heatmap_top5.html"))

# Bottom 5
bot5 = sorted(schools, key=lambda s: s["delta"])[:5]
fig_bot = build_ranked_heatmap(bot5, "Bottom 5 Schools by Progress", n=5)
fig_bot.write_html(str(OUT / "10_ranked_heatmap_bottom5.html"))

# Top 8 (to show N as variable)
top8 = sorted(schools, key=lambda s: s["delta"], reverse=True)[:8]
fig_top8 = build_ranked_heatmap(top8, "Top 8 Schools by Progress", n=8)
fig_top8.write_html(str(OUT / "10_ranked_heatmap_top8.html"))

print(f"Mockups written to {OUT}/")
print("  10_ranked_heatmap_top5.html")
print("  10_ranked_heatmap_bottom5.html")
print("  10_ranked_heatmap_top8.html")
