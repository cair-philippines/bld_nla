"""
CRLA School View

School-level page for school heads to view reading proficiency performance
across assessment timepoints.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TIMEPOINT_ORDER = ["BoSY 2024-25", "EoSY 2024-25", "BoSY 2025-26", "MoSY 2025-26", "EoSY 2025-26"]

PROFILE_COLORS = {
    "Lower Emergent": "#DC143C",
    "Higher Emergent": "#FF8C00",
    "Developing": "#FFD700",
    "Transitioning": "#9ACD32",
    "Grade Level": "#228B22",
}

PROFILE_ORDER = [
    "Lower Emergent",
    "Higher Emergent",
    "Developing",
    "Transitioning",
    "Grade Level",
]

GRADE_LANG_ORDER = ["G1", "G2 MT", "G2 Fil", "G3 MT", "G3 Fil", "G3 Eng"]

# Map grade-lang labels to ordinal column names in the parquet
GRADE_LANG_ORDINAL_COLS = {
    "G1": "ordinal_G1",
    "G2 MT": "ordinal_G2_MT",
    "G2 Fil": "ordinal_G2_Fil",
    "G3 MT": "ordinal_G3_MT",
    "G3 Fil": "ordinal_G3_Fil",
    "G3 Eng": "ordinal_G3_Eng",
}

# Proficiency level labels for heatmap annotation
PROFICIENCY_LABELS = {1: "LE", 2: "HE", 3: "Dev", 4: "Trans", 5: "GL"}


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data
def load_metadata():
    return pd.read_parquet(DATA_DIR / "school_metadata.parquet")


@st.cache_data
def load_profiles():
    return pd.read_parquet(DATA_DIR / "school_profiles.parquet")


@st.cache_data
def load_ordinal():
    return pd.read_parquet(DATA_DIR / "school_ordinal.parquet")


# ---------------------------------------------------------------------------
# Segment helpers
# ---------------------------------------------------------------------------

def get_segments(ordinal_school):
    """Compute segment deltas from a school's ordinal data."""
    segments = []
    tp_data = ordinal_school.sort_values("timepoint_label", key=lambda s: s.map(
        {tp: i for i, tp in enumerate(TIMEPOINT_ORDER)}
    ))

    for i in range(len(tp_data) - 1):
        row0 = tp_data.iloc[i]
        row1 = tp_data.iloc[i + 1]

        if not (row0["valid"] and row1["valid"]):
            continue

        tp0_label = row0["timepoint_label"]
        tp1_label = row1["timepoint_label"]

        # Neutral label: just the two timepoint names
        label = f"{tp0_label} \u2192 {tp1_label}"

        segments.append({
            "label": label,
            "delta_overall": row1["ordinal_overall"] - row0["ordinal_overall"],
            "delta_G1": row1["ordinal_G1"] - row0["ordinal_G1"],
            "delta_G2": row1["ordinal_G2"] - row0["ordinal_G2"],
            "delta_G3": row1["ordinal_G3"] - row0["ordinal_G3"],
            "tp0": tp0_label,
            "tp1": tp1_label,
        })

    return segments


def get_national_segments(ordinal_df):
    """Compute segment deltas for the national mean."""
    nat = ordinal_df[ordinal_df["School ID"] == -1].copy()
    return get_segments(nat)


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

metadata = load_metadata()
profiles = load_profiles()
ordinal = load_ordinal()

national_segments = get_national_segments(ordinal)

# ---------------------------------------------------------------------------
# Sidebar: Cascading filters (Region -> Division -> School)
# ---------------------------------------------------------------------------

st.sidebar.title("CRLA School Dashboard")
st.sidebar.markdown("---")

# Region filter
regions = sorted(metadata["Region"].dropna().unique())
selected_region = st.sidebar.selectbox(
    "Region", options=["All"] + regions
)

filtered = metadata.copy()
if selected_region != "All":
    filtered = filtered[filtered["Region"] == selected_region]

# Division filter
divisions = sorted(filtered["Division"].dropna().unique())
selected_division = st.sidebar.selectbox(
    "Division", options=["All"] + divisions
)

if selected_division != "All":
    filtered = filtered[filtered["Division"] == selected_division]

# School selector — text search with autocomplete
school_options = filtered.sort_values("School Name")
school_labels = {
    row["School ID"]: f"{row['School Name']} ({row['School ID']})"
    for _, row in school_options.iterrows()
}

# Build reverse lookup: display label -> School ID
label_to_id = {v: k for k, v in school_labels.items()}
sorted_labels = sorted(label_to_id.keys())

st.sidebar.markdown("---")

# Text input with search
search_term = st.sidebar.text_input(
    "Search school name",
    placeholder="Type school name...",
)

# Filter school list based on search
if search_term:
    matching_labels = [
        lbl for lbl in sorted_labels
        if search_term.lower() in lbl.lower()
    ]
else:
    matching_labels = sorted_labels

selected_label = st.sidebar.selectbox(
    "School",
    options=matching_labels,
    index=None,
    placeholder=f"Select from {len(matching_labels):,} schools...",
)

selected_school_id = label_to_id.get(selected_label) if selected_label else None

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

