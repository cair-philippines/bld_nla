# CRLA Multi-Year Reading Proficiency Analysis

## 1. Abstract

The Classroom Reading Level Assessment (CRLA) is the Department of Education's standardized tool for measuring early-grade reading proficiency across Philippine public schools. This project implements a reproducible analytical pipeline that harmonizes raw CRLA data across school years, quantifies each school's proficiency distribution through three statistical moments (mean, standard deviation, and skewness), tracks progress between consecutive assessment periods, and produces a principled priority ranking of schools for intervention targeting.

The pipeline covers five timepoints across two school years — BoSY 2024-25, EoSY 2024-25, BoSY 2025-26, MoSY 2025-26 (intervention subset), and EoSY 2025-26 — spanning approximately 39,000 schools and over 10 million assessed learners in Grades 1-3. Schools are evaluated on **within-school-year segments only** (BoSY → EoSY per school year), avoiding cross-year confounds such as summer learning loss. National results show within-year gains of +0.82 ordinal levels (SY 2024-25) and +1.10 ordinal levels (SY 2025-26).

To answer *where interventions should be focused*, the pipeline combines each school's academic need, student population size, and local government fiscal capacity into a composite priority score. Sensitivity analysis confirms that the resulting priority list is robust to methodological choices: the top-100 intervention targets are stable across 500 random weight configurations, with 60% of all ranked schools showing near-zero rank volatility.

## 2. Background

CRLA classifies each assessed learner into one of five reading proficiency levels, ordered from lowest to highest:

| Level | Abbreviation | Ordinal Value |
|-------|-------------|---------------|
| Lower Emergent | LE | 1 |
| Higher Emergent | HE | 2 |
| Developing | Dev | 3 |
| Transitioning | Trans | 4 |
| Grade Level | GL | 5 |

Assessments are administered at the beginning (BoSY) and end (EoSY) of each school year, across three grade levels and six grade-language groups:

| Grade-Language Group | Description |
|---------------------|-------------|
| G1 | Grade 1 (single assessment) |
| G2 MT | Grade 2, Mother Tongue |
| G2 Fil | Grade 2, Filipino |
| G3 MT | Grade 3, Mother Tongue |
| G3 Fil | Grade 3, Filipino |
| G3 Eng | Grade 3, English |

Each school's raw data consists of student counts per proficiency level for each grade-language group, yielding 30 columns per timepoint.

The central policy questions this analysis addresses:

1. **Are learners improving across assessment periods?**
2. **Where should reading interventions be focused?**

## 3. Data

### 3.1 CRLA Assessment Files

Assessment data is sourced from an automated Looker Studio exporter (`notebooks/0.2-export_data_from_crla_dashboard.ipynb`) that produces timestamped CSVs in `data/raw/dashboard_export/`. The pipeline's `resolve_latest_exports()` function automatically selects the most recent file per timepoint.

| Timepoint | Schools | Schema |
|-----------|---------|--------|
| BoSY 2024-25 | 35,280 | 50 cols (Type A) |
| EoSY 2024-25 | 37,045 | 50 cols (Type A) |
| BoSY 2025-26 | 38,981 | 53 cols (Type B) |
| MoSY 2025-26 | 38,297 | 47 cols (Type C — intervention subset) |
| EoSY 2025-26 | 38,322 | 53 cols (Type B) |

**Schema variants:** Type A (SY 2024-25) uses combined grade-level totals. Type B (SY 2025-26) uses per-language totals (`G2 Total MT Assessed`, etc.). Type C (MoSY) is missing G3 MT entirely (5 of 6 grade-language groups) — the pipeline fills these as NaN and validation handles the reduced group count gracefully.

**MoSY 2025-26** is a mid-year checkpoint administered only to schools participating in a specific literacy intervention. It is not a universal assessment — segments involving MoSY are computed only for the intervention subset.

### 3.2 External Data Sources

