# Stakeholder Presentation Notebooks

## Overview

Three Jupyter notebooks prepared for stakeholder meetings. All are presentation-ready: code cells are hidden via CSS injection, leaving only narrative markdown and professional visualizations.

## Notebooks

### 1.0 — Methodology Walkthrough

**File**: `notebooks/1.0_methodology_walkthrough.ipynb`
**Purpose**: Explain the three-pillar priority ranking methodology to a non-technical audience.
**Structure**: 21 cells (14 code, 7 markdown), **12 charts**, 0 errors.

| Section | Content | Charts |
|---|---|---|
| A. National Reading Landscape | National proficiency distribution (stacked bar, all 3 timepoints) + funnel from total schools → strict-valid | 2 |
| B. Why the Mean Isn't Enough | Two schools with identical mean but different distributions (grouped bars) | 1 |
| C. Three Measures of Reading Proficiency | Triptych schematic — Mean (paired bars), SD (dot-and-whisker), Skewness (smoothed area curves via `make_interp_spline`). All panels share x-axis (LE→GL). Panel 3 distributions both verified mean = 3.00 | 1 |
| D. Which Schools Can We Reliably Rank? | Strict validation criteria + scatter (assessed vs groups) with quadrant shading | 1 |
| E. Three Pillars of Priority | Need × Impact × Capacity Gap explained. Pillar percentile distributions (3 histograms) + composite scatter (Need vs Impact, color = Capacity Gap) + top-20 priority table | 4 |
| F. Is the Ranking Robust? | Sensitivity analysis — scenario comparison (Kendall tau bar chart) + Monte Carlo IQR distribution (histogram) | 2 |
| Summary | Bullet-point recap | 0 |

**Key cell**: `f2068a2f` (index 9) — the triptych schematic. Modified to use dot-and-whisker for SD and smoothed area curves for skewness.

### 2.0 — Portfolio Analysis: 131 Schools

**File**: `notebooks/2.0_portfolio_analysis_131_schools.ipynb`
**Purpose**: Show stakeholders how their previously shared 131-school list compares against the improved methodology.
**Structure**: 24 cells (14 code, 10 markdown), **11 charts**, 0 errors.

| Section | Content | Charts |
|---|---|---|
| A. How Were the 131 Schools Identified? | Context on old PCA method, key differences table | 0 |
| B. Applying the New Method | Coverage summary (131 unique IDs → 66 in current ranking, 65 excluded). Priority band distribution (horizontal bar). Pillar percentile comparison (grouped bar: Need vs Impact vs Capacity Gap) | 3 |
| C. (unlabeled) | Scatter plot of Need vs Impact percentile for matched schools, colored by priority band | 1 |
| D. A Closer Look at Individual Schools | Top 10 and bottom 10 schools by priority percentile (horizontal bar pairs). Individual school profile cards (top 5 and bottom 5) showing pillar breakdown | 4 |
| E. What About the Excluded Schools? | Exclusion reasons breakdown (horizontal bar). Treemap or distribution of excluded schools by region | 2 |
| F. A System That Improves With Data | Forward-looking message about data quality → ranking quality | 1 |
| Key Takeaways | Bullet-point summary | 0 |

**Data source**: The original stakeholder list contains **131 unique School IDs** (authoritative source: `output/bbi_annex_b_school_ids.txt`). These are re-evaluated against the **Learning segment (BoSY → EoSY 2024-25)** priority ranking. Result: 66 matched, 65 excluded. Uses same strict validation and three-pillar composite as the main pipeline.

### 3.0 — Cycle 2 Interpretability

**File**: `notebooks/3.0_cycle2_interpretability.ipynb`
**Purpose**: Interpretability and explainability notebook for the top 100 2nd cycle priority schools (Retention segment).
**Structure**: 20 cells (13 code, 7 markdown), **11 charts**, 0 errors.

| Section | Content | Charts |
|---|---|---|
| A. Selection Process | Funnel (20,766 → top 100 after excluding 131 1st-cycle schools) + regional distribution bar chart | 2 |
| B. Profile of Top 100 | Three-pillar boxplots (top 100 vs national) + Need vs Impact scatter (color = Capacity Gap) | 2 |
| C. Pillar Deep Dive | Need decomposition (mean_end vs delta_mean scatter), Impact histogram, SEF per capita distribution | 3 |
| D. Individual School Profiles | Top 10 and bottom 10 within top 100 — grouped horizontal bars (Need, Impact, Capacity Gap pctile) | 1 |
| E. Cycle Comparison | Side-by-side pillar boxplots (1st vs 2nd cycle vs national) + regional overlap bars | 2 |
| F. Robustness Check | Cutoff sensitivity (80–150 threshold) + pillar Spearman correlation with composite | 1 |
| Key Takeaways | Bullet-point summary | 0 |