if selected_school_id is None:
    st.title("CRLA School Performance Dashboard")
    st.info(
        "Use the sidebar filters to narrow down and select a school. "
        f"Currently showing **{len(filtered):,}** schools."
    )
    st.stop()

# Get school data
school_meta = metadata[metadata["School ID"] == selected_school_id].iloc[0]
school_profiles = profiles[profiles["School ID"] == selected_school_id]
school_ordinal = ordinal[ordinal["School ID"] == selected_school_id]

# =========================================================================
# Section A: School Header
# =========================================================================

st.title(school_meta["School Name"])
st.markdown(
    f"**{school_meta['Division']}** · *{school_meta['Region']}*"
)

# Headline metrics per timepoint
available_tps = [
    tp for tp in TIMEPOINT_ORDER
    if tp in school_ordinal["timepoint_label"].values
]

# National GL% for comparison
nat_ordinal = ordinal[ordinal["School ID"] == -1]

cols = st.columns(len(available_tps))
for i, tp in enumerate(available_tps):
    tp_row = school_ordinal[school_ordinal["timepoint_label"] == tp].iloc[0]
    total = tp_row["total_assessed"]
    total_display = f"{int(total):,}" if pd.notna(total) else "\u2014"

    gl_pct = tp_row.get("pct_gl", np.nan)
    nat_row = nat_ordinal[nat_ordinal["timepoint_label"] == tp]
    nat_gl = nat_row.iloc[0].get("pct_gl", np.nan) if not nat_row.empty else np.nan

    with cols[i]:
        st.metric(label=tp, value=total_display, help="Total assessed learners")
        if pd.notna(gl_pct):
            delta_vs_nat = None
            help_gl = f"{gl_pct:.1f}% of learners at Grade Level"
            if pd.notna(nat_gl):
                delta_vs_nat = gl_pct - nat_gl
                direction = "above" if delta_vs_nat > 0 else "below"
                help_gl += f" (national: {nat_gl:.1f}%)"
            st.metric(
                label="At Grade Level",
                value=f"{gl_pct:.1f}%",
                delta=f"{delta_vs_nat:+.1f}pp vs national" if delta_vs_nat is not None else None,
                delta_color="normal",
                help=help_gl,
            )

st.markdown("---")

# =========================================================================
# Section B: Reading Profile Distribution (butterfly charts for same-year)
# =========================================================================

st.subheader("Reading Profile Distribution")

display_mode = st.radio(
    "Show as",
    ["Percentage", "Raw Count"],
    horizontal=True,
    label_visibility="collapsed",
)

value_col = "percentage" if display_mode == "Percentage" else "raw_count"

# Group timepoints by school year for butterfly charts
from collections import OrderedDict
sy_groups = OrderedDict()
for tp in available_tps:
    # Parse "BoSY 2024-25" -> ("2024-25", "BoSY")
    parts = tp.split(" ", 1)
    period, sy = parts[0], parts[1]
    sy_groups.setdefault(sy, []).append((tp, period))


def _build_butterfly_chart(tp_bosy, tp_eosy, sy_label, value_col, display_mode):
    """Build a butterfly/tornado chart comparing BoSY (left) and EoSY (right)."""
    bosy_data = school_profiles[school_profiles["timepoint_label"] == tp_bosy].copy()
    eosy_data = school_profiles[school_profiles["timepoint_label"] == tp_eosy].copy()

    fig = go.Figure()

    for gl in GRADE_LANG_ORDER:
        bosy_row = bosy_data[bosy_data["grade_lang"] == gl]
        eosy_row = eosy_data[eosy_data["grade_lang"] == gl]

        # Build stacked segments for each side
        bosy_profiles = bosy_row.set_index("profile")
        eosy_profiles = eosy_row.set_index("profile")

        for profile in PROFILE_ORDER:
            bosy_val = bosy_profiles.at[profile, value_col] if profile in bosy_profiles.index else 0
            eosy_val = eosy_profiles.at[profile, value_col] if profile in eosy_profiles.index else 0

            if pd.isna(bosy_val):
                bosy_val = 0
            if pd.isna(eosy_val):
                eosy_val = 0

            # BoSY goes left (negative), EoSY goes right (positive)
            fig.add_trace(go.Bar(
                y=[gl],
                x=[-bosy_val],
                orientation="h",
                name=profile,
                marker_color=PROFILE_COLORS[profile],
                legendgroup=profile,
                showlegend=False,
                text=f"{bosy_val:.1f}%" if display_mode == "Percentage" else f"{int(bosy_val):,}",
                textposition="inside",
                textfont_size=9,
                hovertemplate=f"BoSY: {profile}<br>{gl}<br>{bosy_val:.1f}%<extra></extra>" if display_mode == "Percentage"
                    else f"BoSY: {profile}<br>{gl}<br>{int(bosy_val):,}<extra></extra>",
            ))

            fig.add_trace(go.Bar(
                y=[gl],
                x=[eosy_val],
                orientation="h",
                name=profile,
                marker_color=PROFILE_COLORS[profile],
                legendgroup=profile,
                showlegend=False,
                text=f"{eosy_val:.1f}%" if display_mode == "Percentage" else f"{int(eosy_val):,}",
                textposition="inside",
                textfont_size=9,
                hovertemplate=f"EoSY: {profile}<br>{gl}<br>{eosy_val:.1f}%<extra></extra>" if display_mode == "Percentage"
                    else f"EoSY: {profile}<br>{gl}<br>{int(eosy_val):,}<extra></extra>",
            ))

    fig.update_layout(
        barmode="relative",
        title=f"<b>SY {sy_label}</b> — BoSY (left) vs EoSY (right)",
        title_font_size=16,
        height=320,
        margin=dict(l=0, r=0, t=50, b=60),
        yaxis=dict(
            categoryorder="array",
            categoryarray=list(reversed(GRADE_LANG_ORDER)),
            title=None,
        ),
        xaxis=dict(
            title=None,
            tickvals=[-100, -75, -50, -25, 0, 25, 50, 75, 100] if display_mode == "Percentage"
                else None,
            ticktext=["100%", "75%", "50%", "25%", "0", "25%", "50%", "75%", "100%"] if display_mode == "Percentage"
                else None,
        ),
        bargap=0.25,
    )

    # Add center divider
    fig.add_vline(x=0, line_color="#333333", line_width=1.5)

    # Add BoSY/EoSY annotations — use paper coordinates for consistent placement
    fig.add_annotation(
        x=0.25, xref="paper",
        y=1.08, yref="paper",
        text="<b>\u2190 BoSY</b>",
        showarrow=False,
        font=dict(size=13),
    )
    fig.add_annotation(
        x=0.75, xref="paper",
        y=1.08, yref="paper",
        text="<b>EoSY \u2192</b>",
        showarrow=False,
        font=dict(size=13),
    )

    return fig


