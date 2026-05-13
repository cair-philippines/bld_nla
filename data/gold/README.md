# Gold Layer — School-Level Analytical Indicators

Analytical indicators derived from silver parquets for two reading assessment instruments:
**CRLA** (Grades 1–3) and **PhilIRI** (Grades 4–10, split into KS2 and KS3).

Rebuild:
```bash
python scripts/build_silver.py --crla --philiri --rma
python scripts/build_gold.py
python scripts/build_gold_philiri.py
python scripts/build_gold_rma.py
```

Methodology references: `documentation/philiri_gold_methodology.md`

---

## File Inventory

| File | Rows | Schools | Description |
|---|---|---|---|
| `crla_school_timepoints.parquet` | 188,348 | 39,447 | One row per school × timepoint (5 timepoints) |
| `crla_school_segments.parquet` | 259,148 | 39,335 | One row per school × segment pair (7 segments) |
| `philiri_ks2_school_timepoints.parquet` | 147,687 | 38,966 | KS2 one row per school × timepoint (4 timepoints) |
| `philiri_ks2_school_segments.parquet` | 73,319 | 38,726 | KS2 one row per school × within-year segment (2 segments) |
| `philiri_ks2_bosy_yoy.parquet` | 34,593 | 34,593 | KS2 year-over-year BoSY comparison, one row per school |
| `philiri_ks3_school_timepoints.parquet` | 41,446 | 11,004 | KS3 one row per school × timepoint (4 timepoints) |
| `philiri_ks3_school_segments.parquet` | 20,496 | 10,923 | KS3 one row per school × within-year segment (2 segments) |
| `philiri_ks3_bosy_yoy.parquet` | 9,573 | 9,573 | KS3 year-over-year BoSY comparison, one row per school |

---

## Conventions

### Join key
`School ID` (int64) is the shared key across all files and links to the school
crosswalk at `data/gold/public_school_id_crosswalk.parquet` in project_coordinates.

### NaN semantics
A `NaN` in any computed column means the underlying data was absent or had a zero
denominator for that school at that timepoint. NaN propagates honestly — no rows are
excluded; every school in the silver layer has a row in the gold layer.

### `groups_with_data`
Integer count of grade-language groups that had complete data (all level columns
non-null, non-zero denominator) at a given timepoint. Maximum values:

| File | Max groups |
|---|---|
| CRLA | 6 (G1, G2 MT, G2 Fil, G3 MT, G3 Fil, G3 Eng) |
| PhilIRI KS2 | 6 (G4–G6 × Fil/Eng) |
| PhilIRI KS3 | 8 (G7–G10 × Fil/Eng) |

~97–98% of schools reach the maximum. Schools below the maximum typically have a
full language missing across all grades (appearing at even values: 2, 4, 6).
`groups_with_data` is present only in timepoint files; use it as a filter or
display annotation — it does not gate any computed metric.

### Ordinal scales

**CRLA** — 5-level scale used at all timepoints and segments:

| Ordinal | Level |
|---|---|
| 1 | Low Emergent (LE) |
| 2 | Low Fluency (LF) |
| 3 | Low Average (LA) |
| 4 | Low Distinguished (LD) |
| 5 | Grade Level (GL) |

**PhilIRI timepoints and segments** — 3-level collapsed scale:

| Ordinal | Level | BoSY source categories |
|---|---|---|
| 1 | Frustration | 2LD Frustration, 3LD Instructional, 3LD Frustration |
| 2 | Instructional | 2LD Instructional, 3LD Independent |
| 3 | Independent | 2LD Independent, Grade Ready |

**PhilIRI YoY BoSY** — 7-level native BoSY scale:

| Ordinal | Level |
|---|---|
| 1 | 3LD Frustration |
| 2 | 3LD Instructional |
| 3 | 3LD Independent |
| 4 | 2LD Frustration |
| 5 | 2LD Instructional |
| 6 | 2LD Independent |
| 7 | Grade Ready |

**Scales are not comparable across instruments.** CRLA `ordinal_mean` (1–5) and
PhilIRI `ordinal_mean` (1–3) measure different things on different scales.

---

## Schemas

### `crla_school_timepoints.parquet`

