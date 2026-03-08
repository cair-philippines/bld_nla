# CRLA Multi-Year Reading Proficiency Analysis

## Abstract

The Classroom Reading Level Assessment (CRLA) is the Department of Education's standardized tool for measuring early-grade reading proficiency across Philippine public schools. This project implements a reproducible, multi-timepoint analytical pipeline that harmonizes raw CRLA data across school years, computes ordinal proficiency scores for each school, and tracks progress between consecutive assessment periods.

Three timepoints are currently covered: Beginning of School Year (BoSY) 2024-25, End of School Year (EoSY) 2024-25, and BoSY 2025-26. The pipeline produces segment-level deltas for each consecutive pair (BoSY 2024-25 to EoSY 2024-25 and EoSY 2024-25 to BoSY 2025-26), as well as a composite progress score across the full chain. Key results: the national mean ordinal score rose from 3.30 to 4.13 between BoSY and EoSY 2024-25 (+0.82), then declined to 3.06 by BoSY 2025-26 (-1.04), yielding a net composite of -0.14 across 29,854 schools with valid data at all three timepoints.

## Background

CRLA classifies each assessed learner into one of five reading proficiency levels, ordered from lowest to highest:

| Level | Abbreviation | Ordinal Weight |
|-------|-------------|----------------|
| Lower Emergent | LE | 1 |
| Higher Emergent | HE | 2 |
| Developing | Dev | 3 |
| Transitioning | Trans | 4 |
| Grade Level | GL | 5 |

Assessments are administered at the beginning (BoSY) and end (EoSY) of each school year, across three grade levels and multiple language groups:

| Grade-Language Group | Description |
|---------------------|-------------|
| G1 | Grade 1 (single assessment) |
| G2 MT | Grade 2, Mother Tongue |
| G2 Fil | Grade 2, Filipino |
| G3 MT | Grade 3, Mother Tongue |
| G3 Fil | Grade 3, Filipino |
| G3 Eng | Grade 3, English |

Each school's raw data consists of student counts per proficiency level for each of the 6 grade-language groups, yielding 30 reading profile columns per timepoint.

The central policy question this analysis addresses: **Are learners improving across assessment periods, and where should reading interventions be focused?**

## Data

### Input Files

| Timepoint | File | Approximate Schools |
|-----------|------|-------------------|
| BoSY 2024-25 | `CRLA Results Archive_SY 2024-25 Assessment Results_Table_BoSY.csv` | ~35,000 |
| EoSY 2024-25 | `CRLA Results Archive_SY 2024-25 Assessment Results_Table_EoSY.csv` | ~37,000 |
| BoSY 2025-26 | `CRLA National Dashboard_BoSY 2025-26 Assessment Results_Table.csv` | ~39,000 |

Raw files are located in `data/raw/`.

### Schema Hazards

The raw CSVs from different school years exhibit several inconsistencies that the pipeline resolves automatically:

1. **Column order differences**: 2024-25 places G2 Fil Transitioning before G2 Fil Developing; 2025-26 reverses them.
2. **Header typos**: `G2 FIl Higher Emergent` (capital I) appears in both years.
3. **Extra aggregate columns**: 2025-26 introduces per-grade Total Assessed columns not present in 2024-25.
4. **Encoding corruption**: Mojibake affecting approximately 28 school names per file (e.g., `ñ` corrupted to `¤`).

These are documented in detail in [`documentation/step_1_schema_harmonizer.md`](documentation/step_1_schema_harmonizer.md).

## Methodology

The pipeline follows four sequential steps. Each step has a corresponding detailed reference document in `documentation/`.

### Step 1 — Schema Harmonization

Raw CSVs from different school years are normalized into an identical 49-column schema (47 canonical columns + `school_year` and `period` metadata). Column matching is **name-based, not positional**, which avoids the column-swap bugs present in earlier positional (`iloc`) approaches.

Key operations:
- Header typo correction and whitespace normalization
- Canonical column ordering (30 reading profile columns in a fixed grade-language x proficiency sequence)
- Removal of aggregate Total columns
- Mojibake repair for school and geographic names

Reference: [`documentation/step_1_schema_harmonizer.md`](documentation/step_1_schema_harmonizer.md)

### Step 2 — Ordinal Scoring

For each school at each timepoint, raw student counts are converted to percentages within each grade-language group, then summarized into a single ordinal proficiency score on a 1-5 scale.

The ordinal score is a weighted average of the proficiency distribution:

```
ordinal_score = (pct_LE × 1 + pct_HE × 2 + pct_Dev × 3 + pct_Trans × 4 + pct_GL × 5) / 100
```

This yields a score between 1.0 (all learners at Lower Emergent) and 5.0 (all learners at Grade Level). A score of 3.30 means the average learner in that school is between the Developing and Transitioning levels.

**Why ordinal scoring over PCA**: An alternative PCA-based scoring method was explored, where weights are derived from the first principal component of the proficiency distribution. However, PCA weights proved unstable across reference timepoints — using BoSY as the reference produces substantially different weights than using EoSY (e.g., Grade Level receives weight 0 vs. weight 100 depending on reference choice). The ordinal method uses fixed, interpretable weights that are stable across timepoints and require no reference period.

| Property | PCA Scoring | Ordinal Scoring |
|----------|------------|-----------------|
| Scale | 0-100 (arbitrary) | 1-5 (proficiency levels) |
| Reference timepoint | Required | Not needed |
| Stability across timepoints | Weights change with reference | Fixed |
| Interpretability | Opaque | "Average proficiency level" |

Per-timepoint validation flags schools with insufficient data (e.g., missing grade-language groups or zero assessed learners).