def _build_single_chart(tp, value_col, display_mode):
    """Build a standard stacked bar chart for a single timepoint."""
    tp_data = school_profiles[school_profiles["timepoint_label"] == tp].copy()

    if tp_data.empty:
        return None

    x_label = "% of Learners" if display_mode == "Percentage" else "Number of Learners"

    tp_data["grade_lang"] = pd.Categorical(
        tp_data["grade_lang"], categories=GRADE_LANG_ORDER, ordered=True
    )
    tp_data["profile"] = pd.Categorical(
        tp_data["profile"], categories=PROFILE_ORDER, ordered=True
    )
    tp_data = tp_data.sort_values(["grade_lang", "profile"])

    fig = px.bar(
        tp_data,
        y="grade_lang",
        x=value_col,
        color="profile",
        orientation="h",
        category_orders={
            "grade_lang": GRADE_LANG_ORDER,
            "profile": PROFILE_ORDER,
        },
        color_discrete_map=PROFILE_COLORS,
        text=tp_data[value_col].apply(
            lambda v: f"{v:.1f}%" if display_mode == "Percentage" and pd.notna(v)
            else (f"{int(v):,}" if pd.notna(v) else "")
        ),
        labels={
            value_col: x_label,
            "grade_lang": "Grade / Language",
            "profile": "Reading Profile",
        },
    )

    fig.update_layout(
        title=f"<b>{tp}</b>",
        title_font_size=16,
        height=280,
        margin=dict(l=0, r=0, t=50, b=60),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            xanchor="center",
            x=0.5,
            title=None,
        ),
        bargap=0.25,
        xaxis=dict(
            range=[0, 100] if display_mode == "Percentage" else None,
            title=None,
        ),
    )

    fig.update_traces(
        textposition="inside",
        textfont_size=10,
    )

    return fig


# Add legend for butterfly charts (show once at top)
def _add_profile_legend():
    """Render a separate legend for reading profiles."""
    legend_html = " ".join(
        f'<span style="display:inline-block; width:14px; height:14px; '
        f'background-color:{PROFILE_COLORS[p]}; margin-right:4px; '
        f'vertical-align:middle; border-radius:2px;"></span>'
        f'<span style="margin-right:16px; vertical-align:middle;">{p}</span>'
        for p in PROFILE_ORDER
    )
    st.markdown(legend_html, unsafe_allow_html=True)


_add_profile_legend()

for sy, tp_list in sy_groups.items():
    periods = {period: tp for tp, period in tp_list}

    if "BoSY" in periods and "EoSY" in periods:
        # Butterfly chart for same-year comparison
        fig = _build_butterfly_chart(periods["BoSY"], periods["EoSY"], sy, value_col, display_mode)
        st.plotly_chart(fig, use_container_width=True)
    else:
        # Single timepoint — standard bar
        for tp, period in tp_list:
            fig = _build_single_chart(tp, value_col, display_mode)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# =========================================================================
# Section C: Ordinal Progress Score
# =========================================================================

st.subheader("Ordinal Progress Score")

school_segments = get_segments(school_ordinal)

if not school_segments:
    st.warning("Not enough valid timepoints to compute progress scores.")
