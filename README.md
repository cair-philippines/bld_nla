# CRLA Multi-Year Reading Proficiency Analysis

## 1. Abstract

The Classroom Reading Level Assessment (CRLA) is the Department of Education's standardized tool for measuring early-grade reading proficiency across Philippine public schools. This project implements a reproducible analytical pipeline that harmonizes raw CRLA data across school years, quantifies each school's proficiency distribution through three statistical moments (mean, standard deviation, and skewness), tracks progress between consecutive assessment periods, and produces a principled priority ranking of schools for intervention targeting.

The pipeline currently covers three timepoints — BoSY 2024-25, EoSY 2024-25, and BoSY 2025-26 — spanning approximately 39,000 schools and over 10 million assessed learners in Grades 1-3. National results show a within-year gain of +0.82 ordinal levels (BoSY to EoSY 2024-25) followed by a cross-year decline of -1.04 (EoSY 2024-25 to BoSY 2025-26), yielding a net regression of -0.14 across the observation window.

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

| Timepoint | File | Schools |
|-----------|------|---------|
| BoSY 2024-25 | `CRLA Results Archive_SY 2024-25 Assessment Results_Table_BoSY.csv` | 35,280 |
| EoSY 2024-25 | `CRLA Results Archive_SY 2024-25 Assessment Results_Table_EoSY.csv` | 37,045 |
| BoSY 2025-26 | `CRLA National Dashboard_BoSY 2025-26 Assessment Results_Table.csv` | 38,965 |

### 3.2 External Data Sources

| Source | File | Purpose |
|--------|------|---------|
| DepEd School Level Database with PSGC | `SY 2024-2025 School Level Database WITH PSGC.xlsx` | Maps each School ID to a Philippine Standard Geographic Code (PSGC) municipality/city code |
| DOF BLGF Statement of Receipts and Expenditures | `By-LGU-SRE-2024.xlsx` | LGU-level revenue and expenditure data, including the Special Education Fund |

All input files are located in `data/raw/`.

### 3.3 Schema Hazards

The raw CRLA CSVs from different school years exhibit several inconsistencies that the pipeline resolves automatically:

1. **Column order differences**: 2024-25 places G2 Fil Transitioning before G2 Fil Developing; 2025-26 reverses them.
2. **Header typos**: `G2 FIl Higher Emergent` (capital I) appears in both years.
3. **Extra aggregate columns**: 2025-26 introduces per-grade Total Assessed columns not present in 2024-25.
4. **Encoding corruption**: Mojibake affecting approximately 28 school names per file (e.g., `ñ` corrupted to `¤`).

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

$$\bar{x}_s = \frac{1}{G} \sum_{g=1}^{G} \sum_{k=1}^{5} p_{s,g,k} \cdot w_k$$

where $p_{s,g,k}$ is the percentage of learners in school $s$, grade-language group $g$, at proficiency level $k$, and $w_k \in \{1, 2, 3, 4, 5\}$ are the ordinal values from Lower Emergent to Grade Level. The result is a score on the 1-5 scale: a value of 3.30 means the average learner in that school falls between the Developing and Transitioning levels.

**Why ordinal scoring over PCA.** An alternative PCA-based scoring method was explored, where weights are derived from the first principal component of the proficiency distribution. PCA weights proved unstable across reference timepoints — Grade Level receives weight 0 under a BoSY reference but weight 100 under an EoSY reference. The ordinal method uses fixed, interpretable weights that require no reference period.

| Property | PCA Scoring | Ordinal Scoring |
|----------|------------|-----------------|
| Scale | 0-100 (arbitrary) | 1-5 (proficiency levels) |
| Reference timepoint | Required | Not needed |
| Stability across timepoints | Weights change with reference | Fixed |
| Interpretability | Opaque | "Average proficiency level" |

#### 4.2.3 Ordinal Standard Deviation

The ordinal standard deviation measures how spread out a school's learners are across proficiency levels:

$$\sigma_s = \sqrt{\frac{1}{G} \sum_{g=1}^{G} \sum_{k=1}^{5} p_{s,g,k} \cdot (w_k - \bar{x}_{s,g})^2}$$

A low SD indicates learners are clustered around the mean level; a high SD indicates a wide spread (e.g., many learners at both Grade Level and Lower Emergent). Higher SD signals greater within-school inequality.

#### 4.2.4 Ordinal Skewness

The ordinal skewness captures asymmetry in the proficiency distribution:

