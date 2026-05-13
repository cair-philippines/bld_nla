"""
Mockup: Regional / Division summary section above school ranking.

Two scenarios:
  1. Region = "All" → regional bars + top N division bars (side by side)
  2. Region = specific → division bars within that region only

Run: python scripts/viz_mockups_v8.py
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "mockups"
OUT.mkdir(exist_ok=True)

tp_from = "BoSY 2024-25"
tp_to = "EoSY 2024-25"

# --- Sample data: regions ---------------------------------------------------

regions = [
    {"name": "Region VII", "delta": +0.92, "assessed": 48_320},
    {"name": "CAR", "delta": +0.88, "assessed": 12_450},
    {"name": "Region IV-A", "delta": +0.85, "assessed": 67_200},
    {"name": "NCR", "delta": +0.82, "assessed": 95_100},
    {"name": "Region XI", "delta": +0.79, "assessed": 31_800},
    {"name": "Region VI", "delta": +0.76, "assessed": 42_600},
    {"name": "Region X", "delta": +0.74, "assessed": 28_900},
    {"name": "Region XII", "delta": +0.71, "assessed": 19_500},
    {"name": "Region I", "delta": +0.68, "assessed": 35_700},
    {"name": "NIR", "delta": +0.65, "assessed": 15_200},
]

# --- Sample data: divisions (all regions) ------------------------------------

divisions_all = [
    {"name": "Cebu City", "region": "Region VII", "delta": +1.12, "assessed": 14_200},
    {"name": "Baguio City", "region": "CAR", "delta": +1.05, "assessed": 5_800},
    {"name": "Laguna", "region": "Region IV-A", "delta": +0.98, "assessed": 18_400},
    {"name": "Manila", "region": "NCR", "delta": +0.95, "assessed": 22_300},
    {"name": "Davao City", "region": "Region XI", "delta": +0.91, "assessed": 12_100},
    {"name": "Iloilo City", "region": "Region VI", "delta": +0.88, "assessed": 9_700},
    {"name": "Dumaguete City", "region": "Region VII", "delta": +0.86, "assessed": 6_300},
    {"name": "Bukidnon", "region": "Region X", "delta": +0.83, "assessed": 8_900},
    {"name": "Zamboanga City", "region": "Region IX", "delta": +0.80, "assessed": 11_500},
    {"name": "Camarines Sur", "region": "Region V", "delta": +0.77, "assessed": 13_200},
]

# --- Sample data: divisions within Region VII --------------------------------

divisions_r7 = [
    {"name": "Cebu City", "delta": +1.12, "assessed": 14_200},
    {"name": "Dumaguete City", "delta": +0.86, "assessed": 6_300},
    {"name": "Cebu Province", "delta": +0.81, "assessed": 11_800},
    {"name": "Mandaue City", "delta": +0.78, "assessed": 4_500},
    {"name": "Lapu-Lapu City", "delta": +0.74, "assessed": 5_100},
    {"name": "Bohol", "delta": +0.70, "assessed": 8_200},
    {"name": "Siquijor", "delta": +0.62, "assessed": 1_900},
    {"name": "Talisay City", "delta": +0.58, "assessed": 3_400},
]


def _bar_color(d):
    return "#228B22" if d > 0 else "#DC143C"


def build_summary_all_regions(regions_list, divisions_list, n_div=5, sort_by="delta"):
    """
    Scenario 1: Region = "All"
    Two side-by-side charts: ranked regions (left) + top N divisions (right)
    """
    sort_label_map = {"delta": "Delta", "weighted": "Weighted", "impact": "Impact"}

    # Sort regions
    if sort_by == "impact":
        regions_sorted = sorted(regions_list, key=lambda r: r["delta"] * r["assessed"], reverse=True)
    elif sort_by == "weighted":
        regions_sorted = sorted(regions_list, key=lambda r: r["delta"] * np.log1p(r["assessed"]), reverse=True)
    else:
        regions_sorted = sorted(regions_list, key=lambda r: r["delta"], reverse=True)

    # Sort divisions, take top N
    if sort_by == "impact":
        divs_sorted = sorted(divisions_list, key=lambda d: d["delta"] * d["assessed"], reverse=True)[:n_div]
    elif sort_by == "weighted":
        divs_sorted = sorted(divisions_list, key=lambda d: d["delta"] * np.log1p(d["assessed"]), reverse=True)[:n_div]
    else:
        divs_sorted = sorted(divisions_list, key=lambda d: d["delta"], reverse=True)[:n_div]

    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.5, 0.5],
        horizontal_spacing=0.12,
    )

    # --- Left: Regions ---
    reg_labels = [f"{r['name']}  ({r['assessed']:,})" for r in regions_sorted]
    reg_deltas = [r["delta"] for r in regions_sorted]

    fig.add_trace(go.Bar(
        y=reg_labels,
        x=reg_deltas,
        orientation="h",
        marker_color=[_bar_color(d) for d in reg_deltas],
        text=[f"{d:+.2f}" for d in reg_deltas],
        textposition="outside",
        textfont=dict(size=11),
        showlegend=False,
        cliponaxis=False,
    ), row=1, col=1)

    fig.add_vline(x=0, line_color="#333", line_width=1, row=1, col=1)

    # --- Right: Top N Divisions ---
    div_labels = [f"{d['name']}  ({d['assessed']:,})" for d in divs_sorted]
    div_deltas = [d["delta"] for d in divs_sorted]

    fig.add_trace(go.Bar(
        y=div_labels,
        x=div_deltas,
        orientation="h",
        marker_color=[_bar_color(d) for d in div_deltas],
        text=[f"{d:+.2f}" for d in div_deltas],
        textposition="outside",
        textfont=dict(size=11),
        showlegend=False,
        cliponaxis=False,
    ), row=1, col=2)

    fig.add_vline(x=0, line_color="#333", line_width=1, row=1, col=2)

    n_rows = max(len(regions_sorted), len(divs_sorted))
    fig.update_layout(
        height=max(300, 60 + n_rows * 40),
        width=1050,
        title=(
            f"<b>Regional & Division Summary</b>"
            f"<br><span style='font-size:13px;color:#666'>"
            f"{tp_from} → {tp_to} · Rank by: {sort_label_map[sort_by]}"
            f" · Assessed count in parentheses</span>"
        ),
        margin=dict(l=20, r=20, t=80, b=40),
    )

    # Column headers
    fig.add_annotation(
        text="<b>Regions</b>",
        xref="x domain", yref="paper", x=0.5, y=1.08,
        showarrow=False, font=dict(size=14),
    )
    fig.add_annotation(
        text=f"<b>Top {len(divs_sorted)} Divisions</b>",
        xref="x2 domain", yref="paper", x=0.5, y=1.08,
        showarrow=False, font=dict(size=14),
    )

    # Axes
    max_d = max(abs(d) for d in reg_deltas + div_deltas)
    for col in [1, 2]:
        fig.update_xaxes(range=[-max_d * 0.3, max_d * 1.5], row=1, col=col)

    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(reg_labels)),
        tickfont=dict(size=11),
        row=1, col=1,
    )
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(div_labels)),
        tickfont=dict(size=11),
        row=1, col=2,
    )

    return fig


def build_summary_single_region(region_name, divisions_list, sort_by="delta"):
    """
    Scenario 2: Region = specific value
    Single chart: ranked divisions within that region
    """
    sort_label_map = {"delta": "Delta", "weighted": "Weighted", "impact": "Impact"}

    if sort_by == "impact":
        divs_sorted = sorted(divisions_list, key=lambda d: d["delta"] * d["assessed"], reverse=True)
    elif sort_by == "weighted":
        divs_sorted = sorted(divisions_list, key=lambda d: d["delta"] * np.log1p(d["assessed"]), reverse=True)
    else:
        divs_sorted = sorted(divisions_list, key=lambda d: d["delta"], reverse=True)

    labels = [f"{d['name']}  ({d['assessed']:,})" for d in divs_sorted]
    deltas = [d["delta"] for d in divs_sorted]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=labels,
        x=deltas,
        orientation="h",
        marker_color=[_bar_color(d) for d in deltas],
        text=[f"{d:+.2f}" for d in deltas],
        textposition="outside",
        textfont=dict(size=11),
        showlegend=False,
        cliponaxis=False,
    ))

    fig.add_vline(x=0, line_color="#333", line_width=1)

    max_d = max(abs(d) for d in deltas)
    fig.update_xaxes(range=[-max_d * 0.3, max_d * 1.5])
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(labels)),
        tickfont=dict(size=11),
    )

    fig.update_layout(
        height=max(250, 60 + len(divs_sorted) * 40),
        width=700,
        title=(
            f"<b>Divisions in {region_name}</b>"
            f"<br><span style='font-size:13px;color:#666'>"
            f"{tp_from} → {tp_to} · Rank by: {sort_label_map[sort_by]}"
            f" · Assessed count in parentheses</span>"
        ),
        margin=dict(l=20, r=20, t=80, b=40),
    )

    return fig


# --- Generate mockups --------------------------------------------------------

# Scenario 1: Region = "All", sorted by delta
fig1 = build_summary_all_regions(regions, divisions_all, n_div=5, sort_by="delta")
fig1.write_html(str(OUT / "12a_summary_all_regions_delta.html"))

# Scenario 1: Region = "All", sorted by impact
fig2 = build_summary_all_regions(regions, divisions_all, n_div=5, sort_by="impact")
fig2.write_html(str(OUT / "12b_summary_all_regions_impact.html"))

# Scenario 2: Region = "Region VII", sorted by delta
fig3 = build_summary_single_region("Region VII", divisions_r7, sort_by="delta")
fig3.write_html(str(OUT / "12c_summary_region_vii_delta.html"))

# Scenario 2: Region = "Region VII", sorted by impact
fig4 = build_summary_single_region("Region VII", divisions_r7, sort_by="impact")
fig4.write_html(str(OUT / "12d_summary_region_vii_impact.html"))

print(f"Mockups written to {OUT}/")
print("  12a_summary_all_regions_delta.html   — Region=All, Delta")
print("  12b_summary_all_regions_impact.html  — Region=All, Impact")
print("  12c_summary_region_vii_delta.html    — Region VII, Delta")
print("  12d_summary_region_vii_impact.html   — Region VII, Impact")
