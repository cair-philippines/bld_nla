"""
Mockup: Ranked view with delta + assessed count indicator + rank mode toggle.
Option 4: Show both, let the user decide.

Run: python scripts/viz_mockups_v7.py
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

# Sample schools: mix of small and large, high and moderate deltas
schools = [
    {"name": "Mantapay ES", "id": 136960, "delta": +2.47, "assessed": 18,
     "div": "Dumaguete City", "reg": "Region VII",
     "gl_deltas": [+3.0, +2.5, +2.0, +2.8, +2.2, +2.3]},
    {"name": "Sunrise Elementary School", "id": 101001, "delta": +1.42, "assessed": 487,
     "div": "Cebu City", "reg": "Region VII",
     "gl_deltas": [+1.8, +1.5, +1.2, +1.6, +1.1, +1.4]},
    {"name": "Mountain View Central School", "id": 102002, "delta": +1.18, "assessed": 623,
     "div": "Baguio City", "reg": "CAR",
     "gl_deltas": [+1.3, +1.1, +1.4, +0.9, +1.2, +1.0]},
    {"name": "Lakeside Integrated School", "id": 103003, "delta": +0.95, "assessed": 412,
     "div": "Laguna", "reg": "Region IV-A",
     "gl_deltas": [+1.2, -0.4, +1.0, +1.3, +0.8, +1.1]},
    {"name": "Riverside Elementary School", "id": 104004, "delta": +0.87, "assessed": 356,
     "div": "Davao City", "reg": "Region XI",
     "gl_deltas": [+0.9, +1.0, +0.8, -0.5, +1.1, +0.7]},
    {"name": "Valley Elem. School", "id": 105005, "delta": +0.82, "assessed": 289,
     "div": "Bukidnon", "reg": "Region X",
     "gl_deltas": [+0.7, +0.9, +1.0, +0.8, +0.6, -0.3]},
    {"name": "Hilltop Primary School", "id": 106006, "delta": +0.78, "assessed": 534,
     "div": "Iloilo City", "reg": "Region VI",
     "gl_deltas": [+0.5, +0.8, +0.9, +0.7, +1.0, +0.6]},
    {"name": "Coastal Elementary School", "id": 107007, "delta": +1.95, "assessed": 24,
     "div": "Sarangani", "reg": "Region XII",
     "gl_deltas": [+2.5, +1.8, +1.5, +2.0, +1.9, +2.1]},
    {"name": "Peak View ES", "id": 108008, "delta": +1.65, "assessed": 31,
     "div": "Mt. Province", "reg": "CAR",
     "gl_deltas": [+2.0, +1.5, +1.8, +1.2, +1.7, +1.6]},
    {"name": "Grand Central School", "id": 109009, "delta": +0.75, "assessed": 891,
     "div": "Manila", "reg": "NCR",
     "gl_deltas": [+0.8, +0.7, +0.6, +0.9, +0.7, +0.8]},
]

MAX_NAME_LEN = 25


def _truncate(name, sid):
    if len(name) > MAX_NAME_LEN:
        name = name[:MAX_NAME_LEN].rstrip() + "..."
    return f"{name} ({sid})"


def _build_title(title, tp_from, tp_to, sort_by):
    sort_label = "Weighted (delta x log N)" if sort_by == "weighted" else "Delta"
    return (
        f"<b>{title}</b>"
        f"<br><span style='font-size:13px;color:#666'>"
        f"{tp_from} \u2192 {tp_to} \u00b7 "
        f"Sorted by: {sort_label}"
        f"</span>"
    )


def build_ranked_view(school_list, title, sort_by="delta"):
    """
    3-column layout: delta bars | assessed count bars | grade-lang heatmap
    sort_by: "delta" or "weighted"
    """
    n = len(school_list)

    # Sort
    if sort_by == "weighted":
        school_list = sorted(school_list, key=lambda s: s["delta"] * np.log1p(s["assessed"]), reverse=True)
    else:
        school_list = sorted(school_list, key=lambda s: s["delta"], reverse=True)

    labels = []
    for i, s in enumerate(school_list):
        trunc = _truncate(s["name"], s["id"])
        line1 = f"{i+1}. {trunc}"
        line2 = f"   {s['div']}, {s['reg']}"
        labels.append(f"{line1}<br><span style='font-size:9px;color:#888'>{line2}</span>")

    deltas = [s["delta"] for s in school_list]
    assessed = [s["assessed"] for s in school_list]
    bar_colors = ["#228B22" if d > 0 else "#DC143C" for d in deltas]

    # Grade-lang heatmap data
    z_values = [s["gl_deltas"] for s in school_list]
    all_gl = [v for row in z_values for v in row if not np.isnan(v)]
    max_abs = max(abs(v) for v in all_gl) if all_gl else 1

    fig = make_subplots(
        rows=1, cols=3,
        column_widths=[0.25, 0.15, 0.60],
        horizontal_spacing=0.04,
    )

    # Col 1: Delta bars
    fig.add_trace(go.Bar(
        y=labels,
        x=deltas,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{d:+.2f}" for d in deltas],
        textposition="outside",
        textfont=dict(size=10),
        showlegend=False,
        cliponaxis=False,
        hovertemplate="%{y}<br>Delta: %{x:+.2f}<extra></extra>",
    ), row=1, col=1)

    fig.add_vline(x=0, line_color="#333", line_width=1, row=1, col=1)

    # Col 2: Assessed count bars (horizontal, all same color)
    max_assessed = max(assessed)
    fig.add_trace(go.Bar(
        y=labels,
        x=assessed,
        orientation="h",
        marker_color="#5B9BD5",
        text=[f"{a:,}" for a in assessed],
        textposition="outside",
        textfont=dict(size=10),
        showlegend=False,
        cliponaxis=False,
        hovertemplate="%{y}<br>Assessed: %{x:,}<extra></extra>",
    ), row=1, col=2)

    # Col 3: Heatmap
    fig.add_trace(go.Heatmap(
        z=z_values,
        x=GRADE_LANGS,
        y=labels,
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
        showscale=False,
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:+.2f}<extra></extra>",
    ), row=1, col=3)

    # Heatmap annotations
    for i, s in enumerate(school_list):
        for j, val in enumerate(s["gl_deltas"]):
            if not np.isnan(val):
                text_color = "white" if abs(val) > max_abs * 0.6 else "black"
                fig.add_annotation(
                    x=GRADE_LANGS[j], y=labels[i],
                    text=f"{val:+.1f}",
                    showarrow=False,
                    font=dict(size=9, color=text_color),
                    xref="x3", yref="y3",
                )

    # Layout
    fig.update_layout(
        height=max(400, 80 + n * 60),
        width=1050,
        title=_build_title(title, tp_from, tp_to, sort_by),
        margin=dict(l=20, r=20, t=80, b=40),
    )

    # Col 1 axes
    max_d = max(abs(d) for d in deltas)
    fig.update_xaxes(range=[-max_d * 0.3, max_d * 1.5], row=1, col=1)
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(labels)),
        tickfont=dict(size=10),
        row=1, col=1,
    )

    # Col 2 axes
    fig.update_xaxes(range=[0, max_assessed * 1.4], row=1, col=2)
    fig.update_yaxes(showticklabels=False, categoryorder="array",
                     categoryarray=list(reversed(labels)), row=1, col=2)

    # Col 3 axes
    fig.update_xaxes(side="top", tickfont=dict(size=10), row=1, col=3)
    fig.update_yaxes(showticklabels=False, categoryorder="array",
                     categoryarray=list(reversed(labels)), row=1, col=3)

    return fig


# Mockup 1: Sorted by delta (default) — small schools with big deltas rank high
fig1 = build_ranked_view(schools, "Top 10 — Sorted by Delta", sort_by="delta")
fig1.write_html(str(OUT / "11_ranked_with_count_by_delta.html"))

# Mockup 2: Sorted by weighted — large schools with solid deltas rank higher
fig2 = build_ranked_view(schools, "Top 10 — Sorted by Weighted", sort_by="weighted")
fig2.write_html(str(OUT / "11_ranked_with_count_by_weighted.html"))

print(f"Mockups written to {OUT}/")
print("  11_ranked_with_count_by_delta.html")
print("  11_ranked_with_count_by_weighted.html")
