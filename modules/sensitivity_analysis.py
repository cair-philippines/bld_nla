"""
Sensitivity analysis for the three-pillar priority ranking.

Two analyses:

1. **Scenario comparison**: Run a small set of interpretable weight
   profiles (level-focused, delta-focused, etc.) and measure pairwise
   rank stability via Kendall tau and top-N Jaccard overlap.

2. **Per-school robustness**: Monte Carlo draws of random weight
   profiles (Dirichlet), measuring each school's median percentile,
   IQR, and fraction of draws in the top-N.

Only the Need pillar is weight-dependent.  Impact and Capacity Gap
percentile ranks are computed once and reused across all weight
profiles.
"""

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from preprocessing import get_total_assessed
from analysis import _segment_label
from priority_ranking import DEFAULT_NEED_WEIGHTS, _z_score


# ---------------------------------------------------------------------------
# Predefined weight scenarios
# ---------------------------------------------------------------------------

PREDEFINED_SCENARIOS = {
    "default": {
        "level_mean": 2.0, "delta_mean": 2.0,
        "level_sd": 1.0, "level_skew": 1.0,
        "delta_sd": 0.5, "delta_skew": 0.5,
    },
    "level_focused": {
        "level_mean": 4.0, "delta_mean": 0.5,
        "level_sd": 2.0, "level_skew": 2.0,
        "delta_sd": 0.25, "delta_skew": 0.25,
    },
    "delta_focused": {
        "level_mean": 0.5, "delta_mean": 4.0,
        "level_sd": 0.25, "level_skew": 0.25,
        "delta_sd": 2.0, "delta_skew": 2.0,
    },
    "mean_only": {
        "level_mean": 3.0, "delta_mean": 3.0,
        "level_sd": 0.25, "level_skew": 0.25,
        "delta_sd": 0.25, "delta_skew": 0.25,
    },
    "equal": {
        "level_mean": 1.0, "delta_mean": 1.0,
        "level_sd": 1.0, "level_skew": 1.0,
        "delta_sd": 1.0, "delta_skew": 1.0,
    },
}

WEIGHT_KEYS = [
    "level_mean", "delta_mean",
    "level_sd", "level_skew",
    "delta_sd", "delta_skew",
]


# ---------------------------------------------------------------------------
# Weight-independent base preparation
# ---------------------------------------------------------------------------