| Source | File | Purpose |
|--------|------|---------|
| DepEd School Level Database with PSGC | `SY 2024-2025 School Level Database WITH PSGC.xlsx` | Maps each School ID to a Philippine Standard Geographic Code (PSGC) municipality/city code |
| DOF BLGF Statement of Receipts and Expenditures | `By-LGU-SRE-2024.xlsx` | LGU-level revenue and expenditure data, including the Special Education Fund |
| Public enrollment (Project Bukas) | `public_project_bukas_enrollment_2024-25.csv` | School-level enrollment counts used to compute SEF per enrolled learner at the LGU level |

All input files are located in `data/raw/`.

### 3.3 Schema Hazards

The raw CRLA CSVs from different school years exhibit several inconsistencies that the pipeline resolves automatically:

1. **Column order differences**: 2024-25 places G2 Fil Transitioning before G2 Fil Developing; 2025-26 reverses them.
2. **Header typos**: `G2 FIl Higher Emergent` (capital I) appears in both years.
3. **Extra aggregate columns**: 2025-26 introduces per-grade Total Assessed columns not present in 2024-25.
4. **Encoding corruption**: Mojibake affecting approximately 28 school names per file (e.g., `ñ` corrupted to `¤`).
5. **Missing grade-language groups**: MoSY 2025-26 and EoSY 2025-26 are missing G3 MT columns entirely. The harmonizer fills these with NaN rather than failing.
6. **Dashboard export format**: Automated exports use decimal fractions (0.386) for aggregate percentages and raw integers for counts, while original archive files use percentage strings ("38.59%") and comma-separated quoted strings ("2,814"). The 30 canonical grade columns contain raw integer counts in both formats, so no conversion is needed for the pipeline's core computation.

Reference: [`documentation/step_1_schema_harmonizer.md`](documentation/step_1_schema_harmonizer.md)

## 4. Methodology

### 4.1 Schema Harmonization

Raw CSVs from different school years are normalized into an identical column schema. Column matching is **name-based, not positional**, which avoids column-swap bugs present in earlier positional (`iloc`) approaches. Operations include header typo correction, canonical column ordering of the 30 reading profile columns, removal of aggregate Total columns, and mojibake repair.

Reference: [`documentation/step_1_schema_harmonizer.md`](documentation/step_1_schema_harmonizer.md)

### 4.2 Ordinal Proficiency Scoring

For each school at each timepoint, raw student counts are first converted to percentages within each grade-language group, then summarized through three statistical moments that together characterize the school's proficiency distribution.

#### 4.2.1 Percentage Conversion

Within each of the six grade-language groups, raw counts are divided by the group total to obtain the proportion of learners at each proficiency level. Groups with zero assessed learners yield missing values.

#### 4.2.2 Ordinal Mean

The ordinal mean is a weighted average of the proficiency distribution, averaged across all grade-language groups with data:

```math
\bar{x}_s = \frac{1}{G} \sum_{g=1}^{G} \sum_{k=1}^{5} p_{s,g,k} \cdot w_k
```

where *p* is the percentage of learners in school *s*, grade-language group *g*, at proficiency level *k*, and *w* ∈ {1, 2, 3, 4, 5} are the ordinal values from Lower Emergent to Grade Level. The result is a score on the 1-5 scale: a value of 3.30 means the average learner in that school falls between the Developing and Transitioning levels.

**Why ordinal scoring over PCA.** An alternative PCA-based scoring method was explored, where weights are derived from the first principal component of the proficiency distribution. PCA weights proved unstable across reference timepoints — Grade Level receives weight 0 under a BoSY reference but weight 100 under an EoSY reference. The ordinal method uses fixed, interpretable weights that require no reference period.

| Property | PCA Scoring | Ordinal Scoring |
|----------|------------|-----------------|
| Scale | 0-100 (arbitrary) | 1-5 (proficiency levels) |
| Reference timepoint | Required | Not needed |
| Stability across timepoints | Weights change with reference | Fixed |
| Interpretability | Opaque | "Average proficiency level" |

