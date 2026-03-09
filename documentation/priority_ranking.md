# Priority Ranking for Intervention Targeting

## Overview

The priority ranking module produces a principled school-level list for each assessment segment, identifying which schools need the most attention based on three complementary dimensions. A school must score high on **all three pillars** to rank at the top — being high-need but tiny, or large but well-funded, does not alone push a school to the top of the list.

## Three-Pillar Framework

### Pillar 1 — Need (Weighted Z-Scores)

Captures how much a school's learners are struggling, using all three ordinal moments at the segment endpoint and their segment deltas:

| Component | Weight | Direction | Interpretation |
|-----------|--------|-----------|----------------|
| `level_mean` | 2.0 | `5 - mean_end` | Lower mean → higher need |
| `delta_mean` | 2.0 | `-delta_mean` | Negative delta (decline) → higher need |
| `level_sd` | 1.0 | `sd_end` | Higher spread → more inequality → higher need |
| `level_skew` | 1.0 | `skew_end` | Positive skew → long left tail → higher need |
| `delta_sd` | 0.5 | `delta_sd` | Increasing spread → higher need |
| `delta_skew` | 0.5 | `delta_skew` | Increasing right-skew → higher need |

Each component is standardized to z-scores before weighting. The weighted sum produces the need score. Mean and delta components receive double weight (2.0) as they are the primary indicators; SD and skewness receive lower weight (1.0 and 0.5) as secondary distributional signals.

### Pillar 2 — Impact (Assessed Count)

Raw count of assessed learners at the segment endpoint. Prioritizes schools where interventions affect the most students.

### Pillar 3 — Capacity Gap (Inverse SEF per Capita)

Measures how resource-constrained the school's LGU is, using the **Special Education Fund (SEF)** from the DOF BLGF Statement of Receipts and Expenditures (2024).

**Metric**: LGU SEF ÷ total enrolled learners in the LGU

The SEF is a component of Real Property Tax revenue earmarked for education. Per-capita SEF provides a proxy for how thinly the LGU's education-earmarked revenue is spread across its student population. Enrollment counts are sourced from the SY 2024-25 public enrollment dataset (`public_project_bukas_enrollment_2024-25.csv`), aggregated to the LGU level via the school-PSGC crosswalk.

Schools in LGUs with lower SEF per capita have a larger capacity gap. The capacity gap score is the z-score of the negated SEF per capita (lower SEF/capita → higher capacity gap score).

## Composite Score

The composite priority score is the **product of percentile ranks** across all three pillars:

```
priority_score = need_pctile × impact_pctile × capacity_gap_pctile
```

### Why percentile ranks (not min-max scaling)

Both assessed counts and SEF/capita have extreme right-skewness. With min-max scaling, a handful of outlier schools dominate one pillar and the composite becomes effectively single-pillar. Percentile ranks map any distribution to a uniform [0, 1] range, ensuring each pillar contributes equally regardless of its raw distribution shape.

## Eligibility

Only schools passing `valid_strict` at the segment's endpoint are eligible for ranking:

- All three grade levels covered (G1 + G2 + G3)
- At least 4 of 6 grade-language groups reporting
- At least 20 assessed learners in every reporting group

Schools are further dropped if they are missing any of: ordinal mean, delta mean, assessed count, or SEF per capita (typically due to missing LGU crosswalk data).

## Default Need Weights

```python
DEFAULT_NEED_WEIGHTS = {
    "level_mean": 2.0,
    "delta_mean": 2.0,
    "level_sd": 1.0,
    "level_skew": 1.0,
    "delta_sd": 0.5,
    "delta_skew": 0.5,
}
```

These are configurable via the `need_weights` parameter. Sensitivity analysis across different weight configurations is planned.

## Output Columns

Each row represents one ranked school. Columns:

| Column | Description |
|--------|-------------|
| `school_name` | School name |
| `division` | DepEd division |
| `region` | DepEd region |
| `mean_end` | Ordinal mean at segment endpoint (1-5 scale) |
| `sd_end` | Ordinal SD at segment endpoint |
| `skew_end` | Ordinal skewness at segment endpoint |
| `delta_mean` | Change in ordinal mean across the segment |
| `delta_sd` | Change in SD across the segment |
| `delta_skew` | Change in skewness across the segment |
| `assessed_count` | Total assessed learners at endpoint |
| `lgu_name` | Matched LGU name |
| `lgu_sef` | LGU Special Education Fund (PHP) |
| `sef_per_capita` | SEF ÷ total enrolled learners in LGU |
| `need_score` | Pillar 1 weighted z-score |
| `impact_score` | Pillar 2 raw assessed count |
| `capacity_gap_score` | Pillar 3 z-score of negated SEF/capita |
| `need_pctile` | Percentile rank of need score |
| `impact_pctile` | Percentile rank of impact score |
| `capacity_gap_pctile` | Percentile rank of capacity gap score |
| `priority_score` | Composite (product of percentile ranks) |
| `priority_pctile` | Percentile rank of composite score |

## Output Files

Saved to `output/`:

| File | Segment | Schools Ranked |
|------|---------|---------------|
| `priority_ranking.Learning_2024-25.csv` | BoSY → EoSY 2024-25 | ~17,800 |
| `priority_ranking.Retention_2024-25_to_2025-26.csv` | EoSY 2024-25 → BoSY 2025-26 | ~16,700 |

## Module Reference

All functions are in `modules/priority_ranking.py`:

| Function | Purpose |
|----------|---------|
| `compute_priority_ranking(...)` | Main ranking function — filters, scores, and ranks schools for one segment |
| `_z_score(s)` | Standardize a Series to z-scores (returns 0 for constant series) |

## Data Dependencies

- `progress_df`: Output of `compute_chain_progress()` with ordinal SD/skew enabled
- `crosswalk_df`: School-to-LGU crosswalk (from `build_school_lgu_crosswalk()`)
- `matched_lgu_df`: LGU revenue data with matched PSGC codes (from `match_lgu_revenue()`)
- `_total_assessed_cache`: Must be populated by calling `compute_percentages()` first