def _prepare_base(
    progress_df, segment_idx, time_chain,
    crosswalk_df, matched_lgu_df,
    revenue_col="rpt_special_education_fund",
):
    """
    Extract all weight-independent work from compute_priority_ranking.

    Returns a dict with:
        df : DataFrame with metadata, pillar inputs, impact/capacity scores
        need_z : dict of 6 z-scored Series (keyed by weight name)
        impact_pctile : Series
        capacity_gap_pctile : Series
        summary : dict with counts and segment info
    """
    t0 = time_chain[segment_idx]
    t1 = time_chain[segment_idx + 1]
    seg_n = segment_idx + 1
    label = _segment_label(t0, t1)
    sy_end, period_end = t1

    perf_end_col = f"perf_{period_end}_{sy_end}"
    sd_end_col = f"sd_{period_end}_{sy_end}"
    skew_end_col = f"skew_{period_end}_{sy_end}"
    delta_col = f"seg{seg_n}_{label}"
    sd_delta_col = f"seg{seg_n}_{label}_sd_delta"
    skew_delta_col = f"seg{seg_n}_{label}_skew_delta"
    strict_col = f"seg{seg_n}_valid_strict"

    # Filter to strict-valid schools
    eligible = progress_df[progress_df[strict_col]].copy()
    n_strict = len(eligible)

    # Build DataFrame
    df = pd.DataFrame(index=eligible.index)
    df.index.name = "School ID"
    df["school_name"] = eligible.get("School Name")
    df["division"] = eligible.get("Division")
    df["region"] = eligible.get("Region")

    # Need inputs
    df["mean_end"] = eligible[perf_end_col]
    df["sd_end"] = eligible[sd_end_col]
    df["skew_end"] = eligible[skew_end_col]
    df["delta_mean"] = eligible[delta_col]
    df["delta_sd"] = eligible[sd_delta_col]
    df["delta_skew"] = eligible[skew_delta_col]

    # Impact
    assessed = get_total_assessed(sy_end, period_end)
    df["assessed_count"] = assessed.reindex(df.index)

    # Capacity Gap: LGU SEF per school
    xw = crosswalk_df.copy()
    if "School ID" in xw.columns:
        xw = xw.set_index("School ID")
    df["psgc_muni_code"] = xw["psgc_muni_code"].reindex(df.index)

    lgu = matched_lgu_df[["psgc_muni_code", "lgu_name", revenue_col]].copy()
    lgu = lgu.drop_duplicates(subset=["psgc_muni_code"])
    code_to_sef = lgu.set_index("psgc_muni_code")[revenue_col]
    code_to_name = lgu.set_index("psgc_muni_code")["lgu_name"]
    df["lgu_name"] = df["psgc_muni_code"].map(code_to_name)
    df["lgu_sef"] = df["psgc_muni_code"].map(code_to_sef)

    lgu_school_count = xw["psgc_muni_code"].dropna().value_counts()
    df["lgu_school_count"] = df["psgc_muni_code"].map(lgu_school_count)
    df["sef_per_school"] = df["lgu_sef"] / df["lgu_school_count"]

    # Drop missing
    required = ["mean_end", "delta_mean", "assessed_count", "sef_per_school"]
    n_before_drop = len(df)
    df = df.dropna(subset=required)

    for col in ["sd_end", "skew_end", "delta_sd", "delta_skew"]:
        df[col] = df[col].fillna(0)

    # Compute z-scored need components (weight-independent)
    need_z = {
        "level_mean": _z_score(5 - df["mean_end"]),
        "delta_mean": _z_score(-df["delta_mean"]),
        "level_sd": _z_score(df["sd_end"]),
        "level_skew": _z_score(df["skew_end"]),
        "delta_sd": _z_score(df["delta_sd"]),
        "delta_skew": _z_score(df["delta_skew"]),
    }

    # Weight-independent pillar scores and percentiles
    impact_score = df["assessed_count"]
    capacity_gap_score = _z_score(-df["sef_per_school"])
    impact_pctile = impact_score.rank(pct=True)
    capacity_gap_pctile = capacity_gap_score.rank(pct=True)

    # Drop internal columns
    df = df.drop(columns=["psgc_muni_code", "lgu_school_count"])

    summary = {
        "segment": f"seg{seg_n}_{label}",
        "time_start": t0,
        "time_end": t1,
        "strict_valid": n_strict,
        "dropped_missing_data": n_before_drop - len(df),
        "ranked": len(df),
        "revenue_column": revenue_col,
    }

    return {
        "df": df,
        "need_z": need_z,
        "impact_pctile": impact_pctile,
        "capacity_gap_pctile": capacity_gap_pctile,
        "summary": summary,
    }


def _rank_with_weights(base, weights):
    """
    Compute need score, percentiles, and composite for a single weight profile.

    Returns a Series of priority_pctile, indexed by School ID.
    """
    need_z = base["need_z"]
    need_score = sum(weights[k] * need_z[k] for k in WEIGHT_KEYS)
    need_pctile = need_score.rank(pct=True)
    priority_score = (
        need_pctile
        * base["impact_pctile"]
        * base["capacity_gap_pctile"]
    )
    return priority_score.rank(pct=True)


# ---------------------------------------------------------------------------
# Dirichlet weight draws
# ---------------------------------------------------------------------------

def _draw_dirichlet_weights(n_draws, alpha=2.0, seed=42):
    """
    Draw n_draws weight profiles from a Dirichlet distribution.

    Weights are scaled so they sum to the same total as DEFAULT_NEED_WEIGHTS
    (7.0), making them comparable in magnitude.
    """
    rng = np.random.default_rng(seed)
    total = sum(DEFAULT_NEED_WEIGHTS.values())
    alphas = np.full(len(WEIGHT_KEYS), alpha)
    raw = rng.dirichlet(alphas, size=n_draws)  # (n_draws, 6), rows sum to 1
    scaled = raw * total  # rows sum to 7.0

    profiles = []
    for i in range(n_draws):
        profiles.append({k: scaled[i, j] for j, k in enumerate(WEIGHT_KEYS)})
    return profiles