#### 4.2.3 Ordinal Standard Deviation

The ordinal standard deviation measures how spread out a school's learners are across proficiency levels:

```math
\sigma_s = \sqrt{\frac{1}{G} \sum_{g=1}^{G} \sum_{k=1}^{5} p_{s,g,k} \cdot (w_k - \bar{x}_{s,g})^2}
```

A low SD indicates learners are clustered around the mean level; a high SD indicates a wide spread (e.g., many learners at both Grade Level and Lower Emergent). Higher SD signals greater within-school inequality.

#### 4.2.4 Ordinal Skewness

The ordinal skewness captures asymmetry in the proficiency distribution:

```math
\gamma_s = \frac{1}{G} \sum_{g=1}^{G} \frac{\sum_{k=1}^{5} p_{s,g,k} \cdot (w_k - \bar{x}_{s,g})^3}{\sigma_{s,g}^3}
```

Negative skewness (the national tendency) indicates a long lower tail — most learners are at higher levels but a subset remains at lower ones. Positive skewness indicates the reverse. Schools with zero SD (all learners at one level) have undefined skewness, treated as missing.

Reference: [`documentation/step_2_percentages_and_scoring.md`](documentation/step_2_percentages_and_scoring.md)

### 4.3 Validation

Each school is validated at two tiers. The **basic** tier requires at least one grade-language group with non-missing data. The **strict** tier, used for priority ranking, imposes three additional requirements:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Grade coverage | All three grade levels (G1, G2, G3) have at least one reporting group | Ensures the school's score reflects the full early-grade span |
| Group breadth | At least 4 of 6 grade-language groups reporting | Guards against scores driven by a single group |
| Minimum sample | At least 15 assessed learners in every reporting group | Ensures statistical stability of within-group percentages |

A segment delta between two timepoints additionally requires: (1) both endpoints pass basic validation, and (2) the total assessed student count does not change by more than 25% between endpoints.

```math
\text{valid\_segment} = \text{valid}_{t_0} \;\wedge\; \text{valid}_{t_1} \;\wedge\; \left(\frac{|N_{t_1} - N_{t_0}|}{N_{t_0}} \leq 0.25\right)
```

The count-stability check guards against school mergers, splits, or data-entry errors that would make a progress comparison misleading.

### 4.4 Within-School-Year Progress Scoring

Progress is measured **within each school year only** — no cross-year segments are computed. This avoids conflating school performance with summer learning loss and new-cohort effects.

Per-school-year chains define the assessment sequences:

```
SY 2024-25:  BoSY ──────────────────── EoSY
                   Learning_2024-25

SY 2025-26:  BoSY ──── MoSY ──── EoSY
                   BoSYMoSY  MoSYEoSY
                   └── Learning_2025-26 ──┘
```

For each segment pair, the **segment delta** is the change in ordinal mean:

```math
\Delta_i = \bar{x}_{t_{i+1}} - \bar{x}_{t_i}
```

| Segment | Pair | Scope |
|---------|------|-------|
| `Learning_2024-25` | BoSY → EoSY 2024-25 | All schools |
| `Learning_2025-26` | BoSY → EoSY 2025-26 | All schools |
| `BoSYMoSY_2025-26` | BoSY → MoSY 2025-26 | Intervention subset |
| `MoSYEoSY_2025-26` | MoSY → EoSY 2025-26 | Intervention subset |

The **composite progress score** is the sum of the two full-year Learning segment deltas, representing cumulative within-year progress across both school years:

```math
\Delta_{\text{composite}} = \Delta_{\text{Learning\_2024-25}} + \Delta_{\text{Learning\_2025-26}}
```

Schools must have valid data at both endpoints of a segment to receive a delta. The composite requires valid data in both school years.

Segment deltas are also computed for SD and skewness, tracking how distributional shape changes over time. The pipeline extends automatically when new school years are added to `SCHOOL_YEAR_CHAINS`.