$$\gamma_s = \frac{1}{G} \sum_{g=1}^{G} \frac{\sum_{k=1}^{5} p_{s,g,k} \cdot (w_k - \bar{x}_{s,g})^3}{\sigma_{s,g}^3}$$

Negative skewness (the national tendency) indicates a long lower tail — most learners are at higher levels but a subset remains at lower ones. Positive skewness indicates the reverse. Schools with zero SD (all learners at one level) have undefined skewness, treated as missing.

Reference: [`documentation/step_2_percentages_and_scoring.md`](documentation/step_2_percentages_and_scoring.md)

### 4.3 Validation

Each school is validated at two tiers. The **basic** tier requires at least one grade-language group with non-missing data. The **strict** tier, used for priority ranking, imposes three additional requirements:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Grade coverage | All three grade levels (G1, G2, G3) have at least one reporting group | Ensures the school's score reflects the full early-grade span |
| Group breadth | At least 4 of 6 grade-language groups reporting | Guards against scores driven by a single group |
| Minimum sample | At least 20 assessed learners in every reporting group | Ensures statistical stability of within-group percentages |

A segment delta between two timepoints additionally requires: (1) both endpoints pass basic validation, and (2) the total assessed student count does not change by more than 25% between endpoints.

$$\text{valid\_segment} = \text{valid}_{t_0} \;\wedge\; \text{valid}_{t_1} \;\wedge\; \left(\frac{|N_{t_1} - N_{t_0}|}{N_{t_0}} \leq 0.25\right)$$

The count-stability check guards against school mergers, splits, or data-entry errors that would make a progress comparison misleading.

### 4.4 Chain-Based Progress Scoring

An ordered time chain defines the sequence of assessment periods:

$$t_1 \;\rightarrow\; t_2 \;\rightarrow\; t_3 \quad = \quad \text{BoSY 2024-25} \;\rightarrow\; \text{EoSY 2024-25} \;\rightarrow\; \text{BoSY 2025-26}$$

For each consecutive pair $(t_i, t_{i+1})$, a **segment delta** is the change in ordinal mean:

$$\Delta_i = \bar{x}_{t_{i+1}} - \bar{x}_{t_i}$$

The **composite progress score** is the sum of all valid segment deltas, representing cumulative progress across the full chain:

$$\Delta_{\text{composite}} = \sum_{i} \Delta_i$$

Segment deltas are also computed for SD and skewness, tracking how distributional shape changes over time.

The pipeline extends automatically when new timepoints are added — appending a new entry to the time chain produces new segment deltas without modifying any existing computations.

Reference: [`documentation/step_3_chain_progress.md`](documentation/step_3_chain_progress.md)

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

$$\text{Need}_s = \sum_{j} \alpha_j \cdot z(c_{s,j})$$

where $c_{s,j}$ are six components and $\alpha_j$ are their weights:

| Component $c_{s,j}$ | Weight $\alpha_j$ | Direction | Interpretation |
|---------------------|-------------------|-----------|----------------|
| $5 - \bar{x}_{\text{end}}$ | 2.0 | Lower mean = higher need | Current proficiency level |
| $-\Delta_{\text{mean}}$ | 2.0 | Declining trajectory = higher need | Direction of change |
| $\sigma_{\text{end}}$ | 1.0 | Higher spread = higher need | Within-school inequality |
| $\gamma_{\text{end}}$ | 1.0 | Positive skew = higher need | Distribution shape |
| $\Delta_{\sigma}$ | 0.5 | Increasing spread = higher need | Change in inequality |
| $\Delta_{\gamma}$ | 0.5 | Worsening skew = higher need | Change in distribution shape |

**Pillar 2 — Impact.** The total number of assessed learners at the segment endpoint. Schools with more students represent a larger potential impact per intervention.

**Pillar 3 — Capacity Gap.** The inverse of the LGU's Special Education Fund (SEF) per school:

$$\text{SEF per school} = \frac{\text{LGU Special Education Fund}}{\text{Number of schools in LGU}}$$

The SEF is a component of Real Property Tax revenue earmarked for education. Lower SEF per school indicates the LGU has fewer resources available per school, representing a greater capacity gap.

**Composite.** Each pillar is converted to a percentile rank, then the composite is their product:

$$\text{Priority}_s = R_{\%}(\text{Need}_s) \;\times\; R_{\%}(\text{Impact}_s) \;\times\; R_{\%}(\text{CapacityGap}_s)$$

