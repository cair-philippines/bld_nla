"""
Priority ranking for intervention targeting.

Combines three pillars to produce a principled school-level priority
list for a single assessment segment:

    Pillar 1 — Need: derived from ordinal mean, SD, and skewness
        (both endpoint levels and segment deltas)
    Pillar 2 — Impact: number of assessed learners
    Pillar 3 — Capacity Gap: inverse of LGU Special Education Fund
        (SEF) per enrolled learner in the LGU

The composite priority score is the product of percentile ranks across
all three pillars, so a school must score high on all three dimensions
to rank at the top. Percentile ranks neutralize distribution skewness
(assessed counts and SEF/capita are both heavily right-skewed).
"""

import numpy as np
import pandas as pd

from preprocessing import get_total_assessed
from analysis import _segment_label


# ---------------------------------------------------------------------------
# Default need weights
# ---------------------------------------------------------------------------

DEFAULT_NEED_WEIGHTS = {
    "level_mean": 2.0,
    "delta_mean": 2.0,
    "level_sd": 1.0,
    "level_skew": 1.0,
    "delta_sd": 0.5,
    "delta_skew": 0.5,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _z_score(s):
    """Standardize a Series to z-scores. Returns 0 for constant series."""
    std = s.std()
    if std == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / std


# ---------------------------------------------------------------------------
# Main ranking function
# ---------------------------------------------------------------------------

def compute_priority_ranking(
    progress_df,
    segment_idx,
    time_chain,
    crosswalk_df,
    matched_lgu_df,
    revenue_col="rpt_special_education_fund",
    need_weights=None,
    enrollment_df=None,
):
    """
    Compute a three-pillar priority ranking for intervention targeting.

    Filters to schools passing ``valid_strict`` at both segment
    endpoints and with complete data across all three pillars.

    Parameters
    ----------
    progress_df : pandas.DataFrame
        Output of ``compute_chain_progress()``, indexed by School ID.
    segment_idx : int
        0-based index of the segment in *time_chain* (0 = first
        consecutive pair).
    time_chain : list of tuples
        Ordered ``[(sy, period), ...]``.
    crosswalk_df : pandas.DataFrame
        School-to-LGU crosswalk with ``psgc_muni_code`` column.
        School ID as index or column.
    matched_lgu_df : pandas.DataFrame
        Matched LGU revenue data with ``psgc_muni_code`` and
        *revenue_col* columns.
    revenue_col : str, optional
        LGU revenue column for Capacity Gap pillar (SEF).
        Default: ``rpt_special_education_fund``.
    need_weights : dict, optional
        Weights for need components. Keys: ``level_mean``,
        ``delta_mean``, ``level_sd``, ``level_skew``, ``delta_sd``,
        ``delta_skew``. Defaults to ``DEFAULT_NEED_WEIGHTS``.
    enrollment_df : pandas.DataFrame, optional
        School-level enrollment with ``school_id`` and
        ``total_enrolled`` columns. Used to compute SEF per capita
        (SEF ÷ total enrolled in LGU). If None, falls back to
        SEF per school count.

    Returns
    -------
    pandas.DataFrame
        One row per eligible school, sorted by ``priority_score``
        descending (highest priority first). Includes pillar inputs,
        pillar scores, percentile ranks, and composite priority.
    dict
        Summary statistics (counts, thresholds, weights used).
    """
    if need_weights is None:
        need_weights = DEFAULT_NEED_WEIGHTS.copy()

    # ---- Identify segment columns ----
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

    for col in [perf_end_col, sd_end_col, skew_end_col, delta_col,
                sd_delta_col, skew_delta_col, strict_col]:
        if col not in progress_df.columns:
            raise ValueError(
                f"Column '{col}' not found in progress_df. "
                "Ensure compute_chain_progress was called with "
                "ordinal_sd, ordinal_skew, and strict validation."
            )

    # ---- Filter to strict-valid schools ----
    eligible = progress_df[progress_df[strict_col]].copy()
    n_strict = len(eligible)

    # ---- Build output DataFrame ----
    df = pd.DataFrame(index=eligible.index)
    df.index.name = "School ID"

    # Metadata
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

    # ---- Impact input: assessed count at end timepoint ----
    assessed = get_total_assessed(sy_end, period_end)
    df["assessed_count"] = assessed.reindex(df.index)

    # ---- Capacity Gap input: LGU SEF per capita ----
    # Prepare crosswalk
    xw = crosswalk_df.copy()
    if "School ID" in xw.columns:
        xw = xw.set_index("School ID")

    # Map school → LGU code
    df["psgc_muni_code"] = xw["psgc_muni_code"].reindex(df.index)

    # Map LGU code → SEF and name
    lgu = matched_lgu_df[["psgc_muni_code", "lgu_name", revenue_col]].copy()
    lgu = lgu.drop_duplicates(subset=["psgc_muni_code"])
    code_to_sef = lgu.set_index("psgc_muni_code")[revenue_col]
    code_to_name = lgu.set_index("psgc_muni_code")["lgu_name"]
    df["lgu_name"] = df["psgc_muni_code"].map(code_to_name)
    df["lgu_sef"] = df["psgc_muni_code"].map(code_to_sef)

    # Per-capita: total enrolled learners per LGU as denominator
    if enrollment_df is not None:
        enr = enrollment_df[["school_id", "total_enrolled"]].copy()
        enr = enr.merge(
            xw[["psgc_muni_code"]].reset_index(),
            left_on="school_id", right_on="School ID", how="inner",
        )
        lgu_enrolled = enr.groupby("psgc_muni_code")["total_enrolled"].sum()
        df["lgu_enrolled"] = df["psgc_muni_code"].map(lgu_enrolled)
        df["sef_per_capita"] = df["lgu_sef"] / df["lgu_enrolled"]
    else:
        # Fallback: per-school count
        lgu_school_count = xw["psgc_muni_code"].dropna().value_counts()
        df["lgu_enrolled"] = df["psgc_muni_code"].map(lgu_school_count)
        df["sef_per_capita"] = df["lgu_sef"] / df["lgu_enrolled"]

    # ---- Drop schools missing critical data ----
    required = [
        "mean_end", "delta_mean", "assessed_count", "sef_per_capita",
    ]
    n_before_drop = len(df)
    df = df.dropna(subset=required)

    # Fill NaN in secondary need components (sd=0 → skew=NaN edge case)
    for col in ["sd_end", "skew_end", "delta_sd", "delta_skew"]:
        df[col] = df[col].fillna(0)

    # ---- Pillar 1: Need (weighted z-scores) ----
    need_components = {
        "level_mean": _z_score(5 - df["mean_end"]),
        "delta_mean": _z_score(-df["delta_mean"]),
        "level_sd": _z_score(df["sd_end"]),
        "level_skew": _z_score(df["skew_end"]),
        "delta_sd": _z_score(df["delta_sd"]),
        "delta_skew": _z_score(df["delta_skew"]),
    }
    df["need_score"] = sum(
        need_weights[k] * v for k, v in need_components.items()
    )

    # ---- Pillar 2: Impact ----
    df["impact_score"] = df["assessed_count"]

    # ---- Pillar 3: Capacity Gap ----
    df["capacity_gap_score"] = _z_score(-df["sef_per_capita"])

    # ---- Percentile ranks ----
    df["need_pctile"] = df["need_score"].rank(pct=True)
    df["impact_pctile"] = df["impact_score"].rank(pct=True)
    df["capacity_gap_pctile"] = df["capacity_gap_score"].rank(pct=True)

    # ---- Composite (multiplicative on percentile ranks) ----
    # Percentile ranks neutralize distribution skewness (assessed counts
    # have skewness ~5, revenue/student ~20). Each pillar contributes
    # equally regardless of its raw distribution shape.
    df["priority_score"] = (
        df["need_pctile"] * df["impact_pctile"] * df["capacity_gap_pctile"]
    )
    df["priority_pctile"] = df["priority_score"].rank(pct=True)

    # ---- Sort by priority (highest first) ----
    df = df.sort_values("priority_score", ascending=False)

    # ---- Drop internal columns ----
    df = df.drop(columns=["psgc_muni_code", "lgu_enrolled"])

    # ---- Print summary ----
    n_ranked = len(df)
    print(f"Segment: seg{seg_n}_{label}")
    print(f"  Strict-valid schools: {n_strict}")
    print(f"  Dropped (missing LGU or count data): {n_before_drop - n_ranked}")
    print(f"  Ranked: {n_ranked}")
    print(f"  min_group_assessed threshold: 15 (part of valid_strict)")
    print(f"  Need weights: {need_weights}")
    print(f"  Revenue column: {revenue_col}")
    print()
    print(f"  Pillar statistics (across {n_ranked} ranked schools):")
    print(f"    Need score:    mean={df['need_score'].mean():.2f}, "
          f"std={df['need_score'].std():.2f}")
    print(f"    Impact:        mean={df['assessed_count'].mean():.0f}, "
          f"median={df['assessed_count'].median():.0f}")
    print(f"    Capacity gap:  mean={df['capacity_gap_score'].mean():.2f}, "
          f"std={df['capacity_gap_score'].std():.2f}")
    print(f"    SEF/capita:    mean={df['sef_per_capita'].mean():,.0f}, "
          f"median={df['sef_per_capita'].median():,.0f}")
    print()

    # Top 10
    print(f"  Top 10 by priority:")
    top10 = df.head(10)
    for i, (sid, row) in enumerate(top10.iterrows(), 1):
        print(
            f"    {i:2d}. {row['school_name'][:40]:<40s} "
            f"need={row['need_pctile']:.0%} "
            f"impact={row['impact_pctile']:.0%} "
            f"gap={row['capacity_gap_pctile']:.0%} "
            f"priority={row['priority_pctile']:.0%}"
        )

    summary = {
        "segment": f"seg{seg_n}_{label}",
        "time_start": t0,
        "time_end": t1,
        "total_in_progress": len(progress_df),
        "strict_valid": n_strict,
        "dropped_missing_data": n_before_drop - n_ranked,
        "ranked": n_ranked,
        "need_weights": need_weights,
        "revenue_column": revenue_col,
        "min_group_assessed_threshold": 15,
    }

    return df, summary