| Column | Description |
|---|---|
| `School ID` | School identifier |
| `school_year` | `2024-25` or `2025-26` |
| `period` | `BoSY`, `MoSY`, or `EoSY` |
| `timepoint_label` | e.g. `BoSY 2024-25` |
| `total_assessed` | Total students assessed at this timepoint |
| `groups_with_data` | Count of grade-language groups with complete data (max 6) |
| `ordinal_overall` | Mean ordinal across all 6 grade-language groups (= `ordinal_mean`) |
| `ordinal_G1` | Ordinal score for G1 |
| `ordinal_G2` | Mean ordinal across G2 MT and G2 Fil |
| `ordinal_G3` | Mean ordinal across G3 MT, G3 Fil, G3 Eng |
| `pct_gl` | Mean % of assessed students at Grade Level across all groups |
| `ordinal_mean` | Mean ordinal across all groups (5-level scale, 1–5) |
| `ordinal_sd` | SD of ordinal distribution across groups |
| `ordinal_skew` | Skewness |
| `ordinal_kurt` | Excess kurtosis |
| `bimodality_coef` | BC = (skew² + 1) / regular kurtosis |
| `School Name`, `Region`, `Division`, `District` | Metadata |
| `ordinal_G2_MT`, `ordinal_G2_Fil` | Per-group ordinal scores for G2 |
| `ordinal_G3_MT`, `ordinal_G3_Fil`, `ordinal_G3_Eng` | Per-group ordinal scores for G3 |

### `crla_school_segments.parquet`

Segments span consecutive timepoint pairs within a school year chain.
`seg_idx` orders segments chronologically (0 = earliest).

| Column | Description |
|---|---|
| `School ID` | School identifier |
| `tp_from` | Starting timepoint label, e.g. `BoSY 2024-25` |
| `tp_to` | Ending timepoint label |
| `segment_label` | e.g. `Learning_2024-25` |
| `seg_idx` | Chronological index of this segment |
| `delta_mean` | `ordinal_mean(tp_to) − ordinal_mean(tp_from)` |
| `delta_sd` | Change in SD |
| `delta_skew` | Change in skewness |
| `emd_mean` | Mean Earth Mover's Distance (Wasserstein-1) across groups |

### `philiri_{ks}_school_timepoints.parquet`

| Column | Description |
|---|---|
| `School ID` | School identifier |
| `school_year` | `2024-25` or `2025-26` |
| `period` | `BoSY` or `EoSY` |
| `ks` | `ks2` or `ks3` |
| `timepoint_label` | e.g. `BoSY 2024-25` |
| `total_assessed` | Total students assessed |
| `groups_with_data` | Count of grade-language groups with complete data (max 6 KS2, 8 KS3) |
| `ordinal_mean` | Mean ordinal across groups (3-level scale, 1–3) |
| `ordinal_sd` | SD of ordinal distribution across groups |
| `ordinal_skew` | Skewness |
| `ordinal_kurt` | Excess kurtosis |
| `bimodality_coef` | BC = (skew² + 1) / regular kurtosis |
| `pct_grade_ready` | **BoSY only** — mean % classified as Grade Ready across groups |
| `pct_3ld` | **BoSY only** — mean % in any 3LD category across groups |
| `Region`, `Division`, `District`, `School Name` | Metadata |

`pct_grade_ready` and `pct_3ld` are `NaN` for EoSY rows (EoSY has no Grade Ready category).

### `philiri_{ks}_school_segments.parquet`

One segment per school year: `Learning_2024-25` (BoSY→EoSY) and `Learning_2025-26`.
Uses the 3-level collapsed scale at both endpoints.

| Column | Description |
|---|---|
| `School ID` | School identifier |
| `ks` | `ks2` or `ks3` |
| `school_year` | School year of the segment |
| `segment_label` | `Learning_2024-25` or `Learning_2025-26` |
| `delta_mean` | `ordinal_mean(EoSY) − ordinal_mean(BoSY)` on 3-level scale |
| `delta_sd` | Change in SD |
| `delta_skew` | Change in skewness |
| `emd_mean` | Mean Earth Mover's Distance across groups |

### `philiri_{ks}_bosy_yoy.parquet`

Compares BoSY 2024-25 to BoSY 2025-26 using the 7-level native BoSY scale.
One row per school appearing in both BoSY datasets.

| Column | Description |
|---|---|
| `School ID` | School identifier |
| `ks` | `ks2` or `ks3` |
| `delta_mean` | `ordinal_mean(2025-26) − ordinal_mean(2024-25)` on 7-level scale |
| `delta_sd` | Change in SD |
| `delta_skew` | Change in skewness |
| `delta_pct_grade_ready` | Change in Grade Ready fraction (percentage points) |
| `delta_pct_3ld` | Change in deep-need (3LD) fraction (percentage points) |
| `emd_mean` | Mean Earth Mover's Distance between the two BoSY distributions |
| `count_stable` | `True` if \|assessed_2526 − assessed_2425\| / assessed_2425 ≤ 0.25 — informational; does not gate any metric |