else:
    # Metric cards
    seg_cols = st.columns(len(school_segments))
    for i, seg in enumerate(school_segments):
        # Find matching national segment
        nat_delta = None
        for ns in national_segments:
            if ns["tp0"] == seg["tp0"] and ns["tp1"] == seg["tp1"]:
                nat_delta = ns["delta_overall"]
                break

        delta_vs_national = None
        help_text = None
        if nat_delta is not None:
            delta_vs_national = round(seg["delta_overall"] - nat_delta, 3)
            direction = "above" if delta_vs_national > 0 else "below"
            help_text = (
                f"National mean: {nat_delta:+.3f}. "
                f"School is {abs(delta_vs_national):.3f} {direction} national."
            )

        seg_cols[i].metric(
            label=seg["label"],
            value=f"{seg['delta_overall']:+.3f}",
            delta=f"{delta_vs_national:+.3f} vs national" if delta_vs_national is not None else None,
            delta_color="normal",
            help=help_text,
        )

    # Trajectory line chart
    st.markdown("##### Score Trajectory")

    school_trajectory = school_ordinal[
        school_ordinal["timepoint_label"].isin(TIMEPOINT_ORDER) & school_ordinal["valid"]
    ].copy()
    school_trajectory["tp_order"] = school_trajectory["timepoint_label"].map(
        {tp: i for i, tp in enumerate(TIMEPOINT_ORDER)}
    )
    school_trajectory = school_trajectory.sort_values("tp_order")

    national_trajectory = ordinal[
        (ordinal["School ID"] == -1)
        & ordinal["timepoint_label"].isin(TIMEPOINT_ORDER)
    ].copy()
    national_trajectory["tp_order"] = national_trajectory["timepoint_label"].map(
        {tp: i for i, tp in enumerate(TIMEPOINT_ORDER)}
    )
    national_trajectory = national_trajectory.sort_values("tp_order")

    fig_traj = go.Figure()

    fig_traj.add_trace(go.Scatter(
        x=school_trajectory["timepoint_label"],
        y=school_trajectory["ordinal_overall"],
        mode="lines+markers+text",
        name=school_meta["School Name"],
        line=dict(color="#4A90D9", width=3),
        marker=dict(size=10),
        text=school_trajectory["ordinal_overall"].apply(lambda v: f"{v:.2f}"),
        textposition="top center",
        textfont=dict(size=12),
    ))

    fig_traj.add_trace(go.Scatter(
        x=national_trajectory["timepoint_label"],
        y=national_trajectory["ordinal_overall"],
        mode="lines+markers+text",
        name="National Mean",
        line=dict(color="#999999", width=2, dash="dash"),
        marker=dict(size=8),
        text=national_trajectory["ordinal_overall"].apply(lambda v: f"{v:.2f}"),
        textposition="bottom center",
        textfont=dict(size=11, color="#999999"),
    ))

    fig_traj.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis=dict(
            title="Ordinal Score",
            range=[1, 5],
            dtick=1,
        ),
        xaxis=dict(title=None),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
        ),
    )

    st.plotly_chart(fig_traj, use_container_width=True)

    # Interpretation guide
    with st.expander("How to read the ordinal score"):
        st.markdown("""
        The ordinal score represents the **average reading proficiency level** of students in the school, on a 1\u20135 scale:

        | Score | Level |
        |-------|-------|
        | 1 | Lower Emergent |
        | 2 | Higher Emergent |
        | 3 | Developing |
        | 4 | Transitioning |
        | 5 | Grade Level |

        A **positive delta** (e.g., +0.82) means students moved up in proficiency.
        A **negative delta** (e.g., -1.04) means students moved down.

        The "vs national" comparison shows whether the school's change was better or worse than the national average for that period.
        """)

st.markdown("---")

# =========================================================================
# Section D: Grade-Language Proficiency Heatmap
# =========================================================================

st.subheader("Proficiency by Grade Level and Language")

# Build heatmap data: rows = grade-lang groups, columns = timepoints
heatmap_rows = []
for gl in GRADE_LANG_ORDER:
    col_name = GRADE_LANG_ORDINAL_COLS[gl]
    for tp in available_tps:
        tp_row = school_ordinal[school_ordinal["timepoint_label"] == tp]
        if not tp_row.empty:
            score = tp_row.iloc[0][col_name]
        else:
            score = np.nan
        heatmap_rows.append({
            "Grade / Language": gl,
            "Timepoint": tp,
            "Score": score,
        })

heatmap_df = pd.DataFrame(heatmap_rows)

# Pivot for heatmap
pivot = heatmap_df.pivot(index="Grade / Language", columns="Timepoint", values="Score")
pivot = pivot.reindex(index=GRADE_LANG_ORDER, columns=[tp for tp in TIMEPOINT_ORDER if tp in pivot.columns])

# Also get national values for comparison
nat_pivot_rows = []
for gl in GRADE_LANG_ORDER:
    col_name = GRADE_LANG_ORDINAL_COLS[gl]
    for tp in available_tps:
        nat_row = ordinal[(ordinal["School ID"] == -1) & (ordinal["timepoint_label"] == tp)]
        if not nat_row.empty:
            nat_score = nat_row.iloc[0][col_name]
        else:
            nat_score = np.nan
        nat_pivot_rows.append({
            "Grade / Language": gl,
            "Timepoint": tp,
            "Score": nat_score,
        })

nat_pivot = pd.DataFrame(nat_pivot_rows).pivot(
    index="Grade / Language", columns="Timepoint", values="Score"
)
nat_pivot = nat_pivot.reindex(index=GRADE_LANG_ORDER, columns=[tp for tp in TIMEPOINT_ORDER if tp in nat_pivot.columns])