**Data source**: `output/priority_ranking_sef.Retention_2024-25_to_2025-26.csv` (20,766 schools). Top 100 excludes all 131 1st-cycle School IDs. Companion Excel: `output/priority_schools_cycle2_retention.xlsx` (2 sheets: full ranking + top 100).

## Visual Design

Both notebooks share a consistent professional style:

- **Color palette**: `PAL` dict — accent (#4DA688, teal), warning (#E07A3A, orange), highlight (#6CA6CD, steel blue), muted (#B0B0B0), dark (#2C3E50)
- **Typography**: Helvetica Neue / Arial, title 16pt bold, subtitle 14pt, body 11pt
- **Clean axes**: `clean_axes()` helper — removes top/right spines, uses light gray grid on y-axis only
- **rcParams**: Figure facecolor white, axes facecolor #FAFAFA, DPI 130, tight layout
- **Code hiding**: CSS injection (`display:none` on `div.input`, `div.prompt`) in first code cell

## Technical Review Fixes Applied

All 13 items from the technical review have been addressed:

1. Funnel chart sources data from the actual pipeline (not hardcoded)
2. School selection guarded against empty strict-valid set
3. Skewness distributions in Panel 3 both have mean = 3.0 (verified programmatically)
4. `nlargest`/`nsmallest` used instead of full sort for top/bottom-N
5. Segment annotation uses actual timepoint labels from data
6. Exclusion reasons derived from validation flags (not hardcoded)
7. School ID joins use correct dtype (int64)
8. No scipy KDE — smoothed curves use `make_interp_spline` only
9. Moments bridge chart connects methodology (Notebook 1) to portfolio (Notebook 2)
10. Panel 2 (SD) uses dot-and-whisker instead of paired bars
11. Panel 3 (Skewness) uses smoothed area curves instead of paired bars
12. Legend positions optimized (lower right for Panel 1)
13. All charts use consistent PAL colors and clean_axes styling

## Dependencies

- Python: numpy, pandas, matplotlib, seaborn, scipy (interpolation only), json, nbformat
- Data: pipeline outputs from `modules/` (preprocessing, analysis, priority_ranking, sensitivity_analysis)
- Container: runs inside `experiments-innovations-lab` via `ds` wrapper

## Output File

The old-list comparison also produced `data/modified/old_list_vs_current_priority.xlsx` — see `documentation/old_list_comparison.md` for full schema.

## Progress Log

| Date | Status | Notes |
|---|---|---|
| 2025-03-09 | Complete | Both notebooks built, 13 technical review fixes applied, aesthetic overhaul done, triptych cell (`f2068a2f`) updated with dot-and-whisker + smoothed area curves |
| 2025-03-09 | Revised | Notebook 2.0: switched from Retention to Learning segment (BoSY → EoSY 2024-25), explained 131→126 deduplication, fixed `seg2_valid`→`seg1_valid`, fixed overlapping labels (Chart 4 band legend, Chart 7 quadrant labels, Chart 8 TOP/BOTTOM labels) |
| 2025-03-09 | Threshold | Lowered `min_group_assessed` from 20 to 15 across pipeline. Coverage: 22,114 Learning / 20,766 Retention (was 17,836 / 16,749). Portfolio: 63 matched, 63 excluded (was 53/73). Both notebooks + dashboard data + CSVs regenerated. |
| 2025-03-09 | Cycle 2 | Generated `output/priority_schools_cycle2_retention.xlsx` (20,766 all + top 100 excluding 126 1st-cycle schools). Built Notebook 3.0 (11 charts, 6 sections). |
| 2026-03-09 | README | Comprehensive README rewrite with full methodology (math notation), reproducibility instructions, repo structure, AI disclosure. Added `documentation/policy_brief_crla_methodology.md` (one-page policy brief). |
| 2026-03-10 | 131 fix | Corrected school count from 126 → 131 unique IDs (no duplicates existed). Source: `output/bbi_annex_b_school_ids.txt`. Regenerated Excel files, re-executed notebooks 2.0 and 3.0. New counts: 66 matched / 65 excluded (Learning), 57 tagged as 1st cycle (Retention). |
| 2026-03-18 | Workflow shift | Transitioning to **within-school-year evaluation only** (Retention segment retired). EoSY 2025-26 data arrived (38,322 schools). MoSY 2025-26 added as optional intervention-subset timepoint. Cycle 2 list to be regenerated from within-year segments. See `documentation/within_year_evaluation.md`. |
| 2026-03-22 | Composite Excel | Built `output/priority_ranking_composite.xlsx` (4 sheets: ranked, top 100, reference, notes). 16,765 ranked schools, 131 1st-cycle tagged/excluded. Added Province + Municipality columns from PSGC crosswalk. Permanent build script: `scripts/build_composite_ranking.py`. |
| 2026-03-24 | Data refresh | Replaced dashboard exports with Mar 24 download. EoSY 2025-26 +421 schools. Composite ranked: 16,900 (+135). All outputs regenerated. |
