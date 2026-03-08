# Sensitivity Analysis of Priority Ranking Need Weights

## Overview

The Need pillar of the three-pillar priority ranking uses six weighted z-score components. The default weights are chosen by domain judgment, not estimated from data. This analysis tests how sensitive the final priority rankings are to the choice of weights, answering two questions:

1. **Does the weight choice matter?** (Scenario comparison)
2. **Which schools can we confidently act on?** (Per-school robustness)

## 1. Scenario Comparison

Five interpretable weight profiles are compared against each other:

| Scenario | level_mean | delta_mean | level_sd | level_skew | delta_sd | delta_skew | Focus |
|----------|-----------|-----------|---------|-----------|---------|-----------|-------|
| default | 2.0 | 2.0 | 1.0 | 1.0 | 0.5 | 0.5 | Balanced |
| level_focused | 4.0 | 0.5 | 2.0 | 2.0 | 0.25 | 0.25 | Current state only |
| delta_focused | 0.5 | 4.0 | 0.25 | 0.25 | 2.0 | 2.0 | Trajectory only |
| mean_only | 3.0 | 3.0 | 0.25 | 0.25 | 0.25 | 0.25 | Ignore distribution shape |
| equal | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | No prior |

### Metrics

- **Kendall tau**: Rank correlation across all ranked schools. Values near 1.0 indicate nearly identical orderings; values near 0 indicate unrelated orderings.
- **Jaccard overlap**: Fraction of schools shared between two scenarios' top-N lists. Computed at top-50, top-100, and top-500.

### Results — Segment 1 (Learning 2024-25)

**Kendall tau** (17,836 schools):

| Pair | Tau |
|------|-----|
| default vs equal | 0.935 |
| default vs mean_only | 0.917 |
| default vs level_focused | 0.858 |
| default vs delta_focused | 0.820 |
| level_focused vs delta_focused | 0.686 |

**Jaccard overlap (top 100)**:

| Pair | Overlap |
|------|---------|
| default vs mean_only | 88.7% |
| default vs equal | 83.5% |
| default vs level_focused | 66.7% |
| default vs delta_focused | 57.5% |
| level_focused vs delta_focused | 36.1% |

### Results — Segment 2 (Retention 2024-25 to 2025-26)

**Kendall tau** (16,749 schools):

| Pair | Tau |
|------|-----|
| default vs mean_only | 0.905 |
| default vs equal | 0.890 |
| default vs level_focused | 0.856 |
| default vs delta_focused | 0.754 |
| level_focused vs delta_focused | 0.621 |

**Jaccard overlap (top 100)**:

| Pair | Overlap |
|------|---------|
| default vs mean_only | 83.5% |
| default vs equal | 66.7% |
| default vs level_focused | 63.9% |
| default vs delta_focused | 46.0% |
| level_focused vs delta_focused | 26.6% |

### Interpretation

The overall rank ordering is **robust** — Kendall tau between default and its nearest alternatives exceeds 0.85 for both segments. Dropping SD and skewness entirely (mean_only) produces the most similar ranking to the default, confirming that the means dominate the Need pillar.

The top-N lists are **moderately sensitive**. At top-100, dropping distributional moments (mean_only) preserves ~85-88% of schools, but shifting focus between levels and deltas (level_focused vs delta_focused) drops overlap to 27-36%. This reflects a genuine tension: some schools have poor current levels but improving trajectories, and vice versa. The default weights balance both perspectives.

Segment 2 (Retention) shows more sensitivity than Segment 1 (Learning), particularly for delta-focused weights. This is expected: the retention segment captures summer learning loss, where the direction of change varies more across schools.

## 2. Per-School Robustness (Monte Carlo)

500 random weight profiles are drawn from a Dirichlet distribution (alpha=2.0, seed=42). Each draw produces a complete priority ranking. Per-school summary statistics measure how stable each school's position is across weight choices.

### Method

Weights are drawn from Dirichlet(alpha=2.0) and scaled to sum to 7.0 (matching the default total). Alpha=2.0 produces mildly concentrated draws — most profiles are "reasonable" but span a wide range of relative emphasis across the six components.

### Metrics per school