# Build annotated heatmap
z_values = pivot.values
nat_values = nat_pivot.values

# Annotation text: score + proficiency label + vs national
annotations = []
for i, gl in enumerate(pivot.index):
    for j, tp in enumerate(pivot.columns):
        score = z_values[i, j]
        nat_score = nat_values[i, j] if i < nat_values.shape[0] and j < nat_values.shape[1] else np.nan

        if pd.notna(score):
            # Nearest proficiency level
            nearest_level = int(round(score))
            nearest_level = max(1, min(5, nearest_level))
            level_label = PROFICIENCY_LABELS[nearest_level]

            text = f"<b>{score:.2f}</b><br>{level_label}"
            if pd.notna(nat_score):
                diff = score - nat_score
                text += f"<br><span style='font-size:10px'>{diff:+.2f} vs nat'l</span>"
        else:
            text = "\u2014"

        annotations.append(
            go.layout.Annotation(
                text=text,
                x=tp,
                y=gl,
                xref="x",
                yref="y",
                showarrow=False,
                font=dict(size=12, color="white" if pd.notna(score) and score < 3 else "black"),
            )
        )

fig_heat = go.Figure(data=go.Heatmap(
    z=z_values,
    x=list(pivot.columns),
    y=list(pivot.index),
    colorscale=[
        [0.0, "#DC143C"],   # 1 = Lower Emergent (crimson)
        [0.25, "#FF8C00"],  # 2 = Higher Emergent (orange)
        [0.5, "#FFD700"],   # 3 = Developing (gold)
        [0.75, "#9ACD32"],  # 4 = Transitioning (yellowgreen)
        [1.0, "#228B22"],   # 5 = Grade Level (forestgreen)
    ],
    zmin=1,
    zmax=5,
    colorbar=dict(
        title="Score",
        tickvals=[1, 2, 3, 4, 5],
        ticktext=["1 (LE)", "2 (HE)", "3 (Dev)", "4 (Trans)", "5 (GL)"],
        len=0.9,
    ),
    hovertemplate="<b>%{y}</b> @ %{x}<br>Score: %{z:.2f}<extra></extra>",
))

fig_heat.update_layout(
    height=350,
    margin=dict(l=0, r=0, t=10, b=0),
    yaxis=dict(
        categoryorder="array",
        categoryarray=list(reversed(GRADE_LANG_ORDER)),
        title=None,
    ),
    xaxis=dict(title=None, side="top"),
    annotations=annotations,
)

st.plotly_chart(fig_heat, use_container_width=True)

st.caption(
    "Red cells indicate areas needing the most attention. "
    "Green cells show grade-language groups approaching grade level. "
    "Values show the ordinal score (1\u20135) with comparison to the national mean."
)

st.markdown("---")

# =========================================================================
# Section E: Proficiency Distribution Shift (Hybrid)
# =========================================================================

st.subheader("Proficiency Distribution Shift")

