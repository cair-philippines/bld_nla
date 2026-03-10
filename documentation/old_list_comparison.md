# Old Priority List Comparison

## Context

An earlier priority list of 131 schools was generated using the original PCA-based scoring method and shared with stakeholders. This analysis compares that list against the current ordinal-based three-pillar priority ranking to assess how well the two methods agree and explain any discrepancies.

## Methodology

The old list was generated for the **BoSY 2024-25 → EoSY 2024-25** segment (Learning period). The original list contained **131 entries**, but after deduplication there are **126 unique School IDs** (5 schools appeared twice). The comparison looks up each of the 126 unique schools in the current priority ranking for the same segment and examines:

1. **Coverage**: How many old schools appear in the current ranking (i.e., pass strict validation)?
2. **Percentile distribution**: Where do the matched schools fall in the current priority ranking?
3. **Pillar breakdown**: Which pillar(s) explain any shifts in ranking?

## Key Differences Between Methods

| Dimension | Old Method (PCA) | Current Method (Ordinal Three-Pillar) |
|---|---|---|
| Scoring | PCA-derived weights (unstable across timepoints) | Fixed ordinal weights (LE=1, HE=2, Dev=3, Trans=4, GL=5) |
| Validation | Minimal filtering | Strict: all 3 grades, ≥4 groups, ≥20 per group |
| Ranking pillars | Single composite | Need × Impact × Capacity Gap (multiplicative percentile ranks) |
| Capacity Gap metric | Not included | SEF per capita (SEF ÷ total enrolled in LGU) |
| Impact weighting | Not explicit | Assessed learner count as dedicated pillar |

## Results

### Coverage

| Category | Count |
|---|---|
| Entries in old list | 131 (126 unique IDs after deduplication) |
| Found in current ranking | 53 |
| Excluded by strict validation | 73 |

Over half the old list (73 schools) does not pass strict validation — these schools lack sufficient grade coverage or assessed learner counts to be reliably ranked. The old PCA method did not apply these filters, allowing small or incomplete schools to appear in the priority list.

### Priority Percentile Distribution (53 matched schools)

| Percentile Band | Count | Share |
|---|---|---|
| 90th+ | 15 | 28% |
| 70–90th | 17 | 32% |
| 50–70th | 13 | 25% |
| Below 50th | 8 | 15% |

**60% of matched schools still rank above the 70th percentile.** The old and new methods broadly agree on which schools have high need.

### Pillar-Level Median Percentiles

| Pillar | Median | Mean |
|---|---|---|
| Need | 96% | 91% |
| Impact | 45% | 44% |
| Capacity Gap | 59% | 59% |
| Priority (composite) | 75% | 72% |

### Interpretation

- **Need is consistently high** (median 96th percentile). The old PCA method correctly identified schools with poor reading outcomes — this dimension transfers well between methods.
- **Impact is low** (median 45th percentile). Many old-list schools are small. The PCA method had no size-based weighting, so small schools with extreme scores could rank highly. The current method's Impact pillar down-ranks these schools.
- **Capacity Gap is mixed** (median 59th percentile). The switch from no capacity metric to SEF per capita reshuffled this dimension. Schools in better-funded LGUs dropped in priority.

### Why Schools Dropped Out

The 73 excluded schools fall into overlapping categories:

1. **Insufficient grade coverage**: School does not assess all three grade levels (G1 + G2 + G3)
2. **Too few grade-language groups**: Fewer than 4 of 6 groups reporting
3. **Too few assessed learners**: Fewer than 20 learners in one or more reporting groups

These filters ensure that ranked schools have statistically meaningful data. Schools excluded by strict validation may genuinely be high-need, but their data is too sparse to rank confidently.

## Output File

`data/modified/old_list_vs_current_priority.xlsx` contains two sheets:

### Sheet 1: In Current Ranking (53 rows)

| Column | Description |
|---|---|
| School ID | DepEd school identifier |
| School Name | School name |
| Region | DepEd region |
| Division | DepEd division |
| total_assessed | Average assessed learners across both timepoints |
| ordinal_BoSY_2024-25 | Ordinal score at BoSY 2024-25 |
| ordinal_EoSY_2024-25 | Ordinal score at EoSY 2024-25 |
| delta_overall | Score change (EoSY minus BoSY) |
| pct_gl_EoSY_2024-25 | % at Grade Level at EoSY |
| need_pctile | Need percentile rank |
| impact_pctile | Impact percentile rank |
| capacity_gap_pctile | Capacity Gap percentile rank |
| priority_pctile | Composite priority percentile rank |
| priority_band | Categorical label (90th+, 70–90th, 50–70th, Below 50th) |
| lgu_name | Matched LGU name |
| sef_per_capita | SEF ÷ total enrolled in LGU (PHP) |

### Sheet 2: Excluded (73 rows)

| Column | Description |
|---|---|
| School ID | DepEd school identifier |
| School Name | School name |
| Region | DepEd region |
| Division | DepEd division |
| timepoints_available | Which timepoints the school has data for |
| ordinal_BoSY_2024-25 | Ordinal score at BoSY (if available) |
| assessed_BoSY_2024-25 | Assessed count at BoSY (if available) |
| pct_gl_BoSY_2024-25 | % at Grade Level at BoSY (if available) |
| ordinal_EoSY_2024-25 | Ordinal score at EoSY (if available) |
| assessed_EoSY_2024-25 | Assessed count at EoSY (if available) |
| pct_gl_EoSY_2024-25 | % at Grade Level at EoSY (if available) |
| reason | Why the school was excluded |

## Stakeholder Communication

For stakeholders who received the original 131-school list:

- **53 schools remain rankable** under the improved methodology, and 60% of those still fall in the top 30% nationally — the original list was directionally sound.
- **73 schools were excluded** not because they are unimportant, but because their data is too limited to rank reliably. These schools may warrant separate attention through data quality improvement efforts.
- **8 schools fell below the 50th percentile** — these were likely over-ranked by the old method due to small sample sizes or PCA instability.
- The new method adds two dimensions the old method lacked: **school size** (Impact) and **local funding capacity** (Capacity Gap), making the ranking more actionable for intervention targeting.