Percentile ranks map each pillar to a uniform $[0, 1]$ distribution regardless of its raw distribution shape. This is critical because assessed counts (skewness $\approx$ 5) and SEF per school (skewness $\approx$ 20) are heavily right-skewed — without this transformation, a handful of outlier schools would dominate the composite. The multiplicative form ensures a school must score high on **all three** dimensions to rank at the top.

Reference: [`documentation/priority_ranking.md`](documentation/priority_ranking.md)

### 4.7 Sensitivity Analysis

The Need pillar weights $\alpha_j$ are chosen by domain judgment, not estimated from data. To assess how much the final rankings depend on these choices, two analyses are conducted:

**Scenario comparison.** Five interpretable weight profiles — default, level-focused, delta-focused, mean-only, and equal — are compared using Kendall $\tau$ rank correlation (across all ranked schools) and Jaccard overlap (of the top-$N$ lists).

**Per-school robustness.** 500 random weight profiles are drawn from a Dirichlet distribution ($\alpha = 2.0$). For each school, the analysis reports the median priority percentile, interquartile range (IQR) of priority percentile, and the fraction of draws in which the school appears in the top-100. Schools with `frac_top_100 = 100%` are robust intervention targets whose ranking does not depend on the weight specification.

Reference: [`documentation/sensitivity_analysis.md`](documentation/sensitivity_analysis.md)

## 5. Key Results

### 5.1 National Proficiency Trends

Across 29,854 schools with valid data at all three timepoints:

| Timepoint | Mean | SD | Skewness | Interpretation |
|-----------|------|-----|----------|----------------|
| BoSY 2024-25 | 3.30 | 1.07 | -0.49 | Between Developing and Transitioning |
| EoSY 2024-25 | 4.13 | 0.87 | -1.18 | Above Transitioning |
| BoSY 2025-26 | 3.06 | 1.08 | -0.31 | Just above Developing |

| Segment | Mean Delta | Direction |
|---------|-----------|-----------|
| BoSY 2024-25 &rarr; EoSY 2024-25 | +0.82 | Within-year improvement |
| EoSY 2024-25 &rarr; BoSY 2025-26 | -1.04 | Cross-year decline |
| **Composite** | **-0.14** | **Slight net regression** |

The within-year gain indicates that schools moved learners upward by nearly a full proficiency level on average during SY 2024-25. However, the cross-year decline (summer learning loss plus new-cohort effects) more than offset this gain, resulting in a small net regression over the full observation window.

### 5.2 Validation Coverage

| Tier | BoSY 2024-25 | EoSY 2024-25 | BoSY 2025-26 |
|------|-------------|-------------|-------------|
| Basic (at least 1 group with data) | 35,280 (100%) | 37,042 (>99%) | 38,964 (>99%) |
| Strict (all grades, &ge;4 groups, &ge;20 per group) | 18,598 (53%) | 19,869 (54%) | 19,612 (50%) |
| Full chain, strict (all 3 timepoints) | 15,345 (39%) | | |

### 5.3 Priority Ranking

| Segment | Strict-Valid | Ranked | Dropped (missing LGU data) |
|---------|------------|--------|--------------------------|
| BoSY &rarr; EoSY 2024-25 | 17,925 | 17,836 | 89 |
| EoSY 2024-25 &rarr; BoSY 2025-26 | 16,831 | 16,749 | 82 |

Capacity gap statistics (SEF per school): national median = PHP 142,267; mean = PHP 618,732.

### 5.4 Sensitivity Analysis

**Scenario comparison** (Segment 1):

| Pair | Kendall $\tau$ | Top-100 Jaccard |
|------|--------------|-----------------|
| Default vs Mean-only | 0.917 | 88.7% |
| Default vs Equal | 0.935 | 83.5% |
| Default vs Level-focused | 0.858 | 66.7% |
| Default vs Delta-focused | 0.820 | 57.5% |

**Robustness** (500 Dirichlet draws, Segment 1):

| Stability Tier | IQR Threshold | Schools | Share |
|---------------|--------------|---------|-------|
| Stable | IQR < 0.05 | 10,703 | 60% |
| Moderate | 0.05 &le; IQR < 0.15 | 6,517 | 37% |
| Volatile | IQR &ge; 0.15 | 616 | 3% |