Reference: [`documentation/step_3_chain_progress.md`](documentation/step_3_chain_progress.md), [`documentation/within_year_evaluation.md`](documentation/within_year_evaluation.md)

### 4.5 LGU Matching

To incorporate local government fiscal data into the priority ranking, each school must be linked to its municipality or city. The pipeline builds a **school-to-LGU crosswalk** by joining three data sources:

1. **CRLA data** provides the School ID.
2. **DepEd PSGC database** maps School ID to a PSGC municipality/city code.
3. **DOF BLGF data** provides LGU-level revenue figures, matched to PSGC codes via a cascading multi-pass strategy (exact match, cross-region match for NIR boundary issues, independent city resolution, and fuzzy matching).

Coverage: 1,631 of 1,634 cities/municipalities matched (99.8%), covering 99.0% of CRLA schools.

Reference: [`documentation/lgu_matching.md`](documentation/lgu_matching.md)

### 4.6 Priority Ranking

Schools passing strict validation are ranked for intervention targeting using a three-pillar composite. Each pillar captures a distinct dimension of priority:

**Pillar 1 — Need.** A weighted sum of standardized (z-scored) ordinal moment components:

```math
\text{Need}_s = \sum_{j} \alpha_j \cdot z(c_{s,j})
```

where *c* are six need components and *α* are their weights:

| Component | Weight | Direction | Interpretation |
|-----------|--------|-----------|----------------|
| 5 − mean | 2.0 | Lower mean = higher need | Current proficiency level |
| −delta mean | 2.0 | Declining trajectory = higher need | Direction of change |
| SD (endpoint) | 1.0 | Higher spread = higher need | Within-school inequality |
| Skewness (endpoint) | 1.0 | Positive skew = higher need | Distribution shape |
| delta SD | 0.5 | Increasing spread = higher need | Change in inequality |
| delta skewness | 0.5 | Worsening skew = higher need | Change in distribution shape |

**Pillar 2 — Impact.** The total number of assessed learners at the segment endpoint. Schools with more students represent a larger potential impact per intervention.

**Pillar 3 — Capacity Gap.** The inverse of the LGU's Special Education Fund (SEF) per enrolled learner:

```math
\text{SEF per capita} = \frac{\text{LGU Special Education Fund}}{\text{Total enrolled learners in LGU}}
```

The SEF is a component of Real Property Tax revenue earmarked for education. Lower SEF per capita indicates the LGU has fewer resources available per student, representing a greater capacity gap. Enrollment counts are sourced from the SY 2024-25 public enrollment dataset, aggregated to the LGU level via the school-PSGC crosswalk.

**Composite.** Each pillar is converted to a percentile rank, then the composite is their product:

```math
\text{Priority}_s = R_{\%}(\text{Need}_s) \;\times\; R_{\%}(\text{Impact}_s) \;\times\; R_{\%}(\text{CapacityGap}_s)
```

Percentile ranks map each pillar to a uniform [0, 1] distribution regardless of its raw distribution shape. This is critical because assessed counts (skewness ≈ 5) and SEF per capita are heavily right-skewed — without this transformation, a handful of outlier schools would dominate the composite. The multiplicative form ensures a school must score high on **all three** dimensions to rank at the top.

Reference: [`documentation/priority_ranking.md`](documentation/priority_ranking.md)

### 4.7 Sensitivity Analysis

The Need pillar weights *α* are chosen by domain judgment, not estimated from data. To assess how much the final rankings depend on these choices, two analyses are conducted:

**Scenario comparison.** Five interpretable weight profiles — default, level-focused, delta-focused, mean-only, and equal — are compared using Kendall τ rank correlation (across all ranked schools) and Jaccard overlap (of the top-*N* lists).

**Per-school robustness.** 500 random weight profiles are drawn from a Dirichlet distribution (α = 2.0). For each school, the analysis reports the median priority percentile, interquartile range (IQR) of priority percentile, and the fraction of draws in which the school appears in the top-100. Schools with `frac_top_100 = 100%` are robust intervention targets whose ranking does not depend on the weight specification.