# Timepoint selectors
if len(available_tps) >= 2:
    shift_cols = st.columns(2)
    with shift_cols[0]:
        tp_from = st.selectbox(
            "From",
            options=available_tps,
            index=0,
            key="shift_from",
        )
    with shift_cols[1]:
        # Default "To" = next timepoint after "From"
        from_idx = available_tps.index(tp_from)
        default_to = min(from_idx + 1, len(available_tps) - 1)
        to_options = [tp for tp in available_tps if tp != tp_from]
        tp_to = st.selectbox(
            "To",
            options=to_options,
            index=min(default_to - (1 if default_to > from_idx else 0), len(to_options) - 1)
                if to_options else 0,
            key="shift_to",
        )

    # Get profile data for the two selected timepoints
    from_profiles = school_profiles[school_profiles["timepoint_label"] == tp_from]
    to_profiles = school_profiles[school_profiles["timepoint_label"] == tp_to]

    if from_profiles.empty or to_profiles.empty:
        st.warning("Profile data not available for the selected timepoints.")
    else:
        # Aggregate across all grade-language groups: total % per profile
        from_totals = from_profiles.groupby("profile")["raw_count"].sum()
        to_totals = to_profiles.groupby("profile")["raw_count"].sum()

        from_grand = from_totals.sum()
        to_grand = to_totals.sum()

        from_pcts = [(from_totals.get(p, 0) / from_grand * 100) if from_grand > 0 else 0 for p in PROFILE_ORDER]
        to_pcts = [(to_totals.get(p, 0) / to_grand * 100) if to_grand > 0 else 0 for p in PROFILE_ORDER]

        cum_from = np.cumsum(from_pcts).tolist()
        cum_to = np.cumsum(to_pcts).tolist()
        deltas = [t - f for f, t in zip(from_pcts, to_pcts)]

        from plotly.subplots import make_subplots

        fig_hybrid = make_subplots(
            rows=1, cols=2,
            column_widths=[0.6, 0.4],
            horizontal_spacing=0.12,
            subplot_titles=[
                "Cumulative Distribution Shift",
                "Per-Profile Change (pp)",
            ],
        )

        # --- Left panel: Cumulative shift ---

        # Smart text positioning: place "from" labels above, "to" labels below,
        # but at Grade Level (always 100%) offset them left to avoid overlap
        from_positions = []
        to_positions = []
        for i in range(len(PROFILE_ORDER)):
            gap = abs(cum_from[i] - cum_to[i])
            if gap < 4:
                # Points too close — stagger left/right
                from_positions.append("top left")
                to_positions.append("bottom right")
            else:
                from_positions.append("top center")
                to_positions.append("bottom center")

        fig_hybrid.add_trace(go.Scatter(
            x=PROFILE_ORDER,
            y=cum_from,
            mode="lines+markers+text",
            name=tp_from,
            line=dict(color="#4A90D9", width=3),
            marker=dict(size=10),
            text=[f"{v:.1f}%" for v in cum_from],
            textposition=from_positions,
            textfont=dict(size=9),
            legendgroup="from",
            hovertemplate="%{x}<br>Cumulative: %{y:.1f}%<extra>" + tp_from + "</extra>",
        ), row=1, col=1)

        fig_hybrid.add_trace(go.Scatter(
            x=PROFILE_ORDER,
            y=cum_to,
            mode="lines+markers+text",
            name=tp_to,
            line=dict(color="#E74C3C", width=3),
            marker=dict(size=10),
            text=[f"{v:.1f}%" for v in cum_to],
            textposition=to_positions,
            textfont=dict(size=9),
            legendgroup="to",
            hovertemplate="%{x}<br>Cumulative: %{y:.1f}%<extra>" + tp_to + "</extra>",
        ), row=1, col=1)

        # Shade gap
        net_shift = sum(cum_from[i] - cum_to[i] for i in range(len(PROFILE_ORDER) - 1))
        if net_shift > 0:
            fill_color = "rgba(34, 139, 34, 0.15)"
            shade_y = cum_from + cum_to[::-1]
        else:
            fill_color = "rgba(220, 20, 60, 0.15)"
            shade_y = cum_to + cum_from[::-1]

        fig_hybrid.add_trace(go.Scatter(
            x=PROFILE_ORDER + PROFILE_ORDER[::-1],
            y=shade_y,
            fill="toself",
            fillcolor=fill_color,
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ), row=1, col=1)

        # Gap annotations (skip Grade Level — always 100%)
        for i in range(len(PROFILE_ORDER) - 1):
            gap = cum_from[i] - cum_to[i]
            if abs(gap) > 0.5:
                mid_y = (cum_from[i] + cum_to[i]) / 2
                fig_hybrid.add_annotation(
                    x=PROFILE_ORDER[i], y=mid_y,
                    text=f"<b>{gap:+.1f}pp</b>",
                    showarrow=False,
                    font=dict(size=10, color="#228B22" if gap > 0 else "#DC143C"),
                    bgcolor="rgba(255,255,255,0.8)",
                    xref="x1", yref="y1",
                )

        # --- Right panel: Diverging bars ---

        fig_hybrid.add_trace(go.Bar(
            y=PROFILE_ORDER,
            x=deltas,
            orientation="h",
            marker_color=[PROFILE_COLORS[p] for p in PROFILE_ORDER],
            text=[f"{d:+.1f}" for d in deltas],
            textposition="outside",
            textfont=dict(size=11),
            showlegend=False,
            hovertemplate="%{y}: %{x:+.1f}pp<extra></extra>",
            cliponaxis=False,
        ), row=1, col=2)

        fig_hybrid.add_vline(x=0, line_color="#333333", line_width=1.5, row=1, col=2)

        # Layout
        max_abs_delta = max(abs(d) for d in deltas) if deltas else 10
        bar_pad = max_abs_delta * 0.35  # extra room for outside labels

        fig_hybrid.update_layout(
            height=450,
            margin=dict(l=20, r=60, t=40, b=100),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.22,
                xanchor="center",
                x=0.3,
            ),
        )

        # Left panel axes
        fig_hybrid.update_xaxes(
            title=None,
            tickangle=-30,
            tickfont=dict(size=10),
            row=1, col=1,
        )
        fig_hybrid.update_yaxes(
            title="Cumulative %",
            range=[0, 108],
            row=1, col=1,
        )

        # Right panel axes
        fig_hybrid.update_xaxes(
            title="Percentage Points",
            range=[min(min(deltas), 0) - bar_pad, max(max(deltas), 0) + bar_pad],
            row=1, col=2,
        )
        fig_hybrid.update_yaxes(
            categoryorder="array",
            categoryarray=list(reversed(PROFILE_ORDER)),
            tickfont=dict(size=10),
            row=1, col=2,
        )

        st.plotly_chart(fig_hybrid, use_container_width=True)

        # Interpretation
        with st.expander("How to read this chart"):
            st.markdown(f"""
            **Left panel (Cumulative Distribution Shift):**
            Each point shows what % of learners are at or below that proficiency level.
            - If the **{tp_to}** curve sits **below** the **{tp_from}** curve, learners shifted **upward** (green shading = improvement).
            - If it sits **above**, learners shifted **downward** (red shading = regression).
            - The gap annotations show the difference in percentage points.
            - Both lines meet at 100% for Grade Level by definition (all learners are at or below the highest level).

            **Right panel (Per-Profile Change):**
            Shows the percentage point change in each profile's share.
            - Lower profiles (LE, HE) losing share + higher profiles (Trans, GL) gaining share = upward movement.
            """)

