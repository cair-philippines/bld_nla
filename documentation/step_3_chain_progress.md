# Step 3 — Chain-Based Progress Scoring

## Overview

Step 3 computes **pairwise segment deltas** and a **composite progress score** across an ordered chain of time points. It builds directly on Step 2 outputs (performance scores, validation, raw data).

## Time Chain

The default chain is defined in `modules/analysis.py`:

```python
TIME_CHAIN = [
    ("2024-25", "BoSY"),
    ("2024-25", "EoSY"),
    ("2025-26", "BoSY"),
]
```

This produces two segments:
- **Segment 1 — Learning_2024-25**: BoSY → EoSY within the same school year
- **Segment 2 — Retention_2024-25_to_2025-26**: EoSY → BoSY across school years

As new data arrives, append to `TIME_CHAIN` (e.g., `("2025-26", "EoSY")` adds a third segment).

## Segment Types

| Pattern | Label | Interpretation |
|---------|-------|----------------|
| BoSY → EoSY (same year) | `Learning_{sy}` | Within-year growth |
| EoSY → BoSY (next year) | `Retention_{sy0}_to_{sy1}` | Summer/cross-year retention |

## Cross-Timepoint Validation

Each segment requires **two checks** before a delta is computed:

1. **Both-endpoint validity**: The school must pass per-timepoint validation (Step 2b) at both the start and end of the segment.
2. **Count stability**: The total assessed student count must not change by more than `count_threshold` (default 25%) between the two endpoints. Large swings suggest school mergers, splits, or data errors.

If either check fails, the segment delta is set to `NaN`.

### Why count stability matters

A school that reports 500 students at BoSY and 200 at EoSY likely experienced a structural change (not genuine reading growth or decline). The 25% threshold catches these cases while allowing normal enrollment fluctuation.

## Output Columns

`compute_chain_progress()` returns a DataFrame with one row per school (union of all schools across all time points):

| Column | Description |
|--------|-------------|
| `School Name`, `Division`, `District`, `Region` | Metadata (from first available time point) |
| `perf_{period}_{sy}` | Performance score at each time point |
| `seg{n}_{label}` | Segment delta (performance change), NaN if invalid |
| `seg{n}_valid` | Boolean — segment passed both checks |
| `seg{n}_count_stable` | Boolean — count stability check passed |
| `segments_available` | Count of valid segments (0 to N-1 where N = chain length) |
| `composite_score` | Sum of valid segment deltas (NaN if no segments valid) |

## Composite Score

The composite score is the **sum** of all valid segment deltas for a school. It represents cumulative progress across the entire chain.

- A school with 2 valid segments: `composite = seg1_delta + seg2_delta`
- A school with 1 valid segment: `composite = that segment's delta`
- A school with 0 valid segments: `composite = NaN`

The `segments_available` column indicates how many segments contributed to the composite, enabling comparisons among schools with the same number of valid segments.

## Usage

```python
from preprocessing import load_all_assessments
from analysis import process_all_timepoints, compute_chain_progress

# Step 1 + 2
df_all = load_all_assessments()
results = process_all_timepoints(df_all, pca_reference=("2024-25", "BoSY"))

# Step 3
chain_result = compute_chain_progress(
    performance=results["performance"],
    raw_data=df_all,
    validation=results["validation"],
)
```

### Custom time chain

```python
chain_result = compute_chain_progress(
    performance=results["performance"],
    raw_data=df_all,
    validation=results["validation"],
    time_chain=[("2024-25", "BoSY"), ("2024-25", "EoSY")],  # single segment
)
```

### Custom count threshold

```python
chain_result = compute_chain_progress(
    ...,
    count_threshold=0.10,  # stricter: 10% max change
)
```

## Dependencies

- **Input**: Step 2 outputs (`performance`, `validation`) and Step 1 raw data (`df_all`)
- **Module**: `modules/analysis.py` — `compute_chain_progress()`, `_total_assessed()`, `_segment_label()`

## Status

- **Implemented** in `modules/analysis.py`
- **Pending**: user verification in notebook environment
