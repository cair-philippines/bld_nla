# Step 2 — Percentages, PCA Weights, and Performance Scoring

Reference: `documentation/multi_year_expansion_plan.md`

## Objective
Convert harmonized raw-count DataFrames (Step 1) into per-school weighted performance scores, one per time point. PCA weight derivation is part of this step — not optional — because equal weights produce degenerate scores.

## Files Modified/Created

| File | Status | Description |
|---|---|---|
| `modules/preprocessing.py` | Modified | Added `compute_percentages()`, `validate_timepoint()`, `_get_group_columns()` |
| `modules/analysis.py` | Created | `derive_pca_weights()`, `compute_performance_score()`, `process_all_timepoints()` |

## Internal Dependency Chain

```
2a  compute_percentages()       — per time point
 ↓
2b  validate_timepoint()        — per time point
 ↓
2c  derive_pca_weights()        — on ONE reference time point (needs 2a + 2b for that tp)
 ↓
2d  compute_performance_score() — per time point (needs 2a + 2c)
```

`process_all_timepoints(df_all, pca_reference=(...))` runs all four substeps in order.

## Why Equal Weights Are Blocked

With 5 reading profiles per grade-language group, each group sums to 100%. Equal weights → score = mean of all percentages = 100/5 = **20.00 for every school**. No differentiation. Progress (delta of two 20s) = 0. PCA or custom weights required.

`process_all_timepoints()` raises `ValueError` if neither `weights` nor `pca_reference` is provided.

## Functions

### `compute_percentages(df)` — preprocessing.py
- Cleans grade columns (removes commas, coerces to numeric)
- Divides each column by grade-language group row-sum × 100
- Groups with zero or all-NaN → NaN
- Returns DataFrame indexed by School ID (30 pct cols + metadata)

### `validate_timepoint(pct_df)` — preprocessing.py
- Per group: `has_{group}` = any non-NaN value
- `groups_available` (0–6), `valid` = groups_available > 0

### `derive_pca_weights(pct_df, validation, invert)` — analysis.py
- Fits PCA (1 component) on standardized 30-column percentage data of valid schools
- Maps PC1 loadings → category averages → scaled 0–100
- Returns `(weights_dict, pca_model)`
- Ported from `crla_v2.py` `optimize_weights_from_pca`, same logic

### `compute_performance_score(pct_df, weights)` — analysis.py
- `weights` parameter is **required** (no default)
- Weighted average across 30 columns, divisor adjusts for missing data
- Faithful to `crla_v2.py` `calculate_performance_score`

### `process_all_timepoints(df_all, weights=None, pca_reference=None)` — analysis.py
- Runs 2a→2b→2c→2d in order
- Exactly one of `weights` or `pca_reference` required
- Returns `{percentages, validation, weights, pca_model, performance}`

## Notebook Usage
```python
from preprocessing import load_all_assessments
from analysis import process_all_timepoints

df_all = load_all_assessments()
results = process_all_timepoints(df_all, pca_reference=('2024-25', 'EoSY'))

# results["weights"]      → PCA-derived weight dict
# results["performance"]  → {(sy, period): Series} — input to Step 3
```
