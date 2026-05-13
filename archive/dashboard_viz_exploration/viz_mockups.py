"""
Quick mockups of 4 candidate visualizations for proficiency shift.
Uses sample data for a hypothetical school.

Run: python scripts/viz_mockups.py
Opens HTML files in dashboard/scripts/mockups/
"""

import plotly.graph_objects as go
from pathlib import Path

OUT = Path(__file__).parent / "mockups"
OUT.mkdir(exist_ok=True)

# Sample data: % of learners per proficiency level at two timepoints
PROFILES = ["Lower Emergent", "Higher Emergent", "Developing", "Transitioning", "Grade Level"]
COLORS = ["#DC143C", "#FF8C00", "#FFD700", "#9ACD32", "#228B22"]

# BoSY 2024-25 -> EoSY 2024-25 (learning period — expect upward shift)
tp_a = {"label": "BoSY 2024-25", "values": [18, 25, 30, 17, 10]}
tp_b = {"label": "EoSY 2024-25", "values": [8, 15, 25, 28, 24]}

deltas = [b - a for a, b in zip(tp_a["values"], tp_b["values"])]


# =========================================================================
# 1. Slope Chart
# =========================================================================

fig1 = go.Figure()

for i, profile in enumerate(PROFILES):
    fig1.add_trace(go.Scatter(
        x=[tp_a["label"], tp_b["label"]],
        y=[tp_a["values"][i], tp_b["values"][i]],
        mode="lines+markers+text",
        name=profile,
        line=dict(color=COLORS[i], width=3),
        marker=dict(size=10),
        text=[f"{tp_a['values'][i]}%", f"{tp_b['values'][i]}%"],
        textposition=["middle left", "middle right"],
        textfont=dict(size=12),
    ))

fig1.update_layout(
    title="<b>Option 1: Slope Chart</b> — Profile share shift between timepoints",
    height=450,
    width=700,
    xaxis=dict(title=None),
    yaxis=dict(title="% of Learners", range=[0, 40]),
    legend=dict(orientation="h", y=-0.15, xanchor="center", x=0.5),
    margin=dict(l=60, r=120, t=60, b=60),
)

fig1.write_html(str(OUT / "1_slope_chart.html"))


# =========================================================================
# 2. Dumbbell Chart
# =========================================================================

fig2 = go.Figure()

for i, profile in enumerate(PROFILES):
    y_pos = profile
    a_val = tp_a["values"][i]
    b_val = tp_b["values"][i]

    # Connecting line
    fig2.add_trace(go.Scatter(
        x=[a_val, b_val],
        y=[y_pos, y_pos],
        mode="lines",
        line=dict(color="#888888", width=2),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Start dot
    fig2.add_trace(go.Scatter(
        x=[a_val],
        y=[y_pos],
        mode="markers+text",
        marker=dict(size=14, color="#4A90D9"),
        name=tp_a["label"],
        legendgroup="start",
        showlegend=(i == 0),
        text=[f"{a_val}%"],
        textposition="middle left" if b_val > a_val else "middle right",
        textfont=dict(size=11),
        hovertemplate=f"{profile}<br>{tp_a['label']}: {a_val}%<extra></extra>",
    ))

    # End dot
    fig2.add_trace(go.Scatter(
        x=[b_val],
        y=[y_pos],
        mode="markers+text",
        marker=dict(size=14, color="#E74C3C", symbol="diamond"),
        name=tp_b["label"],
        legendgroup="end",
        showlegend=(i == 0),
        text=[f"{b_val}%"],
        textposition="middle right" if b_val > a_val else "middle left",
        textfont=dict(size=11),
        hovertemplate=f"{profile}<br>{tp_b['label']}: {b_val}%<extra></extra>",
    ))

    # Arrow annotation
    arrow_color = "#228B22" if b_val > a_val else "#DC143C"
    diff = b_val - a_val
    fig2.add_annotation(
        x=b_val, y=y_pos,
        ax=a_val, ay=y_pos,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True,
        arrowhead=2, arrowsize=1.5, arrowwidth=1.5,
        arrowcolor=arrow_color,
        opacity=0.4,
    )

fig2.update_layout(
    title="<b>Option 2: Dumbbell Chart</b> — Start vs end per profile",
    height=400,
    width=700,
    xaxis=dict(title="% of Learners", range=[0, 40]),
    yaxis=dict(
        title=None,
        categoryorder="array",
        categoryarray=list(reversed(PROFILES)),
    ),
    legend=dict(orientation="h", y=-0.2, xanchor="center", x=0.5),
    margin=dict(l=0, r=40, t=60, b=60),
)

fig2.write_html(str(OUT / "2_dumbbell_chart.html"))


# =========================================================================
# 3. Waterfall Chart
# =========================================================================

fig3 = go.Figure(go.Waterfall(
    orientation="v",
    x=PROFILES,
    y=deltas,
    text=[f"{d:+d}pp" for d in deltas],
    textposition="outside",
    connector=dict(line=dict(color="#888888", width=1, dash="dot")),
    increasing=dict(marker=dict(color="#228B22")),
    decreasing=dict(marker=dict(color="#DC143C")),
    totals=dict(marker=dict(color="#4A90D9")),
))

fig3.add_hline(y=0, line_color="#333333", line_width=1)

fig3.update_layout(
    title=(
        f"<b>Option 3: Waterfall Chart</b> — Percentage point change per profile"
        f"<br><span style='font-size:13px;color:#666'>"
        f"{tp_a['label']} → {tp_b['label']}</span>"
    ),
    height=400,
    width=700,
    yaxis=dict(title="Change (percentage points)", range=[-15, 20]),
    xaxis=dict(title=None),
    margin=dict(l=60, r=20, t=80, b=20),
    showlegend=False,
)

fig3.write_html(str(OUT / "3_waterfall_chart.html"))


# =========================================================================
# 4. Diverging Bar Chart
# =========================================================================

fig4 = go.Figure()

bar_colors = ["#228B22" if d > 0 else "#DC143C" for d in deltas]

fig4.add_trace(go.Bar(
    y=PROFILES,
    x=deltas,
    orientation="h",
    marker_color=bar_colors,
    text=[f"{d:+d}pp" for d in deltas],
    textposition="outside",
    textfont=dict(size=13),
))

fig4.add_vline(x=0, line_color="#333333", line_width=1.5)

fig4.update_layout(
    title=(
        f"<b>Option 4: Diverging Bar Chart</b> — Net shift per profile"
        f"<br><span style='font-size:13px;color:#666'>"
        f"{tp_a['label']} → {tp_b['label']}</span>"
    ),
    height=350,
    width=700,
    xaxis=dict(title="Change (percentage points)"),
    yaxis=dict(
        title=None,
        categoryorder="array",
        categoryarray=list(reversed(PROFILES)),
    ),
    margin=dict(l=0, r=40, t=80, b=40),
    showlegend=False,
)

fig4.write_html(str(OUT / "4_diverging_bar.html"))


print(f"Mockups written to {OUT}/")
print("  1_slope_chart.html")
print("  2_dumbbell_chart.html")
print("  3_waterfall_chart.html")
print("  4_diverging_bar.html")
