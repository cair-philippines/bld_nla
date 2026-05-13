"""
Mockups for flow-aware proficiency shift visualizations.
Options 1 (cumulative distribution shift) and 4 (arrow flow diagram).

Run: python scripts/viz_mockups_v2.py
"""

import plotly.graph_objects as go
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "mockups"
OUT.mkdir(exist_ok=True)

PROFILES = ["Lower Emergent", "Higher Emergent", "Developing", "Transitioning", "Grade Level"]
COLORS = ["#DC143C", "#FF8C00", "#FFD700", "#9ACD32", "#228B22"]

# Sample data: % of learners at two timepoints
tp_a = {"label": "BoSY 2024-25", "values": [18, 25, 30, 17, 10]}
tp_b = {"label": "EoSY 2024-25", "values": [8, 15, 25, 28, 24]}


# =========================================================================
# Option 1: Cumulative Distribution Shift
# =========================================================================
# Cumulative % AT OR BELOW each level. Curve shifting DOWN = improvement.

cum_a = np.cumsum(tp_a["values"]).tolist()
cum_b = np.cumsum(tp_b["values"]).tolist()

fig1 = go.Figure()

# Fill between the two curves to show the shift
fig1.add_trace(go.Scatter(
    x=PROFILES,
    y=cum_a,
    mode="lines+markers+text",
    name=tp_a["label"],
    line=dict(color="#4A90D9", width=3),
    marker=dict(size=10),
    text=[f"{v}%" for v in cum_a],
    textposition="top center",
    textfont=dict(size=12),
))

fig1.add_trace(go.Scatter(
    x=PROFILES,
    y=cum_b,
    mode="lines+markers+text",
    name=tp_b["label"],
    line=dict(color="#E74C3C", width=3),
    marker=dict(size=10),
    text=[f"{v}%" for v in cum_b],
    textposition="bottom center",
    textfont=dict(size=12),
))

# Shade the gap between curves
fig1.add_trace(go.Scatter(
    x=PROFILES + PROFILES[::-1],
    y=cum_a + cum_b[::-1],
    fill="toself",
    fillcolor="rgba(34, 139, 34, 0.15)",
    line=dict(width=0),
    showlegend=False,
    hoverinfo="skip",
))

# Annotate the gap at each level
for i, profile in enumerate(PROFILES):
    gap = cum_a[i] - cum_b[i]
    if gap != 0:
        mid_y = (cum_a[i] + cum_b[i]) / 2
        fig1.add_annotation(
            x=profile, y=mid_y,
            text=f"<b>{gap:+d}pp</b>",
            showarrow=False,
            font=dict(size=11, color="#228B22" if gap > 0 else "#DC143C"),
            bgcolor="rgba(255,255,255,0.8)",
        )

fig1.update_layout(
    title=(
        "<b>Option 1: Cumulative Distribution Shift</b>"
        "<br><span style='font-size:13px;color:#666'>"
        "% of learners at or below each level. "
        "Green gap = learners shifted UP the proficiency ladder.</span>"
    ),
    height=450,
    width=750,
    xaxis=dict(title="Reading Profile (low → high)"),
    yaxis=dict(title="Cumulative % of Learners", range=[0, 105]),
    legend=dict(orientation="h", y=-0.15, xanchor="center", x=0.5),
    margin=dict(l=60, r=20, t=90, b=60),
)

fig1.write_html(str(OUT / "5_cumulative_shift.html"))


# =========================================================================
# Option 4: Arrow Flow Diagram
# =========================================================================
# Horizontal axis = proficiency levels as ordinal positions.
# Arrows between adjacent levels show net % point flow.

# Compute net flow between adjacent levels using cumulative differences.
# If cum_a[i] > cum_b[i], net flow went UP past level i.
net_flows = []
for i in range(len(PROFILES) - 1):
    # Net upward flow past the boundary between level i and i+1
    flow = cum_a[i] - cum_b[i]  # positive = net upward
    net_flows.append(flow)

x_positions = list(range(len(PROFILES)))

fig4 = go.Figure()

# Draw profile level markers
fig4.add_trace(go.Scatter(
    x=x_positions,
    y=[0] * len(PROFILES),
    mode="markers+text",
    marker=dict(size=30, color=COLORS, line=dict(width=2, color="#333")),
    text=PROFILES,
    textposition="bottom center",
    textfont=dict(size=11),
    showlegend=False,
    hovertemplate="%{text}<br>Start: %{customdata[0]}%<br>End: %{customdata[1]}%<extra></extra>",
    customdata=list(zip(tp_a["values"], tp_b["values"])),
))

# Show start/end percentages inside markers
for i in range(len(PROFILES)):
    fig4.add_annotation(
        x=x_positions[i], y=0,
        text=f"<b>{tp_a['values'][i]}→{tp_b['values'][i]}</b>",
        showarrow=False,
        font=dict(size=9, color="white"),
        bgcolor=COLORS[i],
        borderpad=3,
        opacity=0.9,
        yshift=25,
    )

# Draw flow arrows between adjacent levels
for i, flow in enumerate(net_flows):
    if flow == 0:
        continue

    x_start = x_positions[i] + 0.15
    x_end = x_positions[i + 1] - 0.15

    if flow > 0:
        # Net upward (left to right)
        color = "#228B22"
        label = f"+{flow}pp"
        y_offset = 0.4
    else:
        # Net downward (right to left)
        color = "#DC143C"
        label = f"{flow}pp"
        x_start, x_end = x_end, x_start
        y_offset = -0.4

    # Arrow
    fig4.add_annotation(
        x=x_end, y=y_offset,
        ax=x_start, ay=y_offset,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.5,
        arrowwidth=3,
        arrowcolor=color,
    )

    # Flow label
    mid_x = (x_positions[i] + x_positions[i + 1]) / 2
    fig4.add_annotation(
        x=mid_x, y=y_offset,
        text=f"<b>{label}</b>",
        showarrow=False,
        font=dict(size=13, color=color),
        yshift=20 if flow > 0 else -20,
        bgcolor="rgba(255,255,255,0.85)",
    )

fig4.update_layout(
    title=(
        "<b>Option 4: Arrow Flow Diagram</b>"
        f"<br><span style='font-size:13px;color:#666'>"
        f"{tp_a['label']} → {tp_b['label']} · "
        f"Green arrows = net upward flow between adjacent levels</span>"
    ),
    height=350,
    width=800,
    xaxis=dict(
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        range=[-0.5, len(PROFILES) - 0.5],
    ),
    yaxis=dict(
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        range=[-1.2, 1.2],
    ),
    margin=dict(l=20, r=20, t=90, b=60),
    showlegend=False,
    plot_bgcolor="white",
)

fig4.write_html(str(OUT / "6_arrow_flow.html"))

print(f"Mockups written to {OUT}/")
print("  5_cumulative_shift.html")
print("  6_arrow_flow.html")
