# Old Priority List Comparison

## Context

An earlier priority list of 131 schools was generated using the original PCA-based scoring method and shared with stakeholders. This analysis compares that list against the current ordinal-based three-pillar priority ranking to assess how well the two methods agree and explain any discrepancies.

## Methodology

The old list was generated for the **BoSY 2024-25 → EoSY 2024-25** segment (Learning period). The authoritative source is `output/bbi_annex_b_school_ids.txt`, containing **131 unique School IDs**. The comparison looks up each school in the current priority ranking for the same segment and examines:

1. **Coverage**: How many old schools appear in the current ranking (i.e., pass strict validation)?
2. **Percentile distribution**: Where do the matched schools fall in the current priority ranking?
3. **Pillar breakdown**: Which pillar(s) explain any shifts in ranking?

## Key Differences Between Methods

| Dimension | Old Method (PCA) | Current Method (Ordinal Three-Pillar) |
|---|---|---|
| Scoring | PCA-derived weights (unstable across timepoints) | Fixed ordinal weights (LE=1, HE=2, Dev=3, Trans=4, GL=5) |
| Validation | Minimal filtering | Strict: all 3 grades, ≥4 groups, ≥15 per group |
| Ranking pillars | Single composite | Need × Impact × Capacity Gap (multiplicative percentile ranks) |
| Capacity Gap metric | Not included | SEF per capita (SEF ÷ total enrolled in LGU) |
| Impact weighting | Not explicit | Assessed learner count as dedicated pillar |

## Results

### Coverage

| Category | Count |
|---|---|
| Unique School IDs in old list | 131 |
| Found in current ranking | 66 |
| Excluded by strict validation | 65 |

About half the old list (65 schools) does not pass strict validation — these schools lack sufficient grade coverage or assessed learner counts to be reliably ranked. The old PCA method did not apply these filters, allowing small or incomplete schools to appear in the priority list.

### Why Schools Were Excluded

The 65 excluded schools fall into overlapping categories:

1. **Too few assessed learners** (61 schools): Fewer than 15 learners in one or more reporting groups, or total assessed count too low for reliable ordinal statistics
2. **Did not pass ranking criteria** (4 schools): Failed other strict validation checks (grade coverage, group breadth, or missing LGU data)

These filters ensure that ranked schools have statistically meaningful data. Schools excluded by strict validation may genuinely be high-need, but their data is too sparse to rank confidently.

## Output File

`data/modified/old_list_vs_current_priority.xlsx` contains two sheets:

### Sheet 1: In Current Ranking (66 rows)

| Column | Description |
|---|---|
| School ID | DepEd school identifier |
| School Name | School name |
| Division | DepEd division |
| Region | DepEd region |
| Mean Ordinal (Endpoint) | Ordinal mean at EoSY 2024-25 |
| SD Ordinal (Endpoint) | Ordinal SD at EoSY 2024-25 |
| Skew Ordinal (Endpoint) | Ordinal skewness at EoSY 2024-25 |
| Delta Mean | Change in ordinal mean across the segment |
| Delta SD | Change in SD across the segment |
| Delta Skew | Change in skewness across the segment |
| Assessed Learners | Total assessed at endpoint |
| LGU Name | Matched LGU name |
| SEF per Capita | SEF ÷ total enrolled in LGU (PHP) |
| Need Pctile | Need percentile rank |
| Impact Pctile | Impact percentile rank |
| Capacity Gap Pctile | Capacity Gap percentile rank |
| Priority Score | Composite priority score |
| Priority Pctile | Composite priority percentile rank |

### Sheet 2: Excluded (65 rows)

| Column | Description |
|---|---|
| School ID | DepEd school identifier |
| School Name | School name |
| Division | DepEd division |
| Region | DepEd region |
| Exclusion Reason | Why the school was excluded |

## Stakeholder Communication

For stakeholders who received the original 131-school list:

- **66 schools are now rankable** under the improved methodology — up from 53 after lowering the minimum group assessed threshold from 20 to 15.
- **65 schools were excluded** not because they are unimportant, but because their data is too limited to rank reliably. These schools may warrant separate attention through data quality improvement efforts.
- The new method adds two dimensions the old method lacked: **school size** (Impact) and **local funding capacity** (Capacity Gap), making the ranking more actionable for intervention targeting.