# ---------------------------------------------------------------------------
# 1. Scenario comparison
# ---------------------------------------------------------------------------

def run_scenario_comparison(
    progress_df, segment_idx, time_chain,
    crosswalk_df, matched_lgu_df,
    revenue_col="rpt_special_education_fund",
    scenarios=None,
    top_ns=None,
):
    """
    Compare priority rankings across predefined weight scenarios.

    Parameters
    ----------
    scenarios : dict, optional
        ``{name: weights_dict}``.  Defaults to ``PREDEFINED_SCENARIOS``.
    top_ns : list of int, optional
        Top-N thresholds for Jaccard overlap.  Default: [50, 100, 500].

    Returns
    -------
    dict
        rankings : {name: Series of priority_pctile}
        kendall_tau : DataFrame (scenario × scenario)
        jaccard : dict of {n: DataFrame} (scenario × scenario per top-N)
        base_summary : dict
    """
    if scenarios is None:
        scenarios = PREDEFINED_SCENARIOS
    if top_ns is None:
        top_ns = [50, 100, 500]

    base = _prepare_base(
        progress_df, segment_idx, time_chain,
        crosswalk_df, matched_lgu_df, revenue_col,
    )

    # Rank under each scenario
    rankings = {}
    for name, weights in scenarios.items():
        rankings[name] = _rank_with_weights(base, weights)

    names = list(rankings.keys())
    n_scen = len(names)

    # Kendall tau correlation matrix
    tau_matrix = np.ones((n_scen, n_scen))
    for i in range(n_scen):
        for j in range(i + 1, n_scen):
            tau, _ = kendalltau(rankings[names[i]], rankings[names[j]])
            tau_matrix[i, j] = tau
            tau_matrix[j, i] = tau
    kendall_df = pd.DataFrame(tau_matrix, index=names, columns=names)

    # Jaccard overlap at multiple top-N thresholds
    jaccard = {}
    for top_n in top_ns:
        top_sets = {}
        for name, pctile in rankings.items():
            top_sets[name] = set(
                pctile.sort_values(ascending=False).head(top_n).index
            )
        jac_matrix = np.ones((n_scen, n_scen))
        for i in range(n_scen):
            for j in range(i + 1, n_scen):
                si, sj = top_sets[names[i]], top_sets[names[j]]
                jac = len(si & sj) / len(si | sj)
                jac_matrix[i, j] = jac
                jac_matrix[j, i] = jac
        jaccard[top_n] = pd.DataFrame(jac_matrix, index=names, columns=names)

    # Print summary
    print(f"Scenario comparison: {base['summary']['segment']}")
    print(f"  Schools ranked: {base['summary']['ranked']}")
    print(f"  Scenarios: {', '.join(names)}")
    print()
    print("  Kendall tau rank correlations:")
    for i in range(n_scen):
        for j in range(i + 1, n_scen):
            print(f"    {names[i]:16s} vs {names[j]:16s}: "
                  f"tau={tau_matrix[i, j]:.3f}")
    print()
    for top_n in top_ns:
        print(f"  Jaccard overlap (top {top_n}):")
        jm = jaccard[top_n].values
        for i in range(n_scen):
            for j in range(i + 1, n_scen):
                print(f"    {names[i]:16s} vs {names[j]:16s}: "
                      f"{jm[i, j]:.1%}")
        print()

    return {
        "rankings": rankings,
        "kendall_tau": kendall_df,
        "jaccard": jaccard,
        "top_ns": top_ns,
        "base_summary": base["summary"],
    }


# ---------------------------------------------------------------------------
# 2. Per-school robustness (Monte Carlo)
# ---------------------------------------------------------------------------

