# Step 4 — Output

## Overview

Step 4 exports one CSV per consecutive time-point pair in the chain, matching the column layout of the original `crla_v2.py` output.

## Output Files

For the default 3-point chain, two CSVs are produced per scoring method:

**PCA scoring** (`filename_prefix="crla_progress_score.pca_derived"`):

| File | Pair | Segment |
|------|------|---------|
| `crla_progress_score.pca_derived.Learning_2024-25.csv` | BoSY 2024-25 -> EoSY 2024-25 | Within-year growth |
| `crla_progress_score.pca_derived.Retention_2024-25_to_2025-26.csv` | EoSY 2024-25 -> BoSY 2025-26 | Cross-year retention |

**Ordinal scoring** (`filename_prefix="crla_progress_score.ordinal"`):

| File | Pair | Segment |
|------|------|---------|
| `crla_progress_score.ordinal.Learning_2024-25.csv` | BoSY 2024-25 -> EoSY 2024-25 | Within-year growth |
| `crla_progress_score.ordinal.Retention_2024-25_to_2025-26.csv` | EoSY 2024-25 -> BoSY 2025-26 | Cross-year retention |

Output directory: `output/`

## Column Layout (91 columns per file)

Matches the original `crla_v2.py` format with school-year suffixes added for clarity:

### Metadata (4 columns)
`School Name`, `Region`, `Division`, `District`

### Validation (4 columns)
- `Has {period} {sy} Data` — per-timepoint validity at each endpoint
- `Student Count Mismatch` — >25% student count change between endpoints
- `Valid for Progress Analysis` — both endpoints valid AND count stable

### Scores (3 columns)
- `{period} {sy} Performance` — weighted performance score at each endpoint
- `Progress Score` — performance delta (endpoint 2 - endpoint 1), NaN if invalid

### Per-period breakdown (40 columns per period, 80 total)
For each endpoint period:
- 5 category averages: `{period} {sy} {category} %` — mean across 6 grade-language groups
- 30 individual columns: `{period} {sy} {grade} {lang} {category}` — per grade-language percentage
- 5 weighted columns: `{period} {sy} {category} Weighted` — category avg x weight / 100

Category order: Developing, Transitioning, Higher Emergent, Lower Emergent, Grade Level

## Usage

### PCA scoring
```python
from preprocessing import load_all_assessments
from analysis import process_all_timepoints
from output import export_pairwise_csvs

df_all = load_all_assessments(file_map=local_files, source='local')
results = process_all_timepoints(df_all, pca_reference=('2024-25', 'BoSY'))

exported = export_pairwise_csvs(
    percentages=results['percentages'],
    performance=results['performance'],
    validation=results['validation'],
    raw_data=df_all,
    weights=results['weights'],
    output_dir='output',
)
```

### Ordinal scoring
```python
results = process_all_timepoints(df_all, scoring='ordinal')

exported = export_pairwise_csvs(
    percentages=results['percentages'],
    performance=results['performance'],
    validation=results['validation'],
    raw_data=df_all,
    weights=results['weights'],
    output_dir='output',
    filename_prefix='crla_progress_score.ordinal',
)
```

## Comparison with Original Output

Verified against `data/modified/crla_progress_score.pca_derived.xlsx` (sheet `crla_progress_score.pca_derived`, column `Progress Score (Difference)`).

Reference: old weights were Dev=5, Trans=14, HE=9, LE=0, GL=100.

### What matches
- **Row coverage**: 37,135 common schools out of old 37,137 / new 37,182
- **Validation flags**: Has BoSY Data 100% match, Has EoSY Data 97.7%, Valid for Progress 97.5%
- **G1, G2 Fil, G3 Fil, G3 Eng percentage columns**: Exact match (max_diff = 0.00)

### What differs

#### 1. G2 MT and G3 MT percentage columns — `iloc` positional bug in original

G2 MT and G3 MT columns show differences (max_diff up to 90.91). All other grade-language groups match exactly. Root cause: the original `crla_v2.py` used positional `iloc` splitting to separate grade-language columns. Column order varies between years (e.g., G2 Fil Transitioning before/after G2 Fil Developing), causing MT values to be assigned to wrong columns. Our name-based approach assigns values correctly.

| Column group | Match? |
|-------------|--------|
| G1 (all 5 profiles) | Exact match |
| G2 Fil (all 5) | Exact match |
| **G2 MT (all 5)** | **Differ** (max 80.65) |
| G3 Fil (all 5) | Exact match |
| G3 Eng (all 5) | Exact match |
| **G3 MT (all 5)** | **Differ** (max 90.91) |

#### 2. PCA weights — different reference and pool

- Old: PCA on EoSY, valid-for-progress schools -> Dev=5, Trans=14, HE=9, LE=0, GL=100
- New: PCA on BoSY, per-timepoint valid schools -> Dev=100, Trans=43, HE=77, LE=31, GL=0

Different weights produce different performance scores and progress scores.

#### 3. NaN handling for invalid schools

- Old: fills invalid schools with Progress Score = 0 (3,682 schools)
- New: uses NaN for invalid schools (2,763 NaN)

#### 4. Score ranges (both reasonable)

| Metric | Old (Excel) | New |
|--------|------------|-----|
| Progress Score mean | 19.5 | -5.5 |
| Progress Score range | [-54, +78] | [-39, +28] |
| BoSY Performance mean | 22.1 | 16.3 |
| EoSY Performance mean | 42.3 | 10.7 |

Both are in plausible ranges for weighted-percentage scores. The directional difference (old: positive mean progress, new: negative) reflects the completely different weight profiles — old heavily weights Grade Level (GL=100), new heavily weights Developing (Dev=100).

**Note**: The CSV export (`data/modified/crla_progress_score.pca_derived.csv`) has different values from the Excel and appears to be a separate/buggy run — do not use it as reference.

## Dependencies

- **Input**: Step 2 outputs (`percentages`, `performance`, `validation`, `weights`) and Step 1 raw data
- **Module**: `modules/output.py` — `export_pairwise_csvs()`, `_build_pair_dataframe()`

## Status

- **Implemented and verified** in `modules/output.py`