| Metric | Description |
|--------|-------------|
| `median_pctile` | Median priority percentile across 500 draws |
| `iqr_pctile` | IQR (75th - 25th percentile) of priority percentile — narrower = more stable |
| `frac_top_n` | Fraction of 500 draws where the school appears in the top-100 |
| `mean_rank` | Mean absolute rank position (1 = highest priority) |
| `rank_sd` | Standard deviation of absolute rank position |

### Stability Distribution

| Stability Tier | IQR threshold | Segment 1 | Segment 2 |
|----------------|--------------|-----------|-----------|
| Stable | IQR < 0.05 | 10,703 (60%) | 8,123 (48%) |
| Moderate | 0.05–0.15 | 6,517 (37%) | 7,297 (44%) |
| Volatile | IQR ≥ 0.15 | 616 (3%) | 1,329 (8%) |

The majority of schools have **stable** rankings regardless of weight choice. Only 3-8% of schools are volatile — these are schools where the level and delta components give conflicting signals (e.g., high current need but rapidly improving, or low current need but declining).

### Most Robust High-Priority Schools

**Segment 1 (Learning 2024-25)** — top-100 threshold:

| School | Median Pctile | IQR | In Top-100 |
|--------|--------------|-----|-----------|
| Sibuco CS | 100% | 0.000 | 100% |
| Pambujan 1 Central School | 100% | 0.000 | 100% |
| Mondragon I Central School | 100% | 0.000 | 100% |
| Sultan Naga Dimaporo Memorial IS | 100% | 0.000 | 100% |
| Proper Ned Elementary School | 100% | 0.000 | 100% |
| Lintangan Integrated School | 100% | 0.000 | 100% |
| Kaliantana Elementary School | 100% | 0.000 | 100% |
| Tuyan Integrated School | 100% | 0.000 | 100% |

**Segment 2 (Retention 2024-25 to 2025-26)** — top-100 threshold:

| School | Median Pctile | IQR | In Top-100 |
|--------|--------------|-----|-----------|
| Payao Central Elementary School | 100% | 0.000 | 100% |
| Mabinay Central School | 100% | 0.000 | 100% |
| Basud CS | 100% | 0.000 | 100% |
| Ronquillo & Dayanghirang ES | 100% | 0.000 | 100% |
| Duran ES (Camarines Sur) | 100% | 0.000 | 100% |

These schools appear in the top-100 across **100% of weight profiles** — they are high-need, high-impact, and low-resource regardless of how the Need pillar is weighted. These are the safest intervention targets.

## Practical Guidance

1. **The default weights are defensible.** The ranking is highly correlated (tau > 0.9) with both equal weights and mean-only weights.
2. **SD and skewness contribute marginally.** Dropping them changes ~12-15% of the top-100 list. They serve as tiebreakers among schools with similar means.
3. **Level vs delta emphasis matters more than distributional moments.** The biggest source of ranking instability is the relative emphasis on current state (level_mean) vs trajectory (delta_mean).
4. **Use `frac_top_n` for actionable targeting.** Schools with `frac_top_n = 100%` are robust intervention targets. Schools with `frac_top_n < 50%` are weight-sensitive and warrant case-by-case review.

## Output Files

| File | Description |
|------|-------------|
| `output/sensitivity_robustness.{segment}.csv` | Per-school robustness metrics (median pctile, IQR, frac_top_n, mean_rank, rank_sd) |
| `output/sensitivity_kendall_tau.{segment}.csv` | Pairwise Kendall tau matrix across 5 scenarios |
| `output/sensitivity_jaccard_top{N}.{segment}.csv` | Pairwise Jaccard overlap at top-50, 100, 500 |

## Module Reference

All functions are in `modules/sensitivity_analysis.py`:

| Function | Purpose |
|----------|---------|
| `run_scenario_comparison(...)` | Compare 5 predefined weight scenarios |
| `run_robustness_analysis(...)` | Monte Carlo robustness with Dirichlet weight draws |
| `_prepare_base(...)` | Extract weight-independent work (computed once) |
| `_rank_with_weights(base, weights)` | Recompute Need pillar + composite for a single weight profile |
| `_draw_dirichlet_weights(n, alpha, seed)` | Generate random weight profiles |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_draws` | 500 | Number of MC weight draws |
| `alpha` | 2.0 | Dirichlet concentration (higher = less extreme draws) |
| `top_n` | 100 | Threshold for `frac_top_n` metric |
| `seed` | 42 | Random seed for reproducibility |