else:
    st.info("At least two timepoints are needed to show the distribution shift.")


# =========================================================================
# Section F: Within-Year Distribution Overlay (per grade-language group)
# =========================================================================

st.markdown("---")
st.subheader("Within-Year Distribution Overlay")
st.caption(
    "Smoothed BoSY vs EoSY distributions across reading profiles, shown "
    "per grade and language group. Use this to see how learners redistribute "
    "within each group across a school year."
)

_overlay_mode = st.radio(
    "Show as",
    ["Percentage", "Raw Count"],
    horizontal=True,
    label_visibility="collapsed",
    key="overlay_display_mode",
)
_overlay_value_col = "percentage" if _overlay_mode == "Percentage" else "raw_count"

# Grade → list of grade-language groups in canonical order
_GRADE_TO_GROUPS = {
    "G1": ["G1"],
    "G2": ["G2 MT", "G2 Fil"],
    "G3": ["G3 MT", "G3 Fil", "G3 Eng"],
}

_BOSY_COLOR = "#E07A3A"   # orange
_EOSY_COLOR = "#4DA688"   # teal
_FILL_ALPHA = 0.30


def _smooth_curve(x_positions, y_values):
    """Return an interpolated (x, y) pair with a smoothed curve.

    Uses scipy's make_interp_spline when available (matches the methodology
    notebook's skewness panel approach). Falls back to raw points if
    interpolation is not possible (e.g., all NaN).
    """
    import numpy as np
    x = np.asarray(x_positions, dtype=float)
    y = np.asarray(y_values, dtype=float)
    mask = ~np.isnan(y)
    if mask.sum() < 4:
        return x, y
    try:
        from scipy.interpolate import make_interp_spline
        x_valid = x[mask]
        y_valid = y[mask]
        x_smooth = np.linspace(x_valid.min(), x_valid.max(), 120)
        spline = make_interp_spline(x_valid, y_valid, k=3)
        y_smooth = spline(x_smooth)
        # Avoid negative dips below zero (counts/percentages can't go negative)
        y_smooth = np.clip(y_smooth, 0, None)
        return x_smooth, y_smooth
    except Exception:
        return x, y