Reference: [`documentation/sensitivity_analysis.md`](documentation/sensitivity_analysis.md)

## 5. Key Results

### 5.1 National Proficiency Trends

| Timepoint | Mean | SD | Skewness | Interpretation |
|-----------|------|-----|----------|----------------|
| BoSY 2024-25 | 3.30 | 1.07 | -0.49 | Between Developing and Transitioning |
| EoSY 2024-25 | 4.13 | 0.87 | -1.18 | Above Transitioning |
| BoSY 2025-26 | 3.06 | 1.08 | -0.31 | Just above Developing |
| MoSY 2025-26 | 3.23 | 0.96 | -0.41 | Between Developing and Transitioning |
| EoSY 2025-26 | 4.15 | 0.83 | -1.13 | Above Transitioning |

| Segment | Mean Delta | Schools (strict) |
|---------|-----------|-----------------|
| Learning 2024-25 (BoSY → EoSY) | **+0.82** | 22,206 |
| Learning 2025-26 (BoSY → EoSY) | **+1.10** | 19,605 |
| BoSYMoSY 2025-26 (intervention subset) | +0.56 | 9,061 |
| MoSYEoSY 2025-26 (intervention subset) | +0.56 | 9,722 |

Both school years show strong within-year gains. SY 2025-26 shows an even larger improvement (+1.10) than SY 2024-25 (+0.82), with the national EoSY mean reaching 4.15 — above the Transitioning level. The intervention subset shows balanced gains across both halves of the year (+0.56 each).

### 5.2 Validation Coverage

| Tier | BoSY 2024-25 | EoSY 2024-25 | BoSY 2025-26 | MoSY 2025-26 | EoSY 2025-26 |
|------|-------------|-------------|-------------|-------------|-------------|
| Basic | 35,280 (100%) | 37,042 (>99%) | 38,980 (>99%) | 38,297 (100%) | 38,322 (100%) |
| Strict | 22,961 (65%) | 24,380 (66%) | 24,303 (62%) | 14,182 (37%) | 23,042 (60%) |

| Cross-timepoint tier | Schools |
|---------------------|---------|
| Both Learning segments strict (2024-25 + 2025-26) | 16,824 |

MoSY strict rate is 37% because (a) it is an intervention subset and (b) G3 MT data is absent, reducing group breadth for some schools.

### 5.3 Priority Ranking

**Per-segment rankings:**

| Segment | Strict-Valid | Ranked | Dropped |
|---------|------------|--------|---------|
| Learning 2024-25 | 22,206 | 22,114 | 92 |
| BoSYMoSY 2025-26 | 9,061 | 8,996 | 65 |
| MoSYEoSY 2025-26 | 9,722 | 9,652 | 70 |
| Learning 2025-26 | 19,605 | 19,441 | 164 |

**Composite ranking** (both Learning segments, stakeholder-facing output):

| Metric | Value |
|--------|-------|
| Valid in both years (strict) | 16,824 |
| Ranked (composite) | 16,765 |
| Output file | `output/priority_ranking_composite.xlsx` |

The composite ranking uses the average of both Learning segment deltas for the Need pillar, EoSY 2025-26 as the proficiency endpoint, and assessed learner count at EoSY 2025-26 for Impact.

### 5.4 Sensitivity Analysis

**Scenario comparison** (Segment 1):

| Pair | Kendall τ | Top-100 Jaccard |
|------|--------------|-----------------|
| Default vs Mean-only | 0.917 | 88.7% |
| Default vs Equal | 0.935 | 83.5% |
| Default vs Level-focused | 0.858 | 66.7% |
| Default vs Delta-focused | 0.820 | 57.5% |

**Robustness** (500 Dirichlet draws, Segment 1):

