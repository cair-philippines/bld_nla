# CRLA Dashboard Plan

## Purpose

A Streamlit dashboard for school heads to view their school's CRLA reading proficiency performance across timepoints, with ordinal progress tracking.

## Target Users

School heads who need to:
- See how their students are distributed across reading proficiency levels
- Track whether reading performance improved or declined across assessment periods
- Identify which grade levels and language groups need the most attention

## Technology Stack

- **Framework**: Streamlit (Python)
- **Charts**: Plotly (Graph Objects + Express)
- **Data format**: Pre-computed parquet files (loaded once at startup)
- **Hosting**: Runs in the data science container on port 8050

## Data Preparation

A `prepare_data.py` script pre-computes three parquet files from the raw pipeline:

### 1. `school_metadata.parquet`
One row per school (union across all timepoints). Used for cascading filter lookups.

| Column | Type | Description |
|--------|------|-------------|
| School ID | int | Primary key |
| School Name | str | |
| Region | str | |
| Division | str | |
| District | str | |
| timepoints_available | str | Comma-separated list (e.g., "BoSY 2024-25, EoSY 2024-25, BoSY 2025-26") |

### 2. `school_profiles.parquet`
Long format — one row per school x timepoint x grade-language group x reading profile. Designed for direct use with Plotly stacked bar and butterfly charts.

| Column | Type | Description |
|--------|------|-------------|
| School ID | int | |
| school_year | str | e.g., "2024-25" |
| period | str | "BoSY" or "EoSY" |
| timepoint_label | str | e.g., "BoSY 2024-25" (for display) |
| grade | str | "G1", "G2", "G3" |
| language | str | None, "MT", "Fil", "Eng" |
| grade_lang | str | "G1", "G2 MT", "G2 Fil", "G3 MT", "G3 Fil", "G3 Eng" |
| profile | str | Reading profile name |
| profile_order | int | 1-5 (for consistent stack ordering: LE=1, HE=2, Dev=3, Trans=4, GL=5) |
| raw_count | int | Raw student count |
| percentage | float | Percentage within grade-language group (0-100) |
| group_total | int | Total assessed in this grade-language group |

Rows per school-timepoint: 6 groups x 5 profiles = 30.

### 3. `school_ordinal.parquet`
One row per school x timepoint. Pre-computed ordinal scores at multiple aggregation levels.

| Column | Type | Description |
|--------|------|-------------|
| School ID | int | |
| school_year | str | |
| period | str | |
| timepoint_label | str | |
| total_assessed | int | Sum of all 30 raw count columns |
| ordinal_overall | float | School-wide ordinal score (1-5) |
| ordinal_G1 | float | G1 ordinal score |
| ordinal_G2 | float | Mean of G2 MT and G2 Fil |
| ordinal_G3 | float | Mean of G3 MT, G3 Fil, G3 Eng |
| ordinal_G2_MT | float | |
| ordinal_G2_Fil | float | |
| ordinal_G3_MT | float | |
| ordinal_G3_Fil | float | |
| ordinal_G3_Eng | float | |
| valid | bool | Per-timepoint validation flag |

National means are appended as a synthetic school (School ID = -1) for comparison rendering.

## Dashboard Layout

### Sidebar: Cascading Filters

```
Region        [dropdown, default "All"]
Division      [dropdown, filtered by Region]
Search        [text input — type school name to filter]
School        [dropdown: "School Name (School ID)", filtered by search + Region/Division]
```

Two-level geographic filter (Region → Division), then a text search field that filters the school dropdown by name. District filter removed for simplicity.

### Section A: School Header

```
┌──────────────────────────────────────────────────────────┐
│  School Name                                             │
│  Division · Region                                       │
│                                                          │
│  BoSY 2024-25    EoSY 2024-25     BoSY 2025-26          │
│  ┌──────────┐    ┌──────────┐     ┌──────────┐          │
│  │  4,706   │    │  4,892   │     │  5,103   │          │
│  │ assessed │    │ assessed │     │ assessed │          │
│  └──────────┘    └──────────┘     └──────────┘          │
└──────────────────────────────────────────────────────────┘
```

Three `st.metric` cards showing total assessed learners per timepoint. Uses `st.columns(3)` layout.

### Section B: Reading Profile Distribution

**Butterfly charts** for same-school-year BoSY/EoSY pairs, standard stacked bars for standalone timepoints.

**Butterfly chart spec** (per school year with both BoSY and EoSY):
- Chart type: Plotly horizontal stacked bar (relative barmode)
- BoSY extends left (negative x), EoSY extends right (positive x)
- Y-axis: grade-language group (G1 through G3 Eng)
- Stacks: reading profiles in ordinal order, same colors as single charts
- Center divider line at x=0
- Annotations: "← BoSY" (left) and "EoSY →" (right) above the chart
- Symmetric x-axis ticks (100% to 0 to 100%)
- Makes within-year comparison intuitive (mirror image)

