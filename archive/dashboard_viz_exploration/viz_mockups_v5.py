"""
Mockups for the Ranking/Leaderboard view.
Sections: Top N, Bottom N, with compact distribution shift indicators.

Run: python scripts/viz_mockups_v5.py
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "mockups"
OUT.mkdir(exist_ok=True)

PROFILES = ["Lower Emergent", "Higher Emergent", "Developing", "Transitioning", "Grade Level"]
PROFILE_COLORS = ["#DC143C", "#FF8C00", "#FFD700", "#9ACD32", "#228B22"]

# --- Sample data: 10 schools with progress deltas and distributions ---

schools = [
    {"name": "Sunrise Elementary School", "id": 101, "delta": +1.42,
     "from": [30, 25, 25, 12, 8], "to": [10, 15, 25, 28, 22]},
    {"name": "Mountain View Central School", "id": 102, "delta": +1.18,
     "from": [28, 27, 24, 13, 8], "to": [12, 16, 24, 27, 21]},
    {"name": "Lakeside Integrated School", "id": 103, "delta": +0.95,
     "from": [22, 24, 28, 16, 10], "to": [10, 18, 26, 26, 20]},
    {"name": "Riverside Elementary School", "id": 104, "delta": +0.87,
     "from": [25, 23, 27, 15, 10], "to": [14, 17, 24, 25, 20]},
    {"name": "Valley Elem. School", "id": 105, "delta": +0.82,
     "from": [20, 22, 30, 18, 10], "to": [12, 16, 27, 26, 19]},
    {"name": "Hilltop Primary School", "id": 201, "delta": -0.75,
     "from": [12, 18, 28, 24, 18], "to": [18, 22, 28, 20, 12]},
    {"name": "Seaside Elementary School", "id": 202, "delta": -0.88,
     "from": [10, 15, 26, 28, 21], "to": [18, 20, 26, 22, 14]},
    {"name": "Greenfield Central School", "id": 203, "delta": -1.05,
     "from": [8, 14, 25, 30, 23], "to": [16, 22, 26, 22, 14]},
    {"name": "Eastwood Integrated School", "id": 204, "delta": -1.22,
     "from": [10, 16, 24, 28, 22], "to": [20, 24, 26, 18, 12]},
    {"name": "Westpark Elementary School", "id": 205, "delta": -1.45,
     "from": [8, 12, 22, 32, 26], "to": [22, 24, 24, 18, 12]},
]

tp_from = "BoSY 2024-25"
tp_to = "EoSY 2024-25"

top5 = sorted(schools, key=lambda s: s["delta"], reverse=True)[:5]
bot5 = sorted(schools, key=lambda s: s["delta"])[:5]


# =========================================================================
# Option A: Table + mini stacked bars
# =========================================================================

def build_table_with_mini_bars(school_list, title, is_top=True):
    """Ranked table with inline mini stacked bars showing from/to distributions."""

    fig = make_subplots(
        rows=len(school_list), cols=3,
        column_widths=[0.35, 0.35, 0.30],
        horizontal_spacing=0.04,
        vertical_spacing=0.02,
        subplot_titles=(
            ["From Distribution", "To Distribution", "Delta"] if True else []
        ),
    )

    for rank, school in enumerate(school_list):
        row = rank + 1

        # From distribution (mini stacked bar)
        for pi, profile in enumerate(PROFILES):
            fig.add_trace(go.Bar(
                y=[""],
                x=[school["from"][pi]],
                orientation="h",
                marker_color=PROFILE_COLORS[pi],
                showlegend=(rank == 0),
                legendgroup=profile,
                name=profile,
                hovertemplate=f"{profile}: {school['from'][pi]}%<extra></extra>",
            ), row=row, col=1)

        # To distribution (mini stacked bar)
        for pi, profile in enumerate(PROFILES):
            fig.add_trace(go.Bar(
                y=[""],
                x=[school["to"][pi]],
                orientation="h",
                marker_color=PROFILE_COLORS[pi],
                showlegend=False,
                legendgroup=profile,
                hovertemplate=f"{profile}: {school['to'][pi]}%<extra></extra>",
            ), row=row, col=2)

        # Delta indicator bar
        color = "#228B22" if school["delta"] > 0 else "#DC143C"
        fig.add_trace(go.Bar(
            y=[""],
            x=[school["delta"]],
            orientation="h",
            marker_color=color,
            text=[f"{school['delta']:+.2f}"],
            textposition="outside",
            textfont=dict(size=12, color=color),
            showlegend=False,
            hovertemplate=f"Delta: {school['delta']:+.2f}<extra></extra>",
        ), row=row, col=3)

        # School name as y-axis label
        fig.update_yaxes(
            ticktext=[f"{rank+1}. {school['name']}"],
            tickvals=[""],
            tickfont=dict(size=11),
            row=row, col=1,
        )
        fig.update_yaxes(showticklabels=False, row=row, col=2)
        fig.update_yaxes(showticklabels=False, row=row, col=3)

        # Hide x-axis ticks on stacked bars (except bottom row)
        for c in [1, 2, 3]:
            fig.update_xaxes(
                showticklabels=(row == len(school_list)),
                row=row, col=c,
            )

    # Set barmode and layout
    fig.update_layout(
        barmode="stack",
        height=80 + len(school_list) * 65,
        width=950,
        title=f"<b>{title}</b><br><span style='font-size:13px;color:#666'>{tp_from} → {tp_to}</span>",
        margin=dict(l=200, r=60, t=80, b=30),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.05,
            xanchor="center",
            x=0.5,
        ),
    )

    # x-axis ranges
    for row in range(1, len(school_list) + 1):
        fig.update_xaxes(range=[0, 100], row=row, col=1)
        fig.update_xaxes(range=[0, 100], row=row, col=2)
        max_d = max(abs(s["delta"]) for s in school_list)
        fig.update_xaxes(range=[-max_d * 1.4, max_d * 1.4], row=row, col=3)

    return fig


fig_a_top = build_table_with_mini_bars(top5, "Option A: Top 5 — Table + Mini Bars", is_top=True)
fig_a_top.write_html(str(OUT / "9a_table_mini_bars_top.html"))

fig_a_bot = build_table_with_mini_bars(bot5, "Option A: Bottom 5 — Table + Mini Bars", is_top=False)
fig_a_bot.write_html(str(OUT / "9a_table_mini_bars_bottom.html"))


# =========================================================================
# Option B: Ranked bar chart + mini cumulative shift sparklines
# =========================================================================

def build_ranked_with_sparklines(school_list, title, is_top=True):
    """Horizontal bar chart of deltas with mini cumulative shift insets."""

    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.5, 0.5],
        horizontal_spacing=0.08,
        subplot_titles=["Progress Score Delta", "Cumulative Distribution Shift"],
    )

    school_names = [f"{i+1}. {s['name']}" for i, s in enumerate(school_list)]
    deltas = [s["delta"] for s in school_list]
    bar_colors = ["#228B22" if d > 0 else "#DC143C" for d in deltas]

    # Left: ranked horizontal bars
    fig.add_trace(go.Bar(
        y=school_names,
        x=deltas,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{d:+.2f}" for d in deltas],
        textposition="outside",
        textfont=dict(size=11),
        showlegend=False,
        hovertemplate="%{y}<br>Delta: %{x:+.2f}<extra></extra>",
    ), row=1, col=1)

    fig.add_vline(x=0, line_color="#333", line_width=1, row=1, col=1)

    # Right: overlaid mini cumulative curves for all schools
    for i, school in enumerate(school_list):
        cum_from = np.cumsum(school["from"]).tolist()
        cum_to = np.cumsum(school["to"]).tolist()
        color = bar_colors[i]
        opacity = 1.0 - (i * 0.15)

        fig.add_trace(go.Scatter(
            x=PROFILES,
            y=cum_from,
            mode="lines",
            line=dict(color="#4A90D9", width=1.5, dash="dot"),
            opacity=opacity,
            showlegend=(i == 0),
            legendgroup="from",
            name=tp_from,
            hovertemplate=f"{school['name']}<br>" + "%{x}: %{y:.0f}%<extra>From</extra>",
        ), row=1, col=2)

        fig.add_trace(go.Scatter(
            x=PROFILES,
            y=cum_to,
            mode="lines",
            line=dict(color="#E74C3C", width=1.5),
            opacity=opacity,
            showlegend=(i == 0),
            legendgroup="to",
            name=tp_to,
            hovertemplate=f"{school['name']}<br>" + "%{x}: %{y:.0f}%<extra>To</extra>",
        ), row=1, col=2)

    fig.update_layout(
        height=400,
        width=950,
        title=f"<b>{title}</b><br><span style='font-size:13px;color:#666'>{tp_from} → {tp_to}</span>",
        margin=dict(l=20, r=20, t=80, b=60),
        legend=dict(orientation="h", y=-0.15, xanchor="center", x=0.75),
    )

    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(school_names)),
        tickfont=dict(size=10),
        row=1, col=1,
    )
    fig.update_yaxes(title="Cumulative %", range=[0, 105], row=1, col=2)
    fig.update_xaxes(tickangle=-30, tickfont=dict(size=9), row=1, col=2)

    max_d = max(abs(d) for d in deltas)
    fig.update_xaxes(range=[-max_d * 1.4, max_d * 1.4], row=1, col=1)

    return fig


fig_b_top = build_ranked_with_sparklines(top5, "Option B: Top 5 — Bars + Cumulative Overlay", is_top=True)
fig_b_top.write_html(str(OUT / "9b_ranked_sparklines_top.html"))

fig_b_bot = build_ranked_with_sparklines(bot5, "Option B: Bottom 5 — Bars + Cumulative Overlay", is_top=False)
fig_b_bot.write_html(str(OUT / "9b_ranked_sparklines_bottom.html"))


# =========================================================================
# Option C: Compact card-style — delta bar + before/after stacked bar per school
# =========================================================================

def build_compact_cards(school_list, title, is_top=True):
    """Each school gets a row with: delta value, from bar, to bar, arrow between."""

    n = len(school_list)

    fig = make_subplots(
        rows=n, cols=2,
        column_widths=[0.15, 0.85],
        horizontal_spacing=0.02,
        vertical_spacing=0.06,
    )

    for rank, school in enumerate(school_list):
        row = rank + 1
        color = "#228B22" if school["delta"] > 0 else "#DC143C"

        # Col 1: delta value as a single bar
        fig.add_trace(go.Bar(
            y=[school["name"]],
            x=[school["delta"]],
            orientation="h",
            marker_color=color,
            text=[f"{school['delta']:+.2f}"],
            textposition="outside",
            textfont=dict(size=12, color=color),
            showlegend=False,
        ), row=row, col=1)

        # Col 2: two stacked bars (From on top, To on bottom)
        for pi, profile in enumerate(PROFILES):
            # From bar
            fig.add_trace(go.Bar(
                y=[f"{tp_from}"],
                x=[school["from"][pi]],
                orientation="h",
                marker_color=PROFILE_COLORS[pi],
                showlegend=(rank == 0),
                legendgroup=profile,
                name=profile,
                hovertemplate=f"{profile}: {school['from'][pi]}%<extra>{tp_from}</extra>",
            ), row=row, col=2)
            # To bar
            fig.add_trace(go.Bar(
                y=[f"{tp_to}"],
                x=[school["to"][pi]],
                orientation="h",
                marker_color=PROFILE_COLORS[pi],
                showlegend=False,
                legendgroup=profile,
                hovertemplate=f"{profile}: {school['to'][pi]}%<extra>{tp_to}</extra>",
            ), row=row, col=2)

        # School name annotation
        fig.add_annotation(
            text=f"<b>{rank+1}. {school['name']}</b>",
            xref=f"x{(row-1)*2+2 if row > 1 else 2} domain",
            yref=f"y{(row-1)*2+2 if row > 1 else 2} domain",
            x=0, y=1.25,
            showarrow=False,
            font=dict(size=11),
            xanchor="left",
        )

        fig.update_xaxes(range=[0, 100], showticklabels=(row == n), row=row, col=2)
        max_d = max(abs(s["delta"]) for s in school_list)
        fig.update_xaxes(
            range=[-max_d * 1.5, max_d * 1.5],
            showticklabels=False,
            row=row, col=1,
        )
        fig.update_yaxes(tickfont=dict(size=9), row=row, col=2)
        fig.update_yaxes(showticklabels=False, row=row, col=1)

    fig.update_layout(
        barmode="stack",
        height=100 + n * 120,
        width=950,
        title=f"<b>{title}</b><br><span style='font-size:13px;color:#666'>{tp_from} → {tp_to}</span>",
        margin=dict(l=20, r=20, t=80, b=40),
        legend=dict(orientation="h", y=-0.03, xanchor="center", x=0.55),
    )

    return fig


fig_c_top = build_compact_cards(top5, "Option C: Top 5 — Delta + Before/After Bars", is_top=True)
fig_c_top.write_html(str(OUT / "9c_compact_cards_top.html"))

fig_c_bot = build_compact_cards(bot5, "Option C: Bottom 5 — Delta + Before/After Bars", is_top=False)
fig_c_bot.write_html(str(OUT / "9c_compact_cards_bottom.html"))


print(f"Mockups written to {OUT}/")
print("  9a_table_mini_bars_top.html / bottom")
print("  9b_ranked_sparklines_top.html / bottom")
print("  9c_compact_cards_top.html / bottom")
