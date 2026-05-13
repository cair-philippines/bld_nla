"""
Build the gold layer for CRLA.

Reads silver parquets, computes school-level indicators (ordinal moments,
EMD, bimodality coefficient), and writes two gold parquets:

    data/gold/crla_school_timepoints.parquet
        One row per school × timepoint. Contains ordinal mean, SD,
        skewness, excess kurtosis, bimodality coefficient, grade-level
        aggregations, total assessed, and validation flags.

    data/gold/crla_school_segments.parquet
        One row per school × segment (7 pairs across 5 timepoints).
        Contains delta mean, delta SD, delta skewness, EMD, and segment
        validity flags.

Usage:
    python scripts/build_gold.py

Prerequisites:
    Run scripts/build_silver.py --crla first.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "modules"))

from preprocessing import (
    SILVER_CRLA_DIR,
    GRADE_LANGUAGE_GROUPS,
    METADATA_COLUMNS,
    _get_group_columns,
    compute_percentages,
    get_total_assessed,
)
from analysis import (
    ORDINAL_WEIGHTS,
    ALL_TIMEPOINTS,
    SCHOOL_YEAR_CHAINS,
    _build_segment_pairs,
    _segment_label,
    compute_ordinal_moments,
    compute_emd,
)

GOLD_DIR = PROJECT_ROOT / "data" / "gold"

ORDINAL_VALUES = list(ORDINAL_WEIGHTS.values())

GRADE_LANG_LABELS = [
    f"{grade} {lang}" if lang else grade for grade, lang in GRADE_LANGUAGE_GROUPS
]


# ---------------------------------------------------------------------------
# Silver loader
# ---------------------------------------------------------------------------

def load_silver_crla(silver_dir=None):
    """
    Load all available CRLA silver parquets.

    Returns
    -------
    dict
        ``{(school_year, period): DataFrame}`` with raw-count DataFrames
        indexed by School ID.
    """
    if silver_dir is None:
        silver_dir = SILVER_CRLA_DIR

    silver_path = Path(silver_dir)
    result = {}
    for tp in ALL_TIMEPOINTS:
        sy, period = tp
        fpath = silver_path / f"{sy}_{period}.parquet"
        if fpath.exists():
            df = pd.read_parquet(fpath)
            result[tp] = df
            print(f"  Loaded silver {sy} {period}: {len(df)} schools")
        else:
            print(f"  ⚠ Silver not found: {fpath}")

    return result


# ---------------------------------------------------------------------------
# Build crla_school_timepoints
# ---------------------------------------------------------------------------

def build_timepoints(df_all, percentages):
    """
    Build the school × timepoint gold table.

    Columns
    -------
    School ID, school_year, period, timepoint_label,
    School Name, Region, Division, District,
    total_assessed, groups_with_data,
    ordinal_overall, ordinal_G1, ordinal_G2, ordinal_G3,
    pct_gl,
    ordinal_mean, ordinal_sd, ordinal_skew, ordinal_kurt, bimodality_coef,
    ordinal_{gl_label} for each grade-language group.
    """
    records = []

    for tp in ALL_TIMEPOINTS:
        if tp not in df_all:
            continue
        sy, period = tp
        label = f"{period} {sy}"

        raw_df = df_all[tp]
        pct_df = percentages[tp]

        # Ordinal moments
        moments = compute_ordinal_moments(pct_df)

        # Grade-level aggregated ordinal scores; track groups_with_data in same pass
        group_scores = {}
        group_gl_pcts = {}
        groups_present = []
        for gi, (grade, lang) in enumerate(GRADE_LANGUAGE_GROUPS):
            cols = _get_group_columns(grade, lang)
            gl_label = GRADE_LANG_LABELS[gi]
            group_data = pct_df[cols]
            has_data = group_data.notna().all(axis=1)
            groups_present.append(has_data)

            score = sum(
                group_data[col] * w for col, w in zip(cols, ORDINAL_VALUES)
            ) / 100
            score[~has_data] = np.nan
            group_scores[gl_label] = score
            group_gl_pcts[gl_label] = group_data[cols[-1]].where(has_data)

        groups_with_data = pd.concat(groups_present, axis=1).sum(axis=1).astype(int)

        ordinal_G1 = group_scores.get("G1", pd.Series(np.nan, index=pct_df.index))
        ordinal_G2 = pd.concat(
            [group_scores.get("G2 MT", pd.Series(np.nan, index=pct_df.index)),
             group_scores.get("G2 Fil", pd.Series(np.nan, index=pct_df.index))],
            axis=1,
        ).mean(axis=1)
        ordinal_G3 = pd.concat(
            [group_scores.get("G3 MT", pd.Series(np.nan, index=pct_df.index)),
             group_scores.get("G3 Fil", pd.Series(np.nan, index=pct_df.index)),
             group_scores.get("G3 Eng", pd.Series(np.nan, index=pct_df.index))],
            axis=1,
        ).mean(axis=1)
        pct_gl = pd.concat(list(group_gl_pcts.values()), axis=1).mean(axis=1)

        # Total assessed
        total_assessed = get_total_assessed(sy, period).reindex(pct_df.index)

        for sid in pct_df.index:
            rec = {
                "School ID": sid,
                "school_year": sy,
                "period": period,
                "timepoint_label": label,
                "total_assessed": total_assessed.get(sid, np.nan),
                "groups_with_data": int(groups_with_data.get(sid, 0)),
                "ordinal_overall": moments["ordinal_mean"].get(sid, np.nan),
                "ordinal_G1": ordinal_G1.get(sid, np.nan),
                "ordinal_G2": ordinal_G2.get(sid, np.nan),
                "ordinal_G3": ordinal_G3.get(sid, np.nan),
                "pct_gl": pct_gl.get(sid, np.nan),
                "ordinal_mean": moments["ordinal_mean"].get(sid, np.nan),
                "ordinal_sd": moments["ordinal_sd"].get(sid, np.nan),
                "ordinal_skew": moments["ordinal_skew"].get(sid, np.nan),
                "ordinal_kurt": moments["ordinal_kurt"].get(sid, np.nan),
                "bimodality_coef": moments["bimodality_coef"].get(sid, np.nan),
            }
            # Metadata
            for col in METADATA_COLUMNS:
                rec[col] = raw_df.at[sid, col] if col in raw_df.columns else np.nan
            # Per group ordinal
            for gl_label, score_series in group_scores.items():
                rec[f"ordinal_{gl_label.replace(' ', '_')}"] = score_series.get(sid, np.nan)
            records.append(rec)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Build crla_school_segments
# ---------------------------------------------------------------------------

def build_segments(percentages):
    """
    Build the school × segment gold table with delta metrics and EMD.

    Columns
    -------
    School ID, tp_from, tp_to, segment_label, seg_idx,
    delta_mean, delta_sd, delta_skew, emd_mean.
    """
    segment_pairs = _build_segment_pairs()
    records = []

    for seg_idx, (t0, t1) in enumerate(segment_pairs):
        label = _segment_label(t0, t1)
        tp_from = f"{t0[1]} {t0[0]}"
        tp_to = f"{t1[1]} {t1[0]}"

        if t0 not in percentages or t1 not in percentages:
            continue

        pct0 = percentages[t0]
        pct1 = percentages[t1]

        # Ordinal moments at both endpoints
        m0 = compute_ordinal_moments(pct0)
        m1 = compute_ordinal_moments(pct1)

        delta_mean = m1["ordinal_mean"] - m0["ordinal_mean"]
        delta_sd = m1["ordinal_sd"] - m0["ordinal_sd"]
        delta_skew = m1["ordinal_skew"] - m0["ordinal_skew"]

        # EMD
        emd = compute_emd(pct0, pct1).reindex(pct0.index)

        for sid in pct0.index:
            records.append({
                "School ID": sid,
                "tp_from": tp_from,
                "tp_to": tp_to,
                "segment_label": label,
                "seg_idx": seg_idx,
                "delta_mean": delta_mean.get(sid, np.nan),
                "delta_sd": delta_sd.get(sid, np.nan),
                "delta_skew": delta_skew.get(sid, np.nan),
                "emd_mean": emd.get(sid, np.nan),
            })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading CRLA silver ...")
    df_all = load_silver_crla()
    if not df_all:
        print("No silver files found. Run build_silver.py first.")
        return

    print("\nComputing percentages ...")
    percentages = {}
    for key, df in df_all.items():
        percentages[key] = compute_percentages(df)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    print("\nBuilding crla_school_timepoints ...")
    tp_df = build_timepoints(df_all, percentages)
    tp_out = GOLD_DIR / "crla_school_timepoints.parquet"
    tp_df.to_parquet(tp_out, index=False)
    print(f"  → {tp_out} ({len(tp_df)} rows, "
          f"{tp_df['School ID'].nunique()} schools, "
          f"{tp_df['timepoint_label'].nunique()} timepoints)")

    print("\nBuilding crla_school_segments ...")
    seg_df = build_segments(percentages)
    seg_out = GOLD_DIR / "crla_school_segments.parquet"
    seg_df.to_parquet(seg_out, index=False)
    print(f"  → {seg_out} ({len(seg_df)} rows, "
          f"{seg_df['School ID'].nunique()} schools, "
          f"{seg_df['segment_label'].nunique()} segments)")

    print(f"\nAll gold files written to {GOLD_DIR}/")


if __name__ == "__main__":
    main()
