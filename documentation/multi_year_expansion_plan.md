# Multi-Year CRLA Expansion Plan

## Goal
Expand `crla_v2.py` to support multi-school-year, period-by-period analysis with a chain-based composite progress score.

## Current State
- Pipeline processes one BoSY+EoSY pair (SY 2024-25)
- Hard-coded `iloc` positional splitting assumes fixed column counts per period
- Output: single progress score (EoSY perf - BoSY perf) per school

## Available Data
| Time Point | File | ~Schools |
|---|---|---|
| SY 2024-25 BoSY | `CRLA Results Archive_...BoSY.csv` | 35K |
| SY 2024-25 EoSY | `CRLA Results Archive_...EoSY.csv` | 37K |
| SY 2025-26 BoSY | `CRLA National Dashboard_...BoSY 2025-26...csv` | 39K |

## Schema Differences Between Years
After filtering "Total" columns, both years yield the same 30 reading-profile columns. Three hazards:
1. **Column order swap**: 2024-25 has `G2 Fil Transitioning` before `G2 Fil Developing`; 2025-26 reverses them.
2. **Extra Total columns in 2025-26**: `G2 Total MT Assessed`, `G2 Total Fil Assessed`, `G3 Total MT/Fil/Eng Assessed` (new). Existing filter handles removal, but positions shift.
3. **Typo** in both years: `G2 FIl Higher Emergent` (capital I).

## Plan

### Step 1 — Schema Harmonizer (done)
See `documentation/step_1_schema_harmonizer.md`.

### Step 2 — Percentages, Weights, and Performance Scoring (done)

Two scoring methods available via `process_all_timepoints(..., scoring=)`:

**PCA scoring** (`scoring="pca"`):
```
2a  compute_percentages()       per time point — raw counts → pct (name-based, no iloc)
 |
2b  validate_timepoint()        per time point — flag incomplete schools, count groups (0-6)
 |
2c  derive_pca_weights()        on ONE reference time point — needs 2a + 2b for that tp
 |
2d  compute_performance_score() per time point — needs 2a + 2c (PCA weights)
```
Requires `weights` or `pca_reference`. Equal weights are degenerate (always 20.00).

**Ordinal scoring** (`scoring="ordinal"`):
```
2a  compute_percentages()       per time point
 |
2b  validate_timepoint()        per time point
 |
2d  compute_ordinal_score()     per time point — fixed weights (1-5), no reference needed
```
Uses fixed ordinal proficiency weights: LE=1, HE=2, Dev=3, Trans=4, GL=5. Score range [1, 5] = average proficiency level. No reference timepoint, stable across time, directly interpretable.

Functions in `modules/preprocessing.py`: `compute_percentages()`, `validate_timepoint()`
Functions in `modules/analysis.py`: `derive_pca_weights()`, `compute_performance_score()`, `compute_ordinal_score()`, `process_all_timepoints()`

Output: `{(school_year, period): performance_series}` — one scalar per school per time point.

### Step 3 — Chain-Based Progress Scoring (done)

See `documentation/step_3_chain_progress.md`.

Ordered time chain (extended as new data arrives):
```python
TIME_CHAIN = [
    ('2024-25', 'BoSY'),
    ('2024-25', 'EoSY'),
    ('2025-26', 'BoSY'),
]
```

**Cross-timepoint validation is internal to this step**, not separate. For each consecutive pair `(t_i, t_{i+1})`:
1. Check both endpoints have valid per-timepoint data (from Step 2b).
2. Check raw student count stability between endpoints (>25% change -> flag).
3. If valid, compute segment delta = `perf(t_{i+1}) - perf(t_i)`.

**Segment labels**:
- BoSY -> EoSY = **Learning** (within-year gain)
- EoSY -> next BoSY = **Retention** (over-summer change)

**Composite**: Sum of all available segment scores. Decomposes exactly into segments.

**Output per school (one row)**:
```
School ID | metadata | Perf t0 | Perf t1 | Perf t2 |
  Seg 1 (Learning 24-25) | Seg 2 (Retention 24-25->25-26) |
  Segments Available | Composite Score
```

Core function:
```python
def compute_chain_progress(
    performance,    # {(sy, period): Series} from Step 2d
    raw_data,       # {(sy, period): DataFrame} from Step 1 (for count checks)
    validation,     # {(sy, period): DataFrame} from Step 2b
    time_chain,     # ordered list of (sy, period) tuples
):
```

Lives in `modules/analysis.py`.

### Step 4 — Output (done)

See `documentation/step_4_output.md`.

- One CSV per consecutive pair: `{prefix}.{segment_label}.csv`
- 91 columns matching `crla_v2.py` layout (with school-year suffixes)
- `filename_prefix` parameter: `crla_progress_score.pca_derived` or `crla_progress_score.ordinal`
- Verified against original Excel output (see step_4_output.md for detailed comparison)

## Scoring Method Comparison

| | PCA | Ordinal |
|---|---|---|
| Scale | 0-100 (arbitrary) | 1-5 (proficiency levels) |
| Reference timepoint | Required (unstable: BoSY vs EoSY gives opposite weights) | Not needed |
| Stability | Weights change with reference choice | Fixed, identical across timepoints |
| Learning delta (BoSY->EoSY) | -5.54 (counterintuitive) | +0.82 (gain, intuitive) |
| Retention delta (EoSY->BoSY) | +6.04 | -1.04 (summer loss, intuitive) |
| Interpretability | Opaque | "Average student is at level 3.3" |
| Recommendation | Exploratory/research use | **Preferred for intervention targeting** |

## Dashboard

See `documentation/dashboard_plan.md`.

Streamlit dashboard for school heads. School-level view with:
- Cascading filters (Region → Division → School) with text search for school name
- Total assessed learners per timepoint
- Butterfly/tornado charts for same-year BoSY vs EoSY profile comparison
- Standard stacked bars for standalone timepoints
- Ordinal progress score deltas with neutral timepoint labels and national comparison
- Score trajectory line chart (school vs national)
- Grade-language proficiency heatmap (6 groups × timepoints, color-coded 1-5)

```
dashboard/
  app.py              — Streamlit entry point
  pages/              — future multi-page views
  components/         — reusable chart builders and UI helpers
  scripts/            — data preparation and utilities
    prepare_data.py
    dashboard.ipynb
  data/               — generated parquet files
```

Run: `python dashboard/scripts/prepare_data.py` first, then `streamlit run dashboard/app.py --server.port 8050` (inside DS container)

## Unchanged
- Five reading profiles: Lower Emergent, Higher Emergent, Developing, Transitioning, Grade Level
- Grade structure: G1, G2 (MT/Fil), G3 (MT/Fil/Eng)

## Module Structure
```
modules/
  gcs_utils.py        — GCS filesystem, bucket paths
  preprocessing.py     — harmonization, loading, percentage conversion, per-tp validation
  analysis.py          — PCA weights, ordinal scoring, performance scoring, chain progress
  output.py            — pairwise CSV export
  crla_v2.py           — original (untouched, for backward compat)
```

## Dependency Order (linear, no ambiguity)
```
Step 1 (done) -> 2a -> 2b -> 2c/2d (done) -> Step 3 (done) -> Step 4 (done)
```
