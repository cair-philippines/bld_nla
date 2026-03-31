"""
CRLA Ranked View

Shows top/bottom N schools by ordinal progress score delta between
two user-selected timepoints, with a grade-language shift heatmap.

Target users: division/regional administrators.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TIMEPOINT_ORDER = ["BoSY 2024-25", "EoSY 2024-25", "BoSY 2025-26", "MoSY 2025-26", "EoSY 2025-26"]

GRADE_LANG_ORDER = ["G1", "G2 MT", "G2 Fil", "G3 MT", "G3 Fil", "G3 Eng"]

GRADE_LANG_ORDINAL_COLS = {
    "G1": "ordinal_G1",
    "G2 MT": "ordinal_G2_MT",
    "G2 Fil": "ordinal_G2_Fil",
    "G3 MT": "ordinal_G3_MT",
    "G3 Fil": "ordinal_G3_Fil",
    "G3 Eng": "ordinal_G3_Eng",
}

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data
def load_metadata():
    return pd.read_parquet(DATA_DIR / "school_metadata.parquet")


@st.cache_data
def load_ordinal():
    return pd.read_parquet(DATA_DIR / "school_ordinal.parquet")


@st.cache_data
def load_priority():
    path = DATA_DIR / "school_priority.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return None


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

metadata = load_metadata()
ordinal = load_ordinal()
priority_df = load_priority()

# Exclude national mean row
ordinal_schools = ordinal[ordinal["School ID"] != -1].copy()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.sidebar.title("School Rankings")
st.sidebar.markdown("---")

# Sort mode (prominent position)
_sort_options = ["Delta", "Weighted", "Priority"]
sort_mode = st.sidebar.radio(
    "Rank by",
    _sort_options,
    horizontal=True,
    help="**Delta**: ranks purely by score change. **Weighted**: dampens small-school noise (delta × log N). **Priority**: three-pillar composite (Need × Impact × Capacity Gap percentile ranks).",
)

st.sidebar.markdown("---")

# Region filter (optional)
regions = sorted(metadata["Region"].dropna().unique())
selected_region = st.sidebar.selectbox(
    "Region", options=["All"] + regions
)

filtered_meta = metadata.copy()
if selected_region != "All":
    filtered_meta = filtered_meta[filtered_meta["Region"] == selected_region]

# Division filter (optional)
divisions = sorted(filtered_meta["Division"].dropna().unique())
selected_division = st.sidebar.selectbox(
    "Division", options=["All"] + divisions
)

if selected_division != "All":
    filtered_meta = filtered_meta[filtered_meta["Division"] == selected_division]

# Restrict ordinal data to filtered schools
filtered_school_ids = set(filtered_meta["School ID"].values)
ordinal_filtered = ordinal_schools[
    ordinal_schools["School ID"].isin(filtered_school_ids)
]

st.sidebar.markdown("---")

# Build timepoint pairs from pre-computed priority segments.
# This ensures only valid, interpretable pairs appear in the dropdown.
if priority_df is not None:
    seg_pairs = priority_df[["tp_from", "tp_to"]].drop_duplicates()
    valid_pairs = [
        (row["tp_from"], row["tp_to"])
        for _, row in seg_pairs.iterrows()
        if row["tp_from"] in ordinal_filtered["timepoint_label"].values
        and row["tp_to"] in ordinal_filtered["timepoint_label"].values
    ]
    # Sort by TIMEPOINT_ORDER position of tp_from, then tp_to
    tp_order = {tp: i for i, tp in enumerate(TIMEPOINT_ORDER)}
    valid_pairs.sort(key=lambda p: (tp_order.get(p[0], 99), tp_order.get(p[1], 99)))
else:
    # Fallback: consecutive within-year pairs only
    available_tps = [
        tp for tp in TIMEPOINT_ORDER
        if tp in ordinal_filtered["timepoint_label"].values
    ]
    valid_pairs = [
        (available_tps[i], available_tps[i + 1])
        for i in range(len(available_tps) - 1)
    ]

if not valid_pairs:
    st.title("School Rankings")
    st.warning("Not enough timepoints available for the selected filters.")
    st.stop()

pair_labels = {
    f"{a} \u2192 {b}": (a, b) for a, b in valid_pairs
}

selected_pair = st.sidebar.selectbox("Period", options=list(pair_labels.keys()))
tp_from, tp_to = pair_labels[selected_pair]

st.sidebar.markdown("---")

# N and rank direction
n_schools = st.sidebar.number_input("N (number of schools)", min_value=1, max_value=50, value=10, step=1)
if sort_mode == "Priority":
    is_top = True
else:
    rank_direction = st.sidebar.radio("Show", ["Top (most improved)", "Bottom (most declined)"], horizontal=True)
    is_top = rank_direction.startswith("Top")

# ---------------------------------------------------------------------------
# Compute deltas
# ---------------------------------------------------------------------------

# Get ordinal data at both timepoints
from_data = ordinal_filtered[
    (ordinal_filtered["timepoint_label"] == tp_from) & ordinal_filtered["valid"]
].set_index("School ID")

to_data = ordinal_filtered[
    (ordinal_filtered["timepoint_label"] == tp_to) & ordinal_filtered["valid"]
].set_index("School ID")

# Schools present and valid at both timepoints
common_ids = from_data.index.intersection(to_data.index)

if len(common_ids) == 0:
    st.title("School Rankings")
    st.warning("No schools have valid data at both selected timepoints for the current filters.")
    st.stop()

# Compute overall and per-grade-lang deltas
delta_records = []
for sid in common_ids:
    # Use the average of assessed counts at both timepoints
    assessed_from = from_data.at[sid, "total_assessed"]
    assessed_to = to_data.at[sid, "total_assessed"]
    avg_assessed = np.nanmean([assessed_from, assessed_to])

    rec = {
        "School ID": sid,
        "delta_overall": to_data.at[sid, "ordinal_overall"] - from_data.at[sid, "ordinal_overall"],
        "total_assessed": avg_assessed,
        "pct_gl": to_data.at[sid, "pct_gl"] if "pct_gl" in to_data.columns else np.nan,
    }
    for gl, col in GRADE_LANG_ORDINAL_COLS.items():
        from_val = from_data.at[sid, col]
        to_val = to_data.at[sid, col]
        if pd.notna(from_val) and pd.notna(to_val):
            rec[f"delta_{gl}"] = to_val - from_val
        else:
            rec[f"delta_{gl}"] = np.nan
    delta_records.append(rec)

delta_df = pd.DataFrame(delta_records)

# Join school names
delta_df = delta_df.merge(
    metadata[["School ID", "School Name", "Division", "Region"]],
    on="School ID",
    how="left",
)

# Compute derived ranking scores
delta_df["weighted_score"] = delta_df["delta_overall"] * np.log1p(delta_df["total_assessed"])

# Join priority data if available
has_priority = False
if priority_df is not None and sort_mode == "Priority":
    # Match on School ID + timepoint pair
    seg_priority = priority_df[
        (priority_df["tp_from"] == tp_from) & (priority_df["tp_to"] == tp_to)
    ].copy()
    if len(seg_priority) > 0:
        priority_cols = ["School ID", "need_pctile", "impact_pctile",
                         "capacity_gap_pctile", "priority_score", "priority_pctile",
                         "lgu_name"]
        # Handle column rename (sef_per_school → sef_per_capita)
        for sef_col in ["sef_per_capita", "sef_per_school"]:
            if sef_col in seg_priority.columns:
                priority_cols.append(sef_col)
                break
        delta_df = delta_df.merge(
            seg_priority[priority_cols],
            on="School ID",
            how="left",
        )
        has_priority = True

# Rank
sort_col_map = {"Delta": "delta_overall", "Weighted": "weighted_score", "Priority": "priority_pctile"}
sort_col = sort_col_map[sort_mode]

if sort_mode == "Priority" and not has_priority:
    st.warning("Priority data not available for this timepoint pair. Falling back to Delta ranking.")
    sort_col = "delta_overall"

if sort_mode == "Priority" and has_priority:
    # Priority: always show highest-priority first (descending); top/bottom
    # flips between highest-priority and lowest-priority schools
    if is_top:
        ranked = delta_df.dropna(subset=["priority_pctile"]).nlargest(n_schools, sort_col)
    else:
        ranked = delta_df.dropna(subset=["priority_pctile"]).nsmallest(n_schools, sort_col)
else:
    if is_top:
        ranked = delta_df.nlargest(n_schools, sort_col)
    else:
        ranked = delta_df.nsmallest(n_schools, sort_col)

ranked = ranked.reset_index(drop=True)

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

direction_label = "Top" if is_top else "Bottom"
if sort_mode == "Priority" and has_priority:
    title_suffix = "by Priority" if is_top else "(Lowest Priority)"
else:
    title_suffix = "by Progress"
st.title(f"{direction_label} {len(ranked)} Schools {title_suffix}")

subtitle_parts = [f"{tp_from} \u2192 {tp_to}"]
if selected_region != "All":
    subtitle_parts.append(f"Region: {selected_region}")
if selected_division != "All":
    subtitle_parts.append(f"Division: {selected_division}")
subtitle_parts.append(f"{len(common_ids):,} schools with valid data at both timepoints")

st.markdown(" \u00b7 ".join(subtitle_parts))
st.markdown("---")

# ---------------------------------------------------------------------------
# Regional / Division Summary (collapsible)
# ---------------------------------------------------------------------------

def _build_region_boxplot(df, national_mean):
    """Boxplot of school-level deltas by region, sorted by median, with national mean line."""
    # Compute median per region for sorting
    region_medians = df.groupby("Region")["delta_overall"].median().sort_values()
    sorted_regions = region_medians.index.tolist()

    # School counts per region for axis labels
    region_counts = df.groupby("Region")["School ID"].count()
    x_labels = [f"{r}<br><span style='font-size:9px;color:#888'>n={region_counts[r]:,}</span>" for r in sorted_regions]

    fig = go.Figure()

    for i, region in enumerate(sorted_regions):
        region_data = df[df["Region"] == region]["delta_overall"]
        fig.add_trace(go.Box(
            y=region_data,
            name=x_labels[i],
            marker_color="#5B9BD5",
            line_color="#336699",
            boxmean=True,
            showlegend=False,
            hoverinfo="skip",
        ))

    # National mean line
    fig.add_hline(
        y=national_mean,
        line_dash="dash",
        line_color="#DC143C",
        line_width=1.5,
        annotation_text=f"National mean: {national_mean:+.2f}",
        annotation_position="top right",
        annotation_font=dict(size=11, color="#DC143C"),
    )

    fig.update_layout(
        height=450,
        margin=dict(l=60, r=20, t=20, b=20),
        yaxis_title="Overall Delta",
        hovermode=False,
    )
    fig.update_xaxes(tickfont=dict(size=10))

    return fig


def _build_division_boxplot(df, region_mean, min_width_per_div=180):
    """Boxplot of school-level deltas by division, sorted by median, with region mean line."""
    div_medians = df.groupby("Division")["delta_overall"].median().sort_values()
    sorted_divs = div_medians.index.tolist()
    div_counts = df.groupby("Division")["School ID"].count()

    x_labels = [
        f"{d}<br><span style='font-size:9px;color:#888'>n={div_counts[d]:,}</span>"
        for d in sorted_divs
    ]

    fig = go.Figure()
    for i, div in enumerate(sorted_divs):
        div_data = df[df["Division"] == div]["delta_overall"]
        fig.add_trace(go.Box(
            y=div_data,
            name=x_labels[i],
            marker_color="#5B9BD5",
            line_color="#336699",
            boxmean=True,
            showlegend=False,
            hoverinfo="skip",
        ))

    # Zero line for context when scrolling
    fig.add_hline(y=0, line_color="#333", line_width=1, line_dash="dot")

    # Region mean line
    fig.add_hline(
        y=region_mean,
        line_dash="dash",
        line_color="#DC143C",
        line_width=1.5,
        annotation_text=f"Region mean: {region_mean:+.2f}",
        annotation_position="top right",
        annotation_font=dict(size=11, color="#DC143C"),
    )

    n_divs = len(sorted_divs)
    chart_width = max(700, n_divs * min_width_per_div)

    fig.update_layout(
        height=450,
        width=chart_width,
        margin=dict(l=60, r=20, t=20, b=50),
        yaxis_title="Overall Delta",
        hovermode=False,
    )
    fig.update_xaxes(tickfont=dict(size=10))

    return fig, chart_width


# National mean delta
national_mean_delta = delta_df["delta_overall"].mean()

with st.expander("Regional / Division Summary"):
    if selected_division != "All":
        st.info(f"Showing schools in {selected_division}. Clear the Division filter to see division rankings.")
    elif selected_region == "All":
        # Boxplot of school-level deltas by region
        st.markdown("**School Delta Distribution by Region**")
        fig_box = _build_region_boxplot(delta_df, national_mean_delta)
        st.plotly_chart(fig_box, use_container_width=True)
    else:
        # Single region — boxplot of divisions
        region_schools = delta_df[delta_df["Region"] == selected_region]
        n_divs = region_schools["Division"].nunique()
        region_mean = region_schools["delta_overall"].mean()
        st.markdown(f"**School Delta Distribution by Division in {selected_region}** ({n_divs} divisions)")
        fig_div, chart_width = _build_division_boxplot(region_schools, region_mean)
        if chart_width > 800:
            # Wide chart — render as scrollable HTML
            html_str = fig_div.to_html(include_plotlyjs="cdn", full_html=False)
            scroll_html = (
                f'<div style="overflow-x:auto;max-width:100%;border:1px solid #eee;border-radius:4px;">'
                f'{html_str}'
                f'</div>'
            )
            st.components.v1.html(scroll_html, height=500, scrolling=True)
        else:
            st.plotly_chart(fig_div, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Build ranked delta bars + assessed count + grade-language heatmap
# ---------------------------------------------------------------------------

n_display = len(ranked)

MAX_NAME_LEN = 20

def _truncate_label(row, rank, show_pillars=False):
    """Truncate school name, add ID, region/division on second line.

    When show_pillars=True, adds a third line with Need/Impact/Gap percentiles.
    """
    name = row["School Name"]
    if len(name) > MAX_NAME_LEN:
        name = name[:MAX_NAME_LEN].rstrip() + "..."
    sid = int(row["School ID"])
    line1 = f"{rank}. {name} ({sid})"
    line2 = f"   {row['Division']}, {row['Region']}"
    label = f"{line1}<br><span style='font-size:9px;color:#888'>{line2}</span>"
    if show_pillars and "need_pctile" in row.index and pd.notna(row.get("need_pctile")):
        n = row["need_pctile"]
        im = row["impact_pctile"]
        g = row["capacity_gap_pctile"]
        line3 = f"   Need {n:.0%} · Impact {im:.0%} · Gap {g:.0%}"
        label += f"<br><span style='font-size:9px;color:#4a7c9b'>{line3}</span>"
    return label

show_pillars = sort_mode == "Priority" and has_priority
school_labels = [
    _truncate_label(row, i + 1, show_pillars=show_pillars)
    for i, row in ranked.iterrows()
]

deltas = ranked["delta_overall"].tolist()
assessed = ranked["total_assessed"].tolist()
gl_pcts = ranked["pct_gl"].tolist() if "pct_gl" in ranked.columns else [np.nan] * n_display
bar_colors = ["#228B22" if d > 0 else "#DC143C" for d in deltas]

# Grade-lang delta matrix
gl_delta_cols = [f"delta_{gl}" for gl in GRADE_LANG_ORDER]
z_values = ranked[gl_delta_cols].values.tolist()

# Symmetric color range
all_gl_vals = [v for row in z_values for v in row if pd.notna(v)]
max_abs = max(abs(v) for v in all_gl_vals) if all_gl_vals else 1

fig = make_subplots(
    rows=1, cols=4,
    column_widths=[0.22, 0.13, 0.13, 0.52],
    horizontal_spacing=0.04,
)

# Col 1: Delta bars
fig.add_trace(go.Bar(
    y=school_labels,
    x=deltas,
    orientation="h",
    marker_color=bar_colors,
    text=[f"{d:+.2f}" for d in deltas],
    textposition="outside",
    textfont=dict(size=10),
    showlegend=False,
    hovertemplate="%{y}<br>Delta: %{x:+.2f}<extra></extra>",
    cliponaxis=False,
), row=1, col=1)

fig.add_vline(x=0, line_color="#333", line_width=1, row=1, col=1)

# Col 2: Assessed count bars
max_assessed = max(assessed) if assessed else 1
fig.add_trace(go.Bar(
    y=school_labels,
    x=assessed,
    orientation="h",
    marker_color="#5B9BD5",
    text=[f"{int(a):,}" for a in assessed],
    textposition="outside",
    textfont=dict(size=10),
    showlegend=False,
    hovertemplate="%{y}<br>Assessed: %{x:,.0f}<extra></extra>",
    cliponaxis=False,
), row=1, col=2)

# Col 3: GL% bars
valid_gl = [v for v in gl_pcts if pd.notna(v)]
max_gl = max(valid_gl) if valid_gl else 100
fig.add_trace(go.Bar(
    y=school_labels,
    x=gl_pcts,
    orientation="h",
    marker_color="#9B59B6",
    text=[f"{v:.0f}%" if pd.notna(v) else "" for v in gl_pcts],
    textposition="outside",
    textfont=dict(size=10),
    showlegend=False,
    hovertemplate="%{y}<br>At Grade Level: %{x:.1f}%<extra></extra>",
    cliponaxis=False,
), row=1, col=3)

# Col 4: Heatmap
fig.add_trace(go.Heatmap(
    z=z_values,
    x=GRADE_LANG_ORDER,
    y=school_labels,
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
    hovertemplate="<b>%{y}</b><br>%{x}: %{z:+.2f}<extra></extra>",
    showscale=False,
), row=1, col=4)

# Heatmap cell annotations
for i, row in ranked.iterrows():
    for j, gl in enumerate(GRADE_LANG_ORDER):
        val = row[f"delta_{gl}"]
        if pd.notna(val):
            text_color = "white" if abs(val) > max_abs * 0.6 else "black"
            fig.add_annotation(
                x=gl,
                y=school_labels[i],
                text=f"{val:+.1f}",
                showarrow=False,
                font=dict(size=9, color=text_color),
                xref="x4", yref="y4",
            )

# Layout
fig.update_layout(
    height=max(400, 80 + n_display * (75 if show_pillars else 60)),
    margin=dict(l=20, r=20, t=70, b=40),
)

# Column headers — use "x domain" refs so x=0.5 always centers within each subplot
fig.add_annotation(
    text="<b>Overall Delta</b>",
    xref="x domain", yref="paper", x=0.5, y=1.06,
    showarrow=False, font=dict(size=13),
)
fig.add_annotation(
    text="<b>Assessed</b>",
    xref="x2 domain", yref="paper", x=0.5, y=1.06,
    showarrow=False, font=dict(size=13),
)
fig.add_annotation(
    text="<b>% at Grade Level</b>",
    xref="x3 domain", yref="paper", x=0.5, y=1.06,
    showarrow=False, font=dict(size=13),
)
fig.add_annotation(
    text="<b>Shift by Grade / Language</b>",
    xref="x4 domain", yref="paper", x=0.5, y=1.06,
    showarrow=False, font=dict(size=13),
)

# Col 1 axes (delta)
max_d = max(abs(d) for d in deltas) if deltas else 1
fig.update_xaxes(range=[-max_d * 1.5, max_d * 1.5], row=1, col=1)
fig.update_yaxes(
    categoryorder="array",
    categoryarray=list(reversed(school_labels)),
    tickfont=dict(size=10),
    row=1, col=1,
)

# Col 2 axes (assessed)
fig.update_xaxes(range=[0, max_assessed * 1.4], showticklabels=False, row=1, col=2)
fig.update_yaxes(
    categoryorder="array",
    categoryarray=list(reversed(school_labels)),
    showticklabels=False,
    row=1, col=2,
)

# Col 3 axes (GL%)
fig.update_xaxes(range=[0, max_gl * 1.4], showticklabels=False, row=1, col=3)
fig.update_yaxes(
    categoryorder="array",
    categoryarray=list(reversed(school_labels)),
    showticklabels=False,
    row=1, col=3,
)

# Col 4 axes (heatmap)
fig.update_xaxes(side="bottom", tickfont=dict(size=10), row=1, col=4)
fig.update_yaxes(
    categoryorder="array",
    categoryarray=list(reversed(school_labels)),
    showticklabels=False,
    row=1, col=4,
)

st.plotly_chart(fig, use_container_width=True)

# Interpretation — includes sort mode explanation
with st.expander("How to read this chart"):
    st.markdown(f"""
    **Overall Delta (left):**
    The change in the school's overall ordinal score from {tp_from} to {tp_to}.
    Green = improvement, red = decline.

    **Assessed:**
    Average number of learners assessed across the two timepoints.
    Larger bars = more learners, giving the delta more statistical weight.

    **% at Grade Level:**
    Average percentage of learners at Grade Level proficiency across all grade-language groups
    at the later timepoint. Higher = better overall reading outcomes.

    **Shift by Grade / Language:**
    Each cell shows the ordinal score delta for a specific grade-language group.
    - **Green** = that group improved (learners shifted to higher proficiency levels)
    - **Red** = that group declined
    - **White/near-white** = little or no change
    - **Blank (no value)** = data was not available for that grade-language group at one or both timepoints (e.g., the school did not assess that group)

    ---

    **Ranking modes:**
    - **Delta**: ranks purely by score change regardless of school size. Small schools with few learners can appear at the top with extreme deltas that may not be statistically reliable.
    - **Weighted**: ranks by *delta × log(assessed learners)*. Gently dampens small-school noise — after a few hundred students, the size factor barely matters.
    - **Priority**: three-pillar composite for intervention targeting. Combines **Need** (ordinal mean, SD, skewness, and their deltas), **Impact** (assessed learner count), and **Capacity Gap** (inverse LGU Special Education Fund per enrolled learner). Each pillar is converted to a percentile rank, and the composite is their product — a school must score high on all three to rank at the top. The pillar percentiles are shown below each school name.
    """)

# Summary stats
st.markdown("---")
st.markdown("##### Summary")

if show_pillars:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Schools shown", f"{n_display}")
    col2.metric("Mean delta", f"{ranked['delta_overall'].mean():+.3f}")
    col3.metric("Median priority pctile", f"{ranked['priority_pctile'].median():.0%}")
    col4.metric("Priority-eligible", f"{delta_df['priority_pctile'].notna().sum():,} of {len(delta_df):,}")
else:
    col1, col2, col3 = st.columns(3)
    col1.metric("Schools shown", f"{n_display}")
    col2.metric("Mean delta", f"{ranked['delta_overall'].mean():+.3f}")
    col3.metric("Median delta", f"{ranked['delta_overall'].median():+.3f}")
