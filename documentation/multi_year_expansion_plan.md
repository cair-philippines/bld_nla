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

### Step 2 — Percentages, PCA Weights, and Performance Scoring

Strict internal sequence — each substep depends on the previous:

```
2a  compute_percentages()       per time point — raw counts → pct (name-based, no iloc)
 ↓
2b  validate_timepoint()        per time point — flag incomplete schools, count groups (0–6)
 ↓
2c  derive_pca_weights()        on ONE reference time point — needs 2a + 2b for that tp
 ↓
2d  compute_performance_score() per time point — needs 2a + 2c (PCA weights)
```

**Equal weights are degenerate** (always 20.00 — mathematical identity). PCA or custom weights are required for meaningful scores. `process_all_timepoints()` enforces this: caller must provide `weights` or `pca_reference`.

Functions in `modules/preprocessing.py`: `compute_percentages()`, `validate_timepoint()`
Functions in `modules/analysis.py`: `derive_pca_weights()`, `compute_performance_score()`, `process_all_timepoints()`

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
2. Check raw student count stability between endpoints (>25% change → flag).
3. If valid, compute segment delta = `perf(t_{i+1}) - perf(t_i)`.

**Segment labels**:
- BoSY → EoSY = **Learning** (within-year gain)
- EoSY → next BoSY = **Retention** (over-summer change)

**Composite**: Sum of all available segment scores (= last perf - first perf). Decomposes exactly into segments.

**Output per school (one row)**:
```
School ID | metadata | Perf t0 | Perf t1 | Perf t2 |
  Seg 1 (Learning 24-25) | Seg 2 (Retention 24-25→25-26) |
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

### Step 4 — Output
- Output naming: `crla_progress_score.pca_derived.{chain_description}.xlsx`
- Existing single-year output reproducible (backward compatible)
- Notebook workflow notebook

## Unchanged
- Five reading profiles: Lower Emergent, Higher Emergent, Developing, Transitioning, Grade Level
- Grade structure: G1, G2 (MT/Fil), G3 (MT/Fil/Eng)

## Module Structure
```
modules/
  gcs_utils.py        — GCS filesystem, bucket paths
  preprocessing.py     — harmonization, loading, percentage conversion, per-tp validation
  analysis.py          — PCA weights, performance scoring, chain progress
  crla_v2.py           — original (untouched, for backward compat)
```

## Dependency Order (linear, no ambiguity)
```
Step 1 (done) → 2a → 2b → 2c → 2d (done) → Step 3 (done) → Step 4
```