def run_robustness_analysis(
    progress_df, segment_idx, time_chain,
    crosswalk_df, matched_lgu_df,
    revenue_col="rpt_special_education_fund",
    n_draws=500,
    top_n=100,
    alpha=2.0,
    seed=42,
):
    """
    Monte Carlo robustness analysis of priority rankings.

    Parameters
    ----------
    n_draws : int
        Number of random weight profiles to draw.
    top_n : int
        Threshold for ``frac_top_n`` (fraction of draws in top-N).
    alpha : float
        Dirichlet concentration.  Higher = draws cluster near equal
        weights; lower = more extreme profiles.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    dict
        robustness : DataFrame (one row per school, sorted by median_pctile)
        n_draws, top_n, alpha : parameters used
        base_summary : dict
    """
    base = _prepare_base(
        progress_df, segment_idx, time_chain,
        crosswalk_df, matched_lgu_df, revenue_col,
    )

    profiles = _draw_dirichlet_weights(n_draws, alpha=alpha, seed=seed)
    school_idx = base["df"].index
    n_schools = len(school_idx)

    # Collect priority percentiles across draws
    pctile_matrix = np.empty((n_schools, n_draws))
    for i, weights in enumerate(profiles):
        pctile = _rank_with_weights(base, weights)
        pctile_matrix[:, i] = pctile.values

    # Per-school statistics
    median_pctile = np.median(pctile_matrix, axis=1)
    q25 = np.percentile(pctile_matrix, 25, axis=1)
    q75 = np.percentile(pctile_matrix, 75, axis=1)
    iqr_pctile = q75 - q25

    # Fraction of draws where school is in the top-N
    # (top-N by priority_pctile = highest pctile values)
    ranks = np.empty_like(pctile_matrix)
    for i in range(n_draws):
        # Rank 1 = highest pctile
        ranks[:, i] = (-pctile_matrix[:, i]).argsort().argsort() + 1
    frac_top_n = (ranks <= top_n).mean(axis=1)

    mean_rank = ranks.mean(axis=1)
    rank_sd = ranks.std(axis=1)

    # Build output DataFrame
    rob = base["df"][["school_name", "division", "region"]].copy()
    rob["median_pctile"] = median_pctile
    rob["iqr_pctile"] = iqr_pctile
    rob["frac_top_n"] = frac_top_n
    rob["mean_rank"] = mean_rank
    rob["rank_sd"] = rank_sd
    rob = rob.sort_values("median_pctile", ascending=False)

    # Print summary
    n_ranked = base["summary"]["ranked"]
    print(f"Robustness analysis: {base['summary']['segment']}")
    print(f"  Schools ranked: {n_ranked}")
    print(f"  MC draws: {n_draws}, alpha={alpha}, seed={seed}")
    print(f"  Top-N threshold: {top_n}")
    print()

    # Stability summary
    stable = (rob["iqr_pctile"] < 0.05).sum()
    moderate = ((rob["iqr_pctile"] >= 0.05) & (rob["iqr_pctile"] < 0.15)).sum()
    volatile = (rob["iqr_pctile"] >= 0.15).sum()
    print(f"  Rank stability (by IQR of priority pctile):")
    print(f"    Stable   (IQR < 0.05): {stable:,} ({stable/n_ranked:.0%})")
    print(f"    Moderate (0.05-0.15):  {moderate:,} ({moderate/n_ranked:.0%})")
    print(f"    Volatile (IQR >= 0.15): {volatile:,} ({volatile/n_ranked:.0%})")
    print()

    # Top 10 most robust high-priority schools
    top_robust = rob[rob["frac_top_n"] > 0].head(10)
    print(f"  Top 10 most robust high-priority schools (top-{top_n}):")
    for i, (sid, row) in enumerate(top_robust.iterrows(), 1):
        print(
            f"    {i:2d}. {row['school_name'][:40]:<40s} "
            f"med_pctile={row['median_pctile']:.0%} "
            f"IQR={row['iqr_pctile']:.3f} "
            f"in_top{top_n}={row['frac_top_n']:.0%}"
        )
    print()

    return {
        "robustness": rob,
        "n_draws": n_draws,
        "top_n": top_n,
        "alpha": alpha,
        "seed": seed,
        "base_summary": base["summary"],
    }