The overall rank ordering is robust (Kendall $\tau$ > 0.82 across all scenario pairs). The main axis of sensitivity is the relative emphasis on current proficiency levels versus trajectory — not the inclusion of SD or skewness.  Schools appearing in the top-100 across 100% of random weight draws are the strongest intervention candidates.

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
│   ├── step_1_schema_harmonizer.md    Schema normalization details
│   ├── step_2_percentages_and_scoring.md  Scoring methodology comparison
│   ├── step_3_chain_progress.md       Chain-based progress scoring
│   ├── step_4_output.md               Output format and verification
│   ├── priority_ranking.md            Three-pillar ranking methodology
│   ├── sensitivity_analysis.md        Weight sensitivity and robustness results
│   ├── lgu_matching.md                School-to-LGU crosswalk methodology
│   └── dashboard_plan.md              Streamlit dashboard specifications
│
├── dashboard/                         Interactive Streamlit dashboard
│   ├── app.py                         Application router
│   ├── pages/                         Dashboard views
│   └── data/                          Pre-computed dashboard data
│
├── data/
│   ├── raw/                           Input CSVs and external data files
│   └── modified/                      Crosswalks and reference files
│
├── output/                            Pipeline outputs
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
- scikit-learn (PCA scoring, optional)
- openpyxl (Excel parsing for PSGC and BLGF data)

### 7.2 Running the Pipeline

**1. Load and harmonize data:**

```python
import sys
sys.path.insert(0, 'modules')
from preprocessing import load_all_assessments

file_map = {
    ('2024-25', 'BoSY'): 'data/raw/CRLA Results Archive_SY 2024-25 Assessment Results_Table_BoSY.csv',
    ('2024-25', 'EoSY'): 'data/raw/CRLA Results Archive_SY 2024-25 Assessment Results_Table_EoSY.csv',
    ('2025-26', 'BoSY'): 'data/raw/CRLA National Dashboard_BoSY 2025-26 Assessment Results_Table.csv',
}
df_all = load_all_assessments(file_map=file_map, source='local')
```

**2. Compute ordinal moments and chain progress:**

```python
from analysis import process_all_timepoints, compute_chain_progress, TIME_CHAIN

results = process_all_timepoints(df_all, scoring='ordinal')
progress_df = compute_chain_progress(
    performance=results['performance'],
    raw_data=df_all,
    validation=results['validation'],
    time_chain=TIME_CHAIN,
    ordinal_sd=results['ordinal_sd'],
    ordinal_skew=results['ordinal_skew'],
)
```

**3. Export pairwise progress CSVs:**

```python
from output import export_pairwise_csvs

export_pairwise_csvs(
    percentages=results['percentages'],
    performance=results['performance'],
    validation=results['validation'],
    raw_data=df_all,
    weights=results['weights'],
    time_chain=TIME_CHAIN,
    output_dir='output',
)
```

**4. Generate priority rankings:**

```python
from lgu_matching import load_deped_psgc, load_lgu_revenue, build_school_lgu_crosswalk, match_lgu_revenue
from priority_ranking import compute_priority_ranking

psgc_df = load_deped_psgc('data/raw/SY 2024-2025 School Level Database WITH PSGC.xlsx')
crosswalk_df = build_school_lgu_crosswalk(psgc_df)
lgu_revenue_df = load_lgu_revenue('data/raw/By-LGU-SRE-2024.xlsx')
matched_lgu_df, unmatched_df, match_log = match_lgu_revenue(crosswalk_df, lgu_revenue_df)

for seg_idx in range(len(TIME_CHAIN) - 1):
    ranking_df, summary = compute_priority_ranking(
        progress_df, seg_idx, TIME_CHAIN, crosswalk_df, matched_lgu_df,
    )
    ranking_df.to_csv(f'output/priority_ranking_sef.{summary["segment"]}.csv')
```

**5. Run sensitivity analysis:**

```python
from sensitivity_analysis import run_scenario_comparison, run_robustness_analysis

for seg_idx in range(len(TIME_CHAIN) - 1):
    scen = run_scenario_comparison(progress_df, seg_idx, TIME_CHAIN, crosswalk_df, matched_lgu_df)
    rob = run_robustness_analysis(progress_df, seg_idx, TIME_CHAIN, crosswalk_df, matched_lgu_df)
```

### 7.3 Data Access

Raw input files can be loaded from local paths (as shown above) or from Google Cloud Storage. The default configuration in `modules/gcs_utils.py` points to the GCS bucket `data_ecair_paaral/raw/`. For local execution, pass a custom `file_map` to `load_all_assessments()` as shown above.

### 7.4 Adding New Timepoints

When new assessment data becomes available:

1. Place the raw CSV in `data/raw/`.
2. Add the corresponding `(school_year, period)` entry to `file_map` and `TIME_CHAIN`.
3. Re-run the pipeline. New segment deltas and priority rankings are computed automatically; existing segments are unchanged.