| Stability Tier | IQR Threshold | Schools | Share |
|---------------|--------------|---------|-------|
| Stable | IQR < 0.05 | 10,703 | 60% |
| Moderate | 0.05 ≤ IQR < 0.15 | 6,517 | 37% |
| Volatile | IQR ≥ 0.15 | 616 | 3% |

The overall rank ordering is robust (Kendall τ > 0.82 across all scenario pairs). The main axis of sensitivity is the relative emphasis on current proficiency levels versus trajectory — not the inclusion of SD or skewness.  Schools appearing in the top-100 across 100% of random weight draws are the strongest intervention candidates.

### 5.5 Validation Against Prior School List

A previously curated list of 131 priority schools (identified using the earlier PCA-based method) was compared against the current pipeline's Learning segment (BoSY → EoSY 2024-25) priority ranking. All 131 School IDs are unique (authoritative source: `output/bbi_annex_b_school_ids.txt`). Of these, 66 passed strict validation and appeared in the current ranking, while 65 were excluded due to insufficient data — primarily too few assessed learners for reliable ordinal statistics.

Reference: [`documentation/old_list_comparison.md`](documentation/old_list_comparison.md)

## 6. Repository Structure

```
project_crla/
│
├── modules/                           Analysis pipeline
│   ├── preprocessing.py               Schema harmonization, data loading,
│   │                                  percentage conversion, validation
│   ├── analysis.py                    Ordinal moments, performance scoring,
│   │                                  chain-based progress
│   ├── output.py                      Pairwise CSV export
│   ├── priority_ranking.py            Three-pillar priority ranking
│   ├── sensitivity_analysis.py        Need weight sensitivity and robustness
│   ├── lgu_matching.py                School-to-LGU crosswalk and revenue matching
│   ├── gcs_utils.py                   Google Cloud Storage paths and filesystem
│   └── crla_v2.py                     Original reference implementation (legacy)
│
├── documentation/                     Detailed methodology references
│   ├── multi_year_expansion_plan.md   Overall pipeline design and rationale
│   ├── within_year_evaluation.md      Within-school-year evaluation workflow
│   ├── step_1_schema_harmonizer.md    Schema normalization details
│   ├── step_2_percentages_and_scoring.md  Scoring methodology comparison
│   ├── step_3_chain_progress.md       Chain-based progress scoring
│   ├── step_4_output.md               Output format and verification
│   ├── priority_ranking.md            Three-pillar ranking methodology
│   ├── sensitivity_analysis.md        Weight sensitivity and robustness results
│   ├── lgu_matching.md                School-to-LGU crosswalk methodology
│   ├── old_list_comparison.md         131-school legacy list validation
│   ├── policy_brief_crla_methodology.md  One-page policy brief
│   └── dashboard_plan.md              Streamlit dashboard specifications
│
├── notebooks/                         Stakeholder presentation notebooks
│   ├── 0.2-export_data_from_crla_dashboard.ipynb  Automated Looker Studio exporter
│   ├── 1.0_methodology_walkthrough.ipynb   Three-pillar methodology explainer
│   ├── 2.0_portfolio_analysis_131_schools.ipynb  Legacy list re-evaluation
│   └── 3.0_cycle2_interpretability.ipynb   Cycle 2 interpretability analysis
│
├── dashboard/                         Interactive Streamlit dashboard
│   ├── app.py                         Application router
│   ├── pages/                         Dashboard views
│   └── data/                          Pre-computed dashboard data
│
├── data/
│   ├── raw/                           Input CSVs and external data files
│   │   └── dashboard_export/          Automated Looker Studio CSV exports
│   └── modified/                      Crosswalks and reference files
│
├── output/                            Pipeline outputs
│   ├── priority_ranking_composite.xlsx  Composite ranking (stakeholder-facing)
│   ├── priority_ranking_sef.*.csv     Priority rankings by segment
│   ├── sensitivity_*.csv              Sensitivity analysis outputs
│   └── crla_progress_score.*.csv      Pairwise progress CSVs
│
└── README.md
```