**Single timepoint chart spec** (for unpaired timepoints like BoSY 2025-26):
- Standard horizontal stacked bar (same as before)
- Y-axis: grade-language groups, X-axis: percentage or raw count

Toggle: `st.radio("Show as", ["Percentage", "Raw Count"])` above the charts.

Profile color legend rendered once above all charts using HTML spans.

### Section C: Ordinal Progress Score

```
┌──────────────────────────────────────────────────────────┐
│  Ordinal Progress Score                                  │
│                                                          │
│  BoSY 2024-25 → EoSY 2024-25    EoSY 2024-25 → BoSY …  │
│  ┌────────────────┐              ┌────────────────┐      │
│  │    +0.92       │              │    -1.15       │      │
│  │  ▲ vs +0.82    │              │  ▼ vs -1.04    │      │
│  │   national     │              │   national     │      │
│  └────────────────┘              └────────────────┘      │
│                                                          │
│  [Line chart: ordinal score trajectory across timepoints]│
│  School line vs national mean line (dashed)              │
└──────────────────────────────────────────────────────────┘
```

- **Metric cards**: one per segment, using neutral timepoint labels (e.g., "BoSY 2024-25 → EoSY 2024-25") — no "Learning"/"Retention" terminology pending stakeholder consultation
- **Trajectory line chart**: x-axis = timepoints (ordered), y-axis = ordinal score (1-5). School as solid line, national mean as dashed line.

### Section D: Proficiency by Grade Level and Language (Heatmap)

```
┌──────────────────────────────────────────────────────────┐
│  Proficiency by Grade Level and Language                  │
│                                                          │
│            BoSY 2024-25  EoSY 2024-25  BoSY 2025-26     │
│  G1           2.85          3.60          2.70           │
│  G2 MT        3.12          4.01          2.95           │
│  G2 Fil       3.45          4.20          3.30           │
│  G3 MT        3.50          4.35          3.20           │
│  G3 Fil       3.60          4.40          3.35           │
│  G3 Eng       3.20          4.10          3.00           │
│                                                          │
│  Color: red (1) → green (5), same palette as profiles   │
│  Annotations: score, proficiency label, vs national      │
└──────────────────────────────────────────────────────────┘
```

- **Heatmap**: rows = 6 grade-language groups, columns = timepoints
- **Color scale**: matches reading profile colors (crimson 1 → forestgreen 5)
- **Cell annotations**: ordinal score, nearest proficiency level abbreviation, difference vs national mean
- **Purpose**: school heads can instantly see red cells = areas needing attention
- Replaces the previous grouped bar chart which was less intuitive for identifying focus areas

## Color Palette

### Reading profiles (consistent across all charts)
| Profile | Color | Hex |
|---------|-------|-----|
| Lower Emergent | Crimson | #DC143C |
| Higher Emergent | Orange | #FF8C00 |
| Developing | Gold | #FFD700 |
| Transitioning | Yellow Green | #9ACD32 |
| Grade Level | Forest Green | #228B22 |

### Heatmap
Uses the same 5-color scale as reading profiles, mapped to ordinal scores 1–5.

## File Structure

```
dashboard/
  app.py              — Streamlit entry point
  pages/              — future multi-page views (Streamlit convention)
  components/         — reusable chart builders and UI helpers
  scripts/            — data preparation and one-off utilities
    prepare_data.py
    dashboard.ipynb
  data/               — generated parquet files
    school_metadata.parquet
    school_profiles.parquet
    school_ordinal.parquet
```

## Data Volume Estimates

- Schools: ~39K (union across timepoints)
- `school_metadata.parquet`: 39K rows, ~6 columns — tiny
- `school_profiles.parquet`: 39K x 3 timepoints x 30 = ~3.5M rows — moderate, ~50MB
- `school_ordinal.parquet`: 39K x 3 = ~117K rows — small
- Total memory at runtime: <200MB, well within container limits

## Design Decisions

- **No District filter**: removed to simplify cascading filters (Region → Division → School)
- **Text search for schools**: school name autocomplete via `st.text_input` filters the dropdown
- **Butterfly charts**: BoSY/EoSY of same school year shown as tornado chart for easy comparison
- **Neutral segment labels**: using timepoint names (e.g., "BoSY 2024-25 → EoSY 2024-25") instead of "Learning"/"Retention" pending stakeholder naming convention review
- **Heatmap for Section D**: replaced grouped bar chart — directly answers "what grade and language group needs work?" with color-coded cells