def _build_overlay_subplot(gl_label, bosy_data, eosy_data, value_col, display_mode):
    """Build a single overlay subplot for one grade-language group."""
    x_pos = list(range(1, 6))  # 1..5 matches profile_order

    bosy_row = bosy_data[bosy_data["grade_lang"] == gl_label]
    eosy_row = eosy_data[eosy_data["grade_lang"] == gl_label]

    bosy_vals = [np.nan] * 5
    eosy_vals = [np.nan] * 5

    if not bosy_row.empty:
        for _, r in bosy_row.iterrows():
            idx = int(r["profile_order"]) - 1
            if 0 <= idx < 5:
                bosy_vals[idx] = r[value_col]
    if not eosy_row.empty:
        for _, r in eosy_row.iterrows():
            idx = int(r["profile_order"]) - 1
            if 0 <= idx < 5:
                eosy_vals[idx] = r[value_col]

    fig = go.Figure()

    # If neither timepoint has data, render an empty frame with a note
    if all(np.isnan(bosy_vals)) and all(np.isnan(eosy_vals)):
        fig.add_annotation(
            text="No data for this group",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=11, color="#999999"),
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        fig.update_layout(height=220, margin=dict(l=20, r=10, t=40, b=30),
                          title=dict(text=f"<b>{gl_label}</b>", font=dict(size=13)))
        return fig

    def _hex_to_rgba(hex_color, alpha):
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    # BoSY smoothed curve with fill
    bx, by = _smooth_curve(x_pos, bosy_vals)
    if not all(np.isnan(by)):
        fig.add_trace(go.Scatter(
            x=bx, y=by,
            name=f"BoSY",
            mode="lines",
            line=dict(color=_BOSY_COLOR, width=2.5),
            fill="tozeroy",
            fillcolor=_hex_to_rgba(_BOSY_COLOR, _FILL_ALPHA),
            hovertemplate="BoSY<br>%{y:.1f}<extra></extra>",
        ))
        # Markers at actual data points
        fig.add_trace(go.Scatter(
            x=x_pos, y=bosy_vals,
            mode="markers",
            marker=dict(color=_BOSY_COLOR, size=6),
            showlegend=False,
            hoverinfo="skip",
        ))

    # EoSY smoothed curve with fill
    ex, ey = _smooth_curve(x_pos, eosy_vals)
    if not all(np.isnan(ey)):
        fig.add_trace(go.Scatter(
            x=ex, y=ey,
            name=f"EoSY",
            mode="lines",
            line=dict(color=_EOSY_COLOR, width=2.5),
            fill="tozeroy",
            fillcolor=_hex_to_rgba(_EOSY_COLOR, _FILL_ALPHA),
            hovertemplate="EoSY<br>%{y:.1f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=x_pos, y=eosy_vals,
            mode="markers",
            marker=dict(color=_EOSY_COLOR, size=6),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Y-axis: counts start at 0 with auto max; percentages cap at 100
    if display_mode == "Percentage":
        y_range = [0, 100]
    else:
        combined = [v for v in (bosy_vals + eosy_vals) if not np.isnan(v)]
        y_max = max(combined) * 1.15 if combined else 10
        y_range = [0, y_max]

    fig.update_layout(
        height=220,
        margin=dict(l=40, r=10, t=40, b=35),
        title=dict(text=f"<b>{gl_label}</b>", font=dict(size=13), x=0.02),
        showlegend=False,
        xaxis=dict(
            tickmode="array",
            tickvals=x_pos,
            ticktext=["LE", "HE", "Dev", "Trans", "GL"],
            tickfont=dict(size=10),
            range=[0.8, 5.2],
        ),
        yaxis=dict(
            title=dict(text=display_mode, font=dict(size=9)),
            tickfont=dict(size=9),
            range=y_range,
        ),
        hovermode="x unified",
    )

    return fig


# Render: one block per school year that has both BoSY and EoSY
_within_year_pairs = []
for _sy, _tp_list in sy_groups.items():
    _periods = {p: tp for tp, p in _tp_list}
    if "BoSY" in _periods and "EoSY" in _periods:
        _within_year_pairs.append((_sy, _periods["BoSY"], _periods["EoSY"]))

if not _within_year_pairs:
    st.info("At least one school year with both BoSY and EoSY data is needed for the overlay view.")
else:
    # Legend for this section (orange = BoSY, teal = EoSY)
    _legend_html = (
        f'<span style="display:inline-block; width:14px; height:14px; '
        f'background-color:{_BOSY_COLOR}; margin-right:4px; '
        f'vertical-align:middle; border-radius:2px; opacity:0.7;"></span>'
        f'<span style="margin-right:16px; vertical-align:middle;">BoSY</span>'
        f'<span style="display:inline-block; width:14px; height:14px; '
        f'background-color:{_EOSY_COLOR}; margin-right:4px; '
        f'vertical-align:middle; border-radius:2px; opacity:0.7;"></span>'
        f'<span style="vertical-align:middle;">EoSY</span>'
    )
    st.markdown(_legend_html, unsafe_allow_html=True)
    st.markdown("")

    for _sy, _tp_bosy, _tp_eosy in _within_year_pairs:
        st.markdown(f"**SY {_sy}**")

        _bosy_df = school_profiles[school_profiles["timepoint_label"] == _tp_bosy]
        _eosy_df = school_profiles[school_profiles["timepoint_label"] == _tp_eosy]

        # Row 1: G1 (full width)
        _fig = _build_overlay_subplot("G1", _bosy_df, _eosy_df, _overlay_value_col, _overlay_mode)
        st.plotly_chart(_fig, use_container_width=True, key=f"overlay_{_sy}_G1")

        # Row 2: G2 MT + G2 Fil (half widths)
        _c2a, _c2b = st.columns(2)
        with _c2a:
            _fig = _build_overlay_subplot("G2 MT", _bosy_df, _eosy_df, _overlay_value_col, _overlay_mode)
            st.plotly_chart(_fig, use_container_width=True, key=f"overlay_{_sy}_G2MT")
        with _c2b:
            _fig = _build_overlay_subplot("G2 Fil", _bosy_df, _eosy_df, _overlay_value_col, _overlay_mode)
            st.plotly_chart(_fig, use_container_width=True, key=f"overlay_{_sy}_G2Fil")

        # Row 3: G3 MT + G3 Fil + G3 Eng (third widths)
        _c3a, _c3b, _c3c = st.columns(3)
        with _c3a:
            _fig = _build_overlay_subplot("G3 MT", _bosy_df, _eosy_df, _overlay_value_col, _overlay_mode)
            st.plotly_chart(_fig, use_container_width=True, key=f"overlay_{_sy}_G3MT")
        with _c3b:
            _fig = _build_overlay_subplot("G3 Fil", _bosy_df, _eosy_df, _overlay_value_col, _overlay_mode)
            st.plotly_chart(_fig, use_container_width=True, key=f"overlay_{_sy}_G3Fil")
        with _c3c:
            _fig = _build_overlay_subplot("G3 Eng", _bosy_df, _eosy_df, _overlay_value_col, _overlay_mode)
            st.plotly_chart(_fig, use_container_width=True, key=f"overlay_{_sy}_G3Eng")

        st.markdown("")

    with st.expander("How to read these overlays"):
        st.markdown(
            """
            Each subplot shows a smoothed distribution of learners across the five reading profiles
            (Lower Emergent → Grade Level) for a single grade-language group.
            - **Orange curve** = BoSY (start of year)
            - **Teal curve** = EoSY (end of year)
            - If the teal curve is **shifted right** relative to the orange curve, learners moved
              toward higher proficiency over the school year.
            - If the **peak** of each curve moves rightward, the modal learner is improving.
            - Overlapping regions show where the distributions agree; non-overlapping regions
              show where the school saw net movement.

            Curves are smoothed splines fit to the 5 discrete data points; dots mark the actual values.
            """
        )