Reference: [`documentation/step_2_percentages_and_scoring.md`](documentation/step_2_percentages_and_scoring.md)

### Step 3 — Chain-Based Progress Scoring

An ordered time chain defines the sequence of assessment periods:

```
BoSY 2024-25  →  EoSY 2024-25  →  BoSY 2025-26
```

For each consecutive pair in the chain, a **segment delta** is computed as the difference in ordinal scores between the two endpoints. Two cross-timepoint validation checks must pass for a segment to be considered valid:

1. Both endpoints must have valid per-timepoint data (from Step 2).
2. The total assessed student count must not change by more than 25% between endpoints (catches school mergers, splits, or data errors).

The **composite progress score** is the sum of all valid segment deltas for a given school, representing cumulative progress across the full chain.

The pipeline extends automatically when new timepoints are added — appending a new entry to the time chain produces new segment deltas without modifying any existing computations.

Reference: [`documentation/step_3_chain_progress.md`](documentation/step_3_chain_progress.md)

### Step 4 — Output

The pipeline exports one CSV per consecutive timepoint pair, with 91 columns matching the layout established by the original `crla_v2.py` reference implementation. Each file contains:

- School metadata (name, region, division, district)
- Validation flags (data availability, student count stability, analysis eligibility)
- Endpoint performance scores and the segment delta (progress score)
- Full percentage breakdowns and weighted scores for both timepoints

Reference: [`documentation/step_4_output.md`](documentation/step_4_output.md)

## Key Results

Using ordinal scoring across 29,854 schools with valid data at all three timepoints:

| Timepoint | National Mean Ordinal Score | Interpretation |
|-----------|---------------------------|----------------|
| BoSY 2024-25 | 3.30 | Between Developing and Transitioning |
| EoSY 2024-25 | 4.13 | Above Transitioning |
| BoSY 2025-26 | 3.06 | Just above Developing |

| Segment | Delta | Direction |
|---------|-------|-----------|
| BoSY 2024-25 → EoSY 2024-25 | +0.82 | Improvement |
| EoSY 2024-25 → BoSY 2025-26 | -1.04 | Decline |
| **Composite** | **-0.14** | **Slight net regression** |

The within-year gain (BoSY to EoSY 2024-25) indicates that schools moved learners upward by nearly a full proficiency level on average. However, the cross-year decline (EoSY 2024-25 to BoSY 2025-26) more than offset this gain, resulting in a small net regression over the full observation window.

## Repository Structure

```
project_crla/
│
├── modules/                          Analysis pipeline
│   ├── preprocessing.py              Schema harmonization, data loading, percentage
│   │                                 computation, per-timepoint validation
│   ├── analysis.py                   PCA weights, ordinal scoring, performance
│   │                                 scoring, chain-based progress
│   ├── output.py                     Pairwise CSV export (91-column layout)
│   ├── gcs_utils.py                  Google Cloud Storage paths and filesystem
│   └── crla_v2.py                    Original reference implementation (legacy)
│
├── documentation/                    Methodology references
│   ├── multi_year_expansion_plan.md  Overall pipeline design and rationale
│   ├── step_1_schema_harmonizer.md   Schema normalization details
│   ├── step_2_percentages_and_scoring.md  Scoring methodology comparison
│   ├── step_3_chain_progress.md      Chain-based progress scoring
│   └── step_4_output.md             Output format and verification
│
├── data/
│   ├── raw/                          Input CSVs (3 timepoints)
│   └── modified/                     Pipeline outputs and reference files
│
└── README.md
```

## Reproducibility

### Dependencies

- Python 3.11+
- pandas, numpy (data processing)
- scikit-learn (PCA scoring, optional)

### Running the Pipeline

**1. Load and harmonize data:**

```python
import sys
sys.path.insert(0, 'modules')
from preprocessing import load_all_assessments

# Local files
file_map = {
    ('2024-25', 'BoSY'): 'data/raw/CRLA Results Archive_SY 2024-25 Assessment Results_Table_BoSY.csv',
    ('2024-25', 'EoSY'): 'data/raw/CRLA Results Archive_SY 2024-25 Assessment Results_Table_EoSY.csv',
    ('2025-26', 'BoSY'): 'data/raw/CRLA National Dashboard_BoSY 2025-26 Assessment Results_Table.csv',
}
df_all = load_all_assessments(file_map=file_map, source='local')
```

**2. Compute ordinal scores and chain progress:**

```python
from analysis import process_all_timepoints, compute_chain_progress

TIME_CHAIN = [('2024-25', 'BoSY'), ('2024-25', 'EoSY'), ('2025-26', 'BoSY')]

results = process_all_timepoints(df_all, scoring='ordinal')
progress_df = compute_chain_progress(
    performance=results['performance'],
    raw_data=results['raw_data'],
    validation=results['validation'],
    time_chain=TIME_CHAIN,
)
```

**3. Export pairwise CSVs:**

```python
from output import export_pairwise_csvs

export_pairwise_csvs(
    progress_df=progress_df,
    results=results,
    time_chain=TIME_CHAIN,
    output_dir='data/modified',
    filename_prefix='crla_progress_score.ordinal',
)
```

### Data Access

Raw input files can be loaded from local paths (as shown above) or from Google Cloud Storage. The default configuration in `modules/gcs_utils.py` points to the GCS bucket `data_ecair_paaral/raw/`. For local execution, pass a custom `file_map` to `load_all_assessments()` as shown in the reproducibility steps.

### Adding New Timepoints

When new assessment data becomes available:

1. Place the raw CSV in `data/raw/`.
2. Add the corresponding `(school_year, period)` entry to `file_map` and `TIME_CHAIN`.
3. Re-run the pipeline. New segment deltas are computed automatically; existing segments are unchanged.