## 7. Reproducibility

### 7.1 Dependencies

- Python 3.11+
- pandas, numpy (data processing)
- scipy (sensitivity analysis)
- scikit-learn (legacy PCA scoring comparison only)
- openpyxl (Excel parsing for PSGC and BLGF data)

### 7.2 Running the Pipeline

**1. Load and harmonize data:**

```python
import sys
sys.path.insert(0, 'modules')
from preprocessing import resolve_latest_exports, load_all_assessments

# Automatically finds the most recent CSV per timepoint from dashboard_export/
file_map = resolve_latest_exports()
df_all = load_all_assessments(file_map=file_map, source='local')
```

**2. Compute ordinal moments and chain progress:**

```python
from analysis import process_all_timepoints, compute_chain_progress

results = process_all_timepoints(df_all, scoring='ordinal')
progress_df = compute_chain_progress(
    performance=results['performance'],
    raw_data=df_all,
    validation=results['validation'],
    ordinal_sd=results['ordinal_sd'],
    ordinal_skew=results['ordinal_skew'],
)
```

**3. Generate priority rankings:**

```python
from analysis import _build_segment_pairs, _segment_label
from lgu_matching import load_deped_psgc, load_lgu_revenue, build_school_lgu_crosswalk, match_lgu_revenue
from priority_ranking import compute_priority_ranking

psgc_df = load_deped_psgc('data/raw/SY 2024-2025 School Level Database WITH PSGC.xlsx')
crosswalk_df = build_school_lgu_crosswalk(psgc_df)
lgu_revenue_df = load_lgu_revenue('data/raw/By-LGU-SRE-2024.xlsx')
matched_lgu_df, unmatched_df, match_log = match_lgu_revenue(crosswalk_df, lgu_revenue_df)

for seg_idx, (t0, t1) in enumerate(_build_segment_pairs()):
    ranking_df, summary = compute_priority_ranking(
        progress_df, seg_idx,
        crosswalk_df=crosswalk_df, matched_lgu_df=matched_lgu_df,
    )
    label = _segment_label(t0, t1)
    ranking_df.to_csv(f'output/priority_ranking_sef.{label}.csv')
```

**4. Run sensitivity analysis:**

```python
from sensitivity_analysis import run_scenario_comparison, run_robustness_analysis

for seg_idx, (t0, t1) in enumerate(_build_segment_pairs()):
    scen = run_scenario_comparison(progress_df, seg_idx, crosswalk_df=crosswalk_df, matched_lgu_df=matched_lgu_df)
    rob = run_robustness_analysis(progress_df, seg_idx, crosswalk_df=crosswalk_df, matched_lgu_df=matched_lgu_df)
```

### 7.3 Data Access

Raw input files can be loaded from local paths (as shown above) or from Google Cloud Storage. The default configuration in `modules/gcs_utils.py` points to the GCS bucket `data_ecair_paaral/raw/`. For local execution, pass a custom `file_map` to `load_all_assessments()` as shown above.

### 7.4 Adding New Timepoints

When new assessment data becomes available:

1. Export the CSV via the automated Looker Studio exporter (notebook `0.2`) or place it manually in `data/raw/dashboard_export/` following the naming convention `CRLA_{period}_{school_year}_{timestamp}.csv`.
2. If adding a new school year or period type (e.g., MoSY), add the corresponding entry to `SCHOOL_YEAR_CHAINS` in `modules/analysis.py`.
3. Re-run the pipeline. `resolve_latest_exports()` automatically picks up the new file. New within-year segment deltas and priority rankings are computed automatically; existing segments are unchanged.

## 8. AI Disclosure

AI coding assistants (Claude, Anthropic) were used during the development of this project for code review, documentation drafting, and structured prompt generation. All methodological decisions, domain interpretations, and final outputs were made and validated by the ECAIR team. The underlying data, analytical logic, and policy framing reflect human judgment; AI tools served as a productivity aid, not a decision-maker.
