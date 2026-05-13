"""
Build the gold layer for PhilIRI.

Reads silver parquets, computes school-level indicators, and writes six
gold parquets (KS2 and KS3 × three file types):

    data/gold/philiri_ks{2,3}_school_timepoints.parquet
        One row per school × timepoint (4 timepoints).
        Ordinal moments on the 3-level scale; BoSY-only depth indicators
        (pct_grade_ready, pct_3ld).

    data/gold/philiri_ks{2,3}_school_segments.parquet
        One row per school × within-year segment (BoSY→EoSY).
        Delta metrics and EMD on the 3-level scale.

    data/gold/philiri_ks{2,3}_bosy_yoy.parquet
        One row per school.  Compares BoSY 2024-25 to BoSY 2025-26
        using the full 7-level BoSY scale.

Usage:
    python scripts/build_gold_philiri.py [--ks2] [--ks3]

Prerequisites:
    Run scripts/build_silver.py --philiri first.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "modules"))

from philiri_preprocessing import (
    PHILIRI_SILVER_DIR,
    METADATA_COLUMNS,
    LANGUAGES,
    get_philiri_groups,
    PHILIRI_GRADES_BY_KS,
    _philiri_group_counts_bosy,
    _philiri_group_counts_eosy,
    compute_philiri_percentages,
    compute_philiri_percentages_7level,
)

GOLD_DIR = PROJECT_ROOT / "data" / "gold"

PHILIRI_TIMEPOINTS = [
    ("2024-25", "BoSY"),
    ("2024-25", "EoSY"),
    ("2025-26", "BoSY"),
    ("2025-26", "EoSY"),
]

# Ordinal weights for moment computation
WEIGHTS_3 = np.array([1.0, 2.0, 3.0])   # Frustration=1, Instructional=2, Independent=3
WEIGHTS_7 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])  # 3LD-F=1 … Grade Ready=7

LEVELS_3 = ["Frustration", "Instructional", "Independent"]
LEVELS_7 = [
    "3LD Frustration", "3LD Instructional", "3LD Independent",
    "2LD Frustration", "2LD Instructional", "2LD Independent",
    "Grade Ready",
]


# ---------------------------------------------------------------------------
# Silver loader
# ---------------------------------------------------------------------------

def load_silver_philiri(ks, silver_dir=None):
    """
    Load all four silver parquets for one key stage.

    Returns
    -------
    dict
        ``{(school_year, period): DataFrame}`` indexed by School ID.
    """
    if silver_dir is None:
        silver_dir = PROJECT_ROOT / PHILIRI_SILVER_DIR
    result = {}
    for sy, period in PHILIRI_TIMEPOINTS:
        fpath = Path(silver_dir) / f"{ks}_{sy}_{period}.parquet"
        if fpath.exists():
            df = pd.read_parquet(fpath)
            result[(sy, period)] = df
            print(f"  Loaded {ks} {sy} {period}: {len(df):,} schools")
        else:
            print(f"  ⚠ Not found: {fpath.name}")
    return result


# ---------------------------------------------------------------------------
# Generic ordinal moments and EMD
# ---------------------------------------------------------------------------

def _compute_moments(pct_df, groups, levels, weights):
    """
    Compute ordinal moments across grade-language groups.

    Parameters
    ----------
    pct_df : DataFrame
        Percentage DataFrame with columns ``{G} {lang} {level}``.
    groups : list of (grade, lang)
    levels : list of str
        Level suffixes matching pct_df column names.
    weights : np.ndarray
        Ordinal weights, one per level.

    Returns
    -------
    DataFrame
        Columns: ordinal_mean, ordinal_sd, ordinal_skew, ordinal_kurt
        (excess), bimodality_coef.
    """
    w = weights.astype(float)
    group_means, group_sds, group_skews, group_kurts, group_bcs = [], [], [], [], []

    for grade, lang in groups:
        cols = [f"{grade} {lang} {lv}" for lv in levels]
        if not all(c in pct_df.columns for c in cols):
            continue
        group_data = pct_df[cols]
        has_data = group_data.notna().all(axis=1)
        pct = group_data.values.astype(float)

        mean = (pct * w).sum(axis=1) / 100
        dev = w - mean[:, np.newaxis]
        var = (pct * dev ** 2).sum(axis=1) / 100
        sd = np.sqrt(var)

        with np.errstate(divide="ignore", invalid="ignore"):
            skew = (pct * dev ** 3).sum(axis=1) / 100 / (sd ** 3)
            kurt_reg = (pct * dev ** 4).sum(axis=1) / 100 / (sd ** 4)
            bc = (skew ** 2 + 1) / kurt_reg

        mask = ~has_data.values | (sd == 0)
        for arr in (mean, sd, skew, bc):
            arr[mask] = np.nan
        kurt_excess = np.where(mask, np.nan, kurt_reg - 3.0)

        group_means.append(pd.Series(mean, index=pct_df.index))
        group_sds.append(pd.Series(sd, index=pct_df.index))
        group_skews.append(pd.Series(skew, index=pct_df.index))
        group_kurts.append(pd.Series(kurt_excess, index=pct_df.index))
        group_bcs.append(pd.Series(bc, index=pct_df.index))

    if not group_means:
        empty = pd.Series(np.nan, index=pct_df.index)
        return pd.DataFrame({k: empty for k in [
            "ordinal_mean", "ordinal_sd", "ordinal_skew", "ordinal_kurt", "bimodality_coef"
        ]})

    return pd.DataFrame({
        "ordinal_mean": pd.concat(group_means, axis=1).mean(axis=1),
        "ordinal_sd": pd.concat(group_sds, axis=1).mean(axis=1),
        "ordinal_skew": pd.concat(group_skews, axis=1).mean(axis=1),
        "ordinal_kurt": pd.concat(group_kurts, axis=1).mean(axis=1),
        "bimodality_coef": pd.concat(group_bcs, axis=1).mean(axis=1),
    })


def _compute_emd(pct_df_t0, pct_df_t1, groups, levels, weights):
    """
    Compute mean EMD (Wasserstein-1) per school between two timepoints.

    Returns a Series indexed by the union of both DataFrames' indices.
    """
    w = weights.astype(float)
    common = pct_df_t0.index.intersection(pct_df_t1.index)
    group_emds = []

    for grade, lang in groups:
        cols = [f"{grade} {lang} {lv}" for lv in levels]
        if not all(c in pct_df_t0.columns for c in cols):
            continue
        g0 = pct_df_t0.reindex(common)[cols]
        g1 = pct_df_t1.reindex(common)[cols]
        has_data = g0.notna().all(axis=1) & g1.notna().all(axis=1)
        valid_idx = has_data[has_data].index

        emds = pd.Series(np.nan, index=common)
        if len(valid_idx) > 0:
            p0 = g0.loc[valid_idx].values.astype(float) / 100
            p1 = g1.loc[valid_idx].values.astype(float) / 100
            emd_vals = np.array([
                wasserstein_distance(w, w, p0[i], p1[i])
                for i in range(len(valid_idx))
            ])
            emds.loc[valid_idx] = emd_vals
        group_emds.append(emds)

    if not group_emds:
        return pd.Series(np.nan, index=common)

    all_idx = pct_df_t0.index.union(pct_df_t1.index)
    return pd.concat(group_emds, axis=1).mean(axis=1).reindex(all_idx)


# ---------------------------------------------------------------------------
# Assessed-count helpers
# ---------------------------------------------------------------------------

def _bosy_total_assessed(raw_df, ks):
    """
    Estimate total assessed students at BoSY.

    KS2: sums the per-grade ``{G} Assessed`` columns (combined Fil+Eng total).
    KS3: sums max(Fil assessed, Eng assessed) per grade as proxy for unique
    students, where per-language counts are derived from column sums.
    """
    grades = PHILIRI_GRADES_BY_KS[ks]
    if ks == "ks2":
        cols = [f"{g} Assessed" for g in grades if f"{g} Assessed" in raw_df.columns]
        if cols:
            return raw_df[cols].fillna(0).sum(axis=1)
    # KS3 fallback: max of per-language denominators per grade
    grade_totals = []
    for grade in grades:
        lang_sums = []
        for lang in LANGUAGES:
            f, i, ind = _philiri_group_counts_bosy(raw_df, grade, lang)
            lang_sums.append((f + i + ind))
        grade_totals.append(pd.concat(lang_sums, axis=1).max(axis=1))
    return pd.concat(grade_totals, axis=1).sum(axis=1)


def _eosy_total_assessed(raw_df, ks):
    """
    Estimate total re-assessed students at EoSY (sum of per-language
    column denominators across all grades).
    """
    grades = PHILIRI_GRADES_BY_KS[ks]
    grade_totals = []
    for grade in grades:
        lang_sums = []
        for lang in LANGUAGES:
            f, i, ind = _philiri_group_counts_eosy(raw_df, grade, lang)
            lang_sums.append(f + i + ind)
        grade_totals.append(pd.concat(lang_sums, axis=1).max(axis=1))
    return pd.concat(grade_totals, axis=1).sum(axis=1)


def _bosy_non_gr(raw_df, ks):
    """
    Count non-Grade-Ready students at BoSY (the maximum eligible pool
    for EoSY reassessment).
    """
    grades = PHILIRI_GRADES_BY_KS[ks]
    grade_totals = []
    for grade in grades:
        lang_sums = []
        for lang in LANGUAGES:
            f, i, ind = _philiri_group_counts_bosy(raw_df, grade, lang)
            # ind includes Grade Ready + 2LD-Ind; subtract Grade Ready
            def _get(col):
                return (
                    raw_df[col].fillna(0) if col in raw_df.columns
                    else pd.Series(0.0, index=raw_df.index)
                )
            gr = _get(f"{grade} {lang} Grade Ready")
            lang_sums.append(f + i + ind - gr)
        grade_totals.append(pd.concat(lang_sums, axis=1).max(axis=1))
    return pd.concat(grade_totals, axis=1).sum(axis=1)


# ---------------------------------------------------------------------------
# Build timepoints
# ---------------------------------------------------------------------------

def build_timepoints(ks, df_all):
    """
    Build the school × timepoint gold table.

    For BoSY timepoints, additional columns ``pct_grade_ready`` and
    ``pct_3ld`` are computed from the raw silver data.
    """
    groups = get_philiri_groups(ks)
    records = []

    for (sy, period), raw_df in sorted(df_all.items()):
        pct3 = compute_philiri_percentages(raw_df, ks, period)
        moments = _compute_moments(pct3, groups, LEVELS_3, WEIGHTS_3)

        # groups_with_data: count of grade-language groups with all 3 levels present
        groups_present = []
        for grade, lang in groups:
            cols = [f"{grade} {lang} {lv}" for lv in LEVELS_3]
            has = pct3[cols].notna().all(axis=1) & (pct3[cols].sum(axis=1) > 0)
            groups_present.append(has)
        groups_with_data = pd.concat(groups_present, axis=1).sum(axis=1).astype(int)

        # BoSY-only depth indicators (averaged across groups)
        if period == "BoSY":
            gr_pcts, ld3_pcts = [], []
            for grade, lang in groups:
                def _get(col, df=raw_df):
                    return df[col].fillna(0) if col in df.columns else pd.Series(0.0, index=df.index)
                f, i, ind = _philiri_group_counts_bosy(raw_df, grade, lang)
                denom = (f + i + ind).replace(0, np.nan)
                gr = _get(f"{grade} {lang} Grade Ready")
                ld3 = (
                    _get(f"{grade} 3LD {lang} Frustration")
                    + _get(f"{grade} 3LD {lang} Instructional")
                    + _get(f"{grade} 3LD {lang} Independent")
                )
                gr_pcts.append((gr / denom * 100).where(denom.notna()))
                ld3_pcts.append((ld3 / denom * 100).where(denom.notna()))
            pct_grade_ready = pd.concat(gr_pcts, axis=1).mean(axis=1)
            pct_3ld = pd.concat(ld3_pcts, axis=1).mean(axis=1)
            total_assessed = _bosy_total_assessed(raw_df, ks)
        else:
            pct_grade_ready = pd.Series(np.nan, index=raw_df.index)
            pct_3ld = pd.Series(np.nan, index=raw_df.index)
            total_assessed = _eosy_total_assessed(raw_df, ks)

        label = f"{period} {sy}"
        for sid in raw_df.index:
            rec = {
                "School ID": sid,
                "school_year": sy,
                "period": period,
                "ks": ks,
                "timepoint_label": label,
                "total_assessed": total_assessed.get(sid, np.nan),
                "groups_with_data": int(groups_with_data.get(sid, 0)),
                "ordinal_mean": moments["ordinal_mean"].get(sid, np.nan),
                "ordinal_sd": moments["ordinal_sd"].get(sid, np.nan),
                "ordinal_skew": moments["ordinal_skew"].get(sid, np.nan),
                "ordinal_kurt": moments["ordinal_kurt"].get(sid, np.nan),
                "bimodality_coef": moments["bimodality_coef"].get(sid, np.nan),
                "pct_grade_ready": pct_grade_ready.get(sid, np.nan),
                "pct_3ld": pct_3ld.get(sid, np.nan),
            }
            for col in METADATA_COLUMNS:
                rec[col] = raw_df.at[sid, col] if col in raw_df.columns else np.nan
            records.append(rec)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Build segments (BoSY → EoSY, within year)
# ---------------------------------------------------------------------------

def build_segments(ks, df_all):
    """
    Build the school × segment gold table for within-year BoSY→EoSY segments.

    Columns
    -------
    School ID, ks, school_year, segment_label,
    delta_mean, delta_sd, delta_skew, emd_mean.
    """
    groups = get_philiri_groups(ks)
    records = []

    for sy in ["2024-25", "2025-26"]:
        t0, t1 = (sy, "BoSY"), (sy, "EoSY")
        if t0 not in df_all or t1 not in df_all:
            continue

        raw0, raw1 = df_all[t0], df_all[t1]
        pct0 = compute_philiri_percentages(raw0, ks, "BoSY")
        pct1 = compute_philiri_percentages(raw1, ks, "EoSY")

        m0 = _compute_moments(pct0, groups, LEVELS_3, WEIGHTS_3)
        m1 = _compute_moments(pct1, groups, LEVELS_3, WEIGHTS_3)

        delta_mean = m1["ordinal_mean"] - m0["ordinal_mean"]
        delta_sd = m1["ordinal_sd"] - m0["ordinal_sd"]
        delta_skew = m1["ordinal_skew"] - m0["ordinal_skew"]
        emd = _compute_emd(pct0, pct1, groups, LEVELS_3, WEIGHTS_3).reindex(pct0.index)

        label = f"Learning_{sy}"
        for sid in pct0.index:
            records.append({
                "School ID": sid,
                "ks": ks,
                "school_year": sy,
                "segment_label": label,
                "delta_mean": delta_mean.get(sid, np.nan),
                "delta_sd": delta_sd.get(sid, np.nan),
                "delta_skew": delta_skew.get(sid, np.nan),
                "emd_mean": emd.get(sid, np.nan),
            })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Build YoY BoSY (7-level scale)
# ---------------------------------------------------------------------------

def build_bosy_yoy(ks, df_all):
    """
    Build the year-over-year BoSY comparison table.

    Uses the full 7-level BoSY scale (3LD-F=1 … Grade Ready=7), which
    preserves depth-of-need information not available at EoSY.

    The two BoSY timepoints are independent cohorts; count fluctuation is
    expected and is retained as informational ``count_stable`` but does not
    gate ``valid``.
    """
    groups = get_philiri_groups(ks)
    t0 = ("2024-25", "BoSY")
    t1 = ("2025-26", "BoSY")
    if t0 not in df_all or t1 not in df_all:
        print(f"  ⚠ Cannot build YoY BoSY for {ks}: missing timepoint(s)")
        return pd.DataFrame()

    raw0, raw1 = df_all[t0], df_all[t1]
    pct7_0 = compute_philiri_percentages_7level(raw0, ks)
    pct7_1 = compute_philiri_percentages_7level(raw1, ks)

    common = pct7_0.index.intersection(pct7_1.index)

    # Cohort size change (informational only — independent cohorts).
    cnt0 = _bosy_total_assessed(raw0, ks).reindex(common)
    cnt1 = _bosy_total_assessed(raw1, ks).reindex(common)
    count_stable = ((cnt1 - cnt0).abs() / cnt0 <= 0.25).fillna(False)

    m0 = _compute_moments(pct7_0.reindex(common), groups, LEVELS_7, WEIGHTS_7)
    m1 = _compute_moments(pct7_1.reindex(common), groups, LEVELS_7, WEIGHTS_7)

    delta_mean = m1["ordinal_mean"] - m0["ordinal_mean"]
    delta_sd = m1["ordinal_sd"] - m0["ordinal_sd"]
    delta_skew = m1["ordinal_skew"] - m0["ordinal_skew"]
    emd = _compute_emd(pct7_0, pct7_1, groups, LEVELS_7, WEIGHTS_7).reindex(common)

    # BoSY-only depth indicators (change)
    def _gr_pct(raw_df):
        cols = []
        for grade, lang in groups:
            def _get(col, df=raw_df):
                return df[col].fillna(0) if col in df.columns else pd.Series(0.0, index=df.index)
            f, i, ind = _philiri_group_counts_bosy(raw_df, grade, lang)
            denom = (f + i + ind).replace(0, np.nan)
            gr = _get(f"{grade} {lang} Grade Ready")
            cols.append((gr / denom * 100).where(denom.notna()))
        return pd.concat(cols, axis=1).mean(axis=1)

    def _ld3_pct(raw_df):
        cols = []
        for grade, lang in groups:
            def _get(col, df=raw_df):
                return df[col].fillna(0) if col in df.columns else pd.Series(0.0, index=df.index)
            f, i, ind = _philiri_group_counts_bosy(raw_df, grade, lang)
            denom = (f + i + ind).replace(0, np.nan)
            ld3 = (
                _get(f"{grade} 3LD {lang} Frustration")
                + _get(f"{grade} 3LD {lang} Instructional")
                + _get(f"{grade} 3LD {lang} Independent")
            )
            cols.append((ld3 / denom * 100).where(denom.notna()))
        return pd.concat(cols, axis=1).mean(axis=1)

    gr0 = _gr_pct(raw0).reindex(common)
    gr1 = _gr_pct(raw1).reindex(common)
    ld3_0 = _ld3_pct(raw0).reindex(common)
    ld3_1 = _ld3_pct(raw1).reindex(common)

    delta_pct_grade_ready = gr1 - gr0
    delta_pct_3ld = ld3_1 - ld3_0

    records = []
    for sid in common:
        records.append({
            "School ID": sid,
            "ks": ks,
            "delta_mean": delta_mean.get(sid, np.nan),
            "delta_sd": delta_sd.get(sid, np.nan),
            "delta_skew": delta_skew.get(sid, np.nan),
            "delta_pct_grade_ready": delta_pct_grade_ready.get(sid, np.nan),
            "delta_pct_3ld": delta_pct_3ld.get(sid, np.nan),
            "emd_mean": emd.get(sid, np.nan),
            "count_stable": bool(count_stable.get(sid, False)),
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_ks(ks):
    print(f"\n{'='*50}")
    print(f"Building PhilIRI gold — {ks.upper()}")
    print(f"{'='*50}")

    print(f"\nLoading {ks} silver ...")
    df_all = load_silver_philiri(ks)
    if not df_all:
        print(f"  No silver files found for {ks}. Run build_silver.py --philiri first.")
        return

    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nBuilding philiri_{ks}_school_timepoints ...")
    tp_df = build_timepoints(ks, df_all)
    tp_out = GOLD_DIR / f"philiri_{ks}_school_timepoints.parquet"
    tp_df.to_parquet(tp_out, index=False)
    print(f"  → {tp_out.name} ({len(tp_df):,} rows, "
          f"{tp_df['School ID'].nunique():,} schools, "
          f"{tp_df['timepoint_label'].nunique()} timepoints)")

    print(f"\nBuilding philiri_{ks}_school_segments ...")
    seg_df = build_segments(ks, df_all)
    seg_out = GOLD_DIR / f"philiri_{ks}_school_segments.parquet"
    seg_df.to_parquet(seg_out, index=False)
    n_segs = seg_df["segment_label"].nunique() if not seg_df.empty else 0
    print(f"  → {seg_out.name} ({len(seg_df):,} rows, "
          f"{seg_df['School ID'].nunique():,} schools, "
          f"{n_segs} segments)")

    print(f"\nBuilding philiri_{ks}_bosy_yoy ...")
    yoy_df = build_bosy_yoy(ks, df_all)
    if not yoy_df.empty:
        yoy_out = GOLD_DIR / f"philiri_{ks}_bosy_yoy.parquet"
        yoy_df.to_parquet(yoy_out, index=False)
        print(f"  → {yoy_out.name} ({len(yoy_df):,} rows, "
              f"{yoy_df['School ID'].nunique():,} schools)")


def main():
    parser = argparse.ArgumentParser(description="Build PhilIRI gold layer")
    parser.add_argument("--ks2", action="store_true")
    parser.add_argument("--ks3", action="store_true")
    args = parser.parse_args()

    run_ks2 = args.ks2 or not (args.ks2 or args.ks3)
    run_ks3 = args.ks3 or not (args.ks2 or args.ks3)

    if run_ks2:
        build_ks("ks2")
    if run_ks3:
        build_ks("ks3")

    print(f"\nAll PhilIRI gold files written to {GOLD_DIR}/")


if __name__ == "__main__":
    main()
